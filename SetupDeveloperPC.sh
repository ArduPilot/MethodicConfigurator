#!/bin/bash

# Store the original directory
ORIGINAL_DIR=$(pwd)

# Change to the directory where the script resides
cd "$(dirname "$0")" || exit

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
    git config --local alias.su "submodule update --init --recursive"
    git config --local credential.helper manager
    git config --local pull.rebase true
    git config --local push.autoSetupRemote
    git config --local init.defaultbranch master
    git config --local sequence.editor "code --wait"
    echo Git configuration applied successfully.
}

ConfigurePreCommit() {
    echo Setting pre-commit...
    echo "Checking for pip..."
    if ! command -v pip &> /dev/null; then
        echo "pip is not installed. Please install pip before running this script."
        exit 1
    fi
    pip install 'pre-commit==4.1.0'
    pre-commit install
    echo Pre-commit done.
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

    fi
}

# Call configuration functions
ConfigureGit
ConfigureVSCode
ConfigurePreCommit

# Run pre-commit
echo "running pre-commit checks on all Files"
pre-commit run -a

# Change back to the original directory
cd "$ORIGINAL_DIR" || exit

echo "Script completed successfully."
exit 0
