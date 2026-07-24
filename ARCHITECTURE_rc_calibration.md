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

- Live RC telemetry display: stick positions (roll/pitch/throttle/yaw), flight mode, raw channels
- 100 ms non-blocking polling via tkinter `after()` — same pattern as accelerometer calibration
- Floating, draggable live-monitor popup (`RCCalibrationPopup`) for real-time feedback
- Stick preview using `ttk.Progressbar` bars mapped from the ±1000 µs PWM range to 0–100 %
- 3D vehicle attitude visualisation delegated to `renderer_3d_quadcopter.py`
- Embedded plugin view (`RCCalibrationView`) + standalone dev window (`RCCalibrationWindow`)

> **Note:** The data model is currently a stub that returns dummy data.
> MAVLink integration (`RC_CHANNELS` / `HEARTBEAT` messages) is planned for a future commit.

## Architecture

### Component Layers

```text
┌────────────────────────────────────────────────────────────────────┐
│ GUI Layer (frontend_tkinter_rc_calibration.py)                     │
│                                                                    │
│ ┌──────────────────────────────────────────────────────────────┐   │
│ │ RCCalibrationView (ttk.Frame) — embedded in parameter editor │   │
│ │  - Stick preview progress bars (ROLL / PITCH / THROTTLE / YAW│   │
│ │  - Flight mode label                                         │   │
│ │  - Channel value list                                        │   │
│ │  - 100 ms after() poll → get_rc_telemetry()                  │   │
│ └──────────────────────────────────────────────────────────────┘   │
│                                                                    │
│ ┌──────────────────────────────────────────────────────────────┐   │
│ │ RCCalibrationPopup (tk.Toplevel) — floating draggable window │   │
│ │  - Borderless, transient, grab_set()                         │   │
│ │  - Custom title bar with drag-to-move                        │   │
│ │  - Same stick / mode / channel widgets as the embedded view  │   │
│ │  - 3D attitude preview via QuadcopterRenderer                │   │
│ │  - 100 ms after() poll → get_rc_telemetry()                  │   │
│ └──────────────────────────────────────────────────────────────┘   │
│                                                                    │
│ RCCalibrationWindow (BaseWindow) — standalone dev/test window      │
└─────────────────────────────┬──────────────────────────────────────┘
                              │
┌─────────────────────────────▼──────────────────────────────────────┐
│ Optional Renderer (renderer_3d_quadcopter.py)                      │
│ - QuadcopterRenderer: renders a PIL Image from roll/pitch/yaw/     │
│   throttle inputs                                                  │
│ - Currently a PIL-based stub (real OpenGL rendering is TODO)       │
└────────────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────▼──────────────────────────────────────┐
│ Data Model (data_model_rc_calibration.py)                          │
│ - RCCalibrationDataModel                                           │
│ - start_calibration() / cancel_calibration() / finish_calibration()│
│ - get_rc_telemetry() → dict with roll/pitch/throttle/yaw/          │
│   flight_mode/channels                                             │
│ - Currently returns dummy data; MAVLink integration is TODO        │
└─────────────────────────────┬──────────────────────────────────────┘
                              │
┌─────────────────────────────▼──────────────────────────────────────┐
│ FlightController facade (backend_flightcontroller.py)              │
│ - (Integration not yet wired — planned for future commits)         │
└────────────────────────────────────────────────────────────────────┘
```

### File Map

| File | Role |
| ------ | ------ |
| `plugin_constants.py` | `PLUGIN_RC_CALIBRATION = "rc_calibration"` |
| `data_model_rc_calibration.py` | Business logic + stub telemetry |
| `frontend_tkinter_rc_calibration.py` | `RCCalibrationPopup`, `RCCalibrationView`, `RCCalibrationWindow`, factory & registration |
| `renderer_3d_quadcopter.py` | `QuadcopterRenderer` — PIL-based 3D stub |
| `__main__.py` | `register_plugins()` wires `register_rc_calibration_plugin()` |
| `data_model_parameter_editor.py` | `create_plugin_data_model()` instantiates `RCCalibrationDataModel` |
| `configuration_steps_schema.json` | `"rc_calibration"` added to plugin name enum |

## Requirements Analysis

### Functional Requirements

1. **Live RC Telemetry Display**
   - 🟡 Stick position progress bars (ROLL, PITCH, THROTTLE, YAW) mapped ±1000 µs → 0–100 %
   - 🟡 Current flight mode label
   - 🟡 Per-channel PWM value list (CH1–CH8+)
   - 🟡 3D attitude preview (PIL stub; real rendering TODO)
   - ❌ MAVLink `RC_CHANNELS` / `HEARTBEAT` message parsing

