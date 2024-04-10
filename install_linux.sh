#!/bin/bash

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

# Get the directory of the script
prog_dir=$(realpath "$(dirname "$0")")/MethodicConfigurator

# Check if the system is Debian-based
if [ -f /etc/debian_version ] || [ -f /etc/os-release ] && grep -q 'ID_LIKE=.*debian.*' /etc/os-release; then
    echo "Creating MethodicConfigurator.desktop for Debian-based systems..."
    # Define the desktop entry content
    desktop_entry="[Desktop Entry]\nName=ArduPilot Methodic Configurator\nComment=A clear ArduPilot configuration sequence\nExec=bash -c 'cd $prog_dir && python3 ardupilot_methodic_configurator.py'\nIcon=$prog_dir/ArduPilot_icon.png\nTerminal=true\nType=Application\nCategories=Development;\nKeywords=ardupilot;arducopter;drone;copter;scm"
    # Create the .desktop file in the appropriate directory
    echo -e $desktop_entry > /home/$USER/.local/share/applications/MethodicConfigurator.desktop
    echo "MethodicConfigurator.desktop created successfully."
else
    echo "This system is not Debian-based. Skipping .desktop file creation."
fi

# Check if the ~/Desktop directory exists
if [ -d "$HOME/Desktop" ]; then
    # Copy the .desktop file to the ~/Desktop directory
    cp /home/$USER/.local/share/applications/MethodicConfigurator.desktop $HOME/Desktop/
    # Mark it as thrusted
    chmod 755 $HOME/Desktop/MethodicConfigurator.desktop
    echo "MethodicConfigurator.desktop copied to ~/Desktop."
else
    echo "~/Desktop directory does not exist. Skipping copy to Desktop."
fi

update-desktop-database ~/.local/share/applications/

echo "Installation complete."
echo ""
echo "You can run the ArduPilot methodic configurator GUI by executing:"
echo "cd MethodicConfigurator"
echo "python3 ardupilot_methodic_configurator.py"
echo ""
echo "For more detailed usage instructions, please refer to the USERMANUAL.md file."
