#!/usr/bin/env python3

"""
Unit tests for ConfigurationManager class - Documentation Frame API.

This file tests the ConfigurationManager methods used by the documentation frame frontend.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2025 Amilcar Lucas

SPDX-License-Identifier: GPL-3.0-or-later
"""

from unittest.mock import MagicMock, patch

import pytest

from ardupilot_methodic_configurator.configuration_manager import ConfigurationManager
from ardupilot_methodic_configurator.data_model_par_dict import Par, ParDict
from tests.conftest import assert_download_workflow_result, mock_get_documentation_text_and_url_basic

# pylint: disable=redefined-outer-name, protected-access


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
    mock_fs.get_documentation_text_and_url.side_effect = mock_get_documentation_text_and_url_basic
    return mock_fs


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
            ("complete.param", True),  # Special file is optional
        ]

        for filename, expected_optional in test_cases:
            # Act: Check if file is optional
            is_optional = configuration_manager.is_configuration_step_optional(filename)

            # Assert: Correct optionality determined
            assert is_optional == expected_optional

    def test_user_handles_edge_cases_in_configuration_step_validation(self, configuration_manager) -> None:
        """
        User handles edge cases gracefully when validating configuration steps.

        GIVEN: A user has edge case configuration file names
        WHEN: They check if configuration steps are optional
        THEN: The validation should handle edge cases correctly
        """
        # Arrange: Edge case file names
        edge_cases = [
            ("", True),  # Empty string is optional
            ("0_invalid_number.param", True),  # Invalid number format is optional
            ("00_default.param", True),  # Default file is optional
            ("1.param", False),  # Valid single digit is mandatory
            ("10_config.param", False),  # Valid two digits is mandatory
            ("123_large_number.param", False),  # Large number is mandatory
        ]

        for filename, expected_optional in edge_cases:
            # Act: Check edge case
            is_optional = configuration_manager.is_configuration_step_optional(filename)

            # Assert: Edge case handled correctly
            assert is_optional == expected_optional

    def test_user_validates_special_configuration_files(self, configuration_manager) -> None:
        """
        User validates special configuration files have correct optionality.

        GIVEN: A user has special configuration files like complete.param and defaults
        WHEN: They check if these configuration steps are optional
        THEN: Special files should follow expected optionality rules
        """
        # Arrange: Special configuration file names
        special_files = [
            ("complete.param", True),  # Complete file is optional
            ("00_default.param", True),  # Default file is optional
            ("99_optional_final.param", False),  # Numbered file is mandatory
        ]

        for filename, expected_optional in special_files:
            # Act: Check special file
            is_optional = configuration_manager.is_configuration_step_optional(filename)

            # Assert: Special file has correct optionality
            assert is_optional == expected_optional


