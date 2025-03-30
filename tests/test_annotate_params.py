#!/usr/bin/python3

"""
Tests for the annotate_params.py script.

These are the unit tests for the python script that fetches online ArduPilot
parameter documentation (if not cached) and adds it to the specified file or
to all *.param and *.parm files in the specified directory.

SPDX-FileCopyrightText: 2024-2025 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import contextlib
import os
import tempfile
import unittest
from unittest import mock
from unittest.mock import patch
from xml.etree import ElementTree as ET  # no parsing, just data-structure manipulation

import pytest
import requests  # type: ignore[import-untyped]
from defusedxml import ElementTree as DET  # noqa: N814, just parsing, no data-structure manipulation

from ardupilot_methodic_configurator.annotate_params import (
    BASE_URL,
    PARAM_DEFINITION_XML_FILE,
    Par,
    create_doc_dict,
    extract_parameter_name_and_validate,
    format_columns,
    get_env_proxies,
    get_xml_data,
    get_xml_url,
    main,
    missionplanner_sort,
    parse_arguments,
    print_read_only_params,
    remove_prefix,
    split_into_lines,
    update_parameter_documentation,
)

# pylint: disable=too-many-lines


@pytest.fixture
def mock_update() -> mock.Mock:
    with patch("ardupilot_methodic_configurator.annotate_params.update_parameter_documentation") as mock_fun:
        yield mock_fun


@pytest.fixture
def mock_get_xml_dir() -> mock.Mock:
    with patch("ardupilot_methodic_configurator.annotate_params.get_xml_dir") as mock_fun:
        yield mock_fun


@pytest.fixture
def mock_get_xml_url() -> mock.Mock:
    with patch("ardupilot_methodic_configurator.annotate_params.get_xml_url") as mock_fun:
        yield mock_fun


class TestParamDocsUpdate(unittest.TestCase):  # pylint: disable=missing-class-docstring, too-many-public-methods
    def setUp(self) -> None:
        # Create a temporary directory
        self.temp_dir = tempfile.mkdtemp()

        # Create a temporary file
        # pylint: disable=consider-using-with
        self.temp_file = tempfile.NamedTemporaryFile(delete=False)  # noqa: SIM115
        # pylint: enable=consider-using-with

        # Create a dictionary of parameter documentation
        self.doc_dict = {
            "PARAM1": {
                "humanName": "Param 1",
                "documentation": ["Documentation for Param 1"],
                "fields": {"Field1": "Value1", "Field2": "Value2"},
                "values": {"Code1": "Value1", "Code2": "Value2"},
            },
            "PARAM2": {
                "humanName": "Param 2",
                "documentation": ["Documentation for Param 2"],
                "fields": {"Field3": "Value3", "Field4": "Value4"},
                "values": {"Code3": "Value3", "Code4": "Value4"},
            },
            "PARAM_1": {
                "humanName": "Param _ 1",
                "documentation": ["Documentation for Param_1"],
                "fields": {"Field_1": "Value_1", "Field_2": "Value_2"},
                "values": {"Code_1": "Value_1", "Code_2": "Value_2"},
            },
        }

    @patch("builtins.open", new_callable=mock.mock_open, read_data="<root></root>")
    @patch("os.path.isfile")
    @patch("ardupilot_methodic_configurator.annotate_params.Par.load_param_file_into_dict")
    def test_get_xml_data_local_file(self, mock_load_param, mock_isfile, mock_open_) -> None:
        # Mock the isfile function to return True
        mock_isfile.return_value = True

        # Mock the load_param_file_into_dict function to raise FileNotFoundError
        mock_load_param.side_effect = FileNotFoundError

        # Call the function with a local file
        result = get_xml_data("/path/to/local/file/", ".", "test.xml", "ArduCopter")

        # Check the result
        assert isinstance(result, ET.Element)

        # Assert that the file was opened correctly
        mock_open_.assert_called_once_with(os.path.join(".", "test.xml"), encoding="utf-8")

    @patch("requests.get")
    def test_get_xml_data_remote_file(self, mock_get) -> None:
        # Mock the response
        mock_get.return_value.status_code = 200
        mock_get.return_value.text = "<root></root>"

        # Remove the test.xml file if it exists
        with contextlib.suppress(FileNotFoundError):
            os.remove("test.xml")

        # Call the function with a remote file
        result = get_xml_data("http://example.com/", ".", "test.xml", "ArduCopter")

        # Check the result
        assert isinstance(result, ET.Element)

        # Assert that the requests.get function was called once
        mock_get.assert_called_once_with("http://example.com/test.xml", timeout=5)

    @patch("os.path.isfile")
    @patch("ardupilot_methodic_configurator.annotate_params.Par.load_param_file_into_dict")
    def test_get_xml_data_script_dir_file(self, mock_load_param, mock_isfile) -> None:
        # Mock the isfile function to return False for the current directory and True for the script directory
        def side_effect(_filename) -> bool:
            return True

        mock_isfile.side_effect = side_effect

        # Mock the load_param_file_into_dict function to raise FileNotFoundError
        mock_load_param.side_effect = FileNotFoundError

        # Mock the open function to return a dummy XML string
        mock_open = mock.mock_open(read_data="<root></root>")
        with patch("builtins.open", mock_open):
            # Call the function with a filename that exists in the script directory
            result = get_xml_data(BASE_URL, ".", PARAM_DEFINITION_XML_FILE, "ArduCopter")

        # Check the result
        assert isinstance(result, ET.Element)

        # Assert that the file was opened correctly
        mock_open.assert_called_once_with(os.path.join(".", PARAM_DEFINITION_XML_FILE), encoding="utf-8")

    def test_get_xml_data_no_requests_package(self) -> None:
        # Temporarily remove the requests module
        with patch.dict("sys.modules", {"requests": None}):
            # Remove the test.xml file if it exists
            with contextlib.suppress(FileNotFoundError):
                os.remove("test.xml")

            # Call the function with a remote file
            with pytest.raises(SystemExit):
                get_xml_data("http://example.com/", ".", "test.xml", "ArduCopter")

    @patch("requests.get")
    def test_get_xml_data_request_failure(self, mock_get) -> None:
        # Mock the response
        mock_get.side_effect = requests.exceptions.RequestException

        # Remove the test.xml file if it exists
        with contextlib.suppress(FileNotFoundError):
            os.remove("test.xml")

        # Call the function with a remote file
        with pytest.raises(SystemExit):
            get_xml_data("http://example.com/", ".", "test.xml", "ArduCopter")

    @patch("requests.get")
    def test_get_xml_data_valid_xml(self, mock_get) -> None:
        # Mock the response
        mock_get.return_value.status_code = 200
        mock_get.return_value.text = "<root></root>"

        # Call the function with a remote file
        result = get_xml_data("http://example.com/", ".", "test.xml", "ArduCopter")

        # Check the result
        assert isinstance(result, ET.Element)

    @patch("requests.get")
    def test_get_xml_data_invalid_xml(self, mock_get) -> None:
        # Mock the response
        mock_get.return_value.status_code = 200
        mock_get.return_value.text = "<root><invalid></root>"

        # Remove the test.xml file if it exists
        with contextlib.suppress(FileNotFoundError):
            os.remove("test.xml")

        # Call the function with a remote file
        with pytest.raises(ET.ParseError):
            get_xml_data("http://example.com/", ".", "test.xml", "ArduCopter")

    @patch("requests.get")
    @patch("os.path.isfile")
    def test_get_xml_data_missing_file(self, mock_isfile, mock_get) -> None:
        # Mock the isfile function to return False
        mock_isfile.return_value = False
        # Mock the requests.get call to raise FileNotFoundError
        mock_get.side_effect = FileNotFoundError

        # Remove the test.xml file if it exists
        with contextlib.suppress(FileNotFoundError):
            os.remove("test.xml")

        # Call the function with a local file
        with pytest.raises(FileNotFoundError):
            get_xml_data("/path/to/local/file/", ".", "test.xml", "ArduCopter")

    @patch("requests.get")
    def test_get_xml_data_network_issue(self, mock_get) -> None:
        # Mock the response
        mock_get.side_effect = requests.exceptions.ConnectionError

        # Call the function with a remote file
        with pytest.raises(SystemExit):
            get_xml_data("http://example.com/", ".", "test.xml", "ArduCopter")

    def test_remove_prefix(self) -> None:
        # Test case 1: Normal operation
        assert remove_prefix("prefix_test", "prefix_") == "test"

        # Test case 2: Prefix not present
        assert remove_prefix("test", "prefix_") == "test"

        # Test case 3: Empty string
        assert remove_prefix("", "prefix_") == ""

    def test_split_into_lines(self) -> None:
        # Test case 1: Normal operation
        string_to_split = "This is a test string. It should be split into several lines."
        maximum_line_length = 12
        expected_output = ["This is a", "test string.", "It should be", "split into", "several", "lines."]
        assert split_into_lines(string_to_split, maximum_line_length) == expected_output

        # Test case 2: String shorter than maximum line length
        string_to_split = "Short"
        maximum_line_length = 10
        expected_output = ["Short"]
        assert split_into_lines(string_to_split, maximum_line_length) == expected_output

        # Test case 3: Empty string
        string_to_split = ""
        maximum_line_length = 10
        expected_output = []
        assert split_into_lines(string_to_split, maximum_line_length) == expected_output

    def test_create_doc_dict(self) -> None:
        # Mock XML data
        xml_data = """
        <root>
            <param name="PARAM1" humanName="Param 1" documentation="Documentation for Param 1">
                <field name="Field1">Value1</field>
                <field name="Field2">Value2</field>
                <values>
                    <value code="Code1">Value1</value>
                    <value code="Code2">Value2</value>
                </values>
            </param>
            <param name="PARAM2" humanName="Param 2" documentation="Documentation for Param 2">
                <field name="Units">m/s</field>
                <field name="UnitText">meters per second</field>
                <values>
                    <value code="Code3">Value3</value>
                    <value code="Code4">Value4</value>
                </values>
            </param>
        </root>
        """
        root = DET.fromstring(xml_data)

        # Expected output
        expected_output = {
            "PARAM1": {
                "humanName": "Param 1",
                "documentation": ["Documentation for Param 1"],
                "fields": {"Field1": "Value1", "Field2": "Value2"},
                "values": {"Code1": "Value1", "Code2": "Value2"},
            },
            "PARAM2": {
                "humanName": "Param 2",
                "documentation": ["Documentation for Param 2"],
                "fields": {"Units": "m/s (meters per second)"},
                "values": {"Code3": "Value3", "Code4": "Value4"},
            },
        }

        # Call the function with the mock XML data
        result = create_doc_dict(root, "VehicleType")

        # Check the result
        assert result == expected_output

    def test_format_columns(self) -> None:
        # Define the input
        values = {
            "Key1": "Value1",
            "Key2": "Value2",
            "Key3": "Value3",
            "Key4": "Value4",
            "Key5": "Value5",
            "Key6": "Value6",
            "Key7": "Value7",
            "Key8": "Value8",
            "Key9": "Value9",
            "Key10": "Value10",
            "Key11": "Value11",
            "Key12": "Value12",
        }

        # Define the expected output
        expected_output = [
            "Key1: Value1                                         Key7: Value7",
            "Key2: Value2                                         Key8: Value8",
            "Key3: Value3                                         Key9: Value9",
            "Key4: Value4                                         Key10: Value10",
            "Key5: Value5                                         Key11: Value11",
            "Key6: Value6                                         Key12: Value12",
        ]

        # Call the function with the input
        result = format_columns(values)

        # Check the result
        assert result == expected_output

        assert not format_columns({})

    def test_update_parameter_documentation(self) -> None:
        # Write some initial content to the temporary file
        with open(self.temp_file.name, "w", encoding="utf-8") as file:
            file.write("PARAM1 100\n")

        # Call the function with the temporary file
        update_parameter_documentation(self.doc_dict, self.temp_file.name)

        # Read the updated content from the temporary file
        with open(self.temp_file.name, encoding="utf-8") as file:
            updated_content = file.read()

        # Check if the file has been updated correctly
        assert "Param 1" in updated_content
        assert "Documentation for Param 1" in updated_content
        assert "Field1: Value1" in updated_content
        assert "Field2: Value2" in updated_content
        assert "Code1: Value1" in updated_content
        assert "Code2: Value2" in updated_content

    def test_update_parameter_documentation_sorting_none(self) -> None:
        # Write some initial content to the temporary file
        # With stray leading and trailing whitespaces
        with open(self.temp_file.name, "w", encoding="utf-8") as file:
            file.write("PARAM2 100\n PARAM_1 100 \nPARAM3 3\nPARAM4 4\nPARAM5 5\nPARAM1 100\n")

        # Call the function with the temporary file
        update_parameter_documentation(self.doc_dict, self.temp_file.name)

        # Read the updated content from the temporary file
        with open(self.temp_file.name, encoding="utf-8") as file:
            updated_content = file.read()

        expected_content = """# Param 2
