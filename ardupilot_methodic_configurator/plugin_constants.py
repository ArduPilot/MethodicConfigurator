"""
Plugin name constants for the ArduPilot Methodic Configurator.

This module defines constants for plugin names to maintain DRY principle
and avoid duplication across the codebase.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

# To add a new plugin, you must touch five places:
#   1. Here (``plugin_constants.py``)                            - add a PLUGIN_* constant.
#   2. ``__main__.py -> register_plugins()``                     - import and call its register function.
#   3. ``data_model_parameter_editor.create_plugin_data_model``  - instantiate its data model.
#   4. The plugin's ``frontend_tkinter_*.py`` module             - implement and call ``plugin_factory.register``.
#   5. On ``ardupilot_methodic_configurator\configuration_steps_schema.json`` - add the plugin name to
#      ``plugin > properties > enum`` in the configuration steps schema.

# Plugin name constants
PLUGIN_MOTOR_TEST = "motor_test"
PLUGIN_BATTERY_MONITOR = "battery_monitor"
PLUGIN_COMPASS_CALIBRATION = "compass_calibration"
PLUGIN_ACCELEROMETER_CALIBRATION = "accelerometer_calibration"
PLUGIN_RC_CALIBRATION = "rc_calibration"
