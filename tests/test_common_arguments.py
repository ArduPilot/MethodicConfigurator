#!/usr/bin/env python3

"""
Tests for the common_arguments.py file.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import argparse
from argparse import ArgumentParser

import pytest

from ardupilot_methodic_configurator.common_arguments import add_common_arguments
from ardupilot_methodic_configurator.internationalization import LANGUAGE_CHOICES

# pylint: disable=redefined-outer-name


@pytest.fixture
def parser() -> ArgumentParser:
    """Fixture providing a fresh ArgumentParser with common arguments registered."""
    return add_common_arguments(ArgumentParser())


@pytest.fixture
def defaults(parser: ArgumentParser) -> argparse.Namespace:
    """Fixture providing parsed args with no CLI arguments — all defaults in effect."""
    return parser.parse_args([])


# ---------------------------------------------------------------------------
# --loglevel
# ---------------------------------------------------------------------------


def test_loglevel_defaults_to_info(defaults: argparse.Namespace) -> None:
    """
    --loglevel defaults to INFO when not specified.

    GIVEN: A parser with common arguments registered
    WHEN: No --loglevel argument is supplied
    THEN: The parsed loglevel is 'INFO'
    """
    assert defaults.loglevel == "INFO"


@pytest.mark.parametrize("level", ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"])
def test_loglevel_accepts_all_valid_choices(parser: ArgumentParser, level: str) -> None:
    """
    --loglevel accepts every valid log-level string without error.

    GIVEN: A parser with common arguments registered
    WHEN: --loglevel is set to a valid level
    THEN: The parsed loglevel matches the supplied value
    """
    args = parser.parse_args(["--loglevel", level])
    assert args.loglevel == level


def test_loglevel_rejects_invalid_choice(parser: ArgumentParser) -> None:
    """
    --loglevel rejects unknown log-level strings with exit code 2.

    GIVEN: A parser with common arguments registered
    WHEN: --loglevel is set to an unrecognised value
    THEN: argparse exits with code 2 (argument error)
    """
    with pytest.raises(SystemExit) as exc_info:
        parser.parse_args(["--loglevel", "VERBOSE"])
    assert exc_info.value.code == 2


# ---------------------------------------------------------------------------
# --language
# ---------------------------------------------------------------------------


def test_language_defaults_to_first_language_choice(defaults: argparse.Namespace) -> None:
    """
    --language defaults to the first entry in LANGUAGE_CHOICES ('en').

    GIVEN: A parser with common arguments registered
    WHEN: No --language argument is supplied
    THEN: The parsed language equals LANGUAGE_CHOICES[0]
    """
    assert defaults.language == LANGUAGE_CHOICES[0]


@pytest.mark.parametrize("lang", LANGUAGE_CHOICES)
def test_language_accepts_all_supported_language_codes(parser: ArgumentParser, lang: str) -> None:
    """
    --language accepts every supported language code without error.

    GIVEN: A parser with common arguments registered
    WHEN: --language is set to a supported language code
    THEN: The parsed language matches the supplied code
    """
    args = parser.parse_args(["--language", lang])
    assert args.language == lang


def test_language_rejects_unsupported_language_code(parser: ArgumentParser) -> None:
    """
    --language rejects language codes not in LANGUAGE_CHOICES with exit code 2.

    GIVEN: A parser with common arguments registered
    WHEN: --language is set to an unsupported code
    THEN: argparse exits with code 2 (argument error)
    """
    with pytest.raises(SystemExit) as exc_info:
        parser.parse_args(["--language", "klingon"])
    assert exc_info.value.code == 2


# ---------------------------------------------------------------------------
# --version
# ---------------------------------------------------------------------------


def test_version_flag_exits_with_zero(parser: ArgumentParser) -> None:
    """
    --version prints version information and exits with code 0.

    GIVEN: A parser with common arguments registered
    WHEN: --version is passed
    THEN: argparse exits cleanly with code 0
    """
    with pytest.raises(SystemExit) as exc_info:
        parser.parse_args(["--version"])
    assert exc_info.value.code == 0


# ---------------------------------------------------------------------------
# Combined arguments and structural contract
# ---------------------------------------------------------------------------


def test_loglevel_and_language_can_be_specified_together(parser: ArgumentParser) -> None:
    """
    --loglevel and --language can be combined in a single invocation.

    GIVEN: A parser with common arguments registered
    WHEN: Both --loglevel and --language are supplied
    THEN: Both parsed values reflect the supplied arguments
    """
    args = parser.parse_args(["--loglevel", "DEBUG", "--language", "de"])
    assert args.loglevel == "DEBUG"
    assert args.language == "de"


def test_add_common_arguments_returns_the_same_parser_instance() -> None:
    """
    add_common_arguments returns the parser it was given, enabling fluent chaining.

    GIVEN: A fresh ArgumentParser
    WHEN: add_common_arguments is called
    THEN: The returned object is the same parser instance (identity, not a copy)
    """
    original = ArgumentParser()
    returned = add_common_arguments(original)
    assert returned is original
