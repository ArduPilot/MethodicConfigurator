#!/usr/bin/env python3

'''
This file is part of Ardupilot methodic configurator. https://github.com/ArduPilot/MethodicConfigurator

(C) 2024 Amilcar do Carmo Lucas, IAV GmbH

SPDX-License-Identifier:    GPL-3
'''


from argparse import ArgumentParser

from sys import exit as sys_exit

from copy import deepcopy

from logging import basicConfig as logging_basicConfig
from logging import getLevelName as logging_getLevelName
from logging import warning as logging_warning
from logging import debug as logging_error

import tkinter as tk
from tkinter import ttk
from tkinter import filedialog

from MethodicConfigurator.common_arguments import add_common_arguments_and_parse

from MethodicConfigurator.backend_filesystem import LocalFilesystem

from MethodicConfigurator.frontend_tkinter_base import show_error_message
from MethodicConfigurator.frontend_tkinter_base import show_no_param_files_error
from MethodicConfigurator.frontend_tkinter_base import show_tooltip
from MethodicConfigurator.frontend_tkinter_base import BaseWindow


class DirectorySelectionWidgets():
    """
    A class to manage directory selection widgets in the GUI.

    This class provides functionality for creating and managing widgets related to directory selection,
    including a label, an entry field for displaying the selected directory, and a button for opening a
    directory selection dialog.
    """
    def __init__(self, parent, parent_frame, initialdir: str, label_text: str,  # pylint: disable=too-many-arguments
                 autoresize_width: bool, dir_tooltip: str, button_tooltip: str):
        self.parent = parent
        self.directory = deepcopy(initialdir)
        self.label_text = label_text
        self.autoresize_width = autoresize_width

        # Create a new frame for the directory selection label and button
        self.container_frame = tk.Frame(parent_frame)

        # Create a description label for the directory
        directory_selection_label = tk.Label(self.container_frame, text=label_text)
        directory_selection_label.pack(side=tk.TOP, anchor=tk.NW)
        show_tooltip(directory_selection_label, dir_tooltip)

        # Create a new subframe for the directory selection
        directory_selection_subframe = tk.Frame(self.container_frame)
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
        # Open the directory selection dialog
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
        self.container_frame = tk.Frame(parent_frame)

        # Create a description label for the directory name entry
        directory_selection_label = tk.Label(self.container_frame, text=label_text)
        directory_selection_label.pack(side=tk.TOP, anchor=tk.NW)
        show_tooltip(directory_selection_label, dir_tooltip)

        # Create an entry for the directory
        self.dir_var = tk.StringVar(value=initial_dir)
        directory_entry = tk.Entry(self.container_frame, textvariable=self.dir_var,
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
    def __init__(self, parent: tk, parent_frame: tk.Frame,  # pylint: disable=too-many-arguments
                 local_filesystem: LocalFilesystem,
                 initial_dir: str, destroy_parent_on_open: bool) -> None:
        # Call the parent constructor with the necessary arguments
        super().__init__(parent, parent_frame, initial_dir, "Vehicle directory:",
                         False,
                         "Vehicle-specific directory containing the intermediate\n"
                         "parameter files to be uploaded to the flight controller",
                         "Select the vehicle-specific directory containing the\n"
                         "intermediate parameter files to be uploaded to the flight controller" \
                            if destroy_parent_on_open else '')
        self.local_filesystem = local_filesystem
        self.destroy_parent_on_open = destroy_parent_on_open

    def on_select_directory(self):
        # Call the base class method to open the directory selection dialog
        if super().on_select_directory():
            if "vehicle_templates" in self.directory:
                show_error_message("Invalid Vehicle Directory Selected",
                                   "Please do not edit the files provided 'vehicle_templates' directory\n"
                                   "as those are used as a template for new vehicles")
                return
            self.local_filesystem.vehicle_dir = self.directory
            self.local_filesystem.re_init(self.directory, self.local_filesystem.vehicle_type)
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
    def __init__(self, local_filesystem: LocalFilesystem):
        super().__init__()
        self.local_filesystem = local_filesystem
        self.root.title("Select Vehicle directory")
        self.root.geometry("800x535") # Set the window size

        # Explain why we are here
        if local_filesystem.vehicle_dir == LocalFilesystem.getcwd():
            introduction_text = "No intermediate parameter files found\nin current working directory."
        else:
            introduction_text = "No intermediate parameter files found\nin the --vehicle-dir specified directory."
        introduction_label = tk.Label(self.root, text=introduction_text + \
                                           "\nChoose one of the following three options:")
        introduction_label.pack(expand=False, fill=tk.X, padx=6, pady=6)
        template_dir, new_base_dir, vehicle_dir = LocalFilesystem.get_recently_used_dirs()
        self.create_option1_widgets(template_dir,
                                    new_base_dir,
                                    "MyVehicleName")
        self.create_option2_widgets(vehicle_dir)
        self.create_option3_widgets(vehicle_dir)

        # Bind the close_connection_and_quit function to the window close event
        self.root.protocol("WM_DELETE_WINDOW", self.close_and_quit)

    def close_and_quit(self):
        sys_exit(0)

    def create_option1_widgets(self, initial_template_dir: str, initial_base_dir: str, initial_new_dir: str):
        # Option 1 - Create a new vehicle configuration directory based on an existing template
        option1_label_frame = tk.LabelFrame(self.root, text="Create a new vehicle configuration directory")
        option1_label_frame.pack(expand=True, fill=tk.X, padx=6, pady=5)
        template_dir_edit_tooltip = "Existing vehicle template directory containing the\n" \
                                    "intermediate parameter files to be copied to the new vehicle directory"
        template_dir_btn_tooltip = "Select the existing vehicle template directory containing the\n" \
                                   "intermediate parameter files to be copied to the new vehicle directory"
        self.template_dir = DirectorySelectionWidgets(self, option1_label_frame, initial_template_dir,
                                                      "(source) Template directory:",
                                                      False,
                                                      template_dir_edit_tooltip,
                                                      template_dir_btn_tooltip)
        self.template_dir.container_frame.pack(expand=False, fill=tk.X, padx=3, pady=5, anchor=tk.NW)
        new_base_dir_edit_tooltip = "Existing directory where the new vehicle directory will be created"
        new_base_dir_btn_tooltip = "Select the existing directory where the new vehicle directory will be created"
        self.new_base_dir = DirectorySelectionWidgets(self, option1_label_frame, initial_base_dir,
                                                      "(destination) base directory:",
                                                      False,
                                                      new_base_dir_edit_tooltip,
                                                      new_base_dir_btn_tooltip)
        self.new_base_dir.container_frame.pack(expand=False, fill=tk.X, padx=3, pady=5, anchor=tk.NW)
        new_dir_edit_tooltip = "A new vehicle directory with this name will be created at the (destination) base directory"
        self.new_dir = DirectoryNameWidgets(option1_label_frame, initial_new_dir,
                                            "(destination) new vehicle name:",
                                            new_dir_edit_tooltip)
        self.new_dir.container_frame.pack(expand=False, fill=tk.X, padx=3, pady=5, anchor=tk.NW)
        create_vehicle_directory_from_template_button = tk.Button(option1_label_frame,
                                                                  text="Create vehicle directory from template",
                                                                  command=self.create_new_vehicle_from_template)
        create_vehicle_directory_from_template_button.pack(expand=False, fill=tk.X, padx=20, pady=5, anchor=tk.CENTER)
        show_tooltip(create_vehicle_directory_from_template_button,
                     "Create a new vehicle directory on the (destination) base directory,\n"
                     "copy the template files from the (source) template directory to it and\n"
                     "load the newly created files into the application")

    def create_option2_widgets(self, initial_dir: str):
        # Option 2 - Use an existing vehicle configuration directory
        option2_label_frame = tk.LabelFrame(self.root, text="Open an existing vehicle configuration directory")
        option2_label_frame.pack(expand=True, fill=tk.X, padx=6, pady=6)
        option2_label = tk.Label(option2_label_frame, text="Use an existing vehicle configuration directory\n"
                                 "with intermediate parameter files, apm.pdef.xml\nand vehicle_components.json")
        option2_label.pack(expand=False, fill=tk.X, padx=6)
        self.connection_selection_widgets = VehicleDirectorySelectionWidgets(self, option2_label_frame,
                                                                             self.local_filesystem,
                                                                             initial_dir,
                                                                             destroy_parent_on_open=True)
        self.connection_selection_widgets.container_frame.pack(expand=True, fill=tk.X, padx=3, pady=5, anchor=tk.NW)

    def create_option3_widgets(self, last_vehicle_dir: str):
        # Option 3 - Open the last used vehicle directory
        option3_label_frame = tk.LabelFrame(self.root, text="Open the last used vehicle directory")
        option3_label_frame.pack(expand=True, fill=tk.X, padx=6, pady=6)

        # Check if there is a last used vehicle directory
        button_state = tk.NORMAL if last_vehicle_dir else tk.DISABLED
        open_last_vehicle_directory_button = tk.Button(option3_label_frame, text="Open Last Used Vehicle Directory",
                                                command=lambda last_vehicle_dir=last_vehicle_dir: \
                                                    self.open_last_vehicle_directory(last_vehicle_dir),
                                                state=button_state)
        open_last_vehicle_directory_button.pack(expand=False, fill=tk.X, padx=20, pady=5, anchor=tk.CENTER)
        show_tooltip(open_last_vehicle_directory_button,
                     "Directly open the last used vehicle directory for configuring the vehicle")

    def create_new_vehicle_from_template(self):
        # Get the selected template directory and new vehicle directory name
        template_dir = self.template_dir.get_selected_directory()
        new_base_dir = self.new_base_dir.get_selected_directory()
        new_vehicle_name = self.new_dir.get_selected_directory()
        if new_vehicle_name == "":
            show_error_message("New vehicle directory", "New vehicle name cannot be empty")
            return
        if not LocalFilesystem.valid_directory_name(new_vehicle_name):
            show_error_message("New vehicle directory", "New vehicle name must not contain invalid characters")
            return
        new_vehicle_dir = self.local_filesystem.new_vehicle_dir(new_base_dir, new_vehicle_name)

        error_msg = self.local_filesystem.create_new_vehicle_dir(new_vehicle_dir)
        if error_msg:
            show_error_message("New vehicle directory", error_msg)
            return

        error_msg = self.local_filesystem.copy_template_files_to_new_vehicle_dir(template_dir, new_vehicle_dir)
        if error_msg:
            show_error_message("Copying template files", error_msg)
            return

        # Update the local_filesystem with the new vehicle directory
        self.local_filesystem.vehicle_dir = new_vehicle_dir
        self.local_filesystem.re_init(new_vehicle_dir, self.local_filesystem.vehicle_type)
        files = list(self.local_filesystem.file_parameters.keys())
        if files:
            LocalFilesystem.store_recently_used_template_dirs(template_dir, new_base_dir)
            LocalFilesystem.store_recently_used_vehicle_dir(new_vehicle_dir)
            self.root.destroy()
        else:
            # No intermediate parameter files were found in the source template directory
            error_message = f"No intermediate parameter files found in the selected '{template_dir}'" \
                " template vehicle directory.\n" \
                "Please select a vehicle directory containing valid ArduPilot intermediate parameter files."
            show_error_message("No Parameter Files Found", error_message)

    def open_last_vehicle_directory(self, last_vehicle_dir: str):
        # Attempt to open the last opened vehicle directory
        if last_vehicle_dir:
            # If a last opened directory is found, proceed as if the user had manually selected it
            self.local_filesystem.vehicle_dir = last_vehicle_dir
            self.local_filesystem.re_init(last_vehicle_dir, self.local_filesystem.vehicle_type)
            files = list(self.local_filesystem.file_parameters.keys())
            if files:
                self.root.destroy()
            else:
                show_no_param_files_error(last_vehicle_dir)
        else:
            # If no last opened directory is found, display a message to the user
            show_error_message("No Last Vehicle Directory Found",
                            "No last opened vehicle directory was found. Please select a directory manually.")

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

    local_filesystem = LocalFilesystem(args.vehicle_dir, args.vehicle_type)

    # Get the list of intermediate parameter files files that will be processed sequentially
    files = list(local_filesystem.file_parameters.keys())

    if not files:
        logging_error("No intermediate parameter files found in %s.", args.vehicle_dir)
        window = VehicleDirectorySelectionWindow(local_filesystem)
        window.root.mainloop()


if __name__ == "__main__":
    main()
