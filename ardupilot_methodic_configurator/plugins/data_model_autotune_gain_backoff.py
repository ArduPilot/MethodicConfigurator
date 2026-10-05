"""
Stage additional gain-margin back-off on AutoTune results.

This file is part of ArduPilot Methodic Configurator.
https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2026 Amilcar do Carmo Lucas

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
    from ardupilot_methodic_configurator.data_model_parameter_editor import ParameterEditor


class AutotuneGainBackoffDataModel:
    """Apply one additional reduction, atomically, to active-step new values."""

    MIN_BACKOFF = 0.0
    MAX_BACKOFF = 0.5
    DEFAULT_BACKOFF = 0.25

    def __init__(self, parameter_editor: ParameterEditor) -> None:
        self.parameter_editor = parameter_editor
        self.range_warnings: list[str] = []

    @staticmethod
    def result_axes(filename: str) -> tuple[str, ...]:
        """Resolve the tuned axes without depending on the step number."""
        match = fullmatch(
            r"\d+_autotune_(roll|pitch|yaw|yawd|roll_pitch_retune|roll_RatePD|pitch_RatePD|"
            r"roll_pitch_AngleP|yaw_AngleP)_results\.param",
            filename,
        )
        if match is None:
            return ()
        return {
            "roll": ("RLL",),
            "pitch": ("PIT",),
            "yaw": ("YAW",),
            "yawd": ("YAW",),
            "roll_pitch_retune": ("RLL", "PIT"),
            "roll_RatePD": ("RLL",),
            "pitch_RatePD": ("PIT",),
            "roll_pitch_AngleP": ("RLL", "PIT"),
            "yaw_AngleP": ("YAW",),
        }[match[1]]

    def affected_parameter_names(self) -> list[str]:
        """Select only gains for the tuned axes, including P-derived rate I."""
        filename = self.parameter_editor.current_file
        names: set[str] = set()
        for axis in self.result_axes(filename):
            for prefix in ("ATC", "Q_A"):
                names.add(f"{prefix}_ANG_{axis}_P")
                terms = ("P", "I") if axis == "YAW" and "_yawd_" not in filename else ("P", "I", "D")
                names.update(f"{prefix}_RAT_{axis}_{term}" for term in terms)
        return sorted(names.intersection(self.parameter_editor.current_step_parameters))

    def apply_backoff(self, fraction: float) -> list[str]:
        """Validate all changes before staging any; never upload or save files."""
        self.range_warnings = []
        if not isfinite(fraction) or not self.MIN_BACKOFF <= fraction <= self.MAX_BACKOFF:
            raise ValueError(_("Gain margin back-off must be a finite number between 0.0 and 0.5."))
        if fraction == 0.0:
            return []
        changes: dict[str, tuple[str, str]] = {}
        warnings: list[str] = []
        parameters = self.parameter_editor.current_step_parameters
        for name in self.affected_parameter_names():
            parameter = parameters[name]
            if not parameter.is_editable:
                raise ValueError(_("Parameter {name} is not editable; no gains were changed.").format(name=name))
            current_value = parameter.get_new_value()
            old_value = parameter.value_as_string
            value = current_value * (1.0 - fraction)
            if not isfinite(value) or value < 0:
                raise ValueError(_("Parameter {name} must have a finite non-negative gain.").format(name=name))
            text = str(value)
            try:
                deepcopy(parameter).set_new_value(text)
            except ParameterUnchangedError:
                continue
            except ParameterOutOfRangeError as exc:
                warnings.append(str(exc))
                deepcopy(parameter).set_new_value(text, ignore_out_of_range=True)
            changes[name] = (old_value, text)
        for name, (old_value, text) in changes.items():
            parameter = parameters[name]
            parameter.set_new_value(text, ignore_out_of_range=True)
            previous_reason = parameter.change_reason
            reason = _("{old_value} backed-off by {percent:g}%").format(old_value=old_value, percent=100 * fraction)
            parameter.set_change_reason(f"{previous_reason}; {reason}" if previous_reason else reason)
        self.range_warnings = warnings
        return list(changes)
