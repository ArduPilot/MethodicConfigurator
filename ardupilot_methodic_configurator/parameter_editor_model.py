"""
Parameter editor model for the ArduPilot Methodic Configurator.

This file is part of Ardupilot methodic configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2025 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

from logging import debug as logging_debug
from tkinter import messagebox
from typing import Callable, Optional

from ardupilot_methodic_configurator import _
from ardupilot_methodic_configurator.annotate_params import Par
from ardupilot_methodic_configurator.ardupilot_parameter import ArduPilotParameter
from ardupilot_methodic_configurator.parameter_repository import ParameterObserver, ParameterRepository


class ParameterEditorModel(ParameterObserver):
    """
    Model class that mediates between the UI and parameter repository.

    This class is responsible for managing parameter state and notifying observers of changes.
    It follows the Observer pattern to notify UI components when parameters change.
    """

    def __init__(self, repository: ParameterRepository) -> None:
        """
        Initialize the model with a parameter repository.

        Args:
            repository: The parameter repository to use for storage

        """
        self.repository = repository
        self.parameters: dict[str, ArduPilotParameter] = {}
        self.current_file = ""
        self.observers: list[Callable[[], None]] = []
        self.modified = False

        # Register as an observer of the repository
        self.repository.add_observer(self)

    def load_parameters(self, file_path: str) -> None:
        """
        Load parameters from the specified file.

        Args:
            file_path: Path to the parameter file to load

        """
        self.parameters = self.repository.get_parameters(file_path)
        self.current_file = file_path
        self.modified = False
        self._notify_observers()
        logging_debug(_("Loaded %d parameters from %s"), len(self.parameters), file_path)

    def get_parameter(self, param_name: str) -> Optional[ArduPilotParameter]:
        """
        Get a parameter by name.

        Args:
            param_name: Name of the parameter to get

        Returns:
            The parameter object, or None if not found

        """
        return self.parameters.get(param_name)

    def get_all_parameters(self) -> dict[str, ArduPilotParameter]:
        """
        Get all parameters for the current file.

        Returns:
            Dictionary of parameter names to parameter objects

        """
        return self.parameters

    def get_sorted_parameter_names(self) -> list[str]:
        """
        Get a sorted list of parameter names.

        Returns:
            Sorted list of parameter names

        """
        return sorted(self.parameters.keys())

    def update_parameter(self, param_name: str, value: float, comment: Optional[str] = None) -> bool:
        """
        Update a parameter's value and/or comment.

        Args:
            param_name: Name of the parameter to update
            value: New value for the parameter
            comment: New comment for the parameter (None to leave unchanged)

        Returns:
            True if the parameter was updated, False otherwise

        """
        if param_name not in self.parameters:
            return False

        param = self.parameters[param_name]
        if param.is_forced or param.is_derived:
            return False

        # Check parameter bounds
        if not param.is_valid_value(value) and not self._confirm_out_of_bounds_value(param, value):
            return False

        # Update the repository (which will notify us through the observer pattern)
        return self.repository.update_parameter(self.current_file, param_name, value, comment)

    def delete_parameter(self, param_name: str) -> bool:
        """
        Delete a parameter.

        Args:
            param_name: Name of the parameter to delete

        Returns:
            True if the parameter was deleted, False otherwise

        """
        if param_name not in self.parameters:
            return False

        if not self._confirm_parameter_deletion(param_name):
            return False

        # Delete from repository (which will notify us through the observer pattern)
        return self.repository.delete_parameter(self.current_file, param_name)

    def save_parameters(self) -> bool:
        """
        Save parameters to the current file.

        Returns:
            True if parameters were saved successfully, False otherwise

        """
        if not self.modified:
            logging_debug(_("No parameters were modified, no need to save"))
            return True

        if not self._confirm_save_parameters():
            logging_debug(_("User chose not to save parameters"))
            return False

        success = self.repository.save_parameters(self.current_file)
        if success:
            self.modified = False
            self._notify_observers()
            logging_debug(_("Parameters saved to %s"), self.current_file)
        else:
            logging_debug(_("Failed to save parameters to %s"), self.current_file)

        return success

    def get_parameters_for_upload(self) -> dict[str, Par]:
        """
        Get parameters selected for upload to the flight controller.

        This is a stub method that should be overridden by subclasses or implemented
        with a different pattern since it depends on UI state (checkboxes).

        Returns:
            Dictionary of parameter names to Par objects for selected parameters

        """
        # This method needs UI state input - it's a placeholder for now
        return {}

    def get_available_files(self) -> set[str]:
        """
        Get the set of available parameter files.

        Returns:
            Set of file paths

        """
        return self.repository.get_available_files()

    def is_modified(self) -> bool:
        """
        Check if parameters have been modified.

        Returns:
            True if parameters have been modified, False otherwise

        """
        return self.modified

    def on_parameters_changed(self, file_path: str) -> None:
        """
        Handle notification from the repository that parameters have changed.

        Args:
            file_path: Path to the parameter file that changed

        """
        if file_path == self.current_file:
            # Reload parameters
            self.parameters = self.repository.get_parameters(file_path)
            self.modified = True
            self._notify_observers()

    def add_observer(self, observer: Callable[[], None]) -> None:
        """
        Add an observer to be notified of model changes.

        Args:
            observer: Callback function to call when the model changes

        """
        if observer not in self.observers:
            self.observers.append(observer)

    def remove_observer(self, observer: Callable[[], None]) -> None:
        """
        Remove an observer.

        Args:
            observer: Observer to remove

        """
        if observer in self.observers:
            self.observers.remove(observer)

    def _notify_observers(self) -> None:
        """Notify all observers of a model change."""
        for observer in self.observers:
            observer()

    def _confirm_out_of_bounds_value(self, param: ArduPilotParameter, value: float) -> bool:
        """
        Confirm with the user whether to use an out-of-bounds value.

        Args:
            param: The parameter being updated
            value: The proposed new value

        Returns:
            True if the user confirms, False otherwise

        """
        message = ""
        if param.min_value is not None and value < param.min_value:
            message = _("The value for {param.name} ({value}) should be greater than {param.min_value}\n")
        elif param.max_value is not None and value > param.max_value:
            message = _("The value for {param.name} ({value}) should be smaller than {param.max_value}\n")

        if message:
            return messagebox.askyesno(
                _("Out-of-bounds Value"),
                message.format(param=param, value=value) + _("Use out-of-bounds value?"),
                icon="warning",
            )

        return True

    def _confirm_parameter_deletion(self, param_name: str) -> bool:
        """
        Confirm with the user whether to delete a parameter.

        Args:
            param_name: Name of the parameter to delete

        Returns:
            True if the user confirms, False otherwise

        """
        message = _("Are you sure you want to delete the {param_name} parameter?")
        return messagebox.askyesno(self.current_file, message.format(param_name=param_name))

    def _confirm_save_parameters(self) -> bool:
        """
        Confirm with the user whether to save parameters.

        Returns:
            True if the user confirms, False otherwise

        """
        message = _("Do you want to save the changes to the {file}?")
        return messagebox.askyesno(_("Save Parameters"), message.format(file=self.current_file), icon="question")
