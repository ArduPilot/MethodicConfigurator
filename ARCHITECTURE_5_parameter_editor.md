# Parameter Editor and Uploader Sub-Application Architecture

## Overview

The Parameter Editor and Uploader sub-application is the core of the ArduPilot Methodic Configurator.
It provides sequential configuration through intermediate parameter files, allowing users to view
documentation, edit parameters, upload them to the flight controller, and save them to files.
This systematic approach ensures methodical, traceable, and safe vehicle configuration.

## Requirements

### Functional Requirements

1. **Sequential Configuration Management**
   - Must present configuration steps in a logical, numbered sequence
   - Must advance through intermediate parameter files systematically
   - Must track configuration progress and completion status
   - Must allow skipping steps that don't apply to specific vehicles
   - Must support jumping to specific configuration steps when needed

2. **Parameter File Operations**
   - Must load and parse intermediate parameter files (.param format)
   - Must preserve comments and formatting in parameter files
   - Must validate parameter syntax and structure
   - Must support parameter file editing and modification
   - Must save changes back to parameter files with proper formatting

3. **Parameter Table Management**
   - Must display parameters in an editable table format
   - Must show current values, new values, units, and change reasons
   - Must support parameter addition and deletion
   - Must provide upload selection for individual parameters
   - Must highlight different parameter types (read-only, calibration, etc.)

4. **Documentation Integration**
   - Must display relevant documentation for each configuration step
   - Must provide links to blog posts, wiki pages, and external tools
   - Must show parameter-specific documentation and tooltips
   - Must support automatic documentation opening in simple mode
   - Must handle offline operation when documentation is cached

5. **Flight Controller Integration**
   - Must upload selected parameters to flight controller
   - Must verify successful parameter upload
   - Must handle flight controller resets when required
   - Must re-download and validate parameter values after upload
   - Must support retry mechanisms for failed uploads

6. **Progress Tracking**
   - Must display overall configuration progress
   - Must show completion status for each configuration phase
   - Must provide visual indicators for mandatory vs. optional steps
   - Must track which steps have been completed successfully
   - Must support configuration resumption from any point

7. **Validation and Safety**
   - Must validate parameter values against acceptable ranges
   - Must warn about potentially dangerous parameter combinations
   - Must prevent upload of invalid or out-of-range values
   - Must provide safety checks for critical parameters
   - Must support parameter rollback capabilities

8. **Summary and Reporting**
   - Must generate comprehensive configuration summary at completion
   - Must categorize parameters by type (default, calibration, etc.)
   - Must create summary files for different parameter categories
   - Must provide configuration backup and archival
   - Must support configuration comparison and analysis

### Non-Functional Requirements

1. **Performance**
   - Parameter table should handle 1000+ parameters efficiently
   - Real-time validation should not cause UI lag
   - File operations should be fast and responsive
   - Documentation loading should not block the interface

2. **Usability**
   - Interface should be intuitive for users at all skill levels
   - Parameter editing should provide immediate feedback
   - Error messages should be clear and actionable
   - Progress indication should be accurate and informative

3. **Reliability**
   - Parameter uploads must be atomic and verifiable
   - Configuration state must be preserved across sessions
   - File operations must maintain data integrity
   - Recovery mechanisms must handle unexpected failures

4. **Scalability**
   - Must support different vehicle types and configurations
   - Must handle varying numbers of configuration steps
   - Must adapt to different parameter set sizes
   - Must support multiple simultaneous vehicle configurations

## Architecture

### Components

#### Main Parameter Editor

- **File**: `frontend_tkinter_parameter_editor.py`
- **Purpose**: Primary interface coordinating all parameter editor functionality
- **Responsibilities**:
  - Orchestrate the overall parameter editing workflow
  - Manage configuration step progression
  - Handle user interface layout and navigation
  - Coordinate between documentation, table, and progress components
  - Manage application state and configuration persistence

#### Documentation Frame

