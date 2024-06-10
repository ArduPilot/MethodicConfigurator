#!/usr/bin/env python3

'''
This file is part of Ardupilot methodic configurator. https://github.com/ArduPilot/MethodicConfigurator

(C) 2024 Amilcar do Carmo Lucas

SPDX-License-Identifier:    GPL-3
'''


from argparse import ArgumentParser

from sys import exit as sys_exit

from copy import deepcopy

from logging import basicConfig as logging_basicConfig
from logging import getLevelName as logging_getLevelName
from logging import warning as logging_warning
from logging import info as logging_info
from logging import debug as logging_error

import tkinter as tk
from tkinter import messagebox
from tkinter import ttk
from tkinter import filedialog

from MethodicConfigurator.version import VERSION

from MethodicConfigurator.common_arguments import add_common_arguments_and_parse

from MethodicConfigurator.backend_filesystem import LocalFilesystem

from MethodicConfigurator.frontend_tkinter_base import show_no_param_files_error
from MethodicConfigurator.frontend_tkinter_base import show_tooltip
from MethodicConfigurator.frontend_tkinter_base import BaseWindow

from MethodicConfigurator.frontend_tkinter_template_overview import TemplateOverviewWindow


class DirectorySelectionWidgets():
    """
    A class to manage directory selection widgets in the GUI.

    This class provides functionality for creating and managing widgets related to directory selection,
    including a label, an entry field for displaying the selected directory, and a button for opening a
    directory selection dialog.
    """
    def __init__(self, parent, parent_frame, initialdir: str, label_text: str,  # pylint: disable=too-many-arguments
                 autoresize_width: bool, dir_tooltip: str, button_tooltip: str,
                 local_filesystem: LocalFilesystem = None):
        self.parent = parent
        self.directory = deepcopy(initialdir)
        self.label_text = label_text
        self.autoresize_width = autoresize_width
        self.local_filesystem = local_filesystem

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
        self.directory_entry = tk.Entry(directory_selection_subframe, textvariable=dir_var, state='readonly')
        if autoresize_width:
            self.directory_entry.config(width=max(4, len(self.directory)))
        self.directory_entry.pack(side=tk.LEFT, fill="x", expand=True, anchor=tk.NW, pady=(4, 0))
        show_tooltip(self.directory_entry, dir_tooltip)

        if button_tooltip:
            # Create a button for directory selection
            directory_selection_button = ttk.Button(directory_selection_subframe, text="...",
                                                    command=self.on_select_directory, width=2)
            directory_selection_button.pack(side=tk.RIGHT, anchor=tk.NW)
            show_tooltip(directory_selection_button, button_tooltip)
        else:
            self.directory_entry.xview_moveto(1.0)

    def on_select_directory(self):
        if self.local_filesystem:
            TemplateOverviewWindow(self.parent.root, self.local_filesystem)
            selected_directory = self.local_filesystem.get_recently_used_dirs()[0]
            logging_info("Selected template directory: %s", selected_directory)
        else:
            selected_directory = filedialog.askdirectory(initialdir=self.directory, title=f"Select {self.label_text}")

        if selected_directory:
            if self.autoresize_width:
                # Set the width of the directory_entry to match the width of the selected_directory text
                self.directory_entry.config(width=max(4, len(selected_directory)), state='normal')
            else:
                self.directory_entry.config(state='normal')
            self.directory_entry.delete(0, tk.END)
            self.directory_entry.insert(0, selected_directory)
            self.directory_entry.config(state='readonly')
            self.parent.root.update_idletasks()
            self.directory = selected_directory
            return True
        return False

    def get_selected_directory(self):
        return self.directory


