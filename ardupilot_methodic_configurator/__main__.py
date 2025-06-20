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


def component_editor(
    args: argparse.Namespace,
    flight_controller: FlightController,
    vehicle_type: str,
    local_filesystem: LocalFilesystem,
    vehicle_dir_window: Union[None, VehicleDirectorySelectionWindow],
) -> None:
    component_editor_window = ComponentEditorWindow(__version__, local_filesystem)
    if (
        vehicle_dir_window
        and vehicle_dir_window.configuration_template
        and vehicle_dir_window.infer_comp_specs_and_conn_from_fc_params.get()
        and flight_controller.fc_parameters
    ):
        # Infer vehicle component specifications and connections from FC parameters
        component_editor_window.set_values_from_fc_parameters(flight_controller.fc_parameters, local_filesystem.doc_dict)
    component_editor_window.populate_frames()
    component_editor_window.set_vehicle_type_and_version(vehicle_type, flight_controller.info.flight_sw_version_and_type)
    component_editor_window.set_fc_manufacturer(flight_controller.info.vendor)
    component_editor_window.set_fc_model(flight_controller.info.firmware_type)
    component_editor_window.set_mcu_series(flight_controller.info.mcu_series)
    if vehicle_dir_window and vehicle_dir_window.configuration_template:
        component_editor_window.set_vehicle_configuration_template(vehicle_dir_window.configuration_template)
    if args.skip_component_editor:
        component_editor_window.root.after(10, component_editor_window.root.destroy)
    elif (
        bool(ProgramSettings.get_setting("auto_open_doc_in_browser"))
        and flight_controller.info.firmware_type != _("Unknown")
        and flight_controller.info.firmware_type != ""
    ):
        firmware_type = flight_controller.info.firmware_type
        url = f"https://github.com/ArduPilot/ardupilot/blob/master/libraries/AP_HAL_ChibiOS/hwdef/{firmware_type}/README.md"
        url_found = verify_and_open_url(url)
        if not url_found and firmware_type.endswith("-bdshot"):
            firmware_type = firmware_type[:-7]
            url = (
                f"https://github.com/ArduPilot/ardupilot/blob/master/libraries/AP_HAL_ChibiOS/hwdef/{firmware_type}/README.md"
            )
            url_found = verify_and_open_url(url)

    component_editor_window.root.mainloop()

    source_param_values: Union[dict[str, float], None] = (
        flight_controller.fc_parameters
        if vehicle_dir_window and vehicle_dir_window.configuration_template and vehicle_dir_window.use_fc_params.get()
        else None
    )
    existing_fc_params: list[str] = (
        list(flight_controller.fc_parameters.keys())
        if flight_controller.fc_parameters
        else list(local_filesystem.param_default_dict.keys())
        if local_filesystem.param_default_dict
        else []
    )
    # if source_param_values is None, the template parameter values are used
    # if source_param_values contains the connected FC parameters, then they are used
    error_message = local_filesystem.update_and_export_vehicle_params_from_fc(
        source_param_values=source_param_values, existing_fc_params=existing_fc_params
    )
    if error_message:
        logging_error(error_message)
        show_error_message(_("Error in derived parameters"), error_message)
        sys_exit(1)


def main() -> None:
    args = create_argument_parser().parse_args()

    logging_basicConfig(level=logging_getLevelName(args.loglevel), format="%(asctime)s - %(levelname)s - %(message)s")

    if not args.skip_check_for_updates and check_for_software_updates():
        logging_info(_("Will now exit the old software version."))
        sys_exit(0)

    if bool(ProgramSettings.get_setting("auto_open_doc_in_browser")):
        url = (
            "https://ardupilot.github.io/MethodicConfigurator/USECASES.html"
            "#use-the-ardupilot-methodic-configurator-software-for-the-first-time"
        )
        webbrowser_open(url=url, new=0, autoraise=True)

    # Connect to the flight controller and read the parameters
    flight_controller, vehicle_type = connect_to_fc_and_set_vehicle_type(args)

    param_default_values = {}
    if flight_controller.master is not None or args.device == "test":
        fciw = FlightControllerInfoWindow(flight_controller)
        param_default_values = fciw.get_param_default_values()

    try:
        local_filesystem = LocalFilesystem(
            args.vehicle_dir,
            vehicle_type,
            flight_controller.info.flight_sw_version,
            args.allow_editing_template_files,
            args.save_component_to_system_templates,
        )
    except SystemExit as exp:
        show_error_message(_("Fatal error reading parameter files"), f"{exp}")
        raise

    param_default_values_dirty = False
    if param_default_values:
        param_default_values_dirty = local_filesystem.write_param_default_values(param_default_values)

    # Get the list of intermediate parameter files files that will be processed sequentially
    files = list(local_filesystem.file_parameters.keys()) if local_filesystem.file_parameters else []

    vehicle_dir_window = None
    if not files:
        vehicle_dir_window = VehicleDirectorySelectionWindow(local_filesystem, len(flight_controller.fc_parameters) > 0)
        vehicle_dir_window.root.mainloop()

    component_editor(args, flight_controller, local_filesystem.vehicle_type, local_filesystem, vehicle_dir_window)

    # now that we are sure that the vehicle directory is set, we can write the default values to the file
    if param_default_values_dirty:
        local_filesystem.write_param_default_values_to_file(param_default_values)

    imu_tcal_available = "INS_TCAL1_ENABLE" in flight_controller.fc_parameters or not flight_controller.fc_parameters
    simple_gui: bool = ProgramSettings.get_setting("gui_complexity") == "simple"
    start_file = local_filesystem.get_start_file(args.n, imu_tcal_available and not simple_gui)

    if flight_controller.fc_parameters:
        local_filesystem.backup_fc_parameters_to_file(
            flight_controller.fc_parameters,
            "autobackup_00_before_ardupilot_methodic_configurator.param",
            overwrite_existing_file=False,
            even_if_last_uploaded_filename_exists=False,
        )
        # Create incremental backup file
        backup_num = local_filesystem.find_lowest_available_backup_number()
        local_filesystem.backup_fc_parameters_to_file(
            flight_controller.fc_parameters,
            f"autobackup_{backup_num:02d}.param",
            overwrite_existing_file=True,
            even_if_last_uploaded_filename_exists=True,
        )
        logging_info(_("Created backup file autobackup_%02d.param"), backup_num)

    # Call the GUI function with the starting intermediate parameter file
    ParameterEditorWindow(start_file, flight_controller, local_filesystem)

    # Close the connection to the flight controller
    flight_controller.disconnect()
    sys_exit(0)


if __name__ == "__main__":
    main()
