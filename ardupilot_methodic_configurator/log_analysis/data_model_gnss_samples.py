"""
Schema-aware numeric samples and event intervals for GNSS log analysis.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

from collections.abc import Iterator
from dataclasses import dataclass

import numpy as np

from ardupilot_methodic_configurator.log_analysis.data_model_log_data import LogData

# Fields describe capabilities, not firmware-version assumptions. UBX1 is the
# actual DataFlash message name (there is no generic UBX.jamInd message).
RECEIVER_FIELDS = {"AERG": ("Jam", "Spf"), "ILB5": ("GJS", "GSS"), "UBX1": ("jamInd",)}


def receiver_gap_limit(times: np.ndarray) -> float:
    """Allow normal slow receiver diagnostics while bounding gaps to fifteen seconds."""
    differences = np.diff(times)
    regular = differences[np.isfinite(differences) & (differences > 0)]
    return max(2.0, min(15.0, 3 * float(np.median(regular)))) if len(regular) else 2.0


def numeric_fields(log_data: LogData, message: str, fields: tuple[str, ...]) -> dict[str, np.ndarray] | None:
    """Read canonical scaled values without assuming fields exist in this firmware."""
    columns = log_data.get_message_columns(message)
    if columns is None or not columns.size or not set(fields).issubset(columns.dtype.names or ()):
        return None
    if any(columns.dtype[field].kind not in "biuf" for field in fields):
        return None
    return {field: np.asarray(log_data.get_field(message, field), dtype=np.float64) for field in fields}


@dataclass(frozen=True)
class SensorSeries:
    """One sensor's ordered records; invalid rows remain to break continuity."""

    instance: int | None
    fields: dict[str, np.ndarray]

    @property
    def times(self) -> np.ndarray:
        """Canonical seconds since boot."""
        return self.fields["TimeUS"]


def sensor_series(log_data: LogData, message: str, fields: tuple[str, ...]) -> list[SensorSeries]:
    """Split instance-tagged data; never silently combine two receivers or IMUs."""
    values = numeric_fields(log_data, message, tuple(dict.fromkeys(("TimeUS", *fields))))
    if values is None:
        return []
    columns = log_data.get_message_columns(message)
    names = columns.dtype.names if columns is not None else ()
    instance_field = next((name for name in ("I", "Instance", "C", "IMU") if name in (names or ())), None)
    if instance_field is None:
        return [SensorSeries(None, values)]
    identity = numeric_fields(log_data, message, (instance_field,))
    if identity is None:
        return []
    instances = identity[instance_field]
    valid_ids = np.isfinite(instances) & (instances >= 0) & (instances <= 255) & (instances == np.floor(instances))
    return [
        SensorSeries(int(instance), {name: data[instances == instance] for name, data in values.items()})
        for instance in np.unique(instances[valid_ids])
    ]


def continuous_slices(times: np.ndarray, valid: np.ndarray, max_gap_s: float) -> Iterator[slice]:
    """Yield finite, strictly increasing stretches without bridging bad records or gaps."""
    valid = valid & np.isfinite(times) & (times >= 0)
    start: int | None = None
    for index, timestamp in enumerate(times):
        connected = index > 0 and 0 < timestamp - times[index - 1] <= max_gap_s
        if start is not None and (not valid[index] or not connected):
            yield slice(start, index)
            start = None
        if valid[index] and start is None:
            start = index
    if start is not None:
        yield slice(start, len(times))


def event_intervals(times: np.ndarray, levels: np.ndarray, max_gap_s: float = 2.0) -> Iterator[tuple[int, int, int]]:
    """Group equal positive levels, preserving warning/critical changes and unknown gaps."""
    for section in continuous_slices(times, np.isfinite(levels) & (levels > 0), max_gap_s):
        start = section.start
        for index in range(section.start + 1, section.stop):
            if levels[index] != levels[start]:
                yield start, index - 1, int(levels[start])
                start = index
        yield start, section.stop - 1, int(levels[start])


def aligned_values(series: SensorSeries, times: np.ndarray, field: str, max_age_s: float) -> np.ndarray:
    """Match the last recorded state with a bounded age; never extrapolate through gaps."""
    result = np.full(times.shape, np.nan)
    if np.any(np.diff(series.times) < 0):
        return result  # Repeated boot-time epochs cannot be aligned unambiguously.
    values = series.fields[field]
    for section in continuous_slices(series.times, np.isfinite(values), max_age_s):
        sample_times = series.times[section]
        indices = np.searchsorted(sample_times, times, side="right") - 1
        safe_indices = np.maximum(indices, 0)
        valid = (indices >= 0) & (times - sample_times[safe_indices] <= max_age_s)
        result[valid] = values[section][safe_indices[valid]]
    return result
