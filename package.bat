rem python3.11.exe -m PyInstaller --onefile --noconfirm --add-data "4.4.4-test-params\00_default.param;4.4.4-test-params" --add-data "apm.pdef.xml;." --add-data "apm.pdef.4.3.8-params.xml;." --add-data "apm.pdef.4.4.4-params.xml;." --add-data "apm.pdef.4.5.0-beta2-params.xml;." --add-data "apm.pdef.4.6.0-DEV-params.xml;." --add-data "ArduPilot_32x32.png;." --add-data "file_documentation.json;." ardupilot_methodic_configurator.py
python3.11.exe -m PyInstaller --onefile --noconfirm ardupilot_methodic_configurator.py
md dist\4.4.4-test-params
copy 4.4.4-test-params\00_default.param dist\4.4.4-test-params
copy apm.pdef.xml dist
copy apm.pdef.4.3.8-params.xml dist
copy apm.pdef.4.4.4-params.xml dist
copy apm.pdef.4.5.0-beta2-params.xml dist
copy apm.pdef.4.6.0-DEV-params.xml dist
copy ArduPilot_32x32.png dist
copy ArduPilot.png dist
copy file_documentation.json dist
xcopy /E /I /Y 4.3.8-params dist\4.3.8-params
xcopy /E /I /Y 4.4.4-params dist\4.4.4-params
xcopy /E /I /Y 4.4.4-test-params dist\4.4.4-test-params
xcopy /E /I /Y 4.5.0-beta2-params dist\4.5.0-beta2-params
xcopy /E /I /Y 4.6.0-DEV-params dist\4.6.0-DEV-params
copy *.md dist
copy App_screenshot1.png dist
copy extract_param_defaults.py dist
copy param_pid_adjustment_update.py dist