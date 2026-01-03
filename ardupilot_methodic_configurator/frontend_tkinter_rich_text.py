"""
TKinter base classes reused in multiple parts of the code.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

# https://wiki.tcl-lang.org/page/Changing+Widget+Colors

import tkinter as tk
from tkinter import font as tkFont  # noqa: N812
from tkinter import ttk
from typing import Optional

from ardupilot_methodic_configurator.backend_internet import webbrowser_open_url
from ardupilot_methodic_configurator.frontend_tkinter_font import get_safe_font_config, safe_font_nametofont
from ardupilot_methodic_configurator.frontend_tkinter_show import show_tooltip_on_richtext_tag


def _get_ttk_label_color(widget: Optional[tk.Misc], option: str, fallback: str) -> str:
    """Return a ttk label color or a safe fallback."""
    style = ttk.Style(widget)
    color = style.lookup("TLabel", option)

    if not color and widget:
        try:
            color = widget.cget(option)
        except tk.TclError:
            color = ""

    return color or fallback


class RichText(tk.Text):  # pylint: disable=too-many-ancestors
    """
    Extends the standard Tkinter Text widget to support rich text formatting.

    This class allows for the customization of text appearance through tags, enabling
    bold, italic, and heading styles directly within the text widget. It leverages the
    Tkinter font module to dynamically adjust font properties based on predefined tags.

    Methods:
        __init__(self, *args, **kwargs): Initializes the RichText widget with optional arguments
            passed to the superclass constructor. Custom fonts for bold, italic, and heading styles
            are configured during initialization.

    Tags:
        bold: Applies a bold font style.
        italic: Applies an italic font style.
        h1: Doubles the font size and applies bold styling, suitable for headings.

    Usage:
        To use this widget, simply replace instances of the standard Tkinter Text widget with
        RichText in your UI definitions. Apply tags to text segments using the tag_add method
        and configure the appearance accordingly.

    """

    def __init__(self, *args, **kwargs) -> None:
        master = args[0] if args else kwargs.get("master")
        if not (kwargs.get("background") or kwargs.get("bg")):
            kwargs["background"] = _get_ttk_label_color(master, "background", "white")
        if not (kwargs.get("foreground") or kwargs.get("fg")):
            kwargs["foreground"] = _get_ttk_label_color(master, "foreground", "black")

        super().__init__(*args, **kwargs)

        default_font = kwargs.get("font") or safe_font_nametofont()
        if default_font:
            # Use the actual font configuration if available
            bold_font = tkFont.Font(**default_font.configure())  # type: ignore[arg-type]
            italic_font = tkFont.Font(**default_font.configure())  # type: ignore[arg-type]
            h1_font = tkFont.Font(**default_font.configure())  # type: ignore[arg-type]
            default_size = default_font.cget("size")
        else:
            # Get safe default font configuration
            default_config = get_safe_font_config()
            # Create fonts with safe config
            bold_font = tkFont.Font(**default_config)  # type: ignore[arg-type]
            italic_font = tkFont.Font(**default_config)  # type: ignore[arg-type]
            h1_font = tkFont.Font(**default_config)  # type: ignore[arg-type]
            default_size = int(default_config.get("size", 0))

        bold_font.configure(weight="bold")
        italic_font.configure(slant="italic")
        h1_font.configure(size=int(default_size * 2), weight="bold")

        self.tag_configure("bold", font=bold_font)
        self.tag_configure("italic", font=italic_font)
        self.tag_configure("h1", font=h1_font, spacing3=default_size)

    def insert_clickable_link(self, text: str, unique_name: str, url: str, index: str = tk.END) -> None:
        """
        Insert a clickable link into the RichText widget.

        Args:
            text: The display text for the link.
            unique_name: A unique name for the link tag to avoid conflicts.
            url: The URL that the link points to.
            index: The index at which to insert the link.

        """
        self.insert(index, text, (unique_name,))
        self.tag_configure(unique_name, foreground="blue", underline=True)
        self.tag_bind(unique_name, "<Button-1>", lambda _: webbrowser_open_url(url))
        self.tag_bind(unique_name, "<Enter>", lambda _: self.config(cursor="hand2"))
        self.tag_bind(unique_name, "<Leave>", lambda _: self.config(cursor=""))
        show_tooltip_on_richtext_tag(self, url, unique_name)


def get_widget_font_family_and_size(widget: tk.Widget) -> tuple[str, int]:
    """
    Get the font family and size used by a Tkinter widget.

    Args:
        widget: The Tkinter widget to inspect.

    Returns:
        A tuple containing the font family and size.
        WARNINGS: This function assumes the widget has a style set.
                  On linux the font size might be negative.

    """
    style = ttk.Style()
    widget_style = widget.cget("style")  # Get the style used by the widget
    font_name = style.lookup(widget_style, "font")

    # Safely get platform-specific font configuration
    font_dict = get_safe_font_config(font_name)
    family = font_dict.get("family", "")
    size = font_dict.get("size", 0)
    return str(family), int(size)
