#!/usr/bin/env python3

"""
Tests for export selection, ordering, and writing.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2026 Amilcar Lucas

SPDX-License-Identifier: GPL-3.0-or-later
"""

import pytest

from ardupilot_methodic_configurator.data_model_ardupilot_parameter import ArduPilotParameter
from ardupilot_methodic_configurator.data_model_par_dict import Par
from ardupilot_methodic_configurator.data_model_parameter_export import (
    sorted_export_parameter_names,
)


def test_export_order_uses_numeric_fc_values_and_alphabetical_units() -> None:
    parameters = {
        name: ArduPilotParameter(name, Par(value), metadata={"unit": unit}, fc_value=value)
        for name, value, unit in (("ALPHA", 10.0, "s"), ("BRAVO", 2.0, "m"), ("CHARLIE", 7.0, "m"))
    }

    assert sorted_export_parameter_names(parameters, "fc_value") == ["BRAVO", "CHARLIE", "ALPHA"]
    assert sorted_export_parameter_names(parameters, "fc_value", descending=True) == ["ALPHA", "CHARLIE", "BRAVO"]
    assert sorted_export_parameter_names(parameters, "unit") == ["BRAVO", "CHARLIE", "ALPHA"]


def test_user_can_sort_names_and_units_in_both_directions() -> None:
    """
    Sort the export preview by the chosen heading.

    GIVEN: Parameter names and units in mixed order
    WHEN: The user selects a name or unit heading twice
    THEN: The model supplies alphabetical ascending and descending order
    """
    parameters = {
        name: ArduPilotParameter(name, Par(1.0), metadata={"unit": unit}, fc_value=1.0)
        for name, unit in (("Zulu", "s"), ("alpha", "m"), ("Bravo", "km"))
    }

    assert sorted_export_parameter_names(parameters, "name") == ["alpha", "Bravo", "Zulu"]
    assert sorted_export_parameter_names(parameters, "name", descending=True) == ["Zulu", "Bravo", "alpha"]
    assert sorted_export_parameter_names(parameters, "unit", descending=True) == ["Zulu", "alpha", "Bravo"]


def test_unknown_export_sort_column_is_rejected() -> None:
    """
    Reject unsupported sort headings.

    GIVEN: A parameter preview
    WHEN: A caller requests an unknown heading
    THEN: The model reports the invalid sort request
    """
    with pytest.raises(ValueError, match="Unknown export sort column"):
        sorted_export_parameter_names({}, "unsupported")
