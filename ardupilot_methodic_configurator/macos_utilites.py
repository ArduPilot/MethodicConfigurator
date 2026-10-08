"""
macOS compatibility utilities for the ArduPilot Methodic Configurator.

This module isolates OS-specific workarounds for Apple's kernel.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>
SPDX-FileCopyrightText: 2026 Omkar Sarkar <omkarsarkar24@gmail.com>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import platform


def is_macos_sequoia_or_older() -> bool:
    """
    Return whether synchronous Tk rendering updates must be deferred.

    On Darwin 24 (macOS Sequoia) and older, synchronous ``update_idletasks()``
    can crash, so callers should defer rendering. Darwin 25 (macOS Tahoe 26)
    and newer need idle updates to avoid black windows. Malformed Darwin
    releases are treated conservatively as requiring deferred updates.
    """
    if platform.system() != "Darwin":
        return False

    try:
        # platform.release() returns the Darwin kernel version.
        # Sequoia (macOS 15) is Darwin 24.x.x
        darwin_major = int(platform.release().split(".")[0])
        return darwin_major <= 24
    except (ValueError, IndexError):
        return True
