"""
Parameter metadata helpers for vehicle overview.

SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import contextlib

from ardupilot_methodic_configurator.log_analysis.utils import APMDoc, find_matching_param_values


def tcal_enabled_codes(apm_doc: APMDoc | None, instance: int) -> set[str]:
    """Return INS_TCAL{n}_ENABLE codes that map to enabled states in apm.pdef.xml."""
    if apm_doc is None:
        return set()
    return find_matching_param_values(apm_doc, f"INS_TCAL{instance}_ENABLE", "Enabled")


def enum_value_name(apm_doc: APMDoc | None, param_name: str, value: float | None) -> str | None:
    """Resolve the display name for an enum-like parameter value from apm.pdef.xml."""
    if apm_doc is None or value is None:
        return None

    with contextlib.suppress(TypeError, ValueError):
        key = str(int(value))
        values = apm_doc.get(param_name, {}).get("values", {})
        if isinstance(values, dict):
            resolved = values.get(key)
            if isinstance(resolved, str):
                return resolved

    return None
