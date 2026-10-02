#!/usr/bin/env python3

"""
Behavior-driven tests for staging AutoTune gain back-off.

This file is part of ArduPilot Methodic Configurator.
https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2026 Amilcar do Carmo Lucas

SPDX-License-Identifier: GPL-3.0-or-later
"""

import json
from collections.abc import Callable
from math import isnan
from pathlib import Path
from types import SimpleNamespace
from typing import TYPE_CHECKING, cast
from unittest.mock import MagicMock, patch

import pytest

from ardupilot_methodic_configurator.data_model_ardupilot_parameter import ArduPilotParameter, ParameterOutOfRangeError
from ardupilot_methodic_configurator.data_model_par_dict import Par
from ardupilot_methodic_configurator.data_model_safe_evaluator import safe_evaluate
from ardupilot_methodic_configurator.frontend_tkinter_base_window import BaseWindow
from ardupilot_methodic_configurator.plugins.data_model_autotune_gain_backoff import AutotuneGainBackoffDataModel
from ardupilot_methodic_configurator.plugins.frontend_tkinter_autotune_gain_backoff import (
    AutotuneGainBackoffView,
    register_autotune_gain_backoff_plugin,
)
from ardupilot_methodic_configurator.plugins.plugin_constants import PLUGIN_AUTOTUNE_GAIN_BACKOFF
from ardupilot_methodic_configurator.plugins.plugin_factory import PluginModelContext, plugin_factory

if TYPE_CHECKING:
    from ardupilot_methodic_configurator.data_model_parameter_editor import ParameterEditor

# pylint: disable=redefined-outer-name


def parameter_snapshot(model: AutotuneGainBackoffDataModel) -> dict[str, tuple[str, str, str, bool]]:
    """Capture every staged value, FC value, reason and dirty flag, including NaN."""
    return {
        name: (
            "nan" if isnan(parameter.get_new_value()) else repr(parameter.get_new_value()),
            parameter.fc_value_as_string,
            parameter.change_reason_for_file,
            parameter.is_dirty,
        )
        for name, parameter in model.parameter_editor.current_step_parameters.items()
    }


@pytest.fixture
def model_factory() -> Callable[[str, str], AutotuneGainBackoffDataModel]:
    """Use real parameter objects and an in-memory active-step editor."""

    def create(axis: str = "roll", prefix: str = "ATC") -> AutotuneGainBackoffDataModel:
        values = {
            f"{prefix}_RAT_{name}_{term}": value
            for name in ("RLL", "PIT", "YAW")
            for term, value in (("P", 0.16), ("I", 0.08), ("D", 0.004), ("FF", 0.12), ("FLTE", 10.0))
        }
        values.update({f"{prefix}_ANG_{name}_P": 8.0 for name in ("RLL", "PIT", "YAW")})
        values["ATC_ACCEL_R_MAX"] = 25000
        values["AUTOTUNE_GMBK"] = 0.25
        parameters = {
            name: ArduPilotParameter(name, Par(value, "Existing reason"), fc_value=value) for name, value in values.items()
        }
        editor = cast(
            "ParameterEditor",
            SimpleNamespace(current_file=f"36_autotune_{axis}_results.param", current_step_parameters=parameters),
        )
        return AutotuneGainBackoffDataModel(editor)

    return create


