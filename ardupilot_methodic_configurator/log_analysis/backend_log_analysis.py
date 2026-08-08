"""
Backend orchestration for ArduPilot log analysis.

This module coordinates side-effecting data loading and pure data-model
analysis so frontends do not need to know the parser sequence.

SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-FileCopyrightText: 2026 Omkar Sarkar <omkarsarkar24@gmail.com>

SPDX-License-Identifier: GPL-3.0-or-later
"""

from collections.abc import Callable
from typing import Any

from ardupilot_methodic_configurator.log_analysis.backend_log_extraction import extract_log
from ardupilot_methodic_configurator.log_analysis.data_model_log_analysis import (
    LogSummary,
    analyze_log,
    validate_log_matches_vehicle,
)
from ardupilot_methodic_configurator.log_analysis.data_model_log_analysis_context import LogAnalysisContext
from ardupilot_methodic_configurator.log_analysis.data_model_log_data import LogData
from ardupilot_methodic_configurator.log_analysis.utils import APMDoc


def analyze_log_data(  # pylint: disable=too-many-arguments
    log_data: LogData,
    *,
    project_vehicle_type: object,
    project_firmware_version: object,
    vehicle_components: dict[str, Any] | None,
    configuration_steps: dict[str, Any] | None,
    apm_doc: APMDoc | None,
    validate_project: bool = True,
) -> LogSummary:
    """Validate and analyze already extracted log data."""
    if validate_project:
        if log_data.vehicle_type is None or log_data.firmware_version is None:
            msg = "No firmware version information found in parsed log"
            raise ValueError(msg)
        validate_log_matches_vehicle(
            log_data.vehicle_type,
            log_data.firmware_version,
            project_vehicle_type,
            project_firmware_version,
        )

    parameters = {
        record["Name"]: float(record["Value"])
        for record in log_data.iter_message_records("PARM")
        if record.get("Name") and record.get("Value") is not None
    }
    context = LogAnalysisContext(
        parameters=parameters,
        configuration_steps=configuration_steps or {},
        vehicle_components=vehicle_components or {},
        apm_doc=apm_doc,
    )
    return analyze_log(log_data, context)


def analyze_log_file(  # noqa: PLR0913 # pylint: disable=too-many-arguments
    filepath: str,
    *,
    project_vehicle_type: object,
    project_firmware_version: object,
    vehicle_components: dict[str, Any] | None,
    configuration_steps: dict[str, Any] | None,
    apm_doc: APMDoc | None,
    log_vehicle_type: str | None = None,
    log_firmware_version: tuple[int, int, int] | None = None,
    validate_project: bool = True,
    progress_callback: Callable[[int, int], None] | None = None,
) -> LogSummary:
    """
    Load a .bin log, validate it against the active project, and return an analysis summary.

    Args:
        filepath: Path to the ArduPilot .bin log file.
        project_vehicle_type: Vehicle type from the active project.
        project_firmware_version: Firmware version from the active project.
        vehicle_components: Already loaded vehicle component data.
        configuration_steps: Already loaded Methodic Configurator steps.
        apm_doc: Already loaded parameter metadata.
        log_vehicle_type: Optional vehicle type override for callers that already know the log identity.
        log_firmware_version: Optional firmware version override for callers that already know the log identity.
        validate_project: Whether to reject logs that do not match the active project.
        progress_callback: Optional callback receiving second-pass parser progress as (current, total).

    """
    log_data = extract_log(filepath, progress_callback=progress_callback)

    if log_vehicle_type is not None and log_firmware_version is not None:
        log_data.vehicle_type = log_vehicle_type
        log_data.firmware_version = log_firmware_version

    return analyze_log_data(
        log_data,
        project_vehicle_type=project_vehicle_type,
        project_firmware_version=project_firmware_version,
        vehicle_components=vehicle_components,
        configuration_steps=configuration_steps,
        apm_doc=apm_doc,
        validate_project=validate_project,
    )
