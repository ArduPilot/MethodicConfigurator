#!/usr/bin/env python3

"""
Create the .pot file by extracting strings from the python source code files.

This file is part of Ardupilot methodic configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2025 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import ast
import datetime
import logging
import os
import shutil
import subprocess
import sys
from typing import Optional


def find_pygettext() -> Optional[str]:
    """Find the available pygettext command."""
    # Try different possible command names
    commands = ["pygettext3", "pygettext.py", "pygettext"]

    for cmd in commands:
        if shutil.which(cmd):
            return cmd

    # Try to find pygettext.py in Python installation
    python_dir = os.path.dirname(sys.executable)
    tools_dir = os.path.join(python_dir, "Tools", "i18n")
    pygettext_path = os.path.join(tools_dir, "pygettext.py")

    if os.path.exists(pygettext_path):
        return f'"{sys.executable}" "{pygettext_path}"'

    return None


def extract_strings_manually(file_paths: list, output_pot: str) -> None:
    """Manually extract translatable strings using AST when pygettext is not available."""
    strings_with_locations = []

    for file_path in file_paths:
        try:
            with open(file_path, encoding="utf-8") as f:
                content = f.read()

            tree = ast.parse(content, filename=file_path)

            for node in ast.walk(tree):
                if isinstance(node, ast.Call):
                    if (
                        isinstance(node.func, ast.Name)
                        and node.func.id == "_"
                        and node.args
                        and isinstance(node.args[0], ast.Constant)
                    ):
                        string_value = node.args[0].value
                        # Normalize path separators to forward slashes like pygettext
                        normalized_path = file_path.replace("\\", "/")
                        location = f"{normalized_path}:{node.lineno}"
                        strings_with_locations.append((string_value, location))
        except Exception as e:
            logging.warning(f"Could not parse {file_path}: {e}")

    # Write POT file with LF line endings
    os.makedirs(os.path.dirname(output_pot), exist_ok=True)
    with open(output_pot, "w", encoding="utf-8", newline="\n") as f:
        # Write header similar to pygettext
        creation_date = datetime.datetime.now().strftime("%Y-%m-%d %H:%M%z")
        f.write("# SOME DESCRIPTIVE TITLE.\n")
        f.write("# Copyright (C) YEAR ORGANIZATION\n")
        f.write("# FIRST AUTHOR <EMAIL@ADDRESS>, YEAR.\n")
        f.write("#\n")
        f.write('msgid ""\n')
        f.write('msgstr ""\n')
        f.write('"Project-Id-Version: PACKAGE VERSION\\n"\n')
        f.write(f'"POT-Creation-Date: {creation_date}\\n"\n')
        f.write('"PO-Revision-Date: YEAR-MO-DA HO:MI+ZONE\\n"\n')
        f.write('"Last-Translator: FULL NAME <EMAIL@ADDRESS>\\n"\n')
        f.write('"Language-Team: LANGUAGE <LL@li.org>\\n"\n')
        f.write('"MIME-Version: 1.0\\n"\n')
        f.write('"Content-Type: text/plain; charset=UTF-8\\n"\n')
        f.write('"Content-Transfer-Encoding: 8bit\\n"\n')
        f.write('"Generated-By: ardupilot_methodic_configurator manual extraction\\n"\n')
        f.write("\n")
        f.write("\n")

        # Group strings by value and collect all locations (remove duplicates)
        string_locations = {}
        first_occurrence = {}
        for string_value, location in strings_with_locations:
            if string_value not in string_locations:
                string_locations[string_value] = set()  # Use set to avoid duplicates
                first_occurrence[string_value] = location
            string_locations[string_value].add(location)

        # Create a sorting key function that properly sorts by filename and line number
        def location_sort_key(location_str):
            parts = location_str.split(":")
            filename = parts[0]
            line_num = int(parts[1]) if len(parts) > 1 else 0
            return (filename, line_num)

        # Write entries sorted by first occurrence location (like pygettext)
        sorted_strings = sorted(string_locations.keys(), key=lambda s: location_sort_key(first_occurrence[s]))

        for string_value in sorted_strings:
            if string_value and string_value.strip():
                # Write location comments sorted by filename and line number
                sorted_locations = sorted(string_locations[string_value], key=location_sort_key)
                for location in sorted_locations:
                    f.write(f"#: {location}\n")

                # Handle multi-line strings properly - preserve newlines but escape quotes
                if "\n" in string_value:
                    # Multi-line string - split into lines
                    f.write('msgid ""\n')
                    lines = string_value.split("\n")
                    for i, line in enumerate(lines):
                        escaped_line = line.replace("\\", "\\\\").replace('"', '\\"')
                        # Only add \n if this is not the last line, or if the last line is followed by a newline in original
                        if i < len(lines) - 1 or string_value.endswith("\n"):
                            f.write(f'"{escaped_line}\\n"\n')
                        elif line:  # Don't write empty last line
                            f.write(f'"{escaped_line}"\n')
                else:
                    # Single line string
                    escaped_string = string_value.replace("\\", "\\\\").replace('"', '\\"')
                    f.write(f'msgid "{escaped_string}"\n')

                f.write('msgstr ""\n')
                f.write("\n")


def extract_strings(directory: str, output_dir: str) -> None:
    file_paths = []
    for root, _dirs, files in os.walk(directory):
        for file in files:
            if file.endswith(".py"):
                file_path = os.path.join(root, file)

                # pylint: disable=too-many-boolean-expressions
                if (
                    "annotate_params" in file
                    or "__init__" in file
                    or "backend_mavftp" in file
                    or "extract_param_defaults" in file
                    or "download_numbers.py" in file
                    or "get_release_stats" in file
                    or "mavftp_example" in file
                    or "param_pid_adjustment_update" in file
                    or "safe_eval" in file
                    or "tempcal_imu" in file
                ):
                    # pylint: enable=too-many-boolean-expressions
                    continue

                file_paths.append(file_path)

    # Sort file paths alphabetically to match pygettext behavior
    file_paths.sort()

    # Find pygettext command
    pygettext_cmd = find_pygettext()
    if not pygettext_cmd:
        logging.warning("pygettext not found. Using fallback manual extraction.")
        output_pot = os.path.join(output_dir, "ardupilot_methodic_configurator.pot")
        extract_strings_manually(file_paths, output_pot)
        filenames = " ".join(file_paths).replace(directory + os.path.sep, "")
        msg = f"POT file created successfully using manual extraction for {filenames}"
        logging.info(msg)
        return

    # Construct the command
    output_pot = os.path.join(output_dir, "ardupilot_methodic_configurator.pot")

    if pygettext_cmd.startswith('"'):
        # Handle the case where we're using python -m or full path
        cmd = pygettext_cmd.split() + ["--keyword=_", f"--output={output_pot}"]
    else:
        cmd = [pygettext_cmd, "--keyword=_", f"--output={output_pot}"]

    cmd += file_paths

    try:
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)  # noqa: S603
        print(result.stdout)  # noqa: T201
    except subprocess.CalledProcessError as e:
        msg = f"An error occurred while running {pygettext_cmd}:\n{e}\nStderr: {e.stderr}"
        logging.error(msg)
        raise
    except FileNotFoundError as e:
        msg = f"Command not found: {pygettext_cmd}\n{e}"
        logging.error(msg)
        raise

    filenames = " ".join(file_paths).replace(directory + os.pathsep, "")
    msg = f"POT file created successfully for {filenames}"
    logging.info(msg)


def main() -> None:
    logging.basicConfig(level="INFO", format="%(asctime)s - %(levelname)s - %(message)s")
    directory_to_scan = "ardupilot_methodic_configurator"
    output_directory = os.path.join(directory_to_scan, "locale")

    extract_strings(directory_to_scan, output_directory)
    msg = f"Internationalization strings extracted and saved to {output_directory}"
    logging.info(msg)


if __name__ == "__main__":
    main()
