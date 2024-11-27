sudo pip uninstall -y ardupilot_methodic_configurator
pip uninstall -y ardupilot_methodic_configurator
sudo rm -Rf /usr/local/ardupilot_methodic_configurator/
sudo rm -Rf /usr/local/vehicle_templates/
sudo rm -Rf /usr/local/locale/
rm -Rf ~/.local/locale
rm -Rf ~/.local/vehicle_templates
rm -Rf ~/.local/ardupilot_methodic_configurator
rm -Rf build dist/ ardupilot_methodic_configurator.egg-info/
python -m build --wheel .

# Use either this
sudo pip install -U dist/ardupilot_methodic_configurator-0.9.16-py3-none-any.whl

# Or this
#pip install -U dist/ardupilot_methodic_configurator-0.9.16-py3-none-any.whl


cd ..
ardupilot_methodic_configurator --language=pt
~/.local/bin/ardupilot_methodic_configurator --language=pt
ls -larct /usr/local

