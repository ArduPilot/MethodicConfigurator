#!/usr/bin/env python3
"""
Behavior-driven tests for AutoTune takeoff-weight compensation.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import json
import tkinter as tk
from collections.abc import Callable
from pathlib import Path
from types import SimpleNamespace
from typing import TYPE_CHECKING, cast
from unittest.mock import MagicMock, patch

import jsonschema
import pytest

from ardupilot_methodic_configurator.__main__ import register_plugins
from ardupilot_methodic_configurator.backend_filesystem import LocalFilesystem
from ardupilot_methodic_configurator.backend_filesystem_json_with_schema import FilesystemJSONWithSchema
from ardupilot_methodic_configurator.data_model_ardupilot_parameter import ArduPilotParameter
from ardupilot_methodic_configurator.data_model_par_dict import Par, ParDict
from ardupilot_methodic_configurator.data_model_safe_evaluator import safe_evaluate
from ardupilot_methodic_configurator.frontend_tkinter_base_window import BaseWindow
from ardupilot_methodic_configurator.plugins import frontend_tkinter_autotune_accel_backoff as frontend
from ardupilot_methodic_configurator.plugins.data_model_autotune_accel_backoff import AutotuneAccelBackoffDataModel
from ardupilot_methodic_configurator.plugins.plugin_constants import PLUGIN_AUTOTUNE_ACCEL_BACKOFF
from ardupilot_methodic_configurator.plugins.plugin_factory import PluginModelContext, plugin_factory

if TYPE_CHECKING:
    from ardupilot_methodic_configurator.data_model_parameter_editor import ParameterEditor

# pylint: disable=redefined-outer-name

ModelFactory = Callable[..., AutotuneAccelBackoffDataModel]


@pytest.fixture
def model_factory() -> ModelFactory:
    """Use real parameters and filesystem adapters with loaded in-memory project data."""

    def create(prefix: str = "ATC", acceleration: str = "ACCEL") -> AutotuneAccelBackoffDataModel:
        values: dict[str, float] = {
            f"{prefix}_{acceleration}_{axis}_MAX": value for axis, value in (("R", 90000), ("P", 60000), ("Y", 18000))
        }
        values.update({"ATC_THR_MIX_MAX": 0.9, "ATC_RAT_RLL_P": 0.16})
        parameters = {
            name: ArduPilotParameter(name, Par(value, "Existing reason"), fc_value=value) for name, value in values.items()
        }
        editor = cast(
            "ParameterEditor", SimpleNamespace(current_file="49_autotune_finish.param", current_step_parameters=parameters)
        )
        filesystem = LocalFilesystem.__new__(LocalFilesystem)
        filesystem.vehicle_components_fs = FilesystemJSONWithSchema("vehicle_components.json", "")
        filesystem.vehicle_components_fs.data = {
            "Components": {"Frame": {"Specifications": {"TOW min Kg": 2.0, "TOW max Kg": 3.0}}}
        }
        return AutotuneAccelBackoffDataModel(editor, filesystem)

    return create


def snapshot(model: AutotuneAccelBackoffDataModel) -> dict[str, tuple[str, str, str, bool]]:
    """Capture values, FC state, reasons and dirty state, including invalid floats."""
    return {
        name: (
            repr(parameter.get_new_value()),
            parameter.fc_value_as_string,
            parameter.change_reason_for_file,
            parameter.is_dirty,
        )
        for name, parameter in model.parameter_editor.current_step_parameters.items()
    }


@pytest.mark.parametrize("prefix", ["ATC", "Q_A"])
@pytest.mark.parametrize("acceleration", ["ACCEL", "ACC"])
def test_weight_ratio_reduces_only_current_acceleration_limits(
    model_factory: ModelFactory, prefix: str, acceleration: str
) -> None:
    """
    Apply weight compensation in either firmware unit system.

    GIVEN: A finish step with acceleration limits, gains and throttle mix.
    WHEN: The user applies a 2 kg / 3 kg ratio.
    THEN: Only the three acceleration New values and their reasons change.
    """
    model = model_factory(prefix, acceleration)
    before = snapshot(model)
    changed = model.apply_backoff(2, 3)
    assert set(changed) == {f"{prefix}_{acceleration}_{axis}_MAX" for axis in ("R", "P", "Y")}
    for name, parameter in model.parameter_editor.current_step_parameters.items():
        if name in changed:
            assert parameter.get_new_value() == pytest.approx(float(before[name][0]) * 2 / 3)
            assert parameter.fc_value_as_string == before[name][1]
            assert parameter.is_dirty
            assert parameter.change_reason == (
                f"Existing reason; {before[name][1]} scaled by minimum / maximum takeoff weight (2 / 3 kg)"
                " @autotune_accel_backoff"
            )
        else:
            assert snapshot(model)[name] == before[name]


@pytest.mark.parametrize(
    ("minimum", "maximum"),
    [
        (0, 3),
        (-1, 3),
        (2, 0),
        (3, 2),
        (float("nan"), 3),
        (2, float("inf")),
        (float("inf"), 3),
        (2, float("nan")),
        (-2, -1),
        (1e-300, 1e300),
    ],
)
def test_invalid_weights_leave_all_parameters_unchanged(model_factory: ModelFactory, minimum: float, maximum: float) -> None:
    """
    Invalid weight ranges cannot change a tune.

    GIVEN: Valid acceleration limits.
    WHEN: Weights are zero, negative, reversed, non-finite or underflow the ratio.
    THEN: An error occurs before any staged value or reason changes.
    """
    model = model_factory()
    before = snapshot(model)
    with pytest.raises(ValueError, match=r"takeoff weight|Takeoff weights"):
        model.apply_backoff(minimum, maximum)
    assert snapshot(model) == before
    assert not model.has_applied


@pytest.mark.parametrize("invalid_kind", ["readonly", "forced", "negative", "nonfinite"])
def test_one_invalid_limit_prevents_partial_reductions(model_factory: ModelFactory, invalid_kind: str) -> None:
    """
    All acceleration limits are validated before mutation.

    GIVEN: The last target is read-only, forced, negative or non-finite.
    WHEN: Weight compensation is applied.
    THEN: Earlier targets retain their values and reasons.
    """
    model = model_factory()
    name = "ATC_ACCEL_Y_MAX"
    model.parameter_editor.current_step_parameters[name] = ArduPilotParameter(
        name,
        Par(-1 if invalid_kind == "negative" else float("nan") if invalid_kind == "nonfinite" else 18000),
        {"ReadOnly": invalid_kind == "readonly"},
        forced_par=Par(18000) if invalid_kind == "forced" else None,
    )
    before = snapshot(model)
    with pytest.raises(ValueError, match=r"not editable|finite non-negative"):
        model.apply_backoff(2, 3)
    assert snapshot(model) == before


def test_repeated_reductions_are_blocked_and_preserve_override_marker(model_factory: ModelFactory) -> None:
    """
    Only one reduction is allowed for the staged values.

    GIVEN: A manually overridden acceleration limit with a user reason.
    WHEN: The user changes its New value and applies the ratio twice.
    THEN: The second attempt is rejected and the reason retains one manual-override marker.
    """
    model = model_factory()
    parameter = ArduPilotParameter("ATC_ACCEL_R_MAX", Par(90000, "@manual_override Manual reason"), forced_par=Par(90000))
    model.parameter_editor.current_step_parameters[parameter.name] = parameter
    parameter.set_new_value("120000")
    model.apply_backoff(2, 3)
    before = snapshot(model)
    with pytest.raises(ValueError, match="already been scaled"):
        model.apply_backoff(1, 2)
    assert snapshot(model) == before
    assert model.has_applied
    assert parameter.get_new_value() == pytest.approx(80000)
    assert (
        parameter.change_reason == "Manual reason; 120000 scaled by minimum / maximum takeoff weight (2 / 3 kg)"
        " @autotune_accel_backoff"
    )
    assert parameter.change_reason_for_file.count("@manual_override") == 1


def test_equal_weights_missing_limits_and_disabled_limits_are_preserved(model_factory: ModelFactory) -> None:
    """
    Neutral ratios and disabled limits remain unchanged.

    GIVEN: Equal weights followed by an incomplete step with a disabled axis.
    WHEN: Compensation is applied.
    THEN: Equal weights are a no-op, zero stays zero and missing axes are not added.
    """
    model = model_factory()
    before = snapshot(model)
    assert model.apply_backoff(2, 2) == []
    assert snapshot(model) == before
    with pytest.raises(ValueError, match="already been scaled"):
        model.apply_backoff(2, 3)
    model = model_factory()
    parameters = model.parameter_editor.current_step_parameters
    del parameters["ATC_ACCEL_R_MAX"]
    parameters["ATC_ACCEL_Y_MAX"] = ArduPilotParameter("ATC_ACCEL_Y_MAX", Par(0))
    assert model.apply_backoff(2, 3) == ["ATC_ACCEL_P_MAX"]
    assert "ATC_ACCEL_R_MAX" not in parameters
    assert parameters["ATC_ACCEL_Y_MAX"].get_new_value() == 0
    assert not parameters["ATC_ACCEL_Y_MAX"].is_dirty


def test_non_finish_steps_do_not_expose_acceleration_targets(model_factory: ModelFactory) -> None:
    """
    Compensation belongs to finish steps.

    GIVEN: An AutoTune results step with acceleration parameters.
    WHEN: The plugin is asked to compensate for weight.
    THEN: No targets are exposed and no values change.
    """
    model = model_factory()
    model.parameter_editor.current_file = "36_autotune_roll_results.param"
    before = snapshot(model)
    assert model.apply_backoff(2, 3) == []
    assert snapshot(model) == before


@pytest.mark.parametrize("minimum", ["not a number", "0", "nan", "4"])
def test_apply_button_rejects_invalid_input_without_refreshing(
    tk_root: "tk.Tk", model_factory: ModelFactory, minimum: str
) -> None:
    """
    Invalid entries receive useful feedback.

    GIVEN: A view initialized from project weights.
    WHEN: The user applies invalid text or an invalid weight range.
    THEN: A stable message appears without changing parameters or refreshing.
    """
    model = model_factory()
    before = snapshot(model)
    with (
        patch.object(frontend, "show_tooltip"),
        patch.object(frontend, "showerror") as error,
        patch.object(frontend, "refresh_parameter_editor_table") as refresh,
    ):
        view = frontend.AutotuneAccelBackoffView(tk.Frame(tk_root), model, MagicMock(spec=BaseWindow))
        try:
            assert view.min_tow.get() == "2.0"
            assert view.max_tow.get() == "3.0"
            view.min_tow.set(minimum)
            view.apply_button.invoke()
            message = (
                "Enter numeric minimum and maximum takeoff weights in kg."
                if minimum == "not a number"
                else "Takeoff weights must be finite and positive, with minimum no greater than maximum."
            )
            error.assert_called_once_with("AutoTune acceleration limits", message, parent=view)
            refresh.assert_not_called()
            assert snapshot(model) == before
            assert not model.has_applied
            assert not view.apply_button.instate(["disabled"])
            view.min_tow.set("2")
            view.apply_button.invoke()
            assert model.has_applied
            assert view.apply_button.instate(["disabled"])
            refresh.assert_called_once()
        finally:
            view.destroy()


def test_registered_offline_plugin_stages_values_and_refreshes_the_table(
    tk_root: "tk.Tk", model_factory: ModelFactory
) -> None:
    """
    Startup registers working model and view factories.

    GIVEN: Loaded project weights and an editor without a flight controller.
    WHEN: The user presses the registered plugin's Apply button twice.
    THEN: Only the first click changes limits and lifecycle retains the disabled button.
    """
    original = model_factory()
    register_plugins()
    context = PluginModelContext(MagicMock(), original.filesystem, original.parameter_editor)
    model = plugin_factory.create_model(PLUGIN_AUTOTUNE_ACCEL_BACKOFF, context)
    assert isinstance(model, AutotuneAccelBackoffDataModel)
    assert not plugin_factory.requires_flight_controller(PLUGIN_AUTOTUNE_ACCEL_BACKOFF)
    base_window = MagicMock(spec=BaseWindow)
    with patch.object(frontend, "show_tooltip"), patch.object(frontend, "refresh_parameter_editor_table") as refresh:
        view = plugin_factory.create(PLUGIN_AUTOTUNE_ACCEL_BACKOFF, tk.Frame(tk_root), model, base_window)
        assert isinstance(view, frontend.AutotuneAccelBackoffView)
        try:
            view.apply_button.invoke()
            assert view.apply_button.instate(["disabled"])
            view.apply_button.invoke()
            assert model.parameter_editor.current_step_parameters["ATC_ACCEL_R_MAX"].get_new_value() == pytest.approx(60000)
            refresh.assert_called_once_with(base_window)
            assert "ATC_ACCEL_R_MAX" in view.status.get()
            view.on_suspend()
            view.on_resume()
            view.on_deactivate()
            view.on_activate()
            assert "ATC_ACCEL_R_MAX" in view.status.get()
            assert view.apply_button.instate(["disabled"])
            view.apply_button.invoke()
            refresh.assert_called_once_with(base_window)
            assert view.min_tow.get() == "2.0"
        finally:
            view.destroy()

        fresh_model = AutotuneAccelBackoffDataModel(model.parameter_editor, model.filesystem)
        recreated = plugin_factory.create(PLUGIN_AUTOTUNE_ACCEL_BACKOFF, tk.Frame(tk_root), fresh_model, base_window)
        assert isinstance(recreated, frontend.AutotuneAccelBackoffView)
        try:
            assert recreated.apply_button.instate(["disabled"])
            recreated.apply_button.invoke()
            refresh.assert_called_once_with(base_window)
        finally:
            recreated.destroy()


def test_out_of_range_reductions_warn_after_staging(tk_root: "tk.Tk", model_factory: ModelFactory) -> None:
    """
    Recommended metadata ranges follow the existing gain back-off behavior.

    GIVEN: A limit whose reduction will fall below its recommended minimum.
    WHEN: The user presses Apply.
    THEN: The limit changes, a warning appears and the table refreshes.
    """
    model = model_factory()
    name = "ATC_ACCEL_R_MAX"
    model.parameter_editor.current_step_parameters[name] = ArduPilotParameter(name, Par(90000), {"min": 80000})
    with (
        patch.object(frontend, "show_tooltip"),
        patch.object(frontend, "showwarning") as warning,
        patch.object(frontend, "showerror") as error,
        patch.object(frontend, "refresh_parameter_editor_table") as refresh,
    ):
        view = frontend.AutotuneAccelBackoffView(tk.Frame(tk_root), model, MagicMock(spec=BaseWindow))
        try:
            view.apply_button.invoke()
            assert model.parameter_editor.current_step_parameters[name].get_new_value() == 60000
            assert model.range_warnings
            warning.assert_called_once()
            error.assert_not_called()
            refresh.assert_called_once()
            assert view.apply_button.instate(["disabled"])
            view.apply_button.invoke()
            warning.assert_called_once()
            refresh.assert_called_once()
        finally:
            view.destroy()


@pytest.mark.parametrize("vehicle", ["ArduCopter", "ArduPlane", "Heli", "Rover"])
def test_finish_steps_import_available_limits_and_respect_vehicle_eligibility(vehicle: str) -> None:
    """
    Bundled finish steps expose supported limits even at firmware defaults.

    GIVEN: Bundled steps and old or new firmware parameter names.
    WHEN: Configuration is validated and finish-step additions are computed.
    THEN: Copter, Heli and QuadPlane qualify, with existing values preserved.
    """
    root = Path(__file__).resolve().parents[2] / "ardupilot_methodic_configurator"
    data = json.loads((root / f"configuration_steps_{vehicle}.json").read_text(encoding="utf-8"))
    jsonschema.validate(data, json.loads((root / "configuration_steps_schema.json").read_text(encoding="utf-8")))
    steps = data["steps"]
    filename = "73_autotune_finish.param" if vehicle == "Heli" else "49_autotune_finish.param"
    step = steps[filename]
    if vehicle == "Rover":
        assert "plugin" not in step
        return
    assert step["plugin"]["name"] == PLUGIN_AUTOTUNE_ACCEL_BACKOFF
    assert step["plugin"]["placement"] == "top"
    prefix = "Q_A" if vehicle == "ArduPlane" else "ATC"
    filesystem = LocalFilesystem.__new__(LocalFilesystem)
    filesystem.add_parameters = {}
    for acceleration in ("ACCEL", "ACC"):
        fc_parameters = {f"{prefix}_{acceleration}_{axis}_MAX": 9000.0 for axis in ("R", "P", "Y")}
        for frame_class in ("Quad", "Undefined"):
            variables = {
                "fc_parameters": fc_parameters,
                "vehicle_components": {"Frame": {"Specifications": {"Frame class": frame_class}}},
            }
            expected_visible = vehicle != "ArduPlane" or frame_class != "Undefined"
            assert bool(safe_evaluate(step["plugin"].get("if", "True"), variables)) == expected_visible
            filesystem.compute_add_parameters(filename, step, variables)
            added = filesystem.add_parameters.get(filename, ParDict())
            assert set(added) == (set(fc_parameters) if expected_visible else set())
            assert all(parameter.value == 9000 for parameter in added.values())
            existing = ParDict({name: Par(1234) for name in fc_parameters})
            filesystem.compute_add_parameters(filename, step, variables, existing_params=existing)
            assert not filesystem.add_parameters.get(filename)
    filesystem.compute_add_parameters(filename, step, {"fc_parameters": {}})
    assert not filesystem.add_parameters.get(filename)


@pytest.mark.parametrize("legacy_reason", [False, True])
def test_saved_weight_compensation_blocks_a_fresh_model(
    model_factory: ModelFactory, tmp_path: Path, legacy_reason: bool
) -> None:
    """
    Saved compensation must not compound after revisiting a step or restarting.

    GIVEN: Acceleration limits scaled once and saved with their change reasons.
    WHEN: A fresh model loads those saved values.
    THEN: It reports the applied state and rejects another reduction atomically.
    """
    model = model_factory()
    model.apply_backoff(2, 3)
    saved = ParDict(
        {
            name: Par(
                parameter.get_new_value(),
                parameter.change_reason_for_file.replace(" @autotune_accel_backoff", "")
                if legacy_reason
                else parameter.change_reason_for_file,
            )
            for name, parameter in model.parameter_editor.current_step_parameters.items()
        }
    )
    filename = tmp_path / "49_autotune_finish.param"
    saved.export_to_param(str(filename))
    loaded = ParDict.load_param_file_into_dict(str(filename))
    editor = cast(
        "ParameterEditor",
        SimpleNamespace(
            current_file=filename.name,
            current_step_parameters={name: ArduPilotParameter(name, value) for name, value in loaded.items()},
        ),
    )
    reopened = AutotuneAccelBackoffDataModel(editor, model.filesystem)
    before = snapshot(reopened)
    assert reopened.has_applied
    with pytest.raises(ValueError, match="already been scaled"):
        reopened.apply_backoff(2, 3)
    assert snapshot(reopened) == before
    assert editor.current_step_parameters["ATC_ACCEL_R_MAX"].get_new_value() == 60000
