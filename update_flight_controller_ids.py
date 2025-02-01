#!/usr/bin/env python3

"""
Updates the USB VIDs and PIDs of the supported flight controllers.

This file is part of Ardupilot methodic configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2025 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import io  # Import io for StringIO
import logging
import os
import sys

# Define the base directory to crawl
BASE_DIR = "../ardupilot/libraries/AP_HAL_ChibiOS/hwdef/"

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
    import chibios_hwdef

    logging.info("Module imported successfully.")
except ImportError as e:
    logging.info("ImportError: %s", e)


def remove_suffixes(base_dirname: str, suffixes: list) -> str:
    for suffix in suffixes:
        if base_dirname.endswith(suffix):
            return base_dirname[: -len(suffix)]
    return base_dirname


def process_hwdef_files(base_directory: str) -> dict[str, tuple[int, int, int, str, str]]:
    hwdef_data: dict[str, tuple[int, int, int, str, str]] = {}

    # Walk through the directory
    for dirpath, _dirnames, filenames in os.walk(base_directory):
        for filename in filenames:
            if filename == "hwdef.dat":
                hwdef_file_path = os.path.join(dirpath, filename)
                c = chibios_hwdef.ChibiOSHWDef(
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
                vid_name = str(c.get_config("USB_STRING_MANUFACTURER", default="ArduPilot")).strip('"').strip("'")
                pid_name = str(c.get_config("USB_STRING_PRODUCT", default=dirname)).strip('"').strip("'")
                hwdef_data[dirname] = (numeric_board_id, vid, pid, vid_name, pid_name)
    return hwdef_data


def create_dicts(
    hwdef_data: dict[str, tuple[int, int, int, str, str]],
) -> tuple[dict[int, str], dict[tuple[int, int], str], dict[int, str], dict[int, str]]:
    vid_vendor_dict: dict[int, str] = {}
    vid_pid_product_dict: dict[tuple[int, int], str] = {}
    apj_board_id_name_dict: dict[int, str] = {}
    apj_board_id_vendor_dict: dict[int, str] = {}

    suffixes = ["-bdshot", "-ADSB", "-GPS", "-periph", "-heavy", "-ODID", "-SimOnHardWare"]

    for dirname, (numeric_board_id, vid, pid, vid_name, pid_name) in hwdef_data.items():
        board_name = remove_suffixes(dirname, suffixes)
        # Process USB VID and store the result in it's dictionary
        if vid in vid_vendor_dict:
            if vid_name != vid_vendor_dict[vid]:
                msg = f"VID 0x{vid:04X} has different vendor names: {vid_vendor_dict[vid]} and {vid_name}"
                # raise ValueError(msg)
                logging.error(msg)
        else:
            vid_vendor_dict[vid] = vid_name

        # Process USB PID and store the result in it's dictionary
        if (vid, pid) in vid_pid_product_dict:
            if pid_name != vid_pid_product_dict[(vid, pid)] and vid_vendor_dict[vid] != "ArduPilot":
                msg = (
                    f"VID 0x{vid:04X} PID 0x{pid:04X} has different product names:"
                    f" {vid_pid_product_dict[(vid, pid)]} and {pid_name}"
                )
                # raise ValueError(msg)
                logging.error(msg)
        else:
            vid_pid_product_dict[(vid, pid)] = pid_name

        # Process APJ_BOARD_ID and store the result in it's dictionary
        if numeric_board_id in apj_board_id_name_dict:
            if board_name != apj_board_id_name_dict[numeric_board_id]:
                msg = (
                    f"Warning: Duplicate APJ board ID {numeric_board_id} for different boards:"
                    f" {board_name} and {apj_board_id_name_dict[numeric_board_id]}"
                )
                # raise ValueError(msg)
                logging.error(msg)
        else:
            apj_board_id_name_dict[numeric_board_id] = board_name
            apj_board_id_vendor_dict[numeric_board_id] = vid_name

    return vid_vendor_dict, vid_pid_product_dict, apj_board_id_name_dict, apj_board_id_vendor_dict


def pretty_print_dict(d: dict, indent: int = 4, format_int_in_hex: bool = True) -> str:
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
        # Format the value
        if isinstance(value, dict):
            output.write(" " * indent + f"{formatted_key}: {{\n")
            output.write(pretty_print_dict(value, indent + 4))  # Recursively pretty print nested dicts
            output.write(" " * indent + "},\n")
        elif isinstance(value, int) and format_int_in_hex:
            formatted_value = f"0x{value:X}"
            output.write(" " * indent + f"{formatted_key}: {formatted_value},\n")
        elif isinstance(value, str):
            output.write(" " * indent + f'{formatted_key}: "{value}",\n')
        else:
            output.write(" " * indent + f"{formatted_key}: {value},\n")

    return output.getvalue()


def write_to_file(
    vid_vendor_dict: dict[int, str],
    vid_pid_product_dict: dict[tuple[int, int], str],
    apj_board_id_name_dict: dict[int, str],
    apj_board_id_vendor_dict: dict[int, str],
) -> None:
    directory = "ardupilot_methodic_configurator"
    os.makedirs(directory, exist_ok=True)  # Create the directory if it doesn't exist
    file_path = os.path.join(directory, "middleware_fc_ids.py")

    with open(file_path, "w", encoding="utf-8") as file:
        file.write('"""\n')
        file.write("Defines flight controller vendor and board name depending on hwdef.dat file information.\n")
        file.write("\n")
        file.write("File automatically generated by the update_flight_controller_ids.py script\n")
        file.write("Do not edit directly. ALL CHANGES WILL BE OVERWRITTEN\n")
        file.write("\n")
        file.write("SPDX-FileCopyrightText: 2024-2025 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>\n")
        file.write("\n")
        file.write("SPDX-License-Identifier: GPL-3.0-or-later\n")
        file.write('"""\n')
        file.write("\n")
        file.write("# Maps USB VID to vendor (manufacturer) name\n")
        file.write("VID_VENDOR_DICT: dict[int, str] = {\n")
        file.write(pretty_print_dict(vid_vendor_dict, format_int_in_hex=True))
        file.write("}\n")
        file.write("\n")
        file.write("# Maps USB VID,PID tuple to product name\n")
        file.write("VID_PID_PRODUCT_DICT: dict[tuple[int, int], str] = {\n")
        file.write(pretty_print_dict(vid_pid_product_dict, format_int_in_hex=True))
        file.write("}\n")
        file.write("\n")
        file.write(f"# Maps 16-bit APJ board ID to board name for {len(apj_board_id_name_dict)} supported boards\n")
        file.write("APJ_BOARD_ID_NAME_DICT: dict[int, str] = {\n")
        file.write(pretty_print_dict(apj_board_id_name_dict, format_int_in_hex=False))
        file.write("}\n")
        file.write("\n")
        file.write(f"# Maps 16-bit APJ board ID to board vendor for {len(apj_board_id_name_dict)} supported boards\n")
        file.write("APJ_BOARD_ID_VENDOR_DICT: dict[int, str] = {\n")
        file.write(pretty_print_dict(apj_board_id_vendor_dict, format_int_in_hex=False))
        file.write("}\n")


def main() -> None:
    vid_vendor_dict: dict[int, str] = {}
    vid_pid_product_dict: dict[tuple[int, int], str] = {}
    apj_board_id_name_dict: dict[int, str] = {}
    apj_board_id_vendor_dict: dict[int, str] = {}

    hwdef_data: dict[str, tuple[int, int, int, str, str]] = process_hwdef_files(BASE_DIR)
    vid_vendor_dict, vid_pid_product_dict, apj_board_id_name_dict, apj_board_id_vendor_dict = create_dicts(hwdef_data)
    write_to_file(vid_vendor_dict, vid_pid_product_dict, apj_board_id_name_dict, apj_board_id_vendor_dict)


if __name__ == "__main__":
    main()
