# Software architecture

Before we decided on a software architecture or programming language or toolkit we gathered software requirements as presented below.

## Software requirements

The goal of this software is to automate some of the tasks involved in configuring and tuning an ArduPilot-based vehicle.
The method it follows is explained in the [How to methodically tune (almost) any multicopter using ArduCopter forum Blog post](https://discuss.ardupilot.org/t/how-to-methodically-tune-almost-any-multicopter-using-arducopter-4-4-x/110842/1).
This list of functionalities provides a comprehensive overview of the software's capabilities and can serve as a starting point for further development and refinement.

### 1. Parameter Configuration Management

- The software must allow users to view and manage drone parameters.
- Users should be able to select an intermediate parameter file from a list of available files.
- The software must display a table of parameters with columns for the parameter name, current value, new value, unit, write to flight controller, and change reason.
- The software must validate the new parameter values and handle out-of-bounds values gracefully, reverting to the old value if the user chooses not to use the new value.
- The software must save parameter changes to both the flight controller and the intermediate parameter files

### 2. Communication Protocols

- The software must support communication with the drone's flight controller using MAVlink and FTP over MAVLink protocols.
- The software must handle the encoding and decoding of messages according to the specified protocols.
- The software must allow users to tune drone parameters.
- Users should be able to write selected parameters to the flight controller and advance to the next intermediate parameter file.
- The software must provide a mechanism to reset the ArduPilot if required by the changes made to the parameters.
- The software must make sure the parameter change communication worked by re-reading and validating that the parameter changed on the vehicle.

### 4. User Interface

- The software must provide a user-friendly interface with clear navigation and controls.
- The interface must be responsive and adapt to different screen sizes and resolutions.
- Users should be able to toggle between showing only changed parameters and showing all parameters.
- The software must provide feedback to the user, such as success or error messages, when performing actions like writing parameters to the flight controller.
- Users should be able to skip to the next parameter file without writing changes.
- The software must ensure that all changes made to entry widgets are processed before proceeding with other actions, such as writing parameters to the flight controller.
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
  - Complete flight controller "reason changed" annotated parameters in "complete.param" file
  - Non-default, read-only "reason changed" annotated parameters in, "non-default_read-only.param" file
  - Non-default, writable calibrations "reason changed" annotated parameters in "non-default_writable_calibrations.param" file
  - Non-default, writable non-calibrations "reason changed" annotated parameters in "non-default_writable_non-calibrations.param" file

### 9. Customization and Extensibility

- The software must be extensible to support new drone models and parameter configurations.
- Users should be able to customize the software's behavior through configuration files:
  - `ArduCopter_configuration_steps.json`, `ArduPlane_configuration_steps.json`, etc
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
4. the tkinter frontend, which is the GUI the user interacts with
   1. [`frontend_tkinter_base.py`](MethodicConfigurator/frontend_tkinter_base.py)
   2. [`frontend_tkinter_connection_selection.py`](MethodicConfigurator/frontend_tkinter_connection_selection.py)
   3. [`frontend_tkinter_directory_selection.py`](MethodicConfigurator/frontend_tkinter_directory_selection.py)
   4. [`frontend_tkinter_component_editor.py`](MethodicConfigurator/frontend_tkinter_component_editor.py)
   5. [`frontend_tkinter_parameter_editor.py`](MethodicConfigurator/frontend_tkinter_parameter_editor.py)
   6. [`frontend_tkinter_parameter_editor_table.py`](MethodicConfigurator/frontend_tkinter_parameter_editor_table.py)

![Software Architecture diagram](images/Architecture.drawio.png)

The parts can be individually tested, and do have unit tests.
They can also be exchanged, for instance, [tkinter-frontend](https://docs.python.org/3/library/tkinter.html) can be replaced with [wxWidgets](https://www.wxwidgets.org/) or [pyQt](https://riverbankcomputing.com/software/pyqt/intro).

In the future, we might port the entire application into a client-based web application.
That way the users would not need to install the software and will always use the latest version.
