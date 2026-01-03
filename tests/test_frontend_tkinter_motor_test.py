#!/usr/bin/env python3

"""
Behavior-driven tests for the motor test Tkinter frontend.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

from __future__ import annotations

from importlib import import_module
from tkinter import ttk
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any, Callable, cast  # pylint: disable=unused-import
from unittest.mock import MagicMock, patch

import pytest

import ardupilot_methodic_configurator.frontend_tkinter_motor_test as motor_test_module
from ardupilot_methodic_configurator.data_model_motor_test import (  # pylint: disable=unused-import
    MotorTestDataModel,
    MotorTestExecutionError,
    MotorTestSafetyError,
    ParameterError,
    ValidationError,
)
from ardupilot_methodic_configurator.frontend_tkinter_motor_test import (
    DelayedProgressCallback,
    MotorStatusEvent,
    MotorTestView,
    MotorTestWindow,
    _create_motor_test_view,
    argument_parser,
    main,
    register_motor_test_plugin,
)

if TYPE_CHECKING:
    from collections.abc import Generator


# pylint: disable=redefined-outer-name, too-few-public-methods, protected-access, raising-bad-type
class FakeMotorTestModel:  # pylint: disable=too-many-instance-attributes, too-many-public-methods
    """Minimal stand-in for MotorTestDataModel with controllable behavior."""

    def __init__(self) -> None:
        self.motor_count = 2
        self.motor_labels = ["A", "B"]
        self.motor_numbers = [1, 2]
        self.motor_directions = ["CW", "CCW"]
        self._test_throttle_pct = 25
        self._test_duration_s = 3.0
        self.frame_pairs = [("1", "1: Quad"), ("2", "2: Hex")]
        self.frame_types = {1: "Quad", 2: "Hex"}
        self.diagram_available = False
        self.diagram_path = "diagram.png"
        self.diagram_error = ""
        self.battery_text = ("Voltage: 12.5V", "Current: 3.2A")
        self.battery_color = "green"
        self.parameters = {"MOT_SPIN_ARM": 0.1, "MOT_SPIN_MIN": 0.2}
        self._should_warn = True
        self.refresh_returns = True
        self.raise_frame_error: Exception | None = None
        self.raise_throttle_error: Exception | None = None
        self.raise_duration_error: Exception | None = None
        self.raise_spin_arm_error: Exception | None = None
        self.raise_spin_min_error: Exception | None = None
        self.next_single_motor_error: Exception | None = None
        self.next_all_motor_error: Exception | None = None
        self.next_sequence_error: Exception | None = None
        self.next_emergency_error: Exception | None = None
        self.raise_stop_error: Exception | None = None
        self.last_frame_type_key: str | None = None
        self.single_motor_calls: list[tuple[int, int]] = []
        self.all_motor_runs = 0
        self.sequence_runs = 0
        self.emergency_runs = 0
        self.stop_calls = 0
        self.battery_issue = True

    def refresh_from_flight_controller(self) -> bool:
        return self.refresh_returns

    def get_frame_type_pairs(self) -> list[tuple[str, str]]:
        return self.frame_pairs

    def get_current_frame_selection_key(self) -> str:
        return "1"

    def get_current_frame_class_types(self) -> dict[int, str]:
        return self.frame_types

    def motor_diagram_exists(self) -> bool:
        return self.diagram_available

    def get_motor_diagram_path(self) -> tuple[str, str]:
        return self.diagram_path, self.diagram_error

    def get_battery_display_text(self) -> tuple[str, str]:
        return self.battery_text

    def get_battery_status_color(self) -> str:
        return self.battery_color

    def update_frame_type_by_key(self, key: str, *_callbacks, **_kwargs) -> None:
        if self.raise_frame_error:
            error = self.raise_frame_error
            self.raise_frame_error = None
            raise error
        self.last_frame_type_key = key

    def get_test_throttle_pct(self) -> int:
        return int(self._test_throttle_pct)

    def set_test_throttle_pct(self, throttle_pct: int) -> None:
        if self.raise_throttle_error:
            error = self.raise_throttle_error
            self.raise_throttle_error = None
            raise error
        self._test_throttle_pct = throttle_pct

    def get_test_duration_s(self) -> float:
        return float(self._test_duration_s)

    def set_test_duration_s(self, duration: float) -> None:
        if self.raise_duration_error:
            error = self.raise_duration_error
            self.raise_duration_error = None
            raise error
        self._test_duration_s = duration

    def get_parameter(self, name: str) -> float | None:
        return self.parameters.get(name)

    def set_motor_spin_arm_value(self, value: float, *_args) -> None:
        if self.raise_spin_arm_error:
            error = self.raise_spin_arm_error
            self.raise_spin_arm_error = None
            raise error
        self.parameters["MOT_SPIN_ARM"] = value

    def set_motor_spin_min_value(self, value: float) -> None:
        if self.raise_spin_min_error:
            error = self.raise_spin_min_error
            self.raise_spin_min_error = None
            raise error
        self.parameters["MOT_SPIN_MIN"] = value

    def should_show_first_test_warning(self) -> bool:
        return self._should_warn

    def acknowledge_first_test_warning(self) -> None:
        self._should_warn = False

    def get_safety_warning_message(self) -> str:
        return "Proceed with caution"

    def is_battery_related_safety_issue(self, reason: str) -> bool:
        return self.battery_issue and "voltage" in reason.lower()

    def run_single_motor_test(
        self,
        test_sequence_nr: int,
        motor_output_nr: int,
        status_callback: Callable[[int, MotorStatusEvent], None] | None = None,
    ) -> None:
        if self.next_single_motor_error:
            error = self.next_single_motor_error
            self.next_single_motor_error = None
            raise error
        self.single_motor_calls.append((test_sequence_nr, motor_output_nr))
        if status_callback:
            status_callback(motor_output_nr, MotorStatusEvent.COMMAND_SENT)

    def run_all_motors_test(
        self,
        status_callback: Callable[[int, MotorStatusEvent], None] | None = None,
    ) -> None:
        if self.next_all_motor_error:
            error = self.next_all_motor_error
            self.next_all_motor_error = None
            raise error
        self.all_motor_runs += 1
        if status_callback:
            for motor_number in range(1, self.motor_count + 1):
                status_callback(motor_number, MotorStatusEvent.COMMAND_SENT)

    def run_sequential_motor_test(
        self,
        status_callback: Callable[[int, MotorStatusEvent], None] | None = None,
    ) -> None:
        if self.next_sequence_error:
            error = self.next_sequence_error
            self.next_sequence_error = None
            raise error
        self.sequence_runs += 1
        if status_callback:
            for motor_number in range(1, self.motor_count + 1):
                status_callback(motor_number, MotorStatusEvent.COMMAND_SENT)

    def emergency_stop_motors(
        self,
        status_callback: Callable[[int, MotorStatusEvent], None] | None = None,
    ) -> None:
        if self.next_emergency_error:
            error = self.next_emergency_error
            self.next_emergency_error = None
            raise error
        self.emergency_runs += 1
        if status_callback:
            for motor_number in range(1, self.motor_count + 1):
                status_callback(motor_number, MotorStatusEvent.STOP_SENT)

    def stop_all_motors(self) -> None:
        if self.raise_stop_error:
            error = self.raise_stop_error
            self.raise_stop_error = None
            raise error
        self.stop_calls += 1

    def get_battery_safety_message(self, reason: str) -> str:
        return f"Unsafe battery: {reason}"

    def get_current_frame_selection_text(self) -> str:
        return "Quad"

    def test_order(self, motor_number: int) -> int:
        return motor_number - 1


class DummyBaseWindow:
    """Lightweight base window replacement for tests."""

    def __init__(self, root) -> None:
        self.root = root

    def put_image_in_label(self, parent, filepath: str, image_height: int, fallback_text: str) -> ttk.Label:
        label = ttk.Label(parent, text=fallback_text)
        cast("Any", label).image = f"image::{filepath}::{image_height}"
        return label

    @staticmethod
    def calculate_scaled_image_size(value: int) -> int:
        return value


@pytest.fixture
def fake_model() -> FakeMotorTestModel:
    return FakeMotorTestModel()


@pytest.fixture
def dummy_base_window(tk_root) -> DummyBaseWindow:
    return DummyBaseWindow(tk_root)


@pytest.fixture(autouse=True)
def dialog_spies(mocker) -> SimpleNamespace:
    """Prevent blocking GUI dialogs during tests and expose spies."""
    return SimpleNamespace(
        showerror=mocker.patch.object(motor_test_module, "showerror"),
        showwarning=mocker.patch.object(motor_test_module, "showwarning"),
        askyesno=mocker.patch.object(motor_test_module, "askyesno", return_value=True),
        askfloat=mocker.patch.object(motor_test_module, "askfloat", return_value=None),
    )


@pytest.fixture
def motor_view(
    tk_root,
    fake_model,
    dummy_base_window,
    mocker,
) -> Generator[MotorTestView, None, None]:
    parent = ttk.Frame(tk_root)
    view = MotorTestView(parent, fake_model, dummy_base_window)
    mocker.patch.object(parent, "after")
    mocker.patch.object(tk_root, "after")
    yield view
    parent.destroy()


class TestDelayedProgressCallback:
    """Exercises the delayed progress helper used by long-running operations."""

    def test_callback_triggers_after_delay(self) -> None:
        """
        Delayed callbacks notify observers when time threshold is met.

        GIVEN: A wrapped callback with zero-second delay
        WHEN: The callback is invoked
        THEN: The original callback receives the progress values immediately
        """
        recorded: list[tuple[int, int]] = []

        def recorder(current: int, total: int) -> None:
            recorded.append((current, total))

        delayed = DelayedProgressCallback(recorder, delay_seconds=0.0)
        delayed(1, 5)

        assert recorded == [(1, 5)]


class TestMotorTestView:
    """Covers the Tkinter view widget behavior for the motor test UI."""

    def test_initialization_populates_widgets(self, motor_view: MotorTestView, fake_model: FakeMotorTestModel) -> None:
        """
        The view builds the UI using the model-provided configuration.

        GIVEN: A fake data model with two motors
        WHEN: MotorTestView is instantiated
        THEN: Motor buttons and controls reflect the model state
        """
        assert len(motor_view.motor_buttons) == fake_model.motor_count
        assert motor_view.throttle_spinbox.get() == str(fake_model.get_test_throttle_pct())
        assert motor_view.duration_spinbox.get() == str(fake_model.get_test_duration_s())

    def test_user_adjusts_throttle_and_duration_values(
        self,
        motor_view: MotorTestView,
        fake_model: FakeMotorTestModel,
        dialog_spies: SimpleNamespace,
        mocker,
    ) -> None:
        """
        User edits throttle and duration inputs while recovering from invalid entries.

        GIVEN: The operator tunes the timing and throttle for a test
        WHEN: They enter valid numbers, typos, and values rejected by the model
        THEN: The view stores valid data, reports errors, and syncs with backend changes
        """
        motor_view.throttle_spinbox.delete(0, "end")
        motor_view.throttle_spinbox.insert(0, "45")
        motor_view._on_throttle_change()
        assert fake_model.get_test_throttle_pct() == 45

        dialog_spies.showerror.reset_mock()
        motor_view.throttle_spinbox.delete(0, "end")
        motor_view.throttle_spinbox.insert(0, "oops")
        motor_view._on_throttle_change()
        dialog_spies.showerror.assert_called_once()

        dialog_spies.showerror.reset_mock()
        fake_model.raise_throttle_error = ValidationError("bad throttle")
        motor_view.throttle_spinbox.delete(0, "end")
        motor_view.throttle_spinbox.insert(0, "55")
        motor_view._on_throttle_change()
        dialog_spies.showerror.assert_called_once()

        dialog_spies.showerror.reset_mock()
        motor_view.duration_spinbox.delete(0, "end")
        motor_view.duration_spinbox.insert(0, "6")
        motor_view._on_duration_change()
        assert fake_model.get_test_duration_s() == 6

        motor_view.duration_spinbox.delete(0, "end")
        motor_view.duration_spinbox.insert(0, "oops")
        motor_view._on_duration_change()
        dialog_spies.showerror.assert_called_once()

        dialog_spies.showerror.reset_mock()
        fake_model.raise_duration_error = ValidationError("bad duration")
        motor_view.duration_spinbox.delete(0, "end")
        motor_view.duration_spinbox.insert(0, "7")
        motor_view._on_duration_change()
        dialog_spies.showerror.assert_called_once()

        mocker.patch.object(motor_view.throttle_spinbox, "focus_get", return_value=None)
        mocker.patch.object(motor_view.duration_spinbox, "focus_get", return_value=None)
        fake_model._test_throttle_pct = 60
        fake_model._test_duration_s = 8
        motor_view._update_spinbox_values()
        assert motor_view.throttle_spinbox.get() == "60"
        assert float(motor_view.duration_spinbox.get()) == 8

        with patch.object(fake_model, "get_test_duration_s", side_effect=KeyError("duration")):
            motor_view._update_spinbox_values()

    def test_user_sets_spin_parameters_with_validation(
        self,
        motor_view: MotorTestView,
        fake_model: FakeMotorTestModel,
        dialog_spies: SimpleNamespace,
        mocker,
    ) -> None:
        """
        User edits spin-arm and spin-min values, seeing confirmation and validation feedback.

        GIVEN: Prompted dialogs for spin parameters
        WHEN: The operator cancels, accepts, and triggers validation failures
        THEN: Values persist for valid input and dialogs summarize errors
        """
        dialog_spies.askfloat.return_value = None
        motor_view._set_motor_spin_arm()

        progress_stub = SimpleNamespace(update_progress_bar=lambda *_a: None, destroy=lambda: None)
        mocker.patch(
            "ardupilot_methodic_configurator.frontend_tkinter_motor_test.ProgressWindow",
            return_value=progress_stub,
        )

        dialog_spies.askfloat.return_value = 0.2
        motor_view._set_motor_spin_arm()
        assert fake_model.parameters["MOT_SPIN_ARM"] == 0.2

        dialog_spies.showerror.reset_mock()
        dialog_spies.askfloat.return_value = 0.25
        fake_model.raise_spin_arm_error = ParameterError("spin arm invalid")
        motor_view._set_motor_spin_arm()
        dialog_spies.showerror.assert_called_once()

        dialog_spies.askfloat.return_value = 0.35
        motor_view._set_motor_spin_min()
        assert fake_model.parameters["MOT_SPIN_MIN"] == 0.35

        dialog_spies.showerror.reset_mock()
        dialog_spies.askfloat.return_value = 0.4
        fake_model.raise_spin_min_error = ParameterError("spin min invalid")
        motor_view._set_motor_spin_min()
        dialog_spies.showerror.assert_called_once()

    def test_on_frame_type_change_success_and_error(
        self, motor_view: MotorTestView, fake_model: FakeMotorTestModel, mocker
    ) -> None:
        """
        Frame type changes upload parameters or surface validation errors.

        GIVEN: A selected frame type key
        WHEN: The change succeeds and later raises a validation error
        THEN: The model receives the key and UI displays an error when needed
        """
        motor_view.frame_type_combobox.current(0)
        progress_stub = SimpleNamespace(update_progress_bar=lambda *_a: None, destroy=lambda: None)
        mocker.patch(
            "ardupilot_methodic_configurator.frontend_tkinter_motor_test.ProgressWindow",
            side_effect=[progress_stub, progress_stub, progress_stub, progress_stub],
        )
        motor_view._on_frame_type_change(object())
        assert fake_model.last_frame_type_key == "1"

        fake_model.raise_frame_error = ValidationError("invalid selection")
        motor_view._on_frame_type_change(object())

    def test_throttle_change_paths(
        self, motor_view: MotorTestView, fake_model: FakeMotorTestModel, dialog_spies: SimpleNamespace
    ) -> None:
        """
        Throttle changes accept valid input and handle invalid entries.

        GIVEN: Valid, non-numeric, and model-invalid throttle submissions
        WHEN: The user edits the throttle spinbox
        THEN: The model updates for valid data and dialogs show for errors
        """
        motor_view.throttle_spinbox.delete(0, "end")
        motor_view.throttle_spinbox.insert(0, "40")
        motor_view._on_throttle_change()
        assert fake_model.get_test_throttle_pct() == 40

        motor_view.throttle_spinbox.delete(0, "end")
        motor_view.throttle_spinbox.insert(0, "abc")
        motor_view._on_throttle_change()
        assert dialog_spies.showerror.called

        fake_model.raise_throttle_error = ValidationError("bad")
        motor_view.throttle_spinbox.delete(0, "end")
        motor_view.throttle_spinbox.insert(0, "50")
        motor_view._on_throttle_change()

    def test_duration_change_paths(
        self, motor_view: MotorTestView, fake_model: FakeMotorTestModel, dialog_spies: SimpleNamespace
    ) -> None:
        """
        Duration changes follow the same validation flow as throttle changes.

        GIVEN: Valid, non-numeric, and model-invalid durations
        WHEN: The user edits the duration spinbox
        THEN: The model updates or displays appropriate error dialogs
        """
        motor_view.duration_spinbox.delete(0, "end")
        motor_view.duration_spinbox.insert(0, "5")
        motor_view._on_duration_change()
        assert fake_model.get_test_duration_s() == 5

        motor_view.duration_spinbox.delete(0, "end")
        motor_view.duration_spinbox.insert(0, "oops")
        motor_view._on_duration_change()
        assert dialog_spies.showerror.called

        fake_model.raise_duration_error = ValidationError("bad")
        motor_view.duration_spinbox.delete(0, "end")
        motor_view.duration_spinbox.insert(0, "7")
        motor_view._on_duration_change()

    def test_user_refreshes_layout_and_diagram_feedback(
        self, motor_view: MotorTestView, fake_model: FakeMotorTestModel, mocker
    ) -> None:
        """
        User refreshes the view and sees layout plus diagram feedback update together.

        GIVEN: Changing motor counts and diagram availability
        WHEN: The operator refreshes the panel
        THEN: The motor grid rebuilds and diagram label reflects the current state
        """
        # Prevent the periodic scheduler from re-queuing follow-up updates.
        mocker.patch.object(motor_view.parent, "after")
        mocker.patch.object(motor_view.throttle_spinbox, "focus_get", return_value=None)
        mocker.patch.object(motor_view.duration_spinbox, "focus_get", return_value=None)

        # Layout rebuild when the motor count changes.
        fake_model.motor_count = 1
        fake_model.diagram_available = True
        fake_model.diagram_path = "diagram.png"
        diagram_loader = mocker.patch.object(
            motor_view,
            "_load_png_diagram",
            side_effect=lambda _path: motor_view.diagram_label.configure(text=""),
        )

        motor_view._diagram_needs_update = True
        motor_view._update_view()
        assert len(motor_view.motor_buttons) == 1
        diagram_loader.assert_called_once_with("diagram.png")

        # Non-PNG paths fall back to descriptive text.
        fake_model.diagram_path = "diagram.svg"
        fake_model.diagram_error = "Unsupported diagram format"
        motor_view._diagrams_path = ""
        motor_view._diagram_needs_update = True
        motor_view._update_view()
        assert "diagram" in motor_view.diagram_label.cget("text").lower()
        assert diagram_loader.call_count == 1

        # Unavailable diagrams show the standard notice.
        fake_model.diagram_available = False
        motor_view._diagram_needs_update = True
        motor_view._update_view()
        assert "not available" in motor_view.diagram_label.cget("text").lower()

    @pytest.mark.parametrize(
        ("trigger_exception", "expected_call"),
        [
            (MotorTestSafetyError("voltage low"), "showwarning"),
            (ValidationError("bad param"), "showerror"),
            (MotorTestExecutionError("fail"), "showerror"),
            (RuntimeError("unexpected"), "showerror"),
        ],
    )
    def test_test_motor_exceptions(  # pylint: disable=too-many-arguments, too-many-positional-arguments
        self,
        motor_view: MotorTestView,
        fake_model: FakeMotorTestModel,
        dialog_spies: SimpleNamespace,
        trigger_exception: Exception,
        expected_call: str,
    ) -> None:
        """
        Single-motor tests surface detailed error dialogs for each failure mode.

        GIVEN: A prepared view with acknowledged safety prompt
        WHEN: The data model raises different exceptions
        THEN: The view highlights the failure and shows the matching dialog
        """
        fake_model._should_warn = False
        fake_model.next_single_motor_error = trigger_exception
        motor_view._test_motor(0, 1)
        assert getattr(dialog_spies, expected_call).called

    def test_test_motor_success_flow(self, motor_view: MotorTestView, fake_model: FakeMotorTestModel) -> None:
        """
        Successful motor tests update the status labels and reset readiness.

        GIVEN: The first-test confirmation already acknowledged
        WHEN: A motor test runs without exceptions
        THEN: The status label reflects the sent command
        """
        fake_model._should_warn = False
        motor_view._test_motor(0, 1)
        assert fake_model.single_motor_calls == [(0, 1)]

    @pytest.mark.parametrize(
        "attr",
        ["next_all_motor_error", "next_sequence_error"],
    )
    def test_batch_motor_tests_handle_exceptions(
        self,
        motor_view: MotorTestView,
        fake_model: FakeMotorTestModel,
        dialog_spies: SimpleNamespace,
        attr: str,
    ) -> None:
        """
        Batch test buttons surface validation, safety, execution, and generic errors.

        GIVEN: A batch test invocation
        WHEN: The underlying model raises exceptions
        THEN: The user sees the relevant warning dialog
        """
        fake_model._should_warn = False
        setattr(fake_model, attr, MotorTestSafetyError("issue"))
        if attr == "next_all_motor_error":
            motor_view._test_all_motors()
        else:
            motor_view._test_motors_in_sequence()
        assert dialog_spies.showwarning.called

    def test_stop_all_motors_and_emergency_alias(
        self,
        motor_view: MotorTestView,
        fake_model: FakeMotorTestModel,
        dialog_spies: SimpleNamespace,
    ) -> None:
        """
        Emergency stop commands propagate success and error states.

        GIVEN: A stop command invocation
        WHEN: The model succeeds, raises MotorTestExecutionError, and raises RuntimeError
        THEN: The dialogs reflect the outcome and the alias covers the same path
        """
        motor_view._stop_all_motors()
        fake_model.next_emergency_error = MotorTestExecutionError("bad")
        motor_view._stop_all_motors()
        assert dialog_spies.showerror.called

        fake_model.next_emergency_error = RuntimeError("boom")
        motor_view._stop_all_motors()
        motor_view._emergency_stop()

    def test_handle_status_events_and_ready_reset(
        self,
        motor_view: MotorTestView,
        fake_model: FakeMotorTestModel,  # pylint: disable=unused-argument
        mocker,
    ) -> None:
        """
        Status events immediately update labels and schedule ready reset.

        GIVEN: A motor label displaying its initial status
        WHEN: Command and stop events arrive
        THEN: The UI colors and texts change accordingly
        """
        after_spy = mocker.patch.object(motor_view.root_window, "after")
        motor_view._handle_status_event(1, MotorStatusEvent.COMMAND_SENT)
        motor_view._handle_status_event(1, MotorStatusEvent.STOP_SENT)
        after_spy.assert_called()

    def test_update_and_reset_motor_status(self, motor_view: MotorTestView) -> None:
        """
        Status updates respect motor bounds and reset helper restores readiness.

        GIVEN: Multiple motor labels
        WHEN: Updates reference valid and invalid motor numbers
        THEN: Only valid labels change and reset returns them to Ready
        """
        motor_view._update_motor_status(1, "Running", "red")
        motor_view._update_motor_status(5, "Ignore", "red")
        motor_view._reset_all_motor_status()
        texts = [label.cget("text") for label in motor_view.motor_status_labels]
        assert all(text == "Ready" for text in texts)

    def test_keyboard_shortcuts_bind_actions(self, motor_view: MotorTestView, mocker) -> None:
        """
        Keyboard shortcuts map to stop and test helpers.

        GIVEN: The root window used by the view
        WHEN: Shortcuts are configured
        THEN: The expected bindings and focus calls occur
        """
        bind_spy = mocker.patch.object(motor_view.root_window, "bind")
        focus_spy = mocker.patch.object(motor_view.root_window, "focus_set")
        motor_view._setup_keyboard_shortcuts()
        assert bind_spy.call_count == 4
        focus_spy.assert_called_once()

    def test_on_activate_and_on_deactivate_paths(
        self,
        motor_view: MotorTestView,
        fake_model: FakeMotorTestModel,
        mocker,
    ) -> None:
        """
        Activation refreshes state while deactivation handles stop failures.

        GIVEN: Refresh successes and failures during activation/deactivation
        WHEN: The corresponding lifecycle hooks run
        THEN: The view updates, logs warnings, and re-raises unexpected exceptions
        """
        update_view_spy = mocker.patch.object(motor_view, "_update_view")
        fake_model.refresh_returns = False
        motor_view.on_activate()
        assert update_view_spy.called

        fake_model.raise_stop_error = MotorTestExecutionError("stop")
        motor_view.on_deactivate()

        fake_model.raise_stop_error = ParameterError("stop")
        motor_view.on_deactivate()

        fake_model.raise_stop_error = RuntimeError("boom")
        with pytest.raises(RuntimeError):
            motor_view.on_deactivate()

    def test_first_test_confirmation_flow(
        self,
        motor_view: MotorTestView,
        fake_model: FakeMotorTestModel,
        dialog_spies: SimpleNamespace,
    ) -> None:
        """
        Confirmation prompts gate the first motor command.

        GIVEN: A pending confirmation dialog
        WHEN: The user cancels and later accepts
        THEN: The helper returns False then True and acknowledgement sticks
        """
        dialog_spies.askyesno.return_value = False
        assert motor_view._ensure_first_test_confirmation() is False

        dialog_spies.askyesno.return_value = True
        assert motor_view._ensure_first_test_confirmation() is True
        assert fake_model._should_warn is False


class TestMotorTestWindow:
    """Validates the standalone window wrapper around the motor test view."""

    def test_window_initialization_and_close_flow(self, fake_model: FakeMotorTestModel, mocker) -> None:
        """
        The top-level window wires the view and propagates close events.

        GIVEN: Patched BaseWindow and view constructors
        WHEN: MotorTestWindow initializes and closes with varying stop behaviors
        THEN: Stop commands are attempted and the root is destroyed
        """
        root_mock = MagicMock()
        root_mock.after = MagicMock()
        root_mock.bind = MagicMock()

        def fake_base_init(self) -> None:
            self.root = root_mock
            self.main_frame = MagicMock()
            self.put_image_in_label = MagicMock()
            self.calculate_scaled_image_size = lambda value: value

        mocker.patch("ardupilot_methodic_configurator.frontend_tkinter_motor_test.BaseWindow.__init__", fake_base_init)
        view_mock = MagicMock()
        view_mock.model = fake_model
        mocker.patch(
            "ardupilot_methodic_configurator.frontend_tkinter_motor_test.MotorTestView",
            return_value=view_mock,
        )

        window = MotorTestWindow(cast("MotorTestDataModel", fake_model))
        fake_model.raise_stop_error = MotorTestExecutionError("expected")
        window.on_close()

        fake_model.raise_stop_error = RuntimeError("unexpected")
        window.on_close()

    def test_motor_test_window_on_close_logical_paths(
        self,
        fake_model: FakeMotorTestModel,
        mocker,
    ) -> None:
        """
        Unexpected close exceptions are logged but never re-raised.

        GIVEN: A window whose view stop call raises an arbitrary exception
        WHEN: on_close executes
        THEN: The root destroy call still executes
        """
        root_mock = MagicMock()

        def fake_base_init(self) -> None:
            self.root = root_mock
            self.main_frame = MagicMock()
            self.put_image_in_label = MagicMock()
            self.calculate_scaled_image_size = lambda value: value

        mocker.patch("ardupilot_methodic_configurator.frontend_tkinter_motor_test.BaseWindow.__init__", fake_base_init)
        view_mock = MagicMock()
        view_mock.model = fake_model
        mocker.patch.object(fake_model, "stop_all_motors", side_effect=RuntimeError("boom"))
        mocker.patch(
            "ardupilot_methodic_configurator.frontend_tkinter_motor_test.MotorTestView",
            return_value=view_mock,
        )

        window = MotorTestWindow(cast("MotorTestDataModel", fake_model))
        window.on_close()


class TestCommandLineWorkflow:
    """Verifies CLI helpers, entry points, and plugin registration hooks."""

    def test_argument_parser_wires_common_arguments(self, mocker) -> None:
        """
        Argument parser delegates to backend helpers and parses args.

        GIVEN: Patched backend adders returning the provided parser
        WHEN: argument_parser is invoked
        THEN: Each backend helper receives the parser instance
        """
        parser_mock = MagicMock()
        fc_adder = mocker.patch(
            "ardupilot_methodic_configurator.backend_flightcontroller.FlightController.add_argparse_arguments",
            side_effect=lambda parser: parser,
        )
        fs_adder = mocker.patch(
            "ardupilot_methodic_configurator.backend_filesystem.LocalFilesystem.add_argparse_arguments",
            side_effect=lambda parser: parser,
        )
        mocker.patch(
            "ardupilot_methodic_configurator.frontend_tkinter_motor_test.add_common_arguments",
            return_value=parser_mock,
        )
        parser_mock.parse_args.return_value = SimpleNamespace()

        argument_parser()
        assert fc_adder.called
        assert fs_adder.called
        fc_parser = fc_adder.call_args.args[0]
        fs_parser = fs_adder.call_args.args[0]
        assert fc_parser is fs_parser
        parser_mock.parse_args.assert_called_once_with()

    def test_main_success_and_failure_paths(self, mocker) -> None:
        """
        The standalone entry point starts the window and reports failures.

        GIVEN: Patched dependencies for ApplicationState, window, and dialogs
        WHEN: main succeeds once and fails the next time
        THEN: The window mainloop executes and failures trigger showerror
        """
        args = SimpleNamespace()
        mocker.patch(
            "ardupilot_methodic_configurator.frontend_tkinter_motor_test.argument_parser",
            return_value=args,
        )
        state = SimpleNamespace(flight_controller=MagicMock(), local_filesystem=MagicMock())
        mocker.patch(
            "ardupilot_methodic_configurator.frontend_tkinter_motor_test.ApplicationState",
            return_value=state,
        )
        mocker.patch("ardupilot_methodic_configurator.frontend_tkinter_motor_test.setup_logging")
        mocker.patch("ardupilot_methodic_configurator.frontend_tkinter_motor_test.initialize_flight_controller_and_filesystem")
        window_mock = MagicMock()
        window_mock.root = MagicMock()
        mocker.patch(
            "ardupilot_methodic_configurator.frontend_tkinter_motor_test.MotorTestWindow",
            return_value=window_mock,
        )
        mocker.patch(
            "ardupilot_methodic_configurator.frontend_tkinter_motor_test.MotorTestDataModel", return_value=MagicMock()
        )

        main()
        window_mock.root.mainloop.assert_called_once()

        mocker.patch(
            "ardupilot_methodic_configurator.frontend_tkinter_motor_test.MotorTestWindow",
            side_effect=RuntimeError("boom"),
        )
        main()
        state.flight_controller.disconnect.assert_called()

    def test_plugin_registration_and_factory_creation(
        self,
        tk_root,
        fake_model: FakeMotorTestModel,
        dummy_base_window,
    ) -> None:
        """
        Plugin registration routes through plugin_factory with the view factory.

        GIVEN: The plugin factory is replaced with a spy
        WHEN: register_motor_test_plugin executes
        THEN: The factory receives the plugin ID and creator
        """
        parent = ttk.Frame(tk_root)
        view = _create_motor_test_view(parent, fake_model, dummy_base_window)
        assert isinstance(view, MotorTestView)

        class DummyFactory:
            """Minimal stand-in for plugin_factory to capture registration calls."""

            def __init__(self) -> None:
                self.calls: list[tuple[str, Callable]] = []

            def register(self, name: str, creator: Callable) -> None:
                self.calls.append((name, creator))

        dummy_factory = DummyFactory()
        module = import_module("ardupilot_methodic_configurator.frontend_tkinter_motor_test")
        module_with_attr = cast("Any", module)
        original_factory = module_with_attr.plugin_factory
        module_with_attr.plugin_factory = dummy_factory
        try:
            register_motor_test_plugin()
            assert dummy_factory.calls
        finally:
            module_with_attr.plugin_factory = original_factory
