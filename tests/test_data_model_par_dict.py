#!/usr/bin/env python3

"""
Behavior-driven tests for ArduPilot parameter dictionary data model.

This module contains comprehensive tests for the ParDict class,
focusing on user workflows and business value rather than implementation details.

SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import os
import tempfile
from collections.abc import Generator
from unittest.mock import MagicMock, patch

import pytest

import ardupilot_methodic_configurator.data_model_par_dict as par_dict_module
from ardupilot_methodic_configurator.data_model_par_dict import Par, ParDict, is_within_tolerance, validate_param_name

# pylint: disable=redefined-outer-name, too-many-lines


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


@pytest.fixture
def default_parameters() -> ParDict:
    """Fixture providing default parameter values for comparison testing."""
    default_data = {
        "ACRO_YAW_P": Par(4.5, "Default yaw P gain"),  # Same as sample
        "PILOT_SPEED_UP": Par(200.0, "Default climb rate"),  # Different from sample
        "DEFAULT_ONLY": Par(0.0, "Parameter only in defaults"),
    }
    return ParDict(default_data)


@pytest.fixture
def documentation_dict() -> dict:
    """Fixture providing parameter documentation metadata."""
    return {
        "ACRO_YAW_P": {"ReadOnly": False, "Calibration": False},
        "PILOT_SPEED_UP": {"ReadOnly": True, "Calibration": False},
        "BATT_CAPACITY": {"ReadOnly": False, "Calibration": True},
        "GPS_TYPE": {"ReadOnly": False, "Calibration": False},
        "COMPASS_ENABLE": {"ReadOnly": False, "Calibration": True},
    }


@pytest.fixture
def temp_param_file() -> Generator[str, None, None]:
    """Fixture providing a temporary parameter file for testing."""
    content = """# Test parameter file
ACRO_YAW_P,4.5  # Yaw P gain
PILOT_SPEED_UP,250.0  # Pilot controlled climb rate
BATT_CAPACITY,5000.0  # Battery capacity in mAh
GPS_TYPE,1.0
COMPASS_ENABLE,1.0  # Enable compass
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".param", delete=False) as f:
        f.write(content)
        f.flush()
        yield f.name
    os.unlink(f.name)


