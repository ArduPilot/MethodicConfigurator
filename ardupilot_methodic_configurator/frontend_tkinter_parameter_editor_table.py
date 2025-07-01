"""
Parameter editor table GUI.

This file is part of Ardupilot methodic configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2025 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import tkinter as tk

# from logging import warning as logging_warning
# from logging import error as logging_error
from logging import critical as logging_critical
from logging import debug as logging_debug
from logging import info as logging_info
from math import isfinite, isnan, nan
from platform import system as platform_system
from sys import exit as sys_exit
from tkinter import messagebox, ttk
from typing import Any, Union

from ardupilot_methodic_configurator import _
from ardupilot_methodic_configurator.annotate_params import Par
from ardupilot_methodic_configurator.backend_filesystem import LocalFilesystem, is_within_tolerance

# from ardupilot_methodic_configurator.backend_flightcontroller import FlightController
# from ardupilot_methodic_configurator.frontend_tkinter_auto_resize_combobox import AutoResizeCombobox
from ardupilot_methodic_configurator.frontend_tkinter_base_window import BaseWindow
from ardupilot_methodic_configurator.frontend_tkinter_entry_dynamic import EntryWithDynamicalyFilteredListbox
from ardupilot_methodic_configurator.frontend_tkinter_pair_tuple_combobox import PairTupleCombobox
from ardupilot_methodic_configurator.frontend_tkinter_rich_text import get_widget_font_family_and_size
from ardupilot_methodic_configurator.frontend_tkinter_scroll_frame import ScrollFrame
from ardupilot_methodic_configurator.frontend_tkinter_show import show_tooltip

NEW_VALUE_WIDGET_WIDTH = 9


# pylint: disable=too-many-lines


class ParameterEditorTable(ScrollFrame):  # pylint: disable=too-many-ancestors
    """
    A class to manage and display the parameter editor table within the GUI.

    This class inherits from ScrollFrame and is responsible for creating,
    managing, and updating the table that displays parameters for editing.
    """

    def __init__(self, master, local_filesystem: LocalFilesystem, parameter_editor) -> None:  # noqa: ANN001
        super().__init__(master)
        self.root = master
        self.local_filesystem = local_filesystem
        self.parameter_editor = parameter_editor
        self.current_file = ""
        self.upload_checkbutton_var: dict[str, tk.BooleanVar] = {}
        self.at_least_one_param_edited = False

        style = ttk.Style()
        style.configure("narrow.TButton", padding=0, width=4, border=(0, 0, 0, 0))

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

    def repopulate(self, selected_file: str, fc_parameters: dict[str, float], show_only_differences: bool) -> None:
        for widget in self.view_port.winfo_children():
            widget.destroy()
        self.current_file = selected_file

        # Check if upload column should be shown based on UI complexity
        show_upload_column = self._should_show_upload_column()

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
            self._update_table(different_params, fc_parameters, self.parameter_editor.gui_complexity)
            if not different_params:
                info_msg = _("No different parameters found in {selected_file}. Skipping...").format(**locals())
                logging_info(info_msg)
                messagebox.showinfo(_("ArduPilot methodic configurator"), info_msg)
                self.parameter_editor.on_skip_click(force_focus_out_event=False)
                return
        else:
            self._update_table(
                self.local_filesystem.file_parameters[selected_file],
                fc_parameters,
                self.parameter_editor.gui_complexity,
            )
        # Scroll to the top of the parameter table
        self.canvas.yview("moveto", 0)

    def rename_fc_connection(self, selected_file: str) -> None:
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
                # will ask the user to save changes before switching to another file
                self.at_least_one_param_edited = True
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
                    # will ask the user to save changes before switching to another file
                    self.at_least_one_param_edited = True

    def _update_table(self, params: dict[str, Par], fc_parameters: dict[str, float], gui_complexity: str) -> None:  # pylint: disable=too-many-locals
        current_param_name: str = ""
        show_upload_column = self._should_show_upload_column(gui_complexity)

        try:
            for i, (param_name, param) in enumerate(params.items(), 1):
                current_param_name = param_name
                param_metadata = self.local_filesystem.doc_dict.get(param_name, {})
                param_default = self.local_filesystem.param_default_dict.get(param_name, None)
                doc_tooltip = param_metadata.get(
                    "doc_tooltip", _("No documentation available in apm.pdef.xml for this parameter")
                )

                column: list[tk.Widget] = self._create_column_widgets(
                    param_name, param, param_metadata, param_default, doc_tooltip, fc_parameters, show_upload_column
                )

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

    def _create_column_widgets(  # pylint: disable=too-many-arguments,too-many-positional-arguments
        self,
        param_name: str,
        param: Par,
        param_metadata: dict[str, Any],
        param_default: Union[None, Par],
        doc_tooltip: str,
        fc_parameters: dict[str, float],
        show_upload_column: bool,
    ) -> list[tk.Widget]:
        """Create all column widgets for a parameter row."""
        column: list[tk.Widget] = []
        column.append(self._create_delete_button(param_name))
        column.append(self._create_parameter_name(param_name, param_metadata, doc_tooltip))
        column.append(self._create_flightcontroller_value(fc_parameters, param_name, param_default, doc_tooltip))
        column.append(self._create_new_value_entry(param_name, param, param_metadata, param_default, doc_tooltip))
        column.append(self._create_unit_label(param_metadata))

        if show_upload_column:
            column.append(self._create_upload_checkbutton(param_name, bool(fc_parameters)))

        # workaround a mypy issue
        column.append(self._create_change_reason_entry(param_name, param, column[3]))  # type: ignore[arg-type]

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
        delete_button = ttk.Button(
            self.view_port, text=_("Del"), style="narrow.TButton", command=lambda: self._on_parameter_delete(param_name)
        )
        tooltip_msg = _("Delete {param_name} from the {self.current_file} file")
        show_tooltip(delete_button, tooltip_msg.format(**locals()))
        return delete_button

    def _create_parameter_name(self, param_name: str, param_metadata: dict[str, Any], doc_tooltip: str) -> ttk.Label:
        is_calibration = param_metadata.get("Calibration", False)
        is_readonly = param_metadata.get("ReadOnly", False)
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

    def _create_flightcontroller_value(
        self, fc_parameters: dict[str, float], param_name: str, param_default: Union[None, Par], doc_tooltip: str
    ) -> ttk.Label:
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

        # Use numerically sorted tooltip for Current Value column if available
        param_metadata = self.local_filesystem.doc_dict.get(param_name, {})
        sorted_tooltip = param_metadata.get("doc_tooltip_sorted_numerically", doc_tooltip)
        if sorted_tooltip:
            show_tooltip(flightcontroller_value, sorted_tooltip)
        return flightcontroller_value

    def _update_combobox_style_on_selection(
        self, combobox_widget: PairTupleCombobox, param_default: Union[None, Par], event: tk.Event
    ) -> None:
        try:
            # we want None to raise an exception
            current_value = float(combobox_widget.get_selected_key())  # type: ignore[arg-type]
            has_default_value = param_default is not None and is_within_tolerance(current_value, param_default.value)
            combobox_widget.configure(style="default_v.TCombobox" if has_default_value else "readonly.TCombobox")
            event.width = NEW_VALUE_WIDGET_WIDTH
            combobox_widget.on_combo_configure(event)
        except ValueError:
            msg = _("Could not solve the selected {combobox_widget} key to a float value.")
            logging_info(msg.format(**locals()))

    @staticmethod
    def _update_new_value_entry_text(
        new_value_entry: Union[ttk.Entry, tk.Entry], value: float, param_default: Union[None, Par]
    ) -> None:
        if isinstance(new_value_entry, PairTupleCombobox):
            return
        new_value_entry.delete(0, tk.END)
        value_str = format(value, ".6f").rstrip("0").rstrip(".")
        new_value_entry.insert(0, value_str)
        if param_default is not None and is_within_tolerance(value, param_default.value):
            # Only ttk.Entry widgets support style configuration
            if isinstance(new_value_entry, ttk.Entry):
                new_value_entry.configure(style="default_v.TEntry")
        # Only ttk.Entry widgets support style configuration
        elif isinstance(new_value_entry, ttk.Entry):
            new_value_entry.configure(style="TEntry")

    def _create_new_value_entry(  # pylint: disable=too-many-arguments,too-many-positional-arguments,too-many-locals,too-many-statements # noqa: PLR0915
        self,
        param_name: str,
        param: Par,
        param_metadata: dict[str, Any],
        param_default: Union[None, Par],
        doc_tooltip: str,
    ) -> Union[PairTupleCombobox, ttk.Entry]:
        is_bitmask = param_metadata and "Bitmask" in param_metadata
        is_forced_or_derived, param_type = self._is_forced_or_derived_parameter(param_name)
        present_as_forced = param_type == "forced"
        present_as_derived = param_type == "derived"

        if is_forced_or_derived:
            if param_type == "forced":
                new_value = self.local_filesystem.forced_parameters[self.current_file][param_name].value
            else:  # param_type == "derived"
                new_value = self.local_filesystem.derived_parameters[self.current_file][param_name].value

            if (is_bitmask and param.value != new_value) or not is_within_tolerance(param.value, new_value):
                param.value = new_value
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
                if present_as_forced or present_as_derived
                else "default_v.TCombobox"
                if has_default_value
                else "readonly.TCombobox",
            )
            new_value_entry.set(selected_value)
            font_family, font_size = get_widget_font_family_and_size(new_value_entry)
            font_size -= 2 if platform_system() == "Windows" else 1
            new_value_entry.config(state="readonly", width=NEW_VALUE_WIDGET_WIDTH, font=(font_family, font_size))
            new_value_entry.bind(  # type: ignore[call-overload] # workaround a mypy issue
                "<<ComboboxSelected>>",
                lambda event: self._update_combobox_style_on_selection(new_value_entry, param_default, event),
                "+",
            )
        else:
            new_value_entry = ttk.Entry(self.view_port, width=NEW_VALUE_WIDGET_WIDTH + 1, justify=tk.RIGHT)
            ParameterEditorTable._update_new_value_entry_text(new_value_entry, param.value, param_default)
            bitmask_dict = param_metadata.get("Bitmask") if param_metadata else None
        try:
            old_value = self.local_filesystem.file_parameters[self.current_file][param_name].value
        except KeyError as e:
            logging_critical(_("Parameter %s not found in the %s file: %s"), param_name, self.current_file, e, exc_info=True)
            sys_exit(1)

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
        def show_parameter_error(_event: tk.Event) -> None:
            if present_as_forced:
                messagebox.showerror(_("Forced Parameter"), forced_error_msg)
            elif present_as_derived:
                messagebox.showerror(_("Derived Parameter"), derived_error_msg)

        if present_as_forced or present_as_derived:
            new_value_entry.config(state="disabled", background="light grey")
            new_value_entry.bind("<Button-1>", show_parameter_error)
            # Also bind to right-click for completeness
            new_value_entry.bind("<Button-3>", show_parameter_error)
        elif bitmask_dict:
            new_value_entry.bind(
                "<Double-Button>",
                lambda event: self._open_bitmask_selection_window(event, param_name, bitmask_dict, old_value),
            )
            # pylint: disable=line-too-long
            new_value_entry.bind(
                "<FocusOut>",
                lambda event, current_file=self.current_file, param_name=param_name: self._on_parameter_value_change(  # type: ignore[misc]
                    event, current_file, param_name
                ),
            )
            # pylint: enable=line-too-long
        else:
            # pylint: disable=line-too-long
            new_value_entry.bind(
                "<FocusOut>",
                lambda event, current_file=self.current_file, param_name=param_name: self._on_parameter_value_change(  # type: ignore[misc]
                    event, current_file, param_name
                ),
            )
            # pylint: enable=line-too-long
        if doc_tooltip:
            show_tooltip(new_value_entry, doc_tooltip)
        return new_value_entry

    def _open_bitmask_selection_window(self, event: tk.Event, param_name: str, bitmask_dict: dict, old_value: float) -> None:  # pylint: disable=too-many-locals
        def on_close() -> None:
            checked_keys = [key for key, var in checkbox_vars.items() if var.get()]
            # Convert checked keys back to a decimal value
            new_decimal_value = sum(1 << key for key in checked_keys)
            # Update new_value_entry with the new decimal value
            # For bitmask windows, event.widget should always be ttk.Entry (not PairTupleCombobox)
            # since bitmasks are only created for Entry widgets, not Comboboxes
            if isinstance(event.widget, ttk.Entry):
                ParameterEditorTable._update_new_value_entry_text(
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
                "<Double-Button>",
                lambda event: self._open_bitmask_selection_window(event, param_name, bitmask_dict, old_value),
            )

        def is_widget_visible(widget: Union[tk.Misc, None]) -> bool:
            return bool(widget and widget.winfo_ismapped())

        def focus_out_handler(_event: tk.Event) -> None:
            if not is_widget_visible(window.focus_get()):
                on_close()

        def get_param_value_msg(_param_name: str, checked_keys: set) -> str:
            _new_decimal_value = sum(1 << key for key in checked_keys)
            text = _("{_param_name} Value: {_new_decimal_value}")
            return text.format(**locals())

        def update_label() -> None:
            checked_keys = {key for key, var in checkbox_vars.items() if var.get()}
            close_label.config(text=get_param_value_msg(param_name, checked_keys))

        # Temporarily unbind the FocusIn event to prevent triggering the window again
        event.widget.unbind("<Double-Button>")
        window = tk.Toplevel(self.root)
        title = _("Select {param_name} Bitmask Options")
        window.title(title.format(**locals()))
        checkbox_vars = {}

        main_frame = ttk.Frame(window)
        main_frame.pack(expand=True, fill=tk.BOTH)

        # Convert current_value to a set of checked keys
        widget = event.widget
        # Bitmask windows are only opened for ttk.Entry widgets, not PairTupleCombobox
        # since comboboxes have predefined values and don't use bitmasks
        if not isinstance(widget, ttk.Entry):
            return

        current_value_str = widget.get() or "0"

        try:
            current_value = int(current_value_str)
        except ValueError:
            current_value = 0

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
        window.bind("<FocusOut>", focus_out_handler)
        for child in window.winfo_children():
            child.bind("<FocusOut>", focus_out_handler)

        # Make sure the window is visible before disabling the parent window
        window.deiconify()
        self.root.update_idletasks()
        window.grab_set()

        window.wait_window()  # Wait for the window to be closed

    def _create_unit_label(self, param_metadata: dict[str, Union[float, str]]) -> ttk.Label:
        unit_label = ttk.Label(self.view_port, text=param_metadata.get("unit", ""))
        unit_tooltip = str(
            param_metadata.get("unit_tooltip", _("No documentation available in apm.pdef.xml for this parameter"))
        )
        if unit_tooltip:
            show_tooltip(unit_label, unit_tooltip)
        return unit_label

    def _create_upload_checkbutton(self, param_name: str, fc_connected: bool) -> ttk.Checkbutton:
        self.upload_checkbutton_var[param_name] = tk.BooleanVar(value=fc_connected)
        upload_checkbutton = ttk.Checkbutton(self.view_port, variable=self.upload_checkbutton_var[param_name])
        upload_checkbutton.configure(state="normal" if fc_connected else "disabled")
        msg = _("When selected upload {param_name} new value to the flight controller")
        show_tooltip(upload_checkbutton, msg.format(**locals()))
        return upload_checkbutton

    def _create_change_reason_entry(
        self, param_name: str, param: Par, new_value_entry: Union[ttk.Entry, PairTupleCombobox]
    ) -> ttk.Entry:
        is_forced_or_derived, param_type = self._is_forced_or_derived_parameter(param_name)
        present_as_forced = is_forced_or_derived

        if (
            param_type == "forced"
            and param.comment != self.local_filesystem.forced_parameters[self.current_file][param_name].comment
        ):
            param.comment = self.local_filesystem.forced_parameters[self.current_file][param_name].comment
            self.at_least_one_param_edited = True
        elif (
            param_type == "derived"
            and param.comment != self.local_filesystem.derived_parameters[self.current_file][param_name].comment
        ):
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
                lambda event, current_file=self.current_file, param_name=param_name: self._on_parameter_change_reason_change(  # type: ignore[misc]
                    event, current_file, param_name
                ),
            )
            # pylint: enable=line-too-long
        _value = new_value_entry.get()
        msg = _("Reason why {param_name} should change to {_value}")
        show_tooltip(change_reason_entry, msg.format(**locals()))
        return change_reason_entry

    def _on_parameter_delete(self, param_name: str) -> None:
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

    def _on_parameter_add(self, fc_parameters: dict[str, float]) -> None:
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
            if self._confirm_parameter_addition(parameter_name_combobox.get().upper(), fc_parameters):
                add_parameter_window.root.destroy()
            else:
                add_parameter_window.root.focus()

        # Bindings to handle Enter press and selection while respecting original functionalities
        parameter_name_combobox.bind("<Return>", custom_selection_handler)
        parameter_name_combobox.bind("<<ComboboxSelected>>", custom_selection_handler)

    def _confirm_parameter_addition(self, param_name: str, fc_parameters: dict[str, float]) -> bool:
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

    def _on_parameter_value_change(self, event: tk.Event, current_file: str, param_name: str) -> None:
        # Get the new value from the Entry widget
        widget = event.widget
        if isinstance(widget, PairTupleCombobox):
            new_value = widget.get_selected_key()
        elif isinstance(widget, (ttk.Entry, tk.Entry)):  # it is a ttk.Entry. The tk.Entry check is just defensive programming
            new_value = widget.get()
        else:
            return  # Unknown widget type

        try:
            old_value = self.local_filesystem.file_parameters[current_file][param_name].value
        except KeyError as e:
            logging_critical(_("Parameter %s not found in the %s file: %s"), param_name, current_file, e, exc_info=True)
            sys_exit(1)

        # Handle None or empty values
        if new_value is None:
            new_value = ""

        # Validate the new value format
        is_valid, p = self._validate_parameter_value_format(str(new_value), param_name)
        if not is_valid:
            # Revert to the previous (valid) value
            p = old_value

        # Validate the parameter bounds
        if not self._validate_parameter_bounds(p, param_name):
            # Revert to the previous (valid) value
            p = old_value

        # Check if the value has changed
        changed = self._check_parameter_value_changed(old_value, p)

        # Update the parameter change state
        self._update_parameter_change_state(changed=changed, param_name=param_name)

        # Update the params dictionary with the new value
        self.local_filesystem.file_parameters[current_file][param_name].value = p

        # Update the displayed value in the Entry or Combobox
        if isinstance(
            event.widget, (ttk.Entry, tk.Entry)
        ):  # it is a ttk.Entry. The tk.Entry check is just defensive programming
            self._update_new_value_entry_text(event.widget, p, self.local_filesystem.param_default_dict.get(param_name, None))
        elif isinstance(event.widget, PairTupleCombobox):
            # For PairTupleCombobox, update the style based on whether it matches default value
            param_default = self.local_filesystem.param_default_dict.get(param_name, None)
            self._update_combobox_style_on_selection(event.widget, param_default, event)

        # Update the tooltip for the change reason entry
        self._update_change_reason_entry_tooltip(param_name, p)

    def _validate_parameter_value_format(self, value_str: str, param_name: str) -> tuple[bool, float]:
        """
        Validate that the parameter value is a valid float.

        Args:
            value_str: String value to validate
            param_name: Parameter name for error messages

        Returns:
            Tuple of (is_valid, parsed_value). If invalid, parsed_value is nan.

        """
        try:
            parsed_value = float(value_str)
            # Reject infinity and NaN values
            if not isfinite(parsed_value) or isnan(parsed_value):
                error_msg = _("The value for {param_name} must be a finite number.")
                messagebox.showerror(_("Invalid Value"), error_msg.format(param_name=param_name))
                return False, nan
            return True, parsed_value
        except ValueError:
            error_msg = _("The value for {param_name} must be a valid float.")
            messagebox.showerror(_("Invalid Value"), error_msg.format(param_name=param_name))
            return False, nan

    def _validate_parameter_bounds(self, value: float, param_name: str) -> bool:
        """
        Validate parameter value against min/max bounds.

        Args:
            value: Parameter value to validate
            param_name: Parameter name for error messages

        Returns:
            True if value is valid or user accepts out-of-bounds value

        """
        p_min, p_max = self._get_parameter_validation_bounds(param_name)

        if p_min is not None and value < p_min:
            msg = _("The value for {param_name} {p} should be greater than {p_min}\n")
            if not messagebox.askyesno(
                _("Out-of-bounds Value"),
                msg.format(param_name=param_name, p=value, p_min=p_min) + _("Use out-of-bounds value?"),
                icon="warning",
            ):
                return False

        if p_max is not None and value > p_max:
            msg = _("The value for {param_name} {p} should be smaller than {p_max}\n")
            if not messagebox.askyesno(
                _("Out-of-bounds Value"),
                msg.format(param_name=param_name, p=value, p_max=p_max) + _("Use out-of-bounds value?"),
                icon="warning",
            ):
                return False

        return True

    def _get_parameter_validation_bounds(self, param_name: str) -> tuple[Union[float, None], Union[float, None]]:
        """
        Get the validation bounds for a parameter.

        Args:
            param_name: Name of the parameter to get bounds for

        Returns:
            Tuple of (min_value, max_value) or (None, None) if no bounds available

        """
        param_metadata = self.local_filesystem.doc_dict.get(param_name, {})
        return param_metadata.get("min", None), param_metadata.get("max", None)

    def _check_parameter_value_changed(self, old_value: float, new_value: float) -> bool:
        """
        Check if parameter value has changed within tolerance.

        Args:
            old_value: Original parameter value
            new_value: New parameter value

        Returns:
            True if value has changed beyond tolerance

        """
        return not is_within_tolerance(old_value, new_value)

    def _update_parameter_change_state(self, changed: bool, param_name: str) -> None:
        """
        Update the parameter change state and log if needed.

        Args:
            changed: Whether the parameter has changed
            param_name: Name of the parameter that changed

        """
        if changed and not self.at_least_one_param_edited:
            logging_debug(_("Parameter %s changed, will later ask if change(s) should be saved to file."), param_name)
        self.at_least_one_param_edited = changed or self.at_least_one_param_edited

    def _find_change_reason_widget_by_parameter(self, param_name: str) -> Union[ttk.Entry, None]:
        """
        Find the change reason entry widget for a specific parameter.

        Args:
            param_name: Name of the parameter to find change reason widget for

        Returns:
            The change reason entry widget, or None if not found

        """
        show_upload_column = self._should_show_upload_column()
        change_reason_column = self._get_change_reason_column_index(show_upload_column)

        # Find the change reason entry widget for this parameter
        for widget in self.view_port.winfo_children():
            try:
                widget_column = widget.grid_info().get("column", 0)
            except tk.TclError:
                # Widget not properly gridded, skip it
                continue

            if isinstance(widget, ttk.Entry) and widget_column == change_reason_column:
                # Get the parameter label in the same row
                try:
                    row = widget.grid_info().get("row")
                except tk.TclError:
                    continue

                for param_widget in self.view_port.winfo_children():
                    try:
                        param_column = param_widget.grid_info().get("column", 0)
                        param_row = param_widget.grid_info().get("row")
                    except tk.TclError:
                        continue

                    if (
                        isinstance(param_widget, ttk.Label)
                        and param_column == 1
                        and param_row == row
                        and param_widget.cget("text").strip() == param_name
                    ):
                        return widget
        return None

    def _update_change_reason_entry_tooltip(self, param_name: str, param_value: float) -> None:
        """Update the tooltip on the change reason entry with the current parameter value."""
        value_str = format(param_value, ".6f").rstrip("0").rstrip(".")

        # Use the helper method to find the change reason widget
        change_reason_widget = self._find_change_reason_widget_by_parameter(param_name)
        if change_reason_widget:
            msg = _("Reason why {param_name} should change to {value_str}")
            show_tooltip(change_reason_widget, msg.format(param_name=param_name, value_str=value_str))
        else:
            logging_debug(_("Could not find change reason entry widget for parameter %s (%s)"), param_name, value_str)

    def _on_parameter_change_reason_change(self, event: tk.Event, current_file: str, param_name: str) -> None:
        # Get the new value from the Entry widget
        widget = event.widget
        if not isinstance(
            widget, (ttk.Entry, tk.Entry)
        ):  # it is a ttk.Entry. The tk.Entry check is just defensive programming
            return
        new_value = widget.get()
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

    def get_upload_selected_params(self, current_file: str, gui_complexity: str) -> dict[str, Par]:
        selected_params = {}

        if not self._should_show_upload_column(gui_complexity):
            # all parameters are selected for upload in simple mode
            return self.local_filesystem.file_parameters[current_file]

        for param_name, checkbutton_state in self.upload_checkbutton_var.items():
            if checkbutton_state.get():
                selected_params[param_name] = self.local_filesystem.file_parameters[current_file][param_name]
        return selected_params

    def generate_edit_widgets_focus_out(self) -> None:
        # Trigger the <FocusOut> event for all entry widgets to ensure all changes are processed
        for widget in self.view_port.winfo_children():
            if isinstance(widget, ttk.Entry):
                widget.event_generate("<FocusOut>", when="now")

    def get_at_least_one_param_edited(self) -> bool:
        return self.at_least_one_param_edited

    def set_at_least_one_param_edited(self, value: bool) -> None:
        self.at_least_one_param_edited = value

    def _is_forced_or_derived_parameter(self, param_name: str) -> tuple[bool, str]:
        """
        Check if a parameter is forced or derived and return the appropriate type.

        Args:
            param_name: Name of the parameter to check

        Returns:
            Tuple of (is_forced_or_derived, parameter_type) where parameter_type is 'forced', 'derived', or ''

        """
        if (
            self.current_file in self.local_filesystem.forced_parameters
            and param_name in self.local_filesystem.forced_parameters[self.current_file]
        ):
            return True, "forced"

        if (
            self.current_file in self.local_filesystem.derived_parameters
            and param_name in self.local_filesystem.derived_parameters[self.current_file]
        ):
            return True, "derived"

        return False, ""