class DirectoryNameWidgets():  # pylint: disable=too-few-public-methods
    """
    A class to manage directory name selection widgets in the GUI.

    This class provides functionality for creating and managing widgets related to directory name selection,
    including a label and an entry field for displaying the selected directory name.
    """
    def __init__(self, parent_frame, initial_dir: str, label_text: str, dir_tooltip: str):
        # Create a new frame for the directory name selection label
        self.container_frame = ttk.Frame(parent_frame)

        # Create a description label for the directory name entry
        directory_selection_label = ttk.Label(self.container_frame, text=label_text)
        directory_selection_label.pack(side=tk.TOP, anchor=tk.NW)
        show_tooltip(directory_selection_label, dir_tooltip)

        # Create an entry for the directory
        self.dir_var = tk.StringVar(value=initial_dir)
        directory_entry = ttk.Entry(self.container_frame, textvariable=self.dir_var,
                                        width=max(4, len(initial_dir)))
        directory_entry.pack(side=tk.LEFT, fill="x", expand=True, anchor=tk.NW, pady=(4, 0))
        show_tooltip(directory_entry, dir_tooltip)

    def get_selected_directory(self):
        return self.dir_var.get()


class VehicleDirectorySelectionWidgets(DirectorySelectionWidgets):
    """
    A subclass of DirectorySelectionWidgets specifically tailored for selecting vehicle directories.
    This class extends the functionality of DirectorySelectionWidgets to handle vehicle-specific
    directory selections. It includes additional logic for updating the local filesystem with the
    selected vehicle directory and re-initializing the filesystem with the new directory.
    """
    def __init__(self, parent: ttk, parent_frame: ttk.Frame,  # pylint: disable=too-many-arguments
                 local_filesystem: LocalFilesystem,
                 initial_dir: str, destroy_parent_on_open: bool) -> None:
        # Call the parent constructor with the necessary arguments
        super().__init__(parent, parent_frame, initial_dir, "Vehicle configuration directory:",
                         False,
                         "Vehicle-specific directory containing the intermediate\n"
                         "parameter files to be uploaded to the flight controller",
                         "Select the vehicle-specific configuration directory containing the\n"
                         "intermediate parameter files to be uploaded to the flight controller" \
                            if destroy_parent_on_open else '')
        self.local_filesystem = local_filesystem
        self.destroy_parent_on_open = destroy_parent_on_open

    def on_select_directory(self):
        # Call the base class method to open the directory selection dialog
        if super().on_select_directory():
            if "vehicle_templates" in self.directory and not self.local_filesystem.allow_editing_template_files:
                messagebox.showerror("Invalid Vehicle Directory Selected",
                                     "Please do not edit the files provided 'vehicle_templates' directory\n"
                                     "as those are used as a template for new vehicles")
                return
            self.local_filesystem.vehicle_dir = self.directory

            try:
                self.local_filesystem.re_init(self.directory, self.local_filesystem.vehicle_type)
            except SystemExit as exp:
                messagebox.showerror("Fatal error reading parameter files", f"{exp}")
                raise

            files = list(self.local_filesystem.file_parameters.keys())
            if files:
                LocalFilesystem.store_recently_used_vehicle_dir(self.directory)
                if hasattr(self.parent, 'file_selection_combobox'):
                    # Update the file selection combobox with the new files
                    self.parent.file_selection_combobox.set_entries_tupple(files, files[0])
                    # Trigger the combobox change event to update the table
                    self.parent.on_param_file_combobox_change(None, forced=True)
                if self.destroy_parent_on_open:
                    self.parent.root.destroy()
            else:
                # No files were found in the selected directory
                show_no_param_files_error(self.directory)


