#!/usr/bin/env python3

"""
Integration tests for Parameter Save Confirmation workflows.

This file tests the safety mechanism that prevents the backend from
silently overwriting user parameter files when derived parameters are calculated.
It verifies the interaction between the backend calculation and the frontend
confirmation logic.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import os
from unittest.mock import MagicMock, patch

import pytest

from ardupilot_methodic_configurator.backend_filesystem import LocalFilesystem
from ardupilot_methodic_configurator.data_model_par_dict import Par

# pylint: disable=redefined-outer-name


@pytest.fixture
def temp_vehicle_dir(tmp_path) -> str:
    """Create a temporary vehicle directory with a sample parameter file."""
    vehicle_dir = tmp_path / "TestVehicle"
    vehicle_dir.mkdir()

    # Create a real file on disk (The "Snapshot" source)
    # BATT_ARM_VOLT is 1.0 (Value that needs correcting)
    param_file = vehicle_dir / "08_batt1.param"
    param_content = "BATT_ARM_VOLT,1.0\n"
    param_file.write_text(param_content, encoding="utf-8")

    return str(vehicle_dir)


@pytest.fixture
def filesystem_with_derived_logic(temp_vehicle_dir) -> LocalFilesystem:
    """Create a LocalFilesystem instance configured to trigger a derived parameter change."""
    # We suppress FBT003 because this constructor requires boolean flags
    fs = LocalFilesystem(temp_vehicle_dir, "ArduCopter", "4.6.0", False, False)  # noqa: FBT003

    # 1. Load the file from disk into memory
    fs.file_parameters = fs.read_params_from_files()

    # 2. Mock the configuration steps to force a calculation
    # We simulate a step where BATT_ARM_VOLT is calculated to be 11.75
    fs.configuration_steps = {
        "08_batt1.param": {
            "derived": {
                "BATT_ARM_VOLT": "11.75"  # The "Correct" Math value
            }
        }
    }

    # 3. Mock the derived parameters structure that compute_parameters would populate
    fs.derived_parameters = {"08_batt1.param": {"BATT_ARM_VOLT": Par(11.75, "Calculated safe voltage")}}

    # 4. Mock compute_parameters to simply return success
    fs.compute_parameters = MagicMock(return_value="")

    return fs


class TestParameterSafetyChecks:
    """Tests the backend safety logic for parameter updates."""

    def test_backend_detects_conflict_and_blocks_save(self, filesystem_with_derived_logic) -> None:
        """
        Backend detects conflict and blocks save.

        GIVEN: The Math Engine calculates a new value (11.75) that differs from the Disk (1.0)
        WHEN: The update function is called without explicit permission
        THEN: The backend should NOT save the file
        AND: It returns a dictionary identifying the changed file
        """
        fs = filesystem_with_derived_logic

        # WHEN: Call update without permission (commit_derived_changes=False)
        result = fs.update_and_export_vehicle_params_from_fc(
            source_param_values={},
            existing_fc_params=[],
            commit_derived_changes=False,
        )

        # THEN: Result should be a dict (Pending changes), not an empty string (Success)
        assert isinstance(result, dict)
        assert "08_batt1.param" in result

        # AND: Verify the file on disk was NOT touched
        with open(os.path.join(fs.vehicle_dir, "08_batt1.param"), encoding="utf-8") as f:
            content = f.read().strip()
        assert content == "BATT_ARM_VOLT,1.0", "Silent overwrite occurred! The file should still be 1.0"

    def test_backend_saves_when_permission_granted(self, filesystem_with_derived_logic) -> None:
        """
        Backend saves when permission is granted.

        GIVEN: The user has granted permission to save derived changes
        WHEN: The update function is called with commit_derived_changes=True
        THEN: The backend should write the new value (11.75) to disk
        """
        fs = filesystem_with_derived_logic

        # WHEN: Call update WITH permission (commit_derived_changes=True)
        result = fs.update_and_export_vehicle_params_from_fc(
            source_param_values={},
            existing_fc_params=[],
            commit_derived_changes=True,
        )

        # THEN: Result should be empty string (Success)
        assert result == ""

        # AND: Verify the file on disk WAS updated
        with open(os.path.join(fs.vehicle_dir, "08_batt1.param"), encoding="utf-8") as f:
            content = f.read().strip()
        assert "11.75" in content, "File was not updated despite permission granted."

    def test_backend_blocks_save_even_if_memory_is_modified(self, filesystem_with_derived_logic) -> None:
        """
        Backend blocks save even if memory is modified.

        GIVEN: The Component Editor modifies the in-memory value to 15.7
        AND: The Disk is still 1.0
        WHEN: The update function checks for changes
        THEN: It should read the Disk (1.0), compare it to 15.7, and BLOCK the save
        """
        fs = filesystem_with_derived_logic

        # GIVEN: Dirty the memory artificially (Simulating Component Editor)
        fs.file_parameters["08_batt1.param"]["BATT_ARM_VOLT"].value = 15.7
        # Ensure derived param matches the dirty memory to simulate a "Source" update
        fs.derived_parameters["08_batt1.param"]["BATT_ARM_VOLT"].value = 15.7

        # WHEN: Call update without permission
        result = fs.update_and_export_vehicle_params_from_fc(
            source_param_values={},
            existing_fc_params=[],
            commit_derived_changes=False,
        )

        # THEN: It should still detect the change vs Disk
        assert isinstance(result, dict)
        assert "08_batt1.param" in result

        # AND: Disk should still be 1.0
        with open(os.path.join(fs.vehicle_dir, "08_batt1.param"), encoding="utf-8") as f:
            content = f.read().strip()
        assert content == "BATT_ARM_VOLT,1.0"


class TestUserConfirmationWorkflow:
    """Tests the user interaction workflow for confirming changes."""

    @patch("ardupilot_methodic_configurator.__main__.show_confirmation_dialog")
    def test_user_declines_changes_triggers_revert(self, mock_dialog) -> None:
        """
        User declines changes triggers revert.

        GIVEN: The backend detects pending changes
        WHEN: The user clicks 'No' on the confirmation dialog
        THEN: The system should reload parameters from disk to revert memory
        """
        # Import the function to test
        # pylint: disable=import-outside-toplevel
        from ardupilot_methodic_configurator.__main__ import (  # noqa: PLC0415
            process_component_editor_results,
        )

        # GIVEN: Backend returns pending changes
        mock_fs = MagicMock()
        mock_controller = MagicMock()
        mock_project_manager = MagicMock()
        mock_fs.update_and_export_vehicle_params_from_fc.return_value = {"08_batt1.param": True}

        # WHEN: User responds NO
        mock_dialog.return_value = False

        process_component_editor_results(mock_controller, mock_fs, mock_project_manager)

        # THEN: Verify dialog was shown
        mock_dialog.assert_called_once()

        # AND: Verify we did NOT call update again with commit=True
        assert len(mock_fs.update_and_export_vehicle_params_from_fc.call_args_list) == 1
        assert mock_fs.update_and_export_vehicle_params_from_fc.call_args[1]["commit_derived_changes"] is False

        # AND: Verify REVERT: read_params_from_files must be called
        mock_fs.read_params_from_files.assert_called_once()

    @patch("ardupilot_methodic_configurator.__main__.show_confirmation_dialog")
    def test_user_accepts_changes_triggers_save(self, mock_dialog) -> None:
        """
        User accepts changes triggers save.

        GIVEN: The backend detects pending changes
        WHEN: The user clicks 'Yes' on the confirmation dialog
        THEN: The system should call update again with permission to save
        """
        # pylint: disable=import-outside-toplevel
        from ardupilot_methodic_configurator.__main__ import (  # noqa: PLC0415
            process_component_editor_results,
        )

        # GIVEN: Backend returns pending changes first, then success
        mock_fs = MagicMock()
        mock_controller = MagicMock()
        mock_project_manager = MagicMock()
        mock_fs.update_and_export_vehicle_params_from_fc.side_effect = [{"08_batt1.param": True}, ""]

        # WHEN: User responds YES
        mock_dialog.return_value = True
        process_component_editor_results(mock_controller, mock_fs, mock_project_manager)

        # THEN: Verify dialog was shown
        mock_dialog.assert_called_once()

        # AND: Verify update was called TWICE
        assert len(mock_fs.update_and_export_vehicle_params_from_fc.call_args_list) == 2

        # AND: Verify second call had commit=True
        second_call_kwargs = mock_fs.update_and_export_vehicle_params_from_fc.call_args_list[1][1]
        assert second_call_kwargs["commit_derived_changes"] is True

        # AND: Verify we did NOT revert
        mock_fs.read_params_from_files.assert_not_called()
