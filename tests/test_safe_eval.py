#!/usr/bin/env python3
"""
Tests for safe_eval.py.

This file is part of Ardupilot methodic configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import math

import pytest

from ardupilot_methodic_configurator.safe_eval import safe_eval


def test_basic_arithmetic() -> None:
    """Test basic arithmetic operations."""
    assert safe_eval("1+1") == 2
    assert safe_eval("1+-5") == -4
    assert safe_eval("-1") == -1
    assert safe_eval("-+1") == -1
    assert safe_eval("(100*10)+6") == 1006
    assert safe_eval("100*(10+6)") == 1600
    assert safe_eval("2**4") == 16
    assert pytest.approx(safe_eval("1.2345 * 10")) == 12.345


def test_math_functions() -> None:
    """Test mathematical functions."""
    assert safe_eval("sqrt(16)+1") == 5
    assert safe_eval("sin(0)") == 0
    assert safe_eval("cos(0)") == 1
    assert safe_eval("tan(0)") == 0
    assert safe_eval("log(1)") == 0
    assert safe_eval("exp(0)") == 1
    assert safe_eval("pi") == math.pi


def test_complex_expressions() -> None:
    """Test more complex mathematical expressions."""
    assert safe_eval("2 * (3 + 4)") == 14
    assert safe_eval("2 ** 3 * 4") == 32
    assert safe_eval("sqrt(16) + sqrt(9)") == 7
    assert safe_eval("sin(pi/2)") == 1


def test_error_cases() -> None:
    """Test error conditions."""
    with pytest.raises(SyntaxError):
        safe_eval("1 + ")  # Incomplete expression

    with pytest.raises(SyntaxError):
        safe_eval("unknown_func(10)")  # Unknown function

    with pytest.raises(SyntaxError):
        safe_eval("1 = 1")  # Invalid operator

    with pytest.raises(SyntaxError):
        safe_eval("import os")  # Attempted import


def test_nested_expressions() -> None:
    """Test nested mathematical expressions."""
    assert safe_eval("sqrt(pow(3,2) + pow(4,2))") == 5  # Pythagorean theorem
    assert safe_eval("log(exp(1))") == 1
    assert safe_eval("sin(pi/6)**2 + cos(pi/6)**2") == pytest.approx(1)


def test_division_by_zero() -> None:
    """Test division by zero handling."""
    with pytest.raises(ZeroDivisionError):
        safe_eval("1/0")
    with pytest.raises(ZeroDivisionError):
        safe_eval("10 % 0")


def test_invalid_math_functions() -> None:
    """Test invalid math function calls."""
    with pytest.raises(SyntaxError, match=r".*takes exactly one argument.*"):
        safe_eval("sin()")  # Missing argument
    with pytest.raises(SyntaxError, match=r".*takes exactly one argument.*"):
        safe_eval("sin(1,2)")  # Too many arguments
    with pytest.raises(ValueError, match=r"math domain error"):
        safe_eval("sqrt(-1)")  # Domain error
    with pytest.raises(ValueError, match=r"math domain error"):
        safe_eval("log(-1)")  # Range error
    with pytest.raises(SyntaxError, match=r"Unknown func.*"):
        safe_eval("unknown(1)")  # Unknown function


def test_security() -> None:
    """Test against code injection attempts."""
    with pytest.raises(SyntaxError):
        safe_eval("__import__('os').system('ls')")
    with pytest.raises(SyntaxError):
        safe_eval("open('/etc/passwd')")
    with pytest.raises(SyntaxError):
        safe_eval("eval('1+1')")


def test_operator_precedence() -> None:
    """Test operator precedence rules."""
    assert safe_eval("2 + 3 * 4") == 14
    assert safe_eval("(2 + 3) * 4") == 20
    assert safe_eval("-2 ** 2") == -4  # Exponentiation before negation
    assert safe_eval("-(2 ** 2)") == -4


def test_float_precision() -> None:
    """Test floating point precision handling."""
    assert pytest.approx(safe_eval("0.1 + 0.2")) == 0.3
    assert pytest.approx(safe_eval("sin(pi/2)")) == 1.0
    assert pytest.approx(safe_eval("cos(pi)")) == -1.0
    assert pytest.approx(safe_eval("exp(log(2.718281828))")) == math.e


def test_math_constants() -> None:
    """Test mathematical constants."""
    assert safe_eval("pi") == math.pi
    assert safe_eval("e") == math.e
    assert safe_eval("tau") == math.tau
    assert safe_eval("inf") == math.inf
    with pytest.raises(SyntaxError):
        safe_eval("not_a_constant")
