#!/usr/bin/env python3

"""
Unit tests for download resume and retry behavior.

These tests focus on implementation details of resume and retry mechanisms.
For behavior-driven tests of software update functionality, see bdd_software_update.py.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

from collections.abc import Iterator
from typing import Self

from httpx2 import ConnectError, ReadTimeout

from ardupilot_methodic_configurator.backend_internet import (
    DOWNLOAD_BLOCK_SIZE,
    _attempt_download_once,
    _existing_size_and_headers,
    _write_response,
    download_file_from_url,
)


class DummyResponse:
    """Mock HTTP response object for testing download resume functionality."""

    def __init__(self, chunks: Iterator[bytes], headers: dict[str, str], status_code: int = 200) -> None:
        self._chunks = list(chunks)
        self.headers = headers
        self.status_code = status_code

    def __enter__(self) -> Self:
        """Open the streamed response."""
        return self

    def __exit__(self, *_exc_info: object) -> None:
        """Close the streamed response."""

    def raise_for_status(self) -> None:
        return None

    def iter_bytes(self, chunk_size: int = 8192) -> Iterator[bytes]:  # pylint: disable=unused-argument
        yield from self._chunks


def test_resume_headers_match_existing_file_state(tmp_path) -> None:
    """
    Resume requests match the existing file size and omit ranges when no bytes exist.

    GIVEN: Existing files of zero, one, and several bytes, plus a missing file
    WHEN: The downloader chooses resume headers
    THEN: It resumes only non-empty files and resets the offset when resume is disabled or unavailable
    """
    file_path = tmp_path / "existing.bin"
    for size in (0, 1, 12):
        file_path.write_bytes(b"x" * size)
        headers = {"Range": f"bytes={size}-"} if size else {}
        assert _existing_size_and_headers(str(file_path), resume=True) == (size, headers)

    assert _existing_size_and_headers(str(file_path), resume=False) == (0, {})
    assert _existing_size_and_headers(str(tmp_path / "missing.bin"), resume=True) == (0, {})


def test_write_response_tracks_chunks_and_reports_progress(tmp_path) -> None:
    """
    Response chunks append to the partial file and progress counts the complete download.

    GIVEN: A partial file and a response containing multiple chunks including an empty chunk
    WHEN: The response writer appends the body
    THEN: It requests bounded chunks, writes all bytes, returns the full size, and reports cumulative progress
    """
    file_path = tmp_path / "download.bin"
    file_path.write_bytes(b"zz")
    chunk_sizes = []
    progress = []
    response = DummyResponse([b"ab", b"", b"cd"], {})

    def _iter_bytes(*, chunk_size: int) -> Iterator[bytes]:
        chunk_sizes.append(chunk_size)
        yield from [b"ab", b"", b"cd"]

    response.iter_bytes = _iter_bytes
    downloaded = _write_response(
        response,
        str(file_path),
        "ab",
        initial_downloaded=2,
        total_size=6,
        progress_callback=lambda percent, message: progress.append((percent, message)),
    )

    assert chunk_sizes == [DOWNLOAD_BLOCK_SIZE]
    assert downloaded == 6
    assert file_path.read_bytes() == b"zzabcd"
    assert [round(percent, 1) for percent, _message in progress] == [66.7, 100.0]
    assert [message for _percent, message in progress] == ["Downloading ... 66.7%", "Downloading ... 100.0%"]


def test_download_success(tmp_path, monkeypatch) -> None:
    data = b"hello world"
    file_path = tmp_path / "out.bin"

    def _get(*_args: object, **kwargs: object) -> DummyResponse:
        assert kwargs["timeout"] == 30
        return DummyResponse([data], {"content-length": str(len(data))}, 200)

    monkeypatch.setattr("ardupilot_methodic_configurator.backend_internet.httpx2_stream", _get)

    ok = download_file_from_url("https://example.com/file", str(file_path))
    assert ok is True
    assert file_path.read_bytes() == data


def test_download_resume_with_existing_file(tmp_path, monkeypatch) -> None:
    full = b"abcdefghijklmnopqrstuvwxyz"
    existing = full[:10]
    remaining = full[10:]

    file_path = tmp_path / "resume.bin"
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_bytes(existing)

    # Response must indicate total size via Content-Range or content-length
    headers = {"Content-Range": f"bytes {len(existing)}-{len(full) - 1}/{len(full)}"}

    def _get(*_args: object, **_kwargs: object) -> DummyResponse:
        # Ensure the caller set a Range header when resuming
        headers_arg = _kwargs.get("headers", {})
        assert isinstance(headers_arg, dict)
        assert "Range" in headers_arg
        return DummyResponse([remaining], headers, 206)

    monkeypatch.setattr("ardupilot_methodic_configurator.backend_internet.httpx2_stream", _get)
    progress = []

    ok = download_file_from_url(
        "https://example.com/large",
        str(file_path),
        progress_callback=lambda percent, message: progress.append((percent, message)),
    )
    assert ok is True
    assert file_path.read_bytes() == full
    assert progress[0][0] == 100.0


def test_server_ignoring_range_replaces_the_partial_file(tmp_path, monkeypatch) -> None:
    """A full HTTP 200 response must replace partial data when a server ignores Range."""
    full = b"complete installer payload"
    file_path = tmp_path / "range-ignored.bin"
    file_path.write_bytes(b"old partial data")

    def _get(*_args: object, **kwargs: object) -> DummyResponse:
        headers_arg = kwargs.get("headers", {})
        assert isinstance(headers_arg, dict)
        assert headers_arg.get("Range") == f"bytes={len(b'old partial data')}-"
        return DummyResponse([full], {"content-length": str(len(full))}, 200)

    monkeypatch.setattr("ardupilot_methodic_configurator.backend_internet.httpx2_stream", _get)

    assert download_file_from_url("https://example.com/installer", str(file_path))
    assert file_path.read_bytes() == full


def test_one_byte_partial_download_succeeds_and_bad_range_starts_at_zero(tmp_path, monkeypatch) -> None:
    """
    A one-byte response succeeds even when the resume offset header is malformed.

    GIVEN: A partial response, malformed Range offset, and one response byte
    WHEN: A single download attempt writes the response
    THEN: It treats the invalid offset as zero and accepts the non-empty result
    """
    file_path = tmp_path / "one-byte.bin"
    progress = []

    def _get(*_args: object, **_kwargs: object) -> DummyResponse:
        return DummyResponse([b"x"], {"Content-Range": "bytes 0-0/1"}, 206)

    monkeypatch.setattr("ardupilot_methodic_configurator.backend_internet.httpx2_stream", _get)
    ok = _attempt_download_once(
        "https://example.com/one-byte",
        str(file_path),
        30,
        {"Range": "bytes=invalid-"},
        lambda percent, message: progress.append((percent, message)),
    )

    assert ok is True
    assert file_path.read_bytes() == b"x"
    assert progress[0][0] == 100.0


def test_timeout_retries_use_exponential_jitter_and_report_attempts(tmp_path, monkeypatch, caplog) -> None:
    """
    Transient timeouts retry with increasing backoff and accurate attempt reporting.

    GIVEN: A download that times out on every attempt and deterministic jitter
    WHEN: The downloader exhausts two retries
    THEN: It makes three attempts, sleeps with exponential delays, and logs accurate attempt counts
    """
    file_path = tmp_path / "timeout.bin"
    attempts = []
    delays = []
    jitter_bounds = []

    def _timeout(*_args: object, **_kwargs: object) -> None:
        attempts.append(1)
        err_msg = "transient timeout"
        raise ReadTimeout(err_msg)

    monkeypatch.setattr("ardupilot_methodic_configurator.backend_internet.httpx2_stream", _timeout)
    monkeypatch.setattr("ardupilot_methodic_configurator.backend_internet.time.sleep", delays.append)
    monkeypatch.setattr(
        "ardupilot_methodic_configurator.backend_internet.random.uniform",
        lambda low, high: jitter_bounds.append((low, high)) or 0.8,
    )

    assert not download_file_from_url("https://example.com/timeout", str(file_path), retries=2, backoff_factor=0.5)

    assert len(attempts) == 3
    assert delays == [0.4, 0.8]
    assert jitter_bounds == [(0.8, 1.2), (0.8, 1.2)]
    assert "Download timed out (attempt 1)" in caplog.text
    assert "Download timed out (attempt 2)" in caplog.text
    assert [record.getMessage() for record in caplog.records[:3]] == [
        "Download timed out (attempt 1)",
        "Download timed out (attempt 2)",
        "Download timed out (attempt 3)",
    ]
    assert caplog.records[-1].getMessage() == "Download failed after 3 attempts, cleaning up partial file"


def test_filesystem_failures_are_logged_and_retried(tmp_path, monkeypatch, caplog) -> None:
    """
    Transient filesystem failures are reported and retried within the configured budget.

    GIVEN: A download operation that raises an operating-system error on every attempt
    WHEN: One retry is allowed
    THEN: The downloader makes two attempts and logs each filesystem error with its cause
    """
    file_path = tmp_path / "filesystem-error.bin"
    attempts = []
    delays = []

    def _fail_stream(*_args: object, **_kwargs: object) -> None:
        attempts.append(1)
        err_msg = "disk unavailable"
        raise OSError(err_msg)

    monkeypatch.setattr("ardupilot_methodic_configurator.backend_internet.httpx2_stream", _fail_stream)
    monkeypatch.setattr("ardupilot_methodic_configurator.backend_internet.time.sleep", delays.append)

    assert not download_file_from_url("https://example.com/filesystem", str(file_path), retries=1, backoff_factor=0)

    assert len(attempts) == 2
    assert delays == [0.0]
    assert [record.getMessage() for record in caplog.records[:2]] == [
        "File system error during download (attempt 1): disk unavailable",
        "File system error during download (attempt 2): disk unavailable",
    ]


def test_retry_cleanup_failure_does_not_escape(tmp_path, monkeypatch) -> None:
    """
    A cleanup permission failure does not replace the exhausted-download result.

    GIVEN: A partial download, repeated transient network errors, and blocked cleanup
    WHEN: The retry budget is exhausted
    THEN: The downloader returns False after one cleanup attempt
    """
    file_path = tmp_path / "partial.bin"
    file_path.write_bytes(b"partial")
    attempts = []
    remove_paths = []

    def _fail_stream(*_args: object, **_kwargs: object) -> None:
        attempts.append(1)
        err_msg = "transient"
        raise ConnectError(err_msg)

    def _fail_remove(path: str) -> None:
        remove_paths.append(path)
        err_msg = "file is locked"
        raise PermissionError(err_msg)

    monkeypatch.setattr("ardupilot_methodic_configurator.backend_internet.httpx2_stream", _fail_stream)
    monkeypatch.setattr("ardupilot_methodic_configurator.backend_internet.time.sleep", lambda _delay: None)
    monkeypatch.setattr("ardupilot_methodic_configurator.backend_internet.os.remove", _fail_remove)

    assert not download_file_from_url("https://example.com/retry", str(file_path), retries=1, backoff_factor=0)
    assert len(attempts) == 2
    assert remove_paths == [str(file_path)]
    assert file_path.exists()


def test_download_stops_after_default_transient_retry_budget(tmp_path, monkeypatch) -> None:
    """
    Repeated network failures stop after the default retry budget and remove partial data.

    GIVEN: An existing partial download and a server that always drops the connection
    WHEN: The download uses its default retry settings
    THEN: It makes four total attempts and removes the incomplete file
    """
    file_path = tmp_path / "retry.bin"
    file_path.write_bytes(b"partial")
    attempts = []

    def _get(*_args: object, **kwargs: object) -> DummyResponse:
        assert kwargs["timeout"] == 30
        attempts.append(1)
        err_msg = "transient"
        raise ConnectError(err_msg)

    monkeypatch.setattr("ardupilot_methodic_configurator.backend_internet.httpx2_stream", _get)
    monkeypatch.setattr("ardupilot_methodic_configurator.backend_internet.time.sleep", lambda _delay: None)

    assert download_file_from_url("https://example.com/retry", str(file_path), backoff_factor=0) is False
    assert len(attempts) == 4
    assert not file_path.exists()


def test_download_stops_after_default_transient_retry_budget(tmp_path, monkeypatch) -> None:
    """
    Repeated network failures stop after the default retry budget and remove partial data.

    GIVEN: An existing partial download and a server that always drops the connection
    WHEN: The download uses its default retry settings
    THEN: It makes four total attempts and removes the incomplete file
    """
    file_path = tmp_path / "retry.bin"
    file_path.write_bytes(b"partial")
    attempts = []

    def _get(*_args: object, **kwargs: object) -> DummyResponse:
        assert kwargs["timeout"] == 30
        attempts.append(1)
        raise ConnectError("transient")

    monkeypatch.setattr("ardupilot_methodic_configurator.backend_internet.httpx2_stream", _get)
    monkeypatch.setattr("ardupilot_methodic_configurator.backend_internet.time.sleep", lambda _delay: None)

    assert download_file_from_url("https://example.com/retry", str(file_path), backoff_factor=0) is False
    assert len(attempts) == 4
    assert not file_path.exists()


def test_download_retries_on_transient_errors(tmp_path, monkeypatch) -> None:
    data = b"finaldata"
    file_path = tmp_path / "retry.bin"

    calls = {"n": 0}

    def _get(*_args: object, **_kwargs: object) -> DummyResponse:
        calls["n"] += 1
        # First two attempts raise, third returns data
        if calls["n"] < 3:
            err_msg = "transient"
            err = ConnectError(err_msg)
            raise err
        return DummyResponse([data], {"content-length": str(len(data))}, 200)

    monkeypatch.setattr("ardupilot_methodic_configurator.backend_internet.httpx2_stream", _get)

    ok = download_file_from_url("https://example.com/retry", str(file_path), retries=3, backoff_factor=0.01)
    assert ok is True
    assert file_path.read_bytes() == data
    assert calls["n"] >= 3
