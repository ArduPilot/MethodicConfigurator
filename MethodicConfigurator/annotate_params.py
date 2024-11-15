#!/usr/bin/python3

"""
This script fetches online ArduPilot parameter documentation (if not cached) and adds it to the specified file
 or to all *.param and *.parm files in the specified directory.

1. Checks if a local cache of the apm.pdef.xml file exists in the target directory or on the directory of the target file:
 - If it does, the script loads the file content.
 - If it doesn't, the script sends a GET request to the URL to fetch the XML data for the requested vehicle type.
2. Parses the XML data and creates a dictionary of parameter documentation.
3. DELETES all comments that start at the beginning of a line
4. Adds the parameter documentation to the target file or to all *.param,*.parm files in the target directory.

Supports AP_Periph, AntennaTracker, ArduCopter, ArduPlane, ArduSub, Blimp, Heli, Rover and SITL vehicle types
Supports both Mission Planner and MAVProxy file formats
Supports sorting the parameters

Has unit tests with 88% coverage

SPDX-FileCopyrightText: 2024 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import argparse
import glob
import logging
import re
from os import path as os_path
from os import popen as os_popen
from sys import exc_info as sys_exc_info
from sys import exit as sys_exit
from types import TracebackType
from typing import Any, Optional
from xml.etree import ElementTree as ET  # no parsing, just data-structure manipulation

from defusedxml import ElementTree as DET  # just parsing, no data-structure manipulation

# URL of the XML file
BASE_URL = "https://autotest.ardupilot.org/Parameters/"

PARAM_DEFINITION_XML_FILE = "apm.pdef.xml"
LUA_PARAM_DEFINITION_XML_FILE = "24_inflight_magnetometer_fit_setup.pdef.xml"

# ArduPilot parameter names start with a capital letter and can have capital letters, numbers and _
PARAM_NAME_REGEX = r"^[A-Z][A-Z_0-9]*"
PARAM_NAME_MAX_LEN = 16
VERSION = "1.0"

# mypy: disable-error-code="unused-ignore"


def arg_parser():
    parser = argparse.ArgumentParser(
        description="Fetches on-line ArduPilot parameter documentation and adds it to the "
        "specified file or to all *.param and *.parm files in the specified directory."
    )
    parser.add_argument(
        "target",
        help="The target file or directory.",
    )
    parser.add_argument(
        "-d",
        "--delete-documentation-annotations",
        action="store_true",
        help="Delete parameter documentation annotations (comments above parameters). Defaults to %(default)s",
    )
    parser.add_argument(
        "-f",
        "--firmware-version",
        default="latest",
        help="Flight controller firmware version. Defaults to %(default)s.",
    )
    parser.add_argument(
        "-s",
        "--sort",
        choices=["none", "missionplanner", "mavproxy"],
        default="none",
        help="Sort the parameters in the file. Defaults to %(default)s.",
    )
    parser.add_argument(
        "-t",
        "--vehicle-type",
        choices=["AP_Periph", "AntennaTracker", "ArduCopter", "ArduPlane", "ArduSub", "Blimp", "Heli", "Rover", "SITL"],
        default="ArduCopter",
        help="The type of the vehicle. Defaults to %(default)s.",
    )
    parser.add_argument(
        "-m",
        "--max-line-length",
        type=int,
        default=100,
        help="Maximum documentation line length. Defaults to %(default)s.",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Increase output verbosity, print ReadOnly parameter list. Defaults to %(default)s.",
    )
    parser.add_argument(
        "-v",
        "--version",
        action="version",
        version=f"%(prog)s {VERSION}",
        help="Display version information and exit.",
    )

    args = parser.parse_args()

    if args.verbose:
        logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    else:
        logging.basicConfig(level=logging.WARNING, format="%(levelname)s: %(message)s")

    # Custom validation for --max-line-length
    def check_max_line_length(value):
        if value < 50 or value > 300:
            logging.critical("--max-line-length must be in the interval 50 .. 300, not %d", value)
            raise SystemExit("Correct it and try again")
        return value

    args.max_line_length = check_max_line_length(args.max_line_length)

    return args


class Par:
    """
    Represents a parameter with a value and an optional comment.

    Attributes:
        value (float): The value of the parameter.
        comment (Optional[str]): An optional comment associated with the parameter.
    """

    def __init__(self, value: float, comment: Optional[str] = None):
        self.value = value
        self.comment = comment

    def __eq__(self, other: object) -> bool:
        if isinstance(other, Par):
            return self.value == other.value and self.comment == other.comment
        return False

    @staticmethod
    def load_param_file_into_dict(param_file: str) -> dict[str, "Par"]:
        """
        Loads an ArduPilot parameter file into a dictionary with name, value pairs.

        Parameters:
        parm_file (str): The name of the parameter file to load.

        Returns:
        dict: A dictionary containing the parameters from the file.
        """
        parameter_dict: dict[str, Par] = {}
        try:
            with open(param_file, encoding="utf-8") as f_handle:
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
                        raise SystemExit(f"Missing parameter-value separator: {line} in {param_file} line {i}")
                    parameter = parameter.strip()
                    Par.validate_parameter(param_file, parameter_dict, i, original_line, comment, parameter, value)
        except UnicodeDecodeError as exp:
            raise SystemExit(f"Fatal error reading {param_file}: {exp}") from exp
        return parameter_dict

    @staticmethod
    def validate_parameter(param_file, parameter_dict, i, original_line, comment, parameter, value):  # pylint: disable=too-many-arguments
        if len(parameter) > PARAM_NAME_MAX_LEN:
            raise SystemExit(f"Too long parameter name: {parameter} in {param_file} line {i}")
        if not re.match(PARAM_NAME_REGEX, parameter):
            raise SystemExit(f"Invalid characters in parameter name {parameter} in {param_file} line {i}")
        if parameter in parameter_dict:
            raise SystemExit(f"Duplicated parameter {parameter} in {param_file} line {i}")
        try:
            fvalue = float(value.strip())
            parameter_dict[parameter] = Par(fvalue, comment)
        except ValueError as exc:
            raise SystemExit(f"Invalid parameter value {value} in {param_file} line {i}") from exc
        except OSError as exc:
            _exc_type, exc_value, exc_traceback = sys_exc_info()
            if isinstance(exc_traceback, TracebackType):
                fname = os_path.split(exc_traceback.tb_frame.f_code.co_filename)[1]
                logging.critical("in line %s of file %s: %s", exc_traceback.tb_lineno, fname, exc_value)
                raise SystemExit(f"Caused by line {i} of file {param_file}: {original_line}") from exc

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

    @staticmethod
    def format_params(param_dict: dict[str, "Par"], file_format: str = "missionplanner") -> list[str]:  # pylint: disable=too-many-branches
        """
        Formats the parameters in the provided dictionary into a list of strings.

        Each string in the returned list is a formatted representation of a parameter,
        consisting of the parameter's name, its value, and optionally its comment.
        The comment is included if it is present in the parameter's 'Par' object.

        Parameters:
        param_dict (Dict[str, 'Par']): A dictionary of 'Par' objects.
                                       Each key is a parameter name and each value is a 'Par' object.
                                       Par can be a simple float or a Par object with a comment.
        file_format (str): Can be "missionplanner" or "mavproxy"

        Returns:
        List[str]: A list of strings, each string representing a parameter from the input dictionary
                   in the format "name,value # comment".
        """
        if file_format == "missionplanner":
            param_dict = dict(sorted(param_dict.items(), key=lambda x: Par.missionplanner_sort(x[0])))  # sort alphabetically
        elif file_format == "mavproxy":
            param_dict = dict(sorted(param_dict.items()))  # sort in ASCIIbetical order
        else:
            raise SystemExit(f"ERROR: Unsupported file format {file_format}")

        formatted_params = []
        if file_format == "missionplanner":
            for key, parameter in param_dict.items():
                if isinstance(parameter, Par):
                    if parameter.comment:
                        formatted_params.append(
                            f"{key},{format(parameter.value, '.6f').rstrip('0').rstrip('.')}  # {parameter.comment}"
                        )
                    else:
                        formatted_params.append(f"{key},{format(parameter.value, '.6f').rstrip('0').rstrip('.')}")
                else:
                    formatted_params.append(f"{key},{format(parameter, '.6f').rstrip('0').rstrip('.')}")
        elif file_format == "mavproxy":
            for key, parameter in param_dict.items():
                if isinstance(parameter, Par):
                    if parameter.comment:
                        formatted_params.append(f"{key:<16} {parameter.value:<8.6f}  # {parameter.comment}")
                    else:
                        formatted_params.append(f"{key:<16} {parameter.value:<8.6f}")
                else:
                    formatted_params.append(f"{key:<16} {parameter:<8.6f}")
        return formatted_params

    @staticmethod
    def export_to_param(formatted_params: list[str], filename_out: str) -> None:
        """
        Exports a list of formatted parameters to an ArduPilot parameter file.

        Parameters:
        formatted_params (List[str]): The list of formatted parameters to export.
        filename_out (str): The output filename.

        Returns:
        None
        """
        if not formatted_params:
            return
        try:
            # Ensure newline character is LF, even on windows
            with open(filename_out, "w", encoding="utf-8", newline="\n") as output_file:
                for line in formatted_params:
                    output_file.write(line + "\n")
        except OSError as e:
            raise SystemExit(f"ERROR: writing to file {filename_out}: {e}") from e

    @staticmethod
    def print_out(formatted_params: list[str], name: str) -> None:
        """
        Print out the contents of the provided list.
        If the list is too large, print only the ones that fit on the screen and
        wait for user input to continue.

        Parameters:
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
            rows_str, _columns = os_popen("stty size", "r").read().split()  # noqa S607

        # Convert rows to integer
        rows = int(rows_str) - 2  # -2 for the next print and the input line

        # Convert rows
        print(f"\n{name} has {len(formatted_params)} parameters:")
        for i, line in enumerate(formatted_params):
            if i % rows == 0 and __name__ == "__main__":
                input(f"\n{name} list is long hit enter to continue")
                rows_str, _columns = os_popen("stty size", "r").read().split()  # noqa S607
                rows = int(rows_str) - 2  # -2 for the next print and the input line
            print(line)


