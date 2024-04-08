#!/usr/bin/env python3

'''
This file is part of Ardupilot methodic configurator. https://github.com/ArduPilot/MethodicConfigurator

(C) 2024 Amilcar do Carmo Lucas, IAV GmbH

SPDX-License-Identifier:    GPL-3
'''

import tkinter as tk
from tkinter import ttk
import json


def load_json_data(file_path):
    with open(file_path, 'r') as file:
        data = json.load(file)
    return data


def save_json_data(file_path, data):
    with open(file_path, 'w') as file:
        json.dump(data, file, indent=4)


class JsonEditorApp(tk.Tk):
    def __init__(self, json_file_path):
        """
        Initializes the JsonEditorApp with a given JSON file path.

        Parameters:
        json_file_path (str): The path to the JSON file to be edited.
        """
        super().__init__()
        self.title("Vehicle Component Editor")
        self.json_file_path = json_file_path
        self.data = load_json_data(self.json_file_path)
        self.entry_widgets = {} # Dictionary for entry widgets

        self.main_frame = ttk.Frame(self)
        self.main_frame.pack(expand=True, fill=tk.BOTH, padx=10, pady=10)

        self.populate_frames()

        self.save_button = ttk.Button(self, text="Save", command=self.save_data)
        self.save_button.pack(pady=10)

    def populate_frames(self):
        """
        Populates the frames with widgets based on the JSON data.
        """
        for key, value in self.data.items():
            self.add_frame(self.main_frame, key, value, [])

    def add_frame(self, parent, key, value, path):
        """
        Adds a frame to the parent widget with the given key and value.

        Parameters:
        parent (tkinter.Widget): The parent widget to which the frame will be added.
        key (str): The key for the frame.
        value (dict): The value associated with the key.
        path (list): The path to the current key in the JSON data.
        """
        # Only create a frame if the value is a dictionary or if it's a top-level key
        if isinstance(value, dict) or parent == self.main_frame:
            frame = ttk.LabelFrame(parent, text=key)
            frame.pack(fill=tk.X, pady=5)
            parent_for_entries = frame
        else:
            parent_for_entries = parent

        if isinstance(value, dict):
            path += [key]
            for sub_key, sub_value in value.items():
                self.add_frame(parent_for_entries, sub_key, sub_value, path)
        else:
            self.add_entry(parent_for_entries, key, value, path)

    def add_entry(self, parent, key, value, path):
        """
        Adds an entry widget to the parent widget with the given key and value.

        Parameters:
        parent (tkinter.Widget): The parent widget to which the entry widget will be added.
        key (str): The key for the entry widget.
        value (str): The value associated with the key.
        path (list): The path to the current key in the JSON data.
        """
        entry_frame = ttk.Frame(parent)
        entry_frame.pack(side=tk.LEFT, fill=tk.X)

        label = ttk.Label(entry_frame, text=key)
        label.pack(side=tk.LEFT)

        entry = ttk.Entry(entry_frame)
        entry.insert(0, str(value))
        entry.pack(side=tk.LEFT, expand=True, fill=tk.X)

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
    app = JsonEditorApp(json_file_path)
    app.mainloop()
