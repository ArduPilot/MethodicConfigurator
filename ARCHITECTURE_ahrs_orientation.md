# AHRS Orientation Helper Plugin Architecture

## Overview

The AHRS Orientation Helper plugin assists users during the board-orientation step by either:

- Setting `AHRS_ORIENTATION` manually in the parameter editor, or
- Running a guided three-pose estimation workflow (LEVEL, NOSE DOWN, RIGHT).

The plugin computes the best matching predefined `AHRS_ORIENTATION` value from IMU samples.
If no sufficiently strong and distinct preset match is found, it provides fallback `CUST_ROT1_ROLL`, `CUST_ROT1_PITCH`, and
`CUST_ROT1_YAW` estimates and instructs the user to retry with the vehicle resting still.

## Component Layers

```text
+--------------------------------------------------------------+
| GUI Layer                                                    |
| frontend_tkinter_ahrs_orientation.py                         |
| - Manual guidance text                                       |
| - Auto-detect wizard for 3 capture steps                     |
| - Result presentation (preset or custom fallback angles)     |
+------------------------------+-------------------------------+
                               |
+------------------------------v-------------------------------+
| Data Model Layer                                             |
| data_model_ahrs_orientation.py                               |
| - Sample capture validation                                  |
| - Board-from-body matrix estimation                          |
| - Best-fit preset matching over AHRS_ORIENTATION list        |
| - Euler321 custom-angle fallback estimation                  |
+------------------------------+-------------------------------+
                               |
+------------------------------v-------------------------------+
| Flight Controller facade                                     |
| backend_flightcontroller.py                                  |
| - request_scaled_imu_messages()                              |
| - poll_scaled_imu()                                          |
+--------------------------------------------------------------+
```

## File Map

| File | Role |
| --- | --- |
| `ardupilot_methodic_configurator/plugins/plugin_constants.py` | Plugin name constant (`PLUGIN_AHRS_ORIENTATION`) |
| `ardupilot_methodic_configurator/plugins/data_model_ahrs_orientation.py` | Business logic and orientation estimation |
| `ardupilot_methodic_configurator/plugins/frontend_tkinter_ahrs_orientation.py` | tkinter wizard and status UI |
| `ardupilot_methodic_configurator/__main__.py` | Plugin registration in `register_plugins()` |
| `ardupilot_methodic_configurator/plugins/plugin_factory.py` | View and data-model factory registry |
| `ardupilot_methodic_configurator/configuration_steps_schema.json` | Schema enum for plugin name |
| `ardupilot_methodic_configurator/configuration_steps_*.json` | Step wiring (`05_board_orientation.param`) |

## Requirements Analysis

### Functional

- F1: Provide manual path to set `AHRS_ORIENTATION`.
- F2: Provide a 3-step guided capture sequence controlled by the Continue button.
- F3: Compute best matching predefined `AHRS_ORIENTATION` value.
- F4: Require at least a 90% match score and sufficient separation from the next-best preset.
- F5: When no preset passes the match criteria, provide `CUST_ROT1_ROLL/PITCH/YAW` fallback and retry guidance.

### Non-Functional

- N1: Keep business logic in data model, no tkinter dependency in model.
- N2: Non-blocking UI updates via `after()` polling.
- N3: Reuse existing FlightController IMU-stream helpers.

## Data Flow

```text
User opens 05_board_orientation.param step
  -> Plugin view starts IMU polling loop

Plugin activation starts the detection sequence
  -> reset samples
  -> wizard step 1 (LEVEL)

On each Continue:
  -> capture current IMU sample
  -> validate still-range magnitude
  -> store sample for current step
  -> advance to next step

After step 3 (RIGHT):
  -> estimate board-from-body matrix
  -> score all predefined AHRS_ORIENTATION presets
  -> if match score and separation pass their thresholds: recommend preset code/name
  -> else: show CUST_ROT1_ROLL/PITCH/YAW fallback + retry guidance
```

## Estimation Notes

- Required poses: LEVEL, NOSE DOWN, RIGHT side down.
- Each sample contributes one gravity direction constraint in board coordinates.
- The model reconstructs an orthonormal board-from-body matrix from the three samples.
- Preset fit score is the mean dot product between expected and measured gravity vectors.
- Preset-match gate includes absolute fit and separation from the second-best preset.

## External References

- [ArduPilot mounting and board orientation documentation](https://ardupilot.org/copter/docs/common-mounting-the-flight-controller.html)
- [MAVLink `SCALED_IMU` message](https://mavlink.io/en/messages/common.html#SCALED_IMU)
