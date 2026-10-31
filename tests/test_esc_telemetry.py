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
from pymavlink.dialects.v10 import ardupilotmega as mavlink1
from pymavlink.dialects.v20 import ardupilotmega as mavlink
from telemetry_test_helpers import create_telemetry_link, feed

from ardupilot_methodic_configurator.__main__ import register_plugins
from ardupilot_methodic_configurator.backend_data_telemetry import DataTelemetryBackend
from ardupilot_methodic_configurator.backend_esc_telemetry import EscTelemetryBackend
from ardupilot_methodic_configurator.backend_flightcontroller_commands import FlightControllerCommands
from ardupilot_methodic_configurator.data_model_data_telemetry import TelemetrySample
from ardupilot_methodic_configurator.data_model_esc_telemetry import (
    MAX_ESCS,
    EscTelemetryDataModel,
    EscTelemetryReading,
    EscTelemetrySnapshot,
)
from ardupilot_methodic_configurator.frontend_tkinter_base_window import BaseWindow
from ardupilot_methodic_configurator.frontend_tkinter_navigation_lock import NavigationLock
from ardupilot_methodic_configurator.plugins import frontend_tkinter_esc_telemetry as frontend
from ardupilot_methodic_configurator.plugins.data_model_motor_test import MotorTestDataModel
from ardupilot_methodic_configurator.plugins.frontend_tkinter_esc_rpm_scale import EscRpmScaleView
from ardupilot_methodic_configurator.plugins.plugin_constants import PLUGIN_ESC_TELEMETRY
from ardupilot_methodic_configurator.plugins.plugin_factory import PluginFactory, PluginModelContext

# pylint: disable=protected-access,redefined-outer-name


@pytest.fixture
def link() -> SimpleNamespace:
    """Provide a real MAVLink parser with an isolated byte transport."""
    result = create_telemetry_link()
    result.master.target_system = 1
    result.controller.info.set_system_id_and_component_id("1", "1")
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
        assert model.visible_esc_indices == (start - 1,)
        assert len(link.master.message_hooks) == 1
    finally:
        backend.close()
    assert not link.master.message_hooks


@pytest.mark.parametrize("start", [1, 5, 9, 13, 17, 21, 25, 29])
def test_esc_telemetry_is_displayed_when_connection_initially_detected_mavlink1(
    link: SimpleNamespace, model: EscTelemetryDataModel, start: int
) -> None:
    """
    Decode ESC messages even when the shared connection began in MAVLink 1.

    GIVEN a MAVLink 1 parser and an FC that sends ESC telemetry only after a MAVLink 2 request,
    WHEN the monitor requests and receives an ESC group,
    THEN the correct readings appear without replacing the connection's parser.
    """
    master = link.master
    master.mav = mavlink1.MAVLink(master, srcSystem=255, srcComponent=190)
    master.mav.robust_parsing = True
    master.WIRE_PROTOCOL_VERSION = "1.0"
    parser = master.mav
    message_type = getattr(mavlink, f"MAVLink_esc_telemetry_{start}_to_{start + 3}_message")
    expected = packet()

    def respond_to_request(data: bytes) -> None:
        command = mavlink.MAVLink(None).parse_char(data)
        assert data[0] == 0xFD
        assert command is not None
        assert command.command == mavlink.MAV_CMD_REQUEST_MESSAGE
        feed(
            link,
            message_type(
                *[getattr(expected, name) for name in ("temperature", "voltage", "current", "totalcurrent", "rpm", "count")]
            ),
        )

    master.write.side_effect = respond_to_request
    backend = EscTelemetryBackend(link.controller, lambda: link.now)
    try:
        rows = model.update(backend.poll())
        assert [row[start - 1] for row in rows] == ["1200", "24.50", "1.23", "42", "77", "10"]
        assert model.visible_esc_indices == (start - 1,)
        assert master.mav is parser
    finally:
        backend.close()


