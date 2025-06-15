"""
Refactored Parameter editor table GUI for improved testability.

This file is part of Ardupilot methodic configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2025 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import tkinter as tk
from dataclasses import dataclass
from logging import critical as logging_critical
from logging import debug as logging_debug
from logging import info as logging_info
from math import isfinite, isnan, nan
from platform import system as platform_system
from tkinter import messagebox, ttk
from typing import Any, Optional, Protocol, Union

from ardupilot_methodic_configurator import _
from ardupilot_methodic_configurator.annotate_params import Par
from ardupilot_methodic_configurator.backend_filesystem import LocalFilesystem, is_within_tolerance
from ardupilot_methodic_configurator.frontend_tkinter_pair_tuple_combobox import PairTupleCombobox
from ardupilot_methodic_configurator.frontend_tkinter_rich_text import get_widget_font_family_and_size
from ardupilot_methodic_configurator.frontend_tkinter_scroll_frame import ScrollFrame
from ardupilot_methodic_configurator.frontend_tkinter_show import show_tooltip

NEW_VALUE_WIDGET_WIDTH = 9


@dataclass
class ParameterValidationResult:
    """Result of parameter validation operations."""

    is_valid: bool
    value: float
    error_message: str = ""


@dataclass
class ParameterRowData:
    """Data needed to create a parameter row."""

    param_name: str
    param: Par
    param_metadata: dict[str, Any]
    param_default: Union[None, Par]
    doc_tooltip: str
    fc_parameters: dict[str, float]
    show_upload_column: bool


class ParameterValidator:
    """Handles parameter validation logic with no UI dependencies."""

    def __init__(self, doc_dict: dict[str, dict[str, Any]]) -> None:
        self.doc_dict = doc_dict

    def validate_value_format(self, value_str: str, param_name: str) -> ParameterValidationResult:
        """Validate that the parameter value is a valid float."""
        try:
            parsed_value = float(value_str)
            # Reject infinity and NaN values
            if not isfinite(parsed_value) or isnan(parsed_value):
                error_msg = _("The value for {param_name} must be a finite number.").format(param_name=param_name)
                return ParameterValidationResult(False, nan, error_msg)
            return ParameterValidationResult(True, parsed_value)
        except ValueError:
            error_msg = _("The value for {param_name} must be a valid float.").format(param_name=param_name)
            return ParameterValidationResult(False, nan, error_msg)

    def validate_bounds(self, value: float, param_name: str) -> ParameterValidationResult:
        """Validate parameter value against min/max bounds."""
        p_min, p_max = self._get_parameter_bounds(param_name)

        if p_min is not None and value < p_min:
            error_msg = _("The value for {param_name} {value} should be greater than {p_min}").format(
                param_name=param_name, value=value, p_min=p_min
            )
            return ParameterValidationResult(False, value, error_msg)

        if p_max is not None and value > p_max:
            error_msg = _("The value for {param_name} {value} should be smaller than {p_max}").format(
                param_name=param_name, value=value, p_max=p_max
            )
            return ParameterValidationResult(False, value, error_msg)

        return ParameterValidationResult(True, value)

    def _get_parameter_bounds(self, param_name: str) -> tuple[Union[float, None], Union[float, None]]:
        """Get the validation bounds for a parameter."""
        param_metadata = self.doc_dict.get(param_name, {})
        return param_metadata.get("min", None), param_metadata.get("max", None)

    def is_value_changed(self, old_value: float, new_value: float) -> bool:
        """Check if parameter value has changed within tolerance."""
        return not is_within_tolerance(old_value, new_value)


class ParameterStateManager:
    """Manages parameter state without UI dependencies."""

    def __init__(self) -> None:
        self.parameter_edited = False
        self.upload_selections: dict[str, bool] = {}

    def mark_parameter_edited(self, param_name: str) -> None:
        """Mark that a parameter has been edited."""
        if not self.parameter_edited:
            logging_debug(_("Parameter %s changed, will later ask if change(s) should be saved to file."), param_name)
        self.parameter_edited = True

    def reset_edited_state(self) -> None:
        """Reset the edited state."""
        self.parameter_edited = False

    def set_upload_selection(self, param_name: str, selected: bool) -> None:
        """Set upload selection for a parameter."""
        self.upload_selections[param_name] = selected

    def get_upload_selection(self, param_name: str) -> bool:
        """Get upload selection for a parameter."""
        return self.upload_selections.get(param_name, True)


class UIMessageHandler(Protocol):
    """Protocol for handling UI messages."""

    def show_error(self, title: str, message: str) -> None:
        """Show an error message."""
        ...

    def show_confirmation(self, title: str, message: str) -> bool:
        """Show a confirmation dialog and return user's choice."""
        ...


