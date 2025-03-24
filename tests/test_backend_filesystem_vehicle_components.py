#!/usr/bin/env python3

"""
Tests for the backend_filesystem_vehicle_components.py file.

This file is part of Ardupilot methodic configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2025 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import os.path
import unittest
from unittest.mock import mock_open, patch

from ardupilot_methodic_configurator.backend_filesystem_vehicle_components import VehicleComponents
from ardupilot_methodic_configurator.middleware_template_overview import TemplateOverview


class TestVehicleComponents(unittest.TestCase):  # pylint: disable=too-many-public-methods
    """VehicleComponents test class."""

    def setUp(self) -> None:
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

    @patch("builtins.open", new_callable=mock_open, read_data='{"$schema": "http://json-schema.org/draft-07/schema#"}')
    @patch("ardupilot_methodic_configurator.backend_filesystem_vehicle_components.json_load")
    def test_load_schema(self, mock_json_load, mock_file) -> None:  # type: ignore[misc]
        mock_json_load.return_value = self.valid_schema
        result = self.vehicle_components.load_schema()
        assert result == self.valid_schema
        mock_file.assert_called_once()
        mock_json_load.assert_called_once()

    @patch.object(VehicleComponents, "load_schema")
    def test_validate_vehicle_components_valid(self, mock_load_schema) -> None:  # type: ignore[misc]
        mock_load_schema.return_value = self.valid_schema
        is_valid, error_message = self.vehicle_components.validate_vehicle_components(self.valid_component_data)
        assert is_valid
        assert error_message == ""

    @patch.object(VehicleComponents, "load_schema")
    def test_validate_vehicle_components_invalid(self, mock_load_schema) -> None:  # type: ignore[misc]
        mock_load_schema.return_value = self.valid_schema
        is_valid, error_message = self.vehicle_components.validate_vehicle_components(self.invalid_component_data)
        assert not is_valid
        assert "Validation error" in error_message

    @patch("builtins.open", new_callable=mock_open)
    @patch("ardupilot_methodic_configurator.backend_filesystem_vehicle_components.json_load")
    @patch.object(VehicleComponents, "validate_vehicle_components")
    def test_load_vehicle_components_json_data(self, mock_validate, mock_json_load, mock_file) -> None:  # type: ignore[misc]
        mock_json_load.return_value = self.valid_component_data
        mock_validate.return_value = (True, "")

        result = self.vehicle_components.load_vehicle_components_json_data("/test/dir")

        assert result == self.valid_component_data
        assert self.vehicle_components.vehicle_components == self.valid_component_data

        expected_path = os.path.join("/test/dir", "vehicle_components.json")
        mock_file.assert_called_once_with(expected_path, encoding="utf-8")
        mock_json_load.assert_called_once()

    @patch("builtins.open", new_callable=mock_open)
    @patch("ardupilot_methodic_configurator.backend_filesystem_vehicle_components.json_dump")
    @patch.object(VehicleComponents, "validate_vehicle_components")
    def test_save_vehicle_components_json_data_valid(  # type: ignore[misc]
        self, mock_validate, mock_json_dump, mock_file
    ) -> None:
        mock_validate.return_value = (True, "")

        result, _msg = self.vehicle_components.save_vehicle_components_json_data(self.valid_component_data, "/test/dir")

        assert not result  # False means success
        expected_path = os.path.join("/test/dir", "vehicle_components.json")
        mock_file.assert_called_once_with(expected_path, "w", encoding="utf-8", newline="\n")
        mock_json_dump.assert_called_once()

    @patch.object(VehicleComponents, "validate_vehicle_components")
    def test_save_vehicle_components_json_data_invalid(self, mock_validate) -> None:  # type: ignore[misc]
        mock_validate.return_value = (False, "Validation error")

        result, _msg = self.vehicle_components.save_vehicle_components_json_data(self.invalid_component_data, "/test/dir")

        assert result  # True means failure

    def test_get_fc_fw_type_from_vehicle_components_json(self) -> None:
        self.vehicle_components.vehicle_components = self.valid_component_data
        fw_type = self.vehicle_components.get_fc_fw_type_from_vehicle_components_json()
        assert fw_type == "ArduCopter"

        # Test with unsupported firmware type
        invalid_data = {"Components": {"Flight Controller": {"Firmware": {"Type": "UnsupportedType", "Version": "4.3.0"}}}}
        self.vehicle_components.vehicle_components = invalid_data
        fw_type = self.vehicle_components.get_fc_fw_type_from_vehicle_components_json()
        assert fw_type == ""

    def test_get_fc_fw_version_from_vehicle_components_json(self) -> None:
        self.vehicle_components.vehicle_components = self.valid_component_data
        version = self.vehicle_components.get_fc_fw_version_from_vehicle_components_json()
        assert version == "4.3.0"

        # Test with invalid version format
        invalid_data = {
            "Components": {"Flight Controller": {"Firmware": {"Type": "ArduCopter", "Version": "invalid-version"}}}
        }
        self.vehicle_components.vehicle_components = invalid_data
        version = self.vehicle_components.get_fc_fw_version_from_vehicle_components_json()
        assert version == ""

    def test_supported_vehicles(self) -> None:
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
        mock_get_base_dir.return_value = "/templates"
        mock_join.return_value = "/templates/copter/vehicle.jpg"

        result = VehicleComponents.get_vehicle_image_filepath("copter")

        mock_get_base_dir.assert_called_once()
        mock_join.assert_called_once_with("/templates", "copter", "vehicle.jpg")
        assert result == "/templates/copter/vehicle.jpg"

    def test_wipe_component_info(self) -> None:
        # Test with nested dictionary containing various data types
        self.vehicle_components.vehicle_components = {
            "Components": {
                "Flight Controller": {
                    "Firmware": {"Type": "ArduCopter", "Version": "4.3.0"},
                    "Hardware": {"Model": "Pixhawk", "Ports": 5, "Sensors": ["GPS", "Barometer", "IMU"]},
                    "Options": {"Enabled": True, "Value": 42.5},
                }
            }
        }

        # Call the method to wipe
        self.vehicle_components.wipe_component_info()

        # Verify structure is preserved but values are cleared
        result = self.vehicle_components.vehicle_components
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

    @patch("builtins.open")
    def test_save_vehicle_components_json_data_file_not_found(self, mock_open) -> None:  # type: ignore[misc] # pylint: disable=redefined-outer-name
        mock_open.side_effect = FileNotFoundError()

        result, msg = self.vehicle_components.save_vehicle_components_json_data(self.valid_component_data, "/nonexistent/dir")

        assert result  # True means error
        assert "not found" in msg

    @patch("builtins.open")
    def test_save_vehicle_components_json_data_permission_error(self, mock_open) -> None:  # type: ignore[misc] # pylint: disable=redefined-outer-name
        mock_open.side_effect = PermissionError()

        result, msg = self.vehicle_components.save_vehicle_components_json_data(self.valid_component_data, "/test/dir")

        assert result  # True means error
        assert "Permission denied" in msg

    @patch("builtins.open")
    def test_save_vehicle_components_json_data_is_a_directory_error(self, mock_open) -> None:  # type: ignore[misc] # pylint: disable=redefined-outer-name
        mock_open.side_effect = IsADirectoryError()

        result, msg = self.vehicle_components.save_vehicle_components_json_data(self.valid_component_data, "/test/dir")

        assert result  # True means error
        assert "is a directory" in msg.lower()

    @patch("builtins.open")
    def test_save_vehicle_components_json_data_os_error(self, mock_open) -> None:  # type: ignore[misc] # pylint: disable=redefined-outer-name
        mock_open.side_effect = OSError("Disk full")

        result, msg = self.vehicle_components.save_vehicle_components_json_data(self.valid_component_data, "/test/dir")

        assert result  # True means error
        assert "OS error" in msg
        assert "Disk full" in msg

    @patch("builtins.open", new_callable=mock_open)
    @patch("ardupilot_methodic_configurator.backend_filesystem_vehicle_components.json_dump")
    def test_save_vehicle_components_json_data_type_error(self, mock_json_dump, mock_file) -> None:  # type: ignore[misc] # pylint: disable=unused-argument
        mock_json_dump.side_effect = TypeError("Invalid type")

        result, msg = self.vehicle_components.save_vehicle_components_json_data(self.valid_component_data, "/test/dir")

        assert result  # True means error
        assert "Type error" in msg
        assert "Invalid type" in msg

    @patch("builtins.open", new_callable=mock_open)
    @patch("ardupilot_methodic_configurator.backend_filesystem_vehicle_components.json_dump")
    def test_save_vehicle_components_json_data_value_error(self, mock_json_dump, mock_file) -> None:  # type: ignore[misc] # pylint: disable=unused-argument
        mock_json_dump.side_effect = ValueError("Circular reference")

        result, msg = self.vehicle_components.save_vehicle_components_json_data(self.valid_component_data, "/test/dir")

        assert result  # True means error
        assert "Value error" in msg
        assert "Circular reference" in msg

    @patch("ardupilot_methodic_configurator.backend_filesystem_program_settings.ProgramSettings.get_templates_base_dir")
    @patch("builtins.open", new_callable=mock_open)
    @patch("ardupilot_methodic_configurator.backend_filesystem_vehicle_components.json_load")
    def test_load_system_templates(self, mock_json_load, mock_file, mock_get_base_dir) -> None:  # type: ignore[misc]
        """Test loading system templates."""
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
        mock_file.assert_called_once_with(expected_path, encoding="utf-8")
        mock_json_load.assert_called_once()

    @patch("ardupilot_methodic_configurator.backend_filesystem_program_settings.ProgramSettings.get_templates_base_dir")
    @patch("builtins.open", new_callable=mock_open)
    @patch("ardupilot_methodic_configurator.backend_filesystem_vehicle_components.json_load")
    def test_load_user_templates(self, mock_json_load, mock_file, mock_get_base_dir) -> None:  # type: ignore[misc]
        """Test loading user templates."""
        user_templates = {"TestComponent": [{"name": "User Template", "data": {"param1": "custom"}}]}
        mock_json_load.return_value = user_templates
        mock_get_base_dir.return_value = "/user/templates"

        # Call the method to load user templates
        result = self.vehicle_components._load_user_templates()  # pylint: disable=protected-access

        # Verify the result
        assert result == user_templates

        # Verify the file was opened from the correct location
        expected_path = os.path.join("/user/templates", "user_vehicle_components_template.json")
        mock_file.assert_called_once_with(expected_path, encoding="utf-8")
        mock_json_load.assert_called_once()

    @patch.object(VehicleComponents, "_load_system_templates")
    @patch.object(VehicleComponents, "_load_user_templates")
    def test_load_component_templates_merge(self, mock_load_user, mock_load_system) -> None:  # type: ignore[misc]
        """Test that system and user templates are properly merged with user templates taking precedence."""
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
        """Test loading user templates when the file doesn't exist."""
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
        """Test loading component templates when no user templates exist."""
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
        """Test loading component templates when no system templates exist."""
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
        """Test basic successful saving of component templates."""
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
        """Test that only user-modified templates are saved."""
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
        """Test that templates with data different from system templates are saved."""
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
        """Test that templates not in system templates are saved."""
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
        """Test error handling when template directory cannot be created."""
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
        """Test handling of directory creation errors."""
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
        """Test handling of file-related errors."""
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
        """Test saving empty templates dictionary."""
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
        """Test handling JSON serialization error."""
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
        """Test saving templates to system templates when save_component_to_system_templates is True."""
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


if __name__ == "__main__":
    unittest.main()