2. **Live Monitor Popup**
   - ✅ Draggable borderless `tk.Toplevel` window
   - ✅ Custom title bar with `grab_set()` modal behaviour
   - ✅ 100 ms polling via `after()` (no blocking thread)
   - ✅ `_stop_polling()` called on `destroy()` to cancel pending callbacks

3. **Calibration Control**
   - 🟡 `start_calibration()` / `cancel_calibration()` / `finish_calibration()` stubs
   - ❌ MAVLink `RC_CHANNELS_RAW` trim / deadzone calibration protocol

4. **Plugin Registration**
   - ✅ `PLUGIN_RC_CALIBRATION` constant in `plugin_constants.py`
   - ✅ `register_rc_calibration_plugin()` wired into `register_plugins()`
   - ✅ `create_plugin_data_model()` branch in `data_model_parameter_editor.py`
   - ✅ Schema enum updated in `configuration_steps_schema.json`

### Non-Functional Requirements

1. **Safety**
   - No motor or actuator commands are issued; display-only plugin

2. **Usability**
   - ✅ Draggable popup for flexible screen placement
   - ✅ No-data warning after 50 consecutive empty polls (`_no_telemetry_warning_emitted`)
   - ✅ Graceful degradation when not connected (data model returns stub data)

3. **Reliability**
   - ✅ `_stop_polling()` prevents dangling `after()` callbacks after widget destruction
   - 🟡 Error handling for MAVLink communication (planned)

## Data Flow

### Telemetry Polling (Current Stub)

```text
RCCalibrationView / RCCalibrationPopup
  └─ after(100 ms) → _check_telemetry()
       └─ model.get_rc_telemetry()
            └─ returns dict {roll, pitch, throttle, yaw, flight_mode, channels}
                 (stub: always returns dummy 1500 µs values)
       ├─ Update stick progress bars (±1000 → 0–100 %)
       ├─ Update flight mode label
       ├─ Rebuild channel list widgets
       └─ renderer.render(roll_norm, pitch_norm, yaw_norm, throttle_norm)
            └─ returns PIL.Image → displayed in preview_label
```

### Planned MAVLink Integration

```text
RCCalibrationDataModel.get_rc_telemetry()
  └─ flight_controller.master.recv_match(type="RC_CHANNELS", blocking=False)
       └─ parse chan1_raw … chan18_raw (µs PWM values)
  └─ flight_controller.master.recv_match(type="HEARTBEAT", blocking=False)
       └─ parse custom_mode → flight mode string
```

## Renderer Module (`renderer_3d_quadcopter.py`)

`QuadcopterRenderer` is an **optional auxiliary module** specific to the RC calibration
plugin.  Other plugins do not have a dedicated renderer; this pattern was introduced here
for future 3D attitude visualisation.

**Current implementation:** PIL-based stub that draws a schematic quadcopter shape
(rectangle body + four arm lines) ignoring the attitude inputs.

**Planned implementation:** Off-screen OpenGL rendering capturing the framebuffer into a
`PIL.Image` to show real roll/pitch/yaw attitude.

### API

```python
renderer = QuadcopterRenderer(width=400, height=200)
img: PIL.Image.Image = renderer.render(roll, pitch, yaw, throttle)
# roll/pitch/yaw in normalised range -1.0 … 1.0; throttle 0.0 … 1.0
```

## Popup Window (`RCCalibrationPopup`)

`RCCalibrationPopup` is a `tk.Toplevel` subclass that provides an always-on-top,
draggable monitoring window.  It shares the same telemetry polling loop and widgets as
`RCCalibrationView` but is designed to float above the main AMC window.

**Key design points:**

- `overrideredirect(True)` removes the OS title bar; a custom tkinter frame acts as the
  drag handle.
- `transient(parent)` keeps the popup above its owner window.
- `grab_set()` makes it modal (keyboard/mouse focus stays in the popup).
- `_start_move` / `_do_move` bindings on the title bar implement drag-to-move via
  `winfo_x()` + event delta.
- `_stop_polling()` cancels the `after()` job before `super().destroy()` to prevent
  callbacks firing on a destroyed widget.

## Mission Planner Reference

The RC calibration protocol in ArduPilot uses the standard `RC_CHANNELS` MAVLink message
for telemetry and `PARAM_SET` / `PARAM_VALUE` for storing trim values
(`RCn_TRIM`, `RCn_MIN`, `RCn_MAX`, `RCn_REVERSED`).  See:

- <https://mavlink.io/en/messages/common.html#RC_CHANNELS>
- <https://ardupilot.org/copter/docs/common-radio-control-calibration.html>
