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


class TestVehicleComponents(unittest.TestCase):
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
        self.invalid_component_data = {"WrongKey": {"Flight Controller": {}}}

    @patch("builtins.open", new_callable=mock_open, read_data='{"$schema": "http://json-schema.org/draft-07/schema#"}')
    @patch("ardupilot_methodic_configurator.backend_filesystem_vehicle_components.json_load")
    def test_load_schema(self, mock_json_load, mock_file) -> None:
        mock_json_load.return_value = self.valid_schema
        result = self.vehicle_components.load_schema()
        assert result == self.valid_schema
        mock_file.assert_called_once()
        mock_json_load.assert_called_once()

    @patch.object(VehicleComponents, "load_schema")
    def test_validate_vehicle_components_valid(self, mock_load_schema) -> None:
        mock_load_schema.return_value = self.valid_schema
        is_valid, error_message = self.vehicle_components.validate_vehicle_components(self.valid_component_data)
        assert is_valid
        assert error_message == ""

    @patch.object(VehicleComponents, "load_schema")
    def test_validate_vehicle_components_invalid(self, mock_load_schema) -> None:
        mock_load_schema.return_value = self.valid_schema
        is_valid, error_message = self.vehicle_components.validate_vehicle_components(self.invalid_component_data)
        assert not is_valid
        assert "Validation error" in error_message

    @patch("builtins.open", new_callable=mock_open)
    @patch("ardupilot_methodic_configurator.backend_filesystem_vehicle_components.json_load")
    @patch.object(VehicleComponents, "validate_vehicle_components")
    def test_load_vehicle_components_json_data(self, mock_validate, mock_json_load, mock_file) -> None:
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
    def test_save_vehicle_components_json_data_valid(self, mock_validate, mock_json_dump, mock_file) -> None:
        mock_validate.return_value = (True, "")

        result = self.vehicle_components.save_vehicle_components_json_data(self.valid_component_data, "/test/dir")

        assert not result  # False means success
        expected_path = os.path.join("/test/dir", "vehicle_components.json")
        mock_file.assert_called_once_with(expected_path, "w", encoding="utf-8")
        mock_json_dump.assert_called_once()

    @patch.object(VehicleComponents, "validate_vehicle_components")
    def test_save_vehicle_components_json_data_invalid(self, mock_validate) -> None:
        mock_validate.return_value = (False, "Validation error")

        result = self.vehicle_components.save_vehicle_components_json_data(self.invalid_component_data, "/test/dir")

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
    def test_get_vehicle_components_overviews(self, mock_get_base_dir, mock_load_data, mock_relpath, mock_walk) -> None:
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
    def test_get_vehicle_image_filepath(self, mock_join, mock_get_base_dir) -> None:
        mock_get_base_dir.return_value = "/templates"
        mock_join.return_value = "/templates/copter/vehicle.jpg"

        result = VehicleComponents.get_vehicle_image_filepath("copter")

        mock_get_base_dir.assert_called_once()
        mock_join.assert_called_once_with("/templates", "copter", "vehicle.jpg")
        assert result == "/templates/copter/vehicle.jpg"


if __name__ == "__main__":
    unittest.main()
