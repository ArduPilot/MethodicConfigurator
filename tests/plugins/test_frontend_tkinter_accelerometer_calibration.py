#!/usr/bin/env python3

"""
Behavior-driven tests for the accelerometer calibration Tkinter frontend.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2026 ArduPilot Contributors

SPDX-License-Identifier: GPL-3.0-or-later
"""

from __future__ import annotations

from tkinter import ttk
from types import SimpleNamespace
from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest
from pymavlink import mavutil

from ardupilot_methodic_configurator.data_model_ardupilot_parameter import ArduPilotParameter
from ardupilot_methodic_configurator.data_model_par_dict import Par, ParDict
from ardupilot_methodic_configurator.data_model_parameter_editor import ParameterEditor
from ardupilot_methodic_configurator.plugins.data_model_accelerometer_calibration import AccelerometerCalibrationDataModel
from ardupilot_methodic_configurator.plugins.frontend_tkinter_accelerometer_calibration import (
    AccelerometerCalibrationView,
    _accel_calibration_names,
    _create_accelerometer_calibration_view,
)

if TYPE_CHECKING:
    from collections.abc import Generator

# pylint: disable=protected-access,redefined-outer-name

_FRONTEND = "ardupilot_methodic_configurator.plugins.frontend_tkinter_accelerometer_calibration"


def test_simple_calibration_copy_set_includes_trim_and_all_imu_naming_schemes() -> None:
    """Simple calibration writes trims and both legacy and newer IMU parameter names."""
    parameters = {
        "INS_ACCOFFS_X",
        "INS_ACC2SCAL_Y",
        "INS4_ACCOFFS_X",
        "INS5_ACCSCAL_Z",
        "AHRS_TRIM_X",
        "AHRS_TRIM_Y",
        "INS_ACCEL_FILTER",
        "AHRS_TRIM_LIMIT",
    }

    assert _accel_calibration_names(parameters) == {
        "INS_ACCOFFS_X",
        "INS_ACC2SCAL_Y",
        "INS4_ACCOFFS_X",
        "INS5_ACCSCAL_Z",
        "AHRS_TRIM_X",
        "AHRS_TRIM_Y",
    }


def test_failed_simple_ack_reads_back_accel_without_a_display(mocker) -> None:
    """A lost simple-calibration ACK must still refresh changed values."""
    view = object.__new__(AccelerometerCalibrationView)
    view.model = MagicMock(spec=AccelerometerCalibrationDataModel)
    view.model.start_simple_calibration.return_value = (False, "Acknowledgment timed out")
    view.model.is_connected.return_value = True
    editor = SimpleNamespace(
        fc_parameters={"INS_ACCOFFS_X": 0.1},
        current_step_parameters={"INS_ACCOFFS_X": MagicMock()},
        update_parameters_from_fc_values=MagicMock(),
        find_other_steps_with_stale_calibration_values=MagicMock(return_value=["other.param"]),
    )
    view.base_window = SimpleNamespace(parameter_editor=editor, repopulate_parameter_table=MagicMock())

    def download(*, redownload: bool, response_timeout: float) -> None:
        assert redownload
        assert response_timeout == 2.0
        editor.fc_parameters["INS_ACCOFFS_X"] = 0.2

    view.base_window.download_flight_controller_parameters = MagicMock(side_effect=download)
    showerror = mocker.patch(f"{_FRONTEND}.showerror")

    view._on_simple_calibration()

    editor.update_parameters_from_fc_values.assert_called_once_with({"INS_ACCOFFS_X": 0.2})
    assert "INS_ACCOFFS_X" in showerror.call_args.args[1]
    assert "other.param" in showerror.call_args.args[1]


def test_rejected_simple_calibration_preserves_staged_values_without_a_display(mocker) -> None:
    """A rejected command preserves staged offsets and filter frequency."""
    view = object.__new__(AccelerometerCalibrationView)
    view.model = MagicMock(spec=AccelerometerCalibrationDataModel)
    view.model.start_simple_calibration.return_value = (False, "Command failed")
    view.model.is_connected.return_value = True
    editor = SimpleNamespace(
        fc_parameters={"INS_ACCOFFS_X": 0.1, "INS_ACCEL_FILTER": 20.0},
        current_step_parameters={"INS_ACCOFFS_X": MagicMock(), "INS_ACCEL_FILTER": MagicMock()},
        update_parameters_from_fc_values=MagicMock(),
    )
    view.base_window = SimpleNamespace(
        parameter_editor=editor,
        download_flight_controller_parameters=MagicMock(),
        repopulate_parameter_table=MagicMock(),
    )
    mocker.patch(f"{_FRONTEND}.showerror")

    view._on_simple_calibration()

    editor.update_parameters_from_fc_values.assert_not_called()


