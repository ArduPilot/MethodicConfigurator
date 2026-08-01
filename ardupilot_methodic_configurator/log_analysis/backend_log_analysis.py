"""
ArduPilot log analysis manager.

Coordinates log metadata extraction, quality validation, and subsystem quality
analysis into a single summary object for the Methodic Configurator frontend.

SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

from dataclasses import dataclass

from ardupilot_methodic_configurator.log_analysis.backend_log_extraction import LogData
from ardupilot_methodic_configurator.log_analysis.backend_log_quality_check import (
    MessageValidation,
    PMStatus,
    StepValidationResult,
    check_cpu_performance_message,
    get_pm_status,
    validate_configuration_steps,
)
from ardupilot_methodic_configurator.log_analysis.backend_vehicle_overview import HardwareReport, extract_hardware_report
from ardupilot_methodic_configurator.log_analysis.data_model_log_analysis_context import LogAnalysisContext
from ardupilot_methodic_configurator.log_analysis.data_model_quality_base import BaseLogQualityAnalysisModel, LogQualityResult
from ardupilot_methodic_configurator.log_analysis.data_model_quality_battery import BatteryLogQualityModel
from ardupilot_methodic_configurator.log_analysis.data_model_quality_esc import EscLogQualityModel
from ardupilot_methodic_configurator.log_analysis.data_model_quality_gnss import GPSLogQualityModel

QUALITY_MODELS = [BatteryLogQualityModel, GPSLogQualityModel, EscLogQualityModel]


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
    Run all log quality analyses and return a summary suitable for the frontend.

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

    quality_results: list[LogQualityResult] = [model(log_data, context).check() for model in resolved_quality_models]

    step_results = validate_configuration_steps(log_data, configuration_steps)
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
