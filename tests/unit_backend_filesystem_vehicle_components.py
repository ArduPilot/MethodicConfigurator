#!/usr/bin/env python3

"""
Unit tests for backend_filesystem_vehicle_components.py implementation details.

These tests focus on low-level implementation details for coverage purposes.
For behavior-driven tests, see test_backend_filesystem_vehicle_components.py.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

from importlib.resources import files as importlib_files
from json.decoder import JSONDecodeError as RealJSONDecodeError
from unittest.mock import MagicMock, mock_open, patch

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
    def test_load_system_templates_json_decode_error(
        self, mock_json_load: MagicMock, mock_file: MagicMock, mock_get_base_dir: MagicMock
    ) -> None:
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
    def test_load_user_templates_json_decode_error(
        self, mock_json_load: MagicMock, mock_file: MagicMock, mock_get_base_dir: MagicMock
    ) -> None:
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
    def test_save_component_templates_to_file_makedirs_error(
        self, mock_get_base_dir: MagicMock, mock_makedirs: MagicMock
    ) -> None:
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

    @patch("ardupilot_methodic_configurator.backend_filesystem_vehicle_components.safe_write")
    @patch("ardupilot_methodic_configurator.backend_filesystem_vehicle_components.os_makedirs")
    @patch("ardupilot_methodic_configurator.backend_filesystem_program_settings.ProgramSettings.get_templates_base_dir")
    def test_save_component_templates_to_file_generic_exception(  # type: ignore[misc]
        self, mock_get_base_dir: MagicMock, mock_makedirs: MagicMock, mock_safe_write: MagicMock
    ) -> None:
        """
        Test internal error handling for unexpected exceptions.

        GIVEN: File operation raises unexpected ValueError
        WHEN: Attempting to save templates
        THEN: Should catch and return error with message
        """
        mock_get_base_dir.return_value = "/test/templates"
        mock_makedirs.return_value = None
        mock_safe_write.side_effect = ValueError("Unexpected error")

        templates_to_save = {"Component1": [{"name": "Test", "data": {}}]}

        error, msg = self.vehicle_components.save_component_templates_to_file(templates_to_save)

        assert error is True
        assert "Unexpected error saving templates" in msg

    @patch("ardupilot_methodic_configurator.backend_filesystem_vehicle_components.safe_write")
    @patch("ardupilot_methodic_configurator.backend_filesystem_vehicle_components.os_makedirs")
    @patch("ardupilot_methodic_configurator.backend_filesystem_program_settings.ProgramSettings.get_templates_base_dir")
    def test_save_component_templates_to_file_permission_error(  # type: ignore[misc]
        self, mock_get_base_dir: MagicMock, mock_makedirs: MagicMock, mock_safe_write: MagicMock
    ) -> None:
        """
        Test internal error handling for PermissionError.

        GIVEN: File write fails with PermissionError
        WHEN: Attempting to save templates
        THEN: Should return error with permission denied message
        """
        mock_get_base_dir.return_value = "/test/templates"
        mock_makedirs.return_value = None
        mock_safe_write.side_effect = PermissionError("Access denied")

        templates_to_save = {"Component1": [{"name": "Test", "data": {}}]}

        error, msg = self.vehicle_components.save_component_templates_to_file(templates_to_save)

        assert error is True
        assert "Permission denied" in msg

    @patch("ardupilot_methodic_configurator.backend_filesystem_vehicle_components.safe_write")
    @patch("ardupilot_methodic_configurator.backend_filesystem_vehicle_components.os_makedirs")
    @patch("ardupilot_methodic_configurator.backend_filesystem_program_settings.ProgramSettings.get_templates_base_dir")
    def test_save_component_templates_to_file_os_error(
        self, mock_get_base_dir: MagicMock, mock_makedirs: MagicMock, mock_safe_write: MagicMock
    ) -> None:
        """
        Test internal error handling for OSError during file write.

        GIVEN: File write fails with OSError
        WHEN: Attempting to save templates
        THEN: Should return error with OS error message
        """
        mock_get_base_dir.return_value = "/test/templates"
        mock_makedirs.return_value = None
        mock_safe_write.side_effect = OSError("Disk full")

        templates_to_save = {"Component1": [{"name": "Test", "data": {}}]}

        error, msg = self.vehicle_components.save_component_templates_to_file(templates_to_save)

        assert error is True
        assert "OS error" in msg

    @patch("ardupilot_methodic_configurator.backend_filesystem_vehicle_components.os_path.exists")
    @patch("builtins.open", new_callable=mock_open)
    @patch("ardupilot_methodic_configurator.backend_filesystem_vehicle_components.os_makedirs")
    @patch("ardupilot_methodic_configurator.backend_filesystem_vehicle_components.safe_write")
    @patch("ardupilot_methodic_configurator.backend_filesystem_program_settings.ProgramSettings.get_templates_base_dir")
    def test_save_component_templates_to_file_uses_local_dir_when_local_file_exists(  # pylint: disable=too-many-arguments,too-many-positional-arguments
        self,
        mock_get_base_dir: MagicMock,
        mock_safe_write: MagicMock,
        mock_makedirs: MagicMock,
        mock_file: MagicMock,
        mock_exists: MagicMock,
    ) -> None:
        """
        Test that system templates use local directory when local file exists.

        GIVEN: Saving system templates and local system template file exists
        WHEN: Attempting to save templates
        THEN: Should use local directory instead of system directory
        """
        mock_get_base_dir.return_value = "/system/templates"
        mock_makedirs.return_value = None
        mock_exists.return_value = True  # Local file exists
        mock_safe_write.return_value = None

        vehicle_components_system = VehicleComponents(save_component_to_system_templates=True)
        templates_to_save = {"Component1": [{"name": "Test", "data": {}}]}

        error, msg = vehicle_components_system.save_component_templates_to_file(templates_to_save)

        assert error is False
        # Normalise path separators before comparison to remain platform-independent
        msg_normalized = msg.replace("\\", "/")
        assert "system_vehicle_components_template.json" in msg_normalized
        assert "/system/templates" in msg_normalized or "ardupilot_methodic_configurator/vehicle_templates" in msg_normalized

    @patch.object(VehicleComponents, "_load_system_templates")
    @patch.object(VehicleComponents, "save_component_templates_to_file")
    def test_save_component_templates_template_without_name(
        self, mock_save_to_file: MagicMock, mock_load_system: MagicMock
    ) -> None:
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
        mock_save_to_file.return_value = (False, "/test/templates/user_vehicle_components_template.json")

        result, msg = self.vehicle_components.save_component_templates(templates_no_name)

        assert not result
        assert msg == "/test/templates/user_vehicle_components_template.json"

        # pylint: disable=duplicate-code  # Common assertion pattern
        saved_templates = mock_save_to_file.call_args[0][0]

        assert "Component1" in saved_templates
        assert len(saved_templates["Component1"]) == 1
        # pylint: enable=duplicate-code
        assert saved_templates["Component1"][0]["name"] == "Valid Template"

    @patch.object(VehicleComponents, "_load_system_templates")
    @patch.object(VehicleComponents, "save_component_templates_to_file")
    def test_save_component_templates_to_system_removes_user_modified_flag(
        self, mock_save_to_file: MagicMock, mock_load_system: MagicMock
    ) -> None:
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
        mock_save_to_file.return_value = (False, "/test/templates/system_vehicle_components_template.json")

        result, msg = vehicle_components_system.save_component_templates(new_templates)

        assert not result
        assert msg == "/test/templates/system_vehicle_components_template.json"

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


class TestVehicleComponentsTemplateLoadingErrors:
    """Unit tests for VehicleComponents template loading error handling."""

    @pytest.fixture(autouse=True)
    def setup(self) -> None:
        """Set up test fixtures."""
        self.vehicle_components = VehicleComponents()

    @patch("ardupilot_methodic_configurator.backend_filesystem_program_settings.ProgramSettings.get_templates_base_dir")
    @patch("builtins.open", new_callable=mock_open)
    @patch("ardupilot_methodic_configurator.backend_filesystem_vehicle_components.json_load")
    def test_load_system_templates_file_not_found(
        self, mock_json_load: MagicMock, mock_file: MagicMock, mock_get_base_dir: MagicMock
    ) -> None:
        """
        System template loading is skipped gracefully when the templates file does not exist.

        GIVEN: System templates file doesn't exist
        WHEN: Loading system templates
        THEN: Should return empty dict without crashing
        """
        mock_get_base_dir.return_value = "/app/path"
        mock_file.side_effect = FileNotFoundError("File not found")

        result = self.vehicle_components._load_system_templates()

        assert result == {}

    @patch("ardupilot_methodic_configurator.backend_filesystem_program_settings.ProgramSettings.get_templates_base_dir")
    @patch("builtins.open", new_callable=mock_open)
    @patch("ardupilot_methodic_configurator.backend_filesystem_vehicle_components.json_load")
    def test_load_system_templates_os_error(
        self, mock_json_load: MagicMock, mock_file: MagicMock, mock_get_base_dir: MagicMock
    ) -> None:
        """
        System template loading is skipped gracefully when an OS error prevents file access.

        GIVEN: OS error occurs while reading system templates file
        WHEN: Loading system templates
        THEN: Should return empty dict without crashing
        """
        mock_get_base_dir.return_value = "/app/path"
        mock_file.side_effect = OSError("Permission denied")

        result = self.vehicle_components._load_system_templates()

        assert result == {}

    @patch("ardupilot_methodic_configurator.backend_filesystem_program_settings.ProgramSettings.get_templates_base_dir")
    @patch("builtins.open", new_callable=mock_open)
    @patch("ardupilot_methodic_configurator.backend_filesystem_vehicle_components.json_load")
    def test_load_system_templates_unexpected_exception(
        self, mock_json_load: MagicMock, mock_file: MagicMock, mock_get_base_dir: MagicMock
    ) -> None:
        """
        System template loading is skipped gracefully when an unexpected exception occurs.

        GIVEN: An unexpected exception occurs while reading system templates
        WHEN: Loading system templates
        THEN: Should return empty dict without crashing
        """
        mock_get_base_dir.return_value = "/app/path"
        mock_file.side_effect = RuntimeError("Unexpected error")

        result = self.vehicle_components._load_system_templates()

        assert result == {}

    @patch("ardupilot_methodic_configurator.backend_filesystem_program_settings.ProgramSettings.get_templates_base_dir")
    @patch("builtins.open", new_callable=mock_open)
    @patch("ardupilot_methodic_configurator.backend_filesystem_vehicle_components.json_load")
    def test_load_user_templates_file_not_found(
        self, mock_json_load: MagicMock, mock_file: MagicMock, mock_get_base_dir: MagicMock
    ) -> None:
        """
        User template loading is skipped gracefully when the templates file does not exist.

        GIVEN: User templates file doesn't exist
        WHEN: Loading user templates
        THEN: Should return empty dict without crashing (debug message only)
        """
        mock_get_base_dir.return_value = "/user/templates"
        mock_file.side_effect = FileNotFoundError("File not found")

        result = self.vehicle_components._load_user_templates()

        assert result == {}

    @patch("ardupilot_methodic_configurator.backend_filesystem_program_settings.ProgramSettings.get_templates_base_dir")
    @patch("builtins.open", new_callable=mock_open)
    @patch("ardupilot_methodic_configurator.backend_filesystem_vehicle_components.json_load")
    def test_load_user_templates_os_error(
        self, mock_json_load: MagicMock, mock_file: MagicMock, mock_get_base_dir: MagicMock
    ) -> None:
        """
        User template loading is skipped gracefully when an OS error prevents file access.

        GIVEN: OS error occurs while reading user templates file
        WHEN: Loading user templates
        THEN: Should return empty dict without crashing
        """
        mock_get_base_dir.return_value = "/user/templates"
        mock_file.side_effect = OSError("Disk I/O error")

        result = self.vehicle_components._load_user_templates()

        assert result == {}

    @patch("ardupilot_methodic_configurator.backend_filesystem_program_settings.ProgramSettings.get_templates_base_dir")
    @patch("builtins.open", new_callable=mock_open)
    @patch("ardupilot_methodic_configurator.backend_filesystem_vehicle_components.json_load")
    def test_load_user_templates_unexpected_exception(
        self, mock_json_load: MagicMock, mock_file: MagicMock, mock_get_base_dir: MagicMock
    ) -> None:
        """
        User template loading is skipped gracefully when an unexpected exception occurs.

        GIVEN: An unexpected exception occurs while reading user templates
        WHEN: Loading user templates
        THEN: Should return empty dict without crashing
        """
        mock_get_base_dir.return_value = "/user/templates"
        mock_file.side_effect = RuntimeError("Unexpected error")

        result = self.vehicle_components._load_user_templates()

        assert result == {}


class TestVehicleComponentsTemplateMerging:
    """Unit tests for template merging and filtering during load."""

    @pytest.fixture(autouse=True)
    def setup(self) -> None:
        """Set up test fixtures."""
        self.vehicle_components = VehicleComponents()

    def test_load_component_templates_handles_user_template_without_name(self) -> None:
        """
        load_component_templates skips user templates without a name.

        GIVEN: User templates containing entries without a 'name' field
        WHEN: Loading component templates
        THEN: Templates without names should be skipped silently
        AND: Named templates should still be loaded correctly
        """
        system_templates = {"Motor": [{"name": "Standard 2205", "data": {"kv": 2300}}]}
        user_templates = {
            "Motor": [
                {"data": {"kv": 1500}},  # No 'name' field - should be skipped
                {"name": "", "data": {"kv": 1800}},  # Empty name - should be skipped
                {"name": "Custom Motor", "data": {"kv": 2000}},  # Valid - should be added
            ]
        }

        with (
            patch.object(self.vehicle_components, "_load_system_templates", return_value=system_templates),
            patch.object(self.vehicle_components, "_load_user_templates", return_value=user_templates),
        ):
            result = self.vehicle_components.load_component_templates()

        # Valid user template should be present
        assert "Motor" in result
        motor_names = [t.get("name") for t in result["Motor"]]
        assert "Custom Motor" in motor_names
        # Unnamed templates should NOT be present
        assert None not in motor_names
        assert "" not in motor_names


class TestVehicleComponentsSystemTemplateSaving:
    """Unit tests for system-template path selection and error handling in save operations."""

    def test_save_component_templates_to_file_fallback_when_system_file_not_found(self) -> None:
        """
        save_component_templates_to_file uses package path when system path doesn't exist.

        GIVEN: Saving to system templates and system path doesn't exist on filesystem
        WHEN: save_component_templates_to_file is called
        THEN: Should fall back to package path
        AND: Should not raise an exception
        """
        vehicle_components_system = VehicleComponents(save_component_to_system_templates=True)
        templates_to_save = {"Component1": [{"name": "Test", "data": {}}]}

        with (
            patch(
                "ardupilot_methodic_configurator.backend_filesystem_program_settings.ProgramSettings.get_templates_base_dir"
            ) as mock_get_base_dir,
            patch("ardupilot_methodic_configurator.backend_filesystem_vehicle_components.os_path.exists") as mock_exists,
            patch("ardupilot_methodic_configurator.backend_filesystem_vehicle_components.os_makedirs"),
            patch("ardupilot_methodic_configurator.backend_filesystem_vehicle_components.safe_write") as mock_safe_write,
        ):
            mock_get_base_dir.return_value = "/nonexistent/path"
            mock_exists.return_value = False  # System file does NOT exist at primary location

            error, msg = vehicle_components_system.save_component_templates_to_file(templates_to_save)

        expected_fallback = str(
            importlib_files("ardupilot_methodic_configurator")
            / "vehicle_templates"
            / "system_vehicle_components_template.json"
        ).replace("\\", "/")

        assert error is False
        assert msg == expected_fallback
        assert mock_safe_write.call_count == 1
        safe_write_path = mock_safe_write.call_args.args[0].replace("\\", "/")
        assert safe_write_path == expected_fallback

    def test_save_component_templates_to_file_handles_oserror_in_makedirs_for_system_path(self) -> None:
        """
        save_component_templates_to_file handles OSError when checking system path.

        GIVEN: An OSError occurs when checking for the system template path
        WHEN: save_component_templates_to_file is called for system templates
        THEN: Should handle the error gracefully and continue
        AND: Should fall back to default templates_dir
        """
        vehicle_components_system = VehicleComponents(save_component_to_system_templates=True)
        templates_to_save = {"Component1": [{"name": "Test", "data": {}}]}

        with (
            patch(
                "ardupilot_methodic_configurator.backend_filesystem_program_settings.ProgramSettings.get_templates_base_dir"
            ) as mock_get_base_dir,
            patch("ardupilot_methodic_configurator.backend_filesystem_vehicle_components.os_path.exists") as mock_exists,
            patch("ardupilot_methodic_configurator.backend_filesystem_vehicle_components.os_makedirs") as mock_makedirs,
            patch("ardupilot_methodic_configurator.backend_filesystem_vehicle_components.safe_write") as mock_safe_write,
        ):
            mock_get_base_dir.return_value = "/test/templates"
            mock_exists.side_effect = OSError("Permission denied")
            mock_makedirs.return_value = None

            error, msg = vehicle_components_system.save_component_templates_to_file(templates_to_save)

        expected_path = "/test/templates/system_vehicle_components_template.json"
        assert error is False
        assert msg == expected_path
        assert mock_safe_write.call_count == 1
        safe_write_path = mock_safe_write.call_args.args[0].replace("\\", "/")
        assert safe_write_path == expected_path


class TestVehicleComponentsWipeInfo:
    """Tests for wipe_component_info behavior."""

    def test_wipe_component_info_handles_none_data(self) -> None:
        """
        wipe_component_info does nothing when vehicle_components_fs.data is None.

        GIVEN: vehicle_components_fs has no data (data is None)
        WHEN: wipe_component_info is called
        THEN: No exception should be raised
        AND: Nothing should be modified
        """
        vehicle_components = VehicleComponents()
        vehicle_components.vehicle_components_fs.data = None

        # Should not raise any exception
        vehicle_components.wipe_component_info()

        assert vehicle_components.vehicle_components_fs.data is None

    def test_merge_defaults_applies_default_when_key_missing(self) -> None:
        """
        merge_defaults sets default when key is not in target.

        GIVEN: A target dict missing a key that has a default value
        WHEN: wipe_component_info is called to reset to defaults
        THEN: The missing key should be set to its default value
        """
        vehicle_components = VehicleComponents()
        # Provide minimal data structure that wipe_component_info can work with
        data = {
            "Components": {
                "RC Receiver": {},  # Missing FC Connection
                "Battery": {
                    "Specifications": {}  # Missing Chemistry and other defaults
                },
                "Motors": {
                    "Specifications": {}  # Missing Poles
                },
                "GNSS Receiver": {},
                "Telemetry": {},
                "Battery Monitor": {},
                "ESC": {},
            }
        }
        vehicle_components.vehicle_components_fs.data = data

        vehicle_components.wipe_component_info()

        # After wipe, defaults should have been applied
        components = vehicle_components.vehicle_components_fs.data["Components"]
        assert "FC Connection" in components["RC Receiver"]
        assert "FC Connection" in components["GNSS Receiver"]