def test_successful_simple_calibration_stages_only_offsets_without_a_display(mocker) -> None:
    """A successful command stages offset results and reports stale steps."""
    view = object.__new__(AccelerometerCalibrationView)
    view.model = MagicMock(spec=AccelerometerCalibrationDataModel)
    view.model.start_simple_calibration.return_value = (True, "Calibration successful")
    editor = SimpleNamespace(
        fc_parameters={"INS_ACCOFFS_X": 0.2, "INS_ACCEL_FILTER": 20.0},
        current_step_parameters={"INS_ACCOFFS_X": MagicMock(), "INS_ACCEL_FILTER": MagicMock()},
        update_parameters_from_fc_values=MagicMock(),
        find_other_steps_with_stale_calibration_values=MagicMock(return_value=["other.param"]),
    )
    view.base_window = SimpleNamespace(
        parameter_editor=editor,
        download_flight_controller_parameters=MagicMock(),
        repopulate_parameter_table=MagicMock(),
    )
    showinfo = mocker.patch(f"{_FRONTEND}.showinfo")

    view._on_simple_calibration()

    editor.update_parameters_from_fc_values.assert_called_once_with({"INS_ACCOFFS_X": 0.2})
    assert "other.param" in showinfo.call_args.args[1]


def test_unavailable_simple_calibration_readback_warns_without_a_display(mocker) -> None:
    """A failed parameter download must be visible alongside an uncertain ACK."""
    view = object.__new__(AccelerometerCalibrationView)
    view.model = MagicMock(spec=AccelerometerCalibrationDataModel)
    view.model.start_simple_calibration.return_value = (False, "Acknowledgment timed out")
    view.model.is_connected.return_value = True
    editor = SimpleNamespace(
        fc_parameters={"INS_ACCOFFS_X": 0.1},
        current_step_parameters={"INS_ACCOFFS_X": MagicMock()},
        update_parameters_from_fc_values=MagicMock(),
    )
    view.base_window = SimpleNamespace(
        parameter_editor=editor,
        download_flight_controller_parameters=MagicMock(return_value=({}, {})),
        repopulate_parameter_table=MagicMock(),
    )
    showerror = mocker.patch(f"{_FRONTEND}.showerror")

    view._on_simple_calibration()

    assert "could not confirm" in showerror.call_args.args[1].lower()
    editor.update_parameters_from_fc_values.assert_not_called()


def test_success_without_parameter_download_keeps_staged_values_without_a_display(mocker) -> None:
    """An accepted command alone does not prove the cached values are new."""
    view = object.__new__(AccelerometerCalibrationView)
    view.model = MagicMock(spec=AccelerometerCalibrationDataModel)
    view.model.start_simple_calibration.return_value = (True, "Calibration successful")
    editor = SimpleNamespace(
        fc_parameters={"INS_ACCOFFS_X": 0.1},
        current_step_parameters={"INS_ACCOFFS_X": MagicMock()},
        update_parameters_from_fc_values=MagicMock(),
    )
    view.base_window = SimpleNamespace(
        parameter_editor=editor,
        download_flight_controller_parameters=MagicMock(return_value=({}, {})),
        repopulate_parameter_table=MagicMock(),
    )
    showinfo = mocker.patch(f"{_FRONTEND}.showinfo")

    view._on_simple_calibration()

    editor.update_parameters_from_fc_values.assert_not_called()
    assert "could not download" in showinfo.call_args.args[1].lower()


