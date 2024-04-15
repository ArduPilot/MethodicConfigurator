#!/usr/bin/python3

'''
This script updates the PID adjustment parameters to be factor of the corresponding autotuned or optimized parameters.

Usage:
    ./param_pid_adjustment_update.py -d /path/to/directory optimized_parameter_file.param

This file is part of Ardupilot methodic configurator. https://github.com/ArduPilot/MethodicConfigurator

(C) 2024 Amilcar do Carmo Lucas, IAV GmbH

SPDX-License-Identifier:    GPL-3
'''

# pylint: skip-file

import unittest
import argparse
import os
import shutil

from param_pid_adjustment_update import ranged_type
from param_pid_adjustment_update import Par
from param_pid_adjustment_update import update_pid_adjustment_params


class TestRangedType(unittest.TestCase):
    def test_valid_input(self):
        self.assertEqual(ranged_type(int, 1, 10)(5), 5)
        self.assertEqual(ranged_type(float, 0.1, 0.8)(0.5), 0.5)

    def test_invalid_input(self):
        with self.assertRaises(argparse.ArgumentTypeError) as cm:
            ranged_type(int, 1, 10)(15)
        self.assertEqual(cm.exception.args[0], "must be within [1, 10]")
        with self.assertRaises(argparse.ArgumentTypeError) as cm:
            ranged_type(float, 0.1, 0.8)(0.9)
        self.assertEqual(cm.exception.args[0], "must be within [0.1, 0.8]")
        with self.assertRaises(argparse.ArgumentTypeError) as cm:
            ranged_type(float, 0.1, 0.8)('sf')
        self.assertEqual(cm.exception.args[0], "must be a valid <class 'float'>")


class TestLoadParamFileIntoDict(unittest.TestCase):
    def test_valid_input(self):
        # Create a temporary file with valid parameter data
        with open('temp.param', 'w', encoding='utf-8') as f:
            f.write('PARAM1 1.0\n')
            f.write('# PARAM2 2.0\n')
            f.write('PARAM3 3.0 # Comment\n')

        # Call the function and check the result
        params, _ = Par.load_param_file_into_dict('temp.param')
        self.assertEqual(len(params), 2)
        self.assertEqual(params['PARAM1'].value, 1.0)
        self.assertEqual(params['PARAM3'].value, 3.0)

    def test_invalid_input(self):
        # Create a temporary file with invalid parameter data
        with open('temp.param', 'w', encoding='utf-8') as f:
            f.write('PARAM1 1.0\n')
            f.write('PARAM2\n') # Missing value
            f.write('PARAM3 3.0 # Invalid comment\n')

        # Call the function and check that it raises an exception
        with self.assertRaises(SystemExit) as cm:
            Par.load_param_file_into_dict('temp.param')
        self.assertEqual(cm.exception.args[0], "Missing parameter-value separator: PARAM2 in temp.param line 2")

    def test_empty_file(self):
        # Create an empty temporary file
        with open('temp.param', 'w', encoding='utf-8') as f:  # noqa F841
            pass

        # Call the function and check the result
        params, _ = Par.load_param_file_into_dict('temp.param')
        self.assertEqual(len(params), 0)

    def test_only_comments(self):
        # Create a temporary file with only comments
        with open('temp.param', 'w', encoding='utf-8') as f:
            f.write('# Comment 1\n')
            f.write('# Comment 2\n')

        # Call the function and check the result
        params, _ = Par.load_param_file_into_dict('temp.param')
        self.assertEqual(len(params), 0)

    def test_missing_value(self):
        # Create a temporary file with a missing value
        with open('temp.param', 'w', encoding='utf-8') as f:
            f.write('PARAM1\n')

        # Call the function and check that it raises an exception
        with self.assertRaises(SystemExit) as cm:
            Par.load_param_file_into_dict('temp.param')
        self.assertEqual(cm.exception.args[0], "Missing parameter-value separator: PARAM1 in temp.param line 1")

    def test_space_separator(self):
        # Create a temporary file with a space as the separator
        with open('temp.param', 'w', encoding='utf-8') as f:
            f.write('PARAM1 1.0\n')

        # Call the function and check the result
        params, _ = Par.load_param_file_into_dict('temp.param')
        self.assertEqual(params['PARAM1'].value, 1.0)

    def test_comma_separator(self):
        # Create a temporary file with a comma as the separator
        with open('temp.param', 'w', encoding='utf-8') as f:
            f.write('PARAM1,1.0\n')

        # Call the function and check the result
        params, _ = Par.load_param_file_into_dict('temp.param')
        self.assertEqual(params['PARAM1'].value, 1.0)

    def test_tab_separator(self):
        # Create a temporary file with a tab as the separator
        with open('temp.param', 'w', encoding='utf-8') as f:
            f.write('PARAM1\t1.0\n')

        # Call the function and check the result
        params, _ = Par.load_param_file_into_dict('temp.param')
        self.assertEqual(params['PARAM1'].value, 1.0)

    def test_invalid_characters(self):
        # Create a temporary file with invalid characters in the parameter name
        with open('temp.param', 'w', encoding='utf-8') as f:
            f.write('PARAM-1 1.0\n')

        # Call the function and check that it raises an exception
        with self.assertRaises(SystemExit) as cm:
            Par.load_param_file_into_dict('temp.param')
        self.assertEqual(cm.exception.args[0], "Invalid characters in parameter name PARAM-1 in temp.param line 1")

    def test_long_parameter_name(self):
        # Create a temporary file with a too long parameter name
        with open('temp.param', 'w', encoding='utf-8') as f:
            f.write('PARAMETER_THAT_IS_TOO_LONG 1.0\n')

        # Call the function and check that it raises an exception
        with self.assertRaises(SystemExit) as cm:
            Par.load_param_file_into_dict('temp.param')
        self.assertEqual(cm.exception.args[0], "Too long parameter name: PARAMETER_THAT_IS_TOO_LONG in temp.param line 1")

    def test_invalid_value(self):
        # Create a temporary file with an invalid value
        with open('temp.param', 'w', encoding='utf-8') as f:
            f.write('PARAM1 VALUE\n')

        # Call the function and check that it raises an exception
        with self.assertRaises(SystemExit) as cm:
            Par.load_param_file_into_dict('temp.param')
        self.assertEqual(cm.exception.args[0], "Invalid parameter value VALUE in temp.param line 1")

    def test_duplicated_parameter(self):
        # Create a temporary file with duplicated parameters
        with open('temp.param', 'w', encoding='utf-8') as f:
            f.write('PARAM1 1.0\n')
            f.write('PARAM1 2.0\n')

        # Call the function and check that it raises an exception
        with self.assertRaises(SystemExit) as cm:
            Par.load_param_file_into_dict('temp.param')
        self.assertEqual(cm.exception.args[0], "Duplicated parameter PARAM1 in temp.param line 2")

    def tearDown(self):
        # Remove the temporary file after each test
        if os.path.exists('temp.param'):
            os.remove('temp.param')


