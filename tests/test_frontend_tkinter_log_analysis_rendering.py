#!/usr/bin/env python3
"""
Focused rendering assertions for the detailed log analysis report.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-FileCopyrightText: 2026 Omkar Sarkar <omkarsarkar24@gmail.com>

SPDX-License-Identifier: GPL-3.0-or-later
"""

# pylint: disable=protected-access, redefined-outer-name, duplicate-code

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock, call, patch

import pytest
from test_frontend_tkinter_log_analysis import (
    _make_analysis_result,
    _make_availability_issue,
    _make_availability_result,
)

from ardupilot_methodic_configurator.frontend_tkinter_log_analysis import LogAnalysisReportWindow, Severity

if TYPE_CHECKING:
    from pytest_mock import MockerFixture

MODULE = "ardupilot_methodic_configurator.frontend_tkinter_log_analysis"


@pytest.fixture
def patched_widgets(mocker: MockerFixture) -> dict[str, MagicMock]:
    """Patch the widgets constructed by the report window."""
    return {
        "frame": mocker.patch(f"{MODULE}.ttk.Frame", return_value=MagicMock()),
        "label": mocker.patch(f"{MODULE}.ttk.Label", return_value=MagicMock(pack=MagicMock())),
        "label_frame": mocker.patch(f"{MODULE}.ttk.LabelFrame", return_value=MagicMock(pack=MagicMock())),
        "button": mocker.patch(f"{MODULE}.ttk.Button", return_value=MagicMock(pack=MagicMock(), configure=MagicMock())),
        "combobox": mocker.patch(f"{MODULE}.AutoResizeCombobox", return_value=MagicMock()),
        "scroll_frame": mocker.patch(
            f"{MODULE}.ScrollFrame", return_value=MagicMock(view_port=MagicMock(winfo_children=MagicMock(return_value=[])))
        ),
        "show_tooltip": mocker.patch(f"{MODULE}.show_tooltip"),
    }


@pytest.fixture
def bare_window() -> LogAnalysisReportWindow:
    """Create a report window without initializing a physical Tk window."""
    window = LogAnalysisReportWindow.__new__(LogAnalysisReportWindow)
    window.root = MagicMock()
    window.main_frame = MagicMock()
    window.summary = MagicMock(related_parameter_values={})
    window.body_frame = MagicMock(winfo_children=MagicMock(return_value=[]))
    return window


