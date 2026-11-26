"""
Fit the first dynamic harmonic notch from in-memory pre-filter gyro batches.

The fitting rules follow FilterReview/AutoFit.js of the WebTools "filter-auto-fit" branch at commit
0f1b601607de0833a1c03a3ba7451c0dfb774950 (https://github.com/j-w9/webtools). The FFT and ESC/throttle
tracking adapters follow WebTools commit 7b98e0b21d3d3920f029a9f401269d912828ad67.
All returned parameters are proposals; this module never applies them.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

from collections.abc import Callable, Iterator, Mapping, Sequence
from dataclasses import dataclass, field
from itertools import accumulate, repeat, takewhile
from math import ceil, floor, inf, isfinite, sqrt
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
_PREFIX = "INS_HNTCH_"
_SUFFIXES = ("ENABLE", "MODE", "FREQ", "BW", "ATT", "REF", "FM_RAT", "HMNCS", "OPTS")
_INTERPRETATION_PREFIXES = ("INS_LOG_BAT_", "INS_GYR", "INS_HNTCH_", "FRAME_", "Q_ENABLE", "H_RSC_")

_MODE_THROTTLE = 1
_MODE_ESC = 3
_MODE_FFT = 4
_DOUBLE_NOTCH = 1
_MULTI_SOURCE = 2
_ALL_IMUS = 8
_TRIPLE_NOTCH = 16
_QUINTUPLE_NOTCH = 64
_FILTER_COUNT_WARNING_THRESHOLD = 24  # Default limit for F4 boards in ArduPilot 4.6.
_MAX_MOTOR_NOTCHES = 12
# Fitting rules, named as in WebTools' auto_fit_rules
_MIN_PEAK_DB = 6.0
_MIN_ATTENUATION_DB = 10
_MAX_ATTENUATION_DB = 50
_MAX_HARMONIC = 8
_PEAK_WIDTH = 0.1
_FLOOR_EXCLUDE = 0.12
_MIN_FREQUENCY_HZ = 10.0
_MIN_FREQUENCY_RATIO = 0.8
_LOW_PERCENTILE = 0.05
_BANDWIDTH_RATIO = 0.5
_ESC_CHECK_RATIO = 1.5
_ESC_ORDER_TOLERANCE = 0.05
_ESC_CHECK_RANGE = (0.5, 2.0)
_ESC_CHECK_STEP = 0.01
_ESC_GRID = (0.25, _MAX_HARMONIC + 0.75, 0.005)
_THROTTLE_GRID_STEP = 0.25
_CONFIDENCE_DB = (10.0, 20.0)
_CONFIDENCE_MARGIN = (1.0, 2.0)


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

    def values_at(self, times: FloatArray, max_gap_s: float) -> FloatArray:
        """Tracked value of each series at the times, as a (series, time) array, NaN where unavailable."""
        values = np.array([series.interpolate(times, max_gap_s) for series in self.samples], dtype=np.float64)
        values[values < 0] = np.nan
        return np.sqrt(values) if self.mode == _MODE_THROTTLE else values

    def mean_at(self, times: FloatArray, max_gap_s: float) -> FloatArray:
        """Mean of the series at the times, NaN unless every series is available."""
        return np.asarray(self.values_at(times, max_gap_s).mean(axis=0), dtype=np.float64)


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
    fit_margin: float | None
    window_count: int
    start_time_s: float
    end_time_s: float

    @property
    def strongest_prominence_db(self) -> float:
        """Prominence of the strongest harmonic above the local noise floor."""
        return max(self.prominences_db)

    def confidence(self) -> tuple[str, str]:
        """Rate the fit as low, medium or high and explain why."""
        level = sum(self.strongest_prominence_db >= threshold for threshold in _CONFIDENCE_DB)
        reason = _("strongest harmonic {excess} dB above the noise floor").format(
            excess=_js_round(self.strongest_prominence_db)
        )
        margin = self.fit_margin
        if margin is None:
            level = min(level, 1)
            reason += _(", throttle only approximates motor speed")
        else:
            level = min(level, sum(margin >= threshold for threshold in _CONFIDENCE_MARGIN))
            if margin < 0.95:
                reason += _(
                    ", the harmonics of another frequency fit the noise {ratio:.1f} times better "
                    "than those of the ESC frequency"
                ).format(ratio=1 / margin)
            elif margin <= 1.05:
                reason += _(", the ESC frequency harmonics fit the noise about as well as those of any other frequency")
            elif isfinite(margin):
                reason += _(
                    ", the ESC frequency harmonics fit the noise {ratio:.1f} times better than those of any other frequency"
                ).format(ratio=margin)
            else:
                reason += _(", the ESC frequency harmonics fit the noise better than those of any other frequency")
        return (_("low"), _("medium"), _("high"))[level], reason

    def parameter_values(self, existing_options: int) -> dict[str, int | float]:
        options = existing_options & ~(_DOUBLE_NOTCH | _TRIPLE_NOTCH | _QUINTUPLE_NOTCH | _MULTI_SOURCE)
        if self.multi_source:
            options |= _MULTI_SOURCE
        values = (
            1,
            self.mode,
            self.frequency_hz,
            _js_round(self.frequency_hz * _BANDWIDTH_RATIO),
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


def build_order_spectrum(windows: Sequence[GyroFftWindow], tracked: FloatArray, grid: FloatArray) -> OrderSpectrum:
    """
    Average linear power on a grid of multiples of the tracked value, then convert covered bins to dB.

    ``tracked`` holds the tracked value of each window; windows where it is not finite and positive are ignored.
    """
    total = np.zeros(grid.shape)
    counts = np.zeros(grid.shape, dtype=np.int64)
    accepted: list[int] = []
    for index, (window, value) in enumerate(zip(windows, tracked, strict=True)):
        if not isfinite(value) or value <= 0:
            continue
        accepted.append(index)
        frequencies = grid * value
        covered = frequencies < window.bins_hz[-1]
        power = np.interp(frequencies[covered], window.bins_hz, window.power)
        valid = np.isfinite(power) & (power > 0)
        positions = np.flatnonzero(covered)[valid]
        total[positions] += power[valid]
        counts[positions] += 1
    db = np.full(grid.shape, np.nan)
    covered = (counts > 0) & (counts >= len(accepted) * 0.5)
    db[covered] = 10 * np.log10(total[covered] / counts[covered])
    return OrderSpectrum(grid, db, tracked[accepted], np.array([windows[index].time_s for index in accepted]))


def harmonic_prominence(spectrum: OrderSpectrum, position: float, scale: float) -> float:
    """Peak above the upper median local floor; a boundary maximum is rejected."""
    step = float(spectrum.grid[1] - spectrum.grid[0])

    def index(value: float) -> int:
        return _js_round((value - float(spectrum.grid[0])) / step)

    start, end = index(position - scale * 0.5), index(position + scale * 0.5)
    if start < 0 or end >= len(spectrum.db) or not np.isfinite(spectrum.db[start : end + 1]).all():
        return -inf
    peak_start, peak_end = index(position - scale * _PEAK_WIDTH), index(position + scale * _PEAK_WIDTH)
    peak_values = spectrum.db[peak_start : peak_end + 1]
    maximum = int(np.argmax(peak_values))
    if maximum in (0, len(peak_values) - 1):
        return -inf
    floor_values = spectrum.db[start : end + 1][np.abs(spectrum.grid[start : end + 1] - position) > scale * _FLOOR_EXCLUDE]
    if len(floor_values) == 0:
        return -inf
    noise_floor = np.sort(floor_values)[len(floor_values) // 2]
    return float(peak_values[maximum] - noise_floor)


def _harmonic_prominences(spectrum: OrderSpectrum, fundamental: float) -> tuple[float, ...]:
    return tuple(
        harmonic_prominence(spectrum, fundamental * harmonic, fundamental) for harmonic in range(1, _MAX_HARMONIC + 1)
    )


def _strongest_peak(spectrum: OrderSpectrum, scale: float | None) -> tuple[float, float] | None:
    """Find the peak standing out most from its local floor; ``scale`` of None uses each peak's own position."""
    step = float(spectrum.grid[1] - spectrum.grid[0])
    best_position: float | None = None
    best_excess = -inf
    for index in range(10, len(spectrum.db) - 10):
        value = spectrum.db[index]
        if not isfinite(value) or np.any(spectrum.db[index - 10 : index + 11] > value):
            continue
        position = float(spectrum.grid[index])
        width = _js_round((position if scale is None else scale) * _PEAK_WIDTH / step)
        # The peak must also top the window its height is taken from, so a nearby noise maximum cannot borrow it
        if np.any(spectrum.db[max(0, index - width) : index + width + 1] > value):
            continue
        excess = harmonic_prominence(spectrum, position, position if scale is None else scale)
        if best_position is None or excess > best_excess:
            best_position, best_excess = position, excess
    return (best_position, best_excess) if best_position is not None and best_excess >= _MIN_PEAK_DB else None


