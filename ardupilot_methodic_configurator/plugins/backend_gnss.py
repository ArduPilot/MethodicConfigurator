"""
Nonblocking GNSS telemetry requests over the shared flight-controller connection.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

from typing import Any, cast  # pylint: disable=unused-import

from serial import SerialException

from ardupilot_methodic_configurator.backend_data_telemetry import DataTelemetryBackend
from ardupilot_methodic_configurator.data_model_data_telemetry import TelemetrySample


class GnssBackend(DataTelemetryBackend):
    """Request snapshots without changing stream rates or opening another receiver."""

    _last_request = float("-inf")

    def close(self) -> None:
        """Discard observations and request fresh snapshots when monitoring resumes."""
        super().close()
        self._last_request = float("-inf")

    def poll(self) -> TelemetrySample:
        """Drain bounded telemetry and request GNSS/time snapshots at most once a second."""
        sample = super().poll()
        if sample.connection is not None and not sample.error and sample.time - self._last_request >= 1.0:
            self._last_request = sample.time
            master = cast("Any", sample.connection)
            try:
                for message_id in (24, 124, 2):  # GPS_RAW_INT, GPS2_RAW, SYSTEM_TIME
                    master.mav.command_long_send(
                        master.target_system, master.target_component, 512, 0, message_id, 0, 0, 0, 0, 0, 0
                    )  # MAV_CMD_REQUEST_MESSAGE; no blocking acknowledgment wait
            except (OSError, SerialException, AttributeError, TypeError, ValueError):
                self.close()
                return TelemetrySample(sample.connection, sample.time, error=True)
        return sample
