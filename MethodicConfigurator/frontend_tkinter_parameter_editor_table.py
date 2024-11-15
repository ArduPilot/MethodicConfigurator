#!/usr/bin/env python3

"""
This file is part of Ardupilot methodic configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import tkinter as tk

# from logging import warning as logging_warning
# from logging import error as logging_error
from logging import critical as logging_critical
from logging import debug as logging_debug
from logging import info as logging_info
from platform import system as platform_system
from sys import exit as sys_exit
from tkinter import messagebox, ttk
from typing import Union

from MethodicConfigurator import _
from MethodicConfigurator.annotate_params import Par

# from MethodicConfigurator.backend_filesystem import LocalFilesystem
from MethodicConfigurator.backend_filesystem import is_within_tolerance

# from MethodicConfigurator.backend_flightcontroller import FlightController
# from MethodicConfigurator.frontend_tkinter_base import AutoResizeCombobox
from MethodicConfigurator.frontend_tkinter_base import BaseWindow, ScrollFrame, get_widget_font, show_tooltip
from MethodicConfigurator.frontend_tkinter_entry_dynamic import EntryWithDynamicalyFilteredListbox
from MethodicConfigurator.frontend_tkinter_pair_tuple_combobox import PairTupleCombobox

NEW_VALUE_WIDGET_WIDTH = 9


class ParameterEditorTable(ScrollFrame):  # pylint: disable=too-many-ancestors
    """
    A class to manage and display the parameter editor table within the GUI.

    This class inherits from ScrollFrame and is responsible for creating,
    managing, and updating the table that displays parameters for editing.
    """

    def __init__(self, root, local_filesystem, parameter_editor):
        super().__init__(root)
        self.root = root
        self.local_filesystem = local_filesystem
        self.parameter_editor = parameter_editor
        self.current_file = None
        self.upload_checkbutton_var = {}
        self.at_least_one_param_edited = False

        style = ttk.Style()
        style.configure("narrow.TButton", padding=0, width=4, border=(0, 0, 0, 0))

        # Prepare a dictionary that maps variable names to their values
        # These variables are used by the forced_parameters and derived_parameters in configuration_steps_*.json files
        self.variables = local_filesystem.get_eval_variables()

        self.compute_forced_and_derived_parameters()

    def compute_forced_and_derived_parameters(self):
        if self.local_filesystem.configuration_steps:
            for filename, file_info in self.local_filesystem.configuration_steps.items():
                error_msg = self.local_filesystem.compute_parameters(filename, file_info, "forced", self.variables)
                if error_msg:
                    messagebox.showerror(_("Error in forced parameters"), error_msg)
                else:
                    self.add_forced_or_derived_parameters(filename, self.local_filesystem.forced_parameters)
                # error_msg = self.local_filesystem.compute_parameters(filename, file_info, 'derived', self.variables)
                # if error_msg:
                #    messagebox.showerror("Error in derived parameters", error_msg)

    def add_forced_or_derived_parameters(self, filename, new_parameters, fc_parameters=None):
        """Add forced parameters not yet in the parameter list to the parameter list"""
        if filename in new_parameters:
            for param_name, param in new_parameters[filename].items():
                if filename not in self.local_filesystem.file_parameters:
                    continue
                if param_name not in self.local_filesystem.file_parameters[filename] and (
                    fc_parameters is None or param_name in fc_parameters
                ):
                    self.local_filesystem.file_parameters[filename][param_name] = param

    def repopulate(self, selected_file: str, fc_parameters: dict, show_only_differences: bool):
        for widget in self.view_port.winfo_children():
            widget.destroy()
        self.current_file = selected_file

        # Create labels for table headers
        headers = [_("-/+"), _("Parameter"), _("Current Value"), _("New Value"), _("Unit"), _("Upload"), _("Change Reason")]
        tooltips = [
            _("Delete or add a parameter"),
            _("Parameter name must be ^[A-Z][A-Z_0-9]* and most 16 characters long"),
            _("Current value on the flight controller "),
            _("New value from the above selected intermediate parameter file"),
            _("Parameter Unit"),
            _("When selected, upload the new value to the flight controller"),
            _("Reason why respective parameter changed"),
        ]

        for i, header in enumerate(headers):
            label = ttk.Label(self.view_port, text=header)
            label.grid(row=0, column=i, sticky="ew")  # Use sticky="ew" to make the label stretch horizontally
            show_tooltip(label, tooltips[i])

        self.upload_checkbutton_var = {}

        # re-compute derived parameters because the fc_parameters values might have changed
        if self.local_filesystem.configuration_steps and selected_file in self.local_filesystem.configuration_steps:
            self.variables["fc_parameters"] = fc_parameters
            error_msg = self.local_filesystem.compute_parameters(
                selected_file, self.local_filesystem.configuration_steps[selected_file], "derived", self.variables
            )
            if error_msg:
                messagebox.showerror(_("Error in derived parameters"), error_msg)
            else:
                # Add derived parameters not yet in the parameter list to the parameter list
                self.add_forced_or_derived_parameters(selected_file, self.local_filesystem.derived_parameters, fc_parameters)

            self.rename_fc_connection(selected_file)

        if show_only_differences:
            # recompute different_params because of renames and derived values changes
            different_params = {
                param_name: file_value
                for param_name, file_value in self.local_filesystem.file_parameters[selected_file].items()
                if param_name not in fc_parameters
                or (
                    param_name in fc_parameters and not is_within_tolerance(fc_parameters[param_name], float(file_value.value))
                )
            }
            self.__update_table(different_params, fc_parameters)
            if not different_params:
                info_msg = _("No different parameters found in {selected_file}. Skipping...").format(**locals())
                logging_info(info_msg)
                messagebox.showinfo(_("ArduPilot methodic configurator"), info_msg)
                self.parameter_editor.on_skip_click(force_focus_out_event=False)
                return
        else:
            self.__update_table(self.local_filesystem.file_parameters[selected_file], fc_parameters)
        # Scroll to the top of the parameter table
        self.canvas.yview("moveto", 0)

    def rename_fc_connection(self, selected_file):
        renames = {}
        if "rename_connection" in self.local_filesystem.configuration_steps[selected_file]:
            new_connection_prefix = self.local_filesystem.configuration_steps[selected_file]["rename_connection"]
            new_connection_prefix = eval(str(new_connection_prefix), {}, self.variables)  # noqa: S307 pylint: disable=eval-used
            for param_name in self.local_filesystem.file_parameters[selected_file]:
                new_prefix = new_connection_prefix
                old_prefix = param_name.split("_")[0]

                # Handle CAN parameter names peculiarities
                if new_connection_prefix[:-1] == "CAN" and "CAN_P" in param_name:
                    old_prefix = param_name.split("_")[0] + "_" + param_name.split("_")[1]
                    new_prefix = "CAN_P" + new_connection_prefix[-1]
                if new_connection_prefix[:-1] == "CAN" and "CAN_D" in param_name:
                    old_prefix = param_name.split("_")[0] + "_" + param_name.split("_")[1]
                    new_prefix = "CAN_D" + new_connection_prefix[-1]

                if new_connection_prefix[:-1] in old_prefix:
                    renames[param_name] = param_name.replace(old_prefix, new_prefix)

        new_names = set()
        for old_name, new_name in renames.items():
            if new_name in new_names:
                self.local_filesystem.file_parameters[selected_file].pop(old_name)
                logging_info(_("Removing duplicate parameter %s"), old_name)
                info_msg = _("The parameter '{old_name}' was removed due to duplication.")
                messagebox.showinfo(_("Parameter Removed"), info_msg.format(**locals()))
            else:
                new_names.add(new_name)
                if new_name != old_name:
                    self.local_filesystem.file_parameters[selected_file][new_name] = self.local_filesystem.file_parameters[
                        selected_file
                    ].pop(old_name)
                    logging_info(_("Renaming parameter %s to %s"), old_name, new_name)
                    info_msg = _(
                        "The parameter '{old_name}' was renamed to '{new_name}'.\n"
                        "to obey the flight controller connection defined in the component editor window."
                    )
                    messagebox.showinfo(_("Parameter Renamed"), info_msg.format(**locals()))

    def __update_table(self, params, fc_parameters):
        try:
            for i, (param_name, param) in enumerate(params.items(), 1):
                param_metadata = self.local_filesystem.doc_dict.get(param_name, None)
                param_default = self.local_filesystem.param_default_dict.get(param_name, None)
                doc_tooltip = (
                    param_metadata.get("doc_tooltip")
                    if param_metadata
                    else _("No documentation available in apm.pdef.xml for this parameter")
                )

                column = []
                column.append(self.__create_delete_button(param_name))
                column.append(self.__create_parameter_name(param_name, param_metadata, doc_tooltip))
                column.append(self.__create_flightcontroller_value(fc_parameters, param_name, param_default, doc_tooltip))
                column.append(self.__create_new_value_entry(param_name, param, param_metadata, param_default, doc_tooltip))
                column.append(self.__create_unit_label(param_metadata))
                column.append(self.__create_upload_checkbutton(param_name, bool(fc_parameters)))
                column.append(self.__create_change_reason_entry(param_name, param, column[3]))

                column[0].grid(row=i, column=0, sticky="w", padx=0)
                column[1].grid(row=i, column=1, sticky="w", padx=0)
                column[2].grid(row=i, column=2, sticky="e", padx=0)
                column[3].grid(row=i, column=3, sticky="e", padx=0)
                column[4].grid(row=i, column=4, sticky="e", padx=0)
                column[5].grid(row=i, column=5, sticky="e", padx=0)
                column[6].grid(row=i, column=6, sticky="ew", padx=(0, 5))

            # Add the "Add" button at the bottom of the table
            add_button = ttk.Button(
                self.view_port, text=_("Add"), style="narrow.TButton", command=lambda: self.__on_parameter_add(fc_parameters)
            )
            tooltip_msg = _("Add a parameter to the {self.current_file} file")
            show_tooltip(add_button, tooltip_msg.format(**locals()))
            add_button.grid(row=len(params) + 2, column=0, sticky="w", padx=0)

        except KeyError as e:
            logging_critical(_("Parameter %s not found in the %s file: %s"), param_name, self.current_file, e, exc_info=True)
            sys_exit(1)

        # Configure the table_frame to stretch columns
        self.view_port.columnconfigure(0, weight=0)  # Delete and Add buttons
        self.view_port.columnconfigure(1, weight=0, minsize=120)  # Parameter name
        self.view_port.columnconfigure(2, weight=0)  # Current Value
        self.view_port.columnconfigure(3, weight=0)  # New Value
        self.view_port.columnconfigure(4, weight=0)  # Units
        self.view_port.columnconfigure(5, weight=0)  # Upload to FC
        self.view_port.columnconfigure(6, weight=1)  # Change Reason

    def __create_delete_button(self, param_name):
        delete_button = ttk.Button(
            self.view_port, text=_("Del"), style="narrow.TButton", command=lambda: self.__on_parameter_delete(param_name)
        )
        tooltip_msg = _("Delete {param_name} from the {self.current_file} file")
        show_tooltip(delete_button, tooltip_msg.format(**locals()))
        return delete_button

    def __create_parameter_name(self, param_name, param_metadata, doc_tooltip):
        is_calibration = param_metadata.get("Calibration", False) if param_metadata else False
        is_readonly = param_metadata.get("ReadOnly", False) if param_metadata else False
        parameter_label = ttk.Label(
            self.view_port,
            text=param_name + (" " * (16 - len(param_name))),
            background="red"
            if is_readonly
            else "yellow"
            if is_calibration
            else ttk.Style(self.root).lookup("TFrame", "background"),
        )
        if doc_tooltip:
            show_tooltip(parameter_label, doc_tooltip)
        return parameter_label

    def __create_flightcontroller_value(self, fc_parameters, param_name, param_default, doc_tooltip):
        if param_name in fc_parameters:
            value_str = format(fc_parameters[param_name], ".6f").rstrip("0").rstrip(".")
            if param_default is not None and is_within_tolerance(fc_parameters[param_name], param_default.value):
                # If it matches, set the background color to light blue
                flightcontroller_value = ttk.Label(self.view_port, text=value_str, background="light blue")
            else:
                # Otherwise, set the background color to the default color
                flightcontroller_value = ttk.Label(self.view_port, text=value_str)
        else:
            flightcontroller_value = ttk.Label(self.view_port, text=_("N/A"), background="orange")
        if doc_tooltip:
            show_tooltip(flightcontroller_value, doc_tooltip)
        return flightcontroller_value

    def __update_combobox_style_on_selection(self, combobox_widget, param_default, event):
        try:
            current_value = float(combobox_widget.get_selected_key())
            has_default_value = param_default is not None and is_within_tolerance(current_value, param_default.value)
            combobox_widget.configure(style="default_v.TCombobox" if has_default_value else "readonly.TCombobox")
            event.width = NEW_VALUE_WIDGET_WIDTH
            combobox_widget.on_combo_configure(event)
        except ValueError:
            msg = _("Could not solve the selected {combobox_widget} key to a float value.")
            logging_info(msg.format(**locals()))

    @staticmethod
    def __update_new_value_entry_text(new_value_entry: ttk.Entry, value: float, param_default):
        if isinstance(new_value_entry, PairTupleCombobox):
            return
        new_value_entry.delete(0, tk.END)
        value_str = format(value, ".6f").rstrip("0").rstrip(".")
        new_value_entry.insert(0, value_str)
        if param_default is not None and is_within_tolerance(value, param_default.value):
            new_value_entry.configure(style="default_v.TEntry")
        else:
            new_value_entry.configure(style="TEntry")

    def __create_new_value_entry(  # pylint: disable=too-many-arguments
        self,
        param_name,
        param,
        param_metadata,
        param_default,
        doc_tooltip,
    ):
        present_as_forced = False
        if (
            self.current_file in self.local_filesystem.forced_parameters
            and param_name in self.local_filesystem.forced_parameters[self.current_file]
        ):
            present_as_forced = True
            if not is_within_tolerance(
                param.value, self.local_filesystem.forced_parameters[self.current_file][param_name].value
            ):
                param.value = self.local_filesystem.forced_parameters[self.current_file][param_name].value
                self.at_least_one_param_edited = True
        if (
            self.current_file in self.local_filesystem.derived_parameters
            and param_name in self.local_filesystem.derived_parameters[self.current_file]
        ):
            present_as_forced = True
            if not is_within_tolerance(
                param.value, self.local_filesystem.derived_parameters[self.current_file][param_name].value
            ):
                param.value = self.local_filesystem.derived_parameters[self.current_file][param_name].value
                self.at_least_one_param_edited = True

        bitmask_dict = None
        value_str = format(param.value, ".6f").rstrip("0").rstrip(".")
        new_value_entry: Union[PairTupleCombobox, ttk.Entry]
        if (
            param_metadata
            and "values" in param_metadata
            and param_metadata["values"]
            and value_str in param_metadata["values"]
        ):
            selected_value = param_metadata["values"].get(value_str, None)
            has_default_value = param_default is not None and is_within_tolerance(param.value, param_default.value)
            new_value_entry = PairTupleCombobox(
                self.view_port,
                param_metadata["values"],
                value_str,
                param_name,
                style="TCombobox"
                if present_as_forced
                else "default_v.TCombobox"
                if has_default_value
                else "readonly.TCombobox",
            )
            new_value_entry.set(selected_value)
            font = get_widget_font(new_value_entry)
            font["size"] -= 2 if platform_system() == "Windows" else 1
            new_value_entry.config(state="readonly", width=NEW_VALUE_WIDGET_WIDTH, font=(font["family"], font["size"]))
            new_value_entry.bind(
                "<<ComboboxSelected>>",
                lambda event: self.__update_combobox_style_on_selection(new_value_entry, param_default, event),
                "+",
            )
        else:
            new_value_entry = ttk.Entry(self.view_port, width=NEW_VALUE_WIDGET_WIDTH + 1, justify=tk.RIGHT)
            ParameterEditorTable.__update_new_value_entry_text(new_value_entry, param.value, param_default)
            bitmask_dict = param_metadata.get("Bitmask", None) if param_metadata else None
        try:
            old_value = self.local_filesystem.file_parameters[self.current_file][param_name].value
        except KeyError as e:
            logging_critical(_("Parameter %s not found in the %s file: %s"), param_name, self.current_file, e, exc_info=True)
            sys_exit(1)
        if present_as_forced:
            new_value_entry.config(state="disabled", background="light grey")
        elif bitmask_dict:
            new_value_entry.bind(
                "<FocusIn>", lambda event: self.__open_bitmask_selection_window(event, param_name, bitmask_dict, old_value)
            )
        else:
            # pylint: disable=line-too-long
            new_value_entry.bind(
                "<FocusOut>",
                lambda event, current_file=self.current_file, param_name=param_name: self.__on_parameter_value_change(  # type: ignore[misc]
                    event, current_file, param_name
                ),
            )
            # pylint: enable=line-too-long
        if doc_tooltip:
            show_tooltip(new_value_entry, doc_tooltip)
        return new_value_entry

    def __open_bitmask_selection_window(self, event, param_name, bitmask_dict, old_value):  # pylint: disable=too-many-locals
        def on_close():
            checked_keys = [key for key, var in checkbox_vars.items() if var.get()]
            # Convert checked keys back to a decimal value
            new_decimal_value = sum(1 << key for key in checked_keys)
            # Update new_value_entry with the new decimal value
            ParameterEditorTable.__update_new_value_entry_text(
                event.widget, new_decimal_value, self.local_filesystem.param_default_dict.get(param_name, None)
            )
            self.at_least_one_param_edited = (old_value != new_decimal_value) or self.at_least_one_param_edited
            self.local_filesystem.file_parameters[self.current_file][param_name].value = new_decimal_value
            # Destroy the window
            window.destroy()
            # Issue a FocusIn event on something else than new_value_entry to prevent endless looping
            self.root.focus_set()
            # Run the Tk event loop once to process the event
            self.root.update_idletasks()
            # Re-bind the FocusIn event to new_value_entry
            event.widget.bind(
                "<FocusIn>", lambda event: self.__open_bitmask_selection_window(event, param_name, bitmask_dict, old_value)
            )

        def get_param_value_msg(_param_name, checked_keys) -> str:
            _new_decimal_value = sum(1 << key for key in checked_keys)
            text = _("{_param_name} Value: {_new_decimal_value}")
            return text.format(**locals())

        def update_label():
            checked_keys = [key for key, var in checkbox_vars.items() if var.get()]
            close_label.config(text=get_param_value_msg(param_name, checked_keys))

        # Temporarily unbind the FocusIn event to prevent triggering the window again
        event.widget.unbind("<FocusIn>")
        window = tk.Toplevel(self.root)
        title = _("Select {param_name} Bitmask Options")
        window.title(title.format(**locals()))
        checkbox_vars = {}

        main_frame = ttk.Frame(window)
        main_frame.pack(expand=True, fill=tk.BOTH)

        # Convert current_value to a set of checked keys
        current_value = int(event.widget.get())
        checked_keys = {key for key, _value in bitmask_dict.items() if (current_value >> key) & 1}

        for i, (key, value) in enumerate(bitmask_dict.items()):
            var = tk.BooleanVar(value=key in checked_keys)
            checkbox_vars[key] = var
            checkbox = ttk.Checkbutton(main_frame, text=value, variable=var, command=update_label)
            checkbox.grid(row=i, column=0, sticky="w")

        # Replace the close button with a read-only label displaying the current new_decimal_value
        close_label = ttk.Label(main_frame, text=get_param_value_msg(param_name, checked_keys))
        close_label.grid(row=len(bitmask_dict), column=0, pady=10)

        # Bind the on_close function to the window's WM_DELETE_WINDOW protocol
        window.protocol("WM_DELETE_WINDOW", on_close)

        # Make sure the window is visible before disabling the parent window
        window.deiconify()
        self.root.update_idletasks()
        window.grab_set()

        window.wait_window()  # Wait for the window to be closed

    def __create_unit_label(self, param_metadata):
        unit_label = ttk.Label(self.view_port, text=param_metadata.get("unit") if param_metadata else "")
        unit_tooltip = (
            param_metadata.get("unit_tooltip")
            if param_metadata
            else _("No documentation available in apm.pdef.xml for this parameter")
        )
        if unit_tooltip:
            show_tooltip(unit_label, unit_tooltip)
        return unit_label

    def __create_upload_checkbutton(self, param_name, fc_connected):
        self.upload_checkbutton_var[param_name] = tk.BooleanVar(value=fc_connected)
        upload_checkbutton = ttk.Checkbutton(self.view_port, variable=self.upload_checkbutton_var[param_name])
        upload_checkbutton.configure(state="normal" if fc_connected else "disabled")
        msg = _("When selected upload {param_name} new value to the flight controller")
        show_tooltip(upload_checkbutton, msg.format(**locals()))
        return upload_checkbutton

    def __create_change_reason_entry(self, param_name, param, new_value_entry):
        present_as_forced = False
        if (
            self.current_file in self.local_filesystem.forced_parameters
            and param_name in self.local_filesystem.forced_parameters[self.current_file]
        ):
            present_as_forced = True
            if param.comment != self.local_filesystem.forced_parameters[self.current_file][param_name].comment:
                param.comment = self.local_filesystem.forced_parameters[self.current_file][param_name].comment
                self.at_least_one_param_edited = True
        if (
            self.current_file in self.local_filesystem.derived_parameters
            and param_name in self.local_filesystem.derived_parameters[self.current_file]
        ):
            present_as_forced = True
            if param.comment != self.local_filesystem.derived_parameters[self.current_file][param_name].comment:
                param.comment = self.local_filesystem.derived_parameters[self.current_file][param_name].comment
                self.at_least_one_param_edited = True

        change_reason_entry = ttk.Entry(self.view_port, background="white")
        change_reason_entry.insert(0, "" if param.comment is None else param.comment)
        if present_as_forced:
            change_reason_entry.config(state="disabled", background="light grey")
        else:
            # pylint: disable=line-too-long
            change_reason_entry.bind(
                "<FocusOut>",
                lambda event, current_file=self.current_file, param_name=param_name: self.__on_parameter_change_reason_change(  # type: ignore[misc]
                    event, current_file, param_name
                ),
            )
            # pylint: enable=line-too-long
        _value = new_value_entry.get()
        msg = _("Reason why {param_name} should change to {_value}")
        show_tooltip(change_reason_entry, msg.format(**locals()))
        return change_reason_entry

    def __on_parameter_delete(self, param_name):
        msg = _("Are you sure you want to delete the {param_name} parameter?")
        if messagebox.askyesno(f"{self.current_file}", msg.format(**locals())):
            # Capture current vertical scroll position
            current_scroll_position = self.canvas.yview()[0]

            # Delete the parameter
            del self.local_filesystem.file_parameters[self.current_file][param_name]
            self.at_least_one_param_edited = True
            self.parameter_editor.repopulate_parameter_table(self.current_file)

            # Restore the scroll position
            self.canvas.yview_moveto(current_scroll_position)

    def __on_parameter_add(self, fc_parameters):
        add_parameter_window = BaseWindow(self.root)
        add_parameter_window.root.title(_("Add Parameter to ") + self.current_file)
        add_parameter_window.root.geometry("450x300")

        # Label for instruction
        instruction_label = ttk.Label(add_parameter_window.main_frame, text=_(_("Enter the parameter name to add:")))
        instruction_label.pack(pady=5)

        param_dict = self.local_filesystem.doc_dict or fc_parameters

        if not param_dict:
            messagebox.showerror(
                _("Operation not possible"),
                _("No apm.pdef.xml file and no FC connected. Not possible autocomplete parameter names."),
            )
            return

        # Remove the parameters that are already displayed in this configuration step
        possible_add_param_names = [
            param_name
            for param_name in param_dict
            if param_name not in self.local_filesystem.file_parameters[self.current_file]
        ]

        possible_add_param_names.sort()

        # Prompt the user for a parameter name
        parameter_name_combobox = EntryWithDynamicalyFilteredListbox(
            add_parameter_window.main_frame,
            possible_add_param_names,
            startswith_match=False,
            ignorecase_match=True,
            listbox_height=12,
            width=28,
        )
        parameter_name_combobox.pack(padx=5, pady=5)
        BaseWindow.center_window(add_parameter_window.root, self.root)
        parameter_name_combobox.focus()

        def custom_selection_handler(event):
            parameter_name_combobox.update_entry_from_listbox(event)
            if self.__confirm_parameter_addition(parameter_name_combobox.get().upper(), fc_parameters):
                add_parameter_window.root.destroy()
            else:
                add_parameter_window.root.focus()

        # Bindings to handle Enter press and selection while respecting original functionalities
        parameter_name_combobox.bind("<Return>", custom_selection_handler)
        parameter_name_combobox.bind("<<ComboboxSelected>>", custom_selection_handler)

    def __confirm_parameter_addition(self, param_name: str, fc_parameters: dict) -> bool:
        if not param_name:
            messagebox.showerror(_("Invalid parameter name."), _("Parameter name can not be empty."))
            return False
        if param_name in self.local_filesystem.file_parameters[self.current_file]:
            messagebox.showerror(_("Invalid parameter name."), _("Parameter already exists, edit it instead"))
            return False
        if fc_parameters:
            if param_name in fc_parameters:
                self.local_filesystem.file_parameters[self.current_file][param_name] = Par(fc_parameters[param_name], "")
                self.at_least_one_param_edited = True
                self.parameter_editor.repopulate_parameter_table(self.current_file)
                return True
            messagebox.showerror(_("Invalid parameter name."), _("Parameter name not found in the flight controller."))
        elif self.local_filesystem.doc_dict:
            if param_name in self.local_filesystem.doc_dict:
                self.local_filesystem.file_parameters[self.current_file][param_name] = Par(
                    self.local_filesystem.param_default_dict.get(param_name, Par(0, "")).value, ""
                )
                self.at_least_one_param_edited = True
                self.parameter_editor.repopulate_parameter_table(self.current_file)
                return True
            error_msg = _("'{param_name}' not found in the apm.pdef.xml file.")
            messagebox.showerror(_("Invalid parameter name."), error_msg.format(**locals()))
        else:
            messagebox.showerror(
                _("Operation not possible"),
                _("Can not add parameter when no FC is connected and no apm.pdef.xml file exists."),
            )
        return False

    def __on_parameter_value_change(self, event, current_file, param_name):
        # Get the new value from the Entry widget
        new_value = event.widget.get_selected_key() if isinstance(event.widget, PairTupleCombobox) else event.widget.get()
        try:
            old_value = self.local_filesystem.file_parameters[current_file][param_name].value
        except KeyError as e:
            logging_critical(_("Parameter %s not found in the %s file: %s"), param_name, current_file, e, exc_info=True)
            sys_exit(1)
        valid = True
        # Check if the input is a valid float
        try:
            p = float(new_value)
            changed = not is_within_tolerance(old_value, p)
            param_metadata = self.local_filesystem.doc_dict.get(param_name, None)
            p_min = param_metadata.get("min", None) if param_metadata else None
            p_max = param_metadata.get("max", None) if param_metadata else None
            if changed:
                if p_min and p < p_min:
                    msg = _("The value for {param_name} {p} should be greater than {p_min}\n")
                    if not messagebox.askyesno(
                        _("Out-of-bounds Value"), msg.format(**locals()) + _("Use out-of-bounds value?"), icon="warning"
                    ):
                        valid = False
                if p_max and p > p_max:
                    msg = _("The value for {param_name} {p} should be smaller than {p_max}\n")
                    if not messagebox.askyesno(
                        _("Out-of-bounds Value"), msg.format(**locals()) + _("Use out-of-bounds value?"), icon="warning"
                    ):
                        valid = False
        except ValueError:
            # Optionally, you can handle the invalid value here, for example, by showing an error message
            error_msg = _("The value for {param_name} must be a valid float.")
            messagebox.showerror(_("Invalid Value"), error_msg.format(**locals()))
            valid = False
        if valid:
            if changed and not self.at_least_one_param_edited:
                logging_debug(_("Parameter %s changed, will later ask if change(s) should be saved to file."), param_name)
            self.at_least_one_param_edited = changed or self.at_least_one_param_edited
            # Update the params dictionary with the new value
            self.local_filesystem.file_parameters[current_file][param_name].value = p
        else:
            # Revert to the previous (valid) value
            p = old_value
        self.__update_new_value_entry_text(event.widget, p, self.local_filesystem.param_default_dict.get(param_name, None))

    def __on_parameter_change_reason_change(self, event, current_file, param_name):
        # Get the new value from the Entry widget
        new_value = event.widget.get()
        try:
            changed = new_value != self.local_filesystem.file_parameters[current_file][param_name].comment and not (
                new_value == "" and self.local_filesystem.file_parameters[current_file][param_name].comment is None
            )
        except KeyError as e:
            logging_critical(
                _("Parameter %s not found in the %s file %s: %s"), param_name, current_file, new_value, e, exc_info=True
            )
            sys_exit(1)
        if changed and not self.at_least_one_param_edited:
            logging_debug(
                _("Parameter %s change reason changed from %s to %s, will later ask if change(s) should be saved to file."),
                param_name,
                self.local_filesystem.file_parameters[current_file][param_name].comment,
                new_value,
            )
        self.at_least_one_param_edited = changed or self.at_least_one_param_edited
        # Update the params dictionary with the new value
        self.local_filesystem.file_parameters[current_file][param_name].comment = new_value

    def get_upload_selected_params(self, current_file: str):
        selected_params = {}
        for param_name, checkbutton_state in self.upload_checkbutton_var.items():
            if checkbutton_state.get():
                selected_params[param_name] = self.local_filesystem.file_parameters[current_file][param_name]
        return selected_params

    def generate_edit_widgets_focus_out(self):
        # Trigger the <FocusOut> event for all entry widgets to ensure all changes are processed
        for widget in self.view_port.winfo_children():
            if isinstance(widget, ttk.Entry):
                widget.event_generate("<FocusOut>", when="now")

    def get_at_least_one_param_edited(self):
        return self.at_least_one_param_edited

    def set_at_least_one_param_edited(self, value):
        self.at_least_one_param_edited = value