@pytest.fixture
def temp_mavproxy_file() -> Generator[str, None, None]:
    """Fixture providing a temporary MAVProxy-style parameter file."""
    content = """# MAVProxy style parameter file
ACRO_YAW_P      4.500000  # Yaw P gain
PILOT_SPEED_UP  250.000000  # Pilot controlled climb rate
BATT_CAPACITY   5000.000000
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".param", delete=False) as f:
        f.write(content)
        f.flush()
        yield f.name
    os.unlink(f.name)


class TestParTolerance:
    """Test is_within_tolerance function behavior and functionality."""

    def test_tolerance_handling(self) -> None:
        """Test parameter value tolerance checking."""
        # Setup LocalFilesystem instance

        # Test cases within tolerance (default 0.01%)
        assert is_within_tolerance(10.0, 10.0009)  # +0.009% - should pass
        assert is_within_tolerance(10.0, 9.9991)  # -0.009% - should pass
        assert is_within_tolerance(100, 100)  # Exact match
        assert is_within_tolerance(0.0, 0.0)  # Zero case

        # Test cases outside tolerance
        assert not is_within_tolerance(10.0, 10.02)  # +0.2% - should fail
        assert not is_within_tolerance(10.0, 9.98)  # -0.2% - should fail
        assert not is_within_tolerance(100, 101)  # Integer case

        # Test with custom tolerance
        custom_tolerance = 0.2  # 0.2%
        assert is_within_tolerance(10.0, 10.015, atol=custom_tolerance)  # +0.15% - should pass
        assert is_within_tolerance(10.0, 9.985, atol=custom_tolerance)  # -0.15% - should pass

    def test_is_within_tolerance_edge_cases(self) -> None:
        """Test is_within_tolerance function with edge cases."""
        # Test with negative values
        assert is_within_tolerance(-100, -100)
        assert is_within_tolerance(-100, -100.0099)  # 0.0099% difference
        assert not is_within_tolerance(-100, -101)  # 1% difference

        # Test with very small values (where absolute tolerance dominates)
        assert is_within_tolerance(1e-10, 1.09e-10)  # 9% difference but absolute diff is tiny
        assert is_within_tolerance(0, 1e-9)  # Zero case with small absolute difference

        # Test with very large values
        assert is_within_tolerance(1e10, 1.00009e10)  # 0.009% difference
        assert not is_within_tolerance(1e10, 1.01e10)  # 1% difference

        # Test with custom tolerances
        assert is_within_tolerance(100, 102, atol=3)  # 2% difference but within atol=3
        assert is_within_tolerance(100, 110, rtol=0.1)  # 10% difference but within rtol=0.1


class TestParameterNameValidation:  # pylint: disable=too-few-public-methods
    """Test user-facing validation of parameter names."""

    def test_user_receives_clear_feedback_when_validating_parameter_names(self) -> None:
        """
        User gets actionable guidance when checking parameter names.

        GIVEN: A user verifies both valid and invalid parameter name candidates
        WHEN: They call validate_param_name
        THEN: Valid names pass silently and invalid names return descriptive errors
        """
        # Act & Assert: Valid name succeeds without message
        assert validate_param_name("ACRO_YAW_P") == (True, "")

        # Assert: Invalid names report the specific issue
        invalid_cases = {
            "": "cannot be empty",
            "A" * 20: "too long",
            "lowercase": "Invalid parameter name format",
            "1INVALID": "Invalid parameter name format",
        }
        for candidate, expected_snippet in invalid_cases.items():
            is_valid, error_message = validate_param_name(candidate)
            assert not is_valid
            assert expected_snippet in error_message


class TestParClassBehavior:
    """Test Par class behavior and functionality."""

    def test_user_can_create_parameter_with_value_and_comment(self) -> None:
        """
        User can create a parameter with both value and comment.

        GIVEN: A user needs to define a parameter with documentation
        WHEN: They create a Par object with value and comment
        THEN: Both value and comment should be stored correctly
        """
        # Arrange & Act: Create parameter with value and comment
        param = Par(4.5, "Yaw P gain")

        # Assert: Parameter stores both value and comment
        assert param.value == 4.5
        assert param.comment == "Yaw P gain"

    def test_user_can_create_parameter_with_only_value(self) -> None:
        """
        User can create a parameter with only a value (no comment).

        GIVEN: A user has a parameter value without documentation
        WHEN: They create a Par object with only a value
        THEN: The value should be stored and comment should be None
        """
        # Arrange & Act: Create parameter with only value
        param = Par(250.0)

        # Assert: Parameter stores value with None comment
        assert param.value == 250.0
        assert param.comment is None

    def test_user_can_compare_parameters_for_equality(self) -> None:
        """
        User can compare parameters to check if they are identical.

        GIVEN: A user has multiple parameter objects
        WHEN: They compare parameters with same values and comments
        THEN: Parameters should be considered equal
        """
        # Arrange: Create identical parameters
        param1 = Par(4.5, "Yaw P gain")
        param2 = Par(4.5, "Yaw P gain")
        param3 = Par(4.5, "Different comment")

        # Act & Assert: Test equality comparisons
        assert param1 == param2  # Same value and comment
        assert param1 != param3  # Same value, different comment
        assert param1 != "not a parameter"  # Different type

    def test_user_can_use_parameters_in_sets_and_as_dict_keys(self) -> None:
        """
        User can use Par objects in sets and as dictionary keys.

        GIVEN: A user wants to use parameters in advanced data structures
        WHEN: They use Par objects in sets or as dictionary keys
        THEN: The objects should work correctly due to hash implementation
        """
        # Arrange: Create parameters
        param1 = Par(4.5, "Yaw P gain")
        param2 = Par(4.5, "Yaw P gain")  # Same as param1
        param3 = Par(6.0, "Different value")

        # Act: Use parameters in set and as dict keys
        param_set = {param1, param2, param3}
        param_mapping = {param1: "first", param3: "second"}

        # Assert: Parameters work in advanced data structures
        assert len(param_set) == 2  # param1 and param2 are the same
        assert param_mapping[param2] == "first"  # param2 can access param1's value


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


class TestParameterFileLoading:
    """Test parameter file loading workflows."""

    def test_user_can_load_missionplanner_style_parameter_file(self, temp_param_file) -> None:
        """
        User can load parameters from a Mission Planner style file.

        GIVEN: A user has a Mission Planner format parameter file
        WHEN: They load the file using load_param_file_into_dict
        THEN: All parameters should be loaded with correct values and comments
        """
        # Arrange: Temporary file is provided by fixture

        # Act: Load parameters from file
        param_dict = ParDict.load_param_file_into_dict(temp_param_file)

        # Assert: Parameters loaded correctly
        assert len(param_dict) == 5
        assert param_dict["ACRO_YAW_P"].value == 4.5
        assert param_dict["ACRO_YAW_P"].comment == "Yaw P gain"
        assert param_dict["GPS_TYPE"].value == 1.0
        assert param_dict["GPS_TYPE"].comment is None  # No comment in file

    def test_user_can_load_mavproxy_style_parameter_file(self, temp_mavproxy_file) -> None:
        """
        User can load parameters from a MAVProxy style file.

        GIVEN: A user has a MAVProxy format parameter file (space-separated)
        WHEN: They load the file using load_param_file_into_dict
        THEN: All parameters should be loaded correctly
        """
        # Arrange: MAVProxy style file provided by fixture

        # Act: Load parameters from MAVProxy file
        param_dict = ParDict.load_param_file_into_dict(temp_mavproxy_file)

        # Assert: Parameters loaded correctly from space-separated format
        assert len(param_dict) == 3
        assert param_dict["ACRO_YAW_P"].value == 4.5
        assert param_dict["PILOT_SPEED_UP"].value == 250.0
        assert param_dict["BATT_CAPACITY"].value == 5000.0

    def test_user_can_create_pardict_from_file_using_class_method(self, temp_param_file) -> None:
        """
        User can create a ParDict directly from a file using the from_file class method.

        GIVEN: A user has a parameter file to load
        WHEN: They use ParDict.from_file() class method
        THEN: A new ParDict instance should be created with all file parameters
        """
        # Arrange: Parameter file provided by fixture

        # Act: Create ParDict from file
        param_dict = ParDict.from_file(temp_param_file)

        # Assert: ParDict created with all file parameters
        assert isinstance(param_dict, ParDict)
        assert len(param_dict) == 5
        assert param_dict["BATT_CAPACITY"].value == 5000.0

    def test_user_receives_error_for_invalid_parameter_file(self) -> None:
        """
        User receives clear error when loading an invalid parameter file.

        GIVEN: A user tries to load a file with invalid parameter format
        WHEN: They use load_param_file_into_dict on the invalid file
        THEN: A SystemExit should be raised with descriptive error message
        """
        # Arrange: Create temporary file with invalid content
        invalid_content = """INVALID_LINE_WITHOUT_SEPARATOR
VALID_PARAM,1.0"""

        with tempfile.NamedTemporaryFile(mode="w", suffix=".param", delete=False) as f:
            f.write(invalid_content)
            f.flush()

            # Act & Assert: User gets clear error for invalid format
            with pytest.raises(SystemExit, match="Missing parameter-value separator"):
                ParDict.load_param_file_into_dict(f.name)

        os.unlink(f.name)

    def test_user_receives_error_for_duplicate_parameters(self) -> None:
        """
        User receives error when file contains duplicate parameter names.

        GIVEN: A user has a parameter file with duplicate parameter names
        WHEN: They try to load the file
        THEN: A SystemExit should be raised indicating the duplication
        """
        # Arrange: Create file with duplicate parameters
        duplicate_content = """ACRO_YAW_P,4.5
