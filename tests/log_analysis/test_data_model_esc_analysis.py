#!/usr/bin/env python3

"""
Behavior-driven tests for ESC log analysis data models.

This module contains tests for EscLogAnalysis checks, focusing on user
workflows and business value rather than implementation details.

SPDX-FileCopyrightText: 2026 Omkar Sarkar <omkarsarkar24@gmail.com>

SPDX-License-Identifier: GPL-3.0-or-later
"""

from typing import Any

import numpy as np
import pytest

from ardupilot_methodic_configurator.log_analysis.data_model_availability_esc import EscLogAnalysis
from ardupilot_methodic_configurator.log_analysis.data_model_log_analysis_context import LogAnalysisContext

# pylint: disable=redefined-outer-name


class FakeLogData:
    """Minimal test double for LogData, standing in for the system's log parser."""

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
def esc_apm_doc() -> dict:
    """Fixture providing apm.pdef.xml-shaped metadata for MOT_PWM_TYPE and SERVO1_FUNCTION."""
    return {
        "MOT_PWM_TYPE": {"values": {"0": "Normal", "4": "DShot150", "6": "DShot600"}},
        "SERVO1_FUNCTION": {
            "values": {
                "0": "Disabled",
                "33": "Motor1",
                "34": "Motor2",
                "35": "Motor3",
                "36": "Motor4",
                "164": "Motor17",
            }
        },
    }


@pytest.fixture
def esc_log_data() -> FakeLogData:
    """Fixture providing minimal ESC telemetry so EscLogAnalysis.analyse() runs."""
    return FakeLogData({"ESC": {"RPM": [1000.0, 1000.0]}})


def _context(parameters: dict[str, float] | None = None, *, apm_doc: dict | None = None) -> LogAnalysisContext:
    """Build a LogAnalysisContext with sensible empty defaults."""
    return LogAnalysisContext(
        parameters=parameters or {},
        configuration_steps={},
        apm_doc=apm_doc,
        vehicle_components={},
    )


class TestEscLogAnalysisTkoffRpmMin:
    """Test TKOFF_RPM_MIN validation through analyse()."""

    def test_user_is_warned_when_tkoff_rpm_min_is_zero(self, esc_log_data, esc_apm_doc) -> None:
        """
        User is warned to configure TKOFF_RPM_MIN when ESC telemetry is present and it is 0.

        GIVEN: ESC telemetry is logged and TKOFF_RPM_MIN is 0
        WHEN: Full ESC analysis runs
        THEN: It reports a TKOFF_RPM_MIN finding with value 0.0
        """
        # Arrange: ESC telemetry present with TKOFF_RPM_MIN disabled
        model = EscLogAnalysis(esc_log_data, _context({"TKOFF_RPM_MIN": 0.0}, apm_doc=esc_apm_doc))

        # Act: run full ESC analysis
        result = model.analyse()

        # Assert: single TKOFF_RPM_MIN finding emitted
        assert len(result.outcomes) == 1
        assert result.outcomes[0].param_name == "TKOFF_RPM_MIN"
        assert result.outcomes[0].value == pytest.approx(0.0)
        assert "TKOFF_RPM_MIN is 0" in result.outcomes[0].message

    @pytest.mark.parametrize("parameters", [{"TKOFF_RPM_MIN": 500.0}, {}])
    def test_user_sees_no_warning_when_tkoff_rpm_min_is_nonzero_or_missing(
        self, esc_log_data, esc_apm_doc, parameters: dict[str, float]
    ) -> None:
        """
        User sees no TKOFF_RPM_MIN warning when it is configured or absent from the log.

        GIVEN: ESC telemetry is logged and TKOFF_RPM_MIN is non-zero or absent
        WHEN: Full ESC analysis runs
        THEN: It produces no findings
        """
        # Arrange: valid or absent TKOFF_RPM_MIN
        model = EscLogAnalysis(esc_log_data, _context(parameters, apm_doc=esc_apm_doc))

        # Act: run full ESC analysis
        result = model.analyse()

        # Assert: no findings emitted
        assert not result.outcomes


