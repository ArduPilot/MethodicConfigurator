"""
The documentation frame containing the documentation for the current configuration step.

This file is part of Ardupilot methodic configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import tkinter as tk
from tkinter import ttk

# from logging import debug as logging_debug
# from logging import critical as logging_critical
from webbrowser import open as webbrowser_open  # to open the blog post documentation

from ardupilot_methodic_configurator import _
from ardupilot_methodic_configurator.backend_filesystem import LocalFilesystem
from ardupilot_methodic_configurator.backend_filesystem_program_settings import ProgramSettings
from ardupilot_methodic_configurator.frontend_tkinter_base import show_tooltip


class DocumentationFrame:  # pylint: disable=too-few-public-methods
    """
    A class to manage and display documentation within the GUI.

    This class is responsible for creating a frame that displays
    documentation links related to the current file being edited. It updates
    the documentation links based on the current file and provides
    functionality to open these links in a web browser.
    """

    def __init__(self, root: tk.Widget, local_filesystem: LocalFilesystem, current_file: str) -> None:
        self.root = root
        self.local_filesystem = local_filesystem
        self.current_file = current_file
        self.documentation_frame: ttk.LabelFrame
        self.documentation_labels: dict[str, ttk.Label] = {}
        self.auto_open_var = tk.BooleanVar(value=bool(ProgramSettings.get_setting("auto_open_doc_in_browser")))
        self.__create_documentation_frame()

    def __create_documentation_frame(self) -> None:
        self.documentation_frame = ttk.LabelFrame(self.root, text=_("Documentation"))
        self.documentation_frame.pack(side=tk.TOP, fill="x", expand=False, pady=(4, 4), padx=(4, 4))

        # Create a grid structure within the documentation_frame
        documentation_grid = ttk.Frame(self.documentation_frame)
        documentation_grid.pack(fill="both", expand=True)

        descriptive_texts = [_("Forum Blog:"), _("Wiki:"), _("External tool:"), _("Mandatory:")]
        descriptive_tooltips = [
            _("ArduPilot's forum Methodic configuration Blog post relevant for the current file"),
            _("ArduPilot's wiki page relevant for the current file"),
            _("External tool or documentation relevant for the current file"),
            _(
                "Mandatory level of the current file,\n 100% you MUST use this file to configure the "
                "vehicle,\n 0% you can ignore this file if it does not apply to your vehicle"
            ),
        ]
        for i, text in enumerate(descriptive_texts):
            # Create labels for the first column with static descriptive text
            label = ttk.Label(documentation_grid, text=text)
            label.grid(row=i, column=0, sticky="w")
            show_tooltip(label, descriptive_tooltips[i])

            if i == 3:
                bottom_frame = ttk.Frame(documentation_grid)
                bottom_frame.grid(row=i, column=1, sticky="ew")  # ew to stretch horizontally

                self.documentation_labels[text] = ttk.Label(bottom_frame)
                self.documentation_labels[text].pack(side=tk.LEFT, fill="x", expand=True)
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
            else:
                # Create labels for the second column with the documentation links
                self.documentation_labels[text] = ttk.Label(documentation_grid)
                self.documentation_labels[text].grid(row=i, column=1, sticky="ew")
        documentation_grid.columnconfigure(0, weight=0)
        documentation_grid.columnconfigure(1, weight=1)

        # Dynamically update the documentation text and URL links
        self.update_documentation_labels(self.current_file)

    def update_documentation_labels(self, current_file: str) -> None:
        self.current_file = current_file
        if current_file:
            title = _("{current_file} Documentation")
            frame_title = title.format(**locals())
        else:
            frame_title = _("Documentation")
        self.documentation_frame.config(text=frame_title)

        blog_text, blog_url = self.local_filesystem.get_documentation_text_and_url(current_file, "blog")
        self.__update_documentation_label(_("Forum Blog:"), blog_text, blog_url)
        wiki_text, wiki_url = self.local_filesystem.get_documentation_text_and_url(current_file, "wiki")
        self.__update_documentation_label(_("Wiki:"), wiki_text, wiki_url)
        external_tool_text, external_tool_url = self.local_filesystem.get_documentation_text_and_url(
            current_file, "external_tool"
        )
        self.__update_documentation_label(_("External tool:"), external_tool_text, external_tool_url)
        mandatory_text, mandatory_url = self.local_filesystem.get_documentation_text_and_url(current_file, "mandatory")
        self.__update_documentation_label(_("Mandatory:"), mandatory_text, mandatory_url, url_expected=False)

        if self.auto_open_var.get():
            if wiki_url:
                webbrowser_open(url=wiki_url, new=0, autoraise=False)
            if external_tool_url:
                webbrowser_open(url=external_tool_url, new=0, autoraise=False)
            if blog_url:
                webbrowser_open(url=blog_url, new=0, autoraise=True)

    def __update_documentation_label(self, label_key: str, text: str, url: str, url_expected: bool = True) -> None:
        label = self.documentation_labels[label_key]
        if url:
            label.config(text=text, foreground="blue", cursor="hand2", underline=True)
            label.bind("<Button-1>", lambda event: webbrowser_open(url))  # noqa: ARG005
            show_tooltip(label, url)
        else:
            label.config(text=text, foreground="black", cursor="arrow", underline=False)
            label.bind("<Button-1>", lambda event: None)  # noqa: ARG005
            if url_expected:
                show_tooltip(label, _("Documentation URL not available"))
