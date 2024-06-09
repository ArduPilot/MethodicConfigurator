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

from MethodicConfigurator.middleware_template_overview import TemplateOverview

from MethodicConfigurator.backend_filesystem import LocalFilesystem

from MethodicConfigurator.common_arguments import add_common_arguments_and_parse

from MethodicConfigurator.frontend_tkinter_base import BaseWindow
from MethodicConfigurator.frontend_tkinter_base import show_error_message

from MethodicConfigurator.version import VERSION


class TemplateOverviewWindow(BaseWindow):
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
    def __init__(self, parent: tk.Tk, local_filesystem: LocalFilesystem):
        super().__init__(parent)
        self.root.title(f"Amilcar Lucas's - ArduPilot methodic configurator {VERSION} - Template Overview and selection")
        self.root.geometry("1200x300")
        self.local_filesystem = local_filesystem

        instruction_text = "Please double-click the template below that most resembles your own vehicle components"
        instruction_label = ttk.Label(self.main_frame, text=instruction_text, font=('Arial', 12))
        instruction_label.pack(pady=(10, 20))

        style = ttk.Style(self.root)
        # Add padding to Treeview heading style
        style.layout("Treeview.Heading", [
            ("Treeview.Heading.cell", {'sticky': 'nswe'}),
            ("Treeview.Heading.border", {'sticky':'nswe', 'children': [
                ("Treeview.Heading.padding", {'sticky':'nswe', 'children': [
                    ("Treeview.Heading.image", {'side':'right', 'sticky':''}),
                    ("Treeview.Heading.text", {'sticky':'we'})
                ]})
            ]}),
        ])
        style.configure("Treeview.Heading", padding=[2, 2, 2, 18], justify='center')

        # Define the columns for the Treeview
        columns = TemplateOverview.columns()
        self.tree = ttk.Treeview(self.main_frame, columns=columns, show='headings')
        for col in columns:
            self.tree.heading(col, text=col)

        # Populate the Treeview with data from the template overview
        for key, template_overview in self.local_filesystem.get_vehicle_components_overviews().items():
            attribute_names = template_overview.attributes()
            values = (key,) + tuple(getattr(template_overview, attr, '') for attr in attribute_names)
            self.tree.insert('', 'end', text=key, values=values)

        self.adjust_treeview_column_widths()

        self.tree.bind('<Double-1>', self.on_row_double_click)
        self.tree.pack(fill=tk.BOTH, expand=True)

        if isinstance(self.root, tk.Toplevel):
            try:
                while self.root.children:
                    self.root.update_idletasks()
                    self.root.update()
            except tk.TclError as _exp:
                pass
        else:
            self.root.mainloop()

    def adjust_treeview_column_widths(self):
        """
        Adjusts the column widths of the Treeview to fit the contents of each column.
        """
        for col in self.tree["columns"]:
            max_width = 0
            for subtitle in col.title().split('\n'):
                max_width = max(max_width, tk.font.Font().measure(subtitle))

            # Iterate over all rows and update the max_width if a wider entry is found
            for item in self.tree.get_children():
                item_text = self.tree.item(item, 'values')[self.tree["columns"].index(col)]
                text_width = tk.font.Font().measure(item_text)
                max_width = max(max_width, text_width)

            # Update the column's width property to accommodate the largest text width
            self.tree.column(col, width=int(max_width*0.6 + 10))

    def on_row_double_click(self, event):
        """Handle row double-click event."""
        item_id = self.tree.identify_row(event.y)
        if item_id:
            selected_template_relative_path = self.tree.item(item_id)['text']
            self.local_filesystem.store_template_dir(selected_template_relative_path)
            self.root.destroy()

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

    TemplateOverviewWindow(None, local_filesystem)

    print(local_filesystem.get_recently_used_dirs()[0])

if __name__ == "__main__":
    main()
