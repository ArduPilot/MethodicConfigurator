#!/usr/bin/env python3

"""
Creates the ardupilot_methodic_configurator pip python package.

This file is part of Ardupilot methodic configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import fnmatch
import os

from setuptools import setup

extra_scripts = [
    "ardupilot_methodic_configurator/annotate_params.py",
    "ardupilot_methodic_configurator/extract_param_defaults.py",
    "ardupilot_methodic_configurator/param_pid_adjustment_update.py",
]

PRJ_URL = "https://github.com/ArduPilot/MethodicConfigurator"

for file in extra_scripts:
    os.chmod(file, 0o755)  # noqa: S103

os.chmod("ardupilot_methodic_configurator/__main__.py", 0o755)  # noqa: S103

# Read the long description from the README file
with open("README.md", encoding="utf-8") as f:
    long_description = f.read()
    # Use Absolute links so that the pyPI page renders correctly
    long_description = long_description.replace("(USERMANUAL.md", f"({PRJ_URL}/blob/master/USERMANUAL.md")
    long_description = long_description.replace("(QUICKSTART.md", f"({PRJ_URL}/blob/master/QUICKSTART.md")
    long_description = long_description.replace("(CONTRIBUTING.md", f"({PRJ_URL}/blob/master/CONTRIBUTING.md")
    long_description = long_description.replace("(ARCHITECTURE.md", f"({PRJ_URL}/blob/master/ARCHITECTURE.md")
    long_description = long_description.replace("(CODE_OF_CONDUCT.md", f"({PRJ_URL}/blob/master/CODE_OF_CONDUCT.md")
    long_description = long_description.replace("(LICENSE.md", f"({PRJ_URL}/blob/master/LICENSE.md")
    long_description = long_description.replace("(USECASES.md", f"({PRJ_URL}/blob/master/USECASES.md")
    long_description = long_description.replace("(credits/CREDITS.md", f"({PRJ_URL}/blob/master/credits/CREDITS.md")
    long_description = long_description.replace(
        "images/when_to_use_amc.png", f"{PRJ_URL}/raw/master/images/when_to_use_amc.png"
    )
    long_description = long_description.replace(
        "images/App_screenshot1.png", f"{PRJ_URL}/raw/master/images/App_screenshot1.png"
    )


# recursively find all files that match the globs and return tuples with their directory and a list of relative paths
def find_data_files(path: str, globs: list[str]) -> list[tuple[str, list[str]]]:
    data_files_path_base = "ardupilot_methodic_configurator"
    ret = []
    for dirpath, _dirnames, filenames in os.walk(path):
        data_files = []
        for glob in globs:
            for filename in fnmatch.filter(filenames, glob):
                relative_path = os.path.join(dirpath, filename)
                data_files.append(relative_path)
        if data_files:
            ret.append((os.path.relpath(dirpath, data_files_path_base), data_files))

    return ret


setup(
    packages=["ardupilot_methodic_configurator"],
    # long_description=long_description,
    # long_description_content_type="text/markdown",
    # this is used by bdist
    data_files=[
        *find_data_files(
            os.path.join("ardupilot_methodic_configurator", "vehicle_templates"), ["*.param", "*.jpg", "*.json", "*.xml"]
        ),
        *find_data_files(os.path.join("ardupilot_methodic_configurator", "locale"), ["*.mo"]),
    ],
)
