"""
ArduPilot log analysis domain model.

Combines already loaded log data, parameters, configuration metadata, and
vehicle metadata into a single summary object for presentation.

SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-FileCopyrightText: 2026 Omkar Sarkar <omkarsarkar24@gmail.com>

SPDX-License-Identifier: GPL-3.0-or-later
"""

from dataclasses import dataclass, field

from ardupilot_methodic_configurator import _
from ardupilot_methodic_configurator.log_analysis.data_model_availability_arm import ArmLogAvailabilityModel
from ardupilot_methodic_configurator.log_analysis.data_model_availability_base import (
    BaseLogAnalysisModel,
    BaseLogAvailabilityModel,
)
from ardupilot_methodic_configurator.log_analysis.data_model_availability_battery import (
    BatteryLogAnalysis,
    BatteryLogAvailabilityModel,
)
from ardupilot_methodic_configurator.log_analysis.data_model_availability_err import ErrLogAvailabilityModel
from ardupilot_methodic_configurator.log_analysis.data_model_availability_esc import EscLogAnalysis, EscLogAvailabilityModel
from ardupilot_methodic_configurator.log_analysis.data_model_availability_fft import FftLogAvailabilityModel
from ardupilot_methodic_configurator.log_analysis.data_model_availability_gnss import GPSLogAvailabilityModel
from ardupilot_methodic_configurator.log_analysis.data_model_availability_imu import ImuLogAnalysis, ImuLogAvailabilityModel
from ardupilot_methodic_configurator.log_analysis.data_model_availability_mode import ModeLogAvailabilityModel
from ardupilot_methodic_configurator.log_analysis.data_model_availability_pm import PmLogAvailabilityModel
from ardupilot_methodic_configurator.log_analysis.data_model_availability_vibe import VibeLogAnalysis, VibeLogAvailabilityModel
from ardupilot_methodic_configurator.log_analysis.data_model_log_analysis_context import LogAnalysisContext
from ardupilot_methodic_configurator.log_analysis.data_model_log_analysis_result import LogAnalysis, LogAnalysisResult
from ardupilot_methodic_configurator.log_analysis.data_model_log_availability import (
    AvailabilityIssue,
    LogAvailabilityResult,
    LogAvailabilityState,
    MessageValidation,
    PMStatus,
    StepValidationResult,
)
from ardupilot_methodic_configurator.log_analysis.data_model_log_availability_check import (
    check_cpu_performance_message,
    get_pm_status,
    validate_configuration_steps_data,
)
from ardupilot_methodic_configurator.log_analysis.data_model_log_data import LogData
from ardupilot_methodic_configurator.log_analysis.data_model_vehicle_overview import HardwareReport
from ardupilot_methodic_configurator.log_analysis.data_model_vehicle_overview_report import extract_hardware_report


@dataclass(frozen=True)
class LogAnalysisModelSpec:
    """Registration for one log subsystem and its optional detailed analysis."""

    key: str
    availability_model: type[BaseLogAvailabilityModel]
    analysis_model: type[BaseLogAnalysisModel] | None = None
    component_keys: tuple[str, ...] = ()


LOG_ANALYSIS_SUBSYSTEMS: tuple[LogAnalysisModelSpec, ...] = (
    LogAnalysisModelSpec("battery", BatteryLogAvailabilityModel, BatteryLogAnalysis, ("Battery", "Battery Monitor")),
    LogAnalysisModelSpec("gps", GPSLogAvailabilityModel, component_keys=("GNSS Receiver",)),
    LogAnalysisModelSpec("esc", EscLogAvailabilityModel, EscLogAnalysis, ("ESC", "Motors")),
    LogAnalysisModelSpec("imu", ImuLogAvailabilityModel, ImuLogAnalysis, ("Flight Controller",)),
    LogAnalysisModelSpec("vibe", VibeLogAvailabilityModel, VibeLogAnalysis, ("Flight Controller",)),
    LogAnalysisModelSpec("fft", FftLogAvailabilityModel),
    LogAnalysisModelSpec("err", ErrLogAvailabilityModel),
    LogAnalysisModelSpec("pm", PmLogAvailabilityModel),
    LogAnalysisModelSpec("arm", ArmLogAvailabilityModel),
    LogAnalysisModelSpec("mode", ModeLogAvailabilityModel),
)

ResolvedModel = tuple[type[BaseLogAvailabilityModel], type[BaseLogAnalysisModel] | None, str]


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


def _pm_validation_as_availability_result(validation: MessageValidation | None) -> LogAvailabilityResult | None:
    """Convert PM validation into the common availability-result shape used by the frontend."""
    if validation is None:
        return None

    issues = [AvailabilityIssue(issue) for issue in validation.issues]
    return LogAvailabilityResult(
        available=validation.valid,
        state=LogAvailabilityState.INFO if validation.valid else LogAvailabilityState.WARNING,
        reason=_("Performance monitor data present and good for analysis")
        if validation.valid
        else _("Performance monitor data has availability issues"),
        issues=issues,
        name=_("System Performance"),
    )


def _resolve_models(
    availability_and_analysis_models: list[tuple[type[BaseLogAvailabilityModel], type[BaseLogAnalysisModel] | None]] | None,
) -> tuple[list[ResolvedModel], dict[str, tuple[str, ...]]]:
    """Resolve the default registry or caller-provided model pairs."""
    if availability_and_analysis_models is None:
        return (
            [(spec.availability_model, spec.analysis_model, spec.key) for spec in LOG_ANALYSIS_SUBSYSTEMS],
            {spec.key: spec.component_keys for spec in LOG_ANALYSIS_SUBSYSTEMS},
        )
    return (
        [
            (availability_model, analysis_model, f"custom_{index}")
            for index, (availability_model, analysis_model) in enumerate(availability_and_analysis_models)
        ],
        {},
    )


