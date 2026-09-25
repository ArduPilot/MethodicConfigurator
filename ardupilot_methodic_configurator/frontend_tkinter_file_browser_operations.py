"""
Tk-independent planning and execution for the flight-controller file browser.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>
SPDX-License-Identifier: GPL-3.0-or-later
"""

from __future__ import annotations

import posixpath
import sys
from collections.abc import Callable, Sequence  # noqa: TC003
from dataclasses import dataclass, field
from pathlib import Path  # noqa: TC003

from ardupilot_methodic_configurator.backend_flightcontroller_files import (
    FlightControllerLogFile,
    LastLogDownloadResult,
    is_safe_local_entry_name,
)


@dataclass(frozen=True)
class LocalFileEntry:
    """A local file-system entry displayed in the local panel."""

    name: str
    path: Path
    size_bytes: int
    is_directory: bool = False
    modified_at: float | None = None


def _local_directory_entries(
    directory: Path,
    on_entry_error: Callable[[Path], None] | None = None,
) -> list[LocalFileEntry]:
    """Return safe, sorted entries from one local directory."""
    children = sorted(directory.iterdir(), key=lambda path: path.name.casefold())
    entries: list[LocalFileEntry] = []
    for child in children:
        if child.is_symlink():
            continue
        try:
            is_directory = child.is_dir()
            stat = child.stat()
        except OSError:
            if on_entry_error is not None:
                on_entry_error(child)
            continue
        entries.append(LocalFileEntry(child.name, child, 0 if is_directory else stat.st_size, is_directory, stat.st_mtime))
    return entries


@dataclass(frozen=True)
class RemoteDownloadPlan:
    """Preflight plan for a recursive remote download."""

    directories: tuple[Path, ...]
    files: tuple[tuple[FlightControllerLogFile, Path], ...]
    failed: tuple[str, ...] = ()


@dataclass(frozen=True)
class RemoteDownloadPreflight:
    """Remote download plan plus local filesystem conflict results."""

    plan: RemoteDownloadPlan
    duplicate_targets: tuple[Path, ...]
    existing_conflicts: tuple[Path, ...]


@dataclass(frozen=True)
class LocalUploadPlan:
    """Preflight plan for a recursive local upload."""

    directories: tuple[str, ...]
    files: tuple[tuple[Path, str, int], ...]
    failed: tuple[str, ...] = ()


@dataclass
class TransferBatchResults:
    """Accumulate transfer results across one optional retry."""

    succeeded: list[str] = field(default_factory=list)
    failed: list[str] = field(default_factory=list)
    verification: dict[str, bool | None] = field(default_factory=dict)

    def prepare(self, paths: Sequence[str]) -> None:
        """Discard verification from a prior attempt for files being retried."""
        for path in paths:
            self.verification.pop(path, None)

    def record(self, succeeded: Sequence[str], failed: Sequence[str]) -> None:
        """Keep successful paths once and remove failures recovered by a retry."""
        self.succeeded = list(dict.fromkeys([*self.succeeded, *succeeded]))
        self.failed = [path for path in dict.fromkeys([*self.failed, *failed]) if path not in self.succeeded]


def _retry_remote_download_plan(plan: RemoteDownloadPlan, failed: Sequence[str]) -> RemoteDownloadPlan:
    """Retain only failed file transfers; re-create their directories if needed."""
    failed_paths = set(failed)
    return RemoteDownloadPlan(plan.directories, tuple(item for item in plan.files if item[0].remote_path in failed_paths))


def _retry_local_upload_plan(plan: LocalUploadPlan, failed: Sequence[str]) -> LocalUploadPlan:
    """Retain only failed file transfers, never earlier successful uploads."""
    failed_paths = set(failed)
    return LocalUploadPlan(plan.directories, tuple(item for item in plan.files if item[1] in failed_paths))


def _safe_remote_entry_name(name: str) -> bool:
    """Return whether a remote listing name is safe as one path component."""
    return is_safe_local_entry_name(name)


