"""
Plugin name constants for the ArduPilot Methodic Configurator.

This module defines constants for plugin names to maintain DRY principle
and avoid duplication across the codebase.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

# To add a new plugin, you must touch four places:
#   1. Here (``plugin_constants.py``)                            - add a PLUGIN_* constant.
#   2. ``__main__.py -> register_plugins()``                     - import and call its register function.
#   3. The plugin's ``frontend_tkinter_*.py`` module             - register its view and data-model factories.
#   4. On ``ardupilot_methodic_configurator\configuration_steps_schema.json`` - add the plugin name to
#      ``plugin > properties > enum`` in the configuration steps schema.

# Plugin name constants
PLUGIN_MOTOR_TEST = "motor_test"
PLUGIN_BATTERY_MONITOR = "battery_monitor"
PLUGIN_COMPASS_CALIBRATION = "compass_calibration"
PLUGIN_ACCELEROMETER_CALIBRATION = "accelerometer_calibration"
PLUGIN_LEVEL_CALIBRATION = "level_calibration"
PLUGIN_SERVO_OUT = "servo_out"
PLUGIN_AHRS_ORIENTATION = "ahrs_orientation"
PLUGIN_ESC_RPM_SCALE = "esc_rpm_scale"
PLUGIN_RC_CALIBRATION = "rc_calibration"
