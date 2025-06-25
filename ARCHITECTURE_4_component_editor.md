# Vehicle Component Editor Sub-Application Architecture

## Overview

The Vehicle Component Editor sub-application defines specifications of all vehicle components and their
connections to the flight controller. This critical component ensures that the parameter configuration
is tailored to the specific hardware setup of each vehicle, providing a foundation for accurate and
safe vehicle configuration.

## Requirements

### Functional Requirements

1. **Component Definition Management**
   - Must allow specification of all vehicle components (FC, ESC, motors, propellers, etc.)
   - Must define connections between components and flight controller pins/ports
   - Must validate component compatibility and connections
   - Must support component property editing with appropriate input validation
   - Must handle both required and optional component properties

2. **Component Template System**
   - Must provide pre-defined component templates for common hardware
   - Must allow users to save custom component configurations as templates
   - Must support template loading and modification
   - Must organize templates by component type and manufacturer
   - Must provide template search and filtering capabilities

3. **Connection Validation**
   - Must validate physical connections between components
   - Must check for pin conflicts and invalid assignments
   - Must verify power requirements and compatibility
   - Must validate communication protocol compatibility
   - Must detect and warn about potentially dangerous configurations

4. **Schema Validation**
   - Must enforce JSON schema compliance for all component data
   - Must provide meaningful error messages for validation failures
   - Must support schema versioning and migration
   - Must validate data types and value ranges
   - Must ensure required fields are populated

5. **User Interface Complexity Management**
   - Must support "simple" mode for beginners with reduced complexity
   - Must support "normal" mode for advanced users with full functionality
   - Must dynamically show/hide components based on relevance
   - Must provide appropriate defaults for common configurations
   - Must guide users through the configuration process

6. **Data Persistence**
   - Must save component configurations to vehicle_components.json
   - Must load existing configurations reliably
   - Must backup configurations before modifications
   - Must support configuration import/export
   - Must maintain configuration history for rollback

### Non-Functional Requirements

1. **Usability**
   - Interface must be intuitive for users with varying technical expertise
   - Component selection should be guided with clear descriptions
   - Validation errors must be clearly communicated
   - Configuration changes should provide immediate feedback

2. **Data Integrity**
   - All component data must be validated before saving
   - Configuration files must maintain consistency
   - Schema compliance must be enforced at all times
   - Backup and recovery mechanisms must be reliable

3. **Performance**
   - Component editor should load quickly even with many templates
   - Real-time validation should not cause UI lag
   - Large component libraries should be handled efficiently
   - Memory usage should be optimized for embedded systems

4. **Extensibility**
   - New component types should be easily addable
   - Template system should support third-party extensions
   - Schema should be versionable and upgradeable
   - Component properties should be dynamically configurable

## Architecture

### Components

#### Main Component Editor

- **File**: `frontend_tkinter_component_editor.py`
- **Purpose**: Primary user interface for component configuration
- **Responsibilities**:
  - Present component editing interface
  - Handle user input validation and feedback
  - Manage component template selection
  - Coordinate with backend validation systems
  - Handle GUI complexity mode switching

#### Component Editor Base Classes

- **File**: `frontend_tkinter_component_editor_base.py`
- **Purpose**: Base classes and common functionality for component editing
- **Responsibilities**:
  - Provide reusable GUI components
  - Handle common validation logic
  - Manage component property widgets
  - Support dynamic form generation

#### Component Template Manager

- **File**: `frontend_tkinter_component_template_manager.py`
- **Purpose**: Template management interface and operations
- **Responsibilities**:
  - Template loading and saving operations
  - Template library management
  - Template search and filtering
  - Template import/export functionality

#### Vehicle Components Data Model

- **File**: `data_model_vehicle_components.py`
- **Purpose**: Core data model for vehicle components
- **Responsibilities**:
  - Component data structure definition
  - Business logic for component operations
  - Integration with other data models
  - High-level validation orchestration

#### Base Vehicle Components Model

- **File**: `data_model_vehicle_components_base.py`
- **Purpose**: Base classes and common functionality
- **Responsibilities**:
  - Common component properties and methods
  - Base validation rules
  - Shared utility functions
  - Component type definitions

#### Component Import Handler

- **File**: `data_model_vehicle_components_import.py`
- **Purpose**: Handle importing component configurations
- **Responsibilities**:
  - Parse external component definitions
  - Convert between different configuration formats
  - Handle migration of legacy configurations
  - Validate imported data integrity

#### Component Template Data Model

- **File**: `data_model_vehicle_components_templates.py`
- **Purpose**: Template system data model
- **Responsibilities**:
  - Template data structure management
  - Template versioning and compatibility
  - Template library organization
  - Template inheritance and customization

#### Component Validation Engine

- **File**: `data_model_vehicle_components_validation.py`
- **Purpose**: Comprehensive validation system for components
- **Responsibilities**:
  - Schema validation enforcement
  - Cross-component compatibility checking
  - Connection validation logic
  - Safety constraint verification

#### Battery Cell Voltage Calculator

