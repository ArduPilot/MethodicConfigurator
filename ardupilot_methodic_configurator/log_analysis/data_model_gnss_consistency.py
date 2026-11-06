"""
GPS kinematics, inertial motion and EKF consistency checks over parsed logs.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

from dataclasses import dataclass, field

import numpy as np

from ardupilot_methodic_configurator import _
from ardupilot_methodic_configurator.log_analysis.data_model_gnss_samples import (
    SensorSeries,
    aligned_values,
    continuous_slices,
    event_intervals,
    sensor_series,
)
from ardupilot_methodic_configurator.log_analysis.data_model_log_analysis_result import LogAnalysis
from ardupilot_methodic_configurator.log_analysis.data_model_log_data import LogData
from ardupilot_methodic_configurator.log_analysis.data_model_parameter_history import ParameterHistory

_GRAVITY = 9.80665
_EARTH_RADIUS_M = 6371000.0


def _finite(series: SensorSeries) -> np.ndarray:
    return np.asarray(np.all([np.isfinite(values) for values in series.fields.values()], axis=0), dtype=bool)


def _gps_fix(series: SensorSeries) -> np.ndarray:
    """Reject unknown and fractional fix codes before comparing physical motion."""
    status = series.fields["Status"]
    return np.asarray(_finite(series) & (status >= 3) & (status <= 6) & (status == np.floor(status)), dtype=bool)


def _velocity(series: SensorSeries) -> np.ndarray:
    """Ground course is a velocity direction, not vehicle heading."""
    course = np.deg2rad(series.fields["GCrs"])
    return np.column_stack((series.fields["Spd"] * np.cos(course), series.fields["Spd"] * np.sin(course)))


def _body_to_ned(acceleration: np.ndarray, attitude_deg: np.ndarray) -> np.ndarray:
    """Rotate specific force into NED using roll/pitch/yaw and add downwards gravity."""
    roll, pitch, yaw = np.deg2rad(attitude_deg).T
    cr, sr, cp, sp, cy, sy = np.cos(roll), np.sin(roll), np.cos(pitch), np.sin(pitch), np.cos(yaw), np.sin(yaw)
    ax, ay, az = acceleration.T
    return np.column_stack(
        (
            cp * cy * ax + (sr * sp * cy - cr * sy) * ay + (cr * sp * cy + sr * sy) * az,
            cp * sy * ax + (sr * sp * sy + cr * cy) * ay + (cr * sp * sy - sr * cy) * az,
            -sp * ax + sr * cp * ay + cr * cp * az + _GRAVITY,
        )
    )


def _interpolate(series: SensorSeries, times: np.ndarray, fields: tuple[str, ...], max_gap_s: float) -> np.ndarray:
    """Interpolate only inside continuous valid segments; unwrap attitude angles first."""
    result = np.full((len(times), len(fields)), np.nan)
    if np.any(np.diff(series.times) < 0):
        return result
    valid = np.all([np.isfinite(series.fields[name]) for name in fields], axis=0)
    for section in continuous_slices(series.times, valid, max_gap_s):
        sample_times = series.times[section]
        if len(sample_times) < 2:
            continue
        mask = (times >= sample_times[0]) & (times <= sample_times[-1])
        for column, name in enumerate(fields):
            values = series.fields[name][section]
            if name in ("Roll", "Pitch", "Yaw"):
                values = np.rad2deg(np.unwrap(np.deg2rad(values)))
            result[mask, column] = np.interp(times[mask], sample_times, values)
    return result


@dataclass(frozen=True)
class _MotionSamples:
    gps: SensorSeries
    velocity: np.ndarray
    auxiliary: dict[str, np.ndarray]
    vertical: SensorSeries | None


@dataclass(frozen=True)
class _InertialTrack:
    """One IMU's disjoint continuous segments indexed by their start time."""

    starts: np.ndarray
    segments: tuple[SensorSeries, ...]


def _prediction_residual(tracks: list[_InertialTrack], times: np.ndarray, delta_velocity: np.ndarray) -> float:
    """Return the smallest discrepancy among healthy IMUs at one allowed receiver lag."""
    if times[1] <= times[0] or not np.isfinite(delta_velocity).all():
        return float("nan")
    residuals: list[float] = []
    for track in tracks:
        index = int(np.searchsorted(track.starts, times[0], side="right")) - 1
        if index < 0:
            continue
        segment = track.segments[index]
        if times[1] > segment.times[-1]:
            continue
        integral = np.column_stack([np.interp(times, segment.times, segment.fields[name]) for name in ("VN", "VE", "VD")])
        predicted = np.diff(integral, axis=0)[0, : len(delta_velocity)]
        residuals.append(float(np.linalg.norm(delta_velocity - predicted)))
    return min(residuals) if residuals else float("nan")


