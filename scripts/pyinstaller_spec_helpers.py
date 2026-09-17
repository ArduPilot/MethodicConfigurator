# ruff: noqa: INP001
"""
Shared bundle-shrinking rules for the Windows, Linux and macOS PyInstaller specs.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import os
import platform
import re
from collections.abc import Callable

# Pymavlink ships one large module per MAVLink dialect; the application only uses these.
USED_MAVLINK_DIALECTS = frozenset({"all", "ardupilotmega"})

# Selenium wheels bundle one selenium-manager per OS and architecture.
SELENIUM_MANAGER_FOLDERS = frozenset({"linux", "linux-arm64", "linux-x86_64", "macos", "windows"})

_UNUSED_FILE_PATTERNS = (
    re.compile(r"(^|[\\/])PIL[\\/]_avif\.[^\\/]*$"),  # AVIF images are not used
    re.compile(r"(^|[\\/])libavif[^\\/]*\.(so(\.[0-9]+)*|dylib)$"),  # libavif of the Pillow wheels, wherever it is collected
    re.compile(
        r"(^|[\\/])matplotlib[\\/]mpl-data[\\/]fonts[\\/](afm|pdfcorefonts)[\\/]"
    ),  # only used by PostScript/PDF output
)


def is_unused_mavlink_dialect(module_name: str) -> bool:
    """Return True for pymavlink.dialects.<v10|v20>.<dialect> modules that the application never imports."""
    parts = module_name.split(".")
    return len(parts) >= 4 and parts[:2] == ["pymavlink", "dialects"] and parts[3] not in USED_MAVLINK_DIALECTS


def selenium_manager_folder(target: str, machine: str | None = None) -> str:
    """Return the selenium-manager folder that selenium selects at runtime for the build target."""
    if target == "linux":
        machine = (machine or platform.machine()).lower()
        return "linux-arm64" if machine in {"aarch64", "arm64"} else "linux-x86_64"
    return target


def unused_file_filter(target: str, machine: str | None = None) -> Callable[[tuple], bool]:
    """
    Build a predicate that tells whether a PyInstaller TOC entry is useless for the target platform.

    Args:
        target: "windows", "linux" or "macos".
        machine: CPU architecture of the build machine; defaults to the current one.

    """
    kept_folder = selenium_manager_folder(target, machine)
    unused_prefixes = tuple(
        os.path.join("selenium", "webdriver", "common", folder) + os.sep
        for folder in sorted(SELENIUM_MANAGER_FOLDERS - {kept_folder})
    )

    def is_unused_file(entry: tuple) -> bool:
        destination = os.path.normpath(entry[0])
        return destination.startswith(unused_prefixes) or any(pattern.search(destination) for pattern in _UNUSED_FILE_PATTERNS)

    return is_unused_file
