# ruff: noqa: INP001
"""
Keep frozen builds from selecting a MAVLink dialect that is not bundled.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import os

# This hook runs before the application or pymavlink is imported. An unset value
# retains pymavlink's own default, while bundled dialects remain selectable.
if "MAVLINK_DIALECT" in os.environ and os.environ["MAVLINK_DIALECT"] not in {"all", "ardupilotmega"}:
    os.environ["MAVLINK_DIALECT"] = "ardupilotmega"