def _add_related_parameter_values(
    related_values: dict[str, float],
    findings: list[AvailabilityIssue] | list[LogAnalysis],
    parameters: dict[str, float],
) -> None:
    """Add parameters referenced by availability issues or analysis outcomes."""
    for finding in findings:
        if finding.param_name is not None and finding.param_name in parameters:
            related_values[finding.param_name] = parameters[finding.param_name]


def _run_subsystem_models(
    resolved_models: list[ResolvedModel],
    log_data: LogData,
    context: LogAnalysisContext,
    related_parameter_values: dict[str, float],
) -> tuple[list[LogAvailabilityResult], list[LogAnalysisResult], list[str]]:
    """Run registered availability and available detailed-analysis models."""
    availability_results: list[LogAvailabilityResult] = []
    analysis_results: list[LogAnalysisResult] = []
    analysis_subsystem_keys: list[str] = []
    for availability_model_cls, analysis_model_cls, subsystem_key in resolved_models:
        availability_result = availability_model_cls(log_data, context).check()
        availability_result.subsystem_key = subsystem_key
        availability_results.append(availability_result)
        _add_related_parameter_values(related_parameter_values, availability_result.issues, context.parameters)
        if analysis_model_cls is not None:
            analysis_subsystem_keys.append(subsystem_key)
        if analysis_model_cls is not None and availability_result.available:
            analysis_result = analysis_model_cls(log_data, context).analyse()
            analysis_result.subsystem_key = subsystem_key
            analysis_results.append(analysis_result)
            _add_related_parameter_values(related_parameter_values, analysis_result.outcomes, context.parameters)
    return availability_results, analysis_results, analysis_subsystem_keys


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
    availability_results: list[LogAvailabilityResult]
    analysis_results: list[LogAnalysisResult]
    step_results: list[StepValidationResult]
    hardware_report: HardwareReport
    related_parameter_values: dict[str, float] = field(default_factory=dict)
    analysis_subsystem_keys: tuple[str, ...] = ()
    subsystem_component_keys: dict[str, tuple[str, ...]] = field(default_factory=dict)

    def component_keys_for_subsystem(self, subsystem_key: str | None) -> tuple[str, ...]:
        """Return vehicle-component keys declared by one registered subsystem."""
        if subsystem_key is None:
            return ()
        if subsystem_key in self.subsystem_component_keys:
            return self.subsystem_component_keys[subsystem_key]
        return next((spec.component_keys for spec in LOG_ANALYSIS_SUBSYSTEMS if spec.key == subsystem_key), ())

    def paired_availability_and_analysis_results(
        self,
    ) -> list[tuple[LogAvailabilityResult, LogAnalysisResult | None]]:
        """Return analysis-enabled subsystem results matched by stable subsystem key."""
        availability_by_key = {
            result.subsystem_key: result for result in self.availability_results if result.subsystem_key is not None
        }
        analysis_by_key = {
            result.subsystem_key: result for result in self.analysis_results if result.subsystem_key is not None
        }
        registered_keys = self.analysis_subsystem_keys or tuple(
            spec.key for spec in LOG_ANALYSIS_SUBSYSTEMS if spec.analysis_model is not None
        )
        return [(availability_by_key[key], analysis_by_key.get(key)) for key in registered_keys if key in availability_by_key]


def analyze_log(  # pylint: disable=too-many-locals
    log_data: LogData,
    context: LogAnalysisContext,
    availability_and_analysis_models: list[tuple[type[BaseLogAvailabilityModel], type[BaseLogAnalysisModel] | None]]
    | None = None,
) -> LogSummary:
    """
    Run log analysis over already loaded datasource values.

    Args:
        log_data: Parsed log.
        context: Typed analysis inputs (parameters, configuration steps,
            optional component metadata and apm.pdef definitions).
        availability_and_analysis_models: Optional (availability_model_cls, analysis_model_cls) pairs to run
            instead of the default registry. Pass None if the second element of a pair for
            subsystems with no analysis model.

    Returns:
        Complete log analysis summary.

    """
    parameters = context.parameters
    pm_status = get_pm_status(log_data)
    pm_validation = check_cpu_performance_message(log_data)
    resolved_models, subsystem_component_keys = _resolve_models(availability_and_analysis_models)

    availability_results: list[LogAvailabilityResult] = []
    pm_availability_result = _pm_validation_as_availability_result(pm_validation)
    if pm_availability_result is not None:
        availability_results.append(pm_availability_result)

    related_parameter_values: dict[str, float] = {}
    for result in availability_results:
        _add_related_parameter_values(related_parameter_values, result.issues, parameters)
    subsystem_availability_results, analysis_results, analysis_subsystem_keys = _run_subsystem_models(
        resolved_models, log_data, context, related_parameter_values
    )
    availability_results.extend(subsystem_availability_results)

    step_results = validate_configuration_steps_data(log_data, context.configuration_steps)
    hardware_report = extract_hardware_report(log_data, parameters, context.apm_doc)

    return LogSummary(
        flight_duration_sec=log_data.flight_duration_sec,
        file_size_bytes=log_data.log_file_size,
        total_messages=sum(log_data.msg_count.values()),
        message_types=len(log_data.schemas),
        parameter_count=len(parameters),
        pm_status=pm_status,
        pm_validation=pm_validation,
        availability_results=availability_results,
        step_results=step_results,
        hardware_report=hardware_report,
        analysis_results=analysis_results,
        related_parameter_values=related_parameter_values,
        analysis_subsystem_keys=tuple(analysis_subsystem_keys),
        subsystem_component_keys=subsystem_component_keys,
    )