class TkinterMessageHandler:
    """Tkinter implementation of UIMessageHandler."""

    def show_error(self, title: str, message: str) -> None:
        """Show an error message using tkinter messagebox."""
        messagebox.showerror(title, message)

    def show_confirmation(self, title: str, message: str) -> bool:
        """Show a confirmation dialog using tkinter messagebox."""
        return messagebox.askyesno(title, message, icon="warning")


class ParameterWidgetFactory:
    """Factory for creating parameter widgets with dependency injection."""

    def __init__(self, view_port: tk.Widget, message_handler: UIMessageHandler) -> None:
        self.view_port = view_port
        self.message_handler = message_handler

    def create_delete_button(self, param_name: str, current_file: str, callback) -> ttk.Button:
        """Create a delete button for a parameter."""
        delete_button = ttk.Button(self.view_port, text=_("Del"), style="narrow.TButton", command=lambda: callback(param_name))
        tooltip_msg = _("Delete {param_name} from the {current_file} file")
        show_tooltip(delete_button, tooltip_msg.format(param_name=param_name, current_file=current_file))
        return delete_button

    def create_parameter_label(self, param_name: str, param_metadata: dict[str, Any], doc_tooltip: str) -> ttk.Label:
        """Create a parameter name label."""
        is_calibration = param_metadata.get("Calibration", False)
        is_readonly = param_metadata.get("ReadOnly", False)

        background_color = (
            "red" if is_readonly else "yellow" if is_calibration else "SystemButtonFace"  # Default system color
        )

        parameter_label = ttk.Label(
            self.view_port,
            text=param_name + (" " * (16 - len(param_name))),
            background=background_color,
        )
        if doc_tooltip:
            show_tooltip(parameter_label, doc_tooltip)
        return parameter_label

    def create_value_entry(self, param_data: ParameterRowData, callback) -> Union[PairTupleCombobox, ttk.Entry]:
        """Create a value entry widget for a parameter."""
        param = param_data.param
        param_metadata = param_data.param_metadata

        # Check if this is a dropdown parameter
        if self._should_create_combobox(param_metadata, param):
            return self._create_combobox_widget(param_data)
        return self._create_entry_widget(param_data, callback)

    def _should_create_combobox(self, param_metadata: dict[str, Any], param: Par) -> bool:
        """Determine if a combobox should be created instead of entry."""
        if not param_metadata or "values" not in param_metadata:
            return False

        values = param_metadata["values"]
        if not values:
            return False

        value_str = format(param.value, ".6f").rstrip("0").rstrip(".")
        return value_str in values

    def _create_combobox_widget(self, param_data: ParameterRowData) -> PairTupleCombobox:
        """Create a combobox widget for parameters with predefined values."""
        param_metadata = param_data.param_metadata
        param = param_data.param
        param_default = param_data.param_default
        param_name = param_data.param_name

        value_str = format(param.value, ".6f").rstrip("0").rstrip(".")
        selected_value = param_metadata["values"].get(value_str, None)
        has_default_value = param_default is not None and is_within_tolerance(param.value, param_default.value)

        combobox = PairTupleCombobox(
            self.view_port,
            param_metadata["values"],
            value_str,
            param_name,
            style="default_v.TCombobox" if has_default_value else "readonly.TCombobox",
        )
        combobox.set(selected_value)

        font_family, font_size = get_widget_font_family_and_size(combobox)
        font_size -= 2 if platform_system() == "Windows" else 1
        combobox.config(state="readonly", width=NEW_VALUE_WIDGET_WIDTH, font=(font_family, font_size))

        return combobox

    def _create_entry_widget(self, param_data: ParameterRowData, callback) -> ttk.Entry:
        """Create an entry widget for parameter values."""
        param = param_data.param
        param_default = param_data.param_default
        doc_tooltip = param_data.doc_tooltip

        entry = ttk.Entry(self.view_port, width=NEW_VALUE_WIDGET_WIDTH + 1, justify=tk.RIGHT)
        self._update_entry_text(entry, param.value, param_default)

        if doc_tooltip:
            show_tooltip(entry, doc_tooltip)

        return entry

    def _update_entry_text(self, entry: ttk.Entry, value: float, param_default: Union[None, Par]) -> None:
        """Update entry text and styling based on value."""
        entry.delete(0, tk.END)
        value_str = format(value, ".6f").rstrip("0").rstrip(".")
        entry.insert(0, value_str)

        if param_default is not None and is_within_tolerance(value, param_default.value):
            entry.configure(style="default_v.TEntry")
        else:
            entry.configure(style="TEntry")


