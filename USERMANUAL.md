# ArduPilot Methodic Configurator User Manual

## Overview

*ArduPilot Methodic Configurator* is a PC software designed by ArduPilot developers to simplify the configuration of ArduPilot drones.
It's graphical user interface (GUI) manages, edits and visualizes drone parameter files, as well as uploads parameters to the vehicle.
It automates the tasks described in the [How to methodically tune any ArduCopter](https://ardupilot.github.io/MethodicConfigurator/TUNING_GUIDE_ArduCopter) tuning guide.

This user manual gives a general overview of the Software functionality.
There are also [quick start instructions](README.md) and [specific use case instructions](USECASES.md).

## Usage

Before starting the application on your PC you should connect a flight controller to the PC and wait at least seven seconds.

### Flight Controller Connection Selection Interface

This interface allows users to select or add a connection to a flight controller **if one was not yet auto-detected**.

![Flight controller connection selection window](images/App_screenshot_FC_connection.png)
<figure>
<br>
  <ins><b><i>Flight controller connection selection window</i></b></ins>
</figure>

It provides three main options for connecting to a flight controller:

#### Option 1: Auto-connect to flight controller

This option automatically attempts to connect to a flight controller that has been connected to the PC.
The user must wait for at least 7 seconds for the flight controller to fully boot before attempting the connection.

#### Option 2: Select flight controller connection

Manually select an existing flight controller connection or add a new one.
It provides a dropdown menu listing all available connections, including an option to add a new connection.

- To select an existing connection, use the dropdown menu to choose the desired connection.
- To add a new connection, select "Add another" from the dropdown menu. A dialog box will prompt you to enter the connection string for the new flight controller.

#### Option 3: No flight controller Connection

Skip the flight controller connection process.
It proceeds with editing the intermediate `.param` files on disk without fetching parameter values nor parameter default parameter values from the flight controller.

### Flight Controller Info and parameter download

If a flight controller is connected the software will now get information from it.
The information is presented in the corresponding window and at the same time all flight controller parameters are downloaded to the PC.

![Flight controller info and parameter download](images/App_screenshot_FC_info_and_param_download.png)
<figure>
<br>
  <ins><b><i>Flight controller info and parameter download</i></b></ins>
</figure>

### Vehicle Configuration Directory Selection Interface

This interface allows users to select a vehicle directory that contains intermediate parameter files for ArduPilot
**if one was not specified with the `--vehicle-dir` command line parameter**.

![Vehicle Selection Window](images/App_screenshot_Vehicle_directory.png)
<figure align="center">
<br>
  <ins><b><i>Vehicle Selection Window</i></b></ins>
</figure>

It provides three main options for selecting a vehicle directory:

#### New

Create a new vehicle configuration directory by copying files from an existing template directory.
It's useful for setting up a new vehicle configuration quickly.

- Use the "Source template directory" `...` button to select the existing vehicle template directory containing the intermediate parameter files to be copied.
  Use the overview window to select the template that better matches the components of your vehicle.
![Vehicle template overview](images/App_screenshot_Vehicle_overview.png)
- By default, the new vehicle parameter values are taken from the source template.
  But if your connected vehicle has already been correctly configured, checking the `Use parameter values from connected FC, not from template files`
  will use the parameter values from the FC instead.
- Use the "Destination base directory" `...` button to select the existing directory where the new vehicle directory will be created.
- Enter the name for the new vehicle directory in the "Destination new vehicle name" field.
- Click the "Create vehicle directory from template" button to create the new vehicle directory on the base directory and copy the template files to it.

#### Open

Open an existing vehicle configuration directory that already contains intermediate parameter files.
It's useful for editing an existing vehicle configuration.

- Use the "Vehicle directory" `...` button to select the existing vehicle directory containing the intermediate parameter files.

#### Re-open

Re-open the last used vehicle configuration directory.

### Vehicle Component Editor Interface

Here you specify the components of your vehicle, their properties and how they are connected to the flight controller.

![Vehicle Component Editor Window - simple](images/App_screenshot_Component_Editor.png) ![Vehicle Component Editor Window - normal](images/App_screenshot_Component_Editor_normal.png)

On the left with simple GUI complexity for beginners, on the right with normal GUI complexity.

Change every field to match your vehicle's.
When finished press the `Save data and start configuration` button.

The application will validate your input.
If issues are found the problematic fields' background will be marked in red color.
Correct those entries and press the `Save data and start configuration` button again.

### Parameter File Editor and uploader interface

Here you sequentially configure the parameters of your flight controller to meet your needs while having all the available documentation at your fingertips.

For reproducibility and quality purposes, we configure the vehicle with a well-defined sequence of intermediate parameter files.

Each file modifies just a small set of the [over 1200 parameters on the flight controller](https://ardupilot.org/copter/docs/parameters.html).
By splitting the process into small manageable steps, we reduce the probability of making a mistake or missing a step and allow interleaving parameter changes with test flights.
Each intermediate parameter file is a text file, editable in any common text editor (excluding MS Word) like [Notepad++](https://notepad-plus-plus.org/),
[nano](https://www.nano-editor.org/) or [code](https://code.visualstudio.com/).
It contains the *official ArduPilot parameter documentation* in the form of comments in the lines preceding the parameter.
By using this you save the time of looking up the online documentation for each parameter.
It contains the **reason why we changed the parameter** in a comment on the same line as the parameter and is used to
trace each parameter change to the reason for that parameter change.

Comments start with the '#' character.
A small example with a single parameter is shown below:

```text

# Arming with Rudder enable/disable
# Allow arm/disarm by rudder input. When enabled arming can be done with right rudder, disarming with left rudder.
# 0: Disabled
# 1: ArmingOnly
# 2: ArmOrDisarm
ARMING_RUDDER,0 # We find it safer to use only a switch to arm instead of through rudder inputs
```

If you are working with multiple vehicles, create a separate directory for each vehicle with a descriptive identifiable name.
Copy the approx. 50 *intermediate parameter files* into them.
Edit the files to match the specific requirements of each vehicle.
Now you have traceable documentation records for every parameter change on each of your vehicles.

If you are in the business of manufacturing multicopters and maintain **high-quality standards that result in the production of multiple, nearly identical vehicles**,
you can reuse most intermediate parameter files across these vehicles.
Only three intermediate parameter files: `03_imu_temperature_calibration_results.param`, `12_mp_setup_mandatory_hardware.param` and
`25_inflight_magnetometer_fit_results.param` are specific to each vehicle instance.
All other intermediate parameter files can be used without modifications across all instances (or serial numbers) of the same product model.

![Parameter File Editor and Uploader Window (main application)](images/App_screenshot_Parameter_file_editor_and_uploader4_4_simple.png)
<figure align="center">
<br>
  <ins><b><i>Parameter File Editor and Uploader Window (main application) in simple GUI complexity for beginners</i></b></ins>
</figure>

![Parameter File Editor and Uploader Window (main application)](images/App_screenshot2.png)
<figure align="center">
<br>
  <ins><b><i>Parameter File Editor and Uploader Window (main application) in normal GUI complexity</i></b></ins>
</figure>

The GUI complexity (simple or normal) is selected in the vehicle component editor window in the previous step.
The normal layout is explained below, the simple layout is similar but has less elements.

#### 1. See the Current Vehicle Directory (optional)

- this vehicle configuration directory contains the files to be edited and uploaded

#### 2. Select an Intermediate Parameter File (optional)

- vehicle-specific intermediate parameter filenames start with two digits followed by an underscore and end in `.param`
- **Use the `Current intermediate parameter file:` combobox to select an intermediate parameter file.**
- The first available intermediate parameter file not named `00_default.param` will be selected by default
- If the selection changes, the parameter table will update to display the parameters from the selected file.
- The sequence is defined by the order of the intermediate parameter files in the vehicle configuration directory.

#### 3. About information and help links (optional)

When you click the ArduPilot logo the following window will appear:
![About and help information](images/App_screenshot_about.png)

#### 4a. Configuration sequence progress bar

This segmented bar shows the progress in the vehicle configuration sequence.
The progress bar is updated automatically when you upload an intermediate parameter file to the flight controller or
select a different intermediate parameter file in the `Current intermediate parameter file:` combobox above it.
The steps are grouped into phases and optional phases are greyed-out.
There are mouse-over hints for each phase.

![Parameter editor and uploader window](images/App_parameter_editor_and_uploader.png)

#### 4b. Viewing Documentation

- **Click on the documentation labels to open the corresponding documentation in a web browser.**
- Documentation is split into four categories:
  - **Blog Post - ArduPilot's forum Methodic configuration Blog post relevant to the current file**
  - Wiki - ArduPilot's wiki page relevant to the current file
  - External tool -External tool or documentation relevant to the current file
  - Mandatory - Mandatory level of the current file:
    - 100% you MUST use this file to configure the vehicle,
    - 0% you can ignore this file if it does not apply to your vehicle
- Hover over the labels to see tooltips with additional information.

#### 5. Editing Parameters

![Editing parameters](images/App_editing_parameters.png)

- The parameter table presents the parameters in the current intermediate parameter file
- The first column is a `Del` button that deletes the parameter in this row from the current intermediate parameter file.
- The second column is the ArduPilot parameter name used in that row.
  - ReadOnly parameters are presented on a *red background*🟥, they should not be present in an intermediate configuration file because
    under normal conditions they can not be changed
  - Sensor calibration parameters are presented on a *yellow background*🟨, they are vehicle-instance dependent and can NOT be reused between similar vehicles
- The current parameter value downloaded from your FC is in the `Current Value` column.
  - Not available parameter values are presented as `N/A` on an *orange background*🟧
  - Parameters that have the default parameter value are presented on a *light blue background* 🟦
- The new value is the value in the intermediate file and will be uploaded to the flight controller.
  **You MUST change the value to meet your needs**. The provided values in the `vehicle_template` directory are just examples.
  - parameters that should not be changed by the users, or are derived from information in the [*component editor*](#vehicle-component-editor-interface)
    are greyed out and can not be edited.
  - bitmask parameters are editable in two ways:
    - *Decimal* - enter the decimal value of the bitmask as you would with any other parameter.
    - *Bitmask* - double-click the parameter value with the mouse and a window will popup where you can edit the individual bits in the bitmask.
- **In the parameter table, you can edit the `New Value` and `Change Reason` entries for each parameter.**
- **You MUST edit the `Change Reason` so that other users understand why you changed the parameter to that particular `New value`**
- Check the `Upload` checkbox to select parameters to be uploaded to the flight controller
- **Hover over the labels to see tooltips with additional information.**
- The entire ArduPilot official parameter documentation is available on the tooltip, no need to use a browser to search for it.
- The `Add` button adds a parameter to the current intermediate parameter file.

#### 6a. Focus on the changed parameters (optional)

- You can focus on the changed parameters by ticking the "See only changed parameters" checkbox
- Usually, you want to see all parameters and look at their mouse-over tooltips to decide if and how you want to change them

#### 6b. Annotate parameter metadata information into the parameter files (optional)

Annotate parameter metadata information into the parameter files in the form of comments preceding the respective parameter.
It will create bigger and harder-to-compare parameter files but is more suitable for text editor editing.

#### 7. Uploading Parameters to the Flight Controller

- You can also jump to a particular file using the Combobox as explained in [2. Select an intermediate parameter file](#2-select-an-intermediate-parameter-file-optional)
- **After editing parameters, click the `Upload selected params to FC, and advance to next param file`**
  **button to upload the (`Upload` checkbox) selected parameters to the flight controller.**
- All parameter' `New Value` and `Change Reason` will be written to the current intermediate parameter file, irrespective of the `Upload` checkboxes
- The application will then:
  - upload the selected and changed parameters to the flight controller
  - reset the flight controller if necessary for the new parameter values to take effect
  - upload the parameters again, because before the reset some parameters might have been not visible/uploadable
  - download all the parameters from the flight controller, and validate their value
    - if some parameters fail to upload correctly it asks the user if he wants to retry
- **The application will then advance to the next parameter file.**

#### 8. Skipping to the Next Parameter File (optional)

- If you want to skip the current parameter file without uploading any changes, click the `Skip parameter file` button.

#### 9. Completing the Configuration Process

Once all the intermediate parameter files have been processed, the ArduPilot Methodic Configurator will display a summary message box.
In other words when the last available intermediate parameter file is selected (see
[2. Select an Intermediate Parameter File](#2-select-an-intermediate-parameter-file-optional)) and either
`Upload selected params to FC, and advance to next param file` or `Skip parameter file` button is pressed.
This message box provides a comprehensive overview of the configuration process, including the number of parameters that were kept at their default values,
the number of non-default read-only parameters that were ignored, and the number of non-default writable parameters that were updated.

![Configuration summary message box](images/Last_parameter_file_processed.png)

The summary message box will also categorize the writable parameters into four groups:

```mermaid
pie title Summary files example
    "Unchanged parameters" : 728
    "Non-default read-only parameters - non-default_read-only.param" : 8
    "Non-default writable sensor calibrations - non-default_writable_calibrations.param" : 71
    "Non-default writable non-sensor-calibrations - non-default_writable_non-calibrations.param" : 217
```

- **Unchanged parameters**: These parameters are left unchanged and are displayed on a light blue background 🟦.

- **Non-default read-only parameters**: These parameters are read-only and cannot be changed.
  They are typically related to system configurations that can not be modified and are displayed on a red background 🟥.

- **Non-default writable sensor calibrations**: These parameters are vehicle-instance dependent and cannot be reused between similar vehicles.
  They are typically related to sensor calibration and should be adjusted for each vehicle and are displayed on a yellow background 🟨.

- **Non-default writable non-sensor calibrations**: These parameters can be reused between similar vehicles.
  They are not related to sensor calibration and are generally applicable to a range of vehicles with the same configuration.

After the summary message box is displayed, the application will write the summary information into separate files for easy reference and documentation. These files include:

- `complete.param`: Contains all parameters contained in the flight controller.
- `non-default_read-only.param`: Contains all non-default read-only 🟥 parameters. You can ignore these.
- `non-default_writable_calibrations.param`: Contains all non-default writable sensor calibration 🟨 parameters. These are non-reusable.
- `non-default_writable_non-calibrations.param`: Contains all non-default writable non-sensor-calibration parameters. These are reusable across similar vehicles.

The summary files provide a clear overview of the changes made.

The files are also automatically zipped into a file with the same name as the vehicle directory, inside the vehicle directory.

![Parameter files zipped message box](images/Parameter_files_zipped.png)

You should upload this `.zip` file or the `non-default_writable_non-calibrations.param` file to the [How to methodically tune any ArduCopter Blog post](https://discuss.ardupilot.org/t/how-to-methodically-configure-and-tune-any-arducopter/110842/)

Once the summary files are written, the application will close the connection to the flight controller and terminate.

## Configuring

### 1. Configuration files

Most users will not need to configure the tool, but if you do want to do it you can.

The ArduPilot Methodic Configurator uses several configuration files to manage and visualize drone parameters.
These files are crucial for the tool's operation and are organized in a specific directory structure.

- **Intermediate Parameter Files**: These files are located in the vehicle-specific directory and are named with two digits followed by an underscore, ending in `.param`.
  They contain the parameters that need to be configured for the drone. Each file corresponds to a specific configuration step or aspect of the drone's setup.

- **Documentation File**: This file provides documentation for each intermediate parameter file.
  It is used to display relevant information about the parameters and their configuration process.
  The `configuration_steps_ArduCopter.json` documentation file is first searched in the selected vehicle-specific directory,
  and if not found, in the directory where the script is located.

- **Default Parameter Values File**: The `00_defaults.param` file is located in the vehicle-specific directory.
  If the file does not exist or is invalid, use this command to regenerate it

```bash
extract_param_defaults bin_log_file.bin > 00_default.param
```

- **ArduPilot parameter documentation File**: The `apm.pdef.xml` contains documentation and metadata for each ArduPilot parameter in an XML format.
  The file is first searched in the selected vehicle-specific directory, and if not found, in the directory where the script is located,
  and if not found automatically downloaded [from the internet](https://autotest.ardupilot.org/Parameters/versioned/).
  If the vehicle/version combination does not exist you need to generate this file yourself using the ardupilot source code for the firmware version that you want to use:

```bash
cd ardupilot
./Tools/autotest/param_metadata/param_parse.py --vehicle ArduCopter --format xml
cp apm.pdef.xml /path/to/your/vehicle/directory
```

The tool uses these files to manage the configuration process, allowing users to select and edit parameters, and upload the changes back to the flight controller.
The intermediate parameter files are the primary focus of the user interface, as they contain the parameters that the user can modify.
The documentation files provide context and guidance for each parameter.

## Command Line Usage

The *ArduPilot Methodic Configurator* can be started from the command line.
The command line interface provides several options to customize the behavior of the tool.

To use the command line interface, execute `ardupilot_methodic_configurator` on the command line.

Here is a list of command line options:

- **`--skip-check-for-updates`**: Skip check for software updates before staring the software. Default is False.
- **`--baudrate BAUDRATE`**: MAVLink serial connection baudrate to the flight controller. Default is 115200
- **`--device`**: The MAVLink connection string to the flight controller. It defaults to autoconnection to the first available flight controller.
- **`--vehicle-dir`**: The directory containing intermediate parameter files. Defaults to the current working directory directory.
- **`--n`**: Start directly on the nth intermediate parameter file (skip previous files). The default is 0.
- **`--skip-component-editor`**: Skip the component editor window. Only use this if all components have been configured. Default is False
- **`--loglevel`**: The logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL). The default is INFO.
- **`-t` or `--vehicle-type`**: The type of the vehicle.
  Choices are 'AP_Periph', 'AntennaTracker', 'ArduCopter', 'ArduPlane', 'ArduSub', 'Blimp', 'Heli', 'Rover', 'SITL'. Defaults to 'ArduCopter'.
- **`-r` or `--reboot-time`**: Flight controller reboot time. The default is 7.
- **`-v` or `--version`**: Display version information and exit.

Example usage:

```bash
ardupilot_methodic_configurator --device="tcp:127.0.0.1:5760" --vehicle-dir="/path/to/params" --n=0 --loglevel=INFO -t=ArduCopter
```

This command will connect to the flight controller at `tcp:127.0.0.1:5760`, use the parameter files in the specified directory,
start with the first parameter file, set the logging level to INFO, and target the ArduCopter vehicle type.

For more detailed information on the command line options, you can run the script with the `-h` or `--help` flag to display the help message:

```bash
ardupilot_methodic_configurator --help
```

This will show a list of all available command line options along with a brief description of each.

### Install command line completion

#### Global python argcomplete

For command line (tab) completion for all python scripts that support [argcomplete](https://github.com/kislyuk/argcomplete) do:

```bash
activate-global-python-argcomplete
```

#### Fine granular python argcomplete

For Bash (Linux, macOS) autocompletion, add this to your `~/.bashrc`:

```bash
eval "$(register-python-argcomplete ardupilot_methodic_configurator)"
eval "$(register-python-argcomplete extract_param_defaults)"
eval "$(register-python-argcomplete annotate_params)"
eval "$(register-python-argcomplete param_pid_adjustment_update)"
eval "$(register-python-argcomplete mavftp)"
```

For Zsh (Linux, macOS) autocompletion, add these lines to your `~/.zshrc`:

```zsh
autoload -U bashcompinit
bashcompinit
eval "$(register-python-argcomplete ardupilot_methodic_configurator)"
eval "$(register-python-argcomplete extract_param_defaults)"
eval "$(register-python-argcomplete annotate_params)"
eval "$(register-python-argcomplete param_pid_adjustment_update)"
eval "$(register-python-argcomplete mavftp)"
```

For PowerShell (MS Windows) autocompletion, run this command in PowerShell:

```powershell
notepad $PROFILE
```

And add this line to the file:

```powershell
Import-Module  "C:\Program Files (x86)\ardupilot_methodic_configurator\ardupilot_methodic_configurator_command_line_completion.psm1"
```

## Speed up software start

To speed up the startup of the ArduPilot methodic configurator, consider the following tips, presented from most to least effective:

All of these can be either added in the command line as a parameter, or in the "properties > link > target" of the desktop icon.
Use and empty space to separate each option.

1. `--device <devicename>` this explicitly connects to \<devicename> skipping the auto-detection process.
1. `--vehicle-dir <vehicle-directory>` this explicitly looks for project files in \<vehicle-directory> saving you the trouble to
 manually select it in the GUI.
1. `--skip-component-editor` if you do not need to change the components and connections of your vehicle, this will skip the
 component and connection editor window.
1. `--n <number>` this will skip directly to step number \<number> so that you do not need to skip the previous steps
1. `--skip-check-for-updates` this saves very little time on startup, but you can skip it using this.

**Pro tip:** create multiple desktop icons, each one with a different project and or configuration.

## Troubleshooting

If you encounter any issues during the configuration process, refer to the error messages provided by the application.
These messages can guide you to the specific problem and suggest possible solutions.
If the issue persists, consult the [documentation and support page](https://ardupilot.github.io/MethodicConfigurator/SUPPORT.html)

<!-- Gurubase Widget -->
<script async src="https://widget.gurubase.io/widget.latest.min.js"
    data-widget-id="uE4kxEE4LY3ZSyfNsF5bU6gIOnWGTBOL_e16KwDH-0g"
    data-text="Ask AI"
    data-margins='{"bottom": "1rem", "right": "1rem"}'
    data-light-mode="true"
    id="guru-widget-id">
</script>
