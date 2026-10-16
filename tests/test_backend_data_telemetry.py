#!/usr/bin/env python3
"""
Data telemetry measurements, radio activation and MAVLink observation.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from pymavlink.dialects.v20 import ardupilotmega as mavlink
from telemetry_test_helpers import create_telemetry_link, feed

from ardupilot_methodic_configurator.backend_data_telemetry import DataTelemetryBackend
from ardupilot_methodic_configurator.data_model_data_telemetry import (
    DataTelemetryDataModel,
    MessageSample,
    RadioSample,
    TelemetrySample,
)

# pylint: disable=protected-access,redefined-outer-name


@pytest.fixture
def telemetry_link() -> SimpleNamespace:
    """Provide an isolated real MAVLink parser with an in-memory transport."""
    return create_telemetry_link()


@pytest.mark.parametrize("message_type", [mavlink.MAVLink_radio_message, mavlink.MAVLink_radio_status_message])
def test_user_sees_radio_values_from_modem_sources(telemetry_link: SimpleNamespace, message_type: type) -> None:
    """
    Accept radio status injected by a modem rather than the target autopilot.

    GIVEN a real encoded RADIO or RADIO_STATUS from system 51/component 68,
    WHEN the backend reads it,
    THEN zero is valid, unknown RSSI stays unavailable and counts/fields retain their meaning.
    """
    backend = DataTelemetryBackend(telemetry_link.controller, lambda: telemetry_link.now)
    packet = feed(telemetry_link, message_type(0, 255, 80, 40, 50, 7, 9), 51, 68)
    try:
        sample = backend.poll()
        assert sample.radio == RadioSample((51, 68), 0.0, 0, None, 40, 50, 80, 7, 9)
        assert sample.rx_bytes == len(packet)
        assert sample.messages[(51, 68, message_type.msgname)].count == 1
        assert ("rxerrors", "7") in sample.messages[(51, 68, message_type.msgname)].fields
        sent = mavlink.MAVLink(None).parse_char(telemetry_link.master.write.call_args.args[0])
        assert sent.get_type() == "HEARTBEAT"
        assert sent.type == mavlink.MAV_TYPE_GCS
    finally:
        backend.close()


def test_user_can_measure_rx_tx_and_message_rates(telemetry_link: SimpleNamespace) -> None:
    """
    Calculate connection wire rates and separate messages by source.

    GIVEN a baseline snapshot and known wire traffic over two seconds,
    WHEN snapshots enter the real domain model,
    THEN RX/TX B/s, parse errors/s and per-source message Hz agree with actual traffic.
    """
    backend = DataTelemetryBackend(telemetry_link.controller, lambda: telemetry_link.now)
    model = DataTelemetryDataModel(telemetry_link.controller)
    try:
        assert model.update(backend.poll()).rx_rate is None
        baseline_tx = telemetry_link.master.mav.total_bytes_sent
        packet = feed(telemetry_link, mavlink.MAVLink_heartbeat_message(2, 3, 0, 0, 3, 3))
        other = feed(telemetry_link, mavlink.MAVLink_heartbeat_message(2, 3, 0, 0, 3, 3), 2, 1)
        telemetry_link.master.mav.heartbeat_send(6, 8, 0, 0, 0)
        telemetry_link.now = 2.0
        state = model.update(backend.poll())
        tx_bytes = telemetry_link.master.mav.total_bytes_sent - baseline_tx
        assert state.rx_rate == (len(packet) + len(other)) / 2
        assert state.tx_rate == tx_bytes / 2
        assert state.parse_error_rate == 0
        assert {row.key for row in state.messages} == {(1, 1, "HEARTBEAT"), (2, 1, "HEARTBEAT")}
        assert all(row.hz == 0.5 and row.bytes_per_second == len(packet) / 2 for row in state.messages)
        assert state.receiving
    finally:
        backend.close()


@pytest.mark.parametrize("message_type", [mavlink.MAVLink_radio_message, mavlink.MAVLink_radio_status_message])
def test_local_radio_starts_reporting_after_a_gcs_heartbeat(telemetry_link: SimpleNamespace, message_type: type) -> None:
    """
    Activate a modem that requires a heartbeat on its local serial input.

    GIVEN a modem withholding reports until the PC sends a GCS heartbeat,
    WHEN either telemetry host polls the shared backend,
    THEN a correctly identified GCS heartbeat enables reception of radio status.
    """
    decoder = mavlink.MAVLink(None)

    def modem_write(packet: bytes) -> None:
        heartbeat = decoder.parse_char(packet)
        assert heartbeat.get_type() == "HEARTBEAT"
        assert (heartbeat.get_srcSystem(), heartbeat.get_srcComponent()) == (255, 190)
        assert heartbeat.type == mavlink.MAV_TYPE_GCS
        assert heartbeat.autopilot == mavlink.MAV_AUTOPILOT_INVALID
        assert heartbeat.base_mode == heartbeat.custom_mode == 0
        assert heartbeat.system_status == mavlink.MAV_STATE_ACTIVE
        feed(telemetry_link, message_type(100, 90, 80, 30, 40, 0, 0), 51, 68)

    telemetry_link.master.write.side_effect = modem_write
    backend = DataTelemetryBackend(telemetry_link.controller, lambda: telemetry_link.now)
    try:
        sample = backend.poll()
        assert sample.radio is not None
        assert sample.radio.rssi == 100
        assert sample.messages[(51, 68, message_type.msgname)].count == 1
    finally:
        backend.close()


def test_radio_heartbeats_are_rate_limited_and_restart_after_monitoring_resumes(telemetry_link: SimpleNamespace) -> None:
    """
    Keep radio reports active without flooding a slow telemetry link.

    GIVEN the shared backend polled every quarter second,
    WHEN monitoring runs, pauses and resumes on the same connection,
    THEN heartbeats are sent immediately and at most once per second, without catch-up bursts.
    """
    backend = DataTelemetryBackend(telemetry_link.controller, lambda: telemetry_link.now)
    try:
        for now in (0, 0.25, 0.5, 0.75):
            telemetry_link.now = now
            backend.poll()
        assert telemetry_link.master.write.call_count == 1
        telemetry_link.now = 1
        backend.poll()
        assert telemetry_link.master.write.call_count == 2
        telemetry_link.now = 20
        backend.poll()
        assert telemetry_link.master.write.call_count == 3
        backend.close()
        telemetry_link.now = 20.25
        backend.poll()
        assert telemetry_link.master.write.call_count == 4
        telemetry_link.controller.master = None
        backend.poll()
        assert telemetry_link.master.write.call_count == 4
        telemetry_link.controller.master = telemetry_link.master
        backend.poll()
        assert telemetry_link.master.write.call_count == 5
    finally:
        backend.close()


def test_heartbeat_write_failure_reports_unavailable_and_can_recover(telemetry_link: SimpleNamespace) -> None:
    """
    Recover radio monitoring after a failed heartbeat write.

    GIVEN a serial transport that fails on write,
    WHEN monitoring reports the failure and the transport recovers,
    THEN no observer leaks and a fresh heartbeat is sent on retry.
    """
    backend = DataTelemetryBackend(telemetry_link.controller, lambda: telemetry_link.now)
    try:
        telemetry_link.master.write.side_effect = OSError("radio disconnected")
        assert backend.poll().error
        assert not telemetry_link.master.message_hooks
        telemetry_link.master.write.side_effect = None
        assert not backend.poll().error
        assert telemetry_link.master.write.call_count == 2
        assert len(telemetry_link.master.message_hooks) == 1
    finally:
        backend.close()


def test_stale_radio_and_message_rates_expire_and_recover(telemetry_link: SimpleNamespace) -> None:
    """
    Distinguish stale telemetry from a healthy zero-valued radio measurement.

    GIVEN fresh radio status and increasing counters,
    WHEN the link goes quiet for three seconds then recovers,
    THEN stale radio values disappear, message rates stop and fresh reports restore readings.
    """
    model = DataTelemetryDataModel(telemetry_link.controller)
    connection = object()
    radio = RadioSample((51, 68), 0, 0, 0, 0, 0, 100, 10, 2)
    message = MessageSample(1, 20, 0, (("rssi", "0"),))
    first = TelemetrySample(connection, 0, messages={(51, 68, "RADIO"): message}, radio=radio)
    model.update(first)
    second = replace(first, time=2, radio=replace(radio, time=2, rxerrors=16))
    assert model.update(second).radio_error_rate == 3
    stale = model.update(replace(second, time=5))
    assert stale.radio is None
    assert stale.radio_error_rate is None
    assert not stale.receiving
    assert stale.messages[0].hz == stale.messages[0].bytes_per_second == 0
    recovered = model.update(replace(second, time=6, radio=replace(radio, time=6)))
    assert recovered.radio is not None
    assert recovered.radio.rssi == 0
    assert recovered.radio_error_rate is None  # reboot/reset rebaselines instead of spiking


def test_reconnect_and_counter_reset_never_create_negative_rates(telemetry_link: SimpleNamespace) -> None:
    """
    Reset measurements across reconnects and parser counter resets.

    GIVEN an existing connection with counters,
    WHEN counters reset or the connection changes,
    THEN rates are unavailable until a new valid interval has elapsed.
    """
    model = DataTelemetryDataModel(telemetry_link.controller)
    connection = object()
    model.update(TelemetrySample(connection, 0, 100, 100, 10))
    reset = model.update(TelemetrySample(connection, 1, 0, 0, 0))
    assert reset.rx_rate is reset.tx_rate is reset.parse_error_rate is None
    assert model.update(TelemetrySample(connection, 2, 10, 20)).rx_rate == 10
    assert model.update(TelemetrySample(object(), 3, 10000, 10000)).rx_rate is None
    assert not model.update(TelemetrySample(None, 4)).connected
    assert model.update(TelemetrySample(connection, 5)).rx_rate is None


@pytest.mark.parametrize(("source", "errors"), [((51, 68), 1), ((52, 68), 100)])
def test_radio_counter_changes_clear_the_displayed_rate_immediately(
    telemetry_link: SimpleNamespace, source: tuple[int, int], errors: int
) -> None:
    """A reset or a different sender must never inherit another counter's measured error rate."""
    model = DataTelemetryDataModel(telemetry_link.controller)
    connection = object()
    radio = RadioSample((51, 68), 0, 30, 40, 0, 0, 100, 10, 2)
    model.update(TelemetrySample(connection, 0, radio=radio))
    assert model.update(TelemetrySample(connection, 1, radio=replace(radio, time=1, rxerrors=12))).radio_error_rate == 2

    changed = replace(radio, source=source, time=1.25, rxerrors=errors)
    assert model.update(TelemetrySample(connection, 1.25, radio=changed)).radio_error_rate is None
    assert (
        model.update(
            TelemetrySample(connection, 2.25, radio=replace(changed, time=2.25, rxerrors=errors + 2))
        ).radio_error_rate
        == 2
    )
    assert (
        model.update(
            TelemetrySample(connection, 3.25, radio=replace(changed, time=3.25, rxerrors=errors + 4))
        ).radio_error_rate
        == 2
    )


