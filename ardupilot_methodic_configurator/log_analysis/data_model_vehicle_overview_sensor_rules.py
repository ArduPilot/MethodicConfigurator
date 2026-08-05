"""
Shared sensor-rule helpers for vehicle overview extraction.

SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

from collections.abc import Iterable

from ardupilot_methodic_configurator.log_analysis.decode_devid_lib import decode_device_id, get_device_type_name


def decode_name_and_bus(device_id: float | None, device_category: str) -> tuple[str | None, str | None]:
    """Decode a device id into a type name and bus name."""
    if device_id is None:
        return None, None

    decoded = decode_device_id(int(device_id))
    return get_device_type_name(decoded["devtype"], device_category), decoded["bus_type_name"]


def parameter_enabled(params: dict[str, float], param_name: str) -> bool | None:
    """Map a numeric enable-style parameter to bool using ArduPilot's 1=true convention."""
    value = params.get(param_name)
    return None if value is None else value == 1


def any_nonzero(values: Iterable[float | None]) -> bool | None:
    """Return whether any value is non-zero, or None when at least one value is missing."""
    collected = list(values)
    if any(value is None for value in collected):
        return None
    return any(value != 0 for value in collected)
