# How to contribute to the ArduPilot Methodic Configurator project?

<!-- markdownlint-disable MD025 -->

If you are reading this page, you are possibly interested in contributing to our project.
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
* [Compliance](https://ardupilot.github.io/MethodicConfigurator/COMPLIANCE.html)

## Setting up developer environment

The instructions below assume that you have already installed git and forked the [MethodicConfigurator](https://github.com/ArduPilot/MethodicConfigurator.git) github repository.

Clone your fork and navigate into it:

```bash
git clone https://github.com/YOUR_USER_NAME/MethodicConfigurator.git
cd MethodicConfigurator
```

Run the following helper scripts:

On Windows:

```cmd
.\SetupDeveloperPC.bat
.\install_msgfmt.bat
.\install_wsl.bat
```

On Linux and MacOS:

```bash
./SetupDeveloperPC.sh
```

The above scripts will:

* Configure Git and useful aliases
* Install dependencies
* Install recommended VSCode extensions
* Set up pre-commit hooks for linting and formatting

## Executing the code

You can either install the Methodic Configurator as a package or run it locally from your development codebase.
Installing the package will fetch the latest stable release version — see the [installation guide](https://ardupilot.github.io/MethodicConfigurator/INSTALL.html) for details.

To run it locally (from your cloned repository):

On Windows:

```cmd
python3 -m ardupilot_methodic_configurator
```

On MacOS & Linux:

```bash
source venv/bin/activate

python3 -m ardupilot_methodic_configurator
```

More detailed usage instructions can be found in our [user manual](https://ardupilot.github.io/MethodicConfigurator/USERMANUAL)

## Submitting patches

We encourage you to follow the [Conventional Commits](https://www.conventionalcommits.org/en/v1.0.0/) style for your commit messages, as used in this repository.

Each commit should be signed off using the `--signoff` option in `git commit`.
By signing off your commit, you certify that you agree to the terms of the [Developer Certificate of Origin (DCO)](https://developercertificate.org/).

You can sign your commit by:

```bash
# Sign off a commit as you're making it
git commit --signoff -m"commit message"

# Add a signoff to the last commit you made
git commit --amend --signoff

# Rebase your branch against master and sign off every commit in your branch
git rebase --signoff master
```

Once your changes are ready, submit a [Pull Request (PR)](https://github.com/ArduPilot/MethodicConfigurator/pulls) on GitHub.

## Development Team

The ArduPilot Methodic Configurator project is open-source and maintained by a team of volunteers.

New developers are recommended to join the `#general` channel on
[Discord](https://ardupilot.org/discord).

You can also join the
[development discussion on Discourse](https://discuss.ardupilot.org/c/development-team).

Note that these are NOT for user tech support, and are moderated
for new users to prevent off-topic discussion.

<!-- Gurubase Widget -->
<script async src="https://widget.gurubase.io/widget.latest.min.js"
    data-widget-id="uE4kxEE4LY3ZSyfNsF5bU6gIOnWGTBOL_e16KwDH-0g"
    data-text="Ask AI"
    data-margins='{"bottom": "1rem", "right": "1rem"}'
    data-light-mode="true"
    id="guru-widget-id">
</script>
