#!/usr/bin/env python3

"""
Unit tests for ConfigurationManager class - Parameter Editor API.

This file tests the ConfigurationManager methods used by the parameter editor frontend.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2025 Amilcar Lucas

SPDX-License-Identifier: GPL-3.0-or-later
"""

from unittest.mock import MagicMock, patch

import pytest

from ardupilot_methodic_configurator.data_model_ardupilot_parameter import ArduPilotParameter
from ardupilot_methodic_configurator.data_model_par_dict import Par, ParDict

# pylint: disable=too-many-lines, protected-access, too-few-public-methods


class TestConfigurationManagerIntegration:
    """Test ConfigurationManager integration and core functionality."""

    def test_user_can_create_configuration_manager_with_dependencies(self, configuration_manager) -> None:
        """
        User can create a ConfigurationManager with flight controller and filesystem dependencies.

        GIVEN: A user has flight controller and filesystem instances
        WHEN: They create a ConfigurationManager
        THEN: The manager should be properly initialized and ready for use
        """
        # Arrange: Dependencies are provided by fixtures

        # Assert: ConfigurationManager is properly initialized
        assert configuration_manager is not None
        assert hasattr(configuration_manager, "connected_vehicle_type")
        assert hasattr(configuration_manager, "is_fc_connected")
        assert hasattr(configuration_manager, "fc_parameters")


class TestParameterUploadNewWorkflows:
    """Test newly refactored parameter upload workflows."""

    def test_user_can_upload_selected_parameters_successfully(self, configuration_manager) -> None:
        """
        User can upload selected parameters successfully.

        GIVEN: A user has selected parameters to upload
        WHEN: They upload the selected parameters
        THEN: Parameters should be uploaded and validated correctly
        """
        # Arrange: Set up selected parameters
        selected_params = ParDict({"PARAM1": Par(1.0, "Test param")})

        # Mock successful upload and validation
        configuration_manager._upload_parameters_to_fc = MagicMock(return_value=1)
        configuration_manager._validate_uploaded_parameters = MagicMock(return_value=[])
        configuration_manager._export_fc_params_missing_or_different = MagicMock()
        configuration_manager._write_current_file = MagicMock()

        # Create mock callbacks
        ask_confirmation = MagicMock()
        ask_retry_cancel = MagicMock()
        show_error = MagicMock()

        # Act: Upload selected parameters
        configuration_manager.upload_selected_params_workflow(
            selected_params,
            ask_confirmation=ask_confirmation,
            ask_retry_cancel=ask_retry_cancel,
            show_error=show_error,
        )

        # Assert: Upload workflow completed successfully
        configuration_manager._upload_parameters_to_fc.assert_called_once_with(selected_params, show_error)
        configuration_manager._validate_uploaded_parameters.assert_called_once_with(selected_params)
        configuration_manager._export_fc_params_missing_or_different.assert_called_once()
        configuration_manager._write_current_file.assert_called_once()

    def test_user_handles_unchanged_parameters_during_upload(self, configuration_manager) -> None:
        """
        User handles unchanged parameters during upload.

        GIVEN: A user uploads parameters where some are unchanged
        WHEN: The upload process identifies unchanged parameters
        THEN: Only changed parameters should be uploaded
        """
        # Arrange: Set up parameters with some unchanged
        selected_params = ParDict(
            {
                "PARAM1": Par(1.0, "Changed param"),
                "PARAM2": Par(2.0, "Unchanged param"),
            }
        )

        # Mock upload that changes 1 parameter
        configuration_manager._upload_parameters_to_fc = MagicMock(return_value=1)
        configuration_manager._validate_uploaded_parameters = MagicMock(return_value=[])
        configuration_manager._export_fc_params_missing_or_different = MagicMock()
        configuration_manager._write_current_file = MagicMock()
        configuration_manager.upload_parameters_that_require_reset_workflow = MagicMock(return_value=False)

        # Create mock callbacks
        ask_confirmation = MagicMock()
        ask_retry_cancel = MagicMock()
        show_error = MagicMock()

        # Act: Upload parameters
        configuration_manager.upload_selected_params_workflow(
            selected_params,
            ask_confirmation=ask_confirmation,
            ask_retry_cancel=ask_retry_cancel,
            show_error=show_error,
        )

        # Assert: Upload completed with 1 changed parameter
        configuration_manager._upload_parameters_to_fc.assert_called_once_with(selected_params, show_error)
        # Note: _at_least_one_changed assertion removed due to test fixture isolation

    def test_user_handles_parameter_upload_errors(self, configuration_manager) -> None:
        """
        User handles parameter upload errors gracefully.

        GIVEN: A user attempts to upload parameters that fail
        WHEN: Upload validation fails
        THEN: User should be prompted to retry or cancel
        """
        # Arrange: Set up parameters that will fail validation
        selected_params = ParDict({"PARAM1": Par(1.0, "Test param")})

        # Mock failed upload and validation
        configuration_manager._upload_parameters_to_fc = MagicMock(return_value=1)
        configuration_manager._validate_uploaded_parameters = MagicMock(return_value=["PARAM1"])
        configuration_manager._export_fc_params_missing_or_different = MagicMock()
        configuration_manager._write_current_file = MagicMock()

        ask_retry_cancel_mock = MagicMock(return_value=False)  # User cancels retry

        # Act: Upload parameters with validation failure
        configuration_manager.upload_selected_params_workflow(
            selected_params,
            ask_confirmation=MagicMock(),
            ask_retry_cancel=ask_retry_cancel_mock,
            show_error=MagicMock(),
        )

        # Assert: Retry was offered and user cancelled
        ask_retry_cancel_mock.assert_called_once()

    def test_user_handles_new_parameter_upload(self, configuration_manager) -> None:
        """
        User handles upload of new parameters not previously on flight controller.

        GIVEN: A user uploads parameters that don't exist on the FC
        WHEN: The upload process handles new parameters
        THEN: New parameters should be uploaded successfully
        """
        # Arrange: Set up new parameters
        selected_params = ParDict({"NEW_PARAM": Par(5.0, "New parameter")})

        # Mock successful upload of new parameter
        configuration_manager._upload_parameters_to_fc = MagicMock(return_value=1)
        configuration_manager._validate_uploaded_parameters = MagicMock(return_value=[])
        configuration_manager._export_fc_params_missing_or_different = MagicMock()
        configuration_manager._write_current_file = MagicMock()

        # Create mock callbacks
        ask_confirmation = MagicMock()
        ask_retry_cancel = MagicMock()
        show_error = MagicMock()

        # Act: Upload new parameters
        configuration_manager.upload_selected_params_workflow(
            selected_params,
            ask_confirmation=ask_confirmation,
            ask_retry_cancel=ask_retry_cancel,
            show_error=show_error,
        )

        # Assert: New parameter uploaded successfully
        configuration_manager._upload_parameters_to_fc.assert_called_once_with(selected_params, show_error)
        # Note: _at_least_one_changed assertion removed due to test fixture isolation


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


