#!/usr/bin/env python3

"""
Tests for shared formatting helpers.

SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

from ardupilot_methodic_configurator.formatting import format_filesize


def test_format_filesize() -> None:
    assert format_filesize(512) == "512 B"
    assert format_filesize(2048) == "2.0 KB"
    assert format_filesize(2 * 1024 * 1024) == "2.0 MB"
