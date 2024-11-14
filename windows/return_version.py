#!/usr/bin/env python3

"""
This script returns the current version number
Used as part of building the Windows setup file (MethodicConfiguratorWinBuild.bat)

This file is part of Ardupilot methodic configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

# It assumes there is a line like this:
# __version__ = "12344"

# glob supports Unix style pathname extensions
with open("../MethodicConfigurator/__init__.py", encoding="utf-8") as f:
    searchlines = f.readlines()
    for line in searchlines:
        if "__version__ = " in line:
            print(line[15 : len(line) - 2])
            break
