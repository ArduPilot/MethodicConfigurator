# Flight-controller file browser

**Status:** Implemented
**Entry point:** Parameter Editor -> **Download .bin log file(s)**
**Implemented on:** September 3, 2026

## Purpose

The Parameter Editor opens a modal, two-panel FTP-style browser for the
connected flight controller. The remote MAVFTP panel is on the left and the
local filesystem panel is on the right. The default remote location is
`/APM/LOGS/`. The browser lists all valid regular remote files, not only
numbered `.BIN` logs, and also displays directories. The existing
**Download last .bin log file** workflow remains available.

## User interface

`DownloadBinLogsWindow` inherits from `BaseWindow`, is transient to the
Parameter Editor, and uses a modal grab except on macOS.

Each panel has a location entry, an icon-only `↖` parent-directory button,
refresh/open controls, a Select all button, and a sortable `ttk.Treeview` with
**Name**, **Type**, and **Size** columns.
The remote entry is initialized to `/APM/LOGS/`; Enter in that field performs
the same operation as Open/Refresh. Double-clicking a directory navigates into
it. The local panel additionally provides Browse and Refresh controls.
The local panel initially opens in the current Parameter Editor vehicle
directory, falling back to the process working directory if that directory is
unavailable.
Backspace navigates to the parent directory of the panel that was most
recently focused or had a selection change.
Delete removes all selected files and empty directories in the last selected
panel. F2 starts an inline rename for the last selected entry, with a name
dialog fallback when inline editing is unavailable.

Filename sorting is case-insensitive. Size sorting uses the numeric byte count,
not the formatted display text. Treeview rows retain stable entry identifiers,
so sorting does not change which file is selected. Ctrl+A and Command+A select
all entries in the focused panel.

## Operations

The action bar provides:

- **Download selected**: recursively copies selected remote files/directories
  into the current local directory;
- **Upload selected**: recursively copies selected local files/directories into
  the current remote directory;
- **Delete remote** and **Rename remote**;
- **Delete local** and **Rename local**;
- **Download last .bin log file**; and
- **Cancel**.

Rename requires exactly one selected entry and accepts only one safe path
component. Parent navigation is performed only through the `↖` button or the
Backspace shortcut; it is not represented as a selectable tree row.

Remote downloads enumerate selected directories recursively, create the local
directory tree, and download regular files. Local uploads create remote
directories parent-first and upload regular files. Local symlinks are skipped.
Deletion is deliberately non-recursive: remote and local directories must be
empty. A non-empty directory is reported as failed while other selected files
and empty directories continue to be processed.

Batch operations continue after individual transfer or management failures.
The modal reports succeeded and failed paths separately after each operation.

## Layered architecture

```text
ParameterEditorWindow
        |
        v
DownloadBinLogsWindow(BaseWindow)
        |  injected dialogs/messages/ProgressWindow
        v
ParameterEditor
        |
        v
FlightController
        |
        v
FlightControllerFiles
        |
        v
MAVFTP
```

The Tkinter window owns modal lifecycle, panel navigation, selection, sorting,
local enumeration, recursive operation planning, dialogs, confirmations,
progress updates, and summaries. It does not call MAVFTP directly.

`ParameterEditor` delegates these operations:

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

`DownloadBinLogsUiServices` injects save-file, directory, and rename selectors,
confirmation/message callbacks, and the standard application ProgressWindow
factory. The legacy single/multiple regular-file download workflow is retained:
one file uses a save-file selector, multiple files use a directory selector,
and existing targets receive one overwrite confirmation.

## Backend model and MAVFTP

`FlightControllerFiles.list_remote_files()` returns files and directories;
`list_bin_log_files()` retains its historical name and filters that listing to
regular files. The manager also implements explicit upload/download, directory
creation, deletion, and rename operations, while retaining the existing
LASTLOG/fallback last-log workflow.

```python
@dataclass(frozen=True)
class FlightControllerLogFile:
    name: str
    remote_path: str
    size_bytes: int
    is_directory: bool = False
```

The local panel uses an equivalent `LocalFileEntry` containing `name`, `path`,
`size_bytes`, and `is_directory`.

Remote paths are normalized to absolute POSIX paths and parent segments are
rejected. Directory entry names must be a single component without `/` or
`\\`; embedded, leading, and trailing spaces are preserved, and malformed
listing names are skipped. Paths are passed to MAVFTP as argument values, not
through a shell, so filenames do not need quoting. This prevents malformed
MAVFTP entries from escaping the selected directory during recursive
operations.

The current MAVFTP `DirectoryEntry` exposes `name`, `is_dir`, and `size_b`, but
no modification timestamp. Therefore modification dates cannot currently be
displayed; that requires MAVFTP and firmware support for timestamp metadata.

## Progress and error behavior

Remote transfers run in a worker thread so the Tk event loop remains responsive.
The browser uses the standard ProgressWindow and adapts each MAVFTP percentage
callback into aggregate byte-oriented batch progress. The Cancel button signals
the active transfer to stop at the next MAVFTP progress boundary and failed
transfers terminate their MAVFTP session. Zero-byte files count as one progress
unit. Empty directories are created without file progress units.

Missing local destinations and invalid remote paths are reported before work
starts. Existing local download targets prompt once. Upload confirmation is
conservative because the browser does not pre-query every remote target.
Later entries continue after a transfer failure. Local symlinks are never
included in recursive transfer or destructive operations.

Known limitations are that listing errors and empty directories both appear as
an empty listing, recursive directory planning can briefly block the UI,
explicit remote methods do not use capability-based directory scoping, and
there is no modification-date metadata. Mutations outside `/APM/LOGS/` display
an additional warning and require a separate confirmation.

## Testing

`tests/test_download_bin_logs.py` covers generic listing and directory metadata,
MAVFTP management delegation, recursive planning and execution for downloads
and uploads, recursive deletion, rename, batch continuation after failure,
filename and numeric-size sorting, Select all/Ctrl+A, parent-directory button
and Backspace navigation, remote refresh/Enter behavior, legacy destination
selectors, and modal integration.

```text
.venv\Scripts\python.exe -m pytest tests/test_download_bin_logs.py -q -p no:cacheprovider
```

## Deferred hardening

- modification-date display pending MAVFTP metadata support;
- structured listing errors instead of an empty-list error channel;
- preflight upload conflict discovery; and
- real-Tk/end-to-end MAVFTP integration tests.
