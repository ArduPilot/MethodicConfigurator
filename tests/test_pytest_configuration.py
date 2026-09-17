#!/usr/bin/env python3

"""
Regression checks for repository-wide pytest safeguards.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

from configparser import ConfigParser
from pathlib import Path


def test_pytest_enforces_a_default_test_timeout() -> None:
    """A hung test must fail without each test opting into a timeout marker."""
    config = ConfigParser()
    config.read(Path(__file__).parents[1] / "pytest.ini", encoding="utf-8")

    assert config.getint("pytest", "timeout") == 30
