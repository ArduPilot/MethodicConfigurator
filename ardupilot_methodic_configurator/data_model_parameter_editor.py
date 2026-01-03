"""
The business logic for the configuration (parameter editing and uploading).

Contains state information but no GUI code.
Aggregates flight controller and filesystem access in a single interface.
Uses exceptions for error handling, the GUI layer will catch and display them.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

from csv import writer as csv_writer
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from logging import error as logging_error
from logging import exception as logging_exception
from logging import info as logging_info
from logging import warning as logging_warning
from pathlib import Path
from time import time
from typing import Callable, Literal, Optional

from ardupilot_methodic_configurator import _
from ardupilot_methodic_configurator.backend_filesystem import LocalFilesystem
from ardupilot_methodic_configurator.backend_filesystem_configuration_steps import PhaseData
from ardupilot_methodic_configurator.backend_flightcontroller import FlightController
from ardupilot_methodic_configurator.backend_internet import download_file_from_url, webbrowser_open_url
from ardupilot_methodic_configurator.data_model_ardupilot_parameter import (
    ArduPilotParameter,
    ParameterOutOfRangeError,
    ParameterUnchangedError,
)
from ardupilot_methodic_configurator.data_model_battery_monitor import BatteryMonitorDataModel
from ardupilot_methodic_configurator.data_model_configuration_step import ConfigurationStepProcessor
from ardupilot_methodic_configurator.data_model_motor_test import MotorTestDataModel
from ardupilot_methodic_configurator.data_model_par_dict import Par, ParDict, is_within_tolerance
from ardupilot_methodic_configurator.plugin_constants import PLUGIN_BATTERY_MONITOR, PLUGIN_MOTOR_TEST
from ardupilot_methodic_configurator.tempcal_imu import IMUfit

# Type aliases for callback functions used in workflow methods
AskConfirmationCallback = Callable[[str, str], bool]  # (title, message) -> bool
SelectFileCallback = Callable[[str, list[str]], Optional[str]]  # (title, filetypes) -> Optional[filename]
ShowWarningCallback = Callable[[str, str], None]  # (title, message) -> None
ShowErrorCallback = Callable[[str, str], None]  # (title, message) -> None
ShowInfoCallback = Callable[[str, str], None]  # (title, message) -> None
AskRetryCancelCallback = Callable[[str, str], bool]  # (title, message) -> bool
ExperimentChoice = Literal["close", True, False]
ExperimentChoiceCallback = Callable[[str, str, list[str]], ExperimentChoice]


class OperationNotPossibleError(Exception):
    """Raised when an operation cannot be performed due to missing prerequisites or state."""


class InvalidParameterNameError(Exception):
    """Raised when a parameter name is invalid or already exists."""


class ParameterValueUpdateStatus(Enum):
    """Possible outcomes when updating a parameter value."""

    UPDATED = "updated"
    UNCHANGED = "unchanged"
    ERROR = "error"
    CONFIRM_OUT_OF_RANGE = "confirm_out_of_range"


@dataclass
class ParameterValueUpdateResult:
    """Presenter-friendly response describing the outcome of a parameter update attempt."""

    status: ParameterValueUpdateStatus
    title: Optional[str] = None
    message: Optional[str] = None


# pylint: disable=too-many-lines


class ParameterEditor:  # pylint: disable=too-many-public-methods, too-many-instance-attributes
    """
    Manages configuration state, including flight controller and filesystem access.

    This class aggregates the flight controller and filesystem access to provide a unified interface
    for managing configuration state. It holds protected references to the flight controller and filesystem,
    and provides methods to interact with them.
    """

    def __init__(self, current_file: str, flight_controller: FlightController, filesystem: LocalFilesystem) -> None:
        self.current_file = current_file
        self._flight_controller = flight_controller
        self._local_filesystem = filesystem
        self._config_step_processor = ConfigurationStepProcessor(self._local_filesystem)

        # self.current_step_parameters is rebuilt on every repopulate(...) call and only contains the ArduPilotParameter
        # objects needed for the current table view.
        self.current_step_parameters: dict[str, ArduPilotParameter] = {}

        # Track parameters added by user (not in original file) or renamed by the system in the current configuration step
        self._added_parameters: set[str] = set()

        # Track parameters deleted by user (were in original file) or renamed by the system in the current configuration step
        self._deleted_parameters: set[str] = set()

        self._at_least_one_changed = False

        self._last_time_asked_to_save: float = 0

    # frontend_tkinter_parameter_editor.py API start
    @property
    def connected_vehicle_type(self) -> str:
        return (
            getattr(self._flight_controller.info, "vehicle_type", "")
            if hasattr(self._flight_controller, "info") and self._flight_controller.info is not None
            else ""
        )

    @property
    def is_fc_connected(self) -> bool:
        return self._flight_controller.master is not None and bool(self._flight_controller.fc_parameters)

    @property
    def fc_parameters(self) -> dict[str, float]:
        return (
            self._flight_controller.fc_parameters
            if hasattr(self._flight_controller, "fc_parameters") and self._flight_controller.fc_parameters is not None
            else {}
        )

    @property
    def is_mavftp_supported(self) -> bool:
        return (
            getattr(self._flight_controller.info, "is_mavftp_supported", False)
            if hasattr(self._flight_controller, "info") and self._flight_controller.info is not None
            else False
        )

    def handle_imu_temperature_calibration_workflow(  # pylint: disable=too-many-arguments, too-many-positional-arguments
        self,
        selected_file: str,
        ask_user_confirmation: AskConfirmationCallback,
        select_file: SelectFileCallback,
        show_warning: ShowWarningCallback,
        show_error: ShowErrorCallback,
        get_progress_callback: Optional[Callable[[], Optional[Callable]]] = None,
    ) -> bool:
        """
        Complete IMU temperature calibration workflow with user interaction via callbacks.

        This method orchestrates the entire IMU calibration workflow including user confirmation,
        file selection, warnings, error handling, and the actual calibration through injected
        callback functions. This allows the business logic to be separated from GUI implementation details.

        Args:
            selected_file: The current parameter file being processed.
            ask_user_confirmation: Callback function for asking yes/no questions.
            select_file: Callback function for file selection dialog.
            show_warning: Callback function for showing warning messages.
            show_error: Callback function for showing error messages.
            get_progress_callback: Optional factory function that creates and returns a progress callback.

        Returns:
            bool: True if calibration was performed successfully, False otherwise.

        """
        # Check if IMU temperature calibration should be offered for this file
        tempcal_imu_result_param_filename, tempcal_imu_result_param_fullpath = (
            self._local_filesystem.tempcal_imu_result_param_tuple()
        )
        if selected_file != tempcal_imu_result_param_filename:
            return False

        # Ask user for confirmation using injected callback
        confirmation_msg = _(
            "If you proceed the {tempcal_imu_result_param_filename}\n"
            "will be overwritten with the new calibration results.\n"
            "Do you want to provide a .bin log file and\n"
            "run the IMU temperature calibration using it?"
        ).format(tempcal_imu_result_param_filename=tempcal_imu_result_param_filename)

        if not ask_user_confirmation(_("IMU temperature calibration"), confirmation_msg):
            return False

        # Select log file using injected callback
        log_file = select_file(_("Select ArduPilot binary log file"), ["*.bin", "*.BIN"])

        if not log_file:
            return False  # User cancelled file selection

        # Show warning using injected callback
        show_warning(
            _("IMU temperature calibration"),
            _("Please wait, this can take a really long time and\nthe GUI will be unresponsive until it finishes."),
        )

        # Get progress callback from factory if provided
        progress_callback = get_progress_callback() if get_progress_callback else None

        # Perform the actual IMU temperature calibration
        IMUfit(
            logfile=log_file,
            outfile=tempcal_imu_result_param_fullpath,
            no_graph=False,
            log_parm=False,
            online=False,
            tclr=False,
            figpath=self._local_filesystem.vehicle_dir,
            progress_callback=progress_callback,
        )

        try:
            # Reload parameter files after calibration
            self._local_filesystem.file_parameters = self._local_filesystem.read_params_from_files()
            return True
        except SystemExit as exp:
            show_error(_("Fatal error reading parameter files"), f"{exp}")
            raise

    def _should_copy_fc_values_to_file(self, selected_file: str) -> tuple[bool, Optional[dict], Optional[str]]:
        """
        Check if flight controller values should be copied to the specified file.

        Args:
            selected_file: The file to check for copying requirements.

        Returns:
            tuple: (should_copy, relevant_fc_params, auto_changed_by) - should_copy indicates if copy is needed,
                   relevant_fc_params contains the parameters to copy if needed,
                   auto_changed_by contains the tool name that requires external changes.

        """
        auto_changed_by = self._local_filesystem.auto_changed_by(selected_file)
        if auto_changed_by and self._flight_controller.fc_parameters:
            # Filter relevant FC parameters for this file
            relevant_fc_params = {
                key: value
                for key, value in self._flight_controller.fc_parameters.items()
                if key in self.current_step_parameters
            }
            return True, relevant_fc_params, auto_changed_by
        return False, None, auto_changed_by

    def _update_parameters_from_fc_values(self, relevant_fc_params: dict[str, float]) -> bool:
        """
        Update in-memory parameter values from flight controller values.

        This method updates the ArduPilotParameter objects in current_step_parameters
        with values from the flight controller. The updated values are held in memory
        and will be saved to the parameter file later when the user either:
        - Uploads parameters to the FC (via upload button)
        - Skips to the next parameter file (via skip button)

        At that point, the user will be prompted to save changes to file if any
        parameters have been modified.

        Args:
            relevant_fc_params: Dictionary of parameter names and FC values to copy.

        Returns:
            bool: True if at least one parameter was successfully updated in memory.

        Note:
            This method bypasses range checking since values came from the FC and were
            already accepted there. The GUI table view immediately reflects the copied
            FC values, and subsequent dirty-state tracking operates on the updated state.

        """
        params_copied = 0
        for param_name, value in relevant_fc_params.items():
            param = self.current_step_parameters.get(param_name)
            if param is None:
                logging_error(_("Parameter %s not in current step parameters"), param_name)
                continue
            try:
                param.set_new_value(str(value), ignore_out_of_range=True)
                params_copied += 1
            except ParameterUnchangedError:
                continue  # Expected, not an error
            except ParameterOutOfRangeError:
                # Log warning but accept FC value anyway since it came from FC
                logging_warning(_("Parameter %s value %s is out of range but accepted from FC"), param_name, value)
                params_copied += 1
            except (ValueError, TypeError):
                logging_exception(_("Failed to update in-memory value for %s after FC copy"), param_name)
                continue
        return bool(params_copied)

    def handle_copy_fc_values_workflow(
        self,
        selected_file: str,
        ask_user_choice: ExperimentChoiceCallback,
        show_info: ShowInfoCallback,
    ) -> ExperimentChoice:
        """
        Handle the complete workflow for copying FC values to file with user interaction.

        Args:
            selected_file: The configuration file to potentially update.
            ask_user_choice: Callback to ask user for choice (Yes/No/Close).
            show_info: Callback to show information messages.

        Returns:
            ExperimentChoice: "close" if user chose to close, True if copied, False if no copy.

        """
        should_copy, relevant_fc_params, auto_changed_by = self._should_copy_fc_values_to_file(selected_file)
        if should_copy and relevant_fc_params and auto_changed_by:
            msg = _(
                "This configuration step requires external changes by: {auto_changed_by}\n\n"
                "The external tool experiment procedure is described in the tuning guide.\n\n"
                "Choose an option:\n"
                "* CLOSE - Close the application and go perform the experiment\n"
                "* YES - Copy current FC values to {selected_file} (if you've already completed the experiment)\n"
                "* NO - Continue without copying values (if you haven't performed the experiment yet,"
                " but know what you are doing)"
            ).format(auto_changed_by=auto_changed_by, selected_file=selected_file)

            user_choice = ask_user_choice(_("Update file with values from FC?"), msg, [_("Close"), _("Yes"), _("No")])

            if user_choice is True:  # Yes option
                params_copied = self._update_parameters_from_fc_values(relevant_fc_params)
                if params_copied:
                    show_info(
                        _("Parameters copied"),
                        _("FC values have been copied to {selected_file}").format(selected_file=selected_file),
                    )
            return user_choice
        return False

    def _handle_file_jump_workflow(
        self,
        selected_file: str,
        gui_complexity: str,
        ask_user_confirmation: AskConfirmationCallback,
    ) -> str:
        """
        Handle the complete workflow for file jumping with user interaction.

        Args:
            selected_file: The current configuration file.
            gui_complexity: The GUI complexity setting ("simple" or other).
            ask_user_confirmation: Callback to ask user for confirmation.

        Returns:
            str: The destination file to jump to, or the original file if no jump.

        """
        jump_options = self._get_file_jump_options(selected_file)
        for dest_file, msg in jump_options.items():
            if gui_complexity == "simple" or ask_user_confirmation(
                _("Skip some steps?"), _(msg) if msg else _("Skip to {dest_file}?").format(dest_file=dest_file)
            ):
                return dest_file
        return selected_file

    def _get_file_jump_options(self, selected_file: str) -> dict[str, str]:
        """
        Get available file jump options for the selected file.

        Args:
            selected_file: The current configuration file.

        Returns:
            dict: Dictionary mapping destination files to their messages.

        """
        return self._local_filesystem.jump_possible(selected_file)

    def handle_write_changes_workflow(
        self,
        annotate_params_into_files: bool,
        ask_user_confirmation: AskConfirmationCallback,
    ) -> bool:
        """
        Handle the workflow for writing changes to intermediate parameter file.

        Args:
            at_least_one_param_edited: Whether any parameters have been edited.
            annotate_params_into_files: Whether to annotate documentation into files.
            ask_user_confirmation: Callback to ask user for confirmation.

        Returns:
            bool: True if changes were written, False otherwise.

        """
        elapsed_since_last_ask = time() - self._last_time_asked_to_save
        # Avoid asking the user multiple times in quick succession (e.g., during file transitions)
        # Always check elapsed time to prevent duplicate prompts within 1 second
        # If annotate parameters into files is true, we always need to write to file, because
        # the parameter metadata might have changed, or not be present in the file.
        if (self._has_unsaved_changes() or annotate_params_into_files) and elapsed_since_last_ask > 1.0:
            msg = _("Do you want to write the changes to the {current_filename} file?").format(
                current_filename=self.current_file
            )
            should_save = ask_user_confirmation(_("One or more parameters have been edited"), msg)
            if should_save:
                self._export_current_file(annotate_doc=annotate_params_into_files)

            # Update timestamp regardless of user's answer to prevent duplicate prompts
            self._last_time_asked_to_save = time()
            return should_save
        return False

    def handle_param_file_change_workflow(  # pylint: disable=too-many-arguments, too-many-positional-arguments, too-many-locals # noqa: PLR0913
        self,
        selected_file: str,
        forced: bool,
        gui_complexity: str,
        auto_open_documentation: bool,
        handle_imu_temp_cal: Callable[[str], None],
        handle_copy_fc_values: Callable[[str], ExperimentChoice],
        handle_upload_file: Callable[[str], None],
        ask_confirmation: AskConfirmationCallback,
        show_error: ShowErrorCallback,
        show_info: ShowInfoCallback,
    ) -> tuple[str, bool]:
        """
        Handle the complete workflow when parameter file selection changes.

        This method orchestrates all the steps that need to happen when switching
        to a different parameter file, including:
        - IMU temperature calibration check
        - File jumping
        - Documentation opening
        - FC values copy check
        - File download/upload

        Args:
            selected_file: The newly selected parameter file.
            forced: Whether to force the workflow even if file hasn't changed.
            gui_complexity: The GUI complexity setting ("simple" or other).
            auto_open_documentation: Whether to automatically open documentation.
            handle_imu_temp_cal: Callback to handle IMU temperature calibration.
            handle_copy_fc_values: Callback to handle copying FC values to file.
            handle_upload_file: Callback to handle file upload.
            ask_confirmation: Callback to ask user for confirmation.
            show_error: Callback to show error messages.
            show_info: Callback to show information messages.

        Returns:
            tuple: (final_selected_file, should_continue) - The final file after any jumps,
                   and whether to continue with the workflow (False means user wants to close).

        """
        # If file hasn't changed and not forced, skip the workflow
        if self.current_file == selected_file and not forced:
            return selected_file, True

        # Handle IMU temperature calibration workflow
        handle_imu_temp_cal(selected_file)

        # Handle file jumping
        self.current_file = self._handle_file_jump_workflow(selected_file, gui_complexity, ask_confirmation)

        # Open documentation if configured
        if auto_open_documentation or gui_complexity == "simple":
            self.open_documentation_in_browser(self.current_file)

        # Process configuration step and create domain model parameters
        (ui_errors, ui_infos) = self._repopulate_configuration_step_parameters()

        for title, msg in ui_errors:
            show_error(title, msg)
        for title, msg in ui_infos:
            show_info(title, msg)

        # Handle copying FC values to file, can only be done after repopulate
        result = handle_copy_fc_values(self.current_file)
        if result == "close":
            # User wants to close application
            if self.is_fc_connected:
                self._flight_controller.disconnect()
            return self.current_file, False

        # Handle file download from URL
        if self._should_download_file_from_url_workflow(self.current_file, ask_confirmation, show_error):
            # Handle file upload to FC
            handle_upload_file(self.current_file)

        return self.current_file, True

    def _should_download_file_from_url_workflow(
        self,
        selected_file: str,
        ask_confirmation: AskConfirmationCallback,
        show_error: ShowErrorCallback,
    ) -> bool:
        """
        Handle file download workflow with injected GUI callbacks.

        This method implements the business logic for downloading files while
        allowing the GUI to handle user interactions through callbacks.

        Args:
            selected_file: The configuration file being processed.
            ask_confirmation: Callback to ask user if they want to download the file.
            show_error: Callback to show error messages to the user.

        Returns:
            bool: True if download was successful or not needed, False if download failed.

        """
        url, local_filename = self._local_filesystem.get_download_url_and_local_filename(selected_file)
        if not url or not local_filename:
            return True  # No download required

        if self._local_filesystem.vehicle_configuration_file_exists(local_filename):
            return True  # File already exists in the vehicle directory, no need to download it

        # Ask user for confirmation
        msg = _("Should the {local_filename} file be downloaded from the URL\n{url}?")
        if not ask_confirmation(_("Download file from URL"), msg.format(local_filename=local_filename, url=url)):
            return False  # User declined download

        # Attempt download
        if not download_file_from_url(url, local_filename):
            error_msg = _("Failed to download {local_filename} from {url}, please download it manually")
            show_error(_("Download failed"), error_msg.format(local_filename=local_filename, url=url))
            return False

        return True

    def should_upload_file_to_fc_workflow(  # pylint: disable=too-many-arguments, too-many-positional-arguments
        self,
        selected_file: str,
        ask_confirmation: Callable[[str, str], bool],
        show_error: Callable[[str, str], None],
        show_warning: Callable[[str, str], None],
        get_progress_callback: Callable[[], Optional[Callable]],
    ) -> bool:
        """
        Handle file upload workflow with injected GUI callbacks.

        This method implements the business logic for uploading files to flight controller
        while allowing the GUI to handle user interactions through callbacks.

        Args:
            selected_file: The configuration file being processed.
            ask_confirmation: Callback to ask user if they want to upload the file.
            show_error: Callback to show error messages to the user.
            show_warning: Callback to show warning messages to the user.
            get_progress_callback: Factory callback that creates and returns a progress callback
                                   only when actually needed (after all checks pass).

        Returns:
            bool: True if upload was successful or not needed, False if upload failed.

        """
        local_filename, remote_filename = self._local_filesystem.get_upload_local_and_remote_filenames(selected_file)
        if not local_filename or not remote_filename:
            return True  # No upload required

        if not self._local_filesystem.vehicle_configuration_file_exists(local_filename):
            error_msg = _("Local file {local_filename} does not exist")
            show_error(_("Will not upload any file"), error_msg.format(local_filename=local_filename))
            return False

        if self._flight_controller.master is None:
            show_warning(_("Will not upload any file"), _("No flight controller connection"))
            return False

        # Ask user for confirmation
        msg = _("Should the {local_filename} file be uploaded to the flight controller as {remote_filename}?")
        if not ask_confirmation(
            _("Upload file to FC"), msg.format(local_filename=local_filename, remote_filename=remote_filename)
        ):
            return True  # User declined upload

        # Get progress callback only after all checks passed
        progress_callback = get_progress_callback()

        # Attempt upload
        if not self._flight_controller.upload_file(local_filename, remote_filename, progress_callback):
            error_msg = _("Failed to upload {local_filename} to {remote_filename}, please upload it manually")
            show_error(_("Upload failed"), error_msg.format(local_filename=local_filename, remote_filename=remote_filename))
            return False

        return True

    def ensure_upload_preconditions(
        self,
        selected_params: dict[str, object],
        show_warning: ShowWarningCallback,
    ) -> bool:
        """Validate prerequisites before attempting to upload selected parameters."""
        if not selected_params:
            logging_warning(_("No parameter was selected for upload, will not upload any parameter"))
            show_warning(_("Will not upload any parameter"), _("No parameter was selected for upload"))
            return False

        if not self.fc_parameters:
            logging_warning(_("No parameters were yet downloaded from the flight controller, will not upload any parameter"))
            show_warning(_("Will not upload any parameter"), _("No flight controller connection"))
            return False

        return True

    def download_flight_controller_parameters(
        self, get_progress_callback: Optional[Callable[[], Optional[Callable]]] = None
    ) -> tuple[dict, dict]:
        """
        Download parameters from the flight controller.

        Args:
            get_progress_callback: Optional factory function that creates and returns a progress callback.

        Returns:
            tuple: (fc_parameters, param_default_values) downloaded from the flight controller.

        """
        # Get progress callback from factory if provided
        progress_callback = get_progress_callback() if get_progress_callback else None

        # Download all parameters from the flight controller
        fc_parameters, param_default_values = self._flight_controller.download_params(
            progress_callback,
            Path(self._local_filesystem.vehicle_dir) / "complete.param",
            Path(self._local_filesystem.vehicle_dir) / "00_default.param",
        )

        # Note: fc_parameters are already updated internally in the flight controller
        # via params_manager.download_params()

        if fc_parameters:
            # Update FC values in all current step ArduPilotParameter objects
            # Thread-safety: This assumes single-threaded execution during parameter upload.
            # The parameter editor UI is not designed for concurrent uploads, and the upload
            # workflow blocks the UI thread. If multi-threading is added in the future,
            # this loop would need synchronization (e.g., threading.Lock) to prevent
            # race conditions when modifying current_step_parameters during iteration.
            for param_name, param_obj in self.current_step_parameters.items():
                if param_name in fc_parameters:
                    param_obj.set_fc_value(fc_parameters[param_name])

        # Write default values to file if available
        if param_default_values:
            self._local_filesystem.write_param_default_values_to_file(param_default_values)

        return fc_parameters, param_default_values

    def upload_parameters_that_require_reset_workflow(  # pylint: disable=too-many-locals
        self,
        selected_params: dict,
        ask_confirmation: AskConfirmationCallback,
        show_error: ShowErrorCallback,
        progress_callback: Optional[Callable] = None,
    ) -> tuple[bool, set[str]]:
        """
        Upload parameters that require reset to the flight controller.

        Args:
            selected_params: Dictionary of parameters to upload.
            ask_confirmation: Callback to ask user for confirmation.
            show_error: Callback to show error messages.
            progress_callback: Optional callback for progress updates.

        Returns:
            tuple[bool, set[str]]: (reset_happened, uploaded_param_names) - reset_happened indicates if reset occurred,
                                   uploaded_param_names contains names of parameters that were uploaded.

        """
        reset_required = False
        reset_unsure_params = []
        uploaded_params = set()
        error_messages = []

        # Write each selected parameter to the flight controller
        for param_name, param in selected_params.items():
            try:
                if param_name not in self._flight_controller.fc_parameters or not is_within_tolerance(
                    self._flight_controller.fc_parameters[param_name], param.value
                ):
                    param_metadata = self._local_filesystem.doc_dict.get(param_name, None)
                    if param_metadata and param_metadata.get("RebootRequired", False):
                        success, error_msg = self._flight_controller.set_param(param_name, float(param.value))
                        if not success:
                            logging_error(_("Failed to set parameter %s: %s"), param_name, error_msg)
                            continue
                        uploaded_params.add(param_name)
                        if param_name in self._flight_controller.fc_parameters:
                            logging_info(
                                _("Parameter %s changed from %f to %f, reset required"),
                                param_name,
                                self._flight_controller.fc_parameters[param_name],
                                param.value,
                            )
                        else:
                            logging_info(_("Parameter %s changed to %f, reset required"), param_name, param.value)
                        reset_required = True
                    # Check if any of the selected parameters have a _TYPE, _EN, or _ENABLE suffix
                    elif param_name.endswith(("_TYPE", "_EN", "_ENABLE", "SID_AXIS")):
                        success, error_msg = self._flight_controller.set_param(param_name, float(param.value))
                        if not success:
                            logging_error(_("Failed to set parameter %s: %s"), param_name, error_msg)
                            continue
                        uploaded_params.add(param_name)
                        if param_name in self._flight_controller.fc_parameters:
                            logging_info(
                                _("Parameter %s changed from %f to %f, possible reset required"),
                                param_name,
                                self._flight_controller.fc_parameters[param_name],
                                param.value,
                            )
                        else:
                            logging_info(_("Parameter %s changed to %f, possible reset required"), param_name, param.value)
                        reset_unsure_params.append(param_name)
            except ValueError as e:
                error_msg = _("Failed to set parameter {param_name}: {e}").format(param_name=param_name, e=e)
                logging_error(error_msg)
                error_messages.append(error_msg)
        # Handle any errors with GUI dialogs
        for error_msg in error_messages:
            show_error(_("ArduPilot methodic configurator"), error_msg)

        self.reset_and_reconnect_workflow(reset_required, reset_unsure_params, ask_confirmation, show_error, progress_callback)

        reset_happened = reset_required or bool(reset_unsure_params)
        return reset_happened, uploaded_params

    def _calculate_reset_time(self) -> int:
        """
        Calculate the extra sleep time needed for reset based on boot delay parameters.

        Returns:
            int: Extra sleep time in seconds.

        """
        param_boot_delay = (
            self.current_step_parameters["BRD_BOOT_DELAY"].get_new_value()
            if "BRD_BOOT_DELAY" in self.current_step_parameters
            else 0.0
        )
        flightcontroller_boot_delay = self._flight_controller.fc_parameters.get("BRD_BOOT_DELAY", 0)
        return int(max(param_boot_delay, flightcontroller_boot_delay) // 1000 + 1)  # round up

    def _reset_and_reconnect_flight_controller(
        self, progress_callback: Optional[Callable] = None, sleep_time: Optional[int] = None
    ) -> Optional[str]:
        """
        Reset and reconnect to the flight controller.

        Args:
            progress_callback: Optional callback function for progress updates.
            sleep_time: Optional sleep time override. If None, calculates based on boot delay parameters.

        Returns:
            Optional[str]: Error message if reset failed, None if successful.

        """
        if sleep_time is None:
            sleep_time = self._calculate_reset_time()

        # Call reset_and_reconnect with a callback to update the reset progress bar and the progress message
        return self._flight_controller.reset_and_reconnect(progress_callback, None, int(sleep_time))

    def reset_and_reconnect_workflow(  # pylint: disable=too-many-arguments, too-many-positional-arguments
        self,
        fc_reset_required: bool,
        fc_reset_unsure: list[str],
        ask_confirmation: AskConfirmationCallback,
        show_error: ShowErrorCallback,
        progress_callback: Optional[Callable] = None,
    ) -> bool:
        """
        Complete workflow for resetting and reconnecting to flight controller with user interaction.

        This method orchestrates the complete reset process including:
        - Asking user confirmation for uncertain reset scenarios
        - Performing the actual reset and reconnection
        - Handling errors appropriately

        Args:
            fc_reset_required: Whether reset is definitively required
            fc_reset_unsure: List of parameters that potentially require reset
            ask_confirmation: Callback to ask user for confirmation
            show_error: Callback to show error messages
            progress_callback: Optional callback for progress updates

        Returns:
            bool: True if reset was performed (or not needed), False if reset failed

        """
        # Determine if reset is needed based on required flag and user confirmation for uncertain cases
        should_reset = fc_reset_required
        if not fc_reset_required and fc_reset_unsure:
            # Ask the user if they want to reset the ArduPilot
            param_list_str = ", ".join(fc_reset_unsure)
            msg = _("{param_list_str} parameter(s) potentially require a reset\nDo you want to reset the ArduPilot?")
            should_reset = ask_confirmation(_("Possible reset required"), msg.format(param_list_str=param_list_str))

        if should_reset:
            error_message = self._reset_and_reconnect_flight_controller(progress_callback)
            if error_message:
                show_error(_("ArduPilot methodic configurator"), error_message)
                return False
            return True

        return True  # No reset needed

    def _upload_parameters_to_fc(self, selected_params: dict, show_error: Callable[[str, str], None]) -> int:
        """
        Upload selected parameters to flight controller.

        Args:
            selected_params: Dictionary of parameters to upload.
            show_error: Callback to show error messages to the user.

        Returns:
            int: Number of changed parameters.

        """
        error_messages = []
        nr_changed = 0
        nr_unchanged = 0

        for param_name, param in selected_params.items():
            try:
                success, error_msg = self._flight_controller.set_param(param_name, param.value)
                if not success:
                    error_messages.append(
                        _("Failed to set parameter %(name)s: %(error)s") % {"name": param_name, "error": error_msg}
                    )
                    continue
                if param_name not in self._flight_controller.fc_parameters or not is_within_tolerance(
                    self._flight_controller.fc_parameters[param_name], param.value
                ):
                    if param_name in self._flight_controller.fc_parameters:
                        logging_info(
                            _("Parameter %s changed from %f to %f"),
                            param_name,
                            self._flight_controller.fc_parameters[param_name],
                            param.value,
                        )
                    else:
                        logging_info(
                            _("Parameter %s changed to %f"),
                            param_name,
                            param.value,
                        )
                    nr_changed += 1
                else:
                    logging_info(_("Parameter %s unchanged from %f"), param_name, param.value)
                    nr_unchanged += 1
            except ValueError as _e:
                error_msg = _("Failed to set parameter {param_name}: {_e}").format(**locals())
                logging_error(error_msg)
                error_messages.append(error_msg)

        # Handle any errors with GUI dialogs
        for error_msg in error_messages:
            show_error(_("ArduPilot methodic configurator"), error_msg)

        changed_msg = _("%d FC parameter(s) changed value") % nr_changed if nr_changed else ""
        unchanged_msg = (
            _("%d FC parameter(s) already had the value defined in this configuration step") % nr_unchanged
            if nr_unchanged
            else ""
        )
        msg = changed_msg + (", " if nr_changed and nr_unchanged else "") + unchanged_msg
        logging_info(msg)

        self._update_tuning_report()
        return nr_changed

    def _update_tuning_report(self) -> None:
        report_params = [
            "ATC_ACCEL_P_MAX",
            "ATC_ACCEL_R_MAX",
            "ATC_ACCEL_Y_MAX",
            "ATC_ANG_PIT_P",
            "ATC_ANG_RLL_P",
            "ATC_ANG_YAW_P",
            "ATC_RAT_PIT_FLTD",
            "ATC_RAT_PIT_FLTE",
            "ATC_RAT_PIT_FLTT",
            "ATC_RAT_RLL_FLTD",
            "ATC_RAT_RLL_FLTE",
            "ATC_RAT_RLL_FLTT",
            "ATC_RAT_YAW_FLTD",
            "ATC_RAT_YAW_FLTE",
            "ATC_RAT_YAW_FLTT",
            "ATC_RAT_PIT_D",
            "ATC_RAT_PIT_I",
            "ATC_RAT_PIT_P",
            "ATC_RAT_RLL_D",
            "ATC_RAT_RLL_I",
            "ATC_RAT_RLL_P",
            "ATC_RAT_YAW_D",
            "ATC_RAT_YAW_I",
            "ATC_RAT_YAW_P",
            "INS_ACCEL_FILTER",
            "INS_GYRO_FILTER",
        ]
        report_files = [
            "00_default.param",
            "11_initial_atc.param",
            "16_pid_adjustment.param",
            "23_quick_tune_results.param",
            "31_autotune_roll_results.param",
            "33_autotune_pitch_results.param",
            "35_autotune_yaw_results.param",
            "37_autotune_yawd_results.param",
            "39_autotune_roll_pitch_results.param",
        ]

        report_file_path = Path(getattr(self._local_filesystem, "vehicle_dir", ".")) / "tuning_report.csv"

        # Write a CSV with a header ("param", <list of files>) and one row per parameter.
        with open(report_file_path, "w", newline="", encoding="utf-8") as file:
            writer = csv_writer(file)
            writer.writerow(["param", *report_files])

            for param_name in report_params:
                row = [param_name]
                for param_file in report_files:
                    try:
                        if param_file == "00_default.param":
                            value = str(self._local_filesystem.param_default_dict[param_name].value)
                        else:
                            value = str(self._local_filesystem.file_parameters[param_file][param_name].value)
                    except (KeyError, ValueError):
                        # On any unexpected structure, leave the value empty (don't crash)
                        value = ""
                    row.append(value)
                writer.writerow(row)

    def upload_selected_params_workflow(  # pylint: disable=too-many-arguments, too-many-positional-arguments
        self,
        selected_params: dict,
        ask_confirmation: AskConfirmationCallback,
        ask_retry_cancel: AskRetryCancelCallback,
        show_error: ShowErrorCallback,
        get_reset_progress_callback: Optional[Callable[[], Optional[Callable]]] = None,
        get_download_progress_callback: Optional[Callable[[], Optional[Callable]]] = None,
    ) -> None:
        """
        Complete workflow for uploading selected parameters, including reset, upload, validation, and retry.

        Args:
            selected_params: Dictionary of parameters to upload.
            ask_confirmation: Callback to ask user for confirmation.
            ask_retry_cancel: Callback to ask user to retry or cancel on upload error.
            show_error: Callback to show error messages.
            get_reset_progress_callback: Optional factory function that creates and returns a reset progress callback.
            get_download_progress_callback: Optional factory function that creates and returns a download progress callback.

        """
        logging_info(
            _("Uploading %d selected %s parameters to flight controller..."),
            len(selected_params),
            self.current_file,
        )

        # Get progress callbacks from factories if provided
        progress_callback_for_reset = get_reset_progress_callback() if get_reset_progress_callback else None
        progress_callback_for_download = get_download_progress_callback() if get_download_progress_callback else None
        # Upload parameters that require reset
        reset_happened, already_uploaded_params = self.upload_parameters_that_require_reset_workflow(
            selected_params,
            ask_confirmation,
            show_error,
            progress_callback_for_reset,
        )

        # If reset happened, fc_parameters cache was cleared during disconnect/reconnect
        # Re-download parameters now so _upload_parameters_to_fc has valid cache for comparison
        if reset_happened:
            self.download_flight_controller_parameters(lambda: progress_callback_for_download)

        # Upload remaining parameters (excluding those already uploaded in reset workflow)
        remaining_params = {k: v for k, v in selected_params.items() if k not in already_uploaded_params}
        nr_changed = self._upload_parameters_to_fc(remaining_params, show_error)

        # Add count of already uploaded params to total changed count
        nr_changed += len(already_uploaded_params)

        if reset_happened or nr_changed > 0:
            self._at_least_one_changed = True

        if self._at_least_one_changed:
            # Re-download all parameters to validate
            # Note: Passing the callback directly, not the factory, since we already got it
            self.download_flight_controller_parameters(lambda: progress_callback_for_download)
            param_upload_error = self._validate_uploaded_parameters(selected_params)

            if param_upload_error:
                if ask_retry_cancel(
                    _("Parameter upload error"),
                    _("Failed to upload the following parameters to the flight controller:\n")
                    + f"{(', ').join(param_upload_error)}",
                ):
                    # Retry the entire workflow - pass the factories again, not the callbacks
                    self.upload_selected_params_workflow(
                        selected_params,
                        ask_confirmation,
                        ask_retry_cancel,
                        show_error,
                        get_reset_progress_callback,
                        get_download_progress_callback,
                    )
                # If not retrying, continue without success message
            else:
                logging_info(_("All parameters uploaded to the flight controller successfully"))

            self._export_fc_params_missing_or_different()

        self._write_current_file()
        self._at_least_one_changed = False

    def _validate_uploaded_parameters(self, selected_params: dict) -> list[str]:
        logging_info(_("Re-downloaded all parameters from the flight controller"))

        # Validate that the read parameters are the same as the ones in the current_file
        param_upload_error = []
        for param_name, param in selected_params.items():
            if (
                param_name in self._flight_controller.fc_parameters
                and param is not None
                and not is_within_tolerance(self._flight_controller.fc_parameters[param_name], float(param.value))
            ):
                logging_error(
                    _("Parameter %s upload to the flight controller failed. Expected: %f, Actual: %f"),
                    param_name,
                    param.value,
                    self._flight_controller.fc_parameters[param_name],
                )
                param_upload_error.append(param_name)
            if param_name not in self._flight_controller.fc_parameters:
                logging_error(
                    _("Parameter %s upload to the flight controller failed. Expected: %f, Actual: N/A"),
                    param_name,
                    param.value,
                )
                param_upload_error.append(param_name)
        return param_upload_error

    def _get_non_default_non_read_only_fc_params(self) -> ParDict:
        """
        Get flight controller parameters that are not default values and not read-only.

        Returns:
            ParDict: Dictionary of parameters that are writable and have non-default values.

        """
        # Create FC parameters dictionary
        fc_parameters = ParDict.from_fc_parameters(self._flight_controller.fc_parameters)

        # Early exit if no FC parameters available
        if len(fc_parameters) == 0:
            return fc_parameters

        # Remove default parameters from FC parameters if default file exists
        fc_parameters.remove_if_value_is_similar(self._local_filesystem.param_default_dict, is_within_tolerance)

        # Filter out read-only parameters efficiently - only check params that exist in fc_parameters
        readonly_params_to_remove = [
            param_name
            for param_name in fc_parameters
            if self._local_filesystem.doc_dict.get(param_name, {}).get("ReadOnly", False)
        ]
        for param_name in readonly_params_to_remove:
            del fc_parameters[param_name]

        return fc_parameters

    def _export_fc_params_missing_or_different_in_amc_files(self, fc_parameters: ParDict, last_filename: str) -> None:
        """
        Export flight controller parameters that are missing or different in AMC parameter files.

        This function creates a compound state of all parameters from AMC files (excluding defaults),
        compares them with FC parameters, and exports any parameters that are either missing from
        AMC files or have different values to a separate parameter file.

        Args:
            fc_parameters: Flight controller parameters to compare against.
            last_filename: Last configuration file to process (inclusive).

        """
        if not self._flight_controller.fc_parameters:
            return

        # Create the compounded state of all parameters stored in the AMC .param files
        compound = ParDict()
        first_config_step_filename = None
        for file_name, file_params in self._local_filesystem.file_parameters.items():
            if file_name != "00_default.param":
                if first_config_step_filename is None:
                    first_config_step_filename = file_name
                compound.append(file_params)
            if file_name == last_filename:
                break

        # Calculate parameters that only exist in fc_parameters or have a different value from compound
        params_missing_in_the_amc_param_files = fc_parameters.get_missing_or_different(compound, is_within_tolerance)

        boot_calibration_params_to_remove = [
            "INS_GYR1_CALTEMP",
            "INS_GYR2_CALTEMP",
            "INS_GYR3_CALTEMP",
            "INS_GYR2OFFS_X",
            "INS_GYR2OFFS_Y",
            "INS_GYR2OFFS_Z",
            "INS_GYR3OFFS_X",
            "INS_GYR3OFFS_Y",
            "INS_GYR3OFFS_Z",
            "INS_GYROFFS_X",
            "INS_GYROFFS_Y",
            "INS_GYROFFS_Z",
        ]
        for param_name in boot_calibration_params_to_remove:
            if param_name in params_missing_in_the_amc_param_files:
                del params_missing_in_the_amc_param_files[param_name]

        # Export to file if there are any missing/different parameters
        if params_missing_in_the_amc_param_files:
            # Generate filename based on the range of processed files
            first_name_without_ext = first_config_step_filename.rsplit(".", 1)[0] if first_config_step_filename else "unknown"
            # the last filename already has the .param extension
            filename = f"fc_params_missing_or_different_in_the_amc_param_files_{first_name_without_ext}_to_{last_filename}"
            self._local_filesystem.export_to_param(params_missing_in_the_amc_param_files, filename, annotate_doc=False)
            logging_info(
                _("Exported %d FC parameters missing or different in AMC files to %s"),
                len(params_missing_in_the_amc_param_files),
                filename,
            )
        else:
            logging_info(_("No FC parameters are missing or different from AMC parameter files"))

    def _export_fc_params_missing_or_different(self) -> None:
        non_default_non_read_only_fc_params = self._get_non_default_non_read_only_fc_params()

        last_config_step_filename = list(self._local_filesystem.file_parameters.keys())[-1]
        # Export FC parameters that are missing or different from AMC parameter files
        self._export_fc_params_missing_or_different_in_amc_files(non_default_non_read_only_fc_params, self.current_file)
        self._export_fc_params_missing_or_different_in_amc_files(
            non_default_non_read_only_fc_params, last_config_step_filename
        )

    def download_last_flight_log_workflow(
        self,
        ask_saveas_filename: Callable[[], str],
        show_error: Callable[[str, str], None],
        show_info: Callable[[str, str], None],
        progress_callback: Optional[Callable[[int, int], None]] = None,
    ) -> None:
        """
        Download the last flight log from the flight controller, using GUI callbacks for interaction.

        Args:
            ask_saveas_filename: Callback to show file dialog and get filename.
            show_error: Callback to show error messages.
            show_info: Callback to show info messages.
            progress_callback: Progress bar update callback.
            run_in_thread: Callback to run the download in a thread (optional).

        """
        if self._flight_controller.master is None:
            show_error(_("Error"), _("No flight controller connected"))
            return

        if not self.is_mavftp_supported:
            show_error(_("Error"), _("MAVFTP is not supported by the flight controller"))
            return

        filename = ask_saveas_filename()
        if not filename:
            return

        success = self._flight_controller.download_last_flight_log(filename, progress_callback)
        if success:
            show_info(_("Success"), _("Flight log downloaded successfully to:\n%s") % filename)
        else:
            show_error(_("Error"), _("Failed to download flight log. Check the console for details."))

    def is_configuration_step_optional(self, file_name: Optional[str] = None, threshold_pct: int = 20) -> bool:
        """
        Check if the configuration step for the given file is optional.

        Args:
            file_name: Name of the configuration file to check, defaults to self.current_file.
            threshold_pct: Threshold percentage below which the step is considered optional.

        Returns:
            bool: True if the configuration step is optional, False if mandatory.

        """
        if file_name is None:
            file_name = self.current_file

        # Check if the configuration step for the given file is optional
        mandatory_text, _mandatory_url = self._local_filesystem.get_documentation_text_and_url(file_name, "mandatory")
        # Extract percentage from mandatory_text like "80% mandatory (20% optional)"
        percentage = 0
        if mandatory_text:
            try:
                percentage = int(mandatory_text.split("%")[0])
            except (ValueError, IndexError):
                percentage = 0

        return percentage <= threshold_pct

    def get_next_non_optional_file(self, current_file: Optional[str] = None) -> Optional[str]:
        """
        Get the next non-optional configuration file in sequence.

        Args:
            current_file: The current parameter file being processed, defaults to self.current_file.

        Returns:
            Optional[str]: Next non-optional file name, or None if at the end.

        """
        files = list(self._local_filesystem.file_parameters.keys())
        if not files:
            return None

        if current_file is None:
            current_file = self.current_file

        try:
            next_file_index = files.index(current_file) + 1

            # Skip files with mandatory_level == 0 (completely optional)
            while next_file_index < len(files):
                next_file = files[next_file_index]
                if not self.is_configuration_step_optional(next_file, threshold_pct=0):
                    return next_file
                next_file_index += 1

            # If we've reached the end, return None to indicate completion
            return None

        except ValueError:
            # Current file not found in list
            return None

    def _generate_parameter_summary(self) -> dict[str, ParDict]:
        """
        Generate categorized parameter summaries for the end of configuration workflow.

        Returns:
            dict: Dictionary with parameter categories and their ParDict objects.
                Keys: "complete", "read_only", "calibrations", "non_calibrations"

        """
        # Get annotated FC parameters
        annotated_fc_parameters = self._local_filesystem.annotate_intermediate_comments_to_param_dict(
            self._flight_controller.fc_parameters
        )
        if not annotated_fc_parameters:
            return {}

        # Categorize parameters using filesystem logic
        categorized = self._local_filesystem.categorize_parameters(annotated_fc_parameters)
        if not categorized or len(categorized) != 3:
            # Return empty dict if categorization fails or returns empty tuple
            return {}

        non_default__read_only_params, non_default__writable_calibrations, non_default__writable_non_calibrations = categorized

        return {
            "complete": annotated_fc_parameters,
            "read_only": non_default__read_only_params,
            "calibrations": non_default__writable_calibrations,
            "non_calibrations": non_default__writable_non_calibrations,
        }

    def _get_parameter_summary_msg(self, parameter_summary: dict[str, ParDict]) -> str:
        """
        Get formatted parameter summary message for end-of-configuration display.

        Args:
            parameter_summary: Dictionary with parameter categories from generate_parameter_summary().

        Returns:
            str: Formatted message summarizing parameter categorization and counts.

        """
        if not parameter_summary:
            return _("No parameters available for summary.")

        # Calculate statistics
        nr_total_params = len(parameter_summary.get("complete", {}))
        nr_non_default__read_only_params = len(parameter_summary.get("read_only", {}))
        nr_non_default__writable_calibrations = len(parameter_summary.get("calibrations", {}))
        nr_non_default__writable_non_calibrations = len(parameter_summary.get("non_calibrations", {}))
        nr_unchanged_params = (
            nr_total_params
            - nr_non_default__read_only_params
            - nr_non_default__writable_calibrations
            - nr_non_default__writable_non_calibrations
        )

        # Format the summary message
        summary_message = _(
            "Methodic configuration of {nr_total_params} parameters complete:\n\n"
            "{nr_unchanged_params} kept their default value\n\n"
            "{nr_non_default__read_only_params} non-default read-only parameters - "
            "ignore these, you can not change them\n\n"
            "{nr_non_default__writable_calibrations} non-default writable sensor-calibrations - "
            "non-reusable between vehicles\n\n"
            "{nr_non_default__writable_non_calibrations} non-default writable non-sensor-calibrations - "
            "these can be reused between similar vehicles"
        )

        return summary_message.format(
            nr_total_params=nr_total_params,
            nr_unchanged_params=nr_unchanged_params,
            nr_non_default__read_only_params=nr_non_default__read_only_params,
            nr_non_default__writable_calibrations=nr_non_default__writable_calibrations,
            nr_non_default__writable_non_calibrations=nr_non_default__writable_non_calibrations,
        )

    def write_summary_files_workflow(
        self,
        show_info: ShowInfoCallback,
        ask_confirmation: AskConfirmationCallback,
    ) -> bool:
        """
        Complete summary file writing workflow with user interaction via callbacks.

        This method orchestrates the entire summary file writing process, including:
        - Generating parameter summaries
        - Displaying summary information to user
        - Writing individual summary files with user confirmation
        - Creating zip file with user confirmation

        Args:
            show_info: Callback function for showing information messages.
            ask_confirmation: Callback function for asking user confirmation.

        Returns:
            bool: True if workflow completed successfully, False if no parameters available.

        """
        # Check if we have flight controller parameters
        if not self.fc_parameters:
            return False

        # Generate parameter summary using business logic
        parameter_summary = self._generate_parameter_summary()
        summary_message = self._get_parameter_summary_msg(parameter_summary)

        # Display summary information to user
        show_info(_("Last parameter file processed"), summary_message)

        # Extract categorized parameters
        complete_params = parameter_summary["complete"]
        read_only_params = parameter_summary["read_only"]
        calibration_params = parameter_summary["calibrations"]
        non_calibration_params = parameter_summary["non_calibrations"]

        # Write individual summary files
        wrote_complete = self._write_single_summary_file_workflow(
            complete_params, "complete.param", annotate_doc=False, ask_confirmation=ask_confirmation
        )
        wrote_read_only = self._write_single_summary_file_workflow(
            read_only_params, "non-default_read-only.param", annotate_doc=False, ask_confirmation=ask_confirmation
        )
        wrote_calibrations = self._write_single_summary_file_workflow(
            calibration_params,
            "non-default_writable_calibrations.param",
            annotate_doc=False,
            ask_confirmation=ask_confirmation,
        )
        wrote_non_calibrations = self._write_single_summary_file_workflow(
            non_calibration_params,
            "non-default_writable_non-calibrations.param",
            annotate_doc=False,
            ask_confirmation=ask_confirmation,
        )

        # Create list of files for zipping
        files_to_zip = [
            (wrote_complete, "complete.param"),
            (wrote_read_only, "non-default_read-only.param"),
            (wrote_calibrations, "non-default_writable_calibrations.param"),
            (wrote_non_calibrations, "non-default_writable_non-calibrations.param"),
        ]

        # Write zip file with user confirmation
        self._write_zip_file_workflow(files_to_zip, show_info, ask_confirmation)

        return True

    def _write_single_summary_file_workflow(
        self,
        param_dict: ParDict,
        filename: str,
        annotate_doc: bool,
        ask_confirmation: AskConfirmationCallback,
    ) -> bool:
        """
        Write a single summary file with user confirmation workflow.

        Args:
            param_dict: Parameter dictionary to write.
            filename: Target filename.
            annotate_doc: Whether to annotate with documentation.
            ask_confirmation: Callback function for asking user confirmation.

        Returns:
            bool: True if file was written, False otherwise.

        """
        # Check if we should write the file
        should_write_file = True  # Default to writing new files

        if not param_dict:
            return False

        # If file exists, ask user for confirmation
        if self._local_filesystem.vehicle_configuration_file_exists(filename):
            msg = _("{} file already exists.\nDo you want to overwrite it?")
            should_write_file = ask_confirmation(_("Overwrite existing file"), msg.format(filename))

        # Write the file using if confirmed and has parameters
        if should_write_file:
            self._local_filesystem.export_to_param(param_dict, filename, annotate_doc)
            logging_info(_("Summary file %s written"), filename)

        return should_write_file

    def _write_zip_file_workflow(
        self,
        files_to_zip: list[tuple[bool, str]],
        show_info: ShowInfoCallback,
        ask_confirmation: AskConfirmationCallback,
    ) -> bool:
        """
        Write zip file with user confirmation workflow.

        Args:
            files_to_zip: List of (should_include, filename) tuples.
            show_info: Callback function for showing information messages.
            ask_confirmation: Callback function for asking user confirmation.

        Returns:
            bool: True if file was written, False otherwise.

        """
        # Check if we should write the zip file
        should_write_file = True  # Default to writing new files

        # If file exists, ask user for confirmation
        if self._local_filesystem.zip_file_exists():
            zip_file_path = self._local_filesystem.zip_file_path()
            msg = _("{} file already exists.\nDo you want to overwrite it?")
            should_write_file = ask_confirmation(_("Overwrite existing file"), msg.format(zip_file_path))

        if should_write_file:
            self._local_filesystem.zip_files(files_to_zip)
            zip_file_path = self._local_filesystem.zip_file_path()
            msg = _(
                "All relevant files have been zipped into the \n"
                "{zip_file_path} file.\n\nYou can now upload this file to the ArduPilot Methodic\n"
                "Configuration Blog post on discuss.ardupilot.org."
            )
            show_info(_("Parameter files zipped"), msg.format(zip_file_path=zip_file_path))

        return should_write_file

    def create_forum_help_zip_workflow(
        self,
        show_info: ShowInfoCallback,
        show_error: ShowErrorCallback,
    ) -> bool:
        """
        Complete workflow for creating forum help zip file (< 100 KiB) with user interaction.

        This method orchestrates the complete forum help zip creation process including:
        - Creating the zip file with relevant files and small enough for forum upload
        - Displaying notification with file location and instructions
        - Opening the ArduPilot forum in browser

        Args:
            show_info: Callback to show information messages to the user.
            show_error: Callback to show error messages to the user.

        Returns:
            bool: True if workflow completed successfully, False if an error occurred.

        """
        try:
            vehicle_dir = Path(self._local_filesystem.vehicle_dir)

            # Verify at least one intermediate parameter file exists in file_parameters
            if not self._local_filesystem.file_parameters:
                msg = f"No intermediate parameter files found in {vehicle_dir}"
                raise FileNotFoundError(msg)

            # Generate zip filename with UTC timestamp
            now_utc = datetime.now(timezone.utc)
            timestamp = now_utc.strftime("%Y%m%d_%H%M%S")
            vehicle_name = vehicle_dir.name
            zip_filename = f"{vehicle_name}_{timestamp}UTC.zip"

            # Build list of additional files to include (beyond what zip_files automatically includes)
            # The zip_files method already includes all files from file_parameters and common files
            # like vehicle.jpg, vehicle_components.json, last_uploaded_filename.txt, tempcal files, etc.
            # We just need to specify any extra files as empty list since zip_files handles them
            files_to_zip: list[tuple[bool, str]] = []

            # Use the filesystem's zip_files method with custom filename and without apm.pdef.xml
            # apm.pdef.xml is excluded to keep the zip file size small for forum upload
            # zip_files returns the full path to the created zip file
            zip_path = self._local_filesystem.zip_files(files_to_zip, zip_file_name=zip_filename, include_apm_pdef=False)

            logging_info("Created forum help zip file: %s", zip_path)

            webbrowser_open_url("https://discuss.ardupilot.org")

            # Show success notification to user
            show_info(
                _("Zip file successfully created"),
                _(
                    "Zipped all vehicle configuration files into the file \n"
                    "{zip_fullpath}\n\n"
                    "Upload this file to the ArduPilot support forum to receive help\n"
                    "from the community.\n\n"
                    "If you have a problem during flight, also upload one single .bin file\n"
                    "from a problematic flight to a file sharing service and post a link\n"
                    "to it in the ArduPilot support forum."
                ).format(zip_fullpath=str(zip_path)),
            )

            return True

        except FileNotFoundError as e:
            error_msg = _("Failed to create zip file: {error}").format(error=str(e))
            logging_error(error_msg)
            show_error(_("Zip file creation failed"), error_msg)
            return False

        except (PermissionError, OSError) as e:
            error_msg = _("Failed to create zip file due to file system error: {error}").format(error=str(e))
            logging_error(error_msg)
            show_error(_("Zip file creation failed"), error_msg)
            return False

    # frontend_tkinter_parameter_editor.py API end

    # frontend_tkinter_parameter_editor_table.py API start

    def _repopulate_configuration_step_parameters(
        self,
    ) -> tuple[list[tuple[str, str]], list[tuple[str, str]]]:
        """
        Process the configuration step for the current file and update the self.current_step_parameters.

        Returns:
            tuple: (ui_errors, ui_infos)

        """
        # Reset tracking sets when navigating to new file
        self._added_parameters.clear()
        self._deleted_parameters.clear()

        # Process configuration step and get operations to apply
        self.current_step_parameters, ui_errors, ui_infos, duplicates_to_remove, renames_to_apply, derived_params = (
            self._config_step_processor.process_configuration_step(self.current_file, self.fc_parameters)
        )

        # Apply derived parameters to domain model using specialized setters
        for param_name, derived_par in derived_params.items():
            if param_name in self.current_step_parameters:
                # Update existing forced/derived parameter with new value using dedicated setter
                # The setter methods will raise ValueError for invalid parameters (not forced/derived, readonly, etc.)
                try:
                    self.current_step_parameters[param_name].set_forced_or_derived_value(float(derived_par.value))
                    if derived_par.comment:
                        self.current_step_parameters[param_name].set_forced_or_derived_change_reason(derived_par.comment)
                except (ValueError, TypeError) as e:
                    logging_error(
                        _("Failed to apply derived parameter %s: %s"),
                        param_name,
                        str(e),
                    )
            else:
                # Parameter in derived_params but not in self.parameters - this is unexpected
                logging_error(
                    _("Derived parameter %s not found in current parameters, skipping"),
                    param_name,
                )

        # Apply rename operations to domain model using add/delete tracking
        for old_name in duplicates_to_remove:
            # Mark duplicate as deleted
            if old_name in self._local_filesystem.file_parameters.get(self.current_file, ParDict()):
                self._deleted_parameters.add(old_name)
            # Remove from domain model
            if old_name in self.current_step_parameters:
                del self.current_step_parameters[old_name]

        for old_name, new_name in renames_to_apply:
            # Get the parameter value from the original file
            original_params = self._local_filesystem.file_parameters.get(self.current_file, ParDict())
            if old_name in original_params:
                # Mark old parameter as deleted
                self._deleted_parameters.add(old_name)

                # Create new parameter with renamed name
                old_par = original_params[old_name]
                self.current_step_parameters[new_name] = self._config_step_processor.create_ardupilot_parameter(
                    new_name, old_par, self.current_file, self.fc_parameters
                )

                # Mark new parameter as added
                self._added_parameters.add(new_name)

                # Remove old parameter from domain model
                if old_name in self.current_step_parameters:
                    del self.current_step_parameters[old_name]

        return ui_errors, ui_infos

    def update_parameter_value(
        self,
        param_name: str,
        new_value: str,
        *,
        include_range_check: bool = True,
    ) -> ParameterValueUpdateResult:
        """Update a parameter value and describe the outcome for the UI layer."""
        param = self.current_step_parameters.get(param_name)
        if param is None:
            return ParameterValueUpdateResult(
                ParameterValueUpdateStatus.ERROR,
                title=_("Parameter not found"),
                message=_("Parameter {param_name} could not be located.").format(param_name=param_name),
            )

        try:
            param.set_new_value(new_value, ignore_out_of_range=not include_range_check)
            return ParameterValueUpdateResult(ParameterValueUpdateStatus.UPDATED)
        except ParameterUnchangedError:
            return ParameterValueUpdateResult(ParameterValueUpdateStatus.UNCHANGED)
        except ParameterOutOfRangeError as exc:
            if include_range_check:
                return ParameterValueUpdateResult(
                    ParameterValueUpdateStatus.CONFIRM_OUT_OF_RANGE,
                    title=_("Out-of-range value"),
                    message=str(exc),
                )
            logging_exception(_("Parameter %s out of range: %s"), param_name, exc)
            return ParameterValueUpdateResult(
                ParameterValueUpdateStatus.ERROR,
                title=_("Out-of-range value"),
                message=str(exc),
            )
        except (ValueError, TypeError) as exc:
            logging_exception(_("Invalid value for %s: %s"), param_name, exc)
            return ParameterValueUpdateResult(
                ParameterValueUpdateStatus.ERROR,
                title=_("Invalid value"),
                message=str(exc),
            )

    def get_different_parameters(self) -> dict[str, ArduPilotParameter]:
        """
        Get parameters that are different from FC values or missing from FC.

        Returns:
            Dictionary of parameters that are different from FC

        """
        return self._config_step_processor.filter_different_parameters(self.current_step_parameters)

    def delete_parameter_from_current_file(self, param_name: str) -> None:
        """
        Delete a parameter from the current file parameters.

        Args:
            param_name: The name of the parameter to delete

        """
        # If parameter was in original file, mark as deleted
        if param_name in self._local_filesystem.file_parameters.get(self.current_file, ParDict()):
            self._deleted_parameters.add(param_name)

        # If it was previously added in this session, remove from added set
        self._added_parameters.discard(param_name)

        # Remove from runtime state
        if param_name in self.current_step_parameters:
            del self.current_step_parameters[param_name]

    def get_possible_add_param_names(self) -> list[str]:
        """Return a sorted list of possible parameter names to add, or raise OperationNotPossibleError if not possible."""
        param_dict = self._local_filesystem.doc_dict or self.fc_parameters
        if not param_dict:
            raise OperationNotPossibleError(
                _("No apm.pdef.xml file and no FC connected. Not possible autocomplete parameter names.")
            )

        # Build set of currently active parameters from domain model
        active_params = set(self.current_step_parameters.keys())

        # Find parameters that aren't currently active
        possible_add_param_names = [param_name for param_name in param_dict if param_name not in active_params]
        possible_add_param_names.sort()
        return possible_add_param_names

    def add_parameter_to_current_file(self, param_name: str) -> bool:
        """
        Add a parameter to the current file.

        Returns True if the parameter was added, False if not.

        Raises InvalidParameterNameError or OperationNotPossibleError if not possible.
        """
        param_name = param_name.upper()
        if not param_name:
            raise InvalidParameterNameError(_("Parameter name can not be empty."))

        # Check if parameter already exists (in original file, added, or not deleted)
        original_file_params = self._local_filesystem.file_parameters.get(self.current_file, ParDict())
        is_in_original = param_name in original_file_params
        is_already_added = param_name in self._added_parameters
        is_deleted = param_name in self._deleted_parameters

        if (is_in_original and not is_deleted) or is_already_added:
            raise InvalidParameterNameError(_("Parameter already exists, edit it instead"))

        fc_parameters = self.fc_parameters
        if fc_parameters:
            if param_name in fc_parameters:
                # Create the parameter in domain model
                par = Par(fc_parameters[param_name], "")
                self.current_step_parameters[param_name] = self._config_step_processor.create_ardupilot_parameter(
                    param_name, par, self.current_file, fc_parameters
                )

                # Track addition
                if not is_in_original:
                    self._added_parameters.add(param_name)
                # If was previously deleted, remove from deleted set
                self._deleted_parameters.discard(param_name)

                return True
            raise InvalidParameterNameError(_("Parameter name not found in the flight controller."))

        if self._local_filesystem.doc_dict:
            if param_name in self._local_filesystem.doc_dict:
                # Create the parameter in domain model
                par = Par(self._local_filesystem.param_default_dict.get(param_name, Par(0, "")).value, "")
                self.current_step_parameters[param_name] = self._config_step_processor.create_ardupilot_parameter(
                    param_name, par, self.current_file, fc_parameters
                )

                # Track addition
                if not is_in_original:
                    self._added_parameters.add(param_name)
                # If was previously deleted, remove from deleted set
                self._deleted_parameters.discard(param_name)

                return True
            raise InvalidParameterNameError(
                _("'{param_name}' not found in the apm.pdef.xml file.").format(param_name=param_name)
            )

        if not fc_parameters and not self._local_filesystem.doc_dict:
            raise OperationNotPossibleError(
                _("Can not add parameter when no FC is connected and no apm.pdef.xml file exists.")
            )
        return False

    def should_display_bitmask_parameter_editor_usage(self, param_name: str) -> bool:
        return self.current_step_parameters[param_name].is_editable and self.current_step_parameters[param_name].is_bitmask

    def get_parameters_as_par_dict(self, param_names: Optional[list[str]] = None) -> ParDict:
        """
        Extract Par objects from ArduPilotParameter domain models.

        This method converts the domain model objects to data transfer objects (Par)
        that can be used for file operations or flight controller uploads.

        Args:
            param_names: Optional list of parameter names to include.
                        If None, includes all parameters.

        Returns:
            ParDict containing Par objects with current values and change reasons

        """
        if param_names is None:
            param_names = list(self.current_step_parameters.keys())

        return ParDict(
            {
                name: Par(self.current_step_parameters[name].get_new_value(), self.current_step_parameters[name].change_reason)
                for name in param_names
                if name in self.current_step_parameters
            }
        )

    def _has_unsaved_changes(self) -> bool:
        """
        Check if any changes have been made that need to be saved.

        This includes:
        - User edits to parameter values
        - Derived parameter changes (tracked via is_dirty)
        - Forced parameter changes (tracked via is_dirty)
        - Connection renaming changes (tracked via _added_parameters and _deleted_parameters)
        - Parameter additions
        - Parameter deletions

        Returns:
            True if there are unsaved changes, False otherwise

        """
        # Check for structural changes (additions/deletions, including from renames)
        if self._added_parameters or self._deleted_parameters:
            return True

        # Check individual parameter edits (value or comment changes)
        return any(param.is_dirty for param in self.current_step_parameters.values())

    def get_last_configuration_step_number(self) -> Optional[int]:
        """
        Get the last configuration step number by scanning actual .param files on disk.

        This method gets the highest step number from all .param files in the vehicle directory to
        ensure that if users have manually added or deleted files, the progress bar reflects the actual
        configuration files available on disk, not a possibly outdated and/or incomplete JSON configuration.

        Returns:
            The highest step number found in the .param files, plus 1 (for consistency
            with how the progress bar uses this value), or None if no files found.

        """
        # Always rely on actual files on disk, not configuration_phases which might be outdated
        if self._local_filesystem.configuration_phases and self._local_filesystem.file_parameters:
            # Get all filenames and extract their step numbers
            max_step_nr = 0
            for filename in self._local_filesystem.file_parameters:
                # Extract the first two characters as the step number
                if len(filename) >= 2 and filename[:2].isdigit():
                    step_nr = int(filename[:2])
                    max_step_nr = max(max_step_nr, step_nr)

            # Return max_step_nr + 1 for consistency with progress bar expectations
            if max_step_nr > 0:
                return max_step_nr + 1

        return None

    def get_sorted_phases_with_end_and_weight(self, last_step_nr: int) -> dict[str, PhaseData]:
        return self._local_filesystem.get_sorted_phases_with_end_and_weight(last_step_nr)

    def get_vehicle_directory(self) -> str:
        return self._local_filesystem.vehicle_dir

    def parameter_files(self) -> list[str]:
        return list(self._local_filesystem.file_parameters.keys())

    def parameter_documentation_available(self) -> bool:
        return bool(self._local_filesystem.doc_dict)

    def configuration_phases(self) -> dict[str, PhaseData]:
        return self._local_filesystem.configuration_phases

    def _write_current_file(self) -> None:
        self._local_filesystem.write_last_uploaded_filename(self.current_file)

    def _export_current_file(self, annotate_doc: bool) -> None:
        # Convert domain model parameters to Par objects for export
        export_params = self.get_parameters_as_par_dict()

        # Export to file
        self._local_filesystem.export_to_param(export_params, self.current_file, annotate_doc)

        # Update the filesystem's file_parameters to match what was saved
        self._local_filesystem.file_parameters[self.current_file] = export_params

        self._added_parameters.clear()
        self._deleted_parameters.clear()
        # copy parameters new values to their _values_on_file
        for param in self.current_step_parameters.values():
            param.copy_new_value_to_file()

    def open_documentation_in_browser(self, filename: str) -> None:
        _blog_text, blog_url = self.get_documentation_text_and_url("blog", filename)
        _wiki_text, wiki_url = self.get_documentation_text_and_url("wiki", filename)
        _external_tool_text, external_tool_url = self.get_documentation_text_and_url("external_tool", filename)
        if wiki_url:
            webbrowser_open_url(url=wiki_url, new=0, autoraise=False)
        if external_tool_url:
            webbrowser_open_url(url=external_tool_url, new=0, autoraise=False)
        if blog_url:
            webbrowser_open_url(url=blog_url, new=0, autoraise=True)

    # frontend_tkinter_parameter_editor_table.py API end

    # frontend_tkinter_parameter_editor_documentation_frame.py API start
    def get_documentation_text_and_url(self, key: str, filename: Optional[str] = None) -> tuple[str, str]:
        if filename is None:
            filename = self.current_file
        return self._local_filesystem.get_documentation_text_and_url(filename, key)

    def get_why_why_now_tooltip(self) -> str:
        why_tooltip_text = self._local_filesystem.get_seq_tooltip_text(self.current_file, "why")
        why_now_tooltip_text = self._local_filesystem.get_seq_tooltip_text(self.current_file, "why_now")
        tooltip_text = ""
        if why_tooltip_text:
            tooltip_text += _("Why: ") + _(why_tooltip_text) + "\n"
        if why_now_tooltip_text:
            tooltip_text += _("Why now: ") + _(why_now_tooltip_text)
        return tooltip_text

    def get_documentation_frame_title(self) -> str:
        if self.current_file:
            title = _("{current_file} Documentation")
            return title.format(current_file=self.current_file)
        return _("Documentation")

    def parse_mandatory_level_percentage(self, text: str) -> tuple[int, str]:
        """
        Parse and validate the mandatory level percentage from text.

        Args:
            text: The text containing the mandatory level information

        Returns:
            tuple: (percentage_value, tooltip_text)
                   percentage_value: 0-100 for valid percentage, 0 for invalid
                   tooltip_text: Formatted tooltip text

        """
        current_file = self.current_file or ""
        try:
            # Extract up to 3 digits from the start of the mandatory text
            percentage = int("".join([c for c in text[:3] if c.isdigit()]))
            if 0 <= percentage <= 100:
                tooltip = _("This configuration step ({current_file} intermediate parameter file) is {percentage}% mandatory")
                return percentage, tooltip.format(current_file=current_file, percentage=percentage)
            raise ValueError
        except ValueError:
            tooltip = _("Mandatory level not available for this configuration step ({current_file})")
            return 0, tooltip.format(current_file=current_file)

    # frontend_tkinter_parameter_editor_documentation_frame.py API end

    # plugin API begin

    def get_plugin(self, filename: str) -> Optional[dict]:
        return self._local_filesystem.get_plugin(filename)

    def create_plugin_data_model(self, plugin_name: str) -> Optional[object]:
        """
        Create and return a data model for the specified plugin.

        Args:
            plugin_name: The name of the plugin to create a data model for

        Returns:
            The data model instance, or None if plugin not supported or requirements not met

        """
        if plugin_name == PLUGIN_MOTOR_TEST:
            if not self.is_fc_connected:
                return None
            return MotorTestDataModel(self._flight_controller, self._local_filesystem)
        if plugin_name == PLUGIN_BATTERY_MONITOR:
            if not self.is_fc_connected:
                return None
            return BatteryMonitorDataModel(self._flight_controller, self)
        # Add more plugins here in the future
        return None

    # plugin API end
