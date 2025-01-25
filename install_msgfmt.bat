@echo off
setlocal enabledelayedexpansion

:: Check for admin privileges
net session >nul 2>&1
if %errorLevel% neq 0 (
    echo Please run as administrator
    pause
    exit /b 1
)

:: Set download URL and temp file
set "URL=https://github.com/mlocati/gettext-iconv-windows/releases/download/v0.23-v1.17/gettext0.23-iconv1.17-shared-64.exe"
set "OUTFILE=%TEMP%\gettext-tools-windows-x64.exe"

:: Download installer
echo Downloading GNU gettext tools...
bitsadmin /transfer "GetTextDownload" "%URL%" "%OUTFILE%" >nul
if not exist "%OUTFILE%" (
    echo Download failed
    pause
    exit /b 1
)

:: Run installer silently
echo Installing...
start /wait "" "%OUTFILE%" /SILENT
if %errorLevel% neq 0 (
    echo Installation failed
    pause
    exit /b 1
)

:: Verify installation
echo Verifying installation...
msgfmt --version
if %errorLevel% neq 0 (
    echo Verification failed
    pause
    exit /b 1
)

echo Installation completed successfully
pause