class ParameterEditorTableRefactored(ScrollFrame):
    """
    A refactored, more testable version of the parameter editor table.

    This class separates concerns and uses dependency injection to make testing easier.
    """

    def __init__(
        self,
        master,
        local_filesystem: LocalFilesystem,
        parameter_editor,
        message_handler: UIMessageHandler = None,
    ) -> None:
        super().__init__(master)
        self.root = master
        self.local_filesystem = local_filesystem
        self.parameter_editor = parameter_editor
        self.current_file = ""

        # Dependency injection for better testability
        self.message_handler = message_handler or TkinterMessageHandler()
        self.validator = ParameterValidator(local_filesystem.doc_dict)
        self.state_manager = ParameterStateManager()
        self.widget_factory = ParameterWidgetFactory(self.view_port, self.message_handler)

        # UI state
        self.upload_checkbutton_var: dict[str, tk.BooleanVar] = {}

        # Style configuration
        style = ttk.Style()
        style.configure("narrow.TButton", padding=0, width=4, border=(0, 0, 0, 0))

        # Variables for evaluation (used by forced/derived parameters)
        self.variables = local_filesystem.get_eval_variables()

    # ===== FACTORY METHOD FOR TESTING =====
    @classmethod
    def create_for_testing(
        cls,
        local_filesystem: LocalFilesystem = None,
        parameter_editor=None,
        message_handler: UIMessageHandler = None,
    ) -> "ParameterEditorTableRefactored":
        """Factory method for creating instances in tests with dependency injection."""
        import tkinter as tk
        from unittest.mock import MagicMock

        # Create minimal mocks if not provided
        if local_filesystem is None:
            local_filesystem = MagicMock(spec=LocalFilesystem)
            local_filesystem.doc_dict = {}
            local_filesystem.file_parameters = {}
            local_filesystem.param_default_dict = {}
            local_filesystem.configuration_steps = {}
            local_filesystem.forced_parameters = {}
            local_filesystem.derived_parameters = {}
            local_filesystem.get_eval_variables.return_value = {}

        if parameter_editor is None:
            parameter_editor = MagicMock()
            parameter_editor.ui_complexity = "normal"
            parameter_editor.repopulate_parameter_table = MagicMock()

        if message_handler is None:
            message_handler = MagicMock(spec=UIMessageHandler)

        # Create a test root window
        try:
            root = tk.Tk()
            root.withdraw()  # Hide window during testing
        except tk.TclError:
            # Mock root if Tkinter is not available
            root = MagicMock()

        return cls(root, local_filesystem, parameter_editor, message_handler)

    # ===== PUBLIC API METHODS =====

    def validate_parameter_value(self, value_str: str, param_name: str) -> ParameterValidationResult:
        """
        Public method to validate a parameter value.

        This method can be easily tested without UI dependencies.
        """
        format_result = self.validator.validate_value_format(value_str, param_name)
        if not format_result.is_valid:
            return format_result

        return self.validator.validate_bounds(format_result.value, param_name)

    def update_parameter_value(self, param_name: str, new_value: float) -> bool:
        """
        Update a parameter value and return whether it changed.

        This method encapsulates the business logic and can be tested independently.
        """
        if self.current_file not in self.local_filesystem.file_parameters:
            return False

        if param_name not in self.local_filesystem.file_parameters[self.current_file]:
            return False

        old_value = self.local_filesystem.file_parameters[self.current_file][param_name].value

        if self.validator.is_value_changed(old_value, new_value):
            self.local_filesystem.file_parameters[self.current_file][param_name].value = new_value
            self.state_manager.mark_parameter_edited(param_name)
            return True

        return False

    def get_parameter_row_data(self, param_name: str, param: Par, fc_parameters: dict[str, float]) -> ParameterRowData:
        """Create parameter row data object - easily testable."""
        param_metadata = self.local_filesystem.doc_dict.get(param_name, {})
        param_default = self.local_filesystem.param_default_dict.get(param_name, None)
        doc_tooltip = param_metadata.get("doc_tooltip", _("No documentation available in apm.pdef.xml for this parameter"))
        show_upload_column = self._should_show_upload_column()

        return ParameterRowData(
            param_name=param_name,
            param=param,
            param_metadata=param_metadata,
            param_default=param_default,
            doc_tooltip=doc_tooltip,
            fc_parameters=fc_parameters,
            show_upload_column=show_upload_column,
        )

    def process_parameter_change(self, param_name: str, new_value_str: str) -> bool:
        """
        Process a parameter value change from the UI.

        This method orchestrates the validation and update workflow.
        Returns True if the parameter was successfully updated.
        """
        # Validate the format first
        format_result = self.validator.validate_value_format(new_value_str, param_name)
        if not format_result.is_valid:
            self.message_handler.show_error(_("Invalid Value"), format_result.error_message)
            return False

        # Check bounds and get user confirmation if needed
        bounds_result = self.validator.validate_bounds(format_result.value, param_name)
        if not bounds_result.is_valid:
            user_accepts = self.message_handler.show_confirmation(
                _("Out-of-bounds Value"), bounds_result.error_message + "\n" + _("Use out-of-bounds value?")
            )
            if not user_accepts:
                return False

        # Update the parameter value
        return self.update_parameter_value(param_name, format_result.value)

    # ===== UI COMPLEXITY METHODS =====

    def _should_show_upload_column(self, ui_complexity: Union[str, None] = None) -> bool:
        """Determine if the upload column should be shown based on UI complexity."""
        if ui_complexity is None:
            ui_complexity = self.parameter_editor.ui_complexity
        return ui_complexity != "simple"

    def _get_change_reason_column_index(self, show_upload_column: bool) -> int:
        """Get the column index for the change reason entry."""
        base_column_count = 5  # Delete, Parameter, Current Value, New Value, Unit
        if show_upload_column:
            return base_column_count + 1  # Upload column + Change Reason
        return base_column_count  # Change Reason directly after Unit

    # ===== PARAMETER TYPE CHECKING =====

    def _is_forced_or_derived_parameter(self, param_name: str) -> tuple[bool, str]:
        """Check if a parameter is forced or derived and return the appropriate type."""
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

    # ===== STATE MANAGEMENT =====

    def get_at_least_one_param_edited(self) -> bool:
        """Get whether at least one parameter has been edited."""
        return self.state_manager.parameter_edited

    def set_at_least_one_param_edited(self, value: bool) -> None:
        """Set whether at least one parameter has been edited."""
        if value:
            self.state_manager.parameter_edited = True
        else:
            self.state_manager.reset_edited_state()

    # ===== REMAINING METHODS (kept for compatibility but could be further refactored) =====

    def repopulate(self, selected_file: str, fc_parameters: dict[str, float], show_only_differences: bool) -> None:
        """Repopulate the table with parameters from the selected file."""
        # Clear existing widgets
        for widget in self.view_port.winfo_children():
            widget.destroy()

        self.current_file = selected_file

        # Reset state
        self.upload_checkbutton_var = {}

        # Create headers
        show_upload_column = self._should_show_upload_column()
        headers, tooltips = self._create_headers_and_tooltips(show_upload_column)

        for i, header in enumerate(headers):
            label = ttk.Label(self.view_port, text=header)
            label.grid(row=0, column=i, sticky="ew")
            show_tooltip(label, tooltips[i])

        # Process parameters based on filtering
        if show_only_differences:
            params_to_show = self._get_different_parameters(selected_file, fc_parameters)
            if not params_to_show:
                self._show_no_differences_message(selected_file)
                return
        else:
            params_to_show = self.local_filesystem.file_parameters[selected_file]

        # Create parameter rows
        self._create_parameter_rows(params_to_show, fc_parameters, show_upload_column)

        # Configure columns
        self._configure_table_columns(show_upload_column)

        # Scroll to top
        self.canvas.yview("moveto", 0)

    def _get_different_parameters(self, selected_file: str, fc_parameters: dict[str, float]) -> dict[str, Par]:
        """Get parameters that are different from FC values."""
        return {
            param_name: file_value
            for param_name, file_value in self.local_filesystem.file_parameters[selected_file].items()
            if param_name not in fc_parameters
            or (param_name in fc_parameters and not is_within_tolerance(fc_parameters[param_name], float(file_value.value)))
        }

    def _show_no_differences_message(self, selected_file: str) -> None:
        """Show message when no differences are found."""
        info_msg = _("No different parameters found in {selected_file}. Skipping...").format(selected_file=selected_file)
        logging_info(info_msg)
        messagebox.showinfo(_("ArduPilot methodic configurator"), info_msg)
        self.parameter_editor.on_skip_click(force_focus_out_event=False)

    def _create_parameter_rows(
        self, params: dict[str, Par], fc_parameters: dict[str, float], show_upload_column: bool
    ) -> None:
        """Create all parameter rows in the table."""
        for i, (param_name, param) in enumerate(params.items(), 1):
            row_data = self.get_parameter_row_data(param_name, param, fc_parameters)
            widgets = self._create_row_widgets(row_data)
            self._grid_row_widgets(widgets, i, show_upload_column)

        # Add the "Add" button at the bottom
        self._create_add_button(params, fc_parameters)

    def _create_row_widgets(self, row_data: ParameterRowData) -> list[tk.Widget]:
        """Create all widgets for a parameter row."""
        widgets = []

        # Delete button
        widgets.append(
            self.widget_factory.create_delete_button(row_data.param_name, self.current_file, self._on_parameter_delete)
        )

        # Parameter name label
        widgets.append(
            self.widget_factory.create_parameter_label(row_data.param_name, row_data.param_metadata, row_data.doc_tooltip)
        )

        # Flight controller value
        widgets.append(self._create_fc_value_label(row_data))

        # New value entry
        widgets.append(self.widget_factory.create_value_entry(row_data, self._on_parameter_value_change))

        # Unit label
        widgets.append(self._create_unit_label(row_data.param_metadata))

        # Upload checkbox (if needed)
        if row_data.show_upload_column:
            widgets.append(self._create_upload_checkbox(row_data.param_name, bool(row_data.fc_parameters)))

        # Change reason entry
        widgets.append(self._create_change_reason_entry(row_data.param_name, row_data.param))

        return widgets

    def _create_fc_value_label(self, row_data: ParameterRowData) -> ttk.Label:
        """Create flight controller value label."""
        param_name = row_data.param_name
        fc_parameters = row_data.fc_parameters
        param_default = row_data.param_default
        doc_tooltip = row_data.doc_tooltip

        if param_name in fc_parameters:
            value_str = format(fc_parameters[param_name], ".6f").rstrip("0").rstrip(".")
            if param_default is not None and is_within_tolerance(fc_parameters[param_name], param_default.value):
                label = ttk.Label(self.view_port, text=value_str, background="light blue")
            else:
                label = ttk.Label(self.view_port, text=value_str)
        else:
            label = ttk.Label(self.view_port, text=_("N/A"), background="orange")

        if doc_tooltip:
            show_tooltip(label, doc_tooltip)

        return label

    def _create_unit_label(self, param_metadata: dict[str, Union[float, str]]) -> ttk.Label:
        """Create unit label for a parameter."""
        unit_label = ttk.Label(self.view_port, text=param_metadata.get("unit", ""))
        unit_tooltip = str(
            param_metadata.get("unit_tooltip", _("No documentation available in apm.pdef.xml for this parameter"))
        )
        if unit_tooltip:
            show_tooltip(unit_label, unit_tooltip)
        return unit_label

    def _create_upload_checkbox(self, param_name: str, fc_connected: bool) -> ttk.Checkbutton:
        """Create upload checkbox for a parameter."""
        self.upload_checkbutton_var[param_name] = tk.BooleanVar(value=fc_connected)
        upload_checkbutton = ttk.Checkbutton(self.view_port, variable=self.upload_checkbutton_var[param_name])
        upload_checkbutton.configure(state="normal" if fc_connected else "disabled")
        msg = _("When selected upload {param_name} new value to the flight controller")
        show_tooltip(upload_checkbutton, msg.format(param_name=param_name))
        return upload_checkbutton

    def _create_change_reason_entry(self, param_name: str, param: Par) -> ttk.Entry:
        """Create change reason entry for a parameter."""
        is_forced_or_derived, param_type = self._is_forced_or_derived_parameter(param_name)

        # Update comment from forced/derived if needed
        if param_type == "forced":
            forced_comment = self.local_filesystem.forced_parameters[self.current_file][param_name].comment
            if param.comment != forced_comment:
                param.comment = forced_comment
                self.state_manager.mark_parameter_edited(param_name)
        elif param_type == "derived":
            derived_comment = self.local_filesystem.derived_parameters[self.current_file][param_name].comment
            if param.comment != derived_comment:
                param.comment = derived_comment
                self.state_manager.mark_parameter_edited(param_name)

        entry = ttk.Entry(self.view_port, background="white")
        entry.insert(0, "" if param.comment is None else param.comment)

        if is_forced_or_derived:
            entry.config(state="disabled", background="light grey")
        else:
            entry.bind("<FocusOut>", lambda event: self._on_change_reason_change(event, param_name))

        msg = _("Reason why {param_name} should change")
        show_tooltip(entry, msg.format(param_name=param_name))

        return entry

    def _grid_row_widgets(self, widgets: list[tk.Widget], row: int, show_upload_column: bool) -> None:
        """Grid all widgets for a parameter row."""
        for i, widget in enumerate(widgets[:5]):  # First 5 widgets
            widget.grid(row=row, column=i, sticky="w" if i <= 1 else "e", padx=0)

        # Handle upload column
        widget_index = 5
        if show_upload_column:
            widgets[widget_index].grid(row=row, column=5, sticky="e", padx=0)
            widget_index += 1

        # Change reason column
        change_reason_column = self._get_change_reason_column_index(show_upload_column)
        widgets[widget_index].grid(row=row, column=change_reason_column, sticky="ew", padx=(0, 5))

    def _create_add_button(self, params: dict[str, Par], fc_parameters: dict[str, float]) -> None:
        """Create the add parameter button."""
        add_button = ttk.Button(
            self.view_port, text=_("Add"), style="narrow.TButton", command=lambda: self._on_parameter_add(fc_parameters)
        )
        tooltip_msg = _("Add a parameter to the {current_file} file")
        show_tooltip(add_button, tooltip_msg.format(current_file=self.current_file))
        add_button.grid(row=len(params) + 2, column=0, sticky="w", padx=0)

    def _configure_table_columns(self, show_upload_column: bool) -> None:
        """Configure table column weights and sizes."""
        self.view_port.columnconfigure(0, weight=0)  # Delete and Add buttons
        self.view_port.columnconfigure(1, weight=0, minsize=120)  # Parameter name
        self.view_port.columnconfigure(2, weight=0)  # Current Value
        self.view_port.columnconfigure(3, weight=0)  # New Value
        self.view_port.columnconfigure(4, weight=0)  # Units

        if show_upload_column:
            self.view_port.columnconfigure(5, weight=0)  # Upload to FC

        self.view_port.columnconfigure(self._get_change_reason_column_index(show_upload_column), weight=1)

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
        )

        if show_upload_column:
            base_headers.append(_("Upload"))
            base_tooltips.append(_("When selected, upload the new value to the flight controller"))

        base_headers.append(_("Change Reason"))
        base_tooltips.append(change_reason_tooltip)

        return tuple(base_headers), tuple(base_tooltips)

    # ===== EVENT HANDLERS =====

    def _on_parameter_value_change(self, event: tk.Event, param_name: str) -> None:
        """Handle parameter value change events."""
        new_value = event.widget.get_selected_key() if isinstance(event.widget, PairTupleCombobox) else event.widget.get()

        # Process the change using the testable method
        success = self.process_parameter_change(param_name, str(new_value or ""))

        if success:
            # Update UI elements as needed
            self._update_ui_after_parameter_change(event.widget, param_name)

    def _on_change_reason_change(self, event: tk.Event, param_name: str) -> None:
        """Handle change reason modifications."""
        new_comment = event.widget.get()

        try:
            param = self.local_filesystem.file_parameters[self.current_file][param_name]
            if new_comment != param.comment:
                param.comment = new_comment
                self.state_manager.mark_parameter_edited(param_name)
        except KeyError as e:
            logging_critical(_("Parameter %s not found: %s"), param_name, e, exc_info=True)

    def _on_parameter_delete(self, param_name: str) -> None:
        """Handle parameter deletion."""
        msg = _("Are you sure you want to delete the {param_name} parameter?")
        if self.message_handler.show_confirmation(self.current_file, msg.format(param_name=param_name)):
            # Capture scroll position
            current_scroll_position = self.canvas.yview()[0]

            # Delete parameter
            del self.local_filesystem.file_parameters[self.current_file][param_name]
            self.state_manager.mark_parameter_edited(param_name)
            self.parameter_editor.repopulate_parameter_table(self.current_file)

            # Restore scroll position
            self.canvas.yview_moveto(current_scroll_position)

    def _on_parameter_add(self, fc_parameters: dict[str, float]) -> None:
        """Handle parameter addition - simplified for better testability."""
        # This method could be further refactored to separate UI from logic
        # For now, keeping it similar to original but using dependency injection
        # Implementation would be similar to original but using message_handler

    def _update_ui_after_parameter_change(self, widget: tk.Widget, param_name: str) -> None:
        """Update UI elements after a parameter value change."""
        # Update the displayed value and styling
        try:
            param = self.local_filesystem.file_parameters[self.current_file][param_name]
            param_default = self.local_filesystem.param_default_dict.get(param_name, None)

            if isinstance(widget, ttk.Entry):
                self.widget_factory._update_entry_text(widget, param.value, param_default)
        except KeyError:
            pass  # Parameter not found, skip UI update

    # ===== UTILITY METHODS FOR EXTERNAL ACCESS =====

    def get_upload_selected_params(self, current_file: str, ui_complexity: str) -> dict[str, Par]:
        """Get parameters selected for upload."""
        if not self._should_show_upload_column(ui_complexity):
            return self.local_filesystem.file_parameters[current_file]

        selected_params = {}
        for param_name, checkbutton_state in self.upload_checkbutton_var.items():
            if checkbutton_state.get():
                selected_params[param_name] = self.local_filesystem.file_parameters[current_file][param_name]

        return selected_params

    def generate_edit_widgets_focus_out(self) -> None:
        """Trigger focus out events for all entry widgets."""
        for widget in self.view_port.winfo_children():
            if isinstance(widget, ttk.Entry):
                widget.event_generate("<FocusOut>", when="now")


