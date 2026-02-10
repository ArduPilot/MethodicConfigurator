#!/usr/bin/env python3

"""
Tests for the StageProgressBar class.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import tkinter as tk
from collections.abc import Generator

import pytest

from ardupilot_methodic_configurator.backend_filesystem_configuration_steps import ConfigurationSteps, PhaseData
from ardupilot_methodic_configurator.frontend_tkinter_stage_progress import StageProgressBar

# pylint: disable=redefined-outer-name, too-few-public-methods


@pytest.fixture
def root_window() -> Generator[tk.Tk, None, None]:
    """Fixture providing a tkinter root window for testing."""
    root = tk.Tk()
    yield root
    root.destroy()


@pytest.fixture
def raw_phases() -> dict[str, PhaseData]:
    """Fixture providing raw phase configuration data."""
    return {
        "Phase 1": {"start": 1, "description": "First phase"},
        "Phase 2": {"start": 10, "description": "Second phase", "optional": True},
        "Phase 3": {"start": 20},
        "Milestone": {"description": "A milestone without start"},
    }


@pytest.fixture
def processed_phases(raw_phases) -> dict[str, PhaseData]:
    """Fixture providing processed phase data with end and weight keys."""
    # Use the actual ConfigurationSteps method to process phases
    # This ensures the fixture stays in sync with production code
    config_steps = ConfigurationSteps("", "ArduCopter")

    # Temporarily set phases to our test data
    config_steps.configuration_phases = raw_phases

    # Use the actual method to process phases
    return config_steps.get_sorted_phases_with_end_and_weight(30)


@pytest.fixture
def progress_bar(root_window: tk.Tk, processed_phases: dict[str, PhaseData]) -> StageProgressBar:
    """Fixture providing a configured StageProgressBar instance."""
    return StageProgressBar(root_window, processed_phases, 30, gui_complexity="normal")


class TestStageProgressBarInitialization:
    """Test StageProgressBar initialization and basic setup."""

    def test_user_sees_progress_bar_with_correct_total_steps(self, progress_bar) -> None:
        """
        User sees progress bar initialized with correct total configuration steps.

        GIVEN: A progress bar is created with 30 total steps
        WHEN: The progress bar is initialized
        THEN: It should track the correct total number of steps
        """
        assert progress_bar.total_files == 30

    def test_user_sees_progress_bar_with_processed_phase_data(self, progress_bar, processed_phases) -> None:
        """
        User sees progress bar configured with processed phase information.

        GIVEN: Phase data has been processed to include end positions and weights
        WHEN: The progress bar is initialized
        THEN: It should contain the processed phase configuration
        """
        assert progress_bar.phases == processed_phases

    def test_user_sees_only_active_phases_displayed(self, progress_bar) -> None:
        """
        User sees only phases with start positions displayed in the progress bar.

        GIVEN: Phase configuration includes both active phases and milestones
        WHEN: The progress bar creates phase frames
        THEN: Only phases with start positions should be displayed
        AND: Milestones without start positions should be excluded
        """
        # Should only create frames for phases with start positions
        assert len(progress_bar.phase_frames) == 3
        assert "Milestone" not in progress_bar.phase_frames
        assert "Phase 1" in progress_bar.phase_frames
        assert "Phase 2" in progress_bar.phase_frames
        assert "Phase 3" in progress_bar.phase_frames


class TestPhaseOrdering:
    """Test that phases are ordered correctly in the progress bar."""

    def test_user_sees_phases_ordered_by_start_position(self, progress_bar) -> None:
        """
        User sees configuration phases ordered by their start positions.

        GIVEN: Multiple phases with different start positions
        WHEN: The progress bar displays the phases
        THEN: Phases should be ordered from left to right by start position
        """
        phase_names = list(progress_bar.phase_frames.keys())
        assert phase_names == ["Phase 1", "Phase 2", "Phase 3"]


class TestProgressUpdates:
    """Test progress bar updates as configuration advances."""

    def test_user_sees_progress_update_within_first_phase(self, progress_bar) -> None:
        """
        User sees progress bar update correctly within the first configuration phase.

        GIVEN: Configuration is in progress within Phase 1 (files 1-9)
        WHEN: Progress advances to file 5
        THEN: Phase 1 should show 4/9 progress
        AND: Other phases should remain at 0%
        """
        progress_bar.update_progress(5)

        phase_1_bar = progress_bar.phase_bars[0]["bar"]
        phase_2_bar = progress_bar.phase_bars[1]["bar"]
        phase_3_bar = progress_bar.phase_bars[2]["bar"]

        assert phase_1_bar["value"] == 4  # 5 - 1 = 4
        assert phase_2_bar["value"] == 0
        assert phase_3_bar["value"] == 0

    def test_user_sees_progress_update_within_second_phase(self, progress_bar) -> None:
        """
        User sees progress bar update correctly within the second configuration phase.

        GIVEN: Configuration has completed Phase 1 and is in Phase 2 (files 10-19)
        WHEN: Progress advances to file 15
        THEN: Phase 1 should be complete (9/9)
        AND: Phase 2 should show 5/10 progress
        AND: Phase 3 should remain at 0%
        """
        progress_bar.update_progress(15)

        phase_1_bar = progress_bar.phase_bars[0]["bar"]
        phase_2_bar = progress_bar.phase_bars[1]["bar"]
        phase_3_bar = progress_bar.phase_bars[2]["bar"]

        assert phase_1_bar["value"] == 9  # Phase 1 complete
        assert phase_2_bar["value"] == 5  # 15 - 10 = 5
        assert phase_3_bar["value"] == 0

    def test_user_sees_progress_update_within_third_phase(self, progress_bar) -> None:
        """
        User sees progress bar update correctly within the third configuration phase.

        GIVEN: Configuration has completed Phases 1-2 and is in Phase 3 (files 20-30)
        WHEN: Progress advances to file 25
        THEN: Phase 1 should be complete (9/9)
        AND: Phase 2 should be complete (10/10)
        AND: Phase 3 should show 5/10 progress
        """
        progress_bar.update_progress(25)

        phase_1_bar = progress_bar.phase_bars[0]["bar"]
        phase_2_bar = progress_bar.phase_bars[1]["bar"]
        phase_3_bar = progress_bar.phase_bars[2]["bar"]

        assert phase_1_bar["value"] == 9  # Phase 1 complete
        assert phase_2_bar["value"] == 10  # Phase 2 complete
        assert phase_3_bar["value"] == 5  # 25 - 20 = 5

    def test_user_sees_all_phases_complete_at_final_step(self, progress_bar) -> None:
        """
        User sees all phases complete when configuration reaches the final step.

        GIVEN: Configuration is at the final step
        WHEN: Progress advances to file 29 (last file in Phase 3)
        THEN: All phases should show complete progress
        """
        progress_bar.update_progress(29)

        phase_1_bar = progress_bar.phase_bars[0]["bar"]
        phase_2_bar = progress_bar.phase_bars[1]["bar"]
        phase_3_bar = progress_bar.phase_bars[2]["bar"]

        assert phase_1_bar["value"] == 9  # Phase 1 complete
        assert phase_2_bar["value"] == 10  # Phase 2 complete
        assert phase_3_bar["value"] == 9  # 29 - 20 = 9


class TestErrorHandling:
    """Test error handling for invalid progress updates."""

    def test_user_sees_error_logged_for_invalid_progress_values(self, progress_bar, caplog) -> None:
        """
        User sees error logged when invalid progress values are provided.

        GIVEN: A progress bar is configured with valid range
        WHEN: Invalid progress values are provided (0 or out of range)
        THEN: Error messages should be logged
        """
        with caplog.at_level("ERROR"):
            progress_bar.update_progress(0)  # Below minimum
            progress_bar.update_progress(31)  # Above maximum

        assert "Out of expected range" in caplog.text

    def test_user_can_update_progress_at_final_step_number(self, progress_bar, caplog) -> None:
        """
        User can update progress when current file equals total files (final step).

        GIVEN: A progress bar is configured with total_files=30
        WHEN: Progress is updated to step 30 (total_files)
        THEN: No error should be logged
        AND: Progress should update normally
        """
        with caplog.at_level("ERROR"):
            progress_bar.update_progress(30)  # Final step - should be valid

        assert "Out of expected range" not in caplog.text


class TestWindowResizing:
    """Test progress bar behavior during window resizing."""

    def test_user_sees_labels_adjust_when_window_resizes(self, progress_bar) -> None:
        """
        User sees progress bar labels adjust when window is resized.

        GIVEN: A progress bar with multiple phase labels
        WHEN: The window is resized
        THEN: Label wraplength should be updated for all labels
        AND: Wraplength should change from initial values
        """
        # Store initial wraplength values
        initial_wraplengths = {}
        for phase_name, frame in progress_bar.phase_frames.items():
            for child in frame.winfo_children():
                if isinstance(child, tk.ttk.Label):
                    initial_wraplengths[phase_name] = child.cget("wraplength")

        # Simulate window resize by updating width and calling resize handler
        progress_bar.winfo_width = lambda: 800  # Simulate wider window
        progress_bar._on_resize()  # pylint: disable=protected-access

        # Verify wraplength has been updated for all phase labels
        for phase_name, frame in progress_bar.phase_frames.items():
            for child in frame.winfo_children():
                if isinstance(child, tk.ttk.Label):
                    # Wraplength should be set to a positive value
                    current_wraplength = child.cget("wraplength")
                    initial_wraplength = initial_wraplengths[phase_name]
                    assert current_wraplength > 0, f"Label for {phase_name} should have wraplength > 0"
                    assert current_wraplength != initial_wraplength, (
                        f"Label for {phase_name} wraplength should change after resize"
                    )


class TestOptionalPhaseStyling:
    """Test visual styling of optional phases."""

    def test_user_sees_optional_phases_displayed_in_gray(self, progress_bar) -> None:
        """
        User sees optional phases displayed in gray text color.

        GIVEN: Phase configuration includes optional phases
        WHEN: The progress bar displays phase labels
        THEN: Optional phases should be styled in gray
        AND: Required phases should be styled in black
        """
        optional_frame = progress_bar.phase_frames["Phase 2"]  # Optional phase
        normal_frame = progress_bar.phase_frames["Phase 1"]  # Required phase

        # Find labels in frames
        optional_label = None
        normal_label = None
        for child in optional_frame.winfo_children():
            if isinstance(child, tk.ttk.Label):
                optional_label = child
        for child in normal_frame.winfo_children():
            if isinstance(child, tk.ttk.Label):
                normal_label = child

        assert optional_label is not None
        assert normal_label is not None
        assert str(optional_label.cget("foreground")) == "gray"
        assert str(normal_label.cget("foreground")) == "black"


class TestPhaseFrameStructure:
    """Test the internal structure of phase frames."""

    def test_user_sees_correct_frame_structure_for_each_phase(self, progress_bar) -> None:
        """
        User sees each phase frame contains the expected UI components.

        GIVEN: A progress bar with multiple phases
        WHEN: Phase frames are created
        THEN: Each frame should contain a progress bar and label
        AND: Progress bars should be configured horizontally and determinately
        """
        test_frame = progress_bar.phase_frames["Phase 1"]

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


class TestProgressBarLimits:
    """Test that progress bars have correct maximum values."""

    def test_user_sees_progress_bars_with_correct_maximum_values(self, progress_bar) -> None:
        """
        User sees progress bars configured with correct maximum values for each phase.

        GIVEN: Phases have defined start and end positions
        WHEN: Progress bars are created
        THEN: Each progress bar should have maximum set to phase range (end - start)
        """
        for i, phase in enumerate(progress_bar.phase_bars):
            test_bar = phase["bar"]
            start = phase["start"]
            end = phase["end"]

            # Check maximum is correctly set to phase range
            expected_max = end - start
            assert test_bar.cget("maximum") == expected_max, f"Phase {i + 1} maximum should be {expected_max}"


class TestLabelTextFormatting:
    """Test automatic text formatting for phase labels."""

    def test_user_sees_very_short_labels_formatted_with_padding(self, root_window) -> None:
        """
        User sees very short phase names formatted with padding newlines.

        GIVEN: A phase with a very short name (1 character or less)
        WHEN: The progress bar creates the label
        THEN: The label should end with padding newline and space
        """
        test_phases: dict[str, PhaseData] = {"A": {"start": 1, "end": 5, "weight": 4}}
        progress = StageProgressBar(root_window, test_phases, 10, "normal")

        frame = progress.phase_frames["A"]
        label = None
        for child in frame.winfo_children():
            if isinstance(child, tk.ttk.Label):
                label = child
                break

        assert label is not None
        text = label.cget("text")
        assert text.endswith("\n "), "Very short text 'A' missing padding newline"

    def test_user_sees_short_labels_formatted_with_newlines(self, root_window) -> None:
        """
        User sees short phase names formatted with newlines.

        GIVEN: A phase with a short name (2-5 characters)
        WHEN: The progress bar creates the label
        THEN: The label should contain a newline
        """
        test_phases: dict[str, PhaseData] = {"Short": {"start": 1, "end": 5, "weight": 4}}
        progress = StageProgressBar(root_window, test_phases, 10, "normal")

        frame = progress.phase_frames["Short"]
        label = None
        for child in frame.winfo_children():
            if isinstance(child, tk.ttk.Label):
                label = child
                break

        assert label is not None
        text = label.cget("text")
        assert "\n" in text, "Short text 'Short' missing newline"

    def test_user_sees_medium_labels_with_spaces_split_at_first_space(self, root_window) -> None:
        """
        User sees medium-length phase names with spaces split at the first space.

        GIVEN: A phase with medium-length name containing spaces
        WHEN: The progress bar creates the label
        THEN: The label should be split at the first space position
        """
        test_phases: dict[str, PhaseData] = {"Medium Text": {"start": 1, "end": 5, "weight": 4}}
        progress = StageProgressBar(root_window, test_phases, 10, "normal")

        frame = progress.phase_frames["Medium Text"]
        label = None
        for child in frame.winfo_children():
            if isinstance(child, tk.ttk.Label):
                label = child
                break

        assert label is not None
        text = label.cget("text")
        first_space_pos = "Medium Text".find(" ")
        expected_newline_pos = text.find("\n")
        assert expected_newline_pos == first_space_pos, "Medium text 'Medium Text' not split at first space"
