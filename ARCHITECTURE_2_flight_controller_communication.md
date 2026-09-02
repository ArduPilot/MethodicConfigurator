# Flight Controller Communication Sub-Application Architecture

## Overview

The Flight Controller Communication sub-application connects the application to an ArduPilot
flight controller over MAVLink, retrieves controller information, and downloads or changes
parameters. When the controller advertises MAVFTP support, it can also retrieve parameter defaults
and transfer files.

Communication operations are synchronous. Progress callbacks report work to the UI, but do not
make MAVLink, MAVFTP, or command operations concurrent or non-blocking.

## Requirements Analysis

### Functional Requirements — Implementation Status

1. **Connection Management**
   - ✅ Supports serial, TCP, and UDP connection strings.
   - ✅ Enumerates local serial ports and presents configured network connection strings.
   - ✅ Establishes a connection with `connect()`, validates it by receiving heartbeats, and closes it with `disconnect()`.
   - ✅ Passes retry and `autoreconnect` settings to the pymavlink connection factory.
   - ⚠️ The application does not implement a separate background heartbeat monitor, connection-state machine, or exponential-backoff policy.

2. **Hardware Information Retrieval**
   - ✅ Stores controller metadata in `FlightControllerInfo`.
   - ✅ Retrieves and processes `AUTOPILOT_VERSION` through `_process_autopilot_version()`.
   - ✅ Determines MAVLink capabilities, board details, firmware version, and vehicle type from MAVLink messages and banner text.
   - ⚠️ Capability information describes protocol support; it is not a complete inventory of physical sensors.

3. **Parameter Operations**
   - ✅ Downloads parameters through MAVFTP when supported, with MAVLink `PARAM_REQUEST_LIST` fallback.
   - ✅ Downloads parameter defaults only through the MAVFTP path.
   - ✅ Validates parameter names and numeric value types before sending a parameter write.
   - ✅ Detects a matching MAVLink-2 `PARAM_ERROR` response from newer ArduPilot firmware and reports the controller's rejection reason.
   - ⚠️ Older firmware does not acknowledge `PARAM_SET`; after the short `PARAM_ERROR` response window, `set_param()` can report only that the write was sent.
     Callers that need positive confirmation must use `fetch_param()` or re-download parameters.

4. **Protocol Support**
   - ✅ Uses pymavlink for MAVLink messages, connection creation, retries, and reconnect support.
   - ✅ Implements MAVFTP file and parameter transfers in `MAVFTP`.
   - ✅ Handles command acknowledgements for MAVLink commands through `send_command_and_wait_ack()`.
   - ⚠️ Protocol dialect/version handling and message validation are provided by pymavlink; this sub-application has no explicit protocol-version negotiation layer.

5. **Error Recovery** ⚠️ **PARTIALLY IMPLEMENTED**
   - ✅ Reports connection, timeout, and protocol errors with contextual guidance where available.
   - ✅ Falls back from MAVFTP parameter download to MAVLink parameter download.
   - ⚠️ Parameter transfers do not resume after interruption; an incomplete MAVLink download is rejected.
   - ⚠️ There is no application-level operation-resumption or exponential-backoff mechanism.

### Non-Functional Requirements — Implementation Status

1. **Performance**
   - ✅ Uses MAVFTP when the controller advertises support and provides transfer progress callbacks.
   - ⚠️ Download, command, and connection operations use polling and blocking waits.
     They should be invoked from an appropriate UI workflow to avoid blocking the event loop.
   - ⚠️ No performance limit for parameter count or memory consumption is enforced or benchmarked by this component.

2. **Reliability** ⚠️ **PARTIALLY IMPLEMENTED**
   - ✅ Checks for a connection before most controller operations and returns structured error messages for many failures.
   - ✅ Verifies command results when the MAVLink command protocol provides `COMMAND_ACK`.
   - ✅ Reports explicit rejections from newer firmware through MAVLink-2 `PARAM_ERROR`.
   - ⚠️ Parameter writes still require explicit read-back for positive verification, especially with older firmware that sends no response.
   - ❌ **TODO**: Interrupted operations cannot be resumed from persisted state.

3. **Compatibility**
   - ✅ Supports ArduPilot vehicle types identified from MAVLink heartbeats.
   - ✅ Uses MAVLink capabilities to select the MAVFTP parameter-download path.
   - ⚠️ The connection flow requires `AUTOPILOT_VERSION`; its error message documents support for ArduPilot versions newer than 4.3.8.