def test_observer_preserves_other_consumers_and_detaches_on_reconnect(telemetry_link: SimpleNamespace) -> None:
    """
    Share the parser's observation hooks without replacing existing consumers.

    GIVEN another observer and a plugin observer on the connection,
    WHEN another consumer parses a message and the connection disconnects,
    THEN both see that packet and plugin cleanup preserves the other observer.
    """
    observer = MagicMock()
    telemetry_link.master.message_hooks.append(observer)
    backend = DataTelemetryBackend(telemetry_link.controller)
    backend.poll()
    backend.poll()
    assert len(telemetry_link.master.message_hooks) == 2
    feed(telemetry_link, mavlink.MAVLink_heartbeat_message(2, 3, 0, 0, 3, 3))
    assert telemetry_link.master.recv_match(blocking=False) is not None
    assert backend.poll().messages[(1, 1, "HEARTBEAT")].count == 1
    observer.assert_called_once()
    telemetry_link.controller.master = None
    assert backend.poll().connection is None
    assert telemetry_link.master.message_hooks == [observer]
    backend.close()


def test_read_failure_clears_observer_and_reports_unavailable(telemetry_link: SimpleNamespace) -> None:
    """
    Recover safely from transport errors.

    GIVEN an attached telemetry observer,
    WHEN the transport fails while reading,
    THEN a read error replaces live data and the observer is detached.
    """
    backend = DataTelemetryBackend(telemetry_link.controller)
    backend.poll()
    with patch.object(telemetry_link.master, "recv_match", side_effect=OSError("link lost")):
        sample = backend.poll()
    assert sample.error
    assert not sample.messages
    assert not telemetry_link.master.message_hooks
    assert DataTelemetryDataModel(telemetry_link.controller).update(sample).error


