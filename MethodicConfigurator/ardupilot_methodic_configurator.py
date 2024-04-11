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
# from logging import info as logging_info
from logging import warning as logging_warning
from logging import error as logging_error
from os import getcwd as os_getcwd
from sys import exit as sys_exit

from backend_filesystem import LocalFilesystem
from backend_flightcontroller import FlightController
from frontend_tkinter_base import show_no_param_files_error
from frontend_tkinter_base import show_no_connection_error
from frontend_tkinter import gui

from version import VERSION


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
                        )  # pylint: disable=R0801
    parser.add_argument('--vehicle-dir',
                        type=str,
                        default=os_getcwd(),
                        help='Directory containing vehicle-specific intermediate parameter files. '
                        'Defaults to the current working directory')  # pylint: disable=R0801
    parser.add_argument('--n',
                        type=int,
                        default=0,
                        help='Start directly on the nth intermediate parameter file (skips previous files). '
                        'Default is %(default)s')  # pylint: disable=R0801
    parser.add_argument('--loglevel',
                        type=str,
                        default='INFO',
                        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'],
                        help='Logging level (default is INFO).')  # pylint: disable=R0801
    parser.add_argument('-r', '--reboot-time',
                        type=int,
                        default=7,
                        help='Flight controller reboot time. '
                        'Default is %(default)s')  # pylint: disable=R0801
    parser.add_argument('-t', '--vehicle-type',
                        choices=['AP_Periph', 'AntennaTracker', 'ArduCopter', 'ArduPlane',
                                 'ArduSub', 'Blimp', 'Heli', 'Rover', 'SITL'],
                        default='ArduCopter',
                        help='The type of the vehicle. Defaults to ArduCopter')  # pylint: disable=R0801
    parser.add_argument('-v', '--version',
                        action='version',
                        version=f'%(prog)s {VERSION}',
                        help='Display version information and exit.')  # pylint: disable=R0801
    return parser.parse_args()   # pylint: disable=R0801


if __name__ == "__main__":
    args = argument_parser()

    logging_basicConfig(level=logging_getLevelName(args.loglevel), format='%(asctime)s - %(levelname)s - %(message)s')

    # Connect to the flight controller and read the parameters
    flight_controller = FlightController(args.reboot_time)

    error_str = flight_controller.connect(args.device)
    if error_str:
        logging_error(error_str)
        show_no_connection_error(error_str)

    local_filesystem = LocalFilesystem(args.vehicle_dir, args.vehicle_type)

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
    else:
        logging_error("No intermediate parameter files found in %s.", args.vehicle_dir)
        show_no_param_files_error(args.vehicle_dir)

    # Call the GUI function with the starting intermediate parameter file
    gui(start_file, flight_controller, local_filesystem, VERSION)

    # Close the connection to the flight controller
    flight_controller.disconnect()
    sys_exit(0)
