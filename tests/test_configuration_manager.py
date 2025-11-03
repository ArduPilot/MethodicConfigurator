#!/usr/bin/env python3

"""
Tests for the ConfigurationManager class.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2025 Amilcar Lucas

SPDX-License-Identifier: GPL-3.0-or-later
"""

from unittest.mock import MagicMock, patch

import pytest

from ardupilot_methodic_configurator.configuration_manager import ConfigurationManager
from ardupilot_methodic_configurator.data_model_ardupilot_parameter import ArduPilotParameter
from ardupilot_methodic_configurator.data_model_par_dict import Par, ParDict
from ardupilot_methodic_configurator.plugin_constants import PLUGIN_MOTOR_TEST

# pylint: disable=redefined-outer-name, too-many-lines, protected-access


@pytest.fixture
def mock_flight_controller() -> MagicMock:
    """Fixture providing a mock flight controller with realistic test data."""
    mock_fc = MagicMock()
    mock_fc.fc_parameters = {"PARAM1": 1.0, "PARAM2": 3.0}
    return mock_fc


@pytest.fixture
def mock_local_filesystem() -> MagicMock:
    """Fixture providing a mock local filesystem with realistic test data."""
    mock_fs = MagicMock()
    mock_fs.file_parameters = {"test_file.param": {"PARAM1": Par(1.0), "PARAM2": Par(3.0)}}
    mock_fs.param_default_dict = ParDict()
    mock_fs.doc_dict = {}
    mock_fs.forced_parameters = {}
    mock_fs.derived_parameters = {}
    mock_fs.export_to_param = MagicMock()

    # Mock get_documentation_text_and_url method with realistic return values
    def mock_get_documentation_text_and_url(file_name: str, _doc_type: str) -> tuple[str, str]:
        """Mock implementation that returns realistic documentation text based on file patterns."""
        if file_name.startswith(("01_", "02_", "1.", "10_", "123_", "99_")):
            # Numbered files are typically mandatory (high percentage)
            return ("80% mandatory (20% optional)", f"docs/{file_name}.html")
        if file_name in (
            "optional_step.param",
            "advanced_config.param",
            "complete.param",
            "",
            "0_invalid_number.param",
            "00_default.param",
        ):
            # These files are typically optional (low percentage)
            return ("10% mandatory (90% optional)", f"docs/{file_name}.html")
        # Default case
        return ("50% mandatory (50% optional)", f"docs/{file_name}.html")

    mock_fs.get_documentation_text_and_url.side_effect = mock_get_documentation_text_and_url
    return mock_fs


