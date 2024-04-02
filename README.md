# ArduPilot methodic configurator

Amilcar Lucas's ArduPilot methodic configurator is a Python tool designed to simplify the configuration ArduPilot of drones.
It provides a graphical user interface (GUI) for managing and visualizing drone parameters, as well as communication protocols for drone components.

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
```

You can run the ArduPilot methodic configurator GUI by executing the following command:

```bash
python3 ardupilot_methodic_configurator.py
```

This will launch the GUI, where you can select a vehicle configuration directory where the intermediate parameter files are stored and adjust parameters as needed.
Each parameter change is traceable via its own individual comment

## Usage

Usage is detailed in the [USERMANUAL.md](USERMANUAL.md) file

## Development requirements

Software development requirements are on the [REQUIREMENTS.md](REQUIREMENTS.md) file

## Software architecture

To meet the [Software requirements](REQUIREMENTS.md) a [software architecture](REQUIREMENTS.md#software-architecture) was designed and implemented.

## Contributing

Contributions are welcome! Please feel free to submit [issues](https://github.com/ArduPilot/MethodicConfigurator/issues) or [pull requests](https://github.com/ArduPilot/MethodicConfigurator/pulls).

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
