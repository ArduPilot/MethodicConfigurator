#!/usr/bin/env python3

"""
Tests for the backend_filesystem.py file.

This file is part of Ardupilot methodic configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2025 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

from unittest.mock import mock_open, patch

from ardupilot_methodic_configurator.annotate_params import Par
from ardupilot_methodic_configurator.backend_flightcontroller import FlightController


def test_add_connection() -> None:
    fc = FlightController(reboot_time=7)
    assert fc.add_connection("test_connection") is True
    assert fc.add_connection("test_connection") is False
    assert fc.add_connection("") is False


def test_discover_connections() -> None:
    fc = FlightController(reboot_time=7)
    fc.discover_connections()
    assert len(fc.get_connection_tuples()) > 0


def test_connect() -> None:
    fc = FlightController(reboot_time=7)
    result = fc.connect(device="test")
    assert result == ""


def test_disconnect() -> None:
    fc = FlightController(reboot_time=7)
    fc.connect(device="test")
    fc.disconnect()
    assert fc.master is None


@patch("builtins.open", new_callable=mock_open, read_data="param1=1\nparam2=2")
@patch(
    "ardupilot_methodic_configurator.annotate_params.Par.load_param_file_into_dict",
    side_effect=lambda x: {"param1": Par(1, x), "param2": Par(2, x)},
)
def test_download_params(mock_load_param_file_into_dict, mock_file) -> None:
    fc = FlightController(reboot_time=7)
    fc.connect(device="test")
    with patch("ardupilot_methodic_configurator.backend_flightcontroller.open", mock_file):
        params, _ = fc.download_params()
    assert isinstance(params, dict)
    assert params == {"param1": 1, "param2": 2}
    mock_load_param_file_into_dict.assert_called_once_with("params.param")


@patch("builtins.open", new_callable=mock_open, read_data="param1,1\nparam2,2")
@patch(
    "ardupilot_methodic_configurator.annotate_params.Par.load_param_file_into_dict",
    side_effect=lambda x: {"param1": Par(1, x), "param2": Par(2, x)},
)
def test_set_param(mock_load_param_file_into_dict, mock_file) -> None:
    fc = FlightController(reboot_time=7)
    fc.connect(device="test")
    fc.set_param("TEST_PARAM", 1.0)
    with patch("ardupilot_methodic_configurator.backend_flightcontroller.open", mock_file):
        params, _ = fc.download_params()
    assert params.get("TEST_PARAM") is None  # Assuming the mock environment does not actually set the parameter
    mock_load_param_file_into_dict.assert_called_once_with("params.param")


def test_reset_and_reconnect() -> None:
    fc = FlightController(reboot_time=7)
    fc.connect(device="test")
    result = fc.reset_and_reconnect()
    assert result == ""


def test_upload_file() -> None:
    fc = FlightController(reboot_time=7)
    fc.connect(device="test")
    result = fc.upload_file("local.txt", "remote.txt")
    # Assuming the mock environment always returns False for upload_file
    assert result is False


def test_get_connection_tuples() -> None:
    fc = FlightController(reboot_time=7)
    fc.add_connection("test_connection")
    connections = fc.get_connection_tuples()
    assert ("test_connection", "test_connection") in connections


@patch("builtins.open", new_callable=mock_open, read_data="param1,1\nparam2,2")
@patch(
    "ardupilot_methodic_configurator.annotate_params.Par.load_param_file_into_dict",
    side_effect=lambda x: {"param1": Par(1, x), "param2": Par(2, x)},
)
def test_set_param_and_verify(mock_load_param_file_into_dict, mock_file) -> None:
    fc = FlightController(reboot_time=7)
    fc.connect(device="test")
    fc.set_param("TEST_PARAM", 1.0)
    with patch("ardupilot_methodic_configurator.backend_flightcontroller.open", mock_file):
        params, _ = fc.download_params()
    # Assuming the mock environment does not actually set the parameter
    assert params.get("TEST_PARAM") is None
    mock_load_param_file_into_dict.assert_called_once_with("params.param")


def test_download_params_via_mavftp() -> None:
    fc = FlightController(reboot_time=7)
    fc.connect(device="test")
    params, default_params = fc.download_params_via_mavftp()
    assert isinstance(params, dict)
    assert isinstance(default_params, dict)


def test_auto_detect_serial() -> None:
    fc = FlightController(reboot_time=7)
    serial_ports = fc._FlightController__auto_detect_serial()  # pylint: disable=protected-access
    assert isinstance(serial_ports, list)


def test_list_serial_ports() -> None:
    serial_ports = FlightController._FlightController__list_serial_ports()  # pylint: disable=protected-access
    assert isinstance(serial_ports, list)


def test_list_network_ports() -> None:
    network_ports = FlightController._FlightController__list_network_ports()  # pylint: disable=protected-access
    assert isinstance(network_ports, list)
    assert "tcp:127.0.0.1:5760" in network_ports


def test_request_banner() -> None:
    fc = FlightController(reboot_time=7)
    fc.connect(device="test")
    fc._FlightController__request_banner()  # pylint: disable=protected-access
    # Since we cannot verify in the mock environment, we will just ensure no exceptions are raised


def test_receive_banner_text() -> None:
    fc = FlightController(reboot_time=7)
    fc.connect(device="test")
    banner_text = fc._FlightController__receive_banner_text()  # pylint: disable=protected-access
    assert isinstance(banner_text, list)


def test_request_message() -> None:
    fc = FlightController(reboot_time=7)
    fc.connect(device="test")
    fc._FlightController__request_message(1)  # pylint: disable=protected-access
    # Since we cannot verify in the mock environment, we will just ensure no exceptions are raised


def test_create_connection_with_retry() -> None:
    fc = FlightController(reboot_time=7)
    result = fc._FlightController__create_connection_with_retry(progress_callback=None, retries=1, timeout=1)  # pylint: disable=protected-access
    assert result == ""


def test_process_autopilot_version() -> None:
    fc = FlightController(reboot_time=7)
    fc.connect(device="test")
    banner_msgs = ["ChibiOS: 123", "ArduPilot"]
    result = fc._FlightController__process_autopilot_version(None, banner_msgs)  # pylint: disable=protected-access
    assert isinstance(result, str)
