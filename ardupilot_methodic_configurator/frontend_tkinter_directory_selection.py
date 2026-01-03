"""
GUI to select the directory to store the vehicle configuration files.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import tkinter as tk
from copy import deepcopy
from tkinter import filedialog, messagebox, ttk
from typing import Callable, Optional

from ardupilot_methodic_configurator import _
from ardupilot_methodic_configurator.data_model_vehicle_project_opener import VehicleProjectOpenError
from ardupilot_methodic_configurator.frontend_tkinter_base_window import BaseWindow
from ardupilot_methodic_configurator.frontend_tkinter_show import show_tooltip


class PathEntryWidget:  # pylint: disable=too-few-public-methods
    """
    A GUI widget for path entry and editing.

    Provides a labeled text entry field for entering or editing file/directory paths.
    """

    def __init__(self, master: ttk.Labelframe, initial_dir: str, label_text: str, dir_tooltip: str) -> None:
        # Create a new frame for the path entry widget
        self.container_frame = ttk.Frame(master)

        # Create a description label for the path entry
        path_label = ttk.Label(self.container_frame, text=label_text)
        path_label.pack(side=tk.TOP, anchor=tk.NW)
        show_tooltip(path_label, dir_tooltip)

        # Create an entry field for the path
        self.dir_var = tk.StringVar(value=initial_dir)
        path_entry = ttk.Entry(self.container_frame, textvariable=self.dir_var, width=max(4, len(initial_dir)))
        path_entry.pack(side=tk.LEFT, fill="x", expand=True, anchor=tk.NW, pady=(4, 0))
        show_tooltip(path_entry, dir_tooltip)

    def get_selected_directory(self) -> str:
        return self.dir_var.get()


class DirectorySelectionWidgets:
    """
    A class to manage directory selection widgets in the GUI.

    This class provides functionality for creating and managing widgets related to directory selection,
    including a label, an entry field for displaying the selected directory, and a button for opening a
    directory selection dialog.
    """

    def __init__(  # pylint: disable=too-many-arguments, too-many-positional-arguments
        self,
        parent: BaseWindow,
        parent_frame: tk.Widget,
        initialdir: str,
        label_text: str,
        autoresize_width: bool,
        dir_tooltip: str,
        button_tooltip: str,
        on_directory_selected_callback: Optional[Callable[["DirectorySelectionWidgets"], str]] = None,
    ) -> None:
        self.parent = parent
        self.directory: str = deepcopy(initialdir)
        self.label_text = label_text
        self.autoresize_width = autoresize_width
        self.on_directory_selected_callback = on_directory_selected_callback

        # Create a new frame for the directory selection label and button
        self.container_frame = ttk.Frame(parent_frame)

        # Create a description label for the directory
        directory_selection_label = ttk.Label(self.container_frame, text=label_text)
        directory_selection_label.pack(side=tk.TOP, anchor=tk.NW)
        show_tooltip(directory_selection_label, dir_tooltip)

        # Create a new subframe for the directory selection
        directory_selection_subframe = ttk.Frame(self.container_frame)
        directory_selection_subframe.pack(side=tk.TOP, fill="x", expand=False, anchor=tk.NW)

        # Create a read-only entry for the directory
        dir_var = tk.StringVar(value=self.directory)
        self.directory_entry = tk.Entry(
            directory_selection_subframe, textvariable=dir_var, state="readonly", foreground="black"
        )
        if autoresize_width:
            self.directory_entry.config(width=max(4, len(self.directory)))
        self.directory_entry.pack(side=tk.LEFT, fill="x", expand=True, anchor=tk.NW, pady=(4, 0))
        show_tooltip(self.directory_entry, dir_tooltip)

        if button_tooltip:
            # Create a button for directory selection
            directory_selection_button = ttk.Button(
                directory_selection_subframe, text="...", command=self.on_select_directory, width=2
            )
            directory_selection_button.pack(side=tk.RIGHT, anchor=tk.NW)
            show_tooltip(directory_selection_button, button_tooltip)
        else:
            self.directory_entry.xview_moveto(1.0)

    def on_select_directory(self) -> bool:
        # Use callback if provided, otherwise use default file dialog
        if self.on_directory_selected_callback:
            selected_directory = self.on_directory_selected_callback(self)
        else:
            # Default behavior - open file dialog
            title = _("Select {self.label_text}")
            selected_directory = filedialog.askdirectory(initialdir=self.directory, title=title.format(**locals()))

        if selected_directory:
            self.update_directory_display(selected_directory)
            return True
        return False

    def update_directory_display(self, selected_directory: str) -> None:
        """Update the directory display with the selected directory."""
        if self.autoresize_width:
            # Set the width of the directory_entry to match the width of the selected_directory text
            self.directory_entry.config(width=max(4, len(selected_directory)), state="normal")
        else:
            self.directory_entry.config(state="normal")
        self.directory_entry.delete(0, tk.END)
        self.directory_entry.insert(0, selected_directory)
        self.directory_entry.config(state="readonly")
        if hasattr(self.parent, "root"):
            self.parent.root.update_idletasks()
        self.directory = selected_directory

    def get_selected_directory(self) -> str:
        return self.directory


class VehicleDirectorySelectionWidgets(DirectorySelectionWidgets):
    """
    A subclass of DirectorySelectionWidgets specifically tailored for selecting vehicle directories.

    This class extends the functionality of DirectorySelectionWidgets to handle vehicle-specific
    directory selections. It includes additional logic for updating the local filesystem with the
    selected vehicle directory and re-initializing the filesystem with the new directory.
    """

    def __init__(  # pylint: disable=too-many-arguments, too-many-positional-arguments
        self,
        parent: BaseWindow,
        parent_frame: ttk.Widget,
        initial_dir: str,
        destroy_parent_on_open: bool,
        on_select_directory_callback: Optional[Callable[[str], None]] = None,
    ) -> None:
        # Call the parent constructor with the necessary arguments
        super().__init__(
            parent=parent,
            parent_frame=parent_frame,
            initialdir=initial_dir,
            label_text=_("Vehicle configuration directory:"),
            autoresize_width=False,
            dir_tooltip=_(
                "Vehicle-specific directory containing the intermediate\n"
                "parameter files to be uploaded to the flight controller"
            ),
            button_tooltip=_(
                "Select the vehicle-specific configuration directory containing the\n"
                "intermediate parameter files to be uploaded to the flight controller"
            )
            if destroy_parent_on_open
            else "",
        )
        self.destroy_parent_on_open = destroy_parent_on_open
        self.on_select_directory_callback = on_select_directory_callback

    def on_select_directory(self) -> bool:
        # Call the base class method to open the directory selection dialog
        if super().on_select_directory():
            try:
                # Execute the vehicle-specific callback function if provided
                if self.on_select_directory_callback:
                    self.on_select_directory_callback(self.directory)
                if self.destroy_parent_on_open and hasattr(self.parent, "root"):
                    self.parent.root.destroy()
                return True
            except VehicleProjectOpenError as e:
                messagebox.showerror(e.title, e.message)
                return False
        return False
