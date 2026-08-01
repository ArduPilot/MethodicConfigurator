"""
Types used by vehicle overview extraction.

SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

from dataclasses import dataclass


@dataclass
class ImuInfo:  # pylint: disable=too-many-instance-attributes
    """Single IMU instance."""

    instance: int
    accel_name: str | None
    accel_bus_type: str | None
    gyro_name: str | None
    gyro_bus_type: str | None
    use: bool | None
    accel_calibrated: bool | None
    gyro_calibrated: bool | None
    accel_temp_calibrated: bool | None
    gyro_temp_calibrated: bool | None
    position_offset_set: bool | None
    accel_healthy: bool | None
    gyro_healthy: bool | None


@dataclass
class CompassInfo:  # pylint: disable=too-many-instance-attributes
    """Single compass instance."""

    instance: int
    name: str | None
    bus_type: str | None
    external: bool | None
    use: bool | None
    calibrated: bool | None
    motor_calibrated: bool | None
    healthy: bool | None


@dataclass
class BaroInfo:
    """Single barometer instance."""

    instance: int
    name: str | None
    bus_type: str | None
    wind_compensation: bool | None
    healthy: bool | None


@dataclass
class AirspeedInfo:
    """Single airspeed sensor instance."""

    instance: int
    sensor_type: str | None
    use: bool | None
    healthy: bool | None


@dataclass
class StartupInfo:
    """OS and flight-controller identity strings, read from the MSG startup block."""

    os_string: str | None
    flight_controller: str | None


@dataclass
class VehicleInfo:  # pylint: disable=too-many-instance-attributes
    """Vehicle type, firmware version, board id, and flight-controller identity."""

    vehicle_type: str | None
    major: int | None
    minor: int | None
    patch: int | None
    firmware_hash: str | None
    board_id: int | None
    flight_controller: str | None
    oper_sys: str | None


@dataclass
class HardwareReport:
    """Complete hardware identity for one log: vehicle, IMUs, compasses, baros, airspeed sensors."""

    vehicle: VehicleInfo
    board_name: str | None
    imus: list[ImuInfo]
    compasses: list[CompassInfo]
    baros: list[BaroInfo]
    airspeed_sensors: list[AirspeedInfo]