@pytest.mark.parametrize("prefix", ["ATC", "Q_A"])
@pytest.mark.parametrize(
    ("axis", "axes", "terms"),
    [
        ("roll", ("RLL",), ("P", "I", "D")),
        ("pitch", ("PIT",), ("P", "I", "D")),
        ("yaw", ("YAW",), ("P", "I")),
        ("yawd", ("YAW",), ("P", "I", "D")),
        ("roll_pitch_retune", ("RLL", "PIT"), ("P", "I", "D")),
    ],
)
def test_user_reduces_only_gains_for_the_result_step(model_factory, prefix, axis, axes, terms) -> None:
    """
    Staged back-off respects the user workflow.

    GIVEN: Results contain tuned gains, unrelated axes, filters and acceleration.
    WHEN: The user applies 25% back-off.
    THEN: Only relevant rate P/I/D and angle P New values are reduced; FC values are untouched.
    """
    model = model_factory(axis, prefix)
    parameters = model.parameter_editor.current_step_parameters
    before = {name: parameter.get_new_value() for name, parameter in parameters.items()}
    old_value_strings = {name: parameter.value_as_string for name, parameter in parameters.items()}
    original_state = parameter_snapshot(model)
    expected = {f"{prefix}_RAT_{name}_{term}" for name in axes for term in terms}
    expected.update(f"{prefix}_ANG_{name}_P" for name in axes)

    changed = model.apply_backoff(0.25)

    assert set(changed) == expected
    assert len(changed) == len(expected)
    assert parameters.keys() == original_state.keys()
    for name, parameter in parameters.items():
        assert parameter.get_new_value() == pytest.approx(before[name] * (0.75 if name in expected else 1))
        assert float(parameter.fc_value_as_string) == before[name]
        if name in expected:
            assert parameter.is_dirty
            assert parameter.change_reason_for_file == f"Existing reason; {old_value_strings[name]} backed-off by 25%"
        else:
            assert parameter_snapshot(model)[name] == original_state[name]
    for name in axes:
        assert parameters[f"{prefix}_RAT_{name}_I"].get_new_value() / parameters[
            f"{prefix}_RAT_{name}_P"
        ].get_new_value() == pytest.approx(0.5)


@pytest.mark.parametrize("fraction", [-0.01, 0.51, float("nan"), float("inf"), -float("inf")])
def test_invalid_backoff_does_not_change_any_gain(model_factory, fraction) -> None:
    """
    Staged back-off respects the user workflow.

    GIVEN: Valid staged results.
    WHEN: A user enters a non-finite or out-of-range fraction.
    THEN: An error is reported before any parameter is changed.
    """
    model = model_factory("roll", "ATC")
    before = parameter_snapshot(model)
    with pytest.raises(ValueError, match=r"between 0\.0 and 0\.5"):
        model.apply_backoff(fraction)
    assert parameter_snapshot(model) == before


@pytest.mark.parametrize("fraction", [0.0, 0.5])
def test_user_can_apply_the_firmware_range_boundaries(model_factory, fraction) -> None:
    """
    Staged back-off respects the user workflow.

    GIVEN: A roll gain of 0.16.
    WHEN: Either end of the firmware range is entered.
    THEN: Zero is a no-op and 0.5 halves the gain.
    """
    model = model_factory("roll", "ATC")
    before = parameter_snapshot(model)
    old_value_strings = {
        name: parameter.value_as_string for name, parameter in model.parameter_editor.current_step_parameters.items()
    }
    changed = model.apply_backoff(fraction)
    assert bool(changed) == bool(fraction)
    assert model.parameter_editor.current_step_parameters["ATC_RAT_RLL_P"].get_new_value() == 0.16 * (1 - fraction)
    expected = {"ATC_ANG_RLL_P", "ATC_RAT_RLL_P", "ATC_RAT_RLL_I", "ATC_RAT_RLL_D"}
    assert set(changed) == (expected if fraction else set())
    after = parameter_snapshot(model)
    if fraction == 0:
        assert after == before
    else:
        for name, parameter in model.parameter_editor.current_step_parameters.items():
            if name in expected:
                assert parameter.get_new_value() == float(before[name][0]) * 0.5
                assert parameter.change_reason_for_file == f"Existing reason; {old_value_strings[name]} backed-off by 50%"
                assert parameter.is_dirty
                assert after[name][1] == before[name][1]
            else:
                assert after[name] == before[name]


def test_each_button_press_reduces_the_current_new_values_again(model_factory) -> None:
    """
    Staged back-off respects the user workflow.

    GIVEN: The user manually changed a staged P value.
    WHEN: They apply 25% twice.
    THEN: Reductions compound on that new value rather than the FC value.
    """
    model = model_factory("roll", "ATC")
    parameter = model.parameter_editor.current_step_parameters["ATC_RAT_RLL_P"]
    parameter.set_new_value("0.2")
    model.apply_backoff(0.25)
    model.apply_backoff(0.25)
    assert parameter.get_new_value() == pytest.approx(0.2 * 0.75**2)
    assert float(parameter.fc_value_as_string) == 0.16
    assert parameter.change_reason_for_file == ("Existing reason; 0.2 backed-off by 25%; 0.15 backed-off by 25%")


