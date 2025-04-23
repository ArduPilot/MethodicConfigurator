"""
Parameter editor table UI component.

This file is part of Ardupilot methodic configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2025 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import tkinter as tk
from logging import debug as logging_debug
from tkinter import ttk
from typing import Any, Callable, Dict, Optional

from ardupilot_methodic_configurator import _
from ardupilot_methodic_configurator.annotate_params import Par
from ardupilot_methodic_configurator.backend_filesystem import LocalFilesystem
from ardupilot_methodic_configurator.frontend_tkinter_parameter_editor_row import ParameterEditorRow
from ardupilot_methodic_configurator.frontend_tkinter_scroll_frame import ScrollFrame
from ardupilot_methodic_configurator.parameter_editor_model import ParameterEditorModel


# pylint: disable=too-many-lines


class ParameterEditorTable(ScrollFrame):  # pylint: disable=too-many-ancestors
    """
    A class to manage and display the parameter editor table within the GUI.

    This class inherits from ScrollFrame and is responsible for creating,
    managing, and updating the table that displays parameters for editing.
    """

    def __init__(
        self,
        root: ttk.Widget,
        parent: Any,
        param_default_dict: Dict[str, Par],
        doc_dict: Dict[str, Dict],
        local_filesystem: LocalFilesystem,
        current_file: str,
        parameter_model: ParameterEditorModel,
        parameter_upload_callback: Optional[Callable[[str, float], None]] = None,
        fc_parameters_dict: Dict[str, float] = None,
    ) -> None:
        """
        Create a new row-scrollable parameter editor table.

        Args:
            root: The parent widget for this table
            parent: The parent window (usually ParameterEditorWindow)
            param_default_dict: Dictionary of default parameter values
            doc_dict: Parameter documentation dictionary
            local_filesystem: Local filesystem instance
            current_file: Current parameter file being edited
            parameter_model: The parameter editor model
            parameter_upload_callback: Callback function for parameter uploads
            fc_parameters_dict: Dictionary of flight controller parameters

        """
        super().__init__(root)

        # Store the references
        self.root = root
        self.parent = parent
        self.param_default_dict = param_default_dict
        self.doc_dict = doc_dict
        self.local_filesystem = local_filesystem
        self.current_file = current_file
        self.model = parameter_model
        self.parameter_upload_callback = parameter_upload_callback
        self.fc_parameters_dict = fc_parameters_dict or {}

        # UI state
        self.at_least_one_param_edited = False
        self.upload_checkbutton_var: Dict[str, tk.BooleanVar] = {}
        self.rows: Dict[str, ParameterEditorRow] = {}

        # Initialize the UI
        self.create_table_header()

        # Register as an observer of the model
        self.model.add_observer(self._on_model_changed)

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

    def load_parameters(self, file_path: str) -> None:
        """
        Load parameters from the specified file.

        Args:
            file_path: Path to the parameter file to load

        """
        self.current_file = file_path
        self.model.load_parameters(file_path)

    def _on_model_changed(self) -> None:
        """Handle notification that the model has changed."""
        self.populate_table()

    def populate_table(self) -> None:
        """Populate the table with parameter rows."""
        # Get parameters from the model
        parameters = self.model.get_all_parameters()

        # Clear existing rows and UI widgets
        for widget in self.view_port.grid_slaves():
            if int(widget.grid_info()["row"]) > 0:  # Skip header row
                widget.grid_forget()

        self.rows = {}
        self.upload_checkbutton_var = {}

        # Add parameter rows
        row_index = 1  # Start after header row
        # Process parameters in alphabetical order
        for param_name in self.model.get_sorted_parameter_names():
            parameter = parameters[param_name]

            # Create a row for this parameter
            row = ParameterEditorRow(
                self,
                parameter,
                row_index,
                on_value_changed_callback=self._on_parameter_value_changed,
                on_comment_changed_callback=self._on_parameter_comment_changed,
                on_delete_callback=self._on_parameter_deleted,
            )

            # Store the row for later reference
            self.rows[param_name] = row

            row_index += 1

    def repopulate(self, file_path: str, fc_parameters=None, show_only_differences: bool = False) -> None:
        """
        Repopulate the table with parameters from a specific file.

        Args:
            file_path: The parameter file to display
            fc_parameters: Optional dictionary of flight controller parameters
            show_only_differences: If True, only show parameters that differ from FC values

        """
        # Update FC parameters if provided
        if fc_parameters is not None:
            self.fc_parameters_dict = fc_parameters

        # Load the new file
        self.load_parameters(file_path)

        # If show_only_differences is True, hide rows that don't differ from FC values
        if show_only_differences:
            # recompute different_params because of renames and derived values changes
            self._show_only_differences()
            # Scroll to the top of the parameter table
            self.canvas.yview("moveto", 0)

    def _show_only_differences(self) -> None:
        """Hide rows where the parameter value matches the FC value."""
        for row in self.rows.values():
            if not row.param.is_different_from_fc:
                # Hide this row
                if row.delete_button:
                    row.delete_button.grid_forget()
                if row.param_label:
                    row.param_label.grid_forget()
                if row.fc_value_label:
                    row.fc_value_label.grid_forget()
                if row.new_value_widget:
                    row.new_value_widget.grid_forget()
                if row.unit_label:
                    row.unit_label.grid_forget()
                if row.upload_checkbutton:
                    row.upload_checkbutton.grid_forget()
                if row.change_reason_entry:
                    row.change_reason_entry.grid_forget()

    def _on_parameter_value_changed(self, param_name: str, value: float) -> None:
        """
        Handle parameter value changes from a row.

        Args:
            param_name: Name of the parameter that changed
            value: New parameter value

        """
        self.model.update_parameter(param_name, value)

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

    def _on_parameter_comment_changed(self, param_name: str, comment: str) -> None:
        """
        Handle parameter comment changes from a row.

        Args:
            param_name: Name of the parameter whose comment changed
            comment: New parameter comment

        """
        # Update both the value (to keep it unchanged) and comment
        parameter = self.model.get_parameter(param_name)
        if parameter:
            self.model.update_parameter(param_name, parameter.value, comment)

    def _on_parameter_deleted(self, param_name: str) -> None:
        """
        Handle parameter deletion from a row.

        Args:
            param_name: Name of the parameter to delete

        """
        # Capture current vertical scroll position
        current_scroll_position = self.canvas.yview()[0]

        # Delete the parameter through the model
        self.model.delete_parameter(param_name)

        # Restore the scroll position
        self.canvas.yview_moveto(current_scroll_position)

    def generate_edit_widgets_focus_out(self) -> None:
        """Generate focus out events for all edit widgets to save pending changes."""
        # Simulate focus out events for any edit widgets to save pending changes
        for row in self.rows.values():
            if row.new_value_widget and not (row.param.is_forced or row.param.is_derived):
                focus_out_event = tk.Event()
                focus_out_event.widget = row.new_value_widget
                row.on_value_change(focus_out_event)

            if row.change_reason_entry and not (row.param.is_forced or row.param.is_derived):
                focus_out_event = tk.Event()
                focus_out_event.widget = row.change_reason_entry
                row.on_change_reason_change(focus_out_event)

    def get_parameters_for_upload(self) -> Dict[str, Par]:
        """
        Get parameters selected for upload to the flight controller.

        Returns:
            A dictionary of parameter names to Par objects for selected parameters

        """
        params_to_upload = {}
        parameters = self.model.get_all_parameters()

        for param_name, row in self.rows.items():
            if row.upload_var.get() and param_name in parameters:
                param = parameters[param_name]
                params_to_upload[param_name] = Par(param.value, param.comment)

        return params_to_upload

    def save_parameters(self) -> None:
        """Save parameters to file if any have been edited."""
        self.model.save_parameters()

    def upload_parameters(self) -> None:
        """Upload selected parameters to the flight controller if connected."""
        params_to_upload = self.get_parameters_for_upload()

        if params_to_upload:
            if self.parameter_upload_callback:
                logging_debug(_("Uploading %d parameters to the flight controller"), len(params_to_upload))
                self.parameter_upload_callback(params_to_upload)
            else:
                logging_debug(_("No callback function defined for parameter upload"))
        else:
            logging_debug(_("No parameters selected for upload"))

    def get_at_least_one_param_edited(self) -> bool:
        """Get whether at least one parameter has been edited."""
        return self.at_least_one_param_edited

    def set_at_least_one_param_edited(self, value: bool) -> None:
        """Set whether at least one parameter has been edited."""
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

    def get_upload_selected_params(self, file_path: str) -> Dict[str, Par]:
        """
        Get parameters selected for upload to the flight controller.

        Args:
            file_path: Path to the parameter file

        Returns:
            Dictionary of parameter names to Par objects for upload

        """
        # Make sure we have the latest parameters from the model
        self.model.load_parameters(file_path)
        return self.get_parameters_for_upload()
