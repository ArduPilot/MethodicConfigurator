"""
Shared input context for deterministic log analysis.

SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-FileCopyrightText: 2026 Omkar Sarkar <omkarsarkar24@gmail.com>

SPDX-License-Identifier: GPL-3.0-or-later
"""

from dataclasses import dataclass, field
from typing import Any

from ardupilot_methodic_configurator.log_analysis.utils import APMDoc


@dataclass
class LogAnalysisContext:
    """All external inputs required to run log analysis deterministically."""

    parameters: dict[str, float]
    configuration_steps: dict[str, Any]
    vehicle_components: dict[str, Any] = field(default_factory=dict)
    apm_doc: APMDoc | None = None