# Documentation for Param 2
# Field3: Value3
# Field4: Value4
# Code3: Value3
# Code4: Value4
PARAM2 100

# Param _ 1
# Documentation for Param_1
# Field_1: Value_1
# Field_2: Value_2
# Code_1: Value_1
# Code_2: Value_2
PARAM_1 100
PARAM3 3
PARAM4 4
PARAM5 5

# Param 1
# Documentation for Param 1
# Field1: Value1
# Field2: Value2
# Code1: Value1
# Code2: Value2
PARAM1 100
"""
        assert updated_content == expected_content

    def test_update_parameter_documentation_sorting_missionplanner(self) -> None:
        # Write some initial content to the temporary file
        with open(self.temp_file.name, "w", encoding="utf-8") as file:
            file.write("PARAM2 100 # ignore, me\nPARAM_1\t100\nPARAM1,100\n")

        # Call the function with the temporary file
        update_parameter_documentation(self.doc_dict, self.temp_file.name, "missionplanner")

        # Read the updated content from the temporary file
        with open(self.temp_file.name, encoding="utf-8") as file:
            updated_content = file.read()

        expected_content = """# Param _ 1
# Documentation for Param_1
# Field_1: Value_1
# Field_2: Value_2
# Code_1: Value_1
# Code_2: Value_2
PARAM_1\t100

