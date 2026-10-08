#!/usr/bin/env python3

"""
Tests for macOS-specific compatibility utilities.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

from unittest.mock import patch

import pytest

from ardupilot_methodic_configurator import macos_utilites


@pytest.mark.parametrize(
    ("system", "release", "expected"),
    [
        ("Linux", "6.12.0", False),
        ("Darwin", "24.6.0", True),
        ("Darwin", "25.0.0", False),
        ("Darwin", "not-a-release", True),
        ("Darwin", "", True),
    ],
)
def test_update_safety_predicate_matches_platform_and_darwin_boundary(system: str, release: str, expected: bool) -> None:
    """The update safety predicate distinguishes older Darwin from safe platforms."""
    with (
        patch.object(macos_utilites.platform, "system", return_value=system),
        patch.object(macos_utilites.platform, "release", return_value=release),
    ):
        assert macos_utilites.is_macos_sequoia_or_older() is expected
