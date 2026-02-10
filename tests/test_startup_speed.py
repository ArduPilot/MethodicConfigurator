#!/usr/bin/env python3

"""
Test for startup performance and connection logic.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

from unittest.mock import MagicMock, patch

from ardupilot_methodic_configurator.backend_flightcontroller_connection import (
    FlightControllerConnection,
)
from ardupilot_methodic_configurator.data_model_flightcontroller_info import (
    FlightControllerInfo,
)


@patch(
    "ardupilot_methodic_configurator.backend_flightcontroller_connection.FlightControllerConnection._register_and_try_connect"
)
def test_startup_is_fast_when_no_drone_connected(mock_register_connect) -> None:
    """
    Scenario: User starts the application without a FC connected.

    GIVEN: The application is launching and auto-detecting ports
    WHEN: It attempts to connect to a TCP port that is closed
    THEN: It should use a reduced retry count (2) to minimize startup delay
    """
    # GIVEN: A connection manager looking for devices on a network
    info = FlightControllerInfo()
    connection = FlightControllerConnection(info)

    # Mock: Pretend we found one TCP port to check
    connection.get_network_ports = MagicMock(return_value=["tcp:127.0.0.1:5760"])
    # Mock: Pretend no serial ports exist (simplify the test)
    # pylint: disable=protected-access
    connection._auto_detect_serial = MagicMock(return_value=[])

    # WHEN: The auto-connection logic runs
    connection.connect(device="")

    # THEN: The connection attempt should use retries=2 (not the default 3)
    # Extract the arguments passed to the connection function
    _, kwargs = mock_register_connect.call_args

    # Check that 'retries' was passed explicitly
    assert "retries" in kwargs, "FAIL: The 'retries' argument was not passed!"

    # Check that it is set to 2 (Safety Compromise: 1 retry allowed)
    actual_retries = kwargs["retries"]
    assert actual_retries == 2, f"FAIL: Expected retries=2 for fast startup, but got {actual_retries}!"