ACRO_YAW_P,6.0  # Duplicate parameter"""

        with tempfile.NamedTemporaryFile(mode="w", suffix=".param", delete=False) as f:
            f.write(duplicate_content)
            f.flush()

            # Act & Assert: User gets error for duplicate parameters
            with pytest.raises(SystemExit, match="Duplicated parameter"):
                ParDict.load_param_file_into_dict(f.name)

        os.unlink(f.name)

    def test_user_receives_guidance_when_parameter_file_is_not_utf8(self) -> None:
        """
        User gets clear UTF-8 guidance when loading non-compliant files.

        GIVEN: A user tries to load a parameter file saved with legacy encoding
        WHEN: They read it through load_param_file_into_dict
        THEN: A SystemExit with UTF-8 instructions should be raised
        """
        with tempfile.NamedTemporaryFile(mode="wb", suffix=".param", delete=False) as f:
            f.write(b"\xff\xfe\xfa")  # Invalid UTF-8 byte sequence
            f.flush()
            bad_file = f.name

        try:
            with pytest.raises(SystemExit, match="UTF-8"):
                ParDict.load_param_file_into_dict(bad_file)
        finally:
            os.unlink(bad_file)

    def test_user_receives_traceback_hint_when_parameter_assignment_fails(self) -> None:
        """
        User gets actionable context when the filesystem rejects parameter writes.

        GIVEN: A user loads a valid line but the underlying write fails (e.g., disk full)
        WHEN: _validate_parameter handles the assignment
        THEN: A SystemExit should include the offending line information
        """
        parameter_dict = ParDict()
        original_line = "ACRO_YAW_P,4.5"
        with (
            patch.object(ParDict, "__setitem__", side_effect=OSError("disk full"), autospec=True),
            pytest.raises(SystemExit, match="Caused by line 1"),
        ):
            ParDict._validate_parameter(  # pylint: disable=protected-access
                "test.param",
                parameter_dict,
                1,
                original_line,
                None,
                "ACRO_YAW_P",
                "4.5",
            )

    def test_user_can_ignore_blank_and_comment_only_lines_when_loading(self) -> None:
        """
        User can safely ignore blank and comment-only lines in parameter files.

        GIVEN: A parameter file that mixes comments, blank lines, and valid entries
        WHEN: They load it with load_param_file_into_dict
        THEN: Only the valid parameters should appear in the resulting dictionary
        """
        content = """# Initial comment

ACRO_YAW_P,4.5

# Another comment line
PILOT_SPEED_UP,250.0
"""

        with tempfile.NamedTemporaryFile(mode="w", suffix=".param", delete=False) as f:
            f.write(content)
            f.flush()
            file_path = f.name

        try:
            param_dict = ParDict.load_param_file_into_dict(file_path)
        finally:
            os.unlink(file_path)

        assert len(param_dict) == 2
        assert param_dict["ACRO_YAW_P"].value == 4.5
        assert param_dict["PILOT_SPEED_UP"].value == 250.0

    def test_user_continues_when_traceback_information_is_missing(self, monkeypatch) -> None:
        """
        User still completes validation even if traceback information is unavailable.

        GIVEN: A filesystem write fails but sys_exc_info cannot provide traceback details
        WHEN: _validate_parameter handles the failure
        THEN: The method should suppress the error without raising SystemExit
        """
        parameter_dict = ParDict()
        monkeypatch.setattr(par_dict_module, "sys_exc_info", lambda: (None, None, None))
        with patch.object(ParDict, "__setitem__", side_effect=OSError("disk full"), autospec=True):
            ParDict._validate_parameter(  # pylint: disable=protected-access
                "test.param",
                parameter_dict,
                1,
                "ACRO_YAW_P,4.5",
                None,
                "ACRO_YAW_P",
                "4.5",
            )

        assert "ACRO_YAW_P" not in parameter_dict


class TestParameterFileExporting:
    """Test parameter file exporting workflows."""

    def test_user_can_export_parameters_to_missionplanner_format(self, parameter_dict) -> None:
        """
        User can export parameters to Mission Planner format file.

        GIVEN: A user has a configured parameter dictionary
        WHEN: They export to a file using Mission Planner format
        THEN: Parameters should be saved in comma-separated format with comments
        """
        # Arrange: Create temporary output file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".param", delete=False) as f:
            output_file = f.name

        try:
            # Act: Export parameters to Mission Planner format
            parameter_dict.export_to_param(output_file, "missionplanner")

            # Assert: File contains correctly formatted parameters
            with open(output_file, encoding="utf-8") as f:
                content = f.read()

            assert "ACRO_YAW_P,4.5  # Yaw P gain" in content
            assert "GPS_TYPE,1" in content  # No comment
            assert len(content.splitlines()) >= 5  # At least 5 parameters
        finally:
            os.unlink(output_file)

    def test_user_can_export_parameters_to_mavproxy_format(self, parameter_dict) -> None:
        """
        User can export parameters to MAVProxy format file.

        GIVEN: A user has a configured parameter dictionary
        WHEN: They export to a file using MAVProxy format
        THEN: Parameters should be saved in space-separated format
        """
        # Arrange: Create temporary output file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".param", delete=False) as f:
            output_file = f.name

        try:
            # Act: Export parameters to MAVProxy format
            parameter_dict.export_to_param(output_file, "mavproxy")

            # Assert: File contains space-separated format
            with open(output_file, encoding="utf-8") as f:
                content = f.read()

            # MAVProxy format uses fixed-width columns
            assert "ACRO_YAW_P       4.500000  # Yaw P gain" in content
            assert "GPS_TYPE         1.000000" in content
        finally:
            os.unlink(output_file)

    def test_user_can_export_parameters_with_custom_header(self, parameter_dict) -> None:
        """
        User can export parameters with custom header content.

        GIVEN: A user wants to add custom header information to exported file
        WHEN: They export with content_header parameter
        THEN: The header should appear at the top of the exported file
        """
        # Arrange: Prepare custom header and output file
        custom_header = ["# Custom vehicle configuration", "# Generated on 2024-01-01"]

        with tempfile.NamedTemporaryFile(mode="w", suffix=".param", delete=False) as f:
            output_file = f.name

        try:
            # Act: Export with custom header
            parameter_dict.export_to_param(output_file, content_header=custom_header)

            # Assert: File starts with custom header
            with open(output_file, encoding="utf-8") as f:
                lines = f.readlines()

            assert lines[0].strip() == "# Custom vehicle configuration"
            assert lines[1].strip() == "# Generated on 2024-01-01"
            assert "ACRO_YAW_P" in lines[2]  # Parameters start after header
        finally:
            os.unlink(output_file)


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

    def test_user_receives_error_when_comparing_with_invalid_type(self, parameter_dict) -> None:
        """
        User receives error when trying to compare with non-ParDict objects.

        GIVEN: A user has a valid parameter dictionary
        WHEN: They try to use remove_if_value_is_similar with non-ParDict data
        THEN: A TypeError should be raised with helpful message
        """
        # Arrange: Invalid comparison data
        invalid_data = {"PARAM": 1.0}

        # Act & Assert: User gets clear error message
        with pytest.raises(TypeError, match="Can only compare with another ParDict instance"):
            parameter_dict.remove_if_value_is_similar(invalid_data)

    def test_user_can_find_missing_or_different_parameters(self, parameter_dict, alternate_parameter_dict) -> None:
        """
        User can identify parameters that are missing or have different values in another dictionary.

        GIVEN: A user has two parameter configurations to compare
        WHEN: They use get_missing_or_different to find differences
        THEN: Only parameters that are missing or have different values should be returned
        """
        # Arrange: Two dictionaries with some differences

        # Act: Find missing or different parameters
        differences = parameter_dict.get_missing_or_different(alternate_parameter_dict)

        # Assert: Only different/missing parameters identified
        assert "PILOT_SPEED_UP" in differences  # Missing in alternate
        assert "BATT_CAPACITY" in differences  # Missing in alternate
        assert "GPS_TYPE" in differences  # Missing in alternate
        assert "ACRO_YAW_P" in differences  # Different value (4.5 vs 6.0)
        assert "COMPASS_ENABLE" not in differences  # Same value in both

    def test_user_receives_error_when_requesting_differences_with_invalid_type(self, parameter_dict) -> None:
        """
        User receives clear feedback when requesting differences with invalid data types.

        GIVEN: A user attempts to compare against a plain dictionary
        WHEN: They call get_missing_or_different
        THEN: A TypeError should explain that only ParDict instances are supported
        """
        with pytest.raises(TypeError, match="Can only compare with another ParDict instance"):
            parameter_dict.get_missing_or_different({"PARAM": Par(1.0)})


