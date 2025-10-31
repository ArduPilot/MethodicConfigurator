# How to contribute to the ArduPilot Methodic Configurator project?

<!-- markdownlint-disable MD025 -->

We have a very active (and friendly) developer group and would love to have the help!
Possible ways you can help:

* [Translating the software into your language](https://github.com/ArduPilot/MethodicConfigurator/blob/master/.github/instructions/manually_translate_the_user_interface.md#adding-a-translation)
* Testing [the code](https://github.com/ArduPilot/MethodicConfigurator)
* Filing [issues on github](https://github.com/ArduPilot/MethodicConfigurator/issues/new/choose), when you see a problem (or adding detail to existing issues that affect you)
* Fixing issues
* Adding new features
* Reviewing [existing pull requests](https://github.com/ArduPilot/MethodicConfigurator/pulls), and notifying the maintainer if it passes your code review.
* Finding and fixing [security issues](SECURITY.md)

## Learning the Code

Read [our architecture](https://ardupilot.github.io/MethodicConfigurator/ARCHITECTURE.html) to get a better understanding of the project.

and also:

* [System requirements](https://ardupilot.github.io/MethodicConfigurator/SYSTEM_REQUIREMENTS.html)
* [Compliance](https://ardupilot.github.io/MethodicConfigurator/COMPLIANCE.html), including our [Coding Standards](https://ardupilot.github.io/MethodicConfigurator/COMPLIANCE.html#coding-standards)

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

## Executing the code

You can either install the Methodic Configurator as a package or run it locally from your development codebase.
Installing the package will fetch the latest stable release version — see the [installation guide](https://ardupilot.github.io/MethodicConfigurator/INSTALL.html) for details.

To run it locally (from your cloned repository):

On Windows:

```powershell
.venv\Scripts\activate.ps1
python3 -m ardupilot_methodic_configurator
```

On macOS & Linux:

```bash
source .venv/bin/activate
python3 -m ardupilot_methodic_configurator
```

More detailed usage instructions can be found in our [user manual](https://ardupilot.github.io/MethodicConfigurator/USERMANUAL)

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
* Is the pull request branch free of merge commits?

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
