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
from ardupilot_methodic_configurator.data_model_par_dict import Par, ParDict

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
        pending_changes = fs.update_and_export_vehicle_params_from_fc(
            existing_fc_params=[],
        )

        # THEN: The changed file is reported as pending
        assert "08_batt1.param" in pending_changes

        # AND: The pending value is the newly computed one
        assert pending_changes["08_batt1.param"]["BATT_ARM_VOLT"].value == 11.75

        # AND: The loaded in-memory model was NOT mutated by Phase 1
        assert fs.file_parameters["08_batt1.param"]["BATT_ARM_VOLT"].value == 1.0

        # AND: The file on disk was NOT touched (no silent overwrite)
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

        # WHEN: Call update to detect changes, then save with permission
        pending_changes = fs.update_and_export_vehicle_params_from_fc(
            existing_fc_params=[],
        )

        # Changes detected - simulate user saying Yes: apply then save
        fs.apply_pending_changes(pending_changes)

        # THEN: The in-memory model reflects the derived value
        assert fs.file_parameters["08_batt1.param"]["BATT_ARM_VOLT"].value == 11.75

        # AND: After explicit save, the file on disk is updated
        fs.save_vehicle_params_to_files(list(fs.file_parameters))
        with open(os.path.join(fs.vehicle_dir, "08_batt1.param"), encoding="utf-8") as f:
            content = f.read().strip()
        assert "11.75" in content, "File was not updated despite permission granted."

    def test_backend_detects_comment_only_change(self, temp_vehicle_dir) -> None:
        """
        Backend detects a change in inline comment even when the value is the same.

        GIVEN: The loaded model has BATT_ARM_VOLT=1.0 with no comment
        AND: A derived-parameter computation produces the same value but with a new comment
        WHEN: The update function checks for changes
        THEN: It should detect the comment difference and return the filename as pending
        """
        fs = LocalFilesystem(temp_vehicle_dir, "ArduCopter", "4.6.0", False, False)  # noqa: FBT003
        fs.file_parameters = fs.read_params_from_files()

        # GIVEN: Configure a derived parameter that has the same value but a different comment
        fs.configuration_steps = {
            "08_batt1.param": {
                "derived": {
                    "BATT_ARM_VOLT": "1.0"  # Same value as on disk
                }
            }
        }
        fs.derived_parameters = {"08_batt1.param": {"BATT_ARM_VOLT": Par(1.0, "New change reason")}}
        fs.compute_parameters = MagicMock(return_value="")

        # WHEN
        pending_changes = fs.update_and_export_vehicle_params_from_fc(
            existing_fc_params=[],
        )

        # THEN: Comment change alone triggers the pending flag
        assert "08_batt1.param" in pending_changes

        # AND: The pending change carries the new comment
        assert pending_changes["08_batt1.param"]["BATT_ARM_VOLT"].comment == "New change reason"

        # AND: The loaded in-memory model was NOT mutated by Phase 1
        assert fs.file_parameters["08_batt1.param"]["BATT_ARM_VOLT"].comment is None

        # AND: Disk is unchanged
        with open(os.path.join(fs.vehicle_dir, "08_batt1.param"), encoding="utf-8") as f:
            content = f.read().strip()
        assert content == "BATT_ARM_VOLT,1.0"

    def test_detects_derived_change_even_when_memory_was_already_modified(self, filesystem_with_derived_logic) -> None:
        """
        Derived computation producing a different value is detected even when memory was pre-modified.

        GIVEN: The in-memory model was already modified to 15.7 (e.g. by the Component Editor)
        AND: The derived computation produces 11.75 (different from the pre-modified value)
        WHEN: The update function checks for changes
        THEN: It should detect the difference between the derived value and the loaded state
        AND: The file should appear in pending changes
        """
        fs = filesystem_with_derived_logic

        # GIVEN: Dirty the memory artificially (simulating Component Editor changing the value)
        fs.file_parameters["08_batt1.param"]["BATT_ARM_VOLT"].value = 15.7
        # Derived computation still produces 11.75 (the fixture default)

        # WHEN: Call update
        pending_changes = fs.update_and_export_vehicle_params_from_fc(
            existing_fc_params=[],
        )

        # THEN: Derived value (11.75) differs from loaded value (15.7) → detected
        assert "08_batt1.param" in pending_changes
        assert pending_changes["08_batt1.param"]["BATT_ARM_VOLT"].value == 11.75

        # AND: Phase 1 must not mutate self.file_parameters
        assert fs.file_parameters["08_batt1.param"]["BATT_ARM_VOLT"].value == 15.7


