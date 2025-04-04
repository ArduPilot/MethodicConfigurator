#!/usr/bin/env python3

"""
Vehicle template overview GUI.

This file is part of Ardupilot methodic configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2025 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import argparse
import tkinter as tk
from logging import basicConfig as logging_basicConfig
from logging import debug as logging_debug
from logging import getLevelName as logging_getLevelName
from tkinter import ttk
from typing import Optional

from ardupilot_methodic_configurator import _, __version__
from ardupilot_methodic_configurator.backend_filesystem_program_settings import ProgramSettings
from ardupilot_methodic_configurator.backend_filesystem_vehicle_components import VehicleComponents
from ardupilot_methodic_configurator.common_arguments import add_common_arguments
from ardupilot_methodic_configurator.frontend_tkinter_base_window import BaseWindow
from ardupilot_methodic_configurator.middleware_template_overview import TemplateOverview

IMAGE_HEIGHT_PX = 100


class TemplateOverviewWindow(BaseWindow):
    """
    Represents the window for viewing and managing ArduPilot vehicle templates.

    This class creates a graphical user interface (GUI) window that displays an overview of available vehicle templates.
    Users can browse through different templates, view their attributes, and perform actions such as storing a template
    directory for further configuration. The window utilizes a Treeview widget to present the templates in a structured
    manner, making it easier for users to navigate and select the desired template for configuration.

    Attributes:
        window (tk.Tk|None): The root Tkinter window object for the GUI.

    Methods:
        on_row_double_click(event): Handles the event triggered when a row in the Treeview is double-clicked, allowing the user
                                     to store the corresponding template directory.

    """

    def __init__(self, parent: Optional[tk.Tk] = None) -> None:
        super().__init__(parent)
        title = _("Amilcar Lucas's - ArduPilot methodic configurator {} - Template Overview and selection")
        self.root.title(title.format(__version__))
        self.root.geometry("1200x600")

        self.top_frame = ttk.Frame(self.main_frame, height=IMAGE_HEIGHT_PX)
        self.top_frame.pack(side=tk.TOP, fill="x", expand=False)

        instruction_text = _("Please double-click the template below that most resembles your own vehicle components")
        instruction_text += _("\nit does not need to exactly match your vehicle's components.")
        instruction_label = ttk.Label(self.top_frame, text=instruction_text, font=("Arial", 12))
        instruction_label.pack(side=tk.LEFT, pady=(10, 20))

        self.image_label = ttk.Label(self.top_frame)
        self.image_label.pack(side=tk.RIGHT, anchor=tk.NE, padx=(20, 20), pady=IMAGE_HEIGHT_PX / 2)

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

        self._adjust_treeview_column_widths()

        self.tree.bind("<ButtonRelease-1>", self.__on_row_selection_change)
        self.tree.bind("<Up>", self.__on_row_selection_change)
        self.tree.bind("<Down>", self.__on_row_selection_change)
        self.tree.bind("<Double-1>", self.__on_row_double_click)
        self.tree.pack(fill=tk.BOTH, expand=True)

        for col in self.tree["columns"]:
            col_str = str(col)
            self.tree.heading(
                col_str,
                text=col_str,
                command=lambda col2=col_str: self.__sort_by_column(col2, reverse=False),  # type: ignore[misc]
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

    def _adjust_treeview_column_widths(self) -> None:
        """Adjusts the column widths of the Treeview to fit the contents of each column."""
        for col in self.tree["columns"]:
            max_width = 0
            for subtitle in col.title().split("\n"):
                max_width = max(max_width, tk.font.Font().measure(subtitle))  # pyright: ignore[reportAttributeAccessIssue]

            # Iterate over all rows and update the max_width if a wider entry is found
            for item in self.tree.get_children():
                item_text = self.tree.item(item, "values")[self.tree["columns"].index(col)]
                text_width = tk.font.Font().measure(item_text)  # pyright: ignore[reportAttributeAccessIssue]
                max_width = max(max_width, text_width)

            # Update the column's width property to accommodate the largest text width
            self.tree.column(col, width=int(max_width * 0.6 + 10))

    def __on_row_selection_change(self, _event: tk.Event) -> None:
        """Handle row single-click event."""
        self.root.after(0, self.__update_selection)

    def __update_selection(self) -> None:
        """Update selection after keypress event."""
        selected_item = self.tree.selection()
        if selected_item:
            item_id = selected_item[0]
            selected_template_relative_path = self.tree.item(item_id)["text"]
            ProgramSettings.store_template_dir(selected_template_relative_path)
            self._display_vehicle_image(selected_template_relative_path)

    def __on_row_double_click(self, event: tk.Event) -> None:
        """Handle row double-click event."""
        item_id = self.tree.identify_row(event.y)
        if item_id:
            selected_template_relative_path = self.tree.item(item_id)["text"]
            ProgramSettings.store_template_dir(selected_template_relative_path)
            self.root.destroy()

    def __sort_by_column(self, col: str, reverse: bool) -> None:
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

    def _display_vehicle_image(self, template_path: str) -> None:
        """Display the vehicle image corresponding to the selected template."""
        # Delete the previous image
        for widget in self.top_frame.winfo_children():
            if isinstance(widget, ttk.Label) and widget == self.image_label:
                widget.destroy()
        try:
            vehicle_image_filepath = VehicleComponents.get_vehicle_image_filepath(template_path)
            self.image_label = self.put_image_in_label(self.top_frame, vehicle_image_filepath, IMAGE_HEIGHT_PX)
        except FileNotFoundError:
            self.image_label = ttk.Label(
                self.top_frame,
                text=_("No 'vehicle.jpg' image file in the vehicle directory."),
                padding=IMAGE_HEIGHT_PX / 2 - 8,
            )
        self.image_label.pack(side=tk.RIGHT, anchor=tk.NE, padx=(4, 0), pady=(0, 0))


def argument_parser() -> argparse.Namespace:
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
    return add_common_arguments(parser).parse_args()


def main() -> None:
    args = argument_parser()

    logging_basicConfig(level=logging_getLevelName(args.loglevel), format="%(asctime)s - %(levelname)s - %(message)s")

    TemplateOverviewWindow(None)

    logging_debug(ProgramSettings.get_recently_used_dirs()[0])


if __name__ == "__main__":
    main()
