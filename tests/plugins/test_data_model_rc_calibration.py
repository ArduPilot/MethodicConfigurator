#!/usr/bin/env python3

"""
Tests for the data_model_rc_calibration.py file.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2026 ArduPilot Contributors

SPDX-License-Identifier: GPL-3.0-or-later
"""

import json
import re
from math import nan
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest
from jsonschema import validate

from ardupilot_methodic_configurator.data_model_ardupilot_parameter import ArduPilotParameter
from ardupilot_methodic_configurator.data_model_par_dict import Par
from ardupilot_methodic_configurator.data_model_parameter_editor import InvalidParameterNameError, ParameterEditor
from ardupilot_methodic_configurator.plugins.data_model_rc_calibration import (
    _RC_CENTER_PWM,
    _RC_INVALID_PWM,
    RCCalibrationDataModel,
)
from ardupilot_methodic_configurator.plugins.frontend_tkinter_rc_calibration import _create_rc_calibration_model
from ardupilot_methodic_configurator.plugins.plugin_factory import PluginModelContext

# pylint: disable=protected-access,redefined-outer-name,too-many-lines


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
    flight_controller.fc_parameters = {}
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
    """Calibration measurements become editable New values, never direct controller writes."""

    def test_finish_without_data_writes_no_parameters(self, connected_flight_controller) -> None:
        """
        Finishing with no recorded readings stages nothing.

        GIVEN: A calibration that recorded no channel data
        WHEN: finish_calibration is called
        THEN: It reports no data and tracking stops without writing parameters
        """
        model = RCCalibrationDataModel(connected_flight_controller)
        model.start_calibration()
        success, message = model.finish_calibration()
        assert success is False
        assert message
        assert model._is_calibrating is False
        connected_flight_controller.set_param.assert_not_called()

    @pytest.mark.parametrize(("index", "minimum", "maximum"), [(0, 1100, 1900), (4, 1000, 2000), (15, 1050, 1950)])
    def test_finish_stages_measured_min_max_trim_and_preserves_fc_cache(
        self, rc_staging_context, index: int, minimum: int, maximum: int
    ) -> None:
        """
        Finishing stages MIN, MAX and midpoint TRIM for valid recorded channels.

        GIVEN: A real editor with cached calibration and an observed channel
        WHEN: finish_calibration is called
        THEN: Correctly numbered New values and markers change, tracking clears, and the FC cache is untouched
        """
        controller, editor = rc_staging_context
        model = RCCalibrationDataModel(controller, editor)
        before = dict(controller.fc_parameters)
        model._channel_min = {index: minimum}
        model._channel_max = {index: maximum}
        success, message = model.finish_calibration()
        assert success is True
        assert "upload" in message
        for suffix, value in (("MIN", minimum), ("MAX", maximum), ("TRIM", (minimum + maximum) // 2)):
            assert editor.current_step_parameters[f"RC{index + 1}_{suffix}"].get_new_value() == value
        assert model.get_channel_calibration()[index]["min"] == minimum
        assert controller.fc_parameters == before
        assert not model._channel_min
        assert not model._channel_max
        controller.set_param.assert_not_called()

    def test_finish_uses_symmetric_fallback_when_max_missing(self, rc_staging_context) -> None:
        """
        A missing observed maximum retains the existing symmetric fallback behavior.

        GIVEN: Channel index 0 has a minimum of 1100 but no recorded maximum
        WHEN: finish_calibration is called
        THEN: Only staged MAX/TRIM become 1900/1500; the FC remains unchanged
        """
        controller, editor = rc_staging_context
        model = RCCalibrationDataModel(controller, editor)
        model._channel_min = {0: 1100}
        assert model.finish_calibration()[0] is True
        assert editor.current_step_parameters["RC1_MAX"].get_new_value() == _RC_CENTER_PWM * 2 - 1100
        assert editor.current_step_parameters["RC1_TRIM"].get_new_value() == 1500
        controller.set_param.assert_not_called()

    def test_finish_skips_stationary_channel_and_stages_only_channel_that_moved(
        self, rc_staging_context: tuple[MagicMock, ParameterEditor]
    ) -> None:
        """
        A switch left untouched during calibration keeps its existing endpoints.

        GIVEN: CH1 stays at 1500 while CH2 moves between 1100 and 1900
        WHEN: The user finishes calibration
        THEN: Only CH2 receives staged endpoints and trim, without an FC write
        """
        controller, editor = rc_staging_context
        model = RCCalibrationDataModel(controller, editor)
        model.start_calibration()
        for readings in ([1500, 1100], [1500, 1900]):
            controller.master.recv_match.side_effect = [_make_rc_channels_msg(readings), None]
            model.get_rc_telemetry()

        success, message = model.finish_calibration()

        assert success is True
        assert "upload" in message
        for suffix, value in (("MIN", 1000), ("MAX", 2000), ("TRIM", 1500)):
            assert editor.current_step_parameters[f"RC1_{suffix}"].get_new_value() == value
        for suffix, value in (("MIN", 1100), ("MAX", 1900), ("TRIM", 1500)):
            assert editor.current_step_parameters[f"RC2_{suffix}"].get_new_value() == value
        assert not model._channel_min
        assert not model._channel_max
        assert model._is_calibrating is False
        controller.set_param.assert_not_called()

    def test_finish_with_only_stationary_channels_stages_nothing(
        self, rc_staging_context: tuple[MagicMock, ParameterEditor]
    ) -> None:
        """
        Finishing a run with no stick or switch movement leaves every value alone.

        GIVEN: The user starts calibration and CH1 remains at 1500
        WHEN: The user finishes calibration
        THEN: The run succeeds with a no-movement message and clears its readings
        """
        controller, editor = rc_staging_context
        model = RCCalibrationDataModel(controller, editor)
        before = {name: parameter.get_new_value() for name, parameter in editor.current_step_parameters.items()}
        model.start_calibration()
        controller.master.recv_match.side_effect = [_make_rc_channels_msg([1500]), None]
        model.get_rc_telemetry()

        success, message = model.finish_calibration()

        assert success is True
        assert "No RC channels moved" in message
        assert {name: parameter.get_new_value() for name, parameter in editor.current_step_parameters.items()} == before
        assert not model._channel_min
        assert not model._channel_max
        assert model._is_calibrating is False
        controller.set_param.assert_not_called()

    def test_standalone_finish_cannot_bypass_the_upload_workflow(self, connected_flight_controller) -> None:
        """
        Standalone monitoring has no parameter-editor staging target.

        GIVEN: A standalone model with recorded extrema
        WHEN: The user tries to finish calibration
        THEN: It asks for the parameter editor, preserves the measurements and never sends parameters
        """
        model = RCCalibrationDataModel(connected_flight_controller)
        model._channel_min = {0: 1100}
        model._channel_max = {0: 1900}
        success, message = model.finish_calibration()
        assert success is False
        assert "parameter editor" in message
        assert model._channel_min == {0: 1100}
        connected_flight_controller.set_param.assert_not_called()


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

    def test_telemetry_keeps_all_channels_and_marks_invalid_values_unavailable(self, connected_flight_controller) -> None:
        """
        All 16 display rows remain present when a channel has no valid PWM value.

        GIVEN: CH2 reports the invalid sentinel while CH1 and CH3 are valid
        WHEN: get_rc_telemetry is called
        THEN: CH1-CH16 are present and CH2 has no current value
        """
        model = RCCalibrationDataModel(connected_flight_controller)
        msg = _make_rc_channels_msg([1500, _RC_INVALID_PWM, 1600], chancount=3)
        connected_flight_controller.master.recv_match.side_effect = [msg, None]

        telemetry = model.get_rc_telemetry()

        channels = telemetry["channels"]
        assert len(channels) == 16
        assert channels[0]["value"] == 1500
        assert channels[1]["value"] is None
        assert channels[2]["value"] == 1600
        assert channels[15]["name"] == "CH16"

    def test_telemetry_respects_chancount_upper_bound(self, connected_flight_controller) -> None:
        """
        Values beyond the MAVLink channel count remain unavailable.

        GIVEN: A message with chancount=2 but valid data in later slots
        WHEN: get_rc_telemetry is called
        THEN: CH1 and CH2 have values while later display rows are empty
        """
        model = RCCalibrationDataModel(connected_flight_controller)
        msg = _make_rc_channels_msg([1500, 1500, 1500, 1500], chancount=2)
        connected_flight_controller.master.recv_match.side_effect = [msg, None]

        telemetry = model.get_rc_telemetry()

        channels = telemetry["channels"]
        assert [channel["value"] for channel in channels[:4]] == [1500, 1500, None, None]
        assert len(channels) == 16

    def test_telemetry_caps_display_at_sixteen_channels(self, connected_flight_controller) -> None:
        """
        The user-facing telemetry contains exactly channels CH1 through CH16.

        GIVEN: An RC_CHANNELS message reports 18 channels
        WHEN: get_rc_telemetry is called
        THEN: Exactly 16 channels are returned and CH16 is the last one
        """
        model = RCCalibrationDataModel(connected_flight_controller)
        msg = _make_rc_channels_msg(list(range(1100, 1118)), chancount=18)
        connected_flight_controller.master.recv_match.side_effect = [msg, None]

        telemetry = model.get_rc_telemetry()

        assert len(telemetry["channels"]) == 16
        assert telemetry["channels"][-1]["name"] == "CH16"
        assert telemetry["channels"][-1]["value"] == 1115

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

    def test_monitor_shows_configured_min_max_trim_without_starting_calibration(self, connected_flight_controller) -> None:
        """
        Existing calibration markers are available immediately, including before RC input arrives.

        GIVEN: The parameter cache contains RC1_MIN/MAX/TRIM
        WHEN: The initial channel calibration is queried and live RC data later arrives
        THEN: The configured markers are returned in both cases without writing parameters
        """
        connected_flight_controller.fc_parameters = {"RC1_MIN": 982.0, "RC1_MAX": 2018.0, "RC1_TRIM": 1495.0}
        model = RCCalibrationDataModel(connected_flight_controller)
        initial = model.get_channel_calibration()
        connected_flight_controller.master.recv_match.side_effect = [_make_rc_channels_msg([1500]), None]

        channel = model.get_rc_telemetry()["channels"][0]

        assert {key: initial[0][key] for key in ("name", "value", "min", "max", "trim")} == {
            "name": "CH1",
            "value": None,
            "min": 982,
            "max": 2018,
            "trim": 1495,
        }
        assert initial[0]["function"] == "Roll"
        assert initial[0]["function_editable"] is False
        assert (channel["min"], channel["max"], channel["trim"]) == (982, 2018, 1495)
        connected_flight_controller.set_param.assert_not_called()

    def test_axes_use_channel_mapping_calibration_and_reversal(self, connected_flight_controller) -> None:
        """
        The stick preview follows the flight controller's RC channel mapping and endpoints.

        GIVEN: Roll is mapped to reversed CH5 with endpoints 1100..1900
        WHEN: CH5 reports its low endpoint
        THEN: Roll is full positive while the raw channel value remains unchanged
        """
        connected_flight_controller.fc_parameters = {
            "RCMAP_ROLL": 5.0,
            "RC5_MIN": 1100.0,
            "RC5_MAX": 1900.0,
            "RC5_REVERSED": 1.0,
        }
        model = RCCalibrationDataModel(connected_flight_controller)
        connected_flight_controller.master.recv_match.side_effect = [
            _make_rc_channels_msg([1500, 1500, 1500, 1500, 1100]),
            None,
        ]

        telemetry = model.get_rc_telemetry()

        assert telemetry["roll"] == 1000.0
        assert telemetry["channels"][4]["value"] == 1100

    def test_centered_throttle_uses_endpoint_midpoint_not_low_throttle_trim(self, connected_flight_controller) -> None:
        """
        A physically centered throttle is shown in the middle even when its configured trim is low.

        GIVEN: Throttle endpoints are 1100..1900 with a low-throttle trim of 1100
        WHEN: The throttle channel reports 1500
        THEN: The stick axis is centered and the trim marker remains at 1100
        """
        connected_flight_controller.fc_parameters = {"RC3_MIN": 1100.0, "RC3_MAX": 1900.0, "RC3_TRIM": 1100.0}
        model = RCCalibrationDataModel(connected_flight_controller)
        connected_flight_controller.master.recv_match.side_effect = [_make_rc_channels_msg([1500, 1500, 1500]), None]

        telemetry = model.get_rc_telemetry()

        assert telemetry["throttle"] == 0.0
        assert telemetry["channels"][2]["trim"] == 1100

    def test_centered_roll_uses_the_configured_trim(self, connected_flight_controller) -> None:
        """
        Calibrated neutral roll maps to the gimbal center even with an offset trim.

        GIVEN: RC1 has endpoints 1000..2000 and a neutral trim of 1480
        WHEN: RC1 reports its neutral value
        THEN: The roll position is exactly centered
        """
        connected_flight_controller.fc_parameters = {"RC1_TRIM": 1480.0}
        model = RCCalibrationDataModel(connected_flight_controller)
        connected_flight_controller.master.recv_match.side_effect = [_make_rc_channels_msg([1480]), None]
        assert model.get_rc_telemetry()["roll"] == 0.0

    @pytest.mark.parametrize(
        ("parameters", "expected"),
        [
            ({}, (1000, 2000, 1500)),
            ({"RC1_MIN": nan, "RC1_MAX": 2000}, (1000, 2000, 1500)),
            ({"RC1_MIN": 2000, "RC1_MAX": 1000}, (1000, 2000, 1500)),
            ({"RC1_MIN": 1500.1, "RC1_MAX": 1500.2}, (1000, 2000, 1500)),
            ({"RC1_MIN": 1100, "RC1_MAX": 1900, "RC1_TRIM": 3000}, (1100, 1900, 1500)),
        ],
    )
    def test_invalid_parameter_limits_use_display_only_defaults(self, parameters, expected) -> None:
        """
        Missing or malformed calibration cache entries do not break the display.

        GIVEN: Missing, nonfinite, reversed, or out-of-range calibration parameters
        WHEN: Channel display limits are computed
        THEN: Finite ordered display defaults are returned
        """
        assert RCCalibrationDataModel.channel_limits(parameters, 1) == expected

    @pytest.mark.parametrize("mapping", [0.0, 17.0, 1.5, nan])
    def test_invalid_channel_mapping_centers_the_axis(self, connected_flight_controller, mapping) -> None:
        """
        Invalid RC mapping never selects the wrong channel.

        GIVEN: An invalid RCMAP_ROLL value
        WHEN: Valid RC telemetry is parsed
        THEN: The roll preview remains neutral
        """
        connected_flight_controller.fc_parameters = {"RCMAP_ROLL": mapping}
        model = RCCalibrationDataModel(connected_flight_controller)
        connected_flight_controller.master.recv_match.side_effect = [_make_rc_channels_msg([1000]), None]
        assert model.get_rc_telemetry()["roll"] == 0.0


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
        telemetry: dict = {}
        for value in (1500, 1200, 1800):
            msg = _make_rc_channels_msg([value], chancount=1)
            connected_flight_controller.master.recv_match.side_effect = [msg, None]
            telemetry = model.get_rc_telemetry()

        assert model._channel_min[0] == 1200
        assert model._channel_max[0] == 1800
        assert telemetry["channels"][0]["min"] == 1200
        assert telemetry["channels"][0]["max"] == 1800

    def test_calibration_extremes_preserve_configured_trim_and_cancel_restores_markers(
        self, connected_flight_controller
    ) -> None:
        """
        Live calibration changes min/max markers but not the configured trim marker.

        GIVEN: Configured endpoints and trim plus an active calibration
        WHEN: New extremes arrive and the user then cancels
        THEN: Observed endpoints are shown during calibration and configured endpoints return on cancel
        """
        connected_flight_controller.fc_parameters = {"RC1_MIN": 1000.0, "RC1_MAX": 2000.0, "RC1_TRIM": 1480.0}
        model = RCCalibrationDataModel(connected_flight_controller)
        model.start_calibration()
        for value in (1200, 1800):
            connected_flight_controller.master.recv_match.side_effect = [_make_rc_channels_msg([value]), None]
            telemetry = model.get_rc_telemetry()

        assert (telemetry["channels"][0]["min"], telemetry["channels"][0]["max"], telemetry["channels"][0]["trim"]) == (
            1200,
            1800,
            1480,
        )
        model.cancel_calibration()
        channel = model.get_channel_calibration()[0]
        assert (channel["min"], channel["max"], channel["trim"]) == (1000, 2000, 1480)
        connected_flight_controller.set_param.assert_not_called()

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


class TestTransmitterStickModes:
    """Check each transmitter mode with distinct axis values rather than identical stick movement."""

    @pytest.mark.parametrize(
        ("mode", "expected"),
        [
            (1, ((0.4, -0.2), (0.1, 0.3))),
            (2, ((0.4, 0.3), (0.1, -0.2))),
            (3, ((0.1, -0.2), (0.4, 0.3))),
            (4, ((0.1, 0.3), (0.4, -0.2))),
        ],
    )
    def test_each_axis_is_assigned_to_the_correct_physical_stick(self, mode: int, expected) -> None:
        """
        The four modes each map individual control axes to the correct left/right gimbal coordinates.

        GIVEN: Distinct roll, pitch, throttle and yaw values
        WHEN: Physical stick positions are computed for a selected transmitter mode
        THEN: Horizontal/vertical coordinates match that mode and pitch is inverted
        """
        axes = {"roll": 100.0, "pitch": 200.0, "throttle": 300.0, "yaw": 400.0}

        assert RCCalibrationDataModel.stick_positions(axes, mode) == expected

    def test_out_of_range_stick_inputs_are_clamped_to_the_gimbal_edges(self) -> None:
        """
        Unusually large axis input cannot push a circle outside its square.

        GIVEN: Axis readings beyond normal transmitter travel
        WHEN: Physical stick positions are computed
        THEN: Both coordinates are clamped to the normalised -1..1 range
        """
        positions = RCCalibrationDataModel.stick_positions(
            {"roll": 5000.0, "pitch": 5000.0, "throttle": -5000.0, "yaw": -5000.0}, 2
        )
        assert positions == ((-1.0, -1.0), (1.0, -1.0))


class TestRCMappingStaging:
    """Mapping presets are atomic staged edits and preserve unrelated parameters."""

    @pytest.mark.parametrize(
        ("mode", "expected"),
        [(1, (1, 3, 2, 4)), (2, (1, 2, 3, 4)), (3, (4, 3, 2, 1)), (4, (4, 2, 3, 1))],
    )
    def test_mode_selection_stages_all_four_parameters_without_controller_writes(
        self, rc_staging_context, mode: int, expected: tuple[int, int, int, int]
    ) -> None:
        """
        Each preset selects the four main RC channel assignments.

        GIVEN: A real editor with an existing Mode-2 assignment
        WHEN: The mode is selected twice
        THEN: All New values match the preset, repeats are idempotent, and unrelated values and FC cache are unchanged
        """
        controller, editor = rc_staging_context
        before = dict(controller.fc_parameters)
        model = RCCalibrationDataModel(controller, editor)
        assert model.set_mapping_mode(mode)[0] is True
        reasons = {name: parameter.change_reason_for_file for name, parameter in editor.current_step_parameters.items()}
        assert model.set_mapping_mode(mode)[0] is True
        assert model.get_mapping_mode() == mode
        names = ("RCMAP_ROLL", "RCMAP_PITCH", "RCMAP_THROTTLE", "RCMAP_YAW")
        assert tuple(editor.current_step_parameters[name].get_new_value() for name in names) == expected
        assert {
            name: parameter.change_reason_for_file for name, parameter in editor.current_step_parameters.items()
        } == reasons
        assert editor.current_step_parameters["ARMING_RUDDER"].get_new_value() == 2
        assert controller.fc_parameters == before
        controller.set_param.assert_not_called()

    @pytest.mark.parametrize("protection", ["readonly", "forced", "derived", "range"])
    def test_bulk_mapping_validation_prevents_partial_value_changes(self, rc_staging_context, protection: str) -> None:
        """
        A protected or out-of-range mapping prevents the entire preset edit.

        GIVEN: The last mapping parameter rejects the desired value
        WHEN: Mode 3 would change the preceding three mappings
        THEN: None of the staged values or reasons change
        """
        controller, editor = rc_staging_context
        metadata: dict[str, Any] = (
            {"ReadOnly": True} if protection == "readonly" else {"min": 2} if protection == "range" else {}
        )
        parameter = ArduPilotParameter(
            "RCMAP_YAW",
            Par(4, "Keep reason"),
            metadata=metadata,
            forced_par=Par(4, "Forced") if protection == "forced" else None,
            derived_par=Par(4, "Derived") if protection == "derived" else None,
        )
        editor.current_step_parameters["RCMAP_YAW"] = parameter
        before = {name: (par.get_new_value(), par.change_reason) for name, par in editor.current_step_parameters.items()}
        success, message = RCCalibrationDataModel(controller, editor).set_mapping_mode(3)
        assert success is False
        assert message
        assert {
            name: (par.get_new_value(), par.change_reason) for name, par in editor.current_step_parameters.items()
        } == before
        controller.set_param.assert_not_called()

    def test_missing_mapping_parameters_are_added_with_real_editor_api(self, rc_staging_context) -> None:
        """
        Existing projects need not already contain RCMAP entries in their RC step.

        GIVEN: Only one mapping parameter is staged, with all four known to the FC
        WHEN: A mapping preset is selected
        THEN: Missing parameters are added as editable New values without controller writes
        """
        controller, editor = rc_staging_context
        editor.current_step_parameters = {"RCMAP_ROLL": editor.current_step_parameters["RCMAP_ROLL"]}
        assert RCCalibrationDataModel(controller, editor).set_mapping_mode(1)[0] is True
        assert len(editor.current_step_parameters) == 4
        assert editor.current_step_parameters["RCMAP_PITCH"].get_new_value() == 3
        controller.set_param.assert_not_called()

    def test_failed_parameter_addition_rolls_back_preceding_additions(
        self, rc_staging_context: tuple[MagicMock, ParameterEditor], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """
        Unsupported mapping parameters cannot leave half-added rows.

        GIVEN: An empty step and a backend unable to add the second mapping
        WHEN: A mode preset is selected
        THEN: The first addition is removed and no values or FC parameters change
        """
        controller, editor = rc_staging_context
        editor.current_step_parameters = {}
        real_add = editor.add_parameter_to_current_file

        def add(name: str) -> bool:
            if name == "RCMAP_PITCH":
                message = "Missing"
                raise InvalidParameterNameError(message)
            return real_add(name)

        monkeypatch.setattr(editor, "add_parameter_to_current_file", add)
        success, _message = RCCalibrationDataModel(controller, editor).set_mapping_mode(3)
        assert success is False
        assert editor.current_step_parameters == {}
        controller.set_param.assert_not_called()

    def test_manual_override_reason_marker_is_preserved_once(self, rc_staging_context) -> None:
        """
        A permitted derived-parameter override keeps its serialization marker.

        GIVEN: A manually overridden derived mapping parameter
        WHEN: A mapping mode is staged repeatedly
        THEN: The override remains active and its reason contains one override marker
        """
        controller, editor = rc_staging_context
        parameter = ArduPilotParameter("RCMAP_PITCH", Par(2, "Original"), derived_par=Par(2, "Derived"))
        parameter.set_manual_override(True)
        editor.current_step_parameters["RCMAP_PITCH"] = parameter
        model = RCCalibrationDataModel(controller, editor)
        assert model.set_mapping_mode(1)[0] is True
        assert model.set_mapping_mode(1)[0] is True
        assert parameter.is_manual_override
        assert parameter.change_reason_for_file.count("@manual_override") == 1

    def test_invalid_mode_leaves_all_parameters_untouched(self, rc_staging_context) -> None:
        """
        Invalid mode input is rejected safely.

        GIVEN: A valid staged mapping
        WHEN: An unsupported mode number is submitted
        THEN: The existing mode remains unchanged with no controller writes
        """
        controller, editor = rc_staging_context
        model = RCCalibrationDataModel(controller, editor)
        assert model.set_mapping_mode(0)[0] is False
        assert model.get_mapping_mode() == 2
        controller.set_param.assert_not_called()

    def test_factory_injects_parameter_editor_staging_dependency(self, rc_staging_context) -> None:
        """
        Application plugin construction uses the same staging objects as the parameter table.

        GIVEN: The application plugin context
        WHEN: The RC model factory runs
        THEN: A mode change edits the context's current-step parameters
        """
        controller, editor = rc_staging_context
        model = _create_rc_calibration_model(PluginModelContext(controller, MagicMock(), editor))
        assert model.set_mapping_mode(4)[0] is True
        assert editor.current_step_parameters["RCMAP_YAW"].get_new_value() == 1
        controller.set_param.assert_not_called()

    def test_staged_mapping_is_sent_only_by_the_existing_parameter_upload_workflow(
        self, rc_staging_context, monkeypatch
    ) -> None:
        """
        Staged plugin edits flow through the application's explicit upload workflow.

        GIVEN: A selected mapping preset and completed calibration staged in New values
        WHEN: The parameter editor upload workflow is explicitly invoked
        THEN: The mapping and calibration are sent via the backend only at that point
        """
        controller, editor = rc_staging_context
        model = RCCalibrationDataModel(controller, editor)
        assert model.set_mapping_mode(1)[0] is True
        model._channel_min = {0: 1100}
        model._channel_max = {0: 1900}
        assert model.finish_calibration()[0] is True
        controller.set_param.assert_not_called()
        names = ["RCMAP_ROLL", "RCMAP_PITCH", "RCMAP_THROTTLE", "RCMAP_YAW", "RC1_MIN", "RC1_MAX", "RC1_TRIM"]
        values = editor.get_parameters_as_par_dict(names)

        def set_param(name: str, value: float) -> tuple[bool, str]:
            controller.fc_parameters[name] = value
            return True, ""

        controller.set_param.side_effect = set_param
        # Isolate only reset/readback I/O; run the real upload and parameter verification.
        monkeypatch.setattr(editor, "upload_parameters_that_require_reset_workflow", lambda *_args: (False, set(), True))
        monkeypatch.setattr(
            editor, "download_flight_controller_parameters", lambda *_args, **_kwargs: (controller.fc_parameters, {})
        )
        assert editor.upload_selected_params_workflow(
            values, MagicMock(), MagicMock(return_value=False), MagicMock(), persist_project_state=False
        )
        assert {call.args[0]: call.args[1] for call in controller.set_param.call_args_list} == {
            "RCMAP_ROLL": 1,
            "RCMAP_PITCH": 3,
            "RCMAP_THROTTLE": 2,
            "RCMAP_YAW": 4,
            "RC1_MIN": 1100,
            "RC1_MAX": 1900,
            "RC1_TRIM": 1500,
        }

    def test_failed_calibration_staging_retains_measurements_and_all_prior_values(self, rc_staging_context) -> None:
        """
        Rejected calibration measurements can be retried without losing previous New values.

        GIVEN: Recorded extrema and a read-only trim parameter
        WHEN: Finish Calibration attempts to stage the batch
        THEN: No New values are changed and measurements remain available for retry or cancellation
        """
        controller, editor = rc_staging_context
        editor.current_step_parameters["RC1_TRIM"]._metadata["ReadOnly"] = True
        model = RCCalibrationDataModel(controller, editor)
        model._channel_min = {0: 1100}
        model._channel_max = {0: 1900}
        assert model.finish_calibration()[0] is False
        assert editor.current_step_parameters["RC1_MIN"].get_new_value() == 1000
        assert editor.current_step_parameters["RC1_MAX"].get_new_value() == 2000
        assert model._channel_min == {0: 1100}
        controller.set_param.assert_not_called()


class TestRCChannelOptionProtection:
    """Channel-option protection follows the effective mapping, not fixed channel numbers."""

    @pytest.mark.parametrize("channel_number", [7, 11])
    def test_unsupported_auxiliary_option_does_not_change_or_add_parameter_rows(
        self, rc_staging_context: tuple[MagicMock, ParameterEditor], channel_number: int
    ) -> None:
        """
        Only options advertised by the loaded firmware metadata can be staged.

        GIVEN: A free channel with an existing or missing RCx_OPTION row
        WHEN: An option value absent from its firmware choices is requested
        THEN: The request fails without changing New values, adding rows, or writing to the FC
        """
        controller, editor = rc_staging_context
        model = RCCalibrationDataModel(controller, editor)
        original_values = {name: parameter.get_new_value() for name, parameter in editor.current_step_parameters.items()}
        original_cache = dict(controller.fc_parameters)

        success, message = model.set_channel_option(channel_number, "999")

        assert success is False
        assert "valid RC channel option" in message
        staged_values = {name: parameter.get_new_value() for name, parameter in editor.current_step_parameters.items()}
        assert staged_values == original_values
        assert controller.fc_parameters == original_cache
        controller.set_param.assert_not_called()

    @pytest.mark.parametrize(("axis", "original_channel"), [("ROLL", 1), ("PITCH", 2), ("THROTTLE", 3), ("YAW", 4)])
    @pytest.mark.parametrize("mapped_channel", [6, 16])
    def test_user_cannot_assign_an_auxiliary_option_to_a_remapped_primary_control(
        self, rc_staging_context: tuple[MagicMock, ParameterEditor], axis: str, original_channel: int, mapped_channel: int
    ) -> None:
        """
        Remapping a primary control moves its option protection to the new channel.

        GIVEN: A primary axis is staged on an auxiliary channel
        WHEN: The user attempts to assign an option to that channel and to its former channel
        THEN: The primary channel stays locked while the freed channel accepts a staged option without FC writes
        """
        controller, editor = rc_staging_context
        editor.current_step_parameters[f"RCMAP_{axis}"].set_new_value(str(mapped_channel))
        model = RCCalibrationDataModel(controller, editor)

        channels = model.get_channel_calibration()
        success, message = model.set_channel_option(mapped_channel, "300")

        assert channels[mapped_channel - 1]["function"] == axis.title()
        assert channels[mapped_channel - 1]["function_editable"] is False
        assert success is False
        assert message
        assert editor.current_step_parameters[f"RC{mapped_channel}_OPTION"].get_new_value() == 0
        assert channels[original_channel - 1]["function_editable"] is True
        assert model.set_channel_option(original_channel, "300")[0] is True
        assert editor.current_step_parameters[f"RC{original_channel}_OPTION"].get_new_value() == 300
        assert controller.fc_parameters[f"RCMAP_{axis}"] == original_channel
        controller.set_param.assert_not_called()

    def test_downloaded_mapping_protects_primary_channels_without_staged_mapping_rows(
        self, rc_staging_context: tuple[MagicMock, ParameterEditor]
    ) -> None:
        """
        Downloaded custom mappings are respected when no mapping edit is staged.

        GIVEN: The FC maps roll to CH6 and the step has no RCMAP_ROLL row
        WHEN: Channel functions are queried and a CH6 option is requested
        THEN: CH6 is locked and CH1 remains available for an auxiliary option
        """
        controller, editor = rc_staging_context
        controller.fc_parameters["RCMAP_ROLL"] = 6
        del editor.current_step_parameters["RCMAP_ROLL"]
        model = RCCalibrationDataModel(controller, editor)

        assert model.get_channel_calibration()[5]["function_editable"] is False
        assert model.set_channel_option(6, "300")[0] is False
        assert model.set_channel_option(1, "300")[0] is True
        controller.set_param.assert_not_called()

    def test_rover_mode_channel_takes_priority_over_flight_mode_channel(
        self, rc_staging_context: tuple[MagicMock, ParameterEditor]
    ) -> None:
        """
        Rover's MODE_CH determines which channel is shown and protected as Mode.

        GIVEN: MODE_CH selects CH8 and FLTMODE_CH still names CH5
        WHEN: The user views channels and tries to set auxiliary options
        THEN: CH8 is Mode and locked, while CH5 is available
        """
        controller, editor = rc_staging_context
        controller.fc_parameters["MODE_CH"] = 8.0
        model = RCCalibrationDataModel(controller, editor)

        channels = model.get_channel_calibration()

        assert channels[7]["function"] == "Mode"
        assert channels[7]["function_editable"] is False
        assert channels[4]["function"] == ""
        assert channels[4]["function_editable"] is True
        assert model.set_channel_option(8, "300")[0] is False
        assert model.set_channel_option(5, "300")[0] is True
        assert editor.current_step_parameters["RC5_OPTION"].get_new_value() == 300
        controller.set_param.assert_not_called()

    def test_staged_rover_mode_channel_updates_display_and_option_protection(
        self, rc_staging_context: tuple[MagicMock, ParameterEditor]
    ) -> None:
        """
        A pending MODE_CH edit immediately changes the protected channel.

        GIVEN: The FC uses CH8 for Mode and the editor stages MODE_CH=9
        WHEN: The user views channels and sets an auxiliary option
        THEN: CH9 is protected and CH8 becomes available without an FC write
        """
        controller, editor = rc_staging_context
        controller.fc_parameters["MODE_CH"] = 8.0
        editor.current_step_parameters["MODE_CH"] = ArduPilotParameter("MODE_CH", Par(8.0, "Existing reason"), fc_value=8.0)
        editor.current_step_parameters["MODE_CH"].set_new_value("9")
        model = RCCalibrationDataModel(controller, editor)

        channels = model.get_channel_calibration()

        assert channels[8]["function"] == "Mode"
        assert channels[8]["function_editable"] is False
        assert channels[7]["function"] == ""
        assert channels[7]["function_editable"] is True
        assert model.set_channel_option(9, "300")[0] is False
        assert model.set_channel_option(8, "300")[0] is True
        assert controller.fc_parameters["MODE_CH"] == 8.0
        controller.set_param.assert_not_called()

    @pytest.mark.parametrize("mode_channel", [nan, float("inf"), -1.0, 17.0, 8.5])
    def test_invalid_rover_mode_channel_uses_channel_eight(
        self, rc_staging_context: tuple[MagicMock, ParameterEditor], mode_channel: float
    ) -> None:
        """
        An invalid Rover mode setting falls back to the Rover default.

        GIVEN: MODE_CH is non-finite, out of range, or fractional
        WHEN: Channel functions and editability are queried
        THEN: CH8 is shown and protected as Mode
        """
        controller, editor = rc_staging_context
        controller.fc_parameters["MODE_CH"] = mode_channel
        model = RCCalibrationDataModel(controller, editor)

        channels = model.get_channel_calibration()

        assert channels[7]["function"] == "Mode"
        assert channels[7]["function_editable"] is False
        assert model.set_channel_option(8, "300")[0] is False
        controller.set_param.assert_not_called()

    def test_rover_mode_channel_zero_leaves_auxiliary_channels_available(
        self, rc_staging_context: tuple[MagicMock, ParameterEditor]
    ) -> None:
        """
        Disabling Rover's mode channel leaves no auxiliary channel reserved for it.

        GIVEN: MODE_CH is zero
        WHEN: The user views channels and assigns an option to CH8
        THEN: No channel is marked Mode and CH8 accepts the option
        """
        controller, editor = rc_staging_context
        controller.fc_parameters["MODE_CH"] = 0.0
        model = RCCalibrationDataModel(controller, editor)

        channels = model.get_channel_calibration()

        assert all("Mode" not in channel["function"] for channel in channels)
        assert channels[7]["function_editable"] is True
        assert model.set_channel_option(8, "300")[0] is True
        controller.set_param.assert_not_called()


@pytest.mark.parametrize("template_name", ["Holybro_X500_mig", "empty_4.6.x_mig"])
def test_migration_templates_expose_editable_rc_mapping_in_controller_step(template_name: str) -> None:
    """
    Both migration templates place channel mapping and the plugin in the RC controller step.

    GIVEN: A bundled migration template
    WHEN: Its numbered parameter file and step configuration are loaded
    THEN: All four mappings are present, imported and editable, and the plugin is registered in schema-valid JSON
    """
    package = Path(__file__).parents[2] / "ardupilot_methodic_configurator"
    template = package / "vehicle_templates" / "ArduCopter" / template_name
    config = json.loads((template / "configuration_steps_ArduCopter.json").read_text(encoding="utf-8"))
    validate(config, json.loads((package / "configuration_steps_schema.json").read_text(encoding="utf-8")))
    filename = "06_remote_controller_controller.param"
    step = config["steps"][filename]
    parameters = (template / filename).read_text(encoding="utf-8")
    assert step["plugin"]["name"] == "rc_calibration"
    for name, value in (("RCMAP_ROLL", 1), ("RCMAP_PITCH", 2), ("RCMAP_THROTTLE", 3), ("RCMAP_YAW", 4)):
        assert f"{name},{value}" in parameters
        assert any(re.fullmatch(pattern, name) for pattern in step["autoimport_nondefault_regexp"])
        assert name in step["add_parameters"]
        assert name not in step.get("forced_parameters", {})
        assert name not in step.get("derived_parameters", {})
