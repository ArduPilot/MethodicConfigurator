"""
Log analysis report window for the ArduPilot Methodic Configurator.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-FileCopyrightText: 2026 Omkar Sarkar <omkarsarkar24@gmail.com>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import tkinter as tk
from collections.abc import Callable
from enum import Enum
from functools import partial
from pathlib import Path
from tkinter import messagebox, ttk
from typing import Any

from ardupilot_methodic_configurator import _
from ardupilot_methodic_configurator.backend_internet import webbrowser_open_url
from ardupilot_methodic_configurator.data_model_par_dict import Par
from ardupilot_methodic_configurator.frontend_tkinter_autoresize_combobox import AutoResizeCombobox
from ardupilot_methodic_configurator.frontend_tkinter_base_window import BaseWindow
from ardupilot_methodic_configurator.frontend_tkinter_scroll_frame import ScrollFrame
from ardupilot_methodic_configurator.frontend_tkinter_show import show_tooltip
from ardupilot_methodic_configurator.frontend_tkinter_tuning_report import TuningReportWindow
from ardupilot_methodic_configurator.log_analysis.data_model_log_analysis import LogSummary
from ardupilot_methodic_configurator.log_analysis.data_model_log_analysis_result import LogAnalysis


class Severity(Enum):
    """Severity tiers shown only in the static legend key - not assigned to any finding yet."""

    SEVERE = "severe"
    NEEDS_ATTENTION = "needs_attention"
    INFORMATIONAL = "informational"


_SEVERITY_MARKER_COLOR = {
    Severity.SEVERE: "red3",
    Severity.NEEDS_ATTENTION: "dark orange",
    Severity.INFORMATIONAL: "gray50",
}

_SEVERITY_LABEL = {
    Severity.SEVERE: _("Severe"),
    Severity.NEEDS_ATTENTION: _("Needs attention"),
    Severity.INFORMATIONAL: _("Informational"),
}

_SEVERITY_TOOLTIP = {
    Severity.SEVERE: _("A serious issue that should be fixed before further flights"),
    Severity.NEEDS_ATTENTION: _("Worth reviewing, may or may not need action"),
    Severity.INFORMATIONAL: _("For your information only, no action expected"),
}


def _collect_links(quality_dict: dict[str, Any] | None, analysis_dict: dict[str, Any] | None) -> list[dict[str, Any]]:
    seen: set[tuple[str | None, str | None]] = set()
    links: list[dict[str, Any]] = []

    def _add(step_info: dict[str, Any] | None) -> None:
        if not step_info:
            return
        key = (step_info.get("wiki_url"), step_info.get("blog_url"))
        if key == (None, None) or key in seen:
            return
        seen.add(key)
        links.append(step_info)

    if quality_dict:
        for issue in quality_dict.get("issues", []):
            _add(issue.get("step_info"))
    if analysis_dict:
        for outcome in analysis_dict.get("outcomes", []):
            _add(outcome.get("step_info"))

    return links


def _format_component(component: dict[str, Any]) -> list[str]:  # pylint: disable=too-many-locals
    lines: list[str] = []

    product = component.get("Product", {})
    if isinstance(product, dict):
        manufacturer = str(product.get("Manufacturer") or "").strip()
        model = str(product.get("Model") or "").strip()
        name = " ".join(part for part in (manufacturer, model) if part)
        if name:
            lines.append(name)

    firmware = component.get("Firmware", {})
    if isinstance(firmware, dict):
        fw_type = str(firmware.get("Type") or "").strip()
        fw_version = str(firmware.get("Version") or "").strip()
        firmware_text = " ".join(part for part in (fw_type, fw_version) if part)
        if firmware_text:
            lines.append(_("Firmware: {text}").format(text=firmware_text))

    for key, value in component.items():
        if not isinstance(value, dict) or "Connection" not in key:
            continue
        conn_type = str(value.get("Type") or "").strip()
        conn_protocol = str(value.get("Protocol") or "").strip()
        conn_text = " / ".join(part for part in (conn_type, conn_protocol) if part)
        if conn_text:
            lines.append(f"{key}: {conn_text}")

    notes = str(component.get("Notes") or "").strip()
    if notes:
        lines.append(_("Notes: {notes}").format(notes=notes))

    return lines


class LogAnalysisReportWindow(BaseWindow):  # pylint: disable=too-many-instance-attributes
    """Log analysis window."""

    def __init__(  # pylint: disable=too-many-arguments, too-many-positional-arguments
        self,
        root_tk: tk.Tk | tk.Toplevel,
        summary: LogSummary,
        vehicle_dir: str,
        report: dict[str, Any] | None = None,
        is_fc_connected: bool = False,
        upload_callback: Callable[[dict[str, Par]], bool | None] | None = None,
    ) -> None:
        super().__init__(root_tk)
        self.summary = summary
        self.vehicle_dir = vehicle_dir
        self.report = report
        self.is_fc_connected = is_fc_connected
        self.upload_callback = upload_callback
        self._ai_panel_visible = False

        self.pairs = summary.paired_quality_and_analysis_results()
        self.subsystem_names = [q.name for q, _a in self.pairs]

        self._report_quality_by_name: dict[str, dict[str, Any]] = {}
        self._report_analysis_by_name: dict[str, dict[str, Any]] = {}
        if report is not None:
            for entry in report.get("data_quality", []):
                self._report_quality_by_name[entry.get("name", "")] = entry
            for entry in report.get("analysis", []):
                name = entry.get("name", "")
                self._report_analysis_by_name[name.removesuffix(" Analysis")] = entry

        self.root.title(_("Log Analysis"))
        self.root.geometry(self.calculate_scaled_geometry(1050, 800))
        self.center_window(self.root, root_tk)
        self.root.resizable(width=True, height=True)

        self._build_header()
        self._build_footer()

        self.scroll_container = ScrollFrame(self.main_frame)
        self.scroll_container.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=20, pady=(6, 14))
        self.body_frame = self.scroll_container.view_port

        if self.subsystem_names:
            self.selector.set(self.subsystem_names[0])
            self._render_subsystem(self.subsystem_names[0])

    def _build_header(self) -> None:
        header = ttk.Frame(self.main_frame)
        header.pack(side=tk.TOP, fill=tk.X, padx=20, pady=(16, 4))

        left_col = ttk.Frame(header)
        left_col.pack(side=tk.LEFT, anchor=tk.NW)

        ttk.Label(left_col, text=_("Log Analysis"), font=("TkDefaultFont", 16, "bold")).pack(anchor=tk.W)

        selector_row = ttk.Frame(left_col)
        selector_row.pack(anchor=tk.W, pady=(8, 0))
        ttk.Label(selector_row, text=_("Subsystem:"), font=("TkDefaultFont", 13, "bold")).pack(side=tk.LEFT, padx=(0, 8))
        self.selector = AutoResizeCombobox(
            selector_row,
            self.subsystem_names,
            self.subsystem_names[0] if self.subsystem_names else "",
            _("Select a subsystem to view its details"),
            state="readonly",
            width=30,
        )
        self.selector.pack(side=tk.LEFT)
        self.selector.bind("<<ComboboxSelected>>", lambda _event: self._render_subsystem(self.selector.get()))

        right_col = ttk.Frame(header)
        right_col.pack(side=tk.RIGHT, anchor=tk.NE)
        self._build_legend(right_col)

    def _build_legend(self, parent: ttk.Frame) -> None:
        legend_frame = ttk.LabelFrame(parent, text=_("Legend"))
        legend_frame.pack(side=tk.LEFT, anchor=tk.N, padx=(0, 20))
        show_tooltip(legend_frame, _("Severity of a finding"), position_below=False)

        for severity in Severity:
            row = ttk.Frame(legend_frame)
            row.pack(anchor=tk.W, padx=8, pady=2)
            marker = ttk.Label(row, text="\u25a0", font=("TkDefaultFont", 12), foreground=_SEVERITY_MARKER_COLOR[severity])
            marker.pack(side=tk.LEFT, padx=(0, 6))
            label = ttk.Label(row, text=_SEVERITY_LABEL[severity], font=("TkDefaultFont", 13))
            label.pack(side=tk.LEFT)
            show_tooltip(label, _SEVERITY_TOOLTIP[severity])
            show_tooltip(marker, _SEVERITY_TOOLTIP[severity])

    def _build_footer(self) -> None:
        footer = ttk.Frame(self.main_frame)
        footer.pack(side=tk.BOTTOM, fill=tk.X, padx=20, pady=(0, 14))

        # ai_button = ttk.Button(footer, text=_("Ask AI"), command=self._toggle_ai_panel)
        # ai_button.configure(state="normal" if self.report is not None else "disabled")
        # ai_button.pack(side=tk.RIGHT)
        # show_tooltip(
        #     ai_button,
        #     _("Ask an AI assistant grounded in this flight's log analysis")
        #     if self.report is not None
        #     else _("AI Help unavailable - report data was not provided"),
        # )

        tuning_report_path = Path(self.vehicle_dir) / "tuning_report.csv"
        tuning_button = ttk.Button(footer, text=_("Tuning Parameter Graph"), command=self._on_open_tuning_graph)
        tuning_button.configure(state="normal" if tuning_report_path.exists() else "disabled")
        tuning_button.pack(side=tk.RIGHT, padx=(0, 8))

    def _on_open_tuning_graph(self) -> None:
        tuning_report_path = Path(self.vehicle_dir) / "tuning_report.csv"
        try:
            TuningReportWindow(self.root, str(tuning_report_path))
        except (OSError, ValueError) as exc:
            messagebox.showerror(_("Tuning Graph Error"), str(exc), parent=self.root)

    def _render_subsystem(self, name: str) -> None:  # pylint: disable=too-many-locals, too-many-branches
        for widget in self.body_frame.winfo_children():
            widget.destroy()

        matching = [(q, a) for q, a in self.pairs if q.name == name]
        if not matching:
            return
        quality_result, analysis_result = matching[0]

        quality_dict = self._report_quality_by_name.get(name)
        analysis_dict = self._report_analysis_by_name.get(name)

        self._section_heading(_("Links"))
        links = _collect_links(quality_dict, analysis_dict)
        if not links:
            self._section_body(_("No linked documentation for this subsystem."))
        else:
            for link in links:
                if link.get("wiki_url"):
                    self._section_link(_("Wiki"), link.get("wiki_text") or link["wiki_url"], link["wiki_url"])
                if link.get("blog_url"):
                    self._section_link(_("Guide"), link.get("blog_text") or link["blog_url"], link["blog_url"])

        vehicle_components = (self.report or {}).get("vehicle_components") or {}
        component_keys = self.summary.component_keys_for_subsystem(quality_result.subsystem_key)
        hardware_lines: list[tuple[str, list[str]]] = []
        for key in component_keys:
            component = vehicle_components.get(key)
            if isinstance(component, dict):
                formatted = _format_component(component)
                if formatted:
                    hardware_lines.append((key, formatted))

        if hardware_lines:
            self._section_heading(_("Hardware & Connections"))
            for component_name, lines in hardware_lines:
                self._section_body(component_name, bold=True)
                for line in lines:
                    self._bullet_line(line)

        self._section_heading(_("Quality"))
        self._section_body(quality_result.reason)
        for issue in quality_result.issues:
            self._bullet_line(issue.message)

        self._section_heading(_("Analysis"))
        if analysis_result is None:
            self._section_body(_("Not yet analyzed - {reason}").format(reason=quality_result.reason))
        elif not analysis_result.outcomes:
            self._section_body(_("No findings."))
        else:
            for outcome in analysis_result.outcomes:
                self._outcome_line(outcome)

    def _section_heading(self, text: str) -> None:
        ttk.Label(self.body_frame, text=text, font=("TkDefaultFont", 16, "bold"), foreground="#333333").pack(
            anchor=tk.W, pady=(16, 6)
        )

    def _section_body(self, text: str, *, bold: bool = False) -> None:
        font = ("TkDefaultFont", 14, "bold") if bold else ("TkDefaultFont", 14)
        ttk.Label(self.body_frame, text=text, font=font, wraplength=950, justify=tk.LEFT).pack(anchor=tk.W, pady=2, fill=tk.X)

    def _bullet_line(self, text: str) -> None:
        row = ttk.Frame(self.body_frame)
        row.pack(anchor=tk.W, fill=tk.X, pady=2)

        ttk.Label(row, text="\u2022", font=("TkDefaultFont", 16), foreground="#666666").pack(
            side=tk.LEFT, padx=(10, 8), anchor=tk.N, pady=(0, 0)
        )
        ttk.Label(row, text=text, font=("TkDefaultFont", 14), wraplength=920, justify=tk.LEFT).pack(
            side=tk.LEFT, fill=tk.X, expand=True
        )

    def _outcome_line(self, outcome: LogAnalysis) -> None:
        timestamp_text = f" ({outcome.timestamp_us / 1e6:.1f}s)" if outcome.timestamp_us is not None else ""
        row = ttk.Frame(self.body_frame)
        row.pack(anchor=tk.W, padx=(10, 0), pady=3, fill=tk.X)
        ttk.Label(
            row,
            text=f"{outcome.message}{timestamp_text}",
            font=("TkDefaultFont", 14),
            wraplength=950,
            justify=tk.LEFT,
        ).pack(side=tk.LEFT, fill=tk.X, expand=True)

        fixes = self._fix_for_outcome(outcome)
        if fixes:
            fix_button = ttk.Button(row, text=_("Fix"), command=partial(self._open_review_dialog, fixes))
            fix_button.pack(side=tk.RIGHT, padx=(8, 0))

    def _fix_for_outcome(self, outcome: LogAnalysis) -> list[tuple[str, float, float, list[str]]]:
        if not isinstance(outcome.param_name, str) or not isinstance(outcome.suggested_value, (int, float)):
            return []
        current = self.summary.related_parameter_values.get(outcome.param_name)
        if current is None or float(outcome.suggested_value) == current:
            return []
        return [(outcome.param_name, current, float(outcome.suggested_value), [outcome.message])]

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
            ttk.Label(row, text=str(current), foreground="gray").pack(side=tk.LEFT, padx=(0, 6))
            ttk.Label(row, text="->").pack(side=tk.LEFT, padx=(0, 6))
            value_lbl = ttk.Label(row, text=str(proposed), foreground="darkgreen", font=("TkDefaultFont", 11, "bold"))
            value_lbl.pack(side=tk.LEFT)
            show_tooltip(value_lbl, "\n".join(f"- {reason}" for reason in reasons))

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

    def _section_link(self, tag: str, text: str, url: str) -> None:
        row = ttk.Frame(self.body_frame)
        row.pack(anchor=tk.W, pady=3, padx=(10, 0))
        ttk.Label(row, text=f"[{tag}]", font=("TkDefaultFont", 13, "bold"), foreground="#777777").pack(
            side=tk.LEFT, padx=(0, 6)
        )
        link = ttk.Label(row, text=text, font=("TkDefaultFont", 14), foreground="#0055cc", cursor="hand2")
        link.pack(side=tk.LEFT)
        link.bind("<Button-1>", lambda _event: webbrowser_open_url(url))

    def run(self) -> None:
        self.root.mainloop()
