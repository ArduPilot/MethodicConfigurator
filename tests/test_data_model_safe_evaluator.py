#!/usr/bin/env python3

"""
Tests for data_model_safe_evaluator.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import pytest
from simpleeval import NameNotDefined

from ardupilot_methodic_configurator.data_model_safe_evaluator import (
    ConfigurationStepEvalError,
    safe_evaluate,
)


class TestSafeEvaluateSuccess:
    """Test that successful expressions still return the expected value."""

    def test_evaluates_literal_integer(self) -> None:
        """
        A bare integer literal is returned unchanged.

        GIVEN: The expression '42' and no variables
        WHEN: safe_evaluate is called
        THEN: The integer 42 is returned
        """
        assert safe_evaluate("42", {}) == 42

    def test_evaluates_arithmetic_with_variables(self) -> None:
        """
        An arithmetic expression using supplied variables is evaluated correctly.

        GIVEN: The expression 'a * b + c' and variables {a: 2, b: 3, c: 4}
        WHEN: safe_evaluate is called
        THEN: The result 10 is returned
        """
        assert safe_evaluate("a * b + c", {"a": 2, "b": 3, "c": 4}) == 10

    def test_evaluates_fc_parameters_subscript(self) -> None:
        """
        Subscript access into fc_parameters returns the looked-up value.

        GIVEN: An fc_parameters dict with a numeric entry
        WHEN: safe_evaluate indexes it by key
        THEN: The stored value is returned
        """
        assert safe_evaluate("fc_parameters['INS_GYRO_FILTER']", {"fc_parameters": {"INS_GYRO_FILTER": 20.0}}) == 20.0


class TestSafeEvaluateWrapsExceptions:
    """Test that the full exception surface is wrapped in ConfigurationStepEvalError."""

    def test_wraps_undefined_name(self) -> None:
        """
        Referencing a name that is not in the variables dict raises ConfigurationStepEvalError.

        GIVEN: An expression referencing an undefined bare name
        WHEN: safe_evaluate is called
        THEN: ConfigurationStepEvalError is raised
        AND: The original NameNotDefined is preserved as __cause__
        """
        with pytest.raises(ConfigurationStepEvalError) as excinfo:
            safe_evaluate("UNKNOWN_NAME + 1", {})
        assert "NameNotDefined" in str(excinfo.value)
        assert isinstance(excinfo.value.__cause__, NameNotDefined)

    def test_wraps_missing_dict_key(self) -> None:
        """
        A subscript into a dict with a missing key raises ConfigurationStepEvalError.

        GIVEN: fc_parameters does not contain 'MISSING'
        WHEN: safe_evaluate tries to subscript fc_parameters['MISSING']
        THEN: ConfigurationStepEvalError is raised
        AND: The original KeyError is preserved as __cause__
        AND: The missing key is mentioned in the error message
        """
        with pytest.raises(ConfigurationStepEvalError) as excinfo:
            safe_evaluate("fc_parameters['MISSING']", {"fc_parameters": {}})
        assert "KeyError" in str(excinfo.value)
        assert "MISSING" in str(excinfo.value)
        assert isinstance(excinfo.value.__cause__, KeyError)

    def test_wraps_zero_division(self) -> None:
        """
        Dividing by zero inside an expression raises ConfigurationStepEvalError.

        GIVEN: A denominator of zero in the expression
        WHEN: safe_evaluate is called
        THEN: ConfigurationStepEvalError is raised wrapping ZeroDivisionError
        """
        with pytest.raises(ConfigurationStepEvalError) as excinfo:
            safe_evaluate("1 / 0", {})
        assert "ZeroDivisionError" in str(excinfo.value)
        assert isinstance(excinfo.value.__cause__, ZeroDivisionError)

    def test_wraps_math_domain_error(self) -> None:
        """
        A math domain error (log of zero) raises ConfigurationStepEvalError.

        GIVEN: log(0), which is mathematically undefined
        WHEN: safe_evaluate is called
        THEN: ConfigurationStepEvalError is raised wrapping ValueError
        """
        with pytest.raises(ConfigurationStepEvalError) as excinfo:
            safe_evaluate("log(0)", {})
        assert "ValueError" in str(excinfo.value)
        assert isinstance(excinfo.value.__cause__, ValueError)

    def test_wraps_type_error(self) -> None:
        """
        An operand type mismatch raises ConfigurationStepEvalError.

        GIVEN: A string added to an integer
        WHEN: safe_evaluate is called
        THEN: ConfigurationStepEvalError is raised wrapping TypeError
        """
        with pytest.raises(ConfigurationStepEvalError) as excinfo:
            safe_evaluate("'abc' + 1", {})
        assert "TypeError" in str(excinfo.value)
        assert isinstance(excinfo.value.__cause__, TypeError)

    def test_wraps_disallowed_feature(self) -> None:
        """
        Using a non-whitelisted function raises ConfigurationStepEvalError.

        GIVEN: An expression that calls a function not in SAFE_FUNCTIONS
        WHEN: safe_evaluate is called
        THEN: ConfigurationStepEvalError is raised
        """
        with pytest.raises(ConfigurationStepEvalError):
            safe_evaluate("open('/etc/passwd')", {})


class TestSafeEvaluateIntAndBitshift:
    """Test that int() and bitshift expressions work correctly."""

    def test_int_converts_float_fc_parameter(self) -> None:
        """
        int() applied to a float fc_parameter value returns the integer part.

        GIVEN: fc_parameters contains EK3_PRIMARY as a float (as returned by ArduPilot)
        WHEN: safe_evaluate evaluates int(fc_parameters['EK3_PRIMARY'])
        THEN: The integer value 0 is returned
        """
        result = safe_evaluate("int(fc_parameters['EK3_PRIMARY'])", {"fc_parameters": {"EK3_PRIMARY": 0.0}})
        assert result == 0
        assert isinstance(result, int)

    def test_int_converts_nonzero_float_fc_parameter(self) -> None:
        """
        int() converts a non-zero float fc_parameter value to an integer.

        GIVEN: fc_parameters contains EK3_PRIMARY as 2.0
        WHEN: safe_evaluate evaluates int(fc_parameters['EK3_PRIMARY'])
        THEN: The integer value 2 is returned
        """
        result = safe_evaluate("int(fc_parameters['EK3_PRIMARY'])", {"fc_parameters": {"EK3_PRIMARY": 2.0}})
        assert result == 2
        assert isinstance(result, int)

    def test_bitshift_with_int_fc_parameter(self) -> None:
        """
        A left bitshift using int() on an fc_parameter produces the correct bitmask.

        GIVEN: fc_parameters contains EK3_PRIMARY as 0.0 (primary EKF index 0)
        WHEN: safe_evaluate evaluates 1 << int(fc_parameters['EK3_PRIMARY'])
        THEN: The bitmask 1 (bit 0 set) is returned
        """
        result = safe_evaluate("1 << int(fc_parameters['EK3_PRIMARY'])", {"fc_parameters": {"EK3_PRIMARY": 0.0}})
        assert result == 1

    def test_bitshift_with_nonzero_int_fc_parameter(self) -> None:
        """
        A left bitshift by a non-zero integer index produces the correct bitmask.

        GIVEN: fc_parameters contains EK3_PRIMARY as 2.0 (primary EKF index 2)
        WHEN: safe_evaluate evaluates 1 << int(fc_parameters['EK3_PRIMARY'])
        THEN: The bitmask 4 (bit 2 set) is returned
        """
        result = safe_evaluate("1 << int(fc_parameters['EK3_PRIMARY'])", {"fc_parameters": {"EK3_PRIMARY": 2.0}})
        assert result == 4

    def test_bitshift_conditional_expression(self) -> None:
        """
        A full INS_LOG_BAT_MASK conditional expression evaluates to the correct bitmask.

        GIVEN: fc_parameters has EK3_PRIMARY=1.0 and vehicle_components indicates an F4 processor
        WHEN: safe_evaluate evaluates the full derived parameter expression
        THEN: The bitmask 2 (1 << 1) is returned
        """
        variables = {
            "fc_parameters": {"EK3_PRIMARY": 1.0},
            "vehicle_components": {
                "Flight Controller": {"Specifications": {"MCU Series": "STM32F4"}},
                "Propellers": {"Specifications": {"Diameter_inches": 10}},
            },
        }
        expression = (
            "1 << int(fc_parameters['EK3_PRIMARY']) if 'F4' in "
            "vehicle_components['Flight Controller']['Specifications']['MCU Series'] or "
            "vehicle_components['Propellers']['Specifications']['Diameter_inches'] >= 15 else 0"
        )
        assert safe_evaluate(expression, variables) == 2