def test_malformed_packets_never_appear_as_received_message_types(telemetry_link: SimpleNamespace) -> None:
    """
    Keep undecodable traffic out of the received-message table.

    GIVEN an observer with a valid received heartbeat,
    WHEN its hook is notified about a malformed packet,
    THEN the heartbeat remains intact and BAD_DATA does not become a message row.
    """
    backend = DataTelemetryBackend(telemetry_link.controller, lambda: telemetry_link.now)
    try:
        backend.poll()
        feed(telemetry_link, mavlink.MAVLink_heartbeat_message(2, 3, 0, 0, 3, 3))
        before = backend.poll()
        malformed = mavlink.MAVLink_bad_data(b"noise", "invalid MAVLink data")
        for hook in telemetry_link.master.message_hooks:
            hook(telemetry_link.master, malformed)
        assert backend.poll().messages == before.messages
    finally:
        backend.close()


def test_radio_fields_preserve_valid_limits_and_hide_unknown_or_invalid_readings(telemetry_link: SimpleNamespace) -> None:
    """
    Keep valid raw-scale limits while refusing values outside the documented measurement ranges.

    GIVEN a RADIO_STATUS packet with RSSI/noise sentinels and an invalid free-buffer percentage,
    WHEN the real MAVLink parser passes it to the telemetry backend,
    THEN 254 stays measurable, 255 stays unknown and a buffer over 100 percent is unavailable.
    """
    backend = DataTelemetryBackend(telemetry_link.controller, lambda: telemetry_link.now)
    try:
        feed(telemetry_link, mavlink.MAVLink_radio_status_message(254, 255, 101, 255, 254, 0, 0), 51, 68)
        sample = backend.poll()
        assert sample.radio == RadioSample((51, 68), 0, 254, None, None, 254, None, 0, 0)
    finally:
        backend.close()


