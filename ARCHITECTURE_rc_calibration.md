# RC Calibration Plugin Architecture

## Status Legend

- ✅ **Green Check**: Fully implemented and tested with BDD pytest
- 🟡 **Yellow Check**: Implemented but not yet tested with BDD pytest
- ❌ **Red Cross**: Not implemented

## Overview

The RC Calibration plugin allows users to monitor and calibrate RC (Radio Control) inputs
directly from within the ArduPilot Methodic Configurator (AMC), without switching to
Mission Planner or another GCS.
It follows the same Model-View separation pattern used by the other plugins, and introduces
an additional optional renderer module for 3D vehicle attitude visualisation.

**Key Features:**

- Live RC telemetry display: stick positions (roll/pitch/throttle/yaw) and all 16 RC input channels
- Per-channel PWM labels to the left of status bars mapped across 800-2200 µs
- Green MIN, blue TRIM and red MAX markers on every channel; matching text appears only above channel 1
- 100 ms non-blocking polling via tkinter `after()` — same pattern as accelerometer calibration
- Floating, draggable live-monitor popup (`RCCalibrationPopup`) for real-time feedback
- Remote controller stick preview with two side-by-side 126×126 white squares (30% smaller than the original)
  and red circles whose diameter is 1/12 of the square side
- Channel-function column: channels selected by staged/cached `RCMAP_*` show the primary controls and are fixed;
  the configured `FLTMODE_CH` is marked Mode and fixed; other channels select their firmware-supported `RCx_OPTION`
- Auxiliary-function choices come from the loaded ArduPilot parameter metadata; selections stage New values and
  become flight-controller writes only through the existing parameter-upload action
- Selectable RC mapping presets 1-4; selection stages `RCMAP_ROLL/PITCH/THROTTLE/YAW` in the New-value table
- Existing matching mappings select their preset automatically; custom mappings are retained and shown as Custom
- Axis labels use horizontal ↔ and vertical ↕ direction symbols
- Axis positions respect staged `RCMAP_*` and `RCn_MIN/MAX/TRIM/REVERSED`, falling back to cached FC values
- Mapping and calibration edits never write to the controller until the existing parameter upload workflow is invoked
- Scrollable embedded and popup content keeps the 16 channel rows accessible in small windows
- Compact 4-pixel frame padding, section spacing and outer margins align with the documentation frame;
  the scrollbar sits at the right edge inside that margin, without an extra canvas inset
- Compact RC-driven craft monitor: proportional roll/pitch lean, continuous yaw rotation and throttle lift
- Projected 3D craft drawing delegated to `renderer_3d_quadcopter.py`, using the existing Pillow dependency
- Embedded plugin view (`RCCalibrationView`) + standalone dev window (`RCCalibrationWindow`)

> **Note:** The data model reads MAVLink `RC_CHANNELS` and `HEARTBEAT` messages from the flight-controller
> connection. The craft illustrates interpreted RC inputs, not measured vehicle attitude or actual flight.
> It is a stylized Quad-X, not a vehicle-specific mesh or a physics simulation.

## Architecture

### Component Layers

