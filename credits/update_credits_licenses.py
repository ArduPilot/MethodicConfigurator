#!/usr/bin/env python3

"""
Downloads the licenses of the direct and indirect dependencies of the project.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import logging

import requests

# List of direct dependencies and their license URLs
direct_dependencies = [
    # {"name": "tkinter", "license_url": "https://docs.python.org/3/license.html"},
    # {"name": "argparse", "license_url": "https://docs.python.org/3/license.html"},
    # {"name": "logging", "license_url": "https://docs.python.org/3/license.html"},
    # {"name": "typing", "license_url": "https://docs.python.org/3/license.html"},
    # {"name": "json", "license_url": "https://docs.python.org/3/license.html"},
    # {"name": "os", "license_url": "https://docs.python.org/3/license.html"},
    # {"name": "re", "license_url": "https://docs.python.org/3/license.html"},
    # {"name": "webbrowser", "license_url": "https://docs.python.org/3/license.html"},
    {
        "name": "argcomplete",
        "license_url": "https://raw.githubusercontent.com/kislyuk/argcomplete/refs/heads/main/LICENSE.rst",
    },
    {
        "name": "ArduPilot tempcal_IMU.py",
        "license_url": "https://raw.githubusercontent.com/ArduPilot/ardupilot/master/COPYING.txt",
    },
    {"name": "Scrollable_TK_frame", "license_url": "https://mozilla.org/MPL/2.0/"},
    {"name": "Python_Tkinter_ComboBox", "license_url": "https://mozilla.org/MPL/2.0/"},
    {"name": "defusedxml", "license_url": "https://raw.githubusercontent.com/tiran/defusedxml/main/LICENSE"},
    {
        "name": "jsonschema",
        "license_url": "https://raw.githubusercontent.com/python-jsonschema/jsonschema/refs/heads/main/COPYING",
    },
    {"name": "matplotlib", "license_url": "https://raw.githubusercontent.com/matplotlib/matplotlib/main/LICENSE/LICENSE"},
    {"name": "numpy", "license_url": "https://raw.githubusercontent.com/numpy/numpy/main/LICENSE.txt"},
    {"name": "pillow", "license_url": "https://raw.githubusercontent.com/python-pillow/Pillow/main/LICENSE"},
    {"name": "platformdirs", "license_url": "https://raw.githubusercontent.com/platformdirs/platformdirs/main/LICENSE"},
    {"name": "pymavlink", "license_url": "https://raw.githubusercontent.com/ArduPilot/pymavlink/master/COPYING"},
    {"name": "pyserial", "license_url": "https://raw.githubusercontent.com/pyserial/pyserial/master/LICENSE.txt"},
    {"name": "requests", "license_url": "https://raw.githubusercontent.com/psf/requests/main/LICENSE"},
    {"name": "setuptools", "license_url": "https://raw.githubusercontent.com/pypa/setuptools/main/LICENSE"},
]


# List of indirect dependencies and their license URLs
indirect_dependencies = [
    {"name": "certifi", "license_url": "https://raw.githubusercontent.com/certifi/python-certifi/master/LICENSE"},
    {
        "name": "charset-normalizer",
        "license_url": "https://raw.githubusercontent.com/Ousret/charset_normalizer/master/LICENSE",
    },
    {"name": "future", "license_url": "https://raw.githubusercontent.com/PythonCharmers/python-future/master/LICENSE.txt"},
    {"name": "urllib3", "license_url": "https://raw.githubusercontent.com/urllib3/urllib3/main/LICENSE.txt"},
    {"name": "lxml", "license_url": "https://raw.githubusercontent.com/lxml/lxml/master/LICENSE.txt"},
    {"name": "idna", "license_url": "https://raw.githubusercontent.com/kjd/idna/master/LICENSE.md"},
]


def download_license(package_name: str, license_url: str) -> None:
    try:
        response = requests.get(license_url, timeout=10)
        response.raise_for_status()  # Raise an exception if the request failed
        # Use a fixed filename for the Mozilla Public License version 2.0
        if package_name in {"Scrollable_TK_frame", "Python_Tkinter_ComboBox"}:
            filename = f"{package_name}-Mozilla_Public_License_version_2.0.html"
        else:
            filename = f"{package_name}-{license_url.rsplit('/', 1)[-1]}"
        with open(filename, "wb") as f:
            f.write(response.content)
        msg = f"Downloaded {filename}"
        logging.info(msg)
    except requests.exceptions.RequestException as e:
        msg = f"Failed to download {package_name} license: {e}"
        logging.error(msg)


logging.basicConfig(level="INFO", format="%(asctime)s - %(levelname)s - %(message)s")

# Download each package's license
for package in direct_dependencies + indirect_dependencies:
    download_license(package["name"].replace(" ", "_"), package["license_url"])
