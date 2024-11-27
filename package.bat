del /Q dist\*

rem python3.11.exe -m PyInstaller --onefile --noconfirm --add-data "4.4.4-test-params\00_default.param;4.4.4-test-params" --add-data "apm.pdef.xml;." --add-data "apm.pdef.4.3.8-params.xml;." --add-data "apm.pdef.4.4.4-params.xml;." --add-data "apm.pdef.4.5.x-params.xml;." --add-data "apm.pdef.4.6.x-params.xml;." --add-data "ArduPilot_icon.png;." --add-data "configuration_steps_ArduCopter.json;." ardupilot_methodic_configurator.py
python3.11.exe -m PyInstaller --onefile --noconfirm ardupilot_methodic_configurator\ardupilot_methodic_configurator.py
md dist\4.4.4-test-params
copy 4.4.4-test-params\00_default.param dist\4.4.4-test-params
copy apm.pdef.4.3.8-params.xml dist
copy apm.pdef.4.4.4-params.xml dist
copy apm.pdef.4.5.x-params.xml dist
copy apm.pdef.4.6.x-params.xml dist
copy configuration_steps_ArduCopter.json dist
copy configuration_steps_ArduPlane.json dist
copy configuration_steps_Heli.json dist
copy configuration_steps_Rover.json dist
xcopy /E /I /Y ardupilot_methodic_configurator\vehicle_templates\ArduCopter\diatone_taycan_mxc\4.3.8-params dist\4.3.8-params
xcopy /E /I /Y ardupilot_methodic_configurator\vehicle_templates\ArduCopter\diatone_taycan_mxc\4.4.4-params dist\4.4.4-params
xcopy /E /I /Y 4.4.4-test-params dist\4.4.4-test-params
xcopy /E /I /Y ardupilot_methodic_configurator\vehicle_templates\ArduCopter\diatone_taycan_mxc\4.5.x-params dist\4.5.x-params
xcopy /E /I /Y ardupilot_methodic_configurator\vehicle_templates\ArduCopter\diatone_taycan_mxc\4.6.x-params dist\4.6.x-params
xcopy /E /I /Y images dist\images
copy *.md dist
copy ardupilot_methodic_configurator\*.png dist
copy ardupilot_methodic_configurator\extract_param_defaults.py dist
copy ardupilot_methodic_configurator\param_pid_adjustment_update.py dist