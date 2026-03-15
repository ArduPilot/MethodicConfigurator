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

    def test_user_reconnects_with_existing_connection(self, mock_settings_file: dict[str, Any]) -> None:
        """
        User reconnects with a previously used connection string.

        GIVEN: A connection history with multiple entries
        WHEN: The user connects with an existing connection string
        THEN: That connection should move to the top without creating duplicates
        """
        # Arrange: Setup history with existing connections (GIVEN)
        mock_settings_file["connection_history"] = ["COM1", "COM2", "COM3"]

        with (
            patch.object(ProgramSettings, "_get_settings_as_dict", return_value=mock_settings_file),
            patch.object(ProgramSettings, "_set_settings_from_dict") as mock_set,
        ):
            # Act: User reconnects with COM2 (WHEN)
            ProgramSettings.store_connection("COM2")

            # Assert: COM2 moved to top, no duplicates (THEN)
            saved_settings = mock_set.call_args[0][0]
            history = saved_settings["connection_history"]
            assert history[0] == "COM2"  # Moved to top
            assert history[1] == "COM1"
            assert history[2] == "COM3"
            assert len(history) == 3  # No duplicates
            assert history.count("COM2") == 1

    def test_system_enforces_history_limit(self, mock_settings_file: dict[str, Any]) -> None:
        """
        System enforces maximum history size limit.

        GIVEN: A connection history with 10 entries (at capacity)
        WHEN: The user stores an 11th connection
        THEN: The oldest connection should be removed to maintain the 10-item limit
        """
        # Arrange: Fill history to capacity (GIVEN)
        mock_settings_file["connection_history"] = [f"COM{i}" for i in range(1, 11)]  # COM1 through COM10

        with (
            patch.object(ProgramSettings, "_get_settings_as_dict", return_value=mock_settings_file),
            patch.object(ProgramSettings, "_set_settings_from_dict") as mock_set,
        ):
            # Act: Store 11th connection (WHEN)
            ProgramSettings.store_connection("COM11")

            # Assert: History limited to 10, oldest removed (THEN)
            saved_settings = mock_set.call_args[0][0]
            history = saved_settings["connection_history"]
            assert len(history) == 10  # Limit enforced
            assert history[0] == "COM11"  # New connection at top
            assert "COM10" not in history  # Oldest removed

    def test_system_ignores_empty_connection_string(self, mock_settings_file: dict[str, Any]) -> None:
        """
        System ignores empty connection strings.

        GIVEN: A user attempts to save an invalid connection
        WHEN: The connection string is empty
        THEN: The history should remain unchanged
        """
        # Arrange: Setup initial history (GIVEN)
        initial_history = ["COM1", "COM2"]
        mock_settings_file["connection_history"] = initial_history.copy()

        with (
            patch.object(ProgramSettings, "_get_settings_as_dict", return_value=mock_settings_file),
            patch.object(ProgramSettings, "_set_settings_from_dict") as mock_set,
        ):
            # Act: Try to store empty string (WHEN)
            ProgramSettings.store_connection("")

            # Assert: Settings not modified (THEN)
            mock_set.assert_not_called()

    def test_system_ignores_whitespace_only_connection_string(self, mock_settings_file: dict[str, Any]) -> None:
        """
        System ignores whitespace-only connection strings.

        GIVEN: A user attempts to save a whitespace-only connection
        WHEN: The connection string contains only spaces, tabs, or newlines
        THEN: The history should remain unchanged
        """
        # Arrange: Setup initial history (GIVEN)
        mock_settings_file["connection_history"] = ["COM1"]

        with (
            patch.object(ProgramSettings, "_get_settings_as_dict", return_value=mock_settings_file),
            patch.object(ProgramSettings, "_set_settings_from_dict") as mock_set,
        ):
            # Act: Try to store whitespace strings (WHEN)
            ProgramSettings.store_connection("   ")
            ProgramSettings.store_connection("\t\t")
            ProgramSettings.store_connection("\n\n")
            ProgramSettings.store_connection("  \t\n  ")

            # Assert: Settings not modified (THEN)
            mock_set.assert_not_called()

    def test_system_strips_whitespace_from_valid_connections(self, mock_settings_file: dict[str, Any]) -> None:
        """
        System strips leading and trailing whitespace from connections.

        GIVEN: A user enters a connection string with whitespace
        WHEN: The connection string has valid content with extra spaces
        THEN: The whitespace should be stripped before storage
        """
        # Arrange: Setup initial history (GIVEN)
        mock_settings_file["connection_history"] = []

        with (
            patch.object(ProgramSettings, "_get_settings_as_dict", return_value=mock_settings_file),
            patch.object(ProgramSettings, "_set_settings_from_dict") as mock_set,
        ):
            # Act: Store connection with whitespace (WHEN)
            ProgramSettings.store_connection("  COM3  ")

            # Assert: Whitespace stripped (THEN)
            saved_settings = mock_set.call_args[0][0]
            history = saved_settings["connection_history"]
            assert history[0] == "COM3"  # No whitespace

    def test_system_rejects_excessively_long_connection_strings(self, mock_settings_file: dict[str, Any]) -> None:
        """
        System rejects connection strings exceeding maximum length.

        GIVEN: A user attempts to save an extremely long connection string
        WHEN: The connection string exceeds 200 characters
        THEN: The connection should be rejected and history unchanged
        """
        # Arrange: Setup initial history (GIVEN)
        mock_settings_file["connection_history"] = ["COM1"]

        with (
            patch.object(ProgramSettings, "_get_settings_as_dict", return_value=mock_settings_file),
            patch.object(ProgramSettings, "_set_settings_from_dict") as mock_set,
        ):
            # Act: Try to store overly long string (WHEN)
            long_string = "x" * 201  # 201 characters
            ProgramSettings.store_connection(long_string)

            # Assert: Settings not modified (THEN)
            mock_set.assert_not_called()

    def test_system_accepts_connection_at_maximum_length(self, mock_settings_file: dict[str, Any]) -> None:
        """
        System accepts connection strings at the maximum allowed length.

        GIVEN: A user enters a connection string at the 200-character limit
        WHEN: The connection string is exactly 200 characters
        THEN: The connection should be accepted and stored
        """
        # Arrange: Setup empty history (GIVEN)
        mock_settings_file["connection_history"] = []

        with (
            patch.object(ProgramSettings, "_get_settings_as_dict", return_value=mock_settings_file),
            patch.object(ProgramSettings, "_set_settings_from_dict") as mock_set,
        ):
            # Act: Store 200-character string (WHEN)
            max_length_string = "x" * 200
            ProgramSettings.store_connection(max_length_string)

            # Assert: Connection stored (THEN)
            mock_set.assert_called_once()
            saved_settings = mock_set.call_args[0][0]
            assert saved_settings["connection_history"][0] == max_length_string

    def test_system_handles_corrupted_history_with_non_list_value(self, mock_settings_file: dict[str, Any]) -> None:
        """
        System handles corrupted settings with non-list history gracefully.

        GIVEN: Settings file contains invalid data type for connection_history
        WHEN: The system retrieves connection history
        THEN: An empty list should be returned without errors
        """
        # Arrange: Corrupt history with non-list value (GIVEN)
        mock_settings_file["connection_history"] = "not a list"

        with patch.object(ProgramSettings, "_get_settings_as_dict", return_value=mock_settings_file):
            # Act: Get connection history (WHEN)
            result = ProgramSettings.get_connection_history()

            # Assert: Returns empty list (THEN)
            assert result == []

    def test_system_filters_non_string_values_from_history(self, mock_settings_file: dict[str, Any]) -> None:
        """
        System filters out non-string values from connection history.

        GIVEN: Settings file contains mixed data types in connection_history
        WHEN: The system retrieves connection history
        THEN: Only valid string entries should be returned
        """
        # Arrange: History with mixed types (GIVEN)
        mock_settings_file["connection_history"] = [
            "COM1",
            123,  # Invalid: number
            "COM2",
            None,  # Invalid: None
            "COM3",
            {"port": "COM4"},  # Invalid: dict
            "COM5",
        ]

        with patch.object(ProgramSettings, "_get_settings_as_dict", return_value=mock_settings_file):
            # Act: Get connection history (WHEN)
            result = ProgramSettings.get_connection_history()

            # Assert: Only strings returned (THEN)
            assert result == ["COM1", "COM2", "COM3", "COM5"]
            assert all(isinstance(item, str) for item in result)


