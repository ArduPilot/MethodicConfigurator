# Flight-Controller Log File Download Window

**Status:** Implemented, with the limitations documented below
**Entry point:** `Parameter Editor` → **Download .bin log file(s)**
**Implemented on:** September 3, 2026

## Purpose and scope

The Parameter Editor opens a modal window for browsing and downloading regular
files exposed by MAVFTP. The default remote directory is `/APM/LOGS/`, but the
user can enter another absolute remote directory and press **Open/Refresh**.
The list is intentionally not restricted to numbered `.BIN` names; files such
as `LASTLOG.TXT` and other regular entries are also shown.

The existing **Download last .bin log file** action remains available in the
modal and continues to use the existing last-log discovery workflow.

The first implementation is download-only. It does **not** provide a local
file-browser panel, remote upload, delete, rename, or log analysis.

## Requirements and implementation status

| Requirement | Current implementation |
| --- | --- |
| Rename the Parameter Editor button | Button text is **Download .bin log file(s)**. |
| Open a modal `BaseWindow` | `DownloadBinLogsWindow` is a transient modal child and uses a Tk grab except on macOS. |
| Default remote directory | `/APM/LOGS/`. |
| Remote location control | Entry plus **Open/Refresh** button above the remote file list; pressing Enter in the entry performs the same refresh. |
| List all files | All regular entries returned by `cmd_list()` are converted to `FlightControllerLogFile`; directories and invalid entry names are skipped. |
| Select one or more files | `ttk.Treeview(selectmode="extended")`. |
| Select all | **Select all** and **Ctrl+A** select every listed entry except a defensive `..` entry. |
| Sort results | Clicking **File name** sorts case-insensitively by filename; clicking **Size** sorts numerically by bytes. Repeated clicks reverse the direction. |
| Single-file download | `asksaveasfilename()` supplies the complete local destination filename. |
| Multi-file download | `askdirectory()` supplies the local destination directory; remote basenames are used for local filenames. |
| Existing local destinations | A single overwrite confirmation is requested when any target already exists. Declining cancels before transfers start. |
| Partial failures | Transfers run sequentially and continue after a failure. The final message lists downloaded and failed filenames separately. |
| Progress | Existing `ProgressWindow` callbacks are used. Multi-file progress is aggregated using the listed file sizes. |
| Last-log action | Delegates to `ParameterEditor.download_last_flight_log_workflow()`. |
| Two-panel FTP browser | Deferred. No local panel or local-to-flight-controller upload is implemented. |

The Parameter Editor button is disabled unless a flight controller is
connected and MAVFTP is supported. The modal and model still perform defensive
checks because connection state can change after the button is created.

## Runtime architecture

```text
ParameterEditorWindow
        |
        | opens DownloadBinLogsWindow
        v
DownloadBinLogsWindow(BaseWindow)
        |
        | injected dialogs, messages, progress factory
        v
ParameterEditor
        |
        | delegates list/download calls
        v
FlightController facade
        |
        v
FlightControllerFiles
        |
        v
MAVFTP / selected remote directory
```

Responsibilities are separated as follows:

- **Tkinter window:** modal lifecycle, remote-directory entry, tree selection,
  destination dialogs, Select all, and presentation.
- **Parameter model:** destination mapping, overwrite policy, sequential batch
  orchestration, aggregate progress, and per-file result reporting.
- **Flight-controller facade:** stable delegation boundary.
- **Flight-controller file manager:** MAVFTP path normalization, directory
  listing conversion, and explicit file transfer.
- **MAVFTP:** remote directory listing and file transfer.

## Application-level file model

`backend_flightcontroller_files.py` defines:

```python
@dataclass(frozen=True)
class FlightControllerLogFile:
    name: str
    remote_path: str
    size_bytes: int
```

This record represents a regular remote file. It deliberately does not expose
`backend_mavftp.DirectoryEntry` to the UI and has no `is_directory` field,
because directory entries are filtered out by `FlightControllerFiles`.

## Backend API

`FlightControllerFiles` provides:

```python
def list_bin_log_files(
    self,
    remote_directory: str = "/APM/LOGS/",
) -> list[FlightControllerLogFile]: ...


def download_bin_log_file(
    self,
    remote_path: str,
    local_filename: str,
    progress_callback: Callable[[int, int], None] | None = None,
) -> bool: ...
```

The historical `bin_log` method name is retained for compatibility with the
feature entry point, although the listing accepts every regular filename.

### Listing behavior

