#!/usr/bin/env python3

'''
This file is part of Ardupilot methodic configurator. https://github.com/ArduPilot/MethodicConfigurator

(C) 2024 Amilcar do Carmo Lucas

SPDX-License-Identifier:    GPL-3
'''

import argparse
from logging import basicConfig as logging_basicConfig
from logging import getLevelName as logging_getLevelName

import tkinter as tk
from tkinter import ttk

from typing import Dict

from middleware_template_overview import TemplateOverview

from backend_filesystem import LocalFilesystem

from common_arguments import add_common_arguments_and_parse

from frontend_tkinter_base import show_error_message


class TemplateOverviewWindow:
    """
    Represents the window for viewing and managing ArduPilot vehicle templates.

    This class creates a graphical user interface (GUI) window that displays an overview of available vehicle templates.
    Users can browse through different templates, view their attributes, and perform actions such as storing a template
    directory for further configuration. The window utilizes a Treeview widget to present the templates in a structured
    manner, making it easier for users to navigate and select the desired template for configuration.

    Attributes:
        window (tk.Tk): The root Tkinter window object for the GUI.
        local_filesystem (LocalFilesystem): An instance of LocalFilesystem used to interact with the filesystem, including
                                            operations related to template directories.

    Methods:
        on_row_double_click(event): Handles the event triggered when a row in the Treeview is double-clicked, allowing the user
                                     to store the corresponding template directory.
    """
    def __init__(self, vehicle_templates_overviews: Dict[str, TemplateOverview], local_filesystem: LocalFilesystem, parent: tk.Tk=None):
        self.window = tk.Toplevel(parent)
        self.window.title("ArduPilot methodic configurator - Template Overview")
        self.window.geometry("800x600")
        self.local_filesystem = local_filesystem
        self.font = tk.font.Font()  # Default font for measuring text width

        # Instantiate the RichText widget to display instructions above the Treeview
        instruction_text = "Please double-click the template below that most resembles your own vehicle components"
        instruction_label = ttk.Label(self.window, text=instruction_text, font=('Arial', 12))
        instruction_label.pack(pady=(10, 20))

        # Define the columns for the Treeview
        columns = TemplateOverview.columns()
        self.tree = ttk.Treeview(self.window, columns=columns, show='headings')
        for col in columns:
            self.tree.heading(col, text=col)
            #self.tree.column(col, width=100)

        # Populate the Treeview with data from the template overview
        for key, template_overview in vehicle_templates_overviews.items():
            attribute_names = template_overview.attributes()
            values = (key,) + tuple(getattr(template_overview, attr, '') for attr in attribute_names)
            self.tree.insert('', 'end', text=key, values=values)

        self.tree.bind('<Double-1>', self.on_row_double_click)
        self.tree.pack(fill=tk.BOTH, expand=True)

        #self.adjust_treeview_column_widths()

        self.window.mainloop()

    def adjust_treeview_column_widths(self):
        """
        Adjusts the column widths of the Treeview to fit the contents of each column.
        """
        max_widths = [0] * len(self.tree["columns"])  # Initialize max_widths list with zeros

        # Iterate through all items to find the maximum width required for each column
        for item in self.tree.get_children():
            for i, col in enumerate(self.tree["columns"][:-1]):  # Exclude the last column ('text') as it's handled separately
                max_widths[i] = max(max_widths[i], self.measure_text_width(self.tree.set(item, col)))

        # Set the column widths
        for i, max_w in enumerate(max_widths):
            self.tree.column(self.tree["columns"][i], width=max_w + 0)  # Adding some padding

    def measure_text_width(self, text):
        return self.font.measure(text)  # The width of the text in pixels

    def on_row_double_click(self, event):
        """Handle row double-click event."""
        item_id = self.tree.identify_row(event.y)
        if item_id:
            template_relative_path = self.tree.item(item_id)['text']
            self.local_filesystem.store_template_dir(template_relative_path)
            self.window.destroy()

def argument_parser():
    """
    Parses command-line arguments for the script.

    This function sets up an argument parser to handle the command-line arguments for the script.

    Returns:
    argparse.Namespace: An object containing the parsed arguments.
    """
    parser = argparse.ArgumentParser(description='ArduPilot methodic configurator is a GUI-based tool designed to simplify '
                                                 'the management and visualization of ArduPilot parameters. It enables users '
                                                 'to browse through various vehicle templates, edit parameter files, and '
                                                 'apply changes directly to the flight controller. The tool is built to '
                                                 'semi-automate the configuration process of ArduPilot for drones by '
                                                 'providing a clear and intuitive interface for parameter management.')
    parser = LocalFilesystem.add_argparse_arguments(parser)
    return add_common_arguments_and_parse(parser)

def main():
    args = argument_parser()

    logging_basicConfig(level=logging_getLevelName(args.loglevel), format='%(asctime)s - %(levelname)s - %(message)s')

    vehicle_type = "ArduCopter"

    try:
        local_filesystem = LocalFilesystem(args.vehicle_dir, vehicle_type, args.allow_editing_template_files)
    except SystemExit as expt:
        show_error_message("Fatal error reading parameter files", f"{expt}")
        raise

    vehicle_components_overviews = local_filesystem.get_vehicle_components_overviews()

    TemplateOverviewWindow(vehicle_components_overviews, local_filesystem)

    print(local_filesystem.get_recently_used_dirs()[0])

if __name__ == "__main__":
    main()
