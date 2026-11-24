#!/usr/bin/env python3

"""
Behavior-driven tests for the control surface setup data model.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2026 Allister779

SPDX-License-Identifier: GPL-3.0-or-later
"""

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from ardupilot_methodic_configurator.data_model_parameter_editor import ParameterValueUpdateStatus
from ardupilot_methodic_configurator.plugins.data_model_control_surface_setup import (
    ControlSurfaceSetupDataModel,
    ControlSurfaceSetupError,
    EndpointKind,
    PlaneMode,
    ServoChannel,
    StickAxis,
)

# pylint: disable=redefined-outer-name,protected-access


def _fc_parameters() -> dict[str, float]:
    return {
        "SERVO1_FUNCTION": 4,  # left aileron
        "SERVO2_FUNCTION": 19,  # elevator
        "SERVO3_FUNCTION": 70,  # throttle: not a control surface
        "SERVO4_FUNCTION": 21,  # rudder
        "SERVO5_FUNCTION": 4,  # right aileron on its own output
        "SERVO6_FUNCTION": 75,  # tilt front left
        "SERVO7_FUNCTION": 76,  # tilt front right
        "SERVO1_REVERSED": 0,
        "SERVO1_MIN": 1100,
        "SERVO1_TRIM": 1500,
        "SERVO1_MAX": 1900,
        "SERVO6_MIN": 1000,
        "SERVO6_MAX": 2000,
        "SERVO6_REVERSED": 0,
        "RCMAP_ROLL": 1,
        "RCMAP_PITCH": 2,
        "RCMAP_YAW": 4,
        "RC1_MIN": 1000,
        "RC1_TRIM": 1500,
        "RC1_MAX": 2000,
        "BATT_ARM_VOLT": 11.0,
        "Q_TILT_ENABLE": 1,
        "Q_TILT_MASK": 3,
        "Q_TILT_TYPE": 0,
        "KFF_RDDRMIX": 0.5,
        "SYSID_MYGCS": 255,
    }


@pytest.fixture
def flight_controller() -> MagicMock:
    """A connected FC that accepts every request and echoes written parameters."""
    fc = MagicMock()
    fc.master = MagicMock()
    fc.fc_parameters = _fc_parameters()
    fc.set_param.return_value = (True, "")
    fc.set_flight_mode.return_value = (True, "")
    fc.send_rc_channels_override.return_value = (True, "")
    fc.request_servo_output_messages.return_value = (True, "")
    fc.is_battery_monitoring_enabled.return_value = True
    fc.request_periodic_battery_status.return_value = (True, "")
    fc.get_battery_statuses.return_value = ({0: (12.4, 0.5)}, "")
    fc.info = SimpleNamespace(system_id="1", component_id="1")
    return fc


@pytest.fixture
def model(flight_controller: MagicMock) -> ControlSurfaceSetupDataModel:
    """A data model without a parameter editor (standalone use)."""
    filesystem = SimpleNamespace(doc_dict={"Q_TILT_ENABLE": {"RebootRequired": True}})
    return ControlSurfaceSetupDataModel(flight_controller, filesystem)  # type: ignore[arg-type]


class TestChannelDiscovery:
    """The plugin only adjusts primary flight-control and tilt servos."""

    def test_user_sees_only_primary_flight_control_outputs(self, model: ControlSurfaceSetupDataModel) -> None:
        """GIVEN mixed servo functions WHEN listing surfaces THEN only aileron, elevator and rudder outputs appear."""
        channels = model.control_surface_channels()
        assert [(c.number, c.function) for c in channels] == [(1, 4), (2, 19), (4, 21), (5, 4)]

    def test_tilt_servos_are_listed_separately(self, model: ControlSurfaceSetupDataModel) -> None:
        """GIVEN tilt servo functions WHEN listing tilt servos THEN both front tilt outputs appear."""
        assert [c.number for c in model.tilt_servo_channels()] == [6, 7]

    def test_tilt_setup_requires_non_zero_mask(self, model: ControlSurfaceSetupDataModel) -> None:
        """GIVEN Q_TILT_MASK=0 WHEN checking tilt setup THEN the user is told to set the mask."""
        assert model.tilt_setup_problem() == ""
        model.flight_controller.fc_parameters["Q_TILT_MASK"] = 0
        assert "Q_TILT_MASK" in model.tilt_setup_problem()

    def test_non_tilt_rotor_is_detected(self, model: ControlSurfaceSetupDataModel) -> None:
        """GIVEN Q_TILT_ENABLE=0 WHEN checking THEN the plane is not treated as a tilt-rotor."""
        model.flight_controller.fc_parameters["Q_TILT_ENABLE"] = 0
        assert not model.is_tilt_rotor()


