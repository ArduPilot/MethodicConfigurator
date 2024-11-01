#!/usr/bin/env python3

'''
This file is part of Ardupilot methodic configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
'''

def insert_translations(po_file, translations_file, output_file):
    with open(po_file, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    with open(translations_file, 'r', encoding='utf-8') as f:
        translations_data = f.read().strip().split('\n')

    # Prepare to insert translations
    translations = []
    for data in translations_data:
        index, translation = data.split(':', 1)  # Split the index and the translation
        translations.append((int(index), translation.strip()))  # Store index and translation as tuple

    insertion_offset = 0  # To track how many lines we've inserted
    # To insert the translations correctly
    for index, translation in translations:
        # Adjust index accounting for previously inserted lines
        adjusted_index = index + insertion_offset

        # Check if the next line is an empty msgstr
        if (adjusted_index + 1 < len(lines) and
            lines[adjusted_index + 1].strip() == 'msgstr ""'):
            # Overwrite the empty msgstr line
            lines[adjusted_index + 1] = f'msgstr "{translation}"\n'
        else:
            # Otherwise, insert a new msgstr line
            lines.insert(adjusted_index + 1, f'msgstr "{translation}"\n')
            insertion_offset += 1  # Increment the offset for each insertion

    # Writing back to a new output file
    with open(output_file, 'w', encoding='utf-8') as f:
        f.writelines(lines)

if __name__ == "__main__":
    insert_translations('MethodicConfigurator.po', 'translations.txt', 'updated_MethodicConfigurator.po')