@dataclass
class GnssConsistencyChecks:
    """Deterministic checks with explicit coverage and conservative diagnostic limits."""

    log_data: LogData
    parameters: dict[str, float]
    parameter_history: ParameterHistory | None = None
    coverage: list[LogAnalysis] = field(default_factory=list)

    def parameter(self, name: str, time_s: float) -> float | None:
        """Use the logged value at the event, rather than a later parameter change."""
        if self.parameter_history is not None:
            return self.parameter_history.value_at(name, time_s)
        return self.parameters.get(name)

    def analyse(self) -> list[LogAnalysis]:
        outcomes: list[LogAnalysis] = []
        for check in (
            self.check_gps_quality,
            self.check_gps_clock,
            self.check_position_velocity,
            self.check_altitude_velocity,
            self.check_inertial_motion,
            self.check_ekf,
        ):
            outcomes.extend(check())
        return outcomes + self.coverage

    def _coverage(self, source: str, count: int, total: int, detail: str = "") -> None:
        self.coverage.append(
            LogAnalysis(
                _("{source}: evaluated {count}/{total} samples or intervals. {detail}").format(
                    source=source, count=count, total=total, detail=detail
                ),
                source=source,
                severity="informational",
                group=_("Coverage"),
                evidence={"evaluated": float(count), "total": float(total)},
            )
        )

    def _events(  # pylint: disable=too-many-arguments,too-many-positional-arguments
        self,
        series: SensorSeries,
        levels: np.ndarray,
        source: str,
        message: str,
        measurements: dict[str, np.ndarray] | None = None,
        minimum_duration_s: float = 0.0,
        bitmask_fields: tuple[str, ...] = (),
    ) -> list[LogAnalysis]:
        outcomes: list[LogAnalysis] = []
        for start, end, _level in event_intervals(series.times, levels):
            if series.times[end] - series.times[start] < minimum_duration_s:
                continue
            evidence = {
                name: float(np.bitwise_or.reduce(values[start : end + 1].astype(np.uint16), keepdims=True)[0])
                if name in bitmask_fields
                else float(np.nanmax(values[start : end + 1]))
                for name, values in (measurements or {}).items()
                if np.isfinite(values[start : end + 1]).any()
            }
            identity = str(series.instance) if series.instance is not None else _("unknown")
            outcomes.append(
                LogAnalysis(
                    _("{source}, sensor {identity}: {message}").format(source=source, identity=identity, message=message),
                    timestamp_us=float(series.times[start] * 1e6),
                    end_timestamp_us=float(series.times[end] * 1e6),
                    source=source,
                    instance=series.instance,
                    severity="warning",
                    evidence=evidence,
                    group=_("GNSS consistency"),
                )
            )
        return outcomes

    def _auxiliary(self, gps: SensorSeries, fields: tuple[str, ...]) -> dict[str, np.ndarray]:
        """Align GPA states only to the matching receiver and with a bounded age."""
        result = {name: np.full(gps.times.shape, np.nan) for name in fields}
        for name in fields:
            for auxiliary in sensor_series(self.log_data, "GPA", (name,)):
                if auxiliary.instance == gps.instance:
                    result[name] = aligned_values(auxiliary, gps.times, name, 0.5)
        return result

    def check_gps_quality(self) -> list[LogAnalysis]:
        outcomes: list[LogAnalysis] = []
        total = count = 0
        for series in sensor_series(self.log_data, "GPS", ("Status",)):
            valid = _finite(series) & (series.fields["Status"] >= 0) & (series.fields["Status"] <= 6)
            valid &= series.fields["Status"] == np.floor(series.fields["Status"])
            levels = np.full(series.times.shape, np.nan)
            for section in continuous_slices(series.times, valid, 2.0):
                fixed = False
                for index in range(section.start, section.stop):
                    fixed = fixed or series.fields["Status"][index] >= 3
                    levels[index] = float(fixed and series.fields["Status"][index] < 3)
            outcomes.extend(self._events(series, levels, "GPS.Status", _("GPS lost its 3D fix after acquiring a fix")))
            count += int(np.count_nonzero(np.isfinite(levels)))
            total += len(series.times)
        self._coverage(
            "GPS.Status",
            count,
            total,
            _("Startup acquisition and recovery after long gaps are excluded from fix-loss warnings."),
        )
        return outcomes + self._quality_trends()

    def _quality_trends(self) -> list[LogAnalysis]:
        outcomes: list[LogAnalysis] = []
        # Quality deterioration is contextual evidence, never sufficient for an attack claim.
        for name, source in (("NSats", "GPS.NSats"), ("HDop", "GPS.HDop")):
            for series in sensor_series(self.log_data, "GPS", (name, "Status")):
                values = series.fields[name]
                levels = np.full(values.shape, np.nan)
                valid = _gps_fix(series) & (values > 0)
                for section in continuous_slices(series.times, valid, 2.0):
                    for index in range(section.start + 5, section.stop):
                        left = max(section.start, index - 20)
                        baseline = float(np.median(values[left:index]))
                        degraded = (
                            values[index] < baseline * 0.5 and baseline >= 8
                            if name == "NSats"
                            else values[index] > max(3.0, baseline * 4.0)
                        )
                        levels[index] = float(degraded)
                outcomes.extend(
                    self._events(
                        series,
                        levels,
                        source,
                        _("GPS quality deteriorated relative to preceding samples"),
                        {name: values},
                        0.5,
                    )
                )
        return outcomes

    def check_gps_clock(self) -> list[LogAnalysis]:
        outcomes: list[LogAnalysis] = []
        total = count = 0
        for series in sensor_series(self.log_data, "GPS", ("GWk", "GMS", "Status")):
            # GMS is canonical seconds (FMTU applies 0.001 to milliseconds).
            week, tow = series.fields["GWk"], series.fields["GMS"]
            clock = week * 604800.0 + tow
            valid = (
                _finite(series)
                & (week > 0)
                & (week == np.floor(week))
                & (tow >= 0)
                & (tow < 604800)
                & (series.fields["Status"] >= 3)
            )
            residual = np.full(clock.shape, np.nan)
            for section in continuous_slices(series.times, valid, 2.0):
                for index in range(section.start + 1, section.stop):
                    left = section.start + int(np.searchsorted(series.times[section], series.times[index] - 5.0))
                    left = min(left, index - 1)
                    residual[index] = abs((clock[index] - clock[left]) - (series.times[index] - series.times[left]))
            levels = np.where(np.isfinite(residual), (residual > 1.0).astype(float), np.nan)
            outcomes.extend(
                self._events(
                    series,
                    levels,
                    "GPS.Clock",
                    _("GPS clock progression disagrees with the boot clock"),
                    {"clock_residual_s": residual},
                )
            )
            count += int(np.count_nonzero(np.isfinite(residual)))
            total += max(0, len(clock) - 1)
        self._coverage("GPS.Clock", count, total, _("GPS week rollover is included; boot timestamps determine event time."))
        return outcomes

    def check_position_velocity(self) -> list[LogAnalysis]:  # pylint: disable=too-many-locals
        outcomes: list[LogAnalysis] = []
        total = count = 0
        for series in sensor_series(self.log_data, "GPS", ("Lat", "Lng", "Spd", "GCrs", "Status")):
            latitude, longitude = series.fields["Lat"], series.fields["Lng"]
            valid = (
                _gps_fix(series)
                & (np.abs(latitude) <= 90)
                & (np.abs(longitude) <= 180)
                & (series.fields["Status"] >= 3)
                & (series.fields["Spd"] >= 0)
            )
            velocity = _velocity(series)
            residual = np.full(series.times.shape, np.nan)
            accuracy = self._auxiliary(series, ("HAcc",))["HAcc"]
            tolerance = np.full(series.times.shape, 10.0)
            for section in continuous_slices(series.times, valid, 2.0):
                if section.stop - section.start < 2:
                    continue
                dt = np.diff(series.times[section])
                lat = np.deg2rad(latitude[section])
                lon = np.deg2rad(longitude[section])
                dlon = (np.diff(lon) + np.pi) % (2 * np.pi) - np.pi
                displacement = _EARTH_RADIUS_M * np.column_stack((np.diff(lat), dlon * np.cos((lat[1:] + lat[:-1]) / 2)))
                expected = (velocity[section][1:] + velocity[section][:-1]) * dt[:, None] / 2
                target = slice(section.start + 1, section.stop)
                residual[target] = np.linalg.norm(displacement - expected, axis=1)
                pair_accuracy = accuracy[section][1:] + accuracy[section][:-1]
                tolerance[target] = np.maximum(
                    10.0, np.where(np.isfinite(pair_accuracy) & (pair_accuracy > 0), 3 * pair_accuracy, 0)
                )
            levels = np.where(np.isfinite(residual), (residual > tolerance).astype(float), np.nan)
            outcomes.extend(
                self._events(
                    series,
                    levels,
                    "GPS.PositionVelocity",
                    _("GPS position change disagrees with reported velocity"),
                    {"residual_m": residual, "tolerance_m": tolerance},
                )
            )
            count += int(np.count_nonzero(np.isfinite(residual)))
            total += max(0, len(series.times) - 1)
        self._coverage(
            "GPS.PositionVelocity", count, total, _("Longitude wrap and reported position uncertainty are accounted for.")
        )
        return outcomes

    def _inertial_segments(self) -> list[_InertialTrack]:  # pylint: disable=too-many-locals
        attitudes = sensor_series(self.log_data, "ATT", ("Roll", "Pitch", "Yaw"))
        if len(attitudes) != 1:
            return []
        tracks: list[_InertialTrack] = []
        for imu in sensor_series(self.log_data, "IMU", ("AccX", "AccY", "AccZ", "GyrX", "GyrY", "GyrZ")):
            valid_times = imu.times[np.isfinite(imu.times) & (imu.times >= 0)]
            if np.any(np.diff(valid_times) < 0):
                continue  # Repeated boot epochs cannot be matched to GPS unambiguously.
            segments: list[SensorSeries] = []
            attitude = _interpolate(attitudes[0], imu.times, ("Roll", "Pitch", "Yaw"), 0.25)
            valid = _finite(imu) & np.isfinite(attitude).all(axis=1)
            # Large rotations make unknown antenna/IMU lever arms significant.
            rotation = np.column_stack([imu.fields[name] for name in ("GyrX", "GyrY", "GyrZ")])
            valid &= np.linalg.norm(rotation, axis=1) < 0.5
            for name, healthy in (("AH", 1), ("GH", 1), ("EA", 0), ("EG", 0)):
                matched = False
                for health in sensor_series(self.log_data, "IMU", (name,)):
                    if health.instance == imu.instance:
                        matched = True
                        valid &= aligned_values(health, imu.times, name, 0.2) == healthy
                if not matched and name in ("AH", "GH"):
                    valid &= False
            valid &= self._unclipped_samples(imu)
            acceleration = _body_to_ned(np.column_stack([imu.fields[name] for name in ("AccX", "AccY", "AccZ")]), attitude)
            for section in continuous_slices(imu.times, valid, 0.2):
                times = np.ascontiguousarray(imu.times[section])
                if len(times) < 3:
                    continue
                increments = (acceleration[section][1:] + acceleration[section][:-1]) * np.diff(times)[:, None] / 2
                # Each axis must be contiguous: np.interp otherwise copies the
                # entire history for every GPS interval and candidate latency.
                integral = np.ascontiguousarray(np.vstack((np.zeros(3), np.cumsum(increments, axis=0))).T)
                segments.append(
                    SensorSeries(imu.instance, {"TimeUS": times, "VN": integral[0], "VE": integral[1], "VD": integral[2]})
                )
            if segments:
                tracks.append(_InertialTrack(np.array([segment.times[0] for segment in segments]), tuple(segments)))
        return tracks

    def _unclipped_samples(self, imu: SensorSeries) -> np.ndarray:
        """Exclude the whole counter-increment interval, including low-rate VIBE logs."""
        valid = np.ones(imu.times.shape, dtype=bool)
        sources = [(item, "Clip") for item in sensor_series(self.log_data, "VIBE", ("Clip",)) if item.instance == imu.instance]
        if imu.instance is not None:
            name = f"Clip{imu.instance}"
            sources.extend((item, name) for item in sensor_series(self.log_data, "VIBE", (name,)))
        indices = np.flatnonzero(np.isfinite(imu.times) & (imu.times >= 0))
        times = imu.times[indices]
        for vibration, name in sources:
            finite_times = vibration.times[np.isfinite(vibration.times) & (vibration.times >= 0)]
            if np.any(np.diff(finite_times) < 0):
                return np.zeros(imu.times.shape, dtype=bool)
            starts, ends = vibration.times[:-1], vibration.times[1:]
            increments = np.diff(vibration.fields[name])
            clipped = (increments > 0) & np.isfinite(increments)
            clipped &= np.isfinite(starts) & np.isfinite(ends) & (starts >= 0) & (ends > starts)
            boundaries = np.zeros(len(times) + 1, dtype=int)
            np.add.at(boundaries, np.searchsorted(times, starts[clipped], side="left"), 1)
            np.add.at(boundaries, np.searchsorted(times, ends[clipped], side="right"), -1)
            valid[indices] &= np.cumsum(boundaries[:-1]) == 0
        return valid

    def check_altitude_velocity(self) -> list[LogAnalysis]:
        """Compare relative GPS altitude changes with down-positive vertical velocity."""
        outcomes: list[LogAnalysis] = []
        count = total = 0
        for series in sensor_series(self.log_data, "GPS", ("Alt", "VZ", "Status")):
            auxiliary = self._auxiliary(series, ("VV", "VAcc"))
            valid = _gps_fix(series) & (auxiliary["VV"] == 1)
            residual = np.full(series.times.shape, np.nan)
            tolerance = np.full(series.times.shape, 10.0)
            for section in continuous_slices(series.times, valid, 2.0):
                target = slice(section.start + 1, section.stop)
                residual[target] = np.abs(
                    np.diff(series.fields["Alt"][section])
                    + (series.fields["VZ"][section][1:] + series.fields["VZ"][section][:-1])
                    * np.diff(series.times[section])
                    / 2
                )
                accuracy = auxiliary["VAcc"][section][1:] + auxiliary["VAcc"][section][:-1]
                tolerance[target] = np.maximum(10.0, np.where(np.isfinite(accuracy) & (accuracy > 0), 3 * accuracy, 0))
            levels = np.where(np.isfinite(residual), (residual > tolerance).astype(float), np.nan)
            outcomes.extend(
                self._events(
                    series,
                    levels,
                    "GPS.AltitudeVelocity",
                    _("GPS altitude change disagrees with reported vertical velocity"),
                    {"residual_m": residual, "tolerance_m": tolerance},
                )
            )
            count += int(np.count_nonzero(np.isfinite(residual)))
            total += max(0, len(series.times) - 1)
        self._coverage("GPS.AltitudeVelocity", count, total, _("Requires receiver vertical velocity availability."))
        return outcomes

    def _motion_pair(self, samples: _MotionSamples, index: int, tracks: list[_InertialTrack]) -> tuple[float, float]:
        """Compare one short GPS interval with continuous inertial integration at plausible latencies."""
        pair = slice(index - 1, index + 1)
        times = samples.gps.times[pair].copy()
        if times[1] - times[0] < 0.1:
            return float("nan"), 3.0
        arrival = samples.auxiliary["SMS"][pair]
        if np.isfinite(arrival).all() and np.all((times - arrival >= 0) & (times - arrival <= 0.5)):
            times = arrival
        delay = (
            self.parameter(f"GPS{samples.gps.instance + 1}_DELAY_MS", samples.gps.times[index])
            if samples.gps.instance is not None
            else None
        )
        if delay is None:
            delay = self.parameter("GPS_DELAY_MS", samples.gps.times[index])
        lags = np.array([delay / 1000]) if delay is not None and 0 < delay <= 500 else np.linspace(0, 0.5, 6)
        delta_velocity = samples.velocity[index] - samples.velocity[index - 1]
        if samples.vertical is not None and np.all(samples.auxiliary["VV"][pair] == 1):
            delta_velocity = np.append(delta_velocity, np.diff(samples.vertical.fields["VZ"][pair])[0])
        residuals = np.array([_prediction_residual(tracks, times - lag, delta_velocity) for lag in lags])
        uncertainty = samples.auxiliary["SAcc"][pair]
        tolerance = 3.0 + (3 * float(uncertainty.sum()) if np.isfinite(uncertainty).all() and np.all(uncertainty > 0) else 0.0)
        return (float(np.nanmin(residuals)) if np.isfinite(residuals).any() else float("nan")), tolerance

    def check_inertial_motion(self) -> list[LogAnalysis]:
        tracks = self._inertial_segments()
        outcomes: list[LogAnalysis] = []
        total = count = 0
        for gps in sensor_series(self.log_data, "GPS", ("Spd", "GCrs", "Status")):
            total += max(0, len(gps.times) - 1)
            valid_times = gps.times[np.isfinite(gps.times) & (gps.times >= 0)]
            if np.any(np.diff(valid_times) < 0):
                continue  # Repeated GPS boot epochs cannot be matched to IMU unambiguously.
            valid = _gps_fix(gps) & (gps.fields["Spd"] >= 0)
            samples = _MotionSamples(
                gps,
                _velocity(gps),
                self._auxiliary(gps, ("SAcc", "SMS", "VV")),
                next((item for item in sensor_series(self.log_data, "GPS", ("VZ",)) if item.instance == gps.instance), None),
            )
            residual = np.full(gps.times.shape, np.nan)
            tolerance = np.full(gps.times.shape, 3.0)
            for section in continuous_slices(gps.times, valid, 2.0):
                for index in range(section.start + 1, section.stop):
                    residual[index], tolerance[index] = self._motion_pair(samples, index, tracks)
            levels = np.where(np.isfinite(residual), (residual > tolerance).astype(float), np.nan)
            outcomes.extend(
                self._events(
                    gps,
                    levels,
                    "GPS.IMU",
                    _("GPS velocity change disagrees with gravity-corrected IMU motion"),
                    {"residual_m_s": residual, "tolerance_m_s": tolerance},
                    0.5,
                )
            )
            count += int(np.count_nonzero(np.isfinite(residual)))
        self._coverage(
            "GPS.IMU",
            count,
            total,
            _(
                "Short windows, healthy IMUs, low rotation and continuous attitude required. "
                "Automatic receiver latency is tested over 0-0.5 s; attitude may itself be GPS-aided. "
                "GPS series with reversed boot timestamps are excluded."
            ),
        )
        return outcomes

    def check_ekf(self) -> list[LogAnalysis]:
        """Keep every lane separate and identify lane activity and receiver selection."""
        outcomes: list[LogAnalysis] = []
        for message in ("XKF4", "NKF4"):
            outcomes.extend(self._ekf_ratios(message))
            outcomes.extend(self._ekf_discontinuities(message))
        return outcomes

    def _ekf_source(self, series: SensorSeries, message: str, suffix: str) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        eligible = np.zeros(series.times.shape, dtype=bool)
        source_sets = np.full(series.times.shape, np.nan)
        receiver = np.full(series.times.shape, np.nan)
        if message == "NKF4":
            eligible = np.array(
                [
                    self.parameter("EK2_GPS_TYPE", time) in ((0, 1, 2) if suffix == "POSXY" else (0, 1))
                    if np.isfinite(time)
                    else False
                    for time in series.times
                ]
            )
            return eligible, source_sets, receiver
        for selection in sensor_series(self.log_data, "XKFS", ("SS",)):
            if selection.instance == series.instance:
                source_sets = aligned_values(selection, series.times, "SS", 2.0)
        for selection in sensor_series(self.log_data, "XKFS", ("GI",)):
            if selection.instance == series.instance:
                receiver = aligned_values(selection, series.times, "GI", 2.0)
        receiver = np.where((receiver >= 0) & (receiver <= 255) & (receiver == np.floor(receiver)), receiver, np.nan)
        for index in np.flatnonzero(np.isfinite(series.times)):
            eligible[index] = self._ekf3_uses_gps(suffix, float(series.times[index]), float(source_sets[index]))
        return eligible, source_sets, receiver

    def _ekf3_uses_gps(self, suffix: str, time_s: float, source_set: float) -> bool:
        """Mirror GPS source eligibility, including timestamped FuseAllVelocities."""
        options = self.parameter("EK3_SRC_OPTIONS", time_s)
        if options is not None:
            valid_options = np.isfinite(options) and options >= 0 and options == np.floor(options)
            if suffix == "VELXY" and valid_options and int(options) & 1:
                return any(self.parameter(f"EK3_SRC{index}_VELXY", time_s) == 3 for index in (1, 2, 3))
        return source_set in (0, 1, 2) and self.parameter(f"EK3_SRC{int(source_set) + 1}_{suffix}", time_s) == 3

    def ekf_gps_evidence(self, series: SensorSeries, message: str) -> np.ndarray:
        """Identify rows whose timestamped position or velocity source uses GPS."""
        position, _sets, _receiver = self._ekf_source(series, message, "POSXY")
        velocity, _sets, _receiver = self._ekf_source(series, message, "VELXY")
        # XKFS.GI is logged even during non-GPS navigation; it identifies a
        # receiver but cannot establish that GPS fusion is configured.
        return np.asarray(position | velocity, dtype=bool)

    def _ekf_ratios(self, message: str) -> list[LogAnalysis]:  # pylint: disable=too-many-locals
        outcomes: list[LogAnalysis] = []
        count = total = 0
        for ratio, suffix in (("SV", "VELXY"), ("SP", "POSXY")):
            for series in sensor_series(self.log_data, message, ("PI", ratio)):
                if series.instance is None:
                    continue
                eligible, source_sets, receiver = self._ekf_source(series, message, suffix)
                primary = (series.fields["PI"] == series.instance).astype(float)
                values = series.fields[ratio]
                valid = _finite(series) & eligible & (values >= 0)
                valid &= (
                    (series.fields["PI"] >= 0)
                    & (series.fields["PI"] <= 255)
                    & (series.fields["PI"] == np.floor(series.fields["PI"]))
                )
                # Break event intervals at primary-lane, source-set or receiver changes.
                identity = 1 + primary + 2 * np.nan_to_num(source_sets) + 8 * (np.nan_to_num(receiver, nan=-1) + 1)
                levels = np.where(valid, np.where(values > 1.0, identity, 0.0), np.nan)
                measurements = {"test_ratio": values, "active_primary": primary, "gps_receiver": receiver}
                innovation_fields = ("IVN", "IVE") if ratio == "SV" else ("IPN", "IPE")
                for innovation in sensor_series(self.log_data, message.replace("4", "3"), innovation_fields):
                    if innovation.instance == series.instance:
                        measurements["innovation_norm"] = np.hypot(
                            *(aligned_values(innovation, series.times, name, 0.5) for name in innovation_fields)
                        )
                outcomes.extend(
                    self._events(
                        series,
                        levels,
                        f"{message}.{ratio}",
                        _(
                            "EKF lane velocity innovation gate exceeded while GPS velocity fusion is configured; "
                            "other velocity sources may contribute; active_primary identifies lane activity"
                        )
                        if ratio == "SV"
                        else _("EKF lane GPS position innovation gate exceeded; active_primary identifies lane activity"),
                        measurements,
                        0.5,
                    )
                )
                count += int(np.count_nonzero(np.isfinite(levels)))
                total += len(series.times)
        self._coverage(
            f"{message}.SV/SP",
            count,
            total,
            _("Every logged lane is checked independently; GPS source selection is required. EKF evidence is GPS-aided."),
        )
        return outcomes

    def _gps_timeouts(self, series: SensorSeries, message: str) -> np.ndarray:
        """Retain only position/velocity timeout bits whose navigation source uses GPS."""
        values = series.fields["TS"]
        valid = np.isfinite(values) & (values >= 0) & (values <= 255) & (values == np.floor(values))
        masks = np.where(valid, values, 0).astype(np.uint8)
        relevant = np.zeros(values.shape, dtype=np.uint8)
        for bit, suffix in ((1, "POSXY"), (2, "VELXY")):
            eligible, _sets, _receivers = self._ekf_source(series, message, suffix)
            relevant |= np.where(eligible, bit, 0).astype(np.uint8)
        return np.where(valid, masks & relevant, np.nan)

    def _ekf_startup(self, series: SensorSeries, message: str) -> np.ndarray:
        """Recognize initialization per lane/boot without treating an existing outage as startup."""
        startup = np.zeros(series.times.shape, dtype=bool)
        for status in sensor_series(self.log_data, message, ("SS",)):
            if status.instance != series.instance:
                continue
            states = status.fields["SS"]
            valid = np.isfinite(states) & (states >= 0) & (states <= 4294967295) & (states == np.floor(states))
            masks = np.where(valid, states, 0).astype(np.uint32)
            uninitialized = np.zeros(series.times.shape, dtype=bool)
            for faults in sensor_series(self.log_data, message, ("FS",)):
                if faults.instance == series.instance:
                    values = faults.fields["FS"]
                    valid_faults = np.isfinite(values) & (values >= 0) & (values <= 65535) & (values == np.floor(values))
                    uninitialized = valid_faults & ((np.where(valid_faults, values, 0).astype(np.uint16) & 128) != 0)
            # HORIZ_POS_ABS or USING_GPS establishes aiding; CONST_POS_MODE and
            # NOT_INITIALISED identify startup. INITIALIZED rules out an existing outage.
            aided = valid & ((masks & (16 | 8192)) != 0)
            for section in continuous_slices(series.times, valid, float("inf")):
                first = section.start
                if (uninitialized[first] or (masks[first] & 128) != 0) and not aided[first] and (masks[first] & 65536) == 0:
                    startup[section] = ~np.maximum.accumulate(aided[section])
        return startup

    def _ekf_discontinuities(self, message: str) -> list[LogAnalysis]:  # pylint: disable=too-many-locals
        outcomes: list[LogAnalysis] = []
        for field_name in ("OFN", "OFE", "FS", "TS", "GPS"):
            count = total = 0
            for series in sensor_series(self.log_data, message, ("PI", field_name)):
                total += len(series.times)
                if series.instance is None:
                    continue
                primary = (series.fields["PI"] == series.instance).astype(float)
                levels = np.full(series.times.shape, np.nan)
                values = self._gps_timeouts(series, message) if field_name == "TS" else series.fields[field_name]
                gps_evidence = self.ekf_gps_evidence(series, message)
                startup = self._ekf_startup(series, message)
                if field_name == "FS":
                    valid_faults = np.isfinite(values) & (values >= 0) & (values <= 65535) & (values == np.floor(values))
                    masks = np.where(valid_faults, values, 0).astype(np.uint16)
                    # Only NOT_INITIALISED is expected during startup; numerical
                    # or sensor faults must warn even before aiding is established.
                    values = np.where(valid_faults, np.where(startup, masks & ~np.uint16(128), masks), np.nan)
                for section in continuous_slices(series.times, _finite(series) & np.isfinite(values), 2.0):
                    if field_name in ("OFN", "OFE"):
                        changed = np.abs(np.diff(values[section])) > 0.01
                        changed &= ~(startup[section][1:] | startup[section][:-1])
                        levels[section.start + 1 : section.stop] = np.where(changed, 1 + primary[section][1:], 0)
                    elif field_name == "TS":
                        levels[section] = np.where(values[section] > 0, 1 + values[section] + 4 * primary[section], 0)
                    else:
                        levels[section] = np.where(values[section] > 0, 1 + primary[section], 0)
                if field_name != "FS":
                    levels[startup] = np.nan
                levels[~gps_evidence] = np.nan
                message_text = (
                    _("EKF lane position reset changed")
                    if field_name in ("OFN", "OFE")
                    else _("EKF lane GPS position or velocity measurement timed out")
                    if field_name == "TS"
                    else _("EKF lane reports a fault or GPS quality check failure")
                )
                evidence = {field_name: series.fields[field_name], "active_primary": primary}
                if field_name == "TS":
                    evidence["gps_timeout_mask"] = values
                if field_name in ("TS", "GPS"):
                    _eligible, source_sets, receiver = self._ekf_source(series, message, "POSXY")
                    identity = 8 * (np.nan_to_num(source_sets, nan=-1) + 1) + 32 * (np.nan_to_num(receiver, nan=-1) + 1)
                    levels = np.where(levels > 0, levels + identity, levels)
                    evidence["gps_receiver"] = receiver
                if field_name in ("FS", "GPS"):
                    raw_mask = series.fields[field_name]
                    valid_mask = (
                        np.isfinite(raw_mask) & (raw_mask >= 0) & (raw_mask <= 65535) & (raw_mask == np.floor(raw_mask))
                    )
                    levels = np.where(valid_mask, levels, np.nan)
                count += int(np.count_nonzero(np.isfinite(levels)))
                outcomes.extend(
                    self._events(
                        series,
                        levels,
                        f"{message}.{field_name}",
                        message_text,
                        evidence,
                        bitmask_fields=(field_name,) if field_name in ("FS", "GPS", "TS") else (),
                    )
                )
            self._ekf_discontinuity_coverage(message, field_name, count, total)
        return outcomes

    def _ekf_discontinuity_coverage(self, message: str, field_name: str, count: int, total: int) -> None:
        if not total:
            return
        detail = _("Samples without a usable GPS navigation source are skipped; startup exclusions may also apply.")
        if message == "XKF4":
            detail += _(" XKFS.SS identifies the active source set; FuseAllVelocities can enable GPS velocity fusion.")
        self._coverage(f"{message}.{field_name}.coverage", count, total, detail)
