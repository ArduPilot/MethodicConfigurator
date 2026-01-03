#!/usr/bin/env python3

"""
Unit tests for backend_filesystem_vehicle_components.py implementation details.

These tests focus on low-level implementation details for coverage purposes.
For behavior-driven tests, see test_backend_filesystem_vehicle_components.py.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

from json.decoder import JSONDecodeError as RealJSONDecodeError
from unittest.mock import mock_open, patch

import pytest

from ardupilot_methodic_configurator.backend_filesystem_vehicle_components import VehicleComponents

# pylint: disable=protected-access,attribute-defined-outside-init,unused-argument


class TestVehicleComponentsInternals:
    """Unit tests for VehicleComponents internal implementation."""

    @pytest.fixture(autouse=True)
    def setup(self) -> None:
        """Set up test fixtures."""
        self.vehicle_components = VehicleComponents()

    @patch("ardupilot_methodic_configurator.backend_filesystem_program_settings.ProgramSettings.get_templates_base_dir")
    @patch("builtins.open", new_callable=mock_open)
    @patch("ardupilot_methodic_configurator.backend_filesystem_vehicle_components.json_load")
    def test_load_system_templates_json_decode_error(self, mock_json_load, mock_file, mock_get_base_dir) -> None:
        """
        Test internal error handling for JSONDecodeError in system templates.

        GIVEN: A corrupted system templates file
        WHEN: Loading system templates encounters JSONDecodeError
        THEN: Should return empty dict without crashing
        """
        mock_get_base_dir.return_value = "/app/path"
        mock_json_load.side_effect = RealJSONDecodeError("Invalid JSON", '{"bad": json}', 0)

        result = self.vehicle_components._load_system_templates()

        assert result == {}

    @patch("ardupilot_methodic_configurator.backend_filesystem_program_settings.ProgramSettings.get_templates_base_dir")
    @patch("builtins.open", new_callable=mock_open)
    @patch("ardupilot_methodic_configurator.backend_filesystem_vehicle_components.json_load")
    def test_load_user_templates_json_decode_error(self, mock_json_load, mock_file, mock_get_base_dir) -> None:
        """
        Test internal error handling for JSONDecodeError in user templates.

        GIVEN: A corrupted user templates file
        WHEN: Loading user templates encounters JSONDecodeError
        THEN: Should return empty dict without crashing
        """
        mock_get_base_dir.return_value = "/user/templates"
        mock_json_load.side_effect = RealJSONDecodeError("Invalid JSON", '{"bad": json}', 0)

        result = self.vehicle_components._load_user_templates()

        assert result == {}

    @patch("ardupilot_methodic_configurator.backend_filesystem_vehicle_components.os_makedirs")
    @patch("ardupilot_methodic_configurator.backend_filesystem_program_settings.ProgramSettings.get_templates_base_dir")
    def test_save_component_templates_to_file_makedirs_error(self, mock_get_base_dir, mock_makedirs) -> None:
        """
        Test internal error handling when directory creation fails.

        GIVEN: Directory creation fails with OSError
        WHEN: Attempting to save templates
        THEN: Should return error tuple with message
        """
        mock_get_base_dir.return_value = "/test/templates"
        mock_makedirs.side_effect = OSError("Permission denied")

        templates_to_save = {"Component1": [{"name": "Test", "data": {}}]}

        error, msg = self.vehicle_components.save_component_templates_to_file(templates_to_save)

        assert error is True
        assert "Failed to create templates directory" in msg

    @patch("builtins.open", new_callable=mock_open)
    @patch("ardupilot_methodic_configurator.backend_filesystem_vehicle_components.os_makedirs")
    @patch("ardupilot_methodic_configurator.backend_filesystem_program_settings.ProgramSettings.get_templates_base_dir")
    def test_save_component_templates_to_file_generic_exception(self, mock_get_base_dir, mock_makedirs, mock_file) -> None:
        """
        Test internal error handling for unexpected exceptions.

        GIVEN: File operation raises unexpected ValueError
        WHEN: Attempting to save templates
        THEN: Should catch and return error with message
        """
        mock_get_base_dir.return_value = "/test/templates"
        mock_makedirs.return_value = None
        mock_file.side_effect = ValueError("Unexpected error")

        templates_to_save = {"Component1": [{"name": "Test", "data": {}}]}

        error, msg = self.vehicle_components.save_component_templates_to_file(templates_to_save)

        assert error is True
        assert "Unexpected error saving templates" in msg

    @patch("builtins.open", new_callable=mock_open)
    @patch("ardupilot_methodic_configurator.backend_filesystem_vehicle_components.os_makedirs")
    @patch("ardupilot_methodic_configurator.backend_filesystem_program_settings.ProgramSettings.get_templates_base_dir")
    def test_save_component_templates_to_file_permission_error(self, mock_get_base_dir, mock_makedirs, mock_file) -> None:
        """
        Test internal error handling for PermissionError.

        GIVEN: File write fails with PermissionError
        WHEN: Attempting to save templates
        THEN: Should return error with permission denied message
        """
        mock_get_base_dir.return_value = "/test/templates"
        mock_makedirs.return_value = None
        mock_file.side_effect = PermissionError("Access denied")

        templates_to_save = {"Component1": [{"name": "Test", "data": {}}]}

        error, msg = self.vehicle_components.save_component_templates_to_file(templates_to_save)

        assert error is True
        assert "Permission denied" in msg

    @patch("builtins.open", new_callable=mock_open)
    @patch("ardupilot_methodic_configurator.backend_filesystem_vehicle_components.os_makedirs")
    @patch("ardupilot_methodic_configurator.backend_filesystem_program_settings.ProgramSettings.get_templates_base_dir")
    def test_save_component_templates_to_file_os_error(self, mock_get_base_dir, mock_makedirs, mock_file) -> None:
        """
        Test internal error handling for OSError during file write.

        GIVEN: File write fails with OSError
        WHEN: Attempting to save templates
        THEN: Should return error with OS error message
        """
        mock_get_base_dir.return_value = "/test/templates"
        mock_makedirs.return_value = None
        mock_file.side_effect = OSError("Disk full")

        templates_to_save = {"Component1": [{"name": "Test", "data": {}}]}

        error, msg = self.vehicle_components.save_component_templates_to_file(templates_to_save)

        assert error is True
        assert "OS error" in msg

    @patch.object(VehicleComponents, "_load_system_templates")
    @patch.object(VehicleComponents, "save_component_templates_to_file")
    def test_save_component_templates_template_without_name(self, mock_save_to_file, mock_load_system) -> None:
        """
        Test internal handling of templates without name field.

        GIVEN: Templates missing name field or with empty name
        WHEN: Saving component templates
        THEN: Should skip templates without valid names
        """
        system_templates = {}

        templates_no_name = {
            "Component1": [
                {"data": {"param": "value"}},  # Missing "name" field
                {"name": "", "data": {"param": "value2"}},  # Empty name
                {"name": "Valid Template", "data": {"param": "value3"}},  # Valid
            ],
        }

        mock_load_system.return_value = system_templates
        mock_save_to_file.return_value = (False, "")

        result, msg = self.vehicle_components.save_component_templates(templates_no_name)

        assert not result
        assert msg == ""

        # pylint: disable=duplicate-code  # Common assertion pattern
        saved_templates = mock_save_to_file.call_args[0][0]

        assert "Component1" in saved_templates
        assert len(saved_templates["Component1"]) == 1
        # pylint: enable=duplicate-code
        assert saved_templates["Component1"][0]["name"] == "Valid Template"

    @patch.object(VehicleComponents, "_load_system_templates")
    @patch.object(VehicleComponents, "save_component_templates_to_file")
    def test_save_component_templates_to_system_removes_user_modified_flag(self, mock_save_to_file, mock_load_system) -> None:
        """
        Test internal flag removal when saving to system templates.

        GIVEN: Template with is_user_modified flag in system save mode
        WHEN: Saving to system templates
        THEN: Should remove is_user_modified flag before saving
        """
        vehicle_components_system = VehicleComponents(save_component_to_system_templates=True)

        system_templates = {"Component1": []}

        new_templates = {
            "Component1": [{"name": "New Template", "data": {"param": "value"}, "is_user_modified": True}],
        }

        # pylint: disable=duplicate-code  # Common assertion pattern
        mock_load_system.return_value = system_templates
        mock_save_to_file.return_value = (False, "")

        result, msg = vehicle_components_system.save_component_templates(new_templates)

        assert not result
        assert msg == ""

        saved_templates = mock_save_to_file.call_args[0][0]

        assert "Component1" in saved_templates
        # pylint: enable=duplicate-code
        assert len(saved_templates["Component1"]) == 1
        assert saved_templates["Component1"][0]["name"] == "New Template"
        assert "is_user_modified" not in saved_templates["Component1"][0]

    def test_recursively_clear_dict_edge_cases(self) -> None:
        """
        Test internal _recursively_clear_dict method with edge cases.

        GIVEN: Various edge case dictionary structures
        WHEN: Calling _recursively_clear_dict
        THEN: Should handle all type conversions correctly
        """
        # Test with empty dictionary
        empty_dict = {}
        self.vehicle_components._recursively_clear_dict(empty_dict)
        assert not empty_dict

        # Test with nested empty dictionaries
        nested_empty = {"level1": {"level2": {}}}
        self.vehicle_components._recursively_clear_dict(nested_empty)
        assert nested_empty == {"level1": {"level2": {}}}

        # Test with None values
        none_dict = {"key1": None, "key2": {"nested": None}}
        self.vehicle_components._recursively_clear_dict(none_dict)
        assert none_dict == {"key1": None, "key2": {"nested": None}}

        # Test with mixed types
        complex_dict = {
            "string": "value",
            "int": 42,
            "float": 3.14,
            "bool": True,
            "list": ["a", "b", "c"],
            "dict": {"nested": "value"},
            "none": None,
            "complex_nested": {
                "strings": ["a", "b"],
                "numbers": [1, 2, 3],
                "mixed": [1, "a", True],
                "deep": {"deeper": {"deepest": "value"}},
            },
        }

        self.vehicle_components._recursively_clear_dict(complex_dict)

        assert complex_dict["string"] == ""
        assert complex_dict["int"] == 0
        assert complex_dict["float"] == 0.0
        assert complex_dict["bool"] is False
        assert not complex_dict["list"]
        assert complex_dict["dict"] == {"nested": ""}
        assert complex_dict["none"] is None
        assert not complex_dict["complex_nested"]["strings"]
        assert not complex_dict["complex_nested"]["numbers"]
        assert not complex_dict["complex_nested"]["mixed"]
        assert complex_dict["complex_nested"]["deep"]["deeper"]["deepest"] == ""

    def test_recursively_clear_dict_non_dict_input(self) -> None:
        """
        Test internal _recursively_clear_dict with non-dictionary inputs.

        GIVEN: Non-dictionary inputs (list, string, int, None)
        WHEN: Calling _recursively_clear_dict
        THEN: Should return early without modification
        """
        list_input = [1, 2, 3]
        self.vehicle_components._recursively_clear_dict(list_input)
        assert list_input == [1, 2, 3]

        string_input = "test"
        self.vehicle_components._recursively_clear_dict(string_input)
        assert string_input == "test"

        int_input = 42
        self.vehicle_components._recursively_clear_dict(int_input)
        assert int_input == 42

        none_input = None
        self.vehicle_components._recursively_clear_dict(none_input)
        assert none_input is None