@pytest.fixture
def view_with_model(tk_root, mocker) -> Generator[SimpleNamespace, None, None]:
    """
    Fixture building a real view backed by a mock data model.

    The tkinter ``after``/``after_cancel`` scheduling is neutralised so the
    polling loop can be driven deterministically from the tests, and the
    blocking message boxes are patched so no dialog is ever shown.
    """
    model = MagicMock(spec=AccelerometerCalibrationDataModel)
    parent = ttk.Frame(tk_root)
    base_window = SimpleNamespace(
        root=tk_root,
        download_flight_controller_parameters=MagicMock(),
        parameter_editor=SimpleNamespace(fc_parameters={}, update_parameters_from_fc_values=MagicMock()),
        repopulate_parameter_table=MagicMock(),
    )
    view = AccelerometerCalibrationView(parent, model, base_window)
    mocker.patch.object(view, "after", return_value="after-id")
    mocker.patch.object(view, "after_cancel")
    showinfo = mocker.patch(f"{_FRONTEND}.showinfo")
    showerror = mocker.patch(f"{_FRONTEND}.showerror")
    try:
        yield SimpleNamespace(view=view, model=model, base_window=base_window, showinfo=showinfo, showerror=showerror)
    finally:
        parent.destroy()


class TestSimpleCalibrationButton:
    """Test the always-visible simple calibration button."""

    def test_simple_calibration_success_shows_result_dialog(self, view_with_model) -> None:
        """
        A successful simple calibration informs the user with a result dialog.

        GIVEN: The data model reports a successful simple calibration
        WHEN: The user clicks Simple Calibration
        THEN: An informational result dialog is shown and no error is raised
        """
        view_with_model.model.start_simple_calibration.return_value = (True, "Calibration successful")

        view_with_model.view._on_simple_calibration()

        view_with_model.showinfo.assert_called_once()
        assert view_with_model.showinfo.call_args.args[1] == "Calibration successful"
        view_with_model.showerror.assert_not_called()
        view_with_model.base_window.download_flight_controller_parameters.assert_called_once_with(redownload=True)
        view_with_model.base_window.parameter_editor.update_parameters_from_fc_values.assert_not_called()
        view_with_model.base_window.repopulate_parameter_table.assert_called_once_with()

    def test_simple_calibration_failure_shows_error_dialog(self, view_with_model) -> None:
        """
        A failed simple calibration warns the user with an error dialog.

        GIVEN: The data model reports a failed simple calibration
        WHEN: The user clicks Simple Calibration
        THEN: An error dialog is shown and no result dialog is raised
        """
        view_with_model.model.start_simple_calibration.return_value = (False, "not connected")
        view_with_model.model.is_connected.return_value = False

        view_with_model.view._on_simple_calibration()

        view_with_model.showerror.assert_called_once()
        assert view_with_model.showerror.call_args.args[1] == "not connected"
        view_with_model.showinfo.assert_not_called()

    def test_failed_simple_calibration_reads_back_saved_accel_values(self, view_with_model) -> None:
        """A missing ACK can follow a saved calibration, so read back connected vehicles."""
        fixture = view_with_model
        fixture.model.start_simple_calibration.return_value = (False, "Acknowledgment timed out")
        fixture.model.is_connected.return_value = True
        editor = fixture.base_window.parameter_editor
        editor.fc_parameters = {"INS_ACCOFFS_X": 0.1}
        editor.current_step_parameters = {"INS_ACCOFFS_X": MagicMock()}

        def download(*, redownload: bool, response_timeout: float) -> None:
            assert redownload
            assert response_timeout == 2.0
            editor.fc_parameters["INS_ACCOFFS_X"] = 0.2

        fixture.base_window.download_flight_controller_parameters.side_effect = download
        fixture.view._on_simple_calibration()

        editor.update_parameters_from_fc_values.assert_called_once_with({"INS_ACCOFFS_X": 0.2})
        assert "INS_ACCOFFS_X" in fixture.showerror.call_args.args[1]

    def test_rejected_calibration_preserves_staged_edits(self, view_with_model) -> None:
        """An unchanged calibration result must not replace any staged value."""
        fixture = view_with_model
        fixture.model.start_simple_calibration.return_value = (False, "Command failed")
        fixture.model.is_connected.return_value = True
        editor = fixture.base_window.parameter_editor
        editor.fc_parameters = {"INS_ACCOFFS_X": 0.1, "INS_ACCEL_FILTER": 20.0}
        editor.current_step_parameters = {name: MagicMock() for name in editor.fc_parameters}

        fixture.view._on_simple_calibration()

        editor.update_parameters_from_fc_values.assert_not_called()
        assert fixture.showerror.call_args.args[1] == "Command failed"

    def test_success_copies_calibration_values_and_reports_stale_steps(self, view_with_model) -> None:
        """Successful calibration stages actual offsets and identifies stale steps."""
        fixture = view_with_model
        fixture.model.start_simple_calibration.return_value = (True, "Calibration successful")
        editor = fixture.base_window.parameter_editor
        editor.fc_parameters = {"INS_ACCOFFS_X": 0.2, "INS_ACCEL_FILTER": 20.0}
        editor.current_step_parameters = {name: MagicMock() for name in editor.fc_parameters}
        editor.find_other_steps_with_stale_calibration_values = MagicMock(return_value=["other.param"])

        fixture.view._on_simple_calibration()

        editor.update_parameters_from_fc_values.assert_called_once_with({"INS_ACCOFFS_X": 0.2})
        editor.find_other_steps_with_stale_calibration_values.assert_called_once_with({"INS_ACCOFFS_X": 0.2})
        assert "other.param" in fixture.showinfo.call_args.args[1]

    def test_failed_ack_reports_other_stale_steps(self, view_with_model) -> None:
        """A saved offset after a lost ACK identifies other steps that need review."""
        fixture = view_with_model
        fixture.model.start_simple_calibration.return_value = (False, "Acknowledgment timed out")
        fixture.model.is_connected.return_value = True
        editor = fixture.base_window.parameter_editor
        editor.fc_parameters = {"INS_ACCOFFS_X": 0.1}
        editor.current_step_parameters = {"INS_ACCOFFS_X": MagicMock()}
        editor.find_other_steps_with_stale_calibration_values = MagicMock(return_value=["other.param"])

        def download(*, redownload: bool, response_timeout: float) -> None:
            assert redownload
            assert response_timeout == 2.0
            editor.fc_parameters["INS_ACCOFFS_X"] = 0.2

        fixture.base_window.download_flight_controller_parameters.side_effect = download

        fixture.view._on_simple_calibration()

        assert "other.param" in fixture.showerror.call_args.args[1]

    def test_failed_ack_warns_when_readback_is_unavailable(self, view_with_model) -> None:
        """An empty FC parameter set cannot establish whether the calibration saved."""
        fixture = view_with_model
        fixture.model.start_simple_calibration.return_value = (False, "Acknowledgment timed out")
        fixture.model.is_connected.return_value = True
        fixture.base_window.parameter_editor.fc_parameters = {}

        fixture.view._on_simple_calibration()

        assert "could not confirm" in fixture.showerror.call_args.args[1].lower()


