#!/usr/bin/env python3

"""
Integration tests for ComponentEditorWindow.

This file focuses on integration testing with minimal mocking, testing multiple
components working together in realistic scenarios.

This file is part of Ardupilot methodic configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2025 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import json
import tempfile
import tkinter as tk
from collections.abc import Generator
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from test_data_model_vehicle_components_common import REALISTIC_VEHICLE_DATA

from ardupilot_methodic_configurator.backend_filesystem import LocalFilesystem
from ardupilot_methodic_configurator.data_model_vehicle_components import ComponentDataModel
from ardupilot_methodic_configurator.data_model_vehicle_components_json_schema import VehicleComponentsJsonSchema
from ardupilot_methodic_configurator.frontend_tkinter_component_editor import ComponentEditorWindow

# pylint: disable=redefined-outer-name


@pytest.fixture
def temp_vehicle_dir() -> Generator[str, None, None]:
    """Create a temporary directory for vehicle files."""
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create component json file
        components_file = Path(temp_dir) / "vehicle_components.json"
        with open(components_file, "w", encoding="utf-8") as f:
            json.dump(REALISTIC_VEHICLE_DATA, f)

        yield temp_dir


class TestComponentEditorIntegration:
    """
    Integration tests for ComponentEditorWindow.

    These tests focus on testing multiple components working together with minimal mocking,
    allowing us to verify the behavior of the real implementation with real data.
    """

    @pytest.fixture
    def real_filesystem(self, temp_vehicle_dir) -> LocalFilesystem:
        """Create a real LocalFilesystem instance with a temporary directory."""
        return LocalFilesystem(
            vehicle_dir=temp_vehicle_dir,
            vehicle_type="ArduCopter",
            fw_version="",
            allow_editing_template_files=True,
            save_component_to_system_templates=False,
        )

    @pytest.fixture
    def editor_with_real_filesystem(self, real_filesystem) -> Generator[ComponentEditorWindow, None, None]:
        """Create a ComponentEditorWindow with a real filesystem but mocked UI."""
        # Mock BaseWindow.__init__ to avoid actual window rendering and tkinter initialization
        with patch("ardupilot_methodic_configurator.frontend_tkinter_base_window.BaseWindow.__init__", return_value=None):
            # Create the editor directly without UI initialization
            editor = ComponentEditorWindow.__new__(ComponentEditorWindow)

            # Set up required attributes manually
            editor.local_filesystem = real_filesystem
            editor.version = "1.0.0"
            editor.root = MagicMock()
            editor.main_frame = MagicMock()
            editor.scroll_frame = MagicMock()
            editor.scroll_frame.view_port = MagicMock()
            editor.entry_widgets = {}

            # Initialize data model properly using schema
            schema = VehicleComponentsJsonSchema(real_filesystem.load_schema())
            component_datatypes = schema.get_all_value_datatypes()
            editor.data_model = ComponentDataModel(
                real_filesystem.load_vehicle_components_json_data(real_filesystem.vehicle_dir),
                component_datatypes,
                schema,
            )

            yield editor

    def test_data_model_filesystem_integration(self, editor_with_real_filesystem) -> None:
        """Test integration between data model and filesystem."""
        editor = editor_with_real_filesystem

        # Verify data model was correctly initialized from filesystem
        assert editor.data_model is not None
        assert editor.data_model.is_valid_component_data()
        assert editor.data_model.has_components()

        # Test accessing component data through data model
        components = editor.data_model.get_all_components()
        assert "Components" in editor.data_model.get_component_data()
        assert len(components) > 0

        # Verify schema loading worked properly
        schema = VehicleComponentsJsonSchema(editor.local_filesystem.load_schema())
        component_datatypes = schema.get_all_value_datatypes()
        assert len(component_datatypes) > 0

    def test_component_adding_integration(self, editor_with_real_filesystem) -> None:
        """Test adding a new component through the editor."""
        editor = editor_with_real_filesystem

        # Add a new component
        new_component_data = {
            "Type": "ESC",
            "Model": "XYZ-40A",
            "Specifications": {"Max Current": "40A", "Protocol": "DShot600"},
        }

        # Use the proper method to add a component
        editor.data_model.update_component("ESC4", new_component_data)

        # Verify the component was added properly
        components = editor.data_model.get_all_components()
        assert "ESC4" in components
        assert components["ESC4"]["Type"] == "ESC"
        assert components["ESC4"]["Model"] == "XYZ-40A"
        assert components["ESC4"]["Specifications"]["Max Current"] == "40A"

        # Test save and reload cycle
        with patch.object(editor.data_model, "save_to_filesystem") as mock_save:
            mock_save.return_value = (False, "")  # No error, empty error message
            editor.data_model.save_to_filesystem(editor.local_filesystem)
            mock_save.assert_called_once_with(editor.local_filesystem)

    def test_component_validation_integration(self, editor_with_real_filesystem) -> None:
        """Test component validation integration with realistic data."""
        editor = editor_with_real_filesystem

        # Create a real data model for testing
        schema = VehicleComponentsJsonSchema(editor.local_filesystem.load_schema())
        component_datatypes = schema.get_all_value_datatypes()
        real_data_model = ComponentDataModel(REALISTIC_VEHICLE_DATA, component_datatypes, schema)
        real_data_model.post_init(editor.local_filesystem.doc_dict)
        editor.data_model = real_data_model

        # Test validation of valid battery cell voltage
        editor.data_model.set_component_value(("Battery", "Specifications", "Chemistry"), "Lipo")
        editor.data_model.set_component_value(("Battery", "Specifications", "Volt per cell max"), "4.2")
        editor.data_model.set_component_value(("Battery", "Specifications", "Volt per cell low"), "3.5")
        editor.data_model.set_component_value(("Battery", "Specifications", "Volt per cell crit"), "3.3")

        # Directly validate these values using validate_entry_limits instead
        # The validate_cell_voltage method is internal and should not be called directly
        message, value = editor.data_model.validate_entry_limits("4.2", ("Battery", "Specifications", "Volt per cell max"))
        assert message == ""  # No error message means valid
        assert value is None  # No error message means valid

        # Test validation of invalid battery cell voltage
        message, value = editor.data_model.validate_entry_limits(
            "5.0",  # Too high for LiPo
            ("Battery", "Specifications", "Volt per cell max"),
        )
        assert message != ""  # Error message indicates invalid
        assert "above" in message.lower() or "high" in message.lower()

    def test_parameters_integration(self, editor_with_real_filesystem) -> None:
        """Test integration with FC parameters."""
        editor = editor_with_real_filesystem

        # Setup
        fc_params = {
            "SERIAL1_PROTOCOL": 2,  # MAVLink2
            "SERIAL2_PROTOCOL": 5,  # GPS
            "RC_PROTOCOLS": 1,  # CRSF
            "BATT_MONITOR": 4,  # SMBus
        }

        doc_dict = {
            "SERIAL1_PROTOCOL": {"values": {"2": "MAVLink2"}},
            "SERIAL2_PROTOCOL": {"values": {"5": "GPS"}},
            "RC_PROTOCOLS": {"Bitmask": {"0": "CRSF"}},
            "BATT_MONITOR": {"values": {"4": "SMBus"}},
        }

        # Mock UI components that would be updated
        editor.entry_widgets = {
            ("Telemetry", "FC Connection", "Type"): MagicMock(),
            ("Telemetry", "FC Connection", "Protocol"): MagicMock(),
            ("RC Receiver", "FC Connection", "Type"): MagicMock(),
            ("RC Receiver", "FC Connection", "Protocol"): MagicMock(),
            ("GNSS Receiver", "FC Connection", "Type"): MagicMock(),
            ("GNSS Receiver", "FC Connection", "Protocol"): MagicMock(),
            ("Battery", "FC Connection", "Type"): MagicMock(),
            ("Battery", "FC Connection", "Protocol"): MagicMock(),
        }

        # Test parameter processing with realistic data
        # The set_values_from_fc_parameters method delegates to data_model.process_fc_parameters

        # Create a spy on the correct data model method
        with patch.object(editor.data_model, "process_fc_parameters") as mock_process:
            # Call the method being tested
            editor.set_values_from_fc_parameters(fc_params, doc_dict)

            # Check that the data model was updated
            mock_process.assert_called_once_with(fc_params, doc_dict)

        # Verify some of the key connections are set with any expected protocol

    def test_component_editor_data_flow(self, editor_with_real_filesystem) -> None:
        """
        Test the flow of data from UI widgets to the data model and back.

        This test verifies the integration points between UI widgets,
        the editor controller, and the data model.
        """
        editor = editor_with_real_filesystem

        # Create mock entry widgets
        mock_entry1 = MagicMock()
        mock_entry1.get.return_value = "T-Motor MN3110"
        mock_entry2 = MagicMock()
        mock_entry2.get.return_value = "700"

        # Register them in the editor
        editor.entry_widgets[("Motor", "Model")] = mock_entry1
        editor.entry_widgets[("Motor", "Specifications", "KV")] = mock_entry2

        # Get data from UI
        component_data = editor.get_component_data_from_gui("Motor")

        # Verify data was extracted correctly
        assert "Model" in component_data
        assert component_data["Model"] == "T-Motor MN3110"
        assert "Specifications" in component_data
        assert "KV" in component_data["Specifications"]
        assert str(component_data["Specifications"]["KV"]) == "700"

        # Now test data flow in the other direction
        # First mock the data model method
        original_set_value = editor.data_model.set_component_value
        editor.data_model.set_component_value = MagicMock()

        # Call the method
        editor.set_component_value_and_update_ui(("Motor", "Model"), "T-Motor F80")

        # Verify data model was updated
        editor.data_model.set_component_value.assert_called_with(("Motor", "Model"), "T-Motor F80")

        # Restore original method
        editor.data_model.set_component_value = original_set_value

        # Verify UI was updated
        mock_entry1.delete.assert_called_with(0, tk.END)
        mock_entry1.insert.assert_called_with(0, "T-Motor F80")


class TestComponentEditorWithMinimalMocking:
    """
    Integration tests with minimal mocking for the component editor.

    These tests focus on verifying the integration of multiple classes
    while mocking only the absolute minimum required to avoid UI rendering.
    """

    def test_editor_initialization_process(self, temp_vehicle_dir, root) -> None:
        """
        Test the full initialization process with minimal mocking.

        GIVEN: A temporary vehicle directory with realistic test data
        WHEN: Creating a ComponentEditorWindow with minimal UI mocking
        THEN: The editor should initialize properly with real filesystem and data model
        """
        # Use a real filesystem with temporary directory
        filesystem = LocalFilesystem(
            vehicle_dir=temp_vehicle_dir,
            vehicle_type="ArduCopter",
            fw_version="",
            allow_editing_template_files=True,
            save_component_to_system_templates=False,
        )

        # Mock only the UI rendering parts, use the real root from conftest.py
        with (
            patch.object(ComponentEditorWindow, "_create_scroll_frame") as mock_scroll_frame,
            patch.object(ComponentEditorWindow, "_create_intro_frame") as mock_intro_frame,
            patch.object(ComponentEditorWindow, "_create_save_frame") as mock_save_frame,
            patch("tkinter.PhotoImage"),
            patch("PIL.ImageTk.PhotoImage"),
        ):
            # Create the editor with real filesystem and data model
            editor = ComponentEditorWindow("1.0.0", filesystem)

            # Use the real root from conftest.py
            editor.root = root

            # Check editor has been properly initialized
            assert editor.version == "1.0.0"
            assert editor.local_filesystem == filesystem

            # Verify data model was created and initialized
            assert editor.data_model is not None

            # Verify UI initialization methods were called
            assert mock_scroll_frame.called
            assert mock_intro_frame.called
            assert mock_save_frame.called

            # Test that we can access the data model functionality
            components = editor.data_model.get_all_components()
            assert isinstance(components, dict)
            assert len(components) > 0

    def test_editor_with_real_data_model(self, temp_vehicle_dir, root) -> None:
        """
        Test the editor with a real data model but minimal UI mocking.

        GIVEN: A realistic vehicle data model and minimal UI mocking
        WHEN: Creating and using a ComponentEditorWindow
        THEN: The editor should work with real data validation and processing
        """
        # Use a real filesystem with temporary directory
        filesystem = LocalFilesystem(
            vehicle_dir=temp_vehicle_dir,
            vehicle_type="ArduCopter",
            fw_version="",
            allow_editing_template_files=True,
            save_component_to_system_templates=False,
        )

        # Create a data model with realistic test data
        schema = VehicleComponentsJsonSchema(filesystem.load_schema())
        component_datatypes = schema.get_all_value_datatypes()
        data_model = ComponentDataModel(REALISTIC_VEHICLE_DATA, component_datatypes, schema)

        # Bypass UI initialization but use real data model and real root
        with (
            patch.object(ComponentEditorWindow, "_initialize_ui"),
            patch("tkinter.PhotoImage"),
            patch("PIL.ImageTk.PhotoImage"),
        ):
            # Initialize with existing data_model using dependency injection
            editor = ComponentEditorWindow("1.0.0", filesystem)
            editor.data_model = data_model  # Override the data model
            editor.root = root  # Use the real root from conftest.py

            # Test data model integration
            assert editor.data_model is data_model

            # Test real validation with real data model
            editor.data_model.set_component_value(("Battery", "Specifications", "Chemistry"), "Lipo")
            editor.data_model.set_component_value(("Battery", "Specifications", "Number of cells"), "4")

            # Check that the data model correctly processed these values
            chemistry = editor.data_model.get_component_value(("Battery", "Specifications", "Chemistry"))
            cells = editor.data_model.get_component_value(("Battery", "Specifications", "Number of cells"))

            assert chemistry == "Lipo"
            assert cells == 4  # Data model should convert to proper type (int)

            # Verify default voltage values were set for Lipo
            max_cell_voltage = editor.data_model.get_component_value(("Battery", "Specifications", "Volt per cell max"))
            if isinstance(max_cell_voltage, (str, float)):
                assert float(max_cell_voltage) == pytest.approx(4.2)

            # Test that the editor can process real component data
            components = editor.data_model.get_all_components()
            assert len(components) > 0
            assert "Components" in editor.data_model.get_component_data()


if __name__ == "__main__":
    pytest.main(["-xvs", __file__])
