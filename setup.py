#!/usr/bin/env python3

'''
This script creates the MethodicConfigurator pip python package

This file is part of Ardupilot methodic configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
'''

import shutil
import os

from setuptools import setup
from setuptools import find_packages

from MethodicConfigurator.version import VERSION

dev_requirements = [
    'ruff',
    'pytest',
    'pytest-cov',
    'coverage',
    'mock',
    # Add any other development requirements here
]

extra_scripts = [
    'MethodicConfigurator/annotate_params.py',
    'MethodicConfigurator/extract_param_defaults.py',
    'MethodicConfigurator/param_pid_adjustment_update.py'
]

PRJ_URL = "https://github.com/ArduPilot/MethodicConfigurator"

for file in extra_scripts:
    os.chmod(file, 0o755)

os.chmod("MethodicConfigurator/ardupilot_methodic_configurator.py", 0o755)

# Read the long description from the README file
with open('README.md', 'r', encoding='utf-8') as f:
    long_description = f.read()
    # Use Absolute links so that the pyPI page renders correctly
    long_description = long_description.replace("(USERMANUAL.md", f"({PRJ_URL}/blob/master/USERMANUAL.md")
    long_description = long_description.replace("(QUICKSTART.md", f"({PRJ_URL}/blob/master/QUICKSTART.md")
    long_description = long_description.replace("(CONTRIBUTING.md", f"({PRJ_URL}/blob/master/CONTRIBUTING.md")
    long_description = long_description.replace("(ARCHITECTURE.md", f"({PRJ_URL}/blob/master/ARCHITECTURE.md")
    long_description = long_description.replace("(CODE_OF_CONDUCT.md", f"({PRJ_URL}/blob/master/CODE_OF_CONDUCT.md")
    long_description = long_description.replace("(LICENSE.md", f"({PRJ_URL}/blob/master/LICENSE.md")
    long_description = long_description.replace("(credits/CREDITS.md", f"({PRJ_URL}/blob/master/credits/CREDITS.md")
    long_description = long_description.replace("images/App_screenshot1.png",
                                                f"{PRJ_URL}/raw/master/images/App_screenshot1.png")

# So that the vehicle_templates directory contents get correctly read by the MANIFEST.in file
TEMPLATES_SRC_DIR = 'vehicle_templates'
TEMPLATES_DST_DIR = 'MethodicConfigurator/vehicle_templates'

if os.path.exists(TEMPLATES_DST_DIR):
    shutil.rmtree(TEMPLATES_DST_DIR)

try:
    shutil.copytree(TEMPLATES_SRC_DIR, TEMPLATES_DST_DIR)
    print("Directory tree copied successfully.")
except FileExistsError:
    print(f"The destination directory '{TEMPLATES_DST_DIR}' already exists and cannot be overwritten.")
except PermissionError:
    print(f"Permission denied when trying to copy '{TEMPLATES_SRC_DIR}' to '{TEMPLATES_DST_DIR}'. " \
          "Please check your permissions.")
except Exception as e:  # pylint: disable=broad-except
    print(f"An unexpected error occurred while copying the directory tree: {e}")

setup(
    name='MethodicConfigurator',
    version=VERSION,
    zip_safe=True,
    description='A clear configuration sequence for ArduPilot vehicles',
    long_description=long_description,
    long_description_content_type='text/markdown',
    url=PRJ_URL,
    author='Amilcar do Carmo Lucas',
    author_email='amilcar.lucas@iav.de',
    packages=find_packages(),
    install_requires=[
        'defusedxml',
        'matplotlib',
        'numpy',
        'platformdirs',
        'pymavlink',
        'pyserial',
        'pillow',
        'setuptools',
        'requests',
    ],
    extras_require={
        'dev': dev_requirements,
    },
    classifiers=[
        'Development Status :: 4 - Beta',
        'Intended Audience :: Science/Research',
        'License :: OSI Approved :: GNU General Public License v3 (GPLv3)',
        'Operating System :: OS Independent',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
        'Programming Language :: Python :: 3.10',
        'Programming Language :: Python :: 3.11',
        'Programming Language :: Python :: 3.12',
        'Topic :: Scientific/Engineering',
    ],
    # Add the license
    license='GPLv3',
    python_requires='>=3.6',
    keywords=['ArduPilot', 'Configuration', 'SCM', 'Methodic', 'ArduCopter', 'ArduPlane', 'ArduRover', 'ArduSub'],
    include_package_data=True,
    scripts=extra_scripts,
    # Specify entry points for command-line scripts
    entry_points={
        'console_scripts': [
            'ardupilot_methodic_configurator=MethodicConfigurator.ardupilot_methodic_configurator:main',
            'extract_param_defaults=MethodicConfigurator.extract_param_defaults:main',
            'annotate_params=MethodicConfigurator.annotate_params:main',
            'param_pid_adjustment_update=MethodicConfigurator.param_pid_adjustment_update:main',
        ],
    },
    project_urls={
        'Homepage': PRJ_URL,
        'Documentation': f'{PRJ_URL}/blob/master/USERMANUAL.md',
        'Bug Tracker': f'{PRJ_URL}/issues',
        'Source Code': PRJ_URL,
        'Forum': 'https://discuss.ardupilot.org/t/new-ardupilot-methodic-configurator-gui/115038/',
        'Chat': 'https://discord.com/invite/ArduPilot',
        'Download': f'{PRJ_URL}/releases',
    },
)

# Remove the symbolic link now that the setup is done
if os.path.exists(TEMPLATES_DST_DIR):
    shutil.rmtree(TEMPLATES_DST_DIR)
