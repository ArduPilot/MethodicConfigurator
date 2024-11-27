"""
Common arguments used by all sub applications.

This file is part of Ardupilot methodic configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

from argparse import ArgumentParser, Namespace

from ardupilot_methodic_configurator import _, __version__
from ardupilot_methodic_configurator.internationalization import LANGUAGE_CHOICES


def add_common_arguments_and_parse(parser: ArgumentParser) -> Namespace:
    parser.add_argument(
        "--loglevel",
        type=str,
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        help=_("Logging level (default is %(default)s)."),
    )
    parser.add_argument(
        "-v", "--version", action="version", version=f"%(prog)s {__version__}", help=_("Display version information and exit.")
    )
    parser.add_argument(
        "--language",
        type=str,
        default=LANGUAGE_CHOICES[0],
        choices=LANGUAGE_CHOICES,
        help=_("User interface language (default is %(default)s)."),
    )
    return parser.parse_args()