class TestExportToParam(unittest.TestCase):
    def test_valid_input(self):
        # Create a temporary file with valid parameter data
        with open('temp.param', 'w', encoding='utf-8') as f:
            f.write('PARAM1 1.0\n')
            f.write('PARAM2 2.0\n')
            f.write('PARAM3 3.0 # Comment\n')

        # Load the parameters into a dictionary
        params, _ = Par.load_param_file_into_dict('temp.param')

        # Export the parameters to a file
        Par.export_to_param(params, 'output.param')

        # Check the contents of the output file
        with open('output.param', 'r', encoding='utf-8') as f:
            output = f.read()
        self.assertEqual(output, 'PARAM1,1\nPARAM2,2\nPARAM3,3  # Comment\n')

    def test_with_header(self):
        # Create a temporary file with valid parameter data
        with open('temp.param', 'w', encoding='utf-8') as f:
            f.write('# HEADER\n')
            f.write('PARAM1 1.0\n')
            f.write('PARAM2 2.0\n')
            f.write('PARAM3 3.0\n')

        # Load the parameters into a dictionary
        params, _ = Par.load_param_file_into_dict('temp.param')

        # Export the parameters to a file, including the header
        Par.export_to_param(params, 'output.param', ['# HEADER'])

        # Check the contents of the output file
        with open('output.param', 'r', encoding='utf-8') as f:
            output = f.read()
        self.assertEqual(output, '# HEADER\nPARAM1,1\nPARAM2,2\nPARAM3,3\n')

    def tearDown(self):
        # Remove the temporary files after each test
        if os.path.exists('temp.param'):
            os.remove('temp.param')
        if os.path.exists('output.param'):
            os.remove('output.param')


