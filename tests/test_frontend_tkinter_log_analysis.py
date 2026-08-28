#!/usr/bin/env python3

"""
Tests for frontend_tkinter_log_analysis.py.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-FileCopyrightText: 2026 Omkar Sarkar <omkarsarkar24@gmail.com>

SPDX-License-Identifier: GPL-3.0-or-later
"""

from __future__ import annotations

import sys
from argparse import Namespace
from typing import TYPE_CHECKING, cast
from unittest.mock import MagicMock, patch

import pytest

from ardupilot_methodic_configurator.frontend_tkinter_log_analysis import (
    LogAnalysisReportWindow,
    _collect_links,
    _format_component,
    argument_parser,
    main,
)
from ardupilot_methodic_configurator.log_analysis.data_model_log_analysis import LogSummary

if TYPE_CHECKING:
    from pathlib import Path

    from pytest_mock import MockerFixture

    from ardupilot_methodic_configurator.log_analysis.data_model_log_analysis_result import LogAnalysisResult
    from ardupilot_methodic_configurator.log_analysis.data_model_log_availability import LogAvailabilityResult

MODULE = "ardupilot_methodic_configurator.frontend_tkinter_log_analysis"

# pylint: disable=protected-access, redefined-outer-name, use-implicit-booleaness-not-comparison


def _make_availability_issue(message: str = "issue", config_step: str | None = None) -> MagicMock:
    issue = MagicMock()
    issue.message = message
    issue.config_step = config_step
    return issue


def _make_availability_result(  # pylint: disable=too-many-arguments
    *,
    name: str = "Battery",
    available: bool = True,
    reason: str = "Battery data present and good for analysis",
    issues: list[MagicMock] | None = None,
    related_step: str = "",
    subsystem_key: str | None = "battery",
) -> MagicMock:
    result = MagicMock()
    result.name = name
    result.available = available
    result.reason = reason
    result.issues = issues or []
    result.related_step = related_step
    result.subsystem_key = subsystem_key
    return result


def _make_outcome(
    *,
    message: str = "finding",
    timestamp_us: float | None = None,
    param_name: str | None = None,
    suggested_value: float | None = None,
) -> MagicMock:
    outcome = MagicMock()
    outcome.message = message
    outcome.timestamp_us = timestamp_us
    outcome.param_name = param_name
    outcome.suggested_value = suggested_value
    return outcome


def _make_analysis_result(
    *,
    name: str = "Battery Analysis",
    available: bool = True,
    outcomes: list[MagicMock] | None = None,
    reason: str = "Battery analysis complete",
    subsystem_key: str | None = "battery",
) -> MagicMock:
    result = MagicMock()
    result.name = name
    result.available = available
    result.outcomes = outcomes if outcomes is not None else []
    result.reason = reason
    result.subsystem_key = subsystem_key
    return result


def _make_summary(availability_results: list[MagicMock], analysis_results: list[MagicMock]) -> LogSummary:
    return LogSummary(
        flight_duration_sec=None,
        file_size_bytes=0,
        total_messages=0,
        message_types=0,
        parameter_count=0,
        pm_status=None,
        pm_validation=None,
        availability_results=cast("list[LogAvailabilityResult]", availability_results),
        analysis_results=cast("list[LogAnalysisResult]", analysis_results),
        step_results=[],
        hardware_report=MagicMock(),
        analysis_subsystem_keys=tuple(result.subsystem_key for result in analysis_results if result.subsystem_key is not None)
        or ("battery",),
    )


