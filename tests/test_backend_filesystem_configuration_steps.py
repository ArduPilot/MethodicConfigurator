#!/usr/bin/env python3

"""
Tests for the backend_filesystem_configuration_steps.py file.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import logging
import unittest
from json import JSONDecodeError
from unittest.mock import mock_open, patch

from ardupilot_methodic_configurator.backend_filesystem_configuration_steps import ConfigurationSteps

# ruff: noqa: SIM117
# pylint: disable=protected-access


class TestConfigurationSteps(unittest.TestCase):
    """ConfigurationSteps test class."""

    def setUp(self) -> None:
        self.config_steps = ConfigurationSteps("vehicle_dir", "vehicle_type")

    @patch("builtins.open", new_callable=mock_open, read_data='{"steps": {"test_file": {"forced_parameters": {}}}}')
    @patch("os.path.join")
    @patch("os.path.dirname")
    @patch("os.path.abspath")
    def test_re_init(
        self,
        mock_abspath: unittest.mock.Mock,
        mock_dirname: unittest.mock.Mock,
        mock_join: unittest.mock.Mock,
        mock_open2: unittest.mock.Mock,
    ) -> None:
        mock_abspath.return_value = "abs_path"
        mock_dirname.return_value = "dir_name"
        mock_join.side_effect = lambda *args: "/".join(args)
        self.config_steps.re_init("vehicle_dir", "vehicle_type")
        assert self.config_steps.configuration_steps
        mock_open2.assert_has_calls(
            [
                unittest.mock.call("vehicle_dir/configuration_steps_vehicle_type.json", encoding="utf-8-sig"),
                unittest.mock.call("dir_name/configuration_steps_schema.json", encoding="utf-8"),
            ],
            any_order=True,
        )
        assert "test_file" in self.config_steps.configuration_steps

    def test_compute_parameters(self) -> None:
        file_info = {"forced_parameters": {"PARAM1": {"New Value": "10", "Change Reason": "Test reason"}}}
        variables: dict[str, dict] = {"doc_dict": {"PARAM1": {"values": {10: "value"}}}}
        result = self.config_steps.compute_parameters("test_file", file_info, "forced", variables)
        assert result == ""
        assert "test_file" in self.config_steps.forced_parameters
        assert "PARAM1" in self.config_steps.forced_parameters["test_file"]
        assert self.config_steps.forced_parameters["test_file"]["PARAM1"].value == 10
        assert self.config_steps.forced_parameters["test_file"]["PARAM1"].comment == "Test reason"

    def test_auto_changed_by(self) -> None:
        self.config_steps.configuration_steps = {"test_file": {"auto_changed_by": "auto_change"}}
        result = self.config_steps.auto_changed_by("test_file")
        assert result == "auto_change"

    def test_jump_possible(self) -> None:
        self.config_steps.configuration_steps = {"test_file": {"jump_possible": {"step1": "step2"}}}
        result = self.config_steps.jump_possible("test_file")
        assert result == {"step1": "step2"}

    def test_get_documentation_text_and_url(self) -> None:
        self.config_steps.configuration_steps = {
            "test_file": {"prefix_text": "Documentation text", "prefix_url": "http://example.com"}
        }
        text, url = self.config_steps.get_documentation_text_and_url("test_file", "prefix")
        assert text == "Documentation text"
        assert url == "http://example.com"

    def test_get_seq_tooltip_text(self) -> None:
        self.config_steps.configuration_steps = {"test_file": {"tooltip_key": "Tooltip text"}}
        result = self.config_steps.get_seq_tooltip_text("test_file", "tooltip_key")
        assert result == "Tooltip text"

    def test_missing_new_value(self) -> None:
        file_info = {"forced_parameters": {"PARAM1": {"Change Reason": "Test reason"}}}
        with self.assertLogs(level="ERROR") as log:
            self.config_steps._ConfigurationSteps__validate_parameters_in_configuration_steps("test_file", file_info, "forced")  # pylint: disable=protected-access
            assert any("New Value" in message for message in log.output)

    def test_missing_change_reason(self) -> None:
        file_info = {"forced_parameters": {"PARAM1": {"New Value": "10"}}}
        with self.assertLogs(level="ERROR") as log:
            self.config_steps._ConfigurationSteps__validate_parameters_in_configuration_steps("test_file", file_info, "forced")  # pylint: disable=protected-access
            assert any("Change Reason" in message for message in log.output)

    def test_compute_parameters_with_invalid_expression(self) -> None:
        file_info = {"forced_parameters": {"PARAM1": {"New Value": "invalid_expression", "Change Reason": "Test reason"}}}
        variables: dict[str, dict] = {"doc_dict": {"PARAM1": {"values": {10: "value"}}}}
        result = self.config_steps.compute_parameters("test_file", file_info, "forced", variables)
        assert "could not be computed" in result

    def test_compute_parameters_with_missing_doc_dict(self) -> None:
        file_info = {"forced_parameters": {"PARAM1": {"New Value": "10", "Change Reason": "Test reason"}}}
        variables: dict[str, dict] = {}
        result = self.config_steps.compute_parameters("test_file", file_info, "forced", variables)
        assert result == ""

    def test_compute_parameters_with_string_result(self) -> None:
        file_info = {"forced_parameters": {"PARAM1": {"New Value": "'value'", "Change Reason": "Test reason"}}}
        variables: dict[str, dict] = {"doc_dict": {"PARAM1": {"values": {10: "value"}}}}
        result = self.config_steps.compute_parameters("test_file", file_info, "forced", variables)
        assert result == ""
        assert self.config_steps.forced_parameters["test_file"]["PARAM1"].value == 10

    def test_re_init_file_not_found(self) -> None:
        """Test re_init when configuration file is not found."""
        with patch("builtins.open", side_effect=FileNotFoundError), patch("os.path.join", return_value="test_path"):
            with self.assertLogs(level="WARNING") as log:
                self.config_steps.re_init("vehicle_dir", "vehicle_type")
                assert any("No configuration steps documentation" in message for message in log.output)
        assert not self.config_steps.configuration_steps


def test_re_init_empty_vehicle_type() -> None:
    """Test re_init with empty vehicle type."""
    config_steps = ConfigurationSteps("vehicle_dir", "old_type")
    config_steps.configuration_steps = {"test": {}}

    # Should return early without modifying state
    config_steps.re_init("vehicle_dir", "")

    assert config_steps.configuration_steps_filename == "configuration_steps_old_type.json"
    assert "test" in config_steps.configuration_steps


def test_compute_parameters_with_bitmask() -> None:
    """Test compute_parameters with bitmask values."""
    config_steps = ConfigurationSteps("vehicle_dir", "vehicle_type")
    file_info = {"forced_parameters": {"PARAM1": {"New Value": "'bitmask_option'", "Change Reason": "Test reason"}}}
    variables = {"doc_dict": {"PARAM1": {"values": {}, "Bitmask": {2: "bitmask_option"}}}}

    config_steps.compute_parameters("test_file", file_info, "forced", variables)

    assert config_steps.forced_parameters["test_file"]["PARAM1"].value == 4  # 2^2


def test_compute_parameters_empty_file_info() -> None:
    """Test compute_parameters with empty file_info."""
    config_steps = ConfigurationSteps("vehicle_dir", "vehicle_type")
    result = config_steps.compute_parameters("test_file", {}, "forced", {"doc_dict": {}})

    assert result == ""
    assert not config_steps.forced_parameters


def test_compute_parameters_empty_variables() -> None:
    """Test compute_parameters with empty variables."""
    config_steps = ConfigurationSteps("vehicle_dir", "vehicle_type")
    file_info = {"forced_parameters": {"PARAM1": {"New Value": "10", "Change Reason": "Test"}}}
    result = config_steps.compute_parameters("test_file", file_info, "forced", {})

    assert result == ""
    assert not config_steps.forced_parameters


def test_compute_parameters_with_fc_parameters_missing() -> None:
    """Test compute parameters when fc_parameters referenced but not available."""
    config_steps = ConfigurationSteps("vehicle_dir", "vehicle_type")
    file_info = {"forced_parameters": {"PARAM1": {"New Value": "fc_parameters['P1']", "Change Reason": "Test"}}}
    variables = {"doc_dict": {"PARAM1": {"values": {}}}}

    result = config_steps.compute_parameters("test_file", file_info, "forced", variables)

    # More generalized assertion to match the actual error pattern
    assert "fc_parameters" in result
    assert "not defined" in result or "not found" in result


def test_auto_changed_by_nonexistent_file() -> None:
    """Test auto_changed_by with a nonexistent file."""
    config_steps = ConfigurationSteps("vehicle_dir", "vehicle_type")
    result = config_steps.auto_changed_by("nonexistent_file")

    assert result == ""


def test_jump_possible_nonexistent_file() -> None:
    """Test jump_possible with a nonexistent file."""
    config_steps = ConfigurationSteps("vehicle_dir", "vehicle_type")
    result = config_steps.jump_possible("nonexistent_file")

    assert not result


def test_get_documentation_text_and_url_no_config_steps() -> None:
    """Test get_documentation_text_and_url with no configuration steps."""
    config_steps = ConfigurationSteps("vehicle_dir", "vehicle_type")
    config_steps.configuration_steps = {}

    text, url = config_steps.get_documentation_text_and_url("test_file", "prefix")

    assert "No intermediate parameter configuration steps available" in text
    assert url == ""


def test_schema_validation_error(caplog) -> None:
    """Test handling of schema validation errors during re_init."""
    mock_config_file = '{"steps": {"test_file": {"forced_parameters": {}}}}'

    # We need to provide both open call responses
    with patch(
        "builtins.open",
        side_effect=[
            mock_open(read_data=mock_config_file).return_value,  # First open call
            FileNotFoundError(),  # Schema file not found
        ],
    ):
        with patch("os.path.join", return_value="test_path"):
            with patch("os.path.dirname", return_value="dir_name"):
                with patch("os.path.abspath", return_value="abs_path"):
                    config_steps = ConfigurationSteps("vehicle_dir", "vehicle_type")
                    config_steps.re_init("vehicle_dir", "vehicle_type")

                    # Check for schema file not found message
                    assert "Schema file" in caplog.text
                    assert "not found" in caplog.text


def test_json_decode_error(caplog) -> None:
    """Test handling of JSON decode errors in configuration file."""
    # Create a JSONDecodeError with proper arguments
    json_error = JSONDecodeError("JSON decode error", "", 0)

    with patch("builtins.open", side_effect=json_error):
        with patch("os.path.join", return_value="test_path"):
            config_steps = ConfigurationSteps("vehicle_dir", "vehicle_type")
            config_steps.re_init("vehicle_dir", "vehicle_type")

            assert "Error in file" in caplog.text
            assert not config_steps.configuration_steps


def test_compute_multiple_parameters() -> None:
    """Test computing multiple parameters in a single file."""
    config_steps = ConfigurationSteps("vehicle_dir", "vehicle_type")
    file_info = {
        "forced_parameters": {
            "PARAM1": {"New Value": "10", "Change Reason": "Reason 1"},
            "PARAM2": {"New Value": "20", "Change Reason": "Reason 2"},
            "PARAM3": {"New Value": "30", "Change Reason": "Reason 3"},
        }
    }
    variables = {
        "doc_dict": {
            "PARAM1": {"values": {10: "value1"}},
            "PARAM2": {"values": {20: "value2"}},
            "PARAM3": {"values": {30: "value3"}},
        }
    }

    result = config_steps.compute_parameters("test_file", file_info, "forced", variables)

    assert result == ""
    assert len(config_steps.forced_parameters["test_file"]) == 3
    assert config_steps.forced_parameters["test_file"]["PARAM1"].value == 10
    assert config_steps.forced_parameters["test_file"]["PARAM2"].value == 20
    assert config_steps.forced_parameters["test_file"]["PARAM3"].value == 30


def test_compute_derived_parameters() -> None:
    """Test computing derived parameters."""
    config_steps = ConfigurationSteps("vehicle_dir", "vehicle_type")
    file_info = {"derived_parameters": {"PARAM1": {"New Value": "10 * 2", "Change Reason": "Test derived"}}}
    variables = {"doc_dict": {"PARAM1": {"values": {20: "value"}}}}

    result = config_steps.compute_parameters("test_file", file_info, "derived", variables)

    assert result == ""
    assert "test_file" in config_steps.derived_parameters
    assert "PARAM1" in config_steps.derived_parameters["test_file"]
    assert config_steps.derived_parameters["test_file"]["PARAM1"].value == 20
    assert config_steps.derived_parameters["test_file"]["PARAM1"].comment == "Test derived"


def test_configuration_phases() -> None:
    """Test loading of configuration phases."""
    with (
        patch(
            "builtins.open",
            new_callable=mock_open,
            read_data='{"steps": {}, "phases": {"phase1": {"description": "Phase 1"}}}',
        ),
        patch("os.path.join", return_value="test_path"),
        patch("os.path.dirname", return_value="dir_name"),
    ):
        with patch("os.path.abspath", return_value="abs_path"):
            with patch("jsonschema.validate"):
                config_steps = ConfigurationSteps("vehicle_dir", "vehicle_type")
                config_steps.re_init("vehicle_dir", "vehicle_type")

                assert "phase1" in config_steps.configuration_phases
                assert config_steps.configuration_phases["phase1"]["description"] == "Phase 1"


def test_invalid_parameter_format() -> None:
    """Test validation when parameters aren't properly formatted."""
    with (
        patch(
            "builtins.open", new_callable=mock_open, read_data='{"steps": {"test_file": {"forced_parameters": "not_a_dict"}}}'
        ),
        patch("os.path.join", return_value="test_path"),
        patch("os.path.dirname", return_value="dir_name"),
        patch("os.path.abspath", return_value="abs_path"),
        patch("jsonschema.validate"),
        patch("ardupilot_methodic_configurator.backend_filesystem_configuration_steps.logging_error") as mock_error,
    ):
        config_steps = ConfigurationSteps("vehicle_dir", "vehicle_type")
        config_steps.re_init("vehicle_dir", "vehicle_type")

        # Check if logging.error was called with the expected message
        assert any("is not a dictionary" in str(args) for args, _ in mock_error.call_args_list)


