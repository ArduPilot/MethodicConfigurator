# ArduPilot Methodic Configurator Project Context

This is a Python GUI application for configuring ArduPilot flight controller parameters in a methodical, traceable way.

## Code Style and Standards

We follow PEP 8 Python style guidelines with strict linting using ruff, pylint, mypy, and pyright.
All code must pass these checks before merging.

**Important**: Use ruff only for Python files (*.py).
For markdown files (*.md), use `npx markdownlint-cli2` or similar markdown-specific linting tools.

When writing code, use type hints for all function parameters and return values following PEP 484 standards.

## Testing Philosophy

We use pytest for testing with a behavior-driven development (BDD) approach.
Tests should focus on user behavior and business value, not implementation details.

Test structure follows Given-When-Then pattern with descriptive names like `test_user_can_select_template_by_double_clicking`.

For detailed testing guidelines, see `.github/instructions/pytest_testing_instructions.md`.

## Architecture

The project uses a clean architecture with separation of concerns:

- Frontend: tkinter-based GUI
- Business logic: vehicle templates, configuration steps and parameter management
- Backend: Filesystem operations, Flightcontroller integration and communication

For detailed architecture documentation, see:

- [ARCHITECTURE.md](../ARCHITECTURE.md) - Overall system architecture and V-model development
- [ARCHITECTURE_1_software_update.md](../ARCHITECTURE_1_software_update.md) - Software update sub-application
- [ARCHITECTURE_2_flight_controller_communication.md](../ARCHITECTURE_2_flight_controller_communication.md) - Flight controller communication
- [ARCHITECTURE_3_directory_selection.md](../ARCHITECTURE_3_directory_selection.md) - Directory selection
- [ARCHITECTURE_4_component_editor.md](../ARCHITECTURE_4_component_editor.md) - Component editor
- [ARCHITECTURE_5_parameter_editor.md](../ARCHITECTURE_5_parameter_editor.md) - Parameter editor
- [ARCHITECTURE_motor_test.md](../ARCHITECTURE_motor_test.md) - Motor test functionality
- [ARCHITECTURE_battery_monitor.md](../ARCHITECTURE_battery_monitor.md) - Battery monitoring

## Dependencies and Tools

We use uv for dependency management, not pip directly.
Always update `pyproject.toml` when adding dependencies.

Pre-commit hooks ensure code quality - run `pre-commit install` after cloning.

## File Structure

Parameter files use `.param` extension and are numbered (e.g., `01_first_setup.param`).

Vehicle templates are organized in `ardupilot_methodic_configurator/vehicle_templates/` with subdirectories
for each vehicle type (ArduCopter, ArduPlane, Rover, Heli).

## Internationalization

The application supports multiple languages using gettext.
All user-facing strings should be wrapped with `_()` for translation.

For translation workflow, see `.github/instructions/gui_translation_instructions.md`.

## Development Workflow

### Setting Up Development Environment

```bash
# Clone and setup (Windows)
.\SetupDeveloperPC.bat

# Clone and setup (Linux/macOS)
./SetupDeveloperPC.sh
```

### Running the Application

```bash
# Windows
.venv\Scripts\activate.ps1
python -m ardupilot_methodic_configurator

# Linux/macOS
source .venv/bin/activate
python3 -m ardupilot_methodic_configurator
```

### Code Quality Checks

Run these before committing:

```bash
# Format code
ruff format

# Lint Python files
ruff check --fix

# Type checking
mypy
pyright

# Style checking
pylint $(git ls-files '*.py')

# Lint markdown files
npx markdownlint-cli2 "**/*.md"

# Run all pre-commit hooks
pre-commit run --all-files
```

### Testing

```bash
# Run all tests
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=ardupilot_methodic_configurator --cov-report=html

# Run specific test file
pytest tests/test_frontend_tkinter_template_overview.py -v

# Run tests matching pattern
pytest tests/ -k "test_user" -v
```

## Common Patterns and Best Practices

### GUI Development with tkinter

- Inherit from `BaseWindow` for consistent window behavior
- Use `ScrollFrame` for scrollable content areas
- Mock tkinter components in tests using fixtures from `conftest.py`
- Follow the existing pattern for window initialization and layout

### Error Handling and Logging

- Use the project's logging system with appropriate verbosity levels (5 levels available)
- Catch specific exceptions rather than broad Exception catches
- Provide user-friendly error messages through the GUI

### Parameter Management

- Use `.param` files with numbered prefixes for sequential configuration
- Follow the existing parameter file format and naming conventions
- Validate parameter values before applying to flight controller

### Backend Communication

- Use `backend_flightcontroller.py` facade for flight controller operations
- Handle connection failures gracefully with appropriate user feedback
- Implement progress callbacks for long-running operations

## Specialized Instructions

For specific development tasks, refer to these detailed instruction files:

- **Testing**: `.github/instructions/pytest_testing_instructions.md` - Comprehensive pytest and BDD guidelines
- **Translations**: `.github/instructions/gui_translation_instructions.md` - GUI translation workflow
- **Architecture Validation**: `.github/instructions/architecture_validation_instructions.md` - Keeping architecture docs up-to-date
- **Codebase Analysis**: `.github/instructions/codebase_analysis_instructions.md` - Analyzing code structure and metrics
- **SITL Testing**: `.github/instructions/SITL_TESTING.md` - Software-in-the-loop testing procedures
- **Motor Diagrams**: `.github/instructions/update_motor_diagrams.md` - Updating motor configuration diagrams

## Security Considerations

- Never commit secrets or credentials
- Use SSL verification for network requests
- Validate all user inputs before processing
- Follow secure coding practices as outlined in [SECURITY.md](../SECURITY.md)

## Contributing Guidelines

Read [CONTRIBUTING.md](../CONTRIBUTING.md) for:

- Developer Certificate of Origin (DCO) requirements - all commits must be signed off
- Conventional Commits format for commit messages
- Code review process and criteria
- Pull request guidelines

## Project Documentation

Key documentation files:

- [README.md](../README.md) - Project overview and quick start
- [USERMANUAL.md](../USERMANUAL.md) - Comprehensive user manual
- [QUICKSTART.md](../QUICKSTART.md) - Quick start guide
- [SYSTEM_REQUIREMENTS.md](../SYSTEM_REQUIREMENTS.md) - System requirements
- [COMPLIANCE.md](../COMPLIANCE.md) - Compliance and coding standards
- [FAQ.md](../FAQ.md) - Frequently asked questions
- [ROADMAP.md](../ROADMAP.md) - Project roadmap and future plans