def get_xml_data(base_url: str, directory: str, filename: str, vehicle_type: str) -> ET.Element:
    """
    Fetches XML data from a local file or a URL.

    Args:
        base_url (str): The base URL for fetching the XML file.
        directory (str): The directory where the XML file is expected.
        filename (str): The name of the XML file.
        vehicle_type (str): The type of the vehicle.

    Returns:
        ET.Element: The root element of the parsed XML data.
    """
    file_path = os_path.join(directory, filename)
    # Check if the locally cached file exists
    if os_path.isfile(file_path):
        # Load the file content relative to the script location
        with open(file_path, encoding="utf-8") as file:
            xml_data = file.read()
    elif os_path.isfile(filename):
        # Load the file content from the current directory
        with open(filename, encoding="utf-8") as file:
            xml_data = file.read()
    else:
        # No locally cached file exists, get it from the internet
        try:
            # pylint: disable=import-outside-toplevel
            from requests import exceptions as requests_exceptions  # type: ignore[import-untyped]
            from requests import get as requests_get
            # pylint: enable=import-outside-toplevel
        except ImportError as exc:
            logging.critical("The requests package was not found")
            logging.critical("Please install it by running 'pip install requests' in your terminal.")
            raise SystemExit("requests package is not installed") from exc
        try:
            # Send a GET request to the URL
            url = base_url + filename
            response = requests_get(url, timeout=5)
            if response.status_code != 200:
                logging.warning("Remote URL: %s", url)
                raise requests_exceptions.RequestException(f"HTTP status code {response.status_code}")
        except requests_exceptions.RequestException as e:
            logging.warning("Unable to fetch XML data: %s", e)
            # Send a GET request to the URL to the fallback (DEV) URL
            try:
                url = BASE_URL + vehicle_type + "/" + PARAM_DEFINITION_XML_FILE
                logging.warning("Falling back to the DEV XML file: %s", url)
                response = requests_get(url, timeout=5)
                if response.status_code != 200:
                    logging.critical("Remote URL: %s", url)
                    raise requests_exceptions.RequestException(f"HTTP status code {response.status_code}")
            except requests_exceptions.RequestException as exp:
                logging.critical("Unable to fetch XML data: %s", exp)
                raise SystemExit("unable to fetch online XML documentation") from exp
        # Get the text content of the response
        xml_data = response.text
        try:
            # Write the content to a file
            with open(os_path.join(directory, filename), "w", encoding="utf-8") as file:
                file.write(xml_data)
        except PermissionError as e:
            logging.critical("Permission denied to write XML data to file: %s", e)
            raise SystemExit("permission denied to write online XML documentation to file") from e

    # Parse the XML data
    return DET.fromstring(xml_data)


