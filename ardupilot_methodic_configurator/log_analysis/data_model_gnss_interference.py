"""
Receiver indications and corroborated GNSS interference findings.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

from typing import Literal

import numpy as np

from ardupilot_methodic_configurator import _
from ardupilot_methodic_configurator.log_analysis.data_model_availability_base import BaseLogAnalysisModel
from ardupilot_methodic_configurator.log_analysis.data_model_gnss_consistency import GnssConsistencyChecks
from ardupilot_methodic_configurator.log_analysis.data_model_gnss_samples import (
    RECEIVER_FIELDS,
    SensorSeries,
    continuous_slices,
    event_intervals,
    numeric_fields,
    receiver_gap_limit,
    sensor_series,
)
from ardupilot_methodic_configurator.log_analysis.data_model_log_analysis_result import LogAnalysis, LogAnalysisResult
from ardupilot_methodic_configurator.log_analysis.data_model_log_data import LogData

FindingSeverity = Literal["informational", "warning", "critical"]


def interval_finding(  # pylint: disable=too-many-arguments,too-many-positional-arguments
    series: SensorSeries,
    start: int,
    end: int,
    message: str,
    source: str,
    severity: FindingSeverity = "warning",
    evidence: dict[str, float] | None = None,
) -> LogAnalysis:
    """Convert canonical seconds to the report's explicitly microsecond timestamps."""
    identity = (
        _("sensor {instance}").format(instance=series.instance) if series.instance is not None else _("unidentified sensor")
    )
    return LogAnalysis(
        message=_("{source}, {identity}: {message}").format(source=source, identity=identity, message=message),
        timestamp_us=float(series.times[start] * 1e6),
        end_timestamp_us=float(series.times[end] * 1e6),
        source=source,
        instance=series.instance,
        severity=severity,
        evidence=evidence,
        group=_("Receiver indications"),
    )


