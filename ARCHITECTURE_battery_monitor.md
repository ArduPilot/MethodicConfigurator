# Battery Monitor Plugin Architecture

## Overview

The Battery Monitor plugin displays real-time voltage and current for each enabled battery monitor,
with color-coded status indication (green=safe, red=critical, gray=disabled/unavailable).
It reuses existing flight controller backend methods and follows the Model-View separation pattern.

**Key Features:**

- 500ms periodic display updates for up to 16 battery monitors
- Integrated at configuration step 11_battery.param
- Real-time monitoring with color-coded status display
- Numbered, scrollable battery rows with independent voltage and current readings

## Architecture

### Component Layers

```text
┌─────────────────────────────────────────────────────────┐
│ GUI Layer (frontend_tkinter_battery_monitor.py)        │
│ - UI layout, periodic updates, color-coded display     │
│ - Scrollable, numbered rows for enabled batteries      │
└──────────────────┬──────────────────────────────────────┘
                   │
┌──────────────────▼──────────────────────────────────────┐
│ Data Model (data_model_battery_monitor.py)             │
│ - Business logic, status determination, data retrieval │
│ - Per-battery voltage thresholds and stream recovery   │
└──────────────────┬──────────────────────────────────────┘
                   │
┌──────────────────▼──────────────────────────────────────┐
│ Backend (backend_flightcontroller.py)                  │
│ - MAVLink telemetry (existing, reused methods)         │
│ - Per-ID telemetry cache and unavailable-field decoding│
└─────────────────────────────────────────────────────────┘
```

### Data Model (`data_model_battery_monitor.py`)

**Responsibilities:** Per-battery status determination, data retrieval coordination, backend abstraction

**Key Methods:**

- `get_enabled_battery_ids()` - Return enabled zero-based MAVLink battery IDs from the monitor parameters
- `is_battery_monitoring_enabled()` - Check whether any battery monitor is enabled
- `get_battery_statuses()` - Return a dictionary of battery IDs to (voltage, current) tuples, or None
- `get_voltage_thresholds(battery_id)` - Return the battery's minimum and maximum safe voltage
- `get_voltage_status(battery_id, voltage)` - Return translated "safe"/"critical"/"disabled"/"unavailable"
- `get_battery_status_color(battery_id, voltage)` - Map status to "green"/"red"/"gray"

**Voltage Thresholds:**

- Battery 1 uses the backend's `BATT_ARM_VOLT` and motor voltage limits
- Other batteries use their own arming voltage parameter, such as `BATT2_ARM_VOLT`, with no upper limit
- Missing or invalid thresholds produce an unavailable status

### GUI Layer (`frontend_tkinter_battery_monitor.py`)

**Responsibilities:** UI layout, periodic updates, visual presentation

**Key Features:**

- One numbered row per enabled monitor, with large, bold values and voltage color-coding
- `ScrollFrame` keeps all battery rows accessible in a small window
- Informational text explaining status indicators
- 500ms periodic refresh via tkinter `after()`
- `on_activate()`/`on_deactivate()` for plugin lifecycle
- Add and remove rows when monitor parameters change
- Show N/A independently for missing or expired readings; show Disabled when all monitors are disabled

## Data Flow

### Monitoring Flow

1. **Timer fires** (500ms) → `_periodic_update()` called
2. **Check connection** → Model verifies FC connection status
3. **Retrieve data** → Model gets battery voltage/current keyed by battery ID from backend
4. **Determine status** → Model evaluates each voltage against that battery's thresholds
5. **Update display** → GUI formats each row's values, applies color-coding, updates labels
6. **Schedule next** → Timer scheduled for next update

### Telemetry Stream and Cache

- ArduPilot sends one battery ID per BATTERY_STATUS stream interval, cycling through enabled monitors
- The model requests an interval of `500000 / enabled_monitor_count` microseconds,
  rounded down, so a complete cycle fits within the 500ms display interval
- A change in monitor count triggers a new stream request
- The model retries stream requests until readings arrive and recovers after telemetry loss
- The commands manager drains queued BATTERY_STATUS messages and caches the latest reading for each ID
- Each reading expires independently after three seconds; disabled IDs and readings from an old connection are removed
- Cell voltage sentinels are decoded before summing; a valid pack total of 65535 mV remains valid

### Parameter Changes

Users upload battery parameter changes through the parameter editor's existing upload controls.
The plugin observes the resulting flight controller parameter values during subsequent refreshes.

## Integration

- **Configuration Step:** 11_battery.param (all vehicle types)
- **Plugin Registration:** `@plugin_factory(PLUGIN_BATTERY_MONITOR)` decorator
- **Backend Facade:** Uses `FlightController.get_battery_statuses()` to access the commands manager's per-ID cache
- **Parameter Editor Integration:** Shares the flight controller's uploaded parameter values
- **Motor Test Integration:** Motor testing selects ID 0 and uses battery 1's thresholds;
  when `BATT_MONITOR` is disabled, the existing voltage verification warning permits testing

## Testing

BDD pytest tests cover complete user workflows:

- **Monitoring:** Status determination, threshold validation, error handling, UI updates
- **Multiple Batteries:** Independent readings, secondary-only monitoring, unavailable fields, round-robin streams
- **Integration:** Plugin lifecycle, data model + frontend interaction, row changes, scrolling

Test files:

- `tests/plugins/bdd_battery_monitor.py` - End-to-end user scenarios
- `tests/plugins/acceptance_battery_monitor.py` - Data model + frontend integration
- `tests/plugins/unit_data_model_battery_monitor.py` - Data model and stream timing tests
- `tests/test_backend_flightcontroller_commands.py` - MAVLink decoding and per-battery cache tests
- `tests/plugins/test_data_model_motor_test.py` - Primary-battery safety checks, including translated status strings

## Design Decisions

- **500ms display interval:** Balances responsiveness with system load
- **Monitor-aware stream interval:** Keeps all rows current while preserving the three-second stale-reading limit
- **Color-coded display:** Immediate visual feedback (green/red/gray)
- **Backend reuse:** No telemetry logic duplication, proven implementation
- **Step 11 placement:** Contextually relevant during battery configuration
- **Shared parameter uploads:** The parameter editor manages uploads while the plugin displays their telemetry results
