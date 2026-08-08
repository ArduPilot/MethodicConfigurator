"""
Compass-specific rule helpers for vehicle overview extraction.

SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-FileCopyrightText: 2026 Omkar Sarkar <omkarsarkar24@gmail.com>

SPDX-License-Identifier: GPL-3.0-or-later
"""


def compass_external(params: dict[str, float], instance: int) -> bool | None:
    """Read COMPASS_EXTERNAL/2/3."""
    value = params.get("COMPASS_EXTERNAL") if instance == 1 else params.get(f"COMPASS_EXTERN{instance}")
    return None if value is None else value == 1


def compass_motor_calibrated(mot_values: list[float | None], motct_active: bool | None) -> bool | None:
    """Resolve motor-calibration state from offsets and COMPASS_MOTCT activation state."""
    if any(value is None for value in mot_values):
        return None

    offsets_set = any(value != 0 for value in mot_values)
    if motct_active is None:
        return offsets_set
    return offsets_set and motct_active
