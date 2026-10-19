# Data telemetry plugin

The `data_telemetry` plugin displays connectivity measurements at
`08_telemetry.param` for ArduCopter, ArduPlane, Heli and Rover. The separate
[MAVLink inspector sub-application](ARCHITECTURE_mavlink_inspector.md) opens
from the editor header on any step and also runs standalone.

## Components and data flow

- `backend_data_telemetry.py`: reads the existing `FlightController.master`
  connection and attaches a PyMAVLink message observer. Snapshots contain parser
  counters, bounded message summaries and the latest radio report on that transport.
- `backend_radio_status.py`: sends a GCS heartbeat immediately when monitoring
  starts, then once per second on the existing transport. SiK radios
  require a heartbeat on their local serial input to enable injected radio
  reports. The connection manager owns the sender, which runs independently of
  polling until disconnect. Pausing or closing either telemetry host preserves
  the heartbeat schedule so leaving monitoring does not trigger a GCS failsafe.
  Disconnect signals the sender to stop, disables transport autoreconnection,
  cancels pending serial writes where supported and waits at most one second
  for the worker before closing the transport. A stalled worker keeps its old
  connection and stop event, so it cannot restart on a new connection;
  a new connection starts heartbeats only when monitoring is requested again.
- `data_model_data_telemetry.py`: immutable observations and display data;
  pure calculations for interval rates, stale data and connection boundaries.
  The factory injects the FC reference for the view's backend, without model I/O.
- `frontend_tkinter_radio_status.py`: reusable Tk frame displaying the
  active-connection status, RX/TX rates and parser errors above three-column
  name/value/unit radio readings. It has no label frames or connection controls.
- `plugins/frontend_tkinter_data_telemetry.py`: scrollable panel, bench-test
  guidance, translated labels, factories and registration. The MAVLink inspector
  embeds the same radio status view below its message table and fields.
- `tests/plugins/test_data_telemetry.py`: exercises real MAVLink encoding,
  parsing and hooks over an in-memory transport, domain calculations, real
  widgets, registration and schema-valid step wiring for all four families.

The frontend polls the backend every 250 ms, passes each loaded snapshot to the
model and renders its result in the panel. Opening the inspector suspends the
plugin and gives the sub-application its own bounded receive loop. Closing it
releases the observer and resumes the plugin with fresh measurement baselines.

## Measurement semantics and protocol limits

RX and TX are relative to AMC's active connection. Byte rates use differences
of PyMAVLink's received/sent byte counters over intervals of at least one second.
Received bytes include malformed/partial traffic. Per-message rates count
successfully decoded MAVLink wire packets, including MAVLink headers and signatures.
The first snapshot establishes a baseline; no rate is inferred from earlier traffic.
TX includes the GCS heartbeats sent since monitoring first started on the connection.

RX MAVLink parse errors/s uses the parser's error counter. Radio RX errors/s
uses differences of the reporting modem's cumulative `rxerrors` counter divided by the
time between radio reports. These are counts per second, not packet-loss
percentages. Counter decreases establish a fresh baseline to avoid fabricated
spikes after a reboot or wrap. Corrected packets (`fixed`) remain a separate count.