class TestFileDownloadUrlWorkflows:
    """Test file download URL workflow business logic methods with callback injection."""

    def test_user_can_complete_download_file_workflow_successfully(self, configuration_manager) -> None:
        """
        User can complete the download file workflow with callbacks.

        GIVEN: A user has a file that needs to be downloaded and valid workflow callbacks
        WHEN: They execute the download workflow with user confirmation
        THEN: The file should be downloaded successfully
        """
        # Test successful download workflow
        assert_download_workflow_result(
            configuration_manager,
            selected_file="test_file.param",
            download_result=True,
            confirmation_result=True,
            expect_error_shown=False,
        )

    def test_user_handles_download_failure_in_workflow(self, configuration_manager) -> None:
        """
        User handles download failure gracefully in the workflow.

        GIVEN: A user has a file that needs to be downloaded but download fails
        WHEN: They execute the download workflow
        THEN: Error should be shown and workflow should return False
        """
        # Test failed download workflow
        assert_download_workflow_result(
            configuration_manager,
            selected_file="test_file.param",
            download_result=False,
            confirmation_result=True,
            expect_error_shown=True,
        )

    def test_user_declines_download_in_workflow(self, configuration_manager) -> None:
        """
        User can decline download in the workflow.

        GIVEN: A user has a file that could be downloaded
        WHEN: They decline the download confirmation
        THEN: No download should occur and workflow should return True
        """
        # Test declined download workflow
        assert_download_workflow_result(
            configuration_manager,
            selected_file="test_file.param",
            download_result=True,  # Download would succeed, but user declines
            confirmation_result=False,
            expect_error_shown=False,
        )

    def test_user_skips_download_when_no_url_available(self, configuration_manager) -> None:
        """
        User skips download when no URL is available for the file.

        GIVEN: A user has a file with no download URL configured
        WHEN: They attempt to download the file
        THEN: No download should occur and workflow should return True
        """
        # Arrange: Set up file with no URL
        selected_file = "test_file.param"

        configuration_manager._local_filesystem.get_download_url_and_local_filename.return_value = (None, "test.bin")

        ask_confirmation_mock = MagicMock()
        show_error_mock = MagicMock()

        # Act: Execute download workflow with no URL
        result = configuration_manager.should_download_file_from_url_workflow(
            selected_file,
            ask_confirmation=ask_confirmation_mock,
            show_error=show_error_mock,
        )

        # Assert: Workflow succeeded without download attempt
        assert result is True
        ask_confirmation_mock.assert_not_called()
        show_error_mock.assert_not_called()

    def test_user_skips_download_when_file_already_exists(self, configuration_manager) -> None:
        """
        User skips download when file already exists locally.

        GIVEN: A user has a file that could be downloaded but already exists locally
        WHEN: They attempt to download the file
        THEN: No download should occur and workflow should return True
        """
        # Arrange: Set up file that already exists
        selected_file = "test_file.param"
        url = "https://example.com/test.bin"
        local_filename = "test.bin"

        configuration_manager._local_filesystem.get_download_url_and_local_filename.return_value = (url, local_filename)
        configuration_manager._local_filesystem.vehicle_configuration_file_exists.return_value = True

        ask_confirmation_mock = MagicMock()
        show_error_mock = MagicMock()

        # Act: Execute download workflow for existing file
        result = configuration_manager.should_download_file_from_url_workflow(
            selected_file,
            ask_confirmation=ask_confirmation_mock,
            show_error=show_error_mock,
        )

        # Assert: Workflow succeeded without download attempt
        assert result is True
        ask_confirmation_mock.assert_not_called()
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
            # Act: Execute summary files workflow
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
            # Act: Execute workflow with declined overwrite
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


