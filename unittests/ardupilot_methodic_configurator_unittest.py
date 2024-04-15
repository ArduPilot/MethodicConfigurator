#!/usr/bin/env python3

'''
This file is part of Ardupilot methodic configurator. https://github.com/ArduPilot/MethodicConfigurator

(C) 2024 Amilcar do Carmo Lucas, IAV GmbH

SPDX-License-Identifier:    GPL-3
'''

# pylint: skip-file

import argparse
import unittest
from unittest.mock import patch, MagicMock, mock_open
from ardupilot_methodic_configurator import argument_parser


class TestArgumentParser(unittest.TestCase):
    @patch('argparse.ArgumentParser.parse_args',
           return_value=argparse.Namespace(conn='tcp:127.0.0.1:5760', params='params_dir'))
    def test_argument_parser(self, mock_args):
        args = argument_parser()
        self.assertEqual(args.conn, 'tcp:127.0.0.1:5760')
        self.assertEqual(args.params, 'params_dir')


if __name__ == '__main__':
    unittest.main()
