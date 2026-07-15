#!/bin/bash

sudo pip uninstall -y MethodicConfigurator
pip uninstall -y MethodicConfigurator
uv pip uninstall MethodicConfigurator
sudo rm -Rf /usr/local/MethodicConfigurator/

sudo pip uninstall -y ardupilot_methodic_configurator
pip uninstall -y ardupilot_methodic_configurator
uv pip uninstall ardupilot_methodic_configurator
sudo rm -Rf /usr/local/ardupilot_methodic_configurator/

sudo rm -Rf /usr/local/vehicle_templates/
#sudo rm -Rf /usr/local/locale/
rm -Rf ~/.local/locale
rm -Rf ~/.local/vehicle_templates

rm -Rf ~/.local/MethodicConfigurator
rm -Rf ~/.local/bin/MethodicConfigurator
rm -Rf build dist/ MethodicConfigurator.egg-info/

rm -Rf ~/.local/ardupilot_methodic_configurator
rm -Rf ~/.local/bin/ardupilot_methodic_configurator
rm -Rf build dist/ ardupilot_methodic_configurator.egg-info/

uv venv --python 3.10 .venv
# shellcheck source=/dev/null
if [[ "$OSTYPE" == "msys" || "$OSTYPE" == "win32" ]]; then
    source .venv/Scripts/activate
else
    source .venv/bin/activate
fi
uv pip install "build==1.5.1" "packaging==26.2" "setuptools==83.0.0"

python -m build

uv pip install -U dist/ardupilot_methodic_configurator-4.0.2-py3-none-any.whl

cd ..

ardupilot_methodic_configurator --language=pt --loglevel=DEBUG
ls -larct /usr/local
