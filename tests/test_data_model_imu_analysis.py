#!/usr/bin/env python3

"""
Behavior-driven tests for IMU log quality and analysis data models.

This module contains comprehensive tests for ImuLogQualityModel and
ImuLogAnalysis, focusing on user workflows and business value rather
than implementation details.

SPDX-FileCopyrightText: 2026 Omkar Sarkar <omkarsarkar24@gmail.com>

SPDX-License-Identifier: GPL-3.0-or-later
"""

from typing import Any

import numpy as np
import pytest

from ardupilot_methodic_configurator.log_analysis.data_model_log_analysis_context import LogAnalysisContext
from ardupilot_methodic_configurator.log_analysis.data_model_log_quality import LogQualityState
from ardupilot_methodic_configurator.log_analysis.data_model_quality_imu import ImuLogAnalysis, ImuLogQualityModel

# pylint: disable=redefined-outer-name


class FakeLogData:
    """Minimal real test double for LogData, standing in for the system's log parser."""

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
def imu_apm_doc() -> dict:
    """Fixture providing apm.pdef.xml-shaped metadata for LOG_BITMASK and INS_TCALn_ENABLE."""
    return {
        "LOG_BITMASK": {"fields": {"Bitmask": "7:IMU"}},
        "INS_TCAL1_ENABLE": {"values": {"0": "Disabled", "1": "Enabled", "2": "Learning"}},
        "INS_TCAL2_ENABLE": {"values": {"0": "Disabled", "1": "Enabled", "2": "Learning"}},
        "INS_TCAL3_ENABLE": {"values": {"0": "Disabled", "1": "Enabled", "2": "Learning"}},
    }


@pytest.fixture
def healthy_imu_columns() -> dict[str, list[float]]:
    """Fixture providing a healthy IMU message: zero errors, healthy flags, non-zero signal."""
    return {
        "EG": [0.0, 0.0],
        "EA": [0.0, 0.0],
        "GH": [1.0, 1.0],
        "AH": [1.0, 1.0],
        "GyrX": [0.01, -0.01],
        "GyrY": [0.02, -0.02],
        "GyrZ": [0.03, -0.03],
        "AccX": [0.1, -0.1],
        "AccY": [0.2, -0.2],
        "AccZ": [-9.8, -9.8],
    }


def _context(parameters: dict[str, float] | None = None, *, apm_doc: dict | None = None) -> LogAnalysisContext:
    """Build a LogAnalysisContext with sensible empty defaults for fields a given test doesn't care about."""
    return LogAnalysisContext(
        parameters=parameters or {},
        configuration_steps={},
        apm_doc=apm_doc,
        vehicle_components={},
    )


class TestImuLogQualityModelHealth:
    """Test presence and health checks for IMU telemetry."""

    def test_user_sees_good_quality_for_a_healthy_imu(self, healthy_imu_columns, imu_apm_doc) -> None:
        """
        User sees a clean quality report for a healthy IMU.

        GIVEN: IMU data with zero error counts, healthy flags, and non-zero signal
        WHEN: The IMU quality model runs
        THEN: It reports available data with no issues
        """
        # Arrange: healthy IMU data provided by fixture
        log_data = FakeLogData({"IMU": healthy_imu_columns})
        model = ImuLogQualityModel(log_data, _context(apm_doc=imu_apm_doc))

        # Act: run the quality check
        result = model.check()

        # Assert: no issues, informational state
        assert result.available is True
        assert result.state == LogQualityState.INFO
        assert not result.issues

    def test_user_is_warned_about_a_nonzero_gyro_error_count(self, healthy_imu_columns, imu_apm_doc) -> None:
        """
        User is warned when the gyroscope reports internal errors during the flight.

        GIVEN: EG (gyro error count) is nonzero at some point
        WHEN: The IMU quality model runs
        THEN: It reports a gyroscope error issue
        """
        # Arrange: EG goes nonzero partway through the flight
        columns = dict(healthy_imu_columns)
        columns["EG"] = [0.0, 3.0]
        log_data = FakeLogData({"IMU": columns})
        model = ImuLogQualityModel(log_data, _context(apm_doc=imu_apm_doc))

        # Act: run the quality check
        result = model.check()

        # Assert: gyroscope error issue reported
        assert any("Gyroscope error count" in issue.message for issue in result.issues)

    def test_user_is_warned_when_accelerometer_health_drops(self, healthy_imu_columns, imu_apm_doc) -> None:
        """
        User is warned when the accelerometer reports unhealthy during the flight.

        GIVEN: AH (accelerometer health) drops to 0 at some point
        WHEN: The IMU quality model runs
        THEN: It reports an accelerometer health issue
        """
        # Arrange: AH drops to unhealthy partway through the flight
        columns = dict(healthy_imu_columns)
        columns["AH"] = [1.0, 0.0]
        log_data = FakeLogData({"IMU": columns})
        model = ImuLogQualityModel(log_data, _context(apm_doc=imu_apm_doc))

        # Act: run the quality check
        result = model.check()

        # Assert: accelerometer health issue reported
        assert any("Accelerometer reported unhealthy" in issue.message for issue in result.issues)

    def test_user_is_warned_when_a_gyro_axis_is_flat_zero(self, healthy_imu_columns, imu_apm_doc) -> None:
        """
        User is warned when a gyroscope axis never reports a real reading.

        GIVEN: GyrX is zero throughout the flight
        WHEN: The IMU quality model runs
        THEN: It reports the axis as possibly not reading
        """
        # Arrange: GyrX flat zero throughout
        columns = dict(healthy_imu_columns)
        columns["GyrX"] = [0.0, 0.0]
        log_data = FakeLogData({"IMU": columns})
        model = ImuLogQualityModel(log_data, _context(apm_doc=imu_apm_doc))

        # Act: run the quality check
        result = model.check()

        # Assert: flat-zero axis flagged
        assert any("GyrX is zero throughout" in issue.message for issue in result.issues)