class TestConnectionHistoryReturnValues:
    """Test return values of store_connection and get_connection_history."""

    def test_store_connection_returns_normalized_string_on_success(self, mock_settings_file: dict[str, Any]) -> None:
        """
        store_connection returns the normalized (stripped) string it actually stored.

        GIVEN: A user saves a connection string that has leading/trailing whitespace
        WHEN: store_connection is called with the padded string
        THEN: The return value should be the normalized (stripped) string
        AND: Callers can use the return value as a stable cache key
        """
        # Arrange: Empty history (GIVEN)
        mock_settings_file["connection_history"] = []

        with (
            patch.object(ProgramSettings, "_get_settings_as_dict", return_value=mock_settings_file),
            patch.object(ProgramSettings, "_set_settings_from_dict"),
        ):
            # Act: Store connection with surrounding whitespace (WHEN)
            result = ProgramSettings.store_connection("  COM3  ")

        # Assert: Normalized value returned (THEN)
        assert result == "COM3"

    def test_store_connection_returns_unmodified_string_when_no_whitespace(self, mock_settings_file: dict[str, Any]) -> None:
        """
        store_connection returns the string unchanged when it needs no normalization.

        GIVEN: A user saves a clean connection string with no extra whitespace
        WHEN: store_connection is called
        THEN: The return value should match the input exactly
        """
        # Arrange: Empty history (GIVEN)
        mock_settings_file["connection_history"] = []

        with (
            patch.object(ProgramSettings, "_get_settings_as_dict", return_value=mock_settings_file),
            patch.object(ProgramSettings, "_set_settings_from_dict"),
        ):
            # Act: Store clean connection string (WHEN)
            result = ProgramSettings.store_connection("tcp:127.0.0.1:5760")

        # Assert: Input returned unchanged (THEN)
        assert result == "tcp:127.0.0.1:5760"

    def test_store_connection_returns_none_for_whitespace_only_input(self, mock_settings_file: dict[str, Any]) -> None:
        """
        store_connection returns None when the input is rejected as invalid.

        GIVEN: A user accidentally enters only whitespace as a connection string
        WHEN: store_connection is called with a whitespace-only string
        THEN: None should be returned to signal the input was rejected
        AND: Callers can distinguish a failed store from a successful one
        """
        # Arrange: (GIVEN - no special setup needed)
        with (
            patch.object(ProgramSettings, "_get_settings_as_dict", return_value=mock_settings_file),
            patch.object(ProgramSettings, "_set_settings_from_dict"),
        ):
            # Act: Store whitespace-only string (WHEN)
            result = ProgramSettings.store_connection("   ")

        # Assert: None returned (THEN)
        assert result is None

    def test_store_connection_returns_none_for_excessively_long_input(self, mock_settings_file: dict[str, Any]) -> None:
        """
        store_connection returns None for inputs that exceed the maximum length.

        GIVEN: A user (or malicious input) sends an extremely long connection string
        WHEN: store_connection is called with a 201-character string
        THEN: None should be returned signalling rejection
        """
        # Arrange: (GIVEN)
        with (
            patch.object(ProgramSettings, "_get_settings_as_dict", return_value=mock_settings_file),
            patch.object(ProgramSettings, "_set_settings_from_dict"),
        ):
            # Act: Store excessively long string (WHEN)
            result = ProgramSettings.store_connection("x" * 201)

        # Assert: None returned (THEN)
        assert result is None

    def test_get_connection_history_returns_all_valid_connections_in_order(self, mock_settings_file: dict[str, Any]) -> None:
        """
        get_connection_history returns the stored connections in most-recent-first order.

        GIVEN: The settings file contains a valid connection history
        WHEN: get_connection_history is called
        THEN: All valid connections should be returned in the exact stored order
        AND: The order should reflect most-recently-used first
        """
        # Arrange: Ordered history (GIVEN)
        mock_settings_file["connection_history"] = ["COM1", "tcp:127.0.0.1:5760", "udp:0.0.0.0:14550"]

        with patch.object(ProgramSettings, "_get_settings_as_dict", return_value=mock_settings_file):
            # Act: Retrieve history (WHEN)
            result = ProgramSettings.get_connection_history()

        # Assert: All entries returned in order (THEN)
        assert result == ["COM1", "tcp:127.0.0.1:5760", "udp:0.0.0.0:14550"]

    def test_get_connection_history_returns_empty_list_when_no_history_stored(
        self, mock_settings_file: dict[str, Any]
    ) -> None:
        """
        get_connection_history returns an empty list when no history is present.

        GIVEN: The application is started for the first time with no stored connections
        WHEN: get_connection_history is called
        THEN: An empty list should be returned (no exceptions raised)
        """
        # Arrange: Empty history (GIVEN)
        mock_settings_file["connection_history"] = []

        with patch.object(ProgramSettings, "_get_settings_as_dict", return_value=mock_settings_file):
            # Act: Retrieve history (WHEN)
            result = ProgramSettings.get_connection_history()

        # Assert: Empty list returned (THEN)
        assert result == []
