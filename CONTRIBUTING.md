# How to contribute to the ArduPilot Methodic Configurator project?

<!-- markdownlint-disable MD025 -->

We have a very active (and friendly) developer group and would love to have the help!
Possible ways you can help:

* Testing [the code](https://github.com/ArduPilot/MethodicConfigurator)
* Filing [issues on github](https://github.com/ArduPilot/MethodicConfigurator/issues/new/choose), when you see a problem or adding detail to existing issues
* Fixing issues
* Adding new features
* Reviewing [existing pull requests](https://github.com/ArduPilot/MethodicConfigurator/pulls), and notifying the maintainer if it passes your code review.
* [Translating the software into your language](https://github.com/ArduPilot/MethodicConfigurator/blob/master/.github/skills/add-ui-translation/SKILL.md#adding-a-translation)
* Finding and fixing [security issues](SECURITY.md)

## Learning the Code

Read [our architecture](https://ardupilot.github.io/MethodicConfigurator/ARCHITECTURE.html) to get a better understanding of the project.

and also:

* [System requirements](https://ardupilot.github.io/MethodicConfigurator/SYSTEM_REQUIREMENTS.html)
* [Compliance](https://ardupilot.github.io/MethodicConfigurator/COMPLIANCE.html), including our [Coding Standards](https://ardupilot.github.io/MethodicConfigurator/COMPLIANCE.html#coding-standards)
* [Project Governance](https://ardupilot.github.io/MethodicConfigurator/GOVERNANCE.html) - understand how the project is managed and decisions are made
* [Customizing Configuration Steps](https://ardupilot.github.io/MethodicConfigurator/CUSTOMIZING_CONFIGURATION_STEPS.html) - extend the configuration workflow
* [Project Roadmap](https://ardupilot.github.io/MethodicConfigurator/ROADMAP.html) - see what we're planning to work on

## Setting up developer environment

1. [Install git](https://git-scm.com/install/) on your computer.
2. Create a free [personal github account](https://docs.github.com/en/get-started/start-your-journey/creating-an-account-on-github)
3. [Log in to your github account](https://github.com/login) using a browser
4. [Fork the ArduPilot/MethodicConfigurator github repository](https://github.com/ArduPilot/MethodicConfigurator/fork).
5. Clone your fork and navigate into it:

    ```bash
    git clone https://github.com/YOUR_USER_NAME/MethodicConfigurator.git
    cd MethodicConfigurator
    ```

6. Run the following helper scripts:

    On Windows:

    ```powershell
    .\SetupDeveloperPC.bat
    ```

    On Linux and macOS:

    ```bash
    ./SetupDeveloperPC.sh
    ```

The above scripts will:

* Configure Git and useful aliases
* Create a Python virtual environment and install project dependencies
* Install recommended VSCode extensions
* Set up pre-commit hooks for linting and formatting
* Install GNU gettext tools for internationalization support

### Running tests on Linux

On Linux systems without a usable desktop display, the test suite may need the
project virtual environment and a virtual X display. Use `xvfb-run` together
with `.venv` so GUI-dependent fixtures can initialize correctly:

```bash
PATH="$PWD/.venv/bin:$PATH" xvfb-run -a python -m pytest tests/ -v -m "not sitl and not integration"
```

For SITL integration tests, use the same environment with the SITL runner:

```bash
PATH="$PWD/.venv/bin:$PATH" xvfb-run -a ./scripts/run_sitl_tests.sh test
```

The runner discovers the ArduCopter binary in `sitl/arducopter`. When invoking
SITL tests directly, set `SITL_BINARY` explicitly:

```bash
SITL_BINARY="$PWD/sitl/arducopter" PATH="$PWD/.venv/bin:$PATH" \
  xvfb-run -a python -m pytest -m sitl -v
```

### Mutation testing

The optional [Mutmut](https://mutmut.readthedocs.io/en/latest/) suite checks whether
existing tests detect small changes to thirty-eight modules covering battery voltages,
parameter validation and serialization, firmware version parsing, parameter
history, AutoTune acceleration/gain backoff, IMU helpers, firmware upload,
log-analysis orchestration, usage popups, file browsing and task scheduling, motor-test UI,
bootloader protocol handling, schema-validated filesystem IO, IMU log analysis,
vehicle-component validation/display, flight-controller business rules, transfer
progress accounting, configuration expression evaluation, firmware parameter
migrations, battery-monitor telemetry and status handling, and configuration-step
processing. It runs on Linux, macOS, or Windows
through WSL.

Install it into the project virtual environment:

```bash
uv pip install --python .venv/bin/python --editable '.[dev,mutation]'
```

Mutmut verifies the configured tests against unmodified behavior before testing
mutations. Xvfb is needed on Linux because the shared test fixtures import
PyAutoGUI during collection:

```bash
PATH="$PWD/.venv/bin:$PATH" xvfb-run -a mutmut run --max-children 2
.venv/bin/mutmut results --all true
.venv/bin/mutmut browse
```

On macOS, run `mutmut run --max-children 2` with the virtual environment activated
and a working desktop display, without `xvfb-run`.

The `[tool.mutmut]` section in `pyproject.toml` selects both the modules to mutate
and the tests to run. Update those lists together when expanding the suite.
Include the module's existing behavior, BDD, and unit tests when auditing the
selection. A "no tests" result can indicate an omitted test file or missing
association rather than missing tests in the repository.
Its `do_not_mutate` list mirrors `[report].omit` in `.coveragerc`, keeping generated
and externally maintained files out of mutation runs.
CI reads the same configuration for its separate clean-test run, so new test
selections do not need to be duplicated in the workflow.
Add repository resources and test helpers used by selected tests to `also_copy`;
the AutoTune tests need `TUNING_GUIDE_Heli.md`, component-model tests need the
`tests/` directory for shared fixtures, and MAVLink inspector tests need the
PowerShell completion module copied into Mutmut's test tree.
Generated copies and results are stored in the ignored `mutants/` directory;
Mutmut resumes previous work there. For a fresh baseline, remove that generated
directory first, especially after changing tests or dependencies. Run from the
repository root so that Mutmut reads its configuration.

The [mutation workflow](.github/workflows/mutation.yml) runs manually or weekly on
Ubuntu with Python 3.11. It uploads results without enforcing a mutation score;
clean-test and framework failures still fail the job. Per-mutant timeouts and
crashes are reported for review. Scheduled runs are disabled in forks.
The job summary groups all mutation outcomes by module; the
artifact retains individual results and execution logs. The existing coverage
gate remains independent.

For surviving mutations, inspect the diff with `mutmut show <mutant-name>` and add
assertions for observable behavior. Some mutations are equivalent; review those
individually rather than adding broad suppressions. Mutmut 3 primarily mutates
function bodies, so explicit tests are still needed for module-level constants.
Timeouts, missing test associations, and execution errors need separate review.
Type-check filtering and coverage-only filtering are intentionally disabled for
the mutation suite.

Audit the selected tests before writing replacements: the manual-override unit,
acceptance and integration tests exercise parameter editability and serialization,
while `test_derived_parameter_confirmation.py` checks parameter snapshot differences.
Keep those suites selected when mutating the parameter models.

Review equivalent survivors separately from missing assertions. For example,
`float("inf")` and `float("INF")` behave identically; changing the split limit in
`parse_ver_fields()` does not change its first token; and the battery voltage
helpers' fallback arguments cannot be reached when the preceding indexed lookup
already requires the same keys. In the template-name helper, missing product
fields defaulting to either `None` or an empty string are normalized to the same
empty string. Do not construct unsupported inputs merely to kill these mutants
or exclude entire functions because some of their mutants are equivalent.

The flight-controller frame helper's empty default vehicle type and an unknown
vehicle type both use the standard frame parameters. In transfer accounting,
the extra zero in `max(previous, current, 0)` is redundant while the previous
counter starts at zero and never decreases. Changes to the evaluator's
`typing.cast` type argument also have no runtime effect. Retain these equivalent
survivors rather than weakening the mutation scope or testing invalid counter states.

For firmware parameter migrations, verify release boundaries and the file,
parameter names, and version inputs shown in diagnostic warnings. Some survivors
only change log wording. Others change unused SR helper placeholders, or bypass
the SERIAL preservation branch and reach the same generic preservation behavior.
The outer newer-version guard is redundant with the individual migration gates.
Review these separately from mutations that change migrated tuning.

For battery monitoring, check secondary-battery thresholds and startup recovery
after reconnecting or re-enabling monitoring. False-valued stream-state resets
can be equivalent when only their truth value is used. An unset interval of
`None` or an empty string also compares differently from every positive requested
interval. Review these and diagnostic wording changes separately from safety
status and retry behavior.

For configuration steps, exercise computed values with the real expression
evaluator and check parameter metadata, defaults, identity, and rename feedback.
Some dictionary fallbacks and empty reasons are normalized to the same domain
values. Transient-variable cleanup can be redundant with rebuilding the step's
evaluation context. The current rename planner returns no duplicate removals,
so that feedback branch is unreachable through normal processing. Review these
separately from lost metadata, incorrect live inputs, and conflicting renames.

For a focused rerun, pass quoted module or function patterns to `mutmut run`,
for example:

```bash
PATH="$PWD/.venv/bin:$PATH" xvfb-run -a mutmut run --max-children 2 \
  'ardupilot_methodic_configurator.plugins.imu_helpers.*'
```

Keep a copy of previous results before refreshing `mutants/`, and report killed,
surviving, unassociated, timed-out and crashed mutants separately. A partial run
does not establish a new score for the full configured suite.

If a worker crashes or times out while the same mutant fails normally in a direct
pytest run, compare it in a separate temporary checkout with
`forkserver_warmup = "none"` under `[tool.mutmut]`. This initializes test-module
imports inside each worker instead of preloading them in the fork server and
can distinguish shared GUI import state from an actual mutant-induced hang.
It adds worker startup cost, so use it for diagnosis before changing the normal
suite configuration. Retain both runs' execution outcomes in the report.

### Optional local code graph

For faster codebase exploration with Codex, CodeGraph can be installed as an
optional local developer tool. It is not a project dependency and does not run
in CI:

```bash
codegraph init .
codegraph status .
```

The graph is stored in the ignored `.codegraph/` directory and is kept current
by CodeGraph's local file watcher. Use `codegraph uninit .` to remove the local
index. CodeGraph indexes source code; configuration relationships in JSON and
`.param` files still need to be inspected directly.

## Alternative: Using Docker for Development

As an alternative to setting up the development environment locally, you can use Docker to run the project in a containerized environment.
This ensures consistency across different machines and simplifies dependency management.

### Prerequisites

* [Install Docker](https://docs.docker.com/get-docker/) on your computer
* [Install Docker Compose](https://docs.docker.com/compose/install/) (usually included with Docker Desktop)

### Building and Running

1. Clone the repository and navigate into it:

    ```bash
    git clone https://github.com/YOUR_USER_NAME/MethodicConfigurator.git
    cd MethodicConfigurator
    ```

2. Build the Docker image:

    ```bash
    docker compose build
    ```

3. Run the development environment:

    To start an interactive shell in the container:

    ```bash
    docker compose run --rm dev
    ```

    To run tests:

    ```bash
    docker compose run --rm test
    ```

    To run SITL (Software In The Loop) integration tests:

    ```bash
    docker compose run --rm sitl
    ```

    To run linters:

    ```bash
    docker compose run --rm lint
    ```

### Benefits of Docker Development

* Consistent environment across all contributors
* No need to install Python, dependencies, or tools locally
* Isolated from your system's Python installation
* Easy to test against different Python versions by changing the Dockerfile
* Faster onboarding for new contributors

## Executing the code

You can either install the Methodic Configurator as a package or run it locally from your development codebase.
Installing the package will fetch the latest stable release version - see the [installation guide](https://ardupilot.github.io/MethodicConfigurator/INSTALL.html) for details.

To run it locally (from your cloned repository):

On Windows:

```powershell
.venv\Scripts\activate.ps1
python -m ardupilot_methodic_configurator
```

On macOS & Linux:

```bash
source .venv/bin/activate
python3 -m ardupilot_methodic_configurator
```

More detailed usage instructions can be found in our [user manual](https://ardupilot.github.io/MethodicConfigurator/USERMANUAL)

## Managing Dependencies

When adding a new runtime or development dependency, **all** of the following steps must be completed
in order to keep the project REUSE-compliant and credits accurate:

1. **`pyproject.toml`** — add the package with a pinned version.
2. **`credits/CREDITS.md`** — add a row to the "directly uses" or "indirectly uses" table with a
   link to the project and its license.
3. **`credits/update_credits_licenses.py`** — add an entry (name + raw license URL) to
   `direct_dependencies` or `indirect_dependencies`.
4. **Download the license file** — run `python update_credits_licenses.py` from the `credits/`
   directory to fetch the license file(s).
5. **`REUSE.toml`** — add an `[[annotations]]` block for each downloaded license file with the
   correct `SPDX-FileCopyrightText` and `SPDX-License-Identifier`.
6. **Verify** — run `reuse lint` and `pre-commit run --all` until all checks pass.

Full details and examples are in
[`.github/skills/update-software-dependencies/SKILL.md`](.github/skills/update-software-dependencies/SKILL.md).

## Submitting patches

Follow the [Conventional Commits](https://www.conventionalcommits.org/en/v1.0.0/) style for your git commit messages.

Each commit should be signed off using the `--signoff` option in `git commit`.
By signing off your commit, you certify that you agree to the terms of the [Developer Certificate of Origin (DCO)](https://developercertificate.org/).

You can sign by either your commit by pressing the *sign-off* button on `git gui` or by using the command line:

```bash
# Sign off a commit as you're making it
git commit --signoff -m "commit message"

# Add a signoff to the last commit you made
git commit --amend --signoff

# Rebase your branch against master and sign off every commit in your branch
git rebase --signoff master
```

Once your changes are ready, submit a [GitHub Pull Request (PR)](https://github.com/ArduPilot/MethodicConfigurator/pulls).

## Code review process

Once your pull request is submitted, a thorough code review process will begin.
We evaluate contributions based on multiple criteria to ensure quality, security, and maintainability.
The review includes both automated checks and manual inspection.

### Review Process

1. **Initial Automated Review**: CI checks must pass before manual review begins
2. **Peer Review**: At least one maintainer reviews the code, adding comments and suggestion to the github pull request webpage
3. **Feedback & Iteration**: Contributors address review comments and update the PR
4. **Final Approval**: Maintainers approve and merge the changes
5. **Post-Merge**: Automated deployment and monitoring ensure stability

### Automated Checks

* **CI/CD Workflows**: All changes are automatically tested against our
  [code quality guidelines](https://ardupilot.github.io/MethodicConfigurator/COMPLIANCE.html#coding-standards)
  and [security requirements](https://ardupilot.github.io/MethodicConfigurator/SECURITY)
* **Linting and Formatting**: Code must pass [Ruff](https://github.com/ArduPilot/MethodicConfigurator/actions/workflows/ruff.yml),
  [Pylint](https://github.com/ArduPilot/MethodicConfigurator/actions/workflows/pylint.yml), and other quality checks
* **Type Checking**: [MyPy](https://github.com/ArduPilot/MethodicConfigurator/actions/workflows/mypy.yml) and
  [Pyright](https://github.com/ArduPilot/MethodicConfigurator/actions/workflows/pyright.yml) validation
* **Security Scanning**: Automated vulnerability detection via [CodeQL](https://github.com/ArduPilot/MethodicConfigurator/actions/workflows/codeql.yml) and dependency reviews
* **Testing**: Comprehensive test suite execution with [pytest](https://github.com/ArduPilot/MethodicConfigurator/actions/workflows/pytest.yml)
* **Git branching conventions**: Is the [pull request branch free of merge commits](https://github.com/ArduPilot/MethodicConfigurator/actions/workflows/test_branch_conventions.yml)?

### Manual Review Criteria

We manually verify the following aspects:

#### Code Quality & Standards

* Does the code follow our [coding standards](https://ardupilot.github.io/MethodicConfigurator/COMPLIANCE#coding-standards)
  and [PEP 8](https://peps.python.org/pep-0008/) guidelines?
* Is the code well-documented with appropriate docstrings and comments?
* Does it include comprehensive error handling and logging?
* Are there any code smells, technical debt, or maintainability issues?
* Do the [git commit messages follow conventional commit standards](https://www.conventionalcommits.org/en/v1.0.0/)?
* Is at least the last commit in the pull request branch [signed off](https://developercertificate.org/) by the contributor?
* Does the pull request have a clear description of the changes and their rationale?

#### Architecture & Design

* Does the change follow our [architecture guidelines](https://github.com/ArduPilot/MethodicConfigurator/blob/master/ARCHITECTURE.md)?
* Is there proper separation of concerns (backend, business logic, frontend/GUI)?
* Is the code modular, testable, and maintainable?
* Does it follow object-oriented design principles and [clean code practices](https://www.oreilly.com/library/view/clean-code/9780136083238/)?

#### Functionality & Testing

* Is it generic enough to be useful for multiple use cases?
* Does the change include appropriate unit tests and integration tests?
* Are edge cases and error conditions properly tested?
* Does it maintain or improve [test coverage](https://coveralls.io/github/ArduPilot/MethodicConfigurator)?
* Have manual testing scenarios been considered?

#### Security & Compliance

* Does the change follow [secure coding practices](https://ardupilot.github.io/MethodicConfigurator/SECURITY)?
* Does it comply with our [license requirements](https://github.com/ArduPilot/MethodicConfigurator/blob/master/LICENSE.md) and [REUSE specification](https://reuse.software/spec-3.3/)?

#### User Experience & Documentation

* Does the change maintain or improve usability?
* Is user-facing documentation updated (including translations)?
* Are there any breaking changes that need documentation?
* New strings must be properly internationalized with `_( ... )`

#### Community & Process

* Does the change violate our [code of conduct](https://github.com/ArduPilot/MethodicConfigurator/blob/master/CODE_OF_CONDUCT.md)?

## Development Team

The ArduPilot Methodic Configurator project is open-source and maintained by a team of volunteers.

New developers are recommended to join the `#general` and `#methodic_configurator` channels on
[Discord](https://ardupilot.org/discord).

You can also join the
[development discussion on Discourse](https://discuss.ardupilot.org/c/development-team).

Note that these are NOT for user tech support, and are moderated
for new users to prevent off-topic discussion.
