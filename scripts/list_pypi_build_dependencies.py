#!/usr/bin/env python3
"""
List all packages that are required for building the project for distribution on PyPI.org.

This file is part of ArduPilot methodic configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2025 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import sys

import tomllib

with open("pyproject.toml", "rb") as f:
    data = tomllib.load(f)
pkgs = data.get("project", {}).get("optional-dependencies", {}).get("pypi_dist") or []
if not pkgs:
    sys.exit(0)
print(" ".join(pkgs))  # noqa: T201
