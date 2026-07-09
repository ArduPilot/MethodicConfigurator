# Accelerometer Calibration Plugin Architecture

## Overview

The Accelerometer Calibration plugin allows users to calibrate the flight controller's
accelerometers directly from within the ArduPilot Methodic Configurator (AMC), without
switching to Mission Planner or another GCS.
It follows the same Model-View separation pattern used by the Battery Monitor and Motor
Test plugins.

**Key Features:**

- Three calibration modes: Simple (one-shot), Level trim, and Full 6-position
- Interactive 6-position wizard with non-blocking tkinter polling (`after()`)
- All MAVLink communication delegated to `backend_flightcontroller_commands.py`
- Integrated at the accelerometer calibration configuration step

## Architecture

### Component Layers

```text
┌──────────────────────────────────────────────────────────────────┐
│ GUI Layer (frontend_tkinter_accelerometer_calibration.py)        │
│ - Three calibration buttons (Simple / Level / Full)              │
│ - 6-position wizard panel (hidden until full cal is active)      │
│ - Non-blocking 100 ms polling via tkinter after()                │
│ - Position instructions label + Continue / Cancel buttons        │
└───────────────────────────┬──────────────────────────────────────┘
                            │
┌───────────────────────────▼──────────────────────────────────────┐
│ Data Model (data_model_accelerometer_calibration.py)             │
│ - Three start_*_calibration() entry points                       │
│ - poll_for_next_position() / confirm_current_position()          │
│ - POSITION_LABELS dict (human-readable instructions)             │
│ - Tracks _current_position state across the protocol exchange    │
└───────────────────────────┬──────────────────────────────────────┘
                            │
┌───────────────────────────▼──────────────────────────────────────┐
│ FlightController facade (backend_flightcontroller.py)            │
│ - Thin delegation wrappers for all five methods below            │
└───────────────────────────┬──────────────────────────────────────┘
                            │
┌───────────────────────────▼──────────────────────────────────────┐
│ Commands Backend (backend_flightcontroller_commands.py)          │
│ - start_accel_calibration_simple()    param5=4, with ACK wait    │
│ - start_accel_calibration_level()     param5=2, with ACK wait    │
│ - send_accel_calibration_full_start() param5=1, fire-and-return  │
│ - poll_accel_cal_vehicle_pos()        recv_match COMMAND_LONG    │
│ - confirm_accel_vehicle_pos()         send COMMAND_LONG reply    │
└──────────────────────────────────────────────────────────────────┘
```

### MAVLink Protocol