class TestUpdatePidAdjustmentParams(unittest.TestCase):
    def setUp(self):
        # Create a directory for the test files
        self.test_dir = 'test_directory'
        os.mkdir(self.test_dir)
        # Create a default, adjustment and optimized parameter file for testing
        self.default_param_file = os.path.join(self.test_dir, '00_default.param')
        self.adjustment_param_file = os.path.join(self.test_dir, '14_pid_adjustment.param')
        self.optimized_param_file = os.path.join(self.test_dir, 'optimized_parameter_file.param')
        with open(self.default_param_file, 'w', encoding='utf-8') as f:
            f.write('PARAM1,1.0\nPARAM2,2.0\nPARAM3,3.0\n')
        with open(self.adjustment_param_file, 'w', encoding='utf-8') as f:
            f.write('PARAM1,1.5\nPARAM2,2.5\nPARAM3,3.5\n')
        with open(self.optimized_param_file, 'w', encoding='utf-8') as f:
            f.write('PARAM1,1.5\nPARAM2,2.5\nPARAM3,3.5\n')

    def test_all_parameters_present(self):
        # Remove a parameter from the default parameter file
        with open(self.default_param_file, 'w', encoding='utf-8') as f:
            f.write('PARAM1,1.0\nPARAM3,3.0\n')

        # Call the function and expect a SystemExit exception
        with self.assertRaises(SystemExit) as cm:
            update_pid_adjustment_params(self.test_dir, os.path.basename(self.optimized_param_file), 0.5)

        # Assert that the error message is as expected
        self.assertEqual(cm.exception.args[0], "Parameter PARAM2 is not present in test_directory/00_default.param")

    def test_parameter_missing_from_default_file(self):
        # A parameter is missing from the default parameter file
        with open(self.default_param_file, 'w', encoding='utf-8') as f:
            f.write('PARAM1,1.0\nPARAM3,3.0\n')
        with self.assertRaises(SystemExit) as cm:
            update_pid_adjustment_params(self.test_dir, os.path.basename(self.optimized_param_file), 0.5)
        self.assertEqual(cm.exception.args[0], "Parameter PARAM2 is not present in test_directory/00_default.param")

    def test_parameter_missing_from_optimized_file(self):
        # A parameter is missing from the optimized parameter file
        with open(self.optimized_param_file, 'w', encoding='utf-8') as f:
            f.write('PARAM1,1.5\nPARAM3,3.5\n')
        with self.assertRaises(SystemExit) as cm:
            update_pid_adjustment_params(self.test_dir, os.path.basename(self.optimized_param_file), 0.5)
        self.assertEqual(cm.exception.args[0],
                         "Parameter PARAM2 is not present in test_directory/optimized_parameter_file.param")

    def test_empty_files(self):
        # Both the default and optimized parameter files are empty
        with open(self.default_param_file, 'w', encoding='utf-8') as f:  # noqa F841
            pass
        with open(self.optimized_param_file, 'w', encoding='utf-8') as f:  # noqa F841
            pass
        with self.assertRaises(SystemExit) as cm:
            update_pid_adjustment_params(self.test_dir, os.path.basename(self.optimized_param_file), 0.5)
        self.assertEqual(cm.exception.args[0], "Failed to load default parameters from test_directory/00_default.param")

    def test_empty_default_file(self):
        # Create an empty default parameter file
        with open(self.default_param_file, 'w', encoding='utf-8') as f:  # noqa F841
            pass
        with self.assertRaises(SystemExit) as cm:
            update_pid_adjustment_params(self.test_dir, os.path.basename(self.optimized_param_file), 0.5)
        self.assertEqual(cm.exception.args[0], "Failed to load default parameters from test_directory/00_default.param")

    def test_empty_optimized_file(self):
        # Create an empty optimized parameter file
        with open(self.optimized_param_file, 'w', encoding='utf-8') as f:  # noqa F841
            pass
        with self.assertRaises(SystemExit) as cm:
            update_pid_adjustment_params(self.test_dir, os.path.basename(self.optimized_param_file), 0.5)
        self.assertEqual(cm.exception.args[0],
                         "Failed to load optimized parameters from test_directory/optimized_parameter_file.param")

    def test_empty_adjustment_file(self):
        # Create an empty adjustment parameter file
        with open(self.adjustment_param_file, 'w', encoding='utf-8') as f:  # noqa F841
            pass
        with self.assertRaises(SystemExit) as cm:
            update_pid_adjustment_params(self.test_dir, os.path.basename(self.optimized_param_file), 0.5)
        self.assertEqual(cm.exception.args[0],
                         "Failed to load PID adjustment parameters from test_directory/14_pid_adjustment.param")

    def test_zero_default_value(self):
        # Set a parameter in the default parameter file to zero
        with open(self.default_param_file, 'w', encoding='utf-8') as f:
            f.write('PARAM1,0.0\nPARAM2,2.0\nPARAM3,3.0\n')

        # Call the function
        pid_adjustment_params_dict, _pid_adjustment_file_path, _content_header = \
            update_pid_adjustment_params(self.test_dir, os.path.basename(self.optimized_param_file), 0.5)

        # Assert that the PID adjustment parameter value is zero
        self.assertEqual(pid_adjustment_params_dict['PARAM1'].value, 0)

    def test_update_comment(self):
        # Set a parameter in the default parameter file
        with open(self.default_param_file, 'w', encoding='utf-8') as f:
            f.write('PARAM1,1.0\nPARAM2,2.0\nPARAM3,3.0\n')

        # Call the function
        pid_adjustment_params_dict, _, _ = \
            update_pid_adjustment_params(self.test_dir, os.path.basename(self.optimized_param_file), 0.5)

        # Assert that the comment is updated correctly
        self.assertEqual(pid_adjustment_params_dict['PARAM1'].comment, " = 0.75 * (1 default)")

    def tearDown(self):
        # Remove the test directory after each test
        shutil.rmtree(self.test_dir)


if __name__ == '__main__':
    unittest.main()
