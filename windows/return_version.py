#!/usr/bin/env python3

"""
Returns python package current version number.

Used as part of building the Windows setup file (ardupilot_methodic_configuratorWinBuild.bat)

This file is part of Ardupilot methodic configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

# It assumes there is a line like this:
# __version__ = "12344"

# glob supports Unix style pathname extensions
with open("../ardupilot_methodic_configurator/__init__.py", encoding="utf-8") as f:
    searchlines = f.readlines()
    for line in searchlines:
        if "__version__ = " in line:
            print(line[15 : len(line) - 2])
            break