All three modes use
[`MAV_CMD_PREFLIGHT_CALIBRATION`](https://mavlink.io/en/messages/common.html#MAV_CMD_PREFLIGHT_CALIBRATION)
(command ID 241).  The `param5` field selects the calibration type:

| param5 | Mode | Interaction |
| ------ | ---- | ----------- |
| `4` | **Simple** — one-shot level calibration (`AP_InertialSensor::simple_accel_cal`) | None — wait for `COMMAND_ACK` |
| `2` | **Level trim** — sets `AHRS_TRIM_*` to current attitude | None — wait for `COMMAND_ACK` |
| `1` | **Full 6-position** — interactive multi-step calibration | Bidirectional `COMMAND_LONG` exchange |

The full 6-position protocol (param5=1) uses a secondary command:

| Message direction | Command | Content |
| ----------------- | ------- | ------- |
| FC → GCS | `COMMAND_LONG` cmd=42429 (`MAV_CMD_ACCELCAL_VEHICLE_POS`) | param1 = requested position (1–6) |
| GCS → FC | `COMMAND_LONG` cmd=42429 | param1 = same position value (confirmation) |
| FC → GCS (end) | param1 = 16777215 (success) or 16777216 (failed) | Calibration result |

Position enum values (`ACCELCAL_VEHICLE_POS_*`):

| Value | Name | Instruction |
| ----- | ---- | ----------- |
| 1 | `LEVEL` | Place vehicle LEVEL |
| 2 | `LEFT` | Place vehicle on its LEFT side |
| 3 | `RIGHT` | Place vehicle on its RIGHT side |
| 4 | `NOSEDOWN` | Place vehicle NOSE DOWN |
| 5 | `NOSEUP` | Place vehicle NOSE UP |
| 6 | `BACK` | Place vehicle on its BACK |
| 16777215 | `SUCCESS` | Calibration succeeded |
| 16777216 | `FAILED` | Calibration failed |

### Data Model (`data_model_accelerometer_calibration.py`)

**Responsibilities:** Calibration mode selection, protocol state tracking, backend delegation, position label lookup.

**Key Methods:**

| Method | Description |
| ------ | ----------- |
| `is_connected()` | Guard — checks `flight_controller.master is not None` |
| `start_simple_calibration()` | Calls `start_accel_calibration_simple()`, blocks until ACK |
| `start_level_calibration()` | Calls `start_accel_calibration_level()`, blocks until ACK |
| `start_full_calibration()` | Calls `send_accel_calibration_full_start()`, returns immediately |
| `poll_for_next_position()` | Thin wrapper around `poll_accel_cal_vehicle_pos()` |
| `get_position_label(pos)` | Looks up `POSITION_LABELS[pos]` |
| `confirm_current_position()` | Calls `confirm_accel_vehicle_pos(_current_position)` |

**State:**

- `_current_position: int | None` — last `ACCELCAL_VEHICLE_POS` value received from the FC;
  set by `poll_for_next_position()`, consumed by `confirm_current_position()`.

### Commands Backend (`backend_flightcontroller_commands.py`)

**Constants** (all available in `mavutil.mavlink` from pymavlink):

```python
mavutil.mavlink.MAV_CMD_ACCELCAL_VEHICLE_POS    # = 42429
mavutil.mavlink.ACCELCAL_VEHICLE_POS_LEVEL      # = 1
mavutil.mavlink.ACCELCAL_VEHICLE_POS_LEFT       # = 2
mavutil.mavlink.ACCELCAL_VEHICLE_POS_RIGHT      # = 3
mavutil.mavlink.ACCELCAL_VEHICLE_POS_NOSEDOWN   # = 4
mavutil.mavlink.ACCELCAL_VEHICLE_POS_NOSEUP     # = 5
mavutil.mavlink.ACCELCAL_VEHICLE_POS_BACK       # = 6
mavutil.mavlink.ACCELCAL_VEHICLE_POS_SUCCESS    # = 16777215
mavutil.mavlink.ACCELCAL_VEHICLE_POS_FAILED     # = 16777216
```

**Simple and level modes** use `send_command_and_wait_ack()` (existing shared helper) with
timeouts of 30 s and 15 s respectively, relying on the standard `COMMAND_ACK` response.

**Full calibration** cannot use `send_command_and_wait_ack()` because the final ACK only
arrives after the complete 6-position exchange (potentially minutes later).  Instead:

- `send_accel_calibration_full_start()` sends the `COMMAND_LONG` and returns immediately.
- `poll_accel_cal_vehicle_pos()` calls `master.recv_match(type="COMMAND_LONG", blocking=False)` and filters on `msg.command == 42429`.
- `confirm_accel_vehicle_pos(position)` sends `COMMAND_LONG` with `cmd=42429` and `param1=position` back to the FC.

### GUI Layer (`frontend_tkinter_accelerometer_calibration.py`)

**Responsibilities:** Button layout, wizard state machine, non-blocking polling, user feedback.

**Key design points:**

- The **wizard panel** (`_wizard_frame`) is hidden at startup and shown only when full
  calibration begins.  While it is visible the three top-level buttons are disabled to
  prevent concurrent calibration commands.
- A **100 ms `after()` poll loop** (`_poll_tick`) replaces a blocking thread.  It calls
  `model.poll_for_next_position()` and either reschedules itself (no message yet), enables
  the **Continue** button (new position requested), or ends the wizard (success/failure).
- The **Continue** button is disabled between positions (while the FC is sampling) and
  re-enabled only when a new `ACCELCAL_VEHICLE_POS` message arrives.
- `_stop_polling()` is called from `on_deactivate()` and `destroy()` to cancel any
  pending `after()` job and prevent dangling callbacks after the plugin is hidden or removed.

## Data Flow

### Simple / Level Calibration

```text
User clicks button
  → model.start_simple_calibration() / start_level_calibration()
    → flight_controller.start_accel_calibration_simple/level()
      → FlightControllerCommands.send_command_and_wait_ack(241, param5=4/2)
        → MAVLink COMMAND_LONG sent to FC
        → Wait for COMMAND_ACK (MAV_RESULT_ACCEPTED)
      → returns (True, "")
    → returns (True, "Calibration successful")
  → showinfo(...)
```

### Full 6-Position Calibration

```text
User clicks "Full Calibration (6-Position)"
  → model.start_full_calibration()
    → FlightControllerCommands.send_accel_calibration_full_start()
      → MAVLink COMMAND_LONG (cmd=241, param5=1) sent to FC
      → returns immediately (True, "")
  → wizard panel shown, polling starts

  ── 100 ms poll tick ──────────────────────────────────────────────
  │  model.poll_for_next_position()
  │    → FlightControllerCommands.poll_accel_cal_vehicle_pos()
  │      → recv_match(COMMAND_LONG) from FC
  │        if cmd==42429 → return int(param1)   ← position (1–6)
  │  position_label updated; Continue button enabled
  ──────────────────────────────────────────────────────────────────

  User places vehicle in position; clicks Continue
  → model.confirm_current_position()
    → FlightControllerCommands.confirm_accel_vehicle_pos(position)
      → MAVLink COMMAND_LONG (cmd=42429, param1=position) sent to FC
  → Continue button disabled; position label set to "Waiting..."
  → polling resumes

  (repeat for all 6 positions)

  FC sends COMMAND_LONG cmd=42429, param1=16777215 (SUCCESS)
    or param1=16777216 (FAILED)
  → _end_full_calibration(success=True/False)
  → wizard hidden; top-level buttons re-enabled; showinfo/showerror
```

## Mission Planner Reference

Mission Planner implements the same protocol in its accelerometer calibration screen.
The following source files are the authoritative reference:

- **`GCSViews/ConfigurationView/Setup/Accel.cs`** — the accelerometer calibration UI screen
  (search for `PREFLIGHT_CALIBRATION` and `ACCELCAL_VEHICLE_POS`):
  <https://github.com/ArduPilot/MissionPlanner/search?q=ACCELCAL_VEHICLE_POS>

- **`MAVLink.cs`** — MAVLink message definitions and enum values including
  `MAV_CMD.ACCELCAL_VEHICLE_POS` and `MAV_CMD.PREFLIGHT_CALIBRATION`:
  <https://github.com/ArduPilot/MissionPlanner/blob/master/ExtLibs/Mavlink/MAVLink.cs>

- **ArduPilot firmware `AP_AccelCal.cpp`** — firmware side of the protocol; sends the
  per-position `COMMAND_LONG` requests and the final SUCCESS/FAILED signals:
  <https://github.com/ArduPilot/ardupilot/blob/master/libraries/AP_AccelCal/AP_AccelCal.cpp>

- **ArduPilot firmware `GCS_Common.cpp`** — parses the incoming `PREFLIGHT_CALIBRATION`
  command (param5 dispatch) and sends `send_accelcal_vehicle_position()`:
  <https://github.com/ArduPilot/ardupilot/blob/master/libraries/GCS_MAVLink/GCS_Common.cpp>

- **MAVLink common message set** — `MAV_CMD_PREFLIGHT_CALIBRATION` definition and param
  documentation:
  <https://mavlink.io/en/messages/common.html#MAV_CMD_PREFLIGHT_CALIBRATION>

## Integration

- **Configuration Step:** Accelerometer calibration `.param` file (vehicle type dependent)
- **Plugin Name Constant:** `PLUGIN_ACCELEROMETER_CALIBRATION` in `plugin_constants.py`
- **Plugin Registration:** `register_accelerometer_calibration_plugin()` called from `__main__.register_plugins()`
- **Data Model Construction:** `create_plugin_data_model()` in `data_model_parameter_editor.py`
- **FC Connection Required:** Plugin creation returns `None` when `is_fc_connected` is False

## Design Decisions

- **param5 values are not symmetric:** `4` = simple, `2` = level, `1` = full.
  This ordering comes directly from ArduPilot firmware (`GCS_Common.cpp`) and Mission
  Planner, not from any logical sequence.
- **Full calibration uses fire-and-return:** `send_accel_calibration_full_start()` does
  not wait for `COMMAND_ACK` because the final ACK only arrives after the user completes
  all six positions (minutes of interaction).  The end-of-calibration is signalled by
  `ACCELCAL_VEHICLE_POS_SUCCESS` (16777215) or `ACCELCAL_VEHICLE_POS_FAILED` (16777216)
  in a `COMMAND_LONG` message.
- **`after()` polling instead of a background thread:** Keeps all UI updates on the
  tkinter main thread, eliminates thread-safety concerns, and integrates cleanly with
  the plugin lifecycle (`on_deactivate` / `destroy` simply cancel the pending job).
- **Wizard panel hidden by default:** Avoids UI clutter; only appears when interactive
  calibration is in progress.
- **Constants defined in `mavutil.mavlink`:** All `ACCELCAL_VEHICLE_POS_*` values and
  `MAV_CMD_ACCELCAL_VEHICLE_POS` are part of pymavlink's generated MAVLink bindings.
  The data model imports them directly from `pymavlink.mavutil.mavlink`, keeping the
  code free of duplicated magic numbers.
