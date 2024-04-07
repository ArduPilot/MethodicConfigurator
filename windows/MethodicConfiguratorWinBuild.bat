rem build the standalone MethodicConfigurator.exe for Windows.
rem This assumes Python and pip are on the system path
rem This assumes InnoSetup is installed in C:\Program Files (x86)\Inno Setup 6
rem   If it is not, change the INNOSETUP environment variable accordingly
SETLOCAL enableextensions

if "%INNOSETUP%" == "" (set "INNOSETUP=C:\Program Files (x86)\Inno Setup 6")

rem get the version
for /f "tokens=*" %%a in (
 'python.exe returnVersion.py'
 ) do (
 set VERSION=%%a
 )
 
rem -----Upgrade pymavlink if needed-----
if exist "..\..\pymavlink" (
 rem Rebuild and use pymavlink from pymavlink sources if available
 pushd ..\..\pymavlink
 python.exe setup.py build install --user
 popd
) else (
 if exist "..\..\mavlink\pymavlink" (
  rem Rebuild and use pymavlink from mavlink\pymavlink sources if available
  pushd ..\..\mavlink\pymavlink
  python.exe setup.py build install --user
  popd
 ) else (
  pip.exe install pymavlink -U --user
 )
)

rem -----Build MethodicConfigurator-----
cd ..\
python.exe -m pip install . --user
cd .\MethodicConfigurator
copy ..\windows\ardupilot_methodic_configurator.spec
pyinstaller -y --clean ardupilot_methodic_configurator.spec
del ardupilot_methodic_configurator.spec

rem -----Create version Info-----
@echo off
@echo %VERSION%> ..\windows\version.txt
@echo on

rem -----Build the Installer-----
cd ..\windows
rem Newer Inno Setup versions do not require a -compile flag, please add it if you have an old version
"%INNOSETUP%\ISCC.exe" /dMyAppVersion=%VERSION% ardupilot_methodic_configurator.iss

pause
