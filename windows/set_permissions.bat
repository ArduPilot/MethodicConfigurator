@echo off
:: Change directory to where settings.json is located
cd "%APPDATA%\.ardupilot_methodic_configurator"

:: Grant full control to the current user
icacls settings.json /grant "%USERNAME%:(F)"
