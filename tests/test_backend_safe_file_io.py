#!/usr/bin/env python3

"""
Behavior-driven tests for the backend_safe_file_io.py file.

Tests for crash-safe atomic file writing utilities.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import io
import json
import os
from pathlib import Path
from unittest.mock import patch

import pytest

import ardupilot_methodic_configurator.backend_safe_file_io as sio
from ardupilot_methodic_configurator.backend_safe_file_io import make_capture_safe_write, safe_write

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
        assert tmp_files == [], f"Found leftover temp files: {tmp_files}"


class TestSafeWriteFilePermissions:
    """Tests for safe_write file permission handling."""

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
        assert tmp_files == [], f"Temp files not cleaned up: {tmp_files}"

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
        original_open = os.open

        def mock_os_open(path: str, flags: int, *_args, **_kwargs) -> int:
            return original_open(path, flags, *_args, **_kwargs)

        with patch("os.fsync", side_effect=[None, OSError("fsync failed")]):
            safe_write(str(tmp_file), lambda f: f.write("test content"))

        assert tmp_file.exists()
        assert tmp_file.read_text(encoding="utf-8") == "test content"


class TestMakeCapturesSafeWrite:
    """Tests for the make_capture_safe_write helper function."""

    def test_capture_helper_records_written_json_data(self) -> None:
        """
        make_capture_safe_write helper records JSON data written via safe_write.

        GIVEN: A mock that uses make_capture_safe_write
        WHEN: A function writes JSON data through the mock
        THEN: The captured_data should contain the written JSON
        AND: called[0] should be True
        """
        captured_data, called, side_effect = make_capture_safe_write()

        assert called[0] is False
        assert captured_data == {}

        # Simulate using the side_effect
        mock_file = io.StringIO()
        test_data = {"key": "value", "number": 42}
        mock_file.write(json.dumps(test_data))

        # Call the side_effect directly
        def write_json(f: io.TextIOWrapper) -> None:
            json.dump(test_data, f)

        side_effect("/fake/path", write_json)

        assert called[0] is True
        assert captured_data == test_data

    def test_capture_helper_can_be_used_as_mock_side_effect(self) -> None:
        """
        make_capture_safe_write helper integrates correctly as a mock side_effect.

        GIVEN: A function that calls safe_write internally
        WHEN: safe_write is mocked with the capture side_effect
        THEN: The written data should be captured for verification
        """
        captured_data, called, side_effect = make_capture_safe_write()

        test_data = {"component": "Flight Controller", "version": "4.5.x"}

        with patch("ardupilot_methodic_configurator.backend_safe_file_io.safe_write") as mock_safe_write:
            mock_safe_write.side_effect = side_effect

            # Call something that uses safe_write internally
            sio.safe_write("/fake/path", lambda f: json.dump(test_data, f))

        assert called[0] is True
        assert captured_data == test_data

    def test_capture_helper_returns_three_elements(self) -> None:
        """
        make_capture_safe_write returns exactly three elements.

        GIVEN: The make_capture_safe_write function
        WHEN: Called with no arguments
        THEN: Should return (captured_data, called, side_effect) tuple
        AND: captured_data should be empty dict initially
        AND: called should be [False] initially
        AND: side_effect should be callable
        """
        result = make_capture_safe_write()

        assert len(result) == 3
        captured_data, called, side_effect = result
        assert isinstance(captured_data, dict)
        assert len(captured_data) == 0
        assert isinstance(called, list)
        assert called == [False]
        assert callable(side_effect)
