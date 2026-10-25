#!/usr/bin/env python3
"""
Shared fixtures for plugin recovery lifecycles and staged RC parameter editing.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import tkinter as tk
from collections.abc import Callable
from typing import TYPE_CHECKING, cast
from unittest.mock import MagicMock

import pytest

from ardupilot_methodic_configurator.data_model_ardupilot_parameter import ArduPilotParameter
from ardupilot_methodic_configurator.data_model_par_dict import Par
from ardupilot_methodic_configurator.data_model_parameter_editor import ParameterEditor
from ardupilot_methodic_configurator.frontend_tkinter_parameter_editor import ParameterEditorWindow

if TYPE_CHECKING:
    from ardupilot_methodic_configurator.plugins.plugin_protocol import PluginView


@pytest.fixture
def pause_polling_plugin_for_recovery() -> Callable[[tk.Misc], Callable[[], None]]:
    """Exercise the real editor gate and require cancellation of every view-owned Tk timer."""

    def pause(view: tk.Misc) -> Callable[[], None]:
        editor = object.__new__(ParameterEditorWindow)
        editor.current_plugin_view = cast("PluginView", view)
        editor.root = view.winfo_toplevel()
        resume = editor._pause_connection_plugin()  # pylint: disable=protected-access
        assert callable(resume)
        for timer_id in view.tk.call("after", "info"):
            command = view.tk.call("after", "info", timer_id)[0]
            assert command not in (view._tclCommands or [])  # pylint: disable=protected-access
        return resume

    return pause


@pytest.fixture
def fire_tk_timer() -> Callable[[tk.Misc, str], None]:
    """Run one real scheduled callback deterministically without rendering a Tk event loop."""

    def fire(view: tk.Misc, timer_id: str) -> None:
        command = view.tk.call("after", "info", timer_id)[0]
        view.tk.call("after", "cancel", timer_id)
        view.tk.eval(command)

    return fire


@pytest.fixture
def rc_staging_context() -> tuple[MagicMock, ParameterEditor]:
    """Use real parameter objects and editor APIs; mock only filesystem and FC I/O."""
    controller = MagicMock()
    controller.master.recv_match.return_value = None
    # pylint: disable=duplicate-code
    controller.fc_parameters = {
        "RCMAP_ROLL": 1.0,
        "RCMAP_PITCH": 2.0,
        "RCMAP_THROTTLE": 3.0,
        "RCMAP_YAW": 4.0,
        "FLTMODE_CH": 5.0,
        "ARMING_RUDDER": 2.0,
    }
    # pylint: enable=duplicate-code
    for channel in range(1, 17):
        for suffix, value in (("MIN", 1000.0), ("MAX", 2000.0), ("TRIM", 1500.0)):
            controller.fc_parameters[f"RC{channel}_{suffix}"] = value
        controller.fc_parameters[f"RC{channel}_OPTION"] = 0.0
    filesystem = MagicMock()
    filesystem.get_eval_variables.return_value = {}
    option_choices = {"0": "Disabled", "6": "AutoTune", "17": "AutoTune", "300": "QuickTune"}
    filesystem.doc_dict = {f"RC{channel}_OPTION": {"values": option_choices} for channel in range(1, 17)}
    filesystem.param_default_dict = {}
    filesystem.file_parameters = {}
    filesystem.forced_parameters = {}
    filesystem.derived_parameters = {}
    editor = ParameterEditor("07_remote_controller_controller.param", controller, filesystem)
    editor.current_step_parameters = {
        name: ArduPilotParameter(
            name,
            Par(value, "Existing reason"),
            metadata={"values": option_choices} if name.endswith("_OPTION") else None,
            fc_value=value,
        )
        for name, value in controller.fc_parameters.items()
        if name != "RC11_OPTION"
    }
    return controller, editor
