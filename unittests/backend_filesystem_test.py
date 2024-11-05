#!/usr/bin/env python3

'''
This file is part of Ardupilot methodic configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
'''

# pylint: skip-file

import unittest

# import os
from unittest.mock import MagicMock, patch

from MethodicConfigurator.backend_filesystem import LocalFilesystem


class TestLocalFilesystem():

    @patch('os.path.isdir')
    @patch('os.listdir')
    def test_read_params_from_files(self, mock_listdir, mock_isdir):
        # Setup
        mock_isdir.return_value = True
        mock_listdir.return_value = ['00_default.param', '01_ignore_readonly.param', '02_test.param']
        mock_load_param_file_into_dict = MagicMock()
        mock_load_param_file_into_dict.return_value = {'TEST_PARAM': 'value'}
        LocalFilesystem.load_param_file_into_dict = mock_load_param_file_into_dict

        # Call the method under test
        lfs = LocalFilesystem('vehicle_dir', 'vehicle_type', None, False)
        result = lfs.read_params_from_files()

        # Assertions
        self.assertEqual(result, {'02_test.param': {'TEST_PARAM': 'value'}})
        mock_isdir.assert_called_once_with('vehicle_dir')
        mock_listdir.assert_called_once_with('vehicle_dir')
        mock_load_param_file_into_dict.assert_called_once_with('vehicle_dir/02_test.param')

    def test_str_to_bool(self):
        lfs = LocalFilesystem('vehicle_dir', 'vehicle_type', None, False)
        self.assertTrue(lfs.str_to_bool('true'))
        self.assertTrue(lfs.str_to_bool('yes'))
        self.assertTrue(lfs.str_to_bool('1'))
        self.assertFalse(lfs.str_to_bool('false'))
        self.assertFalse(lfs.str_to_bool('no'))
        self.assertFalse(lfs.str_to_bool('0'))
        self.assertIsNone(lfs.str_to_bool('maybe'))

    @patch('os.path.isdir')
    @patch('os.listdir')
    @patch('backend_filesystem.LocalFilesystem.read_params_from_files')
    def test_re_init(self, mock_read_params_from_files, mock_listdir, mock_isdir):
        mock_isdir.return_value = True
        mock_listdir.return_value = ['00_default.param', '01_ignore_readonly.param', '02_test.param']
        mock_read_params_from_files.return_value = {'02_test.param': {'TEST_PARAM': 'value'}}

        lfs = LocalFilesystem('vehicle_dir', 'vehicle_type', None, False)
        lfs.re_init('new_vehicle_dir', 'new_vehicle_type')

        self.assertEqual(lfs.vehicle_dir, 'new_vehicle_dir')
        self.assertEqual(lfs.vehicle_type, 'new_vehicle_type')
        mock_isdir.assert_called_once_with('new_vehicle_dir')
        mock_listdir.assert_called_once_with('new_vehicle_dir')
        mock_read_params_from_files.assert_called_once()

    def test_write_summary_files(self):
        # Initialize LocalFilesystem with the test directory
        # lfs = LocalFilesystem(self.test_dir, "vehicle_type", None, False)

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


class TestCopyTemplateFilesToNewVehicleDir():

    @patch('os.listdir')
    @patch('os.path.join')
    @patch('shutil.copytree')
    @patch('shutil.copy2')
    def test_copy_template_files_to_new_vehicle_dir(self, mock_copy2, mock_copytree, mock_join, mock_listdir):
        # Ensure the mock for os.listdir returns the expected items
        mock_listdir.return_value = ['file1', 'dir1']
        # Simulate os.path.join behavior to ensure paths are constructed as expected
        mock_join.side_effect = lambda *args: '/'.join(args)

        # Initialize LocalFilesystem
        lfs = LocalFilesystem('vehicle_dir', 'vehicle_type', None, False)

        # Call the method under test
        lfs.copy_template_files_to_new_vehicle_dir('template_dir', 'new_vehicle_dir')

        # Assertions to verify the mocks were called as expected
        mock_listdir.assert_called_once_with('template_dir')
        mock_join.assert_any_call('template_dir', 'file1')
        mock_join.assert_any_call('template_dir', 'dir1')
        mock_join.assert_any_call('new_vehicle_dir', 'file1')
        mock_join.assert_any_call('new_vehicle_dir', 'dir1')
        mock_copy2.assert_called_once_with('template_dir/file1', 'new_vehicle_dir/file1')
        mock_copytree.assert_called_once_with('template_dir/dir1', 'new_vehicle_dir/dir1')


if __name__ == '__main__':
    unittest.main()
