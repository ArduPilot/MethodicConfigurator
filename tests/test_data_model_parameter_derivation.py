#!/usr/bin/env python3

"""
Tests for the configuration step parameter derivation service.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-FileCopyrightText: 2026 Omkar Sarkar <omkarsarkar24@gmail.com>

SPDX-License-Identifier: GPL-3.0-or-later
"""

from ardupilot_methodic_configurator.log_analysis.data_model_parameter_derivation import (
    ConfigurationStepParameterDeriver,
    ParameterDerivationInputs,
)


def _inputs(**overrides) -> ParameterDerivationInputs:
    defaults = {
        "configuration_steps": {},
        "parameters": {},
        "vehicle_components": {},
        "apm_doc": None,
    }
    defaults.update(overrides)
    return ParameterDerivationInputs(**defaults)


def test_expected_parameter_value_returns_none_when_step_missing() -> None:
    derivation = ConfigurationStepParameterDeriver()

    value, source = derivation.expected_parameter_value("11_battery.param", "BATT_CAPACITY", _inputs())

    assert value is None
    assert source == ""


def test_expected_parameter_value_returns_forced_parameter() -> None:
    derivation = ConfigurationStepParameterDeriver()
    configuration_steps = {
        "16_safety_setup.param": {
            "forced_parameters": {"ARMING_CHECK": {"New Value": 1, "Change Reason": "Perform all arming checks"}}
        }
    }

    value, source = derivation.expected_parameter_value(
        "16_safety_setup.param", "ARMING_CHECK", _inputs(configuration_steps=configuration_steps)
    )

    assert value == 1
    assert source == "forced"


def test_expected_parameter_value_returns_derived_parameter() -> None:
    derivation = ConfigurationStepParameterDeriver()
    configuration_steps = {
        "11_battery.param": {
            "derived_parameters": {
                "BATT_CAPACITY": {
                    "New Value": "vehicle_components['Battery']['Specifications']['Capacity mAh']",
                    "Change Reason": "Total battery capacity specified in the component editor",
                }
            }
        }
    }
    vehicle_components = {"Battery": {"Specifications": {"Capacity mAh": 1550}}}

    value, source = derivation.expected_parameter_value(
        "11_battery.param",
        "BATT_CAPACITY",
        _inputs(configuration_steps=configuration_steps, vehicle_components=vehicle_components),
    )

    assert value == 1550
    assert source == "derived"


def test_expected_parameter_value_returns_none_when_param_not_in_step() -> None:
    derivation = ConfigurationStepParameterDeriver()
    configuration_steps = {
        "11_battery.param": {"forced_parameters": {"BATT_FS_CRT_ACT": {"New Value": 1, "Change Reason": "Land ASAP"}}}
    }

    value, source = derivation.expected_parameter_value(
        "11_battery.param", "BATT_CAPACITY", _inputs(configuration_steps=configuration_steps)
    )

    assert value is None
    assert source == ""


def test_derived_and_forced_parameters_matching_returns_all_matches_across_steps() -> None:
    derivation = ConfigurationStepParameterDeriver()
    configuration_steps = {
        "16_safety_setup.param": {"forced_parameters": {"ARMING_CHECK": {}, "ARMING_SKIPCHK": {}}},
        "20_esc.param": {"add_parameters": {"MOT_SPIN_ARM": {}}},
        "22_motor_notch_logging.param": {"derived_parameters": {"INS_LOG_BAT_MASK": {}}},
    }

    matches = derivation.derived_and_forced_parameters_matching(
        r"^ARMING_.*", _inputs(configuration_steps=configuration_steps)
    )

    assert matches == {"ARMING_CHECK": "16_safety_setup.param", "ARMING_SKIPCHK": "16_safety_setup.param"}


def test_derived_and_forced_parameters_matching_ignores_add_parameters() -> None:
    derivation = ConfigurationStepParameterDeriver()
    configuration_steps = {"20_esc.param": {"add_parameters": {"MOT_SPIN_ARM": {}}}}

    matches = derivation.derived_and_forced_parameters_matching(r"^MOT_.*", _inputs(configuration_steps=configuration_steps))

    assert not matches


def test_derived_and_forced_parameters_matching_returns_empty_when_no_match() -> None:
    derivation = ConfigurationStepParameterDeriver()
    configuration_steps = {"11_battery.param": {"forced_parameters": {"BATT_FS_CRT_ACT": {}}}}

    matches = derivation.derived_and_forced_parameters_matching(r"^GPS_.*", _inputs(configuration_steps=configuration_steps))

    assert not matches