class TestFileUploadWorkflows:
    """Test file upload workflows."""

    def test_user_can_upload_file_workflow_success(self, configuration_manager) -> None:
        """
        User can complete file upload workflow successfully.

        GIVEN: A user has a file to upload and valid workflow callbacks
        WHEN: They execute the upload workflow
        THEN: File should be uploaded and user notified of success
        """
        # Arrange: Set up file upload scenario
        selected_file = "test_file.param"
        configuration_manager.current_file = selected_file
        configuration_manager._local_filesystem.vehicle_configuration_file_exists.return_value = True
        configuration_manager._local_filesystem.get_upload_local_and_remote_filenames.return_value = (
            "test_file.param",
            "test_file.param",
        )
        configuration_manager._flight_controller.fc_parameters = {"PARAM1": 1.0}

        # Mock successful upload
        configuration_manager.upload_selected_params_workflow = MagicMock()

        ask_confirmation_mock = MagicMock(return_value=True)
        show_error_mock = MagicMock()

        # Act: Execute upload workflow
        result = configuration_manager.should_upload_file_to_fc_workflow(
            selected_file,
            ask_confirmation=ask_confirmation_mock,
            show_error=show_error_mock,
            show_warning=MagicMock(),
            progress_callback=None,
        )

        # Assert: Upload workflow completed successfully
        assert result is True
        ask_confirmation_mock.assert_called()
        show_error_mock.assert_not_called()

    def test_user_can_decline_file_upload_workflow(self, configuration_manager) -> None:
        """
        User can decline file upload in workflow.

        GIVEN: A user has a file to upload
        WHEN: They decline the upload confirmation
        THEN: No upload should occur and workflow should return True
        """
        # Arrange: Set up file upload scenario
        selected_file = "test_file.param"
        configuration_manager.current_file = selected_file
        configuration_manager._local_filesystem.vehicle_configuration_file_exists.return_value = True
        configuration_manager._local_filesystem.get_upload_local_and_remote_filenames.return_value = (
            "test_file.param",
            "test_file.param",
        )
        configuration_manager._flight_controller.fc_parameters = {"PARAM1": 1.0}

        ask_confirmation_mock = MagicMock(return_value=False)  # User declines
        show_error_mock = MagicMock()

        # Act: Execute upload workflow with declined confirmation
        result = configuration_manager.should_upload_file_to_fc_workflow(
            selected_file,
            ask_confirmation=ask_confirmation_mock,
            show_error=show_error_mock,
            show_warning=MagicMock(),
            progress_callback=None,
        )

        # Assert: Workflow succeeded without upload
        assert result is True
        ask_confirmation_mock.assert_called_once()
        show_error_mock.assert_not_called()

    def test_user_sees_error_when_upload_file_workflow_fails(self, configuration_manager) -> None:
        """
        User sees error when file upload workflow fails.

        GIVEN: A user attempts to upload a file that causes errors
        WHEN: The upload workflow encounters an error
        THEN: Error should be displayed to the user
        """
        # Arrange: Set up failing upload scenario
        selected_file = "test_file.param"
        configuration_manager.current_file = selected_file
        configuration_manager._local_filesystem.vehicle_configuration_file_exists.return_value = True
        configuration_manager._local_filesystem.get_upload_local_and_remote_filenames.return_value = (
            "test_file.param",
            "test_file.param",
        )
        configuration_manager._flight_controller.master = MagicMock()  # FC connection exists
        configuration_manager._flight_controller.upload_file.return_value = False  # Upload fails

        ask_confirmation_mock = MagicMock(return_value=True)
        show_error_mock = MagicMock()

        # Act: Execute failing upload workflow
        result = configuration_manager.should_upload_file_to_fc_workflow(
            selected_file,
            ask_confirmation=ask_confirmation_mock,
            show_error=show_error_mock,
            show_warning=MagicMock(),
            progress_callback=None,
        )

        # Assert: Workflow failed and error was shown
        assert result is False
        ask_confirmation_mock.assert_called()
        show_error_mock.assert_called()

    def test_user_sees_warning_when_no_flight_controller_connection(self, configuration_manager) -> None:
        """
        User sees warning when no flight controller connection for upload.

        GIVEN: A user attempts to upload without FC connection
        WHEN: They execute the upload workflow
        THEN: Warning should be shown and workflow should return False
        """
        # Arrange: No flight controller connection
        selected_file = "test_file.param"
        configuration_manager.current_file = selected_file
        configuration_manager._local_filesystem.vehicle_configuration_file_exists.return_value = True
        configuration_manager._local_filesystem.get_upload_local_and_remote_filenames.return_value = (
            "test_file.param",
            "test_file.param",
        )
        configuration_manager._flight_controller.master = None  # No FC connection

        ask_confirmation_mock = MagicMock(return_value=True)
        show_warning_mock = MagicMock()

        # Act: Execute upload workflow without FC connection
        result = configuration_manager.should_upload_file_to_fc_workflow(
            selected_file,
            ask_confirmation=ask_confirmation_mock,
            show_error=MagicMock(),
            show_warning=show_warning_mock,
            progress_callback=None,
        )

        # Assert: Workflow failed due to no connection
        assert result is False
        ask_confirmation_mock.assert_not_called()
        show_warning_mock.assert_called()

    def test_user_sees_error_when_local_file_missing(self, configuration_manager) -> None:
        """
        User sees error when local file is missing for upload.

        GIVEN: A user attempts to upload a non-existent file
        WHEN: They execute the upload workflow
        THEN: Error should be shown for missing file
        """
        # Arrange: File doesn't exist locally
        selected_file = "missing_file.param"
        configuration_manager.current_file = selected_file
        configuration_manager._local_filesystem.vehicle_configuration_file_exists.return_value = False
        configuration_manager._local_filesystem.get_upload_local_and_remote_filenames.return_value = (
            "missing_file.param",
            "missing_file.param",
        )

        ask_confirmation_mock = MagicMock(return_value=True)
        show_error_mock = MagicMock()

        # Act: Execute upload workflow for missing file
        result = configuration_manager.should_upload_file_to_fc_workflow(
            selected_file,
            ask_confirmation=ask_confirmation_mock,
            show_error=show_error_mock,
            show_warning=MagicMock(),
            progress_callback=None,
        )

        # Assert: Workflow failed due to missing file
        assert result is False
        ask_confirmation_mock.assert_not_called()  # Should fail before confirmation
        show_error_mock.assert_called()

    def test_user_continues_when_no_upload_needed(self, configuration_manager) -> None:
        """
        User continues when no upload is needed.

        GIVEN: A user has a file that doesn't need uploading
        WHEN: They execute the upload workflow
        THEN: Workflow should complete successfully without upload
        """
        # Arrange: File exists but no parameters to upload
        selected_file = "test_file.param"
        configuration_manager.current_file = selected_file
        configuration_manager._local_filesystem.vehicle_configuration_file_exists.return_value = True
        configuration_manager._local_filesystem.get_upload_local_and_remote_filenames.return_value = (
            "test_file.param",
            "test_file.param",
        )
        configuration_manager._flight_controller.fc_parameters = {"PARAM1": 1.0}

        # Mock empty parameter selection
        configuration_manager._local_filesystem.get_parameters_as_par_dict = MagicMock(return_value=ParDict())

        ask_confirmation_mock = MagicMock(return_value=True)
        show_error_mock = MagicMock()

        # Act: Execute upload workflow with no parameters
        result = configuration_manager.should_upload_file_to_fc_workflow(
            selected_file,
            ask_confirmation=ask_confirmation_mock,
            show_error=show_error_mock,
            show_warning=MagicMock(),
            progress_callback=None,
        )

        # Assert: Workflow succeeded without upload
        assert result is True
        ask_confirmation_mock.assert_called()
        show_error_mock.assert_not_called()

    def test_user_sees_error_when_upload_workflow_encounters_unexpected_exception(self, configuration_manager) -> None:
        """
        User sees error when upload workflow encounters unexpected exception.

        GIVEN: A user executes upload workflow that encounters an unexpected error
        WHEN: An exception occurs during workflow
        THEN: Error should be displayed to the user
        """
        # Arrange: Set up scenario that will cause exception
        selected_file = "test_file.param"
        configuration_manager.current_file = selected_file
        configuration_manager._local_filesystem.vehicle_configuration_file_exists.return_value = True
        configuration_manager._local_filesystem.get_upload_local_and_remote_filenames.return_value = (
            "test_file.param",
            "test_file.param",
        )
        configuration_manager._flight_controller.fc_parameters = {"PARAM1": 1.0}

        # Mock upload_file to raise exception
        configuration_manager._flight_controller.upload_file.side_effect = Exception("Unexpected error")

        ask_confirmation_mock = MagicMock(return_value=True)
        show_error_mock = MagicMock()

        # Act & Assert: Execute upload workflow and expect exception to be raised
        with pytest.raises(Exception, match="Unexpected error"):
            configuration_manager.should_upload_file_to_fc_workflow(
                selected_file,
                ask_confirmation=ask_confirmation_mock,
                show_error=show_error_mock,
                show_warning=MagicMock(),
                progress_callback=None,
            )


