"""
Conversions shared by parameter upload and export workflows.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2026 Amilcar Lucas

SPDX-License-Identifier: GPL-3.0-or-later
"""

from ardupilot_methodic_configurator.data_model_ardupilot_parameter import ArduPilotParameter
from ardupilot_methodic_configurator.data_model_par_dict import Par, ParDict


def parameters_as_par_dict(parameters: dict[str, ArduPilotParameter]) -> ParDict:
    """Convert parameter objects to parameter-file values and comments."""
    return ParDict(
        {name: Par(parameter.get_new_value(), parameter.change_reason_for_file) for name, parameter in parameters.items()}
    )
