#!/usr/bin/env python3

"""
Insert bulk translations into an existing .po file.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2025 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import argparse
import logging
import os

from ardupilot_methodic_configurator.internationalization import LANGUAGE_CHOICES

TRANSLATED_LANGUAGES = set(LANGUAGE_CHOICES) - {LANGUAGE_CHOICES[0]}  # Remove the default language (en) from the set


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Insert bulk translations into a .po (GNU gettext) file.")

    # pylint: disable=duplicate-code
    parser.add_argument(
        "--lang-code",
        default="all",
        type=str,
        choices=[*TRANSLATED_LANGUAGES, "all"],
        help="The language code for translations. Available choices: %(choices)s. Default is %(default)s",
    )
    # pylint: enable=duplicate-code

    parser.add_argument(
        "--input-file",
        default="missing_translations",
        type=str,
        help="The base name of the file(s) where the missing translations will be read. "
        "This file contains lines in the format 'index:msgid'. Default is %(default)s",
    )

    parser.add_argument(
        "--output-file",
        default="ardupilot_methodic_configurator.po",
        type=str,
        help="The name of the .po file where the translations will be written. "
        "This file will contain lines in the .po (GNU gettext) format. Default is %(default)s",
    )

    return parser.parse_args()


def load_translations(lang_code: str, translations_basename: str) -> list[tuple[int, str]]:
    """
    Load translations for a language from translation files.

    Args:
        lang_code: Language code to load translations for
        translations_basename: Base name of the translation file(s)

    Returns:
        List of tuples containing (line_index, translation_text)

    """
    translations_data: list[str] = []
    main_file = translations_basename + "_" + lang_code + ".txt"
    try:
        logging.debug("Loading translation file: %s", main_file)
        with open(main_file, encoding="utf-8") as f:
            translations_data = f.read().strip().split("\n")
        logging.debug("Successfully loaded %d lines from: %s", len(translations_data), main_file)
    except FileNotFoundError:
        logging.debug("Main translation file %s not found, looking for numbered files", main_file)

        # Try to load numbered files sequentially until one is not found
        n = 1
        while n < 99:
            numbered_file = translations_basename + "_" + lang_code + "_" + str(n) + ".txt"
            if not os.path.exists(numbered_file):
                break

            with open(numbered_file, encoding="utf-8") as f:
                file_data = f.read().strip().split("\n")
                translations_data += file_data
                logging.debug("Successfully loaded %d lines from: %s", len(file_data), numbered_file)
            n += 1

        if not translations_data:
            logging.error("No translation file(s) found for %s", lang_code)
            return []

    # Process the raw data into tuples of (index, translation)
    translations: list[tuple[int, str]] = []
    for data in translations_data:
        index_str, translation = data.split(":", 1)  # Split the index and the translation
        translations.append((int(index_str), translation.strip()))  # Store index and translation as tuple

    return translations


def insert_translations(lang_code: str, translations_basename: str, output_file_name: str) -> None:
    """
    Insert translations into a .po file.

    Args:
        lang_code: Language code to process
        translations_basename: Base name of the translation file(s)
        output_file_name: Name of the output .po file

    """
    po_file = os.path.join(
        "ardupilot_methodic_configurator", "locale", lang_code, "LC_MESSAGES", "ardupilot_methodic_configurator.po"
    )
    logging.debug("Reading .po file: %s", po_file)
    with open(po_file, encoding="utf-8") as f:
        lines = f.readlines()

    # Load translations from files
    logging.debug("Loading translations for language: %s", lang_code)
    translations = load_translations(lang_code, translations_basename)
    if not translations:
        logging.info("No translations found for language: %s", lang_code)
        return

    logging.info("Found %d translations to insert for language: %s", len(translations), lang_code)

    # Insert the translations into the .po file
    insertion_offset = 0  # To track how many lines we've inserted
    for index, translation in translations:
        # Adjust index accounting for previously inserted lines
        adjusted_index = index + insertion_offset

        # Check if the next line is an empty msgstr
        if adjusted_index + 1 < len(lines) and lines[adjusted_index + 1].strip() == 'msgstr ""':
            # Overwrite the empty msgstr line
            lines[adjusted_index + 1] = f'msgstr "{translation}"\n'
        else:
            # Otherwise, insert a new msgstr line
            lines.insert(adjusted_index + 1, f'msgstr "{translation}"\n')
            insertion_offset += 1  # Increment the offset for each insertion

    # Writing back to a new output file
    output_file = os.path.join("ardupilot_methodic_configurator", "locale", lang_code, "LC_MESSAGES", output_file_name)
    logging.debug("Writing updated translations to: %s", output_file)
    with open(output_file, "w", encoding="utf-8", newline="\n") as f:  # use Linux line endings even on windows
        f.writelines(lines)
    logging.debug("Successfully inserted %d translations for language: %s", len(translations), lang_code)


def main() -> None:
    args = parse_arguments()
    logging.basicConfig(level="INFO", format="%(asctime)s - %(levelname)s - %(message)s")
    lang_codes = TRANSLATED_LANGUAGES if args.lang_code == "all" else [args.lang_code]
    logging.info("Starting translation insertion process for languages: %s", list(lang_codes))
    for lang_code in lang_codes:
        logging.debug("Processing language: %s", lang_code)
        insert_translations(lang_code, args.input_file, args.output_file)
        logging.debug("Completed processing language: %s", lang_code)
    logging.info("Translation insertion process completed successfully")


if __name__ == "__main__":
    main()
