#!/usr/bin/env python3

"""
Tests for ardupilot_methodic_configurator/log_analysis/data_model_log_analysis.py.

SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

from typing import Any, ClassVar

import pytest

from ardupilot_methodic_configurator.log_analysis import data_model_log_analysis
from ardupilot_methodic_configurator.log_analysis.data_model_log_analysis import (
    analyze_log,
    parse_firmware_version,
    validate_log_matches_vehicle,
)
from ardupilot_methodic_configurator.log_analysis.data_model_log_analysis_context import LogAnalysisContext
from ardupilot_methodic_configurator.log_analysis.data_model_log_data import LogData
from ardupilot_methodic_configurator.log_analysis.data_model_log_quality import LogQualityResult, LogQualityState
from ardupilot_methodic_configurator.log_analysis.data_model_quality_base import (
    BaseLogAnalysisModel,
    BaseLogQualityModel,
)


class RecordingQualityModel(BaseLogQualityModel):
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
            state=LogQualityState.INFO,
            reason="ok",
            issues=[],
            name="Recording",
        )


class DummyQualityModel(BaseLogQualityModel):
    """Minimal concrete model to exercise base-class context wiring."""

    def check(self) -> LogQualityResult:
        return LogQualityResult(
            available=True,
            state=LogQualityState.INFO,
            reason="ok",
            issues=[],
            name="Dummy",
        )


class DummyAnalysisModel(BaseLogAnalysisModel):
    """Minimal detailed model used to exercise parameter-derivation wiring."""


class RecordingParameterDeriver:
    """Test double proving detailed models use the context-provided service."""

    def __init__(self) -> None:
        self.expected_call: tuple[str, str] | None = None
        self.matching_pattern: str | None = None

    def expected_parameter_value(self, step_filename: str, param_name: str, **_kwargs: object) -> tuple[float, str]:
        self.expected_call = (step_filename, param_name)
        return 42.0, "derived"

    def derived_and_forced_parameters_matching(self, pattern: str, **_kwargs: object) -> dict[str, str]:
        self.matching_pattern = pattern
        return {"TEST_PARAM": "01_test.param"}


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
        configuration_steps={},
    )

    sentinel_hardware_report = object()
    monkeypatch.setattr(data_model_log_analysis, "get_pm_status", lambda _log_data: None)
    monkeypatch.setattr(
        data_model_log_analysis,
        "check_cpu_performance_message",
        lambda _log_data: data_model_log_analysis.MessageValidation(valid=True, issues=[]),
    )
    seen_steps: list[dict[str, Any]] = []

    def record_configuration_steps(_log_data: LogData, steps: dict[str, Any]) -> list[Any]:
        seen_steps.append(steps)
        return []

    monkeypatch.setattr(data_model_log_analysis, "validate_configuration_steps_data", record_configuration_steps)
    monkeypatch.setattr(
        data_model_log_analysis,
        "extract_hardware_report",
        lambda _log_data, _params, _apm_doc: sentinel_hardware_report,
    )

    summary = analyze_log(log_data, context, quality_and_analysis_models=[(RecordingQualityModel, None)])

    assert RecordingQualityModel.seen_log_data is log_data
    assert RecordingQualityModel.seen_context is context
    assert summary.parameter_count == 1
    assert summary.hardware_report is sentinel_hardware_report
    assert [result.name for result in summary.quality_results] == ["System Performance", "Recording"]
    assert seen_steps == [context.configuration_steps]


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
        configuration_steps={"06_battery": {}},
        vehicle_components={"battery": "present"},
        apm_doc={"BATT_MONITOR": {"humanName": "Battery monitor"}},
    )

    model = DummyQualityModel(log_data, context)

    assert model.log_data is log_data
    assert model.parameters is context.parameters
    assert model.configuration_steps is context.configuration_steps
    assert model.vehicle_components is context.vehicle_components
    assert model.apm_doc is context.apm_doc


def test_base_analysis_model_delegates_parameter_derivation_to_context_service() -> None:
    """Detailed models can be tested with an injected parameter-derivation service."""
    deriver = RecordingParameterDeriver()
    context = LogAnalysisContext(
        parameters={"TEST_PARAM": 1.0},
        configuration_steps={"01_test.param": {}},
        parameter_deriver=deriver,
    )
    model = DummyAnalysisModel(LogData(), context)

    assert model.expected_parameter_value("01_test.param", "TEST_PARAM") == (42.0, "derived")
    assert model.derived_and_forced_parameters_matching(r"TEST_.*") == {"TEST_PARAM": "01_test.param"}
    assert deriver.expected_call == ("01_test.param", "TEST_PARAM")
    assert deriver.matching_pattern == r"TEST_.*"


def test_subsystem_component_metadata_is_declared_by_the_registry() -> None:
    """Component guidance belongs to subsystem registration, not translated UI names."""
    component_keys = {spec.key: spec.component_keys for spec in data_model_log_analysis.LOG_ANALYSIS_SUBSYSTEMS}

    assert component_keys["battery"] == ("Battery", "Battery Monitor")
    assert component_keys["gps"] == ("GNSS Receiver",)
    assert component_keys["esc"] == ("ESC", "Motors")


def test_base_quality_model_tolerates_ambiguous_configuration_metadata() -> None:
    """
    Keep report generation alive when configuration metadata has duplicate references.

    GIVEN duplicated message and parameter references in configuration steps,
    WHEN quality helpers resolve frontend guidance,
    THEN they should fall back instead of raising from the model layer.
    """
    context = LogAnalysisContext(
        parameters={},
        configuration_steps={
            "01_first.param": {
                "related_bin_messages": {"BAT": {"name": "Battery"}},
                "derived_parameters": {"BATT_MONITOR": 4.0},
            },
            "02_second.param": {
                "related_bin_messages": {"BAT": {"name": "Battery again"}},
                "forced_parameters": {"BATT_MONITOR": 4.0},
            },
        },
    )
    model = DummyQualityModel(LogData(), context)

    assert model.resolve_message_step("BAT", "Battery") == ("", "Battery")
    assert model.step_for_parameter("BATT_MONITOR") == ""


def test_parse_firmware_version_accepts_project_version_strings() -> None:
    """Project firmware versions may include a leading V or extra text."""
    assert parse_firmware_version("4.5.5") == (4, 5, 5)
    assert parse_firmware_version("V4.6.0 stable") == (4, 6, 0)


def test_parse_firmware_version_ignores_unavailable_values() -> None:
    """Unavailable or invalid project versions should not force a mismatch."""
    assert parse_firmware_version("") is None
    assert parse_firmware_version(None) is None
    assert parse_firmware_version("4.5") is None
    assert parse_firmware_version("not-a-version") is None


def test_validate_log_matches_vehicle_rejects_different_vehicle_type() -> None:
    """Log analysis should reject logs from a different vehicle type."""
    with pytest.raises(ValueError, match="selected log is from ArduPlane") as error:
        validate_log_matches_vehicle("ArduPlane", (4, 5, 5), "ArduCopter", "4.5.5")

    assert "selected log is from ArduPlane" in str(error.value)
    assert "currently open vehicle is ArduCopter" in str(error.value)


def test_validate_log_matches_vehicle_rejects_different_firmware_version() -> None:
    """Log analysis should reject logs from a different firmware version."""
    with pytest.raises(ValueError, match=r"selected log firmware version is 4\.5\.5") as error:
        validate_log_matches_vehicle("ArduPlane", (4, 5, 5), "ArduPlane", "4.6.0")

    assert "selected log firmware version is 4.5.5" in str(error.value)
    assert "currently open vehicle firmware version is 4.6.0" in str(error.value)


def test_validate_log_matches_vehicle_accepts_matching_or_unknown_project_metadata() -> None:
    """Only clearly mismatched project metadata should reject a log."""
    validate_log_matches_vehicle("ArduPlane", (4, 5, 5), "ArduPlane", "4.5.5")
    validate_log_matches_vehicle("ArduPlane", (4, 5, 5), "", "")
