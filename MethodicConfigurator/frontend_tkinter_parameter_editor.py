#!/usr/bin/env python3

'''
This file is part of Ardupilot methodic configurator. https://github.com/ArduPilot/MethodicConfigurator

(C) 2024 Amilcar do Carmo Lucas

SPDX-License-Identifier:    GPL-3
'''

import tkinter as tk
from tkinter import messagebox
from tkinter import ttk
from tkinter import filedialog

#from logging import debug as logging_debug
from logging import info as logging_info
from logging import warning as logging_warning
from logging import error as logging_error
#from logging import critical as logging_critical

from typing import List
from typing import Tuple

from webbrowser import open as webbrowser_open  # to open the blog post documentation

from MethodicConfigurator.backend_filesystem import LocalFilesystem
from MethodicConfigurator.backend_filesystem import is_within_tolerance

from MethodicConfigurator.backend_flightcontroller import FlightController

from MethodicConfigurator.frontend_tkinter_base import show_tooltip
from MethodicConfigurator.frontend_tkinter_base import AutoResizeCombobox
from MethodicConfigurator.frontend_tkinter_base import ProgressWindow
from MethodicConfigurator.frontend_tkinter_base import BaseWindow
from MethodicConfigurator.frontend_tkinter_base import RichText

from MethodicConfigurator.frontend_tkinter_directory_selection import VehicleDirectorySelectionWidgets

from MethodicConfigurator.frontend_tkinter_parameter_editor_table import ParameterEditorTable

from MethodicConfigurator.tempcal_imu import IMUfit


class DocumentationFrame:  # pylint: disable=too-few-public-methods
    """
    A class to manage and display documentation within the GUI.

    This class is responsible for creating a frame that displays
    documentation links related to the current file being edited. It updates
    the documentation links based on the current file and provides
    functionality to open these links in a web browser.
    """
    def __init__(self, root: tk.Tk, local_filesystem, current_file: str):
        self.root = root
        self.local_filesystem = local_filesystem
        self.current_file = current_file
        self.documentation_frame = None
        self.documentation_labels = {}
        self.__create_documentation_frame()

    def __create_documentation_frame(self):
        self.documentation_frame = ttk.LabelFrame(self.root, text="Documentation")
        self.documentation_frame.pack(side=tk.TOP, fill="x", expand=False, pady=(4, 4), padx=(4, 4))

        # Create a grid structure within the documentation_frame
        documentation_grid = ttk.Frame(self.documentation_frame)
        documentation_grid.pack(fill="both", expand=True)

        descriptive_texts = ["Forum Blog:", "Wiki:", "External tool:", "Mandatory:"]
        descriptive_tooltips = ["ArduPilot's forum Methodic configuration Blog post relevant for the current file",
                                "ArduPilot's wiki page relevant for the current file",
                                "External tool or documentation relevant for the current file",
                                "Mandatory level of the current file,\n 100% you MUST use this file to configure the "
                                "vehicle,\n 0% you can ignore this file if it does not apply to your vehicle"]
        for i, text in enumerate(descriptive_texts):
            # Create labels for the first column with static descriptive text
            label = ttk.Label(documentation_grid, text=text)
            label.grid(row=i, column=0, sticky="w")
            show_tooltip(label, descriptive_tooltips[i])

            # Create labels for the second column with the documentation links
            self.documentation_labels[text] = ttk.Label(documentation_grid)
            self.documentation_labels[text].grid(row=i, column=1, sticky="w")

        # Dynamically update the documentation text and URL links
        self.update_documentation_labels(self.current_file)

    def update_documentation_labels(self, current_file: str):
        self.current_file = current_file
        if current_file:
            frame_title = f"{current_file} Documentation"
        else:
            frame_title = "Documentation"
        self.documentation_frame.config(text=frame_title)

        blog_text, blog_url = self.local_filesystem.get_documentation_text_and_url(current_file, 'blog')
        self.__update_documentation_label('Forum Blog:', blog_text, blog_url)
        wiki_text, wiki_url = self.local_filesystem.get_documentation_text_and_url(current_file, 'wiki')
        self.__update_documentation_label('Wiki:', wiki_text, wiki_url)
        external_tool_text, external_tool_url = self.local_filesystem.get_documentation_text_and_url(current_file,
                                                                                                     'external_tool')
        self.__update_documentation_label('External tool:', external_tool_text, external_tool_url)
        mandatory_text, mandatory_url = self.local_filesystem.get_documentation_text_and_url(current_file,
                                                                                             'mandatory')
        self.__update_documentation_label('Mandatory:', mandatory_text, mandatory_url, False)

    def __update_documentation_label(self, label_key, text, url, url_expected=True):
        label = self.documentation_labels[label_key]
        if url:
            label.config(text=text, foreground="blue", cursor="hand2", underline=True)
            label.bind("<Button-1>", lambda event, url=url: webbrowser_open(url))
            show_tooltip(label, url)
        else:
            label.config(text=text, foreground="black", cursor="arrow", underline=False)
            label.bind("<Button-1>", lambda event: None)
            if url_expected:
                show_tooltip(label, "Documentation URL not available")


