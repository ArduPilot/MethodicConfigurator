"""
Attitude-control saturation analysis.

Detects when the ArduCopter attitude controller is limited by the angular-rate limits (ATC_RATE_*_MAX),
the rate-controller slew limiters (ATC_RAT_*_SMAX), the rate-controller P+D sum limits (ATC_RAT_*_PDMX)
and the final-target lean-angle limits (ANGLE_MAX / ATC_ANGLE_MAX and PSC_ANGLE_MAX).

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

from collections.abc import Iterator
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

import numpy as np

from ardupilot_methodic_configurator import _
from ardupilot_methodic_configurator.log_analysis.data_model_availability_base import (
    AvailabilityIssue,
    BaseLogAnalysisModel,
    BaseLogAvailabilityModel,
    LogAvailabilityResult,
)
from ardupilot_methodic_configurator.log_analysis.data_model_log_analysis_result import LogAnalysis, LogAnalysisResult
from ardupilot_methodic_configurator.log_analysis.data_model_log_availability import LogAvailabilityState
from ardupilot_methodic_configurator.log_analysis.utils import find_log_bit_in_apm_file, get_log_bitmask

if TYPE_CHECKING:
    from ardupilot_methodic_configurator.log_analysis.data_model_log_analysis_context import LogAnalysisContext
    from ardupilot_methodic_configurator.log_analysis.data_model_log_data import LogData

Severity = Literal["informational", "warning", "critical"]

# A finding is reported when the limit was active for at least this share of the armed time, or this long in total
_REPORT_MIN_FRACTION = 0.01
_REPORT_MIN_DURATION_S = 1.0
# Attitude control is considered severely reduced when the limit was active for at least this share of the armed time
_SEVERE_MIN_FRACTION = 0.10
# RATE targets near this share of the configured envelope indicate possible rate limiting, not a limiter flag
_RATE_LIMIT_MARGIN = 0.98
# Slew limiter: Dmod scales both P and D, so Dmod < 1 is a direct reduction of the rate-controller authority
_SLEW_REDUCED_DMOD = 0.9
_SLEW_SEVERE_DMOD = 0.5
_SLEW_SEVERE_MIN_FRACTION = 0.05
# Desired tilt within this many degrees of the lean-angle limit is considered clipped by the limit
_ANGLE_LIMIT_MARGIN_DEG = 0.5
# AP_PIDInfo flag bit logged in the PID* "Flags" field when the PD sum limit (PDMX) is active
_PID_FLAG_PD_SUM_LIMIT = 2

# Fixed attitude-control behaviour that is intended to exceed or bypass the pilot lean-angle limits
_COPTER_MODES_WITHOUT_LEAN_LIMIT = frozenset(
    {1, 14, 15, 18, 20, 25, 26, 28}
)  # Acro, Flip, AutoTune, Throw, Guided_NoGPS, SysID, Autorotate, Turtle
# Modes where the position controller normally requests lean angles and so honours PSC_ANGLE_MAX.
# Auto and Guided attitude-command intervals are excluded separately.
# Land (9) may bypass XY control; FlowHold (22) uses its own per-axis angle constraints.
# Both are skipped because MODE and final tilt alone cannot establish the applicable lean limit.
_COPTER_POSITION_CONTROL_MODES = frozenset({3, 4, 5, 6, 7, 17, 19, 21, 23, 24, 27})
_COPTER_PILOT_LEAN_MODES = frozenset({0, 2, 11, 13, 16})
# AP_Mission::is_nav_cmd includes MAV_CMD_NAV_LAST and these nonstandard navigation commands.
_LAST_STANDARD_NAV_COMMAND_ID = 95
_NAV_ATTITUDE_TIME_COMMAND_ID = 42703
_EXTRA_NAV_COMMAND_IDS = frozenset({213, 42702, _NAV_ATTITUDE_TIME_COMMAND_ID})  # SET_YAW_SPEED, SCRIPT_TIME, ATTITUDE_TIME


@dataclass(frozen=True)
class _AxisSpec:
    """Messages and parameters that describe the saturation of one rotation axis."""

    name: str
    rate_target_field: str
    pid_message: str
    rate_max_param: str
    slew_max_param: str
    pd_max_param: str


_AXES = (
    _AxisSpec("Roll", "RDes", "PIDR", "ATC_RATE_R_MAX", "ATC_RAT_RLL_SMAX", "ATC_RAT_RLL_PDMX"),
    _AxisSpec("Pitch", "PDes", "PIDP", "ATC_RATE_P_MAX", "ATC_RAT_PIT_SMAX", "ATC_RAT_PIT_PDMX"),
    _AxisSpec("Yaw", "YDes", "PIDY", "ATC_RATE_Y_MAX", "ATC_RAT_YAW_SMAX", "ATC_RAT_YAW_PDMX"),
)

_REQUIRED_FIELDS: dict[str, tuple[str, ...]] = {
    "ATT": ("TimeUS", "DesRoll", "DesPitch"),
    "RATE": ("TimeUS", *(axis.rate_target_field for axis in _AXES)),
    **{axis.pid_message: ("TimeUS", "Dmod", "Flags") for axis in _AXES},
}


def _axis_label(axis: _AxisSpec) -> str:
    """Translate the axis name at call time so the active GUI language is used."""
    return {"Roll": _("Roll"), "Pitch": _("Pitch"), "Yaw": _("Yaw")}[axis.name]


@dataclass(frozen=True)
class _SaturationStats:
    """How long and how often a limit was active while the vehicle was armed."""

    fraction: float
    duration_s: float
    first_s: float
    last_s: float
    samples: int


@dataclass(frozen=True)
class _SampledFields:
    """Observed fields held over intervals, with weights retained when a scope is selected."""

    time_s: np.ndarray
    duration_s: np.ndarray
    values: dict[str, np.ndarray]

    def select(self, mask: np.ndarray) -> "_SampledFields":
        return _SampledFields(
            self.time_s[mask], self.duration_s[mask], {key: value[mask] for key, value in self.values.items()}
        )


def _saturation_stats(samples: _SampledFields, saturated: np.ndarray) -> _SaturationStats | None:
    """Summarise elapsed time rather than the density of the selected samples."""
    total_s = float(np.sum(samples.duration_s))
    duration_s = float(np.sum(samples.duration_s[saturated]))
    if total_s <= 0 or duration_s <= 0:
        return None
    active = saturated & (samples.duration_s > 0)
    saturated_times = samples.time_s[active]
    return _SaturationStats(
        fraction=duration_s / total_s,
        duration_s=duration_s,
        first_s=float(saturated_times[0]),
        last_s=float((samples.time_s + samples.duration_s)[active][-1]),
        samples=len(saturated_times),
    )


def _tilt_degrees(roll_deg: np.ndarray, pitch_deg: np.ndarray) -> np.ndarray:
    """Return the angle between the vehicle up axis and vertical for the given roll and pitch."""
    cos_tilt = np.cos(np.radians(roll_deg)) * np.cos(np.radians(pitch_deg))
    return np.asarray(np.degrees(np.arccos(np.clip(cos_tilt, -1.0, 1.0))), dtype=float)


def _is_reportable(stats: _SaturationStats | None) -> bool:
    return stats is not None and (stats.fraction >= _REPORT_MIN_FRACTION or stats.duration_s >= _REPORT_MIN_DURATION_S)


def _fraction_severity(stats: _SaturationStats) -> Severity:
    return "critical" if stats.fraction >= _SEVERE_MIN_FRACTION else "warning"


class AttitudeSaturationLogAvailabilityModel(BaseLogAvailabilityModel):
    """Checks that the attitude, rate and rate-controller messages needed for saturation analysis are logged."""

    def check(self) -> LogAvailabilityResult:
        if self.log_data.vehicle_type not in {"ArduCopter", "Heli"}:
            return LogAvailabilityResult(
                available=False,
                state=LogAvailabilityState.INFO,
                issues=[],
                reason=_("Attitude saturation analysis applies only to Copter and helicopter logs"),
                name=_("Attitude saturation"),
            )
        present = {
            message_name
            for message_name in _REQUIRED_FIELDS
            if (columns := self.log_data.get_message_columns(message_name)) is not None and len(columns) > 0
        }
        if not present:
            return self._diagnose_absence()

        issues: list[AvailabilityIssue] = []
        for message_name, field_names in _REQUIRED_FIELDS.items():
            if message_name in present:
                issues += self.check_fields_present(message_name, field_names)

        if "RATE" not in present:
            issues.append(self._missing_rate_issue())

        if not present.intersection(axis.pid_message for axis in _AXES):
            issues.append(self._missing_pid_issue())

        return self.build_result(issues, _("Attitude saturation"))

    def _missing_rate_issue(self) -> AvailabilityIssue:
        """Explain skipped rate-limit checks and suggest attitude logging when both logging bits are disabled."""
        issue = AvailabilityIssue(
            _(
                "No RATE messages found, ATC_RATE_*_MAX saturation checks were skipped. "
                "Check Fast Attitude or Medium Attitude logging (LOG_BITMASK bit)"
            ),
            self.step_for_parameter("LOG_BITMASK"),
        )
        bitmask = self.parameters.get("LOG_BITMASK")
        bitmask_field = get_log_bitmask(self.apm_doc) if self.apm_doc else None
        fast_bit = find_log_bit_in_apm_file(bitmask_field, "Fast Attitude") if bitmask_field else None
        medium_bit = find_log_bit_in_apm_file(bitmask_field, "Medium Attitude") if bitmask_field else None
        if bitmask is not None and fast_bit is not None and medium_bit is not None:
            attitude_bits = (1 << fast_bit) | (1 << medium_bit)
            if int(bitmask) & attitude_bits == 0:
                issue.param_name = "LOG_BITMASK"
                issue.suggested_value = float(int(bitmask) | (1 << medium_bit))
        return issue

    def _missing_pid_issue(self) -> AvailabilityIssue:
        """Explain that the slew and PD-sum limit checks need PID logging, which has its own LOG_BITMASK bit."""
        bitmask = self.parameters.get("LOG_BITMASK")
        bitmask_field = get_log_bitmask(self.apm_doc) if self.apm_doc else None
        pid_bit = find_log_bit_in_apm_file(bitmask_field, "PID") if bitmask_field else None
        message = _("No PIDR, PIDP or PIDY messages found, ATC_RAT_*_SMAX and ATC_RAT_*_PDMX saturation cannot be checked")
        if bitmask is None or pid_bit is None or int(bitmask) & (1 << pid_bit):
            return AvailabilityIssue(message, self.step_for_parameter("LOG_BITMASK"))
        return AvailabilityIssue(
            message,
            self.step_for_parameter("LOG_BITMASK"),
            param_name="LOG_BITMASK",
            suggested_value=float(int(bitmask) | (1 << pid_bit)),
        )

    def _diagnose_absence(self) -> LogAvailabilityResult:
        """Diagnose why none of the attitude messages are present, using the fast/medium attitude LOG_BITMASK bits."""
        name = _("Attitude saturation")
        bitmask = self.parameters.get("LOG_BITMASK")
        bitmask_field = get_log_bitmask(self.apm_doc) if self.apm_doc else None
        fast_bit = find_log_bit_in_apm_file(bitmask_field, "Fast Attitude") if bitmask_field else None
        medium_bit = find_log_bit_in_apm_file(bitmask_field, "Medium Attitude") if bitmask_field else None

        issues: list[AvailabilityIssue] = []
        if bitmask is not None and fast_bit is not None and medium_bit is not None:
            attitude_bits = (1 << fast_bit) | (1 << medium_bit)
            if int(bitmask) & attitude_bits == 0:
                reason = _("Attitude logging is disabled in LOG_BITMASK")
                issues.append(
                    AvailabilityIssue(
                        _("Enable Fast Attitude or Medium Attitude logging (LOG_BITMASK bit)"),
                        self.step_for_parameter("LOG_BITMASK"),
                        param_name="LOG_BITMASK",
                        suggested_value=float(int(bitmask) | (1 << medium_bit)),
                    )
                )
                return LogAvailabilityResult(
                    available=False, state=LogAvailabilityState.WARNING, reason=reason, issues=issues, name=name
                )

        reason = _("Attitude telemetry (ATT, RATE, PID*) not logged but logging enabled; check the attitude logging options")
        issues.append(AvailabilityIssue(_("No ATT, RATE or PID messages found")))
        return LogAvailabilityResult(
            available=False, state=LogAvailabilityState.WARNING, reason=reason, issues=issues, name=name
        )


class AttitudeSaturationLogAnalysis(BaseLogAnalysisModel):
    """
    Detect attitude-control saturation from the log.

    Every check only considers the time the vehicle was armed, and each reports the share of that time for which the
    limit was active. Limits that act for a large share of the time are rated critical because the
    attitude controller can then no longer deliver what was requested of it.
    """

    def __init__(self, log_data: "LogData", context: "LogAnalysisContext") -> None:
        super().__init__(log_data, context)
        self._parameter_history = context.parameter_history
        if not (self._parameter_history.initial_values or self._parameter_history.changes) and log_data.parameter_history:
            self._parameter_history = log_data.parameter_history

    def analyse(self) -> LogAnalysisResult:
        if self.log_data.vehicle_type not in {"ArduCopter", "Heli"}:
            return LogAnalysisResult(
                available=False,
                outcomes=[],
                name=_("Attitude Saturation Analysis"),
                reason=_("Attitude saturation analysis applies only to Copter and helicopter logs"),
            )
        outcomes: list[LogAnalysis] = []
        for check in (self.check_rate_limits, self.check_slew_limits, self.check_pd_sum_limits, self.check_lean_angle_limits):
            outcomes += check()

        return LogAnalysisResult(
            available=True,
            outcomes=outcomes,
            name=_("Attitude Saturation Analysis"),
            reason=_("Attitude saturation analysis complete"),
        )

    # --- shared helpers -------------------------------------------------------------------------------------

    def _armed_mask(self, time_s: np.ndarray) -> np.ndarray:
        """Resolve ARM transitions, inferring the preceding state when the initial arm event was not logged."""
        columns = self.log_data.get_message_columns("ARM")
        if columns is None or len(columns) == 0:
            return np.ones(len(time_s), dtype=bool)
        if not all(self.field_available("ARM", field) for field in ("TimeUS", "ArmState")):
            return np.zeros(len(time_s), dtype=bool)
        arm_time = np.asarray(self.log_data.get_field("ARM", "TimeUS"), dtype=float)
        arm_state = np.asarray(self.log_data.get_field("ARM", "ArmState"), dtype=float)
        if not (np.isfinite(arm_time).all() and np.isfinite(arm_state).all()):
            return np.zeros(len(time_s), dtype=bool)
        order = np.argsort(arm_time, kind="stable")
        index = np.searchsorted(arm_time[order], time_s, side="right") - 1
        states = arm_state[order] != 0
        return np.asarray(np.where(index >= 0, states[np.maximum(index, 0)], ~states[0]), dtype=bool)

    def _sample_timeline(self, time_s: np.ndarray) -> np.ndarray:
        """Split observed intervals at state and parameter changes before any scope filtering."""
        boundaries = [time_s]
        boundaries.extend(
            np.asarray(self.log_data.get_field(message, "TimeUS"), dtype=float)
            for message in ("ARM", "MODE", "CMD", "MISE", "GUIP", "GUIA")
            if self.field_available(message, "TimeUS")
        )
        limit_names = {name for axis in _AXES for name in (axis.rate_max_param, axis.slew_max_param, axis.pd_max_param)} | {
            "ATC_ANGLE_MAX",
            "ANGLE_MAX",
            "PSC_ANGLE_MAX",
        }
        boundaries.append(
            np.asarray(
                [
                    change.time_s
                    for name, changes in self._parameter_history.changes.items()
                    if name in limit_names
                    for change in changes
                ],
                dtype=float,
            )
        )
        timeline = np.unique(np.concatenate(boundaries))
        return np.asarray(timeline[np.isfinite(timeline) & (timeline >= time_s[0]) & (timeline <= time_s[-1])], dtype=float)

    def _armed_fields(self, message_name: str, field_names: tuple[str, ...]) -> _SampledFields | None:
        """Return the armed-time samples of the requested fields, or None when any of them is unreadable."""
        if not all(self.field_available(message_name, field) for field in ("TimeUS", *field_names)):
            return None
        time_s = np.asarray(self.log_data.get_field(message_name, "TimeUS"), dtype=float)
        if len(time_s) == 0 or not np.isfinite(time_s).all():
            return None
        order = np.argsort(time_s, kind="stable")
        time_s = time_s[order]
        timeline = self._sample_timeline(time_s)
        index = np.searchsorted(time_s, timeline, side="right") - 1
        armed = self._armed_mask(timeline)
        # No duration is inferred beyond the final observation; a lone sample has zero weight.
        duration_s = np.diff(timeline, append=timeline[-1])
        values = {
            field: np.asarray(self.log_data.get_field(message_name, field), dtype=float)[order][index][armed]
            for field in field_names
        }
        if any(not np.isfinite(column).all() for column in values.values()):
            return None
        return _SampledFields(timeline[armed], duration_s[armed], values)

    def _parameter_groups(
        self, samples: _SampledFields, names: tuple[str, ...]
    ) -> Iterator[tuple[tuple[float, ...], np.ndarray]]:
        """Group samples by effective settings, skipping missing and non-finite limits as disabled."""
        columns = []
        for name in names:
            history_has_name = name in self._parameter_history.initial_values or name in self._parameter_history.changes
            values = np.asarray(
                [self._parameter_history.value_at(name, float(t)) for t in samples.time_s]
                if history_has_name
                else [self.parameters.get(name, 0.0)] * len(samples.time_s),
                dtype=float,
            )
            columns.append(np.where(np.isfinite(values), values, 0.0))
        settings = np.column_stack(columns)
        for row in np.unique(settings, axis=0):
            yield tuple(float(value) for value in row), np.all(settings == row, axis=1)

    def _enabled_parameter_mask(self, samples: _SampledFields, name: str) -> np.ndarray:
        """Select only intervals for which a limiter parameter is present and enabled."""
        enabled = np.zeros(len(samples.time_s), dtype=bool)
        for (limit,), mask in self._parameter_groups(samples, (name,)):
            if limit > 0:
                enabled |= mask
        return enabled

    def _finding(  # pylint: disable=too-many-arguments
        self,
        message: str,
        stats: _SaturationStats,
        severity: Severity,
        param_name: str,
        evidence: dict[str, float],
        *,
        source: str,
    ) -> LogAnalysis:
        return LogAnalysis(
            message=message,
            timestamp_us=stats.first_s * 1e6,
            end_timestamp_us=stats.last_s * 1e6,
            value=stats.fraction * 100.0,
            related_step=self.step_for_parameter(param_name),
            param_name=param_name,
            severity=severity,
            source=source,
            evidence={"saturated_percent": stats.fraction * 100.0, "saturated_seconds": stats.duration_s, **evidence},
        )

    # --- ATC_RATE_*_MAX -------------------------------------------------------------------------------------

    def check_rate_limits(self) -> list[LogAnalysis]:
        """Check the shared roll/pitch ellipse and the independent yaw limit using historical settings."""
        outcomes: list[LogAnalysis] = []
        timeline = self._armed_fields("RATE", ())
        if timeline is None:
            return outcomes
        for axes in (_AXES[:2], _AXES[2:]):
            for limits, setting_mask in self._parameter_groups(timeline, tuple(axis.rate_max_param for axis in axes)):
                group = tuple((axis, limit) for axis, limit in zip(axes, limits, strict=True) if limit > 0)
                if not group:
                    continue
                samples = self._armed_fields("RATE", tuple(axis.rate_target_field for axis, _limit in group))
                if samples is None:
                    continue
                magnitude = np.sqrt(sum((samples.values[axis.rate_target_field] / limit) ** 2 for axis, limit in group))
                stats = _saturation_stats(samples, setting_mask & (magnitude >= _RATE_LIMIT_MARGIN))
                if stats is not None and _is_reportable(stats):
                    outcomes.append(self._rate_finding(stats, group))
        return outcomes

    def _rate_finding(self, stats: _SaturationStats, group: tuple[tuple[_AxisSpec, float], ...]) -> LogAnalysis:
        """Describe near-envelope RATE evidence without claiming a directly logged limiter activation."""
        axis_name = _("Roll/pitch") if len(group) == 2 else _axis_label(group[0][0])
        parameter_names = " / ".join(axis.rate_max_param for axis, _ in group)
        limits_text = " / ".join(_("{limit:.0f} deg/s").format(limit=limit) for _axis, limit in group)
        message = _(
            "{axis} rate target reached the configured {param} envelope ({limits}) for {percent:.1f}% of the armed time "
            "({seconds:.1f} s). RATE targets near or above this envelope suggest rate limiting but do not prove clipping. "
            "Check target tracking and disturbances before changing the limits."
        ).format(
            axis=axis_name, param=parameter_names, limits=limits_text, percent=stats.fraction * 100.0, seconds=stats.duration_s
        )
        severity = _fraction_severity(stats)
        if severity == "critical":
            message += " " + _("Frequent rate limiting can severely reduce attitude control.")
        evidence = {"roll_limit": group[0][1], "pitch_limit": group[1][1]} if len(group) == 2 else {"limit": group[0][1]}
        return self._finding(message, stats, severity, group[0][0].rate_max_param, evidence, source="RATE")

    # --- ATC_RAT_*_SMAX -------------------------------------------------------------------------------------

    def check_slew_limits(self) -> list[LogAnalysis]:
        """Detect the rate-controller slew limiter scaling P and D down (ATC_RAT_*_SMAX)."""
        outcomes: list[LogAnalysis] = []
        for axis in _AXES:
            samples = self._armed_fields(axis.pid_message, ("Dmod",))
            if samples is None:
                continue
            enabled = self._enabled_parameter_mask(samples, axis.slew_max_param)
            dmod = samples.values["Dmod"]
            stats = _saturation_stats(samples, enabled & (dmod < _SLEW_REDUCED_DMOD))
            if stats is None or not _is_reportable(stats):
                continue

            severe_fraction = float(np.sum(samples.duration_s[enabled & (dmod < _SLEW_SEVERE_DMOD)])) / float(
                np.sum(samples.duration_s)
            )
            severity: Severity = "critical" if severe_fraction >= _SLEW_SEVERE_MIN_FRACTION else "warning"
            if severity == "critical":
                message = _(
                    "{axis} rate controller P and D gains were cut below {severe:.0%} by the {param} slew limiter for "
                    "{severe_percent:.1f}% of the armed time. This severely reduces attitude control. "
                    "Reduce the P and D gains or increase {param}."
                )
            else:
                message = _(
                    "{axis} rate controller P and D gains were reduced below {reduced:.0%} by the {param} slew limiter for "
                    "{percent:.1f}% of the armed time ({seconds:.1f} s), which indicates an oscillation tendency. "
                    "Check the tune before increasing {param}."
                )
            outcomes.append(
                self._finding(
                    message.format(
                        axis=_axis_label(axis),
                        param=axis.slew_max_param,
                        severe=_SLEW_SEVERE_DMOD,
                        severe_percent=severe_fraction * 100.0,
                        reduced=_SLEW_REDUCED_DMOD,
                        percent=stats.fraction * 100.0,
                        seconds=stats.duration_s,
                    ),
                    stats,
                    severity,
                    axis.slew_max_param,
                    {
                        "minimum_dmod": float(dmod[enabled & (samples.duration_s > 0)].min()),
                        "severe_percent": severe_fraction * 100.0,
                    },
                    source=axis.pid_message,
                )
            )
        return outcomes

    # --- ATC_RAT_*_PDMX -------------------------------------------------------------------------------------

    def check_pd_sum_limits(self) -> list[LogAnalysis]:
        """Detect the P+D sum of the rate controller being clipped by ATC_RAT_*_PDMX."""
        outcomes: list[LogAnalysis] = []
        for axis in _AXES:
            samples = self._armed_fields(axis.pid_message, ("Flags",))
            if samples is None:
                continue
            enabled = self._enabled_parameter_mask(samples, axis.pd_max_param)
            flags = samples.values["Flags"].astype(np.int64)
            stats = _saturation_stats(samples, enabled & ((flags & _PID_FLAG_PD_SUM_LIMIT) != 0))
            if stats is None or not _is_reportable(stats):
                continue

            severity = _fraction_severity(stats)
            if severity == "critical":
                message = _(
                    "{axis} rate controller P+D output was clipped by {param} for {percent:.1f}% of the armed time "
                    "({seconds:.1f} s). This severely reduces attitude control. Increase {param} or lower the P and D gains."
                )
            else:
                message = _(
                    "{axis} rate controller P+D output reached the {param} limit for {percent:.1f}% of the armed time "
                    "({seconds:.1f} s), so attitude control was limited. Consider increasing {param}."
                )
            outcomes.append(
                self._finding(
                    message.format(
                        axis=_axis_label(axis),
                        param=axis.pd_max_param,
                        percent=stats.fraction * 100.0,
                        seconds=stats.duration_s,
                    ),
                    stats,
                    severity,
                    axis.pd_max_param,
                    {},
                    source=axis.pid_message,
                )
            )
        return outcomes

    # --- ANGLE_MAX / ATC_ANGLE_MAX / PSC_ANGLE_MAX ----------------------------------------------------------

    def _mode_numbers_at(self, time_s: np.ndarray) -> np.ndarray | None:
        """Return the flight-mode number active at each time, or None when mode changes are not logged."""
        if not (self.field_available("MODE", "TimeUS") and self.field_available("MODE", "ModeNum")):
            return None
        mode_time = np.asarray(self.log_data.get_field("MODE", "TimeUS"), dtype=float)
        mode_number = np.asarray(self.log_data.get_field("MODE", "ModeNum"), dtype=float)
        if len(mode_time) == 0 or not (np.isfinite(mode_time).all() and np.isfinite(mode_number).all()):
            return None
        order = np.argsort(mode_time, kind="stable")
        index = np.searchsorted(mode_time[order], time_s, side="right") - 1
        numbers = mode_number[order][np.clip(index, 0, None)]
        numbers[index < 0] = -1  # before the first logged mode
        return numbers

    def _lean_limit_kind_per_sample(self, time_s: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        """Classify each sample by the lean-angle limit of its flight mode and whether any such limit applies."""
        modes = self._mode_numbers_at(time_s)
        if modes is None:
            modes = np.full(len(time_s), -1.0)
        kind_per_sample = np.full(len(time_s), "vehicle", dtype=object)
        kind_per_sample[np.isin(modes, list(_COPTER_POSITION_CONTROL_MODES))] = "position"
        known = _COPTER_POSITION_CONTROL_MODES | _COPTER_PILOT_LEAN_MODES
        has_limit = np.isin(modes, list(known)) & ~np.isin(modes, list(_COPTER_MODES_WITHOUT_LEAN_LIMIT))
        if np.any(modes == 4):
            has_limit &= (modes != 4) | self._guided_position_mask(time_s)
        if np.any(modes == 3):
            has_limit &= (modes != 3) | self._guided_position_mask(time_s, auto=True)
        return kind_per_sample, has_limit

    def _guided_position_mask(self, time_s: np.ndarray, *, auto: bool = False) -> np.ndarray:
        """
        Exclude attitude-command intervals that bypass the XY controller in Guided and Auto.

        Guided requires position-target evidence after MODE; Auto also follows executing mission navigation items.
        """
        events: list[tuple[float, bool]] = []
        # Mission attitude commands and GUIA win ties with GUIP to avoid ambiguous position-limit advice.
        target_events = [("MODE", auto), ("GUIP", True)]
        if auto:
            # Copter 4.6+ uses MISE for execution; its CMD records only dump the uploaded mission.
            mission_message = "MISE" if self.log_data.get_message_columns("MISE") is not None else "CMD"
            target_events.append((mission_message, True))
        target_events.append(("GUIA", False))
        for message, position_target in target_events:
            if message in {"MISE", "CMD"}:
                events.extend(self._mission_navigation_events(message))
                continue
            if not self.field_available(message, "TimeUS"):
                continue
            times = np.asarray(self.log_data.get_field(message, "TimeUS"), dtype=float)
            if not np.isfinite(times).all():
                return np.zeros(len(time_s), dtype=bool)
            events.extend((float(timestamp), position_target) for timestamp in times)
        if not events:
            return np.zeros(len(time_s), dtype=bool)
        events.sort(key=lambda event: event[0])
        event_times = np.asarray([timestamp for timestamp, _ in events], dtype=float)
        position_targets = np.asarray([position for _, position in events], dtype=bool)
        index = np.searchsorted(event_times, time_s, side="right") - 1
        return np.asarray((index >= 0) & position_targets[np.maximum(index, 0)], dtype=bool)

    def _mission_navigation_events(self, message: str) -> list[tuple[float, bool]]:
        """Track navigation items only; DO and condition items do not end an active attitude leg."""
        if not all(self.field_available(message, field) for field in ("TimeUS", "CId")):
            return []
        times = np.asarray(self.log_data.get_field(message, "TimeUS"), dtype=float)
        commands = np.asarray(self.log_data.get_field(message, "CId"), dtype=float)
        navigation = np.isfinite(times) & (
            ((commands > 0) & (commands <= _LAST_STANDARD_NAV_COMMAND_ID)) | np.isin(commands, list(_EXTRA_NAV_COMMAND_IDS))
        )
        return [
            (float(timestamp), bool(command != _NAV_ATTITUDE_TIME_COMMAND_ID))
            for timestamp, command in zip(times[navigation], commands[navigation], strict=True)
        ]

    def check_lean_angle_limits(self) -> list[LogAnalysis]:
        """Compare the final target with its historical vehicle or position ceiling, including Loiter."""
        samples = self._armed_fields("ATT", ("DesRoll", "DesPitch"))
        if samples is None:
            return []
        tilt_deg = _tilt_degrees(samples.values["DesRoll"], samples.values["DesPitch"])
        outcomes: list[LogAnalysis] = []
        for (kind, param_name, limit_deg), scope in self._lean_angle_scopes(samples).items():
            scoped_samples = samples.select(scope)
            clipped = tilt_deg[scope] >= limit_deg - _ANGLE_LIMIT_MARGIN_DEG
            stats = _saturation_stats(scoped_samples, clipped)
            if stats is not None and _is_reportable(stats):
                outcomes.append(self._lean_angle_finding(param_name, limit_deg, stats, position_controlled=kind == "position"))
        return outcomes

    def _lean_angle_scopes(self, samples: _SampledFields) -> dict[tuple[str, str, float], np.ndarray]:
        """Merge mode and setting intervals that use the same effective final-target limit."""
        kind_per_sample, has_limit = self._lean_limit_kind_per_sample(samples.time_s)

        scopes: dict[tuple[str, str, float], np.ndarray] = {}
        for (atc_angle, legacy_angle, position_angle), setting_mask in self._parameter_groups(
            samples, ("ATC_ANGLE_MAX", "ANGLE_MAX", "PSC_ANGLE_MAX")
        ):
            # ATC_ANGLE_MAX uses degrees since Copter 4.7; legacy ANGLE_MAX uses centidegrees.
            vehicle: tuple[str, float] = ("ATC_ANGLE_MAX", atc_angle) if atc_angle > 0 else ("ANGLE_MAX", legacy_angle / 100.0)
            position: tuple[str, float] = ("PSC_ANGLE_MAX", position_angle) if position_angle > 0 else vehicle
            for kind, limit in (("vehicle", vehicle), ("position", position)):
                if limit[1] <= 0:
                    continue
                mask = setting_mask & has_limit & (kind_per_sample == kind)
                key = (kind, limit[0], limit[1])
                scopes.setdefault(key, np.zeros(len(samples.time_s), dtype=bool))
                scopes[key] |= mask

        return scopes

    def _lean_angle_finding(
        self, param_name: str, limit_deg: float, stats: _SaturationStats, *, position_controlled: bool
    ) -> LogAnalysis:
        if not position_controlled:
            details = _("The full pilot lean range of {limit:.0f} deg allowed by {param} was used")
        elif param_name == "PSC_ANGLE_MAX":
            details = _("The position controller was limited to {limit:.0f} deg by {param}")
        else:
            details = _("The vehicle lean angle was limited to {limit:.0f} deg by {param}")
        if position_controlled:
            template = _(
                "{details} for {percent:.1f}% of the armed time in the flight modes it applies to ({seconds:.1f} s). "
                "Lean-angle saturation is happening: the vehicle cannot tilt further to follow the demanded acceleration. "
                "Raise {param} if the airframe and payload allow it."
            )
        else:
            template = _(
                "{details} for {percent:.1f}% of the armed time in the flight modes it applies to ({seconds:.1f} s). "
                "Review pilot inputs and the configured lean range."
            )
        message = template.format(
            details=details.format(limit=limit_deg, param=param_name),
            percent=stats.fraction * 100.0,
            seconds=stats.duration_s,
            param=param_name,
        )
        return self._finding(message, stats, "warning", param_name, {"limit_deg": limit_deg}, source="ATT")
