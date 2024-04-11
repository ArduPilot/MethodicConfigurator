#!/usr/bin/env python3

'''
This file is part of Ardupilot methodic configurator. https://github.com/ArduPilot/MethodicConfigurator

(C) 2024 Amilcar do Carmo Lucas, IAV GmbH

SPDX-License-Identifier:    GPL-3
'''

from argparse import ArgumentParser
from logging import basicConfig as logging_basicConfig
from logging import getLevelName as logging_getLevelName
import tkinter as tk
from tkinter import ttk
# from logging import debug as logging_debug
# from logging import info as logging_info
from os import getcwd as os_getcwd

from backend_filesystem import LocalFilesystem
from frontend_tkinter import ScrollFrame

from frontend_tkinter_base import BaseWindow

from version import VERSION


def argument_parser():
    """
    Parses command-line arguments for the script.

    This function sets up an argument parser to handle the command-line arguments for the script.

    Returns:
    argparse.Namespace: An object containing the parsed arguments.
    """
    parser = ArgumentParser(description='')
    parser.add_argument('--vehicle-dir',
                        type=str,
                        default=os_getcwd(),
                        help='Directory containing vehicle-specific intermediate parameter files. '
                        'Defaults to the current working directory')  # pylint: disable=R0801
    parser.add_argument('--loglevel',
                        type=str,
                        default='INFO',
                        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'],
                        help='Logging level (default is INFO).')  # pylint: disable=R0801
    parser.add_argument('-t', '--vehicle-type',
                        choices=['AP_Periph', 'AntennaTracker', 'ArduCopter', 'ArduPlane',
                                 'ArduSub', 'Blimp', 'Heli', 'Rover', 'SITL'],
                        default='ArduCopter',
                        help='The type of the vehicle. Defaults to ArduCopter')  # pylint: disable=R0801
    parser.add_argument('-v', '--version',
                        action='version',
                        version=f'%(prog)s {VERSION}',
                        help='Display version information and exit.')  # pylint: disable=R0801
    return parser.parse_args()  # pylint: disable=R0801


class JsonEditorApp(BaseWindow):
    """
    A class for editing JSON files in the ArduPilot methodic configurator.

    This class provides a graphical user interface for editing JSON files that
    contain vehicle component configurations. It inherits from the BaseWindow
    class, which provides basic window functionality.
    """
    def __init__(self, version, local_filesystem: LocalFilesystem=None):
        super().__init__()
        self.local_filesystem = local_filesystem

        self.root.title("Amilcar Lucas's - ArduPilot methodic configurator - " + version + " - Vehicle Component Editor")
        self.root.geometry("880x900") # Set the window width

        self.data = local_filesystem.load_vehicle_components_json_data()
        self.entry_widgets = {} # Dictionary for entry widgets

        self.main_frame = ttk.Frame(self.root)
        self.main_frame.pack(side=tk.TOP, fill="x", expand=False, pady=(4, 0)) # Pack the frame at the top of the window

        self.scroll_frame = ScrollFrame(self.root)
        self.scroll_frame.pack(side="top", fill="both", expand=True)

        self.populate_frames()

        self.save_button = ttk.Button(self.root, text="Save", command=self.save_data)
        self.save_button.pack(pady=7)

    def populate_frames(self):
        """
        Populates the ScrollFrame with widgets based on the JSON data.
        """
        for key, value in self.data.items():
            self.add_widget(self.scroll_frame.view_port, key, value, [])

    def add_widget(self, parent, key, value, path):
        """
        Adds a widget to the parent widget with the given key and value.

        Parameters:
        parent (tkinter.Widget): The parent widget to which the LabelFrame/Entry will be added.
        key (str): The key for the LabelFrame/Entry.
        value (dict): The value associated with the key.
        path (list): The path to the current key in the JSON data.
        """
        if isinstance(value, dict):             # JSON non-leaf elements, add LabelFrame widget
            frame = ttk.LabelFrame(parent, text=key)
            is_toplevel = parent == self.scroll_frame.view_port
            side = tk.TOP if is_toplevel else tk.LEFT
            pady = 5 if is_toplevel else 3
            anchor = tk.NW if is_toplevel else tk.N
            frame.pack(fill=tk.X, side=side, pady=pady, padx=5, anchor=anchor)
            for sub_key, sub_value in value.items():
                # recursively add child elements
                self.add_widget(frame, sub_key, sub_value, path + [key])
        else:                                   # JSON leaf elements, add Entry widget
            entry_frame = ttk.Frame(parent)
            entry_frame.pack(side=tk.TOP, fill=tk.X, pady=(0, 5))

            label = ttk.Label(entry_frame, text=key)
            label.pack(side=tk.LEFT)

            entry = ttk.Entry(entry_frame)
            entry.insert(0, str(value))
            entry.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(0, 5))

            # Store the entry widget in the entry_widgets dictionary for later retrieval
            self.entry_widgets[tuple(path+[key])] = entry

    def save_data(self):
        """
        Saves the edited JSON data back to the file.
        """
        for path, entry in self.entry_widgets.items():
            value = entry.get()

            # Navigate through the nested dictionaries using the elements of path
            current_data = self.data
            for key in path[:-1]:
                current_data = current_data[key]

            # Update the value in the data dictionary
            current_data[path[-1]] = value

        # Save the updated data back to the JSON file
        self.local_filesystem.save_vehicle_components_json_data(self.data)
        print("Data saved successfully.")


if __name__ == "__main__":
    args = argument_parser()

    logging_basicConfig(level=logging_getLevelName(args.loglevel), format='%(asctime)s - %(levelname)s - %(message)s')

    filesystem = LocalFilesystem(args.vehicle_dir, args.vehicle_type)
    app = JsonEditorApp(VERSION, filesystem)
    app.root.mainloop()
