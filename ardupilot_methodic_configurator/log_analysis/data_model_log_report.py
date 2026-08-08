"""
Pure presentation helpers for log quality reports.

These helpers keep report formatting and display decisions out of Tkinter
widgets so they can be tested without a GUI.

SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-FileCopyrightText: 2026 Omkar Sarkar <omkarsarkar24@gmail.com>

SPDX-License-Identifier: GPL-3.0-or-later
"""

from dataclasses import dataclass

from ardupilot_methodic_configurator import _
from ardupilot_methodic_configurator.log_analysis.data_model_log_analysis import LogSummary
from ardupilot_methodic_configurator.log_analysis.data_model_vehicle_overview import VehicleInfo


@dataclass(frozen=True)
class ReportStatus:
    """Header status for the log quality report."""

    text: str
    color: str
    problem_count: int


@dataclass(frozen=True)
class FirmwareReleaseLink:
    """Display text and URL for an ArduPilot firmware release."""

    base_text: str
    version_tag: str
    url: str


def format_duration(sec: float | None) -> str:
    """Format a duration in seconds for report display."""
    if sec is None:
        return "-"
    minutes = int(sec) // 60
    seconds = int(sec) % 60
    return f"{minutes}m {seconds}s"


def build_report_status(summary: LogSummary) -> ReportStatus:
    """Return the report header status from quality and step results."""
    issues_count = sum(len(res.issues) for res in summary.quality_results)
    failed_steps = sum(1 for res in summary.step_results if not res.valid)
    total_problems = issues_count + failed_steps

    if total_problems == 0:
        return ReportStatus(_("Status: Log looks healthy. No major issues detected."), "darkgreen", 0)
    return ReportStatus(
        _("Status: Found {n} potential issue(s) to review.").format(n=total_problems),
        "darkorange",
        total_problems,
    )


def firmware_release_link(vehicle: VehicleInfo | None) -> FirmwareReleaseLink | None:
    """Return an ArduPilot GitHub release link for a parsed firmware identity."""
    if vehicle is None or not vehicle.vehicle_type or vehicle.major is None:
        return None

    base_text = f"{vehicle.vehicle_type} {vehicle.major}.{vehicle.minor}.{vehicle.patch}"
    short_type = vehicle.vehicle_type.replace("Ardu", "")
    version_tag = f"{short_type}-{vehicle.major}.{vehicle.minor}.{vehicle.patch}"
    return FirmwareReleaseLink(base_text, version_tag, f"https://github.com/ArduPilot/ardupilot/tree/{version_tag}")


def step_display_name(step_filename: str) -> str:
    """Return a human-readable label for a configuration-step filename."""
    return step_filename.removesuffix(".param").replace("_", " ").strip()


def clean_devtype(name: str | None) -> str:
    """Strip DEVTYPE prefixes from hardware device type names."""
    if not name or name == "Unknown":
        return "-"
    for prefix in ("DEVTYPE_INS_", "DEVTYPE_BARO_", "DEVTYPE_AIRSPEED_", "DEVTYPE_"):
        if name.startswith(prefix):
            return name[len(prefix) :]
    return name


def format_optional_value(value: object) -> str:
    """Format absent or unknown values with the report placeholder."""
    if value is None:
        return "-"
    text = str(value)
    return "-" if text in ("Unknown", "None", "") else text
