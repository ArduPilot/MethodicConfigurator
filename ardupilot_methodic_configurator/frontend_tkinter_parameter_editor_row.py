"""
Parameter editor row UI component.

This file is part of Ardupilot methodic configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2025 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import tkinter as tk
from logging import debug as logging_debug
from logging import info as logging_info
from math import nan
from platform import system as platform_system
from tkinter import messagebox, ttk
from typing import Callable, Optional, Union

from ardupilot_methodic_configurator import _
from ardupilot_methodic_configurator.ardupilot_parameter import ArduPilotParameter
from ardupilot_methodic_configurator.backend_filesystem import is_within_tolerance
from ardupilot_methodic_configurator.frontend_tkinter_pair_tuple_combobox import PairTupleCombobox
from ardupilot_methodic_configurator.frontend_tkinter_rich_text import get_widget_font_family_and_size
from ardupilot_methodic_configurator.frontend_tkinter_show import show_tooltip

NEW_VALUE_WIDGET_WIDTH = 9


class BitmaskWindowHandler:
    """Class to handle bitmask selection window and operations."""

    def __init__(
        self,
        parent: tk.Widget,
        parameter_name: str,
        bitmask_dict: dict,
        current_value: float,
        on_selection_applied_callback: Optional[Callable[[float], None]] = None,
    ) -> None:
        """
        Initialize the bitmask handler.

        Args:
            parent: The parent widget for the window
            parameter_name: Name of the parameter being edited
            bitmask_dict: Dictionary mapping bit values to their descriptions
            current_value: Current value of the parameter
            on_selection_applied_callback: Callback function to call with the new value when OK is clicked

        """
        self.parent = parent
        self.parameter_name = parameter_name
        self.bitmask_dict = bitmask_dict
        self.current_value = current_value
        self.on_selection_applied_callback = on_selection_applied_callback
        self.bitmask_window = None
        self.bitmask_vars = {}

    def show_window(self, x_pos: int = 100, y_pos: int = 100) -> None:
        """
        Create and display the bitmask selection window.

        Args:
            x_pos: X position for the window
            y_pos: Y position for the window

        """
        # Create a bitmask selection dialog window
        self.bitmask_window = tk.Toplevel(self.parent)
        self.bitmask_window.title(_("Bitmask Selection for %s") % self.parameter_name)

        # Debug logging to see the actual structure of the bitmask data
        logging_debug("Bitmask dict for %s: %s", self.parameter_name, self.bitmask_dict)

        # Create the widgets for the window
        checkbutton_count = self._create_bitmask_checkbuttons()
        self._create_button_frame(checkbutton_count)

        # Position the window
        self.bitmask_window.geometry(f"+{x_pos}+{y_pos}")
        self.bitmask_window.transient(self.parent)

        # Make sure window is created and visible before calling grab_set()
        self.bitmask_window.update_idletasks()

        # Use try/except block to handle potential "window not viewable" errors
        try:
            self.bitmask_window.grab_set()
            self.bitmask_window.focus_set()
        except tk.TclError as e:
            logging_debug(_("Could not grab focus for bitmask window: %s"), str(e))

    def _create_bitmask_checkbuttons(self) -> int:
        """
        Create checkbuttons for each bitmask value.

        Returns:
            Number of checkbuttons created

        """
        checkbutton_count = 0
        valid_bits = []

        # First, validate all bit values outside the loop to avoid try-except overhead
        for bit_value, bit_text in self.bitmask_dict.items():
            # Avoid try-except in loop for performance reasons
            if not isinstance(bit_value, str) or not bit_value.isdigit():
                logging_debug(_("Invalid bit value %s for parameter %s: not a valid integer"), bit_value, self.parameter_name)
                continue

            bit_num = int(bit_value)
            is_set = bool(int(self.current_value) & (1 << bit_num))
            valid_bits.append((bit_num, bit_text, is_set))

        # Now create checkbuttons only for valid bits
        for i, (bit_num, bit_text, is_set) in enumerate(valid_bits):
            var = tk.BooleanVar(value=is_set)
            self.bitmask_vars[bit_num] = var

            checkbutton = ttk.Checkbutton(self.bitmask_window, text=f"{bit_text} (bit {bit_num})", variable=var)
            checkbutton.grid(row=i, column=0, sticky="w", padx=10, pady=2)
            checkbutton_count += 1

        # If no valid bitmask values were found, show an info message
        if checkbutton_count == 0:
            ttk.Label(
                self.bitmask_window,
                text=_("No bitmask values found for this parameter. Please check parameter documentation."),
                wraplength=300,
            ).grid(row=0, column=0, padx=10, pady=10)

        return checkbutton_count

    def _create_button_frame(self, checkbutton_count: int) -> None:
        """
        Create the button frame with OK and Cancel buttons.

        Args:
            checkbutton_count: Number of checkbuttons, used for positioning

        """
        button_frame = ttk.Frame(self.bitmask_window)
        button_frame.grid(row=max(checkbutton_count, 1), column=0, pady=10, sticky="ew")

        # Add OK and Cancel buttons
        ttk.Button(button_frame, text=_("OK"), command=self._apply_selection).pack(side=tk.LEFT, padx=10)

        ttk.Button(button_frame, text=_("Cancel"), command=self.bitmask_window.destroy).pack(side=tk.RIGHT, padx=10)

    def _apply_selection(self) -> None:
        """Calculate the new value from selected bits and apply it."""
        # Calculate the new value from selected bits
        new_value = self.calculate_bitmask_value()

        # Call the callback function with the new value
        if self.on_selection_applied_callback:
            self.on_selection_applied_callback(new_value)

        # Close the window
        self.bitmask_window.destroy()

    def calculate_bitmask_value(self) -> float:
        """
        Calculate the bitmask value from the selected checkboxes.

        Returns:
            The calculated bitmask value

        """
        new_value = 0
        for bit_num, var in self.bitmask_vars.items():
            if var.get():
                new_value |= 1 << bit_num
        return float(new_value)


class ParameterEditorRow:
    """Class to encapsulate a row in the parameter editor table."""

    def __init__(
        self,
        table: "ParameterEditorTable",
        param: ArduPilotParameter,
        row_index: int,
        on_value_changed_callback: Callable[[str, float], None],
        on_comment_changed_callback: Callable[[str, str], None],
        on_delete_callback: Callable[[str], None],
    ) -> None:
        """
        Initialize a parameter editor row with all its widgets.

        Args:
            table: The parent parameter editor table
            param: The parameter object to display
            row_index: The row index in the table
            on_value_changed_callback: Callback to call when the parameter value changes
            on_comment_changed_callback: Callback to call when the parameter comment changes
            on_delete_callback: Callback to call when the parameter is deleted

        """
        self.table = table
        self.param = param
        self.row_index = row_index
        self.on_value_changed_callback = on_value_changed_callback
        self.on_comment_changed_callback = on_comment_changed_callback
        self.on_delete_callback = on_delete_callback
        self.old_value = param.value  # Track the value when created to detect changes

        # UI widgets
        self.delete_button: Optional[ttk.Button] = None
        self.param_label: Optional[ttk.Label] = None
        self.fc_value_label: Optional[ttk.Label] = None
        self.new_value_widget: Optional[Union[PairTupleCombobox, ttk.Entry]] = None
        self.unit_label: Optional[ttk.Label] = None
        self.upload_checkbutton: Optional[ttk.Checkbutton] = None
        self.change_reason_entry: Optional[ttk.Entry] = None
        self.upload_var = tk.BooleanVar(value=param.has_fc_value)

        # Create the widgets for this row
        self.create_widgets()

    def create_widgets(self) -> None:
        """Create all the widgets for this row and place them in the grid."""
        self.delete_button = self._create_delete_button()
        self.param_label = self._create_parameter_name()
        self.fc_value_label = self._create_flightcontroller_value()
        self.new_value_widget = self._create_new_value_entry()
        self.unit_label = self._create_unit_label()
        self.upload_checkbutton = self._create_upload_checkbutton()
        self.change_reason_entry = self._create_change_reason_entry()

        # Place the widgets in the grid
        self.delete_button.grid(row=self.row_index, column=0, sticky="w", padx=0)
        self.param_label.grid(row=self.row_index, column=1, sticky="w", padx=0)
        self.fc_value_label.grid(row=self.row_index, column=2, sticky="e", padx=0)
        self.new_value_widget.grid(row=self.row_index, column=3, sticky="e", padx=0)
        self.unit_label.grid(row=self.row_index, column=4, sticky="e", padx=0)
        self.upload_checkbutton.grid(row=self.row_index, column=5, sticky="e", padx=0)
        self.change_reason_entry.grid(row=self.row_index, column=6, sticky="ew", padx=(0, 5))

    def _create_delete_button(self) -> ttk.Button:
        """Create the delete button for this parameter row."""
        delete_button = ttk.Button(
            self.table.view_port,
            text=_("Del"),
            style="narrow.TButton",
            command=self._on_delete_click,
        )
        tooltip_msg = _("Delete {param_name} from the {file} file")
        show_tooltip(delete_button, tooltip_msg.format(param_name=self.param.name, file=self.table.current_file))
        return delete_button

    def _create_parameter_name(self) -> ttk.Label:
        """Create the parameter name label."""
        background_color = (
            "red"
            if self.param.is_readonly
            else "yellow"
            if self.param.is_calibration
            else ttk.Style(self.table.root).lookup("TFrame", "background")
        )

        parameter_label = ttk.Label(
            self.table.view_port,
            text=self.param.name + (" " * (16 - len(self.param.name))),
            background=background_color,
        )
        if self.param.doc_tooltip:
            show_tooltip(parameter_label, self.param.doc_tooltip)
        return parameter_label

    def _create_flightcontroller_value(self) -> ttk.Label:
        """Create the flight controller value label."""
        if self.param.has_fc_value:
            background_color = (
                "light blue"
                if self.param.has_default_value
                and is_within_tolerance(
                    self.param.fc_value,
                    self.param.default_value,  # type: ignore[misc]
                )
                else ttk.Style(self.table.root).lookup("TLabel", "background")
            )
            flightcontroller_value = ttk.Label(
                self.table.view_port, text=self.param.fc_value_as_string, background=background_color
            )
        else:
            flightcontroller_value = ttk.Label(self.table.view_port, text=_("N/A"), background="orange")
        if self.param.doc_tooltip:
            show_tooltip(flightcontroller_value, self.param.doc_tooltip)
        return flightcontroller_value

    def _create_new_value_entry(self) -> Union[PairTupleCombobox, ttk.Entry]:
        """Create the widget for editing the parameter value."""
        # Determine the appropriate widget style based on parameter properties
        style = (
            "TCombobox"
            if self.param.is_forced or self.param.is_derived
            else "default_v.TCombobox"
            if self.param.has_default_value
            else "readonly.TCombobox"
        )

        # Create either a combobox or a regular entry based on parameter type
        if self.param.is_in_values_dict():
            selected_value = self.param.get_selected_value_from_dict()
            new_value_widget = PairTupleCombobox(
                self.table.view_port,
                self.param.values_dict,
                self.param.value_as_string,
                self.param.name,
                style=style,
            )
            new_value_widget.set(selected_value)
            font_family, font_size = get_widget_font_family_and_size(new_value_widget)
            font_size -= 2 if platform_system() == "Windows" else 1
            new_value_widget.config(state="readonly", width=NEW_VALUE_WIDGET_WIDTH, font=(font_family, font_size))
            new_value_widget.bind(  # type: ignore[call-overload]
                "<<ComboboxSelected>>",
                self._on_combobox_selected,
                "+",
            )
        else:
            new_value_widget = ttk.Entry(self.table.view_port, width=NEW_VALUE_WIDGET_WIDTH + 1, justify=tk.RIGHT)
            self._update_entry_text(new_value_widget)

        # Set up the widget based on forced/derived status
        if self.param.is_forced or self.param.is_derived:
            new_value_widget.config(state="disabled", background="light grey")
            new_value_widget.bind("<Button-1>", self._show_parameter_error)
            new_value_widget.bind("<Button-3>", self._show_parameter_error)
        elif self.param.is_bitmask:
            new_value_widget.bind(
                "<Double-Button>",
                self._open_bitmask_selection,
            )
            new_value_widget.bind(
                "<FocusOut>",
                self._on_value_change,
            )
        else:
            new_value_widget.bind(
                "<FocusOut>",
                self._on_value_change,
            )

        if self.param.doc_tooltip:
            show_tooltip(new_value_widget, self.param.doc_tooltip)

        return new_value_widget

    def _create_unit_label(self) -> ttk.Label:
        """Create the unit label for this parameter."""
        unit_label = ttk.Label(self.table.view_port, text=self.param.unit)
        if self.param.unit_tooltip:
            show_tooltip(unit_label, self.param.unit_tooltip)
        return unit_label

    def _create_upload_checkbutton(self) -> ttk.Checkbutton:
        """Create the upload checkbutton for this parameter."""
        upload_checkbutton = ttk.Checkbutton(self.table.view_port, variable=self.upload_var)
        upload_checkbutton.configure(state="normal" if self.param.has_fc_value else "disabled")
        msg = _("When selected upload {param_name} new value to the flight controller")
        show_tooltip(upload_checkbutton, msg.format(param_name=self.param.name))

        # Store the variable in the table's collection for later retrieval
        self.table.upload_checkbutton_var[self.param.name] = self.upload_var

        return upload_checkbutton

    def _create_change_reason_entry(self) -> ttk.Entry:
        """Create the change reason entry for this parameter."""
        change_reason_entry = ttk.Entry(self.table.view_port, background="white")
        change_reason_entry.insert(0, "" if self.param.comment is None else self.param.comment)

        if self.param.is_forced or self.param.is_derived:
            change_reason_entry.config(state="disabled", background="light grey")
        else:
            change_reason_entry.bind(
                "<FocusOut>",
                self._on_change_reason_change,
            )

        value_text = self.new_value_widget.get() if self.new_value_widget else self.param.value_as_string
        msg = _("Reason why {param_name} should change to {value_text}")
        show_tooltip(change_reason_entry, msg.format(param_name=self.param.name, value_text=value_text))

        return change_reason_entry

    def _update_entry_text(self, entry_widget: ttk.Entry) -> None:
        """Update the text in an entry widget with the parameter value."""
        if isinstance(entry_widget, PairTupleCombobox):
            return
        entry_widget.delete(0, tk.END)
        entry_widget.insert(0, self.param.value_as_string)
        if self.param.has_default_value:
            entry_widget.configure(style="default_v.TEntry")
        else:
            entry_widget.configure(style="TEntry")

    def _on_delete_click(self) -> None:
        """Handle the delete button click event."""
        self.on_delete_callback(self.param.name)

    def _on_combobox_selected(self, event: tk.Event) -> None:
        """Handle the combobox selection event."""
        try:
            combobox_widget = self.new_value_widget
            if not isinstance(combobox_widget, PairTupleCombobox):
                return

            current_value = float(combobox_widget.get_selected_key())
            has_default_value = self.param.default_value is not None and is_within_tolerance(
                current_value, self.param.default_value
            )
            combobox_widget.configure(style="default_v.TCombobox" if has_default_value else "readonly.TCombobox")
            event.width = NEW_VALUE_WIDGET_WIDTH
            combobox_widget.on_combo_configure(event)

            # Update the parameter value via callback
            if not is_within_tolerance(self.param.value, current_value):
                self.on_value_changed_callback(self.param.name, current_value)

            # Update the UI
            self.param.value = current_value
        except ValueError:
            msg = _("Could not solve the selected {combobox_widget} key to a float value.")
            logging_info(msg.format(combobox_widget=combobox_widget))

    def _on_value_change(self, event: tk.Event) -> None:
        """Handle the value change event."""
        # Get the new value from the Entry widget
        widget = event.widget
        new_value_str = widget.get_selected_key() if isinstance(widget, PairTupleCombobox) else widget.get()

        valid: bool = True
        changed: bool = False
        p: float = nan

        # Check if the input is a valid float
        try:
            p = float(new_value_str)  # type: ignore[arg-type]
            changed = not is_within_tolerance(self.param.value, p)

            if changed:
                # Update through callback - validation will be handled in the model
                self.on_value_changed_callback(self.param.name, p)
                # Update our local reference for UI consistency
                self.param.value = p
        except ValueError:
            # Handle invalid value
            error_msg = _("The value for {param_name} must be a valid float.")
            messagebox.showerror(_("Invalid Value"), error_msg.format(param_name=self.param.name))
            valid = False

        if not valid:
            # Revert to the previous valid value in UI
            if not isinstance(widget, PairTupleCombobox):
                widget.delete(0, tk.END)
                widget.insert(0, self.param.value_as_string)

    def _on_change_reason_change(self, event: tk.Event) -> None:
        """Handle the change reason entry change event."""
        new_comment = event.widget.get()
        current_comment = self.param.comment or ""

        # Check if the comment has actually changed
        if new_comment != current_comment and not (new_comment == "" and current_comment is None):
            # Update through callback
            self.on_comment_changed_callback(self.param.name, new_comment)
            # Update our local reference for UI consistency
            self.param.comment = new_comment

    def _show_parameter_error(self, _event: tk.Event) -> None:
        """Show an error message when a forced or derived parameter is clicked."""
        forced_error_msg = _(
            "This parameter already has the correct value for this configuration step.\n"
            "You must not change it, as this would defeat the purpose of this configuration step.\n\n"
            "Add it to other configuration step and change it there if you have a good reason to."
        )
        derived_error_msg = _(
            "This parameter value has been derived from information you entered in the component editor window.\n"
            "You need to change the information on that window to update the value here.\n"
        )

        if self.param.is_forced:
            messagebox.showerror(_("Forced Parameter"), forced_error_msg)
        elif self.param.is_derived:
            messagebox.showerror(_("Derived Parameter"), derived_error_msg)

    def _open_bitmask_selection(self, event: tk.Event) -> None:
        """Open the bitmask selection window."""
        handler = BitmaskWindowHandler(
            self.table.view_port, self.param.name, self.param.bitmask_dict, self.param.value, self._apply_bitmask_selection
        )
        x = event.widget.winfo_rootx() + 50
        y = event.widget.winfo_rooty() + 50
        handler.show_window(x, y)

    def _apply_bitmask_selection(self, new_value: float) -> None:
        """Apply the bitmask selection and update the parameter value."""
        old_value = self.param.value
        if not is_within_tolerance(old_value, new_value):
            # Update through callback
            self.on_value_changed_callback(self.param.name, new_value)

            # Update our local reference for UI
            self.param.value = new_value

            # Update the entry widget if it's an Entry
            if isinstance(self.new_value_widget, ttk.Entry):
                self._update_entry_text(self.new_value_widget)

            logging_debug(_("Parameter %s changed from %f to %f via bitmask selection"), self.param.name, old_value, new_value)

    def update_parameter_display(self, parameter: ArduPilotParameter) -> None:
        """
        Update the UI to reflect changes in the parameter.

        Args:
            parameter: The updated parameter object

        """
        # Update our reference
        self.param = parameter

        # Update the entry widget
        if isinstance(self.new_value_widget, ttk.Entry):
            self._update_entry_text(self.new_value_widget)
        elif isinstance(self.new_value_widget, PairTupleCombobox):
            selected_value = parameter.get_selected_value_from_dict()
            self.new_value_widget.set(selected_value)

        # Update the comment field
        if self.change_reason_entry:
            self.change_reason_entry.delete(0, tk.END)
            self.change_reason_entry.insert(0, "" if parameter.comment is None else parameter.comment)

    def on_value_change(self, event: tk.Event) -> None:
        """
        Handle the value change event.

        This is a public method that can be called from outside the class.

        Args:
            event: The focus out event

        """
        self._on_value_change(event)

    def on_change_reason_change(self, event: tk.Event) -> None:
        """
        Handle the change reason entry change event.

        This is a public method that can be called from outside the class.

        Args:
            event: The focus out event

        """
        self._on_change_reason_change(event)
