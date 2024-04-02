from setuptools import setup, find_packages
from ardupilot_methodic_configurator import VERSION

# Read the long description from the README file
with open('README.md', 'r', encoding='utf-8') as f:
    long_description = f.read()

setup(
    name='ArduPilot_methodic_configurator',
    version='0.1.0',
    author='Amilcar do Carmo Lucas',
    author_email='amilcar.lucas@iav.de',
    description='A tool for methodically configure ArduPilot drones',
    long_description=long_description,
    long_description_content_type='text/markdown',
    url='https://github.com/amilcarlucas/ArduPilot_methodic_configurator',
    packages=find_packages(),
    install_requires=[
        'pymavlink',
        'tkinter',
        'argparse',
        'logging',
        'pyserial',
        'pyusb',
        'typing',
        'json',
        'os',
        're',
        'webbrowser',
    ],
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: GNU General Public License v3 (GPLv3)',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
    ],
    python_requires='>=3.6',
    # Include package data
    #package_data={
    #    # If you have data files
    #    '': ['*.md', '*.txt', '*.xml', '*.json'],
    #    '4.3.8-params': ['*.param'],
    #    '4.4.4-params': ['*.param'],
    #    '4.5.0-beta2-params': ['*.param'],
    #    '4.6.0-DEV-params': ['*.param'],
    #},
    # Specify entry points for command-line scripts
    entry_points={
        'console_scripts': [
            'ardupilot_methodic_configurator=ardupilot_methodic_configurator:main',
        ],
    },
    # Add the license
    license='GPLv3',
)
