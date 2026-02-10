#!/usr/bin/env python3
# PYTHON_ARGCOMPLETE_OK

"""
Updates the PID adjustment parameters to be factor of the corresponding autotuned or optimized parameters.

Usage:
    ./param_pid_adjustment_update.py -d /path/to/directory optimized_parameter_file.param

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import argparse
import os
import re
from typing import Callable, Union

import argcomplete
from argcomplete.completers import DirectoriesCompleter, FilesCompleter

from ardupilot_methodic_configurator.data_model_par_dict import PARAM_NAME_MAX_LEN, PARAM_NAME_REGEX, Par, ParDict

VERSION = "1.1"


def create_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description="""
Updates PID adjustment parameters values based on the given ADJUSTMENT_FACTOR argument.

It loads three sets of parameters from files in the DIRECTORY directory:
    00_default.param - the (complete) default parameters,
    optimized_param_file - the (complete) optimized parameters, and
    16_pid_adjustment.param - the (intermediate) PID adjustment parameters.
It calculates the PID adjustment parameter values based on the ADJUSTMENT_FACTOR argument.
It updates the intermediate parameter file 16_pid_adjustment.param with parameter comments
explaining how their new value relates to the default parameter value.
""",
    )
    parser.add_argument(  # type: ignore[attr-defined]
        "-d",
        "--directory",
        required=True,
        help="The directory where the parameter files are located.",
    ).completer = DirectoriesCompleter()  # type: ignore[no-untyped-call]
    parser.add_argument(
        "-a",
        "--adjustment_factor",
        type=ranged_type(float, 0.1, 1.2),
        default=0.5,
        help="The adjustment factor to apply to the optimized parameters. Must be in the interval 0.1 to 1.2. Default is 0.5.",
    )
    parser.add_argument(
        "-v",
        "--version",
        action="version",
        version=f"%(prog)s {VERSION}",
        help="Display version information and exit.",
    )
    parser.add_argument(  # type: ignore[attr-defined]
        "optimized_param_file",
        help="The name of the optimized parameter file.",
    ).completer = FilesCompleter(allowednames=[".param"])  # type: ignore[no-untyped-call]
    argcomplete.autocomplete(parser)
    return parser


def ranged_type(value_type: type, min_value: float, max_value: float) -> Callable:
    """
    Returns a function handle to check an ArgumentParser argument range.

    An argument type function for ArgumentParser checking a range:
        min_value <= arg <= max_value
    Args:
        value_type  - value-type to convert arg to
        min_value   - minimum acceptable argument value
        max_value   - maximum acceptable argument value.
    """

    def range_checker(arg: str) -> Union[int, float]:
        try:
            f = value_type(arg)
        except ValueError as exc:
            msg = f"must be a valid {value_type}"
            raise argparse.ArgumentTypeError(msg) from exc
        if f < min_value or f > max_value:
            msg = f"must be within [{min_value}, {max_value}]"
            raise argparse.ArgumentTypeError(msg)
        return f  # type: ignore[no-any-return]

    # Return function handle to checking function
    return range_checker


def load_param_file_with_content(param_file: str) -> tuple[ParDict, list[str]]:
    """
    Load parameter file into ParDict and return the file content as well.

    This is a helper function that extends ParDict.load_param_file_into_dict()
    to also return the original file content lines for header preservation.

    Args:
        param_file: Path to the parameter file.

    Returns:
        A tuple of (ParDict, list of file content lines).

    """
    parameter_dict = ParDict()
    content = []
    try:
        with open(param_file, encoding="utf-8-sig") as f_handle:
            for n, f_line in enumerate(f_handle, start=1):
                line = f_line.strip()
                content.append(line)
                comment = None
                if not line or line.startswith("#"):
                    continue
                if "#" in line:
                    line, comment = line.split("#", 1)
                    comment = comment.strip()
                if "," in line:
                    parameter, value = line.split(",", 1)
                elif " " in line:
                    parameter, value = line.split(" ", 1)
                elif "\t" in line:
                    parameter, value = line.split("\t", 1)
                else:
                    msg = f"Missing parameter-value separator: {line} in {param_file} line {n}"
                    raise SystemExit(msg)
                # Strip whitespace from both parameter name and value immediately after splitting
                parameter = parameter.strip()
                value = value.strip()
                if len(parameter) > PARAM_NAME_MAX_LEN:
                    msg = f"Too long parameter name: {parameter} in {param_file} line {n}"
                    raise SystemExit(msg)
                if not re.match(PARAM_NAME_REGEX, parameter):
                    msg = f"Invalid characters in parameter name {parameter} in {param_file} line {n}"
                    raise SystemExit(msg)
                try:
                    fvalue = float(value)
                except ValueError as exc:
                    msg = f"Invalid parameter value {value} in {param_file} line {n}"
                    raise SystemExit(msg) from exc
                if parameter in parameter_dict:
                    msg = f"Duplicated parameter {parameter} in {param_file} line {n}"
                    raise SystemExit(msg)
                parameter_dict[parameter] = Par(fvalue, comment)
    except UnicodeDecodeError as exp:
        msg = f"Fatal error reading {param_file}, file must be UTF-8 encoded: {exp}"
        raise SystemExit(msg) from exp
    return parameter_dict, content


def update_pid_adjustment_params(
    directory: str, optimized_param_file: str, adjustment_factor: float
) -> tuple[ParDict, str, list[str]]:
    """
    Updates the PID adjustment parameters values based on the given adjustment factor.

    This function loads three sets of parameters from files: the default parameters, the optimized parameters,
    and the PID adjustment parameters.
    It then updates the PID adjustment parameters based on the given adjustment factor.
    Finally, it exports the updated PID adjustment parameters to a file with a comment explaining how their
    new value relates to the default parameter value.

    Args:
        directory (str): The directory where the parameter files are located.
        optimized_param_file (str): The name of the optimized parameter file.
        adjustment_factor (float): The adjustment factor to apply to the optimized parameters.

    """
    default_param_file_path = os.path.join(directory, "00_default.param")
    optimized_param_file_path = os.path.join(directory, optimized_param_file)
    pid_adjustment_file_path = os.path.join(directory, "16_pid_adjustment.param")

    # Load the default parameter file into a dictionary (comment source)
    default_params_dict = ParDict.from_file(default_param_file_path)

    # Load the optimized parameter file into a dictionary (source)
    optimized_params_dict = ParDict.from_file(optimized_param_file_path)

    # Load the PID adjustment parameter file into a dictionary (destination)
    pid_adjustment_params_dict, content = load_param_file_with_content(pid_adjustment_file_path)

    if not default_params_dict:
        msg = f"Failed to load default parameters from {default_param_file_path}"
        raise SystemExit(msg)

    if not optimized_params_dict:
        msg = f"Failed to load optimized parameters from {optimized_param_file_path}"
        raise SystemExit(msg)

    if not pid_adjustment_params_dict:
        msg = f"Failed to load PID adjustment parameters from {pid_adjustment_file_path}"
        raise SystemExit(msg)

    # Update the PID adjustment parameters based on the given adjustment factor
    for param_name, param_value in pid_adjustment_params_dict.items():
        if param_name not in optimized_params_dict:
            msg = f"Parameter {param_name} is not present in {optimized_param_file_path}"
            raise SystemExit(msg)
        if param_name not in default_params_dict:
            msg = f"Parameter {param_name} is not present in {default_param_file_path}"
            raise SystemExit(msg)
        # adjust the parameter value
        param_value.value = optimized_params_dict[param_name].value * adjustment_factor
        if default_params_dict[param_name].value != 0:
            coef = param_value.value / default_params_dict[param_name].value
        else:
            coef = 1.0
            param_value.value = 0  # if the default is zero, let it stay at zero, it is safer
        # explain how the new value relates to the default parameter value
        param_value.comment = (
            f" = {format(coef, '.6f').rstrip('0').rstrip('.')} * ("
            f"{format(default_params_dict[param_name].value, '.6f').rstrip('0').rstrip('.')} default)"
        )

    return pid_adjustment_params_dict, pid_adjustment_file_path, content[0:7]


def main() -> None:
    args = create_argument_parser().parse_args()
    # calculate the parameter values and their comments
    pid_adjustment_params_dict, pid_adjustment_file_path, content_header = update_pid_adjustment_params(
        args.directory, args.optimized_param_file, args.adjustment_factor
    )
    # export the updated PID adjust parameters to a file, preserving the first eight header lines
    pid_adjustment_params_dict.export_to_param(pid_adjustment_file_path, content_header=content_header)


if __name__ == "__main__":
    main()