def load_default_param_file(directory: str) -> dict[str, "Par"]:
    param_default_dict: dict[str, Par] = {}
    # Load parameter default values if the 00_default.param file exists
    try:
        param_default_dict = Par.load_param_file_into_dict(os_path.join(directory, "00_default.param"))
    except FileNotFoundError:
        logging.warning("Default parameter file 00_default.param not found. No default values will be annotated.")
        logging.warning("Create one by using the command ./extract_param_defaults.py log_file.bin > 00_default.param")
    return param_default_dict


def remove_prefix(text: str, prefix: str) -> str:
    """
    Removes a prefix from a string.

    Args:
        text (str): The original string.
        prefix (str): The prefix to remove.

    Returns:
        str: The string without the prefix.
    """
    if text.startswith(prefix):
        return text[len(prefix) :]
    return text


def split_into_lines(string_to_split: str, maximum_line_length: int) -> list[str]:
    """
    Splits a string into lines of a maximum length.

    Args:
        string_to_split (str): The string to split.
        maximum_line_length (int): The maximum length of a line.

    Returns:
        List[str]: The list of lines.
    """
    doc_lines = re.findall(r".{1," + str(maximum_line_length) + r"}(?:\s|$)", string_to_split)
    # Remove trailing whitespace from each line
    return [line.rstrip() for line in doc_lines]


