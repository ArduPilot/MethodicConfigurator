#!/usr/bin/env python3

"""
Tests for the data_model_rc_calibration.py file.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2026 ArduPilot Contributors

SPDX-License-Identifier: GPL-3.0-or-later
"""

from unittest.mock import MagicMock

import pytest

from ardupilot_methodic_configurator.data_model_rc_calibration import (
    _RC_CENTER_PWM,
    _RC_INVALID_PWM,
    RCCalibrationDataModel,
)

# pylint: disable=protected-access,redefined-outer-name


def _make_rc_channels_msg(raw: list[int], chancount: int | None = None) -> MagicMock:
    """
    Build a mock MAVLink RC_CHANNELS message.

    ``raw`` holds the desired chan1_raw..chanN_raw values; the list is padded
    with the invalid-PWM sentinel up to 18 channels so every ``chanN_raw``
    attribute the data model reads is present.
    """
    padded = list(raw) + [_RC_INVALID_PWM] * (18 - len(raw))
    msg = MagicMock()
    for i in range(18):
        setattr(msg, f"chan{i + 1}_raw", padded[i])
    msg.chancount = chancount if chancount is not None else len(raw)
    return msg


@pytest.fixture
def connected_flight_controller() -> MagicMock:
    """Fixture providing a mock flight controller that reports a live MAVLink link."""
    flight_controller = MagicMock()
    flight_controller.master = MagicMock()
    flight_controller.master.recv_match.return_value = None
    return flight_controller


@pytest.fixture
def disconnected_flight_controller() -> MagicMock:
    """Fixture providing a mock flight controller with no MAVLink link."""
    flight_controller = MagicMock()
    flight_controller.master = None
    return flight_controller


class TestRCCalibrationDataModelConnection:
    """Test how the model reflects the flight controller connection state."""

    def test_model_reports_connected_when_master_link_exists(self, connected_flight_controller) -> None:
        """
        The model is connected when the backend holds a MAVLink master link.

        GIVEN: A flight controller with an active master link
        WHEN: is_connected is queried
        THEN: It reports the vehicle as connected
        """
        model = RCCalibrationDataModel(connected_flight_controller)

        assert model.is_connected() is True

    def test_model_reports_disconnected_when_master_link_absent(self, disconnected_flight_controller) -> None:
        """
        The model is disconnected when the backend has no MAVLink master link.

        GIVEN: A flight controller with no master link
        WHEN: is_connected is queried
        THEN: It reports the vehicle as disconnected
        """
        model = RCCalibrationDataModel(disconnected_flight_controller)

        assert model.is_connected() is False


class TestRCCalibrationDataModelStartCancel:
    """Test starting and cancelling the calibration tracking state."""

    def test_start_calibration_is_refused_when_disconnected(self, disconnected_flight_controller) -> None:
        """
        Calibration cannot start without a connected flight controller.

        GIVEN: A disconnected flight controller
        WHEN: start_calibration is called
        THEN: It fails with a non-empty error message and stays inactive
        """
        model = RCCalibrationDataModel(disconnected_flight_controller)

        success, error_msg = model.start_calibration()

        assert success is False
        assert error_msg != ""
        assert model._is_calibrating is False

    def test_start_calibration_activates_tracking_when_connected(self, connected_flight_controller) -> None:
        """
        Calibration starts cleanly when a link is available.

        GIVEN: A connected flight controller
        WHEN: start_calibration is called
        THEN: It succeeds and the model enters the calibrating state
        """
        model = RCCalibrationDataModel(connected_flight_controller)

        success, error_msg = model.start_calibration()

        assert success is True
        assert error_msg == ""
        assert model._is_calibrating is True

    def test_start_calibration_clears_previous_min_max(self, connected_flight_controller) -> None:
        """
        Starting a new calibration discards data from an earlier run.

        GIVEN: A model that already holds stale min/max data
        WHEN: start_calibration is called
        THEN: The recorded extremes are cleared before the new run
        """
        model = RCCalibrationDataModel(connected_flight_controller)
        model._channel_min = {0: 1100}
        model._channel_max = {0: 1900}

        model.start_calibration()

        assert not model._channel_min
        assert not model._channel_max

    def test_cancel_calibration_discards_state_without_writing(self, connected_flight_controller) -> None:
        """
        Cancelling stops tracking and never writes parameters to the FC.

        GIVEN: An active calibration with recorded extremes
        WHEN: cancel_calibration is called
        THEN: Tracking stops, data is cleared, and no parameter is written
        """
        model = RCCalibrationDataModel(connected_flight_controller)
        model.start_calibration()
        model._channel_min = {0: 1100}
        model._channel_max = {0: 1900}

        success, error_msg = model.cancel_calibration()

        assert success is True
        assert error_msg == ""
        assert model._is_calibrating is False
        assert not model._channel_min
        assert not model._channel_max
        connected_flight_controller.master.set_param.assert_not_called()
        connected_flight_controller.set_param.assert_not_called()


