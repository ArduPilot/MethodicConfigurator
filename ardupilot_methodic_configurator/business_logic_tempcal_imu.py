"""
Business logic for IMU temperature calibration.

This module provides the data model and business logic for performing
IMU temperature calibration based on flight log data.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2025 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable

from ardupilot_methodic_configurator import _
from ardupilot_methodic_configurator.tempcal_imu import IMUfit

if TYPE_CHECKING:
    from ardupilot_methodic_configurator.configuration_manager import ConfigurationManager


class TempCalIMUDataModel:  # pylint: disable=too-many-instance-attributes
    """
    Data model for IMU temperature calibration.

    This class encapsulates the business logic for performing IMU temperature
    calibration, including checking if calibration should be offered and
    running the calibration workflow.
    """

    def __init__(  # pylint: disable=too-many-arguments, too-many-positional-arguments
        self,
        configuration_manager: ConfigurationManager,
        step_filename: str,
        ask_confirmation: Callable[[str, str], bool],
        select_file: Callable[[str, list[tuple[str, list[str]]]], str | None],
        show_warning: Callable[[str, str], None],
        show_error: Callable[[str, str], None],
        progress_callback: Callable[[int], None] | None = None,
        cleanup_callback: Callable[[], None] | None = None,
    ) -> None:
        """
        Initialize the IMU temperature calibration data model.

        Args:
            configuration_manager: The configuration manager for accessing vehicle data and parameters
            step_filename: The configuration step filename that triggered the calibration
            ask_confirmation: Callback for yes/no confirmation dialogs (title, message) -> bool
            select_file: Callback for file selection dialog (title, filetypes) -> filepath | None
            show_warning: Callback for warning messages (title, message) -> None
            show_error: Callback for error messages (title, message) -> None
            progress_callback: Optional callback for progress updates (0-100)
            cleanup_callback: Optional callback for cleanup after workflow completion

        """
        self._configuration_manager = configuration_manager
        self._step_filename = step_filename
        self._ask_confirmation = ask_confirmation
        self._select_file = select_file
        self._show_warning = show_warning
        self._show_error = show_error
        self._progress_callback = progress_callback
        self._cleanup_callback = cleanup_callback

    def get_result_param_fullpath(self) -> str:
        """
        Get the full path of the result parameter file.

        Returns:
            str: The full path to the IMU calibration result parameter file

        """
        return self._configuration_manager.get_configuration_file_fullpath(self._step_filename)

    def get_confirmation_message(self) -> str:
        """
        Get the confirmation message to show to the user.

        Returns:
            str: The formatted confirmation message

        """
        return _(
            "If you proceed the {tempcal_imu_result_param_filename}\n"
            "will be overwritten with the new calibration results.\n"
            "Do you want to provide a .bin log file and\n"
            "run the IMU temperature calibration using it?"
        ).format(tempcal_imu_result_param_filename=self._step_filename)

    def run_calibration(self) -> bool:
        """
        Run the IMU temperature calibration workflow with user interaction.

        This method orchestrates the complete calibration process through injected
        callback functions (provided at construction), achieving separation between
        business logic and GUI implementation. The cleanup callback is guaranteed
        to be called whether the workflow succeeds or fails.

        Returns:
            bool: True if calibration was performed successfully, False otherwise

        Raises:
            SystemExit: If the calibration encounters a fatal error reading parameter files

        """
        try:
            # Ask user for confirmation
            if not self._ask_confirmation(
                _("IMU temperature calibration"),
                self.get_confirmation_message(),
            ):
                return False

            # Select log file
            log_file = self._select_file(
                _("Select ArduPilot binary log file"),
                [(_("ArduPilot binary log files"), ["*.bin", "*.BIN"])],
            )
            if not log_file:
                return False  # User cancelled file selection

            # Show warning about processing time
            self._show_warning(
                _("IMU temperature calibration"),
                _("Please wait, this can take a really long time and\nthe GUI will be unresponsive until it finishes."),
            )

            tempcal_imu_result_param_fullpath = self.get_result_param_fullpath()

            # Perform the actual IMU temperature calibration
            # This calls the existing IMUfit function from tempcal_imu.py
            try:
                IMUfit(
                    logfile=log_file,
                    outfile=tempcal_imu_result_param_fullpath,
                    no_graph=False,
                    log_parm=False,
                    online=False,
                    tclr=False,
                    figpath=self._configuration_manager.vehicle_dir,
                    progress_callback=self._progress_callback,
                )

                # Reload parameter files after calibration
                self._configuration_manager.reload_parameter_files()
                return True

            except SystemExit as exp:
                self._show_error(_("Fatal error reading parameter files"), f"{exp}")
                raise

        finally:
            # Always call cleanup callback if provided (e.g., destroy progress window)
            if self._cleanup_callback:
                self._cleanup_callback()