class TestParameterCreationFromDifferentSources:
    """Test creating ParDict from various data sources."""

    def test_user_can_create_pardict_from_float_dictionary(self) -> None:
        """
        User can create a ParDict from a simple float dictionary.

        GIVEN: A user has flight controller parameters as float values
        WHEN: They convert them to ParDict using from_float_dict
        THEN: A ParDict with Par objects should be created with default comments
        """
        # Arrange: Simple float dictionary (like FC parameters)
        float_params = {
            "ACRO_YAW_P": 4.5,
            "PILOT_SPEED_UP": 250.0,
            "BATT_CAPACITY": 5000.0,
        }

        # Act: Create ParDict from float dictionary
        param_dict = ParDict.from_float_dict(float_params, "FC parameter")

        # Assert: ParDict created with default comments
        assert len(param_dict) == 3
        assert param_dict["ACRO_YAW_P"].value == 4.5
        assert param_dict["ACRO_YAW_P"].comment == "FC parameter"
        assert param_dict["PILOT_SPEED_UP"].value == 250.0

    def test_user_can_create_pardict_from_fc_parameters(self) -> None:
        """
        User can create a ParDict from flight controller parameters.

        GIVEN: A user receives parameters from a flight controller
        WHEN: They convert them using from_fc_parameters
        THEN: A ParDict should be created with empty comments
        """
        # Arrange: FC parameters (typically just floats)
        fc_params = {
            "ACRO_YAW_P": 4.5,
            "GPS_TYPE": 1.0,
        }

        # Act: Create ParDict from FC parameters
        param_dict = ParDict.from_fc_parameters(fc_params)

        # Assert: ParDict created with no comments (FC default)
        assert len(param_dict) == 2
        assert param_dict["ACRO_YAW_P"].value == 4.5
        assert param_dict["ACRO_YAW_P"].comment == ""  # Default empty comment
        assert param_dict["GPS_TYPE"].value == 1.0


class TestParameterFiltering:
    """Test parameter filtering by various criteria."""

    def test_user_can_filter_parameters_by_default_values(self, parameter_dict, default_parameters) -> None:
        """
        User can filter out parameters that match default values.

        GIVEN: A user has current parameters and default parameter values
        WHEN: They filter by defaults using _filter_by_defaults
        THEN: Only parameters that differ from defaults should remain
        """
        # Arrange: Parameters with some matching defaults

        # Act: Filter out parameters that match defaults
        non_default = parameter_dict._filter_by_defaults(default_parameters)  # pylint: disable=protected-access

        # Assert: Only non-default parameters remain
        assert "ACRO_YAW_P" not in non_default  # Same as default
        assert "PILOT_SPEED_UP" in non_default  # Different from default (250 vs 200)
        assert "BATT_CAPACITY" in non_default  # Not in defaults
        assert "GPS_TYPE" in non_default  # Not in defaults

    def test_user_can_filter_parameters_by_default_values_with_tolerance(self, parameter_dict, default_parameters) -> None:
        """
        User can filter parameters by defaults using a tolerance function.

        GIVEN: A user wants to filter parameters with a tolerance for floating point comparison
        WHEN: They provide a tolerance function to _filter_by_defaults
        THEN: Parameters within tolerance should be filtered out
        """

        # Arrange: Define tolerance function
        def tolerance_func(val1: float, val2: float) -> bool:
            return abs(val1 - val2) < 100.0  # 100 unit tolerance

        # Act: Filter with tolerance
        non_default = parameter_dict._filter_by_defaults(default_parameters, tolerance_func)  # pylint: disable=protected-access

        # Assert: Parameters within tolerance are filtered
        assert "PILOT_SPEED_UP" not in non_default  # 250 vs 200 = 50 difference (within tolerance)
        assert "BATT_CAPACITY" in non_default  # Not in defaults, so kept

    def test_user_can_filter_readonly_parameters(self, parameter_dict, documentation_dict) -> None:
        """
        User can identify read-only parameters using documentation.

        GIVEN: A user has parameters and documentation indicating read-only status
        WHEN: They filter by read-only status
        THEN: Only read-only parameters should be returned
        """
        # Arrange: Documentation indicates PILOT_SPEED_UP is read-only

        # Act: Filter read-only parameters
        readonly_params = parameter_dict._filter_by_readonly(documentation_dict)  # pylint: disable=protected-access

        # Assert: Only read-only parameters identified
        assert len(readonly_params) == 1
        assert "PILOT_SPEED_UP" in readonly_params  # Marked as ReadOnly: True
        assert "ACRO_YAW_P" not in readonly_params  # Marked as ReadOnly: False

    def test_user_can_filter_calibration_parameters(self, parameter_dict, documentation_dict) -> None:
        """
        User can identify calibration parameters using documentation.

        GIVEN: A user has parameters and documentation indicating calibration status
        WHEN: They filter by calibration status
        THEN: Only calibration parameters should be returned
        """
        # Arrange: Documentation indicates BATT_CAPACITY and COMPASS_ENABLE are calibration

        # Act: Filter calibration parameters
        calibration_params = parameter_dict._filter_by_calibration(documentation_dict)  # pylint: disable=protected-access

        # Assert: Only calibration parameters identified
        assert len(calibration_params) == 2
        assert "BATT_CAPACITY" in calibration_params  # Marked as Calibration: True
        assert "COMPASS_ENABLE" in calibration_params  # Marked as Calibration: True
        assert "ACRO_YAW_P" not in calibration_params  # Marked as Calibration: False

    def test_user_can_categorize_parameters_by_documentation(
        self, parameter_dict, default_parameters, documentation_dict
    ) -> None:
        """
        User can categorize parameters into read-only, calibration, and other categories.

        GIVEN: A user has parameters with documentation and default values
        WHEN: They categorize using categorize_by_documentation
        THEN: Parameters should be sorted into appropriate categories
        """
        # Arrange: Parameters, defaults, and documentation provided by fixtures

        # Act: Categorize parameters
        readonly, calibration, other = parameter_dict.categorize_by_documentation(documentation_dict, default_parameters)

        # Assert: Parameters categorized correctly
        # Note: Only non-default parameters are categorized
        assert "PILOT_SPEED_UP" in readonly  # Read-only and non-default
        assert "BATT_CAPACITY" in calibration  # Calibration and non-default
        assert "GPS_TYPE" in other  # Neither read-only nor calibration, non-default


