"""Coordinate configured file uploads without depending on the editor UI."""

from collections.abc import Callable, Collection, Sequence
from dataclasses import dataclass
from enum import Enum, auto

from ardupilot_methodic_configurator.backend_flightcontroller_protocols import FileUploadCheckStatus, FileUploadResult

ProgressCallback = Callable[[int, int], None]
ProgressCallbackFactory = Callable[[], ProgressCallback | None]
FileUploadCheck = Callable[[str, str], FileUploadCheckStatus]
FileUpload = Callable[[str, str, ProgressCallback | None], FileUploadResult]


class FileUploadDisposition(Enum):
    """Per-file outcome of coordinating a configured upload."""

    AWAITING_DOWNLOAD = auto()
    LOCAL_FILE_MISSING = auto()
    EMPTY_LOCAL_FILE = auto()
    NO_CONNECTION = auto()
    ALREADY_CURRENT = auto()
    VERIFICATION_FAILED = auto()
    USER_DECLINED = auto()
    UPLOADED = auto()
    UPLOAD_FAILED = auto()


_UPLOAD_DISPOSITION_BY_RESULT = {
    FileUploadResult.ALREADY_CURRENT: FileUploadDisposition.ALREADY_CURRENT,
    FileUploadResult.VERIFICATION_FAILED: FileUploadDisposition.VERIFICATION_FAILED,
    FileUploadResult.LOCAL_FILE_MISSING: FileUploadDisposition.LOCAL_FILE_MISSING,
    FileUploadResult.EMPTY_LOCAL_FILE: FileUploadDisposition.EMPTY_LOCAL_FILE,
    FileUploadResult.UPLOADED: FileUploadDisposition.UPLOADED,
    FileUploadResult.UPLOAD_FAILED: FileUploadDisposition.UPLOAD_FAILED,
}


@dataclass(frozen=True)
class FileUploadOutcome:
    """Outcome associated with one configured local-to-remote file pair."""

    local_filename: str
    remote_filename: str
    disposition: FileUploadDisposition


class FileUploadWorkflow:
    """Apply upload policy using injected filesystem, transport, and interaction callbacks."""

    def __init__(
        self,
        file_size: Callable[[str], int | None],
        is_connected: Callable[[], bool],
        check_upload: FileUploadCheck,
        upload_if_needed: FileUpload,
    ) -> None:
        self._file_size = file_size
        self._is_connected = is_connected
        self._check_upload = check_upload
        self._upload_if_needed = upload_if_needed

    def upload_files(
        self,
        files: Sequence[tuple[str, str]],
        download_filenames: Collection[str],
        confirm_upload: Callable[[str, str], bool],
        get_progress_callback: ProgressCallbackFactory,
    ) -> list[FileUploadOutcome]:
        """Return an outcome for each file processed, continuing after individual failures."""
        outcomes: list[FileUploadOutcome] = []
        for local_filename, remote_filename in files:
            outcome = self._upload_file(
                local_filename,
                remote_filename,
                local_filename in download_filenames,
                confirm_upload,
                get_progress_callback,
            )
            outcomes.append(outcome)
            if outcome.disposition is FileUploadDisposition.NO_CONNECTION:
                break
        return outcomes

    def _upload_file(
        self,
        local_filename: str,
        remote_filename: str,
        is_download_configured: bool,
        confirm_upload: Callable[[str, str], bool],
        get_progress_callback: ProgressCallbackFactory,
    ) -> FileUploadOutcome:
        local_file_size = self._file_size(local_filename)
        local_disposition = self._get_local_file_disposition(local_file_size, is_download_configured)
        if local_disposition is not None:
            return FileUploadOutcome(local_filename, remote_filename, local_disposition)
        if not self._is_connected():
            return FileUploadOutcome(local_filename, remote_filename, FileUploadDisposition.NO_CONNECTION)

        check_status = self._check_upload(remote_filename, local_filename)
        if check_status is not FileUploadCheckStatus.NEEDS_UPLOAD:
            disposition = (
                FileUploadDisposition.ALREADY_CURRENT
                if check_status is FileUploadCheckStatus.ALREADY_CURRENT
                else FileUploadDisposition.VERIFICATION_FAILED
            )
            return FileUploadOutcome(local_filename, remote_filename, disposition)
        if not confirm_upload(local_filename, remote_filename):
            return FileUploadOutcome(local_filename, remote_filename, FileUploadDisposition.USER_DECLINED)

        upload_result = self._upload_with_lazy_progress(local_filename, remote_filename, get_progress_callback)
        return FileUploadOutcome(local_filename, remote_filename, _UPLOAD_DISPOSITION_BY_RESULT[upload_result])

    @staticmethod
    def _get_local_file_disposition(
        local_file_size: int | None,
        is_download_configured: bool,
    ) -> FileUploadDisposition | None:
        if local_file_size is None:
            return (
                FileUploadDisposition.AWAITING_DOWNLOAD if is_download_configured else FileUploadDisposition.LOCAL_FILE_MISSING
            )
        if local_file_size == 0:
            return FileUploadDisposition.EMPTY_LOCAL_FILE
        return None

    def _upload_with_lazy_progress(
        self,
        local_filename: str,
        remote_filename: str,
        get_progress_callback: ProgressCallbackFactory,
    ) -> FileUploadResult:
        """Create the progress callback only after the transport reports progress."""
        progress_callback: ProgressCallback | None = None
        progress_callback_created = False

        def forward_upload_progress(current: int, total: int) -> None:
            nonlocal progress_callback, progress_callback_created
            if not progress_callback_created:
                progress_callback = get_progress_callback()
                progress_callback_created = True
            if progress_callback is not None:
                progress_callback(current, total)

        return self._upload_if_needed(local_filename, remote_filename, forward_upload_progress)
