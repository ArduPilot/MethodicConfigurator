#!/bin/bash
#
# Configure a Linux or macOS developer PC for ArduPilot Methodic Configurator development.
#
# SPDX-FileCopyrightText: 2024-2025 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>
#
# SPDX-License-Identifier: GPL-3.0-or-later

echo "This script is only meant for ArduPilot methodic configurator developers."
read -r -p "Do you want to develop ArduPilot methodic Configurator software on your PC? (y/N) " response

# Convert response to lowercase
response=${response,,}

if [[ ! $response =~ ^y(es)?$ ]]; then
    echo "Setup canceled, install the software using 'pip install ardupilot_methodic_configurator' instead."
    exit 0
fi

# Store the original directory
ORIGINAL_DIR=$(pwd)

# Change to the directory where the script resides
cd "$(dirname "$0")" || exit

# Install macOS dependencies early if on macOS
if command -v brew &> /dev/null; then
    echo "Installing macOS dependencies with Homebrew..."
    brew install uv python-tk@3.9
    echo "Creating Python virtual environment with uv..."
    uv venv --python 3.9
else
    # Create a local virtual environment if it doesn't exist
    if [ ! -d ".venv" ]; then
        echo "Creating Python virtual environment..."
        python3 -m venv .venv
    fi
fi

# Activate the virtual environment
echo "Activating virtual environment..."
# shellcheck disable=SC1091
source .venv/bin/activate

InstallDependencies() {
    echo "Updating package lists..."
    if command -v apt-get &> /dev/null; then
        sudo apt-get update
        # Install Python3 PIL.ImageTk for GUI support
        echo "Installing Python3 PIL.ImageTk..."
        sudo apt-get install -y python3-pil.imagetk gettext
        python3 -m pip install uv
    elif command -v brew &> /dev/null; then
        echo "macOS dependencies already installed."
    else
        echo "Neither apt-get nor brew found. Please install dependencies manually."
    fi

    # No need to uninstall serial and pyserial anymore as the virtual environment is isolated
    # Uninstall serial and pyserial to avoid conflicts
    # echo "Uninstalling serial and pyserial..."
    # uv pip uninstall -y serial pyserial

    # Install the project dependencies
    echo "Installing project dependencies..."
    uv pip install -e .[dev]
}

ConfigureGit() {
    echo "Configuring Git settings..."
    git config --local commit.gpgsign false
    git config --local diff.tool meld
    git config --local diff.astextplain.textconv astextplain
    git config --local merge.tool meld
    git config --local difftool.prompt false
    git config --local mergetool.prompt false
    git config --local mergetool.meld.cmd "meld \"\$LOCAL\" \"\$MERGED\" \"\$REMOTE\" --output \"\$MERGED\""
    git config --local core.autocrlf false
    git config --local core.fscache true
    git config --local core.symlinks false
    git config --local core.editor "code --wait --new-window"
    git config --local alias.graph1 "log --graph --abbrev-commit --decorate --format=format:'%C(bold blue)%h%C(reset) - %C(bold green)(%ar)%C(reset) %C(white)%s%C(reset) %C(dim white)- %an%C(reset)%C(bold yellow)%d%C(reset)' --all"
    git config --local alias.graph2 "log --graph --abbrev-commit --decorate --format=format:'%C(bold blue)%h%C(reset) - %C(bold cyan)%aD%C(reset) %C(bold green)(%ar)%C(reset)%C(bold yellow)%d%C(reset)%n''          %C(white)%s%C(reset) %C(dim white)- %an%C(reset)' --all"
    git config --local alias.graph "!git graph1"
    git config --local alias.co checkout
    git config --local alias.st status
    git config --local alias.cm "commit -m"
    git config --local alias.pom "push origin master"
    git config --local alias.aa "add --all"
    git config --local alias.df diff
    git config --local credential.helper manager
    git config --local pull.rebase true
    git config --local push.autoSetupRemote
    git config --local init.defaultbranch master
    git config --local sequence.editor "code --wait"
    echo Git configuration applied successfully.
}

