#!/usr/bin/env python3

"""
BDD-style tests for the backend_safe_file_io.py file.

Tests for crash-safe atomic file writing utilities.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import errno
import io
import json
import os
import stat
import sys
from pathlib import Path
from typing import IO
from unittest.mock import patch

import pytest

from ardupilot_methodic_configurator.backend_safe_file_io import safe_write

# pylint: disable=redefined-outer-name


@pytest.fixture
def tmp_file(tmp_path: Path) -> Path:
    """Fixture providing a temporary file path."""
    return tmp_path / "test_output.json"


class TestSafeWriteBasicBehavior:
    """Tests for basic safe_write behavior."""

    def test_user_can_write_content_to_new_file(self, tmp_file: Path) -> None:
        """
        User can write content to a new file atomically.

        GIVEN: A target file path that does not yet exist
        WHEN: User calls safe_write with a write function
        THEN: File should be created with the correct content
        AND: No temporary files should remain
        """
        content = "Hello, World!\n"

        safe_write(str(tmp_file), lambda f: f.write(content))

        assert tmp_file.exists()
        assert tmp_file.read_text(encoding="utf-8") == content

    def test_user_can_overwrite_existing_file(self, tmp_file: Path) -> None:
        """
        User can atomically overwrite an existing file.

        GIVEN: A target file already containing some content
        WHEN: User calls safe_write with new content
        THEN: File should contain only the new content
        AND: Original content should be replaced
        """
        tmp_file.write_text("old content\n", encoding="utf-8")

        safe_write(str(tmp_file), lambda f: f.write("new content\n"))

        assert tmp_file.read_text(encoding="utf-8") == "new content\n"

    def test_file_is_fully_written_before_target_is_replaced(self, tmp_file: Path) -> None:
        """
        File is fully written to a temp location before replacing the target.

        GIVEN: A target file with existing content
        WHEN: safe_write is called with large content
        THEN: Target should contain the complete new content
        AND: File should be readable immediately after write
        """
        large_content = "x" * 100000 + "\n"

        safe_write(str(tmp_file), lambda f: f.write(large_content))

        result = tmp_file.read_text(encoding="utf-8")
        assert result == large_content

    def test_user_can_write_json_content(self, tmp_file: Path) -> None:
        """
        User can write JSON content to a file using safe_write.

        GIVEN: A dictionary of data to persist
        WHEN: User writes JSON data via safe_write
        THEN: File should contain valid JSON with the expected data
        """
        data = {"key": "value", "number": 42, "nested": {"list": [1, 2, 3]}}

        safe_write(str(tmp_file), lambda f: json.dump(data, f, indent=2))

        written = json.loads(tmp_file.read_text(encoding="utf-8"))
        assert written == data

    def test_user_can_write_unicode_content(self, tmp_file: Path) -> None:
        """
        User can write Unicode content to a file using safe_write.

        GIVEN: Text content containing non-ASCII Unicode characters
        WHEN: User writes the content via safe_write
        THEN: File should be readable with the correct Unicode content preserved
        """
        unicode_content = "Héllo Wörld — 日本語テスト\n"

        safe_write(str(tmp_file), lambda f: f.write(unicode_content))

        assert tmp_file.read_text(encoding="utf-8") == unicode_content

    def test_no_temporary_files_remain_after_successful_write(self, tmp_path: Path) -> None:
        """
        No temporary files remain after a successful write operation.

        GIVEN: A target file path
        WHEN: safe_write completes successfully
        THEN: No .tmp files should remain in the directory
        """
        tmp_file = tmp_path / "output.json"

        safe_write(str(tmp_file), lambda f: f.write("content"))

        tmp_files = list(tmp_path.glob("*.tmp"))
        assert not tmp_files, f"Found leftover temp files: {tmp_files}"


class TestSafeWriteFilePermissions:
    """Tests for safe_write file permission handling."""

    @pytest.mark.skipif(sys.platform == "win32", reason="POSIX permission bits are not meaningful on Windows")
    def test_new_file_gets_default_permissions(self, tmp_file: Path) -> None:
        """
        New file created by safe_write gets reasonable default permissions.

        GIVEN: A target file path that does not exist
        WHEN: safe_write creates the file
        THEN: File should have readable permissions
        """
        safe_write(str(tmp_file), lambda f: f.write("content"))

        assert os.access(str(tmp_file), os.R_OK)
        assert os.access(str(tmp_file), os.W_OK)

    @pytest.mark.skipif(sys.platform == "win32", reason="POSIX permission bits are not meaningful on Windows")
    def test_file_permissions_are_preserved_on_overwrite(self, tmp_file: Path) -> None:
        """
        Existing file permissions are preserved when safe_write overwrites the file.

        GIVEN: An existing file with specific permissions
        WHEN: safe_write overwrites it
        THEN: The file permissions should be preserved (or close to original)
        """
        tmp_file.write_text("original content", encoding="utf-8")
        original_mode = os.stat(str(tmp_file)).st_mode

        safe_write(str(tmp_file), lambda f: f.write("new content"))

        new_mode = os.stat(str(tmp_file)).st_mode
        # Permissions should be preserved (same mode bits for owner/group/other read+write)
        assert (new_mode & 0o666) == (original_mode & 0o666)

    def test_safe_write_handles_file_not_found_for_stat(self, tmp_path: Path) -> None:
        """
        safe_write handles the case where the target doesn't exist (for stat).

        GIVEN: A target file path that does not exist
        WHEN: safe_write tries to stat the target to preserve permissions
        THEN: FileNotFoundError should be handled gracefully
        AND: The write should still succeed with default permissions
        """
        new_file = tmp_path / "nonexistent_parent" / "output.txt"
        new_file.parent.mkdir(parents=True)

        safe_write(str(new_file), lambda f: f.write("content"))

        assert new_file.exists()
        assert new_file.read_text(encoding="utf-8") == "content"


class TestSafeWriteErrorHandling:
    """Tests for safe_write error handling behavior."""

    def test_cleanup_happens_when_write_fails(self, tmp_path: Path) -> None:
        """
        Temporary file is cleaned up when write function raises an exception.

        GIVEN: A write function that raises an exception
        WHEN: safe_write is called and the write fails
        THEN: No temporary files should remain in the directory
        AND: An exception should be raised to the caller
        """

        def failing_write(_f: io.TextIOWrapper) -> None:
            msg = "Simulated disk full"
            raise OSError(msg)

        tmp_file = tmp_path / "output.txt"

        with pytest.raises(OSError, match="Simulated disk full"):
            safe_write(str(tmp_file), failing_write)

        tmp_files = list(tmp_path.glob("*.tmp"))
        assert not tmp_files, f"Temp files not cleaned up: {tmp_files}"

        # Target should not have been created
        assert not tmp_file.exists()

    def test_directory_fsync_failure_does_not_break_write(self, tmp_file: Path) -> None:
        """
        Directory fsync failure does not break the write operation.

        GIVEN: A system where directory fsync fails
        WHEN: safe_write is called
        THEN: The file write should still succeed
        AND: The error from fsync should be silently ignored
        """
        with patch(
            "ardupilot_methodic_configurator.backend_safe_file_io.os.fsync",
            side_effect=[None, OSError("fsync failed")],
        ):
            safe_write(str(tmp_file), lambda f: f.write("test content"))

        assert tmp_file.exists()
        assert tmp_file.read_text(encoding="utf-8") == "test content"


@pytest.mark.parametrize("failure_stage", ["writer", "fsync", "replace"])
def test_failed_update_preserves_the_original_and_removes_temporary_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, failure_stage: str
) -> None:
    """
    A failed save must leave the last valid file available.

    GIVEN: An existing file and a failure during writing, syncing, or replacement
    WHEN: The save fails after writing some temporary content
    THEN: The original content survives, the error propagates, and no temporary file remains
    """
    target = tmp_path / "settings.json"
    target.write_text("original", encoding="utf-8")

    def fail(*_args: object) -> None:
        message = "save failed"
        raise OSError(message)

    def write(file: IO[str]) -> None:
        file.write("partial update")
        if failure_stage == "writer":
            fail()

    if failure_stage != "writer":
        monkeypatch.setattr(f"ardupilot_methodic_configurator.backend_safe_file_io.os.{failure_stage}", fail)

    with pytest.raises(OSError, match="save failed"):
        safe_write(str(target), write)

    assert target.read_text(encoding="utf-8") == "original"
    assert list(tmp_path.iterdir()) == [target]


@pytest.mark.skipif(sys.platform == "win32", reason="Requires POSIX file permissions")
@pytest.mark.parametrize(("umask", "expected_mode"), [(0o022, 0o644), (0o027, 0o640)])
def test_new_file_uses_the_current_umask_without_changing_it(tmp_path: Path, umask: int, expected_mode: int) -> None:
    """
    New files follow the caller's permission policy.

    GIVEN: A restrictive process umask
    WHEN: A new file is saved atomically
    THEN: Its mode matches normal file creation and the umask is restored
    """
    target = tmp_path / "private.json"
    previous_umask = os.umask(umask)
    try:
        safe_write(str(target), lambda file: file.write("content"))
        resulting_umask = os.umask(previous_umask)
    finally:
        os.umask(previous_umask)

    assert stat.S_IMODE(target.stat().st_mode) == expected_mode
    assert resulting_umask == umask


@pytest.mark.skipif(sys.platform == "win32", reason="Requires POSIX file permissions")
def test_overwrite_preserves_custom_permission_bits(tmp_path: Path) -> None:
    """
    Atomic replacement preserves an existing file's access policy.

    GIVEN: An existing file with executable and restricted permission bits
    WHEN: Its content is replaced
    THEN: All permission bits survive the update
    """
    target = tmp_path / "script"
    target.write_text("original", encoding="utf-8")
    target.chmod(0o751)

    safe_write(str(target), lambda file: file.write("updated"))

    assert stat.S_IMODE(target.stat().st_mode) == 0o751
    assert target.read_text(encoding="utf-8") == "updated"


@pytest.mark.skipif(sys.platform == "win32", reason="Requires POSIX directory fsync")
def test_save_flushes_and_syncs_content_before_replacing_and_syncing_the_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    A successful save persists content before making the replacement visible.

    GIVEN: An existing file in a destination directory
    WHEN: New content is saved
    THEN: The temporary file is flushed and synced before replacement, then the directory is synced
    """
    target = tmp_path / "settings.json"
    target.write_text("original", encoding="utf-8")
    events: list[str] = []
    real_fsync, real_replace = os.fsync, os.replace
    directory_fds: list[int] = []

    def sync(fd: int) -> None:
        if stat.S_ISDIR(os.fstat(fd).st_mode):
            events.append("directory synced")
            directory_fds.append(fd)
        else:
            temporary_file = next(path for path in tmp_path.iterdir() if path != target)
            assert temporary_file.read_bytes() == b"updated\n"
            assert target.read_text(encoding="utf-8") == "original"
            events.append("content synced")
        real_fsync(fd)

    def replace(source: str, destination: str) -> None:
        assert Path(source).parent == target.parent
        assert destination == str(target)
        assert events == ["content synced"]
        events.append("replaced")
        real_replace(source, destination)

    monkeypatch.setattr("ardupilot_methodic_configurator.backend_safe_file_io.os.fsync", sync)
    monkeypatch.setattr("ardupilot_methodic_configurator.backend_safe_file_io.os.replace", replace)

    safe_write(str(target), lambda file: file.write("updated\n"))

    assert events == ["content synced", "replaced", "directory synced"]
    assert target.read_bytes() == b"updated\n"
    assert list(tmp_path.iterdir()) == [target]
    with pytest.raises(OSError, match=os.strerror(errno.EBADF)) as error:
        os.fstat(directory_fds[0])
    assert error.value.errno == errno.EBADF


