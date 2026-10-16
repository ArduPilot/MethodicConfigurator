# ESC telemetry

Step `09_esc_telemetry.param` displays live ESC readings for ArduCopter, ArduPlane,
Heli and Rover. Each ESC occupies a column. Measurement rows are RPM, voltage (V),
current (A), temperature (°C), consumption (mAh) and received telemetry packet count.
Missing and stale readings appear as `-`. The table starts with 16 columns and
reveals higher numbered ESCs, up to 32, when they report data. A horizontal scrollbar
provides access on narrower windows.

## Components and reuse

- `ardupilot_methodic_configurator/backend_esc_telemetry.py` owns MAVLink requests,
  source filtering, packet collection and observer cleanup. It obtains the existing
  connection through the `FlightController` facade.
- `ardupilot_methodic_configurator/data_model_esc_telemetry.py` defines typed snapshots,
  unit conversion, freshness rules and table rows. It has no Tkinter or I/O dependency.
- `ardupilot_methodic_configurator/plugins/frontend_tkinter_esc_telemetry.py` provides
  the embedded `EscTelemetryView`, its timer and plugin factories. The view accepts
  the reusable telemetry model directly, so other plugins can embed the same table.
  A factory-only dependency bundle also retains the existing `EscRpmScaleDataModel`;
  the factory embeds `EscRpmScaleView` when the component protocol is `Scripting`.
  The reusable telemetry backend/model have no dependency on that feature.

The plugin requires a flight-controller connection. Its registration uses the normal
shared factory dispatcher. All three PyInstaller specifications already collect
plugin submodules; the plugin's static imports collect the shared backend and model.
No additional dependencies or assets are required.

## Data flow and lifecycle

Every 250 ms the view polls the backend and refreshes its existing tree rows.
The backend sends `MAV_CMD_REQUEST_MESSAGE` for `ESC_TELEMETRY_1_TO_4` at most once per
second. ArduPilot maps this ID to its shared ESC sender, which sends all populated
groups. Requesting each group separately would be redundant and is not supported
by the message-ID mapping. These one-shot requests leave configured stream rates
and vehicle parameters unchanged. Unsupported firmware produces no readings.

An observer receives only ESC messages from the target system and component.
Each polling call reads at most 200 packets and uses a 10 ms receive budget.
Other observers remain registered. Snapshots carry a connection identity so data
cannot cross a connection replacement. Voltage and current convert from centi-units;
RPM and temperature retain the values transmitted by ArduPilot.

The model expires electrical telemetry after three seconds without a changed ESC
packet counter, even when other members of its four-ESC group continue reporting.
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
Existing custom project JSON overrides bundled steps; set its step-09 plugin to
`{"name": "esc_telemetry", "placement": "top"}` to enable the table there.

## Verification

`tests/test_esc_telemetry.py` exercises real encoded MAVLink packets and parser hooks,
all ESC groups, engineering units, padding, RPM-only readings, freshness, counter
wrap, source isolation, connection replacement, I/O recovery, request throttling,
Tkinter refresh, suspension, modal/locked operation, factories, scripting controls,
startup registration and configuration/schema validation for all vehicle workflows.
The existing ESC RPM-scale tests cover its retained script-generation behavior.
