#!/usr/bin/env python3

"""
Behavior tests for the shared standalone parameter application lifecycle.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2026 Amilcar Lucas

SPDX-License-Identifier: GPL-3.0-or-later
"""

import tkinter as tk
from argparse import Namespace
from unittest.mock import MagicMock, patch

import pytest

from ardupilot_methodic_configurator.frontend_tkinter_parameter_application import (
    ParameterApplicationHost,
    create_argument_parser,
    initialize_standalone_parameter_editor,
    run_standalone_parameter_application,
)


@pytest.fixture(name="standalone_args")
def _standalone_args() -> Namespace:
    """Provide the options consumed by both standalone parameter tools."""
    return Namespace(loglevel="INFO", reboot_time=8, baudrate=115200, device="", vehicle_dir="vehicle", vehicle_type="Copter")


def test_user_selects_connection_before_owner_window_is_created(standalone_args: Namespace) -> None:
    """
    Open the connection chooser before the parameter application's Tk owner.

    GIVEN: Automatic port detection found no responsive port
    WHEN: The user connects through the selector
    THEN: The selector runs before the owner exists and the dialog opens with the connected model
    """
    events: list[str] = []
    controller = MagicMock()
    controller.connect.return_value = "No auto-detected ports responded."
    controller.master = None
    owner = MagicMock()
    owner.mainloop.side_effect = lambda: events.append("owner loop")
    selector = MagicMock()

    def select_connection() -> None:
        events.append("selector loop")
        controller.master = object()

    selector.root.mainloop.side_effect = select_connection

    def make_selector(*_args, **_kwargs) -> MagicMock:
        events.append("selector created")
        return selector

    def make_owner(**_kwargs) -> MagicMock:
        events.append("owner created")
        return owner

    editor = MagicMock()
    ui = MagicMock()

    def initialize(root, fc, services) -> MagicMock:
        events.append("model initialized")
        assert (root, fc, services) == (owner, controller, ui)
        return editor

    def open_dialog(root, model, services) -> object:
        events.append("dialog opened")
        assert (root, model, services) == (owner, editor, ui)
        return object()

    with patch(
        "ardupilot_methodic_configurator.frontend_tkinter_parameter_editor.ParameterEditorUiServices.default",
        return_value=ui,
    ):
        run_standalone_parameter_application(
            standalone_args,
            initialize,
            open_dialog,
            root_factory=make_owner,
            flight_controller_factory=lambda **_kwargs: controller,
            connection_selection_window_factory=make_selector,
        )

    assert events == ["selector created", "selector loop", "owner created", "model initialized", "dialog opened", "owner loop"]
    owner.deiconify.assert_called_once_with()
    owner.withdraw.assert_called_once_with()
    controller.disconnect.assert_called_once_with()
    owner.destroy.assert_called_once_with()


@pytest.mark.parametrize("device", ["/dev/ttyUSB0", ""])
def test_connection_error_stops_before_creating_owner(standalone_args: Namespace, device: str) -> None:
    """
    Report connection failures without opening the parameter window.

    GIVEN: An explicit port fails or automatic detection reports a non-selector error
    WHEN: The standalone tool starts
    THEN: It reports the error and releases the controller without creating Tk
    """
    standalone_args.device = device
    controller = MagicMock()
    controller.connect.return_value = "Connection refused"
    make_owner = MagicMock()
    make_selector = MagicMock()
    show_error = MagicMock()

    run_standalone_parameter_application(
        standalone_args,
        MagicMock(),
        MagicMock(),
        root_factory=make_owner,
        flight_controller_factory=lambda **_kwargs: controller,
        connection_selection_window_factory=make_selector,
        error_popup=show_error,
    )

    assert show_error.call_args.args == ("Flight-controller connection error", "Connection refused")
    make_owner.assert_not_called()
    make_selector.assert_not_called()
    controller.disconnect.assert_called_once_with()


def test_cancelling_connection_selector_does_not_create_owner(standalone_args: Namespace) -> None:
    """
    Cancel connection selection cleanly.

    GIVEN: Automatic detection failed
    WHEN: The user closes the connection selector without connecting
    THEN: No owner or parameter dialog is created and the controller is released
    """
    controller = MagicMock()
    controller.connect.return_value = "No auto-detected ports responded."
    controller.master = None
    selector = MagicMock()
    make_owner = MagicMock()
    initialize = MagicMock()

    run_standalone_parameter_application(
        standalone_args,
        initialize,
        MagicMock(),
        root_factory=make_owner,
        flight_controller_factory=lambda **_kwargs: controller,
        connection_selection_window_factory=lambda *_args, **_kwargs: selector,
    )

    selector.root.mainloop.assert_called_once_with()
    make_owner.assert_not_called()
    initialize.assert_not_called()
    controller.disconnect.assert_called_once_with()


