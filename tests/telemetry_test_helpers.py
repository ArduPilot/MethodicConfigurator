#!/usr/bin/env python3
"""
Shared MAVLink byte transport helpers for telemetry tests.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

from collections.abc import Generator
from io import BytesIO
from types import SimpleNamespace
from unittest.mock import MagicMock

from pymavlink import mavutil
from pymavlink.dialects.v20 import ardupilotmega as mavlink

from ardupilot_methodic_configurator.backend_flightcontroller import FlightController
from ardupilot_methodic_configurator.backend_flightcontroller_connection import FlightControllerConnection
from ardupilot_methodic_configurator.data_model_flightcontroller_info import FlightControllerInfo


def connected_telemetry_link() -> Generator[SimpleNamespace, None, None]:
    """Provide a real parser and connection-owned sender, stopping it after each test."""
    link = create_telemetry_link()
    try:
        yield link
    finally:
        link.controller.disconnect()


def create_telemetry_link() -> SimpleNamespace:
    """Exercise the real MAVLink parser and hooks with only byte transport replaced."""
    controller = MagicMock(spec=FlightController)
    master = mavutil.mavfile(None, "telemetry-test", input=False)
    master.first_byte = False
    master.mav = mavlink.MAVLink(master, srcSystem=255, srcComponent=190)
    master.mav.robust_parsing = True
    incoming = BytesIO()
    master.recv = incoming.read
    master.write = MagicMock()
    controller.master = master
    connection = FlightControllerConnection(FlightControllerInfo())
    connection.master = master
    controller.start_gcs_heartbeat.side_effect = connection.start_gcs_heartbeat
    controller.disconnect.side_effect = connection.disconnect
    return SimpleNamespace(
        controller=controller,
        connection=connection,
        master=master,
        incoming=incoming,
        now=0.0,
        sender=mavlink.MAVLink(None, srcSystem=1, srcComponent=1),
    )


def feed(link: SimpleNamespace, message: mavlink.MAVLink_message, system: int = 1, component: int = 1) -> bytes:
    """Append an encoded MAVLink packet while preserving the current read position."""
    link.sender.srcSystem = system
    link.sender.srcComponent = component
    packet = message.pack(link.sender)
    link.sender.seq = (link.sender.seq + 1) % 256
    position = link.incoming.tell()
    link.incoming.seek(0, 2)
    link.incoming.write(packet)
    link.incoming.seek(position)
    return bytes(packet)