class TestBatteryCheck:
    """Servos need battery power above BATT_ARM_VOLT."""

    def test_voltage_above_arm_voltage_is_accepted(self, model: ControlSurfaceSetupDataModel) -> None:
        """GIVEN 12.4 V and BATT_ARM_VOLT 11 V WHEN checking THEN the check passes."""
        ok, message = model.battery_voltage_status()
        assert ok
        assert "12.40" in message

    def test_voltage_at_or_below_arm_voltage_is_rejected(
        self, model: ControlSurfaceSetupDataModel, flight_controller: MagicMock
    ) -> None:
        """GIVEN a voltage equal to BATT_ARM_VOLT WHEN checking THEN the check fails."""
        flight_controller.get_battery_statuses.return_value = ({0: (11.0, 0.0)}, "")
        ok, message = model.battery_voltage_status()
        assert not ok
        assert "BATT_ARM_VOLT" in message

    def test_disabled_battery_monitor_blocks_the_check(
        self, model: ControlSurfaceSetupDataModel, flight_controller: MagicMock
    ) -> None:
        """GIVEN no battery monitor WHEN checking THEN the user is told to enable it."""
        flight_controller.is_battery_monitoring_enabled.return_value = False
        ok, _message = model.battery_voltage_status()
        assert not ok


class TestFlightModes:
    """The plugin commands modes even if they are not configured in FLTMODEx."""

    def test_switching_mode_commands_the_fc_and_remembers_initial_mode(
        self, model: ControlSurfaceSetupDataModel, flight_controller: MagicMock
    ) -> None:
        """GIVEN the FC in RTL WHEN switching to FBWA then MANUAL and shutting down THEN RTL is restored."""
        model._current_mode = 11
        model.set_flight_mode(PlaneMode.FBWA)
        model.set_flight_mode(PlaneMode.MANUAL)
        assert model.current_mode_name() == "MANUAL"
        model.shutdown()
        assert [call.args[0] for call in flight_controller.set_flight_mode.call_args_list] == [5, 0, 11]

    def test_rejected_mode_change_is_reported(self, model: ControlSurfaceSetupDataModel, flight_controller: MagicMock) -> None:
        """GIVEN the FC refuses WHEN switching mode THEN a translated error is raised."""
        flight_controller.set_flight_mode.return_value = (False, "denied")
        with pytest.raises(ControlSurfaceSetupError, match="QSTABILIZE"):
            model.set_flight_mode(PlaneMode.QSTABILIZE)

    def test_heartbeat_and_servo_output_update_live_state(self, model: ControlSurfaceSetupDataModel) -> None:
        """GIVEN telemetry messages WHEN handled THEN mode and per-output PWM are available."""
        model._handle_message(SimpleNamespace(get_type=lambda: "HEARTBEAT", custom_mode=5))
        servo = SimpleNamespace(
            get_type=lambda: "SERVO_OUTPUT_RAW", port=0, **{f"servo{i}_raw": 1000 + i for i in range(1, 17)}
        )
        model._handle_message(servo)
        assert model.current_mode_name() == "FBWA"
        assert model.servo_pwm(2) == 1002
        port1 = SimpleNamespace(get_type=lambda: "SERVO_OUTPUT_RAW", port=1, **{f"servo{i}_raw": 0 for i in range(1, 17)})
        port1.servo1_raw = 1600
        model._handle_message(port1)
        assert model.servo_pwm(17) == 1600


