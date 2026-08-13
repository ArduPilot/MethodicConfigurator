# External Parameter File Upload Architecture

## Overview

The external parameter file comparison and upload feature allows a user to load an ArduPilot
`.parm` or `.param` file that is not part of the files managed by ArduPilot Methodic Configurator
(AMC), inspect its values against the connected flight controller (FC), optionally make temporary
per-parameter changes, and selectively upload parameters.

This workflow is deliberately separate from the sequential configuration-step workflow.
Opening or editing an external file does not add it to the vehicle project, change the current
configuration step, write to the selected file, or ask whether temporary edits should be saved.

## Requirements

### Functional Requirements

1. **External file selection**
   - Provide an `Compare and upload` button beside the parameter-editor legend.
   - Disable this entry button when no FC is connected.
   - Allow selection of `.parm` and `.param` files.
   - Parse and validate the selected file with the standard `ParDict` parser.
   - Report parsing and file-access errors without changing the active AMC project.

2. **Modal parameter preview**
   - Display the selected file in a modal child window.
   - Reuse the standard parameter table and parameter metadata presentation.
   - Display parameter name, current FC value, difference indicator, file/new value, unit,
     Upload checkbox, and Manual checkbox.
   - Omit parameter add/delete controls and the change-reason field.

3. **Upload selection**
   - Provide one Upload checkbox per parameter.
   - Select changed or FC-missing parameters by default when an FC is connected.
   - Leave parameters whose file value equals the FC value deselected by default.
   - Upload only parameters whose Upload checkbox is selected and currently displayed.
   - Preserve Upload selections while the table is repopulated.

4. **Temporary manual editing**
   - Keep every loaded value non-editable by default.
   - Provide one Manual checkbox per writable parameter.
   - Make only that parameter's value editable when its Manual checkbox is selected.
   - Keep edits in memory and use them only for the current upload operation.
   - Restore the value loaded from the external file when Manual is cleared.
   - Never persist a temporary edit to the external file or an AMC-managed file.

5. **Changed-parameter filtering**
   - Provide a `Show only changed parameters` checkbox.
   - Treat parameters missing from the FC as changed.
   - Do not advance or skip an AMC configuration step when no differences exist.

6. **FC upload**: Provide `Compare and upload` and `Cancel` buttons. Use the comparison table to
   review FC values against the external file before uploading. Reuse the standard parameter
   upload, reset, reconnect, re-download, validation, retry, error-reporting, and progress-window
   workflows. Warn before upload when a temporary manual edit differs from the FC value but its
   Upload checkbox is not selected. Close the modal after a successful upload without advancing the
   AMC configuration step.

### Non-Functional Requirements

- Avoid duplicating parameter table rendering and upload orchestration.
- Preserve the behavior of the normal AMC parameter editor.
- Keep project-managed and external-file state clearly separated.
- Validate temporary edits with the same metadata, type, range, choice, and bitmask rules used
  by the regular parameter editor.
- Keep the window modal so that the underlying parameter editor cannot change configuration
  step while an external upload is being prepared.

## Architectural Context

The feature is launched from the normal parameter editor but owns a separate set of
`ArduPilotParameter` objects:

```text
External .parm/.param file
          |
          v
      ParDict parser
          |
          v
External ArduPilotParameter objects <---- FC values + parameter metadata
          |
          v
Configurable shared ParameterEditorTable
          |
          v
Selected temporary values as ParDict
          |
          v
Existing FC upload workflow
```

The active `ParameterEditor.current_step_parameters` remains untouched throughout this flow.

## Components

### Parameter Editor Entry Point

- **File**: `ardupilot_methodic_configurator/frontend_tkinter_parameter_editor.py`
- **Methods**: `_create_conf_widgets()`, `on_upload_parameter_file_click()`
- **Responsibilities**:
  - Place the external upload button to the right of the legend.
  - Disable external upload button when no FC is connected.
  - Open the file-selection dialog with `.parm` and `.param` filters.
  - Ask the data model to parse the selected file.
  - Display file errors through the injected UI services.
  - Construct the modal `ParameterFileUploadWindow` after successful parsing.

The entry point does not alter `current_file`, the configuration-step combobox, or project
filesystem state.

### External Parameter Upload Window

- **File**: `ardupilot_methodic_configurator/frontend_tkinter_parameter_compare_and_upload.py`
- **Class**: `ParameterFileUploadWindow`
- **Responsibilities**:
  - Own the modal window lifecycle.
  - Show the full path of the selected external file.
  - Configure and host the shared parameter table.
  - Apply the changed-only filter.
  - Obtain the checked upload payload from the table.
  - Run upload precondition checks and delegate to the parent upload workflow.
  - Close without invoking project navigation or save operations.

The modal upload button does not duplicate the entry-point connection-state gate. The upload
precondition remains in the data model to handle a connection that disappears while the modal is open.

The window is transient to the main parameter editor. A Tk grab is used for modality on
platforms other than macOS, where grabs are intentionally avoided because of known Tk freezes.

