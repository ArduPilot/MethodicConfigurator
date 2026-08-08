"""
ArduPilot log quality checker.

Validates that the messages and params required by the Methodic Configurator configuration
steps are present, also checks if a specific analysis can be performed and the logged records match their FMT schema.

SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-FileCopyrightText: 2026 Omkar Sarkar <omkarsarkar24@gmail.com>

SPDX-License-Identifier: GPL-3.0-or-later
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ardupilot_methodic_configurator import _
from ardupilot_methodic_configurator.log_analysis.data_model_log_quality import (
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
    import numpy as np

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
    nlon = log_data.get_field("PM", "NLon", scaled=False) if "NLon" in available else None
    max_t = log_data.get_field("PM", "MaxT", scaled=False) if "MaxT" in available else None
    mem = log_data.get_field("PM", "Mem", scaled=False) if "Mem" in available else None

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
    issues: list[str] = []

    # Internal error mask
    if "InE" in available:
        ine = log_data.get_field("PM", "InE", scaled=False)
        if ine.max() > 0:
            issues.append(_("Internal firmware errors were detected (InE)"))

    # Internal error count
    if "ErC" in available:
        erc = log_data.get_field("PM", "ErC", scaled=False)
        count = int(erc.max())
        if count > 0:
            issues.append(_("Internal error count: {count}").format(count=count))

    # Internal error line number
    if "ErrL" in available:
        errl = log_data.get_field("PM", "ErrL", scaled=False)
        if errl.max() > 0:
            issues.append(_("An internal error line was recorded (ErrL)"))

    # Long loops
    if "NLon" in available:
        nlon = log_data.get_field("PM", "NLon", scaled=False)
        count = int(nlon.sum())

        if count > 0:
            issues.append(_("Detected {count} scheduler long loops").format(count=count))

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
    if schema.units and len(schema.units) != len(schema.fields):
        issues.append(_("Unit count mismatch"))
    if schema.multipliers and len(schema.multipliers) != len(schema.fields):
        issues.append(_("Multiplier count mismatch"))

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