def _select_harmonics(prominences: Sequence[float]) -> tuple[int, int] | None:
    """Return the harmonics bitmask and attenuation, or None if no harmonic stands out."""
    standing_out = [(harmonic, prominence) for harmonic, prominence in enumerate(prominences, 1) if prominence >= _MIN_PEAK_DB]
    if not standing_out:
        return None
    harmonics = sum(1 << (harmonic - 1) for harmonic, _prominence in standing_out)
    strongest = max(prominence for _harmonic, prominence in standing_out)
    return harmonics, _js_round(min(max(strongest, _MIN_ATTENUATION_DB), _MAX_ATTENUATION_DB))


def _grid(minimum: float, maximum: float, step: float) -> FloatArray:
    return minimum + step * np.arange(floor((maximum - minimum) / step) + 1, dtype=np.float64)


def _frequency_spectrum(windows: Sequence[GyroFftWindow], frequencies: FloatArray, grid: FloatArray) -> OrderSpectrum:
    """Order spectrum for motor frequencies, ignoring windows with the motors stopped."""
    return build_order_spectrum(windows, np.where(frequencies >= _MIN_FREQUENCY_HZ, frequencies, np.nan), grid)


def _harmonic_fit(spectra: Sequence[OrderSpectrum], fundamental: float) -> tuple[float, bool]:
    """Mean over spectra of how well the harmonics of a fundamental fit, and whether most show a fundamental peak."""
    scores = []
    with_fundamental = 0
    for spectrum in spectra:
        prominences = _harmonic_prominences(spectrum, fundamental)
        scores.append(sum(max(0.0, prominence) for prominence in prominences))
        with_fundamental += prominences[0] >= _MIN_PEAK_DB
    return sum(scores) / len(spectra), with_fundamental > len(spectra) / 2


