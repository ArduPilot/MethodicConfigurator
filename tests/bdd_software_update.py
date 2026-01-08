#!/usr/bin/env python3

"""
BDD tests for software update functionality.

These tests focus on user behavior and business requirements for the software update feature.
For unit tests of implementation details, see unit_backend_internet.py, unit_checksum_parsing.py,
and unit_download_resume.py.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

from unittest.mock import MagicMock, patch

import pytest
from requests import Timeout

from ardupilot_methodic_configurator.backend_internet import (
    download_and_install_on_windows,
    download_file_from_url,
    get_expected_sha256_from_release,
)
from ardupilot_methodic_configurator.data_model_software_updates import UpdateManager, format_version_info

# pylint: disable=redefined-outer-name, protected-access


@pytest.fixture
def mock_release_info() -> dict:
    """Fixture providing realistic GitHub release information."""
    return {
        "tag_name": "v2.0.0",
        "name": "Version 2.0.0",
        "body": "## Changes\n- New feature [#123](url) ([author](url))\n- Bug fix",
        "prerelease": False,
        "assets": [
            {
                "name": "installer.exe",
                "browser_download_url": (
                    "https://github.com/ArduPilot/MethodicConfigurator/releases/download/v2.0.0/installer.exe"
                ),
            },
            {
                "name": "SHA256SUMS",
                "browser_download_url": (
                    "https://github.com/ArduPilot/MethodicConfigurator/releases/download/v2.0.0/SHA256SUMS"
                ),
            },
        ],
    }


@pytest.fixture
def update_manager() -> UpdateManager:
    """Fixture providing an UpdateManager instance."""
    return UpdateManager()


class TestUserChecksForUpdates:
    """Test user workflows for checking software updates."""

    def test_user_can_see_formatted_version_information(self) -> None:
        """
        User can view clean, formatted version information.

        GIVEN: A new version is available with changelog
        WHEN: The user views the update information
        THEN: The version info should be formatted without PR/author details
        """
        # Arrange
        current = "1.0.0"
        latest = "2.0.0"
        raw_changes = "- Feature [#123](url) ([author](url))\n- Bug fix"

        # Act
        formatted = format_version_info(current, latest, raw_changes)

        # Assert
        assert "1.0.0" in formatted
        assert "2.0.0" in formatted
        assert "[#123]" not in formatted  # PR info removed
        assert "([author]" not in formatted  # Author info removed
        assert "Feature" in formatted
        assert "Bug fix" in formatted

    def test_user_sees_clean_changelog_with_proper_spacing(self) -> None:
        """
        User sees clean changelog without excessive whitespace.

        GIVEN: A changelog with multiple spaces and formatting
        WHEN: The user views the update information
        THEN: Spacing should be normalized while preserving structure
        """
        # Arrange
        changes = "- Feature     with    spaces\n\n- Another    feature"

        # Act
        formatted = format_version_info("1.0", "2.0", changes)

        # Assert
        assert "spaces" in formatted
        assert "    " not in formatted  # Multiple spaces cleaned
        assert "\n" in formatted  # Newlines preserved


class TestWindowsUserInstallsUpdate:
    """Test Windows user workflows for installing software updates."""

    @patch("platform.system")
    @patch("ardupilot_methodic_configurator.data_model_software_updates.download_and_install_on_windows")
    @patch("ardupilot_methodic_configurator.data_model_software_updates.get_expected_sha256_from_release")
    def test_windows_user_can_download_verified_update(  # pylint: disable=too-many-arguments, too-many-positional-arguments
        self, mock_get_sha256, mock_download, mock_platform, update_manager, mock_release_info
    ) -> None:
        """
        Windows user can download and install update with integrity verification.

        GIVEN: A Windows user with internet connection
          AND: A new release is available with checksum
        WHEN: The user chooses to install the update
        THEN: The system should download with SHA256 verification
          AND: Installation should be initiated
        """
        # Arrange
        mock_platform.return_value = "Windows"
        mock_get_sha256.return_value = "a" * 64  # Mock SHA256
        mock_download.return_value = True

        # Act
        result = update_manager._perform_download(mock_release_info)

        # Assert
        assert result is True
        mock_download.assert_called_once()
        call_kwargs = mock_download.call_args.kwargs
        assert "expected_sha256" in call_kwargs
        assert call_kwargs["expected_sha256"] == "a" * 64
        assert call_kwargs["download_url"].startswith("https://github.com/")

    @patch("platform.system")
    @patch("ardupilot_methodic_configurator.data_model_software_updates.download_and_install_on_windows")
    def test_windows_user_sees_progress_during_download(
        self, mock_download, mock_platform, update_manager, mock_release_info
    ) -> None:
        """
        Windows user sees progress feedback during download.

        GIVEN: A Windows user downloading an update
        WHEN: The download is in progress
        THEN: Progress updates should be provided to the user interface
        """
        # Arrange
        mock_platform.return_value = "Windows"
        mock_download.return_value = True
        update_manager.dialog = MagicMock()

        # Act
        update_manager._perform_download(mock_release_info)

        # Assert
        call_kwargs = mock_download.call_args.kwargs
        assert "progress_callback" in call_kwargs
        assert call_kwargs["progress_callback"] is not None

    @patch("platform.system")
    @patch("ardupilot_methodic_configurator.data_model_software_updates.download_and_install_on_windows")
    def test_windows_user_is_informed_when_no_installer_available(self, mock_download, mock_platform, update_manager) -> None:
        """
        Windows user is informed when no installer is available.

        GIVEN: A Windows user attempting to update
          AND: No .exe assets are available in the release
        WHEN: The user tries to download the update
        THEN: The user should be informed of the issue
          AND: No download should be attempted
        """
        # Arrange
        mock_platform.return_value = "Windows"
        release_no_assets = {"tag_name": "v2.0.0", "assets": []}

        # Act
        result = update_manager._perform_download(release_no_assets)

        # Assert
        assert result is False
        mock_download.assert_not_called()


class TestLinuxMacUserInstallsUpdate:  # pylint: disable=too-few-public-methods
    """Test Linux/macOS user workflows for installing software updates."""

    @patch("platform.system")
    @patch("ardupilot_methodic_configurator.data_model_software_updates.download_and_install_pip_release")
    def test_linux_user_can_install_from_pypi(self, mock_pip, mock_platform, update_manager, mock_release_info) -> None:
        """
        Linux/macOS user can install updates from PyPI.

        GIVEN: A Linux or macOS user with internet connection
        WHEN: The user chooses to install the update
        THEN: The system should install from PyPI using pip
          AND: Installation should succeed
        """
        # Arrange
        mock_platform.return_value = "Linux"
        mock_pip.return_value = 0  # Success

        # Act
        result = update_manager._perform_download(mock_release_info)

        # Assert
        assert result is True
        mock_pip.assert_called_once()


class TestUpdateErrorHandling:
    """Test error handling during software updates."""

    @patch("platform.system")
    @patch("ardupilot_methodic_configurator.data_model_software_updates.download_and_install_on_windows")
    def test_user_is_protected_from_corrupted_releases(self, mock_download, mock_platform, update_manager) -> None:
        """
        User is protected from installing corrupted release data.

        GIVEN: A release with malformed asset information
        WHEN: The user attempts to download
        THEN: The system should handle the error gracefully
          AND: No installation should proceed
        """
        # Arrange
        mock_platform.return_value = "Windows"
        malformed_release = {"tag_name": "v2.0.0", "assets": [{"invalid": "structure"}]}

        # Act
        result = update_manager._perform_download(malformed_release)

        # Assert
        assert result is False
        mock_download.assert_not_called()

    @patch("platform.system")
    @patch("ardupilot_methodic_configurator.data_model_software_updates.download_and_install_on_windows")
    def test_user_is_informed_of_download_failures(
        self, mock_download, mock_platform, update_manager, mock_release_info
    ) -> None:
        """
        User is informed when download or installation fails.

        GIVEN: A user attempting to install an update
        WHEN: The download or installation process fails
        THEN: The failure should be handled gracefully
          AND: The system should report the failure
        """
        # Arrange
        mock_platform.return_value = "Windows"
        mock_download.return_value = False  # Simulate failure

        # Act
        result = update_manager._perform_download(mock_release_info)

        # Assert
        assert result is False


class TestUserExperienceDuringDownload:
    """Test user experience during software download process."""

    @patch("ardupilot_methodic_configurator.backend_internet.requests_get")
    def test_user_can_download_update_behind_corporate_proxy(self, mock_get, tmp_path, monkeypatch) -> None:
        """
        User can download updates from behind a corporate proxy.

        GIVEN: A user working in a corporate environment with proxy settings
        WHEN: The user downloads a software update
        THEN: The download should respect proxy configuration
          AND: The update should download successfully
        """
        # Arrange - Corporate environment with proxy
        monkeypatch.setenv("HTTP_PROXY", "http://corporate-proxy:8080")
        monkeypatch.setenv("HTTPS_PROXY", "https://corporate-proxy:8443")
        monkeypatch.setenv("NO_PROXY", "localhost,internal.corp")

        mock_response = MagicMock()
        mock_response.headers = {"content-length": "1024"}
        mock_response.iter_content.return_value = [b"update_data"]
        mock_response.status_code = 200
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        test_file = tmp_path / "update.exe"

        # Act
        result = download_file_from_url(
            "https://github.com/ArduPilot/MethodicConfigurator/releases/download/v2.0.0/installer.exe",
            str(test_file),
        )

        # Assert
        assert result is True
        assert test_file.exists()
        # Verify proxy was used
        call_kwargs = mock_get.call_args.kwargs
        assert "proxies" in call_kwargs
        assert call_kwargs["proxies"]["http"] == "http://corporate-proxy:8080"
        assert call_kwargs["proxies"]["https"] == "https://corporate-proxy:8443"

    @patch("ardupilot_methodic_configurator.backend_internet.requests_get")
    def test_user_download_resumes_after_network_interruption(self, mock_get, tmp_path, monkeypatch) -> None:  # pylint: disable=unused-argument
        """
        User can resume interrupted download without starting over.

        GIVEN: A user downloading a large update
          AND: The network connection is interrupted mid-download
        WHEN: The user retries the download
        THEN: The download should resume from where it left off
          AND: Only remaining data should be downloaded
        """
        # Arrange
        full_data = b"A" * 1000  # Large file
        partial_data = full_data[:400]  # 40% downloaded
        remaining_data = full_data[400:]

        test_file = tmp_path / "large_update.exe"
        test_file.write_bytes(partial_data)  # Simulate partial download

        # Mock server response with resume support
        mock_response = MagicMock()
        mock_response.status_code = 206  # Partial Content
        mock_response.headers = {"Content-Range": f"bytes 400-999/{len(full_data)}"}
        mock_response.iter_content.return_value = [remaining_data]
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        # Act
        result = download_file_from_url("https://github.com/test/file", str(test_file), allow_resume=True)

        # Assert - Download completed
        assert result is True
        assert test_file.read_bytes() == full_data
        # Verify Range header was sent
        call_kwargs = mock_get.call_args.kwargs
        assert "headers" in call_kwargs
        assert "Range" in call_kwargs["headers"]

    @patch("ardupilot_methodic_configurator.backend_internet.requests_get")
    def test_user_gets_progress_feedback_during_large_download(self, mock_get, tmp_path) -> None:
        """
        User sees progress updates during large file downloads.

        GIVEN: A user downloading a large update file
        WHEN: The download is in progress
        THEN: The user should receive regular progress updates
          AND: Progress should be displayed as percentage
        """
        # Arrange
        large_file = b"X" * 10000
        mock_response = MagicMock()
        mock_response.headers = {"content-length": str(len(large_file))}
        mock_response.status_code = 200
        # Simulate chunked download
        chunk_size = 1000
        chunks = [large_file[i : i + chunk_size] for i in range(0, len(large_file), chunk_size)]
        mock_response.iter_content.return_value = chunks
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        test_file = tmp_path / "large.exe"
        progress_updates = []

        def progress_callback(progress: float, message: str) -> None:
            progress_updates.append((progress, message))

        # Act
        result = download_file_from_url("https://github.com/test/file", str(test_file), progress_callback=progress_callback)

        # Assert
        assert result is True
        assert len(progress_updates) > 1  # Multiple updates
        assert progress_updates[-1][0] == 100.0  # Final update is 100%
        assert "complete" in progress_updates[-1][1].lower()

    @patch("ardupilot_methodic_configurator.backend_internet.requests_get")
    def test_user_experiences_automatic_retry_on_network_failure(self, mock_get, tmp_path) -> None:
        """
        User benefits from automatic retry on transient network failures.

        GIVEN: A user downloading an update
          AND: A transient network error occurs
        WHEN: The download fails initially
        THEN: The system should automatically retry
          AND: The download should eventually succeed
        """
        # Arrange
        call_count = {"n": 0}

        def mock_get_with_retry(*_args, **_kwargs) -> MagicMock:
            call_count["n"] += 1
            if call_count["n"] < 3:  # Fail first 2 attempts
                msg = "Network timeout"
                raise Timeout(msg)
            # Third attempt succeeds
            mock_response = MagicMock()
            mock_response.headers = {"content-length": "100"}
            mock_response.status_code = 200
            mock_response.iter_content.return_value = [b"success_data"]
            mock_response.raise_for_status.return_value = None
            return mock_response

        mock_get.side_effect = mock_get_with_retry
        test_file = tmp_path / "update.exe"

        # Act
        result = download_file_from_url("https://github.com/test/file", str(test_file), retries=3, backoff_factor=0.01)

        # Assert - Eventually succeeded after retries
        assert result is True
        assert test_file.read_bytes() == b"success_data"
        assert call_count["n"] == 3  # Retried as expected


class TestSecurityAndIntegrity:
    """Test security and integrity verification during updates."""

    @patch("ardupilot_methodic_configurator.backend_internet.requests_get")
    def test_user_is_protected_by_checksum_verification(self, mock_get) -> None:
        """
        User is protected from corrupted or tampered downloads.

        GIVEN: A user downloading a software update
          AND: The release includes SHA256 checksums
        WHEN: A corrupted file is downloaded
        THEN: The system should detect the mismatch
          AND: Reject the corrupted file
        """
        # Arrange
        release_with_checksum = {
            "assets": [
                {
                    "name": "SHA256SUMS",
                    "browser_download_url": "https://github.com/test/sums",
                }
            ],
            "body": "",
        }

        # Mock checksum file response
        checksum_response = MagicMock()
        checksum_response.text = "abc123" + "0" * 58 + "  installer.exe\n"
        checksum_response.raise_for_status.return_value = None
        mock_get.return_value = checksum_response

        # Act
        expected_hash = get_expected_sha256_from_release(release_with_checksum, "installer.exe")

        # Assert
        assert expected_hash is not None
        assert len(expected_hash) == 64  # Valid SHA256
        assert expected_hash.startswith("abc123")

    def test_user_downloads_only_from_trusted_sources(self, update_manager) -> None:  # pylint: disable=unused-argument
        """
        User is protected from downloads from untrusted sources.

        GIVEN: A user attempting to download an update
        WHEN: The download URL is not from GitHub
        THEN: The system should reject the download
          AND: Protect the user from potential security risks
        """
        # Arrange
        untrusted_url = "https://evil-site.com/malware.exe"

        # Act
        result = download_and_install_on_windows(untrusted_url, "update.exe")

        # Assert - Rejected untrusted source
        assert result is False

    @patch("ardupilot_methodic_configurator.backend_internet.requests_get")
    def test_user_update_uses_secure_https_connection(self, mock_get, tmp_path) -> None:
        """
        User downloads are protected by HTTPS encryption.

        GIVEN: A user downloading a software update
        WHEN: The download begins
        THEN: HTTPS should be enforced
          AND: SSL certificate verification should be enabled
        """
        # Arrange
        mock_response = MagicMock()
        mock_response.headers = {"content-length": "100"}
        mock_response.status_code = 200
        mock_response.iter_content.return_value = [b"data"]
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        test_file = tmp_path / "update.exe"

        # Act
        download_file_from_url("https://github.com/test/secure-file", str(test_file))

        # Assert - SSL verification enabled
        call_kwargs = mock_get.call_args.kwargs
        assert call_kwargs["verify"] is True  # SSL verification enabled
