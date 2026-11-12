#!/usr/bin/env python3

"""
Tests for log analysis Tkinter view helpers.

SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

from types import SimpleNamespace
from unittest.mock import MagicMock, call, patch

from ardupilot_methodic_configurator.frontend_tkinter_base_window import BaseWindow
from ardupilot_methodic_configurator.frontend_tkinter_log_availability import LogAvailabilityReportWindow
from ardupilot_methodic_configurator.frontend_tkinter_log_hardware_availability import build_hardware_tab
from ardupilot_methodic_configurator.log_analysis.data_model_log_availability import LogAvailabilityState
from ardupilot_methodic_configurator.log_analysis.data_model_vehicle_overview import HardwareReport, VehicleInfo

# pylint: disable=too-many-lines


def test_hardware_tab_shows_empty_state_when_report_has_no_sensors() -> None:
    """A hardware report with no sensor entries should still show explicit user feedback."""
    parent = MagicMock()
    inner = MagicMock()
    scroll_frame = MagicMock(view_port=inner)
    label = MagicMock()
    hw = HardwareReport(
        vehicle=VehicleInfo(
            vehicle_type="ArduCopter",
            major=4,
            minor=5,
            patch=5,
            firmware_hash=None,
            board_id=None,
            flight_controller=None,
            oper_sys=None,
        ),
        board_name=None,
        imus=[],
        compasses=[],
        baros=[],
        airspeed_sensors=[],
    )

    with (
        patch(
            "ardupilot_methodic_configurator.frontend_tkinter_log_hardware_availability.ScrollFrame", return_value=scroll_frame
        ),
        patch(
            "ardupilot_methodic_configurator.frontend_tkinter_log_hardware_availability.ttk.Label",
            return_value=label,
        ) as mock_label,
    ):
        build_hardware_tab(parent, hw)

    mock_label.assert_called_once_with(inner, text="No hardware data available", foreground="gray")
    label.pack.assert_called_once_with(padx=24, pady=24)


def test_release_link_opens_with_backend_internet_browser_helper() -> None:
    """Clickable report links should reuse the application's browser helper."""
    report_window = LogAvailabilityReportWindow.__new__(LogAvailabilityReportWindow)
    report_window.default_font_size = 11
    parent = MagicMock()
    row = MagicMock()
    key_label = MagicMock()
    link_label = MagicMock()

    with (
        patch("ardupilot_methodic_configurator.frontend_tkinter_log_availability.ttk.Frame", return_value=row) as make_frame,
        patch(
            "ardupilot_methodic_configurator.frontend_tkinter_log_availability.ttk.Label",
            side_effect=[key_label, link_label],
        ) as make_label,
        patch("ardupilot_methodic_configurator.frontend_tkinter_log_availability.show_tooltip") as show_tooltip,
        patch("ardupilot_methodic_configurator.frontend_tkinter_log_availability.webbrowser_open_url") as mock_open,
    ):
        report_window._add_clickable_key_value(parent, "Firmware:", "Copter-4.5.5", "https://example.test/release")  # pylint: disable=protected-access

        callback = link_label.bind.call_args.args[1]
        callback(None)

    make_frame.assert_called_once_with(parent)
    row.pack.assert_called_once_with(fill="x", padx=10, pady=3)
    assert make_label.call_args_list == [
        call(row, text="Firmware:", foreground="gray", font=("TkDefaultFont", 11), width=14),
        call(
            row,
            text="Copter-4.5.5",
            foreground="blue",
            cursor="hand2",
            font=("TkDefaultFont", 11, "underline"),
        ),
    ]
    key_label.pack.assert_called_once_with(side="left")
    link_label.pack.assert_called_once_with(side="left", fill="x", expand=True)
    assert link_label.bind.call_args.args[0] == "<Button-1>"
    show_tooltip.assert_called_once_with(link_label, "Open release page on GitHub")
    mock_open.assert_called_once_with("https://example.test/release")


def test_availability_tab_groups_attention_and_passed_checks() -> None:  # pylint: disable=too-many-locals
    """
    Group report findings by their status and associate absorbed configuration steps.

    GIVEN a report with available, unavailable, and step validation results,
    WHEN the availability tab is built,
    THEN attention items and passed checks are shown in their matching groups.
    """
    window = LogAvailabilityReportWindow.__new__(LogAvailabilityReportWindow)
    attention = SimpleNamespace(state=LogAvailabilityState.WARNING, related_step="calibration")
    unmatched_attention = SimpleNamespace(state=LogAvailabilityState.WARNING, related_step="unmatched-step")
    passed = SimpleNamespace(state=LogAvailabilityState.INFO, related_step="calibration")
    absorbed_step = SimpleNamespace(step="calibration", valid=False)
    standalone_attention_step = SimpleNamespace(step="parameter-check", valid=False)
    standalone_step = SimpleNamespace(step="sensor-check", valid=True)
    window.summary = SimpleNamespace(
        availability_results=[attention, unmatched_attention, passed],
        step_results=[absorbed_step, standalone_attention_step, standalone_step],
    )
    parent = MagicMock()
    scroll_frame = MagicMock()
    events: list[tuple[object, ...]] = []
    current_section: list[str] = []
    heading_labels: list[MagicMock] = []
    separator_widget = MagicMock()

    def record_availability(_parent: object, result: SimpleNamespace, absorbed: list[SimpleNamespace]) -> None:
        """Record the section used for each availability card."""
        events.append(("availability", current_section[0], result.state, tuple(step.step for step in absorbed)))

    def record_step(_parent: object, result: SimpleNamespace) -> None:
        """Record the section used for each step card."""
        events.append(("step", current_section[0], result.step))

    def make_heading(_parent: object, *, text: str, **_kwargs: object) -> MagicMock:
        """Track section headings while returning a stand-in label."""
        current_section[:] = [text]
        events.append(("section", text))
        label = MagicMock()
        heading_labels.append(label)
        return label

    def make_separator(_parent: object, **_kwargs: object) -> MagicMock:
        """Track the separator between attention and passed results."""
        events.append(("separator", current_section[0]))
        return separator_widget

    availability_result_card = MagicMock(side_effect=record_availability)
    step_result_card = MagicMock(side_effect=record_step)
    window._availability_result_card = availability_result_card  # pylint: disable=protected-access
    window._step_result_card = step_result_card  # pylint: disable=protected-access

    with (
        patch(
            "ardupilot_methodic_configurator.frontend_tkinter_log_availability.ScrollFrame", return_value=scroll_frame
        ) as make_scroll,
        patch(
            "ardupilot_methodic_configurator.frontend_tkinter_log_availability.ttk.Label", side_effect=make_heading
        ) as make_label,
        patch(
            "ardupilot_methodic_configurator.frontend_tkinter_log_availability.ttk.Separator", side_effect=make_separator
        ) as make_separator,
    ):
        window._build_availability_tab(parent)  # pylint: disable=protected-access

    make_scroll.assert_called_once_with(parent)
    scroll_frame.pack.assert_called_once_with(fill="both", expand=True)
    assert make_label.call_args_list == [
        call(
            scroll_frame.view_port,
            text="Requires Attention",
            font=("TkDefaultFont", 14, "bold"),
            foreground="darkorange",
        ),
        call(scroll_frame.view_port, text="Passed Checks", font=("TkDefaultFont", 14, "bold"), foreground="darkgreen"),
    ]
    assert [label.pack.call_args for label in heading_labels] == [
        call(anchor="w", padx=14, pady=(18, 6)),
        call(anchor="w", padx=14, pady=(10, 6)),
    ]
    make_separator.assert_called_once_with(scroll_frame.view_port, orient="horizontal")
    separator_widget.pack.assert_called_once_with(fill="x", padx=14, pady=(14, 14))
    assert events == [
        ("section", "Requires Attention"),
        ("availability", "Requires Attention", LogAvailabilityState.WARNING, ("calibration",)),
        ("availability", "Requires Attention", LogAvailabilityState.WARNING, ()),
        ("step", "Requires Attention", "parameter-check"),
        ("separator", "Requires Attention"),
        ("section", "Passed Checks"),
        ("availability", "Passed Checks", LogAvailabilityState.INFO, ("calibration",)),
        ("step", "Passed Checks", "sensor-check"),
    ]
    assert availability_result_card.call_count == 3
    assert step_result_card.call_args_list == [
        call(scroll_frame.view_port, standalone_attention_step),
        call(scroll_frame.view_port, standalone_step),
    ]