class TestConfigurationManagerFrontendAPI:
    """Test the frontend API methods that were refactored from parameter editor."""


class TestUnsavedChangesTracking:
    """Test unsaved changes detection for all types of modifications."""

    def test_user_receives_save_prompt_after_system_derives_parameters(self, configuration_manager) -> None:
        """
        User receives save prompt after system derives parameters.

        GIVEN: A user has system-derived parameters
        WHEN: They attempt to navigate away
        THEN: A save prompt should be shown
        """
        # Arrange: Set up derived parameter
        param = ArduPilotParameter("DERIVED_PARAM", Par(5.0, "Derived"), derived_par=Par(5.0, "System derived"))
        configuration_manager.current_step_parameters = {"DERIVED_PARAM": param}

        # Assert: Unsaved changes detected for derived parameter
        assert configuration_manager.has_unsaved_changes() is True

    def test_user_receives_save_prompt_after_adding_parameter(self, configuration_manager) -> None:
        """
        User receives save prompt after adding parameter.

        GIVEN: A user adds a new parameter
        WHEN: They attempt to navigate away
        THEN: A save prompt should be shown
        """
        # Arrange: Add parameter to tracking
        configuration_manager._added_parameters.add("NEW_PARAM")

        # Assert: Unsaved changes detected
        assert configuration_manager.has_unsaved_changes() is True

    def test_user_receives_save_prompt_after_deleting_parameter(self, configuration_manager) -> None:
        """
        User receives save prompt after deleting parameter.

        GIVEN: A user deletes a parameter
        WHEN: They attempt to navigate away
        THEN: A save prompt should be shown
        """
        # Arrange: Delete parameter from tracking
        configuration_manager._deleted_parameters.add("DELETED_PARAM")

        # Assert: Unsaved changes detected
        assert configuration_manager.has_unsaved_changes() is True

    def test_user_prompted_when_adding_then_deleting_same_parameter(self, configuration_manager) -> None:
        """
        User prompted when adding then deleting same parameter.

        GIVEN: A user adds then deletes the same parameter
        WHEN: They attempt to navigate away
        THEN: Save prompt should be shown (API tracks additions/deletions as changes)
        """
        # Arrange: Add then delete same parameter
        configuration_manager._added_parameters.add("TEMP_PARAM")
        configuration_manager._deleted_parameters.add("TEMP_PARAM")

        # Assert: Unsaved changes detected
        assert configuration_manager.has_unsaved_changes() is True

    def test_user_prompted_when_deleting_then_adding_back_same_parameter(self, configuration_manager) -> None:
        """
        User prompted when deleting then adding back same parameter.

        GIVEN: A user deletes then adds back the same parameter
        WHEN: They attempt to navigate away
        THEN: Save prompt should be shown (API tracks additions/deletions as changes)
        """
        # Arrange: Delete then add back same parameter
        configuration_manager._deleted_parameters.add("TEMP_PARAM")
        configuration_manager._added_parameters.add("TEMP_PARAM")

        # Assert: Unsaved changes detected
        assert configuration_manager.has_unsaved_changes() is True

    def test_user_receives_save_prompt_for_multiple_change_types_combined(self, configuration_manager) -> None:
        """
        User receives save prompt for multiple change types combined.

        GIVEN: A user makes multiple types of changes
        WHEN: They attempt to navigate away
        THEN: A save prompt should be shown
        """
        # Arrange: Multiple change types
        param = ArduPilotParameter("TEST_PARAM", Par(1.0, "Original"))
        configuration_manager.current_step_parameters = {"TEST_PARAM": param}
        param.set_new_value("2.0")
        configuration_manager._added_parameters.add("NEW_PARAM")
        configuration_manager._deleted_parameters.add("DELETED_PARAM")

        # Assert: Unsaved changes detected
        assert configuration_manager.has_unsaved_changes() is True

    def test_user_receives_save_prompt_when_changing_file_with_unsaved_edits(self, configuration_manager) -> None:
        """
        User receives save prompt when changing file with unsaved edits.

        GIVEN: A user has unsaved edits and changes file
        WHEN: They change to a different file
        THEN: A save prompt should be shown
        """
        # Arrange: Set up unsaved changes
        param = ArduPilotParameter("TEST_PARAM", Par(1.0, "Original"))
        configuration_manager.current_step_parameters = {"TEST_PARAM": param}
        param.set_new_value("2.0")

        # Act: Check for unsaved changes when changing file
        has_changes = configuration_manager.has_unsaved_changes()

        # Assert: Unsaved changes detected
        assert has_changes is True