```text
┌────────────────────────────────────────────────────────────────────┐
│ GUI Layer (frontend_tkinter_rc_calibration.py)                     │
│                                                                    │
│ ┌──────────────────────────────────────────────────────────────┐   │
│ │ RCCalibrationView (ttk.Frame) — embedded in parameter editor │   │
│ │  - Two compact white gimbals; red circles show stick positions│  │
│ │  - RC mapping preset selector; staged New-value edits       │   │
│ │  - 16 RC status bars with PWM labels and function selectors   │   │
│ │  - RCMAP / flight-mode roles locked; RCx_OPTION choices staged│   │
│ │  - Green MIN / blue TRIM / red MAX; CH1-only text legend     │   │
│ │  - 100 ms after() poll → get_rc_telemetry()                  │   │
│ └──────────────────────────────────────────────────────────────┘   │
│                                                                    │
│ ┌──────────────────────────────────────────────────────────────┐   │
│ │ RCCalibrationPopup (tk.Toplevel) — floating draggable window │   │
│ │  - Borderless, transient popup window                        │   │
│ │  - Custom title bar with drag-to-move                        │   │
│ │  - Same stick / mapping / channel widgets as embedded view   │   │
│ │  - 3D attitude preview via QuadcopterRenderer                │   │
│ │  - 100 ms after() poll → get_rc_telemetry()                  │   │
│ └──────────────────────────────────────────────────────────────┘   │
│                                                                    │
│ RCCalibrationWindow (BaseWindow) — standalone dev/test window      │
└─────────────────────────────┬──────────────────────────────────────┘
                              │
┌─────────────────────────────▼──────────────────────────────────────┐
│ Optional Renderer (renderer_3d_quadcopter.py)                      │
│ - QuadcopterRenderer: projects procedural Quad-X faces into PIL     │
│ - Roll/pitch lean, yaw heading, throttle vertical lift              │
│ - No OpenGL, external assets or additional runtime dependencies     │
└────────────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────▼──────────────────────────────────────┐
│ Data Model (data_model_rc_calibration.py)                          │
│ - RCCalibrationDataModel                                           │
│ - start_calibration() / cancel_calibration() / finish_calibration()│
│ - get_rc_telemetry() → dict with roll/pitch/throttle/yaw/          │
│   flight_mode/channels                                             │
│ - Reads MAVLink RC_CHANNELS / HEARTBEAT telemetry when connected   │
└─────────────────────────────┬──────────────────────────────────────┘
                              │
┌─────────────────────────────▼──────────────────────────────────────┐
│ ParameterEditor (data_model_parameter_editor.py)                   │
│ - Owns editable New values and parameter addition/removal APIs      │
│ - Validates metadata and serializes values/reasons for upload       │
│ - Only the explicit upload workflow calls FlightController.set_param│
│ FlightController facade (backend_flightcontroller.py)              │
│ - Provides telemetry and downloaded parameter cache                │
└────────────────────────────────────────────────────────────────────┘
```

### File Map

| File | Role |
| ------ | ------ |
| `plugin_constants.py` | `PLUGIN_RC_CALIBRATION = "rc_calibration"` |
| `data_model_rc_calibration.py` | MAVLink parsing, extrema tracking, atomic staged calibration and mapping edits |
| `frontend_tkinter_rc_calibration.py` | Shared `RCCraftPreview`, `RCStickPreview`, `RCChannelBars`, popup/view/window & factories |
| `renderer_3d_quadcopter.py` | Pure Pillow projected 3D Quad-X renderer |
| `__main__.py` | Lazy plugin registration wires `register_rc_calibration_plugin()` |
| `plugin_factory.py` | Creates the registered view and model through their factories |
| `data_model_parameter_editor.py` | Shared dispatch injects editor; owns New values and explicit upload workflow |
| `configuration_steps_schema.json` | `"rc_calibration"` added to plugin name enum |
| `vehicle_templates/ArduCopter/Holybro_X500_mig/configuration_steps_ArduCopter.json` | Example step wiring for the RC calibration plugin |
| `vehicle_templates/ArduCopter/empty_4.6.x_mig/configuration_steps_ArduCopter.json` | Empty migration template step wiring |
| Both migration templates' `07_remote_controller_controller.param` | Editable Mode-2 default mapping entries |
| `tests/plugins/conftest.py` | Real editor/parameter staging fixture with mocked external I/O |
| `tests/plugins/test_data_model_rc_calibration.py` | Telemetry, atomic staging, presets, schema and explicit-upload tests |
| `tests/plugins/test_frontend_tkinter_rc_calibration.py` | Channel markers, stick geometry/modes, and embedded telemetry-update tests |
| `tests/plugins/test_renderer_3d_quadcopter.py` | Rotation directions, responsive images, lift, clamping and heading wrapping |

## Requirements Analysis

### Functional Requirements

1. **Live RC Telemetry Display**
   - ✅ Two 126×126 white square stick boxes, each with a red circle of diameter 1/12 of the square side
   - ✅ Centered axes put both circles at the square centers in all four transmitter modes
   - ✅ Mode selector stages all four mapping parameters and immediately remaps the retained raw sample
   - ✅ Direction symbols next to axis labels: yaw/roll ↔, throttle/pitch ↕
   - ✅ Custom mappings are not silently replaced on plugin creation
   - ✅ No flight-mode readout in either view; heartbeat-only polls retain RC display state
   - ✅ Sixteen persistent RC status bars with adjacent PWM labels
   - ✅ Primary-control function labels and edit locks follow staged/cached RCMAP assignments, including custom channels
   - ✅ The configured FLTMODE_CH is labelled Mode and cannot be edited in the channel list
   - ✅ Other editable channels offer the loaded firmware's RCx_OPTION choices; selecting one stages that parameter
   - ✅ Locked auxiliary channels retain their option labels; mapping and edit-lock changes reconcile labels/selectors on refresh
   - ✅ Green MIN, blue TRIM and red MAX markers show configured calibration even before live input
   - ✅ MIN/TRIM/MAX text appears above the CH1 track only; CH2–CH16 retain markers without repetitive text
   - ✅ During calibration, MIN/MAX use observed extremes; TRIM continues to show the configured value
   - ✅ Invalid/missing cached limits use display-only 1000/2000/1500 µs defaults, not parameter writes
   - ✅ Float-valued parameter-cache entries produce visible markers
   - ✅ Shared Live monitor replaces the static Preview Stages image in embedded and popup views
   - ✅ Roll/pitch deflection commands ±35° visual lean; yaw deflection drives 120°/s maximum visual rotation
   - ✅ Centered yaw holds the accumulated heading, with a 4% display deadband
   - ✅ Throttle maps from centered travel -1..1 to visual lift 0..1
   - ✅ No-data/heartbeat-only polls retain the last pose; yaw animation stops after 500 ms without valid RC input
   - ✅ Waiting state displays a neutral example craft without inventing live status
   - ✅ MAVLink `RC_CHANNELS` / `HEARTBEAT` parsing is implemented and covered by data-model tests