def test_parameter_fixes_merge_log_bitmask_and_keep_first_other_suggestion() -> None:
    """
    Combine compatible automatic fixes while preserving parameter-specific behavior.

    GIVEN issues with repeated LOG_BITMASK and ordinary parameter suggestions,
    WHEN proposed fixes are calculated,
    THEN bitmask values are merged and ordinary parameters use their first suggestion.
    """
    window = LogAvailabilityReportWindow.__new__(LogAvailabilityReportWindow)
    window.summary = SimpleNamespace(
        related_parameter_values={"LOG_BITMASK": 2, "MOT_SPIN_MIN": 0.1, "UNCHANGED": 3, "NEXT": 1.0}
    )
    issues = [
        SimpleNamespace(param_name="LOG_BITMASK", suggested_value=1, message="bit one"),
        SimpleNamespace(param_name="LOG_BITMASK", suggested_value=4, message="bit three"),
        SimpleNamespace(param_name="MOT_SPIN_MIN", suggested_value=0.15, message="first suggestion"),
        SimpleNamespace(param_name="MOT_SPIN_MIN", suggested_value=0.2, message="later suggestion"),
        SimpleNamespace(param_name="UNCHANGED", suggested_value=3, message="already set"),
        SimpleNamespace(param_name="MISSING", suggested_value=1, message="parameter unavailable"),
        SimpleNamespace(param_name="NEXT", suggested_value=2.0, message="later parameter still available"),
        SimpleNamespace(param_name="MOT_SPIN_MIN", suggested_value=None, message="no proposal"),
    ]

    fixes = window._fixes_for_issues(issues)  # pylint: disable=protected-access

    assert fixes == [
        ("LOG_BITMASK", 2, 7.0, ["bit one", "bit three"]),
        ("MOT_SPIN_MIN", 0.1, 0.15, ["first suggestion", "later suggestion"]),
        ("NEXT", 1.0, 2.0, ["later parameter still available"]),
    ]


def test_navigation_restores_parent_window_after_selecting_a_step() -> None:
    """
    Return users to the configurator when they follow a report step link.

    GIVEN a report opened above a hidden parent window,
    WHEN the user chooses a configuration step,
    THEN the callback runs and the parent window becomes visible and focused.
    """
    window = LogAvailabilityReportWindow.__new__(LogAvailabilityReportWindow)
    window.navigate_callback = MagicMock()
    parent_root = MagicMock()
    window._parent_root = parent_root  # pylint: disable=protected-access

    window._navigate_to_step("Compass Calibration")  # pylint: disable=protected-access

    window.navigate_callback.assert_called_once_with("Compass Calibration")
    parent_root.deiconify.assert_called_once_with()
    parent_root.lift.assert_called_once_with()
    parent_root.focus_force.assert_called_once_with()


def test_availability_fix_keeps_dialog_open_when_upload_fails() -> None:
    """
    Keep proposed values pending when the flight controller rejects an upload.

    GIVEN an upload callback that reports failure,
    WHEN the user applies a proposed parameter fix,
    THEN the displayed parameter value stays unchanged and the review remains open.
    """
    window = LogAvailabilityReportWindow.__new__(LogAvailabilityReportWindow)
    window.summary = SimpleNamespace(related_parameter_values={"MOT_SPIN_MIN": 0.1})
    window.upload_callback = MagicMock(return_value=False)
    dialog = MagicMock()

    window._apply_param_fixes([("MOT_SPIN_MIN", 0.1, 0.15, ["finding"])], dialog)  # pylint: disable=protected-access

    window.upload_callback.assert_called_once()
    changes = window.upload_callback.call_args.args[0]
    assert changes["MOT_SPIN_MIN"].value == 0.15
    assert changes["MOT_SPIN_MIN"].comment == ""
    assert window.summary.related_parameter_values == {"MOT_SPIN_MIN": 0.1}
    dialog.destroy.assert_not_called()


