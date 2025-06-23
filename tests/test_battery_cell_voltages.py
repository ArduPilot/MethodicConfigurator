#!/usr/bin/env python3

"""
Tests for the battery_cell_voltages.py file.

This file is part of Ardupilot methodic configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2025 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import unittest
from math import isnan

from ardupilot_methodic_configurator.battery_cell_voltages import BatteryCell, battery_cell_voltages


class TestBatteryCell(unittest.TestCase):  # pylint: disable=missing-class-docstring
    def test_chemistries(self) -> None:
        expected_chemistries = ("LiIon", "LiIonSS", "LiIonSSHV", "Lipo", "LipoHV", "LipoHVSS")
        chemistries = BatteryCell.chemistries()
        assert chemistries == expected_chemistries

    def test_limit_max_voltage(self) -> None:
        assert BatteryCell.limit_max_voltage("LiIon") == 4.2
        assert BatteryCell.limit_max_voltage("LipoHV") == 4.35
        assert BatteryCell.limit_max_voltage("NonExistentChemistry") == 4.45

    def test_limit_min_voltage(self) -> None:
        assert BatteryCell.limit_min_voltage("LiIon") == 2.5
        assert BatteryCell.limit_min_voltage("LipoHV") == 3.0
        assert BatteryCell.limit_min_voltage("NonExistentChemistry") == 2.4

    def test_recommended_max_voltage(self) -> None:
        assert BatteryCell.recommended_max_voltage("LiIon") == 4.1
        assert isnan(BatteryCell.recommended_max_voltage("NonExistentChemistry"))

    def test_recommended_low_voltage(self) -> None:
        assert BatteryCell.recommended_low_voltage("LiIon") == 3.1
        assert isnan(BatteryCell.recommended_low_voltage("NonExistentChemistry"))

    def test_recommended_crit_voltage(self) -> None:
        assert BatteryCell.recommended_crit_voltage("LiIon") == 2.8
        assert isnan(BatteryCell.recommended_crit_voltage("NonExistentChemistry"))

    def test_voltage_monoticity(self) -> None:
        for chemistry in BatteryCell.chemistries():
            with self.subTest(chemistry=chemistry):
                assert BatteryCell.limit_max_voltage(chemistry) == battery_cell_voltages[chemistry].get("absolute_max")
                assert BatteryCell.limit_min_voltage(chemistry) == battery_cell_voltages[chemistry].get("absolute_min")
                assert BatteryCell.limit_max_voltage(chemistry) >= BatteryCell.recommended_max_voltage(chemistry)
                assert BatteryCell.recommended_max_voltage(chemistry) >= BatteryCell.recommended_low_voltage(chemistry)
                assert BatteryCell.recommended_low_voltage(chemistry) >= BatteryCell.recommended_crit_voltage(chemistry)
                assert BatteryCell.recommended_crit_voltage(chemistry) >= BatteryCell.limit_min_voltage(chemistry)


if __name__ == "__main__":
    unittest.main()