class TestImuLogQualityModelAbsenceDiagnosis:  # pylint: disable=too-few-public-methods
    """Test diagnosing why IMU data is absent from a log."""

    def test_user_is_told_to_check_log_bitmask_when_imu_bit_is_disabled(self, imu_apm_doc) -> None:
        """
        User is pointed at LOG_BITMASK when IMU logging was never enabled.

        GIVEN: No IMU data and LOG_BITMASK excludes the IMU bit
        WHEN: The IMU quality model runs
        THEN: It reports the absence as a LOG_BITMASK configuration issue
        """
        # Arrange: no IMU data, bitmask excludes IMU logging
        log_data = FakeLogData({})
        model = ImuLogQualityModel(log_data, _context({"LOG_BITMASK": 0.0}, apm_doc=imu_apm_doc))

        # Act: run the quality check
        result = model.check()

        # Assert: absence diagnosed via LOG_BITMASK
        assert result.available is False
        assert "LOG_BITMASK" in result.reason


class TestImuLogAnalysisTemperatureCalibrationState:
    """Test temperature calibration enable/disable/in-progress state detection."""

    def test_user_is_recommended_to_calibrate_when_temp_cal_is_not_enabled(self) -> None:
        """
        User is nudged to run temperature calibration when it has never been enabled.

        GIVEN: INS_TCAL1_ENABLE is 0 (disabled)
        WHEN: Temperature calibration analysis runs
        THEN: It suggests running calibration, without proposing a one-click fix
        """
        # Arrange: single-IMU board, calibration disabled
        log_data = FakeLogData({})
        model = ImuLogAnalysis(log_data, _context({"INS_TCAL1_ENABLE": 0.0}, apm_doc=imu_apm_doc))

        # Act: run temperature calibration analysis
        outcomes = model.check_temperature_calibration()

        # Assert: one suggestion, no unsafe suggested_value
        assert len(outcomes) == 1
        assert outcomes[0].param_name == "INS_TCAL1_ENABLE"
        assert "not enabled" in outcomes[0].message

    def test_user_sees_calibration_in_progress_status(self) -> None:
        """
        User sees that a calibration is currently running, not yet complete.

        GIVEN: INS_TCAL1_ENABLE is 2 (learning in progress)
        WHEN: Temperature calibration analysis runs
        THEN: It reports the calibration as not yet complete
        """
        # Arrange: calibration in progress
        log_data = FakeLogData({})
        model = ImuLogAnalysis(log_data, _context({"INS_TCAL1_ENABLE": 2.0}, apm_doc=imu_apm_doc))

        # Act: run temperature calibration analysis
        outcomes = model.check_temperature_calibration()

        # Assert: in-progress status reported
        assert "in progress" in outcomes[0].message

    def test_user_sees_only_present_imu_instances_analyzed(self) -> None:
        """
        User sees analysis limited to IMU instances actually present on their board.

        GIVEN: Only INS_TCAL1_ENABLE is present (single-IMU board)
        WHEN: Temperature calibration analysis runs
        THEN: Only instance 1 is analyzed, instances 2 and 3 are silently skipped
        """
        # Arrange: only instance 1's param exists
        log_data = FakeLogData({})
        model = ImuLogAnalysis(log_data, _context({"INS_TCAL1_ENABLE": 0.0}, apm_doc=imu_apm_doc))

        # Act: run temperature calibration analysis
        outcomes = model.check_temperature_calibration()

        # Assert: only one finding, for instance 1
        assert len(outcomes) == 1
        assert outcomes[0].param_name == "INS_TCAL1_ENABLE"


