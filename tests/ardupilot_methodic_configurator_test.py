#!/usr/bin/env python3

"""
Tests for the __main__.py file.

This file is part of Ardupilot methodic configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

# pylint: skip-file

import argparse
import unittest
from unittest.mock import patch

# from unittest.mock import MagicMock
# from unittest.mock import mock_open
from ardupilot_methodic_configurator.__main__ import argument_parser


class TestArgumentParser(unittest.TestCase):  # pylint: disable=missing-class-docstring
    @patch(
        "argparse.ArgumentParser.parse_args", return_value=argparse.Namespace(conn="tcp:127.0.0.1:5760", params="params_dir")
    )
    def test_argument_parser(self, mock_args) -> None:
        args = argument_parser()
        assert args.conn == "tcp:127.0.0.1:5760"
        assert args.params == "params_dir"


if __name__ == "__main__":
    unittest.main()