@pytest.mark.parametrize("invalid_kind", ["readonly", "forced", "negative", "nonfinite"])
def test_unacceptable_gain_prevents_partial_changes(model_factory, invalid_kind) -> None:
    """
    Staged back-off respects the user workflow.

    GIVEN: One affected gain cannot safely be reduced.
    WHEN: Back-off is applied.
    THEN: All gains retain their previous New values and reasons.
    """
    model = model_factory("roll", "ATC")
    parameters = model.parameter_editor.current_step_parameters
    parameters["ATC_RAT_RLL_P"] = ArduPilotParameter(
        "ATC_RAT_RLL_P",
        Par(-0.16 if invalid_kind == "negative" else float("nan") if invalid_kind == "nonfinite" else 0.16),
        {"min": 0.15} if invalid_kind == "range" else {"ReadOnly": invalid_kind == "readonly"},
        forced_par=Par(0.16) if invalid_kind == "forced" else None,
    )
    before = parameter_snapshot(model)
    with pytest.raises((ValueError, ParameterOutOfRangeError)):
        model.apply_backoff(0.25)
    assert parameter_snapshot(model) == before


def test_missing_and_zero_gains_are_not_added_or_changed(model_factory) -> None:
    """
    Staged back-off respects the user workflow.

    GIVEN: An incomplete result step with a zero D gain.
    WHEN: Back-off is applied.
    THEN: Missing parameters are not created and zero gains are left alone.
    """
    model = model_factory("roll", "ATC")
    parameters = model.parameter_editor.current_step_parameters
    del parameters["ATC_RAT_RLL_I"]
    parameters["ATC_RAT_RLL_D"] = ArduPilotParameter("ATC_RAT_RLL_D", Par(0.0))
    before = parameter_snapshot(model)
    changed = model.apply_backoff(0.25)
    assert "ATC_RAT_RLL_I" not in parameters
    assert "ATC_RAT_RLL_D" not in changed
    assert set(changed) == {"ATC_ANG_RLL_P", "ATC_RAT_RLL_P"}
    assert parameters.keys() == before.keys()
    assert parameter_snapshot(model)["ATC_RAT_RLL_D"] == before["ATC_RAT_RLL_D"]
    assert parameters["ATC_ANG_RLL_P"].get_new_value() == 6.0
    assert parameters["ATC_RAT_RLL_P"].get_new_value() == 0.12


def test_setup_steps_do_not_expose_any_backoff_targets(model_factory) -> None:
    """
    Staged back-off respects the user workflow.

    GIVEN: The active file is an AutoTune setup rather than a results step.
    WHEN: Back-off is requested.
    THEN: No gains are changed.
    """
    model = model_factory("roll", "ATC")
    model.parameter_editor.current_file = "35_autotune_roll_setup.param"
    before = parameter_snapshot(model)
    assert model.apply_backoff(0.25) == []
    assert parameter_snapshot(model) == before


def test_backoff_adds_a_reason_when_the_original_reason_is_empty(model_factory) -> None:
    """
    A new reason is recorded without an empty prefix.

    GIVEN: A gain has no existing change reason.
    WHEN: The user applies a 10% reduction.
    THEN: The value and exact reason describe the requested reduction.
    """
    model = model_factory("roll", "ATC")
    parameter = model.parameter_editor.current_step_parameters["ATC_RAT_RLL_P"]
    parameter.set_change_reason("")

    model.apply_backoff(0.1)

    assert parameter.get_new_value() == pytest.approx(0.144)
    assert parameter.change_reason_for_file == "0.16 backed-off by 10%"
    assert parameter.is_dirty
    assert float(parameter.fc_value_as_string) == 0.16


