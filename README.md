# ArduPilot methodic configurator

![GitHub Actions](https://github.com/ardupilot/MethodicConfigurator/actions/workflows/windows_build.yml/badge.svg) ![GitHub Actions](https://github.com/ardupilot/MethodicConfigurator/actions/workflows/python-cleanliness.yml/badge.svg)

Amilcar Lucas's ArduPilot methodic configurator is a Python tool that implements a [clear and proven configuration sequence of ArduPilot of drones](https://discuss.ardupilot.org/t/how-to-methodically-tune-almost-any-multicopter-using-arducopter-4-4-x/110842/1).
It provides a graphical user interface (GUI) for managing and visualizing ArduPilot parameters, parameter files and documentation.

![Application Screenshot](App_screenshot1.png)

## Usage

Usage is detailed in the [USERMANUAL.md](USERMANUAL.md) file

## MS Windows Installation

Install [git](https://git-scm.com/) and [python](https://www.python.org/downloads/). Then do:

```bash
git clone https://github.com/ArduPilot/MethodicConfigurator.git
cd MethodicConfigurator
.\install_windows.bat
```

On MS Windows it tends to auto-connect to the wrong device, you can explicitly set the device with the `--device` command line option to avoid that. Replace COMX with the correct COM port for your device.

```bash
python3 ardupilot_methodic_configurator.py --device COMX
```

## Linux Installation

Install [git](https://git-scm.com/) and [python](https://www.python.org/downloads/). Then do:

```bash
git clone https://github.com/ArduPilot/MethodicConfigurator.git
cd MethodicConfigurator
./install_linux.sh
```

## Support and Contributing

Please feel free to submit [issues](https://github.com/ArduPilot/MethodicConfigurator/issues) or [pull requests](https://github.com/ArduPilot/MethodicConfigurator/pulls). More information is available on the [contributing and support](CONTRIBUTING.md) page.

## Software architecture

To meet the [Software requirements](ARCHITECTURE.md#software-requirements) a [software architecture](ARCHITECTURE.md#the-software-architecture) was designed and implemented.

## Code of conduct

To use and develop this software you must obey the [ArduPilot Methodic Configurator Code of Conduct](CODE_OF_CONDUCT.md).

## License

This project is licensed under the GNU General Public License v3.0. See the [LICENSE](LICENSE) file for details.
It builds upon other [opensource software packages](credits/CREDITS.md)
