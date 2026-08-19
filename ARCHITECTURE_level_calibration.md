# Level Calibration Sub-application Architecture

## Overview

The Level Calibration plugin applies ArduPilot's one-shot level trim to the
current vehicle attitude. It is intentionally separate from the accelerometer
calibration wizard: level trim updates `AHRS_TRIM_*`, while accelerometer
calibration measures sensor offsets and scale.

## Components

```text
User
  │
  ▼
frontend_tkinter_level_calibration.py
  │  button event and success/error dialogs
  ▼
data_model_level_calibration.py
  │  connection guard and result translation
  ▼
backend_flightcontroller.py
  │
  ▼
backend_flightcontroller_commands.py
  │  MAV_CMD_PREFLIGHT_CALIBRATION, param5=2
  ▼
Flight controller
```

### Data model

`LevelCalibrationDataModel.start_level_calibration()`:

1. Rejects the operation when no flight-controller master is connected.
2. Starts the command through `FlightController.start_accel_calibration_level()` without waiting.
3. `poll_level_calibration()` delegates one non-blocking ACK poll and translates the eventual result.

### View

`LevelCalibrationView` presents the level-trim button and explains that the
vehicle must be calibrated, stationary, and level. On success it refreshes the
parameter editor; on failure it shows an error dialog. The button is disabled
while the command is active, and a second click is ignored.

The view polls with Tk `after()` callbacks while the command is active. This
keeps the interface responsive during the 45-second ACK window and cooldown
retries. Pending callbacks are cancelled when the view is destroyed, and the
button is restored only while its widget still exists.

## Safety and behavior

- The vehicle must be stationary on a level surface before starting.
- The operation trims roll and pitch only; it does not change yaw.
- The command waits up to 45 seconds for the flight-controller acknowledgement.
  This margin covers the firmware gyro-convergence path, which can exceed 30
  seconds.
- A temporary `MAV_RESULT_TEMPORARILY_REJECTED` is retried after the firmware's
  five-second cooldown, up to nine retries (45 seconds of cooldown waits).
  Each attempt has a 45-second ACK timeout. Other command results are not
  automatically retried; in particular, an armed-vehicle failure is not retried.
- A failed `COMMAND_ACK` is followed by a 0.5-second receive grace window so
  queued `STATUSTEXT` messages sent after the ACK are included in the error
  message, preserving firmware diagnostics such as the disarm requirement.
- After success, the editor downloads fresh FC parameters and copies
  `AHRS_TRIM_X` and `AHRS_TRIM_Y` only if they are part of the active
  configuration step. When another project step contains a different saved
  trim value, the result dialog names that step for the user to review.
  No other project step or parameter file is changed automatically.

### Calibration sequence

```text
User clicks Level Calibration
  → disable button and call the calibration model
  → send MAV_CMD_PREFLIGHT_CALIBRATION (param5=2) without waiting
  → poll the ACK every 100 ms using Tk after() callbacks
  → retry temporary rejections after five seconds (at most nine retries)
  → on success: download FC parameters, stage active-step trims, identify stale steps, refresh table
  → display success/failure dialog and restore the button if it still exists
```

## Source and tests

- Model: `ardupilot_methodic_configurator/plugins/data_model_level_calibration.py`
- View: `ardupilot_methodic_configurator/plugins/frontend_tkinter_level_calibration.py`
- Tests: `tests/plugins/test_data_model_level_calibration.py` and
  `tests/plugins/test_frontend_tkinter_level_calibration.py`
