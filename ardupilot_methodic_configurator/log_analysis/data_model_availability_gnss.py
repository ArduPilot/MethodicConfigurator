"""
Data model for GPS/GNSS availability check.

SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-FileCopyrightText: 2026 Omkar Sarkar <omkarsarkar24@gmail.com>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import numpy as np

from ardupilot_methodic_configurator import _
from ardupilot_methodic_configurator.log_analysis.data_model_availability_base import (
    AvailabilityIssue,
    BaseLogAvailabilityModel,
    LogAvailabilityResult,
)
from ardupilot_methodic_configurator.log_analysis.data_model_gnss_consistency import GnssConsistencyChecks
from ardupilot_methodic_configurator.log_analysis.data_model_gnss_samples import (
    RECEIVER_FIELDS,
    numeric_fields,
    receiver_gap_limit,
    sensor_series,
)
from ardupilot_methodic_configurator.log_analysis.data_model_log_availability import LogAvailabilityState


class GPSLogAvailabilityModel(BaseLogAvailabilityModel):
    """Checks GPS/GNSS telemetry and configuration availability."""

    def check(self) -> LogAvailabilityResult:
        records = self.log_data.get_message_columns("GPS")
        detection_issues, readable_sources = self.check_detection_sources()
        if records is None or len(records) == 0:
            ekf_sources: list[str] = []
            checks = GnssConsistencyChecks(self.log_data, self.parameters, self.log_data.parameter_history)
            for message in ("XKF4", "NKF4"):
                ekf_sources.extend(
                    f"{message}.{name}"
                    for name in ("SV", "SP", "FS", "TS", "GPS", "OFN", "OFE")
                    if any(
                        item.instance is not None
                        and np.any(
                            np.isfinite(item.times)
                            & (item.times >= 0)
                            & np.isfinite(item.fields["PI"])
                            & np.isfinite(item.fields[name])
                            & checks.ekf_gps_evidence(item, message)
                        )
                        for item in sensor_series(self.log_data, message, ("PI", name))
                    )
                )
            if not readable_sources and not ekf_sources:
                result = self._diagnose_absence()
                result.issues.extend(detection_issues)
                return result
            step, name = self.resolve_message_step("GPS", "GPS")
            return LogAvailabilityResult(
                available=True,
                state=LogAvailabilityState.WARNING,
                reason=_("GNSS evidence available: {sources}. GPS motion data unavailable.").format(
                    sources=", ".join(readable_sources + ekf_sources)
                ),
                issues=[*detection_issues, AvailabilityIssue(_("No GPS messages; motion consistency checks unavailable"))],
                name=name,
                related_step=step,
            )

        issues: list[AvailabilityIssue] = []
        for check in (self.check_status,):
            issues += check()
        issues += self.check_parameters()

        step, name = self.resolve_message_step("GPS", "GPS")
        result = self.build_result(issues + detection_issues, name, related_step=step)
        result.reason = f"{result.reason}. " + _("Receiver interference indicators: {sources}.").format(
            sources=", ".join(readable_sources) or _("none available; explicit jamming/spoofing assessment unavailable")
        )
        return result

    def check_detection_sources(self) -> tuple[list[AvailabilityIssue], list[str]]:
        """Assess each explicit indicator independently, including timestamp and sample usability."""
        issues: list[AvailabilityIssue] = []
        readable: list[str] = []
        for message, fields in RECEIVER_FIELDS.items():
            for field in fields:
                source = f"{message}.{field}"
                samples = numeric_fields(self.log_data, message, ("TimeUS", field))
                if samples is None:
                    issues.append(
                        AvailabilityIssue(
                            _("{source} unavailable: no numeric timestamped samples in this log").format(source=source)
                        )
                    )
                    continue
                valid = np.isfinite(samples["TimeUS"]) & (samples["TimeUS"] >= 0) & np.isfinite(samples[field])
                valid &= (samples[field] >= 0) & (samples[field] <= 255) & (samples[field] == np.floor(samples[field]))
                series = sensor_series(self.log_data, message, (field,))
                if (
                    not any(
                        np.any(np.isfinite(item.times) & (item.times >= 0) & np.isfinite(item.fields[field]))
                        for item in series
                    )
                    or not valid.any()
                ):
                    issues.append(
                        AvailabilityIssue(
                            _("{source} unavailable: timestamps, sensor identifiers or values are invalid").format(
                                source=source
                            )
                        )
                    )
                    continue
                readable.append(source)
                if not valid.all() or sum(len(item.times) for item in series) != len(samples["TimeUS"]):
                    issues.append(
                        AvailabilityIssue(_("{source} contains invalid samples; coverage is incomplete").format(source=source))
                    )
                if any(
                    np.any(
                        (np.diff(item.times) <= 0)
                        | (np.diff(item.times) > (receiver_gap_limit(item.times) if message == "UBX1" else 2.0))
                    )
                    for item in series
                ):
                    issues.append(
                        AvailabilityIssue(
                            _("{source} has timestamp discontinuities; event intervals stop at gaps").format(source=source)
                        )
                    )
        return issues, readable

    def _diagnose_absence(self) -> LogAvailabilityResult:
        """Diagnose why GPS data is absent using LOG_BITMASK."""
        step, name = self.resolve_message_step("GPS", "GPS")
        reason, issues, _bitmask_disabled = self.diagnose_bitmask_absence(
            "GPS", "GPS", "GPS", not_logged_hint=_("check the GPS physical connection")
        )
        return LogAvailabilityResult(
            available=False, state=LogAvailabilityState.WARNING, reason=reason, issues=issues, name=name, related_step=step
        )

    def check_status(self) -> list[AvailabilityIssue]:
        """Validate GPS fix status."""
        status, issues = self.field_values_or_issue(
            "GPS",
            "Status",
            missing_field_message=_("Status field not present in this firmware's GPS schema"),
            missing_values_message=_("GPS fix status missing from GPS records"),
        )
        if status is not None and max(status) < 3:
            issues.append(AvailabilityIssue(_("GPS never achieved a 3D fix")))
        return issues

    def check_parameters(self) -> list[AvailabilityIssue]:
        """Validate GPS-related parameter configuration."""
        issues: list[AvailabilityIssue] = []
        gps_type = self.parameters.get("GPS_TYPE", self.parameters.get("GPS1_TYPE"))
        if gps_type == 0:
            issues.append(AvailabilityIssue(_("GPS type not configured (set to None)"), self.step_for_parameter("GPS_TYPE")))
        return issues
