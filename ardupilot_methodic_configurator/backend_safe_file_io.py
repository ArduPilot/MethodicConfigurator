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
    replaced = False
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as tmp_file:
            write_func(tmp_file)
            tmp_file.flush()
            os.fsync(tmp_file.fileno())

        # Preserve permissions and ownership from the existing target file.
        # For new files, apply umask-derived default (0o666 & ~umask) so the
        # result matches what open("w") would have created.
        try:
            st = os.stat(filepath)
            with suppress(PermissionError):
                os.chmod(tmp_path, st.st_mode)
            if hasattr(os, "chown"):
                with suppress(PermissionError):
                    os.chown(tmp_path, st.st_uid, st.st_gid)
        except FileNotFoundError:
            current_umask = os.umask(0)
            os.umask(current_umask)
            default_mode = 0o666 & ~current_umask
            os.chmod(tmp_path, default_mode)

        os.replace(tmp_path, filepath)  # atomic on POSIX, near-atomic on Windows
        replaced = True

        # Best-effort: fsync the containing directory so the rename is durable
        dir_fd = None
        try:
            flags = getattr(os, "O_RDONLY", 0)
            if hasattr(os, "O_DIRECTORY"):
                flags |= os.O_DIRECTORY
            dir_fd = os.open(dir_name, flags)
            os.fsync(dir_fd)
        except (OSError, AttributeError):
            pass
        finally:
            if dir_fd is not None:
                with suppress(OSError):
                    os.close(dir_fd)
    finally:
        if not replaced:
            with suppress(OSError):
                os.unlink(tmp_path)