class GPSLogAnalysis(BaseLogAnalysisModel):
    """Analyze each available GNSS capability independently of the other sources."""

    def analyse(self) -> LogAnalysisResult:
        outcomes = self.check_receiver_indications()
        checks = GnssConsistencyChecks(self.log_data, self.parameters, self.log_data.parameter_history)
        outcomes.extend(checks.analyse())
        outcomes.extend(self.correlate_findings(outcomes, self.log_data))
        groups = {_("Receiver indications"): 0, _("GNSS consistency"): 1, _("Correlated evidence"): 2, _("Coverage"): 3}
        outcomes.sort(key=lambda item: (groups.get(item.group or "", 4), item.timestamp_us or 0, item.source or ""))
        step, name = self.resolve_message_step("GPS", "GPS")
        reason = _(
            "GNSS assessment complete. Receiver indications and consistency discrepancies require review; "
            "sensor faults can cause similar symptoms, and undetected spoofing remains possible."
        )
        available = any(
            item.timestamp_us is not None
            or (item.evidence or {}).get("evaluated", 0) > 0
            or (item.evidence or {}).get("readable", 0) > 0
            for item in outcomes
        )
        if not available:
            reason = _("No supported timestamped GNSS checks could be evaluated; review the coverage and availability issues")
        return LogAnalysisResult(
            available=available,
            outcomes=outcomes,
            name=_("{name} Analysis").format(name=name),
            reason=reason,
            related_step=step,
        )

    def check_receiver_indications(self) -> list[LogAnalysis]:
        """Decode raw numeric statuses, without trusting delayed GCS text messages."""
        outcomes: list[LogAnalysis] = []
        for message, fields in RECEIVER_FIELDS.items():
            for field in fields:
                for series in sensor_series(self.log_data, message, (field,)):
                    if message == "UBX1":
                        outcomes.extend(self._ublox_indications(series))
                    else:
                        outcomes.extend(self._status_indications(series, message, field))
        return outcomes

    @staticmethod
    def _status_indications(series: SensorSeries, message: str, field: str) -> list[LogAnalysis]:
        values = series.fields[field]
        finite = np.isfinite(values) & (values == np.floor(values)) & (values >= 0) & (values <= 255)
        # 1 means healthy. Zero, undocumented codes and non-integral values are
        # unknown, never evidence that a receiver has ruled interference out.
        levels = np.where(finite, np.where(values == 1, 0, values + 1), np.nan)
        threat = _("spoofing") if field in ("Spf", "GSS") else _("jamming")
        outcomes: list[LogAnalysis] = []
        for start, end, code in event_intervals(series.times, levels):
            status = code - 1
            severity: FindingSeverity = "informational"
            if message == "AERG" and status in (2, 3):
                severity = "warning" if status == 2 else "critical"
                text = _("Receiver-reported {threat} {level} (status {status})").format(
                    threat=threat, level=_("warning") if status == 2 else _("critical"), status=status
                )
            elif field == "GSS" and status in (2, 3):
                severity = "warning"
                text = _("Receiver-reported spoofing indication (status {status}; 3 indicates multiple spoofing)").format(
                    status=status
                )
            elif field == "GJS" and status == 3:
                severity = "critical"
                text = _("Receiver-reported jamming indication with no fix (status 3)")
            else:
                text = _("Unknown {threat} status {status}; interference cannot be assessed from this value").format(
                    threat=threat, status=status
                )
            outcomes.append(
                interval_finding(series, start, end, text, f"{message}.{field}", severity, {"status": float(status)})
            )
        outcomes.extend(GPSLogAnalysis._recoveries(series, message, field, threat))
        count = int(np.count_nonzero(finite & np.isfinite(series.times) & (series.times >= 0)))
        outcomes.append(
            LogAnalysis(
                _("{source}: {count} readable status samples; healthy samples do not exclude undetected interference").format(
                    source=f"{message}.{field}", count=count
                ),
                source=f"{message}.{field}",
                instance=series.instance,
                severity="informational",
                group=_("Coverage"),
                evidence={"readable": float(count)},
            )
        )
        return outcomes

    @staticmethod
    def _recoveries(series: SensorSeries, message: str, field: str, threat: str) -> list[LogAnalysis]:
        values = series.fields[field]
        valid_times = np.isfinite(series.times) & (series.times >= 0)
        indicated = (2, 3) if message == "AERG" or field == "GSS" else (3,)
        return [
            interval_finding(
                series,
                index,
                index,
                _("Receiver reports no {threat} indication after the warning; detection remains limited").format(
                    threat=threat
                ),
                f"{message}.{field}",
                "informational",
                {"status": 1.0},
            )
            for index in range(1, len(values))
            if valid_times[index - 1]
            and valid_times[index]
            and values[index] == 1
            and values[index - 1] in indicated
            and 0 < series.times[index] - series.times[index - 1] <= 2
        ]

    @staticmethod
    def _ublox_indications(series: SensorSeries) -> list[LogAnalysis]:
        """Flag large rises relative to a preceding baseline, not absolute attack claims."""
        values = series.fields["jamInd"]
        valid = np.isfinite(values) & (values >= 0) & (values <= 255) & (values == np.floor(values))
        levels = np.full(values.shape, np.nan)
        max_gap_s = receiver_gap_limit(series.times)
        # A 5-second preceding baseline needs five observations. The floor of
        # 20 indicator counts and 6*MAD are conservative diagnostic heuristics,
        # not vendor-defined attack thresholds; see GNSS_LOG_ANALYSIS.md.
        for section in continuous_slices(series.times, valid, max_gap_s):
            times = series.times[section]
            for offset in range(5, len(times)):
                index = section.start + offset
                left = section.start + int(np.searchsorted(times, times[offset] - 5.0))
                # Jitter or a changed cadence must not shrink a continuous baseline below five samples.
                left = min(left, index - 5)
                baseline = values[left:index]
                median = float(np.median(baseline))
                levels[index] = float(values[index] > median + max(20.0, 6.0 * float(np.median(np.abs(baseline - median)))))
        outcomes = [
            interval_finding(
                series,
                start,
                end,
                _("Elevated u-blox jamming indicator relative to preceding samples; possible RF interference"),
                "UBX1.jamInd",
                evidence={"peak_jamInd": float(np.max(values[start : end + 1]))},
            )
            for start, end, _level in event_intervals(series.times, levels, max_gap_s)
        ]
        if valid.any():
            outcomes.append(
                LogAnalysis(
                    _(
                        "u-blox jamInd range {minimum:.0f}-{maximum:.0f}; no validated absolute threshold. "
                        "Interference present from startup or rising slowly may remain undetected."
                    ).format(minimum=float(values[valid].min()), maximum=float(values[valid].max())),
                    source="UBX1.jamInd",
                    instance=series.instance,
                    severity="informational",
                    group=_("Coverage"),
                    evidence={"readable": float(np.count_nonzero(valid & np.isfinite(series.times) & (series.times >= 0)))},
                )
            )
        return outcomes

    @staticmethod
    def correlate_findings(outcomes: list[LogAnalysis], log_data: LogData | None = None) -> list[LogAnalysis]:
        """Link overlapping independent evidence from an identified GPS receiver."""
        if log_data is not None:
            for message in ("UBX1", "GPS", "IMU"):
                samples = numeric_fields(log_data, message, ("TimeUS",))
                if samples is not None:
                    times = samples["TimeUS"]
                    times = times[np.isfinite(times) & (times >= 0)]
                    if np.any(np.diff(times) < 0):
                        return []  # Boot epochs cannot be assigned to findings unambiguously.
        findings: list[LogAnalysis] = []
        pairs = (
            ("UBX1.jamInd", "GPS.Status", _("Suspected jamming: elevated RF indicator coincides with loss of GPS fix")),
            (
                "GPS.IMU",
                "GPS.PositionVelocity",
                _("Suspected spoofing or GPS fault: inertial and position/velocity discrepancies coincide"),
            ),
        )
        for first_source, second_source, message in pairs:
            for first in outcomes:
                if first.source != first_source or first.instance is None or first.timestamp_us is None:
                    continue
                for second in outcomes:
                    if second.source != second_source or second.instance != first.instance or second.timestamp_us is None:
                        continue
                    start = max(first.timestamp_us, second.timestamp_us)
                    end = min(first.end_timestamp_us or first.timestamp_us, second.end_timestamp_us or second.timestamp_us)
                    if start <= end:
                        findings.append(
                            LogAnalysis(
                                message,
                                timestamp_us=start,
                                end_timestamp_us=end,
                                source="GNSS.Correlation",
                                instance=first.instance,
                                severity="warning",
                                group=_("Correlated evidence"),
                                evidence={"receiver": float(first.instance)},
                            )
                        )
        return findings
