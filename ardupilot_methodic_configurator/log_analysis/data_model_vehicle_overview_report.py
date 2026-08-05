"""
Compatibility facade for vehicle overview extraction.

SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

from ardupilot_methodic_configurator.log_analysis.data_model_vehicle_overview import (
    AirspeedInfo,
    BaroInfo,
    CompassInfo,
    HardwareReport,
    ImuInfo,
    StartupInfo,
    VehicleInfo,
)
from ardupilot_methodic_configurator.log_analysis.data_model_vehicle_overview_hardware import (
    _instance_health_from_message_field,
    build_airspeed_info,
    build_baro_info,
    build_compass_info,
    build_imu_info,
    extract_hardware_report,
)
from ardupilot_methodic_configurator.log_analysis.data_model_vehicle_overview_identity import (
    extract_startup_info,
    extract_vehicle_info,
    resolve_board_name,
)

__all__ = [
    "AirspeedInfo",
    "BaroInfo",
    "CompassInfo",
    "HardwareReport",
    "ImuInfo",
    "StartupInfo",
    "VehicleInfo",
    "_instance_health_from_message_field",
    "build_airspeed_info",
    "build_baro_info",
    "build_compass_info",
    "build_imu_info",
    "extract_hardware_report",
    "extract_startup_info",
    "extract_vehicle_info",
    "resolve_board_name",
]