def _remote_download_plan(
    entry: FlightControllerLogFile,
    local_target: Path,
    get_remote_files: Callable[..., list[FlightControllerLogFile] | None],
    failures: list[str] | None = None,
) -> tuple[list[Path], list[tuple[FlightControllerLogFile, Path]]]:
    """Recursively expand one remote entry without retaining a Tk window."""
    if not entry.is_directory:
        if not _safe_remote_entry_name(entry.name):
            if failures is not None:
                failures.append(entry.remote_path)
            return [], []
        return [], [(entry, local_target)]

    directories = [local_target]
    files: list[tuple[FlightControllerLogFile, Path]] = []
    try:
        children = get_remote_files(entry.remote_path)
    except Exception:  # pylint: disable=broad-exception-caught
        if failures is not None:
            failures.append(entry.remote_path)
        return [], []
    if children is None:
        if failures is not None:
            failures.append(entry.remote_path)
        return [], []
    for child in children:
        if child.name == "..":
            continue
        if not _safe_remote_entry_name(child.name):
            if failures is not None:
                failures.append(child.remote_path)
            continue
        child_dirs, child_files = _remote_download_plan(
            child,
            local_target / child.name,
            get_remote_files,
            failures,
        )
        directories.extend(child_dirs)
        files.extend(child_files)
    return directories, files


def _build_remote_download_plan(
    selected: Sequence[FlightControllerLogFile],
    local_directory: Path,
    get_remote_files: Callable[..., list[FlightControllerLogFile] | None],
) -> RemoteDownloadPlan:
    """Build a recursive remote download plan without touching Tk widgets."""
    directories: list[Path] = []
    files: list[tuple[FlightControllerLogFile, Path]] = []
    failed: list[str] = []
    for entry in selected:
        if not _safe_remote_entry_name(entry.name):
            failed.append(entry.remote_path)
            continue
        child_dirs, child_files = _remote_download_plan(
            entry,
            local_directory / entry.name,
            get_remote_files,
            failed,
        )
        directories.extend(child_dirs)
        files.extend(child_files)
    return RemoteDownloadPlan(tuple(directories), tuple(files), tuple(failed))


def _local_path_key(path: Path) -> str:
    """Return a platform-aware key for detecting local target collisions."""
    return str(path.absolute()).casefold() if sys.platform == "win32" else str(path.absolute())


def _local_path_is_ancestor(parent: Path, child: Path) -> bool:
    """Return whether one planned local path is a strict ancestor of another."""
    parent_key = _local_path_key(parent).rstrip("\\/")
    child_key = _local_path_key(child)
    return child_key.startswith((f"{parent_key}\\", f"{parent_key}/"))


def _local_target_conflicts(plan: RemoteDownloadPlan) -> tuple[list[Path], list[Path]]:
    """Return duplicate planned targets and existing incompatible targets."""
    planned: dict[str, tuple[Path, bool]] = {}
    duplicate_targets: list[Path] = []
    for target, is_directory in (
        *((target, True) for target in plan.directories),
        *((target, False) for _entry, target in plan.files),
    ):
        key = _local_path_key(target)
        if key in planned:
            duplicate_targets.append(target)
        else:
            planned[key] = target, is_directory

    file_targets = tuple(target for target, is_directory in planned.values() if not is_directory)
    for file_target in file_targets:
        for other_target, _is_directory in planned.values():
            if _local_path_is_ancestor(file_target, other_target):
                duplicate_targets.append(other_target)

    existing_conflicts: list[Path] = []
    for target, is_directory in planned.values():
        exists = target.exists() or target.is_symlink()
        if exists and (target.is_symlink() or not is_directory or not target.is_dir()):
            existing_conflicts.append(target)
    return duplicate_targets, existing_conflicts


def _prepare_remote_download(
    selected: Sequence[FlightControllerLogFile],
    local_directory: Path,
    get_remote_files: Callable[..., list[FlightControllerLogFile] | None],
) -> RemoteDownloadPreflight:
    """Build a remote plan and inspect local targets without retaining a Tk window."""
    plan = _build_remote_download_plan(selected, local_directory, get_remote_files)
    duplicate_targets, existing_conflicts = _local_target_conflicts(plan)
    return RemoteDownloadPreflight(plan, tuple(duplicate_targets), tuple(existing_conflicts))


def _local_target_is_contained(local_directory: Path, target: Path) -> bool:
    """Return whether a target remains below the chosen directory after symlink resolution."""
    try:
        target.resolve(strict=False).relative_to(local_directory.resolve(strict=False))
    except (OSError, RuntimeError, ValueError):
        return False
    return True


