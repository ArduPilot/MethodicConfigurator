"""
Shared log-analysis utility types and helpers.

SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

from typing import Any, TypeAlias

APMDoc: TypeAlias = dict[str, Any]


def find_matching_param_values(doc: APMDoc, param_name: str, name_substring: str) -> set[str]:
    """Find all value codes for any parameter value that contains a substring."""
    values = doc.get(param_name, {}).get("values", {})
    return {code for code, name in values.items() if name_substring in name}
