# Correctly configure ArduPilot for your vehicles on your first attempt

| Lint | Quality | Test | Security | Deploy | Maintain |
| ---- | ------- | ---- | -------- | ------ | -------- |
| [![Pylint](https://github.com/ArduPilot/MethodicConfigurator/actions/workflows/pylint.yml/badge.svg)](https://github.com/ArduPilot/MethodicConfigurator/actions/workflows/pylint.yml) | [![Codacy Badge](https://app.codacy.com/project/badge/Grade/720794ed54014c58b9eaf7a097a4e98e)](https://app.codacy.com/gh/amilcarlucas/MethodicConfigurator/dashboard?utm_source=gh&utm_medium=referral&utm_content=&utm_campaign=Badge_grade) | [![pytest status](https://gist.githubusercontent.com/amilcarlucas/81b511dc0ff92b8072613d1cd100832e/raw/badge.svg)](https://github.com/ArduPilot/MethodicConfigurator/actions/workflows/pytest.yml) | [![Known Vulnerabilities](https://snyk.io/test/github/amilcarlucas/MethodicConfigurator/badge.svg)](https://app.snyk.io/org/amilcarlucas/project/c8fd6e29-715b-4949-b828-64eff84f5fe1) | [![pages-build-deployment](https://github.com/ArduPilot/MethodicConfigurator/actions/workflows/pages/pages-build-deployment/badge.svg)](https://github.com/ArduPilot/MethodicConfigurator/actions/workflows/pages/pages-build-deployment) | [![Average time to resolve an issue](http://isitmaintained.com/badge/resolution/ArduPilot/MethodicConfigurator.svg)](http://isitmaintained.com/project/ArduPilot/MethodicConfigurator) |
| [![test Python cleanliness](https://github.com/ArduPilot/MethodicConfigurator/actions/workflows/ruff.yml/badge.svg)](https://github.com/ArduPilot/MethodicConfigurator/actions/workflows/ruff.yml) | [![OpenSSF Best Practices](https://www.bestpractices.dev/projects/9101/badge)](https://www.bestpractices.dev/projects/9101) | [![Pytest tests](https://github.com/ArduPilot/MethodicConfigurator/actions/workflows/pytest.yml/badge.svg)](https://github.com/ArduPilot/MethodicConfigurator/actions/workflows/pytest.yml) | [![CodeQL](https://github.com/ArduPilot/MethodicConfigurator/actions/workflows/codeql.yml/badge.svg)](https://github.com/ArduPilot/MethodicConfigurator/actions/workflows/codeql.yml) | [![Upload MethodicConfigurator Package](https://github.com/ArduPilot/MethodicConfigurator/actions/workflows/python-publish.yml/badge.svg)](https://github.com/ArduPilot/MethodicConfigurator/actions/workflows/python-publish.yml) | [![Percentage of issues still open](http://isitmaintained.com/badge/open/ArduPilot/MethodicConfigurator.svg)](http://isitmaintained.com/project/ArduPilot/MethodicConfigurator) |
| [![mypy](https://github.com/ArduPilot/MethodicConfigurator/actions/workflows/mypy.yml/badge.svg)](https://github.com/ArduPilot/MethodicConfigurator/actions/workflows/mypy.yml) | [![REUSE status](https://api.reuse.software/badge/github.com/ArduPilot/MethodicConfigurator)](https://api.reuse.software/info/github.com/ArduPilot/MethodicConfigurator) | [![Coverage Status](https://coveralls.io/repos/github/ArduPilot/MethodicConfigurator/badge.svg?branch=master)](https://coveralls.io/github/ArduPilot/MethodicConfigurator?branch=master) | [![gitavscan](https://github.com/ArduPilot/MethodicConfigurator/actions/workflows/gitavscan.yml/badge.svg)](https://github.com/ArduPilot/MethodicConfigurator/actions/workflows/gitavscan.yml) | [![pypi](https://img.shields.io/pypi/v/ardupilot-methodic-configurator.svg)](https://pypi.org/project/ardupilot-methodic-configurator/) | [![python versions](https://img.shields.io/pypi/pyversions/ardupilot-methodic-configurator.svg)](https://pypi.python.org/pypi/ardupilot-methodic-configurator) |
| [![Pyright](https://github.com/ArduPilot/MethodicConfigurator/actions/workflows/pyright.yml/badge.svg)](https://github.com/ArduPilot/MethodicConfigurator/actions/workflows/pyright.yml) | [![md-link-check](https://github.com/ArduPilot/MethodicConfigurator/actions/workflows/markdown-link-check.yml/badge.svg)](https://github.com/ArduPilot/MethodicConfigurator/actions/workflows/markdown-link-check.yml) | [![Coverity Scan Build Status](https://scan.coverity.com/projects/30346/badge.svg)](https://scan.coverity.com/projects/ardupilot-methodic-configurator) | [![OpenSSF Scorecard](https://api.scorecard.dev/projects/github.com/ArduPilot/MethodicConfigurator/badge)](https://scorecard.dev/viewer/?uri=github.com/ArduPilot/MethodicConfigurator) | [![PyPI - Downloads](https://img.shields.io/pypi/dm/ardupilot-methodic-configurator?link=https%3A%2F%2Fpypi.org%2Fproject%2Fardupilot-methodic-configurator%2F)](https://pypistats.org/packages/ardupilot-methodic-configurator) | [![Code Climate](https://codeclimate.com/github/amilcarlucas/MethodicConfigurator.png)](https://codeclimate.com/github/amilcarlucas/MethodicConfigurator) |
| [![markdown-lint](https://github.com/ArduPilot/MethodicConfigurator/actions/workflows/markdown-lint.yml/badge.svg)](https://github.com/ArduPilot/MethodicConfigurator/actions/workflows/markdown-lint.yml) | [![pre-commit](https://results.pre-commit.ci/badge/github/ArduPilot/MethodicConfigurator/master.svg)](https://results.pre-commit.ci/latest/github/ArduPilot/MethodicConfigurator/master) | [![Discord](https://img.shields.io/badge/Discord-%235865F2.svg?logo=discord&logoColor=white)](https://discord.com/channels/674039678562861068/1308233496535371856) | | [![Windows Build](https://github.com/ArduPilot/MethodicConfigurator/actions/workflows/build_windows_macos.yml/badge.svg)](https://github.com/ArduPilot/MethodicConfigurator/actions/workflows/windows_build.yml) | [![Update Flight Controller IDs](https://github.com/ArduPilot/MethodicConfigurator/actions/workflows/update_flightcontroller_ids.yml/badge.svg)](https://github.com/ArduPilot/MethodicConfigurator/actions/workflows/update_flightcontroller_ids.yml) |

*ArduPilot Methodic Configurator* is a software, developed by ArduPilot developers, that semi-automates a
[clear, proven and safe configuration sequence for ArduCopter](https://ardupilot.github.io/MethodicConfigurator/TUNING_GUIDE_ArduCopter) drones.
We are working on extending it to [ArduPlane](https://ardupilot.github.io/MethodicConfigurator/TUNING_GUIDE_ArduPlane),
[Heli](https://ardupilot.github.io/MethodicConfigurator/TUNING_GUIDE_Heli) and
[Rover](https://ardupilot.github.io/MethodicConfigurator/TUNING_GUIDE_Rover) vehicles.
But for those it is still very incomplete.

- **clear**: the semi-automated sequence is linear, executed one step at the time with no hidden complex dependencies
- **proven**: the software has been used by hundreds of ArduPilot developers and users. From beginners to advanced. On big and small vehicles.
- **safe**: the sequence reduces trial-and-error by following established best practices and reduces the amount of flights required to configure the vehicle
- **Parameter management**: Upload, download, and edit parameters with full documentation
- **Vehicle templates**: Start from empty templates or from pre-configured settings for common vehicle types
- **Traceability**: Documents every parameter change with reasons

Here are some YouTube video tutorials from the [AMC YouTube Channel](https://www.youtube.com/@AmilcardoCarmoLucas):

[![YouTube tutorial - intro](https://github.com/ArduPilot/MethodicConfigurator/blob/master/images/Video1_Thumbnail_yt.png?raw=true)](https://www.youtube.com/watch?v=47RjQ_GarvE&list=PL1oa0qoJ9W_89eMcn4x2PB6o3fyPbheA9)
[![YouTube tutorial - usecase](https://github.com/ArduPilot/MethodicConfigurator/blob/master/images/Video2_Thumbnail_yt.png?raw=true)](https://www.youtube.com/watch?v=9n4Wh6wBuHQ&list=PL1oa0qoJ9W_89eMcn4x2PB6o3fyPbheA9)

[![YouTube tutorial - beginners](https://github.com/ArduPilot/MethodicConfigurator/blob/master/images/Video3_Thumbnail_yt.png?raw=true)](https://www.youtube.com/watch?v=tM8EznlNhgs&list=PL1oa0qoJ9W_89eMcn4x2PB6o3fyPbheA9)

[![YouTube tutorial - .bin analysis](https://github.com/ArduPilot/MethodicConfigurator/blob/master/images/Video4_Thumbnail_yt.png?raw=true)](https://www.youtube.com/watch?v=EBdczjYX7_s&list=PL1oa0qoJ9W_89eMcn4x2PB6o3fyPbheA9)

And here is a presentation explaining it:

[![ArduPilot methodic configurator power point presentation](https://github.com/ArduPilot/MethodicConfigurator/blob/master/images/ArduPilot_Methodic_Configurator_presentation.png?raw=true)](https://github.com/ArduPilot/MethodicConfigurator/blob/master/images/ArduPilot_Methodic_Configurator.pdf?raw=true)

Comparison with Ground Control Station (GCS) software, traditionally used to configure ArduPilot before AMC existed:

| Feature | Mission Planner, QGroundControl, ... etc | ArduPilot Methodic Configurator |
| ------- | ---------------------------------------- | ------------------------------- |
| full automatic configuration | No | No |
| configuration type | manual [^1] | semi-automated [^2] |
| explains what to do | No | Yes |
| explains when to do something | No | Yes, explains the path |
| explains why do something | No | Yes |
| configuration method | a different menu for each task, some tasks have no menu, so you need to dig into the 1200 parameters | each task only presents you a relevant subset of parameters |
| parameter documentation | Yes, only on the full-parameter tree view | Yes |
| displays relevant documentation | No | Yes |
| makes sure you do not forget a step | No | Yes |
| checks that parameters get correctly uploaded | No (MP), unsure (QGCS), yes (MAVProxy) | Yes |
| reuse params in other vehicles | No, unless you hand edit files | Yes, out-of-the-box |
| documents why you changed each parameter | No | Yes |
| tutorials and learning resources | No, scattered and not integrated | Yes, context-aware help integrated |
| auto. install lua scripts on the FC | No | Yes |
| auto. backup of parameters before changing them | No | Yes |

[^1]: you need to know what/when/why you are doing
[^2]: it explains what you should do, when you should do it and why

<!-- ![When to use ArduPilot Methodic Configurator](https://github.com/ArduPilot/MethodicConfigurator/blob/master/images/when_to_use_amc.png?raw=true) -->

It's simple graphical user interface (GUI) manages and visualizes ArduPilot parameters, parameter files and documentation.

![Application Screenshot](https://github.com/ArduPilot/MethodicConfigurator/blob/master/images/App_screenshot1.png?raw=true)

No visible menus, no hidden menus, no complicated options, what you see is what gets changed.

## Star History

[![Star History Chart](https://api.star-history.com/chart?repos=ArduPilot/MethodicConfigurator&type=date&legend=top-left&sealed_token=mVQBTb1Yx9PvsoRodF1P5omVr_oxCrUmB_QdIk7zbRIBq_2WLMfzVxBjkbyzgb6_MVjHRVYda-7RMWDHpc7vfaaWRXkPBYG1Lvh1zyZWQfRLTlK9ccCWCw)](https://www.star-history.com/?repos=ArduPilot%2FMethodicConfigurator&type=date&legend=top-left)

## Table of Contents

- [Quick Start](#quick-start)
  - [What You'll Accomplish](#what-youll-accomplish)
  - [Important Tips for Success](#important-tips-for-success)
- [1. Quick overview of the entire process](#1-quick-overview-of-the-entire-process)
  - [1.1 Select the vehicle components](#11-select-the-vehicle-components)
  - [1.2 Download and install software](#12-download-and-install-software)
  - [1.3 Input vehicle components and component connections into ArduPilot Methodic Configurator](#13-input-vehicle-components-and-component-connections-into-ardupilot-methodic-configurator)
  - [1.4 Perform IMU temperature calibration before assembling the autopilot into the vehicle (optional)](#14-perform-imu-temperature-calibration-before-assembling-the-autopilot-into-the-vehicle-optional)
  - [1.5 Assemble all components except the propellers](#15-assemble-all-components-except-the-propellers)
  - [1.6 Basic mandatory configuration](#16-basic-mandatory-configuration)
  - [1.7 Assemble propellers and perform the first flight](#17-assemble-propellers-and-perform-the-first-flight)
  - [1.8 Minimalistic mandatory tuning](#18-minimalistic-mandatory-tuning)
  - [1.9 Standard tuning (optional)](#19-standard-tuning-optional)
  - [1.10 Improve altitude under windy conditions (optional)](#110-improve-altitude-under-windy-conditions-optional)
  - [1.11 System identification for analytical PID optimization (optional)](#111-system-identification-for-analytical-pid-optimization-optional)
  - [1.12 Position controller tuning (optional)](#112-position-controller-tuning-optional)
  - [1.13 Everyday use](#113-everyday-use)
- [Documentation and Support](#documentation-and-support)
- [Contributing](#contributing)
- [Internationalization](#internationalization)
- [Code of Conduct](#code-of-conduct)
- [License](#license)
- [Credits](#credits)

## Quick Start

### What You'll Accomplish

By the end of this process, your flight controller will be fully configured with:

- ✅ All parameters optimized for your specific vehicle
- ✅ Complete documentation of every change made
- ✅ Backup files for easy restoration
- ✅ Ready-to-fly configuration

### Important Tips for Success

💡 **Pro Tips:**

- **Take your time**: Read parameter descriptions - they contain valuable insights
- **Test incrementally**: The step-by-step approach allows testing between changes
- **Keep backups**: The software creates them automatically in the vehicle project directory
- **Document changes**: Always fill in the "Change Reason" field - future you will thank you

⚠️ **Common Mistakes to Avoid:**

- **Rushing through steps**: Each parameter has a purpose - understand before changing
- **Skipping component validation**: Incorrect component settings can cause crashes
- **Ignoring warnings**: Red backgrounds and error messages are there for your safety
- **Forgetting calibrations**: Some parameters require physical calibration procedures:
  - IMU temperature, analog voltage and current measurement, gyro, accelerometers

## 1. Quick overview of the entire process

To methodically build, configure and tune ArduPilot vehicles follow this sequence of steps:

### 1.1 Select the vehicle components

- while [choosing an Autopilot](https://ardupilot.org/copter/docs/common-autopilots.html) and
  [other hardware](https://ardupilot.org/copter/docs/common-optional-hardware.html) components
  [avoid these components](https://discuss.ardupilot.org/t/hardware-to-avoid-when-building-your-first-multirotor/114014/1)
- Use [ecalc for multirotor](https://www.ecalc.ch/index.htm) to select the propulsion system.
- follow [hardware best practices](https://ardupilot.github.io/MethodicConfigurator/TUNING_GUIDE_ArduCopter#11-multicopter-hardware-best-practices)

### 1.2 Download and install software

- Install ArduPilot Methodic Configurator on [MS windows](https://ardupilot.github.io/MethodicConfigurator/INSTALL.html#ms-windows-installation),
  [Linux](https://ardupilot.github.io/MethodicConfigurator/INSTALL.html#linux-installation) or
  [macOS](https://ardupilot.github.io/MethodicConfigurator/INSTALL.html#macos-installation)
- [Install the latest Mission Planner version](https://ardupilot.github.io/MethodicConfigurator/INSTALL.html#install-mission-planner-software-on-a-pc-or-mac)
- [Install the latest ArduPilot firmware on your flight controller board](https://ardupilot.github.io/MethodicConfigurator/INSTALL.html#install-ardupilot-firmware-on-the-flight-controller)

### 1.3 Input vehicle components and component connections into ArduPilot Methodic Configurator

The software needs this information to automatically preselect configuration settings relevant to your specific vehicle

- [Start the ArduPilot Methodic Configurator and select a vehicle that resembles yours](https://ardupilot.github.io/MethodicConfigurator/USECASES.html#use-the-ardupilot-methodic-configurator-software-for-the-first-time)
  and input vehicle components and component connections information into the ArduPilot Methodic Configurator *component editor window*

### 1.4 Perform IMU temperature calibration before assembling the autopilot into the vehicle (optional)

IMU temperature calibration reduces the probability of *Accel inconsistent* and *Gyro inconsistent* errors and reduces the time required to arm the vehicle.
IMU temperature calibration requires lowering the temperature of the autopilot (flight controller) to circa -20°C.
That is harder to do once the autopilot is assembled inside the vehicle, hence it is done now.

- [start the software](https://ardupilot.github.io/MethodicConfigurator/USECASES.html#use-the-ardupilot-methodic-configurator-software-for-the-first-time)
- Perform [IMU temperature calibration](https://ardupilot.github.io/MethodicConfigurator/TUNING_GUIDE_ArduCopter#41-setup-imu-temperature-calibration)

Follow [starting the software after having created a new vehicle](https://ardupilot.github.io/MethodicConfigurator/USECASES.html#use-the-ardupilot-methodic-configurator-software-after-having-created-a-vehicle-from-a-template)
instructions once the calibration procedure is finished.

### 1.5 Assemble all components except the propellers

Assemble and connect all components. Make sure you [follow best practices](https://ardupilot.github.io/MethodicConfigurator/TUNING_GUIDE_ArduCopter#11-multicopter-hardware-best-practices)

### 1.6 Basic mandatory configuration

Using the [ArduPilot Methodic Configurator GUI](https://ardupilot.github.io/MethodicConfigurator/USECASES.html#use-the-ardupilot-methodic-configurator-software-after-having-created-a-vehicle-from-a-template),
complete these steps in order:

- [05_remote_controller_receiver.param](https://ardupilot.github.io/MethodicConfigurator/TUNING_GUIDE_ArduCopter#621-configure-the-rc-receiver)
  receiver connections and protocol
- [06_remote_controller_controller.param](https://ardupilot.github.io/MethodicConfigurator/TUNING_GUIDE_ArduCopter#622-configure-the-rc-controller)
  handheld controller calibration
- [07_telemetry.param](https://ardupilot.github.io/MethodicConfigurator/TUNING_GUIDE_ArduCopter#63-configure-telemetry) telemetry connections and protocol (optional)
- [08_esc_telemetry.param](https://ardupilot.github.io/MethodicConfigurator/TUNING_GUIDE_ArduCopter#64-configure-esc-telemetry-and-communication)
  ESC telemetry and communication
- [09_battery_monitor.param](https://ardupilot.github.io/MethodicConfigurator/TUNING_GUIDE_ArduCopter#65-configure-the-primary-battery-monitor)
  battery monitor configuration
- [10_battery.param](https://ardupilot.github.io/MethodicConfigurator/TUNING_GUIDE_ArduCopter#66-configure-the-batteries) battery health and state of charge
- [11_servo_outputs.param](https://ardupilot.github.io/MethodicConfigurator/TUNING_GUIDE_ArduCopter#67-configure-servo-outputs) servo output functions
- [12_motor.param](https://ardupilot.github.io/MethodicConfigurator/TUNING_GUIDE_ArduCopter#68-configure-motor-electrical-pole-count-when-using-rpm-telemetry)
  motor electrical pole count (optional)
- [13_initial_atc.param](https://ardupilot.github.io/MethodicConfigurator/TUNING_GUIDE_ArduCopter#69-initial-attitude-pid-gains-vehicle-size-dependent)
  initial attitude PID gains
- [14_esc.param](https://ardupilot.github.io/MethodicConfigurator/TUNING_GUIDE_ArduCopter#610-configure-esc-outputs-motor-thrust-and-motor-tests)
  ESC outputs, thrust scaling and motor tests
- [15_board_orientation.param](https://ardupilot.github.io/MethodicConfigurator/TUNING_GUIDE_ArduCopter#611-configure-flight-controller-orientation)
  flight controller orientation
- [16_accelerometer_calibration.param](https://ardupilot.github.io/MethodicConfigurator/TUNING_GUIDE_ArduCopter#612-accelerometer-calibration-16_accelerometer_calibrationparam)
  accelerometer calibration
- [17_accelerometer_level.param](https://ardupilot.github.io/MethodicConfigurator/TUNING_GUIDE_ArduCopter#613-accelerometer-level-17_accelerometer_levelparam)
  level calibration
- [18_gnss.param](https://ardupilot.github.io/MethodicConfigurator/TUNING_GUIDE_ArduCopter#614-configure-the-gnss-receivers) GNSS receiver connections and protocol
- [19_compass_calibration.param](https://ardupilot.github.io/MethodicConfigurator/TUNING_GUIDE_ArduCopter#615-compass-calibration-19_compass_calibrationparam)
  compass calibration
- [20_remote_id.param](https://ardupilot.github.io/MethodicConfigurator/TUNING_GUIDE_ArduCopter#616-remote-id-aka-drone-id-optional) Remote ID (optional)
- [21_osd.param](https://ardupilot.github.io/MethodicConfigurator/TUNING_GUIDE_ArduCopter#617-on-screen-display-optional) On-Screen-Display (optional)
- [22_flight_modes.param](https://ardupilot.github.io/MethodicConfigurator/TUNING_GUIDE_ArduCopter#618-flight-modes-22_flight_modesparam) flight modes
- [23_general_configuration.param](https://ardupilot.github.io/MethodicConfigurator/TUNING_GUIDE_ArduCopter#619-general-configuration) general configuration
- [24_safety_setup.param](https://ardupilot.github.io/MethodicConfigurator/TUNING_GUIDE_ArduCopter#620-safety-setup) safety measures
- [25_motor_notch_filter_setup.param](https://ardupilot.github.io/MethodicConfigurator/TUNING_GUIDE_ArduCopter#622-notch-filters-setup) motor notch filter setup
- [26_motor_notch_logging.param](https://ardupilot.github.io/MethodicConfigurator/TUNING_GUIDE_ArduCopter#623-configure-logging) Dataflash/SDCard logging
- [27_optional_pid_adjustment.param](https://ardupilot.github.io/MethodicConfigurator/TUNING_GUIDE_ArduCopter#624-optional-pid-adjustment) optional PID adjustment

Before the first flight, [check the ArduPilot Hardware Report](https://ardupilot.github.io/MethodicConfigurator/TUNING_GUIDE_ArduCopter#621-check-the-ardupilot-hardware-report).

### 1.7 Assemble propellers and perform the first flight

Now that all mandatory configuration steps are done you can [perform the first flight](https://ardupilot.github.io/MethodicConfigurator/TUNING_GUIDE_ArduCopter#7-assemble-propellers-and-perform-the-first-flight)

### 1.8 Minimalistic mandatory tuning

These are the very [minimum tuning steps](https://ardupilot.github.io/MethodicConfigurator/TUNING_GUIDE_ArduCopter#8-minimalistic-mandatory-tuning)
required for a stable flight:

- Load the `.bin` log file from the first flight into [Notch filter webtool](https://firmware.ardupilot.org/Tools/WebTools/FilterReview/)
- [28_throttle_controller.param](https://ardupilot.github.io/MethodicConfigurator/TUNING_GUIDE_ArduCopter#81-configure-the-throttle-controller) the altitude controller
  depends on the power-to-thrust ratio found in the first flight
- [29_motor_notch_filter_results.param](https://ardupilot.github.io/MethodicConfigurator/TUNING_GUIDE_ArduCopter#82-notch-filter-calibration)
  use the webtool information to configure the notch filter(s)
- [30_ekf_config.param](https://ardupilot.github.io/MethodicConfigurator/TUNING_GUIDE_ArduCopter#83-configure-the-ekf-altitude-source-weights) sometimes
  the EKF3 needs a tune to maintain altitude
- [31_pid_notch_filter_logging.param](https://ardupilot.github.io/MethodicConfigurator/TUNING_GUIDE_ArduCopter#841-pid-notch-logging)
  PID notch filter logging configuration
- [32_pid_notch_filter_results.param](https://ardupilot.github.io/MethodicConfigurator/TUNING_GUIDE_ArduCopter#842-pid-notch-tuning)
  PID notch filter configuration
- [33_quick_tune_setup.param](https://ardupilot.github.io/MethodicConfigurator/TUNING_GUIDE_ArduCopter#851-set-up-quicktune) and
  [34_quick_tune_results.param](https://ardupilot.github.io/MethodicConfigurator/TUNING_GUIDE_ArduCopter#852-store-quicktune-results),
  you need lua scripting support to do this if not available you can tune manually.

That is it, if you are impatient and do not want an optimized vehicle you can skip to [everyday use](#113-everyday-use).

### 1.9 Standard tuning (optional)

These are the [standard tuning steps](https://ardupilot.github.io/MethodicConfigurator/TUNING_GUIDE_ArduCopter#9-standard-tuning-optional) required for an optimized flight:

- [35_inflight_magnetometer_fit_setup.param](https://ardupilot.github.io/MethodicConfigurator/TUNING_GUIDE_ArduCopter#911-setup-inflight-magfit-calibration), use lua scripted
  flight path or fly manually, store the results using
  [36_inflight_magnetometer_fit_results.param](https://ardupilot.github.io/MethodicConfigurator/TUNING_GUIDE_ArduCopter#912-calculate-inflight-magfit-calibration), use the
  [magfit webtool](https://firmware.ardupilot.org/Tools/WebTools/MAGFit/) to calculate a file that the ardupilot methodic configurator can use
- [37_evaluate_the_aircraft_tune_ff_disable.param](https://ardupilot.github.io/MethodicConfigurator/TUNING_GUIDE_ArduCopter#92-evaluate-the-aircraft-tune-with-input-shaping-disabled)
  and
  [38_evaluate_the_aircraft_tune_ff_enable.param](https://ardupilot.github.io/MethodicConfigurator/TUNING_GUIDE_ArduCopter#93-evaluate-the-aircraft-tune-with-input-shaping-enabled)
- [39_autotune_roll_setup.param](https://ardupilot.github.io/MethodicConfigurator/TUNING_GUIDE_ArduCopter#941-roll-axis-autotune) and
  [40_autotune_roll_results.param](https://ardupilot.github.io/MethodicConfigurator/TUNING_GUIDE_ArduCopter#941-roll-axis-autotune) tune roll axis rate and angle PIDs
- [41_autotune_pitch_setup.param](https://ardupilot.github.io/MethodicConfigurator/TUNING_GUIDE_ArduCopter#942-pitch-axis-autotune) and
  [42_autotune_pitch_results.param](https://ardupilot.github.io/MethodicConfigurator/TUNING_GUIDE_ArduCopter#942-pitch-axis-autotune) tune pitch axis rate and angle PIDs
- [43_autotune_yaw_setup.param](https://ardupilot.github.io/MethodicConfigurator/TUNING_GUIDE_ArduCopter#943-yaw-axis-autotune) and
  [44_autotune_yaw_results.param](https://ardupilot.github.io/MethodicConfigurator/TUNING_GUIDE_ArduCopter#943-yaw-axis-autotune) tune yaw axis rate and angle PIDs
- [45_autotune_yawd_setup.param](https://ardupilot.github.io/MethodicConfigurator/TUNING_GUIDE_ArduCopter#944-yaw-d-axis-autotune-optional) and
  [46_autotune_yawd_results.param](https://ardupilot.github.io/MethodicConfigurator/TUNING_GUIDE_ArduCopter#944-yaw-d-axis-autotune-optional) tune yawd axis rate and
  angle PIDs
- [47_autotune_roll_pitch_retune_setup.param](https://ardupilot.github.io/MethodicConfigurator/TUNING_GUIDE_ArduCopter#945-roll-and-pitch-axis-re-autotune) and
  [48_autotune_roll_pitch_retune_results.param](https://ardupilot.github.io/MethodicConfigurator/TUNING_GUIDE_ArduCopter#945-roll-and-pitch-axis-re-autotune) re-tune roll
  and pitch pitch axis rate and angle PIDs
- [49_autotune_finish.param](https://ardupilot.github.io/MethodicConfigurator/TUNING_GUIDE_ArduCopter#96-finish-autotune)
  performance evaluation flight after autotune
- [50_pid_d_ff.param](https://ardupilot.github.io/MethodicConfigurator/TUNING_GUIDE_ArduCopter#97-angle-rate-derivative-feed-forward-calculation)
  angle rate derivative feed-forward calculation

Now the standard tuning is complete you can skip to [everyday use](#113-everyday-use)

### 1.10 Improve altitude under windy conditions (optional)

- [51_windspeed_estimation.param](https://ardupilot.github.io/MethodicConfigurator/TUNING_GUIDE_ArduCopter#101-windspeed-estimation-flights)
  estimates the wind speed
- [52_barometer_compensation.param](https://ardupilot.github.io/MethodicConfigurator/TUNING_GUIDE_ArduCopter#102-baro-compensation-flights)
  Uses the estimated wind speed to improve altitude stability
- [53_windspeed_estimation_finish.param](https://ardupilot.github.io/MethodicConfigurator/TUNING_GUIDE_ArduCopter#103-finish-wind-estimation)
  finish wind estimation and restore logging settings

### 1.11 System identification for analytical PID optimization (optional)

- [54_system_id_input_roll.param](https://ardupilot.github.io/MethodicConfigurator/TUNING_GUIDE_ArduCopter#1111-roll-input-system-identification),
  [55_system_id_input_pitch.param](https://ardupilot.github.io/MethodicConfigurator/TUNING_GUIDE_ArduCopter#1112-pitch-input-system-identification),
  [56_system_id_input_yaw.param](https://ardupilot.github.io/MethodicConfigurator/TUNING_GUIDE_ArduCopter#1113-yaw-input-system-identification)
  system identification input flights
- [57_system_id_mixer_roll.param](https://ardupilot.github.io/MethodicConfigurator/TUNING_GUIDE_ArduCopter#1114-roll-rate-mathematical-model),
  [58_system_id_mixer_pitch.param](https://ardupilot.github.io/MethodicConfigurator/TUNING_GUIDE_ArduCopter#1115-pitch-rate-mathematical-model),
  [59_system_id_mixer_yaw.param](https://ardupilot.github.io/MethodicConfigurator/TUNING_GUIDE_ArduCopter#1116-yaw-rate-mathematical-model)
  system identification mixer flights
- [60_system_id_mixer_thrust.param](https://ardupilot.github.io/MethodicConfigurator/TUNING_GUIDE_ArduCopter#1117-thrust-mathematical-model)
  thrust mathematical model identification
- [61_analytical_pid_optimization.param](https://ardupilot.github.io/MethodicConfigurator/TUNING_GUIDE_ArduCopter#112-analytical-multicopter-flight-controller-pid-optimization)

### 1.12 Position controller tuning (optional)

- [64_position_controller.param](https://ardupilot.github.io/MethodicConfigurator/TUNING_GUIDE_ArduCopter#121-position-controller)
  position controller tuning
- [65_guided_operation.param](https://ardupilot.github.io/MethodicConfigurator/TUNING_GUIDE_ArduCopter#122-guided-operation-without-rc-transmitter)
  guided operation without RC transmitter
- [66_precision_land.param](https://ardupilot.github.io/MethodicConfigurator/TUNING_GUIDE_ArduCopter#123-precision-land)
  precision landing configuration
- [67_optical_flow_setup.param](https://ardupilot.github.io/MethodicConfigurator/TUNING_GUIDE_ArduCopter#1241-set-up-optical-flow-calibration),
  [68_optical_flow_results.param](https://ardupilot.github.io/MethodicConfigurator/TUNING_GUIDE_ArduCopter#1242-store-optical-flow-calibration-results),
  [69_use_optical_flow_instead_of_gnss.param](https://ardupilot.github.io/MethodicConfigurator/TUNING_GUIDE_ArduCopter#1243-use-optical-flow-instead-of-gnss)
  optical flow calibration and configuration (optional)

### 1.13 Everyday use

Now that tuning and configuration are done, some logging and tests can be disabled and some more safety features enabled:

- [70_everyday_use.param](https://ardupilot.github.io/MethodicConfigurator/TUNING_GUIDE_ArduCopter#13-productive-configuration)

Congratulations your flight controller is now fully configured in the safest and fastest way publicly known.

Enjoy your properly configured vehicle.

## Documentation and Support

Need [help or support](https://ardupilot.github.io/MethodicConfigurator/SUPPORT.html)

There is also [documentation on other use cases](https://ardupilot.github.io/MethodicConfigurator/USECASES.html)
and a detailed but generic [Usermanual](https://ardupilot.github.io/MethodicConfigurator/USERMANUAL.html).

**Additional Documentation:**

- [Recover a stuck AM32 ESC](https://ardupilot.github.io/MethodicConfigurator/AM32_esc_bootloader_guide.html)
  - recovery steps for AM32 ESCs that are stuck or no longer detected
- [Frequently Asked Questions (FAQ)](https://ardupilot.github.io/MethodicConfigurator/FAQ.html)
- [Customizing Configuration Steps](https://ardupilot.github.io/MethodicConfigurator/CUSTOMIZING_CONFIGURATION_STEPS.html) - for advanced users and integrators
- [Project Governance](https://ardupilot.github.io/MethodicConfigurator/GOVERNANCE.html) - how decisions are made
- [Security Policy](https://ardupilot.github.io/MethodicConfigurator/SECURITY.html) - reporting vulnerabilities
- [Compliance](https://ardupilot.github.io/MethodicConfigurator/COMPLIANCE.html) - standards and regulations
- [Roadmap](https://ardupilot.github.io/MethodicConfigurator/ROADMAP.html) - planned features and improvements

## Contributing

Want [to help us and contribute](https://github.com/ArduPilot/MethodicConfigurator/blob/master/CONTRIBUTING.md)?

## Internationalization

The software is available in [multiple languages](https://github.com/ArduPilot/MethodicConfigurator/tree/master/ardupilot_methodic_configurator/locale).
On MS Windows the language is selected during install and that selection is stored in the desktop icon.
You can manually create multiple desktop icons, each will run the software in a different language.
On Linux and macOS the language is selectable by the `--language` command line argument.

See [contributing page](https://github.com/ArduPilot/MethodicConfigurator/blob/master/CONTRIBUTING.md) if you want to help us translate the software into your language.

## Code of Conduct

To use and develop this software you must obey the [ArduPilot Methodic Configurator Code of Conduct](https://github.com/ArduPilot/MethodicConfigurator/blob/master/CODE_OF_CONDUCT.md).

## License

This software is cost free.
This project is licensed under the [GNU General Public License v3.0](https://github.com/ArduPilot/MethodicConfigurator/blob/master/LICENSE.md).

## Credits

It builds upon other [open-source software packages](https://ardupilot.github.io/MethodicConfigurator/credits/CREDITS.html)

<!-- Gurubase Widget -->
<script async src="https://widget.gurubase.io/widget.latest.min.js"
    data-widget-id="uE4kxEE4LY3ZSyfNsF5bU6gIOnWGTBOL_e16KwDH-0g"
    data-text="Ask AI"
    data-margins='{"bottom": "1rem", "right": "1rem"}'
    data-light-mode="true"
    id="guru-widget-id">
</script>