- **File**: `battery_cell_voltages.py`
- **Purpose**: Battery-specific calculations and validation
- **Responsibilities**:
  - Cell voltage calculations
  - Battery safety parameter validation
  - Capacity and discharge rate checking
  - Battery compatibility verification

### Data Flow

1. **Initialization**
   - Load existing vehicle_components.json if present
   - Initialize component templates library
   - Validate loaded configuration against schema
   - Set up UI based on complexity mode

2. **Component Configuration**
   - User selects component types and properties
   - Real-time validation provides immediate feedback
   - Template system offers pre-configured options
   - Connection validation ensures proper wiring

3. **Template Operations**
   - Users can load templates for quick configuration
   - Custom configurations can be saved as new templates
   - Template library provides organized access to options
   - Template compatibility checking prevents issues

4. **Validation and Saving**
   - Comprehensive validation before saving
   - Schema compliance verification
   - Cross-component compatibility checking
   - Configuration backup and persistence

### Integration Points

- **Directory Selection**: Receives vehicle directory path
- **Parameter Editor**: Provides component-specific parameter defaults
- **Template System**: Integrates with vehicle template selection
- **File System Backend**: Handles configuration file operations

### Component Types Supported

#### Required Components

- **Flight Controller**: Board type, processor, capabilities
- **Frame**: Type, size, material, motor mount configuration
- **Battery Monitor**: Voltage/current sensing configuration
- **Battery**: Cell count, capacity, chemistry, discharge rating
- **ESC**: Type, protocol, telemetry capabilities
- **Motors**: KV rating, size, mounting configuration

#### Optional Components

- **RC Controller**: Transmitter type and configuration
- **RC Receiver**: Protocol, channel count, failsafe settings
- **Telemetry**: Radio type, frequency, range requirements
- **Propellers**: Size, pitch, material, balance requirements
- **GNSS Receiver**: Type, antenna configuration, precision level

### Validation System

#### Schema Validation

- JSON schema enforcement for all component data
- Type checking for all properties
- Range validation for numeric values
- Required field verification
- Format validation for strings and identifiers

#### Cross-Component Validation

- Physical connection compatibility
- Power requirement verification
- Communication protocol matching
- Safety constraint checking
- Performance optimization suggestions

#### Safety Validation

- Critical safety parameter verification
- Dangerous configuration detection
- Warning system for potentially unsafe setups
- Mandatory safety feature enforcement

### Error Handling Strategy

- **Schema Errors**: Detailed field-level error messages with correction suggestions
- **Validation Errors**: Context-sensitive warnings and errors with explanations
- **Template Errors**: Graceful handling of corrupted or incompatible templates
- **File Errors**: Clear guidance for file access and permission issues

### Testing Strategy

- Unit tests for all validation logic
- Integration tests for template system
- UI tests for component editor workflow
- Schema validation tests with edge cases
- Cross-platform compatibility testing

## File Structure

```text
frontend_tkinter_component_editor.py           # Main component editor GUI
frontend_tkinter_component_editor_base.py      # Base classes for editor
frontend_tkinter_component_template_manager.py # Template management GUI
data_model_vehicle_components.py               # Core component data model
data_model_vehicle_components_base.py          # Base component classes
data_model_vehicle_components_import.py        # Import handling
data_model_vehicle_components_templates.py     # Template data model
data_model_vehicle_components_validation.py    # Validation engine
battery_cell_voltages.py                       # Battery calculations
```

## Dependencies

- **Python Standard Library**:
  - `json` for configuration file handling
  - `tkinter` for GUI components
  - `pathlib` for file operations
  - `typing` for type hints

- **Third-party Libraries**:
  - `jsonschema` for schema validation
  - `tkinter.ttk` for enhanced GUI widgets

- **ArduPilot Methodic Configurator Modules**:
  - `backend_filesystem_vehicle_components` for file operations
  - `frontend_tkinter_base_window` for GUI base classes
  - `frontend_tkinter_autoresize_combobox` for adaptive UI
  - `frontend_tkinter_pair_tuple_combobox` for specialized inputs

## Component Template System

### Template Organization

Templates are organized hierarchically:

- **Manufacturer**: Group by component manufacturer
- **Component Type**: Organize by component category
- **Model Series**: Group related models together
- **Compatibility**: Filter by ArduPilot version compatibility

### Template Features

- **Inheritance**: Templates can inherit from base templates
- **Customization**: Users can modify templates before applying
- **Versioning**: Templates support version tracking and updates
- **Sharing**: Templates can be exported and shared between users

### Template Validation

- Schema compliance checking for all templates
- Compatibility verification with current ArduPilot versions
- Safety constraint validation
- Performance optimization recommendations

## User Experience Features

### Guided Configuration

- Step-by-step component configuration wizard
- Context-sensitive help and documentation
- Visual connection diagrams and pin mapping
- Real-time validation feedback

### Complexity Management

- **Simple Mode**: Shows only essential components and properties
- **Normal Mode**: Exposes all configuration options
- **Expert Mode**: Provides advanced validation and optimization tools

### Error Prevention

- Proactive validation to prevent configuration errors
- Safety warnings for potentially dangerous setups
- Compatibility checking between components
- Automatic correction suggestions where possible
