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
from ardupilot_methodic_configurator.log_analysis.data_model_quality_base import (
    BaseLogAnalysisModel,
    BaseLogQualityModel,
)
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


@dataclass(frozen=True)
class LogAnalysisModelSpec:
    """Registration for one log subsystem and its optional detailed analysis."""

    key: str
    quality_model: type[BaseLogQualityModel]
    analysis_model: type[BaseLogAnalysisModel] | None = None


LOG_ANALYSIS_SUBSYSTEMS: tuple[LogAnalysisModelSpec, ...] = (
    LogAnalysisModelSpec("battery", BatteryLogQualityModel, BatteryLogAnalysis),
    LogAnalysisModelSpec("gps", GPSLogQualityModel),
    LogAnalysisModelSpec("esc", EscLogQualityModel, EscLogAnalysis),
    LogAnalysisModelSpec("imu", ImuLogQualityModel, ImuLogAnalysis),
    LogAnalysisModelSpec("vibe", VibeLogQualityModel, VibeLogAnalysis),
    LogAnalysisModelSpec("fft", FftLogQualityModel),
    LogAnalysisModelSpec("err", ErrLogQualityModel),
    LogAnalysisModelSpec("pm", PmLogQualityModel),
    LogAnalysisModelSpec("arm", ArmLogQualityModel),
    LogAnalysisModelSpec("mode", ModeLogQualityModel),
)


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
    related_parameter_values: dict[str, float] = field(default_factory=dict)
    analysis_subsystem_keys: tuple[str, ...] = ()

    def paired_quality_and_analysis_results(
        self,
    ) -> list[tuple[LogQualityResult, LogAnalysisResult | None]]:
        """Return analysis-enabled subsystem results matched by stable subsystem key."""
        quality_by_key = {result.subsystem_key: result for result in self.quality_results if result.subsystem_key is not None}
        analysis_by_key = {
            result.subsystem_key: result for result in self.analysis_results if result.subsystem_key is not None
        }
        registered_keys = self.analysis_subsystem_keys or tuple(
            spec.key for spec in LOG_ANALYSIS_SUBSYSTEMS if spec.analysis_model is not None
        )
        return [(quality_by_key[key], analysis_by_key.get(key)) for key in registered_keys if key in quality_by_key]


def analyze_log(  # pylint: disable=too-many-locals
    log_data: LogData,
    context: LogAnalysisContext,
    quality_and_analysis_models: list[tuple[type[BaseLogQualityModel], type[BaseLogAnalysisModel] | None]] | None = None,
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
    if quality_and_analysis_models is None:
        resolved_models = [(spec.quality_model, spec.analysis_model, spec.key) for spec in LOG_ANALYSIS_SUBSYSTEMS]
    else:
        resolved_models = [
            (quality_model, analysis_model, f"custom_{index}")
            for index, (quality_model, analysis_model) in enumerate(quality_and_analysis_models)
        ]

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
    analysis_subsystem_keys: list[str] = []

    related_parameter_values: dict[str, float] = {}
    for result in quality_results:
        for issue in result.issues:
            if issue.param_name is not None and issue.param_name in parameters:
                related_parameter_values[issue.param_name] = parameters[issue.param_name]

    for quality_model_cls, analysis_model_cls, subsystem_key in resolved_models:
        quality_model = quality_model_cls(log_data, context)
        quality_result = quality_model.check()
        quality_result.subsystem_key = subsystem_key
        quality_results.append(quality_result)
        for issue in quality_result.issues:
            if issue.param_name is not None and issue.param_name in parameters:
                related_parameter_values[issue.param_name] = parameters[issue.param_name]

        if analysis_model_cls is not None:
            analysis_subsystem_keys.append(subsystem_key)
        if analysis_model_cls is not None and quality_result.available:
            analysis_result = analysis_model_cls(log_data, context).analyse()
            analysis_result.subsystem_key = subsystem_key
            analysis_results.append(analysis_result)
            for outcome in analysis_result.outcomes:
                if outcome.param_name is not None and outcome.param_name in parameters:
                    related_parameter_values[outcome.param_name] = parameters[outcome.param_name]

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
        related_parameter_values=related_parameter_values,
        analysis_subsystem_keys=tuple(analysis_subsystem_keys),
    )
