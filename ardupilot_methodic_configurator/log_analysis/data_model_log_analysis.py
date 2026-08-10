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
from ardupilot_methodic_configurator.log_analysis.data_model_quality_base import BaseLogQualityAnalysisModel
from ardupilot_methodic_configurator.log_analysis.data_model_quality_battery import BatteryLogQualityModel
from ardupilot_methodic_configurator.log_analysis.data_model_quality_err import ErrLogQualityModel
from ardupilot_methodic_configurator.log_analysis.data_model_quality_esc import EscLogQualityModel
from ardupilot_methodic_configurator.log_analysis.data_model_quality_fft import FftLogQualityModel
from ardupilot_methodic_configurator.log_analysis.data_model_quality_gnss import GPSLogQualityModel
from ardupilot_methodic_configurator.log_analysis.data_model_quality_imu import ImuLogQualityModel
from ardupilot_methodic_configurator.log_analysis.data_model_quality_mode import ModeLogQualityModel
from ardupilot_methodic_configurator.log_analysis.data_model_quality_pm import PmLogQualityModel
from ardupilot_methodic_configurator.log_analysis.data_model_quality_vibe import VibeLogQualityModel
from ardupilot_methodic_configurator.log_analysis.data_model_vehicle_overview import HardwareReport
from ardupilot_methodic_configurator.log_analysis.data_model_vehicle_overview_report import extract_hardware_report

QUALITY_MODELS = [
    BatteryLogQualityModel,
    GPSLogQualityModel,
    EscLogQualityModel,
    ImuLogQualityModel,
    VibeLogQualityModel,
    FftLogQualityModel,
    ErrLogQualityModel,
    PmLogQualityModel,
    ArmLogQualityModel,
    ModeLogQualityModel,
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
    step_results: list[StepValidationResult]
    hardware_report: HardwareReport


def analyze_log(
    log_data: LogData,
    context: LogAnalysisContext,
    quality_models: list[type[BaseLogQualityAnalysisModel]] | None = None,
) -> LogSummary:
    """
    Run log analysis over already loaded datasource values.

    Args:
        log_data: Parsed log.
        context: Typed analysis inputs (parameters, configuration steps,
            optional component metadata and apm.pdef definitions).
        quality_models: Optional model classes to run instead of the default registry.

    Returns:
        Complete log analysis summary.

    """
    resolved_quality_models: list[type[BaseLogQualityAnalysisModel]] = (
        QUALITY_MODELS if quality_models is None else quality_models
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
    quality_results.extend(model(log_data, context).check() for model in resolved_quality_models)

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
    )
