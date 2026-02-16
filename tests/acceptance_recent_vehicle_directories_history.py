#!/usr/bin/env python3

"""
Acceptance tests for Recent Vehicle Directories History feature.

This file contains BDD-style acceptance tests that validate the requirements
for maintaining a history of the 5 most recently opened vehicle directories.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

from os import path as os_path
from platform import system as platform_system
from unittest.mock import patch

import pytest

from ardupilot_methodic_configurator.backend_filesystem_program_settings import ProgramSettings, normalize_for_comparison

# pylint: disable=protected-access, too-few-public-methods


def path_in_list(path: str, path_list: list[str]) -> bool:
    """Check if path exists in list using normalized comparison."""
    normalized_path = normalize_for_comparison(path)
    return any(normalize_for_comparison(p) == normalized_path for p in path_list)


def count_path_in_list(path: str, path_list: list[str]) -> int:
    """Count occurrences of path in list using normalized comparison."""
    normalized_path = normalize_for_comparison(path)
    return sum(1 for p in path_list if normalize_for_comparison(p) == normalized_path)


class TestRecentVehicleDirectoriesHistoryView:
    """AC1: User Can View Recent Vehicle Directories in Combobox."""

    def test_user_can_view_recent_directories_in_reverse_chronological_order(self) -> None:
        """
        User can view recent directories in combobox sorted by most recent first.

        GIVEN: User has previously opened 3 vehicle directories (Dir_A at 10:00, Dir_B at 10:05, Dir_C at 10:10)
        WHEN: User opens the VehicleProjectOpenerWindow
        THEN: The combobox should display all 3 directories in reverse chronological order [Dir_C, Dir_B, Dir_A]
        AND: The combobox shows full absolute paths for each directory
        AND: The combobox is read-only (no text editing allowed)
        """
        # Arrange: Mock settings with 3 directories in chronological order (most recent first)
        with patch.object(ProgramSettings, "_get_settings_as_dict") as mock_get_settings:
            mock_get_settings.return_value = {
                "recent_vehicle_history": [
                    "/path/to/Dir_C",  # Most recent (opened at 10:10)
                    "/path/to/Dir_B",  # Middle (opened at 10:05)
                    "/path/to/Dir_A",  # Oldest (opened at 10:00)
                ]
            }

            # Act: Retrieve recent directories
            recent_dirs = ProgramSettings.get_recent_vehicle_dirs()

            # Assert: Directories returned in reverse chronological order with full paths
            assert recent_dirs == ["/path/to/Dir_C", "/path/to/Dir_B", "/path/to/Dir_A"]
            assert len(recent_dirs) == 3
            # Verify all paths are absolute (start with / or drive letter)
            for path in recent_dirs:
                assert path.startswith("/") or (len(path) > 2 and path[1] == ":")


class TestRecentVehicleDirectoriesHistorySelection:
    """AC2: User Can Select and Open a Recent Directory."""

    def test_user_can_select_and_open_recent_directory(self) -> None:
        """
        User can select a directory from history and it becomes the most recent.

        GIVEN: User has recent directories [Dir_A, Dir_B, Dir_C] in the history
        WHEN: User selects Dir_B from the combobox dropdown
        AND: User successfully opens Dir_B
        THEN: Dir_B should be promoted to the most recent entry [Dir_B, Dir_A, Dir_C]
        """
        # Arrange: Use platform-appropriate paths
        if platform_system() == "Windows":
            test_paths = ["C:\\path\\to\\Dir_A", "C:\\path\\to\\Dir_B", "C:\\path\\to\\Dir_C"]
        else:
            test_paths = ["/path/to/Dir_A", "/path/to/Dir_B", "/path/to/Dir_C"]

        # Arrange: Mock settings with initial history
        with (
            patch.object(ProgramSettings, "_get_settings_as_dict") as mock_get_settings,
            patch.object(ProgramSettings, "_set_settings_from_dict") as mock_set_settings,
        ):
            # Initial state: [Dir_A, Dir_B, Dir_C]
            mock_get_settings.return_value = {"recent_vehicle_history": test_paths.copy()}

            # Act: User opens Dir_B (should be promoted to top)
            ProgramSettings.store_recently_used_vehicle_dir(test_paths[1])

            # Assert: Dir_B promoted to position [0], no duplicates
            mock_set_settings.assert_called_once()
            saved_settings = mock_set_settings.call_args[0][0]
            assert normalize_for_comparison(saved_settings["recent_vehicle_history"][0]) == normalize_for_comparison(
                test_paths[1]
            )
            assert path_in_list(test_paths[1], saved_settings["recent_vehicle_history"])
            # Verify no duplicates
            assert count_path_in_list(test_paths[1], saved_settings["recent_vehicle_history"]) == 1


class TestRecentVehicleDirectoriesHistoryLimit:
    """AC3: History Maintains Maximum of 5 Entries."""

    def test_history_maintains_maximum_of_five_entries(self) -> None:
        """
        History is limited to 5 entries, oldest is removed when adding 6th.

        GIVEN: User already has 5 directories in history [Dir_A, Dir_B, Dir_C, Dir_D, Dir_E]
        WHEN: User successfully opens a new directory Dir_F
        THEN: The history should contain [Dir_F, Dir_A, Dir_B, Dir_C, Dir_D]
        AND: The oldest entry (Dir_E) should be removed
        """
        # Arrange: Use platform-appropriate paths
        if platform_system() == "Windows":
            test_paths = [
                "C:\\path\\to\\Dir_A",  # Most recent
                "C:\\path\\to\\Dir_B",
                "C:\\path\\to\\Dir_C",
                "C:\\path\\to\\Dir_D",
                "C:\\path\\to\\Dir_E",  # Oldest - should be removed
            ]
            new_path = "C:\\path\\to\\Dir_F"
        else:
            test_paths = [
                "/path/to/Dir_A",  # Most recent
                "/path/to/Dir_B",
                "/path/to/Dir_C",
                "/path/to/Dir_D",
                "/path/to/Dir_E",  # Oldest - should be removed
            ]
            new_path = "/path/to/Dir_F"

        # Arrange: Mock settings with 5 directories (at max capacity)
        with (
            patch.object(ProgramSettings, "_get_settings_as_dict") as mock_get_settings,
            patch.object(ProgramSettings, "_set_settings_from_dict") as mock_set_settings,
        ):
            mock_get_settings.return_value = {"recent_vehicle_history": test_paths.copy()}

            # Act: User opens a new directory Dir_F
            ProgramSettings.store_recently_used_vehicle_dir(new_path)

            # Assert: History limited to MAX_RECENT_DIRS, oldest removed
            mock_set_settings.assert_called_once()
            saved_settings = mock_set_settings.call_args[0][0]
            assert len(saved_settings["recent_vehicle_history"]) <= ProgramSettings.MAX_RECENT_DIRS
            assert normalize_for_comparison(saved_settings["recent_vehicle_history"][0]) == normalize_for_comparison(new_path)
            assert not path_in_list(test_paths[-1], saved_settings["recent_vehicle_history"])


class TestRecentVehicleDirectoriesHistoryPromotion:
    """AC4: Opening Same Directory Promotes It to Top."""

    def test_opening_same_directory_promotes_to_top_without_duplicates(self) -> None:
        """
        Re-opening a directory moves it to top without creating duplicates.

        GIVEN: User has history [Dir_A, Dir_B, Dir_C]
        WHEN: User opens Dir_C again
        THEN: The history should be reordered to [Dir_C, Dir_A, Dir_B]
        AND: No duplicate entries should exist
        """
        # Arrange: Mock settings with 3 directories
        with (
            patch.object(ProgramSettings, "_get_settings_as_dict") as mock_get_settings,
            patch.object(ProgramSettings, "_set_settings_from_dict") as mock_set_settings,
        ):
            # Use platform-appropriate paths for testing
            if platform_system() == "Windows":
                test_paths = ["C:\\path\\to\\Dir_A", "C:\\path\\to\\Dir_B", "C:\\path\\to\\Dir_C"]
            else:
                test_paths = ["/path/to/Dir_A", "/path/to/Dir_B", "/path/to/Dir_C"]

            mock_get_settings.return_value = {"recent_vehicle_history": test_paths.copy()}

            # Act: User opens Dir_C (already in history at position 2)
            ProgramSettings.store_recently_used_vehicle_dir(test_paths[2])

            # Assert: Dir_C moved to top, no duplicates
            mock_set_settings.assert_called_once()
            saved_settings = mock_set_settings.call_args[0][0]
            assert normalize_for_comparison(saved_settings["recent_vehicle_history"][0]) == normalize_for_comparison(
                test_paths[2]
            )
            assert count_path_in_list(test_paths[2], saved_settings["recent_vehicle_history"]) == 1
            # Other directories should remain in relative order
            assert path_in_list(test_paths[0], saved_settings["recent_vehicle_history"])
            assert path_in_list(test_paths[1], saved_settings["recent_vehicle_history"])


class TestRecentVehicleDirectoriesHistoryPersistence:
    """AC5: History Persists Across Application Sessions."""

    def test_history_persists_across_application_sessions(self) -> None:
        """
        History is saved to settings.json and loaded on next session.

        GIVEN: User has history [Dir_A, Dir_B, Dir_C] in current session
        WHEN: Settings are saved to disk
        AND: Application is restarted and settings are reloaded
        THEN: The history should still contain [Dir_A, Dir_B, Dir_C] in the same order
        """
        # Arrange: Use platform-appropriate paths
        if platform_system() == "Windows":
            initial_history = ["C:\\path\\to\\Dir_A", "C:\\path\\to\\Dir_B", "C:\\path\\to\\Dir_C"]
        else:
            initial_history = ["/path/to/Dir_A", "/path/to/Dir_B", "/path/to/Dir_C"]

        # Arrange: Save history in one "session"
        with (
            patch.object(ProgramSettings, "_get_settings_as_dict") as mock_get_settings,
            patch.object(ProgramSettings, "_set_settings_from_dict") as mock_set_settings,
        ):
            mock_get_settings.return_value = {"recent_vehicle_history": initial_history.copy()}

            # Act: Store a directory (simulating normal usage)
            ProgramSettings.store_recently_used_vehicle_dir(initial_history[0])

            # Capture what was saved
            mock_set_settings.assert_called_once()
            saved_data = mock_set_settings.call_args[0][0]

        # Simulate new session: Reload from saved data
        with patch.object(ProgramSettings, "_get_settings_as_dict") as mock_get_settings_new:
            mock_get_settings_new.return_value = saved_data

            # Assert: History is preserved
            loaded_history = ProgramSettings.get_recent_vehicle_dirs()
            assert path_in_list(initial_history[0], loaded_history)
            assert path_in_list(initial_history[1], loaded_history)
            assert path_in_list(initial_history[2], loaded_history)


class TestRecentVehicleDirectoriesHistoryMissingDirectories:
    """AC6: Non-Existent Directory Remains in History with Error."""

    def test_nonexistent_directory_remains_in_history(self) -> None:
        """
        Non-existent directories stay in history for error handling at open time.

        GIVEN: User has history with Dir_X that no longer exists on the filesystem
        WHEN: User views the history
        THEN: Dir_X should still appear in the list
        """
        # Arrange: Mock settings with a directory that doesn't exist
        with patch.object(ProgramSettings, "_get_settings_as_dict") as mock_get_settings:
            mock_get_settings.return_value = {
                "recent_vehicle_history": [
                    "/path/to/existing_dir",
                    "/path/to/nonexistent_dir",  # This directory doesn't exist
                    "/path/to/another_existing_dir",
                ]
            }

            # Act: Retrieve recent directories
            recent_dirs = ProgramSettings.get_recent_vehicle_dirs()

            # Assert: Non-existent directory still in list (error handling happens at open time)
            assert "/path/to/nonexistent_dir" in recent_dirs
            assert len(recent_dirs) == 3


class TestRecentVehicleDirectoriesHistoryEmptyState:
    """AC7: Empty History Shows Default Behavior."""

    def test_empty_history_returns_empty_list(self) -> None:
        """
        Empty history returns an empty list without errors.

        GIVEN: User is running the application for the first time (no history)
        WHEN: Application loads recent directories
        THEN: An empty list should be returned
        """
        # Arrange: Mock settings with no recent_vehicle_history key (first run)
        with patch.object(ProgramSettings, "_get_settings_as_dict") as mock_get_settings:
            mock_get_settings.return_value = {}

            # Act: Get recent directories
            recent_dirs = ProgramSettings.get_recent_vehicle_dirs()

            # Assert: Empty list returned gracefully
            assert recent_dirs == []
            assert isinstance(recent_dirs, list)

    def test_empty_history_gracefully_handles_missing_key(self) -> None:
        """
        Missing recent_vehicle_history key is handled gracefully.

        GIVEN: Settings exist but don't have recent_vehicle_history key
        WHEN: Application requests recent directories
        THEN: Empty list should be returned without raising exceptions
        """
        # Arrange: Settings with other keys but no recent_vehicle_history
        with patch.object(ProgramSettings, "_get_settings_as_dict") as mock_get_settings:
            mock_get_settings.return_value = {
                "Format version": 1,
                "directory_selection": {"template_dir": "/some/path"},
            }

            # Act: Get recent directories
            recent_dirs = ProgramSettings.get_recent_vehicle_dirs()

            # Assert: Empty list returned without errors
            assert recent_dirs == []


class TestRecentVehicleDirectoriesHistoryPathNormalization:
    """AC8: Path Normalization for OS Compatibility."""

    def test_path_normalization_on_windows(self) -> None:
        r"""
        Paths are normalized with backslashes on Windows.

        GIVEN: User is running on Windows and has opened Dir_A
        WHEN: The history is saved to settings.json
        THEN: Paths should use backslashes (C:\\Users\\...\\Dir_A)
        """
        # Arrange: Mock Windows platform and settings
        with (
            patch("ardupilot_methodic_configurator.backend_filesystem_program_settings.IS_WINDOWS", new=True),
            patch.object(ProgramSettings, "_get_settings_as_dict") as mock_get_settings,
            patch.object(ProgramSettings, "_set_settings_from_dict") as mock_set_settings,
        ):
            mock_get_settings.return_value = {"recent_vehicle_history": []}

            # Act: Store a path with forward slashes
            ProgramSettings.store_recently_used_vehicle_dir("C:/Users/test/Dir_A")

            # Assert: Path normalized to backslashes for Windows
            mock_set_settings.assert_called_once()
            saved_settings = mock_set_settings.call_args[0][0]
            saved_path = saved_settings["recent_vehicle_history"][0]
            # On Windows, should have backslashes
            assert "\\" in saved_path or "/" not in saved_path

    def test_path_normalization_on_unix(self) -> None:
        """
        Paths are normalized with platform-appropriate separators.

        GIVEN: User provides a path for storage
        WHEN: The history is saved to settings.json
        THEN: Paths should be normalized and absolute
        """
        # Note: os.path.normpath() uses the current OS separators, so this test
        # verifies normalization happens, but doesn't enforce specific separators
        with (
            patch.object(ProgramSettings, "_get_settings_as_dict") as mock_get_settings,
            patch.object(ProgramSettings, "_set_settings_from_dict") as mock_set_settings,
        ):
            mock_get_settings.return_value = {"recent_vehicle_history": []}

            # Act: Store a path - it will be normalized to platform format
            test_path = "/home/test/Dir_B" if platform_system() != "Windows" else "C:\\test\\Dir_B"
            ProgramSettings.store_recently_used_vehicle_dir(test_path)

            # Assert: Path is normalized and stored
            mock_set_settings.assert_called_once()
            saved_settings = mock_set_settings.call_args[0][0]
            saved_path = saved_settings["recent_vehicle_history"][0]
            # Path should be non-empty and absolute
            assert len(saved_path) > 0
            assert os_path.isabs(saved_path)


class TestRecentVehicleDirectoriesHistoryBackendSettings:
    """AC10: Backend Settings Structure."""

    def test_settings_file_contains_recent_vehicle_dirs_array(self) -> None:
        """
        Settings file structure includes recent_vehicle_history array.

        GIVEN: The application stores recent vehicle directories
        THEN: Settings should contain a "recent_vehicle_history" array
        AND: The array should contain maximum 5 string entries (full paths)
        AND: The array should be ordered with most recent first [0] to oldest [4]
        """
        # Arrange & Act: Mock settings structure
        with patch.object(ProgramSettings, "_get_settings_as_dict") as mock_get_settings:
            mock_get_settings.return_value = {
                "Format version": 1,
                "recent_vehicle_history": [
                    "/path/to/most_recent",
                    "/path/to/second",
                    "/path/to/third",
                    "/path/to/fourth",
                    "/path/to/oldest",
                ],
            }

            # Assert: Structure validation
            settings = ProgramSettings._get_settings_as_dict()
            assert "recent_vehicle_history" in settings
            assert isinstance(settings["recent_vehicle_history"], list)
            assert len(settings["recent_vehicle_history"]) <= ProgramSettings.MAX_RECENT_DIRS
            # Verify all entries are strings (paths)
            for entry in settings["recent_vehicle_history"]:
                assert isinstance(entry, str)
            # Most recent is at index 0
            assert settings["recent_vehicle_history"][0] == "/path/to/most_recent"

    def test_default_settings_includes_empty_recent_vehicle_dirs(self) -> None:
        """
        Default settings include recent_vehicle_history as empty array.

        GIVEN: Application is initialized with default settings
        WHEN: Default settings are generated
        THEN: recent_vehicle_history should exist and be an empty array
        """
        # Act: Get default settings structure
        defaults = ProgramSettings._get_settings_defaults()

        # Assert: recent_vehicle_history exists and is a list
        assert "recent_vehicle_history" in defaults
        assert isinstance(defaults["recent_vehicle_history"], list)
        assert not defaults["recent_vehicle_history"]


class TestRecentVehicleDirectoriesHistoryBackwardCompatibility:
    """Test backward compatibility with existing vehicle_dir setting."""

    def test_migration_seeds_recent_dirs_from_legacy_vehicle_dir(self) -> None:
        """
        Existing vehicle_dir setting seeds recent_vehicle_history on upgrade.

        GIVEN: Old settings with vehicle_dir but empty recent_vehicle_history (upgrading user)
        WHEN: Application reads recent directories for the first time
        THEN: recent_vehicle_history should be seeded with the legacy vehicle_dir
        AND: The migration should be persisted to settings
        """
        # Arrange: Old settings format with vehicle_dir but empty recent_vehicle_history
        captured_settings: dict = {}

        def capture_settings(settings: dict) -> None:
            captured_settings.update(settings)

        with (
            patch.object(ProgramSettings, "_get_settings_as_dict") as mock_get_settings,
            patch.object(ProgramSettings, "_set_settings_from_dict", side_effect=capture_settings) as mock_set_settings,
            patch.object(ProgramSettings, "_is_template_directory", return_value=False),
        ):
            # Use platform-appropriate absolute path for testing
            test_legacy_path = "C:\\path\\to\\old_vehicle" if platform_system() == "Windows" else "/path/to/old_vehicle"

            mock_get_settings.return_value = {
                "Format version": 1,
                "recent_vehicle_history": [],  # Empty (new key exists but no data)
                "directory_selection": {
                    "template_dir": "/templates/ArduCopter",
                    "vehicle_dir": test_legacy_path,  # Legacy setting from previous version
                },
            }

            # Act: Trigger migration explicitly (as done at application startup)
            ProgramSettings.migrate_settings_to_latest_version()

            # Then get recent directories
            recent_dirs = ProgramSettings.get_recent_vehicle_dirs()

            # Assert: Legacy vehicle_dir was migrated to recent_vehicle_history
            assert len(recent_dirs) == 1
            assert path_in_list(test_legacy_path, recent_dirs)

            # Assert: Migration was persisted and version updated
            mock_set_settings.assert_called_once()
            assert path_in_list(test_legacy_path, captured_settings["recent_vehicle_history"])
            assert captured_settings["Format version"] == 2

    def test_migration_does_not_occur_when_recent_dirs_already_has_entries(self) -> None:
        """
        Migration does not overwrite existing recent_vehicle_history entries.

        GIVEN: Settings have both recent_vehicle_history with entries AND legacy vehicle_dir
        WHEN: Application reads recent directories
        THEN: recent_vehicle_history should NOT be modified (no migration needed)
        """
        # Arrange: Settings with both new and old format
        with (
            patch.object(ProgramSettings, "_get_settings_as_dict") as mock_get_settings,
            patch.object(ProgramSettings, "_set_settings_from_dict") as mock_set_settings,
        ):
            mock_get_settings.return_value = {
                "Format version": 1,
                "recent_vehicle_history": ["/path/to/newer_vehicle"],  # Already has entries
                "directory_selection": {
                    "vehicle_dir": "/path/to/old_vehicle",  # Legacy setting should be ignored
                },
            }

            # Act: Get recent directories
            recent_dirs = ProgramSettings.get_recent_vehicle_dirs()

            # Assert: Only the existing entry, no migration
            assert recent_dirs == ["/path/to/newer_vehicle"]
            # Assert: No settings write occurred (no migration needed)
            mock_set_settings.assert_not_called()

    def test_migration_skips_default_template_paths(self) -> None:
        """
        Migration does not seed from vehicle_dir if it points to templates.

        GIVEN: Legacy vehicle_dir points to a vehicle_templates path (default, not user-set)
        WHEN: Application reads recent directories
        THEN: recent_vehicle_history should remain empty (not migrated from default)
        """
        # Arrange: vehicle_dir pointing to templates (default value)
        with (
            patch.object(ProgramSettings, "_get_settings_as_dict") as mock_get_settings,
            patch.object(ProgramSettings, "_set_settings_from_dict") as mock_set_settings,
        ):
            mock_get_settings.return_value = {
                "Format version": 1,
                "recent_vehicle_history": [],
                "directory_selection": {
                    "vehicle_dir": "/app/data/vehicle_templates/ArduCopter/empty_4.6.x",
                },
            }

            # Act: Get recent directories
            recent_dirs = ProgramSettings.get_recent_vehicle_dirs()

            # Assert: Empty list (template path not migrated)
            assert recent_dirs == []
            mock_set_settings.assert_not_called()


class TestRecentVehicleDirectoriesHistoryEdgeCases:
    """Test edge cases and error conditions."""

    def test_duplicate_path_with_different_separators_treated_as_same(self) -> None:
        r"""
        Paths with different separators but same location are treated as duplicates.

        GIVEN: History contains C:/Users/test/Vehicle
        WHEN: User opens C:\\Users\\test\\Vehicle
        THEN: Should be treated as same path, no duplicate created
        """
        # Arrange: Mock settings with path using forward slashes
        with (
            patch.object(ProgramSettings, "_get_settings_as_dict") as mock_get_settings,
            patch.object(ProgramSettings, "_set_settings_from_dict") as mock_set_settings,
        ):
            mock_get_settings.return_value = {
                "recent_vehicle_history": [
                    "C:/Users/test/Vehicle",  # Forward slashes
                ]
            }

            # Act: Store same path with backslashes
            ProgramSettings.store_recently_used_vehicle_dir("C:\\Users\\test\\Vehicle")

            # Assert: Should normalize and detect as duplicate
            mock_set_settings.assert_called_once()
            saved_settings = mock_set_settings.call_args[0][0]
            # Should only have one entry (no duplicate)
            normalized_entries = [p.replace("\\", "/") for p in saved_settings["recent_vehicle_history"]]
            assert normalized_entries.count("C:/Users/test/Vehicle") == 1

    def test_corrupted_history_returns_empty_list(self) -> None:
        """
        Corrupted history data is handled gracefully.

        GIVEN: Settings file has corrupted recent_vehicle_history (not a list)
        WHEN: Application tries to load recent directories
        THEN: Should return empty list without crashing
        """
        # Arrange: Corrupted data (string instead of list)
        with patch.object(ProgramSettings, "_get_settings_as_dict") as mock_get_settings:
            mock_get_settings.return_value = {"recent_vehicle_history": "corrupted_string_instead_of_list"}

            # Act & Assert: Should handle gracefully
            recent_dirs = ProgramSettings.get_recent_vehicle_dirs()
            assert isinstance(recent_dirs, list)


class TestRecentVehicleDirectoriesHistoryIntegration:
    """Integration tests with actual filesystem operations."""

    def test_can_store_and_retrieve_with_actual_temp_directories(self, tmp_path) -> None:
        """
        Integration test: Store and retrieve directories with real filesystem operations.

        GIVEN: Three temporary directories created on the filesystem
        WHEN: Each directory is stored in the history
        THEN: They should be retrievable in correct order
        AND: The paths should be normalized for the current platform
        """
        # Arrange: Create temporary directories
        dir1 = tmp_path / "vehicle_project_1"
        dir2 = tmp_path / "vehicle_project_2"
        dir3 = tmp_path / "vehicle_project_3"
        dir1.mkdir()
        dir2.mkdir()
        dir3.mkdir()

        # Mock file operations to use temp location
        with (
            patch.object(ProgramSettings, "_get_settings_as_dict") as mock_get_settings,
            patch.object(ProgramSettings, "_set_settings_from_dict") as mock_set_settings,
        ):
            captured_settings: dict = {"recent_vehicle_history": []}

            def get_settings() -> dict:
                return captured_settings.copy()

            def set_settings(settings: dict) -> None:
                captured_settings.update(settings)

            mock_get_settings.side_effect = get_settings
            mock_set_settings.side_effect = set_settings

            # Act: Store directories in order
            ProgramSettings.store_recently_used_vehicle_dir(str(dir1))
            ProgramSettings.store_recently_used_vehicle_dir(str(dir2))
            ProgramSettings.store_recently_used_vehicle_dir(str(dir3))

            # Assert: Retrieved in LIFO order (most recent first)
            recent_dirs = ProgramSettings.get_recent_vehicle_dirs()
            assert len(recent_dirs) == 3
            # Most recent is dir3 (last stored)
            assert path_in_list(str(dir3), recent_dirs)
            assert normalize_for_comparison(recent_dirs[0]) == normalize_for_comparison(str(dir3))

    def test_handles_mixed_separator_paths_correctly(self, tmp_path) -> None:
        """
        Integration test: Mixed separator paths are normalized correctly.

        GIVEN: A temporary directory path
        WHEN: The path is stored with different separator styles
        THEN: Should recognize them as the same path and not create duplicates
        """
        # Arrange: Create a temp directory
        test_dir = tmp_path / "test_vehicle"
        test_dir.mkdir()

        with (
            patch.object(ProgramSettings, "_get_settings_as_dict") as mock_get_settings,
            patch.object(ProgramSettings, "_set_settings_from_dict") as mock_set_settings,
        ):
            captured_settings: dict = {"recent_vehicle_history": []}

            def get_settings() -> dict:
                return captured_settings.copy()

            def set_settings(settings: dict) -> None:
                captured_settings.update(settings)

            mock_get_settings.side_effect = get_settings
            mock_set_settings.side_effect = set_settings

            # Act: Store with different separator styles
            path_str = str(test_dir)
            # Store once
            ProgramSettings.store_recently_used_vehicle_dir(path_str)
            # Store again with potentially different separators (pathlib normalized)
            ProgramSettings.store_recently_used_vehicle_dir(str(test_dir.absolute()))

            # Assert: Only one entry (no duplicates)
            recent_dirs = ProgramSettings.get_recent_vehicle_dirs()
            # Should have only 1 entry, not 2
            unique_normalized = {normalize_for_comparison(d) for d in recent_dirs}
            assert len(unique_normalized) == 1

    def test_validation_allows_relative_paths_for_storage(self) -> None:
        """
        Integration test: Relative paths are allowed for storage (permissive).

        GIVEN: A relative path is provided
        WHEN: Attempting to store it in history
        THEN: Should succeed (permissive storage allows potentially invalid paths)
              Path will be normalized to absolute during storage
        """
        settings_dict = {"recent_vehicle_history": []}

        with (
            patch.object(ProgramSettings, "_get_settings_as_dict", return_value=settings_dict),
            patch.object(ProgramSettings, "_set_settings_from_dict") as mock_set,
        ):
            # Act: Store relative path (should succeed with permissive storage)
            ProgramSettings.store_recently_used_vehicle_dir("relative/path/to/vehicle")

            # Assert: Path was stored (will be normalized to absolute)
            mock_set.assert_called_once()
            stored_settings = mock_set.call_args[0][0]
            assert len(stored_settings["recent_vehicle_history"]) == 1
            # Path gets resolved to absolute during normalization
            assert "vehicle" in stored_settings["recent_vehicle_history"][0]

    def test_validation_rejects_empty_string(self) -> None:
        """
        Integration test: Validation rejects empty paths.

        GIVEN: An empty string is provided
        WHEN: Attempting to store it in history
        THEN: Should raise ValueError (minimal validation for truly invalid input)
        """
        # Act & Assert: Empty string should be rejected
        with pytest.raises(ValueError, match="Cannot store empty string"):
            ProgramSettings.store_recently_used_vehicle_dir("")

    def test_validation_rejects_paths_with_null_byte(self) -> None:
        """
        Integration test: Validation rejects paths with null byte.

        GIVEN: A path with a null byte
        WHEN: Attempting to store it in history
        THEN: Should raise ValueError (minimal validation for universally invalid character)
        """
        # Use platform-appropriate absolute path with null byte
        test_path = "C:\\path\\with\x00null" if platform_system() == "Windows" else "/path/with\x00null"

        # Act & Assert: Path with null byte should be rejected
        with pytest.raises(ValueError, match="null byte"):
            ProgramSettings.store_recently_used_vehicle_dir(test_path)

    def test_validation_allows_long_paths_for_storage(self) -> None:
        """
        Integration test: Long paths are allowed for storage (permissive).

        GIVEN: A path longer than typical OS limits
        WHEN: Attempting to store it in history
        THEN: Should succeed (permissive storage allows paths that may be valid on other systems)
        """
        settings_dict = {"recent_vehicle_history": []}

        with (
            patch.object(ProgramSettings, "_get_settings_as_dict", return_value=settings_dict),
            patch.object(ProgramSettings, "_set_settings_from_dict") as mock_set,
        ):
            # Create a long absolute path (but not excessively long to avoid system limits during test)
            long_path = "C:\\" + "a" * 300 if platform_system() == "Windows" else "/" + "a" * 300

            # Act: Store long path (should succeed with permissive storage)
            ProgramSettings.store_recently_used_vehicle_dir(long_path)

            # Assert: Path was stored
            mock_set.assert_called_once()
            stored_settings = mock_set.call_args[0][0]
            assert len(stored_settings["recent_vehicle_history"]) == 1

    def test_cross_platform_path_handling(self, tmp_path) -> None:
        """
        Integration test: Paths are normalized correctly for the current platform.

        GIVEN: A temporary directory path
        WHEN: It is stored in history
        THEN: The stored path should use platform-appropriate separators
        """
        # Arrange: Create a temp directory
        test_dir = tmp_path / "cross_platform_test"
        test_dir.mkdir()

        with (
            patch.object(ProgramSettings, "_get_settings_as_dict") as mock_get_settings,
            patch.object(ProgramSettings, "_set_settings_from_dict") as mock_set_settings,
        ):
            captured_settings: dict = {"recent_vehicle_history": []}

            def get_settings() -> dict:
                return captured_settings.copy()

            def set_settings(settings: dict) -> None:
                captured_settings.update(settings)

            mock_get_settings.side_effect = get_settings
            mock_set_settings.side_effect = set_settings

            # Act: Store directory
            ProgramSettings.store_recently_used_vehicle_dir(str(test_dir))

            # Assert: Path uses correct separator for platform
            recent_dirs = ProgramSettings.get_recent_vehicle_dirs()
            assert len(recent_dirs) == 1
            stored_path = recent_dirs[0]

            if platform_system() == "Windows":
                # Windows should use backslashes (or at least not have forward slashes mixed in wrong way)
                # The path should be valid for Windows
                assert "\\\\" in stored_path or "/" not in stored_path or stored_path.count("/") == stored_path.count(":")
            else:
                # Unix-like should use forward slashes
                assert "/" in stored_path
