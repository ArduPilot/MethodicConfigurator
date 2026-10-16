# MAVLink inspector sub-application

The MAVLink inspector displays received messages by source system, component and
message type, with cumulative counts, Hz, B/s, age and selectable latest decoded
fields. It runs either inside AMC or as a standalone program without downloading
parameters or creating a vehicle project.

## Entry points

- `frontend_tkinter_mavlink_inspector.py` contains `MavlinkInspectorWindow`,
  `open_mavlink_inspector_window()`, `create_argument_parser()` and `main()`.
- The Parameter Editor places `MAVLink inspector` directly below
  `Zip vehicle for Forum help`. It is enabled when a live FC transport exists,
  independently of parameter availability and the selected configuration step.
- `pyproject.toml` publishes `amc_mavlink_inspector` as both a console script and
  an `argcomplete.completers` entry. The module includes the global argcomplete
  discovery marker and calls `argcomplete.autocomplete()` before parsing.
- The PowerShell completion module registers the same command.

Examples after installation:

```sh
amc_mavlink_inspector --device COM5 --baudrate 57600
amc_mavlink_inspector --device udp:127.0.0.1:14550
```

Run from a checkout with the project environment:

```sh
python -m ardupilot_methodic_configurator.frontend_tkinter_mavlink_inspector --help
```

The parser provides the standard device, baudrate, reboot-time, logging and
language options. With no device argument, the shared standalone connection
helper tries autodetection and offers the connection selector when appropriate.
A failed/cancelled connection or offline mode does not open an inspector.

## Components and ownership

The frontend reuses `backend_data_telemetry.py` and
`data_model_data_telemetry.py`, which implement message observations and
pure rate calculations independently of plugin registration.
These modules are shared with the data_telemetry plugin; their measurement semantics and limits
are documented in [the telemetry architecture](ARCHITECTURE_data_telemetry.md).
The shared `frontend_tkinter_radio_status.py` frame renders active
connection status, RX/TX rates and parser errors above three-column radio
name/value/unit tuples below the decoded message fields. It contains no
connection selector or label frames.

The message list and decoded fields occupy two vertical `tk.PanedWindow` panes
with one draggable divider and DPI-scaled minimum heights. Radio status and the
Help/Close actions occupy a fixed footer. Live refresh preserves divider positions;
collapsing decoded fields gives their height to the table.

`data_model_mavlink_inspector.py` contains the pure `MavlinkInspectorDataModel`.
It retains the selected sort column/direction, separates messages by sender,
orders numeric measurements at full precision, and formats rows and decoded fields.
Replacing snapshots removes stale fields without resetting sort preferences.
The Tk frontend only renders these ordered rows and preserves the selected item.

`MavlinkInspectorWindow` derives from `BaseWindow`. It owns one 250 ms timer,
one backend observer, the shared telemetry rate model and the inspector message
model. Each tick loads a bounded snapshot, computes rates and refreshes the table.
The shared backend asks the connection manager to use `backend_radio_status.py` to send a GCS heartbeat
immediately and then at most once per second. This enables local SiK radio
status injection; transmitted heartbeat bytes are included in TX measurements.
Closing or suspending monitoring preserves the heartbeat until the FC disconnects,
including while other FC operations block the UI. This avoids a GCS failsafe caused
by closing an embedded inspector. Sends share a lock around PyMAVLink's encoder,
transport write and sequence/signing updates with other connection users.
MAVFTP holds the same encoder's `amc_send_lock` while packing and flushing a
batch, including paths that write directly to the transport. Disconnect cancels
serial writes where supported and bounds the worker join to one second before
transport cleanup; a stopped worker cannot send on a replacement connection.
No second connection, parameter download, command
or stream-rate request is made by the inspector.
All three areas describe the same active transport. There is no link selector
because AMC maintains only one live connection and RADIO sender IDs do not
identify physical links. A future transport selector must be above the panes and
switch every area together.

The embedded helper accepts an existing Tk owner and `FlightController` facade.
The editor obtains that facade through the model's public `flight_controller`
property. Before launch, the editor suspends its active plugin using paired
suspend/resume hooks, or falls back to deactivation/activation for older plugins.
It holds the navigation lock and waits for the child window to close, preventing
registered editor operations or duplicate inspector launches. On non-macOS platforms,
the embedded window also grabs input to block parent plugin controls. An open FC file browser
must close before inspection starts. Cleanup closes the observer and restores
the original plugin only if it is still active and its owner still exists.

The standalone `main()` owns the connection and Tk event loop. It creates the
window after connecting, and a `finally` block closes the monitor and disconnects
the FC, including when the event loop fails. Closing an embedded inspector
preserves the application's connection.

Both explicit Close and Tk-driven destruction cancel pending callbacks and
remove only this observer. Pending resize callbacks are coalesced and cancelled
on close; already-closed callbacks do no work. Cleanup is idempotent.

## Table interaction

The table follows the parameter-export preview's interaction pattern:

- Clicking a heading sorts ascending; clicking it again reverses the order.
- Message names sort alphabetically. System/component IDs, counts, frequency,
  byte rates and ages sort numerically.
- The selected heading shows an ascending or descending arrow.
- Alternate rows use the same `striped` tag and `#eeeeee` background as export.
- Live refresh preserves sort direction, selection and updated decoded fields.
  Stripes are reapplied after sorting, insertion and removal.
- Context-sensitive table tooltips explain each heading/cell, sort actions and
  column-width dividers. Labels, values, units, scrollbars, section titles and
  actions have beginner guidance, including in the shared radio panel.
- A visible, wrapping notice explains that USB measures USB traffic, and that
  testing a telemetry radio requires connecting through that link.

## Packaging and verification

The message table and collapsible decoded fields share one vertical divider.
Collapsing the fields gives their space to the table. Connection traffic and
radio status occupy a fixed footer with Help and Close controls. Help opens
the published `USERMANUAL_MAVLink_inspector.html`, following the file browser's
documentation convention.

The shared `RadioStatusView` hides the radio metric widgets when a current
RADIO/RADIO_STATUS sample is absent, while connection traffic remains visible.
It wraps either the missing-report notice or the radio-field explanation to
its own allocated width, independently of the host plugin or inspector.

`scripts/regenerate_app_screenshots_fully_automated.py` includes inspector
targets with radio readings, without radio reports, and with decoded fields
collapsed. These render real widgets using illustrative `TelemetryState`
samples and disabled polling, without accessing a vehicle or network.

The editor statically imports the inspector frontend, whose imports also bring
in the top-level telemetry backend/model and radio-status backend. All three
PyInstaller specs discover these modules through normal imports. Their plugin
submodule collection handles dynamically registered plugin modules.
No new dependency or data asset is required.

`tests/test_data_model_mavlink_inspector.py` verifies every sort column, precise
ordering before display rounding, ties, sender identities, live field updates
and invalid sort requests without creating Tk windows.
`tests/test_frontend_tkinter_mavlink_inspector.py` verifies real sortable/striped
widgets, beginner tooltips, wrapping, fixed-footer visibility, live selection,
polling and cancellation, startup errors, standalone connection ownership,
CLI/completion declarations and editor integration. Geometry tests avoid unsafe
rendering on headless macOS; other GUI tests keep rendering patches active there.
`tests/test_backend_data_telemetry.py` exercises real MAVLink encoding/parsing,
rates, stale telemetry, radio heartbeats and backend lifecycle.
Hardware range and throughput verification still requires a physical link.
