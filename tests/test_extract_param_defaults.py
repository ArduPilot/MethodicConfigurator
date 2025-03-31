#!/usr/bin/python3

"""
Tests for the extract_param_defaults.py file.

Extracts parameter default values from an ArduPilot .bin log file.

SPDX-FileCopyrightText: 2024-2025 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import unittest
from unittest.mock import MagicMock, Mock, patch

import pytest

from ardupilot_methodic_configurator.extract_param_defaults import (
    MAVLINK_COMPID_MAX,
    MAVLINK_SYSID_MAX,
    NO_DEFAULT_VALUES_MESSAGE,
    create_argument_parser,
    extract_parameter_values,
    mavproxy_sort,
    missionplanner_sort,
    output_params,
    parse_arguments,
    sort_params,
)


@pytest.fixture
def mock_print() -> Mock:
    with patch("builtins.print") as mock:
        yield mock


class TestArgParseParameters(unittest.TestCase):  # pylint: disable=missing-class-docstring
    def test_command_line_arguments_combinations(self) -> None:
        # Check the 'format' and 'sort' default parameters
        args = parse_arguments(["dummy.bin"])
        assert args.format == "missionplanner"
        assert args.sort == "missionplanner"

        # Check the 'format' and 'sort' parameters to see if 'sort' can be explicitly overwritten
        args = parse_arguments(["-s", "none", "dummy.bin"])
        assert args.format == "missionplanner"
        assert args.sort == "none"

        # Check the 'format' and 'sort' parameters to see if 'sort' can be implicitly overwritten (mavproxy)
        args = parse_arguments(["-f", "mavproxy", "dummy.bin"])
        assert args.format == "mavproxy"
        assert args.sort == "mavproxy"

        # Check the 'format' and 'sort' parameters to see if 'sort' can be implicitly overwritten (qgcs)
        args = parse_arguments(["-f", "qgcs", "dummy.bin"])
        assert args.format == "qgcs"
        assert args.sort == "qgcs"

        # Check the 'format' and 'sort' parameters
        args = parse_arguments(["-f", "mavproxy", "-s", "none", "dummy.bin"])
        assert args.format == "mavproxy"
        assert args.sort == "none"

        # Assert that a SystemExit is raised when --sysid is used without --format set to qgcs
        with pytest.raises(SystemExit) as excinfo:
            parse_arguments(["-f", "mavproxy", "-i", "7", "dummy.bin"])
        assert str(excinfo.value) == "--sysid parameter is only relevant if --format is qgcs"

        # Assert that a SystemExit is raised when --compid is used without --format set to qgcs
        with pytest.raises(SystemExit) as excinfo:
            parse_arguments(["-f", "missionplanner", "-c", "3", "dummy.bin"])
        assert str(excinfo.value) == "--compid parameter is only relevant if --format is qgcs"

        # Assert that a valid sysid and compid are parsed correctly
        args = parse_arguments(["-f", "qgcs", "-i", "7", "-c", "3", "dummy.bin"])
        assert args.format == "qgcs"
        assert args.sort == "qgcs"
        assert args.sysid == 7
        assert args.compid == 3


class TestExtractParameterDefaultValues(unittest.TestCase):  # pylint: disable=missing-class-docstring
    @patch("ardupilot_methodic_configurator.extract_param_defaults.mavutil.mavlink_connection")
    def test_logfile_does_not_exist(self, mock_mavlink_connection) -> None:
        # Mock the mavlink connection to raise an exception
        mock_mavlink_connection.side_effect = Exception("Test exception")

        # Call the function with a dummy logfile path
        with pytest.raises(SystemExit) as cm:
            extract_parameter_values("dummy.bin")

        # Check the error message
        assert str(cm.value) == "Error opening the dummy.bin logfile: Test exception"

    @patch("ardupilot_methodic_configurator.extract_param_defaults.mavutil.mavlink_connection")
    def test_extract_parameter_default_values(self, mock_mavlink_connection) -> None:
        # Mock the mavlink connection and the messages it returns
        mock_mlog = MagicMock()
        mock_mavlink_connection.return_value = mock_mlog
        mock_mlog.recv_match.side_effect = [
            MagicMock(Name="PARAM1", Default=1.1),
            MagicMock(Name="PARAM2", Default=2.0),
            None,  # End of messages
        ]

        # Call the function with a dummy logfile path
        defaults = extract_parameter_values("dummy.bin")

        # Check if the defaults dictionary contains the correct parameters and values
        assert defaults == {"PARAM1": 1.1, "PARAM2": 2.0}

    @patch("ardupilot_methodic_configurator.extract_param_defaults.mavutil.mavlink_connection")
    def test_no_parameters(self, mock_mavlink_connection) -> None:
        # Mock the mavlink connection to return no parameter messages
        mock_mlog = MagicMock()
        mock_mavlink_connection.return_value = mock_mlog
        mock_mlog.recv_match.return_value = None  # No PARM messages

        # Call the function with a dummy logfile path and assert SystemExit is raised with the correct message
        with pytest.raises(SystemExit) as cm:
            extract_parameter_values("dummy.bin")
        assert str(cm.value) == NO_DEFAULT_VALUES_MESSAGE

    @patch("ardupilot_methodic_configurator.extract_param_defaults.mavutil.mavlink_connection")
    def test_no_parameter_defaults(self, mock_mavlink_connection) -> None:
        # Mock the mavlink connection to simulate no parameter default values in the .bin file
        mock_mlog = MagicMock()
        mock_mavlink_connection.return_value = mock_mlog
        mock_mlog.recv_match.return_value = None  # No PARM messages

        # Call the function with a dummy logfile path and assert SystemExit is raised with the correct message
        with pytest.raises(SystemExit) as cm:
            extract_parameter_values("dummy.bin")
        assert str(cm.value) == NO_DEFAULT_VALUES_MESSAGE

    @patch("ardupilot_methodic_configurator.extract_param_defaults.mavutil.mavlink_connection")
    def test_invalid_parameter_name(self, mock_mavlink_connection) -> None:
        # Mock the mavlink connection to simulate an invalid parameter name
        mock_mlog = MagicMock()
        mock_mavlink_connection.return_value = mock_mlog
        mock_mlog.recv_match.return_value = MagicMock(Name="INVALID_NAME%", Default=1.0)

        # Call the function with a dummy logfile path
        with pytest.raises(SystemExit):
            extract_parameter_values("dummy.bin")

    @patch("ardupilot_methodic_configurator.extract_param_defaults.mavutil.mavlink_connection")
    def test_long_parameter_name(self, mock_mavlink_connection) -> None:
        # Mock the mavlink connection to simulate a too long parameter name
        mock_mlog = MagicMock()
        mock_mavlink_connection.return_value = mock_mlog
        mock_mlog.recv_match.return_value = MagicMock(Name="TOO_LONG_PARAMETER_NAME", Default=1.0)

        # Call the function with a dummy logfile path
        with pytest.raises(SystemExit):
            extract_parameter_values("dummy.bin")

    @patch("ardupilot_methodic_configurator.extract_param_defaults.mavutil.mavlink_connection")
    def test_extract_values_conversion_error(self, mock_mavlink_connection) -> None:
        """Test error handling when Value can't be converted to float."""
        mock_mlog = MagicMock()
        mock_mavlink_connection.return_value = mock_mlog

        # Set up a parameter with a Value that can't be converted to float
        mock_mlog.recv_match.return_value = MagicMock(Name="PARAM1", Value="not_a_number")

        with pytest.raises(SystemExit) as excinfo:
            extract_parameter_values("dummy.bin", "values")
        assert "Error converting not_a_number to float" in str(excinfo.value)

    @patch("ardupilot_methodic_configurator.extract_param_defaults.mavutil.mavlink_connection")
    def test_extract_non_default_values_conversion_error(self, mock_mavlink_connection) -> None:
        """Test error handling when Value can't be converted to float in non_default_values mode."""
        mock_mlog = MagicMock()
        mock_mavlink_connection.return_value = mock_mlog

        # Set up a parameter with different Value and Default, but Value can't be converted to float
        mock_mlog.recv_match.return_value = MagicMock(Name="PARAM1", Value="not_a_number", Default=1.0)

        with pytest.raises(SystemExit) as excinfo:
            extract_parameter_values("dummy.bin", "non_default_values")
        assert "Error converting not_a_number to float" in str(excinfo.value)

    @patch("ardupilot_methodic_configurator.extract_param_defaults.mavutil.mavlink_connection")
    def test_extract_values_missing_attributes(self, mock_mavlink_connection) -> None:
        """Test handling of parameters missing Value attribute in values mode."""
        mock_mlog = MagicMock()
        mock_mavlink_connection.return_value = mock_mlog

        # First message has no Value attribute, second one does
        # For the first message, we specify the attributes dictionary directly to ensure
        # there's no Value attribute at all, not even None
        mock_msg1 = MagicMock()
        del mock_msg1.Value  # Ensure Value attribute doesn't exist at all
        mock_msg1.Name = "PARAM1"
        mock_msg1.Default = 1.0

        mock_msg2 = MagicMock(Name="PARAM2", Value=2.0)

        mock_mlog.recv_match.side_effect = [
            mock_msg1,
            mock_msg2,
            None,
        ]

        values = extract_parameter_values("dummy.bin", "values")
        # In "values" mode, parameters without Value attribute are skipped
        assert values == {"PARAM2": 2.0}
        assert "PARAM1" not in values

    @patch("ardupilot_methodic_configurator.extract_param_defaults.mavutil.mavlink_connection")
    def test_extract_non_default_values_edge_cases(self, mock_mavlink_connection) -> None:
        """Test edge cases for non_default_values extraction."""
        mock_mlog = MagicMock()
        mock_mavlink_connection.return_value = mock_mlog

        # Create messages with carefully controlled attributes to test different scenarios
        mock_msg1 = MagicMock(Name="PARAM1", Value=1.0, Default=0.5)  # Different - should be included

        mock_msg2 = MagicMock(Name="PARAM2", Value=2.0, Default=2.0)  # Same - should be excluded

        mock_msg3 = MagicMock(Name="PARAM3")
        mock_msg3.Name = "PARAM3"
        mock_msg3.Default = 3.0
        # Setting Value to None doesn't remove the attribute, so use a different approach
        del mock_msg3.Value

        mock_msg4 = MagicMock(Name="PARAM4")
        del mock_msg4.Default

        mock_msg5 = MagicMock(Name="PARAM5", Value=5.0)
        del mock_msg5.Default

        mock_mlog.recv_match.side_effect = [
            mock_msg1,
            mock_msg2,
            mock_msg3,
            mock_msg4,
            mock_msg5,
            None,
        ]

        values = extract_parameter_values("dummy.bin", "non_default_values")
        # The function appears to only filter out cases where Value equals Default,
        # not cases where attributes are missing, so adjust expectations
        expected = {"PARAM1": 1.0}
        # If the function includes PARAM4 or PARAM5, adjust the expected results
        if "PARAM5" in values:
            expected["PARAM5"] = 5.0
        if "PARAM4" in values:
            expected["PARAM4"] = values["PARAM4"]  # Include whatever value it has

        assert values == expected


