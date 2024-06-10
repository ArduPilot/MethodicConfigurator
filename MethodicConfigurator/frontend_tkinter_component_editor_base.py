#!/usr/bin/env python3

'''
This file is part of Ardupilot methodic configurator. https://github.com/ArduPilot/MethodicConfigurator

(C) 2024 Amilcar do Carmo Lucas

SPDX-License-Identifier:    GPL-3
'''

from argparse import ArgumentParser

from logging import basicConfig as logging_basicConfig
from logging import getLevelName as logging_getLevelName
# from logging import debug as logging_debug
from logging import info as logging_info

import tkinter as tk
from tkinter import ttk

from MethodicConfigurator.common_arguments import add_common_arguments_and_parse

from MethodicConfigurator.backend_filesystem import LocalFilesystem

from MethodicConfigurator.frontend_tkinter_base import show_tooltip
from MethodicConfigurator.frontend_tkinter_base import show_error_message
from MethodicConfigurator.frontend_tkinter_base import ScrollFrame
from MethodicConfigurator.frontend_tkinter_base import BaseWindow

from MethodicConfigurator.version import VERSION


def argument_parser():
    """
    Parses command-line arguments for the script.

    This function sets up an argument parser to handle the command-line arguments for the script.

    Returns:
    argparse.Namespace: An object containing the parsed arguments.
    """
    parser = ArgumentParser(description='A GUI for editing JSON files that contain vehicle component configurations. '
                            'Not to be used directly, but through the main ArduPilot methodic configurator script.')
    parser = LocalFilesystem.add_argparse_arguments(parser)
    parser = ComponentEditorWindowBase.add_argparse_arguments(parser)
    return add_common_arguments_and_parse(parser)


class ComponentEditorWindowBase(BaseWindow):
    """
    A class for editing JSON files in the ArduPilot methodic configurator.

    This class provides a graphical user interface for editing JSON files that
    contain vehicle component configurations. It inherits from the BaseWindow
    class, which provides basic window functionality.
    """
    def __init__(self, version, local_filesystem: LocalFilesystem=None):
        super().__init__()
        self.local_filesystem = local_filesystem

        self.root.title("Amilcar Lucas's - ArduPilot methodic configurator " + version + " - Vehicle Component Editor")
        self.root.geometry("880x600") # Set the window width

        self.data = local_filesystem.load_vehicle_components_json_data(local_filesystem.vehicle_dir)
        if len(self.data) < 1:
            # Schedule the window to be destroyed after the mainloop has started
            self.root.after(100, self.root.destroy) # Adjust the delay as needed
            return

        self.entry_widgets = {} # Dictionary for entry widgets

        intro_frame = ttk.Frame(self.main_frame)
        intro_frame.pack(side=tk.TOP, fill="x", expand=False)

        style = ttk.Style()
        style.configure("bigger.TLabel", font=("TkDefaultFont", 14))

        explanation_text = "Please configure all vehicle component properties in this window.\n"
        explanation_text += "Scroll down and make sure you do not miss a property.\n"
        explanation_text += "Saving the result will write to the vehicle_components.json file."
        explanation_label = ttk.Label(intro_frame, text=explanation_text, wraplength=800, justify=tk.LEFT)
        explanation_label.configure(style="bigger.TLabel")
        explanation_label.pack(side=tk.LEFT, padx=(10, 10), pady=(10, 0), anchor=tk.NW)

        # Load the vehicle image and scale it down to image_height pixels in height
        if local_filesystem.vehicle_image_exists():
            image_label = self.put_image_in_label(intro_frame, local_filesystem.vehicle_image_filepath(), 100)
            image_label.pack(side=tk.RIGHT, anchor=tk.NE, padx=(4, 4), pady=(4, 0))
            show_tooltip(image_label, "Replace the vehicle.jpg file in the vehicle directory to change the vehicle image.")
        else:
            image_label = ttk.Label(intro_frame, text="No vehicle.jpg image file found on the vehicle directory.")
            image_label.pack(side=tk.RIGHT, anchor=tk.NE, padx=(4, 4), pady=(4, 0))

        self.scroll_frame = ScrollFrame(self.main_frame)
        self.scroll_frame.pack(side="top", fill="both", expand=True)

        self.update_json_data()

        self.__populate_frames()

        save_frame = ttk.Frame(self.main_frame)
        save_frame.pack(side=tk.TOP, fill="x", expand=False)
        self.save_button = ttk.Button(save_frame, text="Save data and start configuration", command=self.save_data)
        show_tooltip(self.save_button, "Save component data and start parameter value configuration and tuning.")
        self.save_button.pack(pady=7)

    def update_json_data(self):  # should be overwritten in child classes
        if 'Format version' not in self.data:
            self.data['Format version'] = 1

    def __populate_frames(self):
        """
        Populates the ScrollFrame with widgets based on the JSON data.
        """
        if "Components" in self.data:
            for key, value in self.data["Components"].items():
                self.__add_widget(self.scroll_frame.view_port, key, value, [])

    def __add_widget(self, parent, key, value, path):
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
                self.__add_widget(frame, sub_key, sub_value, path + [key])
        else:                                   # JSON leaf elements, add Entry widget
            entry_frame = ttk.Frame(parent)
            entry_frame.pack(side=tk.TOP, fill=tk.X, pady=(0, 5))

            label = ttk.Label(entry_frame, text=key)
            label.pack(side=tk.LEFT)

            entry = self.add_entry_or_combobox(value, entry_frame, tuple(path+[key]))
            entry.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(0, 5))

            # Store the entry widget in the entry_widgets dictionary for later retrieval
            self.entry_widgets[tuple(path+[key])] = entry

    def save_data(self):
        """
        Saves the edited JSON data back to the file.
        """
        for path, entry in self.entry_widgets.items():
            value = entry.get()
            # Navigate through the nested dictionaries using the elements of the path
            current_data = self.data["Components"]
            for key in path[:-1]:
                current_data = current_data[key]

            if path[-1] != "Version":
                try:
                    value = int(value)
                except ValueError:
                    try:
                        value = float(value)
                    except ValueError:
                        value = str(value)

            # Update the value in the data dictionary
            current_data[path[-1]] = value

        # Save the updated data back to the JSON file
        if self.local_filesystem.save_vehicle_components_json_data(self.data, self.local_filesystem.vehicle_dir):
            show_error_message("Error", "Failed to save data to file. Is the destination write protected?")
        else:
            logging_info("Vehicle component data saved successfully.")
        self.root.destroy()

    # This function will be overwritten in child classes
    def add_entry_or_combobox(self, value, entry_frame, path):  # pylint: disable=unused-argument
        entry = ttk.Entry(entry_frame)
        entry.insert(0, str(value))
        return entry

    @staticmethod
    def add_argparse_arguments(parser):
        parser.add_argument('--skip-component-editor',
                            action='store_true',
                            help='Skip the component editor window. Only use this if all components have been configured. '
                            'Default to false')
        return parser


if __name__ == "__main__":
    args = argument_parser()

    logging_basicConfig(level=logging_getLevelName(args.loglevel), format='%(asctime)s - %(levelname)s - %(message)s')

    filesystem = LocalFilesystem(args.vehicle_dir, args.vehicle_type, args.allow_editing_template_files)
    app = ComponentEditorWindowBase(VERSION, filesystem)
    app.root.mainloop()