def create_doc_dict(root: ET.Element, vehicle_type: str, max_line_length: int = 100) -> dict[str, Any]:
    """
    Create a dictionary of parameter documentation from the root element of the parsed XML data.

    Args:
        root (ET.Element): The root element of the parsed XML data.

    Returns:
        Dict[str, Any]: A dictionary of parameter documentation.
    """
    # Dictionary to store the parameter documentation
    doc: dict[str, Any] = {}

    # Use the findall method with an XPath expression to find all "param" elements
    for param in root.findall(".//param"):
        name = param.get("name")
        if name is None:
            continue
        if vehicle_type == "Heli":
            vehicle_type = "Helicopter"
        # Remove the <vehicle_type>: prefix from the name if it exists
        name = remove_prefix(name, vehicle_type + ":")

        human_name = param.get("humanName")
        documentation = param.get("documentation")
        documentation_lst: list[str] = []
        if documentation:
            documentation_lst = split_into_lines(documentation, max_line_length)
        # the keys are the "name" attribute of the "field" sub-elements
        # the values are the text content of the "field" sub-elements
        fields = {field.get("name"): field.text for field in param.findall("field")}
        # if Units and UnitText exist, combine them into a single element
        delete_unit_text = False
        for key, value in fields.items():
            if key == "Units" and "UnitText" in fields:
                fields[key] = f"{value} ({fields['UnitText']})"
                delete_unit_text = True
        if delete_unit_text:
            del fields["UnitText"]
        # the keys are the "code" attribute of the "values/value" sub-elements
        # the values are the text content of the "values/value" sub-elements
        values = {value.get("code"): value.text for value in param.findall("values/value")}

        # Dictionary with "Parameter names" as keys and the values is a
        # dictionary with "humanName", "documentation" attributes and
        # "fields", "values" sub-elements.
        doc[name] = {
            "humanName": human_name,
            "documentation": documentation_lst,
            "fields": fields,
            "values": values,
        }

    return doc


