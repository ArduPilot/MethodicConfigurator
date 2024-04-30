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
#from logging import info as logging_info
#from logging import warning as logging_warning
#from logging import error as logging_error
from logging import critical as logging_critical

#from backend_filesystem import LocalFilesystem
from backend_filesystem import is_within_tolerance

#from backend_flightcontroller import FlightController

from frontend_tkinter_base import show_tooltip
#from frontend_tkinter_base import AutoResizeCombobox
from frontend_tkinter_base import ScrollFrame



class ParameterEditorTable(ScrollFrame):
    """
    A class to manage and display the parameter editor table within the GUI.

    This class inherits from ScrollFrame and is responsible for creating,
    managing, and updating the table that displays parameters for editing.
    """
    def __init__(self, root, local_filesystem):
        super().__init__(root)
        self.root = root
        self.local_filesystem = local_filesystem
        self.background_color = root.cget("background")
        self.current_file = None
        self.write_checkbutton_var = {}
        self.at_least_one_param_edited = False

    def repopulate(self, selected_file: str, different_params: dict, fc_parameters: dict, show_only_differences: bool):
        for widget in self.view_port.winfo_children():
            widget.destroy()
        self.current_file = selected_file

        # Create labels for table headers
        headers = ["Parameter", "Current Value", "New Value", "Unit", "Write", "Change Reason"]
        tooltips = ["Parameter name must be ^[A-Z][A-Z_0-9]* and most 16 characters long",
                    "Current value on the flight controller ",
                    "New value from the above selected intermediate parameter file",
                    "Parameter Unit",
                    "When selected, write the new value to the flight controller",
                    "Reason why respective parameter changed"]
        for i, header in enumerate(headers):
            label = tk.Label(self.view_port, text=header)
            label.grid(row=0, column=i, sticky="ew") # Use sticky="ew" to make the label stretch horizontally
            show_tooltip(label, tooltips[i])

        self.write_checkbutton_var = {}

        file_documentation = self.local_filesystem.file_documentation
        if file_documentation and selected_file in file_documentation:
            file_info = file_documentation[selected_file]
        else:
            file_info = None

        if show_only_differences:
            self.__update_table(different_params, fc_parameters, file_info)
        else:
            self.__update_table(self.local_filesystem.file_parameters[selected_file], fc_parameters, file_info)
        # Scroll to the top of the parameter table
        self.canvas.yview("moveto", 0)

    def __update_table(self, params, fc_parameters, file_info):  # pylint: disable=too-many-locals
        try:
            for i, (param_name, param) in enumerate(params.items(), 1):
                param_metadata = self.local_filesystem.doc_dict.get(param_name, None)
                param_default = self.local_filesystem.param_default_dict.get(param_name, None)
                doc_tooltip = param_metadata.get('doc_tooltip') if param_metadata else \
                    "No documentation available in apm.pdef.xml for this parameter"

                column_0 = self.__create_parameter_name(param_name, param_metadata, doc_tooltip)
                column_1 = self.__create_flightcontroller_value(fc_parameters, param_name, param_default, doc_tooltip)
                column_2 = self.__create_new_value_entry(param_name, param, param_metadata, file_info,
                                                         param_default, doc_tooltip)
                column_3 = self.__create_unit_label(param_metadata)
                column_4 = self.__create_write_write_checkbutton(param_name)
                column_5 = self.__create_change_reason_entry(param_name, param, column_2, file_info)

                column_0.grid(row=i, column=0, sticky="w", padx=0)
                column_1.grid(row=i, column=1, sticky="e", padx=0)
                column_2.grid(row=i, column=2, sticky="e", padx=0)
                column_3.grid(row=i, column=3, sticky="e", padx=0)
                column_4.grid(row=i, column=4, sticky="e", padx=0)
                column_5.grid(row=i, column=5, sticky="ew", padx=(0, 5))

        except KeyError as e:
            logging_critical("Parameter %s not found in the %s file: %s", param_name, self.current_file, e, exc_info=True)
            sys_exit(1)

        # Configure the table_frame to stretch columns
        self.view_port.columnconfigure(0, weight=0, minsize=120) # Parameter name
        self.view_port.columnconfigure(1, weight=0) # Current Value
        self.view_port.columnconfigure(2, weight=0) # New Value
        self.view_port.columnconfigure(3, weight=0) # Units
        self.view_port.columnconfigure(4, weight=0) # write to FC
        self.view_port.columnconfigure(5, weight=1) # Change Reason

    def __create_parameter_name(self, param_name, param_metadata, doc_tooltip):
        is_calibration = param_metadata.get('Calibration', False) if param_metadata else False
        is_readonly = param_metadata.get('ReadOnly', False) if param_metadata else False
        parameter_label = tk.Label(self.view_port, text=param_name + (" " * (16 - len(param_name))),
                                           background="red" if is_readonly else "yellow" if is_calibration else
                                           self.background_color)
        if doc_tooltip:
            show_tooltip(parameter_label, doc_tooltip)
        return parameter_label

    def __create_flightcontroller_value(self, fc_parameters, param_name, param_default, doc_tooltip):
        if param_name in fc_parameters:
            value_str = format(fc_parameters[param_name], '.6f').rstrip('0').rstrip('.')
            if param_default is not None and is_within_tolerance(fc_parameters[param_name], param_default.value):
                        # If it matches, set the background color to light blue
                flightcontroller_value = tk.Label(self.view_port, text=value_str,
                                                          background="light blue")
            else:
                        # Otherwise, set the background color to the default color
                flightcontroller_value = tk.Label(self.view_port, text=value_str)
        else:
            flightcontroller_value = tk.Label(self.view_port, text="N/A", background="orange")
        if doc_tooltip:
            show_tooltip(flightcontroller_value, doc_tooltip)
        return flightcontroller_value

    @staticmethod
    def __update_new_value_entry_text(new_value_entry: tk.Entry, value: float, param_default):
        new_value_entry.delete(0, tk.END)
        text = format(value, '.6f').rstrip('0').rstrip('.')
        new_value_entry.insert(0, text)
        new_value_background = "light blue" if param_default is not None and \
            is_within_tolerance(value, param_default.value) else "white"
        new_value_entry.config(background=new_value_background)

    def __create_new_value_entry(self, param_name, param,  # pylint: disable=too-many-arguments
                                 param_metadata, file_info, param_default, doc_tooltip):

        present_as_forced = False
        if file_info and 'forced_parameters' in file_info and param_name in file_info['forced_parameters']:
            present_as_forced = True
            if "New Value" in file_info['forced_parameters'][param_name] and \
               param.value != file_info['forced_parameters'][param_name]["New Value"]:
                param.value = file_info['forced_parameters'][param_name]["New Value"]
                self.at_least_one_param_edited = True
        if file_info and 'derived_parameters' in file_info and param_name in file_info['derived_parameters']:
            present_as_forced = True
            if "New Value" in file_info['derived_parameters'][param_name]:
                # Prepare a dictionary that maps variable names to their values
                local_vars = {
                    'vehicle_components': self.local_filesystem.vehicle_components['Components'],
                    'fc_parameters': self.local_filesystem.file_parameters[self.current_file],
                    # Add any other variables you want to make accessible within the eval expression
                }
                eval_result = eval(file_info['derived_parameters'][param_name]["New Value"],  # pylint: disable=eval-used
                                   {}, local_vars)
                if param.value != eval_result:
                    param.value = eval_result
                    self.at_least_one_param_edited = True

        new_value_entry = tk.Entry(self.view_port, width=10, justify=tk.RIGHT)
        ParameterEditorTable.__update_new_value_entry_text(new_value_entry, param.value, param_default)
        bitmask_dict = param_metadata.get('Bitmask', None) if param_metadata else None
        try:
            old_value = self.local_filesystem.file_parameters[self.current_file][param_name].value
        except KeyError as e:
            logging_critical("Parameter %s not found in the %s file: %s", param_name, self.current_file, e, exc_info=True)
            sys_exit(1)
        if present_as_forced:
            new_value_entry.config(state='disabled', background='light grey')
        else:
            if bitmask_dict:
                new_value_entry.bind("<FocusIn>", lambda event:
                                    self.__open_bitmask_selection_window(event, param_name, bitmask_dict, old_value))
            else:
                new_value_entry.bind("<FocusOut>", lambda event, current_file=self.current_file, param_name=param_name:
                                        self.__on_parameter_value_change(event, current_file, param_name))
        if doc_tooltip:
            show_tooltip(new_value_entry, doc_tooltip)
        return new_value_entry

    def __open_bitmask_selection_window(self, event, param_name, bitmask_dict, old_value):  # pylint: disable=too-many-locals
        def on_close():
            checked_keys = [key for key, var in checkbox_vars.items() if var.get()]
            # Convert checked keys back to a decimal value
            new_decimal_value = sum(1 << key for key in checked_keys)
            # Update new_value_entry with the new decimal value
            ParameterEditorTable.__update_new_value_entry_text(event.widget,
                                                               new_decimal_value,
                                                               self.local_filesystem.param_default_dict.get(param_name, None))
            self.at_least_one_param_edited = (old_value != new_decimal_value) or self.at_least_one_param_edited
            self.local_filesystem.file_parameters[self.current_file][param_name].value = new_decimal_value
            # Destroy the window
            window.destroy()
            # Issue a FocusIn event on something else than new_value_entry to prevent endless looping
            self.root.focus_set()
            # Run the Tk event loop once to process the event
            self.root.update_idletasks()
            # Re-bind the FocusIn event to new_value_entry
            event.widget.bind("<FocusIn>", lambda event:
                                        self.__open_bitmask_selection_window(event, param_name, bitmask_dict, old_value))

        def update_label():
            checked_keys = [key for key, var in checkbox_vars.items() if var.get()]
            new_decimal_value = sum(1 << key for key in checked_keys)
            close_label.config(text=f"{param_name} Value: {new_decimal_value}")

        # Temporarily unbind the FocusIn event to prevent triggering the window again
        event.widget.unbind("<FocusIn>")
        window = tk.Toplevel(self.root)
        window.title(f"Select {param_name} Bitmask Options")
        checkbox_vars = {}

        # Convert current_value to a set of checked keys
        current_value = int(event.widget.get())
        checked_keys = {key for key, _value in bitmask_dict.items() if (current_value >> key) & 1}

        for i, (key, value) in enumerate(bitmask_dict.items()):
            var = tk.BooleanVar(value=key in checked_keys)
            checkbox_vars[key] = var
            checkbox = tk.Checkbutton(window, text=value, variable=var, command=update_label)
            checkbox.grid(row=i, column=0, sticky="w")

        # Calculate new_decimal_value here to ensure it's accessible when creating the label
        new_decimal_value = sum(1 << key for key in checked_keys)

        # Replace the close button with a read-only label displaying the current new_decimal_value
        close_label = tk.Label(window, text=f"{param_name} Value: {new_decimal_value}", state='disabled')
        close_label.grid(row=len(bitmask_dict), column=0, pady=10)

        # Bind the on_close function to the window's WM_DELETE_WINDOW protocol
        window.protocol("WM_DELETE_WINDOW", on_close)

        # Make sure the window is visible before disabling the parent window
        window.deiconify()
        self.root.update_idletasks()
        window.grab_set()

        window.wait_window() # Wait for the window to be closed

    def __create_unit_label(self, param_metadata):
        unit_label = tk.Label(self.view_port, text=param_metadata.get('unit') if param_metadata else "")
        unit_tooltip = param_metadata.get('unit_tooltip') if param_metadata else \
            "No documentation available in apm.pdef.xml for this parameter"
        if unit_tooltip:
            show_tooltip(unit_label, unit_tooltip)
        return unit_label

    def __create_write_write_checkbutton(self, param_name):
        self.write_checkbutton_var[param_name] = tk.BooleanVar(value=True) # Default to selected
        write_write_checkbutton = ttk.Checkbutton(self.view_port,
                                                          variable=self.write_checkbutton_var[param_name])
        show_tooltip(write_write_checkbutton, f'When selected write {param_name} new value to the flight controller')
        return write_write_checkbutton

    def __create_change_reason_entry(self, param_name, param, new_value_entry, file_info):

        present_as_forced = False
        if file_info and 'forced_parameters' in file_info and param_name in file_info['forced_parameters']:
            present_as_forced = True
            if "Change Reason" in file_info['forced_parameters'][param_name] and \
               param.comment != file_info['forced_parameters'][param_name]["Change Reason"]:
                param.comment = file_info['forced_parameters'][param_name]["Change Reason"]
                self.at_least_one_param_edited = True
        if file_info and 'derived_parameters' in file_info and param_name in file_info['derived_parameters']:
            present_as_forced = True
            if "Change Reason" in file_info['derived_parameters'][param_name] and \
               param.comment != file_info['derived_parameters'][param_name]["Change Reason"]:
                param.comment = file_info['derived_parameters'][param_name]["Change Reason"]
                self.at_least_one_param_edited = True

        change_reason_entry = tk.Entry(self.view_port, background="white")
        change_reason_entry.insert(0, "" if param.comment is None else param.comment)
        if present_as_forced:
            change_reason_entry.config(state='disabled', background='light grey')
        else:
            change_reason_entry.bind("<FocusOut>", lambda event, current_file=self.current_file, param_name=param_name:
                                     self.__on_parameter_change_reason_change(event, current_file, param_name))
        show_tooltip(change_reason_entry, f'Reason why {param_name} should change to {new_value_entry.get()}')
        return change_reason_entry

    def __on_parameter_value_change(self, event, current_file, param_name):
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
            p = old_value
        ParameterEditorTable.__update_new_value_entry_text(event.widget, p,
                                                           self.local_filesystem.param_default_dict.get(param_name, None))

    def __on_parameter_change_reason_change(self, event, current_file, param_name):
        # Get the new value from the Entry widget
        new_value = event.widget.get()
        try:
            changed = new_value != self.local_filesystem.file_parameters[current_file][param_name].comment and \
                not (new_value == "" and self.local_filesystem.file_parameters[current_file][param_name].comment is None)
        except KeyError as e:
            logging_critical("Parameter %s not found in the %s file %s: %s", param_name, current_file,
                             new_value, e, exc_info=True)
            sys_exit(1)
        if changed and not self.at_least_one_param_edited:
            logging_debug("Parameter %s change reason changed from %s to %s, will later ask if change(s) should be saved to "
                          "file.",
                          param_name, self.local_filesystem.file_parameters[current_file][param_name].comment, new_value)
        self.at_least_one_param_edited = changed or self.at_least_one_param_edited
        # Update the params dictionary with the new value
        self.local_filesystem.file_parameters[current_file][param_name].comment = new_value

    def get_write_selected_params(self, current_file: str):
        selected_params = {}
        for param_name, checkbutton_state in self.write_checkbutton_var.items():
            if checkbutton_state.get():
                selected_params[param_name] = self.local_filesystem.file_parameters[current_file][param_name]
        return selected_params

    def generate_edit_widgets_focus_out(self):
        # Trigger the <FocusOut> event for all entry widgets to ensure all changes are processed
        for widget in self.view_port.winfo_children():
            if isinstance(widget, tk.Entry):
                widget.event_generate("<FocusOut>", when="now")

    def get_at_least_one_param_edited(self):
        return self.at_least_one_param_edited

    def set_at_least_one_param_edited(self, value):
        self.at_least_one_param_edited = value
