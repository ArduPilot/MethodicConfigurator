#!/usr/bin/env python3

"""
Behavior-driven tests for battery log availability and analysis data models.

This module contains comprehensive tests for BatteryLogAvailabilityModel and
BatteryLogAnalysis, focusing on user workflows and business value rather
than implementation details.

SPDX-FileCopyrightText: 2026 Omkar Sarkar <omkarsarkar24@gmail.com>

SPDX-License-Identifier: GPL-3.0-or-later
"""

from typing import Any

import numpy as np
import pytest

from ardupilot_methodic_configurator.log_analysis.data_model_availability_battery import (
    BatteryLogAnalysis,
    BatteryLogAvailabilityModel,
)
from ardupilot_methodic_configurator.log_analysis.data_model_log_analysis_context import LogAnalysisContext
from ardupilot_methodic_configurator.log_analysis.data_model_log_availability import LogAvailabilityState

# pylint: disable=redefined-outer-name


# pylint: disable=duplicate-code
class FakeLogData:
    """
    Test for LogData, standing in for the system's log parser.

    Reproduces get_message_columns/get_field's real contract (structured array
    with dtype.names, or None if the message is absent) without mocking the
    models under test.
    """

    def __init__(self, messages: dict[str, dict[str, list[float]]] | None = None) -> None:
        self._messages = messages or {}
        self.schemas: dict[str, Any] = {}

    def get_message_columns(self, message_name: str) -> np.ndarray | None:
        fields = self._messages.get(message_name)
        if not fields:
            return None
        length = len(next(iter(fields.values())))
        dtype = [(name, "f8") for name in fields]
        arr = np.zeros(length, dtype=dtype)
        for name, values in fields.items():
            arr[name] = values
        return arr

    def get_field(self, message_name: str, field_name: str, scaled: bool = True) -> np.ndarray:  # pylint: disable=unused-argument
        return np.asarray(self._messages[message_name][field_name], dtype=float)


@pytest.fixture
def battery_apm_doc() -> dict:
    """Fixture providing apm.pdef.xml-shaped metadata for LOG_BITMASK and ARMING_CHECK."""
    return {
        "LOG_BITMASK": {"fields": {"Bitmask": "9:Battery Monitor"}},
        "ARMING_CHECK": {"fields": {"Bitmask": "1:Barometer,8:Battery Level"}},
    }


@pytest.fixture
def battery_configuration_steps() -> dict:
    """Fixture providing configuration-step metadata for battery monitor/battery derived parameters."""
    return {
        "10_battery_monitor.param": {
            "related_bin_messages": {"BAT": {"name": "Battery"}},
            "derived_parameters": {
                "BATT_MONITOR": {
                    "New Value": "vehicle_components['Battery Monitor']['FC Connection']['Protocol']",
                    "Change Reason": "x",
                }
            },
        },
        "11_battery.param": {
            "forced_parameters": {
                "BATT_FS_CRT_ACT": {"New Value": 1, "Change Reason": "x"},
            },
            "derived_parameters": {
                "BATT_CAPACITY": {
                    "New Value": "vehicle_components['Battery']['Specifications']['Capacity mAh']",
                    "Change Reason": "x",
                },
            },
        },
    }


@pytest.fixture
def battery_vehicle_components() -> dict:
    """Fixture providing vehicle_components data matching a real GEPRC-style build."""
    return {
        "Battery Monitor": {"FC Connection": {"Protocol": 4}},
        "Battery": {"Specifications": {"Capacity mAh": 1550}},
        "Frame": {"Specifications": {"TOW max Kg": 0.75}},
    }


@pytest.fixture
def healthy_bat_log_data() -> FakeLogData:
    """Fixture providing a log with non-zero, healthy BAT telemetry."""
    return FakeLogData({"BAT": {"Volt": [22.0, 21.8], "Curr": [5.0, 5.2], "CurrTot": [10.0, 20.0]}})