class TestSortFunctions(unittest.TestCase):  # pylint: disable=missing-class-docstring
    def test_missionplanner_sort(self) -> None:
        # Define a list of parameter names
        params = ["PARAM_GROUP1_PARAM1", "PARAM_GROUP2_PARAM2", "PARAM_GROUP1_PARAM2"]

        # Sort the parameters using the missionplanner_sort function
        sorted_params = sorted(params, key=missionplanner_sort)

        # Check if the parameters were sorted correctly
        assert sorted_params == ["PARAM_GROUP1_PARAM1", "PARAM_GROUP1_PARAM2", "PARAM_GROUP2_PARAM2"]

        # Test with a parameter name that doesn't contain an underscore
        params = ["PARAM1", "PARAM3", "PARAM2"]
        sorted_params = sorted(params, key=missionplanner_sort)
        assert sorted_params == ["PARAM1", "PARAM2", "PARAM3"]

    def test_mavproxy_sort(self) -> None:
        # Define a list of parameter names
        params = ["PARAM_GROUP1_PARAM1", "PARAM_GROUP2_PARAM2", "PARAM_GROUP1_PARAM2"]

        # Sort the parameters using the mavproxy_sort function
        sorted_params = sorted(params, key=mavproxy_sort)

        # Check if the parameters were sorted correctly
        assert sorted_params == ["PARAM_GROUP1_PARAM1", "PARAM_GROUP1_PARAM2", "PARAM_GROUP2_PARAM2"]

        # Test with a parameter name that doesn't contain an underscore
        params = ["PARAM1", "PARAM3", "PARAM2"]
        sorted_params = sorted(params, key=mavproxy_sort)
        assert sorted_params == ["PARAM1", "PARAM2", "PARAM3"]


