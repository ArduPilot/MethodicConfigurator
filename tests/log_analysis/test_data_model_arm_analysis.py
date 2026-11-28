#!/usr/bin/env python3

"""
Behavior-driven tests for ARM safety and frame setup log analysis.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-FileCopyrightText: 2026 Omkar Sarkar <omkarsarkar24@gmail.com>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import pytest

from ardupilot_methodic_configurator.log_analysis.data_model_availability_arm import ArmLogAnalysis
from ardupilot_methodic_configurator.log_analysis.data_model_log_data import LogData

# pylint: disable=redefined-outer-name


@pytest.fixture
def arm_apm_doc() -> dict:
    """Fixture providing apm.pdef.xml-shaped metadata for FRAME_CLASS, ARMING_CHECK, and FENCE_ENABLE."""
    frame_values = {"0": "Undefined", "1": "Quad", "2": "Hexa", "6": "Heli"}
    return {
        "FRAME_CLASS": {"values": frame_values},
        "Q_FRAME_CLASS": {"values": frame_values},
        "ARMING_CHECK": {"fields": {"Bitmask": "0:All, 1:Barometer, 2:Compass, 3:GPS lock"}},
        "FENCE_ENABLE": {"values": {"0": "Disabled", "1": "Enabled"}},
    }


class TestArmLogAnalysisFrameClass:
    """Test FRAME_CLASS and Q_FRAME_CLASS configuration validation through analyse()."""

    def test_user_is_warned_when_frame_class_is_undefined(self, arm_apm_doc, make_context) -> None:
        """Warn when FRAME_CLASS is 0 (Undefined)."""
        model = ArmLogAnalysis(LogData(), make_context({"FRAME_CLASS": 0.0}, apm_doc=arm_apm_doc))

        result = model.analyse()

        assert len(result.outcomes) == 1
        assert result.outcomes[0].param_name == "FRAME_CLASS"
        assert "Undefined" in result.outcomes[0].message

    def test_user_is_warned_when_quadplane_frame_class_is_undefined(self, arm_apm_doc, make_context) -> None:
        """Warn when Q_ENABLE is active and Q_FRAME_CLASS is 0 (Undefined)."""
        model = ArmLogAnalysis(LogData(), make_context({"Q_ENABLE": 1.0, "Q_FRAME_CLASS": 0.0}, apm_doc=arm_apm_doc))

        result = model.analyse()

        assert len(result.outcomes) == 1
        assert result.outcomes[0].param_name == "Q_FRAME_CLASS"

    def test_user_is_warned_when_frame_class_is_unrecognized(self, arm_apm_doc, make_context) -> None:
        """Warn when FRAME_CLASS has an undocumented value."""
        model = ArmLogAnalysis(LogData(), make_context({"FRAME_CLASS": 99.0}, apm_doc=arm_apm_doc))

        result = model.analyse()

        assert len(result.outcomes) == 1
        assert result.outcomes[0].param_name == "FRAME_CLASS"
        assert "unrecognized" in result.outcomes[0].message

    @pytest.mark.parametrize(
        "parameters",
        [
            {"FRAME_CLASS": 1.0},
            {"Q_ENABLE": 0.0, "Q_FRAME_CLASS": 0.0},
            {"Q_ENABLE": 1.0, "Q_FRAME_CLASS": 1.0},
            {},
        ],
    )
    def test_user_sees_no_warning_for_valid_or_inactive_frame_class(
        self, arm_apm_doc, make_context, parameters: dict[str, float]
    ) -> None:
        """No warning for valid frame classes or inactive QuadPlane parameters."""
        model = ArmLogAnalysis(LogData(), make_context(parameters, apm_doc=arm_apm_doc))

        assert not model.analyse().outcomes


class TestArmLogAnalysisArmingCheck:
    """Test ARMING_CHECK (pre-4.7) and ARMING_SKIPCHK (4.7+) validation through analyse()."""

    @pytest.mark.parametrize("arming_check", [0.0, 2.0])
    def test_user_is_warned_when_all_arming_checks_are_not_enabled(
        self, arm_apm_doc, make_context, arming_check: float
    ) -> None:
        """Warn when ARMING_CHECK does not include the 'All' bit."""
        model = ArmLogAnalysis(LogData(), make_context({"ARMING_CHECK": arming_check}, apm_doc=arm_apm_doc))

        result = model.analyse()

        assert len(result.outcomes) == 1
        assert result.outcomes[0].param_name == "ARMING_CHECK"
        assert result.outcomes[0].suggested_value == pytest.approx(1.0)

    @pytest.mark.parametrize("skip_chk", [-1.0, 4.0])
    def test_user_is_warned_when_arming_skipchk_is_nonzero(self, arm_apm_doc, make_context, skip_chk: float) -> None:
        """Warn on 4.7+ logs when ARMING_SKIPCHK skips any pre-arm checks."""
        model = ArmLogAnalysis(LogData(), make_context({"ARMING_SKIPCHK": skip_chk}, apm_doc=arm_apm_doc))

        result = model.analyse()

        assert len(result.outcomes) == 1
        assert result.outcomes[0].param_name == "ARMING_SKIPCHK"
        assert result.outcomes[0].suggested_value == pytest.approx(0.0)

    @pytest.mark.parametrize("parameters", [{"ARMING_CHECK": 1.0}, {"ARMING_SKIPCHK": 0.0}, {}])
    def test_user_sees_no_warning_when_all_arming_checks_enabled_or_absent(
        self, arm_apm_doc, make_context, parameters: dict[str, float]
    ) -> None:
        """No warning when all arming checks are enabled or parameters are absent."""
        model = ArmLogAnalysis(LogData(), make_context(parameters, apm_doc=arm_apm_doc))

        assert not model.analyse().outcomes


class TestArmLogAnalysisFenceEnable:
    """Test FENCE_ENABLE validation through analyse()."""

    def test_user_is_warned_without_blind_fix_when_geofence_is_disabled(self, arm_apm_doc, make_context) -> None:
        """Warn when FENCE_ENABLE is 0 without suggesting a blind auto-fix."""
        model = ArmLogAnalysis(LogData(), make_context({"FENCE_ENABLE": 0.0}, apm_doc=arm_apm_doc))

        result = model.analyse()

        assert len(result.outcomes) == 1
        assert result.outcomes[0].param_name == "FENCE_ENABLE"
        assert result.outcomes[0].suggested_value is None

    @pytest.mark.parametrize("parameters", [{"FENCE_ENABLE": 1.0}, {"FENCE_ENABLE": 0.0, "FENCE_AUTOENABLE": 3.0}, {}])
    def test_user_sees_no_warning_when_geofence_enabled_autoenabled_or_absent(
        self, arm_apm_doc, make_context, parameters: dict[str, float]
    ) -> None:
        """No warning when geofence is enabled, auto-enabled, or absent."""
        model = ArmLogAnalysis(LogData(), make_context(parameters, apm_doc=arm_apm_doc))

        assert not model.analyse().outcomes

    def test_non_finite_fence_autoenable_does_not_suppress_fence_warning(self, arm_apm_doc, make_context) -> None:
        model = ArmLogAnalysis(
            LogData(),
            make_context({"FENCE_ENABLE": 0.0, "FENCE_AUTOENABLE": float("nan")}, apm_doc=arm_apm_doc),
        )

        result = model.analyse()

        assert len(result.outcomes) == 1
        assert result.outcomes[0].param_name == "FENCE_ENABLE"


class TestArmLogAnalysisSlewRateLimit:
    """Test ATC_RAT_*_SMAX disabled check through analyse()."""

    @pytest.mark.parametrize("param_name", ["ATC_RAT_RLL_SMAX", "ATC_RAT_PIT_SMAX", "ATC_RAT_YAW_SMAX"])
    def test_user_is_warned_when_slew_rate_limiter_is_disabled(self, arm_apm_doc, make_context, param_name: str) -> None:
        """Warn when any rate-controller slew-rate limiter is set to 0."""
        model = ArmLogAnalysis(LogData(), make_context({param_name: 0.0}, apm_doc=arm_apm_doc))

        result = model.analyse()

        assert len(result.outcomes) == 1
        assert result.outcomes[0].param_name == param_name
        assert result.outcomes[0].value == pytest.approx(0.0)

    @pytest.mark.parametrize(
        "parameters",
        [
            {"ATC_RAT_RLL_SMAX": 50.0, "ATC_RAT_PIT_SMAX": 50.0, "ATC_RAT_YAW_SMAX": 50.0},
            {"ATC_RAT_RLL_SMAX": float("nan")},
            {},
        ],
    )
    def test_user_sees_no_warning_when_slew_rate_limiter_is_enabled_nonfinite_or_absent(
        self, arm_apm_doc, make_context, parameters: dict[str, float]
    ) -> None:
        """No warning when slew-rate limiters are enabled, non-finite, or absent."""
        model = ArmLogAnalysis(LogData(), make_context(parameters, apm_doc=arm_apm_doc))

        assert not model.analyse().outcomes
