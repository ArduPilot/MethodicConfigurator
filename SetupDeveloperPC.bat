@echo off
setlocal enabledelayedexpansion

:: Store the original directory
set "ORIGINAL_DIR=%CD%"

:: Change to the directory where the script resides
cd /d %~dp0

set "targetPath=%USERPROFILE%\AppData\Roaming\Python\Python312\Scripts"
set "found=0"

:: Iterate over each entry in PATH
for %%A in ("%PATH:;=" "%") do (
    if /i "%%~A"=="!targetPath!" (
        set "found=1"
        echo The path is already included in the PATH.
        goto :checkDone
    )
)

if "!found!"=="0" (
    rem The target path is not in the PATH, so we will append it
    echo Appending "!targetPath!" to the PATH...
    setx PATH "%PATH%;!targetPath!"
    rem Update the current session PATH variable
    set "PATH=%PATH%;!targetPath!"
)

:checkDone

call :ConfigureGit
call :ConfigureVSCode
call :ConfigurePreCommit

echo running pre-commit checks on all Files
pre-commit run -a

:: Change back to the original directory
cd /d %ORIGINAL_DIR%

echo Script completed successfully.
exit /b

:ConfigureGit
echo Configuring Git settings...
git config --local commit.gpgsign true
git config --local diff.tool meld
git config --local diff.astextplain.textconv astextplain
git config --local merge.tool meld
git config --local difftool.prompt false
git config --local mergetool.prompt false
git config --local mergetool.meld.cmd "meld \"$LOCAL\" \"$MERGED\" \"$REMOTE\" --output \"$MERGED\""
git config --local core.autocrlf false
git config --local core.fscache true
git config --local core.symlinks false
git config --local core.editor "code"
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
goto :eof

:ConfigurePreCommit
echo Installing pre-commit tools into the Ubuntu running inside WSL2...
wsl --exec bash -c "./install_wsl.bash"
echo Setting pre-commit...
pip3 install pre-commit
pre-commit install
echo Pre-commit done.
goto :eof

:ConfigureVSCode
:: Check for VSCode installation and install extensions
echo Checking for VSCode...
where code >nul
IF %ERRORLEVEL% NEQ 0 (
    echo VSCode is not installed. Please install VSCode before running this script.
    pause
    exit /b
) ELSE (
    echo Installing the markdownlint VSCode extension...
    cmd /c code --install-extension davidanson.vscode-markdownlint
    IF %ERRORLEVEL% NEQ 0 (
        echo Failed to install markdownlint extension.
        pause
        exit /b
    )
    echo Installing the Markdown Preview Enhanced extension...
    cmd /c code --install-extension shd101wyy.markdown-preview-enhanced
    IF %ERRORLEVEL% NEQ 0 (
        echo Failed to install Markdown Preview Enhanced extension.
        pause
        exit /b
    )

    echo Installing GitHub Copilot...
    cmd /c code --install-extension GitHub.copilot
    IF %ERRORLEVEL% NEQ 0 (
        echo Failed to install GitHub Copilot extension.
        pause
        exit /b
    )

    echo Installing the Conventional Commits VSCode extension...
    cmd /c code --install-extension vivaxy.vscode-conventional-commits
    IF %ERRORLEVEL% NEQ 0 (
        echo Failed to install Conventional Commits VSCode extension.
        pause
        exit /b
    )

    echo Installing the GitLens VSCode extension...
    cmd /c code --install-extension eamodio.gitlens
    IF %ERRORLEVEL% NEQ 0 (
        echo Failed to install GitLens VSCode extension.
        pause
        exit /b
    )

    echo Installing code spellcheker extension...
    cmd /c code --install-extension streetsidesoftware.code-spell-checker
    IF %ERRORLEVEL% NEQ 0 (
        echo Failed to install code spellcheker extension.
        pause
        exit /b
    )

    echo Installing the Python VSCode extension...
    cmd /c code --install-extension ms-python.python
    IF %ERRORLEVEL% NEQ 0 (
        echo Failed to install Python VSCode extension.
        pause
        exit /b
    )

    echo Installing ruff extension...
    cmd /c code --install-extension charliermarsh.ruff
    IF %ERRORLEVEL% NEQ 0 (
        echo Failed to install ruff extension.
        pause
        exit /b
    )

)
goto :eof
