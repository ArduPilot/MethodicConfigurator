#!/usr/bin/env python3

"""
GUI to select the directory to store the vehicle configuration files.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import tkinter as tk
from argparse import ArgumentParser, Namespace
from logging import basicConfig as logging_basicConfig
from logging import debug as logging_debug
from logging import error as logging_error
from logging import getLevelName as logging_getLevelName
from logging import warning as logging_warning
from sys import exit as sys_exit
from tkinter import messagebox, ttk

from ardupilot_methodic_configurator import _, __version__
from ardupilot_methodic_configurator.backend_filesystem import LocalFilesystem
from ardupilot_methodic_configurator.common_arguments import add_common_arguments
from ardupilot_methodic_configurator.data_model_vehicle_project import VehicleProjectManager
from ardupilot_methodic_configurator.data_model_vehicle_project_opener import VehicleProjectOpenError
from ardupilot_methodic_configurator.frontend_tkinter_base_window import BaseWindow
from ardupilot_methodic_configurator.frontend_tkinter_directory_selection import (
    DirectorySelectionWidgets,
    VehicleDirectorySelectionWidgets,
)
from ardupilot_methodic_configurator.frontend_tkinter_project_creator import VehicleProjectCreatorWindow
from ardupilot_methodic_configurator.frontend_tkinter_show import show_tooltip


class VehicleProjectOpenerWindow(BaseWindow):
    """
    A window for selecting a vehicle directory with intermediate parameter files.

    This class extends the BaseWindow class to provide a graphical user interface
    for selecting a vehicle directory that contains intermediate parameter files
    for ArduPilot. It allows the user to choose between creating a new vehicle
    configuration directory based on an existing template or using an existing
    vehicle configuration directory.
    """

    # pylint: disable=duplicate-code
    def __init__(self, project_manager: VehicleProjectManager) -> None:
        super().__init__()
        self.project_manager = project_manager
        self.root.title(
            _("Amilcar Lucas's - ArduPilot methodic configurator ")
            + __version__
            + _(" - Select vehicle configuration directory")
        )

        self.root.geometry("600x450")  # Set the window size

        # Explain why we are here
        introduction_text = self.project_manager.get_introduction_message()
        introduction_label = ttk.Label(
            self.main_frame,
            anchor=tk.CENTER,
            justify=tk.CENTER,
            text=introduction_text + _("\nChoose one of the following three options:"),
        )
        introduction_label.pack(expand=False, fill=tk.X, padx=6, pady=6)
        _template_dir, _new_base_dir, vehicle_dir = self.project_manager.get_recently_used_dirs()
        logging_debug("vehicle_dir: %s", vehicle_dir)  # this string is intentionally left untranslated
        self.create_option1_widgets()
        self.create_option2_widgets(vehicle_dir)
        self.create_option3_widgets(vehicle_dir)

        # Bind the close_connection_and_quit function to the window close event
        self.root.protocol("WM_DELETE_WINDOW", self.close_and_quit)

    def close_and_quit(self) -> None:
        sys_exit(0)

    def create_option1_widgets(self) -> None:
        # Option 1 - Create a new vehicle configuration directory based on an existing template
        option1_label = ttk.Label(text=_("New vehicle"), style="Bold.TLabel")
        option1_label_frame = ttk.LabelFrame(self.main_frame, labelwidget=option1_label)
        option1_label_frame.pack(expand=True, fill=tk.X, padx=6, pady=6)

        create_vehicle_directory_from_template_button = ttk.Button(
            option1_label_frame,
            text=_("Create vehicle configuration directory from template"),
            command=self.create_new_vehicle_from_template,
        )
        create_vehicle_directory_from_template_button.pack(expand=False, fill=tk.X, padx=20, pady=5, anchor=tk.CENTER)
        show_tooltip(
            create_vehicle_directory_from_template_button,
            _("Create a new vehicle configuration directory"),
        )

    # pylint: enable=duplicate-code

    def create_option2_widgets(self, initial_dir: str) -> None:
        # Option 2 - Use an existing vehicle configuration directory
        option2_label = ttk.Label(text=_("Open vehicle"), style="Bold.TLabel")
        option2_label_frame = ttk.LabelFrame(self.main_frame, labelwidget=option2_label)
        option2_label_frame.pack(expand=True, fill=tk.X, padx=6, pady=6)
        option2_label = ttk.Label(
            option2_label_frame,
            anchor=tk.CENTER,
            justify=tk.CENTER,
            text=_(
                "Use an existing vehicle configuration directory with\n"
                "intermediate parameter files, apm.pdef.xml and vehicle_components.json"
            ),
        )
        option2_label.pack(expand=False, fill=tk.X, padx=6)

        def on_vehicle_directory_selected(directory: str) -> None:
            self.project_manager.open_vehicle_directory(directory)

        self.connection_selection_widgets = VehicleDirectorySelectionWidgets(
            self,
            option2_label_frame,
            initial_dir,
            destroy_parent_on_open=True,
            on_select_directory_callback=on_vehicle_directory_selected,
        )
        self.connection_selection_widgets.container_frame.pack(expand=True, fill=tk.X, padx=3, pady=5, anchor=tk.NW)

    def create_option3_widgets(self, last_vehicle_dir: str) -> None:
        # Option 3 - Open the last used vehicle configuration directory
        option3_label = ttk.Label(text=_("Re-Open vehicle"), style="Bold.TLabel")
        option3_label_frame = ttk.LabelFrame(self.main_frame, labelwidget=option3_label)
        option3_label_frame.pack(expand=True, fill=tk.X, padx=6, pady=6)

        last_dir = DirectorySelectionWidgets(
            parent=self,
            parent_frame=option3_label_frame,
            initialdir=last_vehicle_dir or "",
            label_text=_("Last used vehicle configuration directory:"),
            autoresize_width=False,
            dir_tooltip=_("Last used vehicle configuration directory"),
            button_tooltip="",
            on_directory_selected_callback=None,  # Use default file dialog behavior
        )
        last_dir.container_frame.pack(expand=False, fill=tk.X, padx=3, pady=5, anchor=tk.NW)

        # Check if there is a last used vehicle configuration directory
        button_state = tk.NORMAL if self.project_manager.can_open_last_vehicle_directory(last_vehicle_dir) else tk.DISABLED
        open_last_vehicle_directory_button = ttk.Button(
            option3_label_frame,
            text=_("Open Last Used Vehicle Configuration Directory"),
            command=lambda last_vehicle_dir=last_vehicle_dir: self.open_last_vehicle_directory(  # type: ignore[misc]
                last_vehicle_dir
            ),
            state=button_state,
        )
        open_last_vehicle_directory_button.pack(expand=False, fill=tk.X, padx=20, pady=5, anchor=tk.CENTER)
        show_tooltip(
            open_last_vehicle_directory_button,
            _("Directly open the last used vehicle configuration directory for configuring and tuning the vehicle"),
        )

    def create_new_vehicle_from_template(self) -> None:
        # close this window and open a VehicleProjectCreatorWindow instance
        self.root.destroy()
        VehicleProjectCreatorWindow(self.project_manager)

    def open_last_vehicle_directory(self, last_vehicle_dir: str) -> None:
        # Attempt to open the last opened vehicle configuration directory
        try:
            self.project_manager.open_last_vehicle_directory(last_vehicle_dir)
            self.root.destroy()
        except VehicleProjectOpenError as e:
            messagebox.showerror(e.title, e.message)


# pylint: disable=duplicate-code
def argument_parser() -> Namespace:
    """
    Parses command-line arguments for the script.

    This function sets up an argument parser to handle the command-line arguments for the script.

    Returns:
    argparse.Namespace: An object containing the parsed arguments.

    """
    parser = ArgumentParser(
        description=_(
            "This main is for testing and development only. "
            "Usually, the VehicleProjectOpenerWindow is called from another script"
        )
    )
    parser = LocalFilesystem.add_argparse_arguments(parser)
    return add_common_arguments(parser).parse_args()


def main() -> None:
    args = argument_parser()

    logging_basicConfig(level=logging_getLevelName(args.loglevel), format="%(asctime)s - %(levelname)s - %(message)s")

    logging_warning(
        _(
            "This main is for testing and development only, usually the VehicleProjectOpenerWindow is"
            " called from another script"
        )
    )

    local_filesystem = LocalFilesystem(
        args.vehicle_dir, args.vehicle_type, "", args.allow_editing_template_files, args.save_component_to_system_templates
    )

    # Create project manager with the local filesystem
    project_manager = VehicleProjectManager(local_filesystem)

    # Get the list of intermediate parameter files files that will be processed sequentially
    files = project_manager.get_file_parameters_list()

    if not files:
        logging_error(_("No intermediate parameter files found in %s."), args.vehicle_dir)

    window = VehicleProjectOpenerWindow(project_manager)
    window.root.mainloop()


# pylint: enable=duplicate-code


if __name__ == "__main__":
    main()
