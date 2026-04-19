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
from typing import Union, cast

from simpleeval import InvalidExpression, simple_eval

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


class ConfigurationStepEvalError(Exception):
    """
    Raised when evaluating a configuration step expression fails.

    Wraps the full exception surface of :func:`safe_evaluate` so callers
    can catch a single domain-level exception instead of enumerating
    every error type that simpleeval, Python arithmetic, or dict
    lookups inside the evaluated expression can raise. The original
    exception is preserved as ``__cause__`` and its class name is
    included in the string form for diagnostics.
    """


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
        ConfigurationStepEvalError: If the expression is malformed,
            references an undefined name or missing dict key, performs a
            disallowed operation, or triggers a runtime error
            (ZeroDivisionError, OverflowError, ValueError, TypeError,
            AttributeError) while evaluating. The original exception is
            attached as ``__cause__``.

    """
    try:
        return cast("Union[int, float, str]", simple_eval(expression, names=variables, functions=SAFE_FUNCTIONS))
    except (
        InvalidExpression,
        SyntaxError,
        KeyError,
        TypeError,
        AttributeError,
        ZeroDivisionError,
        OverflowError,
        ValueError,
    ) as e:
        msg = f"{type(e).__name__}: {e}"
        raise ConfigurationStepEvalError(msg) from e
