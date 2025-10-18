#!/usr/bin/env python3

"""
Updates the USB VIDs and PIDs of the supported flight controllers.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2025 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import io  # Import io for StringIO
import logging
import os
import sys
from typing import Union

# Define the base directory to crawl
BASE_DIR = "../ardupilot/libraries/AP_HAL_ChibiOS/hwdef/"
NON_FC_SUFIXES = (
    "-ADSB",
    "Airspeed",
    "Compass",
    "-ESC",
    "-ETH",
    "GPS",
    "-heavy",
    "-I2C",
    "-ODID",
    "-periph",
    "-Periph",
    "-SimOnHardWare",
)
NON_FC_PREFIXES = (
    "iomcu",
    "TBS-L431",
)
HwdefDict = dict[str, tuple[int, int, int, str, str, str]]

logging.basicConfig(level="INFO", format="%(asctime)s - %(levelname)s - %(message)s")

# Add ../ardupilot/libraries/AP_HAL_ChibiOS/hwdef/scripts to the PYTHON path
scripts_path = os.path.abspath(os.path.join(BASE_DIR, "scripts"))
init_file_path = os.path.join(scripts_path, "__init__.py")

# Check if the __init__.py file exists
if not os.path.exists(init_file_path):
    # Create the __init__.py file
    with open(init_file_path, "w", encoding="utf-8") as init_file:
        init_file.write("# This __init__.py was created automatically\n")
    logging.info("Created __init__.py at: %s", init_file_path)
else:
    logging.info("__init__.py already exists at: %s", init_file_path)
sys.path.append(scripts_path)

try:
    import chibios_hwdef  # pyright: ignore[reportMissingImports]

    logging.info("Module imported successfully.")
except ImportError as e:
    logging.error("ImportError: %s", e)


def process_hwdef_files(base_directory: str) -> HwdefDict:
    hwdef_data: HwdefDict = {}

    # Walk through the directory
    for dirpath, _dirnames, filenames in os.walk(base_directory):
        for filename in filenames:
            if filename == "hwdef.dat":
                hwdef_file_path = os.path.join(dirpath, filename)
                c = chibios_hwdef.ChibiOSHWDef(  # pyright: ignore[reportPossiblyUnboundVariable]
                    outdir="/tmp",  # noqa: S108
                    bootloader=False,
                    signed_fw=False,
                    hwdef=[hwdef_file_path],
                    default_params_filepath=None,
                    quiet=True,
                )
                c.process_hwdefs()

                # The directory name is unique, hence it will be used as a dictionary key
                dirname = os.path.basename(dirpath)
                numeric_board_id = int(c.get_numeric_board_id())
                vid, pid = c.get_USB_IDs()
                vid = int(vid)
                pid = int(pid)
                vid_name = str(c.get_config("USB_STRING_MANUFACTURER", default="ArduPilot")).strip('"').strip("'")
                pid_name = str(c.get_config("USB_STRING_PRODUCT", default=dirname)).strip('"').strip("'")
                mcu_series = str(c.mcu_series)
                hwdef_data[dirname] = (numeric_board_id, vid, pid, vid_name, pid_name, mcu_series)
    # Sort the dictionary by the (dirname) key, so that python 3.13 produces similar results to python 3.12
    return dict(sorted(hwdef_data.items(), key=lambda x: x[0].lower()))


def capitalize_mcu_series(series: str) -> str:
    """
    Capitalize MCU series name while preserving trailing x characters.

    Examples:
        >>> capitalize_mcu_series("stm32f4xx")
        'STM32F4xx'
        >>> capitalize_mcu_series("stm32h7")
        'STM32H7'

    """
    # Split into main part and trailing x's
    main_str = series.rstrip("x")
    x_count = len(series) - len(main_str)

    # Capitalize main part and add back x's
    return main_str.upper() + "x" * x_count


def update_board_id_dict(
    board_id: int, new_value: str, existing_dict: dict[int, list[str]], dict_name: str
) -> dict[int, list[str]]:
    """
    Update a board ID dictionary with new values, logging duplicates.

    Args:
        board_id: The numeric board ID to update
        new_value: The new value to add to the list for this board ID
        existing_dict: The dictionary to update
        dict_name: Name of dictionary for error messages

    Returns:
        Updated dictionary

    """
    if board_id in existing_dict:
        if new_value not in existing_dict[board_id]:
            msg = (
                f"Warning: Duplicate APJ board ID {board_id} for different {dict_name}:"
                f" {', '.join(existing_dict[board_id])} and {new_value}"
            )
            logging.error(msg)
            existing_dict[board_id].append(new_value)
    else:
        existing_dict[board_id] = [new_value]
    return existing_dict


def remove_suffixes(base_dirname: str) -> str:
    suffixes = ["-bdshot", "-DShot"]
    for suffix in suffixes:
        if base_dirname.endswith(suffix):
            return base_dirname[: -len(suffix)]
    return base_dirname


def create_dicts(  # pylint: disable=too-many-locals
    hwdef_data: HwdefDict,
) -> tuple[
    dict[int, list[str]], dict[tuple[int, int], list[str]], dict[int, list[str]], dict[int, list[str]], dict[int, list[str]]
]:
    vid_vendor_dict: dict[int, list[str]] = {}
    vid_pid_product_dict: dict[tuple[int, int], list[str]] = {}
    apj_board_id_name_dict: dict[int, list[str]] = {}
    apj_board_id_vendor_dict: dict[int, list[str]] = {}
    apj_board_id_mcu_series_dict: dict[int, list[str]] = {}

    for dirname, (numeric_board_id, vid, pid, vid_name, pid_namef, mcu_series) in hwdef_data.items():
        if (
            dirname.startswith(NON_FC_PREFIXES)
            or dirname.endswith(NON_FC_SUFIXES)
            or mcu_series.lower().startswith(("stm32f1", "stm32f3", "stm32g4", "stm32l431"))
            or (numeric_board_id == 1062 and dirname != "MatekL431")  # these AP_Periph are not an FC
        ):
            continue  # Skip IOMCU boards, AP_Periph boards, GPS boards

        board_name = remove_suffixes(dirname)
        pid_name = remove_suffixes(pid_namef)

        # Process USB VID and store the result in it's dictionary
        if vid in vid_vendor_dict:
            if vid_name not in vid_vendor_dict[vid]:
                msg = f"VID 0x{vid:04X} has different vendor names: {', '.join(vid_vendor_dict[vid])} and {vid_name}"
                # raise ValueError(msg)
                logging.error(msg)
                vid_vendor_dict[vid].append(vid_name)
        else:
            vid_vendor_dict[vid] = [vid_name]

        # Process USB PID and store the result in it's dictionary
        if (vid, pid) in vid_pid_product_dict:
            if pid_name not in vid_pid_product_dict[(vid, pid)]:
                msg = (
                    f"VID 0x{vid:04X} PID 0x{pid:04X} has different product names:"
                    f" {', '.join(vid_pid_product_dict[(vid, pid)])} and {pid_name}"
                )
                # raise ValueError(msg)
                logging.error(msg)
                vid_pid_product_dict[(vid, pid)].append(pid_name)
        else:
            vid_pid_product_dict[(vid, pid)] = [pid_name]

        apj_board_id_name_dict = update_board_id_dict(numeric_board_id, board_name, apj_board_id_name_dict, "board names")

        apj_board_id_vendor_dict = update_board_id_dict(numeric_board_id, vid_name, apj_board_id_vendor_dict, "vendors")

        apj_board_id_mcu_series_dict = update_board_id_dict(
            numeric_board_id, mcu_series, apj_board_id_mcu_series_dict, "MCU series"
        )

    # apj_board_id_name_dict = dict(sorted(apj_board_id_name_dict.items()))
    # apj_board_id_vendor_dict = dict(sorted(apj_board_id_vendor_dict.items()))
    # apj_board_id_mcu_series_dict = dict(sorted(apj_board_id_mcu_series_dict.items()))

    return (
        vid_vendor_dict,
        vid_pid_product_dict,
        apj_board_id_name_dict,
        apj_board_id_vendor_dict,
        apj_board_id_mcu_series_dict,
    )


def pretty_print_dict(
    d: dict, indent: int = 4, format_int_in_hex: bool = True, board_name: Union[None, dict[int, list[str]]] = None
) -> str:
    """Pretty prints a dictionary, formatting integers in hexadecimal to a string."""
    output = io.StringIO()
    for key, value in d.items():
        # Format the key
        formatted_key = (
            f"0x{key:04X}"
            if isinstance(key, int) and format_int_in_hex
            else f"(0x{key[0]:04X}, 0x{key[1]:04X})"
            if isinstance(key, tuple) and len(key) == 2 and all(isinstance(k, int) for k in key) and format_int_in_hex
            else f'"{key}"'
            if isinstance(key, str)
            else key
        )
        comment: str = ""
        # Format the (optional) board name to be used as a comment
        if board_name is not None:
            if key in board_name:  # key is the board ID
                comment = f"  # {', '.join(board_name[key])}"
            else:  # key is the MCU series
                comment = f"  # {', '.join([', '.join(board_name[val]) for val in value])}"
        # Format the value
        if isinstance(value, dict):
            output.write(" " * indent + f"{formatted_key}: {{\n")
            output.write(pretty_print_dict(value, indent + 4))  # Recursively pretty print nested dicts
            output.write(" " * indent + "},\n")
        elif isinstance(value, int) and format_int_in_hex:
            formatted_value = f"0x{value:X}"
            output.write(" " * indent + f"{formatted_key}: {formatted_value},\n")
        elif isinstance(value, str):
            output.write(" " * indent + f'{formatted_key}: "{value}",{comment}\n')
        elif isinstance(value, list) and all(isinstance(x, str) for x in value):
            quoted_values = [f'"{x}"' for x in value]
            output.write(" " * indent + f"{formatted_key}: [{', '.join(quoted_values)}],{comment}\n")
        else:
            output.write(" " * indent + f"{formatted_key}: {value},{comment}\n")

    return output.getvalue()


def write_to_file(  # pylint: disable=too-many-arguments, too-many-positional-arguments
    vid_vendor_dict: dict[int, list[str]],
    vid_pid_product_dict: dict[tuple[int, int], list[str]],
    apj_board_id_name_dict: dict[int, list[str]],
    apj_board_id_vendor_dict: dict[int, list[str]],
    apj_board_id_mcu_series_dict: dict[int, list[str]],
    mcu_series_apj_board_id_dict: dict[str, list[int]],
) -> None:
    directory = "ardupilot_methodic_configurator"
    os.makedirs(directory, exist_ok=True)  # Create the directory if it doesn't exist
    file_path = os.path.join(directory, "data_model_fc_ids.py")

    nr_supported_boards = sum(len(boards) for boards in apj_board_id_name_dict.values())

    with open(file_path, "w", encoding="utf-8", newline="\n") as file:
        file.write('"""\n')
        file.write("Defines flight controller vendor, board name and MCU series depending on hwdef.dat file information.\n")
        file.write("\n")
        file.write("File automatically generated by the update_flight_controller_ids.py script\n")
        file.write("Do not edit directly. ALL CHANGES WILL BE OVERWRITTEN\n")
        file.write("\n")
        file.write("SPDX-FileCopyrightText: 2024-2025 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>\n")
        file.write("\n")
        file.write("SPDX-License-Identifier: GPL-3.0-or-later\n")
        file.write('"""\n')
        file.write("\n")
        file.write("# ruff: noqa: E501\n")
        file.write("# fmt: off\n")
        file.write("# pylint: disable=line-too-long\n")
        file.write("\n")
        file.write("# Maps USB VID to vendor(s) (manufacturer) name\n")
        file.write("VID_VENDOR_DICT: dict[int, list[str]] = {\n")
        file.write(pretty_print_dict(vid_vendor_dict, format_int_in_hex=True))
        file.write("}\n")
        file.write("\n")
        file.write("# Maps USB VID,PID tuple to product name(s)\n")
        file.write("VID_PID_PRODUCT_DICT: dict[tuple[int, int], list[str]] = {\n")
        file.write(pretty_print_dict(vid_pid_product_dict, format_int_in_hex=True))
        file.write("}\n")
        file.write("\n")
        file.write(f"# Maps 16-bit APJ board ID to board name(s) for {nr_supported_boards} supported boards\n")
        file.write("APJ_BOARD_ID_NAME_DICT: dict[int, list[str]] = {\n")
        file.write(pretty_print_dict(apj_board_id_name_dict, format_int_in_hex=False))
        file.write("}\n")
        file.write("\n")
        file.write(f"# Maps 16-bit APJ board ID to board vendor for {nr_supported_boards} supported boards\n")
        file.write("APJ_BOARD_ID_VENDOR_DICT: dict[int, list[str]] = {\n")
        file.write(pretty_print_dict(apj_board_id_vendor_dict, format_int_in_hex=False, board_name=apj_board_id_name_dict))
        file.write("}\n")
        file.write("\n")
        file.write(f"# Maps 16-bit APJ board ID to MCU series for {nr_supported_boards} supported boards\n")
        file.write("APJ_BOARD_ID_MCU_SERIES_DICT: dict[int, list[str]] = {\n")
        file.write(pretty_print_dict(apj_board_id_mcu_series_dict, format_int_in_hex=False, board_name=apj_board_id_name_dict))
        file.write("}\n")
        file.write("\n")
        file.write(f"# Maps MCU series to 16-bit APJ board ID for {nr_supported_boards} supported boards\n")
        file.write("MCU_SERIES_APJ_BOARD_ID_DICT: dict[str, list[int]] = {\n")
        file.write(pretty_print_dict(mcu_series_apj_board_id_dict, format_int_in_hex=False, board_name=apj_board_id_name_dict))
        file.write("}\n")