class TestEscLogAnalysisBdmaskMatchesMotorOutputs:
    """Test SERVO_BLH_BDMASK validation against configured motor output channels through analyse()."""

    @pytest.mark.parametrize(
        "parameters",
        [
            # Non-DShot protocol (PWM)
            {"MOT_PWM_TYPE": 0.0, "SERVO_BLH_BDMASK": 31.0, "SERVO1_FUNCTION": 33.0},
            # DShot with BDMASK=0 (serial telemetry, not bidirectional DShot)
            {"MOT_PWM_TYPE": 6.0, "SERVO_BLH_BDMASK": 0.0, "SERVO1_FUNCTION": 33.0},
            # Matching full mask (channels 1-4 = 15)
            {
                "MOT_PWM_TYPE": 6.0,
                "SERVO_BLH_BDMASK": 15.0,
                "SERVO1_FUNCTION": 33.0,
                "SERVO2_FUNCTION": 34.0,
                "SERVO3_FUNCTION": 35.0,
                "SERVO4_FUNCTION": 36.0,
            },
            # Deliberate partial mask (only channels 1-2 of 4 motors = 3)
            {
                "MOT_PWM_TYPE": 6.0,
                "SERVO_BLH_BDMASK": 3.0,
                "SERVO1_FUNCTION": 33.0,
                "SERVO2_FUNCTION": 34.0,
                "SERVO3_FUNCTION": 35.0,
                "SERVO4_FUNCTION": 36.0,
            },
            # Motor on channel 17 (bit 16 = 65536)
            {"MOT_PWM_TYPE": 6.0, "SERVO_BLH_BDMASK": 65536.0, "SERVO17_FUNCTION": 164.0},
        ],
    )
    def test_user_sees_no_bdmask_warning_for_valid_or_non_dshot_configs(
        self, esc_log_data, esc_apm_doc, parameters: dict[str, float]
    ) -> None:
        """
        User sees no BDMASK warning for non-DShot, zero mask, matching mask, partial mask, or channels above 16.

        GIVEN: ESC telemetry is logged with a valid or non-bidirectional-DShot configuration
        WHEN: Full ESC analysis runs
        THEN: It produces no findings
        """
        # Arrange: valid or non-DShot configuration
        model = EscLogAnalysis(esc_log_data, _context(parameters, apm_doc=esc_apm_doc))

        # Act: run full ESC analysis
        result = model.analyse()

        # Assert: no findings emitted
        assert not result.outcomes

    def test_user_is_warned_when_bdmask_targets_non_motor_channel(self, esc_log_data, esc_apm_doc) -> None:
        """
        User is warned and offered a cleaned mask when SERVO_BLH_BDMASK includes a non-motor output.

        GIVEN: DShot is enabled and SERVO_BLH_BDMASK sets a bit on a non-motor channel (channel 5)
        WHEN: Full ESC analysis runs
        THEN: It reports SERVO_BLH_BDMASK and suggests the mask restricted to motor channels (15.0)
        """
        # Arrange: channels 1-4 are motors, channel 5 is Disabled, but BDMASK=31 (channels 1-5)
        parameters = {
            "MOT_PWM_TYPE": 6.0,
            "SERVO_BLH_BDMASK": 31.0,
            "SERVO1_FUNCTION": 33.0,
            "SERVO2_FUNCTION": 34.0,
            "SERVO3_FUNCTION": 35.0,
            "SERVO4_FUNCTION": 36.0,
            "SERVO5_FUNCTION": 0.0,
        }
        model = EscLogAnalysis(esc_log_data, _context(parameters, apm_doc=esc_apm_doc))

        # Act: run full ESC analysis
        result = model.analyse()

        # Assert: single BDMASK finding with cleaned suggested_value
        assert len(result.outcomes) == 1
        assert result.outcomes[0].param_name == "SERVO_BLH_BDMASK"
        assert result.outcomes[0].value == pytest.approx(31.0)
        assert result.outcomes[0].suggested_value == pytest.approx(15.0)
        assert "non-motor" in result.outcomes[0].message