def _context(
    parameters: dict[str, float] | None = None,
    *,
    apm_doc: dict | None = None,
    configuration_steps: dict | None = None,
    vehicle_components: dict | None = None,
) -> LogAnalysisContext:
    """Build a LogAnalysisContext with sensible empty defaults for fields a given test doesn't care about."""
    return LogAnalysisContext(
        parameters=parameters or {},
        configuration_steps=configuration_steps or {},
        apm_doc=apm_doc,
        vehicle_components=vehicle_components or {},
    )


class TestBatteryLogAvailabilityModelPresence:
    """Test presence and sensor-reading checks for battery telemetry."""

    def test_user_sees_good_availability_when_bat_data_is_present_and_healthy(
        self, healthy_bat_log_data, battery_apm_doc
    ) -> None:
        """
        User sees a clean availability report for a normally logged battery.

        GIVEN: A log with BAT data whose voltage and current are non-zero
        WHEN: The battery availability model runs
        THEN: It reports available data with no issues
        """
        # Arrange: healthy log data provided by fixture
        model = BatteryLogAvailabilityModel(healthy_bat_log_data, _context({"BATT_MONITOR": 4}, apm_doc=battery_apm_doc))

        # Act: run the availability check
        result = model.check()

        # Assert: no issues, informational state
        assert result.available is True
        assert result.state == LogAvailabilityState.INFO
        assert not result.issues

    def test_user_is_warned_when_voltage_is_stuck_at_zero(self, battery_apm_doc) -> None:
        """
        User is warned when the voltage sensor never reports a real reading.

        GIVEN: BAT data where Volt never leaves zero
        WHEN: The battery availability model runs
        THEN: It reports a availability issue about the sensor not reading
        """
        # Arrange: log where Volt is flat zero throughout
        log_data = FakeLogData({"BAT": {"Volt": [0.0, 0.0], "Curr": [1.0, 1.0], "CurrTot": [1.0, 2.0]}})
        model = BatteryLogAvailabilityModel(log_data, _context({"BATT_MONITOR": 4}, apm_doc=battery_apm_doc))

        # Act: run the availability check
        result = model.check()

        # Assert: warning state with a zero-reading issue
        assert result.state == LogAvailabilityState.WARNING
        assert any("zero throughout" in issue.message for issue in result.issues)


class TestBatteryLogAvailabilityModelFailsafeParameters:  # pylint: disable=too-few-public-methods
    """Test detection of disabled battery failsafe thresholds."""

    def test_user_is_warned_when_low_and_critical_voltage_failsafes_are_disabled(self, battery_apm_doc) -> None:
        """
        User is warned when both battery voltage failsafe thresholds are turned off.

        GIVEN: BATT_LOW_VOLT and BATT_CRT_VOLT are both 0 (disabled)
        WHEN: The battery availability model runs
        THEN: It reports both failsafe thresholds as disabled issues
        """
        # Arrange: log with valid telemetry but both failsafes at 0
        log_data = FakeLogData({"BAT": {"Volt": [22.0], "Curr": [1.0], "CurrTot": [1.0]}})
        model = BatteryLogAvailabilityModel(
            log_data, _context({"BATT_MONITOR": 4, "BATT_LOW_VOLT": 0, "BATT_CRT_VOLT": 0}, apm_doc=battery_apm_doc)
        )

        # Act: run the availability check
        result = model.check()

        # Assert: both failsafe-disabled issues present
        messages = [issue.message for issue in result.issues]
        assert any("low-voltage failsafe threshold disabled" in m for m in messages)
        assert any("critical-voltage failsafe threshold disabled" in m for m in messages)


