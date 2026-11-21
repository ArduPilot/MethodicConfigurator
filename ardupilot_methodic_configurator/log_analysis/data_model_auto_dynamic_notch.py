"""
Fit the first dynamic harmonic notch from in-memory pre-filter gyro batches.

The fitting rules follow ArduPilot WebTools PR #363's auto-fit.js. FFT and
throttle adapters follow WebTools commit 7b98e0b21d3d3920f029a9f401269d912828ad67.
All returned parameters are proposals; this module never applies them.

SPDX-FileCopyrightText: 2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

from collections.abc import Callable, Iterator, Mapping, Sequence
from dataclasses import dataclass, field
from math import ceil, floor, isfinite, sqrt
from typing import Any

import numpy as np
from numpy.typing import NDArray

from ardupilot_methodic_configurator import _
from ardupilot_methodic_configurator.log_analysis.data_model_availability_base import (
    BaseLogAnalysisModel,
    BaseLogAvailabilityModel,
)
from ardupilot_methodic_configurator.log_analysis.data_model_availability_fft import FftLogAvailabilityModel
from ardupilot_methodic_configurator.log_analysis.data_model_log_analysis_context import LogAnalysisContext
from ardupilot_methodic_configurator.log_analysis.data_model_log_analysis_result import LogAnalysis, LogAnalysisResult
from ardupilot_methodic_configurator.log_analysis.data_model_log_availability import (
    AvailabilityIssue,
    LogAvailabilityResult,
    LogAvailabilityState,
)
from ardupilot_methodic_configurator.log_analysis.data_model_log_data import LogData

FloatArray = NDArray[np.float64]
WindowFactory = Callable[[], Iterator["GyroFftWindow"]]
_PREFIX = "INS_HNTCH_"
_SUFFIXES = ("ENABLE", "MODE", "FREQ", "BW", "ATT", "REF", "FM_RAT", "HMNCS", "OPTS")
_FRAME_MOTORS = {1: 4, 2: 6, 3: 8, 4: 8, 5: 6, 7: 4, 8: 6, 9: 6, 12: 12, 14: 10}
_INTERPRETATION_PREFIXES = (
    "INS_LOG_BAT_",
    "INS_GYR",
    "INS_HNTCH_",
    "MOT_",
    "Q_M_",
    "SERVO",
    "FRAME_",
    "Q_FRAME_",
    "BARO_PRIMARY",
    "Q_ENABLE",
    "H_RSC_",
)


@dataclass(frozen=True)
class AutoDynamicNotchSettings:
    """Reproducible FFT and time-coverage settings; times are in seconds."""

    fft_window_size: int = 1024
    overlap: float = 0.5
    start_time_s: float | None = None
    end_time_s: float | None = None
    telemetry_gap_s: float = 1.0

    def __post_init__(self) -> None:
        """Reject unusable numerical settings before preparing log data."""
        size = self.fft_window_size
        if not isinstance(size, int) or size < 64 or size & (size - 1):
            raise ValueError(_("FFT window size must be a power of two of at least 64"))
        if not 0 <= self.overlap < 1 or not isfinite(self.telemetry_gap_s) or self.telemetry_gap_s <= 0:
            raise ValueError(_("Invalid FFT overlap or telemetry gap"))
        for value in (self.start_time_s, self.end_time_s):
            if value is not None and (not isfinite(value) or value < 0):
                raise ValueError(_("Analysis times must be finite and non-negative"))
        if self.start_time_s is not None and self.end_time_s is not None and self.start_time_s >= self.end_time_s:
            raise ValueError(_("Analysis start must precede its end"))


@dataclass(frozen=True)
class GyroFftWindow:
    """One three-axis power spectrum, using WebTools' one-sided scaling."""

    time_s: float
    instance: int
    bins_hz: FloatArray
    power: FloatArray


@dataclass(frozen=True)
class TrackingSamples:
    """One telemetry series; invalid samples and long gaps interrupt coverage."""

    time_s: FloatArray
    values: FloatArray

    def __post_init__(self) -> None:
        """Keep interpolation inputs one-dimensional, finite in time, and ordered."""
        if self.time_s.ndim != 1 or self.values.shape != self.time_s.shape:
            raise ValueError(_("Tracking timestamps and values must have matching one-dimensional shapes"))
        if not np.isfinite(self.time_s).all() or (np.diff(self.time_s) <= 0).any():
            raise ValueError(_("Tracking timestamps must be finite and strictly increasing"))

    def interpolate(self, times: FloatArray, max_gap_s: float) -> FloatArray:
        result = np.full(times.shape, np.nan, dtype=np.float64)
        if len(self.time_s) == 0:
            return result
        indices = np.searchsorted(self.time_s, times)
        exact = indices < len(self.time_s)
        exact[exact] &= self.time_s[indices[exact]] == times[exact]
        result[exact] = self.values[indices[exact]]
        between = (~exact) & (indices > 0) & (indices < len(self.time_s))
        right = indices[between]
        left = right - 1
        gap = self.time_s[right] - self.time_s[left]
        valid = gap <= max_gap_s
        positions = np.flatnonzero(between)[valid]
        fraction = (times[positions] - self.time_s[left[valid]]) / gap[valid]
        result[positions] = self.values[left[valid]] + fraction * (self.values[right[valid]] - self.values[left[valid]])
        return result


