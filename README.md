# ArduPilot methodic configurator

![GitHub Actions](https://github.com/ardupilot/MethodicConfigurator/actions/workflows/windows_build.yml/badge.svg)

Amilcar Lucas's ArduPilot methodic configurator is a Python tool that implements a clear and proven configuration sequence of ArduPilot of drones.
It provides a graphical user interface (GUI) for managing and visualizing ArduPilot parameters, parameter files and documentation.

![Application Screenshot](App_screenshot1.png)

## Usage

Usage is detailed in the [USERMANUAL.md](USERMANUAL.md) file

## Installation

Before installing this package on linux, ensure that the following system dependencies are installed:

- python3-pil.imagetk

You can install these dependencies on Ubuntu or Debian-based systems using the following command:

```bash
sudo apt-get update
sudo apt-get install python3-pil.imagetk
```

Windows systems do not need that.

Install [git](https://git-scm.com/), it is needed until we get [pypi](https://pypi.org/) working. Then do:

```bash
git clone https://github.com/ArduPilot/MethodicConfigurator.git
cd MethodicConfigurator
python3 -m pip install  pymavlink tkinter argparse logging pyserial pyusb typing json os re webbrowser
```

You can run the ArduPilot methodic configurator GUI by executing the following command:

```bash
python3 ardupilot_methodic_configurator.py
```

This will launch the GUI, where you can select a vehicle configuration directory where the intermediate parameter files are stored and adjust parameters as needed.

## Support

Support options are described in the [support section](CONTRIBUTING.md#support)

## Development requirements

Software development requirements are on the [REQUIREMENTS.md](REQUIREMENTS.md) file

## Software architecture

To meet the [Software requirements](REQUIREMENTS.md) a [software architecture](REQUIREMENTS.md#software-architecture) was designed and implemented.

## Code of conduct

To use and develop this software you must obey the [ArduPilot Methodic Configurator Code of Conduct](CODE_OF_CONDUCT.md).

## Contributing

Please feel free to submit [issues](https://github.com/ArduPilot/MethodicConfigurator/issues) or [pull requests](https://github.com/ArduPilot/MethodicConfigurator/pulls). More information is available on the [contributing](CONTRIBUTING.md) page.

## License

This project is licensed under the GNU General Public License v3.0. See the [LICENSE](LICENSE) file for details.

It uses:

| Software | License |
|----------|---------|
| [pymavlink](https://github.com/ArduPilot/pymavlink) | [GNU Lesser General Public License v3.0](https://github.com/ArduPilot/pymavlink/blob/master/COPYING) |
| [tkinter](https://docs.python.org/3/library/tkinter.html) | [Python Software Foundation License](https://docs.python.org/3/license.html) |
| [argparse](https://docs.python.org/3/library/argparse.html) | [Python Software Foundation License](https://docs.python.org/3/license.html) |
| [logging](https://docs.python.org/3/library/logging.html) | [Python Software Foundation License](https://docs.python.org/3/license.html) |
| [pyserial](https://pyserial.readthedocs.io/en/latest/pyserial.html) | [BSD License](https://github.com/pyserial/pyserial/blob/master/LICENSE.txt) |
| [pyusb](https://github.com/pyusb/pyusb) | [BSD 3-Clause](https://github.com/pyusb/pyusb/blob/master/LICENSE) |
| [typing](https://docs.python.org/3/library/typing.html) | [Python Software Foundation License](https://docs.python.org/3/license.html) |
| [json](https://docs.python.org/3/library/json.html) | [Python Software Foundation License](https://docs.python.org/3/license.html) |
| [os](https://docs.python.org/3/library/os.html) | [Python Software Foundation License](https://docs.python.org/3/license.html) |
| [re](https://docs.python.org/3/library/re.html) | [Python Software Foundation License](https://docs.python.org/3/license.html) |
| [webbrowser](https://docs.python.org/3/library/webbrowser.html) | [Python Software Foundation License](https://docs.python.org/3/license.html) |
| [libusb](https://github.com/libusb/libusb) | [Lesser GNU General Public License v2.1](https://github.com/libusb/libusb/blob/master/COPYING) |
| [Scrollable TK frame](https://gist.github.com/mp035/9f2027c3ef9172264532fcd6262f3b01) by Mark Pointing | [Mozilla Public License, v. 2.0](https://mozilla.org/MPL/2.0/) |
| [Python Tkinter ComboBox](https://dev.to/geraldew/python-tkinter-an-exercise-in-wrapping-the-combobox-ndb) by geraldew | [Mozilla Public License, v. 2.0](https://mozilla.org/MPL/2.0/) |