@pytest.mark.parametrize("stop_at", ["model cancellation", "dialog cancellation", "dialog error", "event loop error"])
def test_standalone_releases_controller_and_owner_on_exit(standalone_args: Namespace, stop_at: str) -> None:
    """
    Release application resources for cancellation and errors.

    GIVEN: A connected flight controller and an owner window
    WHEN: setup is cancelled or a dialog/event-loop error occurs
    THEN: Both the connection and the owner window are released
    """
    controller = MagicMock()
    controller.connect.return_value = ""
    owner = MagicMock()
    ui = MagicMock()
    editor = MagicMock()
    initialize = MagicMock(return_value=None if stop_at == "model cancellation" else editor)
    open_dialog = MagicMock(return_value=False if stop_at == "dialog cancellation" else object())
    if stop_at == "dialog error":
        open_dialog.side_effect = RuntimeError("dialog failed")
    if stop_at == "event loop error":
        owner.mainloop.side_effect = RuntimeError("event loop failed")

    with patch(
        "ardupilot_methodic_configurator.frontend_tkinter_parameter_editor.ParameterEditorUiServices.default",
        return_value=ui,
    ):
        if stop_at.endswith("error"):
            with pytest.raises(RuntimeError):
                run_standalone_parameter_application(
                    standalone_args,
                    initialize,
                    open_dialog,
                    root_factory=lambda **_kwargs: owner,
                    flight_controller_factory=lambda **_kwargs: controller,
                )
        else:
            run_standalone_parameter_application(
                standalone_args,
                initialize,
                open_dialog,
                root_factory=lambda **_kwargs: owner,
                flight_controller_factory=lambda **_kwargs: controller,
            )

    controller.disconnect.assert_called_once_with()
    owner.destroy.assert_called_once_with()
    if stop_at == "model cancellation":
        open_dialog.assert_not_called()
        owner.withdraw.assert_not_called()
    elif stop_at == "dialog cancellation":
        owner.mainloop.assert_not_called()


@pytest.mark.parametrize("error", [OSError("metadata unavailable"), ValueError("bad firmware"), SystemExit("invalid pdef")])
def test_metadata_setup_failure_is_reported_without_opening_dialog(standalone_args: Namespace, error: Exception) -> None:
    """
    Report metadata setup failures through the UI service.

    GIVEN: The connected controller's metadata cannot be loaded
    WHEN: The standalone editor is initialized
    THEN: The caller receives no model and sees the specific failure
    """
    controller = MagicMock()
    ui = MagicMock()
    with patch(
        "ardupilot_methodic_configurator.frontend_tkinter_parameter_application."
        "ParameterEditor.for_connected_flight_controller",
        side_effect=error,
    ):
        result = initialize_standalone_parameter_editor(standalone_args, controller, ui)

    assert result is None
    assert ui.show_error.call_args.args == ("Flight-controller parameter setup error", str(error))


def test_embedded_host_notifies_owner_when_dialog_closes() -> None:
    """
    Preserve the embedded caller's close callback.

    GIVEN: An export dialog has an application-owned parent
    WHEN: The dialog signals that it has closed
    THEN: The parent callback runs once
    """
    on_close = MagicMock()
    host = ParameterApplicationHost(MagicMock(), MagicMock(), MagicMock(), gui_complexity="normal", on_close=on_close)

    host.repopulate_parameter_table()
    host.on_skip_click()

    assert host.gui_complexity == "normal"
    on_close.assert_called_once_with()


def test_cleanup_tolerates_owner_that_was_already_destroyed(standalone_args: Namespace) -> None:
    """
    Keep cleanup safe when a dialog has already destroyed the Tk owner.

    GIVEN: A connected controller whose dialog closes the owner
    WHEN: the shared application exits
    THEN: the controller is disconnected despite Tk reporting a destroyed owner
    """
    controller = MagicMock()
    controller.connect.return_value = ""
    owner = MagicMock()
    owner.destroy.side_effect = tk.TclError("application has been destroyed")
    with patch(
        "ardupilot_methodic_configurator.frontend_tkinter_parameter_editor.ParameterEditorUiServices.default",
        return_value=MagicMock(),
    ):
        run_standalone_parameter_application(
            standalone_args,
            lambda *_args: MagicMock(),
            lambda *_args: object(),
            root_factory=lambda **_kwargs: owner,
            flight_controller_factory=lambda **_kwargs: controller,
        )

    controller.disconnect.assert_called_once_with()
    owner.destroy.assert_called_once_with()


def test_connected_editor_uses_vehicle_options_from_standalone_arguments(standalone_args: Namespace) -> None:
    """
    Pass connected vehicle options to the model factory.

    GIVEN: A flight controller connection and selected vehicle options
    WHEN: A standalone parameter tool initializes its editor
    THEN: The model factory receives the connection and matching metadata options
    """
    controller = MagicMock()
    editor = MagicMock()
    ui = MagicMock()
    with patch(
        "ardupilot_methodic_configurator.frontend_tkinter_parameter_application."
        "ParameterEditor.for_connected_flight_controller",
        return_value=editor,
    ) as create_editor:
        result = initialize_standalone_parameter_editor(standalone_args, controller, ui)

    assert result is editor
    create_editor.assert_called_once_with(controller, "vehicle", "Copter")
    ui.show_error.assert_not_called()


def test_embedded_host_uses_saved_complexity_when_no_override_is_given() -> None:
    """
    Use the user's saved complexity for embedded parameter tables.

    GIVEN: An application host without an explicit complexity override
    WHEN: A parameter dialog is opened
    THEN: It uses the saved display setting
    """
    with patch(
        "ardupilot_methodic_configurator.frontend_tkinter_parameter_application.ProgramSettings.get_setting",
        return_value="simple",
    ):
        host = ParameterApplicationHost(MagicMock(), MagicMock(), MagicMock())

    assert host.gui_complexity == "simple"


def test_standalone_parser_exposes_connection_and_vehicle_options(capsys) -> None:
    """
    Offer the common connection and vehicle options to both standalone tools.

    GIVEN: A standalone parameter command
    WHEN: The user requests its help
    THEN: The shared parser shows connection and vehicle configuration options
    """
    parser = create_argument_parser("Standalone parameter tool")

    with pytest.raises(SystemExit) as exit_info:
        parser.parse_args(["--help"])

    assert exit_info.value.code == 0
    help_text = capsys.readouterr().out
    assert "Standalone parameter tool" in help_text
    assert "--device" in help_text
    assert "--vehicle-dir" in help_text
