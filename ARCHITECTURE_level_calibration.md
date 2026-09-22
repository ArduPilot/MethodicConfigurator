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
2. Delegates to `FlightController.start_accel_calibration_level()`.
3. Returns a localized success or failure message.

### View

`LevelCalibrationView` presents the level-trim button and explains that the
vehicle must be calibrated, stationary, and level. The calibration and
parameter readback run in a worker so the Tk event loop remains responsive. A
Cancel button in the modal progress dialog sends the flight-controller abort
command and prevents parameter readback. On success it refreshes the parameter
editor; on failure it shows an error dialog.

## Concurrency

The view marks the shared `BaseWindow` flight-controller operation lock busy
before starting the worker and releases it only after the worker has finished.
The backend uses the connection manager's re-entrant `mavlink_transaction` for
command acknowledgements, telemetry readers, parameter reads, and MAVFTP
response processing because all of them consume the same MAVLink receive queue.
If the view is destroyed while a worker is still waiting, the modal window is
closed but the busy state remains until a Tk callback observes that the worker
has ended.

## Safety and behavior

- The vehicle must be stationary on a level surface before starting.
- The operation trims roll and pitch only; it does not change yaw.
- The command waits for the flight-controller acknowledgement before reporting
  success.

## Source and tests

- Model: `ardupilot_methodic_configurator/plugins/data_model_level_calibration.py`
- View: `ardupilot_methodic_configurator/plugins/frontend_tkinter_level_calibration.py`
- Tests: `tests/plugins/test_data_model_level_calibration.py` and
  `tests/plugins/test_frontend_tkinter_level_calibration.py`
