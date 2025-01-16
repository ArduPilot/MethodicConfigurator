@echo off
rem SPDX-FileCopyrightText: 2024 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>
rem
rem SPDX-License-Identifier: GPL-3.0-or-later

rem Check if Python 3 is installed
where python3 >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Python 3 is not installed or not in PATH.
    echo Please install Python 3 and ensure it's in your system PATH.
    pause
    exit /b 1
)

echo WARNING: If you proceed the python serial package will be uninstalled because it conflicts with pyserial.
choice /C YN /M "Do you want to proceed? (Y/N)"
if errorlevel 2 goto :skip_uninstall
if errorlevel 1 goto :uninstall_python_serial

:uninstall_python_serial
python3 -m pip uninstall serial pyserial -y
echo.
echo python serial has been successfully uninstalled.
echo.

rem Install all dependencies defined in setup.py
python3 -m pip install -e .[dev]

echo.
echo To run the ArduPilot methodic configurator GUI, execute the following command:
echo.
echo python3 -m ardupilot_methodic_configurator
echo.
echo If you encounter issues with auto-connecting to the wrong device on MS Windows,
echo you can explicitly set the device with the --device command line option:
echo.
echo python3 -m ardupilot_methodic_configurator --device COMX
echo.
echo Replace COMX with the correct COM port for your device.
echo.
echo For more detailed usage instructions, please refer to the USERMANUAL.md file.
goto :eof

:skip_uninstall
echo Operation cancelled by the user.
goto :eof
