"""
ArduPilot log availability checker.

Validates that the messages and params required by the Methodic Configurator configuration
steps are present, also checks if a specific analysis can be performed and the logged records match their FMT schema.

SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-FileCopyrightText: 2026 Omkar Sarkar <omkarsarkar24@gmail.com>

SPDX-License-Identifier: GPL-3.0-or-later
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import numpy as np

from ardupilot_methodic_configurator import _
from ardupilot_methodic_configurator.log_analysis.data_model_log_availability import (
    MessageValidation,
    PMStatus,
    StepValidationResult,
)
from ardupilot_methodic_configurator.log_analysis.utils import (
    find_log_bit_in_apm_file as _find_log_bit_in_apm_file,
)
from ardupilot_methodic_configurator.log_analysis.utils import (
    get_configuration_steps_map,
)
from ardupilot_methodic_configurator.log_analysis.utils import (
    get_log_bitmask as _get_log_bitmask,
)

if TYPE_CHECKING:
    from ardupilot_methodic_configurator.log_analysis.data_model_log_data import LogData, MessageSchema

_MAX_HEALTHY_AVG_CPU = 80.0  # percent
_MAX_HEALTHY_PEAK_CPU = 95.0  # percent
_MIN_HEALTHY_FREE_MEM = 10_000  # bytes


def find_log_bit_in_apm_file(bitmask: str, bit_name: str) -> int | None:
    """Compatibility wrapper for LOG_BITMASK category lookup."""
    return _find_log_bit_in_apm_file(bitmask, bit_name)


def get_log_bitmask(doc: dict[str, Any]) -> str | None:
    """Compatibility wrapper for LOG_BITMASK metadata lookup."""
    return _get_log_bitmask(doc)


def validate_configuration_steps_data(log_data: LogData, configuration_steps: dict[str, Any]) -> list[StepValidationResult]:
    """
    Validate the messages required by already loaded configuration steps.

    This is the pure, side-effect free entrypoint intended for deterministic unit tests.
    """
    results: list[StepValidationResult] = []

    steps = get_configuration_steps_map(configuration_steps)
    if not steps:
        return results

    for step_name, step in steps.items():
        related_messages = step.get("related_bin_messages")
        if not related_messages:
            continue

        step_valid = True
        message_results: dict[str, MessageValidation] = {}

        for message_name, message_info in related_messages.items():
            required = message_info.get("required", False)

            schema = log_data.schemas.get(message_name)

            if schema is None:
                validation = MessageValidation(
                    valid=not required,
                    issues=[] if not required else [_("Schema not found")],
                )

                if required:
                    step_valid = False

                message_results[message_name] = validation
                continue

            columns = log_data.get_message_columns(message_name)
            validation = validate_fmt_schema(schema=schema, columns=columns)

            if required and not validation.valid:
                step_valid = False

            message_results[message_name] = validation

        results.append(
            StepValidationResult(
                step=step_name,
                name=step.get("why", step_name),
                valid=step_valid,
                message_results=message_results,
            )
        )

    return results


def get_pm_status(log_data: LogData) -> PMStatus | None:
    """
    Return a summary of the Performance Monitor (PM) message.

    Returns:
        PMStatus if the PM message exists, otherwise None.

    """
    columns = log_data.get_message_columns("PM")
    if columns is None or columns.size == 0:
        return None

    available = set(columns.dtype.names or ())

    load = log_data.get_field("PM", "Load") if "Load" in available else None
    nlon = log_data.get_field("PM", "NLon") if "NLon" in available else None
    max_t = log_data.get_field("PM", "MaxT") if "MaxT" in available else None
    mem = log_data.get_field("PM", "Mem") if "Mem" in available else None

    if any(values is not None and not np.isfinite(values).all() for values in (load, nlon, max_t, mem)):
        return PMStatus(0.0, 0.0, 0, 0, 0, None)

    # compute values into locals first
    avg_cpu_load = float(load.mean()) if load is not None else 0.0
    peak_cpu_load = float(load.max()) if load is not None else 0.0
    long_loops = int(nlon.sum()) if nlon is not None else 0
    max_loop_time = int(max_t.max()) if max_t is not None else 0
    free_memory = int(mem.min()) if mem is not None else 0

    if load is not None and mem is not None:
        healthy = (
            avg_cpu_load < _MAX_HEALTHY_AVG_CPU
            and peak_cpu_load < _MAX_HEALTHY_PEAK_CPU
            and free_memory > _MIN_HEALTHY_FREE_MEM
        )
    else:
        healthy = None

    return PMStatus(
        average_cpu_load=avg_cpu_load,
        peak_cpu_load=peak_cpu_load,
        scheduler_long_loops=long_loops,
        max_loop_time_us=max_loop_time,
        free_memory_bytes=free_memory,
        healthy=healthy,
    )


def _pm_non_finite_issues(log_data: LogData, available: set[str]) -> list[str]:
    """Return one issue for each PM field that contains non-finite samples."""
    return [
        _("{field} contains non-finite telemetry values").format(field=field_name)
        for field_name in ("Load", "NLon", "MaxT", "Mem", "InE", "ErC", "ErrL")
        if field_name in available and not np.isfinite(log_data.get_field("PM", field_name)).all()
    ]


def _pm_error_signal_issues(log_data: LogData, available: set[str]) -> list[str]:
    """Return issues reported by finite PM error counters and masks."""
    issues: list[str] = []
    for field_name, reducer, message in (
        ("InE", np.max, _("Internal firmware errors were detected (InE)")),
        ("ErC", np.max, _("Internal error count: {count}")),
        ("ErrL", np.max, _("An internal error line was recorded (ErrL)")),
        ("NLon", np.sum, _("Detected {count} scheduler long loops")),
    ):
        if field_name in available:
            values = log_data.get_field("PM", field_name)
            if np.isfinite(values).all():
                count = int(reducer(values))
                if count > 0:
                    issues.append(message.format(count=count) if field_name in {"ErC", "NLon"} else message)
    return issues


def check_cpu_performance_message(log_data: LogData) -> MessageValidation:
    """
    Validate the PM (Performance Monitor) message for internal errors and health.

    Only checks documented error signals (internal error mask, error count,
    long loops). Fields vary by firmware version.
    """
    columns = log_data.get_message_columns("PM")
    if columns is None or columns.size == 0:
        return MessageValidation(valid=False, issues=[_("PM message not logged")])

    available = set(columns.dtype.names or ())
    issues = _pm_non_finite_issues(log_data, available)
    issues.extend(_pm_error_signal_issues(log_data, available))

    return MessageValidation(valid=not issues, issues=issues)


def validate_fmt_schema(schema: MessageSchema, columns: np.ndarray | None) -> MessageValidation:
    """
    Validate one message schema.

    Args:
        schema: Schema extracted from the FMT messages.
        columns: Structured numpy array for this message type.

    Returns:
        MessageValidation

    """
    issues: list[str] = []

    if not schema.fields:
        issues.append(_("Missing field definitions"))
    if not schema.format:
        issues.append(_("Missing format string"))
    if schema.length <= 0:
        issues.append(_("Invalid message length"))
    if len(schema.stored_units) != len(schema.fields):
        issues.append(_("Stored unit count mismatch"))
    if len(schema.scaled_units) != len(schema.fields):
        issues.append(_("Scaled unit count mismatch"))
    if schema.multipliers and len(schema.multipliers) != len(schema.fields):
        issues.append(_("Multiplier count mismatch"))
    if len(schema.multipliers_applied_at_ingest) != len(schema.fields):
        issues.append(_("Multiplier ingestion state count mismatch"))

    if columns is None or columns.size == 0:
        issues.append(_("{message} has no logging data").format(message=schema.name))
    else:
        expected_fields = set(schema.fields)
        actual_fields = set(columns.dtype.names or ())
        missing = expected_fields - actual_fields
        extra = actual_fields - expected_fields
        if missing or extra:
            issues.append(
                _("Field mismatch. Missing: {missing}, extra: {extra}").format(
                    missing=sorted(missing),
                    extra=sorted(extra),
                )
            )

    return MessageValidation(valid=not issues, issues=issues)