@dataclass(frozen=True)
class TrackingSource:
    """ESC frequencies in Hz, or normalized thrust for throttle tracking."""

    name: str
    mode: int
    multi_source: bool
    samples: tuple[TrackingSamples, ...]

    def tracked(self, time_s: float, max_gap_s: float) -> float:
        values = np.array([series.interpolate(np.array([time_s]), max_gap_s)[0] for series in self.samples])
        if len(values) == 0 or not np.isfinite(values).all() or (values < 0).any():
            return float("nan")
        if self.mode == 1:
            values = np.sqrt(values)
        return float(np.mean(values))


@dataclass(frozen=True)
class OrderSpectrum:
    """Mean power in dB on a frequency/order grid, with accepted tracking values."""

    grid: FloatArray
    db: FloatArray
    tracked: FloatArray
    times_s: FloatArray


@dataclass(frozen=True)
class DynamicNotchFit:  # pylint: disable=too-many-instance-attributes
    """Complete first-notch proposal and the evidence supporting it."""

    source: str
    mode: int
    frequency_hz: int
    reference: float
    minimum_ratio: float
    multi_source: bool
    harmonics: int
    attenuation_db: int
    prominences_db: tuple[float, ...]
    window_count: int
    start_time_s: float
    end_time_s: float

    def parameter_values(self, existing_options: int) -> dict[str, int | float]:
        options = existing_options & ~(1 | 16 | 64 | 2)
        if self.multi_source:
            options |= 2
        values = (
            1,
            self.mode,
            self.frequency_hz,
            _js_round(self.frequency_hz * 0.5),
            self.attenuation_db,
            self.reference,
            self.minimum_ratio,
            self.harmonics,
            options,
        )
        return {_PREFIX + suffix: value for suffix, value in zip(_SUFFIXES, values, strict=True)}


def _js_round(value: float) -> int:
    return floor(value + 0.5)


def _percentile(values: FloatArray, fraction: float) -> float:
    return float(np.sort(values)[floor((len(values) - 1) * fraction)])


def build_order_spectrum(windows: WindowFactory, tracked_value: Callable[[float], float], grid: FloatArray) -> OrderSpectrum:
    """Average interpolated linear power, then convert sufficiently covered bins to dB."""
    total = np.zeros(grid.shape)
    counts = np.zeros(grid.shape, dtype=np.int64)
    tracked: list[float] = []
    times: list[float] = []
    for window in windows():
        value = tracked_value(window.time_s)
        if not isfinite(value) or value <= 0:
            continue
        tracked.append(value)
        times.append(window.time_s)
        frequencies = grid * value
        covered = frequencies < window.bins_hz[-1]
        power = np.interp(frequencies[covered], window.bins_hz, window.power)
        valid = np.isfinite(power) & (power > 0)
        positions = np.flatnonzero(covered)[valid]
        total[positions] += power[valid]
        counts[positions] += 1
    db = np.full(grid.shape, np.nan)
    covered = (counts > 0) & (counts >= len(tracked) * 0.5)
    db[covered] = 10 * np.log10(total[covered] / counts[covered])
    return OrderSpectrum(grid, db, np.array(tracked), np.array(times))


