"""
Parameter editor table GUI using the "Ardupilot Parameter data model".

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import tkinter as tk
from dataclasses import dataclass
from logging import critical as logging_critical
from logging import debug as logging_debug
from logging import exception as logging_exception
from logging import info as logging_info
from platform import system as platform_system
from sys import exit as sys_exit
from sys import platform as sys_platform
from tkinter import ttk
from typing import TYPE_CHECKING, Callable, Optional, Union

from ardupilot_methodic_configurator import _
from ardupilot_methodic_configurator.data_model_ardupilot_parameter import ArduPilotParameter, BitmaskHelper
from ardupilot_methodic_configurator.data_model_par_dict import ParDict
from ardupilot_methodic_configurator.data_model_parameter_editor import (
    InvalidParameterNameError,
    OperationNotPossibleError,
    ParameterEditor,
    ParameterValueUpdateResult,
    ParameterValueUpdateStatus,
)
from ardupilot_methodic_configurator.frontend_tkinter_base_window import (
    BaseWindow,
    ask_yesno_popup,
    show_error_popup,
    show_info_popup,
    show_warning_popup,
)
from ardupilot_methodic_configurator.frontend_tkinter_pair_tuple_combobox import (
    PairTupleCombobox,
    setup_combobox_mousewheel_handling,
)
from ardupilot_methodic_configurator.frontend_tkinter_rich_text import get_widget_font_family_and_size
from ardupilot_methodic_configurator.frontend_tkinter_scroll_frame import ScrollFrame
from ardupilot_methodic_configurator.frontend_tkinter_show import show_tooltip
from ardupilot_methodic_configurator.frontend_tkinter_usage_popup_window import UsagePopupWindow
from ardupilot_methodic_configurator.frontend_tkinter_usage_popup_windows import (  # pylint: disable=cyclic-import
    display_bitmask_parameters_editor_usage_popup,
)

if TYPE_CHECKING:  # pragma: no cover - import for type checking only
    from ardupilot_methodic_configurator.frontend_tkinter_parameter_editor import ParameterEditorWindow

NEW_VALUE_WIDGET_WIDTH = 9
NEW_VALUE_DIFFERENT_STR = "\u2260" if platform_system() == "Windows" else "!="

# pylint: disable=too-many-lines


@dataclass
class ParameterEditorTableDialogs:
    """Bundle of dialog callbacks so tests can stub them easily."""

    show_error: Callable[[str, str], None] = show_error_popup
    show_info: Callable[[str, str], None] = show_info_popup
    ask_yes_no: Callable[[str, str], bool] = ask_yesno_popup


class ParameterEditorTable(ScrollFrame):  # pylint: disable=too-many-ancestors
    """
    A class to manage and display the parameter editor table within the GUI.

    This class inherits from ScrollFrame and is responsible for creating,
    managing, and updating the table that displays parameters for editing.
    It uses the ArduPilotParameter domain model to handle parameter operations.
    """

    def __init__(
        self,
        master: tk.Misc,
        parameter_editor: ParameterEditor,
        parameter_editor_window: "ParameterEditorWindow",
        dialogs: Optional[ParameterEditorTableDialogs] = None,
    ) -> None:
        super().__init__(master)
        self.main_frame = master
        self.parameter_editor = parameter_editor
        self.parameter_editor_window = parameter_editor_window  # the parent window that contains this table
        self.upload_checkbutton_var: dict[str, tk.BooleanVar] = {}
        self._dialogs = dialogs or ParameterEditorTableDialogs()

        # Track last return values to prevent duplicate event processing
        self._last_return_values: dict[tk.Misc, str] = {}
        self._pending_scroll_to_bottom = False

        style = ttk.Style()
        style.configure("narrow.TButton", padding=0, width=4, border=(0, 0, 0, 0))

    def _get_parent_root(self) -> Optional[tk.Tk]:
        """Return the closest tk.Tk ancestor if available."""
        widget: Optional[tk.Misc] = self.main_frame
        while widget is not None and not isinstance(widget, tk.Tk):
            widget = widget.master
        return widget if isinstance(widget, tk.Tk) else None

    def _get_parent_toplevel(self) -> Union[tk.Tk, tk.Toplevel]:
        """Return the closest Tk or Toplevel ancestor for centering dialogs."""
        widget: Optional[tk.Misc] = self.main_frame
        while widget is not None and not isinstance(widget, (tk.Tk, tk.Toplevel)):
            widget = widget.master
        if isinstance(widget, (tk.Tk, tk.Toplevel)):
            return widget
        ancestor = self.main_frame.winfo_toplevel()
        if isinstance(ancestor, (tk.Tk, tk.Toplevel)):
            return ancestor
        msg = "Could not resolve parent toplevel window"
        raise RuntimeError(msg)

    def _should_show_upload_column(self, gui_complexity: Union[str, None] = None) -> bool:
        """
        Determine if the upload column should be shown based on UI complexity.

        Args:
            gui_complexity: UI complexity level. If None, uses self.parameter_editor.gui_complexity

        Returns:
            True if upload column should be shown, False otherwise

        """
        if gui_complexity is None:
            gui_complexity = self.parameter_editor_window.gui_complexity
        return gui_complexity != "simple"

    def _create_headers_and_tooltips(self, show_upload_column: bool) -> tuple[tuple[str, ...], tuple[str, ...]]:
        """Create table headers and tooltips dynamically based on UI complexity."""
        base_headers = [
            _("-/+"),
            _("Parameter"),
            _("Current Value"),
            NEW_VALUE_DIFFERENT_STR,
            _("New Value"),
            _("Unit"),
        ]

        base_tooltips = [
            _("Delete or add a parameter"),
            _("Parameter name must be ^[A-Z][A-Z_0-9]* and most 16 characters long"),
            _("Current value on the flight controller"),
            _("Is the new value different from the current FC value?"),
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

        base_headers.append(_("Why are you changing this parameter?"))
        base_tooltips.append(change_reason_tooltip)

        return tuple(base_headers), tuple(base_tooltips)

    def repopulate_table(self, show_only_differences: bool, gui_complexity: str) -> None:
        for widget in self.view_port.winfo_children():
            widget.destroy()
        # Clear the last return values tracking dictionary when repopulating
        self._last_return_values.clear()
        scroll_to_bottom = self._pending_scroll_to_bottom
        self._pending_scroll_to_bottom = False

        # Check if upload column should be shown based on UI complexity
        show_upload_column = self._should_show_upload_column(gui_complexity)

        # Create labels for table headers
        headers, tooltips = self._create_headers_and_tooltips(show_upload_column)

        for i, header in enumerate(headers):
            label = ttk.Label(self.view_port, text=header)
            label.grid(row=0, column=i, sticky="ew")  # Use sticky="ew" to make the label stretch horizontally
            show_tooltip(label, tooltips[i])

        self.upload_checkbutton_var = {}

        if show_only_differences:
            # Filter to show only different parameters
            different_params = self.parameter_editor.get_different_parameters()
            self._update_table(different_params, self.parameter_editor_window.gui_complexity)
            if not different_params:
                info_msg = _("No different parameters found in {selected_file}. Skipping...").format(
                    selected_file=self.parameter_editor.current_file
                )
                logging_info(info_msg)
                self._dialogs.show_info(_("ArduPilot methodic configurator"), info_msg)
                self.parameter_editor_window.on_skip_click()
                return
        else:
            self._update_table(self.parameter_editor.current_step_parameters, self.parameter_editor_window.gui_complexity)
        self._apply_scroll_position(scroll_to_bottom)

    def _apply_scroll_position(self, scroll_to_bottom: bool) -> None:
        """Apply the requested scroll position to the canvas."""
        self.update_idletasks()
        position = 1.0 if scroll_to_bottom else 0.0
        self.canvas.yview_moveto(position)

    def _update_table(self, params: dict[str, ArduPilotParameter], gui_complexity: str) -> None:
        """Update the parameter table with the given parameters."""
        current_param_name: str = ""
        show_upload_column = self._should_show_upload_column(gui_complexity)

        should_try_to_display_bitmask_parameter_editor_usage = False
        try:
            for i, (param_name, param) in enumerate(params.items(), 1):
                current_param_name = param_name

                row_widgets: list[tk.Widget] = self._create_column_widgets(param_name, param, show_upload_column)
                if self.parameter_editor.should_display_bitmask_parameter_editor_usage(param_name):
                    should_try_to_display_bitmask_parameter_editor_usage = True
                self._grid_column_widgets(row_widgets, i, show_upload_column)

            # Add the "Add" button at the bottom of the table
            add_button = ttk.Button(self.view_port, text=_("Add"), style="narrow.TButton", command=self._on_parameter_add)
            tooltip_msg = _("Add a parameter to the {self.parameter_editor.current_file} file")
            show_tooltip(add_button, tooltip_msg.format(**locals()))
            add_button.grid(row=len(params) + 2, column=0, sticky="w", padx=0)

        except KeyError as e:
            logging_critical(
                _("Parameter %s not found in the %s file: %s"),
                current_param_name,
                self.parameter_editor.current_file,
                e,
                exc_info=True,
            )
            sys_exit(1)

        self._configure_table_columns(show_upload_column)
        parent_root = self._get_parent_root()
        if (
            parent_root
            and should_try_to_display_bitmask_parameter_editor_usage
            and UsagePopupWindow.should_display("bitmask_parameter_editor")
        ):
            display_bitmask_parameters_editor_usage_popup(parent_root)

    def _create_column_widgets(self, param_name: str, param: ArduPilotParameter, show_upload_column: bool) -> list[tk.Widget]:
        """Create all column widgets for a parameter row."""
        row_widgets: list[tk.Widget] = []
        change_reason_widget = self._create_change_reason_entry(param)
        value_is_different_label = self._create_value_different_label(param)
        row_widgets.append(self._create_delete_button(param_name))
        row_widgets.append(self._create_parameter_name(param))
        row_widgets.append(self._create_flightcontroller_value(param))
        row_widgets.append(value_is_different_label)
        # update the change reason tooltip when the new value changes
        row_widgets.append(self._create_new_value_entry(param, change_reason_widget, value_is_different_label))
        row_widgets.append(self._create_unit_label(param))

        if show_upload_column:
            row_widgets.append(self._create_upload_checkbutton(param_name))

        row_widgets.append(change_reason_widget)

        return row_widgets

    def _grid_column_widgets(self, row_widgets: list[tk.Widget], row: int, show_upload_column: bool) -> None:
        """Grid all column widgets for a parameter row."""
        row_widgets[0].grid(row=row, column=0, sticky="w", padx=0)
        row_widgets[1].grid(row=row, column=1, sticky="w", padx=0)
        row_widgets[2].grid(row=row, column=2, sticky="e", padx=0)
        row_widgets[3].grid(row=row, column=3, sticky="e", padx=0)
        row_widgets[4].grid(row=row, column=4, sticky="e", padx=0)
        row_widgets[5].grid(row=row, column=5, sticky="e", padx=0)

        if show_upload_column:
            row_widgets[6].grid(row=row, column=6, sticky="e", padx=0)

        change_reason_column = self._get_change_reason_column_index(show_upload_column)
        row_widgets[change_reason_column].grid(row=row, column=change_reason_column, sticky="ew", padx=(0, 5))

    def _get_change_reason_column_index(self, show_upload_column: bool) -> int:
        """
        Get the column index for the change reason entry.

        Args:
            show_upload_column: Whether the upload column is shown

        Returns:
            Column index for change reason entry

        """
        # Base columns: Delete, Parameter, Current Value, New Value, Unit
        base_column_count = 6
        if show_upload_column:
            return base_column_count + 1  # Upload column + Change Reason
        return base_column_count  # Change Reason directly after Unit

    def _configure_table_columns(self, show_upload_column: bool) -> None:
        """Configure table column weights and sizes."""
        self.view_port.columnconfigure(0, weight=0)  # Delete and Add buttons
        self.view_port.columnconfigure(1, weight=0, minsize=120)  # Parameter name
        self.view_port.columnconfigure(2, weight=0)  # Current Value
        self.view_port.columnconfigure(3, weight=0)  # Different
        self.view_port.columnconfigure(4, weight=0)  # New Value
        self.view_port.columnconfigure(5, weight=0)  # Units

        if show_upload_column:
            self.view_port.columnconfigure(6, weight=0)  # Upload to FC

        self.view_port.columnconfigure(self._get_change_reason_column_index(show_upload_column), weight=1)  # Change Reason

    def _create_delete_button(self, param_name: str) -> ttk.Button:
        """Create a delete button for a parameter."""
        delete_button = ttk.Button(
            self.view_port, text=_("Del"), style="narrow.TButton", command=lambda: self._on_parameter_delete(param_name)
        )
        tooltip_msg = _("Delete {param_name} from the {self.parameter_editor.current_file} file")
        show_tooltip(delete_button, tooltip_msg.format(**locals()))
        return delete_button

    def _create_parameter_name(self, param: ArduPilotParameter) -> ttk.Label:
        """Create a label displaying the parameter name."""
        parameter_label = ttk.Label(
            self.view_port,
            text=param.name + (" " * (16 - len(param.name))),
            background="purple1"
            if param.is_readonly
            else "yellow"
            if param.is_calibration
            else ttk.Style(self.main_frame).lookup("TFrame", "background"),
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
            elif param.fc_value_is_above_limit() or param.fc_value_has_unknown_bits_set():
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

    def _create_value_different_label(self, param: ArduPilotParameter) -> ttk.Label:
        """Create a label indicating if the new value is different from current FC value."""
        return ttk.Label(self.view_port, text=NEW_VALUE_DIFFERENT_STR if param.is_different_from_fc else " ")

    def _handle_parameter_value_update(
        self, param: ArduPilotParameter, new_value: str, include_range_check: bool = True
    ) -> bool:
        """Delegate parameter updates to the presenter and translate the result for the UI."""
        result = self.parameter_editor.update_parameter_value(
            param.name,
            new_value,
            include_range_check=include_range_check,
        )
        return self._handle_parameter_value_update_result(result, param, new_value)

    def _handle_parameter_value_update_result(
        self, result: ParameterValueUpdateResult, param: ArduPilotParameter, new_value: str
    ) -> bool:
        """Convert presenter update results into concrete UI actions."""
        if result.status is ParameterValueUpdateStatus.UPDATED:
            return True
        if result.status is ParameterValueUpdateStatus.UNCHANGED:
            return False
        if result.status is ParameterValueUpdateStatus.ERROR:
            self._dialogs.show_error(result.title or _("Error"), result.message or _("Unknown error."))
            return False
        if result.status is ParameterValueUpdateStatus.CONFIRM_OUT_OF_RANGE:
            prompt = (result.message or "") + _(" Use out-of-range value?")
            if self._dialogs.ask_yes_no(result.title or _("Out-of-range value"), prompt):
                forced_result = self.parameter_editor.update_parameter_value(
                    param.name,
                    new_value,
                    include_range_check=False,
                )
                return self._handle_parameter_value_update_result(forced_result, param, new_value)
            return False
        return False

    def _update_combobox_style_on_selection(  # pylint: disable=too-many-arguments, too-many-positional-arguments
        self,
        combobox_widget: PairTupleCombobox,
        param: ArduPilotParameter,
        event: tk.Event,
        change_reason_widget: ttk.Entry,
        value_is_different_label: ttk.Label,
    ) -> None:
        """Update the combobox style based on selection."""
        new_value_str = combobox_widget.get_selected_key() or ""

        # Use centralized error handling for parameter value updates
        if self._handle_parameter_value_update(param, new_value_str, include_range_check=False):
            # Success: mark edited and sync the ArduPilotParameter back to filesystem
            show_tooltip(change_reason_widget, param.tooltip_change_reason)
            value_is_different_label.config(text=NEW_VALUE_DIFFERENT_STR if param.is_different_from_fc else " ")

        combobox_widget.configure(
            style="default_v.TCombobox" if param.new_value_equals_default_value else "readonly.TCombobox"
        )
        event.width = NEW_VALUE_WIDGET_WIDTH
        combobox_widget.on_combo_configure(event)

    @staticmethod
    def _update_new_value_entry_text(new_value_entry: ttk.Entry, param: ArduPilotParameter) -> None:
        """Update the new value entry text and style."""
        if isinstance(new_value_entry, PairTupleCombobox):
            # Only ttk.Entry widgets support style configuration
            return
        new_value_entry.delete(0, tk.END)
        new_value_entry.insert(0, param.value_as_string)
        if param.new_value_equals_default_value:
            style = "default_v.TEntry"
        elif param.is_below_limit():
            style = "below_limit.TEntry"
        elif param.is_above_limit() or param.has_unknown_bits_set():
            style = "above_limit.TEntry"
        else:
            style = "TEntry"
        new_value_entry.configure(style=style)

    def _create_new_value_entry(  # pylint: disable=too-many-statements # noqa: PLR0915
        self, param: ArduPilotParameter, change_reason_widget: ttk.Entry, value_is_different_label: ttk.Label
    ) -> Union[PairTupleCombobox, ttk.Entry]:
        """Create an entry widget for editing the parameter value."""
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
            font_size -= 2 if platform_system() == "Windows" else -1
            new_value_entry.config(state="readonly", width=NEW_VALUE_WIDGET_WIDTH, font=(font_family, font_size))
            new_value_entry.bind(  # type: ignore[call-overload] # workaround a mypy issue
                "<<ComboboxSelected>>",
                lambda event: self._update_combobox_style_on_selection(
                    new_value_entry, param, event, change_reason_widget, value_is_different_label
                ),
                "+",
            )

            # Set up mouse wheel handling to prevent unwanted value changes
            setup_combobox_mousewheel_handling(new_value_entry)
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
                self._dialogs.show_error(_("Forced Parameter"), forced_error_msg)
            elif param.is_derived:
                self._dialogs.show_error(_("Derived Parameter"), derived_error_msg)

        def _on_parameter_value_change(event: tk.Event) -> None:
            """Handle changes to parameter values."""
            # Get the new value string from the Entry widget (always treat as string)
            new_value = (
                event.widget.get_selected_key()
                if isinstance(event.widget, PairTupleCombobox)
                else event.widget.get()
                if isinstance(event.widget, (ttk.Entry, tk.Entry))
                else None
            )

            # If we couldn't extract a string, abort early
            if new_value is None:
                return

            # Prevent duplicate execution when both Return and FocusOut events are triggered
            # EventType.KeyPress for Return/Enter, EventType.FocusOut for focus loss
            if (
                hasattr(event, "type")
                and event.type == tk.EventType.FocusOut
                and event.widget in self._last_return_values
                # Check if the widget still has the same value as when Return was pressed
                # If Return was just pressed, skip FocusOut to avoid duplicate processing
                and new_value == self._last_return_values[event.widget]
            ):
                # Clear the flag and skip processing
                del self._last_return_values[event.widget]
                return

            # Mark that Return was pressed with this value (for FocusOut deduplication)
            if hasattr(event, "type") and event.type == tk.EventType.KeyPress:  # KeyPress event (Return/Enter)
                self._last_return_values[event.widget] = new_value

            # Use centralized error handling for parameter value updates
            valid = self._handle_parameter_value_update(param, new_value, include_range_check=True)

            if valid:
                logging_debug(_("Parameter %s changed, will later ask if change(s) should be saved to file."), param.name)
                show_tooltip(change_reason_widget, param.tooltip_change_reason)
                value_is_different_label.config(text=NEW_VALUE_DIFFERENT_STR if param.is_different_from_fc else " ")

            # Update the displayed value in the Entry or Combobox
            if isinstance(
                event.widget, (ttk.Entry, tk.Entry)
            ):  # it is a ttk.Entry. The tk.Entry check is just defensive programming
                self._update_new_value_entry_text(event.widget, param)  # type: ignore[arg-type] # workaround a mypy bug
            elif isinstance(event.widget, PairTupleCombobox):
                # For PairTupleCombobox, update the style based on whether it matches default value
                self._update_combobox_style_on_selection(
                    event.widget,
                    param,
                    event,
                    change_reason_widget,
                    value_is_different_label,
                )

        if not param.is_editable:
            new_value_entry.config(state="disabled", background="light grey")
            new_value_entry.bind("<Button-1>", show_parameter_error)
            # Also bind to right-click for completeness
            new_value_entry.bind("<Button-3>", show_parameter_error)
        elif param.is_bitmask:
            new_value_entry.bind(
                "<Double-Button-1>",
                lambda event: self._open_bitmask_selection_window(
                    event,
                    param,
                    change_reason_widget,
                    value_is_different_label,
                ),
            )
            new_value_entry.bind("<FocusOut>", _on_parameter_value_change)
            new_value_entry.bind("<Return>", _on_parameter_value_change)
            new_value_entry.bind("<KP_Enter>", _on_parameter_value_change)
        else:
            new_value_entry.bind("<FocusOut>", _on_parameter_value_change)
            new_value_entry.bind("<Return>", _on_parameter_value_change)
            new_value_entry.bind("<KP_Enter>", _on_parameter_value_change)

        tooltip_new_value = param.tooltip_new_value
        if tooltip_new_value:
            show_tooltip(new_value_entry, tooltip_new_value)

        # Expose handlers for tests so they can be triggered without tkinter events
        new_value_entry.testing_on_parameter_value_change = _on_parameter_value_change  # type: ignore[attr-defined]
        new_value_entry.testing_show_parameter_error = show_parameter_error  # type: ignore[attr-defined]
        return new_value_entry

    def _open_bitmask_selection_window(  # pylint: disable=too-many-locals, too-many-statements # noqa: PLR0915
        self,
        event: tk.Event,
        param: ArduPilotParameter,
        change_reason_widget: ttk.Entry,
        value_is_different_label: ttk.Label,
    ) -> None:
        """Open a window to select bitmask options."""

        def on_close() -> None:
            try:
                checked_keys = {int(key) for key, var in checkbox_vars.items() if var.get()}
            except (ValueError, TypeError) as e:
                logging_exception(_("Error getting {param_name} checked keys: %s").format(param_name=param.name), e)
                self._dialogs.show_error(
                    _("Error"), _("Could not get {param_name} checked keys. Please try again.").format(param_name=param.name)
                )
                return

            # Use centralized error handling for parameter value updates
            bitmask_value = BitmaskHelper.get_value_from_keys(checked_keys)
            valid = self._handle_parameter_value_update(param, str(bitmask_value), include_range_check=True)

            if valid:
                show_tooltip(change_reason_widget, param.tooltip_change_reason)
                value_is_different_label.config(text=NEW_VALUE_DIFFERENT_STR if param.is_different_from_fc else " ")

            # Update new_value_entry with the new decimal value
            # For bitmask windows, event.widget should always be ttk.Entry (not PairTupleCombobox)
            # since bitmasks are only created for Entry widgets, not Comboboxes
            if isinstance(event.widget, ttk.Entry):
                self._update_new_value_entry_text(event.widget, param)

            # Release the modal grab and destroy the window
            if sys_platform != "darwin":
                window.grab_release()
            window.destroy()
            # Issue a FocusIn event on something else than new_value_entry to prevent endless looping
            self.main_frame.focus_set()
            # Run the Tk event loop once to process the event
            self.main_frame.update_idletasks()
            # Re-bind the FocusIn event to new_value_entry
            event.widget.bind(
                "<Double-Button-1>",
                lambda event: self._open_bitmask_selection_window(
                    event,
                    param,
                    change_reason_widget,
                    value_is_different_label,
                ),
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
        event.widget.unbind("<Double-Button-1>")
        window = tk.Toplevel(self.main_frame.master)
        window.withdraw()  # Hide the window until it's fully set up
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
            self._dialogs.show_error(
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

        # Make sure the window is visible and properly positioned
        window.transient(self._get_parent_toplevel())
        window.deiconify()

        self._center_and_focus_window(window)

        window.wait_window()  # Wait for the window to be closed

    def _create_unit_label(self, param: ArduPilotParameter) -> ttk.Label:
        """Create a label displaying the parameter unit."""
        unit_label = ttk.Label(self.view_port, text=param.unit)
        unit_tooltip = param.tooltip_unit
        if unit_tooltip:
            show_tooltip(unit_label, unit_tooltip)
        return unit_label

    def _create_upload_checkbutton(self, param_name: str) -> ttk.Checkbutton:
        """Create a checkbutton for upload selection."""
        fc_connected: bool = self.parameter_editor.is_fc_connected
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

            def _on_change_reason_change(event: tk.Event) -> None:
                new_comment = change_reason_entry.get()

                # Prevent duplicate execution when both Return and FocusOut events are triggered
                if (
                    hasattr(event, "type")
                    and event.type == tk.EventType.FocusOut
                    and change_reason_entry in self._last_return_values
                    and new_comment == self._last_return_values[change_reason_entry]
                ):
                    # Clear the flag and skip processing
                    del self._last_return_values[change_reason_entry]
                    return

                # Mark that Return was pressed with this value (for FocusOut deduplication)
                if hasattr(event, "type") and event.type == tk.EventType.KeyPress:  # KeyPress event (Return/Enter)
                    self._last_return_values[change_reason_entry] = new_comment

                # Only set the flag and update file if the comment actually changes
                if param.set_change_reason(new_comment):
                    logging_debug(
                        _("Parameter %s change reason changed from %s to %s, will later ask if should be saved to file."),
                        param.name,
                        param.change_reason,
                        new_comment,
                    )

            change_reason_entry.bind("<FocusOut>", _on_change_reason_change)
            change_reason_entry.bind("<Return>", _on_change_reason_change)
            change_reason_entry.bind("<KP_Enter>", _on_change_reason_change)

        show_tooltip(change_reason_entry, param.tooltip_change_reason)

        # Expose handler for tests to call without user events
        if param.is_editable:
            change_reason_entry.testing_on_change_reason_change = _on_change_reason_change  # type: ignore[attr-defined]
        return change_reason_entry

    def _on_parameter_delete(self, param_name: str) -> None:
        """Handle parameter deletion."""
        msg = _("Are you sure you want to delete the {param_name} parameter?")
        if self._dialogs.ask_yes_no(f"{self.parameter_editor.current_file}", msg.format(**locals())):
            # Capture current vertical scroll position
            current_scroll_position = self.canvas.yview()[0]

            # Delete the parameter
            self.parameter_editor.delete_parameter_from_current_file(param_name)
            self.parameter_editor_window.repopulate_parameter_table()

            # Restore the scroll position
            self.canvas.yview_moveto(current_scroll_position)

    def _create_parameter_add_dialog_widgets(
        self,
        window: BaseWindow,
    ) -> tuple[tk.StringVar, ttk.Entry, tk.Listbox, ttk.Button]:
        """Create and configure all widgets for the parameter add dialog."""
        ttk.Label(window.main_frame, text=_("Name filter:")).pack(pady=(5, 0))

        search_var: tk.StringVar = tk.StringVar()
        search_entry: ttk.Entry = ttk.Entry(window.main_frame, textvariable=search_var)
        search_entry.pack(fill="x", padx=10)
        show_tooltip(
            search_entry,
            _(
                "Type part of a parameter name to filter the list.\n"
                "Press Enter to add all filtered parameters,\n"
                "or only the selected ones if any are selected."
            ),
        )

        ttk.Label(window.main_frame, text=_("(Use Ctrl/Shift for multiple selection)"), font=("TkDefaultFont", 8)).pack(
            pady=(5, 0)
        )
        frame = ttk.Frame(window.main_frame)
        frame.pack(fill="both", expand=True, padx=10, pady=5)

        listbox: tk.Listbox = tk.Listbox(frame, selectmode=tk.EXTENDED)
        listbox.pack(side="left", fill="both", expand=True)

        scrollbar = ttk.Scrollbar(frame, orient="vertical", command=listbox.yview)
        scrollbar.pack(side="right", fill="y")
        listbox.configure(yscrollcommand=scrollbar.set)
        show_tooltip(
            listbox,
            _(
                "Double-click to add single parameter\n"
                "Ctrl+click to select multiple one-by-one\n"
                "Shift+click to select multiple by range\n"
                "Ctrl+A: Select all\n"
                "Ctrl+D: Deselect all\n"
                "Return: Add selected"
            ),
        )

        add_button: ttk.Button = ttk.Button(window.main_frame, text=_("No parameter selected"), state="disabled")
        add_button.pack(pady=10)

        return search_var, search_entry, listbox, add_button

    def _bulk_add_parameters_and_show_feedback(self, param_names: list[str], dialog_window: BaseWindow) -> None:
        """
        Execute bulk parameter addition and display feedback to user.

        Args:
            param_names: List of parameter names to add (should be uppercase)
            dialog_window: The add parameter dialog window to close after operation

        Side Effects:
            - Adds parameters to the current configuration file
            - Updates the parameter editor table display
            - Scrolls to bottom if parameters were added
            - Displays feedback popup based on operation results
            - Closes the dialog window

        Note:
            This method orchestrates the UI workflow. The business logic is in
            ParameterEditor.bulk_add_parameters() and message generation is in
            ParameterEditor.generate_bulk_add_feedback_message() for better testability.

        """
        # Call business logic method
        added, skipped, failed = self.parameter_editor.add_parameters_to_current_file(param_names)
        self._show_bulk_add_parameters_feedback(added, skipped, failed)

        # Release the modal grab before destroying the window
        if sys_platform != "darwin":
            dialog_window.root.grab_release()
        dialog_window.root.destroy()

    def _show_bulk_add_parameters_feedback(self, added: list[str], skipped: list[str], failed: list[str]) -> None:
        """
        Show bulk add parameter(s) results/feedback.

        Args:
            added: List of successfully added parameter names
            skipped: List of skipped parameter names (already exist)
            failed: List of failed parameter names (invalid or errors)

        """
        # Update UI if parameters were added
        if added:
            self._pending_scroll_to_bottom = True
            self.parameter_editor_window.repopulate_parameter_table()

        # Generate and show feedback message
        message_type, title, message = self.parameter_editor.generate_bulk_add_feedback_message(added, skipped, failed)

        if message_type == "success":
            pass  # Silent success - no popup needed for clean operation
        elif message_type == "warning":
            show_warning_popup(title, message)
        elif message_type == "info":
            show_info_popup(title, message)
        elif message_type == "error":
            show_error_popup(title, message)

    def _on_parameter_add(self) -> None:
        """Handle parameter addition."""
        add_parameter_window = BaseWindow(self._get_parent_root())
        add_parameter_window.root.title(_("Add parameter(s)"))
        add_parameter_window.root.geometry("250x400")
        add_parameter_window.root.transient(self._get_parent_toplevel())

        all_params = self.parameter_editor.get_possible_add_param_names()
        search_var, search_entry, listbox, add_button = self._create_parameter_add_dialog_widgets(add_parameter_window)

        # Define event handlers as closures with access to widgets
        def update_selection_info() -> None:
            count = len(listbox.curselection())  # type: ignore[no-untyped-call]
            if count == 0:
                add_button.config(text=_("No parameter selected"), state="disabled")
            elif count == 1:
                add_button.config(text=_("Add selected parameter"), state="normal")
            else:
                add_button.config(text=_("Add %d selected parameters") % count, state="normal")

        def refresh_list(*_: object) -> None:
            listbox.delete(0, tk.END)
            query = search_var.get().lower()
            for p in [p for p in all_params if query in p.lower()]:
                listbox.insert(tk.END, p)
            update_selection_info()

        def add_selected() -> None:
            selected = [listbox.get(i).upper() for i in listbox.curselection()]  # type: ignore[no-untyped-call]
            if not selected:
                return
            if len(selected) > ParameterEditor.MAX_BULK_ADD_SUGGESTIONS:
                message = _(
                    "Adding many parameters at once can make it difficult to track changes and may impact GUI performance.\n"
                    "Are you sure you want to add all %d parameters?"
                ) % len(selected)
                if not self._dialogs.ask_yes_no(_("Confirm bulk addition"), message):
                    return
            self._bulk_add_parameters_and_show_feedback(selected, add_parameter_window)

        # pylint: disable=line-too-long
        # Bind events
        search_var.trace_add("write", refresh_list)
        search_entry.bind(
            "<Return>",
            lambda _: (
                listbox.selection_set(0, tk.END) if not listbox.curselection() and listbox.size() > 0 else None,  # type: ignore[func-returns-value, no-untyped-call]
                add_selected(),  # type: ignore[func-returns-value]
            )[1],
        )
        listbox.bind("<<ListboxSelect>>", lambda _: update_selection_info())
        listbox.bind(
            "<Double-Button-1>",
            lambda _: (
                self._bulk_add_parameters_and_show_feedback(
                    [listbox.get(listbox.curselection()[0]).upper()],  # type: ignore[no-untyped-call]
                    add_parameter_window,
                )
                if listbox.curselection()  # type: ignore[no-untyped-call]
                else None
            ),
        )
        listbox.bind("<Return>", lambda _: add_selected())
        listbox.bind("<Control-a>", lambda _: (listbox.selection_set(0, tk.END), update_selection_info(), "break")[2])  # type: ignore[func-returns-value]
        listbox.bind("<Control-A>", lambda _: (listbox.selection_set(0, tk.END), update_selection_info(), "break")[2])  # type: ignore[func-returns-value]
        listbox.bind("<Control-d>", lambda _: (listbox.selection_clear(0, tk.END), update_selection_info(), "break")[2])  # type: ignore[func-returns-value]
        listbox.bind("<Control-D>", lambda _: (listbox.selection_clear(0, tk.END), update_selection_info(), "break")[2])  # type: ignore[func-returns-value]
        # pylint: enable=line-too-long
        add_parameter_window.root.bind("<Return>", lambda _: add_selected())

        def on_escape(_event: tk.Event) -> None:
            """Handle Escape key to close the window."""
            if sys_platform != "darwin":
                add_parameter_window.root.grab_release()
            add_parameter_window.root.destroy()

        add_parameter_window.root.bind("<Escape>", on_escape)
        add_button.config(command=add_selected)

        refresh_list()
        self._center_and_focus_window(add_parameter_window.root)

        # Ensure focus ends up on the search_entry, not just the window
        add_parameter_window.root.after(0, search_entry.focus_set)

    def _center_and_focus_window(self, window: Union[tk.Toplevel, tk.Tk]) -> None:
        BaseWindow.center_window(window, self._get_parent_toplevel())
        window.lift()
        window.update()  # Ensure the window is fully rendered before setting focus

        # On macOS, grab_set() causes UI freeze (issue #1264), so skip it
        if sys_platform != "darwin":
            window.focus_force()
            window.grab_set()

    def _confirm_parameter_addition(self, param_name: str) -> bool:
        """Confirm and process parameter addition using ParameterEditor."""
        try:
            if self.parameter_editor.add_parameter_to_current_file(param_name):
                self._pending_scroll_to_bottom = True
                self.parameter_editor_window.repopulate_parameter_table()

                return True
        except InvalidParameterNameError as exc:
            self._dialogs.show_error(_("Invalid parameter name."), str(exc))
            return False
        except OperationNotPossibleError as exc:
            self._dialogs.show_error(_("Operation not possible"), str(exc))
            return False
        return False

    def get_upload_selected_params(self, gui_complexity: str) -> ParDict:
        """Get the parameters selected for upload."""
        # Check if we should show upload column based on GUI complexity
        if not self._should_show_upload_column(gui_complexity):
            # All parameters are selected for upload in simple mode
            return self.parameter_editor.get_parameters_as_par_dict()

        # Get only selected parameters
        selected_names = [name for name, checkbutton_state in self.upload_checkbutton_var.items() if checkbutton_state.get()]
        return self.parameter_editor.get_parameters_as_par_dict(selected_names)
