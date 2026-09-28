#!/usr/bin/env python3

"""
Tests for the editor-independent file upload workflow.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2026 Amilcar Lucas

SPDX-License-Identifier: GPL-3.0-or-later
"""

from collections.abc import Callable
from unittest.mock import Mock

import pytest

from ardupilot_methodic_configurator.backend_flightcontroller_protocols import FileUploadCheckStatus, FileUploadResult
from ardupilot_methodic_configurator.data_model_file_upload import (
    FileUploadDisposition,
    FileUploadWorkflow,
)


def _create_workflow(
    *,
    file_size: int | None = 12,
    connected: bool = True,
    check_status: FileUploadCheckStatus = FileUploadCheckStatus.NEEDS_UPLOAD,
    upload_result: FileUploadResult = FileUploadResult.UPLOADED,
) -> tuple[FileUploadWorkflow, Mock, Mock, Mock, Mock, Mock]:
    size = Mock(return_value=file_size)
    is_connected = Mock(return_value=connected)
    check_upload = Mock(return_value=check_status)
    upload = Mock(return_value=upload_result)
    confirm = Mock(return_value=True)
    progress_factory = Mock(return_value=Mock())
    workflow = FileUploadWorkflow(size, is_connected, check_upload, upload)
    return workflow, size, check_upload, upload, confirm, progress_factory


@pytest.mark.parametrize(
    ("file_size", "download_filenames", "expected"),
    [
        (None, {"script.lua"}, FileUploadDisposition.AWAITING_DOWNLOAD),
        (None, set(), FileUploadDisposition.LOCAL_FILE_MISSING),
        (0, set(), FileUploadDisposition.EMPTY_LOCAL_FILE),
    ],
)
def test_local_file_states_are_reported_without_remote_operations(
    file_size: int | None,
    download_filenames: set[str],
    expected: FileUploadDisposition,
) -> None:
    """Missing, pending-download, and empty files stop before preflight or upload."""
    workflow, _size, check_upload, upload, confirm, progress_factory = _create_workflow(file_size=file_size)

    outcomes = workflow.upload_files(
        [("script.lua", "/APM/Scripts/script.lua")],
        download_filenames,
        confirm,
        progress_factory,
    )

    assert [outcome.disposition for outcome in outcomes] == [expected]
    check_upload.assert_not_called()
    upload.assert_not_called()
    confirm.assert_not_called()
    progress_factory.assert_not_called()


def test_remote_current_file_skips_confirmation_and_upload() -> None:
    """An already-current remote file completes without prompting or uploading."""
    workflow, _size, check_upload, upload, confirm, progress_factory = _create_workflow(
        check_status=FileUploadCheckStatus.ALREADY_CURRENT
    )

    outcomes = workflow.upload_files([("script.lua", "/APM/Scripts/script.lua")], set(), confirm, progress_factory)

    assert [outcome.disposition for outcome in outcomes] == [FileUploadDisposition.ALREADY_CURRENT]
    check_upload.assert_called_once_with("/APM/Scripts/script.lua", "script.lua")
    upload.assert_not_called()
    confirm.assert_not_called()
    progress_factory.assert_not_called()


def test_remote_verification_failure_is_a_per_file_outcome() -> None:
    """A remote check that cannot be verified returns without prompting or uploading."""
    workflow, _size, check_upload, upload, confirm, progress_factory = _create_workflow(
        check_status=FileUploadCheckStatus.VERIFICATION_FAILED
    )

    outcomes = workflow.upload_files([("script.lua", "/APM/Scripts/script.lua")], set(), confirm, progress_factory)

    assert [outcome.disposition for outcome in outcomes] == [FileUploadDisposition.VERIFICATION_FAILED]
    check_upload.assert_called_once()
    confirm.assert_not_called()
    upload.assert_not_called()


def test_no_connection_stops_before_remote_preflight() -> None:
    """The workflow reports a missing connection without starting remote operations."""
    workflow, _size, check_upload, upload, confirm, progress_factory = _create_workflow(connected=False)

    outcomes = workflow.upload_files([("script.lua", "/APM/Scripts/script.lua")], set(), confirm, progress_factory)

    assert [outcome.disposition for outcome in outcomes] == [FileUploadDisposition.NO_CONNECTION]
    check_upload.assert_not_called()
    confirm.assert_not_called()
    upload.assert_not_called()


