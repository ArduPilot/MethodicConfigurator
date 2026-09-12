#!/usr/bin/env python3

"""
Tests for VIBE availability and analysis models.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-FileCopyrightText: 2026 Omkar Sarkar <omkarsarkar24@gmail.com>

SPDX-License-Identifier: GPL-3.0-or-later
"""

from unittest.mock import MagicMock

import numpy as np
import pytest

from ardupilot_methodic_configurator.log_analysis.data_model_availability_vibe import VibeLogAnalysis, VibeLogAvailabilityModel
from ardupilot_methodic_configurator.log_analysis.data_model_log_analysis_context import LogAnalysisContext


def _context(parameters: dict[str, float] | None = None) -> LogAnalysisContext:
    return LogAnalysisContext(
        parameters=parameters or {},
        configuration_steps={},
        vehicle_components={},
        apm_doc=None,
    )


def _log_data_with_vibe(records: np.ndarray) -> MagicMock:
    log_data = MagicMock()
    log_data.get_message_columns.side_effect = lambda name: records if name == "VIBE" else None

    def _get_field(message_name: str, field_name: str, **_kwargs) -> np.ndarray:
        assert message_name == "VIBE"
        return records[field_name]

    log_data.get_field.side_effect = _get_field
    return log_data


def _log_data_without_vibe() -> MagicMock:
    log_data = MagicMock()
    log_data.get_message_columns.return_value = None
    log_data.parameters = {}
    return log_data


class TestVibeLogAvailabilityModel:
    """Tests for VibeLogAvailabilityModel."""

    def test_check_returns_unavailable_when_vibe_message_missing(self) -> None:
        log_data = _log_data_without_vibe()
        model = VibeLogAvailabilityModel(log_data, _context())

        result = model.check()

        assert result.available is False

    def test_check_returns_available_when_all_fields_present(self) -> None:
        records = np.array(
            [(0, 1.0, 2.0, 3.0, 0), (1, 1.0, 2.0, 3.0, 0)],
            dtype=[("TimeUS", "f8"), ("VibeX", "f8"), ("VibeY", "f8"), ("VibeZ", "f8"), ("Clip", "f8")],
        )
        log_data = _log_data_with_vibe(records)
        model = VibeLogAvailabilityModel(log_data, _context())

        result = model.check()

        assert result.available is True
        assert not result.issues

    def test_check_vibe_levels_reports_issue_when_axis_field_missing(self) -> None:
        records = np.array([(0, 1.0, 3.0, 0)], dtype=[("TimeUS", "f8"), ("VibeX", "f8"), ("VibeZ", "f8"), ("Clip", "f8")])
        log_data = _log_data_with_vibe(records)
        model = VibeLogAvailabilityModel(log_data, _context())

        issues = model.check_vibe_levels()

        assert any("VibeY" in issue.message for issue in issues)

    def test_check_clipping_reports_issue_when_clip_field_missing(self) -> None:
        records = np.array([(0, 1.0, 2.0, 3.0)], dtype=[("TimeUS", "f8"), ("VibeX", "f8"), ("VibeY", "f8"), ("VibeZ", "f8")])
        log_data = _log_data_with_vibe(records)
        model = VibeLogAvailabilityModel(log_data, _context())

        issues = model.check_clipping()

        assert any("Clip" in issue.message for issue in issues)


