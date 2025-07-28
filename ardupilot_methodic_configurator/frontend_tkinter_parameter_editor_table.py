"""
Parameter editor table GUI using the "Ardupilot Parameter data model".

This file is part of Ardupilot methodic configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2025 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import tkinter as tk
from logging import critical as logging_critical
from logging import debug as logging_debug
from logging import exception as logging_exception
from logging import info as logging_info
from platform import system as platform_system
from sys import exit as sys_exit
from tkinter import messagebox, ttk
from typing import Union

from ardupilot_methodic_configurator import _
from ardupilot_methodic_configurator.annotate_params import Par
from ardupilot_methodic_configurator.ardupilot_parameter import ArduPilotParameter, BitmaskHelper, ConnectionRenamer
from ardupilot_methodic_configurator.backend_filesystem import LocalFilesystem
from ardupilot_methodic_configurator.frontend_tkinter_base_window import BaseWindow
from ardupilot_methodic_configurator.frontend_tkinter_entry_dynamic import EntryWithDynamicalyFilteredListbox
from ardupilot_methodic_configurator.frontend_tkinter_pair_tuple_combobox import PairTupleCombobox
from ardupilot_methodic_configurator.frontend_tkinter_rich_text import get_widget_font_family_and_size
from ardupilot_methodic_configurator.frontend_tkinter_scroll_frame import ScrollFrame
from ardupilot_methodic_configurator.frontend_tkinter_show import show_tooltip

NEW_VALUE_WIDGET_WIDTH = 9


class ParameterEditorTable(ScrollFrame):  # pylint: disable=too-many-ancestors, too-many-instance-attributes
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
        self.parameter_editor = parameter_editor  # the parent window that contains this table
        self.current_file = ""
        self.upload_checkbutton_var: dict[str, tk.BooleanVar] = {}
        self.at_least_one_param_edited = False
        self.parameters: dict[str, ArduPilotParameter] = {}

        style = ttk.Style()
        style.configure("narrow.TButton", padding=0, width=4, border=(0, 0, 0, 0))  # type: ignore[no-untyped-call]

        # Prepare a dictionary that maps variable names to their values
        # These variables are used by the forced_parameters and derived_parameters in configuration_steps_*.json files
        self.variables = local_filesystem.get_eval_variables()

    def _should_show_upload_column(self, gui_complexity: Union[str, None] = None) -> bool:
        """
        Determine if the upload column should be shown based on UI complexity.

        Args:
            gui_complexity: UI complexity level. If None, uses self.parameter_editor.gui_complexity

        Returns:
            True if upload column should be shown, False otherwise

        """
        if gui_complexity is None:
            gui_complexity = self.parameter_editor.gui_complexity
        return gui_complexity != "simple"

    def _create_headers_and_tooltips(self, show_upload_column: bool) -> tuple[tuple[str, ...], tuple[str, ...]]:
        """Create table headers and tooltips dynamically based on UI complexity."""
        base_headers = [
            _("-/+"),
            _("Parameter"),
            _("Current Value"),
            _("New Value"),
            _("Unit"),
        ]

        base_tooltips = [
            _("Delete or add a parameter"),
            _("Parameter name must be ^[A-Z][A-Z_0-9]* and most 16 characters long"),
            _("Current value on the flight controller "),
            _("New value from the above selected intermediate parameter file"),
            _("Parameter Unit"),
        ]

        change_reason_tooltip = (
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
            + _(" * Preserves your reasoning for future reference or troubleshooting")
        )

        if show_upload_column:
            base_headers.append(_("Upload"))
            base_tooltips.append(_("When selected, upload the new value to the flight controller"))

        base_headers.append(_("Change Reason"))
        base_tooltips.append(change_reason_tooltip)

        return tuple(base_headers), tuple(base_tooltips)

    def repopulate(
        self, selected_file: str, fc_parameters: dict[str, float], show_only_differences: bool, gui_complexity: str
    ) -> None:
        for widget in self.view_port.winfo_children():
            widget.destroy()
        self.current_file = selected_file
        self.parameters = {}

        # Check if upload column should be shown based on UI complexity
        show_upload_column = self._should_show_upload_column(gui_complexity)

        # Create labels for table headers
        headers, tooltips = self._create_headers_and_tooltips(show_upload_column)

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

            self._rename_fc_connection(selected_file)

        # Convert file parameters to domain model parameters
        self._create_domain_model_parameters(selected_file, fc_parameters)

        if show_only_differences:
            # recompute different_params because of renames and derived values changes
            different_params = {
                name: param for name, param in self.parameters.items() if param.is_different_from_fc or not param.has_fc_value
            }
            self._update_table(different_params, fc_parameters, self.parameter_editor.gui_complexity)
            if not different_params:
                info_msg = _("No different parameters found in {selected_file}. Skipping...").format(**locals())
                logging_info(info_msg)
                messagebox.showinfo(_("ArduPilot methodic configurator"), info_msg)
                self.parameter_editor.on_skip_click(force_focus_out_event=False)
                return
        else:
            self._update_table(self.parameters, fc_parameters, self.parameter_editor.gui_complexity)
        # Scroll to the top of the parameter table
        self.canvas.yview("moveto", 0)

    def _create_domain_model_parameters(self, selected_file: str, fc_parameters: dict[str, float]) -> None:
        """Create ArduPilotParameter objects for each parameter in the file."""
        self.parameters = {}

        for param_name, param in self.local_filesystem.file_parameters[selected_file].items():
            # Get parameter metadata and default values
            metadata = self.local_filesystem.doc_dict.get(param_name, {})
            default_par = self.local_filesystem.param_default_dict.get(param_name, None)

            # Check if parameter is forced or derived
            forced_par = self.local_filesystem.forced_parameters.get(selected_file, {}).get(param_name, None)
            derived_par = self.local_filesystem.derived_parameters.get(selected_file, {}).get(param_name, None)

            # Get FC value if available
            fc_value = fc_parameters.get(param_name)

            # Create domain model parameter
            self.parameters[param_name] = ArduPilotParameter(
                param_name, param, metadata, default_par, fc_value, forced_par, derived_par
            )

    def _rename_fc_connection(self, selected_file: str) -> None:
        """Rename parameters based on connection prefixes using the ConnectionRenamer."""
        if "rename_connection" in self.local_filesystem.configuration_steps[selected_file]:
            new_connection_prefix = self.local_filesystem.configuration_steps[selected_file]["rename_connection"]

            # Apply renames to the parameters dictionary
            duplicated_parameters, renamed_pairs = ConnectionRenamer.apply_renames(
                self.local_filesystem.file_parameters[selected_file], new_connection_prefix, self.variables
            )

            for old_name in duplicated_parameters:
                logging_info(_("Removing duplicate parameter %s"), old_name)
                info_msg = _("The parameter '{old_name}' was removed due to duplication.")
                messagebox.showinfo(_("Parameter Removed"), info_msg.format(**locals()))
                # will ask the user to save changes before switching to another file
                self.at_least_one_param_edited = True

            for old_name, new_name in renamed_pairs:
                logging_info(_("Renaming parameter %s to %s"), old_name, new_name)
                info_msg = _(
                    "The parameter '{old_name}' was renamed to '{new_name}'.\n"
                    "to obey the flight controller connection defined in the component editor window."
                )
                messagebox.showinfo(_("Parameter Renamed"), info_msg.format(**locals()))
                # will ask the user to save changes before switching to another file
                self.at_least_one_param_edited = True

    def _update_table(
        self, params: dict[str, ArduPilotParameter], fc_parameters: dict[str, float], gui_complexity: str
    ) -> None:
        """Update the parameter table with the given parameters."""
        current_param_name: str = ""
        show_upload_column = self._should_show_upload_column(gui_complexity)

        try:
            for i, (param_name, param) in enumerate(params.items(), 1):
                current_param_name = param_name

                column: list[tk.Widget] = self._create_column_widgets(param_name, param, show_upload_column)
                self._grid_column_widgets(column, i, show_upload_column)

            # Add the "Add" button at the bottom of the table
            add_button = ttk.Button(
                self.view_port, text=_("Add"), style="narrow.TButton", command=lambda: self._on_parameter_add(fc_parameters)
            )
            tooltip_msg = _("Add a parameter to the {self.current_file} file")
            show_tooltip(add_button, tooltip_msg.format(**locals()))
            add_button.grid(row=len(params) + 2, column=0, sticky="w", padx=0)

        except KeyError as e:
            logging_critical(
                _("Parameter %s not found in the %s file: %s"), current_param_name, self.current_file, e, exc_info=True
            )
            sys_exit(1)

        self._configure_table_columns(show_upload_column)

    def _create_column_widgets(self, param_name: str, param: ArduPilotParameter, show_upload_column: bool) -> list[tk.Widget]:
        """Create all column widgets for a parameter row."""
        column: list[tk.Widget] = []
        change_reason_widget = self._create_change_reason_entry(param)
        column.append(self._create_delete_button(param_name))
        column.append(self._create_parameter_name(param))
        column.append(self._create_flightcontroller_value(param))
        # update the change reason tooltip when the new value changes
        column.append(self._create_new_value_entry(param, change_reason_widget))
        column.append(self._create_unit_label(param))

        if show_upload_column:
            column.append(self._create_upload_checkbutton(param_name, param.has_fc_value))

        column.append(change_reason_widget)

        return column

    def _grid_column_widgets(self, column: list[tk.Widget], row: int, show_upload_column: bool) -> None:
        """Grid all column widgets for a parameter row."""
        column[0].grid(row=row, column=0, sticky="w", padx=0)
        column[1].grid(row=row, column=1, sticky="w", padx=0)
        column[2].grid(row=row, column=2, sticky="e", padx=0)
        column[3].grid(row=row, column=3, sticky="e", padx=0)
        column[4].grid(row=row, column=4, sticky="e", padx=0)

        if show_upload_column:
            column[5].grid(row=row, column=5, sticky="e", padx=0)

        change_reason_column = self._get_change_reason_column_index(show_upload_column)
        column[change_reason_column].grid(row=row, column=change_reason_column, sticky="ew", padx=(0, 5))

    def _get_change_reason_column_index(self, show_upload_column: bool) -> int:
        """
        Get the column index for the change reason entry.

        Args:
            show_upload_column: Whether the upload column is shown

        Returns:
            Column index for change reason entry

        """
        # Base columns: Delete, Parameter, Current Value, New Value, Unit
        base_column_count = 5
        if show_upload_column:
            return base_column_count + 1  # Upload column + Change Reason
        return base_column_count  # Change Reason directly after Unit

    def _configure_table_columns(self, show_upload_column: bool) -> None:
        """Configure table column weights and sizes."""
        self.view_port.columnconfigure(0, weight=0)  # Delete and Add buttons
        self.view_port.columnconfigure(1, weight=0, minsize=120)  # Parameter name
        self.view_port.columnconfigure(2, weight=0)  # Current Value
        self.view_port.columnconfigure(3, weight=0)  # New Value
        self.view_port.columnconfigure(4, weight=0)  # Units

        if show_upload_column:
            self.view_port.columnconfigure(5, weight=0)  # Upload to FC

        self.view_port.columnconfigure(self._get_change_reason_column_index(show_upload_column), weight=1)  # Change Reason

    def _create_delete_button(self, param_name: str) -> ttk.Button:
        """Create a delete button for a parameter."""
        delete_button = ttk.Button(
            self.view_port, text=_("Del"), style="narrow.TButton", command=lambda: self._on_parameter_delete(param_name)
        )
        tooltip_msg = _("Delete {param_name} from the {self.current_file} file")
        show_tooltip(delete_button, tooltip_msg.format(**locals()))
        return delete_button

    def _create_parameter_name(self, param: ArduPilotParameter) -> ttk.Label:
        """Create a label displaying the parameter name."""
        parameter_label = ttk.Label(
            self.view_port,
            text=param.name + (" " * (16 - len(param.name))),
            background="purpule1"
            if param.is_readonly
            else "yellow"
            if param.is_calibration
            else ttk.Style(self.root).lookup("TFrame", "background"),  # type: ignore[no-untyped-call]
        )

        tooltip_parameter_name = param.tooltip_new_value
        if tooltip_parameter_name:
            show_tooltip(parameter_label, tooltip_parameter_name)
        return parameter_label

    def _create_flightcontroller_value(self, param: ArduPilotParameter) -> ttk.Label:
        """Create a label displaying the flight controller value."""
        if param.has_fc_value:
            if param.fc_value_equals_default_value:
                # If it matches default, set the background color to light blue
                flightcontroller_value = ttk.Label(self.view_port, text=param.fc_value_as_string, background="light blue")
            elif param.fc_value_is_below_limit():
                flightcontroller_value = ttk.Label(self.view_port, text=param.fc_value_as_string, background="orangered")
            elif param.fc_value_is_above_limit():
                flightcontroller_value = ttk.Label(self.view_port, text=param.fc_value_as_string, background="red3")
            else:
                # Otherwise, set the background color to the default color
                flightcontroller_value = ttk.Label(self.view_port, text=param.fc_value_as_string)
        else:
            flightcontroller_value = ttk.Label(self.view_port, text=_("N/A"), background="orange")

        tooltip_fc_value = param.tooltip_fc_value
        if tooltip_fc_value:
            show_tooltip(flightcontroller_value, tooltip_fc_value)
        return flightcontroller_value

    def _update_combobox_style_on_selection(
        self, combobox_widget: PairTupleCombobox, param: ArduPilotParameter, event: tk.Event, change_reason_widget: ttk.Entry
    ) -> None:
        """Update the combobox style based on selection."""
        new_value_str = combobox_widget.get_selected_key()
        try:
            # we want None to raise an exception
            new_value = float(new_value_str)  # type: ignore[arg-type]
            if param.set_new_value(new_value):
                show_tooltip(change_reason_widget, param.tooltip_change_reason)
                self.at_least_one_param_edited = True
                # Update the corresponding file parameter
                self.local_filesystem.file_parameters[self.current_file][param.name].value = new_value
            combobox_widget.configure(
                style="default_v.TCombobox" if param.new_value_equals_default_value else "readonly.TCombobox"
            )
            event.width = NEW_VALUE_WIDGET_WIDTH
            combobox_widget.on_combo_configure(event)
        except ValueError as e:
            msg = _("Could not solve the selected {new_value_str} key to a float value.").format(new_value_str=new_value_str)
            logging_exception(msg, e)
            messagebox.showerror(_("Error"), msg)

    @staticmethod
    def _update_new_value_entry_text(new_value_entry: ttk.Entry, param: ArduPilotParameter) -> None:
        """Update the new value entry text and style."""
        if isinstance(new_value_entry, PairTupleCombobox):
            # Only ttk.Entry widgets support style configuration
            return
        new_value_entry.delete(0, tk.END)
        new_value_entry.insert(0, param.value_as_string)
        if param.new_value_equals_default_value:
            new_value_entry.configure(style="default_v.TEntry")
        elif param.is_below_limit():
            new_value_entry.configure(style="below_limit.TEntry")
        elif param.is_above_limit():
            new_value_entry.configure(style="above_limit.TEntry")
        else:
            new_value_entry.configure(style="TEntry")

    def _create_new_value_entry(  # pylint: disable=too-many-statements # noqa: PLR0915
        self, param: ArduPilotParameter, change_reason_widget: ttk.Entry
    ) -> Union[PairTupleCombobox, ttk.Entry]:
        """Create an entry widget for editing the parameter value."""
        # if param.is_dirty:
        #    self.at_least_one_param_edited = True
        new_value_entry: Union[PairTupleCombobox, ttk.Entry]

        # Check if parameter has values dictionary
        if param.is_multiple_choice:
            selected_value = param.get_selected_value_from_dict()
            new_value_entry = PairTupleCombobox(
                self.view_port,
                list(param.choices_dict.items()),
                param.value_as_string,
                param.name,
                style="TCombobox"
                if not param.is_editable
                else "default_v.TCombobox"
                if param.new_value_equals_default_value
                else "readonly.TCombobox",
            )
            new_value_entry.set(selected_value)
            font_family, font_size = get_widget_font_family_and_size(new_value_entry)
            font_size -= 2 if platform_system() == "Windows" else 1
            new_value_entry.config(state="readonly", width=NEW_VALUE_WIDGET_WIDTH, font=(font_family, font_size))
            new_value_entry.bind(  # type: ignore[call-overload] # workaround a mypy issue
                "<<ComboboxSelected>>",
                lambda event: self._update_combobox_style_on_selection(new_value_entry, param, event, change_reason_widget),
                "+",
            )
        else:
            new_value_entry = ttk.Entry(self.view_port, width=NEW_VALUE_WIDGET_WIDTH + 1, justify=tk.RIGHT)
            self._update_new_value_entry_text(new_value_entry, param)

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
        def show_parameter_error(event: tk.Event) -> None:  # pylint: disable=unused-argument # noqa: ARG001
            if param.is_forced:
                messagebox.showerror(_("Forced Parameter"), forced_error_msg)
            elif param.is_derived:
                messagebox.showerror(_("Derived Parameter"), derived_error_msg)

        def _on_parameter_value_change(event: tk.Event) -> None:
            """Handle changes to parameter values."""
            # Get the new value from the Entry widget
            new_value = (
                event.widget.get_selected_key()
                if isinstance(event.widget, PairTupleCombobox)
                else event.widget.get()
                if isinstance(event.widget, (ttk.Entry, tk.Entry))
                else None
            )
            valid: bool = True
            value: float = param._new_value

            # Check if the input is a valid float
            try:
                value = float(new_value)  # type: ignore[arg-type] # workaround a mypy bug

                err_msg = param.is_invalid_number(value)
                if err_msg:
                    messagebox.showerror(_("Invalid Value"), err_msg)
                    valid = False

                # Check if value is valid according to domain model
                err_msg = param.is_below_limit(value)
                if err_msg and not messagebox.askyesno(
                    _("Out-of-bounds Value"), err_msg + _("Use out-of-bounds value?"), icon="warning"
                ):
                    valid = False

                err_msg = param.is_above_limit(value)
                if err_msg and not messagebox.askyesno(
                    _("Out-of-bounds Value"), err_msg + _("Use out-of-bounds value?"), icon="warning"
                ):
                    valid = False

            except ValueError:
                # Handle invalid value
                error_msg = _("The value for {param.name} must be a valid float.")
                messagebox.showerror(_("Invalid Value"), error_msg.format(**locals()))
                valid = False

            if valid and param.set_new_value(value):
                logging_debug(_("Parameter %s changed, will later ask if change(s) should be saved to file."), param.name)
                show_tooltip(change_reason_widget, param.tooltip_change_reason)
                self.at_least_one_param_edited = True
                # Update the corresponding file parameter
                self.local_filesystem.file_parameters[self.current_file][param.name].value = value

            # Update the displayed value in the Entry or Combobox
            if isinstance(
                event.widget, (ttk.Entry, tk.Entry)
            ):  # it is a ttk.Entry. The tk.Entry check is just defensive programming
                self._update_new_value_entry_text(event.widget, param)  # type: ignore[arg-type] # workaround a mypy bug
            elif isinstance(event.widget, PairTupleCombobox):
                # For PairTupleCombobox, update the style based on whether it matches default value
                self._update_combobox_style_on_selection(event.widget, param, event, change_reason_widget)

        if not param.is_editable:
            new_value_entry.config(state="disabled", background="light grey")
            new_value_entry.bind("<Button-1>", show_parameter_error)
            # Also bind to right-click for completeness
            new_value_entry.bind("<Button-3>", show_parameter_error)
        elif param.is_bitmask:
            new_value_entry.bind(
                "<Double-Button>",
                lambda event: self._open_bitmask_selection_window(event, param, change_reason_widget),
            )
            new_value_entry.bind("<FocusOut>", _on_parameter_value_change)
        else:
            new_value_entry.bind("<FocusOut>", _on_parameter_value_change)

        tooltip_new_value = param.tooltip_new_value
        if tooltip_new_value:
            show_tooltip(new_value_entry, tooltip_new_value)
        return new_value_entry

    def _open_bitmask_selection_window(  # pylint: disable=too-many-locals, too-many-statements # noqa: PLR0915
        self, event: tk.Event, param: ArduPilotParameter, change_reason_widget: ttk.Entry
    ) -> None:
        """Open a window to select bitmask options."""

        def on_close() -> None:
            try:
                checked_keys = [int(key) for key, var in checkbox_vars.items() if var.get()]
            except (ValueError, TypeError) as e:
                logging_exception(_("Error getting {param_name} checked keys: %s").format(param_name=param.name), e)
                messagebox.showerror(
                    _("Error"), _("Could not get {param_name} checked keys. Please try again.").format(param_name=param.name)
                )
                return
            # Convert checked keys back to a decimal value using our helper
            new_decimal_value = BitmaskHelper.get_value_from_keys(set(checked_keys))

            # Update the parameter value and entry text
            if param.set_new_value(new_decimal_value):
                show_tooltip(change_reason_widget, param.tooltip_change_reason)
                self.at_least_one_param_edited = True
                # Update the corresponding file parameter
                self.local_filesystem.file_parameters[self.current_file][param.name].value = new_decimal_value

            # Update new_value_entry with the new decimal value
            # For bitmask windows, event.widget should always be ttk.Entry (not PairTupleCombobox)
            # since bitmasks are only created for Entry widgets, not Comboboxes
            if isinstance(event.widget, ttk.Entry):
                self._update_new_value_entry_text(event.widget, param)

            # Destroy the window
            window.destroy()
            # Issue a FocusIn event on something else than new_value_entry to prevent endless looping
            self.root.focus_set()
            # Run the Tk event loop once to process the event
            self.root.update_idletasks()
            # Re-bind the FocusIn event to new_value_entry
            event.widget.bind(
                "<Double-Button>",
                lambda event: self._open_bitmask_selection_window(event, param, change_reason_widget),
            )

        def is_widget_visible(widget: Union[tk.Misc, None]) -> bool:
            return bool(widget and widget.winfo_ismapped())

        def focus_out_handler(_event: tk.Event) -> None:
            if not is_widget_visible(window.focus_get()):
                on_close()

        def get_param_value_msg(_param_name: str, checked_keys: set[int]) -> str:
            _new_decimal_value = BitmaskHelper.get_value_from_keys(checked_keys)
            text = _("{_param_name} Value: {_new_decimal_value}")
            return text.format(**locals())

        def update_label() -> None:
            checked_keys = {key for key, var in checkbox_vars.items() if var.get()}
            close_label.config(text=get_param_value_msg(param.name, checked_keys))

        # Temporarily unbind the FocusIn event to prevent triggering the window again
        event.widget.unbind("<Double-Button>")
        window = tk.Toplevel(self.root)
        title = _("Select {param.name} Bitmask Options")
        window.title(title.format(**locals()))
        checkbox_vars = {}

        main_frame = ttk.Frame(window)
        main_frame.pack(expand=True, fill=tk.BOTH)

        # Bitmask windows are only opened for ttk.Entry widgets, not PairTupleCombobox
        # since comboboxes have predefined values and don't use bitmasks
        if not isinstance(event.widget, ttk.Entry):
            return

        # Convert new_value to a set of checked keys
        new_value_str = event.widget.get() or "0"
        try:
            new_value = int(new_value_str)
        except (ValueError, TypeError):
            messagebox.showerror(
                _("Invalid Bitmask Value"),
                _("The new value '{new_value_str}' is not a valid integer for the {param.name} bitmask.").format(**locals()),
            )
            new_value = 0
        checked_keys = BitmaskHelper.get_checked_keys(new_value, param.bitmask_dict)

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

    def _create_unit_label(self, param: ArduPilotParameter) -> ttk.Label:
        """Create a label displaying the parameter unit."""
        unit_label = ttk.Label(self.view_port, text=param.unit)
        unit_tooltip = param.tooltip_unit
        if unit_tooltip:
            show_tooltip(unit_label, unit_tooltip)
        return unit_label

    def _create_upload_checkbutton(self, param_name: str, fc_connected: bool) -> ttk.Checkbutton:
        """Create a checkbutton for upload selection."""
        self.upload_checkbutton_var[param_name] = tk.BooleanVar(value=fc_connected)
        upload_checkbutton = ttk.Checkbutton(self.view_port, variable=self.upload_checkbutton_var[param_name])
        upload_checkbutton.configure(state="normal" if fc_connected else "disabled")
        msg = _("When selected upload {param_name} new value to the flight controller")
        show_tooltip(upload_checkbutton, msg.format(**locals()))
        return upload_checkbutton

    def _create_change_reason_entry(self, param: ArduPilotParameter) -> ttk.Entry:
        """Create an entry for the parameter change reason."""
        change_reason_entry = ttk.Entry(self.view_port, background="white")
        change_reason_entry.insert(0, param.change_reason)

        if not param.is_editable:
            change_reason_entry.config(state="disabled", background="light grey")
        else:

            def on_focus_out(event: tk.Event) -> None:  # pylint: disable=unused-argument # noqa: ARG001
                new_comment = change_reason_entry.get()
                # Only set the flag and update file if the comment actually changes
                if param.set_change_reason(new_comment):
                    logging_debug(
                        _("Parameter %s change reason changed from %s to %s, will later ask if should be saved to file."),
                        param.name,
                        param.change_reason,
                        new_comment,
                    )
                    self.at_least_one_param_edited = True
                    # Update the corresponding file parameter comment
                    self.local_filesystem.file_parameters[self.current_file][param.name].comment = new_comment

            change_reason_entry.bind(
                "<FocusOut>",
                on_focus_out,
            )

        show_tooltip(change_reason_entry, param.tooltip_change_reason)
        return change_reason_entry

    def _on_parameter_delete(self, param_name: str) -> None:
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

    def _on_parameter_add(self, fc_parameters: dict[str, float]) -> None:
        """Handle parameter addition."""
        add_parameter_window = BaseWindow(self.root)
        add_parameter_window.root.title(_("Add Parameter to ") + self.current_file)
        add_parameter_window.root.geometry("450x300")

        # Label for instruction
        instruction_label = ttk.Label(add_parameter_window.main_frame, text=_("Enter the parameter name to add:"))
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

        def custom_selection_handler(event: tk.Event) -> None:
            parameter_name_combobox.update_entry_from_listbox(event)
            param_name = parameter_name_combobox.get().upper()
            if self._confirm_parameter_addition(param_name, fc_parameters):
                add_parameter_window.root.destroy()
            else:
                add_parameter_window.root.focus()

        # Bindings to handle Enter press and selection while respecting original functionalities
        parameter_name_combobox.bind("<Return>", custom_selection_handler)
        parameter_name_combobox.bind("<<ComboboxSelected>>", custom_selection_handler)

    def _confirm_parameter_addition(self, param_name: str, fc_parameters: dict[str, float]) -> bool:
        """Confirm and process parameter addition."""
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

    def get_upload_selected_params(self, current_file: str, gui_complexity: str) -> dict[str, Par]:
        """Get the parameters selected for upload."""
        # Check if we should show upload column based on GUI complexity
        if not self._should_show_upload_column(gui_complexity):
            # all parameters are selected for upload in simple mode
            return self.local_filesystem.file_parameters[current_file]

        selected_params = {}
        for param_name, checkbutton_state in self.upload_checkbutton_var.items():
            if checkbutton_state.get():
                selected_params[param_name] = self.local_filesystem.file_parameters[current_file][param_name]
        return selected_params

    def get_at_least_one_param_edited(self) -> bool:
        """Get whether at least one parameter has been edited."""
        return self.at_least_one_param_edited

    def set_at_least_one_param_edited(self, value: bool) -> None:
        """Set whether at least one parameter has been edited."""
        self.at_least_one_param_edited = value
