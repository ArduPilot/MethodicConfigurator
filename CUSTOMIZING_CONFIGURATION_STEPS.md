# Customizing configuration steps

> ⚠️ **For most users**: You don't need to customize these files.
> This section is intended for advanced users, integrators, and developers who need to extend or modify the configuration workflow.

The ArduPilot Methodic Configurator uses several configuration files to manage and visualize vehicle parameters.
These files are crucial for the tool's operation and are organized in a specific directory structure.

## Overview of Configuration Files

The ArduPilot Methodic Configurator relies on the following key files:

- **Intermediate Parameter Files** (`.param`): Located in the vehicle-specific directory with two-digit prefixes (e.g., `02_imu_setup.param`).
  These contain the parameters configured in each step and are editable plain text files.
  Each file modifies a small subset of the flight controller's 1200+ parameters, enabling a stepwise configuration approach that reduces errors and improves traceability.

- **Configuration Steps File** (`configuration_steps_*.json`): Defines the workflow, documentation, explanations, and advanced behavior for each parameter file.
  Searched first in the vehicle-specific directory, then in the application's installation directory.

- **Default Parameter Values File** (`00_default.param`): Located in the vehicle-specific directory.
  Automatically downloaded from the flight controller via MAVFTP or extracted from a `.bin` log file when creating a new project.
  If broken or missing regenerate with:

  ```bash
  extract_param_defaults bin_log_file.bin > 00_default.param
  ```

