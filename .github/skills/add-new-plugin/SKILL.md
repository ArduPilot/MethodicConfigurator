---
name: add-new-plugin
description: 'Create or extend an AMC parameter-editor plugin. Covers plugin-local model/view factories, startup registration, schema and step wiring, lifecycle, offline operation, conditional visibility, architecture documentation and tests.'
argument-hint: 'plugin name (e.g. radio_calibration)'
---

# Add or Extend an AMC Plugin

Read `.github/copilot-instructions.md` and relevant architecture guidance.
Use CodeGraph when available to inspect `PluginFactory`, `PluginModelContext`,
`ParameterEditor.create_plugin_data_model()` and a similar existing plugin.

## Integration points

Plugin-specific Python modules belong in
`ardupilot_methodic_configurator/plugins/`, not the package root.

1. Add `PLUGIN_<NAME>` in `plugins/plugin_constants.py`.
2. Create `plugins/data_model_<name>.py` with typed business logic dependencies.
3. Create `plugins/frontend_tkinter_<name>.py` with the view and both factories.
4. Add `(module_name, registration_function_name)` to the lazy `registrations`
   tuple in `__main__.py:register_plugins()`. Preserve independent import/error
   handling so one broken plugin does not prevent others from registering.
5. Append the name to `configuration_steps_schema.json` at
   `plugin > properties > name > enum`.
6. Wire relevant `configuration_steps_<VehicleType>.json` entries.
7. Document architecture in `ARCHITECTURE_<name>.md` in the project root.

Do **not** add plugin-specific imports or branches to
`ParameterEditor.create_plugin_data_model()`. It delegates to registered model
factories using `PluginModelContext`. The four shared source integration points
are the constant, startup registration, plugin-local registration and schema;
step wiring and documentation complete the feature.

## Factory pattern

Use actual plugin types for view constructors. Factory adapters accept shared
interfaces; follow existing narrowly scoped typing adaptations.

```python
from ardupilot_methodic_configurator.plugins.plugin_constants import PLUGIN_EXAMPLE
from ardupilot_methodic_configurator.plugins.plugin_factory import PluginModelContext, plugin_factory


def _create_model(context: PluginModelContext) -> ExampleDataModel:
    return ExampleDataModel(context.parameter_editor)


def _create_view(parent: tk.Frame | ttk.Frame, model: object, base_window: object) -> ExampleView:
    return ExampleView(parent, model, base_window)  # type: ignore[arg-type]


def register_example_plugin() -> None:
    plugin_factory.register(
        PLUGIN_EXAMPLE,
        _create_view,
        _create_model,
        requires_flight_controller=False,
    )
```

The context provides `flight_controller`, `local_filesystem` and
`parameter_editor`; inject only needed dependencies. FC-required plugins use
`requires_flight_controller=True` (the default). Explicitly opt out for plugins
that transform staged parameters and should work offline.

## Step wiring and conditions

`placement` is `"left"` or `"top"`. Use existing JSON `"if"` support for
firmware/component-dependent visibility instead of duplicating rules in views.
For example, a plugin restricted to firmware below 4.7.0:

```json
"plugin": {
    "name": "example",
    "placement": "top",
    "if": "Version(vehicle_components['Flight Controller']['Firmware']['Version'].split(' ')[0]) < Version('4.7.0')"
}
```

`ParameterEditor.get_plugin()` evaluates conditions and hides plugins when
false or evaluation fails. Test thresholds and unresolved versions as relevant.
Use existing version sources consistently; do not assume a connected FC.
Respect requested comparison semantics, including prereleases.

Update every applicable bundled vehicle-type JSON. Customized project JSON
can override bundled configuration: document required custom-project wiring.

## Views, lifecycle and staged values

- Keep domain rules in models, without Tkinter or external I/O in pure domain
  calculations. Use existing backend adapters for external operations.
- Implement `PluginView` behavior, including activation, deactivation and
  destruction. Cancel timers, callbacks and resources when hidden or removed.
  Simple views can have no-op lifecycle hooks.
- Wrap user-facing text in `_()` and provide tooltips for interactive controls.
- Use `BaseWindow` for standalone windows; follow existing embedded-view patterns.
- Distinguish editing New values from saving or uploading to the FC.
- Respect read-only, forced/derived and metadata constraints. Validate bulk
  edits before mutation or explicitly report partial outcomes.
- Preserve change reasons where appropriate. Refresh with existing helpers in
  `plugins/frontend_tkinter_helpers.py`.
- Define whether repeated clicks compound, replace or are idempotent. Test this
  behavior and disclose potentially surprising effects in the UI.

Optional renderer modules also belong under `plugins/`; keep them independent
of Tkinter. Do not add a renderer if ordinary widgets suffice.

## Documentation and verification

Architecture documentation should explain components, file map, requirements,
data flow, external operations and lifecycle. Link domain research separately
when useful; verify firmware claims against source.

Follow `.github/skills/pytest-testing/SKILL.md`. Test:

- Real domain objects, boundary inputs and unrelated parameter preservation.
- View/button behavior, invalid input, table refresh and lifecycle cleanup.
- Model/view factory registration, startup and FC requirements.
- Configuration/schema coverage and conditional visibility.
- Repeated-action semantics and bulk-edit failure behavior.

Run focused and affected regression tests, Ruff formatting/checks, type checks
and Pylint. Use markdownlint for Markdown, not Ruff. Distinguish pre-existing
or environment errors from regressions. Sync CodeGraph when appropriate.

Verify importability, registration, schema, eligible steps, tests and architecture
documentation before finishing. Keep inline guidance in `plugin_constants.py`
and `__main__.py` consistent with the factory design.
