#!/usr/bin/env python3

"""
Unit tests for the backend_internet.py file.

These tests focus on implementation details, edge cases, and error handling.
For behavior-driven tests of software update functionality, see bdd_software_update.py.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import os
from collections.abc import Generator
from typing import Any
from unittest.mock import Mock, patch

import pytest
from requests import HTTPError as requests_HTTPError
from requests import RequestException as requests_RequestException
from requests import Timeout as requests_Timeout

from ardupilot_methodic_configurator.backend_internet import (
    _get_verify_param,
    _install_app_from_mount,
    _mount_dmg,
    _unmount_dmg,
    _validate_download_file,
    _validate_github_url,
    download_and_install_on_macos,
    download_and_install_on_windows,
    download_and_install_pip_release,
    download_file_from_url,
    get_release_info,
    verify_and_open_url,
)

# pylint: disable=unused-argument, too-many-lines, redefined-outer-name


def test_download_file_from_url_empty_params() -> None:
    assert not download_file_from_url("", "")
    assert not download_file_from_url("http://test.com", "")
    assert not download_file_from_url("", "test.txt")


@pytest.mark.parametrize(
    "env_vars",
    [
        {},
        {"HTTP_PROXY": "http://proxy:8080"},
        {"HTTPS_PROXY": "https://proxy:8080"},
        {"NO_PROXY": "localhost"},
    ],
)
def test_download_file_from_url_proxy_handling(env_vars) -> None:
    with patch.dict(os.environ, env_vars, clear=True), patch("requests.get") as mock_get:
        mock_get.return_value.status_code = 404
        assert not download_file_from_url("http://test.com", "test.txt", timeout=3)


@patch("ardupilot_methodic_configurator.backend_internet.requests_get")
def test_download_file_success(mock_get, tmp_path) -> None:
    # Setup mock response
    mock_response = Mock()
    mock_response.headers = {"content-length": "100"}
    mock_response.iter_content.return_value = [b"test data"]
    mock_response.raise_for_status.return_value = None
    mock_get.return_value = mock_response

    test_file = tmp_path / "test.txt"
    assert download_file_from_url("http://test.com", str(test_file))
    assert test_file.read_bytes() == b"test data"


@pytest.fixture
def mock_get_() -> Mock:
    with patch("ardupilot_methodic_configurator.backend_internet.requests_get") as _mock:
        yield _mock


@patch("ardupilot_methodic_configurator.backend_internet.requests_get")
def test_download_file_invalid_content_length(mock_get) -> None:
    # Test handling of invalid content-length header
    mock_response = Mock()
    mock_response.headers = {"content-length": "invalid"}
    mock_response.iter_content.return_value = [b"test data"]
    mock_get.return_value = mock_response
    assert not download_file_from_url("http://test.com", "test.txt")


@patch("ardupilot_methodic_configurator.backend_internet.requests_get")
def test_download_file_missing_content_length(mock_get) -> None:
    # Test handling of missing content-length header
    mock_response = Mock()
    mock_response.headers = {}
    mock_response.iter_content.return_value = [b"test data"]
    mock_get.return_value = mock_response
    assert download_file_from_url("http://test.com", "test.txt")


@patch("ardupilot_methodic_configurator.backend_internet.requests_get")
def test_download_file_empty_response(mock_get) -> None:
    # Test handling of empty response
    mock_response = Mock()
    mock_response.headers = {"content-length": "0"}
    mock_response.iter_content.return_value = []
    mock_get.return_value = mock_response
    assert not download_file_from_url("http://test.com", "test.txt")


@patch("ardupilot_methodic_configurator.backend_internet.requests_get")
def test_download_file_http_error(mock_get) -> None:
    # Test HTTP error handling
    mock_response = Mock()
    mock_response.raise_for_status.side_effect = requests_HTTPError("404 Not Found")
    mock_get.return_value = mock_response
    assert not download_file_from_url("http://test.com", "test.txt")


@patch("ardupilot_methodic_configurator.backend_internet.requests_get")
def test_download_file_with_progress_no_content_length(mock_get, tmp_path) -> None:
    # Test progress callback without content-length header
    mock_response = Mock()
    mock_response.headers = {}
    mock_response.iter_content.return_value = [b"data"] * 4
    mock_response.raise_for_status.return_value = None
    mock_get.return_value = mock_response

    progress_callback = Mock()
    test_file = tmp_path / "test.txt"

    assert download_file_from_url("http://test.com", str(test_file), progress_callback=progress_callback)
    assert progress_callback.call_count == 1  # Only final callback
    progress_callback.assert_called_with(100.0, "Download complete")


@patch("ardupilot_methodic_configurator.backend_internet.requests_get")
@patch("ardupilot_methodic_configurator.backend_internet._get_verify_param")
def test_download_file_proxy_configuration(mock_verify, mock_get, monkeypatch) -> None:
    # Test proxy configuration handling
    mock_verify.return_value = "/path/to/certs.pem"
    mock_response = Mock()
    mock_response.headers = {"content-length": "100"}
    mock_response.iter_content.return_value = [b"test data"]
    mock_get.return_value = mock_response

    # Set environment variables
    monkeypatch.setenv("HTTP_PROXY", "http://proxy:8080")
    monkeypatch.setenv("HTTPS_PROXY", "https://proxy:8080")
    monkeypatch.setenv("NO_PROXY", "localhost")

    assert download_file_from_url("http://test.com", "test.txt", timeout=3)
    mock_get.assert_called_once_with(
        "http://test.com",
        stream=True,
        timeout=3,
        proxies={"http": "http://proxy:8080", "https": "https://proxy:8080", "no_proxy": "localhost"},
        verify="/path/to/certs.pem",
    )


@patch("ardupilot_methodic_configurator.backend_internet.requests_get")
def test_download_file_value_error(mock_get) -> None:
    # Test handling of ValueError during download
    mock_response = Mock()
    mock_response.headers = {"content-length": "100"}
    mock_response.iter_content.side_effect = ValueError("Invalid data")
    mock_get.return_value = mock_response
    assert not download_file_from_url("http://test.com", "test.txt")


def test_download_file_from_url_invalid_url() -> None:
    # Test with invalid URL format
    assert not download_file_from_url("not_a_valid_url", "test.txt")


@patch("ardupilot_methodic_configurator.backend_internet.requests_get")
def test_download_file_unicode_error(mock_get) -> None:
    # Test handling of Unicode decode errors
    mock_response = Mock()
    mock_response.headers = {"content-length": "100"}
    mock_response.iter_content.return_value = [bytes([0xFF, 0xFE, 0xFD])]  # Invalid UTF-8
    mock_get.return_value = mock_response
    assert download_file_from_url("http://test.com", "test.txt")


@patch("ardupilot_methodic_configurator.backend_internet.requests_get")
def test_get_release_info_invalid_release(mock_get) -> None:
    mock_get.side_effect = requests_RequestException()
    with pytest.raises(requests_RequestException):
        get_release_info("latest", should_be_pre_release=False)


@patch("ardupilot_methodic_configurator.backend_internet.requests_get")
def test_get_release_info_prerelease_mismatch(mock_get) -> None:
    mock_response = Mock()
    mock_response.json.return_value = {"prerelease": True}
    mock_get.return_value = mock_response


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

    # Verify pip was called
    call_args = mock_check_call.call_args[0][0]
    assert call_args[1] == "-m"
    assert call_args[2] == "pip"


@patch("shutil.which", return_value="/usr/bin/uv")  # uv is available
@patch("subprocess.check_call")
def test_download_and_install_pip_release_with_uv(mock_check_call, mock_which) -> None:
    mock_check_call.return_value = 0
    assert download_and_install_pip_release() == 0
    mock_which.assert_called_once_with("uv")

    # Verify uv was called
    call_args = mock_check_call.call_args[0][0]
    assert call_args[0] == "/usr/bin/uv"
    assert call_args[1] == "pip"


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
        assert "small" in caplog.text.lower() or "bytes" in caplog.text.lower()

    def test_accepts_file_with_correct_magic_bytes(self, tmp_path) -> None:
        f = tmp_path / "test.exe"
        f.write_bytes(b"MZ" + b"X" * 2048)
        assert _validate_download_file(str(f), magic_bytes=b"MZ")

    def test_rejects_file_with_wrong_magic_bytes(self, tmp_path, caplog) -> None:
        f = tmp_path / "bad.exe"
        f.write_bytes(b"PK" + b"X" * 2048)  # ZIP signature instead of PE
        assert not _validate_download_file(str(f), magic_bytes=b"MZ", magic_error_msg="Not a PE file")
        assert "Not a PE file" in caplog.text

    def test_uses_default_error_message_when_none_given(self, tmp_path, caplog) -> None:
        f = tmp_path / "bad.bin"
        f.write_bytes(b"?!" + b"X" * 2048)
        assert not _validate_download_file(str(f), magic_bytes=b"MZ")
        assert caplog.text  # some error was logged

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
        """Given all steps succeed, returns True and reports 100% completion."""
        progress = Mock()
        assert download_and_install_on_macos(GITHUB_DOWNLOAD_URL, DMG_FILE_NAME, progress_callback=progress)
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
        response.iter_content.return_value = [b"test data"]
        response.raise_for_status.return_value = None
        return response

    @pytest.fixture
    def mock_get(self) -> Mock:
        with patch("ardupilot_methodic_configurator.backend_internet.requests_get") as _mock:
            yield _mock

    @pytest.fixture
    def mock_verify(self) -> Mock:
        with patch("ardupilot_methodic_configurator.backend_internet._get_verify_param") as _mock:
            _mock.return_value = "/path/to/certs.pem"
            yield _mock

    def test_download_file_network_errors(self, mock_get, caplog) -> None:
        errors = [
            requests_HTTPError("404 Not Found"),
            requests_RequestException("Connection failed"),
            ValueError("Invalid response"),
            OSError("File system error"),
        ]

        for error in errors:
            mock_get.side_effect = error
            assert not download_file_from_url("http://test.com", "test.txt")
            assert str(error) in caplog.text
            caplog.clear()

    def test_download_file_progress_tracking(self, mock_get, mock_response, tmp_path) -> None:
        mock_get.return_value = mock_response
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

    def test_download_file_proxy_configs(self, mock_get, mock_verify, monkeypatch) -> None:
        proxy_configs = [
            {"HTTP_PROXY": "http://proxy1:8080"},
            {"HTTPS_PROXY": "https://proxy2:8080"},
            {"HTTP_PROXY": "http://proxy3:8080", "NO_PROXY": "localhost"},
        ]

        mock_response = Mock()
        mock_response.headers = {"content-length": "100"}
        mock_response.iter_content.return_value = [b"test data"]
        mock_get.return_value = mock_response

        for config in proxy_configs:
            # Clear previous env vars
            monkeypatch.delenv("HTTP_PROXY", raising=False)
            monkeypatch.delenv("HTTPS_PROXY", raising=False)
            monkeypatch.delenv("NO_PROXY", raising=False)

            # Set new config
            for key, value in config.items():
                monkeypatch.setenv(key, value)

            download_file_from_url("http://test.com", "test.txt", allow_resume=False)

            expected_proxies = {}
            if "HTTP_PROXY" in config:
                expected_proxies["http"] = config["HTTP_PROXY"]
            if "HTTPS_PROXY" in config:
                expected_proxies["https"] = config["HTTPS_PROXY"]
            if "NO_PROXY" in config:
                expected_proxies["no_proxy"] = config["NO_PROXY"]

            mock_get.assert_called_with(
                "http://test.com", stream=True, timeout=30, proxies=expected_proxies, verify="/path/to/certs.pem"
            )
            mock_get.reset_mock()

    def test_download_file_filesystem_operations(self, mock_get, mock_response, tmp_path) -> None:
        mock_get.return_value = mock_response
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


@patch("ardupilot_methodic_configurator.backend_internet.requests_get")
@patch("ardupilot_methodic_configurator.backend_internet.webbrowser_open")
def test_verify_and_open_url_success(mock_webbrowser_open, mock_get) -> None:
    """Test successful URL verification and opening."""
    # Setup mock responses
    mock_response = Mock()
    mock_response.status_code = 200
    mock_get.return_value = mock_response
    mock_webbrowser_open.return_value = True

    # Call function and verify results
    assert verify_and_open_url("https://example.com")
    mock_get.assert_called_once()
    mock_webbrowser_open.assert_called_once_with(url="https://example.com", new=0, autoraise=True)


@patch("ardupilot_methodic_configurator.backend_internet.requests_get")
@patch("ardupilot_methodic_configurator.backend_internet.webbrowser_open")
def test_verify_and_open_url_empty_url(mock_webbrowser_open, mock_get) -> None:
    """Test with empty URL."""
    assert not verify_and_open_url("")
    mock_get.assert_not_called()
    mock_webbrowser_open.assert_not_called()


@patch("ardupilot_methodic_configurator.backend_internet.requests_get")
@patch("ardupilot_methodic_configurator.backend_internet.webbrowser_open")
def test_verify_and_open_url_http_error(mock_webbrowser_open, mock_get) -> None:
    """Test with HTTP error response."""
    mock_response = Mock()
    mock_response.status_code = 404
    mock_get.return_value = mock_response

    assert not verify_and_open_url("https://example.com")
    mock_get.assert_called_once()
    mock_webbrowser_open.assert_not_called()


@patch("ardupilot_methodic_configurator.backend_internet.requests_get")
@patch("ardupilot_methodic_configurator.backend_internet.webbrowser_open")
def test_verify_and_open_url_request_exception(mock_webbrowser_open, mock_get) -> None:
    """Test with request exception."""
    mock_get.side_effect = requests_RequestException("Connection failed")

    assert not verify_and_open_url("https://example.com")
    mock_get.assert_called_once()
    mock_webbrowser_open.assert_not_called()


@patch("ardupilot_methodic_configurator.backend_internet.requests_get")
@patch("ardupilot_methodic_configurator.backend_internet.webbrowser_open")
def test_verify_and_open_url_timeout(mock_webbrowser_open, mock_get) -> None:
    """Test with request timeout."""
    mock_get.side_effect = requests_Timeout("Request timed out")

    assert not verify_and_open_url("https://example.com")
    mock_get.assert_called_once()
    mock_webbrowser_open.assert_not_called()


@patch("ardupilot_methodic_configurator.backend_internet.requests_get")
@patch("ardupilot_methodic_configurator.backend_internet.webbrowser_open")
def test_verify_and_open_url_browser_exception(mock_webbrowser_open, mock_get) -> None:
    """Test with browser opening exception."""
    # Setup successful HTTP response but browser error
    mock_response = Mock()
    mock_response.status_code = 200
    mock_get.return_value = mock_response
    mock_webbrowser_open.side_effect = Exception("Browser failed to open")

    assert not verify_and_open_url("https://example.com")
    mock_get.assert_called_once()
    mock_webbrowser_open.assert_called_once()


@pytest.mark.parametrize(
    "env_vars",
    [
        {},
        {"HTTP_PROXY": "http://proxy:8080"},
        {"HTTPS_PROXY": "https://proxy:8080"},
        {"NO_PROXY": "localhost"},
        {"HTTP_PROXY": "http://proxy:8080", "HTTPS_PROXY": "https://proxy:8080"},
    ],
)
@patch("ardupilot_methodic_configurator.backend_internet.requests_get")
@patch("ardupilot_methodic_configurator.backend_internet.webbrowser_open")
def test_verify_and_open_url_proxy_handling(mock_webbrowser_open, mock_get, env_vars, monkeypatch) -> None:
    """Test proxy handling with different environment variables."""
    # Clear existing env vars
    for var in ["HTTP_PROXY", "HTTPS_PROXY", "NO_PROXY", "http_proxy", "https_proxy", "no_proxy"]:
        monkeypatch.delenv(var, raising=False)

    # Set test env vars
    for key, value in env_vars.items():
        monkeypatch.setenv(key, value)

    # Setup successful response
    mock_response = Mock()
    mock_response.status_code = 200
    mock_get.return_value = mock_response
    mock_webbrowser_open.return_value = True

    # Call function
    assert verify_and_open_url("https://example.com")

    # Verify correct proxies were used
    expected_proxies = {k.lower().replace("_proxy", ""): v for k, v in env_vars.items() if k.upper() != "NO_PROXY"}
    if "NO_PROXY" in env_vars:
        expected_proxies["no_proxy"] = env_vars["NO_PROXY"]

    # Get the actual proxies passed to requests_get
    call_args = mock_get.call_args
    if expected_proxies:
        assert "proxies" in call_args[1]
        for key, value in expected_proxies.items():
            assert call_args[1]["proxies"][key] == value
    else:
        # Empty dict should be passed when no proxies are configured
        assert call_args[1]["proxies"] == {}


@patch("ardupilot_methodic_configurator.backend_internet.requests_get")
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


@patch("ardupilot_methodic_configurator.backend_internet.requests_get")
def test_get_release_info_empty_name(mock_get) -> None:
    """Test with empty release name."""
    with pytest.raises(ValueError, match="Release name cannot be empty"):
        get_release_info("", should_be_pre_release=False)
    mock_get.assert_not_called()


@patch("ardupilot_methodic_configurator.backend_internet.requests_get")
def test_get_release_info_http_error(mock_get) -> None:
    """Test handling of HTTP errors."""
    mock_response = Mock()
    mock_response.status_code = 404
    mock_error = requests_HTTPError("404 Not Found")
    mock_error.response = mock_response
    mock_get.side_effect = mock_error

    with pytest.raises(requests_HTTPError):
        get_release_info("latest", should_be_pre_release=False)
    mock_get.assert_called_once()


@patch("ardupilot_methodic_configurator.backend_internet.requests_get")
def test_get_release_info_rate_limit_error(mock_get) -> None:
    """Test handling of GitHub API rate limit errors."""
    mock_response = Mock()
    mock_response.status_code = 403
    mock_response.headers = {"X-RateLimit-Reset": "1609459200"}  # 2021-01-01 00:00:00 UTC
    mock_error = requests_HTTPError("API rate limit exceeded")
    mock_error.response = mock_response
    mock_get.side_effect = mock_error

    with pytest.raises(requests_HTTPError):
        get_release_info("latest", should_be_pre_release=False)
    mock_get.assert_called_once()


@patch("ardupilot_methodic_configurator.backend_internet.requests_get")
def test_get_release_info_request_exception(mock_get) -> None:
    """Test handling of general request exceptions."""
    mock_get.side_effect = requests_RequestException("Connection failed")

    with pytest.raises(requests_RequestException):
        get_release_info("latest", should_be_pre_release=False)
    mock_get.assert_called_once()


@patch("ardupilot_methodic_configurator.backend_internet.requests_get")
def test_get_release_info_timeout(mock_get) -> None:
    """Test handling of request timeouts."""
    mock_get.side_effect = requests_Timeout("Request timed out")

    with pytest.raises(requests_RequestException):
        get_release_info("latest", should_be_pre_release=False)
    mock_get.assert_called_once()


@patch("ardupilot_methodic_configurator.backend_internet.requests_get")
def test_get_release_info_value_error(mock_get) -> None:
    """Test handling of invalid JSON responses."""
    mock_response = Mock()
    mock_response.json.side_effect = ValueError("Invalid JSON")
    mock_get.return_value = mock_response

    with pytest.raises(ValueError, match="Invalid JSON"):
        get_release_info("latest", should_be_pre_release=False)


@patch("ardupilot_methodic_configurator.backend_internet.requests_get")
def test_get_release_info_key_error(mock_get) -> None:
    """Test handling of missing keys in response."""
    mock_response = Mock()
    mock_response.json.return_value = {"name": "Release 1.0.0"}  # Missing 'prerelease' key
    mock_get.return_value = mock_response

    with pytest.raises(KeyError):
        get_release_info("latest", should_be_pre_release=False)


@patch("ardupilot_methodic_configurator.backend_internet.requests_get")
@patch("ardupilot_methodic_configurator.backend_internet._get_verify_param")
@patch("ardupilot_methodic_configurator.backend_internet._get_github_api_headers")
def test_get_release_info_correct_url_formation(mock_headers, mock_verify, mock_get) -> None:
    """Test correct URL formation with different input formats."""
    mock_headers.return_value = {}
    mock_verify.return_value = "/path/to/certs.pem"
    mock_response = Mock()
    mock_response.json.return_value = {"prerelease": False}
    mock_get.return_value = mock_response

    # Test with leading slash
    get_release_info("/latest", should_be_pre_release=False)
    mock_get.assert_called_with(
        "https://api.github.com/repos/ArduPilot/MethodicConfigurator/releases/latest",
        timeout=30,
        verify="/path/to/certs.pem",
        headers={},
    )
    mock_get.reset_mock()

    # Test without leading slash
    get_release_info("latest", should_be_pre_release=False)
    mock_get.assert_called_with(
        "https://api.github.com/repos/ArduPilot/MethodicConfigurator/releases/latest",
        timeout=30,
        verify="/path/to/certs.pem",
        headers={},
    )
    mock_get.reset_mock()

    # Test with tag name
    get_release_info("tags/v1.0.0", should_be_pre_release=False)
    mock_get.assert_called_with(
        "https://api.github.com/repos/ArduPilot/MethodicConfigurator/releases/tags/v1.0.0",
        timeout=30,
        verify="/path/to/certs.pem",
        headers={},
    )


@patch("ardupilot_methodic_configurator.backend_internet.requests_get")
@patch("ardupilot_methodic_configurator.backend_internet._get_verify_param")
@patch("ardupilot_methodic_configurator.backend_internet._get_github_api_headers")
def test_get_release_info_custom_timeout(mock_headers, mock_verify, mock_get) -> None:
    """Test custom timeout parameter."""
    mock_headers.return_value = {}
    mock_verify.return_value = "/path/to/certs.pem"
    mock_response = Mock()
    mock_response.json.return_value = {"prerelease": False}
    mock_get.return_value = mock_response

    get_release_info("latest", should_be_pre_release=False, timeout=60)
    mock_get.assert_called_with(
        "https://api.github.com/repos/ArduPilot/MethodicConfigurator/releases/latest",
        timeout=60,
        verify="/path/to/certs.pem",
        headers={},
    )


@patch("ardupilot_methodic_configurator.backend_internet.requests_get")
def test_get_release_info_prerelease_expectation_violated(mock_get) -> None:
    """Test when prerelease expectation is violated."""
    # Case 1: Expected prerelease but got stable
    mock_response = Mock()
    mock_response.json.return_value = {"prerelease": False}
    mock_get.return_value = mock_response

    # Should log an error but still return the data
    result = get_release_info("latest", should_be_pre_release=True)
    assert not result["prerelease"]
    mock_get.reset_mock()

    # Case 2: Expected stable but got prerelease
    mock_response = Mock()
    mock_response.json.return_value = {"prerelease": True}
    mock_get.return_value = mock_response


@patch("ardupilot_methodic_configurator.backend_internet.certifi")
@patch("ardupilot_methodic_configurator.backend_internet.os.path.isfile")
@patch("ardupilot_methodic_configurator.backend_internet.os.environ")
def test_get_verify_param_env_var_set(mock_environ, mock_isfile, mock_certifi) -> None:  # noqa: ARG001
    """Test _get_verify_param with REQUESTS_CA_BUNDLE set."""
    mock_environ.get.return_value = "/custom/ca-bundle.pem"
    mock_isfile.return_value = True

    result = _get_verify_param()
    assert result == "/custom/ca-bundle.pem"
    mock_environ.get.assert_called_with("REQUESTS_CA_BUNDLE")


@patch("ardupilot_methodic_configurator.backend_internet.certifi")
@patch("ardupilot_methodic_configurator.backend_internet.os.path.isfile")
@patch("ardupilot_methodic_configurator.backend_internet.os.environ")
def test_get_verify_param_ssl_cert_file_set(mock_environ, mock_isfile, mock_certifi) -> None:  # noqa: ARG001
    """Test _get_verify_param with SSL_CERT_FILE set."""
    mock_environ.get.side_effect = lambda key: "/ssl/cert.pem" if key == "SSL_CERT_FILE" else None
    mock_isfile.return_value = True

    result = _get_verify_param()
    assert result == "/ssl/cert.pem"


@patch("ardupilot_methodic_configurator.backend_internet.certifi")
@patch("ardupilot_methodic_configurator.backend_internet.os.path.isfile")
@patch("ardupilot_methodic_configurator.backend_internet.os.environ")
@patch("ardupilot_methodic_configurator.backend_internet.sys")
def test_get_verify_param_frozen_with_bundled_cert(mock_sys, mock_environ, mock_isfile, mock_certifi) -> None:  # noqa: ARG001
    """Test _get_verify_param when frozen with bundled cert available."""
    mock_environ.get.return_value = None
    mock_sys.frozen = True
    mock_sys._MEIPASS = "/app/dir"  # pylint: disable=protected-access
    mock_isfile.return_value = True

    result = _get_verify_param()
    assert result == "/app/dir/certifi/cacert.pem"


@patch("ardupilot_methodic_configurator.backend_internet.certifi")
@patch("ardupilot_methodic_configurator.backend_internet.os.path.isfile")
@patch("ardupilot_methodic_configurator.backend_internet.os.environ")
@patch("ardupilot_methodic_configurator.backend_internet.sys")
def test_get_verify_param_frozen_bundled_cert_missing(mock_sys, mock_environ, mock_isfile, mock_certifi) -> None:
    """Test _get_verify_param when frozen but bundled cert is missing."""
    mock_environ.get.return_value = None
    mock_sys.frozen = True
    mock_sys._MEIPASS = "/app/dir"  # pylint: disable=protected-access
    # Mock isfile to return False for bundled cert, True for others if needed
    mock_isfile.side_effect = lambda path: path != "/app/dir/certifi/cacert.pem"
    mock_certifi.where.return_value = "/certifi/cacert.pem"

    result = _get_verify_param()
    assert result == "/certifi/cacert.pem"
    mock_certifi.where.assert_called_once()
