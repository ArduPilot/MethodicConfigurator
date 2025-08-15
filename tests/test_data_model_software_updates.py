#!/usr/bin/env python3

"""
Tests for data_model_software_updates.py.

This file is part of Ardupilot methodic configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2025 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

from argparse import ArgumentParser
from unittest.mock import Mock, patch

import pytest
from requests import RequestException as requests_RequestException

from ardupilot_methodic_configurator import _
from ardupilot_methodic_configurator.data_model_software_updates import (
    UpdateManager,
    check_for_software_updates,
    format_version_info,
)

# pylint: disable=redefined-outer-name, protected-access


@pytest.fixture
def mock_dialog() -> Mock:
    dialog = Mock()
    dialog.show.return_value = True
    dialog.update_progress = Mock()
    return dialog


@pytest.fixture
def update_manager() -> UpdateManager:
    return UpdateManager()


class TestUpdateManager:
    """Test cases for the UpdateManager class."""

    def test_format_version_info(self) -> None:
        result = format_version_info("1.0.0", "2.0.0", "Test changes")
        assert "1.0.0" in result
        assert "2.0.0" in result
        assert "Test changes" in result

    def test_check_and_update_same_version(self, update_manager) -> None:  # pylint: disable=redefined-outer-name
        latest_release = {"tag_name": "v1.0.0"}
        current_version = "1.0.0"

        assert not update_manager.check_and_update(latest_release, current_version)

    def test_check_and_update_key_error(self, update_manager) -> None:  # pylint: disable=redefined-outer-name
        latest_release = {}
        current_version = "1.0.0"

        with patch("ardupilot_methodic_configurator.data_model_software_updates.logging_error") as mock_logging_error:
            assert not update_manager.check_and_update(latest_release, current_version)
            mock_logging_error.assert_called_once()

    def test_check_and_update_value_error(self, update_manager) -> None:  # pylint: disable=redefined-outer-name
        latest_release = {"tag_name": "v2.0.0"}
        current_version = "1.0.0"

        with (
            patch(
                "ardupilot_methodic_configurator.data_model_software_updates.format_version_info",
                side_effect=ValueError,
            ),
            patch("ardupilot_methodic_configurator.data_model_software_updates.logging_error") as mock_logging_error,
        ):
            assert not update_manager.check_and_update(latest_release, current_version)
            mock_logging_error.assert_called_once()


def test_format_version_info_pr_removal() -> None:
    changes = "Feature [#123) Added test\nBug [#456) Fixed issue"
    result = format_version_info("1.0.0", "2.0.0", changes)
    assert "[#123)" not in result
    assert "[#456)" not in result
    assert "Added test" in result
    assert "Fixed issue" in result


def test_format_version_info_author_removal() -> None:
    changes = "Feature ([author)) Added test\nBug ([contributor)) Fixed issue"
    result = format_version_info("1.0.0", "2.0.0", changes)
    assert "([author))" not in result
    assert "([contributor))" not in result


def test_format_version_info_complex_changes() -> None:
    changes = "Feature [#123)([author)) Multiple tags\nBug [#456)([contributor)) Mixed content"
    result = format_version_info("1.0.0", "2.0.0", changes)
    assert "[#123)" not in result
    assert "[#456)" not in result
    assert "([author))" not in result
    assert "([contributor))" not in result
    assert "Multiple tags" in result
    assert "Mixed content" in result


def test_format_version_info_empty_changes() -> None:
    result = format_version_info("1.0.0", "2.0.0", "")
    assert "Current version: 1.0.0" in result
    assert "Latest version: 2.0.0" in result
    assert "Changes:" in result


def test_format_version_info_special_chars() -> None:
    changes = "Feature ([#123]) Added *special* characters\nBug ([#456]) with $symbols%"
    result = format_version_info("1.0.0", "2.0.0", changes)
    assert "*special*" in result
    assert "$symbols%" in result


def test_format_version_info_basic() -> None:
    result = format_version_info("1.0.0", "2.0.0", "Simple change")
    expected = (
        # pylint: disable=duplicate-code
        _("Current version: {_current_version}")
        + "\n"
        + _("Latest version: {_latest_release}")
        + "\n\n"
        + _("Changes:\n{changes}")
        # pylint: enable=duplicate-code
    ).format(_current_version="1.0.0", _latest_release="2.0.0", changes="Simple change")
    assert result == expected


def test_format_version_info_newlines() -> None:
    result = format_version_info("1.0.0", "2.0.0", "Change 1\nChange 2")
    expected = (
        # pylint: disable=duplicate-code
        _("Current version: {_current_version}")
        + "\n"
        + _("Latest version: {_latest_release}")
        + "\n\n"
        + _("Changes:\n{changes}")
        # pylint: enable=duplicate-code
    ).format(_current_version="1.0.0", _latest_release="2.0.0", changes="Change 1\nChange 2")
    assert result == expected


def test_format_version_info_empty() -> None:
    result = format_version_info("1.0.0", "2.0.0", "")
    assert "Current version: 1.0.0" in result
    assert "Latest version: 2.0.0" in result
    assert "Changes:" in result


def test_format_version_info_pr_references() -> None:
    changes = "Feature [#123) Test\nBug [#456) Fix"
    result = format_version_info("1.0.0", "2.0.0", changes)
    assert "[#123)" not in result
    assert "[#456)" not in result
    assert "Feature Test" in result
    assert "Bug Fix" in result


def test_format_version_info_malformed_refs() -> None:
    changes = "Feature [#123 Test\nBug (#456)] Fix"
    result = format_version_info("1.0.0", "2.0.0", changes)
    assert "Feature" in result
    assert "Bug" in result
    assert "Test" in result
    assert "Fix" in result


def test_check_for_software_updates_success() -> None:
    """Test successful software update check."""
    mock_release = {"tag_name": "v2.0.0", "body": "Test changes"}

    with (
        patch("ardupilot_methodic_configurator.data_model_software_updates.get_release_info", return_value=mock_release),
        patch(
            "ardupilot_methodic_configurator.data_model_software_updates.LocalFilesystem.get_git_commit_hash",
            return_value="abc123",
        ),
        patch("ardupilot_methodic_configurator.data_model_software_updates.UpdateManager.check_and_update", return_value=True),
        patch("ardupilot_methodic_configurator.data_model_software_updates.logging_info"),
    ):
        assert check_for_software_updates() is True


def test_check_for_software_updates_network_error() -> None:
    """Test software update check with network error."""
    with (
        patch(
            "ardupilot_methodic_configurator.data_model_software_updates.get_release_info",
            side_effect=requests_RequestException("Network error"),
        ),
        patch(
            "ardupilot_methodic_configurator.data_model_software_updates.LocalFilesystem.get_git_commit_hash",
            return_value="abc123",
        ),
        patch("ardupilot_methodic_configurator.data_model_software_updates.logging_info"),
        patch("ardupilot_methodic_configurator.data_model_software_updates.logging_error") as mock_logging_error,
    ):
        assert check_for_software_updates() is False
        mock_logging_error.assert_called_once()


def test_update_manager_newer_version(update_manager) -> None:  # pylint: disable=redefined-outer-name
    """Test update manager with newer version available."""
    latest_release = {"tag_name": "v2.0.0", "body": "New features"}
    current_version = "1.0.0"

    with (
        patch("ardupilot_methodic_configurator.data_model_software_updates.webbrowser_open"),
        patch("ardupilot_methodic_configurator.data_model_software_updates.UpdateDialog") as mock_update_dialog_class,
        patch("ardupilot_methodic_configurator.data_model_software_updates.logging_info"),
    ):
        mock_dialog = Mock()
        mock_dialog.show.return_value = True
        mock_update_dialog_class.return_value = mock_dialog

        assert update_manager.check_and_update(latest_release, current_version) is True
        mock_update_dialog_class.assert_called_once()
        mock_dialog.show.assert_called_once()


def test_update_manager_perform_download_windows_success(update_manager, mock_dialog) -> None:  # pylint: disable=redefined-outer-name
    """Test successful download on Windows."""
    update_manager.dialog = mock_dialog
    latest_release = {"assets": [{"browser_download_url": "https://example.com/file.exe", "name": "file.exe"}]}

    with (
        patch("ardupilot_methodic_configurator.data_model_software_updates.platform.system", return_value="Windows"),
        patch(
            "ardupilot_methodic_configurator.data_model_software_updates.download_and_install_on_windows", return_value=True
        ),
    ):
        assert update_manager._perform_download(latest_release) is True


def test_update_manager_perform_download_windows_error(update_manager, mock_dialog) -> None:  # pylint: disable=redefined-outer-name
    """Test failed download on Windows due to missing assets."""
    update_manager.dialog = mock_dialog
    latest_release = {"assets": []}

    with (
        patch("ardupilot_methodic_configurator.data_model_software_updates.platform.system", return_value="Windows"),
        patch("ardupilot_methodic_configurator.data_model_software_updates.logging_error") as mock_logging_error,
    ):
        assert update_manager._perform_download(latest_release) is False
        mock_logging_error.assert_called_once()


def test_update_manager_perform_download_linux(update_manager, mock_dialog) -> None:  # pylint: disable=redefined-outer-name
    """Test download on Linux."""
    update_manager.dialog = mock_dialog
    latest_release = {}

    with (
        patch("ardupilot_methodic_configurator.data_model_software_updates.platform.system", return_value="Linux"),
        patch("ardupilot_methodic_configurator.data_model_software_updates.download_and_install_pip_release", return_value=0),
    ):
        assert update_manager._perform_download(latest_release) is True


def test_update_manager_perform_download_no_dialog(update_manager) -> None:  # pylint: disable=redefined-outer-name
    """Test download with no dialog."""
    latest_release = {"assets": [{"browser_download_url": "url", "name": "name"}]}

    with (
        patch("ardupilot_methodic_configurator.data_model_software_updates.platform.system", return_value="Windows"),
        patch(
            "ardupilot_methodic_configurator.data_model_software_updates.download_and_install_on_windows", return_value=True
        ),
    ):
        assert update_manager._perform_download(latest_release) is True


def test_update_manager_network_error(update_manager) -> None:  # pylint: disable=redefined-outer-name
    """Test network error during update check."""
    latest_release = {"tag_name": "v2.0.0"}
    current_version = "1.0.0"

    with (
        patch(
            "ardupilot_methodic_configurator.data_model_software_updates.format_version_info",
            side_effect=requests_RequestException("Network error"),
        ),
        patch("ardupilot_methodic_configurator.data_model_software_updates.logging_error") as mock_logging_error,
    ):
        assert not update_manager.check_and_update(latest_release, current_version)
        mock_logging_error.assert_called_once()


def test_update_manager_add_argparse_arguments() -> None:
    """Test adding command line arguments."""
    parser = ArgumentParser()
    result = UpdateManager.add_argparse_arguments(parser)

    # Check that the parser has our argument
    found = False
    for action in result._actions:
        if action.dest == "skip_check_for_updates":
            found = True
            break

    assert found is True


def test_update_manager_check_and_update_older_version(update_manager) -> None:  # pylint: disable=redefined-outer-name
    """Test update manager with older version available (should not update)."""
    latest_release = {"tag_name": "v0.9.0", "body": "Old features"}
    current_version = "1.0.0"

    with patch("ardupilot_methodic_configurator.data_model_software_updates.logging_info") as mock_logging_info:
        assert update_manager.check_and_update(latest_release, current_version) is False
        mock_logging_info.assert_called_once()


def test_update_manager_check_and_update_user_cancels(update_manager) -> None:  # pylint: disable=redefined-outer-name
    """Test when user cancels the update dialog."""
    latest_release = {"tag_name": "v2.0.0", "body": "New features"}
    current_version = "1.0.0"

    with (
        patch("ardupilot_methodic_configurator.data_model_software_updates.webbrowser_open"),
        patch("ardupilot_methodic_configurator.data_model_software_updates.UpdateDialog") as mock_update_dialog_class,
    ):
        mock_dialog = Mock()
        mock_dialog.show.return_value = False  # User cancels the dialog
        mock_update_dialog_class.return_value = mock_dialog

        assert update_manager.check_and_update(latest_release, current_version) is False
        mock_update_dialog_class.assert_called_once()


def test_update_manager_perform_download_linux_failure(update_manager, mock_dialog) -> None:  # pylint: disable=redefined-outer-name
    """Test failed download on Linux."""
    update_manager.dialog = mock_dialog
    latest_release = {}

    with (
        patch("ardupilot_methodic_configurator.data_model_software_updates.platform.system", return_value="Linux"),
        patch(
            "ardupilot_methodic_configurator.data_model_software_updates.download_and_install_pip_release", return_value=1
        ),  # Non-zero exit code
    ):
        assert update_manager._perform_download(latest_release) is False


def test_update_manager_perform_download_mac(update_manager, mock_dialog) -> None:  # pylint: disable=redefined-outer-name
    """Test download on macOS."""
    update_manager.dialog = mock_dialog
    latest_release = {}

    with (
        patch("ardupilot_methodic_configurator.data_model_software_updates.platform.system", return_value="Darwin"),
        patch("ardupilot_methodic_configurator.data_model_software_updates.download_and_install_pip_release", return_value=0),
    ):
        assert update_manager._perform_download(latest_release) is True


def test_check_for_software_updates_value_error() -> None:
    """Test software update check with ValueError."""
    with (
        patch(
            "ardupilot_methodic_configurator.data_model_software_updates.get_release_info",
            side_effect=ValueError("Format error"),
        ),
        patch(
            "ardupilot_methodic_configurator.data_model_software_updates.LocalFilesystem.get_git_commit_hash",
            return_value="abc123",
        ),
        patch("ardupilot_methodic_configurator.data_model_software_updates.logging_info"),
        patch("ardupilot_methodic_configurator.data_model_software_updates.logging_error") as mock_logging_error,
    ):
        assert check_for_software_updates() is False
        mock_logging_error.assert_called_once()


def test_update_manager_malformed_tag_name(update_manager) -> None:  # pylint: disable=redefined-outer-name
    """Test handling of malformed version tag."""
    latest_release = {"tag_name": "not_a_version"}
    current_version = "1.0.0"

    with patch("ardupilot_methodic_configurator.data_model_software_updates.logging_error") as mock_logging_error:
        assert not update_manager.check_and_update(latest_release, current_version)
        mock_logging_error.assert_called_once()


def test_update_manager_check_and_update_equal_versions(update_manager) -> None:  # pylint: disable=redefined-outer-name
    """Test when versions are exactly equal."""
    latest_release = {"tag_name": "v1.0.0", "body": "Same features"}
    current_version = "1.0.0"

    with patch("ardupilot_methodic_configurator.data_model_software_updates.logging_info") as mock_logging_info:
        assert not update_manager.check_and_update(latest_release, current_version)
        mock_logging_info.assert_called_once()


def test_format_version_info_multiple_whitespace() -> None:
    """Test that multiple whitespace is cleaned up in the changes text."""
    changes = "Feature    with    extra    spaces\nBug     fix     with     spaces"
    result = format_version_info("1.0.0", "2.0.0", changes)

    assert "Feature with extra spaces" in result
    assert "Bug fix with spaces" in result
    assert "    " not in result  # No groups of multiple spaces


def test_update_manager_with_complex_release_data(update_manager) -> None:  # pylint: disable=redefined-outer-name
    """Test update manager with a realistic GitHub release API response."""
    complex_release = {
        "url": "https://api.github.com/repos/ArduPilot/MethodicConfigurator/releases/12345678",
        "html_url": "https://github.com/ArduPilot/MethodicConfigurator/releases/tag/v2.0.0",
        "tag_name": "v2.0.0",
        "name": "Version 2.0.0",
        "prerelease": False,
        "created_at": "2024-04-01T12:00:00Z",
        "published_at": "2024-04-01T12:30:00Z",
        "body": (
            "## What's New\n"
            "* Feature: Added new capability\n"
            "* Fix: Resolved critical issue\n"
            "* Enhancement: Improved performance\n\n"
            "## Contributors\n"
            "* Developer1\n"
            "* Developer2"
        ),
        "assets": [
            {
                "url": "https://api.github.com/repos/ArduPilot/MethodicConfigurator/releases/assets/12345678",
                "id": 12345678,
                "name": "methodic_configurator_2.0.0_setup.exe",
                "label": "Windows Installer",
                "content_type": "application/x-msdownload",
                "state": "uploaded",
                "size": 15000000,
                "browser_download_url": (
                    "https://github.com/ArduPilot/MethodicConfigurator/releases/download/"
                    "v2.0.0/methodic_configurator_2.0.0_setup.exe"
                ),
            },
            {
                "url": "https://api.github.com/repos/ArduPilot/MethodicConfigurator/releases/assets/12345679",
                "id": 12345679,
                "name": "methodic_configurator-2.0.0.tar.gz",
                "label": "Source Code",
                "content_type": "application/gzip",
                "state": "uploaded",
                "size": 5000000,
                "browser_download_url": (
                    "https://github.com/ArduPilot/MethodicConfigurator/releases/download/"
                    "v2.0.0/methodic_configurator-2.0.0.tar.gz"
                ),
            },
        ],
    }
    current_version = "1.0.0"

    with (
        patch("ardupilot_methodic_configurator.data_model_software_updates.webbrowser_open"),
        patch("ardupilot_methodic_configurator.data_model_software_updates.UpdateDialog") as mock_update_dialog_class,
    ):
        mock_dialog = Mock()
        mock_dialog.show.return_value = True
        mock_update_dialog_class.return_value = mock_dialog

        assert update_manager.check_and_update(complex_release, current_version) is True

        # Verify the dialog was created with expected change information
        call_args = mock_update_dialog_class.call_args[0][0]
        assert "Version 2.0.0" not in call_args  # Title should not be included
        assert "What's New" in call_args
        assert "Added new capability" in call_args
        assert "Resolved critical issue" in call_args
        assert "Improved performance" in call_args
        assert "Contributors" in call_args
        # Developer names should be in the text, they're not in PR/author format
        assert "Developer1" in call_args
        assert "Developer2" in call_args


def test_update_manager_with_prerelease_versions(update_manager) -> None:  # pylint: disable=redefined-outer-name
    """Test with prerelease version numbers."""
    test_cases = [
        # [latest_version, current_version, should_update]
        ["v2.0.0-beta.1", "1.0.0", True],  # Beta is newer than stable
        ["v2.0.0-rc.1", "2.0.0-beta.2", True],  # RC is newer than beta
        ["v2.0.0", "2.0.0-rc.1", True],  # Stable is newer than RC
        ["v1.0.0-rc.1", "1.0.0", False],  # Stable is newer than RC
        ["v1.2.3-alpha.1", "1.2.3-alpha.0", True],  # Alpha.1 is newer than alpha.0
    ]

    for latest, current, should_update in test_cases:
        latest_release = {"tag_name": latest, "body": f"Test changes for {latest}"}

        if should_update:
            # Test path where update should happen
            with (
                patch("ardupilot_methodic_configurator.data_model_software_updates.webbrowser_open") as mock_browser,
                patch(
                    "ardupilot_methodic_configurator.data_model_software_updates.UpdateDialog",
                    return_value=Mock(show=lambda: True),
                ),
            ):
                result = update_manager.check_and_update(latest_release, current)
                assert result is True, f"Failed with latest={latest}, current={current}"
                mock_browser.assert_called()
        else:
            # Test path where update should NOT happen
            with patch("ardupilot_methodic_configurator.data_model_software_updates.logging_info") as mock_info:
                result = update_manager.check_and_update(latest_release, current)
                assert result is False, f"Failed with latest={latest}, current={current}"
                mock_info.assert_called()


def test_update_manager_perform_download_windows_exception(update_manager, mock_dialog) -> None:  # pylint: disable=redefined-outer-name
    """Test exception during Windows download."""
    update_manager.dialog = mock_dialog
    latest_release = {"assets": [{"browser_download_url": "https://example.com/file.exe", "name": "file.exe"}]}

    with (
        patch("ardupilot_methodic_configurator.data_model_software_updates.platform.system", return_value="Windows"),
        patch(
            "ardupilot_methodic_configurator.data_model_software_updates.download_and_install_on_windows",
            side_effect=Exception("Download failed"),
        ),
        patch("ardupilot_methodic_configurator.data_model_software_updates.logging_error") as mock_logging_error,
    ):
        assert update_manager._perform_download(latest_release) is False
        mock_logging_error.assert_called_once()


def test_update_manager_perform_download_pip_exception(update_manager, mock_dialog) -> None:  # pylint: disable=redefined-outer-name
    """Test exception during pip download."""
    update_manager.dialog = mock_dialog
    latest_release = {}

    with (
        patch("ardupilot_methodic_configurator.data_model_software_updates.platform.system", return_value="Linux"),
        patch(
            "ardupilot_methodic_configurator.data_model_software_updates.download_and_install_pip_release",
            side_effect=Exception("Pip install failed"),
        ),
        patch("ardupilot_methodic_configurator.data_model_software_updates.logging_error") as mock_logging_error,
    ):
        assert update_manager._perform_download(latest_release) is False
        mock_logging_error.assert_called_once()


def test_update_manager_perform_download_windows_asset_selection(update_manager, mock_dialog) -> None:  # pylint: disable=redefined-outer-name
    """Test selection of the correct asset on Windows."""
    update_manager.dialog = mock_dialog
    latest_release = {
        "assets": [
            {"browser_download_url": "https://example.com/source.tar.gz", "name": "source.tar.gz"},
            {"browser_download_url": "https://example.com/setup.exe", "name": "setup.exe"},
            {"browser_download_url": "https://example.com/linux.deb", "name": "linux.deb"},
        ]
    }

    with (
        patch("ardupilot_methodic_configurator.data_model_software_updates.platform.system", return_value="Windows"),
        patch(
            "ardupilot_methodic_configurator.data_model_software_updates.download_and_install_on_windows", return_value=True
        ) as mock_download,
    ):
        assert update_manager._perform_download(latest_release) is True
        # Should have chosen the .exe file
        mock_download.assert_called_once_with(
            download_url="https://example.com/setup.exe", file_name="setup.exe", progress_callback=mock_dialog.update_progress
        )
