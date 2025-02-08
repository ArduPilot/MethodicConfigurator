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
    def test_component_editor(self, mock_program_settings, mock_local_filesystem, mock_component_editor_window) -> None:
        mock_program_settings = mock_program_settings.return_value
        mock_program_settings.get_setting.return_value = True

        mock_local_filesystem = mock_local_filesystem.return_value
        mock_local_filesystem.doc_dict = {}

        mock_fc = MagicMock()
        mock_fc.fc_parameters = {"param1": "value1"}
        mock_fc.info.flight_sw_version_and_type = "v1.0"
        mock_fc.info.vendor = "vendor"
        mock_fc.info.firmware_type = "type"

        args = argparse.Namespace(skip_component_editor=False)
        component_editor(args, mock_fc, "quad", mock_local_filesystem, None)
        mock_component_editor_window.assert_called_once()


if __name__ == "__main__":
    unittest.main()
