#!/usr/bin/env python3

"""
Tests for middleware_software_updates.py.

This file is part of Ardupilot methodic configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2025 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

from unittest.mock import Mock, patch

import pytest

from ardupilot_methodic_configurator import _
from ardupilot_methodic_configurator.middleware_software_updates import UpdateManager, format_version_info


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

        with patch("ardupilot_methodic_configurator.middleware_software_updates.logging_error") as mock_logging_error:
            assert not update_manager.check_and_update(latest_release, current_version)
            mock_logging_error.assert_called_once()

    def test_check_and_update_value_error(self, update_manager) -> None:  # pylint: disable=redefined-outer-name
        latest_release = {"tag_name": "v2.0.0"}
        current_version = "1.0.0"

        with (
            patch(
                "ardupilot_methodic_configurator.middleware_software_updates.format_version_info",
                side_effect=ValueError,
            ),
            patch("ardupilot_methodic_configurator.middleware_software_updates.logging_error") as mock_logging_error,
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
