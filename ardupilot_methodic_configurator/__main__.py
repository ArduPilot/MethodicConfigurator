#!/usr/bin/env python3
# PYTHON_ARGCOMPLETE_OK

"""
The main application file.

Calls five sub-applications in sequence:
  1. Check for software updates
  2. Connect to the flight controller and read the parameters
  3. Select the vehicle directory
  4. Component and connection editor
  5. Parameter editor and uploader

This file is part of Ardupilot methodic configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2025 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import argparse
from logging import basicConfig as logging_basicConfig
from logging import debug as logging_debug
from logging import error as logging_error
from logging import getLevelName as logging_getLevelName
from logging import info as logging_info
from sys import exit as sys_exit
from typing import Union
from webbrowser import open as webbrowser_open

import argcomplete

from ardupilot_methodic_configurator import _, __version__
from ardupilot_methodic_configurator.backend_filesystem import LocalFilesystem
from ardupilot_methodic_configurator.backend_filesystem_program_settings import ProgramSettings
from ardupilot_methodic_configurator.backend_flightcontroller import FlightController
from ardupilot_methodic_configurator.backend_internet import verify_and_open_url
from ardupilot_methodic_configurator.common_arguments import add_common_arguments
from ardupilot_methodic_configurator.frontend_tkinter_component_editor import ComponentEditorWindow
from ardupilot_methodic_configurator.frontend_tkinter_connection_selection import ConnectionSelectionWindow
from ardupilot_methodic_configurator.frontend_tkinter_directory_selection import VehicleDirectorySelectionWindow
from ardupilot_methodic_configurator.frontend_tkinter_flightcontroller_info import FlightControllerInfoWindow
from ardupilot_methodic_configurator.frontend_tkinter_parameter_editor import ParameterEditorWindow
from ardupilot_methodic_configurator.frontend_tkinter_show import show_error_message
from ardupilot_methodic_configurator.middleware_software_updates import UpdateManager, check_for_software_updates


class ApplicationState:  # pylint: disable=too-few-public-methods
    """Data class to hold application state throughout the startup process."""

    def __init__(self, args: argparse.Namespace) -> None:
        self.args = args
        self.flight_controller: FlightController = None  # type: ignore[assignment]
        self.vehicle_type: str = ""
        self.param_default_values: dict = {}
        self.local_filesystem: LocalFilesystem = None  # type: ignore[assignment]
        self.vehicle_dir_window: Union[VehicleDirectorySelectionWindow, None] = None
        self.param_default_values_dirty: bool = False


def create_argument_parser() -> argparse.ArgumentParser:
    """
    Argument parser to handle the command-line arguments for the script.

    Returns:
        argparse.ArgumentParser: The argument parser object.

    """
    parser = argparse.ArgumentParser(
        description=_(
            "ArduPilot methodic configurator is a simple GUI with a table that lists "
            "parameters. The GUI reads intermediate parameter files from a directory and "
            "displays their parameters in a table. Each row displays the parameter name, "
            "its current value on the flight controller, its new value from the selected "
            'intermediate parameter file, and an "Upload" checkbox. The GUI includes "Upload '
            'selected params to FC" and "Skip" buttons at the bottom. '
            'When "Upload Selected to FC" is clicked, it uploads the selected parameters to the '
            "flight controller. "
            'When "Skip" is pressed, it skips to the next intermediate parameter file. '
            "The process gets repeated for each intermediate parameter file."
        )
    )
    parser = UpdateManager.add_argparse_arguments(parser)
    parser = FlightController.add_argparse_arguments(parser)
    parser = LocalFilesystem.add_argparse_arguments(parser)
    parser = ComponentEditorWindow.add_argparse_arguments(parser)
    parser = ParameterEditorWindow.add_argparse_arguments(parser)
    parser = add_common_arguments(parser)

    argcomplete.autocomplete(parser)
    return parser


def setup_logging(state: ApplicationState) -> None:
    """
    Set up logging.

    Args:
        state: Application state containing parsed arguments

    """
    logging_basicConfig(level=logging_getLevelName(state.args.loglevel), format="%(asctime)s - %(levelname)s - %(message)s")


def check_updates(state: ApplicationState) -> bool:
    """
    Check for software updates.

    Args:
        state: Application state containing parsed arguments

    Returns:
        True if the application should exit due to updates, False otherwise

    """
    if not state.args.skip_check_for_updates and check_for_software_updates():
        logging_info(_("Will now exit the old software version."))
        return True
    return False


def display_first_use_documentation() -> None:
    """Open documentation in browser if enabled in settings."""
    if bool(ProgramSettings.get_setting("auto_open_doc_in_browser")):
        url = (
            "https://ardupilot.github.io/MethodicConfigurator/USECASES.html"
            "#use-the-ardupilot-methodic-configurator-software-for-the-first-time"
        )
        webbrowser_open(url=url, new=0, autoraise=True)


def connect_to_fc_and_set_vehicle_type(args: argparse.Namespace) -> tuple[FlightController, str]:
    flight_controller = FlightController(reboot_time=args.reboot_time, baudrate=args.baudrate)

    error_str = flight_controller.connect(args.device, log_errors=False)
    if error_str:
        if args.device and _("No serial ports found") not in error_str:
            logging_error(error_str)
        conn_sel_window = ConnectionSelectionWindow(flight_controller, error_str)
        conn_sel_window.root.mainloop()

    vehicle_type = args.vehicle_type
    if vehicle_type == "":  # not explicitly set, to try to guess it
        if flight_controller.info.vehicle_type is not None:
            vehicle_type = flight_controller.info.vehicle_type
            logging_debug(_("Vehicle type not set explicitly, auto-detected %s."), vehicle_type)
    else:
        logging_info(_("Vehicle type explicitly set to %s."), vehicle_type)

    return flight_controller, vehicle_type


def initialize_flight_controller_and_filesystem(state: ApplicationState) -> None:
    """
    Initialize flight controller connection and local filesystem.

    Args:
        state: Application state to populate with initialized objects

    Raises:
        SystemExit: If there's a fatal error reading parameter files

    """
    # Connect to the flight controller and read the parameters
    state.flight_controller, state.vehicle_type = connect_to_fc_and_set_vehicle_type(state.args)

    # Get default parameter values from flight controller
    if state.flight_controller.master is not None or state.args.device == "test":
        fciw = FlightControllerInfoWindow(state.flight_controller)
        state.param_default_values = fciw.get_param_default_values()

    # Initialize local filesystem
    try:
        state.local_filesystem = LocalFilesystem(
            state.args.vehicle_dir,
            state.vehicle_type,
            state.flight_controller.info.flight_sw_version,
            state.args.allow_editing_template_files,
            state.args.save_component_to_system_templates,
        )
    except SystemExit as exp:
        show_error_message(_("Fatal error reading parameter files"), f"{exp}")
        raise

    # Write parameter default values if available
    if state.param_default_values:
        state.param_default_values_dirty = state.local_filesystem.write_param_default_values(state.param_default_values)


def vehicle_directory_selection(state: ApplicationState) -> Union[VehicleDirectorySelectionWindow, None]:
    """
    Handle vehicle directory selection if no parameter files are found.

    Args:
        state: Application state containing filesystem and flight controller info

    Returns:
        VehicleDirectorySelectionWindow if selection was needed, None otherwise

    """
    # Get the list of intermediate parameter files that will be processed sequentially
    files = list(state.local_filesystem.file_parameters.keys()) if state.local_filesystem.file_parameters else []

    if not files:
        fc_connected = len(state.flight_controller.fc_parameters) > 0
        if not state.vehicle_type:
            logging_debug(
                _(
                    "Will present all vehicle templates for all vehicle types since no "
                    "FC connected and no explicit vehicle type set on the command line"
                )
            )
        state.vehicle_dir_window = VehicleDirectorySelectionWindow(state.local_filesystem, fc_connected, state.vehicle_type)
        state.vehicle_dir_window.root.mainloop()
        return state.vehicle_dir_window
    return None


def create_and_configure_component_editor(
    version: str,
    local_filesystem: LocalFilesystem,
    flight_controller: FlightController,
    vehicle_type: str,
    vehicle_dir_window: Union[None, VehicleDirectorySelectionWindow],
) -> ComponentEditorWindow:
    """
    Create and configure the component editor window.

    Args:
        version: Application version
        local_filesystem: Local filesystem instance
        flight_controller: Flight controller instance
        vehicle_type: Vehicle type string
        vehicle_dir_window: Vehicle directory selection window if any

    Returns:
        Configured ComponentEditorWindow instance

    """
    component_editor_window = ComponentEditorWindow(version, local_filesystem)

    # Infer component specifications from FC parameters if requested
    if (
        vehicle_dir_window
        and vehicle_dir_window.configuration_template
        and vehicle_dir_window.infer_comp_specs_and_conn_from_fc_params.get()
        and flight_controller.fc_parameters
    ):
        component_editor_window.set_values_from_fc_parameters(flight_controller.fc_parameters, local_filesystem.doc_dict)

    # Configure basic window properties
    component_editor_window.populate_frames()
    component_editor_window.set_vehicle_type_and_version(vehicle_type, flight_controller.info.flight_sw_version_and_type)
    component_editor_window.set_fc_manufacturer(flight_controller.info.vendor)
    component_editor_window.set_fc_model(flight_controller.info.firmware_type)
    component_editor_window.set_mcu_series(flight_controller.info.mcu_series)

    # Set configuration template if available
    if vehicle_dir_window and vehicle_dir_window.configuration_template:
        component_editor_window.set_vehicle_configuration_template(vehicle_dir_window.configuration_template)

    return component_editor_window


def should_open_firmware_documentation(flight_controller: FlightController) -> bool:
    """
    Determine if firmware documentation should be opened automatically.

    Args:
        flight_controller: Flight controller instance

    Returns:
        True if documentation should be opened, False otherwise

    """
    return (
        bool(ProgramSettings.get_setting("auto_open_doc_in_browser"))
        and flight_controller.info.firmware_type != _("Unknown")
        and flight_controller.info.firmware_type != ""
    )


def open_firmware_documentation(firmware_type: str) -> bool:
    """
    Open firmware-specific documentation in browser.

    Args:
        firmware_type: Firmware type identifier

    Returns:
        True if documentation was found and opened, False otherwise

    """
    url = f"https://github.com/ArduPilot/ardupilot/blob/master/libraries/AP_HAL_ChibiOS/hwdef/{firmware_type}/README.md"
    url_found = verify_and_open_url(url)

    if not url_found and firmware_type.endswith("-bdshot"):
        # Try without the bdshot suffix
        base_firmware_type = firmware_type[:-7]
        fallback_url = (
            f"https://github.com/ArduPilot/ardupilot/blob/master/libraries/AP_HAL_ChibiOS/hwdef/{base_firmware_type}/README.md"
        )
        url_found = verify_and_open_url(fallback_url)

    return url_found


def component_editor(state: ApplicationState) -> None:
    """
    Run the component editor workflow.

    Args:
        state: Application state containing all necessary objects

    Raises:
        SystemExit: If there's an error in derived parameters

    """
    # Create and configure the component editor window
    component_editor_window = create_and_configure_component_editor(
        __version__,
        state.local_filesystem,
        state.flight_controller,
        state.local_filesystem.vehicle_type,
        state.vehicle_dir_window,
    )

    # Handle skip component editor option
    should_skip_editor = state.args.skip_component_editor and not (
        state.vehicle_dir_window
        and state.vehicle_dir_window.configuration_template
        and state.vehicle_dir_window.blank_component_data.get()
    )
    if should_skip_editor:
        component_editor_window.root.after(10, component_editor_window.root.destroy)
    elif should_open_firmware_documentation(state.flight_controller):
        open_firmware_documentation(state.flight_controller.info.firmware_type)

    # Run the GUI
    component_editor_window.root.mainloop()


def process_component_editor_results(
    flight_controller: FlightController,
    local_filesystem: LocalFilesystem,
    vehicle_dir_window: Union[None, VehicleDirectorySelectionWindow],
) -> None:
    """
    Process the results after component editor completion.

    Args:
        flight_controller: Flight controller instance
        local_filesystem: Local filesystem instance
        vehicle_dir_window: Vehicle directory selection window if any

    Raises:
        SystemExit: If there's an error in derived parameters

    """
    # Determine parameter source
    source_param_values: Union[dict[str, float], None] = None
    if vehicle_dir_window and vehicle_dir_window.configuration_template and vehicle_dir_window.use_fc_params.get():
        source_param_values = flight_controller.fc_parameters

    # Get existing FC parameters for reference
    existing_fc_params: list[str] = []
    if flight_controller.fc_parameters:
        existing_fc_params = list(flight_controller.fc_parameters.keys())
    elif local_filesystem.param_default_dict:
        existing_fc_params = list(local_filesystem.param_default_dict.keys())

    # Update and export vehicle parameters
    error_message = local_filesystem.update_and_export_vehicle_params_from_fc(
        source_param_values=source_param_values, existing_fc_params=existing_fc_params
    )

    if error_message:
        logging_error(error_message)
        show_error_message(_("Error in derived parameters"), error_message)
        sys_exit(1)


def write_parameter_defaults_if_dirty(state: ApplicationState) -> None:
    """
    Write parameter default values to file if they have been modified.

    Args:
        state: Application state containing filesystem, parameters, and dirty flag

    """
    if state.param_default_values_dirty:
        state.local_filesystem.write_param_default_values_to_file(state.param_default_values)


def backup_fc_parameters(state: ApplicationState) -> None:
    """
    Create backup files of current flight controller parameters.

    Args:
        state: Application state containing flight controller and filesystem

    """
    if state.flight_controller.fc_parameters:
        try:
            # Create initial backup
            state.local_filesystem.backup_fc_parameters_to_file(
                state.flight_controller.fc_parameters,
                "autobackup_00_before_ardupilot_methodic_configurator.param",
                overwrite_existing_file=False,
                even_if_last_uploaded_filename_exists=False,
            )

            # Create incremental backup file
            backup_num = state.local_filesystem.find_lowest_available_backup_number()
            state.local_filesystem.backup_fc_parameters_to_file(
                state.flight_controller.fc_parameters,
                f"autobackup_{backup_num:02d}.param",
                overwrite_existing_file=True,
                even_if_last_uploaded_filename_exists=True,
            )
            logging_info(_("Created backup file autobackup_%02d.param"), backup_num)
        except PermissionError as e:
            logging_error(_("Permission denied when creating backup files: %s"), str(e))
            logging_error(_("Please check file permissions and ensure you have write access to the vehicle directory"))
        except OSError as e:
            if "No space left on device" in str(e) or "28" in str(e):
                logging_error(_("Insufficient disk space to create backup files: %s"), str(e))
                logging_error(_("Please free up disk space and try again"))
            else:
                logging_error(_("Failed to create backup files: %s"), str(e))
        except Exception as e:  # pylint: disable=broad-exception-caught
            logging_error(_("Unexpected error creating backup files: %s"), str(e))


def parameter_editor_and_uploader(state: ApplicationState) -> None:
    """
    Start the parameter editor with the appropriate starting file.

    Args:
        state: Application state containing all necessary objects

    """
    imu_tcal_available = (
        "INS_TCAL1_ENABLE" in state.flight_controller.fc_parameters or not state.flight_controller.fc_parameters
    )
    simple_gui: bool = ProgramSettings.get_setting("gui_complexity") == "simple"
    start_file = state.local_filesystem.get_start_file(state.args.n, imu_tcal_available and not simple_gui)

    # Call the GUI function with the starting intermediate parameter file
    ParameterEditorWindow(start_file, state.flight_controller, state.local_filesystem)


def main() -> None:
    """
    Main application entry point.

    Orchestrates the entire application startup process by calling specialized functions
    for each major step.
    """
    args = create_argument_parser().parse_args()

    state = ApplicationState(args)

    setup_logging(state)

    # Check for software updates
    if check_updates(state):
        sys_exit(0)  # user asked to update, exit the old version

    display_first_use_documentation()

    initialize_flight_controller_and_filesystem(state)

    # Handle vehicle directory selection if needed
    vehicle_directory_selection(state)

    # Run component editor workflow
    component_editor(state)

    # Process results after component editor GUI closes
    process_component_editor_results(state.flight_controller, state.local_filesystem, state.vehicle_dir_window)

    # Write parameter default values to file if dirty
    write_parameter_defaults_if_dirty(state)

    # Create parameter backups
    backup_fc_parameters(state)

    # Start parameter editor
    parameter_editor_and_uploader(state)

    # Clean up and exit
    state.flight_controller.disconnect()
    sys_exit(0)


if __name__ == "__main__":
    main()
