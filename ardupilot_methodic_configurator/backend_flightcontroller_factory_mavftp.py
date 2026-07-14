"""
MAVFTP utility functions.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

from logging import error as logging_error
from typing import TYPE_CHECKING, Union

from ardupilot_methodic_configurator import _
from ardupilot_methodic_configurator.backend_mavftp import MAVFTP

if TYPE_CHECKING:
    from ardupilot_methodic_configurator.backend_flightcontroller_protocols import MavlinkConnection


def create_mavftp(master: Union["MavlinkConnection", None]) -> MAVFTP:
    """
    Factory function for creating MAVFTP instances.

    This function can be mocked in tests to inject mock MAVFTP.

    Args:
        master: The MAVLink connection object

    Returns:
        MAVFTP: The MAVFTP instance

    Raises:
        RuntimeError: If no MAVLink connection is available

    """
    if master is None:
        msg = "No MAVLink connection available for MAVFTP"
        raise RuntimeError(msg)
    return MAVFTP(master, target_system=master.target_system, target_component=master.target_component)


def create_mavftp_safe(
    master: Union["MavlinkConnection", None],
) -> MAVFTP | None:  # pyright: ignore[reportGeneralTypeIssues]
    """
    Factory function for creating MAVFTP instances with safe error handling.

    Returns None instead of raising an exception when MAVFTP is unavailable or
    MAVFTP initialization fails because the underlying MAVLink/serial connection
    is no longer usable.

    Args:
        master: The MAVLink connection object

    Returns:
        MAVFTP: The MAVFTP instance, or None if not available

    """
    if master is None or MAVFTP is None:
        return None
    try:
        return MAVFTP(
            master,
            target_system=master.target_system,
            target_component=master.target_component,
        )
    except Exception as e:  # pylint: disable=broad-exception-caught
        logging_error(_("Failed to initialize MAVFTP: %(error)s"), {"error": str(e)})
        return None
