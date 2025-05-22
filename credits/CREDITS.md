<!--
SPDX-FileCopyrightText: 2024-2025 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
-->

# Licenses

We use [REUSE software API](https://api.reuse.software/) in the form of SPDX tags in most of the files to explicitly declare Copyright and License.
We check compliance using pre-commit hook and enforce it via a CI job.
Our status is [![REUSE status](https://api.reuse.software/badge/github.com/ArduPilot/MethodicConfigurator)](https://api.reuse.software/info/github.com/ArduPilot/MethodicConfigurator)

This software is licensed under the [GNU General Public License v3.0](../LICENSE.md) and is built on top of (depends on) other open-source software.
We are thankful to the developers of those software packages.

It directly uses:

| Software | License |
|----------|---------|
| [tkinter](https://docs.python.org/3/library/tkinter.html) | [Python Software Foundation License](https://docs.python.org/3/license.html) |
| [argparse](https://docs.python.org/3/library/argparse.html) | [Python Software Foundation License](https://docs.python.org/3/license.html) |
| [logging](https://docs.python.org/3/library/logging.html) | [Python Software Foundation License](https://docs.python.org/3/license.html) |
| [typing](https://docs.python.org/3/library/typing.html) | [Python Software Foundation License](https://docs.python.org/3/license.html) |
| [json](https://docs.python.org/3/library/json.html) | [Python Software Foundation License](https://docs.python.org/3/license.html) |
| [os](https://docs.python.org/3/library/os.html) | [Python Software Foundation License](https://docs.python.org/3/license.html) |
| [re](https://docs.python.org/3/library/re.html) | [Python Software Foundation License](https://docs.python.org/3/license.html) |
| [webbrowser](https://docs.python.org/3/library/webbrowser.html) | [Python Software Foundation License](https://docs.python.org/3/license.html) |
| [pymavlink](https://github.com/ArduPilot/pymavlink) | [GNU Lesser General Public License v3.0](https://github.com/ArduPilot/pymavlink/blob/master/COPYING) |
| [ArduPilot tempcal_IMU.py](https://github.com/ArduPilot/ardupilot/blob/master/Tools/scripts/tempcal_IMU.py) | [GNU General Public License v3.0](https://github.com/ArduPilot/ardupilot/blob/master/COPYING.txt) |
| [argcomplete](https://github.com/kislyuk/argcomplete) | [Apache 2.0 License](https://raw.githubusercontent.com/kislyuk/argcomplete/refs/heads/main/LICENSE.rst) |
| [platformdirs](https://platformdirs.readthedocs.io/en/latest/index.html) | [MIT](https://github.com/platformdirs/platformdirs/blob/main/LICENSE) |
| [pyserial](https://pyserial.readthedocs.io/en/latest/pyserial.html) | [BSD License](https://github.com/pyserial/pyserial/blob/master/LICENSE.txt) |
| [Scrollable TK frame](https://gist.github.com/mp035/9f2027c3ef9172264532fcd6262f3b01) by Mark Pointing | [Mozilla Public License, v. 2.0](https://mozilla.org/MPL/2.0/) |
| [Python Tkinter ComboBox](https://dev.to/geraldew/python-tkinter-an-exercise-in-wrapping-the-combobox-ndb) by geraldew | [Mozilla Public License, v. 2.0](https://mozilla.org/MPL/2.0/) |
| [Argparse check limits](https://gist.github.com/dmitriykovalev/2ab1aa33a8099ef2d514925d84aa89e7) by Dmitriy Kovalev | [Apache 2.0 License](http://www.apache.org/licenses/LICENSE-2.0) |
| [defusedxml](https://github.com/tiran/defusedxml) | [Python Software Foundation License](https://github.com/tiran/defusedxml/blob/main/LICENSE) |
| [matplotlib](https://matplotlib.org/) | [Matplotlib License](https://github.com/matplotlib/matplotlib/blob/main/LICENSE/LICENSE) |
| [numpy](https://numpy.org/) | [BSD License](https://github.com/numpy/numpy/blob/main/LICENSE.txt) |
| [pillow](https://python-pillow.github.io/) | [MIT-CMU License](https://github.com/python-pillow/Pillow/blob/main/LICENSE) |
| [requests](https://requests.readthedocs.io/) | [Apache 2.0 License](https://github.com/psf/requests/blob/main/LICENSE) |
| [setuptools](https://setuptools.pypa.io/) | [MIT License](https://github.com/pypa/setuptools/blob/main/LICENSE) |
| [jsonschema](https://python-jsonschema.readthedocs.io/en/stable/) | [MIT License](https://github.com/python-jsonschema/jsonschema/blob/main/COPYING) |

It indirectly uses:

| Software | License |
|----------|---------|
| [certifi](https://github.com/certifi/python-certifi) | [Mozilla Public License 2.0](https://github.com/certifi/python-certifi/blob/master/LICENSE) |
| [charset-normalizer](https://github.com/Ousret/charset_normalizer) | [MIT License](https://github.com/Ousret/charset_normalizer/blob/master/LICENSE) |
| [future](https://github.com/PythonCharmers/python-future) | [MIT License](https://github.com/PythonCharmers/python-future/blob/master/LICENSE.txt) |
| [urllib3](https://github.com/urllib3/urllib3) | [MIT License](https://github.com/urllib3/urllib3/blob/main/LICENSE.txt) |
| [lxml](https://github.com/lxml/lxml) | [BSD License](https://github.com/lxml/lxml/blob/master/LICENSE.txt) |
| [idna](https://github.com/kjd/idna) | [BSD License](https://github.com/kjd/idna/blob/master/LICENSE.md) |
| [Inno Setup](https://jrsoftware.org/) | [Inno Setup License](https://jrsoftware.org/files/is/license.txt) |

Their licenses are linked above and are available in [this directory](https://github.com/ArduPilot/MethodicConfigurator/tree/master/credits).

Credits also go to these other software projects that helped in developing ArduPilot Methodic Configurator:

- [github](https://github.com/): A platform for version control and collaboration.
- [git extensions](https://gitextensions.github.io/): A graphical user interface for Git.
- [ruff](https://docs.astral.sh/ruff/): A fast Python linter.
- [pylint](https://www.pylint.org/): A Python static code analysis tool.
- [mypy](https://mypy-lang.org/): A static type checker for Python.
- [pyright](https://github.com/microsoft/pyright): Pyright is a full-featured, standards-based static type checker for Python.
- [uv](https://docs.astral.sh/uv/): An extremely fast Python package and project manager.
- [grammarly](https://www.grammarly.com/): An AI-powered writing assistant.
- [markdown-lint-cli2](https://github.com/DavidAnson/markdownlint-cli2): A command-line tool for linting Markdown files.
- [markdown-link-check](https://github.com/tcort/markdown-link-check): A tool to check for broken links in Markdown files.
- [codacy](https://www.codacy.com/): A code quality and code review tool.
- [snyk](https://snyk.io/): A security tool for finding and fixing vulnerabilities.
- [codeclimate](https://codeclimate.com/): A platform for automated code review.
- [coveralls.io](https://coveralls.io/): A tool for measuring code coverage.
- [pypi.org](https://pypi.org/): The Python Package Index, a repository of software for the Python programming language.
- [inno setup](https://jrsoftware.org/isinfo.php): A free installer for Windows programs.
- [bestpractices.dev](https://www.bestpractices.dev/en): A site for checking best practices in software development.
- [isitmaintained.com](https://isitmaintained.com/): A service to check the maintenance status of open-source projects.
- [renovate](https://github.com/renovatebot/renovate): Cross-platform Dependency Automation by Mend.io
- [gurubase](https://github.com/Gurubase/gurubase): An open-source RAG system that we used to create an AI-powered Q&A assistant.
- [gitleaks](https://github.com/gitleaks/gitleaks): a tool for detecting secrets like passwords, API keys, and tokens in git repos.
- [pre-commit](https://pre-commit.com/): A framework for managing and maintaining multi-language git pre-commit hooks.
- [OpenSSF Scorecard](https://securityscorecards.dev/): Quickly assess open source projects for risky practices.

Using these software allowed a small group of programmers to produce better code faster.

Thanks to the users for testing and suggesting features and improvements.

These books helped shape this software:

- [Clean Code by Robert C. Martin](https://www.oreilly.com/library/view/clean-code/9780136083238/)
- [Clean Architecture by Robert C. Martin](https://www.oreilly.com/library/view/clean-architecture/9780134494272/)
- [Modern Software Engineering by David Farley](https://www.oreilly.com/library/view/modern-software-engineering/9780137314942/)
- [The DevOps Handbook by Gene Kim, Patrick Debois, John Willis, and Jez Humble](https://www.oreilly.com/library/view/the-devsecops-handbook/9781098182281/)
