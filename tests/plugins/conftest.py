#!/usr/bin/env python3
"""
Shared fixtures for staged RC parameter editing.

SPDX-FileCopyrightText: 2026 ArduPilot Contributors
SPDX-License-Identifier: GPL-3.0-or-later
"""

from unittest.mock import MagicMock

import pytest

from ardupilot_methodic_configurator.data_model_ardupilot_parameter import ArduPilotParameter
from ardupilot_methodic_configurator.data_model_par_dict import Par
from ardupilot_methodic_configurator.data_model_parameter_editor import ParameterEditor


@pytest.fixture
def rc_staging_context() -> tuple[MagicMock, ParameterEditor]:
    """Use real parameter objects and editor APIs; mock only filesystem and FC I/O."""
    controller = MagicMock()
    controller.master.recv_match.return_value = None
    controller.fc_parameters = {
        "RCMAP_ROLL": 1.0,
        "RCMAP_PITCH": 2.0,
        "RCMAP_THROTTLE": 3.0,
        "RCMAP_YAW": 4.0,
        "FLTMODE_CH": 5.0,
        "ARMING_RUDDER": 2.0,
    }
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
