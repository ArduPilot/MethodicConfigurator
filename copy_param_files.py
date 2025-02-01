#!/usr/bin/env python3

"""
Copy some parameter files. For dev only.

This file is part of Ardupilot methodic configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2025 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import logging
import os
import shutil

# Source directory containing the files to copy
SOURCE_DIR = os.path.join("ArduCopter", "diatone_taycan_mxc", "4.6.x-params")

# Files to copy
files_to_copy = ["50_optical_flow_setup.param", "51_optical_flow_results.param", "52_use_optical_flow_instead_of_gnss.param"]

# Base directory for vehicle templates
BASE_DIR = os.path.join("ardupilot_methodic_configurator", "vehicle_templates")


# Function to get all subdirectories excluding the source (do not copy onto itself)
def get_subdirectories(base_dir: str, exclude_source: bool = True) -> list[str]:
    subdirs = []
    for root, dirs, _ in os.walk(base_dir):
        rel_dir = os.path.relpath(root, base_dir)
        if exclude_source and rel_dir == SOURCE_DIR:
            continue
        if len(dirs) == 0:  # Check if the directory is a leaf directory
            subdirs.append(rel_dir)
    return subdirs


# Function to copy files
def copy_files(source: str, target: str) -> None:
    for file in files_to_copy:
        source_path = os.path.join(source, file)
        target_path = os.path.join(target, file)

        try:
            shutil.copy2(source_path, target_path)
            logging.info("Copied %s to %s", file, target)
        except Exception as e:  # pylint: disable=broad-except
            logging.error("Error copying %s to %s: %s", file, target, e)


logging.basicConfig(level="INFO", format="%(asctime)s - %(levelname)s - %(message)s")

# Get all ArduCopter subdirectories
target_dirs = get_subdirectories(BASE_DIR)
logging.info("Found %d %s leaf subdirectories: %s", len(target_dirs), BASE_DIR, target_dirs)

# Copy files to all target directories
for target_dir in target_dirs:
    full_target_dir = os.path.join(BASE_DIR, target_dir)
    logging.info("Copying files to %s", full_target_dir)
    copy_files(os.path.join(BASE_DIR, SOURCE_DIR), full_target_dir)
