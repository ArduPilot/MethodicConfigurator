#!/usr/bin/env python3

"""
This file is part of Ardupilot methodic configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import argparse
import os


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Insert bulk translations into a .po (GNU gettext) file.")

    # Add argument for language code
    parser.add_argument(
        "--lang-code",
        default="zh_CN",
        type=str,
        help="The language code into which insert bulk translations (e.g., 'zh_CN', 'pt'). Defaults to %(default)s",
    )

    # Add argument for translations file
    parser.add_argument(
        "--translations-file",
        default="translations.txt",
        type=str,
        help="The path to the file containing translations. Defaults to %(default)s.",
    )

    # Add argument for output file
    parser.add_argument(
        "--output-file",
        default="updated_MethodicConfigurator.po",
        type=str,
        help="The name of the .po file where the translations will be written. "
        "This file will contain lines in the .po (GNU gettext) format. Defaults to %(default)s",
    )

    return parser.parse_args()


def insert_translations(lang_code: str, translations_file: str, output_file_name: str) -> None:
    po_file = os.path.join("MethodicConfigurator", "locale", lang_code, "LC_MESSAGES", "MethodicConfigurator.po")
    with open(po_file, encoding="utf-8") as f:
        lines = f.readlines()

    with open(translations_file, encoding="utf-8") as f:
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
    output_file = os.path.join("MethodicConfigurator", "locale", lang_code, "LC_MESSAGES", output_file_name)
    with open(output_file, "w", encoding="utf-8") as f:
        f.writelines(lines)


def main() -> None:
    args = parse_arguments()
    insert_translations(args.lang_code, args.translations_file, args.output_file)


if __name__ == "__main__":
    main()
