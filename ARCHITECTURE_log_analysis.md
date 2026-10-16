# Log Analysis Architecture

The Log Analysis subsystem provides a structured pipeline for analyzing ArduPilot `.bin` flight logs inside ArduPilot Methodic Configurator.

The subsystem separates log extraction, data availability validation, log analysis, configuration validation, hardware extraction, and result presentation.

## The Log Analysis Architecture

The log analysis subsystem follows the same backend, data-model, and frontend separation used throughout Methodic Configurator.

The main components are:

1. **Log Analysis Backend** - Loads and validates ArduPilot `.bin` logs and prepares the data required by the analysis layer.

   * [`backend_log_analysis.py`](https://github.com/ArduPilot/MethodicConfigurator/blob/master/ardupilot_methodic_configurator/log_analysis/backend_log_analysis.py)

2. **Log Analysis Data Models** - Contains the analysis pipeline, shared context, availability models, analysis models, and result structures.

   * [`data_model_log_analysis.py`](https://github.com/ArduPilot/MethodicConfigurator/blob/master/ardupilot_methodic_configurator/log_analysis/data_model_log_analysis.py)
   * [`data_model_log_analysis_context.py`](https://github.com/ArduPilot/MethodicConfigurator/blob/master/ardupilot_methodic_configurator/log_analysis/data_model_log_analysis_context.py)
   * [`data_model_parameter_derivation.py`](https://github.com/ArduPilot/MethodicConfigurator/blob/master/ardupilot_methodic_configurator/log_analysis/data_model_parameter_derivation.py)
   * [`data_model_log_availability.py`](https://github.com/ArduPilot/MethodicConfigurator/blob/master/ardupilot_methodic_configurator/log_analysis/data_model_log_availability.py)
   * [`data_model_log_availability_check.py`](https://github.com/ArduPilot/MethodicConfigurator/blob/master/ardupilot_methodic_configurator/log_analysis/data_model_log_availability_check.py)
   * [`data_model_availability_base.py`](https://github.com/ArduPilot/MethodicConfigurator/blob/master/ardupilot_methodic_configurator/log_analysis/data_model_availability_base.py)

3. **Availability and Analysis Models** - Performs subsystem-specific data validation and analysis.

   * Battery
   * ESC
   * IMU
   * VIBE
   * FFT
   * GPS
   * ERR
   * PM
   * ARM
   * MODE

4. **Result Models** - Provides common result structures consumed by the frontend and report-generation layers.

   * `LogAvailabilityResult`
   * `LogAnalysisResult`
   * `LogSummary`
   * `StepValidationResult`
   * `HardwareReport`

## Log Extraction

The log extraction backend reads an ArduPilot `.bin` flight log and creates the internal `LogData` representation.

The extraction layer is responsible for parsing the log and providing the data required by the analysis models. Individual analysis models do not parse the `.bin` file
themselves.

The extraction backend can also report progress through a callback so that the frontend can display parsing progress without depending on the parser implementation.

### Numeric Storage and Scaling

`LogData` keeps one compact NumPy structured array for each log message type. The stored representation is selected to limit the permanent memory cost of long flight
logs; conversion to analysis units happens only when required.

ArduPilot DataFlash fixed-point format characters `c`, `C`, `e`, `E`, and `L` are stored as their original integer values. Although pymavlink exposes scaled values
through normal attribute access and `to_dict()`, extraction reads the corresponding `DFMessage._elements` entry for these fields. `_elements` is a pymavlink private API,
but it is maintained by the ArduPilot project and is isolated to the extraction adapter with fixture-based regression coverage.

`LogData.get_field(..., scaled=True)` applies the fixed-point multiplier with a vectorized `float64` NumPy operation. The temporary scaled array is not cached, so
analyses that do not request a field do not pay its memory cost.

FMTU multipliers use a width-aware policy:

* `f` and `d` fields apply their dynamic FMTU multiplier while being ingested, retaining their original floating-point dtype and avoiding repeated scaling for common
  telemetry fields.
* Integer fields whose multiplier would require a wider or fractional representation retain their compact stored value and scale lazily.
* Multipliers equal to one leave values unchanged.

Each `MessageSchema` records `stored_units`, `scaled_units`, `multipliers`, and `multipliers_applied_at_ingest`. These fields make the storage-to-analysis conversion
explicit and prevent a multiplier from being applied twice.

Analysis code always uses `LogData`'s default scaled representation. The `scaled=False` option is retained for low-level diagnostics and regression tests, not for
production analysis. A result timestamp is converted to microseconds only when populating `LogAnalysis.timestamp_us`; parameter values with different documented units
are converted explicitly before comparison.

## Log Analysis Backend

[`backend_log_analysis.py`](https://github.com/ArduPilot/MethodicConfigurator/blob/master/ardupilot_methodic_configurator/log_analysis/backend_log_analysis.py) acts as
the orchestration layer between log extraction, Methodic
Configurator context, and the analysis data models.

Its responsibilities are:

* Load an ArduPilot `.bin` log.
* Report extraction progress when requested.
* Validate the vehicle type.
* Validate the firmware version.
* Extract parameter values from `PARM` messages.
* Construct `LogAnalysisContext`.
* Pass the extracted data and context to the analysis layer.
* Return `LogSummary`.

The main analysis entry points are `analyze_log_file()` and `analyze_log_data()`.

`analyze_log_file()` handles the complete operation starting from a `.bin` file.

`analyze_log_data()` operates on an already extracted `LogData` object.

## Vehicle Validation

Before analysis, the selected log can be validated against the currently configured Methodic Configurator vehicle.

The validation checks:

* Vehicle type
* Firmware version

A log that clearly belongs to another vehicle or firmware version is rejected before analysis.

This prevents analysis results from being interpreted using the configuration of a different vehicle.

## Log Analysis Context

[`data_model_log_analysis_context.py`](https://github.com/ArduPilot/MethodicConfigurator/blob/master/ardupilot_methodic_configurator/log_analysis/data_model_log_analysis_context.py)
 provides the common information required by
the availability and analysis models.

The context contains:

* Parameter values extracted from the log
* Methodic Configurator configuration steps
* Vehicle component information
* ArduPilot parameter documentation
* A parameter-derivation service

The backend constructs this context after extracting the log.

The analysis models receive the context instead of independently loading these resources. This keeps data loading outside the analysis models and avoids duplicated
filesystem and configuration logic.

Detailed analysis models use the parameter-derivation service to evaluate forced
and derived configuration parameters. The default adapter reuses the shared
configuration-step expression evaluator with only the already-loaded context
data; tests can supply a small replacement service without a vehicle directory.

## Analysis Pipeline

[`data_model_log_analysis.py`](https://github.com/ArduPilot/MethodicConfigurator/blob/master/ardupilot_methodic_configurator/log_analysis/data_model_log_analysis.py)
contains the main domain-level analysis pipeline.

The `analyze_log()` function performs the following operations:

1. Resolve the availability and analysis model registry.
2. Obtain parameters and documentation from `LogAnalysisContext`.
3. Check Performance Monitor data.
4. Execute the registered availability models.
5. Store each availability result.
6. Execute an analysis model only when the required data is available.
7. Validate configuration-step data.
8. Extract the hardware report.
9. Construct and return `LogSummary`.

The resulting `LogSummary` provides a common result object for the frontend and other consumers.

## Data Availability and Analysis

Data availability and analysis are separate stages.

### Data Availability

An availability model determines whether the required data is available and suitable for a particular analysis.

Availability checks can verify:

* Required log messages
* Required telemetry
* Required parameters
* Data sufficiency

The availability stage produces a `LogAvailabilityResult` containing:

* `available`
* `state`
* `reason`
* `issues`
* `name`
* `related_step`

### Analysis

An analysis model determines what can be established from the available data.

An analysis model is executed only when its corresponding availability result reports that the required data is available.

The analysis stage produces a `LogAnalysisResult` containing the analysis name, availability, reason, outcomes, and related configuration step.

Analysis outcomes can contain:

* Message
* Timestamp
* Value
* Related configuration step
* Parameter name
* Suggested value

This separation distinguishes between missing or invalid data, a valid analysis that identifies an issue, and an analysis that cannot currently be performed.

## Availability and Analysis Model Registry

The availability and analysis model registry is defined in [`data_model_log_analysis.py`](https://github.com/ArduPilot/MethodicConfigurator/blob/master/ardupilot_methodic_configurator/log_analysis/data_model_log_analysis.py).

| Availability Model      | Analysis Model          |
| ----------------------- | ----------------------- |
| Battery                 | Battery                 |
| GPS                     | None                    |
| ESC                     | ESC                     |
| IMU                     | IMU                     |
| VIBE                    | VIBE                    |
| FFT                     | None                    |
| Automatic dynamic notch | Automatic dynamic notch |
| ERR                     | None                    |
| PM                      | None                    |
| ARM                     | None                    |
| MODE                    | None                    |

An entry with `None` as the analysis model means that the availability check exists but a corresponding analysis model is not currently registered.

This allows additional analysis models to be added without modifying the log extraction pipeline.

Automatic dynamic-notch fitting has its own availability and analysis registration, described below.

## Current Analysis Modules

1. **Battery** - Validates the required battery data and performs battery analysis when sufficient data is available.

2. **ESC** - Validates ESC telemetry and performs ESC analysis when sufficient telemetry is available.

3. **IMU** - Validates IMU data and currently includes IMU temperature calibration analysis.

4. **VIBE** - Provides both a VIBE availability model and analysis model.

5. **FFT** - Provides an availability model. An analysis model is not currently registered.

6. **GPS, ERR, PM, ARM, MODE** - Provide availability checks without currently registered analysis models.

7. **Automatic dynamic notch** - Fits the first harmonic notch from pre-filter gyro batches using ESC RPM or throttle tracking.

## Automatic Dynamic Notch Analysis

[`data_model_auto_dynamic_notch.py`](ardupilot_methodic_configurator/log_analysis/data_model_auto_dynamic_notch.py) implements the functionality in
the locally supplied `ardupilot_methodic_configurator/auto-fit.js`, from [ArduPilot WebTools PR #363](https://github.com/ArduPilot/WebTools/pull/363).

The model fits the first harmonic notch (`INS_HNTCH_*`) from logged pre-filter gyro samples. It selects a tracking source, verifies that vibration peaks follow that
source, and suggests frequency, bandwidth, attenuation, harmonics, and tracking parameters. The upstream algorithm prefers ESC telemetry, then per-motor throttle,
then average throttle. A source is accepted only when its frequency-normalized spectrum contains sufficiently prominent peaks.

### Module Responsibilities and Integration

The module contains:

* `AutoDynamicNotchLogAvailabilityModel`, derived from `BaseLogAvailabilityModel`, for checking whether a fit can be attempted.
* `AutoDynamicNotchLogAnalysis`, derived from `BaseLogAnalysisModel`, with the existing `analyse() -> LogAnalysisResult` entry point.
* Typed, in-memory structures for fitting settings, gyro FFT windows, tracking-source samples, order spectra, and the selected fit.
* Numerical helpers for batch reconstruction, FFT preparation, telemetry interpolation, spectrum normalization, peak selection, and parameter suggestions.

The two models are registered together in `LOG_ANALYSIS_SUBSYSTEMS` under the `auto_dynamic_notch` key. The existing `fft` availability entry remains for general batch
logging diagnostics. The new availability model reuses the FFT checks and adds the stricter requirements needed for fitting; the presence of ISBH and ISBD alone
does not establish that pre-filter gyro samples are usable.

Both models consume `LogData` and `LogAnalysisContext`. Batch reconstruction and FFT computation operate on already extracted arrays using NumPy. Parsing `.bin`
files stays in the extraction backend, which already supports DataFlash array fields. Browser globals, DOM access, alerts, and WebTools plotting are replaced by
explicit inputs and structured results. The data model performs no filesystem access, flight-controller communication, or frontend operations.

### Required Data and Availability

Availability requires all of the following:

* Complete pre-filter gyro batches within the analysis interval, identified from ISBH metadata and the logged batch-logging configuration.
* ISBH batch identifiers, sensor type and instance, sample timestamp, sample count, sample rate, and sample multiplier, with matching ISBD batch identifiers,
  sequence numbers, and `x`, `y`, and `z` sample arrays.
* At least one tracking source with usable, positive samples overlapping the gyro FFT windows: ESC RPM, per-motor throttle, or average throttle.
* Logged parameters and parameter documentation sufficient to interpret the selected tracking source and validate the first harmonic-notch parameter group.

Reconstruct batches by header and packet sequence, trim packet padding to the declared sample count, and reject missing packets, duplicate or inconsistent sequences,
invalid multipliers, non-finite samples, and non-positive sample rates. Exclude accelerometer and post-filter batches. Retain each sensor instance's sample rate and
time base; do not concatenate batches across gaps or sample-rate changes.

Use `LogData.get_field()` in its default scaled representation. Apply the batch sample multiplier separately according to the batch format, without applying a FMTU
multiplier twice. Use seconds internally and convert only result timestamps to microseconds. Split or reject intervals where parameter changes affect batch
interpretation, RPM conversion, motor selection, or throttle reconstruction, using `LogAnalysisContext.parameter_history`.

`AutoDynamicNotchSettings` selects the analysis interval, FFT window size, overlap, and maximum telemetry gap. Defaults are a 1024-sample window, 50% overlap,
a one-second maximum gap, and the full available interval. FFT window size must be a power of two of at least 64 samples. Smaller batches are skipped; callers can
select a smaller window explicitly. The registry uses the default settings; direct model callers can supply settings as the optional third constructor argument.

The analysis interval selects FFT window centers. Relevant parameter changes within the interval are rejected, with guidance to select a stable interval; parameter
history supplies the effective values at its start. When none is selected, the implementation uses the full available interval.
Restrict telemetry interpolation to supported time coverage and reject gaps rather than extrapolating stale values into FFT windows. Missing ESC telemetry must allow
throttle fallback; it must not make the entire analysis unavailable when another source is usable.

Firmware and vehicle support are determined from the validated log identity, schemas, logged parameters, and the context's parameter documentation. Check tracking
modes, option masks, motor-output interpretation, and parameter ranges before returning suggestions. An unsupported source can fall back to a supported source;
an unsupported first-notch parameter group makes the analysis unavailable. Any explicit version gate added during implementation must cite tagged or commit-pinned
ArduPilot source for the relevant vehicle and feature.

### Spectrum Preparation and Peak Selection

The script assumes WebTools has already prepared FFT windows and tracking methods. The Python module supplies these prerequisites using the
[WebTools FFT convention](https://github.com/ArduPilot/WebTools/blob/7b98e0b21d3d3920f029a9f401269d912828ad67/Libraries/fft.js): a symmetric Hann window, FFT normalization
by window length, and doubled positive-frequency amplitudes except at DC and Nyquist. Window centers use half the window length. Each batch retains its own sample
rate, and spectra are accumulated incrementally rather than concatenating a full-flight gyro array.

For every valid pre-filter FFT window and sensor instance:

1. Obtain the tracked frequency or throttle frequency ratio at the window time.
2. Sum linear spectral power over the three gyro axes: `power = x**2 + y**2 + z**2`, where `x`, `y`, and `z` are FFT magnitudes.
3. Resample that power by linear interpolation onto a common grid relative to the tracked value. A grid position `q` samples the original spectrum at `q * tracked`.
4. Accumulate power and coverage counts over windows and instances. Retain grid points covered by at least half of the accepted windows and compute
   `10 * log10(mean_power)` after averaging linear power.

This normalization aligns vibration that follows the tracking source. Peaks that do not follow that source are spread across the averaged spectrum.
Frequency coverage is limited by each FFT window's Nyquist frequency. Accumulate spectra incrementally to avoid keeping a second full-log copy of gyro data or every
interpolated spectrum in memory.

At a candidate harmonic, search within plus or minus 10% of the fundamental. Reject a search maximum at either boundary because it may be a slope rather than a
peak. Estimate the local floor from the surrounding plus or minus half-fundamental interval, excluding plus or minus 12% around the candidate. The script uses the
upper middle sorted floor value. Peak prominence is the peak level minus this local floor; a harmonic qualifies when prominence is at least 6 dB.

For strongest-peak searches, require a local maximum within ten grid points on each side, then rank candidates by prominence. Missing coverage, empty floor samples,
and non-finite power must produce rejected candidates rather than numerical exceptions or parameter suggestions.

### Tracking-Source Selection

Attempt sources in this order and retain the reasons why earlier attempts failed:

1. **ESC RPM, mode 3.** Convert motor RPM to Hz using the same semantics as the upstream tracking method. Interpolate the mean frequency of motors selected by
   `INS_HNTCH_ESC_MASK`; use the firmware-defined meaning of a zero mask. Ignore windows with tracked frequency below 10 Hz. Build an order spectrum from 0.25 to
   8.75 with a step of 0.005, and evaluate harmonics 1 through 8 at integer orders. Reject ESC tracking when the strongest peak differs from its nearest positive
   integer order by more than 10% of that order and exceeds the best harmonic prominence by more than 6 dB; report the possible motor-pole/RPM scaling mismatch.
   With qualifying harmonics, set `FREQ = round(0.8 * fifth_percentile(tracked_hz))`, `REF = 1`, and `FM_RAT = 1`. Enable multiple-source tracking when the upstream
   motor-count rule detects more than one motor.
2. **Per-motor throttle, mode 1.** Reconstruct normalized motor throttle using the logged output configuration and the upstream tracking semantics. Let `r` be the
   mean square root of motor throttle for a window. Set `REF` from the mean of `r**2` over positive windows and track `r / sqrt(REF)`. This matches the script's
   averaging of square roots before squaring; it is not the mean of the motor throttle values. Enable multiple-source tracking.
3. **Average throttle, mode 1.** Use the average-throttle tracking method with the same square-root normalization and reference calculation, with multiple-source
   tracking disabled.

ESC RPM is converted to Hz by dividing by 60. The ESC mask selects actual logged motor instances; absent or zero masks select all instances. Average throttle uses
`RATE.AOut`, falling back to `CTUN.ThO` for ArduCopter when RATE is absent. Per-motor reconstruction uses servo motor functions and frame class, PWM/spin ranges,
thrust expo, battery-voltage compensation, and barometric air-density compensation, following the
[WebTools throttle adapter](https://github.com/ArduPilot/WebTools/blob/7b98e0b21d3d3920f029a9f401269d912828ad67/FilterReview/tracking/Throttle.js).
Helicopter throttle tracking and throttle tracking on fixed-wing-only planes are rejected.

Per-motor throttle tracking requires ArduPilot 4.6 or later. It was introduced by
[the AP_Vehicle per-motor notch change](https://github.com/ArduPilot/ardupilot/commit/fd19c3f40159f05c9aa906167b9b599d55ac24b3), included in
[Copter 4.6.0](https://github.com/ArduPilot/ardupilot/blob/Copter-4.6.0/libraries/AP_Vehicle/AP_Vehicle.cpp).

For both throttle sources, build a spectrum in reference-throttle Hz from 10 Hz to the smallest maximum FFT-bin frequency among participating pre-filter batches,
with a step of 0.25 Hz. Start with the strongest prominent peak. Test divisors 4, 3, then 2, selecting the first subharmonic that is at least 20 Hz and also has
6 dB prominence. This becomes the fundamental. Evaluate harmonics 1 through 8 and reject the source if none qualifies.

For throttle fits, round the fundamental to obtain `FREQ` and round `REF` to two decimal places. Compute `FM_RAT` from the fifth percentile of tracked frequency ratios,
multiplied by 0.8, rounded down to a multiple of 0.05, and clamped to `[0.1, 1]`. Use the unrounded reference and fundamental during fitting, as the script does.

If all three sources fail, return an unavailable `LogAnalysisResult` with the source-specific explanations and no parameter suggestions. Distinguish this failure to
find tracking peaks from availability failures such as missing pre-filter gyro data. Successful fallback also reports the rejected sources so the user can understand
why a lower-priority tracking method was selected.

### Fitting Rules and Suggested Parameters

The initial rules preserve the supplied script's defaults:

| Rule | Default |
| ---- | ------- |
| Minimum harmonic prominence | 6 dB |
| Attenuation range | 10 to 50 dB |
| Highest harmonic | 8 |
| Harmonic peak-search half-width | 0.10 times the fundamental |
| Noise-floor exclusion half-width | 0.12 times the fundamental |
| Minimum accepted ESC tracking frequency | 10 Hz |
| Minimum throttle subharmonic frequency | 20 Hz |
| Lower tracking-frequency percentile | 5% |
| Lower frequency multiplier | 0.8 |
| Bandwidth ratio | 0.5 |
| ESC integer-order tolerance | 0.10 times the nearest order |

Use the script's percentile definition: sort `n` values and select index `floor((n - 1) * fraction)`, without interpolation. Preserve JavaScript's rounding behavior
for positive fit values instead of Python's ties-to-even rounding. These details affect numerical parity with the source.

For a successful fit, produce a complete, validated set of suggestions:

| Parameter | Suggested value |
| --------- | --------------- |
| `INS_HNTCH_ENABLE` | `1` |
| `INS_HNTCH_MODE` | `3` for ESC RPM, `1` for throttle |
| `INS_HNTCH_FREQ` | Frequency computed for the selected source, in Hz |
| `INS_HNTCH_BW` | `round(0.5 * suggested FREQ)`, in Hz |
| `INS_HNTCH_ATT` | Rounded largest qualifying harmonic prominence, clamped to 10 through 50 dB |
| `INS_HNTCH_REF` | `1` for ESC RPM; fitted reference throttle for throttle tracking |
| `INS_HNTCH_FM_RAT` | `1` for ESC RPM; fitted lower tracking ratio for throttle |
| `INS_HNTCH_HMNCS` | Bitmask with `1 << (harmonic - 1)` for each qualifying harmonic |
| `INS_HNTCH_OPTS` | Existing options adjusted for a single notch per harmonic and the selected source |

Preserve unrelated option bits. Following the supplied script, clear masks `1`, `16`, and `64`, then set or clear mask `2` according to multiple-source tracking.
Validate those meanings against the target firmware before suggesting the options value. Preserve `INS_HNTCH_ESC_MASK` and all additional notch groups; this design
fits only the first group. If a fitted value or required option is unsupported, reject that candidate with a reason rather than silently emitting an incomplete fit.

### Results and Frontend Review

Return a `LogAnalysisResult` with one `LogAnalysis` outcome per parameter suggestion, including `param_name`, `suggested_value`, a translated explanation, and the
configuration step resolved through the existing parameter-to-step lookup. Give the outcomes a common `group` so the frontend can present the fit as one coordinated
proposal. Include explanatory outcomes for the selected source, accepted window count and time interval, harmonic prominences, and any fallback reasons.

Use the existing `LogSummary` and structured-report path. Keep FFT arrays and temporary fitting structures inside the analysis model; serialize the proposal and its
diagnostics through the existing result fields. The frontend presents the proposed settings for review. Applying accepted changes uses the existing parameter APIs
and preserves change reasons and manual-override markers. Analysis itself does not change the active configuration or upload parameters.

### Automatic Dynamic Notch Tests

[`test_data_model_auto_dynamic_notch.py`](tests/test_data_model_auto_dynamic_notch.py) verifies behavior with deterministic, in-memory fixtures:

* Varying motor-frequency gyro noise yields the expected ESC harmonic mask, attenuation, lower frequency, and bandwidth; unrelated noise does not qualify.
* Missing ESC telemetry and rejected RPM scaling allow per-motor throttle and average-throttle fallback in the specified order.
* Throttle fits recover the fundamental from a stronger harmonic and preserve the reference and lower-ratio calculations.
* Missing pre-filter samples, incomplete batches, telemetry gaps, stopped motors, insufficient spectral coverage, and non-finite inputs produce useful reasons and no
  invalid suggestions.
* Harmonic thresholds, attenuation clamps, percentile selection, median selection, rounding, option preservation, and ESC masks match the source at boundary values.
* Equivalent prepared FFT and tracking inputs produce equivalent fit results in JavaScript and Python. Separate fixtures verify batch-to-FFT and tracking adapters,
  including sample scaling, timing, multiple IMUs, and parameter changes within a log.
* Registry execution and JSON serialization expose the grouped proposal through `LogSummary`, without mutating input parameters or requiring a GUI.

## Log Summary

`LogSummary` is the main result object produced by the domain analysis.

It contains:

* Flight duration
* Log file size
* Total message count
* Number of message types
* Parameter count
* Performance Monitor status
* Performance Monitor validation
* Data availability results
* Analysis results
* Configuration-step validation results
* Hardware report
* Related parameter values

The frontend and report-generation layers can consume this summary without knowing how the log was parsed or how individual models were executed.

## Configuration Step Validation

Configuration-step validation is performed after the availability and analysis models.

The analysis context contains the Methodic Configurator configuration steps required for this validation.

The validation produces `StepValidationResult` objects that are included in `LogSummary`.

## Hardware Report

The analysis pipeline extracts a hardware report from the available log information.

Hardware extraction uses:

* Parsed log data
* Parameter values
* ArduPilot parameter documentation

The resulting `HardwareReport` is included in `LogSummary`.

## Tuning Report

[`data_model_tuning_report.py`](https://github.com/ArduPilot/MethodicConfigurator/blob/master/ardupilot_methodic_configurator/log_analysis/data_model_tuning_report.py)
provides the data model for parameter changes across
Methodic Configurator configuration steps.

The tuning report parser reads `tuning_report.csv` and produces a `TuningReport` containing `steps` and `values`.

`steps` contains the configuration steps in order.

`values` contains the parameter values corresponding to those steps.

Missing parameter values are forward-filled so that a parameter retains its most recently known value until it changes.

The tuning report is related to the log-analysis presentation layer but is not executed as part of `analyze_log()`.

## Structured Log Analysis Report

The log-analysis results can be converted into a persistent JSON report.

The report contains:

* `schema_version`
* `flight`
* `vehicle_components`
* `data_availability`
* `analysis`

The `vehicle_components` section contains vehicle configuration information maintained by Methodic Configurator.

The `flight` section contains the start timestamp, end timestamp, and duration.

The `data_availability` section contains availability results produced by the availability models.

The `analysis` section contains completed analyses.

The JSON structure is defined by `log_analysis_schema.json`.

## Frontend Integration

The backend analysis pipeline does not require the frontend to know the sequence of parsing operations.

The frontend interacts with the backend through the analysis entry points and receives structured results.

The frontend can consume:

* Extraction progress
* `LogSummary`
* Availability results
* Analysis results
* Hardware report
* Configuration-step results
* Tuning report data
* Structured JSON report

This keeps presentation logic separate from the analysis implementation.

## Extending the Log Analysis System

New subsystems should follow the existing availability and analysis model architecture.

A new subsystem should provide an availability model derived from the existing base model.

If analysis is required, it should also provide an analysis model using the shared `LogData` and `LogAnalysisContext`.

The new availability and analysis models are then added to the existing registry.

The extraction backend does not need to be modified when the required log data is already available through `LogData`.

The backend orchestration does not need to know the implementation details of the new subsystem.

The frontend can consume the resulting `LogAvailabilityResult` and `LogAnalysisResult` through the existing result structures.

## Testing

The log-analysis architecture is tested at several levels.

### Data Extraction

Verify that ArduPilot `.bin` logs are correctly converted into `LogData`.

### Availability Models

Verify that each availability model correctly identifies:

* Available data
* Missing data
* Invalid data
* Configuration-related issues

### Analysis Models

Verify that analysis models produce the expected `LogAnalysisResult` for representative logs.

### Pipeline

Verify that:

* Logs are validated against the active vehicle.
* The analysis context is constructed correctly.
* Availability models execute.
* Analysis models execute only when their availability requirements are satisfied.
* Configuration-step validation is performed.
* Hardware information is extracted.
* `LogSummary` contains all expected results.

### Report

Validate generated JSON reports against `log_analysis_schema.json`.

## Current Architecture

The current implementation provides:

* ArduPilot `.bin` log extraction
* Vehicle and firmware validation
* Shared log data representation
* Shared analysis context
* Modular data availability models
* Battery analysis
* ESC analysis
* IMU analysis
* VIBE analysis
* FFT data availability checking
* Automatic dynamic-notch parameter proposals from pre-filter gyro batches
* Additional availability checks for ERR, PM, ARM, and MODE
* Configuration-step validation
* Hardware report extraction
* Tuning report parsing
* Structured log-analysis JSON output

The architecture allows additional availability checks and analysis modules to be introduced without changing the fundamental log extraction and orchestration pipeline.