def format_columns(values: dict[str, Any], max_width: int = 105, max_columns: int = 4) -> list[str]:
    """
    Formats a dictionary of values into column-major horizontally aligned columns.
    It uses at most max_columns columns

    Args:
        values (Dict[str, Any]): The dictionary of values to format.
        max_width (int, optional): The maximum number of characters on all columns. Defaults to 105.

    Returns:
        List[str]: The list of formatted strings.
    """
    # Convert the dictionary into a list of strings
    strings = [f"{k}: {v}" for k, v in values.items()]

    if (not strings) or (len(strings) == 0):
        return []

    # Calculate the maximum length of the strings
    max_len = max(len(s) for s in strings)

    num_cols = 1  # At least one column, no matter what max_columns is
    # Determine the number of columns
    # Column distribution will only happen if it results in more than 5 rows
    # The strings will be distributed evenly across up-to max_columns columns.
    for num_cols in range(max_columns, 0, -1):
        if len(strings) // num_cols > 5 and (max_len + 2) * num_cols < max_width:
            break

    # Calculate the column width
    col_width = max_width // num_cols

    num_rows = (len(strings) + num_cols - 1) // num_cols

    formatted_strings = []
    for j in range(num_rows):
        row = []
        for i in range(num_cols):
            if i * num_rows + j < len(strings):
                if i < num_cols - 1 and ((i + 1) * num_rows + j < len(strings)):
                    row.append(strings[i * num_rows + j].ljust(col_width))
                else:
                    row.append(strings[i * num_rows + j])
        formatted_strings.append(" ".join(row))

    return formatted_strings


def extract_parameter_name(item: str) -> str:
    """
    Extract the parameter name from a line. Very simple to use in sorting
    """
    item = item.strip()
    match = re.match(PARAM_NAME_REGEX, item)
    return match.group(0) if match else item


def missionplanner_sort(item: str) -> tuple[str, ...]:
    """
    MissionPlanner parameter sorting function
    """
    # Split the parameter name by underscore
    parts = extract_parameter_name(item).split("_")
    # Compare the parts separately
    return tuple(parts)


def extract_parameter_name_and_validate(line: str, filename: str, line_nr: int) -> str:
    """
    Extracts the parameter name from a line and validates it.
    Args:
        line (str): The line to extract the parameter name from.
    Returns:
        str: The extracted parameter name.
    Raises:
        SystemExit: If the line is invalid or the parameter name is too long or invalid.
    """
    # Extract the parameter name
    match = re.match(PARAM_NAME_REGEX, line)
    if match:
        param_name = match.group(0)
    else:
        logging.critical("Invalid line %d in file %s: %s", line_nr, filename, line)
        raise SystemExit("Invalid line in input file")
    param_len = len(param_name)
    param_sep = line[param_len]  # the character following the parameter name must be a separator
    if param_sep not in {",", " ", "\t"}:
        logging.critical("Invalid parameter name %s on line %d in file %s", param_name, line_nr, filename)
        raise SystemExit("Invalid parameter name")
    if param_len > PARAM_NAME_MAX_LEN:
        logging.critical("Too long parameter name on line %d in file %s", line_nr, filename)
        raise SystemExit("Too long parameter name")
    return param_name


