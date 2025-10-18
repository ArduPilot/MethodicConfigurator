#!/usr/bin/env python3

"""
Extract missing translations from a .po file.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2025 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import argparse
import gettext
import glob
import logging
import os

from ardupilot_methodic_configurator.internationalization import LANGUAGE_CHOICES

TRANSLATED_LANGUAGES = set(LANGUAGE_CHOICES) - {LANGUAGE_CHOICES[0]}  # Remove the default language (en) from the set


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Extract missing translations from a .po (GNU gettext) file.")

    # pylint: disable=duplicate-code
    parser.add_argument(
        "--lang-code",
        default="all",
        type=str,
        choices=[*TRANSLATED_LANGUAGES, "test", "all"],
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

    parser.add_argument(
        "--max-characters",
        default=6000,
        type=int,
        help="The approximate maximum number of characters to include in each output file. Default is %(default)s",
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


def output_to_files(
    missing_translations: list[tuple[int, str]],
    output_file_base_name: str,
    max_translations: int,
    max_characters: int = 6000,
) -> None:
    # Remove any existing output files with the same base name
    existing_files = glob.glob(f"{output_file_base_name}.txt")
    existing_files += glob.glob(f"{output_file_base_name}_*.txt")

    for existing_file in existing_files:
        os.remove(existing_file)

    if max_translations <= 0:
        msg = "max_translations must be greater than zero"
        raise ValueError(msg)

    if max_characters <= 0:
        msg = "max_characters must be greater than zero"
        raise ValueError(msg)

    chunks: list[list[tuple[int, str]]] = []
    current_chunk: list[tuple[int, str]] = []
    current_length = 0

    for index, item in missing_translations:
        line = f"{index}:{item}\n"

        if not current_chunk and len(line) > max_characters:
            logging.warning(
                "Single translation with index %d exceeds max-characters limit (%d > %d)",
                index,
                len(line),
                max_characters,
            )

        if current_chunk and (len(current_chunk) >= max_translations or current_length + len(line) > max_characters):
            chunks.append(current_chunk)
            current_chunk = []
            current_length = 0

        current_chunk.append((index, item))
        current_length += len(line)

    if current_chunk:
        chunks.append(current_chunk)

    num_files = len(chunks)

    for file_index, chunk in enumerate(chunks, start=1):
        current_output_file = output_file_base_name
        current_output_file += f"_{file_index}" if num_files > 1 else ""
        current_output_file += ".txt"

        with open(current_output_file, "w", encoding="utf-8") as f:
            f.writelines(f"{index}:{item}\n" for index, item in chunk)


def main() -> None:
    args = parse_arguments()
    logging.basicConfig(level="INFO", format="%(asctime)s - %(levelname)s - %(message)s")
    lang_codes = TRANSLATED_LANGUAGES if args.lang_code == "all" else [args.lang_code]
    for lang_code in lang_codes:
        missing_translations = extract_missing_translations(lang_code)
        logging.info("Found %d missing translations for language '%s'", len(missing_translations), lang_code)
        if missing_translations:
            output_to_files(
                missing_translations,
                args.output_file + "_" + lang_code,
                args.max_translations,
                args.max_characters,
            )
            logging.debug("Created translation file(s) for language '%s'", lang_code)
        else:
            logging.info("No missing translations found for language '%s', no file created", lang_code)


if __name__ == "__main__":
    main()
