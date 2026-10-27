#!/usr/bin/env python3
"""
Verify generic ArduPlane compass templates do not assign hardware-specific IDs.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2026 ArduPilot Methodic Configurator contributors

SPDX-License-Identifier: GPL-3.0-or-later
"""

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from ardupilot_methodic_configurator.backend_filesystem import LocalFilesystem
from ardupilot_methodic_configurator.data_model_configuration_step import ConfigurationStepProcessor
from ardupilot_methodic_configurator.data_model_par_dict import Par, ParDict

PACKAGE_DIR = Path(__file__).resolve().parents[1] / "ardupilot_methodic_configurator"
PLANE_TEMPLATES = PACKAGE_DIR / "vehicle_templates" / "ArduPlane"
STEP_NAME = "19_compass_calibration.param"
COMPASS_ID = 855297


@pytest.mark.parametrize(("template_name", "external"), [("empty_4.7.x", 0), ("normal_plane", 1)])
def test_generic_plane_compass_templates_keep_other_parameters_without_device_id(template_name: str, external: int) -> None:
    """Given a generic Plane template, its compass step has no hardware ID and retains its other settings."""
    lines = (PLANE_TEMPLATES / template_name / STEP_NAME).read_text(encoding="utf-8").splitlines()

    assert lines == [
        f"COMPASS_EXTERNAL,{external}",
        "COMPASS_ORIENT,0",
        "COMPASS_USE2,1",
        "COMPASS_USE3,1",
    ]


@pytest.mark.parametrize("template_name", ["empty_4.7.x", "normal_plane"])
@pytest.mark.parametrize("already_saved", [False, True])
def test_plane_compass_step_imports_or_retains_valid_fc_priority_id(template_name: str, already_saved: bool) -> None:
    """Given a real FC compass ID, the Plane step imports it or retains the existing project value."""
    lines = (PLANE_TEMPLATES / template_name / STEP_NAME).read_text(encoding="utf-8").splitlines()
    saved_parameters = ParDict({name: Par(float(value)) for name, value in (line.split(",") for line in lines)})
    if already_saved:
        saved_parameters["COMPASS_PRIO1_ID"] = Par(float(COMPASS_ID), "Saved FC compass")

    config = json.loads((PACKAGE_DIR / "configuration_steps_ArduPlane.json").read_text(encoding="utf-8"))
    filesystem = MagicMock(spec=LocalFilesystem)
    filesystem.file_parameters = {STEP_NAME: saved_parameters}
    filesystem.configuration_steps = {STEP_NAME: config["steps"][STEP_NAME]}
    filesystem.param_default_dict = {"COMPASS_PRIO1_ID": Par(0.0)}
    filesystem.doc_dict = {}
    filesystem.forced_parameters = {}
    filesystem.derived_parameters = {}
    filesystem.get_eval_variables.return_value = {}
    filesystem.compute_forced_and_derived_parameters.return_value = ("", "")
    filesystem.compute_deletions.return_value = set()

    parameters, errors, _, _, _, _, imported = ConfigurationStepProcessor(filesystem).process_configuration_step(
        STEP_NAME, {"COMPASS_PRIO1_ID": float(COMPASS_ID)}
    )

    assert not errors
    assert parameters["COMPASS_PRIO1_ID"].get_new_value() == COMPASS_ID
    assert imported == (set() if already_saved else {"COMPASS_PRIO1_ID"})
    if already_saved:
        assert parameters["COMPASS_PRIO1_ID"].change_reason == "Saved FC compass"
