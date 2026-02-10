# Battery Monitor Plugin Architecture

## Overview

The Battery Monitor plugin displays real-time battery voltage and current with color-coded status indication (green=safe, red=critical, gray=disabled/unavailable).
It reuses existing flight controller backend methods and follows the Model-View separation pattern.

**Key Features:**

- 500ms periodic updates
- Integrated at configuration step 08_batt1.param
- Real-time monitoring with color-coded status display
- Parameter upload capability for immediate tuning validation

## Architecture

### Component Layers

```text
┌─────────────────────────────────────────────────────────┐
│ GUI Layer (frontend_tkinter_battery_monitor.py)        │
│ - UI layout, periodic updates, color-coded display     │
│ - Upload button for selected parameter changes         │
└──────────────────┬──────────────────────────────────────┘
                   │
┌──────────────────▼──────────────────────────────────────┐
│ Data Model (data_model_battery_monitor.py)             │
│ - Business logic, status determination, data retrieval │
│ - Parameter editor integration for uploads             │
└──────────────────┬──────────────────────────────────────┘
                   │
┌──────────────────▼──────────────────────────────────────┐
│ Backend (backend_flightcontroller.py)                  │
│ - MAVLink telemetry (existing, reused methods)         │
│ - Parameter upload and validation                      │
└─────────────────────────────────────────────────────────┘
```

### Data Model (`data_model_battery_monitor.py`)

**Responsibilities:** Status determination, data retrieval coordination, backend abstraction, parameter editor integration

**Key Methods:**

- `is_battery_monitoring_enabled()` - Check BATT_MONITOR != 0
- `get_battery_status()` - Returns (voltage, current) tuple or None
- `get_voltage_status()` - Returns "safe"/"critical"/"disabled"/"unavailable"
- `get_battery_status_color()` - Maps status to "green"/"red"/"gray"

**Parameter Editor Integration:**

- Optional `parameter_editor` reference for upload capability
- Enables parameter changes to be uploaded directly from plugin
- Maintains separation of concerns through optional dependency

### GUI Layer (`frontend_tkinter_battery_monitor.py`)

**Responsibilities:** UI layout, periodic updates, visual presentation, parameter upload workflow

**Key Features:**

- Large, bold value displays with color-coding
- Informational text explaining status indicators
- 500ms periodic refresh via tkinter `after()`
- `on_activate()`/`on_deactivate()` for plugin lifecycle
- Upload button for selected parameters (when parameter editor available)
- Progress window integration for upload feedback
- Automatic table refresh after parameter upload

## Data Flow

### Monitoring Flow

1. **Timer fires** (500ms) → `_periodic_update()` called
2. **Check connection** → Model verifies FC connection status
3. **Retrieve data** → Model gets battery voltage/current from backend
4. **Determine status** → Model evaluates voltage against thresholds (BATT_ARM_VOLT, MOT_BAT_VOLT_MAX)
5. **Update display** → GUI formats values, applies color-coding, updates labels
6. **Schedule next** → Timer scheduled for next update

### Parameter Upload Flow

1. **User clicks upload** → `_on_upload_button_clicked()` invoked
2. **Gather selections** → Retrieve selected parameters from parameter editor table
3. **Validate preconditions** → Check FC connection and parameter selection
4. **Execute workflow** → Call `upload_params_with_progress()` with callbacks
5. **Progress feedback** → Display reset/download progress windows as needed
6. **Update FC values** → Refresh parameter objects with new FC values
7. **Refresh table** → Repopulate parameter editor table to show updated values

## Integration

- **Configuration Step:** 08_batt1.param (all vehicle types)
- **Plugin Registration:** `@plugin_factory(PLUGIN_BATTERY_MONITOR)` decorator
- **Backend Reuse:** Leverages existing `backend_flightcontroller.py` methods (no new backend code required)
- **Parameter Editor Integration:** Optional injection for upload capability
- **UI Services Reuse:** Leverages `ParameterEditorUiServices` for consistent upload workflows

## Testing

BDD pytest tests cover complete user workflows:

- **Monitoring:** Status determination, threshold validation, error handling, UI updates
- **Parameter Upload:** Selection, validation, progress feedback, error recovery
- **Integration:** Plugin lifecycle, data model + frontend interaction, table refresh

Test files:

- `tests/bdd_battery_monitor.py` - End-to-end user scenarios
- `tests/acceptance_battery_monitor.py` - Data model + frontend integration
- `tests/unit_data_model_battery_monitor.py` - Data model unit tests

## Design Decisions

- **500ms update interval:** Balances responsiveness with system load
- **Color-coded display:** Immediate visual feedback (green/red/gray)
- **Backend reuse:** No telemetry logic duplication, proven implementation
- **Step 08 placement:** Contextually relevant during battery configuration
- **Optional parameter editor:** Plugin works standalone for monitoring, enhanced with upload capability when editor available
- **Centralized upload workflow:** Reuses `upload_params_with_progress()` for consistency across application
- **Immediate validation:** Upload button enables users to test battery parameter changes without advancing to next step