def show_about_window(root, version: str):
    # Create a new window for the custom "About" message
    about_window = tk.Toplevel(root)
    about_window.title("About")
    about_window.geometry("650x220")

    main_frame = ttk.Frame(about_window)
    main_frame.pack(expand=True, fill=tk.BOTH)

    # Add the "About" message
    about_message = f"ArduPilot Methodic Configurator Version: {version}\n\n" \
                    "A clear configuration sequence for ArduPilot vehicles.\n\n" \
                    "Copyright © 2024 Amilcar do Carmo Lucas and ArduPilot.org\n\n" \
                    "Licensed under the GNU General Public License v3.0"
    about_label = ttk.Label(main_frame, text=about_message, wraplength=450)
    about_label.grid(column=0, row=0, padx=10, pady=10, columnspan=5)  # Span across all columns

    # Create buttons for each action
    user_manual_button = ttk.Button(main_frame, text="User Manual",
                                    command=lambda: webbrowser_open(
                                       "https://github.com/ArduPilot/MethodicConfigurator/blob/master/USERMANUAL.md"))
    support_forum_button = ttk.Button(main_frame, text="Support Forum",
                                      command=lambda: webbrowser_open(
                                         "http://discuss.ardupilot.org/t/new-ardupilot-methodic-configurator-gui/115038/1"))
    report_bug_button = ttk.Button(main_frame, text="Report a Bug",
                                   command=lambda: webbrowser_open(
                                      "https://github.com/ArduPilot/MethodicConfigurator/issues/new"))
    credits_button = ttk.Button(main_frame, text="Credits",
                                command=lambda: webbrowser_open(
                                   "https://github.com/ArduPilot/MethodicConfigurator/blob/master/credits/CREDITS.md"))
    source_button = ttk.Button(main_frame, text="Source Code",
                               command=lambda: webbrowser_open(
                                  "https://github.com/ArduPilot/MethodicConfigurator"))

    # Place buttons using grid for equal spacing and better control over layout
    user_manual_button.grid(column=0, row=1, padx=10, pady=10)
    support_forum_button.grid(column=1, row=1, padx=10, pady=10)
    report_bug_button.grid(column=2, row=1, padx=10, pady=10)
    credits_button.grid(column=3, row=1, padx=10, pady=10)
    source_button.grid(column=4, row=1, padx=10, pady=10)

    # Configure the grid to ensure equal spacing and expansion
    main_frame.columnconfigure([0, 1, 2, 3, 4], weight=1)


