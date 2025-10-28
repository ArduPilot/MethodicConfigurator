#!/usr/bin/env python3

"""
SITL integration tests for the backend_flightcontroller.py file.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2025 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import time

import pytest

from ardupilot_methodic_configurator.backend_flightcontroller import FlightController


@pytest.mark.sitl
def test_sitl_connection(sitl_flight_controller: FlightController) -> None:
    """Test that we can connect to SITL."""
    assert sitl_flight_controller.master is not None
    assert sitl_flight_controller.info.firmware_type == "ArduCopter"


@pytest.mark.sitl
def test_sitl_parameter_download(sitl_flight_controller: FlightController) -> None:
    """Test downloading parameters from SITL."""
    params, _ = sitl_flight_controller.download_params()

    assert isinstance(params, dict)
    assert len(params) > 0
    assert "FRAME_TYPE" in params  # Common ArduCopter parameter


@pytest.mark.sitl
def test_sitl_motor_test(sitl_flight_controller: FlightController) -> None:
    """Test motor testing against SITL."""
    success, error_msg = sitl_flight_controller.test_motor(
        test_sequence_nr=0, motor_letters="A", motor_output_nr=1, throttle_percent=10, timeout_seconds=2
    )

    assert success, f"Motor test failed: {error_msg}"


@pytest.mark.sitl
def test_sitl_battery_status(sitl_flight_controller: FlightController) -> None:
    """Test battery status monitoring with SITL."""
    # Download parameters first as get_battery_status requires them
    params, _ = sitl_flight_controller.download_params()
    assert isinstance(params, dict)
    assert len(params) > 0
    # Store parameters in the flight controller instance
    sitl_flight_controller.fc_parameters = params

    success, error_msg = sitl_flight_controller.request_periodic_battery_status()
    assert success, f"Battery monitoring setup failed: {error_msg}"

    time.sleep(1)  # Wait for battery data

    battery_status, status_error = sitl_flight_controller.get_battery_status()
    assert battery_status is not None, f"Battery status retrieval failed: {status_error}"


@pytest.mark.sitl
def test_sitl_parameter_set_and_verify(sitl_flight_controller: FlightController) -> None:
    """Test setting and verifying a parameter value with SITL."""
    # Save original value
    original_value = sitl_flight_controller.fetch_param("FRAME_TYPE")
    assert original_value is not None

    # Set a new value (ensure it's different)
    new_value = 1 if original_value != 1 else 2
    sitl_flight_controller.set_param("FRAME_TYPE", float(new_value))

    # Wait a bit for the parameter to be set
    time.sleep(0.5)

    # Verify the parameter was set
    fetched_value = sitl_flight_controller.fetch_param("FRAME_TYPE")
    assert fetched_value == new_value, f"Parameter not set correctly: expected {new_value}, got {fetched_value}"

    # Restore original value
    sitl_flight_controller.set_param("FRAME_TYPE", float(original_value))
    time.sleep(0.5)


@pytest.mark.sitl
def test_sitl_frame_info(sitl_flight_controller: FlightController) -> None:
    """Test frame information retrieval from SITL."""
    frame_type, motor_count = sitl_flight_controller.get_frame_info()

    assert isinstance(frame_type, int)
    assert isinstance(motor_count, int)
    assert motor_count > 0  # Should have motors configured