class TestLiveAdjustments:
    """Edits are written to the FC immediately and validated first."""

    def test_reversing_a_servo_writes_it_live(self, model: ControlSurfaceSetupDataModel, flight_controller: MagicMock) -> None:
        """GIVEN aileron SERVO1 WHEN ticking Reversed THEN SERVO1_REVERSED=1 is sent and reflected."""
        channel = model.control_surface_channels()[0]
        model.set_servo_reversed(channel, reversed_=True)
        flight_controller.set_param.assert_called_with("SERVO1_REVERSED", 1.0)
        assert model.is_servo_reversed(channel)

    def test_rc_reversal_follows_rcmap(self, model: ControlSurfaceSetupDataModel, flight_controller: MagicMock) -> None:
        """GIVEN RCMAP_YAW=4 WHEN reversing yaw THEN RC4_REVERSED is written."""
        model.set_rc_reversed(StickAxis.YAW, reversed_=True)
        flight_controller.set_param.assert_called_with("RC4_REVERSED", 1.0)
        assert model.rc_reversed_parameters() == ["RC1_REVERSED", "RC2_REVERSED", "RC4_REVERSED"]

    def test_trim_outside_min_max_is_rejected(self, model: ControlSurfaceSetupDataModel, flight_controller: MagicMock) -> None:
        """GIVEN MIN=1100 WHEN setting TRIM=1050 THEN nothing is written and the user sees why."""
        channel = model.control_surface_channels()[0]
        with pytest.raises(ControlSurfaceSetupError, match="SERVO1_TRIM"):
            model.set_servo_endpoint(channel, EndpointKind.TRIM, 1050)
        flight_controller.set_param.assert_not_called()

    def test_out_of_range_pwm_is_rejected(self, model: ControlSurfaceSetupDataModel) -> None:
        """GIVEN the documented PWM range WHEN setting MAX=2500 THEN the range is reported."""
        channel = model.control_surface_channels()[0]
        assert "2200" in model.validate_servo_endpoint(channel, EndpointKind.MAX, 2500)

    @pytest.mark.parametrize(("trim", "warn"), [(1450, False), (1550, False), (1449, True), (1551, True)])
    def test_trim_warning_boundary(self, trim: int, warn: bool) -> None:
        """GIVEN a trim WHEN more than 50 µs from 1500 THEN mechanical adjustment is suggested."""
        assert ControlSurfaceSetupDataModel.trim_needs_mechanical_adjustment(trim) is warn

    def test_failed_write_raises(self, model: ControlSurfaceSetupDataModel, flight_controller: MagicMock) -> None:
        """GIVEN no connection WHEN writing THEN a connection error is raised."""
        flight_controller.master = None
        with pytest.raises(ControlSurfaceSetupError):
            model.write_parameter("SERVO1_TRIM", 1500)


class TestSimulatedSticks:
    """Sliders send RC overrides scaled to the RC calibration."""

    def test_full_right_roll_uses_rc_max(self, model: ControlSurfaceSetupDataModel, flight_controller: MagicMock) -> None:
        """GIVEN RC1 1000..2000 WHEN roll slider at +100 % THEN RC1 override is 2000 and others centred."""
        model.set_stick_fraction(StickAxis.ROLL, 1.0)
        model.send_stick_override()
        channels = flight_controller.send_rc_channels_override.call_args.args[0]
        assert channels == {1: 2000, 2: 1500, 4: 1500}
        assert model.override_active

    def test_half_left_roll_scales_below_trim(self, model: ControlSurfaceSetupDataModel) -> None:
        """GIVEN RC1 1000..2000 WHEN roll at -50 % THEN PWM is 1250."""
        model.set_stick_fraction(StickAxis.ROLL, -0.5)
        assert model.stick_pwm(StickAxis.ROLL) == 1250

    def test_release_hands_channels_back(self, model: ControlSurfaceSetupDataModel, flight_controller: MagicMock) -> None:
        """GIVEN an active override WHEN released THEN zero is sent for each stick channel."""
        model.send_stick_override()
        model.release_stick_override()
        assert flight_controller.send_rc_channels_override.call_args.args[0] == {1: 0, 2: 0, 4: 0}
        assert not model.override_active

    def test_other_gcs_id_is_flagged(self, model: ControlSurfaceSetupDataModel) -> None:
        """GIVEN SYSID_MYGCS=254 WHEN checking THEN the user is warned overrides will be ignored."""
        model.flight_controller.fc_parameters["SYSID_MYGCS"] = 254
        assert "SYSID_MYGCS" in model.rc_override_warning()


