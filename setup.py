#!/usr/bin/env python3

"""
Creates the ardupilot_methodic_configurator pip python package.

This file is part of Ardupilot methodic configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2025 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import fnmatch
import os

from setuptools import setup


# recursively find all files that match the globs and return tuples with their directory and a list of relative paths
def find_data_files(globs: list[str]) -> list[tuple[str, list[str]]]:
    data_files_path_base = "ardupilot_methodic_configurator"
    ret = []
    for dirpath, _dirnames, filenames in os.walk(data_files_path_base):
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
    # this is used by bdist
    data_files=[*find_data_files(["*.param", "*.jpg", "*.json", "*.xml", "*.mo"])],
)