def test_invalid_unknown_esc_packet_does_not_display_telemetry(link: SimpleNamespace) -> None:
    """
    Validate packets before using telemetry unknown to a MAVLink 1 parser.

    GIVEN a corrupted MAVLink 2 ESC packet received by a MAVLink 1 parser,
    WHEN the monitor polls,
    THEN the invalid reading is ignored without stopping the observer.
    """
    master = link.master
    master.mav = mavlink1.MAVLink(master, srcSystem=255, srcComponent=190)
    master.mav.robust_parsing = True
    encoded = bytearray(packet().pack(link.sender))
    encoded[-1] ^= 1
    link.incoming.write(encoded)
    link.incoming.seek(0)
    backend = EscTelemetryBackend(link.controller, lambda: link.now)
    try:
        snapshot = backend.poll()
        assert not snapshot.error
        assert not snapshot.readings
        assert backend._capture in master.message_hooks
    finally:
        backend.close()


@pytest.mark.parametrize("source", [(2, 1), (1, 2)])
def test_mavlink1_parser_does_not_accept_esc_packets_from_other_sources(
    link: SimpleNamespace, source: tuple[int, int]
) -> None:
    """
    Filter decoded ESC packets using the actual MAVLink 2 source.

    GIVEN a MAVLink 1 parser and an ESC packet from another system or component,
    WHEN the monitor decodes it,
    THEN the unrelated ESC is not displayed.
    """
    link.master.mav = mavlink1.MAVLink(link.master, srcSystem=255, srcComponent=190)
    link.master.mav.robust_parsing = True
    feed(link, packet(), *source)
    backend = EscTelemetryBackend(link.controller, lambda: link.now)
    try:
        assert not backend.poll().readings
    finally:
        backend.close()


@pytest.mark.parametrize("valid", [True, False])
def test_mavlink1_unknown_esc_packets_respect_connection_signing(link: SimpleNamespace, valid: bool) -> None:
    """
    Preserve the connection's authentication policy while decoding ESC packets.

    GIVEN a MAVLink 1 parser with a signing key and a signed MAVLink 2 ESC packet,
    WHEN the monitor decodes the packet,
    THEN only a packet with a valid signature is accepted.
    """
    link.master.mav = mavlink1.MAVLink(link.master, srcSystem=255, srcComponent=190)
    link.master.mav.robust_parsing = True
    link.master.mav.signing.secret_key = b"a" * 32
    link.sender.signing.secret_key = (b"a" if valid else b"b") * 32
    link.sender.signing.sign_outgoing = True
    link.sender.signing.timestamp = 100
    feed(link, packet())
    backend = EscTelemetryBackend(link.controller, lambda: link.now)
    try:
        snapshot = backend.poll()
        assert not snapshot.error
        assert bool(snapshot.readings) is valid
    finally:
        backend.close()


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
    assert model.visible_esc_indices == (15,)
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
    assert model.visible_esc_indices == (0,)


def test_stopped_bdshot_outputs_from_real_controller_packet_are_visible(link: SimpleNamespace) -> None:
    """
    Show zero-filled packets from the connected controller.

    GIVEN the connected controller's four configured BDShot outputs and an all-zero group 9-12
    WHEN the encoded packet is received and later stops arriving
    THEN ambiguous zero RPMs are shown, electrical data stays unavailable, and RPM expires.
    """
    link.controller.fc_parameters = {"SERVO_BLH_BDMASK": 3840.0, "ESC_TLM_MAV_OFS": 0.0}
    model = EscTelemetryDataModel(link.controller)
    backend = EscTelemetryBackend(link.controller, lambda: link.now)
    feed(link, mavlink.MAVLink_esc_telemetry_9_to_12_message(*([[0] * 4] * 6)))
    try:
        rows = model.update(backend.poll())
        assert model.visible_esc_indices == (8, 9, 10, 11)
        assert rows[0][8:12] == ("0*",) * 4
        assert all(row[8:12] == ("-",) * 4 for row in rows[1:])
        link.now = 3.0
        assert model.update(backend.poll())[0][8:12] == ("-",) * 4
    finally:
        backend.close()


