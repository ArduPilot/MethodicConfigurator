# ArduPilot Log Analysis

ArduPilot Methodic Configurator includes a Log Analysis feature that helps you inspect an ArduPilot `.bin` flight log.

It checks the quality of the recorded data and, when enough information is available, performs additional analysis of the vehicle.

The process is simple:

> Select a flight log, run the analysis, and use the results to find things that may need attention for a smooth and stable flight.

## What all can be analyzed?

The current Log Analysis system provides **detailed analysis** for:

* Battery
* ESC
* IMU
* Vibration

It also performs **data quality checks only** (no detailed analysis yet) for:

* GPS
* FFT
* Errors
* Performance Monitor
* Arming
* Flight Mode

All ten subsystems are checked for data quality first. Only the four listed above currently go on to produce detailed findings; the other six report whether their data is
present and usable.

## Before you start

You need:

* [ArduPilot Methodic Configurator](https://github.com/ArduPilot/MethodicConfigurator)
* An ArduPilot `.bin` DataFlash log
* The correct vehicle project opened in Methodic Configurator (This is very important)

The log should come from the same vehicle configuration that you are currently working with. The tool checks the vehicle type and firmware version from the log
against the currently opened project. A log from a different vehicle or incompatible firmware version is rejected instead of being analyzed against the wrong configuration.

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
Check data quality
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

Open the Log Analysis section and select the `.bin` file. The tool reads the log and extracts the information required for analysis. This can include:

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

### 5. Data quality

Before running an analysis, the tool checks whether the required data exists and can be used. This is important because a missing or invalid log message should not produce
a misleading analysis result.

For example, the IMU quality checks can detect:

* Missing IMU fields
* Missing IMU values
* Unhealthy gyroscope status
* Unhealthy accelerometer status
* Accelerometer errors
* Gyroscope signals that remain at zero
* Accelerometer signals that remain at zero

A quality problem does not necessarily mean that the hardware is broken. It may simply mean that the required information was not recorded correctly.

## Battery Analysis

Battery Analysis examines the battery information recorded in the BAT messages together with the vehicle's [battery monitor parameters]
(<https://ardupilot.org/copter/docs/common-battery-monitor-landing-page.html>). It currently checks:

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

The analysis examines the voltage recorded during the flight. If unusual voltage values are reported, investigate:

* Battery condition
* [Battery monitor configuration](https://ardupilot.org/copter/docs/common-battery-monitor-landing-page.html)
* Battery wiring
* Vehicle load
* Battery parameters

Do not assume that an unusual voltage value automatically means that the battery is faulty.

### Battery failsafe parameters

Battery failsafe thresholds should be configured consistently. If the analysis reports a problem with the battery thresholds, inspect the related parameters in
Methodic Configurator before changing them.
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

ESC Analysis examines the [ESC information](https://ardupilot.org/copter/docs/common-esc-guide.html) available in the flight log. ArduPilot can communicate with ESCs
using several protocols, including:

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

An ESC finding does not automatically mean that the ESC itself is defective. Use the finding as a starting point for further investigation.

## IMU Analysis

IMU Analysis checks the temperature calibration state of the vehicle's IMUs. It examines parameters such as:

* `INS_TCAL1_ENABLE`
* `INS_TCAL2_ENABLE`
* `INS_TCAL3_ENABLE`

It also checks the calibration information associated with the accelerometer and gyroscope.

### Temperature calibration disabled

You may see a result such as:

> IMU 1 temperature calibration is not enabled. Consider running it for better accuracy across temperature changes.

This means temperature calibration is not enabled for that IMU. If appropriate for the vehicle, follow the ArduPilot IMU temperature calibration procedure.

### Temperature calibration in progress

The analysis can also report that temperature calibration is still in progress. This means the calibration has not yet reached its completed state.

### Accelerometer/gyroscope calibration prerequisite

Temperature calibration data can only be trusted if a 6-axis accelerometer and gyroscope calibration has already been performed. If that prerequisite calibration is
missing, the analysis reports that the IMU is marked as temperature-calibrated but the underlying data may be unreliable, and recommends running the accelerometer
and gyroscope calibration before relying on the temperature calibration.

### Invalid calibration

The analysis can detect inconsistent calibration information. For example, an IMU may be marked as temperature-calibrated while the required accelerometer or gyroscope
calibration temperature information is missing. In this situation, the analysis recommends correcting the calibration before relying on the temperature calibration data.

### Missing temperature range

The temperature calibration data includes the temperature range over which calibration was performed. If the required minimum or maximum temperature information is missing,
the analysis reports an inconsistent state.

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

Do not immediately change flight controller tuning parameters. First find the physical source of the vibration.

### Accelerometer clipping

The analysis also checks for accelerometer clipping events. Clipping occurs when the measured acceleration reaches the sensor's measurable limit. If clipping is reported,
investigate the cause before continuing with detailed tuning.

## When an analysis is unavailable

You may see a result such as:

> No BAT data available for analysis

or:

> No VIBE data available for analysis

This does not automatically mean that there is a hardware problem. It may simply mean that the required message was not recorded in the log. For example,
Vibration Analysis requires usable VIBE data.

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

The important part is not only the warning itself. Use the related parameter or configuration step to understand what should be checked next.

### What to do when a problem is reported

Do not blindly change parameters. Use this workflow:

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

The purpose of Log Analysis is to help identify problems and guide investigation. It is not yet intended to automatically change vehicle parameters.
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
5. Check the data quality results.
6. Read the analysis results.
7. Investigate reported issues.
8. Correct the underlying problem.
9. Perform another flight.
10. Analyze the new log again.

## Important notes

Log Analysis depends on the information recorded in the flight log. A missing analysis result does not automatically mean that the vehicle is healthy.
Similarly, a reported issue does not automatically mean that a hardware component has failed. Always investigate the finding together with the
vehicle configuration and the original flight conditions.

## Frequently asked questions

**Do I need a `.bin` file?**
Yes. The Log Analysis feature works with ArduPilot DataFlash `.bin` logs.

**Can I analyze a log from another vehicle?**
When analysing the log using AMC the log must match the currently opened vehicle project. The tool validates the vehicle type and firmware version before continuing.

**Why is an analysis unavailable?**
Usually because the required log data is missing or cannot be used. Check whether the required message was recorded in the log.

**Does a warning mean something is broken?**
Not necessarily. A warning identifies something that should be investigated.

**Should I immediately change the parameter mentioned in a warning?**
No. First understand why the value was reported and check the related Methodic Configurator step.

**Why does the tool check data quality first?**
Because an analysis based on missing or invalid data could produce a misleading result.

## Useful ArduPilot documentation

* [ArduPilot Documentation](https://ardupilot.org/)
* [Copter Documentation](https://ardupilot.org/copter/index.html)
* [ArduPilot Methodic Configurator](https://github.com/ArduPilot/MethodicConfigurator)
* [ESC (Electronic Speed Controls) Guide](https://ardupilot.org/copter/docs/common-esc-guide.html)
* [Battery Monitor Documentation](https://ardupilot.org/copter/docs/common-battery-monitor-landing-page.html)
* [Mounting the Autopilot / Vibration Damping](https://ardupilot.org/copter/docs/common-vibration-damping.html)
* [Motor Thrust Scaling](https://ardupilot.org/copter/docs/motor-thrust-scaling.html)
* [Diagnosing Common Problems Using Logs](https://ardupilot.org/copter/docs/common-diagnosing-problems-using-logs.html)

## Summary

The Log Analysis feature makes it easier to understand what happened during an ArduPilot flight.

Current detailed analyses include Battery, ESC, IMU, and Vibration. The system also performs data quality checks for other vehicle subsystems (GPS, FFT, Errors, Performance
Monitor, Arming, and Flight Mode). The best results come from a correctly configured vehicle, a complete flight log, and investigating the reported findings rather than
blindly changing parameters.
