#!/usr/bin/env python3

"""
Tests for external parameter upload selection rules.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2026 Amilcar Lucas

SPDX-License-Identifier: GPL-3.0-or-later
"""

from unittest.mock import MagicMock

from ardupilot_methodic_configurator.data_model_ardupilot_parameter import ArduPilotParameter
from ardupilot_methodic_configurator.data_model_par_dict import Par
from ardupilot_methodic_configurator.data_model_parameter_compare_and_upload import (
    confirm_external_upload_selection,
    refresh_external_fc_values,
    selected_external_parameters,
    unselected_manual_edits,
)


def test_external_upload_selection_excludes_read_only_values_and_warns_about_omitted_manual_edits() -> None:
    edited = ArduPilotParameter("EDITED", Par(0.1), fc_value=0.0)
    edited.set_new_value("0.2")
    read_only = ArduPilotParameter("READONLY", Par(1.0), metadata={"ReadOnly": True}, fc_value=1.0)
    parameters = {"EDITED": edited, "READONLY": read_only}
    warning = MagicMock()

    assert selected_external_parameters(parameters, ["EDITED", "READONLY"]) == {"EDITED": edited}
    assert unselected_manual_edits(parameters, ["EDITED"], []) == ["EDITED"]
    assert not confirm_external_upload_selection(["EDITED"], warning)
    warning.assert_called_once()
    assert "EDITED" in warning.call_args.args[1]


def test_verified_upload_refreshes_external_snapshot() -> None:
    parameter = ArduPilotParameter("ROLL_P", Par(0.2), fc_value=0.1)

    refresh_external_fc_values({"ROLL_P": parameter}, {"ROLL_P": 0.2})

    assert parameter.fc_value_as_string == "0.2"
    assert not parameter.is_different_from_fc


def test_user_is_warned_only_for_dirty_unselected_edits_that_differ_from_fc() -> None:
    """
    Warn only about manual changes that the upload would leave behind.

    GIVEN: Dirty, unchanged, selected, and absent manual-edit candidates
    WHEN: The model evaluates the upload selection
    THEN: Only a dirty, different, unselected parameter is reported
    """
    omitted = ArduPilotParameter("OMITTED", Par(0.1), fc_value=0.0)
    omitted.set_new_value("0.2")
    selected = ArduPilotParameter("SELECTED", Par(0.1), fc_value=0.0)
    selected.set_new_value("0.2")
    unchanged = ArduPilotParameter("UNCHANGED", Par(0.1), fc_value=0.2)
    unchanged.set_new_value("0.2")
    unedited = ArduPilotParameter("UNEDITED", Par(0.1), fc_value=0.0)
    parameters = {p.name: p for p in (omitted, selected, unchanged, unedited)}

    result = unselected_manual_edits(parameters, [*parameters, "ABSENT"], ["SELECTED"])

    assert result == ["OMITTED"]


def test_user_can_continue_when_no_manual_edits_are_omitted() -> None:
    """
    Continue without warning when the external upload selection is complete.

    GIVEN: No changed manual edits were omitted
    WHEN: The user starts an upload
    THEN: Validation succeeds without showing a warning
    """
    warning = MagicMock()

    assert confirm_external_upload_selection([], warning)
    warning.assert_not_called()


def test_refresh_keeps_values_for_parameters_missing_from_fc_reply() -> None:
    """
    Preserve the preview value when the FC did not return a parameter.

    GIVEN: A parameter absent from the verified FC upload reply
    WHEN: The preview snapshot is refreshed
    THEN: Its previous FC value remains available for comparison
    """
    parameter = ArduPilotParameter("ROLL_P", Par(0.2), fc_value=0.1)

    refresh_external_fc_values({"ROLL_P": parameter}, {})

    assert parameter.fc_value_as_string == "0.1"
