#!/usr/bin/env python3

'''
This file is part of Ardupilot methodic configurator. https://github.com/ArduPilot/MethodicConfigurator

(C) 2024 Amilcar do Carmo Lucas, IAV GmbH

SPDX-License-Identifier:    GPL-3
'''

from sys import exit as sys_exit

import tkinter as tk
from tkinter import messagebox
from tkinter import ttk

from logging import debug as logging_debug
from logging import info as logging_info
from logging import warning as logging_warning
from logging import error as logging_error
from logging import critical as logging_critical

from typing import List
from typing import Tuple

from webbrowser import open as webbrowser_open  # to open the blog post documentation

from PIL import Image
from PIL import ImageTk

from backend_filesystem import LocalFilesystem
from backend_filesystem import is_within_tolerance

from backend_flightcontroller import FlightController

from frontend_tkinter_base import show_tooltip
from frontend_tkinter_base import AutoResizeCombobox
from frontend_tkinter_base import ScrollFrame
from frontend_tkinter_base import BaseWindow

from frontend_tkinter_connection_selection import ConnectionSelectionWidgets

from frontend_tkinter_directory_selection import VehicleDirectorySelectionWidgets


def show_about_window(root, version: str):
    # Create a new window for the custom "About" message
    about_window = tk.Toplevel(root)
    about_window.title("About")
    about_window.geometry("650x220")

    # Add the "About" message
    about_message = f"ArduPilot Methodic Configurator Version: {version}\n\n" \
                    "A clear configuration sequence for ArduPilot vehicles.\n\n" \
                    "Copyright © 2024 Amilcar do Carmo Lucas and ArduPilot.org\n\n" \
                    "Licensed under the GNU General Public License v3.0"
    about_label = tk.Label(about_window, text=about_message, wraplength=450)
    about_label.pack(padx=10, pady=10)

    # Create buttons for each action
    user_manual_button = tk.Button(about_window, text="User Manual",
                                   command=lambda: webbrowser_open(
                                       "https://github.com/ArduPilot/MethodicConfigurator/blob/master/USERMANUAL.md"))
    support_forum_button = tk.Button(about_window, text="Support Forum",
                                     command=lambda: webbrowser_open(
                                         "http://discuss.ardupilot.org/t/new-ardupilot-methodic-configurator-gui/115038/1"))
    report_bug_button = tk.Button(about_window, text="Report a Bug",
                                  command=lambda: webbrowser_open(
                                      "https://github.com/ArduPilot/MethodicConfigurator/issues/new"))
    credits_button = tk.Button(about_window, text="Credits",
                               command=lambda: webbrowser_open(
                                   "https://github.com/ArduPilot/MethodicConfigurator/blob/master/credits/CREDITS.md"))
    source_button = tk.Button(about_window, text="Source Code",
                              command=lambda: webbrowser_open(
                                  "https://github.com/ArduPilot/MethodicConfigurator"))

    # Pack the buttons
    user_manual_button.pack(side=tk.LEFT, padx=10, pady=10)
    support_forum_button.pack(side=tk.LEFT, padx=10, pady=10)
    report_bug_button.pack(side=tk.LEFT, padx=10, pady=10)
    credits_button.pack(side=tk.LEFT, padx=10, pady=10)
    source_button.pack(side=tk.LEFT, padx=10, pady=10)