def test_manual_override_keeps_one_marker_when_backoff_is_repeated(model_factory) -> None:
    """
    Additional back-off preserves the manual override marker in the saved reason.

    GIVEN: A forced gain whose file value has a manual override and user reason.
    WHEN: The user applies two back-off reductions.
    THEN: The reason updates without duplicating the serialization marker.
    """
    model = model_factory("roll", "ATC")
    parameter = ArduPilotParameter(
        "ATC_RAT_RLL_P",
        Par(0.16, "@manual_override Keep this manual value"),
        fc_value=0.16,
        forced_par=Par(0.16, "Forced value"),
    )
    model.parameter_editor.current_step_parameters[parameter.name] = parameter

    model.apply_backoff(0.25)
    model.apply_backoff(0.25)

    assert parameter.is_manual_override
    assert parameter.change_reason == ("Keep this manual value; 0.16 backed-off by 25%; 0.12 backed-off by 25%")
    assert parameter.change_reason_for_file == (
        "@manual_override Keep this manual value; 0.16 backed-off by 25%; 0.12 backed-off by 25%"
    )
    assert parameter.change_reason_for_file.count("@manual_override") == 1


@pytest.mark.parametrize("text", ["-0.1", "0.6", "nan", "inf"])
def test_apply_button_rejects_invalid_fractions_without_refreshing_or_changing_values(tk_root, model_factory, text) -> None:
    """
    Invalid numeric input leaves the entire displayed workflow unchanged.

    GIVEN: The plugin has staged gains and existing feedback.
    WHEN: The user presses Apply with an invalid numeric fraction.
    THEN: The domain error is shown and no state or table refresh changes occur.
    """
    model = model_factory("roll", "ATC")
    before = parameter_snapshot(model)
    base_window = MagicMock(spec=BaseWindow)
    with (
        patch("ardupilot_methodic_configurator.plugins.frontend_tkinter_autotune_gain_backoff.show_tooltip"),
        patch("ardupilot_methodic_configurator.plugins.frontend_tkinter_autotune_gain_backoff.showerror") as error,
        patch(
            "ardupilot_methodic_configurator.plugins.frontend_tkinter_autotune_gain_backoff.refresh_parameter_editor_table"
        ) as refresh,
    ):
        view = AutotuneGainBackoffView(tk_root, model, base_window)
        try:
            view.status.set("Previous feedback")
            view.backoff.set(text)
            view.apply_button.invoke()

            assert parameter_snapshot(model) == before
            assert view.status.get() == "Previous feedback"
            error.assert_called_once_with(
                "Gain margin back-off", "Gain margin back-off must be a finite number between 0.0 and 0.5.", parent=view
            )
            refresh.assert_not_called()
        finally:
            view.destroy()


def test_apply_button_shows_translated_message_for_non_numeric_input(tk_root, model_factory) -> None:
    """Nonnumeric text gets stable guidance instead of a Python conversion error."""
    model = model_factory("roll", "ATC")
    before = parameter_snapshot(model)
    base_window = MagicMock(spec=BaseWindow)
    with (
        patch("ardupilot_methodic_configurator.plugins.frontend_tkinter_autotune_gain_backoff.show_tooltip"),
        patch("ardupilot_methodic_configurator.plugins.frontend_tkinter_autotune_gain_backoff.showerror") as error,
        patch(
            "ardupilot_methodic_configurator.plugins.frontend_tkinter_autotune_gain_backoff.refresh_parameter_editor_table"
        ) as refresh,
    ):
        view = AutotuneGainBackoffView(tk_root, model, base_window)
        try:
            view.backoff.set("not a number")
            view.apply_button.invoke()

            error.assert_called_once_with("Gain margin back-off", "Enter a number between 0.0 and 0.5.", parent=view)
            assert parameter_snapshot(model) == before
            refresh.assert_not_called()
        finally:
            view.destroy()