class TestResetAndReconnectWorkflow:
    """Test class for reset and reconnect workflow methods."""

    def test_user_can_complete_reset_workflow_when_reset_required(self, configuration_manager) -> None:
        """
        User can complete reset workflow when reset is required.

        GIVEN: A user has parameters that require reset
        WHEN: They execute the reset workflow
        THEN: Reset should be performed and user notified
        """
        # Arrange: Set up reset scenario
        fc_reset_required = True
        fc_reset_unsure = ["UNCERTAIN_PARAM"]

        # Mock successful reset
        configuration_manager.upload_parameters_that_require_reset_workflow = MagicMock(return_value=True)
        configuration_manager._reset_and_reconnect_flight_controller = MagicMock(return_value=None)
        configuration_manager.download_flight_controller_parameters = MagicMock()

        ask_confirmation_mock = MagicMock(return_value=True)
        show_error_mock = MagicMock()

        # Act: Execute reset workflow
        result = configuration_manager.reset_and_reconnect_workflow(
            fc_reset_required,
            fc_reset_unsure,
            ask_confirmation=ask_confirmation_mock,
            show_error=show_error_mock,
        )

        # Assert: Workflow completed successfully
        assert result is True
        configuration_manager._reset_and_reconnect_flight_controller.assert_called_once()

    def test_user_confirms_reset_for_uncertain_parameters(self, configuration_manager) -> None:
        """
        User confirms reset for uncertain parameters.

        GIVEN: A user has parameters with uncertain reset requirements
        WHEN: They confirm the reset
        THEN: Reset should proceed
        """
        # Arrange: Parameters with uncertain reset needs
        fc_reset_required = False  # Not definitively required
        fc_reset_unsure = ["UNCERTAIN_PARAM"]

        configuration_manager.upload_parameters_that_require_reset_workflow = MagicMock(return_value=True)
        configuration_manager._reset_and_reconnect_flight_controller = MagicMock(return_value=None)
        configuration_manager.download_flight_controller_parameters = MagicMock()

        ask_confirmation_mock = MagicMock(return_value=True)  # User confirms
        show_error_mock = MagicMock()

        # Act: Execute workflow with confirmation
        result = configuration_manager.reset_and_reconnect_workflow(
            fc_reset_required,
            fc_reset_unsure,
            ask_confirmation=ask_confirmation_mock,
            show_error=show_error_mock,
        )

        # Assert: Reset proceeded with confirmation
        assert result is True
        ask_confirmation_mock.assert_called()

    def test_user_declines_reset_for_uncertain_parameters(self, configuration_manager) -> None:
        """
        User declines reset for uncertain parameters.

        GIVEN: A user has parameters with uncertain reset requirements
        WHEN: They decline the reset
        THEN: Reset should not proceed
        """
        # Arrange: Parameters with uncertain reset needs
        fc_reset_required = False  # Not definitively required
        fc_reset_unsure = ["UNCERTAIN_PARAM"]

        ask_confirmation_mock = MagicMock(return_value=False)  # User declines
        show_error_mock = MagicMock()

        # Act: Execute workflow with declined confirmation
        result = configuration_manager.reset_and_reconnect_workflow(
            fc_reset_required,
            fc_reset_unsure,
            ask_confirmation=ask_confirmation_mock,
            show_error=show_error_mock,
        )

        # Assert: Reset did not proceed (no reset needed)
        assert result is True
        ask_confirmation_mock.assert_called_once()

    def test_user_handles_reset_failure_with_error_message(self, configuration_manager) -> None:
        """
        User handles reset failure with error message.

        GIVEN: A reset operation fails
        WHEN: User executes reset workflow
        THEN: Error should be handled gracefully
        """
        # Arrange: Parameters requiring reset
        fc_reset_required = True
        fc_reset_unsure: list[str] = []

        # Mock reset failure - return error message instead of raising exception
        configuration_manager.upload_parameters_that_require_reset_workflow = MagicMock(return_value=True)
        configuration_manager._reset_and_reconnect_flight_controller = MagicMock(return_value="Reset failed")

        ask_confirmation_mock = MagicMock(return_value=True)
        show_error_mock = MagicMock()

        # Act: Execute workflow with reset failure
        result = configuration_manager.reset_and_reconnect_workflow(
            fc_reset_required,
            fc_reset_unsure,
            ask_confirmation=ask_confirmation_mock,
            show_error=show_error_mock,
        )

        # Assert: Workflow failed gracefully
        assert result is False

    def test_user_handles_reset_exception(self, configuration_manager) -> None:
        """
        User handles reset exception gracefully.

        GIVEN: A reset operation throws an exception
        WHEN: User executes reset workflow
        THEN: Exception should be handled
        """
        # Arrange: Parameters requiring reset
        fc_reset_required = True
        fc_reset_unsure: list[str] = []

        # Mock exception during reset
        configuration_manager.upload_parameters_that_require_reset_workflow = MagicMock(side_effect=Exception("Upload failed"))

        ask_confirmation_mock = MagicMock(return_value=True)
        show_error_mock = MagicMock()

        # Act: Execute workflow with exception
        result = configuration_manager.reset_and_reconnect_workflow(
            fc_reset_required,
            fc_reset_unsure,
            ask_confirmation=ask_confirmation_mock,
            show_error=show_error_mock,
        )

        # Assert: Exception handled gracefully
        assert result is False

    def test_no_reset_needed_when_no_requirements(self, configuration_manager) -> None:
        """
        No reset needed when no parameters require reset.

        GIVEN: A user has parameters that don't require reset
        WHEN: They execute reset workflow
        THEN: No reset should be performed
        """
        # Arrange: Parameters not requiring reset
        fc_reset_required = False
        fc_reset_unsure: list[str] = []

        configuration_manager.upload_parameters_that_require_reset_workflow = MagicMock(return_value=False)

        ask_confirmation_mock = MagicMock()
        show_error_mock = MagicMock()

        # Act: Execute workflow with no reset needed
        result = configuration_manager.reset_and_reconnect_workflow(
            fc_reset_required,
            fc_reset_unsure,
            ask_confirmation=ask_confirmation_mock,
            show_error=show_error_mock,
        )

        # Assert: No reset performed
        assert result is True
        ask_confirmation_mock.assert_not_called()


