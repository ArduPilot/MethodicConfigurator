#!/usr/bin/env python3

'''
This file is part of Ardupilot methodic configurator. https://github.com/ArduPilot/MethodicConfigurator

(C) 2024 Amilcar do Carmo Lucas, IAV GmbH

SPDX-License-Identifier:    GPL-3
'''

import argparse
from logging import basicConfig as logging_basicConfig
from logging import getLevelName as logging_getLevelName
# from logging import debug as logging_debug
from logging import info as logging_info
from logging import warning as logging_warning
from logging import error as logging_error
from os import getcwd as os_getcwd
from sys import exit as sys_exit

from backend_filesystem import LocalFilesystem
from backend_flightcontroller import FlightController

from frontend_tkinter_connection_selection import ConnectionSelectionWindow

from frontend_tkinter_directory_selection import VehicleDirectorySelectionWindow

from component_editor import JsonEditorApp

from frontend_tkinter import ParameterEditorWindow

from version import VERSION


# pylint: disable=duplicate-code
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
                                     'intermediate parameter file, and an "write" checkbox. The GUI includes "Write '
                                     'Selected to FC" and "Skip" buttons at the bottom. '
                                     'When "Write Selected to FC" is clicked, it writes the selected parameters to the '
                                     'flight controller. '
                                     'When "Skip" is pressed, it skips to the next intermediate parameter file. '
                                     'The process gets repeated for each intermediate parameter file.')
    parser.add_argument('--device',
                        type=str,
                        default="",
                        help='MAVLink connection string to the flight controller. Defaults to autodetection'
                        )
    parser.add_argument('-r', '--reboot-time',
                        type=int,
                        default=7,
                        help='Flight controller reboot time. '
                        'Default is %(default)s')
    parser.add_argument('-t', '--vehicle-type',
                        choices=['AP_Periph', 'AntennaTracker', 'ArduCopter', 'ArduPlane',
                                 'ArduSub', 'Blimp', 'Heli', 'Rover', 'SITL'],
                        default='',
                        help='The type of the vehicle. Defaults to ArduCopter')
    parser.add_argument('--vehicle-dir',
                        type=str,
                        default=os_getcwd(),
                        help='Directory containing vehicle-specific intermediate parameter files. '
                        'Defaults to the current working directory')
    parser.add_argument('--n',
                        type=int,
                        default=0,
                        help='Start directly on the nth intermediate parameter file (skips previous files). '
                        'Default is %(default)s')
    parser.add_argument('--loglevel',
                        type=str,
                        default='INFO',
                        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'],
                        help='Logging level (default is INFO).')
    parser.add_argument('-v', '--version',
                        action='version',
                        version=f'%(prog)s {VERSION}',
                        help='Display version information and exit.')
    return parser.parse_args()
# pylint: enable=duplicate-code


def main():
    args = argument_parser()

    logging_basicConfig(level=logging_getLevelName(args.loglevel), format='%(asctime)s - %(levelname)s - %(message)s')

    # Connect to the flight controller and read the parameters
    flight_controller = FlightController(args.reboot_time)

    error_str = flight_controller.connect(args.device)
    if error_str:
        logging_error(error_str)
        conn_sel_window = ConnectionSelectionWindow(flight_controller, error_str)
        conn_sel_window.root.mainloop()

    vehicle_type = args.vehicle_type
    if vehicle_type == "":  # not explicitly set, to try to guess it
        if "MOT_OPTIONS" in flight_controller.fc_parameters:
            vehicle_type = "ArduCopter"
        if "TECS_OPTIONS" in flight_controller.fc_parameters:
            vehicle_type = "ArduPlane"
        if "WENC_TYPE" in flight_controller.fc_parameters:
            vehicle_type = "ArduRover"
        if "RCMAP_LATERAL" in flight_controller.fc_parameters:
            vehicle_type = "ArduSub"
        if vehicle_type:
            logging_info("Vehicle type not set explicitly, auto-detected %s.", vehicle_type)
    else:
        logging_info("Vehicle type explicitly set to %s.", vehicle_type)

    if vehicle_type == "": # did not guess it, default to ArduCopter
        vehicle_type = "ArduCopter"
        logging_warning("Could not detect vehicle type. Defaulting to ArduCopter.")

    local_filesystem = LocalFilesystem(args.vehicle_dir, vehicle_type)

    # Get the list of intermediate parameter files files that will be processed sequentially
    files = list(local_filesystem.file_parameters.keys())

    if not files:
        logging_error("No intermediate parameter files found in %s.", args.vehicle_dir)
        vehicle_dir_window = VehicleDirectorySelectionWindow(local_filesystem)
        vehicle_dir_window.root.mainloop()

   # Get the list of intermediate parameter files files that will be processed sequentially
    files = list(local_filesystem.file_parameters.keys())

    start_file = None  # pylint: disable=invalid-name
    if files:
        # Determine the starting file based on the --n command line argument
        start_file_index = min(args.n, len(files) - 1) # Ensure the index is within the range of available files
        if start_file_index != args.n:
            logging_warning("Starting file index %s is out of range. Starting with file %s instead.",
                            args.n, files[start_file_index])
        start_file = files[start_file_index]

    app = JsonEditorApp(VERSION, local_filesystem)
    app.root.mainloop()

    # Call the GUI function with the starting intermediate parameter file
    ParameterEditorWindow(start_file, flight_controller, local_filesystem, VERSION)

    # Close the connection to the flight controller
    flight_controller.disconnect()
    sys_exit(0)

if __name__ == "__main__":
    main()