4. **Security** ⚠️ **PARTIALLY IMPLEMENTED**
   - ✅ Validates parameter names and value types before sending parameter writes.
   - ⚠️ Message parsing and transport-level validation are delegated to pymavlink; this is not an end-to-end integrity or authorization guarantee.
   - ❌ **TODO**: MAVLink signing/authentication is not implemented by this component.
   - ⚠️ Newer firmware can explicitly reject writes with `PARAM_ERROR`, but positive parameter-write confirmation still requires an explicit read-back.

## Architecture

### Architectural Pattern — Delegation with Specialized Managers

`FlightController` is a facade that delegates work to specialized manager classes. The connection
manager owns the live MAVLink connection and is the sole mutator of the shared
`FlightControllerInfo` instance. Other managers hold references to the connection and parameter
managers through protocols and query them as needed. The commands manager additionally caches the
most recent battery telemetry for a short period.

This arrangement provides clear responsibilities, dependency injection for tests, and a single
owner for connection state. It does include deliberately shared mutable state (`FlightControllerInfo`
and the parameter dictionary); the ownership and mutation rules above are the relevant invariant.

### Components

#### Flight Controller Facade

- **File**: `backend_flightcontroller.py`
- **Class**: `FlightController`
- **Purpose**: Main entry point that creates or accepts the managers and delegates their public operations.
- **Delegates**:
  - Connection operations → `_connection_manager`
  - Parameter operations → `_params_manager`
  - Command execution → `_commands_manager`
  - File operations → `_files_manager`
- **Representative methods**: `connect()`, `download_params()`, `set_param()`, `test_motor()`, and `upload_file()`.

#### Connection Manager

- **File**: `backend_flightcontroller_connection.py`
- **Classes**: `FlightControllerConnection`, `FakeSerialForTests`
- **Purpose**: Discovers connection choices, establishes and closes MAVLink connections, and selects a supported
  autopilot from heartbeats before populating `FlightControllerInfo`.
- **Key methods**:
  - `connect()` — connects to an explicit device or tries auto-detected choices.
  - `disconnect()` — closes the current connection, clears the banner buffer, and resets controller information.
  - `discover_connections(preserved_connections)` — merges locally enumerated serial ports, configured network endpoints, and persisted choices.
  - `_register_and_try_connect()` and `create_connection_with_retry()` — internal connection helpers.
- **Connection validation**: `_detect_vehicles_from_heartbeats()` is used during connection establishment;
  `_retrieve_autopilot_version_and_banner()` then requests controller details.
- **Dependencies**: pymavlink, pyserial port discovery, `FlightControllerInfo`, time, and logging.

#### Parameters Manager

- **File**: `backend_flightcontroller_params.py`
- **Class**: `FlightControllerParams`
- **Purpose**: Downloads, stores, sends, fetches, and clears controller parameters.
- **Key methods**:
  - `download_params()` — tries `_download_params_via_mavftp()` when supported, otherwise uses `_download_params_via_mavlink()`.
  - `set_param()` — validates then sends a parameter write; it does not verify the new value.
  - `fetch_param()` — fetches one parameter and can be used for read-back verification.
  - `get_param()` — reads the local parameter dictionary with a default.
- **State**: Owns `fc_parameters`; it queries the connection manager for `master`, `info`, and `comport_device`.
- **Dependencies**: `FlightControllerConnectionProtocol`, MAVFTP factory functions, `Par`, and `ParDict`.

#### Commands Manager

- **File**: `backend_flightcontroller_commands.py`
- **Class**: `FlightControllerCommands`
- **Purpose**: Sends MAVLink commands, waits for command acknowledgements, and provides controller-status helpers.
- **Key methods**: `send_command_and_wait_ack()`, motor-test operations, `reset_all_parameters_to_default()`, and `get_battery_status()`.
- **State and query pattern**: Queries the parameter manager for parameter values and the connection manager for `master`. It caches the latest battery telemetry briefly.
- **Dependencies**: connection and parameter protocols plus pure business-logic functions.

#### Files Manager

- **File**: `backend_flightcontroller_files.py`
- **Class**: `FlightControllerFiles`
- **Purpose**: Uploads files and downloads the latest flight log through MAVFTP.
- **Key methods**: `upload_file()` and `download_last_flight_log()`.
- **Query pattern**: Queries the connection manager for `master` and `info`; it checks MAVFTP support before downloading a log.

