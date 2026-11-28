#!/usr/bin/env python3

"""
Behavior-driven tests for ESC log analysis data models.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-FileCopyrightText: 2026 Omkar Sarkar <omkarsarkar24@gmail.com>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import numpy as np
import pytest

from ardupilot_methodic_configurator.log_analysis.data_model_availability_esc import EscLogAnalysis
from ardupilot_methodic_configurator.log_analysis.data_model_log_data import LogData

# pylint: disable=redefined-outer-name


@pytest.fixture
def esc_apm_doc() -> dict:
    """Fixture providing apm.pdef.xml-shaped metadata for ESC parameters."""
    dshot_values = {"0": "Normal", "4": "DShot150", "6": "DShot600"}
    return {
        "MOT_PWM_TYPE": {"values": dshot_values},
        "Q_M_PWM_TYPE": {"values": dshot_values},
        "SERVO_BLH_OTYPE": {"values": {"0": "Disabled", "4": "DShot150", "6": "DShot600"}},
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


def _esc_log(vehicle_type: str = "ArduCopter") -> LogData:
    """Create a minimal LogData containing ESC RPM rows."""
    log = LogData(vehicle_type=vehicle_type)
    log.add_message_columns("ESC", np.array([(1000.0,), (1000.0,)], dtype=[("RPM", "f8")]))
    return log


class TestEscLogAnalysisTkoffRpmMin:
    """Test TKOFF_RPM_MIN and Q_TKOFF_RPM_MIN validation through analyse()."""

    @pytest.mark.parametrize(
        ("vehicle_type", "param_name"),
        [("ArduCopter", "TKOFF_RPM_MIN"), ("ArduPlane", "Q_TKOFF_RPM_MIN")],
    )
    def test_user_is_warned_when_tkoff_rpm_min_is_zero(
        self, esc_apm_doc, make_context, vehicle_type: str, param_name: str
    ) -> None:
        """Warn when minimum takeoff RPM is 0 with ESC telemetry present."""
        model = EscLogAnalysis(_esc_log(vehicle_type), make_context({param_name: 0.0}, apm_doc=esc_apm_doc))

        result = model.analyse()

        assert len(result.outcomes) == 1
        assert result.outcomes[0].param_name == param_name
        assert result.outcomes[0].value == pytest.approx(0.0)
        assert f"{param_name} is 0" in result.outcomes[0].message

    @pytest.mark.parametrize("parameters", [{"TKOFF_RPM_MIN": 500.0}, {}])
    def test_user_sees_no_warning_when_tkoff_rpm_min_is_nonzero_or_missing(
        self, esc_apm_doc, make_context, parameters: dict[str, float]
    ) -> None:
        """No warning when TKOFF_RPM_MIN is non-zero or absent."""
        model = EscLogAnalysis(_esc_log(), make_context(parameters, apm_doc=esc_apm_doc))

        assert not model.analyse().outcomes

    def test_fixed_wing_plane_with_q_enable_zero_skips_q_tkoff_rpm_min(self, esc_apm_doc, make_context) -> None:
        model = EscLogAnalysis(
            _esc_log("ArduPlane"),
            make_context({"Q_ENABLE": 0.0, "Q_TKOFF_RPM_MIN": 0.0}, apm_doc=esc_apm_doc),
        )

        assert not model.analyse().outcomes


class TestEscLogAnalysisBdmaskMatchesMotorOutputs:
    """Test SERVO_BLH_BDMASK validation against configured DShot outputs through analyse()."""

    @pytest.mark.parametrize(
        "parameters",
        [
            {"MOT_PWM_TYPE": 0.0, "SERVO_BLH_BDMASK": 31.0, "SERVO1_FUNCTION": 33.0},
            {"MOT_PWM_TYPE": 6.0, "SERVO_BLH_BDMASK": 0.0, "SERVO1_FUNCTION": 33.0},
            {
                "MOT_PWM_TYPE": 6.0,
                "SERVO_BLH_BDMASK": 15.0,
                "SERVO1_FUNCTION": 33.0,
                "SERVO2_FUNCTION": 34.0,
                "SERVO3_FUNCTION": 35.0,
                "SERVO4_FUNCTION": 36.0,
            },
            {
                "MOT_PWM_TYPE": 6.0,
                "SERVO_BLH_BDMASK": 3.0,
                "SERVO1_FUNCTION": 33.0,
                "SERVO2_FUNCTION": 34.0,
                "SERVO3_FUNCTION": 35.0,
                "SERVO4_FUNCTION": 36.0,
            },
            {"MOT_PWM_TYPE": 6.0, "SERVO_BLH_BDMASK": 65536.0, "SERVO17_FUNCTION": 164.0},
            # Auxiliary DShot output configured via SERVO_BLH_MASK (channel 5 = bit 4 = 16)
            {
                "MOT_PWM_TYPE": 6.0,
                "SERVO_BLH_OTYPE": 6.0,
                "SERVO_BLH_MASK": 16.0,
                "SERVO_BLH_BDMASK": 17.0,
                "SERVO1_FUNCTION": 33.0,
            },
            # Signed 32-bit mask with motor on output 32 (bit 31 = -2147483648)
            {"MOT_PWM_TYPE": 6.0, "SERVO_BLH_BDMASK": -2147483648.0, "SERVO32_FUNCTION": 33.0},
        ],
    )
    def test_user_sees_no_bdmask_warning_for_valid_or_non_dshot_configs(
        self, esc_apm_doc, make_context, parameters: dict[str, float]
    ) -> None:
        """No warning for non-DShot, zero mask, matching/partial masks, SERVO_BLH_MASK, or output 32."""
        model = EscLogAnalysis(_esc_log(), make_context(parameters, apm_doc=esc_apm_doc))

        assert not model.analyse().outcomes

    def test_user_is_warned_when_bdmask_targets_non_dshot_channel(self, esc_apm_doc, make_context) -> None:
        """Warn and suggest cleaned mask when SERVO_BLH_BDMASK includes a non-DShot channel."""
        parameters = {
            "MOT_PWM_TYPE": 6.0,
            "SERVO_BLH_BDMASK": 31.0,
            "SERVO1_FUNCTION": 33.0,
            "SERVO2_FUNCTION": 34.0,
            "SERVO3_FUNCTION": 35.0,
            "SERVO4_FUNCTION": 36.0,
            "SERVO5_FUNCTION": 0.0,
        }
        model = EscLogAnalysis(_esc_log(), make_context(parameters, apm_doc=esc_apm_doc))

        result = model.analyse()

        assert len(result.outcomes) == 1
        assert result.outcomes[0].param_name == "SERVO_BLH_BDMASK"
        assert result.outcomes[0].value == pytest.approx(31.0)
        assert result.outcomes[0].suggested_value == pytest.approx(15.0)

    def test_bdmask_signed_int32_suggestion_for_output_32(self, esc_apm_doc, make_context) -> None:
        """Keep suggested mask inside signed int32 range when output 32 is a motor."""
        parameters = {
            "MOT_PWM_TYPE": 6.0,
            "SERVO_BLH_BDMASK": -2147483632.0,  # bit 31 (motor) + bit 4 (disabled)
            "SERVO32_FUNCTION": 33.0,
            "SERVO5_FUNCTION": 0.0,
        }
        model = EscLogAnalysis(_esc_log(), make_context(parameters, apm_doc=esc_apm_doc))

        result = model.analyse()

        assert len(result.outcomes) == 1
        assert result.outcomes[0].suggested_value == pytest.approx(-2147483648.0)

    def test_quadplane_uses_q_m_pwm_type_for_bdmask_check(self, esc_apm_doc, make_context) -> None:
        """QuadPlane logs validate SERVO_BLH_BDMASK using Q_M_PWM_TYPE."""
        parameters = {
            "Q_M_PWM_TYPE": 6.0,
            "SERVO_BLH_BDMASK": 3.0,
            "SERVO1_FUNCTION": 33.0,
            "SERVO2_FUNCTION": 0.0,
        }
        model = EscLogAnalysis(_esc_log("ArduPlane"), make_context(parameters, apm_doc=esc_apm_doc))

        result = model.analyse()

        assert len(result.outcomes) == 1
        assert result.outcomes[0].param_name == "SERVO_BLH_BDMASK"
        assert result.outcomes[0].suggested_value == pytest.approx(1.0)

    def test_non_dshot_servo_blh_otype_does_not_whitelist_servo_blh_mask(self, esc_apm_doc, make_context) -> None:
        parameters = {
            "MOT_PWM_TYPE": 6.0,
            "SERVO_BLH_OTYPE": 0.0,
            "SERVO_BLH_MASK": 16.0,
            "SERVO_BLH_BDMASK": 17.0,
            "SERVO1_FUNCTION": 33.0,
        }
        model = EscLogAnalysis(_esc_log(), make_context(parameters, apm_doc=esc_apm_doc))

        result = model.analyse()

        assert len(result.outcomes) == 1
        assert result.outcomes[0].param_name == "SERVO_BLH_BDMASK"
        assert result.outcomes[0].suggested_value == pytest.approx(1.0)

    def test_non_finite_esc_parameters_are_ignored_without_error(self, esc_apm_doc, make_context) -> None:
        parameters = {
            "MOT_PWM_TYPE": float("nan"),
            "SERVO_BLH_BDMASK": float("nan"),
            "TKOFF_RPM_MIN": float("nan"),
        }
        model = EscLogAnalysis(_esc_log(), make_context(parameters, apm_doc=esc_apm_doc))

        assert not model.analyse().outcomes
