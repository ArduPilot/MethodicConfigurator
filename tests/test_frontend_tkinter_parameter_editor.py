#!/usr/bin/python3

"""
Tests for the ParameterEditorWindow class.

This file is part of Ardupilot methodic configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2025 Amilcar Lucas

SPDX-License-Identifier: GPL-3.0-or-later
"""

from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from ardupilot_methodic_configurator import _
from ardupilot_methodic_configurator.data_model_par_dict import Par, ParDict
from ardupilot_methodic_configurator.frontend_tkinter_parameter_editor import ParameterEditorWindow

# pylint: disable=redefined-outer-name, too-many-arguments, too-many-positional-arguments, unused-argument, protected-access


@pytest.fixture
def mock_flight_controller() -> MagicMock:
    """Create a mock flight controller for testing."""
    mock_fc = MagicMock()
    mock_fc.fc_parameters = {"PARAM1": 1.0, "PARAM2": 2.0}
    return mock_fc


@pytest.fixture
def mock_local_filesystem() -> MagicMock:
    """Create a mock local filesystem for testing."""
    mock_fs = MagicMock()
    mock_fs.file_parameters = {"test_file.param": {"PARAM1": Par(1.0), "PARAM2": Par(2.0)}}
    return mock_fs


@pytest.fixture
def parameter_editor(root, mock_flight_controller, mock_local_filesystem) -> ParameterEditorWindow:
    """Create a ParameterEditorWindow instance for testing with real widgets in headless mode."""
    # Create the object without calling __init__
    editor = ParameterEditorWindow.__new__(ParameterEditorWindow)

    # Create a mock for parameter_editor_table
    mock_parameter_editor_table = MagicMock()

    # Manually set required attributes for tests using real root
    editor.root = root
    editor.main_frame = MagicMock()  # Still mock the main frame to avoid complex UI setup
    editor.current_file = "test_file.param"
    editor.flight_controller = mock_flight_controller
    editor.local_filesystem = mock_local_filesystem
    editor.at_least_one_changed_parameter_written = False
    editor.parameter_editor_table = mock_parameter_editor_table

    return editor


@pytest.fixture
def configured_parameter_editor(mock_flight_controller, mock_local_filesystem) -> ParameterEditorWindow:
    """Fixture providing a configured ParameterEditorWindow for business logic testing."""
    with (
        patch("tkinter.Tk"),
        patch.object(ParameterEditorWindow, "__init__", return_value=None),
        patch("ardupilot_methodic_configurator.frontend_tkinter_parameter_editor.logging_info"),
    ):
        editor = ParameterEditorWindow.__new__(ParameterEditorWindow)
        editor.flight_controller = mock_flight_controller
        editor.local_filesystem = mock_local_filesystem
        return editor


