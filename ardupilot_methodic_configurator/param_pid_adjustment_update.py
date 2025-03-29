#!/usr/bin/python3
# PYTHON_ARGCOMPLETE_OK

"""
Updates the PID adjustment parameters to be factor of the corresponding autotuned or optimized parameters.

Usage:
    ./param_pid_adjustment_update.py -d /path/to/directory optimized_parameter_file.param

This file is part of Ardupilot methodic configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2025 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import argparse
import os
import re
import subprocess
from typing import Callable, Optional, Union

import argcomplete
from argcomplete.completers import DirectoriesCompleter, FilesCompleter

PARAM_NAME_REGEX = r"^[A-Z][A-Z_0-9]*$"
PARAM_NAME_MAX_LEN = 16
VERSION = "1.0"


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
        type=ranged_type(float, 0.1, 0.8),
        default=0.5,
        help="The adjustment factor to apply to the optimized parameters. Must be in the interval 0.1 to 0.8. Default is 0.5.",
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


class Par:
    """
    A class representing a parameter with a value and an optional comment.

    Attributes:
        value (float): The value of the parameter.
        comment (str): An optional comment describing the parameter.

    """

    def __init__(self, value: float, comment: Optional[str] = None) -> None:
        self.value = value
        self.comment = comment

    @staticmethod
    def load_param_file_into_dict(param_file: str) -> tuple[dict[str, "Par"], list[str]]:
        parameter_dict = {}
        content = []
        with open(param_file, encoding="utf-8") as f_handle:
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
        return parameter_dict, content

    @staticmethod
    def export_to_param(param_dict: dict[str, "Par"], filename_out: str, content_header: Optional[list[str]] = None) -> None:
        if content_header is None:
            content_header = []
        with open(filename_out, "w", encoding="utf-8") as output_file:
            if content_header:
                output_file.write("\n".join(content_header) + "\n")
            for key, par in param_dict.items():
                line = f"{key},{format(par.value, '.6f').rstrip('0').rstrip('.')}"
                if par.comment:
                    line += f"  # {par.comment}"
                output_file.write(line + "\n")


def update_pid_adjustment_params(
    directory: str, optimized_param_file: str, adjustment_factor: float
) -> tuple[dict[str, "Par"], str, list[str]]:
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
    default_params_dict, _ = Par.load_param_file_into_dict(default_param_file_path)

    # Load the optimized parameter file into a dictionary (source)
    optimized_params_dict, _ = Par.load_param_file_into_dict(optimized_param_file_path)

    # Load the PID adjustment parameter file into a dictionary (destination)
    pid_adjustment_params_dict, content = Par.load_param_file_into_dict(pid_adjustment_file_path)

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
    Par.export_to_param(pid_adjustment_params_dict, pid_adjustment_file_path, content_header)
    # annotate each parameter with up-to date documentation
    subprocess.run(["./annotate_params.py", os.path.join(args.directory, "16_pid_adjustment.param")], check=True)  # noqa: S603


if __name__ == "__main__":
    main()