def test_step_card_shows_validation_issues_and_returns_to_the_configurator() -> None:
    """
    Let users understand a failed configuration step and jump directly to it.

    GIVEN a step validation result with an issue,
    WHEN its report card is displayed and the user selects Go to Step,
    THEN the issue is shown as a tooltip and the configurator navigates to that step.
    """
    window = LogAvailabilityReportWindow.__new__(LogAvailabilityReportWindow)
    window.navigate_callback = MagicMock()
    parent_root = MagicMock()
    window._parent_root = parent_root  # pylint: disable=protected-access
    parent = MagicMock()
    card = MagicMock()
    label = MagicMock()
    button = MagicMock()
    result = SimpleNamespace(
        step="08-compass-calibration",
        name="Compass Calibration",
        valid=False,
        message_results={
            "COMPASS": SimpleNamespace(issues=["Compass orientation is missing", "Compass calibration is incomplete"])
        },
    )

    with (
        patch("ardupilot_methodic_configurator.frontend_tkinter_log_availability.ttk.Frame", return_value=card) as make_frame,
        patch("ardupilot_methodic_configurator.frontend_tkinter_log_availability.ttk.Label", return_value=label) as make_label,
        patch(
            "ardupilot_methodic_configurator.frontend_tkinter_log_availability.ttk.Button", return_value=button
        ) as mock_button,
        patch(
            "ardupilot_methodic_configurator.frontend_tkinter_log_availability.step_display_name",
            return_value="Compass Calibration",
        ),
        patch("ardupilot_methodic_configurator.frontend_tkinter_log_availability.show_tooltip") as mock_tooltip,
    ):
        window._step_result_card(parent, result)  # pylint: disable=protected-access

    make_frame.assert_called_once_with(parent)
    card.pack.assert_called_once_with(fill="x", padx=14, pady=6)
    make_label.assert_called_once_with(card, text="Compass Calibration", font=("TkDefaultFont", 12), wraplength=500)
    label.pack.assert_called_once_with(side="left", anchor="w", fill="x", expand=True)
    assert mock_button.call_args.args == (card,)
    assert mock_button.call_args.kwargs["text"] == "Go to Step"
    button.pack.assert_called_once_with(side="right", padx=(0, 8))
    resize_callback = card.bind.call_args.args[1]
    assert card.bind.call_args.args[0] == "<Configure>"
    LogAvailabilityReportWindow._set_step_wraplength(label, None)  # pylint: disable=protected-access
    resize_callback(SimpleNamespace(width=200))
    assert label.configure.call_args_list == [call(wraplength=10), call(wraplength=110)]
    mock_tooltip.assert_any_call(label, "Compass Calibration")
    issues_tooltip = "- Compass orientation is missing\n- Compass calibration is incomplete"
    mock_tooltip.assert_any_call(label, issues_tooltip)
    mock_tooltip.assert_any_call(card, issues_tooltip)
    mock_button.call_args.kwargs["command"]()
    window.navigate_callback.assert_called_once_with("08-compass-calibration")
    parent_root.deiconify.assert_called_once_with()


def test_availability_card_offers_fix_and_step_navigation_actions() -> None:
    """
    Offer relevant actions beside an availability finding.

    GIVEN an availability result with a parameter fix and a related configuration step,
    WHEN the result card is rendered,
    THEN users can review the fix and jump to the related step.
    """
    window = LogAvailabilityReportWindow.__new__(LogAvailabilityReportWindow)
    window.default_font_size = 11
    window.navigate_callback = MagicMock()
    parent_root = MagicMock()
    window._parent_root = parent_root  # pylint: disable=protected-access
    window._fixes_for_issues = MagicMock(return_value=[("LOG_BITMASK", 0, 1, ["required message missing"])])  # pylint: disable=protected-access
    window._open_review_dialog = MagicMock()  # pylint: disable=protected-access
    parent = MagicMock()
    card = MagicMock()
    text_frame = MagicMock()
    labels = [MagicMock(), MagicMock(), MagicMock()]
    buttons = [MagicMock(), MagicMock()]
    issue = SimpleNamespace(message="Required message missing", config_step="05-log-bitmask")
    absorbed_step = SimpleNamespace(step="05-log-bitmask")
    result = SimpleNamespace(
        name="Log message coverage",
        reason="A required message was not found.",
        issues=[issue],
        related_step="",
    )

    with (
        patch(
            "ardupilot_methodic_configurator.frontend_tkinter_log_availability.ttk.Frame",
            side_effect=[card, text_frame],
        ) as mock_frame,
        patch("ardupilot_methodic_configurator.frontend_tkinter_log_availability.ttk.Label", side_effect=labels) as mock_label,
        patch(
            "ardupilot_methodic_configurator.frontend_tkinter_log_availability.ttk.Button", side_effect=buttons
        ) as mock_button,
        patch(
            "ardupilot_methodic_configurator.frontend_tkinter_log_availability.step_display_name", return_value="Log Bitmask"
        ) as make_step_display_name,
        patch("ardupilot_methodic_configurator.frontend_tkinter_log_availability.show_tooltip") as mock_tooltip,
    ):
        window._availability_result_card(parent, result, [absorbed_step])  # pylint: disable=protected-access

    make_step_display_name.assert_called_once_with("05-log-bitmask")
    assert mock_frame.call_args_list == [call(parent), call(card)]
    card.pack.assert_called_once_with(fill="x", padx=14, pady=6)
    text_frame.pack.assert_called_once_with(side="left", fill="x", expand=True)
    assert mock_label.call_args_list == [
        call(text_frame, text=result.name, font=("TkDefaultFont", 12, "bold")),
        call(text_frame, text=result.reason, foreground="gray", font=("TkDefaultFont", 11), wraplength=500),
        call(card, text="1 Issue(s)", foreground="darkorange", font=("TkDefaultFont", 11, "bold")),
    ]
    assert [call.kwargs["text"] for call in mock_button.call_args_list] == ["Fix", "Go to Step"]
    assert mock_tooltip.call_args_list == [
        call(labels[2], "- Required message missing\n- Also required for: Log Bitmask"),
        call(card, "- Required message missing\n- Also required for: Log Bitmask"),
        call(buttons[1], "Jump to the 05-log-bitmask configuration step"),
    ]
    labels[0].pack.assert_called_once_with(anchor="w")
    labels[1].pack.assert_called_once_with(anchor="w", fill="x")
    labels[2].pack.assert_called_once_with(side="right", padx=14)
    assert all(button_call.args[0] is card for button_call in mock_button.call_args_list)
    buttons[0].pack.assert_called_once_with(side="right", padx=(0, 8))
    buttons[1].pack.assert_called_once_with(side="right", padx=(0, 8))
    mock_button.call_args_list[0].kwargs["command"]()
    mock_button.call_args_list[1].kwargs["command"]()
    window._open_review_dialog.assert_called_once_with([("LOG_BITMASK", 0, 1, ["required message missing"])])  # pylint: disable=protected-access
    window.navigate_callback.assert_called_once_with("05-log-bitmask")


def test_continue_to_analysis_warns_about_subsystems_without_results() -> None:
    """
    Explain which analysis sections will be skipped before opening detailed results.

    GIVEN a summary with one subsystem that has no analysis result,
    WHEN the user continues to the detailed analysis,
    THEN the skipped subsystem is named and the analysis window receives the report context.
    """
    window = LogAvailabilityReportWindow.__new__(LogAvailabilityReportWindow)
    window.summary = MagicMock()
    availability_results = [SimpleNamespace(name="FFT"), SimpleNamespace(name="IMU")]
    window.summary.paired_availability_and_analysis_results.return_value = [(result, None) for result in availability_results]
    window.root = MagicMock()
    window.vehicle_dir = "/vehicle"
    window.is_fc_connected = True
    window.upload_callback = MagicMock()
    window.report = {"flight": "test"}

    with (
        patch("ardupilot_methodic_configurator.frontend_tkinter_log_availability.messagebox.showinfo") as mock_info,
        patch("ardupilot_methodic_configurator.frontend_tkinter_log_availability.LogAnalysisReportWindow") as mock_analysis,
    ):
        window._on_continue_to_analysis()  # pylint: disable=protected-access

    mock_info.assert_called_once_with(
        "Continue to Analysis",
        "The following subsystems don't have enough data and will be skipped:\n\n- FFT\n- IMU",
        parent=window.root,
    )
    mock_analysis.assert_called_once_with(
        window.root,
        window.summary,
        "/vehicle",
        is_fc_connected=True,
        upload_callback=window.upload_callback,
        report={"flight": "test"},
    )


