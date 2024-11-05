#!/usr/bin/env python3

'''
This file is part of Ardupilot methodic configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
'''

import os
import shutil

# Source directory containing the files to copy
SOURCE_DIR = "ArduCopter\\diatone_taycan_mxc\\4.6.x-params"

# Files to copy
files_to_copy = ["50_optical_flow_setup.param", "51_optical_flow_results.param", "52_use_optical_flow_instead_of_gnss.param"]

# Base directory for vehicle templates
BASE_DIR = "vehicle_templates"

# Function to get all subdirectories excluding the source (do not copy onto itself)
def get_subdirectories(base_dir, exclude_source=True):
    subdirs = []
    for root, dirs, _ in os.walk(base_dir):
        rel_dir = os.path.relpath(root, base_dir)
        if exclude_source and rel_dir == SOURCE_DIR:
            continue
        if len(dirs) == 0:  # Check if the directory is a leaf directory
            subdirs.append(rel_dir)
    return subdirs

# Function to copy files
def copy_files(source, target):
    for file in files_to_copy:
        source_path = os.path.join(source, file)
        target_path = os.path.join(target, file)

        try:
            shutil.copy2(source_path, target_path)
            print(f"Copied {file} to {target}")
        except Exception as e:  # pylint: disable=broad-except
            print(f"Error copying {file} to {target}: {str(e)}")

# Get all ArduCopter subdirectories
target_dirs = get_subdirectories(BASE_DIR)
print(f"Found {len(target_dirs)} {BASE_DIR} leaf subdirectories: {target_dirs}")

# Copy files to all target directories
for target_dir in target_dirs:
    full_target_dir = os.path.join(BASE_DIR, target_dir)
    print(f"Copying files to {full_target_dir}")
    copy_files(os.path.join(BASE_DIR, SOURCE_DIR), full_target_dir)
