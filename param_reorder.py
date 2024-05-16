#!/usr/bin/python3

"""
This script inserts and/or removes parameter files in the configuration sequence
defined in the ArduCopter_configuration_steps.json file.

It also replaces all occurrences of the old names with the new names
 in all *.py and *.md files in the current directory.
Finally, it renames the actual files on disk.

This file is part of Ardupilot methodic configurator. https://github.com/ArduPilot/MethodicConfigurator

(C) 2024 Amilcar do Carmo Lucas, IAV GmbH

SPDX-License-Identifier:    GPL-3
"""

import os
import json

SEQUENCE_FILENAME = "ArduCopter_configuration_steps.json"

file_renames = {}

# Add lines like these to rename files
# file_renames["old_name"] = "new_name"
file_renames["00_Default_Parameters.param"] = "00_default.param"

def prepare_file_renames(filename):
    """Prepare a list of parameter files from the configuration steps JSON file."""
    with open(os.path.join("MethodicConfigurator", filename), 'r', encoding='utf-8') as f:
        data = json.load(f)
    param_files = []
    for param_file in data:
        param_files.append(param_file)
    return param_files

def reorder_param_files(param_files):
    """Reorder parameters and prepare renaming rules."""
    # Iterate over the param_files and rename the keys to be in two-digit prefix ascending order
    new_dict = {}
    for i, old_key in enumerate(param_files, 2):
        new_key = f"{i:02d}_{old_key.split('_', 1)[1]}"
        # Get the value associated with new_key in the file_renames dictionary.
        # If new_key is not found, it will return new_key itself as the default value,
        # effectively leaving it unchanged.
        new_key = file_renames.get(new_key, new_key)
        new_dict[new_key] = 1
        if old_key != new_key:
            print(f"Info: Will rename {old_key} to {new_key}")
    return new_dict

def loop_relevant_files(param_files, new_dict):
    param_dirs = ['.']
    # Search all *.py, *.json and *.md files in the current directory
    # and replace all occurrences of the old names with the new names
    for root, _dirs, files in os.walk("."):
        for file in files:
            if file.endswith(".param"):
                if root not in param_dirs:
                    param_dirs.append(root)
            update_file_content = file in ["param_pid_adjustment_update.py", "param_pid_adjustment_update_test.py",
                                        "annotate_params.py"] or file.endswith(".md") or file.endswith(".json")
            if file == 'LICENSE.md':
                continue
            if file == 'vehicle_components.json':
                continue
            if update_file_content:
                update_file_contents(param_files, new_dict, root, file)
    return param_dirs

def update_file_contents(param_files, new_dict, root, file):
    with open(os.path.join(root, file), "r", encoding="utf-8") as handle:
        file_content = handle.read()
    if file in ["README.md", "BLOG.md", "BLOG-discuss1.md", "BLOG-discuss2.md"]:
        for param_filename in param_files:
            if param_filename not in file_content:
                print(f"Error: The intermediate parameter file '{param_filename}'" \
                                f" is not mentioned in the {file} file")
    for old_name, new_name in zip(param_files, new_dict.keys()):
        if 'configuration_steps.json' in file:
            new_file_content = ""
            for line in file_content.splitlines(keepends=True):
                if "old_filenames" in line:
                    new_file_content += line
                else:
                    new_file_content += line.replace(old_name, new_name)
            file_content = new_file_content
        else:
            file_content = file_content.replace(old_name, new_name)
    with open(os.path.join(root, file), "w", encoding="utf-8") as handle:
        handle.write(file_content)

def rename_file(old_name, new_name, param_dir):
    """Rename a single file."""
    old_name_path = os.path.join(param_dir, old_name)
    new_name_path = os.path.join(param_dir, new_name)
    if os.path.exists(old_name_path):
        os.rename(old_name_path, new_name_path)
    else:
        print(f"Error: Could not rename file {old_name_path}, file not found")

def reorder_actual_files(param_files, new_dict, param_dirs):
    # Rename the actual files on disk based on new_dict re-ordering
    for param_dir in param_dirs:
        for old_name, new_name in zip(param_files, new_dict.keys()):
            rename_file(old_name, new_name, param_dir)

def rename_actual_files(param_dirs):
    # Rename the actual files on disk based on file_renames
    for param_dir in param_dirs:
        for old_name, new_name in file_renames.items():
            rename_file(old_name, new_name, param_dir)

def change_line_endings_for_md_files():
    # Change line endings of BLOG*.md files to CRLF
    for root, _dirs, files in os.walk("."):
        for file in files:
            if (file.startswith("BLOG") and file.endswith(".md")) or file == "README.md":
                file_path = os.path.join(root, file)
                with open(file_path, "rb") as handle:
                    content = handle.read()
                content = content.replace(b'\n', b'\r\n')
                with open(file_path, "wb") as handle:
                    handle.write(content)

def main():
    param_files = prepare_file_renames(SEQUENCE_FILENAME)
    new_dict = reorder_param_files(param_files)
    param_dirs = loop_relevant_files(param_files, new_dict)
    reorder_actual_files(param_files, new_dict, param_dirs)
    rename_actual_files(param_dirs)
    change_line_endings_for_md_files()

if __name__ == "__main__":
    main()
