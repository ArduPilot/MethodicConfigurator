#!/usr/bin/env python3

"""
Tests for IMU temperature calibration business logic.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2025 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

from unittest.mock import MagicMock, patch

import pytest

from ardupilot_methodic_configurator.business_logic_tempcal_imu import TempCalIMUDataModel


class TestTempCalIMUDataModel:
    """Test suite for IMU temperature calibration business logic."""

    @pytest.fixture
    def mock_configuration_manager(self) -> MagicMock:
        """Create a mock configuration manager."""
        config_mgr = MagicMock()
        config_mgr.vehicle_dir = "/test/vehicle/dir"
        config_mgr.get_configuration_file_fullpath.return_value = "/test/vehicle/dir/03_imu_temp_cal.param"
        return config_mgr

    @pytest.fixture
    def mock_callbacks(self) -> dict:
        """Create mock callbacks for user interaction."""
        return {
            "ask_confirmation": MagicMock(return_value=True),
            "select_file": MagicMock(return_value="/test/log.bin"),
            "show_warning": MagicMock(),
            "show_error": MagicMock(),
        }

    @pytest.fixture
    def data_model(self, mock_configuration_manager, mock_callbacks) -> TempCalIMUDataModel:
        """Create a TempCalIMUDataModel instance with mocked dependencies."""
        return TempCalIMUDataModel(
            mock_configuration_manager,
            "03_imu_temp_cal.param",
            mock_callbacks["ask_confirmation"],
            mock_callbacks["select_file"],
            mock_callbacks["show_warning"],
            mock_callbacks["show_error"],
        )

    def test_calibration_result_file_path_is_in_vehicle_directory(self, data_model, mock_configuration_manager) -> None:
        """
        Calibration results are saved to the vehicle configuration directory.

        GIVEN: A calibration workflow for a specific configuration step
        WHEN: Determining where to save calibration results
        THEN: Results should be saved in the vehicle's configuration directory
        """
        result = data_model.get_result_param_fullpath()

        assert result == "/test/vehicle/dir/03_imu_temp_cal.param"
        mock_configuration_manager.get_configuration_file_fullpath.assert_called_once_with("03_imu_temp_cal.param")

    def test_get_confirmation_message(self, data_model) -> None:
        """
        User receives clear warning about calibration file being overwritten.

        GIVEN: A calibration workflow is about to start
        WHEN: Requesting user confirmation
        THEN: Message should warn that existing calibration file will be overwritten
        """
        message = data_model.get_confirmation_message()

        assert "03_imu_temp_cal.param" in message
        assert "overwritten" in message
        assert ".bin" in message

    @patch("ardupilot_methodic_configurator.business_logic_tempcal_imu.IMUfit")
    def test_user_successfully_completes_calibration_workflow(
        self, mock_imufit, mock_configuration_manager, mock_callbacks
    ) -> None:
        """
        User successfully completes IMU temperature calibration.

        GIVEN: User has a valid flight log file
        WHEN: User confirms all dialogs and calibration completes successfully
        THEN: Calibration should run, parameters should reload, and workflow returns success
        """
        progress_callback = MagicMock()
        data_model = TempCalIMUDataModel(
            mock_configuration_manager,
            "03_imu_temp_cal.param",
            mock_callbacks["ask_confirmation"],
            mock_callbacks["select_file"],
            mock_callbacks["show_warning"],
            mock_callbacks["show_error"],
            progress_callback=progress_callback,
        )

        result = data_model.run_calibration()

        assert result is True
        mock_callbacks["ask_confirmation"].assert_called_once()
        mock_callbacks["select_file"].assert_called_once()
        mock_callbacks["show_warning"].assert_called_once()
        mock_imufit.assert_called_once_with(
            logfile="/test/log.bin",
            outfile="/test/vehicle/dir/03_imu_temp_cal.param",
            no_graph=False,
            log_parm=False,
            online=False,
            tclr=False,
            figpath="/test/vehicle/dir",
            progress_callback=progress_callback,
        )
        mock_configuration_manager.reload_parameter_files.assert_called_once()

    def test_run_calibration_user_declines_confirmation(self, data_model, mock_callbacks) -> None:
        """
        User can cancel calibration at confirmation step.

        GIVEN: User is presented with calibration confirmation dialog
        WHEN: User clicks "No" or cancels the confirmation
        THEN: Workflow should exit gracefully without starting calibration
        """
        mock_callbacks["ask_confirmation"].return_value = False

        result = data_model.run_calibration()

        assert result is False
        mock_callbacks["ask_confirmation"].assert_called_once()
        mock_callbacks["select_file"].assert_not_called()
        mock_callbacks["show_warning"].assert_not_called()

    def test_run_calibration_user_cancels_file_selection(self, data_model, mock_callbacks) -> None:
        """
        User can cancel calibration during file selection.

        GIVEN: User confirmed calibration but is selecting a log file
        WHEN: User cancels the file selection dialog
        THEN: Workflow should exit gracefully without running calibration
        """
        mock_callbacks["select_file"].return_value = None

        result = data_model.run_calibration()

        assert result is False
        mock_callbacks["ask_confirmation"].assert_called_once()
        mock_callbacks["select_file"].assert_called_once()
        mock_callbacks["show_warning"].assert_not_called()

    @patch("ardupilot_methodic_configurator.business_logic_tempcal_imu.IMUfit")
    def test_run_calibration_handles_system_exit(self, mock_imufit, data_model, mock_callbacks) -> None:
        """
        User is informed when calibration encounters fatal errors.

        GIVEN: User starts calibration workflow
        WHEN: Calibration encounters a fatal error that causes SystemExit
        THEN: User should see error message and application should exit gracefully
        """
        mock_imufit.side_effect = SystemExit("Fatal calibration error")

        with pytest.raises(SystemExit):
            data_model.run_calibration()

        mock_callbacks["show_error"].assert_called_once()

    @patch("ardupilot_methodic_configurator.business_logic_tempcal_imu.IMUfit")
    def test_calibration_works_without_visual_progress_updates(
        self, mock_imufit, mock_configuration_manager, mock_callbacks
    ) -> None:
        """
        Calibration completes successfully even without progress bar.

        GIVEN: User runs calibration
        WHEN: No progress callback is provided (headless mode or simple UI)
        THEN: Calibration should complete successfully without visual feedback
        """
        data_model = TempCalIMUDataModel(
            mock_configuration_manager,
            "03_imu_temp_cal.param",
            mock_callbacks["ask_confirmation"],
            mock_callbacks["select_file"],
            mock_callbacks["show_warning"],
            mock_callbacks["show_error"],
            progress_callback=None,
        )

        result = data_model.run_calibration()

        assert result is True
        mock_imufit.assert_called_once()
        assert mock_imufit.call_args[1]["progress_callback"] is None
        mock_configuration_manager.reload_parameter_files.assert_called_once()

    @patch("ardupilot_methodic_configurator.business_logic_tempcal_imu.IMUfit")
    def test_cleanup_callback_is_called_after_successful_calibration(
        self,
        mock_imufit,  # pylint: disable=unused-argument
        mock_configuration_manager,
        mock_callbacks,
    ) -> None:
        """
        Cleanup actions execute after successful calibration.

        GIVEN: User runs calibration with cleanup callback (e.g., close progress window)
        WHEN: Calibration completes successfully
        THEN: Cleanup callback should be invoked to release resources
        """
        cleanup_callback = MagicMock()
        data_model = TempCalIMUDataModel(
            mock_configuration_manager,
            "03_imu_temp_cal.param",
            mock_callbacks["ask_confirmation"],
            mock_callbacks["select_file"],
            mock_callbacks["show_warning"],
            mock_callbacks["show_error"],
            cleanup_callback=cleanup_callback,
        )

        data_model.run_calibration()

        cleanup_callback.assert_called_once()

    @patch("ardupilot_methodic_configurator.business_logic_tempcal_imu.IMUfit")
    def test_cleanup_callback_is_called_even_when_calibration_fails(
        self, mock_imufit, mock_configuration_manager, mock_callbacks
    ) -> None:
        """
        Cleanup actions execute even when calibration fails.

        GIVEN: User runs calibration with cleanup callback
        WHEN: Calibration encounters an error
        THEN: Cleanup callback should still be invoked (finally block behavior)
        """
        cleanup_callback = MagicMock()
        mock_imufit.side_effect = SystemExit("Calibration failed")

        data_model = TempCalIMUDataModel(
            mock_configuration_manager,
            "03_imu_temp_cal.param",
            mock_callbacks["ask_confirmation"],
            mock_callbacks["select_file"],
            mock_callbacks["show_warning"],
            mock_callbacks["show_error"],
            cleanup_callback=cleanup_callback,
        )

        with pytest.raises(SystemExit):
            data_model.run_calibration()

        cleanup_callback.assert_called_once()

    @patch("ardupilot_methodic_configurator.business_logic_tempcal_imu.IMUfit")
    def test_cleanup_callback_is_called_when_user_cancels_at_confirmation(
        self,
        mock_imufit,  # pylint: disable=unused-argument
        mock_configuration_manager,
        mock_callbacks,
    ) -> None:
        """
        Cleanup callback is called even when user cancels at confirmation step.

        GIVEN: User runs calibration with cleanup callback
        WHEN: User cancels at the confirmation dialog
        THEN: Cleanup callback should still be invoked
        """
        cleanup_callback = MagicMock()
        mock_callbacks["ask_confirmation"].return_value = False

        data_model = TempCalIMUDataModel(
            mock_configuration_manager,
            "03_imu_temp_cal.param",
            mock_callbacks["ask_confirmation"],
            mock_callbacks["select_file"],
            mock_callbacks["show_warning"],
            mock_callbacks["show_error"],
            cleanup_callback=cleanup_callback,
        )

        result = data_model.run_calibration()

        assert result is False
        cleanup_callback.assert_called_once()

    @patch("ardupilot_methodic_configurator.business_logic_tempcal_imu.IMUfit")
    def test_cleanup_callback_is_called_when_user_cancels_file_selection(
        self,
        mock_imufit,  # pylint: disable=unused-argument
        mock_configuration_manager,
        mock_callbacks,
    ) -> None:
        """
        Cleanup callback is called when user cancels file selection.

        GIVEN: User runs calibration with cleanup callback
        WHEN: User cancels the file selection dialog
        THEN: Cleanup callback should still be invoked
        """
        cleanup_callback = MagicMock()
        mock_callbacks["select_file"].return_value = None

        data_model = TempCalIMUDataModel(
            mock_configuration_manager,
            "03_imu_temp_cal.param",
            mock_callbacks["ask_confirmation"],
            mock_callbacks["select_file"],
            mock_callbacks["show_warning"],
            mock_callbacks["show_error"],
            cleanup_callback=cleanup_callback,
        )

        result = data_model.run_calibration()

        assert result is False
        cleanup_callback.assert_called_once()
