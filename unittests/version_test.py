#!/usr/bin/env python3

'''
This file is part of Ardupilot methodic configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
'''

import unittest
import re

from MethodicConfigurator.version import VERSION

class TestVersion(unittest.TestCase):
    """
    Test that the VERSION constant is a string and follows semantic versioning.
    """

    def test_version_format(self):
        # Semantic versioning pattern
        semver_pattern = r'^\d+\.\d+\.\d+$'
        match = re.match(semver_pattern, VERSION)
        msg = f"VERSION string '{VERSION}' does not follow semantic versioning"
        self.assertIsNotNone(match, msg)


if __name__ == '__main__':
    unittest.main()
