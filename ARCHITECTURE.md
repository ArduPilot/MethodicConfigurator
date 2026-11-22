# Development guide

The goal *ArduPilot methodic Configurator* software is guide the users (think checklist) and, if possible automate,
the tasks involved in configuring and tuning ArduPilot-based vehicles.

## The Software architecture

We decided to use python as programming language, and the following libraries and frameworks:

- [pymavlink](https://github.com/ArduPilot/pymavlink) for the flight controller communication
- [tkinter](https://docs.python.org/3/library/tkinter.html) for the graphical user interface
- GNU gettext `po` files to translate the software to other languages

The main application parses command-line arguments and orchestrates the main workflow.
In the typical workflow it checks for updates, connects to the flight controller, opens or creates
a vehicle project, optionally opens the component editor for a new project, and then opens the parameter editor.
Firmware upload is available on demand from the project opener;
it is not another step in the startup sequence.

- [`__main__.py`](ardupilot_methodic_configurator/__main__.py)

To satisfy the [system design requirements](https://ardupilot.github.io/MethodicConfigurator/SYSTEM_REQUIREMENTS) the following user interface sub-applications were developed:

### Sub-Application Architecture Documentation

The linked architecture documents describe the implementation and workflow of each sub-application;
their level of detail and sections vary.

1. **[Software Update Check](ARCHITECTURE_1_software_update.md)** - Checks for and downloads software updates
   - [`frontend_tkinter_software_update.py`](ardupilot_methodic_configurator/frontend_tkinter_software_update.py)
   - [`data_model_software_updates.py`](ardupilot_methodic_configurator/data_model_software_updates.py)
   - Standalone test/development entry point (runs the update check directly): [`data_model_software_updates.py`](ardupilot_methodic_configurator/data_model_software_updates.py)

2. **[Flight Controller Communication](ARCHITECTURE_2_flight_controller_communication.md)** - Establishes FC connection, downloads parameters and metadata
   - [`frontend_tkinter_connection_selection.py`](ardupilot_methodic_configurator/frontend_tkinter_connection_selection.py)
     - [`frontend_tkinter_flightcontroller_info.py`](ardupilot_methodic_configurator/frontend_tkinter_flightcontroller_info.py)
     - [`backend_flightcontroller.py`](ardupilot_methodic_configurator/backend_flightcontroller.py) - Main facade class using delegation pattern
       - [`backend_flightcontroller_connection.py`](ardupilot_methodic_configurator/backend_flightcontroller_connection.py) - Connection management
       - [`backend_flightcontroller_params.py`](ardupilot_methodic_configurator/backend_flightcontroller_params.py) - Parameter operations
       - [`backend_flightcontroller_commands.py`](ardupilot_methodic_configurator/backend_flightcontroller_commands.py) - Command execution
       - [`backend_flightcontroller_files.py`](ardupilot_methodic_configurator/backend_flightcontroller_files.py) - File operations
       - [`data_model_flightcontroller_info.py`](ardupilot_methodic_configurator/data_model_flightcontroller_info.py) - FC information
       - [`backend_flightcontroller_protocols.py`](ardupilot_methodic_configurator/backend_flightcontroller_protocols.py) - Protocol definitions
     - [`backend_mavftp.py`](ardupilot_methodic_configurator/backend_mavftp.py)
   - Standalone entry point: [`frontend_tkinter_connection_selection.py`](ardupilot_methodic_configurator/frontend_tkinter_connection_selection.py)

3. **[Directory and Project Selection](ARCHITECTURE_3_directory_selection.md)** - Creates new projects or opens existing ones
   - [`frontend_tkinter_directory_selection.py`](ardupilot_methodic_configurator/frontend_tkinter_directory_selection.py)
     - [`frontend_tkinter_template_overview.py`](ardupilot_methodic_configurator/frontend_tkinter_template_overview.py)
   - Standalone entry points (`frontend_tkinter_directory_selection.py` only contains reusable widgets):
     - [`frontend_tkinter_project_opener.py`](ardupilot_methodic_configurator/frontend_tkinter_project_opener.py)
     - [`frontend_tkinter_project_creator.py`](ardupilot_methodic_configurator/frontend_tkinter_project_creator.py)
     - [`frontend_tkinter_template_overview.py`](ardupilot_methodic_configurator/frontend_tkinter_template_overview.py)

4. **[Vehicle Component Editor](ARCHITECTURE_4_component_editor.md)** - Defines vehicle components and their FC connections
   - [`frontend_tkinter_component_editor.py`](ardupilot_methodic_configurator/frontend_tkinter_component_editor.py)
     - [`frontend_tkinter_component_editor_base.py`](ardupilot_methodic_configurator/frontend_tkinter_component_editor_base.py)
     - [`frontend_tkinter_component_template_manager.py`](ardupilot_methodic_configurator/frontend_tkinter_component_template_manager.py)
   - Standalone entry point: [`frontend_tkinter_component_editor.py`](ardupilot_methodic_configurator/frontend_tkinter_component_editor.py)

5. **[Parameter Editor and Uploader](ARCHITECTURE_5_parameter_editor.md)** - Views documentation, edits parameters, uploads to FC
   - sequentially for each configuration step:
     - view documentation relevant for the current configuration step,
     - edit parameters relevant for the current configuration step,
     - upload them to the flight controller,
     - save them to file
   - [`frontend_tkinter_parameter_editor.py`](ardupilot_methodic_configurator/frontend_tkinter_parameter_editor.py)
     - [`frontend_tkinter_parameter_editor_documentation_frame.py`](ardupilot_methodic_configurator/frontend_tkinter_parameter_editor_documentation_frame.py)
     - [`frontend_tkinter_parameter_editor_table.py`](ardupilot_methodic_configurator/frontend_tkinter_parameter_editor_table.py)
     - [`frontend_tkinter_stage_progress.py`](ardupilot_methodic_configurator/frontend_tkinter_stage_progress.py)
   - Standalone entry point: [`frontend_tkinter_parameter_editor.py`](ardupilot_methodic_configurator/frontend_tkinter_parameter_editor.py)

6. **[Firmware Upload](ARCHITECTURE_firmware_upload.md)** - Flashes an ArduPilot APJ firmware image through the bootloader
   and reconnects to the flight controller. It is opened on demand from the project opener (sub-application 3)
   - [`frontend_tkinter_firmware_upload.py`](ardupilot_methodic_configurator/frontend_tkinter_firmware_upload.py)
     - [`backend_firmware_upload.py`](ardupilot_methodic_configurator/backend_firmware_upload.py)
     - [`backend_flightcontroller_bootloader.py`](ardupilot_methodic_configurator/backend_flightcontroller_bootloader.py)
     - [`data_model_firmware_upload.py`](ardupilot_methodic_configurator/data_model_firmware_upload.py)
   - Standalone entry point: [`frontend_tkinter_firmware_upload.py`](ardupilot_methodic_configurator/frontend_tkinter_firmware_upload.py)

Where a standalone entry point is provided, it can be used to test or develop that part in isolation.
Some entry points are test/development runners rather than complete standalone versions of the integrated workflow.
Run an entry point from the repository root with its Python environment activated, for example
`python -m ardupilot_methodic_configurator.frontend_tkinter_firmware_upload`.

### Parameter editor sub-applications

The parameter editor also opens the following tools alongside the configuration-step workflow.
`ParameterEditorWindow` coordinates their windows and passes the current project or flight-controller
state through the `ParameterEditor` model. FC operations share the existing `FlightController` facade;
the navigation lock and plugin suspension coordinate tools that need exclusive access to the connection.

1. **Compare and upload parameters**: An external `.param` or `.parm` file is loaded into
   `ParameterFileUploadWindow`, which reuses the parameter table to compare its values with the FC,
   select changes and optionally upload them. The external file is separate from the managed
   configuration-step files. See [parameter upload architecture](ARCHITECTURE_parameter_upload.md).
   Standalone entry point: [`frontend_tkinter_parameter_compare_and_upload.py`](ardupilot_methodic_configurator/frontend_tkinter_parameter_compare_and_upload.py)

2. **Export parameters**: `ParameterExportWindow` filters a snapshot of current FC values and writes
   the selection to a user-chosen `.param` file, optionally with documentation. The model handles
   classification and serialization. See [export architecture](ARCHITECTURE_fc_param_export.md) and
   [user manual](USERMANUAL_fc_parameter_export.md).
   Standalone entry point: [`frontend_tkinter_parameter_export.py`](ardupilot_methodic_configurator/frontend_tkinter_parameter_export.py)

3. **FC information**: `FlightControllerBannerWindow` displays captured startup text,
   recent `STATUSTEXT` messages and devices decoded from FC parameter values. The editor pauses the
   active plugin receiver while the diagnostics window is open. See the [FC banner user manual](USERMANUAL_fc_banner.md).
   Standalone entry point: none, it is only opened from the parameter editor.

4. **MAVLink inspector**: The embedded inspector observes the existing connection and presents
   messages, rates and decoded fields. Its telemetry backend and data models collect and calculate
   observations independently of the Tk window. It does not open a second connection. See the
   [inspector architecture](ARCHITECTURE_mavlink_inspector.md),
   [telemetry architecture](ARCHITECTURE_data_telemetry.md) and
   [user manual](USERMANUAL_MAVLink_inspector.md).
   Standalone entry point: [`frontend_tkinter_mavlink_inspector.py`](ardupilot_methodic_configurator/frontend_tkinter_mavlink_inspector.py)

5. **Internal .bin log analyser**: The editor selects a local log and supplies project context to
   the log-analysis pipeline. The extraction backend parses the log; availability and analysis models
   produce structured results for the report windows, including configuration-step and hardware
   information. A local log can also be selected from the file browser. See
   [log analysis architecture](ARCHITECTURE_log_analysis.md).
   Standalone entry point: [`frontend_tkinter_log_analysis.py`](ardupilot_methodic_configurator/frontend_tkinter_log_analysis.py)

6. **Skybrush .bin log analyser**: `SkybrushLogAnalysisWindow` uses the Skybrush client to
   authenticate and upload a selected log to the remote service, then presents its results. This
   requires an internet connection and a Skybrush account; analysis runs on Skybrush servers. See the
   [Skybrush user manual](USERMANUAL_skybrush_log_analyzer.md).
   Standalone entry point: none, it is only opened from the parameter editor.

7. **Tuning parameter graph**: `TuningReportWindow` reads the vehicle directory's `tuning_report.csv`
   through `data_model_tuning_report.py` and plots selected parameter values across configuration
   steps. Missing values are carried forward by the model. The graph is opened from the parameter
   editor header when the CSV exists. See the
   [tuning report architecture](ARCHITECTURE_log_analysis.md#tuning-report).
   Standalone entry point: none, it is only opened from the parameter editor.

8. **File browser (MAVFTP)**: `FileBrowserWindow` presents local and FC files and runs remote
   operations in background tasks. The model delegates through `FlightController` and
   `FlightControllerFiles` to MAVFTP; `FlightControllerFiles` serializes remote operations. See the
   [file browser architecture](ARCHITECTURE_file_browser.md) and [user manual](USERMANUAL_MAVFTP.md).
   Standalone entry point: [`frontend_tkinter_file_browser.py`](ardupilot_methodic_configurator/frontend_tkinter_file_browser.py)

### Plugins

Plugins encapsulate configuration-step functionality that the parameter editor can embed when a step calls for it.
We chose this architecture to keep the main application less ArduPilot-specific and to compartmentalize configuration
steps so their functionality can be reused across ArduPilot vehicle types.
Some plugin frontends can also be run standalone for testing and development;
the entry point list below distinguishes those from plugins that are only hosted by the parameter editor.

The plugins live in [`ardupilot_methodic_configurator/plugins`](ardupilot_methodic_configurator/plugins/).
The application registers them at startup through [`register_plugins`](ardupilot_methodic_configurator/__main__.py)
and the [plugin factory](ardupilot_methodic_configurator/plugins/plugin_factory.py); vehicle configuration steps select
the plugins to display.
The [parameter editor architecture](ARCHITECTURE_5_parameter_editor.md#plugin-lifecycle-during-step-changes)
describes their lifecycle during step changes.

The available plugins, their architecture documentation and standalone entry points are listed below.
Run an entry point from the repository root with its Python environment activated, for example
`python -m ardupilot_methodic_configurator.plugins.frontend_tkinter_motor_test`.
Plugins marked "none" currently have no standalone entry point and are exercised through the parameter editor and their unit tests.

- [Accelerometer calibration](ARCHITECTURE_accelerometer_calibration.md) -
  [`frontend_tkinter_accelerometer_calibration.py`](ardupilot_methodic_configurator/plugins/frontend_tkinter_accelerometer_calibration.py)
- [AHRS orientation](ARCHITECTURE_ahrs_orientation.md) - none
- [AutoTune acceleration back-off](ARCHITECTURE_autotune_accel_backoff.md) - none
- [AutoTune gain back-off](ARCHITECTURE_autotune_gain_backoff.md) - none
- [Battery monitor](ARCHITECTURE_battery_monitor.md) -
  [`frontend_tkinter_battery_monitor.py`](ardupilot_methodic_configurator/plugins/frontend_tkinter_battery_monitor.py)
- [Compass calibration](ARCHITECTURE_compass_calibration.md) -
  [`frontend_tkinter_compass_calibration.py`](ardupilot_methodic_configurator/plugins/frontend_tkinter_compass_calibration.py)
- [Data telemetry](ARCHITECTURE_data_telemetry.md) - none
- [ESC telemetry and ESC RPM scaling](ARCHITECTURE_esc_telemetry.md) - none
- [GNSS](ARCHITECTURE_gnss.md) - none
- [Level calibration](ARCHITECTURE_level_calibration.md) - none
- [Motor test](ARCHITECTURE_motor_test.md) - motor testing with a visual diagram -
  [`frontend_tkinter_motor_test.py`](ardupilot_methodic_configurator/plugins/frontend_tkinter_motor_test.py)
- [RC calibration](ARCHITECTURE_rc_calibration.md) -
  [`frontend_tkinter_rc_calibration.py`](ardupilot_methodic_configurator/plugins/frontend_tkinter_rc_calibration.py)
- [RC receiver](ARCHITECTURE_rc_receiver.md) - none
- [Servo output functions](ARCHITECTURE_servo_out.md) - none

#### Data Models and Architecture

Each application follows a simple three-level separation:

1. `backend_*.py` modules are datasource adapters. They communicate with external systems such as the local filesystem,
   the flight controller, the internet, or a log-file parser. They may perform I/O, translate external formats into Python
   data structures, and expose test seams for those external dependencies.
2. `data_model_*.py` modules contain the application/domain model. This is where AMC keeps business logic and computation
   over already loaded data: validation rules, derived values, analysis results, workflow decisions, and plain data
   containers. Data models should not open Tkinter dialogs, read files, download data, or talk directly to the flight
   controller.
3. `frontend_tkinter_*.py` modules contain the user interface. They collect user input, call backend adapters when data
   must be loaded or saved, pass the loaded values into data models, and render the resulting data. Frontend modules should
   avoid duplicating domain rules.

This convention keeps the architecture small while preserving testability. Backend adapters can be mocked or replaced;
data-model logic can be tested with in-memory inputs; and the frontend stays focused on presentation and interaction.

For example, log analysis uses backend modules to parse `.bin` logs and uses `LocalFilesystem.doc_dict` for already loaded
parameter metadata.
Those loaded values are passed into `data_model_log_analysis.py`, `data_model_log_analysis_result.py`,
`data_model_log_availability.py`, `data_model_log_availability_check.py`, and the `data_model_vehicle_overview_*.py`
models.
The data model may combine `LogData`, parameters, configuration steps, `apm.pdef` metadata, and vehicle components
to produce a report, but it should not fetch those inputs itself.

1. Check for software updates:
   1. [`data_model_software_updates.py`](ardupilot_methodic_configurator/data_model_software_updates.py)
1. FC connection:
   1. [`data_model_fc_ids.py`](ardupilot_methodic_configurator/data_model_fc_ids.py) <- autogenerated by `update_flight_controller_ids.py`
1. Create or open project:
   1. [`data_model_vehicle_project.py`](ardupilot_methodic_configurator/data_model_vehicle_project.py)
   1. [`data_model_vehicle_project_creator.py`](ardupilot_methodic_configurator/data_model_vehicle_project_creator.py)
   1. [`data_model_vehicle_project_opener.py`](ardupilot_methodic_configurator/data_model_vehicle_project_opener.py)
   1. [`data_model_template_overview.py`](ardupilot_methodic_configurator/data_model_template_overview.py)
1. Component editor:
   1. [`battery_cell_voltages.py`](ardupilot_methodic_configurator/battery_cell_voltages.py)
   1. [`data_model_vehicle_components_base.py`](ardupilot_methodic_configurator/data_model_vehicle_components_base.py)
   1. [`data_model_vehicle_components_display.py`](ardupilot_methodic_configurator/data_model_vehicle_components_display.py)
   1. [`data_model_vehicle_components_import.py`](ardupilot_methodic_configurator/data_model_vehicle_components_import.py)
   1. [`data_model_vehicle_components_json_schema.py`](ardupilot_methodic_configurator/data_model_vehicle_components_json_schema.py)
   1. [`data_model_vehicle_components_templates.py`](ardupilot_methodic_configurator/data_model_vehicle_components_templates.py)
   1. [`data_model_vehicle_components_validation.py`](ardupilot_methodic_configurator/data_model_vehicle_components_validation.py)
   1. [`data_model_vehicle_components.py`](ardupilot_methodic_configurator/data_model_vehicle_components.py)
1. Parameter editor:
   1. [`data_model_configuration_step.py`](ardupilot_methodic_configurator/data_model_configuration_step.py)
   1. [`data_model_par_dict.py`](ardupilot_methodic_configurator/data_model_par_dict.py)
   1. [`data_model_ardupilot_parameter.py`](ardupilot_methodic_configurator/data_model_ardupilot_parameter.py)
   1. [`data_model_log_analysis.py`](ardupilot_methodic_configurator/log_analysis/data_model_log_analysis.py)
   1. [`data_model_log_analysis_result.py`](ardupilot_methodic_configurator/log_analysis/data_model_log_analysis_result.py)
   1. [`data_model_log_availability.py`](ardupilot_methodic_configurator/log_analysis/data_model_log_availability.py)
   1. [`data_model_log_availability_check.py`](ardupilot_methodic_configurator/log_analysis/data_model_log_availability_check.py)
   1. [`data_model_availability_base.py`](ardupilot_methodic_configurator/log_analysis/data_model_availability_base.py)
   1. [`data_model_vehicle_overview*.py`](ardupilot_methodic_configurator/log_analysis/data_model_vehicle_overview.py)

The detailed data models, components, and dependencies for each sub-application are documented in their respective architecture files linked above.

#### Common Libraries and Shared Components

All applications use one or more of the following shared libraries:

1. internationalization
   1. [`__init__.py`](ardupilot_methodic_configurator/__init__.py)
   1. [`internationalization.py`](ardupilot_methodic_configurator/internationalization.py)
   1. [`configuration_steps_strings.py`](ardupilot_methodic_configurator/configuration_steps_strings.py) <- autogenerated by `scripts/update_configuration_steps_translation.py`
   1. [`vehicle_components.py`](ardupilot_methodic_configurator/vehicle_components.py) <- autogenerated by `update_vehicle_components_translation.py`
1. command line parsing
   1. [`common_arguments.py`](ardupilot_methodic_configurator/common_arguments.py)
   1. [`argparse_check_range.py`](ardupilot_methodic_configurator/argparse_check_range.py)
1. the local filesystem backend does file I/O on the local file system. Operates mostly on parameter files and metadata/documentation files
   1. [`backend_filesystem.py`](ardupilot_methodic_configurator/backend_filesystem.py)
   2. [`backend_filesystem_vehicle_components.py`](ardupilot_methodic_configurator/backend_filesystem_vehicle_components.py)
   3. [`backend_filesystem_configuration_steps.py`](ardupilot_methodic_configurator/backend_filesystem_configuration_steps.py)
   4. [`backend_filesystem_program_settings.py`](ardupilot_methodic_configurator/backend_filesystem_program_settings.py)
1. the internet backend communicates with the internet
   1. [`backend_internet.py`](ardupilot_methodic_configurator/backend_internet.py)
1. the flight controller backend communicates with the flight controller using a **delegation pattern** with specialized managers:
   1. [`backend_flightcontroller.py`](ardupilot_methodic_configurator/backend_flightcontroller.py) -
     Main facade class that delegates to specialized managers
   2. [`backend_flightcontroller_connection.py`](ardupilot_methodic_configurator/backend_flightcontroller_connection.py) -
     Handles connection establishment, port discovery, and heartbeat detection
   3. [`backend_flightcontroller_params.py`](ardupilot_methodic_configurator/backend_flightcontroller_params.py) -
     Manages parameter download, upload, and querying
   4. [`backend_flightcontroller_commands.py`](ardupilot_methodic_configurator/backend_flightcontroller_commands.py) -
     Executes MAVLink commands (motor tests, battery status, etc.)
   5. [`backend_flightcontroller_files.py`](ardupilot_methodic_configurator/backend_flightcontroller_files.py) -
     Handles file upload/download via MAVFTP
   6. [`data_model_flightcontroller_info.py`](ardupilot_methodic_configurator/data_model_flightcontroller_info.py) -
     Stores flight controller metadata and capabilities
   7. [`backend_flightcontroller_protocols.py`](ardupilot_methodic_configurator/backend_flightcontroller_protocols.py) -
     Protocol definitions for dependency injection and testing
   8. [`backend_mavftp.py`](ardupilot_methodic_configurator/backend_mavftp.py) - MAVFTP protocol implementation

   **Flight Controller Backend Architecture:**
   - The `FlightController` class acts as a facade, delegating operations to specialized managers
   - Each manager handles a specific concern (connection, parameters, commands, files)
   - Managers can reference each other (e.g., params manager holds reference to connection manager)
   - Protocol definitions enable dependency injection for testing
   - Connection manager is the source of truth for connection state (`master`, `comport`, `info`)
   - Other managers query connection manager for current state rather than caching it
   - `backend_flightcontroller_factory_mavftp.py` owns baud detection and link-specific MAVFTP timing settings.
     Both factory entry points inject settings before session initialization. The protocol implementation provides
     transport-neutral defaults and handles progress-aware idle detection and bounded session cleanup.

   **Error Handling Standards:**

   To maintain consistency across the flight controller backend, the following error handling patterns are used:

   1. **Connection and I/O Operations** - Return `str` (empty string on success, error message on failure):
      - `connect()`, `disconnect()`, `register_and_try_connect()`
      - Rationale: Allows user-friendly error messages to be displayed directly

   2. **Command Operations** - Return `tuple[bool, str]` (success flag, error message):
      - `test_motor()`, `test_all_motors()`, `reset_all_parameters_to_default()`
      - Rationale: Separates success/failure from error details for better control flow

   3. **Query Operations** - Return `Optional[T]` or raise exceptions:
      - `fetch_param()` - raises `TimeoutError` on timeout
      - `get_battery_statuses()` - returns `tuple[dict[int, tuple[float, float]] | None, str]`, keyed by battery ID
      - Rationale: Distinguishes between "not found" (None) and "error" (exception)

   4. **Bulk Operations** - Return data structures or tuples:
      - `download_params()` - returns `tuple[dict[str, float], ParDict]`
      - Rationale: Success implied by returned data, errors logged but not returned

   **Testing Hacks and Violations:**

   The following methods exist for testing purposes only and violate architectural principles:

   - `FlightController.set_master_for_testing()` - Directly mutates connection manager's internal state,
     violating the principle that connection manager should be the sole mutator of connection state.
     **Never use in production code.**

   - Test parameter loading via `device=DEVICE_FC_PARAM_FROM_FILE` in `backend_flightcontroller_params.py` - Bypasses normal
     parameter download flow to load from local file.

1. the tkinter frontend, which is the GUI the user interacts with
   1. [`frontend_tkinter_autoresize_combobox.py`](ardupilot_methodic_configurator/frontend_tkinter_autoresize_combobox.py)
   1. [`frontend_tkinter_base_window.py`](ardupilot_methodic_configurator/frontend_tkinter_base_window.py)
   1. [`frontend_tkinter_entry_dynamic.py`](ardupilot_methodic_configurator/frontend_tkinter_entry_dynamic.py)
   1. [`frontend_tkinter_pair_tuple_combobox.py`](ardupilot_methodic_configurator/frontend_tkinter_pair_tuple_combobox.py)
   1. [`frontend_tkinter_progress_window.py`](ardupilot_methodic_configurator/frontend_tkinter_progress_window.py)
   1. [`frontend_tkinter_rich_text.py`](ardupilot_methodic_configurator/frontend_tkinter_rich_text.py)
   1. [`frontend_tkinter_scroll_frame.py`](ardupilot_methodic_configurator/frontend_tkinter_scroll_frame.py)
   1. [`frontend_tkinter_show.py`](ardupilot_methodic_configurator/frontend_tkinter_show.py)
   1. [`frontend_tkinter_usage_popup_window.py`](ardupilot_methodic_configurator/frontend_tkinter_usage_popup_window.py)

When all is combined it looks like this:

![Software Architecture diagram](images/Architecture2.drawio.png)

The parts can be individually tested, and do have unit tests.
They can also be exchanged, for instance, [tkinter-frontend](https://docs.python.org/3/library/tkinter.html) can be replaced with
[wxWidgets](https://www.wxwidgets.org/) or [pyQt](https://riverbankcomputing.com/software/pyqt/intro).

In the future, we might port the entire application into a client-based web application.
That way the users would not need to install the software and will always use the latest version.

#### Generated Files

Several files in the project are automatically generated and should not be manually edited:

##### Core Application Generated Files

1. [`data_model_fc_ids.py`](ardupilot_methodic_configurator/data_model_fc_ids.py) <- autogenerated by `update_flight_controller_ids.py`
   - Contains flight controller hardware identification mappings
   - Generated from ArduPilot firmware metadata

2. [`configuration_steps_strings.py`](ardupilot_methodic_configurator/configuration_steps_strings.py) <- autogenerated by `scripts/update_configuration_steps_translation.py`
   - Contains translatable strings for configuration step descriptions
   - Generated from configuration JSON files for internationalization

3. [`vehicle_components.py`](ardupilot_methodic_configurator/vehicle_components.py) <- autogenerated by `update_vehicle_components_translation.py`
   - Contains translatable strings for vehicle component descriptions
   - Generated from vehicle component JSON schemas for internationalization

#### Development and Analysis Tools

1. [`generate_codebase_pie_chart.py`](scripts/generate_codebase_pie_chart.py) <- generated by AI assistant for codebase analysis
   - Creates pie chart visualizations of codebase structure
   - Automatically maintains codebase metrics and statistics
   - Part of the development workflow for project health assessment

2. [`download_motor_diagrams.py`](scripts/download_motor_diagrams.py) <- autogenerated by `.github/skills/update-motor-diagrams/SKILL.md`
   - Downloads motor diagram SVG files from ArduPilot documentation
   - Updates motor diagrams used in the motor test plugin
   - Periodically updated via GitHub Actions workflow

**Note**: When calculating code metrics or performing codebase analysis, these generated files should be counted separately
from hand-written code to provide accurate development statistics.

### Module design

To assure code quality we decided to use Microsoft VS code with a [lot of extensions](SetupDeveloperPC.bat) to lint the code as you type.
We use git [pre-commit](https://pre-commit.com/) hooks to [check the code](.pre-commit-config.yaml) before it is committed to the repository.

### Module testing

We tested using **automated static tests** in both pre-commit hooks and on github CI:

- ruff
- pylint
- mypy
- pyright
- markdown-lint
- markdown-link-check
- codespell, grammarly
- shellcheck
- ty

We tested using **automated dynamic tests** on github CI including automated test coverage reports.
We use [pytest](https://docs.pytest.org/en/stable/) to run the test suite, including unit and GUI tests.
The tests are easy to run on the command line or in VS code.
When you write new code you must also write tests in the `tests/` directory, there is CI test that only passes if test coverage increases monotonically.

To run the tests either use the python tests plugin in visualstudio code, or execute:

```bash
pytest
```

### Integration testing

The different sub-applications are tested independently before integration.
Each has detailed testing strategies documented in their respective architecture files:

- **[Software Update](ARCHITECTURE_1_software_update.md#testing-analysis)** - `python .\ardupilot_methodic_configurator\data_model_software_updates.py`
- **[Flight Controller Communication](ARCHITECTURE_2_flight_controller_communication.md#testing-analysis)** - `python .\ardupilot_methodic_configurator\frontend_tkinter_connection_selection.py`
- **[Directory Selection](ARCHITECTURE_3_directory_selection.md#testing-strategy)**
  - `python .\ardupilot_methodic_configurator\frontend_tkinter_project_opener.py`
  - `python .\ardupilot_methodic_configurator\frontend_tkinter_project_creator.py`
  - `python .\ardupilot_methodic_configurator\frontend_tkinter_template_overview.py`
- **[Component Editor](ARCHITECTURE_4_component_editor.md#testing-strategy)** - `python .\ardupilot_methodic_configurator\frontend_tkinter_component_editor.py`
- **[Parameter Editor](ARCHITECTURE_5_parameter_editor.md#testing-strategy)** - `python .\ardupilot_methodic_configurator\frontend_tkinter_parameter_editor.py`
- **[Firmware Upload](ARCHITECTURE_firmware_upload.md)** - `python .\ardupilot_methodic_configurator\frontend_tkinter_firmware_upload.py`

Plugins are also tested independently; see the architecture documents linked in the [Plugins](#plugins) section.

Testing sub-applications independently helps isolate issues before they are integrated and tested together.

### System testing

Here the integrated application was tested against the system requirements defined above.
The tests were conducted on Windows and Linux machines using multiple different flight controllers and firmware versions.
The software is automatically build and distributed using the github CD pipeline.

### Acceptance testing

The software was tested by multiple users with different skill levels, languages, flight controller and backgrounds.
The feedback was used to improve the user interface and user experience.
The software is ready for production use since November 2024.

## DevOps

The software is feature complete and stable with a user base of hundreds of users, we switched from the V-Model to DevOps development process on November 2024.
This provides faster response to requirements changes and additions.

![code line statistics](images/codebase_structure_pie_chart.png)

## Do a release

The release process is automated.
To do a release navigate to the [bump_version_and_tag workflow](https://github.com/ArduPilot/MethodicConfigurator/actions/workflows/bump_version_and_tag.yml)
and select `Run Workflow` enter the version and the description and press the green `Run Workflow` button.

![bump_version_and_tag workflow](images/bump_version_and_tag.png)

<!-- Gurubase Widget -->
<script async src="https://widget.gurubase.io/widget.latest.min.js"
    data-widget-id="uE4kxEE4LY3ZSyfNsF5bU6gIOnWGTBOL_e16KwDH-0g"
    data-text="Ask AI"
    data-margins='{"bottom": "1rem", "right": "1rem"}'
    data-light-mode="true"
    id="guru-widget-id">
</script>
