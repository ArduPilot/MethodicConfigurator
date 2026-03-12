"""
MAVFTP utility functions.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

from typing import TYPE_CHECKING, Optional, Union

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
) -> Optional[MAVFTP]:  # pyright: ignore[reportGeneralTypeIssues]
    """
    Factory function for creating MAVFTP instances with safe error handling.

    Returns None instead of raising an exception when MAVFTP is unavailable.

    Args:
        master: The MAVLink connection object

    Returns:
        MAVFTP: The MAVFTP instance, or None if not available

    """
    if master is None or MAVFTP is None:
        return None
    return MAVFTP(
        master,
        target_system=master.target_system,
        target_component=master.target_component,
    )