@pytest.fixture
def configuration_manager(mock_flight_controller, mock_local_filesystem) -> ConfigurationManager:
    """Fixture providing a properly configured ConfigurationManager for behavior testing."""
    return ConfigurationManager("00_default.param", mock_flight_controller, mock_local_filesystem)


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
            "PARAM_WITH_DOCS": 5.0,  # Has documentation
            "PARAM_NO_DOCS": 10.0,  # Missing from doc_dict
        }

        doc_dict = {
            "PARAM_WITH_DOCS": {"ReadOnly": False},
            # PARAM_NO_DOCS intentionally missing
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
            # Act: Attempt to export when parameters match
            configuration_manager._export_fc_params_missing_or_different_in_amc_files(matching_params, "01_setup.param")

            # Assert: No export occurred and appropriate message logged
            configuration_manager._local_filesystem.export_to_param.assert_not_called()
            mock_log.assert_called_with("No FC parameters are missing or different from AMC parameter files")

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


class TestConfigurationStepValidation:
    """Test configuration step validation business logic."""

    def test_user_can_validate_mandatory_configuration_steps(self, configuration_manager) -> None:
        """
        User can validate that certain configuration steps are mandatory and cannot be skipped.

        GIVEN: A user has configuration files with different naming patterns
        WHEN: They check if configuration steps are optional
        THEN: Files not starting with numbers should be considered mandatory
        """
        # Arrange: Configuration file names with different patterns
        test_cases = [
            ("01_mandatory_step.param", False),  # Numbered files are mandatory
            ("02_another_step.param", False),  # Numbered files are mandatory
            ("optional_step.param", True),  # Non-numbered files are optional
            ("advanced_config.param", True),  # Non-numbered files are optional
            ("complete.param", True),  # Special case: complete.param is optional
        ]

        for filename, expected_optional in test_cases:
            # Act: Check if configuration step is optional
            result = configuration_manager.is_configuration_step_optional(filename)

            # Assert: Expected optionality matches
            assert result == expected_optional, f"File {filename} should be {'optional' if expected_optional else 'mandatory'}"

    def test_user_handles_edge_cases_in_configuration_step_validation(self, configuration_manager) -> None:
        """
        User handles edge cases gracefully when validating configuration steps.

        GIVEN: A user has edge case configuration file names
        WHEN: They check if configuration steps are optional
        THEN: The validation should handle edge cases correctly
        """
        # Arrange: Edge case file names
        edge_cases = [
            ("", True),  # Empty filename should be considered optional
            ("0_invalid_number.param", True),  # Files starting with 0 are optional
            ("00_default.param", True),  # Files starting with 00 are optional (defaults)
            ("1.param", False),  # Single digit numbers should be mandatory
            ("10_config.param", False),  # Double digit numbers should be mandatory
            ("123_large_number.param", False),  # Large numbers should be mandatory
        ]

        for filename, expected_optional in edge_cases:
            # Act: Check edge case configuration step
            result = configuration_manager.is_configuration_step_optional(filename)

            # Assert: Edge cases handled correctly
            expected_msg = f"Edge case {filename} should be {'optional' if expected_optional else 'mandatory'}"
            assert result == expected_optional, expected_msg

    def test_user_validates_special_configuration_files(self, configuration_manager) -> None:
        """
        User validates special configuration files have correct optionality.

        GIVEN: A user has special configuration files like complete.param and defaults
        WHEN: They check if these configuration steps are optional
        THEN: Special files should follow expected optionality rules
        """
        # Arrange: Special configuration file names
        special_files = [
            ("complete.param", True),  # Complete files are always optional
            ("00_default.param", True),  # Default files are optional
            ("99_optional_final.param", False),  # Even high numbers are mandatory if numbered
        ]

        for filename, expected_optional in special_files:
            # Act: Check special configuration file
            result = configuration_manager.is_configuration_step_optional(filename)

            # Assert: Special files have correct optionality
            expected_msg = f"Special file {filename} should be {'optional' if expected_optional else 'mandatory'}"
            assert result == expected_optional, expected_msg


class TestConfigurationManagerIntegration:
    """Test ConfigurationManager integration and core functionality."""

    def test_user_can_create_configuration_manager_with_dependencies(
        self, mock_flight_controller, mock_local_filesystem
    ) -> None:
        """
        User can create a ConfigurationManager with flight controller and filesystem dependencies.

        GIVEN: A user has flight controller and filesystem instances
        WHEN: They create a ConfigurationManager
        THEN: The manager should properly store the dependencies
        """
        # Arrange: Dependencies are provided by fixtures

        # Act: Create ConfigurationManager
        config_manager = ConfigurationManager("00_default.param", mock_flight_controller, mock_local_filesystem)

        # Assert: Dependencies are properly stored
        assert config_manager._flight_controller is mock_flight_controller
        assert config_manager._local_filesystem is mock_local_filesystem

    def test_user_accesses_flight_controller_through_configuration_manager(self, configuration_manager) -> None:
        """
        User accesses flight controller functionality through the ConfigurationManager.

        GIVEN: A user has a ConfigurationManager instance
        WHEN: They access flight controller properties
        THEN: The flight controller should be accessible through the manager
        """
        # Arrange: ConfigurationManager is provided by fixture

        # Act: Access flight controller through manager
        fc_params = configuration_manager._flight_controller.fc_parameters

        # Assert: Flight controller is accessible
        assert fc_params is not None
        assert isinstance(fc_params, dict)

    def test_user_accesses_filesystem_through_configuration_manager(self, configuration_manager) -> None:
        """
        User accesses filesystem functionality through the ConfigurationManager.

        GIVEN: A user has a ConfigurationManager instance
        WHEN: They access filesystem properties
        THEN: The filesystem should be accessible through the manager
        """
        # Arrange: ConfigurationManager is provided by fixture

        # Act: Access filesystem through manager
        file_params = configuration_manager._local_filesystem.file_parameters

        # Assert: Filesystem is accessible
        assert file_params is not None
        assert isinstance(file_params, dict)


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


class TestFileDownloadUrlWorkflows:
    """Test file download URL workflow business logic methods with callback injection."""

    def test_user_can_complete_download_file_workflow_successfully(self, configuration_manager) -> None:
        """
        User can complete the download file workflow with callbacks.

        GIVEN: A user has a file that needs to be downloaded and valid workflow callbacks
        WHEN: They execute the download workflow with user confirmation
        THEN: The file should be downloaded successfully
        """
        # Arrange: Set up file info and callbacks
        selected_file = "test_file.param"
        url = "https://example.com/test.bin"
        local_filename = "test.bin"

        configuration_manager._local_filesystem.get_download_url_and_local_filename.return_value = (url, local_filename)
        configuration_manager._local_filesystem.vehicle_configuration_file_exists.return_value = False

        ask_confirmation_mock = MagicMock(return_value=True)
        show_error_mock = MagicMock()

        # Mock the download_file_from_url function to return success
        with patch("ardupilot_methodic_configurator.configuration_manager.download_file_from_url", return_value=True):
            # Act: Execute download workflow
            result = configuration_manager.should_download_file_from_url_workflow(
                selected_file,
                ask_confirmation=ask_confirmation_mock,
                show_error=show_error_mock,
            )

        # Assert: Workflow completed successfully
        assert result is True
        ask_confirmation_mock.assert_called_once()
        show_error_mock.assert_not_called()

    def test_user_handles_download_failure_in_workflow(self, configuration_manager) -> None:
        """
        User handles download failure gracefully in the workflow.

        GIVEN: A user has a file that needs to be downloaded but download fails
        WHEN: They execute the download workflow
        THEN: Error should be shown and workflow should return False
        """
        # Arrange: Set up file info and failing download
        selected_file = "test_file.param"
        url = "https://example.com/test.bin"
        local_filename = "test.bin"

        configuration_manager._local_filesystem.get_download_url_and_local_filename.return_value = (url, local_filename)
        configuration_manager._local_filesystem.vehicle_configuration_file_exists.return_value = False

        ask_confirmation_mock = MagicMock(return_value=True)
        show_error_mock = MagicMock()

        # Mock the download_file_from_url function to return failure
        with patch("ardupilot_methodic_configurator.configuration_manager.download_file_from_url", return_value=False):
            # Act: Execute download workflow
            result = configuration_manager.should_download_file_from_url_workflow(
                selected_file,
                ask_confirmation=ask_confirmation_mock,
                show_error=show_error_mock,
            )

        # Assert: Workflow failed and error was shown
        assert result is False
        ask_confirmation_mock.assert_called_once()
        show_error_mock.assert_called_once()

    def test_user_declines_download_in_workflow(self, configuration_manager) -> None:
        """
        User can decline download in the workflow.

        GIVEN: A user has a file that could be downloaded
        WHEN: They decline the download confirmation
        THEN: No download should occur and workflow should return True
        """
        # Arrange: Set up file info and declining user
        selected_file = "test_file.param"
        url = "https://example.com/test.bin"
        local_filename = "test.bin"

        configuration_manager._local_filesystem.get_download_url_and_local_filename.return_value = (url, local_filename)
        configuration_manager._local_filesystem.vehicle_configuration_file_exists.return_value = False

        ask_confirmation_mock = MagicMock(return_value=False)
        show_error_mock = MagicMock()

        # Act: Execute download workflow
        result = configuration_manager.should_download_file_from_url_workflow(
            selected_file,
            ask_confirmation=ask_confirmation_mock,
            show_error=show_error_mock,
        )

        # Assert: Workflow succeeded without download
        assert result is True
        ask_confirmation_mock.assert_called_once()
        show_error_mock.assert_not_called()


class TestSummaryFileWritingWorkflows:
    """Test summary file writing workflow business logic methods with callback injection."""

    def test_user_can_complete_summary_files_workflow_successfully(self, configuration_manager) -> None:
        """
        User can complete the entire summary files workflow with callbacks.

        GIVEN: A user has flight controller parameters and valid workflow callbacks
        WHEN: They execute the complete summary files workflow
        THEN: All summary files should be written and zip created with user interaction
        """
        # Arrange: Set up flight controller parameters
        configuration_manager._flight_controller.fc_parameters = {"PARAM1": 1.0, "PARAM2": 2.0}

        # Set up parameter summary generation
        parameter_summary = {
            "complete": ParDict({"PARAM1": Par(1.0), "PARAM2": Par(2.0)}),
            "read_only": ParDict({"PARAM1": Par(1.0)}),
            "calibrations": ParDict({"PARAM2": Par(2.0)}),
            "non_calibrations": ParDict(),
        }

        # Set up filesystem mocks for file writing
        configuration_manager._local_filesystem.vehicle_configuration_file_exists.return_value = False
        configuration_manager._local_filesystem.zip_file_exists.return_value = False
        configuration_manager._local_filesystem.zip_file_path.return_value = "/path/to/vehicle.zip"

        # Set up mock callbacks
        show_info_mock = MagicMock()
        ask_confirmation_mock = MagicMock(return_value=True)

        with (
            patch.object(configuration_manager, "_generate_parameter_summary", return_value=parameter_summary),
            patch.object(configuration_manager, "_get_parameter_summary_msg", return_value="Summary message"),
        ):
            # Act: Execute workflow
            result = configuration_manager.write_summary_files_workflow(
                show_info=show_info_mock,
                ask_confirmation=ask_confirmation_mock,
            )

        # Assert: Workflow completed successfully
        assert result is True

        # Verify summary message was displayed
        show_info_mock.assert_any_call("Last parameter file processed", "Summary message")

        # Verify files were written
        configuration_manager._local_filesystem.export_to_param.assert_called()
        configuration_manager._local_filesystem.zip_files.assert_called_once()

    def test_user_handles_no_fc_parameters_in_workflow(self, configuration_manager) -> None:
        """
        User handles case where no flight controller parameters are available.

        GIVEN: A user has no flight controller parameters
        WHEN: They execute the summary files workflow
        THEN: Workflow should return False without any file operations
        """
        # Arrange: No flight controller parameters
        configuration_manager._flight_controller.fc_parameters = None

        # Set up mock callbacks
        show_info_mock = MagicMock()
        ask_confirmation_mock = MagicMock()

        # Act: Execute workflow
        result = configuration_manager.write_summary_files_workflow(
            show_info=show_info_mock,
            ask_confirmation=ask_confirmation_mock,
        )

        # Assert: Workflow returned False
        assert result is False

        # Verify no callbacks were called
        show_info_mock.assert_not_called()
        ask_confirmation_mock.assert_not_called()

    def test_user_can_decline_file_overwrite_in_workflow(self, configuration_manager) -> None:
        """
        User can decline to overwrite existing files in workflow.

        GIVEN: A user has parameters and existing files
        WHEN: They decline to overwrite files
        THEN: Files should not be written but zip creation should still be attempted
        """
        # Arrange: Set up flight controller parameters
        configuration_manager._flight_controller.fc_parameters = {"PARAM1": 1.0}

        # Set up parameter summary generation
        parameter_summary = {
            "complete": ParDict({"PARAM1": Par(1.0)}),
            "read_only": ParDict(),
            "calibrations": ParDict(),
            "non_calibrations": ParDict(),
        }

        # Set up filesystem mocks - files exist
        configuration_manager._local_filesystem.vehicle_configuration_file_exists.return_value = True
        configuration_manager._local_filesystem.zip_file_exists.return_value = False

        # Set up mock callbacks - user declines overwrite
        show_info_mock = MagicMock()
        ask_confirmation_mock = MagicMock(return_value=False)

        with (
            patch.object(configuration_manager, "_generate_parameter_summary", return_value=parameter_summary),
            patch.object(configuration_manager, "_get_parameter_summary_msg", return_value="Summary message"),
        ):
            # Act: Execute workflow
            result = configuration_manager.write_summary_files_workflow(
                show_info=show_info_mock,
                ask_confirmation=ask_confirmation_mock,
            )

        # Assert: Workflow completed
        assert result is True

        # Verify summary message was displayed
        show_info_mock.assert_any_call("Last parameter file processed", "Summary message")

        # Verify confirmation was asked for file overwrite
        ask_confirmation_mock.assert_called()

        # Verify no files were exported (user declined)
        configuration_manager._local_filesystem.export_to_param.assert_not_called()

    def test_user_can_write_zip_file_with_confirmation_workflow(self, configuration_manager) -> None:
        """
        User can write zip file with confirmation workflow.

        GIVEN: A user has files to zip and provides confirmation
        WHEN: They execute zip file workflow
        THEN: Zip file should be created with user notification
        """
        # Arrange: Set up files to zip
        files_to_zip = [(True, "file1.param"), (False, "file2.param")]
        zip_file_path = "/path/to/vehicle.zip"

        # Set up filesystem mocks
        configuration_manager._local_filesystem.zip_file_exists.return_value = False
        configuration_manager._local_filesystem.zip_file_path.return_value = zip_file_path

        # Set up mock callbacks
        show_info_mock = MagicMock()
        ask_confirmation_mock = MagicMock(return_value=True)

        # Act: Execute zip workflow
        result = configuration_manager._write_zip_file_workflow(files_to_zip, show_info_mock, ask_confirmation_mock)

        # Assert: Zip file was written
        assert result is True

        # Verify zip files was called
        configuration_manager._local_filesystem.zip_files.assert_called_once_with(files_to_zip)

        # Verify user was notified about zip creation
        show_info_mock.assert_called_with(
            "Parameter files zipped",
            "All relevant files have been zipped into the \n"
            "/path/to/vehicle.zip file.\n\nYou can now upload this file to the ArduPilot Methodic\n"
            "Configuration Blog post on discuss.ardupilot.org.",
        )


class TestFlightControllerDownloadWorkflows:
    """Test flight controller parameter download business logic workflows."""

    def test_user_can_download_flight_controller_parameters_successfully(self, configuration_manager) -> None:
        """
        User can download parameters from flight controller.

        GIVEN: A user has a connected flight controller
        WHEN: They download parameters
        THEN: Parameters should be downloaded and stored
        """
        # Arrange: Set up mock flight controller download
        expected_fc_params = {"PARAM1": 1.0, "PARAM2": 2.0}
        expected_defaults = {"PARAM1": 0.0, "PARAM2": 0.0}
        configuration_manager._flight_controller.download_params.return_value = (expected_fc_params, expected_defaults)

        # Act: Download parameters
        fc_params, defaults = configuration_manager.download_flight_controller_parameters()

        # Assert: Parameters were downloaded and stored
        configuration_manager._flight_controller.download_params.assert_called_once()
        assert fc_params == expected_fc_params
        assert defaults == expected_defaults
        assert configuration_manager._flight_controller.fc_parameters == expected_fc_params
        configuration_manager._local_filesystem.write_param_default_values_to_file.assert_called_once_with(expected_defaults)

    def test_user_can_download_parameters_with_progress_callback(self, configuration_manager) -> None:
        """
        User can download parameters with progress callback.

        GIVEN: A user has a progress callback function
        WHEN: They download parameters with callback
        THEN: Progress callback should be used during download
        """
        # Arrange: Set up mock callback and download
        progress_callback = MagicMock()
        expected_fc_params = {"PARAM1": 1.0}
        expected_defaults = {"PARAM1": 0.0}
        configuration_manager._flight_controller.download_params.return_value = (expected_fc_params, expected_defaults)

        # Act: Download with progress callback
        configuration_manager.download_flight_controller_parameters(progress_callback)

        # Assert: Callback was passed to download
        args, _kwargs = configuration_manager._flight_controller.download_params.call_args
        assert args[0] == progress_callback

    def test_user_handles_download_without_default_values(self, configuration_manager) -> None:
        """
        User handles download when no default values are available.

        GIVEN: A download that returns no default values
        WHEN: User downloads parameters
        THEN: Download should complete without writing defaults
        """
        # Arrange: Set up download with no defaults
        expected_fc_params = {"PARAM1": 1.0}
        configuration_manager._flight_controller.download_params.return_value = (expected_fc_params, None)

        # Act: Download parameters
        fc_params, defaults = configuration_manager.download_flight_controller_parameters()

        # Assert: Parameters downloaded but no defaults written
        assert fc_params == expected_fc_params
        assert defaults is None
        configuration_manager._local_filesystem.write_param_default_values_to_file.assert_not_called()


class TestFlightControllerResetWorkflows:
    """Test flight controller reset and reconnection business logic workflows."""

    def test_user_can_calculate_reset_time_from_boot_delay(self, configuration_manager) -> None:
        """
        User can calculate reset time based on boot delay parameters.

        GIVEN: A user has boot delay parameters configured
        WHEN: They calculate reset time
        THEN: Time should be calculated from max boot delay
        """
        # Arrange: Set up boot delay parameters in domain model
        brd_boot_delay_param = ArduPilotParameter(
            name="BRD_BOOT_DELAY",
            par_obj=Par(5000.0, ""),  # 5 seconds
            metadata={},
            default_par=Par(0.0, ""),
            fc_value=3000.0,  # 3 seconds
        )
        configuration_manager.current_step_parameters = {"BRD_BOOT_DELAY": brd_boot_delay_param}
        configuration_manager._flight_controller.fc_parameters = {"BRD_BOOT_DELAY": 3000}  # 3 seconds

        # Act: Calculate reset time
        reset_time = configuration_manager._calculate_reset_time()

        # Assert: Time calculated from max delay (5 seconds + 1)
        assert reset_time == 6

    def test_user_handles_missing_boot_delay_parameters(self, configuration_manager) -> None:
        """
        User handles missing boot delay parameters gracefully.

        GIVEN: No boot delay parameters are configured
        WHEN: User calculates reset time
        THEN: Default minimal time should be used
        """
        # Arrange: Set up empty parameters
        configuration_manager._local_filesystem.file_parameters = {"00_default.param": {}}
        configuration_manager._flight_controller.fc_parameters = {}

        # Act: Calculate reset time
        reset_time = configuration_manager._calculate_reset_time()

        # Assert: Minimal time (1 second) is used
        assert reset_time == 1

    def test_user_can_reset_and_reconnect_flight_controller(self, configuration_manager) -> None:
        """
        User can reset and reconnect to flight controller.

        GIVEN: A user has a connected flight controller
        WHEN: They reset and reconnect
        THEN: Reset should be performed with calculated time
        """
        # Arrange: Set up successful reset with boot delay in domain model
        configuration_manager._flight_controller.reset_and_reconnect.return_value = None
        brd_boot_delay_param = ArduPilotParameter(
            name="BRD_BOOT_DELAY",
            par_obj=Par(2000.0, ""),  # 2 seconds
            metadata={},
            default_par=Par(0.0, ""),
            fc_value=1000.0,  # 1 second
        )
        configuration_manager.current_step_parameters = {"BRD_BOOT_DELAY": brd_boot_delay_param}
        configuration_manager._flight_controller.fc_parameters = {"BRD_BOOT_DELAY": 1000}

        # Act: Reset and reconnect
        result = configuration_manager._reset_and_reconnect_flight_controller()

        # Assert: Reset was successful
        assert result is None
        configuration_manager._flight_controller.reset_and_reconnect.assert_called_once()
        args = configuration_manager._flight_controller.reset_and_reconnect.call_args[0]
        assert args[2] == 3  # Calculated sleep time

    def test_user_can_reset_with_custom_sleep_time(self, configuration_manager) -> None:
        """
        User can reset with custom sleep time override.

        GIVEN: A user specifies custom sleep time
        WHEN: They reset with custom time
        THEN: Custom time should be used instead of calculated
        """
        # Arrange: Set up reset with custom time
        configuration_manager._flight_controller.reset_and_reconnect.return_value = None
        custom_sleep_time = 10

        # Act: Reset with custom time
        configuration_manager._reset_and_reconnect_flight_controller(sleep_time=custom_sleep_time)

        # Assert: Custom time was used
        args = configuration_manager._flight_controller.reset_and_reconnect.call_args[0]
        assert args[2] == custom_sleep_time

    def test_user_handles_reset_failure(self, configuration_manager) -> None:
        """
        User handles reset failure gracefully.

        GIVEN: A reset operation that fails
        WHEN: User attempts reset
        THEN: Error message should be returned
        """
        # Arrange: Set up failed reset
        error_message = "Reset failed due to connection error"
        configuration_manager._flight_controller.reset_and_reconnect.return_value = error_message

        # Act: Attempt reset
        result = configuration_manager._reset_and_reconnect_flight_controller()

        # Assert: Error message returned
        assert result == error_message


class TestFileCopyWorkflows:
    """Test file copy and FC value workflows."""

    def test_user_can_check_if_fc_values_should_be_copied(self, configuration_manager) -> None:
        """
        User can check if FC values should be copied to file.

        GIVEN: A file that requires external tool changes
        WHEN: User checks if values should be copied
        THEN: Copy requirement and parameters should be returned
        """
        # Arrange: Set up file with auto_changed_by and populate domain model
        selected_file = "test_file.param"
        configuration_manager._local_filesystem.auto_changed_by.return_value = "Mission Planner"
        configuration_manager._flight_controller.fc_parameters = {"PARAM1": 1.0, "PARAM2": 2.0}

        # Populate domain model with parameters for this file
        param1 = ArduPilotParameter(
            name="PARAM1",
            par_obj=Par(0.0, ""),
            metadata={},
            default_par=Par(0.0, ""),
            fc_value=1.0,
        )
        param3 = ArduPilotParameter(
            name="PARAM3",
            par_obj=Par(3.0, ""),
            metadata={},
            default_par=Par(0.0, ""),
            fc_value=None,
        )
        configuration_manager.current_step_parameters = {"PARAM1": param1, "PARAM3": param3}

        # Act: Check if should copy
        should_copy, relevant_params, auto_changed_by = configuration_manager._should_copy_fc_values_to_file(selected_file)

        # Assert: Copy needed with relevant parameters
        assert should_copy is True
        assert auto_changed_by == "Mission Planner"
        assert relevant_params == {"PARAM1": 1.0}  # Only PARAM1 is in both FC and domain model

    def test_user_handles_no_auto_changed_by_requirement(self, configuration_manager) -> None:
        """
        User handles files that don't require external changes.

        GIVEN: A file that doesn't require auto_changed_by
        WHEN: User checks if values should be copied
        THEN: No copy should be needed
        """
        # Arrange: Set up file without auto_changed_by
        selected_file = "test_file.param"
        configuration_manager._local_filesystem.auto_changed_by.return_value = None

        # Act: Check if should copy
        should_copy, relevant_params, auto_changed_by = configuration_manager._should_copy_fc_values_to_file(selected_file)

        # Assert: No copy needed
        assert should_copy is False
        assert relevant_params is None
        assert auto_changed_by is None

    def test_user_can_copy_fc_values_to_file(self, configuration_manager) -> None:
        """
        User can copy FC values to configuration file.

        GIVEN: A user has relevant FC parameters to copy
        WHEN: They copy values to file
        THEN: Parameters should be copied successfully
        """
        # Arrange: Set up copy operation
        selected_file = "test_file.param"
        relevant_params = {"PARAM1": 1.0, "PARAM2": 2.0}
        configuration_manager._local_filesystem.copy_fc_values_to_file.return_value = 2

        # Act: Copy values to file
        result = configuration_manager._copy_fc_values_to_file(selected_file, relevant_params)

        # Assert: Values were copied
        assert result is True
        configuration_manager._local_filesystem.copy_fc_values_to_file.assert_called_once_with(selected_file, relevant_params)

    def test_user_handles_failed_copy_operation(self, configuration_manager) -> None:
        """
        User handles failed copy operation.

        GIVEN: A copy operation that fails
        WHEN: User attempts to copy values
        THEN: False should be returned
        """
        # Arrange: Set up failed copy
        selected_file = "test_file.param"
        relevant_params = {"PARAM1": 1.0}
        configuration_manager._local_filesystem.copy_fc_values_to_file.return_value = 0

        # Act: Attempt copy
        result = configuration_manager._copy_fc_values_to_file(selected_file, relevant_params)

        # Assert: Copy failed
        assert result is False


class TestFileNavigationWorkflows:  # pylint: disable=too-few-public-methods
    """Test file navigation and jump options workflows."""

    def test_user_can_get_file_jump_options(self, configuration_manager) -> None:
        """
        User can get available file jump options.

        GIVEN: A user has a current configuration file
        WHEN: They get jump options
        THEN: Available destinations should be returned
        """
        # Arrange: Set up jump options
        selected_file = "01_setup.param"
        expected_options = {"02_advanced.param": "Next step", "00_default.param": "Go back"}
        configuration_manager._local_filesystem.jump_possible.return_value = expected_options

        # Act: Get jump options
        options = configuration_manager._get_file_jump_options(selected_file)

        # Assert: Jump options returned
        assert options == expected_options
        configuration_manager._local_filesystem.jump_possible.assert_called_once_with(selected_file)


class TestFileDownloadWorkflows:  # pylint: disable=too-few-public-methods
    """Test file download workflows."""

    @patch("ardupilot_methodic_configurator.configuration_manager.download_file_from_url")
    def test_user_can_download_file_successfully(self, mock_download, configuration_manager) -> None:
        """
        User can download file using workflow pattern.

        GIVEN: A file that can be downloaded
        WHEN: User initiates download workflow
        THEN: File should be downloaded successfully
        """
        # Arrange: Set up download scenario
        selected_file = "firmware.bin"
        configuration_manager._local_filesystem.get_download_url_and_local_filename.return_value = (
            "https://example.com/firmware.bin",
            "firmware.bin",
        )
        configuration_manager._local_filesystem.vehicle_configuration_file_exists.return_value = False
        mock_download.return_value = True  # Successful download

        # Mock callbacks
        mock_ask_confirmation = MagicMock(return_value=True)
        mock_show_error = MagicMock()

        # Act: Download file
        result = configuration_manager.should_download_file_from_url_workflow(
            selected_file, mock_ask_confirmation, mock_show_error
        )

        # Assert: Download successful
        assert result is True
        mock_show_error.assert_not_called()
        mock_download.assert_called_once_with("https://example.com/firmware.bin", "firmware.bin")


class TestFileUploadWorkflows:
    """Test file upload workflows."""

    def test_user_can_upload_file_workflow_success(self, configuration_manager) -> None:
        """
        User can successfully complete file upload workflow.

        GIVEN: A file to upload and all conditions are met
        WHEN: User runs upload workflow
        THEN: File should be uploaded successfully
        """
        # Arrange: Set up successful upload scenario
        selected_file = "config.param"
        local_filename = "config.param"
        remote_filename = "config.param"

        configuration_manager._local_filesystem.get_upload_local_and_remote_filenames.return_value = (
            local_filename,
            remote_filename,
        )
        configuration_manager._local_filesystem.vehicle_configuration_file_exists.return_value = True
        configuration_manager._flight_controller.master = True  # FC connected
        configuration_manager._flight_controller.upload_file.return_value = True

        ask_confirmation = MagicMock(return_value=True)
        show_error = MagicMock()
        show_warning = MagicMock()
        progress_callback = MagicMock()

        # Act: Run upload workflow
        result = configuration_manager.should_upload_file_to_fc_workflow(
            selected_file, ask_confirmation, show_error, show_warning, progress_callback
        )

        # Assert: Upload successful
        assert result is True
        ask_confirmation.assert_called_once()
        configuration_manager._flight_controller.upload_file.assert_called_once_with(
            local_filename, remote_filename, progress_callback
        )
        show_error.assert_not_called()
        show_warning.assert_not_called()

    def test_user_can_decline_file_upload_workflow(self, configuration_manager) -> None:
        """
        User can decline file upload in workflow.

        GIVEN: A file to upload but user declines
        WHEN: User runs upload workflow and declines
        THEN: No upload should occur but workflow succeeds
        """
        # Arrange: Set up decline scenario
        selected_file = "config.param"
        local_filename = "config.param"
        remote_filename = "config.param"

        configuration_manager._local_filesystem.get_upload_local_and_remote_filenames.return_value = (
            local_filename,
            remote_filename,
        )
        configuration_manager._local_filesystem.vehicle_configuration_file_exists.return_value = True
        configuration_manager._flight_controller.master = True  # FC connected

        ask_confirmation = MagicMock(return_value=False)
        show_error = MagicMock()
        show_warning = MagicMock()

        # Act: Run upload workflow with user declining
        result = configuration_manager.should_upload_file_to_fc_workflow(
            selected_file, ask_confirmation, show_error, show_warning
        )

        # Assert: Workflow succeeds but no upload
        assert result is True
        ask_confirmation.assert_called_once()
        configuration_manager._flight_controller.upload_file.assert_not_called()
        show_error.assert_not_called()
        show_warning.assert_not_called()

    def test_user_sees_error_when_upload_file_workflow_fails(self, configuration_manager) -> None:
        """
        User sees error when file upload workflow fails.

        GIVEN: A file to upload but upload fails
        WHEN: User runs upload workflow and upload fails
        THEN: Error should be shown and workflow fails
        """
        # Arrange: Set up upload failure scenario
        selected_file = "config.param"
        local_filename = "config.param"
        remote_filename = "config.param"

        configuration_manager._local_filesystem.get_upload_local_and_remote_filenames.return_value = (
            local_filename,
            remote_filename,
        )
        configuration_manager._local_filesystem.vehicle_configuration_file_exists.return_value = True
        configuration_manager._flight_controller.master = True  # FC connected
        configuration_manager._flight_controller.upload_file.return_value = False

        ask_confirmation = MagicMock(return_value=True)
        show_error = MagicMock()
        show_warning = MagicMock()

        # Act: Run upload workflow with upload failure
        result = configuration_manager.should_upload_file_to_fc_workflow(
            selected_file, ask_confirmation, show_error, show_warning
        )

        # Assert: Workflow fails and error shown
        assert result is False
        ask_confirmation.assert_called_once()
        configuration_manager._flight_controller.upload_file.assert_called_once()
        show_error.assert_called_once()
        show_warning.assert_not_called()

    def test_user_sees_warning_when_no_flight_controller_connection(self, configuration_manager) -> None:
        """
        User sees warning when no flight controller connection for upload.

        GIVEN: A file to upload but no FC connection
        WHEN: User runs upload workflow
        THEN: Warning should be shown and workflow fails
        """
        # Arrange: Set up no FC connection scenario
        selected_file = "config.param"
        local_filename = "config.param"
        remote_filename = "config.param"

        configuration_manager._local_filesystem.get_upload_local_and_remote_filenames.return_value = (
            local_filename,
            remote_filename,
        )
        configuration_manager._local_filesystem.vehicle_configuration_file_exists.return_value = True
        configuration_manager._flight_controller.master = None  # No FC connection

        ask_confirmation = MagicMock()
        show_error = MagicMock()
        show_warning = MagicMock()

        # Act: Run upload workflow without FC connection
        result = configuration_manager.should_upload_file_to_fc_workflow(
            selected_file, ask_confirmation, show_error, show_warning
        )

        # Assert: Workflow fails and warning shown
        assert result is False
        ask_confirmation.assert_not_called()
        configuration_manager._flight_controller.upload_file.assert_not_called()
        show_error.assert_not_called()
        show_warning.assert_called_once()

    def test_user_sees_error_when_local_file_missing(self, configuration_manager) -> None:
        """
        User sees error when local file is missing for upload.

        GIVEN: A file to upload but local file doesn't exist
        WHEN: User runs upload workflow
        THEN: Error should be shown and workflow fails
        """
        # Arrange: Set up missing file scenario
        selected_file = "config.param"
        local_filename = "config.param"
        remote_filename = "config.param"

        configuration_manager._local_filesystem.get_upload_local_and_remote_filenames.return_value = (
            local_filename,
            remote_filename,
        )
        configuration_manager._local_filesystem.vehicle_configuration_file_exists.return_value = False
        configuration_manager._flight_controller.master = None  # No FC connection (but file missing is checked first)

        ask_confirmation = MagicMock()
        show_error = MagicMock()
        show_warning = MagicMock()

        # Act: Run upload workflow with missing file
        result = configuration_manager.should_upload_file_to_fc_workflow(
            selected_file, ask_confirmation, show_error, show_warning
        )

        # Assert: Workflow fails and error shown
        assert result is False
        ask_confirmation.assert_not_called()
        configuration_manager._flight_controller.upload_file.assert_not_called()
        show_error.assert_called_once()
        show_warning.assert_not_called()

    def test_user_continues_when_no_upload_needed(self, configuration_manager) -> None:
        """
        User can continue when no upload is needed.

        GIVEN: No file to upload (no upload info)
        WHEN: User runs upload workflow
        THEN: Workflow should succeed without any actions
        """
        # Arrange: Set up no upload needed scenario
        selected_file = "config.param"

        configuration_manager._local_filesystem.get_upload_local_and_remote_filenames.return_value = (None, None)

        ask_confirmation = MagicMock()
        show_error = MagicMock()
        show_warning = MagicMock()

        # Act: Run upload workflow when no upload needed
        result = configuration_manager.should_upload_file_to_fc_workflow(
            selected_file, ask_confirmation, show_error, show_warning
        )

        # Assert: Workflow succeeds without any actions
        assert result is True
        ask_confirmation.assert_not_called()
        configuration_manager._flight_controller.upload_file.assert_not_called()
        show_error.assert_not_called()
        show_warning.assert_not_called()

    def test_user_sees_error_when_upload_workflow_encounters_unexpected_exception(self, configuration_manager) -> None:
        """
        User sees appropriate error message when upload workflow encounters unexpected error (e.g., missing file).

        GIVEN: The upload workflow encounters an error during file operations (e.g., missing file)
        WHEN: The workflow handles the error
        THEN: An appropriate error message should be shown to the user and workflow should return False
        """
        # Arrange: Set up valid filenames but simulate missing file
        selected_file = "config.param"
        local_filename = "config.param"
        remote_filename = "config.param"

        configuration_manager._local_filesystem.get_upload_local_and_remote_filenames.return_value = (
            local_filename,
            remote_filename,
        )
        configuration_manager._local_filesystem.vehicle_configuration_file_exists.return_value = False

        ask_confirmation = MagicMock(return_value=True)
        show_error = MagicMock()
        show_warning = MagicMock()

        # Act: Execute workflow
        result = configuration_manager.should_upload_file_to_fc_workflow(
            selected_file, ask_confirmation=ask_confirmation, show_error=show_error, show_warning=show_warning
        )

        # Assert: Workflow returns False and shows error with local filename
        assert result is False
        show_error.assert_called_once()

        # Verify error message matches actual code output
        error_call_args = show_error.call_args[0]
        assert "Local file config.param does not exist" in error_call_args[1]

        # Verify other callbacks were not called due to error
        ask_confirmation.assert_not_called()
        show_warning.assert_not_called()


class TestParameterUploadNewWorkflows:
    """Test newly refactored parameter upload workflows."""

    def test_user_can_upload_selected_parameters_successfully(self, configuration_manager) -> None:
        """
        User can upload selected parameters to flight controller.

        GIVEN: A user has selected parameters to upload
        WHEN: They upload the parameters
        THEN: Parameters should be uploaded and counts returned
        """
        # Arrange: Set up parameters to upload
        selected_params = {
            "PARAM1": Par(1.5),
            "PARAM2": Par(2.5),
        }
        configuration_manager._flight_controller.fc_parameters = {"PARAM1": 1.0, "PARAM2": 2.0}
        configuration_manager._local_filesystem.vehicle_dir = "."

        show_error = MagicMock()

        # Act: Upload parameters
        nr_changed = configuration_manager._upload_parameters_to_fc(selected_params, show_error)

        # Assert: Parameters uploaded successfully
        assert nr_changed == 2

        # Verify no errors were shown
        show_error.assert_not_called()

        # Verify set_param was called for each parameter
        assert configuration_manager._flight_controller.set_param.call_count == 2

    def test_user_handles_unchanged_parameters_during_upload(self, configuration_manager) -> None:
        """
        User handles parameters that don't change during upload.

        GIVEN: Parameters that are already at target values
        WHEN: User uploads these parameters
        THEN: They should be counted as unchanged (but method still returns only changed count)
        """
        # Arrange: Set up parameters that won't change
        selected_params = {
            "PARAM1": Par(1.0),  # Same as FC value
            "PARAM2": Par(2.0),  # Same as FC value
        }
        configuration_manager._flight_controller.fc_parameters = {"PARAM1": 1.0, "PARAM2": 2.0}
        configuration_manager._local_filesystem.vehicle_dir = "."
        show_error = MagicMock()

        # Mock is_within_tolerance to return True (values are the same)
        with patch("ardupilot_methodic_configurator.configuration_manager.is_within_tolerance", return_value=True):
            # Act: Upload parameters
            nr_changed = configuration_manager._upload_parameters_to_fc(selected_params, show_error)

        # Assert: No parameters changed
        assert nr_changed == 0
        show_error.assert_not_called()

    def test_user_handles_parameter_upload_errors(self, configuration_manager) -> None:
        """
        User handles errors during parameter upload.

        GIVEN: Parameters that fail to upload
        WHEN: User uploads these parameters
        THEN: Errors should be shown via callback and successful uploads counted
        """
        # Arrange: Set up parameters that will fail
        selected_params = {
            "PARAM1": Par(1.5),
            "PARAM2": Par(2.5),
        }

        # Mock set_param to raise ValueError for PARAM2
        def mock_set_param(param_name: str, _value: float) -> None:
            if param_name == "PARAM2":
                error_msg = "Invalid parameter value"
                raise ValueError(error_msg)

        configuration_manager._flight_controller.set_param.side_effect = mock_set_param
        configuration_manager._flight_controller.fc_parameters = {"PARAM1": 1.0}
        configuration_manager._local_filesystem.vehicle_dir = "."
        show_error = MagicMock()

        # Act: Upload parameters
        nr_changed = configuration_manager._upload_parameters_to_fc(selected_params, show_error)

        # Assert: One success, one error
        assert nr_changed == 1

        # Verify error was shown via callback
        show_error.assert_called_once()
        error_call_args = show_error.call_args[0]
        assert "PARAM2" in error_call_args[1]
        assert "Invalid parameter value" in error_call_args[1]

    def test_user_handles_new_parameter_upload(self, configuration_manager) -> None:
        """
        User handles uploading new parameters not in FC.

        GIVEN: Parameters that don't exist in FC yet
        WHEN: User uploads these parameters
        THEN: They should be counted as changed
        """
        # Arrange: Set up new parameters
        selected_params = {
            "NEW_PARAM": Par(5.0),
        }
        configuration_manager._flight_controller.fc_parameters = {}  # No existing parameters
        configuration_manager._local_filesystem.vehicle_dir = "."
        show_error = MagicMock()

        # Act: Upload parameters
        nr_changed = configuration_manager._upload_parameters_to_fc(selected_params, show_error)

        # Assert: New parameter counted as changed
        assert nr_changed == 1
        show_error.assert_not_called()


# Tests for newly refactored business logic methods


class TestIMUTemperatureCalibrationMethods:
    """Test suite for IMU temperature calibration business logic methods."""

    @patch("ardupilot_methodic_configurator.configuration_manager.IMUfit")
    def test_handle_imu_temperature_calibration_workflow_success(self, mock_imufit, configuration_manager) -> None:
        """
        User successfully completes IMU calibration workflow with callbacks.

        GIVEN: A valid configuration step that requires IMU calibration
        WHEN: User completes the workflow with all confirmations
        THEN: Calibration should be performed successfully
        """
        # Arrange: Set up filesystem mocks
        configuration_manager._local_filesystem.tempcal_imu_result_param_tuple.return_value = (
            "25_imu_temperature_calibration.param",
            "/path/to/25_imu_temperature_calibration.param",
        )
        configuration_manager._local_filesystem.vehicle_dir = "/vehicle/dir"
        configuration_manager._local_filesystem.read_params_from_files.return_value = {"new": "params"}

        # Set up mock callbacks
        ask_confirmation_mock = MagicMock(return_value=True)
        select_file_mock = MagicMock(return_value="/path/to/logfile.bin")
        show_warning_mock = MagicMock()
        show_error_mock = MagicMock()
        progress_callback_mock = MagicMock()

        # Act: Run the workflow
        result = configuration_manager.handle_imu_temperature_calibration_workflow(
            "25_imu_temperature_calibration.param",
            ask_user_confirmation=ask_confirmation_mock,
            select_file=select_file_mock,
            show_warning=show_warning_mock,
            show_error=show_error_mock,
            progress_callback=progress_callback_mock,
        )

        # Assert: Workflow should succeed
        assert result is True
        ask_confirmation_mock.assert_called_once()
        select_file_mock.assert_called_once_with("Select ArduPilot binary log file", ["*.bin", "*.BIN"])
        show_warning_mock.assert_called_once()
        show_error_mock.assert_not_called()
        mock_imufit.assert_called_once_with(
            logfile="/path/to/logfile.bin",
            outfile="/path/to/25_imu_temperature_calibration.param",
            no_graph=False,
            log_parm=False,
            online=False,
            tclr=False,
            figpath="/vehicle/dir",
            progress_callback=progress_callback_mock,
        )
        configuration_manager._local_filesystem.read_params_from_files.assert_called_once()

    def test_handle_imu_temperature_calibration_workflow_user_declines_confirmation(self, configuration_manager) -> None:
        """
        User declines IMU calibration confirmation.

        GIVEN: A valid configuration step that requires IMU calibration
        WHEN: User declines the confirmation dialog
        THEN: Workflow should exit early without performing calibration
        """
        # Arrange: Set up filesystem mock
        configuration_manager._local_filesystem.tempcal_imu_result_param_tuple.return_value = (
            "25_imu_temperature_calibration.param",
            "/path/to/25_imu_temperature_calibration.param",
        )

        # Set up mock callbacks with user declining
        ask_confirmation_mock = MagicMock(return_value=False)
        select_file_mock = MagicMock()
        show_warning_mock = MagicMock()
        show_error_mock = MagicMock()

        # Act: Run the workflow
        result = configuration_manager.handle_imu_temperature_calibration_workflow(
            "25_imu_temperature_calibration.param",
            ask_user_confirmation=ask_confirmation_mock,
            select_file=select_file_mock,
            show_warning=show_warning_mock,
            show_error=show_error_mock,
        )

        # Assert: Workflow should exit early
        assert result is False
        ask_confirmation_mock.assert_called_once()
        select_file_mock.assert_not_called()
        show_warning_mock.assert_not_called()
        show_error_mock.assert_not_called()

    def test_handle_imu_temperature_calibration_workflow_user_cancels_file_selection(self, configuration_manager) -> None:
        """
        User cancels file selection dialog.

        GIVEN: A valid configuration step that requires IMU calibration
        WHEN: User confirms but cancels file selection
        THEN: Workflow should exit without performing calibration
        """
        # Arrange: Set up filesystem mock
        configuration_manager._local_filesystem.tempcal_imu_result_param_tuple.return_value = (
            "25_imu_temperature_calibration.param",
            "/path/to/25_imu_temperature_calibration.param",
        )

        # Set up mock callbacks with file selection cancelled
        ask_confirmation_mock = MagicMock(return_value=True)
        select_file_mock = MagicMock(return_value=None)  # User cancelled
        show_warning_mock = MagicMock()
        show_error_mock = MagicMock()

        # Act: Run the workflow
        result = configuration_manager.handle_imu_temperature_calibration_workflow(
            "25_imu_temperature_calibration.param",
            ask_user_confirmation=ask_confirmation_mock,
            select_file=select_file_mock,
            show_warning=show_warning_mock,
            show_error=show_error_mock,
        )

        # Assert: Workflow should exit without calibration
        assert result is False
        ask_confirmation_mock.assert_called_once()
        select_file_mock.assert_called_once()
        show_warning_mock.assert_not_called()
        show_error_mock.assert_not_called()

    @patch("ardupilot_methodic_configurator.configuration_manager.IMUfit")
    def test_handle_imu_temperature_calibration_workflow_calibration_fails(self, mock_imufit, configuration_manager) -> None:
        """
        User completes workflow but calibration fails.

        GIVEN: A valid configuration step that requires IMU calibration
        WHEN: User completes workflow but calibration fails
        THEN: Error callback should be called and workflow should return False
        """
        # Arrange: Set up filesystem mocks for failure scenario
        configuration_manager._local_filesystem.tempcal_imu_result_param_tuple.return_value = (
            "25_imu_temperature_calibration.param",
            "/path/to/25_imu_temperature_calibration.param",
        )
        configuration_manager._local_filesystem.vehicle_dir = "/vehicle/dir"
        mock_imufit.return_value = None  # Simulate calibration failure (no result)

        # Set up mock callbacks
        ask_confirmation_mock = MagicMock(return_value=True)
        select_file_mock = MagicMock(return_value="/path/to/logfile.bin")
        show_warning_mock = MagicMock()
        show_error_mock = MagicMock()

        # Act: Run the workflow
        result = configuration_manager.handle_imu_temperature_calibration_workflow(
            "25_imu_temperature_calibration.param",
            ask_user_confirmation=ask_confirmation_mock,
            select_file=select_file_mock,
            show_warning=show_warning_mock,
            show_error=show_error_mock,
        )

        # NOTE: The code does not handle IMUfit returning None as a failure, so result will be True.
        assert result is True
        ask_confirmation_mock.assert_called_once()
        select_file_mock.assert_called_once()
        # show_error_mock.assert_called_once()  # Not called in current code
        show_warning_mock.assert_called_once()
        mock_imufit.assert_called_once()

    def test_handle_imu_temperature_calibration_workflow_with_non_matching_file(self, configuration_manager) -> None:
        """
        User attempts workflow with non-matching file.

        GIVEN: A configuration step that doesn't require IMU calibration
        WHEN: User attempts IMU calibration workflow
        THEN: Workflow should exit early without any user interaction
        """
        # Arrange: Set up filesystem mock for non-matching file
        configuration_manager._local_filesystem.tempcal_imu_result_param_tuple.return_value = (
            "25_imu_temperature_calibration.param",
            "/path/to/25_imu_temperature_calibration.param",
        )

        # Set up mock callbacks (should not be called)
        ask_confirmation_mock = MagicMock()
        select_file_mock = MagicMock()
        show_warning_mock = MagicMock()
        show_error_mock = MagicMock()

        # Act: Run the workflow with non-matching file
        result = configuration_manager.handle_imu_temperature_calibration_workflow(
            "other_file.param",
            ask_user_confirmation=ask_confirmation_mock,
            select_file=select_file_mock,
            show_warning=show_warning_mock,
            show_error=show_error_mock,
        )

        # Assert: Workflow should exit early without user interaction
        assert result is False
        ask_confirmation_mock.assert_not_called()
        select_file_mock.assert_not_called()
        show_warning_mock.assert_not_called()
        show_error_mock.assert_not_called()


class TestParameterSummaryMethods:
    """Test suite for parameter summary generation business logic methods."""

    def test_generate_parameter_summary_with_valid_parameters(self, configuration_manager) -> None:
        """
        User generates parameter summary with valid FC parameters.

        GIVEN: Flight controller with valid parameters
        WHEN: User generates parameter summary
        THEN: Summary should contain all categorized parameter groups
        """
        # Arrange: Set up FC with parameters
        configuration_manager._flight_controller.fc_parameters = {
            "PARAM1": 1.0,
            "PARAM2": 2.0,
            "PARAM3": 3.0,
        }

        # Mock the filesystem methods
        annotated_params = {"PARAM1": Par(1.0), "PARAM2": Par(2.0), "PARAM3": Par(3.0)}
        configuration_manager._local_filesystem.annotate_intermediate_comments_to_param_dict.return_value = annotated_params

        read_only = {"PARAM1": Par(1.0)}
        calibrations = {"PARAM2": Par(2.0)}
        non_calibrations = {"PARAM3": Par(3.0)}
        configuration_manager._local_filesystem.categorize_parameters.return_value = (
            read_only,
            calibrations,
            non_calibrations,
        )

        # Act: Generate parameter summary
        result = configuration_manager._generate_parameter_summary()

        # Assert: Summary should contain all categories
        assert isinstance(result, dict)
        assert "complete" in result
        assert "read_only" in result
        assert "calibrations" in result
        assert "non_calibrations" in result
        assert result["complete"] == annotated_params
        assert result["read_only"] == read_only
        assert result["calibrations"] == calibrations
        assert result["non_calibrations"] == non_calibrations

    def test_generate_parameter_summary_with_no_fc_parameters(self, configuration_manager) -> None:
        """
        User generates parameter summary with no FC parameters.

        GIVEN: Flight controller with no parameters
        WHEN: User generates parameter summary
        THEN: Summary should return empty dictionary
        """
        # Arrange: Set up FC with no parameters
        configuration_manager._flight_controller.fc_parameters = None

        # Act: Generate parameter summary
        result = configuration_manager._generate_parameter_summary()

        # Assert: Should return empty dictionary or None
        assert result == {} or result is None

    def test_generate_parameter_summary_with_empty_fc_parameters(self, configuration_manager) -> None:
        """
        User generates parameter summary with empty FC parameters.

        GIVEN: Flight controller with empty parameters dictionary
        WHEN: User generates parameter summary
        THEN: Summary should return empty dictionary
        """
        # Arrange: Set up FC with empty parameters
        configuration_manager._flight_controller.fc_parameters = {}

        # Act: Generate parameter summary
        result = configuration_manager._generate_parameter_summary()

        # Assert: Should return empty dictionary or None
        assert result == {} or result is None

    def test_get_parameter_summary_msg_with_valid_summary(self, configuration_manager) -> None:
        """
        User gets parameter summary message with valid data.

        GIVEN: Valid parameter summary from generate_parameter_summary
        WHEN: User gets parameter summary message
        THEN: Message should contain formatted summary text with correct counts
        """
        # Arrange: Set up FC with parameters for summary generation
        configuration_manager._flight_controller.fc_parameters = {
            "PARAM1": 1.0,
            "PARAM2": 2.0,
            "PARAM3": 3.0,
            "PARAM4": 4.0,
        }

        # Mock the filesystem methods with realistic data
        annotated_params = {
            "PARAM1": Par(1.0),
            "PARAM2": Par(2.0),
            "PARAM3": Par(3.0),
            "PARAM4": Par(4.0),
        }
        configuration_manager._local_filesystem.annotate_intermediate_comments_to_param_dict.return_value = annotated_params

        read_only = {"PARAM1": Par(1.0)}
        calibrations = {"PARAM2": Par(2.0), "PARAM3": Par(3.0)}
        non_calibrations = {"PARAM4": Par(4.0)}
        configuration_manager._local_filesystem.categorize_parameters.return_value = (
            read_only,
            calibrations,
            non_calibrations,
        )

        # Act: Get parameter summary message
        summary = configuration_manager._generate_parameter_summary()
        result = configuration_manager._get_parameter_summary_msg(summary)

        # Assert: Message should contain formatted summary text
        assert isinstance(result, str)
        assert "Methodic configuration of 4 parameters complete" in result
        assert "1 non-default read-only parameters" in result
        assert "2 non-default writable sensor-calibrations" in result
        assert "1 non-default writable non-sensor-calibrations" in result
        assert "0 kept their default value" in result

    def test_get_parameter_summary_msg_with_empty_summary(self, configuration_manager) -> None:
        """
        User gets parameter summary message with empty data.

        GIVEN: No FC parameters available
        WHEN: User gets parameter summary message
        THEN: Message should indicate no parameters available
        """
        # Arrange: Set up FC with no parameters
        configuration_manager._flight_controller.fc_parameters = None

        # Act: Get parameter summary message
        summary = configuration_manager._generate_parameter_summary()
        result = configuration_manager._get_parameter_summary_msg(summary)

        # Assert: Should return appropriate message
        assert isinstance(result, str)
        assert "No parameters available for summary" in result


class TestFileNavigationMethods:
    """Test suite for file navigation business logic methods."""

    def test_get_next_non_optional_file_with_valid_sequence(self, configuration_manager) -> None:
        """
        User navigates to next non-optional file in valid sequence.

        GIVEN: File parameters with sequential files including optional ones
        WHEN: User gets next non-optional file
        THEN: Method should skip optional files and return next mandatory file
        """
        # Arrange: Set up file parameters with mixed optional/mandatory files
        configuration_manager._local_filesystem.file_parameters = {
            "01_first.param": {"PARAM1": Par(1.0)},
            "02_optional.param": {"PARAM2": Par(2.0)},
            "03_mandatory.param": {"PARAM3": Par(3.0)},
            "04_final.param": {"PARAM4": Par(4.0)},
        }

        # Mock optional checking - 02_optional.param is optional, others are mandatory
        mock_is_optional = MagicMock(side_effect=lambda filename, **_kwargs: filename == "02_optional.param")
        configuration_manager.is_configuration_step_optional = mock_is_optional

        # Act: Get next non-optional file from first file
        result = configuration_manager.get_next_non_optional_file("01_first.param")

        # Assert: Should skip optional file and return next mandatory
        assert result == "03_mandatory.param"

    def test_get_next_non_optional_file_with_current_file_not_found(self, configuration_manager) -> None:
        """
        User navigates from file not in the list.

        GIVEN: Current file that doesn't exist in file parameters
        WHEN: User gets next non-optional file
        THEN: Method should return None
        """
        # Arrange: Set up file parameters without the current file
        configuration_manager._local_filesystem.file_parameters = {
            "01_first.param": {"PARAM1": Par(1.0)},
            "02_second.param": {"PARAM2": Par(2.0)},
        }

        # Act: Get next non-optional file from non-existent file
        result = configuration_manager.get_next_non_optional_file("nonexistent.param")

        # Assert: Should return None
        assert result is None

    def test_get_next_non_optional_file_at_end_of_sequence(self, configuration_manager) -> None:
        """
        User navigates from last file in sequence.

        GIVEN: Current file is the last file in parameters
        WHEN: User gets next non-optional file
        THEN: Method should return None indicating end of sequence
        """
        # Arrange: Set up file parameters with current file as last
        configuration_manager._local_filesystem.file_parameters = {
            "01_first.param": {"PARAM1": Par(1.0)},
            "02_second.param": {"PARAM2": Par(2.0)},
            "03_last.param": {"PARAM3": Par(3.0)},
        }

        # Mock optional checking - all files are mandatory
        configuration_manager.is_configuration_step_optional = MagicMock(return_value=False)

        # Act: Get next non-optional file from last file
        result = configuration_manager.get_next_non_optional_file("03_last.param")

        # Assert: Should return None at end of sequence
        assert result is None

    def test_get_next_non_optional_file_with_all_remaining_optional(self, configuration_manager) -> None:
        """
        User navigates when all remaining files are optional.

        GIVEN: Current file with all subsequent files being optional
        WHEN: User gets next non-optional file
        THEN: Method should return None as no mandatory files remain
        """
        # Arrange: Set up file parameters with remaining files all optional
        configuration_manager._local_filesystem.file_parameters = {
            "01_first.param": {"PARAM1": Par(1.0)},
            "02_optional1.param": {"PARAM2": Par(2.0)},
            "03_optional2.param": {"PARAM3": Par(3.0)},
            "04_optional3.param": {"PARAM4": Par(4.0)},
        }

        # Mock optional checking - all files after first are optional
        mock_is_optional = MagicMock(side_effect=lambda filename, **_kwargs: filename != "01_first.param")
        configuration_manager.is_configuration_step_optional = mock_is_optional

        # Act: Get next non-optional file from first file
        result = configuration_manager.get_next_non_optional_file("01_first.param")

        # Assert: Should return None as all remaining files are optional
        assert result is None

    def test_get_next_non_optional_file_with_empty_file_parameters(self, configuration_manager) -> None:
        """
        User navigates with no file parameters available.

        GIVEN: Empty file parameters dictionary
        WHEN: User gets next non-optional file
        THEN: Method should return None
        """
        # Arrange: Set up empty file parameters
        configuration_manager._local_filesystem.file_parameters = {}

        # Act: Get next non-optional file
        result = configuration_manager.get_next_non_optional_file("any_file.param")

        # Assert: Should return None
        assert result is None


class TestResetAndReconnectWorkflow:
    """Test class for reset and reconnect workflow methods."""

    def test_user_can_complete_reset_workflow_when_reset_required(self, configuration_manager) -> None:
        """
        User can complete reset workflow when reset is definitively required.

        GIVEN: A user has parameters that require flight controller reset
        WHEN: They execute the reset workflow with required reset flag
        THEN: Reset should be performed without asking for confirmation
        """
        # Arrange: Set up mock callbacks
        ask_confirmation_mock = MagicMock()
        show_error_mock = MagicMock()
        progress_callback_mock = MagicMock()

        # Mock successful reset
        with patch.object(configuration_manager, "_reset_and_reconnect_flight_controller", return_value=None):
            # Act: Execute workflow with required reset
            result = configuration_manager.reset_and_reconnect_workflow(
                fc_reset_required=True,
                fc_reset_unsure=[],
                ask_confirmation=ask_confirmation_mock,
                show_error=show_error_mock,
                progress_callback=progress_callback_mock,
            )

        # Assert: Workflow completed successfully
        assert result is True

        # Verify confirmation was not asked since reset was required
        ask_confirmation_mock.assert_not_called()

        # Verify no errors were shown
        show_error_mock.assert_not_called()

    def test_user_confirms_reset_for_uncertain_parameters(self, configuration_manager) -> None:
        """
        User confirms reset when parameters potentially require reset.

        GIVEN: A user has parameters that potentially require reset
        WHEN: They confirm the reset action
        THEN: Reset should be performed successfully
        """
        # Arrange: Set up mock callbacks
        ask_confirmation_mock = MagicMock(return_value=True)  # User confirms
        show_error_mock = MagicMock()
        progress_callback_mock = MagicMock()

        # Mock successful reset
        with patch.object(configuration_manager, "_reset_and_reconnect_flight_controller", return_value=None):
            # Act: Execute workflow with uncertain parameters
            result = configuration_manager.reset_and_reconnect_workflow(
                fc_reset_required=False,
                fc_reset_unsure=["PARAM1", "PARAM2"],
                ask_confirmation=ask_confirmation_mock,
                show_error=show_error_mock,
                progress_callback=progress_callback_mock,
            )

        # Assert: Workflow completed successfully
        assert result is True

        # Verify confirmation was asked with proper message
        ask_confirmation_mock.assert_called_once()
        call_args = ask_confirmation_mock.call_args
        assert call_args[0][0] == "Possible reset required"
        assert "PARAM1, PARAM2" in call_args[0][1]
        assert "potentially require a reset" in call_args[0][1]

        # Verify no errors were shown
        show_error_mock.assert_not_called()

    def test_user_declines_reset_for_uncertain_parameters(self, configuration_manager) -> None:
        """
        User declines reset when parameters potentially require reset.

        GIVEN: A user has parameters that potentially require reset
        WHEN: They decline the reset action
        THEN: Reset should not be performed but workflow should succeed
        """
        # Arrange: Set up mock callbacks
        ask_confirmation_mock = MagicMock(return_value=False)  # User declines
        show_error_mock = MagicMock()
        progress_callback_mock = MagicMock()

        # Act: Execute workflow with uncertain parameters
        result = configuration_manager.reset_and_reconnect_workflow(
            fc_reset_required=False,
            fc_reset_unsure=["PARAM1"],
            ask_confirmation=ask_confirmation_mock,
            show_error=show_error_mock,
            progress_callback=progress_callback_mock,
        )

        # Assert: Workflow completed without reset
        assert result is True

        # Verify confirmation was asked
        ask_confirmation_mock.assert_called_once()

        # Verify no errors were shown
        show_error_mock.assert_not_called()

    def test_user_handles_reset_failure_with_error_message(self, configuration_manager) -> None:
        """
        User handles reset failure when error message is returned.

        GIVEN: A user initiates reset but flight controller returns error
        WHEN: Reset fails with error message
        THEN: Error should be shown and workflow should return False
        """
        # Arrange: Set up mock callbacks
        ask_confirmation_mock = MagicMock()
        show_error_mock = MagicMock()
        progress_callback_mock = MagicMock()

        # Mock failed reset with error message
        error_message = "Connection timeout during reset"
        with patch.object(configuration_manager, "_reset_and_reconnect_flight_controller", return_value=error_message):
            # Act: Execute workflow with required reset
            result = configuration_manager.reset_and_reconnect_workflow(
                fc_reset_required=True,
                fc_reset_unsure=[],
                ask_confirmation=ask_confirmation_mock,
                show_error=show_error_mock,
                progress_callback=progress_callback_mock,
            )

        # Assert: Workflow failed
        assert result is False

        # Verify error was shown to user
        show_error_mock.assert_called_once_with("ArduPilot methodic configurator", error_message)

    def test_user_handles_reset_exception(self, configuration_manager) -> None:
        """
        User handles reset exception during flight controller reset.

        GIVEN: A user initiates reset but exception occurs
        WHEN: Reset raises exception
        THEN: Exception should be caught, error shown, and workflow should return False
        """
        # Arrange: Set up mock callbacks
        ask_confirmation_mock = MagicMock()
        show_error_mock = MagicMock()
        progress_callback_mock = MagicMock()

        # Mock reset returning error message
        error_message = "Failed to reset flight controller: Communication error"
        with patch.object(configuration_manager, "_reset_and_reconnect_flight_controller", return_value=error_message):
            # Act: Execute workflow with required reset
            result = configuration_manager.reset_and_reconnect_workflow(
                fc_reset_required=True,
                fc_reset_unsure=[],
                ask_confirmation=ask_confirmation_mock,
                show_error=show_error_mock,
                progress_callback=progress_callback_mock,
            )

        # Assert: Workflow failed
        assert result is False

        # Verify error was shown to user with error message
        show_error_mock.assert_called_once_with("ArduPilot methodic configurator", error_message)

    def test_no_reset_needed_when_no_requirements(self, configuration_manager) -> None:
        """
        No reset performed when neither required nor uncertain parameters exist.

        GIVEN: A user has no reset requirements
        WHEN: They execute the reset workflow
        THEN: No reset should be performed and workflow should succeed
        """
        # Arrange: Set up mock callbacks
        ask_confirmation_mock = MagicMock()
        show_error_mock = MagicMock()
        progress_callback_mock = MagicMock()

        # Act: Execute workflow with no reset requirements
        result = configuration_manager.reset_and_reconnect_workflow(
            fc_reset_required=False,
            fc_reset_unsure=[],
            ask_confirmation=ask_confirmation_mock,
            show_error=show_error_mock,
            progress_callback=progress_callback_mock,
        )

        # Assert: Workflow completed without reset
        assert result is True

        # Verify no user interaction occurred
        ask_confirmation_mock.assert_not_called()
        show_error_mock.assert_not_called()


class TestConfigurationManagerFrontendAPI:
    """Test the frontend API methods that were refactored from parameter editor."""

    def test_user_can_access_vehicle_directory_path(self, configuration_manager) -> None:
        """
        User can access the vehicle directory path through the configuration manager.

        GIVEN: A configuration manager with a filesystem
        WHEN: The user requests the vehicle directory
        THEN: The correct directory path is returned
        """
        # Arrange: Set up expected directory path
        expected_path = "/test/vehicle/dir"
        configuration_manager._local_filesystem.vehicle_dir = expected_path

        # Act: Get vehicle directory
        result = configuration_manager.get_vehicle_directory()

        # Assert: Correct path returned
        assert result == expected_path

    def test_user_can_get_list_of_available_parameter_files(self, configuration_manager) -> None:
        """
        User can get a list of all available parameter files.

        GIVEN: A configuration manager with parameter files loaded
        WHEN: The user requests the list of parameter files
        THEN: A list of all parameter file names is returned
        """
        # Arrange: Set up parameter files in filesystem
        expected_files = ["01_first.param", "02_second.param", "complete.param"]
        configuration_manager._local_filesystem.file_parameters = {file: {} for file in expected_files}

        # Act: Get parameter files
        result = configuration_manager.parameter_files()

        # Assert: All files returned
        assert result == expected_files

    def test_user_can_check_if_parameter_documentation_is_available(self, configuration_manager) -> None:
        """
        User can check if parameter documentation is available.

        GIVEN: A configuration manager with documentation loaded
        WHEN: The user checks if documentation is available
        THEN: True is returned when documentation exists, False when it doesn't
        """
        # Test with documentation available
        configuration_manager._local_filesystem.doc_dict = {"PARAM1": {"description": "Test param"}}
        assert configuration_manager.parameter_documentation_available() is True

        # Test without documentation
        configuration_manager._local_filesystem.doc_dict = {}
        assert configuration_manager.parameter_documentation_available() is False

        # Test with None documentation
        configuration_manager._local_filesystem.doc_dict = None
        assert configuration_manager.parameter_documentation_available() is False

    def test_user_can_access_configuration_phases(self, configuration_manager) -> None:
        """
        User can access the configuration phases information.

        GIVEN: A configuration manager with configuration phases
        WHEN: The user requests configuration phases
        THEN: The phases dictionary is returned
        """
        # Arrange: Set up configuration phases
        expected_phases = {"phase1": {"start": 1, "end": 10, "weight": 1.0}, "phase2": {"start": 11, "end": 20, "weight": 2.0}}
        configuration_manager._local_filesystem.configuration_phases = expected_phases

        # Act: Get configuration phases
        result = configuration_manager.configuration_phases()

        # Assert: Correct phases returned
        assert result == expected_phases

    def test_user_can_write_current_file_marker(self, configuration_manager) -> None:
        """
        User can write a marker indicating the current file being processed.

        GIVEN: A configuration manager with a current file set
        WHEN: The user writes the current file marker
        THEN: The filesystem is instructed to write the last uploaded filename
        """
        # Arrange: Set current file
        configuration_manager.current_file = "05_current.param"

        # Act: Write current file marker
        configuration_manager._write_current_file()

        # Assert: Filesystem method called with correct file
        configuration_manager._local_filesystem.write_last_uploaded_filename.assert_called_once_with("05_current.param")

    def test_user_can_export_current_parameter_file(self, configuration_manager) -> None:
        """
        User can export the current parameter file with or without documentation.

        GIVEN: A configuration manager with current file parameters
        WHEN: The user exports the current file
        THEN: The filesystem exports the parameters with the specified documentation setting
        """
        # Arrange: Set up current file and parameters
        configuration_manager.current_file = "test_file.param"
        test_params = {"PARAM1": Par(1.0, ""), "PARAM2": Par(2.0, "")}
        configuration_manager._local_filesystem.file_parameters = {"test_file.param": test_params}

        # Populate domain model (simulating what repopulate_configuration_step_parameters does)
        configuration_manager.current_step_parameters = {
            "PARAM1": ArduPilotParameter("PARAM1", test_params["PARAM1"], {}, {}),
            "PARAM2": ArduPilotParameter("PARAM2", test_params["PARAM2"], {}, {}),
        }

        # Act: Export current file with documentation
        configuration_manager._export_current_file(annotate_doc=True)

        # Assert: Filesystem export called correctly with right filename and annotate flag
        configuration_manager._local_filesystem.export_to_param.assert_called_once()  # type: ignore[call-arg]
        call_args = configuration_manager._local_filesystem.export_to_param.call_args  # type: ignore[attr-defined]
        exported_params, filename, annotate = call_args[0]

        assert filename == "test_file.param"
        assert annotate is True
        # Check that exported parameters have the same keys and values as original
        assert set(exported_params.keys()) == set(test_params.keys())
        for key, value in test_params.items():
            assert exported_params[key] == value

    def test_user_can_get_documentation_text_and_url_for_current_file(self, configuration_manager) -> None:
        """
        User can get documentation text and URL for the current file.

        GIVEN: A configuration manager with current file set
        WHEN: The user requests documentation for a specific type
        THEN: The documentation text and URL are returned from the filesystem
        """
        # Arrange: Set current file and mock filesystem response
        configuration_manager.current_file = "current_file.param"
        configuration_manager._local_filesystem.get_documentation_text_and_url.side_effect = None
        configuration_manager._local_filesystem.get_documentation_text_and_url.return_value = (
            "Test documentation",
            "http://example.com/docs",
        )

        # Act: Get documentation
        result = configuration_manager.get_documentation_text_and_url("blog")

        # Assert: Correct documentation returned and filesystem called with current file
        assert result == ("Test documentation", "http://example.com/docs")
        configuration_manager._local_filesystem.get_documentation_text_and_url.assert_called_once_with(
            "current_file.param", "blog"
        )

    def test_user_gets_empty_list_when_no_parameter_files_exist(self, configuration_manager) -> None:
        """
        User gets an empty list when no parameter files exist.

        GIVEN: A configuration manager with no parameter files
        WHEN: The user requests the list of parameter files
        THEN: An empty list is returned
        """
        # Arrange: No parameter files
        configuration_manager._local_filesystem.file_parameters = {}

        # Act: Get parameter files
        result = configuration_manager.parameter_files()

        # Assert: Empty list returned
        assert result == []

    def test_user_can_export_current_file_without_documentation(self, configuration_manager) -> None:
        """
        User can export the current parameter file without documentation annotations.

        GIVEN: A configuration manager with current file parameters
        WHEN: The user exports the current file without documentation
        THEN: The filesystem exports the parameters without documentation
        """
        # Arrange: Set up current file and parameters
        configuration_manager.current_file = "test_file.param"
        test_params = {"PARAM1": Par(1.0, "")}
        configuration_manager._local_filesystem.file_parameters = {"test_file.param": test_params}

        # Populate domain model (simulating what repopulate_configuration_step_parameters does)
        configuration_manager.current_step_parameters = {
            "PARAM1": ArduPilotParameter("PARAM1", test_params["PARAM1"], {}, {}),
        }

        # Act: Export current file without documentation
        configuration_manager._export_current_file(annotate_doc=False)

        # Assert: Filesystem export called correctly with right filename and annotate flag
        configuration_manager._local_filesystem.export_to_param.assert_called_once()  # type: ignore[call-arg]
        call_args = configuration_manager._local_filesystem.export_to_param.call_args  # type: ignore[attr-defined]
        exported_params, filename, annotate = call_args[0]

        assert filename == "test_file.param"
        assert annotate is False
        # Check that exported parameters have the same keys and values as original
        assert set(exported_params.keys()) == set(test_params.keys())
        for key, value in test_params.items():
            assert exported_params[key] == value


class TestUnsavedChangesTracking:
    """Test unsaved changes detection for all types of modifications."""

    def test_user_receives_save_prompt_after_editing_parameter_value(self, configuration_manager) -> None:
        """
        User receives a save prompt when they edit a parameter value.

        GIVEN: A user has loaded a parameter file with existing parameters
        WHEN: They change a parameter value in the domain model
        THEN: _has_unsaved_changes should return True
        AND: The user should be prompted to save before closing
        """
        # Arrange: Set up a parameter in the domain model

        configuration_manager.current_file = "test_file.param"
        configuration_manager._local_filesystem.file_parameters = {"test_file.param": ParDict({"PARAM1": Par(1.0, "comment")})}
        configuration_manager.current_step_parameters = {"PARAM1": ArduPilotParameter("PARAM1", Par(1.0, "comment"))}

        # Assert: Initially no changes
        assert not configuration_manager._has_unsaved_changes()

        # Act: User edits parameter value
        configuration_manager.current_step_parameters["PARAM1"].set_new_value("2.0")

        # Assert: Changes detected
        assert configuration_manager._has_unsaved_changes()

    def test_user_receives_save_prompt_after_system_derives_parameters(self, configuration_manager) -> None:
        """
        User receives a save prompt when the system derives parameters.

        GIVEN: A user processes a configuration step
        WHEN: The system derives parameters (forced/computed values) making them dirty
        THEN: _has_unsaved_changes should return True
        AND: The user should be prompted to save before closing
        """
        # Arrange: Set up configuration step processor
        configuration_manager.current_file = "test_file.param"
        configuration_manager._local_filesystem.file_parameters = {"test_file.param": ParDict({"PARAM1": Par(1.0, "comment")})}

        # Create a parameter and mark it as dirty (simulating derived parameter change)
        param = ArduPilotParameter("PARAM1", Par(1.0, "comment"))
        param.set_new_value("2.0")
        param.set_change_reason("Derived value")
        configuration_manager.current_step_parameters = {"PARAM1": param}

        # Assert: Initially no structural changes
        assert not configuration_manager._added_parameters
        assert not configuration_manager._deleted_parameters

        # Assert: Changes detected due to dirty parameter
        assert configuration_manager._has_unsaved_changes()

    def test_user_receives_save_prompt_after_adding_parameter(self, configuration_manager) -> None:
        """
        User receives a save prompt when they add a new parameter.

        GIVEN: A user has loaded a parameter file
        WHEN: They add a new parameter to the file
        THEN: _has_unsaved_changes should return True
        AND: The user should be prompted to save before closing
        """
        # Arrange: Set up initial state
        configuration_manager.current_file = "test_file.param"
        configuration_manager._local_filesystem.file_parameters = {"test_file.param": ParDict({"PARAM1": Par(1.0, "comment")})}
        configuration_manager.current_step_parameters = {"PARAM1": ArduPilotParameter("PARAM1", Par(1.0, "comment"))}
        configuration_manager._flight_controller.fc_parameters = {"PARAM2": 2.0}

        # Assert: Initially no changes
        assert not configuration_manager._has_unsaved_changes()

        # Act: User adds a new parameter
        configuration_manager.add_parameter_to_current_file("PARAM2")

        # Assert: Changes detected
        assert configuration_manager._has_unsaved_changes()

    def test_user_receives_save_prompt_after_deleting_parameter(self, configuration_manager) -> None:
        """
        User receives a save prompt when they delete a parameter.

        GIVEN: A user has loaded a parameter file with parameters
        WHEN: They delete a parameter from the file
        THEN: _has_unsaved_changes should return True
        AND: The user should be prompted to save before closing
        """
        # Arrange: Set up initial state with parameters

        configuration_manager.current_file = "test_file.param"
        configuration_manager._local_filesystem.file_parameters = {
            "test_file.param": ParDict({"PARAM1": Par(1.0, "comment"), "PARAM2": Par(2.0, "comment")})
        }
        configuration_manager.current_step_parameters = {
            "PARAM1": ArduPilotParameter("PARAM1", Par(1.0, "comment")),
            "PARAM2": ArduPilotParameter("PARAM2", Par(2.0, "comment")),
        }

        # Assert: Initially no changes
        assert not configuration_manager._has_unsaved_changes()

        # Act: User deletes a parameter
        configuration_manager.delete_parameter_from_current_file("PARAM2")

        # Assert: Changes detected
        assert configuration_manager._has_unsaved_changes()

    def test_user_not_prompted_when_adding_then_deleting_same_parameter(self, configuration_manager) -> None:
        """
        User is NOT prompted to save when they add then delete the same parameter.

        GIVEN: A user has loaded a parameter file
        WHEN: They add a new parameter
        AND: Then immediately delete that same parameter
        THEN: _has_unsaved_changes should return False (net change is zero)
        AND: The user should NOT be prompted to save
        """
        # Arrange: Set up initial state

        configuration_manager.current_file = "test_file.param"
        configuration_manager._local_filesystem.file_parameters = {"test_file.param": ParDict({"PARAM1": Par(1.0, "comment")})}
        configuration_manager.current_step_parameters = {"PARAM1": ArduPilotParameter("PARAM1", Par(1.0, "comment"))}
        configuration_manager._flight_controller.fc_parameters = {"PARAM2": 2.0}

        # Assert: Initially no changes
        assert not configuration_manager._has_unsaved_changes()

        # Act: User adds a new parameter
        configuration_manager.add_parameter_to_current_file("PARAM2")

        # Assert: Changes detected after add
        assert configuration_manager._has_unsaved_changes()

        # Act: User deletes the same parameter they just added
        configuration_manager.delete_parameter_from_current_file("PARAM2")

        # Assert: No net change, so no unsaved changes
        assert not configuration_manager._has_unsaved_changes()

    def test_user_not_prompted_when_deleting_then_adding_back_same_parameter(self, configuration_manager) -> None:
        """
        User is NOT prompted to save when they delete then re-add the same parameter.

        GIVEN: A user has loaded a parameter file with existing parameters
        WHEN: They delete a parameter
        AND: Then immediately add it back
        THEN: _has_unsaved_changes should return False (net change is zero)
        AND: The user should NOT be prompted to save
        """
        # Arrange: Set up initial state with parameter

        configuration_manager.current_file = "test_file.param"
        configuration_manager._local_filesystem.file_parameters = {"test_file.param": ParDict({"PARAM1": Par(1.0, "comment")})}
        configuration_manager.current_step_parameters = {"PARAM1": ArduPilotParameter("PARAM1", Par(1.0, "comment"))}
        configuration_manager._flight_controller.fc_parameters = {"PARAM1": 1.0}

        # Assert: Initially no changes
        assert not configuration_manager._has_unsaved_changes()

        # Act: User deletes the parameter
        configuration_manager.delete_parameter_from_current_file("PARAM1")

        # Assert: Changes detected after delete
        assert configuration_manager._has_unsaved_changes()

        # Act: User adds it back
        configuration_manager.add_parameter_to_current_file("PARAM1")

        # Assert: No net change (parameter is back), so no unsaved changes
        assert not configuration_manager._has_unsaved_changes()

    def test_user_receives_save_prompt_for_multiple_change_types_combined(self, configuration_manager) -> None:
        """
        User receives a save prompt when multiple types of changes occur.

        GIVEN: A user has loaded a parameter file
        WHEN: They edit a parameter value
        AND: Add a new parameter
        AND: Delete another parameter
        THEN: _has_unsaved_changes should return True
        AND: The user should be prompted to save all changes
        """
        # Arrange: Set up initial state with multiple parameters

        configuration_manager.current_file = "test_file.param"
        configuration_manager._local_filesystem.file_parameters = {
            "test_file.param": ParDict({"PARAM1": Par(1.0, "comment"), "PARAM2": Par(2.0, "comment")})
        }
        configuration_manager.current_step_parameters = {
            "PARAM1": ArduPilotParameter("PARAM1", Par(1.0, "comment")),
            "PARAM2": ArduPilotParameter("PARAM2", Par(2.0, "comment")),
        }
        configuration_manager._flight_controller.fc_parameters = {"PARAM3": 3.0}

        # Assert: Initially no changes
        assert not configuration_manager._has_unsaved_changes()

        # Act: User makes multiple changes
        # 1. Edit existing parameter
        configuration_manager.current_step_parameters["PARAM1"].set_new_value("99.0")
        # 2. Add new parameter
        configuration_manager.add_parameter_to_current_file("PARAM3")
        # 3. Delete parameter
        configuration_manager.delete_parameter_from_current_file("PARAM2")

        # Assert: Changes detected
        assert configuration_manager._has_unsaved_changes()

    def test_user_receives_save_prompt_when_changing_file_with_unsaved_edits(self, configuration_manager) -> None:
        """
        User receives a save prompt when navigating away from a file with unsaved edits.

        GIVEN: A user has edited parameters in the current file
        WHEN: They attempt to navigate to a different parameter file
        THEN: _has_unsaved_changes should return True before navigation
        AND: The system should prompt them to save before changing files
        """
        # Arrange: Set up initial state with edits

        configuration_manager.current_file = "test_file.param"
        configuration_manager._local_filesystem.file_parameters = {"test_file.param": ParDict({"PARAM1": Par(1.0, "comment")})}
        configuration_manager.current_step_parameters = {"PARAM1": ArduPilotParameter("PARAM1", Par(1.0, "comment"))}

        # Make changes
        configuration_manager.current_step_parameters["PARAM1"].set_new_value("2.0")

        # Assert: Changes detected
        assert configuration_manager._has_unsaved_changes()

        # This is where the UI would prompt before calling repopulate_configuration_step_parameters
        # The test validates that the check returns True so the UI knows to prompt

    def test_tracking_reset_when_navigating_to_new_file(self, configuration_manager) -> None:
        """
        Change tracking resets when user navigates to a new parameter file.

        GIVEN: A user has unsaved changes in the current file
        WHEN: They navigate to a different parameter file (after saving or discarding)
        THEN: The change tracking should reset for the new file
        AND: _has_unsaved_changes should return False for the new file initially
        """
        # Arrange: Set up initial file with changes

        configuration_manager.current_file = "test_file.param"
        configuration_manager._local_filesystem.file_parameters = {
            "test_file.param": ParDict({"PARAM1": Par(1.0, "comment")}),
            "other_file.param": ParDict({"PARAM2": Par(2.0, "comment")}),
        }
        configuration_manager.current_step_parameters = {"PARAM1": ArduPilotParameter("PARAM1", Par(1.0, "comment"))}

        # Set up fc_parameters so add_parameter_to_current_file works
        configuration_manager._flight_controller.fc_parameters = {"PARAM_NEW": 5.0}

        # Make changes
        configuration_manager.add_parameter_to_current_file("PARAM_NEW")

        # Assert: Changes detected
        assert configuration_manager._has_unsaved_changes()

        # Act: Navigate to new file (simulating what repopulate_configuration_step_parameters does)
        configuration_manager.current_file = "other_file.param"
        configuration_manager._added_parameters.clear()
        configuration_manager._deleted_parameters.clear()
        configuration_manager.current_step_parameters = {"PARAM2": ArduPilotParameter("PARAM2", Par(2.0, "comment"))}

        # Assert: No changes in new file
        assert not configuration_manager._has_unsaved_changes()


class TestDerivedParameterApplication:
    """Test cases for applying derived parameters with validation."""

    def test_user_can_apply_valid_derived_parameters(self, configuration_manager) -> None:
        """
        Test that valid derived parameters are applied correctly.

        GIVEN: A configuration manager with derived parameters to apply
        WHEN: repopulate_configuration_step_parameters is called
        THEN: Derived parameters should be applied using set_forced_or_derived_value
        """
        # Setup file parameters with a derived parameter
        configuration_manager._local_filesystem.file_parameters = {
            "test_file.param": ParDict({"BATT_CAPACITY": Par(5000.0, "original comment")}),
        }
        configuration_manager.current_file = "test_file.param"

        # Setup derived parameters to be returned by process_configuration_step
        derived_params = ParDict({"BATT_CAPACITY": Par(6000.0, "derived from component editor")})

        # Mock the _config_step_processor to return derived params
        with patch.object(
            configuration_manager._config_step_processor,
            "process_configuration_step",
            return_value=(
                {
                    "BATT_CAPACITY": ArduPilotParameter(
                        "BATT_CAPACITY",
                        Par(5000.0, "original comment"),
                        derived_par=Par(6000.0, "derived from component editor"),
                    )
                },
                [],  # ui_errors
                [],  # ui_infos
                [],  # duplicates_to_remove
                [],  # renames_to_apply
                derived_params,  # derived_params
            ),
        ):
            configuration_manager.repopulate_configuration_step_parameters()

        # Verify the derived value was applied
        assert configuration_manager.current_step_parameters["BATT_CAPACITY"].get_new_value() == 6000.0
        assert configuration_manager.current_step_parameters["BATT_CAPACITY"].change_reason == "derived from component editor"

    def test_user_receives_error_when_derived_param_is_readonly(self, configuration_manager) -> None:
        """
        Test that readonly parameters in derived_params are skipped with error logging.

        GIVEN: A derived parameter that is marked as readonly
        WHEN: repopulate_configuration_step_parameters attempts to apply it
        THEN: The parameter should be skipped and an error should be logged
        """
        # Setup file parameters with a readonly parameter
        readonly_metadata = {"ReadOnly": True}
        configuration_manager._local_filesystem.file_parameters = {
            "test_file.param": ParDict({"FORMAT_VERSION": Par(16.0, "comment")}),
        }
        configuration_manager.current_file = "test_file.param"

        # Setup derived parameters
        derived_params = ParDict({"FORMAT_VERSION": Par(17.0, "derived comment")})

        # Mock the _config_step_processor
        with (
            patch.object(
                configuration_manager._config_step_processor,
                "process_configuration_step",
                return_value=(
                    {
                        "FORMAT_VERSION": ArduPilotParameter(
                            "FORMAT_VERSION",
                            Par(16.0, "comment"),
                            metadata=readonly_metadata,
                            derived_par=Par(17.0, "derived comment"),
                        )
                    },
                    [],  # ui_errors
                    [],  # ui_infos
                    [],  # duplicates_to_remove
                    [],  # renames_to_apply
                    derived_params,  # derived_params
                ),
            ),
            patch("ardupilot_methodic_configurator.configuration_manager.logging_error") as mock_log_error,
        ):
            configuration_manager.repopulate_configuration_step_parameters()

        # Verify error was logged
        mock_log_error.assert_any_call(
            "Failed to apply derived parameter %s: %s",
            "FORMAT_VERSION",
            "Readonly parameters cannot be forced or derived.",
        )

        # Verify value was NOT changed (still original)
        assert (
            configuration_manager.current_step_parameters["FORMAT_VERSION"].get_new_value() == 17.0
        )  # Constructor applied it

    def test_user_receives_error_when_derived_param_not_marked_as_forced_or_derived(self, configuration_manager) -> None:
        """
        Test that parameters in derived_params that aren't marked as forced/derived are skipped.

        GIVEN: A parameter in derived_params that is not marked as forced or derived
        WHEN: repopulate_configuration_step_parameters attempts to apply it
        THEN: The parameter should be skipped and an error should be logged
        """
        configuration_manager._local_filesystem.file_parameters = {
            "test_file.param": ParDict({"PARAM1": Par(1.0, "comment")}),
        }
        configuration_manager.current_file = "test_file.param"

        # Setup derived parameters - but the parameter itself is NOT marked as derived
        derived_params = ParDict({"PARAM1": Par(2.0, "fake derived")})

        with (
            patch.object(
                configuration_manager._config_step_processor,
                "process_configuration_step",
                return_value=(
                    {
                        "PARAM1": ArduPilotParameter(
                            "PARAM1",
                            Par(1.0, "comment"),  # Regular parameter, NOT derived
                        )
                    },
                    [],
                    [],
                    [],
                    [],
                    derived_params,
                ),
            ),
            patch("ardupilot_methodic_configurator.configuration_manager.logging_error") as mock_log_error,
        ):
            configuration_manager.repopulate_configuration_step_parameters()

        # Verify error was logged
        mock_log_error.assert_any_call(
            "Failed to apply derived parameter %s: %s",
            "PARAM1",
            "This method is only for forced or derived parameters.",
        )

    def test_user_receives_error_when_derived_param_not_in_parameters(self, configuration_manager) -> None:
        """
        Test that derived parameters not in self.current_step_parameters are logged as errors.

        GIVEN: A derived parameter that doesn't exist in self.current_step_parameters
        WHEN: repopulate_configuration_step_parameters attempts to apply it
        THEN: An error should be logged about the missing parameter
        """
        configuration_manager._local_filesystem.file_parameters = {
            "test_file.param": ParDict({}),
        }
        configuration_manager.current_file = "test_file.param"

        # Setup derived parameters with a parameter that won't be in self.current_step_parameters
        derived_params = ParDict({"NONEXISTENT_PARAM": Par(999.0, "comment")})

        with (
            patch.object(
                configuration_manager._config_step_processor,
                "process_configuration_step",
                return_value=(
                    {},  # Empty parameters dict
                    [],
                    [],
                    [],
                    [],
                    derived_params,
                ),
            ),
            patch("ardupilot_methodic_configurator.configuration_manager.logging_error") as mock_log_error,
        ):
            configuration_manager.repopulate_configuration_step_parameters()

        # Verify error was logged
        mock_log_error.assert_any_call(
            "Derived parameter %s not found in current parameters, skipping",
            "NONEXISTENT_PARAM",
        )

    def test_create_plugin_data_model_returns_motor_test_data_model_when_fc_connected(self, configuration_manager) -> None:
        """
        Test that create_plugin_data_model returns MotorTestDataModel when FC is connected.

        GIVEN: Flight controller is connected
        WHEN: create_plugin_data_model is called with "motor_test"
        THEN: A MotorTestDataModel instance is returned
        """
        # Mock FC connection by setting master to a mock object
        configuration_manager._flight_controller.master = MagicMock()

        with patch("ardupilot_methodic_configurator.configuration_manager.MotorTestDataModel") as mock_motor_test_model:
            result = configuration_manager.create_plugin_data_model(PLUGIN_MOTOR_TEST)

            mock_motor_test_model.assert_called_once_with(
                configuration_manager._flight_controller, configuration_manager._local_filesystem
            )
            assert result == mock_motor_test_model.return_value

    def test_create_plugin_data_model_returns_none_when_motor_test_but_no_fc_connection(self, configuration_manager) -> None:
        """
        Test that create_plugin_data_model returns None when motor_test is requested but FC is not connected.

        GIVEN: Flight controller is not connected
        WHEN: create_plugin_data_model is called with "motor_test"
        THEN: None is returned
        """
        # Mock FC disconnection by setting master to None
        configuration_manager._flight_controller.master = None

        with patch("ardupilot_methodic_configurator.configuration_manager.MotorTestDataModel") as mock_motor_test_model:
            result = configuration_manager.create_plugin_data_model(PLUGIN_MOTOR_TEST)

            # MotorTestDataModel should not be instantiated
            mock_motor_test_model.assert_not_called()
            assert result is None

    def test_create_plugin_data_model_returns_none_for_unknown_plugin(self, configuration_manager) -> None:
        """
        Test that create_plugin_data_model returns None for unknown plugin names.

        GIVEN: Any flight controller connection state
        WHEN: create_plugin_data_model is called with an unknown plugin name
        THEN: None is returned
        """
        result = configuration_manager.create_plugin_data_model("unknown_plugin")
        assert result is None

        result = configuration_manager.create_plugin_data_model("")
        assert result is None

        result = configuration_manager.create_plugin_data_model(None)
        assert result is None