2. **Live Monitor Popup**
   - 🟡 Draggable borderless `tk.Toplevel` owned by the `CalibrationPopupBase`/`BaseWindow` wrapper
   - ✅ Custom title bar; popup is non-modal
   - ✅ 100 ms polling via `after()` (no blocking thread)
   - ✅ `_stop_polling()` called on `destroy()` to cancel pending callbacks

3. **Calibration Control**
   - ✅ `start_calibration()` tracks observed channel extremes; `cancel_calibration()` discards them
   - ✅ Explicit finish stages observed `RCn_MIN`, `RCn_MAX`, and midpoint `RCn_TRIM` values in the parameter editor
   - ✅ Missing calibration/mapping rows are added through the existing editor API
   - ✅ Complete batches are validated on copies before mutation; read-only, forced/derived and range constraints are respected
   - ✅ Rejected batches retain prior New values; failed calibration staging retains measurements for retry or cancellation
   - ✅ Repeated preset selection is idempotent and preserves manual-override reason markers
   - ✅ Parameter table refresh uses the shared helper without downloading, saving or uploading
   - ✅ Standalone development monitoring cannot write parameters without a staging editor

4. **Plugin Registration**
   - ✅ `PLUGIN_RC_CALIBRATION` constant in `plugin_constants.py`
   - ✅ `register_rc_calibration_plugin()` wired into `register_plugins()`
   - ✅ model factory registered through `PluginFactory` and invoked by shared parameter-editor dispatch
   - ✅ Schema enum updated in `configuration_steps_schema.json`

### Non-Functional Requirements

1. **Safety**
   - No motor or actuator commands are issued. The plugin never sends parameters directly to the flight controller.
   - Mapping and calibration only edit New values. Upload and readback use the existing parameter-editor workflow.
   - Mapping changes require a controller reboot after upload; the selector tooltip and success status explain this.

2. **Usability**
   - ✅ Draggable popup for flexible screen placement
   - ✅ No-data warning after 50 consecutive empty polls (`_no_telemetry_warning_emitted`)
   - ✅ Disconnected/no-input telemetry does not invent live PWM values; configured/default markers remain visible
   - ✅ Heartbeat-only updates preserve the last channel bars and stick positions
   - ✅ Live monitor, remote controller stick preview and Channels use 4-pixel padding and gaps with no extra scroll-canvas inset
   - ✅ Embedded and popup scrollbar use compact 4-pixel outer margins

3. **Reliability**
   - ✅ `_stop_polling()` prevents dangling `after()` callbacks after widget destruction
   - ✅ MAVLink read exceptions are caught and logged; staging errors are reported in the view

## Data Flow

### Telemetry Polling

```text
RCCalibrationView / RCCalibrationPopup
  └─ after(100 ms) → _check_telemetry()
       └─ model.get_rc_telemetry()
            └─ reads non-blocking RC_CHANNELS / HEARTBEAT messages from the MAVLink master
                 └─ returns roll, pitch, throttle, yaw, flight_mode, and CH1–CH16
                      (invalid or unreported channel values are None)
       ├─ Map RCMAP-selected axes using staged/cached endpoints and reversal to -1000..1000
       │    └─ Mode 1-4 maps axes to two square gimbals; draw circles inside square boundaries
       ├─ Update 16 persistent status bars and numeric PWM labels
       │    └─ draw configured/default MIN/MAX/TRIM; substitute observed MIN/MAX during calibration
       │    └─ update RCMAP/FLTMODE_CH function labels and RCx_OPTION selectors
       └─ craft_preview.update_telemetry(telemetry), including empty and heartbeat-only polls
            ├─ retain latest axes, integrate yaw heading with monotonic elapsed time while RC is fresh
            └─ renderer.render(roll_norm, pitch_norm, heading_degrees, throttle_lift)
                 └─ projected PIL craft → displayed in craft_preview.image_label
```