class TestUserConfirmationWorkflow:
    """Tests the user interaction workflow for confirming changes."""

    @patch("ardupilot_methodic_configurator.__main__.ask_yesno_message")
    def test_user_declining_changes_leaves_memory_unchanged(self, mock_dialog) -> None:
        """
        User declining changes leaves memory unchanged.

        GIVEN: The backend detects pending changes
        WHEN: The user clicks 'No' on the confirmation dialog
        THEN: The in-memory model is not mutated (Phase 1 never touched it)
        AND: No disk write occurs
        """
        # Import the function to test
        # pylint: disable=import-outside-toplevel
        from ardupilot_methodic_configurator.__main__ import (  # noqa: PLC0415
            process_component_editor_results,
        )

        # GIVEN: Backend returns pending changes
        mock_fs = MagicMock()
        mock_controller = MagicMock()
        mock_fs.update_and_export_vehicle_params_from_fc.return_value = {"08_batt1.param": MagicMock()}

        # WHEN: User responds NO
        mock_dialog.return_value = False

        process_component_editor_results(mock_controller, mock_fs)

        # THEN: A confirmation dialog was shown
        mock_dialog.assert_called_once()

        # AND: The in-memory model was NOT updated (user said No)
        mock_fs.apply_pending_changes.assert_not_called()

        # AND: No disk write occurred
        mock_fs.save_vehicle_params_to_files.assert_not_called()

    @patch("ardupilot_methodic_configurator.__main__.ask_yesno_message")
    def test_user_accepts_changes_keeps_memory_updated(self, mock_dialog) -> None:
        """
        User accepts changes: derived values stay in memory; no disk write here.

        GIVEN: The backend detects pending changes
        WHEN: The user clicks 'Yes' on the confirmation dialog
        THEN: The derived values remain in the in-memory data model
        AND: No disk write occurs at this stage (the parameter editor handles that per step)
        AND: No revert of in-memory values occurs
        """
        # pylint: disable=import-outside-toplevel
        from ardupilot_methodic_configurator.__main__ import (  # noqa: PLC0415
            process_component_editor_results,
        )

        # GIVEN: Backend returns pending changes
        mock_fs = MagicMock()
        mock_controller = MagicMock()
        mock_fs.update_and_export_vehicle_params_from_fc.return_value = {"08_batt1.param": MagicMock()}

        # WHEN: User responds YES
        mock_dialog.return_value = True
        process_component_editor_results(mock_controller, mock_fs)

        # THEN: A confirmation dialog was shown
        mock_dialog.assert_called_once()

        # AND: The pending changes were applied to the in-memory data model
        pending = mock_fs.update_and_export_vehicle_params_from_fc.return_value
        mock_fs.apply_pending_changes.assert_called_once_with(pending)

        # AND: No disk write at this stage - the parameter editor handles that per step
        mock_fs.save_vehicle_params_to_files.assert_not_called()

    @patch("ardupilot_methodic_configurator.__main__.ask_yesno_message")
    def test_no_pending_changes_does_not_write_to_disk(self, mock_dialog) -> None:
        """
        No pending changes: no disk write and no dialog shown.

        GIVEN: The backend detects no differences between memory and disk
        WHEN: process_component_editor_results is called
        THEN: No confirmation dialog is shown
        AND: No disk write occurs (in-memory model already matches disk)
        AND: No revert occurs
        """
        # pylint: disable=import-outside-toplevel
        from ardupilot_methodic_configurator.__main__ import (  # noqa: PLC0415
            process_component_editor_results,
        )

        mock_fs = MagicMock()
        mock_controller = MagicMock()
        # Empty dict == no changes
        mock_fs.update_and_export_vehicle_params_from_fc.return_value = {}

        process_component_editor_results(mock_controller, mock_fs)

        # THEN: No confirmation dialog was shown
        mock_dialog.assert_not_called()

        # AND: The in-memory model was not touched
        mock_fs.apply_pending_changes.assert_not_called()

        # AND: No disk write occurred
        mock_fs.save_vehicle_params_to_files.assert_not_called()

    @patch("ardupilot_methodic_configurator.__main__.show_error_message")
    @patch("ardupilot_methodic_configurator.__main__.sys_exit")
    def test_value_error_shows_error_dialog_and_exits(self, mock_exit, mock_error_dialog) -> None:
        """
        ValueError from backend shows error dialog and exits.

        GIVEN: The backend raises a ValueError during parameter computation
        WHEN: process_component_editor_results is called
        THEN: An error dialog is shown to the user
        AND: The application exits with code 1
        """
        # pylint: disable=import-outside-toplevel
        from ardupilot_methodic_configurator.__main__ import (  # noqa: PLC0415
            process_component_editor_results,
        )

        mock_fs = MagicMock()
        mock_controller = MagicMock()
        mock_fs.update_and_export_vehicle_params_from_fc.side_effect = ValueError("Compute error in 08_batt1.param")

        process_component_editor_results(mock_controller, mock_fs)

        # THEN: An error dialog was shown with the error message
        mock_error_dialog.assert_called_once()
        dialog_message = str(mock_error_dialog.call_args)
        assert "Compute error in 08_batt1.param" in dialog_message

        # AND: The application exited
        mock_exit.assert_called_once_with(1)

        # AND: No changes were applied to the in-memory model
        mock_fs.apply_pending_changes.assert_not_called()

    @patch("ardupilot_methodic_configurator.__main__.ask_yesno_message")
    def test_multiple_files_pending_lists_all_in_dialog(self, mock_dialog) -> None:
        """
        Multiple pending files are all listed in the confirmation dialog.

        GIVEN: The backend detects changes in two parameter files
        WHEN: The confirmation dialog is shown
        THEN: Both filenames appear in the dialog message
        """
        # pylint: disable=import-outside-toplevel
        from ardupilot_methodic_configurator.__main__ import (  # noqa: PLC0415
            process_component_editor_results,
        )

        mock_fs = MagicMock()
        mock_controller = MagicMock()
        mock_fs.update_and_export_vehicle_params_from_fc.return_value = {
            "08_batt1.param": MagicMock(),
            "12_motor.param": MagicMock(),
        }
        mock_dialog.return_value = True

        process_component_editor_results(mock_controller, mock_fs)

        # THEN: The dialog message mentions both filenames
        dialog_message = str(mock_dialog.call_args)
        assert "08_batt1.param" in dialog_message
        assert "12_motor.param" in dialog_message

        # AND: The pending changes for both files were applied (user said Yes)
        mock_fs.apply_pending_changes.assert_called_once()


