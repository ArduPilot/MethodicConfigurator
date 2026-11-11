#!/usr/bin/env python3

"""
Behavior-driven tests for the motor test Tkinter frontend.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

from __future__ import annotations

import tkinter as tk
from importlib import import_module
from threading import Event as ThreadEvent
from threading import get_ident
from tkinter import Event, ttk
from types import SimpleNamespace
from typing import TYPE_CHECKING, cast
from unittest.mock import MagicMock, patch

import pytest
from pymavlink.dialects.v20 import ardupilotmega as mavlink
from telemetry_test_helpers import create_telemetry_link, feed

import ardupilot_methodic_configurator.plugins.frontend_tkinter_motor_test as motor_test_module
from ardupilot_methodic_configurator.backend_filesystem_program_settings import ProgramSettings
from ardupilot_methodic_configurator.backend_flightcontroller import FlightController
from ardupilot_methodic_configurator.backend_flightcontroller_reconnect import FlightControllerReconnect
from ardupilot_methodic_configurator.frontend_tkinter_connection_recovery import (
    ConnectionRecovery,
    RecoveryCallbacks,
    RecoveryState,
)
from ardupilot_methodic_configurator.frontend_tkinter_navigation_lock import NavigationLock
from ardupilot_methodic_configurator.frontend_tkinter_parameter_editor import ParameterEditorWindow
from ardupilot_methodic_configurator.plugins.data_model_motor_test import (
    MotorTestDataModel,
    MotorTestExecutionError,
    MotorTestSafetyError,
    ParameterError,
    ValidationError,
)
from ardupilot_methodic_configurator.plugins.frontend_tkinter_motor_test import (
    DelayedProgressCallback,
    MotorStatusEvent,
    MotorTestView,
    MotorTestWindow,
    _create_motor_test_view,
    register_motor_test_plugin,
)
from ardupilot_methodic_configurator.plugins.plugin_protocol import PluginPauseReason

if TYPE_CHECKING:
    from collections.abc import Callable, Generator
    from pathlib import Path
    from typing import Any

    from pytest_mock import MockerFixture


# pylint: disable=redefined-outer-name, too-few-public-methods, protected-access, raising-bad-type, too-many-lines


class FakeMotorTestModel:  # pylint: disable=too-many-instance-attributes, too-many-public-methods
    """Minimal stand-in for MotorTestDataModel with controllable behavior."""

    def __init__(self) -> None:
        self.flight_controller = MagicMock(spec=FlightController)
        self.flight_controller.master = None
        self.frame_class = 1
        self.frame_type = 1
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

    def is_battery_related_safety_issue(self, reason: MotorTestSafetyError) -> bool:
        return self.battery_issue and reason.battery_related

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
        self.navigation_lock = NavigationLock()

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
        showinfo=mocker.patch.object(motor_test_module, "showinfo"),
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
    motor_update_timers: dict[str, Callable[[], None]],  # noqa: ARG001 # pylint: disable=unused-argument
) -> Generator[MotorTestView, None, None]:
    parent = ttk.Frame(tk_root)
    view = MotorTestView(parent, fake_model, dummy_base_window)
    mocker.patch.object(parent, "after")
    mocker.patch.object(tk_root, "after")
    try:
        yield view
    finally:
        if view.winfo_exists():
            view.destroy()
        parent.destroy()


@pytest.fixture
def motor_update_timers(mocker: MockerFixture) -> dict[str, Callable[[], None]]:
    """Control the real motor view's update clock without entering Tk's event loop."""
    pending: dict[str, Callable[[], None]] = {}
    next_id = 0

    def schedule(_view: MotorTestView, delay: int, callback: Callable[[], None]) -> str:
        nonlocal next_id
        assert delay == 1000
        next_id += 1
        timer_id = f"motor-update-{next_id}"
        pending[timer_id] = callback
        return timer_id

    def cancel(_view: MotorTestView, timer_id: str) -> None:
        pending.pop(timer_id, None)

    mocker.patch.object(MotorTestView, "after", autospec=True, side_effect=schedule)
    mocker.patch.object(MotorTestView, "after_cancel", autospec=True, side_effect=cancel)
    return pending


@pytest.fixture
def motor_view_with_controller(
    tk_root: tk.Tk,
    dummy_base_window: DummyBaseWindow,
    mocker: MockerFixture,
    motor_update_timers: dict[str, Callable[[], None]],  # noqa: ARG001 # pylint: disable=unused-argument
) -> Generator[MotorTestView, None, None]:
    """Use the real motor model and frame definitions with an in-memory FC parameter cache."""
    fc = MagicMock(spec=FlightController)
    fc.master = object()
    fc.fc_parameters = {"FRAME_CLASS": 1.0, "FRAME_TYPE": 1.0, "BATT_MONITOR": 0.0}
    fc.is_battery_monitoring_enabled.return_value = False
    fc.get_frame_info.side_effect = lambda: (int(fc.fc_parameters["FRAME_CLASS"]), int(fc.fc_parameters["FRAME_TYPE"]))
    filesystem = MagicMock()
    filesystem.doc_dict = {}
    mocker.patch.object(
        ProgramSettings, "get_setting", side_effect={"motor_test/duration": 3.0, "motor_test/throttle_pct": 25}.get
    )
    mocker.patch.object(ProgramSettings, "motor_diagram_exists", return_value=True)
    mocker.patch.object(
        ProgramSettings,
        "motor_diagram_filepath",
        side_effect=lambda frame_class, frame_type: (f"frame-{frame_class}-{frame_type}.svg", ""),
    )
    model = MotorTestDataModel(fc, filesystem)
    parent = ttk.Frame(tk_root)
    view = MotorTestView(parent, model, dummy_base_window)
    try:
        yield view
    finally:
        view.destroy()
        parent.destroy()


@pytest.fixture
def motor_connection_recovery(motor_view_with_controller: MotorTestView) -> Generator[ConnectionRecovery, None, None]:
    """Monitor the motor view using the real editor's ownership gate and FC liveness checks."""
    view = motor_view_with_controller
    fc = cast("MagicMock", view.model.flight_controller)
    fc.master = MagicMock(message_hooks=[], portdead=False)
    fc.info = SimpleNamespace(hw_unique_id="original-fc", system_id=1, component_id=1)
    fc.comport_device = "/dev/ttyACM0"
    fc.active_baudrate = 115200
    fc.get_serial_ports.return_value = []
    editor = object.__new__(ParameterEditorWindow)
    editor.root = view.root_window
    editor.navigation_lock = view.base_window.navigation_lock
    editor._file_browser_window = None
    editor.parameter_editor_table = MagicMock(bitmask_editor_open=False)
    callbacks = RecoveryCallbacks(
        reader_busy=editor._connection_reader_busy,
        can_read=lambda: False,
        pause_receiver=MagicMock(return_value=lambda: None),
        lock_controls=MagicMock(return_value=lambda: None),
        show_status=MagicMock(),
        on_recovered=MagicMock(),
    )
    recovery = ConnectionRecovery(MagicMock(), FlightControllerReconnect(fc), callbacks)
    recovery.start()
    try:
        yield recovery
    finally:
        recovery.stop()


@pytest.mark.parametrize("reason", list(PluginPauseReason))
def test_motor_view_reuses_live_esc_table_and_cleans_up_its_receiver(
    motor_view: MotorTestView, fake_model: FakeMotorTestModel, reason: PluginPauseReason
) -> None:
    """
    Keep the embedded table in step with the motor view lifecycle.

    GIVEN motor test controls and a reporting ESC on the shared connection,
    WHEN the view pauses, resumes, hides and is destroyed,
    THEN the bottom table displays telemetry and releases its receiver and timer.
    """
    link = create_telemetry_link()
    link.master.target_system = 1
    link.master.target_component = 1
    fake_model.flight_controller.master = link.master
    telemetry = motor_view.esc_telemetry_view
    assert motor_view._content_frame.pack_slaves()[-1] is telemetry
    feed(link, mavlink.MAVLink_esc_telemetry_1_to_4_message([40] * 4, [1200] * 4, [0] * 4, [0] * 4, [100] * 4, [1] * 4))
    telemetry.after_cancel(telemetry._timer_id)
    telemetry._poll()
    assert telemetry.table.cget("displaycolumns") == ("1", "2", "3", "4")
    assert telemetry.table.item("1", "values")[:4] == ("12.00",) * 4
    assert len(link.master.message_hooks) == 1

    timer = telemetry._timer_id
    motor_view.on_suspend(reason)
    assert timer not in telemetry.tk.call("after", "info")
    assert telemetry._timer_id is None
    assert not link.master.message_hooks
    assert not telemetry.table.cget("displaycolumns")
    assert fake_model.stop_calls == (1 if reason is PluginPauseReason.EXCLUSIVE_OPERATION else 0)
    telemetry._poll()
    assert telemetry._timer_id is None

    motor_view.on_resume()
    timer = telemetry._timer_id
    motor_view.on_activate()
    assert telemetry._timer_id == timer
    motor_view.on_deactivate()
    assert telemetry._timer_id is None
    motor_view.on_activate()
    telemetry.after_cancel(telemetry._timer_id)
    telemetry._poll()
    assert len(link.master.message_hooks) == 1
    timer = telemetry._timer_id
    motor_view.destroy()
    assert timer not in telemetry.tk.call("after", "info")
    assert not link.master.message_hooks


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


