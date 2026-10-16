#!/usr/bin/env python3
"""
Data telemetry measurements, message inspection and plugin lifecycle behavior.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import json
import tkinter as tk
from collections.abc import Generator
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import jsonschema
import pytest
from pymavlink.dialects.v20 import ardupilotmega as mavlink
from telemetry_test_helpers import create_telemetry_link, feed

from ardupilot_methodic_configurator import _
from ardupilot_methodic_configurator.__main__ import register_plugins
from ardupilot_methodic_configurator.data_model_data_telemetry import DataTelemetryDataModel
from ardupilot_methodic_configurator.frontend_tkinter_base_window import BaseWindow
from ardupilot_methodic_configurator.frontend_tkinter_mavlink_inspector import MavlinkInspectorWindow
from ardupilot_methodic_configurator.frontend_tkinter_navigation_lock import NavigationLock
from ardupilot_methodic_configurator.frontend_tkinter_parameter_editor import ParameterEditorWindow
from ardupilot_methodic_configurator.plugins import frontend_tkinter_data_telemetry as frontend
from ardupilot_methodic_configurator.plugins.frontend_tkinter_data_telemetry import DataTelemetryView
from ardupilot_methodic_configurator.plugins.plugin_constants import PLUGIN_DATA_TELEMETRY
from ardupilot_methodic_configurator.plugins.plugin_factory import PluginFactory, PluginModelContext

# pylint: disable=protected-access,redefined-outer-name


@pytest.fixture
def telemetry_link() -> SimpleNamespace:
    """Provide an isolated real MAVLink parser with an in-memory transport."""
    return create_telemetry_link()


@pytest.fixture
def telemetry_view(root: tk.Tk, telemetry_link: SimpleNamespace) -> Generator[DataTelemetryView, None, None]:
    """Use real widgets and model, suppressing physical display updates on macOS."""
    with (
        patch("tkinter.Misc.update"),
        patch("tkinter.Misc.update_idletasks"),
        patch("tkinter.Misc.wait_visibility"),
        patch("tkinter.Misc.wait_window"),
        patch.object(tk.Toplevel, "winfo_fpixels", side_effect=tk.TclError("no display")),
    ):
        base_window = MagicMock(spec=BaseWindow)
        base_window.root = root
        base_window.navigation_lock = NavigationLock()
        view = DataTelemetryView(root, DataTelemetryDataModel(telemetry_link.controller), base_window)
        try:
            yield view
        finally:
            view.destroy()


def test_user_sees_testing_guidance_and_unknown_values(telemetry_view: DataTelemetryView) -> None:
    """
    Explain how to check the intended telemetry path and unavailable metrics.

    GIVEN a newly opened telemetry panel without radio reports,
    WHEN the user reads its instructions and measurements,
    THEN bench safety, USB selection, interruption/recovery and upload actions are explained.
    """
    instructions = str(telemetry_view.instructions.cget("text"))
    for phrase in ("propellers removed", "disarmed", "USB", "Interrupt", "restore", "Upload selected params to FC"):
        assert phrase in instructions
    assert all(str(value.cget("text")) == _("Unavailable") for value in telemetry_view.radio_status.values.values())
    assert str(telemetry_view.radio_status.connection_status.cget("text")) == _("Flight controller disconnected.")
    assert len(telemetry_view.radio_status.values["rssi"].grid_info()) == 0
    assert "RADIO or RADIO_STATUS" in str(telemetry_view.radio_status.metrics_note.cget("text"))
    telemetry_view._resize_instructions(SimpleNamespace(width=260))
    assert int(telemetry_view.instructions.cget("wraplength")) == 248


def test_inspector_subapplication_displays_received_packets(
    telemetry_view: DataTelemetryView,
    telemetry_link: SimpleNamespace,
) -> None:
    """
    Inspect real MAVLink packets in the independent sub-application.

    GIVEN the telemetry panel has yielded its receive stream,
    WHEN the inspector polls a real encoded heartbeat,
    THEN its table and field display update and its observer is removed on close.
    """
    telemetry_view.on_suspend()
    inspector = MavlinkInspectorWindow(telemetry_link.controller, telemetry_view.base_window.root)
    try:
        feed(telemetry_link, mavlink.MAVLink_heartbeat_message(2, 3, 0, 0, 3, 3))
        inspector.root.after_cancel(inspector._timer_id)
        inspector._poll()
        assert inspector._timer_id is not None
        identifier = inspector.table.get_children()[0]
        assert inspector.table.item(identifier, "values")[:4] == ("1", "1", "HEARTBEAT", "1")
        inspector.table.selection_set(identifier)
        inspector._show_fields()
        assert "autopilot: 3" in inspector.fields.get("1.0", "end")
        assert len(telemetry_link.master.message_hooks) == 1
    finally:
        inspector.close()
    assert not telemetry_link.master.message_hooks
    telemetry_view.on_resume()


def test_hiding_plugin_releases_hook_and_resumes_once(telemetry_view: DataTelemetryView) -> None:
    """
    Release every resource when diagnostics opens or the configuration step changes.

    GIVEN an active telemetry monitor,
    WHEN deactivated and activated twice,
    THEN the old timer/observer disappear and exactly one new loop resumes.
    """
    telemetry_view.backend.poll()
    timer = telemetry_view._timer_id
    master = telemetry_view.model.flight_controller.master
    telemetry_view.on_deactivate()
    assert timer not in telemetry_view.tk.call("after", "info")
    assert telemetry_view._timer_id is None
    assert not master.message_hooks
    telemetry_view.on_activate()
    resumed = telemetry_view._timer_id
    telemetry_view.on_activate()
    assert resumed == telemetry_view._timer_id
    telemetry_view.destroy()
    assert resumed not in telemetry_view.tk.call("after", "info")


def test_factories_and_startup_register_fc_required_telemetry_plugin(telemetry_view: DataTelemetryView) -> None:
    """
    Use the normal model/view dispatch and independent startup registration.

    GIVEN an isolated plugin factory and application startup,
    WHEN telemetry registers and its factories run,
    THEN real models/views are created with the injected controller and FC requirement.
    """
    factory = PluginFactory()
    with patch.object(frontend, "plugin_factory", factory):
        frontend.register_data_telemetry_plugin()
    controller = telemetry_view.model.flight_controller
    model = factory.create_model(PLUGIN_DATA_TELEMETRY, PluginModelContext(controller, MagicMock(), MagicMock()))
    assert isinstance(model, DataTelemetryDataModel)
    assert model.flight_controller is controller
    assert factory.requires_flight_controller(PLUGIN_DATA_TELEMETRY)
    view = factory.create(PLUGIN_DATA_TELEMETRY, telemetry_view, model, telemetry_view.base_window)
    assert isinstance(view, DataTelemetryView)
    view.destroy()
    with patch.object(frontend, "register_data_telemetry_plugin") as register, patch.object(PluginFactory, "register"):
        register_plugins()
    register.assert_called_once()


@pytest.mark.parametrize("failure", [False, True])
def test_uploads_suspend_monitor_until_replies_are_consumed(telemetry_view: DataTelemetryView, failure: bool) -> None:
    """
    Prevent GUI reentry during uploads from consuming command replies.

    GIVEN a running telemetry monitor and an upload workflow,
    WHEN upload progress processes timers or upload fails,
    THEN the observer and timer stay paused during upload and resume afterward.
    """
    editor = MagicMock(spec=ParameterEditorWindow)
    editor.navigation_lock = NavigationLock()
    editor.current_plugin_view = telemetry_view
    editor.root = telemetry_view.base_window.root
    editor._pause_plugin_receiver = lambda: ParameterEditorWindow._pause_plugin_receiver(editor)
    telemetry_view.backend.poll()
    suspension_states = []

    def upload(*_args: object) -> bool:
        suspension_states.append(
            (telemetry_view._timer_id is None, not telemetry_view.model.flight_controller.master.message_hooks)
        )
        if failure:
            message = "link lost"
            raise OSError(message)
        return True

    editor.ui = MagicMock()
    editor.ui.upload_params_with_progress.side_effect = upload
    assert ParameterEditorWindow._upload_params(editor, {}, MagicMock()) is not failure
    assert suspension_states == [(True, True)]
    assert telemetry_view._timer_id is not None
    assert editor.ui.show_error.called is failure
    if failure:
        assert "link lost" in editor.ui.show_error.call_args.args[1]


@pytest.mark.parametrize("modal", [False, True])
def test_modal_tools_and_locked_operations_keep_their_receive_stream(
    telemetry_view: DataTelemetryView,
    telemetry_link: SimpleNamespace,
    modal: bool,
) -> None:
    """
    Yield polling to modal file browsers and operations holding the navigation lock.

    GIVEN a queued MAVLink packet and another tool owning the connection,
    WHEN the monitor timer runs,
    THEN the queued packet remains available for that tool and monitoring stays scheduled.
    """
    feed(telemetry_link, mavlink.MAVLink_heartbeat_message(2, 3, 0, 0, 3, 3))
    if not modal:
        telemetry_view.base_window.navigation_lock.acquire(object())
    telemetry_view.after_cancel(telemetry_view._timer_id)
    with patch.object(telemetry_view, "grab_current", return_value=telemetry_view if modal else None):
        telemetry_view._check_telemetry()
    assert telemetry_link.master.mav.total_bytes_received == 0
    assert telemetry_view._timer_id is not None
    assert telemetry_link.master.recv_match(blocking=False).get_type() == "HEARTBEAT"


def test_native_message_box_pauses_telemetry_and_monitoring_recovers(
    telemetry_view: DataTelemetryView,
    telemetry_link: SimpleNamespace,
) -> None:
    """
    Keep monitoring scheduled while a native Tk message box holds the grab.

    GIVEN a queued packet and a native dialog without a Python widget,
    WHEN Tkinter cannot resolve the grab owner and the dialog later closes,
    THEN polling waits without consuming the packet and resumes afterward.
    """
    feed(telemetry_link, mavlink.MAVLink_heartbeat_message(2, 3, 0, 0, 3, 3))
    telemetry_view.after_cancel(telemetry_view._timer_id)
    with patch.object(telemetry_view, "grab_current", side_effect=KeyError("__tk__messagebox")):
        telemetry_view._check_telemetry()
    assert telemetry_link.master.mav.total_bytes_received == 0
    assert telemetry_view._timer_id is not None
    assert not telemetry_link.master.message_hooks

    telemetry_view.after_cancel(telemetry_view._timer_id)
    telemetry_view._check_telemetry()
    assert telemetry_link.master.mav.total_bytes_received > 0
    assert telemetry_view._timer_id is not None
    assert len(telemetry_link.master.message_hooks) == 1


@pytest.mark.parametrize("vehicle", ["ArduCopter", "ArduPlane", "Heli", "Rover"])
def test_each_vehicle_has_schema_valid_step_08_telemetry(vehicle: str) -> None:
    """
    Make the protocol-only telemetry monitor available for all bundled vehicle families.

    GIVEN a bundled vehicle configuration and the shared schema,
    WHEN step 08 is loaded,
    THEN the telemetry plugin is selected at the top and the entire configuration is valid.
    """
    package = Path(__file__).resolve().parents[2] / "ardupilot_methodic_configurator"
    config = json.loads((package / f"configuration_steps_{vehicle}.json").read_text(encoding="utf-8"))
    schema = json.loads((package / "configuration_steps_schema.json").read_text(encoding="utf-8"))
    jsonschema.validate(config, schema)
    assert config["steps"]["08_telemetry.param"]["plugin"] == {
        "name": "data_telemetry",
        "placement": "top",
    }