def test_bdshot_zero_padding_respects_mask_and_mavlink_offset(link: SimpleNamespace) -> None:
    """
    Avoid treating unconfigured padding as a BDShot output.

    GIVEN a group containing configured and unconfigured zero-filled outputs and a MAVLink offset
    WHEN the group arrives
    THEN only configured outputs become visible and their RPM is explicitly ambiguous.
    """
    link.controller.fc_parameters = {"SERVO_BLH_BDMASK": float(1 << 9), "ESC_TLM_MAV_OFS": 4.0}
    model = EscTelemetryDataModel(link.controller)
    readings = {index: EscTelemetryReading((0, 0, 0, 0, 0, 0)) for index in range(4, 8)}
    rows = model.update(EscTelemetrySnapshot(object(), 0, readings))
    assert model.visible_esc_indices == (5,)
    assert rows[0][4:8] == ("-", "0*", "-", "-")


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


@pytest.mark.parametrize(
    ("discovered_ids", "target_ids", "source"),
    [
        (("2", "3"), (1, 0), (2, 3)),
        (("", ""), (1, 0), (1, 1)),
        (("", ""), (0, 0), (2, 3)),
    ],
)
def test_discovered_identity_and_broadcast_targets_accept_esc_telemetry(
    link: SimpleNamespace, discovered_ids: tuple[str, str], target_ids: tuple[int, int], source: tuple[int, int]
) -> None:
    """
    Match discovered FC identity without rejecting broadcast component targets.

    GIVEN FC identity or broadcast pymavlink targets after discovery,
    WHEN the matching autopilot sends ESC telemetry,
    THEN its data is accepted and requests use the resolved target IDs.
    """
    link.controller.info.set_system_id_and_component_id(*discovered_ids)
    link.master.target_system, link.master.target_component = target_ids
    feed(link, packet(), *source)
    backend = EscTelemetryBackend(link.controller, lambda: link.now)
    try:
        assert backend.poll().readings[0].values[0] == 1200
        decoder = mavlink.MAVLink(None)
        command = decoder.parse_char(link.master.write.call_args.args[0])
        expected = tuple(
            int(identity) if identity else target for identity, target in zip(discovered_ids, target_ids, strict=True)
        )
        assert (command.target_system, command.target_component) == expected
    finally:
        backend.close()


def test_esc_polling_preserves_battery_readings_for_motor_test_safety(link: SimpleNamespace) -> None:
    """
    Keep motor tests available when the ESC table reads battery packets first.

    GIVEN interleaved ESC and multiple-battery messages on a real MAVLink parser,
    WHEN ESC polling drains them before the motor safety check,
    THEN all battery readings remain available without repeated stream requests.
    """
    controller = link.controller
    controller.fc_parameters = {"FRAME_CLASS": 1.0, "FRAME_TYPE": 1.0, "BATT_MONITOR": 4.0, "BATT2_MONITOR": 4.0}
    commands = FlightControllerCommands(
        params_manager=MagicMock(fc_parameters=controller.fc_parameters), connection_manager=link.connection
    )
    controller.get_battery_statuses.side_effect = commands.get_battery_statuses
    controller.request_periodic_battery_status.return_value = (True, "")
    controller.get_voltage_thresholds.return_value = (10.0, 13.0)
    controller.get_frame_info.return_value = (1, 1)
    motor = MotorTestDataModel(controller, MagicMock(doc_dict={}))
    for battery_id, voltage in ((0, 12000), (1, 24000)):
        feed(link, mavlink.MAVLink_battery_status_message(battery_id, 0, 0, 32767, [voltage] + [65535] * 9, 200, -1, -1, -1))
    feed(link, packet())
    backend = EscTelemetryBackend(controller, lambda: link.now)
    try:
        assert backend.poll().readings[0].values[0] == 1200
        assert commands.get_battery_statuses() == ({0: (12.0, 2.0), 1: (24.0, 2.0)}, "")
        motor.is_motor_test_safe()
        backend.poll()
        motor.is_motor_test_safe()
        controller.request_periodic_battery_status.assert_called_once()
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
        for now in (0, 0.25, 0.5, 0.75, 1, 1.25, 1.75, 20):
            link.now = now
            backend.poll()
        assert link.master.write.call_count == 3
        decoder = mavlink.MAVLink(None)
        for call in link.master.write.call_args_list:
            command = decoder.parse_char(call.args[0])
            assert command.command == mavlink.MAV_CMD_REQUEST_MESSAGE
            assert command.confirmation == 0
            assert (command.param2, command.param3, command.param4, command.param5, command.param6, command.param7) == (0,) * 6
            assert command.param1 == mavlink.MAVLINK_MSG_ID_ESC_TELEMETRY_1_TO_4
            assert (command.target_system, command.target_component) == (1, 1)
        backend.close()
        backend.poll()
        assert link.master.write.call_count == 4
    finally:
        backend.close()


