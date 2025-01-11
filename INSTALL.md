# Install instructions
<!--
SPDX-FileCopyrightText: 2024-2025 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
-->

This software is available for multiple operating systems:

- [Microsoft Windows](#ms-windows-installation)
- [Linux](#linux-installation)
- [MacOS](#macos-installation)

After installing it you must also:

- [Install the latest Mission Planner version](#install-mission-planner-software-on-a-pc-or-mac)
- [Install the latest ArduPilot firmware on your flight controller board](#install-ardupilot-firmware-on-the-flight-controller)

## MS Windows Installation

Download the [latest MethodicConfiguratorSetup-x.x.x.exe installer file](https://github.com/ArduPilot/MethodicConfigurator/releases/tag/latest).

Do the steps highlighted in red.

![AMC install 01](images/AMC_install_01.png)

![AMC install 02](images/AMC_install_02.png)

![AMC install 03](images/AMC_install_03.png)

![AMC install 04](images/AMC_install_04.png)

![AMC install 05](images/AMC_install_05.png)

To run it, double-click on the newly created desktop item.

## Linux Installation

### Older linux distributions without venv

Install [python pip](https://pypi.org/project/pip/). Then execute the command line:

```bash
pip install -U ardupilot_methodic_configurator
```

To run it, execute the command line:

```bash
ardupilot_methodic_configurator
```

### Newer linux distributions with venv

You need to create and activate a new virtual environment before you can run the software.

```bash
python -m venv .ardupilot_methodic_configurator_venv
source .ardupilot_methodic_configurator_venv/bin/activate
python -m pip install --upgrade pip
pip install ardupilot_methodic_configurator
```

To run it, execute the command line:

```bash
source .ardupilot_methodic_configurator_venv/bin/activate
ardupilot_methodic_configurator
```

## MacOS Installation

Install [git](https://git-scm.com/) and [python](https://www.python.org/downloads/). Then execute the command lines:

```bash
git clone https://github.com/ArduPilot/MethodicConfigurator.git
cd MethodicConfigurator
./install_macos.sh
```

## Install *Mission Planner* software on a PC or Mac

1. Download and install [Mission Planner](https://firmware.ardupilot.org/Tools/MissionPlanner/).
1. Make sure to install all the recommended device drivers when asked to.

## Install *ArduPilot* firmware on the flight controller

1. Connect the flight controller to the computer using a USB cable.
1. Open *Mission Planner* software.
1. Go to *SETUP* > *Install Firmware* select your vehicle type and install version 4.3.8 **or newer** of the ArduPilot firmware onto the flight controller.
![Install ArduPilot firmware](images/MissionPlanne_install_firmware.png)
1. Wait until the firmware download is complete.
1. Disconnect the USB cable from the flight controller.
