#!/usr/bin/env python3

'''
This file is part of Ardupilot methodic configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
'''

import gettext


# Setup language
locale_path = 'locale'  # directory of locale file
language = 'zh_CN'  # select language

# create translation
translation = gettext.translation('messages', localedir=locale_path, languages=[language], fallback=True)

# set translation object as _()
_ = translation.gettext
