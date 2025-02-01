#!/usr/bin/env python3

"""
Copy 24_inflight_magnetometer_fit_setup.pdef.xml file to all vehicle template subdirectories.

This file is part of Ardupilot methodic configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2025 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import logging
import os
import shutil
import sys

# Define the source directory and the file to be copied
BASE_TARGET_DIR = os.path.join("ardupilot_methodic_configurator", "vehicle_templates")
FILE_TO_COPY = "24_inflight_magnetometer_fit_setup.pdef.xml"

logging.basicConfig(level="INFO", format="%(asctime)s - %(levelname)s - %(message)s")

# Ensure the base target directory exists
if not os.path.exists(BASE_TARGET_DIR):
    logging.critical("Base target directory %s does not exist.", BASE_TARGET_DIR)
    sys.exit(1)

# Ensure the file to be copied exists
source_file_path = os.path.join(".", FILE_TO_COPY)
if not os.path.exists(source_file_path):
    logging.critical("File %s does not exist.", source_file_path)
    sys.exit(1)

# Traverse the source directory and copy the file to each subdirectory
for root, dirs, _files in os.walk(BASE_TARGET_DIR):
    # If this directory has no subdirectories, copy the file
    if not dirs:
        target_file_path = os.path.join(root, FILE_TO_COPY)
        shutil.copy(source_file_path, target_file_path)
        logging.info("Copied %s to %s", FILE_TO_COPY, target_file_path)
