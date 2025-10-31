# Compliance

ArduPilot Methodic Configurator adheres to multiple compliance standards and best practices:

## Usability

- [Wizard like interface](https://www.nngroup.com/articles/wizards/), allows user to concentrate in one task at a time
- All GUI elements contain [mouse over tooltips](https://www.nngroup.com/articles/tooltip-guidelines/) explaining their function
- Relevant documentation opens automatically in a browser window
- Uses *What you see is what gets changed* paradigm. No parameters are changed without the users's knowledge
- Translated into multiple languages
- No visible menus, no hidden menus.

## Coding Standards

- Follows object-oriented design principles and [clean code practices](https://www.oreilly.com/library/view/clean-code/9780136083238/)
  - [Backend, business logic, frontend (GUI) separation](ARCHITECTURE.md) for improved testability and maintainability
- Follows [PEP 8](https://peps.python.org/pep-0008/) Python code style guidelines
- Uses [PEP 484](https://peps.python.org/pep-0484/) [type hints](https://docs.python.org/3/library/typing.html)
  - Enforces type checking with [MyPy](https://www.mypy-lang.org/) and [pyright](https://microsoft.github.io/pyright/#/) type checkers
- Automated code formatting using [ruff](https://docs.astral.sh/ruff/) for consistency
- Implements [PEP 621](https://peps.python.org/pep-0621/) project metadata standards
- Adheres to [Keep a Changelog](https://keepachangelog.com/) format
- Complies with [Python Packaging Authority](https://www.pypa.io/) guidelines

## Code Quality

- Maintains high code quality through automated linting (static code analysis), all using strict settings:
  - [Pylint](https://www.pylint.org/) [automated workflow](https://github.com/ArduPilot/MethodicConfigurator/actions/workflows/pylint.yml),
  - [Ruff](https://docs.astral.sh/ruff/) [automated workflow](https://github.com/ArduPilot/MethodicConfigurator/actions/workflows/ruff.yml),
  - [mypy](https://www.mypy-lang.org/) [automated workflow](https://github.com/ArduPilot/MethodicConfigurator/actions/workflows/mypy.yml) and
  - [pyright](https://microsoft.github.io/pyright/#/) [automated workflow](https://github.com/ArduPilot/MethodicConfigurator/actions/workflows/pyright.yml)
- Implements comprehensive error handling and logging, with 5 verbosity levels
- Code and documentation are [spell checked](https://streetsidesoftware.com/vscode-spell-checker/)
  and [english grammar checked](https://app.grammarly.com/)
  - [markdown-lint](https://github.com/DavidAnson/markdownlint-cli2)
  [automated workflow](https://github.com/ArduPilot/MethodicConfigurator/actions/workflows/markdown-lint.yml) and
  - [markdown-link-check](https://github.com/tcort/markdown-link-check) [automated workflow](https://github.com/ArduPilot/MethodicConfigurator/actions/workflows/markdown-link-check.yml)

## Software Development

- Implements [continuous integration/continuous deployment](https://github.com/ArduPilot/MethodicConfigurator/actions) (CI/CD) practices
- Maintains comprehensive [assertion-based test coverage](https://coveralls.io/github/ArduPilot/MethodicConfigurator?branch=master) through [pytest](https://docs.pytest.org/en/stable/)
- Follows [Conventional Commits](https://www.conventionalcommits.org/en/v1.0.0/) and uses [semantic versioning](https://semver.org/) for releases
- Follows [git-flow branching model](https://www.gitkraken.com/learn/git/git-flow)
- Implements [git pre-commit hooks](https://pre-commit.com/) to ensure code quality and compliance on every commit
- Uses containerized CI/CD environments for consistency
- Uses [automated](https://github.com/ArduPilot/MethodicConfigurator/actions/workflows/windows_build.yml) [changelog generation](https://github.com/ArduPilot/MethodicConfigurator/releases)
- Implements reproducible builds with [pinned software dependencies](https://www.kusari.dev/blog/pinning-dependencies)
- Implements automated dependency updates and security patches using [renovate](https://www.mend.io/renovate/) and [dependabot](https://github.com/dependabot)

## Open Source

- Complies with [OpenSSF Best Practices](https://www.bestpractices.dev/projects/9101) for open source projects
- Uses [REUSE specification](https://reuse.software/spec-3.3/) for license compliance
  - Uses [CI job to ensure compliance](https://github.com/ArduPilot/MethodicConfigurator/actions/workflows/reuse.yml)
  - Uses [SPDX license identifiers](https://spdx.org/licenses/)
- Maintains comprehensive (more than 5000 lines) documentation
- Implements [inclusive community guidelines](https://github.com/ArduPilot/MethodicConfigurator/blob/master/CODE_OF_CONDUCT.md)
- Provides [clear contribution procedures](https://github.com/ArduPilot/MethodicConfigurator/blob/master/CONTRIBUTING.md)

## Security

See our comprehensive [Security Policy](https://ardupilot.github.io/MethodicConfigurator/SECURITY) for details on security measures,
audits, and vulnerability reporting processes.

<!-- Gurubase Widget -->
<script async src="https://widget.gurubase.io/widget.latest.min.js"
    data-widget-id="uE4kxEE4LY3ZSyfNsF5bU6gIOnWGTBOL_e16KwDH-0g"
    data-text="Ask AI"
    data-margins='{"bottom": "1rem", "right": "1rem"}'
    data-light-mode="true"
    id="guru-widget-id">
</script>
