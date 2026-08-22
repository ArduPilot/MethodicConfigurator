"""
Structured result types for log quality analysis.

SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-FileCopyrightText: 2026 Omkar Sarkar <omkarsarkar24@gmail.com>

SPDX-License-Identifier: GPL-3.0-or-later
"""

from dataclasses import dataclass, field
from enum import Enum


class LogQualityState(str, Enum):
    """Semantic state for a quality-analysis result."""

    INFO = "info"
    WARNING = "warning"


@dataclass
class QualityIssue:
    """One detected issue, paired with the configuration step that would fix it."""

    message: str
    config_step: str = ""
    param_name: str | None = None
    suggested_value: float | None = None


@dataclass
class LogQualityResult:
    """Result produced by a subsystem quality model (battery, GPS, etc.)."""

    available: bool
    state: LogQualityState
    reason: str
    issues: list[QualityIssue]
    name: str
    related_step: str = ""


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


@dataclass
class PMStatus:
    """Performance Monitor summary."""

    average_cpu_load: float
    peak_cpu_load: float
    scheduler_long_loops: int
    max_loop_time_us: int
    free_memory_bytes: int
    healthy: bool | None
