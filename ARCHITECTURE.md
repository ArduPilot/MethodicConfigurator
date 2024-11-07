# Software architecture
<!--
SPDX-FileCopyrightText: 2024 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
-->

Before we decided on a software architecture or programming language or toolkit we gathered software requirements as presented below.

## Software requirements

The goal of this software is to automate some of the tasks involved in configuring and tuning an ArduPilot-based vehicle.
The method it follows is explained in the [How to methodically tune any ArduCopter](https://ardupilot.github.io/MethodicConfigurator/TUNING_GUIDE_ArduCopter).
This list of functionalities provides a comprehensive overview of the software's capabilities and can serve as a starting point for further development and refinement.

### 1. Parameter Configuration Management

- The software must allow users to view and manage drone parameters.
- Users should be able to select an intermediate parameter file from a list of available files.
- The software must display a table of parameters with columns for the parameter name, current value, new value, unit, upload to flight controller, and change reason.
- The software must validate the new parameter values and handle out-of-bounds values gracefully, reverting to the old value if the user chooses not to use the new value.
- The software must save parameter changes to both the flight controller and the intermediate parameter files

### 2. Communication Protocols

- The software must support communication with the drone's flight controller using MAVlink and FTP over MAVLink protocols.
- The software must handle the encoding and decoding of messages according to the specified protocols.
- The software must allow users to tune drone parameters.
- Users should be able to upload selected parameters to the flight controller and advance to the next intermediate parameter file.
- The software must provide a mechanism to reset the ArduPilot if required by the changes made to the parameters.
- The software must make sure the parameter change communication worked by re-downloading and validating that the parameter changed on the vehicle.

### 4. User Interface

- The software must provide a user-friendly interface with clear navigation and controls.
- The interface must be responsive and adapt to different screen sizes and resolutions.
- Users should be able to toggle between showing only changed parameters and showing all parameters.
- The software must provide feedback to the user, such as success or error messages, when performing actions like uploading parameters to the flight controller.
- Users should be able to skip to the next parameter file without uploading changes.
- The software must ensure that all changes made to entry widgets are processed before proceeding with other actions, such as uploading parameters to the flight controller.
- Read-only parameters are displayed in red, Sensor Calibrations are displayed in yellow and non-existing parameters in blue
- Users should be able to edit the new value for each parameter directly in the table.
- Users should be able to edit the reason changed for each parameter directly in the table.
- The software must provide tooltips for each parameter to explain their purpose and usage.

### 5. Documentation and Help

- The software must include comprehensive documentation and help resources.
- Users should be able to access a blog post or other resources for more information on the software and its usage.

### 6. Error Handling and Logging

- The software must handle errors gracefully and provide clear error messages to the user.
- The software must log events and errors for debugging and auditing purposes.

### 7. Connection Management

- The software must manage the connection to the flight controller, including establishing, maintaining, and closing the connection.
- Users should be able to reconnect to the flight controller if the connection is lost.

### 8. Parameter File Management

- The software must support the loading and parsing of parameter files.
- Users should be able to navigate through different parameter files and select the one to be used.
- Comments are first-class citizens and are preserved when reading/writing files
- The software must write at the end of the configuration the following summary files:
  - Complete flight controller *reason changed* annotated parameters in `complete.param` file
  - Non-default, read-only *reason changed* annotated parameters in, `non-default_read-only.param` file
  - Non-default, writable calibrations *reason changed* annotated parameters in `non-default_writable_calibrations.param` file
  - Non-default, writable non-calibrations *reason changed* annotated parameters in `non-default_writable_non-calibrations.param` file

### 9. Customization and Extensibility

- The software must be extensible to support new drone models and parameter configurations.
- Users should be able to customize the software's behavior through configuration files:
  - `configuration_steps_ArduCopter.json`, `configuration_steps_ArduPlane.json`, etc
  - `vehicle_components.json`
  - intermediate parameter files (`*.param`)
- Development should use industry best practices:
  - [Test-driven development](https://en.wikipedia.org/wiki/Test-driven_development) (TDD)
  - [DevOps](https://en.wikipedia.org/wiki/DevOps)

### 10. Performance and Efficiency

- The software must perform efficiently, with minimal lag or delay in response to user actions.
- The software must be optimized for performance, especially when handling large numbers of parameters.

## The Software architecture

To satisfy the software requirements described above the following software architecture was developed:

It consists of four main components:

1. the application itself does the command line parsing and starts the other processes
   1. [`ardupilot_methodic_configurator.py`](MethodicConfigurator/ardupilot_methodic_configurator.py)
   2. [`common_arguments.py`](MethodicConfigurator/common_arguments.py)
   3. [`version.py`](MethodicConfigurator/version.py)
2. the local filesystem backend does file I/O on the local file system. Operates mostly on parameter files and metadata/documentation files
   1. [`backend_filesystem.py`](MethodicConfigurator/backend_filesystem.py)
   2. [`backend_filesystem_vehicle_components.py`](MethodicConfigurator/backend_filesystem_vehicle_components.py)
   3. [`backend_filesystem_configuration_steps.py`](MethodicConfigurator/backend_filesystem_configuration_steps.py)
3. the flight controller backend communicates with the flight controller
   1. [`backend_flight_controller.py`](MethodicConfigurator/backend_flight_controller.py)
   2. [`backend_mavftp.py`](MethodicConfigurator/backend_mavftp.py)
   3. [`param_ftp.py`](MethodicConfigurator/param_ftp.py)
   4. [`battery_cell_voltages.py`](MethodicConfigurator/battery_cell_voltages.py)
4. the tkinter frontend, which is the GUI the user interacts with
   1. [`frontend_tkinter_base.py`](MethodicConfigurator/frontend_tkinter_base.py)
   2. [`frontend_tkinter_connection_selection.py`](MethodicConfigurator/frontend_tkinter_connection_selection.py)
   3. [`frontend_tkinter_directory_selection.py`](MethodicConfigurator/frontend_tkinter_directory_selection.py)
   4. [`frontend_tkinter_component_editor.py`](MethodicConfigurator/frontend_tkinter_component_editor.py)
   5. [`frontend_tkinter_component_editor_base.py`](MethodicConfigurator/frontend_tkinter_component_editor_base.py)
   6. [`frontend_tkinter_parameter_editor.py`](MethodicConfigurator/frontend_tkinter_parameter_editor.py)
   7. [`frontend_tkinter_parameter_editor_table.py`](MethodicConfigurator/frontend_tkinter_parameter_editor_table.py)

![Software Architecture diagram](images/Architecture.drawio.png)

The parts can be individually tested, and do have unit tests.
They can also be exchanged, for instance, [tkinter-frontend](https://docs.python.org/3/library/tkinter.html) can be replaced with [wxWidgets](https://www.wxwidgets.org/) or [pyQt](https://riverbankcomputing.com/software/pyqt/intro).

In the future, we might port the entire application into a client-based web application.
That way the users would not need to install the software and will always use the latest version.

## Adding a translation

To add a new translation language to the Ardupilot Methodic Configurator, follow the steps below. This process involves creating a new language folder in the locale directory and generating the necessary translation files. You will use the `create_pot_file.py` script to extract the strings that need translation and create a `.pot` file, which serves as a template for the translation.

### 1. Set Up Your Locale Directory

Navigate to the `locale` directory inside your project:

```bash
cd MethodicConfigurator/locale
```

### 2. Create a New Language Directory

Create a new folder for the language you want to add. The name of the folder should follow the standard language code format (e.g., de for German, fr for French).

```bash
mkdir <language_code>
```

For example, to add support for German:

```bash
mkdir de
```

### 3. Generate a Template POT File

If you haven't already generated a `.pot` file, you can do so by running the `create_pot_file.py` script.
This script will extract all translatable strings from the project files and create a `.pot` file.

Ensure you are in the root directory of your project, and execute the following command:

```bash
python3 create_pot_file.py
```

This will create a file named `MethodicConfigurator.pot` inside the `MethodicConfigurator/locale` directory.

### 4. Create a New PO File

Inside your newly created language directory, create a new `.po` file using the `.pot` template:

```bash
cd de
cp ../MethodicConfigurator.pot MethodicConfigurator.po
```

### 5. Translate the Strings

Open the `MethodicConfigurator.po` file in a text editor or a specialist translation tool (e.g., [Poedit](https://poedit.net/)). You will see the extracted strings, which you can begin translating.

Each entry will look like this:

```text
msgid "Original English String"
msgstr ""
```

Fill in the `msgstr` lines with your translations:

```text
msgid "Original English String"
msgstr "Translated String"
```

### 6. Compile the PO File

Once you have completed your translations, you will need to compile the `.po` file into a binary `.mo` file. This can be done using the command:

```bash
python3 create_mo_files.py
```

Make sure you have `msgfmt` installed, which is part of the *GNU gettext* package.

### 7. Test the New Language

Now add the language to the end of the `LANGUAGE_CHOICES` array in the `MethodicConfigurator/internationalization.py` file.

```python
LANGUAGE_CHOICES = ['en', 'zh_CN', 'pt', 'de']
```

And add it also to the `[Languages]` and `[Icons]` sections of the `windows/ardupilot_methodic_configurator.iss` file.

```text
[Languages]
 Name: "en"; MessagesFile: "compiler:Default.isl"
 Name: "zh_CN"; MessagesFile: "compiler:Languages\ChineseSimplified.isl"
 Name: "pt"; MessagesFile: "compiler:Languages\Portuguese.isl"
 Name: "de"; MessagesFile: "compiler:Languages\German.isl"
...

[Icons]
...
Name: "{commondesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{userappdata}\.ardupilot_methodic_configurator"; Tasks: desktopicon; IconFilename: "{app}\MethodicConfigurator.ico"; Parameters: "--language {language}"; Languages: zh_CN pt de
...
```

With the new `.mo` file created, you should ensure the software correctly loads the new language.
Update the software's configuration to set the desired language and run the application to test your translations.

### 8. Review and Refine

Once the new language is running in the software, review the translations within the application for clarity and correctness. Make adjustments as needed in the `.po` file and recompile to an `.mo` file.

Following these steps should enable you to successfully add support for any new translation language within the Ardupilot Methodic Configurator.
