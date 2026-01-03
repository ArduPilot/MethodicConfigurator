#!/usr/bin/env python3

"""
GUI to create the directory to store the vehicle configuration files.

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
from logging import info as logging_info
from logging import warning as logging_warning
from sys import exit as sys_exit
from tkinter import messagebox, ttk
from typing import Optional

from ardupilot_methodic_configurator import _, __version__
from ardupilot_methodic_configurator.backend_filesystem import LocalFilesystem
from ardupilot_methodic_configurator.common_arguments import add_common_arguments
from ardupilot_methodic_configurator.data_model_vehicle_project import VehicleProjectManager
from ardupilot_methodic_configurator.data_model_vehicle_project_creator import (
    NewVehicleProjectSettings,
    VehicleProjectCreationError,
)
from ardupilot_methodic_configurator.frontend_tkinter_base_window import BaseWindow
from ardupilot_methodic_configurator.frontend_tkinter_directory_selection import (
    DirectorySelectionWidgets,
    PathEntryWidget,
)
from ardupilot_methodic_configurator.frontend_tkinter_show import show_tooltip
from ardupilot_methodic_configurator.frontend_tkinter_template_overview import TemplateOverviewWindow


class VehicleProjectCreatorWindow(BaseWindow):
    """
    Window for creating a new vehicle project directory using a template and user-defined settings.

    Dynamically builds the GUI based on available settings, allowing users to select source template,
    destination directory, and project options. Integrates with VehicleProjectManager for project creation.
    """

    def __init__(self, project_manager: VehicleProjectManager) -> None:
        super().__init__()
        self.project_manager = project_manager
        self.root.title(
            _("Amilcar Lucas's - ArduPilot methodic configurator ")
            + __version__
            + _(" - Create a new vehicle project directory")
        )

        fc_connected = project_manager.is_flight_controller_connected()
        fc_parameters = project_manager.fc_parameters()

        # Initialize settings variables dynamically from data model
        self.new_project_settings_vars: dict[str, tk.BooleanVar] = {}
        self.new_project_settings_widgets: dict[str, ttk.Checkbutton] = {}

        template_dir, new_base_dir, vehicle_dir = self.project_manager.get_recently_used_dirs()
        logging_debug("template_dir: %s", template_dir)  # this string is intentionally left untranslated
        logging_debug("new_base_dir: %s", new_base_dir)  # this string is intentionally left untranslated
        logging_debug("vehicle_dir: %s", vehicle_dir)  # this string is intentionally left untranslated
        self.create_option1_widgets(
            template_dir,
            new_base_dir,
            self.project_manager.get_default_vehicle_name(),
            fc_connected,
            fc_parameters,
            project_manager.get_vehicle_type(),
        )

        # Bind the close_connection_and_quit function to the window close event
        self.root.protocol("WM_DELETE_WINDOW", self.close_and_quit)

    def close_and_quit(self) -> None:
        sys_exit(0)

    def create_option1_widgets(  # pylint: disable=too-many-locals,too-many-arguments,too-many-positional-arguments
        self,
        initial_template_dir: str,
        initial_base_dir: str,
        initial_new_dir: str,
        fc_connected: bool,
        fc_parameters: Optional[dict[str, float]],
        connected_fc_vehicle_type: str,
    ) -> None:
        # Option 1 - Create a new vehicle configuration directory based on an existing template
        option1_label = ttk.Label(text=_("New vehicle"), style="Bold.TLabel")
        option1_label_frame = ttk.LabelFrame(self.main_frame, labelwidget=option1_label)
        option1_label_frame.pack(expand=True, fill=tk.X, padx=6, pady=6)
        template_dir_edit_tooltip = _(
            "Existing vehicle template directory containing the intermediate\n"
            "parameter files to be copied to the new vehicle configuration directory"
        )
        template_dir_btn_tooltip = _(
            "Select the existing vehicle template directory containing the intermediate\n"
            "parameter files to be copied to the new vehicle configuration directory"
        )

        def template_selection_callback(_widget: "DirectorySelectionWidgets") -> str:
            # Template selection logic
            if isinstance(self.root, tk.Tk):  # this keeps mypy and pyright happy
                to = TemplateOverviewWindow(self.root, connected_fc_vehicle_type=connected_fc_vehicle_type)
                to.run_app()
            # Get recently used template directory from project manager
            template_dir, _nbd, _vd = self.project_manager.get_recently_used_dirs()
            logging_info(_("Selected template directory: %s"), template_dir)
            return template_dir

        self.template_dir = DirectorySelectionWidgets(
            parent=self,
            parent_frame=option1_label_frame,
            initialdir=initial_template_dir,
            label_text=_("Source Template directory:"),
            autoresize_width=False,
            dir_tooltip=template_dir_edit_tooltip,
            button_tooltip=template_dir_btn_tooltip,
            on_directory_selected_callback=template_selection_callback,
        )
        self.template_dir.container_frame.pack(expand=False, fill=tk.X, padx=3, pady=5, anchor=tk.NW)

        # Create checkboxes dynamically from settings metadata
        settings_metadata = NewVehicleProjectSettings.get_all_settings_metadata(fc_connected, fc_parameters)
        new_project_settings_default_values = NewVehicleProjectSettings.get_default_values()
        for setting_name in settings_metadata:
            default_value = new_project_settings_default_values.get(setting_name, False)
            self.new_project_settings_vars[setting_name] = tk.BooleanVar(value=default_value)

        # Set dynamic window size based on number of settings
        window_height = 250 + (len(settings_metadata) * 23)
        self.root.geometry(f"800x{window_height}")  # Set the window size

        for setting_name, metadata in settings_metadata.items():
            checkbox = ttk.Checkbutton(
                option1_label_frame,
                variable=self.new_project_settings_vars[setting_name],
                text=metadata.label,
                state=tk.NORMAL if metadata.enabled else tk.DISABLED,
            )
            checkbox.pack(anchor=tk.NW)
            show_tooltip(checkbox, metadata.tooltip)
            self.new_project_settings_widgets[setting_name] = checkbox

        new_base_dir_edit_tooltip = _("Existing directory where the new vehicle configuration directory will be created")
        new_base_dir_btn_tooltip = _("Select the directory where the new vehicle configuration directory will be created")
        self.new_base_dir = DirectorySelectionWidgets(
            parent=self,
            parent_frame=option1_label_frame,
            initialdir=initial_base_dir,
            label_text=_("Destination base directory:"),
            autoresize_width=False,
            dir_tooltip=new_base_dir_edit_tooltip,
            button_tooltip=new_base_dir_btn_tooltip,
            on_directory_selected_callback=None,  # Use default file dialog behavior
        )
        self.new_base_dir.container_frame.pack(expand=False, fill=tk.X, padx=3, pady=5, anchor=tk.NW)
        new_dir_edit_tooltip = _(
            "A new vehicle configuration directory with this name will be created at the (destination) base directory"
        )
        self.new_dir = PathEntryWidget(
            option1_label_frame, initial_new_dir, _("Destination new vehicle name:"), new_dir_edit_tooltip
        )
        self.new_dir.container_frame.pack(expand=False, fill=tk.X, padx=3, pady=5, anchor=tk.NW)
        create_vehicle_directory_from_template_button = ttk.Button(
            option1_label_frame,
            text=_("Create vehicle configuration directory from template"),
            command=self.create_new_vehicle_from_template,
        )
        create_vehicle_directory_from_template_button.pack(expand=False, fill=tk.X, padx=20, pady=5, anchor=tk.CENTER)
        show_tooltip(
            create_vehicle_directory_from_template_button,
            _(
                "Create a new vehicle configuration directory on the (destination) base directory,\n"
                "copy the template files from the (source) template directory to it and\n"
                "load the newly created files into the application"
            ),
        )

    def create_new_vehicle_from_template(self) -> None:
        # Get the selected template directory and new vehicle configuration directory name
        template_dir = self.template_dir.get_selected_directory()
        new_base_dir = self.new_base_dir.get_selected_directory()
        new_vehicle_name = self.new_dir.get_selected_directory()

        # Create settings object from GUI state using dynamic settings
        settings_kwargs = {}
        for setting_name, var in self.new_project_settings_vars.items():
            settings_kwargs[setting_name] = var.get()
        settings = NewVehicleProjectSettings(**settings_kwargs)

        # Create the vehicle project
        try:
            self.project_manager.create_new_vehicle_from_template(template_dir, new_base_dir, new_vehicle_name, settings)
            self.root.destroy()
        except VehicleProjectCreationError as e:
            messagebox.showerror(e.title, e.message)


# pylint: disable=duplicate-code
def argument_parser() -> Namespace:
    """
    Set up and parse command-line arguments for development/testing purposes.

    Returns:
        argparse.Namespace: Parsed arguments.

    """
    parser = ArgumentParser(
        description=_(
            "This main is for testing and development only. "
            "Usually, the VehicleProjectCreatorWindow is called from another script"
        )
    )
    parser = LocalFilesystem.add_argparse_arguments(parser)
    return add_common_arguments(parser).parse_args()


def main() -> None:
    args = argument_parser()

    logging_basicConfig(level=logging_getLevelName(args.loglevel), format="%(asctime)s - %(levelname)s - %(message)s")

    logging_warning(
        _(
            "This main is for testing and development only, usually the VehicleProjectCreatorWindow is"
            " called from another script"
        )
    )

    local_filesystem = LocalFilesystem(
        args.vehicle_dir, args.vehicle_type, "", args.allow_editing_template_files, args.save_component_to_system_templates
    )

    # Create project manager with the local filesystem
    project_manager = VehicleProjectManager(local_filesystem)

    # Get the list of intermediate parameter files to be processed
    files = project_manager.get_file_parameters_list()

    if not files:
        logging_error(_("No intermediate parameter files found in %s."), args.vehicle_dir)

    window = VehicleProjectCreatorWindow(project_manager)
    window.root.mainloop()


# pylint: enable=duplicate-code


if __name__ == "__main__":
    main()
