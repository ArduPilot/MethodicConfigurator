# Correctly configure ArduPilot for your vehicles on your first attempt

<!--
SPDX-FileCopyrightText: 2024-2025 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
-->

| Lint | Quality | Test | Deploy | Maintain |
| ---- | ------- | ---- | ------ | -------- |
| [![Pylint](https://github.com/ArduPilot/MethodicConfigurator/actions/workflows/pylint.yml/badge.svg)](https://github.com/ArduPilot/MethodicConfigurator/actions/workflows/pylint.yml) | [![Codacy Badge](https://app.codacy.com/project/badge/Grade/720794ed54014c58b9eaf7a097a4e98e)](https://app.codacy.com/gh/amilcarlucas/MethodicConfigurator/dashboard?utm_source=gh&utm_medium=referral&utm_content=&utm_campaign=Badge_grade) | [![Python unit-tests](https://github.com/ArduPilot/MethodicConfigurator/actions/workflows/unit-tests.yml/badge.svg)](https://github.com/ArduPilot/MethodicConfigurator/actions/workflows/unit-tests.yml) | [![pages-build-deployment](https://github.com/ArduPilot/MethodicConfigurator/actions/workflows/pages/pages-build-deployment/badge.svg)](https://github.com/ArduPilot/MethodicConfigurator/actions/workflows/pages/pages-build-deployment) | [![Average time to resolve an issue](http://isitmaintained.com/badge/resolution/ArduPilot/MethodicConfigurator.svg)](http://isitmaintained.com/project/ArduPilot/MethodicConfigurator) |
| [![test Python cleanliness](https://github.com/ArduPilot/MethodicConfigurator/actions/workflows/ruff.yml/badge.svg)](https://github.com/ArduPilot/MethodicConfigurator/actions/workflows/ruff.yml) | [![OpenSSF Best Practices](https://www.bestpractices.dev/projects/9101/badge)](https://www.bestpractices.dev/projects/9101) | [![Pytest tests](https://github.com/ArduPilot/MethodicConfigurator/actions/workflows/pytest.yml/badge.svg)](https://github.com/ArduPilot/MethodicConfigurator/actions/workflows/pytest.yml) | [![Upload MethodicConfigurator Package](https://github.com/ArduPilot/MethodicConfigurator/actions/workflows/python-publish.yml/badge.svg)](https://github.com/ArduPilot/MethodicConfigurator/actions/workflows/python-publish.yml) | [![Percentage of issues still open](http://isitmaintained.com/badge/open/ArduPilot/MethodicConfigurator.svg)](http://isitmaintained.com/project/ArduPilot/MethodicConfigurator) |
| [![mypy](https://github.com/ArduPilot/MethodicConfigurator/actions/workflows/mypy.yml/badge.svg)](https://github.com/ArduPilot/MethodicConfigurator/actions/workflows/mypy.yml) | [![Known Vulnerabilities](https://snyk.io/test/github/amilcarlucas/MethodicConfigurator/badge.svg)](https://app.snyk.io/org/amilcarlucas/project/c8fd6e29-715b-4949-b828-64eff84f5fe1) | [![codecov](https://codecov.io/github/amilcarlucas/MethodicConfigurator/graph/badge.svg?token=76P928EOL2)](https://codecov.io/github/amilcarlucas/MethodicConfigurator) | [![Windows Build](https://github.com/ArduPilot/MethodicConfigurator/actions/workflows/windows_build.yml/badge.svg)](https://github.com/ArduPilot/MethodicConfigurator/actions/workflows/windows_build.yml) | |
| [![markdown](https://github.com/ArduPilot/MethodicConfigurator/actions/workflows/markdown-lint.yml/badge.svg)](https://github.com/ArduPilot/MethodicConfigurator/actions/workflows/markdown-lint.yml) | [![Code Climate](https://codeclimate.com/github/amilcarlucas/MethodicConfigurator.png)](https://codeclimate.com/github/amilcarlucas/MethodicConfigurator) | [![Coverity Scan Build Status](https://scan.coverity.com/projects/30346/badge.svg)](https://scan.coverity.com/projects/ardupilot-methodic-configurator) | | |
| [![md-link-check](https://github.com/ArduPilot/MethodicConfigurator/actions/workflows/markdown-link-check.yml/badge.svg)](https://github.com/ArduPilot/MethodicConfigurator/actions/workflows/markdown-link-check.yml) | | | | |

*ArduPilot Methodic Configurator* is a software, developed by ArduPilot developers, that semi-automates a
[clear, proven and safe configuration sequence](https://ardupilot.github.io/MethodicConfigurator/TUNING_GUIDE_ArduCopter) for ArduCopter drones.
We are working on extending it to [ArduPlane](https://ardupilot.github.io/MethodicConfigurator/TUNING_GUIDE_ArduPlane),
[Heli](https://ardupilot.github.io/MethodicConfigurator/TUNING_GUIDE_Heli) and
[Rover](https://ardupilot.github.io/MethodicConfigurator/TUNING_GUIDE_Rover) vehicles.
But for those it is still very incomplete.

- **clear**: the sequence is linear, executed one step at the time with no hidden complex dependencies
- **proven**: the software has been used by hundreds of ArduPilot developers and users. From beginners to advanced. On big and small vehicles.
- **safe**: the sequence reduces trial-and-error and reduces the amount of flights required to configure the vehicle

Let's compare it with the traditional tool used to configure ArduPilot: a generalist Ground Control Station (GCS) software.

| Feature | Mission Planner, QGroundControl, ... etc | ArduPilot Methodic Configurator |
| ------- | ---------------------------------------- | ------------------------------- |
| configuration type | manual [^1]  | semi-automated [^2] |
| explains what to do | No | Yes  |
| explains when to do something | No, leaves you lost | Yes, explains the path |
| explains why do something | No | Yes |
| configuration method | a different menu for each task, some tasks have no menu, so you need to dig into the 1200 parameters | each task only presents you a relevant subset of parameters |
| parameter documentation | Yes, only on the full-parameter tree view | Yes |
| displays relevant documentation | No | Yes |
| makes sure you do not forget a step | No | Yes |
| checks that parameters get correctly uploaded | No | Yes |
| reuse params in other vehicles | No, unless you hand edit files | Yes, out-of-the-box |
| documents why you changed each parameter | No | Yes |
| tutorials and learning resources | No, scattered and not integrated | Yes, context-aware help integrated |

[^1]: you need to know what/when/why you are doing
[^2]: it explains what you should do, when you should do it and why

<!-- ![When to use ArduPilot Methodic Configurator](https://github.com/ArduPilot/MethodicConfigurator/blob/master/images/when_to_use_amc.png?raw=true) -->

It's simple graphical user interface (GUI) manages and visualizes ArduPilot parameters, parameter files and documentation.

![Application Screenshot](https://github.com/ArduPilot/MethodicConfigurator/blob/master/images/App_screenshot1.png?raw=true)

No visible menus, no hidden menus, no complicated options, what you see is what gets changed.

## 1. Quick overview of the entire process

To methodically build, configure and tune ArduPilot vehicles follow this sequence of steps:

### 1.1 Select the vehicle components

- while [choosing an Autopilot](https://ardupilot.org/copter/docs/common-autopilots.html) and
  [other hardware](https://ardupilot.org/copter/docs/common-optional-hardware.html) components
  [avoid these components](https://discuss.ardupilot.org/t/hardware-to-avoid-when-building-your-first-multirotor/114014/1)
- Use [ecalc for multirotor](https://www.ecalc.ch/index.htm) to select the propulsion system.
- follow [hardware best practices](https://ardupilot.github.io/MethodicConfigurator/TUNING_GUIDE_ArduCopter#11-multicopter-hardware-best-practices)

### 1.2 Install Software

- Install ArduPilot Methodic Configurator on [MS windows](https://ardupilot.github.io/MethodicConfigurator/INSTALL.html#ms-windows-installation),
  [linux](https://ardupilot.github.io/MethodicConfigurator/INSTALL.html#linux-installation) or
  [MacOS](https://ardupilot.github.io/MethodicConfigurator/INSTALL.html##macos-installation)
- [Install the latest Mission Planner version](https://ardupilot.github.io/MethodicConfigurator/INSTALL.html#install-mission-planner-software-on-a-pc-or-mac)
- [Install the latest ArduPilot firmware on your flight controller board](https://ardupilot.github.io/MethodicConfigurator/INSTALL.html#install-ardupilot-firmware-on-the-flight-controller)

### 1.3 Input vehicle components and component connections into ArduPilot Methodic Configurator

The software needs this information to automatically pre-select configuration settings relevant to your specific vehicle

- [Start the ArduPilot Methodic Configurator and select a vehicle that resembles yours](#5-use-the-ardupilot-methodic-configurator-software-for-the-first-time)
  and input vehicle components and component connections information into the ArduPilot Methodic Configurator *component editor window*

### 1.4 Perform IMU temperature calibration before assembling the autopilot into the vehicle (optional)

IMU temperature calibration reduces the probability of *Accel inconsistent* and *Gyro inconsistent* errors and reduces the time required to arm the vehicle.
IMU temperature calibration requires lowering the temperature of the autopilot (flight controller) to circa -20°C.
That is harder to do once the autopilot is assembled inside the vehicle, hence it is done now.

- [start the software](#6-configure-the-vehicles-parameters-in-a-traceable-way)
- Perform [IMU temperature calibration](https://ardupilot.github.io/MethodicConfigurator/TUNING_GUIDE_ArduCopter#21-configure-imu-temperature-calibration-using-the-offline-calibration-tool)

### 1.5 Assemble all components except the propellers

Assemble and connect all components. Make sure you [follow best practices](https://ardupilot.github.io/MethodicConfigurator/TUNING_GUIDE_ArduCopter#11-multicopter-hardware-best-practices)

### 1.6 Basic mandatory configuration

Again using the [*ArduPilot Methodic configurator* software GUI](#7-use-the-ardupilot-methodic-configurator-software-after-having-created-a-vehicle-from-a-template)
perform the following steps:

- [04_board_orientation.param](https://ardupilot.github.io/MethodicConfigurator/TUNING_GUIDE_ArduCopter#61-configure-flight-controller-orientation) flight controller orientation
- [05_remote_controller.param](https://ardupilot.github.io/MethodicConfigurator/TUNING_GUIDE_ArduCopter#62-configure-the-rc-receiver) remote controller connections and protocol
- [06_telemetry.param](https://ardupilot.github.io/MethodicConfigurator/TUNING_GUIDE_ArduCopter#63-configure-telemetry) telemetry transceiver connections and protocol (optional)
- [07_esc.param](https://ardupilot.github.io/MethodicConfigurator/TUNING_GUIDE_ArduCopter#64-configure-the-esc) Electronic-Speed-Controller connections and protocol
- [08_batt1.param](https://ardupilot.github.io/MethodicConfigurator/TUNING_GUIDE_ArduCopter#65-configure-the-primary-battery-monitor) Battery health and state of charge monitoring
- [10_gnss.param](https://ardupilot.github.io/MethodicConfigurator/TUNING_GUIDE_ArduCopter#67-configure-the-gnss-receivers) GNSS receiver connection and protocol
- [11_initial_atc.param](https://ardupilot.github.io/MethodicConfigurator/TUNING_GUIDE_ArduCopter#68-initial-attitude-pid-gains-vehicle-size-dependent) initial attitude
  PID gains (vehicle size dependent)

Now use [Mission Planner](https://firmware.ardupilot.org/Tools/MissionPlanner/) to do:

- [12_mp_setup_mandatory_hardware.param](https://ardupilot.github.io/MethodicConfigurator/TUNING_GUIDE_ArduCopter#69-configure-mandatory-hardware-parameters)
  calibrate vehicle sensors

And continue with the [*ArduPilot Methodic configurator* software GUI](#7-use-the-ardupilot-methodic-configurator-software-after-having-created-a-vehicle-from-a-template):

- [13_general_configuration.param](https://ardupilot.github.io/MethodicConfigurator/TUNING_GUIDE_ArduCopter#610-general-configuration) general misc configuration
- [Test if the hardware diagnostics are OK](https://ardupilot.github.io/MethodicConfigurator/TUNING_GUIDE_ArduCopter#611-ardupilot-hardware-report)
- [14_logging.param](https://ardupilot.github.io/MethodicConfigurator/TUNING_GUIDE_ArduCopter#612-configure-logging) configure Dataflash/SDCard logging (black box data)
- [15_motor.param](https://ardupilot.github.io/MethodicConfigurator/TUNING_GUIDE_ArduCopter#613-motorpropeller-order-and-direction-test) motor order and direction tests.
  ESC linearization.
- [16_pid_adjustment.parm](https://ardupilot.github.io/MethodicConfigurator/TUNING_GUIDE_ArduCopter#614-optional-pid-adjustment) attitude PID gains (vehicle size dependent)
- [17_remote_id.param](https://ardupilot.github.io/MethodicConfigurator/TUNING_GUIDE_ArduCopter#615-remote-id-aka-drone-id) required by law in many countries
- [18_notch_filter_setup.param](https://ardupilot.github.io/MethodicConfigurator/TUNING_GUIDE_ArduCopter#616-notch-filters-setup) to remove motor noise,
  reduce power consumption and increase flight stability

### 1.7 Assemble propellers and perform the first flight

Now that all mandatory configuration steps are done you can [perform the first flight](https://ardupilot.github.io/MethodicConfigurator/TUNING_GUIDE_ArduCopter#7-assemble-propellers-and-perform-the-first-flight)

### 1.8 Minimalistic mandatory tuning

These are the very [minimum tuning steps](https://ardupilot.github.io/MethodicConfigurator/TUNING_GUIDE_ArduCopter#8-minimalistic-mandatory-tuning) required for a stable flight:

- Load the `.bin` log file from the first flight into [Notch filter webtool](https://firmware.ardupilot.org/Tools/WebTools/FilterReview/)
- [19_notch_filter_results.param](https://ardupilot.github.io/MethodicConfigurator/TUNING_GUIDE_ArduCopter#81-notch-filter-calibration) use the webtool information to
  configure the notch filter(s)
- [20_throttle_controller.param](https://ardupilot.github.io/MethodicConfigurator/TUNING_GUIDE_ArduCopter#82-configure-the-throttle-controller) the altitude controller
  depends on the power-to-thrust ratio found in the first flight
- [21_ekf_config.param](https://ardupilot.github.io/MethodicConfigurator/TUNING_GUIDE_ArduCopter#83-configure-the-ekf-altitude-source-weights) sometimes
  the EKF3 needs a tune to maintain altitude
- [22_quick_tune_setup.param](https://ardupilot.github.io/MethodicConfigurator/TUNING_GUIDE_ArduCopter#84-second-flight-pid-vtol-quiktune-lua-script-or-manual-pid-tune) and
  [23_quick_tune_results.param](https://ardupilot.github.io/MethodicConfigurator/TUNING_GUIDE_ArduCopter#84-second-flight-pid-vtol-quiktune-lua-script-or-manual-pid-tune),
  you need lua scripting support to do this if not available you can tune manually.

That is it, if you are impatient and do not want an optimized vehicle you can skip to [everyday use](#113-everyday-use).

### 1.9 Standard tuning (optional)

These are the [standard tuning steps](https://ardupilot.github.io/MethodicConfigurator/TUNING_GUIDE_ArduCopter#9-standard-tuning-optional) required for an optimized flight:

- [24_inflight_magnetometer_fit_setup.param](https://ardupilot.github.io/MethodicConfigurator/TUNING_GUIDE_ArduCopter#91-third-flight-magfit), use lua scripted
  flight path or fly manually, store the results using
  [25_inflight_magnetometer_fit_results.param](https://ardupilot.github.io/MethodicConfigurator/TUNING_GUIDE_ArduCopter#912-calculate-inflight-magfit-calibration), use the
  [magfit webtool](https://firmware.ardupilot.org/Tools/WebTools/MAGFit/) to calculate a file that the ardupilot methodic configurator can use
- [26_quick_tune_setup.param](https://ardupilot.github.io/MethodicConfigurator/TUNING_GUIDE_ArduCopter#921-setup-quicktune) and
  [27_quick_tune_results.param](https://ardupilot.github.io/MethodicConfigurator/TUNING_GUIDE_ArduCopter#922-store-quicktune-results-to-file) Redo quick-tune now that
  the compass magnetic interference is fully calibrated
- [28_evaluate_the_aircraft_tune_ff_disable.param](https://ardupilot.github.io/MethodicConfigurator/TUNING_GUIDE_ArduCopter#93-fifth-flight-evaluate-the-aircraft-tune---part-1)
  and
  [29_evaluate_the_aircraft_tune_ff_enable.param](https://ardupilot.github.io/MethodicConfigurator/TUNING_GUIDE_ArduCopter#94-sixth-flight-evaluate-the-aircraft-tune---part-2)
- [30_autotune_roll_setup.param](https://ardupilot.github.io/MethodicConfigurator/TUNING_GUIDE_ArduCopter#95-autotune-flights) and
  [31_autotune_roll_results.param](https://ardupilot.github.io/MethodicConfigurator/TUNING_GUIDE_ArduCopter#951-roll-axis-autotune) tune roll axis rate and angle PIDs
- [32_autotune_pitch_setup.param](https://ardupilot.github.io/MethodicConfigurator/TUNING_GUIDE_ArduCopter#952-pitch-axis-autotune) and
  [33_autotune_pitch_results.param](https://ardupilot.github.io/MethodicConfigurator/TUNING_GUIDE_ArduCopter#952-pitch-axis-autotune) tune pitch axis rate and angle PIDs
- [34_autotune_yaw_setup.param](https://ardupilot.github.io/MethodicConfigurator/TUNING_GUIDE_ArduCopter#953-yaw-axis-autotune) and
  [35_autotune_yaw_results.param](https://ardupilot.github.io/MethodicConfigurator/TUNING_GUIDE_ArduCopter#953-yaw-axis-autotune) tune yaw axis rate and angle PIDs
- [36_autotune_yawd_setup.param](https://ardupilot.github.io/MethodicConfigurator/TUNING_GUIDE_ArduCopter#954-yaw-d-axis-autotune-optional) and
  [37_autotune_yawd_results.param](https://ardupilot.github.io/MethodicConfigurator/TUNING_GUIDE_ArduCopter#954-yaw-d-axis-autotune-optional) tune yawd axis rate and
  angle PIDs
- [38_autotune_roll_pitch_retune_setup.param](https://ardupilot.github.io/MethodicConfigurator/TUNING_GUIDE_ArduCopter#955-roll-and-pitch-axis-re-autotune) and
  [39_autotune_roll_pitch_retune_results.param](https://ardupilot.github.io/MethodicConfigurator/TUNING_GUIDE_ArduCopter#955-roll-and-pitch-axis-re-autotune) re-tune roll
  and pitch pitch axis rate and angle PIDs

Now the standard tuning is complete you can skip to [everyday use](#113-everyday-use)

### 1.10 Improve altitude under windy conditions (optional)

- [40_windspeed_estimation.param](https://ardupilot.github.io/MethodicConfigurator/TUNING_GUIDE_ArduCopter#10-improve-altitude-under-windy-conditions-optional)
  estimates the wind speed
- [41_barometer_compensation.param](https://ardupilot.github.io/MethodicConfigurator/TUNING_GUIDE_ArduCopter#102-baro-compensation-flights)
  Uses the estimated wind speed to improve altitude stability

### 1.11 System identification for analytical PID optimization (optional)

- [42_system_id_roll.param, 43_system_id_pitch.param, 44_system_id_yaw.param](https://ardupilot.github.io/MethodicConfigurator/TUNING_GUIDE_ArduCopter#11-system-identification-for-analytical-pid-optimization-optional)
- [46_analytical_pid_optimization.param](https://ardupilot.github.io/MethodicConfigurator/TUNING_GUIDE_ArduCopter#112-analytical-multicopter-flight-controller-pid-optimization)

### 1.12 Position controller tuning (optional)

- [47_position_controller.param, 48_guided_operation.param, 49_precision_land.param](https://ardupilot.github.io/MethodicConfigurator/TUNING_GUIDE_ArduCopter#12-position-controller-tuning-optional)

### 1.13 Everyday use

Now that tuning and configuration are done, some logging and tests can be disabled and some more safety features enabled:

- [53_everyday_use.param](https://ardupilot.github.io/MethodicConfigurator/TUNING_GUIDE_ArduCopter#13-productive-configuration)

Enjoy your properly configured vehicle.

The following sections describe each step of the procedure in more detail.

## 2. Install *ArduPilot Methodic Configurator* software on a PC or Mac

Install ArduPilot Methodic Configurator on [MS windows](https://ardupilot.github.io/MethodicConfigurator/INSTALL.html#ms-windows-installation),
[linux](https://ardupilot.github.io/MethodicConfigurator/INSTALL.html#linux-installation) or
[MacOS](https://ardupilot.github.io/MethodicConfigurator/INSTALL.html##macos-installation)

## 3. Install *Mission Planner* software on a PC or Mac

[Install the latest Mission Planner version](https://ardupilot.github.io/MethodicConfigurator/INSTALL.html#install-mission-planner-software-on-a-pc-or-mac)

## 4. Install *ArduPilot* firmware on the flight controller

[Install the latest ArduPilot firmware on your flight controller board](https://ardupilot.github.io/MethodicConfigurator/INSTALL.html#install-ardupilot-firmware-on-the-flight-controller)

## 5. Use the *ArduPilot Methodic Configurator* software for the first time

See the [Use the *ArduPilot Methodic Configurator* software for the first time](USECASES.md#use-the-ardupilot-methodic-configurator-software-for-the-first-time)
usecase.

## 6. Configure the vehicle's parameters in a traceable way

The following simple loop is presented as welcome instructions:
![AMC welcome instructions](https://github.com/ArduPilot/MethodicConfigurator/blob/master/images/App_screenshot_instructions.png?raw=true)

Now do this in a loop until the software automatically closes or you are asked to close the software:

- Read all the documentation links displayed at the top of the GUI (marked with the big red number 4),
- Edit the parameter's *New value* and *Reason changed* fields to match your vehicle (marked with the big red number 5),
  - The *Reason changed* field is extremely important because:
    - if forces you to think, causing rational decisions instead of impulsive ones
    - justifies your decisions on a vehicle certification process required in most countries
    - allows for someone else to see if you know what you are doing
    - allows for someone else (or yourself after a few weeks) to understand your rationale
- Press *Del* and/or *Add* buttons to delete or add parameters respectively (marked with the big red number 5),
- If necessary scroll down using the scroll bar on the right and make sure you edit all parameters,
- Press *Upload selected params to FC, and advance to next param file* (marked with the big red number 7),
- Repeat from the top until the program automatically closes.

## 7. Use the *ArduPilot Methodic Configurator* software after having created a vehicle from a template

See the [Use the *ArduPilot Methodic Configurator* software after having created a vehicle from a template](USECASES.md#use-the-ardupilot-methodic-configurator-software-after-having-created-a-vehicle-from-a-template)
usecase.

Congratulations your flight controller is now fully configured in the safest and fastest way publicly known.

There is also [documentation on other use cases](https://ardupilot.github.io/MethodicConfigurator/USECASES.html)
and a detailed but generic [Usermanual](https://ardupilot.github.io/MethodicConfigurator/USERMANUAL.html).

## Install

See the [install instructions](https://ardupilot.github.io/MethodicConfigurator/INSTALL.html)

## Documentation and Support

Need [help or support](https://ardupilot.github.io/MethodicConfigurator/SUPPORT.html)

## Contributing

Want [to help us and contribute](https://github.com/ArduPilot/MethodicConfigurator/blob/master/CONTRIBUTING.md)?

## Software design and development

To meet the [Software requirements](https://ardupilot.github.io/MethodicConfigurator/ARCHITECTURE.html#software-requirements) a
[software architecture](https://ardupilot.github.io/MethodicConfigurator/ARCHITECTURE.html#the-software-architecture) was designed and implemented.

## Internationalization

The software is available in [multiple languages](https://github.com/ArduPilot/MethodicConfigurator/tree/master/ardupilot_methodic_configurator/locale).
On MS Windows the language is selected during install and that selection is stored in the desktop icon.
You can manually create multiple desktop icons, each will run the software in a different language.
On linux and MacOS the language is selectable by the `--language` command line argument.

See [contributing page](https://github.com/ArduPilot/MethodicConfigurator/blob/master/CONTRIBUTING.md) if you want to help us translate the software into your language.

## Code of conduct

To use and develop this software you must obey the [ArduPilot Methodic Configurator Code of Conduct](https://github.com/ArduPilot/MethodicConfigurator/blob/master/CODE_OF_CONDUCT.md).

## License

This software is cost free.
This project is licensed under the [GNU General Public License v3.0](https://github.com/ArduPilot/MethodicConfigurator/blob/master/LICENSE.md).

## Credits

It builds upon other [open-source software packages](https://ardupilot.github.io/MethodicConfigurator/credits/CREDITS.html)
