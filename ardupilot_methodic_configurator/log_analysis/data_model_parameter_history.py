"""
Timestamped ArduPilot parameter history for log analysis.

SPDX-FileCopyrightText: 2026 Donald Smith

SPDX-License-Identifier: GPL-3.0-or-later
"""

import math
from bisect import bisect_right
from dataclasses import dataclass, field

from ardupilot_methodic_configurator.log_analysis.data_model_log_data import LogData


@dataclass(frozen=True, slots=True)
class _ParameterValue:
    """One logged parameter value and its scaled timestamp in seconds."""

    time_s: float
    value: float


@dataclass(frozen=True, slots=True)
class ParameterHistory:
    """
    Resolve logged parameter values at analysis timestamps in seconds.

    ArduPilot's initial parameter snapshot is emitted incrementally after log
    startup. Therefore, the chronologically first record for a parameter is its
    baseline from the beginning of the log, rather than becoming applicable
    only at that record's timestamp. Later records take effect at their logged
    timestamps. This is stepwise resolution, not interpolation.
    """

    _values_by_name: dict[str, tuple[_ParameterValue, ...]] = field(default_factory=dict)

    @classmethod
    def from_log_data(cls, log_data: LogData) -> "ParameterHistory":
        """Build history from scaled PARM records already extracted into ``log_data``."""
        values_by_name: dict[str, list[_ParameterValue]] = {}
        for record in log_data.iter_message_records("PARM"):
            name = record.get("Name")
            value = record.get("Value")
            time_s = record.get("TimeUS")
            if not isinstance(name, str) or not name or value is None or time_s is None:
                continue

            timestamp = float(time_s)
            if not math.isfinite(timestamp):
                msg = f"PARM timestamp for {name} must be finite"
                raise ValueError(msg)
            values_by_name.setdefault(name, []).append(_ParameterValue(timestamp, float(value)))

        return cls({name: tuple(sorted(values, key=lambda item: item.time_s)) for name, values in values_by_name.items()})

    def value_at(self, parameter_name: str, time_s: float) -> float | None:
        """
        Return the value applicable at ``time_s``, or ``None`` when absent.

        The first logged value is the log-start baseline, including for queries
        before its timestamp. At duplicate timestamps, the last logged record
        at that timestamp wins.
        """
        if not math.isfinite(time_s):
            msg = "Parameter query time_s must be finite"
            raise ValueError(msg)

        values = self._values_by_name.get(parameter_name)
        if not values:
            return None

        index = bisect_right(values, time_s, key=lambda item: item.time_s) - 1
        return values[max(index, 0)].value
