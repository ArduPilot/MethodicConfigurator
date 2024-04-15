#!/usr/bin/env python3

'''
This file is part of Ardupilot methodic configurator. https://github.com/ArduPilot/MethodicConfigurator

(C) 2024 Amilcar do Carmo Lucas, IAV GmbH

SPDX-License-Identifier:    GPL-3
'''

# pylint: skip-file

import unittest
# import os
from unittest.mock import patch, MagicMock
from backend_filesystem import LocalFilesystem


class TestLocalFilesystem(unittest.TestCase):

    @patch('backend_filesystem.os.path.isdir')
    @patch('backend_filesystem.os.listdir')
    def test_read_params_from_files(self, mock_listdir, mock_isdir):
        # Setup
        mock_isdir.return_value = True
        mock_listdir.return_value = ['00_default.param', '01_ignore_readonly.param', '02_test.param']
        mock_load_param_file_into_dict = MagicMock()
        mock_load_param_file_into_dict.return_value = {'TEST_PARAM': 'value'}
        LocalFilesystem.load_param_file_into_dict = mock_load_param_file_into_dict

        # Call the method under test
        lfs = LocalFilesystem('vehicle_dir', 'vehicle_type')
        result = lfs.read_params_from_files()

        # Assertions
        self.assertEqual(result, {'02_test.param': {'TEST_PARAM': 'value'}})
        mock_isdir.assert_called_once_with('vehicle_dir')
        mock_listdir.assert_called_once_with('vehicle_dir')
        mock_load_param_file_into_dict.assert_called_once_with('vehicle_dir/02_test.param')

    def test_str_to_bool(self):
        lfs = LocalFilesystem('vehicle_dir', 'vehicle_type')
        self.assertTrue(lfs.str_to_bool('true'))
        self.assertTrue(lfs.str_to_bool('yes'))
        self.assertTrue(lfs.str_to_bool('1'))
        self.assertFalse(lfs.str_to_bool('false'))
        self.assertFalse(lfs.str_to_bool('no'))
        self.assertFalse(lfs.str_to_bool('0'))
        self.assertIsNone(lfs.str_to_bool('maybe'))

    @patch('backend_filesystem.os.path.isdir')
    @patch('backend_filesystem.os.listdir')
    @patch('backend_filesystem.LocalFilesystem.read_params_from_files')
    def test_re_init(self, mock_read_params_from_files, mock_listdir, mock_isdir):
        mock_isdir.return_value = True
        mock_listdir.return_value = ['00_default.param', '01_ignore_readonly.param', '02_test.param']
        mock_read_params_from_files.return_value = {'02_test.param': {'TEST_PARAM': 'value'}}

        lfs = LocalFilesystem('vehicle_dir', 'vehicle_type')
        lfs.re_init('new_vehicle_dir', 'new_vehicle_type')

        self.assertEqual(lfs.vehicle_dir, 'new_vehicle_dir')
        self.assertEqual(lfs.vehicle_type, 'new_vehicle_type')
        mock_isdir.assert_called_once_with('new_vehicle_dir')
        mock_listdir.assert_called_once_with('new_vehicle_dir')
        mock_read_params_from_files.assert_called_once()

    def test_write_summary_files(self):
        # Initialize LocalFilesystem with the test directory
        # lfs = LocalFilesystem(self.test_dir, "vehicle_type")

        # Call the method under test
        # Assuming you have a method to write summary files
        # lfs.write_summary_files()

        # Assertions
        # Check if the summary files were created in the test directory
        # summary_files = ["complete.param", "non-default_read-only.param", "non-default_writable_calibrations.param",
        # "non-default_writable_non-calibrations.param"]
        # for file_name in summary_files:
        #     self.assertTrue(os.path.exists(os.path.join(self.test_dir, file_name)))
        pass


if __name__ == '__main__':
    unittest.main()