class TestParameterUtilities:
    """Test utility methods for parameter handling."""

    def test_user_can_sort_parameters_using_missionplanner_rules(self) -> None:
        """
        User can sort parameter names using Mission Planner sorting rules.

        GIVEN: A user has parameter names that need to be sorted
        WHEN: They use missionplanner_sort function
        THEN: Parameters should be sorted by component parts
        """
        # Arrange: Parameter names with different patterns
        param_names = ["BATT_CAPACITY", "ACRO_YAW_P", "BATT_MONITOR", "ACRO_PITCH_P"]

        # Act: Sort using Mission Planner rules
        sorted_names = sorted(param_names, key=ParDict.missionplanner_sort)

        # Assert: Parameters sorted by component groups
        assert sorted_names[0].startswith("ACRO")
        assert sorted_names[1].startswith("ACRO")
        assert sorted_names[2].startswith("BATT")
        assert sorted_names[3].startswith("BATT")

    def test_user_can_format_parameters_for_missionplanner(self, parameter_dict) -> None:
        """
        User can format parameters for Mission Planner compatibility.

        GIVEN: A user has parameters to format for Mission Planner
        WHEN: They use _format_params with missionplanner format
        THEN: Parameters should be formatted with comma separation
        """
        # Arrange: Parameter dictionary with mixed comments

        # Act: Format for Mission Planner
        formatted = parameter_dict._format_params("missionplanner")  # pylint: disable=protected-access

        # Assert: Correct Mission Planner format
        assert any("ACRO_YAW_P,4.5  # Yaw P gain" in line for line in formatted)
        assert any("GPS_TYPE,1" in line for line in formatted)  # No comment case
        assert len(formatted) == 5  # All parameters formatted

    def test_user_can_format_parameters_for_mavproxy(self, parameter_dict) -> None:
        """
        User can format parameters for MAVProxy compatibility.

        GIVEN: A user has parameters to format for MAVProxy
        WHEN: They use _format_params with mavproxy format
        THEN: Parameters should be formatted with space separation and fixed width
        """
        # Arrange: Parameter dictionary

        # Act: Format for MAVProxy
        formatted = parameter_dict._format_params("mavproxy")  # pylint: disable=protected-access

        # Assert: Correct MAVProxy format (space-separated, fixed width)
        yaw_line = next((line for line in formatted if "ACRO_YAW_P" in line), "")
        assert yaw_line == "ACRO_YAW_P       4.500000  # Yaw P gain"

    def test_user_receives_error_for_unsupported_format(self, parameter_dict) -> None:
        """
        User receives error when using unsupported export format.

        GIVEN: A user tries to format parameters with unsupported format
        WHEN: They call _format_params with invalid format
        THEN: A SystemExit should be raised with error message
        """
        # Arrange: Invalid format string

        # Act & Assert: User gets error for unsupported format
        with pytest.raises(SystemExit, match="Unsupported file format"):
            parameter_dict._format_params("invalid_format")  # pylint: disable=protected-access

    def test_user_can_annotate_parameters_with_comments(self, parameter_dict) -> None:
        """
        User can add comments to parameters using a lookup table.

        GIVEN: A user has parameters without comments and a comment lookup
        WHEN: They use annotate_with_comments
        THEN: Parameters should be updated with comments from lookup
        """
        # Arrange: Comment lookup table
        comment_lookup = {
            "ACRO_YAW_P": "Updated yaw P gain comment",
            "GPS_TYPE": "GPS receiver type selection",
            "NEW_PARAM": "This param doesn't exist",
        }

        # Act: Annotate with comments
        annotated = parameter_dict.annotate_with_comments(comment_lookup)

        # Assert: Comments updated from lookup
        assert annotated["ACRO_YAW_P"].comment == "Updated yaw P gain comment"
        assert annotated["GPS_TYPE"].comment == "GPS receiver type selection"
        assert annotated["PILOT_SPEED_UP"].comment == "Pilot controlled climb rate"  # Original preserved

    @patch("ardupilot_methodic_configurator.data_model_par_dict.os_popen")
    def test_user_can_print_parameter_list_with_pagination(self, mock_popen) -> None:
        """
        User can print long parameter lists with automatic pagination.

        GIVEN: A user has a long list of formatted parameters
        WHEN: They use print_out static method
        THEN: Parameters should be printed with pagination control
        """
        # Arrange: Mock terminal size and formatted parameters
        mock_popen.return_value.read.return_value = "25 80"  # 25 rows, 80 columns
        formatted_params = [f"PARAM_{i},1.0" for i in range(50)]  # Long list

        # Act: Print with pagination (capture in StringIO since we can't easily test print)
        with patch("builtins.print") as mock_print:
            ParDict.print_out(formatted_params, "Test Parameters")

        # Assert: Print called with pagination info
        mock_print.assert_any_call("\nTest Parameters has 50 parameters:")

    def test_user_skips_printing_when_parameter_list_is_empty(self) -> None:
        """
        User skips any output when no parameters exist to print.

        GIVEN: A user requests to print an empty parameter list
        WHEN: They call print_out
        THEN: No print statements should be executed
        """
        with patch("builtins.print") as mock_print:
            ParDict.print_out([], "Empty Params")

        mock_print.assert_not_called()

    def test_user_gets_cli_pagination_when_running_as_main(self, monkeypatch) -> None:
        """
        User sees CLI pagination prompts when running the module as a script.

        GIVEN: A user invokes print_out while the module behaves as __main__
        WHEN: The parameter list exceeds one terminal page
        THEN: The user should be prompted to continue and terminal size should refresh
        """
        terminal_result = MagicMock()
        terminal_result.read.return_value = "5 80"  # Terminal with 5 rows for this test
        mock_popen = MagicMock(return_value=terminal_result)
        monkeypatch.setattr(par_dict_module, "os_popen", mock_popen)
        monkeypatch.setattr(par_dict_module, "__name__", "__main__")
        mock_input = MagicMock(return_value="")
        monkeypatch.setattr("builtins.input", mock_input)

        with patch("builtins.print") as mock_print:
            ParDict.print_out([f"PARAM_{i},1.0" for i in range(6)], "CLI Parameters")

        assert mock_input.call_count >= 1
        assert mock_popen.call_count >= 2  # Initial size read and refresh after pagination pause
        mock_print.assert_any_call("\nCLI Parameters has 6 parameters:")


