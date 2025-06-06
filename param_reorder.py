#!/usr/bin/python3

"""
Inserts and/or removes parameter files in the configuration sequence defined in the configuration_steps_ArduCopter.json.

It also replaces all occurrences of the old names with the new names
 in all *.py and *.md files in the current directory.
Finally, it renames the actual files on disk.

This file is part of Ardupilot methodic configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2025 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import json
import logging
import os
import re

SEQUENCE_FILENAME = "configuration_steps_ArduCopter.json"
PYTHON_FILES = [
    "param_pid_adjustment_update.py",
    "test_param_pid_adjustment_update.py",
    "annotate_params.py",
    "copy_magfit_pdef_to_template_dirs.py",
]
file_renames = {}

# Add lines like these to rename files
# file_renames["old_name"] = "new_name"
file_renames["00_Default_Parameters.param"] = "00_default.param"


def reorder_param_files(steps: dict) -> dict[str, str]:
    """Reorder parameters and prepare renaming rules."""
    # Iterate over the param_files and rename the keys to be in two-digit prefix ascending order
    param_files = list(steps)
    renames = {}
    for i, old_key in enumerate(param_files, 2):
        new_key = f"{i:02d}_{old_key.split('_', 1)[1]}"
        # Get the value associated with new_key in the file_renames dictionary.
        # If new_key is not found, it will return new_key itself as the default value,
        # effectively leaving it unchanged.
        new_key = file_renames.get(new_key, new_key)
        renames[new_key] = old_key
        if old_key != new_key:
            msg = f"Info: Will rename {old_key} to {new_key}"
            logging.info(msg)
    return renames


def loop_relevant_files(renames: dict[str, str], steps: dict) -> list[str]:
    param_dirs = ["."]
    # Search all *.py, *.json and *.md files in the current directory
    # and replace all occurrences of the old names with the new names
    for root, _dirs, files in os.walk("."):
        for file in files:
            if file.endswith(".param") and root not in param_dirs:
                param_dirs.append(root)
            if file == "LICENSE.md":
                continue
            if file == "vehicle_components.json":
                continue
            if file == SEQUENCE_FILENAME:
                uplate_old_filenames(renames, steps)
            if file in PYTHON_FILES or file.endswith((".md", ".json")):
                update_file_contents(renames, root, file, steps)
    return param_dirs


def uplate_old_filenames(renames: dict[str, str], steps: dict) -> None:
    for new_name, old_name in renames.items():
        if old_name != new_name:
            if "old_filenames" in steps[old_name]:
                if old_name not in steps[old_name]["old_filenames"]:
                    steps[old_name]["old_filenames"].append(old_name)
            else:
                steps[old_name]["old_filenames"] = [old_name]


def update_file_contents(renames: dict[str, str], root: str, file: str, steps: dict) -> None:
    with open(os.path.join(root, file), encoding="utf-8") as handle:
        file_content = handle.read()
    if file.startswith("TUNING_GUIDE_") and file.endswith(".md"):
        for old_filename in renames.values():
            if old_filename not in file_content:
                msg = f"The intermediate parameter file '{old_filename}' is not mentioned in the {file} file"
                logging.error(msg)
    for new_name, old_name in renames.items():
        if "configuration_steps" in file and file.endswith(".json"):
            file_content = update_configuration_steps_json_file_contents(steps, file_content, new_name, old_name)
        else:
            file_content = file_content.replace(old_name, new_name)
    with open(os.path.join(root, file), "w", encoding="utf-8") as handle:
        handle.write(file_content)


def update_configuration_steps_json_file_contents(steps: dict, file_content: str, new_name: str, old_name: str) -> str:
    new_file_content = ""
    curr_filename = ""
    in_steps_block = False

    for line in file_content.splitlines(keepends=True):
        # Track when we enter/exit the "steps" block
        if '"steps": {' in line:
            in_steps_block = True
            new_file_content += line
            continue

        # Only process filenames when inside steps block
        if in_steps_block:
            re_search = re.search(r"^        \"(\w.+)\"", line)
            if re_search:
                curr_filename = re_search.group(1)

        if "old_filenames" in line:
            if curr_filename in steps and "old_filenames" in steps[curr_filename]:
                # WARNING!!! old_filenames can only used once, so we remove it after using it
                old_filenames = str(steps[curr_filename].pop("old_filenames")).replace("'", '"')
                new_file_content += f'            "old_filenames": {old_filenames}'
                if line.endswith(",\n"):
                    new_file_content += ","
                new_file_content += "\n"
            else:
                new_file_content += line
        else:
            new_file_content += line.replace(old_name, new_name)

        # Track end of steps block
        if in_steps_block and line.strip() == "}," and curr_filename:
            in_steps_block = False

    return new_file_content


def rename_file(old_name: str, new_name: str, param_dir: str) -> None:
    """Rename a single file."""
    old_name_path = os.path.join(param_dir, old_name)
    new_name_path = os.path.join(param_dir, new_name)
    if os.path.exists(old_name_path):
        os.rename(old_name_path, new_name_path)
    else:
        msg = f"Could not rename file {old_name_path}, file not found"
        logging.error(msg)


def reorder_actual_files(renames: dict[str, str], param_dirs: list[str]) -> None:
    # Rename the actual files on disk based on renames re-ordering
    for param_dir in param_dirs:
        for new_name, old_name in renames.items():
            rename_file(old_name, new_name, param_dir)


def change_line_endings_for_md_files() -> None:
    # Change line endings of TUNING_GUIDE_*.md, README.md files to CRLF
    for root, _dirs, files in os.walk("."):
        for file in files:
            if (file.startswith(("README", "TUNING_GUIDE_"))) and file.endswith(".md"):
                file_path = os.path.join(root, file)
                with open(file_path, "rb") as handle:
                    content = handle.read()
                content = content.replace(b"\n", b"\r\n")
                with open(file_path, "wb") as handle:
                    handle.write(content)


def main() -> None:
    logging.basicConfig(level="INFO", format="%(asctime)s - %(levelname)s - %(message)s")
    with open(os.path.join("ardupilot_methodic_configurator", SEQUENCE_FILENAME), encoding="utf-8") as f:
        json_content = json.load(f)
    steps = json_content["steps"]
    renames = reorder_param_files(steps)
    param_dirs = loop_relevant_files(renames, steps)
    reorder_actual_files(renames, param_dirs)
    change_line_endings_for_md_files()


if __name__ == "__main__":
    main()