### Configurable Parameter Table

- **File**: `ardupilot_methodic_configurator/frontend_tkinter_parameter_editor_table.py`
- **Classes**: `ParameterEditorTable`, `ParameterTableOptions`
- **Responsibilities**:
  - Render both the normal AMC table and the external upload table.
  - Select columns and behaviors through `ParameterTableOptions`.
  - Render per-row Upload and Manual controls.
  - Preserve upload selections across repopulation.
  - Validate edits and update difference indicators.
  - Build a `ParDict` containing only selected external parameters.

The external modal uses these options:

| Option | Value | Effect |
| --- | ---: | --- |
| `show_parameter_actions` | `False` | Hides add/delete controls |
| `show_upload_column` | `True` | Shows per-parameter Upload checkboxes |
| `show_manual_override_column` | `True` | Shows per-parameter Manual checkboxes |
| `show_change_reason_column` | `False` | Omits the change-reason field |
| `values_editable` | `False` | Makes all values read-only initially |
| `skip_when_no_differences` | `False` | Prevents AMC step navigation |
| `manual_override_for_all_parameters` | `True` | Gives external parameters temporary Manual behavior |

`manually_editable_parameters` is an in-memory set of names whose Manual checkbox is active.
It is table-view state, not the persisted manual-override state used by forced and derived AMC
parameters.

### Parameter Editor Data Model

- **File**: `ardupilot_methodic_configurator/data_model_parameter_editor.py`
- **Methods**: `load_external_parameter_file()`, `update_parameter_object()`,
  `parameters_as_par_dict()`
- **Responsibilities**:
  - Parse external files through `ParDict.from_file()`.
  - Create independent `ArduPilotParameter` objects using available documentation, default
    values, and current FC values.
  - Validate changes to parameter objects that are not in `current_step_parameters`.
  - Convert selected parameter objects to the `ParDict` required by the upload workflow.

An empty configuration-step filename is supplied while constructing external parameter objects.
This prevents forced or derived definitions from the active AMC step being applied to the external
file.

### ArduPilot Parameter Model

- **File**: `ardupilot_methodic_configurator/data_model_ardupilot_parameter.py`
- **Method**: `reset_new_value_to_file_value()`
- **Responsibilities**:
  - Retain the immutable value originally loaded from the external file.
  - Hold a separately editable in-memory new value.
  - Restore the original file value when the external Manual checkbox is cleared.

The reset method changes only the in-memory candidate value. It performs no file I/O.

### Existing Upload Infrastructure

- **Files**: `frontend_tkinter_parameter_editor.py`, `data_model_parameter_editor.py`
- **Methods**: `ParameterEditorWindow.upload_selected_params()`,
  `ParameterEditorWindow.upload_external_params()`,
  `ParameterEditorUiServices.upload_params_with_progress()`,
  `ParameterEditor.upload_selected_params_workflow()`,
  `ParameterEditor.upload_external_params_workflow()`
- **Responsibilities**:
  - Validate that parameters and an FC connection are available.
  - Upload parameters that require an FC reset in the correct order.
  - Reset and reconnect when required.
  - Upload remaining selected parameters.
  - Re-download FC parameters and validate the resulting values.
  - Offer retry/cancel behavior and manage progress windows.

The external model entry point delegates to the common upload implementation with project-state
persistence disabled. The shared FC safety mechanics remain common, while the normal workflow
continues to write the current-step marker and reports.

## State Model

Each external parameter has four relevant pieces of state:

| State | Owner | Lifetime | Persistent? |
| --- | --- | --- | ---: |
| Value loaded from file | `ArduPilotParameter` | Modal lifetime | No writes |
| Candidate/new value | `ArduPilotParameter` | Modal lifetime | No |
| Upload selection | `ParameterEditorTable.upload_checkbutton_var` | Modal lifetime | No |
| Manual selection | `ParameterTableOptions.manually_editable_parameters` | Modal lifetime | No |

The FC value and parameter metadata in each external parameter object are snapshots supplied when
the object is created. The shared upload workflow refreshes its FC parameter cache for verification;
it does not convert the modal's original comparison values into project state.

## Detailed Workflows

### Open and Display

1. The user presses `Compare and upload` to choose an external file for comparison.
2. Tk displays a file picker restricted to ArduPilot parameter files, with an all-files fallback.
3. Cancellation returns without side effects.
4. `ParameterEditor.load_external_parameter_file()` parses the selected file.
5. Each parsed `Par` is converted to an `ArduPilotParameter` with metadata, default value, and
   matching FC value when available.
6. `ParameterFileUploadWindow` creates the configured shared table.
7. The modal grab prevents configuration-step changes behind the window.

### Manual Edit

1. All New Value widgets begin disabled.
2. Selecting Manual for a writable row adds its name to `manually_editable_parameters`.
3. The table enables only that row's existing value widget; the static table is not rebuilt.
4. The user edits the value; standard parameter validation runs.
5. The candidate value and difference indicator update in memory.
6. Clearing Manual removes the name from the set and restores the original external-file value.
7. Closing or cancelling the modal discards every temporary edit.

