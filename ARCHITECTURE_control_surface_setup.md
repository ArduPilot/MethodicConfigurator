# Control Surface Setup Plugin Architecture

## Overview

The control surface setup plugin guides the user through setting up the physical
flight controls of a plane, and the tilt servos of a tilt-rotor QuadPlane. It is
shown in the ArduPlane step `23_general_configuration.param`, placed on the left.

It assumes that the RC inputs, the flight controller orientation and the servo
output functions are already set up in earlier steps. It needs a connected flight
controller and battery power for the servos.

Every adjustment is written to the flight controller immediately, so the surfaces
move while the user edits them. **Save to flight controller** reads each live
value back from the FC to check it. It then stages the value, with a change
reason, in the current configuration step so the project files record it.

References:

- [Four channel plane setup](https://ardupilot.org/plane/docs/guide-four-channel-plane.html)
- [QuadPlane tips: tilt-rotor setup](https://ardupilot.org/plane/docs/quadplane-tips.html#tilt-rotor-setup)
- [Tilt-rotor guide](https://ardupilot.org/plane/docs/guide-tilt-rotor.html)
- Tilt output scaling: [ArduPlane tiltrotor.cpp (Plane-4.6.0)](https://github.com/ArduPilot/ardupilot/blob/Plane-4.6.0/ArduPlane/tiltrotor.cpp)

## Components

```text
User
  │
  ▼
plugins/frontend_tkinter_control_surface_setup.py   notebook view, timers, dialogs
  │
  ▼
plugins/data_model_control_surface_setup.py         validation, live writes, save/staging
  ├── plugins/backend_servo_telemetry.py            SERVO_OUTPUT_RAW + HEARTBEAT reader
  ├── plugins/data_model_battery_monitor.py         servo supply voltage (BATT_ARM_VOLT check)
  ├── backend_flightcontroller.py                   set_param, fetch_param, set_flight_mode,
  │                                                 send_rc_channels_override, request_servo_output_messages
  └── data_model_parameter_editor.py                stage saved values in the current step
```

## Workflow (one notebook tab per stage)

| Tab | Mode | Adjusts | User action |
| --- | --- | --- | --- |
| 1. Servo direction | FBWA | `SERVOx_REVERSED` | Move the airframe by hand. Surfaces must oppose the motion |
| 2. Stick direction | FBWA | `RCx_REVERSED` for the `RCMAP_ROLL/PITCH/YAW` channels | Move the transmitter sticks |
| 3. Trim and travel | MANUAL | `SERVOx_TRIM`, `SERVOx_MIN`, `SERVOx_MAX` | Trim with sticks centred. Use the sliders to drive the surfaces to their limits |
| 4. Tilt rotors (`Q_TILT_ENABLE=1` only) | MANUAL / QSTABILIZE | `Q_TILT_TYPE`, `Q_TILT_YAW_ANGLE`, `Q_TILT_FIX_ANGLE`, tilt `SERVOx_REVERSED/MIN/MAX` | Point the motors forward (MANUAL) and vertical (QSTABILIZE) |

Primary flight-control functions: 4 Aileron, 19 Elevator, 21 Rudder,
77/78 Elevon left/right, 79/80 V-tail left/right. Tilt functions: 41, 45, 46,
47, 75 and 76. Several outputs can share a function, for example one per
aileron.

### Safety and preconditions

- A mode switch is refused unless the battery voltage is above `BATT_ARM_VOLT`.
- The tilt tab requires `Q_TILT_MASK > 0` and at least one tilt servo output.
- A warning is shown when `KFF_RDDRMIX = 0`. With that setting the rudder does
  not respond when the plane is rolled in FBWA.
- A warning is shown when `MAV_GCS_SYSID`/`SYSID_MYGCS` is not 255, AMC's MAVLink
  system ID. The FC ignores RC overrides from any other GCS ID.
- A warning is shown when a trim is more than 50 µs from 1500 µs. The fix is a
  mechanical adjustment.
- Values are range-checked against the firmware metadata, defaulting to
  500–2200 µs. For control surfaces, `MIN <= TRIM <= MAX` must hold. For tilt
  servos, `MIN < MAX` must hold.

### Simulated stick input

The sliders send `RC_CHANNELS_OVERRIDE` messages for the roll, pitch and yaw
channels. Each slider position is scaled with the channel's `RCx_MIN/TRIM/MAX`.
The FC discards overrides after `RC_OVERRIDE_TIME`, so while any override is
active the view resends it every 300 ms. A slider stays where the user leaves
it. Each slider has a **Center** button. **Center all** (also Esc on a slider)
recentres every stick, and **Release to transmitter** sends the release values
(0 for channels 1–8, 65534 for channels 9–18).

### Tilt end points

ArduPlane scales the tilt output from 0 (vertical) to 1 (forward) across
`SERVOx_MIN..MAX`. A servo that is not reversed is therefore vertical at MIN
and forward at MAX. `SERVOx_REVERSED` swaps the two ends, and so does
`Q_TILT_TYPE = 3` (Bicopter), where MIN is horizontal. The view highlights the
end point that is expected to set each position. The user still sees which
parameter it is and can adjust it directly.

## Lifecycle

- `on_activate`: starts a 100 ms telemetry poll (servo PWM and flight mode) and
  a 1 s battery check.
- `on_deactivate` / `destroy`: cancels the timers and releases the overrides. It
  also restores the flight mode that was active before the plugin changed it,
  and restores the default `SERVO_OUTPUT_RAW` stream interval.
- `on_suspend(EXCLUSIVE_OPERATION)`: stops the timers and releases the
  overrides. `on_suspend(CONNECTION_RECOVERY)` only stops the timers and sends
  no commands. `on_resume` restarts polling but does not resend stick input.

Parameters marked `RebootRequired` in the metadata are listed after a save,
with a request to reboot the flight controller.

## Source and tests

- Model: `ardupilot_methodic_configurator/plugins/data_model_control_surface_setup.py`
- View: `ardupilot_methodic_configurator/plugins/frontend_tkinter_control_surface_setup.py`
- Telemetry: `ardupilot_methodic_configurator/plugins/backend_servo_telemetry.py`
- Tests: `tests/plugins/test_data_model_control_surface_setup.py`,
  `tests/plugins/test_frontend_tkinter_control_surface_setup.py` and
  `TestControlSurfaceSetupCommands` in `tests/test_backend_flightcontroller_commands.py`
