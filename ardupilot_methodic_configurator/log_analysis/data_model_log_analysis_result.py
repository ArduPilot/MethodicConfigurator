"""
Structured types for log analysis.

SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-FileCopyrightText: 2026 Omkar Sarkar <omkarsarkar24@gmail.com>

SPDX-License-Identifier: GPL-3.0-or-later

"""

from dataclasses import dataclass


@dataclass
class LogAnalysis:
    """Base log analysis class."""

    message: str
    timestamp_us: int | float | None = None
    value: float | None = None
    related_step: str | None = None
    param_name: str | None = None
    suggested_value: int | float | None = None


@dataclass
class LogAnalysisResult:
    """Result produced by a single analysis model."""

    available: bool
    outcomes: list[LogAnalysis]
    name: str | None
    reason: str
    related_step: str | None = None
    subsystem_key: str | None = None
