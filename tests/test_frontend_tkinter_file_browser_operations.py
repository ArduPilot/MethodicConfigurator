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
from unittest.mock import MagicMock, patch

import pytest

from ardupilot_methodic_configurator.backend_flightcontroller_files import FlightControllerLogFile, LastLogDownloadResult
from ardupilot_methodic_configurator.frontend_tkinter_file_browser_operations import (
    LocalFileEntry,
    LocalUploadPlan,
    RemoteDownloadPlan,
    TransferAttempt,
    TransferBatchResults,
    _build_local_upload_plan,
    _build_remote_download_plan,
    _create_remote_directory_worker,
    _delete_remote_entries_worker,
    _download_last_flight_log_worker,
    _download_remote_plan_worker,
    _local_directory_entries,
    _local_target_conflicts,
    _local_target_is_contained,
    _local_upload_plan,
    _prepare_remote_download,
    _remote_download_plan,
    _rename_remote_entry_worker,
    _retry_local_upload_plan,
    _retry_remote_download_plan,
    _upload_local_plan_worker,
    format_transfer_summary,
)


def test_transfer_batch_results_replace_retried_failure_and_verification() -> None:
    """The shared retry state retains order, clears stale CRCs, and removes recovered failures."""
    results = TransferBatchResults()
    results.prepare(["/a", "/b"])
    results.record(
        TransferAttempt(
            files_succeeded=["/a"],
            files_failed=["/b"],
            other_failed=["/directory"],
            verification={"/a": True, "/b": False},
        )
    )

    results.prepare(["/b"])
    assert results.verification == {"/a": True}
    results.record(TransferAttempt(files_succeeded=["/b"], files_failed=["/b"], verification={"/b": True}))

    assert results.succeeded == ["/a", "/b"]
    assert results.failed == ["/directory"]
    assert results.verification == {"/a": True, "/b": True}


def test_download_directory_success_does_not_erase_colliding_file_failure(tmp_path: Path) -> None:
    """A local directory and remote file can have identical path strings."""
    directory = FlightControllerLogFile("folder", "/remote/folder", 0, is_directory=True)
    remote_file = FlightControllerLogFile("other.bin", str(tmp_path / "folder"), 5)
    plan = _build_remote_download_plan([directory, remote_file], tmp_path, MagicMock(return_value=[]))

    attempt = _download_remote_plan_worker(
        plan,
        tmp_path,
        5,
        MagicMock(return_value=False),
        MagicMock(),
    )
    results = TransferBatchResults()
    results.record(attempt)

    assert attempt.directories_succeeded == [str(tmp_path / "folder")]
    assert attempt.files_failed == [remote_file.remote_path]
    assert str(tmp_path / "folder") in results.failed


def test_failed_directory_retry_is_not_cleared_by_earlier_success() -> None:
    """A directory that fails on retry remains failed even if it succeeded before."""
    results = TransferBatchResults()
    results.record(TransferAttempt(directories_succeeded=["/folder"], files_failed=["/folder/file.bin"]))
    results.record(TransferAttempt(directories_failed=["/folder"], files_failed=["/folder/file.bin"]))

    assert "/folder" in results.failed
    assert "/folder/file.bin" in results.failed


def test_file_success_does_not_hide_a_directory_failure_with_the_same_path() -> None:
    """The two path namespaces remain separate in either collision direction."""
    results = TransferBatchResults()
    results.record(TransferAttempt(files_succeeded=["/same"], directories_failed=["/same"]))

    assert results.succeeded == ["/same"]
    assert results.failed == ["/same"]


def test_format_transfer_summary_keeps_failures_and_file_successes_visible() -> None:
    """Formatting can be checked without creating a Tk window."""
    results = TransferBatchResults()
    directories = [f"/dir-{index}" for index in range(20)]
    results.record(
        TransferAttempt(files_succeeded=["/good.bin"], files_failed=["/bad.bin"], directories_succeeded=directories)
    )

    summary = format_transfer_summary(results.succeeded, results.failed, {}, 20)

    assert "Succeeded: /good.bin" in summary
    assert "Failed: /bad.bin" in summary
    assert "… 2 more entries omitted." in summary


def test_operation_annotations_resolve_at_runtime() -> None:
    """Public planning annotations can be inspected by runtime tooling."""
    assert typing.get_type_hints(LocalFileEntry)["path"] == Path
    assert typing.get_type_hints(_build_local_upload_plan)


