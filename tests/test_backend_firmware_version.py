#!/usr/bin/env python3

"""
Tests for firmware identity extraction in backend_bin_log.py.

SPDX-FileCopyrightText: 2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

from unittest.mock import MagicMock

from ardupilot_methodic_configurator.backend_bin_log import process_msg_identity, process_ver_identity


def _message(message_type: str, **fields: object) -> MagicMock:
    result = MagicMock()
    result.get_type.return_value = message_type
    for name, value in fields.items():
        setattr(result, name, value)
    return result


def test_structured_ver_identity_is_parsed() -> None:
    ver = _message("VER", FWS="ArduCopter V4.6.3", Maj=4, Min=6, Pat=3)

    assert process_ver_identity(ver) == ("ArduCopter", 4, 6, 3)


def test_msg_identity_is_used_as_fallback() -> None:
    msg = _message("MSG", Message="ArduPlane V4.5 (abcdef01)")

    assert process_msg_identity(msg) == ("ArduPlane", 4, 5, 0)


def test_missing_identity_is_reported() -> None:
    assert process_ver_identity(_message("VER", FWS=None, Maj=4, Min=6, Pat=3)) is None
    assert process_msg_identity(_message("MSG", Message="Boot started")) is None