This Manual behavior must not be confused with the persisted `@manual_override` mechanism for
forced and derived parameters in AMC-managed configuration steps.

### Changed-Only Filter

1. Selecting `Show only changed parameters` repopulates the shared table.
2. A parameter remains visible when its candidate value differs from the FC value or the parameter
   is absent from the FC parameter set.
3. Upload selections are captured before widgets are destroyed so they survive repopulation.
4. An empty result leaves the modal open and does not call the parameter editor's skip action.

### Upload

1. `ParameterEditorTable.get_upload_selected_params()` reads the visible Upload checkbox states.
2. The table identifies manually enabled parameters that were edited, differ from the FC, and are
   not selected for upload; the modal warns the user and stops that upload attempt when this set
   is non-empty.
3. Selected external `ArduPilotParameter` objects are converted to a `ParDict` using their current
   candidate values.
4. `ensure_upload_preconditions()` rejects an empty selection or missing FC connection.
5. `ParameterEditorWindow.upload_external_params()` invokes the shared progress-managed upload
   UI with `ParameterEditor.upload_external_params_workflow()`.
6. Reset-required parameters, reconnection, remaining uploads, re-download, and validation follow
   the normal parameter editor rules.
7. The user reviews the differences and may edit values temporarily before pressing `Upload selected params to the FC`.
8. On success the modal closes.
9. The current AMC configuration step is not saved, skipped, or advanced; no tuning report or
   FC-difference export is written.

## Data Integrity Invariants

The following invariants define the boundary between external upload and project editing:

- The selected external file is opened only for parsing.
- The external file is never passed to a write/export method.
- External parameters are never inserted into `ParameterEditor.current_step_parameters`.
- External parameters are never inserted into `LocalFilesystem.file_parameters`.
- Temporary changes never set the normal parameter editor's dirty/save state.
- The external upload path never calls `write_changes_to_intermediate_parameter_file()`.
- The external upload path never writes `last_uploaded_filename.txt`, `tuning_report.csv`, or an
  FC-difference export.
- Reset timing uses `BRD_BOOT_DELAY` from the selected external payload when present, rather than
  the active AMC step.
- Read-only parameters are never selected or included in an external upload payload.
- The external upload path never calls `on_skip_click()` or changes `current_file`.
- Cancel always destroys the modal without file or project mutations.
- Only the checked Upload parameters are converted to the upload payload.

## Error Handling

- **File cancelled**: return silently.
- **Malformed, duplicate, invalid, non-finite, or incorrectly encoded parameter**: show a
  `Parameter file error` dialog and do not open the modal.
- **No FC connection**: disable the parameter editor's `Compare and upload` entry button;
  the model precondition remains a defensive check if the connection is lost while the modal is open.
- **No Upload checkbox selected**: show the standard no-parameter-selected warning.
- **Unselected changed manual edit**: warn with the omitted parameter names and leave the modal
  open without starting an upload.
- **Invalid temporary value**: show the same validation feedback as the regular parameter editor.
- **Out-of-range value**: use the shared confirmation behavior.
- **Upload or verification failure**: use the standard error and retry/cancel workflow.
- **External-only parameter name**: render directly from the external parameter object rather than
  looking it up in the active AMC configuration step.

## Testing Strategy

### Data Model Tests

- Load `.parm` files into independent `ArduPilotParameter` objects.
- Attach FC context without registering the file in project state.
- Validate temporary object edits.
- Convert edited objects to upload `ParDict` values.
- Restore the value loaded from the file when a temporary edit is discarded.

### Table and Modal Tests

- Verify external-table columns include Upload and Manual and omit editor-only columns.
- Verify Manual affects only the selected parameter.
- Verify clearing Manual discards its in-memory edit.
- Verify external-only names do not access `current_step_parameters`.
- Verify only Upload-checked parameters enter the payload.
- Verify the modal delegates to the shared upload workflow and never advances the project.
- Verify a failed model upload leaves the modal open.
- Verify Manual toggles update only the affected row rather than rebuilding the static table.
- Verify file-selection and parse-error orchestration.

### Regression Tests

The default `ParameterTableOptions` retain the normal parameter editor layout and behavior. Existing
parameter editor and `ArduPilotParameter` tests protect the managed-file editing, forced/derived
manual override, validation, bitmask, and upload workflows while the external-specific tests cover
the alternate table configuration. Model-level external upload tests exercise the shared upload
orchestration and assert that it produces no AMC project markers, reports, or exports.

## Extension Points

- Additional read-only comparison columns can be added through `ParameterTableOptions` without
  creating a separate table implementation.
- A future preview summary can consume the external parameter dictionary without changing project
  ownership.
- Additional accepted ArduPilot parameter filename extensions can be added at the file-selection
  boundary while keeping parsing centralized in `ParDict`.
- Upload policy changes should be implemented in the shared `ParameterEditor` upload workflow so
  both managed and external parameter uploads retain identical FC safety behavior.
