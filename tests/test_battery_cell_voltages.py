#!/usr/bin/env python3

"""
Tests for the battery_cell_voltages.py file.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import unittest
from math import isnan

from ardupilot_methodic_configurator.battery_cell_voltages import BatteryCell, _recommended_battery_cell_voltages


class TestBatteryCell(unittest.TestCase):  # pylint: disable=missing-class-docstring
    def test_chemistries(self) -> None:
        expected_chemistries = ("LiIon", "LiIonSS", "LiIonSSHV", "Lipo", "LipoHV", "LipoHVSS", "NiCd", "NiMH")
        chemistries = BatteryCell.chemistries()
        assert chemistries == expected_chemistries

    def test_limit_max_voltage(self) -> None:
        assert BatteryCell.limit_max_voltage("LiIon") == 4.2
        assert BatteryCell.limit_max_voltage("LipoHV") == 4.35
        assert BatteryCell.limit_max_voltage("NonExistentChemistry") == 4.45

    def test_limit_min_voltage(self) -> None:
        assert BatteryCell.limit_min_voltage("LiIon") == 2.5
        assert BatteryCell.limit_min_voltage("LipoHV") == 3.0
        assert BatteryCell.limit_min_voltage("NonExistentChemistry") == 1.0

    def test_recommended_max_voltage(self) -> None:
        assert BatteryCell.recommended_cell_voltage("LiIon", "Volt per cell max") == 4.1
        assert isnan(BatteryCell.recommended_cell_voltage("NonExistentChemistry", "Volt per cell max"))

    def test_recommended_low_voltage(self) -> None:
        assert BatteryCell.recommended_cell_voltage("LiIon", "Volt per cell low") == 3.1
        assert isnan(BatteryCell.recommended_cell_voltage("NonExistentChemistry", "Volt per cell low"))

    def test_recommended_crit_voltage(self) -> None:
        assert BatteryCell.recommended_cell_voltage("LiIon", "Volt per cell crit") == 2.8
        assert isnan(BatteryCell.recommended_cell_voltage("NonExistentChemistry", "Volt per cell crit"))

    def test_recommended_arm_voltage(self) -> None:
        assert BatteryCell.recommended_cell_voltage("LiIon", "Volt per cell arm") == 3.6
        assert isnan(BatteryCell.recommended_cell_voltage("NonExistentChemistry", "Volt per cell arm"))

    def test_recommended_min_voltage(self) -> None:
        assert BatteryCell.recommended_cell_voltage("LiIon", "Volt per cell min") == 2.7
        assert isnan(BatteryCell.recommended_cell_voltage("NonExistentChemistry", "Volt per cell min"))

    def test_voltage_monoticity(self) -> None:
        for chem in BatteryCell.chemistries():
            with self.subTest(chemistry=chem):
                assert BatteryCell.limit_max_voltage(chem) == _recommended_battery_cell_voltages[chem].get("absolute_max")
                assert BatteryCell.limit_min_voltage(chem) == _recommended_battery_cell_voltages[chem].get("absolute_min")
                assert BatteryCell.limit_max_voltage(chem) >= BatteryCell.recommended_cell_voltage(chem, "Volt per cell max")
                assert BatteryCell.recommended_cell_voltage(chem, "Volt per cell max") >= BatteryCell.recommended_cell_voltage(
                    chem, "Volt per cell arm"
                )
                assert BatteryCell.recommended_cell_voltage(chem, "Volt per cell arm") >= BatteryCell.recommended_cell_voltage(
                    chem, "Volt per cell low"
                )
                assert BatteryCell.recommended_cell_voltage(chem, "Volt per cell low") >= BatteryCell.recommended_cell_voltage(
                    chem, "Volt per cell crit"
                )
                # This is not required, the user might want to stop PID scaling above the critical voltage
                # assert BatteryCell.recommended_cell_voltage(chem, "Volt per cell crit") >=
                # BatteryCell.recommended_cell_voltage(chem, "Volt per cell min")
                assert BatteryCell.recommended_cell_voltage(chem, "Volt per cell min") >= BatteryCell.limit_min_voltage(chem)
                assert BatteryCell.recommended_cell_voltage(chem, "Volt per cell crit") >= BatteryCell.limit_min_voltage(chem)


if __name__ == "__main__":
    unittest.main()