def harmonic_prominence(spectrum: OrderSpectrum, position: float, scale: float) -> float:
    """Peak above the upper median local floor; a boundary maximum is rejected."""
    step = float(spectrum.grid[1] - spectrum.grid[0])

    def index(value: float) -> int:
        return _js_round((value - float(spectrum.grid[0])) / step)

    start, end = index(position - scale * 0.5), index(position + scale * 0.5)
    if start < 0 or end >= len(spectrum.db) or not np.isfinite(spectrum.db[start : end + 1]).all():
        return float("-inf")
    peak_start, peak_end = index(position - scale * 0.1), index(position + scale * 0.1)
    peak_values = spectrum.db[peak_start : peak_end + 1]
    maximum = int(np.argmax(peak_values))
    if maximum in (0, len(peak_values) - 1):
        return float("-inf")
    floor_values = spectrum.db[start : end + 1][np.abs(spectrum.grid[start : end + 1] - position) > scale * 0.12]
    if len(floor_values) == 0:
        return float("-inf")
    noise_floor = np.sort(floor_values)[len(floor_values) // 2]
    return float(peak_values[maximum] - noise_floor)


def _strongest_peak(spectrum: OrderSpectrum, scale: float | None) -> tuple[float, float] | None:
    best_position: float | None = None
    best_excess = float("-inf")
    for index in range(10, len(spectrum.db) - 10):
        value = spectrum.db[index]
        if not isfinite(value) or np.any(spectrum.db[index - 10 : index + 11] > value):
            continue
        position = float(spectrum.grid[index])
        excess = harmonic_prominence(spectrum, position, position if scale is None else scale)
        if best_position is None or excess > best_excess:
            best_position, best_excess = position, excess
    return (best_position, best_excess) if best_position is not None and best_excess >= 6 else None


def fit_tracking_source(  # pylint: disable=too-many-locals
    windows: WindowFactory,
    source: TrackingSource,
    settings: AutoDynamicNotchSettings,
) -> DynamicNotchFit:
    """Fit one source, raising a translated ValueError when its tracking is rejected."""
    if source.mode not in (1, 3):
        raise ValueError(_("Only ESC RPM and throttle tracking are supported"))
    reference = 1.0
    if source.mode == 1:
        roots = [source.tracked(window.time_s, settings.telemetry_gap_s) for window in windows()]
        positive = np.array([root for root in roots if isfinite(root) and root > 0])
        if len(positive) == 0:
            raise ValueError(_("Throttle is zero or unavailable in the analysis interval"))
        reference = float(np.mean(positive**2))
        maximum_frequency = min(float(window.bins_hz[-1]) for window in windows())
        grid = np.arange(10, maximum_frequency + 0.001, 0.25, dtype=np.float64)
    else:
        grid = np.arange(0.25, 8.75 + 0.001, 0.005, dtype=np.float64)

    def tracked_value(time_s: float) -> float:
        value = source.tracked(time_s, settings.telemetry_gap_s)
        if source.mode == 3 and value < 10:
            return float("nan")
        return value / sqrt(reference)

    spectrum = build_order_spectrum(windows, tracked_value, grid)
    if len(spectrum.tracked) == 0:
        raise ValueError(_("No FFT windows have tracking telemetry with motors running"))
    strongest = _strongest_peak(spectrum, 1.0 if source.mode == 3 else None)
    fundamental = 1.0
    if source.mode == 1:
        if strongest is None:
            raise ValueError(_("No noise peaks follow throttle"))
        fundamental = strongest[0]
        for harmonic in (4, 3, 2):
            position = strongest[0] / harmonic
            if position >= 20 and harmonic_prominence(spectrum, position, position) >= 6:
                fundamental = position
                break
    peaks = tuple(harmonic_prominence(spectrum, fundamental * harmonic, fundamental) for harmonic in range(1, 9))
    if source.mode == 3 and strongest is not None:
        nearest = max(1, _js_round(strongest[0]))
        if abs(strongest[0] - nearest) > nearest * 0.1 and strongest[1] > max(peaks) + 6:
            raise ValueError(
                _("Largest noise peak is at {order:.2f} times ESC frequency; check motor poles").format(order=strongest[0])
            )
    harmonics = sum(1 << index for index, peak in enumerate(peaks) if peak >= 6)
    if harmonics == 0:
        raise ValueError(_("No noise peaks follow the selected tracking source"))
    low = _percentile(spectrum.tracked, 0.05)
    frequency = _js_round(low * 0.8) if source.mode == 3 else _js_round(fundamental)
    minimum_ratio = 1.0 if source.mode == 3 else min(1.0, max(0.1, floor(20 * low * 0.8) / 20))
    return DynamicNotchFit(
        source.name,
        source.mode,
        frequency,
        _js_round(reference * 100) / 100,
        minimum_ratio,
        source.multi_source,
        harmonics,
        _js_round(min(50, max(10, *peaks))),
        peaks,
        len(spectrum.tracked),
        float(np.min(spectrum.times_s)),
        float(np.max(spectrum.times_s)),
    )


def _columns(log_data: LogData, message: str, names: Sequence[str]) -> dict[str, NDArray[Any]]:
    records = log_data.get_message_columns(message)
    if records is None or len(records) == 0 or not set(names).issubset(records.dtype.names or ()):
        raise ValueError(_("Missing {message} fields: {fields}").format(message=message, fields=", ".join(names)))
    columns = {name: log_data.get_field(message, name) for name in names}
    if any(not np.issubdtype(values.dtype, np.number) for values in columns.values()):
        raise ValueError(_("Non-numeric fields in {message}").format(message=message))
    return columns


def _instance_field(log_data: LogData, message: str) -> str:
    records = log_data.get_message_columns(message)
    for name in ("Instance", "I", "Inst"):
        if records is not None and name in (records.dtype.names or ()):
            return name
    raise ValueError(_("Missing instance field in {message}").format(message=message))


def _tracking_series(times: FloatArray, values: FloatArray) -> TrackingSamples:
    times = np.asarray(times, dtype=np.float64)
    if len(times) == 0 or not np.isfinite(times).all() or (np.diff(times) < 0).any():
        raise ValueError(_("Tracking timestamps are missing, invalid, or out of order"))
    # Keep the last observation at duplicate timestamps without bridging invalid values.
    keep = np.r_[np.diff(times) > 0, True]
    return TrackingSamples(np.asarray(times[keep], dtype=np.float64), np.asarray(values[keep], dtype=np.float64))


def _gyro_count(log_data: LogData, parameters: Mapping[str, float]) -> int | None:
    indices = [index for index in range(1, 10) if parameters.get("INS_GYR_ID" if index == 1 else f"INS_GYR{index}_ID", 0) > 0]
    if indices:
        return max(indices)
    records = log_data.get_message_columns("IMU")
    if records is not None and "I" in (records.dtype.names or ()):
        instances = log_data.get_field("IMU", "I")
        if len(instances) > 0 and np.isfinite(instances).all():
            return int(np.max(instances)) + 1
    return None


def iter_gyro_fft_windows(  # pylint: disable=too-many-locals
    log_data: LogData,
    parameters: Mapping[str, float],
    settings: AutoDynamicNotchSettings,
    diagnostics: list[str] | None = None,
) -> Iterator[GyroFftWindow]:
    """Reconstruct complete pre-filter batches; never join across a batch boundary."""
    headers = _columns(log_data, "ISBH", ("TimeUS", "N", "type", "instance", "mul", "smp_cnt", "smp_rate", "SampleUS"))
    packets = _columns(log_data, "ISBD", ("TimeUS", "N", "seqno", "x", "y", "z"))
    gyro_limit = _pre_filter_gyro_limit(log_data, parameters)
    size = settings.fft_window_size
    taper = np.hanning(size)
    scale = np.full(size // 2 + 1, 2.0 / size)
    scale[[0, -1]] = 1.0 / size
    spacing = max(1, _js_round(size * (1 - settings.overlap)))
    skipped = 0
    for index in _gyro_batch_indices(headers, packets, gyro_limit):
        batch = _reconstruct_batch(headers, packets, index, size)
        if batch is None:
            skipped += 1
            continue
        sample_time, rate, samples = batch
        bins = np.asarray(np.fft.rfftfreq(size, 1.0 / rate), dtype=np.float64)
        for offset in range(0, samples.shape[1] - size + 1, spacing):
            time_s = float(sample_time + (offset + size * 0.5) / rate)
            if settings.start_time_s is not None and time_s < settings.start_time_s:
                continue
            if settings.end_time_s is not None and time_s > settings.end_time_s:
                continue
            magnitude = np.abs(np.fft.rfft(samples[:, offset : offset + size] * taper, axis=1)) * scale
            yield GyroFftWindow(time_s, int(headers["instance"][index]), bins, np.sum(magnitude**2, axis=0))
    if diagnostics is not None and skipped:
        diagnostics.append(_("Skipped {count} incomplete or invalid gyro batches").format(count=skipped))


def _pre_filter_gyro_limit(log_data: LogData, parameters: Mapping[str, float]) -> int:
    options = parameters.get("INS_LOG_BAT_OPT")
    if options is None or not isfinite(options) or options < 0 or options != int(options):
        raise ValueError(_("INS_LOG_BAT_OPT is required to identify pre-filter gyro data"))
    combined = bool(int(options) & 4)
    if int(options) & 2 and not combined:
        raise ValueError(_("Auto fit requires pre-filter gyro data; only post-filter batches were logged"))
    count = _gyro_count(log_data, parameters)
    if combined and count is None:
        raise ValueError(_("Gyro count is required to distinguish pre-filter and post-filter instances"))
    return count if count is not None else 256


def _gyro_batch_indices(
    headers: Mapping[str, NDArray[Any]],
    packets: Mapping[str, NDArray[Any]],
    gyro_limit: int,
) -> Iterator[int]:
    for columns in (headers, packets):
        times = columns["TimeUS"]
        if times.ndim != 1 or not np.isfinite(times).all() or (times[1:] < times[:-1]).any():
            raise ValueError(_("Batch logging timestamps are invalid or out of order"))
    if any(packets[axis].shape != (len(packets["N"]), 32) for axis in ("x", "y", "z")):
        raise ValueError(_("Gyro batch packets must contain 32 samples per axis"))
    for index, sensor_type in enumerate(headers["type"]):
        if sensor_type == 1 and headers["instance"][index] < gyro_limit:
            yield index


def _reconstruct_batch(
    headers: Mapping[str, NDArray[Any]],
    packets: Mapping[str, NDArray[Any]],
    index: int,
    minimum_samples: int,
) -> tuple[float, float, FloatArray] | None:
    sample_time, rate, multiplier, count, instance = (
        float(headers[name][index]) for name in ("SampleUS", "smp_rate", "mul", "smp_cnt", "instance")
    )
    if not all(isfinite(value) and value > 0 for value in (rate, multiplier, count)):
        return None
    if not isfinite(sample_time) or sample_time < 0 or not isfinite(instance) or instance < 0 or instance != int(instance):
        return None
    if count != int(count) or count < minimum_samples or count > 65535:
        return None
    first = int(np.searchsorted(packets["TimeUS"], headers["TimeUS"][index]))
    next_time = headers["TimeUS"][index + 1] if index + 1 < len(headers["N"]) else float("inf")
    last = int(np.searchsorted(packets["TimeUS"], next_time))
    selected = np.arange(first, last)[packets["N"][first:last] == headers["N"][index]]
    if len(selected) != ceil(count / 32) or not np.array_equal(packets["seqno"][selected], np.arange(len(selected))):
        return None
    samples = np.array([packets[axis][selected].reshape(-1)[: int(count)] for axis in ("x", "y", "z")]) / multiplier
    if samples.shape != (3, int(count)) or not np.isfinite(samples).all():
        return None
    return sample_time, rate, samples


def _esc_source(log_data: LogData, parameters: Mapping[str, float]) -> TrackingSource:
    instance_field = _instance_field(log_data, "ESC")
    columns = _columns(log_data, "ESC", ("TimeUS", "RPM", instance_field))
    instances = np.unique(columns[instance_field])
    if (
        not np.isfinite(instances).all()
        or (instances < 0).any()
        or (instances > 31).any()
        or (instances != np.floor(instances)).any()
    ):
        raise ValueError(_("ESC instances are invalid"))
    mask = parameters.get("INS_HNTCH_ESC_MASK", 0)
    if not isfinite(mask) or mask < 0 or mask != int(mask):
        raise ValueError(_("INS_HNTCH_ESC_MASK is invalid"))
    selected = [int(instance) for instance in instances if mask == 0 or int(mask) & (1 << int(instance))]
    if mask and sum(1 << instance for instance in selected) != int(mask):
        raise ValueError(_("ESC telemetry is missing for motors selected by INS_HNTCH_ESC_MASK"))
    tracks = []
    for instance in selected:
        keep = columns[instance_field] == instance
        tracks.append(_tracking_series(columns["TimeUS"][keep], columns["RPM"][keep] / 60))
    if not tracks:
        raise ValueError(_("No ESC telemetry"))
    return TrackingSource(_("ESC RPM"), 3, len(instances) > 1, tuple(tracks))


def _average_throttle_source(log_data: LogData, parameters: Mapping[str, float]) -> TrackingSource:
    if log_data.vehicle_type not in ("ArduCopter", "Copter", "ArduPlane", "ArduRover", "Rover"):
        raise ValueError(_("Throttle tracking is unsupported for this vehicle type"))
    if parameters.get("FRAME_CLASS") == 6 or parameters.get("H_RSC_MODE", 0) > 0:
        raise ValueError(_("Throttle tracking is unavailable for helicopters"))
    if log_data.vehicle_type == "ArduPlane" and parameters.get("Q_ENABLE", 0) <= 0:
        raise ValueError(_("Throttle tracking requires a QuadPlane motor configuration"))
    message, name = "RATE", "AOut"
    if log_data.get_message_columns(message) is None and log_data.vehicle_type in ("ArduCopter", "Copter"):
        message, name = "CTUN", "ThO"
    columns = _columns(log_data, message, ("TimeUS", name))
    values = columns[name]
    values = np.where((values >= 0) & (values <= 1), values, np.nan)
    return TrackingSource(_("Average throttle"), 1, multi_source=False, samples=(_tracking_series(columns["TimeUS"], values),))


def _air_density_correction(altitude_m: FloatArray) -> FloatArray:
    # US Standard Atmosphere 1976 constants, as used by AP_Baro/WebTools.
    layers = np.array(
        [
            (-5000, 320.650, 1.930467, -0.0065),
            (11000, 216.650, 0.363918, 0),
            (20000, 216.650, 0.0880349, 0.001),
            (32000, 228.650, 0.0132250, 0.0028),
            (47000, 270.650, 0.00142753, 0),
            (51000, 270.650, 0.000861606, -0.0028),
            (71000, 214.650, 0.000064211, -0.002),
            (84852, 186.946, 0.00000695788, 0),
        ]
    )
    altitude = 6356766 * altitude_m / (6356766 + altitude_m)
    index = np.clip(np.searchsorted(layers[:, 0], altitude, side="right") - 1, 0, len(layers) - 1)
    base, temperature, density, lapse = layers[index].T
    delta = altitude - base
    actual_temperature = temperature + lapse * delta
    ratio = np.full(altitude.shape, np.nan)
    valid = np.isfinite(altitude) & (actual_temperature > 0)
    isothermal = valid & (lapse == 0)
    gradient = valid & (lapse != 0)
    ratio[isothermal] = (
        density[isothermal] * np.exp(-9.80665 * delta[isothermal] / (temperature[isothermal] * 287.053072)) / 1.225
    )
    ratio[gradient] = (
        density[gradient]
        * (actual_temperature[gradient] / temperature[gradient]) ** (-(9.80665 / (lapse[gradient] * 287.053072) + 1))
        / 1.225
    )
    correction = np.where((ratio > 0.3) & (ratio < 1.5), 1 / np.clip(ratio, 0.5, 1.25), 1.0)
    correction[~valid] = np.nan
    return correction


def _motor_functions(parameters: Mapping[str, float]) -> list[int]:
    functions = [int(parameters.get(f"SERVO{channel}_FUNCTION", 0)) for channel in range(1, 33)]
    motor_count = sum(33 <= value <= 40 or 82 <= value <= 85 for value in functions)
    frame = int(parameters.get("FRAME_CLASS", parameters.get("Q_FRAME_CLASS", 0)))
    if frame == 10:
        return [73, 74]
    count = motor_count if frame in (15, 16, 17) else _FRAME_MOTORS.get(frame, 0)
    if not count or count != motor_count:
        raise ValueError(_("Motor output functions do not match the frame class"))
    if frame == 7:
        return [33, 34, 36]
    if frame in (8, 9):
        return [38, 39]
    return [33 + index if index < 8 else 82 + index - 8 for index in range(count)]


def _battery_corrections(
    log_data: LogData,
    motor: Mapping[str, float],
    times: FloatArray,
    settings: AutoDynamicNotchSettings,
) -> tuple[FloatArray, FloatArray]:
    if motor["BAT_VOLT_MAX"] <= 0 or motor["BAT_VOLT_MIN"] >= motor["BAT_VOLT_MAX"]:
        return np.ones(times.shape), np.ones(times.shape)
    instance = _instance_field(log_data, "BAT")
    names = ("TimeUS", instance, "Volt") if int(motor["OPTIONS"]) & 1 else ("TimeUS", instance, "Volt", "VoltR")
    columns = _columns(log_data, "BAT", names)
    keep = columns[instance] == motor["BAT_IDX"]
    voltage = columns["Volt"][keep]
    if not int(motor["OPTIONS"]) & 1:
        voltage = np.maximum(voltage, columns["VoltR"][keep])
    normalized = np.clip(voltage, motor["BAT_VOLT_MIN"], motor["BAT_VOLT_MAX"]) / motor["BAT_VOLT_MAX"]
    normalized[voltage < 0.25 * motor["BAT_VOLT_MIN"]] = 1
    lift = normalized * (1 - motor["THST_EXPO"]) + motor["THST_EXPO"] * normalized**2
    return (
        _tracking_series(columns["TimeUS"][keep], normalized).interpolate(times, settings.telemetry_gap_s),
        _tracking_series(columns["TimeUS"][keep], lift).interpolate(times, settings.telemetry_gap_s),
    )


def _motor_throttle_source(  # pylint: disable=too-many-locals
    log_data: LogData,
    parameters: Mapping[str, float],
    settings: AutoDynamicNotchSettings,
) -> TrackingSource:
    _average_throttle_source(log_data, parameters)  # Same vehicle/source eligibility as WebTools.
    if log_data.firmware_version is None or log_data.firmware_version < (4, 6, 0):
        raise ValueError(_("Per-motor throttle tracking requires ArduPilot 4.6 or later"))
    prefix = "Q_M_" if log_data.vehicle_type == "ArduPlane" else "MOT_"
    names = ("THST_EXPO", "SPIN_MAX", "SPIN_MIN", "PWM_MIN", "PWM_MAX", "BAT_VOLT_MIN", "BAT_VOLT_MAX", "BAT_IDX")
    if any(prefix + name not in parameters for name in names):
        raise ValueError(_("Motor parameters are incomplete for per-motor throttle reconstruction"))
    motor = {name: parameters[prefix + name] for name in names}
    motor["OPTIONS"] = parameters.get(prefix + "OPTIONS", 0)
    if motor["PWM_MAX"] <= motor["PWM_MIN"] or motor["SPIN_MAX"] <= motor["SPIN_MIN"]:
        raise ValueError(_("Motor PWM or spin ranges are invalid"))
    motor["THST_EXPO"] = min(1, max(-1, motor["THST_EXPO"]))
    instance = _instance_field(log_data, "BARO")
    barometer = _columns(log_data, "BARO", ("TimeUS", instance, "Alt"))
    if "BARO_PRIMARY" not in parameters:
        raise ValueError(_("BARO_PRIMARY is required for per-motor throttle reconstruction"))
    keep = barometer[instance] == parameters["BARO_PRIMARY"]
    density = _tracking_series(barometer["TimeUS"][keep], _air_density_correction(barometer["Alt"][keep]))
    tracks = []
    for function in _motor_functions(parameters):
        channels = [channel for channel in range(1, 33) if parameters.get(f"SERVO{channel}_FUNCTION") == function]
        if len(channels) != 1:
            raise ValueError(_("Motor output assignment is missing or ambiguous"))
        channel = channels[0]
        message = "RCOU" if channel <= 14 else "RCO2" if channel <= 18 else "RCO3"
        output = _columns(log_data, message, ("TimeUS", f"C{channel}"))
        times = output["TimeUS"]
        voltage, lift = _battery_corrections(log_data, motor, times, settings)
        throttle = (output[f"C{channel}"] - motor["PWM_MIN"]) / (motor["PWM_MAX"] - motor["PWM_MIN"])
        throttle = np.clip((throttle - motor["SPIN_MIN"]) / (motor["SPIN_MAX"] - motor["SPIN_MIN"]), 0, 1)
        expo = motor["THST_EXPO"]
        # Invert actuator thrust curve, voltage scaling, and compensation gain.
        thrust = (
            throttle * voltage
            if expo == 0
            else np.clip(((2 * expo * throttle * voltage + 1 - expo) ** 2 - (1 - expo) ** 2) / (4 * expo * lift), 0, 1) * lift
        )
        thrust /= density.interpolate(times, settings.telemetry_gap_s)
        tracks.append(_tracking_series(times, thrust))
    return TrackingSource(_("Per-motor throttle"), 1, multi_source=True, samples=tuple(tracks))


def _parameter_error(parameters: Mapping[str, float], documentation: Mapping[str, Any] | None) -> str:
    for suffix in _SUFFIXES:
        name = _PREFIX + suffix
        if name not in parameters or not isfinite(parameters[name]) or not documentation or name not in documentation:
            return _("Logged parameter and documentation required: {name}").format(name=name)
    if parameters[_PREFIX + "OPTS"] < 0 or parameters[_PREFIX + "OPTS"] != int(parameters[_PREFIX + "OPTS"]):
        return _("Harmonic notch options are invalid")
    return ""


def _validate_proposal(values: Mapping[str, int | float], documentation: Mapping[str, Any]) -> None:
    for name, value in values.items():
        metadata = documentation[name]
        minimum, maximum = metadata.get("min"), metadata.get("max")
        bounds = str(metadata.get("fields", {}).get("Range", "")).split()
        if len(bounds) == 2 and minimum is None and maximum is None:
            minimum, maximum = float(bounds[0]), float(bounds[1])
        if (
            not isfinite(value)
            or (minimum is not None and value < float(minimum))
            or (maximum is not None and value > float(maximum))
        ):
            raise ValueError(_("Fitted value for {name} is outside its documented range").format(name=name))
        enums = metadata.get("Values", metadata.get("values", {}))
        if enums and value not in {float(code) for code in enums}:
            raise ValueError(_("Fitted value for {name} is unsupported by this firmware").format(name=name))
        bits = metadata.get("Bitmask", metadata.get("bitmask", {}))
        if bits and int(value) & ~sum(1 << int(bit) for bit in bits):
            raise ValueError(_("Fitted option bits for {name} are unsupported by this firmware").format(name=name))
    if values[_PREFIX + "FREQ"] <= 0 or values[_PREFIX + "BW"] <= 0 or values[_PREFIX + "REF"] <= 0:
        raise ValueError(_("Fitted frequency, bandwidth, and reference must be positive"))


@dataclass
class _FitInputs:
    """Loaded fitting context shared by availability and analysis adapters."""

    log_data: LogData
    context: LogAnalysisContext
    settings: AutoDynamicNotchSettings
    diagnostics: list[str] = field(default_factory=list)

    def parameters(self) -> dict[str, float]:
        parameters = dict(self.context.parameters)
        history = self.context.parameter_history
        start = self.settings.start_time_s or 0
        end = self.settings.end_time_s if self.settings.end_time_s is not None else float("inf")
        for name, changes in history.changes.items():
            relevant = name.startswith(_INTERPRETATION_PREFIXES)
            if relevant and any(start < change.time_s <= end for change in changes):
                raise ValueError(_("Parameter {name} changed during analysis; select a stable interval").format(name=name))
        for name in history.initial_values.keys() | history.changes.keys():
            value = history.value_at(name, start)
            if value is not None:
                parameters[name] = value
        relevant_values = (value for name, value in parameters.items() if name.startswith(_INTERPRETATION_PREFIXES))
        if any(not isfinite(value) for value in relevant_values):
            raise ValueError(_("Logged parameters contain non-finite values"))
        error = _parameter_error(parameters, self.context.apm_doc)
        if error:
            raise ValueError(error)
        return parameters

    def sources(self, parameters: Mapping[str, float]) -> Iterator[TrackingSource | str]:
        factories: tuple[Callable[[], TrackingSource], ...] = (
            lambda: _esc_source(self.log_data, parameters),
            lambda: _motor_throttle_source(self.log_data, parameters, self.settings),
            lambda: _average_throttle_source(self.log_data, parameters),
        )
        for factory in factories:
            try:
                yield factory()
            except ValueError as error:  # noqa: PERF203 - Only three candidates; failures enable fallback.
                yield str(error)


class AutoDynamicNotchLogAvailabilityModel(BaseLogAvailabilityModel):
    """Require usable pre-filter gyro batches and at least one overlapping source."""

    def __init__(
        self,
        log_data: LogData,
        context: LogAnalysisContext,
        settings: AutoDynamicNotchSettings | None = None,
    ) -> None:
        super().__init__(log_data, context)
        self.inputs = _FitInputs(log_data, context, settings or AutoDynamicNotchSettings())

    def check(self) -> LogAvailabilityResult:
        fft = FftLogAvailabilityModel(self.log_data, self.inputs.context).check()
        issues = list(fft.issues)
        reason = ""
        try:
            if not fft.available:
                raise ValueError(fft.reason)
            parameters = self.inputs.parameters()
            sources = [source for source in self.inputs.sources(parameters) if isinstance(source, TrackingSource)]
            usable = any(
                any(
                    0 < source.tracked(window.time_s, self.inputs.settings.telemetry_gap_s) < float("inf")
                    for source in sources
                )
                for window in iter_gyro_fft_windows(self.log_data, parameters, self.inputs.settings)
            )
            if not usable:
                raise ValueError(_("No complete pre-filter FFT windows overlap usable tracking telemetry"))
        except ValueError as error:
            reason = str(error)
            issues.append(AvailabilityIssue(reason))
        return LogAvailabilityResult(
            available=not reason,
            state=LogAvailabilityState.WARNING if reason or issues else LogAvailabilityState.INFO,
            reason=reason or _("Pre-filter gyro data and tracking telemetry are available"),
            issues=issues,
            name=_("Automatic dynamic notch"),
            related_step=self.step_for_parameter(_PREFIX + "FREQ"),
        )


class AutoDynamicNotchLogAnalysis(BaseLogAnalysisModel):
    """Fit ESC RPM, per-motor throttle, then average throttle without applying changes."""

    def __init__(
        self,
        log_data: LogData,
        context: LogAnalysisContext,
        settings: AutoDynamicNotchSettings | None = None,
    ) -> None:
        super().__init__(log_data, context)
        self.inputs = _FitInputs(log_data, context, settings or AutoDynamicNotchSettings())

    def analyse(self) -> LogAnalysisResult:
        self.inputs.diagnostics.clear()
        errors: list[str] = []
        try:
            parameters = self.inputs.parameters()

            def windows() -> Iterator[GyroFftWindow]:
                return iter_gyro_fft_windows(self.log_data, parameters, self.inputs.settings, self.inputs.diagnostics)

            for source in self.inputs.sources(parameters):
                if isinstance(source, str):
                    errors.append(source)
                    continue
                try:
                    fit = fit_tracking_source(windows, source, self.inputs.settings)
                    values = fit.parameter_values(int(parameters[_PREFIX + "OPTS"]))
                    _validate_proposal(values, self.apm_doc or {})
                    return self._result(fit, values, errors)
                except ValueError as error:
                    errors.append(_("{source}: {reason}").format(source=source.name, reason=str(error)))
        except ValueError as error:
            errors.append(str(error))
        return LogAnalysisResult(available=False, outcomes=[], name=_("Automatic dynamic notch"), reason="; ".join(errors))

    def _result(self, fit: DynamicNotchFit, values: Mapping[str, int | float], errors: list[str]) -> LogAnalysisResult:
        group = _("First harmonic notch")
        outcomes = [
            LogAnalysis(
                _("Fitted {parameter} using {source}").format(parameter=name, source=fit.source),
                param_name=name,
                suggested_value=value,
                related_step=self.step_for_parameter(name),
                group=group,
            )
            for name, value in values.items()
        ]
        settings = self.inputs.settings
        outcomes.append(
            LogAnalysis(
                _(
                    "Fitted using {source}: {count} FFT windows, {start:.3f} to {end:.3f} s; "
                    "window size {size}, overlap {overlap}"
                ).format(
                    source=fit.source,
                    count=fit.window_count,
                    start=fit.start_time_s,
                    end=fit.end_time_s,
                    size=settings.fft_window_size,
                    overlap=settings.overlap,
                ),
                group=group,
            )
        )
        for harmonic, prominence in enumerate(fit.prominences_db, 1):
            if isfinite(prominence):
                outcomes.append(
                    LogAnalysis(
                        _("Harmonic {harmonic}: {prominence:.1f} dB above local noise floor").format(
                            harmonic=harmonic, prominence=prominence
                        ),
                        value=prominence,
                        group=group,
                    )
                )
        outcomes.extend(LogAnalysis(error, group=group) for error in errors)
        outcomes.extend(LogAnalysis(message, group=group) for message in dict.fromkeys(self.inputs.diagnostics))
        return LogAnalysisResult(
            available=True,
            outcomes=outcomes,
            name=_("Automatic dynamic notch"),
            reason=_("First harmonic notch fitted successfully"),
            related_step=self.step_for_parameter(_PREFIX + "FREQ"),
        )