class TestRCCalibrationDataModelFinish:
    """Test writing observed min/max values as RCn_MIN/MAX/TRIM parameters."""

    def test_finish_without_data_writes_no_parameters(self, connected_flight_controller) -> None:
        """
        Finishing with no recorded readings writes nothing.

        GIVEN: A calibration that recorded no channel data
        WHEN: finish_calibration is called
        THEN: No parameter is written and tracking is stopped
        """
        model = RCCalibrationDataModel(connected_flight_controller)
        model.start_calibration()

        model.finish_calibration()

        assert model._is_calibrating is False
        connected_flight_controller.set_param.assert_not_called()

    def test_finish_writes_min_max_trim_for_recorded_channel(self, connected_flight_controller) -> None:
        """
        Finishing writes MIN, MAX and the midpoint TRIM for each channel.

        GIVEN: A channel with observed extremes 1100..1900 (0-based index 0)
        WHEN: finish_calibration is called
        THEN: RC1_MIN=1100, RC1_MAX=1900 and RC1_TRIM=1500 are written as floats
        """
        model = RCCalibrationDataModel(connected_flight_controller)
        model._channel_min = {0: 1100}
        model._channel_max = {0: 1900}

        model.finish_calibration()

        connected_flight_controller.set_param.assert_any_call("RC1_MIN", 1100.0)
        connected_flight_controller.set_param.assert_any_call("RC1_MAX", 1900.0)
        connected_flight_controller.set_param.assert_any_call("RC1_TRIM", 1500.0)

    def test_finish_uses_symmetric_fallback_when_max_missing(self, connected_flight_controller) -> None:
        """
        A channel seen only at its minimum gets a symmetric max fallback.

        GIVEN: Channel index 0 has a min of 1100 but no recorded max
        WHEN: finish_calibration is called
        THEN: MAX falls back to 2*center-min (1900) and TRIM is the midpoint (1500)
        """
        model = RCCalibrationDataModel(connected_flight_controller)
        model._channel_min = {0: 1100}
        model._channel_max = {}  # max never recorded for this channel

        model.finish_calibration()

        expected_max = float(_RC_CENTER_PWM * 2 - 1100)
        connected_flight_controller.set_param.assert_any_call("RC1_MAX", expected_max)
        connected_flight_controller.set_param.assert_any_call("RC1_TRIM", 1500.0)

    def test_finish_converts_zero_based_index_to_one_based_channel(self, connected_flight_controller) -> None:
        """
        Channel numbering exposed to the FC is 1-based.

        GIVEN: Internal 0-based channel index 4 (the fifth channel)
        WHEN: finish_calibration is called
        THEN: The parameter name uses the 1-based number RC5_*
        """
        model = RCCalibrationDataModel(connected_flight_controller)
        model._channel_min = {4: 1000}
        model._channel_max = {4: 2000}

        model.finish_calibration()

        written = {call.args[0] for call in connected_flight_controller.set_param.call_args_list}
        assert "RC5_MIN" in written
        assert "RC5_MAX" in written
        assert "RC5_TRIM" in written

    def test_finish_clears_state_after_writing(self, connected_flight_controller) -> None:
        """
        Finishing clears recorded extremes so a later run starts fresh.

        GIVEN: A channel with recorded extremes
        WHEN: finish_calibration is called
        THEN: The min/max dictionaries are emptied afterwards
        """
        model = RCCalibrationDataModel(connected_flight_controller)
        model._channel_min = {0: 1100}
        model._channel_max = {0: 1900}

        model.finish_calibration()

        assert not model._channel_min
        assert not model._channel_max


