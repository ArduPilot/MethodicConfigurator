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
from logging import getLevelName as logging_getLevelName
from logging import info as logging_info
from tkinter import font as tkfont
from tkinter import ttk
from typing import Optional, Protocol

from ardupilot_methodic_configurator import _, __version__
from ardupilot_methodic_configurator.backend_filesystem_program_settings import ProgramSettings
from ardupilot_methodic_configurator.backend_filesystem_vehicle_components import VehicleComponents
from ardupilot_methodic_configurator.common_arguments import add_common_arguments
from ardupilot_methodic_configurator.data_model_template_overview import TemplateOverview
from ardupilot_methodic_configurator.frontend_tkinter_base_window import BaseWindow
from ardupilot_methodic_configurator.frontend_tkinter_rich_text import get_widget_font_family_and_size


class VehicleComponentsProviderProtocol(Protocol):
    """Minimal protocol for vehicle components provider - only methods used by TemplateOverviewWindow."""

    @staticmethod
    def get_vehicle_components_overviews() -> dict[str, TemplateOverview]:
        """Get vehicle components overviews."""
        ...  # pylint: disable=unnecessary-ellipsis

    @staticmethod
    def get_vehicle_image_filepath(relative_template_path: str) -> str:
        """Get vehicle image filepath."""
        ...  # pylint: disable=unnecessary-ellipsis


class ProgramSettingsProviderProtocol(Protocol):  # pylint: disable=too-few-public-methods
    """Minimal protocol for program settings provider - only methods used by TemplateOverviewWindow."""

    @staticmethod
    def store_template_dir(relative_template_dir: str) -> None:
        """Store template directory."""
        ...  # pylint: disable=unnecessary-ellipsis


IMAGE_HEIGHT_PX = 100


