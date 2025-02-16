#!/usr/bin/env python3

"""
Tests for the backend_filesystem_configuration_steps.py file.

This file is part of Ardupilot methodic configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2025 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import unittest
from unittest.mock import mock_open, patch

from ardupilot_methodic_configurator.backend_filesystem_configuration_steps import ConfigurationSteps


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
                unittest.mock.call("vehicle_dir/configuration_steps_vehicle_type.json", encoding="utf-8"),
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


if __name__ == "__main__":
    unittest.main()