class TestFullCalibrationStart:
    """Test entering and failing to enter the 6-position wizard."""

    def test_starting_full_calibration_reveals_wizard_and_disables_top_buttons(self, view_with_model) -> None:
        """
        A successful start reveals the wizard and locks the top-level buttons.

        GIVEN: The data model accepts the full calibration start
        WHEN: The user clicks Full Calibration
        THEN: The wizard panel is shown, the top buttons are disabled and polling begins
        """
        view = view_with_model.view
        view_with_model.model.start_full_calibration.return_value = (True, "started")

        view._on_start_full_calibration()

        assert view._wizard_frame.winfo_manager() == "pack"
        assert str(view._simple_btn.cget("state")) == "disabled"
        assert str(view._full_btn.cget("state")) == "disabled"
        assert view._poll_job == "after-id"
        view_with_model.showerror.assert_not_called()

    def test_failing_to_start_full_calibration_shows_error_and_keeps_wizard_hidden(self, view_with_model) -> None:
        """
        A rejected start surfaces an error and never shows the wizard.

        GIVEN: The data model rejects the full calibration start
        WHEN: The user clicks Full Calibration
        THEN: An error dialog is shown, the wizard stays hidden and polling never starts
        """
        view = view_with_model.view
        view_with_model.model.start_full_calibration.return_value = (False, "link busy")

        view._on_start_full_calibration()

        view_with_model.showerror.assert_called_once()
        assert view._wizard_frame.winfo_manager() == ""
        assert view._poll_job is None