class TestParameterEditorWindow:
    """Test cases for the ParameterEditorWindow class."""

    @patch("sys.exit")
    def test_should_copy_fc_values_to_file_no_auto_change(
        self, mock_exit: MagicMock, parameter_editor, mock_local_filesystem
    ) -> None:
        """Test that nothing happens when there is no auto_changed_by value."""
        mock_local_filesystem.auto_changed_by.return_value = None

        parameter_editor._ParameterEditorWindow__should_copy_fc_values_to_file("test_file.param")  # pylint: disable=protected-access

        mock_local_filesystem.auto_changed_by.assert_called_once_with("test_file.param")
        mock_local_filesystem.copy_fc_values_to_file.assert_not_called()
        mock_exit.assert_not_called()

    @patch("tkinter.Toplevel")
    @patch("tkinter.Label")
    @patch("tkinter.Frame")
    @patch("tkinter.Button")
    @patch("sys.exit")
    def test_should_copy_fc_values_to_file_yes_response(
        self,
        mock_exit: MagicMock,
        mock_button: MagicMock,
        mock_frame: MagicMock,
        mock_label: MagicMock,
        mock_toplevel: MagicMock,
        parameter_editor,
        mock_local_filesystem,
        root,
    ) -> None:
        """Test handling 'Yes' response in the dialog."""
        mock_local_filesystem.auto_changed_by.return_value = "External Tool"

        # Setup the mock toplevel to better simulate dialog behavior
        mock_dialog = MagicMock()
        mock_toplevel.return_value = mock_dialog
        mock_dialog.result = [None]  # Initialize result list

        # Create a fake dialog response mechanism - simulate "Yes" button click
        def side_effect(*args, **kwargs) -> None:  # noqa: ARG001 # pylint: disable=unused-argument
            # Find the "Yes" button callback and execute it
            for call in mock_button.call_args_list:
                _call_args, call_kwargs = call
                if "text" in call_kwargs and call_kwargs["text"] == _("Yes"):
                    # This is the "Yes" button - execute its command
                    call_kwargs["command"]()
                    break

        # Set up the dialog behavior when wait_window is called
        root.wait_window = MagicMock(side_effect=side_effect)

        parameter_editor._ParameterEditorWindow__should_copy_fc_values_to_file("test_file.param")  # pylint: disable=protected-access

        mock_local_filesystem.auto_changed_by.assert_called_once_with("test_file.param")
        mock_local_filesystem.copy_fc_values_to_file.assert_called_once()
        mock_exit.assert_not_called()

    @patch("tkinter.Toplevel")
    @patch("tkinter.Label")
    @patch("tkinter.Frame")
    @patch("tkinter.Button")
    @patch("sys.exit")
    def test_should_copy_fc_values_to_file_no_response(
        self,
        mock_exit: MagicMock,
        mock_button: MagicMock,
        mock_frame: MagicMock,
        mock_label: MagicMock,
        mock_toplevel: MagicMock,
        parameter_editor,
        mock_local_filesystem,
        root,
    ) -> None:
        """Test handling 'No' response in the dialog."""
        mock_local_filesystem.auto_changed_by.return_value = "External Tool"

        # Setup the mock toplevel to better simulate dialog behavior
        mock_dialog = MagicMock()
        mock_toplevel.return_value = mock_dialog
        mock_dialog.result = [None]  # Initialize result list

        # Create a fake dialog response mechanism - simulate "No" button click
        def side_effect(*args, **kwargs) -> None:  # noqa: ARG001 # pylint: disable=unused-argument
            # Find the "No" button callback and execute it
            for call in mock_button.call_args_list:
                _call_args, call_kwargs = call
                if "text" in call_kwargs and call_kwargs["text"] == _("No"):
                    # This is the "No" button - execute its command
                    call_kwargs["command"]()
                    break

        # Set up the dialog behavior when wait_window is called
        root.wait_window = MagicMock(side_effect=side_effect)

        parameter_editor._ParameterEditorWindow__should_copy_fc_values_to_file("test_file.param")  # pylint: disable=protected-access

        mock_local_filesystem.auto_changed_by.assert_called_once_with("test_file.param")
        mock_local_filesystem.copy_fc_values_to_file.assert_not_called()
        mock_exit.assert_not_called()

    @patch("tkinter.Toplevel")
    @patch("tkinter.Label")
    @patch("tkinter.Frame")
    @patch("tkinter.Button")
    @patch("sys.exit")
    def test_should_copy_fc_values_to_file_close_response(
        self,
        mock_exit: MagicMock,
        mock_button: MagicMock,
        mock_frame: MagicMock,
        mock_label: MagicMock,
        mock_toplevel: MagicMock,
        parameter_editor,
        mock_local_filesystem,
        root,
    ) -> None:
        """Test handling 'Close' response in the dialog."""
        mock_local_filesystem.auto_changed_by.return_value = "External Tool"

        # Setup the mock toplevel to better simulate dialog behavior
        mock_dialog = MagicMock()
        mock_toplevel.return_value = mock_dialog
        mock_dialog.result = [None]  # Initialize result list

        # Create a fake dialog response mechanism - simulate "Close" button click
        def side_effect(*args, **kwargs) -> None:  # noqa: ARG001 # pylint: disable=unused-argument
            # Find the "Close" button callback and execute it
            for call in mock_button.call_args_list:
                _call_args, call_kwargs = call
                if "text" in call_kwargs and call_kwargs["text"] == _("Close"):
                    # This is the "Close" button - execute its command
                    call_kwargs["command"]()
                    break

        # Set up the dialog behavior when wait_window is called
        root.wait_window = MagicMock(side_effect=side_effect)

        parameter_editor._ParameterEditorWindow__should_copy_fc_values_to_file("test_file.param")  # pylint: disable=protected-access

        mock_local_filesystem.auto_changed_by.assert_called_once_with("test_file.param")
        mock_local_filesystem.copy_fc_values_to_file.assert_not_called()
        mock_exit.assert_called_once_with(0)

    @patch("tkinter.Toplevel")
    @patch("tkinter.Label")
    @patch("tkinter.Frame")
    @patch("tkinter.Button")
    def test_dialog_creation(
        self,
        mock_button: MagicMock,
        mock_frame: MagicMock,
        mock_label: MagicMock,
        mock_toplevel: MagicMock,
        parameter_editor,
        mock_local_filesystem,
        root,
    ) -> None:
        """Test the creation of the dialog with its components."""
        mock_local_filesystem.auto_changed_by.return_value = "External Tool"

        # Setup the mock toplevel to better simulate dialog behavior
        mock_dialog = MagicMock()
        mock_toplevel.return_value = mock_dialog
        mock_dialog.result = [None]  # Initialize result list

        # Don't let the test exit
        with patch("sys.exit"):
            # Replace wait_window with a mock that doesn't block
            def fake_wait_window(*args: Any, **kwargs: Any) -> None:  # noqa: ANN401 # pylint: disable=unused-argument
                pass

            root.wait_window = MagicMock(side_effect=fake_wait_window)

            parameter_editor._ParameterEditorWindow__should_copy_fc_values_to_file("test_file.param")  # pylint: disable=protected-access

        # Verify dialog creation
        mock_toplevel.assert_called_once()

        # Check for label, buttons, and frame creation
        mock_label.assert_called_once()
        mock_frame.assert_called_once()


