#!/usr/bin/env python3

"""
Tests for pure firmware version parsing helpers.

SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

from types import SimpleNamespace

from ardupilot_methodic_configurator.log_analysis.data_model_firmware_version import (
    extract_msg_identity,
    extract_ver_identity,
    parse_first_msg_version,
    parse_msg_ver_string,
    parse_ver_fields,
)


def test_parse_ver_fields_returns_vehicle_and_numeric_version() -> None:
    """VER fields are parsed without importing backend log I/O."""
    assert parse_ver_fields("ArduCopter V4.6.3 (3fc7011a)", "4", "6", "3") == ("ArduCopter", 4, 6, 3)


def test_parse_msg_ver_string_accepts_missing_patch() -> None:
    """Old MSG firmware lines can omit the patch component."""
    assert parse_msg_ver_string("ArduPlane V4.6 (142aece2)") == ("ArduPlane", 4, 6, 0, "142aece2")


def test_parse_first_msg_version_skips_unrelated_messages() -> None:
    """The first parseable firmware line wins."""
    messages = ["Booting", "Frame: QUAD", "ArduCopter V4.5.5 (abcdef01)", "ArduPlane V4.5.5"]

    assert parse_first_msg_version(messages) == ("ArduCopter", 4, 5, 5, "abcdef01")


def test_extract_ver_identity_decodes_bytes_fws() -> None:
    """A VER message with a bytes FWS field is decoded before parsing."""
    msg = SimpleNamespace(FWS=b"ArduCopter V4.6.3", Maj=4, Min=6, Pat=3)

    assert extract_ver_identity(msg) == ("ArduCopter", 4, 6, 3)


def test_extract_ver_identity_returns_none_without_fws() -> None:
    """A VER message missing the FWS field yields no identity."""
    assert extract_ver_identity(SimpleNamespace(Maj=4, Min=6, Pat=3)) is None


def test_extract_msg_identity_decodes_bytes_message() -> None:
    """An old-style MSG firmware line as bytes is decoded before parsing."""
    msg = SimpleNamespace(Message=b"ArduPlane V4.5.5 (abcdef01)")

    assert extract_msg_identity(msg) == ("ArduPlane", 4, 5, 5)


def test_extract_msg_identity_returns_none_for_unrelated_message() -> None:
    """A non-firmware MSG line yields no identity."""
    assert extract_msg_identity(SimpleNamespace(Message="Booting")) is None
