#!/usr/bin/env python3

"""
This file is part of Ardupilot methodic configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import os
import shutil
import sys

# Define the source directory and the file to be copied
BASE_TARGET_DIR = "vehicle_templates/"
FILE_TO_COPY = "24_inflight_magnetometer_fit_setup.pdef.xml"

# Ensure the base target directory exists
if not os.path.exists(BASE_TARGET_DIR):
    print(f"Error: Base target directory {BASE_TARGET_DIR} does not exist.")
    sys.exit(1)

# Ensure the file to be copied exists
source_file_path = os.path.join(".", FILE_TO_COPY)
if not os.path.exists(source_file_path):
    print(f"Error: File {source_file_path} does not exist.")
    sys.exit(1)

# Traverse the source directory and copy the file to each subdirectory
for root, dirs, _files in os.walk(BASE_TARGET_DIR):
    for directory in dirs:
        target_dir = os.path.join(root, directory)
        target_file_path = os.path.join(target_dir, FILE_TO_COPY)
        shutil.copy(source_file_path, target_file_path)
        print(f"Copied {FILE_TO_COPY} to {target_file_path}")
