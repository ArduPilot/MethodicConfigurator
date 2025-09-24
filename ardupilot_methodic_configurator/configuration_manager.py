"""
The business logic for the configuration (parameter editing and uploading).

Contains state information but no GUI code.
Aggregates flight controller and filesystem access in a single interface.
Uses exceptions for error handling, the GUI layer will catch and display them.

This file is part of Ardupilot methodic configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2025 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

from csv import writer as csv_writer
from logging import error as logging_error
from logging import info as logging_info
from pathlib import Path
from typing import Callable, Optional

from ardupilot_methodic_configurator import _
from ardupilot_methodic_configurator.backend_filesystem import LocalFilesystem
from ardupilot_methodic_configurator.backend_flightcontroller import FlightController
from ardupilot_methodic_configurator.backend_internet import download_file_from_url
from ardupilot_methodic_configurator.data_model_par_dict import Par, ParDict, is_within_tolerance
from ardupilot_methodic_configurator.tempcal_imu import IMUfit

# Type aliases for callback functions used in workflow methods
AskConfirmationCallback = Callable[[str, str], bool]  # (title, message) -> bool
SelectFileCallback = Callable[[str, list[str]], Optional[str]]  # (title, filetypes) -> Optional[filename]
ShowWarningCallback = Callable[[str, str], None]  # (title, message) -> None
ShowErrorCallback = Callable[[str, str], None]  # (title, message) -> None
ShowInfoCallback = Callable[[str, str], None]  # (title, message) -> None

# pylint: disable=too-many-lines


class ConfigurationManager:
    """
    Manages configuration state, including flight controller and filesystem access.

    This class aggregates the flight controller and filesystem access to provide a unified interface
    for managing configuration state. It holds references to the flight controller and filesystem,
    and provides methods to interact with them.
    """

    def __init__(self, current_file: str, flight_controller: FlightController, filesystem: LocalFilesystem) -> None:
        self.current_file = current_file
        self.flight_controller = flight_controller
        self.filesystem = filesystem

    @property
    def connected_vehicle_type(self) -> str:
        return (
            getattr(self.flight_controller.info, "vehicle_type", "")
            if hasattr(self.flight_controller, "info") and self.flight_controller.info is not None
            else ""
        )

    @property
    def is_fc_connected(self) -> bool:
        return self.flight_controller.master is not None

    @property
    def fc_parameters(self) -> dict[str, float]:
        return (
            self.flight_controller.fc_parameters
            if hasattr(self.flight_controller, "fc_parameters") and self.flight_controller.fc_parameters is not None
            else {}
        )

    @property
    def is_mavftp_supported(self) -> bool:
        return (
            getattr(self.flight_controller.info, "is_mavftp_supported", False)
            if hasattr(self.flight_controller, "info") and self.flight_controller.info is not None
            else False
        )

    def handle_imu_temperature_calibration_workflow(  # pylint: disable=too-many-arguments, too-many-positional-arguments
        self,
        selected_file: str,
        ask_user_confirmation: AskConfirmationCallback,
        select_file: SelectFileCallback,
        show_warning: ShowWarningCallback,
        show_error: ShowErrorCallback,
        progress_callback: Optional[Callable] = None,
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
            progress_callback: Optional callback function for progress updates.

        Returns:
            bool: True if calibration was performed successfully, False otherwise.

        """
        # Check if IMU temperature calibration should be offered for this file
        tempcal_imu_result_param_filename, tempcal_imu_result_param_fullpath = self.filesystem.tempcal_imu_result_param_tuple()
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

        # Perform the actual IMU temperature calibration
        IMUfit(
            logfile=log_file,
            outfile=tempcal_imu_result_param_fullpath,
            no_graph=False,
            log_parm=False,
            online=False,
            tclr=False,
            figpath=self.filesystem.vehicle_dir,
            progress_callback=progress_callback,
        )

        try:
            # Reload parameter files after calibration
            self.filesystem.file_parameters = self.filesystem.read_params_from_files()
            return True
        except SystemExit as exp:
            show_error(_("Fatal error reading parameter files"), f"{exp}")
            raise

    def should_copy_fc_values_to_file(self, selected_file: str) -> tuple[bool, Optional[dict], Optional[str]]:
        """
        Check if flight controller values should be copied to the specified file.

        Args:
            selected_file: The file to check for copying requirements.

        Returns:
            tuple: (should_copy, relevant_fc_params, auto_changed_by) - should_copy indicates if copy is needed,
                   relevant_fc_params contains the parameters to copy if needed,
                   auto_changed_by contains the tool name that requires external changes.

        """
        auto_changed_by = self.filesystem.auto_changed_by(selected_file)
        if auto_changed_by and self.flight_controller.fc_parameters:
            # Filter relevant FC parameters for this file
            relevant_fc_params = {
                key: value
                for key, value in self.flight_controller.fc_parameters.items()
                if key in self.filesystem.file_parameters[selected_file]
            }
            return True, relevant_fc_params, auto_changed_by
        return False, None, auto_changed_by

    def copy_fc_values_to_file(self, selected_file: str, relevant_fc_params: dict) -> bool:
        """
        Copy FC values to the specified file.

        Args:
            selected_file: The configuration file to update.
            relevant_fc_params: The parameters to copy.

        Returns:
            bool: True if parameters were copied successfully.

        """
        params_copied = self.filesystem.copy_fc_values_to_file(selected_file, relevant_fc_params)
        return bool(params_copied)

    def get_file_jump_options(self, selected_file: str) -> dict[str, str]:
        """
        Get available file jump options for the selected file.

        Args:
            selected_file: The current configuration file.

        Returns:
            dict: Dictionary mapping destination files to their messages.

        """
        return self.filesystem.jump_possible(selected_file)

    def should_download_file_from_url_workflow(
        self,
        selected_file: str,
        ask_confirmation: Callable[[str, str], bool],
        show_error: Callable[[str, str], None],
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
        url, local_filename = self.filesystem.get_download_url_and_local_filename(selected_file)
        if not url or not local_filename:
            return True  # No download required

        if self.filesystem.vehicle_configuration_file_exists(local_filename):
            return True  # File already exists in the vehicle directory, no need to download it

        # Ask user for confirmation
        msg = _("Should the {local_filename} file be downloaded from the URL\n{url}?")
        if not ask_confirmation(_("Download file from URL"), msg.format(local_filename=local_filename, url=url)):
            return True  # User declined download

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
        progress_callback: Optional[Callable] = None,
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
            progress_callback: Optional callback for progress updates.

        Returns:
            bool: True if upload was successful or not needed, False if upload failed.

        """
        local_filename, remote_filename = self.filesystem.get_upload_local_and_remote_filenames(selected_file)
        if not local_filename or not remote_filename:
            return True  # No upload required

        if not self.filesystem.vehicle_configuration_file_exists(local_filename):
            error_msg = _("Local file {local_filename} does not exist")
            show_error(_("Will not upload any file"), error_msg.format(local_filename=local_filename))
            return False

        if self.flight_controller.master is None:
            show_warning(_("Will not upload any file"), _("No flight controller connection"))
            return False

        # Ask user for confirmation
        msg = _("Should the {local_filename} file be uploaded to the flight controller as {remote_filename}?")
        if not ask_confirmation(
            _("Upload file to FC"), msg.format(local_filename=local_filename, remote_filename=remote_filename)
        ):
            return True  # User declined upload

        # Attempt upload
        if not self.flight_controller.upload_file(local_filename, remote_filename, progress_callback):
            error_msg = _("Failed to upload {local_filename} to {remote_filename}, please upload it manually")
            show_error(_("Upload failed"), error_msg.format(local_filename=local_filename, remote_filename=remote_filename))
            return False

        return True

    def download_flight_controller_parameters(self, progress_callback: Optional[Callable] = None) -> tuple[dict, dict]:
        """
        Download parameters from the flight controller.

        Args:
            progress_callback: Optional callback function for progress updates.

        Returns:
            tuple: (fc_parameters, param_default_values) downloaded from the flight controller.

        """
        # Download all parameters from the flight controller
        fc_parameters, param_default_values = self.flight_controller.download_params(
            progress_callback,
            Path(self.filesystem.vehicle_dir) / "complete.param",
            Path(self.filesystem.vehicle_dir) / "00_default.param",
        )

        # Update the flight controller parameters
        self.flight_controller.fc_parameters = fc_parameters

        # Write default values to file if available
        if param_default_values:
            self.filesystem.write_param_default_values_to_file(param_default_values)

        return fc_parameters, param_default_values

    def upload_parameters_that_require_reset_workflow(
        self,
        selected_params: dict,
        ask_confirmation: AskConfirmationCallback,
        show_error: ShowErrorCallback,
        progress_callback: Optional[Callable] = None,
    ) -> bool:
        """
        Upload parameters that require reset to the flight controller.

        Args:
            selected_params: Dictionary of parameters to upload.
            ask_confirmation: Callback to ask user for confirmation.
            show_error: Callback to show error messages.
            progress_callback: Optional callback for progress updates.

        Returns:
            bool: True if reset was required or unsure, False otherwise.

        """
        reset_required = False
        reset_unsure_params = []
        error_messages = []

        # Write each selected parameter to the flight controller
        for param_name, param in selected_params.items():
            try:
                if param_name not in self.flight_controller.fc_parameters or not is_within_tolerance(
                    self.flight_controller.fc_parameters[param_name], param.value
                ):
                    param_metadata = self.filesystem.doc_dict.get(param_name, None)
                    if param_metadata and param_metadata.get("RebootRequired", False):
                        self.flight_controller.set_param(param_name, float(param.value))
                        if param_name in self.flight_controller.fc_parameters:
                            logging_info(
                                _("Parameter %s changed from %f to %f, reset required"),
                                param_name,
                                self.flight_controller.fc_parameters[param_name],
                                param.value,
                            )
                        else:
                            logging_info(_("Parameter %s changed to %f, reset required"), param_name, param.value)
                        reset_required = True
                    # Check if any of the selected parameters have a _TYPE, _EN, or _ENABLE suffix
                    elif param_name.endswith(("_TYPE", "_EN", "_ENABLE", "SID_AXIS")):
                        self.flight_controller.set_param(param_name, float(param.value))
                        if param_name in self.flight_controller.fc_parameters:
                            logging_info(
                                _("Parameter %s changed from %f to %f, possible reset required"),
                                param_name,
                                self.flight_controller.fc_parameters[param_name],
                                param.value,
                            )
                        else:
                            logging_info(_("Parameter %s changed to %f, possible reset required"), param_name, param.value)
                        reset_unsure_params.append(param_name)
            except ValueError as e:  # noqa: PERF203
                error_msg = _("Failed to set parameter {param_name}: {e}").format(param_name=param_name, e=e)
                logging_error(error_msg)
                error_messages.append(error_msg)

        # Handle any errors with GUI dialogs
        for error_msg in error_messages:
            show_error(_("ArduPilot methodic configurator"), error_msg)

        self.reset_and_reconnect_workflow(reset_required, reset_unsure_params, ask_confirmation, show_error, progress_callback)

        return reset_required or bool(reset_unsure_params)

    def _calculate_reset_time(self) -> int:
        """
        Calculate the extra sleep time needed for reset based on boot delay parameters.

        Returns:
            int: Extra sleep time in seconds.

        """
        current_file_params: ParDict = self.filesystem.file_parameters.get(self.current_file, ParDict())
        filesystem_boot_delay = current_file_params.get("BRD_BOOT_DELAY", Par(0.0))
        flightcontroller_boot_delay = self.flight_controller.fc_parameters.get("BRD_BOOT_DELAY", 0)
        return int(max(filesystem_boot_delay.value, flightcontroller_boot_delay) // 1000 + 1)  # round up

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
        return self.flight_controller.reset_and_reconnect(progress_callback, None, int(sleep_time))

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

    def upload_selected_parameters_workflow(self, selected_params: dict, show_error: Callable[[str, str], None]) -> int:
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
                self.flight_controller.set_param(param_name, param.value)
                if param_name not in self.flight_controller.fc_parameters or not is_within_tolerance(
                    self.flight_controller.fc_parameters[param_name], param.value
                ):
                    if param_name in self.flight_controller.fc_parameters:
                        logging_info(
                            _("Parameter %s changed from %f to %f"),
                            param_name,
                            self.flight_controller.fc_parameters[param_name],
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
            except ValueError as _e:  # noqa: PERF203
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

        report_file_path = Path(getattr(self.filesystem, "vehicle_dir", ".")) / "tuning_report.csv"

        # Write a CSV with a header ("param", <list of files>) and one row per parameter.
        with open(report_file_path, "w", newline="", encoding="utf-8") as file:
            writer = csv_writer(file)
            writer.writerow(["param", *report_files])

            for param_name in report_params:
                row = [param_name]
                for param_file in report_files:
                    try:
                        if param_file == "00_default.param":
                            value = str(self.filesystem.param_default_dict[param_name].value)
                        else:
                            value = str(self.filesystem.file_parameters[param_file][param_name].value)
                    except (KeyError, ValueError):
                        # On any unexpected structure, leave the value empty (don't crash)
                        value = ""
                    row.append(value)
                writer.writerow(row)

    def validate_uploaded_parameters(self, selected_params: dict) -> list[str]:
        logging_info(_("Re-downloaded all parameters from the flight controller"))

        # Validate that the read parameters are the same as the ones in the current_file
        param_upload_error = []
        for param_name, param in selected_params.items():
            if (
                param_name in self.flight_controller.fc_parameters
                and param is not None
                and not is_within_tolerance(self.flight_controller.fc_parameters[param_name], float(param.value))
            ):
                logging_error(
                    _("Parameter %s upload to the flight controller failed. Expected: %f, Actual: %f"),
                    param_name,
                    param.value,
                    self.flight_controller.fc_parameters[param_name],
                )
                param_upload_error.append(param_name)
            if param_name not in self.flight_controller.fc_parameters:
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
        fc_parameters = ParDict.from_fc_parameters(self.flight_controller.fc_parameters)

        # Early exit if no FC parameters available
        if len(fc_parameters) == 0:
            return fc_parameters

        # Remove default parameters from FC parameters if default file exists
        fc_parameters.remove_if_value_is_similar(self.filesystem.param_default_dict, is_within_tolerance)

        # Filter out read-only parameters efficiently - only check params that exist in fc_parameters
        readonly_params_to_remove = [
            param_name for param_name in fc_parameters if self.filesystem.doc_dict.get(param_name, {}).get("ReadOnly", False)
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
        if not self.flight_controller.fc_parameters:
            return

        # Create the compounded state of all parameters stored in the AMC .param files
        compound = ParDict()
        first_config_step_filename = None
        for file_name, file_params in self.filesystem.file_parameters.items():
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
            self.filesystem.export_to_param(params_missing_in_the_amc_param_files, filename, annotate_doc=False)
            logging_info(
                _("Exported %d FC parameters missing or different in AMC files to %s"),
                len(params_missing_in_the_amc_param_files),
                filename,
            )
        else:
            logging_info(_("No FC parameters are missing or different from AMC parameter files"))

    def export_fc_params_missing_or_different(self) -> None:
        non_default_non_read_only_fc_params = self._get_non_default_non_read_only_fc_params()

        last_config_step_filename = list(self.filesystem.file_parameters.keys())[-1]
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
        if self.flight_controller.master is None:
            show_error(_("Error"), _("No flight controller connected"))
            return

        if not self.is_mavftp_supported:
            show_error(_("Error"), _("MAVFTP is not supported by the flight controller"))
            return

        filename = ask_saveas_filename()
        if not filename:
            return

        success = self.flight_controller.download_last_flight_log(filename, progress_callback)
        if success:
            show_info(_("Success"), _("Flight log downloaded successfully to:\n%s") % filename)
        else:
            show_error(_("Error"), _("Failed to download flight log. Check the console for details."))

    def is_configuration_step_optional(self, file_name: str, threshold_pct: int = 20) -> bool:
        """
        Check if the configuration step for the given file is optional.

        Args:
            file_name: Name of the configuration file to check.
            threshold_pct: Threshold percentage below which the step is considered optional.

        Returns:
            bool: True if the configuration step is optional, False if mandatory.

        """
        # Check if the configuration step for the given file is optional
        mandatory_text, _mandatory_url = self.filesystem.get_documentation_text_and_url(file_name, "mandatory")
        # Extract percentage from mandatory_text like "80% mandatory (20% optional)"
        percentage = 0
        if mandatory_text:
            try:
                percentage = int(mandatory_text.split("%")[0])
            except (ValueError, IndexError):
                percentage = 0

        return percentage <= threshold_pct

    def get_next_non_optional_file(self, current_file: str) -> Optional[str]:
        """
        Get the next non-optional configuration file in sequence.

        Args:
            current_file: The current parameter file being processed.

        Returns:
            Optional[str]: Next non-optional file name, or None if at the end.

        """
        files = list(self.filesystem.file_parameters.keys())
        if not files:
            return None

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
        annotated_fc_parameters = self.filesystem.annotate_intermediate_comments_to_param_dict(
            self.flight_controller.fc_parameters
        )
        if not annotated_fc_parameters:
            return {}

        # Categorize parameters using filesystem logic
        categorized = self.filesystem.categorize_parameters(annotated_fc_parameters)
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
        if self.filesystem.vehicle_configuration_file_exists(filename):
            msg = _("{} file already exists.\nDo you want to overwrite it?")
            should_write_file = ask_confirmation(_("Overwrite existing file"), msg.format(filename))

        # Write the file using if confirmed and has parameters
        if should_write_file:
            self.filesystem.export_to_param(param_dict, filename, annotate_doc)
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
        if self.filesystem.zip_file_exists():
            zip_file_path = self.filesystem.zip_file_path()
            msg = _("{} file already exists.\nDo you want to overwrite it?")
            should_write_file = ask_confirmation(_("Overwrite existing file"), msg.format(zip_file_path))

        if should_write_file:
            self.filesystem.zip_files(files_to_zip)
            zip_file_path = self.filesystem.zip_file_path()
            msg = _(
                "All relevant files have been zipped into the \n"
                "{zip_file_path} file.\n\nYou can now upload this file to the ArduPilot Methodic\n"
                "Configuration Blog post on discuss.ardupilot.org."
            )
            show_info(_("Parameter files zipped"), msg.format(zip_file_path=zip_file_path))

        return should_write_file
