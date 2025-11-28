"""
TKinter base classes reused in multiple parts of the code.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2025 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

# https://wiki.tcl-lang.org/page/Changing+Widget+Colors

import tkinter as tk
from platform import system as platform_system
from tkinter import messagebox, ttk
from typing import Optional, cast

from ardupilot_methodic_configurator import _


def show_error_message(title: str, message: str, root: Optional[tk.Tk] = None) -> None:
    if root is None:
        root = tk.Tk(className="ArduPilotMethodicConfigurator")
        # Set the theme to 'alt'
        style = ttk.Style()
        style.theme_use("alt")
        root.withdraw()  # Hide the main window
        messagebox.showerror(title, message)
        root.destroy()
    else:
        messagebox.showerror(title, message)


def show_warning_message(title: str, message: str, root: Optional[tk.Tk] = None) -> None:
    if root is None:
        root = tk.Tk(className="ArduPilotMethodicConfigurator")
        # Set the theme to 'alt'
        style = ttk.Style()
        style.theme_use("alt")
        root.withdraw()  # Hide the main window
        messagebox.showwarning(title, message)
        root.destroy()
    else:
        messagebox.showwarning(title, message)


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


def calculate_tooltip_position(  # noqa: PLR0913
    widget_x: int,
    widget_y: int,
    widget_width: int,
    widget_height: int,
    tooltip_width: int,
    tooltip_height: int,
    parent_x: int,
    parent_y: int,
    parent_width: int,
    parent_height: int,
    position_below: bool,
) -> tuple[int, int]:
    """Calculate the position of the tooltip to ensure it fits inside the parent window."""
    x = widget_x + min(widget_width // 2, 100)
    y = widget_y + (widget_height if position_below else -10)

    # Adjust x position to keep tooltip inside parent window
    if x + tooltip_width > parent_x + parent_width:
        x = parent_x + parent_width - tooltip_width
    x = max(x, parent_x)

    # Adjust y position to keep tooltip inside parent window
    if y + tooltip_height > parent_y + parent_height:
        y = parent_y + parent_height - tooltip_height
    y = max(y, parent_y)

    return x, y


class Tooltip:
    """
    A tooltip class for displaying tooltips on widgets.

    Creates a tooltip that appears when the mouse hovers over a widget and disappears when the mouse leaves the widget.
    """

    def __init__(
        self,
        widget: tk.Widget,
        text: str,
        position_below: bool = True,
        tag_name: str = "",
        toplevel_class: Optional[type] = None,
    ) -> None:
        self.widget: tk.Widget = widget
        self.text: str = text
        self.tooltip: Optional[tk.Toplevel] = None
        self.position_below: bool = position_below
        self.toplevel_class = toplevel_class or tk.Toplevel
        self.hide_timer: Optional[str] = None

        # Bind the <Enter> and <Leave> events to show and hide the tooltip
        if platform_system() == "Darwin":
            # On macOS, only create the tooltip when the mouse enters the widget
            if tag_name and isinstance(self.widget, tk.Text):
                self.widget.tag_bind(tag_name, "<Enter>", self.create_show, "+")
                self.widget.tag_bind(tag_name, "<Leave>", self.destroy_hide, "+")
            else:
                self.widget.bind("<Enter>", self.create_show, "+")
                self.widget.bind("<Leave>", self.destroy_hide, "+")
        else:
            if tag_name and isinstance(self.widget, tk.Text):
                self.widget.tag_bind(tag_name, "<Enter>", self.show, "+")
                self.widget.tag_bind(tag_name, "<Leave>", self.hide, "+")
            else:
                self.widget.bind("<Enter>", self.show, "+")
                self.widget.bind("<Leave>", self.hide, "+")
            # On non-macOS, create the tooltip immediately and show/hide it on events
            self.tooltip = cast("tk.Toplevel", self.toplevel_class(widget))
            self.tooltip.wm_overrideredirect(boolean=True)
            tooltip_label = ttk.Label(
                self.tooltip, text=text, background="#ffffe0", relief="solid", borderwidth=1, justify=tk.LEFT
            )
            tooltip_label.pack()
            self.tooltip.withdraw()  # Initially hide the tooltip
            # Bind to tooltip to prevent hiding when mouse is over it
            self.tooltip.bind("<Enter>", self._cancel_hide)
            self.tooltip.bind("<Leave>", self.hide)

    def show(self, event: Optional[tk.Event] = None) -> None:  # noqa: ARG002 # pylint: disable=unused-argument
        """On non-macOS, tooltip already exists, show it on events."""
        self._cancel_hide()
        if self.tooltip:
            self.position_tooltip()
            self.tooltip.deiconify()

    def _cancel_hide(self, event: Optional[tk.Event] = None) -> None:  # noqa: ARG002 # pylint: disable=unused-argument
        """Cancel the hide timer."""
        if self.hide_timer:
            self.widget.after_cancel(self.hide_timer)
            self.hide_timer = None

    def create_show(self, event: Optional[tk.Event] = None) -> None:  # noqa: ARG002 # pylint: disable=unused-argument
        """On macOS, only create the tooltip when the mouse enters the widget."""
        if self.tooltip:
            return  # Avoid redundant tooltip creation

        self.tooltip = cast("tk.Toplevel", self.toplevel_class(self.widget))

        try:
            self.tooltip.tk.call(
                "::tk::unsupported::MacWindowStyle",
                "style",
                self.tooltip._w,  # type: ignore[attr-defined] # noqa: SLF001 # pylint: disable=protected-access
                "help",
                "noActivates",
            )
            self.tooltip.configure(bg="#ffffe0")
        except AttributeError:  # Catches protected member access error
            self.tooltip.wm_attributes("-alpha", 1.0)  # Ensure opacity
            self.tooltip.wm_attributes("-topmost", True)  # Keep on top # noqa: FBT003
            self.tooltip.configure(bg="#ffffe0")
        tooltip_label = ttk.Label(
            self.tooltip, text=self.text, background="#ffffe0", relief="solid", borderwidth=1, justify=tk.LEFT
        )
        tooltip_label.pack()
        self.position_tooltip()
        # Bind to tooltip to prevent hiding when mouse is over it
        self.tooltip.bind("<Enter>", self._cancel_hide)
        self.tooltip.bind("<Leave>", self.hide)

    def position_tooltip(self) -> None:
        """Calculate the position of the tooltip based on the widget's position, ensuring it fits inside the parent window."""
        if not self.tooltip:
            return

        # Ensure tooltip geometry is calculated
        self.tooltip.update_idletasks()
        tooltip_width = self.tooltip.winfo_reqwidth()
        tooltip_height = self.tooltip.winfo_reqheight()

        # Get parent window dimensions
        parent = self.widget.winfo_toplevel()
        parent_x = parent.winfo_rootx()
        parent_y = parent.winfo_rooty()
        parent_width = parent.winfo_width()
        parent_height = parent.winfo_height()

        x, y = calculate_tooltip_position(
            self.widget.winfo_rootx(),
            self.widget.winfo_rooty(),
            self.widget.winfo_width(),
            self.widget.winfo_height(),
            tooltip_width,
            tooltip_height,
            parent_x,
            parent_y,
            parent_width,
            parent_height,
            self.position_below,
        )

        self.tooltip.geometry(f"+{x}+{y}")

    def hide(self, event: Optional[tk.Event] = None) -> None:  # noqa: ARG002 # pylint: disable=unused-argument
        """Hide the tooltip after a delay on non-macOS."""
        self._cancel_hide()
        self.hide_timer = self.widget.after(10, self._do_hide)

    def _do_hide(self) -> None:
        """Actually hide or destroy the tooltip depending on platform."""
        if self.tooltip:
            self.tooltip.withdraw()
        self.hide_timer = None

    def destroy_hide(self, event: Optional[tk.Event] = None) -> None:  # noqa: ARG002 # pylint: disable=unused-argument
        """On macOS, fully destroy the tooltip when the mouse leaves the widget."""
        self._cancel_hide()
        if self.tooltip:
            self.tooltip.destroy()
            self.tooltip = None


def show_tooltip(widget: tk.Widget, text: str, position_below: bool = True) -> Tooltip:
    return Tooltip(widget, text, position_below=position_below, tag_name="")


def show_tooltip_on_richtext_tag(widget: tk.Text, text: str, tag_name: str, position_below: bool = True) -> Tooltip:
    return Tooltip(widget, text, position_below=position_below, tag_name=tag_name)