ConfigureVSCode() {
    # Check for VSCode installation
    echo "Checking for VSCode..."
    if ! command -v code &> /dev/null; then
        echo "VSCode is not installed. Please install VSCode before running this script."
        exit 1
    else
        echo "Installing the markdownlint VSCode extension..."
        if ! code --install-extension davidanson.vscode-markdownlint; then
            echo "Failed to install markdownlint extension."
            exit 1
        fi

        echo "Installing the Markdown Preview Enhanced extension..."
        if ! code --install-extension shd101wyy.markdown-preview-enhanced; then
            echo "Failed to install Markdown Preview Enhanced extension."
            exit 1
        fi

        echo "Installing GitHub Copilot..."
        if ! code --install-extension GitHub.copilot; then
            echo "Failed to install GitHub Copilot extension."
            exit 1
        fi

        echo "Installing the Conventional Commits VSCode extension..."
        if ! code --install-extension vivaxy.vscode-conventional-commits; then
            echo "Failed to install Conventional Commits VSCode extension."
            exit 1
        fi

        echo "Installing the GitLens VSCode extension..."
        if ! code --install-extension eamodio.gitlens; then
            echo "Failed to install GitLens VSCode extension."
            exit 1
        fi

        echo "Installing code spellcheker extension..."
        if ! code --install-extension streetsidesoftware.code-spell-checker; then
            echo "Failed to install code spellcheker extension."
            exit 1
        fi

        echo "Installing the Python VSCode extension..."
        if ! code --install-extension ms-python.python; then
            echo "Failed to install Python VSCode extension."
            exit 1
        fi

        echo "Installing ruff extension..."
        if ! code --install-extension charliermarsh.ruff; then
            echo "Failed to install ruff extension."
            exit 1
        fi

    fi
}

SetupSITL() {
    echo ""
    read -r -p "Do you want to download ArduCopter SITL for integration testing? (y/N) " response
    response=${response,,}

    if [[ $response =~ ^y(es)?$ ]]; then
        echo "Downloading ArduCopter SITL from official firmware server..."

        # Use the run_sitl_tests.sh script if available
        if [ -f "scripts/run_sitl_tests.sh" ]; then
            bash scripts/run_sitl_tests.sh download
        else
            # Fallback to direct download if script not found
            mkdir -p sitl
            curl -L -o sitl/arducopter https://firmware.ardupilot.org/Copter/latest/SITL_x86_64_linux_gnu/arducopter
            curl -L -o sitl/firmware-version.txt https://firmware.ardupilot.org/Copter/latest/SITL_x86_64_linux_gnu/firmware-version.txt
            curl -L -o sitl/git-version.txt https://firmware.ardupilot.org/Copter/latest/SITL_x86_64_linux_gnu/git-version.txt
            curl -L -o sitl/copter.parm https://raw.githubusercontent.com/ArduPilot/ardupilot/master/Tools/autotest/default_params/copter.parm
            chmod +x sitl/arducopter
            echo "✓ ArduCopter SITL downloaded successfully"
        fi

        # Set environment variable in shell profile
        echo ""
        echo "To enable SITL tests permanently, add this to your ~/.bashrc or ~/.zshrc:"
        echo "  export SITL_BINARY=$(pwd)/sitl/arducopter"
    else
        echo "Skipping SITL download. You can download it later with: ./scripts/run_sitl_tests.sh download"
    fi
}

# Call configuration functions
InstallDependencies
ConfigureGit
ConfigureVSCode
SetupSITL

activate-global-python-argcomplete

pre-commit install

# Run pre-commit
echo "running pre-commit checks on all Files"
pre-commit run -a

# Change back to the original directory
cd "$ORIGINAL_DIR" || exit

echo ""
echo "To run the ArduPilot methodic configurator GUI, execute the following commands:"
echo ""
echo "source .venv/bin/activate"
echo "python3 -m ardupilot_methodic_configurator"
echo ""
echo "To run SITL integration tests (if SITL was downloaded):"
echo ""
echo "export SITL_BINARY=\$(pwd)/sitl/arducopter"
echo "pytest -m sitl -v"
echo ""
echo "For more detailed usage instructions, please refer to the USERMANUAL.md file."
echo ""

echo "Script completed successfully."
exit 0
