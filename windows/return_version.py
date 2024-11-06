#!/usr/bin/env python3

"""
This script returns the current version number
Used as part of building the Windows setup file (MethodicConfiguratorWinBuild.bat)

This file is part of Ardupilot methodic configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

# It assumes there is a line like this:
# VERSION = "12344"

# from ..MethodicConfigurator.version import VERSION
# print(VERSION)

# glob supports Unix style pathname extensions
with open("../MethodicConfigurator/version.py", encoding="utf-8") as f:
    searchlines = f.readlines()
    for line in searchlines:
        if "VERSION = " in line:
            print(line[11 : len(line) - 2])
            break
