#!/usr/bin/env python3

"""
GUI to select the directory to store the vehicle configuration files.

This file is part of Ardupilot methodic configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2025 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import tkinter as tk
from argparse import ArgumentParser, Namespace
from copy import deepcopy
from logging import basicConfig as logging_basicConfig
from logging import debug as logging_debug
from logging import error as logging_error
from logging import getLevelName as logging_getLevelName
from logging import info as logging_info
from logging import warning as logging_warning
from sys import exit as sys_exit
from tkinter import filedialog, messagebox, ttk
from typing import Union

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
from ardupilot_methodic_configurator.frontend_tkinter_show import show_tooltip
from ardupilot_methodic_configurator.frontend_tkinter_template_overview import TemplateOverviewWindow


class DirectorySelectionWidgets:  # pylint: disable=too-many-instance-attributes
    """
    A class to manage directory selection widgets in the GUI.

    This class provides functionality for creating and managing widgets related to directory selection,
    including a label, an entry field for displaying the selected directory, and a button for opening a
    directory selection dialog.
    """

    def __init__(  # pylint: disable=too-many-arguments, too-many-positional-arguments
        self,
        parent: Union[BaseWindow, "VehicleDirectorySelectionWindow"],
        parent_frame: tk.Widget,
        initialdir: str,
        label_text: str,
        autoresize_width: bool,
        dir_tooltip: str,
        button_tooltip: str,
        is_template_selection: bool,
        connected_fc_vehicle_type: str,
    ) -> None:
        self.parent = parent
        self.directory: str = deepcopy(initialdir)
        self.label_text = label_text
        self.autoresize_width = autoresize_width
        self.is_template_selection = is_template_selection
        self.connected_fc_vehicle_type = connected_fc_vehicle_type

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
        self.directory_entry = tk.Entry(directory_selection_subframe, textvariable=dir_var, state="readonly")
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
        if self.is_template_selection:
            if isinstance(self.parent.root, tk.Tk):  # this keeps mypy and pyright happy
                to = TemplateOverviewWindow(self.parent.root, connected_fc_vehicle_type=self.connected_fc_vehicle_type)
                to.run_app()
            if isinstance(self.parent, VehicleDirectorySelectionWindow):
                selected_directory = self.parent.project_manager.get_recently_used_dirs()[0]
            else:
                selected_directory = ""
            logging_info(_("Selected template directory: %s"), selected_directory)
        else:
            title = _("Select {self.label_text}")
            selected_directory = filedialog.askdirectory(initialdir=self.directory, title=title.format(**locals()))

        if selected_directory:
            if self.autoresize_width:
                # Set the width of the directory_entry to match the width of the selected_directory text
                self.directory_entry.config(width=max(4, len(selected_directory)), state="normal")
            else:
                self.directory_entry.config(state="normal")
            self.directory_entry.delete(0, tk.END)
            self.directory_entry.insert(0, selected_directory)
            self.directory_entry.config(state="readonly")
            self.parent.root.update_idletasks()
            self.directory = selected_directory
            return True
        return False

    def get_selected_directory(self) -> str:
        return self.directory


class DirectoryNameWidgets:  # pylint: disable=too-few-public-methods
    """
    A class to manage directory name selection widgets in the GUI.

    This class provides functionality for creating and managing widgets related to directory name selection,
    including a label and an entry field for displaying the selected directory name.
    """

    def __init__(self, master: ttk.Labelframe, initial_dir: str, label_text: str, dir_tooltip: str) -> None:
        # Create a new frame for the directory name selection label
        self.container_frame = ttk.Frame(master)

        # Create a description label for the directory name entry
        directory_selection_label = ttk.Label(self.container_frame, text=label_text)
        directory_selection_label.pack(side=tk.TOP, anchor=tk.NW)
        show_tooltip(directory_selection_label, dir_tooltip)

        # Create an entry for the directory
        self.dir_var = tk.StringVar(value=initial_dir)
        directory_entry = ttk.Entry(self.container_frame, textvariable=self.dir_var, width=max(4, len(initial_dir)))
        directory_entry.pack(side=tk.LEFT, fill="x", expand=True, anchor=tk.NW, pady=(4, 0))
        show_tooltip(directory_entry, dir_tooltip)

    def get_selected_directory(self) -> str:
        return self.dir_var.get()


class VehicleDirectorySelectionWidgets(DirectorySelectionWidgets):
    """
    A subclass of DirectorySelectionWidgets specifically tailored for selecting vehicle directories.

    This class extends the functionality of DirectorySelectionWidgets to handle vehicle-specific
    directory selections. It includes additional logic for updating the local filesystem with the
    selected vehicle directory and re-initializing the filesystem with the new directory.
    """

    def __init__(  # pylint: disable=too-many-arguments, too-many-positional-arguments
        self,
        parent: Union[BaseWindow, "VehicleDirectorySelectionWindow"],
        parent_frame: ttk.Widget,
        initial_dir: str,
        destroy_parent_on_open: bool,
        connected_fc_vehicle_type: str = "",
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
            is_template_selection=False,
            connected_fc_vehicle_type=connected_fc_vehicle_type,
        )
        self.destroy_parent_on_open = destroy_parent_on_open

    def on_select_directory(self) -> bool:
        # Call the base class method to open the directory selection dialog
        if super().on_select_directory():
            try:
                if isinstance(self.parent, VehicleDirectorySelectionWindow):
                    self.parent.project_manager.open_vehicle_directory(self.directory)
                if self.destroy_parent_on_open:
                    self.parent.root.destroy()
                return True
            except VehicleProjectOpenError as e:
                messagebox.showerror(e.title, e.message)
                return False
        return False


class VehicleDirectorySelectionWindow(BaseWindow):  # pylint: disable=too-many-instance-attributes
    """
    A window for selecting a vehicle directory with intermediate parameter files.

    This class extends the BaseWindow class to provide a graphical user interface
    for selecting a vehicle directory that contains intermediate parameter files
    for ArduPilot. It allows the user to choose between creating a new vehicle
    configuration directory based on an existing template or using an existing
    vehicle configuration directory.
    """

    def __init__(
        self, project_manager: VehicleProjectManager, fc_connected: bool = False, connected_fc_vehicle_type: str = ""
    ) -> None:
        super().__init__()
        self.project_manager = project_manager
        self.connected_fc_vehicle_type = connected_fc_vehicle_type
        self.root.title(
            _("Amilcar Lucas's - ArduPilot methodic configurator ")
            + __version__
            + _(" - Select vehicle configuration directory")
        )

        # Initialize settings variables dynamically from data model
        self.new_project_settings_vars: dict[str, tk.BooleanVar] = {}
        self.new_project_settings_widgets: dict[str, ttk.Checkbutton] = {}
        new_project_settings_metadata = NewVehicleProjectSettings.get_all_settings_metadata(fc_connected)
        new_project_settings_default_values = NewVehicleProjectSettings.get_default_values()
        for setting_name in new_project_settings_metadata:
            default_value = new_project_settings_default_values.get(setting_name, False)
            self.new_project_settings_vars[setting_name] = tk.BooleanVar(value=default_value)

        # Set dynamic window size based on number of settings
        nr_new_project_settings = len(new_project_settings_metadata)
        window_height = 550 + (nr_new_project_settings * 21)
        self.root.geometry(f"800x{window_height}")  # Set the window size

        # Explain why we are here
        introduction_text = self.project_manager.get_introduction_message()
        introduction_label = ttk.Label(
            self.main_frame,
            anchor=tk.CENTER,
            justify=tk.CENTER,
            text=introduction_text + _("\nChoose one of the following three options:"),
        )
        introduction_label.pack(expand=False, fill=tk.X, padx=6, pady=6)
        template_dir, new_base_dir, vehicle_dir = self.project_manager.get_recently_used_dirs()
        logging_debug("template_dir: %s", template_dir)  # this string is intentionally left untranslated
        logging_debug("new_base_dir: %s", new_base_dir)  # this string is intentionally left untranslated
        logging_debug("vehicle_dir: %s", vehicle_dir)  # this string is intentionally left untranslated
        self.create_option1_widgets(
            template_dir,
            new_base_dir,
            self.project_manager.get_default_vehicle_name(),
            fc_connected,
            connected_fc_vehicle_type,
        )
        self.create_option2_widgets(vehicle_dir)
        self.create_option3_widgets(vehicle_dir)

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
        self.template_dir = DirectorySelectionWidgets(
            parent=self,
            parent_frame=option1_label_frame,
            initialdir=initial_template_dir,
            label_text=_("Source Template directory:"),
            autoresize_width=False,
            dir_tooltip=template_dir_edit_tooltip,
            button_tooltip=template_dir_btn_tooltip,
            is_template_selection=True,
            connected_fc_vehicle_type=connected_fc_vehicle_type,
        )
        self.template_dir.container_frame.pack(expand=False, fill=tk.X, padx=3, pady=5, anchor=tk.NW)

        # Create checkboxes dynamically from settings metadata
        settings_metadata = NewVehicleProjectSettings.get_all_settings_metadata(fc_connected)
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
            is_template_selection=False,
            connected_fc_vehicle_type="",
        )
        self.new_base_dir.container_frame.pack(expand=False, fill=tk.X, padx=3, pady=5, anchor=tk.NW)
        new_dir_edit_tooltip = _(
            "A new vehicle configuration directory with this name will be created at the (destination) base directory"
        )
        self.new_dir = DirectoryNameWidgets(
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
        self.connection_selection_widgets = VehicleDirectorySelectionWidgets(
            self,
            option2_label_frame,
            initial_dir,
            destroy_parent_on_open=True,
            connected_fc_vehicle_type=self.connected_fc_vehicle_type,
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
            is_template_selection=False,
            connected_fc_vehicle_type="",
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

    def open_last_vehicle_directory(self, last_vehicle_dir: str) -> None:
        # Attempt to open the last opened vehicle configuration directory
        try:
            self.project_manager.open_last_vehicle_directory(last_vehicle_dir)
            self.root.destroy()
        except VehicleProjectOpenError as e:
            messagebox.showerror(e.title, e.message)


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
            "Usually, the VehicleDirectorySelectionWindow is called from another script"
        )
    )
    parser = LocalFilesystem.add_argparse_arguments(parser)
    return add_common_arguments(parser).parse_args()


# pylint: disable=duplicate-code
def main() -> None:
    args = argument_parser()

    logging_basicConfig(level=logging_getLevelName(args.loglevel), format="%(asctime)s - %(levelname)s - %(message)s")

    logging_warning(
        _(
            "This main is for testing and development only, usually the VehicleDirectorySelectionWindow is"
            " called from another script"
        )
    )
    # pylint: enable=duplicate-code

    local_filesystem = LocalFilesystem(
        args.vehicle_dir, args.vehicle_type, "", args.allow_editing_template_files, args.save_component_to_system_templates
    )

    # Create project manager with the local filesystem
    project_manager = VehicleProjectManager(local_filesystem)

    # Get the list of intermediate parameter files files that will be processed sequentially
    files = project_manager.get_file_parameters_list()

    if not files:
        logging_error(_("No intermediate parameter files found in %s."), args.vehicle_dir)

    window = VehicleDirectorySelectionWindow(project_manager)
    window.root.mainloop()


if __name__ == "__main__":
    main()
