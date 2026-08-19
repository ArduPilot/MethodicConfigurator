"""
Shared log-analysis utility types and helpers.

SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-FileCopyrightText: 2026 Omkar Sarkar <omkarsarkar24@gmail.com>

SPDX-License-Identifier: GPL-3.0-or-later
"""

from typing import Any, TypeAlias

APMDoc: TypeAlias = dict[str, Any]


def get_configuration_steps_map(configuration_steps: dict[str, Any]) -> dict[str, Any]:
    """Return the configuration steps mapping or an empty dict when unavailable."""
    return configuration_steps if isinstance(configuration_steps, dict) else {}


def find_configuration_step_for_message(
    configuration_steps: dict[str, Any], message_name: str
) -> tuple[str, dict[str, Any]] | None:
    """Find the configuration step whose related_bin_messages documents a given message type."""
    steps = get_configuration_steps_map(configuration_steps)
    matches = [step_key for step_key, step in steps.items() if message_name in step.get("related_bin_messages", {})]
    if len(matches) > 1:
        msg = f"Message '{message_name}' is documented by multiple steps: {matches}"
        raise ValueError(msg)
    if not matches:
        return None

    step_key = matches[0]
    related_messages = steps[step_key].get("related_bin_messages", {})
    if not isinstance(related_messages, dict):
        return None
    return step_key, related_messages


def find_configuration_step_for_parameter(configuration_steps: dict[str, Any], param_name: str) -> str | None:
    """Find the configuration step that sets a given FC parameter (derived/forced/add parameters)."""
    steps = get_configuration_steps_map(configuration_steps)
    matches = [
        step_key
        for step_key, step in steps.items()
        if param_name in step.get("derived_parameters", {})
        or param_name in step.get("forced_parameters", {})
        or param_name in step.get("add_parameters", {})
    ]
    if len(matches) > 1:
        msg = f"Parameter '{param_name}' is set by multiple steps: {matches}"
        raise ValueError(msg)
    return matches[0] if matches else None


def find_matching_param_values(doc: APMDoc, param_name: str, name_substring: str) -> set[str]:
    """Find all value codes for any parameter value that contains a substring."""
    values = doc.get(param_name, {}).get("values", {})
    return {code for code, name in values.items() if name_substring in name}


def find_log_bit_in_apm_file(bitmask: str, bit_name: str) -> int | None:
    """
    Find the LOG_BITMASK bit number for a named logging category.

    Args:
        bitmask: The raw "Bitmask" field string from apm.pdef.xml's
            LOG_BITMASK parameter, e.g. "0:Fast Attitude,1:...,9:Battery Monitor".
        bit_name: The category name to search for, e.g. "Battery Monitor".

    Returns:
        The bit if found, otherwise None.

    """
    normalized_name = bit_name.strip().lower()
    entries = bitmask.split(",")

    for entry in entries:
        item = entry.strip()
        if ":" not in item:
            continue

        code, name = item.split(":", 1)
        try:
            bit = int(code.strip())
        except ValueError:
            continue

        if name.strip().lower() == normalized_name:
            return bit
    return None


def get_log_bitmask(doc: APMDoc) -> str | None:
    """Get the LOG_BITMASK Bitmask field from parameter metadata."""
    bit_value = doc.get("LOG_BITMASK", {}).get("fields", {}).get("Bitmask")
    return bit_value if isinstance(bit_value, str) else None
