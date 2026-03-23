"""
Battery cell voltages management.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

from math import nan

battery_cell_voltages = {
    "LiIon": {
        "absolute_max": 4.2,
        "absolute_min": 2.5,
        "recommended_max": 4.1,
        "recommended_arm": 3.6,
        "recommended_low": 3.1,
        "recommended_crit": 2.8,
        "recommended_min": 2.7,
    },
    "LiIonSS": {
        "absolute_max": 4.2,
        "absolute_min": 2.4,
        "recommended_max": 4.2,
        "recommended_arm": 3.6,
        "recommended_low": 3.0,
        "recommended_crit": 2.7,
        "recommended_min": 2.6,
    },
    "LiIonSSHV": {
        "absolute_max": 4.45,
        "absolute_min": 2.4,
        "recommended_max": 4.45,
        "recommended_arm": 3.8,
        "recommended_low": 3.0,
        "recommended_crit": 2.7,
        "recommended_min": 2.6,
    },
    "Lipo": {
        "absolute_max": 4.2,
        "absolute_min": 3.0,
        "recommended_max": 4.2,
        "recommended_arm": 3.8,
        "recommended_low": 3.6,
        "recommended_crit": 3.3,
        "recommended_min": 3.2,
    },
    "LipoHV": {
        "absolute_max": 4.35,
        "absolute_min": 3.0,
        "recommended_max": 4.35,
        "recommended_arm": 3.9,
        "recommended_low": 3.6,
        "recommended_crit": 3.3,
        "recommended_min": 3.2,
    },
    "LipoHVSS": {
        "absolute_max": 4.2,
        "absolute_min": 2.9,
        "recommended_max": 4.2,
        "recommended_arm": 3.8,
        "recommended_low": 3.5,
        "recommended_crit": 3.2,
        "recommended_min": 3.1,
    },
    "NiCd": {
        "absolute_max": 1.45,
        "absolute_min": 1.0,
        "recommended_max": 1.4,
        "recommended_arm": 1.28,
        "recommended_low": 1.2,
        "recommended_crit": 1.1,
        "recommended_min": 1.05,
    },
    "NiMH": {
        "absolute_max": 1.45,
        "absolute_min": 1.0,
        "recommended_max": 1.4,
        "recommended_arm": 1.28,
        "recommended_low": 1.2,
        "recommended_crit": 1.1,
        "recommended_min": 1.05,
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
        return tuple(battery_cell_voltages.keys())

    @staticmethod
    def limit_max_voltage(chemistry: str) -> float:
        max_abs_max = max(chemistry["absolute_max"] for chemistry in battery_cell_voltages.values())
        if chemistry not in battery_cell_voltages:
            return max_abs_max
        return battery_cell_voltages[chemistry].get("absolute_max", max_abs_max)

    @staticmethod
    def limit_min_voltage(chemistry: str) -> float:
        min_abs_min = min(chemistry["absolute_min"] for chemistry in battery_cell_voltages.values())
        if chemistry not in battery_cell_voltages:
            return min_abs_min
        return battery_cell_voltages[chemistry].get("absolute_min", min_abs_min)

    @staticmethod
    def recommended_max_voltage(chemistry: str) -> float:
        if chemistry not in battery_cell_voltages:
            return nan
        return battery_cell_voltages[chemistry].get("recommended_max", nan)

    @staticmethod
    def recommended_arm_voltage(chemistry: str) -> float:
        if chemistry not in battery_cell_voltages:
            return nan
        return battery_cell_voltages[chemistry].get("recommended_arm", nan)

    @staticmethod
    def recommended_low_voltage(chemistry: str) -> float:
        if chemistry not in battery_cell_voltages:
            return nan
        return battery_cell_voltages[chemistry].get("recommended_low", nan)

    @staticmethod
    def recommended_crit_voltage(chemistry: str) -> float:
        if chemistry not in battery_cell_voltages:
            return nan
        return battery_cell_voltages[chemistry].get("recommended_crit", nan)

    @staticmethod
    def recommended_min_voltage(chemistry: str) -> float:
        if chemistry not in battery_cell_voltages:
            return nan
        return battery_cell_voltages[chemistry].get("recommended_min", nan)
