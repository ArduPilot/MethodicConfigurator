"""
A reusable usage popup window.

This file is part of Ardupilot methodic configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2025 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

# https://wiki.tcl-lang.org/page/Changing+Widget+Colors

import tkinter as tk

# from logging import debug as logging_debug
# from logging import info as logging_info
from platform import system as platform_system
from tkinter import BooleanVar, ttk

from ardupilot_methodic_configurator import _
from ardupilot_methodic_configurator.backend_filesystem_program_settings import ProgramSettings
from ardupilot_methodic_configurator.frontend_tkinter_base_window import BaseWindow
from ardupilot_methodic_configurator.frontend_tkinter_rich_text import RichText


class UsagePopupWindow:
    """
    A class for creating and managing usage popup windows in the application.

    This class extends the BaseWindow class to provide functionality for displaying
    usage popups with instructions and options to show them again or dismiss.
    """

    def __init__(self) -> None:
        pass

    @staticmethod
    def should_display(ptype: str) -> bool:
        return ProgramSettings.display_usage_popup(ptype)

    @staticmethod
    def display(  # pylint: disable=too-many-arguments, too-many-positional-arguments
        parent: tk.Tk,
        usage_popup_window: BaseWindow,
        title: str,
        ptype: str,
        geometry: str,
        instructions_text: RichText,
    ) -> None:
        usage_popup_window.root.title(title)
        usage_popup_window.root.geometry(geometry)

        instructions_text.pack(padx=6, pady=10)

        show_again_var = BooleanVar()
        show_again_var.set(True)

        def update_show_again() -> None:
            ProgramSettings.set_display_usage_popup(ptype, show_again_var.get())

        show_again_checkbox = ttk.Checkbutton(
            usage_popup_window.main_frame,
            text=_("Show this usage popup again"),
            variable=show_again_var,
            command=update_show_again,
        )
        show_again_checkbox.pack(pady=(10, 5))

        dismiss_button = ttk.Button(
            usage_popup_window.main_frame,
            text=_("Dismiss"),
            command=lambda: UsagePopupWindow.close(usage_popup_window, parent),
        )
        dismiss_button.pack(pady=10)

        BaseWindow.center_window(usage_popup_window.root, parent)
        usage_popup_window.root.attributes("-topmost", True)  # noqa: FBT003

        if platform_system() == "Windows":
            parent.attributes("-disabled", True)  # noqa: FBT003  # Disable parent window input

        usage_popup_window.root.protocol("WM_DELETE_WINDOW", lambda: UsagePopupWindow.close(usage_popup_window, parent))

    @staticmethod
    def close(usage_popup_window: BaseWindow, parent: tk.Tk) -> None:
        usage_popup_window.root.destroy()
        if platform_system() == "Windows":
            parent.attributes("-disabled", False)  # noqa: FBT003  # Re-enable the parent window
        parent.focus_set()
