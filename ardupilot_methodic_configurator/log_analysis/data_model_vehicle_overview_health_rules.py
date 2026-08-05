"""
Health-selection rule helpers for vehicle overview extraction.

SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

from ardupilot_methodic_configurator.log_analysis.data_model_log_data import LogData
from ardupilot_methodic_configurator.log_analysis.data_model_vehicle_overview_health import (
    instance_health_from_message_field,
)


def _message_health_with_preferred_fields(
    log_data: LogData,
    message_name: str,
    instance: int,
    preferred_fields: tuple[str, ...],
) -> bool | None:
    """Resolve per-instance message health using the first available field from preferred_fields."""
    columns = log_data.get_message_columns(message_name)
    names = tuple(columns.dtype.names or ()) if columns is not None else ()

    for field_name in preferred_fields:
        if field_name in names:
            return instance_health_from_message_field(log_data, message_name, instance, field_name)

    return None


def imu_health(log_data: LogData, instance: int) -> tuple[bool | None, bool | None]:
    """Return IMU accel and gyro health for one instance."""
    accel_healthy = _message_health_with_preferred_fields(log_data, "IMU", instance, ("AH",))
    gyro_healthy = _message_health_with_preferred_fields(log_data, "IMU", instance, ("GH",))
    return accel_healthy, gyro_healthy


def compass_health(log_data: LogData, instance: int) -> bool | None:
    """Return compass health for one instance from MAG message."""
    return _message_health_with_preferred_fields(log_data, "MAG", instance, ("Health",))


def baro_health(log_data: LogData, instance: int) -> bool | None:
    """Return barometer health for one instance, handling firmware field-name variants."""
    return _message_health_with_preferred_fields(log_data, "BARO", instance, ("Health", "H"))


def airspeed_health(log_data: LogData, instance: int) -> bool | None:
    """Return airspeed sensor health for one instance from ARSP message."""
    return _message_health_with_preferred_fields(log_data, "ARSP", instance, ("H",))