#### Protocol Definitions

- **File**: `backend_flightcontroller_protocols.py`
- **Purpose**: Defines structural contracts used for dependency injection and tests.
- **Key protocols**: `FlightControllerConnectionProtocol`, `FlightControllerParamsProtocol`, `FlightControllerCommandsProtocol`, and `FlightControllerFilesProtocol`.
- `preserved_connections` uses `Sequence[str] | None`, allowing callers to provide a list, tuple, or another sequence without requiring a mutable list.

#### Business Logic Functions

- **File**: `backend_flightcontroller_business_logic.py`
- **Purpose**: Holds side-effect-free calculations and validations shared by controller commands.
- **Representative functions**: `calculate_voltage_thresholds()`, `is_battery_monitoring_enabled()`, `get_frame_info()`, and `validate_battery_voltage()`.

#### MAVFTP Factory and Backend

- **Files**: `backend_flightcontroller_factory_mavftp.py`, `backend_mavftp.py`
- **Purpose**: Create `MAVFTP` instances and implement MAVLink FTP operations.
- `create_mavftp()` raises when no connection is available. `create_mavftp_safe()` returns `None` when creation is unavailable or fails.
- `MAVFTP` implements file listing, uploads, downloads, parameter retrieval, progress reporting, CRC operations, and burst-read support.

#### Flight Controller Information Model

- **File**: `data_model_flightcontroller_info.py`
- **Class**: `FlightControllerInfo`
- **Purpose**: Stores and derives flight-controller metadata from heartbeat, `AUTOPILOT_VERSION`, and banner data,
  including capabilities, board information, firmware details, and vehicle type.

#### Flight Controller ID Model

- **File**: `data_model_fc_ids.py`
- **Purpose**: Provides board-ID mappings used while deriving controller hardware information.

#### Connection Selection UI

- **File**: `frontend_tkinter_connection_selection.py`
- **Classes**: `ConnectionSelectionWidgets`, `ConnectionSelectionWindow`
- **Purpose**: Lets the user choose or add a connection and provides progress/status feedback.
- **Key behavior**: `_refresh_ports()` refreshes choices every three seconds while preserving connection history cached
  from `ProgramSettings`. `reconnect()` persists the user-selected connection string where possible.

#### Flight Controller Information UI

- **File**: `frontend_tkinter_flightcontroller_info.py`
- **Classes**: `FlightControllerInfoPresenter`, `FlightControllerInfoWindow`
- **Purpose**: Presents flight-controller information and parameter-download progress.

### Data Flow

1. **Startup and initialization**
   - `connect_to_fc_and_set_vehicle_type()` creates a `FlightController` facade.
   - The facade constructs or receives the connection, parameter, command, and file managers.
   - `discover_connections()` obtains serial choices and configured network endpoints; the UI can show `ConnectionSelectionWindow` when manual selection is needed.

2. **Connection establishment**
   - `FlightController.connect()` delegates to the connection manager.
   - The manager creates a pymavlink connection with configured retry and autoreconnect settings.
   - It collects heartbeats, selects a supported ArduPilot autopilot, and stores the selected system/component IDs and vehicle type.
   - It requests banner text and `AUTOPILOT_VERSION`, then updates `FlightControllerInfo`.

3. **Parameter operations**
   - `FlightController.download_params()` delegates to the parameters manager.
   - When `info.is_mavftp_supported` is true, the manager first tries MAVFTP, including defaults when requested; otherwise it uses MAVLink parameter messages.
   - If MAVFTP fails, it falls back to MAVLink. An incomplete MAVLink download returns no parameter set.
   - `set_param()` waits briefly for newer firmware's `PARAM_ERROR` rejection response. No response preserves compatibility
     with older firmware, so a caller needing positive confirmation follows it with `fetch_param()` or another download.

4. **Command and file operations**
   - Command operations that use `send_command_and_wait_ack()` send `COMMAND_LONG` messages and wait synchronously
     for matching `COMMAND_ACK` messages. Batched motor-test commands are sent without per-command acknowledgement waits.
   - Battery status is read from telemetry and briefly cached.
   - The files manager creates a MAVFTP instance for uploads and supported log downloads.

5. **UI updates**
   - Synchronous operations invoke progress callbacks, which the UI uses to update `ProgressWindow` and status messages.

### Integration Points

