#!/usr/bin/env python3

"""
Tk-independent file-browser transfer planning and worker tests.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import sys
import typing
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from ardupilot_methodic_configurator.backend_flightcontroller_files import FlightControllerLogFile, LastLogDownloadResult
from ardupilot_methodic_configurator.frontend_tkinter_file_browser_operations import (
    LocalFileEntry,
    LocalUploadPlan,
    RemoteDownloadPlan,
    TransferBatchResults,
    _build_local_upload_plan,
    _build_remote_download_plan,
    _download_last_flight_log_worker,
    _download_remote_plan_worker,
    _local_directory_entries,
    _local_target_conflicts,
    _local_upload_plan,
    _remote_download_plan,
    _upload_local_plan_worker,
)


def test_transfer_batch_results_replace_retried_failure_and_verification() -> None:
    """The shared retry state retains order, clears stale CRCs, and removes recovered failures."""
    results = TransferBatchResults()
    results.prepare(["/a", "/b"])
    results.verification.update({"/a": True, "/b": False})
    results.record(["/a"], ["/b", "/directory"])

    results.prepare(["/b"])
    assert results.verification == {"/a": True}
    results.verification["/b"] = True
    results.record(["/b"], ["/b"])

    assert results.succeeded == ["/a", "/b"]
    assert results.failed == ["/directory"]
    assert results.verification == {"/a": True, "/b": True}


def test_operation_annotations_resolve_at_runtime() -> None:
    """Public planning annotations can be inspected by runtime tooling."""
    assert typing.get_type_hints(LocalFileEntry)["path"] == Path
    assert typing.get_type_hints(_build_local_upload_plan)


class TestFileBrowserOperations:
    """Exercise recursive plans and transfer workers without a Tk window."""

    def test_remote_download_plan_expands_directories_recursively(self) -> None:
        """
        A selected remote directory expands into nested local directories/files.

        GIVEN: A remote directory contains a nested directory and a file
        WHEN: A download plan is built
        THEN: Every remote file is mapped beneath the selected local directory
        """
        root = FlightControllerLogFile("folder", "/APM/LOGS/folder", 0, is_directory=True)
        nested = FlightControllerLogFile("nested", "/APM/LOGS/folder/nested", 0, is_directory=True)
        leaf = FlightControllerLogFile("leaf.bin", "/APM/LOGS/folder/nested/leaf.bin", 12)
        get_remote_files = MagicMock(side_effect=[[nested], [leaf]])

        directories, files = _remote_download_plan(
            root,
            Path("C:/downloads/folder"),
            get_remote_files,
        )

        assert directories == [Path("C:/downloads/folder"), Path("C:/downloads/folder/nested")]
        assert files == [(leaf, Path("C:/downloads/folder/nested/leaf.bin"))]

    def test_remote_download_plan_does_not_create_directory_when_listing_fails(self) -> None:
        """A failed recursive listing must not turn into a successful empty directory plan."""
        get_remote_files = MagicMock(return_value=None)
        root = FlightControllerLogFile("folder", "/APM/LOGS/folder", 0, is_directory=True)
        failures: list[str] = []

        directories, files = _remote_download_plan(
            root,
            Path("C:/downloads/folder"),
            get_remote_files,
            failures,
        )

        assert not directories
        assert not files
        assert failures == ["/APM/LOGS/folder"]

    def test_remote_download_plan_lists_each_selected_directory(self) -> None:
        """Recursive remote planning uses the listing callback."""
        entry = FlightControllerLogFile("folder", "/APM/LOGS/folder", 0, is_directory=True)
        get_remote_files = MagicMock(return_value=[])

        _remote_download_plan(entry, Path("C:/downloads/folder"), get_remote_files)

        get_remote_files.assert_called_once_with(entry.remote_path)

    def test_remote_download_plan_rejects_windows_unsafe_names(self) -> None:
        """A hostile remote basename cannot become a Windows drive-relative path."""
        entry = FlightControllerLogFile("C:evil.bin", "/APM/LOGS/C:evil.bin", 12)

        plan = _build_remote_download_plan([entry], Path("C:/downloads"), MagicMock())

        assert not plan.directories
        assert not plan.files
        assert plan.failed == ("/APM/LOGS/C:evil.bin",)

    def test_local_target_conflicts_reports_exact_duplicate_targets(self, tmp_path: Path) -> None:
        """Two planned entries with the same target are rejected as duplicates."""
        target = tmp_path / "same.bin"
        first = FlightControllerLogFile("first.bin", "/APM/LOGS/first.bin", 10)
        second = FlightControllerLogFile("second.bin", "/APM/LOGS/second.bin", 20)
        plan = RemoteDownloadPlan((), ((first, target), (second, target)))

        duplicate_targets, existing_conflicts = _local_target_conflicts(plan)

        assert duplicate_targets == [target]
        assert not existing_conflicts

    def test_local_target_conflicts_reports_file_ancestor_targets(self, tmp_path: Path) -> None:
        """A planned file cannot also be an ancestor of another target."""
        file_target = tmp_path / "target"
        nested_target = file_target / "nested.bin"
        first = FlightControllerLogFile("target", "/APM/LOGS/target", 10)
        second = FlightControllerLogFile("nested.bin", "/APM/LOGS/nested.bin", 20)
        plan = RemoteDownloadPlan((), ((first, file_target), (second, nested_target)))

        duplicate_targets, existing_conflicts = _local_target_conflicts(plan)

        assert duplicate_targets == [nested_target]
        assert not existing_conflicts

    def test_local_upload_plan_expands_directories_recursively(self) -> None:
        """
        A selected local directory expands into remote directories/files.

        GIVEN: A local directory entry contains one nested file
        WHEN: An upload plan is built
        THEN: The remote directory and file paths preserve the hierarchy
        """
        root_path = MagicMock()
        child_path = MagicMock()
        root_path.iterdir.return_value = [child_path]
        root_path.name = "folder"
        child_path.name = "leaf.bin"
        root_path.is_symlink.return_value = False
        child_path.is_symlink.return_value = False
        root_path.is_dir.return_value = True
        child_path.is_dir.return_value = False
        child_path.stat.return_value.st_size = 12
        entry = LocalFileEntry("folder", root_path, 0, is_directory=True)

        directories, files = _local_upload_plan(entry, "/APM/LOGS/folder")

        assert directories == ["/APM/LOGS/folder"]
        assert files == [(child_path, "/APM/LOGS/folder/leaf.bin", 12)]

    def test_local_directory_entries_are_shared_by_panel_refresh_and_upload_planning(self) -> None:
        """Local enumeration supplies the same metadata to both consumers."""
        directory = MagicMock()
        child = MagicMock()
        child.name = "leaf.bin"
        child.is_symlink.return_value = False
        child.is_dir.return_value = False
        child.stat.return_value.st_size = 12
        child.stat.return_value.st_mtime = 34.5
        directory.iterdir.return_value = [child]

        assert _local_directory_entries(directory) == [
            LocalFileEntry("leaf.bin", child, 12, is_directory=False, modified_at=34.5)
        ]

    def test_upload_plan_rejects_unsafe_local_names(self, tmp_path: Path) -> None:
        """Names that cannot be listed safely on the remote panel are not uploaded."""
        invalid = LocalFileEntry("bad:name.bin", tmp_path / "bad:name.bin", 12)
        valid = LocalFileEntry("good.bin", tmp_path / "good.bin", 8)

        plan = _build_local_upload_plan([invalid, valid], "/APM/LOGS/")

        assert plan.files == ((valid.path, "/APM/LOGS/good.bin", 8),)
        assert plan.failed == ("/APM/LOGS/bad:name.bin",)

    def test_upload_plan_rejects_unsafe_nested_names(self) -> None:
        """Invalid children are reported without preventing safe siblings."""
        root = MagicMock()
        invalid = MagicMock()
        valid = MagicMock()
        root.name = "folder"
        root.iterdir.return_value = [invalid, valid]
        invalid.name = "bad:name.bin"
        invalid.is_symlink.return_value = False
        invalid.is_dir.return_value = False
        invalid.stat.return_value.st_size = 12
        valid.name = "good.bin"
        valid.is_symlink.return_value = False
        valid.is_dir.return_value = False
        valid.stat.return_value.st_size = 8

        plan = _build_local_upload_plan([LocalFileEntry("folder", root, 0, is_directory=True)], "/APM/LOGS/")

        assert plan.files == ((valid, "/APM/LOGS/folder/good.bin", 8),)
        assert plan.failed == ("/APM/LOGS/folder/bad:name.bin",)

    def test_upload_skips_files_below_failed_remote_directory(self) -> None:
        """A failed mkdir prevents attempts to upload descendants, but not siblings."""
        failed_file = Path("folder/child.bin")
        good_file = Path("other/good.bin")
        plan = LocalUploadPlan(
            ("/APM/LOGS/folder", "/APM/LOGS/folder/nested", "/APM/LOGS/other"),
            (
                (failed_file, "/APM/LOGS/folder/nested/child.bin", 5),
                (good_file, "/APM/LOGS/other/good.bin", 8),
            ),
        )
        make_directory = MagicMock(side_effect=[False, True])
        upload = MagicMock(return_value=True)

        succeeded, failed = _upload_local_plan_worker(plan, 13, make_directory, upload, MagicMock())

        assert succeeded == ["/APM/LOGS/other", "/APM/LOGS/other/good.bin"]
        assert "/APM/LOGS/folder" in failed
        assert "/APM/LOGS/folder/nested/child.bin" in failed
        make_directory.assert_any_call("/APM/LOGS/other")
        upload.assert_called_once()
        assert upload.call_args.args[:2] == (str(good_file), "/APM/LOGS/other/good.bin")

    def test_upload_worker_reports_successful_directory_creation(self) -> None:
        """A directory created during a transfer is included in successful results."""
        plan = LocalUploadPlan(
            ("/APM/LOGS/folder",),
            ((Path("folder/child.bin"), "/APM/LOGS/folder/child.bin", 5),),
        )

        succeeded, failed = _upload_local_plan_worker(
            plan,
            5,
            MagicMock(return_value=True),
            MagicMock(return_value=True),
            MagicMock(),
        )

        assert succeeded == ["/APM/LOGS/folder", "/APM/LOGS/folder/child.bin"]
        assert failed == []  # pylint: disable=use-implicit-booleaness-not-comparison

    @pytest.mark.skipif(sys.platform == "win32", reason="CI validates symbolic-link containment on POSIX.")
    def test_download_worker_rejects_a_symlinked_destination_ancestor(self, tmp_path: Path) -> None:
        """A symlink below the selected directory cannot redirect a download."""
        destination = tmp_path / "destination"
        outside = tmp_path / "outside"
        destination.mkdir()
        outside.mkdir()
        redirected = destination / "folder"
        redirected.symlink_to(outside, target_is_directory=True)

        nested_target = redirected / "nested"
        target = nested_target / "log.bin"
        entry = FlightControllerLogFile("log.bin", "/APM/LOGS/folder/nested/log.bin", 12)
        plan = RemoteDownloadPlan((redirected, nested_target), ((entry, target),))
        download_remote_file = MagicMock()
        progress = MagicMock()

        succeeded, failed = _download_remote_plan_worker(
            plan,
            destination,
            12,
            download_remote_file,
            progress,
        )

        assert not succeeded
        assert entry.remote_path in failed
        assert not (outside / "nested" / "log.bin").exists()
        download_remote_file.assert_not_called()

    def test_download_worker_reports_success(self, tmp_path: Path) -> None:
        """The remote download worker passes the path and progress callback."""
        destination = tmp_path / "destination"
        destination.mkdir()
        target = destination / "log.bin"
        entry = FlightControllerLogFile("log.bin", "/APM/LOGS/log.bin", 12)
        plan = RemoteDownloadPlan((), ((entry, target),))
        download_remote_file = MagicMock(return_value=True)

        succeeded, failed = _download_remote_plan_worker(
            plan,
            destination,
            12,
            download_remote_file,
            MagicMock(),
        )

        assert succeeded == [entry.remote_path]
        assert failed == []  # pylint: disable=use-implicit-booleaness-not-comparison
        assert download_remote_file.call_args.args[:2] == (entry.remote_path, str(target))
        assert callable(download_remote_file.call_args.args[2])

    def test_download_worker_reports_successful_directory_creation(self, tmp_path: Path) -> None:
        """A directory created during a download is included in successful results."""
        destination = tmp_path / "destination"
        destination.mkdir()
        directory = destination / "folder"
        target = directory / "log.bin"
        entry = FlightControllerLogFile("log.bin", "/APM/LOGS/log.bin", 12)
        plan = RemoteDownloadPlan((directory,), ((entry, target),))

        succeeded, failed = _download_remote_plan_worker(
            plan,
            destination,
            12,
            MagicMock(return_value=True),
            MagicMock(),
        )

        assert succeeded == [str(directory), entry.remote_path]
        assert failed == []  # pylint: disable=use-implicit-booleaness-not-comparison

    def test_download_verification_failure_is_retryable(self, tmp_path: Path) -> None:
        """A successful transfer with mismatched CRC remains a failed batch item."""
        entry = FlightControllerLogFile("log.bin", "/APM/LOGS/log.bin", 12)
        plan = RemoteDownloadPlan((), ((entry, tmp_path / "log.bin"),))
        verification: dict[str, bool | None] = {}

        succeeded, failed = _download_remote_plan_worker(
            plan,
            tmp_path,
            12,
            MagicMock(return_value=True),
            MagicMock(),
            verify_remote_file=MagicMock(return_value=False),
            verification_results=verification,
        )

        assert not succeeded
        assert failed == [entry.remote_path]
        assert verification == {entry.remote_path: False}

    def test_verification_keeps_progress_open_until_crc_finishes(self, tmp_path: Path) -> None:
        """The final file callback cannot announce completion before CRC returns."""
        entry = FlightControllerLogFile("log.bin", "/APM/LOGS/log.bin", 12)
        plan = RemoteDownloadPlan((), ((entry, tmp_path / "log.bin"),))
        progress: list[tuple[int, int]] = []
        progress_during_crc: list[tuple[int, int]] = []

        def download(_remote: str, _local: str, callback) -> bool:
            callback(100, 100)
            return True

        def verify(_remote: str, _local: str) -> bool:
            progress_during_crc.append(progress[-1])
            return True

        succeeded, failed = _download_remote_plan_worker(
            plan, tmp_path, 12, download, lambda *args: progress.append(args), verify_remote_file=verify
        )

        assert succeeded == [entry.remote_path]
        assert not failed
        assert progress_during_crc[0][0] < progress_during_crc[0][1]
        assert progress[-1] == (12, 12)

    def test_upload_verification_can_be_skipped_for_virtual_file(self) -> None:
        """An unsupported verification result must not masquerade as verified."""
        plan = LocalUploadPlan((), ((Path("threads.txt"), "/@SYS/threads.txt", 12),))
        verification: dict[str, bool | None] = {}

        succeeded, failed = _upload_local_plan_worker(
            plan,
            12,
            MagicMock(),
            MagicMock(return_value=True),
            MagicMock(),
            verify_remote_file=MagicMock(return_value=None),
            verification_results=verification,
        )

        assert succeeded == ["/@SYS/threads.txt"]
        assert not failed
        assert verification == {"/@SYS/threads.txt": None}

    def test_last_log_worker_passes_progress_to_backend(self) -> None:
        """The last-log worker passes a progress callback to the backend."""
        download_last_flight_log = MagicMock(return_value=LastLogDownloadResult.SUCCESS)
        progress = MagicMock()

        outcome = _download_last_flight_log_worker(
            "last.BIN",
            download_last_flight_log,
            progress,
        )

        assert outcome is LastLogDownloadResult.SUCCESS
        download_last_flight_log.assert_called_once_with("last.BIN", progress)

    def test_last_log_worker_maps_unexpected_exception_to_failure(self) -> None:
        """Unexpected worker errors must not be mistaken for confirmed no-logs."""
        download = MagicMock(side_effect=RuntimeError("MAVFTP failed"))

        assert _download_last_flight_log_worker("last.BIN", download, MagicMock()) is LastLogDownloadResult.FAILED