def test_review_dialog_disables_upload_without_a_connected_controller() -> None:
    """
    Prevent users from uploading automatic fixes without a flight controller.

    GIVEN proposed parameter changes and no connected flight controller,
    WHEN the review dialog is opened,
    THEN the upload action is disabled while the user can still cancel.
    """
    window = LogAvailabilityReportWindow.__new__(LogAvailabilityReportWindow)
    window.root = MagicMock()
    window.is_fc_connected = False
    window.default_font_size = 11
    window.calculate_scaled_geometry = MagicMock(return_value="520x260")
    window.center_window = MagicMock()
    dialog = MagicMock()
    rows_frame = MagicMock()
    parameter_rows = [MagicMock(), MagicMock()]
    button_row = MagicMock()
    labels = [MagicMock() for _ in range(9)]
    buttons = [MagicMock(), MagicMock()]
    fixes = [
        ("MOT_SPIN_MIN", 0.1, 0.15, ["minimum throttle too high", "minimum throttle too low"]),
        ("MOT_SPIN_MAX", 0.2, 0.25, ["maximum throttle too low"]),
    ]

    with (
        patch(
            "ardupilot_methodic_configurator.frontend_tkinter_log_availability.tk.Toplevel", return_value=dialog
        ) as mock_toplevel,
        patch(
            "ardupilot_methodic_configurator.frontend_tkinter_log_availability.ttk.Frame",
            side_effect=[rows_frame, *parameter_rows, button_row],
        ) as make_frame,
        patch(
            "ardupilot_methodic_configurator.frontend_tkinter_log_availability.ttk.Label",
            side_effect=labels,
        ) as make_label,
        patch(
            "ardupilot_methodic_configurator.frontend_tkinter_log_availability.ttk.Button", side_effect=buttons
        ) as mock_button,
        patch("ardupilot_methodic_configurator.frontend_tkinter_log_availability.show_tooltip") as show_tooltip,
    ):
        window._open_review_dialog(fixes)  # pylint: disable=protected-access

    mock_toplevel.assert_called_once_with(window.root)
    dialog.title.assert_called_once_with("Review Parameter Changes")
    window.calculate_scaled_geometry.assert_called_once_with(520, 260)
    dialog.geometry.assert_called_once_with("520x260")
    window.center_window.assert_called_once_with(dialog, window.root)
    dialog.transient.assert_called_once_with(window.root)
    dialog.grab_set.assert_called_once_with()
    assert make_frame.call_args_list == [call(dialog), call(rows_frame), call(rows_frame), call(dialog)]
    rows_frame.pack.assert_called_once_with(fill="both", expand=True, padx=14, pady=(0, 6))
    for parameter_row in parameter_rows:
        parameter_row.pack.assert_called_once_with(fill="x", pady=4)
    button_row.pack.assert_called_once_with(fill="x", padx=14, pady=(6, 14))
    assert make_label.call_args_list == [
        call(dialog, text="The following parameter change(s) are proposed:", font=("TkDefaultFont", 11, "bold")),
        call(parameter_rows[0], text="MOT_SPIN_MIN", width=18, font=("TkDefaultFont", 11, "bold")),
        call(parameter_rows[0], text="0.1", foreground="gray"),
        call(parameter_rows[0], text="->"),
        call(parameter_rows[0], text="0.15", foreground="darkgreen", font=("TkDefaultFont", 11, "bold")),
        call(parameter_rows[1], text="MOT_SPIN_MAX", width=18, font=("TkDefaultFont", 11, "bold")),
        call(parameter_rows[1], text="0.2", foreground="gray"),
        call(parameter_rows[1], text="->"),
        call(parameter_rows[1], text="0.25", foreground="darkgreen", font=("TkDefaultFont", 11, "bold")),
    ]
    labels[0].pack.assert_called_once_with(anchor="w", padx=14, pady=(14, 6))
    labels[1].pack.assert_called_once_with(side="left")
    labels[2].pack.assert_called_once_with(side="left", padx=(0, 6))
    labels[3].pack.assert_called_once_with(side="left", padx=(0, 6))
    labels[4].pack.assert_called_once_with(side="left")
    show_tooltip.assert_any_call(labels[4], "- minimum throttle too high\n- minimum throttle too low")
    show_tooltip.assert_any_call(labels[8], "- maximum throttle too low")
    buttons[1].configure.assert_called_once_with(state="disabled")
    assert mock_button.call_args_list[0] == call(button_row, text="Cancel", command=dialog.destroy)
    assert mock_button.call_args_list[1].args == (button_row,)
    assert mock_button.call_args_list[1].kwargs["text"] == "Apply & Upload"
    buttons[0].pack.assert_called_once_with(side="right", padx=(6, 0))
    buttons[1].pack.assert_called_once_with(side="right")
    show_tooltip.assert_any_call(buttons[1], "No flight controller connected, upload not available")
    mock_button.call_args_list[0].kwargs["command"]()
    dialog.destroy.assert_called_once_with()


def test_review_dialog_applies_fix_when_controller_is_connected() -> None:
    """
    Apply reviewed values after the user confirms while connected to a controller.

    GIVEN a connected controller and one proposed parameter change,
    WHEN the user selects Apply & Upload,
    THEN the parameter summary is updated and the review dialog closes.
    """
    window = LogAvailabilityReportWindow.__new__(LogAvailabilityReportWindow)
    window.root = MagicMock()
    window.summary = SimpleNamespace(related_parameter_values={"MOT_SPIN_MIN": 0.1})
    window.is_fc_connected = True
    window.upload_callback = None
    window.default_font_size = 11
    window.calculate_scaled_geometry = MagicMock(return_value="520x200")
    window.center_window = MagicMock()
    dialog = MagicMock()
    buttons = [MagicMock(), MagicMock()]
    fixes = [("MOT_SPIN_MIN", 0.1, 0.15, ["minimum throttle too high"])]

    with (
        patch(
            "ardupilot_methodic_configurator.frontend_tkinter_log_availability.tk.Toplevel",
            return_value=dialog,
        ),
        patch("ardupilot_methodic_configurator.frontend_tkinter_log_availability.ttk.Frame"),
        patch("ardupilot_methodic_configurator.frontend_tkinter_log_availability.ttk.Label") as make_label,
        patch(
            "ardupilot_methodic_configurator.frontend_tkinter_log_availability.ttk.Button",
            side_effect=buttons,
        ) as make_button,
        patch("ardupilot_methodic_configurator.frontend_tkinter_log_availability.show_tooltip") as show_tooltip,
    ):
        window._open_review_dialog(fixes)  # pylint: disable=protected-access

    window.calculate_scaled_geometry.assert_called_once_with(520, 200)
    dialog.geometry.assert_called_once_with("520x200")
    window.center_window.assert_called_once_with(dialog, window.root)
    buttons[1].configure.assert_called_once_with(state="normal")
    assert show_tooltip.call_args_list == [call(make_label.return_value, "- minimum throttle too high")]
    make_button.call_args_list[1].kwargs["command"]()
    assert window.summary.related_parameter_values == {"MOT_SPIN_MIN": 0.15}
    dialog.destroy.assert_called_once_with()


