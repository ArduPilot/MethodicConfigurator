<!--
SPDX-FileCopyrightText: 2026 Amilcar do Carmo Lucas
SPDX-License-Identifier: GPL-3.0-or-later
-->

# AutoTune gain margin back-off

## Firmware research

`AUTOTUNE_GMBK` first shipped in Copter-4.7.0: it is present in the
[Copter-4.7.0 source](https://github.com/ArduPilot/ardupilot/blob/Copter-4.7.0/libraries/AC_AutoTune/AC_AutoTune_Multi.cpp#L118-L123)
and absent from the corresponding
[Copter-4.6.3 source](https://github.com/ArduPilot/ardupilot/blob/Copter-4.6.3/libraries/AC_AutoTune/AC_AutoTune_Multi.cpp).
The implementation details below are based on the
[Copter-4.7.0 source](https://github.com/ArduPilot/ardupilot/blob/Copter-4.7.0/libraries/AC_AutoTune/AC_AutoTune_Multi.cpp).

- `AUTOTUNE_GMBK` is a fraction in **0.0-0.5**, default **0.25**.
- [`set_tuning_gains_with_backoff()`](https://github.com/ArduPilot/ardupilot/blob/Copter-4.7.0/libraries/AC_AutoTune/AC_AutoTune_Multi.cpp#L909-L936)
  constrains the fraction and
  multiplies rate P and D by `1 - GMBK` when rate P tuning completes.
  Ordinary yaw tuning reduces P only; yaw-D tuning reduces both P and D.
- [Angle P back-off](https://github.com/ArduPilot/ardupilot/blob/Copter-4.7.0/libraries/AC_AutoTune/AC_AutoTune_Multi.cpp#L940-L953)
  multiplies angle P by
  `(1 - GMBK) * (1 - AUTOTUNE_AGGR)`. Aggressiveness is a separate factor.
- [Rate I derivation](https://github.com/ArduPilot/ardupilot/blob/Copter-4.7.0/libraries/AC_AutoTune/AC_AutoTune_Multi.cpp#L53-L55)
  and the [roll, pitch and yaw tuning paths](https://github.com/ArduPilot/ardupilot/blob/Copter-4.7.0/libraries/AC_AutoTune/AC_AutoTune_Multi.cpp#L415-L459)
  derive final rate I from backed-off P.
  Roll/pitch I equals P; yaw I equals `0.1 * P`.
  Therefore I is indirectly reduced by the same fraction.

| Results axis | Rate gains | Angle gain |
| --- | --- | --- |
| Roll | `ATC_RAT_RLL_P`, `_I`, `_D` | `ATC_ANG_RLL_P` |
| Pitch | `ATC_RAT_PIT_P`, `_I`, `_D` | `ATC_ANG_PIT_P` |
| Yaw | `ATC_RAT_YAW_P`, `_I` | `ATC_ANG_YAW_P` |
| Yaw-D | `ATC_RAT_YAW_P`, `_I`, `_D` | `ATC_ANG_YAW_P` |

The shared multicopter AutoTune also serves QuadPlane: equivalent attitude
gains use `Q_A_` instead of `ATC_`. Acceleration limits, feed-forward gains,
filters, slew limits and integrator limits are not scaled by `GMBK`.

Helicopter AutoTune has a [separate implementation](https://github.com/ArduPilot/ardupilot/blob/Copter-4.7.0/libraries/AC_AutoTune/AC_AutoTune_Heli.cpp#L1167-L1216)
using fixed back-off constants rather than `GMBK`. This feature does not
reproduce the Heli or fixed-wing AutoTune algorithms; it offers additional
scaling of supported attitude gains in eligible AMC results steps. On
ArduPlane, it is shown only for QuadPlane projects, whose gains use `Q_A_`.
Because Heli firmware does not gain the multicopter `AUTOTUNE_GMBK` control in
4.7.0, the plugin remains available for Heli results regardless of firmware
version.

## AMC behavior

The `autotune_gain_backoff` plugin is configured above the parameter table in
the bundled Copter and Heli results steps and in ArduPlane results steps for
QuadPlane projects, including the legacy Heli result filenames in the bundled
OMP_M4 template. It is hidden for fixed-wing Plane and is not wired into Rover
steps. For Copter and QuadPlane it appears only when the project's firmware
version is below 4.7.0, because Copter-4.7.0 first includes `AUTOTUNE_GMBK`.
For Heli it remains available at all firmware versions. It works offline.

Enter a fraction from **0.0 to 0.5**, press **Apply back-off**, and review the
changed **New values** before the normal save/upload workflow.

One click applies `new_value = current_new_value * (1 - fraction)` to supported
gains present in the active step, restricted to that step's tuned axes.
Roll/pitch retuning affects both axes. Missing parameters are not added.
Rate I is scaled proportionally, preserving the user's existing I/P ratio
rather than imposing firmware ratios on previously edited results.

Every click is an **additional**, compounding reduction. Two clicks at `0.25`
retain `0.75 * 0.75 = 0.5625` of the initial staged gains. Firmware-saved
results may already include back-off; the plugin warns about this explicitly.
It neither reverses existing firmware back-off nor reapplies `AUTOTUNE_AGGR`.
It does not change the `AUTOTUNE_GMBK` parameter itself.

All affected values are validated before any value changes. Invalid input,
non-editable gains or invalid gains abort without partial changes.
Metadata range violations do not prevent the reduction: New values are changed
and a warning popup lists the recommended-range violations afterward.
Zero back-off and zero gains are no-ops.
Existing change reasons are preserved. Each click appends the pre-click New
value and reduction percentage, for example `Existing reason; 0.16 backed-off
by 25%`.
FC values, other steps and files are not modified by the button.

Custom project configuration JSON overrides the bundled configuration.
To enable the plugin in an existing customized results step, add:

```json
"plugin": {
    "name": "autotune_gain_backoff",
    "placement": "top",
    "if": "Version(vehicle_components['Flight Controller']['Firmware']['Version'].split(' ')[0]) < Version('4.7.0')"
}
```
