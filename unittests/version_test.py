#!/usr/bin/env python3

"""
This file is part of Ardupilot methodic configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import re
import unittest

from MethodicConfigurator import __version__


class TestVersion(unittest.TestCase):
    """
    Test that the __version__ constant is a string and follows semantic versioning.
    """

    def test_version_format(self):
        # Semantic versioning pattern
        semver_pattern = r"^\d+\.\d+\.\d+$"
        match = re.match(semver_pattern, __version__)
        msg = f"__version__ string '{__version__}' does not follow semantic versioning"
        self.assertIsNotNone(match, msg)


if __name__ == "__main__":
    unittest.main()
