# Plugin Architecture

This document describes the plugin architecture of the ArduPilot Methodic Configurator,
which allows extending the application with modular components for UI enhancements and workflow automation.

## Overview

The plugin system enables developers to add new functionality to the application without modifying the core codebase.
There are two types of plugins:

1. **UI Plugins**: Provide persistent user interface components (e.g., motor test panels)
2. **Workflow Plugins**: Execute triggered actions (e.g., IMU temperature calibration workflows)

## Architecture Principles

### Separation of Concerns

- **Business Logic**: Encapsulated in data models with no UI dependencies
- **UI Coordination**: Handled by coordinators that orchestrate user interactions
- **Dependency Injection**: UI callbacks injected into business logic for testability

### Plugin Lifecycle

- **Registration**: Plugins register themselves with factories during application startup
- **Discovery**: The system discovers available plugins through factory queries
- **Instantiation**: Plugins are created on-demand with appropriate context
- **Execution**: UI plugins remain active; workflow plugins execute once and complete

## UI Plugin System

### UI Components

#### Plugin Factory UI (`plugin_factory_ui.py`)

- Manages registration and creation of UI plugins
- Provides a registry of plugin creators
- Ensures unique plugin names

#### Plugin Constants (`plugin_constants.py`)

- Defines string constants for plugin identifiers
- Centralizes plugin naming for consistency

#### Registration (`__main__.py`)

- Plugins register their creators during application initialization
- Ensures plugins are available when needed

### UI Implementation Pattern

```python
# 1. Define plugin constant
PLUGIN_MOTOR_TEST = "motor_test"

# 2. Create plugin view class
class MotorTestView:
    def __init__(self, parent, model, base_window):
        # Implementation

# 3. Create factory function
def create_motor_test_view(parent, model, base_window):
    return MotorTestView(parent, model, base_window)

# 4. Register plugin
plugin_factory_ui.register(PLUGIN_MOTOR_TEST, create_motor_test_view)
```

### UI usage in Parameter Editor

- UI plugins are instantiated when a parameter file with plugin configuration is selected
- Plugins receive parent frame, data model, and base window references
- Plugins manage their own lifecycle and cleanup

## Workflow Plugin System

### Workflow Components

#### Plugin Factory Workflow (`plugin_factory_workflow.py`)

- Manages registration and creation of workflow plugins
- Symmetric API to UI plugin factory
- Handles one-time execution workflows

#### Data Models

- Contain business logic with no UI dependencies
- Use dependency injection for user interactions
- Implement callback-based interfaces for testability

#### Workflow Coordinators

- Handle UI orchestration for workflows
- Manage progress indicators and user feedback
- Ensure proper cleanup after execution

### Workflow Implementation Pattern

```python
# 1. Define plugin constant
PLUGIN_TEMPCAL_IMU = "tempcal_imu"

# 2. Create data model class
class TempCalIMUDataModel:
    def __init__(self, config_manager, step_filename, callbacks...):
        # Business logic only

    def run_calibration(self) -> bool:
        # Orchestrate workflow using injected callbacks

# 3. Create workflow coordinator class
class TempCalIMUWorkflow:
    def __init__(self, root_window, data_model):
        # UI coordination

    def run_workflow(self) -> bool:
        # Execute workflow with UI feedback

# 4. Create factory function
def create_tempcal_imu_workflow(root_window, data_model):
    return TempCalIMUWorkflow(root_window, data_model)

# 5. Register plugin
plugin_factory_workflow.register(PLUGIN_TEMPCAL_IMU, create_tempcal_imu_workflow)
```

### Workflow usage in Parameter Editor

- Workflow plugins are triggered when specific parameter files are selected
- Configuration manager creates data models with injected UI callbacks
- Workflow coordinators handle execution and provide user feedback
- Cleanup ensures resources are released after completion

## Configuration Integration

### JSON Schema Updates

The configuration schema supports plugin definitions:

```json
{
  "plugin": {
    "name": "tempcal_imu",
    "placement": "workflow"
  }
}
```

### Supported Placements

- `"left"`: Plugin appears left of scrollable content
- `"top"`: Plugin appears above content
- `"workflow"`: Plugin executes as a triggered workflow

## Testing Strategy

### Unit Testing

- Business logic tested in isolation with mocked callbacks
- Plugin factories tested for registration and creation
- Data models tested for all execution paths

### Integration Testing

- End-to-end plugin execution workflows
- UI interaction verification
- Configuration loading and plugin discovery

## Implementation Notes

### Error Handling

- Plugin loading failures don't prevent application startup
- Individual plugin errors are logged and isolated
- Graceful degradation when plugins are unavailable

### Performance Considerations

- Lazy loading prevents startup delays
- Plugin instantiation on-demand reduces memory usage
- Callback-based design minimizes coupling overhead