@pytest.mark.parametrize(
    ("initial_value", "metadata", "expected_message"),
    [
        (
            30.04033,
            {"max": 12.0},
            "The value for ATC_ANG_RLL_P (22.5302475) should be smaller than 12.0\n",
        ),
        (
            4.0,
            {"min": 4.0},
            "The value for ATC_ANG_RLL_P (3.0) should be greater than 4.0\n",
        ),
    ],
)
def test_apply_button_shows_range_warning_without_callback_traceback(  # pylint: disable=too-many-locals
    tk_root, model_factory, initial_value, metadata, expected_message
) -> None:
    """
    Metadata range violations are presented as warnings, not callback failures.

    GIVEN: An affected angle gain would remain above its maximum or fall below its minimum.
    WHEN: The user presses Apply back-off.
    THEN: All affected New values change, the table refreshes and a warning replaces the traceback.
    """
    model = model_factory("roll", "ATC")
    model.parameter_editor.current_step_parameters["ATC_ANG_RLL_P"] = ArduPilotParameter(
        "ATC_ANG_RLL_P", Par(initial_value, "Existing reason"), metadata, fc_value=initial_value
    )
    before = parameter_snapshot(model)
    base_window = MagicMock(spec=BaseWindow)
    with (
        patch("ardupilot_methodic_configurator.plugins.frontend_tkinter_autotune_gain_backoff.show_tooltip"),
        patch("ardupilot_methodic_configurator.plugins.frontend_tkinter_autotune_gain_backoff.showwarning") as warning,
        patch("ardupilot_methodic_configurator.plugins.frontend_tkinter_autotune_gain_backoff.showerror") as error,
        patch(
            "ardupilot_methodic_configurator.plugins.frontend_tkinter_autotune_gain_backoff.refresh_parameter_editor_table"
        ) as refresh,
        patch.object(tk_root, "report_callback_exception") as callback_exception,
    ):
        view = AutotuneGainBackoffView(tk_root, model, base_window)
        try:
            view.status.set("Previous feedback")
            refresh.side_effect = lambda *_: warning.assert_called_once()
            view.apply_button.invoke()

            warning.assert_called_once_with(
                "Gain margin back-off",
                "The New values were changed, but some gains are outside their recommended ranges:\n\n" + expected_message,
                parent=view,
            )
            callback_exception.assert_not_called()
            error.assert_not_called()
            refresh.assert_called_once_with(base_window)
            changed_names = {"ATC_ANG_RLL_P", "ATC_RAT_RLL_P", "ATC_RAT_RLL_I", "ATC_RAT_RLL_D"}
            after = parameter_snapshot(model)
            for name, parameter in model.parameter_editor.current_step_parameters.items():
                if name in changed_names:
                    assert parameter.get_new_value() == pytest.approx(float(before[name][0]) * 0.75)
                    assert parameter.is_dirty
                    assert parameter.change_reason_for_file == (
                        f"Existing reason; {format(float(before[name][0]), '.6f').rstrip('0').rstrip('.')} backed-off by 25%"
                    )
                    assert after[name][1] == before[name][1]
                else:
                    assert after[name] == before[name]
            assert view.status.get() == "Updated gains: ATC_ANG_RLL_P, ATC_RAT_RLL_D, ATC_RAT_RLL_I, ATC_RAT_RLL_P"
            assert model.range_warnings == [expected_message]
            model.apply_backoff(0.0)
            assert model.range_warnings == []
        finally:
            view.destroy()


def test_bundled_autotune_results_steps_only_enable_the_plugin_for_supported_vehicles() -> None:
    """
    Staged back-off respects the user workflow.

    GIVEN: Bundled AutoTune results steps for each vehicle family.
    WHEN: Plugin visibility is evaluated for supported and unsupported frames.
    THEN: Copter, Heli and QuadPlane qualify; Rover and fixed-wing Plane do not.
    """
    root = Path(__file__).resolve().parents[2] / "ardupilot_methodic_configurator"
    for vehicle in ("ArduCopter", "ArduPlane", "Heli", "Rover"):
        steps = json.loads((root / f"configuration_steps_{vehicle}.json").read_text(encoding="utf-8"))["steps"]
        results = {name: step for name, step in steps.items() if "_autotune_" in name and name.endswith("_results.param")}
        assert len(results) == (9 if vehicle == "Heli" else 5)
        for name, step in results.items():
            assert AutotuneGainBackoffDataModel.result_axes(name)
            if vehicle == "Rover":
                assert "plugin" not in step
                continue
            assert step["plugin"]["name"] == PLUGIN_AUTOTUNE_GAIN_BACKOFF
            assert step["plugin"]["placement"] == "top"
            for version, version_visible in (("4.6.3", True), ("4.7.0", False), ("4.7.1", False), ("4.8.0", False)):
                frames = ("Undefined", "Quad") if vehicle == "ArduPlane" else ("Quad",)
                for frame_class in frames:
                    variables = {
                        "vehicle_components": {
                            "Flight Controller": {"Firmware": {"Version": version}},
                            "Frame": {"Specifications": {"Frame class": frame_class}},
                        }
                    }
                    if "if" in step["plugin"]:
                        visible = bool(safe_evaluate(step["plugin"]["if"], variables))
                    else:
                        visible = True
                    expected_visible = (vehicle == "Heli" or version_visible) and (
                        vehicle != "ArduPlane" or frame_class != "Undefined"
                    )
                    assert visible is expected_visible

    heli_template_results = {
        "27_autotune_pitch_RatePD_results.param",
        "29_autotune_roll_RatePD_results.param",
        "31_autotune_roll_pitch_AngleP_results.param",
        "35_autotune_yaw_AngleP_results.param",
    }
    heli_steps = json.loads((root / "configuration_steps_Heli.json").read_text(encoding="utf-8"))["steps"]
    assert all(heli_steps[name]["plugin"]["name"] == PLUGIN_AUTOTUNE_GAIN_BACKOFF for name in heli_template_results)


