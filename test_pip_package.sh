sudo pip uninstall -y MethodicConfigurator
pip uninstall -y MethodicConfigurator
sudo rm -Rf /usr/local/MethodicConfigurator/
sudo rm -Rf /usr/local/vehicle_templates/
sudo rm -Rf /usr/local/locale/
rm -Rf ~/.local/locale
rm -Rf ~/.local/vehicle_templates
rm -Rf ~/.local/MethodicConfigurator
rm -Rf build dist/ MethodicConfigurator.egg-info/
python -m build --wheel .

# Use either this
sudo pip install -U dist/MethodicConfigurator-0.9.11-py3-none-any.whl

# Or this
#pip install -U dist/MethodicConfigurator-0.9.11-py3-none-any.whl


cd ..
ardupilot_methodic_configurator --language=pt
~/.local/bin/ardupilot_methodic_configurator --language=pt
ls -larct /usr/local