class TestMotorTestView:  # pylint: disable=too-many-public-methods
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
            "ardupilot_methodic_configurator.plugins.frontend_tkinter_motor_test.ProgressWindow",
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
            "ardupilot_methodic_configurator.plugins.frontend_tkinter_motor_test.ProgressWindow",
            side_effect=[progress_stub, progress_stub, progress_stub, progress_stub],
        )
        motor_view._on_frame_type_change(object())
        assert fake_model.last_frame_type_key == "1"

        fake_model.raise_frame_error = ValidationError("invalid selection")
        motor_view._on_frame_type_change(object())

    def test_spin_arm_update_holds_navigation_lock_during_progress_window_creation(
        self,
        motor_view: MotorTestView,
        fake_model: FakeMotorTestModel,
        dummy_base_window: DummyBaseWindow,
        dialog_spies: SimpleNamespace,
        mocker: MockerFixture,
    ) -> None:
        """
        Keep recovery blocked throughout the spin-arm update.

        GIVEN: An accepted spin-arm value
        WHEN: The progress window is created, the value is updated, and the window is destroyed
        THEN: Navigation stays locked until cleanup completes
        """
        lock_states: list[bool] = []

        def destroy_progress_window() -> None:
            lock_states.append(dummy_base_window.navigation_lock.locked)

        progress_stub = SimpleNamespace(update_progress_bar=lambda *_a: None, destroy=destroy_progress_window)

        def create_progress_window(*_args: object, **_kwargs: object) -> SimpleNamespace:
            lock_states.append(dummy_base_window.navigation_lock.locked)
            return progress_stub

        mocker.patch(
            "ardupilot_methodic_configurator.plugins.frontend_tkinter_motor_test.ProgressWindow",
            side_effect=create_progress_window,
        )
        mocker.patch.object(
            fake_model,
            "set_motor_spin_arm_value",
            side_effect=lambda *_args: lock_states.append(dummy_base_window.navigation_lock.locked),
        )
        dialog_spies.askfloat.return_value = 0.2

        motor_view._set_motor_spin_arm()

        assert lock_states == [True, True, True]
        assert not dummy_base_window.navigation_lock.locked

    @pytest.mark.parametrize("failure_stage", ["construction", "update", "destruction"])
    def test_spin_arm_update_releases_navigation_lock_after_unexpected_failure(  # pylint: disable=too-many-arguments,too-many-positional-arguments
        self,
        failure_stage: str,
        motor_view: MotorTestView,
        fake_model: FakeMotorTestModel,
        dummy_base_window: DummyBaseWindow,
        dialog_spies: SimpleNamespace,
        mocker: MockerFixture,
    ) -> None:
        """
        Restore navigation even when the spin-arm workflow raises an unexpected error.

        GIVEN: A failure in progress-window construction, parameter updating, or window destruction
        WHEN: The operator accepts a spin-arm value
        THEN: Cleanup runs while locked, navigation is released, and the original error propagates
        """
        error = RuntimeError(f"spin-arm {failure_stage} failed")
        lock_states: list[bool] = []
        progress_window = MagicMock()

        def create_progress_window(*_args: object, **_kwargs: object) -> MagicMock:
            lock_states.append(dummy_base_window.navigation_lock.locked)
            if failure_stage == "construction":
                raise error
            return progress_window

        def destroy_progress_window() -> None:
            lock_states.append(dummy_base_window.navigation_lock.locked)
            if failure_stage == "destruction":
                raise error

        mocker.patch.object(motor_test_module, "ProgressWindow", side_effect=create_progress_window)
        progress_window.destroy.side_effect = destroy_progress_window
        if failure_stage == "update":
            fake_model.raise_spin_arm_error = error
        dialog_spies.askfloat.return_value = 0.2

        with pytest.raises(RuntimeError) as raised:
            motor_view._set_motor_spin_arm()

        assert raised.value is error
        assert lock_states == ([True] if failure_stage == "construction" else [True, True])
        assert not dummy_base_window.navigation_lock.locked
        if failure_stage == "construction":
            progress_window.destroy.assert_not_called()
        else:
            progress_window.destroy.assert_called_once_with()
        assert fake_model.parameters["MOT_SPIN_ARM"] == (0.2 if failure_stage == "destruction" else 0.1)
        dialog_spies.showerror.assert_not_called()

    @pytest.mark.parametrize("handler", ["frame", "spin_arm"])
    def test_progress_window_is_destroyed_when_parameter_update_fails(
        self,
        handler: str,
        motor_view: MotorTestView,
        fake_model: FakeMotorTestModel,
        dialog_spies: SimpleNamespace,
        mocker,
    ) -> None:
        """Failed parameter updates must not leave their progress window allocated."""
        progress_window = MagicMock()
        mocker.patch(
            "ardupilot_methodic_configurator.plugins.frontend_tkinter_motor_test.ProgressWindow",
            return_value=progress_window,
        )

        if handler == "frame":
            motor_view.frame_type_combobox.current(0)
            fake_model.raise_frame_error = ParameterError("frame update failed")
            motor_view._on_frame_type_change(object())
        else:
            dialog_spies.askfloat.return_value = 0.2
            fake_model.raise_spin_arm_error = ParameterError("spin-arm update failed")
            motor_view._set_motor_spin_arm()

        progress_window.destroy.assert_called_once_with()
        assert not motor_view.base_window.navigation_lock.locked

    @pytest.mark.parametrize("handler", ["frame", "spin_arm"])
    @pytest.mark.parametrize("fails", [False, True])
    def test_sequoia_restart_yields_to_tk_without_competing_link_operations(
        self,
        motor_view: MotorTestView,
        dialog_spies: SimpleNamespace,
        mocker: MockerFixture,
        handler: str,
        fails: bool,
    ) -> None:
        """
        Restarting from motor configuration keeps progress and errors on Tk.

        GIVEN: Sequoia and a frame or spin-arm edit requiring a restart
        WHEN: The restart runs while Tk services a timer and progress updates
        THEN: Telemetry and shortcuts wait, UI updates stay on Tk, and polling resumes
        """
        ui_thread = get_ident()
        heartbeat = ThreadEvent()
        rendered: list[int] = []
        mocker.patch("tkinter.Misc.update")
        mocker.patch("tkinter.Misc.update_idletasks")
        # The general view fixture stubs after(); this integration case needs real polling.
        mocker.patch.object(
            motor_view.root_window,
            "after",
            new=tk.Misc.after.__get__(motor_view.root_window, type(motor_view.root_window)),  # pylint: disable=no-value-for-parameter
        )
        mocker.patch.object(motor_test_module, "is_macos_sequoia_or_older", return_value=True)
        mocker.patch.object(motor_test_module, "DelayedProgressCallback", side_effect=lambda callback, _delay: callback)

        def tick() -> None:
            assert motor_view._restart_active
            assert motor_view._timer_id is None
            shortcut = MagicMock()
            motor_view._handle_keyboard_shortcut(shortcut)
            shortcut.assert_not_called()
            heartbeat.set()

        def render(_window: object, current: int, _total: int) -> None:
            assert get_ident() == ui_thread
            rendered.append(current)

        def restart(_value: object, report: Callable[[int, int], None], **_kwargs: object) -> bool:
            assert get_ident() != ui_thread
            assert heartbeat.wait(2)
            report(50, 100)
            if fails:
                message = "restart failed"
                raise ParameterError(message)
            return True

        mocker.patch.object(motor_test_module, "update_flight_controller_restart_progress", side_effect=render)
        method = "update_frame_type_by_key" if handler == "frame" else "set_motor_spin_arm_value"
        mocker.patch.object(motor_view.model, method, side_effect=restart)
        motor_view.root_window.after(0, tick)
        if handler == "frame":
            motor_view.frame_type_combobox.current(0)
            motor_view._on_frame_type_change(None)
        else:
            dialog_spies.askfloat.return_value = 0.2
            motor_view._set_motor_spin_arm()

        assert rendered == [50]
        assert not motor_view._restart_active
        assert motor_view._timer_id is not None
        assert dialog_spies.showerror.call_count == int(fails)

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
            (MotorTestSafetyError("voltage low", battery_related=True), "showwarning"),
            (ValidationError("bad param"), "showerror"),
            (MotorTestExecutionError("fail"), "showerror"),
            (RuntimeError("unexpected"), "showerror"),
        ],
    )
    def test_test_motor_exceptions(
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
        THEN: The expected bindings and focus calls occur, and destruction removes the bindings
        """
        # Teardown needs the real bind method to remove scripts as well as callback commands.
        bind_spy = mocker.spy(motor_view.root_window, "bind")
        focus_spy = mocker.patch.object(motor_view.root_window, "focus_set")
        motor_view._setup_keyboard_shortcuts()
        assert {call.args[0] for call in bind_spy.call_args_list} == {"<Escape>", "<Control-s>"}
        focus_spy.assert_called_once()

        bindings = list(motor_view._keyboard_bindings)
        motor_view.destroy()
        for sequence, binding_id in bindings:
            assert binding_id not in motor_view.root_window.tk.call("bind", str(motor_view.root_window), sequence)

    def test_destroy_unbinds_keyboard_shortcuts(self, motor_view: MotorTestView) -> None:
        """Destroying the view must remove its app-wide actuator shortcuts."""
        bindings = list(motor_view._keyboard_bindings)

        assert bindings
        assert all(binding_id in motor_view.root_window.bind(sequence) for sequence, binding_id in bindings)

        motor_view.destroy()

        assert all(binding_id not in motor_view.root_window.bind(sequence) for sequence, binding_id in bindings)

    @pytest.mark.parametrize("legacy_unbind", [False, True])
    def test_destroy_preserves_preexisting_root_binding(
        self, motor_view: MotorTestView, mocker: MockerFixture, legacy_unbind: bool
    ) -> None:
        """Destroying the view preserves earlier and later shortcuts on all supported Python versions."""
        sequences = ("<Escape>", "<Control-s>", "<Control-a>", "<Control-q>")
        for sequence in sequences:
            motor_view.root_window.unbind(sequence)
        earlier_id = motor_view.root_window.bind("<Control-s>", lambda _event: "break")
        motor_view._keyboard_bindings.clear()
        motor_view._setup_keyboard_shortcuts()
        later_id = motor_view.root_window.bind("<Control-s>", lambda _event: "break", add="+")
        if legacy_unbind:
            # Reproduce Python 3.11.0-3.11.7 and 3.12.0 clearing every handler, even with a callback ID.
            mocker.patch.object(
                motor_view.root_window,
                "unbind",
                side_effect=lambda sequence, _funcid=None: motor_view.root_window.tk.call(
                    "bind", str(motor_view.root_window), sequence, ""
                ),
            )

        motor_view.destroy()

        remaining = motor_view.root_window.bind("<Control-s>")
        for binding_id in (earlier_id, later_id):
            assert binding_id in remaining
            assert motor_view.root_window.tk.call("info", "commands", binding_id)

    def test_destroy_deletes_tcl_binding_commands(self, motor_view: MotorTestView) -> None:
        """Cleanup must delete callback commands as well as binding scripts."""
        sequences = ("<Escape>", "<Control-s>", "<Control-a>", "<Control-q>")
        for sequence in sequences:
            motor_view.root_window.unbind(sequence)
        motor_view._keyboard_bindings.clear()
        motor_view._setup_keyboard_shortcuts()
        binding_ids = [binding_id for _sequence, binding_id in motor_view._keyboard_bindings]

        assert all(motor_view.root_window.tk.call("info", "commands", binding_id) for binding_id in binding_ids)

        motor_view.destroy()

        assert all(not motor_view.root_window.tk.call("info", "commands", binding_id) for binding_id in binding_ids)

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
            self.dpi_scaling_factor = 1.0

        mocker.patch("ardupilot_methodic_configurator.plugins.frontend_tkinter_motor_test.BaseWindow.__init__", fake_base_init)
        view_mock = MagicMock()
        view_mock.model = fake_model
        mocker.patch(
            "ardupilot_methodic_configurator.plugins.frontend_tkinter_motor_test.MotorTestView",
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
            self.dpi_scaling_factor = 1.0

        mocker.patch("ardupilot_methodic_configurator.plugins.frontend_tkinter_motor_test.BaseWindow.__init__", fake_base_init)
        view_mock = MagicMock()
        view_mock.model = fake_model
        mocker.patch.object(fake_model, "stop_all_motors", side_effect=RuntimeError("boom"))
        mocker.patch(
            "ardupilot_methodic_configurator.plugins.frontend_tkinter_motor_test.MotorTestView",
            return_value=view_mock,
        )

        window = MotorTestWindow(cast("MotorTestDataModel", fake_model))
        window.on_close()


class TestCommandLineWorkflow:
    """Verifies plugin registration hooks."""

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

            def register(self, name: str, creator: Callable, model_creator: Callable) -> None:
                self.calls.append((name, creator))
                assert callable(model_creator)

        dummy_factory = DummyFactory()
        module = import_module("ardupilot_methodic_configurator.plugins.frontend_tkinter_motor_test")
        module_with_attr = cast("Any", module)
        original_factory = module_with_attr.plugin_factory
        module_with_attr.plugin_factory = dummy_factory
        try:
            register_motor_test_plugin()
            assert dummy_factory.calls
        finally:
            module_with_attr.plugin_factory = original_factory


class TestMotorTestViewMotorSwapping:
    """Test the frontend GUI logic specifically for motor swapping."""

    def test_on_combobox_selected_routes_correctly(self, motor_view: MotorTestView, mocker) -> None:
        """
        Combobox selection routes the expected and detected labels to the swap logic.

        GIVEN: A combobox selection event triggered by the first combobox
        WHEN: _on_combobox_selected is called
        THEN: It looks up the correct labels and routes data to _on_motor_swapped
        """
        cb = motor_view.detected_comboboxes[0]
        cb.set("B")

        mock_event = MagicMock(spec=Event)
        mock_event.widget = cb

        swap_spy = mocker.patch.object(motor_view, "_on_motor_swapped")

        # Act
        motor_view._on_combobox_selected(mock_event)

        swap_spy.assert_called_once_with("A", "B")

    def test_on_motor_swapped_early_exit(
        self, motor_view: MotorTestView, fake_model: FakeMotorTestModel, dialog_spies: SimpleNamespace
    ) -> None:
        """
        Swapping a motor with itself exits early without prompting.

        GIVEN: A swap request where expected and detected labels are identical
        WHEN: _on_motor_swapped is called
        THEN: It clears the comboboxes and returns immediately without prompting the user
        """
        fake_model.swap_motor_functions = MagicMock()
        motor_view.detected_comboboxes[0].set("A")

        motor_view._on_motor_swapped("A", "A")

        dialog_spies.askyesno.assert_not_called()
        fake_model.swap_motor_functions.assert_not_called()
        assert motor_view.detected_comboboxes[0].get() == ""

    def test_on_motor_swapped_cancelled_by_user(
        self, motor_view: MotorTestView, fake_model: FakeMotorTestModel, dialog_spies: SimpleNamespace
    ) -> None:
        """
        Swap requests cancelled by the user reset the UI safely.

        GIVEN: A valid swap request
        WHEN: The user clicks 'No' on the confirmation dialog
        THEN: It clears the comboboxes and aborts the swap
        """
        dialog_spies.askyesno.return_value = False
        fake_model.swap_motor_functions = MagicMock()
        motor_view.detected_comboboxes[0].set("B")

        motor_view._on_motor_swapped("A", "B")

        dialog_spies.askyesno.assert_called_once()
        fake_model.swap_motor_functions.assert_not_called()
        assert motor_view.detected_comboboxes[0].get() == ""

    def test_on_motor_swapped_success(
        self, motor_view: MotorTestView, fake_model: FakeMotorTestModel, dialog_spies: SimpleNamespace, mocker
    ) -> None:
        """
        Successful swap requests apply parameters and show a success dialog.

        GIVEN: A valid swap request confirmed by the user
        WHEN: The data model successfully swaps the parameters
        THEN: A success info dialog is shown and comboboxes are cleared
        """
        dialog_spies.askyesno.return_value = True
        mock_showinfo = mocker.patch("ardupilot_methodic_configurator.plugins.frontend_tkinter_motor_test.showinfo")
        fake_model.swap_motor_functions = MagicMock()
        motor_view.detected_comboboxes[0].set("B")

        motor_view._on_motor_swapped("A", "B")

        fake_model.swap_motor_functions.assert_called_once_with("A", "B")
        mock_showinfo.assert_called_once()
        assert motor_view.detected_comboboxes[0].get() == ""

    def test_on_motor_swapped_handles_exception(
        self, motor_view: MotorTestView, fake_model: FakeMotorTestModel, dialog_spies: SimpleNamespace
    ) -> None:
        """
        Swap requests that fail at the backend show an error dialog.

        GIVEN: A valid swap request confirmed by the user
        WHEN: The data model raises an exception during the swap
        THEN: An error dialog is shown and comboboxes are cleared
        """
        dialog_spies.askyesno.return_value = True
        fake_model.swap_motor_functions = MagicMock(side_effect=ParameterError("Mock FC read error"))
        motor_view.detected_comboboxes[0].set("B")

        motor_view._on_motor_swapped("A", "B")

        fake_model.swap_motor_functions.assert_called_once_with("A", "B")
        dialog_spies.showerror.assert_called_once()

        # Verify the actual error message was passed to the UI
        assert "Mock FC read error" in dialog_spies.showerror.call_args[0][1]
        assert motor_view.detected_comboboxes[0].get() == ""


@pytest.mark.parametrize("control", ["throttle", "duration"])
@pytest.mark.parametrize("error_kind", ["conversion", "validation", "parameter"])
def test_invalid_motor_settings_restore_the_last_accepted_value_and_explain_the_failure(
    motor_view: MotorTestView, fake_model: FakeMotorTestModel, dialog_spies: SimpleNamespace, control: str, error_kind: str
) -> None:
    """
    Keep rejected motor-test input from changing the active test settings.

    GIVEN: An accepted throttle or duration setting
    WHEN: The user submits a typo or a value rejected by the model
    THEN: The original setting is restored and the dialog explains the failed input
    """
    spinbox = motor_view.throttle_spinbox if control == "throttle" else motor_view.duration_spinbox
    value = "oops" if error_kind == "conversion" else "77"
    if error_kind != "conversion":
        error = (
            ValidationError("outside the allowed range") if error_kind == "validation" else ParameterError("FC rejected it")
        )
        setattr(fake_model, f"raise_{control}_error", error)
    spinbox.delete(0, "end")
    spinbox.insert(0, value)

    if control == "throttle":
        motor_view._on_throttle_change()
    else:
        motor_view._on_duration_change()

    expected_value = "25" if control == "throttle" else "3.0"
    assert spinbox.get() == expected_value
    assert fake_model.get_test_throttle_pct() == 25
    assert fake_model.get_test_duration_s() == 3.0
    title = "Throttle value error" if control == "throttle" else "Duration value error"
    if error_kind == "conversion":
        message = (
            "Invalid throttle value entered, reset to 25%"
            if control == "throttle"
            else "Invalid duration value entered, reset to 3 seconds"
        )
    else:
        detail = "outside the allowed range" if error_kind == "validation" else "FC rejected it"
        message = f"{control.capitalize()} validation failed: {detail}"
    dialog_spies.showerror.assert_called_once_with(title, message)


@pytest.mark.parametrize("action", ["single", "all", "sequence"])
def test_declining_motor_safety_confirmation_does_not_send_any_test_command(
    motor_view: MotorTestView, fake_model: FakeMotorTestModel, dialog_spies: SimpleNamespace, action: str
) -> None:
    """
    Respect refusal of the first motor-test safety confirmation.

    GIVEN: The first-test warning has not been acknowledged
    WHEN: The user declines a single, simultaneous or sequential motor test
    THEN: No test command is sent and the warning remains pending
    """
    dialog_spies.askyesno.return_value = False

    if action == "single":
        motor_view._test_motor(0, 1)
    elif action == "all":
        motor_view._test_all_motors()
    else:
        motor_view._test_motors_in_sequence()

    assert fake_model.single_motor_calls == []
    assert fake_model.all_motor_runs == 0
    assert fake_model.sequence_runs == 0
    assert fake_model.should_show_first_test_warning()
    dialog_spies.askyesno.assert_called_once_with("Safety Confirmation", fake_model.get_safety_warning_message())


@pytest.mark.parametrize(
    ("event", "status", "color"),
    [(MotorStatusEvent.COMMAND_SENT, "Command sent", "green"), (MotorStatusEvent.STOP_SENT, "Stop sent", "red")],
)
def test_motor_status_updates_only_the_selected_motor_and_returns_to_ready_after_the_delay(
    motor_view: MotorTestView, mocker: MockerFixture, event: MotorStatusEvent, status: str, color: str
) -> None:
    """
    Show command feedback on the affected motor for the intended interval.

    GIVEN: Two ready motor labels
    WHEN: The second motor reports a test or stop command
    THEN: Only that motor changes and the scheduled callback restores Ready after two seconds
    """
    schedule = mocker.patch.object(motor_view.root_window, "after")

    motor_view._handle_status_event(2, event)

    first, second = motor_view.motor_status_labels
    assert first.cget("text") == "Ready"
    assert second.cget("text") == status
    assert str(second.cget("foreground")) == color
    schedule.assert_called_once()
    delay, callback = schedule.call_args.args
    assert delay == 2000
    callback()
    assert second.cget("text") == "Ready"
    assert str(second.cget("foreground")) == "blue"
    assert first.cget("text") == "Ready"


def test_motor_diagram_displays_a_real_png_and_reuses_the_resolved_path(
    motor_view: MotorTestView,
    fake_model: FakeMotorTestModel,
    dummy_base_window: DummyBaseWindow,
    tmp_path: Path,
    mocker: MockerFixture,
) -> None:
    """
    Display and retain the motor-layout PNG through repeated refreshes.

    GIVEN: A valid PNG layout in the selected frame configuration
    WHEN: The diagram is refreshed twice
    THEN: The image remains displayed and the resolved path is reused
    """
    # Given: Create a genuine PNG and isolate only the external image-loading boundary.
    path = tmp_path / "motor-layout.png"
    tk.PhotoImage(master=motor_view, width=2, height=2).write(str(path), format="png")
    images: list[tk.PhotoImage] = []

    def load(parent: tk.Misc, filepath: str, image_height: int, fallback_text: str) -> ttk.Label:
        assert image_height == 230
        image = tk.PhotoImage(master=parent, file=filepath)
        images.append(image)
        label = ttk.Label(parent, image=image, text=fallback_text)
        cast("Any", label).image = image
        return label

    mocker.patch.object(dummy_base_window, "put_image_in_label", side_effect=load)
    fake_model.diagram_available = True
    fake_model.diagram_path = str(path)
    resolver = mocker.patch.object(fake_model, "get_motor_diagram_path", wraps=fake_model.get_motor_diagram_path)
    # When: Display the image and refresh it again.
    motor_view._update_diagram()
    motor_view._update_diagram()
    # Then: Tk has a real image, its Python reference is retained and the path was resolved only once.
    assert tuple(str(image) for image in motor_view.tk.splitlist(motor_view.diagram_label.cget("image"))) == (str(images[-1]),)
    assert motor_view._current_diagram_image is images[-1]
    assert motor_view.diagram_label.cget("text") == ""
    resolver.assert_called_once_with()


def test_motor_diagram_shows_the_loader_fallback_when_no_image_is_available(
    motor_view: MotorTestView, dummy_base_window: DummyBaseWindow, mocker: MockerFixture
) -> None:
    """
    Show useful fallback text when a diagram loader has no image.

    GIVEN: Image loading returns a label describing the unavailable image
    WHEN: The view loads a PNG diagram
    THEN: The fallback text replaces the diagram and no stale image reference remains
    """
    # Given: A real label without an image represents the loader fallback.
    mocker.patch.object(
        dummy_base_window,
        "put_image_in_label",
        side_effect=lambda **kwargs: ttk.Label(kwargs["parent"], text="Image unavailable"),
    )
    # When: Load the diagram through the real view method.
    motor_view._load_png_diagram("missing.png")
    # Then: The fallback is visible without retaining an old diagram.
    assert motor_view.diagram_label.cget("text") == "Image unavailable"
    assert motor_view._current_diagram_image is None


@pytest.mark.parametrize("exception_type", [FileNotFoundError, OSError, ValueError, TypeError, AttributeError])
def test_motor_diagram_loading_errors_leave_the_test_controls_usable(
    motor_view: MotorTestView, dummy_base_window: DummyBaseWindow, mocker: MockerFixture, exception_type: type[Exception]
) -> None:
    """
    Recover the diagram display from expected image-loading failures.

    GIVEN: The loader raises a file, decoding or image-configuration error
    WHEN: The view attempts to load the PNG
    THEN: A useful fallback is visible and motor test controls remain enabled
    """
    # Given: Fail only at the external image-loader boundary.
    mocker.patch.object(dummy_base_window, "put_image_in_label", side_effect=exception_type("Cannot load diagram"))
    # When: Attempt to display the diagram.
    motor_view._load_png_diagram("layout.png")
    # Then: The image failure does not prevent motor configuration.
    assert motor_view.diagram_label.cget("text") == (
        "Diagram not found" if exception_type is FileNotFoundError else "Error loading diagram"
    )
    assert motor_view._current_diagram_image is None
    assert all(button.instate(["!disabled"]) for button in motor_view.motor_buttons)


@pytest.mark.parametrize("operation", ["single", "all", "sequence"])
def test_declining_the_motor_safety_warning_sends_no_motor_commands(
    motor_view: MotorTestView, fake_model: FakeMotorTestModel, dialog_spies: SimpleNamespace, operation: str
) -> None:
    """
    Respect declined propeller-removal confirmation for every motor test mode.

    GIVEN: The first motor-test safety warning has not been acknowledged
    WHEN: The operator declines confirmation
    THEN: No motor test runs and the warning remains unacknowledged
    """
    # Given: The operator declines the safety prompt.
    dialog_spies.askyesno.return_value = False
    # When: Request a single, simultaneous or sequential test.
    if operation == "single":
        motor_view._test_motor(0, 1)
    elif operation == "all":
        motor_view._test_all_motors()
    else:
        motor_view._test_motors_in_sequence()
    # Then: Every motor command path remains inactive.
    assert fake_model.single_motor_calls == []
    assert fake_model.all_motor_runs == 0
    assert fake_model.sequence_runs == 0
    assert fake_model.should_show_first_test_warning()


@pytest.mark.parametrize("operation", ["all", "sequence"])
@pytest.mark.parametrize("exception_type", [MotorTestSafetyError, ValidationError, RuntimeError])
def test_batch_motor_failures_show_feedback_without_claiming_success(
    motor_view: MotorTestView,
    fake_model: FakeMotorTestModel,
    dialog_spies: SimpleNamespace,
    operation: str,
    exception_type: type[Exception],
) -> None:
    """
    Explain rejected batch motor tests.

    GIVEN: Batch testing fails a safety check, parameter validation or transport operation
    WHEN: The operator runs all motors or a sequence
    THEN: The matching warning or error is displayed
    """
    # Given: Confirmation was acknowledged but the model rejects execution.
    fake_model._should_warn = False
    error = exception_type("Test cannot proceed")
    if operation == "all":
        fake_model.next_all_motor_error = error
        callback = motor_view._test_all_motors
    else:
        fake_model.next_sequence_error = error
        callback = motor_view._test_motors_in_sequence
    # When: Execute the batch test.
    callback()
    # Then: Safety failures are warnings and other failures are errors.
    if exception_type is MotorTestSafetyError:
        dialog_spies.showwarning.assert_called_once_with("Safety Check Failed", "Test cannot proceed")
    else:
        dialog_spies.showerror.assert_called_once()
        assert dialog_spies.showerror.call_args.args[1] == "Test cannot proceed"


@pytest.mark.parametrize("focused_control", ["throttle_spinbox", "duration_spinbox"])
def test_periodic_motor_refresh_preserves_the_input_being_edited(
    motor_view: MotorTestView, mocker: MockerFixture, focused_control: str
) -> None:
    """
    Preserve the operator's unfinished throttle or duration entry.

    GIVEN: A motor-test input has focus and contains an unfinished edit
    WHEN: The periodic view refresh runs
    THEN: The focused input is not overwritten by the current model value
    """
    # Given: Only one input has focus, as in a real Tk window.
    control = getattr(motor_view, focused_control)
    control.delete(0, "end")
    control.insert(0, "editing")
    mocker.patch("tkinter.Misc.focus_get", return_value=control)
    # When: Refresh current values from the model.
    motor_view._update_spinbox_values()
    # Then: User input survives the refresh.
    assert control.get() == "editing"


def test_fast_motor_operations_do_not_flash_a_progress_window(mocker: MockerFixture) -> None:
    """
    Delay progress feedback until an operation has actually taken long enough.

    GIVEN: A progress callback with a one-second delay
    WHEN: Updates arrive before and at the delay threshold
    THEN: Only the update at the threshold is forwarded
    """
    # Given: Control the clock rather than sleeping in the test.
    mocker.patch.object(motor_test_module.time, "time", side_effect=[0.0, 0.0, 0.5, 1.0])
    progress = MagicMock()
    delayed = DelayedProgressCallback(progress, delay_seconds=1.0)
    # When: Report progress over the first second.
    delayed(1, 3)
    delayed(2, 3)
    delayed(3, 3)
    # Then: Fast intermediate updates do not show progress UI.
    progress.assert_called_once_with(3, 3)


def test_missing_frame_selection_does_not_restart_the_controller(
    motor_view: MotorTestView, fake_model: FakeMotorTestModel, caplog: pytest.LogCaptureFixture
) -> None:
    """
    Ignore an empty frame-type selection safely.

    GIVEN: No frame type is selected
    WHEN: A selection-change notification arrives
    THEN: No controller configuration command is sent and the missing selection is logged
    """
    # Given: The combobox has no user selection.
    motor_view.frame_type_combobox.set("")
    # When: Handle the selection notification.
    motor_view._on_frame_type_change(None)
    # Then: Do not send an invalid frame update or restart.
    assert fake_model.last_frame_type_key is None
    assert "No frame type selected" in caplog.messages


def test_motor_diagram_without_a_supported_image_format_shows_its_path(
    motor_view: MotorTestView, fake_model: FakeMotorTestModel
) -> None:
    """
    Retain useful diagram information when only an unsupported image format is available.

    GIVEN: The model has an SVG diagram without a loading error
    WHEN: The view refreshes the motor diagram
    THEN: Its path is shown as descriptive fallback text
    """
    # Given: A diagram exists but cannot be displayed by the PNG loader.
    fake_model.diagram_available = True
    fake_model.diagram_path = "motor-layout.svg"
    fake_model.diagram_error = ""
    # When: Refresh the diagram.
    motor_view._update_diagram()
    # Then: Preserve useful information instead of showing an empty image.
    assert motor_view.diagram_label.cget("text") == "Diagram: motor-layout.svg"


def test_non_battery_motor_safety_failures_show_the_specific_check_reason(
    motor_view: MotorTestView, fake_model: FakeMotorTestModel, dialog_spies: SimpleNamespace
) -> None:
    """
    Explain safety rejections that are unrelated to battery voltage.

    GIVEN: Confirmation was acknowledged but the controller cannot safely run a motor
    WHEN: The user requests a single-motor test
    THEN: The actual safety reason is shown and the motor status reports the failure
    """
    # Given: A safety rejection unrelated to battery telemetry.
    fake_model._should_warn = False
    fake_model.next_single_motor_error = MotorTestSafetyError("Vehicle not secured", battery_related=False)
    # When: Attempt the test.
    motor_view._test_motor(0, 1)
    # Then: Do not substitute irrelevant battery guidance.
    dialog_spies.showwarning.assert_called_once_with("Safety Check Failed", "Vehicle not secured")
    assert motor_view.motor_status_labels[0].cget("text") == "Safety Check Failed"


@pytest.mark.parametrize("handler", ["frame", "spin_arm"])
@pytest.mark.parametrize("worker_restart", [False, True], ids=["synchronous", "sequoia-worker"])
@pytest.mark.parametrize("fails", [False, True], ids=["success", "failure"])
def test_motor_restart_retains_recovery_ownership_and_resumes_polling(
    motor_update_timers: dict[str, Callable[[], None]],
    motor_view: MotorTestView,
    handler: str,
    worker_restart: bool,
    fails: bool,
) -> None:
    """
    Motor configuration restarts retain the link and resume continuous polling.

    GIVEN: A frame or spin-arm restart that services Tk events
    WHEN: Recovery checks run during the restart, which succeeds or fails
    THEN: Recovery cannot read or reconnect, and battery polling resumes for multiple ticks.
    """
    recovery = ConnectionRecovery(MagicMock(), MagicMock(spec=FlightControllerReconnect), MagicMock())
    progress_window = MagicMock()
    progress_window.run_task.side_effect = lambda task, *, on_progress: task(on_progress)

    def restart(*_args: object, **_kwargs: object) -> None:
        assert recovery.operation_active
        assert motor_view.esc_telemetry_view._timer_id is None
        motor_view.esc_telemetry_view._poll()
        telemetry_poll.assert_not_called()
        recovery.check()
        recovery._monitor.poll.assert_not_called()
        recovery._monitor.reconnect.assert_not_called()
        if fails:
            message = "restart failed"
            raise ParameterError(message)

    method = "update_frame_type_by_key" if handler == "frame" else "set_motor_spin_arm_value"
    with (
        patch.object(motor_view.base_window, "_connection_recovery", recovery, create=True),
        patch.object(motor_test_module, "ProgressWindow", return_value=progress_window),
        patch.object(motor_test_module, "is_macos_sequoia_or_older", return_value=worker_restart),
        patch.object(motor_test_module, "askfloat", return_value=0.2),
        patch.object(motor_view.model, method, side_effect=restart),
        patch.object(motor_view, "_update_battery_status", wraps=motor_view._update_battery_status) as battery_poll,
        patch.object(motor_view.esc_telemetry_view.backend, "poll") as telemetry_poll,
    ):
        if handler == "frame":
            motor_view.frame_type_combobox.current(0)
            motor_view._on_frame_type_change(None)
        else:
            motor_view._set_motor_spin_arm()
        assert not recovery.operation_active
        assert motor_view.esc_telemetry_view._timer_id is not None
        for _tick in range(2):
            motor_update_timers.pop(motor_view._timer_id)()
            assert len(motor_update_timers) == 1
        assert battery_poll.call_count == 2


class TestMotorTestConnectionOwnership:
    """Motor operations preserve the exclusive connection owner."""

    @pytest.mark.parametrize("reconnect_fails", [False, True])
    def test_frame_type_reboot_keeps_recovery_from_reconnecting_at_the_same_time(
        self,
        motor_view_with_controller: MotorTestView,
        motor_connection_recovery: ConnectionRecovery,
        mocker: MockerFixture,
        dialog_spies: SimpleNamespace,
        reconnect_fails: bool,
    ) -> None:
        """
        Keep the frame-type reboot exclusive while its progress window processes events.

        GIVEN: Connection recovery is monitoring a motor-test view
        WHEN: Changing frame type clears the connection and progress runs a recovery check
        THEN: No background reconnect starts until the frame-change callback finishes
        """
        # Given: Real frame-change and recovery logic share the editor's navigation lock.
        view = motor_view_with_controller
        fc = cast("MagicMock", view.model.flight_controller)
        master = fc.master
        view.model.filesystem.doc_dict = {"FRAME_TYPE": {"RebootRequired": True}}
        fc.set_param.return_value = (True, "")
        fc.fetch_param.return_value = 0.0
        recovery = motor_connection_recovery
        worker = mocker.patch("ardupilot_methodic_configurator.frontend_tkinter_connection_recovery.Thread")
        worker.return_value.is_alive.return_value = False
        progress_window = MagicMock()
        mocker.patch.object(motor_test_module, "ProgressWindow", return_value=progress_window)
        progress_window.update_progress_bar_with_message.side_effect = lambda *_args: recovery.check()
        ticks = iter([0.0, 2.0])
        mocker.patch.object(motor_test_module, "time", SimpleNamespace(time=lambda: next(ticks)))

        def reboot(progress: Callable[[int, int], None], extra_sleep_time: int) -> str:
            assert extra_sleep_time == 2
            fc.master = None
            # Simulate the due recovery timer inside the progress window's nested event loop.
            progress(20, 100)
            assert recovery.state is RecoveryState.MONITORING
            worker.assert_not_called()
            if reconnect_fails:
                message = "Controller unavailable"
                raise OSError(message)
            fc.master = master
            fc.fc_parameters["FRAME_TYPE"] = 0.0
            return ""

        fc.reset_and_reconnect.side_effect = reboot
        view.frame_type_combobox.current(0)
        assert view.frame_type_combobox.get_selected_key() == "0"

        # When: Select Quad Plus instead of Quad X, requiring a reboot.
        view._on_frame_type_change(None)

        # Then: Cleanup releases ownership on both success and failure; monitoring can resume.
        fc.reset_and_reconnect.assert_called_once()
        progress_window.update_progress_bar_with_message.assert_called_once()
        progress_window.destroy.assert_called_once()
        assert not view.base_window.navigation_lock.locked
        worker.assert_not_called()
        recovery.check()
        if reconnect_fails:
            dialog_spies.showerror.assert_called_once()
            assert recovery.state is RecoveryState.RECOVERING
            worker.assert_called_once()
        else:
            assert view.model.frame_type == 0
            assert recovery.state is RecoveryState.MONITORING
            worker.assert_not_called()

    def test_activation_keeps_one_polling_loop_and_suspend_stops_pending_updates(
        self,
        motor_view_with_controller: MotorTestView,
        motor_update_timers: dict[str, Callable[[], None]],
        mocker: MockerFixture,
        pause_polling_plugin_for_recovery: Callable[[tk.Misc], Callable[[], None]],
    ) -> None:
        """
        Stop all polling during recovery even after construction and activation.

        GIVEN: The editor constructs and activates a real motor view
        WHEN: Recovery suspends it and an already queued callback fires
        THEN: No battery polling or timers survive, and resume uses the recovered frame
        """
        view = motor_view_with_controller
        view.on_activate()
        assert len(motor_update_timers) == 1
        assert view._timer_id is not None
        callback = motor_update_timers.pop(view._timer_id)
        callback()
        assert len(motor_update_timers) == 1
        callback = next(iter(motor_update_timers.values()))
        battery_poll = mocker.spy(view.model, "get_battery_display_text")

        resume = pause_polling_plugin_for_recovery(view)
        assert not motor_update_timers
        callback()
        battery_poll.assert_not_called()
        assert not motor_update_timers
        fc = cast("MagicMock", view.model.flight_controller)
        fc.fc_parameters.update(FRAME_CLASS=2.0, FRAME_TYPE=1.0)
        resume()

        assert (view.model.frame_class, view.model.frame_type) == (2, 1)
        assert len(view.motor_buttons) == 6
        assert len(motor_update_timers) == 1
        battery_poll.assert_called_once()
        fc.test_motor.assert_not_called()
        fc.stop_all_motors.assert_not_called()
        fc.set_param.assert_not_called()

    def test_resume_refreshes_frame_even_when_an_update_is_pending(
        self, motor_view_with_controller: MotorTestView, motor_update_timers: dict[str, Callable[[], None]]
    ) -> None:
        """
        Refresh cached frame values independently of polling state.

        GIVEN: A motor view with a pending update and newly recovered FC values
        WHEN: The view resumes
        THEN: Its model and controls use the new frame without adding a second timer
        """
        view = motor_view_with_controller
        timer_id = view._timer_id
        fc = cast("MagicMock", view.model.flight_controller)
        fc.fc_parameters.update(FRAME_CLASS=2.0, FRAME_TYPE=0.0)

        view.on_resume()

        assert (view.model.frame_class, view.model.frame_type) == (2, 0)
        assert len(view.motor_buttons) == 6
        assert view.frame_type_combobox.get_selected_key() == "0"
        assert view._timer_id == timer_id
        assert len(motor_update_timers) == 1

    @pytest.mark.parametrize(
        ("frame_class", "frame_type", "motor_numbers"),
        [(1, 1, [1, 4, 2, 3]), (1, 0, [3, 1, 4, 2]), (2, 1, [5, 1, 4, 6, 2, 3])],
        ids=["unchanged-quad-x", "quad-plus-same-motor-count", "hexa-x"],
    )
    def test_resuming_uses_the_recovered_frame_layout_without_motor_commands(
        self,
        motor_view_with_controller: MotorTestView,
        mocker: MockerFixture,
        frame_class: int,
        frame_type: int,
        motor_numbers: list[int],
    ) -> None:
        """
        Resume with the recovered frame while preserving settings and healthy-link state.

        GIVEN: A Quad X view paused while the same controller's cached frame values change
        WHEN: The view resumes after recovery or a healthy-link probe
        THEN: Motor controls, frame selection and diagram match the FC without sending commands
        """
        view = motor_view_with_controller
        fc = cast("MagicMock", view.model.flight_controller)
        original_buttons = list(view.motor_buttons)
        view.motor_status_labels[0].configure(text="Running")
        view.on_suspend(PluginPauseReason.CONNECTION_RECOVERY)
        fc.fc_parameters.update(FRAME_CLASS=float(frame_class), FRAME_TYPE=float(frame_type))

        view.on_resume()

        assert (view.model.frame_class, view.model.frame_type) == (frame_class, frame_type)
        assert view.model.motor_numbers == motor_numbers
        assert len(view.motor_buttons) == len(motor_numbers)
        assert view.frame_type_combobox.get_selected_key() == str(frame_type)
        assert view.frame_type_combobox.get_entries_tuple() == view.model.get_frame_type_pairs()
        assert view.diagram_label.cget("text") == f"Diagram: frame-{frame_class}-{frame_type}.svg"
        assert view.throttle_spinbox.get() == "25"
        assert view.duration_spinbox.get() == "3.0"
        test_motor = mocker.patch.object(view, "_test_motor")
        for index, (button, motor_number) in enumerate(zip(view.motor_buttons, motor_numbers, strict=True)):
            button.invoke()
            test_motor.assert_called_with(index, motor_number)
        if (frame_class, frame_type) == (1, 1):
            assert view.motor_buttons == original_buttons
            assert view.motor_status_labels[0].cget("text") == "Running"
        timer_id = view._timer_id
        assert timer_id is not None
        view.on_resume()
        assert view._timer_id == timer_id
        fc.test_motor.assert_not_called()
        fc.stop_all_motors.assert_not_called()
        fc.set_param.assert_not_called()

    def test_connection_probe_preserves_running_motors(
        self, motor_view: MotorTestView, fake_model: FakeMotorTestModel
    ) -> None:
        """GIVEN a running motor test, WHEN reception is suspended and resumed, THEN motors are not stopped or restarted."""
        motor_view._test_all_motors()
        stop_calls, runs = fake_model.stop_calls, fake_model.all_motor_runs
        editor = SimpleNamespace(current_plugin_view=motor_view, root=motor_view.root_window)
        resume = ParameterEditorWindow._pause_plugin_receiver(editor, reason=PluginPauseReason.CONNECTION_RECOVERY)
        assert motor_view._timer_id is None
        resume()
        assert motor_view._timer_id is not None
        assert fake_model.stop_calls == stop_calls
        assert fake_model.all_motor_runs == runs

    def test_exclusive_fc_operation_stops_motors_before_disabling_stop_shortcuts(
        self, motor_view: MotorTestView, fake_model: FakeMotorTestModel
    ) -> None:
        """GIVEN Test All is running, WHEN an FC tool takes reception, THEN motors stop and never restart on resume."""
        motor_view._test_all_motors()
        stop_calls, runs = fake_model.stop_calls, fake_model.all_motor_runs
        editor = SimpleNamespace(current_plugin_view=motor_view, root=motor_view.root_window)

        resume = ParameterEditorWindow._pause_plugin_receiver(editor)

        assert fake_model.stop_calls == stop_calls + 1
        assert motor_view._suspended
        assert motor_view._timer_id is None
        resume()
        assert not motor_view._suspended
        assert motor_view._timer_id is not None
        assert fake_model.all_motor_runs == runs

    @pytest.mark.parametrize("suspended", [False, True])
    def test_shortcuts_cannot_send_commands_while_connection_is_owned(
        self, motor_view: MotorTestView, fake_model: FakeMotorTestModel, suspended: bool
    ) -> None:
        """GIVEN recovery or diagnostics owns the link, WHEN a stop shortcut fires, THEN it sends no motor commands."""
        owner = object()
        if suspended:
            motor_view.on_suspend()
        else:
            motor_view.base_window.navigation_lock.acquire(owner)
        before = fake_model.emergency_runs
        assert motor_view._handle_keyboard_shortcut(motor_view._stop_all_motors) == "break"
        assert fake_model.emergency_runs == before
        if suspended:
            motor_view.on_resume()
        else:
            motor_view.base_window.navigation_lock.release(owner)
        motor_view._handle_keyboard_shortcut(motor_view._stop_all_motors)
        assert fake_model.emergency_runs == before + 1


class TestMotorSwapDialogs:
    """Operator-facing wording and recovery for the motor swap confirmation flow."""

    def test_declining_a_swap_asks_with_exact_wording_and_clears_the_selection(
        self, motor_view: MotorTestView, fake_model: FakeMotorTestModel, dialog_spies: SimpleNamespace, mocker
    ) -> None:
        """
        Declining a swap leaves motors untouched and clears the dropdown.

        GIVEN: Motor A's dropdown set to Motor B
        WHEN: The operator declines the swap confirmation
        THEN: The question names both motors, no swap happens and the dropdown is cleared
        """
        swap = mocker.patch.object(fake_model, "swap_motor_functions", create=True)
        dialog_spies.askyesno.return_value = False
        motor_view.detected_comboboxes[0].set("B")

        motor_view._on_motor_swapped("A", "B")

        dialog_spies.askyesno.assert_called_once_with(
            "Swapping Motors?",
            "Are you sure you want to swap the functions of Motor A and Motor B?",
        )
        swap.assert_not_called()
        dialog_spies.showinfo.assert_not_called()
        assert motor_view.detected_comboboxes[0].get() == ""

    def test_confirmed_swap_reports_success_naming_both_motors(
        self, motor_view: MotorTestView, fake_model: FakeMotorTestModel, dialog_spies: SimpleNamespace, mocker
    ) -> None:
        """
        A confirmed swap is applied and reported with the motor labels.

        GIVEN: The operator confirms swapping Motor A and Motor B
        WHEN: The swap completes without error
        THEN: The model swaps the two motors and the success dialog names them
        """
        swap = mocker.patch.object(fake_model, "swap_motor_functions", create=True)
        dialog_spies.askyesno.return_value = True

        motor_view._on_motor_swapped("A", "B")

        swap.assert_called_once_with("A", "B")
        dialog_spies.showinfo.assert_called_once_with("Success", "Motor A and Motor B have been successfully swapped.")
        dialog_spies.showerror.assert_not_called()

    def test_failed_swap_shows_the_model_error_and_still_clears_the_selection(
        self, motor_view: MotorTestView, fake_model: FakeMotorTestModel, dialog_spies: SimpleNamespace, mocker
    ) -> None:
        """
        A rejected swap explains why and leaves the dropdown clean.

        GIVEN: The operator confirms a swap that the model rejects
        WHEN: The model raises a ParameterError
        THEN: A "Swap Failed" error shows the model message, no success is reported and the dropdown is cleared
        """
        mocker.patch.object(
            fake_model, "swap_motor_functions", create=True, side_effect=ParameterError("Motor B is not configured")
        )
        dialog_spies.askyesno.return_value = True
        motor_view.detected_comboboxes[0].set("B")

        motor_view._on_motor_swapped("A", "B")

        dialog_spies.showerror.assert_called_once_with("Swap Failed", "Motor B is not configured")
        dialog_spies.showinfo.assert_not_called()
        assert motor_view.detected_comboboxes[0].get() == ""


class TestMotorThrottleAndDurationRecovery:
    """Invalid throttle and duration entries are reported and replaced with the last accepted value."""

    def test_non_numeric_throttle_reports_the_accepted_percentage_and_restores_it(
        self, motor_view: MotorTestView, fake_model: FakeMotorTestModel, dialog_spies: SimpleNamespace
    ) -> None:
        """
        A non-numeric throttle entry is rejected and the spinbox shows the model value again.

        GIVEN: A throttle of 25% accepted by the model
        WHEN: The operator types text that is not a number
        THEN: The spinbox shows 25 again and the error names 25%
        """
        motor_view.throttle_spinbox.delete(0, "end")
        motor_view.throttle_spinbox.insert(0, "abc")

        motor_view._on_throttle_change()

        dialog_spies.showerror.assert_called_once_with("Throttle value error", "Invalid throttle value entered, reset to 25%")
        assert motor_view.throttle_spinbox.get() == "25"
        assert fake_model.get_test_throttle_pct() == 25

    def test_throttle_rejected_by_the_model_shows_the_validation_reason(
        self, motor_view: MotorTestView, fake_model: FakeMotorTestModel, dialog_spies: SimpleNamespace, mocker
    ) -> None:
        """
        A throttle the model refuses shows the model reason and restores the accepted value.

        GIVEN: A throttle entry of 150 that the model refuses
        WHEN: The model raises a ValidationError
        THEN: A "Throttle value error" shows the validation reason and the spinbox returns to 25
        """
        mocker.patch.object(fake_model, "set_test_throttle_pct", side_effect=ValidationError("above maximum"))
        motor_view.throttle_spinbox.delete(0, "end")
        motor_view.throttle_spinbox.insert(0, "150")

        motor_view._on_throttle_change()

        dialog_spies.showerror.assert_called_once_with("Throttle value error", "Throttle validation failed: above maximum")
        assert motor_view.throttle_spinbox.get() == "25"

    def test_non_numeric_duration_reports_the_accepted_seconds_and_restores_them(
        self, motor_view: MotorTestView, fake_model: FakeMotorTestModel, dialog_spies: SimpleNamespace
    ) -> None:
        """
        A non-numeric duration entry is rejected and the spinbox shows the model value again.

        GIVEN: A duration of 3 seconds accepted by the model
        WHEN: The operator types text that is not a number
        THEN: The spinbox shows 3.0 again and the error names 3 seconds
        """
        motor_view.duration_spinbox.delete(0, "end")
        motor_view.duration_spinbox.insert(0, "soon")

        motor_view._on_duration_change()

        dialog_spies.showerror.assert_called_once_with(
            "Duration value error", "Invalid duration value entered, reset to 3 seconds"
        )
        assert motor_view.duration_spinbox.get() == "3.0"
        assert fake_model.get_test_duration_s() == 3.0

    def test_duration_rejected_by_the_model_shows_the_validation_reason(
        self, motor_view: MotorTestView, fake_model: FakeMotorTestModel, dialog_spies: SimpleNamespace, mocker
    ) -> None:
        """
        A duration the model refuses shows the model reason and restores the accepted value.

        GIVEN: A duration entry that the model refuses
        WHEN: The model raises a ParameterError
        THEN: A "Duration value error" shows the reason and the spinbox returns to 3.0
        """
        mocker.patch.object(fake_model, "set_test_duration_s", side_effect=ParameterError("too long"))
        motor_view.duration_spinbox.delete(0, "end")
        motor_view.duration_spinbox.insert(0, "999")

        motor_view._on_duration_change()

        dialog_spies.showerror.assert_called_once_with("Duration value error", "Duration validation failed: too long")
        assert motor_view.duration_spinbox.get() == "3.0"


class TestMotorSpinDialogs:
    """MOT_SPIN_ARM and MOT_SPIN_MIN dialogs keep their wording, bounds and error handling."""

    def test_spin_arm_dialog_is_prefilled_with_the_current_parameter(
        self, motor_view: MotorTestView, dialog_spies: SimpleNamespace
    ) -> None:
        """
        The spin-arm dialog starts from the value currently on the flight controller.

        GIVEN: MOT_SPIN_ARM currently set to 0.1
        WHEN: The operator opens the spin-arm dialog
        THEN: The question shows the margin wording and the input is prefilled with 0.1
        """
        motor_view._set_motor_spin_arm()

        dialog_spies.askfloat.assert_called_once_with(
            "Set Motor Spin Arm",
            "Enter new value for MOT_SPIN_ARM with 0.02 margin:",
            initialvalue=0.1,
        )

    def test_cancelling_spin_arm_dialog_changes_nothing(
        self, motor_view: MotorTestView, fake_model: FakeMotorTestModel, dialog_spies: SimpleNamespace, mocker
    ) -> None:
        """
        Cancelling the spin-arm dialog does not write anything to the flight controller.

        GIVEN: The spin-arm dialog is cancelled by the operator
        WHEN: The dialog returns None
        THEN: The model is not asked to change MOT_SPIN_ARM and the navigation lock is free
        """
        setter = mocker.patch.object(fake_model, "set_motor_spin_arm_value")
        dialog_spies.askfloat.return_value = None

        motor_view._set_motor_spin_arm()

        setter.assert_not_called()
        assert not motor_view.base_window.navigation_lock.locked

    def test_accepted_spin_arm_value_is_written_while_the_navigation_lock_is_held(
        self, motor_view: MotorTestView, fake_model: FakeMotorTestModel, dialog_spies: SimpleNamespace, mocker
    ) -> None:
        """
        An accepted spin-arm value is written, and other actions are locked out during the write.

        GIVEN: The operator enters 0.15 for MOT_SPIN_ARM
        WHEN: The write runs
        THEN: The model receives 0.15, the navigation lock is held during the write and released afterwards
        """
        locked_during_write: list[bool] = []

        def record_lock_state(*_args: object) -> None:
            locked_during_write.append(motor_view.base_window.navigation_lock.locked)

        setter = mocker.patch.object(fake_model, "set_motor_spin_arm_value", side_effect=record_lock_state)
        dialog_spies.askfloat.return_value = 0.15

        motor_view._set_motor_spin_arm()

        assert setter.call_args.args[0] == 0.15
        assert locked_during_write == [True]
        assert not motor_view.base_window.navigation_lock.locked

    def test_spin_arm_parameter_error_is_shown_as_a_plain_error_and_lock_is_released(
        self, motor_view: MotorTestView, fake_model: FakeMotorTestModel, dialog_spies: SimpleNamespace, mocker
    ) -> None:
        """
        A rejected spin-arm value shows the reason under the generic Error title.

        GIVEN: The operator enters a value the flight controller rejects
        WHEN: The model raises a ParameterError
        THEN: An "Error" dialog shows the reason and the navigation lock is released
        """
        mocker.patch.object(fake_model, "set_motor_spin_arm_value", side_effect=ParameterError("out of range"))
        dialog_spies.askfloat.return_value = 0.9

        motor_view._set_motor_spin_arm()

        dialog_spies.showerror.assert_called_once_with("Error", "out of range")
        assert not motor_view.base_window.navigation_lock.locked

    def test_spin_min_dialog_is_bounded_between_zero_and_one_and_prefilled(
        self, motor_view: MotorTestView, dialog_spies: SimpleNamespace
    ) -> None:
        """
        The spin-min dialog offers the full 0.0 to 1.0 range starting from the current value.

        GIVEN: MOT_SPIN_MIN currently set to 0.2
        WHEN: The operator opens the spin-min dialog
        THEN: The question explains the 0.02 rule and the input is bounded to 0.0 through 1.0
        """
        motor_view._set_motor_spin_min()

        dialog_spies.askfloat.assert_called_once_with(
            "Set Motor Spin Min",
            "Enter new value for MOT_SPIN_MIN, must be at least 0.02 higher than MOT_SPIN_ARM:",
            initialvalue=0.2,
            minvalue=0.0,
            maxvalue=1.0,
        )

    def test_accepted_spin_min_value_is_written_to_the_model(
        self, motor_view: MotorTestView, fake_model: FakeMotorTestModel, dialog_spies: SimpleNamespace, mocker
    ) -> None:
        """
        An accepted spin-min value is passed to the model unchanged.

        GIVEN: The operator enters 0.3 for MOT_SPIN_MIN
        WHEN: The dialog returns 0.3
        THEN: The model receives 0.3 and no error is shown
        """
        setter = mocker.patch.object(fake_model, "set_motor_spin_min_value")
        dialog_spies.askfloat.return_value = 0.3

        motor_view._set_motor_spin_min()

        setter.assert_called_once_with(0.3)
        dialog_spies.showerror.assert_not_called()

    def test_spin_min_rejection_is_shown_under_the_generic_error_title(
        self, motor_view: MotorTestView, fake_model: FakeMotorTestModel, dialog_spies: SimpleNamespace, mocker
    ) -> None:
        """
        A spin-min value the model rejects is reported to the operator.

        GIVEN: The model rejects MOT_SPIN_MIN because it is too close to MOT_SPIN_ARM
        WHEN: The operator submits the value
        THEN: An "Error" dialog shows the model message
        """
        mocker.patch.object(fake_model, "set_motor_spin_min_value", side_effect=ValidationError("too close to spin arm"))
        dialog_spies.askfloat.return_value = 0.11

        motor_view._set_motor_spin_min()

        dialog_spies.showerror.assert_called_once_with("Error", "too close to spin arm")

    def test_cancelling_spin_min_dialog_changes_nothing(
        self, motor_view: MotorTestView, fake_model: FakeMotorTestModel, dialog_spies: SimpleNamespace, mocker
    ) -> None:
        """
        Cancelling the spin-min dialog does not write to the flight controller.

        GIVEN: The spin-min dialog is cancelled
        WHEN: The dialog returns None
        THEN: The model is not called
        """
        setter = mocker.patch.object(fake_model, "set_motor_spin_min_value")
        dialog_spies.askfloat.return_value = None

        motor_view._set_motor_spin_min()

        setter.assert_not_called()


class TestMotorRunFeedback:
    """Each motor-run failure mode shows its own status label and dialog wording."""

    @pytest.mark.parametrize(
        ("error", "status", "dialog", "title", "message"),
        [
            (
                MotorTestSafetyError("Battery too low", battery_related=True),
                "Safety Check Failed",
                "showwarning",
                "Battery Voltage Warning",
                "Unsafe battery: Battery too low",
            ),
            (
                MotorTestSafetyError("Arming check failed"),
                "Safety Check Failed",
                "showwarning",
                "Safety Check Failed",
                "Arming check failed",
            ),
            (ValidationError("bad output"), "Invalid Parameters", "showerror", "Parameter Validation Error", "bad output"),
            (MotorTestExecutionError("link lost"), "Test Failed", "showerror", "Error", "link lost"),
            (RuntimeError("kaboom"), "Error", "showerror", "Unexpected Error", "kaboom"),
        ],
    )
    def test_single_motor_failure_marks_only_that_motor_and_explains_the_failure(  # pylint: disable=too-many-arguments,too-many-positional-arguments
        self,
        motor_view: MotorTestView,
        fake_model: FakeMotorTestModel,
        dialog_spies: SimpleNamespace,
        mocker,
        error: Exception,
        status: str,
        dialog: str,
        title: str,
        message: str,
    ) -> None:
        """
        A failing single-motor test explains itself and marks the affected motor in red.

        GIVEN: A single-motor test on motor output 2 that fails with the given error
        WHEN: The test is started
        THEN: Motor 2 shows the failure status in red and the matching dialog shows the title and message
        """
        mocker.patch.object(fake_model, "run_single_motor_test", side_effect=error)
        mocker.patch.object(
            fake_model, "is_battery_related_safety_issue", return_value=getattr(error, "battery_related", False)
        )

        motor_view._test_motor(0, 2)

        first, second = motor_view.motor_status_labels
        assert second.cget("text") == status
        assert str(second.cget("foreground")) == "red"
        assert first.cget("text") != status
        getattr(dialog_spies, dialog).assert_called_once_with(title, message)

    def test_single_motor_test_status_feedback_is_routed_through_the_model_callback(
        self, motor_view: MotorTestView, fake_model: FakeMotorTestModel, mocker
    ) -> None:
        """
        A single-motor test passes its status callback to the model so feedback reaches the labels.

        GIVEN: A healthy model
        WHEN: Motor output 1 is tested
        THEN: The model receives the view's status handler and the motor reports it sent the command
        """
        run = mocker.patch.object(fake_model, "run_single_motor_test")

        motor_view._test_motor(0, 1)

        run.assert_called_once_with(0, 1, motor_view._handle_status_event)

    @pytest.mark.parametrize(
        ("error", "dialog", "title", "message"),
        [
            (MotorTestSafetyError("Arming check failed"), "showwarning", "Safety Check Failed", "Arming check failed"),
            (ValidationError("bad output"), "showerror", "Parameter Validation Error", "bad output"),
            (MotorTestExecutionError("link lost"), "showerror", "Error", "link lost"),
            (RuntimeError("kaboom"), "showerror", "Unexpected Error", "kaboom"),
        ],
    )
    def test_all_motors_failure_is_explained_with_the_matching_dialog(  # pylint: disable=too-many-arguments,too-many-positional-arguments
        self,
        motor_view: MotorTestView,
        fake_model: FakeMotorTestModel,
        dialog_spies: SimpleNamespace,
        mocker,
        error: Exception,
        dialog: str,
        title: str,
        message: str,
    ) -> None:
        """
        A failed all-motors test shows the dialog that matches the failure.

        GIVEN: An all-motors test that fails with the given error
        WHEN: The test is started
        THEN: The matching dialog shows the title and the error text
        """
        mocker.patch.object(fake_model, "run_all_motors_test", side_effect=error)

        motor_view._test_all_motors()

        getattr(dialog_spies, dialog).assert_called_once_with(title, message)

    @pytest.mark.parametrize(
        ("error", "dialog", "title", "message"),
        [
            (MotorTestSafetyError("Arming check failed"), "showwarning", "Safety Check Failed", "Arming check failed"),
            (ValidationError("bad output"), "showerror", "Parameter Validation Error", "bad output"),
            (MotorTestExecutionError("link lost"), "showerror", "Error", "link lost"),
            (RuntimeError("kaboom"), "showerror", "Unexpected Error", "kaboom"),
        ],
    )
    def test_sequence_failure_is_explained_with_the_matching_dialog(  # pylint: disable=too-many-arguments,too-many-positional-arguments
        self,
        motor_view: MotorTestView,
        fake_model: FakeMotorTestModel,
        dialog_spies: SimpleNamespace,
        mocker,
        error: Exception,
        dialog: str,
        title: str,
        message: str,
    ) -> None:
        """
        A failed sequence test shows the dialog that matches the failure.

        GIVEN: A sequential test that fails with the given error
        WHEN: The sequence is started
        THEN: The matching dialog shows the title and the error text
        """
        mocker.patch.object(fake_model, "run_sequential_motor_test", side_effect=error)

        motor_view._test_motors_in_sequence()

        getattr(dialog_spies, dialog).assert_called_once_with(title, message)

    def test_all_motors_run_marks_every_motor_as_command_sent(
        self, motor_view: MotorTestView, fake_model: FakeMotorTestModel
    ) -> None:
        """
        Running all motors shows each motor as having received its command.

        GIVEN: A two-motor frame
        WHEN: All motors are tested together
        THEN: The model runs once and both motor labels read "Command sent" in green
        """
        motor_view._test_all_motors()

        assert fake_model.all_motor_runs == 1
        for label in motor_view.motor_status_labels:
            assert label.cget("text") == "Command sent"
            assert str(label.cget("foreground")) == "green"

    def test_emergency_stop_marks_motors_stop_sent_and_reports_failures(
        self, motor_view: MotorTestView, fake_model: FakeMotorTestModel, dialog_spies: SimpleNamespace
    ) -> None:
        """
        Emergency stop marks motors as stopped and reports a failed stop to the operator.

        GIVEN: A two-motor frame
        WHEN: An emergency stop succeeds, then fails with a model error
        THEN: The motors show "Stop sent" in red, and the failure is shown under the "Error" title
        """
        motor_view._stop_all_motors()

        assert fake_model.emergency_runs == 1
        for label in motor_view.motor_status_labels:
            assert label.cget("text") == "Stop sent"
            assert str(label.cget("foreground")) == "red"

        fake_model.next_emergency_error = MotorTestExecutionError("stop failed")
        motor_view._stop_all_motors()

        dialog_spies.showerror.assert_called_once_with("Error", "stop failed")


def test_throttle_entry_logs_the_requested_value_and_resulting_percentage(
    motor_view: MotorTestView, fake_model: FakeMotorTestModel, caplog: pytest.LogCaptureFixture
) -> None:
    """
    A valid throttle entry is logged with both the raw text and the applied percentage.

    GIVEN: A throttle spinbox holding "40"
    WHEN: The throttle change handler runs
    THEN: The model stores 40 and the debug log names the entered value and applied percentage
    """
    caplog.set_level("DEBUG")
    motor_view.throttle_spinbox.delete(0, "end")
    motor_view.throttle_spinbox.insert(0, "40")

    motor_view._on_throttle_change()

    assert fake_model.get_test_throttle_pct() == 40
    assert "_on_throttle_change called with value: 40" in caplog.messages
    assert "Throttle set to 40%" in caplog.messages


def test_invalid_throttle_entry_logs_and_reports_the_reset_value(
    motor_view: MotorTestView, dialog_spies: SimpleNamespace, caplog: pytest.LogCaptureFixture
) -> None:
    """
    A non-numeric throttle entry is reported and replaced with the model value.

    GIVEN: A throttle spinbox holding text that is not a number
    WHEN: The throttle change handler runs
    THEN: A warning is logged, the spinbox shows the model value and the operator sees the reset message
    """
    caplog.set_level("DEBUG")
    motor_view.throttle_spinbox.delete(0, "end")
    motor_view.throttle_spinbox.insert(0, "abc")

    motor_view._on_throttle_change()

    assert any(message.startswith("ValueError in _on_throttle_change: ") for message in caplog.messages)
    assert motor_view.throttle_spinbox.get() == "25"
    dialog_spies.showerror.assert_called_once_with("Throttle value error", "Invalid throttle value entered, reset to 25%")


def test_rejected_throttle_value_reports_the_validation_message(
    motor_view: MotorTestView, fake_model: FakeMotorTestModel, dialog_spies: SimpleNamespace, caplog: pytest.LogCaptureFixture
) -> None:
    """
    A throttle value rejected by the model is explained to the operator.

    GIVEN: A model that rejects the throttle value with a parameter error
    WHEN: The throttle change handler runs
    THEN: The rejection is logged and the operator sees the validation message under the throttle title
    """
    caplog.set_level("DEBUG")
    fake_model.raise_throttle_error = ParameterError("too high")
    motor_view.throttle_spinbox.delete(0, "end")
    motor_view.throttle_spinbox.insert(0, "90")

    motor_view._on_throttle_change()

    assert "ValidationError/ParameterError in _on_throttle_change: too high" in caplog.messages
    assert motor_view.throttle_spinbox.get() == "25"
    dialog_spies.showerror.assert_called_once_with("Throttle value error", "Throttle validation failed: too high")


def test_duration_entry_logs_the_requested_value_and_applied_seconds(
    motor_view: MotorTestView, fake_model: FakeMotorTestModel, caplog: pytest.LogCaptureFixture
) -> None:
    """
    A valid duration entry is logged with the raw text and the applied seconds.

    GIVEN: A duration spinbox holding "4.5"
    WHEN: The duration change handler runs
    THEN: The model stores 4.5 and the debug log names the entered value and applied seconds
    """
    caplog.set_level("DEBUG")
    motor_view.duration_spinbox.delete(0, "end")
    motor_view.duration_spinbox.insert(0, "4.5")

    motor_view._on_duration_change()

    assert fake_model.get_test_duration_s() == 4.5
    assert "_on_duration_change called with value: 4.5" in caplog.messages
    assert "Duration set to 4.5 seconds" in caplog.messages


def test_invalid_duration_entry_logs_and_reports_the_reset_value(
    motor_view: MotorTestView, dialog_spies: SimpleNamespace, caplog: pytest.LogCaptureFixture
) -> None:
    """
    A non-numeric duration entry is reported and replaced with the model value.

    GIVEN: A duration spinbox holding text that is not a number
    WHEN: The duration change handler runs
    THEN: A warning is logged, the spinbox shows the model duration and the operator sees the reset message
    """
    caplog.set_level("DEBUG")
    motor_view.duration_spinbox.delete(0, "end")
    motor_view.duration_spinbox.insert(0, "abc")

    motor_view._on_duration_change()

    assert any(message.startswith("ValueError in _on_duration_change: ") for message in caplog.messages)
    assert motor_view.duration_spinbox.get() == "3.0"
    dialog_spies.showerror.assert_called_once_with(
        "Duration value error", "Invalid duration value entered, reset to 3 seconds"
    )


def test_rejected_duration_value_reports_the_validation_message(
    motor_view: MotorTestView, fake_model: FakeMotorTestModel, dialog_spies: SimpleNamespace, caplog: pytest.LogCaptureFixture
) -> None:
    """
    A duration value rejected by the model is explained to the operator.

    GIVEN: A model that rejects the duration with a validation error
    WHEN: The duration change handler runs
    THEN: The rejection is logged and the operator sees the validation message under the duration title
    """
    caplog.set_level("DEBUG")
    fake_model.raise_duration_error = ValidationError("too long")
    motor_view.duration_spinbox.delete(0, "end")
    motor_view.duration_spinbox.insert(0, "99")

    motor_view._on_duration_change()

    assert "ValidationError/ParameterError in _on_duration_change: too long" in caplog.messages
    assert motor_view.duration_spinbox.get() == "3.0"
    dialog_spies.showerror.assert_called_once_with("Duration value error", "Duration validation failed: too long")


def test_spin_arm_dialog_uses_its_title_and_reports_model_rejections(
    motor_view: MotorTestView, fake_model: FakeMotorTestModel, dialog_spies: SimpleNamespace
) -> None:
    """
    The MOT_SPIN_ARM dialog is titled and rejected values are reported under the generic error title.

    GIVEN: The operator enters a spin-arm value that the model rejects
    WHEN: The spin-arm dialog is confirmed
    THEN: The dialog uses its own title and the rejection message is shown under "Error"
    """
    dialog_spies.askfloat.return_value = 0.3
    fake_model.raise_spin_arm_error = ParameterError("out of range")

    motor_view._set_motor_spin_arm()

    assert dialog_spies.askfloat.call_args.args[0] == "Set Motor Spin Arm"
    dialog_spies.showerror.assert_called_once_with("Error", "out of range")


def test_frame_type_change_shows_the_restart_progress_window_with_its_texts(
    motor_view: MotorTestView, mocker: MockerFixture
) -> None:
    """
    A frame type change shows a restart progress window that only appears for slow restarts.

    GIVEN: A selected frame type and a patched progress window
    WHEN: The frame type change is handled
    THEN: The progress window is created with the restart title, status text and auto-close policy
    """
    progress_window_cls = mocker.patch.object(motor_test_module, "ProgressWindow")
    motor_view.frame_type_combobox.current(0)

    motor_view._on_frame_type_change(None)

    progress_window_cls.assert_called_once_with(
        motor_view.root_window,
        "Restarting Flight Controller",
        "Reset command sent",
        only_show_when_update_progress_called=True,
        auto_close_on_complete=False,
    )
    progress_window_cls.return_value.destroy.assert_called_once_with()


def test_frame_type_change_delays_progress_and_forwards_it_to_the_restart_window(
    motor_view: MotorTestView, fake_model: FakeMotorTestModel, mocker: MockerFixture
) -> None:
    """
    Restart progress is forwarded to the progress window only after one second of waiting.

    GIVEN: A frame type change with a controlled clock
    WHEN: The model reports progress at 0.0, 0.5 and 1.0 seconds after the first report
    THEN: Nothing is forwarded before one second and the first report after it reaches the restart progress window
    """
    clock = {"now": 100.0}
    mocker.patch.object(motor_test_module.time, "time", side_effect=lambda: clock["now"])
    progress_window = MagicMock()
    mocker.patch.object(motor_test_module, "ProgressWindow", return_value=progress_window)
    update_progress = mocker.patch.object(motor_test_module, "update_flight_controller_restart_progress")
    spy = mocker.patch.object(fake_model, "update_frame_type_by_key")
    motor_view.frame_type_combobox.current(0)

    motor_view._on_frame_type_change(None)

    key, delayed_callback = spy.call_args.args[0], spy.call_args.args[1]
    assert key == fake_model.get_current_frame_selection_key() or isinstance(key, str)
    assert spy.call_args.kwargs == {"extra_sleep_time": 2}
    assert isinstance(delayed_callback, DelayedProgressCallback)
    assert delayed_callback.delay_seconds == 1.0

    delayed_callback(1, 4)
    clock["now"] = 100.5
    delayed_callback(2, 4)
    update_progress.assert_not_called()

    clock["now"] = 101.0
    delayed_callback(3, 4)
    update_progress.assert_called_once_with(progress_window, 3, 4)


def test_spin_arm_change_shows_the_restart_progress_window_without_the_slow_only_option(
    motor_view: MotorTestView, dialog_spies: SimpleNamespace, mocker: MockerFixture
) -> None:
    """
    Changing MOT_SPIN_ARM shows the restart progress window immediately.

    GIVEN: A confirmed spin-arm value and a patched progress window
    WHEN: The spin-arm change runs
    THEN: The progress window is created with the restart texts and without the slow-only option
    """
    dialog_spies.askfloat.return_value = 0.3
    progress_window_cls = mocker.patch.object(motor_test_module, "ProgressWindow")

    motor_view._set_motor_spin_arm()

    progress_window_cls.assert_called_once_with(
        motor_view.root_window,
        "Restarting Flight Controller",
        "Reset command sent",
        auto_close_on_complete=False,
    )
    progress_window_cls.return_value.destroy.assert_called_once_with()


def test_frame_type_change_marks_the_diagram_for_refresh(motor_view: MotorTestView, mocker: MockerFixture) -> None:
    """
    A frame type change makes the next view refresh redraw the motor diagram.

    GIVEN: A selected frame type and a spy on the diagram update
    WHEN: The frame type change completes and the view refreshes
    THEN: The diagram update runs
    """
    mocker.patch.object(motor_test_module, "ProgressWindow")
    diagram_update = mocker.spy(motor_view, "_update_diagram")
    motor_view.frame_type_combobox.current(0)

    motor_view._on_frame_type_change(None)
    motor_view._update_view()

    diagram_update.assert_called_once_with()


def test_restart_keeps_telemetry_suspended_while_the_view_is_suspended(
    motor_view: MotorTestView, mocker: MockerFixture
) -> None:
    """
    A restart does not resume telemetry while the view is suspended.

    GIVEN: A suspended motor test view and a spy on telemetry resume
    WHEN: A restart task runs
    THEN: Telemetry is not resumed
    """
    resume = mocker.patch.object(motor_view.esc_telemetry_view, "on_resume")
    motor_view._suspended = True

    motor_view._run_restart_task(MagicMock(), lambda _report: None, lambda _current, _total: None)

    resume.assert_not_called()


def test_restart_resumes_telemetry_when_the_view_is_active(motor_view: MotorTestView, mocker: MockerFixture) -> None:
    """
    A restart resumes telemetry once it completes for an active view.

    GIVEN: An active motor test view and a spy on telemetry resume
    WHEN: A restart task runs
    THEN: Telemetry is resumed exactly once
    """
    resume = mocker.patch.object(motor_view.esc_telemetry_view, "on_resume")

    motor_view._run_restart_task(MagicMock(), lambda _report: None, lambda _current, _total: None)

    resume.assert_called_once_with()


def test_restart_reschedules_updates_only_when_they_were_running(
    motor_view: MotorTestView, motor_update_timers: dict[str, Callable[[], None]]
) -> None:
    """
    Restarting does not start the update clock when it was not running before.

    GIVEN: A motor test view whose update clock is stopped
    WHEN: A restart task runs
    THEN: No update timer is pending afterwards
    """
    motor_view._timer_id = None
    timers_before_restart = set(motor_update_timers)

    motor_view._run_restart_task(MagicMock(), lambda _report: None, lambda _current, _total: None)

    assert motor_view._timer_id is None
    assert set(motor_update_timers) == timers_before_restart


def test_restart_reschedules_updates_that_were_running_before(
    motor_view: MotorTestView, motor_update_timers: dict[str, Callable[[], None]]
) -> None:
    """
    Restarting restores the update clock that was running before it started.

    GIVEN: A motor test view with a pending update timer
    WHEN: A restart task runs
    THEN: The previous timer is cancelled and a new one is pending
    """
    motor_view._update_view()
    previous_timer = motor_view._timer_id
    assert previous_timer in motor_update_timers

    motor_view._run_restart_task(MagicMock(), lambda _report: None, lambda _current, _total: None)

    assert previous_timer not in motor_update_timers
    assert motor_view._timer_id is not None
    assert motor_view._timer_id in motor_update_timers


def test_deactivation_cancels_the_pending_update_timer(
    motor_view: MotorTestView, motor_update_timers: dict[str, Callable[[], None]]
) -> None:
    """
    Leaving the plugin cancels the pending update timer and clears its handle.

    GIVEN: A motor test view with a pending update timer
    WHEN: The plugin is deactivated
    THEN: The timer is cancelled and no timer handle remains
    """
    motor_view._update_view()
    timer_id = motor_view._timer_id
    assert timer_id in motor_update_timers

    motor_view.on_deactivate()

    assert timer_id not in motor_update_timers
    assert motor_view._timer_id is None


def test_suspending_for_recovery_yields_without_stopping_motors(
    motor_view: MotorTestView, fake_model: FakeMotorTestModel, mocker: MockerFixture
) -> None:
    """
    Connection recovery suspends the view without commanding motors to stop.

    GIVEN: A motor test view and a spy on telemetry suspension
    WHEN: The view is suspended for connection recovery
    THEN: Telemetry is suspended with that reason, no motor stop is sent and the view is marked suspended
    """
    suspend = mocker.patch.object(motor_view.esc_telemetry_view, "on_suspend")
    deactivate = mocker.spy(motor_view, "on_deactivate")

    motor_view.on_suspend(PluginPauseReason.CONNECTION_RECOVERY)

    suspend.assert_called_once_with(PluginPauseReason.CONNECTION_RECOVERY)
    deactivate.assert_not_called()
    assert fake_model.stop_calls == 0
    assert motor_view._suspended is True


def test_exclusive_suspend_defaults_the_telemetry_reason_and_cancels_updates(
    motor_view: MotorTestView, motor_update_timers: dict[str, Callable[[], None]], mocker: MockerFixture
) -> None:
    """
    An exclusive operation suspends telemetry with its reason and cancels the update clock.

    GIVEN: A motor test view with a pending update timer
    WHEN: The view is suspended without an explicit reason
    THEN: Telemetry is suspended for an exclusive operation, the timer is cancelled and the view is deactivated
    """
    suspend = mocker.patch.object(motor_view.esc_telemetry_view, "on_suspend")
    motor_view._update_view()
    timer_id = motor_view._timer_id

    motor_view.on_suspend()

    suspend.assert_called_once_with(PluginPauseReason.EXCLUSIVE_OPERATION)
    assert timer_id not in motor_update_timers
    assert motor_view._timer_id is None


def test_resume_warns_when_the_frame_cannot_be_refreshed(
    motor_view: MotorTestView, fake_model: FakeMotorTestModel, caplog: pytest.LogCaptureFixture
) -> None:
    """
    A failed frame refresh on resume is logged as a warning.

    GIVEN: A flight controller whose frame configuration cannot be refreshed
    WHEN: The plugin resumes
    THEN: A warning explains that the frame configuration could not be refreshed
    """
    caplog.set_level("DEBUG")
    fake_model.refresh_returns = False

    motor_view.on_resume()

    assert "Could not refresh frame configuration from flight controller" in caplog.messages


def test_motor_status_defaults_to_black_text(motor_view: MotorTestView) -> None:
    """
    A motor status update without an explicit colour is shown in black.

    GIVEN: A motor test view
    WHEN: A status is set without a colour
    THEN: The status label text is black
    """
    motor_view._update_motor_status(1, "Running")

    labels = [label for label in motor_view.motor_status_labels if label.cget("text") == "Running"]
    assert len(labels) == 1
    assert str(labels[0].cget("foreground")) == "black"


def test_resetting_motor_status_restores_ready_in_blue(motor_view: MotorTestView) -> None:
    """
    Resetting motor status returns every motor to the ready state in blue.

    GIVEN: A motor status that was shown in red
    WHEN: All motor statuses are reset
    THEN: Every motor status reads "Ready" in blue
    """
    motor_view._update_motor_status(1, "Failed", "red")

    motor_view._reset_all_motor_status()

    for label in motor_view.motor_status_labels:
        assert label.cget("text") == "Ready"
        assert str(label.cget("foreground")) == "blue"


def test_sequence_test_reports_status_through_the_view_handler(
    motor_view: MotorTestView, fake_model: FakeMotorTestModel, caplog: pytest.LogCaptureFixture, mocker: MockerFixture
) -> None:
    """
    The sequential motor test streams its status updates to the view.

    GIVEN: A confirmed sequential motor test
    WHEN: The sequence is started
    THEN: The model receives the view's status handler and the start is logged
    """
    caplog.set_level("DEBUG")
    run_sequence = mocker.patch.object(fake_model, "run_sequential_motor_test")

    motor_view._test_motors_in_sequence()

    run_sequence.assert_called_once_with(motor_view._handle_status_event)
    assert "Testing motors in sequence" in caplog.messages


def test_all_motors_and_stop_all_log_their_actions(motor_view: MotorTestView, caplog: pytest.LogCaptureFixture) -> None:
    """
    Testing all motors and stopping them are both recorded in the debug log.

    GIVEN: A motor test view
    WHEN: All motors are tested and then stopped
    THEN: Each action is logged with its description
    """
    caplog.set_level("DEBUG")

    motor_view._test_all_motors()
    motor_view._stop_all_motors()

    assert "Testing all motors" in caplog.messages
    assert "Stopping all motors" in caplog.messages


def test_single_motor_test_logs_the_sequence_and_output_numbers(
    motor_view: MotorTestView, fake_model: FakeMotorTestModel, caplog: pytest.LogCaptureFixture
) -> None:
    """
    A single motor test records which sequence position and motor output it addresses.

    GIVEN: A motor test view with three motor sequence labels
    WHEN: Motor sequence position 2 is tested on motor output 1
    THEN: The debug log names the sequence label and the motor output
    """
    caplog.set_level("DEBUG")
    fake_model.motor_labels = ["A", "B", "C"]

    motor_view._test_motor(2, 1)

    assert "Testing motor C at motor output 1" in caplog.messages


def _mock_png_loader(mocker: MockerFixture, dummy_base_window: DummyBaseWindow, tk_root: tk.Tk) -> MagicMock:
    """Make the diagram loader return a label carrying a real image, so Tk can display it."""
    photo = tk.PhotoImage(master=tk_root, width=1, height=1)
    label = ttk.Label(tk_root)
    cast("Any", label).image = photo
    return mocker.patch.object(dummy_base_window, "put_image_in_label", return_value=label)


def test_png_diagram_load_logs_the_path_and_success(
    motor_view: MotorTestView,
    dummy_base_window: DummyBaseWindow,
    tk_root: tk.Tk,
    mocker: MockerFixture,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """
    A loaded PNG diagram is logged with its path and a success message.

    GIVEN: A diagram file that the image loader can display
    WHEN: The diagram is loaded
    THEN: The debug log names the diagram path and reports the successful display
    """
    caplog.set_level("DEBUG")
    _mock_png_loader(mocker, dummy_base_window, tk_root)

    motor_view._load_png_diagram("layout.png")

    assert "Found PNG diagram at: layout.png" in caplog.messages
    assert "Image loaded and displayed successfully" in caplog.messages


def test_png_diagram_loader_uses_the_motor_diagram_height_and_fallback(
    motor_view: MotorTestView, dummy_base_window: DummyBaseWindow, tk_root: tk.Tk, mocker: MockerFixture
) -> None:
    """
    The diagram loader asks for the motor diagram height and a translated fallback text.

    GIVEN: A diagram loader spy
    WHEN: A diagram is loaded
    THEN: The loader receives the 230 pixel height, the fallback text and a parent under the diagram's container
    """
    loader = _mock_png_loader(mocker, dummy_base_window, tk_root)

    motor_view._load_png_diagram("layout.png")

    kwargs = loader.call_args.kwargs
    assert kwargs["filepath"] == "layout.png"
    assert kwargs["image_height"] == 230
    assert kwargs["fallback_text"] == "Error loading diagram"
    assert str(kwargs["parent"].master) == str(motor_view.diagram_label.master)


def test_failed_png_load_clears_the_previously_shown_diagram(
    motor_view: MotorTestView,
    dummy_base_window: DummyBaseWindow,
    tk_root: tk.Tk,
    mocker: MockerFixture,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """
    A diagram that fails to load does not leave the previous diagram image in place.

    GIVEN: A diagram that was displayed successfully
    WHEN: A later diagram file is missing
    THEN: The image reference is cleared, the label reads "Diagram not found" and the missing path is logged
    """
    caplog.set_level("DEBUG")
    loader = _mock_png_loader(mocker, dummy_base_window, tk_root)
    motor_view._load_png_diagram("layout.png")
    assert motor_view._current_diagram_image is not None
    loader.side_effect = FileNotFoundError("missing")

    motor_view._load_png_diagram("missing.png")

    assert motor_view._current_diagram_image is None
    assert motor_view.diagram_label.cget("text") == "Diagram not found"
    assert "Image file not found: missing.png" in caplog.messages


def test_png_diagram_decoding_error_is_logged_with_its_reason(
    motor_view: MotorTestView, dummy_base_window: DummyBaseWindow, mocker: MockerFixture, caplog: pytest.LogCaptureFixture
) -> None:
    """
    A diagram that cannot be decoded is logged with the underlying reason.

    GIVEN: An image loader that fails with an OS error
    WHEN: The diagram is loaded
    THEN: The error is logged with its reason and the label reads "Error loading diagram"
    """
    caplog.set_level("DEBUG")
    mocker.patch.object(dummy_base_window, "put_image_in_label", side_effect=OSError("corrupt"))

    motor_view._load_png_diagram("layout.png")

    assert "Error loading PNG diagram: corrupt" in caplog.messages
    assert motor_view.diagram_label.cget("text") == "Error loading diagram"
    assert motor_view._current_diagram_image is None


def test_deactivation_reports_an_expected_motor_stop_failure(
    motor_view: MotorTestView, fake_model: FakeMotorTestModel, caplog: pytest.LogCaptureFixture
) -> None:
    """
    A motor stop failure during deactivation is logged as a warning for the operator to verify.

    GIVEN: A model whose stop command fails with a motor test execution error
    WHEN: The plugin is deactivated
    THEN: A warning asks the operator to verify the motors are stopped
    """
    caplog.set_level("DEBUG")
    fake_model.raise_stop_error = MotorTestExecutionError("stop failed")

    motor_view.on_deactivate()

    assert "Motor stop failed during deactivation: stop failed. Please verify motors are stopped." in caplog.messages


def test_deactivation_logs_and_re_raises_unexpected_motor_stop_errors(
    motor_view: MotorTestView, fake_model: FakeMotorTestModel, caplog: pytest.LogCaptureFixture
) -> None:
    """
    An unexpected motor stop error during deactivation is logged as critical and re-raised.

    GIVEN: A model whose stop command fails unexpectedly
    WHEN: The plugin is deactivated
    THEN: The error is logged with its reason and propagated to the caller
    """
    caplog.set_level("DEBUG")
    fake_model.raise_stop_error = RuntimeError("boom")

    with pytest.raises(RuntimeError, match="boom"):
        motor_view.on_deactivate()

    assert "Critical error during motor stop at deactivation: boom" in caplog.messages


def _build_motor_window(mocker: MockerFixture, model: FakeMotorTestModel) -> tuple[MotorTestWindow, MagicMock, MagicMock]:
    root_mock = MagicMock()

    def fake_base_init(self) -> None:
        self.root = root_mock
        self.main_frame = MagicMock(name="main_frame")
        self.dpi_scaling_factor = 1.0

    mocker.patch("ardupilot_methodic_configurator.plugins.frontend_tkinter_motor_test.BaseWindow.__init__", fake_base_init)
    view_cls = mocker.patch("ardupilot_methodic_configurator.plugins.frontend_tkinter_motor_test.MotorTestView")
    window = MotorTestWindow(cast("MotorTestDataModel", model))
    return window, root_mock, view_cls


def test_standalone_window_is_titled_sized_and_wired_to_its_view(
    fake_model: FakeMotorTestModel, mocker: MockerFixture
) -> None:
    """
    The standalone motor test window is titled, sized and built around its model and close handler.

    GIVEN: A patched base window and a motor test model
    WHEN: The standalone window is created
    THEN: It keeps the model, has the motor test title, uses the scaled 400x610 geometry, builds its view
          with the main frame, model and window, and routes the close button to on_close
    """
    window, root_mock, view_cls = _build_motor_window(mocker, fake_model)

    assert window.model is fake_model
    root_mock.title.assert_called_once_with("ArduPilot Motor Test")
    root_mock.geometry.assert_called_once_with(window.calculate_scaled_geometry(400, 610))
    assert root_mock.geometry.call_args.args[0] == "400x610"
    view_cls.assert_called_once_with(window.main_frame, fake_model, window)
    root_mock.protocol.assert_called_once_with("WM_DELETE_WINDOW", window.on_close)


def test_standalone_window_close_stops_motors_and_destroys_the_root(
    fake_model: FakeMotorTestModel, mocker: MockerFixture
) -> None:
    """
    Closing the standalone window stops the motors and then destroys the window.

    GIVEN: A standalone motor test window whose stop command succeeds
    WHEN: The window is closed
    THEN: The stop command runs and the root window is destroyed
    """
    window, root_mock, _view_cls = _build_motor_window(mocker, fake_model)
    window.view.model = fake_model
    stop = mocker.spy(fake_model, "stop_all_motors")

    window.on_close()

    stop.assert_called_once_with()
    root_mock.destroy.assert_called_once_with()


def test_standalone_window_close_logs_expected_stop_refusals_at_debug(
    fake_model: FakeMotorTestModel, mocker: MockerFixture, caplog: pytest.LogCaptureFixture
) -> None:
    """
    Frame types without motor commands are logged quietly when the window closes.

    GIVEN: A model whose stop command reports that the frame type does not support it
    WHEN: The standalone window is closed
    THEN: A debug message explains the refusal is normal and the root window is still destroyed
    """
    caplog.set_level("DEBUG")
    window, root_mock, _view_cls = _build_motor_window(mocker, fake_model)
    window.view.model = fake_model
    fake_model.raise_stop_error = MotorTestExecutionError("unsupported")

    window.on_close()

    assert "Motor stop command failed during shutdown - this is normal for some frame types" in caplog.messages
    root_mock.destroy.assert_called_once_with()


def test_standalone_window_close_logs_unexpected_stop_errors_and_still_closes(
    fake_model: FakeMotorTestModel, mocker: MockerFixture, caplog: pytest.LogCaptureFixture
) -> None:
    """
    An unexpected stop error does not prevent the standalone window from closing.

    GIVEN: A model whose stop command fails unexpectedly
    WHEN: The standalone window is closed
    THEN: A warning names the error and the root window is still destroyed
    """
    caplog.set_level("DEBUG")
    window, root_mock, _view_cls = _build_motor_window(mocker, fake_model)
    window.view.model = fake_model
    fake_model.raise_stop_error = RuntimeError("unexpected")

    window.on_close()

    assert "Unexpected error during motor stop at shutdown: unexpected" in caplog.messages
    root_mock.destroy.assert_called_once_with()


def test_motor_view_factory_passes_its_arguments_to_the_view(
    mocker: MockerFixture, fake_model: FakeMotorTestModel, dummy_base_window: DummyBaseWindow
) -> None:
    """
    The plugin factory builds the motor test view from the parent, model and base window it receives.

    GIVEN: A patched view class, a parent frame, a model and a base window
    WHEN: The factory creates the view
    THEN: The view is built with exactly those three arguments
    """
    view_cls = mocker.patch.object(motor_test_module, "MotorTestView")
    parent = MagicMock(name="parent")

    result = _create_motor_test_view(parent, fake_model, dummy_base_window)

    view_cls.assert_called_once_with(parent, fake_model, dummy_base_window)
    assert result is view_cls.return_value


def test_delayed_progress_callback_measures_elapsed_time_from_its_first_report(mocker: MockerFixture) -> None:
    """
    A delayed progress callback waits for the configured time measured from its first report.

    GIVEN: A progress callback delayed by one second and a controlled clock
    WHEN: Reports arrive at 100.0, 100.5 and 101.0 seconds
    THEN: Only the report that is at least one second after the first report is forwarded
    """
    clock = {"now": 100.0}
    mocker.patch.object(motor_test_module.time, "time", side_effect=lambda: clock["now"])
    received: list[tuple[int, int]] = []
    delayed = DelayedProgressCallback(lambda current, total: received.append((current, total)), 1.0)

    delayed(1, 10)
    clock["now"] = 100.5
    delayed(2, 10)
    assert not received
    clock["now"] = 101.0
    delayed(3, 10)
    assert received == [(3, 10)]
