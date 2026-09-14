#!/usr/bin/env python3

"""
Tests for shared formatting helpers.

SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

from ardupilot_methodic_configurator.formatting import format_elapsed_time, format_filesize


def test_format_filesize() -> None:
    assert format_filesize(512) == "512 B"
    assert format_filesize(2048) == "2.0 KB"
    assert format_filesize(2 * 1024 * 1024) == "2.0 MB"


def test_format_elapsed_time_under_at_and_over_one_hour() -> None:
    assert format_elapsed_time(0.0) == "0:00.0"
    assert format_elapsed_time(65.4) == "1:05.4"
    assert format_elapsed_time(1039.9) == "17:19.9"
    assert format_elapsed_time(3599.9) == "59:59.9"
    assert format_elapsed_time(3600.0) == "1:00:00.0"
    assert format_elapsed_time(8263.2) == "2:17:43.2"