def test_backend_recovers_from_disconnect_and_io_failure(link: SimpleNamespace, caplog: pytest.LogCaptureFixture) -> None:
    """
    A failed telemetry write.

    GIVEN a failed telemetry write,
    WHEN the transport recovers or is disconnected,
    THEN observations restart without leaking hooks or retaining old readings.
    """
    backend = EscTelemetryBackend(link.controller, lambda: link.now)
    link.master.write.side_effect = OSError("disconnected")
    link.now = 12.0
    with caplog.at_level("DEBUG"):
        failed = backend.poll()
    assert failed.error
    assert failed.connection is link.master
    assert failed.time == 12.0
    assert caplog.messages == ["Error reading ESC telemetry: disconnected"]
    assert not link.master.message_hooks
    link.master.write.side_effect = None
    assert not backend.poll().error
    assert len(link.master.message_hooks) == 1
    link.controller.master = None
    link.now = 42.0
    disconnected = backend.poll()
    assert disconnected.connection is None
    assert disconnected.time == 42.0
    assert not link.master.message_hooks


@pytest.fixture
def view(tk_root, link: SimpleNamespace) -> Generator[frontend.EscTelemetryView, None, None]:
    """Use real widgets with rendering suppressed for macOS CI."""
    # Real telemetry widgets need the same macOS rendering stubs in each fixture.
    # pylint: disable=duplicate-code
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
    A six-row table with no detected ESCs.

    GIVEN a six-row table with no detected ESCs,
    WHEN telemetry arrives and the plugin is suspended and resumed,
    THEN values refresh, callbacks detach and exactly one receiver restarts.
    """
    assert len(view.table.get_children()) == 6
    assert not view.table.cget("displaycolumns")
    assert view.table.item("0", "values") == ("-",) * MAX_ESCS
    feed(link, packet())
    poll_view(view)
    values = view.table.item("1", "values")
    assert isinstance(values, tuple)
    assert values[0] == "24.50"
    assert view.table.cget("displaycolumns") == ("1",)
    timer = view._timer_id
    view.on_suspend()
    assert timer not in view.tk.call("after", "info")
    assert not link.master.message_hooks
    assert not view.table.cget("displaycolumns")
    assert view.table.item("0", "values") == ("-",) * MAX_ESCS
    view._poll()  # A cancelled callback must not restart a suspended receiver.
    assert view._timer_id is None
    view.on_resume()
    resumed = view._timer_id
    view.on_activate()
    assert view._timer_id == resumed
    view.destroy()
    assert resumed not in view.tk.call("after", "info")


def test_esc_step_shows_values_from_mavlink1_initial_connection(
    view: frontend.EscTelemetryView, link: SimpleNamespace
) -> None:
    """
    Show the decoded ESC values in the real step table.

    GIVEN a connection that initially selected the MAVLink 1 dialect,
    WHEN an ESC telemetry packet arrives in MAVLink 2,
    THEN the ESC column and its voltage become visible.
    """
    link.master.mav = mavlink1.MAVLink(link.master, srcSystem=255, srcComponent=190)
    link.master.mav.robust_parsing = True
    feed(link, packet())
    poll_view(view)
    assert view.table.cget("displaycolumns") == ("1",)
    values = view.table.item("1", "values")
    assert isinstance(values, tuple)
    assert values[0] == "24.50"


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


@pytest.mark.parametrize(("delay", "expected_rpm"), [(2.5, "1200"), (3.0, "-")])
def test_modal_deferral_preserves_the_age_of_packets_parsed_by_another_reader(
    view: frontend.EscTelemetryView, link: SimpleNamespace, delay: float, expected_rpm: str
) -> None:
    """
    Expire ESC readings from their receipt time after a modal defers polling.

    GIVEN an attached ESC observer and a modal dialog deferring its polling,
    WHEN another reader parses telemetry that stops before the modal closes,
    THEN resuming the table preserves the packet's age for RPM and electrical data.
    """
    view.backend._clock = lambda: link.now
    poll_view(view)
    view.grab_set()
    try:
        link.now = 1.0
        feed(link, packet())
        assert link.master.recv_match(type="BATTERY_STATUS", blocking=False) is None
        link.now += delay
        poll_view(view)
        assert not view.table.cget("displaycolumns")
    finally:
        view.grab_release()
    poll_view(view)
    rpm_values = view.table.item("0", "values")
    voltage_values = view.table.item("1", "values")
    assert isinstance(rpm_values, tuple)
    assert isinstance(voltage_values, tuple)
    assert rpm_values[0] == expected_rpm
    assert voltage_values[0] == ("24.50" if expected_rpm != "-" else "-")


@pytest.mark.parametrize("scripting", [False, True])
def test_plugin_factories_display_telemetry_without_rpm_scaling_controls(
    view: frontend.EscTelemetryView, link: SimpleNamespace, scripting: bool
) -> None:
    """
    Normal plugin dependencies with or without scripting telemetry.

    GIVEN normal plugin dependencies with or without scripting telemetry,
    WHEN startup and factory dispatch create the telemetry plugin,
    THEN the FC-required table appears with RPM scaling left to the motor step.
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
    assert isinstance(plugin_model, EscTelemetryDataModel)
    assert factory.requires_flight_controller(PLUGIN_ESC_TELEMETRY)
    result = factory.create(PLUGIN_ESC_TELEMETRY, view, plugin_model, view.base_window)
    assert isinstance(result, frontend.EscTelemetryView)
    try:
        assert not any(isinstance(child, EscRpmScaleView) for child in result.winfo_children())
    finally:
        result.destroy()
    with patch.object(frontend, "register_esc_telemetry_plugin") as registration, patch.object(PluginFactory, "register"):
        register_plugins()
    registration.assert_called_once()