def test_compute_parameters_with_fc_parameters() -> None:
    """Test compute_parameters when fc_parameters are provided."""
    config_steps = ConfigurationSteps("vehicle_dir", "vehicle_type")
    file_info = {"forced_parameters": {"PARAM1": {"New Value": "fc_parameters['P1'] * 2", "Change Reason": "Test FC"}}}
    variables = {"doc_dict": {"PARAM1": {"values": {20: "value"}}}, "fc_parameters": {"P1": 10}}

    result = config_steps.compute_parameters("test_file", file_info, "forced", variables)

    assert result == ""
    assert config_steps.forced_parameters["test_file"]["PARAM1"].value == 20


def test_get_seq_tooltip_text_nonexistent_tooltip() -> None:
    """Test getting tooltip text for a nonexistent tooltip key."""
    config_steps = ConfigurationSteps("vehicle_dir", "vehicle_type")
    config_steps.configuration_steps = {"test_file": {}}

    result = config_steps.get_seq_tooltip_text("test_file", "nonexistent_tooltip")

    assert "No documentation available" in result


def test_nonexistent_parameter_in_doc_dict() -> None:
    """Test computing parameter value when parameter not in doc_dict."""
    config_steps = ConfigurationSteps("vehicle_dir", "vehicle_type")
    file_info = {"forced_parameters": {"PARAM1": {"New Value": "'unknown_value'", "Change Reason": "Test"}}}
    variables = {"doc_dict": {"PARAM2": {"values": {}}}}  # PARAM1 not in doc_dict

    # Simply check the returned error message
    result = config_steps.compute_parameters("test_file", file_info, "forced", variables)
    assert "could not be computed" in result or "not found" in result

    # Also verify the parameter wasn't added
    assert "test_file" not in config_steps.forced_parameters or "PARAM1" not in config_steps.forced_parameters.get(
        "test_file", {}
    )


