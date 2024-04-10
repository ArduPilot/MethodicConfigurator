#!/usr/bin/env python3

'''
This file is part of Ardupilot methodic configurator. https://github.com/ArduPilot/MethodicConfigurator

(C) 2024 Amilcar do Carmo Lucas, IAV GmbH

SPDX-License-Identifier:    GPL-3
'''

import tkinter as tk
from tkinter import ttk
from json import load as json_load
from json import dump as json_dump
from logging import basicConfig as logging_basicConfig
# from logging import debug as logging_debug
# from logging import info as logging_info

from backend_filesystem import LocalFilesystem
from frontend_tkinter import ScrollFrame

from version import VERSION


def load_json_data(file_path):
    with open(file_path, 'r', encoding='utf-8') as file:
        data = json_load(file)
    return data


def save_json_data(file_path, data):
    with open(file_path, 'w', encoding='utf-8') as file:
        json_dump(data, file, indent=4)


class JsonEditorApp(tk.Tk):
    def __init__(self, json_file_path, version):
        """
        Initializes the JsonEditorApp with a given JSON file path.

        Parameters:
        json_file_path (str): The path to the JSON file to be edited.
        """
        super().__init__()
        self.title("Amilcar Lucas's - ArduPilot methodic configurator - " + version + " - Vehicle Component Editor")
        self.geometry("880x900") # Set the window width

        # Set the theme to 'alt'
        style = ttk.Style()
        style.theme_use('alt')

        # Set the application icon for the window and all child windows
        # https://pythonassets.com/posts/window-icon-in-tk-tkinter/
        self.iconphoto(True, tk.PhotoImage(file=LocalFilesystem.application_icon_filepath()))

        self.json_file_path = json_file_path
        self.data = load_json_data(self.json_file_path)
        self.entry_widgets = {} # Dictionary for entry widgets

        self.main_frame = ttk.Frame(self)
        self.main_frame.pack(expand=True, fill=tk.BOTH, padx=0, pady=0)

        self.scroll_frame = ScrollFrame(self.main_frame)
        self.scroll_frame.pack(side="top", fill="both", expand=True)

        self.populate_frames()

        self.save_button = ttk.Button(self, text="Save", command=self.save_data)
        self.save_button.pack(pady=7)

    def populate_frames(self):
        """
        Populates the ScrollFrame with widgets based on the JSON data.
        """
        for key, value in self.data.items():
            self.add_widget(self.scroll_frame.viewPort, key, value, [])

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
            is_toplevel = parent == self.scroll_frame.viewPort
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
        save_json_data(self.json_file_path, self.data)
        print("Data saved successfully.")


if __name__ == "__main__":
    json_file_path = "Frame Diatone Taycan MX-C.json" # Adjust the path as necessary
    logging_basicConfig(level=0)
    app = JsonEditorApp(json_file_path, VERSION)
    app.mainloop()
