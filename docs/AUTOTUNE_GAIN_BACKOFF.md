# AutoTune gain margin back-off

## Firmware research

The local ArduPilot checkout was inspected using CodeGraph and on-disk source
at commit `cafe67457776027a1bad6e165c409828c1a851e5`.

In `../ardupilot/libraries/AC_AutoTune/AC_AutoTune_Multi.cpp`:

- Lines 118-123: `AUTOTUNE_GMBK` is a fraction in **0.0-0.5**, default **0.25**.
- Lines 909-936: `set_tuning_gains_with_backoff()` constrains the fraction and
  multiplies rate P and D by `1 - GMBK` when rate P tuning completes.
  Ordinary yaw tuning reduces P only; yaw-D tuning reduces both P and D.
- Lines 940-953: angle P is multiplied by
  `(1 - GMBK) * (1 - AUTOTUNE_AGGR)`. Aggressiveness is a separate factor.
- Lines 53-55, 415-459 and 544-625: final rate I is derived from backed-off P.
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

Helicopter AutoTune has a separate implementation in
`AC_AutoTune_Heli.cpp:1167-1216`, using fixed back-off constants rather than
`GMBK`. This feature does not claim to reproduce helicopter or fixed-wing
AutoTune. It offers additional scaling of supported attitude gains wherever
they are present in an AMC results step.

## AMC behavior

The `autotune_gain_backoff` plugin is configured above the parameter table in
all 20 bundled `XX_autotune_*_results.param` steps, **only when the project's
firmware version is below 4.7.0**. It works offline. The existing plugin `if`
evaluation hides it when the firmware version cannot be resolved.

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
Existing change reasons are preserved and the additional reduction is appended.
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