def test_compute_parameters_with_float_result() -> None:
    """Test compute_parameters with a float result."""
    config_steps = ConfigurationSteps("vehicle_dir", "vehicle_type")
    file_info = {"forced_parameters": {"PARAM1": {"New Value": "10.5", "Change Reason": "Test float"}}}
    variables = {"doc_dict": {"PARAM1": {"values": {}}}}

    result = config_steps.compute_parameters("test_file", file_info, "forced", variables)

    assert result == ""
    assert config_steps.forced_parameters["test_file"]["PARAM1"].value == 10.5


def test_get_seq_tooltip_text_when_documentation_none() -> None:
    """Test get_seq_tooltip_text when documentation is None."""
    config_steps = ConfigurationSteps("vehicle_dir", "vehicle_type")
    config_steps.configuration_steps = None

    result = config_steps.get_seq_tooltip_text("test_file", "tooltip_key")

    assert "not found" in result


def test_compute_parameters_with_complex_expression() -> None:
    """Test compute_parameters with a more complex expression."""
    config_steps = ConfigurationSteps("vehicle_dir", "vehicle_type")
    file_info = {"forced_parameters": {"PARAM1": {"New Value": "10 * 2 + 5", "Change Reason": "Complex calculation"}}}
    variables = {"doc_dict": {"PARAM1": {"values": {}}}}

    result = config_steps.compute_parameters("test_file", file_info, "forced", variables)

    assert result == ""
    assert config_steps.forced_parameters["test_file"]["PARAM1"].value == 25


