#!/usr/bin/python3

"""
Tests for the argcomplete command line completions for the user-facing scripts.

SPDX-FileCopyrightText: 2024-2025 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

from argparse import ArgumentParser

from ardupilot_methodic_configurator.__main__ import create_argument_parser as main_parser
from ardupilot_methodic_configurator.annotate_params import create_argument_parser as annotate_parser
from ardupilot_methodic_configurator.backend_mavftp import create_argument_parser as mavftp_parser
from ardupilot_methodic_configurator.extract_param_defaults import create_argument_parser as extract_parser
from ardupilot_methodic_configurator.param_pid_adjustment_update import create_argument_parser as pid_parser


def test_main_parser_type() -> None:
    parser = main_parser()
    assert isinstance(parser, ArgumentParser)
    assert hasattr(parser, "_actions")
    assert any(hasattr(action, "completer") for action in parser._actions)  # pylint: disable=protected-access


def test_extract_defaults_parser_type() -> None:
    parser = extract_parser()
    assert isinstance(parser, ArgumentParser)
    assert hasattr(parser, "_actions")
    assert any(hasattr(action, "completer") for action in parser._actions)  # pylint: disable=protected-access


def test_annotate_params_parser_type() -> None:
    parser = annotate_parser()
    assert isinstance(parser, ArgumentParser)
    assert hasattr(parser, "_actions")
    assert any(hasattr(action, "completer") for action in parser._actions)  # pylint: disable=protected-access


def test_pid_adjustment_parser_type() -> None:
    parser = pid_parser()
    assert isinstance(parser, ArgumentParser)
    assert hasattr(parser, "_actions")
    assert any(hasattr(action, "completer") for action in parser._actions)  # pylint: disable=protected-access


def test_mavftp_parser_type() -> None:
    parser = mavftp_parser()
    assert isinstance(parser, ArgumentParser)
    assert hasattr(parser, "_actions")
    assert any(hasattr(action, "completer") for action in parser._actions)  # pylint: disable=protected-access
