#!/usr/bin/env python3

"""
Tests for the backend_filesystem_vehicle_components.py file.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import os.path
from json.decoder import JSONDecodeError as RealJSONDecodeError
from unittest.mock import mock_open, patch

import pytest

from ardupilot_methodic_configurator.backend_filesystem_vehicle_components import VehicleComponents
from ardupilot_methodic_configurator.data_model_template_overview import TemplateOverview

# pylint: disable=too-many-lines,too-many-public-methods,attribute-defined-outside-init


class TestVehicleComponents:
    """VehicleComponents test class."""

    @pytest.fixture(autouse=True)
    def setup(self) -> None:
        """Set up test fixtures."""
        self.vehicle_components = VehicleComponents()
        # Sample valid schema
        self.valid_schema = {
            "$schema": "http://json-schema.org/draft-07/schema#",
            "type": "object",
            "properties": {"Components": {"type": "object"}},
            "required": ["Components"],
        }
        # Sample valid component data
        self.valid_component_data = {
            "Components": {"Flight Controller": {"Firmware": {"Type": "ArduCopter", "Version": "4.3.0"}}}
        }
        # Sample invalid component data
        self.invalid_component_data: dict[str, dict] = {"WrongKey": {"Flight Controller": {}}}

        # Detailed schema with MCU Series for testing modify_schema_for_mcu_series
        self.schema_with_mcu_series = {  # pylint: disable=duplicate-code  # Schema fixture for MCU tests
            "$schema": "http://json-schema.org/draft-07/schema#",
            "definitions": {
                "flightController": {
                    "allOf": [
                        {
                            "properties": {
                                "Specifications": {
                                    "type": "object",
                                    "properties": {
                                        "MCU Series": {
                                            "type": "string",
                                            "description": "Microcontroller series used in the flight controller",
                                        }
                                    },
                                }
                            }
                        }
                    ]
                }
            },
            "properties": {
                "Components": {
                    "type": "object",
                    "properties": {"Flight Controller": {"$ref": "#/definitions/flightController"}},
                }
            },
        }
        # pylint: enable=duplicate-code

    @patch("ardupilot_methodic_configurator.backend_filesystem_vehicle_components.FilesystemJSONWithSchema")
    def test_load_schema(self, mock_fs_class) -> None:  # type: ignore[misc]
        """
        Test method.

        GIVEN: A VehicleComponents instance
        WHEN: User loads the JSON schema
        THEN: Should return the valid schema from FilesystemJSONWithSchema.
        """
        mock_fs = mock_fs_class.return_value
        mock_fs.load_schema.return_value = self.valid_schema

        # Create a new instance so it uses the mocked FilesystemJSONWithSchema
        vehicle_components = VehicleComponents()
        result = vehicle_components.load_schema()

        assert result == self.valid_schema
        mock_fs.load_schema.assert_called_once()

    @patch("ardupilot_methodic_configurator.backend_filesystem_vehicle_components.FilesystemJSONWithSchema")
    def test_validate_vehicle_components_valid(self, mock_fs_class) -> None:  # type: ignore[misc]
        """
        Test method.

        GIVEN: Valid vehicle components data
        WHEN: User validates the components against schema
        THEN: Should return success with no error message.
        """
        mock_fs = mock_fs_class.return_value
        mock_fs.validate_json_against_schema.return_value = (True, "")

        vehicle_components = VehicleComponents()
        is_valid, error_message = vehicle_components.validate_vehicle_components(self.valid_component_data)
        assert is_valid
        assert error_message == ""

    @patch("ardupilot_methodic_configurator.backend_filesystem_vehicle_components.FilesystemJSONWithSchema")
    def test_validate_vehicle_components_invalid(self, mock_fs_class) -> None:  # type: ignore[misc]
        """
        Test method.

        GIVEN: Invalid vehicle components data
        WHEN: User validates the components against schema
        THEN: Should return failure with validation error message.
        """
        mock_fs = mock_fs_class.return_value
        mock_fs.validate_json_against_schema.return_value = (False, "Validation error")

        vehicle_components = VehicleComponents()
        is_valid, error_message = vehicle_components.validate_vehicle_components(self.invalid_component_data)
        assert not is_valid
        assert "Validation error" in error_message

    @patch("ardupilot_methodic_configurator.backend_filesystem_vehicle_components.FilesystemJSONWithSchema")
    def test_load_vehicle_components_json_data(self, mock_fs_class) -> None:  # type: ignore[misc]
        """
        Test method.

        GIVEN: A directory path with vehicle components JSON file
        WHEN: User loads vehicle components data from the directory
        THEN: Should return the vehicle components data.
        """
        mock_fs = mock_fs_class.return_value
        mock_fs.load_json_data.return_value = self.valid_component_data

        vehicle_components = VehicleComponents()
        result = vehicle_components.load_vehicle_components_json_data("/test/dir")

        assert result == self.valid_component_data
        mock_fs.load_json_data.assert_called_once_with("/test/dir")

    @patch("ardupilot_methodic_configurator.backend_filesystem_vehicle_components.FilesystemJSONWithSchema")
    def test_save_vehicle_components_json_data_valid(self, mock_fs_class) -> None:  # type: ignore[misc]
        """
        Test method.

        GIVEN: Valid vehicle components data to save
        WHEN: User saves the data to a directory
        THEN: Should successfully save without errors.
        """
        mock_fs = mock_fs_class.return_value
        mock_fs.save_json_data.return_value = (False, "")

        vehicle_components = VehicleComponents()
        result, _msg = vehicle_components.save_vehicle_components_json_data(self.valid_component_data, "/test/dir")

        assert not result  # False means success
        mock_fs.save_json_data.assert_called_once_with(self.valid_component_data, "/test/dir")

    @patch("ardupilot_methodic_configurator.backend_filesystem_vehicle_components.FilesystemJSONWithSchema")
    def test_save_vehicle_components_json_data_invalid(self, mock_fs_class) -> None:  # type: ignore[misc]
        """
        Test method.

        GIVEN: Invalid vehicle components data
        WHEN: User attempts to save the data
        THEN: Should return error indicating validation failure.
        """
        mock_fs = mock_fs_class.return_value
        mock_fs.save_json_data.return_value = (True, "Validation error")

        vehicle_components = VehicleComponents()
        result, _msg = vehicle_components.save_vehicle_components_json_data(self.invalid_component_data, "/test/dir")

        assert result  # True means failure

    def test_get_fc_fw_type_from_vehicle_components_json(self) -> None:
        """
        Get Fc Fw Type From Vehicle Components Json.

        GIVEN: Vehicle components data with firmware information
        WHEN: User retrieves the flight controller firmware type
        THEN: Should return the firmware type or empty string if unsupported
        """
        self.vehicle_components.vehicle_components_fs.data = self.valid_component_data
        fw_type = self.vehicle_components.get_fc_fw_type_from_vehicle_components_json()
        assert fw_type == "ArduCopter"

        # Test with unsupported firmware type
        invalid_data = {"Components": {"Flight Controller": {"Firmware": {"Type": "UnsupportedType", "Version": "4.3.0"}}}}
        self.vehicle_components.vehicle_components_fs.data = invalid_data
        fw_type = self.vehicle_components.get_fc_fw_type_from_vehicle_components_json()
        assert fw_type == ""

    def test_get_fc_fw_version_from_vehicle_components_json(self) -> None:
        """
        Get Fc Fw Version From Vehicle Components Json.

        GIVEN: Vehicle components data with firmware version
        WHEN: User retrieves the flight controller firmware version
        THEN: Should return the version string or empty string if invalid format
        """
        self.vehicle_components.vehicle_components_fs.data = self.valid_component_data
        version = self.vehicle_components.get_fc_fw_version_from_vehicle_components_json()
        assert version == "4.3.0"

        # Test with invalid version format
        invalid_data = {
            "Components": {"Flight Controller": {"Firmware": {"Type": "ArduCopter", "Version": "invalid-version"}}}
        }
        self.vehicle_components.vehicle_components_fs.data = invalid_data
        version = self.vehicle_components.get_fc_fw_version_from_vehicle_components_json()
        assert version == ""

    def test_supported_vehicles(self) -> None:
        """
        Supported Vehicles.

        GIVEN: The VehicleComponents class
        WHEN: User requests list of supported vehicles
        THEN: Should return tuple with all supported vehicle types
        """
        supported = VehicleComponents.supported_vehicles()
        assert isinstance(supported, tuple)
        assert "ArduCopter" in supported
        assert "ArduPlane" in supported
        assert len(supported) >= 9  # Ensure all expected vehicles are present

    @patch("ardupilot_methodic_configurator.backend_filesystem_vehicle_components.os_walk")
    @patch("ardupilot_methodic_configurator.backend_filesystem_vehicle_components.os_path.relpath")
    @patch.object(VehicleComponents, "load_vehicle_components_json_data")
    @patch("ardupilot_methodic_configurator.backend_filesystem_program_settings.ProgramSettings.get_templates_base_dir")
    def test_get_vehicle_components_overviews(  # type: ignore[misc]
        self,
        mock_get_base_dir,
        mock_load_data,
        mock_relpath,
        mock_walk,
    ) -> None:
        """
        Get Vehicle Components Overviews.

        GIVEN: Template directories with vehicle_components.json files
        WHEN: User requests vehicle component overviews
        THEN: Should return dictionary of TemplateOverview objects for each vehicle
        """
        mock_get_base_dir.return_value = "/templates"
        mock_walk.return_value = [
            ("/templates/copter", [], ["vehicle_components.json"]),
            ("/templates/plane", [], ["vehicle_components.json"]),
        ]
        mock_relpath.side_effect = ["copter", "plane"]
        mock_load_data.side_effect = [
            {"Components": {"Flight Controller": {"Firmware": {"Type": "ArduCopter"}}}},
            {"Components": {"Flight Controller": {"Firmware": {"Type": "ArduPlane"}}}},
        ]

        result = VehicleComponents.get_vehicle_components_overviews()

        assert len(result) == 2
        assert "copter" in result
        assert "plane" in result
        assert isinstance(result["copter"], TemplateOverview)
        assert isinstance(result["plane"], TemplateOverview)

    @patch("ardupilot_methodic_configurator.backend_filesystem_program_settings.ProgramSettings.get_templates_base_dir")
    @patch("os.path.join")
    def test_get_vehicle_image_filepath(self, mock_join, mock_get_base_dir) -> None:  # type: ignore[misc]
        """
        Test method.

        GIVEN: A vehicle type directory name
        WHEN: User requests the image filepath for the vehicle
        THEN: Should return the full path to the vehicle image file.
        """
        mock_get_base_dir.return_value = "/templates"
        mock_join.return_value = "/templates/copter/vehicle.jpg"

        result = VehicleComponents.get_vehicle_image_filepath("copter")

        mock_get_base_dir.assert_called_once()
        mock_join.assert_called_once_with("/templates", "copter", "vehicle.jpg")
        assert result == "/templates/copter/vehicle.jpg"

    def test_wipe_component_info(self) -> None:
        """
        Wipe Component Info.

        GIVEN: Vehicle components data with various data types
        WHEN: User wipes all component information
        THEN: Should preserve structure but clear all values to defaults
        """
        # Test with nested dictionary containing various data types
        test_data = {
            "Components": {
                "Flight Controller": {
                    "Firmware": {"Type": "ArduCopter", "Version": "4.3.0"},
                    "Hardware": {"Model": "Pixhawk", "Ports": 5, "Sensors": ["GPS", "Barometer", "IMU"]},
                    "Options": {"Enabled": True, "Value": 42.5},
                }
            }
        }
        self.vehicle_components.vehicle_components_fs.data = test_data

        # Call the method to wipe
        self.vehicle_components.wipe_component_info()

        # Verify structure is preserved but values are cleared
        result = self.vehicle_components.vehicle_components_fs.data
        assert "Components" in result
        assert "Flight Controller" in result["Components"]
        assert "Firmware" in result["Components"]["Flight Controller"]
        assert result["Components"]["Flight Controller"]["Firmware"]["Type"] == ""
        assert result["Components"]["Flight Controller"]["Firmware"]["Version"] == ""
        assert result["Components"]["Flight Controller"]["Hardware"]["Model"] == ""
        assert result["Components"]["Flight Controller"]["Hardware"]["Ports"] == 0
        assert result["Components"]["Flight Controller"]["Hardware"]["Sensors"] == []
        assert result["Components"]["Flight Controller"]["Options"]["Enabled"] == 0
        assert result["Components"]["Flight Controller"]["Options"]["Value"] == 0.0

    @patch("ardupilot_methodic_configurator.backend_filesystem_vehicle_components.FilesystemJSONWithSchema")
    def test_save_vehicle_components_json_data_file_not_found(self, mock_fs_class) -> None:  # type: ignore[misc]
        """
        Test method.

        GIVEN: A nonexistent directory path
        WHEN: User attempts to save vehicle components data
        THEN: Should return error indicating file not found.
        """
        mock_fs = mock_fs_class.return_value
        mock_fs.save_json_data.return_value = (True, "File not found")

        vehicle_components = VehicleComponents()
        result, msg = vehicle_components.save_vehicle_components_json_data(self.valid_component_data, "/nonexistent/dir")

        assert result  # True means error
        assert "not found" in msg

    @patch("ardupilot_methodic_configurator.backend_filesystem_vehicle_components.FilesystemJSONWithSchema")
    def test_save_vehicle_components_json_data_permission_error(self, mock_fs_class) -> None:  # type: ignore[misc]
        """
        Test method.

        GIVEN: A directory without write permissions
        WHEN: User attempts to save vehicle components data
        THEN: Should return error indicating permission denied.
        """
        mock_fs = mock_fs_class.return_value
        mock_fs.save_json_data.return_value = (True, "Permission denied")

        vehicle_components = VehicleComponents()
        result, msg = vehicle_components.save_vehicle_components_json_data(self.valid_component_data, "/test/dir")

        assert result  # True means error
        assert "Permission denied" in msg

    @patch("ardupilot_methodic_configurator.backend_filesystem_vehicle_components.FilesystemJSONWithSchema")
    def test_save_vehicle_components_json_data_is_a_directory_error(self, mock_fs_class) -> None:  # type: ignore[misc]
        """
        Test method.

        GIVEN: A path that is a directory instead of a file
        WHEN: User attempts to save vehicle components data
        THEN: Should return error indicating path is a directory.
        """
        mock_fs = mock_fs_class.return_value
        mock_fs.save_json_data.return_value = (True, "path is a directory")

        vehicle_components = VehicleComponents()
        result, msg = vehicle_components.save_vehicle_components_json_data(self.valid_component_data, "/test/dir")

        assert result  # True means error
        assert "is a directory" in msg.lower()

    @patch("ardupilot_methodic_configurator.backend_filesystem_vehicle_components.FilesystemJSONWithSchema")
    def test_save_vehicle_components_json_data_os_error(self, mock_fs_class) -> None:  # type: ignore[misc]
        """
        Test method.

        GIVEN: An OS-level error condition (e.g., disk full)
        WHEN: User attempts to save vehicle components data
        THEN: Should return error with OS error message.
        """
        mock_fs = mock_fs_class.return_value
        mock_fs.save_json_data.return_value = (True, "OS error: Disk full")

        vehicle_components = VehicleComponents()
        result, msg = vehicle_components.save_vehicle_components_json_data(self.valid_component_data, "/test/dir")

        assert result  # True means error
        assert "OS error" in msg
        assert "Disk full" in msg

    @patch("ardupilot_methodic_configurator.backend_filesystem_vehicle_components.FilesystemJSONWithSchema")
    def test_save_vehicle_components_json_data_type_error(self, mock_fs_class) -> None:  # type: ignore[misc]
        """
        Test method.

        GIVEN: Invalid data type in vehicle components
        WHEN: User attempts to save the data
        THEN: Should return error indicating type error.
        """
        mock_fs = mock_fs_class.return_value
        mock_fs.save_json_data.return_value = (True, "Type error: Invalid type")

        vehicle_components = VehicleComponents()
        result, msg = vehicle_components.save_vehicle_components_json_data(self.valid_component_data, "/test/dir")

        assert result  # True means error
        assert "Type error" in msg
        assert "Invalid type" in msg

    @patch("ardupilot_methodic_configurator.backend_filesystem_vehicle_components.FilesystemJSONWithSchema")
    def test_save_vehicle_components_json_data_value_error(self, mock_fs_class) -> None:  # type: ignore[misc]
        """
        Test method.

        GIVEN: Vehicle components data with circular reference
        WHEN: User attempts to save the data
        THEN: Should return error indicating value error.
        """
        mock_fs = mock_fs_class.return_value
        mock_fs.save_json_data.return_value = (True, "Value error: Circular reference")

        vehicle_components = VehicleComponents()
        result, msg = vehicle_components.save_vehicle_components_json_data(self.valid_component_data, "/test/dir")

        assert result  # True means error
        assert "Value error" in msg
        assert "Circular reference" in msg

    @patch("ardupilot_methodic_configurator.backend_filesystem_program_settings.ProgramSettings.get_templates_base_dir")
    @patch("builtins.open", new_callable=mock_open)
    @patch("ardupilot_methodic_configurator.backend_filesystem_vehicle_components.json_load")
    def test_load_system_templates(self, mock_json_load, mock_file, mock_get_base_dir) -> None:  # type: ignore[misc]
        """
        Test method.

        GIVEN: System templates file exists in templates directory
        WHEN: User loads system templates
        THEN: Should return the system templates from the file.
        """
        system_templates = {
            "TestComponent": [
                {"name": "System Template 1", "data": {"param1": "value1"}},
                {"name": "System Template 2", "data": {"param2": "value2"}},
            ]
        }
        mock_json_load.return_value = system_templates
        mock_get_base_dir.return_value = "/app/path"

        # Call the method to load system templates
        result = self.vehicle_components._load_system_templates()  # pylint: disable=protected-access

        # Verify the result
        assert result == system_templates

        # Verify the correct path was used
        expected_path = os.path.join("/app/path", "system_vehicle_components_template.json")
        mock_file.assert_called_once_with(expected_path, encoding="utf-8-sig")
        mock_json_load.assert_called_once()

    @patch("ardupilot_methodic_configurator.backend_filesystem_program_settings.ProgramSettings.get_templates_base_dir")
    @patch("builtins.open", new_callable=mock_open)
    @patch("ardupilot_methodic_configurator.backend_filesystem_vehicle_components.json_load")
    def test_load_user_templates(self, mock_json_load, mock_file, mock_get_base_dir) -> None:  # type: ignore[misc]
        """
        Test method.

        GIVEN: User templates file exists in templates directory
        WHEN: User loads user-customized templates
        THEN: Should return the user templates from the file.
        """
        user_templates = {"TestComponent": [{"name": "User Template", "data": {"param1": "custom"}}]}
        mock_json_load.return_value = user_templates
        mock_get_base_dir.return_value = "/user/templates"

        # Call the method to load user templates
        result = self.vehicle_components._load_user_templates()  # pylint: disable=protected-access

        # Verify the result
        assert result == user_templates

        # Verify the file was opened from the correct location
        expected_path = os.path.join("/user/templates", "user_vehicle_components_template.json")
        mock_file.assert_called_once_with(expected_path, encoding="utf-8-sig")
        mock_json_load.assert_called_once()

    @patch.object(VehicleComponents, "_load_system_templates")
    @patch.object(VehicleComponents, "_load_user_templates")
    def test_load_component_templates_merge(self, mock_load_user, mock_load_system) -> None:  # type: ignore[misc]
        """
        Test method.

        GIVEN: Both system and user templates exist with some overlapping names
        WHEN: User loads component templates
        THEN: Should merge templates with user templates overriding system ones and mark them as modified.
        """
        # Setup system templates
        system_templates = {
            "Component1": [
                {"name": "Template A", "data": {"original": "value"}},
                {"name": "Template B", "data": {"system": "value"}},
            ],
            "Component2": [{"name": "System Only", "data": {"system": "unchanged"}}],
        }

        # Setup user templates with one overriding system template and one new template
        user_templates = {
            "Component1": [
                {"name": "Template A", "data": {"modified": "value"}},  # Overrides system template
                {"name": "User Only", "data": {"user": "value"}},  # New template
            ]
        }

        mock_load_system.return_value = system_templates
        mock_load_user.return_value = user_templates

        # Call the method to load and merge templates
        result = self.vehicle_components.load_component_templates()

        # Verify system templates were loaded
        assert "Component1" in result
        assert "Component2" in result

        # Verify Component1 has all templates (2 from system, 1 new from user)
        component1_templates = result["Component1"]
        assert len(component1_templates) == 3

        # Find templates by name
        template_a = next((t for t in component1_templates if t["name"] == "Template A"), None)
        template_b = next((t for t in component1_templates if t["name"] == "Template B"), None)
        user_only = next((t for t in component1_templates if t["name"] == "User Only"), None)

        # Verify Template A was overridden by user template
        assert template_a is not None
        assert template_a["data"]["modified"] == "value"
        assert "original" not in template_a["data"]
        assert template_a.get("is_user_modified") is True

        # Verify Template B remains unchanged
        assert template_b is not None
        assert template_b["data"]["system"] == "value"

        # Verify new user template was added
        assert user_only is not None
        assert user_only["data"]["user"] == "value"
        assert user_only.get("is_user_modified") is True

        # Verify Component2 templates remain unchanged
        assert len(result["Component2"]) == 1
        assert result["Component2"][0]["name"] == "System Only"
        assert result["Component2"][0]["data"]["system"] == "unchanged"

    @patch("builtins.open", new_callable=mock_open)
    @patch("ardupilot_methodic_configurator.backend_filesystem_vehicle_components.json_load")
    @patch("ardupilot_methodic_configurator.backend_filesystem_vehicle_components.logging_debug")
    def test_load_user_templates_file_not_found(self, mock_logging_debug, mock_json_load, mock_file) -> None:  # type: ignore[misc] # pylint: disable=unused-argument
        """
        Test method.

        GIVEN: User templates file does not exist
        WHEN: User attempts to load user templates
        THEN: Should return empty dict and log debug message.
        """
        # Setup the mock to raise FileNotFoundError
        mock_file.side_effect = FileNotFoundError()

        # Call the method - this should handle the exception internally
        result = self.vehicle_components._load_user_templates()  # pylint: disable=protected-access

        # Verify an empty dict is returned
        assert result == {}
        # Verify the logging message was called
        mock_logging_debug.assert_called_once()
        assert "not found" in str(mock_logging_debug.call_args)

    @patch.object(VehicleComponents, "_load_system_templates")
    @patch.object(VehicleComponents, "_load_user_templates")
    def test_load_component_templates_no_user_templates(self, mock_load_user, mock_load_system) -> None:  # type: ignore[misc]
        """
        Test method.

        GIVEN: Only system templates exist, no user templates
        WHEN: User loads component templates
        THEN: Should return only system templates without modification flags.
        """
        system_templates = {"Component1": [{"name": "System Template", "data": {"param": "value"}}]}

        mock_load_system.return_value = system_templates
        mock_load_user.return_value = {}

        # Call the method
        result = self.vehicle_components.load_component_templates()

        # Verify only system templates are returned, unmodified
        assert result == system_templates
        assert not result["Component1"][0].get("is_user_modified", False)

    @patch.object(VehicleComponents, "_load_system_templates")
    @patch.object(VehicleComponents, "_load_user_templates")
    def test_load_component_templates_no_system_templates(  # type: ignore[misc]
        self,
        mock_load_user,
        mock_load_system,
    ) -> None:
        """
        Load Component Templates No System Templates.

        GIVEN: Only user templates exist, no system templates
        WHEN: User loads component templates
        THEN: Should return only user templates with modification flags
        """
        user_templates = {"Component1": [{"name": "User Template", "data": {"param": "value"}}]}

        mock_load_system.return_value = {}
        mock_load_user.return_value = user_templates

        # Call the method
        result = self.vehicle_components.load_component_templates()

        # Verify user templates are returned with is_user_modified flag
        assert "Component1" in result
        assert len(result["Component1"]) == 1
        assert result["Component1"][0]["name"] == "User Template"
        assert result["Component1"][0]["is_user_modified"] is True

    @patch.object(VehicleComponents, "_load_system_templates")
    @patch.object(VehicleComponents, "_load_user_templates")
    @patch("builtins.open", new_callable=mock_open)
    @patch("ardupilot_methodic_configurator.backend_filesystem_vehicle_components.json_dump")
    @patch("ardupilot_methodic_configurator.backend_filesystem_vehicle_components.os_makedirs")
    @patch("ardupilot_methodic_configurator.backend_filesystem_program_settings.ProgramSettings.get_templates_base_dir")
    def test_save_component_templates_basic(  # type: ignore[misc] # pylint: disable=too-many-arguments, too-many-positional-arguments
        self, mock_get_base_dir, mock_makedirs, mock_json_dump, mock_file, mock_load_user, mock_load_system
    ) -> None:
        """
        Save Component Templates Basic.

        GIVEN: User-modified component templates to save
        WHEN: User saves the templates
        THEN: Should save to user templates file with modification flags removed
        """
        # Setup
        mock_get_base_dir.return_value = "/templates"
        mock_load_system.return_value = {}
        mock_load_user.return_value = {}

        templates = {"Component1": [{"name": "Test Template", "data": {"param": "value"}, "is_user_modified": True}]}

        # Call method
        result, msg = self.vehicle_components.save_component_templates(templates)

        # Verify results
        assert not result  # False means success
        assert msg == ""

        # Verify directory was created
        mock_makedirs.assert_called_once_with("/templates", exist_ok=True)

        # Verify file was opened correctly
        expected_path = os.path.join("/templates", "user_vehicle_components_template.json")
        mock_file.assert_called_once_with(expected_path, "w", encoding="utf-8")

        # Verify JSON was dumped with is_user_modified flag removed
        expected_save = {"Component1": [{"name": "Test Template", "data": {"param": "value"}}]}
        mock_json_dump.assert_called_once()
        args, kwargs = mock_json_dump.call_args
        assert args[0] == expected_save  # First argument should be the data
        assert kwargs["indent"] == 4

    @patch.object(VehicleComponents, "_load_system_templates")
    @patch.object(VehicleComponents, "_load_user_templates")
    @patch("builtins.open", new_callable=mock_open)
    @patch("ardupilot_methodic_configurator.backend_filesystem_vehicle_components.json_dump")
    @patch("ardupilot_methodic_configurator.backend_filesystem_vehicle_components.os_makedirs")
    @patch("ardupilot_methodic_configurator.backend_filesystem_program_settings.ProgramSettings.get_templates_base_dir")
    def test_save_component_templates_only_modified(  # type: ignore[misc] # pylint: disable=too-many-arguments, too-many-positional-arguments
        self,
        mock_get_base_dir,
        mock_makedirs,  # pylint: disable=unused-argument
        mock_json_dump,
        mock_file,  # pylint: disable=unused-argument
        mock_load_user,
        mock_load_system,
    ) -> None:
        """
        Save Component Templates Only Modified.

        GIVEN: Mix of modified and unmodified templates
        WHEN: User saves component templates
        THEN: Should save only templates marked as user-modified
        """
        # Setup system templates
        system_templates = {
            "Component1": [
                {"name": "Template A", "data": {"original": "value"}},
                {"name": "Template B", "data": {"system": "value"}},
            ]
        }

        # Setup templates with one modified and one unmodified
        templates = {
            "Component1": [
                {"name": "Template A", "data": {"original": "value"}, "is_user_modified": True},  # Modified flag
                {"name": "Template B", "data": {"system": "value"}},  # No modification
            ]
        }

        mock_get_base_dir.return_value = "/templates"
        mock_load_system.return_value = system_templates
        mock_load_user.return_value = {}

        # Call method
        result, msg = self.vehicle_components.save_component_templates(templates)

        # Verify results
        assert not result  # False means success
        assert msg == ""

        # Verify only Template A was saved (with is_user_modified flag removed)
        expected_save = {"Component1": [{"name": "Template A", "data": {"original": "value"}}]}
        mock_json_dump.assert_called_once()
        args, _kwargs = mock_json_dump.call_args
        assert args[0] == expected_save

    @patch.object(VehicleComponents, "_load_system_templates")
    @patch.object(VehicleComponents, "_load_user_templates")
    @patch("builtins.open", new_callable=mock_open)
    @patch("ardupilot_methodic_configurator.backend_filesystem_vehicle_components.json_dump")
    @patch("ardupilot_methodic_configurator.backend_filesystem_vehicle_components.os_makedirs")
    @patch("ardupilot_methodic_configurator.backend_filesystem_program_settings.ProgramSettings.get_templates_base_dir")
    def test_save_component_templates_different_data(  # type: ignore[misc] # pylint: disable=too-many-arguments, too-many-positional-arguments
        self,
        mock_get_base_dir,
        mock_makedirs,  # pylint: disable=unused-argument
        mock_json_dump,
        mock_file,  # pylint: disable=unused-argument
        mock_load_user,
        mock_load_system,
    ) -> None:
        """
        Save Component Templates Different Data.

        GIVEN: Templates with data different from system templates
        WHEN: User saves component templates
        THEN: Should detect data changes and save modified templates
        """
        # Setup system templates
        system_templates = {"Component1": [{"name": "Template A", "data": {"original": "value"}}]}

        # Setup templates with modified data but no is_user_modified flag
        templates = {
            "Component1": [
                {"name": "Template A", "data": {"modified": "new_value"}}  # Different data
            ]
        }

        mock_get_base_dir.return_value = "/templates"
        mock_load_system.return_value = system_templates
        mock_load_user.return_value = {}

        # Call method
        result, msg = self.vehicle_components.save_component_templates(templates)

        # Verify results
        assert not result  # False means success
        assert msg == ""

        # Verify Template A was saved with new data
        expected_save = {"Component1": [{"name": "Template A", "data": {"modified": "new_value"}}]}
        mock_json_dump.assert_called_once()
        args, _kwargs = mock_json_dump.call_args
        assert args[0] == expected_save

    @patch.object(VehicleComponents, "_load_system_templates")
    @patch.object(VehicleComponents, "_load_user_templates")
    @patch("builtins.open", new_callable=mock_open)
    @patch("ardupilot_methodic_configurator.backend_filesystem_vehicle_components.json_dump")
    @patch("ardupilot_methodic_configurator.backend_filesystem_vehicle_components.os_makedirs")
    @patch("ardupilot_methodic_configurator.backend_filesystem_program_settings.ProgramSettings.get_templates_base_dir")
    def test_save_component_templates_not_in_system(  # type: ignore[misc] # pylint: disable=too-many-arguments, too-many-positional-arguments
        self,
        mock_get_base_dir,
        mock_makedirs,  # pylint: disable=unused-argument
        mock_json_dump,
        mock_file,  # pylint: disable=unused-argument
        mock_load_user,
        mock_load_system,
    ) -> None:
        """
        Save Component Templates Not In System.

        GIVEN: Templates including new ones not in system templates
        WHEN: User saves component templates
        THEN: Should save only new templates not present in system
        """
        # Setup system templates
        system_templates = {"Component1": [{"name": "System Template", "data": {"system": "value"}}]}

        # Setup templates with one new template not in system
        templates = {
            "Component1": [
                {"name": "System Template", "data": {"system": "value"}},
                {"name": "New Template", "data": {"new": "value"}},  # Not in system
            ]
        }

        mock_get_base_dir.return_value = "/templates"
        mock_load_system.return_value = system_templates
        mock_load_user.return_value = {}

        # Call method
        result, msg = self.vehicle_components.save_component_templates(templates)

        # Verify results
        assert not result  # False means success
        assert msg == ""

        # Verify only the new template was saved
        expected_save = {"Component1": [{"name": "New Template", "data": {"new": "value"}}]}
        mock_json_dump.assert_called_once()
        args, _kwargs = mock_json_dump.call_args
        assert args[0] == expected_save

    @patch.object(VehicleComponents, "_load_system_templates")
    @patch.object(VehicleComponents, "_load_user_templates")
    @patch("ardupilot_methodic_configurator.backend_filesystem_vehicle_components.os_makedirs")
    @patch("ardupilot_methodic_configurator.backend_filesystem_program_settings.ProgramSettings.get_templates_base_dir")
    def test_save_component_templates_directory_error(  # type: ignore[misc]
        self, mock_get_base_dir, mock_makedirs, mock_load_user, mock_load_system
    ) -> None:
        """
        Save Component Templates Directory Error.

        GIVEN: Directory creation fails with OSError
        WHEN: User attempts to save component templates
        THEN: Should return error indicating directory creation failure
        """
        mock_get_base_dir.return_value = "/templates"
        mock_load_system.return_value = {}
        mock_load_user.return_value = {}
        mock_makedirs.side_effect = OSError("Permission denied")

        templates = {"Component1": [{"name": "Test Template", "data": {"param": "value"}, "is_user_modified": True}]}

        # Call method
        result, msg = self.vehicle_components.save_component_templates(templates)

        # Verify results
        assert result  # True means error
        assert "Failed to create templates directory" in msg
        assert "Permission denied" in msg

    @patch.object(VehicleComponents, "_load_system_templates")
    @patch.object(VehicleComponents, "_load_user_templates")
    @patch("builtins.open", new_callable=mock_open)
    @patch("ardupilot_methodic_configurator.backend_filesystem_vehicle_components.json_dump")
    @patch("ardupilot_methodic_configurator.backend_filesystem_vehicle_components.os_makedirs")
    @patch("ardupilot_methodic_configurator.backend_filesystem_program_settings.ProgramSettings.get_templates_base_dir")
    def test_save_component_templates_directory_creation_error(  # type: ignore[misc] # pylint: disable=too-many-arguments, too-many-positional-arguments
        self, mock_get_base_dir, mock_makedirs, mock_json_dump, mock_file, mock_load_user, mock_load_system
    ) -> None:
        """
        Save Component Templates Directory Creation Error.

        GIVEN: Directory creation fails with PermissionError
        WHEN: User attempts to save templates
        THEN: Should return error and skip file operations
        """
        mock_get_base_dir.return_value = "/templates"
        mock_makedirs.side_effect = PermissionError("Access denied")
        mock_load_system.return_value = {}
        mock_load_user.return_value = {}

        templates = {"Component1": [{"name": "Test Template", "data": {"param": "value"}}]}

        # Call method
        result, msg = self.vehicle_components.save_component_templates(templates)

        # Verify error handling
        assert result  # True means error
        assert "Failed to create templates directory" in msg
        assert "Access denied" in msg
        mock_file.assert_not_called()
        mock_json_dump.assert_not_called()

    @patch.object(VehicleComponents, "_load_system_templates")
    @patch.object(VehicleComponents, "_load_user_templates")
    @patch("builtins.open")
    @patch("ardupilot_methodic_configurator.backend_filesystem_vehicle_components.json_dump")
    @patch("ardupilot_methodic_configurator.backend_filesystem_vehicle_components.os_makedirs")
    @patch("ardupilot_methodic_configurator.backend_filesystem_program_settings.ProgramSettings.get_templates_base_dir")
    def test_save_component_templates_file_errors(  # type: ignore[misc] # pylint: disable=too-many-arguments, too-many-positional-arguments
        self,
        mock_get_base_dir,
        mock_makedirs,  # pylint: disable=unused-argument
        mock_json_dump,  # pylint: disable=unused-argument
        mock_file,
        mock_load_user,
        mock_load_system,
    ) -> None:
        """
        Save Component Templates File Errors.

        GIVEN: File write operation fails with PermissionError
        WHEN: User attempts to save templates
        THEN: Should return error indicating permission denied
        """
        mock_get_base_dir.return_value = "/templates"
        mock_load_system.return_value = {}
        mock_load_user.return_value = {}

        # Test permission error
        mock_file.side_effect = PermissionError()

        templates = {"Component1": [{"name": "Test Template", "data": {"param": "value"}}]}

        # Call method
        result, msg = self.vehicle_components.save_component_templates(templates)

        # Verify error handling
        assert result  # True means error
        assert "Permission denied" in msg

    @patch.object(VehicleComponents, "_load_system_templates")
    @patch.object(VehicleComponents, "_load_user_templates")
    @patch("builtins.open", new_callable=mock_open)
    @patch("ardupilot_methodic_configurator.backend_filesystem_vehicle_components.json_dump")
    @patch("ardupilot_methodic_configurator.backend_filesystem_vehicle_components.os_makedirs")
    @patch("ardupilot_methodic_configurator.backend_filesystem_program_settings.ProgramSettings.get_templates_base_dir")
    def test_save_component_templates_empty_input(  # type: ignore[misc] # pylint: disable=too-many-arguments, too-many-positional-arguments
        self,
        mock_get_base_dir,
        mock_makedirs,  # pylint: disable=unused-argument
        mock_json_dump,
        mock_file,
        mock_load_user,
        mock_load_system,
    ) -> None:
        """
        Save Component Templates Empty Input.

        GIVEN: Empty templates dictionary
        WHEN: User saves component templates
        THEN: Should save empty dictionary successfully
        """
        mock_get_base_dir.return_value = "/templates"
        mock_load_system.return_value = {}
        mock_load_user.return_value = {}

        # Call method with empty dictionary
        result, msg = self.vehicle_components.save_component_templates({})

        # Verify results
        assert not result  # False means success
        assert msg == ""
        # Should save empty dict
        mock_json_dump.assert_called_once_with({}, mock_file(), indent=4)

    @patch.object(VehicleComponents, "_load_system_templates")
    @patch.object(VehicleComponents, "_load_user_templates")
    @patch("builtins.open", new_callable=mock_open)
    @patch("ardupilot_methodic_configurator.backend_filesystem_vehicle_components.json_dump")
    @patch("ardupilot_methodic_configurator.backend_filesystem_vehicle_components.os_makedirs")
    @patch("ardupilot_methodic_configurator.backend_filesystem_program_settings.ProgramSettings.get_templates_base_dir")
    def test_save_component_templates_json_error(  # type: ignore[misc] # pylint: disable=too-many-arguments, too-many-positional-arguments
        self,
        mock_get_base_dir,
        mock_makedirs,  # pylint: disable=unused-argument
        mock_json_dump,
        mock_file,  # pylint: disable=unused-argument
        mock_load_user,
        mock_load_system,
    ) -> None:
        """
        Save Component Templates Json Error.

        GIVEN: Templates that cause JSON serialization error
        WHEN: User attempts to save the templates
        THEN: Should return error indicating serialization failure
        """
        mock_get_base_dir.return_value = "/templates"
        mock_load_system.return_value = {}
        mock_load_user.return_value = {}
        mock_json_dump.side_effect = TypeError("Cannot serialize circular reference")

        templates = {"Component1": [{"name": "Test Template", "data": {"param": "value"}}]}

        # Call method
        result, msg = self.vehicle_components.save_component_templates(templates)

        # Verify error handling
        assert result  # True means error
        assert "Unexpected error" in msg
        assert "Cannot serialize circular reference" in msg

    @patch.object(VehicleComponents, "_load_system_templates")
    @patch.object(VehicleComponents, "save_component_templates_to_file")
    def test_save_component_templates_to_system(  # type: ignore[misc]
        self, mock_save_to_file, mock_load_system
    ) -> None:
        """
        Save Component Templates To System.

        GIVEN: Instance configured to save to system templates
        WHEN: User saves component templates
        THEN: Should merge new templates with existing system templates
        """
        # Setup system templates
        system_templates = {"ExistingComponent": [{"name": "Existing Template", "data": {"param": "value"}}]}

        # Setup new templates to save
        new_templates = {"NewComponent": [{"name": "New Template", "data": {"param": "new_value"}}]}

        # Set up the instance to save to system templates
        self.vehicle_components.save_component_to_system_templates = True

        # Mock loading system templates
        mock_load_system.return_value = system_templates
        mock_save_to_file.return_value = (False, "")  # No error

        # Call the method
        result, msg = self.vehicle_components.save_component_templates(new_templates)

        # Verify success
        assert not result  # False means success
        assert msg == ""

        # Capture what was passed to save_component_templates_to_file
        saved_templates = mock_save_to_file.call_args[0][0]

        # Verify that system templates and new templates were merged
        assert "ExistingComponent" in saved_templates
        assert "NewComponent" in saved_templates

        # Verify existing component was preserved
        assert len(saved_templates["ExistingComponent"]) == 1
        assert saved_templates["ExistingComponent"][0]["name"] == "Existing Template"

        # Verify new component was added
        assert len(saved_templates["NewComponent"]) == 1
        assert saved_templates["NewComponent"][0]["name"] == "New Template"
        assert saved_templates["NewComponent"][0]["data"]["param"] == "new_value"

    @patch("ardupilot_methodic_configurator.backend_filesystem_vehicle_components.FilesystemJSONWithSchema")
    def test_load_schema_invalid_json(self, mock_fs_class) -> None:
        """
        Load Schema Invalid Json.

        GIVEN: Schema file contains invalid JSON
        WHEN: User loads the schema
        THEN: Should return empty dictionary without crashing
        """
        mock_fs = mock_fs_class.return_value
        mock_fs.load_schema.return_value = {}  # FilesystemJSONWithSchema returns empty dict on error

        vehicle_components = VehicleComponents()
        result = vehicle_components.load_schema()

        # Verify an empty dict is returned
        assert result == {}

    @patch("ardupilot_methodic_configurator.backend_filesystem_vehicle_components.os_path.relpath")
    @patch("ardupilot_methodic_configurator.backend_filesystem_vehicle_components.os_walk")
    @patch("ardupilot_methodic_configurator.backend_filesystem_program_settings.ProgramSettings.get_templates_base_dir")
    def test_get_vehicle_components_overviews_empty(self, mock_get_base_dir, mock_walk, mock_relpath) -> None:
        """
        Get Vehicle Components Overviews Empty.

        GIVEN: No template directories exist
        WHEN: User requests vehicle component overviews
        THEN: Should return empty dictionary
        """
        # Setup
        mock_get_base_dir.return_value = "/templates"
        mock_walk.return_value = []  # No directories found

        # Call the method
        result = VehicleComponents.get_vehicle_components_overviews()

        # Verify an empty dict is returned
        assert not result
        mock_walk.assert_called_once_with("/templates")
        mock_relpath.assert_not_called()

    @patch("ardupilot_methodic_configurator.backend_filesystem_vehicle_components.os_walk")
    @patch("ardupilot_methodic_configurator.backend_filesystem_program_settings.ProgramSettings.get_templates_base_dir")
    def test_get_vehicle_components_overviews_no_components_files(self, mock_get_base_dir, mock_walk) -> None:
        """
        Get Vehicle Components Overviews No Components Files.

        GIVEN: Directories exist but contain no vehicle_components.json files
        WHEN: User requests vehicle component overviews
        THEN: Should return empty dictionary
        """
        # Setup
        mock_get_base_dir.return_value = "/templates"
        mock_walk.return_value = [("/templates/dir1", [], ["other_file.txt"]), ("/templates/dir2", [], ["another_file.json"])]

        # Call the method
        result = VehicleComponents.get_vehicle_components_overviews()

        # Verify an empty dict is returned since no vehicle_components.json files were found
        assert not result

    def test_json_load_error_handling(self) -> None:
        """
        Json Load Error Handling.

        GIVEN: JSON files with various error conditions
        WHEN: User loads vehicle components data
        THEN: Should handle errors gracefully and return appropriate values
        """
        # Test with broken JSON that generates a JSONDecodeError
        broken_json = '{"broken": "json",}'

        with (
            patch("builtins.open", mock_open(read_data=broken_json)),
            patch(
                "ardupilot_methodic_configurator.backend_filesystem_vehicle_components.json_load",
                side_effect=RealJSONDecodeError("Expecting ',' delimiter", broken_json, 15),
            ),
        ):
            result = self.vehicle_components.load_vehicle_components_json_data("/test/dir")
            assert result == {}  # Should return empty dict on error

        # Test with valid JSON but invalid schema
        with (
            patch("builtins.open", mock_open(read_data='{"valid": "json"}')),
            patch(
                "ardupilot_methodic_configurator.backend_filesystem_vehicle_components.json_load",
                return_value={"valid": "json"},
            ),
            patch.object(VehicleComponents, "validate_vehicle_components", return_value=(False, "Schema validation error")),
        ):
            # Should still return the data even if validation fails
            result = self.vehicle_components.load_vehicle_components_json_data("/test/dir")
            assert result == {"valid": "json"}

    @patch.object(VehicleComponents, "_load_system_templates")
    @patch.object(VehicleComponents, "save_component_templates_to_file")
    def test_save_component_templates_user_modified_flag(self, mock_save_to_file, mock_load_system) -> None:
        """
        Save Component Templates User Modified Flag.

        GIVEN: Templates with is_user_modified flag set
        WHEN: User saves the templates
        THEN: Should save templates but remove the is_user_modified flag
        """
        # Setup system templates
        system_templates = {
            "Component1": [{"name": "System Template", "data": {"param": "system_value"}}],
        }

        # Setup templates with user-modified flag
        templates_with_flag = {
            "Component1": [{"name": "Modified Template", "data": {"param": "user_value"}, "is_user_modified": True}],
        }

        mock_load_system.return_value = system_templates
        mock_save_to_file.return_value = (False, "")

        # Call the method
        result, msg = self.vehicle_components.save_component_templates(templates_with_flag)

        # Verify success
        assert not result
        assert msg == ""

        # pylint: disable=duplicate-code  # Common assertion pattern
        # Get the templates that were saved
        saved_templates = mock_save_to_file.call_args[0][0]

        # Verify user-modified template was saved without the flag
        assert "Component1" in saved_templates
        assert len(saved_templates["Component1"]) == 1
        # pylint: enable=duplicate-code
        assert saved_templates["Component1"][0]["name"] == "Modified Template"
        assert "is_user_modified" not in saved_templates["Component1"][0]

    @patch.object(VehicleComponents, "_load_system_templates")
    @patch.object(VehicleComponents, "save_component_templates_to_file")
    def test_save_component_templates_data_comparison(self, mock_save_to_file, mock_load_system) -> None:
        """
        Save Component Templates Data Comparison.

        GIVEN: Templates with data different from system templates
        WHEN: User saves the templates
        THEN: Should detect data changes and save modified templates
        """
        # Setup system templates
        system_templates = {
            "Component1": [{"name": "Template A", "data": {"param": "original"}}],
        }

        # Setup templates with modified data
        modified_templates = {
            "Component1": [{"name": "Template A", "data": {"param": "modified"}}],  # Data is different
        }

        mock_load_system.return_value = system_templates
        mock_save_to_file.return_value = (False, "")

        # Call the method
        result, msg = self.vehicle_components.save_component_templates(modified_templates)

        # Verify success
        assert not result
        assert msg == ""

        # Get the templates that were saved
        saved_templates = mock_save_to_file.call_args[0][0]

        # Verify modified template was saved because data differs
        assert "Component1" in saved_templates
        assert len(saved_templates["Component1"]) == 1
        assert saved_templates["Component1"][0]["data"]["param"] == "modified"

    @patch.object(VehicleComponents, "_load_system_templates")
    @patch.object(VehicleComponents, "save_component_templates_to_file")
    def test_save_component_templates_identical_data_not_saved(self, mock_save_to_file, mock_load_system) -> None:
        """
        Save Component Templates Identical Data Not Saved.

        GIVEN: Templates with data identical to system templates
        WHEN: User saves the templates
        THEN: Should not save templates since they match system defaults
        """
        # Setup system templates
        system_templates = {
            "Component1": [{"name": "Template A", "data": {"param": "value"}}],
        }

        # Setup templates with identical data (no is_user_modified flag)
        identical_templates = {
            "Component1": [{"name": "Template A", "data": {"param": "value"}}],  # Data is identical
        }

        mock_load_system.return_value = system_templates
        mock_save_to_file.return_value = (False, "")

        # Call the method
        result, msg = self.vehicle_components.save_component_templates(identical_templates)

        # Verify success
        assert not result
        assert msg == ""

        # Get the templates that were saved
        saved_templates = mock_save_to_file.call_args[0][0]

        # Verify component entry was removed because template is identical to system
        assert "Component1" not in saved_templates

    @patch("ardupilot_methodic_configurator.backend_filesystem_vehicle_components.FilesystemJSONWithSchema")
    def test_get_fc_fw_version_invalid_format(self, mock_fs_class) -> None:
        """
        Get Fc Fw Version Invalid Format.

        GIVEN: Firmware version in invalid format with too many parts
        WHEN: User retrieves firmware version
        THEN: Should return empty string for invalid format
        """
        mock_fs = mock_fs_class.return_value
        mock_fs.data = {"Components": {"Flight Controller": {"Firmware": {"Version": "invalid.version.format.extra"}}}}

        vehicle_components = VehicleComponents()
        version = vehicle_components.get_fc_fw_version_from_vehicle_components_json()

        # Verify empty string is returned for invalid format
        assert version == ""

    @patch("ardupilot_methodic_configurator.backend_filesystem_vehicle_components.FilesystemJSONWithSchema")
    def test_get_fc_fw_version_with_whitespace_and_extra_text(self, mock_fs_class) -> None:
        """
        Get Fc Fw Version With Whitespace And Extra Text.

        GIVEN: Firmware version with leading whitespace and extra text
        WHEN: User retrieves firmware version
        THEN: Should extract and return clean version number
        """
        mock_fs = mock_fs_class.return_value
        mock_fs.data = {"Components": {"Flight Controller": {"Firmware": {"Version": "  4.5.1 dev-build"}}}}

        vehicle_components = VehicleComponents()
        version = vehicle_components.get_fc_fw_version_from_vehicle_components_json()

        # Verify version is correctly extracted
        assert version == "4.5.1"

    @patch("ardupilot_methodic_configurator.backend_filesystem_vehicle_components.FilesystemJSONWithSchema")
    def test_wipe_component_info_with_defaults_merge(self, mock_fs_class) -> None:
        """
        Wipe Component Info With Defaults Merge.

        GIVEN: Component data missing some default components
        WHEN: User wipes component info
        THEN: Should merge in all default components while clearing existing ones
        """
        mock_fs = mock_fs_class.return_value
        # Setup data with some existing components but missing defaults
        mock_fs.data = {
            "Components": {
                "Flight Controller": {"Firmware": {"Type": "ArduCopter"}},
                # Missing RC Receiver, Telemetry, etc.
            }
        }

        vehicle_components = VehicleComponents()
        vehicle_components.wipe_component_info()

        # Verify default components were merged
        components = mock_fs.data["Components"]
        assert "RC Receiver" in components
        assert "Telemetry" in components
        assert "Battery Monitor" in components
        assert "Battery" in components
        assert "ESC" in components
        assert "Motors" in components
        assert "GNSS Receiver" in components

        # Verify existing component was preserved but cleared
        assert "Flight Controller" in components
        assert components["Flight Controller"]["Firmware"]["Type"] == ""

    @patch("ardupilot_methodic_configurator.backend_filesystem_vehicle_components.FilesystemJSONWithSchema")
    def test_wipe_component_info_preserves_nested_defaults(self, mock_fs_class) -> None:
        """
        Wipe Component Info Preserves Nested Defaults.

        GIVEN: Component data with partial nested specifications
        WHEN: User wipes component info
        THEN: Should merge nested default values while preserving structure
        """
        mock_fs = mock_fs_class.return_value
        mock_fs.data = {
            "Components": {
                "Battery": {
                    "Specifications": {
                        # Only has some fields, missing others
                        "Chemistry": "Custom"
                    }
                }
            }
        }

        vehicle_components = VehicleComponents()
        vehicle_components.wipe_component_info()

        # Verify nested defaults were merged
        battery_specs = mock_fs.data["Components"]["Battery"]["Specifications"]
        # Chemistry was cleared by _recursively_clear_dict but then default "Lipo" was merged
        assert battery_specs["Chemistry"] == "Lipo"  # Default value merged in
        assert "Volt per cell max" in battery_specs  # Default added
        assert battery_specs["Volt per cell max"] == 4.2
        assert "Volt per cell low" in battery_specs
        assert battery_specs["Volt per cell low"] == 3.6

    @patch.object(VehicleComponents, "_load_system_templates")
    @patch.object(VehicleComponents, "save_component_templates_to_file")
    def test_save_component_templates_to_system_with_new_template(self, mock_save_to_file, mock_load_system) -> None:
        """
        Save Component Templates To System With New Template.

        GIVEN: Instance configured to save to system templates with new templates to add
        WHEN: User saves component templates
        THEN: Should add new templates to existing system templates
        """
        # Create instance configured to save to system templates
        vehicle_components_system = VehicleComponents(save_component_to_system_templates=True)

        # Setup existing system templates
        system_templates = {
            "Component1": [{"name": "Existing Template", "data": {"param": "value"}}],
        }

        # Setup new templates to add to system
        new_templates = {
            "Component1": [
                {"name": "Existing Template", "data": {"param": "value"}},  # Same as system, won't be added
                {"name": "New Template", "data": {"param": "new_value"}},  # Will be added
            ],
        }

        # pylint: disable=duplicate-code  # Common assertion pattern
        mock_load_system.return_value = system_templates
        mock_save_to_file.return_value = (False, "")

        # Call the method
        result, msg = vehicle_components_system.save_component_templates(new_templates)

        # Verify success
        assert not result
        assert msg == ""

        # Get the templates that were saved
        saved_templates = mock_save_to_file.call_args[0][0]

        # Verify new template was added to system templates
        assert "Component1" in saved_templates
        # pylint: enable=duplicate-code
        assert len(saved_templates["Component1"]) == 2
        template_names = [t["name"] for t in saved_templates["Component1"]]
        assert "Existing Template" in template_names
        assert "New Template" in template_names

    @patch("ardupilot_methodic_configurator.backend_filesystem_vehicle_components.FilesystemJSONWithSchema")
    def test_get_fc_fw_type_unsupported_vehicle(self, mock_fs_class) -> None:
        """
        Get Fc Fw Type Unsupported Vehicle.

        GIVEN: Vehicle components with unsupported firmware type
        WHEN: User retrieves firmware type
        THEN: Should return empty string for unsupported type
        """
        mock_fs = mock_fs_class.return_value
        mock_fs.data = {"Components": {"Flight Controller": {"Firmware": {"Type": "UnsupportedType"}}}}
        mock_fs.json_filename = "vehicle_components.json"

        vehicle_components = VehicleComponents()
        fw_type = vehicle_components.get_fc_fw_type_from_vehicle_components_json()

        # Verify empty string is returned for unsupported type
        assert fw_type == ""

    @patch("ardupilot_methodic_configurator.backend_filesystem_vehicle_components.FilesystemJSONWithSchema")
    def test_get_fc_fw_type_missing_components(self, mock_fs_class) -> None:
        """
        Get Fc Fw Type Missing Components.

        GIVEN: Vehicle data missing Components key
        WHEN: User retrieves firmware type
        THEN: Should return empty string without crashing
        """
        mock_fs = mock_fs_class.return_value
        mock_fs.data = {}  # No Components key

        vehicle_components = VehicleComponents()
        fw_type = vehicle_components.get_fc_fw_type_from_vehicle_components_json()

        # Verify empty string is returned
        assert fw_type == ""

    @patch("ardupilot_methodic_configurator.backend_filesystem_vehicle_components.FilesystemJSONWithSchema")
    def test_get_fc_fw_version_missing_components(self, mock_fs_class) -> None:
        """
        Get Fc Fw Version Missing Components.

        GIVEN: Vehicle data is None or missing Components key
        WHEN: User retrieves firmware version
        THEN: Should return empty string without crashing
        """
        mock_fs = mock_fs_class.return_value
        mock_fs.data = None  # No data

        vehicle_components = VehicleComponents()
        version = vehicle_components.get_fc_fw_version_from_vehicle_components_json()

        # Verify empty string is returned
        assert version == ""