### Remote Controller Stick Preview Mapping

The two 126×126 stick boxes are 30% smaller than the original 180×180 preview. The selector applies application
mapping presets by editing ArduPilot's `RCMAP_*` parameters
(not `RC_MAP_*`). The presets assume physical channel slots corresponding to a conventional Mode-2
layout: right horizontal CH1, right vertical CH2, left vertical CH3, left horizontal CH4.
That convention is explicitly stated in the tooltip; verify channel movement against the transmitter before upload.
Physical transmitter mode cannot be inferred uniquely from RCMAP: a transmitter can emit any channel order.
Custom assignments remain editable directly in the parameter table and are shown as Custom in the selector.
Their preview uses the last selected physical layout (Mode 2 initially) with the custom channel mapping.
Arbitrary transmitter mixes cannot be reconstructed from four channel inputs.

| Mode | Left horizontal | Left vertical | Right horizontal | Right vertical |
| ---- | --------------- | ------------- | ---------------- | -------------- |
| 1 | Yaw | Pitch | Roll | Throttle |
| 2 | Yaw | Throttle | Roll | Pitch |
| 3 | Roll | Pitch | Yaw | Throttle |
| 4 | Roll | Throttle | Yaw | Pitch |

| Preset | `RCMAP_ROLL` | `RCMAP_PITCH` | `RCMAP_THROTTLE` | `RCMAP_YAW` |
| ------ | ------------ | ------------- | ---------------- | ----------- |
| 1 | 1 | 3 | 2 | 4 |
| 2 | 1 | 2 | 3 | 4 |
| 3 | 4 | 3 | 2 | 1 |
| 4 | 4 | 2 | 3 | 1 |

The registered model factory injects `context.parameter_editor` alongside the flight controller.
Preview calculations overlay current-step New values on a copy of the downloaded FC cache.
Selection does not modify that cache or call `set_param()`. After staging, the frontend refreshes the
New-value table and recomputes axes from the retained raw sample without awaiting another RC packet.

Positive yaw/roll moves the circle right. Positive throttle moves it up. Positive pitch moves it down
(pulling the pitch stick back). Roll/pitch/yaw use the configured neutral trim as center and normalise each
side independently. Throttle uses the endpoint midpoint for physical stick center: `RCn_TRIM` can be at low
throttle and is displayed as a separate marker rather than used as throttle-stick center.
Inputs are clamped to the square's travel range, keeping the entire red circle within its white box.

### Calibration Data Flow

```text
Start Calibration
  └─ clear prior extrema and enable tracking
       └─ each valid RC_CHANNELS sample updates per-channel minimum and maximum
            └─ view renders observed MIN in green and MAX in red; configured TRIM remains blue
Finish Calibration
  └─ validate and stage RCn_MIN / RCn_MAX / RCn_TRIM in ParameterEditor.current_step_parameters
       └─ refresh New values and markers; status asks the user to press parameter upload
Parameter upload (existing editor workflow)
  └─ serialize selected New values and reasons → FlightController.set_param()
       └─ existing reset/reconnect/readback verification workflow
Cancel Calibration
  └─ disable tracking and discard the observed extrema without writing parameters
```

## Renderer Module (`renderer_3d_quadcopter.py`)

`QuadcopterRenderer` is a pure, UI-independent **auxiliary module** specific to the RC calibration plugin.
It projects independently generated Quad-X body/stack faces, arms, motor rings, propellers and a nose marker
from a low rear chase view (17° elevation). Depth-sorted polygons are drawn with Pillow.
Orange front accents, cyan rear accents, a dark background and a fixed floor/shadow provide direction and lift cues.
No Three.js, OpenGL context, GLTF files or new dependency is needed.

The visual behavior was compared with the local `arduconfigurator` receiver monitor:

- `apps/web/src/sections/ReceiverSection.tsx`: compact live craft card beside channel bars
- `apps/web/src/preview-components.tsx`: `StickCraftPreview` calibrated lean, yaw-rate integration and throttle lift
- `apps/web/src/flight-deck-preview.tsx`: low rear chase camera and compact craft styling

