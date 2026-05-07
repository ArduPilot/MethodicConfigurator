#!/usr/bin/env python3

"""
Tests for the backend_filesystem_configuration_steps.py file.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import logging
from json import JSONDecodeError
from unittest.mock import call, mock_open, patch

import pytest
from jsonschema.exceptions import ValidationError

from ardupilot_methodic_configurator.backend_filesystem_configuration_steps import ConfigurationSteps

# pylint: disable=protected-access, too-many-lines


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def config_steps() -> ConfigurationSteps:
    """Fixture providing a fresh ConfigurationSteps instance for each test."""
    return ConfigurationSteps("vehicle_dir", "vehicle_type")


# ---------------------------------------------------------------------------
# re_init loading behavior
# ---------------------------------------------------------------------------


class TestReInit:
    """Tests for re_init() — loading and validating configuration step files."""

    def test_configuration_steps_are_loaded_from_vehicle_directory(self, config_steps: ConfigurationSteps) -> None:
        """
        Configuration steps are loaded when a valid file exists in the vehicle directory.

        GIVEN: A configuration file with a single step exists in the vehicle directory
        WHEN: re_init is called with the correct vehicle_dir and vehicle_type
        THEN: configuration_steps is populated and both the config and schema files are opened
        """
        read_data = '{"steps": {"test_file": {"forced_parameters": {}}}}'
        with (
            patch("builtins.open", new_callable=mock_open, read_data=read_data) as mock_file,
            patch("os.path.abspath", return_value="abs_path"),
            patch("os.path.dirname", return_value="dir_name"),
            patch("os.path.join", side_effect=lambda *args: "/".join(args)),
        ):
            config_steps.re_init("vehicle_dir", "vehicle_type")

            assert config_steps.configuration_steps
            assert "test_file" in config_steps.configuration_steps
            mock_file.assert_has_calls(
                [
                    call("vehicle_dir/configuration_steps_vehicle_type.json", encoding="utf-8-sig"),
                    call("dir_name/configuration_steps_schema.json", encoding="utf-8"),
                ],
                any_order=True,
            )

    def test_re_init_returns_early_when_vehicle_type_is_empty(self, config_steps: ConfigurationSteps) -> None:
        """
        re_init does nothing when vehicle_type is an empty string.

        GIVEN: A ConfigurationSteps instance with existing configuration steps
        WHEN: re_init is called with an empty vehicle_type
        THEN: The existing configuration_steps_filename and steps are preserved unchanged
        """
        config_steps.configuration_steps_filename = "configuration_steps_old_type.json"
        config_steps.configuration_steps = {"test": {}}

        config_steps.re_init("vehicle_dir", "")

        assert config_steps.configuration_steps_filename == "configuration_steps_old_type.json"
        assert "test" in config_steps.configuration_steps

    def test_re_init_logs_warning_when_configuration_file_not_found(
        self, config_steps: ConfigurationSteps, caplog: pytest.LogCaptureFixture
    ) -> None:
        """
        A warning is logged and configuration_steps remains empty when the file is missing.

        GIVEN: No configuration file exists in any search directory
        WHEN: re_init is called
        THEN: A warning about missing configuration steps is logged and steps remain empty
        """
        with (
            patch("builtins.open", side_effect=FileNotFoundError),
            patch("os.path.join", return_value="test_path"),
            caplog.at_level(logging.WARNING),
        ):
            config_steps.re_init("vehicle_dir", "vehicle_type")

        assert "No configuration steps documentation" in caplog.text
        assert not config_steps.configuration_steps

    def test_re_init_logs_error_for_json_decode_error(
        self, config_steps: ConfigurationSteps, caplog: pytest.LogCaptureFixture
    ) -> None:
        """
        A JSON decode error in the config file is surfaced as an error log entry.

        GIVEN: The configuration file contains malformed JSON
        WHEN: re_init is called
        THEN: An error is logged and configuration_steps remains empty
        """
        json_error = JSONDecodeError("JSON decode error", "", 0)
        with (
            patch("builtins.open", side_effect=json_error),
            patch("os.path.join", return_value="test_path"),
            caplog.at_level(logging.ERROR),
        ):
            config_steps.re_init("vehicle_dir", "vehicle_type")

        assert "Error in file" in caplog.text
        assert not config_steps.configuration_steps

    def test_re_init_logs_error_when_schema_file_not_found(
        self, config_steps: ConfigurationSteps, caplog: pytest.LogCaptureFixture
    ) -> None:
        """
        A missing schema file is reported as an error without aborting step loading.

        GIVEN: The config file is valid JSON but the JSON schema file is absent
        WHEN: re_init is called
        THEN: An error mentioning the schema file is logged
        """
        mock_config_file = '{"steps": {"test_file": {"forced_parameters": {}}}}'
        with (
            patch(
                "builtins.open",
                side_effect=[mock_open(read_data=mock_config_file).return_value, FileNotFoundError()],
            ),
            patch("os.path.join", return_value="test_path"),
            patch("os.path.dirname", return_value="dir_name"),
            patch("os.path.abspath", return_value="abs_path"),
            caplog.at_level(logging.ERROR),
        ):
            config_steps.re_init("vehicle_dir", "vehicle_type")

        assert "Schema file" in caplog.text
        assert "not found" in caplog.text

    def test_re_init_loads_configuration_phases(self, config_steps: ConfigurationSteps) -> None:
        """
        Configuration phases are populated when the file contains a 'phases' section.

        GIVEN: A configuration file containing both steps and phases
        WHEN: re_init is called
        THEN: configuration_phases contains the expected phase data
        """
        read_data = '{"steps": {}, "phases": {"phase1": {"description": "Phase 1"}}}'
        with (
            patch("builtins.open", new_callable=mock_open, read_data=read_data),
            patch("os.path.join", return_value="test_path"),
            patch("os.path.dirname", return_value="dir_name"),
            patch("os.path.abspath", return_value="abs_path"),
            patch("jsonschema.validate"),
        ):
            config_steps.re_init("vehicle_dir", "vehicle_type")

        assert "phase1" in config_steps.configuration_phases
        assert config_steps.configuration_phases["phase1"]["description"] == "Phase 1"

    def test_second_reinit_logs_warning_when_config_file_overrides_default(
        self, config_steps: ConfigurationSteps, caplog: pytest.LogCaptureFixture
    ) -> None:
        """
        A warning is logged when re_init is called a second time and the file is in the vehicle directory.

        GIVEN: A valid configuration file in the vehicle directory
        WHEN: re_init is called a second time (log_loaded_file is True from the first call)
        THEN: A warning mentioning 'overwriting default' is logged
        """
        config_data: dict = {"steps": {}}
        with (
            patch(
                "ardupilot_methodic_configurator.backend_filesystem_configuration_steps.json_load",
                return_value=config_data,
            ),
            patch("builtins.open", mock_open()),
            patch("os.path.join", side_effect=lambda *args: "/".join(args)),
            patch("os.path.abspath", return_value="abs_path"),
            patch("os.path.dirname", return_value="dir_name"),
            patch("ardupilot_methodic_configurator.backend_filesystem_configuration_steps.json_validate"),
        ):
            config_steps.re_init("vehicle_dir", "vehicle_type")  # first call: sets log_loaded_file=True
            with caplog.at_level(logging.WARNING):
                config_steps.re_init("vehicle_dir", "vehicle_type")  # second call: triggers i==0 warning

        assert any("overwriting default" in r.message for r in caplog.records)

    def test_second_reinit_logs_info_when_config_file_found_in_package_dir(
        self, config_steps: ConfigurationSteps, caplog: pytest.LogCaptureFixture
    ) -> None:
        """
        An info message is logged when the config file is only in the package directory.

        GIVEN: No configuration file in the vehicle directory, file found only in the package directory
        WHEN: re_init is called a second time (log_loaded_file is True)
        THEN: An INFO message mentioning 'loaded from' is logged
        """
        config_data: dict = {"steps": {}}

        def open_side_effect(path: str, **_kwargs: object) -> object:  # type: ignore[return]
            if "vehicle_dir" in str(path):
                raise FileNotFoundError
            return mock_open(read_data="")()  # type: ignore[return-value]

        with (
            patch("builtins.open", side_effect=open_side_effect),
            patch(
                "ardupilot_methodic_configurator.backend_filesystem_configuration_steps.json_load",
                return_value=config_data,
            ),
            patch("os.path.join", side_effect=lambda *args: "/".join(args)),
            patch("os.path.abspath", return_value="abs_path"),
            patch("os.path.dirname", return_value="dir_name"),
            patch("ardupilot_methodic_configurator.backend_filesystem_configuration_steps.json_validate"),
        ):
            config_steps.re_init("vehicle_dir", "vehicle_type")  # first call: sets log_loaded_file=True
            with caplog.at_level(logging.INFO):
                config_steps.re_init("vehicle_dir", "vehicle_type")  # second call: triggers i==1 info log

        assert any("loaded from" in r.message for r in caplog.records if r.levelno == logging.INFO)

    def test_re_init_logs_error_for_schema_validation_error(
        self, config_steps: ConfigurationSteps, caplog: pytest.LogCaptureFixture
    ) -> None:
        """
        A ValidationError during schema validation is logged as an error.

        GIVEN: A valid config file and a json_validate that raises ValidationError
        WHEN: re_init is called
        THEN: An error mentioning 'validation error' is logged
        """
        config_data: dict = {"steps": {}}
        with (
            patch(
                "ardupilot_methodic_configurator.backend_filesystem_configuration_steps.json_load",
                side_effect=[config_data, {}],
            ),
            patch(
                "ardupilot_methodic_configurator.backend_filesystem_configuration_steps.json_validate",
                side_effect=ValidationError("Schema validation failed"),
            ),
            patch("builtins.open", mock_open()),
            patch("os.path.join", side_effect=lambda *args: "/".join(args)),
            patch("os.path.abspath", return_value="abs_path"),
            patch("os.path.dirname", return_value="dir_name"),
            caplog.at_level(logging.ERROR),
        ):
            config_steps.re_init("vehicle_dir", "vehicle_type")

        assert any("validation error" in r.message.lower() for r in caplog.records)

    def test_re_init_logs_error_for_schema_json_decode_error(
        self, config_steps: ConfigurationSteps, caplog: pytest.LogCaptureFixture
    ) -> None:
        """
        A JSONDecodeError while reading the schema file is reported as an error.

        GIVEN: A valid config file and a schema file that raises JSONDecodeError on load
        WHEN: re_init is called
        THEN: An error mentioning 'schema' is logged
        """
        config_data: dict = {"steps": {}}
        schema_error = JSONDecodeError("bad json", "", 0)
        with (
            patch(
                "ardupilot_methodic_configurator.backend_filesystem_configuration_steps.json_load",
                side_effect=[config_data, schema_error],
            ),
            patch("builtins.open", mock_open()),
            patch("os.path.join", side_effect=lambda *args: "/".join(args)),
            patch("os.path.abspath", return_value="abs_path"),
            patch("os.path.dirname", return_value="dir_name"),
            caplog.at_level(logging.ERROR),
        ):
            config_steps.re_init("vehicle_dir", "vehicle_type")

        assert any("schema" in r.message.lower() for r in caplog.records)

    def test_re_init_loads_configuration_phases_with_module_level_patches(self, config_steps: ConfigurationSteps) -> None:
        """
        Configuration phases are populated when module-level json_load and json_validate are patched.

        GIVEN: json_load returns a config dict with phases and json_validate is patched at module level
        WHEN: re_init is called
        THEN: configuration_phases is populated with the expected phase data
        """
        config_data: dict = {"steps": {}, "phases": {"phase1": {"description": "Phase 1"}}}
        with (
            patch(
                "ardupilot_methodic_configurator.backend_filesystem_configuration_steps.json_load",
                side_effect=[config_data, {}],
            ),
            patch("ardupilot_methodic_configurator.backend_filesystem_configuration_steps.json_validate"),
            patch("builtins.open", mock_open()),
            patch("os.path.join", side_effect=lambda *args: "/".join(args)),
            patch("os.path.abspath", return_value="abs_path"),
            patch("os.path.dirname", return_value="dir_name"),
        ):
            config_steps.re_init("vehicle_dir", "vehicle_type")

        assert "phase1" in config_steps.configuration_phases
        assert config_steps.configuration_phases["phase1"]["description"] == "Phase 1"


# ---------------------------------------------------------------------------
# Parameter format validation
# ---------------------------------------------------------------------------


class TestParameterValidation:
    """Tests for __validate_parameters_in_configuration_steps() format-checking behavior."""

    def test_missing_new_value_attribute_is_logged_as_error(
        self, config_steps: ConfigurationSteps, caplog: pytest.LogCaptureFixture
    ) -> None:
        """
        A forced parameter missing 'New Value' triggers an error log.

        GIVEN: A file_info dict with a forced parameter that has no 'New Value' key
        WHEN: The parameter validator is called
        THEN: An error mentioning 'New Value' is logged
        """
        file_info = {"forced_parameters": {"PARAM1": {"Change Reason": "Test reason"}}}
        with caplog.at_level(logging.ERROR):
            config_steps._ConfigurationSteps__validate_parameters_in_configuration_steps(  # type: ignore[attr-defined]
                "test_file", file_info, "forced"
            )

        assert any("New Value" in message for message in caplog.messages)

    def test_missing_change_reason_attribute_is_logged_as_error(
        self, config_steps: ConfigurationSteps, caplog: pytest.LogCaptureFixture
    ) -> None:
        """
        A forced parameter missing 'Change Reason' triggers an error log.

        GIVEN: A file_info dict with a forced parameter that has no 'Change Reason' key
        WHEN: The parameter validator is called
        THEN: An error mentioning 'Change Reason' is logged
        """
        file_info = {"forced_parameters": {"PARAM1": {"New Value": "10"}}}
        with caplog.at_level(logging.ERROR):
            config_steps._ConfigurationSteps__validate_parameters_in_configuration_steps(  # type: ignore[attr-defined]
                "test_file", file_info, "forced"
            )

        assert any("Change Reason" in message for message in caplog.messages)

    def test_validation_passes_silently_for_empty_parameters_dict(self, config_steps: ConfigurationSteps) -> None:
        """
        An empty forced_parameters dict produces no errors or exceptions.

        GIVEN: A file_info dict with an empty forced_parameters section
        WHEN: The parameter validator is called
        THEN: No exception is raised and execution completes normally
        """
        file_info = {"forced_parameters": {}}
        config_steps._ConfigurationSteps__validate_parameters_in_configuration_steps(  # type: ignore[attr-defined]
            "test_file", file_info, "forced"
        )

    def test_add_from_fc_shorthand_derived_parameter_is_silently_skipped(self, config_steps: ConfigurationSteps) -> None:
        """
        A derived parameter with only an 'if' key and no 'New Value' is silently skipped.

        GIVEN: A file_info with a derived parameter entry containing only 'if' (no 'New Value')
        WHEN: __validate_parameters_in_configuration_steps is called for derived parameters
        THEN: No error is logged and execution completes normally (add-from-FC shorthand)
        """
        file_info = {"derived_parameters": {"PARAM1": {"if": "some_condition"}}}
        with patch("ardupilot_methodic_configurator.backend_filesystem_configuration_steps.logging_error") as mock_error:
            config_steps._ConfigurationSteps__validate_parameters_in_configuration_steps(  # type: ignore[attr-defined]
                "test_file", file_info, "derived"
            )

        mock_error.assert_not_called()

    def test_non_dict_parameter_section_is_logged_as_error(self, config_steps: ConfigurationSteps) -> None:
        """
        A forced_parameters section that is not a dict triggers an error log during re_init.

        GIVEN: A configuration file where forced_parameters is a string instead of a dict
        WHEN: re_init processes the file
        THEN: An error mentioning 'is not a dictionary' is logged
        """
        read_data = '{"steps": {"test_file": {"forced_parameters": "not_a_dict"}}}'
        with (
            patch("builtins.open", new_callable=mock_open, read_data=read_data),
            patch("os.path.join", return_value="test_path"),
            patch("os.path.dirname", return_value="dir_name"),
            patch("os.path.abspath", return_value="abs_path"),
            patch("jsonschema.validate"),
            patch("ardupilot_methodic_configurator.backend_filesystem_configuration_steps.logging_error") as mock_error,
        ):
            config_steps.re_init("vehicle_dir", "vehicle_type")

        assert any("is not a dictionary" in str(args) for args, _ in mock_error.call_args_list)

    def test_delete_parameters_section_not_a_dict_is_logged_as_error(
        self, config_steps: ConfigurationSteps, caplog: pytest.LogCaptureFixture
    ) -> None:
        """
        A delete_parameters section that is not a dict triggers an error log.

        GIVEN: A file_info where delete_parameters is a string instead of a dict
        WHEN: __validate_delete_parameters_in_configuration_steps is called
        THEN: An error mentioning 'is not a dictionary' is logged
        """
        file_info = {"delete_parameters": "not_a_dict"}
        with caplog.at_level(logging.ERROR):
            config_steps._ConfigurationSteps__validate_delete_parameters_in_configuration_steps(  # type: ignore[attr-defined]
                "test_file", file_info
            )

        assert any("is not a dictionary" in m for m in caplog.messages)

    def test_delete_parameter_entry_not_a_dict_is_logged_as_error(
        self, config_steps: ConfigurationSteps, caplog: pytest.LogCaptureFixture
    ) -> None:
        """
        A delete_parameters entry whose value is not a dict triggers an error log.

        GIVEN: A file_info where a delete_parameter value is a string instead of a dict
        WHEN: __validate_delete_parameters_in_configuration_steps is called
        THEN: An error mentioning 'is not a dictionary' is logged for that entry
        """
        file_info = {"delete_parameters": {"PARAM1": "not_a_dict"}}
        with caplog.at_level(logging.ERROR):
            config_steps._ConfigurationSteps__validate_delete_parameters_in_configuration_steps(  # type: ignore[attr-defined]
                "test_file", file_info
            )

        assert any("is not a dictionary" in m for m in caplog.messages)

    def test_delete_parameter_with_unknown_keys_is_logged_as_error(
        self, config_steps: ConfigurationSteps, caplog: pytest.LogCaptureFixture
    ) -> None:
        """
        A delete_parameters entry with unexpected keys beyond 'if' triggers an error log.

        GIVEN: A file_info where a delete_parameter has both 'if' and an unexpected key
        WHEN: __validate_delete_parameters_in_configuration_steps is called
        THEN: An error mentioning 'unexpected keys' is logged
        """
        file_info = {"delete_parameters": {"PARAM1": {"if": "True", "unexpected_key": "value"}}}
        with caplog.at_level(logging.ERROR):
            config_steps._ConfigurationSteps__validate_delete_parameters_in_configuration_steps(  # type: ignore[attr-defined]
                "test_file", file_info
            )

        assert any("unexpected keys" in m for m in caplog.messages)

    def test_validation_warns_when_parameter_in_both_derived_and_delete(
        self, config_steps: ConfigurationSteps, caplog: pytest.LogCaptureFixture
    ) -> None:
        """
        A parameter appearing in both derived_parameters and delete_parameters should log a WARNING.

        Such a configuration is almost certainly a mistake: the derived value would be immediately
        removed, or the delete would defeat the derived setting.

        GIVEN: A file_info where PARAM1 is listed in both derived_parameters and delete_parameters
        WHEN: re_init processes the file
        THEN: A WARNING mentioning 'PARAM1' and both sections is logged

        REGRESSION: Previously no cross-validation existed between these two sections.
        """
        read_data = (
            '{"steps": {"test_file": {'
            '"derived_parameters": {"PARAM1": {"New Value": "10", "Change Reason": "test"}},'
            '"delete_parameters": {"PARAM1": {}}'
            "}}}"
        )
        with (
            patch("builtins.open", new_callable=mock_open, read_data=read_data),
            patch("os.path.join", side_effect=lambda *args: "/".join(args)),
            patch("os.path.abspath", return_value="abs_path"),
            patch("os.path.dirname", return_value="dir_name"),
            patch("ardupilot_methodic_configurator.backend_filesystem_configuration_steps.json_validate"),
            caplog.at_level(logging.WARNING),
        ):
            config_steps.re_init("vehicle_dir", "vehicle_type")

        assert any("PARAM1" in r.message and r.levelno == logging.WARNING for r in caplog.records)

    def test_validation_errors_when_derived_add_from_fc_shorthand_has_unexpected_keys(
        self, config_steps: ConfigurationSteps, caplog: pytest.LogCaptureFixture
    ) -> None:
        """
        A derived add-from-FC shorthand entry (no 'New Value') that contains keys other than 'if' should log an ERROR.

        GIVEN: A derived parameter with no 'New Value' but with an unrecognised key 'Typo'
        WHEN: re_init processes the file
        THEN: An ERROR-level message mentioning the unexpected key is logged

        REGRESSION: Line 175 — the logging_error branch for unexpected keys on shorthand entries.
        """
        read_data = '{"steps": {"test_file": {"derived_parameters": {"INS_TCAL2_ENABLE": {"Typo": "oops"}}}}}'
        with (
            patch("builtins.open", new_callable=mock_open, read_data=read_data),
            patch("os.path.join", side_effect=lambda *args: "/".join(args)),
            patch("os.path.abspath", return_value="abs_path"),
            patch("os.path.dirname", return_value="dir_name"),
            patch("ardupilot_methodic_configurator.backend_filesystem_configuration_steps.json_validate"),
            caplog.at_level(logging.ERROR),
        ):
            config_steps.re_init("vehicle_dir", "vehicle_type")

        assert any(
            "INS_TCAL2_ENABLE" in r.message and "unexpected" in r.message and r.levelno == logging.ERROR
            for r in caplog.records
        )


# ---------------------------------------------------------------------------
# compute_parameters — forced and derived parameter computation
# ---------------------------------------------------------------------------


class TestParameterComputation:
    """Tests for compute_parameters() behavior with forced and derived parameters."""

    def test_forced_parameter_is_computed_and_stored(self, config_steps: ConfigurationSteps) -> None:
        """
        A valid forced parameter expression is evaluated and stored with its change reason.

        GIVEN: A forced parameter with a literal numeric expression
        WHEN: compute_parameters is called
        THEN: The parameter is stored with the correct value and comment
        """
        file_info = {"forced_parameters": {"PARAM1": {"New Value": "10", "Change Reason": "Test reason"}}}
        variables: dict = {"doc_dict": {"PARAM1": {"values": {10: "value"}}}}

        result = config_steps.compute_parameters("test_file", file_info, "forced", variables)

        assert result == ""
        assert config_steps.forced_parameters["test_file"]["PARAM1"].value == 10
        assert config_steps.forced_parameters["test_file"]["PARAM1"].comment == "Test reason"

    def test_forced_bitmask_string_is_resolved_to_numeric_value(self, config_steps: ConfigurationSteps) -> None:
        """
        A string result matching a Bitmask entry is converted to its numeric power-of-two value.

        GIVEN: A forced parameter expression returning a string matching a bitmask label
        WHEN: compute_parameters is called with doc_dict containing bitmask metadata
        THEN: The stored value equals 2 raised to the bitmask key
        """
        file_info = {"forced_parameters": {"PARAM1": {"New Value": "'bitmask_option'", "Change Reason": "Test reason"}}}
        variables: dict = {"doc_dict": {"PARAM1": {"values": {}, "Bitmask": {2: "bitmask_option"}}}}

        result = config_steps.compute_parameters("test_file", file_info, "forced", variables)

        assert result == ""
        assert config_steps.forced_parameters["test_file"]["PARAM1"].value == 4  # 2^2

    def test_empty_file_info_results_in_no_parameters_stored(self, config_steps: ConfigurationSteps) -> None:
        """
        An empty file_info produces no stored parameters and no error.

        GIVEN: An empty file_info dict (no forced_parameters key)
        WHEN: compute_parameters is called
        THEN: No parameters are stored and the returned error string is empty
        """
        result = config_steps.compute_parameters("test_file", {}, "forced", {"doc_dict": {}})

        assert result == ""
        assert not config_steps.forced_parameters

    def test_empty_variables_dict_skips_computation(self, config_steps: ConfigurationSteps) -> None:
        """
        An empty variables dict causes compute_parameters to skip all computation.

        GIVEN: A valid file_info with forced parameters and an empty variables dict
        WHEN: compute_parameters is called
        THEN: No parameters are stored and no error is returned
        """
        file_info = {"forced_parameters": {"PARAM1": {"New Value": "10", "Change Reason": "Test"}}}

        result = config_steps.compute_parameters("test_file", file_info, "forced", {})

        assert result == ""
        assert not config_steps.forced_parameters

    def test_invalid_expression_returns_evaluation_error(self, config_steps: ConfigurationSteps) -> None:
        """
        An expression referencing an undefined name returns an evaluation error.

        GIVEN: A forced parameter whose 'New Value' references an undefined variable
        WHEN: compute_parameters is called
        THEN: The returned string reports an evaluation error for that parameter
        """
        file_info = {"forced_parameters": {"PARAM1": {"New Value": "invalid_expression", "Change Reason": "Test reason"}}}
        variables: dict = {"doc_dict": {"PARAM1": {"values": {10: "value"}}}}

        result = config_steps.compute_parameters("test_file", file_info, "forced", variables)

        assert "could not be evaluated" in result
        assert "NameNotDefined" in result

    def test_missing_fc_parameters_key_reports_key_error(self, config_steps: ConfigurationSteps) -> None:
        """
        Subscripting a key that does not exist in fc_parameters returns an evaluation error.

        GIVEN: A forced parameter subscripting a missing key in fc_parameters
        WHEN: compute_parameters is called with fc_parameters lacking that key
        THEN: The error identifies the parameter and the missing key
        """
        file_info = {
            "forced_parameters": {"PARAM1": {"New Value": "fc_parameters['DOES_NOT_EXIST'] * 2", "Change Reason": "Test"}}
        }
        variables: dict = {"doc_dict": {"PARAM1": {"values": {}}}, "fc_parameters": {"OTHER": 1.0}}

        result = config_steps.compute_parameters("test_file", file_info, "forced", variables)

        assert "could not be evaluated" in result
        assert "KeyError" in result
        assert "DOES_NOT_EXIST" in result

    def test_type_error_in_expression_is_reported(self, config_steps: ConfigurationSteps) -> None:
        """
        An expression with incompatible operand types returns a typed evaluation error.

        GIVEN: A forced parameter expression that adds a string to an integer
        WHEN: compute_parameters is called
        THEN: The error identifies the parameter and mentions TypeError
        """
        file_info = {"forced_parameters": {"PARAM1": {"New Value": "'abc' + 1", "Change Reason": "Test"}}}
        variables: dict = {"doc_dict": {"PARAM1": {"values": {}}}}

        result = config_steps.compute_parameters("test_file", file_info, "forced", variables)

        assert "could not be evaluated" in result
        assert "TypeError" in result

    def test_string_result_resolved_via_values_lookup(self, config_steps: ConfigurationSteps) -> None:
        """
        A string evaluation result is resolved to its numeric key from doc_dict values.

        GIVEN: A forced parameter expression returning a string that exists in the values dict
        WHEN: compute_parameters is called
        THEN: The stored value is the numeric key associated with that string
        """
        file_info = {"forced_parameters": {"PARAM1": {"New Value": "'value'", "Change Reason": "Test reason"}}}
        variables: dict = {"doc_dict": {"PARAM1": {"values": {10: "value"}}}}

        result = config_steps.compute_parameters("test_file", file_info, "forced", variables)

        assert result == ""
        assert config_steps.forced_parameters["test_file"]["PARAM1"].value == 10

    def test_fc_parameters_reference_without_fc_reports_error(self, config_steps: ConfigurationSteps) -> None:
        """
        Referencing fc_parameters in an expression when no FC is connected reports an error.

        GIVEN: A forced parameter expression referencing fc_parameters
        WHEN: compute_parameters is called without fc_parameters in variables
        THEN: The error mentions fc_parameters and asks whether an FC is connected
        """
        file_info = {"forced_parameters": {"PARAM1": {"New Value": "fc_parameters['P1']", "Change Reason": "Test"}}}
        variables: dict = {"doc_dict": {"PARAM1": {"values": {}}}}

        result = config_steps.compute_parameters("test_file", file_info, "forced", variables)

        assert "fc_parameters" in result
        assert "not defined" in result or "not found" in result

    def test_multiple_forced_parameters_all_computed_correctly(self, config_steps: ConfigurationSteps) -> None:
        """
        All parameters in a multi-parameter forced block are computed independently.

        GIVEN: A file with three forced parameters each having distinct values
        WHEN: compute_parameters is called
        THEN: All three parameters are stored with their correct values
        """
        file_info = {
            "forced_parameters": {
                "PARAM1": {"New Value": "10", "Change Reason": "Reason 1"},
                "PARAM2": {"New Value": "20", "Change Reason": "Reason 2"},
                "PARAM3": {"New Value": "30", "Change Reason": "Reason 3"},
            }
        }
        variables: dict = {
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

    def test_derived_parameter_is_computed_and_stored_with_change_reason(self, config_steps: ConfigurationSteps) -> None:
        """
        A derived parameter expression is evaluated and stored with its change reason as comment.

        GIVEN: A derived parameter with an arithmetic expression
        WHEN: compute_parameters is called with parameter_type='derived'
        THEN: The parameter is stored in derived_parameters with the correct value and comment
        """
        file_info = {"derived_parameters": {"PARAM1": {"New Value": "10 * 2", "Change Reason": "Test derived"}}}
        variables: dict = {"doc_dict": {"PARAM1": {"values": {20: "value"}}}}

        result = config_steps.compute_parameters("test_file", file_info, "derived", variables)

        assert result == ""
        assert config_steps.derived_parameters["test_file"]["PARAM1"].value == 20
        assert config_steps.derived_parameters["test_file"]["PARAM1"].comment == "Test derived"

    def test_fc_parameters_values_are_used_when_provided(self, config_steps: ConfigurationSteps) -> None:
        """
        An expression referencing fc_parameters is evaluated using the provided FC values.

        GIVEN: A forced parameter expression multiplying an FC parameter value
        WHEN: compute_parameters is called with fc_parameters in variables
        THEN: The stored value reflects the computation against the FC value
        """
        file_info = {"forced_parameters": {"PARAM1": {"New Value": "fc_parameters['P1'] * 2", "Change Reason": "Test FC"}}}
        variables: dict = {"doc_dict": {"PARAM1": {"values": {20: "value"}}}, "fc_parameters": {"P1": 10}}

        result = config_steps.compute_parameters("test_file", file_info, "forced", variables)

        assert result == ""
        assert config_steps.forced_parameters["test_file"]["PARAM1"].value == 20

    def test_parameter_not_in_doc_dict_reports_error(self, config_steps: ConfigurationSteps) -> None:
        """
        A string result for a parameter absent from doc_dict produces a computed error.

        GIVEN: A forced parameter returning a string, but the parameter has no doc_dict entry
        WHEN: compute_parameters is called
        THEN: An error is returned and the parameter is not stored
        """
        file_info = {"forced_parameters": {"PARAM1": {"New Value": "'unknown_value'", "Change Reason": "Test"}}}
        variables: dict = {"doc_dict": {"PARAM2": {"values": {}}}}  # PARAM1 absent

        result = config_steps.compute_parameters("test_file", file_info, "forced", variables)

        assert "could not be computed" in result or "not found" in result
        assert "PARAM1" not in config_steps.forced_parameters.get("test_file", {})

    def test_float_result_is_stored_with_correct_precision(self, config_steps: ConfigurationSteps) -> None:
        """
        A parameter expression evaluating to a float is stored as-is.

        GIVEN: A forced parameter with a float literal expression
        WHEN: compute_parameters is called
        THEN: The stored value equals the float exactly
        """
        file_info = {"forced_parameters": {"PARAM1": {"New Value": "10.5", "Change Reason": "Test float"}}}
        variables: dict = {"doc_dict": {"PARAM1": {"values": {}}}}

        result = config_steps.compute_parameters("test_file", file_info, "forced", variables)

        assert result == ""
        assert config_steps.forced_parameters["test_file"]["PARAM1"].value == 10.5

    def test_complex_expression_is_evaluated_correctly(self, config_steps: ConfigurationSteps) -> None:
        """
        A compound arithmetic expression is fully evaluated before storing.

        GIVEN: A forced parameter with a multi-operator arithmetic expression
        WHEN: compute_parameters is called
        THEN: The stored value equals the fully computed result
        """
        file_info = {"forced_parameters": {"PARAM1": {"New Value": "10 * 2 + 5", "Change Reason": "Complex calculation"}}}
        variables: dict = {"doc_dict": {"PARAM1": {"values": {}}}}

        result = config_steps.compute_parameters("test_file", file_info, "forced", variables)

        assert result == ""
        assert config_steps.forced_parameters["test_file"]["PARAM1"].value == 25

    def test_expression_can_read_values_from_doc_dict(self, config_steps: ConfigurationSteps) -> None:
        """
        A parameter expression that reads from doc_dict produces the correct derived value.

        GIVEN: Two forced parameters where the second reads values from doc_dict
        WHEN: compute_parameters is called
        THEN: Both parameters are stored with the correct values
        """
        file_info = {
            "forced_parameters": {
                "PARAM1": {"New Value": "10", "Change Reason": "Base value"},
                "PARAM2": {
                    "New Value": "doc_dict['PARAM1']['values'][10] == 'value1' and 20 or 30",
                    "Change Reason": "Lookup",
                },
            }
        }
        variables: dict = {"doc_dict": {"PARAM1": {"values": {10: "value1"}}, "PARAM2": {"values": {}}}}

        result = config_steps.compute_parameters("test_file", file_info, "forced", variables)

        assert result == ""
        assert config_steps.forced_parameters["test_file"]["PARAM2"].value == 20

    def test_string_value_not_found_in_values_dict_returns_error(self, config_steps: ConfigurationSteps) -> None:
        """
        A string result not present in the doc_dict values dict triggers an error.

        GIVEN: A forced parameter returning a string that has no match in the values dict
        WHEN: compute_parameters is called
        THEN: A non-empty error string is returned
        """
        file_info = {
            "forced_parameters": {"PARAM1": {"New Value": "'value with \\'quotes\\''", "Change Reason": "Test escapes"}}
        }
        variables: dict = {"doc_dict": {"PARAM1": {"values": {10: "value"}}}}

        result = config_steps.compute_parameters("test_file", file_info, "forced", variables)

        assert result != ""

    def test_derived_undefined_variable_is_silently_skipped(self, config_steps: ConfigurationSteps) -> None:
        """
        A derived parameter referencing an undefined variable is silently skipped (no error returned).

        GIVEN: A derived parameter expression referencing an undefined variable
        WHEN: compute_parameters is called
        THEN: No error string is returned and no parameter is stored
        """
        file_info = {"derived_parameters": {"PARAM1": {"New Value": "undefined_var", "Change Reason": "Test warning"}}}
        variables: dict = {"doc_dict": {"PARAM1": {"values": {}}}}

        result = config_steps.compute_parameters("test_file", file_info, "derived", variables)

        assert result == ""
        assert "test_file" not in config_steps.derived_parameters

    def test_forced_inf_result_is_rejected_with_non_finite_error(self, config_steps: ConfigurationSteps) -> None:
        """
        A forced parameter evaluating to infinity returns a non-finite error and is not stored.

        GIVEN: A forced parameter expression that overflows to infinity (1e309)
        WHEN: compute_parameters is called
        THEN: An error mentioning 'non-finite' is returned and the parameter is not stored
        """
        file_info = {"forced_parameters": {"PARAM1": {"New Value": "1e309", "Change Reason": "Test"}}}
        variables: dict = {"doc_dict": {"PARAM1": {"values": {}}}}

        result = config_steps.compute_parameters("test_file", file_info, "forced", variables)

        assert "non-finite" in result
        assert "test_file" not in config_steps.forced_parameters

    def test_forced_negative_inf_result_is_rejected_with_non_finite_error(self, config_steps: ConfigurationSteps) -> None:
        """
        A forced parameter evaluating to negative infinity returns a non-finite error.

        GIVEN: A forced parameter expression that underflows to negative infinity (-1e309)
        WHEN: compute_parameters is called
        THEN: An error mentioning 'non-finite' is returned and the parameter is not stored
        """
        file_info = {"forced_parameters": {"PARAM1": {"New Value": "-1e309", "Change Reason": "Test"}}}
        variables: dict = {"doc_dict": {"PARAM1": {"values": {}}}}

        result = config_steps.compute_parameters("test_file", file_info, "forced", variables)

        assert "non-finite" in result
        assert "test_file" not in config_steps.forced_parameters

    def test_derived_inf_result_is_silently_skipped(self, config_steps: ConfigurationSteps) -> None:
        """
        A derived parameter evaluating to infinity is silently skipped without error.

        GIVEN: A derived parameter expression that overflows to infinity (1e309)
        WHEN: compute_parameters is called
        THEN: No error is returned and no parameter is stored
        """
        file_info = {"derived_parameters": {"PARAM1": {"New Value": "1e309", "Change Reason": "Test"}}}
        variables: dict = {"doc_dict": {"PARAM1": {"values": {}}}}

        result = config_steps.compute_parameters("test_file", file_info, "derived", variables)

        assert result == ""
        assert "test_file" not in config_steps.derived_parameters

    def test_error_in_one_forced_parameter_does_not_skip_remaining(self, config_steps: ConfigurationSteps) -> None:
        """
        A failure in one forced parameter does not prevent the others from being computed.

        GIVEN: Three forced parameters where the middle one has an invalid expression
        WHEN: compute_parameters is called
        THEN: The error names the bad parameter and the two valid parameters are stored
        """
        file_info = {
            "forced_parameters": {
                "GOOD_PARAM1": {"New Value": "10", "Change Reason": "Reason 1"},
                "BAD_PARAM": {"New Value": "undefined_var + 1", "Change Reason": "Will fail"},
                "GOOD_PARAM2": {"New Value": "20", "Change Reason": "Reason 2"},
            }
        }
        variables: dict = {
            "doc_dict": {
                "GOOD_PARAM1": {"values": {10: "value1"}},
                "BAD_PARAM": {"values": {}},
                "GOOD_PARAM2": {"values": {20: "value2"}},
            }
        }

        result = config_steps.compute_parameters("test_file", file_info, "forced", variables)

        assert "BAD_PARAM" in result
        assert config_steps.forced_parameters["test_file"]["GOOD_PARAM1"].value == 10
        assert config_steps.forced_parameters["test_file"]["GOOD_PARAM2"].value == 20

    def test_multiple_forced_parameter_errors_are_all_collected(self, config_steps: ConfigurationSteps) -> None:
        """
        All forced parameter errors are collected and returned as a newline-joined string.

        GIVEN: Four forced parameters where two have invalid expressions
        WHEN: compute_parameters is called
        THEN: The returned error string names both bad parameters separated by a newline
        """
        file_info = {
            "forced_parameters": {
                "GOOD1": {"New Value": "10", "Change Reason": "Reason 1"},
                "BAD1": {"New Value": "undefined_a", "Change Reason": "Fail 1"},
                "GOOD2": {"New Value": "20", "Change Reason": "Reason 2"},
                "BAD2": {"New Value": "undefined_b", "Change Reason": "Fail 2"},
            }
        }
        variables: dict = {
            "doc_dict": {
                "GOOD1": {"values": {10: "value1"}},
                "BAD1": {"values": {}},
                "GOOD2": {"values": {20: "value2"}},
                "BAD2": {"values": {}},
            }
        }

        result = config_steps.compute_parameters("test_file", file_info, "forced", variables)

        assert "BAD1" in result
        assert "BAD2" in result
        assert "\n" in result
        assert config_steps.forced_parameters["test_file"]["GOOD1"].value == 10
        assert config_steps.forced_parameters["test_file"]["GOOD2"].value == 20

    def test_safe_log_function_is_whitelisted_in_evaluator(self, config_steps: ConfigurationSteps) -> None:
        """
        The log() function is available in the safe evaluator for realistic math expressions.

        GIVEN: A forced parameter using log() from the whitelisted safe math functions
        WHEN: compute_parameters is called with vehicle_components data
        THEN: The computed value matches the expected mathematical result
        """
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
        variables: dict = {
            "doc_dict": {"MOT_THST_EXPO": {"values": {}}},
            "vehicle_components": {"Propellers": {"Specifications": {"Diameter_inches": 10}}},
        }

        result = config_steps.compute_parameters("test_file", file_info, "forced", variables)

        assert result == ""
        assert abs(config_steps.forced_parameters["test_file"]["MOT_THST_EXPO"].value - 0.6) < 0.01

    def test_import_expression_is_blocked_by_safe_evaluator(self, config_steps: ConfigurationSteps) -> None:
        """
        A __import__ expression is rejected by the safe evaluator.

        GIVEN: A forced parameter expression attempting to call __import__
        WHEN: compute_parameters is called
        THEN: An error is returned and the parameter is not stored
        """
        file_info = {
            "forced_parameters": {
                "PARAM1": {"New Value": "__import__('os').system('echo pwned')", "Change Reason": "Malicious"},
            }
        }
        variables: dict = {"doc_dict": {"PARAM1": {"values": {}}}}

        result = config_steps.compute_parameters("test_file", file_info, "forced", variables)

        assert result != ""
        assert "PARAM1" in result
        assert "test_file" not in config_steps.forced_parameters

    def test_builtins_access_is_blocked_by_safe_evaluator(self, config_steps: ConfigurationSteps) -> None:
        """
        Accessing __builtins__ is rejected by the safe evaluator.

        GIVEN: A forced parameter expression attempting to access __builtins__
        WHEN: compute_parameters is called
        THEN: An error is returned and the parameter is not stored
        """
        file_info = {
            "forced_parameters": {
                "PARAM1": {"New Value": "__builtins__.__import__('os').system('id')", "Change Reason": "Malicious"},
            }
        }
        variables: dict = {"doc_dict": {"PARAM1": {"values": {}}}}

        result = config_steps.compute_parameters("test_file", file_info, "forced", variables)

        assert result != ""
        assert "PARAM1" in result
        assert "test_file" not in config_steps.forced_parameters

    def test_ignore_fc_derived_param_warnings_suppresses_derived_error_logging(self, config_steps: ConfigurationSteps) -> None:
        """
        Derived parameter errors are suppressed when ignore_fc_derived_param_warnings is True.

        GIVEN: A derived parameter referencing a missing key in fc_parameters
        WHEN: compute_parameters is called with ignore_fc_derived_param_warnings=True
        THEN: An empty string is returned and no warning is logged
        """
        file_info = {"derived_parameters": {"PARAM1": {"New Value": "fc_parameters['MISSING']", "Change Reason": "Test"}}}
        variables: dict = {"doc_dict": {"PARAM1": {"values": {}}}, "fc_parameters": {}}
        with patch("ardupilot_methodic_configurator.backend_filesystem_configuration_steps.logging_warning") as mock_warn:
            result = config_steps.compute_parameters(
                "test_file", file_info, "derived", variables, ignore_fc_derived_param_warnings=True
            )

        assert result == ""
        mock_warn.assert_not_called()

    def test_string_result_with_empty_values_and_bitmask_reports_no_metadata_error(
        self, config_steps: ConfigurationSteps
    ) -> None:
        """
        A string result with empty values and empty bitmasks returns an explicit 'no metadata' error.

        GIVEN: A forced parameter returning a string, with empty values and empty Bitmask in doc_dict
        WHEN: compute_parameters is called
        THEN: _resolve_string_result returns a descriptive error instead of silently passing the raw
              string through to float(), which would produce an obscure 'could not be computed' message
        """
        file_info = {"forced_parameters": {"PARAM1": {"New Value": "'some_string'", "Change Reason": "Test"}}}
        variables: dict = {"doc_dict": {"PARAM1": {"values": {}, "Bitmask": {}}}}

        result = config_steps.compute_parameters("test_file", file_info, "forced", variables)

        assert "has no documentation metadata values or bitmasks" in result
        assert "PARAM1" not in config_steps.forced_parameters.get("test_file", {})

    def test_string_result_not_found_in_nonempty_values_dict_reports_error(self, config_steps: ConfigurationSteps) -> None:
        """
        A string result absent from a non-empty values dict triggers a 'not found in values' error.

        GIVEN: A forced parameter returning a string that does not appear as a value in doc_dict
        WHEN: compute_parameters is called with a non-empty values mapping
        THEN: An error mentioning 'not found in documentation metadata values' is returned
        """
        file_info = {"forced_parameters": {"PARAM1": {"New Value": "'nonexistent_value'", "Change Reason": "Test"}}}
        variables: dict = {"doc_dict": {"PARAM1": {"values": {10: "existing_value", 20: "another_value"}}}}

        result = config_steps.compute_parameters("test_file", file_info, "forced", variables)

        assert "not found in documentation metadata values" in result
        assert "PARAM1" not in config_steps.forced_parameters.get("test_file", {})

    def test_string_result_not_found_in_bitmask_dict_reports_error(self, config_steps: ConfigurationSteps) -> None:
        """
        A string result absent from a non-empty bitmask dict triggers a 'not found in bitmasks' error.

        GIVEN: A forced parameter returning a string not present in the doc_dict Bitmask mapping
        WHEN: compute_parameters is called with an empty values dict and a non-empty Bitmask dict
        THEN: An error mentioning 'not found in documentation metadata bitmasks' is returned
        """
        file_info = {"forced_parameters": {"PARAM1": {"New Value": "'nonexistent_bitmask'", "Change Reason": "Test"}}}
        variables: dict = {"doc_dict": {"PARAM1": {"values": {}, "Bitmask": {2: "existing_bitmask", 3: "another"}}}}

        result = config_steps.compute_parameters("test_file", file_info, "forced", variables)

        assert "not found in documentation metadata bitmasks" in result
        assert "PARAM1" not in config_steps.forced_parameters.get("test_file", {})

    def test_forced_parameter_error_is_not_logged_inside_handle_param_error(self) -> None:
        """
        _handle_param_error must not internally call logging_error for forced parameters.

        Logging is the caller's responsibility once the error propagates as a ValueError.
        Double-logging would show the same message twice in the user-facing error log.

        GIVEN: A forced parameter error string
        WHEN: _handle_param_error is called with parameter_type='forced'
        THEN: logging_error is NOT called inside _handle_param_error and the message is returned

        REGRESSION: Previously _handle_param_error called logging_error AND returned the message,
        which caused the error to be logged twice — once here and once by the __main__ ValueError handler.
        """
        with patch("ardupilot_methodic_configurator.backend_filesystem_configuration_steps.logging_error") as mock_error:
            result = ConfigurationSteps._handle_param_error("test forced error", "forced")

        mock_error.assert_not_called()
        assert result == "test forced error"

    def test_stale_forced_parameter_is_cleared_when_condition_becomes_false(self, config_steps: ConfigurationSteps) -> None:
        """
        A forced parameter computed in a previous call must not persist when its condition is now False.

        GIVEN: A forced parameter with an 'if' guard that was True on call 1
        WHEN: compute_parameters is called a second time with the guard evaluating to False
        THEN: The parameter is absent from forced_parameters after the second call

        REGRESSION: Previously the entry from call 1 remained in self.forced_parameters and was
        merged into the working copy even though the condition no longer held.
        """
        file_info = {"forced_parameters": {"PARAM1": {"if": "flag", "New Value": "42", "Change Reason": "test"}}}
        variables_true: dict = {"doc_dict": {}, "flag": True}
        variables_false: dict = {"doc_dict": {}, "flag": False}

        config_steps.compute_parameters("test_file", file_info, "forced", variables_true)
        assert "PARAM1" in config_steps.forced_parameters.get("test_file", {})

        config_steps.compute_parameters("test_file", file_info, "forced", variables_false)
        assert "PARAM1" not in config_steps.forced_parameters.get("test_file", {})

    def test_stale_derived_parameter_is_cleared_when_condition_becomes_false(self, config_steps: ConfigurationSteps) -> None:
        """
        A derived parameter computed in a previous call must not persist when its condition is now False.

        GIVEN: A derived parameter with an 'if' guard that was True on call 1
        WHEN: compute_parameters is called a second time with the guard evaluating to False
        THEN: The parameter is absent from derived_parameters after the second call

        REGRESSION: Same stale-state bug as the forced parameter variant.
        """
        file_info = {"derived_parameters": {"PARAM1": {"if": "flag", "New Value": "42", "Change Reason": "test"}}}
        variables_true: dict = {"doc_dict": {}, "flag": True}
        variables_false: dict = {"doc_dict": {}, "flag": False}

        config_steps.compute_parameters("test_file", file_info, "derived", variables_true)
        assert "PARAM1" in config_steps.derived_parameters.get("test_file", {})

        config_steps.compute_parameters("test_file", file_info, "derived", variables_false)
        assert "PARAM1" not in config_steps.derived_parameters.get("test_file", {})


# ---------------------------------------------------------------------------
# _condition_passes — conditional guard evaluation
# ---------------------------------------------------------------------------


class TestConditionEvaluation:
    """Tests for _condition_passes() — the 'if' guard evaluator."""

    def test_no_if_key_always_passes(self) -> None:
        """
        An entry with no 'if' key always passes unconditionally.

        GIVEN: A parameter_info dict with no 'if' key
        WHEN: _condition_passes is called
        THEN: True is returned
        """
        assert ConfigurationSteps._condition_passes({}, {}) is True

    def test_true_condition_passes(self) -> None:
        """
        An 'if' expression that evaluates to True causes the condition to pass.

        GIVEN: A parameter_info with if='1 == 1'
        WHEN: _condition_passes is called
        THEN: True is returned
        """
        assert ConfigurationSteps._condition_passes({"if": "1 == 1"}, {}) is True

    def test_false_condition_fails(self) -> None:
        """
        An 'if' expression that evaluates to False causes the condition to fail.

        GIVEN: A parameter_info with if='1 == 2'
        WHEN: _condition_passes is called
        THEN: False is returned
        """
        assert ConfigurationSteps._condition_passes({"if": "1 == 2"}, {}) is False

    def test_syntax_error_in_condition_logs_warning_and_returns_false(self, caplog: pytest.LogCaptureFixture) -> None:
        """
        A syntactically invalid 'if' expression logs a warning and returns False.

        GIVEN: A parameter_info with an unparsable 'if' expression
        WHEN: _condition_passes is called
        THEN: False is returned and a warning mentioning 'syntax error' is logged
        """
        with caplog.at_level(logging.WARNING):
            result = ConfigurationSteps._condition_passes({"if": "this is not valid python !!!"}, {})

        assert result is False
        assert any("syntax error" in r.message.lower() for r in caplog.records)

    def test_missing_fc_parameters_variable_is_silently_skipped(self, config_steps: ConfigurationSteps) -> None:
        """
        A NameError for fc_parameters is suppressed without logging a warning.

        GIVEN: A condition that references fc_parameters, which is absent from variables
        WHEN: _condition_passes is called
        THEN: False is returned and no warning is logged
        """
        with patch("ardupilot_methodic_configurator.backend_filesystem_configuration_steps.logging_warning") as mock_warn:
            result = config_steps._condition_passes({"if": "'PARAM' in fc_parameters"}, {})

        assert result is False
        mock_warn.assert_not_called()

    def test_condition_with_provided_variables_is_evaluated_correctly(self) -> None:
        """
        A condition expression correctly uses values from the supplied variables dict.

        GIVEN: A condition 'x > 0' and variables containing x
        WHEN: _condition_passes is called with x=5 and then x=-1
        THEN: True is returned for x=5 and False for x=-1
        """
        assert ConfigurationSteps._condition_passes({"if": "x > 0"}, {"x": 5}) is True
        assert ConfigurationSteps._condition_passes({"if": "x > 0"}, {"x": -1}) is False

    def test_non_name_non_syntax_error_in_condition_logs_warning_message(self, caplog: pytest.LogCaptureFixture) -> None:
        """
        A runtime error other than an undefined name or SyntaxError logs a warning and returns False.

        GIVEN: A condition expression that causes a ZeroDivisionError at evaluation time
        WHEN: _condition_passes is called
        THEN: False is returned and a WARNING-level message mentioning 'could not be evaluated' is logged
        """
        with caplog.at_level(logging.WARNING):
            result = ConfigurationSteps._condition_passes({"if": "1/0"}, {})

        assert result is False
        assert any("could not be evaluated" in r.message.lower() for r in caplog.records if r.levelno == logging.WARNING)

    def test_condition_passes_warns_when_undefined_name_is_not_fc_parameters(self, caplog: pytest.LogCaptureFixture) -> None:
        """
        An undefined name that is NOT 'fc_parameters' should log a WARNING (likely a typo in the JSON config).

        GIVEN: A condition 'typo_variable > 0' where 'typo_variable' is not in variables and is not fc_parameters
        WHEN: _condition_passes is called
        THEN: False is returned and a WARNING-level message is logged

        REGRESSION: Previously ALL undefined-name errors were silently swallowed, hiding config typos.
        The silent treatment is correct only for 'fc_parameters' (expected to be absent when no FC connected).
        """
        with caplog.at_level(logging.WARNING):
            result = ConfigurationSteps._condition_passes({"if": "typo_variable > 0"}, {})

        assert result is False
        assert any(r.levelno == logging.WARNING for r in caplog.records)

    def test_condition_passes_logs_warning_not_debug_for_runtime_error(self, caplog: pytest.LogCaptureFixture) -> None:
        """
        A runtime error (e.g. ZeroDivisionError) in a condition must log at WARNING, not DEBUG.

        GIVEN: A condition expression '1/0' that raises ZeroDivisionError
        WHEN: _condition_passes is called
        THEN: False is returned and a WARNING-level message is logged

        REGRESSION: Previously this was logged at DEBUG, making it nearly invisible in production logs.
        """
        with caplog.at_level(logging.WARNING):
            result = ConfigurationSteps._condition_passes({"if": "1/0"}, {})

        assert result is False
        assert any(r.levelno == logging.WARNING for r in caplog.records)


# ---------------------------------------------------------------------------
# compute_deletions — conditional parameter removal
# ---------------------------------------------------------------------------


class TestParameterDeletion:
    """Tests for compute_deletions() — evaluating which parameters to remove."""

    def test_no_delete_parameters_section_returns_empty_set(self, config_steps: ConfigurationSteps) -> None:
        """
        An empty set is returned when file_info has no 'delete_parameters' key.

        GIVEN: A file_info dict with no delete_parameters section
        WHEN: compute_deletions is called
        THEN: An empty set is returned
        """
        assert config_steps.compute_deletions("test_file", {}, {"doc_dict": {}}) == set()

    def test_empty_variables_logs_warning_and_returns_empty_set(
        self, config_steps: ConfigurationSteps, caplog: pytest.LogCaptureFixture
    ) -> None:
        """
        An empty variables dict causes a warning and returns an empty set.

        GIVEN: A file_info with delete_parameters and an empty variables dict
        WHEN: compute_deletions is called
        THEN: An empty set is returned and a warning mentioning the filename is logged
        """
        file_info = {"delete_parameters": {"PARAM1": {}}}
        with caplog.at_level(logging.WARNING):
            result = config_steps.compute_deletions("test_file", file_info, {})

        assert result == set()
        assert any("test_file" in r.message for r in caplog.records)

    def test_parameter_without_condition_is_always_deleted(self, config_steps: ConfigurationSteps) -> None:
        """
        Parameters with no 'if' guard are always included in the deletion set.

        GIVEN: A delete_parameters section with two unconditional entries
        WHEN: compute_deletions is called
        THEN: Both parameter names appear in the returned set
        """
        file_info = {"delete_parameters": {"PARAM1": {}, "PARAM2": {}}}

        result = config_steps.compute_deletions("test_file", file_info, {"doc_dict": {}})

        assert result == {"PARAM1", "PARAM2"}

    def test_true_condition_marks_parameter_for_deletion(self, config_steps: ConfigurationSteps) -> None:
        """
        A parameter whose condition evaluates to True is marked for deletion.

        GIVEN: A delete_parameters entry with if='True'
        WHEN: compute_deletions is called
        THEN: That parameter name is in the returned set
        """
        file_info = {"delete_parameters": {"PARAM1": {"if": "True"}}}

        assert "PARAM1" in config_steps.compute_deletions("test_file", file_info, {"doc_dict": {}})

    def test_false_condition_keeps_parameter(self, config_steps: ConfigurationSteps) -> None:
        """
        A parameter whose condition evaluates to False is excluded from deletion.

        GIVEN: A delete_parameters entry with if='False'
        WHEN: compute_deletions is called
        THEN: That parameter name is NOT in the returned set
        """
        file_info = {"delete_parameters": {"PARAM1": {"if": "False"}}}

        assert "PARAM1" not in config_steps.compute_deletions("test_file", file_info, {"doc_dict": {}})

    def test_fc_not_connected_skips_deletion_silently(self, config_steps: ConfigurationSteps) -> None:
        """
        A condition referencing fc_parameters silently skips deletion when FC is not connected.

        GIVEN: A delete_parameters condition referencing fc_parameters, absent from variables
        WHEN: compute_deletions is called
        THEN: The parameter is NOT in the returned set
        """
        file_info = {"delete_parameters": {"PARAM1": {"if": "fc_parameters and ('PARAM1' not in fc_parameters)"}}}

        assert "PARAM1" not in config_steps.compute_deletions("test_file", file_info, {"doc_dict": {}})

    def test_syntax_error_in_deletion_condition_logs_warning(
        self, config_steps: ConfigurationSteps, caplog: pytest.LogCaptureFixture
    ) -> None:
        """
        A syntactically invalid deletion condition logs a warning and skips the parameter.

        GIVEN: A delete_parameters condition with invalid Python syntax
        WHEN: compute_deletions is called
        THEN: A warning mentioning 'syntax error' is logged and the parameter is not deleted
        """
        file_info = {"delete_parameters": {"PARAM1": {"if": "this is not valid python !!!"}}}
        with caplog.at_level(logging.WARNING):
            result = config_steps.compute_deletions("test_file", file_info, {"doc_dict": {}})

        assert "PARAM1" not in result
        assert any("syntax error" in r.message.lower() for r in caplog.records)

    def test_fc_parameters_condition_correctly_determines_deletion(self, config_steps: ConfigurationSteps) -> None:
        """
        An fc_parameters-based condition correctly includes or excludes parameters.

        GIVEN: A deletion condition that removes a parameter when it is absent from fc_parameters
        WHEN: compute_deletions is called first without the parameter, then with it
        THEN: The parameter is deleted when absent and kept when present
        """
        file_info = {
            "delete_parameters": {"INS_TCAL2_ENABLE": {"if": "fc_parameters and ('INS_TCAL2_ENABLE' not in fc_parameters)"}}
        }

        result_absent = config_steps.compute_deletions("test_file", file_info, {"fc_parameters": {"OTHER": 1.0}})
        result_present = config_steps.compute_deletions("test_file", file_info, {"fc_parameters": {"INS_TCAL2_ENABLE": 2.0}})

        assert "INS_TCAL2_ENABLE" in result_absent
        assert "INS_TCAL2_ENABLE" not in result_present


# ---------------------------------------------------------------------------
# add-from-FC shorthand — derived entries with only an 'if' guard
# ---------------------------------------------------------------------------


class TestAddFromFCShorthand:
    """Tests for the add-from-FC shorthand: derived entries with only an 'if' key and no 'New Value'."""

    def test_derived_parameter_is_populated_from_fc_when_present(self, config_steps: ConfigurationSteps) -> None:
        """
        A derived entry with only 'if' copies the parameter value from fc_parameters.

        GIVEN: A derived parameter with only an 'if' guard and the parameter exists in fc_parameters
        WHEN: compute_parameters is called
        THEN: The parameter is stored in derived_parameters with the FC value and an empty comment
        """
        file_info = {"derived_parameters": {"INS_TCAL2_ENABLE": {"if": "'INS_TCAL2_ENABLE' in fc_parameters"}}}
        variables: dict = {"doc_dict": {}, "fc_parameters": {"INS_TCAL2_ENABLE": 2.0}}

        result = config_steps.compute_parameters("test_file", file_info, "derived", variables)

        assert result == ""
        assert config_steps.derived_parameters["test_file"]["INS_TCAL2_ENABLE"].value == 2.0
        assert config_steps.derived_parameters["test_file"]["INS_TCAL2_ENABLE"].comment != ""

    def test_shorthand_is_silently_skipped_when_fc_not_connected(self, config_steps: ConfigurationSteps) -> None:
        """
        The add-from-FC shorthand is silently skipped when fc_parameters is absent.

        GIVEN: A derived parameter with only 'if' and no fc_parameters in variables
        WHEN: compute_parameters is called
        THEN: No error is returned and no parameter is stored
        """
        file_info = {"derived_parameters": {"INS_TCAL2_ENABLE": {"if": "'INS_TCAL2_ENABLE' in fc_parameters"}}}
        variables: dict = {"doc_dict": {}}

        result = config_steps.compute_parameters("test_file", file_info, "derived", variables)

        assert result == ""
        assert "test_file" not in config_steps.derived_parameters

    def test_shorthand_is_skipped_when_param_absent_from_fc(self, config_steps: ConfigurationSteps) -> None:
        """
        The add-from-FC shorthand skips a parameter not present in the FC's parameter set.

        GIVEN: A derived entry with if='True' and fc_parameters that does not contain that parameter
        WHEN: compute_parameters is called
        THEN: The parameter is not stored in derived_parameters
        """
        file_info = {"derived_parameters": {"INS_TCAL2_ENABLE": {"if": "True"}}}
        variables: dict = {"doc_dict": {}, "fc_parameters": {"OTHER_PARAM": 1.0}}

        result = config_steps.compute_parameters("test_file", file_info, "derived", variables)

        assert result == ""
        assert "INS_TCAL2_ENABLE" not in config_steps.derived_parameters.get("test_file", {})

    def test_forced_parameter_without_new_value_logs_warning_and_is_skipped(
        self, config_steps: ConfigurationSteps, caplog: pytest.LogCaptureFixture
    ) -> None:
        """
        A forced entry without 'New Value' logs a warning explaining the shorthand restriction.

        GIVEN: A forced parameter entry with only an 'if' key (no 'New Value')
        WHEN: compute_parameters is called
        THEN: No error string is returned, the parameter is not stored, and a warning is logged
        """
        file_info = {"forced_parameters": {"PARAM1": {"if": "True"}}}
        variables: dict = {"doc_dict": {}, "fc_parameters": {"PARAM1": 5.0}}

        with caplog.at_level(logging.WARNING):
            result = config_steps.compute_parameters("test_file", file_info, "forced", variables)

        assert result == ""
        assert "PARAM1" not in config_steps.forced_parameters.get("test_file", {})
        assert any("add-from-FC shorthand is only valid for derived parameters" in r.message for r in caplog.records)

    def test_add_from_fc_shorthand_uses_informative_change_reason(self, config_steps: ConfigurationSteps) -> None:
        """
        The add-from-FC shorthand must store a non-empty change reason so the user understands where the value came from.

        GIVEN: A derived parameter with no 'New Value' and the parameter is present in fc_parameters
        WHEN: compute_parameters is called
        THEN: The stored change reason is not an empty string

        REGRESSION: Previously the shorthand set Par(..., "") leaving users with no explanation.
        """
        file_info = {"derived_parameters": {"INS_TCAL2_ENABLE": {}}}
        variables: dict = {"doc_dict": {}, "fc_parameters": {"INS_TCAL2_ENABLE": 2.0}}

        config_steps.compute_parameters("test_file", file_info, "derived", variables)

        assert config_steps.derived_parameters["test_file"]["INS_TCAL2_ENABLE"].comment != ""


# ---------------------------------------------------------------------------
# Configuration navigation helpers
# ---------------------------------------------------------------------------


class TestConfigurationNavigation:
    """Tests for lookup helpers: auto_changed_by, jump_possible, documentation, tooltip, and plugins."""

    def test_auto_changed_by_returns_value_for_known_file(self, config_steps: ConfigurationSteps) -> None:
        """
        auto_changed_by returns the configured string for a file that has one.

        GIVEN: configuration_steps contains auto_changed_by for a known file
        WHEN: auto_changed_by is called with that filename
        THEN: The configured string is returned
        """
        config_steps.configuration_steps = {"test_file": {"auto_changed_by": "auto_change"}}

        assert config_steps.auto_changed_by("test_file") == "auto_change"

    def test_auto_changed_by_returns_empty_string_for_unknown_file(self, config_steps: ConfigurationSteps) -> None:
        """
        auto_changed_by returns an empty string for a file not in configuration_steps.

        GIVEN: An empty configuration_steps
        WHEN: auto_changed_by is called with an unknown filename
        THEN: An empty string is returned
        """
        assert config_steps.auto_changed_by("nonexistent_file") == ""

    def test_jump_possible_returns_mapping_for_known_file(self, config_steps: ConfigurationSteps) -> None:
        """
        jump_possible returns the configured jump mapping for a known file.

        GIVEN: configuration_steps contains a jump_possible mapping
        WHEN: jump_possible is called with that filename
        THEN: The mapping dict is returned
        """
        config_steps.configuration_steps = {"test_file": {"jump_possible": {"step1": "step2"}}}

        assert config_steps.jump_possible("test_file") == {"step1": "step2"}

    def test_jump_possible_returns_empty_dict_for_unknown_file(self, config_steps: ConfigurationSteps) -> None:
        """
        jump_possible returns an empty dict for a file not in configuration_steps.

        GIVEN: An empty configuration_steps
        WHEN: jump_possible is called with an unknown filename
        THEN: An empty dict is returned
        """
        assert config_steps.jump_possible("nonexistent_file") == {}

    def test_documentation_text_and_url_returned_for_known_file(self, config_steps: ConfigurationSteps) -> None:
        """
        Both documentation text and URL are returned for a file that has them.

        GIVEN: configuration_steps has prefix_text and prefix_url for a known file
        WHEN: get_documentation_text_and_url is called
        THEN: The configured text and URL are returned
        """
        config_steps.configuration_steps = {
            "test_file": {"prefix_text": "Documentation text", "prefix_url": "http://example.com"}
        }

        text, url = config_steps.get_documentation_text_and_url("test_file", "prefix")

        assert text == "Documentation text"
        assert url == "http://example.com"

    def test_documentation_text_falls_back_when_no_config_steps(self, config_steps: ConfigurationSteps) -> None:
        """
        A fallback message is returned when configuration_steps is empty.

        GIVEN: An empty configuration_steps dict
        WHEN: get_documentation_text_and_url is called
        THEN: A fallback message mentioning 'No intermediate parameter configuration steps available' is returned
        """
        config_steps.configuration_steps = {}

        text, url = config_steps.get_documentation_text_and_url("test_file", "prefix")

        assert "No intermediate parameter configuration steps available" in text
        assert url == ""

    def test_documentation_url_defaults_to_empty_string_when_absent(self, config_steps: ConfigurationSteps) -> None:
        """
        The URL defaults to an empty string when only text is configured.

        GIVEN: configuration_steps has prefix_text but no prefix_url
        WHEN: get_documentation_text_and_url is called
        THEN: The configured text is returned with an empty URL
        """
        config_steps.configuration_steps = {"test_file": {"prefix_text": "Documentation text"}}

        text, url = config_steps.get_documentation_text_and_url("test_file", "prefix")

        assert text == "Documentation text"
        assert url == ""

    def test_tooltip_text_returned_for_known_key(self, config_steps: ConfigurationSteps) -> None:
        """
        The tooltip text is returned when the key exists for the selected file.

        GIVEN: configuration_steps has a tooltip_key entry for a known file
        WHEN: get_seq_tooltip_text is called with that key
        THEN: The configured tooltip string is returned
        """
        config_steps.configuration_steps = {"test_file": {"tooltip_key": "Tooltip text"}}

        assert config_steps.get_seq_tooltip_text("test_file", "tooltip_key") == "Tooltip text"

    def test_tooltip_fallback_text_for_unknown_key(self, config_steps: ConfigurationSteps) -> None:
        """
        A fallback message is returned when the tooltip key does not exist.

        GIVEN: configuration_steps has an entry for the file but not the requested tooltip key
        WHEN: get_seq_tooltip_text is called with an unknown key
        THEN: A message mentioning 'No documentation available' is returned
        """
        config_steps.configuration_steps = {"test_file": {}}

        assert "No documentation available" in config_steps.get_seq_tooltip_text("test_file", "nonexistent_tooltip")

    def test_tooltip_not_found_message_when_documentation_is_none(self, config_steps: ConfigurationSteps) -> None:
        """
        A 'not found' message is returned when configuration_steps itself is None.

        GIVEN: configuration_steps is set to None
        WHEN: get_seq_tooltip_text is called
        THEN: A message mentioning 'not found' is returned
        """
        config_steps.configuration_steps = None  # type: ignore[assignment]

        assert "not found" in config_steps.get_seq_tooltip_text("test_file", "tooltip_key")

    def test_instructions_popup_returns_dict_for_known_file_and_none_otherwise(self, config_steps: ConfigurationSteps) -> None:
        """
        get_instructions_popup returns the popup dict when present, or None when absent.

        GIVEN: configuration_steps with one file that has an instructions_popup and one that does not
        WHEN: get_instructions_popup is called for each file and a missing file
        THEN: The popup dict, None, and None are returned respectively
        """
        config_steps.configuration_steps = {
            "16_pid_adjustment.param": {"instructions_popup": {"type": "info", "msg": "Test message"}},
            "other.param": {},
        }

        assert config_steps.get_instructions_popup("16_pid_adjustment.param") == {"type": "info", "msg": "Test message"}
        assert config_steps.get_instructions_popup("other.param") is None
        assert config_steps.get_instructions_popup("missing.param") is None

    def test_get_plugin_returns_plugin_dict_when_configured(self, config_steps: ConfigurationSteps) -> None:
        """
        get_plugin returns the plugin configuration dict for a file that has one.

        GIVEN: configuration_steps has a plugin entry for a known file
        WHEN: get_plugin is called with that filename
        THEN: The plugin dict is returned
        """
        config_steps.configuration_steps = {"16_pid.param": {"plugin": {"name": "motor_test", "placement": "after"}}}

        assert config_steps.get_plugin("16_pid.param") == {"name": "motor_test", "placement": "after"}

    def test_get_plugin_returns_none_when_no_plugin_configured(self, config_steps: ConfigurationSteps) -> None:
        """
        get_plugin returns None for a file that has no plugin entry.

        GIVEN: configuration_steps has an entry for a file but no plugin key
        WHEN: get_plugin is called with that filename
        THEN: None is returned
        """
        config_steps.configuration_steps = {"16_pid.param": {}}

        assert config_steps.get_plugin("16_pid.param") is None

    def test_get_plugin_returns_none_for_unknown_file(self, config_steps: ConfigurationSteps) -> None:
        """
        get_plugin returns None for a file not present in configuration_steps.

        GIVEN: An empty configuration_steps
        WHEN: get_plugin is called with an unknown filename
        THEN: None is returned
        """
        assert config_steps.get_plugin("unknown.param") is None

    def test_get_sorted_phases_with_end_and_weight_for_multiple_phases(self, config_steps: ConfigurationSteps) -> None:
        """
        Phases are sorted by start and each receives correct end and weight values.

        GIVEN: Three phases with known start positions
        WHEN: get_sorted_phases_with_end_and_weight is called with total_files=15
        THEN: Each phase has end=next_start (or total_files for last) and weight=max(2, end-start)
        """
        config_steps.configuration_phases = {
            "phase1": {"start": 1, "description": "Phase 1"},  # type: ignore[typeddict-item]
            "phase2": {"start": 5, "description": "Phase 2"},  # type: ignore[typeddict-item]
            "phase3": {"start": 10, "description": "Phase 3"},  # type: ignore[typeddict-item]
        }

        result = config_steps.get_sorted_phases_with_end_and_weight(15)

        assert result["phase1"]["end"] == 5
        assert result["phase1"]["weight"] == 4  # max(2, 5-1)
        assert result["phase2"]["end"] == 10
        assert result["phase2"]["weight"] == 5  # max(2, 10-5)
        assert result["phase3"]["end"] == 15
        assert result["phase3"]["weight"] == 5  # max(2, 15-10)

    def test_get_sorted_phases_with_single_phase_uses_total_files_as_end(self, config_steps: ConfigurationSteps) -> None:
        """
        A single phase receives total_files as its end and the weight is computed accordingly.

        GIVEN: One phase with a known start position
        WHEN: get_sorted_phases_with_end_and_weight is called with total_files=10
        THEN: The phase end equals total_files and weight equals max(2, total_files - start)
        """
        config_steps.configuration_phases = {
            "only_phase": {"start": 1, "description": "Only Phase"},  # type: ignore[typeddict-item]
        }

        result = config_steps.get_sorted_phases_with_end_and_weight(10)

        assert result["only_phase"]["end"] == 10
        assert result["only_phase"]["weight"] == 9  # max(2, 10-1)

    def test_get_sorted_phases_filters_out_phases_without_start_key(self, config_steps: ConfigurationSteps) -> None:
        """
        Phases without a 'start' key are excluded from the sorted result.

        GIVEN: One phase with 'start' and one without
        WHEN: get_sorted_phases_with_end_and_weight is called
        THEN: Only the phase with 'start' appears in the result
        """
        config_steps.configuration_phases = {
            "no_start_phase": {"description": "No start"},  # type: ignore[typeddict-item]
            "has_start_phase": {"start": 5, "description": "Has start"},  # type: ignore[typeddict-item]
        }

        result = config_steps.get_sorted_phases_with_end_and_weight(10)

        assert "no_start_phase" not in result
        assert "has_start_phase" in result

    def test_get_sorted_phases_clamps_weight_to_minimum_of_two(self, config_steps: ConfigurationSteps) -> None:
        """
        The weight is clamped to a minimum of 2 even when phases are only 1 file apart.

        GIVEN: Two phases whose starts are only 1 apart
        WHEN: get_sorted_phases_with_end_and_weight is called
        THEN: Both phases have weight=2 (the minimum)
        """
        config_steps.configuration_phases = {
            "phase1": {"start": 1, "description": "Phase 1"},  # type: ignore[typeddict-item]
            "phase2": {"start": 2, "description": "Phase 2"},  # type: ignore[typeddict-item]
        }

        result = config_steps.get_sorted_phases_with_end_and_weight(3)

        assert result["phase1"]["weight"] == 2  # max(2, 2-1) = 2
        assert result["phase2"]["weight"] == 2  # max(2, 3-2) = 2
