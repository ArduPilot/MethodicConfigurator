#!/usr/bin/env python3

"""
Tests for the backend_filesystem_program_settings.py file.

This file is part of ArduPilot methodic configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2025 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import json
from unittest.mock import mock_open, patch

import pytest

from ardupilot_methodic_configurator.backend_filesystem_program_settings import ProgramSettings

# pylint: disable=protected-access


class TestProgramSettings:
    """Tests for the ProgramSettings class."""

    def test_application_icon_filepath(self) -> None:
        with (
            patch("os.path.dirname") as mock_dirname,
            patch("os.path.abspath") as mock_abspath,
            patch("os.path.join") as mock_join,
        ):
            mock_dirname.return_value = "/mock/dir"
            mock_abspath.return_value = "/mock/dir/file"
            mock_join.return_value = "/mock/dir/ArduPilot_icon.png"

            result = ProgramSettings.application_icon_filepath()

            mock_dirname.assert_called_once()
            mock_abspath.assert_called_once()
            mock_join.assert_called_once_with("/mock/dir", "ArduPilot_icon.png")
            assert result == "/mock/dir/ArduPilot_icon.png"

    def test_application_logo_filepath(self) -> None:
        with (
            patch("os.path.dirname") as mock_dirname,
            patch("os.path.abspath") as mock_abspath,
            patch("os.path.join") as mock_join,
        ):
            mock_dirname.return_value = "/mock/dir"
            mock_abspath.return_value = "/mock/dir/file"
            mock_join.return_value = "/mock/dir/ArduPilot_logo.png"

            result = ProgramSettings.application_logo_filepath()

            mock_dirname.assert_called_once()
            mock_abspath.assert_called_once()
            mock_join.assert_called_once_with("/mock/dir", "ArduPilot_logo.png")
            assert result == "/mock/dir/ArduPilot_logo.png"

    def test_create_new_vehicle_dir_already_exists(self) -> None:
        with patch("os.path.exists", return_value=True):
            result = ProgramSettings.create_new_vehicle_dir("/mock/dir")
            assert result != ""  # Error message returned

    def test_create_new_vehicle_dir_failure(self) -> None:
        with (
            patch("os.path.exists", return_value=False),
            patch("os.makedirs", side_effect=OSError("Test error")),
            patch("ardupilot_methodic_configurator.backend_filesystem_program_settings.logging_error") as mock_log_error,
        ):
            result = ProgramSettings.create_new_vehicle_dir("/mock/dir")

            mock_log_error.assert_called_once()
            assert "Test error" in result

    def test_valid_directory_name(self) -> None:
        assert ProgramSettings.valid_directory_name("valid_dir_name-123") is True
        assert ProgramSettings.valid_directory_name("invalid/dir/name") is True  # Because '/' is allowed
        assert ProgramSettings.valid_directory_name("invalid<dir>name") is False
        assert ProgramSettings.valid_directory_name("invalid*dir?name") is False

    def test_user_config_dir(self) -> None:
        with (
            patch(
                "ardupilot_methodic_configurator.backend_filesystem_program_settings.user_config_dir",
                return_value="/mock/user/config",
            ),
            patch("os.path.exists", return_value=True),
            patch("os.path.isdir", return_value=True),
        ):
            result = ProgramSettings._ProgramSettings__user_config_dir()

            assert result == "/mock/user/config"

    def test_user_config_dir_not_exists(self) -> None:
        with (
            patch("platformdirs.user_config_dir", return_value="/mock/user/config"),
            patch("os.path.exists", return_value=False),
            pytest.raises(FileNotFoundError),
        ):
            ProgramSettings._ProgramSettings__user_config_dir()

    def test_user_config_dir_not_directory(self) -> None:
        with (
            patch("platformdirs.user_config_dir", return_value="/mock/user/config"),
            patch("os.path.exists", return_value=True),
            patch("os.path.isdir", return_value=False),
            pytest.raises(NotADirectoryError),
        ):
            ProgramSettings._ProgramSettings__user_config_dir()

    def test_get_settings_as_dict_file_exists(self) -> None:
        mock_settings = {
            "Format version": 1,
            "directory_selection": {"template_dir": "/mock/template"},
            "display_usage_popup": {"component_editor": False, "parameter_editor": True},
            "auto_open_doc_in_browser": False,
        }

        expected_result = mock_settings.copy()
        # The method adds this default setting if not present in the file
        expected_result["annotate_docs_into_param_files"] = False

        with (
            patch.object(ProgramSettings, "_ProgramSettings__user_config_dir", return_value="/mock/config"),
            patch("os.path.join", return_value="/mock/config/settings.json"),
            patch("builtins.open", mock_open(read_data=json.dumps(mock_settings))),
        ):
            result = ProgramSettings._ProgramSettings__get_settings_as_dict()

            assert result == expected_result

    def test_get_settings_as_dict_file_not_exists(self) -> None:
        with (
            patch.object(ProgramSettings, "_ProgramSettings__user_config_dir", return_value="/mock/config"),
            patch("os.path.join", return_value="/mock/config/settings.json"),
            patch("builtins.open", side_effect=FileNotFoundError),
        ):
            result = ProgramSettings._ProgramSettings__get_settings_as_dict()

            assert "Format version" in result
            assert "directory_selection" in result
            assert "display_usage_popup" in result
            assert "component_editor" in result["display_usage_popup"]
            assert "parameter_editor" in result["display_usage_popup"]
            assert "auto_open_doc_in_browser" in result
            assert "annotate_docs_into_param_files" in result

    def test_set_settings_from_dict(self) -> None:
        mock_settings = {"test": "value"}

        with (
            patch.object(ProgramSettings, "_ProgramSettings__user_config_dir", return_value="/mock/config"),
            patch("os.path.join", return_value="/mock/config/settings.json"),
            patch("builtins.open", mock_open()) as mock_file,
        ):
            ProgramSettings._ProgramSettings__set_settings_from_dict(mock_settings)

            mock_file.assert_called_once_with("/mock/config/settings.json", "w", encoding="utf-8")
            mock_file().write.assert_called()

    def test_display_usage_popup(self) -> None:
        with patch.object(ProgramSettings, "_ProgramSettings__get_settings_as_dict") as mock_get_settings:
            mock_get_settings.return_value = {"display_usage_popup": {"component_editor": False, "parameter_editor": True}}

            assert ProgramSettings.display_usage_popup("component_editor") is False
            assert ProgramSettings.display_usage_popup("parameter_editor") is True
            assert ProgramSettings.display_usage_popup("nonexistent_type") is True  # Default is True

    def test_set_display_usage_popup(self) -> None:
        with (
            patch.object(ProgramSettings, "_ProgramSettings__get_settings_config") as mock_get_config,
            patch.object(ProgramSettings, "_ProgramSettings__set_settings_from_dict") as mock_set_settings,
        ):
            mock_get_config.return_value = (
                {"display_usage_popup": {"component_editor": True, "parameter_editor": True}},
                "pattern",
                "replacement",
            )

            # Test valid type
            ProgramSettings.set_display_usage_popup("component_editor", value=False)
            mock_set_settings.assert_called_with(
                {"display_usage_popup": {"component_editor": False, "parameter_editor": True}}
            )

            # Test invalid type
            mock_set_settings.reset_mock()
            ProgramSettings.set_display_usage_popup("nonexistent_type", value=False)
            mock_set_settings.assert_not_called()

    def test_get_setting(self) -> None:
        with patch.object(ProgramSettings, "_ProgramSettings__get_settings_as_dict") as mock_get_settings:
            mock_get_settings.return_value = {"Format version": 2, "auto_open_doc_in_browser": False}

            # Test existing settings
            assert ProgramSettings.get_setting("Format version") == 2
            assert ProgramSettings.get_setting("auto_open_doc_in_browser") is False

            # Test default values
            assert ProgramSettings.get_setting("annotate_docs_into_param_files") is False

            # Test non-existent setting
            assert ProgramSettings.get_setting("nonexistent_setting") is False

    def test_set_setting(self) -> None:
        with (
            patch.object(ProgramSettings, "_ProgramSettings__get_settings_config") as mock_get_config,
            patch.object(ProgramSettings, "_ProgramSettings__set_settings_from_dict") as mock_set_settings,
        ):
            mock_get_config.return_value = ({"Format version": 1, "auto_open_doc_in_browser": True}, "pattern", "replacement")

            # Test valid setting
            ProgramSettings.set_setting("auto_open_doc_in_browser", value=False)
            mock_set_settings.assert_called_with({"Format version": 1, "auto_open_doc_in_browser": False})

            # Test invalid setting
            mock_set_settings.reset_mock()
            ProgramSettings.set_setting("nonexistent_setting", value=True)
            mock_set_settings.assert_not_called()
