"""
Shared log-analysis utility types and helpers.

SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

from typing import Any, TypeAlias

APMDoc: TypeAlias = dict[str, Any]


def get_configuration_steps_map(configuration_steps: dict[str, Any]) -> dict[str, Any]:
    """Return the configuration steps mapping or an empty dict when unavailable."""
    steps = configuration_steps.get("steps")
    return steps if isinstance(steps, dict) else {}


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
    """Find the configuration step that sets a given FC parameter (derived/forced parameters only)."""
    steps = get_configuration_steps_map(configuration_steps)
    matches = [
        step_key
        for step_key, step in steps.items()
        if param_name in step.get("derived_parameters", {}) or param_name in step.get("forced_parameters", {})
    ]
    if len(matches) > 1:
        msg = f"Parameter '{param_name}' is set by multiple steps: {matches}"
        raise ValueError(msg)
    return matches[0] if matches else None


def find_matching_param_values(doc: APMDoc, param_name: str, name_substring: str) -> set[str]:
    """Find all value codes for any parameter value that contains a substring."""
    values = doc.get(param_name, {}).get("values", {})
    return {code for code, name in values.items() if name_substring in name}