# Transfer callbacks stay explicit so the worker remains independent of Tk and easy to inject in tests.
def _download_remote_plan_worker(  # pylint: disable=too-many-arguments,too-many-locals
    plan: RemoteDownloadPlan,
    local_directory: Path,
    total: int,
    download_remote_file: Callable[..., bool],
    report_progress: Callable[[int, int], None],
    *,
    verify_remote_file: Callable[[str, str], bool | None] | None = None,
    verification_results: dict[str, bool | None] | None = None,
) -> tuple[list[str], list[str]]:
    """Create local directories and transfer files without retaining a Tk window."""
    completed = 0
    succeeded: list[str] = []
    failed = list(plan.failed)
    for directory in plan.directories:
        try:
            if not _local_target_is_contained(local_directory, directory) or (
                directory.is_symlink() or (directory.exists() and not directory.is_dir())
            ):
                failed.append(str(directory))
                continue
            directory.mkdir(parents=True, exist_ok=True)
        except OSError:
            failed.append(str(directory))
        else:
            succeeded.append(str(directory))

    for entry, target in plan.files:
        units = max(entry.size_bytes, 1)
        if not _local_target_is_contained(local_directory, target) or (
            target.is_symlink() or (target.parent.exists() and not target.parent.is_dir())
        ):
            failed.append(entry.remote_path)
            completed += units
            report_progress(completed, total)
            continue

        def report_file_progress(
            current: int,
            maximum: int,
            offset: int = completed,
            size: int = units,
        ) -> None:
            # Keep the progress window open until optional CRC verification finishes.
            limit = total - 1 if verify_remote_file is not None else total
            progress = min(limit, int(offset + size * (current / maximum if maximum else 0.0)))
            report_progress(progress, total)

        try:
            success = download_remote_file(entry.remote_path, str(target), report_file_progress)
        except Exception:  # pylint: disable=broad-exception-caught
            success = False
        if success and verify_remote_file is not None:
            try:
                verification = verify_remote_file(entry.remote_path, str(target))
            except Exception:  # pylint: disable=broad-exception-caught
                verification = False
            if verification_results is not None:
                verification_results[entry.remote_path] = verification
            success = verification is not False
        if success:
            succeeded.append(entry.remote_path)
        else:
            failed.append(entry.remote_path)
        completed += units
        report_progress(completed, total)
    return succeeded, failed


def _local_upload_plan(
    entry: LocalFileEntry,
    remote_target: str,
    failures: list[str] | None = None,
) -> tuple[list[str], list[tuple[Path, str, int]]]:
    """Recursively expand one local entry into remote directories and files."""
    if not is_safe_local_entry_name(entry.name):
        if failures is not None:
            failures.append(remote_target)
        return [], []
    if not entry.is_directory:
        return [], [(entry.path, remote_target, entry.size_bytes)]
    directories = [remote_target]
    files: list[tuple[Path, str, int]] = []

    def record_entry_error(child: Path) -> None:
        if failures is not None:
            failures.append(posixpath.join(remote_target.rstrip("/"), child.name))

    try:
        children = _local_directory_entries(entry.path, record_entry_error)
    except OSError:
        if failures is not None:
            failures.append(remote_target)
        return [], []
    for child_entry in children:
        child_dirs, child_files = _local_upload_plan(
            child_entry,
            posixpath.join(remote_target.rstrip("/"), child_entry.name),
            failures,
        )
        directories.extend(child_dirs)
        files.extend(child_files)
    return directories, files


def _build_local_upload_plan(
    selected: Sequence[LocalFileEntry],
    remote_directory: str,
) -> LocalUploadPlan:
    """Build a recursive local upload plan without touching Tk widgets."""
    directories: list[str] = []
    files: list[tuple[Path, str, int]] = []
    failed: list[str] = []
    for entry in selected:
        target = posixpath.join(remote_directory, entry.name)
        child_dirs, child_files = _local_upload_plan(entry, target, failed)
        directories.extend(child_dirs)
        files.extend(child_files)
    return LocalUploadPlan(tuple(directories), tuple(files), tuple(failed))


def _call_remote_bool(callback: Callable[..., bool], *args: object) -> bool:
    """Call a remote-operation callback without aborting a batch on one exception."""
    try:
        return bool(callback(*args))
    except Exception:  # pylint: disable=broad-exception-caught
        return False