class ParameterEditorWindow(BaseWindow):  # pylint: disable=too-many-instance-attributes, too-many-public-methods
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

        self.at_least_one_param_edited = False
        self.at_least_one_changed_parameter_written = False
        self.write_checkbutton_var = {}
        self.file_selection_combobox = None
        self.documentation_label_blog = None
        self.documentation_label_wiki = None
        self.documentation_label_extra = None
        self.documentation_label_mandatory = None
        self.show_only_differences = None
        self.scroll_frame = None
        self.reset_progress_window = None
        self.reset_progress_bar = None
        self.reset_progress_label = None
        self.param_read_progress_window = None
        self.param_read_progress_bar = None
        self.param_read_progress_label = None

        self.root.title("Amilcar Lucas's - ArduPilot methodic configurator - " + version)
        self.root.geometry("880x500") # Set the window width

        # Bind the close_connection_and_quit function to the window close event
        self.root.protocol("WM_DELETE_WINDOW", self.close_connection_and_quit)

        self.__create_widgets(version)

    def __create_widgets(self, version: str):  # pylint: disable=too-many-locals, too-many-statements
        config_frame = tk.Frame(self.root)
        config_frame.pack(side=tk.TOP, fill="x", expand=False, pady=(4, 0)) # Pack the frame at the top of the window

        config_subframe = tk.Frame(config_frame)
        config_subframe.pack(side=tk.LEFT, fill="x", expand=True, anchor=tk.NW) # Pack the frame at the top of the window

        # Create a new frame inside the config_subframe for the intermediate parameter file directory selection labels
        # and directory selection button
        directory_selection_frame = VehicleDirectorySelectionWidgets(self, config_subframe, self.local_filesystem,
                                                                     destroy_parent_on_open=False)
        directory_selection_frame.container_frame.pack(side=tk.LEFT, fill="x", expand=False, padx=(4, 6))

        # Create a new frame inside the config_subframe for the intermediate parameter file selection label and combobox
        file_selection_frame = tk.Frame(config_subframe)
        file_selection_frame.pack(side=tk.LEFT, fill="x", expand=False, padx=(6, 6))

        # Create a label for the combobox
        file_selection_label = tk.Label(file_selection_frame, text="Current intermediate parameter file:")
        file_selection_label.pack(side=tk.TOP, anchor=tk.NW) # Add the label to the top of the file_selection_frame

        # Create combobox for intermediate parameter file selection
        self.file_selection_combobox = AutoResizeCombobox(file_selection_frame,
                                                          list(self.local_filesystem.file_parameters.keys()),
                                                          self.current_file,
                                                          "Select the intermediate parameter file from the list of available "
                                                          "files in the selected vehicle directory\nIt will automatically "
                                                          "advance to the next file once the current file is written to the "
                                                          "fight controller",
                                                          state='readonly', width=45)
        self.file_selection_combobox.bind("<<ComboboxSelected>>", self.on_param_file_combobox_change)
        self.file_selection_combobox.pack(side=tk.TOP, anchor=tk.NW, pady=(4, 0))

        # Create a new frame inside the config_subframe for the flight controller connection selection label and combobox
        csw = ConnectionSelectionWidgets(self, config_subframe, self.flight_controller,
                                         destroy_parent_on_connect=False, read_params_on_connect=True)
        csw.container_frame.pack(side=tk.RIGHT, fill="x", expand=False, padx=(6, 4))

        # Load the ArduPilot logo and scale it down to image_height pixels in height
        image_height = 40
        image = Image.open(LocalFilesystem.application_logo_filepath())
        width, height = image.size
        aspect_ratio = width / height
        new_width = int(image_height * aspect_ratio)
        resized_image = image.resize((new_width, image_height))

        # Convert the image to a format that can be used by Tkinter
        photo = ImageTk.PhotoImage(resized_image)

        # Create a label with the resized image
        image_label = tk.Label(config_frame, image=photo)
        image_label.image = photo # Keep a reference to the image to prevent it from being garbage collected
        image_label.pack(side=tk.RIGHT, anchor=tk.NE, padx=(4, 4), pady=(4, 0))
        image_label.bind("<Button-1>", lambda event: show_about_window(self.root, version))
        show_tooltip(image_label, "User Manual, Support Forum, Report a Bug, Credits, Source Code")

        # Create a Frame for the Documentation Content
        documentation_frame = tk.LabelFrame(self.root, text="Documentation")
        documentation_frame.pack(side=tk.TOP, fill="x", expand=False, pady=(4, 4), padx=(4, 4))

        # Create a grid structure within the documentation_frame
        documentation_grid = tk.Frame(documentation_frame)
        documentation_grid.pack(fill="both", expand=True)

        # Create labels for the first column with static descriptive text
        descriptive_texts = ["Forum Blog:", "Wiki:", "External tool:", "Mandatory:"]
        descriptive_tooltips = ["ArduPilot's forum Methodic configuration Blog post relevant for the current file",
                                "ArduPilot's wiki page relevant for the current file",
                                "External tool or documentation relevant for the current file",
                                "Mandatory level of the current file,\n 100% you MUST use this file to configure the "
                                "vehicle,\n 0% you can ignore this file if it does not apply to your vehicle"]
        for i, text in enumerate(descriptive_texts):
            label = tk.Label(documentation_grid, text=text)
            label.grid(row=i, column=0, sticky="w")
            show_tooltip(label, descriptive_tooltips[i])

        # Create labels for the second column with the documentation links
        self.documentation_label_blog = tk.Label(documentation_grid)
        self.documentation_label_wiki = tk.Label(documentation_grid)
        self.documentation_label_extra = tk.Label(documentation_grid)
        self.documentation_label_mandatory = tk.Label(documentation_grid)

        # Grid the documentation labels in the second column
        self.documentation_label_blog.grid(row=0, column=1, sticky="w")
        self.documentation_label_wiki.grid(row=1, column=1, sticky="w")
        self.documentation_label_extra.grid(row=2, column=1, sticky="w")
        self.documentation_label_mandatory.grid(row=3, column=1, sticky="w")

        # Dynamically update the documentation text and URL links
        self.update_documentation_labels()

        self.show_only_differences = tk.BooleanVar(value=False)

        # Create a Frame for the Scrollable Content
        self.scroll_frame = ScrollFrame(self.root)
        self.repopulate_parameter_table(self.current_file)
        self.scroll_frame.pack(side="top", fill="both", expand=True)

        # Create a frame for the buttons
        buttons_frame = tk.Frame(self.root)
        buttons_frame.pack(side="bottom", fill="x", expand=False, pady=(10, 10))

        # Create checkbox for toggling parameter display
        only_changed_checkbox = ttk.Checkbutton(buttons_frame, text="See only changed parameters",
                                                variable=self.show_only_differences,
                                                command=self.on_show_only_changed_checkbox_change)
        only_changed_checkbox.pack(side=tk.LEFT, padx=(8, 8))
        show_tooltip(only_changed_checkbox, "Toggle to show only parameters that will change if/when written to the flight "
                     "controller")

        # Create write button
        write_selected_button = tk.Button(buttons_frame, text="Write selected params to FC, and advance to next param file",
                                          command=self.on_write_selected_click)
        write_selected_button.pack(side=tk.LEFT, padx=(8, 8)) # Add padding on both sides of the write selected button
        show_tooltip(write_selected_button, "Write selected parameters to the flight controller and advance to the next "
                     "intermediate parameter file\nIf changes have been made to the current file it will ask if you want "
                     "to save them\nIt will reset the FC if necessary, re-read all parameters and validate their value")

        # Create skip button
        skip_button = tk.Button(buttons_frame, text="Skip parameter file", command=self.on_skip_click)
        skip_button.pack(side=tk.RIGHT, padx=(8, 8)) # Add right padding to the skip button
        show_tooltip(skip_button, "Skip to the next intermediate parameter file without writing any changes to the flight "
                     "controller\nIf changes have been made to the current file it will ask if you want to save them")

        self.root.after(50, self.read_flight_controller_parameters(reread=False)) # 50 milliseconds
        self.root.mainloop()

    def on_param_file_combobox_change(self, _event, forced: bool = False):
        if not self.file_selection_combobox['values']:
            return
        self.param_edit_widgets_event_generate_focus_out()
        selected_file = self.file_selection_combobox.get()
        if self.current_file != selected_file or forced:
            self.write_changes_to_intermediate_parameter_file()
            # Update the current_file attribute to the selected file
            self.current_file = selected_file
            self.at_least_one_changed_parameter_written = False
            self.update_documentation_labels()
            self.repopulate_parameter_table(selected_file)

    def read_flight_controller_parameters(self, reread: bool = False):
        [self.param_read_progress_window,
         self.param_read_progress_bar,
         self.param_read_progress_label] = self.create_progress_window(("Re-r" if reread else "R") + "eading FC parameters")
        # Download all parameters from the flight controller
        self.flight_controller.fc_parameters = self.flight_controller.read_params(self.update_param_download_progress_bar)
        self.param_read_progress_window.destroy()  # for the case that we are doing test and there is no real FC connected
        if not reread:
            self.on_param_file_combobox_change(None, True) # the initial param read will trigger a table update

    def get_documentation_text_and_url(self, documentation, text_key, url_key):
        if documentation:
            text = documentation.get(text_key, f"No documentation available for {self.current_file} in the "
                                     f"{self.local_filesystem.file_documentation_filename} file")
            url = documentation.get(url_key, None)
        else:
            text = f"File '{self.local_filesystem.file_documentation_filename}' not found. No intermediate parameter " \
                "file documentation available"
            url = None
        return text, url

    def update_documentation_label(self, label, text, url, url_expected=True):
        if url:
            label.config(text=text, fg="blue", cursor="hand2", underline=True)
            label.bind("<Button-1>", lambda event, url=url: webbrowser_open(url))
            show_tooltip(label, url)
        else:
            label.config(text=text, fg="black", cursor="arrow", underline=False)
            label.bind("<Button-1>", lambda event: None)
            if url_expected:
                show_tooltip(label, "Documentation URL not available")

    def update_documentation_labels(self):
        documentation = self.local_filesystem.file_documentation.get(self.current_file, None) if \
            self.local_filesystem.file_documentation else None

        blog_text, blog_url = self.get_documentation_text_and_url(documentation, 'blog_text', 'blog_url')
        self.update_documentation_label(self.documentation_label_blog, blog_text, blog_url)
        wiki_text, wiki_url = self.get_documentation_text_and_url(documentation, 'wiki_text', 'wiki_url')
        self.update_documentation_label(self.documentation_label_wiki, wiki_text, wiki_url)
        external_tool_text, external_tool_url = self.get_documentation_text_and_url(documentation, 'external_tool_text',
                                                                                    'external_tool_url')
        self.update_documentation_label(self.documentation_label_extra, external_tool_text, external_tool_url)
        mandatory_text, mandatory_url = self.get_documentation_text_and_url(documentation, 'mandatory_text', 'mandatory_url')
        self.update_documentation_label(self.documentation_label_mandatory, mandatory_text, mandatory_url, False)

    def repopulate_parameter_table(self, selected_file):
        if not selected_file:
            return  # no file was yet selected, so skip it
        if hasattr(self.flight_controller, 'fc_parameters') and self.flight_controller.fc_parameters:
            fc_parameters = self.flight_controller.fc_parameters
        else:
            fc_parameters = {}
        # Different parameters based on the thresholdfile_value
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
        # Clear the current table
        for widget in self.scroll_frame.view_port.winfo_children():
            widget.destroy()
        # Repopulate the table with the new parameters
        if self.show_only_differences.get():
            self.update_table(different_params, fc_parameters)
        else:
            self.update_table(self.local_filesystem.file_parameters[selected_file], fc_parameters)
        # Scroll to the top of the parameter table
        self.scroll_frame.canvas.yview("moveto", 0)

    def update_table(self, params, fc_parameters):  # pylint: disable=too-many-locals, too-many-statements
        # Create labels for table headers
        headers = ["Parameter", "Current Value", "New Value", "Unit", "Write", "Change Reason"]
        tooltips = ["Parameter name must be ^[A-Z][A-Z_0-9]* and most 16 characters long",
                    "Current value on the flight controller ",
                    "New value from the above selected intermediate parameter file",
                    "Parameter Unit",
                    "When selected, write new value to the flight controller",
                    "Reason why respective parameter changed"]
        for i, header in enumerate(headers):
            label = tk.Label(self.scroll_frame.view_port, text=header)
            label.grid(row=0, column=i, sticky="ew") # Use sticky="ew" to make the label stretch horizontally
            show_tooltip(label, tooltips[i])

        self.write_checkbutton_var = {}
        try:
            # Create the new table
            for i, (param_name, param) in enumerate(params.items()):
                param_metadata = self.local_filesystem.doc_dict.get(param_name, None)
                param_default = self.local_filesystem.param_default_dict.get(param_name, None)

                is_calibration = param_metadata.get('Calibration', False) if param_metadata else False
                is_readonly = param_metadata.get('ReadOnly', False) if param_metadata else False
                parameter_label = tk.Label(self.scroll_frame.view_port, text=param_name + (" " * (16 - len(param_name))),
                                           background="red" if is_readonly else "yellow" if is_calibration else
                                           self.default_background_color)
                if param_name in fc_parameters:
                    value_str = format(fc_parameters[param_name], '.6f').rstrip('0').rstrip('.')
                    if param_default is not None and is_within_tolerance(fc_parameters[param_name], param_default.value):
                        # If it matches, set the background color to light blue
                        flightcontroller_value = tk.Label(self.scroll_frame.view_port, text=value_str,
                                                          background="light blue")
                    else:
                        # Otherwise, set the background color to the default color
                        flightcontroller_value = tk.Label(self.scroll_frame.view_port, text=value_str)
                else:
                    flightcontroller_value = tk.Label(self.scroll_frame.view_port, text="N/A", background="blue")

                new_value_background = "light blue" if param_default is not None and \
                    is_within_tolerance(param.value, param_default.value) else "white"
                new_value_entry = tk.Entry(self.scroll_frame.view_port, width=10, justify=tk.RIGHT,
                                           background=new_value_background)
                new_value_entry.insert(0, format(param.value, '.6f').rstrip('0').rstrip('.'))
                new_value_entry.bind("<FocusOut>", lambda event, current_file=self.current_file, param_name=param_name:
                                     self.on_parameter_value_change(event, current_file, param_name))

                unit_label = tk.Label(self.scroll_frame.view_port, text=param_metadata.get('unit') if param_metadata else "")

                self.write_checkbutton_var[param_name] = tk.BooleanVar(value=True) # Default to selected
                write_write_checkbutton = ttk.Checkbutton(self.scroll_frame.view_port,
                                                          variable=self.write_checkbutton_var[param_name])

                change_reason_entry = tk.Entry(self.scroll_frame.view_port, background="white")
                change_reason_entry.insert(0, "" if param.comment is None else param.comment)
                change_reason_entry.bind("<FocusOut>", lambda event, current_file=self.current_file, param_name=param_name:
                                         self.on_parameter_change_reason_change(event, current_file, param_name))

                doc_tooltip = param_metadata.get('doc_tooltip') if param_metadata else \
                    "No documentation available in apm.pdef.xml for this parameter"
                if doc_tooltip:
                    show_tooltip(parameter_label, doc_tooltip)
                    show_tooltip(flightcontroller_value, doc_tooltip)
                    show_tooltip(new_value_entry, doc_tooltip)
                unit_tooltip = param_metadata.get('unit_tooltip') if param_metadata else \
                    "No documentation available in apm.pdef.xml for this parameter"
                if unit_tooltip:
                    show_tooltip(unit_label, unit_tooltip)
                show_tooltip(write_write_checkbutton, f'When selected write {param_name} new value to the flight controller')
                show_tooltip(change_reason_entry, f'Reason why {param_name} should change to {new_value_entry.get()}')

                row = [
                    parameter_label,
                    flightcontroller_value,
                    new_value_entry,
                    unit_label,
                    write_write_checkbutton,
                    change_reason_entry,
                ]
                for j, widget in enumerate(row):
                    # Use sticky="ew" to make the widget stretch horizontally
                    widget.grid(row=i+1, column=j,
                                sticky="w" if j == 0 else "ew" if j == 5 else "e", padx=(0, 5) if j == 5 else 0)
        except KeyError as e:
            logging_critical("Parameter %s not found in the %s file: %s", param_name, self.current_file, e, exc_info=True)
            sys_exit(1)

        # Configure the table_frame to stretch columns
        self.scroll_frame.view_port.columnconfigure(0, weight=0, minsize=120) # Parameter name
        self.scroll_frame.view_port.columnconfigure(1, weight=0) # Current Value
        self.scroll_frame.view_port.columnconfigure(2, weight=0) # New Value
        self.scroll_frame.view_port.columnconfigure(3, weight=0) # Units
        self.scroll_frame.view_port.columnconfigure(4, weight=0) # write to FC
        self.scroll_frame.view_port.columnconfigure(5, weight=1) # Change reason

    def on_parameter_value_change(self, event, current_file, param_name):
        # Get the new value from the Entry widget
        new_value = event.widget.get()
        try:
            old_value = self.local_filesystem.file_parameters[current_file][param_name].value
        except KeyError as e:
            logging_critical("Parameter %s not found in the %s file: %s", param_name, current_file, e, exc_info=True)
            sys_exit(1)
        valid = True
        # Check if the input is a valid float
        try:
            p = float(new_value)
            changed = not is_within_tolerance(old_value, p)
            param_metadata = self.local_filesystem.doc_dict.get(param_name, None)
            p_min = param_metadata.get('min', None) if param_metadata else None
            p_max = param_metadata.get('max', None) if param_metadata else None
            if changed:
                if p_min and p < p_min:
                    if not messagebox.askyesno("Out-of-bounds Value",
                                               f"The value for {param_name} {p} should be greater than {p_min}\n"
                                               "Use out-of-bounds value?", icon='warning'):
                        valid = False
                if p_max and p > p_max:
                    if not messagebox.askyesno("Out-of-bounds Value",
                                               f"The value for {param_name} {p} should be smaller than {p_max}\n"
                                               "Use out-of-bounds value?", icon='warning'):
                        valid = False
        except ValueError:
            # Optionally, you can handle the invalid value here, for example, by showing an error message
            messagebox.showerror("Invalid Value", f"The value for {param_name} must be a valid float.")
            valid = False
        if valid:
            if changed and not self.at_least_one_param_edited:
                logging_debug("Parameter %s changed, will later ask if change(s) should be saved to file.", param_name)
            self.at_least_one_param_edited = changed or self.at_least_one_param_edited
            # Update the params dictionary with the new value
            self.local_filesystem.file_parameters[current_file][param_name].value = p
        else:
            # Revert to the previous (valid) value
            event.widget.delete(0, tk.END)
            event.widget.insert(0, old_value)
        # Update the background color of the new value Entry widget to light blue if the new value is the default value
        param_default = self.local_filesystem.param_default_dict.get(param_name, None)
        new_value_background = "light blue" if param_default is not None and \
            is_within_tolerance(p, param_default.value) else "white"
        event.widget.config(background=new_value_background)

    def on_parameter_change_reason_change(self, event, current_file, param_name):
        # Get the new value from the Entry widget
        new_value = event.widget.get()
        try:
            changed = new_value != self.local_filesystem.file_parameters[current_file][param_name].comment and \
                not (new_value == "" and self.local_filesystem.file_parameters[current_file][param_name].comment is None)
        except KeyError as e:
            logging_critical("Parameter %s not found in the %s file %s: %s", param_name, self.current_file,
                             new_value, e, exc_info=True)
            sys_exit(1)
        if changed and not self.at_least_one_param_edited:
            logging_debug("Parameter %s change reason changed from %s to %s, will later ask if change(s) should be saved to "
                          "file.",
                          param_name, self.local_filesystem.file_parameters[current_file][param_name].comment, new_value)
        self.at_least_one_param_edited = changed or self.at_least_one_param_edited
        # Update the params dictionary with the new value
        self.local_filesystem.file_parameters[current_file][param_name].comment = new_value

    def get_write_selected_params(self):
        selected_params = {}
        for param_name, checkbutton_state in self.write_checkbutton_var.items():
            if checkbutton_state.get():
                selected_params[param_name] = self.local_filesystem.file_parameters[self.current_file][param_name]
        return selected_params

    def on_show_only_changed_checkbox_change(self):
        self.repopulate_parameter_table(self.current_file)

    def update_reset_progress_bar(self, current_value: int, max_value: int):
        """
        Update the FC reset progress bar and the progress message with the current progress.

        Args:
            current_value (int): The current progress value.
            max_value (int): The maximum progress value.
        """
        self.reset_progress_window.lift()

        self.reset_progress_bar['value'] = current_value
        self.reset_progress_bar['maximum'] = max_value
        self.reset_progress_bar.update()

        # Update the reset progress message
        self.reset_progress_label.config(text=f"waiting for {current_value} of {max_value} seconds")

        # Close the reset progress window when the process is complete
        if current_value == max_value:
            self.reset_progress_window.destroy()

    def update_param_download_progress_bar(self, current_value: int, max_value: int):
        """
        Update the FC parameter read progress bar the progress message with the current progress.

        Args:
            current_value (int): The current progress value.
            max_value (int): The maximum progress value.
        """
        self.param_read_progress_window.lift()

        self.param_read_progress_bar['value'] = current_value
        self.param_read_progress_bar['maximum'] = max_value
        self.param_read_progress_bar.update()

        # Update the param read progress message
        self.param_read_progress_label.config(text=f"Reading parameter {current_value} of {max_value}")

        # Close the param read progress window when the process is complete
        if current_value == max_value:
            self.param_read_progress_window.destroy()

    def param_edit_widgets_event_generate_focus_out(self):
        # Trigger the <FocusOut> event for all entry widgets to ensure all changes are processed
        for widget in self.scroll_frame.view_port.winfo_children():
            if isinstance(widget, tk.Entry):
                widget.event_generate("<FocusOut>", when="now")

    def write_params_that_require_reset(self, selected_params: dict):
        """
        Write the selected parameters to the flight controller that require a reset.

        After the reset, the other parameters that do not require a reset, must still be written to the flight controller.
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
                    elif param_name.endswith(('_TYPE', '_EN', '_ENABLE')):
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

        if not fc_reset_required:
            if fc_reset_unsure:
                # Ask the user if they want to reset the ArduPilot
                fc_reset_required = messagebox.askyesno("Possible reset required", f"{(', ').join(fc_reset_unsure)} parameter"
                                                        "(s) potentially require a reset\nDo you want to reset the ArduPilot?")

        if fc_reset_required:
            [self.reset_progress_window,
             self.reset_progress_bar,
             self.reset_progress_label] = self.create_progress_window("Resetting Flight Controller")
            # Call reset_and_reconnect with a callback to update the reset progress bar and the progress message
            self.flight_controller.reset_and_reconnect(self.update_reset_progress_bar)
            self.reset_progress_window.destroy()  # for the case that we are doing test and there is no real FC connected

    def on_write_selected_click(self):
        self.param_edit_widgets_event_generate_focus_out()

        self.write_changes_to_intermediate_parameter_file()
        selected_params = self.get_write_selected_params()
        if selected_params:
            if hasattr(self.flight_controller, 'fc_parameters') and self.flight_controller.fc_parameters:
                self.write_selected_params(selected_params)
            else:
                logging_warning("No parameters were yet read from the flight controller, will not write any parameter")
                messagebox.showwarning("Will not write any parameter", "No flight controller connection")
        else:
            logging_warning("No parameter was selected for write, will not write any parameter")
            messagebox.showwarning("Will not write any parameter", "No parameter was selected for write")
        # Delete the parameter table and create a new one with the next file if available
        self.on_skip_click(force_focus_out_event=False)

    # This function can recurse multiple time if there is a write error
    def write_selected_params(self, selected_params):
        logging_info("Writing %d selected %s parameters to flight controller...", len(selected_params), self.current_file)

        self.write_params_that_require_reset(selected_params)

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
            # Re-Download all parameters, in case one of them changed, and to validate that all writes where successful
            self.read_flight_controller_parameters(True)
            logging_info("Re-read all parameters from the flight controller")

            # Validate that the read parameters are the same as the ones in the current_file
            param_write_error = []
            for param_name, param in selected_params.items():
                if param_name in self.flight_controller.fc_parameters and \
                   param is not None and \
                   not is_within_tolerance(self.flight_controller.fc_parameters[param_name], float(param.value)):
                    logging_error("Parameter %s write to the flight controller failed. Expected: %f, Actual: %f",
                                  param_name, param.value, self.flight_controller.fc_parameters[param_name])
                    param_write_error.append(param_name)
                if param_name not in self.flight_controller.fc_parameters:
                    logging_error("Parameter %s write to the flight controller failed. Expected: %f, Actual: N/A",
                                  param_name, param.value)
                    param_write_error.append(param_name)

            if param_write_error:
                if messagebox.askretrycancel("Parameter write error",
                                             "Failed to write the following parameters to the flight controller:\n"
                                             f"{(', ').join(param_write_error)}"):
                    self.write_selected_params(selected_params)
            else:
                logging_info("All parameters written to the flight controller successfully")

    def on_skip_click(self, _event=None, force_focus_out_event=True):
        if force_focus_out_event:
            self.param_edit_widgets_event_generate_focus_out()
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
            # Update the combobox selection to the next file
            self.file_selection_combobox.set(next_file)
            # Trigger the combobox change event to update the table
            self.on_param_file_combobox_change(None)
        except ValueError:
            # If the current file is not found in the list, present a message box
            messagebox.showerror("ArduPilot methodic configurator", "Current file not found in the list of files")
            # Close the application and the connection
            self.close_connection_and_quit()

    def write_changes_to_intermediate_parameter_file(self):
        if self.at_least_one_param_edited:
            if messagebox.askyesno("One or more parameters have been edited",
                                   f"Do you want to write the changes to the {self.current_file} file?"):
                self.local_filesystem.export_to_param(self.local_filesystem.file_parameters[self.current_file],
                                                      self.current_file, annotate_doc=False)
        self.at_least_one_param_edited = False

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
        self.root.quit() # Then stop the Tkinter event loop