def test_compute_parameters_with_parameter_lookup() -> None:
    """Test compute_parameters using values from another parameter."""
    config_steps = ConfigurationSteps("vehicle_dir", "vehicle_type")
    file_info = {
        "forced_parameters": {
            "PARAM1": {"New Value": "10", "Change Reason": "Base value"},
            "PARAM2": {"New Value": "doc_dict['PARAM1']['values'][10] == 'value1' and 20 or 30", "Change Reason": "Lookup"},
        }
    }
    variables = {"doc_dict": {"PARAM1": {"values": {10: "value1"}}, "PARAM2": {"values": {}}}}

    result = config_steps.compute_parameters("test_file", file_info, "forced", variables)

    assert result == ""
    assert config_steps.forced_parameters["test_file"]["PARAM2"].value == 20


def test_escape_characters_in_parameters() -> None:
    """Test handling of escape characters in parameter strings."""
    config_steps = ConfigurationSteps("vehicle_dir", "vehicle_type")
    file_info = {"forced_parameters": {"PARAM1": {"New Value": "'value with \\'quotes\\''", "Change Reason": "Test escapes"}}}
    variables = {"doc_dict": {"PARAM1": {"values": {10: "value"}}}}

    result = config_steps.compute_parameters("test_file", file_info, "forced", variables)

    # The evaluated string "value with 'quotes'" is not in the doc_dict values dict,
    # so since StopIteration is now caught in _resolve_string_result the error message
    # describes the lookup failure rather than the generic "could not be computed" phrase.
    assert result != ""  # An error was reported (not silent success)


