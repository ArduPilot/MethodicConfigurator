"""
TKinter base classes reused in multiple parts of the code.

This file is part of Ardupilot methodic configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2025 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

# https://wiki.tcl-lang.org/page/Changing+Widget+Colors

import tkinter as tk
from platform import system as platform_system
from tkinter import messagebox, ttk

from ardupilot_methodic_configurator import _


def show_error_message(title: str, message: str) -> None:
    root = tk.Tk()
    # Set the theme to 'alt'
    style = ttk.Style()
    style.theme_use("alt")
    root.withdraw()  # Hide the main window
    messagebox.showerror(title, message)
    root.destroy()


def show_no_param_files_error(_dirname: str) -> None:
    error_message = _(
        "No intermediate parameter files found in the selected '{_dirname}' vehicle directory.\n"
        "Please select and step inside a vehicle directory containing valid ArduPilot intermediate parameter files.\n\n"
        "Make sure to step inside the directory (double-click) and not just select it."
    )
    show_error_message(_("No Parameter Files Found"), error_message.format(**locals()))


def show_no_connection_error(_error_string: str) -> None:
    error_message = _("{_error_string}\n\nPlease connect a flight controller to the PC,\nwait at least 7 seconds and retry.")
    show_error_message(_("No Connection to the Flight Controller"), error_message.format(**locals()))


def show_tooltip(widget: tk.Widget, text: str, position_below: bool = True) -> None:
    def enter(_event: tk.Event) -> None:
        # Calculate the position of the tooltip based on the widget's position
        x = widget.winfo_rootx() + min(widget.winfo_width() // 2, 100)
        y = widget.winfo_rooty() + (widget.winfo_height() if position_below else -10)
        tooltip.geometry(f"+{x}+{y}")
        tooltip.deiconify()

    def leave(_event: tk.Event) -> None:
        tooltip.withdraw()

    tooltip = tk.Toplevel(widget)
    if platform_system() == "Darwin":  # macOS
        try:
            tooltip.tk.call(
                "::tk::unsupported::MacWindowStyle",
                "style",
                tooltip._w,  # type: ignore[attr-defined] # noqa: SLF001 # pylint: disable=protected-access
                "help",
                "noActivates",
            )
            tooltip.configure(bg="#ffffe0")
        except AttributeError:  # Catches protected member access error
            tooltip.wm_attributes("-alpha", 1.0)  # Ensure opacity
            tooltip.wm_attributes("-topmost", True)  # Keep on top # noqa: FBT003
            tooltip.configure(bg="#ffffe0")
    else:
        tooltip.wm_overrideredirect(boolean=True)
    tooltip_label = ttk.Label(tooltip, text=text, background="#ffffe0", relief="solid", borderwidth=1, justify=tk.LEFT)
    tooltip_label.pack()
    tooltip.withdraw()  # Initially hide the tooltip

    # Bind the <Enter> and <Leave> events to show and hide the tooltip
    widget.bind("<Enter>", enter)
    widget.bind("<Leave>", leave)
