#!/bin/bash
#
# SPDX-FileCopyrightText: 2024 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>
#
#SPDX-License-Identifier: GPL-3.0-or-later

PYTHONPATH=../MethodicConfigurator python3 -m coverage run -m unittest extract_param_defaults_test.py
python3 -m coverage html
firefox htmlcov/extract_param_defaults_py.html