def test_documentation_url_when_not_provided() -> None:
    """Test documentation URL behavior when not provided."""
    config_steps = ConfigurationSteps("vehicle_dir", "vehicle_type")
    config_steps.configuration_steps = {"test_file": {"prefix_text": "Documentation text"}}

    text, url = config_steps.get_documentation_text_and_url("test_file", "prefix")

    assert text == "Documentation text"
    assert url == ""  # URL should be empty string when not provided


def test_compute_derived_parameters_with_warning() -> None:
    """Test derived parameters with a warning instead of error."""
    config_steps = ConfigurationSteps("vehicle_dir", "vehicle_type")
    file_info = {"derived_parameters": {"PARAM1": {"New Value": "undefined_var", "Change Reason": "Test warning"}}}
    variables = {"doc_dict": {"PARAM1": {"values": {}}}}

    # Just check that it doesn't raise an exception and returns empty string
    result = config_steps.compute_parameters("test_file", file_info, "derived", variables)
    assert result == ""

    # Or focus on the behavior rather than the logs:
    assert "test_file" not in config_steps.derived_parameters


def test_validate_parameters_empty_dict() -> None:
    """Test parameter validation with empty parameters dict."""
    config_steps = ConfigurationSteps("vehicle_dir", "vehicle_type")
    file_info = {"forced_parameters": {}}

    # Should not raise any errors or log any warnings
    config_steps._ConfigurationSteps__validate_parameters_in_configuration_steps("test_file", file_info, "forced")  # pylint: disable=protected-access
    assert True  # If we get here, no exception was raised