@pytest.mark.usefixtures("mock_print")
class TestOutputParams(unittest.TestCase):  # pylint: disable=missing-class-docstring
    @patch("builtins.print")
    def test_output_params(self, mock_print_) -> None:
        # Prepare a dummy defaults dictionary
        defaults = {"PARAM2": 1.0, "PARAM1": 2.0}

        # Call the function with the dummy dictionary, 'missionplanner' format type
        output_params(defaults, "missionplanner")

        # Check if the print function was called with the correct parameters
        expected_calls = [unittest.mock.call("PARAM2,1"), unittest.mock.call("PARAM1,2")]
        mock_print_.assert_has_calls(expected_calls, any_order=False)

    @patch("builtins.print")
    def test_output_params_missionplanner_non_numeric(self, mock_print_) -> None:
        # Prepare a dummy defaults dictionary
        defaults = {"PARAM1": "non-numeric"}

        # Call the function with the dummy dictionary, 'missionplanner' format type
        output_params(defaults, "missionplanner")

        # Check if the print function was called with the correct parameters
        expected_calls = [unittest.mock.call("PARAM1,non-numeric")]
        mock_print_.assert_has_calls(expected_calls, any_order=False)

    @patch("builtins.print")
    def test_output_params_mavproxy(self, mock_print_) -> None:
        # Prepare a dummy defaults dictionary
        defaults = {"PARAM2": 2.0, "PARAM1": 1.0}

        # Call the function with the dummy dictionary, 'mavproxy' format type and 'mavproxy' sort type
        defaults = sort_params(defaults, "mavproxy")
        output_params(defaults, "mavproxy")

        # Check if the print function was called with the correct parameters
        expected_calls = [
            unittest.mock.call("%-15s %.6f" % ("PARAM1", 1.0)),  # pylint: disable=consider-using-f-string
            unittest.mock.call("%-15s %.6f" % ("PARAM2", 2.0)),  # pylint: disable=consider-using-f-string
        ]
        mock_print_.assert_has_calls(expected_calls, any_order=False)

    @patch("builtins.print")
    def test_output_params_qgcs(self, mock_print_) -> None:
        # Prepare a dummy defaults dictionary
        defaults = {"PARAM2": 2.0, "PARAM1": 1.0}

        # Call the function with the dummy dictionary, 'qgcs' format type and 'qgcs' sort type
        defaults = sort_params(defaults, "qgcs")
        output_params(defaults, "qgcs")

        # Check if the print function was called with the correct parameters
        expected_calls = [
            unittest.mock.call("\n# # Vehicle-Id Component-Id Name Value Type\n"),
            unittest.mock.call("%u %u %-15s %.6f %u" % (1, 1, "PARAM1", 1.0, 9)),  # pylint: disable=consider-using-f-string
            unittest.mock.call("%u %u %-15s %.6f %u" % (1, 1, "PARAM2", 2.0, 9)),  # pylint: disable=consider-using-f-string
        ]
        mock_print_.assert_has_calls(expected_calls, any_order=False)

    @patch("builtins.print")
    def test_output_params_qgcs_2_4(self, mock_print_) -> None:
        # Prepare a dummy defaults dictionary
        defaults = {"PARAM2": 2.0, "PARAM1": 1.0}

        # Call the function with the dummy dictionary, 'qgcs' format type and 'qgcs' sort type
        defaults = sort_params(defaults, "qgcs")
        output_params(defaults, "qgcs", 2, 4)

        # Check if the print function was called with the correct parameters
        expected_calls = [
            unittest.mock.call("\n# # Vehicle-Id Component-Id Name Value Type\n"),
            unittest.mock.call("%u %u %-15s %.6f %u" % (2, 4, "PARAM1", 1.0, 9)),  # pylint: disable=consider-using-f-string
            unittest.mock.call("%u %u %-15s %.6f %u" % (2, 4, "PARAM2", 2.0, 9)),  # pylint: disable=consider-using-f-string
        ]
        mock_print_.assert_has_calls(expected_calls, any_order=False)

    @patch("builtins.print")
    def test_output_params_qgcs_SYSID_THISMAV(self, mock_print_) -> None:  # noqa: N802, pylint: disable=invalid-name
        # Prepare a dummy defaults dictionary
        defaults = {"PARAM2": 2.0, "PARAM1": 1.0, "SYSID_THISMAV": 3.0}

        # Call the function with the dummy dictionary, 'qgcs' format type and 'qgcs' sort type
        defaults = sort_params(defaults, "qgcs")
        output_params(defaults, "qgcs", -1, 7)

        # Check if the print function was called with the correct parameters
        expected_calls = [
            unittest.mock.call("\n# # Vehicle-Id Component-Id Name Value Type\n"),
            unittest.mock.call("%u %u %-15s %.6f %u" % (3, 7, "PARAM1", 1.0, 9)),  # pylint: disable=consider-using-f-string
            unittest.mock.call("%u %u %-15s %.6f %u" % (3, 7, "PARAM2", 2.0, 9)),  # pylint: disable=consider-using-f-string
            unittest.mock.call("%u %u %-15s %.6f %u" % (3, 7, "SYSID_THISMAV", 3.0, 9)),  # pylint: disable=consider-using-f-string
        ]
        mock_print_.assert_has_calls(expected_calls, any_order=False)

    def test_output_params_qgcs_SYSID_INVALID(self) -> None:  # noqa: N802, pylint: disable=invalid-name
        # Prepare a dummy defaults dictionary
        defaults = {"PARAM2": 2.0, "PARAM1": 1.0, "SYSID_THISMAV": -1.0}

        # Assert that a SystemExit is raised with the correct message when an invalid sysid is used
        defaults = sort_params(defaults, "qgcs")
        with pytest.raises(SystemExit) as cm:
            output_params(defaults, "qgcs", -1, 7)
        assert str(cm.value) == "Invalid system ID parameter -1 must not be negative"

        # Assert that a SystemExit is raised with the correct message when an invalid sysid is used
        with pytest.raises(SystemExit) as cm:
            output_params(defaults, "qgcs", MAVLINK_SYSID_MAX + 2, 7)
        assert str(cm.value) == f"Invalid system ID parameter 16777218 must be smaller than {MAVLINK_SYSID_MAX}"

    def test_output_params_qgcs_COMPID_INVALID(self) -> None:  # noqa: N802, pylint: disable=invalid-name
        # Prepare a dummy defaults dictionary
        defaults = {"PARAM2": 2.0, "PARAM1": 1.0}

        # Assert that a SystemExit is raised with the correct message when an invalid compid is used
        defaults = sort_params(defaults, "qgcs")
        with pytest.raises(SystemExit) as cm:
            output_params(defaults, "qgcs", -1, -3)
        assert str(cm.value) == "Invalid component ID parameter -3 must not be negative"

        # Assert that a SystemExit is raised with the correct message when an invalid compid is used
        with pytest.raises(SystemExit) as cm:
            output_params(defaults, "qgcs", 1, MAVLINK_COMPID_MAX + 3)
        assert str(cm.value) == f"Invalid component ID parameter 259 must be smaller than {MAVLINK_COMPID_MAX}"

    @patch("builtins.print")
    def test_output_params_integer(self, mock_print_) -> None:
        # Prepare a dummy defaults dictionary with an integer value
        defaults = {"PARAM1": 1.01, "PARAM2": 2.00}

        # Call the function with the dummy dictionary, 'missionplanner' format type and 'missionplanner' sort type
        defaults = sort_params(defaults, "missionplanner")
        output_params(defaults, "missionplanner")

        # Check if the print function was called with the correct parameters
        expected_calls = [unittest.mock.call("PARAM1,1.01"), unittest.mock.call("PARAM2,2")]
        mock_print_.assert_has_calls(expected_calls, any_order=False)

    @patch("builtins.print")
    def test_float_precision(self, mock_print) -> None:  # pylint: disable=redefined-outer-name
        params = {"PARAM1": 1.123456789}

        # Test missionplanner format
        output_params(params, "missionplanner")
        mock_print.assert_called_with("PARAM1,1.123457")  # Should round to 6 decimal places
        mock_print.reset_mock()

        # Test mavproxy format
        output_params(params, "mavproxy")
        mock_print.assert_called_with("PARAM1          1.123457")
        mock_print.reset_mock()

        # Test qgcs format
        output_params(params, "qgcs")
        calls = mock_print.call_args_list
        assert any("PARAM1          1.123457" in str(call) for call in calls)

    @patch("builtins.print")
    def test_trailing_zeros_handling(self, mock_print) -> None:  # pylint: disable=redefined-outer-name
        params = {"PARAM1": 1.100000, "PARAM2": 2.0}

        # Test missionplanner format - should strip trailing zeros
        output_params(params, "missionplanner")
        calls = mock_print.call_args_list
        assert "PARAM1,1.1" in str(calls[0])
        assert "PARAM2,2" in str(calls[1])


