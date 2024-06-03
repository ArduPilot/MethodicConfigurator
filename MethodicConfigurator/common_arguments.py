#!/usr/bin/env python3

'''
This file is part of Ardupilot methodic configurator. https://github.com/ArduPilot/MethodicConfigurator

(C) 2024 Amilcar do Carmo Lucas

SPDX-License-Identifier:    GPL-3
'''

from MethodicConfigurator.version import VERSION


def add_common_arguments_and_parse(parser):
    parser.add_argument('--loglevel',
                        type=str,
                        default='INFO',
                        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'],
                        help='Logging level (default is INFO).')
    parser.add_argument('-v', '--version',
                        action='version',
                        version=f'%(prog)s {VERSION}',
                        help='Display version information and exit.')
    return parser.parse_args()
