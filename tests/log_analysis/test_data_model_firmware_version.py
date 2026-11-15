#!/usr/bin/env python3

"""
Tests for pure firmware version parsing helpers.

SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import pytest

from ardupilot_methodic_configurator.log_analysis.data_model_firmware_version import (
    parse_first_msg_version,
    parse_msg_ver_string,
    parse_ver_fields,
)


def test_parse_ver_fields_returns_vehicle_and_numeric_version() -> None:
    """VER fields are parsed without importing backend log I/O."""
    assert parse_ver_fields("ArduCopter V4.6.3 (3fc7011a)", "4", "6", "3") == ("ArduCopter", 4, 6, 3)


@pytest.mark.parametrize("firmware", ["", "   ", "\t\n"])
def test_parse_ver_fields_rejects_missing_vehicle(firmware: str) -> None:
    """A blank firmware name cannot identify a vehicle, even with complete version fields."""
    assert parse_ver_fields(firmware, 4, 6, 3) is None


@pytest.mark.parametrize(
    ("major", "minor", "patch"),
    [
        (None, 6, 3),
        (4, None, 3),
        (4, 6, None),
        ("invalid", 6, 3),
        (4, "invalid", 3),
        (4, 6, "invalid"),
        ([], 6, 3),
        (4, [], 3),
        (4, 6, []),
    ],
)
def test_parse_ver_fields_rejects_incomplete_or_invalid_versions(major: object, minor: object, patch: object) -> None:
    """Every version component must be present and convertible to an integer."""
    assert parse_ver_fields("ArduPlane V4.6.3", major, minor, patch) is None


def test_parse_ver_fields_strips_whitespace_and_preserves_zero_components() -> None:
    """Whitespace around the firmware name and zero version numbers are valid."""
    assert parse_ver_fields("  ArduPlane V0.0.0  ", 0, "0", 0) == ("ArduPlane", 0, 0, 0)


def test_parse_msg_ver_string_accepts_missing_patch() -> None:
    """Old MSG firmware lines can omit the patch component."""
    assert parse_msg_ver_string("ArduPlane V4.6 (142aece2)") == ("ArduPlane", 4, 6, 0, "142aece2")


def test_parse_first_msg_version_skips_unrelated_messages() -> None:
    """The first parseable firmware line wins."""
    messages = ["Booting", "Frame: QUAD", "ArduCopter V4.5.5 (abcdef01)", "ArduPlane V4.5.5"]

    assert parse_first_msg_version(messages) == ("ArduCopter", 4, 5, 5, "abcdef01")
