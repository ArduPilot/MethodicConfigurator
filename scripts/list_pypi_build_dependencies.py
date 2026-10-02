#!/usr/bin/env python3
"""
List all packages that are required for building the project for distribution on PyPI.org.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import importlib
import sys

try:
    import tomllib  # ty: ignore[unresolved-import]
except ModuleNotFoundError:  # Python 3.10
    tomllib = importlib.import_module("tomli")

with open("pyproject.toml", "rb") as f:
    data = tomllib.load(f)
pkgs = data.get("project", {}).get("optional-dependencies", {}).get("pypi_dist") or []
if not pkgs:
    sys.exit(0)
print(" ".join(pkgs))  # noqa: T201
