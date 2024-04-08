# ArduPilot Methodic Configurator User Manual

## Overview

Amilcar Lucas's - ArduPilot Methodic Configurator is a Python tool designed to simplify the configuration of ArduPilot drones.
It provides a graphical user interface (GUI) for managing, editing and visualizing drone parameter files, as well as writing parameters to the vehicle.
It automates the tasks described in the [How to methodically tune (almost) any multicopter using ArduCopter forum Blog post](https://discuss.ardupilot.org/t/how-to-methodically-tune-almost-any-multicopter-using-arducopter-4-4-x/110842/1)

![Application Screenshot](images/App_screenshot2.png)

## Usage

Before you start you must copy one of the `vehicle_example` directories, and rename the copy to the name of your vehicle.
Please do not change the original vehicle example files of the application, so that you can compare changes if you want to.

For example if you are using `ArduCopter 4.5.1` on MS Windows do:

1. copy `C:\ProgramData\.ardupilot_methodic_configurator\vehicle_examples\4.5.1-params` to `C:\ProgramData\.ardupilot_methodic_configurator\my_cool_vehicle`
2. connect a flight controller to your PC and wait 5 seconds
3. start the application using the Desktop Icon

For example if you are using `ArduCopter 4.4.4` on Linux do:

1. copy `MethodicConfigurator/vehicle_examples/4.4.4-params` to `MethodicConfigurator/my_cool_vehicle`
2. connect a flight controller to your PC and wait 5 seconds
3. start the application using the Desktop Icon


### 1. Select a Vehicle Directory

- **Click the `...` button next to the `Vehicle directory:` label to open a directory selection dialog.**
- **Navigate to the directory containing the vehicle-specific intermediate parameter files (if you are running it for the first time use the one you just created) and click `OK`.**
- vehicle-specific intermediate parameter filenames start with two digits followed by an underscore and end in `.param`

### 2. Select an Intermediate Parameter File

- **Use the `Current intermediate parameter file:` combobox to select an intermediate parameter file.**
- The first available intermediate parameter file not named `00_default.param` will be selected by default
- If the selection changes, the parameter table will update to display the parameters from the selected file.

### 3. Select a Flight Controller Connection

- **If a flight controller is detected and the `--device` command-line parameter was not explicitly set, it will connect to it.**
- The `Flight controller connection:` combobox lists available connections.
- Select a connection to establish communication with the flight controller.

### 4. Viewing Documentation

- **Click on the documentation labels to open the corresponding documentation in a web browser.**
- Documentation is split into four categories:
  - **Blog Post - ArduPilot's forum Methodic configuration Blog post relevant for the current file**
  - Wiki - ArduPilot's wiki page relevant for the current file
  - External tool -External tool or documentation relevant for the current file
  - Mandatory - Mandatory level of the current file:
    - 100% you MUST use this file to configure the vehicle,
    - 0% you can ignore this file if it does not apply to your vehicle
- Hover over the labels to see tooltips with additional information.

### 5. Editing Parameters

- The parameter table presents the parameters in the current intermediate parameter file
- The first colum is the ArduPilot parameter name used in that row.
  - ReadOnly parameters are presented on a read background, they should not be present in a intermediate configuration file because under normal conditions they can not be changed
  - Sensor calibration parameters are presented on a yellow background, they are vehicle-instance dependent and can NOT be reused between similar vehicles
- The current parameter value read from your FC is on the `Current Value` column.
  - Not available parameter values are presented on a blue background
- The new value is the value in the intermediate file and will be written to the flight controller. **You MUST change the value to meet your needs**. The provided values in the `example_vehicle` directory are just examples.
- **In the parameter table, you can edit the `New Value` and `Change Reason` entries for each parameter.**
- **You MUST edit the `Change Reason` so that other users understand why you changed the parameter to that particular `new value`**
- Check the `Write` checkbox to select parameters to be written to the flight controller
- **Hover over the labels to see tooltips with additional information.**
- The entire ArduPilot official parameter documentation is available on the tooltip, no need to use a browser to search it

### 6. Focus on the changed parameters (optional)

- You can focus on the changed parameters by ticking the "See only changed parameters" checkbox
- Usually you want to see all parameters and look at their mouse-over tooltips to decide if and how you want to change them

### 7. Writing Parameters to the Flight Controller

- You can also jump to a particular file using the combobox as explained in [2. Select an Intermediate Parameter File](#2-select-an-intermediate-parameter-file)
- **After editing parameters, click the `Write selected params to FC, and advance to next param file` button to write the (`Write` checkbox) selected parameters to the flight controller.**
- All parameter's `New Value` and `Change Reason` will be written to the current intermediate parameter file, irrespective of the `Write` checkboxes
- The application will them:
  - write the selected and changed parameters to the flight controller
  - reset the flight controller if necessary for the new parameter values to take effect
  - write the parameters again, because before the reset some parameters might have been not visible/writeable
  - read all the parameters from the flight controller, and validate their value
    - if some parameters failed to write correctly it asks the user if he wants to retry
- **The application will then advance to the next parameter file.**

### 8. Skipping to the Next Parameter File (optional)

- If you want to skip the current parameter file without writing any changes, click the `Skip parameter file` button.

### 9. Completing the Configuration Process

Once all the intermediate parameter files have been processed, the ArduPilot Methodic Configurator will display a summary message box.
In other words when the last available intermediate parameter file is selected (see [2. Select an Intermediate Parameter File](#2-select-an-intermediate-parameter-file)) and either  `Write selected params to FC, and advance to next param file` or `Skip parameter file` button is pressed.
This message box provides a comprehensive overview of the configuration process, including the number of parameters that were kept at their default values, the number of non-default read-only parameters that were ignored, and the number of non-default writable parameters that were updated.

![Configuration summary message box](images/Last_parameter_file_processed.png)

The summary message box will also categorize the writable parameters into four groups:

```mermaid!
pie title Summary files example
    "Unchanged parameters" : 728
    "Non-default read-only parameters - non-default_read-only.param" : 8
    "Non-default writable sensor calibrations - non-default_writable_calibrations.param" : 71
    "Non-default writable non-sensor-calibrations - non-default_writable_non-calibrations.param" : 217
```

- **Unchanged parameters**: These parameters left unchanged.

- **Non-default read-only parameters**: These parameters are read-only and cannot be changed. They are typically related to system configurations that can not be modified.

- **Non-default writable sensor calibrations**: These parameters are vehicle-instance dependent and cannot be reused between similar vehicles. They are typically related to sensor calibration and should be adjusted for each individual vehicle.

- **Non-default writable non-sensor-calibrations**: These parameters can be reused between similar vehicles. They are not related to sensor calibration and are generally applicable to a range of vehicles with the same configuration.

After the summary message box is displayed, the application will write the summary information to separate files for easy reference and documentation. These files include:

- `complete.param`: Contains all parameters contained in the flight controller.
- `non-default_read-only.param`: Contains all non-default read-only parameters. You can ignore these.
- `non-default_writable_calibrations.param`: Contains all non-default writable sensor calibration parameters. These are non-reusable.
- `non-default_writable_non-calibrations.param`: Contains all non-default writable non-sensor-calibration parameters. These are reusable across similar vehicles.


The summary files provide a clear overview of the changes made.

The files are also automatically zipped into a file with the same name as the vehicle directory, inside the vehicle directory.

![Parameter files zipped message box](images/Parameter_files_zipped.png)

You should upload this `.zip` file or the `non-default_writable_non-calibrations.param` file to the [ArduPilot Methodic configuration Blog post](https://discuss.ardupilot.org/t/how-to-methodically-tune-almost-any-multicopter-using-arducopter-4-4-x/110842)

Once the summary files are written, the application will close the connection to the flight controller and terminate.

## Configuring

### 1. Configuration files

Most users will not need to configure the tool, but if you do want to do it you can.

The ArduPilot Methodic Configurator uses several configuration files to manage and visualize drone parameters. These files are crucial for the tool's operation and are organized in a specific directory structure.

- **Intermediate Parameter Files**: These files are located in the vehicle-specific directory and are named with two digits followed by an underscore, ending in `.param`. They contain the parameters that need to be configured for the drone. Each file corresponds to a specific configuration step or aspect of the drone's setup.

- **Documentation File**: This file provides documentation for each intermediate parameter file. It is used to display relevant information about the parameters and their configuration process. The `file_documentation.json` documentation file is first searched in the selected vehicle-specific directory, and if not found, in the directory where the script is located.

- **Default Parameter Values File**: The `00_defaults.param` file is located in the vehicle-specific directory.
If the file does not exist, or is invalid, use this command to regenerate it

```bash
./extract_param_defaults.py bin_log_file.bin > 00_default.param
```

- **ArduPilot parameter documentation File**: The `apm.pdef.xml` contains documentation and metadata for each ArduPilot parameter in an XML format.
The file is first searched in the selected vehicle-specific directory, and if not found, in the directory where the script is located, and if not found automatically downloaded from the internet.
The only version available in the internet ist the latest 4.6.0-DEV.
So until that changes you need to genet´rate this file yourself for the firmware version that you want to use.

The tool uses these files to manage the configuration process, allowing users to select and edit parameters, and to write the changes back to the flight controller. The intermediate parameter files are the primary focus of the user interface, as they contain the parameters that the user can modify. The documentation files provide context and guidance for each parameter.


## Command Line Usage

The ArduPilot Methodic Configurator can be started from the command line.
The command line interface provides several options to customize the behavior of the tool.

To use the command line interface, navigate to the directory where the `ardupilot_methodic_configurator.py` script is located and run the script with the appropriate arguments.

Here is a list of command line options:

- **`--device`**: The MAVLink connection string to the flight controller. It defaults to autoconnection to the first available flight controller.
- **`--vehicle-dir`**: The directory containing intermediate parameter files. Defaults to the current working directory directory.
- **`--n`**: Start directly on the nth intermediate parameter file (skips previous files). Default is 0.
- **`--loglevel`**: The logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL). Default is INFO.
- **`-t` or `--vehicle-type`**: The type of the vehicle. Choices are 'AP_Periph', 'AntennaTracker', 'ArduCopter', 'ArduPlane', 'ArduSub', 'Blimp', 'Heli', 'Rover', 'SITL'. Defaults to 'ArduCopter'.
- **`-r` or `--reboot-time`**: Flight controller reboot time. Default is 7.
- **`-v` or `--version`**: Display version information and exit.

Example usage:

```bash
python ardupilot_methodic_configurator.py --device="tcp:127.0.0.1:5760" --vehicle-dir="/path/to/params" --n=0 --loglevel=INFO -t=ArduCopter
```

This command will connect to the flight controller at `tcp:127.0.0.1:5760`, use the parameter files in the specified directory, start with the first parameter file, set the logging level to INFO, and target the ArduCopter vehicle type.

For more detailed information on the command line options, you can run the script with the `-h` or `--help` flag to display the help message:

```bash
python ardupilot_methodic_configurator.py --help
```

This will show a list of all available command line options along with a brief description of each.


## Troubleshooting

If you encounter any issues during the configuration process, refer to the error messages provided by the application.
These messages can guide you to the specific problem and suggest possible solutions.
If the issue persists, consider consulting Amilcar Lucas at ArduPilot community forums or re-read this documentation.


