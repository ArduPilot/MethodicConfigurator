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
        logging_error("Configuration file '%s' not found", config_file)
    except JSONDecodeError as e:
        logging_error("Error in configuration file '%s': %s", config_file, e)

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


def validate_fmt_schema(schema: MessageSchema, records: list[dict]) -> MessageValidation:
    """
    Validate one message schema.

    Args:
        schema: Schema extracted from the FMT messages.
        records: Decoded records for this message type.

    Returns:
        MessageValidation

    """
    issues: list[str] = []

    # To be removed if these checks become stale, as pymavlink should handle these
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

    if not records:
        issues.append(_("{message} has no logging data").format(message=schema.name))
    else:
        expected_fields = set(schema.fields)
        for index, record in enumerate(records):
            actual_fields = {col for col in record if col != "mavpackettype"}
            missing = expected_fields - actual_fields
            extra = actual_fields - expected_fields
            if missing or extra:
                issues.append(
                    _("Field mismatch in record {index}. Missing: {missing}, extra: {extra}").format(
                        index=index,
                        missing=sorted(missing),
                        extra=sorted(extra),
                    )
                )
                break

    return MessageValidation(
        valid=not issues,
        issues=issues,
    )


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

            records = log_data.raw_messages.get(message_name, [])

            validation = validate_fmt_schema(
                schema=schema,
                records=records,
            )

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
