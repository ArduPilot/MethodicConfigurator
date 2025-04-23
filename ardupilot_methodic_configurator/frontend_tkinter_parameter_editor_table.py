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

    def create_table_header(self) -> None:
        """Create the table header with column labels."""
        ttk.Style().configure("TEntry", fieldbackground="white")
        ttk.Style().configure("default_v.TEntry", fieldbackground="#d0d0ff")
        ttk.Style().configure("default_v.TCombobox", fieldbackground="#d0d0ff")

        # Configure grid columns
        self.view_port.columnconfigure(0, weight=0)  # delete button
        self.view_port.columnconfigure(1, weight=0)  # parameter name
        self.view_port.columnconfigure(2, weight=0)  # FC value
        self.view_port.columnconfigure(3, weight=0)  # parameter value
        self.view_port.columnconfigure(4, weight=0)  # parameter unit
        self.view_port.columnconfigure(5, weight=0)  # upload checkbox
        self.view_port.columnconfigure(6, weight=1)  # change reason

        # Create header labels
        header_bg = ttk.Style(self.root).lookup("TFrame", "background")
        ttk.Label(self.view_port, text=_("Del"), background=header_bg).grid(row=0, column=0, sticky="w", padx=0)
        ttk.Label(self.view_port, text=_("Parameter name"), background=header_bg).grid(row=0, column=1, sticky="w", padx=0)
        ttk.Label(self.view_port, text=_("FC Value"), background=header_bg).grid(row=0, column=2, sticky="e", padx=0)
        ttk.Label(self.view_port, text=_("New Value"), background=header_bg).grid(row=0, column=3, sticky="e", padx=0)
        ttk.Label(self.view_port, text=_("Unit"), background=header_bg).grid(row=0, column=4, sticky="e", padx=0)
        ttk.Label(self.view_port, text=_("Upload"), background=header_bg).grid(row=0, column=5, sticky="e", padx=0)
        ttk.Label(self.view_port, text=_("Reason for change"), background=header_bg).grid(
            row=0, column=6, sticky="ew", padx=(0, 5)
        )

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
            self._show_only_differences()

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