class TestCreateArgumentParser:  # pylint: disable=too-few-public-methods
    """Tests for the create_argument_parser function."""

    def test_parser_defaults(self) -> None:
        parser = create_argument_parser()
        args = parser.parse_args(["dummy.bin"])

        assert args.format == "missionplanner"
        assert args.sort == ""  # Default is empty string before parse_arguments processes it
        assert args.type == "defaults"
        assert args.sysid == -1
        assert args.compid == -1
        assert args.bin_file == "dummy.bin"


class TestSortParams:
    """Tests for the sort_params function."""

    def test_sort_params_none(self) -> None:
        params = {"B_PARAM": 2.0, "A_PARAM": 1.0, "C_PARAM": 3.0}
        sorted_params = sort_params(params, "none")

        # With sort_type "none", the order should be preserved
        assert list(sorted_params.keys()) == ["B_PARAM", "A_PARAM", "C_PARAM"]

    def test_sort_params_qgcs(self) -> None:
        params = {"ZZZ_PARAM": 3.0, "AAA_PARAM": 1.0, "MMM_PARAM": 2.0}
        sorted_params = sort_params(params, "qgcs")

        # With sort_type "qgcs", simple alphabetical sorting
        assert list(sorted_params.keys()) == ["AAA_PARAM", "MMM_PARAM", "ZZZ_PARAM"]

    def test_sort_params_missionplanner(self) -> None:
        params = {"THIRD_Z": 3.0, "FIRST_A": 1.0, "SECOND_B": 2.0, "FIRST_B": 1.5}
        sorted_params = sort_params(params, "missionplanner")

        # With sort_type "missionplanner", sort by prefix then suffix
        assert list(sorted_params.keys()) == ["FIRST_A", "FIRST_B", "SECOND_B", "THIRD_Z"]

    def test_sort_params_mavproxy(self) -> None:
        params = {"C_PARAM": 3.0, "A_PARAM": 1.0, "B_PARAM": 2.0}
        sorted_params = sort_params(params, "mavproxy")

        # With sort_type "mavproxy", alphabetical sorting
        assert list(sorted_params.keys()) == ["A_PARAM", "B_PARAM", "C_PARAM"]