def _esc_fit_margin(spectra: Sequence[OrderSpectrum]) -> float:
    """
    Check that the noise follows whole multiples of the ESC frequency.

    A wrongly scaled ESC frequency, for example by the motor poles, moves each motor's harmonics to the same other
    fundamental. Other motors at different speeds only line up at a ratio that differs from motor to motor, so the fit
    of each fundamental is averaged over the motor spectra. Returns how much better the ESC frequency fits than any
    other fundamental.
    """
    # Telemetry can be a little off, so the ESC frequency fit is the best within the tolerance
    logged_score = best_other_score = 0.0
    fundamentals = takewhile(
        lambda value: value <= _ESC_CHECK_RANGE[1], accumulate(repeat(_ESC_CHECK_STEP), initial=_ESC_CHECK_RANGE[0])
    )
    for fundamental in fundamentals:
        score, has_peak = _harmonic_fit(spectra, fundamental)
        if abs(fundamental - 1) <= _ESC_ORDER_TOLERANCE:
            logged_score = max(logged_score, score)
        elif has_peak:
            best_other_score = max(best_other_score, score)
    if best_other_score > logged_score * _ESC_CHECK_RATIO:
        raise ValueError(_("Noise does not follow whole multiples of the ESC frequency; check motor poles"))
    return logged_score / best_other_score if best_other_score > 0 else inf


