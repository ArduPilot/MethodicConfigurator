#!/usr/bin/env python3

"""
This file is part of Ardupilot methodic configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

from math import nan

battery_cell_voltages = {
    "LiIon": {
        "absolute_max": 4.1,
        "absolute_min": 2.5,
        "recommended_max": 4.1,
        "recommended_low": 3.1,
        "recommended_crit": 2.8,
    },
    "LiIonSS": {
        "absolute_max": 4.2,
        "absolute_min": 2.4,
        "recommended_max": 4.2,
        "recommended_low": 3.0,
        "recommended_crit": 2.7,
    },
    "LiIonSSHV": {
        "absolute_max": 4.45,
        "absolute_min": 2.4,
        "recommended_max": 4.45,
        "recommended_low": 3.0,
        "recommended_crit": 2.7,
    },
    "Lipo": {
        "absolute_max": 4.2,
        "absolute_min": 3.0,
        "recommended_max": 4.2,
        "recommended_low": 3.6,
        "recommended_crit": 3.3,
    },
    "LipoHV": {
        "absolute_max": 4.35,
        "absolute_min": 3.0,
        "recommended_max": 4.35,
        "recommended_low": 3.6,
        "recommended_crit": 3.3,
    },
    "LipoHVSS": {
        "absolute_max": 4.2,
        "absolute_min": 2.9,
        "recommended_max": 4.2,
        "recommended_low": 3.5,
        "recommended_crit": 3.2,
    },
    # Add more chemistries as needed
}


class BatteryCell:
    """
    This class provides methods to work with battery cell voltages for different chemistries.

    It includes methods to get the list of chemistries, limit voltages based on chemistry type,
    and get recommended voltages for a given chemistry.
    """

    @staticmethod
    def chemistries() -> list:
        return list(battery_cell_voltages.keys())

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
        return battery_cell_voltages[chemistry].get("recommended_max", 4.2)

    @staticmethod
    def recommended_low_voltage(chemistry: str) -> float:
        if chemistry not in battery_cell_voltages:
            return nan
        return battery_cell_voltages[chemistry].get("recommended_low", 3.6)

    @staticmethod
    def recommended_crit_voltage(chemistry: str) -> float:
        if chemistry not in battery_cell_voltages:
            return nan
        return battery_cell_voltages[chemistry].get("recommended_crit", 3.3)