def test_report_window_initializes_and_builds_each_report_section() -> None:
    """
    Initialize the report window with its caller's context and build its sections.

    GIVEN a configured parent window and report data,
    WHEN the availability report window is opened,
    THEN it stores the context, configures its window, and builds each section.
    """
    root = MagicMock()
    summary = MagicMock()
    upload_callback = MagicMock()
    navigate_callback = MagicMock()
    report = {"flight": "test"}

    with (
        patch.object(BaseWindow, "__init__", autospec=True, side_effect=lambda self, parent: setattr(self, "root", parent)),
        patch.object(BaseWindow, "calculate_scaled_geometry", return_value="1000x750") as calculate_geometry,
        patch.object(BaseWindow, "center_window") as center_window,
        patch.object(LogAvailabilityReportWindow, "_build_header_summary") as build_header,
        patch.object(LogAvailabilityReportWindow, "_build_stats_cards") as build_stats,
        patch.object(LogAvailabilityReportWindow, "_build_footer") as build_footer,
        patch.object(LogAvailabilityReportWindow, "_build_tabs") as build_tabs,
    ):
        window = LogAvailabilityReportWindow(
            root,
            summary,
            "/vehicle",
            upload_callback=upload_callback,
            navigate_callback=navigate_callback,
            report=report,
        )

    assert window.root is root
    assert window.summary is summary
    assert window.vehicle_dir == "/vehicle"
    assert window.is_fc_connected is False
    assert window.upload_callback is upload_callback
    assert window.navigate_callback is navigate_callback
    assert window._parent_root is root  # pylint: disable=protected-access
    assert window.report is report
    assert window._analysis_window is None  # pylint: disable=protected-access
    root.title.assert_called_once_with("Log Availability Report")
    calculate_geometry.assert_called_once_with(1000, 750)
    root.geometry.assert_called_once_with("1000x750")
    root.resizable.assert_called_once_with(width=True, height=True)
    center_window.assert_called_once_with(window.root, root)
    build_header.assert_called_once_with()
    build_stats.assert_called_once_with()
    build_footer.assert_called_once_with()
    build_tabs.assert_called_once_with()


def test_report_window_format_helpers_delegate_to_shared_formatters() -> None:
    """
    Reuse shared duration and file-size formatting in the report.

    GIVEN duration and file-size values,
    WHEN the report formats them,
    THEN each value is passed to its corresponding shared formatter.
    """
    with (
        patch(
            "ardupilot_methodic_configurator.frontend_tkinter_log_availability.format_duration", return_value="00:42"
        ) as duration,
        patch(
            "ardupilot_methodic_configurator.frontend_tkinter_log_availability.format_filesize", return_value="4 KB"
        ) as size,
    ):
        assert LogAvailabilityReportWindow._fmt_duration(42.0) == "00:42"  # pylint: disable=protected-access
        assert LogAvailabilityReportWindow._fmt_filesize(4096) == "4 KB"  # pylint: disable=protected-access

    duration.assert_called_once_with(42.0)
    size.assert_called_once_with(4096)


def test_key_value_row_displays_both_labels_with_the_expected_layout() -> None:
    """
    Show a report field as a readable key and value pair.

    GIVEN a report card and a field name with its value,
    WHEN the key-value row is built,
    THEN both labels are displayed inside a full-width row.
    """
    parent = MagicMock()
    row = MagicMock()
    labels = [MagicMock(), MagicMock()]

    with (
        patch("ardupilot_methodic_configurator.frontend_tkinter_log_availability.ttk.Frame", return_value=row) as make_frame,
        patch("ardupilot_methodic_configurator.frontend_tkinter_log_availability.ttk.Label", side_effect=labels) as make_label,
    ):
        LogAvailabilityReportWindow._add_key_value(parent, "Flight Time:", "00:42")  # pylint: disable=protected-access

    make_frame.assert_called_once_with(parent)
    row.pack.assert_called_once_with(fill="x", padx=10, pady=3)
    assert make_label.call_args_list == [
        call(row, text="Flight Time:", foreground="gray", font=("TkDefaultFont", 11), width=14),
        call(row, text="00:42", font=("TkDefaultFont", 11, "bold")),
    ]
    labels[0].pack.assert_called_once_with(side="left")
    labels[1].pack.assert_called_once_with(side="left", fill="x", expand=True)


def test_header_and_footer_present_summary_and_analysis_action() -> None:
    """
    Show the report status and a clear route to detailed analysis.

    GIVEN a report with a summary status,
    WHEN its header and footer are built,
    THEN the status is visible and the analysis button invokes the continuation action.
    """
    window = LogAvailabilityReportWindow.__new__(LogAvailabilityReportWindow)
    window.summary = MagicMock()
    window.main_frame = MagicMock()
    window._on_continue_to_analysis = MagicMock()  # pylint: disable=protected-access
    header = MagicMock()
    footer = MagicMock()
    button = MagicMock()
    status = SimpleNamespace(text="Needs attention", color="darkorange")

    with (
        patch(
            "ardupilot_methodic_configurator.frontend_tkinter_log_availability.ttk.Frame",
            side_effect=[header, footer],
        ) as make_frame,
        patch("ardupilot_methodic_configurator.frontend_tkinter_log_availability.ttk.Label") as make_label,
        patch(
            "ardupilot_methodic_configurator.frontend_tkinter_log_availability.ttk.Button", return_value=button
        ) as make_button,
        patch(
            "ardupilot_methodic_configurator.frontend_tkinter_log_availability.build_report_status",
            return_value=status,
        ) as make_status,
        patch("ardupilot_methodic_configurator.frontend_tkinter_log_availability.show_tooltip") as show_tooltip,
    ):
        window._build_header_summary()  # pylint: disable=protected-access
        window._build_footer()  # pylint: disable=protected-access

    assert make_frame.call_args_list == [call(window.main_frame), call(window.main_frame)]
    make_status.assert_called_once_with(window.summary)
    header.pack.assert_called_once_with(side="top", fill="x", padx=14, pady=(14, 6))
    footer.pack.assert_called_once_with(side="bottom", fill="x", padx=14, pady=(0, 14))
    make_label.assert_called_once_with(
        header, text="Needs attention", foreground="darkorange", font=("TkDefaultFont", 13, "bold")
    )
    make_label.return_value.pack.assert_called_once_with(side="left")
    analysis_callback = window._on_continue_to_analysis  # pylint: disable=protected-access
    make_button.assert_called_once_with(footer, text="Continue to Analysis", command=analysis_callback)
    button.pack.assert_called_once_with(side="right")
    make_button.call_args.kwargs["command"]()
    window._on_continue_to_analysis.assert_called_once_with()  # pylint: disable=protected-access
    show_tooltip.assert_called_once_with(button, "Open the detailed log analysis for this flight")


