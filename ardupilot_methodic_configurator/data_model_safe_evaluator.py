"""
Safe expression evaluator for configuration step parameter processing.

Replaces Python's built-in expression evaluation with simpleeval to prevent
arbitrary code execution from user-controlled JSON configuration files.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

from math import log
from types import MappingProxyType
from typing import Union

from simpleeval import simple_eval

SAFE_FUNCTIONS = MappingProxyType(
    {
        "max": max,
        "min": min,
        "round": round,
        "abs": abs,
        "len": len,
        "log": log,
    }
)


def safe_evaluate(expression: str, variables: dict) -> Union[int, float, str]:
    """
    Evaluate a parameter expression safely using simpleeval.

    Only arithmetic, comparisons, ternary conditionals, dict lookups,
    and whitelisted functions (max, min, round, abs, len, log) are allowed.
    Any attempt to call __import__, access dunder attributes, or use
    disallowed constructs will raise an exception.

    Args:
        expression: The expression string from a configuration step JSON file.
        variables: A dictionary of variable names available during evaluation.

    Returns:
        The result of evaluating the expression.

    Raises:
        InvalidExpression: If the expression uses a disallowed feature,
            calls an unknown function, or references an undefined variable.

    """
    return simple_eval(expression, names=variables, functions=SAFE_FUNCTIONS)