class TestParameterSummaryMethods:
    """Test suite for parameter summary generation business logic methods."""

    def test_generate_parameter_summary_with_valid_parameters(self, configuration_manager) -> None:
        """
        User can generate parameter summary with valid parameters.

        GIVEN: A user has flight controller parameters and documentation
        WHEN: They generate parameter summary
        THEN: Parameters should be categorized correctly
        """
        # Arrange: Set up FC parameters and documentation
        fc_params = {"PARAM1": 1.0, "PARAM2": 2.0, "PARAM3": 3.0}
        configuration_manager._flight_controller.fc_parameters = fc_params

        # Mock the filesystem methods
        annotated_params = {"PARAM1": Par(1.0), "PARAM2": Par(2.0), "PARAM3": Par(3.0)}
        configuration_manager._local_filesystem.annotate_intermediate_comments_to_param_dict.return_value = annotated_params

        read_only = {"PARAM2": Par(2.0)}
        calibrations = {"PARAM3": Par(3.0)}
        non_calibrations = {"PARAM1": Par(1.0)}
        configuration_manager._local_filesystem.categorize_parameters.return_value = (
            read_only,
            calibrations,
            non_calibrations,
        )

        # Act: Generate parameter summary
        summary = configuration_manager._generate_parameter_summary()

        # Assert: Parameters categorized correctly
        assert "complete" in summary
        assert "read_only" in summary
        assert "calibrations" in summary
        assert "non_calibrations" in summary

        # Verify complete contains all parameters
        assert len(summary["complete"]) == 3

        # Verify read-only parameter is categorized
        assert len(summary["read_only"]) == 1
        assert "PARAM2" in summary["read_only"]

        # Verify calibration parameter is categorized
        assert len(summary["calibrations"]) == 1
        assert "PARAM3" in summary["calibrations"]

    def test_generate_parameter_summary_with_no_fc_parameters(self, configuration_manager) -> None:
        """
        User handles parameter summary generation with no FC parameters.

        GIVEN: A user has no flight controller parameters
        WHEN: They generate parameter summary
        THEN: Empty summary should be returned
        """
        # Arrange: No FC parameters
        configuration_manager._flight_controller.fc_parameters = None

        # Act: Generate summary with no parameters
        summary = configuration_manager._generate_parameter_summary()

        # Assert: Empty summary returned
        assert summary == {}

    def test_generate_parameter_summary_with_empty_fc_parameters(self, configuration_manager) -> None:
        """
        User handles parameter summary generation with empty FC parameters.

        GIVEN: A user has empty flight controller parameters
        WHEN: They generate parameter summary
        THEN: Empty summary should be returned
        """
        # Arrange: Empty FC parameters
        configuration_manager._flight_controller.fc_parameters = {}

        # Act: Generate summary with empty parameters
        summary = configuration_manager._generate_parameter_summary()

        # Assert: Empty summary returned
        assert summary == {}

    def test_get_parameter_summary_msg_with_valid_summary(self, configuration_manager) -> None:
        """
        User can get parameter summary message with valid summary.

        GIVEN: A user has a parameter summary
        WHEN: They get the summary message
        THEN: Formatted message should be returned
        """
        # Arrange: Set up FC with parameters for summary generation
        configuration_manager._flight_controller.fc_parameters = {
            "PARAM1": 1.0,
            "PARAM2": 2.0,
        }

        # Mock the filesystem methods with realistic data
        annotated_params = {
            "PARAM1": Par(1.0),
            "PARAM2": Par(2.0),
        }
        configuration_manager._local_filesystem.annotate_intermediate_comments_to_param_dict.return_value = annotated_params

        read_only = {"PARAM1": Par(1.0)}
        calibrations = {"PARAM2": Par(2.0)}
        non_calibrations: dict[str, Par] = {}
        configuration_manager._local_filesystem.categorize_parameters.return_value = (
            read_only,
            calibrations,
            non_calibrations,
        )

        # Act: Get parameter summary message
        summary = configuration_manager._generate_parameter_summary()
        message = configuration_manager._get_parameter_summary_msg(summary)

        # Assert: Message contains summary information
        assert "Methodic configuration of 2 parameters complete" in message
        assert "1 non-default read-only parameters" in message
        assert "1 non-default writable sensor-calibrations" in message

    def test_get_parameter_summary_msg_with_empty_summary(self, configuration_manager) -> None:
        """
        User handles parameter summary message with empty summary.

        GIVEN: A user has an empty parameter summary
        WHEN: They get the summary message
        THEN: Appropriate empty message should be returned
        """
        # Arrange: Set up FC with no parameters
        configuration_manager._flight_controller.fc_parameters = None

        # Act: Get parameter summary message
        summary = configuration_manager._generate_parameter_summary()
        message = configuration_manager._get_parameter_summary_msg(summary)

        # Assert: Empty message returned
        assert "No parameters available for summary" in message


