"""
ArduPilot log analysis domain model.

Combines already loaded log data, parameters, configuration metadata, and
vehicle metadata into a single summary object for presentation.

SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-FileCopyrightText: 2026 Omkar Sarkar <omkarsarkar24@gmail.com>

SPDX-License-Identifier: GPL-3.0-or-later
"""

from dataclasses import dataclass

from ardupilot_methodic_configurator import _
from ardupilot_methodic_configurator.log_analysis.data_model_log_analysis_context import LogAnalysisContext
from ardupilot_methodic_configurator.log_analysis.data_model_log_analysis_result import LogAnalysisResult
from ardupilot_methodic_configurator.log_analysis.data_model_log_data import LogData
from ardupilot_methodic_configurator.log_analysis.data_model_log_quality import (
    LogQualityResult,
    LogQualityState,
    MessageValidation,
    PMStatus,
    QualityIssue,
    StepValidationResult,
)
from ardupilot_methodic_configurator.log_analysis.data_model_log_quality_check import (
    check_cpu_performance_message,
    get_pm_status,
    validate_configuration_steps_data,
)
from ardupilot_methodic_configurator.log_analysis.data_model_quality_arm import ArmLogQualityModel
from ardupilot_methodic_configurator.log_analysis.data_model_quality_base import BaseLogModel
from ardupilot_methodic_configurator.log_analysis.data_model_quality_battery import BatteryLogAnalysis, BatteryLogQualityModel
from ardupilot_methodic_configurator.log_analysis.data_model_quality_err import ErrLogQualityModel
from ardupilot_methodic_configurator.log_analysis.data_model_quality_esc import EscLogAnalysis, EscLogQualityModel
from ardupilot_methodic_configurator.log_analysis.data_model_quality_fft import FftLogQualityModel
from ardupilot_methodic_configurator.log_analysis.data_model_quality_gnss import GPSLogQualityModel
from ardupilot_methodic_configurator.log_analysis.data_model_quality_imu import ImuLogAnalysis, ImuLogQualityModel
from ardupilot_methodic_configurator.log_analysis.data_model_quality_mode import ModeLogQualityModel
from ardupilot_methodic_configurator.log_analysis.data_model_quality_pm import PmLogQualityModel
from ardupilot_methodic_configurator.log_analysis.data_model_quality_vibe import VibeLogAnalysis, VibeLogQualityModel
from ardupilot_methodic_configurator.log_analysis.data_model_vehicle_overview import HardwareReport
from ardupilot_methodic_configurator.log_analysis.data_model_vehicle_overview_report import extract_hardware_report

QUALITY_AND_ANALYSIS_MODELS: list[tuple[type[BaseLogModel], type[BaseLogModel] | None]] = [
    (BatteryLogQualityModel, BatteryLogAnalysis),
    (GPSLogQualityModel, None),
    (EscLogQualityModel, EscLogAnalysis),
    (ImuLogQualityModel, ImuLogAnalysis),
    (VibeLogQualityModel, VibeLogAnalysis),
    (FftLogQualityModel, None),
    (ErrLogQualityModel, None),
    (PmLogQualityModel, None),
    (ArmLogQualityModel, None),
    (ModeLogQualityModel, None),
]


def parse_firmware_version(version: object) -> tuple[int, int, int] | None:
    """Parse a firmware version string into a comparable tuple, if available."""
    if not isinstance(version, str) or not version:
        return None

    version_text = version.strip().split(" ", 1)[0].lstrip("Vv")
    parts = version_text.split(".")
    if len(parts) != 3:
        return None

    try:
        return int(parts[0]), int(parts[1]), int(parts[2])
    except ValueError:
        return None


def _pm_validation_as_quality_result(validation: MessageValidation | None) -> LogQualityResult | None:
    """Convert PM validation into the common quality-result shape used by the frontend."""
    if validation is None:
        return None

    issues = [QualityIssue(issue) for issue in validation.issues]
    return LogQualityResult(
        available=validation.valid,
        state=LogQualityState.INFO if validation.valid else LogQualityState.WARNING,
        reason=_("Performance monitor data present and good for analysis")
        if validation.valid
        else _("Performance monitor data has quality issues"),
        issues=issues,
        name=_("System Performance"),
    )


