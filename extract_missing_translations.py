#!/usr/bin/env python3

"""
This file is part of Ardupilot methodic configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import argparse
import gettext
import glob
import os


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Extract missing translations from a .po (GNU gettext) file.")

    # Add argument for language code
    parser.add_argument(
        "--lang-code",
        default="zh_CN",
        type=str,
        help="The language code for which to extract missing translations (e.g., 'zh_CN', 'pt'). Defaults to %(default)s",
    )

    # Add argument for output file
    parser.add_argument(
        "--output-file",
        default="missing_translation",
        type=str,
        help="The base name of the file(s) where the missing translations will be written. "
        "This file will contain lines in the format 'index:msgid'. Defaults to %(default)s",
    )

    # Add argument for maximum number of translations per output file
    parser.add_argument(
        "--max-translations",
        default=80,
        type=int,
        help="The maximum number of missing translations to write to each output file. Defaults to %(default)s",
    )

    return parser.parse_args()


def extract_missing_translations(lang_code: str) -> list[tuple[int, str]]:
    # Set up the translation catalog
    po_file = os.path.join("MethodicConfigurator", "locale", lang_code, "LC_MESSAGES", "MethodicConfigurator.po")
    language = gettext.translation(
        "MethodicConfigurator", localedir="MethodicConfigurator\\locale", languages=[lang_code], fallback=True
    )

    # Read the .po file entries
    with open(po_file, encoding="utf-8") as f:
        lines = f.readlines()

    missing_translations: list[tuple[int, str]] = []

    # Iterate through lines to find untranslated msgid
    msgid = ""
    in_msgid = False
    for i, f_line in enumerate(lines):
        line = f_line.strip()

        if line.startswith("msgid "):
            msgid = ""
            in_msgid = True

        if in_msgid and not line.startswith("msgstr "):
            line_split = line.split('"')
            if len(line_split) > 1:
                msgid += '"'.join(line_split[1:-1])  # Get the msgid string
            else:
                print(f"Error on line {i}")
            continue

        if in_msgid and line.startswith("msgstr "):
            in_msgid = False
            # escape \ characters in a string
            # msgid_escaped = msgid.replace("\\", "\\\\")
            msgid_escaped = msgid
            # Check if the translation exists
            if language.gettext(msgid_escaped) == msgid:  # If translation is the same as msgid, it's missing
                missing_translations.append((i - 1, msgid))

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
    missing_translations = extract_missing_translations(args.lang_code)
    output_to_files(missing_translations, args.output_file, args.max_translations)


if __name__ == "__main__":
    main()