def _fit_esc(windows: Sequence[GyroFftWindow], source: TrackingSource, settings: AutoDynamicNotchSettings) -> DynamicNotchFit:
    """The notch tracks the motor frequency, so its harmonics are whole multiples of it."""
    per_motor = source.values_at(np.array([window.time_s for window in windows]), settings.telemetry_gap_s)
    grid = _grid(*_ESC_GRID)
    mean_spectrum = _frequency_spectrum(windows, per_motor.mean(axis=0), grid)
    if len(mean_spectrum.tracked) == 0:
        raise ValueError(_("No FFT windows have tracking telemetry with motors running"))
    # The notch tracks each motor separately, and motors at different speeds spread the harmonics of the mean
    motor_spectra: list[OrderSpectrum] = []
    if source.multi_source:
        spectra = (_frequency_spectrum(windows, frequencies, grid) for frequencies in per_motor)
        motor_spectra = [spectrum for spectrum in spectra if len(spectrum.tracked) > 0]
    fit_margin = _esc_fit_margin(motor_spectra or [mean_spectrum])
    # A harmonic is used if it stands out for the mean or for any one motor
    prominences = tuple(
        float(prominence)
        for prominence in np.max(
            [_harmonic_prominences(spectrum, 1.0) for spectrum in (mean_spectrum, *motor_spectra)], axis=0
        )
    )
    selection = _select_harmonics(prominences)
    if selection is None:
        raise ValueError(_("No noise peaks follow the ESC frequency"))
    # A slow motor can be well below the mean
    lowest = _percentile(np.concatenate([spectrum.tracked for spectrum in motor_spectra or [mean_spectrum]]), _LOW_PERCENTILE)
    return DynamicNotchFit(
        source.name,
        _MODE_ESC,
        _js_round(lowest * _MIN_FREQUENCY_RATIO),
        1,
        1.0,
        source.multi_source,
        selection[0],
        selection[1],
        tuple(float(prominence) for prominence in prominences),
        fit_margin,
        len(mean_spectrum.tracked),
        float(np.min(mean_spectrum.times_s)),
        float(np.max(mean_spectrum.times_s)),
    )


def _mean_throttle(series: TrackingSamples, settings: AutoDynamicNotchSettings) -> float:
    """Mean throttle over the analysis interval, the reference at which the notch frequency is fitted."""
    start = settings.start_time_s if settings.start_time_s is not None else -inf
    end = settings.end_time_s if settings.end_time_s is not None else inf
    values = series.values[(series.time_s >= start) & (series.time_s <= end)]
    values = values[np.isfinite(values)]
    return float(np.mean(values)) if len(values) else float("nan")


