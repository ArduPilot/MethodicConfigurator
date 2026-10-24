"""
Interpret GNSS telemetry and unavailable values independently of Tkinter.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

from datetime import datetime, timedelta, timezone
from math import isfinite
from typing import TYPE_CHECKING

from ardupilot_methodic_configurator import _
from ardupilot_methodic_configurator.data_model_data_telemetry import STALE_SECONDS, MessageSample, TelemetrySample

if TYPE_CHECKING:
    from ardupilot_methodic_configurator.backend_flightcontroller import FlightController


def _number(fields: dict[str, str], name: str) -> float | None:
    """Treat missing, malformed and non-finite telemetry as unavailable."""
    try:
        value = float(fields[name])
    except (KeyError, ValueError, TypeError):
        return None
    return value if isfinite(value) else None


def _timestamp(utc_usec: float | None, offset_minutes: float | None) -> str:
    """Convert reported UTC using the configured flight-controller timezone offset."""
    if utc_usec is None or utc_usec < 1e12 or offset_minutes is None:
        return _("N/A")
    if not isfinite(offset_minutes) or not -720 <= offset_minutes <= 840 or not float(offset_minutes).is_integer():
        return _("N/A")
    try:
        local_zone = timezone(timedelta(minutes=offset_minutes))
        return datetime.fromtimestamp(utc_usec / 1e6, local_zone).strftime("%Y-%m-%d %H:%M:%S %Z")
    except (OverflowError, OSError, ValueError):
        return _("N/A")


class GnssDataModel:  # pylint: disable=too-few-public-methods
    """Build display rows from fresh reports sent by the selected autopilot."""

    def __init__(self, flight_controller: "FlightController") -> None:
        self.flight_controller = flight_controller
        self.second_receiver_present = False

    @staticmethod
    def _readings(message: MessageSample, local_time: str) -> tuple[str, ...]:
        fields = dict(message.fields)
        fix = _number(fields, "fix_type")
        statuses = (
            _("No GNSS"),
            _("No fix"),
            _("2D fix"),
            _("3D fix"),
            _("DGPS"),
            _("RTK float"),
            _("RTK fixed"),
            _("Static"),
            _("PPP"),
        )
        status = statuses[int(fix)] if fix is not None and fix.is_integer() and 0 <= fix < len(statuses) else _("Unknown fix")
        result = [status]
        for name, scale, precision, limit, required_fix in (
            ("lat", 1e7, 7, 90, 2),
            ("lon", 1e7, 7, 180, 2),
            ("alt", 1000, 3, float("inf"), 3),
        ):
            value = _number(fields, name)
            result.append(
                f"{value / scale:.{precision}f}"
                if value is not None and abs(value / scale) <= limit and fix is not None and fix >= required_fix
                else _("N/A")
            )
        result.append(local_time)
        satellites = _number(fields, "satellites_visible")
        result.append(
            str(int(satellites)) if satellites is not None and satellites.is_integer() and 0 <= satellites < 255 else _("N/A")
        )
        for name in ("h_acc", "v_acc"):
            value = _number(fields, name)
            result.append(
                f"{value / 1000:.3f}"
                if value is not None and 0 < value < 4294967295 and fix is not None and fix >= 3
                else _("N/A")
            )
        return tuple(result)

    def update(self, sample: TelemetrySample) -> tuple[tuple[str, ...], ...]:
        """Return independent rows for both receivers, clearing stale positions."""
        self.second_receiver_present = False
        if sample.connection is None or sample.error:
            status = _("Disconnected") if sample.connection is None else _("Connection error")
            return ((status, *(_("N/A") for _index in range(7))),) * 2
        system = getattr(sample.connection, "target_system", 0)
        component = getattr(sample.connection, "target_component", 0) or 1

        def fresh(name: str) -> MessageSample | None:
            message = sample.messages.get((system, component, name))
            return message if message is not None and 0 <= sample.time - message.last_seen < STALE_SECONDS else None

        clock = fresh("SYSTEM_TIME")
        local_time = _timestamp(
            _number(dict(clock.fields), "time_unix_usec") if clock else None,
            self.flight_controller.fc_parameters.get("BRD_RTC_TZ_MIN"),
        )
        rows = []
        for name in ("GPS_RAW_INT", "GPS2_RAW"):
            message = fresh(name)
            if name == "GPS2_RAW" and message is not None:
                fix = _number(dict(message.fields), "fix_type")
                self.second_receiver_present = fix is not None and fix.is_integer() and 1 <= fix <= 8
            rows.append(
                self._readings(message, local_time)
                if message
                else (_("Waiting for GNSS data"), *(_("N/A") for _index in range(7)))
            )
        return tuple(rows)
