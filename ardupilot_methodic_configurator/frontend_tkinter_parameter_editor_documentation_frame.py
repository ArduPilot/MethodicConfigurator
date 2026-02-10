"""
The documentation frame containing the documentation for the current configuration step.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import tkinter as tk
from platform import system as platform_system
from tkinter import ttk

from ardupilot_methodic_configurator import _
from ardupilot_methodic_configurator.backend_filesystem_program_settings import ProgramSettings
from ardupilot_methodic_configurator.backend_internet import webbrowser_open_url
from ardupilot_methodic_configurator.data_model_parameter_editor import ParameterEditor
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

    def __init__(self, root: tk.Widget, parameter_editor: ParameterEditor) -> None:
        self.root = root
        self.parameter_editor = parameter_editor
        self.documentation_frame: ttk.LabelFrame
        self.documentation_labels: dict[str, ttk.Label] = {}
        self.mandatory_level: ttk.Progressbar
        self.auto_open_var = tk.BooleanVar(value=bool(ProgramSettings.get_setting("auto_open_doc_in_browser")))
        self._create_documentation_frame()

    def _create_documentation_frame(self) -> None:
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
        self.refresh_documentation_labels()
        self.update_why_why_now_tooltip()

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

    def update_why_why_now_tooltip(self) -> None:
        tooltip_text = self.parameter_editor.get_why_why_now_tooltip()
        if tooltip_text:
            show_tooltip(self.documentation_frame, tooltip_text, position_below=False)

    def get_auto_open_documentation_in_browser(self) -> bool:
        return self.auto_open_var.get()

    def refresh_documentation_labels(self) -> None:
        frame_title = self.parameter_editor.get_documentation_frame_title()
        self.documentation_frame.config(text=frame_title)

        blog_text, blog_url = self.parameter_editor.get_documentation_text_and_url("blog")
        self._refresh_documentation_label(self.BLOG_LABEL, _(blog_text) if blog_text else "", blog_url)
        wiki_text, wiki_url = self.parameter_editor.get_documentation_text_and_url("wiki")
        self._refresh_documentation_label(self.WIKI_LABEL, _(wiki_text) if wiki_text else "", wiki_url)
        external_tool_text, external_tool_url = self.parameter_editor.get_documentation_text_and_url("external_tool")
        self._refresh_documentation_label(
            self.EXTERNAL_TOOL_LABEL, _(external_tool_text) if external_tool_text else "", external_tool_url
        )
        mandatory_text, _mandatory_url = self.parameter_editor.get_documentation_text_and_url("mandatory")
        self._refresh_mandatory_level(mandatory_text)

    def _refresh_documentation_label(self, label_key: str, text: str, url: str, url_expected: bool = True) -> None:
        label = self.documentation_labels[label_key]
        font_family, font_size = get_widget_font_family_and_size(label)
        if url:
            # Create a font with underline attribute
            underlined_font = (font_family, font_size, "underline")
            label.config(text=text, foreground="blue", cursor="hand2", font=underlined_font)
            label.bind("<Button-1>", lambda event: webbrowser_open_url(url))  # noqa: ARG005
            show_tooltip(label, url)
        else:
            # Use regular font without underline
            regular_font = (font_family, font_size)
            label.config(text=text, foreground="black", cursor="arrow", font=regular_font)
            label.bind("<Button-1>", lambda event: None)  # noqa: ARG005
            if url_expected:
                show_tooltip(label, _("Documentation URL not available"))

    def _refresh_mandatory_level(self, text: str) -> None:
        percentage, tooltip = self.parameter_editor.parse_mandatory_level_percentage(text)
        self.mandatory_level.config(value=percentage)
        show_tooltip(self.mandatory_level, tooltip)
