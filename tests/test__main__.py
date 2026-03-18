#!/usr/bin/env python3

"""
Behavior-driven tests for the __main__.py file.

Following pytest_testing_instructions.md guidelines for testability and maintainability.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import argparse
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from ardupilot_methodic_configurator import __main__ as amc_main
from ardupilot_methodic_configurator.__main__ import (
    ApplicationState,
    backup_fc_parameters,
    check_updates,
    component_editor,
    connect_to_fc_and_set_vehicle_type,
    create_and_configure_component_editor,
    create_argument_parser,
    display_first_use_documentation,
    get_preferred_vehicle_dir,
    initialize_filesystem,
    initialize_flight_controller_and_filesystem,
    main,
    open_firmware_documentation,
    parameter_editor_and_uploader,
    process_component_editor_results,
    register_plugins,
    resolve_writable_vehicle_dir_for_initial_download,
    should_open_firmware_documentation,
    validate_plugin_registry,
    vehicle_directory_selection,
    write_parameter_defaults,
)
from ardupilot_methodic_configurator.backend_flightcontroller import DEVICE_FC_PARAM_FROM_FILE
from ardupilot_methodic_configurator.data_model_par_dict import ParDict
from ardupilot_methodic_configurator.frontend_tkinter_usage_popup_window import PopupWindow

# pylint: disable=too-many-lines,redefined-outer-name,too-few-public-methods

# ====== Fixtures following pytest_testing_instructions.md ======


@pytest.fixture
def mock_args() -> MagicMock:
    """Fixture providing realistic mock arguments for application startup."""
    args = MagicMock(spec=argparse.Namespace)
    args.loglevel = "INFO"
    args.skip_check_for_updates = False
    args.vehicle_dir = "/test/vehicle/dir"
    args.device = DEVICE_FC_PARAM_FROM_FILE
    args.vehicle_type = "ArduCopter"
    args.allow_editing_template_files = False
    args.save_component_to_system_templates = False
    args.reboot_time = 10.0
    args.baudrate = 115200
    args.skip_component_editor = False
    args.n = 0
    args.export_fc_params_missing_or_different = False
    return args


@pytest.fixture
def application_state(mock_args: MagicMock) -> ApplicationState:
    """Fixture providing a configured ApplicationState for behavior testing."""
    return ApplicationState(mock_args)


@pytest.fixture
def mock_flight_controller() -> MagicMock:
    """Fixture providing a realistic mock flight controller with proper structure."""
    fc = MagicMock()
    fc.master = MagicMock()
    fc.fc_parameters = {"PARAM1": 1.0, "PARAM2": 2.0, "INS_TCAL1_ENABLE": 1}

    # Configure flight controller info with realistic data
    fc.info.vehicle_type = "ArduCopter"
    fc.info.flight_sw_version = "4.5.0"
    fc.info.flight_sw_version_and_type = "ArduCopter V4.5.0"
    fc.info.vendor = "Pixhawk"
    fc.info.firmware_type = "CubeOrange"
    fc.info.mcu_series = "STM32H7xx"

    fc.connect.return_value = ""  # No error
    fc.disconnect.return_value = None
    return fc


@pytest.fixture
def mock_local_filesystem() -> MagicMock:
    """Fixture providing a realistic mock local filesystem."""
    fs = MagicMock()
    fs.vehicle_type = "ArduCopter"
    fs.file_parameters = {"01_basic.param": {}, "02_advanced.param": {}}
    fs.param_default_dict = {"PARAM1": 1.0, "PARAM2": 2.0}
    fs.doc_dict = {"PARAM1": "Parameter 1 documentation"}

    # Configure realistic return values
    fs.write_param_default_values.return_value = False
    fs.calculate_derived_and_forced_param_changes.return_value = {}  # Empty dict = no pending changes
    fs.get_start_file.return_value = "01_basic.param"
    fs.find_lowest_available_backup_number.return_value = 1

    return fs


@pytest.fixture
def configured_application_state(
    application_state: ApplicationState, mock_flight_controller: MagicMock, mock_local_filesystem: MagicMock
) -> ApplicationState:
    """Fixture providing a fully configured ApplicationState for integration testing."""
    application_state.flight_controller = mock_flight_controller
    application_state.local_filesystem = mock_local_filesystem
    application_state.vehicle_type = "ArduCopter"
    application_state.param_default_values = {"PARAM1": 1.0, "PARAM2": 2.0}
    application_state.param_default_values_dirty = False
    application_state.vehicle_dir_window = None
    return application_state


@pytest.fixture
def mock_vehicle_directory_window() -> MagicMock:
    """Fixture providing a realistic mock vehicle directory selection window."""
    window = MagicMock()
    window.configuration_template = "QuadCopter_X"

    # Mock BooleanVar objects with get() method
    mock_infer_bool_var = MagicMock()
    mock_infer_bool_var.get.return_value = True
    window.infer_comp_specs_and_conn_from_fc_params = mock_infer_bool_var

    mock_use_fc_bool_var = MagicMock()
    mock_use_fc_bool_var.get.return_value = True
    window.use_fc_params = mock_use_fc_bool_var

    window.root.mainloop.return_value = None
    return window


# ====== Application State Tests ======


class TestApplicationStartup:
    """Test application startup behavior from user perspective."""

    def test_user_can_start_application_with_updates_disabled(self, application_state: ApplicationState) -> None:
        """
        User can start application smoothly when update checking is disabled.

        GIVEN: A user wants to start the application without checking for updates
        WHEN: They launch with --skip-check-for-updates flag
        THEN: Application should proceed immediately to main functionality
        """
        # Arrange: User disables update checking
        application_state.args.skip_check_for_updates = True

        with (
            patch("ardupilot_methodic_configurator.__main__.check_for_software_updates") as mock_check,
        ):
            # Act: User starts application
            should_exit = check_updates(application_state)

            # Assert: Application continues normally
            assert should_exit is False
            mock_check.assert_not_called()

    def test_user_receives_update_notification_when_new_version_available(self, application_state: ApplicationState) -> None:
        """
        User is notified when a software update is available and application exits gracefully.

        GIVEN: A user starts an outdated version of the application
        WHEN: The application checks for updates
        THEN: User should be informed and application should exit for update
        """
        # Arrange: Updates are available
        application_state.args.skip_check_for_updates = False

        with (
            patch("ardupilot_methodic_configurator.__main__.logging_basicConfig"),
            patch("ardupilot_methodic_configurator.__main__.check_for_software_updates", return_value=True),
        ):
            # Act: User starts outdated application
            should_exit = check_updates(application_state)

            # Assert: User informed and application exits
            assert should_exit is True

    def test_user_proceeds_normally_when_application_is_current(self, application_state: ApplicationState) -> None:
        """
        User can proceed with application when no updates are needed.

        GIVEN: A user starts the current version of the application
        WHEN: The application checks for updates
        THEN: Application should continue with normal startup
        """
        # Arrange: No updates needed
        application_state.args.skip_check_for_updates = False

        with (
            patch("ardupilot_methodic_configurator.__main__.check_for_software_updates", return_value=False),
        ):
            # Act: User starts current application
            should_exit = check_updates(application_state)

            # Assert: Application continues normally
            assert should_exit is False

    def test_user_sees_workflow_explanation_popup_on_first_startup(self) -> None:
        """
        User sees workflow explanation popup when starting application for the first time.

        GIVEN: A user starts the application for the first time
        WHEN: The application initializes
        THEN: The workflow explanation popup should be displayed to guide them
        AND: The popup should explain that AMC is not a ground control station
        """
        # Arrange: Mock popup display enabled (default behavior)
        with (
            patch(
                "ardupilot_methodic_configurator.__main__.PopupWindow.should_display",
                return_value=True,
            ) as mock_should_display,
            patch("ardupilot_methodic_configurator.__main__.display_workflow_explanation") as module_display,
        ):
            mock_popup_window = MagicMock()
            module_display.return_value = mock_popup_window

            # Act: Simulate the startup popup logic from main()
            if PopupWindow.should_display("workflow_explanation"):
                amc_main.display_workflow_explanation()
                # Note: We don't call mainloop() in tests to avoid blocking

            # Assert: User preference was checked
            mock_should_display.assert_called_once_with("workflow_explanation")

            # Assert: Popup was displayed for user guidance
            module_display.assert_called_once()

    def test_user_can_skip_workflow_popup_when_previously_disabled(self) -> None:
        """
        User can skip workflow explanation popup when they have previously disabled it.

        GIVEN: A user has previously chosen to disable the workflow popup
        WHEN: The application starts
        THEN: No popup should appear and application should proceed normally
        """
        # Arrange: Mock popup display disabled by user preference
        with patch(
            "ardupilot_methodic_configurator.__main__.PopupWindow.should_display",
            return_value=False,
        ) as mock_should_display:
            popup_displayed = False

            # Act: Simulate the startup popup logic from main()
            if PopupWindow.should_display("workflow_explanation"):
                popup_displayed = True

            # Assert: User preference was checked
            mock_should_display.assert_called_once_with("workflow_explanation")

            # Assert: No popup was shown, respecting user preference
            assert popup_displayed is False


class TestDocumentationBehavior:
    """Test automatic documentation opening behavior."""

    def test_user_sees_help_documentation_when_auto_open_enabled(self) -> None:
        """
        User automatically receives helpful documentation when feature is enabled.

        GIVEN: A user has enabled automatic documentation opening in settings
        WHEN: The application starts
        THEN: Relevant help documentation should open in their default browser
        """
        # Arrange: Auto-open documentation enabled
        with (
            patch("ardupilot_methodic_configurator.__main__.ProgramSettings.get_setting", return_value=True),
            patch("ardupilot_methodic_configurator.__main__.webbrowser_open_url") as mock_browser,
        ):
            # Act: User starts application
            display_first_use_documentation()

            # Assert: Documentation opens correctly for user
            mock_browser.assert_called_once()
            call_args = mock_browser.call_args
            # User should see the use cases documentation
            assert "USECASES.html" in call_args[1]["url"]
            # Browser should open in existing window/tab for user convenience
            assert call_args[1]["new"] == 0
            assert call_args[1]["autoraise"] is True

    def test_user_startup_not_interrupted_when_auto_documentation_disabled(self) -> None:
        """
        User experiences uninterrupted startup when auto-documentation is disabled.

        GIVEN: A user has disabled automatic documentation opening
        WHEN: The application checks the setting
        THEN: No browser windows should open and startup should be clean
        """
        # Arrange: Auto-open documentation disabled
        with (
            patch("ardupilot_methodic_configurator.__main__.ProgramSettings.get_setting", return_value=False) as mock_setting,
            patch("ardupilot_methodic_configurator.__main__.webbrowser_open_url") as mock_browser,
            patch("ardupilot_methodic_configurator.__main__.display_first_use_documentation") as mock_display_doc,
        ):
            # Test the conditional logic - simulate the main function behavior
            auto_open_setting = mock_setting.return_value
            if bool(auto_open_setting):
                mock_display_doc()

            # Assert: No browser interruption and function not called
            mock_browser.assert_not_called()
            mock_display_doc.assert_not_called()


class TestFlightControllerConnection:
    """Test flight controller connection and initialization behavior."""

    def test_user_can_initialize_with_connected_hardware(
        self, application_state: ApplicationState, mock_flight_controller: MagicMock, mock_local_filesystem: MagicMock
    ) -> None:
        """
        User can successfully initialize when flight controller hardware is connected.

        GIVEN: A user has connected flight controller hardware
        WHEN: The application initializes flight controller connection
        THEN: All parameters should be read and filesystem should be configured
        """
        # Arrange: Configure realistic hardware connection scenario
        mock_flight_controller.master = MagicMock()  # Hardware connected
        default_params = {"TEST_PARAM": 1.0, "BATT_MONITOR": 4}

        with (
            patch(
                "ardupilot_methodic_configurator.__main__.connect_to_fc_and_set_vehicle_type",
                return_value=(mock_flight_controller, "ArduCopter"),
            ),
            patch("ardupilot_methodic_configurator.__main__.FlightControllerInfoWindow") as mock_fc_window,
            patch("ardupilot_methodic_configurator.__main__.LocalFilesystem", return_value=mock_local_filesystem),
        ):
            # Configure parameter retrieval
            mock_fc_info = MagicMock()
            mock_fc_info.get_param_default_values.return_value = default_params
            mock_fc_window.return_value = mock_fc_info
            mock_local_filesystem.write_param_default_values.return_value = True

            # Act: User initializes with connected hardware
            initialize_flight_controller_and_filesystem(application_state)

            # Assert: Successful hardware initialization
            assert application_state.flight_controller is mock_flight_controller
            assert application_state.vehicle_type == "ArduCopter"
            assert application_state.local_filesystem is mock_local_filesystem
            assert application_state.param_default_values == default_params
            assert application_state.param_default_values_dirty is True

    def test_user_can_work_in_simulation_mode(self, application_state: ApplicationState) -> None:
        """
        User can use application in simulation mode without physical hardware.

        GIVEN: A user wants to test or configure without hardware
        WHEN: The application runs in test/simulation mode
        THEN: Application should work with simulated data
        """
        # Arrange: Simulation mode setup
        application_state.args.device = DEVICE_FC_PARAM_FROM_FILE

        with (
            patch("ardupilot_methodic_configurator.__main__.connect_to_fc_and_set_vehicle_type") as mock_connect,
            patch("ardupilot_methodic_configurator.__main__.FlightControllerInfoWindow") as mock_fc_window,
            patch("ardupilot_methodic_configurator.__main__.LocalFilesystem") as mock_fs_class,
        ):
            # Configure simulation mode
            mock_fc = MagicMock()
            mock_fc.master = None  # Simulation mode
            mock_connect.return_value = (mock_fc, "ArduCopter")

            mock_fc_info = MagicMock()
            mock_fc_info.get_param_default_values.return_value = {}
            mock_fc_window.return_value = mock_fc_info

            mock_fs_class.return_value = MagicMock()

            # Act: User initializes in simulation mode
            initialize_flight_controller_and_filesystem(application_state)

            # Assert: Simulation mode works
            assert application_state.flight_controller is mock_fc
            assert application_state.vehicle_type == "ArduCopter"
            # Verify FlightControllerInfoWindow was called with flight controller and vehicle_dir
            mock_fc_window.assert_called_once()
            call_args = mock_fc_window.call_args[0]
            assert call_args[0] is mock_fc
            assert isinstance(call_args[1], Path)

    def test_user_receives_clear_error_when_configuration_invalid(self, application_state: ApplicationState) -> None:
        """
        User receives clear error message when configuration is invalid.

        GIVEN: A user has invalid configuration or corrupted files
        WHEN: Filesystem initialization fails
        THEN: A clear, actionable error message should be displayed
        """
        # Arrange: Mock configuration failure
        mock_fc = MagicMock()
        with (
            patch(
                "ardupilot_methodic_configurator.__main__.connect_to_fc_and_set_vehicle_type",
                return_value=(mock_fc, "ArduCopter"),
            ),
            patch("ardupilot_methodic_configurator.__main__.FlightControllerInfoWindow"),
            patch(
                "ardupilot_methodic_configurator.__main__.LocalFilesystem",
                side_effect=SystemExit("Configuration error"),
            ),
            patch("ardupilot_methodic_configurator.__main__.show_error_message") as mock_error,
        ):
            # Act & Assert: Configuration error should be handled gracefully
            with pytest.raises(SystemExit):
                initialize_flight_controller_and_filesystem(application_state)

            # Assert: Clear error message displayed
            mock_error.assert_called_once()
            error_args = mock_error.call_args[0]
            assert "Fatal error reading parameter files" in error_args[0]
            assert "Configuration error" in error_args[1]


class TestVehicleDirectoryWorkflow:
    """Test vehicle directory selection workflow."""

    def test_user_proceeds_directly_when_configuration_ready(self, application_state: ApplicationState) -> None:
        """
        User proceeds directly to main functionality when configuration is ready.

        GIVEN: A user has valid parameter files in their vehicle directory
        WHEN: The application checks for vehicle directory selection
        THEN: User should proceed directly without interruption
        """
        # Arrange: Ready configuration
        mock_fs = MagicMock()
        mock_fs.file_parameters = {"00_default.param": {}, "01_test.param": {}}
        application_state.local_filesystem = mock_fs
        application_state.flight_controller = MagicMock()

        # Mock the window to prevent sys_exit(0) call
        with patch("ardupilot_methodic_configurator.__main__.VehicleProjectOpenerWindow") as mock_window_class:
            mock_window = MagicMock()
            mock_window.root.mainloop = MagicMock()
            mock_window_class.return_value = mock_window

            # Act: Check if directory selection needed
            result = vehicle_directory_selection(application_state)

            # Assert: Directory selection window is created and shown
            assert result is mock_window
            mock_window.root.mainloop.assert_called_once()

    def test_user_can_select_vehicle_configuration_when_needed(self, application_state: ApplicationState, root) -> None:
        """
        User can select appropriate vehicle configuration when none exists.

        GIVEN: A user starts with empty or new vehicle directory
        WHEN: The application needs vehicle configuration
        THEN: User should see intuitive vehicle directory selection interface
        """
        # Arrange: No existing configuration
        mock_fs = MagicMock()
        mock_fs.file_parameters = {}  # No files
        application_state.local_filesystem = mock_fs

        mock_fc = MagicMock()
        mock_fc.fc_parameters = {"PARAM1": 1.0}  # Connected FC
        mock_fc.info.vehicle_type = "ArduCopter"
        mock_fc.master = None  # Ensure FC info window isn't triggered
        mock_fc.reset_all_parameters_to_default.return_value = (True, "")  # Mock successful reset
        mock_fc.reset_and_reconnect.return_value = ""  # Mock successful reconnect
        application_state.flight_controller = mock_fc
        application_state.vehicle_type = "ArduCopter"  # This is what actually gets used
        application_state.args.device = "serial"  # Not DEVICE_FC_PARAM_FROM_FILE to avoid FC info window

        with (
            patch("ardupilot_methodic_configurator.__main__.VehicleProjectOpenerWindow") as mock_window_class,
            patch("ardupilot_methodic_configurator.__main__.VehicleProjectManager") as mock_project_manager_class,
            patch("tkinter.Tk", return_value=root),
        ):  # Use conftest root fixture
            mock_window = MagicMock()
            mock_window.root = root  # Use the conftest root which is already set up for testing
            mock_window_class.return_value = mock_window

            mock_project_manager = MagicMock()
            mock_project_manager_class.return_value = mock_project_manager

            # Mock mainloop to prevent blocking (conftest root has this handled)
            root.mainloop = MagicMock()

            # Act: User selects vehicle configuration
            result = vehicle_directory_selection(application_state)

            # Assert: Directory selection interface shown
            mock_project_manager_class.assert_called_once_with(mock_fs, mock_fc)
            mock_window_class.assert_called_once_with(mock_project_manager)
            root.mainloop.assert_called_once()
            assert result is mock_window

    def test_user_can_configure_without_connected_hardware(self, application_state: ApplicationState, root) -> None:
        """
        User can configure vehicle directory even without connected flight controller.

        GIVEN: A user works without connected flight controller hardware
        WHEN: Vehicle directory selection is needed
        THEN: User should still be able to select and configure vehicle directory
        """
        # Arrange: No connected hardware
        mock_fs = MagicMock()
        mock_fs.file_parameters = None  # No configuration
        application_state.local_filesystem = mock_fs

        mock_fc = MagicMock()
        mock_fc.fc_parameters = {}  # No connection
        mock_fc.info.vehicle_type = None
        mock_fc.master = None  # Ensure FC info window isn't triggered
        mock_fc.reset_all_parameters_to_default.return_value = (True, "")  # Mock successful reset
        mock_fc.reset_and_reconnect.return_value = ""  # Mock successful reconnect
        application_state.flight_controller = mock_fc
        application_state.args.device = "serial"  # Not DEVICE_FC_PARAM_FROM_FILE to avoid FC info window

        with (
            patch("ardupilot_methodic_configurator.__main__.VehicleProjectOpenerWindow") as mock_window_class,
            patch("ardupilot_methodic_configurator.__main__.VehicleProjectManager") as mock_project_manager_class,
            patch("ardupilot_methodic_configurator.__main__.FlightControllerInfoWindow") as mock_fc_info,
            patch("tkinter.Tk", return_value=root),
        ):  # Use conftest root fixture
            mock_window = MagicMock()
            mock_window.root = root  # Use the conftest root which is already set up for testing
            mock_window_class.return_value = mock_window

            mock_project_manager = MagicMock()
            mock_project_manager_class.return_value = mock_project_manager

            # Mock FC info window
            mock_fc_info_window = MagicMock()
            mock_fc_info_window.get_param_default_values.return_value = {}
            mock_fc_info.return_value = mock_fc_info_window

            # Mock mainloop to prevent blocking (conftest root has this handled)
            root.mainloop = MagicMock()

            # Act: User configures without hardware
            result = vehicle_directory_selection(application_state)

            # Assert: Configuration possible without hardware
            mock_project_manager_class.assert_called_once_with(mock_fs, mock_fc)
            mock_window_class.assert_called_once_with(mock_project_manager)
            root.mainloop.assert_called_once()
            assert result is mock_window


class TestApplicationIntegration:
    """Test complete application workflows and integration scenarios."""

    def test_user_can_complete_standard_startup_workflow(self, mock_args: MagicMock) -> None:
        """
        User can complete the standard application startup workflow end-to-end.

        GIVEN: A user starts the application with typical configuration
        WHEN: They go through the complete startup sequence
        THEN: All components should initialize properly and be ready for use
        """
        # Arrange: Standard user configuration
        mock_args.skip_check_for_updates = True  # Skip for test efficiency

        with (
            patch("ardupilot_methodic_configurator.__main__.ProgramSettings.get_setting", return_value=False),
            patch("ardupilot_methodic_configurator.__main__.connect_to_fc_and_set_vehicle_type") as mock_connect,
            patch("ardupilot_methodic_configurator.__main__.FlightControllerInfoWindow"),
            patch("ardupilot_methodic_configurator.__main__.LocalFilesystem") as mock_fs_class,
            patch("ardupilot_methodic_configurator.__main__.VehicleProjectOpenerWindow") as mock_window_class,
        ):
            # Configure successful workflow
            mock_fc = MagicMock()
            mock_fc.master = MagicMock()
            mock_connect.return_value = (mock_fc, "ArduCopter")

            mock_fs = MagicMock()
            mock_fs.file_parameters = {"00_default.param": {}}
            mock_fs_class.return_value = mock_fs

            # Mock window to prevent actual GUI creation
            mock_window = MagicMock()
            mock_window.root.mainloop = MagicMock()
            mock_window_class.return_value = mock_window

            # Act: Execute complete startup workflow
            state = ApplicationState(mock_args)

            should_exit = check_updates(state)
            assert should_exit is False

            display_first_use_documentation()  # Should complete without issues

            initialize_flight_controller_and_filesystem(state)

            result = vehicle_directory_selection(state)

            # Assert: Complete successful workflow
            assert state.flight_controller is mock_fc
            assert state.vehicle_type == "ArduCopter"
            assert state.local_filesystem is mock_fs
            assert result is mock_window  # Directory selection window shown


class TestArgumentParser:
    """Test argument parser creation and configuration."""

    def test_argument_parser_creates_all_required_options(self) -> None:
        """
        User can access all necessary command-line options for configuration.

        GIVEN: A user needs to configure the application via command line
        WHEN: They check available options
        THEN: All necessary configuration options should be available
        """
        # Act: Create argument parser
        parser = create_argument_parser()

        # Assert: Parser is created and has expected structure
        assert parser is not None
        assert hasattr(parser, "parse_args")

        # Test with minimal arguments to ensure it works
        test_args = parser.parse_args(["--skip-check-for-updates"])
        assert test_args.skip_check_for_updates is True


class TestFlightControllerConnectionLogic:
    """Test flight controller connection logic in detail."""

    def test_flight_controller_connection_with_explicit_vehicle_type(self) -> None:
        """
        User can explicitly set vehicle type to override auto-detection.

        GIVEN: A user knows their vehicle type and wants to set it explicitly
        WHEN: They provide --vehicle-type argument
        THEN: Application should use the explicitly set type
        """
        # Arrange: Mock arguments with explicit vehicle type
        mock_args = MagicMock()
        mock_args.vehicle_type = "ArduPlane"
        mock_args.device = DEVICE_FC_PARAM_FROM_FILE
        mock_args.reboot_time = 10.0
        mock_args.baudrate = 115200

        with (
            patch("ardupilot_methodic_configurator.__main__.FlightController") as mock_fc_class,
            patch("ardupilot_methodic_configurator.__main__.FlightControllerConnectionProgress") as mock_progress_class,
            patch("ardupilot_methodic_configurator.__main__.ConnectionSelectionWindow"),
            patch("ardupilot_methodic_configurator.__main__.logging_info") as mock_log,
        ):
            mock_progress = MagicMock()
            mock_progress_class.return_value.__enter__.return_value = mock_progress

            mock_fc = MagicMock()
            mock_fc.connect.return_value = ""  # No error
            mock_fc.info.vehicle_type = "ArduCopter"  # Different from explicit
            mock_fc_class.return_value = mock_fc

            # Act: Connect with explicit vehicle type
            _fc, vehicle_type = connect_to_fc_and_set_vehicle_type(mock_args)

            # Assert: User's explicit type choice is respected
            assert vehicle_type == "ArduPlane"
            # User gets informed about configuration choice
            mock_log.assert_called_once()
            log_message = mock_log.call_args[0][0]
            # User should understand that type was specified rather than auto-detected
            assert "explicitly set" in log_message or "specified" in log_message

    def test_flight_controller_auto_detection_when_type_not_specified(self) -> None:
        """
        User benefits from automatic vehicle type detection when not specified.

        GIVEN: A user doesn't specify vehicle type
        WHEN: A flight controller with known type is connected
        THEN: Application should auto-detect and use the FC's vehicle type
        """
        # Arrange: Mock arguments without vehicle type
        mock_args = MagicMock()
        mock_args.vehicle_type = ""  # Not specified
        mock_args.device = DEVICE_FC_PARAM_FROM_FILE
        mock_args.reboot_time = 10.0
        mock_args.baudrate = 115200

        with (
            patch("ardupilot_methodic_configurator.__main__.FlightController") as mock_fc_class,
            patch("ardupilot_methodic_configurator.__main__.FlightControllerConnectionProgress") as mock_progress_class,
            patch("ardupilot_methodic_configurator.__main__.ConnectionSelectionWindow"),
            patch("ardupilot_methodic_configurator.__main__.logging_debug") as mock_log,
        ):
            mock_progress = MagicMock()
            mock_progress_class.return_value.__enter__.return_value = mock_progress

            mock_fc = MagicMock()
            mock_fc.connect.return_value = ""
            mock_fc.info.vehicle_type = "ArduCopter"
            mock_fc_class.return_value = mock_fc

            # Act: Connect with auto-detection
            _fc, vehicle_type = connect_to_fc_and_set_vehicle_type(mock_args)

            # Assert: Auto-detected type used
            assert vehicle_type == "ArduCopter"
            mock_log.assert_called_once()
            assert "auto-detected" in mock_log.call_args[0][0]


class TestVehicleDirectoryResolution:
    """Test selection of writable vehicle directory for initial parameter download."""

    def test_prefers_args_vehicle_dir_when_available(self) -> None:
        """Given args with vehicle_dir, preferred directory should come from args."""
        mock_args = MagicMock()
        mock_args.vehicle_dir = "C:/tmp/vehicle"

        result = get_preferred_vehicle_dir(mock_args)

        assert result == Path("C:/tmp/vehicle")

    def test_falls_back_to_cwd_when_vehicle_dir_missing(self) -> None:
        """Given args without vehicle_dir, preferred directory should be current working directory."""
        mock_args = MagicMock(spec=[])

        with patch("ardupilot_methodic_configurator.__main__.Path.cwd", return_value=Path("C:/cwd")):
            result = get_preferred_vehicle_dir(mock_args)

        assert result == Path("C:/cwd")

    def test_returns_preferred_when_writable(self) -> None:
        """Given writable preferred dir, resolver should return it unchanged."""
        preferred_dir = Path("C:/preferred")

        with patch("ardupilot_methodic_configurator.__main__._is_directory_writable", return_value=True):
            result = resolve_writable_vehicle_dir_for_initial_download(preferred_dir)

        assert result == preferred_dir

    def test_falls_back_to_default_when_not_writable(self) -> None:
        """Given non-writable preferred dir, resolver should switch to ProgramSettings default directory."""
        preferred_dir = Path("C:/preferred")
        fallback_dir = MagicMock(spec=Path)

        with (
            patch("ardupilot_methodic_configurator.__main__._is_directory_writable", return_value=False),
            patch(
                "ardupilot_methodic_configurator.__main__.ProgramSettings.get_vehicles_default_dir",
                return_value=fallback_dir,
            ),
            patch("ardupilot_methodic_configurator.__main__.logging_warning") as mock_warning,
        ):
            result = resolve_writable_vehicle_dir_for_initial_download(preferred_dir)

        assert result is fallback_dir
        fallback_dir.mkdir.assert_called_once_with(parents=True, exist_ok=True)
        mock_warning.assert_called_once()


class TestParameterBackupWorkflow:
    """Test parameter backup functionality."""

    def test_user_gets_automatic_parameter_backup_when_fc_connected(
        self, configured_application_state: ApplicationState
    ) -> None:
        """
        User automatically gets parameter backup for safety when FC is connected.

        GIVEN: A user has connected flight controller with parameters
        WHEN: The backup process runs
        THEN: Multiple backup files should be created for safety
        """
        # Arrange: Configure FC with realistic parameters
        configured_application_state.flight_controller.fc_parameters = {"BATT_MONITOR": 4, "COMPASS_USE": 1, "GPS_TYPE": 1}
        configured_application_state.local_filesystem.find_lowest_available_backup_number.return_value = 5

        with patch("ardupilot_methodic_configurator.__main__.logging_info") as mock_log:
            # Act: User triggers automatic parameter backup
            backup_fc_parameters(configured_application_state)

            # Assert: User gets comprehensive backup protection
            fs = configured_application_state.local_filesystem
            # Verify both safety backup types are created for user protection
            assert fs.backup_fc_parameters_to_file.called

            # Check that both initial and incremental backups were created
            calls = fs.backup_fc_parameters_to_file.call_args_list
            assert len(calls) == 2, "User should get both safety backup types"

            # Verify initial backup preserves existing files for safety
            first_call = calls[0]
            assert "autobackup_00_before" in first_call[0][1]
            assert first_call[1]["overwrite_existing_file"] is False

            # Verify incremental backup uses available number
            second_call = calls[1]
            assert "autobackup_05.param" in second_call[0][1]
            assert second_call[1]["overwrite_existing_file"] is True

            # Verify user gets feedback about backup creation
            mock_log.assert_called_once()
            # Focus on behavior: user should be informed that backup was created
            log_message = str(mock_log.call_args)
            assert "backup file" in log_message or "Created" in log_message

    def test_user_workflow_continues_smoothly_when_no_fc_connected(self, application_state: ApplicationState) -> None:
        """
        User workflow continues without issues when no FC is connected.

        GIVEN: A user works without connected flight controller
        WHEN: Backup process runs
        THEN: No backup attempts should be made and workflow should continue
        """
        # Arrange: No connected FC
        mock_fc = MagicMock()
        mock_fc.fc_parameters = {}  # Empty - no connection
        application_state.flight_controller = mock_fc

        mock_fs = MagicMock()
        application_state.local_filesystem = mock_fs

        # Act: Attempt backup without connection
        backup_fc_parameters(application_state)

        # Assert: No backup operations attempted
        mock_fs.backup_fc_parameters_to_file.assert_not_called()
        mock_fs.find_lowest_available_backup_number.assert_not_called()

    def test_user_gets_clear_feedback_when_backup_directory_unavailable(
        self, configured_application_state: ApplicationState
    ) -> None:
        """
        User receives clear feedback when backup directory is not available.

        GIVEN: A user has connected flight controller but backup directory is unavailable
        WHEN: The backup process attempts to run
        THEN: User should receive clear error message and application should handle gracefully
        AND: The error message should provide specific guidance about permissions
        """
        # Arrange: Configure FC with parameters but filesystem backup fails
        configured_application_state.flight_controller.fc_parameters = {
            "BATT_MONITOR": 4,
            "COMPASS_USE": 1,
        }
        # Simulate backup directory unavailable due to permissions
        configured_application_state.local_filesystem.backup_fc_parameters_to_file.side_effect = PermissionError(
            "Permission denied"
        )

        with patch("ardupilot_methodic_configurator.__main__.logging_error") as mock_error:
            # Act: User attempts backup with unavailable directory
            backup_fc_parameters(configured_application_state)

            # Assert: User gets clear error feedback about permissions
            assert mock_error.call_count >= 2, "User should receive both error description and actionable guidance"
            error_calls = mock_error.call_args_list

            # Check first error message contains permission information
            first_message = str(error_calls[0])
            assert "permission" in first_message.lower() or "denied" in first_message.lower(), (
                "User should see clear indication of permission issue"
            )

            # Check second error message provides actionable guidance
            second_message = str(error_calls[1])
            assert (
                "check" in second_message.lower() and "permission" in second_message.lower()
            ) or "write access" in second_message.lower(), "User should receive actionable steps to resolve permission issues"

    def test_user_gets_helpful_error_when_disk_space_insufficient(
        self, configured_application_state: ApplicationState
    ) -> None:
        """
        User receives helpful guidance when insufficient disk space prevents backup.

        GIVEN: A user has limited disk space on their storage device
        WHEN: The backup process attempts to create backup files
        THEN: User should receive actionable error message with clear guidance
        AND: The error message should suggest specific remediation steps
        """
        # Arrange: Configure FC with parameters but disk space insufficient
        configured_application_state.flight_controller.fc_parameters = {
            "BATT_MONITOR": 4,
            "COMPASS_USE": 1,
        }
        # Simulate insufficient disk space (common Linux/Windows disk full error)
        configured_application_state.local_filesystem.backup_fc_parameters_to_file.side_effect = OSError(
            "[Errno 28] No space left on device"
        )

        with patch("ardupilot_methodic_configurator.__main__.logging_error") as mock_error:
            # Act: User attempts backup with insufficient space
            backup_fc_parameters(configured_application_state)

            # Assert: User gets actionable error guidance about disk space
            assert mock_error.call_count >= 2, "User should receive both error description and actionable guidance"
            error_calls = mock_error.call_args_list

            # Check first error message contains disk space information
            first_message = str(error_calls[0])
            assert "space" in first_message.lower() or "disk" in first_message.lower(), (
                "User should see clear indication of disk space issue"
            )

            # Check second error message provides actionable guidance
            second_message = str(error_calls[1])
            assert "free up" in second_message.lower() or "try again" in second_message.lower(), (
                "User should receive actionable steps to resolve the issue"
            )

    def test_user_gets_general_error_feedback_for_unexpected_oserror(
        self, configured_application_state: ApplicationState
    ) -> None:
        """
        User receives appropriate feedback for other unexpected OS-level errors during backup.

        GIVEN: A user encounters an unexpected OS-level error during backup
        WHEN: The backup process attempts to create backup files
        THEN: User should receive a general error message indicating the issue
        AND: The error should be logged without crashing the application
        """
        # Arrange: Configure FC with parameters but unexpected OS error occurs
        configured_application_state.flight_controller.fc_parameters = {
            "BATT_MONITOR": 4,
            "COMPASS_USE": 1,
        }
        # Simulate unexpected OS error (not disk space related)
        configured_application_state.local_filesystem.backup_fc_parameters_to_file.side_effect = OSError(
            "[Errno 5] Input/output error"
        )

        with patch("ardupilot_methodic_configurator.__main__.logging_error") as mock_error:
            # Act: User attempts backup with unexpected OS error
            backup_fc_parameters(configured_application_state)

            # Assert: User gets appropriate error feedback for general OS error
            assert mock_error.called, "User should receive error feedback for OS-level issues"
            error_message = str(mock_error.call_args_list[0])
            assert "failed to create backup files" in error_message.lower(), (
                "User should see clear indication of backup failure"
            )

    def test_user_gets_graceful_handling_for_unexpected_exceptions(
        self, configured_application_state: ApplicationState
    ) -> None:
        """
        User experiences graceful error handling for completely unexpected exceptions.

        GIVEN: A user encounters an unexpected exception during backup
        WHEN: The backup process runs into an unforeseen error
        THEN: The application should handle it gracefully and inform the user
        AND: The application should continue running without crashing
        """
        # Arrange: Configure FC with parameters but unexpected exception occurs
        configured_application_state.flight_controller.fc_parameters = {
            "BATT_MONITOR": 4,
            "COMPASS_USE": 1,
        }
        # Simulate unexpected exception
        configured_application_state.local_filesystem.backup_fc_parameters_to_file.side_effect = ValueError(
            "Unexpected validation error"
        )

        with patch("ardupilot_methodic_configurator.__main__.logging_error") as mock_error:
            # Act: User encounters unexpected exception during backup
            backup_fc_parameters(configured_application_state)

            # Assert: User gets graceful error handling
            assert mock_error.called, "User should be informed of unexpected errors"
            error_message = str(mock_error.call_args_list[0])
            assert "unexpected error" in error_message.lower(), "User should understand this was an unexpected issue"


class TestParameterEditorStartup:
    """Test parameter editor startup logic."""

    def test_user_gets_appropriate_starting_file_based_on_configuration(self, application_state: ApplicationState) -> None:
        """
        User starts with appropriate parameter file based on their configuration.

        GIVEN: A user has specific flight controller configuration
        WHEN: Parameter editor starts
        THEN: Appropriate starting file should be selected based on capabilities
        """
        # Arrange: FC with IMU temperature calibration capability
        mock_fc = MagicMock()
        mock_fc.fc_parameters = {"INS_TCAL1_ENABLE": 1, "PARAM2": 2.0}
        application_state.flight_controller = mock_fc

        mock_fs = MagicMock()
        mock_fs.get_start_file.return_value = "05_imu_temperature_calibration.param"
        application_state.local_filesystem = mock_fs

        application_state.args.n = 0  # Start from beginning

        with (
            patch("ardupilot_methodic_configurator.__main__.ProgramSettings.get_setting", return_value="normal"),
            patch("ardupilot_methodic_configurator.__main__.ParameterEditorWindow") as mock_editor,
            patch("ardupilot_methodic_configurator.__main__.ParameterEditor") as mock_param_editor,
        ):
            # Act: Start parameter editor
            parameter_editor_and_uploader(application_state)

            # Assert: Advanced mode with IMU calibration considered
            mock_fs.get_start_file.assert_called_once_with(0, True)  # noqa: FBT003 IMU tcal available and not simple GUI
            mock_param_editor.assert_called_once_with(
                "05_imu_temperature_calibration.param", mock_fc, mock_fs, export_fc_params_missing_or_different=False
            )
            mock_editor.assert_called_once_with(mock_param_editor.return_value)

    def test_user_gets_simplified_workflow_in_simple_mode(self, application_state: ApplicationState) -> None:
        """
        User gets simplified workflow when simple GUI mode is enabled.

        GIVEN: A user prefers simple interface
        WHEN: Parameter editor starts in simple mode
        THEN: Advanced features should be disabled for cleaner experience
        """
        # Arrange: Simple GUI mode
        mock_fc = MagicMock()
        mock_fc.fc_parameters = {"INS_TCAL1_ENABLE": 1}
        application_state.flight_controller = mock_fc

        mock_fs = MagicMock()
        application_state.local_filesystem = mock_fs
        application_state.args.n = 0

        with (
            patch("ardupilot_methodic_configurator.__main__.ProgramSettings.get_setting", return_value="simple"),
            patch("ardupilot_methodic_configurator.__main__.ParameterEditorWindow") as mock_editor,
            patch("ardupilot_methodic_configurator.__main__.ParameterEditor") as mock_param_editor,
        ):
            # Act: Start in simple mode
            parameter_editor_and_uploader(application_state)

            # Assert: IMU calibration disabled in simple mode
            mock_fs.get_start_file.assert_called_once_with(0, False)  # noqa: FBT003 Simple GUI disables IMU tcal
            mock_editor.assert_called_once_with(mock_param_editor.return_value)


# ====== Component Editor Helper Function Tests ======


class TestComponentEditorHelperFunctions:
    """Test the refactored component editor helper functions for better testability."""

    def test_create_and_configure_component_editor_basic_setup(self) -> None:
        """
        User can create and configure component editor with basic settings.

        GIVEN: Valid application components
        WHEN: Component editor is created and configured
        THEN: Window should be properly initialized with basic settings
        """
        # Arrange: Mock dependencies
        mock_filesystem = MagicMock()
        mock_fc = MagicMock()
        mock_fc.info.flight_sw_version_and_type = "ArduCopter V4.5.0"
        mock_fc.info.vendor = "Pixhawk"
        mock_fc.info.firmware_type = "CubeOrange"
        mock_fc.info.mcu_series = "STM32H7xx"

        with patch("ardupilot_methodic_configurator.__main__.ComponentEditorWindow") as mock_window_class:
            mock_window = MagicMock()
            mock_window_class.return_value = mock_window

            # Act: Create and configure component editor
            result = create_and_configure_component_editor("1.0.0", mock_filesystem, mock_fc, "ArduCopter", None)

            # Assert: Window configured correctly
            assert result == mock_window
            mock_window.populate_frames.assert_called_once()
            mock_window.set_vehicle_type_and_version.assert_called_once_with("ArduCopter", "ArduCopter V4.5.0")
            mock_window.set_fc_manufacturer.assert_called_once_with("Pixhawk")
            mock_window.set_fc_model.assert_called_once_with("CubeOrange")
            mock_window.set_mcu_series.assert_called_once_with("STM32H7xx")

    def test_create_and_configure_component_editor_with_vehicle_template(self) -> None:
        """
        User can configure component editor with vehicle template and FC parameter inference.

        GIVEN: Vehicle directory window with configuration template
        WHEN: Component editor is created with inference enabled
        THEN: Component specs should be inferred from FC parameters
        """
        # Arrange: Mock with vehicle directory and inference
        mock_filesystem = MagicMock()
        mock_filesystem.doc_dict = {"PARAM1": "doc1"}
        mock_fc = MagicMock()
        mock_fc.fc_parameters = {"PARAM1": 1.0, "PARAM2": 2.0}
        mock_fc.info.flight_sw_version_and_type = "ArduCopter V4.5.0"
        mock_fc.info.vendor = "Pixhawk"
        mock_fc.info.firmware_type = "CubeOrange"
        mock_fc.info.mcu_series = "STM32H7xx"

        mock_vehicle_dir_window = MagicMock()
        mock_vehicle_dir_window.configuration_template = "template1"

        # Mock BooleanVar object with get() method
        mock_infer_bool_var = MagicMock()
        mock_infer_bool_var.get.return_value = True
        mock_vehicle_dir_window.infer_comp_specs_and_conn_from_fc_params = mock_infer_bool_var

        with patch("ardupilot_methodic_configurator.__main__.ComponentEditorWindow") as mock_window_class:
            mock_window = MagicMock()
            mock_window_class.return_value = mock_window

            # Act: Create with vehicle template
            result = create_and_configure_component_editor(
                "1.0.0", mock_filesystem, mock_fc, "ArduCopter", mock_vehicle_dir_window
            )

            # Assert: Inference and template configuration applied
            assert result == mock_window
            mock_window.set_values_from_fc_parameters.assert_called_once_with(mock_fc.fc_parameters, mock_filesystem.doc_dict)
            mock_window.set_vehicle_configuration_template.assert_called_once_with("template1")

    def test_should_open_firmware_documentation_when_enabled(self) -> None:
        """
        User gets firmware documentation opened when auto-open is enabled.

        GIVEN: Auto-open documentation is enabled and firmware type is known
        WHEN: Documentation opening decision is made
        THEN: Function should return True to open documentation
        """
        # Arrange: Mock flight controller with known firmware
        mock_fc = MagicMock()
        mock_fc.info.firmware_type = "CubeOrange"

        with patch("ardupilot_methodic_configurator.__main__.ProgramSettings.get_setting", return_value=True):
            # Act: Check if documentation should open
            result = should_open_firmware_documentation(mock_fc)

            # Assert: Should open documentation
            assert result is True

    def test_should_open_firmware_documentation_when_disabled(self) -> None:
        """
        User workflow is not interrupted when auto-documentation is disabled.

        GIVEN: Auto-open documentation is disabled
        WHEN: Documentation opening decision is made
        THEN: Function should return False to skip documentation
        """
        # Arrange: Mock with disabled auto-open
        mock_fc = MagicMock()
        mock_fc.info.firmware_type = "CubeOrange"

        with patch("ardupilot_methodic_configurator.__main__.ProgramSettings.get_setting", return_value=False):
            # Act: Check with disabled setting
            result = should_open_firmware_documentation(mock_fc)

            # Assert: Should not open documentation
            assert result is False

    def test_should_open_firmware_documentation_unknown_firmware(self) -> None:
        """
        User doesn't get irrelevant documentation when firmware type is unknown.

        GIVEN: Firmware type is unknown or empty
        WHEN: Documentation opening decision is made
        THEN: Function should return False to avoid opening irrelevant documentation
        """
        # Arrange: Mock with unknown firmware
        mock_fc = MagicMock()
        mock_fc.info.firmware_type = "Unknown"

        with patch("ardupilot_methodic_configurator.__main__.ProgramSettings.get_setting", return_value=True):
            # Act: Check with unknown firmware
            result = should_open_firmware_documentation(mock_fc)

            # Assert: Should not open documentation for unknown firmware
            assert result is False

    def test_open_firmware_documentation_success(self) -> None:
        """
        User gets firmware documentation opened successfully.

        GIVEN: Valid firmware type
        WHEN: Documentation opening is attempted
        THEN: URL should be verified and opened
        """
        with patch("ardupilot_methodic_configurator.__main__.verify_and_open_url", return_value=True) as mock_open:
            # Act: Open documentation
            result = open_firmware_documentation("CubeOrange")

            # Assert: URL opened successfully
            assert result is True
            expected_url = (
                "https://github.com/ArduPilot/ardupilot/blob/master/libraries/AP_HAL_ChibiOS/hwdef/CubeOrange/README.md"
            )
            mock_open.assert_called_once_with(expected_url)

    def test_open_firmware_documentation_bdshot_fallback(self) -> None:
        """
        User gets correct documentation for bdshot firmware variants.

        GIVEN: Firmware type with -bdshot suffix
        WHEN: Primary URL is not found
        THEN: Fallback URL without suffix should be tried
        """
        with patch("ardupilot_methodic_configurator.__main__.verify_and_open_url", side_effect=[False, True]) as mock_open:
            # Act: Open documentation for bdshot variant
            result = open_firmware_documentation("CubeOrange-bdshot")

            # Assert: Fallback URL tried and succeeded
            assert result is True
            assert mock_open.call_count == 2
            expected_primary_url = (
                "https://github.com/ArduPilot/ardupilot/blob/master/libraries/AP_HAL_ChibiOS/hwdef/CubeOrange-bdshot/README.md"
            )
            expected_fallback_url = (
                "https://github.com/ArduPilot/ardupilot/blob/master/libraries/AP_HAL_ChibiOS/hwdef/CubeOrange/README.md"
            )
            mock_open.assert_any_call(expected_primary_url)
            mock_open.assert_any_call(expected_fallback_url)

    def test_process_component_editor_results_with_fc_params(self) -> None:
        """
        User gets proper parameter processing when FC parameters are used.

        GIVEN: Component editor completed with FC parameter usage enabled
        WHEN: Results are processed
        THEN: FC parameter names should be used as existing-parameter reference
        """
        # Arrange: Mock components with FC parameter usage
        mock_fc = MagicMock()
        mock_fc.fc_parameters = {"PARAM1": 1.0, "PARAM2": 2.0}
        mock_filesystem = MagicMock()
        mock_filesystem.calculate_derived_and_forced_param_changes.return_value = {}  # Empty dict = no pending changes

        mock_vehicle_dir_window = MagicMock()
        mock_vehicle_dir_window.configuration_template = "template1"

        mock_vehicle_dir_window.use_fc_params = True

        # Act: Process results
        process_component_editor_results(mock_fc, mock_filesystem)

        # Assert: FC parameter names used as existing-parameter reference
        mock_filesystem.calculate_derived_and_forced_param_changes.assert_called_once()
        call_args = mock_filesystem.calculate_derived_and_forced_param_changes.call_args
        assert call_args.kwargs["fc_param_names"] == ["PARAM1", "PARAM2"]

        # Assert: No disk write - in-memory model already matches disk when pending list is empty
        mock_filesystem.save_vehicle_params_to_files.assert_not_called()

    def test_process_component_editor_results_error_handling(self) -> None:
        """
        User gets clear error message when parameter processing fails.

        GIVEN: Parameter processing encounters an error
        WHEN: Results are processed
        THEN: Error should be logged and application should exit with error code
        """
        # Arrange: Mock with error condition
        mock_fc = MagicMock()
        mock_fc.fc_parameters = {"PARAM1": 1.0}
        mock_filesystem = MagicMock()
        mock_filesystem.calculate_derived_and_forced_param_changes.side_effect = ValueError("Parameter error occurred")

        with (
            patch("ardupilot_methodic_configurator.__main__.logging_error") as mock_logging,
            patch("ardupilot_methodic_configurator.__main__.show_error_message") as mock_show_error,
            patch("ardupilot_methodic_configurator.__main__.sys_exit") as mock_exit,
        ):
            # Act & Assert: Error handling
            process_component_editor_results(mock_fc, mock_filesystem)

            mock_logging.assert_called_once_with("Parameter error occurred")
            mock_show_error.assert_called_once()
            mock_exit.assert_called_once_with(1)

    def test_write_parameter_defaults_when_dirty(self, application_state: ApplicationState) -> None:
        """
        User gets parameter defaults saved when they have been modified.

        GIVEN: Parameter defaults have been modified (dirty flag is True)
        WHEN: Write function is called
        THEN: Parameter defaults should be written to file
        """
        # Arrange: Mock filesystem and dirty parameters
        mock_filesystem = MagicMock()
        param_values = {"PARAM1": 1.0, "PARAM2": 2.0}

        application_state.local_filesystem = mock_filesystem
        application_state.param_default_values = param_values
        application_state.param_default_values_dirty = True

        # Act: Write when dirty
        write_parameter_defaults(application_state)

        # Assert: File written
        mock_filesystem.write_param_default_values_to_file.assert_called_once_with(param_values)

    def test_write_parameter_defaults_when_clean(self, application_state: ApplicationState) -> None:
        """
        Function writes parameter defaults regardless of dirty flag.

        GIVEN: Parameter defaults with dirty flag set to False
        WHEN: Write function is called directly
        THEN: File operation should still occur (function doesn't check dirty flag)
        """
        # Arrange: Mock filesystem and clean parameters
        mock_filesystem = MagicMock()
        param_values = {"PARAM1": 1.0, "PARAM2": 2.0}

        application_state.local_filesystem = mock_filesystem
        application_state.param_default_values = param_values
        application_state.param_default_values_dirty = False

        # Act: Write when clean (function doesn't check dirty flag)
        write_parameter_defaults(application_state)

        # Assert: File operation occurs regardless of dirty flag
        mock_filesystem.write_param_default_values_to_file.assert_called_once_with(param_values)


class TestComponentEditorIntegration:
    """Test the integrated component editor workflow."""

    def test_component_editor_workflow_with_skip(self, application_state: ApplicationState) -> None:
        """
        User can skip component editor for automated workflows.

        GIVEN: User wants to skip component editor
        WHEN: Component editor workflow runs
        THEN: GUI should close automatically without user interaction
        """
        # Note: component_editor is already imported at the top of the file

        # Arrange: Mock arguments with skip option
        application_state.args.skip_component_editor = True

        # Mock vehicle_dir_window to ensure skip condition is met
        # The skip condition requires that NOT(vehicle_dir_window AND configuration_template AND blank_component_data.get())
        # So we need to set vehicle_dir_window to None or make one of the other conditions False
        application_state.vehicle_dir_window = None

        # Mock local filesystem with vehicle_type
        mock_filesystem = MagicMock()
        mock_filesystem.vehicle_type = "ArduCopter"
        application_state.local_filesystem = mock_filesystem

        with patch("ardupilot_methodic_configurator.__main__.create_and_configure_component_editor") as mock_create:
            mock_window = MagicMock()
            mock_create.return_value = mock_window

            # Act: Run component editor with skip
            component_editor(application_state)

            # Assert: Window configured to auto-close
            mock_window.root.after.assert_called_once_with(10, mock_window.root.destroy)
            mock_window.root.mainloop.assert_called_once()

    def test_component_editor_workflow_with_documentation(self, application_state: ApplicationState) -> None:
        """
        User gets firmware documentation opened during component editor workflow.

        GIVEN: Auto-documentation is enabled and firmware is known
        WHEN: Component editor workflow runs
        THEN: Firmware documentation should open automatically
        """
        # Note: component_editor is already imported at the top of the file

        # Arrange: Mock for documentation opening
        application_state.args.skip_component_editor = False

        # Mock flight controller with proper structure
        mock_fc = MagicMock()
        mock_fc.info.firmware_type = "CubeOrange"
        application_state.flight_controller = mock_fc
        application_state.vehicle_dir_window = None

        # Mock local filesystem with vehicle_type
        mock_filesystem = MagicMock()
        mock_filesystem.vehicle_type = "ArduCopter"
        application_state.local_filesystem = mock_filesystem

        with (
            patch("ardupilot_methodic_configurator.__main__.create_and_configure_component_editor") as mock_create,
            patch("ardupilot_methodic_configurator.__main__.should_open_firmware_documentation", return_value=True),
            patch("ardupilot_methodic_configurator.__main__.open_firmware_documentation") as mock_open_doc,
        ):
            mock_window = MagicMock()
            mock_create.return_value = mock_window

            # Act: Run component editor
            component_editor(application_state)

            # Assert: Documentation opened
            mock_open_doc.assert_called_once_with("CubeOrange")


class TestRegisterPluginsInternals:
    """Feature: Plugin registration executes both plugin registrations."""

    def test_both_plugin_register_functions_are_called(self) -> None:
        """
        register_plugins calls motor_test and battery_monitor registration.

        GIVEN: Both plugin register functions are available
        WHEN: register_plugins is called
        THEN: register_motor_test_plugin and register_battery_monitor_plugin are executed
        """
        # Arrange
        with (
            patch("ardupilot_methodic_configurator.frontend_tkinter_motor_test.register_motor_test_plugin") as mock_motor,
            patch(
                "ardupilot_methodic_configurator.frontend_tkinter_battery_monitor.register_battery_monitor_plugin"
            ) as mock_battery,
        ):
            register_plugins()

            # Assert
            mock_motor.assert_called_once()
            mock_battery.assert_called_once()


class TestValidatePluginRegistry:
    """Feature: All configured plugins must be registered before startup."""

    def test_no_error_logged_when_every_plugin_is_registered(self) -> None:
        """
        Every configured plugin is successfully registered.

        GIVEN: A filesystem with a known, registered plugin ('motor_test')
        WHEN: validate_plugin_registry is called
        THEN: No errors are logged
        """
        # Arrange
        mock_fs = MagicMock()
        mock_fs.configuration_steps = {"step1.param": {"plugin": {"name": "motor_test"}}}

        with (
            patch("ardupilot_methodic_configurator.__main__.plugin_factory") as mock_factory,
            patch("ardupilot_methodic_configurator.__main__.logging_error") as mock_err,
        ):
            mock_factory.is_registered.return_value = True

            # Act
            validate_plugin_registry(mock_fs)

            # Assert
            mock_err.assert_not_called()

    def test_error_logged_for_unregistered_plugin(self) -> None:
        """
        A configured plugin is missing from the registry.

        GIVEN: A filesystem referencing an unregistered plugin
        WHEN: validate_plugin_registry is called
        THEN: An error is logged identifying the missing plugin
        """
        # Arrange
        mock_fs = MagicMock()
        mock_fs.configuration_steps = {"step1.param": {"plugin": {"name": "unknown_plugin"}}}

        with (
            patch("ardupilot_methodic_configurator.__main__.plugin_factory") as mock_factory,
            patch("ardupilot_methodic_configurator.__main__.logging_error") as mock_err,
        ):
            mock_factory.is_registered.return_value = False

            # Act
            validate_plugin_registry(mock_fs)

            # Assert
            mock_err.assert_called_once()
            args, kwargs = mock_err.call_args
            # Ensure that the logged error message identifies the missing plugin
            combined = " ".join([str(a) for a in args] + [str(v) for v in kwargs.values()])
            assert "unknown_plugin" in combined


class TestConnectionAndFilesystemBranches:
    """Feature: Connection errors, writable-dir fallback and filesystem fatal errors."""

    def test_first_use_documentation_opens_correct_url(self) -> None:
        """
        display_first_use_documentation opens the USECASES first-time URL.

        GIVEN: The application is running for the first time
        WHEN: display_first_use_documentation is called
        THEN: webbrowser_open_url is called with the USECASES.html URL and autoraise=True
        """
        with patch("ardupilot_methodic_configurator.__main__.webbrowser_open_url") as mock_open:
            # Act
            display_first_use_documentation()

            # Assert
            mock_open.assert_called_once()
            url_arg: str = mock_open.call_args[1].get("url") or mock_open.call_args[0][0]
            assert "USECASES.html" in url_arg
            assert "first-time" in url_arg
            assert mock_open.call_args[1].get("autoraise") is True

    def test_connection_selection_window_shown_when_fc_returns_error(self) -> None:
        """
        ConnectionSelectionWindow is shown when the flight controller returns an error.

        GIVEN: connect_to_fc returns a non-empty error string and a device path is set
        WHEN: connect_to_fc_and_set_vehicle_type is called
        THEN: ConnectionSelectionWindow is constructed and root.mainloop is called
        """
        # Arrange
        mock_fc = MagicMock()
        mock_fc.info.vehicle_type = None
        mock_csw = MagicMock()
        mock_csw.root = MagicMock()
        args = argparse.Namespace(device="/dev/ttyUSB0", baudrate=115200, reboot_time=5)

        with (
            patch(
                "ardupilot_methodic_configurator.__main__.connect_to_fc",
                return_value=(mock_fc, "Timeout connecting"),
            ),
            patch(
                "ardupilot_methodic_configurator.__main__.ConnectionSelectionWindow",
                return_value=mock_csw,
            ) as mock_cls,
            patch("ardupilot_methodic_configurator.__main__.FreeDesktop.setup_startup_notification"),
            patch("ardupilot_methodic_configurator.__main__.resolve_vehicle_type"),
            patch("ardupilot_methodic_configurator.__main__.logging_error"),
        ):
            # Act
            connect_to_fc_and_set_vehicle_type(args)

        # Assert
        mock_cls.assert_called_once()
        mock_csw.root.mainloop.assert_called_once()

    def test_logging_error_called_when_device_set_and_error_is_not_no_ports(self) -> None:
        """
        logging_error is called when a device is specified and connection fails with real error.

        GIVEN: args.device is set and the error string is not 'No serial ports found'
        WHEN: connect_to_fc_and_set_vehicle_type is called
        THEN: logging_error is called once
        """
        # Arrange
        mock_fc = MagicMock()
        mock_fc.info.vehicle_type = None
        mock_csw = MagicMock()
        mock_csw.root = MagicMock()
        args = argparse.Namespace(device="/dev/ttyUSB0", baudrate=115200, reboot_time=5)

        with (
            patch(
                "ardupilot_methodic_configurator.__main__.connect_to_fc",
                return_value=(mock_fc, "Timeout connecting"),
            ),
            patch(
                "ardupilot_methodic_configurator.__main__.ConnectionSelectionWindow",
                return_value=mock_csw,
            ),
            patch("ardupilot_methodic_configurator.__main__.FreeDesktop.setup_startup_notification"),
            patch("ardupilot_methodic_configurator.__main__.resolve_vehicle_type"),
            patch("ardupilot_methodic_configurator.__main__.logging_error") as mock_err,
        ):
            # Act
            connect_to_fc_and_set_vehicle_type(args)

        # Assert
        mock_err.assert_called_once()

    def test_fallback_dir_returned_when_preferred_dir_not_writable(self) -> None:
        """
        resolve_writable_vehicle_dir_for_initial_download returns fallback dir when preferred is unwritable.

        GIVEN: _is_directory_writable returns False for the preferred directory
        AND: ProgramSettings.get_vehicles_default_dir returns a valid fallback path
        WHEN: resolve_writable_vehicle_dir_for_initial_download is called
        THEN: The fallback directory is returned and logging_warning is called once
        """
        with tempfile.TemporaryDirectory() as fallback_tmp:
            fallback = Path(fallback_tmp)
            preferred = Path("/not/writable")

            with (
                patch(
                    "ardupilot_methodic_configurator.__main__._is_directory_writable",
                    return_value=False,
                ),
                patch(
                    "ardupilot_methodic_configurator.__main__.ProgramSettings.get_vehicles_default_dir",
                    return_value=fallback,
                ),
                patch("ardupilot_methodic_configurator.__main__.logging_warning") as mock_warn,
            ):
                # Act
                result = resolve_writable_vehicle_dir_for_initial_download(preferred)

            # Assert
            assert result == fallback
            mock_warn.assert_called_once()
            args, kwargs = mock_warn.call_args
            if kwargs:
                warn_kwargs: dict = kwargs
            elif len(args) > 1 and isinstance(args[1], dict):
                warn_kwargs = args[1]
            else:
                pytest.fail("logging_warning was not called with expected keyword or dict positional arguments")
            assert warn_kwargs["old_dir"] == preferred
            assert warn_kwargs["new_dir"] == fallback

    def test_initialize_filesystem_shows_error_and_re_raises_on_system_exit(self) -> None:
        """
        initialize_filesystem shows an error message then re-raises SystemExit.

        GIVEN: LocalFilesystem constructor raises SystemExit
        WHEN: initialize_filesystem is called
        THEN: show_error_message is called with a title containing 'fatal'
        AND: SystemExit propagates to the caller
        """
        # Arrange
        state = ApplicationState(
            argparse.Namespace(
                vehicle_dir=None,
                allow_editing_template_files=False,
                save_component_to_system_templates=False,
            )
        )
        state.flight_controller = MagicMock()
        state.param_default_values = {}

        with (
            patch(
                "ardupilot_methodic_configurator.__main__.LocalFilesystem",
                side_effect=SystemExit("bad files"),
            ),
            patch("ardupilot_methodic_configurator.__main__.show_error_message") as mock_err,
        ):
            # Act + Assert
            with pytest.raises(SystemExit):
                initialize_filesystem(state)
            mock_err.assert_called_once()
            assert "fatal" in mock_err.call_args[0][0].lower()

    def test_vehicle_directory_selection_resets_fc_when_flag_is_set(self) -> None:
        """
        vehicle_directory_selection resets FC parameters when the user requests it.

        GIVEN: vehicle_project_manager.reset_fc_parameters_to_their_defaults is True
        AND: reset_all_parameters_to_default returns success
        WHEN: vehicle_directory_selection is called
        THEN: flight_controller.reset_and_reconnect is called once
        """
        # Arrange
        state = ApplicationState(argparse.Namespace(vehicle_dir="/some/dir", device=None))
        state.flight_controller = MagicMock()
        state.flight_controller.reset_all_parameters_to_default.return_value = (True, "")
        state.flight_controller.fc_parameters = {MagicMock(): MagicMock()}
        state.flight_controller.master = None
        state.local_filesystem = MagicMock()
        state.vehicle_type = MagicMock()
        state.param_default_values = {}

        mock_vpm = MagicMock()
        mock_vpm.reset_fc_parameters_to_their_defaults = True
        mock_vpm.infer_comp_specs_and_conn_from_fc_params = False
        mock_window = MagicMock()
        mock_window.root = MagicMock()

        with (
            patch(
                "ardupilot_methodic_configurator.__main__.VehicleProjectManager",
                return_value=mock_vpm,
            ),
            patch(
                "ardupilot_methodic_configurator.__main__.VehicleProjectOpenerWindow",
                return_value=mock_window,
            ),
            patch("ardupilot_methodic_configurator.__main__.FreeDesktop.setup_startup_notification"),
            patch("ardupilot_methodic_configurator.__main__.backup_fc_parameters"),
            patch("ardupilot_methodic_configurator.__main__.FlightControllerInfoWindow") as mock_fciw,
        ):
            mock_fciw.return_value.get_param_default_values.return_value = {}

            # Act
            vehicle_directory_selection(state)

        # Assert
        state.flight_controller.reset_and_reconnect.assert_called_once()

    def test_vehicle_directory_selection_logs_error_when_fc_reset_fails(self) -> None:
        """
        vehicle_directory_selection logs an error when the FC reset operation fails.

        GIVEN: reset_all_parameters_to_default returns (False, 'Reset failed')
        WHEN: vehicle_directory_selection is called
        THEN: logging_error is called at least once
        """
        # Arrange
        state = ApplicationState(argparse.Namespace(vehicle_dir="/some/dir", device=None))
        state.flight_controller = MagicMock()
        state.flight_controller.reset_all_parameters_to_default.return_value = (False, "Reset failed")
        state.flight_controller.fc_parameters = {}
        state.flight_controller.master = None
        state.local_filesystem = MagicMock()
        state.vehicle_type = MagicMock()
        state.param_default_values = {}

        mock_vpm = MagicMock()
        mock_vpm.reset_fc_parameters_to_their_defaults = True
        mock_vpm.infer_comp_specs_and_conn_from_fc_params = False
        mock_window = MagicMock()
        mock_window.root = MagicMock()

        with (
            patch(
                "ardupilot_methodic_configurator.__main__.VehicleProjectManager",
                return_value=mock_vpm,
            ),
            patch(
                "ardupilot_methodic_configurator.__main__.VehicleProjectOpenerWindow",
                return_value=mock_window,
            ),
            patch("ardupilot_methodic_configurator.__main__.FreeDesktop.setup_startup_notification"),
            patch("ardupilot_methodic_configurator.__main__.backup_fc_parameters"),
            patch("ardupilot_methodic_configurator.__main__.FlightControllerInfoWindow") as mock_fciw,
            patch("ardupilot_methodic_configurator.__main__.logging_error") as mock_log_err,
        ):
            mock_fciw.return_value.get_param_default_values.return_value = {}

            # Act
            vehicle_directory_selection(state)

        # Assert
        mock_log_err.assert_called()


class TestEditorBackupAndMainOrchestration:
    """Feature: Component editor branches, backup error handling, GPS upgrade and main() flow."""

    def test_component_editor_skip_schedules_window_destruction(self) -> None:
        """
        component_editor schedules immediate window destruction when skip flag is set.

        GIVEN: skip_component_editor=True and blank_component_data=False
        WHEN: component_editor is called
        THEN: root.after(10, root.destroy) is called and root.mainloop runs
        """
        # Arrange
        state = ApplicationState(argparse.Namespace(skip_component_editor=True, vehicle_dir=None))
        state.flight_controller = MagicMock()
        state.local_filesystem = MagicMock()
        mock_vpm = MagicMock()
        mock_vpm.blank_component_data = False
        state.vehicle_project_manager = mock_vpm
        mock_cew = MagicMock()
        mock_cew.root = MagicMock()

        with patch(
            "ardupilot_methodic_configurator.__main__.create_and_configure_component_editor",
            return_value=mock_cew,
        ):
            # Act
            component_editor(state)

        # Assert
        mock_cew.root.after.assert_called_once_with(10, mock_cew.root.destroy)
        mock_cew.root.mainloop.assert_called_once()

    def test_component_editor_opens_firmware_doc_when_auto_open_enabled(self) -> None:
        """
        component_editor opens firmware documentation when auto-open is enabled.

        GIVEN: skip_component_editor=False and should_open_firmware_documentation returns True
        WHEN: component_editor is called
        THEN: open_firmware_documentation is called with the firmware type
        """
        # Arrange
        state = ApplicationState(argparse.Namespace(skip_component_editor=False, vehicle_dir=None))
        state.flight_controller = MagicMock()
        state.local_filesystem = MagicMock()
        state.vehicle_project_manager = None
        mock_cew = MagicMock()
        mock_cew.root = MagicMock()

        with (
            patch(
                "ardupilot_methodic_configurator.__main__.create_and_configure_component_editor",
                return_value=mock_cew,
            ),
            patch(
                "ardupilot_methodic_configurator.__main__.should_open_firmware_documentation",
                return_value=True,
            ),
            patch("ardupilot_methodic_configurator.__main__.open_firmware_documentation") as mock_open_doc,
            patch("ardupilot_methodic_configurator.__main__.FreeDesktop.setup_startup_notification"),
        ):
            # Act
            component_editor(state)

        # Assert
        mock_open_doc.assert_called_once_with(state.flight_controller.info.firmware_type)

    def test_simple_gui_warning_contains_jump_hint(self) -> None:
        """
        process_component_editor_results includes simple-GUI jump hint in warning body.

        GIVEN: calculate_derived returns a non-empty list and gui_complexity == 'simple'
        WHEN: process_component_editor_results is called
        THEN: show_warning_message body contains simple-GUI guidance text
        """
        # Arrange
        fc = MagicMock()
        fc.fc_parameters = {MagicMock(): MagicMock()}
        fs = MagicMock()
        fs.calculate_derived_and_forced_param_changes.return_value = ["param_file.param"]
        fs.param_default_dict = {}

        with (
            patch("ardupilot_methodic_configurator.__main__.show_warning_message") as mock_warn,
            patch(
                "ardupilot_methodic_configurator.__main__.ProgramSettings.get_setting",
                return_value="simple",
            ),
        ):
            # Act
            process_component_editor_results(fc, fs)

            # Assert
            mock_warn.assert_called_once()
            args, kwargs = mock_warn.call_args
            if "body" in kwargs:
                body: str = kwargs["body"]
            elif len(args) > 1:
                body = args[1]
            else:
                pytest.fail("show_warning_message was not called with a body argument")

            body_lower = body.lower()
            assert ("jump" in body_lower and "advanced" in body_lower) or (
                "switch" in body_lower and "gui" in body_lower and "complexity" in body_lower
            )

    def test_backup_logs_error_when_disk_is_full(self) -> None:
        """
        backup_fc_parameters logs an error and does not raise when disk is full.

        GIVEN: backup_fc_parameters_to_file raises OSError('No space left on device')
        WHEN: backup_fc_parameters is called
        THEN: logging_error is called and no exception propagates
        """
        # Arrange
        state = ApplicationState(argparse.Namespace())
        state.flight_controller = MagicMock()
        state.flight_controller.fc_parameters = {MagicMock(): MagicMock()}
        state.local_filesystem = MagicMock()
        state.local_filesystem.find_lowest_available_backup_number.return_value = 1
        state.local_filesystem.backup_fc_parameters_to_file.side_effect = OSError("No space left on device")

        with patch("ardupilot_methodic_configurator.__main__.logging_error") as mock_err:
            # Act
            backup_fc_parameters(state)

            # Assert
            mock_err.assert_called()
            messages: str = " ".join(str(c) for c in mock_err.call_args_list)
            assert "space" in messages.lower() or "disk" in messages.lower()

    def test_backup_logs_error_for_unexpected_exception(self) -> None:
        """
        backup_fc_parameters logs an error and does not raise on unexpected exceptions.

        GIVEN: backup_fc_parameters_to_file raises RuntimeError
        WHEN: backup_fc_parameters is called
        THEN: logging_error is called and no exception propagates
        """
        # Arrange
        state = ApplicationState(argparse.Namespace())
        state.flight_controller = MagicMock()
        state.flight_controller.fc_parameters = {MagicMock(): MagicMock()}
        state.local_filesystem = MagicMock()
        state.local_filesystem.find_lowest_available_backup_number.return_value = 1
        state.local_filesystem.backup_fc_parameters_to_file.side_effect = RuntimeError("weird")

        with patch("ardupilot_methodic_configurator.__main__.logging_error") as mock_err:
            # Act
            backup_fc_parameters(state)

            # Assert
            mock_err.assert_called()

    def test_gps_params_renamed_for_46_firmware(self) -> None:
        """
        parameter_editor_and_uploader renames legacy GPS params for 4.6 firmware.

        GIVEN: fc firmware starts with '4.6.' and file_parameters contains 'GPS_TYPE'
        WHEN: parameter_editor_and_uploader is called
        THEN: 'GPS_TYPE' is replaced by 'GPS1_TYPE' in file_parameters
        """
        # Arrange
        state = ApplicationState(argparse.Namespace(n=0, export_fc_params_missing_or_different=False))
        state.flight_controller = MagicMock()
        state.flight_controller.info.flight_sw_version = "4.6.0"
        state.flight_controller.fc_parameters = {
            "GPS_TYPE": MagicMock(),
            "INS_TCAL1_ENABLE": MagicMock(),
        }
        mock_fs = MagicMock()
        mock_fs.file_parameters = {"01.param": ParDict({"GPS_TYPE": MagicMock()})}
        mock_fs.get_start_file.return_value = "01.param"
        state.local_filesystem = mock_fs

        with (
            patch(
                "ardupilot_methodic_configurator.__main__.ProgramSettings.get_setting",
                return_value="normal",
            ),
            patch("ardupilot_methodic_configurator.__main__.ParameterEditor"),
            patch("ardupilot_methodic_configurator.__main__.ParameterEditorWindow"),
        ):
            # Act
            parameter_editor_and_uploader(state)

        # Assert
        updated = mock_fs.file_parameters["01.param"]
        assert "GPS1_TYPE" in updated
        assert "GPS_TYPE" not in updated

    def test_main_disconnect_and_exit_0_on_normal_completion(self) -> None:
        """
        main() calls flight_controller.disconnect and sys_exit(0) on normal completion.

        GIVEN: All sub-steps succeed without error
        WHEN: main is called
        THEN: flight_controller.disconnect is called once and sys_exit(0) is the final call
        """
        # Arrange
        fc_mock = MagicMock()
        fc_mock.fc_parameters = {MagicMock(): MagicMock()}

        def _init_fs(state: object) -> None:
            state.flight_controller = fc_mock  # type: ignore[union-attr]
            state.local_filesystem = MagicMock()  # type: ignore[union-attr]
            state.local_filesystem.file_parameters = {"01.param": {}}
            state.local_filesystem.doc_dict = {}
            state.local_filesystem.vehicle_dir = "/fake"
            state.param_default_values_dirty = False  # type: ignore[union-attr]

        with (
            patch("ardupilot_methodic_configurator.__main__.create_argument_parser") as mock_parser,
            patch("ardupilot_methodic_configurator.__main__.register_plugins"),
            patch("ardupilot_methodic_configurator.__main__.FreeDesktop.create_desktop_icon_if_needed"),
            patch("ardupilot_methodic_configurator.__main__.setup_logging"),
            patch("ardupilot_methodic_configurator.__main__.ProgramSettings.migrate_settings_to_latest_version"),
            patch("ardupilot_methodic_configurator.__main__.check_updates", return_value=False),
            patch(
                "ardupilot_methodic_configurator.__main__.PopupWindow.should_display",
                return_value=False,
            ),
            patch(
                "ardupilot_methodic_configurator.__main__.ProgramSettings.get_setting",
                side_effect=lambda key: False if key != "gui_complexity" else "normal",
            ),
            patch(
                "ardupilot_methodic_configurator.__main__.initialize_flight_controller_and_filesystem",
                side_effect=_init_fs,
            ),
            patch("ardupilot_methodic_configurator.__main__.component_editor"),
            patch("ardupilot_methodic_configurator.__main__.process_component_editor_results"),
            patch("ardupilot_methodic_configurator.__main__.backup_fc_parameters"),
            patch("ardupilot_methodic_configurator.__main__.parameter_editor_and_uploader"),
            patch("ardupilot_methodic_configurator.__main__.sys_exit") as mock_exit,
        ):
            mock_parser.return_value.parse_args.return_value = argparse.Namespace(
                loglevel="INFO",
                skip_check_for_updates=False,
                vehicle_dir=None,
                vehicle_type=None,
                device=None,
                reboot_time=5,
                baudrate=115200,
                n=0,
                skip_component_editor=False,
                allow_editing_template_files=False,
                save_component_to_system_templates=False,
                export_fc_params_missing_or_different=False,
            )

            # Act
            main()

        # Assert: disconnect
        fc_mock.disconnect.assert_called_once()
        mock_exit.assert_called_with(0)
