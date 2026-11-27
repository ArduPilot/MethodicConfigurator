#!/usr/bin/env python3

"""
Unit tests for the backend_internet.py file.

These tests focus on implementation details, edge cases, and error handling.
For behavior-driven tests of software update functionality, see bdd_software_update.py.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import hashlib
import os
import sys
from collections.abc import Generator
import os
from pathlib import Path
from typing import Any
from unittest.mock import ANY, Mock, patch

import pytest
from httpx2 import ConnectError as httpx2_ConnectError
from httpx2 import Headers
from httpx2 import HTTPError as httpx2_HTTPError
from httpx2 import HTTPStatusError as httpx2_HTTPStatusError
from httpx2 import ReadTimeout as httpx2_ReadTimeout

from ardupilot_methodic_configurator.backend_internet import (
    PE_MAGIC_BYTES,
    DOWNLOAD_BLOCK_SIZE,
    _compute_sha256,
    _create_installer_batch_file,
    _get_github_api_headers,
    _install_app_from_mount,
    _mount_dmg,
    _parse_total_size,
    _unmount_dmg,
    _validate_download_file,
    _validate_github_url,
    _verify_installer_integrity,
    download_and_install_on_macos,
    download_and_install_on_windows,
    download_and_install_pip_release,
    download_file_from_url,
    get_expected_sha256_from_release,
    get_release_info,
    verify_and_open_url,
)

# pylint: disable=unused-argument, redefined-outer-name


def test_installer_integrity_accepts_a_matching_sha256(tmp_path: Path) -> None:
    """A downloaded installer is accepted when its SHA-256 matches the trusted digest."""
    payload = b"trusted installer content"
    installer = tmp_path / "installer.bin"
    installer.write_bytes(payload)
    expected = hashlib.sha256(payload).hexdigest()

    assert _verify_installer_integrity(str(installer), expected)
    assert installer.read_bytes() == payload


def test_installer_integrity_rejects_a_mismatch_and_deletes_the_file(tmp_path: Path) -> None:
    """A checksum mismatch rejects and removes the downloaded installer."""
    installer = tmp_path / "installer.bin"
    installer.write_bytes(b"untrusted installer content")

    assert not _verify_installer_integrity(str(installer), "0" * 64)
    assert not installer.exists()


def test_installer_integrity_allows_a_missing_expected_digest(tmp_path: Path) -> None:
    """When release metadata has no digest, verification preserves the documented fallback."""
    missing_installer = tmp_path / "not-downloaded.bin"

    assert _verify_installer_integrity(str(missing_installer), None)


def test_windows_installer_reports_failure_when_temporary_storage_is_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    """A Windows update must report failure when it cannot create temporary storage."""
    monkeypatch.setattr(
        "ardupilot_methodic_configurator.backend_internet.tempfile.TemporaryDirectory",
        Mock(side_effect=OSError("temporary storage unavailable")),
    )

    assert not download_and_install_on_windows(
        "https://github.com/ArduPilot/MethodicConfigurator/releases/download/v1/setup.exe", "setup.exe"
    )


def test_macos_installer_reports_failure_when_temporary_storage_is_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    """A macOS update must report failure when it cannot create temporary storage."""
    monkeypatch.setattr(
        "ardupilot_methodic_configurator.backend_internet.tempfile.TemporaryDirectory",
        Mock(side_effect=OSError("temporary storage unavailable")),
    )

    assert not download_and_install_on_macos(
        "https://github.com/ArduPilot/MethodicConfigurator/releases/download/v1/app.dmg", "app.dmg"
    )


def test_installer_batch_file_quotes_installer_path_and_self_deletes(tmp_path: Path) -> None:
    """The delayed Windows installer script checks and launches its exact path."""
    installer_path = tmp_path / "installer with spaces.exe"

    batch_path = _create_installer_batch_file(str(tmp_path), str(installer_path))

    assert batch_path == str(tmp_path / "run_installer.bat")
    assert Path(batch_path).read_text(encoding="utf-8") == (
        "@echo off\n"
        "ping 127.0.0.1 -n 2 > nul\n"
        f'if exist "{installer_path}" (\n'
        f'  start "" "{installer_path}"\n'
        ") else (\n"
        "  echo Installer not found\n"
        ")\n"
        "del %0\n"
    )


def test_compute_sha256_reads_the_entire_file_in_chunks(tmp_path) -> None:
    """
    Installer verification hashes every byte across multiple read chunks.

    GIVEN: A file larger than two download blocks
    WHEN: Its SHA-256 digest is computed
    THEN: The digest matches the complete file contents
    """
    payload_size = DOWNLOAD_BLOCK_SIZE * 2 + 17
    payload = (bytes(range(256)) * ((payload_size + 255) // 256))[:payload_size]
    file_path = tmp_path / "installer.bin"
    file_path.write_bytes(payload)
    read_sizes = []
    real_open = open

    class RecordingFile:
        """Record requested read sizes while delegating to the real file."""

        def __init__(self, file_handle) -> None:
            self.file_handle = file_handle

        def __enter__(self) -> object:
            return self

        def __exit__(self, *_args) -> None:
            self.file_handle.close()

        def read(self, size: int = -1) -> bytes:
            read_sizes.append(size)
            return self.file_handle.read(size)

    with patch("builtins.open", side_effect=lambda path, mode: RecordingFile(real_open(path, mode))):
        digest = _compute_sha256(str(file_path))

    assert digest == hashlib.sha256(payload).hexdigest()
    assert read_sizes == [DOWNLOAD_BLOCK_SIZE] * 4


def test_github_api_headers_use_optional_bearer_token(monkeypatch) -> None:
    """
    Release API requests use the configured token and omit authorization when it is unavailable.

    GIVEN: The GitHub token is unset, empty, or populated
    WHEN: API request headers are created
    THEN: Only a populated token produces a Bearer authorization header
    """
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    assert _get_github_api_headers() == {}

    monkeypatch.setenv("GITHUB_TOKEN", "")
    assert _get_github_api_headers() == {}

    monkeypatch.setenv("GITHUB_TOKEN", "test-token")
    assert _get_github_api_headers() == {"Authorization": "Bearer test-token"}


def test_download_file_from_url_empty_params(caplog) -> None:
    with patch("ardupilot_methodic_configurator.backend_internet.httpx2_stream") as stream:
        assert not download_file_from_url("", "")
        assert not download_file_from_url("http://test.com", "")
        assert not download_file_from_url("", "test.txt")
    stream.assert_not_called()
    assert [record.getMessage() for record in caplog.records] == [
        "URL or local filename not provided.",
        "URL or local filename not provided.",
        "URL or local filename not provided.",
    ]


@patch("ardupilot_methodic_configurator.backend_internet.httpx2_stream")
def test_download_file_success(mock_get, tmp_path) -> None:
    # Setup mock response
    mock_response = Mock()
    mock_response.headers = {"content-length": "100"}
    mock_response.iter_bytes.return_value = [b"test data"]
    mock_response.raise_for_status.return_value = None
    mock_get.return_value.__enter__.return_value = mock_response

    test_file = tmp_path / "test.txt"
    assert download_file_from_url("http://test.com", str(test_file))
    assert test_file.read_bytes() == b"test data"


@patch("ardupilot_methodic_configurator.backend_internet.httpx2_stream")
def test_download_file_invalid_content_length(mock_get) -> None:
    # Test handling of invalid content-length header
    mock_response = Mock()
    mock_response.headers = {"content-length": "invalid"}
    mock_response.iter_bytes.return_value = [b"test data"]
    mock_get.return_value.__enter__.return_value = mock_response
    assert not download_file_from_url("http://test.com", "test.txt")


@patch("ardupilot_methodic_configurator.backend_internet.httpx2_stream")
def test_download_file_missing_content_length(mock_get) -> None:
    # Test handling of missing content-length header
    mock_response = Mock()
    mock_response.headers = {}
    mock_response.iter_bytes.return_value = [b"test data"]
    mock_get.return_value.__enter__.return_value = mock_response
    assert download_file_from_url("http://test.com", "test.txt")


@patch("ardupilot_methodic_configurator.backend_internet.httpx2_stream")
def test_download_file_empty_response(mock_get) -> None:
    # Test handling of empty response
    mock_response = Mock()
    mock_response.headers = {"content-length": "0"}
    mock_response.iter_bytes.return_value = []
    mock_get.return_value.__enter__.return_value = mock_response
    assert not download_file_from_url("http://test.com", "test.txt")


@patch("ardupilot_methodic_configurator.backend_internet.httpx2_stream")
def test_download_file_http_error(mock_get, caplog) -> None:
    # Test HTTP error handling
    mock_response = Mock()
    mock_response.raise_for_status.side_effect = httpx2_HTTPStatusError("404 Not Found", request=Mock(), response=Mock())
    mock_get.return_value.__enter__.return_value = mock_response
    assert not download_file_from_url("http://test.com", "test.txt", retries=0)
    assert caplog.records[0].getMessage().startswith("Network error during download (attempt 1):")


@patch("ardupilot_methodic_configurator.backend_internet.httpx2_stream")
def test_download_file_with_progress_no_content_length(mock_get, tmp_path) -> None:
    # Test progress callback without content-length header
    mock_response = Mock()
    mock_response.headers = {}
    mock_response.iter_bytes.return_value = [b"data"] * 4
    mock_response.raise_for_status.return_value = None
    mock_get.return_value.__enter__.return_value = mock_response

    progress_callback = Mock()
    test_file = tmp_path / "test.txt"

    assert download_file_from_url("http://test.com", str(test_file), progress_callback=progress_callback)
    assert progress_callback.call_count == 1  # Only final callback
    progress_callback.assert_called_with(100.0, "Download complete")


@patch("ardupilot_methodic_configurator.backend_internet.httpx2_stream")
def test_download_file_asks_httpx2_to_follow_redirects(mock_get, tmp_path) -> None:
    mock_response = Mock()
    mock_response.headers = {"content-length": "100"}
    mock_response.iter_bytes.return_value = [b"test data"]
    mock_get.return_value.__enter__.return_value = mock_response

    assert download_file_from_url("http://test.com", str(tmp_path / "test.txt"), timeout=3, allow_resume=False)
    mock_get.assert_called_once_with("GET", "http://test.com", headers={}, timeout=3, follow_redirects=True)


@patch("ardupilot_methodic_configurator.backend_internet.httpx2_stream")
def test_download_file_value_error(mock_get, tmp_path, caplog, monkeypatch) -> None:
    # Test handling of ValueError during download
    mock_response = Mock()
    mock_response.headers = {"content-length": "100"}
    mock_response.raise_for_status.return_value = None
    mock_response.iter_bytes.side_effect = ValueError("Invalid data")
    mock_get.return_value.__enter__.return_value = mock_response
    file_path = tmp_path / "invalid.bin"
    file_path.write_bytes(b"partial")
    removed_paths = []

    def _remove(path: str) -> None:
        removed_paths.append(path)
        err_msg = "download is locked"
        raise PermissionError(err_msg)

    monkeypatch.setattr("ardupilot_methodic_configurator.backend_internet.os.remove", _remove)
    assert not download_file_from_url("http://test.com", str(file_path), retries=0)
    assert removed_paths == [str(file_path)]
    assert file_path.exists()
    assert caplog.records[0].getMessage() == "Invalid data received from http://test.com: Invalid data"


def test_download_file_from_url_invalid_url() -> None:
    # Test with invalid URL format
    assert not download_file_from_url("not_a_valid_url", "test.txt")


@patch("ardupilot_methodic_configurator.backend_internet.time.sleep")
def test_download_file_fails_without_retrying_when_url_is_malformed(mock_sleep, tmp_path, caplog) -> None:
    """A URL that cannot be parsed is reported as a failed download and is not retried."""
    url = "http://bad\x00host.com/file"
    assert not download_file_from_url(url, str(tmp_path / "file"))
    mock_sleep.assert_not_called()
    assert caplog.records[0].getMessage().startswith(f"Failed to access URL: {url}. Error:")
    assert caplog.records[0].getMessage() != f"Failed to access URL: {url}. Error: None"


@patch("ardupilot_methodic_configurator.backend_internet.httpx2_stream")
def test_download_file_unicode_error(mock_get) -> None:
    # Test handling of Unicode decode errors
    mock_response = Mock()
    mock_response.headers = {"content-length": "100"}
    mock_response.iter_bytes.return_value = [bytes([0xFF, 0xFE, 0xFD])]  # Invalid UTF-8
    mock_get.return_value.__enter__.return_value = mock_response
    assert download_file_from_url("http://test.com", "test.txt")


@patch("ardupilot_methodic_configurator.backend_internet.httpx2_get")
def test_get_release_info_invalid_release(mock_get) -> None:
    mock_get.side_effect = httpx2_ConnectError("Connection failed")
    with pytest.raises(httpx2_HTTPError):
        get_release_info("latest", should_be_pre_release=False)


@patch("ardupilot_methodic_configurator.backend_internet.httpx2_get")
def test_get_release_info_accepts_expected_prerelease(mock_get, caplog) -> None:
    mock_response = Mock()
    mock_response.json.return_value = {"prerelease": True}
    mock_get.return_value = mock_response

    result = get_release_info("latest", should_be_pre_release=True)

    assert result["prerelease"]
    assert not caplog.records


@patch("ardupilot_methodic_configurator.backend_internet.download_file_from_url")
def test_download_and_install_windows_download_failure(mock_download) -> None:
    mock_download.return_value = False
    assert not download_and_install_on_windows("http://test.com", "test.exe")


@patch("shutil.which", return_value=None)  # No uv available, use pip
@patch("subprocess.check_call")
def test_download_and_install_pip_release(mock_check_call, mock_which) -> None:
    mock_check_call.return_value = 0
    assert download_and_install_pip_release() == 0
    mock_which.assert_called_once_with("uv")

    assert mock_check_call.call_args.args[0] == [
        sys.executable,
        "-m",
        "pip",
        "install",
        "--upgrade",
        "--index-url",
        "https://pypi.org/simple",
        "ardupilot_methodic_configurator",
    ]


@patch("shutil.which", return_value="/usr/bin/uv")
@patch("subprocess.check_call", return_value=0)
def test_pip_release_reports_started_and_completed_progress(mock_check_call, mock_which) -> None:
    """
    Installation progress begins at zero and reaches completion after success.

    GIVEN: A successful package installation and a progress callback
    WHEN: The update installer runs
    THEN: The callback receives numeric start and completion values with status text
    """
    updates: list[tuple[float, str]] = []

    result = download_and_install_pip_release(lambda current, message: updates.append((current, message)))

    assert result == 0
    assert updates == [(0.0, "Starting installation..."), (100.0, "Download complete")]
    mock_which.assert_called_once_with("uv")
    mock_check_call.assert_called_once()


@patch("shutil.which", return_value="/usr/bin/uv")  # uv is available
@patch("subprocess.check_call")
def test_download_and_install_pip_release_with_uv(mock_check_call, mock_which) -> None:
    mock_check_call.return_value = 0
    assert download_and_install_pip_release() == 0
    mock_which.assert_called_once_with("uv")

    assert mock_check_call.call_args.args[0] == [
        "/usr/bin/uv",
        "pip",
        "install",
        "--upgrade",
        "--index-url",
        "https://pypi.org/simple",
        "ardupilot_methodic_configurator",
    ]


def test_windows_installer_is_downloaded_validated_and_handed_off_safely() -> None:
    """
    A trusted Windows installer is downloaded to a temporary path and validated before launch.

    GIVEN: A trusted GitHub release URL, checksum, and progress callback
    WHEN: The Windows update installer is prepared
    THEN: The installer is downloaded with the large-file timeout, checksum and PE signature are checked,
      AND: The verified temporary file is handed to the post-exit installer launcher
    """
    url = "https://github.com/ArduPilot/MethodicConfigurator/releases/download/v2/setup.exe"
    expected_sha256 = "a" * 64
    progress = Mock()
    batch_path = "run_installer.bat"

    with (
        patch("ardupilot_methodic_configurator.backend_internet.download_file_from_url", return_value=True) as download,
        patch("ardupilot_methodic_configurator.backend_internet._verify_installer_integrity", return_value=True) as verify,
        patch("ardupilot_methodic_configurator.backend_internet._validate_download_file", return_value=True) as validate,
        patch(
            "ardupilot_methodic_configurator.backend_internet._create_installer_batch_file", return_value=batch_path
        ) as create_batch,
        patch("ardupilot_methodic_configurator.backend_internet._launch_installer_and_exit") as launch,
    ):
        download_and_install_on_windows(url, "setup.exe", progress_callback=progress, expected_sha256=expected_sha256)

    downloaded_url, installer_path = download.call_args.args
    assert downloaded_url == url
    assert os.path.isabs(installer_path)
    assert installer_path.endswith("setup.exe")
    assert download.call_args.kwargs == {"timeout": 60, "progress_callback": progress}
    verify.assert_called_once_with(installer_path, expected_sha256)
    validate.assert_called_once_with(
        installer_path,
        magic_bytes=PE_MAGIC_BYTES,
        magic_error_msg=ANY,
    )
    assert "Windows executable" in validate.call_args.kwargs["magic_error_msg"]
    create_batch.assert_called_once_with(os.path.dirname(installer_path), installer_path)
    launch.assert_called_once_with(batch_path, progress)
    first_progress = progress.call_args_list[0].args
    assert first_progress[0] == 0.0
    assert isinstance(first_progress[1], str)


@pytest.mark.parametrize("failed_step", ["download", "integrity", "validation"])
def test_windows_installer_fails_closed_before_handoff_on_preflight_failure(failed_step: str) -> None:
    """
    An installer is never handed off when its download or validation stage fails.

    GIVEN: A trusted GitHub release and a failure in one preflight stage
    WHEN: The Windows update installer is prepared
    THEN: The workflow returns False and skips the batch launcher
    """
    url = "https://github.com/ArduPilot/MethodicConfigurator/releases/download/v2/setup.exe"
    download_ok = failed_step != "download"
    integrity_ok = failed_step != "integrity"
    validation_ok = failed_step != "validation"

    with (
        patch("ardupilot_methodic_configurator.backend_internet.download_file_from_url", return_value=download_ok),
        patch(
            "ardupilot_methodic_configurator.backend_internet._verify_installer_integrity",
            return_value=integrity_ok,
        ) as verify,
        patch(
            "ardupilot_methodic_configurator.backend_internet._validate_download_file",
            return_value=validation_ok,
        ) as validate,
        patch("ardupilot_methodic_configurator.backend_internet._create_installer_batch_file") as create_batch,
        patch("ardupilot_methodic_configurator.backend_internet._launch_installer_and_exit") as launch,
    ):
        result = download_and_install_on_windows(url, "setup.exe", expected_sha256="a" * 64)

    assert result is False
    create_batch.assert_not_called()
    launch.assert_not_called()
    if failed_step == "download":
        verify.assert_not_called()
        validate.assert_not_called()
    elif failed_step == "integrity":
        validate.assert_not_called()


def test_windows_installer_is_downloaded_validated_and_handed_off_safely() -> None:
    """
    A trusted Windows installer is downloaded to a temporary path and validated before launch.

    GIVEN: A trusted GitHub release URL, checksum, and progress callback
    WHEN: The Windows update installer is prepared
    THEN: The installer is downloaded with the large-file timeout, checksum and PE signature are checked,
      AND: The verified temporary file is handed to the post-exit installer launcher
    """
    url = "https://github.com/ArduPilot/MethodicConfigurator/releases/download/v2/setup.exe"
    expected_sha256 = "a" * 64
    progress = Mock()
    batch_path = "/tmp/run_installer.bat"

    with (
        patch("ardupilot_methodic_configurator.backend_internet.download_file_from_url", return_value=True) as download,
        patch("ardupilot_methodic_configurator.backend_internet._verify_installer_integrity", return_value=True) as verify,
        patch("ardupilot_methodic_configurator.backend_internet._validate_download_file", return_value=True) as validate,
        patch(
            "ardupilot_methodic_configurator.backend_internet._create_installer_batch_file", return_value=batch_path
        ) as create_batch,
        patch("ardupilot_methodic_configurator.backend_internet._launch_installer_and_exit") as launch,
    ):
        download_and_install_on_windows(url, "setup.exe", progress_callback=progress, expected_sha256=expected_sha256)

    downloaded_url, installer_path = download.call_args.args
    assert downloaded_url == url
    assert os.path.isabs(installer_path)
    assert installer_path.endswith("setup.exe")
    assert download.call_args.kwargs == {"timeout": 60, "progress_callback": progress}
    verify.assert_called_once_with(installer_path, expected_sha256)
    validate.assert_called_once_with(
        installer_path,
        magic_bytes=PE_MAGIC_BYTES,
        magic_error_msg=ANY,
    )
    assert "Windows executable" in validate.call_args.kwargs["magic_error_msg"]
    create_batch.assert_called_once_with(os.path.dirname(installer_path), installer_path)
    launch.assert_called_once_with(batch_path, progress)


# ---------------------------------------------------------------------------
# Tests for shared validation helpers
# ---------------------------------------------------------------------------


GITHUB_DOWNLOAD_URL = "https://github.com/ArduPilot/MethodicConfigurator/releases/download/v1/app.dmg"
DMG_FILE_NAME = "app.dmg"


class TestValidateGithubUrl:
    """Tests for the _validate_github_url helper."""

    @pytest.mark.parametrize(
        "url",
        [
            "https://github.com/ArduPilot/MethodicConfigurator/releases/download/v1/file.exe",
            "https://github.com/ArduPilot/MethodicConfigurator/releases/download/v2/app.dmg",
            "HTTPS://github.com/ArduPilot/MethodicConfigurator/releases/download/v0.1/whl.whl",
            "  https://github.com/ArduPilot/MethodicConfigurator/releases/download/v1/x.exe  ",
        ],
    )
    def test_accepts_valid_github_https_urls(self, url: str) -> None:
        assert _validate_github_url(url)

    @pytest.mark.parametrize(
        "url",
        [
            "https://example.com/installer.exe",  # wrong domain
            "http://github.com/ArduPilot/MethodicConfigurator/releases/download/v1/x.exe",  # HTTP, not HTTPS
            "https://evil.com/github.com/ArduPilot/MethodicConfigurator/releases/download/v1/x.exe",  # github.com in path
            "ftp://github.com/ArduPilot/MethodicConfigurator/releases/download/v1/x.exe",  # wrong scheme
            "https://github.com/user/repo/releases/download/v0.1/whl.whl",  # wrong owner/repo
            "https://github.com/ArduPilot/MethodicConfigurator/",  # no releases/download prefix
            "",  # empty
        ],
    )
    def test_rejects_invalid_urls(self, url: str) -> None:
        assert not _validate_github_url(url)

    def test_logs_error_for_rejected_url(self, caplog) -> None:
        _validate_github_url("https://evil.com/bad.exe")
        assert "https://evil.com/bad.exe" in caplog.text  # the rejected URL must appear verbatim in the log


class TestExpectedSha256FromRelease:
    """Tests for obtaining an installer checksum from GitHub release data."""

    def test_prefers_asset_digest_without_fetching_checksum_file(self, monkeypatch) -> None:
        """
        The release asset's GitHub-computed digest is used directly.

        GIVEN: A matching release asset with a sha256 digest
        WHEN: The expected installer digest is requested
        THEN: The digest is returned without making an extra request
        """
        digest = "a" * 64
        release_info = {"assets": [{"name": "setup.exe", "digest": f"sha256:{digest}"}]}
        monkeypatch.setattr("ardupilot_methodic_configurator.backend_internet.httpx2_get", Mock())

        assert get_expected_sha256_from_release(release_info, "setup.exe") == digest

    def test_reads_filename_specific_checksum_line(self, monkeypatch) -> None:
        """
        A checksum file returns the hash that belongs to the requested installer.

        GIVEN: A checksum asset containing entries for several files
        WHEN: The requested installer's digest is looked up
        THEN: Its matching filename entry is returned and timeout settings are forwarded
        """
        digest = "A" * 64
        lowercase_digest = "b" * 64
        response = Mock()
        response.text = f"{'c' * 64}  other.exe\n{digest}  setup.exe\n{lowercase_digest}  setup-lower.exe\n"
        response.raise_for_status.return_value = None
        get = Mock(return_value=response)
        monkeypatch.setattr("ardupilot_methodic_configurator.backend_internet.httpx2_get", get)
        release_info = {"assets": [{"name": "SHA256SUMS", "browser_download_url": "https://example.com/SHA256SUMS"}]}

        assert get_expected_sha256_from_release(release_info, "setup.exe", timeout=60) == digest
        assert get_expected_sha256_from_release(release_info, "setup-lower.exe", timeout=60) == lowercase_digest
        assert get.call_count == 2
        assert all(call.kwargs == {"timeout": 60, "follow_redirects": True} for call in get.call_args_list)

    def test_uses_first_hash_when_checksum_file_omits_filename(self, monkeypatch) -> None:
        """
        A checksum file with only a hash still provides a usable fallback digest.

        GIVEN: A checksum asset whose text contains a SHA256 value but no filename
        WHEN: The requested installer's digest is looked up
        THEN: The first 64-character hash is returned
        """
        digest = "E" * 64
        response = Mock()
        response.text = f"unlabelled checksum: {digest}"
        response.raise_for_status.return_value = None
        get = Mock(return_value=response)
        monkeypatch.setattr("ardupilot_methodic_configurator.backend_internet.httpx2_get", get)
        release_info = {
            "assets": [{"name": "release-notes.txt", "browser_download_url": "https://example.com/release-notes.txt"}]
        }

        assert get_expected_sha256_from_release(release_info, "setup.exe") == digest
        get.assert_called_once_with("https://example.com/release-notes.txt", timeout=30, follow_redirects=True)

    def test_recognizes_checksum_named_assets(self, monkeypatch) -> None:
        """A checksum-named asset without a standard extension is still parsed."""
        digest = "f" * 64
        response = Mock()
        response.text = f"{digest}  setup.exe\n"
        response.raise_for_status.return_value = None
        monkeypatch.setattr("ardupilot_methodic_configurator.backend_internet.httpx2_get", Mock(return_value=response))
        release_info = {"assets": [{"name": "checksum.dat", "browser_download_url": "https://example.com/checksum.dat"}]}

        assert get_expected_sha256_from_release(release_info, "setup.exe") == digest

    def test_skips_unavailable_checksum_assets_and_continues(self, monkeypatch) -> None:
        """
        An unavailable checksum asset does not prevent trying the next checksum file.

        GIVEN: One checksum asset without a URL, one whose download errors, and one usable asset
        WHEN: The installer digest is looked up
        THEN: The helper skips unavailable assets and returns the later matching checksum
        """
        digest = "e" * 64
        response = Mock()
        response.text = f"{digest}  setup.exe\n"
        response.raise_for_status.return_value = None
        get = Mock(side_effect=[httpx2_ConnectError("offline"), response])
        monkeypatch.setattr("ardupilot_methodic_configurator.backend_internet.httpx2_get", get)
        release_info = {
            "assets": [
                {},
                {"name": "SHA256SUMS"},
                {"name": "setup.exe.sha256", "browser_download_url": "https://example.com/unavailable"},
                {"name": "checksums.txt", "browser_download_url": "https://example.com/checksums.txt"},
            ]
        }

        assert get_expected_sha256_from_release(release_info, "setup.exe") == digest
        assert get.call_count == 2

    def test_returns_none_when_release_or_filename_is_missing(self) -> None:
        """
        Incomplete lookup input does not trigger a checksum request.

        GIVEN: An empty release or an empty filename
        WHEN: The expected digest is requested
        THEN: No digest is returned
        """
        assert get_expected_sha256_from_release({}, "setup.exe") is None
        assert get_expected_sha256_from_release({"assets": []}, "") is None
        assert get_expected_sha256_from_release({}, "") is None
        assert get_expected_sha256_from_release({"tag_name": "v1.0"}, "setup.exe") is None


class TestParseTotalSize:
    """Tests for total-size parsing from HTTP response headers."""

    def test_uses_content_range_total_for_resumed_download(self) -> None:
        """
        A resumed response reports the complete file size instead of only remaining bytes.

        GIVEN: A range response with a partial content length and the complete range total
        WHEN: The downloader parses the response size
        THEN: It returns the complete total from Content-Range
        """
        response = Mock()
        response.headers = Headers({"Content-Range": "bytes 100-199/1000", "content-length": "100"})
        assert _parse_total_size(response) == 1000

    @pytest.mark.parametrize("content_range", ["bytes 100-199/not-a-number", "bytes 100-199"])
    def test_invalid_content_range_returns_zero(self, content_range: str) -> None:
        """
        A malformed range total is rejected instead of being mistaken for a file size.

        GIVEN: A response with a malformed Content-Range and a content-length fallback
        WHEN: The downloader parses the response size
        THEN: It returns zero because the present range header is invalid
        """
        response = Mock()
        response.headers = Headers({"Content-Range": content_range, "content-length": "4096"})
        assert _parse_total_size(response) == 0

    def test_uses_content_length_when_no_range_header_is_present(self) -> None:
        """
        A non-range response uses its content length as the total file size.

        GIVEN: A response without Content-Range and with a content length
        WHEN: The downloader parses the response size
        THEN: It returns the content-length value
        """
        response = Mock()
        response.headers = Headers({"content-length": "2048"})
        assert _parse_total_size(response) == 2048


class TestValidateDownloadFile:
    """Tests for the _validate_download_file helper."""

    @pytest.mark.parametrize("size", [1024, 2048, 10_000])
    def test_accepts_files_at_or_above_minimum_size(self, tmp_path, size: int) -> None:
        f = tmp_path / "test.bin"
        f.write_bytes(b"X" * size)
        assert _validate_download_file(str(f))

    @pytest.mark.parametrize("size", [0, 512, 1023])
    def test_rejects_files_below_minimum_size(self, tmp_path, size: int, caplog) -> None:
        f = tmp_path / "tiny.bin"
        f.write_bytes(b"X" * size)
        assert not _validate_download_file(str(f))
        assert f"{size} bytes" in caplog.text

    def test_accepts_file_with_correct_magic_bytes(self, tmp_path) -> None:
        f = tmp_path / "test.exe"
        f.write_bytes(b"MZ" + b"X" * 2048)
        assert _validate_download_file(str(f), magic_bytes=b"MZ")

    def test_rejects_file_with_wrong_magic_bytes(self, tmp_path, caplog) -> None:
        f = tmp_path / "bad.exe"
        f.write_bytes(b"PK" + b"X" * 2048)  # ZIP signature instead of PE
        assert not _validate_download_file(str(f), magic_bytes=b"MZ", magic_error_msg="Not a PE file")
        assert caplog.records[-1].getMessage() == "Not a PE file"

    def test_uses_default_error_message_when_none_given(self, tmp_path, caplog) -> None:
        """
        A malformed download reports a useful format error when no custom message is supplied.

        GIVEN: A sufficiently large download with an invalid signature
        WHEN: The download validator checks it without a custom error message
        THEN: The log explains that the downloaded file has an unexpected format
        """
        f = tmp_path / "bad.bin"
        f.write_bytes(b"?!" + b"X" * 2048)
        assert not _validate_download_file(str(f), magic_bytes=b"MZ")
        assert "unexpected format" in caplog.text.lower()

    def test_rejects_nonexistent_file(self, caplog) -> None:
        assert not _validate_download_file("/nonexistent/path/file.dmg")
        assert caplog.text  # error was logged

    def test_cleans_up_too_small_file(self, tmp_path) -> None:
        f = tmp_path / "tiny.bin"
        f.write_bytes(b"X" * 512)
        _validate_download_file(str(f))
        assert not f.exists()

    def test_cleans_up_wrong_magic_bytes_file(self, tmp_path) -> None:
        f = tmp_path / "bad.exe"
        f.write_bytes(b"PK" + b"X" * 2048)
        _validate_download_file(str(f), magic_bytes=b"MZ")
        assert not f.exists()

    @pytest.mark.parametrize(
        ("file_content", "magic_bytes"),
        [(b"X" * 512, None), (b"PK" + b"X" * 2048, b"MZ")],
    )
    def test_cleanup_failure_does_not_escape_validation(self, tmp_path, caplog, file_content, magic_bytes) -> None:
        """
        An invalid download remains a rejected download when cleanup is blocked.

        GIVEN: A download that fails validation and cannot be deleted
        WHEN: The validator attempts cleanup
        THEN: It returns False without raising the cleanup error
        """
        f = tmp_path / "invalid.bin"
        f.write_bytes(file_content)
        with patch(
            "ardupilot_methodic_configurator.backend_internet.os.remove",
            side_effect=PermissionError("cannot delete"),
        ) as remove:
            assert not _validate_download_file(str(f), magic_bytes=magic_bytes)
        remove.assert_called_once_with(str(f))
        assert "Failed to validate downloaded file" not in caplog.text

    @pytest.mark.parametrize("error", [PermissionError("denied"), OSError("unsupported"), NotImplementedError()])
    def test_permission_restriction_failure_does_not_reject_valid_download(self, tmp_path, error) -> None:
        """
        Platforms that cannot change file permissions can still use a valid download.

        GIVEN: A valid sufficiently large download and a platform permission-setting failure
        WHEN: The validator restricts file permissions
        THEN: The download is accepted because permission restriction is best effort
        """
        f = tmp_path / "valid.bin"
        f.write_bytes(b"X" * 2048)
        with patch("ardupilot_methodic_configurator.backend_internet.os.chmod", side_effect=error):
            assert _validate_download_file(str(f))

    def test_valid_download_uses_owner_only_permissions(self, tmp_path) -> None:
        """Downloaded installers are restricted to owner read/write without execute bits."""
        f = tmp_path / "valid.bin"
        f.write_bytes(b"X" * 2048)
        with patch("ardupilot_methodic_configurator.backend_internet.os.chmod") as chmod:
            assert _validate_download_file(str(f))

        chmod.assert_called_once_with(str(f), 0o600)

    def test_validation_os_error_is_logged_and_cleanup_error_is_suppressed(self, tmp_path, caplog) -> None:
        """
        A file access error is logged with context even when cleanup also fails.

        GIVEN: A file whose validation stat fails and whose cleanup is blocked
        WHEN: The validator handles the filesystem error
        THEN: It returns False, logs the cause, and suppresses the cleanup failure
        """
        f = tmp_path / "unreadable.bin"
        with (
            patch("ardupilot_methodic_configurator.backend_internet.os.stat", side_effect=OSError("stat denied")),
            patch("ardupilot_methodic_configurator.backend_internet.os.remove", side_effect=PermissionError("locked")),
        ):
            assert not _validate_download_file(str(f))
        assert "Failed to validate downloaded file" in caplog.text
        assert "stat denied" in caplog.text


# ---------------------------------------------------------------------------
# Tests for macOS DMG installation helpers
# ---------------------------------------------------------------------------


class TestMountDmg:
    """Tests for the _mount_dmg helper."""

    @patch("ardupilot_methodic_configurator.backend_internet.subprocess.run")
    def test_returns_mount_point_on_success(self, mock_run) -> None:
        mock_run.return_value.stdout = "/dev/disk2s1\t\tHFS+\t/Volumes/MyApp\n"
        assert _mount_dmg("/fake/app.dmg") == "/Volumes/MyApp"

    @patch("ardupilot_methodic_configurator.backend_internet.subprocess.run")
    def test_passes_correct_hdiutil_arguments(self, mock_run) -> None:
        mock_run.return_value.stdout = "/dev/disk2\t\t\t/Volumes/App\n"
        _mount_dmg("/fake/app.dmg")
        call_args = mock_run.call_args[0][0]
        assert call_args[0] == "hdiutil"
        assert call_args[1] == "attach"
        assert "/fake/app.dmg" in call_args
        assert "-nobrowse" in call_args
        assert "-noautoopen" in call_args
        assert mock_run.call_args.kwargs == {"capture_output": True, "text": True, "check": True}

    @patch("ardupilot_methodic_configurator.backend_internet.subprocess.run")
    def test_preserves_spaces_in_mounted_volume_name(self, mock_run) -> None:
        """Tab-separated hdiutil output keeps spaces inside the mount point."""
        mock_run.return_value.stdout = "/dev/disk2s1\t\tHFS+\t/Volumes/My Flight App\n"

        assert _mount_dmg("/fake/app.dmg") == "/Volumes/My Flight App"

    @patch("ardupilot_methodic_configurator.backend_internet.subprocess.run")
    def test_returns_none_when_no_volumes_path(self, mock_run, caplog) -> None:
        mock_run.return_value.stdout = "/dev/disk2s1\t\tHFS+\t/mnt/other\n"
        assert _mount_dmg("/fake/app.dmg") is None
        assert "hdiutil" in caplog.text.lower() or "mount" in caplog.text.lower()

    @patch("ardupilot_methodic_configurator.backend_internet.subprocess.run")
    def test_returns_none_on_empty_stdout(self, mock_run) -> None:
        mock_run.return_value.stdout = ""
        assert _mount_dmg("/fake/app.dmg") is None

    @patch(
        "ardupilot_methodic_configurator.backend_internet.subprocess.run",
        side_effect=__import__("subprocess").CalledProcessError(1, "hdiutil"),
    )
    def test_returns_none_and_logs_on_subprocess_error(self, mock_run, caplog) -> None:
        assert _mount_dmg("/fake/app.dmg") is None
        assert caplog.text  # error was logged

    @patch(
        "ardupilot_methodic_configurator.backend_internet.subprocess.run",
        side_effect=OSError("hdiutil not found"),
    )
    def test_returns_none_and_logs_on_os_error(self, mock_run, caplog) -> None:
        assert _mount_dmg("/fake/app.dmg") is None
        assert caplog.text  # error was logged


class TestUnmountDmg:
    """Tests for the _unmount_dmg helper."""

    @patch("ardupilot_methodic_configurator.backend_internet.subprocess.run")
    def test_calls_hdiutil_detach_with_force(self, mock_run) -> None:
        mock_run.return_value = Mock()
        _unmount_dmg("/Volumes/MyApp")
        mock_run.assert_called_once()
        args = mock_run.call_args[0][0]
        assert args[0] == "hdiutil"
        assert args[1] == "detach"
        assert "/Volumes/MyApp" in args
        assert "-force" in args

    @patch(
        "ardupilot_methodic_configurator.backend_internet.subprocess.run",
        side_effect=OSError("detach failed"),
    )
    def test_suppresses_os_error(self, mock_run) -> None:
        _unmount_dmg("/Volumes/MyApp")  # must not raise

    @patch(
        "ardupilot_methodic_configurator.backend_internet.subprocess.run",
        side_effect=__import__("subprocess").CalledProcessError(1, "hdiutil"),
    )
    def test_suppresses_called_process_error(self, mock_run) -> None:
        _unmount_dmg("/Volumes/MyApp")  # must not raise


class TestInstallAppFromMount:
    """Tests for the _install_app_from_mount helper."""

    @patch("ardupilot_methodic_configurator.backend_internet.subprocess.check_call")
    @patch("ardupilot_methodic_configurator.backend_internet.os.listdir")
    def test_installs_first_app_bundle_using_ditto(self, mock_listdir, mock_check_call, tmp_path) -> None:
        """Given a mount point with a .app bundle, it copies it to /Applications via ditto."""
        mock_listdir.return_value = ["MyApp.app", "README.txt"]
        mock_check_call.return_value = 0
        assert _install_app_from_mount(str(tmp_path))
        call_args = mock_check_call.call_args[0][0]
        assert call_args[0] == "ditto"
        # source must be the .app inside the mount point
        assert "MyApp.app" in call_args[1]
        # destination must be /Applications/MyApp.app
        dest = call_args[2]
        assert "Applications" in dest
        assert "MyApp.app" in dest

    @patch("ardupilot_methodic_configurator.backend_internet.subprocess.check_call")
    @patch("ardupilot_methodic_configurator.backend_internet.os.listdir")
    def test_invokes_progress_callbacks_before_and_after(self, mock_listdir, mock_check_call, tmp_path) -> None:
        """Progress callback must be called at the start and on completion."""
        mock_listdir.return_value = ["MyApp.app"]
        mock_check_call.return_value = 0
        progress = Mock()
        _install_app_from_mount(str(tmp_path), progress_callback=progress)
        assert progress.call_count == 2
        first_call_progress = progress.call_args_list[0][0][0]
        last_call_progress = progress.call_args_list[-1][0][0]
        assert first_call_progress == 60.0  # "Installing..." message at 60% of second phase
        assert last_call_progress == 80.0  # "App installed" message at 80% of second phase

    @patch("ardupilot_methodic_configurator.backend_internet.subprocess.check_call")
    @patch("ardupilot_methodic_configurator.backend_internet.os.listdir")
    def test_picks_first_app_when_multiple_present(self, mock_listdir, mock_check_call, tmp_path) -> None:
        mock_listdir.return_value = ["FirstApp.app", "SecondApp.app"]
        mock_check_call.return_value = 0
        _install_app_from_mount(str(tmp_path))
        dest = mock_check_call.call_args[0][0][2]
        assert "FirstApp.app" in dest

    @patch("ardupilot_methodic_configurator.backend_internet.os.listdir")
    def test_returns_false_when_no_app_bundle_found(self, mock_listdir, caplog) -> None:
        mock_listdir.return_value = ["README.txt", "License.txt"]
        assert not _install_app_from_mount("/Volumes/MyApp")
        assert caplog.text  # error was logged

    @patch(
        "ardupilot_methodic_configurator.backend_internet.subprocess.check_call",
        side_effect=__import__("subprocess").CalledProcessError(1, "ditto"),
    )
    @patch("ardupilot_methodic_configurator.backend_internet.os.listdir")
    def test_returns_false_and_logs_on_ditto_failure(self, mock_listdir, mock_check_call, caplog) -> None:
        mock_listdir.return_value = ["MyApp.app"]
        assert not _install_app_from_mount("/Volumes/MyApp")
        assert caplog.text  # error was logged

    @patch(
        "ardupilot_methodic_configurator.backend_internet.os.listdir",
        side_effect=OSError("permission denied"),
    )
    def test_returns_false_on_os_error(self, mock_listdir, caplog) -> None:
        assert not _install_app_from_mount("/Volumes/MyApp")
        assert caplog.text  # error was logged


@pytest.fixture
def macos_happy_path() -> Generator[dict[str, Any], None, None]:
    """
    Fixture that patches all backend helpers so download_and_install_on_macos succeeds end-to-end.

    Tests override individual patches by using the returned dict of mocks.
    """
    with (
        patch("ardupilot_methodic_configurator.backend_internet.download_file_from_url", return_value=True) as dl,
        patch("ardupilot_methodic_configurator.backend_internet._verify_installer_integrity", return_value=True) as sha,
        patch("ardupilot_methodic_configurator.backend_internet._validate_download_file", return_value=True) as vf,
        patch("ardupilot_methodic_configurator.backend_internet._mount_dmg", return_value="/Volumes/App") as mount,
        patch("ardupilot_methodic_configurator.backend_internet._install_app_from_mount", return_value=True) as install,
        patch("ardupilot_methodic_configurator.backend_internet._unmount_dmg") as unmount,
    ):
        yield {"download": dl, "sha256": sha, "validate": vf, "mount": mount, "install": install, "unmount": unmount}


class TestDownloadAndInstallOnMacos:
    """Tests for the download_and_install_on_macos function."""

    def test_rejects_non_github_url(self) -> None:
        assert not download_and_install_on_macos("https://evil.com/app.dmg", DMG_FILE_NAME)

    @patch("ardupilot_methodic_configurator.backend_internet.download_file_from_url", return_value=False)
    def test_returns_false_when_download_fails(self, mock_dl) -> None:
        assert not download_and_install_on_macos(GITHUB_DOWNLOAD_URL, DMG_FILE_NAME)

    def test_full_success_flow(self, macos_happy_path) -> None:
        """Given all steps succeed, passes the temporary artifact through validation and install."""
        progress = Mock()
        assert download_and_install_on_macos(GITHUB_DOWNLOAD_URL, DMG_FILE_NAME, progress_callback=progress)

        macos_happy_path["download"].assert_called_once()
        download_call = macos_happy_path["download"].call_args
        assert download_call.args[0] == GITHUB_DOWNLOAD_URL
        downloaded_path = Path(download_call.args[1])
        assert downloaded_path.name == DMG_FILE_NAME
        assert downloaded_path.parent != Path(".")
        assert download_call.kwargs == {"timeout": 60, "progress_callback": progress}
        macos_happy_path["sha256"].assert_called_once_with(str(downloaded_path), None)
        macos_happy_path["validate"].assert_called_once_with(str(downloaded_path))
        macos_happy_path["mount"].assert_called_once_with(str(downloaded_path))

        progress_events = [call.args for call in progress.call_args_list]
        assert any(event[0] == 0.0 and isinstance(event[1], str) for event in progress_events)
        assert any(event[0] == 20.0 and isinstance(event[1], str) for event in progress_events)
        # Progress must be called with 100% at the end
        final_call = progress.call_args_list[-1]
        assert final_call[0][0] == 100.0

    def test_unmount_is_always_called_even_when_install_fails(self, macos_happy_path) -> None:
        """_unmount_dmg must be called in the finally block regardless of install outcome."""
        macos_happy_path["install"].return_value = False
        download_and_install_on_macos(GITHUB_DOWNLOAD_URL, DMG_FILE_NAME)
        macos_happy_path["unmount"].assert_called_once_with("/Volumes/App")

    def test_unmount_is_called_with_correct_mount_point(self, macos_happy_path) -> None:
        macos_happy_path["mount"].return_value = "/Volumes/SpecificApp"
        download_and_install_on_macos(GITHUB_DOWNLOAD_URL, DMG_FILE_NAME)
        macos_happy_path["unmount"].assert_called_once_with("/Volumes/SpecificApp")

    def test_returns_false_when_install_fails(self, macos_happy_path) -> None:
        macos_happy_path["install"].return_value = False
        assert not download_and_install_on_macos(GITHUB_DOWNLOAD_URL, DMG_FILE_NAME)

    def test_returns_false_and_skips_install_when_mount_fails(self, macos_happy_path) -> None:
        macos_happy_path["mount"].return_value = None
        assert not download_and_install_on_macos(GITHUB_DOWNLOAD_URL, DMG_FILE_NAME)
        macos_happy_path["install"].assert_not_called()

    def test_returns_false_when_file_validation_fails(self, macos_happy_path) -> None:
        macos_happy_path["validate"].return_value = False
        assert not download_and_install_on_macos(GITHUB_DOWNLOAD_URL, DMG_FILE_NAME)
        # Validation failed before mount — mount should not be attempted
        macos_happy_path["mount"].assert_not_called()

    def test_returns_false_when_sha256_mismatch(self, macos_happy_path) -> None:
        macos_happy_path["sha256"].return_value = False
        assert not download_and_install_on_macos(GITHUB_DOWNLOAD_URL, DMG_FILE_NAME, expected_sha256="deadbeef")
        # SHA256 failed before file validation — validate should not be attempted
        macos_happy_path["validate"].assert_not_called()

    def test_passes_expected_sha256_to_integrity_check(self, macos_happy_path) -> None:
        sha = "abc123def456" * 4  # 48-char fake hash
        download_and_install_on_macos(GITHUB_DOWNLOAD_URL, DMG_FILE_NAME, expected_sha256=sha)
        macos_happy_path["sha256"].assert_called_once()
        # Second positional arg is expected_sha256
        assert sha in macos_happy_path["sha256"].call_args[0]


class TestDownloadFile:
    """Tests for the download_file_from_url function."""

    @pytest.fixture
    def mock_response(self) -> Mock:
        response = Mock()
        response.headers = {"content-length": "100"}
        response.iter_bytes.return_value = [b"test data"]
        response.raise_for_status.return_value = None
        return response

    @pytest.fixture
    def mock_get(self) -> Generator[Mock, None, None]:
        with patch("ardupilot_methodic_configurator.backend_internet.httpx2_stream") as _mock:
            yield _mock

    def test_download_file_network_errors(self, mock_get, caplog) -> None:
        errors = [
            httpx2_HTTPStatusError("404 Not Found", request=Mock(), response=Mock()),
            httpx2_ConnectError("Connection failed"),
            ValueError("Invalid response"),
            OSError("File system error"),
        ]

        for error in errors:
            mock_get.side_effect = error
            assert not download_file_from_url("http://test.com", "test.txt")
            assert str(error) in caplog.text
            caplog.clear()

    def test_download_file_progress_tracking(self, mock_get, mock_response, tmp_path) -> None:
        mock_get.return_value.__enter__.return_value = mock_response
        progress_values = []

        def progress_callback(progress: float, msg: str) -> None:
            progress_values.append((progress, msg))

        test_file = tmp_path / "test.txt"
        assert download_file_from_url("http://test.com", str(test_file), progress_callback=progress_callback)

        # Verify progress tracking
        assert len(progress_values) > 0
        assert progress_values[-1][0] == 100.0
        assert "Download complete" in progress_values[-1][1]
        assert test_file.exists()
        assert test_file.read_bytes() == b"test data"

    def test_download_file_filesystem_operations(self, mock_get, mock_response, tmp_path) -> None:
        mock_get.return_value.__enter__.return_value = mock_response
        mock_get.configure(timeout=5)

        # Test directory creation
        nested_path = tmp_path / "deep" / "nested" / "path"
        test_file = nested_path / "test.txt"

        assert download_file_from_url("http://test.com", str(test_file))
        assert test_file.exists()
        assert test_file.read_bytes() == b"test data"

        # Test file overwrite
        assert download_file_from_url("http://test.com", str(test_file))
        assert test_file.exists()


@patch("ardupilot_methodic_configurator.backend_internet.httpx2_stream")
@patch("ardupilot_methodic_configurator.backend_internet.webbrowser_open")
def test_verify_and_open_url_success(mock_webbrowser_open, mock_get) -> None:
    """Test successful URL verification and opening."""
    # Setup mock responses
    mock_response = Mock()
    mock_response.status_code = 200
    mock_get.return_value.__enter__.return_value = mock_response
    mock_webbrowser_open.return_value = True

    # Call function and verify results
    assert verify_and_open_url("https://example.com")
    mock_get.assert_called_once_with("GET", "https://example.com", timeout=5, follow_redirects=True)
    mock_webbrowser_open.assert_called_once_with(url="https://example.com", new=0, autoraise=True)


@patch("ardupilot_methodic_configurator.backend_internet.httpx2_stream")
@patch("ardupilot_methodic_configurator.backend_internet.webbrowser_open")
def test_verify_and_open_url_empty_url(mock_webbrowser_open, mock_get) -> None:
    """Test with empty URL."""
    assert not verify_and_open_url("")
    mock_get.assert_not_called()
    mock_webbrowser_open.assert_not_called()


@patch("ardupilot_methodic_configurator.backend_internet.httpx2_stream")
@patch("ardupilot_methodic_configurator.backend_internet.webbrowser_open")
def test_verify_and_open_url_http_error(mock_webbrowser_open, mock_get) -> None:
    """Test with HTTP error response."""
    mock_response = Mock()
    mock_response.status_code = 404
    mock_get.return_value.__enter__.return_value = mock_response

    assert not verify_and_open_url("https://example.com")
    mock_get.assert_called_once()
    mock_webbrowser_open.assert_not_called()


@patch("ardupilot_methodic_configurator.backend_internet.httpx2_stream")
@patch("ardupilot_methodic_configurator.backend_internet.webbrowser_open")
def test_verify_and_open_url_request_exception(mock_webbrowser_open, mock_get) -> None:
    """Test with request exception."""
    mock_get.side_effect = httpx2_ConnectError("Connection failed")

    assert not verify_and_open_url("https://example.com")
    mock_get.assert_called_once()
    mock_webbrowser_open.assert_not_called()


@patch("ardupilot_methodic_configurator.backend_internet.httpx2_stream")
@patch("ardupilot_methodic_configurator.backend_internet.webbrowser_open")
def test_verify_and_open_url_timeout(mock_webbrowser_open, mock_get) -> None:
    """Test with request timeout."""
    mock_get.side_effect = httpx2_ReadTimeout("Request timed out")

    assert not verify_and_open_url("https://example.com")
    mock_get.assert_called_once()
    mock_webbrowser_open.assert_not_called()


@patch("ardupilot_methodic_configurator.backend_internet.httpx2_stream")
@patch("ardupilot_methodic_configurator.backend_internet.webbrowser_open")
def test_verify_and_open_url_browser_exception(mock_webbrowser_open, mock_get) -> None:
    """Test with browser opening exception."""
    # Setup successful HTTP response but browser error
    mock_response = Mock()
    mock_response.status_code = 200
    mock_get.return_value.__enter__.return_value = mock_response
    mock_webbrowser_open.side_effect = Exception("Browser failed to open")

    assert not verify_and_open_url("https://example.com")
    mock_get.assert_called_once()
    mock_webbrowser_open.assert_called_once()


@patch("ardupilot_methodic_configurator.backend_internet.webbrowser_open")
def test_verify_and_open_url_fails_gracefully_with_stale_ssl_cert_file(
    mock_webbrowser_open, tmp_path, monkeypatch, caplog
) -> None:
    """A stale SSL_CERT_FILE makes the URL check fail instead of raising, and the error names the variable."""
    stale_cert_file = str(tmp_path / "uninstalled-tool-ca.pem")
    monkeypatch.setenv("SSL_CERT_FILE", stale_cert_file)

    assert not verify_and_open_url("https://example.com")
    mock_webbrowser_open.assert_not_called()
    assert any("SSL_CERT_FILE" in r.getMessage() and stale_cert_file in r.getMessage() for r in caplog.records)


@patch("ardupilot_methodic_configurator.backend_internet.webbrowser_open")
def test_verify_and_open_url_supports_socks_proxies(mock_webbrowser_open, monkeypatch) -> None:
    """A SOCKS proxy is used for the URL check; an unreachable one makes the check fail instead of raising."""
    for name in ("HTTPS_PROXY", "https_proxy", "NO_PROXY", "no_proxy", "SSL_CERT_FILE", "SSL_CERT_DIR"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("ALL_PROXY", "socks5://127.0.0.1:1")

    assert not verify_and_open_url("https://example.com")
    mock_webbrowser_open.assert_not_called()


@patch("ardupilot_methodic_configurator.backend_internet.httpx2_get")
def test_get_release_info_success(mock_get) -> None:
    """Test successful retrieval of release information."""
    mock_response = Mock()
    mock_release_data = {
        "tag_name": "v1.0.0",
        "name": "Release 1.0.0",
        "body": "Release notes",
        "prerelease": False,
        "assets": [{"name": "asset1", "browser_download_url": "http://example.com/asset1"}],
    }
    mock_response.json.return_value = mock_release_data
    mock_get.return_value = mock_response

    release_info = get_release_info("latest", should_be_pre_release=False)

    mock_get.assert_called_once()
    assert release_info == mock_release_data
    assert release_info["tag_name"] == "v1.0.0"


@patch("ardupilot_methodic_configurator.backend_internet.httpx2_get")
def test_get_release_info_empty_name(mock_get) -> None:
    """Test with empty release name."""
    with pytest.raises(ValueError, match=r"^Release name cannot be empty$"):
        get_release_info("", should_be_pre_release=False)
    mock_get.assert_not_called()


@patch("ardupilot_methodic_configurator.backend_internet.httpx2_get")
def test_get_release_info_http_error(mock_get) -> None:
    """Test handling of HTTP errors."""
    mock_response = Mock()
    mock_response.status_code = 404
    mock_error = httpx2_HTTPStatusError("404 Not Found", request=Mock(), response=mock_response)
    mock_get.side_effect = mock_error

    with pytest.raises(httpx2_HTTPStatusError):
        get_release_info("latest", should_be_pre_release=False)
    mock_get.assert_called_once()


@patch("ardupilot_methodic_configurator.backend_internet.httpx2_get")
def test_get_release_info_rate_limit_error(mock_get, caplog) -> None:
    """Test handling of GitHub API rate limit errors."""
    mock_response = Mock()
    mock_response.status_code = 403
    mock_response.headers = Headers({"X-RateLimit-Reset": "1609459200"})  # 2021-01-01 00:00:00 UTC
    mock_error = httpx2_HTTPStatusError("API rate limit exceeded", request=Mock(), response=mock_response)
    mock_get.side_effect = mock_error

    with pytest.raises(httpx2_HTTPStatusError):
        get_release_info("latest", should_be_pre_release=False)
    mock_get.assert_called_once()
    assert caplog.records[0].getMessage() == f"Failed to fetch release info: {mock_error}"
    assert caplog.records[1].getMessage() == "Rate limit exceeded. Please try again after: 2021-01-01 00:00:00 UTC (UTC)"


@patch("ardupilot_methodic_configurator.backend_internet.httpx2_get")
def test_get_release_info_rate_limit_without_reset_header(mock_get, caplog) -> None:
    """Rate-limit handling gives a UTC fallback when GitHub omits its reset header."""
    mock_response = Mock()
    mock_response.status_code = 403
    mock_response.headers = Headers({})
    error = httpx2_HTTPStatusError("API rate limit exceeded", request=Mock(), response=mock_response)
    mock_get.side_effect = error

    with pytest.raises(httpx2_HTTPStatusError):
        get_release_info("latest", should_be_pre_release=False)

    assert caplog.records[-1].getMessage() == "Rate limit exceeded. Please try again after: 1970-01-01 00:00:00 UTC (UTC)"


@patch("ardupilot_methodic_configurator.backend_internet.httpx2_get")
def test_get_release_info_request_exception(mock_get, caplog) -> None:
    """Test handling of general request exceptions."""
    error = httpx2_ConnectError("Connection failed")
    mock_get.side_effect = error

    with pytest.raises(httpx2_HTTPError):
        get_release_info("latest", should_be_pre_release=False)
    mock_get.assert_called_once()
    assert caplog.records[-1].getMessage() == f"Failed to fetch release info: {error}"


@patch("ardupilot_methodic_configurator.backend_internet.httpx2_get")
def test_get_release_info_timeout(mock_get, caplog) -> None:
    """Test handling of request timeouts."""
    error = httpx2_ReadTimeout("Request timed out")
    mock_get.side_effect = error

    with pytest.raises(httpx2_HTTPError):
        get_release_info("latest", should_be_pre_release=False)
    mock_get.assert_called_once()
    assert caplog.records[-1].getMessage() == f"Failed to fetch release info: {error}"


@patch("ardupilot_methodic_configurator.backend_internet.httpx2_get")
def test_get_release_info_value_error(mock_get, caplog) -> None:
    """Test handling of invalid JSON responses."""
    mock_response = Mock()
    mock_response.json.side_effect = ValueError("Invalid JSON")
    mock_get.return_value = mock_response

    with pytest.raises(ValueError, match="Invalid JSON"):
        get_release_info("latest", should_be_pre_release=False)
    assert caplog.records[-1].getMessage() == "Invalid release data: Invalid JSON"


@patch("ardupilot_methodic_configurator.backend_internet.httpx2_get")
def test_get_release_info_key_error(mock_get, caplog) -> None:
    """Test handling of missing keys in response."""
    mock_response = Mock()
    mock_response.json.return_value = {"name": "Release 1.0.0"}  # Missing 'prerelease' key
    mock_get.return_value = mock_response

    with pytest.raises(KeyError):
        get_release_info("latest", should_be_pre_release=False)
    assert caplog.records[-1].getMessage() == "Invalid release data: 'prerelease'"


@patch("ardupilot_methodic_configurator.backend_internet.httpx2_get")
@patch("ardupilot_methodic_configurator.backend_internet._get_github_api_headers")
def test_get_release_info_correct_url_formation(mock_headers, mock_get) -> None:
    """Test correct URL formation with different input formats."""
    mock_headers.return_value = {}
    mock_response = Mock()
    mock_response.json.return_value = {"prerelease": False}
    mock_get.return_value = mock_response

    # Test with leading slash
    get_release_info("/latest", should_be_pre_release=False)
    mock_get.assert_called_with(
        "https://api.github.com/repos/ArduPilot/MethodicConfigurator/releases/latest",
        timeout=30,
        headers={},
        follow_redirects=True,
    )
    mock_get.reset_mock()

    # Test without leading slash
    get_release_info("latest", should_be_pre_release=False)
    mock_get.assert_called_with(
        "https://api.github.com/repos/ArduPilot/MethodicConfigurator/releases/latest",
        timeout=30,
        headers={},
        follow_redirects=True,
    )
    mock_get.reset_mock()

    # Test with tag name
    get_release_info("tags/v1.0.0", should_be_pre_release=False)
    mock_get.assert_called_with(
        "https://api.github.com/repos/ArduPilot/MethodicConfigurator/releases/tags/v1.0.0",
        timeout=30,
        headers={},
        follow_redirects=True,
    )
    mock_get.reset_mock()

    get_release_info("/X/latest", should_be_pre_release=False)
    mock_get.assert_called_with(
        "https://api.github.com/repos/ArduPilot/MethodicConfigurator/releases/X/latest",
        timeout=30,
        headers={},
        follow_redirects=True,
    )


@patch("ardupilot_methodic_configurator.backend_internet.httpx2_get")
@patch("ardupilot_methodic_configurator.backend_internet._get_github_api_headers")
def test_get_release_info_custom_timeout(mock_headers, mock_get) -> None:
    """Test custom timeout parameter."""
    mock_headers.return_value = {}
    mock_response = Mock()
    mock_response.json.return_value = {"prerelease": False}
    mock_get.return_value = mock_response

    get_release_info("latest", should_be_pre_release=False, timeout=60)
    mock_get.assert_called_with(
        "https://api.github.com/repos/ArduPilot/MethodicConfigurator/releases/latest",
        timeout=60,
        headers={},
        follow_redirects=True,
    )


@patch("ardupilot_methodic_configurator.backend_internet.httpx2_get")
def test_get_release_info_prerelease_expectation_violated(mock_get, caplog) -> None:
    """Mismatched release channels are logged while the release payload is returned."""
    stable_response = Mock()
    stable_response.json.return_value = {"prerelease": False}
    mock_get.return_value = stable_response

    stable_result = get_release_info("latest", should_be_pre_release=True)
    assert not stable_result["prerelease"]
    assert caplog.records[-1].getMessage() == "The latest continuous delivery build must be a pre-release"
    mock_get.reset_mock()
    caplog.clear()

    prerelease_response = Mock()
    prerelease_response.json.return_value = {"prerelease": True}
    mock_get.return_value = prerelease_response

    prerelease_result = get_release_info("latest", should_be_pre_release=False)
    assert prerelease_result["prerelease"]
    assert caplog.records[-1].getMessage() == "The latest stable release must not be a pre-release"