@pytest.mark.parametrize(("vehicle", "step"), [("ArduCopter", "08"), ("ArduPlane", "08"), ("Heli", "14"), ("Rover", "11")])
def test_esc_telemetry_step_enables_telemetry_for_all_supported_vehicle_families(vehicle: str, step: str) -> None:
    """
    A bundled vehicle workflow.

    GIVEN a bundled vehicle workflow,
    WHEN its ESC telemetry step is loaded and validated,
    THEN telemetry is available for every protocol and the configuration matches the schema.
    """
    package = Path(frontend.__file__).parents[1]
    configuration = json.loads((package / f"configuration_steps_{vehicle}.json").read_text(encoding="utf-8"))
    schema = json.loads((package / "configuration_steps_schema.json").read_text(encoding="utf-8"))
    jsonschema.validate(configuration, schema)
    plugin = configuration["steps"][f"{step}_esc_telemetry.param"]["plugin"]
    assert plugin == {"name": PLUGIN_ESC_TELEMETRY, "placement": "top"}


def test_last_esc_column_is_revealed_and_cleared_on_disconnect(view: frontend.EscTelemetryView, link: SimpleNamespace) -> None:
    """
    Reveal the last supported ESC only when data arrives.

    GIVEN a table with no detected ESCs,
    WHEN ESC 32 reports and the connection is subsequently removed,
    THEN only its column appears with converted values and disconnect hides it.
    """
    feed(
        link,
        mavlink.MAVLink_esc_telemetry_29_to_32_message(
            [0, 0, 0, 50], [0, 0, 0, 1234], [0, 0, 0, 50], [0, 0, 0, 12], [0, 0, 0, 100], [0, 0, 0, 1]
        ),
    )
    poll_view(view)
    assert view.table.cget("displaycolumns") == ("32",)
    values = view.table.item("1", "values")
    assert isinstance(values, tuple)
    assert values[31] == "12.34"
    link.controller.master = None
    poll_view(view)
    assert not view.table.cget("displaycolumns")
    assert view.table.item("1", "values") == ("-",) * MAX_ESCS


