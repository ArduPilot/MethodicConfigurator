# Motor Test Sub-application Architecture

## Overview

The Motor Test sub-application provides a graphical interface for testing individual motors on ArduPilot vehicles, similar to Mission Planner's motor test functionality.
It allows users to test motor functionality, verify motor order and direction, and configure motor parameters before flight.

## Requirements Analysis

### Functional Requirements

1. **Frame Configuration Interface**
   - FRAME_TYPE dropdown populated from parameter documentation metadata
   - FRAME_CLASS dropdown populated from parameter documentation metadata
   - Immediate parameter application to flight controller on selection
   - Dynamic motor count calculation based on frame configuration
   - Motor diagram display showing the currently selected frame configuration
   - SVG motor diagrams loaded from local images directory (downloaded from [ArduPilot documentation](https://ardupilot.org/copter/docs/connect-escs-and-motors.html))
     - The original diagrams are the `.svg` files in the `https://ardupilot.org/copter/_images/` directory

2. **Motor Parameter Configuration**
   - "Set Motor Spin Arm" button with parameter dialog for MOT_SPIN_ARM
   - "Set Motor Spin Min" button with parameter dialog for MOT_SPIN_MIN
   - Immediate parameter save and upload to flight controller
   - Current value display and validation

3. **Motor Testing Interface**
   - Display N motor test buttons based on detected/configured frame
   - Label buttons with letters (A, B, C, D...) following ArduPilot conventions
   - Expected direction labels (CW/CCW) for each motor position
   - Detected order dropdown comboboxes for user feedback
   - Configurable test duration (default: 2 seconds)
   - Real-time BATT1 voltage and current display with color-coded status

4. **Battery Status Display**
   - Current BATT1 voltage and current readings (only when BATT_MONITOR != 0)
   - When BATT_MONITOR == 0: Display "N/A"
   - Color-coded voltage display based on BATT_ARM_VOLT and MOT_BAT_VOLT_MAX thresholds:
     - Green: Voltage within BATT_ARM_VOLT to MOT_BAT_VOLT_MAX range (safe for motor testing)
     - Red: Voltage outside the safe range (unsafe for motor testing)
   - Safety popup when motor testing attempted with voltage outside safe range
   - Real-time updates during motor testing operations

5. **Safety Controls**
   - Prominent red "Stop all motors" emergency button
   - "Test in Sequence" button for automated testing
   - Safety warnings and operational guidelines at top
   - Parameter validation before motor testing
   - Automatic motor timeout for safety

6. **Order Detection and Validation**
   - User-selectable "Detected" comboboxes for each motor
   - Comparison between expected and detected motor order
   - Visual feedback for correct/incorrect motor placement
   - Guidance for correcting wiring issues

### Non-Functional Requirements

1. **Safety**
   - Multiple safety warnings prominently displayed
   - Clear indication of active motor testing
   - Emergency stop functionality always accessible
   - Safe parameter defaults and validation

2. **Usability**
   - Intuitive frame-based layout with logical workflow progression
   - Clear visual feedback for active operations
   - Immediate parameter application with confirmation
   - Responsive UI with real-time feedback
   - Keyboard shortcuts for critical functions

3. **Reliability**
   - Robust error handling for communication failures
   - Parameter validation and bounds checking
   - Graceful degradation when features unavailable
   - Comprehensive logging for debugging

4. **Performance**
   - Responsive UI updates during motor testing
   - Efficient parameter reading/writing
   - Minimal latency for emergency stop operations
   - Low resource usage

## System Design

### Architecture Pattern

The motor test sub-application follows the Model-View separation pattern established in the project:

```text
┌─────────────────┐    ┌──────────────────────┐
│   GUI Layer     │    │   Data Model Layer   │
│                 │    │                      │
│ frontend_tkinter│◄──►│ data_model_motor     │
│ _motor_test.py  │    │ _test.py             │
│                 │    │                      │
│ - UI Layout     │    │ - Business Logic     │
│ - Event Handling│    │ - Parameter Mgmt     │
│ - User Feedback │    │ - Frame Detection    │
└─────────────────┘    └──────────────────────┘
                                │
                                ▼
                       ┌──────────────────────┐
                       │ Flight Controller    │
                       │                      │
                       │ backend_flight       │
                       │ controller.py        │
                       │                      │
                       │ - MAVLink Comm       │
                       │ - Parameter I/O      │
                       │ - Motor Commands     │
                       └──────────────────────┘
```

### Component Responsibilities

#### Data Model Layer (`data_model_motor_test.py`)

**Primary Responsibilities:**

- Frame type detection and motor count calculation
- Motor label generation (numbers and letters)
- Parameter reading and writing (MOT_SPIN_ARM, MOT_SPIN_MIN)
- Battery status monitoring (BATT1 voltage and current when BATT_MONITOR != 0)
- Voltage threshold validation (BATT_ARM_VOLT and MOT_BAT_VOLT_MAX thresholds)
- Business logic validation
- Flight controller communication abstraction

**Key Methods:**

```python
def __init__(self, flight_controller: FlightController) -> None
def get_motor_count(self) -> int
def get_motor_labels(self) -> list[str]
def get_battery_status(self) -> tuple[float, float] | None  # voltage, current or None if BATT_MONITOR == 0
def get_voltage_status(self) -> str  # "safe", "critical" or "disabled"
def is_battery_monitoring_enabled(self) -> bool  # True if BATT_MONITOR != 0
def set_parameter(self, param_name: str, value: float) -> bool
def test_motor(self, motor_number: int, throttle_percent: int, timeout_seconds: int) -> None
def stop_all_motors(self) -> None
```

**Data Attributes:**

- `flight_controller`: Backend communication interface
- `frame_class`: Detected vehicle frame class
- `frame_type`: Detected vehicle frame type
- `motor_count`: Number of motors for current frame

#### GUI Layer (`frontend_tkinter_motor_test.py`)

**Primary Responsibilities:**

- User interface layout and visual design
- Event handling and user interactions
- Real-time feedback and status updates
- Safety confirmations and warnings
- Integration with application window management

**Key UI Components:**

- Information and safety warnings at the top
- Frame configuration section with FRAME_TYPE and FRAME_CLASS comboboxes
- Arm and min throttle configuration with parameter buttons
- Motor order/direction configuration with test buttons and direction detection
- Real-time battery status display with color-coded voltage indication
- Prominent red emergency stop button and test sequence controls

**Layout Structure:**

```text
┌─────────────────────────────────────────────────────────────┐
│ Information & Safety Warnings                               │
│ • Remove propellers before testing                          │
│ • Ensure vehicle is secured                                 │
│ • Emergency stop always available                           │
├─────────────────────────────────────────────────────────────┤
│ 1. Frame configuration                                      │
│ Frame Type: [FRAME_TYPE ▼]  Frame Class: [FRAME_CLASS ▼]   │
├─────────────────────────────────────────────────────────────┤
│ 2. Arm and min throttle configuration                      │
│ [Set Motor Spin Arm] [Set Motor Spin Min]                  │
├─────────────────────────────────────────────────────────────┤
│ 3. Motor order/direction configuration                     │
│ Duration: [____] seconds    Battery: 12.4V/2.1A            │
│                                                             │
│ [Motor A] Motor 1 CW  [Detected: ▼]                       │
│ [Motor B] Motor 2 CCW [Detected: ▼]                       │
│ [Motor C] Motor 3 CCW [Detected: ▼]                       │
│ [Motor D] Motor 4 CW  [Detected: ▼]                       │
│ ...                                                         │
│                                                             │
│ [🛑 STOP ALL MOTORS] [Test in Sequence]                   │
└─────────────────────────────────────────────────────────────┘
```

### Data Flow

#### User Workflow Sequence

1. **Safety Setup**
   - User reads safety warnings and ensures propellers are removed
   - User secures vehicle to prevent movement during tests

2. **Frame Configuration**
   - User selects appropriate FRAME_TYPE from dropdown (populated from parameter documentation)
   - User selects appropriate FRAME_CLASS from dropdown (populated from parameter documentation)
   - Parameters are immediately applied to flight controller on selection

3. **Motor Parameter Configuration**
   - User clicks "Set Motor Spin Arm" to configure MOT_SPIN_ARM parameter
   - User clicks "Set Motor Spin Min" to configure MOT_SPIN_MIN parameter
   - Each button opens parameter dialog and saves/uploads value immediately

4. **Motor Testing and Order Detection**
   - User monitors real-time battery voltage and current display (if BATT_MONITOR != 0)
   - User sets test duration (default: 2 seconds)
   - User tests individual motors using labeled buttons (Motor A, B, C, etc.)
   - User observes actual motor spinning and records in "Detected" comboboxes
   - System provides color-coded voltage feedback (green=safe, red=outside safe range)
   - Safety popup appears when attempting motor test with voltage outside BATT_ARM_VOLT to MOT_BAT_VOLT_MAX range
   - User can run "Test in Sequence" to automatically test all motors
   - Emergency stop button available at all times during testing

5. **Order Validation**
   - System compares expected vs detected motor order
   - User corrects any wiring issues based on feedback
   - System provides guidance on proper motor/ESC connections

#### Motor Testing Workflow

1. **Initialization**: GUI requests motor count and labels from data model
2. **Frame Detection**: Data model reads FRAME_CLASS/FRAME_TYPE parameters
3. **Battery Monitoring**: Data model reads BATT1 voltage/current and BATT_ARM_VOLT/MOT_BAT_VOLT_MAX thresholds (if BATT_MONITOR != 0)
4. **UI Setup**: Dynamic button creation based on detected frame configuration
5. **Battery Validation**: System checks voltage status before allowing motor tests
6. **User Action**: User clicks motor test button
7. **Safety Validation**: Data model validates parameters, battery status (if enabled), and safety conditions
8. **Execution**: Motor command sent to flight controller via backend
9. **Feedback**: UI updates to show active motor testing status and battery monitoring
10. **Completion**: Automatic timeout or user stop action

#### Battery Safety Validation Workflow

1. **Motor Test Request**: User clicks any motor test button
2. **Battery Monitor Check**: Data model checks if BATT_MONITOR != 0
3. **Voltage Range Check**: If battery monitoring enabled, validate voltage is within BATT_ARM_VOLT to MOT_BAT_VOLT_MAX range
4. **Safety Popup**: If voltage outside safe range, display popup:
   "Battery voltage outside safe range. Please connect battery and/or ensure battery is in charged state."
5. **User Action**: User can choose to:
   - Cancel motor test and address battery issue
   - Override and proceed (with additional warning)
6. **Test Execution**: Motor test proceeds only if voltage is safe or user explicitly overrides

#### Parameter Configuration Workflow

1. **Frame Selection**: User selects FRAME_TYPE/FRAME_CLASS from dropdowns
2. **Immediate Application**: Parameters uploaded to flight controller immediately
3. **Parameter Button**: User clicks "Set Motor Spin Arm/Min" button
4. **Current Value**: Data model reads current parameter value
5. **User Input**: GUI presents input dialog with current value
6. **Validation**: Data model validates new parameter value
7. **Update**: Parameter uploaded to flight controller
8. **Confirmation**: UI confirms successful parameter update

## Testing Strategy

### Pytest Unit Testing Requirements

#### Data Model Tests (`tests/test_data_model_motor_test.py`)

- Frame detection logic with various FRAME_CLASS/FRAME_TYPE combinations
- Motor count calculation for all supported frame types
- Motor label generation (number/letter mapping)
- Parameter validation and bounds checking
- Error handling for communication failures
- Motor testing command generation

#### GUI Tests (`tests/test_frontend_tkinter_motor_test.py`)

- UI component creation and layout
- Button generation based on motor count
- Event handling for all interactive elements
- Safety confirmation dialogs
- Parameter input validation
- Integration with data model layer

### Integration Testing

#### End-to-End Scenarios

- Complete motor testing workflow from GUI to flight controller
- Parameter configuration and validation
- Emergency stop functionality
- Multi-frame type support validation

#### Mock Testing Strategy

- Flight controller communication mocking
- Parameter read/write simulation
- Frame detection with various configurations
- Error condition simulation
- Safety mechanism testing

### Test Fixtures and Patterns

Following project pytest guidelines with BDD structure:

```python
@pytest.fixture
def mock_flight_controller() -> MagicMock:
    """Fixture providing mocked flight controller with realistic responses."""
    
@pytest.fixture
def motor_test_data_model(mock_flight_controller) -> MotorTestDataModel:
    """Fixture providing configured motor test data model."""
    
@pytest.fixture
def motor_test_window(motor_test_data_model) -> MotorTestWindow:
    """Fixture providing configured motor test GUI window."""

def test_user_can_test_individual_motor(self, motor_test_window) -> None:
    """
    User can test individual motors safely.
    
    GIVEN: A configured vehicle with detected frame type
    WHEN: User clicks a motor test button
    THEN: The corresponding motor should activate with feedback
    """
```

## Implementation Guidelines

### Code Style Requirements

1. **Type Hints**: All functions must include complete type annotations
2. **Documentation**: Comprehensive docstrings following project standards
3. **Error Handling**: Graceful error handling with user feedback
4. **Logging**: Appropriate logging for debugging and audit trail
5. **Internationalization**: All user-facing strings wrapped with `_()`

### Safety Implementation

1. **Parameter Validation**: All parameters validated before sending to FC
2. **Battery Monitoring**: Real-time battery voltage monitoring with BATT_ARM_VOLT/MOT_BAT_VOLT_MAX threshold validation (when BATT_MONITOR != 0)
3. **Voltage Safety**: Safety popup when attempting motor test with voltage outside safe range, prompting user to connect battery and/or ensure charged state
4. **Timeout Mechanisms**: Automatic motor stop after configured timeout
5. **Emergency Stop**: Always accessible stop functionality
6. **User Confirmation**: Display a Safety confirmation popup the first time a Motor test button is pressed
7. **Visual Feedback**: Clear indication of active motor testing (status column) and battery status (green/red voltage display)

### Performance Considerations

1. **Lazy Loading**: UI components created only when needed
2. **Efficient Updates**: Minimal UI updates during motor testing
3. **Resource Management**: Proper cleanup of timers and connections
4. **Responsive Design**: Non-blocking operations for UI responsiveness

## Integration Points

### Main Application Integration

The motor test sub-application integrates with the main ArduPilot Methodic Configurator through:

1. **Menu Integration**: Accessible from dedicated button
2. **Flight Controller Sharing**: Uses existing FC connection
3. **Parameter Context**: Reads current vehicle configuration (LocalFilesystem)
4. **Logging Integration**: Uses application logging framework
5. **Settings Persistence**: Saves user settings (test duration in ProgramSettings)

### ArduPilot Integration

Communication with ArduPilot flight controller via:

1. **MAVLink Protocol**: Standard parameter and command protocols
2. **Parameter System**: Read/write MOT_* parameters
3. **Motor Commands**: Direct motor control via MAVLink
4. **Status Monitoring**: Real-time status and safety monitoring
5. **Frame Detection**: Automatic vehicle configuration detection

## Future Enhancements

### Planned Features

1. **Motor Health Monitoring**: Current draw and performance metrics
2. **Calibration Assistance**: Guided motor calibration procedures
3. **Visual Frame Display**: Graphical representation of motor layout

## Security Considerations

### Safety Measures

1. **Parameter Bounds**: Strict validation of all motor parameters

### Risk Mitigation

1. **Hardware Safety**: Clear warnings about propeller removal
2. **Software Safety**: Multiple layers of safety checks
3. **Communication Safety**: Robust error handling for comm failures
4. **User Safety**: Clear operational guidelines and warnings

---

This architecture provides a comprehensive foundation for implementing a safe, reliable, and user-friendly motor test sub-application
that integrates seamlessly with the ArduPilot Methodic Configurator while maintaining the highest safety standards for motor testing operations.