- **File**: `frontend_tkinter_parameter_editor_documentation_frame.py`
- **Purpose**: Display and manage configuration step documentation
- **Responsibilities**:
  - Render documentation for current configuration step
  - Handle links to external documentation sources
  - Manage automatic documentation opening in simple mode
  - Display mandatory level and step-specific information
  - Handle documentation caching and offline operation

#### Parameter Table Editor

- **File**: `frontend_tkinter_parameter_editor_table.py`
- **Purpose**: Interactive table for parameter viewing and editing
- **Responsibilities**:
  - Display parameters in sortable, filterable table
  - Handle parameter value editing with validation
  - Manage parameter selection for upload
  - Provide parameter-specific tooltips and help
  - Handle parameter addition and deletion operations

#### Stage Progress Tracker

- **File**: `frontend_tkinter_stage_progress.py`
- **Purpose**: Visual progress tracking for configuration stages
- **Responsibilities**:
  - Display overall configuration progress
  - Show completion status for each phase
  - Indicate mandatory vs. optional steps
  - Provide visual feedback for current step
  - Handle progress state persistence

#### Configuration Steps Backend

- **File**: `backend_filesystem_configuration_steps.py`
- **Purpose**: Manage configuration step definitions and metadata
- **Responsibilities**:
  - Load configuration step definitions from JSON
  - Validate step sequences and dependencies
  - Handle step-specific documentation metadata
  - Manage step categorization and grouping
  - Support multiple vehicle type configurations

#### Parameter File Backend

- **File**: `backend_filesystem.py`
- **Purpose**: Handle parameter file operations and management
- **Responsibilities**:
  - Load and parse parameter files
  - Preserve comments and formatting
  - Validate parameter file syntax
  - Handle file backup and versioning
  - Support batch parameter operations

### Data Flow

1. **Initialization**
   - Load vehicle directory and configuration
   - Initialize configuration steps for vehicle type
   - Load current parameter values from flight controller
   - Set up progress tracking and state management

2. **Step Processing**
   - Load current intermediate parameter file
   - Display relevant documentation
   - Present parameters in editable table
   - Allow user modifications and validation
   - Enable parameter selection for upload

3. **Parameter Upload**
   - Validate selected parameters
   - Upload parameters to flight controller
   - Handle required flight controller resets
   - Verify parameter upload success
   - Update progress and advance to next step

4. **Completion**
   - Generate comprehensive summary
   - Create categorized parameter files
   - Archive configuration for future reference
   - Provide completion report and next steps

### Integration Points

- **Flight Controller Communication**: Provides parameter upload/download capabilities
- **Component Editor**: Receives vehicle-specific component configuration
- **Directory Selection**: Works within selected vehicle directory
- **Documentation System**: Integrates with online and cached documentation

### Parameter Management System

#### Parameter Types

The system recognizes and handles different parameter categories:

- **Default Parameters**: Parameters at their default values (light blue background)
- **Read-Only Parameters**: System parameters that cannot be modified (red background)
- **Calibration Parameters**: Vehicle-specific sensor calibrations (yellow background)
- **Configuration Parameters**: User-configurable operational parameters
- **Safety Parameters**: Critical parameters affecting vehicle safety

#### Parameter Validation

- **Range Checking**: Validate parameters against min/max bounds
- **Type Validation**: Ensure correct data types (integer, float, etc.)
- **Dependency Checking**: Validate parameter interdependencies
- **Safety Validation**: Check for potentially dangerous combinations
- **Format Validation**: Ensure proper parameter naming and format

#### Upload Process

1. **Pre-Upload Validation**: Check all selected parameters
2. **Batch Upload**: Send parameters to flight controller efficiently
3. **Reset Handling**: Automatically reset FC when required parameters change
4. **Post-Upload Verification**: Download and verify all uploaded parameters
5. **Retry Logic**: Handle failed uploads with appropriate retry mechanisms

### Documentation System

#### Documentation Types

- **Blog Posts**: ArduPilot forum methodic configuration posts
- **Wiki Pages**: Official ArduPilot documentation
- **External Tools**: Links to relevant external tools and calculators
- **Parameter Documentation**: Detailed parameter descriptions and usage

