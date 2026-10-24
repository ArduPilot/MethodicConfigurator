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


def test_receiver_values_use_correct_units_without_substituting_boot_time(sample: TelemetrySample) -> None:
    """
    Display the receiver's fix without substituting vehicle position estimates.

    GIVEN: A fixed RTK report with scaled coordinates, negative height and uncertainties.
    WHEN: Its readings are displayed.
    THEN: Degrees, metres and satellite count are correct, and absent UTC stays unavailable.
    """
    rows = GnssDataModel(MagicMock()).update(sample)
    assert rows[0] == ("RTK fixed", "52.1234567", "0.0000000", "-12.345", "N/A", "19", "0.450", "0.800")
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
    model = GnssDataModel(MagicMock(fc_parameters={"BRD_RTC_TZ_MIN": 0}))
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


@pytest.mark.parametrize("clock_value", [None, "0", "nan"])
def test_boot_timestamps_never_replace_unavailable_utc(sample: TelemetrySample, clock_value: str | None) -> None:
    """
    Boot-relative receiver timestamps never substitute for UTC.

    GIVEN: A GPS report after twelve days with no usable system UTC clock.
    WHEN: Time is displayed.
    THEN: Time is unavailable rather than showing uptime or a 1970 date.
    """
    fields = dict(sample.messages[(1, 1, "GPS_RAW_INT")].fields)
    fields["time_usec"] = "1036800000000"
    sample.messages[(1, 1, "GPS_RAW_INT")] = MessageSample(1, 52, 10, tuple(fields.items()))
    if clock_value is not None:
        sample.messages[(1, 1, "SYSTEM_TIME")] = MessageSample(1, 20, 10, (("time_unix_usec", clock_value),))
    assert GnssDataModel(MagicMock()).update(sample)[0][4] == "N/A"


@pytest.mark.parametrize(("fix", "visible"), [("0", False), ("1", True), ("3", True), ("bad", False)])
def test_second_receiver_visibility_requires_fresh_detected_hardware(sample: TelemetrySample, fix: str, visible: bool) -> None:
    """
    Receiver detection is distinct from acquiring a satellite fix.

    GIVEN: A second receiver report indicating detection or missing hardware.
    WHEN: The report is interpreted, expires, or the connection is lost.
    THEN: Only a fresh detected receiver requests a second display column.
    """
    model = GnssDataModel(MagicMock(fc_parameters={"BRD_RTC_TZ_MIN": 0}))
    model.update(sample)
    assert not model.second_receiver_present
    fields = dict(sample.messages[(1, 1, "GPS_RAW_INT")].fields)
    fields["fix_type"] = fix
    sample.messages[(1, 1, "GPS2_RAW")] = MessageSample(1, 52, 10, tuple(fields.items()))
    model.update(sample)
    assert model.second_receiver_present is visible
    model.update(replace(sample, time=13))
    assert not model.second_receiver_present
    model.update(replace(sample, connection=None))
    assert not model.second_receiver_present


def test_second_receiver_column_follows_live_detection(
    tk_root: tk.Tk, link: SimpleNamespace, fire_tk_timer: Callable[[tk.Misc, str], None]
) -> None:
    """
    Single-receiver installations should not display an empty receiver column.

    GIVEN: A monitor with no second receiver.
    WHEN: A detected receiver without a fix appears and then reports no hardware.
    THEN: Its header and values appear together and disappear together.
    """
    window = MagicMock(spec=BaseWindow)
    window.navigation_lock = NavigationLock()
    view = GnssView(tk.Frame(tk_root), GnssDataModel(link.controller), window)
    try:
        assert all(not widget.winfo_manager() for widget in view._second_receiver_widgets)
        view.backend.poll()
        for fix in (1, 0):
            feed(link, mavlink.MAVLink_gps2_raw_message(123000000, fix, 520000000, 130000000, 12000, 80, 120, 0, 0, 10, 0, 0))
            assert view._timer_id is not None
            fire_tk_timer(view, view._timer_id)
            assert all((widget.winfo_manager() == "grid") is bool(fix) for widget in view._second_receiver_widgets)
        view.on_deactivate()
        assert all(not widget.winfo_manager() for widget in view._second_receiver_widgets)
    finally:
        view.destroy()


@pytest.mark.parametrize(
    ("offset", "expected"),
    [
        (0, "2023-11-14 22:13:20 UTC"),
        (120, "2023-11-15 00:13:20 UTC+02:00"),
        (-720, "2023-11-14 10:13:20 UTC-12:00"),
        (840, "2023-11-15 12:13:20 UTC+14:00"),
        (345, "2023-11-15 03:58:20 UTC+05:45"),
        (-210, "2023-11-14 18:43:20 UTC-03:30"),
    ],
)
def test_local_time_uses_current_fc_timezone_for_both_receivers(sample: TelemetrySample, offset: float, expected: str) -> None:
    """
    Local time follows the vehicle's timezone rather than the computer's timezone.

    GIVEN: Two receivers, valid UTC and a configured minute offset.
    WHEN: Local time is displayed and the FC timezone parameter changes.
    THEN: Both receivers show the correct offset and date rollover, and refresh the offset.
    """
    controller = MagicMock(fc_parameters={"BRD_RTC_TZ_MIN": offset})
    model = GnssDataModel(controller)
    sample.messages[(1, 1, "SYSTEM_TIME")] = MessageSample(1, 20, 10, (("time_unix_usec", "1700000000000000"),))
    sample.messages[(1, 1, "GPS2_RAW")] = sample.messages[(1, 1, "GPS_RAW_INT")]
    assert [row[4] for row in model.update(sample)] == [expected, expected]
    controller.fc_parameters["BRD_RTC_TZ_MIN"] = 0
    assert model.update(sample)[0][4] == "2023-11-14 22:13:20 UTC"


@pytest.mark.parametrize("offset", [None, float("nan"), float("inf"), -721, 841, 1.5])
def test_unknown_or_invalid_timezone_keeps_local_time_unavailable(sample: TelemetrySample, offset: float | None) -> None:
    """
    An unknown timezone must not silently present UTC as local time.

    GIVEN: Valid UTC with a missing or invalid vehicle timezone offset.
    WHEN: Local time is requested.
    THEN: Time is N/A while receiver position remains visible.
    """
    parameters = {} if offset is None else {"BRD_RTC_TZ_MIN": offset}
    model = GnssDataModel(MagicMock(fc_parameters=parameters))
    sample.messages[(1, 1, "SYSTEM_TIME")] = MessageSample(1, 20, 10, (("time_unix_usec", "1700000000000000"),))
    row = model.update(sample)[0]
    assert row[4] == "N/A"
    assert row[1] == "52.1234567"