class TestBatteryLogAvailabilityModelAbsenceDiagnosis:
    """Test diagnosing why BAT data is absent from a log."""

    def test_user_is_told_to_check_log_bitmask_when_battery_monitor_bit_is_disabled(self, battery_apm_doc) -> None:
        """
        User is pointed at LOG_BITMASK when battery logging was never enabled.

        GIVEN: No BAT data and LOG_BITMASK with the Battery Monitor bit cleared
        WHEN: The battery availability model runs
        THEN: It reports the absence as a LOG_BITMASK configuration issue, not a wiring problem
        """
        # Arrange: no BAT data, bitmask excludes battery monitor logging
        log_data = FakeLogData({})
        model = BatteryLogAvailabilityModel(
            log_data, _context({"LOG_BITMASK": 0.0, "BATT_MONITOR": 4.0}, apm_doc=battery_apm_doc)
        )

        # Act: run the availability check
        result = model.check()

        # Assert: absence diagnosed via LOG_BITMASK, not physical connection
        assert result.available is False
        assert "LOG_BITMASK" in result.reason

    def test_user_is_told_batt_monitor_is_disabled_when_bitmask_is_fine(self, battery_apm_doc) -> None:
        """
        User is pointed at BATT_MONITOR when logging is enabled but the monitor itself is off.

        GIVEN: No BAT data, LOG_BITMASK includes Battery Monitor logging, but BATT_MONITOR is 0
        WHEN: The battery availability model runs
        THEN: It reports BATT_MONITOR as the misconfiguration, not the physical connection
        """
        # Arrange: bitmask enabled, but BATT_MONITOR itself is 0
        log_data = FakeLogData({})
        model = BatteryLogAvailabilityModel(
            log_data, _context({"LOG_BITMASK": 512.0, "BATT_MONITOR": 0.0}, apm_doc=battery_apm_doc)
        )

        # Act: run the availability check
        result = model.check()

        # Assert: absence diagnosed via BATT_MONITOR, not LOG_BITMASK
        assert result.available is False
        assert "BATT_MONITOR is 0" in result.reason


class TestBatteryLogAnalysisCapacityRetention:
    """Test capacity-used-percentage analysis."""

    def test_user_sees_capacity_used_percentage_for_a_normal_flight(self) -> None:
        """
        User sees an accurate capacity-used percentage for a flight within rated capacity.

        GIVEN: A flight that consumed less current than the rated capacity
        WHEN: Capacity retention analysis runs
        THEN: It reports the correct percentage without flagging an anomaly
        """
        # Arrange: CurrTot is scaled to Ah by LogData: 500 mAh from a 1000 mAh pack
        log_data = FakeLogData({"BAT": {"CurrTot": [0.1, 0.5], "TimeUS": [0, 1_000_000]}})
        model = BatteryLogAnalysis(log_data, _context({"BATT_CAPACITY": 1000.0}))

        # Act: run capacity retention analysis
        outcomes = model.check_battery_capacity_retention()

        # Assert: 50% used, no param flagged
        assert len(outcomes) == 1
        assert outcomes[0].value == pytest.approx(50.0)
        assert outcomes[0].param_name is None

    def test_user_is_warned_when_consumed_current_exceeds_rated_capacity(self) -> None:
        """
        User is warned about a physically impossible over-100% capacity result.

        GIVEN: CurrTot exceeds the rated BATT_CAPACITY
        WHEN: Capacity retention analysis runs
        THEN: It flags the anomaly and points at BATT_CAPACITY as the likely cause
        """
        # Arrange: CurrTot is scaled to Ah by LogData: 1200 mAh against a 1000 mAh rated pack
        log_data = FakeLogData({"BAT": {"CurrTot": [1.2], "TimeUS": [1_000_000]}})
        model = BatteryLogAnalysis(log_data, _context({"BATT_CAPACITY": 1000.0}))

        # Act: run capacity retention analysis
        outcomes = model.check_battery_capacity_retention()

        # Assert: over-100% anomaly flagged with the right param
        assert len(outcomes) == 1

        outcome = outcomes[0]
        assert outcome.value is not None
        assert outcome.value > 100
        assert outcome.param_name == "BATT_CAPACITY"
        assert "exceeds 100%" in outcome.message