class TestParameterFilteringWorkflows:
    """Test parameter filtering business logic workflows."""

    def test_user_can_filter_fc_parameters_excluding_defaults_and_readonly(self, configured_parameter_editor) -> None:
        """
        User can filter FC parameters to exclude default values and read-only parameters.

        GIVEN: A user has FC parameters with defaults and read-only parameters
        WHEN: They filter using _non_default_non_read_only_fc_params
        THEN: Only non-default, writable parameters should remain
        """
        # Arrange: Set up FC parameters with mixed types
        fc_params = {
            "PARAM_NORMAL": 5.0,  # Normal parameter, non-default
            "PARAM_DEFAULT": 1.0,  # Default parameter, should be filtered
            "PARAM_READONLY": 10.0,  # Read-only parameter, should be filtered
            "PARAM_WRITABLE": 15.0,  # Normal writable parameter
        }

        default_params = ParDict(
            {
                "PARAM_DEFAULT": Par(1.0, "Default value"),
            }
        )

        doc_dict = {
            "PARAM_READONLY": {"ReadOnly": True},
            "PARAM_NORMAL": {"ReadOnly": False},
            "PARAM_WRITABLE": {"ReadOnly": False},
        }

        configured_parameter_editor.flight_controller.fc_parameters = fc_params
        configured_parameter_editor.local_filesystem.param_default_dict = default_params
        configured_parameter_editor.local_filesystem.doc_dict = doc_dict

        # Act: Filter the parameters
        result = configured_parameter_editor._non_default_non_read_only_fc_params()

        # Assert: Only non-default, writable parameters remain
        assert len(result) == 2
        assert "PARAM_NORMAL" in result
        assert "PARAM_WRITABLE" in result
        assert "PARAM_DEFAULT" not in result  # Filtered as default
        assert "PARAM_READONLY" not in result  # Filtered as read-only

    def test_user_receives_empty_result_when_no_fc_parameters_available(self, configured_parameter_editor) -> None:
        """
        User receives empty result when no FC parameters are available for filtering.

        GIVEN: A user has no FC parameters available
        WHEN: They attempt to filter parameters
        THEN: An empty ParDict should be returned
        """
        # Arrange: No FC parameters available
        configured_parameter_editor.flight_controller.fc_parameters = {}

        # Act: Attempt to filter empty parameters
        result = configured_parameter_editor._non_default_non_read_only_fc_params()

        # Assert: Empty result returned
        assert len(result) == 0
        assert isinstance(result, ParDict)

    def test_user_can_filter_parameters_with_missing_documentation(self, configured_parameter_editor) -> None:
        """
        User can filter parameters even when documentation is incomplete.

        GIVEN: A user has FC parameters with incomplete documentation
        WHEN: They filter parameters
        THEN: Parameters without documentation should be treated as writable
        """
        # Arrange: FC parameters with incomplete documentation
        fc_params = {
            "PARAM_WITH_DOCS": 5.0,  # Has documentation
            "PARAM_NO_DOCS": 10.0,  # Missing from doc_dict
        }

        doc_dict = {
            "PARAM_WITH_DOCS": {"ReadOnly": False},
            # PARAM_NO_DOCS intentionally missing
        }

        configured_parameter_editor.flight_controller.fc_parameters = fc_params
        configured_parameter_editor.local_filesystem.param_default_dict = ParDict()
        configured_parameter_editor.local_filesystem.doc_dict = doc_dict

        # Act: Filter parameters with incomplete documentation
        result = configured_parameter_editor._non_default_non_read_only_fc_params()

        # Assert: Both parameters included (missing docs treated as writable)
        assert len(result) == 2
        assert "PARAM_WITH_DOCS" in result
        assert "PARAM_NO_DOCS" in result


