#!/usr/bin/env python3

"""
Behavior-focused tests for the refactored ParameterEditorTable.

This demonstrates how to test the refactored version properly by focusing on behavior
rather than implementation details and using minimal mocking.

This file is part of Ardupilot methodic configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2025 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

from unittest.mock import MagicMock

import pytest

from ardupilot_methodic_configurator.annotate_params import Par
from ardupilot_methodic_configurator.backend_filesystem import LocalFilesystem
from ardupilot_methodic_configurator.frontend_tkinter_parameter_editor_table_refactored import (
    MockMessageHandler,
    MockParameterValidator,
    ParameterEditorTableRefactored,
    ParameterStateManager,
    ParameterValidationResult,
    ParameterValidator,
)


class TestParameterValidationBehavior:
    """Test parameter validation behavior without UI dependencies."""

    @pytest.fixture
    def validator(self) -> ParameterValidator:
        """Create a validator with test parameter metadata."""
        doc_dict = {
            "TEST_PARAM": {"min": 0.0, "max": 100.0},
            "UNBOUNDED_PARAM": {},
            "MIN_ONLY_PARAM": {"min": 10.0},
            "MAX_ONLY_PARAM": {"max": 50.0},
        }
        return ParameterValidator(doc_dict)

    def test_valid_float_validation(self, validator: ParameterValidator) -> None:
        """Test validation of valid float values."""
        result = validator.validate_value_format("42.5", "TEST_PARAM")

        assert result.is_valid is True
        assert result.value == 42.5
        assert result.error_message == ""

    def test_invalid_float_validation(self, validator: ParameterValidator) -> None:
        """Test validation of invalid float values."""
        result = validator.validate_value_format("not_a_number", "TEST_PARAM")

        assert result.is_valid is False
        assert str(result.value) == "nan"
        assert "must be a valid float" in result.error_message

    def test_infinity_rejection(self, validator: ParameterValidator) -> None:
        """Test that infinity values are rejected."""
        result = validator.validate_value_format("inf", "TEST_PARAM")

        assert result.is_valid is False
        assert "must be a finite number" in result.error_message

    def test_nan_rejection(self, validator: ParameterValidator) -> None:
        """Test that NaN values are rejected."""
        result = validator.validate_value_format("nan", "TEST_PARAM")

        assert result.is_valid is False
        assert "must be a finite number" in result.error_message

    def test_value_within_bounds(self, validator: ParameterValidator) -> None:
        """Test validation of values within bounds."""
        result = validator.validate_bounds(50.0, "TEST_PARAM")

        assert result.is_valid is True
        assert result.value == 50.0
        assert result.error_message == ""

    def test_value_below_minimum_bound(self, validator: ParameterValidator) -> None:
        """Test validation of values below minimum bound."""
        result = validator.validate_bounds(-5.0, "TEST_PARAM")

        assert result.is_valid is False
        assert result.value == -5.0
        assert "should be greater than 0.0" in result.error_message

    def test_value_above_maximum_bound(self, validator: ParameterValidator) -> None:
        """Test validation of values above maximum bound."""
        result = validator.validate_bounds(150.0, "TEST_PARAM")

        assert result.is_valid is False
        assert result.value == 150.0
        assert "should be smaller than 100.0" in result.error_message

    def test_unbounded_parameter_always_valid(self, validator: ParameterValidator) -> None:
        """Test that parameters without bounds are always valid."""
        result = validator.validate_bounds(999999.0, "UNBOUNDED_PARAM")

        assert result.is_valid is True
        assert result.value == 999999.0

    def test_value_change_detection(self, validator: ParameterValidator) -> None:
        """Test detection of value changes."""
        # Values that are different beyond tolerance
        assert validator.is_value_changed(0.0, 1.0) is True

        # Values that are the same within tolerance
        assert validator.is_value_changed(1.0, 1.0) is False
        assert validator.is_value_changed(1.0, 1.0000001) is False  # Very small difference


class TestParameterStateManagerBehavior:
    """Test parameter state management behavior."""

    @pytest.fixture
    def state_manager(self) -> ParameterStateManager:
        """Create a fresh state manager for each test."""
        return ParameterStateManager()

    def test_initial_state_is_not_edited(self, state_manager: ParameterStateManager) -> None:
        """Test that initial state shows no parameters edited."""
        assert state_manager.parameter_edited is False

    def test_marking_parameter_edited_changes_state(self, state_manager: ParameterStateManager) -> None:
        """Test that marking a parameter as edited changes the state."""
        state_manager.mark_parameter_edited("TEST_PARAM")

        assert state_manager.parameter_edited is True

    def test_resetting_edited_state(self, state_manager: ParameterStateManager) -> None:
        """Test resetting the edited state."""
        state_manager.mark_parameter_edited("TEST_PARAM")
        state_manager.reset_edited_state()

        assert state_manager.parameter_edited is False

    def test_upload_selection_management(self, state_manager: ParameterStateManager) -> None:
        """Test upload selection management."""
        # Default selection
        assert state_manager.get_upload_selection("NEW_PARAM") is True

        # Set selection
        state_manager.set_upload_selection("TEST_PARAM", False)
        assert state_manager.get_upload_selection("TEST_PARAM") is False

        # Change selection
        state_manager.set_upload_selection("TEST_PARAM", True)
        assert state_manager.get_upload_selection("TEST_PARAM") is True


class TestParameterEditorBehaviorFocused:
    """Test parameter editor behavior using the refactored class."""

    @pytest.fixture
    def test_filesystem(self) -> LocalFilesystem:
        """Create a mock filesystem with test data."""
        filesystem = MagicMock(spec=LocalFilesystem)
        filesystem.doc_dict = {
            "TEST_PARAM": {"min": 0.0, "max": 100.0, "unit": "m/s"},
            "BOUNDED_PARAM": {"min": -10.0, "max": 10.0},
        }
        filesystem.file_parameters = {
            "test_file.param": {
                "TEST_PARAM": Par(50.0, "Test parameter"),
                "BOUNDED_PARAM": Par(5.0, "Bounded parameter"),
            }
        }
        filesystem.param_default_dict = {
            "TEST_PARAM": Par(0.0, "Default"),
            "BOUNDED_PARAM": Par(0.0, "Default"),
        }
        filesystem.configuration_steps = {}
        filesystem.forced_parameters = {}
        filesystem.derived_parameters = {}
        filesystem.get_eval_variables.return_value = {}
        return filesystem

    @pytest.fixture
    def test_message_handler(self) -> MockMessageHandler:
        """Create a test message handler."""
        return MockMessageHandler()

    @pytest.fixture
    def parameter_editor(
        self, test_filesystem: LocalFilesystem, test_message_handler: MockMessageHandler
    ) -> ParameterEditorTableRefactored:
        """Create a parameter editor for testing."""
        return ParameterEditorTableRefactored.create_for_testing(
            local_filesystem=test_filesystem, message_handler=test_message_handler
        )

    def test_valid_parameter_value_validation(self, parameter_editor: ParameterEditorTableRefactored) -> None:
        """Test validation of valid parameter values."""
        result = parameter_editor.validate_parameter_value("75.5", "TEST_PARAM")

        assert result.is_valid is True
        assert result.value == 75.5
        assert result.error_message == ""

    def test_invalid_parameter_value_validation(self, parameter_editor: ParameterEditorTableRefactored) -> None:
        """Test validation of invalid parameter values."""
        result = parameter_editor.validate_parameter_value("invalid", "TEST_PARAM")

        assert result.is_valid is False
        assert str(result.value) == "nan"
        assert "must be a valid float" in result.error_message

    def test_out_of_bounds_parameter_validation(self, parameter_editor: ParameterEditorTableRefactored) -> None:
        """Test validation of out-of-bounds parameter values."""
        result = parameter_editor.validate_parameter_value("150.0", "TEST_PARAM")

        assert result.is_valid is False
        assert result.value == 150.0
        assert "should be smaller than 100.0" in result.error_message

    def test_successful_parameter_update(self, parameter_editor: ParameterEditorTableRefactored) -> None:
        """Test successful parameter value update."""
        parameter_editor.current_file = "test_file.param"

        changed = parameter_editor.update_parameter_value("TEST_PARAM", 75.0)

        assert changed is True
        assert parameter_editor.local_filesystem.file_parameters["test_file.param"]["TEST_PARAM"].value == 75.0
        assert parameter_editor.get_at_least_one_param_edited() is True

    def test_parameter_update_with_same_value(self, parameter_editor: ParameterEditorTableRefactored) -> None:
        """Test parameter update with the same value (no change)."""
        parameter_editor.current_file = "test_file.param"

        # Get current value
        current_value = parameter_editor.local_filesystem.file_parameters["test_file.param"]["TEST_PARAM"].value

        changed = parameter_editor.update_parameter_value("TEST_PARAM", current_value)

        assert changed is False
        assert parameter_editor.get_at_least_one_param_edited() is False

    def test_parameter_update_nonexistent_file(self, parameter_editor: ParameterEditorTableRefactored) -> None:
        """Test parameter update with nonexistent file."""
        parameter_editor.current_file = "nonexistent_file.param"

        changed = parameter_editor.update_parameter_value("TEST_PARAM", 75.0)

        assert changed is False

    def test_parameter_update_nonexistent_parameter(self, parameter_editor: ParameterEditorTableRefactored) -> None:
        """Test parameter update with nonexistent parameter."""
        parameter_editor.current_file = "test_file.param"

        changed = parameter_editor.update_parameter_value("NONEXISTENT_PARAM", 75.0)

        assert changed is False

    def test_process_parameter_change_valid_input(
        self, parameter_editor: ParameterEditorTableRefactored, test_message_handler: MockMessageHandler
    ) -> None:
        """Test processing valid parameter change."""
        parameter_editor.current_file = "test_file.param"

        success = parameter_editor.process_parameter_change("TEST_PARAM", "75.0")

        assert success is True
        assert parameter_editor.local_filesystem.file_parameters["test_file.param"]["TEST_PARAM"].value == 75.0
        assert len(test_message_handler.error_calls) == 0

    def test_process_parameter_change_invalid_input(
        self, parameter_editor: ParameterEditorTableRefactored, test_message_handler: MockMessageHandler
    ) -> None:
        """Test processing invalid parameter change."""
        parameter_editor.current_file = "test_file.param"

        success = parameter_editor.process_parameter_change("TEST_PARAM", "invalid")

        assert success is False
        assert len(test_message_handler.error_calls) == 1
        assert "Invalid Value" in test_message_handler.error_calls[0][0]

    def test_process_parameter_change_out_of_bounds_rejected(
        self, parameter_editor: ParameterEditorTableRefactored, test_message_handler: MockMessageHandler
    ) -> None:
        """Test processing out-of-bounds parameter change that user rejects."""
        parameter_editor.current_file = "test_file.param"
        test_message_handler.set_confirmation_response(False)  # User rejects

        success = parameter_editor.process_parameter_change("TEST_PARAM", "150.0")

        assert success is False
        assert len(test_message_handler.confirmation_calls) == 1
        assert "Out-of-bounds Value" in test_message_handler.confirmation_calls[0][0]

    def test_process_parameter_change_out_of_bounds_accepted(
        self, parameter_editor: ParameterEditorTableRefactored, test_message_handler: MockMessageHandler
    ) -> None:
        """Test processing out-of-bounds parameter change that user accepts."""
        parameter_editor.current_file = "test_file.param"
        test_message_handler.set_confirmation_response(True)  # User accepts

        success = parameter_editor.process_parameter_change("TEST_PARAM", "150.0")

        assert success is True
        assert parameter_editor.local_filesystem.file_parameters["test_file.param"]["TEST_PARAM"].value == 150.0
        assert len(test_message_handler.confirmation_calls) == 1

    def test_parameter_row_data_creation(self, parameter_editor: ParameterEditorTableRefactored) -> None:
        """Test creation of parameter row data."""
        param = Par(50.0, "Test parameter")
        fc_parameters = {"TEST_PARAM": 45.0}

        row_data = parameter_editor.get_parameter_row_data("TEST_PARAM", param, fc_parameters)

        assert row_data.param_name == "TEST_PARAM"
        assert row_data.param == param
        assert row_data.param_metadata["min"] == 0.0
        assert row_data.param_metadata["max"] == 100.0
        assert row_data.fc_parameters == fc_parameters
        assert isinstance(row_data.show_upload_column, bool)

    def test_ui_complexity_affects_upload_column(self, parameter_editor: ParameterEditorTableRefactored) -> None:
        """Test that UI complexity affects upload column visibility."""
        # Normal complexity should show upload column
        parameter_editor.parameter_editor.ui_complexity = "normal"
        assert parameter_editor._should_show_upload_column() is True

        # Simple complexity should hide upload column
        parameter_editor.parameter_editor.ui_complexity = "simple"
        assert parameter_editor._should_show_upload_column() is False

        # Advanced complexity should show upload column
        parameter_editor.parameter_editor.ui_complexity = "advanced"
        assert parameter_editor._should_show_upload_column() is True

    def test_forced_parameter_detection(self, parameter_editor: ParameterEditorTableRefactored) -> None:
        """Test detection of forced parameters."""
        parameter_editor.current_file = "test_file.param"
        parameter_editor.local_filesystem.forced_parameters = {"test_file.param": {"FORCED_PARAM": Par(10.0, "Forced value")}}

        is_forced, param_type = parameter_editor._is_forced_or_derived_parameter("FORCED_PARAM")

        assert is_forced is True
        assert param_type == "forced"

    def test_derived_parameter_detection(self, parameter_editor: ParameterEditorTableRefactored) -> None:
        """Test detection of derived parameters."""
        parameter_editor.current_file = "test_file.param"
        parameter_editor.local_filesystem.derived_parameters = {
            "test_file.param": {"DERIVED_PARAM": Par(20.0, "Derived value")}
        }

        is_derived, param_type = parameter_editor._is_forced_or_derived_parameter("DERIVED_PARAM")

        assert is_derived is True
        assert param_type == "derived"

    def test_normal_parameter_detection(self, parameter_editor: ParameterEditorTableRefactored) -> None:
        """Test detection of normal (non-forced, non-derived) parameters."""
        parameter_editor.current_file = "test_file.param"

        is_special, param_type = parameter_editor._is_forced_or_derived_parameter("TEST_PARAM")

        assert is_special is False
        assert param_type == ""


class TestMockValidatorBehavior:
    """Test the mock validator for improved test control."""

    @pytest.fixture
    def mock_validator(self) -> MockParameterValidator:
        """Create a mock validator for testing."""
        return MockParameterValidator()

    def test_custom_bounds_setting(self, mock_validator: MockParameterValidator) -> None:
        """Test setting custom bounds for testing."""
        mock_validator.set_parameter_bounds("TEST_PARAM", min_val=5.0, max_val=95.0)

        result = mock_validator.validate_bounds(100.0, "TEST_PARAM")

        assert result.is_valid is False
        assert "should be smaller than 95.0" in result.error_message

    def test_custom_validation_results(self, mock_validator: MockParameterValidator) -> None:
        """Test setting custom validation results."""
        custom_result = ParameterValidationResult(False, 50.0, "Custom error")
        mock_validator.set_validation_result("TEST_PARAM", 50.0, custom_result)

        # This would normally require implementing the lookup in the mock
        # For now, this demonstrates the concept


class MockMessageHandlerBehavior:
    """Test the test message handler behavior."""

    @pytest.fixture
    def message_handler(self) -> MockMessageHandler:
        """Create a test message handler."""
        return MockMessageHandler()

    def test_error_message_recording(self, message_handler: MockMessageHandler) -> None:
        """Test that error messages are properly recorded."""
        message_handler.show_error("Test Title", "Test Message")

        assert len(message_handler.error_calls) == 1
        assert message_handler.error_calls[0] == ("Test Title", "Test Message")
        assert message_handler.get_last_error() == ("Test Title", "Test Message")

    def test_confirmation_message_recording(self, message_handler: MockMessageHandler) -> None:
        """Test that confirmation messages are properly recorded."""
        message_handler.set_confirmation_response(True)
        result = message_handler.show_confirmation("Confirm Title", "Confirm Message")

        assert result is True
        assert len(message_handler.confirmation_calls) == 1
        assert message_handler.confirmation_calls[0] == ("Confirm Title", "Confirm Message")

    def test_confirmation_response_setting(self, message_handler: MockMessageHandler) -> None:
        """Test setting different confirmation responses."""
        # Test True response
        message_handler.set_confirmation_response(True)
        assert message_handler.show_confirmation("Title", "Message") is True

        # Test False response
        message_handler.set_confirmation_response(False)
        assert message_handler.show_confirmation("Title", "Message") is False

    def test_multiple_message_tracking(self, message_handler: MockMessageHandler) -> None:
        """Test tracking multiple messages."""
        message_handler.show_error("Error 1", "Message 1")
        message_handler.show_error("Error 2", "Message 2")
        message_handler.show_confirmation("Confirm 1", "Message 1")
        message_handler.show_confirmation("Confirm 2", "Message 2")

        assert len(message_handler.error_calls) == 2
        assert len(message_handler.confirmation_calls) == 2
        assert message_handler.get_last_error() == ("Error 2", "Message 2")
        assert message_handler.get_last_confirmation() == ("Confirm 2", "Message 2")


class TestIntegrationWorkflows:
    """Integration tests that demonstrate realistic usage scenarios."""

    @pytest.fixture
    def complete_setup(self) -> tuple[ParameterEditorTableRefactored, MockMessageHandler]:
        """Create a complete setup for integration testing."""
        filesystem = MagicMock(spec=LocalFilesystem)
        filesystem.doc_dict = {
            "PARAM_1": {"min": 0.0, "max": 100.0, "unit": "m/s"},
            "PARAM_2": {"min": -50.0, "max": 50.0, "unit": "degrees"},
            "UNBOUNDED": {"unit": "none"},
        }
        filesystem.file_parameters = {
            "test.param": {
                "PARAM_1": Par(25.0, "First parameter"),
                "PARAM_2": Par(-10.0, "Second parameter"),
                "UNBOUNDED": Par(1000.0, "Unbounded parameter"),
            }
        }
        filesystem.param_default_dict = {
            "PARAM_1": Par(0.0, "Default"),
            "PARAM_2": Par(0.0, "Default"),
            "UNBOUNDED": Par(0.0, "Default"),
        }
        filesystem.configuration_steps = {}
        filesystem.forced_parameters = {}
        filesystem.derived_parameters = {}
        filesystem.get_eval_variables.return_value = {}

        message_handler = MockMessageHandler()

        editor = ParameterEditorTableRefactored.create_for_testing(
            local_filesystem=filesystem, message_handler=message_handler
        )

        return editor, message_handler

    def test_complete_parameter_validation_workflow(self, complete_setup) -> None:
        """Test a complete parameter validation and update workflow."""
        editor, message_handler = complete_setup
        editor.current_file = "test.param"

        # Test valid change
        success = editor.process_parameter_change("PARAM_1", "75.0")
        assert success is True
        assert editor.local_filesystem.file_parameters["test.param"]["PARAM_1"].value == 75.0
        assert editor.get_at_least_one_param_edited() is True
        assert len(message_handler.error_calls) == 0

        # Test invalid input
        success = editor.process_parameter_change("PARAM_1", "invalid")
        assert success is False
        assert len(message_handler.error_calls) == 1

        # Test out-of-bounds with user rejection
        message_handler.set_confirmation_response(False)
        success = editor.process_parameter_change("PARAM_1", "150.0")
        assert success is False
        assert len(message_handler.confirmation_calls) == 1

        # Test out-of-bounds with user acceptance
        message_handler.set_confirmation_response(True)
        success = editor.process_parameter_change("PARAM_1", "150.0")
        assert success is True
        assert editor.local_filesystem.file_parameters["test.param"]["PARAM_1"].value == 150.0

    def test_multiple_parameter_changes_workflow(self, complete_setup) -> None:
        """Test workflow with multiple parameter changes."""
        editor, message_handler = complete_setup
        editor.current_file = "test.param"

        # Change multiple parameters
        changes = [
            ("PARAM_1", "80.0"),
            ("PARAM_2", "30.0"),
            ("UNBOUNDED", "5000.0"),
        ]

        for param_name, value in changes:
            success = editor.process_parameter_change(param_name, value)
            assert success is True

        # Verify all changes
        assert editor.local_filesystem.file_parameters["test.param"]["PARAM_1"].value == 80.0
        assert editor.local_filesystem.file_parameters["test.param"]["PARAM_2"].value == 30.0
        assert editor.local_filesystem.file_parameters["test.param"]["UNBOUNDED"].value == 5000.0
        assert editor.get_at_least_one_param_edited() is True
        assert len(message_handler.error_calls) == 0

    def test_state_management_across_operations(self, complete_setup) -> None:
        """Test state management across multiple operations."""
        editor, _ = complete_setup
        editor.current_file = "test.param"

        # Initial state
        assert editor.get_at_least_one_param_edited() is False

        # Make a change
        editor.process_parameter_change("PARAM_1", "50.0")
        assert editor.get_at_least_one_param_edited() is True

        # Reset state
        editor.set_at_least_one_param_edited(False)
        assert editor.get_at_least_one_param_edited() is False

        # Make another change
        editor.process_parameter_change("PARAM_2", "25.0")
        assert editor.get_at_least_one_param_edited() is True


if __name__ == "__main__":
    pytest.main([__file__])
