"""
Unit tests for checksum parsing helpers in backend_internet.

These tests exercise `get_expected_sha256_from_release` behaviour against
different asset and release body formats.
"""

from typing import NoReturn

from requests.exceptions import RequestException

from ardupilot_methodic_configurator.backend_internet import get_expected_sha256_from_release


class DummyResp:
    def __init__(self, text: str = "") -> None:
        self.text = text

    def raise_for_status(self) -> None:  # mimic requests.Response
        return None


def test_parse_sha256_from_asset_exact_match(monkeypatch) -> None:
    filename = "mywheel-1.2.3-py3.whl"
    expected = "a" * 64
    text = f"{expected}  {filename}\n"

    release_info = {
        "assets": [{"name": "SHA256SUMS", "browser_download_url": "https://example.com/sums"}],
        "body": "",
    }

    monkeypatch.setattr(
        "ardupilot_methodic_configurator.backend_internet.requests_get",
        lambda *_, **__: DummyResp(text),
    )

    got = get_expected_sha256_from_release(release_info, filename)
    assert got == expected


def test_parse_sha256_from_asset_first_hash(monkeypatch) -> None:
    filename = "other.whl"
    expected = "b" * 64
    text = f"{expected}\n"

    release_info = {"assets": [{"name": "checksums.txt", "browser_download_url": "u"}], "body": ""}

    monkeypatch.setattr(
        "ardupilot_methodic_configurator.backend_internet.requests_get",
        lambda *_, **__: DummyResp(text),
    )

    got = get_expected_sha256_from_release(release_info, filename)
    assert got == expected


def test_fallback_to_body_hash() -> None:
    filename = "pkg.exe"
    expected = "c" * 64
    release_info = {"assets": [], "body": f"Release notes\n{expected}  {filename}\n"}

    got = get_expected_sha256_from_release(release_info, filename)
    assert got == expected


def test_body_single_hash_without_filename() -> None:
    expected = "d" * 64
    release_info = {"assets": [], "body": f"{expected}\n"}
    got = get_expected_sha256_from_release(release_info, "anyfile")
    assert got == expected


def test_requests_error_skips_asset_and_uses_body(monkeypatch) -> None:
    filename = "file.whl"
    expected = "e" * 64
    release_info = {
        "assets": [{"name": "sha256sums.txt", "browser_download_url": "u"}],
        "body": f"Notes {expected}\n",
    }

    def _raise(*_, **__) -> NoReturn:
        msg = "network"
        raise RequestException(msg)

    monkeypatch.setattr(
        "ardupilot_methodic_configurator.backend_internet.requests_get",
        _raise,
    )

    got = get_expected_sha256_from_release(release_info, filename)
    assert got == expected


def test_no_hash_found_returns_none(monkeypatch) -> None:
    release_info = {"assets": [{"name": "notes.txt", "browser_download_url": "u"}], "body": ""}
    monkeypatch.setattr(
        "ardupilot_methodic_configurator.backend_internet.requests_get",
        lambda *_, **__: DummyResp(""),
    )

    got = get_expected_sha256_from_release(release_info, "file.bin")
    assert got is None
