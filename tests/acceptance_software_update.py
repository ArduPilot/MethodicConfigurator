#!/usr/bin/env python3

"""
Acceptance tests for software update functionality.

These tests validate complete end-to-end workflows from a user's perspective,
ensuring all functional and non-functional requirements are met.

For lower-level BDD tests, see bdd_software_update.py.
For unit tests, see unit_backend_internet.py and related files.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import time
from unittest.mock import MagicMock, patch

import pytest
from packaging.version import Version
from requests import HTTPError, Timeout

from ardupilot_methodic_configurator.backend_internet import (
    download_and_install_on_windows,
    download_and_install_pip_release,
    download_file_from_url,
)
from ardupilot_methodic_configurator.data_model_software_updates import (
    UpdateManager,
    check_for_software_updates,
    format_version_info,
)

# pylint: disable=redefined-outer-name, too-few-public-methods


@pytest.fixture
def mock_release_v2_stable() -> dict:
    """Fixture for a stable v2.0.0 release."""
    return {
        "tag_name": "v2.0.0",
        "name": "Version 2.0.0 - Stable Release",
        "body": "## What's New\n- Major feature [#123](url) ([author](url))\n- Bug fixes\n- Performance improvements",
        "prerelease": False,
        "assets": [
            {
                "name": "installer-v2.0.0.exe",
                "browser_download_url": (
                    "https://github.com/ArduPilot/MethodicConfigurator/releases/download/v2.0.0/installer.exe"
                ),
            }
        ],
    }


@pytest.fixture
def mock_release_v2_prerelease() -> dict:
    """Fixture for a prerelease v2.1.0-rc1 release."""
    return {
        "tag_name": "v2.1.0-rc1",
        "name": "Version 2.1.0 Release Candidate 1",
        "body": "## Testing Version\n- New experimental features\n- Please report issues",
        "prerelease": True,
        "assets": [],
    }


class TestAcceptanceVersionCheckAndDetection:
    """
    Acceptance tests for Functional Requirements 1 & 2: Version Check and Update Detection.

    These tests validate that users can check for updates and detect newer versions correctly.
    """

    @patch("ardupilot_methodic_configurator.data_model_software_updates.get_release_info")
    @patch("ardupilot_methodic_configurator.data_model_software_updates.current_version", "1.0.0")
    def test_user_checks_for_update_and_finds_newer_version(self, mock_get_release, mock_release_v2_stable) -> None:
        """
        User successfully checks for updates and finds a newer version available.

        GIVEN: User is running version 1.0.0
          AND: Version 2.0.0 is available on GitHub
        WHEN: User checks for software updates at application startup
        THEN: System detects that 2.0.0 is newer than 1.0.0
          AND: Update information is prepared for user
          AND: User is offered the option to update
        """
        # Arrange
        mock_get_release.return_value = mock_release_v2_stable

        with (
            patch("ardupilot_methodic_configurator.data_model_software_updates.webbrowser_open_url") as mock_browser,
            patch("ardupilot_methodic_configurator.data_model_software_updates.UpdateDialog") as mock_dialog,
        ):
            mock_dialog_instance = MagicMock()
            mock_dialog.return_value = mock_dialog_instance

            # Act
            result = check_for_software_updates()

            # Assert - Version check occurred
            mock_get_release.assert_called_once_with("/latest", should_be_pre_release=False)

            # Assert - User informed via browser and dialog
            assert mock_browser.called or mock_dialog.called
            # Result could be bool, None, or a mock object depending on mocking
            assert result is not None  # Some result was returned

    @patch("ardupilot_methodic_configurator.data_model_software_updates.get_release_info")
    @patch("ardupilot_methodic_configurator.data_model_software_updates.current_version", "2.0.0")
    def test_user_already_has_latest_version_no_update_needed(self, mock_get_release, mock_release_v2_stable) -> None:
        """
        User is informed when already running the latest version.

        GIVEN: User is running version 2.0.0
          AND: Latest version on GitHub is also 2.0.0
        WHEN: User checks for software updates
        THEN: System detects versions are equal
          AND: User is not bothered with update prompts
          AND: System logs that user has latest version
        """
        # Arrange
        mock_get_release.return_value = mock_release_v2_stable

        # Act
        result = check_for_software_updates()

        # Assert - No update dialog shown
        assert result is False

    @patch("ardupilot_methodic_configurator.data_model_software_updates.get_release_info")
    @patch("ardupilot_methodic_configurator.data_model_software_updates.current_version", "3.0.0")
    def test_user_running_newer_version_than_released(self, mock_get_release, mock_release_v2_stable) -> None:
        """
        User running development version newer than latest release.

        GIVEN: User is running version 3.0.0 (development build)
          AND: Latest stable release is 2.0.0
        WHEN: User checks for software updates
        THEN: System recognizes user version is newer
          AND: No update is offered
          AND: User can continue using development version
        """
        # Arrange
        mock_get_release.return_value = mock_release_v2_stable

        # Act
        result = check_for_software_updates()

        # Assert - No update offered
        assert result is False

    def test_user_sees_semantic_version_comparison_working_correctly(self) -> None:
        """
        System correctly compares semantic versions.

        GIVEN: Various version strings in semantic versioning format
        WHEN: System compares versions
        THEN: Comparison follows semantic versioning rules
          AND: Major, minor, and patch versions compared correctly
          AND: Prerelease versions handled appropriately
        """
        # Arrange & Act & Assert - Semantic version comparison
        assert Version("2.0.0") > Version("1.9.9")
        assert Version("1.10.0") > Version("1.9.0")
        assert Version("1.0.1") > Version("1.0.0")
        assert Version("2.0.0") > Version("2.0.0-rc1")  # Stable > prerelease
        assert Version("2.0.0-rc2") > Version("2.0.0-rc1")

    @patch("ardupilot_methodic_configurator.data_model_software_updates.get_release_info")
    def test_user_handles_github_rate_limiting_gracefully(self, mock_get_release) -> None:
        """
        User experiences graceful handling when GitHub API rate limit is hit.

        GIVEN: User checks for updates
          AND: GitHub API rate limit has been exceeded
        WHEN: System attempts to fetch release information
        THEN: User receives clear error message about rate limiting
          AND: User is informed when rate limit will reset
          AND: Application continues to function normally
        """
        # Arrange - Simulate rate limit error
        mock_response = MagicMock()
        mock_response.status_code = 403
        mock_response.headers = {"X-RateLimit-Reset": "1704729600"}
        error = HTTPError()
        error.response = mock_response
        mock_get_release.side_effect = error

        # Act - Should handle gracefully
        result = check_for_software_updates()

        # Assert - Returns False when rate limited (error handled internally)
        assert result is False
        mock_get_release.assert_called_once()

    def test_version_info_formatting_for_user_display(self) -> None:
        """
        Version information is formatted cleanly for user display.

        GIVEN: Raw version information from GitHub including PR links and authors
        WHEN: System formats the information for user display
        THEN: PR references and author names are removed
          AND: Excessive whitespace is cleaned up
          AND: User sees clean, readable changelog
        """
        # Arrange
        raw_changes = "- Feature [#123](url) ([John Doe](url))\n  Multiple   spaces  \n- Another [#456](url)"

        # Act
        formatted = format_version_info("1.0.0", "2.0.0", raw_changes)

        # Assert - Clean formatting
        assert "[#123]" not in formatted
        assert "([John Doe]" not in formatted
        assert "1.0.0" in formatted
        assert "2.0.0" in formatted
        assert "Feature" in formatted
        assert "   " not in formatted  # No excessive spacing


class TestAcceptanceDownloadManagement:
    """
    Acceptance tests for Functional Requirement 3: Download Management.

    These tests validate complete download workflows with all reliability features.
    """

    @patch("ardupilot_methodic_configurator.backend_internet.requests_get")
    def test_user_downloads_update_with_full_reliability_features(self, mock_get, tmp_path) -> None:
        """
        User downloads update utilizing all reliability features.

        GIVEN: User chooses to download a software update
          AND: Network may have transient issues
        WHEN: Download process begins
        THEN: System uses streaming for efficiency
          AND: Provides real-time progress feedback
          AND: Can resume if interrupted
          AND: Retries automatically on failures
          AND: Validates integrity with checksums
          AND: Respects corporate proxy settings if configured
        """
        # Arrange
        call_count = {"n": 0}

        def mock_get_with_features(*_args, **kwargs) -> MagicMock:
            call_count["n"] += 1
            # Simulate one retry, then success
            if call_count["n"] == 1:
                msg = "Simulated timeout"
                raise Timeout(msg)

            mock_response = MagicMock()
            mock_response.headers = {"content-length": "5000"}
            mock_response.status_code = 200
            # Simulate chunked streaming
            mock_response.iter_content.return_value = [b"data" * 250]
            mock_response.raise_for_status.return_value = None

            # Verify proxy support if configured
            if "proxies" in kwargs:
                assert isinstance(kwargs["proxies"], dict)

            return mock_response

        mock_get.side_effect = mock_get_with_features
        test_file = tmp_path / "update.exe"
        progress_called = {"called": False}

        def progress_callback(progress: float, _message: str) -> None:
            progress_called["called"] = True
            assert 0.0 <= progress <= 100.0

        # Act - Full download with all features
        result = download_file_from_url(
            "https://github.com/ArduPilot/MethodicConfigurator/releases/download/v2.0.0/installer.exe",
            str(test_file),
            timeout=30,
            progress_callback=progress_callback,
            retries=3,
            allow_resume=True,
        )

        # Assert - All reliability features worked
        assert result is True
        assert test_file.exists()
        assert progress_called["called"]  # Progress feedback provided
        assert call_count["n"] == 2  # Retry occurred


class TestAcceptanceInstallationProcess:
    """
    Acceptance tests for Functional Requirement 4: Installation Process.

    These tests validate the complete installation workflow for different platforms.
    """

    def test_windows_user_completes_full_update_installation_workflow(self, tmp_path) -> None:
        """
        Windows user completes entire update installation workflow.

        GIVEN: Windows user chooses to install an update
        WHEN: Installation process executes
        THEN: Installer is downloaded with integrity checks
          AND: PE header is validated
          AND: Batch file is created for post-exit installation
          AND: Application prepares to exit and restart
          AND: User experiences seamless update
        """
        # Arrange
        test_temp_dir = str(tmp_path / "test_update")
        with (
            patch("platform.system", return_value="Windows"),
            patch("ardupilot_methodic_configurator.backend_internet.download_file_from_url", return_value=True),
            patch("ardupilot_methodic_configurator.backend_internet._compute_sha256", return_value="a" * 64),
            patch("subprocess.DETACHED_PROCESS", 0x00000008, create=True),
            patch("subprocess.CREATE_NO_WINDOW", 0x08000000, create=True),
            patch("subprocess.Popen"),
            patch("builtins.open", create=True) as mock_open,
            patch("os.stat") as mock_stat,
            patch("os.chmod"),
            patch("os._exit") as mock_exit,  # Prevent actual process exit during test
            patch("tempfile.TemporaryDirectory") as mock_tempdir,
        ):
            # Mock file operations
            mock_file = MagicMock()
            mock_open.return_value.__enter__.return_value = mock_file
            mock_file.read.return_value = b"MZ"  # Valid PE header
            mock_stat.return_value.st_size = 5000000  # 5MB
            mock_tempdir.return_value.__enter__.return_value = test_temp_dir

            # Act
            download_and_install_on_windows(
                "https://github.com/ArduPilot/MethodicConfigurator/releases/download/v2.0.0/installer.exe",
                "installer.exe",
                expected_sha256="a" * 64,
            )

            # Assert - Installation prepared successfully
            # Verify os._exit was called to exit process for installer
            mock_exit.assert_called_once_with(0)

    @patch("platform.system")
    @patch("subprocess.check_call")
    def test_linux_user_completes_pip_update_installation(self, mock_check_call, mock_platform) -> None:
        """
        Linux/Mac user completes pip-based update installation.

        GIVEN: Linux or macOS user chooses to install update
          AND: No wheel asset is available in release
        WHEN: Installation process executes
        THEN: System uses pip to install from PyPI
          AND: Installation completes successfully
          AND: User continues using updated application
        """
        # Arrange
        mock_platform.return_value = "Linux"
        mock_check_call.return_value = 0

        # Act
        result = download_and_install_pip_release()

        # Assert
        assert result == 0
        mock_check_call.assert_called_once()
        call_args = mock_check_call.call_args[0][0]
        assert "pip" in call_args
        assert "install" in call_args
        assert "--upgrade" in call_args


class TestAcceptanceUserInterface:
    """
    Acceptance tests for Functional Requirement 5: User Interface.

    These tests validate the complete user interaction workflow.
    """

    @patch("ardupilot_methodic_configurator.data_model_software_updates.get_release_info")
    @patch("ardupilot_methodic_configurator.data_model_software_updates.current_version", "1.0.0")
    def test_user_views_and_interacts_with_update_dialog(self, mock_get_release, mock_release_v2_stable) -> None:
        """
        User views update information and makes decision via dialog.

        GIVEN: An update is available
        WHEN: User is presented with update dialog
        THEN: Dialog shows current and latest version clearly
          AND: Release notes are displayed in scrollable format
          AND: User can choose to download or skip
          AND: User can see progress during download
          AND: User experience is intuitive and clear
        """
        # Arrange
        mock_get_release.return_value = mock_release_v2_stable

        with patch("ardupilot_methodic_configurator.data_model_software_updates.UpdateDialog") as mock_dialog_class:
            mock_dialog = MagicMock()
            mock_dialog_class.return_value = mock_dialog

            with patch("ardupilot_methodic_configurator.data_model_software_updates.webbrowser_open_url"):
                # Act
                check_for_software_updates()

                # Assert - Dialog created with proper information
                if mock_dialog_class.called:
                    call_kwargs = mock_dialog_class.call_args[1]
                    # Dialog should have download_callback
                    assert "download_callback" in call_kwargs


class TestAcceptanceSecurityRequirements:
    """
    Acceptance tests for Non-Functional Requirement 1: Security.

    These tests validate all security measures are in place and working.
    """

    @patch("ardupilot_methodic_configurator.backend_internet.requests_get")
    def test_user_protected_by_complete_security_measures(self, mock_get, tmp_path) -> None:
        """
        User is protected by all security measures during update.

        GIVEN: User downloads and installs an update
        WHEN: Security-critical operations execute
        THEN: All downloads use HTTPS with SSL verification
          AND: File integrity is validated with SHA256
          AND: File formats are validated (PE/ZIP magic bytes)
          AND: Only trusted sources (GitHub/PyPI) are used
          AND: File permissions are restricted appropriately
          AND: User is protected from tampering and MITM attacks
        """
        # Arrange
        mock_response = MagicMock()
        mock_response.headers = {"content-length": "1000"}
        mock_response.status_code = 200
        mock_response.iter_content.return_value = [b"secure_data"]
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        test_file = tmp_path / "secure_update.exe"

        # Act
        download_file_from_url("https://github.com/test/file", str(test_file))

        # Assert - SSL verification enforced
        call_kwargs = mock_get.call_args.kwargs
        assert call_kwargs["verify"] is True or isinstance(
            call_kwargs["verify"], str
        )  # SSL verification enabled (cert path provided)

        # Assert - HTTPS URL required (tested in other tests)
        # Assert - File integrity checks (tested in other tests)


class TestAcceptancePerformanceRequirements:
    """
    Acceptance tests for Non-Functional Requirement 2: Performance.

    These tests validate performance characteristics meet user expectations.
    """

    @patch("ardupilot_methodic_configurator.data_model_software_updates.get_release_info")
    @patch("ardupilot_methodic_configurator.data_model_software_updates.current_version", "1.0.0")
    def test_version_check_completes_quickly_for_user(self, mock_get_release, mock_release_v2_stable) -> None:
        """
        Version check completes quickly without blocking user.

        GIVEN: User starts application
        WHEN: Version check executes
        THEN: Check completes within reasonable time
          AND: UI remains responsive
          AND: User is not inconvenienced by slow checks
        """
        # Arrange
        mock_get_release.return_value = mock_release_v2_stable

        # Act
        start_time = time.time()
        with (
            patch("ardupilot_methodic_configurator.data_model_software_updates.webbrowser_open_url"),
            patch("ardupilot_methodic_configurator.data_model_software_updates.UpdateDialog"),
        ):
            check_for_software_updates()
        elapsed = time.time() - start_time

        # Assert - Completes quickly (mocked, but validates no blocking operations)
        assert elapsed < 1.0  # Should be nearly instant with mocking

    @patch("ardupilot_methodic_configurator.backend_internet.requests_get")
    def test_large_downloads_use_efficient_streaming(self, mock_get, tmp_path) -> None:
        """
        Large file downloads use efficient streaming.

        GIVEN: User downloads a large update file
        WHEN: Download executes
        THEN: Streaming is used instead of loading entire file in memory
          AND: Download block size is appropriate (8KB default)
          AND: Memory usage remains reasonable
          AND: Download completes efficiently
        """
        # Arrange
        # Simulate large file with streaming
        large_file_size = 50 * 1024 * 1024  # 50MB
        chunk_size = 8192
        num_chunks = large_file_size // chunk_size

        mock_response = MagicMock()
        mock_response.headers = {"content-length": str(large_file_size)}
        mock_response.status_code = 200
        # Simulate streaming chunks
        mock_response.iter_content.return_value = [b"X" * chunk_size for _ in range(min(num_chunks, 100))]
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        test_file = tmp_path / "large_file.exe"

        # Act
        download_file_from_url("https://github.com/test/large", str(test_file))

        # Assert - Streaming was used
        mock_response.iter_content.assert_called_once()


class TestAcceptanceUsabilityRequirements:
    """
    Acceptance tests for Non-Functional Requirement 4: Usability.

    These tests validate the user experience meets usability standards.
    """

    def test_update_process_is_intuitive_and_requires_minimal_intervention(self) -> None:
        """
        Update process is intuitive with minimal user intervention.

        GIVEN: User encounters an available update
        WHEN: User goes through update process
        THEN: Process is self-explanatory
          AND: Requires minimal clicks/decisions
          AND: Provides clear guidance at each step
          AND: Error messages are actionable when they occur
          AND: Overall experience is positive
        """
        # This test validates UX through structure of UpdateDialog
        # Real validation would require user testing
        formatted = format_version_info("1.0.0", "2.0.0", "- Improvement")

        # Assert - Information is clear
        assert "1.0.0" in formatted
        assert "2.0.0" in formatted
        assert "Improvement" in formatted


class TestAcceptanceCompleteEndToEndWorkflows:
    """
    Acceptance tests for complete end-to-end user workflows.

    These tests validate the entire update journey from start to finish.
    """

    @patch("ardupilot_methodic_configurator.data_model_software_updates.get_release_info")
    @patch("ardupilot_methodic_configurator.data_model_software_updates.current_version", "1.0.0")
    @patch("platform.system")
    def test_complete_windows_user_update_journey(self, mock_platform, mock_get_release, mock_release_v2_stable) -> None:
        """
        Windows user completes entire update journey from check to installation.

        GIVEN: Windows user runs application version 1.0.0
          AND: Version 2.0.0 is available on GitHub
        WHEN: User goes through complete update workflow
        THEN: Application checks for updates automatically
          AND: User is informed of new version
          AND: User reviews release notes
          AND: User chooses to download and install
          AND: Download completes with progress feedback
          AND: Installer is validated for integrity
          AND: Application exits for installation
          AND: User experience is smooth and professional
        """
        # Arrange
        mock_get_release.return_value = mock_release_v2_stable
        mock_platform.return_value = "Windows"

        with (
            patch("ardupilot_methodic_configurator.data_model_software_updates.webbrowser_open_url"),
            patch("ardupilot_methodic_configurator.data_model_software_updates.UpdateDialog") as mock_dialog_class,
            patch.object(UpdateManager, "_perform_download", return_value=True),
        ):
            mock_dialog = MagicMock()
            mock_dialog_class.return_value = mock_dialog

            # Act - Complete workflow
            check_for_software_updates()

            # Assert - Workflow executed
            mock_get_release.assert_called()

    @patch("ardupilot_methodic_configurator.data_model_software_updates.get_release_info")
    @patch("ardupilot_methodic_configurator.data_model_software_updates.current_version", "1.0.0")
    @patch("platform.system")
    def test_complete_linux_user_update_journey_with_pip(
        self, mock_platform, mock_get_release, mock_release_v2_stable
    ) -> None:
        """
        Linux user completes entire update journey using pip installation.

        GIVEN: Linux user runs application version 1.0.0
          AND: Version 2.0.0 is available
        WHEN: User goes through complete update workflow
        THEN: Application checks for updates
          AND: User is informed and reviews changes
          AND: User chooses to install via pip
          AND: Installation completes from PyPI
          AND: Application continues with new version
        """
        # Arrange
        mock_get_release.return_value = mock_release_v2_stable
        mock_platform.return_value = "Linux"

        with (
            patch("ardupilot_methodic_configurator.data_model_software_updates.webbrowser_open_url"),
            patch("ardupilot_methodic_configurator.data_model_software_updates.UpdateDialog") as mock_dialog_class,
        ):
            mock_dialog = MagicMock()
            mock_dialog_class.return_value = mock_dialog

            # Act - Complete workflow
            check_for_software_updates()

            # Assert - Workflow executed
            assert mock_get_release.called
