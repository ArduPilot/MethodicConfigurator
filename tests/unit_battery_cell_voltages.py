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

    @pytest.mark.parametrize("chemistry", BatteryCell.chemistries())
    def test_unknown_voltage_recommendations_are_unavailable(self, chemistry: str) -> None:
        """
        An unsupported voltage setting has no recommendation for a known chemistry.

        GIVEN: A supported battery chemistry and an unknown voltage setting
        WHEN: A recommendation is requested for that setting
        THEN: The result is NaN, matching other unavailable recommendations
        """
        # Act (When): Request a setting absent from the chemistry's recommendations.
        recommendation = BatteryCell.recommended_cell_voltage(chemistry, "Unknown voltage setting")

        # Assert (Then): Missing recommendations retain the numeric unavailable sentinel.
        assert isnan(recommendation)

    def test_positive_pack_voltages_below_one_volt_can_be_scored(self) -> None:
        """
        Small positive voltage readings remain valid inputs to chemistry scoring.

        GIVEN: A NiMH recommendation of 1.4 volts per cell and a 0.7 volt reading
        WHEN: The reading is scored against the maximum cell voltage
        THEN: The half-cell estimate has a distance of 0.5 from a whole cell count
        """
        # Act (When): Score a positive reading below one volt.
        score = BatteryCell.chemistry_voltage_score("NiMH", 0.7, "Volt per cell max")

        # Assert (Then): Positive readings are scored rather than discarded as unavailable.
        assert score == pytest.approx(0.5)

    def test_one_volt_cell_limits_can_be_used_as_scoring_references(self) -> None:
        """
        A one-volt reference remains a valid basis for estimating cell counts.

        GIVEN: NiMH cells with an absolute minimum of one volt per cell
        WHEN: A four-volt pack is scored against that lower limit
        THEN: The four-cell estimate is an exact match
        """
        # Act (When): Use the chemistry's absolute lower limit as the reference.
        score = BatteryCell.chemistry_voltage_score("NiMH", 4.0, "absolute_min")

        # Assert (Then): A positive one-volt reference is accepted.
        assert score == 0.0

    @pytest.mark.parametrize("cell_voltage", [0.0, -1.0])
    def test_invalid_cell_recommendations_cannot_produce_a_chemistry_score(
        self, monkeypatch: pytest.MonkeyPatch, cell_voltage: float
    ) -> None:
        """
        Invalid reference data cannot produce a match or cause division by zero.

        GIVEN: A chemistry recommendation contains a non-positive cell voltage
        WHEN: A positive pack reading is scored against that recommendation
        THEN: The score is unavailable instead of raising or suggesting a match
        """
        # Arrange (Given): Override only the reference data; run the real scoring methods.
        monkeypatch.setitem(_recommended_battery_cell_voltages["Lipo"], "Volt per cell max", cell_voltage)

        # Act (When): Score the pack using the invalid reference.
        score = BatteryCell.chemistry_voltage_score("Lipo", 16.8, "Volt per cell max")

        # Assert (Then): Invalid cell voltages cannot participate in chemistry selection.
        assert isnan(score)

    def test_uncertain_pack_voltages_do_not_suggest_a_chemistry(self) -> None:
        """
        A poor match requires the user to select the chemistry explicitly.

        GIVEN: A ten-volt pack with no chemistry closer than 0.03 to a whole cell count
        WHEN: A chemistry suggestion is requested from the maximum cell voltage
        THEN: No chemistry is suggested
        """
        # Act (When): Request a recommendation for an uncertain pack voltage.
        result = BatteryCell.best_chemistry_for_voltage(10.0, "Volt per cell max")

        # Assert (Then): An arbitrary known chemistry is not a valid recommendation.
        assert result is None

    def test_equal_chemistry_matches_preserve_the_first_recommendation(self) -> None:
        """
        Equally good matches produce a stable recommendation in chemistry order.

        GIVEN: A 16.8 volt pack matches LiIonSS, Lipo, and LipoHVSS equally well
        WHEN: A chemistry suggestion is requested from the maximum cell voltage
        THEN: LiIonSS, the first exact match in chemistry order, is suggested
        """
        # Act (When): Request a suggestion where multiple chemistries share the best score.
        result = BatteryCell.best_chemistry_for_voltage(16.8, "Volt per cell max")

        # Assert (Then): Later equal or worse matches cannot replace the first best match.
        assert result == "LiIonSS"

    @pytest.mark.parametrize(
        ("total_voltage", "expected_chemistry"),
        [
            pytest.param(0.1335 - 1e-9, "LiIonSSHV", id="below-threshold"),
            pytest.param(0.1335, None, id="at-threshold"),
            pytest.param(0.1335 + 1e-9, None, id="above-threshold"),
        ],
    )
    def test_chemistry_suggestions_require_a_score_strictly_below_the_confidence_limit(
        self, total_voltage: float, expected_chemistry: str | None
    ) -> None:
        """
        The confidence boundary is exclusive when deciding whether to suggest a chemistry.

        GIVEN: A small reading whose closest match is near the 0.03 score limit
        WHEN: A chemistry suggestion is requested from the maximum cell voltage
        THEN: A chemistry is suggested only below the limit, including no match at equality
        """
        # Arrange (Given): 0.1335 / 4.45 is exactly the floating-point value 0.03.
        # This small reading makes the equality case exact, without rounding a multi-cell estimate.

        # Act (When): Apply the real scoring and recommendation logic around the boundary.
        result = BatteryCell.best_chemistry_for_voltage(total_voltage, "Volt per cell max")

        # Assert (Then): Equality cannot turn an uncertain reading into a recommendation.
        assert result == expected_chemistry
