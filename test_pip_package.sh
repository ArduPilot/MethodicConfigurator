#!/bin/bash

sudo pip uninstall -y MethodicConfigurator
pip uninstall -y MethodicConfigurator
sudo rm -Rf /usr/local/MethodicConfigurator/

sudo pip uninstall -y ardupilot_methodic_configurator
pip uninstall -y ardupilot_methodic_configurator
sudo rm -Rf /usr/local/ardupilot_methodic_configurator/

sudo rm -Rf /usr/local/vehicle_templates/
sudo rm -Rf /usr/local/locale/
rm -Rf ~/.local/locale
rm -Rf ~/.local/vehicle_templates

rm -Rf ~/.local/MethodicConfigurator
rm -Rf ~/.local/bin/MethodicConfigurator
rm -Rf build dist/ MethodicConfigurator.egg-info/

rm -Rf ~/.local/ardupilot_methodic_configurator
rm -Rf ~/.local/bin/ardupilot_methodic_configurator
rm -Rf build dist/ ardupilot_methodic_configurator.egg-info/

uv venv --python 3.12
source .venv/Scripts/activate
uv pip install -U build packaging setuptools wheel

python -m build

uv pip install -U dist/ardupilot_methodic_configurator-2.0.3-py3-none-any.whl

cd ..

ardupilot_methodic_configurator --language=pt --loglevel=DEBUG
ls -larct /usr/local