class TestDocumentationFrameAPIMethods:
    """Test suite for frontend_tkinter_parameter_editor_documentation_frame.py API methods."""

    def test_get_documentation_text_and_url_with_current_file(self, configuration_manager) -> None:
        """
        User can get documentation text and URL using current file.

        GIVEN: A user has a configuration manager with a current file
        WHEN: They request documentation text and URL without specifying filename
        THEN: The method uses the current file and returns the expected result
        """
        # Arrange: Set up expected return value
        expected_text = "10% mandatory (90% optional)"
        expected_url = "docs/00_default.param.html"
        configuration_manager._local_filesystem.get_documentation_text_and_url.return_value = (expected_text, expected_url)

        # Act: Get documentation text and URL without filename parameter
        text, url = configuration_manager.get_documentation_text_and_url("mandatory")

        # Assert: Method uses current file and returns expected values
        configuration_manager._local_filesystem.get_documentation_text_and_url.assert_called_once_with(
            "00_default.param", "mandatory"
        )
        assert text == expected_text
        assert url == expected_url

    def test_get_documentation_text_and_url_with_explicit_filename(self, configuration_manager) -> None:
        """
        User can get documentation text and URL with explicit filename.

        GIVEN: A user has a configuration manager
        WHEN: They request documentation text and URL with an explicit filename
        THEN: The method uses the provided filename instead of current file
        """
        # Arrange: Set up expected return value
        expected_text = "50% mandatory (50% optional)"
        expected_url = "docs/test_file.param.html"
        configuration_manager._local_filesystem.get_documentation_text_and_url.return_value = (expected_text, expected_url)

        # Act: Get documentation text and URL with explicit filename
        text, url = configuration_manager.get_documentation_text_and_url("mandatory", "test_file.param")

        # Assert: Method uses provided filename
        configuration_manager._local_filesystem.get_documentation_text_and_url.assert_called_once_with(
            "test_file.param", "mandatory"
        )
        assert text == expected_text
        assert url == expected_url

    def test_get_why_why_now_tooltip_with_both_texts(self, configuration_manager) -> None:
        """
        User can get tooltip with both why and why_now texts.

        GIVEN: A user has a configuration manager with both why and why_now tooltip texts
        WHEN: They request the tooltip
        THEN: Both texts are included in the formatted tooltip
        """
        # Arrange: Set up mock return values
        configuration_manager._local_filesystem.get_seq_tooltip_text.side_effect = lambda file, key: {
            ("00_default.param", "why"): "This is why",
            ("00_default.param", "why_now"): "This is why now",
        }.get((file, key), "")

        # Act: Get tooltip
        tooltip = configuration_manager.get_why_why_now_tooltip()

        # Assert: Both texts are included
        assert "Why: This is why" in tooltip
        assert "Why now: This is why now" in tooltip
        assert tooltip.count("\n") == 1  # One newline between the two texts

    def test_get_why_why_now_tooltip_with_only_why_text(self, configuration_manager) -> None:
        """
        User can get tooltip with only why text.

        GIVEN: A user has a configuration manager with only why tooltip text
        WHEN: They request the tooltip
        THEN: Only why text is included, no why_now text
        """
        # Arrange: Set up mock return values
        configuration_manager._local_filesystem.get_seq_tooltip_text.side_effect = lambda file, key: {
            ("00_default.param", "why"): "This is why",
            ("00_default.param", "why_now"): "",
        }.get((file, key), "")

        # Act: Get tooltip
        tooltip = configuration_manager.get_why_why_now_tooltip()

        # Assert: Only why text is included
        assert "Why: This is why" in tooltip
        assert "Why now:" not in tooltip
        assert tooltip == "Why: This is why\n"  # Includes trailing newline

    def test_get_why_why_now_tooltip_with_only_why_now_text(self, configuration_manager) -> None:
        """
        User can get tooltip with only why_now text.

        GIVEN: A user has a configuration manager with only why_now tooltip text
        WHEN: They request the tooltip
        THEN: Only why_now text is included, no why text
        """
        # Arrange: Set up mock return values
        configuration_manager._local_filesystem.get_seq_tooltip_text.side_effect = lambda file, key: {
            ("00_default.param", "why"): "",
            ("00_default.param", "why_now"): "This is why now",
        }.get((file, key), "")

        # Act: Get tooltip
        tooltip = configuration_manager.get_why_why_now_tooltip()

        # Assert: Only why_now text is included
        assert "Why now: This is why now" in tooltip
        assert "Why:" not in tooltip
        assert tooltip.endswith("This is why now")  # No trailing newline

    def test_get_why_why_now_tooltip_with_no_texts(self, configuration_manager) -> None:
        """
        User can get tooltip when no tooltip texts are available.

        GIVEN: A user has a configuration manager with no tooltip texts
        WHEN: They request the tooltip
        THEN: Empty string is returned
        """
        # Arrange: Set up mock return values
        configuration_manager._local_filesystem.get_seq_tooltip_text.return_value = ""

        # Act: Get tooltip
        tooltip = configuration_manager.get_why_why_now_tooltip()

        # Assert: Empty string returned
        assert tooltip == ""

    def test_get_documentation_frame_title_with_current_file(self, configuration_manager) -> None:
        """
        User can get documentation frame title with current file.

        GIVEN: A user has a configuration manager with a current file
        WHEN: They request the documentation frame title
        THEN: Title includes the current file name
        """
        # Act: Get title
        title = configuration_manager.get_documentation_frame_title()

        # Assert: Title includes current file
        assert "00_default.param Documentation" in title

    def test_get_documentation_frame_title_without_current_file(self, mock_flight_controller, mock_local_filesystem) -> None:
        """
        User can get documentation frame title when no current file is set.

        GIVEN: A user has a configuration manager with no current file
        WHEN: They request the documentation frame title
        THEN: Generic "Documentation" title is returned
        """
        # Arrange: Create ConfigurationManager with no current file
        config_manager = ConfigurationManager("", mock_flight_controller, mock_local_filesystem)

        # Act: Get title
        title = config_manager.get_documentation_frame_title()

        # Assert: Generic title returned
        assert title == "Documentation"

    def test_parse_mandatory_level_percentage_with_valid_percentage(self, configuration_manager) -> None:
        """
        User can parse valid mandatory level percentage.

        GIVEN: A user has text with a valid percentage
        WHEN: They parse the mandatory level percentage
        THEN: Correct percentage and tooltip are returned
        """
        # Arrange: Valid percentage text
        text = "80% mandatory (20% optional)"

        # Act: Parse percentage
        percentage, tooltip = configuration_manager.parse_mandatory_level_percentage(text)

        # Assert: Correct values returned
        assert percentage == 80
        assert "80% mandatory" in tooltip
        assert "00_default.param" in tooltip

    def test_parse_mandatory_level_percentage_with_invalid_percentage(self, configuration_manager) -> None:
        """
        User handles invalid mandatory level percentage.

        GIVEN: A user has text with invalid percentage
        WHEN: They parse the mandatory level percentage
        THEN: Zero percentage and error tooltip are returned
        """
        # Arrange: Invalid percentage text
        text = "invalid percentage text"

        # Act: Parse percentage
        percentage, tooltip = configuration_manager.parse_mandatory_level_percentage(text)

        # Assert: Zero percentage and error tooltip
        assert percentage == 0
        assert "Mandatory level not available" in tooltip
        assert "00_default.param" in tooltip

    def test_parse_mandatory_level_percentage_with_out_of_range_percentage(self, configuration_manager) -> None:
        """
        User handles out-of-range mandatory level percentage.

        GIVEN: A user has text with percentage outside 0-100 range
        WHEN: They parse the mandatory level percentage
        THEN: Zero percentage and error tooltip are returned
        """
        # Arrange: Out-of-range percentage text
        text = "150% mandatory (negative optional)"

        # Act: Parse percentage
        percentage, tooltip = configuration_manager.parse_mandatory_level_percentage(text)

        # Assert: Zero percentage and error tooltip
        assert percentage == 0
        assert "Mandatory level not available" in tooltip

    def test_parse_mandatory_level_percentage_with_empty_text(self, configuration_manager) -> None:
        """
        User handles empty mandatory level text.

        GIVEN: A user has empty text
        WHEN: They parse the mandatory level percentage
        THEN: Zero percentage and error tooltip are returned
        """
        # Arrange: Empty text
        text = ""

        # Act: Parse percentage
        percentage, tooltip = configuration_manager.parse_mandatory_level_percentage(text)

        # Assert: Zero percentage and error tooltip
        assert percentage == 0
        assert "Mandatory level not available" in tooltip

    def test_parse_mandatory_level_percentage_with_no_percentage_symbol(self, configuration_manager) -> None:
        """
        User handles text without percentage symbol.

        GIVEN: A user has text without % symbol
        WHEN: They parse the mandatory level percentage
        THEN: Percentage is extracted from the beginning of the text
        """
        # Arrange: Text without % symbol
        text = "80 mandatory 20 optional"

        # Act: Parse percentage
        percentage, tooltip = configuration_manager.parse_mandatory_level_percentage(text)

        # Assert: Percentage extracted from beginning of text
        assert percentage == 80
        assert "80% mandatory" in tooltip
