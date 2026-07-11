---
name: add-new-plugin
description: 'Add a new plugin to ArduPilot Methodic Configurator (AMC). Use when implementing a new calibration, monitoring, or configuration plugin — e.g., "add a radio calibration plugin". Covers all five mandatory touch-points: plugin_constants.py, __main__.py, data_model_parameter_editor.py, frontend_tkinter_*.py, and configuration_steps_schema.json, plus the optional configuration_steps_*.json wiring and an optional renderer module.'
argument-hint: 'plugin name (e.g. radio_calibration)'
---

# Add a New Plugin to AMC

## When to Use

- Implementing a new GUI panel that appears alongside parameter editing (calibration,
  monitoring, testing, …).
- Extending an existing configuration step with a plugin widget.

## Background

AMC uses a **plugin factory** pattern.  Every plugin consists of:

| Layer | File(s) |
| ------- | --------- |
| Constant | `plugin_constants.py` |
| Data model | `data_model_<plugin>.py` |
| Frontend | `frontend_tkinter_<plugin>.py` |
| Registration | `__main__.py → register_plugins()` |
| Data-model wiring | `data_model_parameter_editor.py → create_plugin_data_model()` |
| Schema | `configuration_steps_schema.json` |
| Step wiring | `configuration_steps_<VehicleType>.json` |
| Architecture doc | `ARCHITECTURE_<plugin_name>.md` in the project root |
| Renderer (optional) | `renderer_<name>.py` — for plugins needing a dedicated visualisation helper |

The inline docs in `plugin_constants.py`, `__main__.py:register_plugins()`, and
`data_model_parameter_editor.py:create_plugin_data_model()` should be kept in sync
with this skill (schema path: `plugin > properties > name > enum`).

---

## Step-by-Step Procedure

### 1. Add the constant — `plugin_constants.py`

Add a `PLUGIN_<NAME>` constant at the bottom of the file:

```python
PLUGIN_<NAME> = "<snake_case_name>"
```

Example (RC calibration):

```python
PLUGIN_RC_CALIBRATION = "rc_calibration"
```

### 2. Create the data model — `data_model_<plugin>.py`

Create `ardupilot_methodic_configurator/data_model_<plugin>.py`.

- Accept `flight_controller: FlightController` (and optionally
  `local_filesystem: LocalFilesystem`) in `__init__`.
- Expose only business logic; **no tkinter imports**.
- Follow the same structure as `data_model_accelerometer_calibration.py` or
  `data_model_battery_monitor.py` for inspiration.

### 3. Create the frontend — `frontend_tkinter_<plugin>.py`

Create `ardupilot_methodic_configurator/frontend_tkinter_<plugin>.py`.

Mandatory elements:

```python
from ardupilot_methodic_configurator.plugin_constants import PLUGIN_<NAME>
from ardupilot_methodic_configurator.plugin_factory import plugin_factory

def _create_<plugin>_view(parent: object, model: object, base_window: object) -> <PluginView>:
    # Type checker verifies correct types are provided by the caller
    return <PluginView>(parent, model, base_window)  # type: ignore[arg-type]

def register_<plugin>_plugin() -> None:
    """Register the <plugin> plugin with the factory."""
    plugin_factory.register(PLUGIN_<NAME>, _create_<plugin>_view)
```

Optionally add a standalone `<PluginName>Window(BaseWindow)` class for
development/testing (mark it `# pragma: no cover`).

### 4. Register the plugin — `__main__.py → register_plugins()`

Inside `register_plugins()` add a deferred import and a registration call:

```python
from ardupilot_methodic_configurator.frontend_tkinter_<plugin> import (  # noqa: PLC0415
    register_<plugin>_plugin,
)
# ...
register_<plugin>_plugin()
```

Keep imports inside the function body to avoid circular-import issues (the
`frontend_tkinter_*` modules import `plugin_factory` at module level).

### 5. Wire the data model — `data_model_parameter_editor.py → create_plugin_data_model()`

Add an `if` branch **before** the `raise ValueError` at the end:

```python
from ardupilot_methodic_configurator.data_model_<plugin> import <PluginDataModel>
from ardupilot_methodic_configurator.plugin_constants import PLUGIN_<NAME>

# inside create_plugin_data_model():
if plugin_name == PLUGIN_<NAME>:
    return <PluginDataModel>(self._flight_controller) if self.is_fc_connected else None
```

