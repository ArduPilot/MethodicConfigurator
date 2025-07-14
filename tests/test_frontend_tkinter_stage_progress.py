#!/usr/bin/env python3

"""
Tests for the StageProgressBar class.

This file is part of Ardupilot methodic configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2025 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import tkinter as tk
import unittest
from unittest.mock import patch

from ardupilot_methodic_configurator.frontend_tkinter_stage_progress import StageProgressBar


class TestStageProgressBar(unittest.TestCase):
    """Test cases for the StageProgressBar class."""

    def setUp(self) -> None:
        """Set up test fixtures."""
        self.root = tk.Tk()
        self.test_phases = {
            "Phase 1": {"start": 1, "description": "First phase"},
            "Phase 2": {"start": 10, "description": "Second phase", "optional": True},
            "Phase 3": {"start": 20},
            "Milestone": {"description": "A milestone without start"},
        }
        self.total_steps = 30
        self.progress_bar = StageProgressBar(self.root, self.test_phases, self.total_steps, gui_complexity="normal")

    def tearDown(self) -> None:
        """Clean up after tests."""
        self.root.destroy()

    def test_initialization(self) -> None:
        """Test proper initialization of StageProgressBar."""
        assert self.progress_bar.total_files == self.total_steps
        assert self.progress_bar.phases == self.test_phases

        # Should only create frames for phases with start positions
        assert len(self.progress_bar.phase_frames) == 3
        assert "Milestone" not in self.progress_bar.phase_frames

    def test_phase_ordering(self) -> None:
        """Test that phases are ordered correctly by start position."""
        phase_names = list(self.progress_bar.phase_frames.keys())
        assert phase_names == ["Phase 1", "Phase 2", "Phase 3"]

    def test_progress_updates(self) -> None:
        """Test progress bar updates for different file positions."""
        test_cases = [
            (5, [4, 0, 0]),  # In Phase 1 (1-9)
            (15, [9, 5, 0]),  # In Phase 2 (10-19)
            (25, [9, 10, 5]),  # In Phase 3 (20-30)
            (29, [9, 10, 9]),  # Still in Phase 3, but not beyond total
        ]

        for current_file, expected_values in test_cases:
            self.progress_bar.update_progress(current_file)
            for test_bar, expected in zip(self.progress_bar.phase_bars, expected_values):
                assert test_bar["bar"]["value"] == expected

    def test_invalid_progress_update(self) -> None:
        """Test handling of invalid progress updates."""
        with self.assertLogs(level="ERROR"):
            self.progress_bar.update_progress(0)
            self.progress_bar.update_progress(31)

    @patch("tkinter.ttk.Label.configure")
    def test_resize_handling(self, mock_configure) -> None:
        """Test window resize handling."""
        self.root.geometry("400x300")
        self.progress_bar._on_resize()  # pylint: disable=protected-access

        # Should update wraplength for all phase labels
        expected_calls = len(self.progress_bar.phase_frames)
        assert mock_configure.call_count == expected_calls

    def test_optional_phase_styling(self) -> None:
        """Test that optional phases are styled correctly."""
        optional_frame = self.progress_bar.phase_frames["Phase 2"]
        normal_frame = self.progress_bar.phase_frames["Phase 1"]

        # Find labels in frames
        optional_label = None
        normal_label = None
        for child in optional_frame.winfo_children():
            if isinstance(child, tk.ttk.Label):
                optional_label = child
        for child in normal_frame.winfo_children():
            if isinstance(child, tk.ttk.Label):
                normal_label = child

        assert str(optional_label.cget("foreground")) == "gray"
        assert str(normal_label.cget("foreground")) == "black"

    def test_phase_frame_creation(self) -> None:
        """Test that phase frames are created with correct structure."""
        test_frame = self.progress_bar.phase_frames["Phase 1"]

        # Check frame structure
        children = test_frame.winfo_children()
        progressbar = None
        label = None
        for child in children:
            if isinstance(child, tk.ttk.Progressbar):
                progressbar = child
            elif isinstance(child, tk.ttk.Label):
                label = child

        assert progressbar is not None, "Progressbar should exist"
        assert label is not None, "Label should exist"
        assert str(progressbar.cget("orient")) == "horizontal"
        assert str(progressbar.cget("mode")) == "determinate"

    def test_progress_bar_limits(self) -> None:
        """Test progress bar maximum values are set correctly."""
        for i, phase in enumerate(self.progress_bar.phase_bars):
            test_bar = phase["bar"]
            start = phase["start"]
            end = phase["end"]

            # Check maximum is correctly set to phase range
            assert test_bar.cget("maximum") == end - start, f"Phase {i + 1} maximum should be {end - start}"

    def test_label_text_splitting(self) -> None:
        """Test text splitting behavior for different label lengths."""
        test_texts = {
            "A": {"start": 1},  # Very short
            "Short": {"start": 2},  # Short
            "Medium Text": {"start": 3},  # Medium with space
            "MediumNoSpace": {"start": 4},  # Medium without space
            "Very Long Phase Name Example": {"start": 5},  # Long with spaces
        }

        test_progress = StageProgressBar(self.root, test_texts, 10, "normal")

        for phase_name, frame in test_progress.phase_frames.items():
            label = None
            for child in frame.winfo_children():
                if isinstance(child, tk.ttk.Label):
                    label = child
                    break

            assert label is not None
            text = label.cget("text")

            if len(phase_name) <= 1:
                # Very short text should have padding newline
                assert text.endswith("\n "), f"Very short text '{phase_name}' missing padding newline"
            elif len(phase_name) < 6:
                # Short text should have newline
                assert "\n" in text, f"Short text '{phase_name}' missing newline"
            elif " " in phase_name and len(phase_name) < 20:
                # Medium text with space should split at first space
                first_space_pos = phase_name.find(" ")
                expected_newline_pos = text.find("\n")
                assert expected_newline_pos == first_space_pos, f"Medium text '{phase_name}' not split at first space"


if __name__ == "__main__":
    unittest.main()
