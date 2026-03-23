"""
Battery cell recommended voltages.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

from math import isnan, nan
from typing import Optional

BATTERY_CELL_VOLTAGE_TYPES: tuple[str, ...] = (
    "Volt per cell max",
    "Volt per cell arm",
    "Volt per cell low",
    "Volt per cell crit",
    "Volt per cell min",
)

_recommended_battery_cell_voltages = {
    "LiIon": {
        "absolute_max": 4.2,
        "absolute_min": 2.5,
        "Volt per cell max": 4.1,
        "Volt per cell arm": 3.6,
        "Volt per cell low": 3.1,
        "Volt per cell crit": 2.8,
        "Volt per cell min": 2.7,
    },
    "LiIonSS": {
        "absolute_max": 4.2,
        "absolute_min": 2.4,
        "Volt per cell max": 4.2,
        "Volt per cell arm": 3.6,
        "Volt per cell low": 3.0,
        "Volt per cell crit": 2.7,
        "Volt per cell min": 2.6,
    },
    "LiIonSSHV": {
        "absolute_max": 4.45,
        "absolute_min": 2.4,
        "Volt per cell max": 4.45,
        "Volt per cell arm": 3.8,
        "Volt per cell low": 3.0,
        "Volt per cell crit": 2.7,
        "Volt per cell min": 2.6,
    },
    "Lipo": {
        "absolute_max": 4.2,
        "absolute_min": 3.0,
        "Volt per cell max": 4.2,
        "Volt per cell arm": 3.8,
        "Volt per cell low": 3.6,
        "Volt per cell crit": 3.3,
        "Volt per cell min": 3.2,
    },
    "LipoHV": {
        "absolute_max": 4.35,
        "absolute_min": 3.0,
        "Volt per cell max": 4.35,
        "Volt per cell arm": 3.9,
        "Volt per cell low": 3.6,
        "Volt per cell crit": 3.3,
        "Volt per cell min": 3.2,
    },
    "LipoHVSS": {
        "absolute_max": 4.2,
        "absolute_min": 2.9,
        "Volt per cell max": 4.2,
        "Volt per cell arm": 3.8,
        "Volt per cell low": 3.5,
        "Volt per cell crit": 3.2,
        "Volt per cell min": 3.1,
    },
    "NiCd": {
        "absolute_max": 1.45,
        "absolute_min": 1.0,
        "Volt per cell max": 1.4,
        "Volt per cell arm": 1.28,
        "Volt per cell low": 1.2,
        "Volt per cell crit": 1.1,
        "Volt per cell min": 1.05,
    },
    "NiMH": {
        "absolute_max": 1.45,
        "absolute_min": 1.0,
        "Volt per cell max": 1.4,
        "Volt per cell arm": 1.28,
        "Volt per cell low": 1.2,
        "Volt per cell crit": 1.1,
        "Volt per cell min": 1.05,
    },
    # Add more chemistries as needed
}


class BatteryCell:
    """
    Battery cell voltages for different chemistries.

    It includes methods to get the tuple of chemistries, limit voltages based on chemistry type,
    and get recommended voltages for a given chemistry.
    """

    @staticmethod
    def chemistries() -> tuple[str, ...]:
        return tuple(_recommended_battery_cell_voltages.keys())

    @staticmethod
    def limit_max_voltage(chemistry: str) -> float:
        max_abs_max = max(chemistry["absolute_max"] for chemistry in _recommended_battery_cell_voltages.values())
        if chemistry not in _recommended_battery_cell_voltages:
            return max_abs_max
        return _recommended_battery_cell_voltages[chemistry].get("absolute_max", max_abs_max)

    @staticmethod
    def limit_min_voltage(chemistry: str) -> float:
        min_abs_min = min(chemistry["absolute_min"] for chemistry in _recommended_battery_cell_voltages.values())
        if chemistry not in _recommended_battery_cell_voltages:
            return min_abs_min
        return _recommended_battery_cell_voltages[chemistry].get("absolute_min", min_abs_min)

    @staticmethod
    def recommended_cell_voltage(chemistry: str, voltage_type: str) -> float:
        if chemistry not in _recommended_battery_cell_voltages:
            return nan
        return _recommended_battery_cell_voltages[chemistry].get(voltage_type, nan)

    @staticmethod
    def chemistry_voltage_score(chemistry: str, total_voltage: float, voltage_type: str) -> float:
        """
        Score how well a chemistry matches a total pack voltage for a given voltage type.

        Returns abs(estimated_cells - round(estimated_cells)), i.e. 0.0 is a perfect
        integer cell count. Returns nan if the chemistry has no valid volt-per-cell for
        this voltage type or if total_voltage is not positive.
        """
        if total_voltage <= 0:
            return nan
        volt_per_cell = BatteryCell.recommended_cell_voltage(chemistry, voltage_type)
        if isnan(volt_per_cell) or volt_per_cell <= 0:
            return nan
        estimated_cells = total_voltage / volt_per_cell
        return abs(estimated_cells - round(estimated_cells))

    @staticmethod
    def best_chemistry_for_voltage(total_voltage: float, voltage_type: str) -> Optional[str]:
        """
        Return the chemistry whose recommended cell voltage gives the most integer-like cell count.

        Returns the chemistry name if a clear winner is found (score < 0.03),
        otherwise returns None.
        """
        best_chemistry: Optional[str] = None
        best_score = float("inf")
        for chemistry in _recommended_battery_cell_voltages:
            score = BatteryCell.chemistry_voltage_score(chemistry, total_voltage, voltage_type)
            if not isnan(score) and score < best_score:
                best_score = score
                best_chemistry = chemistry
        if best_chemistry is not None and best_score < 0.03:
            return best_chemistry
        return None
