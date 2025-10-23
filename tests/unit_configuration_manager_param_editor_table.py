#!/usr/bin/env python3

"""
Unit tests for ConfigurationManager class - Parameter Editor Table API.

This file tests the ConfigurationManager methods used by the parameter editor table frontend.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2025 Amilcar Lucas

SPDX-License-Identifier: GPL-3.0-or-later
"""

from unittest.mock import MagicMock, patch

from ardupilot_methodic_configurator.data_model_par_dict import Par, ParDict

# pylint: disable=protected-access, too-few-public-methods


class TestParameterFilteringWorkflows:
    """Test parameter filtering business logic workflows."""

    def test_user_can_filter_fc_parameters_excluding_defaults_and_readonly(self, configuration_manager) -> None:
        """
        User can filter FC parameters to exclude default values and read-only parameters.

        GIVEN: A user has FC parameters with defaults and read-only parameters
        WHEN: They filter using _get_non_default_non_read_only_fc_params
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

        configuration_manager._flight_controller.fc_parameters = fc_params
        configuration_manager._local_filesystem.param_default_dict = default_params
        configuration_manager._local_filesystem.doc_dict = doc_dict

        # Act: Filter the parameters
        result = configuration_manager._get_non_default_non_read_only_fc_params()

        # Assert: Only non-default, writable parameters remain
        assert len(result) == 2
        assert "PARAM_NORMAL" in result
        assert "PARAM_WRITABLE" in result
        assert "PARAM_DEFAULT" not in result  # Filtered as default
        assert "PARAM_READONLY" not in result  # Filtered as read-only

    def test_user_receives_empty_result_when_no_fc_parameters_available(self, configuration_manager) -> None:
        """
        User receives empty result when no FC parameters are available for filtering.

        GIVEN: A user has no FC parameters available
        WHEN: They attempt to filter parameters
        THEN: An empty ParDict should be returned
        """
        # Arrange: No FC parameters available
        configuration_manager._flight_controller.fc_parameters = {}

        # Act: Attempt to filter empty parameters
        result = configuration_manager._get_non_default_non_read_only_fc_params()

        # Assert: Empty result returned
        assert len(result) == 0
        assert isinstance(result, ParDict)

    def test_user_can_filter_parameters_with_missing_documentation(self, configuration_manager) -> None:
        """
        User can filter parameters even when documentation is incomplete.

        GIVEN: A user has FC parameters with incomplete documentation
        WHEN: They filter parameters
        THEN: Parameters without documentation should be treated as writable
        """
        # Arrange: FC parameters with incomplete documentation
        fc_params = {
            "PARAM_WITH_DOCS": 5.0,  # Parameter with documentation
            "PARAM_NO_DOCS": 10.0,  # Parameter without documentation
        }

        doc_dict = {
            "PARAM_WITH_DOCS": {"ReadOnly": False},
            # PARAM_NO_DOCS missing from doc_dict
        }

        configuration_manager._flight_controller.fc_parameters = fc_params
        configuration_manager._local_filesystem.param_default_dict = ParDict()
        configuration_manager._local_filesystem.doc_dict = doc_dict

        # Act: Filter parameters with incomplete documentation
        result = configuration_manager._get_non_default_non_read_only_fc_params()

        # Assert: Both parameters included (missing docs treated as writable)
        assert len(result) == 2
        assert "PARAM_WITH_DOCS" in result
        assert "PARAM_NO_DOCS" in result


class TestParameterExportWorkflows:
    """Test parameter export business logic workflows."""

    def test_user_can_export_missing_parameters_with_range_filename(self, configuration_manager) -> None:
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

        configuration_manager._flight_controller.fc_parameters = {"test": "data"}
        configuration_manager._local_filesystem.file_parameters = amc_file_params

        # Act: Export missing/different parameters
        configuration_manager._export_fc_params_missing_or_different_in_amc_files(fc_params, "01_setup.param")

        # Assert: Export called with correct filename and parameters
        expected_filename = "fc_params_missing_or_different_in_the_amc_param_files_01_setup_to_01_setup.param"
        configuration_manager._local_filesystem.export_to_param.assert_called_once()
        args, kwargs = configuration_manager._local_filesystem.export_to_param.call_args

        assert args[1] == expected_filename
        assert kwargs["annotate_doc"] is False
        # Verify exported parameters contain differences
        exported_params = args[0]
        assert "FC_ONLY_PARAM" in exported_params
        assert "DIFFERENT_PARAM" in exported_params

    def test_user_sees_no_export_when_parameters_match_amc_files(self, configuration_manager) -> None:
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

        configuration_manager._flight_controller.fc_parameters = {"test": "data"}
        configuration_manager._local_filesystem.file_parameters = amc_file_params

        with patch("ardupilot_methodic_configurator.configuration_manager.logging_info") as mock_log:
            # Act: Attempt export with matching parameters
            configuration_manager._export_fc_params_missing_or_different_in_amc_files(matching_params, "01_setup.param")

            # Assert: No export occurred
            configuration_manager._local_filesystem.export_to_param.assert_not_called()
            mock_log.assert_called_once()
            log_call_args = mock_log.call_args[0]
            assert "No FC parameters are missing or different from AMC parameter files" in log_call_args[0]

    def test_user_handles_early_exit_when_no_fc_parameters(self, configuration_manager) -> None:
        """
        User handles graceful early exit when no FC parameters are available.

        GIVEN: A user has no FC parameters available
        WHEN: They attempt to export missing/different parameters
        THEN: The function should exit early without processing
        """
        # Arrange: No FC parameters available
        configuration_manager._flight_controller.fc_parameters = None

        # Act: Attempt export with no FC parameters
        configuration_manager._export_fc_params_missing_or_different_in_amc_files(ParDict(), "01_setup.param")

        # Assert: No processing occurred
        configuration_manager._local_filesystem.export_to_param.assert_not_called()

    def test_user_can_export_with_multi_file_range(self, configuration_manager) -> None:
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

        configuration_manager._flight_controller.fc_parameters = {"test": "data"}
        configuration_manager._local_filesystem.file_parameters = amc_file_params

        # Act: Export parameters with multi-file range
        configuration_manager._export_fc_params_missing_or_different_in_amc_files(fc_params, "03_final.param")

        # Assert: Filename reflects correct range
        expected_filename = "fc_params_missing_or_different_in_the_amc_param_files_01_basic_to_03_final.param"
        configuration_manager._local_filesystem.export_to_param.assert_called_once()
        args, _ = configuration_manager._local_filesystem.export_to_param.call_args
        assert args[1] == expected_filename

    def test_user_handles_unknown_first_filename_gracefully(self, configuration_manager) -> None:
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

        configuration_manager._flight_controller.fc_parameters = {"test": "data"}
        configuration_manager._local_filesystem.file_parameters = amc_file_params

        # Act: Export with no valid first config file
        configuration_manager._export_fc_params_missing_or_different_in_amc_files(fc_params, "00_default.param")

        # Assert: Uses 'unknown' for missing first filename
        expected_filename = "fc_params_missing_or_different_in_the_amc_param_files_unknown_to_00_default.param"
        configuration_manager._local_filesystem.export_to_param.assert_called_once()
        args, _ = configuration_manager._local_filesystem.export_to_param.call_args
        assert args[1] == expected_filename


class TestFileCopyWorkflows:
    """Test file copy and FC value workflows."""

    def test_user_can_check_if_fc_values_should_be_copied(self, configuration_manager) -> None:
        """
        User can check if FC values should be copied to file.

        GIVEN: A user has parameters with auto-changed-by settings
        WHEN: They check if FC values should be copied
        THEN: Correct decision should be made based on parameter metadata
        """
        # Arrange: Set up parameters with auto-changed-by
        configuration_manager._local_filesystem.file_parameters = {"test.param": {"PARAM1": Par(1.0), "PARAM2": Par(2.0)}}
        configuration_manager._local_filesystem.doc_dict = {
            "PARAM1": {"auto_changed_by": "system"},
            "PARAM2": {"auto_changed_by": "user"},
        }
        configuration_manager.current_step_parameters = ["PARAM1", "PARAM2"]
        configuration_manager._flight_controller.fc_parameters = {"PARAM1": 1.0, "PARAM2": 2.0}
        configuration_manager._local_filesystem.auto_changed_by = MagicMock(return_value="system")

        # Act: Check if FC values should be copied
        should_copy, relevant_fc_params, auto_changed_by = configuration_manager.should_copy_fc_values_to_file("test.param")

        # Assert: Should copy due to auto-changed-by system parameter
        assert should_copy is True
        assert relevant_fc_params == {"PARAM1": 1.0, "PARAM2": 2.0}
        assert auto_changed_by == "system"

    def test_user_handles_no_auto_changed_by_requirement(self, configuration_manager) -> None:
        """
        User handles case where no auto-changed-by requirement exists.

        GIVEN: A user has parameters without auto-changed-by settings
        WHEN: They check if FC values should be copied
        THEN: No copy should be needed
        """
        # Arrange: Set up parameters without auto-changed-by
        configuration_manager._local_filesystem.file_parameters = {"test.param": {"PARAM1": Par(1.0), "PARAM2": Par(2.0)}}
        configuration_manager._local_filesystem.doc_dict = {
            "PARAM1": {},
            "PARAM2": {},
        }
        configuration_manager.current_step_parameters = ["PARAM1", "PARAM2"]
        configuration_manager._flight_controller.fc_parameters = {"PARAM1": 1.0, "PARAM2": 2.0}
        configuration_manager._local_filesystem.auto_changed_by = MagicMock(return_value="")

        # Act: Check if FC values should be copied
        should_copy, relevant_fc_params, auto_changed_by = configuration_manager.should_copy_fc_values_to_file("test.param")

        # Assert: No copy needed
        assert should_copy is False
        assert relevant_fc_params is None
        assert auto_changed_by == ""

    def test_user_can_copy_fc_values_to_file(self, configuration_manager) -> None:
        """
        User can copy FC values to parameter file.

        GIVEN: A user has FC parameters that should be copied to file
        WHEN: They copy FC values to file
        THEN: FC values should be written to the parameter file
        """
        # Arrange: Set up FC parameters and file
        fc_params = {"PARAM1": 1.0, "PARAM2": 2.0}
        file_name = "test.param"

        configuration_manager._flight_controller.fc_parameters = fc_params
        configuration_manager._local_filesystem.file_parameters = {file_name: {"PARAM1": Par(0.0), "PARAM2": Par(0.0)}}
        configuration_manager.current_step_parameters = ["PARAM1", "PARAM2"]
        configuration_manager._local_filesystem.doc_dict = {"PARAM1": {"auto_changed_by": "system"}}
        configuration_manager._local_filesystem.auto_changed_by = MagicMock(return_value="system")

        # Mock the copy method to actually update the file parameters
        def mock_copy(selected_file, params) -> int:
            if selected_file in configuration_manager._local_filesystem.file_parameters:
                for param, value in params.items():
                    if param in configuration_manager._local_filesystem.file_parameters[selected_file]:
                        configuration_manager._local_filesystem.file_parameters[selected_file][param].value = value
                return len(params)
            return 0

        configuration_manager._local_filesystem.copy_fc_values_to_file.side_effect = mock_copy

        # Get relevant parameters first
        should_copy, relevant_fc_params, _auto_changed_by = configuration_manager.should_copy_fc_values_to_file(file_name)
        assert should_copy is True

        # Act: Copy FC values to file
        result = configuration_manager.copy_fc_values_to_file(file_name, relevant_fc_params)

        # Assert: FC values copied to file
        assert result is True
        assert configuration_manager._local_filesystem.file_parameters[file_name]["PARAM1"].value == 1.0
        assert configuration_manager._local_filesystem.file_parameters[file_name]["PARAM2"].value == 2.0

    def test_user_handles_failed_copy_operation(self, configuration_manager) -> None:
        """
        User handles failed copy operation gracefully.

        GIVEN: A user attempts to copy FC values to file
        WHEN: The parameters are not in the file (simulating failure)
        THEN: No parameters should be copied
        """
        # Arrange: Set up FC parameters but file doesn't have the parameters
        fc_params = {"PARAM1": 1.0}
        file_name = "test.param"

        configuration_manager._flight_controller.fc_parameters = fc_params
        configuration_manager._local_filesystem.file_parameters = {file_name: {"PARAM2": Par(2.0)}}  # Different parameter
        configuration_manager.current_step_parameters = ["PARAM1"]
        configuration_manager._local_filesystem.doc_dict = {"PARAM1": {"auto_changed_by": "system"}}
        configuration_manager._local_filesystem.auto_changed_by = MagicMock(return_value="system")

        # Get relevant parameters first
        should_copy, relevant_fc_params, _auto_changed_by = configuration_manager.should_copy_fc_values_to_file(file_name)
        assert should_copy is True

        # Act: Try to copy FC values to file
        result = configuration_manager.copy_fc_values_to_file(file_name, relevant_fc_params)

        # Assert: No parameters were copied (PARAM1 not in file)
        assert result is True  # Method returns True even if 0 parameters copied
        # PARAM1 should not be in the file parameters
        assert "PARAM1" not in configuration_manager._local_filesystem.file_parameters[file_name]


class TestFileNavigationWorkflows:
    """Test file navigation and jump options workflows."""

    def test_user_can_get_file_jump_options(self, configuration_manager) -> None:
        """
        User can get file jump options for navigation.

        GIVEN: A user has multiple parameter files
        WHEN: They request file jump options
        THEN: Appropriate jump options should be returned
        """
        # Arrange: Set up parameter files and mock jump options
        jump_options = {"00_default.param": "Go to default", "complete.param": "Go to complete"}
        configuration_manager._local_filesystem.jump_possible = MagicMock(return_value=jump_options)

        # Act: Get file jump options
        result = configuration_manager.get_file_jump_options("01_setup.param")

        # Assert: Jump options returned
        assert isinstance(result, dict)
        assert result == jump_options
        configuration_manager._local_filesystem.jump_possible.assert_called_once_with("01_setup.param")


class TestParameterUploadWorkflows:
    """Test parameter upload business logic workflows."""

    def test_user_can_upload_parameters_requiring_reset_successfully(self, configuration_manager) -> None:
        """
        User can upload parameters that require reset to the flight controller.

        GIVEN: A user has parameters that require reset according to documentation
        WHEN: They upload parameters requiring reset
        THEN: Parameters should be uploaded and reset status should be reported correctly
        """
        # Arrange: Set up parameters requiring reset
        selected_params = {
            "PARAM_RESET_REQ": Par(1.0, "Requires reset"),
            "PARAM_TYPE": Par(2.0, "Type parameter"),
        }

        configuration_manager._flight_controller.fc_parameters = {}
        configuration_manager._local_filesystem.doc_dict = {
            "PARAM_RESET_REQ": {"RebootRequired": True},
            "PARAM_TYPE": {"RebootRequired": False},
        }

        # Mock the callbacks
        mock_ask_confirmation = MagicMock(return_value=True)
        mock_show_error = MagicMock()

        # Mock successful reset and reconnect (returns None for no error)
        configuration_manager._reset_and_reconnect_flight_controller = MagicMock(return_value=None)

        # Act: Upload parameters requiring reset
        reset_required = configuration_manager.upload_parameters_that_require_reset_workflow(
            selected_params, mock_ask_confirmation, mock_show_error
        )

        # Assert: Reset required
        assert reset_required is True
        mock_show_error.assert_not_called()

    def test_user_handles_parameter_upload_errors_gracefully(self, configuration_manager) -> None:
        """
        User handles parameter upload errors gracefully with error messages.

        GIVEN: A user has parameters that will cause upload errors
        WHEN: They upload parameters with errors
        THEN: Error messages should be collected and returned
        """
        # Arrange: Mock set_param to raise ValueError and ensure parameter will be set
        selected_params = {"INVALID_PARAM": Par(1.0, "Invalid value")}
        configuration_manager._flight_controller.fc_parameters = {}  # Parameter not in FC, so it will try to set
        configuration_manager._local_filesystem.doc_dict = {"INVALID_PARAM": {"RebootRequired": True}}
        configuration_manager._flight_controller.set_param.side_effect = ValueError("Invalid parameter value")

        # Mock the callbacks
        mock_ask_confirmation = MagicMock(return_value=True)
        mock_show_error = MagicMock()

        # Act: Upload parameters with errors
        reset_required = configuration_manager.upload_parameters_that_require_reset_workflow(
            selected_params, mock_ask_confirmation, mock_show_error
        )

        # Assert: Errors handled via callback
        assert reset_required is False  # No successful uploads
        mock_show_error.assert_called_once()
        error_call_args = mock_show_error.call_args[0]
        assert "Failed to set parameter" in error_call_args[1]  # Second argument is the error message