- **Main application**: `connect_to_fc_and_set_vehicle_type()` in `__main__.py`.
- **Parameter editor**: Receives the `FlightController`, its parameter dictionary, and parameter-operation methods.
- **Configuration**: `ProgramSettings` persists connection history.
- **GUI**: `BaseWindow`, `ProgressWindow`, and custom tkinter widgets present controller operations.
- **Logging**: Python logging records diagnostic and user-facing status information.

### Protocol Implementation

#### MAVLink Parameter Protocol

- Uses `PARAM_REQUEST_LIST`/`PARAM_VALUE` for bulk MAVLink downloads.
- Uses pymavlink parameter-send support for writes and locally registers the MAVLink-2 `PARAM_ERROR` decoder required
  by the pinned pymavlink version. It polls `PARAM_VALUE` for individual reads.
- Validates parameter names and numeric value types locally before writes.

#### FTP-over-MAVLink

- Uses MAVFTP for supported parameter-default downloads and file operations.
- Supports directory operations, file uploads/downloads, progress reporting, CRC operations, and burst reads.
- Falls back to MAVLink only for parameter download; arbitrary file operations require MAVFTP.

### Error Handling Strategy

- **Connection errors**: Return error messages and, for several serial failures, actionable guidance. Pymavlink receives the configured retry/autoreconnect settings.
- **Timeout errors**: Use operation-specific fixed timeouts and return an error when they expire.
- **Parameter download errors**: Fall back from MAVFTP to MAVLink; reject incomplete MAVLink downloads.
- **Parameter write errors**: Validate locally before sending and report a matching newer-firmware `PARAM_ERROR`
  rejection. Read back the parameter when positive verification is required or when the firmware provides no rejection response.

## Testing Strategy

### Test Organization

The test suite separates manager/facade tests from SITL coverage:

- `test_backend_flightcontroller.py` exercises facade delegation, lifecycle, commands, parameter workflows, and error
  paths.
- `test_backend_flightcontroller_business_logic.py` exercises pure calculations and validation functions.
- `test_backend_flightcontroller_connection.py`, `test_backend_flightcontroller_params.py`,
  `test_backend_flightcontroller_commands.py`, and `test_backend_flightcontroller_files.py` exercise the specialized managers.
- `test_backend_flightcontroller_sitl.py` uses a real ArduCopter SITL TCP connection and is marked with both `integration` and `sitl` where applicable.

Test names and marker use vary by test; do not treat BDD-style names or integration markers as universal conventions.
Avoid recording fixed test counts here because they change as the suite evolves.

### Running Tests Selectively

```bash
# Run all flight-controller tests, including unit-prefixed modules
pytest tests/test_*flightcontroller*.py tests/unit_backend_flightcontroller*.py -v

# Run flight-controller tests that are not marked SITL
pytest tests/test_*flightcontroller*.py tests/unit_backend_flightcontroller*.py -m "not sitl" -v

# Run integration-marked tests
pytest -m integration tests/ -v

# Run SITL-marked tests
pytest -m sitl tests/ -v

# Run a specific manager test module
pytest tests/test_backend_flightcontroller_params.py -v
```

## File Structure

```text
ardupilot_methodic_configurator/
├── backend_flightcontroller.py
├── backend_flightcontroller_connection.py
├── backend_flightcontroller_params.py
├── backend_flightcontroller_commands.py
├── backend_flightcontroller_files.py
├── backend_flightcontroller_protocols.py
├── backend_flightcontroller_business_logic.py
├── backend_flightcontroller_factory_mavlink.py
├── backend_flightcontroller_factory_mavftp.py
├── backend_flightcontroller_factory_serial.py
├── backend_mavlink_param_error.py
├── backend_mavftp.py
├── data_model_par_dict.py
├── data_model_flightcontroller_info.py
├── data_model_fc_ids.py
├── frontend_tkinter_connection_selection.py
├── frontend_tkinter_flightcontroller_connection_progress.py
└── frontend_tkinter_flightcontroller_info.py
```

## Dependencies

- **Python standard library**: `contextlib`, `logging`, `os`, `pathlib`, `random`, `struct`, `time`, and typing utilities.
- **Python standard-library GUI**: `tkinter` and `tkinter.ttk`.
- **Third-party libraries**: `pymavlink` for MAVLink and `pyserial` for serial-port discovery and communication.
- **Project modules**: parameter models (`Par`, `ParDict`), program settings, GUI base/progress windows, and the MAVFTP backend.
