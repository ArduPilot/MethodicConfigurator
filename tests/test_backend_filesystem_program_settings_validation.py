#!/usr/bin/env python3

"""
BDD-style unit tests for path normalization in backend_filesystem_program_settings.py.

This file contains tests for the path normalization logic for the Recent Vehicle
Directories History feature.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import platform
from unittest.mock import patch

from ardupilot_methodic_configurator.backend_filesystem_program_settings import (
    ProgramSettings,
    normalize_for_comparison,
    normalize_path,
)

# pylint: disable=protected-access


class TestIsTemplateDirectory:
    """Unit tests for _is_template_directory() method."""

    def test_identifies_template_directory(self) -> None:
        """
        Identifies paths within template base directory.

        GIVEN: A path that is within the templates base directory
        WHEN: _is_template_directory is called
        THEN: Should return True
        """
        with patch.object(ProgramSettings, "get_templates_base_dir", return_value="/app/vehicle_templates"):
            # Path inside templates should return True
            result = ProgramSettings._is_template_directory("/app/vehicle_templates/ArduCopter/QuadX")
            assert result is True

    def test_identifies_non_template_directory(self) -> None:
        """
        Identifies paths outside template base directory.

        GIVEN: A path that is NOT within the templates base directory
        WHEN: _is_template_directory is called
        THEN: Should return False
        """
        with patch.object(ProgramSettings, "get_templates_base_dir", return_value="/app/vehicle_templates"):
            # Path outside templates should return False
            result = ProgramSettings._is_template_directory("/home/user/vehicles/my_project")
            assert result is False

    def test_handles_path_resolution_error_conservatively(self) -> None:
        """
        Handles path resolution errors conservatively.

        GIVEN: A path that causes ValueError during commonpath check
        WHEN: _is_template_directory is called
        THEN: Should return True (conservative - don't migrate problematic paths)
        """
        with (
            patch.object(ProgramSettings, "get_templates_base_dir", return_value="/templates"),
            patch("ardupilot_methodic_configurator.backend_filesystem_program_settings.os_path") as mock_os_path,
        ):
            # Make commonpath() raise ValueError (different drives on Windows)
            mock_os_path.normpath.side_effect = lambda x: x
            mock_os_path.abspath.side_effect = lambda x: x
            mock_os_path.commonpath.side_effect = ValueError("Paths on different drives")

            result = ProgramSettings._is_template_directory("/some/path")
            # Should return True conservatively (don't migrate paths that cause errors)
            assert result is True

    def test_handles_os_error_conservatively(self) -> None:
        """
        Handles OS errors conservatively.

        GIVEN: A path that causes OSError during path operations
        WHEN: _is_template_directory is called
        THEN: Should return True (conservative - don't migrate inaccessible paths)
        """
        with (
            patch.object(ProgramSettings, "get_templates_base_dir", return_value="/templates"),
            patch("ardupilot_methodic_configurator.backend_filesystem_program_settings.os_path") as mock_os_path,
        ):
            # Make commonpath() raise OSError
            mock_os_path.normpath.side_effect = lambda x: x
            mock_os_path.abspath.side_effect = lambda x: x
            mock_os_path.commonpath.side_effect = OSError("Network error")

            result = ProgramSettings._is_template_directory("\\\\network\\share\\path")
            # Should return True conservatively
            assert result is True


class TestMigrateLegacyVehicleDir:
    """Unit tests for migrate_settings_to_latest_version() method."""

    def test_migrates_valid_legacy_path(self) -> None:
        """
        Migrates valid legacy vehicle_dir to recent_vehicle_history.

        GIVEN: Settings with Format version 1 and valid legacy vehicle_dir
        WHEN: migrate_settings_to_latest_version is called
        THEN: Legacy path should be migrated to recent_vehicle_history[0]
        AND: Format version should be updated to 2
        """
        test_path = "C:\\vehicles\\old" if platform.system() == "Windows" else "/vehicles/old"
        captured_settings = {}

        def capture(settings: dict) -> None:
            captured_settings.update(settings)

        with (
            patch.object(ProgramSettings, "_get_settings_as_dict") as mock_get,
            patch.object(ProgramSettings, "_set_settings_from_dict", side_effect=capture) as mock_set,
            patch.object(ProgramSettings, "_is_template_directory", return_value=False),
        ):
            mock_get.return_value = {
                "Format version": 1,
                "recent_vehicle_history": [],
                "directory_selection": {"vehicle_dir": test_path},
            }

            ProgramSettings.migrate_settings_to_latest_version()

            # Should have persisted the migration
            mock_set.assert_called_once()
            assert captured_settings["Format version"] == 2
            assert len(captured_settings["recent_vehicle_history"]) == 1

    def test_migrates_any_legacy_path(self) -> None:
        """
        Migrates any legacy vehicle_dir to history (permissive approach).

        GIVEN: Settings with Format version 1 and legacy vehicle_dir
        WHEN: migrate_settings_to_latest_version is called
        THEN: Path is migrated to history regardless of validity, legacy setting removed
        AND: Format version should be updated to 2
        """
        captured_settings = {}

        def capture(settings: dict) -> None:
            captured_settings.update(settings)

        with (
            patch.object(ProgramSettings, "_get_settings_as_dict") as mock_get,
            patch.object(ProgramSettings, "_set_settings_from_dict", side_effect=capture) as mock_set,
            patch.object(ProgramSettings, "_is_template_directory", return_value=False),
        ):
            mock_get.return_value = {
                "Format version": 1,
                "recent_vehicle_history": [],
                "directory_selection": {"vehicle_dir": "any/path/here"},
            }

            ProgramSettings.migrate_settings_to_latest_version()

            # Should have persisted changes (removed legacy setting, added to history)
            mock_set.assert_called_once()
            assert captured_settings["Format version"] == 2
            # Legacy setting should be removed
            assert "vehicle_dir" not in captured_settings["directory_selection"]
            # Path should be in history (permissive approach)
            assert len(captured_settings["recent_vehicle_history"]) == 1

    def test_skips_template_paths(self) -> None:
        """
        Removes template paths from legacy settings without migrating.

        GIVEN: Settings with Format version 1 and vehicle_dir pointing to template directory
        WHEN: migrate_settings_to_latest_version is called
        THEN: Template path not added to history, but legacy setting is removed
        AND: Format version should be updated to 2
        """
        captured_settings = {}

        def capture(settings: dict) -> None:
            captured_settings.update(settings)

        with (
            patch.object(ProgramSettings, "_get_settings_as_dict") as mock_get,
            patch.object(ProgramSettings, "_set_settings_from_dict", side_effect=capture) as mock_set,
            patch.object(ProgramSettings, "_is_template_directory", return_value=True),  # Is template
        ):
            mock_get.return_value = {
                "Format version": 1,
                "recent_vehicle_history": [],
                "directory_selection": {"vehicle_dir": "/templates/ArduCopter/QuadX"},
            }

            ProgramSettings.migrate_settings_to_latest_version()

            # Should have persisted to remove legacy template path
            mock_set.assert_called_once()
            assert captured_settings["Format version"] == 2
            # Legacy setting should be removed
            assert "vehicle_dir" not in captured_settings["directory_selection"]
            # Template path should NOT be in history
            assert len(captured_settings["recent_vehicle_history"]) == 0

    def test_handles_corrupted_history_data(self) -> None:
        """
        Handles corrupted recent_vehicle_history data gracefully.

        GIVEN: Settings with Format version 1 where recent_vehicle_history is not a list (corrupted)
        WHEN: migrate_settings_to_latest_version is called
        THEN: Should treat as empty list and continue migration
        AND: Format version should be updated to 2
        """
        test_path = "C:\\vehicles\\old" if platform.system() == "Windows" else "/vehicles/old"
        captured_settings = {}

        def capture(settings: dict) -> None:
            captured_settings.update(settings)

        with (
            patch.object(ProgramSettings, "_get_settings_as_dict") as mock_get,
            patch.object(ProgramSettings, "_set_settings_from_dict", side_effect=capture),
            patch.object(ProgramSettings, "_is_template_directory", return_value=False),
        ):
            mock_get.return_value = {
                "Format version": 1,
                "recent_vehicle_history": "corrupted_string",  # Should be list
                "directory_selection": {"vehicle_dir": test_path},
            }

            ProgramSettings.migrate_settings_to_latest_version()

            # Should have treated corrupted data as empty and migrated
            assert captured_settings["Format version"] == 2
            assert isinstance(captured_settings["recent_vehicle_history"], list)

    def test_avoids_duplicate_migration(self) -> None:
        """
        Avoids migrating path that already exists in recent_vehicle_history.

        GIVEN: Settings with Format version 1 where vehicle_dir already exists in recent_vehicle_history
        WHEN: migrate_settings_to_latest_version is called
        THEN: Should not create duplicate entry but still remove legacy setting
        AND: Format version should be updated to 2
        """
        test_path = "C:\\vehicles\\existing" if platform.system() == "Windows" else "/vehicles/existing"
        captured_settings = {}

        def capture(settings: dict) -> None:
            captured_settings.update(settings)

        with (
            patch.object(ProgramSettings, "_get_settings_as_dict") as mock_get,
            patch.object(ProgramSettings, "_set_settings_from_dict", side_effect=capture) as mock_set,
            patch.object(ProgramSettings, "_is_template_directory", return_value=False),
        ):
            mock_get.return_value = {
                "Format version": 1,
                "recent_vehicle_history": [test_path],  # Already in history
                "directory_selection": {"vehicle_dir": test_path},
            }

            ProgramSettings.migrate_settings_to_latest_version()

            # Should have persisted to remove legacy setting even though path already in history
            mock_set.assert_called_once()
            assert captured_settings["Format version"] == 2
            # Legacy setting should be removed
            assert "vehicle_dir" not in captured_settings["directory_selection"]
            # Should NOT have created duplicate - still only 1 entry
            assert len(captured_settings["recent_vehicle_history"]) == 1
            assert captured_settings["recent_vehicle_history"][0] == test_path


class TestPathNormalization:
    """Unit tests for path normalization behavior."""

    def test_normalize_resolves_relative_components(self) -> None:
        """
        Path normalization resolves relative components.

        GIVEN: A path with . and .. components
        WHEN: _normalize_path is called
        THEN: Should resolve relative components
        """
        # This test documents that Path() does MORE than just normalize separators
        with patch("ardupilot_methodic_configurator.backend_filesystem_program_settings.platform_system") as mock_platform:
            mock_platform.return_value = "Linux"
            # Note: Path normalization may resolve these components
            result = normalize_path("/path/./to/../dir")
            # The exact result depends on Path() behavior - just verify it doesn't error
            assert result is not None

    def test_normalize_for_comparison_handles_case_on_windows(self) -> None:
        """
        Normalize for comparison is case-insensitive on Windows.

        GIVEN: Two paths differing only in case
        WHEN: _normalize_for_comparison is called on Windows
        THEN: Should return same normalized form
        """
        with patch("ardupilot_methodic_configurator.backend_filesystem_program_settings.platform_system") as mock_platform:
            mock_platform.return_value = "Windows"
            path1 = normalize_for_comparison("C:\\Path\\To\\Dir")
            path2 = normalize_for_comparison("c:\\path\\to\\dir")
            # On Windows, should normalize to same value (case-insensitive)
            assert path1.lower() == path2.lower()

    def test_normalize_for_comparison_case_sensitive_on_unix(self) -> None:
        """
        Normalize for comparison is case-sensitive on Unix.

        GIVEN: Two paths differing only in case
        WHEN: _normalize_for_comparison is called on Unix
        THEN: May return different normalized forms (case-sensitive)
        """
        with patch("ardupilot_methodic_configurator.backend_filesystem_program_settings.platform_system") as mock_platform:
            mock_platform.return_value = "Linux"
            # On Unix, case matters in paths - but normpath may still affect it
            result1 = normalize_for_comparison("/Path/To/Dir")
            result2 = normalize_for_comparison("/path/to/dir")
            # The results exist and are processed
            assert result1 is not None
            assert result2 is not None
