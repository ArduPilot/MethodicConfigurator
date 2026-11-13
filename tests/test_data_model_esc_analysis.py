#!/usr/bin/env python3

"""
Mock tests for ESC availability and analysis models.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-FileCopyrightText: 2026 Omkar Sarkar <omkarsarkar24@gmail.com>

SPDX-License-Identifier: GPL-3.0-or-later
"""

from unittest.mock import MagicMock

import numpy as np
import pytest

from ardupilot_methodic_configurator.log_analysis import data_model_availability_esc
from ardupilot_methodic_configurator.log_analysis.data_model_availability_esc import EscLogAvailabilityModel
from ardupilot_methodic_configurator.log_analysis.data_model_log_analysis_context import LogAnalysisContext


def _context(
    parameters: dict[str, float] | None = None,
    apm_doc: MagicMock | None = None,
) -> LogAnalysisContext:
    return LogAnalysisContext(
        parameters=parameters or {},
        configuration_steps={},
        vehicle_components={},
        apm_doc=apm_doc,
    )


def _log_data_with_esc(records: np.ndarray, arm_records: np.ndarray | None = None) -> MagicMock:
    log_data = MagicMock()

    def _get_message_columns(message_name: str) -> np.ndarray | None:
        if message_name == "ESC":
            return records
        if message_name == "ARM":
            return arm_records
        return None

    def _get_field(message_name: str, field_name: str, **_kwargs) -> np.ndarray:
        source = records if message_name == "ESC" else arm_records
        assert source is not None
        return source[field_name]

    log_data.get_message_columns.side_effect = _get_message_columns
    log_data.get_field.side_effect = _get_field
    return log_data


def _log_data_without_esc() -> MagicMock:
    log_data = MagicMock()
    log_data.get_message_columns.return_value = None
    return log_data


class TestEscLogAvailabilityModel:
    """Tests for EscLogAvailabilityModel."""

    def test_check_returns_unavailable_when_esc_message_missing(self) -> None:
        log_data = _log_data_without_esc()
        model = EscLogAvailabilityModel(log_data, _context())

        result = model.check()

        assert result.available is False
        assert any("No ESC messages found" in issue.message for issue in result.issues)

    def test_check_reports_non_dshot_configuration_when_esc_message_missing(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(data_model_availability_esc, "find_matching_param_values", lambda *_args: {"4"})
        log_data = _log_data_without_esc()
        context = _context(parameters={"MOT_PWM_TYPE": 0.0}, apm_doc=MagicMock())
        model = EscLogAvailabilityModel(log_data, context)

        result = model.check()

        assert result.available is False
        assert "ESC telemetry not logged" in result.reason
        assert any("Set MOT_PWM_TYPE to a DShot variant" in issue.message for issue in result.issues)

    def test_check_reports_scripting_disabled_when_dshot_is_configured(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(data_model_availability_esc, "find_matching_param_values", lambda *_args: {"4"})
        log_data = _log_data_without_esc()
        context = _context(parameters={"MOT_PWM_TYPE": 4.0, "SCR_ENABLE": 0.0}, apm_doc=MagicMock())
        model = EscLogAvailabilityModel(log_data, context)

        result = model.check()

        assert result.available is False
        assert "scripting is disabled" in result.reason
