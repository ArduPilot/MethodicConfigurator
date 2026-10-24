# AutoTune Acceleration Back-off Plugin Architecture

## Purpose and use

After AutoTune at minimum takeoff weight, this plugin scales the current New
roll, pitch and yaw acceleration limits by `minimum TOW / maximum TOW`.
For example, weights of 2 kg and 3 kg reduce 90000 to 60000. The weight entries
start with `Frame > Specifications > TOW min Kg` and `TOW max Kg` from the
vehicle project. Editing these entries affects this calculation only; it does
not save changes to the Frame specifications.

The plugin appears at `49_autotune_finish.param` for Copter and QuadPlane,
and the equivalent `73_autotune_finish.param` for Heli. Fixed-wing Plane
and Rover do not use these attitude-controller acceleration limits. QuadPlane
visibility requires a configured Frame class, as for the gain back-off plugin.
Customized project configuration JSON must include the same plugin and
`add_parameters` entries as the applicable bundled finish step.

## Components

| Responsibility | File under `ardupilot_methodic_configurator/` |
| --- | --- |
| Calculation and validation | `plugins/data_model_autotune_accel_backoff.py` |
| Weight entries, Apply button and feedback | `plugins/frontend_tkinter_autotune_accel_backoff.py` |
| Model and view factory registry | `plugins/plugin_factory.py` |
| Startup registration | `__main__.py`, `plugins/plugin_constants.py` |
| Step wiring and schema | `configuration_steps_*.json`, `configuration_steps_schema.json` |

## Data flow and behavior

Finish-step `add_parameters` entries copy available acceleration limits from
the loaded FC parameters, including firmware defaults. Existing staged values
are preserved. No default acceleration values are invented for offline use;
offline users can reduce the values already present in their finish file.
Both `ATC_` and QuadPlane `Q_A_` families are supported. Only existing limits
in the active finish step are changed; gains and throttle mix are untouched.

The view parses numeric input separately from domain validation. Weights must
be finite and positive, and minimum must not exceed maximum. Equal weights
leave values and reasons unchanged and disable Apply for the current visit.
A successful reduction adds the stable `@autotune_accel_backoff` marker to its
parameter change reasons. Fresh models detect that saved marker and disable
Apply after navigation or restart, preventing compounded reductions.
Existing English compensation reasons from earlier versions are also recognized.
Invalid input leaves the button available so the user can correct it.
Zero acceleration limits remain disabled.

The model validates all candidates on independent parameter copies before
applying changes. Read-only or forced values block the entire operation unless
an existing manual override makes them editable. Reasons record the prior New
value and both weights, preserving previous text and a single serialized
manual-override marker. Metadata range violations produce warnings after
staging, as in gain back-off. The view refreshes the parameter table.

## Firmware evidence

The plugin supports both naming schemes without a firmware gate because the
weight ratio is dimensionless:

- [Copter 4.6.3 attitude controller](https://github.com/ArduPilot/ardupilot/blob/Copter-4.6.3/libraries/AC_AttitudeControl/AC_AttitudeControl.cpp)
  defines `ACCEL_R_MAX`, `ACCEL_P_MAX` and `ACCEL_Y_MAX` in centidegrees/s².
- [Copter 4.7.0 attitude controller](https://github.com/ArduPilot/ardupilot/blob/Copter-4.7.0/libraries/AC_AttitudeControl/AC_AttitudeControl.cpp)
  replaces these with `ACC_R_MAX`, `ACC_P_MAX` and `ACC_Y_MAX` in degrees/s².
- [Copter parameter registration](https://github.com/ArduPilot/ardupilot/blob/Copter-4.6.3/ArduCopter/Parameters.cpp)
  registers the shared controller, including Heli, under `ATC_`.
- [QuadPlane controller registration](https://github.com/ArduPilot/ardupilot/blob/Plane-4.6.3/ArduPlane/quadplane.cpp)
  provides the shared attitude controller under the QuadPlane parameter family.

The requested ratio applies directly in either unit system, with no conversion.

## Lifecycle and verification

The factories inject only the parameter editor and local filesystem. The model
reads already-loaded project data and does no external I/O. Registration sets
`requires_flight_controller=False`. Save and upload use normal editor actions.
The view has no timers, subscriptions or connections to release; deactivation,
suspension and resumption retain inputs. Activation preserves the disabled
button and feedback after application; recreating a view with the same model
also keeps the button disabled.

All three platform PyInstaller specs already collect every submodule of
`ardupilot_methodic_configurator.plugins`, covering both new modules without
additional assets or dependencies. Tests cover calculation, invalid weights,
atomic validation, naming schemes, manual overrides, blocked repeated clicks, real
widgets, offline factories, startup registration, schema and vehicle wiring.