1. Verify that a master connection exists and MAVFTP is supported.
2. Normalize the entered path to absolute POSIX form.
3. Ensure a directory path has a trailing `/`.
4. Call `cmd_list([normalized_directory])`.
5. Skip directory entries.
6. Convert valid direct-child names into `FlightControllerLogFile` records,
   preserving directory order, casing, and non-negative size.

The backend rejects empty, relative, or parent-directory (`..`) path segments.
MAVFTP/listing exceptions and invalid preconditions are currently logged and
returned as an empty list; the UI therefore presents an empty state rather than
an error-specific state for those backend failures.

### Explicit download behavior

`download_bin_log_file()` normalizes an absolute remote path and delegates to
the shared MAVFTP download helper. MAVFTP completion percentages are converted
to the application's `(current, total)` callback convention.

The current API validates that the path is absolute and contains no `..`
segment, but it does **not** receive the selected remote directory and does not
prove that the path belongs to that directory. The UI normally passes paths
returned by `list_bin_log_files()`, but this is a trust-boundary limitation that
should be addressed before exposing the API to a general remote-file browser.

The existing `download_last_flight_log()` method and its
`LASTLOG.TXT` → directory listing → binary-search fallback order remain
unchanged apart from sharing the transfer helper.

## Parameter model workflows

`ParameterEditor` exposes:

```python
def get_bin_log_files(
    self,
    remote_directory: str = "/APM/LOGS/",
) -> list[FlightControllerLogFile]: ...


def download_selected_bin_logs_workflow(
    self,
    selected_files: Sequence[FlightControllerLogFile],
    destination: str,
    destination_is_directory: bool,
    ask_overwrite: AskConfirmationCallback,
    show_error: ShowErrorCallback,
    show_info: ShowInfoCallback,
    progress_callback: Callable[[int, int], None] | None = None,
) -> BinLogDownloadResult: ...
```

`BinLogDownloadResult` contains:

```python
successful: tuple[str, ...]
failed: tuple[str, ...]
cancelled: bool
```

The workflow:

1. Rejects an empty selection without side effects.
2. Validates a directory destination for multi-file downloads.
3. Uses the user-selected complete path for a single-file download.
4. Builds multi-file targets from the chosen directory and each `name`.
5. Asks once if any target already exists. This check currently applies to
   both single-file and multi-file operations.
6. Downloads files sequentially.
7. Continues after a failed transfer.
8. Reports all successful and failed names in the final message.

Aggregate progress uses `max(size_bytes, 1)` for each file, so zero-byte files
still contribute one progress unit. Backend transfer failures are represented
as failed entries rather than raised to the UI.

### Current trust-boundary limitation

