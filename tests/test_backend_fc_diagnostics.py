#!/usr/bin/env python3

"""
Exercise diagnostics reception with PyMAVLink's real packet parser.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

from collections.abc import Callable
from datetime import datetime, timezone
from unittest.mock import patch

import pytest
from pymavlink import mavutil
from pymavlink.dialects.v20 import ardupilotmega as mavlink

import ardupilot_methodic_configurator.backend_flightcontroller_connection as connection_module
from ardupilot_methodic_configurator.backend_flightcontroller_connection import FlightControllerConnection
from ardupilot_methodic_configurator.data_model_flightcontroller_info import FlightControllerInfo

# pylint: disable=redefined-outer-name


@pytest.fixture
def diagnostics_connection(monkeypatch: pytest.MonkeyPatch) -> tuple[FlightControllerConnection, Callable[..., None]]:
    """Provide the real receive/parser/hook pipeline with an in-memory transport."""
    # pylint: disable=duplicate-code  # Shared in-memory PyMAVLink transport setup.
    master = mavutil.mavfile(None, "in-memory", input=False)
    master.mav = mavlink.MAVLink(master)
    master.target_system = 1
    master.target_component = 1
    wire = bytearray()

    def recv(count: int) -> bytes:
        data = bytes(wire[:count])
        del wire[:count]
        return data

    def enqueue(text: bytes, system: int = 1, component: int = 1, message_id: int = 0, sequence: int = 0) -> None:
        encoder = mavlink.MAVLink(None, srcSystem=system, srcComponent=component)
        wire.extend(mavlink.MAVLink_statustext_message(4, text, id=message_id, chunk_seq=sequence).pack(encoder))

    monkeypatch.setattr(master, "recv", recv)
    connection = FlightControllerConnection(info=FlightControllerInfo())
    connection.set_master_for_testing(master)
    # pylint: enable=duplicate-code
    return connection, enqueue


def test_opening_diagnostics_receives_queued_messages_without_another_fc_operation(
    diagnostics_connection: tuple[FlightControllerConnection, Callable[..., None]],
) -> None:
    """GIVEN unread wire packets, WHEN diagnostics polls, THEN the latest messages are captured."""
    connection, enqueue = diagnostics_connection
    enqueue(b"New critical diagnostic")
    assert connection.status_text_buffer == []
    assert connection.poll_status_text() == ["New critical diagnostic"]


def test_other_vehicles_and_components_cannot_displace_the_selected_controllers_diagnostics(
    diagnostics_connection: tuple[FlightControllerConnection, Callable[..., None]],
) -> None:
    """GIVEN a shared link, WHEN unrelated packets arrive, THEN only the selected FC is displayed."""
    connection, enqueue = diagnostics_connection
    enqueue(b"Target warning")
    for _index in range(101):
        enqueue(b"Other vehicle", system=2)
        enqueue(b"Other component", component=100)
    assert connection.poll_status_text() == ["Target warning"]


def test_banner_information_is_excluded_from_runtime_history_even_when_repeated(
    diagnostics_connection: tuple[FlightControllerConnection, Callable[..., None]],
) -> None:
    """GIVEN a captured banner, WHEN it is repeated, THEN it appears only in the top buffer."""
    connection, enqueue = diagnostics_connection
    enqueue(b"ArduCopter V4.6.3")
    with (
        patch("ardupilot_methodic_configurator.backend_flightcontroller_connection.time_time", side_effect=[0, 2]),
        patch("ardupilot_methodic_configurator.backend_flightcontroller_connection.time_sleep"),
    ):
        assert connection._receive_banner_text() == ["ArduCopter V4.6.3"]  # pylint: disable=protected-access
    enqueue(b"ArduCopter V4.6.3")
    enqueue(b"Runtime warning")
    assert connection.poll_status_text() == ["Runtime warning"]


def test_banner_burst_is_fully_captured_before_runtime_polling(
    diagnostics_connection: tuple[FlightControllerConnection, Callable[..., None]],
) -> None:
    """GIVEN fifteen queued banner lines, WHEN received, THEN all remain in the banner, with no runtime spillover."""
    connection, enqueue = diagnostics_connection
    expected = [f"Banner line {index}" for index in range(15)]
    for line in expected:
        enqueue(line.encode())
    with (
        patch("ardupilot_methodic_configurator.backend_flightcontroller_connection.time_time", side_effect=[0, 2]),
        patch("ardupilot_methodic_configurator.backend_flightcontroller_connection.time_sleep"),
    ):
        assert connection._receive_banner_text() == expected  # pylint: disable=protected-access

    assert connection.poll_status_text() == []


def test_history_retains_one_hundred_complete_diagnostics_without_counting_banner_or_chunks(
    diagnostics_connection: tuple[FlightControllerConnection, Callable[..., None]],
) -> None:
    """GIVEN over 100 long messages, WHEN captured, THEN the latest 100 complete messages are retained."""
    connection, enqueue = diagnostics_connection
    expected = []
    for index in range(101):
        text = (f"Diagnostic {index}: " + "A" * 60).encode()
        enqueue(text[:50], message_id=index + 1)
        enqueue(text[50:], message_id=index + 1, sequence=1)
        expected.append(text.decode())
    while len(connection.status_text_buffer) < 100:
        connection.poll_status_text()
    connection.poll_status_text()
    assert connection.status_text_buffer == expected[1:]


def test_display_history_is_newest_first_with_local_arrival_times(
    diagnostics_connection: tuple[FlightControllerConnection, Callable[..., None]],
) -> None:
    """
    Displayed diagnostics include local arrival times and put the newest message first.

    GIVEN: Two complete STATUSTEXT packets arrive at known local times
    WHEN: The diagnostics display history is requested
    THEN: Each message has its own local arrival time and the newest appears first
    AND: The raw status buffer remains unformatted and in arrival order
    """
    # Arrange: Use the real MAVLink parser while controlling only the arrival clock.
    connection, enqueue = diagnostics_connection
    received_times = [
        datetime(2026, 10, 13, 12, 34, 56, tzinfo=timezone.utc),
        datetime(2026, 10, 13, 12, 34, 58, tzinfo=timezone.utc),
    ]

    # Act: Parse each packet separately so each completed message receives its own timestamp.
    with patch.object(connection_module, "datetime") as datetime_mock:
        datetime_mock.now.side_effect = received_times
        enqueue(b"Older warning")
        connection.poll_status_text()
        enqueue(b"Newer warning")
        connection.poll_status_text()

    # Assert: Display data is local-time and newest-first without changing the raw API.
    assert connection.status_text_buffer == ["Older warning", "Newer warning"]
    assert connection.status_text_display_buffer == [
        f"[{received_times[1].astimezone():%Y-%m-%d %H:%M:%S}] Newer warning",
        f"[{received_times[0].astimezone():%Y-%m-%d %H:%M:%S}] Older warning",
    ]


def test_reconnect_discards_unfinished_diagnostics(
    diagnostics_connection: tuple[FlightControllerConnection, Callable[..., None]],
) -> None:
    """GIVEN an old unfinished message, WHEN disconnected, THEN its ending cannot contaminate a new session."""
    connection, enqueue = diagnostics_connection
    enqueue(b"A" * 50, message_id=42)
    connection.poll_status_text()
    master = connection.master
    connection.set_master_for_testing(None)
    connection.set_master_for_testing(master)
    enqueue(b"Old ending", message_id=42, sequence=1)
    enqueue(b"New session warning")
    assert connection.poll_status_text() == ["New session warning"]