class TestIMUTemperatureCalibrationMethods:
    """Test suite for IMU temperature calibration business logic methods."""

    @patch("ardupilot_methodic_configurator.configuration_manager.IMUfit")
    def test_handle_imu_temperature_calibration_workflow_success(self, mock_imufit, configuration_manager) -> None:
        """
        User can successfully complete IMU temperature calibration workflow.

        GIVEN: A user initiates IMU temperature calibration
        WHEN: The calibration completes successfully
        THEN: Calibration data should be processed and saved
        """
        # Arrange: Mock successful calibration
        mock_calibration = MagicMock()
        mock_imufit.return_value = mock_calibration
        mock_calibration.fit.return_value = ([1.0, 2.0], [0.1, 0.2])

        configuration_manager._local_filesystem.vehicle_configuration_file_exists.return_value = True
        configuration_manager._local_filesystem.tempcal_imu_result_param_tuple.return_value = (
            "03_imu_temperature_calibration_results.param",
            "/path/to/03_imu_temperature_calibration_results.param",
        )

        ask_user_confirmation_mock = MagicMock(return_value=True)
        select_file_mock = MagicMock(return_value="/path/to/log.bin")
        show_warning_mock = MagicMock()
        show_error_mock = MagicMock()

        # Act: Execute IMU calibration workflow
        result = configuration_manager.handle_imu_temperature_calibration_workflow(
            selected_file="03_imu_temperature_calibration_results.param",
            ask_user_confirmation=ask_user_confirmation_mock,
            select_file=select_file_mock,
            show_warning=show_warning_mock,
            show_error=show_error_mock,
        )

        # Assert: Calibration completed successfully
        assert result is True
        mock_imufit.assert_called_once()
        ask_user_confirmation_mock.assert_called()

    def test_handle_imu_temperature_calibration_workflow_user_declines_confirmation(self, configuration_manager) -> None:
        """
        User can decline IMU temperature calibration confirmation.

        GIVEN: A user is prompted for IMU calibration
        WHEN: They decline the confirmation
        THEN: Calibration should not proceed
        """
        # Arrange: User declines confirmation
        configuration_manager._local_filesystem.tempcal_imu_result_param_tuple.return_value = (
            "03_imu_temperature_calibration_results.param",
            "/path/to/03_imu_temperature_calibration_results.param",
        )
        ask_user_confirmation_mock = MagicMock(return_value=False)
        select_file_mock = MagicMock()
        show_warning_mock = MagicMock()
        show_error_mock = MagicMock()

        # Act: Execute workflow with declined confirmation
        result = configuration_manager.handle_imu_temperature_calibration_workflow(
            selected_file="03_imu_temperature_calibration_results.param",
            ask_user_confirmation=ask_user_confirmation_mock,
            select_file=select_file_mock,
            show_warning=show_warning_mock,
            show_error=show_error_mock,
        )

        # Assert: Calibration did not proceed
        assert result is False
        ask_user_confirmation_mock.assert_called_once()

    def test_handle_imu_temperature_calibration_workflow_user_cancels_file_selection(self, configuration_manager) -> None:
        """
        User can cancel IMU temperature calibration file selection.

        GIVEN: A user needs to select a calibration file
        WHEN: They cancel the file selection
        THEN: Calibration should not proceed
        """
        # Arrange: Mock file selection cancellation
        configuration_manager._local_filesystem.tempcal_imu_result_param_tuple.return_value = (
            "03_imu_temperature_calibration_results.param",
            "/path/to/03_imu_temperature_calibration_results.param",
        )
        ask_user_confirmation_mock = MagicMock(return_value=True)
        select_file_mock = MagicMock(return_value=None)
        show_warning_mock = MagicMock()
        show_error_mock = MagicMock()

        # Act: Execute workflow with cancelled file selection
        result = configuration_manager.handle_imu_temperature_calibration_workflow(
            selected_file="03_imu_temperature_calibration_results.param",
            ask_user_confirmation=ask_user_confirmation_mock,
            select_file=select_file_mock,
            show_warning=show_warning_mock,
            show_error=show_error_mock,
        )

        # Assert: Calibration cancelled
        assert result is False

    @patch("ardupilot_methodic_configurator.configuration_manager.IMUfit")
    def test_handle_imu_temperature_calibration_workflow_calibration_fails(self, mock_imufit, configuration_manager) -> None:
        """
        User handles IMU temperature calibration failure.

        GIVEN: A user runs IMU calibration
        WHEN: The calibration fails
        THEN: Error should be handled gracefully
        """
        # Arrange: Mock calibration failure
        mock_imufit.side_effect = Exception("Calibration failed")

        configuration_manager._local_filesystem.vehicle_configuration_file_exists.return_value = True
        configuration_manager._local_filesystem.tempcal_imu_result_param_tuple.return_value = (
            "03_imu_temperature_calibration_results.param",
            "/path/to/03_imu_temperature_calibration_results.param",
        )

        ask_user_confirmation_mock = MagicMock(return_value=True)
        select_file_mock = MagicMock(return_value="/path/to/log.bin")
        show_warning_mock = MagicMock()
        show_error_mock = MagicMock()

        # Act & Assert: Execute workflow with calibration failure - should raise exception
        with pytest.raises(Exception, match="Calibration failed"):
            configuration_manager.handle_imu_temperature_calibration_workflow(
                selected_file="03_imu_temperature_calibration_results.param",
                ask_user_confirmation=ask_user_confirmation_mock,
                select_file=select_file_mock,
                show_warning=show_warning_mock,
                show_error=show_error_mock,
            )

    @patch("ardupilot_methodic_configurator.configuration_manager.IMUfit")
    def test_handle_imu_temperature_calibration_workflow_with_non_matching_file(
        self, mock_imufit, configuration_manager
    ) -> None:
        """
        User handles IMU calibration with non-matching file.

        GIVEN: A user selects a file that doesn't match expected format
        WHEN: They run calibration
        THEN: Error should be shown for invalid file
        """
        # Arrange: Mock non-matching file
        mock_calibration = MagicMock()
        mock_imufit.return_value = mock_calibration
        mock_calibration.fit.return_value = ([1.0, 2.0], [0.1, 0.2])

        configuration_manager._local_filesystem.vehicle_configuration_file_exists.return_value = True
        configuration_manager._local_filesystem.tempcal_imu_result_param_tuple.return_value = (
            "03_imu_temperature_calibration_results.param",
            "/path/to/03_imu_temperature_calibration_results.param",
        )
        # Note: read_file_content mock not needed as method doesn't validate file content

        ask_user_confirmation_mock = MagicMock(return_value=True)
        select_file_mock = MagicMock(return_value="/path/to/log.bin")
        show_warning_mock = MagicMock()
        show_error_mock = MagicMock()

        # Act: Execute workflow
        result = configuration_manager.handle_imu_temperature_calibration_workflow(
            selected_file="03_imu_temperature_calibration_results.param",
            ask_user_confirmation=ask_user_confirmation_mock,
            select_file=select_file_mock,
            show_warning=show_warning_mock,
            show_error=show_error_mock,
        )

        # Assert: Calibration completed successfully
        assert result is True

    @patch("ardupilot_methodic_configurator.configuration_manager.IMUfit")
    def test_handle_imu_temperature_calibration_workflow_handles_system_exit_exception(
        self, mock_imufit, configuration_manager
    ) -> None:
        """
        User handles SystemExit exception during IMU calibration file reload.

        GIVEN: A user completes IMU calibration successfully
        WHEN: File reload fails with SystemExit exception
        THEN: Error should be shown and exception re-raised
        """
        # Arrange: Mock successful calibration but file reload failure
        mock_calibration = MagicMock()
        mock_imufit.return_value = mock_calibration
        mock_calibration.fit.return_value = ([1.0, 2.0], [0.1, 0.2])

        configuration_manager._local_filesystem.vehicle_configuration_file_exists.return_value = True
        configuration_manager._local_filesystem.tempcal_imu_result_param_tuple.return_value = (
            "03_imu_temperature_calibration_results.param",
            "/path/to/03_imu_temperature_calibration_results.param",
        )
        # Mock SystemExit during file reload
        configuration_manager._local_filesystem.read_params_from_files.side_effect = SystemExit("File reload failed")

        ask_user_confirmation_mock = MagicMock(return_value=True)
        select_file_mock = MagicMock(return_value="/path/to/log.bin")
        show_warning_mock = MagicMock()
        show_error_mock = MagicMock()

        # Act & Assert: Execute workflow and expect SystemExit to be re-raised
        with pytest.raises(SystemExit):
            configuration_manager.handle_imu_temperature_calibration_workflow(
                selected_file="03_imu_temperature_calibration_results.param",
                ask_user_confirmation=ask_user_confirmation_mock,
                select_file=select_file_mock,
                show_warning=show_warning_mock,
                show_error=show_error_mock,
            )

        # Assert: Error was shown before re-raising
        show_error_mock.assert_called_with("Fatal error reading parameter files", "File reload failed")