def test_declined_upload_does_not_start_transfer() -> None:
    """A declined confirmation is returned as a per-file outcome."""
    workflow, _size, _check_upload, upload, confirm, progress_factory = _create_workflow()
    confirm.return_value = False

    outcomes = workflow.upload_files([("script.lua", "/APM/Scripts/script.lua")], set(), confirm, progress_factory)

    assert [outcome.disposition for outcome in outcomes] == [FileUploadDisposition.USER_DECLINED]
    confirm.assert_called_once_with("script.lua", "/APM/Scripts/script.lua")
    upload.assert_not_called()
    progress_factory.assert_not_called()


def test_upload_failure_is_returned_to_the_presenter() -> None:
    """A transport failure is returned without invoking UI-specific error handling."""
    workflow, _size, _check_upload, upload, _confirm, progress_factory = _create_workflow(
        upload_result=FileUploadResult.UPLOAD_FAILED
    )

    outcomes = workflow.upload_files(
        [("script.lua", "/APM/Scripts/script.lua")], set(), Mock(return_value=True), progress_factory
    )

    assert [outcome.disposition for outcome in outcomes] == [FileUploadDisposition.UPLOAD_FAILED]
    upload.assert_called_once()


def test_execution_recheck_can_skip_a_file_that_became_current() -> None:
    """The backend's execution-time recheck wins if the remote file changed after preflight."""
    workflow, _size, _check_upload, upload, _confirm, progress_factory = _create_workflow(
        upload_result=FileUploadResult.ALREADY_CURRENT
    )

    outcomes = workflow.upload_files(
        [("script.lua", "/APM/Scripts/script.lua")], set(), Mock(return_value=True), progress_factory
    )

    assert [outcome.disposition for outcome in outcomes] == [FileUploadDisposition.ALREADY_CURRENT]
    upload.assert_called_once()
    assert upload.call_args.args[:2] == ("script.lua", "/APM/Scripts/script.lua")
    progress_factory.assert_not_called()


def test_progress_callback_is_created_only_when_upload_reports_progress() -> None:
    """The workflow lazily creates and forwards a progress callback on first progress."""
    workflow, _size, _check_upload, upload, _confirm, progress_factory = _create_workflow()
    progress = progress_factory.return_value

    def upload_with_progress(_local_filename: str, _remote_filename: str, callback) -> FileUploadResult:
        callback(25, 100)
        callback(100, 100)
        return FileUploadResult.UPLOADED

    upload.side_effect = upload_with_progress
    outcomes = workflow.upload_files(
        [("script.lua", "/APM/Scripts/script.lua")], set(), Mock(return_value=True), progress_factory
    )

    assert [outcome.disposition for outcome in outcomes] == [FileUploadDisposition.UPLOADED]
    progress_factory.assert_called_once_with()
    assert progress.call_args_list == [((25, 100),), ((100, 100),)]


def test_progress_factory_is_not_reentered_by_a_nested_progress_notification() -> None:
    """
    Creating the progress UI must not recursively create another progress UI.

    GIVEN: The progress factory dispatches another notification before returning
    WHEN: A file upload reports its first progress notification
    THEN: Exactly one callback is created and subsequent progress reaches it
    """
    workflow, _size, _check, upload, confirm, progress_factory = _create_workflow()
    callback = Mock()

    def create_progress() -> Mock:
        if progress_factory.call_count == 1:
            upload.call_args.args[2](30, 100)
        return callback

    def report_progress(_local: str, _remote: str, forward: Callable[[int, int], None]) -> FileUploadResult:
        forward(20, 100)
        forward(100, 100)
        return FileUploadResult.UPLOADED

    progress_factory.side_effect = create_progress
    upload.side_effect = report_progress

    outcomes = workflow.upload_files([("a.lua", "/APM/Scripts/a.lua")], set(), confirm, progress_factory)

    assert outcomes[0].disposition is FileUploadDisposition.UPLOADED
    progress_factory.assert_called_once_with()
    assert callback.call_args_list == [((20, 100),), ((100, 100),)]


