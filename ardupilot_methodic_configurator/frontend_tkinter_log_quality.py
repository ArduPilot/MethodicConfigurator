"""
Log quality report window for the ArduPilot Methodic Configurator.

Displays a parsed ArduPilot .bin log analysis.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-FileCopyrightText: 2026 Omkar Sarkar <omkarsarkar24@gmail.com>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import tkinter as tk
from collections.abc import Callable
from functools import partial
from tkinter import messagebox, ttk
from typing import cast

from ardupilot_methodic_configurator import _
from ardupilot_methodic_configurator.backend_internet import webbrowser_open_url
from ardupilot_methodic_configurator.data_model_par_dict import Par
from ardupilot_methodic_configurator.formatting import format_filesize
from ardupilot_methodic_configurator.frontend_tkinter_base_window import BaseWindow
from ardupilot_methodic_configurator.frontend_tkinter_log_analysis import (
    LogAnalysisReportWindow,
    paired_quality_and_analysis_results,
)
from ardupilot_methodic_configurator.frontend_tkinter_log_hardware_quality import build_hardware_tab
from ardupilot_methodic_configurator.frontend_tkinter_scroll_frame import ScrollFrame
from ardupilot_methodic_configurator.frontend_tkinter_show import show_tooltip
from ardupilot_methodic_configurator.log_analysis.data_model_log_analysis import LogSummary
from ardupilot_methodic_configurator.log_analysis.data_model_log_quality import (
    LogQualityResult,
    LogQualityState,
    QualityIssue,
    StepValidationResult,
)
from ardupilot_methodic_configurator.log_analysis.data_model_log_report import (
    build_report_status,
    firmware_release_link,
    format_duration,
    step_display_name,
)


def _format_parameter_value(value: float) -> str:
    """Format a parameter value without hiding fractional changes."""
    return str(int(value)) if value.is_integer() else str(value)


class LogQualityReportWindow(BaseWindow):  # pylint: disable=too-many-instance-attributes
    """Displays log analysis results as a beginner-friendly, detailed dashboard."""

    # pylint: disable=duplicate-code
    def __init__(  # pylint: disable=too-many-arguments, too-many-positional-arguments
        self,
        root_tk: tk.Tk | tk.Toplevel,
        summary: LogSummary,
        vehicle_dir: str,
        is_fc_connected: bool = False,
        upload_callback: Callable[[dict[str, Par]], bool | None] | None = None,
        navigate_callback: Callable[[str], None] | None = None,
        report: dict | None = None,
    ) -> None:
        super().__init__(root_tk)
        self.summary = summary
        self.vehicle_dir = vehicle_dir
        self.is_fc_connected = is_fc_connected
        self.upload_callback = upload_callback
        self.navigate_callback = navigate_callback
        self._parent_root = root_tk
        self.root.title(_("Log Quality Report"))
        self.root.geometry(self.calculate_scaled_geometry(1000, 750))
        self.center_window(self.root, root_tk)
        self.root.resizable(width=True, height=True)
        self._analysis_window: LogAnalysisReportWindow | None = None

        self._build_header_summary()
        self._build_stats_cards()
        self._build_footer()
        self.report = report
        self._build_tabs()

    @staticmethod
    def _fmt_duration(sec: float | None) -> str:
        return format_duration(sec)

    @staticmethod
    def _fmt_filesize(size_bytes: int) -> str:  # pylint: disable=duplicate-code
        return format_filesize(size_bytes)

    @staticmethod
    def _add_key_value(parent: ttk.Frame | ttk.LabelFrame, key: str, value: str) -> None:
        """Pack a key-value pair inside a card."""
        row = ttk.Frame(parent)
        row.pack(fill=tk.X, padx=10, pady=3)
        ttk.Label(row, text=key, foreground="gray", font=("TkDefaultFont", 11), width=14).pack(side=tk.LEFT)
        ttk.Label(row, text=value, font=("TkDefaultFont", 11, "bold")).pack(side=tk.LEFT, fill=tk.X, expand=True)

    @staticmethod
    def _open_url(url: str, _event: tk.Event | None = None) -> None:
        webbrowser_open_url(url)

    @staticmethod
    def _set_wraplength(label: ttk.Label, event: tk.Event | None) -> None:
        label.configure(wraplength=max(10, (event.width if event is not None else 0) - 15))

    @staticmethod
    def _set_step_wraplength(label: ttk.Label, event: tk.Event | None) -> None:
        label.configure(wraplength=max(10, (event.width if event is not None else 0) - 90))

    def _add_clickable_key_value(self, parent: ttk.Frame | ttk.LabelFrame, key: str, value: str, url: str) -> None:
        """Pack a clickable key-value pair that opens a URL."""
        row = ttk.Frame(parent)
        row.pack(fill=tk.X, padx=10, pady=3)
        ttk.Label(row, text=key, foreground="gray", font=("TkDefaultFont", 11), width=14).pack(side=tk.LEFT)
        link = ttk.Label(
            row,
            text=value,
            foreground="blue",
            cursor="hand2",
            font=("TkDefaultFont", self.default_font_size, "underline"),
        )
        link.pack(side=tk.LEFT, fill=tk.X, expand=True)
        link.bind("<Button-1>", partial(self._open_url, url))
        show_tooltip(link, _("Open release page on GitHub"))

    def _build_header_summary(self) -> None:
        """Quick TL;DR banner."""
        header_frame = ttk.Frame(self.main_frame)
        header_frame.pack(side=tk.TOP, fill=tk.X, padx=14, pady=(14, 6))

        status = build_report_status(self.summary)
        ttk.Label(
            header_frame,
            text=status.text,
            foreground=status.color,
            font=("TkDefaultFont", 13, "bold"),
        ).pack(side=tk.LEFT)

    def _build_footer(self) -> None:
        footer = ttk.Frame(self.main_frame)
        footer.pack(side=tk.BOTTOM, fill=tk.X, padx=14, pady=(0, 14))

        continue_button = ttk.Button(footer, text=_("Continue to Analysis"), command=self._on_continue_to_analysis)
        continue_button.pack(side=tk.RIGHT)
        show_tooltip(continue_button, _("Open the detailed log analysis for this flight"))

    def _on_continue_to_analysis(self) -> None:
        pending_names = [
            quality_result.name
            for quality_result, analysis_result in paired_quality_and_analysis_results(self.summary)
            if analysis_result is None
        ]
        if pending_names:
            messagebox.showinfo(
                _("Continue to Analysis"),
                _("The following subsystems don't have enough data and will be skipped:\n\n{names}").format(
                    names="\n".join(f"- {n}" for n in pending_names)
                ),
                parent=self.root,
            )
        self._analysis_window = LogAnalysisReportWindow(
            self.root,
            self.summary,
            self.vehicle_dir,
            is_fc_connected=self.is_fc_connected,
            upload_callback=self.upload_callback,
            report=self.report,
        )

    def _open_review_dialog(self, fixes: list[tuple[str, float, float, list[str]]]) -> None:
        dialog = tk.Toplevel(self.root)
        dialog.title(_("Review Parameter Changes"))
        dialog.geometry(self.calculate_scaled_geometry(520, 140 + 60 * len(fixes)))
        self.center_window(dialog, self.root)
        dialog.transient(self.root)
        dialog.grab_set()

        ttk.Label(dialog, text=_("The following parameter change(s) are proposed:"), font=("TkDefaultFont", 11, "bold")).pack(
            anchor=tk.W, padx=14, pady=(14, 6)
        )

        rows_frame = ttk.Frame(dialog)
        rows_frame.pack(fill=tk.BOTH, expand=True, padx=14, pady=(0, 6))

        for param_name, current, proposed, reasons in fixes:
            row = ttk.Frame(rows_frame)
            row.pack(fill=tk.X, pady=4)
            ttk.Label(row, text=param_name, width=18, font=("TkDefaultFont", 11, "bold")).pack(side=tk.LEFT)
            ttk.Label(row, text=_format_parameter_value(current), foreground="gray").pack(side=tk.LEFT, padx=(0, 6))
            ttk.Label(row, text="->").pack(side=tk.LEFT, padx=(0, 6))
            value_lbl = ttk.Label(
                row,
                text=_format_parameter_value(proposed),
                foreground="darkgreen",
                font=("TkDefaultFont", 11, "bold"),
            )
            value_lbl.pack(side=tk.LEFT)
            show_tooltip(value_lbl, "\n".join(f"- {r}" for r in reasons))

        button_row = ttk.Frame(dialog)
        button_row.pack(fill=tk.X, padx=14, pady=(6, 14))
        ttk.Button(button_row, text=_("Cancel"), command=dialog.destroy).pack(side=tk.RIGHT, padx=(6, 0))

        upload_button = ttk.Button(
            button_row,
            text=_("Apply & Upload"),
            command=partial(self._apply_param_fixes, fixes, dialog),
        )
        upload_button.configure(state="normal" if self.is_fc_connected else "disabled")
        upload_button.pack(side=tk.RIGHT)
        if not self.is_fc_connected:
            show_tooltip(upload_button, _("No flight controller connected, upload not available"))

    def _apply_param_fixes(self, fixes: list[tuple[str, float, float, list[str]]], dialog: tk.Toplevel) -> None:
        changes = {param_name: Par(proposed, "") for param_name, _current, proposed, _reasons in fixes}
        if self.upload_callback is not None:
            upload_result = self.upload_callback(changes)
            if upload_result is False:
                return

        self.summary.related_parameter_values.update({name: par.value for name, par in changes.items()})
        dialog.destroy()

    @staticmethod
    def _first_config_step(issues: list[QualityIssue]) -> str:
        for issue in issues:
            if issue.config_step:
                return issue.config_step
        return ""

    def _navigate_to_step(self, step: str) -> None:
        if self.navigate_callback is not None:
            self.navigate_callback(step)
        self._parent_root.deiconify()
        self._parent_root.lift()
        self._parent_root.focus_force()

    def _fixes_for_issues(self, issues: list[QualityIssue]) -> list[tuple[str, float, float, list[str]]]:
        """
        Compute proposed parameter changes for a specific set of issues.

        Returns (param_name, current_value, proposed_value, reasons) tuples.
        LOG_BITMASK entries within the given issues are OR-merged; every other
        parameter takes its first suggested value.
        """
        by_param: dict[str, list[QualityIssue]] = {}
        for issue in issues:
            if issue.param_name is not None and issue.suggested_value is not None:
                by_param.setdefault(issue.param_name, []).append(issue)

        fixes: list[tuple[str, float, float, list[str]]] = []
        for param_name, param_issues in by_param.items():
            current = self.summary.related_parameter_values.get(param_name)
            if current is None:
                continue

            if param_name == "LOG_BITMASK":
                proposed = int(current)
                for issue in param_issues:
                    proposed |= int(issue.suggested_value)  # type: ignore[arg-type]
                proposed_value = float(proposed)
            else:
                first_suggested = param_issues[0].suggested_value
                if first_suggested is None:
                    continue
                proposed_value = first_suggested

            if proposed_value != current:
                fixes.append((param_name, current, proposed_value, [i.message for i in param_issues]))

        return fixes

    def _build_stats_cards(self) -> None:
        card_container = ttk.Frame(self.main_frame)
        card_container.pack(side=tk.TOP, fill=tk.X, padx=12, pady=8)

        self._build_vehicle_card(card_container)
        self._build_log_overview_card(card_container)
        self._build_performance_card(card_container)

    def _build_vehicle_card(self, parent: ttk.Frame) -> None:
        hw = self.summary.hardware_report
        v = hw.vehicle if hw else None

        card = ttk.LabelFrame(parent, text=_("Vehicle & Firmware"))
        card.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 6))

        release = firmware_release_link(v)
        if release is not None:
            self._add_clickable_key_value(
                card,
                _("Firmware:"),
                f"{release.base_text} ({release.version_tag})",
                release.url,
            )
        else:
            self._add_key_value(card, _("Firmware:"), "-")

        fc = v.flight_controller if v and v.flight_controller else "-"
        board = hw.board_name if hw and hw.board_name else "-"
        self._add_key_value(card, _("FC:"), fc)
        self._add_key_value(card, _("Board:"), board)

    def _build_log_overview_card(self, parent: ttk.Frame) -> None:
        card = ttk.LabelFrame(parent, text=_("Log Overview"))
        card.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=6)

        self._add_key_value(card, _("Flight Time:"), self._fmt_duration(self.summary.flight_duration_sec))
        self._add_key_value(card, _("Log Size:"), self._fmt_filesize(self.summary.file_size_bytes))
        self._add_key_value(card, _("Total Msgs:"), str(self.summary.total_messages))

    def _build_performance_card(self, parent: ttk.Frame) -> None:
        card = ttk.LabelFrame(parent, text=_("System Performance"))
        card.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(6, 0))

        pm = self.summary.pm_status
        self._add_key_value(card, _("Avg CPU:"), f"{pm.average_cpu_load:.1f}%" if pm else "-")
        self._add_key_value(card, _("Peak CPU:"), f"{pm.peak_cpu_load:.1f}%" if pm else "-")
        self._add_key_value(card, _("Long Loops:"), str(pm.scheduler_long_loops) if pm else "-")

    def _build_tabs(self) -> None:
        style = ttk.Style()
        style.configure("TNotebook.Tab", font=("TkDefaultFont", 11))

        notebook = ttk.Notebook(self.main_frame)
        notebook.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=12, pady=(12, 12))

        quality_frame = ttk.Frame(notebook)
        notebook.add(quality_frame, text=_("  Quality Report  "))
        self._build_quality_tab(quality_frame)

        hardware_frame = ttk.Frame(notebook)
        notebook.add(hardware_frame, text=_("  Hardware Overview  "))
        build_hardware_tab(hardware_frame, self.summary.hardware_report)

    def _build_quality_tab(self, parent: ttk.Frame) -> None:  # pylint: disable=too-many-branches
        scroll_container = ScrollFrame(parent)
        scroll_container.pack(fill=tk.BOTH, expand=True)
        inner = scroll_container.view_port

        absorbed_by_step: dict[str, list[StepValidationResult]] = {}
        for step_result in self.summary.step_results:
            for q in self.summary.quality_results:
                if q.related_step and q.related_step == step_result.step:
                    absorbed_by_step.setdefault(q.related_step, []).append(step_result)
                    break

        absorbed_steps = set(absorbed_by_step)

        needs_attention: list[tuple[str, object]] = []
        passed_checks: list[tuple[str, object]] = []

        for q in self.summary.quality_results:
            (passed_checks if q.state == LogQualityState.INFO else needs_attention).append(("quality", q))
        for s in self.summary.step_results:
            if s.step in absorbed_steps:
                continue
            (passed_checks if s.valid else needs_attention).append(("step", s))

        if needs_attention:
            ttk.Label(inner, text=_("Requires Attention"), font=("TkDefaultFont", 14, "bold"), foreground="darkorange").pack(
                anchor=tk.W, padx=14, pady=(18, 6)
            )
            for kind, item in needs_attention:
                if kind == "quality":
                    quality_item = cast("LogQualityResult", item)
                    quality_absorbed_steps = absorbed_by_step.get(quality_item.related_step, [])
                    self._quality_result_card(inner, quality_item, quality_absorbed_steps)
                else:
                    self._step_result_card(inner, item)  # type: ignore[arg-type]
            ttk.Separator(inner, orient=tk.HORIZONTAL).pack(fill=tk.X, padx=14, pady=(14, 14))

        if passed_checks:
            ttk.Label(inner, text=_("Passed Checks"), font=("TkDefaultFont", 14, "bold"), foreground="darkgreen").pack(
                anchor=tk.W, padx=14, pady=(10, 6)
            )
            for kind, item in passed_checks:
                if kind == "quality":
                    quality_item = cast("LogQualityResult", item)
                    quality_absorbed_steps = absorbed_by_step.get(quality_item.related_step, [])
                    self._quality_result_card(inner, quality_item, quality_absorbed_steps)
                else:
                    self._step_result_card(inner, item)  # type: ignore[arg-type]

    def _quality_result_card(
        self, parent: ttk.Frame, result: LogQualityResult, absorbed_steps: list[StepValidationResult]
    ) -> None:
        card = ttk.Frame(parent)
        card.pack(fill=tk.X, padx=14, pady=6)

        text_frame = ttk.Frame(card)
        text_frame.pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Label(text_frame, text=result.name, font=("TkDefaultFont", 12, "bold")).pack(anchor=tk.W)
        reason_lbl = ttk.Label(text_frame, text=result.reason, foreground="gray", font=("TkDefaultFont", 11), wraplength=500)
        reason_lbl.pack(anchor=tk.W, fill=tk.X)
        text_frame.bind("<Configure>", partial(self._set_wraplength, reason_lbl))

        if result.issues:
            tooltip_lines = [f"- {i.message}" for i in result.issues]
            tooltip_lines += [f"- Also required for: {step_display_name(s.step)}" for s in absorbed_steps]
            tooltip = "\n".join(tooltip_lines)
            issue_lbl = ttk.Label(
                card, text=f"{len(result.issues)} Issue(s)", foreground="darkorange", font=("TkDefaultFont", 11, "bold")
            )
            issue_lbl.pack(side=tk.RIGHT, padx=14)
            show_tooltip(issue_lbl, tooltip)
            show_tooltip(card, tooltip)

            fixes = self._fixes_for_issues(result.issues)
            if fixes:
                fix_button = ttk.Button(card, text=_("Fix"), command=partial(self._open_review_dialog, fixes))
                fix_button.pack(side=tk.RIGHT, padx=(0, 8))

            step = result.related_step or self._first_config_step(result.issues)
            if step:
                step_button = ttk.Button(card, text=_("Go to Step"), command=partial(self._navigate_to_step, step))
                step_button.pack(side=tk.RIGHT, padx=(0, 8))
                show_tooltip(step_button, _("Jump to the {step} configuration step").format(step=step))

    def _step_result_card(self, parent: ttk.Frame, result: StepValidationResult) -> None:
        card = ttk.Frame(parent)
        card.pack(fill=tk.X, padx=14, pady=6)

        lbl = ttk.Label(card, text=step_display_name(result.step), font=("TkDefaultFont", 12), wraplength=500)
        lbl.pack(side=tk.LEFT, anchor=tk.W, fill=tk.X, expand=True)
        card.bind("<Configure>", partial(self._set_step_wraplength, lbl))
        if result.name:
            show_tooltip(lbl, result.name)

        if not result.valid:
            issues_lines = [i for mr in result.message_results.values() for i in mr.issues]
            step_button = ttk.Button(card, text=_("Go to Step"), command=partial(self._navigate_to_step, result.step))
            step_button.pack(side=tk.RIGHT, padx=(0, 8))
            if issues_lines:
                tooltip = "\n".join(f"- {i}" for i in issues_lines)
                show_tooltip(lbl, tooltip)
                show_tooltip(card, tooltip)

    def run(self) -> None:
        self.root.mainloop()