def _fit_throttle(  # pylint: disable=too-many-locals
    windows: Sequence[GyroFftWindow], source: TrackingSource, settings: AutoDynamicNotchSettings
) -> DynamicNotchFit:
    """Fit FREQ in freq * sqrt(throttle / REF) with REF as the mean throttle, using one notch for the average throttle."""
    reference = _mean_throttle(source.samples[0], settings)
    # REF is set to two decimal places, zero would disable tracking
    if not isfinite(reference) or reference < 0.005:
        raise ValueError(_("Mean throttle is too low"))
    root_throttle = source.mean_at(np.array([window.time_s for window in windows]), settings.telemetry_gap_s)
    spectrum = build_order_spectrum(
        windows,
        root_throttle / sqrt(reference),
        _grid(_MIN_FREQUENCY_HZ, min(float(window.bins_hz[-1]) for window in windows), _THROTTLE_GRID_STEP),
    )
    if len(spectrum.tracked) == 0:
        raise ValueError(_("No FFT windows have tracking telemetry with motors running"))
    # The fundamental is the strongest peak, or the lowest whole fraction of it that also has a peak
    strongest = _strongest_peak(spectrum, None)
    if strongest is None:
        raise ValueError(_("No noise peaks follow throttle"))
    fundamental = strongest[0]
    for harmonic in (4, 3, 2):
        position = strongest[0] / harmonic
        if position >= _MIN_FREQUENCY_HZ * 2 and harmonic_prominence(spectrum, position, position) >= _MIN_PEAK_DB:
            fundamental = position
            break
    prominences = _harmonic_prominences(spectrum, fundamental)
    selection = _select_harmonics(prominences)
    if selection is None:
        raise ValueError(_("No noise peaks follow throttle"))
    # The frequency at the rounded reference is the same notch
    rounded_reference = _js_round(reference * 100) / 100
    frequency = fundamental * sqrt(rounded_reference / reference)
    # The notch frequency never goes below FREQ * FM_RAT. Keep that limit a little below the lowest frequency seen in
    # flight so the notch keeps tracking at low throttle. FM_RAT is between 0.1 and 1, rounded down to a multiple of 0.05.
    lowest = _percentile(spectrum.tracked, _LOW_PERCENTILE) * fundamental
    minimum_ratio = min(1.0, max(0.1, floor(lowest * _MIN_FREQUENCY_RATIO / frequency * 20) / 20))
    return DynamicNotchFit(
        source.name,
        _MODE_THROTTLE,
        _js_round(frequency),
        rounded_reference,
        minimum_ratio,
        multi_source=False,
        harmonics=selection[0],
        attenuation_db=selection[1],
        prominences_db=prominences,
        fit_margin=None,
        window_count=len(spectrum.tracked),
        start_time_s=float(np.min(spectrum.times_s)),
        end_time_s=float(np.max(spectrum.times_s)),
    )


def fit_tracking_source(
    windows: Sequence[GyroFftWindow], source: TrackingSource, settings: AutoDynamicNotchSettings
) -> DynamicNotchFit:
    """Fit one source, raising a translated ValueError when its tracking is rejected."""
    if source.mode not in (_MODE_THROTTLE, _MODE_ESC):
        raise ValueError(_("Only ESC RPM and throttle tracking are supported"))
    if not windows:
        raise ValueError(_("No complete pre-filter FFT windows in the analysis interval"))
    return (_fit_esc if source.mode == _MODE_ESC else _fit_throttle)(windows, source, settings)


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
        fields = metadata.get("fields", {})
        bounds = str(fields.get("Range", "")).split()
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
        raw_bits = fields.get("Bitmask")
        if not bits and raw_bits:
            bits = [item.partition(":")[0].strip() for item in raw_bits.split(",") if ":" in item]
        if bits and (int(value) != value or int(value) & ~sum(1 << bit for bit in {int(key) for key in bits})):
            raise ValueError(_("Fitted option bits for {name} are unsupported by this firmware").format(name=name))
    if values[_PREFIX + "FREQ"] <= 0 or values[_PREFIX + "BW"] <= 0 or values[_PREFIX + "REF"] <= 0:
        raise ValueError(_("Fitted frequency, bandwidth, and reference must be positive"))


def _estimated_motor_count(log_data: LogData, parameters: Mapping[str, float]) -> int:
    # Boot allocation uses the motor mask, even when INS_HNTCH_ESC_MASK selects fewer tracking sources.
    try:
        esc_count = len(np.unique(log_data.get_field("ESC", _instance_field(log_data, "ESC"), scaled=False)))
    except ValueError:
        esc_count = 0
    # SERVOx_FUNCTION codes for Motor1-8, Motor9-12 and Motor13-32.
    motor_functions = {
        value
        for name, value in parameters.items()
        if name.startswith("SERVO")
        and name.endswith("_FUNCTION")
        and (33 <= value <= 40 or 82 <= value <= 85 or 160 <= value <= 179)
    }
    return max(1, min(_MAX_MOTOR_NOTCHES, max(esc_count, len(motor_functions))))


