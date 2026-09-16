# MAVFTP File Browser Architecture

**Status:** Implemented
**Entry point:** Parameter Editor → **Download .bin log file(s)**

> **User-facing documentation:** [USERMANUAL_MAVFTP.md](USERMANUAL_MAVFTP.md)
> is the authoritative description of the browser's interface, workflows,
> shortcuts, confirmations, and troubleshooting. This document describes the
> implementation boundaries and technical contracts.

## Scope

`DownloadBinLogsWindow` is a modal two-panel browser for MAVFTP files on a
connected flight controller and files on the local PC. It is implemented in
`ardupilot_methodic_configurator/frontend_tkinter_download_bin_logs.py`.

The window does not access MAVFTP directly. It coordinates user-interface
state, background work, and local filesystem operations while the data model
and backend own flight-controller communication.

## Layered design

```text
ParameterEditorWindow
        |
        v
DownloadBinLogsWindow(BaseWindow)
        |  DownloadBinLogsUiServices
        v
ParameterEditor
        v
FlightController
        v
FlightControllerFiles
        v
MAVFTP
```

### Frontend

`DownloadBinLogsWindow` owns:

- modal lifecycle and widget state;
- Treeview population, stable item IDs, selection, and sorting;
- local directory enumeration;
- recursive download/upload planning;
- dialogs, confirmations, summaries, and progress display;
- dispatch of blocking remote work to background threads; and
- post-refresh selection of newly created directories.

`DownloadBinLogsUiServices` injects file/directory/name dialogs, messages,
confirmations, and the standard `ProgressWindow` factory. This permits
unit-level testing without a live Tk desktop.

The standalone module creates its own `FlightController`, `LocalFilesystem`,
and `ParameterEditor`; it connects the controller before opening the window.

### Model and backend

`ParameterEditor` exposes the frontend-facing operations and delegates to
`FlightController` and `FlightControllerFiles`. The relevant interface is:

```python
get_bin_log_files(remote_directory)
get_remote_files(remote_directory)
upload_file_to_fc(local_filename, remote_filename, progress_callback)
download_remote_file(remote_path, local_filename, progress_callback)
make_remote_directory(remote_directory)
delete_remote_path(remote_path, is_directory=False)
rename_remote_path(remote_path, new_remote_path)
download_selected_bin_logs_workflow(...)
download_last_flight_log_workflow(...)
```

`FlightControllerFiles` serializes MAVFTP access with its `_mavftp_lock`.
It implements remote listing, file transfer, directory creation, deletion,
rename, and the existing LASTLOG/fallback workflow.

## Data contracts

Remote entries are represented by `FlightControllerLogFile`:

```python
@dataclass(frozen=True)
class FlightControllerLogFile:
    name: str
    remote_path: str
    size_bytes: int
    is_directory: bool = False
    modified_at: int | None = None
```

The local panel uses `LocalFileEntry`, which additionally retains a local
`Path` and a local modification timestamp.

MAVFTP `DirectoryEntry` values can optionally include a Unix modification
timestamp. `backend_mavftp.py` probes timestamp-capable directory listings and
falls back to the baseline listing request when firmware does not support that
metadata. The frontend receives `None` for unsupported remote timestamps.

## Concurrency and operation lifecycle

Directory listing and remote download planning use `_start_remote_task`.
Transfer, delete, rename, and remote-directory creation use
`_start_background_operation`. Both keep blocking MAVFTP calls away from the
Tk event loop.

Remote task results and transfer progress are returned to the Tk thread through
queues. While a remote operation is active, relevant controls are disabled
using the ttk state API. Cancellation is represented by a `threading.Event`;
the progress adapter raises `_TransferCancelledError` when cancellation is
observed during a transfer callback.

Batch transfer progress is aggregated in bytes. Unknown-size and zero-byte
files still consume at least one progress unit so they remain cancellable and
do not create a zero-total progress calculation.

## Path and filesystem boundaries

The frontend and backend enforce the following boundaries:

- remote destinations are normalized absolute POSIX paths;
- parent segments are rejected from remote paths;
- names supplied for create and rename operations must be one path component;
- malformed remote listing names are skipped;
- local symbolic links are excluded from recursive transfer planning; and
- local and remote directory deletion is non-recursive.

Paths are passed as MAVFTP values rather than through a shell command.

## Test coverage

`tests/test_download_bin_logs.py` covers panel population, metadata display,
sorting, navigation, selection, context-menu directory creation, recursive
transfer planning/execution, deletion, rename, cancellation-related transfer
behavior, and compatibility workflows.

`tests/test_backend_mavftp.py` and
`tests/test_backend_flightcontroller_files.py` cover MAVFTP and backend
behavior, including listing and transfer details.

Run the focused frontend tests with:

```text
.venv\Scripts\python.exe -m pytest tests/test_download_bin_logs.py -q -p no:cacheprovider
```

## Deferred technical work

- structured remote-listing errors instead of an empty-list error channel;
- preflight discovery of remote upload conflicts;
- real-Tk/end-to-end MAVFTP integration tests; and
- a standalone-window smoke test covering connection establishment and initial
  panel rendering.
