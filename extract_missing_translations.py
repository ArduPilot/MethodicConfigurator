#!/usr/bin/env python3

"""
Extract missing translations from a .po file.

This file is part of Ardupilot methodic configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2025 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import argparse
import gettext
import glob
import logging
import os

from ardupilot_methodic_configurator.internationalization import LANGUAGE_CHOICES


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Extract missing translations from a .po (GNU gettext) file.")

    # pylint: disable=duplicate-code
    parser.add_argument(
        "--lang-code",
        default="zh_CN",
        type=str,
        choices=[*LANGUAGE_CHOICES, "test"],
        help="The language code for translations. Available choices: %(choices)s. Default is %(default)s",
    )
    # pylint: enable=duplicate-code

    parser.add_argument(
        "--output-file",
        default="missing_translations",
        type=str,
        help="The base name of the file(s) where the missing translations will be written. "
        "This file will contain lines in the format 'index:msgid'. Default is %(default)s",
    )

    parser.add_argument(
        "--max-translations",
        default=60,
        type=int,
        help="The maximum number of missing translations to write to each output file. Default is %(default)s",
    )

    return parser.parse_args()


def extract_missing_translations(lang_code: str) -> list[tuple[int, str]]:  # noqa: PLR0915 # pylint: disable=too-many-statements,too-many-branches,too-many-locals
    """
    Extract missing translations from a .po file.

    Special handling for empty msgid (msgid "") which represents the header
    Not require msgid to be non-empty
    Detect the end of multiline msgstr entries
    Malformed line detection only apply when not in msgid or msgstr blocks
    A check for trailing untranslated entries at the end of the file

    Args:
        lang_code: The language code for translations.

    Returns:
        A list of tuples containing:
         - line index where to insert the translated string into (msgstr)
         - the untranslated msgid.

    """
    # Set up the translation catalog
    po_file = os.path.join(
        "ardupilot_methodic_configurator", "locale", lang_code, "LC_MESSAGES", "ardupilot_methodic_configurator.po"
    )
    gettext.translation(
        "ardupilot_methodic_configurator",
        localedir=os.path.join("ardupilot_methodic_configurator", "locale"),
        languages=[lang_code],
        fallback=True,
    )

    # Read the .po file entries
    with open(po_file, encoding="utf-8") as f:
        lines = f.readlines()

    missing_translations: list[tuple[int, str]] = []

    # Iterate through lines to find untranslated msgid
    msgid = ""
    msgstr = ""
    msgstr_line_index = -1
    in_msgid = False
    in_msgstr = False
    has_malformed_line = False

    for i, f_line in enumerate(lines):
        line = f_line.strip()
        error_msg = f"Error in line {i}: {line}"

        # Start of a new msgid entry
        if line.startswith("msgid "):
            # If we were in a msgstr before, check if we need to add this entry to missing translations
            if in_msgstr and not has_malformed_line and msgstr == "" and msgid:
                missing_translations.append((msgstr_line_index, msgid))

            # Reset for new entry
            msgid = ""
            msgstr = ""
            in_msgid = True
            in_msgstr = False
            has_malformed_line = False

            # Extract the content of the msgid from this line
            if line.count('"') >= 2:  # Check if there are at least 2 quotes
                try:
                    content = line.split('"', 1)[1].rsplit('"', 1)[0]
                    msgid = content
                except IndexError:
                    logging.error(error_msg)
                    has_malformed_line = True
            # Special case for empty msgid (header or start of multiline)
            elif line == 'msgid ""':
                msgid = ""
            else:
                logging.error(error_msg)
                has_malformed_line = True

        # Continuation of msgid (multiline)
        elif in_msgid and not in_msgstr and line.startswith('"'):
            try:
                content = line.split('"', 1)[1].rsplit('"', 1)[0]
                msgid += content
            except IndexError:
                logging.error(error_msg)
                has_malformed_line = True

        # Start of msgstr
        elif line.startswith("msgstr "):
            in_msgid = False
            in_msgstr = True
            msgstr_line_index = i - 1

            # Extract the content of msgstr from this line
            if line.count('"') >= 2:
                try:
                    content = line.split('"', 1)[1].rsplit('"', 1)[0]
                    msgstr = content
                except IndexError:
                    logging.error(error_msg)
                    has_malformed_line = True
            # Empty msgstr is OK, it's what we're looking for
            elif line == 'msgstr ""':
                msgstr = ""
            else:
                logging.error(error_msg)
                has_malformed_line = True

        # Continuation of msgstr (multiline)
        elif in_msgstr and line.startswith('"'):
            try:
                content = line.split('"', 1)[1].rsplit('"', 1)[0]
                msgstr += content
            except IndexError:
                logging.error(error_msg)
                has_malformed_line = True

        # End of msgstr multi-line (detected by blank line or new msgid or comment)
        elif in_msgstr and (not line or line.startswith(("msgid ", "#"))):
            # Check if the entry was untranslated
            if not has_malformed_line and msgstr == "" and msgid:
                missing_translations.append((msgstr_line_index, msgid))
            in_msgstr = False

        # Malformed line detection
        elif not line.startswith('"') and not line.startswith("#") and line and not in_msgstr and not in_msgid:
            if not line.startswith("msgid"):  # Only log for truly malformed lines
                logging.error(error_msg)
                has_malformed_line = True

    # Check for any untranslated entries at the end of the file
    if in_msgstr and not has_malformed_line and msgstr == "" and msgid:
        missing_translations.append((msgstr_line_index, msgid))

    return missing_translations


def output_to_files(missing_translations: list[tuple[int, str]], output_file_base_name: str, max_translations: int) -> None:
    # Remove any existing output files with the same base name
    existing_files = glob.glob(f"{output_file_base_name}.txt")
    existing_files += glob.glob(f"{output_file_base_name}_*.txt")

    for existing_file in existing_files:
        os.remove(existing_file)

    # Determine the number of files needed
    total_missing = len(missing_translations)
    num_files = (total_missing // max_translations) + (1 if total_missing % max_translations else 0)

    # Write untranslated msgids along with their indices to the output file(s)
    for file_index in range(num_files):
        start_index = file_index * max_translations
        end_index = start_index + max_translations

        # Set the name of the output file based on the index
        current_output_file = output_file_base_name
        current_output_file += f"_{file_index + 1}" if num_files > 1 else ""
        current_output_file += ".txt"

        # Write untranslated msgids along with their indices to the output file
        with open(current_output_file, "w", encoding="utf-8") as f:
            for index, item in missing_translations[start_index:end_index]:
                f.write(f"{index}:{item}\n")


def main() -> None:
    args = parse_arguments()
    logging.basicConfig(level="INFO", format="%(asctime)s - %(levelname)s - %(message)s")
    missing_translations = extract_missing_translations(args.lang_code)
    output_to_files(missing_translations, args.output_file + "_" + args.lang_code, args.max_translations)


if __name__ == "__main__":
    main()