class TestFileBrowserOperations:  # pylint: disable=too-many-public-methods
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

    def test_remote_plan_keeps_sibling_file_when_nested_listing_fails(self, tmp_path: Path) -> None:
        """One unreadable child does not discard files discovered in the same directory."""
        root = FlightControllerLogFile("folder", "/APM/LOGS/folder", 0, is_directory=True)
        unreadable = FlightControllerLogFile("unreadable", "/APM/LOGS/folder/unreadable", 0, is_directory=True)
        log = FlightControllerLogFile("log.bin", "/APM/LOGS/folder/log.bin", 3)

        def list_remote(directory: str) -> list[FlightControllerLogFile]:
            if directory == root.remote_path:
                return [unreadable, log]
            message = "permission denied"
            raise PermissionError(message)

        plan = _build_remote_download_plan([root], tmp_path, list_remote)

        assert plan.directories == (tmp_path / "folder",)
        assert plan.files == ((log, tmp_path / "folder" / "log.bin"),)
        assert plan.failed == (unreadable.remote_path,)

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

    def test_download_preflight_prompts_for_existing_file_but_reuses_directory(self, tmp_path: Path) -> None:
        """A recursive download treats an existing directory differently from its file."""
        local_folder = tmp_path / "folder"
        local_folder.mkdir()
        (local_folder / "log.bin").write_bytes(b"old")
        root = FlightControllerLogFile("folder", "/APM/LOGS/folder", 0, is_directory=True)
        log = FlightControllerLogFile("log.bin", "/APM/LOGS/folder/log.bin", 3)

        preflight = _prepare_remote_download([root], tmp_path, lambda _directory: [log])

        assert preflight.plan.directories == (local_folder,)
        assert preflight.plan.files == ((log, local_folder / "log.bin"),)
        assert not preflight.duplicate_targets
        assert preflight.existing_conflicts == (local_folder / "log.bin",)

    def test_retry_plans_keep_only_failed_files_and_required_directories(self) -> None:
        """A retry never retransfers a successful sibling file."""
        good = FlightControllerLogFile("good.bin", "/APM/LOGS/folder/good.bin", 1)
        bad = FlightControllerLogFile("bad.bin", "/APM/LOGS/folder/bad.bin", 1)
        download = RemoteDownloadPlan(
            (Path("folder"),),
            ((good, Path("folder/good.bin")), (bad, Path("folder/bad.bin"))),
        )
        upload = LocalUploadPlan(
            ("/APM/LOGS/folder",),
            ((Path("good.bin"), good.remote_path, 1), (Path("bad.bin"), bad.remote_path, 1)),
        )

        download_retry = _retry_remote_download_plan(download, [bad.remote_path])
        upload_retry = _retry_local_upload_plan(upload, [bad.remote_path])

        assert download_retry.directories == download.directories
        assert download_retry.files == ((bad, Path("folder/bad.bin")),)
        assert upload_retry.directories == upload.directories
        assert upload_retry.files == ((Path("bad.bin"), bad.remote_path, 1),)

    def test_local_upload_plan_expands_directories_recursively(self, tmp_path: Path) -> None:
        """
        A selected local directory expands into remote directories/files.

        GIVEN: A local directory entry contains one nested file
        WHEN: An upload plan is built
        THEN: The remote directory and file paths preserve the hierarchy
        """
        root_path = tmp_path / "folder"
        nested_path = root_path / "nested"
        nested_path.mkdir(parents=True)
        child_path = nested_path / "leaf.bin"
        child_path.write_bytes(b"flight log!")
        entry = LocalFileEntry("folder", root_path, 0, is_directory=True)

        directories, files = _local_upload_plan(entry, "/APM/LOGS/folder")

        assert directories == ["/APM/LOGS/folder", "/APM/LOGS/folder/nested"]
        assert files == [(child_path, "/APM/LOGS/folder/nested/leaf.bin", len(b"flight log!"))]

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
        attempt = _upload_local_plan_worker(plan, 13, make_directory, upload, MagicMock())

        assert attempt.files_succeeded == ["/APM/LOGS/other/good.bin"]
        assert attempt.files_failed == ["/APM/LOGS/folder/nested/child.bin"]
        assert attempt.directories_succeeded == ["/APM/LOGS/other"]
        assert attempt.directories_failed == ["/APM/LOGS/folder", "/APM/LOGS/folder/nested"]
        make_directory.assert_any_call("/APM/LOGS/other")
        upload.assert_called_once()
        assert upload.call_args.args[:2] == (str(good_file), "/APM/LOGS/other/good.bin")

    def test_upload_worker_reports_successful_directory_creation(self) -> None:
        """A directory created during a transfer is included in successful results."""
        plan = LocalUploadPlan(
            ("/APM/LOGS/folder",),
            ((Path("folder/child.bin"), "/APM/LOGS/folder/child.bin", 5),),
        )

        attempt = _upload_local_plan_worker(
            plan,
            5,
            MagicMock(return_value=True),
            MagicMock(return_value=True),
            MagicMock(),
        )

        assert attempt.directories_succeeded == ["/APM/LOGS/folder"]
        assert attempt.files_succeeded == ["/APM/LOGS/folder/child.bin"]
        assert not attempt.files_failed

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

        attempt = _download_remote_plan_worker(
            plan,
            destination,
            12,
            download_remote_file,
            progress,
        )

        assert not attempt.files_succeeded
        assert entry.remote_path in attempt.files_failed
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

        attempt = _download_remote_plan_worker(
            plan,
            destination,
            12,
            download_remote_file,
            MagicMock(),
        )

        assert attempt.files_succeeded == [entry.remote_path]
        assert not attempt.files_failed
        assert download_remote_file.call_args.args[:2] == (entry.remote_path, str(target))
        assert callable(download_remote_file.call_args.args[2])

    def test_download_worker_rejects_target_outside_chosen_directory(self, tmp_path: Path) -> None:
        """A malformed plan cannot write a file beyond the selected local root."""
        destination = tmp_path / "destination"
        destination.mkdir()
        outside = tmp_path / "outside.bin"
        entry = FlightControllerLogFile("outside.bin", "/APM/LOGS/outside.bin", 3)
        attempted: list[str] = []

        def download(_remote: str, local: str, _progress: object) -> bool:
            attempted.append(local)
            Path(local).write_bytes(b"bad")
            return True

        attempt = _download_remote_plan_worker(
            RemoteDownloadPlan((), ((entry, outside),)), destination, 3, download, lambda _done, _total: None
        )

        assert not attempt.files_succeeded
        assert attempt.files_failed == [entry.remote_path]
        assert not attempted
        assert not outside.exists()

    def test_download_worker_reports_successful_directory_creation(self, tmp_path: Path) -> None:
        """A directory created during a download is included in successful results."""
        destination = tmp_path / "destination"
        destination.mkdir()
        directory = destination / "folder"
        target = directory / "log.bin"
        entry = FlightControllerLogFile("log.bin", "/APM/LOGS/log.bin", 12)
        plan = RemoteDownloadPlan((directory,), ((entry, target),))

        attempt = _download_remote_plan_worker(
            plan,
            destination,
            12,
            MagicMock(return_value=True),
            MagicMock(),
        )

        assert attempt.directories_succeeded == [str(directory)]
        assert attempt.files_succeeded == [entry.remote_path]
        assert not attempt.files_failed

    def test_download_verification_failure_is_retryable(self, tmp_path: Path) -> None:
        """A successful transfer with mismatched CRC remains a failed batch item."""
        entry = FlightControllerLogFile("log.bin", "/APM/LOGS/log.bin", 12)
        plan = RemoteDownloadPlan((), ((entry, tmp_path / "log.bin"),))
        attempt = _download_remote_plan_worker(
            plan,
            tmp_path,
            12,
            MagicMock(return_value=True),
            MagicMock(),
            verify_remote_file=MagicMock(return_value=False),
        )

        assert not attempt.files_succeeded
        assert attempt.files_failed == [entry.remote_path]
        assert attempt.verification == {entry.remote_path: False}

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

        attempt = _download_remote_plan_worker(
            plan, tmp_path, 12, download, lambda *args: progress.append(args), verify_remote_file=verify
        )

        assert attempt.files_succeeded == [entry.remote_path]
        assert not attempt.files_failed
        assert progress_during_crc[0][0] < progress_during_crc[0][1]
        assert progress[-1] == (12, 12)

    def test_upload_verification_keeps_progress_open_until_crc_finishes(self) -> None:
        """Upload progress also waits for optional CRC verification."""
        plan = LocalUploadPlan((), ((Path("log.bin"), "/APM/LOGS/log.bin", 12),))
        progress: list[tuple[int, int]] = []

        def upload(_local: str, _remote: str, callback) -> bool:
            callback(100, 100)
            return True

        def verify(_remote: str, _local: str) -> bool:
            assert progress[-1] == (11, 12)
            return True

        attempt = _upload_local_plan_worker(
            plan, 12, MagicMock(), upload, lambda *args: progress.append(args), verify_remote_file=verify
        )

        assert attempt.files_succeeded == ["/APM/LOGS/log.bin"]
        assert not attempt.files_failed
        assert progress[-1] == (12, 12)

    @pytest.mark.parametrize("direction", ["download", "upload"])
    def test_transfer_exception_records_failure_and_advances_progress(self, direction: str, tmp_path: Path) -> None:
        """An unexpected transfer exception fails only that file in either direction."""
        remote = "/APM/LOGS/log.bin"
        progress = MagicMock()
        verify = MagicMock()
        transfer = MagicMock(side_effect=RuntimeError("transfer failed"))
        if direction == "download":
            entry = FlightControllerLogFile("log.bin", remote, 12)
            outcome = _download_remote_plan_worker(
                RemoteDownloadPlan((), ((entry, tmp_path / "log.bin"),)),
                tmp_path,
                12,
                transfer,
                progress,
                verify_remote_file=verify,
            )
        else:
            outcome = _upload_local_plan_worker(
                LocalUploadPlan((), ((tmp_path / "log.bin", remote, 12),)),
                12,
                MagicMock(),
                transfer,
                progress,
                verify_remote_file=verify,
            )

        assert outcome.files_succeeded == []  # pylint: disable=use-implicit-booleaness-not-comparison
        assert outcome.files_failed == [remote]
        verify.assert_not_called()
        progress.assert_called_with(12, 12)

    def test_upload_verification_can_be_skipped_for_virtual_file(self) -> None:
        """An unsupported verification result must not masquerade as verified."""
        plan = LocalUploadPlan((), ((Path("threads.txt"), "/@SYS/threads.txt", 12),))
        attempt = _upload_local_plan_worker(
            plan,
            12,
            MagicMock(),
            MagicMock(return_value=True),
            MagicMock(),
            verify_remote_file=MagicMock(return_value=None),
        )

        assert attempt.files_succeeded == ["/@SYS/threads.txt"]
        assert not attempt.files_failed
        assert attempt.verification == {"/@SYS/threads.txt": None}

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

    def test_local_listing_reports_one_unreadable_entry_and_keeps_its_sibling(self) -> None:
        """
        A user can still browse readable files when one local entry becomes inaccessible.

        GIVEN: One directory entry raises an OS error while a sibling remains readable
        WHEN: The local directory is enumerated
        THEN: The readable entry is returned and the inaccessible path is reported
        """
        directory = MagicMock()
        unreadable = MagicMock(name="unreadable")
        unreadable.name = "broken.bin"
        unreadable.is_symlink.return_value = False
        unreadable.is_dir.side_effect = OSError("permission denied")
        readable = MagicMock(name="readable")
        readable.name = "good.bin"
        readable.is_symlink.return_value = False
        readable.is_dir.return_value = False
        readable.stat.return_value.st_size = 7
        readable.stat.return_value.st_mtime = 12.5
        symlink = MagicMock(name="symlink")
        symlink.name = "redirect.bin"
        symlink.is_symlink.return_value = True
        directory.iterdir.return_value = [readable, symlink, unreadable]
        entry_errors: list[object] = []

        entries = _local_directory_entries(directory, entry_errors.append)

        assert entries == [LocalFileEntry("good.bin", readable, 7, modified_at=12.5)]
        assert entry_errors == [unreadable]
        symlink.stat.assert_not_called()

    def test_summary_prioritizes_failures_when_the_display_limit_is_reached(self) -> None:
        """
        A user sees failed transfers before successful ones in a bounded summary.

        GIVEN: Failures alone fill the available summary lines
        WHEN: The transfer summary is formatted
        THEN: Only failures are shown and omitted entries are counted
        """
        summary = format_transfer_summary(["/good.bin"], ["/bad-1.bin", "/bad-2.bin"], None, 2)

        assert "Failed: /bad-1.bin" in summary
        assert "Failed: /bad-2.bin" in summary
        assert "Succeeded: /good.bin" not in summary
        assert "… 1 more entries omitted." in summary
        assert format_transfer_summary([], [], None, 2) == "No entries processed."

    def test_remote_plan_skips_parent_and_unsafe_child_entries(self) -> None:
        """
        A user cannot download parent markers or unsafe names returned by a remote listing.

        GIVEN: A remote directory contains a parent marker and a hostile child name
        WHEN: Its recursive plan is expanded
        THEN: Neither entry becomes a local path and the hostile path is reported
        """
        root = FlightControllerLogFile("folder", "/APM/LOGS/folder", 0, is_directory=True)
        parent = FlightControllerLogFile("..", "/APM/LOGS", 0, is_directory=True)
        unsafe = FlightControllerLogFile("bad:name.bin", "/APM/LOGS/folder/bad:name.bin", 4)
        failures: list[str] = []

        directories, files = _remote_download_plan(root, Path("folder"), MagicMock(return_value=[parent, unsafe]), failures)

        assert directories == [Path("folder")]
        assert not files
        assert failures == [unsafe.remote_path]

    def test_remote_plan_rejects_an_unsafe_selected_file(self) -> None:
        """
        A user cannot schedule a directly selected remote file with an unsafe name.

        GIVEN: A selected remote file has a platform-unsafe basename
        WHEN: Its download plan is expanded
        THEN: No local file is scheduled and the remote path is reported
        """
        entry = FlightControllerLogFile("bad:name.bin", "/APM/LOGS/bad:name.bin", 4)
        failures: list[str] = []

        directories, files = _remote_download_plan(entry, Path("bad:name.bin"), MagicMock(), failures)

        assert not directories
        assert not files
        assert failures == [entry.remote_path]

    def test_local_upload_reports_directory_enumeration_failures(self) -> None:
        """
        A user sees an upload planning failure when a selected directory cannot be read.

        GIVEN: A selected local directory becomes inaccessible during planning
        WHEN: Its recursive upload plan is built
        THEN: No children are scheduled and the directory is reported as failed
        """
        entry = LocalFileEntry("folder", Path("folder"), 0, is_directory=True)
        failures: list[str] = []

        with patch(
            "ardupilot_methodic_configurator.frontend_tkinter_file_browser_operations._local_directory_entries",
            side_effect=OSError("permission denied"),
        ):
            directories, files = _local_upload_plan(entry, "/APM/LOGS/folder", failures)

        assert not directories
        assert not files
        assert failures == ["/APM/LOGS/folder"]

    def test_local_upload_reports_an_entry_that_disappears_during_planning(self) -> None:
        """
        A user sees the precise child path when one directory entry disappears.

        GIVEN: Local enumeration reports an error for one child
        WHEN: A recursive upload plan is built
        THEN: The failed child path is retained for the transfer summary
        """
        entry = LocalFileEntry("folder", Path("folder"), 0, is_directory=True)
        failures: list[str] = []

        def enumerate_with_error(_directory: Path, on_entry_error) -> list[LocalFileEntry]:
            on_entry_error(Path("folder") / "vanished.bin")
            return []

        with patch(
            "ardupilot_methodic_configurator.frontend_tkinter_file_browser_operations._local_directory_entries",
            side_effect=enumerate_with_error,
        ):
            directories, files = _local_upload_plan(entry, "/APM/LOGS/folder", failures)

        assert directories == ["/APM/LOGS/folder"]
        assert not files
        assert failures == ["/APM/LOGS/folder/vanished.bin"]

    def test_download_marks_a_directory_failed_when_it_cannot_be_created(self) -> None:
        """
        A user receives a failed-directory result when local directory creation raises.

        GIVEN: A safe planned directory cannot be created by the filesystem
        WHEN: The download worker prepares its destinations
        THEN: The directory is recorded as failed without aborting the batch
        """
        directory = MagicMock()
        directory.is_symlink.return_value = False
        directory.exists.return_value = False
        directory.mkdir.side_effect = OSError("read-only filesystem")

        with patch(
            "ardupilot_methodic_configurator.frontend_tkinter_file_browser_operations._local_target_is_contained",
            return_value=True,
        ):
            attempt = _download_remote_plan_worker(
                RemoteDownloadPlan((directory,), ()), Path("destination"), 0, MagicMock(), MagicMock()
            )

        assert attempt.directories_failed == [str(directory)]
        assert not attempt.directories_succeeded

    def test_containment_check_rejects_unresolvable_paths(self) -> None:
        """
        A user cannot write through a destination whose canonical path cannot be resolved.

        GIVEN: Path resolution raises a filesystem error
        WHEN: Download containment is checked
        THEN: The target is rejected
        """
        local_directory = MagicMock()
        target = MagicMock()
        target.resolve.side_effect = RuntimeError("symlink loop")

        assert not _local_target_is_contained(local_directory, target)

    def test_remote_mutation_workers_convert_callback_exceptions_to_failures(self) -> None:
        """
        A user receives failed results instead of a crashed batch when remote callbacks raise.

        GIVEN: Delete, rename, and directory-creation callbacks raise transport errors
        WHEN: Their independent workers run
        THEN: Every affected path is returned as failed
        """
        entry = FlightControllerLogFile("log.bin", "/APM/LOGS/log.bin", 4)
        failure = MagicMock(side_effect=RuntimeError("link lost"))

        deleted = _delete_remote_entries_worker([entry], MagicMock(), failure)
        renamed = _rename_remote_entry_worker(entry, "/APM/LOGS/new.bin", failure)
        created = _create_remote_directory_worker("/APM/LOGS/new", failure)

        assert deleted == ([], [entry.remote_path])
        assert renamed == ([], [entry.remote_path])
        assert created == ([], ["/APM/LOGS/new"])

    def test_upload_verification_exception_leaves_file_retryable(self) -> None:
        """
        A user can retry an uploaded file when checksum verification raises unexpectedly.

        GIVEN: Upload succeeds but its verification callback raises
        WHEN: The upload worker records the attempt
        THEN: The file remains failed with a false verification result
        """
        remote_path = "/APM/LOGS/log.bin"
        plan = LocalUploadPlan((), ((Path("log.bin"), remote_path, 4),))

        attempt = _upload_local_plan_worker(
            plan,
            4,
            MagicMock(),
            MagicMock(return_value=True),
            MagicMock(),
            verify_remote_file=MagicMock(side_effect=RuntimeError("CRC unavailable")),
        )

        assert attempt.files_failed == [remote_path]
        assert not attempt.files_succeeded
        assert attempt.verification == {remote_path: False}

    def test_download_callback_exceptions_leave_files_retryable(self, tmp_path: Path) -> None:
        """
        A user can retry files when downloading or checksum verification raises.

        GIVEN: One transfer callback and one verification callback raise unexpectedly
        WHEN: The download worker processes each file
        THEN: Both files are recorded as failed without aborting the worker
        """
        first = FlightControllerLogFile("first.bin", "/APM/LOGS/first.bin", 2)
        second = FlightControllerLogFile("second.bin", "/APM/LOGS/second.bin", 2)
        download = MagicMock(side_effect=[RuntimeError("link lost"), True])
        verify = MagicMock(side_effect=RuntimeError("CRC unavailable"))

        attempt = _download_remote_plan_worker(
            RemoteDownloadPlan((), ((first, tmp_path / first.name), (second, tmp_path / second.name))),
            tmp_path,
            4,
            download,
            MagicMock(),
            verify_remote_file=verify,
        )

        assert attempt.files_failed == [first.remote_path, second.remote_path]
        assert attempt.verification == {second.remote_path: False}

    def test_upload_forwards_incremental_file_progress(self) -> None:
        """
        A user sees byte-weighted progress while a file upload is active.

        GIVEN: The backend reports a half-complete file upload
        WHEN: The upload worker forwards progress
        THEN: The batch reports the proportional progress before completion
        """
        progress = MagicMock()

        def upload(_local: str, _remote: str, report_file_progress) -> bool:
            report_file_progress(1, 2)
            return True

        _upload_local_plan_worker(
            LocalUploadPlan((), ((Path("log.bin"), "/APM/LOGS/log.bin", 10),)),
            10,
            MagicMock(),
            upload,
            progress,
        )

        assert progress.call_args_list[0].args == (5, 10)
        assert progress.call_args_list[-1].args == (10, 10)

    def test_remote_directory_deletion_handles_listing_outcomes_independently(self) -> None:
        """
        A user receives precise results when selected directories cannot all be inspected.

        GIVEN: One listing raises, one directory is non-empty, and one is empty
        WHEN: The delete worker processes the batch
        THEN: Only the confirmed empty directory is deleted successfully
        """
        unreadable = FlightControllerLogFile("unreadable", "/unreadable", 0, is_directory=True)
        populated = FlightControllerLogFile("populated", "/populated", 0, is_directory=True)
        empty = FlightControllerLogFile("empty", "/empty", 0, is_directory=True)
        child = FlightControllerLogFile("child.bin", "/populated/child.bin", 1)
        listings = MagicMock(side_effect=[RuntimeError("link lost"), [child], []])
        delete = MagicMock(return_value=True)

        succeeded, failed = _delete_remote_entries_worker([unreadable, populated, empty], listings, delete)

        assert succeeded == [empty.remote_path]
        assert failed == [unreadable.remote_path, populated.remote_path]
        delete.assert_called_once_with(empty.remote_path, True)  # noqa: FBT003
