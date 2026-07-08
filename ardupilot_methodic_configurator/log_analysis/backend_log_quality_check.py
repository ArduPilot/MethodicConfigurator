"""
ArduPilot log quality checker.

Validates that the messages and params required by the Methodic Configurator configuration
steps are present, also checks if a specific analysis can be performed and the logged records match their FMT schema.

SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

from dataclasses import dataclass, field
from json import JSONDecodeError
from json import load as json_load
from logging import error as logging_error
from pathlib import Path
from typing import Any

import numpy as np

from ardupilot_methodic_configurator import _
from ardupilot_methodic_configurator.log_analysis.backend_log_extraction import LogData, MessageSchema


def load_configuration_steps(vehicle_type: str = "ArduCopter") -> dict[str, Any] | None:
    """
    Load the Methodic Configurator configuration steps for the given vehicle type.

    Returns None on any I/O or JSON error so callers can distinguish file errors
    from a legitimately empty configuration.
    """
    config_file = Path(__file__).parent.parent / f"configuration_steps_{vehicle_type}.json"

    try:
        with open(config_file, encoding="utf-8") as file:
            data: dict[str, Any] = json_load(file)
            return data
    except FileNotFoundError:
        logging_error(_("Configuration file '{config_file}' not found").format(config_file=config_file))
    except JSONDecodeError as e:
        logging_error(_("Error in configuration file '{config_file}': {error}").format(config_file=config_file, error=e))

    return None


@dataclass
class MessageValidation:
    """Validation result for a single message type and its schema."""

    valid: bool
    issues: list[str] = field(default_factory=list)


@dataclass
class StepValidationResult:
    """Validation result for configuration step."""

    step: str
    name: str
    valid: bool
    message_results: dict[str, MessageValidation]


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


def validate_configuration_steps(  # pylint: disable=too-many-locals
    log_data: LogData,
    configuration_steps: dict[str, Any] | None = None,
    vehicle_type: str = "ArduCopter",
) -> list[StepValidationResult]:
    """
    Validate the messages required by the configuration steps.

    Args:
        log_data: Parsed log.
        configuration_steps: Pre-loaded configuration steps dict. If None, loaded
            from the filesystem for the given vehicle_type.
        vehicle_type: Vehicle type used to resolve the configuration file when
            configuration_steps is None. Defaults to "ArduCopter".

    Returns:
        List of validation results. Returns an empty list if configuration_steps
        is None and the configuration file cannot be loaded.

    """
    if configuration_steps is None:
        configuration_steps = load_configuration_steps(vehicle_type)
        if configuration_steps is None:
            return []
    results: list[StepValidationResult] = []

    steps = configuration_steps.get("steps")
    if not isinstance(steps, dict):
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
