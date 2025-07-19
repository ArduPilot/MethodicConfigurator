"""
Parameter editor table GUI using the domain model.

This file is part of Ardupilot methodic configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2025 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import tkinter as tk
from logging import critical as logging_critical
from logging import debug as logging_debug
from logging import info as logging_info
from math import nan
from platform import system as platform_system
from sys import exit as sys_exit
from tkinter import messagebox, ttk
from typing import Union

from ardupilot_methodic_configurator import _
from ardupilot_methodic_configurator.annotate_params import Par
from ardupilot_methodic_configurator.ardupilot_parameter import ArduPilotParameter
from ardupilot_methodic_configurator.backend_filesystem import LocalFilesystem
from ardupilot_methodic_configurator.bitmask_helper import BitmaskHelper
from ardupilot_methodic_configurator.connection_renamer import ConnectionRenamer
from ardupilot_methodic_configurator.frontend_tkinter_base_window import BaseWindow
from ardupilot_methodic_configurator.frontend_tkinter_entry_dynamic import EntryWithDynamicalyFilteredListbox
from ardupilot_methodic_configurator.frontend_tkinter_pair_tuple_combobox import PairTupleCombobox
from ardupilot_methodic_configurator.frontend_tkinter_rich_text import get_widget_font_family_and_size
from ardupilot_methodic_configurator.frontend_tkinter_scroll_frame import ScrollFrame
from ardupilot_methodic_configurator.frontend_tkinter_show import show_tooltip

NEW_VALUE_WIDGET_WIDTH = 9


class ParameterEditorTable(ScrollFrame):  # pylint: disable=too-many-ancestors
    """
    A class to manage and display the parameter editor table within the GUI.

    This class inherits from ScrollFrame and is responsible for creating,
    managing, and updating the table that displays parameters for editing.
    It uses the ArduPilotParameter domain model to handle parameter operations.
    """

    def __init__(self, master, local_filesystem: LocalFilesystem, parameter_editor) -> None:  # noqa: ANN001
        super().__init__(master)
        self.root = master
        self.local_filesystem = local_filesystem
        self.parameter_editor = parameter_editor
        self.current_file = ""
        self.upload_checkbutton_var: dict[str, tk.BooleanVar] = {}
        self.at_least_one_param_edited = False
        self.parameters: dict[str, ArduPilotParameter] = {}

        style = ttk.Style()
        style.configure("narrow.TButton", padding=0, width=4, border=(0, 0, 0, 0))

        # Prepare a dictionary that maps variable names to their values
        # These variables are used by the forced_parameters and derived_parameters in configuration_steps_*.json files
        self.variables = local_filesystem.get_eval_variables()

    def repopulate(self, selected_file: str, fc_parameters: dict[str, float], show_only_differences: bool) -> None:
        for widget in self.view_port.winfo_children():
            widget.destroy()
        self.current_file = selected_file
        self.parameters = {}

        # Create labels for table headers
        headers = (_("-/+"), _("Parameter"), _("Current Value"), _("New Value"), _("Unit"), _("Upload"), _("Change Reason"))
        tooltips = (
            _("Delete or add a parameter"),
            _("Parameter name must be ^[A-Z][A-Z_0-9]* and most 16 characters long"),
            _("Current value on the flight controller "),
            _("New value from the above selected intermediate parameter file"),
            _("Parameter Unit"),
            _("When selected, upload the new value to the flight controller"),
            _("Reason why respective parameter changed.")
            + "\n\n"
            + _("Documenting change reasons is crucial because it:")
            + "\n"
            + _(" * Promotes thoughtful decisions over impulsive changes")
            + "\n"
            + _(" * Provides documentation for vehicle certification requirements")
            + "\n"
            + _(" * Enables validation or suggestions from team members or AI tools")
            + "\n"
            + _(" * Preserves your reasoning for future reference or troubleshooting"),
        )

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
            # merge derived parameter values
            elif self.local_filesystem.merge_forced_or_derived_parameters(
                selected_file, self.local_filesystem.derived_parameters, list(fc_parameters.keys())
            ):
                self.at_least_one_param_edited = True

            self.__rename_fc_connection(selected_file)

        # Convert file parameters to domain model parameters
        self.__create_domain_model_parameters(selected_file, fc_parameters)

        if show_only_differences:
            # recompute different_params because of renames and derived values changes
            different_params = {
                name: param for name, param in self.parameters.items() if param.is_different_from_fc or not param.has_fc_value
            }
            self.__update_table(different_params)
            if not different_params:
                info_msg = _("No different parameters found in {selected_file}. Skipping...").format(**locals())
                logging_info(info_msg)
                messagebox.showinfo(_("ArduPilot methodic configurator"), info_msg)
                self.parameter_editor.on_skip_click(force_focus_out_event=False)
                return
        else:
            self.__update_table(self.parameters)
        # Scroll to the top of the parameter table
        self.canvas.yview("moveto", 0)

    def __create_domain_model_parameters(self, selected_file: str, fc_parameters: dict[str, float]) -> None:
        """Create ArduPilotParameter objects for each parameter in the file."""
        self.parameters = {}

        for param_name, param in self.local_filesystem.file_parameters[selected_file].items():
            # Get parameter metadata and default values
            metadata = self.local_filesystem.doc_dict.get(param_name, {})
            default_par = self.local_filesystem.param_default_dict.get(param_name, None)

            # Check if parameter is forced or derived
            is_forced = (
                selected_file in self.local_filesystem.forced_parameters
                and param_name in self.local_filesystem.forced_parameters[selected_file]
            )
            is_derived = (
                selected_file in self.local_filesystem.derived_parameters
                and param_name in self.local_filesystem.derived_parameters[selected_file]
            )

            # Get FC value if available
            fc_value = fc_parameters.get(param_name)

            # Create domain model parameter
            self.parameters[param_name] = ArduPilotParameter(
                param_name, param, metadata, default_par, fc_value, is_forced, is_derived
            )

    def __rename_fc_connection(self, selected_file: str) -> None:
        """Rename parameters based on connection prefixes using the ConnectionRenamer."""
        if "rename_connection" in self.local_filesystem.configuration_steps[selected_file]:
            new_connection_prefix = self.local_filesystem.configuration_steps[selected_file]["rename_connection"]

            # Apply renames to the parameters dictionary
            updated_parameters, new_names, renamed_pairs = ConnectionRenamer.apply_renames(
                self.local_filesystem.file_parameters[selected_file], new_connection_prefix, self.variables
            )

            # Update the file parameters with the renamed ones
            self.local_filesystem.file_parameters[selected_file] = updated_parameters

            # Show info messages for renamed parameters
            for old_name, new_name in renamed_pairs:
                logging_info(_("Renaming parameter %s to %s"), old_name, new_name)
                info_msg = _(
                    "The parameter '{old_name}' was renamed to '{new_name}'.\n"
                    "to obey the flight controller connection defined in the component editor window."
                )
                messagebox.showinfo(_("Parameter Renamed"), info_msg.format(**locals()))
                # will ask the user to save changes before switching to another file
                self.at_least_one_param_edited = True

    def __update_table(self, params: dict[str, ArduPilotParameter]) -> None:
        """Update the parameter table with the given parameters."""
        current_param_name: str = ""
        try:
            for i, (param_name, param) in enumerate(params.items(), 1):
                current_param_name = param_name

                column: list[tk.Widget] = []
                column.append(self.__create_delete_button(param_name))
                column.append(self.__create_parameter_name(param))
                column.append(self.__create_flightcontroller_value(param))
                column.append(self.__create_new_value_entry(param))
                column.append(self.__create_unit_label(param))
                column.append(self.__create_upload_checkbutton(param_name, param.has_fc_value))
                # workaround a mypy issue
                column.append(self.__create_change_reason_entry(param, column[3]))  # type: ignore[arg-type]

                column[0].grid(row=i, column=0, sticky="w", padx=0)
                column[1].grid(row=i, column=1, sticky="w", padx=0)
                column[2].grid(row=i, column=2, sticky="e", padx=0)
                column[3].grid(row=i, column=3, sticky="e", padx=0)
                column[4].grid(row=i, column=4, sticky="e", padx=0)
                column[5].grid(row=i, column=5, sticky="e", padx=0)
                column[6].grid(row=i, column=6, sticky="ew", padx=(0, 5))

            # Add the "Add" button at the bottom of the table
            add_button = ttk.Button(
                self.view_port, text=_("Add"), style="narrow.TButton", command=lambda: self.__on_parameter_add()
            )
            tooltip_msg = _("Add a parameter to the {self.current_file} file")
            show_tooltip(add_button, tooltip_msg.format(**locals()))
            add_button.grid(row=len(params) + 2, column=0, sticky="w", padx=0)

        except KeyError as e:
            logging_critical(
                _("Parameter %s not found in the %s file: %s"), current_param_name, self.current_file, e, exc_info=True
            )
            sys_exit(1)

        # Configure the table_frame to stretch columns
        self.view_port.columnconfigure(0, weight=0)  # Delete and Add buttons
        self.view_port.columnconfigure(1, weight=0, minsize=120)  # Parameter name
        self.view_port.columnconfigure(2, weight=0)  # Current Value
        self.view_port.columnconfigure(3, weight=0)  # New Value
        self.view_port.columnconfigure(4, weight=0)  # Units
        self.view_port.columnconfigure(5, weight=0)  # Upload to FC
        self.view_port.columnconfigure(6, weight=1)  # Change Reason

    def __create_delete_button(self, param_name: str) -> ttk.Button:
        """Create a delete button for a parameter."""
        delete_button = ttk.Button(
            self.view_port, text=_("Del"), style="narrow.TButton", command=lambda: self.__on_parameter_delete(param_name)
        )
        tooltip_msg = _("Delete {param_name} from the {self.current_file} file")
        show_tooltip(delete_button, tooltip_msg.format(**locals()))
        return delete_button

    def __create_parameter_name(self, param: ArduPilotParameter) -> ttk.Label:
        """Create a label displaying the parameter name."""
        parameter_label = ttk.Label(
            self.view_port,
            text=param.name + (" " * (16 - len(param.name))),
            background="red"
            if param.is_readonly
            else "yellow"
            if param.is_calibration
            else ttk.Style(self.root).lookup("TFrame", "background"),
        )

        if param.doc_tooltip:
            show_tooltip(parameter_label, param.doc_tooltip)
        return parameter_label

    def __create_flightcontroller_value(self, param: ArduPilotParameter) -> ttk.Label:
        """Create a label displaying the flight controller value."""
        if param.has_fc_value:
            if param.has_default_value:
                # If it matches default, set the background color to light blue
                flightcontroller_value = ttk.Label(self.view_port, text=param.fc_value_as_string, background="light blue")
            else:
                # Otherwise, set the background color to the default color
                flightcontroller_value = ttk.Label(self.view_port, text=param.fc_value_as_string)
        else:
            flightcontroller_value = ttk.Label(self.view_port, text=_("N/A"), background="orange")

        if param.doc_tooltip:
            show_tooltip(flightcontroller_value, param.doc_tooltip)
        return flightcontroller_value

    def __update_combobox_style_on_selection(
        self, combobox_widget: PairTupleCombobox, param: ArduPilotParameter, event: tk.Event
    ) -> None:
        """Update the combobox style based on selection."""
        try:
            # we want None to raise an exception
            current_value = float(combobox_widget.get_selected_key())  # type: ignore[arg-type]
            combobox_widget.configure(style="default_v.TCombobox" if param.has_default_value else "readonly.TCombobox")
            event.width = NEW_VALUE_WIDGET_WIDTH
            combobox_widget.on_combo_configure(event)
        except ValueError:
            msg = _("Could not solve the selected {combobox_widget} key to a float value.")
            logging_info(msg.format(**locals()))

    @staticmethod
    def __update_new_value_entry_text(new_value_entry: ttk.Entry, param: ArduPilotParameter) -> None:
        """Update the new value entry text and style."""
        if isinstance(new_value_entry, PairTupleCombobox):
            return
        new_value_entry.delete(0, tk.END)
        new_value_entry.insert(0, param.value_as_string)
        if param.has_default_value:
            new_value_entry.configure(style="default_v.TEntry")
        else:
            new_value_entry.configure(style="TEntry")

    def __create_new_value_entry(self, param: ArduPilotParameter) -> Union[PairTupleCombobox, ttk.Entry]:
        """Create an entry widget for editing the parameter value."""
        # Check if parameter has values dictionary
        value_str = param.value_as_string
        new_value_entry: Union[PairTupleCombobox, ttk.Entry]

        if param.values_dict and param.is_in_values_dict():
            selected_value = param.get_selected_value_from_dict()
            new_value_entry = PairTupleCombobox(
                self.view_port,
                param.values_dict,
                value_str,
                param.name,
                style="TCombobox"
                if not param.is_editable()
                else "default_v.TCombobox"
                if param.has_default_value
                else "readonly.TCombobox",
            )
            new_value_entry.set(selected_value)
            font_family, font_size = get_widget_font_family_and_size(new_value_entry)
            font_size -= 2 if platform_system() == "Windows" else 1
            new_value_entry.config(state="readonly", width=NEW_VALUE_WIDGET_WIDTH, font=(font_family, font_size))
            new_value_entry.bind(  # type: ignore[call-overload] # workaround a mypy issue
                "<<ComboboxSelected>>",
                lambda event: self.__update_combobox_style_on_selection(new_value_entry, param, event),
                "+",
            )
        else:
            new_value_entry = ttk.Entry(self.view_port, width=NEW_VALUE_WIDGET_WIDTH + 1, justify=tk.RIGHT)
            self.__update_new_value_entry_text(new_value_entry, param)

        # Store error messages for forced and derived parameters
        forced_error_msg = _(
            "This parameter already has the correct value for this configuration step.\n"
            "You must not change it, as this would defeat the purpose of this configuration step.\n\n"
            "Add it to other configuration step and change it there if you have a good reason to."
        )
        derived_error_msg = _(
            "This parameter value has been derived from information you entered in the component editor window.\n"
            "You need to change the information on that window to update the value here.\n"
        )

        # Function to show the appropriate error message
        def show_parameter_error(_event: tk.Event) -> None:  # pylint: disable=unused-argument
            if param.is_forced:
                messagebox.showerror(_("Forced Parameter"), forced_error_msg)
            elif param.is_derived:
                messagebox.showerror(_("Derived Parameter"), derived_error_msg)

        if not param.is_editable():
            new_value_entry.config(state="disabled", background="light grey")
            new_value_entry.bind("<Button-1>", show_parameter_error)
            # Also bind to right-click for completeness
            new_value_entry.bind("<Button-3>", show_parameter_error)
        elif param.is_bitmask:
            new_value_entry.bind(
                "<Double-Button>",
                lambda event: self.__open_bitmask_selection_window(event, param),
            )
            # pylint: disable=line-too-long
            new_value_entry.bind(
                "<FocusOut>",
                lambda event: self.__on_parameter_value_change(  # type: ignore[misc]
                    event, param
                ),
            )
            # pylint: enable=line-too-long
        else:
            # pylint: disable=line-too-long
            new_value_entry.bind(
                "<FocusOut>",
                lambda event: self.__on_parameter_value_change(  # type: ignore[misc]
                    event, param
                ),
            )
            # pylint: enable=line-too-long

        if param.doc_tooltip:
            show_tooltip(new_value_entry, param.doc_tooltip)
        return new_value_entry

    def __open_bitmask_selection_window(self, event: tk.Event, param: ArduPilotParameter) -> None:  # pylint: disable=too-many-locals
        """Open a window to select bitmask options."""

        def on_close() -> None:
            checked_keys = [key for key, var in checkbox_vars.items() if var.get()]
            # Convert checked keys back to a decimal value using our helper
            new_decimal_value = BitmaskHelper.get_value_from_keys(checked_keys)

            # Update the parameter value and entry text
            if param.set_value(new_decimal_value):
                self.at_least_one_param_edited = True
                # Update the corresponding file parameter
                self.local_filesystem.file_parameters[self.current_file][param.name].value = new_decimal_value

            # Update the entry widget
            self.__update_new_value_entry_text(event.widget, param)

            # Destroy the window
            window.destroy()
            # Issue a FocusIn event on something else than new_value_entry to prevent endless looping
            self.root.focus_set()
            # Run the Tk event loop once to process the event
            self.root.update_idletasks()
            # Re-bind the FocusIn event to new_value_entry
            event.widget.bind(
                "<Double-Button>",
                lambda event: self.__open_bitmask_selection_window(event, param),
            )

        def is_widget_visible(widget: Union[tk.Misc, None]) -> bool:
            return bool(widget and widget.winfo_ismapped())

        def focus_out_handler(_event: tk.Event) -> None:
            if not is_widget_visible(window.focus_get()):
                on_close()

        def update_label() -> None:
            checked_keys = {key for key, var in checkbox_vars.items() if var.get()}
            close_label.config(text=get_param_value_msg(param.name, checked_keys))

        def get_param_value_msg(_param_name: str, checked_keys: set) -> str:
            _new_decimal_value = BitmaskHelper.get_value_from_keys(list(checked_keys))
            text = _("{_param_name} Value: {_new_decimal_value}")
            return text.format(**locals())

        # Temporarily unbind the FocusIn event to prevent triggering the window again
        event.widget.unbind("<Double-Button>")
        window = tk.Toplevel(self.root)
        title = _("Select {param.name} Bitmask Options")
        window.title(title.format(**locals()))
        checkbox_vars = {}

        main_frame = ttk.Frame(window)
        main_frame.pack(expand=True, fill=tk.BOTH)

        # Convert current_value to a set of checked keys using our helper
        current_value = int(float(event.widget.get()))
        checked_keys = BitmaskHelper.get_checked_keys(current_value, param.bitmask_dict)

        for i, (key, value) in enumerate(param.bitmask_dict.items()):
            var = tk.BooleanVar(value=key in checked_keys)
            checkbox_vars[key] = var
            checkbox = ttk.Checkbutton(main_frame, text=value, variable=var, command=update_label)
            checkbox.grid(row=i, column=0, sticky="w")

        # Add a read-only label displaying the current new_decimal_value
        close_label = ttk.Label(main_frame, text=get_param_value_msg(param.name, checked_keys))
        close_label.grid(row=len(param.bitmask_dict), column=0, pady=10)

        # Bind the on_close function to the window's WM_DELETE_WINDOW protocol
        window.protocol("WM_DELETE_WINDOW", on_close)
        window.bind("<FocusOut>", focus_out_handler)
        for child in window.winfo_children():
            child.bind("<FocusOut>", focus_out_handler)

        # Make sure the window is visible before disabling the parent window
        window.deiconify()
        self.root.update_idletasks()
        window.grab_set()

        window.wait_window()  # Wait for the window to be closed

    def __create_unit_label(self, param: ArduPilotParameter) -> ttk.Label:
        """Create a label displaying the parameter unit."""
        unit_label = ttk.Label(self.view_port, text=param.unit)
        if param.unit_tooltip:
            show_tooltip(unit_label, param.unit_tooltip)
        return unit_label

    def __create_upload_checkbutton(self, param_name: str, fc_connected: bool) -> ttk.Checkbutton:
        """Create a checkbutton for upload selection."""
        self.upload_checkbutton_var[param_name] = tk.BooleanVar(value=fc_connected)
        upload_checkbutton = ttk.Checkbutton(self.view_port, variable=self.upload_checkbutton_var[param_name])
        upload_checkbutton.configure(state="normal" if fc_connected else "disabled")
        msg = _("When selected upload {param_name} new value to the flight controller")
        show_tooltip(upload_checkbutton, msg.format(**locals()))
        return upload_checkbutton

    def __create_change_reason_entry(
        self, param: ArduPilotParameter, new_value_entry: Union[ttk.Entry, PairTupleCombobox]
    ) -> ttk.Entry:
        """Create an entry for the parameter change reason."""
        change_reason_entry = ttk.Entry(self.view_port, background="white")
        change_reason_entry.insert(0, "" if param.comment is None else param.comment)

        if not param.is_editable():
            change_reason_entry.config(state="disabled", background="light grey")
        else:
            # pylint: disable=line-too-long
            change_reason_entry.bind(
                "<FocusOut>",
                lambda event: self.__on_parameter_change_reason_change(  # type: ignore[misc]
                    event, param
                ),
            )
            # pylint: enable=line-too-long

        _value = new_value_entry.get()
        msg = _("Reason why {param.name} should change to {_value}")
        show_tooltip(change_reason_entry, msg.format(**locals()))
        return change_reason_entry

    def __on_parameter_delete(self, param_name: str) -> None:
        """Handle parameter deletion."""
        msg = _("Are you sure you want to delete the {param_name} parameter?")
        if messagebox.askyesno(f"{self.current_file}", msg.format(**locals())):
            # Capture current vertical scroll position
            current_scroll_position = self.canvas.yview()[0]

            # Delete the parameter
            del self.local_filesystem.file_parameters[self.current_file][param_name]
            if param_name in self.parameters:
                del self.parameters[param_name]
            self.at_least_one_param_edited = True
            self.parameter_editor.repopulate_parameter_table(self.current_file)

            # Restore the scroll position
            self.canvas.yview_moveto(current_scroll_position)

    def __on_parameter_add(self) -> None:
        """Handle parameter addition."""
        add_parameter_window = BaseWindow(self.root)
        add_parameter_window.root.title(_("Add Parameter to ") + self.current_file)
        add_parameter_window.root.geometry("450x300")

        # Label for instruction
        instruction_label = ttk.Label(add_parameter_window.main_frame, text=_("Enter the parameter name to add:"))
        instruction_label.pack(pady=5)

        fc_parameters = {name: param.fc_value for name, param in self.parameters.items() if param.has_fc_value}
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

        def custom_selection_handler(event: tk.Event) -> None:
            parameter_name_combobox.update_entry_from_listbox(event)
            param_name = parameter_name_combobox.get().upper()
            if self.__confirm_parameter_addition(param_name):
                add_parameter_window.root.destroy()
            else:
                add_parameter_window.root.focus()

        # Bindings to handle Enter press and selection while respecting original functionalities
        parameter_name_combobox.bind("<Return>", custom_selection_handler)
        parameter_name_combobox.bind("<<ComboboxSelected>>", custom_selection_handler)

    def __confirm_parameter_addition(self, param_name: str) -> bool:
        """Confirm and process parameter addition."""
        if not param_name:
            messagebox.showerror(_("Invalid parameter name."), _("Parameter name can not be empty."))
            return False

        if param_name in self.local_filesystem.file_parameters[self.current_file]:
            messagebox.showerror(_("Invalid parameter name."), _("Parameter already exists, edit it instead"))
            return False

        fc_parameters = {name: param.fc_value for name, param in self.parameters.items() if param.has_fc_value}

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

    def __on_parameter_value_change(self, event: tk.Event, param: ArduPilotParameter) -> None:
        """Handle changes to parameter values."""
        # Get the new value from the Entry widget
        new_value = event.widget.get_selected_key() if isinstance(event.widget, PairTupleCombobox) else event.widget.get()
        valid: bool = True
        value: float = nan

        # Check if the input is a valid float
        try:
            value = float(new_value)  # type: ignore[arg-type] # workaround a mypy bug

            # Check if value is valid with domain model
            if not param.is_valid_value(value):
                min_val = param.min_value
                max_val = param.max_value

                if min_val is not None and value < min_val:
                    msg = _("The value for {param.name} {value} should be greater than {min_val}\n")
                    if not messagebox.askyesno(
                        _("Out-of-bounds Value"), msg.format(**locals()) + _("Use out-of-bounds value?"), icon="warning"
                    ):
                        valid = False

                if max_val is not None and value > max_val:
                    msg = _("The value for {param.name} {value} should be smaller than {max_val}\n")
                    if not messagebox.askyesno(
                        _("Out-of-bounds Value"), msg.format(**locals()) + _("Use out-of-bounds value?"), icon="warning"
                    ):
                        valid = False
        except ValueError:
            # Handle invalid value
            error_msg = _("The value for {param.name} must be a valid float.")
            messagebox.showerror(_("Invalid Value"), error_msg.format(**locals()))
            valid = False

        if valid and param.set_value(value):
            logging_debug(_("Parameter %s changed, will later ask if change(s) should be saved to file."), param.name)
            self.at_least_one_param_edited = True
            # Update the corresponding file parameter
            self.local_filesystem.file_parameters[self.current_file][param.name].value = value

        # Update the entry widget
        self.__update_new_value_entry_text(event.widget, param)

    def __on_parameter_change_reason_change(self, event: tk.Event, param: ArduPilotParameter) -> None:
        """Handle changes to parameter change reasons."""
        # Get the new value from the Entry widget
        new_comment = event.widget.get()

        # Use domain model's set_comment method
        if param.set_comment(new_comment):
            logging_debug(
                _("Parameter %s change reason changed from %s to %s, will later ask if change(s) should be saved to file."),
                param.name,
                param.comment,
                new_comment,
            )
            self.at_least_one_param_edited = True
            # Update the corresponding file parameter comment
            self.local_filesystem.file_parameters[self.current_file][param.name].comment = new_comment

    def get_upload_selected_params(self, current_file: str) -> dict[str, Par]:
        """Get the parameters selected for upload."""
        selected_params = {}
        for param_name, checkbutton_state in self.upload_checkbutton_var.items():
            if checkbutton_state.get():
                selected_params[param_name] = self.local_filesystem.file_parameters[current_file][param_name]
        return selected_params

    def generate_edit_widgets_focus_out(self) -> None:
        """Generate focus out events for all entry widgets."""
        # Trigger the <FocusOut> event for all entry widgets to ensure all changes are processed
        for widget in self.view_port.winfo_children():
            if isinstance(widget, ttk.Entry):
                widget.event_generate("<FocusOut>", when="now")

    def get_at_least_one_param_edited(self) -> bool:
        """Get whether at least one parameter has been edited."""
        return self.at_least_one_param_edited

    def set_at_least_one_param_edited(self, value: bool) -> None:
        """Set whether at least one parameter has been edited."""
        self.at_least_one_param_edited = value