class VehicleDirectorySelectionWindow(BaseWindow):
    """
    A window for selecting a vehicle directory with intermediate parameter files.

    This class extends the BaseWindow class to provide a graphical user interface
    for selecting a vehicle directory that contains intermediate parameter files
    for ArduPilot. It allows the user to choose between creating a new vehicle
    configuration directory based on an existing template or using an existing
    vehicle configuration directory.
    """
    def __init__(self, local_filesystem: LocalFilesystem, fc_connected: bool = False):
        super().__init__()
        self.local_filesystem = local_filesystem
        self.root.title("Amilcar Lucas's - ArduPilot methodic configurator " + VERSION + \
                        " - Select vehicle configuration directory")
        self.root.geometry("800x625") # Set the window size
        self.use_fc_params = tk.BooleanVar(value=False)
        self.created_new_vehicle_from_template = False

        # Explain why we are here
        if local_filesystem.vehicle_dir == LocalFilesystem.getcwd():
            introduction_text = "No intermediate parameter files found\nin current working directory."
        else:
            introduction_text = "No intermediate parameter files found\nin the --vehicle-dir specified directory."
        introduction_label = ttk.Label(self.main_frame, anchor=tk.CENTER, justify=tk.CENTER,
                                       text=introduction_text + "\nChoose one of the following three options:")
        introduction_label.pack(expand=False, fill=tk.X, padx=6, pady=6)
        template_dir, new_base_dir, vehicle_dir = LocalFilesystem.get_recently_used_dirs()
        self.create_option1_widgets(template_dir,
                                    new_base_dir,
                                    "MyVehicleName",
                                    fc_connected)
        self.create_option2_widgets(vehicle_dir)
        self.create_option3_widgets(vehicle_dir)

        # Bind the close_connection_and_quit function to the window close event
        self.root.protocol("WM_DELETE_WINDOW", self.close_and_quit)

    def close_and_quit(self):
        sys_exit(0)

    def create_option1_widgets(self, initial_template_dir: str, initial_base_dir: str,
                               initial_new_dir: str, fc_connected: bool):
        # Option 1 - Create a new vehicle configuration directory based on an existing template
        option1_label = ttk.Label(text="Create a new vehicle configuration directory", style="Bold.TLabel")
        option1_label_frame = ttk.LabelFrame(self.main_frame, labelwidget=option1_label, borderwidth=1, relief="solid")
        option1_label_frame.pack(expand=True, fill=tk.X, padx=6, pady=6)
        template_dir_edit_tooltip = "Existing vehicle template directory containing the intermediate\n" \
                                    "parameter files to be copied to the new vehicle configuration directory"
        template_dir_btn_tooltip = "Select the existing vehicle template directory containing the intermediate\n" \
                                   "parameter files to be copied to the new vehicle configuration directory"
        self.template_dir = DirectorySelectionWidgets(self, option1_label_frame, initial_template_dir,
                                                      "(source) Template directory:",
                                                      False,
                                                      template_dir_edit_tooltip,
                                                      template_dir_btn_tooltip,
                                                      self.local_filesystem)
        self.template_dir.container_frame.pack(expand=False, fill=tk.X, padx=3, pady=5, anchor=tk.NW)

        use_fc_params_checkbox = ttk.Checkbutton(option1_label_frame, variable=self.use_fc_params,
                                                 text="Use parameter values from connected FC, not from template files")
        use_fc_params_checkbox.pack(anchor=tk.NW)
        show_tooltip(use_fc_params_checkbox,
                     "Use the parameter values from the connected flight controller instead of the\n" \
                     "template files when creating a new vehicle configuration directory from a template.\n" \
                     "This option is only available when a flight controller is connected")
        if not fc_connected:
            self.use_fc_params.set(False)
            use_fc_params_checkbox.config(state=tk.DISABLED)

        new_base_dir_edit_tooltip = "Existing directory where the new vehicle configuration directory will be created"
        new_base_dir_btn_tooltip = "Select the directory where the new vehicle configuration directory will be created"
        self.new_base_dir = DirectorySelectionWidgets(self, option1_label_frame, initial_base_dir,
                                                      "(destination) base directory:",
                                                      False,
                                                      new_base_dir_edit_tooltip,
                                                      new_base_dir_btn_tooltip)
        self.new_base_dir.container_frame.pack(expand=False, fill=tk.X, padx=3, pady=5, anchor=tk.NW)
        new_dir_edit_tooltip = "A new vehicle configuration directory with this name will be created at the " \
            "(destination) base directory"
        self.new_dir = DirectoryNameWidgets(option1_label_frame, initial_new_dir,
                                            "(destination) new vehicle name:",
                                            new_dir_edit_tooltip)
        self.new_dir.container_frame.pack(expand=False, fill=tk.X, padx=3, pady=5, anchor=tk.NW)
        create_vehicle_directory_from_template_button = ttk.Button(option1_label_frame,
                                                                  text="Create vehicle configuration directory from template",
                                                                  command=self.create_new_vehicle_from_template)
        create_vehicle_directory_from_template_button.pack(expand=False, fill=tk.X, padx=20, pady=5, anchor=tk.CENTER)
        show_tooltip(create_vehicle_directory_from_template_button,
                     "Create a new vehicle configuration directory on the (destination) base directory,\n"
                     "copy the template files from the (source) template directory to it and\n"
                     "load the newly created files into the application")

    def create_option2_widgets(self, initial_dir: str):
        # Option 2 - Use an existing vehicle configuration directory
        option2_label = ttk.Label(text="Open an existing vehicle configuration directory", style="Bold.TLabel")
        option2_label_frame = ttk.LabelFrame(self.main_frame, labelwidget=option2_label, borderwidth=1, relief="solid")
        option2_label_frame.pack(expand=True, fill=tk.X, padx=6, pady=6)
        option2_label = ttk.Label(option2_label_frame, anchor=tk.CENTER, justify=tk.CENTER,
                                  text="Use an existing vehicle configuration directory with\n" \
                                   "intermediate parameter files, apm.pdef.xml and vehicle_components.json")
        option2_label.pack(expand=False, fill=tk.X, padx=6)
        self.connection_selection_widgets = VehicleDirectorySelectionWidgets(self, option2_label_frame,
                                                                             self.local_filesystem,
                                                                             initial_dir,
                                                                             destroy_parent_on_open=True)
        self.connection_selection_widgets.container_frame.pack(expand=True, fill=tk.X, padx=3, pady=5, anchor=tk.NW)

    def create_option3_widgets(self, last_vehicle_dir: str):
        # Option 3 - Open the last used vehicle configuration directory
        option3_label = ttk.Label(text="Open the last used vehicle configuration directory", style="Bold.TLabel")
        option3_label_frame = ttk.LabelFrame(self.main_frame, labelwidget=option3_label, borderwidth=1, relief="solid")
        option3_label_frame.pack(expand=True, fill=tk.X, padx=6, pady=6)

        last_dir = DirectorySelectionWidgets(self, option3_label_frame, last_vehicle_dir if last_vehicle_dir else '',
                                             "Last used vehicle configuration directory:",
                                             False,
                                             "Last used vehicle configuration directory",
                                             "")
        last_dir.container_frame.pack(expand=False, fill=tk.X, padx=3, pady=5, anchor=tk.NW)

        # Check if there is a last used vehicle configuration directory
        button_state = tk.NORMAL if last_vehicle_dir else tk.DISABLED
        open_last_vehicle_directory_button = ttk.Button(option3_label_frame,
                                                       text="Open Last Used Vehicle Configuration Directory",
                                                       command=lambda last_vehicle_dir=last_vehicle_dir: \
                                                        self.open_last_vehicle_directory(last_vehicle_dir),
                                                       state=button_state)
        open_last_vehicle_directory_button.pack(expand=False, fill=tk.X, padx=20, pady=5, anchor=tk.CENTER)
        show_tooltip(open_last_vehicle_directory_button,
                     "Directly open the last used vehicle configuration directory for configuring and tuning the vehicle")

    def create_new_vehicle_from_template(self):
        # Get the selected template directory and new vehicle configuration directory name
        template_dir = self.template_dir.get_selected_directory()
        new_base_dir = self.new_base_dir.get_selected_directory()
        new_vehicle_name = self.new_dir.get_selected_directory()

        if template_dir == "":
            messagebox.showerror("Vehicle template directory", "Vehicle template directory cannot be empty")
            return
        if not LocalFilesystem.directory_exists(template_dir):
            messagebox.showerror("Vehicle template directory", "Vehicle template directory does not exist")
            return

        if new_vehicle_name == "":
            messagebox.showerror("New vehicle directory", "New vehicle name cannot be empty")
            return
        if not LocalFilesystem.valid_directory_name(new_vehicle_name):
            messagebox.showerror("New vehicle directory", "New vehicle name must not contain invalid characters")
            return
        new_vehicle_dir = LocalFilesystem.new_vehicle_dir(new_base_dir, new_vehicle_name)

        error_msg = self.local_filesystem.create_new_vehicle_dir(new_vehicle_dir)
        if error_msg:
            messagebox.showerror("New vehicle directory", error_msg)
            return

        error_msg = self.local_filesystem.copy_template_files_to_new_vehicle_dir(template_dir, new_vehicle_dir)
        if error_msg:
            messagebox.showerror("Copying template files", error_msg)
            return

        # Update the local_filesystem with the new vehicle configuration directory
        self.local_filesystem.vehicle_dir = new_vehicle_dir

        try:
            self.local_filesystem.re_init(new_vehicle_dir, self.local_filesystem.vehicle_type)
        except SystemExit as exp:
            messagebox.showerror("Fatal error reading parameter files", f"{exp}")
            raise

        files = list(self.local_filesystem.file_parameters.keys())
        if files:
            LocalFilesystem.store_recently_used_template_dirs(template_dir, new_base_dir)
            LocalFilesystem.store_recently_used_vehicle_dir(new_vehicle_dir)
            self.root.destroy()
        else:
            show_no_param_files_error(template_dir)
        self.created_new_vehicle_from_template = True

    def open_last_vehicle_directory(self, last_vehicle_dir: str):
        # Attempt to open the last opened vehicle configuration directory
        if last_vehicle_dir:
            # If a last opened directory is found, proceed as if the user had manually selected it
            self.local_filesystem.vehicle_dir = last_vehicle_dir

            try:
                self.local_filesystem.re_init(last_vehicle_dir, self.local_filesystem.vehicle_type)
            except SystemExit as exp:
                messagebox.showerror("Fatal error reading parameter files", f"{exp}")
                raise

            files = list(self.local_filesystem.file_parameters.keys())
            if files:
                self.root.destroy()
            else:
                show_no_param_files_error(last_vehicle_dir)
        else:
            # If no last opened directory is found, display a message to the user
            messagebox.showerror("No Last Vehicle Directory Found",
                                 "No last opened vehicle configuration directory was found.\n" \
                                    "Please select a directory manually.")

def argument_parser():
    """
    Parses command-line arguments for the script.

    This function sets up an argument parser to handle the command-line arguments for the script.

    Returns:
    argparse.Namespace: An object containing the parsed arguments.
    """
    parser = ArgumentParser(description='This main is for testing and development only. '
                            'Usually, the VehicleDirectorySelectionWindow is called from another script')
    parser = LocalFilesystem.add_argparse_arguments(parser)
    return add_common_arguments_and_parse(parser)


def main():
    args = argument_parser()

    logging_basicConfig(level=logging_getLevelName(args.loglevel), format='%(asctime)s - %(levelname)s - %(message)s')

    logging_warning("This main is for testing and development only, usually the VehicleDirectorySelectionWindow is"
                    " called from another script")

    local_filesystem = LocalFilesystem(args.vehicle_dir, args.vehicle_type, args.allow_editing_template_files)

    # Get the list of intermediate parameter files files that will be processed sequentially
    files = list(local_filesystem.file_parameters.keys())

    if not files:
        logging_error("No intermediate parameter files found in %s.", args.vehicle_dir)
        window = VehicleDirectorySelectionWindow(local_filesystem)
        window.root.mainloop()


if __name__ == "__main__":
    main()