class TestRCCalibrationDataModelTelemetry:
    """Test live RC telemetry parsing from MAVLink RC_CHANNELS messages."""

    def test_telemetry_is_empty_when_disconnected(self, disconnected_flight_controller) -> None:
        """
        Telemetry is empty without a link so the GUI keeps waiting.

        GIVEN: A disconnected flight controller
        WHEN: get_rc_telemetry is called
        THEN: An empty dict is returned
        """
        model = RCCalibrationDataModel(disconnected_flight_controller)

        assert not model.get_rc_telemetry()

    def test_telemetry_is_empty_when_no_message_available(self, connected_flight_controller) -> None:
        """
        Telemetry is empty when no RC_CHANNELS message has arrived yet.

        GIVEN: A connected FC whose recv_match returns None
        WHEN: get_rc_telemetry is called
        THEN: An empty dict is returned
        """
        model = RCCalibrationDataModel(connected_flight_controller)
        connected_flight_controller.master.recv_match.return_value = None

        assert not model.get_rc_telemetry()

    def test_telemetry_maps_first_four_channels_to_axes(self, connected_flight_controller) -> None:
        """
        Channels 1-4 map to roll/pitch/throttle/yaw normalised to -1000..+1000.

        GIVEN: An RC_CHANNELS message with CH1..CH4 = 1000/1500/2000/1500
        WHEN: get_rc_telemetry is called
        THEN: roll=-1000, pitch=0, throttle=+1000, yaw=0
        """
        model = RCCalibrationDataModel(connected_flight_controller)
        msg = _make_rc_channels_msg([1000, 1500, 2000, 1500])
        connected_flight_controller.master.recv_match.side_effect = [msg, None]

        telemetry = model.get_rc_telemetry()

        assert telemetry["roll"] == -1000.0
        assert telemetry["pitch"] == 0.0
        assert telemetry["throttle"] == 1000.0
        assert telemetry["yaw"] == 0.0

    def test_telemetry_excludes_invalid_channels_from_channel_list(self, connected_flight_controller) -> None:
        """
        Channels reporting the invalid-PWM sentinel are dropped from the list.

        GIVEN: CH2 reports the invalid sentinel while CH1 and CH3 are valid
        WHEN: get_rc_telemetry is called
        THEN: The channels list omits CH2 but keeps CH1 and CH3
        """
        model = RCCalibrationDataModel(connected_flight_controller)
        msg = _make_rc_channels_msg([1500, _RC_INVALID_PWM, 1600], chancount=3)
        connected_flight_controller.master.recv_match.side_effect = [msg, None]

        telemetry = model.get_rc_telemetry()

        names = {ch["name"] for ch in telemetry["channels"]}
        assert names == {"CH1", "CH3"}

    def test_telemetry_respects_chancount_upper_bound(self, connected_flight_controller) -> None:
        """
        Only the number of channels reported by chancount is surfaced.

        GIVEN: A message with chancount=2 but valid data in later slots
        WHEN: get_rc_telemetry is called
        THEN: Only CH1 and CH2 appear in the channels list
        """
        model = RCCalibrationDataModel(connected_flight_controller)
        msg = _make_rc_channels_msg([1500, 1500, 1500, 1500], chancount=2)
        connected_flight_controller.master.recv_match.side_effect = [msg, None]

        telemetry = model.get_rc_telemetry()

        names = {ch["name"] for ch in telemetry["channels"]}
        assert names == {"CH1", "CH2"}

    def test_invalid_axis_channel_maps_to_zero(self, connected_flight_controller) -> None:
        """
        An axis channel carrying the invalid sentinel normalises to 0.0.

        GIVEN: CH1 (roll) reports the invalid-PWM sentinel
        WHEN: get_rc_telemetry is called
        THEN: roll is reported as 0.0 rather than a garbage value
        """
        model = RCCalibrationDataModel(connected_flight_controller)
        msg = _make_rc_channels_msg([_RC_INVALID_PWM, 1500, 1500, 1500], chancount=4)
        connected_flight_controller.master.recv_match.side_effect = [msg, None]

        telemetry = model.get_rc_telemetry()

        assert telemetry["roll"] == 0.0

    def test_recv_match_exception_is_swallowed(self, connected_flight_controller) -> None:
        """
        A telemetry read error never propagates to the GUI.

        GIVEN: recv_match raises an exception on the RC_CHANNELS read
        WHEN: get_rc_telemetry is called
        THEN: An empty dict is returned instead of raising
        """
        model = RCCalibrationDataModel(connected_flight_controller)
        connected_flight_controller.master.recv_match.side_effect = RuntimeError("link lost")

        assert not model.get_rc_telemetry()

    def test_telemetry_includes_flight_mode_from_heartbeat(self, connected_flight_controller) -> None:
        """
        A HEARTBEAT following the RC_CHANNELS read populates the flight mode.

        GIVEN: An RC_CHANNELS message followed by a HEARTBEAT with custom_mode=3
        WHEN: get_rc_telemetry reads both messages
        THEN: The telemetry carries flight_mode="3"
        """
        model = RCCalibrationDataModel(connected_flight_controller)
        rc_msg = _make_rc_channels_msg([1500], chancount=1)
        hb = MagicMock()
        hb.custom_mode = 3
        connected_flight_controller.master.recv_match.side_effect = [rc_msg, hb]

        telemetry = model.get_rc_telemetry()

        assert telemetry["flight_mode"] == "3"


