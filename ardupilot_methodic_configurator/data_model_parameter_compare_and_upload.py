"""
Selection rules and snapshot updates for external parameter uploads.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2026 Amilcar Lucas

SPDX-License-Identifier: GPL-3.0-or-later
"""

from collections.abc import Callable, Iterable

from ardupilot_methodic_configurator import _
from ardupilot_methodic_configurator.data_model_ardupilot_parameter import ArduPilotParameter


def selected_external_parameters(
    parameters: dict[str, ArduPilotParameter], selected_names: Iterable[str]
) -> dict[str, ArduPilotParameter]:
    """Return selected external parameters that the FC permits uploading."""
    return {name: parameters[name] for name in selected_names if name in parameters and not parameters[name].is_readonly}


def unselected_manual_edits(
    parameters: dict[str, ArduPilotParameter], manually_editable_names: Iterable[str], selected_names: Iterable[str]
) -> list[str]:
    """Find changed manual edits that the user has left out of the upload."""
    selected = set(selected_names)
    return [
        name
        for name in sorted(manually_editable_names)
        if name in parameters and parameters[name].is_dirty and parameters[name].is_different_from_fc and name not in selected
    ]


def confirm_external_upload_selection(omitted_manual_edits: list[str], show_warning: Callable[[str, str], None]) -> bool:
    """Warn and stop when temporary manual edits would be discarded."""
    if not omitted_manual_edits:
        return True
    show_warning(
        _("Manual parameter edits not selected"),
        _(
            "The following manually edited parameters differ from the flight controller "
            "but are not selected for upload:\n\n{parameter_names}"
        ).format(parameter_names="\n".join(omitted_manual_edits)),
    )
    return False


def refresh_external_fc_values(parameters: dict[str, ArduPilotParameter], fc_parameters: dict[str, float]) -> None:
    """Update a preview after the FC has verified the uploaded values."""
    for name, parameter in parameters.items():
        if name in fc_parameters:
            parameter.set_fc_value(fc_parameters[name])
