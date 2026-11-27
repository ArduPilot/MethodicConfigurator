#!/usr/bin/env python3

"""
Unit tests for checksum parsing helpers in backend_internet.

These tests exercise `get_expected_sha256_from_release` implementation details
against different asset and release body formats.
For behavior-driven tests of software update functionality, see bdd_software_update.py.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

from typing import NoReturn

from httpx2 import ConnectError

from ardupilot_methodic_configurator.backend_internet import get_expected_sha256_from_release


class DummyResp:  # pylint: disable=too-few-public-methods, missing-class-docstring
    def __init__(self, text: str = "") -> None:
        self.text = text

    def raise_for_status(self) -> None:  # mimic Response
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
        "ardupilot_methodic_configurator.backend_internet.httpx2_get",
        lambda *_, **__: DummyResp(text),
    )

    got = get_expected_sha256_from_release(release_info, filename)
    assert got == expected


def test_release_asset_digest_is_used_before_fetching_checksum_files(monkeypatch) -> None:
    """
    A GitHub-provided SHA256 digest is trusted for the selected release asset.

    GIVEN: The release asset contains its SHA256 digest and a checksum sidecar exists
    WHEN: The expected installer checksum is requested
    THEN: The asset digest is returned without downloading the sidecar
    """
    filename = "installer.exe"
    expected = "a" * 64
    requests: list[str] = []
    release_info = {
        "assets": [
            {"name": filename, "digest": f"sha256:{expected}"},
            {"name": "SHA256SUMS", "browser_download_url": "https://example.com/sums"},
        ]
    }

    monkeypatch.setattr(
        "ardupilot_methodic_configurator.backend_internet.httpx2_get",
        lambda url, **_kwargs: (requests.append(url), DummyResp(""))[1],
    )

    assert get_expected_sha256_from_release(release_info, filename) == expected
    assert requests == []


def test_parse_sha256_from_asset_first_hash(monkeypatch) -> None:
    filename = "other.whl"
    expected = "b" * 64
    text = f"{expected}\n"

    release_info = {"assets": [{"name": "checksums.txt", "browser_download_url": "u"}], "body": ""}

    monkeypatch.setattr(
        "ardupilot_methodic_configurator.backend_internet.httpx2_get",
        lambda *_, **__: DummyResp(text),
    )

    got = get_expected_sha256_from_release(release_info, filename)
    assert got == expected


def test_empty_asset_name_does_not_fetch_or_accept_a_checksum(monkeypatch) -> None:
    """
    A checksum is never accepted when no release asset name is selected.

    GIVEN: A release with a checksum file and an empty requested asset name
    WHEN: The expected checksum is looked up
    THEN: No checksum file is fetched and no digest is returned
    """
    requests: list[str] = []
    release_info = {"assets": [{"name": "SHA256SUMS", "browser_download_url": "https://example.com/sums"}]}

    def record_request(url: str, **_kwargs: object) -> DummyResp:
        requests.append(url)
        return DummyResp(f"{'a' * 64}  installer.exe\n")

    monkeypatch.setattr("ardupilot_methodic_configurator.backend_internet.httpx2_get", record_request)

    assert get_expected_sha256_from_release(release_info, "") is None
    assert requests == []


def test_fallback_to_body_hash() -> None:
    """Release body parsing is no longer supported - function should return None."""
    filename = "pkg.exe"
    expected_hash = "c" * 64
    release_info = {"assets": [], "body": f"Release notes\n{expected_hash}  {filename}\n"}

    got = get_expected_sha256_from_release(release_info, filename)
    # Body parsing removed - should return None when only body contains hash
    assert got is None


def test_body_single_hash_without_filename() -> None:
    """Release body parsing is no longer supported - function should return None."""
    expected_hash = "d" * 64
    release_info = {"assets": [], "body": f"{expected_hash}\n"}
    got = get_expected_sha256_from_release(release_info, "anyfile")
    # Body parsing removed - should return None when only body contains hash
    assert got is None


def test_network_error_skips_asset_and_uses_body(monkeypatch) -> None:
    """When asset download fails, function should return None (body parsing removed)."""
    filename = "file.whl"
    expected_hash = "e" * 64
    release_info = {
        "assets": [{"name": "sha256sums.txt", "browser_download_url": "u"}],
        "body": f"Notes {expected_hash}\n",
    }

    def _raise(*_, **__) -> NoReturn:
        msg = "network"
        raise ConnectError(msg)

    monkeypatch.setattr(
        "ardupilot_methodic_configurator.backend_internet.httpx2_get",
        _raise,
    )

    got = get_expected_sha256_from_release(release_info, filename)
    # Body parsing removed - should return None when asset fails and only body has hash
    assert got is None


def test_no_hash_found_returns_none(monkeypatch) -> None:
    release_info = {"assets": [{"name": "notes.txt", "browser_download_url": "u"}], "body": ""}
    monkeypatch.setattr(
        "ardupilot_methodic_configurator.backend_internet.httpx2_get",
        lambda *_, **__: DummyResp(""),
    )

    got = get_expected_sha256_from_release(release_info, "file.bin")
    assert got is None
