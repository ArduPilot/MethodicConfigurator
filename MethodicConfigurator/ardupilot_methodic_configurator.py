#!/usr/bin/env python3

'''
This file is part of Ardupilot methodic configurator. https://github.com/ArduPilot/MethodicConfigurator

(C) 2024 Amilcar do Carmo Lucas

SPDX-License-Identifier:    GPL-3
'''

import argparse
from logging import basicConfig as logging_basicConfig
from logging import getLevelName as logging_getLevelName
from logging import debug as logging_debug
from logging import info as logging_info
from logging import warning as logging_warning
from logging import error as logging_error
from sys import exit as sys_exit

from MethodicConfigurator.backend_filesystem import LocalFilesystem
from MethodicConfigurator.backend_flightcontroller import FlightController

from MethodicConfigurator.frontend_tkinter_base import show_error_message

from MethodicConfigurator.frontend_tkinter_connection_selection import ConnectionSelectionWindow

from MethodicConfigurator.frontend_tkinter_flightcontroller_info import FlightControllerInfoWindow

from MethodicConfigurator.frontend_tkinter_directory_selection import VehicleDirectorySelectionWindow

from MethodicConfigurator.frontend_tkinter_component_editor import ComponentEditorWindow

from MethodicConfigurator.frontend_tkinter_parameter_editor import ParameterEditorWindow

from MethodicConfigurator.common_arguments import add_common_arguments_and_parse

from MethodicConfigurator.version import VERSION


def argument_parser():
    """
    Parses command-line arguments for the script.

    This function sets up an argument parser to handle the command-line arguments for the script.

    Returns:
    argparse.Namespace: An object containing the parsed arguments.
    """
    parser = argparse.ArgumentParser(description='ArduPilot methodic configurator is a simple GUI with a table that lists '
                                     'parameters. The GUI reads intermediate parameter files from a directory and '
                                     'displays their parameters in a table. Each row displays the parameter name, '
                                     'its current value on the flight controller, its new value from the selected '
                                     'intermediate parameter file, and an "Upload" checkbox. The GUI includes "Upload '
                                     'selected params to FC" and "Skip" buttons at the bottom. '
                                     'When "Upload Selected to FC" is clicked, it uploads the selected parameters to the '
                                     'flight controller. '
                                     'When "Skip" is pressed, it skips to the next intermediate parameter file. '
                                     'The process gets repeated for each intermediate parameter file.')
    parser = FlightController.add_argparse_arguments(parser)
    parser = LocalFilesystem.add_argparse_arguments(parser)
    parser = ComponentEditorWindow.add_argparse_arguments(parser)
    return add_common_arguments_and_parse(parser)


def connect_to_fc_and_read_parameters(args):
    flight_controller = FlightController(args.reboot_time)

    error_str = flight_controller.connect(args.device)
    if error_str:
        if "No serial ports found" not in error_str:
            logging_error(error_str)
        conn_sel_window = ConnectionSelectionWindow(flight_controller, error_str)
        conn_sel_window.root.mainloop()

    vehicle_type = args.vehicle_type
    if vehicle_type == "":  # not explicitly set, to try to guess it
        if flight_controller.info.vehicle_type is not None:
            vehicle_type = flight_controller.info.vehicle_type
            logging_debug("Vehicle type not set explicitly, auto-detected %s.", vehicle_type)
    else:
        logging_info("Vehicle type explicitly set to %s.", vehicle_type)

    if vehicle_type == "": # did not guess it, default to ArduCopter
        vehicle_type = "ArduCopter"
        logging_warning("Could not detect vehicle type. Defaulting to ArduCopter.")
    return flight_controller,vehicle_type


def component_editor(args, flight_controller, vehicle_type, local_filesystem, vehicle_dir_window):
    component_editor_window = ComponentEditorWindow(VERSION, local_filesystem)
    component_editor_window.set_vehicle_type_and_version(vehicle_type, flight_controller.info.flight_sw_version_and_type)
    component_editor_window.set_fc_manufacturer(flight_controller.info.vendor)
    component_editor_window.set_fc_model(flight_controller.info.product)
    if vehicle_dir_window and \
       vehicle_dir_window.created_new_vehicle_from_template and \
       flight_controller.fc_parameters:
        # copy vehicle parameters to component editor values
        component_editor_window.set_values_from_fc_parameters(flight_controller.fc_parameters, local_filesystem.doc_dict)
    if args.skip_component_editor:
        component_editor_window.root.after(10, component_editor_window.root.destroy)
    component_editor_window.root.mainloop()

    if vehicle_dir_window and \
       vehicle_dir_window.created_new_vehicle_from_template and \
       vehicle_dir_window.use_fc_params.get():
        error_message = local_filesystem.copy_fc_params_values_to_template_created_vehicle_files(
            flight_controller.fc_parameters)
        if error_message:
            logging_error(error_message)
            show_error_message("Error in derived parameters", error_message)
            sys_exit(1)


def main():
    args = argument_parser()

    logging_basicConfig(level=logging_getLevelName(args.loglevel), format='%(asctime)s - %(levelname)s - %(message)s')

    # Connect to the flight controller and read the parameters
    flight_controller, vehicle_type = connect_to_fc_and_read_parameters(args)

    if flight_controller.master is not None or args.device == 'test':
        FlightControllerInfoWindow(flight_controller)

    try:
        local_filesystem = LocalFilesystem(args.vehicle_dir, vehicle_type, args.allow_editing_template_files)
    except SystemExit as exp:
        show_error_message("Fatal error reading parameter files", f"{exp}")
        raise

    # Get the list of intermediate parameter files files that will be processed sequentially
    files = list(local_filesystem.file_parameters.keys())

    vehicle_dir_window = None
    if not files:
        vehicle_dir_window = VehicleDirectorySelectionWindow(local_filesystem, len(flight_controller.fc_parameters) > 0)
        vehicle_dir_window.root.mainloop()

    start_file = local_filesystem.get_start_file(args.n)

    component_editor(args, flight_controller, vehicle_type, local_filesystem, vehicle_dir_window)

    # Call the GUI function with the starting intermediate parameter file
    ParameterEditorWindow(start_file, flight_controller, local_filesystem, VERSION)

    # Close the connection to the flight controller
    flight_controller.disconnect()
    sys_exit(0)


if __name__ == "__main__":
    main()
