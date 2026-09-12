"""
Shared formatting helpers.

SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""


def format_filesize(size_bytes: int) -> str:
    """Format a byte count for display."""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    if size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    return f"{size_bytes / (1024 * 1024):.1f} MB"


def format_elapsed_time(seconds: float) -> str:
    """Format elapsed seconds as M:SS.s or H:MM:SS.s for display."""
    total_tenths = round(seconds * 10)
    hours, remainder_tenths = divmod(total_tenths, 36_000)
    minutes, second_tenths = divmod(remainder_tenths, 600)
    seconds_text = f"{second_tenths / 10:04.1f}"
    if hours:
        return f"{hours}:{minutes:02d}:{seconds_text}"
    return f"{minutes}:{seconds_text}"