def test_malicious_expression_import_blocked() -> None:
    """Test that __import__ expressions are blocked by the safe evaluator."""
    config_steps = ConfigurationSteps("vehicle_dir", "vehicle_type")
    file_info = {
        "forced_parameters": {
            "PARAM1": {"New Value": "__import__('os').system('echo pwned')", "Change Reason": "Malicious"},
        }
    }
    variables = {"doc_dict": {"PARAM1": {"values": {}}}}

    result = config_steps.compute_parameters("test_file", file_info, "forced", variables)

    assert result != ""
    assert "PARAM1" in result
    assert "test_file" not in config_steps.forced_parameters


def test_malicious_expression_builtins_blocked() -> None:
    """Test that accessing __builtins__ is blocked by the safe evaluator."""
    config_steps = ConfigurationSteps("vehicle_dir", "vehicle_type")
    file_info = {
        "forced_parameters": {
            "PARAM1": {"New Value": "__builtins__.__import__('os').system('id')", "Change Reason": "Malicious"},
        }
    }
    variables = {"doc_dict": {"PARAM1": {"values": {}}}}

    result = config_steps.compute_parameters("test_file", file_info, "forced", variables)

    assert result != ""
    assert "PARAM1" in result
    assert "test_file" not in config_steps.forced_parameters


def test_safe_log_function_in_expression() -> None:
    """Test that log() works as a whitelisted safe function (replacing __import__('math').log())."""
    config_steps = ConfigurationSteps("vehicle_dir", "vehicle_type")
    file_info = {
        "forced_parameters": {
            "MOT_THST_EXPO": {
                "New Value": (
                    "min(0.8, round(0.15686*log("
                    "vehicle_components['Propellers']['Specifications']['Diameter_inches'])"
                    "+0.23693, 2))"
                ),
                "Change Reason": "Derived from propeller size",
            },
        }
    }
    variables = {
        "doc_dict": {"MOT_THST_EXPO": {"values": {}}},
        "vehicle_components": {"Propellers": {"Specifications": {"Diameter_inches": 10}}},
    }

    result = config_steps.compute_parameters("test_file", file_info, "forced", variables)

    assert result == ""
    assert abs(config_steps.forced_parameters["test_file"]["MOT_THST_EXPO"].value - 0.6) < 0.01


# ---------------------------------------------------------------------------
# Tests for _condition_passes
# ---------------------------------------------------------------------------


def test_condition_passes_no_if_key() -> None:
    """Test _condition_passes returns True when no 'if' key is present."""
    result = ConfigurationSteps._condition_passes({}, {})
    assert result is True


def test_condition_passes_true_condition() -> None:
    """Test _condition_passes returns True when condition evaluates to True."""
    result = ConfigurationSteps._condition_passes({"if": "1 == 1"}, {})
    assert result is True


def test_condition_passes_false_condition() -> None:
    """Test _condition_passes returns False when condition evaluates to False."""
    result = ConfigurationSteps._condition_passes({"if": "1 == 2"}, {})
    assert result is False


def test_condition_passes_syntax_error_logs_warning(caplog) -> None:
    """Test _condition_passes logs a warning and returns False on SyntaxError."""
    with caplog.at_level(logging.WARNING):
        result = ConfigurationSteps._condition_passes({"if": "this is not valid python !!!"}, {})
    assert result is False
    assert caplog.records, "Expected a warning to be logged for a syntax error in the condition"
    assert any("syntax error" in r.message.lower() for r in caplog.records)


