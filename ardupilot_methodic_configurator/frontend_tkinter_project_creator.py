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

from ardupilot_methodic_configurator import _, __version__
from ardupilot_methodic_configurator.backend_filesystem import LocalFilesystem
from ardupilot_methodic_configurator.common_arguments import add_common_arguments
from ardupilot_methodic_configurator.data_model_vehicle_project import VehicleProjectManager
from ardupilot_methodic_configurator.data_model_vehicle_project_creator import (
    NewVehicleProjectSettings,
    VehicleProjectCreationError,
)
from ardupilot_methodic_configurator.data_model_vehicle_project_opener import VehicleProjectOpenError
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

    def __init__(self, project_manager: VehicleProjectManager, from_flight_controller: bool = False) -> None:
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
        # Created only for the regular template workflow; initialize the attribute here so
        # static analysis also recognizes it when the flight-controller workflow is used.
        self.template_dir: DirectorySelectionWidgets

        recent_template_dir, new_base_dir, vehicle_dir = self.project_manager.get_recently_used_dirs()
        template_dir = (
            self.project_manager.get_fc_default_template_dir()
            if fc_connected and not from_flight_controller
            else recent_template_dir
        )
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
            from_flight_controller=from_flight_controller,
        )

        # Bind the close_connection_and_quit function to the window close event
        self.root.protocol("WM_DELETE_WINDOW", self.close_and_quit)

    def close_and_quit(self) -> None:
        sys_exit(0)

    def create_option1_widgets(  # pylint: disable=too-many-arguments,too-many-positional-arguments
        self,
        initial_template_dir: str,
        initial_base_dir: str,
        initial_new_dir: str,
        fc_connected: bool,
        fc_parameters: dict[str, float] | None,
        connected_fc_vehicle_type: str,
        from_flight_controller: bool = False,
    ) -> None:
        option1_label = ttk.Label(
            self.main_frame,
            text=_("New vehicle"),
            style="Bold.TLabel",
        )
        option1_label_frame = ttk.LabelFrame(self.main_frame, labelwidget=option1_label)
        option1_label_frame.pack(expand=True, fill=tk.X, padx=6, pady=6)

        if from_flight_controller:
            window_height = 200
        else:
            self._create_template_selection_widgets(option1_label_frame, initial_template_dir, connected_fc_vehicle_type)
            window_height = self._create_settings_widgets(option1_label_frame, fc_connected, fc_parameters)
        self.root.geometry(self.calculate_scaled_geometry(800, window_height))  # Set the window size

        self.center_window_on_screen(self.root)
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
        create_vehicle_button = ttk.Button(
            option1_label_frame,
            text=(
                _("Create a vehicle project from an already configured flight controller")
                if from_flight_controller
                else _("Create a vehicle project from a template")
            ),
            command=(
                self.create_new_vehicle_from_flight_controller
                if from_flight_controller
                else self.create_new_vehicle_from_template
            ),
        )
        create_vehicle_button.pack(expand=False, fill=tk.X, padx=20, pady=5, anchor=tk.CENTER)
        show_tooltip(
            create_vehicle_button,
            _(
                "Create a new vehicle configuration directory using the connected flight controller's\n"
                "parameters and component information."
            )
            if from_flight_controller
            else _(
                "Create a new vehicle configuration directory on the (destination) base directory,\n"
                "copy the template files from the (source) template directory to it and\n"
                "load the newly created files into the application"
            ),
        )

    def _create_template_selection_widgets(
        self, parent_frame: ttk.LabelFrame, initial_template_dir: str, connected_fc_vehicle_type: str
    ) -> None:
        """Create the template directory selector and its template overview callback."""
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
                to = TemplateOverviewWindow(
                    self.root,
                    connected_fc_vehicle_type=connected_fc_vehicle_type,
                    current_template_dir=_widget.get_selected_directory(),
                )
                to.run_app()
                if not to.user_made_selection:
                    # User closed the window without confirming - keep the current widget value
                    return _widget.get_selected_directory()
            # Get recently used template directory from project manager
            template_dir, _nbd, _vd = self.project_manager.get_recently_used_dirs()
            logging_info(_("Selected template directory: %s"), template_dir)
            return template_dir

        self.template_dir = DirectorySelectionWidgets(
            parent=self,
            parent_frame=parent_frame,
            initialdir=initial_template_dir,
            label_text=_("Source Template directory:"),
            autoresize_width=False,
            dir_tooltip=template_dir_edit_tooltip,
            button_tooltip=template_dir_btn_tooltip,
            on_directory_selected_callback=template_selection_callback,
        )
        self.template_dir.container_frame.pack(expand=False, fill=tk.X, padx=3, pady=5, anchor=tk.NW)

    def _create_settings_widgets(
        self, parent_frame: ttk.LabelFrame, fc_connected: bool, fc_parameters: dict[str, float] | None
    ) -> int:
        """Create the dynamic project-setting checkboxes and return the required window height."""
        settings_metadata = NewVehicleProjectSettings.get_all_settings_metadata(fc_connected, fc_parameters)
        new_project_settings_default_values = NewVehicleProjectSettings.get_default_values()
        for setting_name in settings_metadata:
            default_value = new_project_settings_default_values.get(setting_name, False)
            self.new_project_settings_vars[setting_name] = tk.BooleanVar(value=default_value)

        for setting_name, metadata in settings_metadata.items():
            checkbox = ttk.Checkbutton(
                parent_frame,
                variable=self.new_project_settings_vars[setting_name],
                text=metadata.label,
                state=tk.NORMAL if metadata.enabled else tk.DISABLED,
            )
            checkbox.pack(anchor=tk.NW)
            show_tooltip(checkbox, metadata.tooltip)
            self.new_project_settings_widgets[setting_name] = checkbox

        return 250 + (len(settings_metadata) * 23)

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
        except (VehicleProjectCreationError, VehicleProjectOpenError) as e:
            messagebox.showerror(e.title, e.message)

    def create_new_vehicle_from_flight_controller(self) -> None:
        """Create a vehicle project using the connected flight controller's configuration."""
        new_base_dir = self.new_base_dir.get_selected_directory()
        new_vehicle_name = self.new_dir.get_selected_directory()
        try:
            self.project_manager.create_new_vehicle_from_flight_controller(new_base_dir, new_vehicle_name)
            self.root.destroy()
        except (VehicleProjectCreationError, VehicleProjectOpenError) as e:
            messagebox.showerror(e.title, e.message)


# pylint: disable=duplicate-code
def argument_parser() -> Namespace:  # pragma: no cover
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


def main() -> None:  # pragma: no cover
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


if __name__ == "__main__":  # pragma: no cover
    main()
