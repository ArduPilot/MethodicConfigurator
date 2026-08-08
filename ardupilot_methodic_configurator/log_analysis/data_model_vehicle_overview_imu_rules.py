"""
IMU-specific rule helpers for vehicle overview extraction.

SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-FileCopyrightText: 2026 Omkar Sarkar <omkarsarkar24@gmail.com>

SPDX-License-Identifier: GPL-3.0-or-later
"""

from ardupilot_methodic_configurator.log_analysis.data_model_vehicle_overview_sensor_rules import any_nonzero


def imu_axes_offsets(params: dict[str, float], prefix: str, suffix: str) -> list[float | None]:
    """Read three-axis offsets from parameter map."""
    return [params.get(f"{prefix}{suffix}_{axis}") for axis in ("X", "Y", "Z")]


def imu_axes_offsets_by_instance(params: dict[str, float], prefix: str, instance: int) -> list[float | None]:
    """Read three-axis offsets from parameter map where instance is part of the key stem."""
    return [params.get(f"{prefix}{instance}_{axis}") for axis in ("X", "Y", "Z")]


def imu_calibration_from_offsets(offsets: list[float | None]) -> bool | None:
    """Resolve calibration state from 3-axis offsets."""
    return any_nonzero(offsets)


def imu_temp_calibrated(tcal_enable: float | None, enabled_codes: set[str]) -> bool | None:
    """Resolve temperature-calibration state from INS_TCALn_ENABLE value and enabled code set."""
    if tcal_enable is None:
        return None
    return str(int(tcal_enable)) in enabled_codes