def main() -> None:
    vid_vendor_dict: dict[int, list[str]] = {}
    vid_pid_product_dict: dict[tuple[int, int], list[str]] = {}
    apj_board_id_name_dict: dict[int, list[str]] = {}
    apj_board_id_vendor_dict: dict[int, list[str]] = {}
    apj_board_id_mcu_series_dict: dict[int, list[str]] = {}
    # Dict mapping MCU series to list of board IDs
    mcu_series_apj_board_id_dict: dict[str, list[int]] = {}

    hwdef_data: HwdefDict = process_hwdef_files(BASE_DIR)
    vid_vendor_dict, vid_pid_product_dict, apj_board_id_name_dict, apj_board_id_vendor_dict, apj_board_id_mcu_series_dict = (
        create_dicts(hwdef_data)
    )

    # Iterate through the original dict and build the new mapping
    for board_id, mcu_series in apj_board_id_mcu_series_dict.items():
        for mcu_serie in mcu_series:
            if mcu_serie not in mcu_series_apj_board_id_dict:
                mcu_series_apj_board_id_dict[mcu_serie] = []
            mcu_series_apj_board_id_dict[mcu_serie].append(board_id)

    # Sort the board ID lists for consistency
    # for mcu_series in mcu_series_apj_board_id_dict.keys():
    #     mcu_series_apj_board_id_dict[mcu_series].sort()
    mcu_series_apj_board_id_dict = dict(sorted(mcu_series_apj_board_id_dict.items()))

    write_to_file(
        vid_vendor_dict,
        vid_pid_product_dict,
        apj_board_id_name_dict,
        apj_board_id_vendor_dict,
        apj_board_id_mcu_series_dict,
        mcu_series_apj_board_id_dict,
    )


if __name__ == "__main__":
    main()
