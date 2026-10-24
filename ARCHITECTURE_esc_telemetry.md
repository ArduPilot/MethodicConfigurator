# ESC telemetry

The ESC telemetry step displays live ESC readings: step 08 for ArduCopter and
ArduPlane, step 14 for Heli and step 11 for Rover. Each ESC occupies a column.
Measurement rows are RPM, voltage (V),
current (A), temperature (°C), consumption (mAh) and received telemetry packet count.
Missing and stale readings appear as `-`. The table starts with no ESC columns and
shows only detected ESCs, up to ESC 32, in their original numeric order. RPM-only
telemetry also reveals its ESC. Unused slots and gaps stay hidden. Detected columns
remain visible until observations are cleared, so stale readings can be inspected.
ESC columns are 55 pixels wide; a horizontal scrollbar provides access on narrower windows.

## Components and reuse

- `ardupilot_methodic_configurator/backend_esc_telemetry.py` owns MAVLink requests,
  source filtering, packet collection and observer cleanup. It obtains the existing
  connection through the `FlightController` facade.
- `ardupilot_methodic_configurator/data_model_esc_telemetry.py` defines typed snapshots,
  unit conversion, freshness rules and table rows. It has no Tkinter or I/O dependency.
- `ardupilot_methodic_configurator/frontend_tkinter_esc_telemetry.py` provides
  the reusable `EscTelemetryView` and its timer. The view accepts the telemetry
  model and base window directly, independently of plugin registration.
- `ardupilot_methodic_configurator/plugins/frontend_tkinter_esc_telemetry.py` supplies
  the plugin factories for the dedicated ESC telemetry configuration step.
  RPM scaling uses the separate `esc_rpm_scale` plugin at the motor configuration
  step: step 12 for ArduCopter and ArduPlane, step 32 for Heli and step 23 for Rover.
  Its controls appear when the component protocol is `Scripting`.
- `MotorTestView` embeds the same `EscTelemetryView` below its motor controls in
  the scrollable content frame. It forwards activation, suspension, resumption and
  deactivation to the child. Tkinter destroys the child with its parent, releasing
  its polling timer and observer. Controller restart tasks also pause the table.

The plugin requires a flight-controller connection. Its registration uses the normal
shared factory dispatcher. All three PyInstaller specifications already collect
plugin submodules; static imports collect the shared view, backend and model.
No additional dependencies or assets are required.

## Data flow and lifecycle

Every 250 ms the view polls the backend and refreshes its existing tree rows.
The backend sends `MAV_CMD_REQUEST_MESSAGE` for `ESC_TELEMETRY_1_TO_4` at most once per
second. ArduPilot maps this ID to its shared ESC sender, which sends all populated
groups. Requesting each group separately would be redundant and is not supported
by the message-ID mapping. These one-shot requests leave configured stream rates
and vehicle parameters unchanged. Unsupported firmware produces no readings.

An observer filters ESC messages using the discovered FC system and component IDs,
falling back to pymavlink targets when discovery has not populated the FC info.
Only positive IDs constrain filtering; zero retains broadcast discovery behavior.
Requests use the same resolved identity, including when pymavlink leaves its target
component at zero after discovery.
Each polling call reads at most 200 packets and uses a 10 ms receive budget.
Other observers remain registered. Snapshots carry a connection identity so data
cannot cross a connection replacement. Voltage and current convert from centi-units;
RPM and temperature retain the values transmitted by ArduPilot.

ESC polling can also parse battery messages while draining the shared connection.
The battery reader recovers those readings from pymavlink's per-battery message
cache, retaining their original receipt timestamps. This keeps motor safety checks
and multiple-battery monitoring available without refreshing stale readings or
repeatedly requesting a stream merely because another reader consumed its packets.

The model expires electrical telemetry after three seconds without a changed ESC
packet counter, even when other members of its four-ESC group continue reporting.
Each captured reading carries its monotonic receipt time. Freshness uses that time,
so packets parsed by another reader during a modal dialog do not become fresh again
when deferred ESC polling resumes.
Counter wrap is accepted. RPM is independently refreshed by nonzero RPM or fresh
telemetry. All-zero unused slots are ignored. RPM-only telemetry can show RPM while
other rows remain `-`. A genuine zero measurement is displayed for a reporting ESC.

The legacy ESC messages have no per-field validity flags. Once an ESC reports a
telemetry packet count, zero-filled unsupported fields cannot be distinguished from
measured zeros. RPM-only all-zero stopped motors also cannot be distinguished from
unused slots. The UI preserves these protocol limitations rather than inventing
sentinel values. ESC numbering follows `ESC_TELEM_MAV_OFS`, not motor test order.

Activation schedules one timer. Suspension, deactivation and destruction cancel it,
remove only this backend's hook and discard observations. Resumption starts fresh.
Modal dialogs and the shared navigation lock also defer polling while another tool
owns the connection. Read/write failures clear live data and allow later retries.

## Firmware evidence

Implementation was checked against the local ArduPilot checkout at commit
`92b0cd788ec29406f26c6f9c31d5ceedbd1cc538`, using its CodeGraph index:

- [Shared message-ID mapping and request handler](https://github.com/ArduPilot/ardupilot/blob/92b0cd788ec29406f26c6f9c31d5ceedbd1cc538/libraries/GCS_MAVLink/GCS_Common.cpp)
  map the first ESC group to the shared sender across vehicle families.
- [ESC group sender and unit conversion](https://github.com/ArduPilot/ardupilot/blob/92b0cd788ec29406f26c6f9c31d5ceedbd1cc538/libraries/AP_ESC_Telem/AP_ESC_Telem.cpp)
  show four-member padding, RPM-only reporting, counts and groups through ESC 32.
- [ESC configuration](https://github.com/ArduPilot/ardupilot/blob/92b0cd788ec29406f26c6f9c31d5ceedbd1cc538/libraries/AP_ESC_Telem/AP_ESC_Telem.h)
  derives the maximum ESC count from `NUM_SERVO_CHANNELS`.

This monitor does not require a new parameter or a firmware version condition.
Availability depends on the firmware build, ESC hardware and configured telemetry.
Existing custom project JSON overrides bundled steps; set its ESC telemetry step's
plugin to `{"name": "esc_telemetry", "placement": "top"}` to enable the table there.
Configure `esc_rpm_scale` separately at the motor step, with `placement` set to
`left` and an `if` condition of
`vehicle_components['ESC']['ESC->FC Telemetry']['Protocol'] == 'Scripting'`.

## Verification

`tests/test_esc_telemetry.py` exercises real encoded MAVLink packets and parser hooks,
all ESC groups, engineering units, padding, RPM-only readings, freshness, counter
wrap, source isolation, connection replacement, I/O recovery, request throttling,
Tkinter refresh, suspension, modal/locked operation, factories, scripting controls,
startup registration and configuration/schema validation for all vehicle workflows.
The existing ESC RPM-scale tests cover its retained script-generation behavior.