def test_relative_destination_is_saved_in_the_current_directory(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Relative filenames receive the same atomic-save guarantees as full paths.

    GIVEN: A destination with no directory component
    WHEN: Its content is saved
    THEN: The file appears in the current directory without leftover temporary files
    """
    monkeypatch.chdir(tmp_path)

    safe_write("settings.json", lambda file: file.write("content"))

    target = tmp_path / "settings.json"
    assert target.read_text(encoding="utf-8") == "content"
    assert list(tmp_path.iterdir()) == [target]


@pytest.mark.parametrize("denied_operation", ["chmod", "chown"])
def test_denied_metadata_preservation_does_not_discard_the_saved_content(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, denied_operation: str
) -> None:
    """
    Unsupported metadata changes must not prevent an otherwise valid save.

    GIVEN: An existing file and an OS denial when preserving permissions or ownership
    WHEN: The file is updated
    THEN: The content is saved and the temporary file is removed
    """
    if not hasattr(os, denied_operation):
        pytest.skip(f"{denied_operation} is not available on this platform")
    target = tmp_path / "settings.json"
    target.write_text("original", encoding="utf-8")

    def deny(*_args: object) -> None:
        message = "metadata denied"
        raise PermissionError(message)

    monkeypatch.setattr(f"ardupilot_methodic_configurator.backend_safe_file_io.os.{denied_operation}", deny)

    safe_write(str(target), lambda file: file.write("updated"))

    assert target.read_text(encoding="utf-8") == "updated"
    assert list(tmp_path.iterdir()) == [target]


def test_directory_open_failure_does_not_discard_a_completed_save(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Directory syncing remains best effort after a successful replacement.

    GIVEN: A filesystem that cannot open directories for syncing
    WHEN: File replacement succeeds but opening its directory fails
    THEN: The completed save remains available without reporting a failed write
    """
    target = tmp_path / "settings.json"
    real_open = os.open

    def open_file(path: str, flags: int, mode: int = 0o777, *, dir_fd: int | None = None) -> int:
        if path == str(tmp_path):
            message = "directory open failed"
            raise OSError(message)
        return real_open(path, flags, mode, dir_fd=dir_fd)

    monkeypatch.setattr("ardupilot_methodic_configurator.backend_safe_file_io.os.open", open_file)

    safe_write(str(target), lambda file: file.write("updated"))

    assert target.read_text(encoding="utf-8") == "updated"
    assert list(tmp_path.iterdir()) == [target]


@pytest.mark.skipif(not hasattr(os, "chown"), reason="Ownership preservation requires os.chown")
def test_atomic_save_requests_the_original_owner_and_group_for_the_replacement(tmp_path: Path) -> None:
    """
    Preserve the ownership policy when replacing an existing file.

    GIVEN: An existing file with an owner and group
    WHEN: Its replacement is prepared for an atomic save
    THEN: The OS is asked to apply the original owner and group to that replacement
    """
    target = tmp_path / "settings.json"
    target.write_text("original", encoding="utf-8")
    original = target.stat()

    with patch("ardupilot_methodic_configurator.backend_safe_file_io.os.chown", autospec=True) as set_owner:
        safe_write(str(target), lambda file: file.write("updated"))

    set_owner.assert_called_once()
    replacement, owner, group = set_owner.call_args.args
    assert (owner, group) == (original.st_uid, original.st_gid)
    assert Path(replacement).parent == target.parent
    assert Path(replacement) != target
    assert target.read_text(encoding="utf-8") == "updated"


@pytest.mark.skipif(sys.platform == "win32", reason="Requires POSIX directory descriptors")
def test_directory_close_failure_does_not_report_a_successful_save_as_failed(tmp_path: Path) -> None:
    """
    A best-effort directory-close error must not undo a completed save.

    GIVEN: A directory descriptor whose close operation reports an I/O error
    WHEN: The file is saved and its directory is synced
    THEN: The save succeeds and the directory descriptor is released
    """
    target = tmp_path / "settings.json"
    real_close = os.close
    closed: list[int] = []

    def close_with_error(fd: int) -> None:
        real_close(fd)
        closed.append(fd)
        message = "directory close failed"
        raise OSError(message)

    with patch("ardupilot_methodic_configurator.backend_safe_file_io.os.close", side_effect=close_with_error):
        safe_write(str(target), lambda file: file.write("updated"))

    assert len(closed) == 1
    with pytest.raises(OSError, match=os.strerror(errno.EBADF)) as error:
        os.fstat(closed[0])
    assert error.value.errno == errno.EBADF
    assert target.read_text(encoding="utf-8") == "updated"
    assert list(tmp_path.iterdir()) == [target]


def test_temporary_file_cleanup_failure_preserves_the_original_write_error(tmp_path: Path) -> None:
    """
    Report the original save failure even if temporary-file cleanup also fails.

    GIVEN: An existing file, a failed writer, and an OS error removing its temporary file
    WHEN: Atomic saving aborts
    THEN: The original error reaches the caller and the previous file remains intact
    """
    target = tmp_path / "settings.json"
    target.write_text("original", encoding="utf-8")
    write_error = ValueError("cannot serialize settings")

    def fail_write(file: IO[str]) -> None:
        file.write("partial update")
        raise write_error

    with (
        patch(
            "ardupilot_methodic_configurator.backend_safe_file_io.os.unlink", side_effect=OSError("cleanup denied")
        ) as cleanup,
        pytest.raises(ValueError, match="cannot serialize settings") as error,
    ):
        safe_write(str(target), fail_write)

    assert error.value is write_error
    cleanup.assert_called_once()
    assert target.read_text(encoding="utf-8") == "original"