class TestParameterCategorization:
    """Test parameter categorization workflows by documentation."""

    def test_user_can_categorize_parameters_by_documentation_type(
        self, parameter_dict, documentation_dict, default_parameters
    ) -> None:
        """
        User can categorize parameters into read-only, calibration, and other types.

        GIVEN: A user has parameters with documentation metadata
        WHEN: They categorize parameters by documentation type
        THEN: Parameters should be properly sorted into read-only, calibration, and other categories
        """
        # Arrange: Parameter dictionary with documentation

        # Act: Categorize parameters by documentation
        readonly, calibration, other = parameter_dict.categorize_by_documentation(documentation_dict, default_parameters)

        # Assert: Parameters correctly categorized
        assert "PILOT_SPEED_UP" in readonly  # Marked as ReadOnly=True
        assert "BATT_CAPACITY" in calibration  # Marked as Calibration=True
        assert "COMPASS_ENABLE" in calibration  # Marked as Calibration=True
        assert "ACRO_YAW_P" not in readonly  # Not read-only
        assert "ACRO_YAW_P" not in calibration  # Not calibration
        assert "GPS_TYPE" in other  # Non-default, non-readonly, non-calibration

    def test_user_can_categorize_parameters_with_tolerance_function(
        self, parameter_dict, documentation_dict, default_parameters
    ) -> None:
        """
        User can categorize parameters using a custom tolerance function for value comparison.

        GIVEN: A user has parameters and wants to use tolerance-based comparison
        WHEN: They provide a tolerance function for categorization
        THEN: Parameters should be categorized considering the tolerance
        """

        # Arrange: Custom tolerance function (always returns True for this test)
        def always_within_tolerance(_value1: float, _value2: float) -> bool:
            return True

        # Act: Categorize with tolerance function
        readonly, calibration, other = parameter_dict.categorize_by_documentation(
            documentation_dict, default_parameters, always_within_tolerance
        )

        # Assert: Only parameters not in defaults remain, but tolerance affects those that are
        # PILOT_SPEED_UP should be filtered out by tolerance despite different value
        assert "PILOT_SPEED_UP" not in readonly  # Tolerance made it seem default
        # Parameters not in defaults (BATT_CAPACITY, GPS_TYPE, COMPASS_ENABLE) still remain
        assert len(readonly) == 0  # No readonly parameters after tolerance filtering
        assert "BATT_CAPACITY" in calibration  # Still non-default, still calibration
        assert "COMPASS_ENABLE" in calibration  # Still non-default, still calibration
        assert "GPS_TYPE" in other  # Still non-default, not readonly, not calibration


class TestParameterCommentAnnotation:
    """Test parameter comment annotation workflows."""

    def test_user_can_annotate_parameters_with_new_comments(self, parameter_dict) -> None:
        """
        User can add or update comments on parameters from a lookup table.

        GIVEN: A user has parameters and wants to add descriptive comments
        WHEN: They use annotate_with_comments with a comment lookup table
        THEN: Parameters should have updated comments from the lookup table
        """
        # Arrange: Comment lookup table
        comment_lookup = {
            "ACRO_YAW_P": "Updated yaw rate controller P gain",
            "BATT_CAPACITY": "Battery capacity for flight planning",
            "NEW_PARAM": "This parameter doesn't exist in original",
        }

        # Act: Annotate parameters with new comments
        annotated_params = parameter_dict.annotate_with_comments(comment_lookup)

        # Assert: Comments updated from lookup table
        assert annotated_params["ACRO_YAW_P"].comment == "Updated yaw rate controller P gain"
        assert annotated_params["BATT_CAPACITY"].comment == "Battery capacity for flight planning"
        assert annotated_params["PILOT_SPEED_UP"].comment == "Pilot controlled climb rate"  # Original comment preserved

    def test_user_can_preserve_original_comments_when_no_lookup_found(self, parameter_dict) -> None:
        """
        User preserves original comments when no lookup entry is found.

        GIVEN: A user has parameters with existing comments and an incomplete lookup table
        WHEN: They annotate parameters but some parameters are not in the lookup
        THEN: Original comments should be preserved for parameters not in lookup
        """
        # Arrange: Partial comment lookup
        partial_lookup = {
            "ACRO_YAW_P": "New yaw comment",
            # PILOT_SPEED_UP not in lookup - should preserve original
        }

        # Act: Annotate with partial lookup
        annotated_params = parameter_dict.annotate_with_comments(partial_lookup)

        # Assert: Mixed comment sources
        assert annotated_params["ACRO_YAW_P"].comment == "New yaw comment"  # From lookup
        assert annotated_params["PILOT_SPEED_UP"].comment == "Pilot controlled climb rate"  # Original preserved