def test_continue_to_analysis_skips_warning_when_every_subsystem_has_results() -> None:
    """
    Open analysis directly when no subsystem will be skipped.

    GIVEN every available subsystem has a corresponding analysis result,
    WHEN the user continues to analysis,
    THEN the detailed analysis opens without a skip warning.
    """
    window = LogAvailabilityReportWindow.__new__(LogAvailabilityReportWindow)
    window.summary = MagicMock()
    window.summary.paired_availability_and_analysis_results.return_value = [(SimpleNamespace(name="FFT"), object())]
    window.root = MagicMock()
    window.vehicle_dir = "/vehicle"
    window.is_fc_connected = False
    window.upload_callback = None
    window.report = None

    with (
        patch("ardupilot_methodic_configurator.frontend_tkinter_log_availability.messagebox.showinfo") as show_info,
        patch("ardupilot_methodic_configurator.frontend_tkinter_log_availability.LogAnalysisReportWindow") as analysis_window,
    ):
        window._on_continue_to_analysis()  # pylint: disable=protected-access

    show_info.assert_not_called()
    analysis_window.assert_called_once()
    assert window._analysis_window is analysis_window.return_value  # pylint: disable=protected-access


def test_step_fallback_returns_empty_when_no_issue_has_a_configuration_step() -> None:
    """
    Leave findings without a configuration reference without a navigation target.

    GIVEN issues whose configuration-step references are empty,
    WHEN a fallback step is requested,
    THEN no navigation step is returned.
    """
    issues = [SimpleNamespace(config_step=""), SimpleNamespace(config_step="")]

    assert LogAvailabilityReportWindow._first_config_step(issues) == ""  # pylint: disable=protected-access


def test_navigation_restores_parent_even_when_no_navigation_callback_is_set() -> None:
    """
    Restore the parent window even when the report has no step-navigation callback.

    GIVEN a report without a navigation callback,
    WHEN a user chooses a step,
    THEN the parent configurator is shown and focused.
    """
    window = LogAvailabilityReportWindow.__new__(LogAvailabilityReportWindow)
    window.navigate_callback = None
    parent_root = MagicMock()
    window._parent_root = parent_root  # pylint: disable=protected-access

    window._navigate_to_step("08-calibration")  # pylint: disable=protected-access

    parent_root.deiconify.assert_called_once_with()
    parent_root.lift.assert_called_once_with()
    parent_root.focus_force.assert_called_once_with()


def test_apply_parameter_fixes_updates_summary_without_an_upload_callback() -> None:
    """
    Apply a local parameter fix when no flight-controller upload callback is provided.

    GIVEN a parameter fix and no upload callback,
    WHEN the fix is applied,
    THEN the summary reflects the proposed value and the review dialog closes.
    """
    window = LogAvailabilityReportWindow.__new__(LogAvailabilityReportWindow)
    window.summary = SimpleNamespace(related_parameter_values={"MOT_SPIN_MIN": 0.1})
    window.upload_callback = None
    dialog = MagicMock()

    window._apply_param_fixes([("MOT_SPIN_MIN", 0.1, 0.15, ["finding"])], dialog)  # pylint: disable=protected-access

    assert window.summary.related_parameter_values == {"MOT_SPIN_MIN": 0.15}
    dialog.destroy.assert_called_once_with()


def test_stats_card_builder_creates_vehicle_log_and_performance_cards() -> None:
    """
    Build the three summary cards into one shared container.

    GIVEN a report window with a main content frame,
    WHEN its statistics section is built,
    THEN vehicle, log, and performance cards receive the same container.
    """
    window = LogAvailabilityReportWindow.__new__(LogAvailabilityReportWindow)
    window.main_frame = MagicMock()
    container = MagicMock()

    with (
        patch(
            "ardupilot_methodic_configurator.frontend_tkinter_log_availability.ttk.Frame", return_value=container
        ) as make_frame,
        patch.object(window, "_build_vehicle_card") as vehicle_card,
        patch.object(window, "_build_log_overview_card") as log_card,
        patch.object(window, "_build_performance_card") as performance_card,
    ):
        window._build_stats_cards()  # pylint: disable=protected-access

    make_frame.assert_called_once_with(window.main_frame)
    container.pack.assert_called_once_with(side="top", fill="x", padx=12, pady=8)
    vehicle_card.assert_called_once_with(container)
    log_card.assert_called_once_with(container)
    performance_card.assert_called_once_with(container)


def test_vehicle_card_shows_firmware_link_and_hardware_details() -> None:
    """
    Display firmware and vehicle hardware details when they are available.

    GIVEN a hardware report with firmware release and board information,
    WHEN the vehicle card is built,
    THEN the firmware is clickable and controller and board names are shown.
    """
    window = LogAvailabilityReportWindow.__new__(LogAvailabilityReportWindow)
    vehicle = SimpleNamespace(flight_controller="Cube Orange")
    hardware = SimpleNamespace(vehicle=vehicle, board_name="CubeOrange")
    window.summary = SimpleNamespace(hardware_report=hardware)
    window._add_key_value = MagicMock()  # pylint: disable=protected-access
    window._add_clickable_key_value = MagicMock()  # pylint: disable=protected-access
    parent = MagicMock()
    card = MagicMock()
    release = SimpleNamespace(base_text="ArduCopter", version_tag="Copter-4.5.5", url="https://example.test/release")

    with (
        patch(
            "ardupilot_methodic_configurator.frontend_tkinter_log_availability.ttk.LabelFrame", return_value=card
        ) as make_card,
        patch(
            "ardupilot_methodic_configurator.frontend_tkinter_log_availability.firmware_release_link",
            return_value=release,
        ) as make_release,
    ):
        window._build_vehicle_card(parent)  # pylint: disable=protected-access

    make_card.assert_called_once_with(parent, text="Vehicle & Firmware")
    card.pack.assert_called_once_with(side="left", fill="both", expand=True, padx=(0, 6))
    make_release.assert_called_once_with(vehicle)
    window._add_clickable_key_value.assert_called_once_with(  # pylint: disable=protected-access
        card, "Firmware:", "ArduCopter (Copter-4.5.5)", "https://example.test/release"
    )
    assert window._add_key_value.call_args_list == [  # pylint: disable=protected-access
        call(card, "FC:", "Cube Orange"),
        call(card, "Board:", "CubeOrange"),
    ]


