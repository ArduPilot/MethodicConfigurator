#!/usr/bin/env python3

"""
Insert bulk translations into an existing .po file.

This file is part of Ardupilot methodic configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2025 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import argparse
import os

from ardupilot_methodic_configurator.internationalization import LANGUAGE_CHOICES


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Insert bulk translations into a .po (GNU gettext) file.")

    # pylint: disable=duplicate-code
    parser.add_argument(
        "--lang-code",
        default="zh_CN",
        type=str,
        choices=LANGUAGE_CHOICES,
        help="The language code for translations. Available choices: %(choices)s. Defaults to %(default)s",
    )
    # pylint: enable=duplicate-code

    parser.add_argument(
        "--input-file",
        default="missing_translations",
        type=str,
        help="The base name of the file(s) where the missing translations will be read. "
        "This file contains lines in the format 'index:msgid'. Defaults to %(default)s",
    )

    parser.add_argument(
        "--output-file",
        default="ardupilot_methodic_configurator_new.po",
        type=str,
        help="The name of the .po file where the translations will be written. "
        "This file will contain lines in the .po (GNU gettext) format. Defaults to %(default)s",
    )

    return parser.parse_args()


def insert_translations(lang_code: str, translations_basename: str, output_file_name: str) -> None:
    po_file = os.path.join(
        "ardupilot_methodic_configurator", "locale", lang_code, "LC_MESSAGES", "ardupilot_methodic_configurator.po"
    )
    with open(po_file, encoding="utf-8") as f:
        lines = f.readlines()

    with open(translations_basename + "_" + lang_code + ".txt", encoding="utf-8") as f:
        translations_data = f.read().strip().split("\n")

    # Prepare to insert translations
    translations: list[tuple[int, str]] = []
    for data in translations_data:
        index_str, translation = data.split(":", 1)  # Split the index and the translation
        translations.append((int(index_str), translation.strip()))  # Store index and translation as tuple

    insertion_offset = 0  # To track how many lines we've inserted
    # To insert the translations correctly
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
    with open(output_file, "w", encoding="utf-8") as f:
        f.writelines(lines)


def main() -> None:
    args = parse_arguments()
    insert_translations(args.lang_code, args.input_file, args.output_file)


if __name__ == "__main__":
    main()
