# Log Analysis Architecture

The Log Analysis subsystem provides a structured pipeline for analyzing ArduPilot `.bin` flight logs inside ArduPilot Methodic Configurator.

The subsystem separates log extraction, data quality validation, log analysis, configuration validation, hardware extraction, and result presentation.

## The Log Analysis Architecture

The log analysis subsystem follows the same backend, data-model, and frontend separation used throughout Methodic Configurator.

The main components are:

1. **Log Analysis Backend** - Loads and validates ArduPilot `.bin` logs and prepares the data required by the analysis layer.

   * [`backend_log_analysis.py`](https://github.com/ArduPilot/MethodicConfigurator/blob/master/ardupilot_methodic_configurator/log_analysis/backend_log_analysis.py)
   * [`backend_log_extraction.py`](https://github.com/ArduPilot/MethodicConfigurator/blob/master/ardupilot_methodic_configurator/log_analysis/backend_log_extraction.py)

2. **Log Analysis Data Models** - Contains the analysis pipeline, shared context, quality models, analysis models, and result structures.

   * [`data_model_log_analysis.py`](https://github.com/ArduPilot/MethodicConfigurator/blob/master/ardupilot_methodic_configurator/log_analysis/data_model_log_analysis.py)
   * [`data_model_log_analysis_context.py`](https://github.com/ArduPilot/MethodicConfigurator/blob/master/ardupilot_methodic_configurator/log_analysis/data_model_log_analysis_context.py)
   * [`data_model_parameter_derivation.py`](https://github.com/ArduPilot/MethodicConfigurator/blob/master/ardupilot_methodic_configurator/log_analysis/data_model_parameter_derivation.py)
   * [`data_model_log_quality.py`](https://github.com/ArduPilot/MethodicConfigurator/blob/master/ardupilot_methodic_configurator/log_analysis/data_model_log_quality.py)
   * [`data_model_log_quality_check.py`](https://github.com/ArduPilot/MethodicConfigurator/blob/master/ardupilot_methodic_configurator/log_analysis/data_model_log_quality_check.py)
   * [`data_model_quality_base.py`](https://github.com/ArduPilot/MethodicConfigurator/blob/master/ardupilot_methodic_configurator/log_analysis/data_model_quality_base.py)

3. **Quality and Analysis Models** - Performs subsystem-specific data validation and analysis.

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

   * `LogQualityResult`
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
the quality and analysis models.

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

1. Resolve the quality and analysis model registry.
2. Obtain parameters and documentation from `LogAnalysisContext`.
3. Check Performance Monitor data.
4. Execute the registered quality models.
5. Store each quality result.
6. Execute an analysis model only when the required data is available.
7. Validate configuration-step data.
8. Extract the hardware report.
9. Construct and return `LogSummary`.

The resulting `LogSummary` provides a common result object for the frontend and other consumers.

## Data Quality and Analysis

Data quality and analysis are separate stages.

### Data Quality

A quality model determines whether the required data is available and suitable for a particular analysis.

Quality checks can verify:

* Required log messages
* Required telemetry
* Required parameters
* Data sufficiency

The quality stage produces a `LogQualityResult` containing:

* `available`
* `state`
* `reason`
* `issues`
* `name`
* `related_step`

### Analysis

An analysis model determines what can be established from the available data.

An analysis model is executed only when its corresponding quality result reports that the required data is available.

The analysis stage produces a `LogAnalysisResult` containing the analysis name, availability, reason, outcomes, and related configuration step.

Analysis outcomes can contain:

* Message
* Timestamp
* Value
* Related configuration step
* Parameter name
* Suggested value

This separation distinguishes between missing or invalid data, a valid analysis that identifies an issue, and an analysis that cannot currently be performed.

## Quality and Analysis Model Registry

The quality and analysis model registry is defined in [`data_model_log_analysis.py`](https://github.com/ArduPilot/MethodicConfigurator/blob/master/ardupilot_methodic_configurator/log_analysis/data_model_log_analysis.py).

| Quality Model | Analysis Model |
| ------------- | -------------- |
| Battery       | Battery        |
| GPS           | None           |
| ESC           | ESC            |
| IMU           | IMU            |
| VIBE          | VIBE           |
| FFT           | None           |
| ERR           | None           |
| PM            | None           |
| ARM           | None           |
| MODE          | None           |

An entry with `None` as the analysis model means that the quality check exists but a corresponding analysis model is not currently registered.

This allows additional analysis models to be added without modifying the log extraction pipeline.

## Current Analysis Modules

1. **Battery** - Validates the required battery data and performs battery analysis when sufficient data is available.

2. **ESC** - Validates ESC telemetry and performs ESC analysis when sufficient telemetry is available.

3. **IMU** - Validates IMU data and currently includes IMU temperature calibration analysis.

4. **VIBE** - Provides both a VIBE quality model and analysis model.

5. **FFT** - Provides a quality model. An analysis model is not currently registered.

6. **GPS, ERR, PM, ARM, MODE** - Provide quality checks without currently registered analysis models.

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
* Data quality results
* Analysis results
* Configuration-step validation results
* Hardware report
* Related parameter values

The frontend and report-generation layers can consume this summary without knowing how the log was parsed or how individual models were executed.

## Configuration Step Validation

Configuration-step validation is performed after the quality and analysis models.

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
* `data_quality`
* `analysis`

The `vehicle_components` section contains vehicle configuration information maintained by Methodic Configurator.

The `flight` section contains the start timestamp, end timestamp, and duration.

The `data_quality` section contains quality results produced by the quality models.

The `analysis` section contains completed analyses.

The JSON structure is defined by `log_analysis_schema.json`.

## Frontend Integration

The backend analysis pipeline does not require the frontend to know the sequence of parsing operations.

The frontend interacts with the backend through the analysis entry points and receives structured results.

The frontend can consume:

* Extraction progress
* `LogSummary`
* Quality results
* Analysis results
* Hardware report
* Configuration-step results
* Tuning report data
* Structured JSON report

This keeps presentation logic separate from the analysis implementation.

## Extending the Log Analysis System

New subsystems should follow the existing quality and analysis model architecture.

A new subsystem should provide a quality model derived from the existing base model.

If analysis is required, it should also provide an analysis model using the shared `LogData` and `LogAnalysisContext`.

The new quality and analysis models are then added to the existing registry.

The extraction backend does not need to be modified when the required log data is already available through `LogData`.

The backend orchestration does not need to know the implementation details of the new subsystem.

The frontend can consume the resulting `LogQualityResult` and `LogAnalysisResult` through the existing result structures.

## Testing

The log-analysis architecture is tested at several levels.

### Data Extraction

Verify that ArduPilot `.bin` logs are correctly converted into `LogData`.

### Quality Models

Verify that each quality model correctly identifies:

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
* Quality models execute.
* Analysis models execute only when their quality requirements are satisfied.
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
* Modular data quality models
* Battery analysis
* ESC analysis
* IMU analysis
* VIBE analysis
* FFT data quality checking
* Additional quality checks for ERR, PM, ARM, and MODE
* Configuration-step validation
* Hardware report extraction
* Tuning report parsing
* Structured log-analysis JSON output

The architecture allows additional quality checks and analysis modules to be introduced without changing the fundamental log extraction and orchestration pipeline.
