#!/usr/bin/env python3
"""
User-visible receiver checks and plugin lifecycle behavior.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import tkinter as tk
from collections.abc import Callable, Generator
from tkinter import ttk
from types import SimpleNamespace
from typing import cast
from unittest.mock import MagicMock, patch

import pytest

from ardupilot_methodic_configurator import _
from ardupilot_methodic_configurator.__main__ import register_plugins
from ardupilot_methodic_configurator.frontend_tkinter_base_window import BaseWindow
from ardupilot_methodic_configurator.frontend_tkinter_navigation_lock import NavigationLock
from ardupilot_methodic_configurator.frontend_tkinter_parameter_editor import ParameterEditorWindow
from ardupilot_methodic_configurator.plugins import frontend_tkinter_rc_receiver as frontend
from ardupilot_methodic_configurator.plugins.data_model_rc_receiver import RCReceiverDataModel, RCReceiverState
from ardupilot_methodic_configurator.plugins.frontend_tkinter_rc_receiver import RCReceiverView
from ardupilot_methodic_configurator.plugins.plugin_constants import PLUGIN_RC_RECEIVER
from ardupilot_methodic_configurator.plugins.plugin_factory import PluginFactory, PluginModelContext

# pylint: disable=protected-access,redefined-outer-name


@pytest.fixture
def receiver_view(root: tk.Tk) -> Generator[RCReceiverView, None, None]:
    """Use real widgets and model with only the transport and parent services mocked."""
    controller = MagicMock()
    controller.request_rc_receiver_messages.return_value = (True, "")
    controller.master.recv_match.return_value = None
    # pylint: disable=duplicate-code
    with (
        patch("tkinter.Misc.update"),
        patch("tkinter.Misc.update_idletasks"),
        patch("tkinter.Misc.wait_visibility"),
        patch("tkinter.Misc.wait_window"),
    ):
        parent = ttk.Frame(root)
        view = RCReceiverView(parent, RCReceiverDataModel(controller), MagicMock(spec=BaseWindow))
        try:
            yield view
        finally:
            view.destroy()
            parent.destroy()
        # pylint: enable=duplicate-code


def test_recovery_cancels_the_real_receiver_timer_and_resumes_one_polling_loop(
    receiver_view: RCReceiverView,
    pause_polling_plugin_for_recovery: Callable[[tk.Misc], Callable[[], None]],
    fire_tk_timer: Callable[[tk.Misc, str], None],
) -> None:
    """
    Yield the receiver plugin through its legacy lifecycle.

    GIVEN: A receiver view actively reading RC telemetry
    WHEN: The editor pauses it for connection recovery and later resumes it
    THEN: Every polling timer is cancelled and reception restarts once
    """
    view = receiver_view
    view.on_activate()
    assert view._timer_id is not None
    fire_tk_timer(view, view._timer_id)
    controller = view.model.flight_controller
    reads = controller.master.recv_match.call_count
    assert reads > 0

    resume = pause_polling_plugin_for_recovery(view)

    assert view._timer_id is None
    assert controller.master.recv_match.call_count == reads
    resume()
    assert view._timer_id is not None
    fire_tk_timer(view, view._timer_id)
    assert controller.master.recv_match.call_count > reads


def _label_texts(widget: tk.Misc) -> list[str]:
    texts = [str(widget.cget("text"))] if isinstance(widget, ttk.Label) else []
    for child in widget.winfo_children():
        texts.extend(_label_texts(child))
    return texts


def test_user_sees_exactly_five_channels_rssi_and_receiver_test_instructions(receiver_view: RCReceiverView) -> None:
    """
    Keep receiver checks compact and explain the required user actions.

    GIVEN the receiver plugin is open,
    WHEN the user inspects its controls,
    THEN CH1-CH5 and RSSI appear with upload, movement and transmitter power-off instructions.
    """
    labels = _label_texts(receiver_view)
    assert [label for label in labels if label.startswith("CH")] == [f"CH{channel}" for channel in range(1, 6)]
    assert _("RSSI") in labels
    assert len(receiver_view.channel_bars) == 5
    instructions = str(receiver_view.instructions.cget("text"))
    assert "Upload" in instructions
    assert "first five channels" in instructions
    assert "Power off the RC transmitter" in instructions
    assert "power it back on" in instructions
    assert "parameters on the right" in instructions
    assert not any(isinstance(child, ttk.Button) for child in receiver_view.winfo_children())


def test_live_values_and_unavailable_readings_are_visibly_distinct(receiver_view: RCReceiverView) -> None:
    """
    Display actual PWM and RSSI without inventing missing readings.

    GIVEN receiver telemetry includes values outside the visual span and unavailable channels,
    WHEN the view updates,
    THEN bars clamp to their range, numeric PWM stays accurate and RSSI zero remains visible.
    """
    receiver_view._show_state(
        RCReceiverState(connected=True, channels=(700, 1500, 2300, None, 2000), rssi=0, receiving_channels=True)
    )
    assert [float(channel_bar.cget("value")) for channel_bar in receiver_view.channel_bars] == [0, 700, 1400, 0, 1200]
    assert [str(label.cget("text")) for label in receiver_view.channel_values] == [
        "700 µs",
        "1500 µs",
        "2300 µs",
        _("Unavailable"),
        "2000 µs",
    ]
    assert str(receiver_view.rssi_value.cget("text")) == "0 / 254"
    assert str(receiver_view.input_status.cget("foreground")) == "green"
    receiver_view._show_state(RCReceiverState(connected=True))
    assert all(float(channel_bar.cget("value")) == 0 for channel_bar in receiver_view.channel_bars)
    assert str(receiver_view.rssi_value.cget("text")) == _("Unavailable")
    assert str(receiver_view.input_status.cget("foreground")) == "red"
    assert str(receiver_view.failsafe_status.cget("text")) == _("RC failsafe: unknown (status unavailable).")
    assert str(receiver_view.failsafe_status.cget("foreground")) == "red"


def test_status_messages_occupy_the_space_to_the_right_of_quarter_width_bars(receiver_view: RCReceiverView) -> None:
    """
    Keep receiver status readable beside the compact channel display.

    GIVEN the receiver monitor's channel bars and status messages,
    WHEN the layout allocates horizontal space,
    THEN the bars receive one quarter, with input status first in the right-hand status column.
    """
    labels = [
        receiver_view.input_status,
        receiver_view.receiver_status,
        receiver_view.failsafe_status,
        receiver_view.failsafe_history,
    ]
    status_frame = receiver_view.input_status.master
    assert all(label.master is status_frame for label in labels)
    assert status_frame.pack_slaves() == labels
    status_layout = status_frame.grid_info()
    bars = [*receiver_view.channel_bars, receiver_view.rssi_bar]
    assert all(int(status_layout["column"]) > int(channel_bar.grid_info()["column"]) for channel_bar in bars)
    assert int(status_layout["row"]) == int(bars[0].grid_info()["row"])
    assert int(status_layout["row"]) + int(status_layout["rowspan"]) > int(bars[-1].grid_info()["row"])
    content = status_frame.master
    bar_column = content.grid_columnconfigure(bars[0].grid_info()["column"])
    status_column = content.grid_columnconfigure(status_layout["column"])
    assert bar_column["uniform"] == status_column["uniform"] != ""
    assert bar_column["weight"] / (bar_column["weight"] + status_column["weight"]) == pytest.approx(0.25)


@pytest.mark.parametrize("width", [0, 240, 600])
def test_status_messages_wrap_with_their_column_and_stay_wrapped_after_telemetry(
    receiver_view: RCReceiverView, width: int
) -> None:
    """
    Preserve status text wrapping as the panel resizes and live telemetry arrives.

    GIVEN the right-hand status column changes width,
    WHEN a configure event and then a telemetry refresh occur,
    THEN every status message retains wrapping within the column.
    """
    receiver_view.input_status.master.event_generate("<Configure>", width=width, height=160)
    receiver_view._show_state(RCReceiverState(connected=True, receiver_present=True, failsafe=False))
    for label in (
        receiver_view.input_status,
        receiver_view.receiver_status,
        receiver_view.failsafe_status,
        receiver_view.failsafe_history,
    ):
        assert int(label.cget("wraplength")) == max(1, width)


@pytest.mark.parametrize("failsafe", [None, False, True])
def test_rc_failsafe_and_recovery_have_explicit_text(receiver_view: RCReceiverView, failsafe: bool | None) -> None:
    """
    Expose current RC failsafe independently from prior detection.

    GIVEN failsafe may be active, recovered or unavailable,
    WHEN status is displayed after a detection,
    THEN current status is explicit and the earlier detection remains visible.
    """
    receiver_view._show_state(RCReceiverState(connected=True, failsafe=failsafe, failsafe_detected=True))
    expected = {
        None: _("RC failsafe: unknown (status unavailable)."),
        False: _("RC failsafe: not active."),
        True: _("RC failsafe: DETECTED."),
    }
    assert str(receiver_view.failsafe_status.cget("text")) == expected[failsafe]
    assert str(receiver_view.failsafe_status.cget("foreground")) == ("red" if failsafe is None else "black")
    assert str(receiver_view.failsafe_history.cget("text")) == _("RC failsafe detected during this test.")
    assert str(receiver_view.failsafe_history.cget("foreground")) == "green"


@pytest.mark.parametrize("present", [None, False, True])
def test_receiver_presence_is_not_claimed_without_fc_evidence(receiver_view: RCReceiverView, present: bool | None) -> None:
    """
    Distinguish unknown status, no input yet and detected input.

    GIVEN the FC reports a receiver presence state,
    WHEN it is shown,
    THEN the text preserves the difference between current uncertainty and past detection.
    """
    receiver_view._show_state(RCReceiverState(connected=True, receiver_present=present))
    expected = {
        None: _("Receiver status: unknown."),
        False: _("Receiver: no RC input detected by the flight controller yet."),
        True: _("Receiver: RC input has been detected by the flight controller."),
    }
    assert str(receiver_view.receiver_status.cget("text")) == expected[present]
    expected_color = {None: "red", False: "orange", True: "green"}
    assert str(receiver_view.receiver_status.cget("foreground")) == expected_color[present]


@pytest.mark.parametrize(
    ("state", "expected_color"),
    [
        (RCReceiverState(), "orange"),
        (RCReceiverState(connected=True, receiving_channels=True), "green"),
        (RCReceiverState(connected=True), "red"),
    ],
)
def test_input_status_color_matches_connection_and_channel_data(
    receiver_view: RCReceiverView, state: RCReceiverState, expected_color: str
) -> None:
    """Use clear colors for disconnected, receiving and stale/no channel states."""
    receiver_view._show_state(state)
    assert str(receiver_view.input_status.cget("foreground")) == expected_color


@pytest.mark.parametrize("failsafe_detected", [False, True])
def test_failsafe_history_color_matches_whether_it_was_detected(
    receiver_view: RCReceiverView, failsafe_detected: bool
) -> None:
    """Show a detected failsafe in green and the absence of detection in red."""
    receiver_view._show_state(RCReceiverState(failsafe_detected=failsafe_detected))
    assert str(receiver_view.failsafe_history.cget("foreground")) == ("green" if failsafe_detected else "red")


def test_diagnostics_pause_cancels_polling_and_resumes_once(receiver_view: RCReceiverView) -> None:
    """
    Yield the shared receiver without losing failsafe test evidence.

    GIVEN a pending receiver poll,
    WHEN diagnostics deactivates the view and subsequently activates it twice,
    THEN the old timer is cancelled, live state clears and exactly one timer resumes.
    """
    receiver_view.model._failsafe_detected = True
    old_timer = receiver_view._timer_id
    receiver_view.on_deactivate()
    assert receiver_view._timer_id is None
    pending = receiver_view.tk.call("after", "info")
    assert old_timer not in pending
    assert receiver_view.model._failsafe_detected
    receiver_view.on_activate()
    resumed_timer = receiver_view._timer_id
    receiver_view.on_activate()
    assert receiver_view._timer_id == resumed_timer
    assert resumed_timer is not None


def test_polling_refreshes_status_and_keeps_one_callback(receiver_view: RCReceiverView) -> None:
    """
    Update the monitor periodically without accumulating timers.

    GIVEN a scheduled poll and an FC without messages,
    WHEN the scheduled callback runs,
    THEN waiting guidance is displayed and one future callback is registered.
    """
    old_timer = receiver_view._timer_id
    assert old_timer is not None
    receiver_view.after_cancel(old_timer)
    receiver_view._check_telemetry()
    assert receiver_view._timer_id is not None
    assert receiver_view._timer_id != old_timer
    assert "No current RC channel data" in str(receiver_view.input_status.cget("text"))


def test_view_destruction_cancels_pending_callbacks(receiver_view: RCReceiverView) -> None:
    """
    Release polling when changing configuration steps.

    GIVEN an active receiver view,
    WHEN it is destroyed,
    THEN no receiver callback remains queued.
    """
    timer = receiver_view._timer_id
    receiver_view.destroy()
    assert timer not in receiver_view.tk.call("after", "info")
    assert receiver_view._timer_id is None


@pytest.mark.parametrize("external", [False, True])
@pytest.mark.parametrize("outcome", [True, False, "error"])
def test_upload_yields_receiver_and_restores_navigation(
    receiver_view: RCReceiverView, external: bool, outcome: bool | str
) -> None:
    """
    Give upload and verification exclusive access to telemetry.

    GIVEN an active receiver monitor with failsafe history,
    WHEN an internal or external upload completes, fails, or raises,
    THEN its timer stays cancelled during progress and resumes after cleanup.
    """
    receiver_view.model._failsafe_detected = True
    old_timer = receiver_view._timer_id
    editor = ParameterEditorWindow.__new__(ParameterEditorWindow)
    editor._connection_recovery = None
    editor.root = MagicMock()
    editor.navigation_lock = NavigationLock()
    editor.parameter_editor = MagicMock()
    editor.ui = MagicMock()
    editor.current_plugin_view = receiver_view

    def upload_with_progress(*_args: object) -> bool:
        assert receiver_view._timer_id is None
        assert old_timer not in receiver_view.tk.call("after", "info")
        assert editor.navigation_lock.locked
        # A queued macOS step-change event must not start another receiver.
        editor.on_skip_click()
        editor.parameter_editor.get_next_non_optional_file.assert_not_called()
        if outcome == "error":
            message = "connection lost"
            raise OSError(message)
        return bool(outcome)

    editor.ui.upload_params_with_progress.side_effect = upload_with_progress
    upload = editor.upload_external_params if external else editor.upload_selected_params
    assert upload({}) is (outcome is True)
    assert not editor.navigation_lock.locked
    assert receiver_view._timer_id is not None
    assert receiver_view._timer_id != old_timer
    assert receiver_view.model._failsafe_detected


def test_file_browser_pauses_the_real_receiver_timer_until_closed(receiver_view: RCReceiverView) -> None:
    """
    Leave MAVFTP replies to the file browser while preserving receiver test evidence.

    GIVEN an active receiver monitor with observed failsafe,
    WHEN the file browser opens and later closes,
    THEN polling stops during the browser and resumes once with history intact.
    """
    receiver_view.model.get_receiver_state()
    receiver_view.model._failsafe_detected = True
    old_timer = receiver_view._timer_id
    editor = ParameterEditorWindow.__new__(ParameterEditorWindow)
    editor._connection_recovery = None
    editor.root = MagicMock()
    editor.navigation_lock = MagicMock(locked=False)
    editor.parameter_editor = MagicMock()
    editor.ui = MagicMock()
    editor.current_plugin_view = receiver_view
    with patch("ardupilot_methodic_configurator.frontend_tkinter_parameter_editor.FileBrowserWindow") as browser:
        editor.on_download_bin_logs_click()
        assert receiver_view._timer_id is None
        assert old_timer not in receiver_view.tk.call("after", "info")
        cast("MagicMock", receiver_view.model.flight_controller).request_rc_receiver_messages.assert_called_with(0)
        browser.return_value.set_closed_callback.call_args.args[0]()
    assert receiver_view._timer_id is not None
    assert receiver_view._timer_id != old_timer
    assert receiver_view.model._failsafe_detected


def test_registered_factories_create_real_receiver_view(receiver_view: RCReceiverView) -> None:
    """
    Build receiver views through the normal plugin factory.

    GIVEN the receiver registration function,
    WHEN both registered factories are invoked,
    THEN they construct the receiver model and its actual widgets with the injected FC.
    """
    factory = PluginFactory()
    with patch.object(frontend, "plugin_factory", factory):
        frontend.register_rc_receiver_plugin()
    controller = MagicMock()
    context = PluginModelContext(controller, MagicMock(), MagicMock())
    model = factory.create_model(PLUGIN_RC_RECEIVER, context)
    assert isinstance(model, RCReceiverDataModel)
    assert model.flight_controller is controller
    assert factory.requires_flight_controller(PLUGIN_RC_RECEIVER)
    view = factory.create(PLUGIN_RC_RECEIVER, receiver_view, model, receiver_view.base_window)
    assert isinstance(view, RCReceiverView)
    view.destroy()


def test_startup_registers_receiver_independently() -> None:
    """
    Include the receiver plugin in lazy startup registration.

    GIVEN the application startup registration list,
    WHEN plugins register,
    THEN the receiver registration hook runs once.
    """
    with (
        patch.object(frontend, "register_rc_receiver_plugin") as register,
        patch.object(PluginFactory, "register"),
    ):
        register_plugins()
    register.assert_called_once()


def test_instructions_wrap_to_available_width(receiver_view: RCReceiverView) -> None:
    """
    Keep guidance readable in a narrow plugin panel.

    GIVEN a resized content frame,
    WHEN its configure callback runs,
    THEN instructions wrap within the available width.
    """
    receiver_view._resize_instructions(SimpleNamespace(width=250))
    assert int(receiver_view.instructions.cget("wraplength")) == 238