Both `RADIO` and `RADIO_STATUS` contain local/remote received signal strength,
noise, free TX buffer percentage, receive errors and corrected packets.
They contain neither TX error counters nor byte rates. TX errors therefore
display as unavailable. Remote RX RSSI describes reception at the far end;
RSSI/noise are raw device-dependent values, never assumed to be dBm or percentages.
RSSI/noise value 255 and TX buffer values outside 0–100 display as unavailable.
Zero remains a valid reading. See the
[RADIO_STATUS definition](https://mavlink.io/en/messages/common.html#RADIO_STATUS)
and [legacy RADIO definition](https://mavlink.io/en/messages/ardupilotmega.html#RADIO).

Modems inject status on the connected transport, often under a different
system/component from the autopilot. Neither message contains a serial-port or
link identifier. ArduPilot handles both as incoming modem reports; it does not
produce a separate selectable report for every serial port. Its
[routing code](https://github.com/ArduPilot/ardupilot/blob/master/libraries/GCS_MAVLink/MAVLink_routing.cpp#L124)
explicitly prevents forwarding these reports between MAVLink channels. Therefore
a USB connection cannot inspect another serial radio through ordinary forwarding.
The [SiK firmware](https://github.com/ArduPilot/SiK/blob/master/Firmware/radio/mavlink.c#L48)
uses fixed system/component IDs (51/68), further preventing these IDs from serving
as physical link identifiers.

AMC currently owns one live `FlightController.master`. Both hosts show the latest
radio report on that transport and offer no source-as-link selector. To monitor
another physical link, connect AMC through that link. Any future selection among
multiple live transports belongs to the inspector's top-level controls and must
switch its entire snapshot, including messages, fields, rates and radio readings.
The reusable radio view only renders loaded state.

Radio readings expire after three seconds; stale message rows retain their
fields/counts with increasing age and zero current rate. Source changes, counter
decreases and stale intervals discard the radio error rate immediately. Connection
changes and deactivation clear all baselines.

This plugin observes MAVLink and adds no firmware-specific parameter controls;
it therefore needs no firmware version gate. ArduPilot's
[Copter 4.6.0 radio handling source](https://github.com/ArduPilot/ardupilot/blob/Copter-4.6.0/libraries/GCS_MAVLink/GCS_Common.cpp)
accepts both message types in the common GCS layer. Hardware that does not emit
radio status still supports connection and message measurements.

## External operations, lifecycle and packaging

The monitor receives packets and enables connection-owned GCS heartbeats.
It sends no commands, alters no stream
intervals and edits no staged or FC parameters. Polling is nonblocking and limited
to 200 packets or 10 ms per tick; message summaries are capped at 512 source/type
combinations, with each field's display text capped at 512 characters.
The observer also captures messages parsed by other consumers while attached;
it preserves existing hooks and does not install a second connection or receiver.
Paired suspend/resume hooks pause the monitor during parameter uploads and
diagnostics. The polling loop also yields while a modal tool holds the Tk grab
or an operation holds the parent navigation lock, preserving its receive stream.

Deactivation cancels the timer, removes only this observer and clears measurements.
GCS heartbeats continue during suspension, other FC operations and step changes.
Destruction performs the same cleanup. Reactivation
starts exactly one timer. Read errors clear live observations and report a
connection problem; subsequent ticks can observe recovery.

Startup registration, plugin constants, schema and bundled step files wire the
feature through the shared factory. Customized projects overriding the bundled
configuration need this entry inside their `08_telemetry.param` step:

```json
"plugin": {
    "name": "data_telemetry",
    "placement": "top"
}
```

Windows, macOS and Linux PyInstaller specs already use
`collect_submodules("ardupilot_methodic_configurator.plugins")`, collecting
the dynamically loaded model, backend and frontend without spec changes.
No new runtime dependencies or package data are required.

## Bench verification

1. Remove propellers and leave the vehicle disarmed. Upload the desired serial
   telemetry parameters using the normal step controls, rebooting if required.
2. Connect AMC over the telemetry path being tested. USB measures USB traffic;
   it cannot establish the wireless link's throughput or range.
3. Observe RX/TX B/s, RSSI/noise and radio errors while safely changing antenna
   orientation and separation. TX includes the periodic GCS heartbeat.
4. Press `MAVLink inspector` below `Zip vehicle for Forum help`, select messages
   and check their rates and fields. Click headings to sort and verify the stripes
   follow the new row order as traffic updates. Close it to resume the panel.
5. Briefly interrupt the telemetry path. Radio values should become unavailable
   within three seconds, old message ages should increase and their rates reach zero.
   Restore the path and verify reception recovers; reconnect AMC if needed.
6. Change steps or open FC diagnostics. Monitoring should stop, GCS heartbeats
   should continue, and returning to the step should start a fresh measurement interval.
   Disconnect AMC and verify its heartbeat sender stops.

A safe bench check does not establish an operational flight range.