@pytest.mark.parametrize("message_type", [mavlink.MAVLink_radio_message, mavlink.MAVLink_radio_status_message])
def test_radio_updates_when_message_table_is_full(telemetry_link: SimpleNamespace, message_type: type) -> None:
    """
    Keep radio measurements current even when no more message rows fit.

    GIVEN a message table filled with heartbeat sources,
    WHEN radio reports arrive from previously unseen modem sources,
    THEN the latest radio readings update while the table remains bounded.
    """
    backend = DataTelemetryBackend(telemetry_link.controller, lambda: telemetry_link.now)
    try:
        backend.poll()
        for index in range(512):
            message = mavlink.MAVLink_heartbeat_message(2, 3, 0, 0, 3, 3)
            message.pack(mavlink.MAVLink(None, srcSystem=index // 250, srcComponent=index % 250))
            backend._capture(telemetry_link.master, message)
        before = backend.poll().messages
        assert len(before) == 512
        for source in (51, 52):
            telemetry_link.now += 1
            feed(telemetry_link, message_type(100, 90, 80, 30, 40, 7, 9), source, 68)
            sample = backend.poll()
            assert sample.radio == RadioSample((source, 68), telemetry_link.now, 100, 90, 30, 40, 80, 7, 9)
            assert sample.messages == before
    finally:
        backend.close()


def test_busy_stream_and_source_count_are_bounded(telemetry_link: SimpleNamespace) -> None:
    """
    Bound monitoring work even with a continuously busy transport.

    GIVEN more packets than one GUI tick should read,
    WHEN polling and observing excessive source identities,
    THEN only a bounded batch and bounded set of source/type rows are retained.
    """
    backend = DataTelemetryBackend(telemetry_link.controller, lambda: 0.0)
    try:
        for _index in range(250):
            feed(telemetry_link, mavlink.MAVLink_heartbeat_message(2, 3, 0, 0, 3, 3))
        assert backend.poll().messages[(1, 1, "HEARTBEAT")].count == 200
        assert backend.poll().messages[(1, 1, "HEARTBEAT")].count == 250
        for index in range(600):
            message = mavlink.MAVLink_heartbeat_message(2, 3, 0, 0, 3, 3)
            message.pack(mavlink.MAVLink(None, srcSystem=index // 250, srcComponent=index % 250))
            backend._capture(telemetry_link.master, message)
        assert len(backend.poll().messages) == 512
    finally:
        backend.close()