def test_vehicle_card_uses_placeholders_when_hardware_is_missing() -> None:
    """
    Show stable placeholders when a log has no hardware report.

    GIVEN no hardware report or firmware release,
    WHEN the vehicle card is built,
    THEN firmware, controller, and board fields show placeholders.
    """
    window = LogAvailabilityReportWindow.__new__(LogAvailabilityReportWindow)
    window.summary = SimpleNamespace(hardware_report=None)
    window._add_key_value = MagicMock()  # pylint: disable=protected-access
    window._add_clickable_key_value = MagicMock()  # pylint: disable=protected-access
    parent = MagicMock()
    card = MagicMock()

    with (
        patch(
            "ardupilot_methodic_configurator.frontend_tkinter_log_availability.ttk.LabelFrame", return_value=card
        ) as make_card,
        patch(
            "ardupilot_methodic_configurator.frontend_tkinter_log_availability.firmware_release_link",
            return_value=None,
        ) as make_release,
    ):
        window._build_vehicle_card(parent)  # pylint: disable=protected-access

    make_card.assert_called_once_with(parent, text="Vehicle & Firmware")
    card.pack.assert_called_once_with(side="left", fill="both", expand=True, padx=(0, 6))
    make_release.assert_called_once_with(None)
    assert window._add_key_value.call_args_list == [  # pylint: disable=protected-access
        call(card, "Firmware:", "-"),
        call(card, "FC:", "-"),
        call(card, "Board:", "-"),
    ]
    window._add_clickable_key_value.assert_not_called()  # pylint: disable=protected-access


def test_log_overview_card_formats_duration_file_size_and_message_count() -> None:
    """
    Show the core file and flight summary values in the log overview card.

    GIVEN duration, file size, and total message data,
    WHEN the log overview card is built,
    THEN all values are formatted and displayed with their labels.
    """
    window = LogAvailabilityReportWindow.__new__(LogAvailabilityReportWindow)
    window.summary = SimpleNamespace(flight_duration_sec=42.0, file_size_bytes=4096, total_messages=1234)
    window._add_key_value = MagicMock()  # pylint: disable=protected-access
    window._fmt_duration = MagicMock(return_value="00:42")  # pylint: disable=protected-access
    window._fmt_filesize = MagicMock(return_value="4 KB")  # pylint: disable=protected-access
    card = MagicMock()
    parent = MagicMock()

    with patch(
        "ardupilot_methodic_configurator.frontend_tkinter_log_availability.ttk.LabelFrame", return_value=card
    ) as make_card:
        window._build_log_overview_card(parent)  # pylint: disable=protected-access

    make_card.assert_called_once_with(parent, text="Log Overview")
    card.pack.assert_called_once_with(side="left", fill="both", expand=True, padx=6)
    window._fmt_duration.assert_called_once_with(42.0)  # pylint: disable=protected-access
    window._fmt_filesize.assert_called_once_with(4096)  # pylint: disable=protected-access
    assert window._add_key_value.call_args_list == [  # pylint: disable=protected-access
        call(card, "Flight Time:", "00:42"),
        call(card, "Log Size:", "4 KB"),
        call(card, "Total Msgs:", "1234"),
    ]


def test_performance_card_shows_metrics_or_placeholders() -> None:
    """
    Show performance values when present and placeholders when unavailable.

    GIVEN reports both with and without performance-monitor data,
    WHEN each performance card is built,
    THEN available metrics are formatted and missing metrics use placeholders.
    """
    window = LogAvailabilityReportWindow.__new__(LogAvailabilityReportWindow)
    window._add_key_value = MagicMock()  # pylint: disable=protected-access
    parent = MagicMock()

    for pm_status, expected in (
        (SimpleNamespace(average_cpu_load=12.34, peak_cpu_load=87.65, scheduler_long_loops=6), ("12.3%", "87.7%", "6")),
        (None, ("-", "-", "-")),
    ):
        window.summary = SimpleNamespace(pm_status=pm_status)
        window._add_key_value.reset_mock()  # pylint: disable=protected-access
        card = MagicMock()
        with patch(
            "ardupilot_methodic_configurator.frontend_tkinter_log_availability.ttk.LabelFrame", return_value=card
        ) as make_card:
            window._build_performance_card(parent)  # pylint: disable=protected-access
        make_card.assert_called_once_with(parent, text="System Performance")
        card.pack.assert_called_once_with(side="left", fill="both", expand=True, padx=(6, 0))
        assert window._add_key_value.call_args_list == [  # pylint: disable=protected-access
            call(card, "Avg CPU:", expected[0]),
            call(card, "Peak CPU:", expected[1]),
            call(card, "Long Loops:", expected[2]),
        ]


def test_tabs_build_availability_and_hardware_pages() -> None:
    """
    Present availability and hardware reports on separate notebook tabs.

    GIVEN report data and a main content frame,
    WHEN the tabs are built,
    THEN each page is added and populated with its corresponding report.
    """
    window = LogAvailabilityReportWindow.__new__(LogAvailabilityReportWindow)
    window.main_frame = MagicMock()
    window.summary = SimpleNamespace(hardware_report="hardware-data")
    notebook = MagicMock()
    availability_frame = MagicMock()
    hardware_frame = MagicMock()
    window._build_availability_tab = MagicMock()  # pylint: disable=protected-access

    with (
        patch("ardupilot_methodic_configurator.frontend_tkinter_log_availability.ttk.Style") as make_style,
        patch(
            "ardupilot_methodic_configurator.frontend_tkinter_log_availability.ttk.Notebook", return_value=notebook
        ) as make_notebook,
        patch(
            "ardupilot_methodic_configurator.frontend_tkinter_log_availability.ttk.Frame",
            side_effect=[availability_frame, hardware_frame],
        ) as make_frame,
        patch("ardupilot_methodic_configurator.frontend_tkinter_log_availability.build_hardware_tab") as hardware_tab,
    ):
        window._build_tabs()  # pylint: disable=protected-access

    make_style.return_value.configure.assert_called_once_with("TNotebook.Tab", font=("TkDefaultFont", 11))
    make_notebook.assert_called_once_with(window.main_frame)
    notebook.pack.assert_called_once_with(side="top", fill="both", expand=True, padx=12, pady=(12, 12))
    assert make_frame.call_args_list == [call(notebook), call(notebook)]
    assert notebook.add.call_args_list == [
        call(availability_frame, text="  Data Availability Report  "),
        call(hardware_frame, text="  Hardware Overview  "),
    ]
    window._build_availability_tab.assert_called_once_with(availability_frame)  # pylint: disable=protected-access
    hardware_tab.assert_called_once_with(hardware_frame, "hardware-data")