class TestPairedAvailabilityAndAnalysisResults:
    """Cover stable-key pairing between availability and analysis results."""

    def test_pairs_available_availability_with_its_analysis_result(self) -> None:
        """
        Availability models with an analysis counterpart are paired when data is available.

        GIVEN: Battery has an analysis class and its availability check was available
        WHEN: Results are paired
        THEN: The availability result is paired with the corresponding analysis result
        """
        availability = _make_availability_result(name="Battery", available=True)
        analysis = _make_analysis_result(name="Battery Analysis")
        summary = _make_summary([availability], [analysis])

        pairs = summary.paired_availability_and_analysis_results()

        assert pairs == [(availability, analysis)]

    def test_pairs_unavailable_availability_with_none(self) -> None:
        """
        Availability models whose data was unavailable pair with None instead of an analysis result.

        GIVEN: Battery has an analysis class but the availability check reported unavailable
        WHEN: Results are paired
        THEN: The analysis side of the pair is None
        AND: No analysis result is consumed from the iterator
        """
        availability = _make_availability_result(name="ESC telemetry", available=False)
        summary = _make_summary([availability], [])

        pairs = summary.paired_availability_and_analysis_results()

        assert pairs == [(availability, None)]

    def test_skips_availability_models_with_no_analysis_class(self) -> None:
        """
        Subsystems with no analysis model (analysis_cls is None) are excluded entirely.

        GIVEN: GPS has no analysis class registered
        WHEN: Results are paired
        THEN: GPS does not appear in the paired output at all
        """
        availability = _make_availability_result(name="GPS", available=True, subsystem_key="gps")
        summary = _make_summary([availability], [])

        pairs = summary.paired_availability_and_analysis_results()

        assert not pairs

    def test_ignores_unregistered_prepended_availability_result(self) -> None:
        """
        A single extra availability result (e.g. System Performance) prepended by analyze_log().

        GIVEN: the extra result has no subsystem key
        WHEN: Results are paired
        THEN: the keyed Battery entry is paired, independently of list position
        """
        prepended = _make_availability_result(name="System Performance", available=True, subsystem_key=None)
        battery_availability = _make_availability_result(name="Battery", available=True)
        analysis = _make_analysis_result(name="Battery Analysis")
        summary = _make_summary([prepended, battery_availability], [analysis])

        pairs = summary.paired_availability_and_analysis_results()

        assert pairs == [(battery_availability, analysis)]

    def test_ignores_results_without_a_registered_subsystem_key(self) -> None:
        """
        Unknown or legacy result entries do not affect keyed pairing.

        GIVEN: availability results have no registered subsystem keys
        WHEN: Results are paired
        THEN: no positional pairing is attempted
        """
        summary = _make_summary(
            [
                _make_availability_result(subsystem_key=None),
                _make_availability_result(subsystem_key=None),
                _make_availability_result(subsystem_key=None),
            ],
            [],
        )

        assert summary.paired_availability_and_analysis_results() == []


class TestCollectLinks:
    """Cover step_info link de-duplication across availability issues and analysis outcomes."""

    def test_collects_link_from_availability_issue_step_info(self) -> None:
        """
        A availability issue's step_info with a wiki_url is included in the collected links.

        GIVEN: One availability issue carries step_info with a wiki_url
        WHEN: Links are collected
        THEN: That step_info dict is present in the returned list
        """
        step_info = {"wiki_url": "https://ardupilot.org/wiki", "wiki_text": "Wiki"}
        availability_dict = {"issues": [{"step_info": step_info}]}

        links = _collect_links(availability_dict, None)

        assert links == [step_info]

    def test_collects_link_from_analysis_outcome_step_info(self) -> None:
        """
        An analysis outcome's step_info with a blog_url is included in the collected links.

        GIVEN: One analysis outcome carries step_info with a blog_url
        WHEN: Links are collected
        THEN: That step_info dict is present in the returned list
        """
        step_info = {"blog_url": "https://example.com/guide", "blog_text": "Guide"}
        analysis_dict = {"outcomes": [{"step_info": step_info}]}

        links = _collect_links(None, analysis_dict)

        assert links == [step_info]

    def test_deduplicates_identical_links_across_multiple_findings(self) -> None:
        """
        The same (wiki_url, blog_url) pair appearing on multiple findings is only listed once.

        GIVEN: Two availability issues reference the same step_info wiki_url and blog_url
        WHEN: Links are collected
        THEN: Only one entry appears in the result
        """
        step_info = {"wiki_url": "https://ardupilot.org/wiki", "blog_url": None}
        availability_dict = {"issues": [{"step_info": step_info}, {"step_info": dict(step_info)}]}

        links = _collect_links(availability_dict, None)

        assert len(links) == 1

    def test_ignores_step_info_with_no_urls_at_all(self) -> None:
        """
        A step_info dict with neither wiki_url nor blog_url set is not treated as a real link.

        GIVEN: step_info exists but both wiki_url and blog_url are None
        WHEN: Links are collected
        THEN: No links are returned
        """
        availability_dict = {"issues": [{"step_info": {"wiki_url": None, "blog_url": None}}]}

        links = _collect_links(availability_dict, None)

        assert links == []

    def test_returns_empty_list_when_no_availability_or_analysis_dicts_given(self) -> None:
        """
        Missing availability/analysis dicts (e.g. pending subsystem) produce no links, not an error.

        GIVEN: Both availability_dict and analysis_dict are None
        WHEN: Links are collected
        THEN: An empty list is returned
        """
        links = _collect_links(None, None)

        assert links == []

    def test_ignores_issues_or_outcomes_missing_step_info_key(self) -> None:
        """
        Findings that never had step_info attached (e.g. no related_step) are skipped safely.

        GIVEN: An issue dict with no "step_info" key at all
        WHEN: Links are collected
        THEN: No exception is raised and no link is added
        """
        availability_dict = {"issues": [{"message": "no step info here"}]}

        links = _collect_links(availability_dict, None)

        assert links == []