This is a Tk/Pillow analogue, not a copy of its Three.js renderer or a full Receiver workbench port.
The existing vertically stacked plugin layout is preserved. Only the Preview Stages section is replaced.

`RCCraftPreview` retains axes and heading, renders on the existing 100 ms polling loop, and uses monotonic time
for yaw integration. Elapsed time is capped at 250 ms to prevent large jumps after UI delays.
RC freshness expires after 500 ms; heartbeat packets do not refresh it. There is no additional timer or thread.
Destroying the embedded view/popup cancels the existing polling timer.

### API

```python
renderer = QuadcopterRenderer(width=400, height=200)
img: PIL.Image.Image = renderer.render(roll, pitch, yaw_heading_degrees, throttle_lift)
# roll/pitch normalised -1.0 … 1.0; heading degrees; throttle lift 0.0 … 1.0
```

## Validation Notes

- Unit tests cover telemetry, bounds, extrema tracking, cancellation, all four mapping presets,
  protected/range-invalid batches, missing rows, manual overrides, idempotency and explicit-upload integration.
- Tk tests cover all 16 rows, float-valued MIN/MAX/TRIM markers, two white squares, centered circles,
  the 1/12 diameter ratio, all four stick modes, staged combobox changes, direction symbols,
  finish-button staging, custom-mapping errors, table refresh and heartbeat-only telemetry updates.
- Channel tests cover custom staged/cached mapping protection, the locked FLTMODE_CH row, metadata-driven RCx_OPTION choices,
  locked auxiliary labels, live label/selector transitions, manual overrides, adding missing option rows, and staging without FC writes.
- Tests verify all four axis arrows, marker colors, CH1-only labels above the track, retained craft pose,
  live/no-data status, yaw rate/deadband/stale-input behavior and pure renderer rotation directions.
- Layout tests verify compact margins, section padding, right-aligned scrollbar and removal of the flight-mode readout.
- The embedded view is instantiated with a real Tk widget hierarchy to verify initial markers and polling updates.
- The plugin is registered globally, but a configuration step must reference `rc_calibration` for the view to appear;
  both `*mig` templates now provide step wiring and editable mapping entries.
- The empty migration template previously inherited the package step JSON. Its new local JSON preserves that
  definition except for the RC controller step, which now includes the plugin and mapping declarations.
- Existing migrated projects acquire missing RCMAP rows from current FC values when the controller step opens;
  filename/format migration does not invent mapping defaults or overwrite custom mappings.
- No live flight-controller or SITL validation is claimed; the craft remains an illustrative Quad-X rather than measured attitude.
- New UI strings use gettext. Catalog regeneration requires `pygettext3`, which is absent in this environment.

## Popup Window (`RCCalibrationPopup`)

`RCCalibrationPopup` inherits `CalibrationPopupBase`, which owns a transient `tk.Toplevel` through `BaseWindow`.
It shares the same telemetry polling loop and widgets as
`RCCalibrationView` but is designed to float above the main AMC window.

**Key design points:**

- `overrideredirect(True)` removes the OS title bar; a custom tkinter frame acts as the
  drag handle.
- `transient(parent)` keeps the popup above its owner window.
- The popup is intentionally non-modal so the user can continue interacting with the main AMC window while monitoring RC input.
- `_start_move` / `_do_move` bindings on the title bar implement drag-to-move via
  `winfo_x()` + event delta.
- `_stop_polling()` cancels the `after()` job before the owned window is destroyed to prevent
  callbacks firing on a destroyed widget.

## Mission Planner Reference

The RC calibration protocol in ArduPilot uses the standard `RC_CHANNELS` MAVLink message
for telemetry and `PARAM_SET` / `PARAM_VALUE` for storing trim values
(`RCn_TRIM`, `RCn_MIN`, `RCn_MAX`, `RCn_REVERSED`).  See:

- <https://mavlink.io/en/messages/common.html#RC_CHANNELS>
- <https://ardupilot.org/copter/docs/common-radio-control-calibration.html>

### Verified Mapping Parameter Reference

The upstream [ArduCopter 4.6.3 RCMapper implementation](https://github.com/ArduPilot/ardupilot/blob/Copter-4.6.3/libraries/AP_RCMapper/AP_RCMapper.cpp)
defines roll/pitch/throttle/yaw mapping defaults 1/2/3/4, range 1–16, and `RebootRequired: True`.
This verifies availability for the migration templates' 4.6.x firmware target; no new version gate is introduced.
The physical-slot presets above are application conventions, not ArduPilot-defined transmitter mode parameters.