class TemplateOverviewWindow(BaseWindow):
    """
    Represents the window for viewing and managing ArduPilot vehicle templates.

    This class creates a graphical user interface (GUI) window that displays an overview of available vehicle templates.
    Users can browse through different templates, view their attributes, and perform actions such as storing a template
    directory for further configuration. The window utilizes a Treeview widget to present the templates in a structured
    manner, making it easier for users to navigate and select the desired template for configuration.

    Attributes:
        sort_column (str): The column currently being used for sorting
        tree (ttk.Treeview): The treeview widget displaying templates
        image_label (ttk.Label): Label for displaying vehicle images
        top_frame (ttk.Frame): Top frame containing instructions and image
        vehicle_components_provider: Provider for vehicle components data
        program_settings_provider: Provider for program settings operations

    """

    def __init__(
        self,
        parent: Optional[tk.Tk] = None,
        vehicle_components_provider: Optional[VehicleComponentsProviderProtocol] = None,
        program_settings_provider: Optional[ProgramSettingsProviderProtocol] = None,
        connected_fc_vehicle_type: Optional[str] = None,
    ) -> None:
        """
        Initialize the TemplateOverviewWindow.

        Args:
            parent: Optional parent Tk window
            vehicle_components_provider: Optional provider for vehicle components (for dependency injection)
            program_settings_provider: Optional provider for program settings (for dependency injection)
            connected_fc_vehicle_type: Optional firmware type of connected flight controller for filtering templates

        """
        super().__init__(parent)

        # Dependency injection for better testability
        self.vehicle_components_provider: VehicleComponentsProviderProtocol = vehicle_components_provider or VehicleComponents
        self.program_settings_provider: ProgramSettingsProviderProtocol = program_settings_provider or ProgramSettings

        self.image_label: ttk.Label
        # Initialize sorting state
        self.sort_column: str = ""

        # Initialize UI configuration
        self._configure_window()
        self._initialize_ui_components()
        self._setup_layout()
        self._configure_treeview(connected_fc_vehicle_type or "")
        self._bind_events()

    def _configure_window(self) -> None:
        """Configure the main window properties."""
        title = _("Amilcar Lucas's - ArduPilot methodic configurator {} - Template Overview and selection")
        self.root.title(title.format(__version__))

        # Scale window geometry for HiDPI displays
        scaled_width = int(1200 * self.dpi_scaling_factor)
        scaled_height = int(600 * self.dpi_scaling_factor)
        self.root.geometry(f"{scaled_width}x{scaled_height}")

    def _initialize_ui_components(self) -> None:
        """Initialize UI components with proper scaling."""
        # Initialize frames
        self.top_frame = ttk.Frame(self.main_frame, height=int(IMAGE_HEIGHT_PX * self.dpi_scaling_factor))

        # Initialize instruction label
        instruction_text = self._get_instruction_text()
        font_family, font_size = get_widget_font_family_and_size(self.main_frame)
        scaled_font_size = self.calculate_scaled_font_size(font_size)
        self.instruction_label = ttk.Label(self.top_frame, text=instruction_text, font=(font_family, scaled_font_size))

        # Initialize image label
        self.image_label = ttk.Label(self.top_frame)

        # Initialize treeview
        columns = TemplateOverview.columns()
        self.tree = ttk.Treeview(self.main_frame, columns=columns, show="headings")

    def _get_instruction_text(self) -> str:
        """Get the instruction text for the user interface."""
        instruction_text = _("Please double-click the template below that most resembles your own vehicle components")
        instruction_text += _("\nit does not need to exactly match your vehicle's components.")
        return instruction_text

    def _setup_layout(self) -> None:
        """Setup the layout of UI components."""
        # Pack top frame
        self.top_frame.pack(side=tk.TOP, fill="x", expand=False)

        # Pack instruction label
        scaled_pady = self.calculate_scaled_padding_tuple(10, 20)
        self.instruction_label.pack(side=tk.LEFT, pady=scaled_pady)

        # Pack image label
        scaled_padx = self.calculate_scaled_padding_tuple(20, 20)
        scaled_pady_value = int(IMAGE_HEIGHT_PX * self.dpi_scaling_factor / 2)
        self.image_label.pack(side=tk.RIGHT, anchor=tk.NE, padx=scaled_padx, pady=scaled_pady_value)

    def run_app(self) -> None:
        """Run the TemplateOverviewWindow application."""
        if isinstance(self.root, tk.Toplevel):
            try:
                while self.root.children:
                    self.root.update_idletasks()
                    self.root.update()
            except tk.TclError as _exp:
                pass
        elif isinstance(self.root, tk.Tk):
            self.root.mainloop()

    def _configure_treeview(self, connected_fc_vehicle_type: str) -> None:
        """Configure the treeview with styling and data."""
        self._setup_treeview_style()
        self._setup_treeview_columns()
        self._populate_treeview(connected_fc_vehicle_type)
        self._adjust_treeview_column_widths()
        self.tree.pack(fill=tk.BOTH, expand=True)

    def _setup_treeview_style(self) -> None:
        """Setup treeview styling with DPI scaling."""
        style = ttk.Style(self.root)
        # Add padding to Treeview heading style
        style.layout(  # type: ignore[no-untyped-call]
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
        # Scale padding for HiDPI displays
        scaled_padding = [
            self.calculate_scaled_padding(2),
            self.calculate_scaled_padding(2),
            self.calculate_scaled_padding(2),
            self.calculate_scaled_padding(18),
        ]
        style.configure("Treeview.Heading", padding=scaled_padding, justify="center")  # type: ignore[no-untyped-call]

    def _setup_treeview_columns(self) -> None:
        """Setup treeview column headers."""
        for col in self.tree["columns"]:
            self.tree.heading(col, text=col)

    def _populate_treeview(self, connected_fc_vehicle_type: str) -> None:
        """
        Populate the treeview with data from vehicle components.

        Args:
            connected_fc_vehicle_type: Optional firmware type to filter templates by

        """
        for key, template_overview in self.vehicle_components_provider.get_vehicle_components_overviews().items():
            attribute_names = template_overview.attributes()
            values = (key, *(getattr(template_overview, attr, "") for attr in attribute_names))
            if connected_fc_vehicle_type and not key.startswith(connected_fc_vehicle_type):
                continue
            self.tree.insert("", "end", text=key, values=values)

    def _adjust_treeview_column_widths(self) -> None:
        """Adjusts the column widths of the Treeview to fit the contents of each column."""
        for col in self.tree["columns"]:
            max_width = 0
            # Create a font object that matches the Treeview's font and scale for HiDPI
            tree_font = tkfont.Font()
            for subtitle in col.title().split("\n"):
                scaled_width = int(tree_font.measure(subtitle) * self.dpi_scaling_factor)
                max_width = max(max_width, scaled_width)

            # Iterate over all rows and update the max_width if a wider entry is found
            for item in self.tree.get_children():
                item_text = self.tree.item(item, "values")[self.tree["columns"].index(col)]
                scaled_text_width = int(tree_font.measure(item_text) * self.dpi_scaling_factor)
                max_width = max(max_width, scaled_text_width)

            # Update the column's width property to accommodate the largest text width
            # Scale the padding and multiplication factor for HiDPI
            scaled_padding = int(10 * self.dpi_scaling_factor)
            self.tree.column(col, width=int(max_width * 0.6 + scaled_padding))

    def _bind_events(self) -> None:
        """Bind events to the treeview."""
        self.tree.bind("<ButtonRelease-1>", self._on_row_selection_change)
        self.tree.bind("<Up>", self._on_row_selection_change)
        self.tree.bind("<Down>", self._on_row_selection_change)
        self.tree.bind("<Double-1>", self._on_row_double_click)

        for col in self.tree["columns"]:
            col_str = str(col)
            self.tree.heading(
                col_str,
                text=col_str,
                command=lambda col2=col_str: self._sort_by_column(col2, reverse=False),  # type: ignore[misc]
            )

    def _on_row_selection_change(self, _event: tk.Event) -> None:
        """Handle row single-click event."""
        self.root.after(0, self._update_selection)

    def _update_selection(self) -> None:
        """Update selection after keypress event."""
        selected_item = self.tree.selection()
        if selected_item:
            item_id = selected_item[0]
            selected_template_relative_path = self.tree.item(item_id)["text"]
            self.store_template_dir(selected_template_relative_path)
            self._display_vehicle_image(selected_template_relative_path)

    def store_template_dir(self, template_path: str) -> None:
        """
        Store the selected template directory.

        This method is separated from the UI event handler to improve testability.

        Args:
            template_path: The path to store

        """
        self.program_settings_provider.store_template_dir(template_path)

    def _on_row_double_click(self, event: tk.Event) -> None:
        """Handle row double-click event."""
        item_id = self.tree.identify_row(event.y)
        if item_id:
            selected_template_relative_path = self.tree.item(item_id)["text"]
            self.store_template_dir(selected_template_relative_path)
            self.close_window()

    def close_window(self) -> None:
        """Close the window - separated for testability."""
        self.root.destroy()

    def _sort_by_column(self, col: str, reverse: bool) -> None:
        """Sort treeview items by the specified column."""
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
        self.tree.heading(col, command=lambda: self._sort_by_column(col, not reverse))

    def _display_vehicle_image(self, template_path: str) -> None:
        """Display the vehicle image corresponding to the selected template."""
        # Delete the previous image
        for widget in self.top_frame.winfo_children():
            if isinstance(widget, ttk.Label) and widget == self.image_label:
                widget.destroy()
        try:
            vehicle_image_filepath = self.get_vehicle_image_filepath(template_path)
            self.image_label = self.put_image_in_label(self.top_frame, vehicle_image_filepath, IMAGE_HEIGHT_PX)
        except FileNotFoundError:
            scaled_padding = int(((IMAGE_HEIGHT_PX / 2) - 5.5) * self.dpi_scaling_factor)
            self.image_label = ttk.Label(
                self.top_frame,
                text=_("No 'vehicle.jpg' image file in the vehicle template directory."),
                padding=scaled_padding,
            )
        # Scale padding for HiDPI displays
        scaled_padx = (int(4 * self.dpi_scaling_factor), 0)
        self.image_label.pack(side=tk.RIGHT, anchor=tk.NE, padx=scaled_padx, pady=(0, 0))

    def get_vehicle_image_filepath(self, template_path: str) -> str:
        """
        Get the filepath for a vehicle image.

        Separated from display method for testability.

        Args:
            template_path: Path to the template

        Returns:
            Path to the vehicle image

        Raises:
            FileNotFoundError: If the image file doesn't exist

        """
        return self.vehicle_components_provider.get_vehicle_image_filepath(template_path)


def argument_parser() -> argparse.Namespace:
    """
    Parses command-line arguments for the script.

    This function sets up an argument parser to handle the command-line arguments for the script.

    Returns:
    argparse.Namespace: An object containing the parsed arguments.

    """
    parser = argparse.ArgumentParser(
        description=_(
            "ArduPilot Template Overview - A component of the ArduPilot Methodic Configurator suite. "
            "This tool presents available vehicle templates in a user-friendly interface, allowing you "
            "to browse, compare, and select the most appropriate template for your vehicle configuration. "
            "Select a template that most closely resembles your vehicle's component setup to streamline "
            "the configuration process. The selected template will serve as a starting point for more "
            "detailed parameter configuration."
        )
    )
    return add_common_arguments(parser).parse_args()


def setup_logging(loglevel: str) -> None:
    """
    Set up logging with the specified log level.

    Args:
        loglevel: The log level as a string (e.g. 'DEBUG', 'INFO')

    """
    logging_basicConfig(level=logging_getLevelName(loglevel), format="%(asctime)s - %(levelname)s - %(message)s")


def main() -> None:
    """Main entry point for the application."""
    args = argument_parser()
    setup_logging(args.loglevel)

    window = TemplateOverviewWindow()
    window.run_app()

    if window and ProgramSettings.get_recently_used_dirs():
        logging_info(ProgramSettings.get_recently_used_dirs()[0])


if __name__ == "__main__":
    main()