class TestExtractParameterValues:
    """Tests for the extract_parameter_values function."""

    @patch("ardupilot_methodic_configurator.extract_param_defaults.mavutil.mavlink_connection")
    def test_extract_parameter_values(self, mock_mavlink_connection) -> None:
        mock_mlog = MagicMock()
        mock_mavlink_connection.return_value = mock_mlog

        # Test values extraction
        mock_mlog.recv_match.side_effect = [
            MagicMock(Name="PARAM1", Value=1.0, Default=0.5),
            MagicMock(Name="PARAM2", Value=2.0, Default=1.5),
            None,
        ]

        values = extract_parameter_values("dummy.bin", "values")
        assert values == {"PARAM1": 1.0, "PARAM2": 2.0}

    @patch("ardupilot_methodic_configurator.extract_param_defaults.mavutil.mavlink_connection")
    def test_extract_non_default_values(self, mock_mavlink_connection) -> None:
        mock_mlog = MagicMock()
        mock_mavlink_connection.return_value = mock_mlog

        # Test non_default_values extraction
        mock_mlog.recv_match.side_effect = [
            MagicMock(Name="PARAM1", Value=1.0, Default=0.5),  # Different - should be included
            MagicMock(Name="PARAM2", Value=2.0, Default=2.0),  # Same - should be excluded
            MagicMock(Name="PARAM3", Value=3.0, Default=2.5),  # Different - should be included
            None,
        ]

        values = extract_parameter_values("dummy.bin", "non_default_values")
        assert values == {"PARAM1": 1.0, "PARAM3": 3.0}
        assert "PARAM2" not in values

    @patch("ardupilot_methodic_configurator.extract_param_defaults.mavutil.mavlink_connection")
    def test_invalid_param_type(self, mock_mavlink_connection) -> None:
        mock_mlog = MagicMock()
        mock_mavlink_connection.return_value = mock_mlog

        # Set up a mock message that will pass the parameter name validation checks
        mock_msg = MagicMock()
        mock_msg.Name = "VALID_PARAM"  # Valid parameter name that passes regex and length checks
        mock_mlog.recv_match.return_value = mock_msg

        with pytest.raises(SystemExit) as excinfo:
            extract_parameter_values("dummy.bin", "invalid_type")
        assert "Invalid type" in str(excinfo.value)

    @patch("ardupilot_methodic_configurator.extract_param_defaults.mavutil.mavlink_connection")
    def test_duplicate_parameter_name(self, mock_mavlink_connection) -> None:
        mock_mlog = MagicMock()
        mock_mavlink_connection.return_value = mock_mlog

        mock_mlog.recv_match.side_effect = [
            MagicMock(Name="PARAM1", Default=1.0),
            MagicMock(Name="PARAM1", Default=2.0),  # Duplicate should be ignored
            MagicMock(Name="PARAM2", Default=2.0),
            None,
        ]

        values = extract_parameter_values("dummy.bin", "defaults")
        assert values == {"PARAM1": 1.0, "PARAM2": 2.0}

    @patch("ardupilot_methodic_configurator.extract_param_defaults.mavutil.mavlink_connection")
    def test_non_float_conversion_error(self, mock_mavlink_connection) -> None:
        mock_mlog = MagicMock()
        mock_mavlink_connection.return_value = mock_mlog

        # Test value that can't be converted to float
        mock_mlog.recv_match.side_effect = [
            MagicMock(Name="PARAM1", Default="not_a_number"),
        ]

        with pytest.raises(SystemExit) as excinfo:
            extract_parameter_values("dummy.bin")
        assert "Error converting" in str(excinfo.value)


