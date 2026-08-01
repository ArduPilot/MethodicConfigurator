#!/usr/bin/env python3

"""
Tests for ardupilot_methodic_configurator/log_analysis/backend_log_analysis.py.

SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

from typing import Any, ClassVar

from ardupilot_methodic_configurator.log_analysis import backend_log_analysis
from ardupilot_methodic_configurator.log_analysis.backend_log_analysis import analyze_log
from ardupilot_methodic_configurator.log_analysis.backend_log_extraction import LogData
from ardupilot_methodic_configurator.log_analysis.data_model_log_analysis_context import LogAnalysisContext
from ardupilot_methodic_configurator.log_analysis.data_model_quality_base import (
    BaseLogQualityAnalysisModel,
    LogQualityResult,
)


class RecordingQualityModel(BaseLogQualityAnalysisModel):
    """Quality model test double that records constructor inputs."""

    seen_log_data: ClassVar[LogData | None] = None
    seen_context: ClassVar[LogAnalysisContext | None] = None

    def __init__(self, log_data: LogData, context: LogAnalysisContext) -> None:
        super().__init__(log_data, context)
        type(self).seen_log_data = log_data
        type(self).seen_context = context

    def check(self) -> LogQualityResult:
        return LogQualityResult(
            available=True,
            state="info",
            reason="ok",
            issues=[],
            name="Recording",
        )


class DummyQualityModel(BaseLogQualityAnalysisModel):
    """Minimal concrete model to exercise base-class context wiring."""

    def check(self) -> LogQualityResult:
        return LogQualityResult(
            available=True,
            state="info",
            reason="ok",
            issues=[],
            name="Dummy",
        )


def test_analyze_log_passes_context_to_quality_models(monkeypatch: Any) -> None:  # noqa: ANN401
    """
    Pass the same context object through to each quality model constructor.

    GIVEN analyze_log is called with an explicit context and quality-model list,
    WHEN the analysis runs,
    THEN each model should receive the original context object.
    """
    log_data = LogData(msg_count={"MSG": 3})
    context = LogAnalysisContext(
        parameters={"LOG_BITMASK": 1.0},
        configuration_steps={"steps": {}},
    )

    sentinel_hardware_report = object()
    monkeypatch.setattr(backend_log_analysis, "get_pm_status", lambda _log_data: None)
    monkeypatch.setattr(
        backend_log_analysis,
        "check_cpu_performance_message",
        lambda _log_data: backend_log_analysis.MessageValidation(valid=True, issues=[]),
    )
    monkeypatch.setattr(backend_log_analysis, "validate_configuration_steps", lambda _log_data, _steps: [])
    monkeypatch.setattr(
        backend_log_analysis,
        "extract_hardware_report",
        lambda _log_data, _params, _apm_doc: sentinel_hardware_report,
    )

    summary = analyze_log(log_data, context, quality_models=[RecordingQualityModel])

    assert RecordingQualityModel.seen_log_data is log_data
    assert RecordingQualityModel.seen_context is context
    assert summary.parameter_count == 1
    assert summary.hardware_report is sentinel_hardware_report
    assert [result.name for result in summary.quality_results] == ["Recording"]


def test_base_quality_model_reads_fields_from_context() -> None:
    """
    Populate base-model dependencies directly from context.

    GIVEN a context with parameters, config steps, apm-doc, and components,
    WHEN a concrete quality model is created,
    THEN the base model should expose those values without repacking args.
    """
    log_data = LogData()
    context = LogAnalysisContext(
        parameters={"BATT_MONITOR": 4.0},
        configuration_steps={"steps": {"06_battery": {}}},
        vehicle_components={"battery": "present"},
        apm_doc={"BATT_MONITOR": {"humanName": "Battery monitor"}},
    )

    model = DummyQualityModel(log_data, context)

    assert model.log_data is log_data
    assert model.parameters is context.parameters
    assert model.configuration_steps is context.configuration_steps
    assert model.vehicle_components is context.vehicle_components
    assert model.apm_doc is context.apm_doc