def test_empty_availability_report_renders_no_result_sections() -> None:
    """
    Leave the availability tab clear when a report has no checks to show.

    GIVEN a report with no availability or step results,
    WHEN the availability tab is built,
    THEN no empty attention or passed-check sections are drawn.
    """
    window = LogAvailabilityReportWindow.__new__(LogAvailabilityReportWindow)
    window.summary = SimpleNamespace(availability_results=[], step_results=[])
    scroll = MagicMock()

    with (
        patch(
            "ardupilot_methodic_configurator.frontend_tkinter_log_availability.ScrollFrame", return_value=scroll
        ) as make_scroll,
        patch("ardupilot_methodic_configurator.frontend_tkinter_log_availability.ttk.Label") as make_label,
        patch("ardupilot_methodic_configurator.frontend_tkinter_log_availability.ttk.Separator") as make_separator,
    ):
        parent = MagicMock()
        window._build_availability_tab(parent)  # pylint: disable=protected-access

    make_scroll.assert_called_once_with(parent)
    scroll.pack.assert_called_once_with(fill="both", expand=True)
    make_label.assert_not_called()
    make_separator.assert_not_called()


def test_availability_card_without_issues_shows_only_name_and_reason() -> None:
    """
    Keep successful availability cards free of issue actions.

    GIVEN an availability result with no issues,
    WHEN its card is rendered,
    THEN only the result name and reason are shown without action buttons.
    """
    window = LogAvailabilityReportWindow.__new__(LogAvailabilityReportWindow)
    parent = MagicMock()
    card = MagicMock()
    text_frame = MagicMock()
    result = SimpleNamespace(name="Battery telemetry", reason="All required data is present", issues=[])
    name_label = MagicMock()
    reason_label = MagicMock()

    with (
        patch(
            "ardupilot_methodic_configurator.frontend_tkinter_log_availability.ttk.Frame",
            side_effect=[card, text_frame],
        ) as make_frame,
        patch(
            "ardupilot_methodic_configurator.frontend_tkinter_log_availability.ttk.Label",
            side_effect=[name_label, reason_label],
        ) as make_label,
        patch("ardupilot_methodic_configurator.frontend_tkinter_log_availability.ttk.Button") as make_button,
    ):
        window._availability_result_card(parent, result, [])  # pylint: disable=protected-access

    assert make_frame.call_args_list == [call(parent), call(card)]
    card.pack.assert_called_once_with(fill="x", padx=14, pady=6)
    text_frame.pack.assert_called_once_with(side="left", fill="x", expand=True)
    assert make_label.call_args_list == [
        call(text_frame, text=result.name, font=("TkDefaultFont", 12, "bold")),
        call(text_frame, text=result.reason, foreground="gray", font=("TkDefaultFont", 11), wraplength=500),
    ]
    name_label.pack.assert_called_once_with(anchor="w")
    reason_label.pack.assert_called_once_with(anchor="w", fill="x")
    make_button.assert_not_called()
    assert text_frame.bind.call_args.args[0] == "<Configure>"
    wrap_callback = text_frame.bind.call_args.args[1]
    LogAvailabilityReportWindow._set_wraplength(reason_label, None)  # pylint: disable=protected-access
    wrap_callback(SimpleNamespace(width=100))
    assert reason_label.configure.call_args_list == [call(wraplength=10), call(wraplength=85)]


def test_availability_card_with_non_actionable_issue_has_no_fix_or_step_buttons() -> None:
    """
    Keep findings visible without offering actions when no fix or step is known.

    GIVEN an issue without a suggested parameter or configuration step,
    WHEN its availability card is rendered,
    THEN the finding is explained and no Fix or Go to Step button appears.
    """
    window = LogAvailabilityReportWindow.__new__(LogAvailabilityReportWindow)
    window.summary = SimpleNamespace(related_parameter_values={})
    result = SimpleNamespace(
        name="Log message coverage",
        reason="A required message was not found.",
        issues=[SimpleNamespace(message="Missing message", param_name=None, suggested_value=None, config_step="")],
        related_step="",
    )

    with (
        patch("ardupilot_methodic_configurator.frontend_tkinter_log_availability.ttk.Frame"),
        patch("ardupilot_methodic_configurator.frontend_tkinter_log_availability.ttk.Label"),
        patch("ardupilot_methodic_configurator.frontend_tkinter_log_availability.ttk.Button") as make_button,
        patch("ardupilot_methodic_configurator.frontend_tkinter_log_availability.show_tooltip") as show_tooltip,
    ):
        window._availability_result_card(MagicMock(), result, [])  # pylint: disable=protected-access

    make_button.assert_not_called()
    assert any("Missing message" in str(tooltip_call.args[1]) for tooltip_call in show_tooltip.call_args_list)


def test_valid_step_card_has_no_navigation_action() -> None:
    """
    Avoid offering step navigation for a validation result that already passes.

    GIVEN a valid step with no display name,
    WHEN the step card is rendered,
    THEN it shows the step without a tooltip or Go to Step button.
    """
    window = LogAvailabilityReportWindow.__new__(LogAvailabilityReportWindow)
    result = SimpleNamespace(step="08-compass-calibration", name="", valid=True, message_results={})

    with (
        patch("ardupilot_methodic_configurator.frontend_tkinter_log_availability.ttk.Frame"),
        patch("ardupilot_methodic_configurator.frontend_tkinter_log_availability.ttk.Label"),
        patch("ardupilot_methodic_configurator.frontend_tkinter_log_availability.ttk.Button") as make_button,
        patch("ardupilot_methodic_configurator.frontend_tkinter_log_availability.show_tooltip") as show_tooltip,
    ):
        window._step_result_card(MagicMock(), result)  # pylint: disable=protected-access

    make_button.assert_not_called()
    show_tooltip.assert_not_called()

    invalid_result = SimpleNamespace(
        step="08-compass-calibration",
        name="",
        valid=False,
        message_results={"COMPASS": SimpleNamespace(issues=[])},
    )
    with (
        patch("ardupilot_methodic_configurator.frontend_tkinter_log_availability.ttk.Frame"),
        patch("ardupilot_methodic_configurator.frontend_tkinter_log_availability.ttk.Label"),
        patch("ardupilot_methodic_configurator.frontend_tkinter_log_availability.ttk.Button") as make_button,
        patch("ardupilot_methodic_configurator.frontend_tkinter_log_availability.show_tooltip") as show_tooltip,
    ):
        window._step_result_card(MagicMock(), invalid_result)  # pylint: disable=protected-access

    make_button.assert_called_once()
    show_tooltip.assert_not_called()


def test_run_enters_the_tk_event_loop() -> None:
    """
    Keep the report window active until its Tk event loop exits.

    GIVEN a constructed report window,
    WHEN it is run,
    THEN its root event loop is started.
    """
    window = LogAvailabilityReportWindow.__new__(LogAvailabilityReportWindow)
    window.root = MagicMock()

    window.run()

    window.root.mainloop.assert_called_once_with()
