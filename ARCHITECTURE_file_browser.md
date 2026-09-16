# MAVFTP File Browser Architecture

**Status:** Implemented
**Entry point:** Parameter Editor → **Download .bin log file(s)**

> **User-facing documentation:** [USERMANUAL_MAVFTP.md](USERMANUAL_MAVFTP.md)
> is the authoritative description of the browser's interface, workflows,
> shortcuts, confirmations, and troubleshooting. This document describes the
> implementation boundaries and technical contracts.

## Scope

`FileBrowserWindow` is a modal two-panel browser for MAVFTP files on a
connected flight controller and files on the local PC. It is implemented in
`ardupilot_methodic_configurator/frontend_tkinter_file_browser.py`.

The window does not access MAVFTP directly. It coordinates user-interface
state, background work, and local filesystem operations while the data model
and backend own flight-controller communication.

## Layered design

```text
ParameterEditorWindow
        |
        v
FileBrowserWindow(BaseWindow)
        |  FileBrowserUiServices
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

`FileBrowserWindow` owns:

- modal lifecycle and widget state;
- Treeview population, stable item IDs, selection, and sorting;
- local directory enumeration;
- dialogs, confirmations, summaries, and progress display;
- dispatch of blocking remote work to background threads; and
- post-refresh selection of newly created directories.

`frontend_tkinter_file_browser_operations.py` contains the Tk-independent
recursive transfer plans, path/conflict checks, batch workers, and local entry
types. The window
supplies model callbacks and applies results on the Tk thread.
This boundary lets the file-operation policies be tested without constructing a
window.

`FileBrowserUiServices` injects file/directory/name dialogs, messages,
confirmations, and the standard `ProgressWindow` factory. This permits
unit-level testing without a live Tk desktop.

The standalone module creates its own `FlightController`, `LocalFilesystem`,
and `ParameterEditor`; it connects the controller before opening the window.

### Model and backend

`ParameterEditor` exposes the frontend-facing operations and delegates to
`FlightController` and `FlightControllerFiles`. The relevant interface is:

```python
get_remote_files(remote_directory)
upload_file_to_fc(local_filename, remote_filename, progress_callback)
download_remote_file(remote_path, local_filename, progress_callback)
make_remote_directory(remote_directory)
delete_remote_path(remote_path, is_directory=False)
rename_remote_path(remote_path, new_remote_path)
download_last_flight_log(local_filename, progress_callback)
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
`_start_background_operation`. These are thin UI adapters over one
`BackgroundTaskRunner` in `frontend_tkinter_file_browser_tasks.py`, which
serializes work, runs blocking calls in a worker thread, and delivers progress,
results, and errors on the Tk thread.
Unit tests inject an immediate runner instead of relying on a production
code path that runs without Tk.

While a remote operation is active, relevant controls are disabled
using the ttk state API. The browser cannot close until that operation finishes.

Batch transfer progress is aggregated in bytes. Unknown-size and zero-byte
files still consume at least one progress unit, avoiding a zero-total progress
calculation.

Optional CRC32 verification runs after a completed file transfer via
`FlightControllerFiles.verify_remote_file`. Generated `@SYS` files are marked
not verified. The batch summary offers a single explicit retry of failed
file transfers using a reduced plan; successful files and remote mutations
are never retried.

## Path and filesystem boundaries

The frontend and backend enforce the following boundaries:

- remote destinations are normalized absolute POSIX paths;
- parent segments are rejected from remote paths;
- names supplied for create and rename operations must be one path component;
- malformed remote listing names are skipped, including names unsafe on a
  supported local filesystem;
- local symbolic links are excluded from recursive transfer planning; and
- resolved local download targets must remain under the selected directory,
  preventing symbolic-link ancestors from redirecting writes;
- local and remote directory deletion is non-recursive.

Paths are passed as MAVFTP values rather than through a shell command.

## Test coverage

`tests/test_frontend_tkinter_file_browser.py` covers real-Tk construction,
panel behavior, navigation, sorting, context menus, transfers, and the
busy-window lifecycle. `tests/test_frontend_tkinter_file_browser_operations.py`
tests Tk-independent transfer planning, workers, and path boundaries.
`tests/test_frontend_tkinter_file_browser_tasks.py` tests progress, errors, and
task serialization. `tests/test_backend_flightcontroller_file_browser.py`
tests the flight-controller file API used by the browser.

`tests/test_backend_mavftp.py` and
`tests/test_backend_flightcontroller_files.py` cover MAVFTP and backend
behavior, including listing and transfer details.

Run the focused frontend tests with:

```text
python -m pytest tests/test_frontend_tkinter_file_browser.py -q -p no:cacheprovider
```

## Deferred technical work

- structured remote-listing errors instead of an empty-list error channel;
- preflight discovery of remote upload conflicts;
- real-Tk/end-to-end MAVFTP integration tests; and
- a standalone-window smoke test covering connection establishment and initial
  panel rendering.