#### Documentation Management

- **Automatic Opening**: Simple mode opens all relevant documentation
- **Contextual Help**: Parameter-specific tooltips and help text
- **Offline Support**: Cached documentation for offline operation
- **Version Compatibility**: Documentation matched to firmware version

### Progress Tracking System

#### Configuration Phases

The system organizes configuration into logical phases:

1. **Initial Setup**: Basic vehicle configuration
2. **Hardware Configuration**: Component-specific settings
3. **Safety Configuration**: Failsafe and safety systems
4. **Tuning Configuration**: Performance optimization
5. **Advanced Configuration**: Optional advanced features

#### Progress Visualization

- **Phase Completion**: Visual indicators for each phase
- **Step Progress**: Individual step completion tracking
- **Mandatory Indicators**: Clear marking of required vs. optional steps
- **Current Position**: Highlighting of current configuration step

### Error Handling Strategy

- **Parameter Errors**: Detailed validation messages with correction guidance
- **Upload Errors**: Retry logic with exponential backoff and user notification
- **File Errors**: Graceful handling with backup and recovery options
- **Documentation Errors**: Fallback to cached or alternative sources

### Testing Strategy

- Unit tests for parameter validation logic
- Integration tests for upload/download workflows
- UI tests for table editing and navigation
- File system tests for parameter file operations
- End-to-end tests for complete configuration workflows

## File Structure

```text
frontend_tkinter_parameter_editor.py                    # Main parameter editor
frontend_tkinter_parameter_editor_documentation_frame.py # Documentation display
frontend_tkinter_parameter_editor_table.py              # Parameter table editor
frontend_tkinter_stage_progress.py                      # Progress tracking
backend_filesystem_configuration_steps.py              # Step management
backend_filesystem.py                                   # Parameter file operations
```

## Dependencies

- **Python Standard Library**:
  - `tkinter` for GUI components
  - `json` for configuration file handling
  - `re` for parameter parsing
  - `webbrowser` for opening documentation links

- **Third-party Libraries**:
  - `tkinter.ttk` for enhanced table components
  - `tkinter.font` for text formatting

- **ArduPilot Methodic Configurator Modules**:
  - `backend_flightcontroller` for FC communication
  - `backend_filesystem` for file operations
  - `frontend_tkinter_base_window` for GUI base classes
  - `frontend_tkinter_rich_text` for documentation display

## Configuration File Management

### Intermediate Parameter Files

Parameter files follow a specific naming convention:

- `##_descriptive_name.param` (e.g., `01_initial_setup.param`)
- Files are processed in numerical order
- Each file contains parameters for a specific configuration aspect
- Comments provide documentation and rationale for parameter choices

### Summary Files

At completion, the system generates several summary files:

- `complete.param`: All parameters with change reasons
- `non-default_read-only.param`: Read-only parameters that differ from defaults
- `non-default_writable_calibrations.param`: Vehicle-specific calibrations
- `non-default_writable_non-calibrations.param`: Reusable configuration parameters

### Configuration Steps Definition

Configuration steps are defined in JSON files:

- `configuration_steps_ArduCopter.json`
- `configuration_steps_ArduPlane.json`
- etc.

Each step definition includes:

- Step number and name
- Documentation links
- Mandatory level (0-100%)
- Associated parameter file
- Dependencies and prerequisites

## Performance Optimization

### Table Performance

- Virtual scrolling for large parameter sets
- Lazy loading of parameter documentation
- Efficient filtering and sorting algorithms
- Optimized redraw operations

### File Operations

- Asynchronous file loading
- Incremental parsing for large files
- Efficient backup and versioning
- Batch operations where possible

### Memory Management

- Efficient parameter storage
- Cleanup of unused resources
- Optimized GUI component lifecycle
- Memory-conscious documentation caching

## Security Considerations

- Parameter validation to prevent dangerous values
- Safe handling of file operations
- Protection against malformed parameter files
- Secure documentation link handling
- Validation of flight controller responses
