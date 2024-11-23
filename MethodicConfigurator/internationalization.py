"""
Translations to other written languages.

This file is part of Ardupilot methodic configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import argparse
import gettext
from os import path as os_path
from platform import system as platform_system
from typing import Callable

# Do not import nor use logging functions in this file.
# Logging is not yet configured when these functions are called

LANGUAGE_CHOICES = ["en", "zh_CN", "pt", "de"]


def identity_function(s: str) -> str:
    return s


def load_translation() -> Callable[[str], str]:
    default_language = LANGUAGE_CHOICES[0]

    # First, pre-parse to find the --language argument
    pre_parser = argparse.ArgumentParser(add_help=False)
    pre_parser.add_argument("--language", type=str, default=default_language, choices=LANGUAGE_CHOICES)
    pre_args, _list_str = pre_parser.parse_known_args()

    if pre_args.language == default_language:
        return identity_function

    # Load the correct language ASAP based on the command line argument
    try:
        script_dir = os_path.dirname(os_path.abspath(__file__))
        if platform_system() != "Windows":
            if "site-packages" in script_dir:
                script_dir = os_path.join(os_path.expanduser("~"), ".local", "MethodicConfigurator")
            elif "dist-packages" in script_dir:
                script_dir = os_path.join("/usr", "local", "MethodicConfigurator")
        locale_dir = os_path.join(script_dir, "locale")
        translation = gettext.translation(
            "MethodicConfigurator", localedir=locale_dir, languages=[pre_args.language], fallback=False
        )
        translation.install()
        # Do not use logging functions here the logging system has not been configured yet
        # Do not translate this message, the translation will not work here anyways
        print(f"Loaded {pre_args.language} translation files.")
        return translation.gettext
    except FileNotFoundError:
        # Do not use logging functions here the logging system has not been configured yet
        # Do not translate this message, the translation will not work here anyways
        print(f"{pre_args.language} translation files not found. Using default {default_language} language.")
        return identity_function  # Return identity function on error
