#!/usr/bin/env python3

"""
This file is part of Ardupilot methodic configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import argparse
import tkinter as tk
from logging import basicConfig as logging_basicConfig
from logging import getLevelName as logging_getLevelName
from tkinter import ttk
from typing import Optional

from MethodicConfigurator import _, __version__
from MethodicConfigurator.backend_filesystem_program_settings import ProgramSettings
from MethodicConfigurator.backend_filesystem_vehicle_components import VehicleComponents
from MethodicConfigurator.common_arguments import add_common_arguments_and_parse
from MethodicConfigurator.frontend_tkinter_base import BaseWindow
from MethodicConfigurator.middleware_template_overview import TemplateOverview


class TemplateOverviewWindow(BaseWindow):
    """
    Represents the window for viewing and managing ArduPilot vehicle templates.

    This class creates a graphical user interface (GUI) window that displays an overview of available vehicle templates.
    Users can browse through different templates, view their attributes, and perform actions such as storing a template
    directory for further configuration. The window utilizes a Treeview widget to present the templates in a structured
    manner, making it easier for users to navigate and select the desired template for configuration.

    Attributes:
        window (tk.Toplevel): The root Tkinter window object for the GUI.

    Methods:
        on_row_double_click(event): Handles the event triggered when a row in the Treeview is double-clicked, allowing the user
                                     to store the corresponding template directory.
    """

    def __init__(self, parent: Optional[tk.Toplevel] = None):
        super().__init__(parent)
        title = _("Amilcar Lucas's - ArduPilot methodic configurator {} - Template Overview and selection")
        self.root.title(title.format(__version__))
        self.root.geometry("1200x600")

        instruction_text = _("Please double-click the template below that most resembles your own vehicle components")
        instruction_label = ttk.Label(self.main_frame, text=instruction_text, font=("Arial", 12))
        instruction_label.pack(pady=(10, 20))

        self.sort_column: str

        style = ttk.Style(self.root)
        # Add padding to Treeview heading style
        style.layout(
            "Treeview.Heading",
            [
                ("Treeview.Heading.cell", {"sticky": "nswe"}),
                (
                    "Treeview.Heading.border",
                    {
                        "sticky": "nswe",
                        "children": [
                            (
                                "Treeview.Heading.padding",
                                {
                                    "sticky": "nswe",
                                    "children": [
                                        ("Treeview.Heading.image", {"side": "right", "sticky": ""}),
                                        ("Treeview.Heading.text", {"sticky": "we"}),
                                    ],
                                },
                            )
                        ],
                    },
                ),
            ],
        )
        style.configure("Treeview.Heading", padding=[2, 2, 2, 18], justify="center")

        # Define the columns for the Treeview
        columns = TemplateOverview.columns()
        self.tree = ttk.Treeview(self.main_frame, columns=columns, show="headings")
        for col in columns:
            self.tree.heading(col, text=col)

        # Populate the Treeview with data from the template overview
        for key, template_overview in VehicleComponents.get_vehicle_components_overviews().items():
            attribute_names = template_overview.attributes()
            values = (key, *(getattr(template_overview, attr, "") for attr in attribute_names))
            self.tree.insert("", "end", text=key, values=values)

        self.__adjust_treeview_column_widths()

        self.tree.bind("<Double-1>", self.__on_row_double_click)
        self.tree.pack(fill=tk.BOTH, expand=True)

        for col in self.tree["columns"]:
            col_str = str(col)
            self.tree.heading(
                col_str,
                text=col_str,
                command=lambda col=col_str: self.__sort_by_column(col, False),  # type: ignore[misc]
            )

        if isinstance(self.root, tk.Toplevel):
            try:
                while self.root.children:
                    self.root.update_idletasks()
                    self.root.update()
            except tk.TclError as _exp:
                pass
        else:
            self.root.mainloop()

    def __adjust_treeview_column_widths(self):
        """
        Adjusts the column widths of the Treeview to fit the contents of each column.
        """
        for col in self.tree["columns"]:
            max_width = 0
            for subtitle in col.title().split("\n"):
                max_width = max(max_width, tk.font.Font().measure(subtitle))

            # Iterate over all rows and update the max_width if a wider entry is found
            for item in self.tree.get_children():
                item_text = self.tree.item(item, "values")[self.tree["columns"].index(col)]
                text_width = tk.font.Font().measure(item_text)
                max_width = max(max_width, text_width)

            # Update the column's width property to accommodate the largest text width
            self.tree.column(col, width=int(max_width * 0.6 + 10))

    def __on_row_double_click(self, event):
        """Handle row double-click event."""
        item_id = self.tree.identify_row(event.y)
        if item_id:
            selected_template_relative_path = self.tree.item(item_id)["text"]
            ProgramSettings.store_template_dir(selected_template_relative_path)
            self.root.destroy()

    def __sort_by_column(self, col: str, reverse: bool):
        if hasattr(self, "sort_column") and self.sort_column and self.sort_column != col:
            self.tree.heading(self.sort_column, text=self.sort_column)
        self.tree.heading(col, text=col + (" ▼" if reverse else " ▲"))
        self.sort_column = col

        try:
            col_data = [(float(self.tree.set(k, col)), k) for k in self.tree.get_children("")]
        except ValueError:
            col_data = [(self.tree.set(k, col), k) for k in self.tree.get_children("")]
        col_data.sort(reverse=reverse)

        # rearrange items in sorted positions
        for index, (_val, k) in enumerate(col_data):
            self.tree.move(k, "", index)

        # reverse sort next time
        self.tree.heading(col, command=lambda: self.__sort_by_column(col, not reverse))


def argument_parser():
    """
    Parses command-line arguments for the script.

    This function sets up an argument parser to handle the command-line arguments for the script.

    Returns:
    argparse.Namespace: An object containing the parsed arguments.
    """
    parser = argparse.ArgumentParser(
        description=_(
            "ArduPilot methodic configurator is a GUI-based tool designed to simplify "
            "the management and visualization of ArduPilot parameters. It enables users "
            "to browse through various vehicle templates, edit parameter files, and "
            "apply changes directly to the flight controller. The tool is built to "
            "semi-automate the configuration process of ArduPilot for drones by "
            "providing a clear and intuitive interface for parameter management."
        )
    )
    return add_common_arguments_and_parse(parser)


def main():
    args = argument_parser()

    logging_basicConfig(level=logging_getLevelName(args.loglevel), format="%(asctime)s - %(levelname)s - %(message)s")

    TemplateOverviewWindow(None)

    print(ProgramSettings.get_recently_used_dirs()[0])


if __name__ == "__main__":
    main()
