"""
Stage takeoff-weight compensation for AutoTune acceleration limits.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

from __future__ import annotations

from copy import deepcopy
from math import isfinite
from re import fullmatch
from typing import TYPE_CHECKING

from ardupilot_methodic_configurator import _
from ardupilot_methodic_configurator.data_model_ardupilot_parameter import ParameterOutOfRangeError, ParameterUnchangedError

if TYPE_CHECKING:
    from ardupilot_methodic_configurator.backend_filesystem import LocalFilesystem
    from ardupilot_methodic_configurator.data_model_parameter_editor import ParameterEditor


class AutotuneAccelBackoffDataModel:
    """Reduce staged acceleration limits atomically, without saving or uploading."""

    def __init__(self, parameter_editor: ParameterEditor, filesystem: LocalFilesystem) -> None:
        self.parameter_editor = parameter_editor
        self.filesystem = filesystem
        self.range_warnings: list[str] = []
        self.has_applied = False

    def takeoff_weights(self) -> tuple[str, str]:
        """Read the project's minimum and maximum takeoff weights in kilograms."""
        components = self.filesystem.get_eval_variables().get("vehicle_components", {})
        specifications = components.get("Frame", {}).get("Specifications", {})
        return str(specifications.get("TOW min Kg", "")), str(specifications.get("TOW max Kg", ""))

    def affected_parameter_names(self) -> list[str]:
        """Select existing limits in finish steps, using either firmware naming scheme."""
        if fullmatch(r"\d+_autotune_finish\.param", self.parameter_editor.current_file) is None:
            return []
        names = {
            f"{prefix}_{acceleration}_{axis}_MAX"
            for prefix in ("ATC", "Q_A")
            for acceleration in ("ACCEL", "ACC")
            for axis in ("R", "P", "Y")
        }
        return sorted(names.intersection(self.parameter_editor.current_step_parameters))

    def apply_backoff(self, min_tow: float, max_tow: float) -> list[str]:
        """Multiply current New values by min/max TOW once for this model."""
        if self.has_applied:
            raise ValueError(_("Acceleration limits have already been scaled for this step."))
        self.range_warnings = []
        if not isfinite(min_tow) or not isfinite(max_tow) or not 0 < min_tow <= max_tow:
            raise ValueError(_("Takeoff weights must be finite and positive, with minimum no greater than maximum."))
        ratio = min_tow / max_tow
        if ratio <= 0:
            raise ValueError(_("The minimum / maximum takeoff weight ratio is too small."))
        if ratio == 1.0:
            self.has_applied = True
            return []
        changes: dict[str, tuple[str, str]] = {}
        warnings: list[str] = []
        parameters = self.parameter_editor.current_step_parameters
        for name in self.affected_parameter_names():
            parameter = parameters[name]
            if not parameter.is_editable:
                raise ValueError(_("Parameter {name} is not editable; no acceleration limits were changed.").format(name=name))
            current_value = parameter.get_new_value()
            value = current_value * ratio
            if not isfinite(value) or value < 0 or (current_value > 0 and value == 0):
                raise ValueError(_("Parameter {name} must have a finite non-negative acceleration limit.").format(name=name))
            text = str(value)
            try:
                deepcopy(parameter).set_new_value(text)
            except ParameterUnchangedError:
                continue
            except ParameterOutOfRangeError as exc:
                warnings.append(str(exc))
                deepcopy(parameter).set_new_value(text, ignore_out_of_range=True)
            changes[name] = (parameter.value_as_string, text)
        for name, (old_value, text) in changes.items():
            parameter = parameters[name]
            parameter.set_new_value(text, ignore_out_of_range=True)
            reason = _("{old_value} scaled by minimum / maximum takeoff weight ({min_tow:g} / {max_tow:g} kg)").format(
                old_value=old_value, min_tow=min_tow, max_tow=max_tow
            )
            parameter.set_change_reason(f"{parameter.change_reason}; {reason}" if parameter.change_reason else reason)
        self.range_warnings = warnings
        self.has_applied = True
        return list(changes)