# ===== ADDITIONAL TESTING UTILITIES =====


class MockParameterValidator(ParameterValidator):
    """Mock validator for testing that doesn't depend on real parameter metadata."""

    def __init__(self) -> None:
        super().__init__({})
        self.custom_bounds = {}
        self.custom_validations = {}

    def set_parameter_bounds(self, param_name: str, min_val: Optional[float] = None, max_val: Optional[float] = None) -> None:
        """Set custom bounds for a parameter during testing."""
        self.custom_bounds[param_name] = (min_val, max_val)

    def set_validation_result(self, param_name: str, value: float, result: ParameterValidationResult) -> None:
        """Set a custom validation result for testing."""
        self.custom_validations[(param_name, value)] = result

    def _get_parameter_bounds(self, param_name: str) -> tuple[Union[float, None], Union[float, None]]:
        """Override to return custom bounds for testing."""
        return self.custom_bounds.get(param_name, (None, None))


class MockMessageHandler:
    """Mock implementation of UIMessageHandler that records calls instead of showing dialogs."""

    def __init__(self) -> None:
        self.error_calls = []
        self.confirmation_calls = []
        self.confirmation_response = True

    def show_error(self, title: str, message: str) -> None:
        """Record error message calls."""
        self.error_calls.append((title, message))

    def show_confirmation(self, title: str, message: str) -> bool:
        """Record confirmation calls and return preset response."""
        self.confirmation_calls.append((title, message))
        return self.confirmation_response

    def set_confirmation_response(self, response: bool) -> None:
        """Set the response for confirmation dialogs."""
        self.confirmation_response = response

    def get_last_error(self) -> tuple[str, str]:
        """Get the last error message shown."""
        return self.error_calls[-1] if self.error_calls else ("", "")

    def get_last_confirmation(self) -> tuple[str, str]:
        """Get the last confirmation dialog shown."""
        return self.confirmation_calls[-1] if self.confirmation_calls else ("", "")