class TestFullCalibrationPolling:
    """Test the tkinter after() polling loop that drives the wizard."""

    def test_successful_full_calibration_stages_measured_values_for_later_upload(self, view_with_model) -> None:
        """
        Completing full calibration preserves the measured results in the staged upload values.

        GIVEN: Old staged offsets, scales and trims alongside an unrelated filter edit
        WHEN: Full calibration completes and fresh flight-controller values are downloaded
        THEN: Calibration results are staged, the filter edit survives, and other stale steps are reported
        """
        fixture = view_with_model
        editor = ParameterEditor.__new__(ParameterEditor)
        editor._flight_controller = SimpleNamespace(fc_parameters={"INS_ACCOFFS_X": 0.1})
        editor.current_file = "14_accelerometer_calibration.param"
        editor._local_filesystem = SimpleNamespace(file_parameters={"other.param": ParDict({"AHRS_TRIM_X": Par(0)})})
        staged_values = {"INS_ACCOFFS_X": 0.1, "INS_ACC2SCAL_Y": 1.0, "AHRS_TRIM_X": 0.0, "INS_ACCEL_FILTER": 42.0}
        editor.current_step_parameters = {name: ArduPilotParameter(name, Par(value)) for name, value in staged_values.items()}
        fixture.base_window.parameter_editor = editor
        downloaded_values = {
            "INS_ACCOFFS_X": 0.2,
            "INS_ACC2SCAL_Y": 0.98,
            "AHRS_TRIM_X": 0.01,
            "INS_ACCEL_FILTER": 20.0,
            "INS_ACC3SCAL_Z": 1.02,
        }

        def download(*, redownload: bool) -> tuple[dict[str, float], dict[str, float]]:
            assert redownload
            editor._flight_controller.fc_parameters = downloaded_values
            return downloaded_values, {}

        fixture.base_window.download_flight_controller_parameters.side_effect = download
        fixture.model.poll_for_next_position.return_value = mavutil.mavlink.ACCELCAL_VEHICLE_POS_SUCCESS
        fixture.model.is_calibration_complete.return_value = True
        fixture.model.is_calibration_successful.return_value = True

        fixture.view._poll_tick()

        for name in ["INS_ACCOFFS_X", "INS_ACC2SCAL_Y", "AHRS_TRIM_X"]:
            assert editor.current_step_parameters[name].get_new_value() == downloaded_values[name]
        assert editor.current_step_parameters["INS_ACCEL_FILTER"].get_new_value() == 42.0
        assert "INS_ACC3SCAL_Z" not in editor.current_step_parameters
        assert editor._local_filesystem.file_parameters["other.param"]["AHRS_TRIM_X"].value == 0
        assert "other.param" in fixture.showinfo.call_args.args[1]

    def test_full_calibration_failed_readback_preserves_staged_values(self, view_with_model) -> None:
        """
        A failed readback must not replace staged values with the pre-calibration cache.

        GIVEN: A successful calibration followed by an empty parameter download
        WHEN: The wizard finishes
        THEN: No cached parameters are copied into staged values or other steps
        """
        fixture = view_with_model
        editor = fixture.base_window.parameter_editor
        editor.fc_parameters = {"INS_ACCOFFS_X": 0.1}
        editor.current_step_parameters = {"INS_ACCOFFS_X": ArduPilotParameter("INS_ACCOFFS_X", Par(0.3))}
        editor.find_other_steps_with_stale_calibration_values = MagicMock()
        fixture.base_window.download_flight_controller_parameters.return_value = ({}, {})

        fixture.view._end_full_calibration(success=True)

        assert editor.current_step_parameters["INS_ACCOFFS_X"].get_new_value() == 0.3
        editor.update_parameters_from_fc_values.assert_not_called()
        editor.find_other_steps_with_stale_calibration_values.assert_not_called()
        assert "could not download" in fixture.showinfo.call_args.args[1].lower()

    def test_poll_tick_reschedules_itself_while_no_position_is_ready(self, view_with_model) -> None:
        """
        Polling keeps itself alive while the flight controller stays silent.

        GIVEN: The data model has no new position to report
        WHEN: A poll tick runs
        THEN: A new poll job is scheduled and the Continue button stays disabled
        """
        view = view_with_model.view
        view_with_model.model.poll_for_next_position.return_value = None

        view._poll_tick()

        assert view._poll_job == "after-id"
        assert str(view._continue_btn.cget("state")) == "disabled"

    def test_poll_tick_presents_requested_position_and_enables_continue(self, view_with_model) -> None:
        """
        A newly requested position is shown and the user can confirm it.

        GIVEN: The data model reports a new, non-terminal position
        WHEN: A poll tick runs
        THEN: The instruction label is updated and the Continue button is enabled
        """
        view = view_with_model.view
        view_with_model.model.poll_for_next_position.return_value = mavutil.mavlink.ACCELCAL_VEHICLE_POS_LEVEL
        view_with_model.model.is_calibration_complete.return_value = False
        view_with_model.model.get_position_label.return_value = "Place vehicle LEVEL and click Continue"

        view._poll_tick()

        assert str(view._position_label.cget("text")) == "Place vehicle LEVEL and click Continue"
        assert str(view._continue_btn.cget("state")) == "normal"

    def test_poll_tick_ends_calibration_successfully_on_success_sentinel(self, view_with_model) -> None:
        """
        Reaching the success sentinel ends the wizard with a success dialog.

        GIVEN: The data model reports a completed, successful calibration
        WHEN: A poll tick runs
        THEN: The wizard is hidden and a success result dialog is shown
        """
        view = view_with_model.view
        view_with_model.model.start_full_calibration.return_value = (True, "started")
        view._on_start_full_calibration()
        view_with_model.model.poll_for_next_position.return_value = mavutil.mavlink.ACCELCAL_VEHICLE_POS_SUCCESS
        view_with_model.model.is_calibration_complete.return_value = True
        view_with_model.model.is_calibration_successful.return_value = True

        view._poll_tick()

        assert view._wizard_frame.winfo_manager() == ""
        view_with_model.showinfo.assert_called_once()
        view_with_model.base_window.download_flight_controller_parameters.assert_called_once_with(redownload=True)
        view_with_model.base_window.parameter_editor.update_parameters_from_fc_values.assert_not_called()
        view_with_model.base_window.repopulate_parameter_table.assert_called_once_with()

    def test_poll_tick_ends_calibration_with_failure_on_failure_sentinel(self, view_with_model) -> None:
        """
        Reaching the failure sentinel ends the wizard with a failure dialog.

        GIVEN: The data model reports a completed but failed calibration
        WHEN: A poll tick runs
        THEN: The wizard is hidden and a failure dialog is shown
        """
        view = view_with_model.view
        view_with_model.model.start_full_calibration.return_value = (True, "started")
        view._on_start_full_calibration()
        view_with_model.model.poll_for_next_position.return_value = mavutil.mavlink.ACCELCAL_VEHICLE_POS_FAILED
        view_with_model.model.is_calibration_complete.return_value = True
        view_with_model.model.is_calibration_successful.return_value = False

        view._poll_tick()

        assert view._wizard_frame.winfo_manager() == ""
        view_with_model.showerror.assert_called_once()


