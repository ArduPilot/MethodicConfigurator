# ArduPilot Methodic Configurator Project Context

This is a Python GUI application for configuring ArduPilot flight controller parameters in a methodical, traceable way.

## Code Style and Standards

We follow PEP 8 Python style guidelines with strict linting using ruff, pylint, mypy, and pyright. All code must pass these checks before merging.

When writing code, use type hints for all function parameters and return values following PEP 484 standards.

## Testing Philosophy

We use pytest for testing with a behavior-driven development (BDD) approach. Tests should focus on user behavior and business value, not implementation details.

Test structure follows Given-When-Then pattern with descriptive names like `test_user_can_select_template_by_double_clicking`.

For detailed testing guidelines, see `.github/instructions/pytest_testing_instructions.md`.

## Architecture

The project uses a clean architecture with separation of concerns:

- Frontend: tkinter-based GUI
- Backend: Filesystem operations and parameter management
- Business logic: Configuration steps and vehicle templates

## Dependencies and Tools

We use uv for dependency management, not pip directly. Always update pyproject.toml when adding dependencies.

Pre-commit hooks ensure code quality - run `pre-commit install` after cloning.

## File Structure

Parameter files use `.param` extension and are numbered (e.g., `01_first_setup.param`).

Vehicle templates are organized in `ardupilot_methodic_configurator/vehicle_templates/` with subdirectories for each vehicle type
(ArduCopter, ArduPlane, Rover, Heli).

## Internationalization

The application supports multiple languages using gettext. All user-facing strings should be wrapped with `_()` for translation.

## Documentation

We maintain comprehensive documentation including
[user manuals](../USERMANUAL.md), [tuning guides](../TUNING_GUIDE_ArduCopter.md), and
[architecture](../ARCHITECTURE.md) documentation.
All changes should include appropriate documentation updates.

For specific workflows, see detailed instructions in `.github/instructions/`:

- [GUI Translation Instructions](instructions/gui_translation_instructions.md) - Complete guide for translating the user interface
- [Pytest Testing Guidelines](instructions/pytest_testing_instructions.md) - Comprehensive testing standards