class TestTiltRotor:
    """Tilt servo forward and hover end points depend on reversal and tilt type."""

    def test_non_reversed_servo_is_vertical_at_min(self, model: ControlSurfaceSetupDataModel) -> None:
        """GIVEN a non-reversed continuous tilt servo THEN forward is MAX and hover is MIN."""
        channel = model.tilt_servo_channels()[0]
        assert model.tilt_endpoints(channel) == (EndpointKind.MAX, EndpointKind.MIN)

    def test_reversal_swaps_endpoints(self, model: ControlSurfaceSetupDataModel) -> None:
        """GIVEN a reversed tilt servo THEN forward is MIN."""
        channel = model.tilt_servo_channels()[0]
        model.set_servo_reversed(channel, reversed_=True)
        assert model.tilt_endpoints(channel) == (EndpointKind.MIN, EndpointKind.MAX)

    def test_tilt_servo_has_no_trim_constraint(self, model: ControlSurfaceSetupDataModel) -> None:
        """GIVEN a tilt servo WHEN MIN would exceed MAX THEN it is rejected, otherwise trim is ignored."""
        channel = model.tilt_servo_channels()[0]
        assert model.validate_servo_endpoint(channel, EndpointKind.MIN, 1200) == ""
        assert model.validate_servo_endpoint(channel, EndpointKind.MIN, 2000) != ""

    def test_only_tilt_settings_can_be_written(self, model: ControlSurfaceSetupDataModel) -> None:
        """GIVEN a non tilt parameter WHEN set as tilt setting THEN it is refused."""
        with pytest.raises(ControlSurfaceSetupError):
            model.set_tilt_setting("Q_TILT_ENABLE", 0)
        model.set_tilt_setting("Q_TILT_TYPE", 2)
        assert model.tilt_type() == 2


class TestSaving:
    """Saving verifies FC values and stages them in the current configuration step."""

    def test_verified_values_are_staged_with_a_reason(self, flight_controller: MagicMock) -> None:
        """GIVEN a live-written trim WHEN saving THEN it is read back and added to the current step."""
        parameter = MagicMock(change_reason="")
        editor = MagicMock()
        editor.current_step_parameters = {}

        def add(name: str) -> bool:
            editor.current_step_parameters[name] = parameter
            return True

        editor.add_parameter_to_current_file.side_effect = add
        editor.update_parameter_value.return_value = SimpleNamespace(status=ParameterValueUpdateStatus.UPDATED)
        model = ControlSurfaceSetupDataModel(flight_controller, SimpleNamespace(doc_dict={}), editor)  # type: ignore[arg-type]
        channel = ServoChannel(1, 4, "Aileron")
        model.set_servo_endpoint(channel, EndpointKind.TRIM, 1520)
        flight_controller.fetch_param.return_value = 1520.0

        result = model.save_parameters(["SERVO1_TRIM"], "trimmed")

        assert result.success
        editor.update_parameter_value.assert_called_once_with("SERVO1_TRIM", "1520", include_range_check=False)
        parameter.set_change_reason.assert_called_once_with("trimmed")

    def test_unconfirmed_value_is_reported(self, model: ControlSurfaceSetupDataModel, flight_controller: MagicMock) -> None:
        """GIVEN the FC reads back a different value WHEN saving THEN the parameter is listed as unconfirmed."""
        model.write_parameter("SERVO1_TRIM", 1520)
        flight_controller.fetch_param.return_value = 1500.0
        result = model.save_parameters(["SERVO1_TRIM"], "trimmed")
        assert result.mismatched == ["SERVO1_TRIM"]
        assert "SERVO1_TRIM" in result.message()

    def test_reboot_required_parameters_are_reported(self, model: ControlSurfaceSetupDataModel) -> None:
        """GIVEN a RebootRequired parameter was written THEN it is listed for reboot."""
        model.write_parameter("Q_TILT_ENABLE", 1)
        assert model.pending_reboot_parameters() == ["Q_TILT_ENABLE"]
