#!/usr/bin/python3

"""
Tests for the extract_missing_translations.py file.

Tests the extraction of missing translations from a .po file.

SPDX-FileCopyrightText: 2024-2025 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import os
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, call, patch

import pytest

# Add the parent directory to the path to import the script
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# pylint: disable=wrong-import-position
import extract_missing_translations

# pylint: enable=wrong-import-position


class TestExtractMissingTranslations(unittest.TestCase):
    """Tests for the extract_missing_translations functionality using unittest framework."""

    def setUp(self) -> None:
        # Set up a test po file path
        self.test_po_file = os.path.join(os.path.dirname(__file__), "test_extract_missing_translations_input.po")

    def test_parse_arguments_real(self) -> None:
        # Test with actual argument parser
        with patch("sys.argv", ["extract_missing_translations.py"]):
            args = extract_missing_translations.parse_arguments()
            assert args.lang_code == "all"  # Default value
            assert args.output_file == "missing_translations"  # Default value
            assert args.max_translations == 60  # Default value

        # Test with custom arguments
        with patch(
            "sys.argv",
            ["extract_missing_translations.py", "--lang-code", "ja", "--output-file", "test_out", "--max-translations", "30"],
        ):
            args = extract_missing_translations.parse_arguments()
            assert args.lang_code == "ja"
            assert args.output_file == "test_out"
            assert args.max_translations == 30

    @patch("extract_missing_translations.argparse.ArgumentParser.parse_args")
    def test_parse_arguments_mock(self, mock_parse_args) -> None:
        # Use a proper mock object with the expected attributes
        mock_args = MagicMock()
        mock_args.lang_code = "zh_CN"
        mock_args.output_file = "missing_translations"
        mock_args.max_translations = 60
        mock_parse_args.return_value = mock_args

        args = extract_missing_translations.parse_arguments()
        assert args.lang_code == "zh_CN"
        assert args.output_file == "missing_translations"
        assert args.max_translations == 60

    @patch("extract_missing_translations.open")
    @patch("extract_missing_translations.gettext.translation")
    def test_extract_missing_translations_fixed(self, mock_translation, mock_open) -> None:
        # Mock the gettext translation
        mock_translator = MagicMock()
        # Make gettext return the same string for Test string 1, but a different string for Test string 2
        mock_translator.gettext.side_effect = lambda x: x if x == "Test string 1" else "Translated"
        mock_translation.return_value = mock_translator

        # Mock file reading
        mock_file = MagicMock()
        mock_file.__enter__.return_value.readlines.return_value = [
            'msgid "Test string 1"\n',
            'msgstr ""\n',
            'msgid "Test string 2"\n',
            'msgstr "Translated"\n',
            "\n",
        ]
        mock_open.return_value = mock_file

        result = extract_missing_translations.extract_missing_translations("ja")
        assert len(result) == 1
        assert result[0][1] == "Test string 1"

    @patch("extract_missing_translations.os.path.join")
    @patch("extract_missing_translations.open")
    @patch("extract_missing_translations.gettext.translation")
    def test_extract_missing_translations_with_real_file(self, mock_translation, mock_open, mock_path_join) -> None:
        # Set the path to our test file
        mock_path_join.return_value = self.test_po_file

        # Open the actual test file for reading its content
        with open(self.test_po_file, encoding="utf-8") as f:
            actual_lines = f.readlines()

        # Mock file reading to return actual content from test file
        mock_file = MagicMock()
        mock_file.__enter__.return_value.readlines.return_value = actual_lines
        mock_open.return_value = mock_file

        # Mock the gettext translation
        mock_translator = MagicMock()
        # Make gettext return the same string to simulate missing translations
        mock_translator.gettext.side_effect = lambda x: x
        mock_translation.return_value = mock_translator

        result = extract_missing_translations.extract_missing_translations("ja")
        # We should have at least 6 missing translations from the test file
        assert len(result) == 6

        # Normalize the strings to handle escape sequences
        def normalize_string(s: str) -> str:
            return s.replace('\\"', '"').replace("\\n", "\n")

        # Normalize the actual output for comparison
        normalized_entries = [normalize_string(entry) for _, entry in result]

        # Verify specific entries that should be identified as missing
        expected_missing = [
            "ArduPilot methodic configurator is a simple GUI with a table that lists parameters. "
            "The GUI reads intermediate parameter files from a directory and displays their parameters in a table. "
            "Each row displays the parameter name, its current value on the flight controller, its new value from "
            'the selected intermediate parameter file, and an "Upload" checkbox. The GUI includes "Upload selected '
            'params to FC" and "Skip" buttons at the bottom. When "Upload Selected to FC" is clicked, it uploads '
            'the selected parameters to the flight controller. When "Skip" is pressed, it skips to the next '
            "intermediate parameter file. The process gets repeated for each intermediate parameter file.",
            "No serial ports found",
            "Vehicle type not set explicitly, auto-detected %s.",
            "Vehicle type explicitly set to %s.",
            "Unknown",
            "ArduPilot Methodic Configurator Version: {_version}\n\n"
            "A clear configuration sequence for ArduPilot vehicles.\n\n"
            "Copyright © 2024-2025 Amilcar do Carmo Lucas and ArduPilot.org\n\n"
            "Licensed under the GNU General Public License v3.0",
        ]

        for expected in expected_missing:
            assert any(expected in norm_entry for norm_entry in normalized_entries), (
                f"Expected string not found in normalized entries: {expected}"
            )

    @patch("extract_missing_translations.logging.error")
    @patch("extract_missing_translations.open")
    @patch("extract_missing_translations.gettext.translation")
    def test_extract_missing_translations_with_malformed_line(self, mock_translation, mock_open, mock_logging) -> None:
        # Mock the gettext translation
        mock_translator = MagicMock()
        mock_translator.gettext.side_effect = lambda x: x
        mock_translation.return_value = mock_translator

        # Mock file reading with a malformed line
        mock_file = MagicMock()
        mock_file.__enter__.return_value.readlines.return_value = [
            "msgid bad format line\n",  # Malformed line
            'msgstr ""\n',
        ]
        mock_open.return_value = mock_file

        result = extract_missing_translations.extract_missing_translations("ja")
        # Check that the result is empty (malformed lines are skipped)
        assert len(result) == 0
        # Check that the error was logged
        mock_logging.assert_called_once()

    def test_output_to_files_with_empty_list(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdirname:
            output_path = os.path.join(tmpdirname, "test_empty")
            extract_missing_translations.output_to_files([], output_path, 10)
            # No files should be created for empty list
            assert len(os.listdir(tmpdirname)) == 0

    def test_output_to_files_exact_max_translations(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdirname:
            output_path = os.path.join(tmpdirname, "test_exact")
            missing_translations = [(1, "Test 1"), (2, "Test 2"), (3, "Test 3")]
            extract_missing_translations.output_to_files(missing_translations, output_path, 3)
            # Should create exactly one file
            assert len(os.listdir(tmpdirname)) == 1

            with open(f"{output_path}.txt", encoding="utf-8") as f:
                content = f.read()
                assert "1:Test 1" in content
                assert "2:Test 2" in content
                assert "3:Test 3" in content

    def test_output_to_files_multiple_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdirname:
            output_path = os.path.join(tmpdirname, "test_multiple")
            missing_translations = [(1, "Test 1"), (2, "Test 2"), (3, "Test 3"), (4, "Test 4"), (5, "Test 5")]
            extract_missing_translations.output_to_files(missing_translations, output_path, 2)
            # Should create 3 files (ceiling division of 5/2)
            assert len(os.listdir(tmpdirname)) == 3

            with open(f"{output_path}_1.txt", encoding="utf-8") as f:
                content = f.read()
                assert "1:Test 1" in content
                assert "2:Test 2" in content

            with open(f"{output_path}_2.txt", encoding="utf-8") as f:
                content = f.read()
                assert "3:Test 3" in content
                assert "4:Test 4" in content

            with open(f"{output_path}_3.txt", encoding="utf-8") as f:
                content = f.read()
                assert "5:Test 5" in content

    @patch("extract_missing_translations.glob.glob")
    @patch("extract_missing_translations.os.remove")
    def test_output_to_files_removes_existing_files(self, mock_remove, mock_glob) -> None:
        mock_glob.side_effect = lambda pattern: ["file1.txt", "file2.txt", "file3.txt"] if pattern.endswith("*.txt") else []

        extract_missing_translations.output_to_files([], "test_output", 10)

        # Should attempt to remove all three existing files
        assert mock_remove.call_count == 3
        calls = [call("file1.txt"), call("file2.txt"), call("file3.txt")]
        mock_remove.assert_has_calls(calls, any_order=True)

    @patch("extract_missing_translations.parse_arguments")
    @patch("extract_missing_translations.extract_missing_translations")
    @patch("extract_missing_translations.output_to_files")
    def test_main_with_large_number_of_translations(self, mock_output, mock_extract, mock_args) -> None:
        # Test main with a large number of translations
        mock_args_instance = MagicMock()
        mock_args_instance.lang_code = "fr"
        mock_args_instance.output_file = "test_large"
        mock_args_instance.max_translations = 5
        mock_args.return_value = mock_args_instance

        # Create a large list of translations
        large_translations = [(i, f"Test string {i}") for i in range(20)]
        mock_extract.return_value = large_translations

        extract_missing_translations.main()

        # Verify the function was called with the correct parameters
        mock_extract.assert_called_once_with("fr")
        mock_output.assert_called_once_with(large_translations, "test_large_fr", 5)

    @patch("extract_missing_translations.open")
    @patch("extract_missing_translations.gettext.translation")
    def test_extract_missing_translations(self, mock_translation, mock_open) -> None:
        # Mock the gettext translation
        mock_translator = MagicMock()

        # Make gettext return the same string to simulate missing translations for Test string 1
        # But return a different string for Test string 2 to simulate it's already translated
        def mock_gettext(text: str) -> str:
            if text == "Test string 1":
                return text
            return "Translated Test string 2"

        mock_translator.gettext.side_effect = mock_gettext
        mock_translation.return_value = mock_translator

        # Mock file reading
        mock_file = MagicMock()
        mock_file.__enter__.return_value.readlines.return_value = [
            'msgid "Test string 1"\n',
            'msgstr ""\n',
            'msgid "Test string 2"\n',
            'msgstr "Translated"\n',
            "\n",
        ]
        mock_open.return_value = mock_file

        result = extract_missing_translations.extract_missing_translations("ja")
        assert len(result) == 1
        assert result[0][1] == "Test string 1"

    @patch("extract_missing_translations.parse_arguments")
    @patch("extract_missing_translations.extract_missing_translations")
    @patch("extract_missing_translations.output_to_files")
    @patch("extract_missing_translations.logging.basicConfig")
    def test_main(self, mock_logging, mock_output, mock_extract, mock_args) -> None:
        # Test the main function
        mock_args_instance = MagicMock()
        mock_args_instance.lang_code = "ja"
        mock_args_instance.output_file = "test_output"
        mock_args_instance.max_translations = 50
        mock_args.return_value = mock_args_instance

        mock_extract.return_value = [(1, "Test string 1")]

        extract_missing_translations.main()

        mock_extract.assert_called_once_with("ja")
        mock_output.assert_called_once_with([(1, "Test string 1")], "test_output_ja", 50)
        mock_logging.assert_called_once()


# These are pytest-style standalone functions, outside the class
@pytest.fixture
def temp_dir() -> str:
    with tempfile.TemporaryDirectory() as tmpdirname:
        yield tmpdirname


def test_output_to_files_real(temp_dir) -> None:  # pylint: disable=redefined-outer-name
    # Test with real file output
    missing_translations = [(1, "Test string 1"), (5, "Test string 2"), (10, "Test string 3")]
    output_path = os.path.join(temp_dir, "test_output")

    extract_missing_translations.output_to_files(missing_translations, output_path, 2)

    # Check that files were created
    assert os.path.exists(f"{output_path}_1.txt")
    assert os.path.exists(f"{output_path}_2.txt")

    # Check file contents
    with open(f"{output_path}_1.txt", encoding="utf-8") as f:
        content = f.read()
        assert "1:Test string 1" in content
        assert "5:Test string 2" in content

    with open(f"{output_path}_2.txt", encoding="utf-8") as f:
        content = f.read()
        assert "10:Test string 3" in content


def test_extract_missing_translations_with_real_po_file() -> None:
    # Test with the actual test PO file to verify it works correctly
    test_po_file = os.path.join(os.path.dirname(__file__), "test_extract_missing_translations_input.po")

    # Skip this test if the file doesn't exist
    if not os.path.exists(test_po_file):
        pytest.skip(f"Test PO file not found: {test_po_file}")

    # Use a single with statement with multiple contexts instead of nested with statements
    with (
        patch("extract_missing_translations.os.path.join", return_value=test_po_file),
        patch("extract_missing_translations.gettext.translation") as mock_translation,
    ):
        # Mock translator to simulate all strings are untranslated
        mock_translator = MagicMock()
        mock_translator.gettext.side_effect = lambda x: x
        mock_translation.return_value = mock_translator

        result = extract_missing_translations.extract_missing_translations("ja")

        # Verify we have exactly 6 missing translations
        assert len(result) == 6

        # Create a dictionary of line numbers to strings for easier verification
        missing_by_line = dict(result)

        # Verify all expected strings are present with correct line numbers
        expected_strings = [
            (20, "ArduPilot methodic configurator is a simple GUI"),
            (24, "No serial ports found"),
            (27, "Vehicle type not set explicitly, auto-detected %s."),
            (32, "Vehicle type explicitly set to %s."),
            (45, "Unknown"),
            (56, "ArduPilot Methodic Configurator Version:"),
        ]

        for expected_line, expected_text in expected_strings:
            assert expected_line in missing_by_line
            assert expected_text in missing_by_line[expected_line]
