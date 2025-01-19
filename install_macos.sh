#!/bin/bash
#
# SPDX-FileCopyrightText: 2024 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>
#
#SPDX-License-Identifier: GPL-3.0-or-later

# Use venv if you use python3 due to the PEP668
python3 -m venv .venv
# shellcheck source=/dev/null
source .venv/bin/activate

# Uninstall serial and pyserial to avoid conflicts
echo "Uninstalling serial and pyserial..."
python3 -m pip uninstall -y serial pyserial

# Install the project dependencies
echo "Installing project dependencies..."
python3 -m pip install -e .[dev]

# configure git local repository settings
git config --local pull.rebase true
git config --local push.autoSetupRemote
git config --local init.defaultbranch master
git config --local sequence.editor "code --wait"

# install pre-commit git hooks
pre-commit install


echo "Installation complete."
echo ""
echo "You can run the ArduPilot methodic configurator GUI by executing:"
echo "python3 -m ardupilot_methodic_configurator"
echo ""
echo "For more detailed usage instructions, please refer to the USERMANUAL.md file."