class TestImuLogAnalysisTemperatureSpread:
    """Test the sourced spread thresholds (10C required, 25C recommended) for completed calibrations."""

    def test_user_sees_good_coverage_for_a_wide_freezer_to_desk_spread(self, imu_apm_doc) -> None:
        """
        User sees a positive result for a calibration meeting the recommended range.

        GIVEN: A completed calibration with a 30 degree spread from a cold start
        WHEN: Temperature calibration analysis runs
        THEN: It reports good coverage with no warnings
        """
        # Arrange: -15C to 15C, a 30 degree spread
        log_data = FakeLogData({})
        model = ImuLogAnalysis(
            log_data,
            _context(
                {
                    "INS_TCAL1_ENABLE": 1.0,
                    "INS_ACC1_CALTEMP": 25.0,
                    "INS_GYR1_CALTEMP": 25.0,
                    "INS_TCAL1_TMIN": -15.0,
                    "INS_TCAL1_TMAX": 15.0,
                },
                apm_doc=imu_apm_doc,
            ),
        )

        # Act: run temperature calibration analysis
        outcomes = model.check_temperature_calibration()

        # Assert: single "good coverage" finding with the correct spread value
        assert len(outcomes) == 1
        assert "good coverage" in outcomes[0].message
        assert outcomes[0].value == pytest.approx(30.0)

    def test_user_is_warned_when_spread_is_below_ardupilots_required_minimum(self, imu_apm_doc) -> None:
        """
        User is warned that a calibration doesn't meet ArduPilot's own hard requirement.

        GIVEN: A completed calibration with only a 5 degree spread, starting above freezing
        WHEN: Temperature calibration analysis runs
        THEN: It reports both the warm-start caveat and the spread as below ArduPilot's hard minimum
        """
        # Arrange: 18C to 23C, only a 5 degree spread, and a warm start
        log_data = FakeLogData({})
        model = ImuLogAnalysis(
            log_data,
            _context(
                {
                    "INS_TCAL1_ENABLE": 1.0,
                    "INS_ACC1_CALTEMP": 20.0,
                    "INS_GYR1_CALTEMP": 20.0,
                    "INS_TCAL1_TMIN": 18.0,
                    "INS_TCAL1_TMAX": 23.0,
                },
                apm_doc=imu_apm_doc,
            ),
        )

        # Act: run temperature calibration analysis
        outcomes = model.check_temperature_calibration()

        # Assert: warm-start caveat, then below-minimum spread finding
        assert len(outcomes) == 2
        assert "above freezing" in outcomes[0].message
        assert "below ArduPilot's required minimum" in outcomes[1].message

    def test_user_sees_both_a_warm_start_caveat_and_a_below_recommended_spread_finding(self, imu_apm_doc) -> None:
        """
        User sees both the warm-start caveat and the resulting sub-recommended spread.

        GIVEN: A calibration that started above freezing with a 20 degree spread
        WHEN: Temperature calibration analysis runs
        THEN: It reports both the warm-start caveat and a below-recommended spread finding
        """
        # Arrange: 10C to 30C - warm start, meets minimum but below recommended
        log_data = FakeLogData({})
        model = ImuLogAnalysis(
            log_data,
            _context(
                {
                    "INS_TCAL1_ENABLE": 1.0,
                    "INS_ACC1_CALTEMP": 30.0,
                    "INS_GYR1_CALTEMP": 30.0,
                    "INS_TCAL1_TMIN": 10.0,
                    "INS_TCAL1_TMAX": 30.0,
                },
                apm_doc=imu_apm_doc,
            ),
        )

        # Act: run temperature calibration analysis
        outcomes = model.check_temperature_calibration()

        # Assert: two findings, warm-start then spread
        assert len(outcomes) == 2
        assert "above freezing" in outcomes[0].message
        assert "below the recommended" in outcomes[1].message


class TestImuLogAnalysisInvalidCalTemp:  # pylint: disable=too-few-public-methods
    """Test detection of an invalid CALTEMP baseline on a calibrated IMU."""

    def test_user_is_warned_when_caltemp_baseline_was_never_set(self, imu_apm_doc) -> None:
        """
        User is warned that calibration data may be unreliable due to a missing accel/gyro baseline.

        GIVEN: INS_TCAL1_ENABLE is 1 (calibrated) but CALTEMP was never set (-300 sentinel)
        WHEN: Temperature calibration analysis runs
        THEN: It reports the calibration data as potentially unreliable
        """
        # Arrange: enabled but CALTEMP still at the invalid -300 default
        log_data = FakeLogData({})
        model = ImuLogAnalysis(
            log_data,
            _context(
                {
                    "INS_TCAL1_ENABLE": 1.0,
                    "INS_ACC1_CALTEMP": -300.0,
                    "INS_GYR1_CALTEMP": -300.0,
                    "INS_TCAL1_TMIN": -15.0,
                    "INS_TCAL1_TMAX": 15.0,
                },
                apm_doc=imu_apm_doc,
            ),
        )

        # Act: run temperature calibration analysis
        outcomes = model.check_temperature_calibration()

        # Assert: single "never performed" finding, spread not evaluated
        assert len(outcomes) == 1
        assert "never performed" in outcomes[0].message