class TestParameterSortingBehavior:
    """Test parameter sorting functionality."""

    def test_user_gets_mission_planner_compatible_sorting(self) -> None:
        """
        User gets parameters sorted in Mission Planner compatible order.

        GIVEN: A user has parameters that need to be sorted for Mission Planner
        WHEN: They use missionplanner_sort function
        THEN: Parameters should be sorted by underscore-separated parts
        """
        # Arrange: Parameter names to sort
        param_names = ["BATT_CAPACITY", "ACRO_YAW_P", "PILOT_SPEED_UP", "GPS_TYPE"]

        # Act: Sort using Mission Planner rules
        sorted_names = sorted(param_names, key=ParDict.missionplanner_sort)

        # Assert: Correct alphabetical order by parts
        expected_order = ["ACRO_YAW_P", "BATT_CAPACITY", "GPS_TYPE", "PILOT_SPEED_UP"]
        assert sorted_names == expected_order

    def test_user_gets_consistent_parameter_sorting_with_underscore_parts(self) -> None:
        """
        User gets consistent sorting when parameters have multiple underscore parts.

        GIVEN: A user has parameters with multiple underscore separators
        WHEN: They sort using missionplanner_sort
        THEN: Each part should be compared separately for consistent ordering
        """
        # Arrange: Complex parameter names
        complex_names = ["MOTOR_PWM_TYPE", "MOTOR_EXPO", "MOTOR_THST_EXPO", "MOTOR_PWM_MAX"]

        # Act: Sort using Mission Planner rules
        sorted_names = sorted(complex_names, key=ParDict.missionplanner_sort)

        # Assert: Correct part-wise sorting
        expected_order = ["MOTOR_EXPO", "MOTOR_PWM_MAX", "MOTOR_PWM_TYPE", "MOTOR_THST_EXPO"]
        assert sorted_names == expected_order


class TestParameterParsingEdgeCases:
    """Test edge cases in parameter file parsing."""

    def test_user_can_parse_parameters_with_tab_separators(self) -> None:
        """
        User can parse parameter files that use tab separators.

        GIVEN: A user has a parameter file with tab-separated values
        WHEN: They load the parameter file
        THEN: Parameters should be correctly parsed despite tab separators
        """
        # Arrange: Parameter file with tab separators
        tab_content = "ACRO_YAW_P\t4.5\t# Tab separated parameter\nPILOT_SPEED_UP\t250.0"

        with tempfile.NamedTemporaryFile(mode="w", suffix=".param", delete=False) as f:
            f.write(tab_content)
            f.flush()
            f.close()

            try:
                # Act: Load parameter file with tabs
                params = ParDict.load_param_file_into_dict(f.name)

                # Assert: Parameters parsed correctly
                assert len(params) == 2
                assert params["ACRO_YAW_P"].value == 4.5
                assert params["ACRO_YAW_P"].comment == "Tab separated parameter"
                assert params["PILOT_SPEED_UP"].value == 250.0
            finally:
                os.unlink(f.name)

    def test_user_receives_clear_error_for_missing_separators(self) -> None:
        """
        User receives clear error when parameter files lack proper separators.

        GIVEN: A user has a malformed parameter file without proper separators
        WHEN: They try to load the parameter file
        THEN: A clear error message should be provided about missing separators
        """
        # Arrange: Malformed parameter content (no separator)
        malformed_content = "PARAM_WITHOUT_SEPARATOR_VALUE"

        with tempfile.NamedTemporaryFile(mode="w", suffix=".param", delete=False) as f:
            f.write(malformed_content)
            f.flush()
            f.close()

            try:
                # Act & Assert: Clear error for missing separator
                with pytest.raises(SystemExit, match="Missing parameter-value separator"):
                    ParDict.load_param_file_into_dict(f.name)
            finally:
                os.unlink(f.name)

    def test_user_receives_error_for_too_long_parameter_names(self) -> None:
        """
        User receives error when parameter names exceed maximum length.

        GIVEN: A user has a parameter file with names that are too long
        WHEN: They try to load the parameter file
        THEN: A clear error should be provided about parameter name length
        """
        # Arrange: Parameter name longer than 16 characters
        long_name = "A" * 17  # 17 characters (max is 16)
        long_param_content = f"{long_name},1.0"

        with tempfile.NamedTemporaryFile(mode="w", suffix=".param", delete=False) as f:
            f.write(long_param_content)
            f.flush()
            f.close()

            try:
                # Act & Assert: Error for too long parameter name
                with pytest.raises(SystemExit, match="Too long parameter name"):
                    ParDict.load_param_file_into_dict(f.name)
            finally:
                os.unlink(f.name)

    def test_user_receives_error_for_invalid_parameter_name_characters(self) -> None:
        """
        User receives error when parameter names contain invalid characters.

        GIVEN: A user has a parameter file with invalid characters in names
        WHEN: They try to load the parameter file
        THEN: A clear error should be provided about invalid characters
        """
        # Arrange: Parameter name with invalid characters (lowercase not allowed)
        invalid_content = "invalid_name,1.0"

        with tempfile.NamedTemporaryFile(mode="w", suffix=".param", delete=False) as f:
            f.write(invalid_content)
            f.flush()
            f.close()

            try:
                # Act & Assert: Error for invalid characters
                with pytest.raises(SystemExit, match="Invalid characters in parameter name"):
                    ParDict.load_param_file_into_dict(f.name)
            finally:
                os.unlink(f.name)

    def test_user_receives_error_for_duplicate_parameter_names(self) -> None:
        """
        User receives error when parameter files contain duplicate parameter names.

        GIVEN: A user has a parameter file with duplicate parameter names
        WHEN: They try to load the parameter file
        THEN: A clear error should be provided about parameter duplication
        """
        # Arrange: Parameter file with duplicates
        duplicate_content = "ACRO_YAW_P,4.5\nACRO_YAW_P,6.0"

        with tempfile.NamedTemporaryFile(mode="w", suffix=".param", delete=False) as f:
            f.write(duplicate_content)
            f.flush()
            f.close()

            try:
                # Act & Assert: Error for duplicate parameters
                with pytest.raises(SystemExit, match="Duplicated parameter"):
                    ParDict.load_param_file_into_dict(f.name)
            finally:
                os.unlink(f.name)

    def test_user_can_parse_parameters_with_leading_and_trailing_whitespace(self) -> None:
        """
        User can parse parameter files with various whitespace around parameter names and values.

        GIVEN: A user has a parameter file with inconsistent whitespace formatting
        WHEN: They load the parameter file
        THEN: Parameters should be correctly parsed with whitespace stripped
        """
        # Arrange: Parameter file with various whitespace scenarios
        whitespace_content = (
            "  PARAM1  ,  1.5  \n\tPARAM2\t,\t2.5\t\n   PARAM3   3.5   \n\t PARAM4\t \t4.5 \t\n\t\tPARAM5\t\t,\t\t5.5\t\t"
        )

        with tempfile.NamedTemporaryFile(mode="w", suffix=".param", delete=False) as f:
            f.write(whitespace_content)
            f.flush()
            f.close()

            try:
                # Act: Load parameter file with whitespace
                params = ParDict.load_param_file_into_dict(f.name)

                # Assert: All parameters parsed correctly with whitespace stripped
                assert len(params) == 5
                assert params["PARAM1"].value == 1.5
                assert params["PARAM2"].value == 2.5
                assert params["PARAM3"].value == 3.5
                assert params["PARAM4"].value == 4.5
                assert params["PARAM5"].value == 5.5
            finally:
                os.unlink(f.name)

    def test_user_can_parse_parameters_with_mixed_separator_and_whitespace_combinations(self) -> None:
        """
        User can parse parameter files with mixed separators and whitespace combinations.

        GIVEN: A user has a parameter file mixing comma, space, and tab separators with whitespace
        WHEN: They load the parameter file
        THEN: All parameters should be correctly parsed regardless of separator type
        """
        # Arrange: Mixed separator and whitespace combinations
        mixed_content = " COMMA1 , 1.0 \n\tTAB2\t2.0\t\n SPACE3   3.0  \n\t COMMA_TAB\t,\t 4.0 \t\n  TAB_SPACE  \t  5.0    "

        with tempfile.NamedTemporaryFile(mode="w", suffix=".param", delete=False) as f:
            f.write(mixed_content)
            f.flush()
            f.close()

            try:
                # Act: Load parameter file with mixed separators
                params = ParDict.load_param_file_into_dict(f.name)

                # Assert: All parameters parsed correctly
                assert len(params) == 5
                assert params["COMMA1"].value == 1.0
                assert params["TAB2"].value == 2.0
                assert params["SPACE3"].value == 3.0
                assert params["COMMA_TAB"].value == 4.0
                assert params["TAB_SPACE"].value == 5.0
            finally:
                os.unlink(f.name)

    def test_user_can_parse_parameters_with_extreme_whitespace_scenarios(self) -> None:
        """
        User can parse parameter files with extreme whitespace scenarios.

        GIVEN: A user has a parameter file with extreme amounts of whitespace
        WHEN: They load the parameter file
        THEN: Parameters should be parsed correctly with all whitespace properly handled
        """
        # Arrange: Extreme whitespace scenarios
        extreme_content = (
            "\t\t\tEXTREME1\t\t\t,\t\t\t1.0\t\t\t\n"
            "                    EXTREME2                    2.0                    \n"
            "\t \t \tEXTREME3\t \t ,\t \t 3.0\t \t \n"
            "        EXTREME4        ,        4.0        "
        )

        with tempfile.NamedTemporaryFile(mode="w", suffix=".param", delete=False) as f:
            f.write(extreme_content)
            f.flush()
            f.close()

            try:
                # Act: Load parameter file with extreme whitespace
                params = ParDict.load_param_file_into_dict(f.name)

                # Assert: All parameters parsed correctly despite extreme whitespace
                assert len(params) == 4
                assert params["EXTREME1"].value == 1.0
                assert params["EXTREME2"].value == 2.0
                assert params["EXTREME3"].value == 3.0
                assert params["EXTREME4"].value == 4.0
            finally:
                os.unlink(f.name)