def test_plugin_can_be_created_without_a_connected_flight_controller(model_factory) -> None:
    """
    Staged back-off respects the user workflow.

    GIVEN: An offline parameter editor.
    WHEN: The registered factory creates the plugin model.
    THEN: It uses the active editor without requiring a flight controller.
    """
    register_autotune_gain_backoff_plugin()
    editor = model_factory("roll", "ATC").parameter_editor
    context = PluginModelContext(MagicMock(), MagicMock(), editor)
    model = plugin_factory.create_model(PLUGIN_AUTOTUNE_GAIN_BACKOFF, context)
    assert isinstance(model, AutotuneGainBackoffDataModel)
    assert model.parameter_editor is editor
    assert not plugin_factory.requires_flight_controller(PLUGIN_AUTOTUNE_GAIN_BACKOFF)


def test_apply_button_stages_values_and_refreshes_the_table(tk_root, model_factory) -> None:
    """
    Staged back-off respects the user workflow.

    GIVEN: The actual plugin controls and an offline results model.
    WHEN: The Apply button is pressed twice, then invalid text is entered.
    THEN: Values compound, the table refreshes, and invalid text reports an error.
    """
    model = model_factory("roll", "ATC")
    base_window = MagicMock(spec=BaseWindow)
    with (
        patch("ardupilot_methodic_configurator.plugins.frontend_tkinter_autotune_gain_backoff.show_tooltip"),
        patch("ardupilot_methodic_configurator.plugins.frontend_tkinter_autotune_gain_backoff.showerror") as error,
        patch(
            "ardupilot_methodic_configurator.plugins.frontend_tkinter_autotune_gain_backoff.refresh_parameter_editor_table"
        ) as refresh,
    ):
        register_autotune_gain_backoff_plugin()
        view = plugin_factory.create(PLUGIN_AUTOTUNE_GAIN_BACKOFF, tk_root, model, base_window)
        assert isinstance(view, AutotuneGainBackoffView)
        try:
            assert view.model is model
            assert view.base_window is base_window
            assert view.backoff.get() == "0.25"
            assert float(view.entry.cget("from")) == 0
            assert float(view.entry.cget("to")) == 0.5
            view.apply_button.invoke()
            view.apply_button.invoke()
            assert model.parameter_editor.current_step_parameters["ATC_RAT_RLL_P"].get_new_value() == pytest.approx(
                0.16 * 0.75**2
            )
            assert refresh.call_count == 2
            refresh.assert_called_with(base_window)
            expected_names = "ATC_ANG_RLL_P, ATC_RAT_RLL_D, ATC_RAT_RLL_I, ATC_RAT_RLL_P"
            assert view.status.get() == f"Updated gains: {expected_names}"
            error.assert_not_called()
            before_error = parameter_snapshot(model)
            previous_status = view.status.get()
            refresh.reset_mock()
            view.backoff.set("invalid")
            view.apply_button.invoke()
            error.assert_called_once_with("Gain margin back-off", "Enter a number between 0.0 and 0.5.", parent=view)
            assert parameter_snapshot(model) == before_error
            assert view.status.get() == previous_status
            refresh.assert_not_called()
            view.on_deactivate()
            view.on_activate()
            assert view.status.get() == ""
            view.backoff.set("0")
            view.apply_button.invoke()
            assert view.status.get() == "No gains changed."
            assert parameter_snapshot(model) == before_error
            refresh.assert_called_once_with(base_window)
        finally:
            view.destroy()