Add the import with the other data-model imports near the top of the file, maintaining
**alphabetical order** within the `data_model_*` import block (ruff enforces sorted
imports and will flag violations during `ruff check`).

### 6. Update the schema — `configuration_steps_schema.json`

Find the `plugin > properties > name > enum` array and append the new plugin
name string:

```json
"enum": [
    "motor_test",
    "battery_monitor",
    "compass_calibration",
    "accelerometer_calibration",
    "<snake_case_name>"
]
```

### 7. (Optional) Wire to a configuration step — `configuration_steps_<VehicleType>.json`

To show the plugin in a specific parameter-editing step, add a `"plugin"` key
to the relevant step object:

```json
"<param_file>.param": {
    "why": "...",
    "plugin": {
        "name": "<snake_case_name>",
        "placement": "left"
    }
}
```

`placement` is either `"left"` (beside the scrollable frame) or `"top"` (above
the parameter list).  Repeat for each vehicle-type JSON that should display the
plugin (`configuration_steps_ArduCopter.json`, `configuration_steps_ArduPlane.json`,
`configuration_steps_Heli.json`, `configuration_steps_Rover.json`).

### 8. Create the architecture document — `ARCHITECTURE_<plugin_name>.md`

Every plugin must have a corresponding architecture document in the project root.
Follow the same structure as `ARCHITECTURE_accelerometer_calibration.md` or
`ARCHITECTURE_rc_calibration.md`:

- Overview paragraph + key features list
- Component layers ASCII diagram
- File map table
- Requirements Analysis (functional + non-functional) with ✅ / 🟡 / ❌ status
- Data flow section (sequence diagrams in code blocks)
- Any plugin-specific design notes (e.g., popup window, renderer module)
- External reference links (MAVLink docs, ArduPilot wiki)

### 9. (Optional) Create a renderer module — `renderer_<name>.py`

If the plugin needs a dedicated visualisation helper (e.g., a 3D attitude renderer),
create `ardupilot_methodic_configurator/renderer_<name>.py`.

- **No tkinter dependency** — return a `PIL.Image.Image` that the frontend displays
  via a `ttk.Label`.
- Avoid wildcard imports (`from SomeLib import *`) — ruff enforces explicit imports.
  Use `# noqa: ARG002` on the method signature if arguments are unused in a stub.
- See `renderer_3d_quadcopter.py` for the established pattern.

---

## Verification Checklist

After completing all steps, verify:

- [ ] `PLUGIN_<NAME>` constant exists in `plugin_constants.py`
- [ ] `data_model_<plugin>.py` is importable and has no tkinter dependency
- [ ] `frontend_tkinter_<plugin>.py` exports `register_<plugin>_plugin()`
- [ ] `register_plugins()` in `__main__.py` imports and calls the register function
- [ ] `create_plugin_data_model()` handles the new plugin name
- [ ] New `data_model_*` import in `data_model_parameter_editor.py` is in alphabetical order
- [ ] `configuration_steps_schema.json` enum includes the new name
- [ ] Relevant `configuration_steps_*.json` files reference the plugin
- [ ] (If renderer) `renderer_<name>.py` has no wildcard imports; unused stub args use `# noqa: ARG002`
- [ ] `ARCHITECTURE_<plugin_name>.md` exists in the project root
- [ ] `pytest tests/ -v` passes
- [ ] `ruff check .` and `ruff format` pass
- [ ] `mypy` / `pyright` / `pylint` pass

---

## Reference: Touch-Point Summary

The same five mandatory touch-points are documented inline in the source:

- `plugin_constants.py` — top-of-file comment block
- `__main__.py → register_plugins()` — docstring
- `data_model_parameter_editor.py → create_plugin_data_model()` — docstring

## Lessons Learned

### Deferred imports inside functions avoid circular imports

The `frontend_tkinter_*` modules import `plugin_factory` at module level.  Importing
them at the top of `__main__.py` would create a circular import.  Always place the
`from frontend_tkinter_<plugin> import register_<plugin>_plugin` call **inside** the
`register_plugins()` function body, annotated with `# noqa: PLC0415`.
