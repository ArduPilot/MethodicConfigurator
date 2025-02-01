#!/usr/bin/env python3

"""
Create the .pot file by extracting strings from the python source code files.

This file is part of Ardupilot methodic configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2025 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import logging
import os
import subprocess


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

    # Construct the command
    output_pot = os.path.join(output_dir, "ardupilot_methodic_configurator.pot")
    cmd = ["pygettext3", "--keyword=_", f"--output={output_pot}"]
    cmd += file_paths

    try:
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)  # noqa: S603
        print(result.stdout)  # noqa: T201
    except subprocess.CalledProcessError as e:
        msg = f"An error occurred while running pygettext3:\n{e}"
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
