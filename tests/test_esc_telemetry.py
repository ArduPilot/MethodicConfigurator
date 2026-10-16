#!/usr/bin/env python3
"""
ESC telemetry requests, table readings, lifecycle and workflow integration.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import json
from collections.abc import Generator
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import jsonschema
import pytest
from pymavlink.dialects.v20 import ardupilotmega as mavlink
from telemetry_test_helpers import create_telemetry_link, feed

from ardupilot_methodic_configurator.__main__ import register_plugins
from ardupilot_methodic_configurator.backend_esc_telemetry import EscTelemetryBackend
from ardupilot_methodic_configurator.data_model_esc_telemetry import (
    EscTelemetryDataModel,
    EscTelemetryReading,
    EscTelemetrySnapshot,
)
from ardupilot_methodic_configurator.frontend_tkinter_base_window import BaseWindow
from ardupilot_methodic_configurator.frontend_tkinter_navigation_lock import NavigationLock
from ardupilot_methodic_configurator.plugins import frontend_tkinter_esc_telemetry as frontend
from ardupilot_methodic_configurator.plugins.frontend_tkinter_esc_rpm_scale import EscRpmScaleView
from ardupilot_methodic_configurator.plugins.plugin_constants import PLUGIN_ESC_TELEMETRY
from ardupilot_methodic_configurator.plugins.plugin_factory import PluginFactory, PluginModelContext

# pylint: disable=protected-access,redefined-outer-name


@pytest.fixture
def link() -> SimpleNamespace:
    """Provide a real MAVLink parser with an isolated byte transport."""
    result = create_telemetry_link()
    result.master.target_system = 1
    result.master.target_component = 1
    return result


@pytest.fixture
def model(link: SimpleNamespace) -> EscTelemetryDataModel:
    return EscTelemetryDataModel(link.controller)


def packet(count: int = 10, rpm: int = 1200) -> mavlink.MAVLink_esc_telemetry_1_to_4_message:
    """Represent one populated ESC followed by three unused group members."""
    return mavlink.MAVLink_esc_telemetry_1_to_4_message(
        [42, 0, 0, 0], [2450, 0, 0, 0], [123, 0, 0, 0], [77, 0, 0, 0], [rpm, 0, 0, 0], [count, 0, 0, 0]
    )


@pytest.mark.parametrize("start", [1, 5, 9, 13, 17, 21, 25, 29])
def test_received_esc_groups_appear_in_the_correct_columns(
    link: SimpleNamespace, model: EscTelemetryDataModel, start: int
) -> None:
    """
    Encoded telemetry for any of ArduPilot's eight ESC groups.

    GIVEN encoded telemetry for any of ArduPilot's eight ESC groups,
    WHEN the shared backend and model read it,
    THEN units and column positions match the FC and unused columns show dashes.
    """
    backend = EscTelemetryBackend(link.controller, lambda: link.now)
    message_type = getattr(mavlink, f"MAVLink_esc_telemetry_{start}_to_{start + 3}_message")
    feed(
        link,
        message_type(
            *[getattr(packet(), name) for name in ("temperature", "voltage", "current", "totalcurrent", "rpm", "count")]
        ),
    )
    try:
        rows = model.update(backend.poll())
        assert [row[start - 1] for row in rows] == ["1200", "24.50", "1.23", "42", "77", "10"]
        assert all(value == "-" for row in rows for column, value in enumerate(row) if column != start - 1)
        assert len(rows[0]) == max(16, start)
        assert len(link.master.message_hooks) == 1
    finally:
        backend.close()
    assert not link.master.message_hooks


def test_missing_and_stale_escs_are_unavailable(model: EscTelemetryDataModel) -> None:
    """
    An empty table and one reporting ESC.

    GIVEN an empty table and one reporting ESC,
    WHEN packets stop or the FC repeats a frozen telemetry counter,
    THEN all measurements expire instead of showing old values indefinitely.
    """
    connection = object()
    assert all(value == "-" for row in model.update(EscTelemetrySnapshot(connection, 0)) for value in row)
    reading = EscTelemetryReading((0, 1200, 0, 0, 0, 10))
    rows = model.update(EscTelemetrySnapshot(connection, 0, {15: reading}))
    assert [row[15] for row in rows] == ["0", "12.00", "0.00", "0", "0", "10"]
    rows = model.update(EscTelemetrySnapshot(connection, 3, {15: reading}))
    assert all(row[15] == "-" for row in rows)
    rows = model.update(EscTelemetrySnapshot(connection, 4, {15: EscTelemetryReading((0, 1200, 0, 0, 0, 11))}))
    assert rows[1][15] == "12.00"


def test_rpm_only_telemetry_does_not_invent_electrical_readings(model: EscTelemetryDataModel) -> None:
    """
    Bidirectional DShot RPM with no telemetry packets.

    GIVEN bidirectional DShot RPM with no telemetry packets,
    WHEN ArduPilot zero-fills the other fields,
    THEN RPM appears and the electrical measurements remain unavailable.
    """
    rows = model.update(EscTelemetrySnapshot(object(), 0, {0: EscTelemetryReading((1500, 0, 0, 0, 0, 0))}))
    assert rows[0][0] == "1500"
    assert all(row[0] == "-" for row in rows[1:])


def test_counter_wrap_and_connection_boundaries(model: EscTelemetryDataModel) -> None:
    """
    A reporting ESC near counter wrap.

    GIVEN a reporting ESC near counter wrap,
    WHEN its counter wraps, the connection changes or a read fails,
    THEN fresh values survive wrap and old connection values disappear.
    """
    connection = object()
    model.update(EscTelemetrySnapshot(connection, 0, {0: EscTelemetryReading((20, 100, 0, 0, 0, 65535))}))
    rows = model.update(EscTelemetrySnapshot(connection, 4, {0: EscTelemetryReading((20, 100, 0, 0, 0, 0))}))
    assert rows[5][0] == "0"
    assert all(row[0] == "-" for row in model.update(EscTelemetrySnapshot(object(), 4)))
    model.update(EscTelemetrySnapshot(connection, 5, {0: EscTelemetryReading((20, 100, 0, 0, 0, 1))}))
    assert all(row[0] == "-" for row in model.update(EscTelemetrySnapshot(connection, 5, error=True)))


@pytest.mark.parametrize("source", [(2, 1), (1, 2)])
def test_other_vehicle_packets_cannot_replace_target_escs(link: SimpleNamespace, source: tuple[int, int]) -> None:
    """
    A shared MAVLink transport.

    GIVEN a shared MAVLink transport,
    WHEN another system or component sends telemetry,
    THEN the target FC's ESC table stays empty.
    """
    backend = EscTelemetryBackend(link.controller, lambda: link.now)
    feed(link, packet(), *source)
    try:
        assert not backend.poll().readings
    finally:
        backend.close()


def test_requests_are_bounded_and_do_not_change_stream_rates(link: SimpleNamespace) -> None:
    """
    Repeated polls over a working connection.

    GIVEN repeated polls over a working connection,
    WHEN time passes and monitoring resumes,
    THEN one request per second asks the shared ESC sender for all groups.
    """
    backend = EscTelemetryBackend(link.controller, lambda: link.now)
    try:
        for now in (0, 0.25, 0.5, 0.75, 1, 20):
            link.now = now
            backend.poll()
        assert link.master.write.call_count == 3
        decoder = mavlink.MAVLink(None)
        for call in link.master.write.call_args_list:
            command = decoder.parse_char(call.args[0])
            assert command.command == mavlink.MAV_CMD_REQUEST_MESSAGE
            assert command.param1 == mavlink.MAVLINK_MSG_ID_ESC_TELEMETRY_1_TO_4
            assert (command.target_system, command.target_component) == (1, 1)
        backend.close()
        backend.poll()
        assert link.master.write.call_count == 4
    finally:
        backend.close()


def test_backend_recovers_from_disconnect_and_io_failure(link: SimpleNamespace) -> None:
    """
    A failed telemetry write.

    GIVEN a failed telemetry write,
    WHEN the transport recovers or is disconnected,
    THEN observations restart without leaking hooks or retaining old readings.
    """
    backend = EscTelemetryBackend(link.controller, lambda: link.now)
    link.master.write.side_effect = OSError("disconnected")
    assert backend.poll().error
    assert not link.master.message_hooks
    link.master.write.side_effect = None
    assert not backend.poll().error
    assert len(link.master.message_hooks) == 1
    link.controller.master = None
    assert backend.poll().connection is None
    assert not link.master.message_hooks


@pytest.fixture
def view(tk_root, link: SimpleNamespace) -> Generator[frontend.EscTelemetryView, None, None]:
    """Use real widgets with rendering suppressed for macOS CI."""
    with (
        patch("tkinter.Misc.update"),
        patch("tkinter.Misc.update_idletasks"),
        patch("tkinter.Misc.wait_visibility"),
        patch("tkinter.Misc.wait_window"),
    ):
        base = MagicMock(spec=BaseWindow)
        base.navigation_lock = NavigationLock()
        result = frontend.EscTelemetryView(tk_root, EscTelemetryDataModel(link.controller), base)
        try:
            yield result
        finally:
            if result.winfo_exists():
                result.destroy()


def poll_view(view: frontend.EscTelemetryView) -> None:
    """Run a scheduled callback directly without leaving a duplicate timer."""
    view.after_cancel(view._timer_id)
    view._poll()


def test_treeview_refreshes_and_releases_resources(view: frontend.EscTelemetryView, link: SimpleNamespace) -> None:
    """
    A six-row table with 16 ESC columns.

    GIVEN a six-row table with 16 ESC columns,
    WHEN telemetry arrives and the plugin is suspended and resumed,
    THEN values refresh, callbacks detach and exactly one receiver restarts.
    """
    assert len(view.table.get_children()) == 6
    assert len(view.table.cget("displaycolumns")) == 16
    assert view.table.item("0", "values") == ("-",) * 16
    feed(link, packet())
    poll_view(view)
    values = view.table.item("1", "values")
    assert isinstance(values, tuple)
    assert values[0] == "24.50"
    timer = view._timer_id
    view.on_suspend()
    assert timer not in view.tk.call("after", "info")
    assert not link.master.message_hooks
    assert view.table.item("0", "values") == ("-",) * 16
    view.on_resume()
    resumed = view._timer_id
    view.on_activate()
    assert view._timer_id == resumed
    view.destroy()
    assert resumed not in view.tk.call("after", "info")


def test_upload_lock_and_modal_dialog_pause_reads(view: frontend.EscTelemetryView, link: SimpleNamespace) -> None:
    """
    An exclusive FC operation or modal tool.

    GIVEN an exclusive FC operation or modal tool,
    WHEN a refresh timer runs,
    THEN the view yields the receive loop and schedules a later refresh.
    """
    view.base_window.navigation_lock.acquire("test")
    try:
        poll_view(view)
        assert not link.master.message_hooks
    finally:
        view.base_window.navigation_lock.release("test")
    view.grab_set()
    try:
        poll_view(view)
        assert not link.master.message_hooks
    finally:
        view.grab_release()


@pytest.mark.parametrize("scripting", [False, True])
def test_plugin_factories_preserve_scripting_controls(
    view: frontend.EscTelemetryView, link: SimpleNamespace, scripting: bool
) -> None:
    """
    Normal plugin dependencies with or without scripting telemetry.

    GIVEN normal plugin dependencies with or without scripting telemetry,
    WHEN startup and factory dispatch create step 09,
    THEN the FC-required table appears and scripting keeps its RPM-scale controls.
    """
    factory = PluginFactory()
    filesystem = MagicMock()
    filesystem.vehicle_components_fs.data = {
        "Components": {"ESC": {"ESC->FC Telemetry": {"Protocol": "Scripting" if scripting else "BLHeli32"}}}
    }
    with patch.object(frontend, "plugin_factory", factory):
        frontend.register_esc_telemetry_plugin()
    context = PluginModelContext(link.controller, filesystem, MagicMock())
    plugin_model = factory.create_model(PLUGIN_ESC_TELEMETRY, context)
    assert isinstance(plugin_model, frontend.EscTelemetryPluginModel)
    assert factory.requires_flight_controller(PLUGIN_ESC_TELEMETRY)
    result = factory.create(PLUGIN_ESC_TELEMETRY, view, plugin_model, view.base_window)
    assert isinstance(result, frontend.EscTelemetryView)
    try:
        assert any(isinstance(child, EscRpmScaleView) for child in result.winfo_children()) is scripting
    finally:
        result.destroy()
    with patch.object(frontend, "register_esc_telemetry_plugin") as registration, patch.object(PluginFactory, "register"):
        register_plugins()
    registration.assert_called_once()


@pytest.mark.parametrize("vehicle", ["ArduCopter", "ArduPlane", "Heli", "Rover"])
def test_step_09_enables_telemetry_for_all_supported_vehicle_families(vehicle: str) -> None:
    """
    A bundled vehicle workflow.

    GIVEN a bundled vehicle workflow,
    WHEN step 09 is loaded and validated,
    THEN telemetry is available for every protocol and the configuration matches the schema.
    """
    package = Path(frontend.__file__).parents[1]
    configuration = json.loads((package / f"configuration_steps_{vehicle}.json").read_text(encoding="utf-8"))
    schema = json.loads((package / "configuration_steps_schema.json").read_text(encoding="utf-8"))
    jsonschema.validate(configuration, schema)
    plugin = configuration["steps"]["09_esc_telemetry.param"]["plugin"]
    assert plugin == {"name": PLUGIN_ESC_TELEMETRY, "placement": "top"}


def test_last_esc_column_is_revealed_and_cleared_on_disconnect(view: frontend.EscTelemetryView, link: SimpleNamespace) -> None:
    """
    Reveal the last supported ESC only when data arrives.

    GIVEN the initial 16-column table,
    WHEN ESC 32 reports and the connection is subsequently removed,
    THEN its column appears with converted values and disconnect restores unknown readings.
    """
    feed(
        link,
        mavlink.MAVLink_esc_telemetry_29_to_32_message(
            [0, 0, 0, 50], [0, 0, 0, 1234], [0, 0, 0, 50], [0, 0, 0, 12], [0, 0, 0, 100], [0, 0, 0, 1]
        ),
    )
    poll_view(view)
    assert len(view.table.cget("displaycolumns")) == 32
    values = view.table.item("1", "values")
    assert isinstance(values, tuple)
    assert values[31] == "12.34"
    link.controller.master = None
    poll_view(view)
    assert len(view.table.cget("displaycolumns")) == 16
    assert view.table.item("1", "values") == ("-",) * 16


def test_busy_links_have_bounded_reads_and_preserve_other_observers(link: SimpleNamespace) -> None:
    """
    Keep telemetry responsive on a busy shared connection.

    GIVEN more packets than one UI refresh should drain and an existing observer,
    WHEN telemetry polls, replaces its connection and closes,
    THEN reads are bounded and the unrelated observer stays registered on the old connection.
    """
    observer = MagicMock()
    link.master.message_hooks.append(observer)
    for _index in range(250):
        feed(link, mavlink.MAVLink_heartbeat_message(2, 3, 0, 0, 3, 3))
    backend = EscTelemetryBackend(link.controller, lambda: link.now)
    backend.poll()
    assert observer.call_count == 200
    replacement = create_telemetry_link()
    link.controller.master = replacement.master
    backend.poll()
    assert link.master.message_hooks == [observer]
    assert len(replacement.master.message_hooks) == 1
    backend.close()
    assert not replacement.master.message_hooks
