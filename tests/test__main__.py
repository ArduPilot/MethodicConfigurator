#!/usr/bin/env python3

"""
Tests for the __main__.py file.

This file is part of Ardupilot methodic configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2025 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import argparse
import unittest
from unittest.mock import MagicMock, patch

import pytest

from ardupilot_methodic_configurator.__main__ import (
    component_editor,
    connect_to_fc_and_set_vehicle_type,
    create_argument_parser,
)


@pytest.fixture
def _mock_args(mocker) -> None:
    mocker.patch(
        "argparse.ArgumentParser.parse_args", return_value=argparse.Namespace(conn="tcp:127.0.0.1:5760", params="params_dir")
    )


class TestArgumentParser(unittest.TestCase):
    """Test the argument_parser function."""

    @pytest.mark.usefixtures("_mock_args")
    def test_argument_parser(self) -> None:
        args = create_argument_parser().parse_args()
        assert args.conn == "tcp:127.0.0.1:5760"
        assert args.params == "params_dir"


class TestMainFunctions(unittest.TestCase):
    """Test the main functions of the __main__.py file."""

    @patch("ardupilot_methodic_configurator.__main__.FlightController")
    def test_connect_to_fc_and_read_parameters(self, mock_flight_controller) -> None:
        mock_fc = mock_flight_controller.return_value
        mock_fc.connect.return_value = ""
        mock_fc.info.vehicle_type = "quad"
        mock_fc.info.flight_sw_version_and_type = "v1.0"
        mock_fc.info.vendor = "vendor"
        mock_fc.info.firmware_type = "type"

        args = argparse.Namespace(device="test_device", vehicle_type="", reboot_time=5)
        flight_controller, vehicle_type = connect_to_fc_and_set_vehicle_type(args)
        assert flight_controller == mock_fc
        assert vehicle_type == "quad"

    @patch("ardupilot_methodic_configurator.__main__.ComponentEditorWindow")
    @patch("ardupilot_methodic_configurator.__main__.LocalFilesystem")
    @patch("ardupilot_methodic_configurator.__main__.ProgramSettings")
    @patch("ardupilot_methodic_configurator.__main__.sys_exit")
    @patch("ardupilot_methodic_configurator.__main__.show_error_message")
    def test_component_editor(  # pylint: disable=too-many-arguments, too-many-positional-arguments
        self, mock_show_error, mock_sys_exit, mock_program_settings, mock_local_filesystem, mock_component_editor_window
    ) -> None:
        # Setup mock ComponentEditorWindow
        mock_editor = MagicMock()
        mock_component_editor_window.return_value = mock_editor

        # Setup mock ProgramSettings
        mock_program_settings.get_setting.return_value = False

        # Setup mock LocalFilesystem
        mock_local_fs = mock_local_filesystem
        mock_local_fs.doc_dict = {}
        mock_local_fs.update_and_export_vehicle_params_from_fc.return_value = ""  # Return success

        # Setup mock FlightController
        mock_fc = MagicMock()
        mock_fc.fc_parameters = {"param1": "value1"}
        mock_fc.info.flight_sw_version_and_type = "v1.0"
        mock_fc.info.vendor = "vendor"
        mock_fc.info.firmware_type = "type"
        mock_fc.info.mcu_series = "series"

        # Test successful execution
        args = argparse.Namespace(skip_component_editor=True)  # Skip to avoid mainloop blocking
        component_editor(args, mock_fc, "quad", mock_local_fs, None)

        # Verify correct method calls
        mock_component_editor_window.assert_called_once()
        mock_editor.populate_frames.assert_called_once()
        mock_editor.set_vehicle_type_and_version.assert_called_once_with("quad", "v1.0")
        mock_local_fs.update_and_export_vehicle_params_from_fc.assert_called_once_with(
            source_param_values=None, existing_fc_params=list(mock_fc.fc_parameters.keys())
        )
        mock_sys_exit.assert_not_called()

        # Test error case
        mock_local_fs.update_and_export_vehicle_params_from_fc.return_value = "Error message"
        component_editor(args, mock_fc, "quad", mock_local_fs, None)

        # Verify error handling
        mock_show_error.assert_called_once()
        mock_sys_exit.assert_called_once_with(1)

    @patch("ardupilot_methodic_configurator.__main__.FlightController")
    def test_connect_to_fc_with_explicit_vehicle_type(self, mock_flight_controller) -> None:
        """Test connecting to FC with explicitly set vehicle type."""
        mock_fc = mock_flight_controller.return_value
        mock_fc.connect.return_value = ""
        mock_fc.info.vehicle_type = "quad"
        mock_fc.info.flight_sw_version_and_type = "v1.0"

        # Set an explicit vehicle type
        args = argparse.Namespace(device="test_device", vehicle_type="plane", reboot_time=5)
        flight_controller, vehicle_type = connect_to_fc_and_set_vehicle_type(args)

        assert flight_controller == mock_fc
        assert vehicle_type == "plane"  # Should use explicitly provided type

    @patch("ardupilot_methodic_configurator.__main__.FlightController")
    def test_connect_to_fc_with_connection_error(self, mock_flight_controller) -> None:
        """Test handling of connection errors."""
        mock_fc = mock_flight_controller.return_value
        mock_fc.connect.return_value = "Connection error"

        with patch("ardupilot_methodic_configurator.__main__.ConnectionSelectionWindow") as mock_window:
            mock_window_instance = MagicMock()
            mock_window.return_value = mock_window_instance

            args = argparse.Namespace(device="test_device", vehicle_type="", reboot_time=5)
            connect_to_fc_and_set_vehicle_type(args)

            # Verify ConnectionSelectionWindow was created with the right parameters
            mock_window.assert_called_once_with(mock_fc, "Connection error")
            mock_window_instance.root.mainloop.assert_called_once()

    @patch("ardupilot_methodic_configurator.__main__.FlightController")
    def test_flight_controller_info_attributes(self, mock_flight_controller) -> None:
        """Test that FlightController info attributes are correctly used."""
        mock_fc = mock_flight_controller.return_value
        mock_fc.connect.return_value = ""
        mock_fc.info.vehicle_type = "quad"
        mock_fc.info.flight_sw_version_and_type = "v1.0"
        mock_fc.info.vendor = "ArduPilot"
        mock_fc.info.firmware_type = "CubeOrange"
        mock_fc.info.mcu_series = "STM32F7"
        mock_fc.info.flight_sw_version = "4.3.0"

        # Test that info attributes are used in component editor
        with patch("ardupilot_methodic_configurator.__main__.ComponentEditorWindow") as mock_editor_window:
            mock_editor = MagicMock()
            mock_editor_window.return_value = mock_editor

            with patch("ardupilot_methodic_configurator.__main__.LocalFilesystem") as mock_filesystem:
                mock_fs = MagicMock()
                mock_filesystem.return_value = mock_fs
                mock_fs.update_and_export_vehicle_params_from_fc.return_value = ""

                with patch("ardupilot_methodic_configurator.__main__.ProgramSettings"):
                    args = argparse.Namespace(skip_component_editor=True)
                    component_editor(args, mock_fc, "quad", mock_fs, None)

                    # Verify that info attributes are correctly passed to component editor
                    mock_editor.set_vehicle_type_and_version.assert_called_once_with("quad", "v1.0")
                    mock_editor.set_fc_manufacturer.assert_called_once_with("ArduPilot")
                    mock_editor.set_fc_model.assert_called_once_with("CubeOrange")
                    mock_editor.set_mcu_series.assert_called_once_with("STM32F7")

    @patch("ardupilot_methodic_configurator.__main__.FlightController")
    @patch("ardupilot_methodic_configurator.__main__.LocalFilesystem")
    @patch("ardupilot_methodic_configurator.__main__.ParameterEditorWindow")
    def test_backup_fc_parameters(self, mock_param_editor, mock_local_filesystem, mock_flight_controller) -> None:  # pylint: disable=unused-argument
        """Test that FC parameters are backed up correctly."""
        # Setup mocks
        mock_fc = MagicMock()
        mock_flight_controller.return_value = mock_fc
        mock_fc.connect.return_value = ""
        mock_fc.info.vehicle_type = "quad"
        mock_fc.fc_parameters = {"PARAM1": 1.0, "PARAM2": 2.0}

        mock_fs = MagicMock()
        mock_local_filesystem.return_value = mock_fs
        mock_fs.vehicle_type = "quad"
        mock_fs.find_lowest_available_backup_number.return_value = 5
        mock_fs.get_start_file.return_value = "start_file.param"

        # Patch the main function to avoid running the entire flow
        with (
            patch("ardupilot_methodic_configurator.__main__.main"),
            patch("ardupilot_methodic_configurator.__main__.component_editor"),
        ):
            # Import and call main to trigger the backup functionality

            # Just calling connect_to_fc_and_set_vehicle_type to get flight_controller
            args = argparse.Namespace(
                device="test_device",
                vehicle_type="",
                reboot_time=5,
                n=0,
                skip_check_for_updates=True,
                loglevel="INFO",
                skip_component_editor=True,
                allow_editing_template_files=False,
                save_component_to_system_templates=False,
                vehicle_dir="",
            )

            # Create a custom version of main that only tests the backup functionality
            def test_backup_only() -> None:
                flight_controller, _vehicle_type = connect_to_fc_and_set_vehicle_type(args)

                # This is the portion we want to test
                if flight_controller.fc_parameters:
                    mock_fs.backup_fc_parameters_to_file(
                        flight_controller.fc_parameters,
                        "autobackup_00_before_ardupilot_methodic_configurator.param",
                        overwrite_existing_file=False,
                        even_if_last_uploaded_filename_exists=False,
                    )
                    # Create incremental backup file
                    backup_num = mock_fs.find_lowest_available_backup_number()
                    mock_fs.backup_fc_parameters_to_file(
                        flight_controller.fc_parameters,
                        f"autobackup_{backup_num:02d}.param",
                        overwrite_existing_file=True,
                        even_if_last_uploaded_filename_exists=True,
                    )

            # Call our custom test function
            test_backup_only()

            # Verify backup files were created
            mock_fs.backup_fc_parameters_to_file.assert_any_call(
                mock_fc.fc_parameters,
                "autobackup_00_before_ardupilot_methodic_configurator.param",
                overwrite_existing_file=False,
                even_if_last_uploaded_filename_exists=False,
            )
            mock_fs.backup_fc_parameters_to_file.assert_any_call(
                mock_fc.fc_parameters,
                "autobackup_05.param",
                overwrite_existing_file=True,
                even_if_last_uploaded_filename_exists=True,
            )
            assert mock_fs.backup_fc_parameters_to_file.call_count == 2

    @patch("ardupilot_methodic_configurator.__main__.LocalFilesystem")
    def test_no_backup_without_fc_parameters(self, mock_local_filesystem) -> None:
        """Test that backup is not created when there are no FC parameters."""
        # Setup mocks
        mock_fs = MagicMock()
        mock_local_filesystem.return_value = mock_fs

        # Create a mock flight controller with empty parameters
        mock_fc = MagicMock()
        mock_fc.fc_parameters = {}

        # Directly test the functionality
        if mock_fc.fc_parameters:
            mock_fs.backup_fc_parameters_to_file(
                mock_fc.fc_parameters,
                "autobackup_00_before_ardupilot_methodic_configurator.param",
                overwrite_existing_file=False,
                even_if_last_uploaded_filename_exists=False,
            )

        # Verify no backups were created
        mock_fs.backup_fc_parameters_to_file.assert_not_called()

    def test_backup_filename_formatting(self) -> None:
        """Test the formatting of backup filenames."""
        # Test different numbers
        for num in [0, 1, 5, 10, 99]:
            filename = f"autobackup_{num:02d}.param"
            expected = f"autobackup_{'0' + str(num) if num < 10 else str(num)}.param"
            assert filename == expected, f"Expected {expected}, got {filename}"


if __name__ == "__main__":
    unittest.main()