- **ArduPilot parameter documentation file** (`apm.pdef.xml`): Contains parameter documentation and metadata in XML format.
  Searched in this order: vehicle directory → installation directory → automatically downloaded [from the internet](https://autotest.ardupilot.org/Parameters/versioned/).
  Generate from ArduPilot source code if needed:

  ```bash
  cd ardupilot
  ./Tools/autotest/param_metadata/param_parse.py --vehicle ArduCopter --format xml
  cp apm.pdef.xml /path/to/your/vehicle/directory
  ```

- **Vehicle Components File** (`vehicle_components.json`): Located in the vehicle-specific directory.
  Stores information about all vehicle components (flight controller, frame, battery, ESC, motors, propellers, receivers, GNSS, telemetry, etc.)
  including their connectivity, specifications, firmware versions, and notes.
  Used for deriving parameter values based on component specifications and validating configuration compatibility.
  Created manually or imported from templates.

- **Vehicle Image File** (`vehicle.jpg`): Located in the vehicle-specific directory.
  Optional photograph or diagram of the vehicle displayed in the GUI for visual reference during configuration.
  Helps users identify the correct vehicle and its physical layout during setup.

## Intermediate Parameter Files

Each intermediate parameter file is a plain text file, editable with ArduPilot Methodic Configurator or any common text editor like
[Notepad++](https://notepad-plus-plus.org/), [nano](https://www.nano-editor.org/), or [VS Code](https://code.visualstudio.com/).

**File contents**:

- **Official ArduPilot documentation** (optional): Included as comments above each parameter, eliminating the need for online documentation lookups
- **Change reason**: A comment on the same line as each parameter, explaining why it was changed

Comments start with the `#` character.
Example:

```text
# Arming with Rudder enable/disable
# Allow arm/disarm by rudder input. When enabled arming can be done with right rudder, disarming with left rudder.
# 0: Disabled
# 1: ArmingOnly
# 2: ArmOrDisarm
ARMING_RUDDER,0 # We find it safer to use only a switch to arm instead of through rudder inputs
```

### Configuration Steps file

The configuration steps file is a JSON file that defines the workflow, documentation, and advanced behavior for each intermediate parameter file.
It serves as the central control mechanism for how the Methodic Configurator processes vehicle configuration steps.

#### File Structure

The configuration steps file contains two main top-level objects:

- **`steps`**: Defines configuration for each parameter file (e.g., `02_imu_temperature_calibration_setup.param`)
- **`phases`** (optional): Groups steps into logical phases for better user organization

```json
{
  "steps": {
    "NN_step_name.param": {
      // Step configuration here
    }
  },
  "phases": {
    "Phase Name": {
      "description": "Phase description",
      "start": 2
    }
  }
}
```

#### Best Practices

Follow these guidelines when creating or modifying configuration steps:

1. **Always provide meaningful explanations**: The `why` and `why_now` fields are crucial for user understanding. Be clear and specific.
2. **Keep URLs current**: External documentation links may move. Regularly verify that `blog_url` and `wiki_url` are still valid.
3. **Use derived parameters for dynamic values**: When parameter values depend on component specifications, use `derived_parameters` with expressions rather
   than forcing fixed values.
4. **Provide fallbacks**: In `derived_parameters`, use `vehicle_components.get()` and `fc_parameters.get()` with default values to prevent errors.
5. **Organize with phases**: Group related configuration steps into phases to help users understand the overall workflow.
6. **Include migration info**: When renaming steps, keep the old filename in `old_filenames` to maintain backward compatibility with existing projects.
7. **Test expressions thoroughly**: Complex expressions in derived parameters should be tested with various input values to ensure correct calculations.

#### Step Fields Reference

Each step in the configuration file can include the following fields.
Start with the **Required Fields** for every step, then add **Optional Fields** as needed for advanced features.

##### Required Fields (All steps must include these)

**`why`**: Explains the purpose and importance of this configuration step.

- **Type**: String
- **Purpose**: Helps users understand the reasoning behind this step
- **Example**:

  ```json
  "why": "The IMU drift is temperature dependent and can cause gyro and/or accel inconsistent errors"
  ```

**`why_now`**: Explains why this step needs to be performed at this specific point in the configuration sequence.

- **Type**: String
- **Purpose**: Justifies the step's position in the workflow
- **Example**:

  ```json
  "why_now": "You need to cool down the FC to perform this calibration. It is easier to do before the FC is mounted in the vehicle"
  ```

**`blog_text`**: Short text describing the step for blog/documentation references.

- **Type**: String
- **Purpose**: Provides a concise title for external documentation
- **Example**:

  ```json
  "blog_text": "IMU (Inertial Measurement Unit) temperature calibration setup"
  ```

**`blog_url`**: URL to the blog or documentation page for this step.

- **Type**: String (must start with `https://`)
- **Purpose**: Direct link to detailed external documentation
- **Example**:

  ```json
  "blog_url": "https://ardupilot.github.io/MethodicConfigurator/TUNING_GUIDE_ArduCopter#41-setup-imu-temperature-calibration"
  ```

**`wiki_text`**: Short text describing the step for wiki references.

- **Type**: String
- **Purpose**: Provides a title for ArduPilot wiki documentation
- **Example**:

  ```json
  "wiki_text": "IMU Temperature Calibration"
  ```

**`wiki_url`**: URL to the ArduPilot wiki documentation for this step.

- **Type**: String
- **Purpose**: Link to official ArduPilot documentation
- **Example**:

  ```json
  "wiki_url": "https://ardupilot.org/copter/docs/common-imutempcal.html"
  ```

**`external_tool_text`**: Name of an external tool needed for this step (can be empty string if not needed).

- **Type**: String
- **Purpose**: Identifies external tools required by the user
- **Examples**:

  ```json
  "external_tool_text": "Mission Planner"
  "external_tool_text": "autotune"
  ```

- **Example (no tool needed)**:

  ```json
  "external_tool_text": ""
  ```

**`external_tool_url`**: URL to download or access the external tool (can be empty string if not needed).

- **Type**: String
- **Purpose**: Provides access to external tools
- **Example**:

  ```json
  "external_tool_url": "https://ardupilot.org/copter/docs/configuring-hardware.html"
  ```

**`mandatory_text`**: Indicates whether the step is mandatory or optional with percentages.

- **Type**: String
- **Format**: Must match the pattern `^[0-9]{1,3}% mandatory \([0-9]{1,3}% optional\)$`
- **Purpose**: Communicates to users the importance level of this step
- **Examples**:

  ```json
  "mandatory_text": "100% mandatory (0% optional)"
  "mandatory_text": "80% mandatory (20% optional)"
  "mandatory_text": "0% mandatory (100% optional)"
  ```

##### Optional Fields

**`auto_changed_by`**: Name of the tool or process that automatically modifies these parameters.

- **Type**: String
- **Purpose**: Informs users which tool is making automatic changes
- **Examples**:

  ```json
  "auto_changed_by": "Mission Planner"
  "auto_changed_by": "FlowCal"
  "auto_changed_by": ""  // Empty if no tool auto-changes these parameters
  ```

**`autoimport_nondefault_regexp`**: Array of regular expressions to match parameters for automatic import if they have non-default values.

- **Type**: Array of strings
- **Purpose**: Parameters to include in this configuration step if their flight controller value differs from the default
- **Use case**: When a user's flight controller already has some parameters configured, this regex pattern ensures those non-default values are imported into the GUI.
- **Example**:

  ```json
  "autoimport_nondefault_regexp": [
    "BRD_HEAT_.*",
    "INS_TCAL_OPTIONS",
    "TCAL_ENABLED"
  ]
  ```

**`forced_parameters`**: Parameters that are set to fixed values without user modification.

- **Type**: Object with parameter names as keys
- **Structure**: Each parameter must have:
  - `New Value`: The value to set (number or string)
  - `Change Reason`: Explanation of why this value is forced
- **Purpose**: Enforces critical parameter values that should not be changed by users
- **Example**:

  ```json
  "forced_parameters": {
    "INS_TCAL1_ENABLE": {
      "New Value": 2,
      "Change Reason": "Activates the temperature calibration for IMU 1 at the next start"
    },
    "LOG_DISARMED": {
      "New Value": 1,
      "Change Reason": "Gather data for offline IMU temperature calibration while the FC is disarmed"
    }
  }
  ```

**`derived_parameters`**: Parameters whose values are calculated based on other data (component specifications, expressions, etc.).

- **Type**: Object with parameter names as keys
- **Structure**: Each parameter must have:
  - `New Value`: An expression or formula to calculate the value (as a string)
  - `Change Reason`: Explanation of the derivation
- **Purpose**: Automatically calculates parameter values based on vehicle components or complex logic
- **Example**:

  ```json
  "derived_parameters": {
    "INS_TCAL2_ENABLE": {
      "New Value": "2",
      "Change Reason": "Activates the temperature calibration for IMU 2 at the next start"
    },
    "BRD_HEAT_TARG": {
      "New Value": "65",
      "Change Reason": "Reasonable for most places on this planet"
    },
    "BATT_CAPACITY": {
      "New Value": "vehicle_components['Battery']['Specifications']['Capacity mAh']",
      "Change Reason": "Total battery capacity specified in the component editor"
    },
    "ATC_ACCEL_P_MAX": {
      "New Value": "max(10000,(round(-2.613267*vehicle_components['Propellers']['Specifications']['Diameter_inches']**3+343.39216*vehicle_components['Propellers']['Specifications']['Diameter_inches']**2-15083.7121*vehicle_components['Propellers']['Specifications']['Diameter_inches']+235771, -2)))",
      "Change Reason": "Derived from vehicle component editor propeller size"
    }
  }
  ```

- **New Value** expressions can access:
  - Component specifications: `vehicle_components['Battery']['Specifications']['Capacity mAh']`
  - Flight controller parameters: `fc_parameters['PARAM_NAME']` or `fc_parameters.get('PARAM_NAME', default_value)`
  - Conditional logic: `if...else` expressions
  - Mathematical functions: `max()`, `min()`, `round()`, `log()`, conditional expressions with `if...else`

**`jump_possible`**: Allows users to skip ahead to another step under certain conditions.

- **Type**: Object with target step filenames as keys
- **Value**: Message explaining the skip condition
- **Purpose**: Provides optional shortcuts when a step can be skipped
- **Example**:

  ```json
  "jump_possible": {
    "04_board_orientation.param": "IMU temperature calibration reduces the number of possible 'Accel inconsistent' and 'Gyro inconsistent' errors.\nIMU temperature calibration is optional.\n\nDo you want to skip it?"
  }
  ```

**`old_filenames`**: List of previous filenames for this step (for migration purposes).

- **Type**: Array of strings
- **Purpose**: Tracks filename changes across versions for backward compatibility
- **Example**:

  ```json
  "old_filenames": ["11_mp_setup_mandatory_hardware.param"]
  ```

**`rename_connection`**: Expression to dynamically rename a connection based on component data.

- **Type**: String
- **Purpose**: Updates connection names based on selected components
- **Example**:

  ```json
  "rename_connection": "vehicle_components['RC Receiver']['FC Connection']['Type']"
  ```

**`download_file`**: Downloads a file from the internet to the local vehicle project directory.

- **Type**: Object
- **Required properties**:
  - `source_url`: URL to download from (must start with `https://`)
  - `dest_local`: Local filename to save as
- **Purpose**: Automatically fetches scripts or resources needed for this step
- **Example**:

  ```json
  "download_file": {
    "source_url": "https://raw.githubusercontent.com/ArduPilot/ardupilot/Copter-4.5/libraries/AP_Scripting/applets/VTOL-quicktune.lua",
    "dest_local": "VTOL-quicktune.lua"
  }
  ```

**`upload_file`**: Uploads a file from the vehicle project directory to the flight controller.

- **Type**: Object
- **Required properties**:
  - `source_local`: Local filename to upload
  - `dest_on_fc`: Destination path on flight controller (must start with `/APM/`)
- **Purpose**: Sends scripts or configuration files to the flight controller
- **Example**:

  ```json
  "upload_file": {
    "source_local": "VTOL-quicktune.lua",
    "dest_on_fc": "/APM/Scripts/VTOL-quicktune.lua"
  }
  ```

**`plugin`**: Loads a specialized plugin window for this step.

- **Type**: Object
- **Required properties**:
  - `name`: Plugin name (`"motor_test"` or `"battery_monitor"`)
  - `placement`: Where to display (`"left"` or `"top"`)
- **Purpose**: Provides specialized UI components for complex configuration tasks
- **Examples**:

  ```json
  "plugin": {
    "name": "motor_test",
    "placement": "left"
  }
  ```

  ```json
  "plugin": {
    "name": "battery_monitor",
    "placement": "left"
  }
  ```

**`instructions_popup`**: Displays a popup message when the user enters this step.

- **Type**: Object
- **Required properties**:
  - `type`: Dialog type (`"info"` or `"warning"`)
  - `msg`: The message to display
- **Purpose**: Provides important instructions or warnings to users
- **Examples**:

  ```json
  "instructions_popup": {
    "type": "info",
    "msg": "This step is optional, only perform it if your vehicle is tiny, huge, or its motor outputs oscillate"
  }
  ```

  ```json
  "instructions_popup": {
    "type": "warning",
    "msg": "Propeller size has a big influence on the vehicle dynamics. Ensure you have specified the correct propeller diameter in the component editor."
  }
  ```

#### Phases (Optional)

Phases group related steps into logical sections of the configuration workflow.

**Phase fields**:

- `description`: Required. Describes the purpose of this phase
- `optional`: Optional boolean. Whether the entire phase is optional
- `start`: Optional integer. The starting step number of this phase

**Example**:

```json
"phases": {
  "IMU temperature calibration": {
    "description": "Temperature calibration for accurate sensor readings",
    "start": 2
  },
  "Basic mandatory configuration": {
    "description": "Core vehicle configuration required for safe operation",
    "start": 4
  },
  "Optical flow calibration": {
    "description": "Optional advanced positioning",
    "optional": true,
    "start": 50
  }
}
```

#### Complete Examples

The vehicle-specific default configuration steps files can be used as example/inspiration:

- [configuration_steps_ArduCopter.json](https://github.com/ArduPilot/MethodicConfigurator/blob/master/ardupilot_methodic_configurator/configuration_steps_ArduCopter.json)
- [configuration_steps_ArduPlane.json](https://github.com/ArduPilot/MethodicConfigurator/blob/master/ardupilot_methodic_configurator/configuration_steps_ArduPlane.json)
- [configuration_steps_Heli.json](https://github.com/ArduPilot/MethodicConfigurator/blob/master/ardupilot_methodic_configurator/configuration_steps_Heli.json)
- [configuration_steps_Rover.json](https://github.com/ArduPilot/MethodicConfigurator/blob/master/ardupilot_methodic_configurator/configuration_steps_Rover.json)

## Vehicle Components File

The vehicle components file (`vehicle_components.json`) is a JSON file located in the vehicle-specific directory that stores comprehensive information
about all vehicle components and their configurations.
It serves as the central data source for component specifications, connections, and firmware versions used by the Methodic Configurator.

### Purpose and Use Cases

The vehicle components file is used to:

- **Store component specifications**: Motor poles, propeller sizes, battery capacity, voltage thresholds, etc.
- **Track component connectivity**: How components connect to the flight controller (UART, I2C, SPI, etc.)
- **Maintain component metadata**: Manufacturer, model, firmware versions, URLs, and notes
- **Enable dynamic parameter derivation**: Configuration steps can automatically calculate parameter values based on component specifications
- **Provide component validation**: Validate that components are compatible with the flight controller and configured correctly
- **Preserve vehicle configuration history**: Keep track of all components used in the vehicle throughout its lifecycle

### File Structure and Schema

The vehicle components file follows a strict JSON schema defined in `vehicle_components_schema.json`.
It contains the following top-level properties:

```json
{
  "Format version": 1,
  "Program version": "x.x.x",
  "Configuration template": "Template Name",
  "Components": {
    "Flight Controller": { /* flight controller details */ },
    "Frame": { /* frame details */ },
    "Battery Monitor": { /* battery monitor details */ },
    "Battery": { /* battery details */ },
    "ESC": { /* ESC details */ },
    "Motors": { /* motor details */ },
    "Propellers": { /* propeller details */ },
    "RC Receiver": { /* RC receiver details */ },
    "RC Transmitter": { /* RC transmitter details */ },
    "Telemetry": { /* telemetry module details */ },
    "GNSS Receiver": { /* GNSS receiver details */ }
  }
}
```

### Component Properties

Each component can include the following properties:

#### Product Information

- **Manufacturer**: Company or brand name
- **Model**: Specific model number or name
- **URL**: Link to product page or datasheet
- **Version**: Hardware revision

#### Firmware Information (where applicable)

- **Type**: Firmware type (e.g., "ArduPilot", "BLHeli_32")
- **Version**: Firmware version number

#### Flight Controller Connection (for physically connected components)

- **Type**: Connection type (e.g., "UART1", "I2C1", "SPI", "CAN", "Analog")
- **Protocol**: Communication protocol (e.g., "MAVLink", "SBUS", "PPM", "CRSF")

#### Component-Specific Specifications

Each component type may have specialized specifications:

**Battery**:

- Chemistry (LiPo, Li-Ion, LiFe)
- Cell count (e.g., 4S means 4 cells in series)
- Capacity (mAh)
- Voltage thresholds (max per cell, arm threshold, low warning, critical, minimum)

**Motors**:

- Pole count (affects RPM calculations)

**Propellers**:

- Diameter (in inches, affects PID tuning calculations)

**Frame**:

- Minimum take-off weight (kg)
- Maximum take-off weight (kg)
- Frame class (Quad, Hexa, Octa, Plane, Rover, etc.)

#### Notes and Metadata

- **Notes**: Optional free-text field for additional information about the component

### Editing the Vehicle Components File

The vehicle components file can be edited in several ways:

#### 1. Using the GUI Component Editor

The recommended way for most users:

1. Open the ArduPilot Methodic Configurator
2. Load or create a vehicle configuration
3. Use the **Component Editor** window to view and modify all component information
4. Changes are saved to the vehicle's `vehicle_components.json` file

#### 2. Manual JSON Editing

For advanced users who want to edit directly:

1. Locate the vehicle-specific `vehicle_components.json` file
2. Edit with any JSON-compatible text editor ([VS Code](https://code.visualstudio.com/), [Notepad++](https://notepad-plus-plus.org/), [nano](https://www.nano-editor.org/))
3. Ensure the JSON remains valid
4. Validate against the schema before using in the application

### Deriving Parameters from Components

One of the key features of the vehicle components file is the ability to derive flight controller parameters automatically based on component specifications.
In the `configuration_steps_*.json` file, you can reference component data:

```json
"derived_parameters": {
  "BATT_CAPACITY": {
    "New Value": "vehicle_components['Battery']['Specifications']['Capacity mAh']",
    "Change Reason": "Total battery capacity from component editor"
  },
  "ATC_ACCEL_P_MAX": {
    "New Value": "max(10000,(round(-2.613267*vehicle_components['Propellers']['Specifications']['Diameter_inches']**3+343.39216*vehicle_components['Propellers']['Specifications']['Diameter_inches']**2-15083.7121*vehicle_components['Propellers']['Specifications']['Diameter_inches']+235771, -2)))",
    "Change Reason": "Derived from propeller size specifications"
  }
}
```

### Validation and Compatibility Checks

The application validates the vehicle components file to ensure:

- All required components are present (Flight Controller, Frame, Battery, ESC, Motors)
- Component connections are valid for the selected flight controller
- Battery specifications are within safe limits
- Component specifications are logically consistent

If validation errors are found, the application displays clear error messages indicating which components or properties need correction.

## Vehicle Image File

The vehicle image file (`vehicle.jpg`) is an optional photograph or diagram stored in the vehicle-specific directory that provides
a visual reference of the vehicle during configuration.

### File Format and Location

- **Format**: JPEG image file (`.jpg` extension)
- **Location**: Vehicle-specific directory (same level as `vehicle_components.json`, `.param` files, and configuration steps)

### Guidelines for Vehicle Images

When creating or providing a vehicle image:

- **Clarity**: Clear, well-lit photograph without shadows obscuring details
- **Size**: Reasonable file size (typically 200-500 KB) for responsive GUI performance
- **Subject**: Include the complete vehicle or key components being configured
- **Angle**: Position that best shows the vehicle's physical layout and component locations

### Creating or Updating the Vehicle Image

1. **Take a photograph**: Use a camera or smartphone to capture the vehicle
2. **Process the image**: Crop to show the vehicle clearly, adjust lighting if needed
3. **Convert to JPEG** (if not already): Use image editing software to save as `.jpg` format with at most 400x400 pixels
4. **Place in vehicle directory**: Copy to the same directory as `vehicle_components.json`
5. **Name consistently**: Ensure the filename is exactly `vehicle.jpg` for the application to locate it automatically

### Image Not Found Handling

If `vehicle.jpg` is missing:

- The application displays a placeholder or blank area where the image would appear
- Configuration functionality is not affected
- Users can add the image later by copying it to the vehicle directory
