#!/bin/bash
#
# SPDX-FileCopyrightText: 2024 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>
#
#SPDX-License-Identifier: GPL-3.0-or-later

PYTHONPATH=../MethodicConfigurator python3 -m coverage run -m unittest param_pid_adjustment_update_test.py
python3 -m coverage html
firefox htmlcov/param_pid_adjustment_update_py.html