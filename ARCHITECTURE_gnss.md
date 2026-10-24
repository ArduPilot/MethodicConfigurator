# GNSS Plugin Architecture

## Purpose and display

The `gnss` plugin displays receiver fix status, latitude and longitude in
seven decimal degree places, height above mean sea level in metres, time,
number of satellites and horizontal/vertical accuracy in metres. It presents
receiver 1 and receiver 2 independently. The second column is hidden until a
fresh `GPS2_RAW` report indicates detected hardware (`fix_type` 1 through 8).
A detected receiver without a fix remains visible; absent hardware, expired
data, disconnects and reception errors hide the column again. Accuracy is receiver-reported position
uncertainty; HDOP and VDOP are not substituted for accuracy in metres.

The plugin is connected to the GNSS configuration step for all bundled vehicle
families: Copter and Plane step 18, Heli step 21, Rover step 15. These families
provide the common MAVLink GPS reports, so no firmware gate is needed.
Custom project configurations must add
`"plugin": {"name": "gnss", "placement": "top"}` to their GNSS step.

## Components and data flow

| Responsibility | File under `ardupilot_methodic_configurator/` |
| --- | --- |
| Bounded reception and message requests | `plugins/backend_gnss.py` |
| Fix, unit, time and availability interpretation | `plugins/data_model_gnss.py` |
| Embedded display and lifecycle | `plugins/frontend_tkinter_gnss.py` |
| Existing shared connection monitor | `backend_data_telemetry.py` |
| Registration | `__main__.py`, `plugins/plugin_constants.py` |
| Eligibility and placement | `configuration_steps_*.json`, `configuration_steps_schema.json` |

`GnssBackend` extends the existing shared telemetry observer. It requests
`GPS_RAW_INT`, `GPS2_RAW` and `SYSTEM_TIME` snapshots once a second using
`MAV_CMD_REQUEST_MESSAGE`. Requests do not wait for acknowledgments or change
persistent parameters or stream rates. Firmware may decline a message request;
the monitor also accepts normally streamed reports. No new connection or
independent receive loop is opened. Existing reception limits remain 200
packets or 10 ms per poll, with Tk polling every 250 ms.

The model accepts only reports from the selected autopilot system/component.
Data expires after three seconds. Disconnects, reception errors and missing
receiver messages clear readings instead of leaving an apparently current fix.
No-fix reports retain status and satellite count; latitude/longitude require a
2D fix, and height/accuracy require a 3D fix. Missing or zero accuracy extensions,
invalid satellite counts, malformed numbers and non-finite values display N/A.
Zero coordinates, negative height and zero satellites remain valid measurements.

The `Local time (FC)` row adds the current downloaded `BRD_RTC_TZ_MIN`
parameter (minutes) to fresh `SYSTEM_TIME.time_unix_usec`. It uses the vehicle's
configured offset, independently of the computer's timezone, and displays the
UTC offset alongside the local date and time. Date rollover is handled by the
fixed-offset timezone conversion. Missing, non-finite, fractional or out-of-range
offsets (outside -720 to +840 minutes) display N/A.
Missing, zero, malformed, stale or unrepresentable UTC displays N/A; there is
no fallback to receiver uptime. This is the flight controller's reported UTC
clock converted to local time, normally synchronized from GNSS, rather than an individual receiver's
calendar time. Its active source is not exposed in these telemetry messages.
ArduPilot internally receives GPS week/time-of-week, but sends
`last_fix_time_ms * 1000` in `GPS_RAW_INT` and `GPS2_RAW`. See the stable
[ArduPilot GPS implementation](https://github.com/ArduPilot/ardupilot/blob/Copter-4.6.3/libraries/AP_GPS/AP_GPS.cpp#L1284-L1324).

## Protocol evidence

The [MAVLink GPS_RAW_INT definition](https://mavlink.io/en/messages/common.html#GPS_RAW_INT)
provides coordinates in degrees times 10⁷, height in millimetres above mean sea
level, satellite count with 255 meaning unknown, and MAVLink 2 accuracy
extensions in millimetres. The
[GPS2_RAW definition](https://mavlink.io/en/messages/common.html#GPS2_RAW)
provides the second receiver. MAVLink 1 reports lack accuracy extensions and
therefore show unavailable accuracy. The
[SYSTEM_TIME definition](https://mavlink.io/en/messages/common.html#SYSTEM_TIME)
provides UNIX time. ArduPilot's
[Copter 4.6.3 common MAVLink implementation](https://github.com/ArduPilot/ardupilot/blob/Copter-4.6.3/libraries/GCS_MAVLink/GCS_Common.cpp)
handles common GNSS messages and message requests for the vehicle families.

## Lifecycle and packaging

Factories require a connected flight controller and inject the existing facade.
The view uses a ScrollFrame and translated labels. Polling pauses while a modal
dialog or navigation lock owns the connection. Deactivation, suspension and
destruction cancel the timer, detach the observer and clear values. Resumption
attaches a fresh observer and issues new requests, including after reconnection.
Suspension cleanup sends no commands to a recovering controller.

All three PyInstaller specs collect every plugin submodule, including the new
backend, model and view. No additional dependencies or data assets are needed.