def update_parameter_documentation(
    doc: dict[str, Any],
    target: str = ".",
    sort_type: str = "none",
    param_default_dict: Optional[dict] = None,
    delete_documentation_annotations=False,
) -> None:
    """
    Updates the parameter documentation in the target file or in all *.param,*.parm files of the target directory.

    This function iterates over all the ArduPilot parameter files in the target directory or file.
    For each file, it DELETES all comments that start at the beginning of a line, optionally sorts the
    parameter names and checks if the parameter name is in the dictionary of parameter documentation.
    If it is, it prefixes the line with a comment derived from the dictionary element.
    If it's not, it copies the parameter line 1-to-1.
    After processing all the parameters in a file, it writes the new lines back to the file.

    Args:
        doc (Dict[str, Any]): A dictionary of parameter documentation.
        target (str, optional): The target directory or file. Defaults to '.'.
        sort_type (str, optional): The type of sorting to apply to the parameters.
                                   Can be 'none', 'missionplanner', or 'mavproxy'. Defaults to 'none'.
        param_default_dict (Dict, optional): A dictionary of default parameter values. Defaults to None.
                                              If None, an empty dictionary is used.
    """
    # Check if the target is a file or a directory
    if os_path.isfile(target):
        # If it's a file, process only that file
        param_files = [target]
    elif os_path.isdir(target):
        # If it's a directory, process all .param and .parm files in that directory
        param_files = glob.glob(os_path.join(target, "*.param")) + glob.glob(os_path.join(target, "*.parm"))
    else:
        raise ValueError(f"Target '{target}' is neither a file nor a directory.")

    if param_default_dict is None:
        param_default_dict = {}

    # Iterate over all the target ArduPilot parameter files
    for param_file in param_files:
        if os_path.basename(param_file).endswith("24_inflight_magnetometer_fit_setup.param") and "MAGH_ALT_DELTA" not in doc:
            continue

        # Read the entire file contents
        with open(param_file, encoding="utf-8") as file:
            lines = file.readlines()

        update_parameter_documentation_file(
            doc, sort_type, param_default_dict, param_file, lines, delete_documentation_annotations
        )


def update_parameter_documentation_file(  # pylint: disable=too-many-locals, too-many-arguments
    doc,
    sort_type,
    param_default_dict,
    param_file,
    lines,
    delete_documentation_annotations: bool,
):
    new_lines = []
    if os_path.basename(param_file).endswith("16_pid_adjustment.param"):
        new_lines.extend(lines[0:5])  # copy the first 6 lines verbatim

    total_params = 0
    documented_params = 0
    undocumented_params = []
    is_first_param_in_file = True
    if sort_type == "missionplanner":
        lines.sort(key=missionplanner_sort)
    if sort_type == "mavproxy":
        lines.sort(key=extract_parameter_name)
    for n, f_line in enumerate(lines, start=1):
        line = f_line.strip()
        if not line.startswith("#") and line:
            param_name = extract_parameter_name_and_validate(line, param_file, n)

            if param_name in doc and not delete_documentation_annotations:
                # If the parameter name is in the dictionary,
                #  prefix the line with a comment derived from the dictionary element
                data = doc[param_name]
                prefix_parts = [
                    f"{data['humanName']}",
                ]
                prefix_parts += data["documentation"]
                for key, value in data["fields"].items():
                    prefix_parts.append(f"{key}: {value}")
                prefix_parts += format_columns(data["values"])
                doc_text = "\n# ".join(prefix_parts)
                if param_name in param_default_dict:
                    default_value = format(param_default_dict[param_name].value, ".6f").rstrip("0").rstrip(".")
                    doc_text += f"\n# Default: {default_value}"
                if not is_first_param_in_file:
                    new_lines.append("\n")
                new_lines.append(f"# {doc_text}\n{line}\n")
                documented_params += 1
            else:
                # If the parameter name is in not the dictionary, copy the parameter line 1-to-1
                new_lines.append(f"{line}\n")
                undocumented_params.append(param_name)
            total_params += 1
            is_first_param_in_file = False

    if total_params == documented_params:
        logging.info("Read file %s with %d parameters, all got documented", param_file, total_params)
    else:
        logging.warning(
            "Read file %s with %d parameters, but only %s of which got documented", param_file, total_params, documented_params
        )
        logging.warning("No documentation found for: %s", ", ".join(undocumented_params))

    # Write the new file contents to the file
    with open(param_file, "w", encoding="utf-8", newline="\n") as file:  # Ensure newline character is LF, even on windows
        file.writelines(new_lines)