class TestFullCalibrationContinueAndCancel:
    """Test the Continue and Cancel wizard controls."""

    def test_continue_confirms_position_and_resumes_polling(self, view_with_model) -> None:
        """
        Confirming a position resumes the polling loop for the next step.

        GIVEN: The data model confirms the current position successfully
        WHEN: The user clicks Continue
        THEN: The Continue button is disabled again and polling resumes
        """
        view = view_with_model.view
        view_with_model.model.confirm_current_position.return_value = (True, "confirmed")

        view._on_continue()

        assert str(view._continue_btn.cget("state")) == "disabled"
        assert view._poll_job == "after-id"
        view_with_model.showerror.assert_not_called()

    def test_continue_failure_aborts_calibration_with_error(self, view_with_model) -> None:
        """
        A failed confirmation aborts the wizard and reports the error.

        GIVEN: The data model fails to confirm the current position
        WHEN: The user clicks Continue
        THEN: An error dialog is shown and the wizard is torn down
        """
        view = view_with_model.view
        view_with_model.model.start_full_calibration.return_value = (True, "started")
        view._on_start_full_calibration()
        view_with_model.model.confirm_current_position.return_value = (False, "command denied")

        view._on_continue()

        assert view_with_model.showerror.called
        assert view_with_model.showerror.call_args_list[0].args[1] == "command denied"
        assert view._wizard_frame.winfo_manager() == ""

    def test_cancel_stops_polling_hides_wizard_and_notifies_user(self, view_with_model) -> None:
        """
        Cancelling tears the wizard down and tells the user it was cancelled.

        GIVEN: An active full calibration wizard
        WHEN: The user clicks Cancel
        THEN: Polling stops, the wizard is hidden and a cancellation dialog is shown
        """
        view = view_with_model.view
        view_with_model.model.start_full_calibration.return_value = (True, "started")
        view_with_model.model.cancel_full_calibration.return_value = (
            True,
            "The calibration wizard was closed. The flight controller may still be finishing calibration.",
        )
        view._on_start_full_calibration()

        view._on_cancel_full_calibration()

        assert view._poll_job is None
        assert view._wizard_frame.winfo_manager() == ""
        assert str(view._simple_btn.cget("state")) == "normal"
        view_with_model.showinfo.assert_called_once_with(
            "Calibration Wizard Closed",
            "The calibration wizard was closed. The flight controller may still be finishing calibration.",
        )
        view_with_model.showerror.assert_not_called()

    def test_failed_cancel_still_closes_wizard_and_shows_fc_error(self, view_with_model) -> None:
        """A cancellation error is reported only after the local wizard has been made escapable."""
        view = view_with_model.view
        view_with_model.model.start_full_calibration.return_value = (True, "started")
        view_with_model.model.cancel_full_calibration.return_value = (False, "Command denied")
        view._on_start_full_calibration()

        view._on_cancel_full_calibration()

        assert view._wizard_frame.winfo_manager() == ""
        assert view._poll_job is None
        assert str(view._simple_btn.cget("state")) == "normal"
        view_with_model.showerror.assert_called_once_with("Calibration Failed", "Command denied")


