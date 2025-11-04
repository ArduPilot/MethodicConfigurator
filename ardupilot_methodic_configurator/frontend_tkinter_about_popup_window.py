"""
Display the about popup window.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2025 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import tkinter as tk

# from logging import debug as logging_debug
from tkinter import ttk

# from logging import critical as logging_critical
from webbrowser import open as webbrowser_open  # to open the blog post documentation

from ardupilot_methodic_configurator import _
from ardupilot_methodic_configurator.backend_filesystem_program_settings import ProgramSettings
from ardupilot_methodic_configurator.frontend_tkinter_base_window import (
    BaseWindow,
)


def show_about_window(root: ttk.Frame, _version: str) -> None:  # pylint: disable=too-many-locals
    # Create a new window for the custom "About" message
    about_window = tk.Toplevel(root)
    about_window.title(_("About"))
    about_window.geometry("650x340")

    main_frame = ttk.Frame(about_window)
    main_frame.pack(expand=True, fill=tk.BOTH)

    # Add the "About" message
    about_message = _(
        "ArduPilot Methodic Configurator Version: {_version}\n\n"
        "A clear configuration sequence for ArduPilot vehicles.\n\n"
        "Copyright © 2024-2025 Amilcar do Carmo Lucas and ArduPilot.org\n\n"
        "Licensed under the GNU General Public License v3.0"
    )
    about_label = ttk.Label(main_frame, text=about_message.format(**locals()), wraplength=450)
    about_label.grid(column=0, row=0, padx=10, pady=10, columnspan=5)  # Span across all columns

    usage_popup_frame = ttk.Frame(main_frame)
    usage_popup_frame.grid(column=0, row=1, columnspan=5, padx=10, pady=10)

    usage_popup_label = ttk.Label(usage_popup_frame, text=_("Display usage popup"))
    usage_popup_label.pack(side=tk.TOP, anchor=tk.W)

    component_editor_var = tk.BooleanVar(value=ProgramSettings.display_usage_popup("component_editor"))
    component_editor_checkbox = ttk.Checkbutton(
        usage_popup_frame,
        text=_("Component editor window introduction"),
        variable=component_editor_var,
        command=lambda: ProgramSettings.set_display_usage_popup("component_editor", component_editor_var.get()),
    )
    component_editor_checkbox.pack(side=tk.TOP, anchor=tk.W)

    component_editor_validation_var = tk.BooleanVar(value=ProgramSettings.display_usage_popup("component_editor_validation"))
    component_editor_validation_checkbox = ttk.Checkbutton(
        usage_popup_frame,
        text=_("Component editor window data validation"),
        variable=component_editor_validation_var,
        command=lambda: ProgramSettings.set_display_usage_popup(
            "component_editor_validation", component_editor_validation_var.get()
        ),
    )
    component_editor_validation_checkbox.pack(side=tk.TOP, anchor=tk.W)

    parameter_editor_var = tk.BooleanVar(value=ProgramSettings.display_usage_popup("parameter_editor"))
    parameter_editor_checkbox = ttk.Checkbutton(
        usage_popup_frame,
        text=_("Parameter file editor and uploader window"),
        variable=parameter_editor_var,
        command=lambda: ProgramSettings.set_display_usage_popup("parameter_editor", parameter_editor_var.get()),
    )
    parameter_editor_checkbox.pack(side=tk.TOP, anchor=tk.W)

    # Create buttons for each action
    user_manual_button = ttk.Button(
        main_frame,
        text=_("User Manual"),
        command=lambda: webbrowser_open("https://github.com/ArduPilot/MethodicConfigurator/blob/master/USERMANUAL.md"),
    )
    support_forum_button = ttk.Button(
        main_frame,
        text=_("Support Forum"),
        command=lambda: webbrowser_open("http://discuss.ardupilot.org/t/new-ardupilot-methodic-configurator-gui/115038/1"),
    )
    report_bug_button = ttk.Button(
        main_frame,
        text=_("Report a Bug"),
        command=lambda: webbrowser_open("https://github.com/ArduPilot/MethodicConfigurator/issues/new/choose"),
    )
    licenses_button = ttk.Button(
        main_frame,
        text=_("Licenses"),
        command=lambda: webbrowser_open("https://github.com/ArduPilot/MethodicConfigurator/blob/master/credits/CREDITS.md"),
    )
    source_button = ttk.Button(
        main_frame, text=_("Source Code"), command=lambda: webbrowser_open("https://github.com/ArduPilot/MethodicConfigurator")
    )

    # Place buttons using grid for equal spacing and better control over layout
    user_manual_button.grid(column=0, row=2, padx=10, pady=10)
    support_forum_button.grid(column=1, row=2, padx=10, pady=10)
    report_bug_button.grid(column=2, row=2, padx=10, pady=10)
    licenses_button.grid(column=3, row=2, padx=10, pady=10)
    source_button.grid(column=4, row=2, padx=10, pady=10)

    # Configure the grid to ensure equal spacing and expansion
    main_frame.columnconfigure([0, 1, 2, 3, 4], weight=1)

    # Center the about window on its parent
    BaseWindow.center_window(about_window, root.winfo_toplevel())
