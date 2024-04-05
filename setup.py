from setuptools import setup
from setuptools import find_packages

import os

from MethodicConfigurator.version import VERSION


def package_files(directory):
    paths = []
    for (path, _directories, filenames) in os.walk(directory):
        for filename in filenames:
            paths.append(os.path.join('..', path, filename))
    return paths


package_data = [
    'vehcle_examples/diatone_taycan_mxc/*',
    # Add any other package_data requirements here
]

# note that we do not include all the real dependencies here (like lxml etc)
# as that breaks the pip install. It seems that pip is not smart enough to
# use the system versions of these dependencies, so it tries to download and install
# large numbers of modules like tkinter etc which may be already installed
requirements = ['pymavlink>=2.4.14',
                'pyserial>=3.0']

dev_requirements = [
    'flake8',
    # Add any other development requirements here
]

# Read the long description from the README file
with open('README.md', 'r', encoding='utf-8') as f:
    long_description = f.read()

setup(
    name='ArduPilot_methodic_configurator',
    version=VERSION,
    zip_safe=True,
    description='A tool to methodically configure ArduPilot drones',
    long_description=long_description,
    long_description_content_type='text/markdown',
    url='https://github.com/amilcarlucas/ArduPilot_methodic_configurator',
    author='Amilcar do Carmo Lucas',
    author_email='amilcar.lucas@iav.de',
    packages=find_packages(),
    install_requires=[
        'pymavlink',
        'pyserial',
        'pillow',
        'requests',
    ],
    extras_require={
        'dev': dev_requirements,
    },
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Intended Audience :: Science/Research',
        'License :: OSI Approved :: GNU General Public License v3 (GPLv3)',
        'Operating System :: OS Independent',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
        'Programming Language :: Python :: 3.10',
        'Topic :: Scientific/Engineering',
    ],
    # Add the license
    license='GPLv3',
    python_requires='>=3.6',
    # Include package data
    # package_data={
    #    # If you have data files
    #    '': ['*.md', '*.txt', '*.xml', '*.json'],
    #    '4.3.8-params': ['*.param'],
    #    '4.4.4-params': ['*.param'],
    #    '4.5.0-beta2-params': ['*.param'],
    #    '4.6.0-DEV-params': ['*.param'],
    # },
    # Specify entry points for command-line scripts
    entry_points={
        'console_scripts': [
            'ardupilot_methodic_configurator=MethodicConfigurator.ardupilot_methodic_configurator:main',
        ],
    },
)
