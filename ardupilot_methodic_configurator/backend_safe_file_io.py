"""
Crash-safe file writing utilities.

Provides atomic write operations that prevent data corruption from
crashes, power loss, or OS-level interruptions during file writes.

SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import os
import tempfile
from contextlib import suppress
from typing import IO, Callable


def safe_write(filepath: str, write_func: Callable[[IO[str]], object]) -> None:
    """
    Write to a temporary file, then atomically replace the target.

    This ensures the target file is either fully written or untouched —
    never truncated or empty due to a crash mid-write.

    Args:
        filepath: The target file path to write to.
        write_func: A callable that receives an open file handle and writes content to it.

    """
    dir_name = os.path.dirname(filepath) or "."
    fd, tmp_path = tempfile.mkstemp(dir=dir_name, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as tmp_file:
            write_func(tmp_file)
            tmp_file.flush()
            os.fsync(tmp_file.fileno())

        # Preserve permissions from the existing target file, if any
        with suppress(FileNotFoundError):
            st = os.stat(filepath)
            with suppress(PermissionError):
                os.chmod(tmp_path, st.st_mode)

        os.replace(tmp_path, filepath)  # atomic on POSIX, near-atomic on Windows
    except BaseException:
        with suppress(OSError):
            os.unlink(tmp_path)
        raise
