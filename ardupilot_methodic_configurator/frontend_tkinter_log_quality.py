"""
Log quality report window for the ArduPilot Methodic Configurator.

Displays a parsed ArduPilot .bin log analysis.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import tkinter as tk
from tkinter import ttk

from ardupilot_methodic_configurator import _
from ardupilot_methodic_configurator.backend_internet import webbrowser_open_url
from ardupilot_methodic_configurator.formatting import format_filesize
from ardupilot_methodic_configurator.frontend_tkinter_base_window import BaseWindow
from ardupilot_methodic_configurator.frontend_tkinter_log_hardware_quality import build_hardware_tab
from ardupilot_methodic_configurator.frontend_tkinter_scroll_frame import ScrollFrame
from ardupilot_methodic_configurator.frontend_tkinter_show import show_tooltip
from ardupilot_methodic_configurator.log_analysis.data_model_log_analysis import LogSummary
from ardupilot_methodic_configurator.log_analysis.data_model_log_quality import (
    LogQualityResult,
    LogQualityState,
    StepValidationResult,
)
from ardupilot_methodic_configurator.log_analysis.data_model_log_report import (
    build_report_status,
    firmware_release_link,
    format_duration,
    step_display_name,
)


class LogQualityReportWindow(BaseWindow):
    """Displays log analysis results as a beginner-friendly, detailed dashboard."""

    # pylint: disable=duplicate-code
    def __init__(self, root_tk: tk.Tk | tk.Toplevel, summary: LogSummary) -> None:
        super().__init__(root_tk)
        self.summary = summary
        self.root.title(_("Log Quality Report"))
        self.root.geometry(self.calculate_scaled_geometry(1000, 750))
        self.center_window(self.root, root_tk)
        self.root.resizable(width=True, height=True)

        self._build_header_summary()
        self._build_stats_cards()
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
        link.bind("<Button-1>", lambda _e, u=url: webbrowser_open_url(u))
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

    # ------------------------------------------------------------------ tabs

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

    def _build_quality_tab(self, parent: ttk.Frame) -> None:
        scroll_container = ScrollFrame(parent)
        scroll_container.pack(fill=tk.BOTH, expand=True)
        inner = scroll_container.view_port

        needs_attention: list[tuple[str, object]] = []
        passed_checks: list[tuple[str, object]] = []

        for q in self.summary.quality_results:
            (passed_checks if q.state == LogQualityState.INFO else needs_attention).append(("quality", q))
        for s in self.summary.step_results:
            (passed_checks if s.valid else needs_attention).append(("step", s))

        if needs_attention:
            ttk.Label(inner, text=_("Requires Attention"), font=("TkDefaultFont", 14, "bold"), foreground="darkorange").pack(
                anchor=tk.W, padx=14, pady=(18, 6)
            )
            for kind, item in needs_attention:
                if kind == "quality":
                    self._quality_result_card(inner, item)  # type: ignore[arg-type]
                else:
                    self._step_result_card(inner, item)  # type: ignore[arg-type]
            ttk.Separator(inner, orient=tk.HORIZONTAL).pack(fill=tk.X, padx=14, pady=(14, 14))

        if passed_checks:
            ttk.Label(inner, text=_("Passed Checks"), font=("TkDefaultFont", 14, "bold"), foreground="darkgreen").pack(
                anchor=tk.W, padx=14, pady=(10, 6)
            )
            for kind, item in passed_checks:
                if kind == "quality":
                    self._quality_result_card(inner, item)  # type: ignore[arg-type]
                else:
                    self._step_result_card(inner, item)  # type: ignore[arg-type]

    def _quality_result_card(self, parent: ttk.Frame, result: LogQualityResult) -> None:
        card = ttk.Frame(parent)
        card.pack(fill=tk.X, padx=14, pady=6)

        tag = "OK" if result.state == LogQualityState.INFO else "WARN"
        color = "darkgreen" if result.state == LogQualityState.INFO else "red3"

        icon_lbl = ttk.Label(card, text=tag, foreground=color, font=("TkDefaultFont", 12, "bold"), width=8)
        icon_lbl.pack(side=tk.LEFT)

        text_frame = ttk.Frame(card)
        text_frame.pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Label(text_frame, text=result.name, font=("TkDefaultFont", 12, "bold")).pack(anchor=tk.W)
        reason_lbl = ttk.Label(text_frame, text=result.reason, foreground="gray", font=("TkDefaultFont", 11), wraplength=500)
        reason_lbl.pack(anchor=tk.W, fill=tk.X)
        text_frame.bind(
            "<Configure>",
            lambda e, l=reason_lbl: l.configure(wraplength=max(10, e.width - 15)),  # noqa: E741
        )

        if result.issues:
            tooltip = "\n".join(f"- {i.message}" for i in result.issues)
            issue_lbl = ttk.Label(
                card, text=f"{len(result.issues)} Issue(s)", foreground="darkorange", font=("TkDefaultFont", 11, "bold")
            )
            issue_lbl.pack(side=tk.RIGHT, padx=14)
            show_tooltip(issue_lbl, tooltip)
            show_tooltip(icon_lbl, tooltip)
            show_tooltip(card, tooltip)

    def _step_result_card(self, parent: ttk.Frame, result: StepValidationResult) -> None:
        card = ttk.Frame(parent)
        card.pack(fill=tk.X, padx=14, pady=6)

        tag = "PASS" if result.valid else "FAIL"
        color = "darkgreen" if result.valid else "darkorange"

        icon_lbl = ttk.Label(card, text=tag, foreground=color, font=("TkDefaultFont", 12, "bold"), width=8)
        icon_lbl.pack(side=tk.LEFT)

        lbl = ttk.Label(card, text=step_display_name(result.step), font=("TkDefaultFont", 12), wraplength=500)
        lbl.pack(side=tk.LEFT, anchor=tk.W, fill=tk.X, expand=True)
        card.bind("<Configure>", lambda e, l=lbl: l.configure(wraplength=max(10, e.width - 90)))  # noqa: E741
        if result.name:
            show_tooltip(lbl, result.name)

        if not result.valid:
            issues_lines = [i for mr in result.message_results.values() for i in mr.issues]
            if issues_lines:
                tooltip = "\n".join(f"- {i}" for i in issues_lines)
                show_tooltip(icon_lbl, tooltip)
                show_tooltip(lbl, tooltip)
                show_tooltip(card, tooltip)

    def run(self) -> None:
        self.root.mainloop()