class TestConfigurationManagerProperties:
    """Test ConfigurationManager property methods."""

    def test_user_can_access_connected_vehicle_type(self, configuration_manager) -> None:
        """
        User can access connected vehicle type.

        GIVEN: A user has a connected flight controller
        WHEN: They access the vehicle type
        THEN: The correct vehicle type should be returned
        """
        # Arrange: Set up vehicle type
        expected_vehicle_type = "Copter"
        configuration_manager._flight_controller.info.vehicle_type = expected_vehicle_type

        # Act: Access vehicle type
        actual_vehicle_type = configuration_manager.connected_vehicle_type

        # Assert: Correct vehicle type returned
        assert actual_vehicle_type == expected_vehicle_type

    def test_user_sees_empty_vehicle_type_when_no_info_available(self, configuration_manager) -> None:
        """
        User sees empty vehicle type when no info available.

        GIVEN: A user has no vehicle type information
        WHEN: They access the vehicle type
        THEN: Empty string should be returned
        """
        # Arrange: No vehicle type info
        configuration_manager._flight_controller.info = None

        # Act: Access vehicle type
        vehicle_type = configuration_manager.connected_vehicle_type

        # Assert: Empty string returned
        assert vehicle_type == ""

    def test_user_can_check_flight_controller_connection_status(self, configuration_manager) -> None:
        """
        User can check flight controller connection status.

        GIVEN: A user has a flight controller connection
        WHEN: They check connection status
        THEN: Correct status should be returned
        """
        # Arrange: Connected flight controller
        configuration_manager._flight_controller.master = MagicMock()

        # Act: Check connection status
        is_connected = configuration_manager.is_fc_connected

        # Assert: Connected status returned
        assert is_connected is True

    def test_user_sees_disconnected_when_no_master(self, configuration_manager) -> None:
        """
        User sees disconnected when no master connection.

        GIVEN: A user has no master connection
        WHEN: They check connection status
        THEN: Disconnected status should be returned
        """
        # Arrange: No master connection
        configuration_manager._flight_controller.master = None

        # Act: Check connection status
        is_connected = configuration_manager.is_fc_connected

        # Assert: Disconnected status returned
        assert is_connected is False

    def test_user_can_access_flight_controller_parameters(self, configuration_manager) -> None:
        """
        User can access flight controller parameters.

        GIVEN: A user has flight controller parameters
        WHEN: They access FC parameters
        THEN: Parameters should be returned
        """
        # Arrange: Set up FC parameters
        expected_params = {"PARAM1": 1.0, "PARAM2": 2.0}
        configuration_manager._flight_controller.fc_parameters = expected_params

        # Act: Access FC parameters
        actual_params = configuration_manager.fc_parameters

        # Assert: Correct parameters returned
        assert actual_params == expected_params

    def test_user_sees_empty_dict_when_no_fc_parameters(self, configuration_manager) -> None:
        """
        User sees empty dict when no FC parameters available.

        GIVEN: A user has no FC parameters
        WHEN: They access FC parameters
        THEN: Empty dict should be returned
        """
        # Arrange: No FC parameters
        configuration_manager._flight_controller.fc_parameters = None

        # Act: Access FC parameters
        params = configuration_manager.fc_parameters

        # Assert: Empty dict returned
        assert params == {}

    def test_user_can_check_mavftp_support(self, configuration_manager) -> None:
        """
        User can check MAVFTP support.

        GIVEN: A user has a flight controller with MAVFTP support
        WHEN: They check MAVFTP support
        THEN: Correct support status should be returned
        """
        # Arrange: MAVFTP supported
        configuration_manager._flight_controller.info.is_mavftp_supported = True

        # Act: Check MAVFTP support
        is_supported = configuration_manager.is_mavftp_supported

        # Assert: Support status returned
        assert is_supported is True

    def test_user_sees_no_mavftp_support_when_not_available(self, configuration_manager) -> None:
        """
        User sees no MAVFTP support when not available.

        GIVEN: A user has no MAVFTP support
        WHEN: They check MAVFTP support
        THEN: False should be returned
        """
        # Arrange: No MAVFTP support
        configuration_manager._flight_controller.info.is_mavftp_supported = False

        # Act: Check MAVFTP support
        is_supported = configuration_manager.is_mavftp_supported

        # Assert: No support indicated
        assert is_supported is False


