# System design requirements

## Requirements analysis

We collected and analyzed the needs of the ArduPilot users by
[reading 108K+ forum posts](https://discuss.ardupilot.org/u?order=likes_received&period=all),
by reading [Ardupilot FW issues on github](https://github.com/ArduPilot/ardupilot/issues),
by reading the [ArduPilot documentation](https://ardupilot.org/ardupilot/),
by attending the weekly ArduPilot developers meeting and by participating in forum discussions:

- guidelines on how to correctly build the vehicle, many users are not aware of the hardware basics.
- a non-trial and error approach to set the [1300 ArduPilot parameters](https://ardupilot.org/copter/docs/parameters.html)
- a clear sequence of steps to take to configure the vehicle
- a way to save and load the configuration for later use
- a way to document how decisions where made during the configuration process
  - to be able to not repeat errors
  - to be able to reproduce the configuration on another similar but different vehicle
  - to understand why decisions where made and their implications

Then we developed, documented and tested the *clear sequence of steps to take to configure the vehicle* in the
[How to methodically tune any ArduCopter](https://ardupilot.github.io/MethodicConfigurator/TUNING_GUIDE_ArduCopter) guide in Dec 2023.
To semi-automate the steps and processes on that guide the following *system design requirements* were derived:

## 1. Parameter Configuration Management

- The software must allow users to view parameter values
- The software must allow users to change parameter values
- For each step in the configuration sequence there must be a "partial/intermediate" parameter file
- The "partial/intermediate" parameter files must have meaningful names
- The sequence of the "partial/intermediate" parameter files must be clear
- Users should be able to upload all parameters from a "partial/intermediate" parameter file to the flight controller and advance to the next intermediate parameter file.
- Users should be able to upload a subset of parameters from a "partial/intermediate" parameter file to the flight controller
  and advance to the next "partial/intermediate" parameter file in the configuration sequence.
- Users should be able to select a "partial/intermediate" parameter file from a list of available files and select the one to be used.
- The software must display a table of parameters with columns for:
  - the parameter name,
  - current value,
  - new value,
  - unit,
  - upload to flight controller,
  - and change reason.
- The software must validate the new parameter values and handle out-of-bounds values gracefully, reverting to the old value if the user chooses not to use the new value.
- The software must save parameter changes to both the flight controller and the intermediate parameter files

## 2. Communication Protocols

- The software must support communication with the drone's flight controller using [MAVlink](https://mavlink.io/en/):
  - [parameter protocol](https://mavlink.io/en/services/parameter.html) or
  - [FTP-over-MAVLink](https://mavlink.io/en/services/ftp.html) protocols.
- The software must automatically reset the ArduPilot if required by the changes made to the parameters.
  - parameters ending in "_TYPE", "_EN", "_ENABLE", "SID_AXIS" require a reset after being changed
- The software must automatically validate if the parameter was correctly uploaded to the flight controller
  - It must re-upload any parameters that failed to be uploaded correctly
- The software must manage the connection to the flight controller, including establishing, maintaining, and closing the connection.
- Users should be able to reconnect to the flight controller if the connection is lost.

## 3. User Interface

- The software must provide a user-friendly interface with clear navigation and controls.
- The interface must be responsive and adapt to different screen sizes and resolutions.
- Users should be able to toggle between showing only changed parameters and showing all parameters.
- Users should be able to skip to the next parameter file without uploading changes.
- The software must ensure that all changes made to entry widgets are processed before proceeding with other actions, such as uploading parameters to the flight controller.
- Read-only parameters are displayed in red, Sensor Calibrations are displayed in yellow and non-existing parameters in blue
- Users should be able to edit the new value for each parameter directly in the table.
- Users should be able to edit the reason changed for each parameter directly in the table.
- The software must perform efficiently, with minimal lag or delay in response to user actions.
- The software must provide a `gui_complexity` setting that controls the user interface complexity:
  - When set to "simple" (default), the interface simplifies for beginners by:
    - In the component editor:
      - only displaying non-optional properties
      - only displaying components that have at least one non-optional parameter, hiding components with only optional parameters
      - not displaying component template load/save controls
    - In the parameter editor:
      - hiding the "Upload" column, "Current intermediate parameter file" combobox, "See only changed parameters" checkbox, and "Annotate docs into .param files" checkbox;
      - automatically selecting all parameters for upload
    - In the documentation frame:
      - automatically opening all available documentation links (wiki, external tools, blog posts) in the browser
        when the current intermediate parameter file changes, providing immediate access to relevant documentation for beginners
  - When set to "normal", all interface elements are displayed for advanced users
  - Users should be able to switch between complexity levels using a dropdown combobox in the component editor

## 4. Documentation and Help

- The software must include comprehensive documentation and help resources.
- The software must provide tooltips for each GUI widget.
- The software must provide tooltips for each parameter to explain their purpose and usage.
- Users should be able to access the blog post and other resources for more information on the software and its usage.
- The software website should use an AI assistant, trained with ArduPilot documentation, to help users configure their
  vehicles [PR #175](https://github.com/ArduPilot/MethodicConfigurator/pull/175)
  - The AI assistant should be able to answer questions about the parameters and the configuration process
  - The AI assistant should be able to provide guidance on how to resolve common issues that may arise during the configuration process
- The software must have a "Zip Vehicle for Forum Help" button that creates a support package:
  - **Button location**: The button must be placed on the parameter editor window, positioned between the "Download .bin" button and the "Skip Step" button
  - **Button label**: The default English label must read "Zip Vehicle for Forum Help" while still allowing translations for other locales
  - **Files to include**: The button must create a zip archive containing:
    - All intermediate parameter files (numbered configuration step files like `01_setup.param`, `02_config.param`, etc.)
    - The file `00_default.param` if it exists
    - The file `vehicle.jpg` if it exists
    - The file `vehicle_components.json` if it exists
    - The file `last_uploaded_filename.txt` if it exists
    - The file `tempcal_gyro.png` if it exists
    - The file `tempcal_acc.png` if it exists
    - The file `tuning_report.csv` if it exists
    - The configuration steps documentation file for the current vehicle type (e.g., `configuration_steps_ArduCopter.json`)
    - All step-specific documentation metadata files (`.pdef.xml` files corresponding to each parameter file)
  - **Zip size constraint**: The generated archive must stay below 100 KiB so it can be uploaded to the ArduPilot
    forum. To achieve this, the software must automatically exclude heavyweight helper files such as
    `apm.pdef.xml` while still bundling the step-specific `.pdef.xml` files listed above.
  - **Zip filename format**: The created zip file must be named using the format `<vehicle_name>_YYYYMMDD_HHMMSSUTC.zip` where:
    - `<vehicle_name>` is the name of the current vehicle directory
    - `YYYYMMDD` is the current date in UTC (4-digit year, 2-digit month, 2-digit day)
    - `HHMMSS` is the current time in UTC (2-digit hour in 24-hour format, 2-digit minute, 2-digit second)
    - Example: `MyDrone_20231215_143052UTC.zip`
  - **Zip file location**: The zip file must be saved in the current vehicle directory
  - **User notification**: After creating the zip file, the software must display an informational popup that:
    - Shows the full path and filename of the created zip file
    - Instructs the user to upload the zip file to the ArduPilot forum at <https://discuss.ardupilot.org> to
      receive help
    - Instructs the user that if they have a problem during flight, they should also upload one single .bin
      file from a problematic flight to a file sharing service and post a link to it in the support forum
    - Is a standard information dialog that the user must acknowledge
  - **Browser action**: After the user acknowledges the notification popup, the software must
    automatically open the URL <https://discuss.ardupilot.org> in the system's default web browser
  - **Error handling**: If the zip creation fails (e.g., due to file permission issues or disk space),
    the software must display an error message explaining the failure and must not open the browser URL

## 5. Error Handling and Logging

- The software must provide feedback to the user, such as success or error messages, after each action.
- The software must handle errors gracefully and provide clear error messages to the user.
- The software must log events and errors for debugging and auditing purposes to the console.
- if files are empty flag them as non-existing [PR #135](https://github.com/ArduPilot/MethodicConfigurator/pull/135)
- if a downloaded file is empty flag it as download failed [PR #135](https://github.com/ArduPilot/MethodicConfigurator/pull/135)

## 6. Parameter File Management

- The software must support the loading and parsing of parameter files.
- Comments are first-class citizens and are preserved when reading/writing files
- The software must write at the end of the configuration the following summary files:
  - Complete flight controller *reason changed* annotated parameters in `complete.param` file
  - Non-default, read-only *reason changed* annotated parameters in, `non-default_read-only.param` file
  - Non-default, writable calibrations *reason changed* annotated parameters in `non-default_writable_calibrations.param` file
  - Non-default, writable non-calibrations *reason changed* annotated parameters in `non-default_writable_non-calibrations.param` file
- automatically create a parameter backup before the first usage of the software to change parameters [PR #173](https://github.com/ArduPilot/MethodicConfigurator/pull/173)
  - Only backs up the parameters if a backup file does not exist and only if AMC has not yet been used to write parameters to the FC

## 7. Customization and Extensibility

- The software must be extensible to support new drone models and parameter configurations.
- Users should be able to customize the software's behavior through configuration files:
  - `configuration_steps_ArduCopter.json`, `configuration_steps_ArduPlane.json`, etc
  - `vehicle_components.json`
  - intermediate parameter files (`*.param`)

## 8. Automation of development processes

- As many of the development processes should be automated as possible
- Development should use industry best practices:
  - Use git as version control and host the project on [ArduPilot GitHub repository](https://github.com/ArduPilot/MethodicConfigurator)
  - Start with a V-Model development until feature completeness, then switch to DevOps ASAP.
  - [Test-driven development](https://en.wikipedia.org/wiki/Test-driven_development) (TDD)
  - [DevOps](https://en.wikipedia.org/wiki/DevOps)
  - [CI/CD automation](https://en.wikipedia.org/wiki/CI/CD)
  - [git pre-commit hooks](https://github.com/ArduPilot/MethodicConfigurator/blob/master/.pre-commit-config.yaml) for code linting and other code quality checks
  - create command-line autocompletion for bash, zsh and powershell [PR #134](https://github.com/ArduPilot/MethodicConfigurator/pull/134)

## 9. Vehicle components and connections

- Use a JSON schema to define a JSON file that describes all configuration-relevant vehicle components and
 their connections to the flight controller.
  - Required top-level keys are "Format version", "Components", "Program version", "Configuration template"
  - Required components are Flight Controller, Frame, Battery Monitor, Battery, ESC, Motors
  - Optional components are RC Controller, RC Transmitter, RC Receiver, Telemetry, Propellers, GNSS Receiver
  - Each component follows the appropriate structure with required and optional fields
  - Common patterns are defined as reusable definitions
- ensure that both loaded and saved vehicle component data complies with the schema, provide useful error messages when validation fails.
- Allow the user to save a vehicle component to a template and select it directly from a pre-defined set of
  common vehicle components. [PR 272](https://github.com/ArduPilot/MethodicConfigurator/pull/272)
  - For each vehicle component, a dropdown arrow is present as well as a button to allow to save the current filled component.
    - These are presented in alphabetical order
  - A predefined set of commonly used components is included in the software as read-only
    - These get updated and overwritten when a new SW version is installed
  - The user can extend that using his own locally saved component templates
    - These do not get overwritten when a new SW version is installed

<!-- Gurubase Widget -->
<script async src="https://widget.gurubase.io/widget.latest.min.js"
    data-widget-id="uE4kxEE4LY3ZSyfNsF5bU6gIOnWGTBOL_e16KwDH-0g"
    data-text="Ask AI"
    data-margins='{"bottom": "1rem", "right": "1rem"}'
    data-light-mode="true"
    id="guru-widget-id">
</script>