class TestFormatComponent:
    """Cover the vehicle_components -> readable-lines formatter."""

    def test_formats_manufacturer_and_model_as_one_line(self) -> None:
        """
        Product manufacturer and model are joined into a single readable line.

        GIVEN: A component with Product.Manufacturer and Product.Model set
        WHEN: The component is formatted
        THEN: One line combines both, space-separated
        """
        component = {"Product": {"Manufacturer": "GEN X POWER", "Model": "6S"}}

        lines = _format_component(component)

        assert "GEN X POWER 6S" in lines

    def test_skips_empty_manufacturer_and_model(self) -> None:
        """
        An empty Product block produces no name line.

        GIVEN: Product.Manufacturer and Product.Model are both empty strings
        WHEN: The component is formatted
        THEN: No blank or whitespace-only line is added
        """
        component = {"Product": {"Manufacturer": "", "Model": ""}}

        lines = _format_component(component)

        assert lines == []

    def test_formats_firmware_type_and_version(self) -> None:
        """
        Firmware type and version are combined into a single "Firmware: ..." line.

        GIVEN: A component with Firmware.Type and Firmware.Version set
        WHEN: The component is formatted
        THEN: A line starting with "Firmware:" contains both values
        """
        component = {"Firmware": {"Type": "AM32", "Version": "F421"}}

        lines = _format_component(component)

        assert any(line.startswith("Firmware:") and "AM32" in line and "F421" in line for line in lines)

    def test_formats_connection_fields_by_key_name(self) -> None:
        """
        Any dict key containing "Connection" is formatted as "<key>: <Type> / <Protocol>".

        GIVEN: A component with an "FC->ESC Connection" dict containing Type and Protocol
        WHEN: The component is formatted
        THEN: A line named after that exact key includes both values
        """
        component = {"FC->ESC Connection": {"Type": "Analog", "Protocol": "Analog Voltage and Current"}}

        lines = _format_component(component)

        assert any(line.startswith("FC->ESC Connection:") for line in lines)
        assert any("Analog" in line for line in lines)

    def test_formats_notes_when_present(self) -> None:
        """
        A non-empty Notes field produces a "Notes: ..." line.

        GIVEN: A component with Notes set to a non-empty string
        WHEN: The component is formatted
        THEN: A line starting with "Notes:" contains that text
        """
        component = {"Notes": "Built into ESC"}

        lines = _format_component(component)

        assert any(line.startswith("Notes:") and "Built into ESC" in line for line in lines)

    def test_returns_empty_list_for_completely_empty_component(self) -> None:
        """
        A component dict with no recognizable fields produces no lines at all.

        GIVEN: An empty component dict
        WHEN: The component is formatted
        THEN: The result is an empty list
        """
        assert _format_component({}) == []

    def test_ignores_non_dict_connection_like_values(self) -> None:
        """
        A key containing "Connection" whose value is not a dict is skipped safely.

        GIVEN: A component where "FC Connection" maps to a plain string, not a dict
        WHEN: The component is formatted
        THEN: No exception is raised and no line is produced for that key
        """
        component = {"FC Connection": "not-a-dict"}

        lines = _format_component(component)

        assert lines == []


