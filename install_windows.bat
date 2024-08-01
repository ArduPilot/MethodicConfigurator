@echo off
rem SPDX-FileCopyrightText: 2024 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>
rem
rem SPDX-License-Identifier: GPL-3.0-or-later

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
python3 -m pip install .

echo.
echo On MS Windows softlinks require admin privileges and have other problems so we will 
echo replace the linux parameter metadata/documentation files softlinks with MS Windows hardlinks

setlocal enabledelayedexpansion
for %%f in (
    4.3.8-params
    4.4.4-params
    4.5.x-params
    4.6.x-params
) do (
    set "src=apm.pdef.%%f.xml"
    set "dest=vehicle_templates\ArduCopter\diatone_taycan_mxc\%%f\apm.pdef.xml"
    rem remove the old linux softlinks
    del !dest!
    rem echo Copying !src! to !dest!
    rem copy .\!src! !dest!
    mklink /H !dest! .\!src!
)

rem echo Copying complete.
echo Hard links creation complete
echo.
echo To run the ArduPilot methodic configurator GUI, execute the following command:
echo.
echo cd MethodicConfigurator
echo python3 ardupilot_methodic_configurator.py
echo.
echo If you encounter issues with auto-connecting to the wrong device on MS Windows,
echo you can explicitly set the device with the --device command line option:
echo.
echo cd MethodicConfigurator
echo python3 ardupilot_methodic_configurator.py --device COMX
echo.
echo Replace COMX with the correct COM port for your device.
echo.
echo For more detailed usage instructions, please refer to the USERMANUAL.md file.
goto :eof

:skip_uninstall
echo Operation cancelled by the user.
goto :eof
