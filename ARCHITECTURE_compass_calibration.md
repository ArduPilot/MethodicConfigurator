# Compass Calibration Sub-application Architecture

## Overview

The Compass Calibration sub-application provides a guided interface for
calibrating the onboard magnetometers of an ArduPilot vehicle.

The workflow consists of two popup windows. The first popup provides
preparation instructions before calibration begins. After the user
continues, a second popup displays live calibration progress for up to
three active compasses.

Communication with the flight controller is performed through MAVLink
commands. Progress updates continue until calibration is completed or
cancelled.

## Functional Requirements

### Calibration Control

- Start Compass Calibration button integrated into the
  parameter editor.
- Two step workflow consisting of an instructions popup
  followed by the calibration progress popup.
- Sends `MAV_CMD_DO_START_MAG_CAL`.
- Sends `MAV_CMD_DO_CANCEL_MAG_CAL`.
- Cancel Calibration button available throughout the
  calibration process.

### Real Time Progress Monitoring

- Continuously processes the MAVLink receive buffer.
- Reads `MAG_CAL_PROGRESS` and `MAG_CAL_REPORT` messages.
- Returns progress as `list[dict]` to support multiple
  compasses.

### User Interface

- Progress bars are created before calibration
  begins to keep the layout stable.
- Independent progress display for Compass 0, Compass 1,
  and Compass 2 and so on.
- Visual indication when a compass completes calibration, turns green.
- Automatically closes after all active compasses finish.

## Non Functional Requirements

### Safety

- Uses `grab_set()` to prevent interaction with the main
  application during calibration.
- Sends the cancel command if the popup is closed.
- Displays preparation instructions before calibration.

### Usability

- Does not change the parameter editor layout.
- Centers popup windows over the parent window.
- Keeps the progress layout stable.

### Reliability

- Handles disconnected flight controllers.
- Returns an empty list when no progress is available.

## System Design

### Architecture

```text
            User Interface
                   |
                   v
┌─────────────────────────────────────────┐
| frontend_tkinter_compass_calibration.py |
└─────────────────────────────────────────┘
                   |
                   v
┌─────────────────────────────────────────┐
| data_model_compass_calibration.py       |
└─────────────────────────────────────────┘
                   |
                   v
┌─────────────────────────────────────────┐
| backend_flightcontroller_commands.py    |
└─────────────────────────────────────────┘
                   |
                   v
            Flight Controller
```

## Component Responsibilities

### Data Model

#### Module

`data_model_compass_calibration.py`

#### Data Model Responsibilities

- Validates the flight controller connection.
- Starts calibration.
- Cancels calibration.
- Retrieves progress information.
- Returns data in a format suitable for the user interface.

#### Data Model Public Methods

```python
def __init__(self, flight_controller: FlightController) -> None
def is_connected(self) -> bool
def start_calibration(self) -> tuple[bool, str]
def cancel_calibration(self) -> tuple[bool, str]
def get_progress(self) -> list[dict[str, int | float | str]]
```

### Backend

#### Backend Module

`backend_flightcontroller_commands.py`

#### Backend Responsibilities

- Sends MAVLink commands.
- Waits for acknowledgements.
- Reads calibration messages.
- Collects progress for all active compasses.

#### Backend Public Methods

```python
def start_compass_calibration(self) -> tuple[bool, str]
def cancel_compass_calibration(self) -> tuple[bool, str]
def get_compass_calibration_progress(
    self,
) -> list[dict[str, int | float | str]]
```

### Frontend

#### Frontend Module

`frontend_tkinter_compass_calibration.py`

#### User Interface Responsibilities

- Displays calibration controls.
- Displays preparation instructions.
- Displays live progress.
- Updates progress bars.
- Handles user actions.
- Displays completion and error dialogs.

#### Main Classes

##### `CompassCalibrationView`

Embedded entry point inside the parameter editor.

##### `CompassCalibrationInstructionsPopup`

Displays preparation instructions before calibration begins.

##### `CompassCalibrationPopup`

Displays live progress and manages the update loop.

## Data Flow

### Calibration Workflow

1. The user opens the mandatory hardware configuration page.

2. The user selects **Start Compass Calibration**.

3. The instructions popup is displayed and takes focus.

4. The user selects **Continue**.

5. The user interface calls:

6. The backend sends:

7. The progress popup opens.

8. Every 100 milliseconds:

   - The user interface requests progress.
   - The data model requests telemetry.
   - The backend reads available calibration messages.
   - Progress is returned as a list.
   - Matching progress bars are updated.

9. `MAG_CAL_PROGRESS` and `MAG_CAL_REPORT` messages are processed.

10. When every active compass reports completion:

    - Progress reaches 100%.
    - The popup closes.
    - A success dialog is displayed.

```python
model.start_calibration()
```

```text
MAV_CMD_DO_START_MAG_CAL
```

## Integration

### Configuration

```text
#Todo be put after finalising the step
```

### Plugin Registration

```python
@plugin_factory(PLUGIN_COMPASS_CALIBRATION)
```

### Backend Integration

The implementation reuses the existing `MavlinkConnection` and command
handling infrastructure. No additional dependencies are required.

## Testing

### Unit Testing

Module:

```text
tests/unit_data_model_compass_calibration.py
```

Verified behavior includes:

- Flight controller disconnection handling.
- Calibration state tracking.
- Backend command delegation.
- Progress data forwarding.
- Empty progress handling.

### Integration Testing

Verified using SITL, test scripts and a real FC:

- Calibration command acceptance.
- Progress message processing.
- Connection failure handling.
- Independent updates for multiple compasses.
- Stable user interface layout.
- Automatic completion handling.

### Static Analysis

Strict type checking is verified across all modules.

## Summary

The Compass Calibration sub-application provides a guided workflow for
onboard compass calibration. The implementation separates the user
interface, data model, and backend communication layers while reusing the
existing flight controller communication infrastructure. Live progress is
displayed for each active compass until calibration completes or is
cancelled.
