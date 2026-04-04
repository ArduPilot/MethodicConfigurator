#!/usr/bin/env python3

"""
Unit tests for the battery_cell_voltages.py file.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

from math import isnan

import pytest

from ardupilot_methodic_configurator.battery_cell_voltages import BatteryCell, _recommended_battery_cell_voltages


class TestBatteryCell:
    """Unit tests for the BatteryCell class."""

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

    @pytest.mark.parametrize("chem", BatteryCell.chemistries())
    def test_voltage_monotonicity(self, chem: str) -> None:
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

    def test_chemistry_voltage_score_returns_nan_for_non_positive_total_voltage(self) -> None:
        """chemistry_voltage_score returns nan when total_voltage is zero or negative."""
        # total_voltage <= 0 → early return nan (covers the branch at the very top of the function)
        assert isnan(BatteryCell.chemistry_voltage_score("Lipo", 0.0, "Volt per cell max"))
        assert isnan(BatteryCell.chemistry_voltage_score("Lipo", -1.0, "Volt per cell max"))

    def test_chemistry_voltage_score_returns_nan_for_unknown_chemistry(self) -> None:
        """chemistry_voltage_score returns nan when chemistry has no recommended volt-per-cell."""
        # recommended_cell_voltage returns nan for unknown chemistry → inner nan branch
        assert isnan(BatteryCell.chemistry_voltage_score("NonExistentChem", 16.8, "Volt per cell max"))

    def test_chemistry_voltage_score_returns_float_for_valid_inputs(self) -> None:
        """chemistry_voltage_score returns a non-nan float for valid chemistry, voltage and type."""
        score = BatteryCell.chemistry_voltage_score("Lipo", 16.8, "Volt per cell max")
        assert not isnan(score)
        assert 0.0 <= score < 0.5  # 16.8 / 4.2 = 4.0 cells → score should be 0.0

    def test_best_chemistry_for_voltage_returns_none_or_valid_chemistry_for_ambiguous_voltage(self) -> None:
        """best_chemistry_for_voltage may return None or a known chemistry for an ambiguous voltage."""
        # 10.0 V may be ambiguous depending on scoring; if a match is returned, it must be a known chemistry.
        result = BatteryCell.best_chemistry_for_voltage(10.0, "Volt per cell max")
        assert result is None or result in BatteryCell.chemistries()

    def test_best_chemistry_for_voltage_identifies_chemistry_for_4s_voltage(self) -> None:
        """best_chemistry_for_voltage returns a chemistry for a classic 4S full-charge voltage."""
        result = BatteryCell.best_chemistry_for_voltage(16.8, "Volt per cell max")
        # 16.8 / 4.2 = exactly 4.0 cells → a clear winner should be found
        assert result is not None
        assert isinstance(result, str)
        assert result in BatteryCell.chemistries()
