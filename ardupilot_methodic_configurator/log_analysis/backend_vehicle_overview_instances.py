"""
Instance and parameter-key helpers for vehicle overview extraction.

SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

from collections.abc import Callable, Iterable
from typing import TypeVar

T = TypeVar("T")


def has_nonzero_parameter(params: dict[str, float], name: str) -> bool:
    """Return True when a parameter exists and is not the zero placeholder used for absent hardware."""
    value = params.get(name)
    return value is not None and value != 0


def instance_suffix(instance: int) -> str:
    """Return ArduPilot instance suffix where instance 1 uses an empty suffix."""
    return "" if instance == 1 else str(instance)


def imu_device_id_param(instance: int) -> str:
    return f"INS_ACC{instance_suffix(instance)}_ID"


def compass_device_id_param(instance: int) -> str:
    return f"COMPASS_DEV_ID{instance_suffix(instance)}"


def baro_device_id_param(instance: int) -> str:
    return f"BARO{instance}_DEVID"


def airspeed_type_param(instance: int) -> str:
    return "ARSPD_TYPE" if instance == 1 else f"ARSPD{instance}_TYPE"


def airspeed_use_param(instance: int) -> str:
    return "ARSPD_USE" if instance == 1 else f"ARSPD{instance}_USE"


def collect_present_instances(
    params: dict[str, float],
    instances: Iterable[int],
    param_name_for_instance: Callable[[int], str],
    build_for_instance: Callable[[int], T],
) -> list[T]:
    """Build instance objects only when the identifying parameter is present and non-zero."""
    return [
        build_for_instance(instance)
        for instance in instances
        if has_nonzero_parameter(params, param_name_for_instance(instance))
    ]
