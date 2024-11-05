#!/usr/bin/env python3

"""
This file is part of Ardupilot methodic configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import gettext
import os


def extract_missing_translations(po_file, output_file):
    # Set up the translation catalog
    language = gettext.translation("messages", localedir=os.path.dirname(po_file), languages=["zh_CN"], fallback=True)

    # Read the .po file entries
    with open(po_file, "r", encoding="utf-8") as f:
        lines = f.readlines()

    missing_translations = []

    # Iterate through lines to find untranslated msgid
    for i, f_line in enumerate(lines):
        line = f_line.strip()

        if line.startswith("msgid"):
            msgid = line.split('"')[1]  # Get the msgid string

            # Check if the translation exists
            if language.gettext(msgid) == msgid:  # If translation is the same as msgid, it's missing
                missing_translations.append((i, msgid))

    # Write untranslated msgids along with their indices to the output file
    with open(output_file, "w", encoding="utf-8") as f:
        for index, item in missing_translations:
            f.write(f"{index}:{item}\n")


if __name__ == "__main__":
    extract_missing_translations("MethodicConfigurator.po", "missing_translations.txt")
