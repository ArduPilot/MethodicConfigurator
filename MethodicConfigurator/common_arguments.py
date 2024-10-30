#!/usr/bin/env python3

'''
This file is part of Ardupilot methodic configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
'''

from MethodicConfigurator.version import VERSION

from MethodicConfigurator.internationalization import _, LANGUAGE_CHOICES


def add_common_arguments_and_parse(parser):
    parser.add_argument('--loglevel',
                        type=str,
                        default='INFO',
                        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'],
                        help=_('Logging level (default is %(default)s).'))
    parser.add_argument('-v', '--version',
                        action='version',
                        version=f'%(prog)s {VERSION}',
                        help=_('Display version information and exit.'))
    parser.add_argument('--language',
                        type=str,
                        default='en',
                        choices=LANGUAGE_CHOICES,
                        help=_('User interface language (default is %(default)s).'))
    return parser.parse_args()
