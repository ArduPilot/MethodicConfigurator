#!/usr/bin/python3

"""
Tests for the internationalization.py file.

This file is part of Ardupilot methodic configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2025 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import argparse
import unittest
from os import path as os_path

import pytest

from ardupilot_methodic_configurator.internationalization import LANGUAGE_CHOICES, identity_function, load_translation


@pytest.mark.usefixtures("mock_args_de")
def test_no_logging_import() -> None:
    """Test that logging is not imported in internationalization.py."""
    with open(
        os_path.join(os_path.dirname(__file__), "../ardupilot_methodic_configurator/internationalization.py"), encoding="utf-8"
    ) as f:
        content = f.read()
        assert "import logging" not in content
        assert "from logging import" not in content


class TestInternationalization(unittest.TestCase):
    """Test the internationalization functions."""

    def test_default_language_is_english(self) -> None:
        assert LANGUAGE_CHOICES[0] == "en"

    def test_load_translation_default(self) -> None:
        translation_function = load_translation()
        assert translation_function == identity_function  # pylint: disable=comparison-with-callable

    def test_identity_function(self) -> None:
        test_string = "test"
        assert identity_function(test_string) == test_string

    @pytest.mark.usefixtures("mock_args_de")
    def test_load_translation_with_language(self) -> None:
        translation_function = load_translation()
        assert translation_function != identity_function  # pylint: disable=comparison-with-callable

    @pytest.mark.usefixtures("mock_args_invalid")
    def test_load_translation_with_invalid_language(self) -> None:
        translation_function = load_translation()
        assert translation_function == identity_function  # pylint: disable=comparison-with-callable

    @pytest.mark.usefixtures("mock_gettext", "mock_args_zh_cn")
    def test_load_translation_fallback(self) -> None:
        translation_function = load_translation()
        assert translation_function == identity_function  # pylint: disable=comparison-with-callable

    def test_language_choices(self) -> None:
        expected_languages = ["en", "zh_CN", "pt", "de", "it", "ja"]
        assert expected_languages == LANGUAGE_CHOICES


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


if __name__ == "__main__":
    unittest.main()