@pytest.fixture
def patched_widgets(mocker: MockerFixture) -> dict[str, MagicMock]:
    """Patch every Tkinter widget class LogAnalysisReportWindow touches during construction."""
    patches = {
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
    return patches  # noqa: RET504


@pytest.fixture
def bare_window() -> LogAnalysisReportWindow:
    """Build an uninitialized window instance, bypassing the real BaseWindow.__init__."""
    window = LogAnalysisReportWindow.__new__(LogAnalysisReportWindow)
    window.root = MagicMock()
    window.main_frame = MagicMock()
    window.summary = MagicMock(related_parameter_values={})
    return window


class TestWindowConstruction:
    """Cover LogAnalysisReportWindow's full __init__ flow with widgets mocked."""

    def _build_window(  # pylint: disable=too-many-arguments
        self,
        mocker: MockerFixture,
        patched_widgets: dict[str, MagicMock],
        availability_results: list[MagicMock],
        analysis_results: list[MagicMock],
        *,
        report: dict | None = None,
        vehicle_dir: str = "/vehicle",
    ) -> LogAnalysisReportWindow:
        _ = patched_widgets  # Keep the widget patches active while constructing the window.
        mocker.patch.object(LogAnalysisReportWindow, "calculate_scaled_geometry", return_value="1050x800")
        mocker.patch.object(LogAnalysisReportWindow, "center_window")
        summary = _make_summary(availability_results, analysis_results)

        root = MagicMock()

        def _fake_base_init(self: LogAnalysisReportWindow, root_tk: object) -> None:
            self.root = root_tk
            self.main_frame = MagicMock()

        mocker.patch(f"{MODULE}.BaseWindow.__init__", _fake_base_init)
        return LogAnalysisReportWindow(root, summary, vehicle_dir, report=report)

    def test_selector_defaults_to_first_subsystem(self, mocker: MockerFixture, patched_widgets: dict[str, MagicMock]) -> None:
        """
        The subsystem selector is preset to the first available subsystem on open.

        GIVEN: Two availability/analysis pairs are present, Battery first
        WHEN: The window is constructed
        THEN: The selector's set() is called with the first subsystem's name
        """
        availability_battery = _make_availability_result(name="Battery", subsystem_key="battery")
        availability_imu = _make_availability_result(name="IMU", subsystem_key="imu")
        analysis_battery = _make_analysis_result(name="Battery Analysis", subsystem_key="battery")
        analysis_imu = _make_analysis_result(name="IMU Analysis", subsystem_key="imu")

        window = self._build_window(
            mocker, patched_widgets, [availability_battery, availability_imu], [analysis_battery, analysis_imu]
        )

        cast("MagicMock", window.selector.set).assert_called_once_with("Battery")

    def test_no_selector_default_when_no_subsystems_present(
        self, mocker: MockerFixture, patched_widgets: dict[str, MagicMock]
    ) -> None:
        """
        An empty pairing list does not attempt to set a selector value.

        GIVEN: No availability/analysis pairs exist (empty registry)
        WHEN: The window is constructed
        THEN: The selector's set() is never called
        """
        window = self._build_window(mocker, patched_widgets, [], [])

        cast("MagicMock", window.selector.set).assert_not_called()

class TestTuningGraphButton:
    """Cover the footer's Tuning Parameter Graph button state and click handler."""

    def test_button_enabled_when_tuning_report_exists(self, patched_widgets: dict[str, MagicMock], tmp_path: Path) -> None:
        """
        The tuning graph button is enabled when tuning_report.csv exists in the vehicle directory.

        GIVEN: tuning_report.csv exists at the vehicle directory
        WHEN: The footer is built
        THEN: The button is configured with state="normal"
        """
        (tmp_path / "tuning_report.csv").write_text("param,00_default.param\n", encoding="utf-8")
        window = LogAnalysisReportWindow.__new__(LogAnalysisReportWindow)
        window.main_frame = MagicMock()
        window.vehicle_dir = str(tmp_path)
        window.report = None

        window._build_footer()

        button_mock = patched_widgets["button"].return_value
        button_mock.configure.assert_any_call(state="normal")

    def test_button_disabled_when_tuning_report_missing(self, patched_widgets: dict[str, MagicMock], tmp_path: Path) -> None:
        """
        The tuning graph button is disabled when tuning_report.csv is absent.

        GIVEN: No tuning_report.csv exists at the vehicle directory
        WHEN: The footer is built
        THEN: The button is configured with state="disabled"
        """
        window = LogAnalysisReportWindow.__new__(LogAnalysisReportWindow)
        window.main_frame = MagicMock()
        window.vehicle_dir = str(tmp_path)
        window.report = None

        window._build_footer()

        button_mock = patched_widgets["button"].return_value
        button_mock.configure.assert_any_call(state="disabled")

    def test_open_tuning_graph_shows_error_on_bad_csv(self, bare_window: LogAnalysisReportWindow, tmp_path: Path) -> None:
        """
        A malformed tuning_report.csv surfaces a user-facing error dialog, not a crash.

        GIVEN: TuningReportWindow raises ValueError when opening the report
        WHEN: The user clicks the tuning graph button
        THEN: An error messagebox is shown and no exception propagates
        """
        bare_window.vehicle_dir = str(tmp_path)
        (tmp_path / "tuning_report.csv").write_text("bad data", encoding="utf-8")

        with (
            patch(f"{MODULE}.TuningReportWindow", side_effect=ValueError("bad csv")),
            patch(f"{MODULE}.messagebox.showerror") as mock_error,
        ):
            bare_window._on_open_tuning_graph()

        mock_error.assert_called_once()


class TestRenderSubsystem:
    """Cover _render_subsystem's section building for a selected subsystem."""

    def _window_for_render(self, bare_window: LogAnalysisReportWindow) -> LogAnalysisReportWindow:
        bare_window.body_frame = MagicMock(winfo_children=MagicMock(return_value=[]))
        return bare_window

    def test_shows_pending_message_for_unpaired_analysis(self, bare_window: LogAnalysisReportWindow) -> None:
        """
        A subsystem with no analysis result (pending) shows its availability reason as the analysis text.

        GIVEN: A subsystem paired with None (availability gate not yet passed)
        WHEN: That subsystem is rendered
        THEN: The Analysis section body includes the availability result's reason
        """
        window = self._window_for_render(bare_window)
        availability = _make_availability_result(name="ESC telemetry", reason="ESC telemetry not logged")
        window.pairs = [(availability, None)]
        window.report = None
        window._report_availability_by_name = {}
        window._report_analysis_by_name = {}

        with (
            patch.object(window, "_section_heading") as mock_heading,
            patch.object(window, "_section_body") as mock_body,
        ):
            window._render_subsystem("ESC telemetry")

        mock_heading.assert_any_call("Analysis")
        assert any("ESC telemetry not logged" in call.args[0] for call in mock_body.call_args_list)

    def test_shows_no_findings_message_for_clean_subsystem(self, bare_window: LogAnalysisReportWindow) -> None:
        """
        A completed analysis with zero outcomes shows a "No findings." message.

        GIVEN: An analysis result with an empty outcomes list
        WHEN: That subsystem is rendered
        THEN: The Analysis section body includes "No findings."
        """
        window = self._window_for_render(bare_window)
        availability = _make_availability_result(name="VIBE", reason="VIBE data present and good for analysis")
        analysis = _make_analysis_result(name="Vibration Analysis", outcomes=[])
        window.pairs = [(availability, analysis)]
        window.report = None
        window._report_availability_by_name = {}
        window._report_analysis_by_name = {}

        with (
            patch.object(window, "_section_heading"),
            patch.object(window, "_section_body") as mock_body,
        ):
            window._render_subsystem("VIBE")

        assert any("No findings." in call.args[0] for call in mock_body.call_args_list)

    def test_renders_each_outcome_as_an_outcome_line(self, bare_window: LogAnalysisReportWindow) -> None:
        """
        Every outcome in a completed analysis is rendered via _outcome_line.

        GIVEN: An analysis result with two outcomes
        WHEN: That subsystem is rendered
        THEN: _outcome_line is called once per outcome
        """
        window = self._window_for_render(bare_window)
        outcomes = [_make_outcome(message="first"), _make_outcome(message="second")]
        availability = _make_availability_result(name="Battery")
        analysis = _make_analysis_result(name="Battery Analysis", outcomes=outcomes)
        window.pairs = [(availability, analysis)]
        window.report = None
        window._report_availability_by_name = {}
        window._report_analysis_by_name = {}

        with (
            patch.object(window, "_section_heading"),
            patch.object(window, "_section_body"),
            patch.object(window, "_outcome_line") as mock_outcome_line,
        ):
            window._render_subsystem("Battery")

        assert mock_outcome_line.call_count == 2
        mock_outcome_line.assert_any_call(outcomes[0])
        mock_outcome_line.assert_any_call(outcomes[1])

    def test_actionable_outcome_exposes_a_parameter_fix(self, bare_window: LogAnalysisReportWindow) -> None:
        """Analysis recommendations should use the same parameter-fix workflow as availability issues."""
        outcome = _make_outcome(param_name="MOT_SPIN_MIN", suggested_value=0.15)
        bare_window.summary.related_parameter_values = {"MOT_SPIN_MIN": 0.1}

        fixes = bare_window._fix_for_outcome(outcome)

        assert fixes == [("MOT_SPIN_MIN", 0.1, 0.15, ["finding"])]

    @pytest.mark.parametrize("upload_result", [None, True])
    def test_analysis_fix_accepts_non_false_upload_result(
        self, bare_window: LogAnalysisReportWindow, upload_result: bool | None
    ) -> None:
        """
        Treat callbacks without an explicit failure result as successful.

        GIVEN a parameter-fix callback returning None or True,
        WHEN the analysis report applies a fix,
        THEN the displayed parameter state is updated and the dialog closes.
        """
        # Arrange: provide a side-effect callback and a pending parameter fix.
        bare_window.upload_callback = MagicMock(return_value=upload_result)
        fixes = [("MOT_SPIN_MIN", 0.1, 0.15, ["finding"])]
        dialog = MagicMock()

        # Act: apply the proposed change.
        bare_window._apply_param_fixes(fixes, dialog)

        # Assert: None is not mistaken for an upload failure.
        assert bare_window.summary.related_parameter_values == {"MOT_SPIN_MIN": 0.15}
        dialog.destroy.assert_called_once()

    def test_renders_no_hardware_section_when_no_component_data(self, bare_window: LogAnalysisReportWindow) -> None:
        """
        Subsystems with no matching vehicle_components entries do not show a Hardware section.

        GIVEN: The report's vehicle_components has no data for the selected subsystem
        WHEN: That subsystem is rendered
        THEN: "Hardware & Connections" is never passed to _section_heading
        """
        window = self._window_for_render(bare_window)
        availability = _make_availability_result(name="ARM")
        analysis = _make_analysis_result(name="ARM Analysis", outcomes=[])
        window.pairs = [(availability, analysis)]
        window.report = {"vehicle_components": {}}
        window._report_availability_by_name = {}
        window._report_analysis_by_name = {}

        with (
            patch.object(window, "_section_heading") as mock_heading,
            patch.object(window, "_section_body"),
        ):
            window._render_subsystem("ARM")

        headings = [call.args[0] for call in mock_heading.call_args_list]
        assert "Hardware & Connections" not in headings

    def test_returns_early_when_subsystem_name_not_found(self, bare_window: LogAnalysisReportWindow) -> None:
        """
        Selecting a name absent from self.pairs does nothing rather than raising.

        GIVEN: No pair matches the requested subsystem name
        WHEN: _render_subsystem is called with that name
        THEN: No section headings or bodies are rendered
        """
        window = self._window_for_render(bare_window)
        window.pairs = []

        with (
            patch.object(window, "_section_heading") as mock_heading,
            patch.object(window, "_section_body") as mock_body,
        ):
            window._render_subsystem("Nonexistent")

        mock_heading.assert_not_called()
        mock_body.assert_not_called()


class TestStandaloneLogAnalysis:
    """Tests for the standalone log-analysis entry point."""

    def test_argument_parser_accepts_an_omitted_logfile(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """
        Users can launch the standalone report without a command-line log path.

        GIVEN: The standalone command is launched without positional arguments
        WHEN: Its arguments are parsed
        THEN: The log-file argument is left unset so the file chooser can be displayed
        """
        # Arrange (Given): Simulate launching without a log path.
        monkeypatch.setattr(sys, "argv", ["frontend_tkinter_log_analysis.py"])

        # Act (When): Parse the command-line arguments.
        args = argument_parser()

        # Assert (Then): The main entry point can request the log interactively.
        assert args.logfile is None

    def test_main_returns_when_logfile_selection_is_cancelled(self, mocker: MockerFixture) -> None:
        """
        Users can cancel the interactive log-file selection without opening a report.

        GIVEN: The standalone report has no command-line log path
        WHEN: The user cancels the file chooser
        THEN: The temporary selector closes and no vehicle project is loaded
        """
        # Arrange (Given): Provide the minimum arguments and a cancelled selection.
        mocker.patch(f"{MODULE}.argument_parser", return_value=Namespace(logfile=None, loglevel="INFO"))
        selector_root = mocker.patch(f"{MODULE}.tk.Tk").return_value
        file_selector = mocker.patch(f"{MODULE}.filedialog.askopenfilename", return_value="")
        local_filesystem = mocker.patch(f"{MODULE}.LocalFilesystem")

        # Act (When): Start the standalone report.
        main()

        # Assert (Then): Clean up the chooser and skip all analysis work.
        selector_root.withdraw.assert_called_once()
        file_selector.assert_called_once()
        selector_root.destroy.assert_called_once()
        local_filesystem.assert_not_called()

    def test_main_analyses_selected_log_and_opens_report(self, mocker: MockerFixture, tmp_path: Path) -> None:
        """
        Users can select a log interactively and open its detailed report.

        GIVEN: The standalone report has no command-line log path and a vehicle project is available
        WHEN: The user selects an ArduPilot binary log
        THEN: The log is analysed with that project's metadata and the report opens
        """
        # Arrange (Given): Provide a selected log and representative vehicle metadata.
        args = Namespace(
            logfile=None,
            loglevel="INFO",
            vehicle_dir=str(tmp_path / "vehicle"),
            vehicle_type="ArduCopter",
            allow_editing_template_files=False,
            save_component_to_system_templates=False,
        )
        mocker.patch(f"{MODULE}.argument_parser", return_value=args)
        selector_root = mocker.patch(f"{MODULE}.tk.Tk").return_value
        mocker.patch(f"{MODULE}.filedialog.askopenfilename", return_value=str(tmp_path / "flight.bin"))
        filesystem = mocker.patch(f"{MODULE}.LocalFilesystem").return_value
        filesystem.vehicle_dir = args.vehicle_dir
        filesystem.vehicle_type = args.vehicle_type
        filesystem.fw_version = "4.6.0"
        filesystem.vehicle_components_fs.data = {"Components": {"Battery": {}}}
        filesystem.configuration_steps = {"01_step.param": {}}
        filesystem.doc_dict = {}
        log_data = mocker.patch(f"{MODULE}.extract_log").return_value
        summary = MagicMock()
        analyze_log_data = mocker.patch(f"{MODULE}.analyze_log_data", return_value=summary)
        report_window_class = mocker.patch(f"{MODULE}.LogAnalysisReportWindow")
        report_window = report_window_class.return_value

        # Act (When): Start the standalone report.
        main()

        # Assert (Then): Analyse the selected log and show its detailed report.
        analyze_log_data.assert_called_once_with(
            log_data,
            project_vehicle_type="ArduCopter",
            project_firmware_version="4.6.0",
            vehicle_components={"Battery": {}},
            configuration_steps={"01_step.param": {}},
            apm_doc=None,
            validate_project=False,
        )
        report_window_class.assert_called_once_with(None, summary, args.vehicle_dir)
        report_window.run.assert_called_once()
        selector_root.destroy.assert_called_once()
