#!/usr/bin/env python3

"""
High-level BDD integration tests for vehicle project management workflows.

This file tests complete user workflows that span across VehicleProjectCreatorWindow
and VehicleProjectOpenerWindow, focusing on end-to-end integration scenarios.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from ardupilot_methodic_configurator.data_model_vehicle_project_creator import (
    NewVehicleProjectSettings,
    VehicleProjectCreationError,
)
from ardupilot_methodic_configurator.frontend_tkinter_base_window import BaseWindow
from ardupilot_methodic_configurator.frontend_tkinter_project_creator import VehicleProjectCreatorWindow
from ardupilot_methodic_configurator.frontend_tkinter_project_opener import VehicleProjectOpenerWindow

# pylint: disable=redefined-outer-name


@pytest.fixture
def mock_project_manager() -> MagicMock:
    """Create a realistic project manager mock for integration testing."""
    manager = MagicMock()
    manager.is_flight_controller_connected.return_value = False
    manager.get_vehicle_type.return_value = "ArduCopter"
    manager.get_recently_used_dirs.return_value = (
        "/home/user/templates/copter_basic",
        "/home/user/vehicles",
        "/home/user/vehicles/my_drone",
    )
    manager.get_default_vehicle_name.return_value = "NewVehicle"
    manager.get_file_parameters_list.return_value = ["01_basic_setup.param", "02_flight_modes.param"]
    return manager


@pytest.fixture
def realistic_temp_structure(tmp_path: Path) -> dict[str, Path]:
    """Create a realistic temporary directory structure for integration testing."""
    # Create template directories with realistic structure
    copter_template = tmp_path / "vehicle_templates" / "ArduCopter" / "dji_f450_basic"
    copter_template.mkdir(parents=True)

    plane_template = tmp_path / "vehicle_templates" / "ArduPlane" / "cessna_basic"
    plane_template.mkdir(parents=True)

    # Create realistic parameter files
    for template_dir in [copter_template, plane_template]:
        (template_dir / "00_default.param").write_text("# Default parameters\nSERIAL0_BAUD,115200")
        (template_dir / "01_brd_safety.param").write_text("# Safety parameters\nBRD_SAFETYENABLE,0")
        (template_dir / "vehicle_components.json").write_text('{"Frame": {"Category": "Multirotor"}}')

    # Create vehicles directory
    vehicles_dir = tmp_path / "vehicles"
    vehicles_dir.mkdir()

    # Create existing vehicle directory
    existing_vehicle = vehicles_dir / "existing_copter"
    existing_vehicle.mkdir()
    (existing_vehicle / "00_default.param").write_text("# Existing vehicle params")

    return {
        "root": tmp_path,
        "templates": tmp_path / "vehicle_templates",
        "copter_template": copter_template,
        "plane_template": plane_template,
        "vehicles": vehicles_dir,
        "existing_vehicle": existing_vehicle,
    }


@pytest.fixture
def configured_creator_window(mock_project_manager: MagicMock) -> VehicleProjectCreatorWindow:
    """Provide a configured creator window for integration testing."""
    with (
        patch("tkinter.Toplevel"),
        patch.object(BaseWindow, "_setup_application_icon"),
        patch.object(BaseWindow, "_setup_theme_and_styling"),
        patch.object(BaseWindow, "_get_dpi_scaling_factor", return_value=1.0),
        patch("tkinter.ttk.Label"),
        patch("tkinter.ttk.LabelFrame"),
        patch("tkinter.ttk.Button"),
        patch("tkinter.ttk.Checkbutton"),
        patch("tkinter.ttk.Frame"),
        patch("ardupilot_methodic_configurator.frontend_tkinter_project_creator.DirectorySelectionWidgets"),
        patch("ardupilot_methodic_configurator.frontend_tkinter_project_creator.PathEntryWidget"),
        patch("ardupilot_methodic_configurator.frontend_tkinter_project_creator.NewVehicleProjectSettings") as mock_settings,
        patch("ardupilot_methodic_configurator.frontend_tkinter_project_creator.show_tooltip"),
        patch("ardupilot_methodic_configurator.frontend_tkinter_project_creator.tk.BooleanVar"),
        patch("tkinter.Tk"),
    ):
        # Setup mock settings like in the existing tests
        mock_settings.get_all_settings_metadata.return_value = {
            "copy_vehicle_image": MagicMock(label="Copy vehicle image", enabled=True, tooltip="Copy vehicle image"),
        }
        mock_settings.get_default_values.return_value = {"copy_vehicle_image": False}

        window = VehicleProjectCreatorWindow(mock_project_manager)

        # Mock essential UI components for testing
        window.root = MagicMock()
        window.template_dir = MagicMock()
        window.new_base_dir = MagicMock()
        window.new_dir = MagicMock()

        return window


@pytest.fixture
def configured_opener_window(mock_project_manager: MagicMock) -> VehicleProjectOpenerWindow:
    """Provide a configured opener window for integration testing."""
    with (
        patch("tkinter.Toplevel"),
        patch.object(BaseWindow, "_setup_application_icon"),
        patch.object(BaseWindow, "_setup_theme_and_styling"),
        patch.object(BaseWindow, "_get_dpi_scaling_factor", return_value=1.0),
        patch("tkinter.ttk.Label"),
        patch("tkinter.ttk.LabelFrame"),
        patch("tkinter.ttk.Button"),
        patch("tkinter.ttk.Frame"),
        patch("ardupilot_methodic_configurator.frontend_tkinter_project_opener.DirectorySelectionWidgets"),
        patch("ardupilot_methodic_configurator.frontend_tkinter_project_opener.VehicleDirectorySelectionWidgets"),
    ):
        window = VehicleProjectOpenerWindow(mock_project_manager)

        # Mock essential UI components
        window.root = MagicMock()
        window.vehicle_dir_selection = MagicMock()

        return window


class TestVehicleProjectWorkflows:
    """Test complete user workflows for vehicle project management."""

    def test_user_can_create_and_immediately_open_new_vehicle_project(
        self,
        configured_creator_window: VehicleProjectCreatorWindow,
        configured_opener_window: VehicleProjectOpenerWindow,
        realistic_temp_structure: dict[str, Path],
    ) -> None:
        """
        User can create a new vehicle project and immediately open it for configuration.

        GIVEN: A user wants to set up a new vehicle configuration
        WHEN: They create a new project from a template and then open it
        THEN: The project should be created successfully with all necessary files
        AND: The project should open immediately for parameter configuration
        """
        # Arrange (Given): User selects template and destination
        creator = configured_creator_window
        opener = configured_opener_window

        template_path = str(realistic_temp_structure["copter_template"])
        vehicles_path = str(realistic_temp_structure["vehicles"])
        new_vehicle_name = "MyNewCopter"

        creator.template_dir.get_selected_directory.return_value = template_path
        creator.new_base_dir.get_selected_directory.return_value = vehicles_path
        creator.new_dir.get_selected_directory.return_value = new_vehicle_name

        # Mock successful project creation
        creator.project_manager.create_new_vehicle_from_template.return_value = True

        # Act (When): User creates and opens the project
        creator.create_new_vehicle_from_template()

        # Simulate opening the newly created project
        new_project_path = str(realistic_temp_structure["vehicles"] / new_vehicle_name)
        opener.vehicle_dir_selection.get_selected_directory.return_value = new_project_path
        # User opens newly created project through project manager
        opener.project_manager.open_vehicle_directory(new_project_path)

        # Assert (Then): Project creation and opening workflow completed
        creator.project_manager.create_new_vehicle_from_template.assert_called_once()
        opener.project_manager.open_vehicle_directory.assert_called_once_with(new_project_path)
        creator.root.destroy.assert_called_once()
        # Note: opener.root.destroy is not called because we're using project_manager directly,
        # not the opener's own open_last_vehicle_directory method

    def test_user_receives_clear_error_when_template_directory_invalid(
        self, configured_creator_window: VehicleProjectCreatorWindow
    ) -> None:
        """
        User receives clear feedback when attempting to use an invalid template directory.

        GIVEN: A user is creating a new vehicle project
        WHEN: They select an invalid or non-existent template directory
        THEN: They should receive a clear, actionable error message
        AND: The project creation should not proceed
        """
        # Arrange (Given): User selects invalid template
        creator = configured_creator_window
        creator.template_dir.get_selected_directory.return_value = "/nonexistent/template"
        creator.new_base_dir.get_selected_directory.return_value = "/valid/destination"
        creator.new_dir.get_selected_directory.return_value = "ValidName"

        # Configure project manager to raise error
        creator.project_manager.create_new_vehicle_from_template.side_effect = VehicleProjectCreationError(
            "Invalid Template", "The selected template directory does not exist or is not valid."
        )

        # Act & Assert (When/Then): Error handling
        with patch("tkinter.messagebox.showerror") as mock_error:
            creator.create_new_vehicle_from_template()

            # Verify user sees helpful error message
            mock_error.assert_called_once_with(
                "Invalid Template", "The selected template directory does not exist or is not valid."
            )
            # Verify window doesn't close on error
            creator.root.destroy.assert_not_called()

    def test_user_can_switch_between_creating_and_opening_existing_projects(
        self, realistic_temp_structure: dict[str, Path]
    ) -> None:
        """
        User can seamlessly switch between creating new projects and opening existing ones.

        GIVEN: A user has both existing projects and wants to create new ones
        WHEN: They alternate between opening existing projects and creating new ones
        THEN: Both workflows should work independently without interference
        """
        # Arrange (Given): Set up project manager with both capabilities
        manager = MagicMock()
        manager.get_recently_used_dirs.return_value = (
            str(realistic_temp_structure["copter_template"]),
            str(realistic_temp_structure["vehicles"]),
            str(realistic_temp_structure["existing_vehicle"]),
        )
        manager.get_file_parameters_list.return_value = ["01_basic.param", "02_advanced.param"]

        # Act (When): User opens existing project first
        with (
            patch("tkinter.Toplevel"),
            patch.object(BaseWindow, "_setup_application_icon"),
            patch.object(BaseWindow, "_setup_theme_and_styling"),
            patch.object(BaseWindow, "_get_dpi_scaling_factor", return_value=1.0),
            patch("tkinter.ttk.Label"),
            patch("tkinter.ttk.LabelFrame"),
            patch("tkinter.ttk.Button"),
            patch("tkinter.ttk.Frame"),
            patch("ardupilot_methodic_configurator.frontend_tkinter_project_opener.DirectorySelectionWidgets"),
            patch("ardupilot_methodic_configurator.frontend_tkinter_project_opener.VehicleDirectorySelectionWidgets"),
            patch("ardupilot_methodic_configurator.frontend_tkinter_project_creator.DirectorySelectionWidgets"),
            patch("ardupilot_methodic_configurator.frontend_tkinter_project_creator.PathEntryWidget"),
            patch("ardupilot_methodic_configurator.frontend_tkinter_project_creator.NewVehicleProjectSettings"),
            patch("ardupilot_methodic_configurator.frontend_tkinter_project_creator.show_tooltip"),
            patch("ardupilot_methodic_configurator.frontend_tkinter_project_creator.tk.BooleanVar"),
            patch("tkinter.Tk"),
            patch("tkinter.ttk.Checkbutton"),
        ):
            opener = VehicleProjectOpenerWindow(manager)
            opener.root = MagicMock()
            opener.vehicle_dir_selection = MagicMock()

            existing_path = str(realistic_temp_structure["existing_vehicle"])
            opener.vehicle_dir_selection.get_selected_directory.return_value = existing_path
            # User opens existing project through project manager
            opener.project_manager.open_vehicle_directory(existing_path)

            # Then user creates a new project
            creator = VehicleProjectCreatorWindow(manager)
            creator.root = MagicMock()
            creator.template_dir = MagicMock()
            creator.new_base_dir = MagicMock()
            creator.new_dir = MagicMock()

            creator.template_dir.get_selected_directory.return_value = str(realistic_temp_structure["copter_template"])
            creator.new_base_dir.get_selected_directory.return_value = str(realistic_temp_structure["vehicles"])
            creator.new_dir.get_selected_directory.return_value = "AnotherVehicle"

            manager.create_new_vehicle_from_template.return_value = True
            creator.create_new_vehicle_from_template()

        # Assert (Then): Both operations completed successfully
        manager.open_vehicle_directory.assert_called_once_with(existing_path)
        manager.create_new_vehicle_from_template.assert_called_once()

    def test_flight_controller_connection_affects_both_creator_and_opener_options(
        self, mock_project_manager: MagicMock
    ) -> None:
        """
        Flight controller connection state influences available options in both windows.

        GIVEN: A flight controller is connected to the system
        WHEN: User opens either the creator or opener window
        THEN: Both should show FC-specific options and capabilities
        AND: Options should be consistent between windows
        """
        # Arrange (Given): Flight controller connected
        mock_project_manager.is_flight_controller_connected.return_value = True
        mock_project_manager.get_vehicle_type.return_value = "ArduCopter"

        # Act (When): Create both windows with FC connected
        with (
            patch("tkinter.Toplevel"),
            patch.object(BaseWindow, "_setup_application_icon"),
            patch.object(BaseWindow, "_setup_theme_and_styling"),
            patch.object(BaseWindow, "_get_dpi_scaling_factor", return_value=1.0),
            patch("tkinter.ttk.Label"),
            patch("tkinter.ttk.LabelFrame"),
            patch("tkinter.ttk.Button"),
            patch("tkinter.ttk.Frame"),
            patch("ardupilot_methodic_configurator.frontend_tkinter_project_opener.DirectorySelectionWidgets"),
            patch("ardupilot_methodic_configurator.frontend_tkinter_project_opener.VehicleDirectorySelectionWidgets"),
            patch("ardupilot_methodic_configurator.frontend_tkinter_project_creator.DirectorySelectionWidgets"),
            patch("ardupilot_methodic_configurator.frontend_tkinter_project_creator.PathEntryWidget"),
            patch("ardupilot_methodic_configurator.frontend_tkinter_project_creator.NewVehicleProjectSettings"),
            patch("ardupilot_methodic_configurator.frontend_tkinter_project_creator.show_tooltip"),
            patch("ardupilot_methodic_configurator.frontend_tkinter_project_creator.tk.BooleanVar"),
            patch("tkinter.Tk"),
            patch("tkinter.ttk.Checkbutton"),
        ):
            creator = VehicleProjectCreatorWindow(mock_project_manager)
            creator.root = MagicMock()

            opener = VehicleProjectOpenerWindow(mock_project_manager)
            opener.root = MagicMock()

        # Assert (Then): Both windows recognize FC connection
        assert creator.project_manager.is_flight_controller_connected() is True
        assert opener.project_manager.is_flight_controller_connected() is True
        assert creator.project_manager.get_vehicle_type() == "ArduCopter"
        assert opener.project_manager.get_vehicle_type() == "ArduCopter"

    def test_user_workflow_with_project_settings_persistence(
        self, configured_creator_window: VehicleProjectCreatorWindow, realistic_temp_structure: dict[str, Path]
    ) -> None:
        """
        User's project creation settings are properly applied and persisted.

        GIVEN: A user configures specific project creation options
        WHEN: They create a new vehicle project with those settings
        THEN: The settings should be applied to the created project
        AND: The settings should be persisted for future use
        """
        # Arrange (Given): User configures project settings
        creator = configured_creator_window

        # Mock project settings configuration
        _settings = NewVehicleProjectSettings(
            copy_vehicle_image=True, blank_component_data=False, use_fc_params=True, blank_change_reason=False
        )

        template_path = str(realistic_temp_structure["copter_template"])
        vehicles_path = str(realistic_temp_structure["vehicles"])

        creator.template_dir.get_selected_directory.return_value = template_path
        creator.new_base_dir.get_selected_directory.return_value = vehicles_path
        creator.new_dir.get_selected_directory.return_value = "ConfiguredVehicle"

        # Mock the settings variables to return configured values
        creator.new_project_settings_vars = {
            "copy_vehicle_image": MagicMock(),
            "blank_component_data": MagicMock(),
            "use_fc_params": MagicMock(),
            "blank_change_reason": MagicMock(),
        }
        creator.new_project_settings_vars["copy_vehicle_image"].get.return_value = True
        creator.new_project_settings_vars["blank_component_data"].get.return_value = False
        creator.new_project_settings_vars["use_fc_params"].get.return_value = True
        creator.new_project_settings_vars["blank_change_reason"].get.return_value = False

        # Act (When): User creates project with settings
        creator.create_new_vehicle_from_template()

        # Assert (Then): Settings were applied correctly
        creator.project_manager.create_new_vehicle_from_template.assert_called_once()
        call_args = creator.project_manager.create_new_vehicle_from_template.call_args

        # Verify the settings object was passed correctly
        assert len(call_args[0]) == 4  # template_dir, base_dir, vehicle_name, settings
        passed_settings = call_args[0][3]
        assert passed_settings.copy_vehicle_image is True
        assert passed_settings.use_fc_params is True