class TestBatteryLogAnalysisVoltageExtrema:
    """Test voltage spike/sag analysis against motor thresholds."""

    def test_user_is_warned_about_a_voltage_spike_above_motor_max_threshold(self) -> None:
        """
        User is warned when logged voltage exceeds the expected motor threshold.

        GIVEN: Volt exceeds 1.2x MOT_BAT_VOLT_MAX
        WHEN: Voltage extrema analysis runs
        THEN: It reports a spike finding tied to MOT_BAT_VOLT_MAX
        """
        # Arrange: voltage spikes to 30V against a 25V max threshold
        log_data = FakeLogData({"BAT": {"Volt": [25.0, 30.0], "TimeUS": [0, 1_000_000]}})
        model = BatteryLogAnalysis(log_data, _context({"MOT_BAT_VOLT_MAX": 25.0}))

        # Act: run voltage extrema analysis
        outcomes = model.check_voltage_extrema()

        # Assert: spike flagged against MOT_BAT_VOLT_MAX
        assert any(o.param_name == "MOT_BAT_VOLT_MAX" for o in outcomes)

    def test_user_sees_no_findings_for_voltage_within_normal_bounds(self) -> None:
        """
        User sees no false alarms when voltage stays within expected bounds.

        GIVEN: Volt stays within [0.8x MIN, 1.2x MAX]
        WHEN: Voltage extrema analysis runs
        THEN: It reports no findings
        """
        # Arrange: voltage stays comfortably within bounds
        log_data = FakeLogData({"BAT": {"Volt": [22.0, 23.0], "TimeUS": [0, 1_000_000]}})
        model = BatteryLogAnalysis(log_data, _context({"MOT_BAT_VOLT_MAX": 25.0, "MOT_BAT_VOLT_MIN": 19.0}))

        # Act: run voltage extrema analysis
        outcomes = model.check_voltage_extrema()

        # Assert: no findings
        assert not outcomes


class TestBatteryLogAnalysisEfficiency:
    """Test power-to-weight efficiency analysis."""

    def test_user_sees_power_to_weight_efficiency_when_frame_specs_are_available(self, battery_vehicle_components) -> None:
        """
        User sees a computed W/Kg efficiency figure when frame specs are known.

        GIVEN: vehicle_components has a Frame TOW max Kg specification
        WHEN: Efficiency analysis runs
        THEN: It reports a W/Kg finding computed from mean Volt * mean Curr / TOW
        """
        # Arrange: constant 20V, 4A flight, 0.75 Kg TOW frame
        log_data = FakeLogData({"BAT": {"Volt": [20.0, 20.0], "Curr": [4.0, 4.0], "TimeUS": [0, 1_000_000]}})
        model = BatteryLogAnalysis(log_data, _context({}, vehicle_components=battery_vehicle_components))

        # Act: run efficiency analysis
        outcomes = model.check_efficiency()

        # Assert: single finding matching the expected W/Kg computation
        assert len(outcomes) == 1
        assert outcomes[0].value == pytest.approx((20.0 * 4.0) / 0.75)

    def test_user_sees_no_efficiency_finding_when_frame_specs_are_missing(self) -> None:
        """
        User sees no guessed efficiency figure when the frame's weight is unknown.

        GIVEN: vehicle_components has no Frame specifications
        WHEN: Efficiency analysis runs
        THEN: It produces no findings rather than guessing
        """
        # Arrange: no vehicle_components at all
        log_data = FakeLogData({"BAT": {"Volt": [20.0], "Curr": [4.0], "TimeUS": [0]}})
        model = BatteryLogAnalysis(log_data, _context({}, vehicle_components={}))

        # Act: run efficiency analysis
        outcomes = model.check_efficiency()

        # Assert: no findings
        assert not outcomes


