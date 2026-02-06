# ArduPilot Methodic Configurator Project Context

This is a Python GUI application for configuring ArduPilot flight controller parameters in a methodical, traceable way.

## Code Style and Standards

- Follow PEP 8 Python style guidelines with strict linting (ruff, pylint, mypy, pyright)
- Use type hints for all function parameters and return values (PEP 484)
- Use ruff only for Python files (*.py); use `npx markdownlint-cli2` for markdown files (*.md)
- All code must pass pre-commit checks before merging

## Testing

- Use pytest with behavior-driven development (BDD) approach
- Test structure: Given-When-Then pattern with descriptive names like `test_user_can_select_template_by_double_clicking`
- Focus on user behavior and business value, not implementation details

## Architecture

Clean architecture with separation of concerns:

- **Frontend**: tkinter-based GUI (inherit from `BaseWindow`, use `ScrollFrame` for scrollable areas)
- **Business logic**: Vehicle templates, configuration steps, parameter management
- **Backend**: Filesystem operations (`backend_filesystem.py`), flight controller communication (`backend_flightcontroller.py`)

## Dependencies and Tools

- **Dependency management**: Use `uv`, not `pip` directly. Update `pyproject.toml` and `credits/CREDITS.md` when adding dependencies
- **Pre-commit hooks**: Run `pre-commit install` after cloning

## Key File Conventions

- **Parameter files**: Use `.param` extension with numbered prefixes (e.g., `01_first_setup.param`)
- **Vehicle templates**: Located in `ardupilot_methodic_configurator/vehicle_templates/` with subdirectories for each vehicle type (ArduCopter, ArduPlane, Rover, Heli)
- **Internationalization**: Wrap all user-facing strings with `_()` for gettext translation

## Development Workflow

**Setup**: Run `SetupDeveloperPC.bat` (Windows) or `SetupDeveloperPC.sh` (Linux/macOS)

**Run app**: Activate `.venv` then `python -m ardupilot_methodic_configurator`

**Code quality**: `ruff format`, `ruff check --fix`, `mypy`, `pyright`, `pylint $(git ls-files '*.py')`

**Testing**: `pytest tests/ -v` or `pytest tests/ --cov=ardupilot_methodic_configurator`

## Common Patterns

- **Error Handling**: Use the project's logging system (5 verbosity levels); catch specific exceptions; provide user-friendly GUI messages
- **Parameter Management**: Validate parameter values before applying to flight controller
- **Backend Communication**: Use `backend_flightcontroller.py` facade; implement progress callbacks for long operations

## Security

- Never commit secrets or credentials
- Use SSL verification for network requests
- Validate all user inputs before processing

## Contributing

- All commits must be signed off (DCO requirements)
- Use Conventional Commits format for commit messages
- See CONTRIBUTING.md for full details

## Additional Documentation

When needed for specific tasks, refer to:

- Architecture details: ARCHITECTURE*.md files in project root
- Testing guidelines: .github/instructions/pytest_testing_instructions.md
- Translation workflow: .github/instructions/gui_translation_instructions.md
- Other specialized instructions: .github/instructions/ directory
