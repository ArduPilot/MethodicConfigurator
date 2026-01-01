# Battery Monitor Plugin Architecture

## Overview

The Battery Monitor plugin displays real-time battery voltage and current with color-coded status indication (green=safe, red=critical, gray=disabled/unavailable).
It reuses existing flight controller backend methods and follows the Model-View separation pattern.

**Key Features:**

- 500ms periodic updates
- Integrated at configuration step 08_batt1.param
- Read-only monitoring (no parameter modification)

## Architecture

### Component Layers

```text
┌─────────────────────────────────────────────────────────┐
│ GUI Layer (frontend_tkinter_battery_monitor.py)        │
│ - UI layout, periodic updates, color-coded display     │
└──────────────────┬──────────────────────────────────────┘
                   │
┌──────────────────▼──────────────────────────────────────┐
│ Data Model (data_model_battery_monitor.py)             │
│ - Business logic, status determination, data retrieval │
└──────────────────┬──────────────────────────────────────┘
                   │
┌──────────────────▼──────────────────────────────────────┐
│ Backend (backend_flightcontroller.py)                  │
│ - MAVLink telemetry (existing, reused methods)         │
└─────────────────────────────────────────────────────────┘
```

### Data Model (`data_model_battery_monitor.py`)

**Responsibilities:** Status determination, data retrieval coordination, backend abstraction

**Key Methods:**

- `is_battery_monitoring_enabled()` - Check BATT_MONITOR != 0
- `get_battery_status()` - Returns (voltage, current) tuple or None
- `get_voltage_status()` - Returns "safe"/"critical"/"disabled"/"unavailable"
- `get_battery_status_color()` - Maps status to "green"/"red"/"gray"

### GUI Layer (`frontend_tkinter_battery_monitor.py`)

**Responsibilities:** UI layout, periodic updates, visual presentation

**Key Features:**

- Large, bold value displays with color-coding
- Informational text explaining status indicators
- 500ms periodic refresh via tkinter `after()`
- `on_activate()`/`on_deactivate()` for plugin lifecycle

## Data Flow

1. **Timer fires** (500ms) → `_periodic_update()` called
2. **Check connection** → Model verifies FC connection status
3. **Retrieve data** → Model gets battery voltage/current from backend
4. **Determine status** → Model evaluates voltage against thresholds (BATT_ARM_VOLT, MOT_BAT_VOLT_MAX)
5. **Update display** → GUI formats values, applies color-coding, updates labels
6. **Schedule next** → Timer scheduled for next update

## Integration

- **Configuration Step:** 08_batt1.param (all vehicle types)
- **Plugin Registration:** `@plugin_factory(PLUGIN_BATTERY_MONITOR)` decorator
- **Backend Reuse:** Leverages existing `backend_flightcontroller.py` methods (no new backend code required)

## Testing

BDD pytest tests planned for:

- Data model: Status determination, threshold validation, error handling
- GUI: UI updates, periodic scheduling, color-coding

## Design Decisions

- **500ms update interval:** Balances responsiveness with system load
- **Color-coded display:** Immediate visual feedback (green/red/gray)
- **Backend reuse:** No telemetry logic duplication, proven implementation
- **Step 08 placement:** Contextually relevant during battery configuration
