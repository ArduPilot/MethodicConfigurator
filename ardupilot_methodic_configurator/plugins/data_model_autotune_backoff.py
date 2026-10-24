"""
Validate scaled AutoTune parameters before staging any changes.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

from collections.abc import Mapping, Sequence
from copy import deepcopy
from math import isfinite

from ardupilot_methodic_configurator.data_model_ardupilot_parameter import (
    ArduPilotParameter,
    ParameterOutOfRangeError,
    ParameterUnchangedError,
)


def prepare_scaled_parameters(
    parameters: Mapping[str, ArduPilotParameter],
    names: Sequence[str],
    ratio: float,
    *,
    not_editable_message: str,
    invalid_value_message: str,
) -> tuple[dict[str, tuple[str, str]], list[str]]:
    """Validate candidates on copies, preserving atomicity and metadata warnings."""
    changes: dict[str, tuple[str, str]] = {}
    warnings: list[str] = []
    for name in names:
        parameter = parameters[name]
        if not parameter.is_editable:
            raise ValueError(not_editable_message.format(name=name))
        current_value = parameter.get_new_value()
        value = current_value * ratio
        if not isfinite(value) or value < 0 or (current_value > 0 and value == 0):
            raise ValueError(invalid_value_message.format(name=name))
        text = str(value)
        candidate = deepcopy(parameter)
        try:
            candidate.set_new_value(text)
        except ParameterUnchangedError:
            continue
        except ParameterOutOfRangeError as exc:
            warnings.append(str(exc))
            candidate.set_new_value(text, ignore_out_of_range=True)
        changes[name] = (parameter.value_as_string, text)
    return changes, warnings