def test_condition_passes_name_error_fc_parameters_silent() -> None:
    """Test _condition_passes returns False silently (no warning) when fc_parameters not in variables."""
    config_steps = ConfigurationSteps("vehicle_dir", "vehicle_type")
    with unittest.mock.patch(
        "ardupilot_methodic_configurator.backend_filesystem_configuration_steps.logging_warning"
    ) as mock_warn:
        result = config_steps._condition_passes({"if": "'PARAM' in fc_parameters"}, {})
    assert result is False
    mock_warn.assert_not_called()


def test_condition_passes_with_variables() -> None:
    """Test _condition_passes correctly evaluates a condition using provided variables."""
    result = ConfigurationSteps._condition_passes({"if": "x > 0"}, {"x": 5})
    assert result is True
    result = ConfigurationSteps._condition_passes({"if": "x > 0"}, {"x": -1})
    assert result is False


# ---------------------------------------------------------------------------
# Tests for compute_deletions
# ---------------------------------------------------------------------------


def test_compute_deletions_no_delete_parameters() -> None:
    """Test compute_deletions returns empty set when no delete_parameters in file_info."""
    config_steps = ConfigurationSteps("vehicle_dir", "vehicle_type")
    result = config_steps.compute_deletions("test_file", {}, {"doc_dict": {}})
    assert result == set()


def test_compute_deletions_empty_variables_logs_warning(caplog) -> None:
    """Test compute_deletions warns and returns empty set when delete_parameters present but variables empty."""
    config_steps = ConfigurationSteps("vehicle_dir", "vehicle_type")
    file_info = {"delete_parameters": {"PARAM1": {}}}
    with caplog.at_level(logging.WARNING):
        result = config_steps.compute_deletions("test_file", file_info, {})
    assert result == set()
    assert any("test_file" in r.message for r in caplog.records)


def test_compute_deletions_unconditional() -> None:
    """Test compute_deletions deletes parameters unconditionally when no 'if' key."""
    config_steps = ConfigurationSteps("vehicle_dir", "vehicle_type")
    file_info = {"delete_parameters": {"PARAM1": {}, "PARAM2": {}}}
    result = config_steps.compute_deletions("test_file", file_info, {"doc_dict": {}})
    assert result == {"PARAM1", "PARAM2"}


def test_compute_deletions_with_true_condition() -> None:
    """Test compute_deletions includes parameter when condition evaluates to True."""
    config_steps = ConfigurationSteps("vehicle_dir", "vehicle_type")
    file_info = {"delete_parameters": {"PARAM1": {"if": "True"}}}
    result = config_steps.compute_deletions("test_file", file_info, {"doc_dict": {}})
    assert "PARAM1" in result


def test_compute_deletions_with_false_condition() -> None:
    """Test compute_deletions excludes parameter when condition evaluates to False."""
    config_steps = ConfigurationSteps("vehicle_dir", "vehicle_type")
    file_info = {"delete_parameters": {"PARAM1": {"if": "False"}}}
    result = config_steps.compute_deletions("test_file", file_info, {"doc_dict": {}})
    assert "PARAM1" not in result


def test_compute_deletions_fc_not_connected_skips_silently() -> None:
    """Test compute_deletions silently skips deletion when fc_parameters not in variables."""
    config_steps = ConfigurationSteps("vehicle_dir", "vehicle_type")
    file_info = {"delete_parameters": {"PARAM1": {"if": "fc_parameters and ('PARAM1' not in fc_parameters)"}}}
    # No fc_parameters in variables — NameError is expected and should be silent
    result = config_steps.compute_deletions("test_file", file_info, {"doc_dict": {}})
    assert "PARAM1" not in result


def test_compute_deletions_syntax_error_logs_warning(caplog) -> None:
    """Test compute_deletions logs a warning and skips parameter on condition SyntaxError."""
    config_steps = ConfigurationSteps("vehicle_dir", "vehicle_type")
    file_info = {"delete_parameters": {"PARAM1": {"if": "this is not valid python !!!"}}}
    with caplog.at_level(logging.WARNING):
        result = config_steps.compute_deletions("test_file", file_info, {"doc_dict": {}})
    assert "PARAM1" not in result
    assert any("syntax error" in r.message.lower() for r in caplog.records)


