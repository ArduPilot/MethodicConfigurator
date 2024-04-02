#!/usr/bin/env python3

'''
This file is part of Ardupilot methodic configurator. https://github.com/ArduPilot/MethodicConfigurator

AP_FLAKE8_CLEAN

(C) 2024 Amilcar do Carmo Lucas, IAV GmbH

SPDX-License-Identifier:    GPL-3
'''

import argparse
import unittest
from unittest.mock import patch, MagicMock, mock_open
from ardupilot_methodic_configurator import argument_parser
from ardupilot_methodic_configurator import create_connection_with_retry
from ardupilot_methodic_configurator import read_params_from_files


class TestArgumentParser(unittest.TestCase):
    @patch('argparse.ArgumentParser.parse_args', return_value=argparse.Namespace(conn='tcp:127.0.0.1:5760', params='params_dir'))
    def test_argument_parser(self, mock_args):
        args = argument_parser()
        self.assertEqual(args.conn, 'tcp:127.0.0.1:5760')
        self.assertEqual(args.params, 'params_dir')


class TestConnectionCreation(unittest.TestCase):
    @patch('param_gui.mavutil.mavlink_connection', return_value=MagicMock())
    def test_create_connection_with_retry(self, mock_mavlink_connection):
        conn_string = 'tcp:127.0.0.1:5760'
        master = create_connection_with_retry(conn_string)
        mock_mavlink_connection.assert_called_once_with(conn_string, timeout=5)

class TestReadParamsFromFiles(unittest.TestCase):    
    @patch('os.listdir', return_value=['file1.param'])
    @patch('builtins.open', new_callable=mock_open, read_data='param1 1.0\nparam2 2.0')
    def test_read_params_from_files(self, mock_file, mock_listdir):
        params_dir = '.'
        params = read_params_from_files(params_dir)
        expected_params = {'file1.param': {'param1': '1.0', 'param2': '2.0'}}
        self.assertEqual(params, expected_params)

if __name__ == '__main__':
    unittest.main()