class TestPluginLifecycle:
    """Test the plugin lifecycle hooks that keep the view reusable."""

    def test_on_deactivate_hides_active_wizard_and_restores_buttons(self, tk_root, mocker) -> None:
        """
        Deactivation should leave the view in a reusable state.

        GIVEN: A full calibration wizard is active
        WHEN: on_deactivate() is called
        THEN: The polling job is cancelled
        AND: The wizard is hidden and the top-level buttons are re-enabled
        """
        flight_controller = MagicMock()
        flight_controller.master = MagicMock()
        flight_controller.send_accel_calibration_full_start.return_value = (True, "")
        model = AccelerometerCalibrationDataModel(flight_controller)

        parent = ttk.Frame(tk_root)
        try:
            view = AccelerometerCalibrationView(parent, model, SimpleNamespace(root=tk_root))

            after_spy = mocker.patch.object(view, "after", return_value="after-id")
            after_cancel_spy = mocker.patch.object(view, "after_cancel")

            view._on_start_full_calibration()

            assert after_spy.called
            assert view._poll_job == "after-id"
            assert view._wizard_frame.winfo_manager() == "pack"
            assert str(view._simple_btn.cget("state")) == "disabled"
            assert str(view._full_btn.cget("state")) == "disabled"

            view.on_deactivate()

            after_cancel_spy.assert_any_call("after-id")
            assert view._poll_job is None
            assert view._imu_poll_job is None
            assert view._wizard_frame.winfo_manager() == ""
            assert str(view._simple_btn.cget("state")) == "normal"
            assert str(view._full_btn.cget("state")) == "normal"
        finally:
            parent.destroy()

    def test_destroy_cancels_pending_poll_job(self, tk_root, mocker) -> None:
        """
        Destroying the view must cancel any in-flight poll job.

        GIVEN: A view with a scheduled poll job
        WHEN: destroy() is called
        THEN: The pending poll job is cancelled before the widget is torn down
        """
        flight_controller = MagicMock()
        flight_controller.master = MagicMock()
        flight_controller.send_accel_calibration_full_start.return_value = (True, "")
        model = AccelerometerCalibrationDataModel(flight_controller)

        parent = ttk.Frame(tk_root)
        view = AccelerometerCalibrationView(parent, model, SimpleNamespace(root=tk_root))
        mocker.patch.object(view, "after", return_value="after-id")
        after_cancel_spy = mocker.patch.object(view, "after_cancel")
        view._on_start_full_calibration()

        view.destroy()

        after_cancel_spy.assert_any_call("after-id")
        assert view._poll_job is None
        assert view._imu_poll_job is None
        parent.destroy()


class TestPluginFactoryFunction:  # pylint: disable=too-few-public-methods
    """Test the module-level factory function used by the plugin registry."""

    def test_factory_builds_a_view_wired_to_the_given_parent_and_model(self, tk_root) -> None:
        """
        The factory produces a ready-to-use view bound to its collaborators.

        GIVEN: A parent frame, a data model and a base window
        WHEN: The plugin factory function is invoked
        THEN: It returns an AccelerometerCalibrationView wired to that model
        """
        model = MagicMock(spec=AccelerometerCalibrationDataModel)
        parent = ttk.Frame(tk_root)
        try:
            view = _create_accelerometer_calibration_view(parent, model, SimpleNamespace(root=tk_root))

            assert isinstance(view, AccelerometerCalibrationView)
            assert view.model is model
        finally:
            parent.destroy()
