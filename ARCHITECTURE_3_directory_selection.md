# Vehicle Configuration Directory Selection Sub-Application Architecture

## Overview

The Vehicle Configuration Directory Selection sub-application allows users to either create a new vehicle
configuration project or open an existing one. It manages the selection and creation of vehicle directories,
handles template selection, and downloads parameter documentation metadata corresponding to the flight
controller firmware version to the project directory.

## Requirements

### Functional Requirements

1. **Directory Management**
   - Must allow creation of new vehicle configuration directories
   - Must allow opening of existing vehicle configuration directories
   - Must provide re-open functionality for recently used directories
   - Must validate directory structure and required files
   - Must handle directory permissions and access rights

2. **Template System**
   - Must provide a comprehensive template overview interface
   - Must support multiple vehicle types (ArduCopter, ArduPlane, Rover, Heli, etc.)
   - Must allow template selection based on vehicle characteristics
   - Must copy template files to new vehicle directories
   - Must preserve template structure and file organization

3. **Vehicle Template Selection**
   - Must display available templates with descriptions
   - Must show template compatibility information
   - Must provide visual representation of template contents
   - Must allow filtering and searching of templates
   - Must support template comparison features

4. **Parameter Documentation Management**
   - Must download parameter documentation metadata for FC firmware version
   - Must store documentation files in the appropriate project directory
   - Must handle offline operation when documentation is already available
   - Must validate documentation file integrity
   - Must support multiple documentation formats

5. **Project Configuration**
   - Must initialize project configuration files
   - Must set up directory structure for parameter files
   - Must create necessary subdirectories and organize files
   - Must handle configuration file validation
   - Must support project metadata management

### Non-Functional Requirements

1. **Usability**
   - Directory selection should be intuitive and user-friendly
   - Template overview should provide clear visual guidance
   - File operations should provide clear progress feedback
   - Error messages should be actionable and informative

2. **Performance**
   - Directory operations should complete quickly
   - Template copying should handle large file sets efficiently
   - Documentation download should not block the user interface
   - Memory usage should be optimized for large template collections

3. **Reliability**
   - Must handle incomplete or corrupted templates gracefully
   - Must verify successful completion of all file operations
   - Must provide rollback capability for failed operations
   - Must maintain project integrity during all operations

4. **Compatibility**
   - Must support different operating system path conventions
   - Must handle various file system limitations
   - Must work with different permission systems
   - Must support unicode file names and paths

## Architecture

### Components

#### Directory Selection Interface

- **File**: `frontend_tkinter_directory_selection.py`
- **Purpose**: Main interface for vehicle directory selection and management
- **Responsibilities**:
  - Present directory selection options (New, Open, Re-open)
  - Handle directory creation and validation
  - Manage recent directory history
  - Integrate with template selection system

#### Template Overview Interface

- **File**: `frontend_tkinter_template_overview.py`
- **Purpose**: Visual interface for template browsing and selection
- **Responsibilities**:
  - Display available vehicle templates
  - Show template details and compatibility information
  - Handle template selection and preview
  - Provide template comparison features

#### Configuration Steps Backend

- **File**: `backend_filesystem_configuration_steps.py`
- **Purpose**: Manage configuration step definitions and documentation
- **Responsibilities**:
  - Load configuration step metadata
  - Validate configuration file structure
  - Handle configuration step documentation
  - Manage step sequencing and dependencies

#### Vehicle Components Backend

- **File**: `backend_filesystem_vehicle_components.py`
- **Purpose**: Handle vehicle component definitions and templates
- **Responsibilities**:
  - Load and validate vehicle component schemas
  - Manage component template libraries
  - Handle component compatibility checking
  - Support component customization

### Data Flow

1. **Application Start**
   - Load available templates from template directories
   - Scan for existing vehicle directories
   - Initialize recent directory history
   - Prepare template metadata

2. **New Project Creation**
   - User selects "New" option
   - Template overview interface displays available options
   - User selects appropriate template for their vehicle
   - User specifies destination directory and project name
   - Template files are copied to new directory
   - Project configuration is initialized

3. **Existing Project Opening**
   - User selects "Open" option
   - File browser allows directory selection
   - Directory structure is validated
   - Required files are checked for existence and integrity
   - Project configuration is loaded

4. **Documentation Download**
   - System determines required documentation based on FC firmware
   - Downloads parameter documentation if not already present
   - Validates downloaded documentation
   - Stores documentation in project directory

### Integration Points

- **Flight Controller Communication**: Receives firmware version information
- **Component Editor**: Provides project directory and configuration
- **Parameter Editor**: Supplies configuration steps and documentation
- **File System Backend**: Handles all file operations
- **Internet Backend**: Downloads documentation and templates

### Template Management

#### Template Structure

Templates are organized hierarchically by vehicle type:

```text
vehicle_templates/
├── ArduCopter/
│   ├── X-Quadcopter/
│   ├── Y6-Hexacopter/
│   └── Traditional-Helicopter/
├── ArduPlane/
│   ├── Fixed-Wing/
│   └── VTOL/
└── Rover/
    ├── 4WD/
    └── Boat/
```

#### Template Content

Each template contains:

- Parameter files (*.param) for configuration steps
- Vehicle component configuration (vehicle_components.json)
- Configuration step definitions
- Documentation and readme files
- Default parameter values

### Error Handling Strategy

- **Directory Access Errors**: Provide clear guidance for permission issues
- **Template Corruption**: Validate templates and provide recovery options
- **Network Errors**: Handle documentation download failures gracefully
- **File System Errors**: Provide detailed error information and recovery steps

### Testing Strategy

- Unit tests for directory validation logic
- Integration tests for template copying operations
- UI tests for template selection workflow
- File system tests across different operating systems
- Network simulation for documentation download testing

## File Structure

```text
frontend_tkinter_directory_selection.py     # Main directory selection GUI
frontend_tkinter_template_overview.py       # Template browsing interface
backend_filesystem_configuration_steps.py  # Configuration step management
backend_filesystem_vehicle_components.py   # Vehicle component handling
```

## Dependencies

- **Python Standard Library**:
  - `os` and `pathlib` for path operations
  - `shutil` for directory copying
  - `json` for configuration file handling
  - `tkinter` for GUI components

- **Third-party Libraries**:
  - `jsonschema` for configuration validation
  - `PIL` (Pillow) for image handling in templates

- **ArduPilot Methodic Configurator Modules**:
  - `backend_filesystem` for file operations
  - `backend_internet` for documentation downloads
  - `frontend_tkinter_base_window` for GUI base classes
  - `frontend_tkinter_scroll_frame` for scrollable interfaces

## Template System Features

### Template Categories

- **Vehicle Type Based**: Organized by ArduPilot vehicle type
- **Size Categories**: Small, medium, large vehicle templates
- **Application Specific**: Racing, photography, mapping, etc.
- **Hardware Specific**: Specific flight controller or component combinations

### Template Validation

- Schema validation for all template configuration files
- Parameter file syntax checking
- Dependency verification between configuration steps
- Compatibility checking with different firmware versions

### Template Customization

- User can modify templates after copying
- Support for local template libraries
- Template versioning and update mechanisms
- Template sharing and import/export functionality

## Performance Optimization

- Lazy loading of template metadata
- Efficient directory scanning algorithms
- Parallel file operations where safe
- Caching of frequently accessed templates
- Progress reporting for long operations