class TestVibeLogAnalysis:
    """Tests for VibeLogAnalysis."""

    def test_analyse_returns_unavailable_when_vibe_message_missing(self) -> None:
        log_data = _log_data_without_vibe()
        model = VibeLogAnalysis(log_data, _context())

        result = model.analyse()

        assert result.available is False
        assert not result.outcomes

    def test_check_vibration_levels_reports_no_finding_below_warning_threshold(self) -> None:
        records = np.array(
            [(0, 10.0, 10.0, 10.0, 0), (1_000_000, 10.0, 10.0, 10.0, 0)],
            dtype=[("TimeUS", "f8"), ("VibeX", "f8"), ("VibeY", "f8"), ("VibeZ", "f8"), ("Clip", "f8")],
        )
        log_data = _log_data_with_vibe(records)
        model = VibeLogAnalysis(log_data, _context())

        outcomes = model.check_vibration_levels()

        assert not outcomes

    def test_check_vibration_levels_reports_warning_between_thresholds(self) -> None:
        records = np.array(
            [(0.0, 10.0, 10.0, 10.0, 0), (1.0, 10.0, 40.8, 10.0, 0)],
            dtype=[("TimeUS", "f8"), ("VibeX", "f8"), ("VibeY", "f8"), ("VibeZ", "f8"), ("Clip", "f8")],
        )
        log_data = _log_data_with_vibe(records)
        model = VibeLogAnalysis(log_data, _context())

        outcomes = model.check_vibration_levels()

        assert len(outcomes) == 1
        assert "VibeY" in outcomes[0].message
        assert "40.8" in outcomes[0].message
        assert outcomes[0].timestamp_us == pytest.approx(1_000_000.0)

    def test_check_vibration_levels_reports_severe_at_or_above_severe_threshold(self) -> None:
        records = np.array(
            [(0, 10.0, 10.0, 10.0, 0), (1_000_000, 10.0, 10.0, 65.0, 0)],
            dtype=[("TimeUS", "f8"), ("VibeX", "f8"), ("VibeY", "f8"), ("VibeZ", "f8"), ("Clip", "f8")],
        )
        log_data = _log_data_with_vibe(records)
        model = VibeLogAnalysis(log_data, _context())

        outcomes = model.check_vibration_levels()

        assert len(outcomes) == 1
        assert "VibeZ" in outcomes[0].message
        assert "nearly always present" in outcomes[0].message

    def test_check_vibration_levels_reports_severe_exactly_at_threshold(self) -> None:
        records = np.array(
            [(0, 10.0, 10.0, 10.0, 0), (1_000_000, 10.0, 10.0, 60.0, 0)],
            dtype=[("TimeUS", "f8"), ("VibeX", "f8"), ("VibeY", "f8"), ("VibeZ", "f8"), ("Clip", "f8")],
        )
        log_data = _log_data_with_vibe(records)
        model = VibeLogAnalysis(log_data, _context())

        outcomes = model.check_vibration_levels()

        assert len(outcomes) == 1
        assert "nearly always present" in outcomes[0].message

    def test_check_vibration_levels_skips_axis_when_field_missing(self) -> None:
        records = np.array(
            [(0, 65.0, 10.0, 0), (1_000_000, 65.0, 10.0, 0)],
            dtype=[("TimeUS", "f8"), ("VibeX", "f8"), ("VibeZ", "f8"), ("Clip", "f8")],
        )
        log_data = _log_data_with_vibe(records)
        model = VibeLogAnalysis(log_data, _context())

        outcomes = model.check_vibration_levels()

        assert len(outcomes) == 1
        assert "VibeX" in outcomes[0].message

    def test_check_clipping_reports_no_finding_when_clip_stays_zero(self) -> None:
        records = np.array(
            [(0, 1.0, 2.0, 3.0, 0), (1_000_000, 1.0, 2.0, 3.0, 0)],
            dtype=[("TimeUS", "f8"), ("VibeX", "f8"), ("VibeY", "f8"), ("VibeZ", "f8"), ("Clip", "f8")],
        )
        log_data = _log_data_with_vibe(records)
        model = VibeLogAnalysis(log_data, _context())

        outcomes = model.check_clipping()

        assert not outcomes

    def test_check_clipping_reports_finding_when_clip_count_nonzero(self) -> None:
        records = np.array(
            [(0.0, 1.0, 2.0, 3.0, 0), (1.0, 1.0, 2.0, 3.0, 4)],
            dtype=[("TimeUS", "f8"), ("VibeX", "f8"), ("VibeY", "f8"), ("VibeZ", "f8"), ("Clip", "f8")],
        )
        log_data = _log_data_with_vibe(records)
        model = VibeLogAnalysis(log_data, _context())

        outcomes = model.check_clipping()

        assert len(outcomes) == 1
        assert outcomes[0].value == 4.0
        assert outcomes[0].timestamp_us == pytest.approx(1_000_000.0)

    def test_check_clipping_returns_no_finding_when_clip_field_missing(self) -> None:
        records = np.array([(0, 1.0, 2.0, 3.0)], dtype=[("TimeUS", "f8"), ("VibeX", "f8"), ("VibeY", "f8"), ("VibeZ", "f8")])
        log_data = _log_data_with_vibe(records)
        model = VibeLogAnalysis(log_data, _context())

        outcomes = model.check_clipping()

        assert not outcomes

    def test_analyse_returns_available_result_with_no_outcomes_on_clean_data(self) -> None:
        records = np.array(
            [(0, 1.0, 2.0, 3.0, 0), (1_000_000, 1.0, 2.0, 3.0, 0)],
            dtype=[("TimeUS", "f8"), ("VibeX", "f8"), ("VibeY", "f8"), ("VibeZ", "f8"), ("Clip", "f8")],
        )
        log_data = _log_data_with_vibe(records)
        model = VibeLogAnalysis(log_data, _context())

        result = model.analyse()

        assert result.available is True
        assert not result.outcomes