class TestParameterExportWorkflows:
    """Test parameter export business logic workflows."""

    def test_user_can_export_missing_parameters_with_range_filename(self, configured_parameter_editor) -> None:
        """
        User can export FC parameters missing from AMC files with descriptive filename.

        GIVEN: A user has FC parameters that differ from AMC parameter files
        WHEN: They export missing/different parameters
        THEN: Parameters should be exported with a range-based filename
        """
        # Arrange: Set up FC parameters and AMC files
        fc_params = ParDict(
            {
                "FC_ONLY_PARAM": Par(5.0, "FC only"),
                "DIFFERENT_PARAM": Par(10.0, "Different value"),
                "SAME_PARAM": Par(1.0, "Same value"),
            }
        )

        amc_file_params = {
            "01_setup.param": ParDict(
                {
                    "DIFFERENT_PARAM": Par(15.0, "Original value"),
                    "SAME_PARAM": Par(1.0, "Same value"),
                }
            ),
            "00_default.param": ParDict(
                {
                    "DEFAULT_PARAM": Par(0.0, "Default"),
                }
            ),
        }

        configured_parameter_editor.flight_controller.fc_parameters = {"test": "data"}
        configured_parameter_editor.local_filesystem.file_parameters = amc_file_params
        configured_parameter_editor.local_filesystem.export_to_param = MagicMock()

        # Act: Export missing/different parameters
        configured_parameter_editor._export_fc_params_missing_or_different_in_amc_files(fc_params, "01_setup.param")

        # Assert: Export called with correct filename and parameters
        expected_filename = "fc_params_missing_or_different_in_the_amc_param_files_01_setup_to_01_setup.param"
        configured_parameter_editor.local_filesystem.export_to_param.assert_called_once()
        args, kwargs = configured_parameter_editor.local_filesystem.export_to_param.call_args

        assert args[1] == expected_filename
        assert kwargs["annotate_doc"] is False
        # Verify exported parameters contain differences
        exported_params = args[0]
        assert "FC_ONLY_PARAM" in exported_params
        assert "DIFFERENT_PARAM" in exported_params

    def test_user_sees_no_export_when_parameters_match_amc_files(self, configured_parameter_editor) -> None:
        """
        User sees no export when all FC parameters match AMC files.

        GIVEN: A user has FC parameters that perfectly match AMC parameter files
        WHEN: They attempt to export missing/different parameters
        THEN: No export should occur and appropriate log message should be shown
        """
        # Arrange: Matching FC and AMC parameters
        matching_params = ParDict(
            {
                "MATCHING_PARAM": Par(5.0, "Same value"),
            }
        )

        amc_file_params = {
            "01_setup.param": ParDict(
                {
                    "MATCHING_PARAM": Par(5.0, "AMC value"),
                }
            ),
        }

        configured_parameter_editor.flight_controller.fc_parameters = {"test": "data"}
        configured_parameter_editor.local_filesystem.file_parameters = amc_file_params
        configured_parameter_editor.local_filesystem.export_to_param = MagicMock()

        with patch("ardupilot_methodic_configurator.frontend_tkinter_parameter_editor.logging_info") as mock_log:
            # Act: Attempt to export when parameters match
            configured_parameter_editor._export_fc_params_missing_or_different_in_amc_files(matching_params, "01_setup.param")

            # Assert: No export occurred and appropriate message logged
            configured_parameter_editor.local_filesystem.export_to_param.assert_not_called()
            mock_log.assert_called_with("No FC parameters are missing or different from AMC parameter files")

    def test_user_handles_early_exit_when_no_fc_parameters(self, configured_parameter_editor) -> None:
        """
        User handles graceful early exit when no FC parameters are available.

        GIVEN: A user has no FC parameters available
        WHEN: They attempt to export missing/different parameters
        THEN: The function should exit early without processing
        """
        # Arrange: No FC parameters available
        configured_parameter_editor.flight_controller.fc_parameters = None
        configured_parameter_editor.local_filesystem.export_to_param = MagicMock()

        # Act: Attempt export with no FC parameters
        configured_parameter_editor._export_fc_params_missing_or_different_in_amc_files(ParDict(), "01_setup.param")

        # Assert: No processing occurred
        configured_parameter_editor.local_filesystem.export_to_param.assert_not_called()

    def test_user_can_export_with_multi_file_range(self, configured_parameter_editor) -> None:
        """
        User can export parameters with filenames reflecting multi-file ranges.

        GIVEN: A user processes multiple AMC parameter files
        WHEN: They export missing parameters after processing several files
        THEN: The filename should reflect the range from first to last processed file
        """
        # Arrange: Multiple AMC files with different content
        fc_params = ParDict(
            {
                "FC_PARAM": Par(10.0, "FC parameter"),
            }
        )

        amc_file_params = {
            "01_basic.param": ParDict({"BASIC_PARAM": Par(1.0, "Basic")}),
            "02_advanced.param": ParDict({"ADVANCED_PARAM": Par(2.0, "Advanced")}),
            "03_final.param": ParDict({"FINAL_PARAM": Par(3.0, "Final")}),
            "00_default.param": ParDict({"DEFAULT": Par(0.0, "Default")}),
        }

        configured_parameter_editor.flight_controller.fc_parameters = {"test": "data"}
        configured_parameter_editor.local_filesystem.file_parameters = amc_file_params
        configured_parameter_editor.local_filesystem.export_to_param = MagicMock()

        # Act: Export parameters with multi-file range
        configured_parameter_editor._export_fc_params_missing_or_different_in_amc_files(fc_params, "03_final.param")

        # Assert: Filename reflects correct range
        expected_filename = "fc_params_missing_or_different_in_the_amc_param_files_01_basic_to_03_final.param"
        configured_parameter_editor.local_filesystem.export_to_param.assert_called_once()
        args, _ = configured_parameter_editor.local_filesystem.export_to_param.call_args
        assert args[1] == expected_filename

    def test_user_handles_unknown_first_filename_gracefully(self, configured_parameter_editor) -> None:
        """
        User handles case where no valid first configuration file is found.

        GIVEN: A user has only default parameter files
        WHEN: They attempt to export parameters
        THEN: The filename should use 'unknown' for missing first filename
        """
        # Arrange: Only default files available
        fc_params = ParDict(
            {
                "FC_PARAM": Par(5.0, "FC parameter"),
            }
        )

        amc_file_params = {
            "00_default.param": ParDict({"DEFAULT": Par(0.0, "Default")}),
        }

        configured_parameter_editor.flight_controller.fc_parameters = {"test": "data"}
        configured_parameter_editor.local_filesystem.file_parameters = amc_file_params
        configured_parameter_editor.local_filesystem.export_to_param = MagicMock()

        # Act: Export with no valid first config file
        configured_parameter_editor._export_fc_params_missing_or_different_in_amc_files(fc_params, "00_default.param")

        # Assert: Uses 'unknown' for missing first filename
        expected_filename = "fc_params_missing_or_different_in_the_amc_param_files_unknown_to_00_default.param"
        configured_parameter_editor.local_filesystem.export_to_param.assert_called_once()
        args, _ = configured_parameter_editor.local_filesystem.export_to_param.call_args
        assert args[1] == expected_filename
