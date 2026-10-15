# RC Receiver Plugin Architecture

The `rc_receiver` plugin checks receiver setup before RC calibration. It displays
exactly five channel bars labeled CH1 through CH5, a receiver RSSI bar, receiver
presence, current RC failsafe status, and whether failsafe was observed during
the current test. Instructions explain uploading parameter edits, moving the
first five channels, switching the transmitter off, and checking recovery.

## Components and data flow

| File | Responsibility |
| --- | --- |
| `plugins/data_model_rc_receiver.py` | Nonblocking telemetry polling, source filtering, freshness and failsafe history |
| `plugins/frontend_tkinter_rc_receiver.py` | Scrollable widgets, translated guidance, lifecycle and both plugin factories |
| `plugins/plugin_constants.py` | Declares `PLUGIN_RC_RECEIVER` |
| `__main__.py` | Independently imports and registers the plugin at startup |
| `configuration_steps_schema.json` | Accepts the plugin name |
| `configuration_steps_{ArduCopter,ArduPlane,Heli,Rover}.json` | Places the plugin beside receiver-step parameters |
| `tests/plugins/test_data_model_rc_receiver.py` | Receiver telemetry, failures, eligibility and configuration tests |
| `tests/plugins/test_frontend_tkinter_rc_receiver.py` | Visible behavior, factories, startup and timer cleanup tests |

Python paths in this table are relative to `ardupilot_methodic_configurator/`
except for tests. The design follows the model/view and plugin-local factory
patterns described in [RC calibration](ARCHITECTURE_rc_calibration.md).

The shared parameter editor creates the model through `PluginModelContext` and
the plugin factory. Only `FlightController` is injected into this model. An
injectable monotonic clock makes timeout behavior deterministic in tests.
The immutable `RCReceiverState` snapshot separates telemetry interpretation
from Tkinter presentation. No calibration, mapping, renderer or parameter-editor
dependency is required in the receiver model.

The view polls every 100 ms with `after()`. The model reads up to 50 packets
per poll from `FlightController.master`, counting unrelated traffic toward that
limit and retaining the latest channel and status readings. Source filtering uses
the selected FC system and component from discovery metadata, falling back to
pymavlink targets; component zero accepts any component of the selected system.
On the first poll after activation or reconnect, the model requests `RC_CHANNELS`
and `SYS_STATUS` at 5 Hz through `FlightController.request_rc_receiver_messages()`.
The facade delegates the two `MAV_CMD_SET_MESSAGE_INTERVAL` commands to the
command manager, using the same short ACK timeout as the SCALED_IMU request.
Both requests are attempted even if one fails, and existing telemetry remains
usable if firmware rejects a request. Polling performs no parameter writes,
calibration commands or uploads. Existing parameter-table editing and explicit
Upload remain responsible for applying receiver settings.

## Telemetry interpretation

- `RC_CHANNELS.chancount` determines which of CH1-CH5 exist. PWM 0 and 65535 are
  unavailable. Missing channels have empty bars and an Unavailable label.
  Bars span 800-2200 microseconds; numeric readings retain their actual values.
- Receiver `RC_CHANNELS.rssi` values 0-254 are displayed in the reported scale;
  255 is unavailable. Zero is valid. This is receiver RSSI, separate from GCS
  telemetry-radio RSSI, and is not presented as a universal percentage.
- `SYS_STATUS` receiver-present and enabled bits must both be set before the
  receiver health bit determines RC failsafe. An unhealthy receiver means
  failsafe detected; a healthy receiver means failsafe not active. Unreported
  or disabled receiver status is unknown. Other sensor failures and general
  heartbeat system state do not imply RC failsafe.
- Receiver presence means the FC has seen RC input; it does not independently
  prove current transmitter reception. Channel movement and the transmitter
  power-cycle test provide the practical checks described in the UI.
- Channels/RSSI and receiver status expire independently after three seconds.
  Missing telemetry clears readings and makes status unknown; it does not
  manufacture failsafe evidence. Transport errors immediately invalidate live
  readings. New telemetry restores them.
- A positive RC failsafe observation remains visible after recovery or telemetry
  loss. Changing the FC connection resets that evidence for a fresh test.

The field semantics follow the upstream [MAVLink common definitions](
https://github.com/mavlink/mavlink/blob/master/message_definitions/v1.0/common.xml).
ArduPilot's shared [GCS receiver-status implementation at Copter-4.6.3](
https://github.com/ArduPilot/ardupilot/blob/Copter-4.6.3/libraries/GCS_MAVLink/GCS.cpp#L354-L361)
sets receiver presence/enabled after RC input has been seen and receiver health
when `in_rc_failsafe()` is false. This shared code supports the bundled Copter,
Heli, Plane and Rover receiver steps. The plugin introduces no parameter groups
or version-gated controls. Firmware omitting these messages or status bits
remains explicitly unavailable or unknown.

## Lifecycle and packaging

Activation schedules one callback idempotently. Deactivation and destruction
cancel it, yielding the shared receiver to diagnostics, the file browser or
another step. Deactivation restores firmware default intervals (zero) for both
requested streams on the same connection and invalidates live snapshots while
retaining failsafe test history. Resuming requests the streams again. A changed
connection never receives cleanup commands intended for the previous controller.
The parameter editor pauses plugins before constructing the file browser and
resumes the same view after its close callback, provided the parent still exists.
Paired suspend/resume hooks preserve plugin state; legacy views use
deactivate/activate, matching diagnostics behavior.
All four bundled vehicle configurations use `placement: left` on
`06_remote_controller_receiver.param`. Projects supplying their own configuration
JSON need the equivalent plugin entry in that step.

The Windows, Linux and macOS PyInstaller specs already collect every submodule
of `ardupilot_methodic_configurator.plugins`; the new modules require no assets
or dependencies. New Python files carry SPDX headers and this root document is
covered by `REUSE.toml`.

## Verification

BDD tests use real models, real MAVLink messages and real Tkinter widgets.
Only transport, clock and parent application services are mocked. They cover
valid and unavailable channels/RSSI, RC-only failsafe and recovery, retained
evidence, source filtering, stale streams, bounded polling, disconnects and
I/O recovery. Integration checks cover both factories, startup, shared model
dispatch, FC requirements, all four JSON configurations and all platform specs.

Run the focused suite with:

```text
python -m pytest tests/plugins/test_data_model_rc_receiver.py tests/plugins/test_frontend_tkinter_rc_receiver.py
```

Hardware acceptance: upload receiver settings, verify movement of CH1-CH5,
confirm RSSI if supplied, switch the transmitter off and observe RC failsafe,
then restore transmitter power and verify recovery. Automated tests do not
replace this physical wiring and transmitter check.