def validate_log_matches_vehicle(
    log_vehicle_type: str,
    log_firmware_version: tuple[int, int, int],
    project_vehicle_type: object,
    project_firmware_version: object,
) -> None:
    """Reject logs that clearly do not match the currently open vehicle project."""
    if isinstance(project_vehicle_type, str) and project_vehicle_type and log_vehicle_type != project_vehicle_type:
        msg = _(
            "The selected log is from {log_vehicle_type}, but the currently open vehicle is {project_vehicle_type}."
        ).format(log_vehicle_type=log_vehicle_type, project_vehicle_type=project_vehicle_type)
        raise ValueError(msg)

    parsed_project_version = parse_firmware_version(project_firmware_version)
    if parsed_project_version is not None and log_firmware_version != parsed_project_version:
        msg = _(
            "The selected log firmware version is {log_version}, but the currently open vehicle firmware version is "
            "{project_version}."
        ).format(
            log_version=".".join(str(part) for part in log_firmware_version),
            project_version=".".join(str(part) for part in parsed_project_version),
        )
        raise ValueError(msg)


@dataclass
class LogSummary:  # pylint: disable=too-many-instance-attributes
    """Summary of a parsed ArduPilot log."""

    flight_duration_sec: float | None
    file_size_bytes: int
    total_messages: int
    message_types: int
    parameter_count: int
    pm_status: PMStatus | None
    pm_validation: MessageValidation | None
    quality_results: list[LogQualityResult]
    analysis_results: list[LogAnalysisResult]
    step_results: list[StepValidationResult]
    hardware_report: HardwareReport


def analyze_log(  # pylint: disable=too-many-locals
    log_data: LogData,
    context: LogAnalysisContext,
    quality_and_analysis_models: list[tuple[type[BaseLogModel], type[BaseLogModel] | None]] | None = None,
) -> LogSummary:
    """
    Run log analysis over already loaded datasource values.

    Args:
        log_data: Parsed log.
        context: Typed analysis inputs (parameters, configuration steps,
            optional component metadata and apm.pdef definitions).
        quality_and_analysis_models: Optional (quality_model_cls, analysis_model_cls) pairs to run
            instead of the default registry. Pass None if the second element of a pair for
            subsystems with no analysis model.

    Returns:
        Complete log analysis summary.

    """
    resolved_models: list[tuple[type[BaseLogModel], type[BaseLogModel] | None]] = (
        QUALITY_AND_ANALYSIS_MODELS if quality_and_analysis_models is None else quality_and_analysis_models
    )

    parameters = context.parameters
    configuration_steps = context.configuration_steps
    apm_doc = context.apm_doc

    pm_status = get_pm_status(log_data)
    pm_validation = check_cpu_performance_message(log_data)

    quality_results: list[LogQualityResult] = []
    pm_quality_result = _pm_validation_as_quality_result(pm_validation)
    if pm_quality_result is not None:
        quality_results.append(pm_quality_result)
    analysis_results: list[LogAnalysisResult] = []
    for quality_model_cls, analysis_model_cls in resolved_models:
        quality_model = quality_model_cls(log_data, context)
        quality_result = quality_model.check()
        quality_results.append(quality_result)

        if analysis_model_cls is not None and quality_result.available:
            analysis_results.append(analysis_model_cls(log_data, context).analyse())

    step_results = validate_configuration_steps_data(log_data, configuration_steps)
    hardware_report = extract_hardware_report(log_data, parameters, apm_doc)

    return LogSummary(
        flight_duration_sec=log_data.flight_duration_sec,
        file_size_bytes=log_data.log_file_size,
        total_messages=sum(log_data.msg_count.values()),
        message_types=len(log_data.schemas),
        parameter_count=len(parameters),
        pm_status=pm_status,
        pm_validation=pm_validation,
        quality_results=quality_results,
        step_results=step_results,
        hardware_report=hardware_report,
        analysis_results=analysis_results,
    )