@pytest.mark.parametrize("callback_stage", ["confirmation", "progress"])
def test_nested_upload_batch_is_rejected_without_disturbing_outer_batch(callback_stage: str) -> None:
    """
    Nested UI callbacks cannot start an unconfirmed replacement batch.

    GIVEN: A confirmation or progress callback dispatches another upload request
    WHEN: The outer batch is still active
    THEN: Re-entry is rejected before any nested preflight or transfer
    AND: The outer batch and a subsequent batch complete normally
    """
    workflow, _size, check, upload, confirm, progress_factory = _create_workflow()

    def attempt_nested_upload(*_args: object) -> bool:
        with pytest.raises(RuntimeError, match="already in progress"):
            workflow.upload_files([("nested.lua", "/APM/Scripts/nested.lua")], set(), Mock(), Mock())
        return True

    def report_progress(_local: str, _remote: str, callback: Callable[[int, int], None]) -> FileUploadResult:
        callback(50, 100)
        return FileUploadResult.UPLOADED

    if callback_stage == "confirmation":
        confirm.side_effect = attempt_nested_upload
    else:
        progress_factory.return_value = attempt_nested_upload
        upload.side_effect = report_progress

    outcomes = workflow.upload_files([("outer.lua", "/APM/Scripts/outer.lua")], set(), confirm, progress_factory)

    assert outcomes[0].disposition is FileUploadDisposition.UPLOADED
    check.assert_called_once_with("/APM/Scripts/outer.lua", "outer.lua")
    upload.assert_called_once()
    assert workflow.upload_files([("later.lua", "/APM/Scripts/later.lua")], set(), Mock(return_value=True), Mock())


@pytest.mark.parametrize(
    ("provider_stage", "error_type", "expected"),
    [
        ("size", OSError, FileUploadDisposition.LOCAL_FILE_MISSING),
        ("check", OSError, FileUploadDisposition.VERIFICATION_FAILED),
        ("check", RuntimeError, FileUploadDisposition.VERIFICATION_FAILED),
        ("upload", OSError, FileUploadDisposition.UPLOAD_FAILED),
        ("upload", RuntimeError, FileUploadDisposition.UPLOAD_FAILED),
    ],
)
def test_provider_exception_does_not_skip_later_uploads(
    provider_stage: str, error_type: type[Exception], expected: FileUploadDisposition
) -> None:
    """
    Recoverable provider errors are isolated to the affected file.

    GIVEN: The first file's filesystem or transport provider raises
    WHEN: A batch contains another valid file
    THEN: The first failure is reported and the second file is uploaded
    """
    workflow, size, check, upload, confirm, progress_factory = _create_workflow()
    provider, success = {
        "size": (size, 12),
        "check": (check, FileUploadCheckStatus.NEEDS_UPLOAD),
        "upload": (upload, FileUploadResult.UPLOADED),
    }[provider_stage]
    provider.side_effect = [error_type("file operation failed"), success]

    outcomes = workflow.upload_files(
        [("first.lua", "/APM/Scripts/first.lua"), ("second.lua", "/APM/Scripts/second.lua")],
        set(),
        confirm,
        progress_factory,
    )

    assert [outcome.disposition for outcome in outcomes] == [expected, FileUploadDisposition.UPLOADED]
    assert upload.call_args.args[:2] == ("second.lua", "/APM/Scripts/second.lua")


def test_confirmation_exception_releases_batch_for_a_later_request() -> None:
    """
    Unexpected UI errors must not leave the workflow permanently busy.

    GIVEN: A confirmation callback raises before the transfer starts
    WHEN: Another batch is requested after the exception
    THEN: The exception propagates and the later batch completes normally
    """
    workflow, _size, _check, upload, confirm, progress_factory = _create_workflow()
    confirm.side_effect = ValueError("dialog failed")

    with pytest.raises(ValueError, match="dialog failed"):
        workflow.upload_files([("a.lua", "/APM/Scripts/a.lua")], set(), confirm, progress_factory)
    upload.assert_not_called()

    confirm.side_effect = None
    outcomes = workflow.upload_files([("a.lua", "/APM/Scripts/a.lua")], set(), confirm, progress_factory)

    assert outcomes[0].disposition is FileUploadDisposition.UPLOADED
