#!/usr/bin/env python3
"""
BDD-style tests for the backend_filesystem_program_settings.py file.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

from typing import Any
from unittest.mock import patch

import pytest

from ardupilot_methodic_configurator.backend_filesystem_program_settings import ProgramSettings

# pylint: disable=redefined-outer-name


@pytest.fixture
def mock_settings_file() -> dict[str, Any]:
    """Fixture providing realistic settings data for testing."""
    return {
        "Format version": 1,
        "display_usage_popup": {
            "workflow_explanation": True,
            "component_editor": False,
        },
        "connection_history": ["COM3", "tcp:127.0.0.1:5760"],
        "directory_selection": {
            "template_dir": "/path/to/template",
            "new_base_dir": "/path/to/base",
            "vehicle_dir": "/path/to/vehicle",
        },
        "auto_open_doc_in_browser": True,
        "gui_complexity": "simple",
        "motor_test": {
            "duration": 2,
            "throttle_pct": 10,
        },
    }


class TestConnectionHistoryManagement:
    """Test user connection history management workflows."""

    def test_user_can_store_new_connection(self, mock_settings_file: dict[str, Any]) -> None:
        """
        User can save a new connection string to history.

        GIVEN: A user successfully connects to a device
        WHEN: The connection is stored
        THEN: It should appear at the top of the connection history
        """
        # Arrange: Mock settings and file operations (GIVEN)
        with (
            patch.object(ProgramSettings, "_get_settings_as_dict", return_value=mock_settings_file),
            patch.object(ProgramSettings, "_set_settings_from_dict") as mock_set,
        ):
            # Act: User stores a new connection (WHEN)
            ProgramSettings.store_connection("udp:192.168.1.100:14550")

            # Assert: New connection added to top of history (THEN)
            mock_set.assert_called_once()
            saved_settings = mock_set.call_args[0][0]
            assert saved_settings["connection_history"][0] == "udp:192.168.1.100:14550"

    def test_user_can_store_multiple_connections_in_order(self, mock_settings_file: dict[str, Any]) -> None:
        """
        User can store multiple connections and they maintain order.

        GIVEN: A clean connection history
        WHEN: The user stores multiple connection strings
        THEN: The connections should be stored in most-recent-first order
        """
        # Arrange: Start with empty history (GIVEN)
        mock_settings_file["connection_history"] = []

        with (
            patch.object(ProgramSettings, "_get_settings_as_dict", return_value=mock_settings_file),
            patch.object(ProgramSettings, "_set_settings_from_dict") as mock_set,
        ):
            # Act: User stores multiple connections (WHEN)
            ProgramSettings.store_connection("COM1")
            ProgramSettings.store_connection("COM2")
            ProgramSettings.store_connection("COM3")

            # Assert: Connections in correct order (THEN)
            # We check the very last call to see the final state of history
            final_settings = mock_set.call_args[0][0]
            history = final_settings["connection_history"]
            assert history[0] == "COM3"  # Most recent first
            assert history[1] == "COM2"
            assert history[2] == "COM1"
