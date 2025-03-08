@echo off
setlocal enabledelayedexpansion

:: Store the original directory
set "ORIGINAL_DIR=%CD%"

:: Change to the directory where the script resides
cd /d %~dp0

if exist "C:\Program Files\WindowsApps\PythonSoftwareFoundation.Python.3.12_3.12.2544.0_x64__qbz5n2kfra8p0" (
    set "targetPath=C:\Program Files\WindowsApps\PythonSoftwareFoundation.Python.3.12_3.12.2544.0_x64__qbz5n2kfra8p0"
) else if exist "%USERPROFILE%\AppData\Roaming\Python\Python312\Scripts" (
    set "targetPath=%USERPROFILE%\\AppData\Roaming\Python\Python312\Scripts"
)

set "found=0"

:: Normalize the target path by removing any trailing backslash
if "!targetPath:~-1!"=="\" set "targetPath=!targetPath:~0,-1!"
echo Checking if "!targetPath!" is already in PATH...

:: Iterate over each entry in PATH
for %%A in ("%PATH:;=" "%") do (
    :: Remove quotes and trailing backslash for comparison
    set "currentPath=%%~A"
    if "!currentPath:~-1!"=="\" set "currentPath=!currentPath:~0,-1!"

    :: Case-insensitive comparison for Windows paths
    if /i "!currentPath!"=="!targetPath!" (
        set "found=1"
        echo The path "!targetPath!" is already included in the PATH.
        goto :checkDone
    )
)

if "!found!"=="0" (
    echo The path "!targetPath!" is not in the PATH.
    echo Appending "!targetPath!" to the PATH...
    setx PATH "%PATH%;!targetPath!"
    if !ERRORLEVEL! EQU 0 (
        echo Successfully updated system PATH.
        rem Update the current session PATH variable
        set "PATH=%PATH%;!targetPath!"
    ) else (
        echo Failed to update system PATH. Please check permissions.
    )
)

:checkDone


call :ConfigureArgComplete
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
git config --local commit.gpgsign false
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

:ConfigureArgComplete

:: Define paths
set "PROFILE_PATH=%USERPROFILE%\Documents\WindowsPowerShell\Microsoft.PowerShell_profile.ps1"
set "MODULE_PATH=C:\Program^ Files^ ^(x86^)\ardupilot_methodic_configurator\ardupilot_methodic_configurator_command_line_completion.psm1"

:: Create profile directory if it doesn't exist
if not exist "%USERPROFILE%\Documents\WindowsPowerShell" (
    mkdir "%USERPROFILE%\Documents\WindowsPowerShell"
)

:: Check if module exists
if not exist "%MODULE_PATH%" (
    echo Error: Module file not found at %MODULE_PATH%
    pause
    exit /b 1
)

:: Add import line to profile if it doesn't exist
powershell -Command "if (-not (Test-Path '%PROFILE_PATH%')) { New-Item -Path '%PROFILE_PATH%' -Force } else { $content = Get-Content '%PROFILE_PATH%'; if ($content -notcontains 'Import-Module \"%MODULE_PATH%\"') { Add-Content '%PROFILE_PATH%' 'Import-Module \"%MODULE_PATH%\"' }}"

if %errorLevel% equ 0 (
    echo PowerShell profile updated successfully.
    echo Please restart PowerShell for changes to take effect.
) else (
    echo Failed to update PowerShell profile.
)

goto :eof
