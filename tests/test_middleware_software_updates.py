#!/usr/bin/env python3

"""
Tests for middleware_software_updates.py.

This file is part of Ardupilot methodic configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2025 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

from unittest.mock import Mock, patch

import pytest

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

    def test_check_and_update_same_version(self, update_manager) -> None:
        latest_release = {"tag_name": "v1.0.0"}
        current_version = "1.0.0"

        assert not update_manager.check_and_update(latest_release, current_version)

    def test_check_and_update_key_error(self, update_manager) -> None:
        latest_release = {}
        current_version = "1.0.0"

        with patch("ardupilot_methodic_configurator.middleware_software_updates.logging_error") as mock_logging_error:
            assert not update_manager.check_and_update(latest_release, current_version)
            mock_logging_error.assert_called_once()

    def test_check_and_update_value_error(self, update_manager) -> None:
        latest_release = {"tag_name": "v2.0.0"}
        current_version = "1.0.0"

        with patch("ardupilot_methodic_configurator.middleware_software_updates.format_version_info", side_effect=ValueError):  # noqa: SIM117
            with patch("ardupilot_methodic_configurator.middleware_software_updates.logging_error") as mock_logging_error:
                assert not update_manager.check_and_update(latest_release, current_version)
                mock_logging_error.assert_called_once()