def test_sparse_esc_columns_keep_their_numbers_and_ignore_unused_slots(view: frontend.EscTelemetryView) -> None:
    """
    Show sparse telemetry without filling gaps with empty columns.

    GIVEN nonadjacent ESCs and unused slots in a telemetry group,
    WHEN telemetry includes a stopped reporting ESC and RPM-only telemetry,
    THEN only detected ESCs appear in numeric order with their own measurements.
    """
    rows = view.model.update(
        EscTelemetrySnapshot(
            object(),
            0,
            {
                7: EscTelemetryReading((1500, 0, 0, 0, 0, 0)),
                1: EscTelemetryReading((0, 1200, 0, 0, 0, 10)),
                2: EscTelemetryReading((0, 0, 0, 0, 0, 0)),
                3: EscTelemetryReading((0, 1200, 0, 0, 0, 0)),
            },
        )
    )
    view._show_rows(rows)
    assert view.table.cget("displaycolumns") == ("2", "8")
    rpm_values = view.table.item("0", "values")
    voltage_values = view.table.item("1", "values")
    assert isinstance(rpm_values, tuple)
    assert isinstance(voltage_values, tuple)
    assert rpm_values[7] == "1500"
    assert voltage_values[1] == "12.00"
    assert view.table.column("8", "width") == 55
    assert view.table.column("8", "stretch") == 0


@pytest.mark.parametrize("backend_type", [EscTelemetryBackend, DataTelemetryBackend])
def test_busy_links_have_bounded_reads_and_preserve_other_observers(
    link: SimpleNamespace, backend_type: type[EscTelemetryBackend] | type[DataTelemetryBackend]
) -> None:
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
    backend = backend_type(link.controller, lambda: link.now)
    backend.poll()
    assert observer.call_count == 200
    replacement = create_telemetry_link()
    link.controller.master = replacement.master
    backend.poll()
    assert link.master.message_hooks == [observer]
    assert len(replacement.master.message_hooks) == 1
    backend.close()
    assert not replacement.master.message_hooks


@pytest.mark.parametrize("backend_type", [EscTelemetryBackend, DataTelemetryBackend])
def test_slow_packets_stop_both_telemetry_polls_at_the_time_budget(
    link: SimpleNamespace, backend_type: type[EscTelemetryBackend] | type[DataTelemetryBackend]
) -> None:
    """
    Bound elapsed work even when packet processing is slow.

    GIVEN a backlog whose observer takes six milliseconds to process each packet
    WHEN the telemetry backend polls with a ten-millisecond budget
    THEN only two packets are read and closing the backend preserves the other observer
    """

    def advance_clock(_master: object, _message: object) -> None:
        link.now += 0.006

    observer = MagicMock(side_effect=advance_clock)
    link.master.message_hooks.append(observer)
    for _index in range(10):
        feed(link, mavlink.MAVLink_heartbeat_message(2, 3, 0, 0, 3, 3))
    backend = backend_type(link.controller, lambda: link.now)
    try:
        backend.poll()
        assert observer.call_count == 2
    finally:
        backend.close()
    assert link.master.message_hooks == [observer]


def test_reusable_esc_table_labels_identify_every_measurement_and_its_units() -> None:
    """
    Keep measurement labels and engineering units consistent in every ESC table host.

    GIVEN: The reusable ESC telemetry model
    WHEN: A host requests its row labels
    THEN: The six labels distinguish RPM, electrical units, temperature, consumption and packet count
    """
    assert EscTelemetryDataModel.row_labels() == (
        "RPM",
        "Voltage (V)",
        "Current (A)",
        "Temperature (°C)",
        "Consumption (mAh)",
        "Telemetry packets",
    )


def test_model_keeps_exactly_32_esc_columns_and_ignores_unusable_snapshot_entries(model: EscTelemetryDataModel) -> None:
    """
    Preserve the table shape and discard invalid or unused ESC entries.

    GIVEN: First and last ESC readings alongside out-of-range, incomplete and zero-padded entries
    WHEN: A reusable table host updates the model
    THEN: Only ESCs 1 and 32 are detected and every measurement row has exactly 32 columns
    """
    reading = EscTelemetryReading((1200, 2450, 123, 42, 77, 10), received_at=1.0)
    entries = {
        0: reading,
        31: reading,
        -1: reading,
        32: reading,
        1: EscTelemetryReading((0,) * 6),
        2: EscTelemetryReading((1200, 2450)),
    }
    rows = model.update(EscTelemetrySnapshot(object(), 1.0, entries))
    assert model.visible_esc_indices == (0, 31)
    assert len(rows) == 6
    assert all(len(row) == 32 for row in rows)
    assert [row[31] for row in rows] == ["1200", "24.50", "1.23", "42", "77", "10"]
    assert all(row[index] == "-" for row in rows for index in range(1, 31))