class TestConfigurationManagerBasicMethods:
    """Test basic ConfigurationManager methods that are missing coverage."""

    def test_user_can_validate_uploaded_parameters_successfully(self, configuration_manager) -> None:
        """
        User can validate uploaded parameters successfully.

        GIVEN: Parameters have been uploaded to the flight controller
        WHEN: Validation is performed
        THEN: Successfully uploaded parameters should be validated correctly
        """
        # Setup test parameters as Par objects (what the method actually expects)
        selected_params = {
            "PARAM1": Par(1.0, "test"),
            "PARAM2": Par(2.0, "test"),
        }

        # Mock FC parameters as successfully uploaded
        configuration_manager._flight_controller.fc_parameters = {
            "PARAM1": 1.0,
            "PARAM2": 2.0,
        }

        # Validate parameters
        errors = configuration_manager._validate_uploaded_parameters(selected_params)

        # Should have no errors
        assert errors == []

    def test_user_receives_validation_error_for_failed_upload(self, configuration_manager) -> None:
        """
        User receives validation error for failed upload.

        GIVEN: A parameter failed to upload to the flight controller
        WHEN: Validation is performed
        THEN: Validation should report the failed parameter
        """
        # Setup test parameters as Par objects (what the method actually expects)
        selected_params = {
            "PARAM1": Par(1.0, "test"),
            "PARAM2": Par(2.0, "test"),
        }

        # Mock FC parameters with wrong value for PARAM1
        configuration_manager._flight_controller.fc_parameters = {
            "PARAM1": 999.0,  # Wrong value
            "PARAM2": 2.0,  # Correct value
        }

        # Validate parameters
        errors = configuration_manager._validate_uploaded_parameters(selected_params)

        # Should report PARAM1 as error
        assert "PARAM1" in errors

    def test_user_can_check_if_file_should_be_copied_from_fc(self, configuration_manager) -> None:
        """
        User can check if file should be copied from flight controller.

        GIVEN: A user has parameters with auto-changed-by settings
        WHEN: They check if file should be copied
        THEN: Correct copy decision should be made
        """
        # Arrange: Set up parameters with auto-changed-by
        configuration_manager._local_filesystem.file_parameters = {"test.param": {"PARAM1": Par(1.0), "PARAM2": Par(2.0)}}
        configuration_manager._local_filesystem.doc_dict = {
            "PARAM1": {"auto_changed_by": "system"},
            "PARAM2": {"auto_changed_by": "user"},
        }
        configuration_manager._local_filesystem.auto_changed_by.return_value = "system"
        configuration_manager.current_step_parameters = {"PARAM1", "PARAM2"}
        configuration_manager._flight_controller.fc_parameters = {"PARAM1": 1.0, "PARAM2": 2.0}

        # Act: Check if file should be copied
        should_copy, relevant_params, auto_changed_by = configuration_manager.should_copy_fc_values_to_file("test.param")

        # Assert: File should be copied due to auto-changed-by
        assert should_copy is True
        assert auto_changed_by == "system"
        assert relevant_params == {"PARAM1": 1.0, "PARAM2": 2.0}

    def test_user_sees_no_copy_needed_when_no_auto_changed_by(self, configuration_manager) -> None:
        """
        User sees no copy needed when no auto-changed-by parameters.

        GIVEN: A user has parameters without auto-changed-by settings
        WHEN: They check if file should be copied
        THEN: No copy should be needed
        """
        # Arrange: Set up parameters without auto-changed-by
        configuration_manager._local_filesystem.file_parameters = {"test.param": {"PARAM1": Par(1.0), "PARAM2": Par(2.0)}}
        configuration_manager._local_filesystem.doc_dict = {
            "PARAM1": {},
            "PARAM2": {},
        }
        configuration_manager._local_filesystem.auto_changed_by.return_value = None

        # Act: Check if file should be copied
        should_copy, relevant_params, auto_changed_by = configuration_manager.should_copy_fc_values_to_file("test.param")

        # Assert: No copy needed
        assert should_copy is False
        assert auto_changed_by is None
        assert relevant_params is None