class ParameterEditorWindow(BaseWindow):  # pylint: disable=too-many-instance-attributes
    """
    This class is responsible for creating and managing the graphical user interface (GUI)
    for the ArduPilot methodic configurator. It inherits from the BaseWindow class
    and provides functionalities for displaying and interacting with drone
    parameters, documentation, and flight controller connection settings.
    """
    def __init__(self, current_file: str, flight_controller: FlightController,
                 local_filesystem: LocalFilesystem, version: str):
        super().__init__()
        self.current_file = current_file
        self.flight_controller = flight_controller
        self.local_filesystem = local_filesystem

        self.at_least_one_changed_parameter_written = False
        self.file_selection_combobox = None
        self.show_only_differences = None
        self.annotate_params_into_files = None
        self.parameter_editor_table = None
        self.reset_progress_window = None
        self.param_download_progress_window = None
        self.tempcal_imu_progress_window = None

        self.root.title("Amilcar Lucas's - ArduPilot methodic configurator " + version + \
                        " - Parameter file editor and uploader")
        self.root.geometry("900x500") # Set the window width

        # Bind the close_connection_and_quit function to the window close event
        self.root.protocol("WM_DELETE_WINDOW", self.close_connection_and_quit)

        self.__create_conf_widgets(version)

        # Create a DocumentationFrame object for the Documentation Content
        self.documentation_frame = DocumentationFrame(self.main_frame, self.local_filesystem, self.current_file)

        self.__create_parameter_area_widgets()

        # trigger a table update to ask the user what to do in the case this file needs special actions
        self.root.after(10, self.on_param_file_combobox_change(None, True))

        # this one should be on top of the previous one hence the longer time
        self.root.after(100, self.__please_read_the_docs(self.root))
        self.root.mainloop()

    def __create_conf_widgets(self, version: str):
        config_frame = ttk.Frame(self.main_frame)
        config_frame.pack(side=tk.TOP, fill="x", expand=False, pady=(4, 0)) # Pack the frame at the top of the window

        config_subframe = ttk.Frame(config_frame)
        config_subframe.pack(side=tk.LEFT, fill="x", expand=True, anchor=tk.NW) # Pack the frame at the top of the window

        # Create a new frame inside the config_subframe for the intermediate parameter file directory selection labels
        # and directory selection button
        directory_selection_frame = VehicleDirectorySelectionWidgets(self, config_subframe, self.local_filesystem,
                                                                     self.local_filesystem.vehicle_dir,
                                                                     destroy_parent_on_open=False)
        directory_selection_frame.container_frame.pack(side=tk.LEFT, fill="x", expand=False, padx=(4, 6))

        # Create a new frame inside the config_subframe for the intermediate parameter file selection label and combobox
        file_selection_frame = ttk.Frame(config_subframe)
        file_selection_frame.pack(side=tk.LEFT, fill="x", expand=False, padx=(6, 6))

        # Create a label for the Combobox
        file_selection_label = ttk.Label(file_selection_frame, text="Current intermediate parameter file:")
        file_selection_label.pack(side=tk.TOP, anchor=tk.NW) # Add the label to the top of the file_selection_frame

        # Create Combobox for intermediate parameter file selection
        self.file_selection_combobox = AutoResizeCombobox(file_selection_frame,
                                                          list(self.local_filesystem.file_parameters.keys()),
                                                          self.current_file,
                                                          "Select the intermediate parameter file from the list of available "
                                                          "files in the selected vehicle directory\nIt will automatically "
                                                          "advance to the next file once the current file is uploaded to the "
                                                          "fight controller",
                                                          state='readonly', width=45)
        self.file_selection_combobox.bind("<<ComboboxSelected>>", self.on_param_file_combobox_change)
        self.file_selection_combobox.pack(side=tk.TOP, anchor=tk.NW, pady=(4, 0))

        image_label = BaseWindow.put_image_in_label(config_frame, LocalFilesystem.application_logo_filepath())
        image_label.pack(side=tk.RIGHT, anchor=tk.NE, padx=(4, 4), pady=(4, 0))
        image_label.bind("<Button-1>", lambda event: show_about_window(self.main_frame, version))
        show_tooltip(image_label, "User Manual, Support Forum, Report a Bug, Credits, Source Code")

    def __create_parameter_area_widgets(self):
        self.show_only_differences = tk.BooleanVar(value=False)
        self.annotate_params_into_files = tk.BooleanVar(value=False)

        # Create a Scrollable parameter editor table
        self.parameter_editor_table = ParameterEditorTable(self.main_frame, self.local_filesystem, self)
        self.repopulate_parameter_table(self.current_file)
        self.parameter_editor_table.pack(side="top", fill="both", expand=True)

        # Create a frame for the buttons
        buttons_frame = ttk.Frame(self.main_frame)
        buttons_frame.pack(side="bottom", fill="x", expand=False, pady=(10, 10))

        # Create a frame for the checkboxes
        checkboxes_frame = ttk.Frame(buttons_frame)
        checkboxes_frame.pack(side=tk.LEFT, padx=(8, 8))

        # Create a checkbox for toggling parameter display
        only_changed_checkbox = ttk.Checkbutton(checkboxes_frame, text="See only changed parameters",
                                                variable=self.show_only_differences,
                                                command=self.on_show_only_changed_checkbox_change)
        only_changed_checkbox.pack(side=tk.TOP, anchor=tk.NW)
        show_tooltip(only_changed_checkbox, "Toggle to show only parameters that will change if/when uploaded to the flight "
                     "controller")

        annotate_params_checkbox = ttk.Checkbutton(checkboxes_frame, text="Annotate docs into .param files",
                                                   state='normal' if self.local_filesystem.doc_dict else 'disabled',
                                                   variable=self.annotate_params_into_files)
        annotate_params_checkbox.pack(side=tk.TOP, anchor=tk.NW)
        show_tooltip(annotate_params_checkbox, "Annotate ArduPilot parameter documentation metadata into the intermediate "
                     "parameter files\n"
                     "The files will be bigger, but all the existing parameter documentation will be included inside")

        # Create upload button
        upload_selected_button = ttk.Button(buttons_frame, text="Upload selected params to FC, and advance to next param file",
                                            command=self.on_upload_selected_click)
        upload_selected_button.configure(state='normal' if self.flight_controller.master else 'disabled')
        upload_selected_button.pack(side=tk.LEFT, padx=(8, 8)) # Add padding on both sides of the upload selected button
        show_tooltip(upload_selected_button, "Upload selected parameters to the flight controller and advance to the next "
                     "intermediate parameter file\nIf changes have been made to the current file it will ask if you want "
                     "to save them\nIt will reset the FC if necessary, re-download all parameters and validate their value")

        # Create skip button
        skip_button = ttk.Button(buttons_frame, text="Skip parameter file", command=self.on_skip_click)
        skip_button.pack(side=tk.RIGHT, padx=(8, 8)) # Add right padding to the skip button
        show_tooltip(skip_button, "Skip to the next intermediate parameter file without uploading any changes to the flight "
                     "controller\nIf changes have been made to the current file it will ask if you want to save them")

    @staticmethod
    def __please_read_the_docs(parent: tk.Tk):
        welcome_window = BaseWindow(parent)
        welcome_window.root.title("Welcome to the ArduPilot Methodic Configurator")
        welcome_window.root.geometry("690x170")

        style = ttk.Style()

        instructions_text = RichText(welcome_window.main_frame, wrap=tk.WORD, height=5, bd=0,
                                     background=style.lookup("TLabel", "background"))
        instructions_text.pack(padx=10, pady=10)
        instructions_text.insert(tk.END, "1. Read ")
        instructions_text.insert(tk.END, "all", "bold")
        instructions_text.insert(tk.END, " the documentation on top of the parameter table\n")
        instructions_text.insert(tk.END, "2. Edit the parameter ")
        instructions_text.insert(tk.END, "New Values", "italic")
        instructions_text.insert(tk.END, " and", "bold")
        instructions_text.insert(tk.END, " their ")
        instructions_text.insert(tk.END, "Change Reason\n", "italic")
        instructions_text.insert(tk.END, "3. Use ")
        instructions_text.insert(tk.END, "Del", "italic")
        instructions_text.insert(tk.END, " and ")
        instructions_text.insert(tk.END, "Add", "italic")
        instructions_text.insert(tk.END, " buttons to delete and add parameters if necessary\n")
        instructions_text.insert(tk.END, "4. Press the ")
        instructions_text.insert(tk.END, "Upload selected params to FC, and advance to next param file", "italic")
        instructions_text.insert(tk.END, " button\n")
        instructions_text.insert(tk.END, "5. Repeat until the program automatically closes")
        instructions_text.config(state=tk.DISABLED)

        dismiss_button = ttk.Button(welcome_window.main_frame, text="Dismiss",
                                    command=lambda: ParameterEditorWindow.__close_instructions_window(welcome_window, parent))
        dismiss_button.pack(pady=10)

        BaseWindow.center_window(welcome_window.root, parent)
        welcome_window.root.attributes('-topmost', True)

        # Disable the parent window
        #parent.state('withdraw')

    @staticmethod
    def __close_instructions_window(welcome_window, parent):
        welcome_window.root.destroy()
        #parent.deiconify()  # Show the parent window again
        #parent.state('normal')  # Enable the parent window
        parent.focus_set()

    def __do_tempcal_imu(self, selected_file:str):
        tempcal_imu_result_param_filename, tempcal_imu_result_param_fullpath = \
           self.local_filesystem.tempcal_imu_result_param_tuple()
        if selected_file == tempcal_imu_result_param_filename:
            if messagebox.askyesno("IMU temperature calibration",
                                    f"If you proceed the {tempcal_imu_result_param_filename}\n"
                                    "will be overwritten with the new calibration results.\n"
                                    "Do you want to provide a .bin log file and\n"
                                    "run the IMU temperature calibration using it?"):
                # file selection dialog to select the *.bin file to be used in the IMUfit temperature calibration
                filename = filedialog.askopenfilename(filetypes=[("ArduPilot binary log files", ["*.bin", "*.BIN"])])
                if filename:
                    messagebox.showwarning("IMU temperature calibration", "Please wait, this can take a really long time and\n"
                                           "the GUI will be unresponsive until it finishes.")
                    self.tempcal_imu_progress_window = ProgressWindow(self.main_frame, "Reading IMU calibration messages",
                                                                      "Please wait, this can take a long time")
                    # Pass the selected filename to the IMUfit class
                    IMUfit(filename, tempcal_imu_result_param_fullpath, False, False, False, False,
                            self.local_filesystem.vehicle_dir, self.tempcal_imu_progress_window.update_progress_bar_300_pct)
                    self.tempcal_imu_progress_window.destroy()
                    try:
                        self.local_filesystem.file_parameters = self.local_filesystem.read_params_from_files()
                    except SystemExit as exp:
                        messagebox.showerror("Fatal error reading parameter files", f"{exp}")
                        raise
                    self.parameter_editor_table.set_at_least_one_param_edited(True)  # force writing doc annotations to file

    def __should_copy_fc_values_to_file(self, selected_file: str):
        auto_changed_by = self.local_filesystem.auto_changed_by(selected_file)
        if auto_changed_by and self.flight_controller.fc_parameters:
            if messagebox.askyesno("Update file with values from FC?",
                                   "This configuration step should be performed outside this tool by\n"
                                   f"{auto_changed_by}\n"
                                   "and that should have changed the parameters on the FC.\n\n"
                                   f"Should the FC values now be copied to the {selected_file} file?"):
                relevant_fc_params = {key: value for key, value in self.flight_controller.fc_parameters.items() \
                                      if key in self.local_filesystem.file_parameters[selected_file]}
                params_copied = self.local_filesystem.copy_fc_values_to_file(selected_file, relevant_fc_params)
                if params_copied:
                    self.parameter_editor_table.set_at_least_one_param_edited(True)

    def __should_jump_to_file(self, selected_file: str) -> str:
        jump_possible = self.local_filesystem.jump_possible(selected_file)
        for dest_file, msg in jump_possible.items():
            if messagebox.askyesno("Skip some steps?", msg):
                self.file_selection_combobox.set(dest_file)
                return dest_file
        return selected_file

    def on_param_file_combobox_change(self, _event, forced: bool = False):
        if not self.file_selection_combobox['values']:
            return
        self.parameter_editor_table.generate_edit_widgets_focus_out()
        selected_file = self.file_selection_combobox.get()
        if self.current_file != selected_file or forced:
            self.write_changes_to_intermediate_parameter_file()
            self.__do_tempcal_imu(selected_file)
            self.__should_copy_fc_values_to_file(selected_file)
            selected_file = self.__should_jump_to_file(selected_file)

            # Update the current_file attribute to the selected file
            self.current_file = selected_file
            self.at_least_one_changed_parameter_written = False
            self.documentation_frame.update_documentation_labels(selected_file)
            self.repopulate_parameter_table(selected_file)

    def download_flight_controller_parameters(self, redownload: bool = False):
        self.param_download_progress_window = ProgressWindow(self.main_frame, ("Re-d" if redownload else "D") + \
                                                             "ownloading FC parameters", "Downloaded {} of {} parameters")
        # Download all parameters from the flight controller
        self.flight_controller.fc_parameters = self.flight_controller.download_params(
            self.param_download_progress_window.update_progress_bar)
        self.param_download_progress_window.destroy()  # for the case that '--device test' and there is no real FC connected
        if not redownload:
            self.on_param_file_combobox_change(None, True) # the initial param read will trigger a table update

    def repopulate_parameter_table(self, selected_file):
        if not selected_file:
            return  # no file was yet selected, so skip it
        if hasattr(self.flight_controller, 'fc_parameters') and self.flight_controller.fc_parameters:
            fc_parameters = self.flight_controller.fc_parameters
        else:
            fc_parameters = {}
        # Different parameters based on the tolerance value
        different_params = {param_name: file_value for param_name, file_value in
                            self.local_filesystem.file_parameters[selected_file].items()
                            if param_name not in fc_parameters or (param_name in fc_parameters and \
                                not is_within_tolerance(fc_parameters[param_name], float(file_value.value)))}
        if not different_params and self.show_only_differences.get():
            logging_info("No different parameters found in %s. Skipping...", selected_file)
            messagebox.showinfo("ArduPilot methodic configurator",
                                f"No different parameters found in {selected_file}. Skipping...")
            self.on_skip_click(force_focus_out_event=False)
            return
        # Re-populate the table with the new parameters
        self.parameter_editor_table.repopulate(selected_file, different_params,
                                               fc_parameters, self.show_only_differences.get())

    def on_show_only_changed_checkbox_change(self):
        self.repopulate_parameter_table(self.current_file)

    def upload_params_that_require_reset(self, selected_params: dict):
        """
        Write the selected parameters to the flight controller that require a reset.

        After the reset, the other parameters that do not require a reset must still be written to the flight controller.
        """
        fc_reset_required = False
        fc_reset_unsure = []

        # Write each selected parameter to the flight controller
        for param_name, param in selected_params.items():
            try:
                logging_info("Parameter %s set to %f", param_name, param.value)
                if param_name not in self.flight_controller.fc_parameters or \
                   not is_within_tolerance(self.flight_controller.fc_parameters[param_name], param.value):
                    param_metadata = self.local_filesystem.doc_dict.get(param_name, None)
                    if param_metadata and param_metadata.get('RebootRequired', False):
                        self.flight_controller.set_param(param_name, float(param.value))
                        self.at_least_one_changed_parameter_written = True
                        if param_name in self.flight_controller.fc_parameters:
                            logging_info("Parameter %s changed from %f to %f, reset required", param_name,
                                         self.flight_controller.fc_parameters[param_name], param.value)
                        else:
                            logging_info("Parameter %s changed to %f, reset required", param_name, param.value)
                        fc_reset_required = True
                    # Check if any of the selected parameters have a _TYPE, _EN, or _ENABLE suffix
                    elif param_name.endswith(('_TYPE', '_EN', '_ENABLE', 'SID_AXIS')):
                        self.flight_controller.set_param(param_name, float(param.value))
                        self.at_least_one_changed_parameter_written = True
                        if param_name in self.flight_controller.fc_parameters:
                            logging_info("Parameter %s changed from %f to %f, possible reset required", param_name,
                                         self.flight_controller.fc_parameters[param_name], param.value)
                        else:
                            logging_info("Parameter %s changed to %f, possible reset required", param_name, param.value)
                        fc_reset_unsure.append(param_name)
            except ValueError as e:
                logging_error("Failed to set parameter %s: %s", param_name, e)
                messagebox.showerror("ArduPilot methodic configurator", f"Failed to set parameter {param_name}: {e}")

        self.__reset_and_reconnect(fc_reset_required, fc_reset_unsure)

    def __reset_and_reconnect(self, fc_reset_required, fc_reset_unsure):
        if not fc_reset_required:
            if fc_reset_unsure:
                # Ask the user if they want to reset the ArduPilot
                fc_reset_required = messagebox.askyesno("Possible reset required", f"{(', ').join(fc_reset_unsure)} parameter"
                                                        "(s) potentially require a reset\nDo you want to reset the ArduPilot?")

        if fc_reset_required:
            self.reset_progress_window = ProgressWindow(self.main_frame, "Resetting Flight Controller",
                                                        "Waiting for {} of {} seconds")
            # Call reset_and_reconnect with a callback to update the reset progress bar and the progress message
            error_message = self.flight_controller.reset_and_reconnect(self.reset_progress_window.update_progress_bar)
            if error_message:
                logging_error(error_message)
                messagebox.showerror("ArduPilot methodic configurator", error_message)
            self.reset_progress_window.destroy()  # for the case that we are doing a test and there is no real FC connected

    def on_upload_selected_click(self):
        self.parameter_editor_table.generate_edit_widgets_focus_out()

        self.write_changes_to_intermediate_parameter_file()
        selected_params = self.parameter_editor_table.get_upload_selected_params(self.current_file)
        if selected_params:
            if hasattr(self.flight_controller, 'fc_parameters') and self.flight_controller.fc_parameters:
                self.upload_selected_params(selected_params)
            else:
                logging_warning("No parameters were yet downloaded from the flight controller, will not upload any parameter")
                messagebox.showwarning("Will not upload any parameter", "No flight controller connection")
        else:
            logging_warning("No parameter was selected for upload, will not upload any parameter")
            messagebox.showwarning("Will not upload any parameter", "No parameter was selected for upload")
        # Delete the parameter table and create a new one with the next file if available
        self.on_skip_click(force_focus_out_event=False)

    # This function can recurse multiple times if there is an upload error
    def upload_selected_params(self, selected_params):
        logging_info("Uploading %d selected %s parameters to flight controller...", len(selected_params), self.current_file)

        self.upload_params_that_require_reset(selected_params)

        # Write each selected parameter to the flight controller
        for param_name, param in selected_params.items():
            try:
                self.flight_controller.set_param(param_name, param.value)
                logging_info("Parameter %s set to %f", param_name, param.value)
                if param_name not in self.flight_controller.fc_parameters or \
                   not is_within_tolerance(self.flight_controller.fc_parameters[param_name], param.value):
                    self.at_least_one_changed_parameter_written = True
            except ValueError as e:
                logging_error("Failed to set parameter %s: %s", param_name, e)
                messagebox.showerror("ArduPilot methodic configurator", f"Failed to set parameter {param_name}: {e}")

        if self.at_least_one_changed_parameter_written:
            # Re-download all parameters, in case one of them changed, and validate that all uploads were successful
            self.download_flight_controller_parameters(True)
            logging_info("Re-download all parameters from the flight controller")

            # Validate that the read parameters are the same as the ones in the current_file
            param_upload_error = []
            for param_name, param in selected_params.items():
                if param_name in self.flight_controller.fc_parameters and \
                   param is not None and \
                   not is_within_tolerance(self.flight_controller.fc_parameters[param_name], float(param.value)):
                    logging_error("Parameter %s upload to the flight controller failed. Expected: %f, Actual: %f",
                                  param_name, param.value, self.flight_controller.fc_parameters[param_name])
                    param_upload_error.append(param_name)
                if param_name not in self.flight_controller.fc_parameters:
                    logging_error("Parameter %s upload to the flight controller failed. Expected: %f, Actual: N/A",
                                  param_name, param.value)
                    param_upload_error.append(param_name)

            if param_upload_error:
                if messagebox.askretrycancel("Parameter upload error",
                                             "Failed to upload the following parameters to the flight controller:\n"
                                             f"{(', ').join(param_upload_error)}"):
                    self.upload_selected_params(selected_params)
            else:
                logging_info("All parameters uploaded to the flight controller successfully")
        self.local_filesystem.write_last_uploaded_filename(self.current_file)

    def on_skip_click(self, _event=None, force_focus_out_event=True):
        if force_focus_out_event:
            self.parameter_editor_table.generate_edit_widgets_focus_out()
        self.write_changes_to_intermediate_parameter_file()
        # Find the next filename in the file_parameters dictionary
        files = list(self.local_filesystem.file_parameters.keys())
        if not files:
            return
        try:
            next_file_index = files.index(self.current_file) + 1
            if next_file_index >= len(files):
                self.write_summary_files()
                # Close the application and the connection
                self.close_connection_and_quit()
                return
            next_file = files[next_file_index]
            # Update the Combobox selection to the next file
            self.file_selection_combobox.set(next_file)
            # Trigger the combobox change event to update the table
            self.on_param_file_combobox_change(None)
        except ValueError:
            # If the current file is not found in the list, present a message box
            messagebox.showerror("ArduPilot methodic configurator", "Current file not found in the list of files")
            # Close the application and the connection
            self.close_connection_and_quit()

    def write_changes_to_intermediate_parameter_file(self):
        if self.parameter_editor_table.get_at_least_one_param_edited():
            if messagebox.askyesno("One or more parameters have been edited",
                                   f"Do you want to write the changes to the {self.current_file} file?"):
                self.local_filesystem.export_to_param(self.local_filesystem.file_parameters[self.current_file],
                                                      self.current_file, annotate_doc=self.annotate_params_into_files.get())
        self.parameter_editor_table.set_at_least_one_param_edited(False)

    def write_summary_files(self):
        if not hasattr(self.flight_controller, 'fc_parameters') or self.flight_controller.fc_parameters is None:
            return
        annotated_fc_parameters = self.local_filesystem.annotate_intermediate_comments_to_param_dict(
            self.flight_controller.fc_parameters)
        non_default__read_only_params, non_default__writable_calibrations, non_default__writable_non_calibrations = \
            self.local_filesystem.categorize_parameters(annotated_fc_parameters)

        nr_unchanged_params = len(annotated_fc_parameters) - len(non_default__read_only_params) - \
            len(non_default__writable_calibrations) - len(non_default__writable_non_calibrations)
        # If there are no more files, present a summary message box
        summary_message = f"Methodic configuration of {len(annotated_fc_parameters)} parameters complete:\n\n" \
            f"{nr_unchanged_params} kept their default value\n\n" \
            f"{len(non_default__read_only_params)} non-default read-only parameters - " \
            "ignore these, you can not change them\n\n" \
            f"{len(non_default__writable_calibrations)} non-default writable sensor-calibrations - " \
            "non-reusable between vehicles\n\n" \
            f"{len(non_default__writable_non_calibrations)} non-default writable non-sensor-calibrations - " \
            "these can be reused between similar vehicles"
        messagebox.showinfo("Last parameter file processed", summary_message)
        wrote_complete = self.write_summary_file(annotated_fc_parameters,
                                                 "complete.param", False)
        wrote_read_only = self.write_summary_file(non_default__read_only_params,
                                                  "non-default_read-only.param", False)
        wrote_calibrations = self.write_summary_file(non_default__writable_calibrations,
                                                     "non-default_writable_calibrations.param", False)
        wrote_non_calibrations = self.write_summary_file(non_default__writable_non_calibrations,
                                                         "non-default_writable_non-calibrations.param", False)
        files_to_zip = [
            (wrote_complete, "complete.param"),
            (wrote_read_only, "non-default_read-only.param"),
            (wrote_calibrations, "non-default_writable_calibrations.param"),
            (wrote_non_calibrations, "non-default_writable_non-calibrations.param")]
        self.write_zip_file(files_to_zip)

    def write_summary_file(self, param_dict: dict, filename: str, annotate_doc: bool):
        should_write_file = True
        if param_dict:
            if self.local_filesystem.intermediate_parameter_file_exists(filename):
                should_write_file = messagebox.askyesno("Overwrite existing file",
                                                        f"{filename} file already exists.\nDo you want to overwrite it?")
            if should_write_file:
                self.local_filesystem.export_to_param(param_dict, filename, annotate_doc)
                logging_info("Summary file %s written", filename)
        return should_write_file

    def write_zip_file(self, files_to_zip: List[Tuple[bool, str]]):
        should_write_file = True
        zip_file_path = self.local_filesystem.zip_file_path()
        if self.local_filesystem.zip_file_exists():
            should_write_file = messagebox.askyesno("Overwrite existing file",
                                                    f"{zip_file_path} file already exists.\nDo you want to overwrite it?")
        if should_write_file:
            self.local_filesystem.zip_files(files_to_zip)
            messagebox.showinfo("Parameter files zipped", "All relevant files have been zipped into the \n"
                                f"{zip_file_path} file.\n\nYou can now upload this file to the ArduPilot Methodic\n"
                                "Configuration Blog post on discuss.ardupilot.org.")
        return should_write_file

    def close_connection_and_quit(self):
        self.parameter_editor_table.generate_edit_widgets_focus_out()
        self.write_changes_to_intermediate_parameter_file()
        self.root.quit() # Then stop the Tkinter event loop