class TestBatteryLogAnalysisFailsafeOrdering:
    """Test failsafe voltage ordering analysis, sourced from ArduPilot's own arming checks."""

    def test_user_is_warned_when_critical_voltage_is_not_below_low_voltage(self) -> None:
        """
        User is warned about an inverted failsafe voltage configuration.

        GIVEN: BATT_CRT_VOLT is not lower than BATT_LOW_VOLT
        WHEN: Failsafe ordering analysis runs
        THEN: It reports the violation, sourced from ArduPilot's own arming check
        """
        # Arrange: equal critical/low thresholds, an inversion
        log_data = FakeLogData({})
        model = BatteryLogAnalysis(log_data, _context({"BATT_CRT_VOLT": 21.0, "BATT_LOW_VOLT": 21.0}))

        # Act: run failsafe ordering analysis
        outcomes = model.check_failsafe_ordering()

        # Assert: violation reported
        assert len(outcomes) == 1
        assert "not lower than" in outcomes[0].message

    def test_user_is_told_when_arming_checks_would_not_have_caught_the_violation(self, battery_apm_doc) -> None:
        """
        User learns whether ArduPilot's own arming checks would have caught the problem.

        GIVEN: A failsafe ordering violation AND ARMING_CHECK excludes Battery Level and All
        WHEN: Failsafe ordering analysis runs
        THEN: The finding notes that arming would not have been blocked
        """
        # Arrange: inversion plus ARMING_CHECK that skips the battery check
        log_data = FakeLogData({})
        model = BatteryLogAnalysis(
            log_data,
            _context({"BATT_CRT_VOLT": 21.0, "BATT_LOW_VOLT": 21.0, "ARMING_CHECK": 2.0}, apm_doc=battery_apm_doc),
        )

        # Act: run failsafe ordering analysis
        outcomes = model.check_failsafe_ordering()

        # Assert: bypass note included
        assert "would not have blocked arming" in outcomes[0].message

    def test_user_sees_no_findings_for_correctly_ordered_failsafe_thresholds(self) -> None:
        """
        User sees no false alarm when failsafe voltages are correctly ordered.

        GIVEN: BATT_CRT_VOLT is lower than BATT_LOW_VOLT
        WHEN: Failsafe ordering analysis runs
        THEN: It reports no findings
        """
        # Arrange: correct ordering
        log_data = FakeLogData({})
        model = BatteryLogAnalysis(log_data, _context({"BATT_CRT_VOLT": 19.8, "BATT_LOW_VOLT": 21.0}))

        # Act: run failsafe ordering analysis
        outcomes = model.check_failsafe_ordering()

        # Assert: no findings
        assert not outcomes


class TestBatteryLogAnalysisParameterDerivation:
    """Test comparison of actual battery parameters against AMC's own derived-parameter formulas."""

    def test_user_is_warned_when_a_parameter_disagrees_with_its_derived_formula(
        self, battery_configuration_steps, battery_vehicle_components
    ) -> None:
        """
        User is warned when a logged parameter does not match what AMC would derive for their vehicle.

        GIVEN: BATT_CAPACITY in the log disagrees with the value derived_parameters would compute
        WHEN: Parameter derivation analysis runs
        THEN: It reports the mismatch with a ready-to-use suggested_value
        """
        # Arrange: log claims 5000 mAh, vehicle_components says 1550 mAh
        log_data = FakeLogData({})
        model = BatteryLogAnalysis(
            log_data,
            _context(
                {"BATT_CAPACITY": 5000.0},
                configuration_steps=battery_configuration_steps,
                vehicle_components=battery_vehicle_components,
            ),
        )

        # Act: run parameter derivation analysis
        outcomes = model.check_battery_parameter_derivation()

        # Assert: mismatch found with the correct suggested value
        capacity_finding = next(o for o in outcomes if o.param_name == "BATT_CAPACITY")
        assert capacity_finding.suggested_value == pytest.approx(1550.0)

    def test_user_sees_no_finding_when_a_parameter_matches_its_derived_formula(
        self, battery_configuration_steps, battery_vehicle_components
    ) -> None:
        """
        User sees no false alarm when a logged parameter already matches the derived formula.

        GIVEN: BATT_CAPACITY in the log already matches the derived formula's result
        WHEN: Parameter derivation analysis runs
        THEN: It reports no mismatch for that parameter
        """
        # Arrange: log already matches vehicle_components' 1550 mAh
        log_data = FakeLogData({})
        model = BatteryLogAnalysis(
            log_data,
            _context(
                {"BATT_CAPACITY": 1550.0},
                configuration_steps=battery_configuration_steps,
                vehicle_components=battery_vehicle_components,
            ),
        )

        # Act: run parameter derivation analysis
        outcomes = model.check_battery_parameter_derivation()

        # Assert: no mismatch reported for BATT_CAPACITY
        assert not any(o.param_name == "BATT_CAPACITY" for o in outcomes)