# Param 1
# Documentation for Param 1
# Field1: Value1
# Field2: Value2
# Code1: Value1
# Code2: Value2
PARAM1,100

# Param 2
# Documentation for Param 2
# Field3: Value3
# Field4: Value4
# Code3: Value3
# Code4: Value4
PARAM2 100 # ignore, me
"""
        assert updated_content == expected_content

    def test_update_parameter_documentation_sorting_mavproxy(self) -> None:
        # Write some initial content to the temporary file
        with open(self.temp_file.name, "w", encoding="utf-8") as file:
            file.write("PARAM2 100\nPARAM_1\t100\nPARAM1,100\n")

        # Call the function with the temporary file
        update_parameter_documentation(self.doc_dict, self.temp_file.name, "mavproxy")

        # Read the updated content from the temporary file
        with open(self.temp_file.name, encoding="utf-8") as file:
            updated_content = file.read()

        expected_content = """# Param 1
# Documentation for Param 1
# Field1: Value1
# Field2: Value2
# Code1: Value1
# Code2: Value2
PARAM1,100

# Param 2
# Documentation for Param 2
# Field3: Value3
# Field4: Value4
# Code3: Value3
# Code4: Value4
PARAM2 100

# Param _ 1
# Documentation for Param_1
# Field_1: Value_1
# Field_2: Value_2
# Code_1: Value_1
# Code_2: Value_2
PARAM_1\t100
"""
        assert updated_content == expected_content

    def test_update_parameter_documentation_invalid_line_format(self) -> None:
        # Write some initial content to the temporary file with an invalid line format
        with open(self.temp_file.name, "w", encoding="utf-8") as file:
            file.write("%INVALID_LINE_FORMAT\n")

        # Call the function with the temporary file
        with pytest.raises(SystemExit) as cm:
            update_parameter_documentation(self.doc_dict, self.temp_file.name)

        # Check if the SystemExit exception contains the expected message
        assert cm.value.code == "Invalid line in input file"

    @patch("logging.Logger.info")
    def test_print_read_only_params(self, mock_info) -> None:
        # Mock XML data
        xml_data = """
        <root>
            <param name="PARAM1" humanName="Param 1" documentation="Documentation for Param 1">
                <field name="ReadOnly">True</field>
                <field name="Field1">Value1</field>
                <field name="Field2">Value2</field>
                <values>
                    <value code="Code1">Value1</value>
                    <value code="Code2">Value2</value>
                </values>
            </param>
            <param name="PARAM2" humanName="Param 2" documentation="Documentation for Param 2">
                <field name="Field3">Value3</field>
                <field name="Field4">Value4</field>
                <values>
                    <value code="Code3">Value3</value>
                    <value code="Code4">Value4</value>
                </values>
            </param>
        </root>
        """
        root = DET.fromstring(xml_data)
        doc_dict = create_doc_dict(root, "VehicleType")

        # Call the function with the mock XML data
        print_read_only_params(doc_dict)

        # Check if the parameter name was logged
        mock_info.assert_has_calls([mock.call("ReadOnly parameters:"), mock.call("PARAM1")])

    def test_update_parameter_documentation_invalid_target(self) -> None:
        with pytest.raises(ValueError, match="Target 'invalid_target' is neither a file nor a directory."):
            update_parameter_documentation(self.doc_dict, "invalid_target")

    def test_invalid_parameter_name(self) -> None:
        # Write some initial content to the temporary file
        with open(self.temp_file.name, "w", encoding="utf-8") as file:
            file.write("INVALID_$PARAM 100\n")

        # Call the function with the temporary file
        with pytest.raises(SystemExit):
            update_parameter_documentation(self.doc_dict, self.temp_file.name)

    def test_update_parameter_documentation_too_long_parameter_name(self) -> None:
        # Write some initial content to the temporary file
        with open(self.temp_file.name, "w", encoding="utf-8") as file:
            file.write("TOO_LONG_PARAMETER_NAME 100\n")

        # Call the function with the temporary file
        with pytest.raises(SystemExit):
            update_parameter_documentation(self.doc_dict, self.temp_file.name)

    @patch("logging.Logger.warning")
    def test_missing_parameter_documentation(self, mock_warning) -> None:
        # Write some initial content to the temporary file
        with open(self.temp_file.name, "w", encoding="utf-8") as file:
            file.write("MISSING_DOC_PARA 100\n")

        # Call the function with the temporary file
        update_parameter_documentation(self.doc_dict, self.temp_file.name)

        # Check if the warnings were logged
        mock_warning.assert_has_calls(
            [
                mock.call("Read file %s with %d parameters, but only %s of which got documented", self.temp_file.name, 1, 0),
                mock.call("No documentation found for: %s", "MISSING_DOC_PARA"),
            ]
        )

    def test_empty_parameter_file(self) -> None:
        # Call the function with the temporary file
        update_parameter_documentation(self.doc_dict, self.temp_file.name)

        # Read the updated content from the temporary file
        with open(self.temp_file.name, encoding="utf-8") as file:
            updated_content = file.read()

        # Check if the file is still empty
        assert updated_content == ""

    def test_get_xml_url_valid_vehicles(self) -> None:
        """Test get_xml_url with all valid vehicle types."""
        vehicle_types = ["ArduCopter", "ArduPlane", "Rover", "ArduSub", "AntennaTracker", "AP_Periph", "Blimp", "Heli", "SITL"]
        for vehicle in vehicle_types:
            url = get_xml_url(vehicle, "4.3")
            assert url.startswith(BASE_URL)
            assert "stable-4.3" in url
            assert url.endswith("/")

    def test_get_xml_url_invalid_vehicle(self) -> None:
        """Test get_xml_url with invalid vehicle type."""
        with pytest.raises(ValueError, match="Vehicle type 'InvalidVehicle' is not supported."):
            get_xml_url("InvalidVehicle", "4.3")

    def test_split_into_lines_edge_cases(self) -> None:
        """Test split_into_lines with edge cases."""
        # Test with various line lengths
        # Function will return largest possible chunks based on max length
        assert split_into_lines("a b c", 2) == ["a", "b", "c"]
        assert split_into_lines("", 10) == []

    def test_format_columns_edge_cases(self) -> None:
        """Test format_columns with edge cases."""
        # Empty dictionary
        assert not format_columns({})

        # Single item
        assert format_columns({"Key": "Value"}) == ["Key: Value"]

        # Test with different max widths
        values = {"K1": "V1", "K2": "V2"}
        assert len(format_columns(values, max_width=20)[0]) <= 20

        # Test with many columns
        many_values = {f"Key{i}": f"Value{i}" for i in range(20)}
        result = format_columns(many_values, max_width=200, max_columns=5)
        assert all(len(line) <= 200 for line in result)

    def test_create_doc_dict_edge_cases(self) -> None:
        """Test create_doc_dict with edge cases."""
        # Test with empty XML
        empty_root = ET.Element("root")
        assert not create_doc_dict(empty_root, "ArduCopter")

        # Test with missing attributes
        param = ET.SubElement(empty_root, "param")
        assert not create_doc_dict(empty_root, "ArduCopter")

        # Test with minimal valid param
        param.set("name", "TEST_PARAM")
        param.set("humanName", "Test Parameter")
        param.set("documentation", "Test documentation")
        doc_dict = create_doc_dict(empty_root, "ArduCopter")
        assert "TEST_PARAM" in doc_dict
        assert doc_dict["TEST_PARAM"]["humanName"] == "Test Parameter"

    @patch("os.path.isfile")
    def test_update_parameter_documentation_sorting(self, mock_isfile) -> None:
        """Test parameter sorting in update_parameter_documentation."""
        # Mock file existence check
        mock_isfile.return_value = True

        test_content = "PARAM_Z 100\nPARAM_A 200\nPARAM_M 300\n"

        # Create a real temporary file for testing
        with tempfile.NamedTemporaryFile(mode="w", delete=False) as temp_file:
            temp_file.write(test_content)
            temp_file_name = temp_file.name

        doc = {
            "PARAM_Z": {"humanName": "Z", "documentation": ["Z doc"], "fields": {}, "values": {}},
            "PARAM_A": {"humanName": "A", "documentation": ["A doc"], "fields": {}, "values": {}},
            "PARAM_M": {"humanName": "M", "documentation": ["M doc"], "fields": {}, "values": {}},
        }

        try:
            # Test MissionPlanner sorting
            update_parameter_documentation(doc, temp_file_name, "missionplanner")

            with open(temp_file_name, encoding="utf-8") as f:
                content = f.read()

            # Verify content and order
            assert "PARAM_A" in content
            assert "PARAM_M" in content
            assert "PARAM_Z" in content
            assert content.index("PARAM_A") < content.index("PARAM_M") < content.index("PARAM_Z")

            # Test MAVProxy sorting
            # Reset file content
            with open(temp_file_name, "w", encoding="utf-8") as f:
                f.write(test_content)

            update_parameter_documentation(doc, temp_file_name, "mavproxy")

            with open(temp_file_name, encoding="utf-8") as f:
                content = f.read()

            # Verify content for MAVProxy format
            assert "PARAM_A" in content
            assert "PARAM_M" in content
            assert "PARAM_Z" in content

        finally:
            # Clean up
            os.unlink(temp_file_name)

    def test_extract_parameter_name_and_validate_invalid_cases(self) -> None:
        """Test parameter name validation with invalid cases."""
        # Test invalid parameter name pattern
        with pytest.raises(SystemExit):
            extract_parameter_name_and_validate("invalid_param 100", "test.param", 1)

        # Test too long parameter name
        with pytest.raises(SystemExit):
            extract_parameter_name_and_validate("VERY_LONG_PARAMETER_NAME_THAT_EXCEEDS_LIMIT 100", "test.param", 1)

        # Test invalid separator
        with pytest.raises(SystemExit):
            extract_parameter_name_and_validate("PARAM:100", "test.param", 1)

    def test_par_class_methods(self) -> None:
        """Test Par class methods."""
        # Test equality
        par1 = Par(100.0, "comment1")
        par2 = Par(100.0, "comment1")
        par3 = Par(200.0, "comment2")

        assert par1 == par2
        assert par1 != par3
        assert par1 != "not a Par object"

        # Test load_param_file with invalid values
        with tempfile.NamedTemporaryFile(mode="w", delete=False) as tf:
            tf.write("PARAM1 invalid_value\n")
            tf.flush()

            with pytest.raises(SystemExit):
                Par.load_param_file_into_dict(tf.name)

    def test_format_params_methods(self) -> None:
        """Test Par.format_params method."""
        param_dict = {"PARAM1": Par(100.0, "comment1"), "PARAM2": Par(200.0), "PARAM3": 300.0}

        # Test MissionPlanner format
        mp_format = Par.format_params(param_dict, "missionplanner")
        assert any("PARAM1,100" in line for line in mp_format)
        assert any("# comment1" in line for line in mp_format)

        # Test MAVProxy format
        mavproxy_format = Par.format_params(param_dict, "mavproxy")
        # Use correct spacing format - 16 chars for name, 8 for value
        assert any("PARAM1           100.000000" in line for line in mavproxy_format)
        assert any("# comment1" in line for line in mavproxy_format)

        # Test invalid format
        with pytest.raises(SystemExit):
            Par.format_params(param_dict, "invalid_format")


class AnnotateParamsTest(unittest.TestCase):
    """Test annotate parameters."""

    def test_arg_parser_valid_arguments(self) -> None:
        test_args = ["annotate_params", "--vehicle-type", "ArduCopter", "--sort", "none", "parameters"]
        with patch("sys.argv", test_args):
            args = parse_arguments()
            assert args.vehicle_type == "ArduCopter"
            assert args.sort == "none"
            assert args.target == "parameters"
            assert args.verbose is False
            assert args.max_line_length == 100

    def test_arg_parser_invalid_vehicle_type(self) -> None:
        test_args = ["annotate_params", "--vehicle-type", "InvalidType", "--sort", "none", "parameters"]
        with patch("sys.argv", test_args), pytest.raises(SystemExit):
            parse_arguments()

    def test_arg_parser_invalid_sort_option(self) -> None:
        test_args = ["annotate_params", "--vehicle-type", "ArduCopter", "--sort", "invalid", "parameters"]
        with patch("sys.argv", test_args), pytest.raises(SystemExit):
            parse_arguments()

    def test_arg_parser_invalid_line_length_option(self) -> None:
        test_args = ["annotate_params", "--vehicle-type", "ArduCopter", "--sort", "none", "-m", "invalid", "parameters"]
        with patch("sys.argv", test_args), pytest.raises(SystemExit):
            parse_arguments()


class TestAnnotateParamsExceptionHandling(unittest.TestCase):
    """Test parameter exception handling."""

    @pytest.mark.usefixtures("mock_update", "mock_get_xml_dir", "mock_get_xml_url")
    @patch("builtins.open", new_callable=mock.mock_open)
    def test_main_ioerror(self, mock_file) -> None:
        with patch("ardupilot_methodic_configurator.annotate_params.parse_arguments") as mock_arg_parser:
            mock_arg_parser.return_value = mock.Mock(
                vehicle_type="ArduCopter",
                firmware_version="4.0",
                target=".",
                sort="none",
                delete_documentation_annotations=False,
                verbose=False,
            )
            mock_file.side_effect = OSError("Mocked IO Error")

            with pytest.raises(SystemExit) as cm:
                main()

            assert cm.value.code in [1, 2]

    @pytest.mark.usefixtures("mock_update", "mock_get_xml_dir", "mock_get_xml_url")
    @patch("builtins.open", new_callable=mock.mock_open)
    def test_main_oserror(self, mock_file) -> None:
        with patch("ardupilot_methodic_configurator.annotate_params.parse_arguments") as mock_arg_parser:
            mock_arg_parser.return_value = mock.Mock(
                vehicle_type="ArduCopter",
                firmware_version="4.0",
                target=".",
                sort="none",
                delete_documentation_annotations=False,
                verbose=False,
            )
            mock_file.side_effect = OSError("Mocked OS Error")

            with pytest.raises(SystemExit) as cm:
                main()

            assert cm.value.code in [1, 2]

    @patch("ardupilot_methodic_configurator.annotate_params.get_xml_url")
    def test_get_xml_url_exception(self, mock_get_xml_url_) -> None:
        mock_get_xml_url_.side_effect = ValueError("Mocked Value Error")
        with pytest.raises(ValueError, match="Vehicle type 'NonExistingVehicle' is not supported."):  # noqa: PT012
            get_xml_url("NonExistingVehicle", "4.0")

            @patch("requests.get")
            def test_get_xml_data_remote_file(mock_get) -> None:
                """Test fetching XML data from remote file."""
                # Mock the response
                mock_get.return_value.status_code = 200
                mock_get.return_value.text = "<root></root>"

                # Remove the test.xml file if it exists
                with contextlib.suppress(FileNotFoundError):
                    os.remove("test.xml")

                # Call the function with a remote file
                result = get_xml_data("http://example.com/", ".", "test.xml", "ArduCopter")

                # Check the result
                assert isinstance(result, ET.Element)

                # Assert that requests.get was called once with correct parameters including proxies
                mock_get.assert_called_once_with("http://example.com/test.xml", timeout=5, proxies=None)

            @patch("requests.get")
            def test_get_xml_data_remote_file_with_proxies(mock_get) -> None:
                """Test fetching XML data with proxy configuration."""
                # Mock environment variables
                with patch.dict(
                    os.environ,
                    {"HTTP_PROXY": "http://proxy:8080", "HTTPS_PROXY": "https://proxy:8080", "NO_PROXY": "localhost"},
                ):
                    # Mock the response
                    mock_get.return_value.status_code = 200
                    mock_get.return_value.text = "<root></root>"

                    # Call the function
                    result = get_xml_data("http://example.com/", ".", "test.xml", "ArduCopter")

                    # Check the result
                    assert isinstance(result, ET.Element)

                    # Assert that requests.get was called with proxy settings
                    expected_proxies = {"http": "http://proxy:8080", "https": "https://proxy:8080", "no_proxy": "localhost"}
                    mock_get.assert_called_once_with("http://example.com/test.xml", timeout=5, proxies=expected_proxies)

            @patch("requests.get")
            def test_get_xml_data_remote_file_no_proxies(mock_get) -> None:
                """Test fetching XML data with no proxy configuration."""
                # Clear environment variables
                with patch.dict(os.environ, {}, clear=True):
                    # Mock the response
                    mock_get.return_value.status_code = 200
                    mock_get.return_value.text = "<root></root>"

                    # Call the function
                    result = get_xml_data("http://example.com/", ".", "test.xml", "ArduCopter")

                    # Check the result
                    assert isinstance(result, ET.Element)

                    # Assert that requests.get was called with no proxies
                    mock_get.assert_called_once_with("http://example.com/test.xml", timeout=5, proxies=None)

    @patch.dict(
        "os.environ",
        {
            "HTTP_PROXY": "http://proxy-server:8080",
            "HTTPS_PROXY": "https://proxy-server:8080",
            "NO_PROXY": "localhost,127.0.0.1",
        },
    )
    def test_get_env_proxies_with_proxies(self) -> None:
        """Test getting proxies from environment variables."""
        proxies = get_env_proxies()
        assert proxies is not None
        assert proxies["http"] == "http://proxy-server:8080"
        assert proxies["https"] == "https://proxy-server:8080"
        assert proxies["no_proxy"] == "localhost,127.0.0.1"

    @patch.dict("os.environ", {}, clear=True)
    def test_get_env_proxies_without_proxies(self) -> None:
        """Test getting proxies when environment variables are not set."""
        proxies = get_env_proxies()
        assert proxies is None

    @patch.dict("os.environ", {"http_proxy": "http://lowercase-proxy:8080"})
    def test_get_env_proxies_lowercase(self) -> None:
        """Test getting proxies from lowercase environment variables."""
        proxies = get_env_proxies()
        assert proxies is not None
        assert proxies["http"] == "http://lowercase-proxy:8080"

    def test_extract_parameter_name_and_validate_edge_cases(self) -> None:
        """Test extract_parameter_name_and_validate with various edge cases."""
        # Valid parameter names with different separators
        assert extract_parameter_name_and_validate("PARAM1,100", "test.param", 1) == "PARAM1"
        assert extract_parameter_name_and_validate("PARAM2 100", "test.param", 1) == "PARAM2"
        assert extract_parameter_name_and_validate("PARAM3\t100", "test.param", 1) == "PARAM3"

        # Parameter name must start with capital letter
        with pytest.raises(SystemExit):
            extract_parameter_name_and_validate("param4 100", "test.param", 1)

        # Parameter name can't have special characters
        with pytest.raises(SystemExit):
            extract_parameter_name_and_validate("PARAM-5 100", "test.param", 1)

        # Parameter must be followed by a valid separator
        with pytest.raises(SystemExit):
            extract_parameter_name_and_validate("PARAM6:100", "test.param", 1)

    def test_par_class_methods_comprehensive(self) -> None:
        """Test Par class methods more comprehensively."""
        # Test Par.__init__ and equality
        par1 = Par(10.5, "comment")
        par2 = Par(10.5, "comment")
        par3 = Par(10.5, "different comment")
        par4 = Par(11.0, "comment")

        assert par1 == par2
        assert par1 != par3
        assert par1 != par4
        assert par1 != "not a Par object"

        # Test load_param_file_into_dict with various formats
        with tempfile.NamedTemporaryFile(mode="w", delete=False) as tf:
            tf.write("PARAM1,10.5 # comment1\n")
            tf.write("PARAM2 20.75 # comment2\n")
            tf.write("PARAM3\t30.25\n")  # tab separator, no comment
            tf.write("# This is a full line comment\n")
            tf.write("\n")  # empty line
            tf_name = tf.name

        param_dict = Par.load_param_file_into_dict(tf_name)
        os.unlink(tf_name)

        assert len(param_dict) == 3
        assert param_dict["PARAM1"].value == 10.5
        assert param_dict["PARAM1"].comment == "comment1"
        assert param_dict["PARAM2"].value == 20.75
        assert param_dict["PARAM2"].comment == "comment2"
        assert param_dict["PARAM3"].value == 30.25
        assert param_dict["PARAM3"].comment is None

        # Test load_param_file_into_dict with duplicate parameters
        with tempfile.NamedTemporaryFile(mode="w", delete=False) as tf:
            tf.write("PARAM1,10.5\n")
            tf.write("PARAM1,20.5\n")  # Duplicate parameter
            tf_name = tf.name

        with pytest.raises(SystemExit):
            Par.load_param_file_into_dict(tf_name)
        os.unlink(tf_name)

    def test_missionplanner_sort_function(self) -> None:
        """Test the missionplanner_sort function."""
        # Basic sorting
        params = ["Z_PARAM", "A_PARAM", "C_PARAM", "B_PARAM"]
        sorted_params = sorted(params, key=missionplanner_sort)
        assert sorted_params == ["A_PARAM", "B_PARAM", "C_PARAM", "Z_PARAM"]

        # Complex sorting with underscores
        params = ["RC_FEEL", "RC_MAP_ROLL", "RC_MAP_PITCH", "RC_1_MIN"]
        sorted_params = sorted(params, key=missionplanner_sort)
        assert sorted_params == ["RC_1_MIN", "RC_FEEL", "RC_MAP_PITCH", "RC_MAP_ROLL"]

        # Sort with line content
        lines = ["RC_FEEL 100", "RC_MAP_ROLL 200", "RC_MAP_PITCH 300", "RC_1_MIN 400"]
        sorted_lines = sorted(lines, key=missionplanner_sort)
        assert sorted_lines == ["RC_1_MIN 400", "RC_FEEL 100", "RC_MAP_PITCH 300", "RC_MAP_ROLL 200"]

    @patch("logging.Logger.warning")
    def test_update_parameter_documentation_edge_cases(self, mock_warning) -> None:  # pylint: disable=unused-argument
        """Test update_parameter_documentation with edge cases."""
        # Create a simplified doc_dict for testing
        doc_dict = {
            "PARAM1": {
                "humanName": "Parameter 1",
                "documentation": ["Documentation for Parameter 1"],
                "fields": {},
                "values": {},
            },
            "PARAM2": {
                "humanName": "Parameter 2",
                "documentation": ["Documentation for Parameter 2"],
                "fields": {},
                "values": {},
            },
        }

        # Create a temporary directory
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create an empty file
            empty_file = os.path.join(temp_dir, "empty.param")
            with open(empty_file, "w", encoding="utf-8") as f:
                pass

            # Create file with only comments and whitespace
            comments_file = os.path.join(temp_dir, "comments.param")
            with open(comments_file, "w", encoding="utf-8") as f:
                f.write("# This is a comment\n\n# Another comment\n")

            # Create file with comments and parameters
            mixed_file = os.path.join(temp_dir, "mixed.param")
            with open(mixed_file, "w", encoding="utf-8") as f:
                f.write("# A comment\nPARAM1,100\n\n# Another comment\nPARAM2 200\n")

            # Test with empty file
            update_parameter_documentation(doc_dict, empty_file)
            with open(empty_file, encoding="utf-8") as f:
                content = f.read()
            assert content == ""

            # Test with comments-only file
            update_parameter_documentation(doc_dict, comments_file)
            with open(comments_file, encoding="utf-8") as f:
                content = f.read()
            assert content == ""

            # Test with mixed content and delete_documentation_annotations=True
            update_parameter_documentation(doc_dict, mixed_file, delete_documentation_annotations=True)
            with open(mixed_file, encoding="utf-8") as f:
                content = f.read()
            assert "# Parameter 1" not in content
            assert "PARAM1,100" in content
            assert "PARAM2 200" in content

            # Write the file again with annotations
            with open(mixed_file, "w", encoding="utf-8") as f:
                f.write("# A comment\nPARAM1,100\n\n# Another comment\nPARAM2 200\n")

            # Test with mixed content and regular annotations
            update_parameter_documentation(doc_dict, mixed_file)
            with open(mixed_file, encoding="utf-8") as f:
                content = f.read()
            assert "# Parameter 1" in content
            assert "# Documentation for Parameter 1" in content
            assert "PARAM1,100" in content
            assert "# Parameter 2" in content
            assert "# Documentation for Parameter 2" in content
            assert "PARAM2 200" in content

    def test_extract_parameter_name_and_validate_comprehensive(self) -> None:
        """Comprehensive testing of parameter name extraction and validation."""
        # Valid parameter names with different separators
        assert extract_parameter_name_and_validate("PARAM1,100", "test.param", 1) == "PARAM1"
        assert extract_parameter_name_and_validate("PARAM2 100", "test.param", 1) == "PARAM2"
        assert extract_parameter_name_and_validate("PARAM3\t100", "test.param", 1) == "PARAM3"
        assert extract_parameter_name_and_validate("A123_XYZ,100", "test.param", 1) == "A123_XYZ"

        # Parameter name with trailing whitespace before separator
        assert extract_parameter_name_and_validate("PARAM4   \t100", "test.param", 1) == "PARAM4"

        # Invalid parameter format (not starting with uppercase letter)
        with pytest.raises(SystemExit):
            extract_parameter_name_and_validate("param5 100", "test.param", 1)

        # Invalid parameter format (invalid character)
        with pytest.raises(SystemExit):
            extract_parameter_name_and_validate("PARAM-5 100", "test.param", 1)

        # Invalid separator
        with pytest.raises(SystemExit):
            extract_parameter_name_and_validate("PARAM6:100", "test.param", 1)

        # Parameter name too long
        with pytest.raises(SystemExit):
            extract_parameter_name_and_validate("ABCDEFGHIJKLMNOPQR 100", "test.param", 1)

        # Empty line
        with pytest.raises(SystemExit):
            extract_parameter_name_and_validate("", "test.param", 1)


if __name__ == "__main__":
    unittest.main()