def _estimated_filter_count(log_data: LogData, parameters: Mapping[str, float], proposal: Mapping[str, int | float]) -> int:
    """Estimate boot allocation for the fitted notch and any other logged notch."""
    motors = _estimated_motor_count(log_data, parameters)
    gyro_count = _gyro_count(log_data, parameters) or 3
    imus = sum(
        parameters.get("INS_USE" if index == 1 else f"INS_USE{index}", index <= gyro_count) > 0
        for index in range(1, max(3, gyro_count) + 1)
    )
    count = 0
    for prefix, values in ((_PREFIX, proposal), ("INS_HNTC2_", parameters)):
        if values.get(prefix + "ENABLE", 0) <= 0 and parameters.get("FFT_ENABLE", 0) <= 0:
            continue
        harmonics = values.get(prefix + "HMNCS", 0)
        options = values.get(prefix + "OPTS", 0)
        if not (isfinite(harmonics) and harmonics > 0 and isfinite(options) and options >= 0):
            continue
        options = int(options)
        sources = 1
        if options & _MULTI_SOURCE:
            sources = 3 if values.get(prefix + "MODE") == _MODE_FFT else motors
        if options & _DOUBLE_NOTCH:
            composite = 2
        elif options & _TRIPLE_NOTCH:
            composite = 3
        else:
            composite = 5 if options & _QUINTUPLE_NOTCH else 1
        count += int(harmonics).bit_count() * sources * composite * (max(1, imus) if options & _ALL_IMUS else 1)
    return count


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
            lambda: _average_throttle_source(self.log_data, parameters),
        )
        for factory in factories:
            try:
                yield factory()
            except ValueError as error:
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
            times = np.array(
                [window.time_s for window in iter_gyro_fft_windows(self.log_data, parameters, self.inputs.settings)]
            )
            usable = any(
                np.any(source.mean_at(times, self.inputs.settings.telemetry_gap_s) > 0) for source in sources if len(times)
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
    """Fit ESC RPM, then average throttle, without applying changes."""

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
            windows = tuple(iter_gyro_fft_windows(self.log_data, parameters, self.inputs.settings, self.inputs.diagnostics))

            for source in self.inputs.sources(parameters):
                if isinstance(source, str):
                    errors.append(source)
                    continue
                try:
                    fit = fit_tracking_source(windows, source, self.inputs.settings)
                    values = fit.parameter_values(int(parameters[_PREFIX + "OPTS"]))
                    _validate_proposal(values, self.apm_doc or {})
                    return self._result(fit, values, _estimated_filter_count(self.log_data, parameters, values), errors)
                except ValueError as error:
                    errors.append(_("{source}: {reason}").format(source=source.name, reason=str(error)))
        except ValueError as error:
            errors.append(str(error))
        return LogAnalysisResult(available=False, outcomes=[], name=_("Automatic dynamic notch"), reason="; ".join(errors))

    def _result(
        self, fit: DynamicNotchFit, values: Mapping[str, int | float], filter_count: int, errors: list[str]
    ) -> LogAnalysisResult:
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
        confidence, confidence_reason = fit.confidence()
        outcomes.append(
            LogAnalysis(
                _("Fitted using {source}, {confidence} confidence: {reason}").format(
                    source=fit.source, confidence=confidence, reason=confidence_reason
                ),
                group=group,
            )
        )
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
        if filter_count > _FILTER_COUNT_WARNING_THRESHOLD:
            outcomes.append(
                LogAnalysis(
                    _(
                        "The proposed configuration is estimated to allocate {count} notch filters. "
                        "Some flight controllers support only {limit}. Check your board and firmware limit "
                        "before uploading. Exceeding it can prevent the flight controller from starting."
                    ).format(count=filter_count, limit=_FILTER_COUNT_WARNING_THRESHOLD),
                    group=group,
                    severity="warning",
                )
            )
        return LogAnalysisResult(
            available=True,
            outcomes=outcomes,
            name=_("Automatic dynamic notch"),
            reason=_("First harmonic notch fitted successfully"),
            related_step=self.step_for_parameter(_PREFIX + "FREQ"),
            apply_together=True,
        )
