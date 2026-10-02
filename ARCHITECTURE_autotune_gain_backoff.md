# AutoTune Gain Back-off Plugin Architecture

## Overview

An offline-capable plugin stages an explicit additional gain reduction in the
active AutoTune results step. It loads only for project firmware below 4.7.0.
See [firmware research and usage](docs/AUTOTUNE_GAIN_BACKOFF.md).

## Components

```text
Configuration JSON ("plugin", "if")
    -> ParameterEditor.get_plugin() -> plugin_factory
    -> AutotuneGainBackoffView
    -> AutotuneGainBackoffDataModel
    -> active-step ArduPilotParameter objects
    -> refreshed parameter table
```

| Layer | File under `ardupilot_methodic_configurator/` |
| --- | --- |
| Domain | `plugins/data_model_autotune_gain_backoff.py` |
| Frontend | `plugins/frontend_tkinter_autotune_gain_backoff.py` |
| Factory | `plugins/plugin_factory.py` |
| Registration | `__main__.py`, `plugins/plugin_constants.py` |
| Activation | `configuration_steps_*.json`, `configuration_steps_schema.json` |

## Requirements and verification

- Implemented and tested: fraction range 0.0-0.5; default 0.25.
- Implemented and tested: active-axis P/I/D and angle P selection; ordinary
  yaw excludes D; roll/pitch retune includes both axes.
- Implemented and tested: `ATC_` and QuadPlane `Q_A_` gain families.
- Implemented and tested: repeated clicks compound on current New values.
- Implemented and tested: all values validated before any mutation.
- Implemented and tested: preserved reasons, unchanged FC values, no missing
  parameters added, zero back-off is a no-op.
- Implemented and tested: offline model factory and actual Apply button.
- Implemented and tested: all 20 bundled results steps use the firmware guard.

## Data flow and boundaries

The view parses input and passes the fraction to the model. The model resolves
the tuned axes from the active filename and validates proposed values on
independent parameter copies. Only after all validations succeed are original
parameter objects changed and reasons appended. The view refreshes the table.
Metadata range violations are collected rather than blocking the reduction;
the view displays them in a warning popup after changing the New values.
Normal AMC save/upload remains a separate user action.

No new backend, dependencies, timers or connections are required. The model
reads already-loaded editor state and performs no file or FC I/O. The factory
registers with `requires_flight_controller=False`. Visibility uses existing
JSON condition evaluation rather than a plugin-specific frontend check.
