#!/usr/bin/env python3
"""
List all packages that are required for building the project for distribution on PyPI.org.

This file is part of ArduPilot methodic configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2025 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import sys

# This library is part of python 3.11+
# so this line fails when pylint runs with python 3.9,
# but that can be ignored, because pypi is packaged with python 3.13
import tomllib  # pylint: disable=import-error, useless-suppression

with open("pyproject.toml", "rb") as f:
    data = tomllib.load(f)
pkgs = data.get("project", {}).get("optional-dependencies", {}).get("pypi_dist") or []
if not pkgs:
    sys.exit(0)
print(" ".join(pkgs))  # noqa: T201
