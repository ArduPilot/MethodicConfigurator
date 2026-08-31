"""
Timestamped ArduPilot parameter history for log analysis.

SPDX-FileCopyrightText: 2026 Donald Smith

SPDX-License-Identifier: GPL-3.0-or-later
"""

import math
from bisect import bisect_right
from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType


@dataclass(frozen=True, slots=True)
class ParameterChange:
    """One effective parameter change after startup initialization."""

    time_s: float
    value: float


@dataclass(frozen=True, slots=True)
class ParameterHistory:
    """
    Resolve logged parameter values at analysis timestamps in seconds.

    Startup baselines are retained separately and apply from time zero. Later
    records take effect at their logged timestamps. This is stepwise
    resolution, not interpolation.
    """

    initial_values: Mapping[str, float] = field(default_factory=dict)
    changes: Mapping[str, tuple[ParameterChange, ...]] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Freeze mappings and change sequences so finalized histories are immutable."""
        object.__setattr__(self, "initial_values", MappingProxyType(dict(self.initial_values)))
        frozen_changes = {
            parameter_name: tuple(sorted(changes, key=lambda change: change.time_s))
            for parameter_name, changes in self.changes.items()
        }
        object.__setattr__(self, "changes", MappingProxyType(frozen_changes))

    @property
    def latest_values(self) -> dict[str, float]:
        """Return the final logged value of every valid parameter."""
        latest_values = dict(self.initial_values)
        for parameter_name, parameter_changes in self.changes.items():
            if parameter_changes:
                latest_values[parameter_name] = parameter_changes[-1].value
        return latest_values

    def value_at(self, parameter_name: str, time_s: float) -> float | None:
        """
        Return the value applicable at ``time_s``, or ``None`` when absent.

        An initial value applies from time zero until its first recorded change.
        At duplicate timestamps, the last logged record at that timestamp wins.
        """
        if not math.isfinite(time_s):
            msg = "Parameter query time_s must be finite"
            raise ValueError(msg)

        changes = self.changes.get(parameter_name)
        if not changes:
            return self.initial_values.get(parameter_name)

        index = bisect_right(changes, time_s, key=lambda item: item.time_s) - 1
        return self.initial_values.get(parameter_name) if index < 0 else changes[index].value
