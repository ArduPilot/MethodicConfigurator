#!/usr/bin/env python3

"""
DOS to Unix line ending converter utility.

This module provides functionality to convert text files from DOS/Windows (CRLF)
to Unix (LF) line endings. Binary files are automatically skipped.

This file is part of Ardupilot methodic configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2025 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import logging
import sys
from glob import glob
from pathlib import Path

# pylint: disable=duplicate-code

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
logger = logging.getLogger(__name__)


def is_binary(filepath: Path) -> bool:
    """
    Check if a file is binary by reading its first 8192 bytes.

    Returns True if the file appears to be binary, False otherwise.
    """
    chunk_size = 8192
    try:
        with open(filepath, "rb") as file:
            chunk = file.read(chunk_size)
            # Check for null bytes and other binary characters
            textchars = bytearray({7, 8, 9, 10, 12, 13, 27} | set(range(0x20, 0x100)) - {0x7F})
            return bool(chunk.translate(None, textchars))
    except OSError as e:
        logger.error("Failed to read file %s: %s", filepath, str(e))
        return True  # If we can't read the file, treat it as binary to be safe


def dos2unix(filepath: str) -> None:
    """Convert DOS line endings (CRLF) to Unix line endings (LF)."""
    try:
        path = Path(filepath)

        if is_binary(path):
            logger.warning("Skipping binary file: %s", filepath)
            return

        # Read content in binary mode
        content = path.read_bytes()

        # Replace \r\n with \n
        content = content.replace(b"\r\n", b"\n")

        # Write back in binary mode
        path.write_bytes(content)
        logger.info("Successfully converted %s", filepath)

    except OSError as e:
        logger.error("Error processing %s: %s", filepath, str(e))
        sys.exit(1)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        logger.error("Usage: dos2unix.py <filepath or pattern>")
        sys.exit(1)

    pattern = sys.argv[1]
    files = glob(pattern)

    if not files:
        logger.error("No files found matching pattern: %s", pattern)
        sys.exit(1)

    for filename in files:
        dos2unix(filename)
