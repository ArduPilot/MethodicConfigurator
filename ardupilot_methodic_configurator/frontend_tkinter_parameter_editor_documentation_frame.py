"""
The documentation frame containing the documentation for the current configuration step.

This file is part of Ardupilot methodic configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2025 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import tkinter as tk
from platform import system as platform_system
from tkinter import ttk
from webbrowser import open as webbrowser_open  # to open the blog post documentation

from ardupilot_methodic_configurator import _
from ardupilot_methodic_configurator.backend_filesystem import LocalFilesystem
from ardupilot_methodic_configurator.backend_filesystem_program_settings import ProgramSettings
from ardupilot_methodic_configurator.frontend_tkinter_rich_text import get_widget_font_family_and_size
from ardupilot_methodic_configurator.frontend_tkinter_show import show_tooltip


class DocumentationFrame:
    """
    A class to manage and display documentation within the GUI.

    This class is responsible for creating a frame that displays
    documentation links related to the current file being edited. It updates
    the documentation links based on the current file and provides
    functionality to open these links in a web browser.
    """

    BLOG_LABEL = _("💬 Forum Blog:") if platform_system() == "Windows" else _("Forum Blog:")
    WIKI_LABEL = _("📖 Wiki:") if platform_system() == "Windows" else _("Wiki:")
    EXTERNAL_TOOL_LABEL = _("🔧 External tool:") if platform_system() == "Windows" else _("External tool:")
    MANDATORY_LABEL = _("❗ Mandatory:") if platform_system() == "Windows" else _("Mandatory:")

    DOCUMENTATION_SECTIONS = (
        (BLOG_LABEL, _("ArduPilot's forum Methodic configuration Blog post relevant for the current file")),
        (WIKI_LABEL, _("ArduPilot's wiki page relevant for the current file")),
        (EXTERNAL_TOOL_LABEL, _("External tool or documentation relevant for the current file")),
        (
            MANDATORY_LABEL,
            _(
                "Mandatory level of the current file,\n"
                "100% you MUST use this file to configure the vehicle,\n"
                "0% you can ignore this file if it does not apply to your vehicle"
            ),
        ),
    )

    def __init__(self, root: tk.Widget, local_filesystem: LocalFilesystem, current_file: str) -> None:
        self.root = root
        self.local_filesystem = local_filesystem
        self.documentation_frame: ttk.LabelFrame
        self.documentation_labels: dict[str, ttk.Label] = {}
        self.mandatory_level: ttk.Progressbar
        self.auto_open_var = tk.BooleanVar(value=bool(ProgramSettings.get_setting("auto_open_doc_in_browser")))
        self._create_documentation_frame(current_file)

    def _create_documentation_frame(self, current_file: str) -> None:
        self.documentation_frame = ttk.LabelFrame(self.root, text=_("Documentation"))

        # Create a grid structure within the documentation_frame
        documentation_grid = ttk.Frame(self.documentation_frame)
        documentation_grid.pack(fill="both", expand=True)

        for row, (text, tooltip) in enumerate(self.DOCUMENTATION_SECTIONS):
            if row == 3 and ProgramSettings.get_setting("gui_complexity") == "simple":
                # Skip the mandatory level row in simple mode
                self.mandatory_level = ttk.Progressbar(documentation_grid, length=100, mode="determinate")
                continue

            # Create labels for the first column with static descriptive text
            label = ttk.Label(documentation_grid, text=text)
            label.grid(row=row, column=0, sticky="w")
            show_tooltip(label, tooltip)

            if row == 3:
                self._create_bottom_row(documentation_grid, row)
            else:
                # Create labels for the second column with the documentation links
                self.documentation_labels[text] = ttk.Label(documentation_grid)
                self.documentation_labels[text].grid(row=row, column=1, sticky="ew")
        documentation_grid.columnconfigure(0, weight=0)
        documentation_grid.columnconfigure(1, weight=1)

        # Dynamically update the documentation text and URL links
        self.refresh_documentation_labels(current_file)
        self.update_why_why_now_tooltip(current_file)

    def _create_bottom_row(self, documentation_grid: ttk.Frame, row: int) -> None:
        bottom_frame = ttk.Frame(documentation_grid)
        bottom_frame.grid(row=row, column=1, sticky="ew")  # ew to stretch horizontally

        self.mandatory_level = ttk.Progressbar(bottom_frame, length=100, mode="determinate")
        self.mandatory_level.pack(side=tk.LEFT, fill="x", expand=True, padx=(0, 100))

        auto_open_checkbox = ttk.Checkbutton(
            bottom_frame,
            text=_("Automatically open documentation links in browser"),
            variable=self.auto_open_var,
            command=lambda: ProgramSettings.set_setting("auto_open_doc_in_browser", self.auto_open_var.get()),
        )
        show_tooltip(
            auto_open_checkbox,
            _(
                "Automatically open all the above documentation links in a browser\n"
                "whenever the current intermediate parameter file changes"
            ),
        )
        auto_open_checkbox.pack(side=tk.LEFT, expand=False)

    def update_why_why_now_tooltip(self, current_file: str) -> None:
        why_tooltip_text = self.local_filesystem.get_seq_tooltip_text(current_file, "why")
        why_now_tooltip_text = self.local_filesystem.get_seq_tooltip_text(current_file, "why_now")
        tooltip_text = ""
        if why_tooltip_text:
            tooltip_text += _("Why: ") + _(why_tooltip_text) + "\n"
        if why_now_tooltip_text:
            tooltip_text += _("Why now: ") + _(why_now_tooltip_text)
        if tooltip_text:
            show_tooltip(self.documentation_frame, tooltip_text, position_below=False)

    def open_documentation_in_browser(self, current_file: str) -> None:
        _blog_text, blog_url = self.local_filesystem.get_documentation_text_and_url(current_file, "blog")
        _wiki_text, wiki_url = self.local_filesystem.get_documentation_text_and_url(current_file, "wiki")
        _external_tool_text, external_tool_url = self.local_filesystem.get_documentation_text_and_url(
            current_file, "external_tool"
        )

        if self.auto_open_var.get() or ProgramSettings.get_setting("gui_complexity") == "simple":
            if wiki_url:
                webbrowser_open(url=wiki_url, new=0, autoraise=False)
            if external_tool_url:
                webbrowser_open(url=external_tool_url, new=0, autoraise=False)
            if blog_url:
                webbrowser_open(url=blog_url, new=0, autoraise=True)

    def refresh_documentation_labels(self, current_file: str) -> None:
        if current_file:
            title = _("{current_file} Documentation")
            frame_title = title.format(**locals())
        else:
            frame_title = _("Documentation")
        self.documentation_frame.config(text=frame_title)

        blog_text, blog_url = self.local_filesystem.get_documentation_text_and_url(current_file, "blog")
        self._refresh_documentation_label(self.BLOG_LABEL, _(blog_text) if blog_text else "", blog_url)
        wiki_text, wiki_url = self.local_filesystem.get_documentation_text_and_url(current_file, "wiki")
        self._refresh_documentation_label(self.WIKI_LABEL, _(wiki_text) if wiki_text else "", wiki_url)
        external_tool_text, external_tool_url = self.local_filesystem.get_documentation_text_and_url(
            current_file, "external_tool"
        )
        self._refresh_documentation_label(
            self.EXTERNAL_TOOL_LABEL, _(external_tool_text) if external_tool_text else "", external_tool_url
        )
        mandatory_text, _mandatory_url = self.local_filesystem.get_documentation_text_and_url(current_file, "mandatory")
        self._refresh_mandatory_level(current_file, mandatory_text)

    def _refresh_documentation_label(self, label_key: str, text: str, url: str, url_expected: bool = True) -> None:
        label = self.documentation_labels[label_key]
        font_family, font_size = get_widget_font_family_and_size(label)
        if url:
            # Create a font with underline attribute
            underlined_font = (font_family, font_size, "underline")
            label.config(text=text, foreground="blue", cursor="hand2", font=underlined_font)
            label.bind("<Button-1>", lambda event: webbrowser_open(url))  # noqa: ARG005
            show_tooltip(label, url)
        else:
            # Use regular font without underline
            regular_font = (font_family, font_size)
            label.config(text=text, foreground="black", cursor="arrow", font=regular_font)
            label.bind("<Button-1>", lambda event: None)  # noqa: ARG005
            if url_expected:
                show_tooltip(label, _("Documentation URL not available"))

    def _refresh_mandatory_level(self, current_file: str, text: str) -> None:
        _used_indirectly_by_the_tooltip = current_file
        try:
            # Extract up to 3 digits from the start of the mandatory text
            percentage = int("".join([c for c in text[:3] if c.isdigit()]))
            if 0 <= percentage <= 100:
                self.mandatory_level.config(value=percentage)
                tooltip = _("This configuration step ({current_file} intermediate parameter file) is {percentage}% mandatory")
            else:
                raise ValueError
        except ValueError:
            self.mandatory_level.config(value=0)
            tooltip = _("Mandatory level not available for this configuration step ({current_file})")
        show_tooltip(self.mandatory_level, tooltip.format(**locals()))