class TestParameterDictionaryEdgeCases:
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

    def test_user_can_handle_empty_parameter_lists_gracefully(self) -> None:
        """
        User can handle empty parameter lists without errors.

        GIVEN: A user has empty parameter dictionaries
        WHEN: They perform operations on empty dictionaries
        THEN: Operations should complete without errors
        """
        # Arrange: Empty dictionaries
        empty1 = ParDict()
        empty2 = ParDict()

        # Act & Assert: Operations work with empty dictionaries
        empty1.append(empty2)  # Append empty to empty
        assert len(empty1) == 0

        empty1.remove_if_value_is_similar(empty2)  # Remove from empty
        assert len(empty1) == 0

        differences = empty1.get_missing_or_different(empty2)
        assert len(differences) == 0

    def test_parameter_validation_rejects_invalid_names(self) -> None:
        """
        Parameter validation rejects invalid parameter names.

        GIVEN: A user tries to load parameters with invalid names
        WHEN: The validation process checks parameter names
        THEN: Invalid names should be rejected with clear errors
        """
        # Arrange: Invalid parameter content
        invalid_names = [
            "lowercase_param,1.0",  # Lowercase not allowed
            "123_NUMERIC_START,1.0",  # Can't start with number
            "PARAM-WITH-DASH,1.0",  # Dashes not allowed
            "A" * 20 + ",1.0",  # Too long
        ]

        for invalid_content in invalid_names:
            with tempfile.NamedTemporaryFile(mode="w", suffix=".param", delete=False) as f:
                f.write(invalid_content)
                f.flush()

                # Act & Assert: Invalid names rejected
                with pytest.raises(SystemExit):
                    ParDict.load_param_file_into_dict(f.name)

            os.unlink(f.name)

    def test_parameter_validation_rejects_invalid_values(self) -> None:
        """
        Parameter validation rejects invalid parameter values.

        GIVEN: A user tries to load parameters with invalid values
        WHEN: The validation process checks parameter values
        THEN: Invalid values should be rejected with clear errors
        """
        # Arrange: Invalid parameter values
        invalid_content = "VALID_PARAM,not_a_number"

        with tempfile.NamedTemporaryFile(mode="w", suffix=".param", delete=False) as f:
            f.write(invalid_content)
            f.flush()

            # Act & Assert: Invalid values rejected
            with pytest.raises(SystemExit, match="Invalid parameter value"):
                ParDict.load_param_file_into_dict(f.name)

        os.unlink(f.name)
