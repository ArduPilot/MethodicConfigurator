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
from tkinter import BooleanVar, ttk
from typing import Callable

from ardupilot_methodic_configurator import _
from ardupilot_methodic_configurator.backend_filesystem_program_settings import ProgramSettings
from ardupilot_methodic_configurator.frontend_tkinter_base_window import BaseWindow
from ardupilot_methodic_configurator.frontend_tkinter_rich_text import RichText


class PopupWindow:
    """
    Base class for creating and managing popup windows in the application.

    This class provides common functionality for popup windows including:
    - Window setup and positioning
    - "Show again" checkbox management
    - Window cleanup and parent re-enabling
    - Platform-specific behavior (Windows vs. other OS)
    """

    def __init__(self) -> None:
        pass

    @staticmethod
    def should_display(ptype: str) -> bool:
        """Check if the popup should be displayed based on user preferences."""
        return ProgramSettings.display_usage_popup(ptype)

    @staticmethod
    def setup_window(
        popup_window: BaseWindow,
        title: str,
        geometry: str,
        instructions_text: RichText,
    ) -> None:
        """Set up the basic window properties and add the instructions text."""
        popup_window.root.title(title)
        popup_window.root.geometry(geometry)
        instructions_text.config(borderwidth=0, relief="flat")
        instructions_text.pack(padx=6, pady=10)

    @staticmethod
    def add_show_again_checkbox(
        popup_window: BaseWindow,
        ptype: str,
    ) -> BooleanVar:
        """Add a 'Show this usage popup again' checkbox and return its variable."""
        show_again_var = BooleanVar()
        show_again_var.set(True)

        def update_show_again() -> None:
            ProgramSettings.set_display_usage_popup(ptype, show_again_var.get())

        show_again_checkbox = ttk.Checkbutton(
            popup_window.main_frame,
            text=_("Show this usage popup again"),
            variable=show_again_var,
            command=update_show_again,
        )
        show_again_checkbox.pack(pady=(10, 5))
        return show_again_var

    @staticmethod
    def finalize_window_setup(popup_window: BaseWindow, parent: tk.Tk, close_callback: Callable[[], None]) -> None:
        """Finalize window setup: center, make topmost, disable parent, set close handler."""
        BaseWindow.center_window(popup_window.root, parent)
        popup_window.root.deiconify()  # Show the window now that it's positioned
        popup_window.root.attributes("-topmost", True)  # noqa: FBT003
        popup_window.root.grab_set()  # Make the popup modal

        popup_window.root.protocol("WM_DELETE_WINDOW", close_callback)

    @staticmethod
    def close(popup_window: BaseWindow, parent: tk.Tk) -> None:
        """Close the popup window and re-enable the parent window."""
        popup_window.root.grab_release()  # Release the modal grab
        popup_window.root.destroy()
        parent.focus_set()
        parent.lift()


class UsagePopupWindow(PopupWindow):
    """
    A class for creating and managing usage popup windows with a Dismiss button.

    This class extends PopupWindow to provide informational popups with instructions
    and options to show them again or dismiss.
    """

    @staticmethod
    def display(  # pylint: disable=too-many-arguments, too-many-positional-arguments
        parent: tk.Tk,
        usage_popup_window: BaseWindow,
        title: str,
        ptype: str,
        geometry: str,
        instructions_text: RichText,
    ) -> None:
        """Display a usage popup with a Dismiss button."""
        # Hide the window until it's properly positioned
        usage_popup_window.root.withdraw()

        # Set up the window
        PopupWindow.setup_window(usage_popup_window, title, geometry, instructions_text)

        # Add show again checkbox
        PopupWindow.add_show_again_checkbox(usage_popup_window, ptype)

        # Add dismiss button
        dismiss_button = ttk.Button(
            usage_popup_window.main_frame,
            text=_("Dismiss"),
            command=lambda: PopupWindow.close(usage_popup_window, parent),
        )
        dismiss_button.pack(pady=10)

        # Finalize window setup
        PopupWindow.finalize_window_setup(usage_popup_window, parent, lambda: PopupWindow.close(usage_popup_window, parent))


class ConfirmationPopupWindow(PopupWindow):
    """
    A class for creating confirmation popup windows with Yes/No buttons.

    This class extends PopupWindow to provide confirmation dialogs that
    return a boolean result based on user's choice.
    """

    @staticmethod
    def display(  # pylint: disable=too-many-arguments, too-many-positional-arguments
        parent: tk.Tk,
        usage_popup_window: BaseWindow,
        title: str,
        ptype: str,
        geometry: str,
        instructions_text: RichText,
    ) -> bool:
        """
        Display a confirmation popup with Yes/No buttons.

        Args:
            parent: Parent Tk window
            usage_popup_window: BaseWindow instance for the popup
            title: Window title
            ptype: Type identifier for the popup (used for "show again" setting)
            geometry: Window geometry string (e.g., "600x220")
            instructions_text: RichText widget containing the confirmation message

        Returns:
            bool: True if user clicked Yes, False if user clicked No

        """
        # Hide the window until it's properly positioned
        usage_popup_window.root.withdraw()

        # Set up the window
        PopupWindow.setup_window(usage_popup_window, title, geometry, instructions_text)

        # Add show again checkbox
        PopupWindow.add_show_again_checkbox(usage_popup_window, ptype)

        # Create result dictionary to capture user's choice
        result = {"confirmed": False}

        # Create Yes/No buttons for confirmation dialogs
        button_frame = ttk.Frame(usage_popup_window.main_frame)
        button_frame.pack(pady=10)

        def on_yes() -> None:
            result["confirmed"] = True
            PopupWindow.close(usage_popup_window, parent)

        def on_no() -> None:
            result["confirmed"] = False
            PopupWindow.close(usage_popup_window, parent)

        yes_button = ttk.Button(button_frame, text=_("Yes"), command=on_yes, width=10)
        yes_button.pack(side=tk.LEFT, padx=5)

        no_button = ttk.Button(button_frame, text=_("No"), command=on_no, width=10)
        no_button.pack(side=tk.LEFT, padx=5)

        # Finalize window setup
        PopupWindow.finalize_window_setup(usage_popup_window, parent, lambda: PopupWindow.close(usage_popup_window, parent))

        # Wait for the window to be closed (modal behavior)
        parent.wait_window(usage_popup_window.root)

        return result["confirmed"]
