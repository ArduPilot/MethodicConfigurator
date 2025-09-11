#!/usr/bin/env python3

"""
Behavior-driven tests for ArduPilot parameter dictionary data model.

This module contains comprehensive tests for the ParDict class,
focusing on user workflows and business value rather than implementation details.

SPDX-FileCopyrightText: 2024-2025 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import pytest

from ardupilot_methodic_configurator.data_model_par_dict import Par, ParDict

# pylint: disable=redefined-outer-name


@pytest.fixture
def sample_par_objects() -> ParDict:
    """Fixture providing realistic Par objects for testing."""
    return {
        "ACRO_YAW_P": Par(4.5, "Yaw P gain"),
        "PILOT_SPEED_UP": Par(250.0, "Pilot controlled climb rate"),
        "BATT_CAPACITY": Par(5000.0, "Battery capacity in mAh"),
        "GPS_TYPE": Par(1.0, "GPS type"),
        "COMPASS_ENABLE": Par(1.0, "Enable compass"),
    }


@pytest.fixture
def parameter_dict(sample_par_objects) -> ParDict:
    """Fixture providing a configured ParDict for behavior testing."""
    return ParDict(sample_par_objects)


@pytest.fixture
def empty_parameter_dict() -> ParDict:
    """Fixture providing an empty ParDict."""
    return ParDict()


@pytest.fixture
def alternate_parameter_dict() -> ParDict:
    """Fixture providing an alternate parameter dictionary for comparison testing."""
    alternate_data = {
        "ACRO_YAW_P": Par(6.0, "Modified Yaw P gain"),  # Different value
        "NEW_PARAM": Par(100.0, "New parameter"),  # New parameter
        "COMPASS_ENABLE": Par(1.0, "Enable compass"),  # Same value
    }
    return ParDict(alternate_data)


class TestParDictInitialization:
    """Test ParDict initialization workflows."""

    def test_user_can_create_empty_parameter_dictionary(self) -> None:
        """
        User can create an empty parameter dictionary for fresh configurations.

        GIVEN: A user needs to start with a clean parameter configuration
        WHEN: They create a new ParDict without initial data
        THEN: An empty dictionary should be created successfully
        """
        # Arrange & Act: Create empty parameter dictionary
        param_dict = ParDict()

        # Assert: Dictionary is empty and functional
        assert len(param_dict) == 0
        assert isinstance(param_dict, dict)
        assert isinstance(param_dict, ParDict)

    def test_user_can_create_parameter_dictionary_with_initial_data(self, sample_par_objects) -> None:
        """
        User can create a parameter dictionary with initial configuration data.

        GIVEN: A user has existing parameter data to work with
        WHEN: They create a new ParDict with initial data
        THEN: The dictionary should contain all provided parameters
        """
        # Arrange: Initial data is provided via fixture

        # Act: Create parameter dictionary with initial data
        param_dict = ParDict(sample_par_objects)

        # Assert: Dictionary contains all initial parameters
        assert len(param_dict) == 5
        assert param_dict["ACRO_YAW_P"].value == 4.5
        assert param_dict["PILOT_SPEED_UP"].comment == "Pilot controlled climb rate"
        assert "BATT_CAPACITY" in param_dict

    def test_user_can_create_parameter_dictionary_with_none_initial_data(self) -> None:
        """
        User can create a parameter dictionary when initial data is None.

        GIVEN: A user passes None as initial data
        WHEN: They create a new ParDict
        THEN: An empty dictionary should be created without errors
        """
        # Arrange & Act: Create parameter dictionary with None
        param_dict = ParDict(None)

        # Assert: Dictionary is empty and functional
        assert len(param_dict) == 0
        assert isinstance(param_dict, ParDict)


class TestParameterMergingWorkflows:
    """Test parameter merging and appending workflows."""

    def test_user_can_merge_parameters_from_another_dictionary(self, parameter_dict, alternate_parameter_dict) -> None:
        """
        User can merge parameters from another dictionary to update their configuration.

        GIVEN: A user has an existing parameter configuration
        WHEN: They append parameters from another ParDict
        THEN: Parameters should be merged with newer values replacing existing ones
        """
        # Arrange: Two parameter dictionaries with some overlapping parameters
        original_count = len(parameter_dict)

        # Act: User merges parameters from alternate dictionary
        parameter_dict.append(alternate_parameter_dict)

        # Assert: Parameters merged correctly
        assert len(parameter_dict) == original_count + 1  # One new parameter added
        assert parameter_dict["ACRO_YAW_P"].value == 6.0  # Updated value
        assert parameter_dict["NEW_PARAM"].value == 100.0  # New parameter added
        assert parameter_dict["COMPASS_ENABLE"].value == 1.0  # Unchanged parameter preserved

    def test_user_can_append_parameters_to_empty_dictionary(self, empty_parameter_dict, alternate_parameter_dict) -> None:
        """
        User can append parameters to an initially empty dictionary.

        GIVEN: A user starts with an empty parameter dictionary
        WHEN: They append parameters from another dictionary
        THEN: All parameters should be added to the empty dictionary
        """
        # Arrange: Empty dictionary and source dictionary
        source_count = len(alternate_parameter_dict)

        # Act: User appends parameters to empty dictionary
        empty_parameter_dict.append(alternate_parameter_dict)

        # Assert: All parameters copied to previously empty dictionary
        assert len(empty_parameter_dict) == source_count
        assert empty_parameter_dict["ACRO_YAW_P"].value == 6.0
        assert empty_parameter_dict["NEW_PARAM"].comment == "New parameter"

    def test_user_receives_error_when_appending_invalid_type(self, parameter_dict) -> None:
        """
        User receives clear error when trying to append incompatible data types.

        GIVEN: A user has a valid parameter dictionary
        WHEN: They try to append data that is not an ParDict
        THEN: A TypeError should be raised with a helpful message
        """
        # Arrange: Invalid data to append
        invalid_data = {"PARAM": Par(1.0)}

        # Act & Assert: User gets helpful error message
        with pytest.raises(TypeError, match="Can only append another ParDict instance"):
            parameter_dict.append(invalid_data)


class TestParameterComparisonWorkflows:  # pylint: disable=too-few-public-methods
    """Test parameter comparison and filtering workflows."""

    def test_user_can_remove_parameters_with_same_values_but_different_comments(self, parameter_dict) -> None:
        """
        User can remove parameters that have the same values but different comments.

        GIVEN: A user has FC parameters (no comments) and file parameters (with comments) with same values
        WHEN: They remove parameters with similar values using remove_if_value_is_similar
        THEN: Parameters with matching values should be removed regardless of comment differences
        """
        # Arrange: Create a dictionary with parameters that have same values but different comments
        file_params_with_comments = ParDict(
            {
                "ACRO_YAW_P": Par(4.5, "Yaw rate controller P gain"),  # Same value, different comment
                "COMPASS_ENABLE": Par(1.0, "Enable compass sensor"),  # Same value, different comment
                "NEW_PARAM": Par(999.0, "This parameter doesn't exist in original"),  # Different parameter
            }
        )

        original_count = len(parameter_dict)

        # Act: User removes parameters with similar values
        parameter_dict.remove_if_value_is_similar(file_params_with_comments)

        # Assert: Parameters with matching values were removed, regardless of comments
        assert len(parameter_dict) == original_count - 2  # Two parameters removed
        assert "ACRO_YAW_P" not in parameter_dict  # Same value, removed despite different comment
        assert "COMPASS_ENABLE" not in parameter_dict  # Same value, removed despite different comment
        assert "PILOT_SPEED_UP" in parameter_dict  # Different value, kept
        assert "BATT_CAPACITY" in parameter_dict  # Not in other dict, kept
        assert "GPS_TYPE" in parameter_dict  # Not in other dict, kept


class TestParameterDictionaryEdgeCases:  # pylint: disable=too-few-public-methods
    """Test edge cases and error conditions."""

    def test_user_can_work_with_parameters_having_none_comments(self) -> None:
        """
        User can work with parameters that have None comments without issues.

        GIVEN: A user has parameters with None comments
        WHEN: They perform operations on these parameters
        THEN: All operations should work correctly
        """
        # Arrange: Parameters with None comments
        params_with_none = {
            "PARAM_1": Par(1.0, None),
            "PARAM_2": Par(2.0, "Has comment"),
        }
        param_dict = ParDict(params_with_none)

        # Act & Assert: Operations work with None comments
        assert len(param_dict) == 2
        assert param_dict["PARAM_1"].comment is None
        assert param_dict["PARAM_2"].comment == "Has comment"
