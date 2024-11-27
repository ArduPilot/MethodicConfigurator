#!/bin/bash
#
# SPDX-FileCopyrightText: 2024 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>
#
#SPDX-License-Identifier: GPL-3.0-or-later

# Use venv if you use python3 due to the PEP668
python3 -m venv venv
source venv/bin/activate

# Uninstall serial and pyserial to avoid conflicts
python3 -m pip uninstall -y serial pyserial

# Install the project dependencies
python3 -m pip install .

echo "Installation complete."
echo ""
echo "You can run the ArduPilot methodic configurator GUI by executing:"
echo "cd ardupilot_methodic_configurator"
echo "python3 ./ardupilot_methodic_configurator.py"
echo ""
echo "For more detailed usage instructions, please refer to the USERMANUAL.md file."
