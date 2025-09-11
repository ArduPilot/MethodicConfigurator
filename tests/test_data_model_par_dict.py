"""
Behavior-driven tests for ArduPilot parameter dictionary data model.

This module contains comprehensive tests for the ParDict class,
focusing on user workflows and business value rather than implementation details.

SPDX-FileCopyrightText: 2024-2025 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import pytest

from ardupilot_methodic_configurator.annotate_params import Par
from ardupilot_methodic_configurator.data_model_par_dict import ParDict


@pytest.fixture
def sample_par_objects() -> dict[str, Par]:
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


class TestParameterComparisonWorkflows:
    """Test parameter comparison and filtering workflows."""

    def test_user_can_remove_duplicate_parameters(self, parameter_dict, alternate_parameter_dict) -> None:
        """
        User can remove parameters that have identical values in another dictionary.

        GIVEN: A user has two parameter dictionaries with some identical parameters
        WHEN: They remove similar parameters from their main dictionary
        THEN: Only parameters with different values should remain
        """
        # Arrange: Dictionaries with one identical parameter (COMPASS_ENABLE)
        original_count = len(parameter_dict)

        # Act: User removes similar parameters
        parameter_dict.remove_if_similar(alternate_parameter_dict)

        # Assert: Only identical parameter was removed
        assert len(parameter_dict) == original_count - 1
        assert "COMPASS_ENABLE" not in parameter_dict  # Identical parameter removed
        assert "ACRO_YAW_P" in parameter_dict  # Different value parameter kept
        assert "PILOT_SPEED_UP" in parameter_dict  # Parameter not in other dict kept

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

    def test_user_can_identify_different_parameters(self, parameter_dict, alternate_parameter_dict) -> None:
        """
        User can identify parameters that differ between two dictionaries.

        GIVEN: A user needs to compare two parameter configurations
        WHEN: They get different parameters between dictionaries
        THEN: A new dictionary containing only differing parameters should be returned
        """
        # Arrange: Two dictionaries with known differences

        # Act: User identifies different parameters
        different_params = parameter_dict.get_different_parameters(alternate_parameter_dict)

        # Assert: Only different and unique parameters returned
        assert len(different_params) == 4  # All except COMPASS_ENABLE
        assert "ACRO_YAW_P" in different_params  # Different value
        assert "PILOT_SPEED_UP" in different_params  # Only in original
        assert "BATT_CAPACITY" in different_params  # Only in original
        assert "GPS_TYPE" in different_params  # Only in original
        assert "COMPASS_ENABLE" not in different_params  # Identical value
        assert "NEW_PARAM" not in different_params  # Not in original

    def test_user_can_identify_common_parameters(self, parameter_dict, alternate_parameter_dict) -> None:
        """
        User can identify parameters that are identical between two dictionaries.

        GIVEN: A user needs to find shared configuration between two setups
        WHEN: They get common parameters between dictionaries
        THEN: A new dictionary containing only identical parameters should be returned
        """
        # Arrange: Two dictionaries with one known common parameter

        # Act: User identifies common parameters
        common_params = parameter_dict.get_common_parameters(alternate_parameter_dict)

        # Assert: Only identical parameters returned
        assert len(common_params) == 1
        assert "COMPASS_ENABLE" in common_params
        assert common_params["COMPASS_ENABLE"].value == 1.0

    def test_user_receives_error_when_comparing_invalid_type(self, parameter_dict) -> None:
        """
        User receives clear error when comparing with incompatible data types.

        GIVEN: A user has a valid parameter dictionary
        WHEN: They try to compare with data that is not an ParDict
        THEN: A TypeError should be raised with a helpful message
        """
        # Arrange: Invalid data for comparison
        invalid_data = {"PARAM": Par(1.0)}

        # Act & Assert: User gets helpful error for each comparison method
        with pytest.raises(TypeError, match="Can only compare with another ParDict instance"):
            parameter_dict.remove_if_similar(invalid_data)

        with pytest.raises(TypeError, match="Can only compare with another ParDict instance"):
            parameter_dict.get_different_parameters(invalid_data)

        with pytest.raises(TypeError, match="Can only compare with another ParDict instance"):
            parameter_dict.get_common_parameters(invalid_data)


class TestParameterFilteringWorkflows:
    """Test parameter filtering and selection workflows."""

    def test_user_can_filter_parameters_by_prefix(self, parameter_dict) -> None:
        """
        User can filter parameters by name prefix to focus on specific subsystems.

        GIVEN: A user has a parameter dictionary with various parameter types
        WHEN: They filter parameters by a specific prefix
        THEN: Only parameters starting with that prefix should be returned
        """
        # Arrange: Dictionary with parameters having different prefixes

        # Act: User filters by "ACRO" prefix
        acro_params = parameter_dict.filter_by_prefix("ACRO")

        # Assert: Only ACRO parameters returned
        assert len(acro_params) == 1
        assert "ACRO_YAW_P" in acro_params
        assert acro_params["ACRO_YAW_P"].value == 4.5

        # Act: User filters by "BATT" prefix
        batt_params = parameter_dict.filter_by_prefix("BATT")

        # Assert: Only BATT parameters returned
        assert len(batt_params) == 1
        assert "BATT_CAPACITY" in batt_params

    def test_user_gets_empty_result_when_prefix_not_found(self, parameter_dict) -> None:
        """
        User gets empty result when filtering with non-existent prefix.

        GIVEN: A user has a parameter dictionary
        WHEN: They filter by a prefix that doesn't match any parameters
        THEN: An empty dictionary should be returned
        """
        # Arrange: Known parameter dictionary

        # Act: User filters by non-existent prefix
        result = parameter_dict.filter_by_prefix("NONEXISTENT")

        # Assert: Empty result returned
        assert len(result) == 0
        assert isinstance(result, ParDict)


class TestParameterDictionaryUtilities:
    """Test utility methods and helper functionality."""

    def test_user_can_get_parameter_count(self, parameter_dict, empty_parameter_dict) -> None:
        """
        User can get the total number of parameters in their configuration.

        GIVEN: A user has parameter dictionaries of various sizes
        WHEN: They check the parameter count
        THEN: The correct number of parameters should be returned
        """
        # Arrange: Dictionaries with known sizes

        # Act & Assert: Count matches expected values
        assert parameter_dict.get_parameter_count() == 5
        assert empty_parameter_dict.get_parameter_count() == 0

    def test_user_can_create_copy_of_parameter_dictionary(self, parameter_dict) -> None:
        """
        User can create an independent copy of their parameter configuration.

        GIVEN: A user has a parameter dictionary they want to preserve
        WHEN: They create a copy of the dictionary
        THEN: An independent copy with identical content should be created
        """
        # Arrange: Original parameter dictionary

        # Act: User creates a copy
        copied_dict = parameter_dict.copy()

        # Assert: Copy is independent but identical
        assert copied_dict is not parameter_dict  # Different objects
        assert len(copied_dict) == len(parameter_dict)
        assert copied_dict["ACRO_YAW_P"].value == parameter_dict["ACRO_YAW_P"].value

        # Modify copy to verify independence
        copied_dict["NEW_PARAM"] = Par(999.0, "Test parameter")
        assert "NEW_PARAM" not in parameter_dict  # Original unchanged

    def test_user_sees_informative_string_representation(self, parameter_dict, empty_parameter_dict) -> None:
        """
        User sees helpful information when viewing parameter dictionary as string.

        GIVEN: A user has parameter dictionaries of various states
        WHEN: They view the string representation
        THEN: Informative descriptions should be displayed
        """
        # Arrange: Dictionaries in different states

        # Act & Assert: String representations are informative
        param_repr = repr(parameter_dict)
        param_str = str(parameter_dict)
        empty_str = str(empty_parameter_dict)

        assert "ParDict" in param_repr
        assert "5 parameters" in param_repr
        assert "5 parameters" in param_str
        assert "ACRO_YAW_P" in param_str  # Shows parameter names
        assert "empty" in empty_str

    def test_user_sees_truncated_display_for_large_dictionaries(self) -> None:
        """
        User sees manageable display even for large parameter dictionaries.

        GIVEN: A user has a large parameter dictionary
        WHEN: They view the string representation
        THEN: The display should be truncated for readability
        """
        # Arrange: Create large parameter dictionary
        large_dict = ParDict()
        for i in range(10):
            large_dict[f"PARAM_{i:02d}"] = Par(float(i), f"Parameter {i}")

        # Act: Get string representation
        str_repr = str(large_dict)

        # Assert: Display is truncated with ellipsis
        assert "10 parameters" in str_repr
        assert "..." in str_repr  # Truncation indicator


class TestParameterDictionaryEdgeCases:
    """Test edge cases and error conditions."""

    def test_user_can_handle_empty_dictionary_operations(self, empty_parameter_dict) -> None:
        """
        User can perform all operations on empty dictionaries without errors.

        GIVEN: A user has an empty parameter dictionary
        WHEN: They perform various operations on it
        THEN: All operations should complete without errors
        """
        # Arrange: Empty dictionary
        another_empty = ParDict()

        # Act & Assert: All operations work with empty dictionaries
        empty_parameter_dict.append(another_empty)
        assert len(empty_parameter_dict) == 0

        empty_parameter_dict.remove_if_similar(another_empty)
        assert len(empty_parameter_dict) == 0

        different = empty_parameter_dict.get_different_parameters(another_empty)
        assert len(different) == 0

        common = empty_parameter_dict.get_common_parameters(another_empty)
        assert len(common) == 0

        filtered = empty_parameter_dict.filter_by_prefix("ANY")
        assert len(filtered) == 0

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

        # Copy works with None comments
        copied = param_dict.copy()
        assert copied["PARAM_1"].comment is None

    def test_parameter_equality_works_correctly_for_comparisons(self) -> None:
        """
        Parameter equality comparison works correctly for all comparison operations.

        GIVEN: Parameters with various value and comment combinations
        WHEN: They are compared for equality
        THEN: Equality should be determined by both value and comment
        """
        # Arrange: Parameters with different combinations
        param1 = Par(1.0, "Comment")
        param2 = Par(1.0, "Comment")  # Identical
        param3 = Par(1.0, "Different comment")  # Same value, different comment
        param4 = Par(2.0, "Comment")  # Different value, same comment

        dict1 = ParDict({"PARAM": param1})
        dict2 = ParDict({"PARAM": param2})
        dict3 = ParDict({"PARAM": param3})
        dict4 = ParDict({"PARAM": param4})

        # Act & Assert: Equality comparisons work correctly
        common_1_2 = dict1.get_common_parameters(dict2)
        assert len(common_1_2) == 1  # Identical parameters

        common_1_3 = dict1.get_common_parameters(dict3)
        assert len(common_1_3) == 0  # Different comments

        common_1_4 = dict1.get_common_parameters(dict4)
        assert len(common_1_4) == 0  # Different values
