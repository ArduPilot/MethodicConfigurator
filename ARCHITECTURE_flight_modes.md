# Flight Modes Plugin

The `flight_modes` plugin appears above the parameter table on the ArduCopter
and ArduPlane `22_flight_modes.param` step, Heli `25_flight_modes.param`,
and Rover `18_flight_modes.param`. Live readings require a connected
flight controller. Custom configuration-step files can enable it by adding
`"plugin": {"name": "flight_modes", "placement": "top"}` to the step.

## Telemetry and display

- [The data model](ardupilot_methodic_configurator/plugins/data_model_flight_modes.py)
  reads the active mode number from `HEARTBEAT.custom_mode` and looks up its name
  using pymavlink's mode maps. QuadPlane parameters identify Plane firmware
  when it advertises a different vehicle type in the heartbeat.
- The model uses the controller's downloaded `FLTMODE_CH` value to find the
  switch channel in `RC_CHANNELS`. Rover uses `MODE_CH` and `MODE1` through
  `MODE6`, while the other vehicles use `FLTMODE_CH` and `FLTMODE1` through
  `FLTMODE6`. The model reads that channel's raw PWM, which can include an
  override above the physical receiver's channel count, and applies ArduPilot's
  switch thresholds. The slot represents the latest switch sample.
  The active mode can differ during failsafe, when a mode
  change is rejected, or when another input selects the mode.
- Mode and RC samples expire independently. A disabled channel, unavailable
  PWM or reported RC failsafe leaves the switch slot unavailable. After a
  failsafe, the slot requires a healthy receiver status and a fresh PWM sample.
  Unknown mode names still display the reported number.
- [The Tkinter view](ardupilot_methodic_configurator/plugins/frontend_tkinter_flight_modes.py)
  polls every 200 ms. The shared RC telemetry backend requests channel and
  receiver status streams, bounds each batch and filters it to the selected
  controller. Polling yields to modal dialogs and the editor's navigation lock.
  When the editor pauses or removes the view, it cancels polling and discards
  the samples. The view requests default intervals during normal cleanup and
  leaves the link to the connection monitor during recovery.

The plugin only displays telemetry. Mode selection and parameter updates use
the vehicle's existing controls and the parameter editor.

## Firmware references

The switch parameters and PWM decoding are available in the bundled workflow
versions without a firmware gate. See the
[Copter 4.7.3 parameters](https://github.com/ArduPilot/ardupilot/blob/Copter-4.7.3/ArduCopter/Parameters.cpp),
[Plane 4.7.3 parameters](https://github.com/ArduPilot/ardupilot/blob/Plane-4.7.3/ArduPlane/Parameters.cpp)
and [six-position switch decoder](https://github.com/ArduPilot/ardupilot/blob/Plane-4.7.3/libraries/RC_Channel/RC_Channel.cpp#L596-L622).