class TestFocusedReportRendering:
    """Check user visible report header, legend, and subsystem details."""

    def test_header_explains_and_configures_subsystem_selection(self, patched_widgets: dict[str, MagicMock]) -> None:
        """
        The report header identifies the page and offers the available subsystem choices.

        GIVEN: A report window with Battery and GPS subsystem summaries
        WHEN: The header is built
        THEN: The selector lists both names, starts at Battery, and explains how to use it
        """
        window = LogAnalysisReportWindow.__new__(LogAnalysisReportWindow)
        window.main_frame = MagicMock()
        window.subsystem_names = ["Battery", "GPS"]
        created_frames: list[MagicMock] = []

        def make_frame(*_args: object, **_kwargs: object) -> MagicMock:
            frame = MagicMock()
            created_frames.append(frame)
            return frame

        patched_widgets["frame"].side_effect = make_frame

        window._build_header()

        selector = patched_widgets["combobox"].return_value
        assert patched_widgets["combobox"].call_args.args[1:4] == (
            ["Battery", "GPS"],
            "Battery",
            "Select a subsystem to view its details",
        )
        assert patched_widgets["combobox"].call_args.kwargs == {
            "state": "readonly",
            "width": 30,
        }
        selector.bind.assert_called_once()
        assert selector.bind.call_args.args[0] == "<<ComboboxSelected>>"
        labels = [call.kwargs.get("text") for call in patched_widgets["label"].call_args_list]
        assert "Log Analysis" in labels
        assert "Subsystem:" in labels
        header, left_column, selector_row, right_column = (
            created_frames[0],
            created_frames[1],
            created_frames[2],
            created_frames[3],
        )
        assert patched_widgets["frame"].call_args_list[:4] == [
            call(window.main_frame),
            call(header),
            call(left_column),
            call(header),
        ]
        assert header.pack.call_args == call(side="top", fill="x", padx=20, pady=(16, 4))
        assert left_column.pack.call_args == call(side="left", anchor="nw")
        assert selector_row.pack.call_args == call(anchor="w", pady=(8, 0))
        assert right_column.pack.call_args == call(side="right", anchor="ne")
        title_call, subsystem_call = patched_widgets["label"].call_args_list[:2]
        assert title_call.args[0] == left_column
        assert title_call.kwargs == {"text": "Log Analysis", "font": ("TkDefaultFont", 16, "bold")}
        assert subsystem_call.args[0] == selector_row
        assert subsystem_call.kwargs == {"text": "Subsystem:", "font": ("TkDefaultFont", 13, "bold")}
        assert patched_widgets["label"].return_value.pack.call_args_list[0] == call(anchor="w")

    def test_legend_shows_each_severity_with_its_color_and_guidance(  # pylint: disable=too-many-locals
        self, patched_widgets: dict[str, MagicMock]
    ) -> None:
        """
        Each report severity has a visible label, matching marker color, and explanatory tooltip.

        GIVEN: A report header that includes the severity legend
        WHEN: The legend is built
        THEN: Users can distinguish all severity levels and read their guidance
        """
        window = LogAnalysisReportWindow.__new__(LogAnalysisReportWindow)
        parent = MagicMock()
        created_frames: list[MagicMock] = []

        def make_frame(*_args: object, **_kwargs: object) -> MagicMock:
            frame = MagicMock()
            created_frames.append(frame)
            return frame

        patched_widgets["frame"].side_effect = make_frame

        window._build_legend(parent)

        labels = [call.kwargs for call in patched_widgets["label"].call_args_list]
        assert patched_widgets["show_tooltip"].call_args_list[0] == call(
            patched_widgets["label_frame"].return_value,
            "Severity of a finding",
            position_below=False,
        )
        tooltips = [call.args[1] for call in patched_widgets["show_tooltip"].call_args_list]
        for _severity, label, color, guidance in (
            (Severity.SEVERE, "Severe", "red3", "A serious issue that should be fixed before further flights"),
            (Severity.NEEDS_ATTENTION, "Needs attention", "dark orange", "Worth reviewing, may or may not need action"),
            (Severity.INFORMATIONAL, "Informational", "gray50", "For your information only, no action expected"),
        ):
            assert any(item.get("text") == label for item in labels)
            assert any(item.get("text") == "■" and item.get("foreground") == color for item in labels)
            assert guidance in tooltips
        patched_widgets["label_frame"].assert_called_once_with(parent, text="Legend")
        patched_widgets["label_frame"].return_value.pack.assert_called_once_with(side="left", anchor="n", padx=(0, 20))
        assert len(created_frames) == len(Severity)
        assert all(frame.pack.call_args == call(anchor="w", padx=8, pady=2) for frame in created_frames)
        assert patched_widgets["show_tooltip"].call_count == 1 + 2 * len(Severity)
        for row_index, row in enumerate(created_frames):
            marker_call, label_call = patched_widgets["label"].call_args_list[2 * row_index : 2 * row_index + 2]
            assert marker_call.args[0] == row
            assert label_call.args[0] == row

    def test_report_details_include_component_issues_and_documentation_links(
        self, bare_window: LogAnalysisReportWindow
    ) -> None:
        """
        A subsystem report brings its hardware, availability issues, analysis, and help links together.

        GIVEN: A Battery subsystem with a component, one availability issue, and wiki and guide links
        WHEN: The user opens its detailed report
        THEN: Each detail appears in the appropriate report section
        """
        window = bare_window
        window.body_frame = MagicMock(winfo_children=MagicMock(return_value=[]))
        issue = _make_availability_issue(message="Voltage samples are sparse")
        availability = _make_availability_result(name="Battery", issues=[issue])
        analysis = _make_analysis_result(name="Battery analysis", reason="Cell balance is acceptable")
        window.pairs = [(availability, analysis)]
        window.report = {
            "vehicle_components": {
                "Battery": {"Product": {"Manufacturer": "GEN X POWER", "Model": "6S"}},
            }
        }
        window.summary.component_keys_for_subsystem.return_value = ["Battery"]
        window._report_availability_by_name = {
            "Battery": {
                "issues": [
                    {
                        "step_info": {
                            "wiki_url": "https://example.test/wiki",
                            "wiki_text": "Battery setup",
                            "blog_url": "https://example.test/guide",
                            "blog_text": "Battery guide",
                        }
                    }
                ]
            }
        }
        window._report_analysis_by_name = {"Battery": {"outcomes": []}}

        with (
            patch.object(window, "_section_heading") as heading,
            patch.object(window, "_section_body") as body,
            patch.object(window, "_section_link") as link,
            patch.object(window, "_bullet_line") as bullet,
        ):
            window._render_subsystem("Battery")

        assert heading.call_args_list == [
            call("Links"),
            call("Hardware & Connections"),
            call("Availability"),
            call("Analysis"),
        ]
        assert link.call_args_list == [
            call("Wiki", "Battery setup", "https://example.test/wiki"),
            call("Guide", "Battery guide", "https://example.test/guide"),
        ]
        body.assert_any_call("Battery", bold=True)
        body.assert_any_call("Cell balance is acceptable")
        assert bullet.call_args_list == [call("GEN X POWER 6S"), call("Voltage samples are sparse")]