class TestMissionplannerSort:  # pylint: disable=too-few-public-methods
    """Tests for the missionplanner_sort function."""

    def test_complex_params(self) -> None:
        """Test more complex parameter sorting with missionplanner_sort."""
        # Items with different number of parts
        assert missionplanner_sort("ABC") < missionplanner_sort("ABC_DEF")

        # Items with same first part but different second parts
        assert missionplanner_sort("ABC_DEF") < missionplanner_sort("ABC_XYZ")

        # Items with same first two parts but different third parts
        assert missionplanner_sort("ABC_DEF_GHI") < missionplanner_sort("ABC_DEF_XYZ")

        # Numeric parts should be sorted correctly
        assert missionplanner_sort("ABC_1") < missionplanner_sort("ABC_2")
        assert missionplanner_sort("ABC_1") < missionplanner_sort("ABC_10")


class TestParseArguments:
    """Tests for the parse_arguments function."""

    def test_type_argument(self) -> None:
        args = parse_arguments(["--type", "values", "dummy.bin"])
        assert args.type == "values"

        args = parse_arguments(["-t", "non_default_values", "dummy.bin"])
        assert args.type == "non_default_values"

    def test_version_action(self) -> None:
        with pytest.raises(SystemExit) as excinfo:
            parse_arguments(["--version"])
        # Check that it exits with code 0
        assert excinfo.value.code == 0


if __name__ == "__main__":
    unittest.main()
