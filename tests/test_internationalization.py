#!/usr/bin/env python3

"""
Tests for the internationalization.py file.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import argparse
from os import path as os_path

import pytest

from ardupilot_methodic_configurator.internationalization import LANGUAGE_CHOICES, identity_function, load_translation


@pytest.fixture
def mock_args_de(mocker) -> None:
    mocker.patch("argparse.ArgumentParser.parse_known_args", return_value=(argparse.Namespace(language="de"), []))


@pytest.fixture
def mock_args_invalid(mocker) -> None:
    mocker.patch("argparse.ArgumentParser.parse_known_args", return_value=(argparse.Namespace(language="invalid"), []))


@pytest.fixture
def mock_args_zh_cn(mocker) -> None:
    mocker.patch("argparse.ArgumentParser.parse_known_args", return_value=(argparse.Namespace(language="zh_CN"), []))


@pytest.fixture
def mock_gettext(mocker) -> None:
    mocker.patch("gettext.translation", side_effect=FileNotFoundError)


def test_no_logging_import() -> None:
    """
    The internationalization module must not import logging.

    GIVEN: The internationalization.py source file
    WHEN: Its content is read
    THEN: No logging import statements should be present
    """
    with open(
        os_path.join(os_path.dirname(__file__), "../ardupilot_methodic_configurator/internationalization.py"), encoding="utf-8"
    ) as f:
        content = f.read()
        assert "import logging" not in content
        assert "from logging import" not in content


def test_default_language_is_english() -> None:
    """
    English is the default/first supported language.

    GIVEN: The list of supported language choices
    WHEN: The first entry is inspected
    THEN: It should be 'en' (English)
    """
    assert LANGUAGE_CHOICES[0] == "en"


def test_load_translation_returns_identity_when_no_language_arg() -> None:
    """
    load_translation returns the identity function when no language argument is provided.

    GIVEN: No --language argument is passed on the command line
    WHEN: load_translation() is called
    THEN: The identity function is returned (no-op translation)
    """
    translation_function = load_translation()
    assert translation_function == identity_function  # pylint: disable=comparison-with-callable


def test_identity_function_returns_input_unchanged() -> None:
    """
    The identity function returns its input string unchanged.

    GIVEN: Any input string
    WHEN: identity_function is called with that string
    THEN: The same string is returned
    """
    test_string = "test"
    assert identity_function(test_string) == test_string


@pytest.mark.usefixtures("mock_args_de")
def test_load_translation_returns_real_translator_for_valid_language() -> None:
    """
    load_translation returns a real translation function for a valid language code.

    GIVEN: The --language argument is set to 'de' (German)
    WHEN: load_translation() is called
    THEN: A non-identity translation function is returned
    """
    translation_function = load_translation()
    assert translation_function != identity_function  # pylint: disable=comparison-with-callable


@pytest.mark.usefixtures("mock_args_invalid")
def test_load_translation_falls_back_to_identity_for_invalid_language() -> None:
    """
    load_translation falls back to the identity function for an unrecognised language code.

    GIVEN: The --language argument is set to an invalid code
    WHEN: load_translation() is called
    THEN: The identity function is returned
    """
    translation_function = load_translation()
    assert translation_function == identity_function  # pylint: disable=comparison-with-callable


@pytest.mark.usefixtures("mock_gettext", "mock_args_zh_cn")
def test_load_translation_falls_back_to_identity_when_translation_file_missing() -> None:
    """
    load_translation falls back to the identity function when the .mo file is missing.

    GIVEN: The --language argument is 'zh_CN' but gettext.translation raises FileNotFoundError
    WHEN: load_translation() is called
    THEN: The identity function is returned
    """
    translation_function = load_translation()
    assert translation_function == identity_function  # pylint: disable=comparison-with-callable


def test_language_choices_contains_expected_languages() -> None:
    """
    LANGUAGE_CHOICES contains exactly the expected set of supported language codes.

    GIVEN: The LANGUAGE_CHOICES constant
    WHEN: Its value is compared to the expected list
    THEN: All expected language codes are present in the correct order
    """
    expected_languages = ["en", "zh_CN", "pt", "de", "it", "ja"]
    assert expected_languages == LANGUAGE_CHOICES


def test_all_language_codes_are_non_empty_strings() -> None:
    """
    Every entry in LANGUAGE_CHOICES is a non-empty string.

    GIVEN: The LANGUAGE_CHOICES constant
    WHEN: Each entry is inspected
    THEN: All entries are non-empty strings
    """
    for code in LANGUAGE_CHOICES:
        assert isinstance(code, str), f"Language code {code!r} must be a string"
        assert code, f"Language code {code!r} must be non-empty"


def test_load_translation_is_callable() -> None:
    """
    load_translation is a callable that returns a callable.

    GIVEN: The internationalization module
    WHEN: load_translation and its return value are inspected
    THEN: Both are callable
    """
    assert callable(load_translation)
    result = load_translation()
    assert callable(result)


def test_identity_function_is_callable_and_transparent_for_multiple_inputs() -> None:
    """
    identity_function is a callable that returns its input unchanged for any string.

    GIVEN: Several different string inputs
    WHEN: identity_function is called with each
    THEN: The exact same string is returned in every case
    """
    for s in ["", "hello", "ArduPilot", "日本語", "  spaces  "]:
        assert identity_function(s) == s
