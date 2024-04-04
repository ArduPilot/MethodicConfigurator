#!/bin/bash

# Check if the script is run as root
if [ "$EUID" -ne 0 ]
 then echo "Please run as root"
 exit
fi

# Update package lists
echo "Updating package lists..."
sudo apt-get update

# Install Python3 PIL.ImageTk for GUI support
echo "Installing Python3 PIL.ImageTk..."
sudo apt-get install -y python3-pil.imagetk

# Uninstall serial and pyserial to avoid conflicts
echo "Uninstalling serial and pyserial..."
python3 -m pip uninstall -y serial pyserial

# Install the project dependencies
echo "Installing project dependencies..."
python3 -m pip install .

echo "Installation complete."
echo ""
echo "You can run the ArduPilot methodic configurator GUI by executing:"
echo "python3 ardupilot_methodic_configurator.py"
echo ""
echo "For more detailed usage instructions, please refer to the USERMANUAL.md file."