# Transfer callbacks stay explicit so the worker remains independent of Tk and easy to inject in tests.
def _upload_local_plan_worker(  # pylint: disable=too-many-arguments,too-many-locals
    plan: LocalUploadPlan,
    total: int,
    make_remote_directory: Callable[..., bool],
    upload_file_to_fc: Callable[..., bool],
    report_progress: Callable[[int, int], None],
    *,
    verify_remote_file: Callable[[str, str], bool | None] | None = None,
    verification_results: dict[str, bool | None] | None = None,
) -> tuple[list[str], list[str]]:
    """Create remote directories and upload files without retaining a Tk window."""
    completed = 0
    succeeded: list[str] = []
    failed = list(plan.failed)
    failed_directories: set[str] = set()

    def below_failed_directory(remote_path: str) -> bool:
        return any(
            remote_path == directory or remote_path.startswith(f"{directory.rstrip('/')}/") for directory in failed_directories
        )

    for directory in plan.directories:
        if below_failed_directory(directory):
            failed.append(directory)
            failed_directories.add(directory)
        elif _call_remote_bool(make_remote_directory, directory):
            succeeded.append(directory)
        else:
            failed.append(directory)
            failed_directories.add(directory)
    for local_path, remote_path, size in plan.files:
        units = max(size, 1)

        def report_file_progress(
            current: int,
            maximum: int,
            offset: int = completed,
            file_size: int = units,
        ) -> None:
            limit = total - 1 if verify_remote_file is not None else total
            progress = min(limit, int(offset + file_size * (current / maximum if maximum else 0.0)))
            report_progress(progress, total)

        success = not below_failed_directory(remote_path) and _call_remote_bool(
            upload_file_to_fc, str(local_path), remote_path, report_file_progress
        )
        if success and verify_remote_file is not None:
            try:
                verification = verify_remote_file(remote_path, str(local_path))
            except Exception:  # pylint: disable=broad-exception-caught
                verification = False
            if verification_results is not None:
                verification_results[remote_path] = verification
            success = verification is not False
        if success:
            succeeded.append(remote_path)
        else:
            failed.append(remote_path)
        completed += units
        report_progress(completed, total)
    return succeeded, failed


def _delete_remote_entries_worker(
    selected: Sequence[FlightControllerLogFile],
    get_remote_files: Callable[..., list[FlightControllerLogFile] | None],
    delete_remote_path: Callable[..., bool],
) -> tuple[list[str], list[str]]:
    """Delete selected remote files and empty directories without retaining a Tk window."""
    succeeded: list[str] = []
    failed: list[str] = []
    for entry in selected:
        if entry.is_directory:
            try:
                listing = get_remote_files(entry.remote_path)
            except Exception:  # pylint: disable=broad-exception-caught
                failed.append(entry.remote_path)
                continue
            if listing is None or any(child.name != ".." for child in listing):
                failed.append(entry.remote_path)
                continue
        if _call_remote_bool(delete_remote_path, entry.remote_path, entry.is_directory):
            succeeded.append(entry.remote_path)
        else:
            failed.append(entry.remote_path)
    return succeeded, failed


def _rename_remote_entry_worker(
    entry: FlightControllerLogFile,
    new_path: str,
    rename_remote_path: Callable[..., bool],
) -> tuple[list[str], list[str]]:
    """Rename one remote entry without retaining a Tk window."""
    success = _call_remote_bool(rename_remote_path, entry.remote_path, new_path)
    return ([entry.remote_path], []) if success else ([], [entry.remote_path])


def _create_remote_directory_worker(
    new_path: str,
    make_remote_directory: Callable[..., bool],
) -> tuple[list[str], list[str]]:
    """Create one remote directory without retaining a Tk window."""
    success = _call_remote_bool(make_remote_directory, new_path)
    return ([new_path], []) if success else ([], [new_path])


def _download_last_flight_log_worker(
    filename: str,
    download_last_flight_log: Callable[..., LastLogDownloadResult],
    report_progress: Callable[[int, int], None],
) -> LastLogDownloadResult:
    """Download the last flight log without retaining a Tk window."""
    try:
        return download_last_flight_log(filename, report_progress)
    except Exception:  # pylint: disable=broad-exception-caught
        return LastLogDownloadResult.FAILED