class TestRCCalibrationDataModelMinMaxTracking:
    """Test that min/max extremes are tracked only while calibrating."""

    def test_extremes_are_recorded_while_calibrating(self, connected_flight_controller) -> None:
        """
        Successive readings widen the recorded min/max window.

        GIVEN: An active calibration receiving 1500 then 1200 then 1800 on CH1
        WHEN: get_rc_telemetry processes each message
        THEN: The recorded window for channel index 0 becomes 1200..1800
        """
        model = RCCalibrationDataModel(connected_flight_controller)
        model.start_calibration()
        for value in (1500, 1200, 1800):
            msg = _make_rc_channels_msg([value], chancount=1)
            connected_flight_controller.master.recv_match.side_effect = [msg, None]
            model.get_rc_telemetry()

        assert model._channel_min[0] == 1200
        assert model._channel_max[0] == 1800

    def test_extremes_are_not_recorded_when_not_calibrating(self, connected_flight_controller) -> None:
        """
        Telemetry outside a calibration run never mutates the min/max window.

        GIVEN: A model that is not calibrating
        WHEN: get_rc_telemetry processes an RC_CHANNELS message
        THEN: No channel extremes are recorded
        """
        model = RCCalibrationDataModel(connected_flight_controller)
        msg = _make_rc_channels_msg([1200], chancount=1)
        connected_flight_controller.master.recv_match.side_effect = [msg, None]

        model.get_rc_telemetry()

        assert not model._channel_min
        assert not model._channel_max


class TestRCCalibrationDataModelFlightMode:
    """Test flight-mode reporting from HEARTBEAT messages."""

    def test_flight_mode_reports_not_connected_without_link(self, disconnected_flight_controller) -> None:
        """
        Flight mode is reported as not-connected without a link.

        GIVEN: A disconnected flight controller
        WHEN: get_flight_mode is called
        THEN: A non-empty not-connected string is returned
        """
        model = RCCalibrationDataModel(disconnected_flight_controller)

        assert model.get_flight_mode() != ""

    def test_flight_mode_returns_custom_mode_from_heartbeat(self, connected_flight_controller) -> None:
        """
        The custom_mode from a HEARTBEAT is surfaced as the flight mode.

        GIVEN: A HEARTBEAT message with custom_mode=5
        WHEN: get_flight_mode is called
        THEN: The string "5" is returned
        """
        model = RCCalibrationDataModel(connected_flight_controller)
        hb = MagicMock()
        hb.custom_mode = 5
        connected_flight_controller.master.recv_match.return_value = hb

        assert model.get_flight_mode() == "5"

    def test_flight_mode_returns_no_data_without_heartbeat(self, connected_flight_controller) -> None:
        """
        Absence of a HEARTBEAT yields a no-data marker rather than an error.

        GIVEN: A connected FC whose recv_match returns None
        WHEN: get_flight_mode is called
        THEN: A non-empty no-data string is returned
        """
        model = RCCalibrationDataModel(connected_flight_controller)
        connected_flight_controller.master.recv_match.return_value = None

        assert model.get_flight_mode() != ""

    def test_flight_mode_swallows_recv_match_exception(self, connected_flight_controller) -> None:
        """
        A HEARTBEAT read error never propagates out of get_flight_mode.

        GIVEN: recv_match raises an exception
        WHEN: get_flight_mode is called
        THEN: A non-empty fallback string is returned instead of raising
        """
        model = RCCalibrationDataModel(connected_flight_controller)
        connected_flight_controller.master.recv_match.side_effect = RuntimeError("link lost")

        assert model.get_flight_mode() != ""