The workflow joins `Path(destination)` with each `FlightControllerLogFile.name`.
The backend listing rejects common POSIX path components, but the workflow
itself does not independently enforce a basename-only policy. A future
hardening change should reject `/`, `\`, `.`, `..`, absolute names, and
platform-specific path components before creating local targets.

## Modal UI

`DownloadBinLogsWindow`:

- inherits from `BaseWindow`;
- is transient to the Parameter Editor;
- centers over its parent;
- uses a modal grab except on macOS;
- initializes the remote entry to `/APM/LOGS/`;
- loads the initial listing synchronously during construction;
- displays only filename and formatted size columns;
- makes the filename and size headings clickable for ascending/descending
  sorting;
- supports extended Treeview selection;
- provides **Open/Refresh**, **Download**, **Select all**,
  **Download last .bin log file**, and **Cancel**;
- keeps the modal open after success, cancellation, or transfer failure.

The **Select all** button and **Ctrl+A** key binding call
`Treeview.selection_set()` for all current rows except a row whose
application-level filename is exactly `..`. The backend normally filters that
entry before it reaches the UI, so this is defensive behavior.

Sorting is performed in the UI without another MAVFTP request. Filename
sorting uses case-insensitive raw names; size sorting uses `size_bytes`, not
the human-readable size text displayed in the Treeview. Sorting reorders rows
while retaining their stable numeric Treeview identifiers, so selected files
continue to map to the correct application records.

The UI uses `ParameterEditorUiServices` for:

- save-file selection;
- directory selection;
- overwrite confirmation;
- information/error messages; and
- progress-window creation.

No worker thread is used. The MAVFTP operations are synchronous, so the
window does not currently show a separate listing progress dialog or disable
its controls during the synchronous list/transfer call.

## User workflows

### Open and refresh

1. The user presses **Download .bin log file(s)**.
2. The modal opens with `/APM/LOGS/` in the remote entry.
3. The initial list is loaded.
4. The user may edit the entry and press **Open/Refresh**.
5. The current Treeview contents are replaced with the returned regular files.

Pressing Enter while the remote-directory entry has focus performs the same
refresh action.

The entry is passed to the model, and backend normalization is applied there.
The label displays the user-entered text rather than the normalized path.

### Select and download one file

1. The user selects one row.
2. The user presses **Download**.
3. `asksaveasfilename()` opens with the remote basename as `initialfile`.
4. Cancellation returns without creating a progress window or starting a
   transfer.
5. The selected complete local path is passed to the model.
6. MAVFTP progress is displayed through the standard progress window.

### Select and download multiple files

1. The user selects multiple rows, manually or with **Select all**.
2. The user presses **Download**.
3. `askdirectory()` chooses the local destination directory.
4. Cancellation returns without a transfer.
5. The model checks for existing targets and asks once before overwriting.
6. Files are transferred in selection/list order.
7. A failed file does not stop later files.
8. A final summary identifies each downloaded and failed filename.

### Download the last log

The modal's **Download last .bin log file** button uses the existing
`download_last_flight_log_workflow()` and its existing save dialog, discovery
fallbacks, and success/failure behavior.

## Error and edge-case behavior

| Situation | Current behavior |
| --- | --- |
| No connection or unsupported MAVFTP at entry point | Parameter Editor button is disabled. |
| Connection lost before listing | Backend returns `[]` after logging the failure. |
| Invalid/relative/parent-segment remote directory | Backend returns `[]` after logging the validation failure. |
| MAVFTP list exception | Backend returns `[]`; UI shows the empty state. |
| Empty remote directory | UI shows the empty-state text and no downloadable selection. |
| Save-file or directory dialog cancelled | No transfer is started. |
| Existing local target | One confirmation is requested; rejection marks the request cancelled before transfer. |
| Remote file disappears or transfer fails | That file is marked failed; the remaining batch continues. |
| Invalid local directory for a batch | Error is shown and all selected names are returned as failed. |
| One-file transfer failure | Error summary is shown and the modal remains open. |
| Multi-file partial failure | Error summary contains both downloaded and failed names; modal remains open. |

The current implementation does not explicitly disable or defer window
destruction while a synchronous operation is running. It also does not
reconcile the list after a failed transfer.

## Security and correctness review findings

The following points were identified during adversarial review and are
documented rather than silently presented as guarantees:

1. **Remote-directory scoping:** explicit downloads accept any normalized
   absolute remote path. The selected directory is not carried into the
   download API.
2. **Local basename validation:** the model trusts `FlightControllerLogFile.name`
   when constructing local targets. The backend filters common POSIX traversal
   forms, but cross-platform separator validation is not centralized.
3. **Error-channel ambiguity:** listing failures return `[]`, which is
   indistinguishable from an empty directory in the UI.
4. **Synchronous UI:** list and transfer operations run on the UI call stack;
   no listing progress indicator or operation-state lock exists.
5. **Display path:** the remote path label shows the raw entry text, not the
   normalized path used by MAVFTP.
6. **Test boundary:** current feature tests cover backend listing, model
   workflows, selector choice, Select all, batch continuation, and modal
   integration. They do not instantiate a real Tk window, exercise facade
   delegation directly, or verify generated translations.

These are follow-up hardening items, not behavior currently guaranteed by the
feature.

## Testing

Current feature-specific tests are in
`tests/test_download_bin_logs.py`. They cover:

- arbitrary regular filenames and directory exclusion;
- default and custom remote directories;
- overwrite confirmation and cancellation;
- continuation after a failed transfer;
- per-file summary contents;
- filename and numeric-size sorting;
- single-file save dialog selection;
- multi-file directory selection;
- Select all and Ctrl+A excluding `..`; and
- Parameter Editor modal integration.

The implementation was validated with the feature test module, Ruff, and
Pyright. The broader repository suite contains unrelated environment-sensitive
tests, including GUI tests and Windows temporary-directory permission
failures; those are not part of this feature's passing targeted test result.

## Deferred work

The following changes are intentionally outside the current implementation:

- two-panel FTP-style local/remote browser;
- local-to-flight-controller upload;
- delete, rename, and remote directory navigation UI;
- explicit remote-directory scoping for download requests;
- centralized local-basename validation;
- structured listing errors instead of `[]`;
- asynchronous transfer/listing with cancellable operation state;
- generated translation-resource updates; and
- real-Tk, facade, and end-to-end MAVFTP integration tests.
