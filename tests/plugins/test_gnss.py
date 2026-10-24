#!/usr/bin/env python3
"""
GNSS receiver readings, shared telemetry and lifecycle behavior.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import json
import tkinter as tk
from collections.abc import Callable, Generator
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import jsonschema
import pytest
from pymavlink.dialects.v20 import ardupilotmega as mavlink
from telemetry_test_helpers import connected_telemetry_link, feed

from ardupilot_methodic_configurator.__main__ import register_plugins
from ardupilot_methodic_configurator.data_model_data_telemetry import MessageSample, TelemetrySample
from ardupilot_methodic_configurator.frontend_tkinter_base_window import BaseWindow
from ardupilot_methodic_configurator.frontend_tkinter_navigation_lock import NavigationLock
from ardupilot_methodic_configurator.plugins.backend_gnss import GnssBackend
from ardupilot_methodic_configurator.plugins.data_model_gnss import GnssDataModel
from ardupilot_methodic_configurator.plugins.frontend_tkinter_gnss import GnssView
from ardupilot_methodic_configurator.plugins.plugin_factory import PluginModelContext, plugin_factory

# pylint: disable=redefined-outer-name,protected-access


@pytest.fixture
def link() -> Generator[SimpleNamespace, None, None]:
    """Use real MAVLink encoding and parsing with in-memory byte transport."""
    for connection in connected_telemetry_link():
        connection.master.target_system = 1
        connection.master.target_component = 1
        yield connection


@pytest.fixture
def sample() -> TelemetrySample:
    """Provide a fresh fix with zero longitude and negative MSL height."""
    fields = {
        "fix_type": "6",
        "lat": "521234567",
        "lon": "0",
        "alt": "-12345",
        "time_usec": "123000000",
        "satellites_visible": "19",
        "h_acc": "450",
        "v_acc": "800",
    }
    message = MessageSample(1, 52, 10.0, tuple(fields.items()))
    return TelemetrySample(
        SimpleNamespace(target_system=1, target_component=1), 10.0, messages={(1, 1, "GPS_RAW_INT"): message}
    )


def test_receiver_values_use_correct_units_and_boot_time(sample: TelemetrySample) -> None:
    """
    Display the receiver's fix without substituting vehicle position estimates.

    GIVEN: A fixed RTK report with scaled coordinates, negative height and uncertainties.
    WHEN: Its readings are displayed.
    THEN: Degrees, metres, satellite count and explicitly labelled boot time are correct.
    """
    rows = GnssDataModel(MagicMock()).update(sample)
    assert rows[0] == ("RTK fixed", "52.1234567", "0.0000000", "-12.345", "123.0 s since boot", "19", "0.450", "0.800")
    assert rows[1] == ("Waiting for GNSS data", *("N/A" for _index in range(7)))


@pytest.mark.parametrize("fix", ["0", "1", "2"])
def test_no_fix_and_2d_fix_hide_unusable_coordinates(sample: TelemetrySample, fix: str) -> None:
    """
    A fresh packet does not imply a valid position.

    GIVEN: A receiver without a 3D fix.
    WHEN: Its readings are displayed.
    THEN: Height and accuracy are unavailable, and coordinates require a 2D fix.
    """
    fields = dict(sample.messages[(1, 1, "GPS_RAW_INT")].fields)
    fields["fix_type"] = fix
    sample.messages[(1, 1, "GPS_RAW_INT")] = MessageSample(1, 52, 10, tuple(fields.items()))
    row = GnssDataModel(MagicMock()).update(sample)[0]
    assert row[3] == row[6] == row[7] == "N/A"
    assert (row[1] == "N/A") is (fix != "2")
    assert row[5] == "19"


@pytest.mark.parametrize("value", ["0", "nan", "inf", "bad", "4294967295"])
def test_unknown_accuracy_is_not_reported_as_perfect_accuracy(sample: TelemetrySample, value: str) -> None:
    """
    Missing accuracy extensions are distinct from measured accuracy.

    GIVEN: Zero, invalid or unsupported accuracy fields.
    WHEN: A report is interpreted.
    THEN: Accuracy displays N/A while a valid position remains visible.
    """
    fields = dict(sample.messages[(1, 1, "GPS_RAW_INT")].fields)
    fields.update(h_acc=value, v_acc=value, satellites_visible="255")
    sample.messages[(1, 1, "GPS_RAW_INT")] = MessageSample(1, 52, 10, tuple(fields.items()))
    row = GnssDataModel(MagicMock()).update(sample)[0]
    assert row[5:] == ("N/A", "N/A", "N/A")
    assert row[1] == "52.1234567"


def test_time_secondary_receiver_and_stale_data_remain_independent(sample: TelemetrySample) -> None:
    """
    Receiver and clock freshness are checked independently.

    GIVEN: Two receiver reports and a fresh UTC clock.
    WHEN: One receiver expires, then the connection is lost.
    THEN: UTC is shown and each unavailable receiver clears its old readings.
    """
    model = GnssDataModel(MagicMock())
    sample.messages[(1, 1, "SYSTEM_TIME")] = MessageSample(1, 20, 10, (("time_unix_usec", "1700000000000000"),))
    sample.messages[(1, 1, "GPS2_RAW")] = replace(sample.messages[(1, 1, "GPS_RAW_INT")], last_seen=7)
    rows = model.update(sample)
    assert rows[0][4] == "2023-11-14 22:13:20 UTC"
    assert rows[1][0] == "Waiting for GNSS data"
    assert model.update(replace(sample, time=13))[0][1] == "N/A"
    assert model.update(replace(sample, connection=None))[0][0] == "Disconnected"
    assert model.update(replace(sample, error=True))[0][0] == "Connection error"
    sample.messages[(2, 1, "GPS_RAW_INT")] = sample.messages.pop((1, 1, "GPS_RAW_INT"))
    assert model.update(sample)[0][1] == "N/A"


def test_monitor_requests_and_parses_real_gnss_packets_without_changing_stream_rates(link: SimpleNamespace) -> None:
    """
    Shared reception provides real telemetry without blocking acknowledgment waits.

    GIVEN: An in-memory MAVLink connection and an active GNSS monitor.
    WHEN: GNSS reports arrive and the monitor polls repeatedly.
    THEN: Values decode correctly, requests are bounded and cleanup detaches the hook.
    """
    backend = GnssBackend(link.controller, clock=lambda: link.now)
    backend.poll()
    with patch.object(link.master.mav, "command_long_send") as send:
        link.now = 1
        feed(
            link,
            mavlink.MAVLink_gps_raw_int_message(
                123000000, 3, 520000000, 130000000, 12000, 80, 120, 0, 0, 10, h_acc=500, v_acc=900
            ),
        )
        sample = backend.poll()
        assert GnssDataModel(link.controller).update(sample)[0][1] == "52.0000000"
        assert send.call_count == 3
        assert {call.args[4] for call in send.call_args_list} == {24, 124, 2}
        assert all(call.args[2] == 512 for call in send.call_args_list)
        backend.poll()
        assert send.call_count == 3
        backend.close()
        assert not link.master.message_hooks
        backend.poll()
        assert send.call_count == 6
    backend.close()


def test_registered_view_updates_and_yields_the_connection(
    tk_root: tk.Tk, link: SimpleNamespace, fire_tk_timer: Callable[[tk.Misc, str], None]
) -> None:
    """
    The GNSS plugin has real factories, widgets and a cancellable receive lifecycle.

    GIVEN: A registered GNSS plugin on a connected controller.
    WHEN: Reports arrive, then polling is suspended and resumed.
    THEN: Values update, locks prevent reception and cleanup removes timers and hooks.
    """
    register_plugins()
    assert plugin_factory.requires_flight_controller("gnss")
    model = plugin_factory.create_model("gnss", PluginModelContext(link.controller, MagicMock(), MagicMock()))
    assert isinstance(model, GnssDataModel)
    window = MagicMock(spec=BaseWindow)
    window.navigation_lock = NavigationLock()
    view = plugin_factory.create("gnss", tk.Frame(tk_root), model, window)
    assert isinstance(view, GnssView)
    try:
        view.backend.poll()
        feed(link, mavlink.MAVLink_gps_raw_int_message(123000000, 3, 520000000, 130000000, 12000, 80, 120, 0, 0, 10))
        assert view._timer_id is not None
        fire_tk_timer(view, view._timer_id)
        assert view.values[0][1].get() == "52.0000000, 13.0000000"
        view.on_suspend()
        assert view._timer_id is None
        assert not link.master.message_hooks
        assert view.values[0][1].get() == "N/A"
        view.on_resume()
        timer = view._timer_id
        view.on_activate()
        assert timer is not None
        assert view._timer_id == timer
        with patch.object(view.backend, "poll") as poll:
            window.navigation_lock.acquire(view)
            try:
                fire_tk_timer(view, timer)
            finally:
                window.navigation_lock.release(view)
            poll.assert_not_called()
    finally:
        view.destroy()
    assert not link.master.message_hooks


@pytest.mark.parametrize("vehicle", ["ArduCopter", "ArduPlane", "Heli", "Rover"])
def test_gnss_configuration_steps_enable_the_registered_plugin(vehicle: str) -> None:
    """
    All bundled vehicle families provide live GNSS monitoring.

    GIVEN: A vehicle's bundled steps and shared schema.
    WHEN: The GNSS step is loaded.
    THEN: Its plugin configuration is valid and selects the GNSS display.
    """
    root = Path(__file__).resolve().parents[2] / "ardupilot_methodic_configurator"
    data = json.loads((root / f"configuration_steps_{vehicle}.json").read_text(encoding="utf-8"))
    jsonschema.validate(data, json.loads((root / "configuration_steps_schema.json").read_text(encoding="utf-8")))
    steps = [step for name, step in data["steps"].items() if name.endswith("_gnss.param") and "instead_of" not in name]
    assert len(steps) == 1
    assert steps[0]["plugin"] == {"name": "gnss", "placement": "top"}