class TestParameterChangeDetection:
    """
    Unit tests for ParDict.differs_from().

    These test the comparison method directly because it is a pure function
    with well-defined semantics.  Testing through the full public API would require
    heavyweight filesystem fixtures for each edge-case combination.
    """

    def test_identical_parameters_are_not_flagged(self) -> None:
        """
        Identical parameter sets produce no pending changes.

        GIVEN: Two parameter sets with the same names, values, and comments
        WHEN: Checked for differences
        THEN: No change is reported
        """
        original = ParDict({"P1": Par(1.0, "comment"), "P2": Par(2.0, "")})
        working = ParDict({"P1": Par(1.0, "comment"), "P2": Par(2.0, "")})
        assert working.differs_from(original) is False

    def test_value_change_is_detected(self) -> None:
        """
        A recomputed parameter with a different value is flagged.

        GIVEN: A parameter whose value changed from 1.0 to 99.0
        WHEN: Checked for differences
        THEN: A change is reported
        """
        original = ParDict({"P1": Par(1.0, ""), "P2": Par(2.0, "")})
        working = ParDict({"P1": Par(99.0, ""), "P2": Par(2.0, "")})
        assert working.differs_from(original) is True

    def test_comment_change_is_detected(self) -> None:
        """
        A recomputed parameter with only a different comment is flagged.

        GIVEN: A parameter whose comment changed from "old reason" to "new reason"
        WHEN: Checked for differences
        THEN: A change is reported
        """
        original = ParDict({"P1": Par(1.0, "old reason")})
        working = ParDict({"P1": Par(1.0, "new reason")})
        assert working.differs_from(original) is True

    def test_none_and_empty_comment_are_equivalent(self) -> None:
        """
        A None comment and an empty-string comment do not count as a difference.

        GIVEN: Original has None comment and computed has empty string
        WHEN: Checked for differences
        THEN: No change is reported
        """
        original = ParDict({"P1": Par(1.0, None)})
        working = ParDict({"P1": Par(1.0, "")})
        assert working.differs_from(original) is False

    def test_added_parameter_is_detected(self) -> None:
        """
        A parameter added by the computation is flagged.

        GIVEN: The computed set has an extra parameter not in the original
        WHEN: Checked for differences
        THEN: A change is reported
        """
        original = ParDict({"P1": Par(1.0, "")})
        working = ParDict({"P1": Par(1.0, ""), "P2": Par(2.0, "")})
        assert working.differs_from(original) is True

    def test_removed_parameter_is_detected(self) -> None:
        """
        A parameter present in the original but absent in the computed set is flagged.

        GIVEN: The original has a parameter that is missing from the computed set
        WHEN: Checked for differences
        THEN: A change is reported
        """
        original = ParDict({"P1": Par(1.0, ""), "P2": Par(2.0, "")})
        working = ParDict({"P1": Par(1.0, "")})
        assert working.differs_from(original) is True
