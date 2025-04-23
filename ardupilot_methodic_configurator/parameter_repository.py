"""
Parameter repository for managing ArduPilot parameters.

This file is part of Ardupilot methodic configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2025 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

from abc import ABC, abstractmethod
from logging import debug as logging_debug
from typing import Optional, Protocol

from ardupilot_methodic_configurator import _
from ardupilot_methodic_configurator.ardupilot_parameter import ArduPilotParameter
from ardupilot_methodic_configurator.backend_filesystem import LocalFilesystem, is_within_tolerance


class ParameterObserver(Protocol):
    """Protocol for observers of parameter changes."""

    def on_parameters_changed(self, file_path: str) -> None:
        """Called when parameters for a file have changed."""
        ...


class ParameterRepository(ABC):
    """Interface for parameter storage and retrieval."""

    @abstractmethod
    def get_parameters(self, file_path: str) -> dict[str, ArduPilotParameter]:
        """
        Get all parameters for the specified file.

        Args:
            file_path: Path to the parameter file

        Returns:
            Dictionary mapping parameter names to ArduPilotParameter objects

        """

    @abstractmethod
    def get_parameter(self, file_path: str, param_name: str) -> Optional[ArduPilotParameter]:
        """
        Get a specific parameter from the specified file.

        Args:
            file_path: Path to the parameter file
            param_name: Name of the parameter to retrieve

        Returns:
            The ArduPilotParameter object for the specified parameter, or None if not found

        """

    @abstractmethod
    def save_parameters(self, file_path: str) -> bool:
        """
        Save parameters to the specified file.

        Args:
            file_path: Path to the parameter file

        Returns:
            True if successful, False otherwise

        """

    @abstractmethod
    def update_parameter(self, file_path: str, param_name: str, value: float, comment: Optional[str] = None) -> bool:
        """
        Update a parameter's value and optionally its comment.

        Args:
            file_path: Path to the parameter file
            param_name: Name of the parameter to update
            value: New value for the parameter
            comment: New comment for the parameter (None to leave unchanged)

        Returns:
            True if the parameter was updated, False otherwise

        """

    @abstractmethod
    def delete_parameter(self, file_path: str, param_name: str) -> bool:
        """
        Delete a parameter from the specified file.

        Args:
            file_path: Path to the parameter file
            param_name: Name of the parameter to delete

        Returns:
            True if the parameter was deleted, False otherwise

        """

    @abstractmethod
    def get_available_files(self) -> set[str]:
        """
        Get the set of available parameter files.

        Returns:
            Set of file paths

        """

    @abstractmethod
    def add_observer(self, observer: ParameterObserver) -> None:
        """
        Add an observer to be notified of parameter changes.

        Args:
            observer: Observer to add

        """

    @abstractmethod
    def remove_observer(self, observer: ParameterObserver) -> None:
        """
        Remove an observer.

        Args:
            observer: Observer to remove

        """


class LocalFilesystemParameterRepository(ParameterRepository):
    """Implementation of ParameterRepository using the local filesystem."""

    def __init__(self, local_filesystem: LocalFilesystem) -> None:
        """
        Initialize the repository with a LocalFilesystem instance.

        Args:
            local_filesystem: Instance of LocalFilesystem to use for storage

        """
        self.local_filesystem = local_filesystem
        self.observers: list[ParameterObserver] = []

    def get_parameters(self, file_path: str) -> dict[str, ArduPilotParameter]:
        """
        Get all parameters for the specified file.

        Args:
            file_path: Path to the parameter file

        Returns:
            Dictionary mapping parameter names to ArduPilotParameter objects

        """
        result = {}
        params = self.local_filesystem.file_parameters.get(file_path, {})
        forced_params = self.local_filesystem.forced_parameters.get(file_path, {})
        derived_params = self.local_filesystem.derived_parameters.get(file_path, {})
        default_params = self.local_filesystem.param_default_dict
        fc_params = {}

        # Handle flight controller parameters if available
        if hasattr(self.local_filesystem, "fc_parameters"):
            fc_params = self.local_filesystem.fc_parameters
        elif hasattr(self.local_filesystem, "flight_controller") and hasattr(
            self.local_filesystem.flight_controller, "fc_parameters"
        ):
            fc_params = self.local_filesystem.flight_controller.fc_parameters

        for name, par_obj in params.items():
            # Determine if the parameter is forced or derived
            is_forced = name in forced_params
            is_derived = name in derived_params

            # Get metadata, default value, and FC value
            metadata = self.local_filesystem.doc_dict.get(name, {})
            default_par = default_params.get(name, None)
            fc_value = fc_params.get(name, None)

            # Create ArduPilotParameter object
            parameter = ArduPilotParameter(
                name=name,
                par_obj=par_obj,
                metadata=metadata,
                default_par=default_par,
                fc_value=fc_value,
                is_forced=is_forced,
                is_derived=is_derived,
            )
            result[name] = parameter

        return result

    def get_parameter(self, file_path: str, param_name: str) -> Optional[ArduPilotParameter]:
        """
        Get a specific parameter from the specified file.

        Args:
            file_path: Path to the parameter file
            param_name: Name of the parameter to retrieve

        Returns:
            The ArduPilotParameter object for the specified parameter, or None if not found

        """
        params = self.local_filesystem.file_parameters.get(file_path, {})
        if param_name not in params:
            return None

        par_obj = params[param_name]
        is_forced = param_name in self.local_filesystem.forced_parameters.get(file_path, {})
        is_derived = param_name in self.local_filesystem.derived_parameters.get(file_path, {})
        metadata = self.local_filesystem.doc_dict.get(param_name, {})
        default_par = self.local_filesystem.param_default_dict.get(param_name, None)
        fc_value = {}

        # Handle flight controller parameters if available
        if hasattr(self.local_filesystem, "fc_parameters"):
            fc_value = self.local_filesystem.fc_parameters.get(param_name, None)
        elif hasattr(self.local_filesystem, "flight_controller") and hasattr(
            self.local_filesystem.flight_controller, "fc_parameters"
        ):
            fc_value = self.local_filesystem.flight_controller.fc_parameters.get(param_name, None)

        return ArduPilotParameter(
            name=param_name,
            par_obj=par_obj,
            metadata=metadata,
            default_par=default_par,
            fc_value=fc_value,
            is_forced=is_forced,
            is_derived=is_derived,
        )

    def save_parameters(self, file_path: str) -> bool:
        """
        Save parameters to the specified file.

        Args:
            file_path: Path to the parameter file

        Returns:
            True if successful, False otherwise

        """
        try:
            self.local_filesystem.save_parameters(file_path)
            logging_debug(_("Parameters saved to %s"), file_path)
            return True
        except Exception as e:
            logging_debug(_("Error saving parameters to %s: %s"), file_path, str(e))
            return False

    def update_parameter(self, file_path: str, param_name: str, value: float, comment: Optional[str] = None) -> bool:
        """
        Update a parameter's value and optionally its comment.

        Args:
            file_path: Path to the parameter file
            param_name: Name of the parameter to update
            value: New value for the parameter
            comment: New comment for the parameter (None to leave unchanged)

        Returns:
            True if the parameter was updated, False otherwise

        """
        # Check if the parameter exists
        file_params = self.local_filesystem.file_parameters.get(file_path, {})
        if param_name not in file_params:
            return False

        # Check if the parameter is forced or derived
        if param_name in self.local_filesystem.forced_parameters.get(file_path, {}):
            logging_debug(_("Cannot update forced parameter %s"), param_name)
            return False

        if param_name in self.local_filesystem.derived_parameters.get(file_path, {}):
            logging_debug(_("Cannot update derived parameter %s"), param_name)
            return False

        # Update parameter value and comment
        param = file_params[param_name]
        changed = False

        if not is_within_tolerance(param.value, value):
            param.value = value
            changed = True
            logging_debug(_("Parameter %s value updated to %f"), param_name, value)

        if comment is not None and comment != param.comment:
            param.comment = comment
            changed = True
            logging_debug(_("Parameter %s comment updated to: %s"), param_name, comment)

        # Notify observers if the parameter was changed
        if changed:
            self._notify_observers(file_path)

        return changed

    def delete_parameter(self, file_path: str, param_name: str) -> bool:
        """
        Delete a parameter from the specified file.

        Args:
            file_path: Path to the parameter file
            param_name: Name of the parameter to delete

        Returns:
            True if the parameter was deleted, False otherwise

        """
        file_params = self.local_filesystem.file_parameters.get(file_path, {})
        if param_name not in file_params:
            return False

        # Cannot delete forced or derived parameters
        if param_name in self.local_filesystem.forced_parameters.get(file_path, {}):
            logging_debug(_("Cannot delete forced parameter %s"), param_name)
            return False

        if param_name in self.local_filesystem.derived_parameters.get(file_path, {}):
            logging_debug(_("Cannot delete derived parameter %s"), param_name)
            return False

        # Delete the parameter
        del file_params[param_name]
        logging_debug(_("Parameter %s deleted from %s"), param_name, file_path)

        # Notify observers
        self._notify_observers(file_path)

        return True

    def get_available_files(self) -> set[str]:
        """
        Get the set of available parameter files.

        Returns:
            Set of file paths

        """
        # Directly access the file_parameters dictionary keys from the LocalFilesystem
        return set(self.local_filesystem.file_parameters.keys())

    def add_observer(self, observer: ParameterObserver) -> None:
        """
        Add an observer to be notified of parameter changes.

        Args:
            observer: Observer to add

        """
        if observer not in self.observers:
            self.observers.append(observer)

    def remove_observer(self, observer: ParameterObserver) -> None:
        """
        Remove an observer.

        Args:
            observer: Observer to remove

        """
        if observer in self.observers:
            self.observers.remove(observer)

    def _notify_observers(self, file_path: str) -> None:
        """
        Notify all observers of a parameter change.

        Args:
            file_path: Path to the parameter file that changed

        """
        for observer in self.observers:
            observer.on_parameters_changed(file_path)
