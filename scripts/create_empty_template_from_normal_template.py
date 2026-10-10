#!/usr/bin/env python3

"""
Create an empty vehicle template from a normal vehicle template.

# This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

# SPDX-FileCopyrightText: 2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

# SPDX-License-Identifier: GPL-3.0-or-later
"""

import argparse
import sys
from pathlib import Path
from shutil import copy2

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# pylint: disable=wrong-import-position
from ardupilot_methodic_configurator.data_model_par_dict import Par, ParamFileError, ParDict  # noqa: E402

DEFAULT_PARAM_FILENAME = "00_default.param"
MISSING_DEFAULT_COMMENT = "No default value found in 00_default.param; source value retained"


def create_empty_template_from_normal_template(source_directory: Path, destination_directory: Path) -> None:
    """
    Create a directory whose parameter files use their documented defaults.

    Values found in ``00_default.param`` replace the corresponding values in each
    other parameter file. Parameters without a default entry retain their source
    value and receive a comment explaining why. Other source comments are removed.
    """
    source_directory = source_directory.resolve()
    destination_directory = destination_directory.resolve()

    if not source_directory.is_dir():
        message = f"Source vehicle directory does not exist: {source_directory}"
        raise NotADirectoryError(message)
    if destination_directory.exists():
        message = f"Destination directory already exists: {destination_directory}"
        raise FileExistsError(message)
    if destination_directory.is_relative_to(source_directory):
        message = "Destination directory must not be inside the source vehicle directory"
        raise ValueError(message)

    default_param_file = source_directory / DEFAULT_PARAM_FILENAME
    if not default_param_file.is_file():
        message = f"Source vehicle directory is missing {DEFAULT_PARAM_FILENAME}: {source_directory}"
        raise FileNotFoundError(message)

    default_parameters = ParDict.load_param_file_into_dict(str(default_param_file))
    source_param_files = sorted(source_directory.glob("*.param"))

    destination_directory.mkdir(parents=True)
    copy2(default_param_file, destination_directory / DEFAULT_PARAM_FILENAME)

    for source_param_file in source_param_files:
        if source_param_file.name == DEFAULT_PARAM_FILENAME:
            continue

        source_parameters = ParDict.load_param_file_into_dict(str(source_param_file))
        defaulted_parameters = ParDict(
            {
                name: Par(
                    default_parameters[name].value if name in default_parameters else parameter.value,
                    None if name in default_parameters else MISSING_DEFAULT_COMMENT,
                )
                for name, parameter in source_parameters.items()
            }
        )
        defaulted_parameters.export_to_param(str(destination_directory / source_param_file.name))


def main() -> None:
    """Parse the two directory arguments and create an empty template copy."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source_directory", type=Path, help="Existing normal AMC vehicle template directory")
    parser.add_argument("destination_directory", type=Path, help="New empty AMC vehicle template directory to create")
    args = parser.parse_args()

    try:
        create_empty_template_from_normal_template(args.source_directory, args.destination_directory)
    except (FileExistsError, FileNotFoundError, NotADirectoryError, OSError, ParamFileError, ValueError) as error:
        parser.error(str(error))


if __name__ == "__main__":
    main()
