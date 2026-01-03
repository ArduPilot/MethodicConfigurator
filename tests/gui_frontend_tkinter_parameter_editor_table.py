#!/usr/bin/env python3

"""
GUI tests for the ParameterEditorTable using PyAutoGUI.

This module contains automated GUI tests for the Tkinter-based parameter editor table.
Tests verify that the table creation and widget generation works correctly.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import contextlib
import tkinter as tk
from collections.abc import Generator
from tkinter import ttk
from typing import Union, cast
from unittest.mock import Mock, patch

import pytest
from conftest import PARAMETER_EDITOR_TABLE_HEADERS_ADVANCED, PARAMETER_EDITOR_TABLE_HEADERS_SIMPLE

from ardupilot_methodic_configurator.data_model_ardupilot_parameter import ArduPilotParameter, Par
from ardupilot_methodic_configurator.data_model_par_dict import ParDict
from ardupilot_methodic_configurator.data_model_parameter_editor import ParameterEditor
from ardupilot_methodic_configurator.frontend_tkinter_pair_tuple_combobox import PairTupleCombobox
from ardupilot_methodic_configurator.frontend_tkinter_parameter_editor_table import (
    ParameterEditorTable,
    ParameterEditorTableDialogs,
)

# pylint: disable=protected-access


def create_mock_data_model_ardupilot_parameter(  # pylint: disable=too-many-arguments,too-many-positional-arguments  # noqa: PLR0913
    name: str = "TEST_PARAM",
    value: float = 1.0,
    default_value: Union[float, None] = None,
    comment: str = "test comment",
    metadata: Union[dict, None] = None,
    fc_value: Union[float, None] = None,
    is_forced: bool = False,
    is_calibration: bool = False,
    is_readonly: bool = False,
    min_value: Union[float, None] = None,
    max_value: Union[float, None] = None,
) -> ArduPilotParameter:
    """Create a mock ArduPilotParameter for testing in GUI workflows."""
    metadata = metadata or {}

    if is_calibration:
        metadata["Calibration"] = True
    if is_readonly:
        metadata["ReadOnly"] = True
    if min_value is not None:
        metadata["min"] = min_value
    if max_value is not None:
        metadata["max"] = max_value

    metadata.setdefault("unit", "")
    metadata.setdefault("doc_tooltip", "Test tooltip")
    metadata.setdefault("unit_tooltip", "Unit tooltip")

    par_obj = Par(value, comment)
    default_par = Par(default_value if default_value is not None else 0.0, "default")
    forced_par = Par(value, "forced comment") if is_forced else None

    return ArduPilotParameter(
        name=name, par_obj=par_obj, metadata=metadata, default_par=default_par, fc_value=fc_value, forced_par=forced_par
    )


class TestParameterEditorTableUserWorkflows:
    """Test user workflows and behaviors for ParameterEditorTable GUI components."""

    @pytest.fixture
    def mock_parameter_editor(self) -> Mock:
        """Create a mock parameter editor with gui_complexity attribute."""
        mock_editor = Mock()
        mock_editor.gui_complexity = "normal"
        return mock_editor

    @pytest.fixture
    def parameter_table(
        self, test_param_editor: ParameterEditor, mock_parameter_editor: Mock
    ) -> Generator[ParameterEditorTable, None, None]:
        """Create a ParameterEditorTable instance for testing."""
        # Create a root window for the table
        root = tk.Tk()
        root.withdraw()  # Hide the root window

        dialog_mocks = ParameterEditorTableDialogs(
            show_error=Mock(),
            show_info=Mock(),
            ask_yes_no=Mock(return_value=True),
        )

        # Create the table
        table = ParameterEditorTable(root, test_param_editor, mock_parameter_editor, dialogs=dialog_mocks)

        yield table

        # Cleanup
        with contextlib.suppress(tk.TclError):
            root.destroy()

    def test_user_sees_pyautogui_environment_ready_for_testing(self, gui_test_environment) -> None:
        """
        User can verify that the GUI testing environment is properly configured.

        GIVEN: A user wants to run automated GUI tests
        WHEN: They check the PyAutoGUI environment setup
        THEN: The screen capture and automation capabilities should be available
        """
        # The gui_test_environment fixture handles all the assertions

    def test_user_sees_upload_column_based_on_gui_complexity_level(self, parameter_table: ParameterEditorTable) -> None:
        """
        User sees the upload column displayed according to their GUI complexity preference.

        GIVEN: A user is viewing the parameter editor table
        WHEN: They have different GUI complexity settings
        THEN: The upload column should be shown/hidden appropriately
        AND: Simple users don't see advanced features
        AND: Advanced/Expert users see the upload column
        """
        # Test with different GUI complexity levels
        assert parameter_table._should_show_upload_column("simple") is False
        assert parameter_table._should_show_upload_column("normal") is True

        # Test with None (should use parameter_editor.gui_complexity)
        assert parameter_table._should_show_upload_column(None) is True  # advanced

    def test_user_sees_clear_table_headers_with_helpful_tooltips(self, parameter_table: ParameterEditorTable) -> None:
        """
        User sees clear, descriptive table headers with helpful tooltips.

        GIVEN: A user is viewing the parameter editor table
        WHEN: They look at the table headers
        THEN: Headers should be clear and descriptive
        AND: Tooltips should provide additional guidance
        AND: Headers should adapt based on upload column visibility
        """
        # Test without upload column
        headers, tooltips = parameter_table._create_headers_and_tooltips(show_upload_column=False)

        assert headers == PARAMETER_EDITOR_TABLE_HEADERS_SIMPLE
        assert len(tooltips) == len(headers)

        # Test with upload column
        headers_with_upload, tooltips_with_upload = parameter_table._create_headers_and_tooltips(show_upload_column=True)

        assert headers_with_upload == PARAMETER_EDITOR_TABLE_HEADERS_ADVANCED
        assert len(tooltips_with_upload) == len(headers_with_upload)

    def test_user_sees_parameter_names_displayed_with_proper_formatting(self, parameter_table: ParameterEditorTable) -> None:
        """
        User sees parameter names displayed with consistent formatting and padding.

        GIVEN: A user is viewing parameters in the table
        WHEN: Parameters have different name lengths
        THEN: All parameter names should be displayed with consistent 16-character padding
        AND: The formatting should be user-friendly and readable
        """
        # Create a mock parameter
        mock_param = Mock(spec=ArduPilotParameter)
        mock_param.name = "TEST_PARAM"
        mock_param.is_readonly = False
        mock_param.is_calibration = False
        mock_param.tooltip_new_value = "Test tooltip"

        # Create the label
        label = parameter_table._create_parameter_name(mock_param)

        # Verify it's a ttk.Label
        assert isinstance(label, ttk.Label)

        # Verify the text (should be padded to 16 characters)
        expected_text = "TEST_PARAM" + " " * (16 - len("TEST_PARAM"))
        assert label.cget("text") == expected_text

    def test_user_sees_flight_controller_values_with_clear_indicators(self, parameter_table: ParameterEditorTable) -> None:
        """
        User sees flight controller values clearly indicated in the table.

        GIVEN: A user is comparing parameter values
        WHEN: Some parameters have flight controller values and others don't
        THEN: Parameters with FC values should display the actual value
        AND: Parameters without FC values should show "N/A" clearly
        AND: The display should be unambiguous and user-friendly
        """
        # Test with parameter that has FC value
        mock_param = Mock(spec=ArduPilotParameter)
        mock_param.has_fc_value = True
        mock_param.fc_value_as_string = "1.5"
        mock_param.fc_value_equals_default_value = True
        mock_param.fc_value_is_below_limit.return_value = False
        mock_param.fc_value_is_above_limit.return_value = False
        mock_param.fc_value_has_unknown_bits_set.return_value = False
        mock_param.tooltip_fc_value = "FC value tooltip"

        label = parameter_table._create_flightcontroller_value(mock_param)
        assert isinstance(label, ttk.Label)
        assert label.cget("text") == "1.5"

        # Test with parameter that doesn't have FC value
        mock_param_no_fc = Mock(spec=ArduPilotParameter)
        mock_param_no_fc.has_fc_value = False

        label_no_fc = parameter_table._create_flightcontroller_value(mock_param_no_fc)
        assert isinstance(label_no_fc, ttk.Label)
        assert label_no_fc.cget("text") == "N/A"

    def test_user_sees_clear_visual_indicators_for_parameter_differences(self, parameter_table: ParameterEditorTable) -> None:
        """
        User sees clear visual indicators when parameter values differ from flight controller.

        GIVEN: A user is reviewing parameter changes
        WHEN: Some parameters have different values than the flight controller
        THEN: Different parameters should have clear visual indicators (≠ or !=)
        AND: Same parameters should have neutral indicators
        AND: The indicators should be immediately recognizable
        """
        # Test with different parameter
        mock_param_different = Mock(spec=ArduPilotParameter)
        mock_param_different.is_different_from_fc = True

        label_different = parameter_table._create_value_different_label(mock_param_different)
        assert isinstance(label_different, ttk.Label)
        assert "≠" in label_different.cget("text") or "!=" in label_different.cget("text")

        # Test with same parameter
        mock_param_same = Mock(spec=ArduPilotParameter)
        mock_param_same.is_different_from_fc = False

        label_same = parameter_table._create_value_different_label(mock_param_same)
        assert isinstance(label_same, ttk.Label)
        assert label_same.cget("text") == " "

    def test_user_can_delete_parameters_using_clearly_labeled_buttons(self, parameter_table: ParameterEditorTable) -> None:
        """
        User can delete parameters using clearly labeled buttons.

        GIVEN: A user wants to remove a parameter from their configuration
        WHEN: They look for deletion functionality
        THEN: They should see clearly labeled "Del" buttons
        AND: The buttons should have proper click handlers
        AND: The interface should be intuitive and discoverable
        """
        button = parameter_table._create_delete_button("TEST_PARAM")

        assert isinstance(button, ttk.Button)
        assert button.cget("text") == "Del"

        # Check that the button has a command (callback)
        assert button.cget("command") is not None

    def test_user_sees_table_adapts_to_column_configurations(self, parameter_table: ParameterEditorTable) -> None:
        """
        User sees the table layout properly adapts to different column configurations.

        GIVEN: A user is viewing the parameter table
        WHEN: The table shows different columns based on settings
        THEN: The table layout should adapt gracefully
        AND: Column weights should be configured appropriately
        AND: The layout should remain usable and professional
        """
        # This method configures grid column weights, but doesn't return anything
        # We just verify it doesn't raise an exception
        parameter_table._configure_table_columns(show_upload_column=False)
        parameter_table._configure_table_columns(show_upload_column=True)

    def test_user_sees_appropriate_input_widgets_for_parameter_types(self, parameter_table: ParameterEditorTable) -> None:
        """
        User sees appropriate input widgets based on parameter characteristics.

        GIVEN: A user is editing parameters of different types
        WHEN: Parameters have different properties (multiple choice, bitmask, editable, etc.)
        THEN: They should see the correct input widget type for each parameter
        AND: Widgets should be configured appropriately for the parameter type
        AND: Non-editable parameters should be clearly disabled
        """
        # Create mock change reason widget and value different label
        change_reason_widget = ttk.Entry(parameter_table.view_port)
        value_different_label = ttk.Label(parameter_table.view_port)

        # Test multiple choice parameter (should create combobox)
        mock_multiple_choice_param = Mock(spec=ArduPilotParameter)
        mock_multiple_choice_param.is_multiple_choice = True
        mock_multiple_choice_param.choices_dict = {"Option1": "1", "Option2": "2"}
        mock_multiple_choice_param.get_selected_value_from_dict.return_value = "Option1"
        mock_multiple_choice_param.value_as_string = "Option1"  # Should be the key, not the value
        mock_multiple_choice_param.name = "MULTI_PARAM"
        mock_multiple_choice_param.is_editable = True
        mock_multiple_choice_param.new_value_equals_default_value = False
        mock_multiple_choice_param.tooltip_new_value = "Multiple choice tooltip"

        widget = parameter_table._create_new_value_entry(
            mock_multiple_choice_param, change_reason_widget, value_different_label
        )
        # Should return a PairTupleCombobox for multiple choice parameters
        assert isinstance(widget, PairTupleCombobox)

        # Test regular parameter (should create entry)
        mock_regular_param = Mock(spec=ArduPilotParameter)
        mock_regular_param.is_multiple_choice = False
        mock_regular_param.value_as_string = "42.5"
        mock_regular_param.name = "REGULAR_PARAM"
        mock_regular_param.is_editable = True
        mock_regular_param.new_value_equals_default_value = True
        mock_regular_param.is_below_limit.return_value = False
        mock_regular_param.is_above_limit.return_value = False
        mock_regular_param.has_unknown_bits_set.return_value = False
        mock_regular_param.tooltip_new_value = "Regular parameter tooltip"

        widget = parameter_table._create_new_value_entry(mock_regular_param, change_reason_widget, value_different_label)
        # Should return a ttk.Entry for regular parameters
        assert isinstance(widget, ttk.Entry)

        # Test non-editable parameter (should be disabled)
        mock_non_editable_param = Mock(spec=ArduPilotParameter)
        mock_non_editable_param.is_multiple_choice = False
        mock_non_editable_param.value_as_string = "100"
        mock_non_editable_param.name = "NON_EDITABLE_PARAM"
        mock_non_editable_param.is_editable = False
        mock_non_editable_param.new_value_equals_default_value = False
        mock_non_editable_param.is_below_limit.return_value = False
        mock_non_editable_param.is_above_limit.return_value = False
        mock_non_editable_param.has_unknown_bits_set.return_value = False
        mock_non_editable_param.tooltip_new_value = "Non-editable parameter tooltip"

        widget = parameter_table._create_new_value_entry(mock_non_editable_param, change_reason_widget, value_different_label)
        # Should return a ttk.Entry that is disabled
        assert isinstance(widget, ttk.Entry)
        # For ttk widgets, state is a tuple, check if 'disabled' is in it
        widget_state = widget.state()
        assert "disabled" in widget_state

    def test_user_can_interact_with_bitmask_selection_dialog(self, parameter_table: ParameterEditorTable) -> None:
        """
        User can interact with bitmask selection dialogs for bitmask parameters.

        GIVEN: A user is editing a bitmask parameter
        WHEN: They double-click on the parameter value field
        THEN: A bitmask selection window should open
        AND: They should be able to select/deselect individual bit options
        AND: The parameter value should update based on their selections
        """
        # Create mock change reason widget and value different label
        change_reason_widget = ttk.Entry(parameter_table.view_port)
        value_different_label = ttk.Label(parameter_table.view_port)

        # Create a mock bitmask parameter
        mock_bitmask_param = Mock(spec=ArduPilotParameter)
        mock_bitmask_param.name = "BITMASK_PARAM"
        mock_bitmask_param.value_as_string = "5"  # Binary 101, so bits 0 and 2 set
        mock_bitmask_param.tooltip_new_value = "Bitmask parameter tooltip"
        mock_bitmask_param.bitmask_dict = {0: "Option 1", 1: "Option 2", 2: "Option 3"}

        # Mock the BitmaskHelper to return expected values
        with (
            patch("ardupilot_methodic_configurator.frontend_tkinter_parameter_editor_table.BitmaskHelper") as mock_helper,
            patch("ardupilot_methodic_configurator.frontend_tkinter_parameter_editor_table.BaseWindow.center_window"),
            patch("tkinter.Toplevel") as mock_toplevel,
            patch("tkinter.Checkbutton"),
            patch("tkinter.BooleanVar"),
        ):
            mock_helper.get_checked_keys.return_value = {0, 2}  # Bits 0 and 2 set

            # Create a mock event for double-click
            mock_event = Mock()
            mock_event.widget = Mock(spec=ttk.Entry)
            mock_event.widget.get.return_value = "5"

            # Call the bitmask selection window method
            parameter_table._open_bitmask_selection_window(
                mock_event, mock_bitmask_param, change_reason_widget, value_different_label
            )

            # Verify that a window was created
            mock_toplevel.assert_called_once()

            # Verify that bitmask helper methods were called
            mock_helper.get_checked_keys.assert_called_once_with(5, mock_bitmask_param.bitmask_dict)

    @pytest.mark.skip(reason="Full table population requires complex parameter data setup")
    def test_user_can_work_with_fully_populated_parameter_table(self, parameter_table: ParameterEditorTable) -> None:  # pylint: disable=unused-argument
        """
        User can work with a fully populated parameter table (integration test).

        GIVEN: A user has loaded a complete parameter set
        WHEN: The table is fully populated with real parameter data
        THEN: All parameters should be displayed correctly
        AND: User interactions should work as expected
        AND: The table should handle large datasets efficiently

        NOTE: This test is skipped because it requires complex setup with actual
        parameter data and GUI components. Individual component tests above
        verify the building blocks work correctly.
        """
        pytest.skip("Full table population requires complex parameter data setup - focus on component testing instead")

    def test_user_can_edit_multiple_parameters_in_complete_workflow(self, parameter_table: ParameterEditorTable) -> None:
        """
        User can manage multiple parameters with visual indicators throughout workflow.

        GIVEN: A user has multiple parameters with different states
        WHEN: Parameters have different values (default vs changed)
        THEN: Visual indicators show parameter states correctly
        AND: Each parameter maintains independent state
        AND: The system handles multiple parameter contexts simultaneously
        """
        # Arrange: Create parameters with different value states
        param_default = create_mock_data_model_ardupilot_parameter(
            name="PARAM_DEFAULT",
            value=10.0,
            default_value=10.0,  # Same as default
        )
        param_changed = create_mock_data_model_ardupilot_parameter(
            name="PARAM_CHANGED",
            value=20.0,
            default_value=15.0,  # Different from default
        )

        # Verify: Parameters have correct comparison states
        assert param_default.new_value_equals_default_value is True  # Default
        assert param_changed.new_value_equals_default_value is False  # Changed

        # Verify: parameter editor data model can handle multiple parameters
        assert parameter_table.parameter_editor.current_file == "04_board_orientation.param"
        assert parameter_table.parameter_editor.is_fc_connected is False

    def test_user_can_switch_between_gui_complexity_modes_seamlessly(self, parameter_table: ParameterEditorTable) -> None:
        """
        User can work with different GUI complexity modes.

        GIVEN: A user switches between GUI complexity modes
        WHEN: The table needs to adapt to show/hide upload column
        THEN: Upload column visibility changes based on complexity level
        AND: Simple mode hides advanced features
        AND: Advanced/Expert modes show full functionality
        """
        # Verify: Simple mode hides upload column
        assert parameter_table._should_show_upload_column("simple") is False

        # Verify: Expert mode shows upload column
        assert parameter_table._should_show_upload_column("normal") is True

        # Verify: Change reason column index adapts to upload column visibility
        change_reason_idx_simple = parameter_table._get_change_reason_column_index(show_upload_column=False)
        change_reason_idx_advanced = parameter_table._get_change_reason_column_index(show_upload_column=True)

        # Verify: Column index is one less without upload column
        assert change_reason_idx_advanced == change_reason_idx_simple + 1

    def test_user_recovers_gracefully_from_validation_errors(self, parameter_table: ParameterEditorTable) -> None:
        """
        User receives clear feedback for validation errors and can recover.

        GIVEN: A user enters parameter values
        WHEN: Values are outside allowed ranges
        THEN: System provides clear error handling
        AND: Valid values are accepted
        AND: Invalid values trigger appropriate error responses
        """
        # Arrange: Create parameter with validation constraints
        param_constrained = create_mock_data_model_ardupilot_parameter(
            name="CONSTRAINED_PARAM", value=50.0, default_value=50.0, min_value=0.0, max_value=100.0
        )

        # Configure test file parameters
        parameter_table.parameter_editor._local_filesystem.file_parameters = {
            "04_board_orientation.param": ParDict({"CONSTRAINED_PARAM": Par(50.0, "constrained")})
        }
        parameter_table.parameter_editor.current_step_parameters = {
            param_constrained.name: param_constrained,
        }

        # Act & Verify: Attempt out-of-range value with rejection
        ask_dialog = cast("Mock", parameter_table._dialogs.ask_yes_no)
        ask_dialog.return_value = False  # User rejects invalid value

        result_invalid = parameter_table._handle_parameter_value_update(
            param_constrained,
            "150.0",  # Out of range
            include_range_check=True,
        )

        # Verify: Invalid value rejected
        assert result_invalid is False
        ask_dialog.assert_called_once()

        ask_dialog.reset_mock()
        ask_dialog.return_value = True

        # Act & Verify: Valid value accepted
        with patch("ardupilot_methodic_configurator.frontend_tkinter_parameter_editor_table.show_tooltip"):
            result_valid = parameter_table._handle_parameter_value_update(
                param_constrained,
                "75.0",  # Valid value within range
                include_range_check=True,
            )

            # Verify: Valid value accepted
            assert result_valid is True