def print_read_only_params(doc):
    """
    Print the names of read-only parameters.

    Args:
        doc (dict): A dictionary of parameter documentation.
    """
    logging.info("ReadOnly parameters:")
    for param_name, param_value in doc.items():
        if "ReadOnly" in param_value["fields"] and param_value["fields"]["ReadOnly"]:
            logging.info(param_name)


def get_xml_dir(target: str) -> str:
    return target if os_path.isdir(target) else os_path.dirname(os_path.realpath(target))


def get_xml_url(vehicle_type: str, firmware_version: str) -> str:
    vehicle_parm_subdir = {
        "ArduCopter": "versioned/Copter/stable-",
        "ArduPlane": "versioned/Plane/stable-",
        "Rover": "versioned/Rover/stable-",
        "ArduSub": "versioned/Sub/stable-",
        "AntennaTracker": "versioned/Tracker/stable-",
        # Not yet versioned in the https://autotest.ardupilot.org/Parameters server
        "AP_Periph": "versioned/Periph/stable-",
        "Blimp": "versioned/Blimp/stable-",
        "Heli": "versioned/Copter/stable-",
        "SITL": "versioned/SITL/stable-",
    }
    try:
        vehicle_subdir = vehicle_parm_subdir[vehicle_type] + firmware_version
    except KeyError as e:
        raise ValueError(f"Vehicle type '{vehicle_type}' is not supported.") from e

    xml_url = BASE_URL
    xml_url += vehicle_subdir if firmware_version else vehicle_type
    xml_url += "/"
    return xml_url


def parse_parameter_metadata(
    xml_url: str, xml_dir: str, xml_file: str, vehicle_type: str, max_line_length: int
) -> dict[str, Any]:
    xml_root = get_xml_data(xml_url, xml_dir, xml_file, vehicle_type)
    return create_doc_dict(xml_root, vehicle_type, max_line_length)


def main():
    args = arg_parser()
    try:
        xml_url = get_xml_url(args.vehicle_type, args.firmware_version)
        xml_dir = get_xml_dir(args.target)

        doc_dict = parse_parameter_metadata(
            xml_url, xml_dir, PARAM_DEFINITION_XML_FILE, args.vehicle_type, args.max_line_length
        )
        param_default_dict = load_default_param_file(xml_dir)
        update_parameter_documentation(
            doc_dict, args.target, args.sort, param_default_dict, args.delete_documentation_annotations
        )
        if args.verbose:
            print_read_only_params(doc_dict)

        # Annotate lua MAGfit XML documentation into the respective parameter file
        xml_file = LUA_PARAM_DEFINITION_XML_FILE
        target = os_path.join(os_path.dirname(args.target), "24_inflight_magnetometer_fit_setup.param")
        if os_path.isfile(os_path.join(os_path.dirname(args.target), xml_file)):
            doc_dict = parse_parameter_metadata(xml_url, xml_dir, xml_file, args.vehicle_type, args.max_line_length)
            param_default_dict = load_default_param_file(xml_dir)
            update_parameter_documentation(
                doc_dict, target, args.sort, param_default_dict, args.delete_documentation_annotations
            )
        else:
            logging.warning("No LUA MAGfit XML documentation found, skipping annotation of %s", target)

    except (OSError, SystemExit) as exp:
        logging.fatal(exp)
        sys_exit(1)


if __name__ == "__main__":
    main()
