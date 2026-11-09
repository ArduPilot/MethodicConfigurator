# ArduPilot Log Analysis

ArduPilot Methodic Configurator includes a Log Analysis feature that helps you inspect an ArduPilot `.bin` flight log.

It checks the availability of the recorded data and, when enough information is available, performs additional analysis of the vehicle.

The process is simple:

> Select a flight log, run the analysis, and use the results to find things that may need attention for a smooth and stable flight.

## What all can be analyzed?

The current Log Analysis system provides **detailed analysis** for:

* Attitude control saturation
* Battery
* ESC
* GPS/GNSS consistency and interference indicators
* IMU
* Vibration

It also performs **data availability checks only** (no detailed analysis yet) for:

* FFT
* Errors
* Performance Monitor
* Arming
* Flight Mode

Subsystems are checked for data availability first.
Those listed above can also produce detailed findings.

## Before you start

You need:

* [ArduPilot Methodic Configurator](https://github.com/ArduPilot/MethodicConfigurator)
* An ArduPilot `.bin` DataFlash log
* The correct vehicle project opened in Methodic Configurator (This is very important)

For the standalone report, pass a log path as a positional argument, for example
`python ardupilot_methodic_configurator/frontend_tkinter_log_analysis.py "path/to/flight.bin"`.
Use `--vehicle-dir` to supply the vehicle project for configuration context.
If no log path is supplied, a file selector opens.

The log should come from the same vehicle configuration that you are currently working with.
The tool checks the vehicle type and firmware version from the log against the currently opened project.
A log from a different vehicle or incompatible firmware version is rejected instead of being analyzed against the wrong configuration.

## Basic workflow

The complete workflow is:

```text
Flight
  |
  v
.bin log file
  |
  v
Select the log
  |
  v
Read and validate log
  |
  v
Check data availability
  |
  v
Run available analyses
  |
  v
Read results
  |
  v
Investigate reported issues

```

### 1. Get the flight log

The logs are stored in the SD card in your flight controller in:
`/APM/LOGS/`

Copy the `.bin` file to your computer.

### 2. Open your vehicle project

Open the vehicle project that corresponds to the flight log.
For example:

* Vehicle: ArduCopter
* Firmware: 4.6.3

Make sure you are using the correct project AMC before selecting the log.

### 3. Select the log

Open the Log Analysis section and select the `.bin` file.
The tool reads the log and extracts the information required for analysis.
This can include:

* Vehicle type
* Firmware version
* Parameters
* Logged messages
* Sensor data
* Vehicle configuration information

### 4. Log validation

Before performing the analysis, the log is checked against the currently opened vehicle project.

**Valid Example:**

* Project: Vehicle: ArduCopter, Firmware: 4.6.3
* Log: Vehicle: ArduCopter, Firmware: 4.6.3
* Result: Valid

**Rejected Example:**

* Project: Vehicle: ArduCopter
* Log: Vehicle: ArduPlane
* Result: Log rejected

This prevents a log from one vehicle from accidentally being analyzed using another vehicle's configuration.
Which can provide wrong analysis.

### 5. Data availability

Before running an analysis, the tool checks whether the required data exists and can be used.
This is important because a missing or invalid log message should not produce a misleading analysis result.

For example, the IMU data availability checks can detect:

* Missing IMU fields
* Missing IMU values
* Unhealthy gyroscope status
* Unhealthy accelerometer status
* Accelerometer errors
* Gyroscope signals that remain at zero
* Accelerometer signals that remain at zero

Data availability problem does not necessarily mean that the hardware is broken.
It may simply mean that the required information was not recorded correctly.

## Battery Analysis

Battery Analysis examines the battery information recorded in the BAT messages together with the vehicle's [battery monitor parameters]
(<https://ardupilot.org/copter/docs/common-powermodule-landingpage.html>).
It currently checks:

* Battery capacity usage
* Voltage extremes
* Battery efficiency
* Battery failsafe ordering
* Battery parameter derivation

If there is no usable battery data, the analysis reports that Battery Analysis is unavailable.

### Battery capacity usage

The analysis compares the amount of battery capacity used during the flight with the configured `BATT_CAPACITY`.

For example:

* Configured capacity: 1800 mAh
* Consumed: 900 mAh
* Usage: 50 %

This gives an indication of how much of the configured battery capacity was consumed.

### Battery voltage

The analysis examines the voltage recorded during the flight.
If unusual voltage values are reported, investigate:

* Battery condition
* [Battery monitor configuration](https://ardupilot.org/copter/docs/common-powermodule-landingpage.html)
* Battery wiring
* Vehicle load
* Battery parameters

Do not assume that an unusual voltage value automatically means that the battery is faulty.

### Battery failsafe parameters

Battery failsafe thresholds should be configured consistently.
If the analysis reports a problem with the battery thresholds, inspect the related parameters in Methodic Configurator before changing them.
The relevant parameters include:

* `BATT_LOW_VOLT`
* `BATT_CRT_VOLT`

### What should I do with a battery warning?

Use the following process:

```text
Battery warning
      |
      v
Read the finding
      |
      v
Check the related parameter
      |
      v
Check the battery monitor
      |
      v
Inspect the physical battery/system
      |
      v
Correct the problem

```

## ESC Analysis

ESC Analysis examines the [ESC information](https://ardupilot.org/copter/docs/common-esc-guide.html) available in the flight log.
ArduPilot can communicate with ESCs using several protocols, including:

* [PWM, OneShot, OneShot125](https://ardupilot.org/copter/docs/common-brushless-escs.html)
* [DShot](https://ardupilot.org/copter/docs/common-dshot-escs.html)
* [DroneCAN/CAN](https://ardupilot.org/copter/docs/common-uavcan-escs.html)

Depending on the ESC and protocol, [ESC telemetry](https://ardupilot.org/copter/docs/common-esc-telemetry.html) can provide additional information to the flight controller.
When ESC telemetry information is available, Log Analysis can use
it to identify potential problems.
If the required ESC information is not present in the log, a reliable ESC analysis cannot be performed.

The analysis currently checks:

* The spin margin between `MOT_SPIN_MIN` and `MOT_SPIN_ARM` (motors may not spin reliably once armed if this margin is too small)
* The effective DShot output rate, derived from `SCHED_LOOP_RATE` and `SERVO_DSHOT_RATE`
* Per-output current draw compared against the other ESC outputs, to flag one output that stands out from the rest
* Whether any ESC output reported zero RPM throughout a period the vehicle was armed

### If an ESC problem is reported

Check:

* ESC telemetry configuration
* ESC wiring
* Motor configuration
* Motor RPM
* Motor condition
* Propeller condition
* ESC communication protocol

An ESC finding does not automatically mean that the ESC itself is defective.
Use the finding as a starting point for further investigation.

## IMU Analysis

IMU Analysis checks the temperature calibration state of the vehicle's IMUs.
It examines parameters such as:

* `INS_TCAL1_ENABLE`
* `INS_TCAL2_ENABLE`
* `INS_TCAL3_ENABLE`

It also checks the calibration information associated with the accelerometer and gyroscope.

### Temperature calibration disabled

You may see a result such as:

> IMU 1 temperature calibration is not enabled. Consider running it for better accuracy across temperature changes.

This means temperature calibration is not enabled for that IMU.
If appropriate for the vehicle, follow the ArduPilot IMU temperature calibration procedure.

### Temperature calibration in progress

The analysis can also report that temperature calibration is still in progress.
This means the calibration has not yet reached its completed state.

### Accelerometer/gyroscope calibration prerequisite

Temperature calibration data can only be trusted if a 6-axis accelerometer and gyroscope calibration has already been performed.
If that prerequisite calibration is missing, the analysis reports that the IMU is marked as temperature-calibrated but the underlying
data may be unreliable, and recommends running the accelerometer and gyroscope calibration before relying on the temperature calibration.

### Invalid calibration

The analysis can detect inconsistent calibration information.
For example, an IMU may be marked as temperature-calibrated while the required accelerometer or gyroscope calibration temperature information is missing.
In this situation, the analysis recommends correcting the calibration before relying on the temperature calibration data.

### Missing temperature range

The temperature calibration data includes the temperature range over which calibration was performed.
If the required minimum or maximum temperature information is missing, the analysis reports an inconsistent state.

## Vibration Analysis

Vibration Analysis examines the VIBE data recorded during the flight. It checks:

* Vibration levels
* Accelerometer clipping

### Vibration levels

The analysis checks the three vibration axes: `VibeX`, `VibeY`, `VibeZ`.

The current analysis uses the following guidance levels, based on the [ArduPilot documentation on diagnosing common log problems](https://ardupilot.org/copter/docs/common-diagnosing-problems-using-logs.html):

* Vibration levels below 30 m/s/s are normally acceptable.
* Levels above 30 m/s/s may cause position or altitude-hold problems.
* Levels above 60 m/s/s nearly always indicate a more serious vibration problem.

### Common things to inspect

If high vibration is reported, check:

* Propellers
* Motors
* Motor mounting
* Frame
* [Flight controller mounting](https://ardupilot.org/copter/docs/common-vibration-damping.html)
* Loose screws
* Damaged components
* Propeller balance

Do not immediately change flight controller tuning parameters.
First find the physical source of the vibration.

### Accelerometer clipping

The analysis also checks for accelerometer clipping events.
Clipping occurs when the measured acceleration reaches the sensor's measurable limit.
If clipping is reported, investigate the cause before continuing with detailed tuning.

## Attitude Saturation Analysis

Attitude Saturation Analysis checks Copter and helicopter logs for evidence of attitude-control limiting while the vehicle was armed.
It needs the `ATT` and `RATE` messages (LOG_BITMASK *Fast Attitude* or *Medium Attitude*)
and the `PIDR`, `PIDP` and `PIDY` messages (LOG_BITMASK *PID*).
Checks whose messages or parameters are not available are skipped.

Each finding reports elapsed seconds and the percentage of the relevant armed time.
Sample intervals are weighted before selecting armed periods or flight modes, so uneven logging does not inflate the percentage.
For these duration estimates, each observed value is held until the next sample,
splitting its interval at ARM, MODE, mission-item (MISE or legacy CMD), Guided target and parameter changes.
The final sample contributes no unobserved time beyond the end of the data.
Before the first ARM transition, the vehicle is assumed to have the opposite state.
This includes the armed portion of default `LOG_DISARMED=0` logs whose initial arm event occurred before logging started.
An unmatched arm event remains effective through the end of the observed data.
When there are no ARM records, the analysis uses all observed time.
Limits changed during the flight are evaluated using the logged parameter history.
A finding is rated *critical* when attitude control is severely reduced, otherwise *warning*.

| Limit | Detected by | Critical when |
| ----- | ----------- | ------------- |
| `ATC_RATE_R_MAX`, `ATC_RATE_P_MAX` | Normalised roll/pitch target length `sqrt((RDes/R_MAX)^2 + (PDes/P_MAX)^2)` at or above 0.98 when both limits are enabled; otherwise the enabled axis alone | Near the envelope for 10% or more of the armed time |
| `ATC_RATE_Y_MAX` | Magnitude of `RATE.YDes` at or above 98% of the configured limit | Near the envelope for 10% or more of the armed time |
| `ATC_RAT_RLL_SMAX`, `ATC_RAT_PIT_SMAX`, `ATC_RAT_YAW_SMAX` | Slew limiter scaling P and D down (`PID*.Dmod`) | Gains below 50% for 5% or more of the armed time |
| `ATC_RAT_RLL_PDMX`, `ATC_RAT_PIT_PDMX`, `ATC_RAT_YAW_PDMX` | P+D sum limit flag (`PID*.Flags`) | Active for 10% or more of the armed time |
| `ANGLE_MAX` (`ATC_ANGLE_MAX` since 4.7), `PSC_ANGLE_MAX` | Final desired lean angle (`ATT.DesRoll`, `DesPitch`) at the applicable ceiling | Never, always a warning |

Absent or disabled rate, slew and P+D limit parameters are skipped.
Short episodes are ignored: a finding needs the limit to be active for at least 1% of the time or at least one second in total.
Rate targets provide indirect evidence: reaching or exceeding the configured envelope does not prove that a limiter clipped the target.
Compare desired and measured rates and check disturbances before changing a rate limit.
The shared roll/pitch ellipse is defined by
[`AC_AttitudeControl::ang_vel_limit` in Copter 4.6.3](https://github.com/ArduPilot/ardupilot/blob/Copter-4.6.3/libraries/AC_AttitudeControl/AC_AttitudeControl.cpp).

### Lean-angle limits

The lean-angle check uses the limit that applies to the flight mode (from the `MODE` messages) active at each moment:

* In supported position-controlled modes (including Loiter, Auto and RTL), a positive `PSC_ANGLE_MAX` is used directly,
  even when it is larger than the vehicle pilot limit.
  When it is absent or 0, the vehicle limit is used.
  In Auto, `GUIA` attitude commands (including NAVGUIDED companion and NAV_SCRIPT_TIME Lua attitude legs)
  bypass the horizontal position controller. Their intervals are skipped until the next `MODE`, `GUIP` or executing
  navigation item: `MISE` in Copter 4.6+, with `CMD` as the fallback for older logs without `MISE`.
  DO and condition items do not end an attitude leg; uploaded-mission `CMD` dumps are ignored when `MISE` is present.
  NAV_ATTITUDE_TIME (`CId` 42703) also bypasses horizontal position control without emitting `GUIA`,
  so its interval is skipped until navigation resumes.
* Guided is checked only while `GUIP` records identify position targets in the current Guided session.
  `GUIA` attitude targets bypass the horizontal position controller, so their intervals are skipped.
  Guided intervals without target evidence and Guided_NoGPS are also skipped.
* `LOIT_ANG_MAX` limits the pilot's input in Loiter. Position corrections can produce final ATT targets above that value,
  so this analysis does not infer pilot-limit saturation from those targets.
* In supported pilot lean-angle modes, `ANGLE_MAX` (`ATC_ANGLE_MAX`) is used.
* Land is skipped because `MODE` does not distinguish horizontal position control from the no-GPS pilot lean path.
* FlowHold is skipped because it uses its own per-axis angle constraints, which this final-tilt check does not model.
* Acro, Flip, AutoTune, Throw, SystemID, Autorotate and Turtle are ignored because they are not bound by the pilot lean-angle limit.
* Samples with no known applicable MODE record are skipped.

The Guided target message meanings are defined in
[`Log.cpp` in Copter 4.6.3](https://github.com/ArduPilot/ardupilot/blob/Copter-4.6.3/ArduCopter/Log.cpp).
[`ModeGuided::angle_control_run`](https://github.com/ArduPilot/ardupilot/blob/Copter-4.6.3/ArduCopter/mode_guided.cpp)
passes attitude commands directly to the attitude controller;
[`ModeGuidedNoGPS::run`](https://github.com/ArduPilot/ardupilot/blob/Copter-4.6.3/ArduCopter/mode_guided_nogps.cpp)
uses that same path.
Auto's navigation-item classification is defined in
[`AP_Mission::is_nav_cmd` in Copter 4.6.3](https://github.com/ArduPilot/ardupilot/blob/Copter-4.6.3/libraries/AP_Mission/AP_Mission.cpp),
and [`ModeAuto::nav_attitude_time_run`](https://github.com/ArduPilot/ardupilot/blob/Copter-4.6.3/ArduCopter/mode_auto.cpp)
sends roll/pitch targets directly to the attitude controller.

The alternative Land control paths are defined in
[`ModeLand` in Copter 4.6.3](https://github.com/ArduPilot/ardupilot/blob/Copter-4.6.3/ArduCopter/mode_land.cpp).
FlowHold's separate angle constraints are defined in
[`ModeFlowHold` in Copter 4.6.3](https://github.com/ArduPilot/ardupilot/blob/Copter-4.6.3/ArduCopter/mode_flowhold.cpp).
Rate, slew and P+D limit checks still apply in both modes.

See the final position ceiling in
[`AC_PosControl` in Copter 4.6.3](https://github.com/ArduPilot/ardupilot/blob/Copter-4.6.3/libraries/AC_AttitudeControl/AC_PosControl.cpp)
and the separate pilot input limit in
[`AC_Loiter`](https://github.com/ArduPilot/ardupilot/blob/Copter-4.6.3/libraries/AC_WPNav/AC_Loiter.cpp).
The renamed degree-based `ATC_ANGLE_MAX` is present in
[`AC_AttitudeControl` in Copter 4.7.0](https://github.com/ArduPilot/ardupilot/blob/Copter-4.7.0/libraries/AC_AttitudeControl/AC_AttitudeControl.cpp).

In position-controlled modes, lean-angle saturation indicates that the vehicle could not tilt further to follow the demanded acceleration.
Raise the reported parameter if the airframe and payload allow it.
In pilot lean-angle modes such as Stabilize, the finding reports use of the full pilot lean range.
Review pilot inputs and the configured lean range; full stick alone does not indicate a position-controller limit.
Pilot and position-controlled periods receive separate findings even when they use the same parameter.

### Rate-controller saturation

A critical rate-limit finding means that RATE targets frequently reached the configured `ATC_RATE_*_MAX` envelope.
This suggests rate limiting but does not prove clipping.
Check target tracking and disturbances before raising the limit.

Critical slew-limiter or P+D sum-limit findings indicate reduced attitude-control authority.
Review the P and D gains and the reported limit.
A slew limiter that is frequently active also indicates an oscillation tendency.

## When an analysis is unavailable

You may see a result such as:

> No BAT data available for analysis

or:

> No VIBE data available for analysis

This does not automatically mean that there is a hardware problem.
It may simply mean that the required message was not recorded in the log.
For example, Vibration Analysis requires usable VIBE data.

If an analysis is unavailable:

1. Check whether the corresponding message exists in the log.
2. Check the vehicle's logging configuration.
3. Make another flight if necessary.
4. Analyze the new log.

## Understanding the results

A result can contain information such as:

* What was detected
* Measured value
* Time of the event
* Related parameter
* Suggested parameter value
* Related Methodic Configurator step

For example:

> IMU 1 temperature calibration is not enabled.

The important part is not only the warning itself.
Use the related parameter or configuration step to understand what should be checked next.

### What to do when a problem is reported

Do not blindly change parameters.
Use this workflow:

```text
Finding
  |
  v
Understand the issue
  |
  v
Check the related data
  |
  v
Check parameter/configuration
  |
  v
Inspect hardware if necessary
  |
  v
Correct the problem
  |
  v
Fly again
  |
  v
Analyze new log

```

The purpose of Log Analysis is to help identify problems and guide investigation.
It is not yet intended to automatically change vehicle parameters.
In the upcoming versions that can also be done.

## Recommended flight log workflow

### Before the flight

Make sure:

* The vehicle is correctly configured.
* Sensors are correctly configured.
* Required logging is enabled.
* The battery monitor is configured.
* ESC telemetry is configured when available.
* Required calibrations have been completed.

### During the flight

* Fly the vehicle normally.
* Avoid intentionally creating failures simply to test the analysis.
* Generate enough flight data for the systems you want to analyze.

### After the flight

1. Copy the `.bin` log from the flight controller.
2. Open the correct Methodic Configurator project.
3. Select the log.
4. Run Log Analysis.
5. Check the data availability results.
6. Read the analysis results.
7. Investigate reported issues.
8. Correct the underlying problem.
9. Perform another flight.
10. Analyze the new log again.

## Important notes

Log Analysis depends on the information recorded in the flight log.
A missing analysis result does not automatically mean that the vehicle is healthy.
Similarly, a reported issue does not automatically mean that a hardware component has failed.
Always investigate the finding together with the vehicle configuration and the original flight conditions.

## Frequently asked questions

**Do I need a `.bin` file?**
Yes. The Log Analysis feature works with ArduPilot DataFlash `.bin` logs.

**Can I analyze a log from another vehicle?**
When analysing the log using AMC the log must match the currently opened vehicle project.
The tool validates the vehicle type and firmware version before continuing.

**Why is an analysis unavailable?**
Usually because the required log data is missing or cannot be used.
Check whether the required message was recorded in the log.

**Does a warning mean something is broken?**
Not necessarily. A warning identifies something that should be investigated.

**Should I immediately change the parameter mentioned in a warning?**
No. First understand why the value was reported and check the related Methodic Configurator step.

**Why does the tool check data availability first?**
Because an analysis based on missing or invalid data could produce a misleading result.

## Useful ArduPilot documentation

* [ArduPilot Documentation](https://ardupilot.org/)
* [Copter Documentation](https://ardupilot.org/copter/index.html)
* [ArduPilot Methodic Configurator](https://github.com/ArduPilot/MethodicConfigurator)
* [ESC (Electronic Speed Controls) Guide](https://ardupilot.org/copter/docs/common-esc-guide.html)
* [Battery Monitor Documentation](https://ardupilot.org/copter/docs/common-powermodule-landingpage.html)
* [Mounting the Autopilot / Vibration Damping](https://ardupilot.org/copter/docs/common-vibration-damping.html)
* [Motor Thrust Scaling](https://ardupilot.org/copter/docs/motor-thrust-scaling.html)
* [Diagnosing Common Problems Using Logs](https://ardupilot.org/copter/docs/common-diagnosing-problems-using-logs.html)

## Summary

The Log Analysis feature makes it easier to understand what happened during an ArduPilot flight.

Current detailed analyses include Attitude Saturation, Battery, ESC, IMU, Vibration, and GPS/GNSS.
The system also performs data availability checks for other vehicle subsystems (FFT, Errors, Performance Monitor, Arming, and Flight Mode).
The best results come from a correctly configured vehicle, a complete flight log, and investigating the reported findings
rather than blindly changing parameters.
