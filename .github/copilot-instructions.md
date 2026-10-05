# ArduPilot Methodic Configurator Project Context

This is a Python GUI application for configuring ArduPilot flight controller parameters in a methodical, traceable way.

## Code Style and Standards

- Follow PEP 8 Python style guidelines with strict linting (ruff, pylint, mypy, pyright)
- Use type hints for all function parameters and return values (PEP 484)
- Use ruff only for Python files (*.py); use `npx markdownlint-cli2` for markdown files (*.md)
- All code must pass pre-commit checks before merging

### Python file headers and test executability

New hand-written Python files must use the full project module-docstring header below.
Include the project identification and URL, blank lines, copyright notice and SPDX license identifier;
an SPDX-only header does not match the project format. Use the appropriate year and copyright holder,
and preserve existing notices when editing or moving files.

```python
"""
Brief description of this module.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: YYYY Copyright holder <email>

SPDX-License-Identifier: GPL-3.0-or-later
"""
```

New Python test modules anywhere under `tests/`, including `tests/plugins/`, must also:

- Start with `#!/usr/bin/env python3` as the very first line, immediately before the module docstring.
- Be executable and recorded in Git with mode `100755`. Preserve this mode when moving or replacing tests.
- Keep helper modules such as `conftest.py` and `__init__.py` without a shebang unless they are executable scripts.

On Linux/macOS, use `chmod +x` on each new test module before staging it.
On Windows, set the Git index mode explicitly; filesystem permissions and `core.filemode=false` do not establish it.
Use the exact file paths, for example:

```text
git add -- tests/test_example.py
git update-index --chmod=+x -- tests/test_example.py
git ls-files --stage -- tests/test_example.py
pre-commit run --files tests/test_example.py
```

Verify the first line and the staged `100755` mode before finishing.
The existing shebang/executable hooks check consistency, but a test lacking both can pass them;
REUSE checks SPDX coverage, not the complete project header format. Check all three requirements explicitly.

## Testing

- Use pytest with behavior-driven development (BDD) approach
- Test structure: Given-When-Then pattern with descriptive names like `test_user_can_select_template_by_double_clicking`
- Focus on user behavior and business value, not implementation details
- On Linux, use the repository's local .venv and xvfb-run when running tests, for example:

```bash
PATH="$PWD/.venv/bin:$PATH" xvfb-run -a python -m pytest -q tests/test_frontend_tkinter_parameter_export.py
```

## Architecture

Clean architecture with separation of concerns:

- **Frontend**: tkinter-based GUI (inherit from `BaseWindow`, use `ScrollFrame` for scrollable areas)
- **Business logic**: Vehicle templates, configuration steps, parameter management
- **Backend**: Filesystem operations (`backend_filesystem.py`), flight controller communication (`backend_flightcontroller.py`)

When reviewing code, always apply the repository guidelines in `/COMPLIANCE.md` and `/CONTRIBUTING.md`.
For changes affecting architecture, module boundaries, dependencies, data flow, generated files, or repository tooling such as repo graphing, also consult `/ARCHITECTURE.md`.

When adding or moving files, check their exact path against `REUSE.toml`; root-level globs such as `*.md` do not cover nested directories.
Add an SPDX header or a matching annotation for new files.

For modules loaded dynamically (including plugin registrations), check all three platform PyInstaller specs and ensure the package, submodules and required data are collected.
Static import checks alone do not verify frozen builds.

## Dependencies and Tools

- **Dependency management**: Use `uv`, not `pip` directly. Update `pyproject.toml` and `credits/CREDITS.md` when adding dependencies
- **Pre-commit hooks**: Run `pre-commit install` after cloning

## Key File Conventions

- **Parameter files**: Use `.param` extension with numbered prefixes (e.g., `01_first_setup.param`)
- **Vehicle templates**: Located in `ardupilot_methodic_configurator/vehicle_templates/` with subdirectories for each vehicle type (ArduCopter, ArduPlane, Rover, Heli)
- **Internationalization**: Wrap all user-facing strings with `_()` for gettext translation

## CodeGraph

- When .codegraph/ exists, use CodeGraph to understand or locate repository code when it is useful for the task.
  Prefer codegraph_explore (or codegraph explore in a shell) before text search or reading source files.
- sync the index when necessary.

## Development Workflow

**Setup**: Run `SetupDeveloperPC.bat` (Windows) or `SetupDeveloperPC.sh` (Linux/macOS)

**Run app**: Activate `.venv` then `python -m ardupilot_methodic_configurator`

**Code quality**: `ruff format`, `ruff check --fix`, `mypy`, `pyright`, `pylint $(git ls-files '*.py')`

**Testing**: `pytest tests/ -v` or `pytest tests/ --cov=ardupilot_methodic_configurator`

## Common Patterns

- **Error Handling**: Use the project's logging system (5 verbosity levels); catch specific exceptions; provide user-friendly GUI messages
- **Parameter Management**: Validate parameter values before applying to flight controller
- **Parameter edits**: Use `ArduPilotParameter.change_reason` for the editable reason;
  `change_reason_for_file` is the serialized form and may add markers such as `@manual_override`.
  Use the parameter APIs to preserve these markers without duplication.
- **Numeric GUI input**: Handle conversion failures and range failures separately, and show translated, stable guidance rather than raw Python exception text.
- **Firmware support**: Verify parameter groups and version availability for each vehicle type before wiring a plugin into its configuration steps.
  Cite upstream source with a stable tag or commit permalink in research documentation, and state the release that introduced the feature when it explains a version gate.
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
- Testing guidelines: .github/skills/pytest-testing/SKILL.md
- Translation workflow: .github/skills/update-gui-translations/SKILL.md
- Plugin creation: .github/skills/add-new-plugin/SKILL.md
- Other specialized skills: .github/skills/ directory
