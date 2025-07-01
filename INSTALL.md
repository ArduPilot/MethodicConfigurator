# Install instructions

This software is available for multiple operating systems:

- [Microsoft Windows](#ms-windows-installation)
- [Linux](#linux-installation)
- [macOS](#macos-installation)

After installing it you must also:

- [Install the latest Mission Planner version](#install-mission-planner-software-on-a-pc-or-mac)
- [Install the latest ArduPilot firmware on your flight controller board](#install-ardupilot-firmware-on-the-flight-controller)

## MS Windows Installation

Download the latest [ardupilot_methodic_configurator_setup_x.x.x.exe](https://github.com/ArduPilot/MethodicConfigurator/releases/latest) installer file and execute it.

Ignore the `ardupilot_methodic_configurator_setup_x.x.x.exe.bundle` and `ardupilot_methodic_configurator_setup_x.x.x.exe.sig` files
those are just cryptographic signatures for cyber security applications.

Do the steps highlighted in red.

![AMC install 01](images/AMC_install_01.png)

It is available in multiple languages, select the one that better suits you.

![AMC install 01b](images/AMC_install_01b.png)

Accept the software license.

![AMC install 02](images/AMC_install_02.png)

Create a desktop icon, so that the language setting will take effect.
Most users do not use the command line and do not need to add the application to their path.

![AMC install 03](images/AMC_install_03.png)

Click `Install`.

![AMC install 04](images/AMC_install_04.png)

Click `Finish`.

![AMC install 05](images/AMC_install_05.png)

To run it, double-click on the newly created desktop item.

## Linux Installation

### Older Linux distributions without venv

Install [python pip](https://pypi.org/project/pip/). Then execute the command line:

```bash
pip install -U ardupilot_methodic_configurator
```

To run it, execute the command line:

```bash
ardupilot_methodic_configurator
```

### Newer Linux distributions with venv

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

## macOS Installation

Follow the Linux installation instructions above.

You might need to also do:

```bash
brew install uv python-tk@3.9
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

<!-- Gurubase Widget -->
<script async src="https://widget.gurubase.io/widget.latest.min.js"
    data-widget-id="uE4kxEE4LY3ZSyfNsF5bU6gIOnWGTBOL_e16KwDH-0g"
    data-text="Ask AI"
    data-margins='{"bottom": "1rem", "right": "1rem"}'
    data-light-mode="true"
    id="guru-widget-id">
</script>
