"""
ArduPilot parameter dictionary data model.

This module provides the Par class and ParDict class which extends dict[str, Par]
with specialized methods for managing ArduPilot parameters.

SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import logging
import re
from os import path as os_path
from os import popen as os_popen
from sys import exc_info as sys_exc_info
from types import TracebackType
from typing import Callable, Optional, Union

from ardupilot_methodic_configurator import _

# ArduPilot parameter names start with a capital letter and can have capital letters, numbers and _
PARAM_NAME_REGEX = r"^[A-Z][A-Z_0-9]*$"
PARAM_NAME_MAX_LEN = 16


def validate_param_name(param_name: str) -> tuple[bool, str]:
    """
    Validate parameter name according to ArduPilot standards.

    Args:
        param_name: The parameter name to validate

    Returns:
        tuple[bool, str]: (is_valid, error_message)
            is_valid: True if valid, False otherwise
            error_message: Description of validation error, empty if valid

    """
    # Check if parameter name is provided and is a string
    if not param_name or not isinstance(param_name, str):
        return False, _("Parameter name cannot be empty")

    # Check if parameter name exceeds maximum length
    if len(param_name) > PARAM_NAME_MAX_LEN:
        msg = _("Parameter name too long (max %d characters): %s") % (PARAM_NAME_MAX_LEN, param_name)
        return False, msg

    # Check if parameter name matches the required format
    if not re.match(PARAM_NAME_REGEX, param_name):
        msg = _("Invalid parameter name format (must start with capital letter, contain only A-Z, 0-9, _): %s") % param_name
        return False, msg

    return True, ""


def is_within_tolerance(x: float, y: float, atol: float = 1e-08, rtol: float = 1e-04) -> bool:
    """
    Determines if the absolute difference between two numbers is within a specified tolerance.

    This function checks if the absolute difference between `x` and `y` is less than or equal to
    the sum of the absolute tolerance (`atol`) and the product of the relative tolerance (`rtol`)
    and the absolute value of `y`.

    Args:
      x (float): The first number to compare.
      y (float): The second number to compare.
      atol (float, optional): The absolute tolerance. Default is 1e-08.
      rtol (float, optional): The relative tolerance. Default is 1e-04.

    Returns:
      bool: True if the difference is within the tolerance, False otherwise.

    """
    return abs(x - y) <= atol + (rtol * abs(y))


class Par:
    """
    Represents a parameter with a value and an optional comment.

    Attributes:
        value (float): The value of the parameter.
        comment (Optional[str]): An optional comment associated with the parameter.

    """

    def __init__(self, value: float, comment: Optional[str] = None) -> None:
        self.value = value
        self.comment = comment

    def __eq__(self, other: object) -> bool:
        """Equality operation."""
        if isinstance(other, Par):
            return self.value == other.value and self.comment == other.comment
        return False

    def __hash__(self) -> int:
        """Hash operation for using Par objects in sets and as dict keys."""
        return hash((self.value, self.comment))


class ParDict(dict[str, Par]):
    """
    A specialized dictionary for managing ArduPilot parameters.

    This class extends dict[str, Par] to provide additional functionality
    for merging and comparing parameter dictionaries.
    """

    def __init__(self, initial_data: Optional[dict[str, Par]] = None) -> None:
        """
        Initialize the ParDict.

        Args:
            initial_data: Optional initial parameter data to populate the dictionary.

        """
        super().__init__()
        if initial_data is not None:
            self.update(initial_data)

    @staticmethod
    def load_param_file_into_dict(param_file: str) -> "ParDict":
        """
        Loads an ArduPilot parameter file into a ParDict with name, value pairs.

        Args:
            param_file (str): The name of the parameter file to load.

        Returns:
            ParDict: A ParDict containing the parameters from the file.

        """
        parameter_dict = ParDict()
        try:
            with open(param_file, encoding="utf-8-sig") as f_handle:
                for i, f_line in enumerate(f_handle, start=1):
                    original_line = f_line
                    line = f_line.strip()
                    comment = None
                    if not line:
                        continue  # skip empty lines
                    if line[0] == "#":
                        continue  # skip comments
                    if "#" in line:
                        line, comment = line.split("#", 1)  # strip trailing comments
                        comment = comment.strip()
                    if "," in line:
                        # parse mission planner style parameter files
                        parameter, value = line.split(",", 1)
                    elif " " in line:
                        # parse mavproxy style parameter files
                        parameter, value = line.split(" ", 1)
                    elif "\t" in line:
                        parameter, value = line.split("\t", 1)
                    else:
                        msg = _("Missing parameter-value separator: {line} in {param_file} line {i}").format(
                            line=line, param_file=param_file, i=i
                        )
                        raise SystemExit(msg)
                    # Strip whitespace from both parameter name and value immediately after splitting
                    parameter = parameter.strip()
                    value = value.strip()
                    ParDict._validate_parameter(param_file, parameter_dict, i, original_line, comment, parameter, value)
        except UnicodeDecodeError as exp:
            msg = _("Fatal error reading {param_file}, file must be UTF-8 encoded: {exp}").format(
                param_file=param_file, exp=exp
            )
            raise SystemExit(msg) from exp
        return parameter_dict

    @staticmethod
    def _validate_parameter(  # pylint: disable=too-many-arguments, too-many-positional-arguments
        param_file: str,
        parameter_dict: "ParDict",
        i: int,
        original_line: str,
        comment: Union[None, str],
        parameter_name: str,
        value: str,
    ) -> None:
        if len(parameter_name) > PARAM_NAME_MAX_LEN:
            msg = _("Too long parameter name: {parameter_name} in {param_file} line {i}").format(
                parameter_name=parameter_name, param_file=param_file, i=i
            )
            raise SystemExit(msg)
        if not re.match(PARAM_NAME_REGEX, parameter_name):
            msg = _("Invalid characters in parameter name {parameter_name} in {param_file} line {i}").format(
                parameter_name=parameter_name, param_file=param_file, i=i
            )
            raise SystemExit(msg)
        if parameter_name in parameter_dict:
            msg = _("Duplicated parameter {parameter_name} in {param_file} line {i}").format(
                parameter_name=parameter_name, param_file=param_file, i=i
            )
            raise SystemExit(msg)
        try:
            fvalue = float(value)
            parameter_dict[parameter_name] = Par(fvalue, comment)
        except ValueError as exc:
            msg = _("Invalid parameter value {value} in {param_file} line {i}").format(value=value, param_file=param_file, i=i)
            raise SystemExit(msg) from exc
        except OSError as exc:
            _exc_type, exc_value, exc_traceback = sys_exc_info()
            if isinstance(exc_traceback, TracebackType):
                fname = os_path.split(exc_traceback.tb_frame.f_code.co_filename)[1]
                logging.critical("in line %s of file %s: %s", exc_traceback.tb_lineno, fname, exc_value)
                msg = _("Caused by line {i} of file {param_file}: {original_line}").format(
                    i=i, param_file=param_file, original_line=original_line
                )
                raise SystemExit(msg) from exc

    @staticmethod
    def missionplanner_sort(item: str) -> tuple[str, ...]:
        """
        Sorts a parameter name according to the rules defined in the Mission Planner software.

        Args:
            item: The parameter name to sort.

        Returns:
            A tuple representing the sorted parameter name.

        """
        parts = item.split("_")  # Split the parameter name by underscore
        # Compare the parts separately
        return tuple(parts)

    def _format_params(self, file_format: str = "missionplanner") -> list[str]:
        """
        Formats the parameters in this dictionary into a list of strings.

        Each string in the returned list is a formatted representation of a parameter,
        consisting of the parameter's name, its value, and optionally its comment.

        Args:
            file_format (str): Can be "missionplanner" or "mavproxy"

        Returns:
            List[str]: A list of strings, each string representing a parameter
                       in the format "name,value # comment".

        """
        if file_format == "missionplanner":
            sorted_items = dict(sorted(self.items(), key=lambda x: ParDict.missionplanner_sort(x[0])))
            sorted_dict = ParDict(sorted_items)
            formatted_params = [
                (
                    f"{key},{format(parameter.value, '.6f').rstrip('0').rstrip('.')}  # {parameter.comment}"
                    if isinstance(parameter, Par) and parameter.comment
                    else f"{key},{format(parameter.value if isinstance(parameter, Par) else parameter, '.6f').rstrip('0').rstrip('.')}"  # noqa: E501 # pylint: disable=line-too-long
                )
                for key, parameter in sorted_dict.items()
            ]
        elif file_format == "mavproxy":
            sorted_dict = ParDict(dict(sorted(self.items())))
            formatted_params = [
                (
                    f"{key:<16} {parameter.value:<8.6f}  # {parameter.comment}"
                    if isinstance(parameter, Par) and parameter.comment
                    else f"{key:<16} {parameter.value if isinstance(parameter, Par) else parameter:<8.6f}"
                )
                for key, parameter in sorted_dict.items()
            ]
        else:
            msg = _("ERROR: Unsupported file format {file_format}").format(file_format=file_format)
            raise SystemExit(msg)
        return formatted_params

    def export_to_param(
        self, filename_out: str, file_format: str = "missionplanner", content_header: Optional[list[str]] = None
    ) -> None:
        """
        Export parameters to a parameter file.

        Args:
            filename_out: Output filename.
            file_format: File format ("missionplanner" or "mavproxy").
            content_header: Optional list of header lines to include at the top of the file.

        """
        formatted_params = self._format_params(file_format)
        with open(filename_out, "w", encoding="utf-8", newline="\n") as output_file:  # use Linux line endings even on windows
            if content_header:
                output_file.write("\n".join(content_header) + "\n")
            output_file.writelines(line + "\n" for line in formatted_params)

    @staticmethod
    def print_out(formatted_params: list[str], name: str) -> None:
        """
        Print out the contents of the provided list.

        If the list is too large, print only the ones that fit on the screen and
        wait for user input to continue.

        Args:
            formatted_params (List[str]): The list of formatted parameters to print.
            name (str): A descriptive string for the list contents

        Returns:
            None

        """
        if not formatted_params:
            return

        rows_str = "100"  # number of lines to display before waiting for user input

        # Get the size of the terminal
        if __name__ == "__main__":
            rows_str, _columns = os_popen("stty size", "r").read().split()  # noqa: S605, S607

        # Convert rows to integer
        rows = int(rows_str) - 2  # -2 for the next print and the input line

        # Convert rows
        print(  # noqa: T201
            _("\n{name} has {len_formatted_params} parameters:").format(name=name, len_formatted_params=len(formatted_params))
        )
        for i, line in enumerate(formatted_params):
            if i % rows == 0 and __name__ == "__main__":
                input(_("\n{name} list is long hit enter to continue").format(name=name))
                rows_str, _columns = os_popen("stty size", "r").read().split()  # noqa: S605, S607
                rows = int(rows_str) - 2  # -2 for the next print and the input line
            print(line)  # noqa: T201

    def append(self, other: "ParDict") -> None:
        """
        Append parameters from another ParDict.

        Parameters with the same name will be replaced with values from the other dictionary.

        Args:
            other: Another ParDict to append from.

        Raises:
            TypeError: If other is not an ParDict instance.

        """
        if not isinstance(other, ParDict):
            msg = _("Can only append another ParDict instance")
            raise TypeError(msg)

        for param_name, param_value in other.items():
            self[param_name] = param_value

    def remove_if_value_is_similar(
        self, other: "ParDict", tolerance_func: Optional[Callable[[float, float], bool]] = None
    ) -> None:
        """
        Remove parameters from this dictionary if their values match those in another dictionary.

        This method compares only parameter values and ignores comments when determining similarity.
        Parameters from the current dictionary are removed if they have the same name and value
        as parameters in the other dictionary, regardless of comment differences.

        This is particularly useful when comparing flight controller parameters (which have no comments)
        with file parameters (which typically have comments).

        Args:
            other: Another ParDict to compare against.
            tolerance_func: the tolerance function to use to compare values

        Raises:
            TypeError: If other is not an ParDict instance.

        """
        if not isinstance(other, ParDict):
            msg = _("Can only compare with another ParDict instance")
            raise TypeError(msg)

        # Use the shared filtering logic and replace the contents of the current dictionary
        filtered_params = self._get_different_or_missing_params(other, tolerance_func)
        self.clear()
        self.update(filtered_params)

    def get_missing_or_different(
        self, other: "ParDict", tolerance_func: Optional[Callable[[float, float], bool]] = None
    ) -> "ParDict":
        """
        Get parameters that are missing in the other ParDict or have different values.

        Args:
            other: The ParDict to compare against.
            tolerance_func: the tolerance function to use to compare values

        Returns:
            A new ParDict containing parameters that are missing or different.

        Raises:
            TypeError: If other is not an ParDict instance.

        """
        if not isinstance(other, ParDict):
            msg = _("Can only compare with another ParDict instance")
            raise TypeError(msg)

        # Use the shared filtering logic to create a new ParDict
        return ParDict(self._get_different_or_missing_params(other, tolerance_func))

    def _get_different_or_missing_params(
        self, other: "ParDict", tolerance_func: Optional[Callable[[float, float], bool]] = None
    ) -> dict[str, Par]:
        """
        Private helper method to get parameters that are missing or have different values.

        Args:
            other: The ParDict to compare against.
            tolerance_func: the tolerance function to use to compare values

        Returns:
            A dictionary containing parameters that are missing or different.

        """
        return {
            param_name: param_value
            for param_name, param_value in self.items()
            if param_name not in other
            or (
                not tolerance_func(param_value.value, other[param_name].value)
                if tolerance_func
                else param_value.value != other[param_name].value
            )
        }

    @classmethod
    def from_file(cls, param_file: str) -> "ParDict":
        """
        Create a ParDict by loading from a parameter file.

        Args:
            param_file: Path to the parameter file.

        Returns:
            A new ParDict loaded from the file.

        """
        param_dict = ParDict.load_param_file_into_dict(param_file)
        return cls(param_dict)

    @classmethod
    def from_float_dict(cls, param_dict: dict[str, float], default_comment: str = "") -> "ParDict":
        """
        Create a ParDict from a dictionary of parameter names to float values.

        Args:
            param_dict: Dictionary mapping parameter names to float values.
            default_comment: Default comment to apply to all parameters.

        Returns:
            A new ParDict with Par objects created from the float values.

        """
        return cls({param_name: Par(float(param_value), default_comment) for param_name, param_value in param_dict.items()})

    @classmethod
    def from_fc_parameters(cls, fc_params: dict[str, float]) -> "ParDict":
        """
        Create a ParDict from flight controller parameters (dict[str, float]).

        Args:
            fc_params: Dictionary of flight controller parameters.

        Returns:
            A new ParDict with Par objects created from the flight controller parameters.

        """
        return cls.from_float_dict(fc_params)

    def _filter_by_defaults(
        self, default_params: "ParDict", tolerance_func: Optional[Callable[[float, float], bool]] = None
    ) -> "ParDict":
        """
        Filter out parameters that have default values within tolerance.

        Args:
            default_params: ParDict containing default parameter values.
            tolerance_func: Function to check if values are within tolerance.
                           If None, uses exact comparison.

        Returns:
            A new ParDict containing only non-default parameters.

        """
        return ParDict(
            {
                param_name: param_info
                for param_name, param_info in self.items()
                if param_name not in default_params
                or (
                    not tolerance_func(param_info.value, default_params[param_name].value)
                    if tolerance_func
                    else param_info.value != default_params[param_name].value
                )
            }
        )

    def _filter_by_readonly(self, doc_dict: dict) -> "ParDict":
        """
        Filter parameters that are marked as read-only in the documentation.

        Args:
            doc_dict: Documentation dictionary containing parameter metadata.

        Returns:
            A new ParDict containing only read-only parameters.

        """
        return ParDict(
            {
                param_name: param_info
                for param_name, param_info in self.items()
                if param_name in doc_dict and doc_dict[param_name].get("ReadOnly", False)
            }
        )

    def _filter_by_calibration(self, doc_dict: dict) -> "ParDict":
        """
        Filter parameters that are marked as calibration parameters in the documentation.

        Args:
            doc_dict: Documentation dictionary containing parameter metadata.

        Returns:
            A new ParDict containing only calibration parameters.

        """
        return ParDict(
            {
                param_name: param_info
                for param_name, param_info in self.items()
                if param_name in doc_dict and doc_dict[param_name].get("Calibration", False)
            }
        )

    def categorize_by_documentation(
        self,
        doc_dict: dict,
        default_params: "ParDict",
        tolerance_func: Optional[Callable[[float, float], bool]] = None,
    ) -> tuple["ParDict", "ParDict", "ParDict"]:
        """
        Categorize parameters into read-only, calibration, and other non-default parameters.

        Args:
            doc_dict: Documentation dictionary containing parameter metadata.
            default_params: ParDict containing default parameter values.
            tolerance_func: Function to check if values are within tolerance.

        Returns:
            A tuple of three ParDict objects:
            - Non-default read-only parameters
            - Non-default writable calibration parameters
            - Non-default writable non-calibration parameters

        """
        non_default_params = self._filter_by_defaults(default_params, tolerance_func)

        # there are protected members from a locally created object, so it is OK to access them like this
        read_only_params = non_default_params._filter_by_readonly(doc_dict)  # pylint: disable=protected-access # noqa: SLF001
        calibration_params = non_default_params._filter_by_calibration(doc_dict)  # pylint: disable=protected-access # noqa: SLF001

        # Non-calibration parameters are those that are not read-only and not calibration
        other_params = ParDict(
            {
                param_name: param_info
                for param_name, param_info in non_default_params.items()
                if param_name not in read_only_params and param_name not in calibration_params
            }
        )

        return read_only_params, calibration_params, other_params

    def annotate_with_comments(self, comment_lookup: dict[str, str]) -> "ParDict":
        """
        Create a new ParDict with comments added from a lookup table.

        Args:
            comment_lookup: Dictionary mapping parameter names to their comments.

        Returns:
            A new ParDict with updated comments.

        """
        return ParDict(
            {
                param_name: Par(param.value, comment_lookup.get(param_name, param.comment or ""))
                for param_name, param in self.items()
            }
        )
