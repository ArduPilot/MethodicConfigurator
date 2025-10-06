# Compliance

ArduPilot Methodic Configurator adheres to multiple compliance standards and best practices:

## Usability

- [Wizard like interface](https://www.nngroup.com/articles/wizards/), allows user to concentrate in one task at a time
- All GUI elements contain [mouse over tooltips](https://www.nngroup.com/articles/tooltip-guidelines/) explaining their function
- Relevant documentation opens automatically in a browser window
- Uses *What you see is what gets changed* paradigm. No parameters are changed without the users's knowledge
- Translated into multiple languages
- No visible menus, no hidden menus.

## Code Quality

- Follows [PEP 8](https://peps.python.org/pep-0008/) Python code style guidelines
- Maintains high code quality through automated linting (static code analysis), all using strict settings:
  - [Pylint](https://www.pylint.org/) [automated workflow](https://github.com/ArduPilot/MethodicConfigurator/actions/workflows/pylint.yml),
  - [Ruff](https://docs.astral.sh/ruff/) [automated workflow](https://github.com/ArduPilot/MethodicConfigurator/actions/workflows/ruff.yml),
  - [mypy](https://www.mypy-lang.org/) [automated workflow](https://github.com/ArduPilot/MethodicConfigurator/actions/workflows/mypy.yml) and
  - [pyright](https://microsoft.github.io/pyright/#/) [automated workflow](https://github.com/ArduPilot/MethodicConfigurator/actions/workflows/pyright.yml)
- Uses [PEP 484](https://peps.python.org/pep-0484/) [type hints](https://docs.python.org/3/library/typing.html)
  - Enforces type checking with [MyPy](https://www.mypy-lang.org/) and [pyright](https://microsoft.github.io/pyright/#/) type checkers
- Automated code formatting using [ruff](https://docs.astral.sh/ruff/) for consistency
- Code and documentation are [spell checked](https://streetsidesoftware.com/vscode-spell-checker/)
  and [english grammar checked](https://app.grammarly.com/)
  - [markdown-lint](https://github.com/DavidAnson/markdownlint-cli2)
  [automated workflow](https://github.com/ArduPilot/MethodicConfigurator/actions/workflows/markdown-lint.yml) and
  - [markdown-link-check](https://github.com/tcort/markdown-link-check) [automated workflow](https://github.com/ArduPilot/MethodicConfigurator/actions/workflows/markdown-link-check.yml)
- Follows object-oriented design principles and [clean code practices](https://www.oreilly.com/library/view/clean-code/9780136083238/)
- Implements comprehensive error handling and logging, with 5 verbosity levels
- Implements [PEP 621](https://peps.python.org/pep-0621/) project metadata standards
- Adheres to [Keep a Changelog](https://keepachangelog.com/) format
- Complies with [Python Packaging Authority](https://www.pypa.io/) guidelines

## Software Development

- Implements [continuous integration/continuous deployment](https://github.com/ArduPilot/MethodicConfigurator/actions) (CI/CD) practices
- Maintains comprehensive [assertion-based test coverage](https://coveralls.io/github/ArduPilot/MethodicConfigurator?branch=master) through [pytest](https://docs.pytest.org/en/stable/)
- Uses [semantic versioning](https://semver.org/) for releases
- Follows [git-flow branching model](https://www.gitkraken.com/learn/git/git-flow)
- Implements [automated security scanning and vulnerability checks](https://app.snyk.io/org/amilcarlucas/project/c8fd6e29-715b-4949-b828-64eff84f5fe1)
- Implements [git pre-commit hooks](https://pre-commit.com/) to ensure code quality and compliance on every commit
- Implements reproducible builds with locked dependencies
- Uses containerized CI/CD environments for consistency
- Uses automated changelog generation
- Implements automated dependency updates and security patches using [renovate](https://www.mend.io/renovate/) and [dependabot](https://github.com/dependabot)

## Open Source

- Complies with [OpenSSF Best Practices](https://www.bestpractices.dev/projects/9101) for open source projects
- Uses [REUSE specification](https://reuse.software/spec-3.3/) for license compliance
  - Uses CI job to ensure compliance
  - Uses [SPDX license identifiers](https://spdx.org/licenses/)
- Maintains comprehensive (more than 5000 lines) documentation
- Implements [inclusive community guidelines](https://github.com/ArduPilot/MethodicConfigurator/blob/master/CODE_OF_CONDUCT.md)
- Provides [clear contribution procedures](https://github.com/ArduPilot/MethodicConfigurator/blob/master/CONTRIBUTING.md)

## Security

- Regular security audits through [Snyk](https://snyk.io/), [codacy](https://www.codacy.com/), [black duck](https://www.blackduck.com/) and other tools
- Follows [OpenSSF Security Scorecard](https://securityscorecards.dev/) best practices
- Uses [gitleaks](https://github.com/gitleaks/gitleaks) pre-commit hook to ensure no secrets are leaked
- Implements secure coding practices, runs [anti-virus in CI](https://github.com/ArduPilot/MethodicConfigurator/actions/workflows/gitavscan.yml)
- Maintains [security policy and vulnerability reporting process](https://github.com/ArduPilot/MethodicConfigurator/blob/master/SECURITY.md)
