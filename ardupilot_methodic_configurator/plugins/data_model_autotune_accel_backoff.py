"""
Stage takeoff-weight compensation for AutoTune acceleration limits.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

from __future__ import annotations

from math import isfinite
from re import fullmatch
from typing import TYPE_CHECKING

from ardupilot_methodic_configurator import _
from ardupilot_methodic_configurator.plugins.data_model_autotune_backoff import prepare_scaled_parameters

if TYPE_CHECKING:
    from ardupilot_methodic_configurator.backend_filesystem import LocalFilesystem
    from ardupilot_methodic_configurator.data_model_parameter_editor import ParameterEditor


class AutotuneAccelBackoffDataModel:
    """Reduce staged acceleration limits atomically, without saving or uploading."""

    APPLIED_MARKER = "@autotune_accel_backoff"

    def __init__(self, parameter_editor: ParameterEditor, filesystem: LocalFilesystem) -> None:
        self.parameter_editor = parameter_editor
        self.filesystem = filesystem
        self.range_warnings: list[str] = []
        self.has_applied = any(
            self.APPLIED_MARKER in parameter.change_reason
            or " scaled by minimum / maximum takeoff weight (" in parameter.change_reason
            for name in self.affected_parameter_names()
            for parameter in (self.parameter_editor.current_step_parameters[name],)
        )

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
        """Multiply current New values by min/max TOW once, retaining the guard in saved change reasons."""
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
        changes, warnings = prepare_scaled_parameters(
            self.parameter_editor.current_step_parameters,
            self.affected_parameter_names(),
            ratio,
            not_editable_message=_("Parameter {name} is not editable; no acceleration limits were changed."),
            invalid_value_message=_("Parameter {name} must have a finite non-negative acceleration limit."),
        )
        parameters = self.parameter_editor.current_step_parameters
        for name, (old_value, text) in changes.items():
            parameter = parameters[name]
            parameter.set_new_value(text, ignore_out_of_range=True)
            reason = _("{old_value} scaled by minimum / maximum takeoff weight ({min_tow:g} / {max_tow:g} kg)").format(
                old_value=old_value, min_tow=min_tow, max_tow=max_tow
            )
            reason = f"{reason} {self.APPLIED_MARKER}"
            parameter.set_change_reason(f"{parameter.change_reason}; {reason}" if parameter.change_reason else reason)
        self.range_warnings = warnings
        self.has_applied = True
        return list(changes)