def test_rpm_updates_independently_of_a_frozen_electrical_telemetry_counter(model: EscTelemetryDataModel) -> None:
    """
    Preserve faster RPM measurements while electrical telemetry waits for its next packet.

    GIVEN: An ESC reports electrical telemetry and a packet count of ten
    WHEN: RPM changes without the electrical packet counter advancing
    THEN: RPM updates immediately while voltage retains the last measured value.
    """
    connection = object()
    first = EscTelemetryReading((1000, 1200, 0, 25, 0, 10))
    model.update(EscTelemetrySnapshot(connection, 0.0, {0: first}))
    latest = EscTelemetryReading((2000, 1300, 0, 25, 0, 10))
    rows = model.update(EscTelemetrySnapshot(connection, 1.0, {0: latest}))
    assert rows[0][0] == "2000"
    assert rows[1][0] == "12.00"


@pytest.mark.parametrize("failed", [True, False])
def test_invalid_snapshots_cannot_repopulate_live_esc_readings(model: EscTelemetryDataModel, failed: bool) -> None:
    """
    Discard observations attached to an error or disconnected snapshot.

    GIVEN: Cached ESC telemetry followed by a snapshot with an error or no connection
    WHEN: The invalid snapshot still contains observations
    THEN: All visible ESCs and displayed values are cleared.
    """
    connection = object()
    readings = {0: EscTelemetryReading((1000, 1200, 0, 25, 0, 10))}
    model.update(EscTelemetrySnapshot(connection, 0.0, readings))
    rows = model.update(EscTelemetrySnapshot(connection if failed else None, 1.0, readings, error=failed))
    assert model.visible_esc_indices == ()
    assert all(value == "-" for row in rows for value in row)


@pytest.mark.parametrize(("elapsed", "requests"), [(0.999, 1), (1.0, 2), (1.001, 2), (5.0, 2)])
def test_esc_request_is_due_at_exactly_one_second_without_catching_up_after_a_pause(
    link: SimpleNamespace, elapsed: float, requests: int
) -> None:
    """
    Request ESC telemetry at its deadline without flooding a resumed connection.

    GIVEN: An initial ESC request sent at time zero
    WHEN: Polling resumes just before, at, or after its one-second deadline
    THEN: A due request is sent immediately and missed intervals never produce a burst
    """
    backend = EscTelemetryBackend(link.controller, lambda: link.now)
    try:
        backend.poll()
        assert link.master.write.call_count == 1

        link.now = elapsed
        snapshot = backend.poll()

        assert not snapshot.error
        assert link.master.write.call_count == requests
    finally:
        backend.close()


@pytest.mark.parametrize("backend_type", [DataTelemetryBackend, EscTelemetryBackend])
def test_empty_telemetry_poll_never_waits_for_a_packet(
    link: SimpleNamespace, backend_type: type[DataTelemetryBackend] | type[EscTelemetryBackend]
) -> None:
    """
    An empty telemetry queue must not block the GUI refresh callback.

    GIVEN: A connected transport with no queued packets
    WHEN: A telemetry backend polls within its receive budget
    THEN: The receive operation never waits and returns a successful empty snapshot
    """
    # Heartbeat scheduling is an external FC operation, independent of the receive contract.
    link.controller.start_gcs_heartbeat.side_effect = None
    backend = backend_type(link.controller, lambda: link.now)
    real_receive = link.master.recv_match

    def receive(*, blocking: bool = False) -> object:
        assert not blocking, "Telemetry polling must not wait for a packet"
        return real_receive(blocking=blocking)

    try:
        with patch.object(link.master, "recv_match", side_effect=receive) as receiver:
            snapshot = backend.poll()

        receiver.assert_called_once()
        assert snapshot.connection is link.master
        assert not snapshot.error
        assert not (snapshot.messages if isinstance(snapshot, TelemetrySample) else snapshot.readings)
    finally:
        backend.close()