def test_compute_deletions_with_fc_parameters_condition() -> None:
    """Test compute_deletions correctly evaluates an fc_parameters-based condition."""
    config_steps = ConfigurationSteps("vehicle_dir", "vehicle_type")
    file_info = {
        "delete_parameters": {"INS_TCAL2_ENABLE": {"if": "fc_parameters and ('INS_TCAL2_ENABLE' not in fc_parameters)"}}
    }
    # FC connected but parameter not present → should be deleted
    result = config_steps.compute_deletions("test_file", file_info, {"fc_parameters": {"OTHER": 1.0}})
    assert "INS_TCAL2_ENABLE" in result
    # FC connected and parameter present → should NOT be deleted
    result2 = config_steps.compute_deletions("test_file", file_info, {"fc_parameters": {"INS_TCAL2_ENABLE": 2.0}})
    assert "INS_TCAL2_ENABLE" not in result2


# ---------------------------------------------------------------------------
# Tests for add-from-FC shorthand in compute_parameters
# ---------------------------------------------------------------------------


def test_add_from_fc_shorthand_populates_derived_parameter() -> None:
    """Test add-from-FC shorthand: derived entry with only 'if' gets its value from FC."""
    config_steps = ConfigurationSteps("vehicle_dir", "vehicle_type")
    file_info = {"derived_parameters": {"INS_TCAL2_ENABLE": {"if": "'INS_TCAL2_ENABLE' in fc_parameters"}}}
    variables = {"doc_dict": {}, "fc_parameters": {"INS_TCAL2_ENABLE": 2.0}}

    result = config_steps.compute_parameters("test_file", file_info, "derived", variables)

    assert result == ""
    assert "test_file" in config_steps.derived_parameters
    assert config_steps.derived_parameters["test_file"]["INS_TCAL2_ENABLE"].value == 2.0
    assert config_steps.derived_parameters["test_file"]["INS_TCAL2_ENABLE"].comment == ""


def test_add_from_fc_shorthand_skipped_when_fc_disconnected() -> None:
    """Test add-from-FC shorthand is silently skipped when FC variables not available."""
    config_steps = ConfigurationSteps("vehicle_dir", "vehicle_type")
    file_info = {"derived_parameters": {"INS_TCAL2_ENABLE": {"if": "'INS_TCAL2_ENABLE' in fc_parameters"}}}
    variables = {"doc_dict": {}}  # no fc_parameters

    result = config_steps.compute_parameters("test_file", file_info, "derived", variables)

    assert result == ""
    assert "test_file" not in config_steps.derived_parameters


def test_add_from_fc_shorthand_skipped_when_param_absent_from_fc() -> None:
    """Test add-from-FC shorthand skips parameter when condition passes but param not in fc_params dict."""
    config_steps = ConfigurationSteps("vehicle_dir", "vehicle_type")
    # Condition references a different checking method — always True but param not in FC
    file_info = {"derived_parameters": {"INS_TCAL2_ENABLE": {"if": "True"}}}
    variables = {"doc_dict": {}, "fc_parameters": {"OTHER_PARAM": 1.0}}

    result = config_steps.compute_parameters("test_file", file_info, "derived", variables)

    assert result == ""
    assert "INS_TCAL2_ENABLE" not in config_steps.derived_parameters.get("test_file", {})


def test_add_from_fc_shorthand_forced_logs_warning(caplog) -> None:
    """Test that a forced parameter entry without 'New Value' logs a warning and is skipped."""
    config_steps = ConfigurationSteps("vehicle_dir", "vehicle_type")
    file_info = {"forced_parameters": {"PARAM1": {"if": "True"}}}
    variables = {"doc_dict": {}, "fc_parameters": {"PARAM1": 5.0}}

    with caplog.at_level(logging.WARNING):
        result = config_steps.compute_parameters("test_file", file_info, "forced", variables)

    assert result == ""  # Not a fatal error, just a warning
    assert "PARAM1" not in config_steps.forced_parameters.get("test_file", {})
    assert any("add-from-FC shorthand is only valid for derived parameters" in r.message for r in caplog.records)


if __name__ == "__main__":
    unittest.main()
