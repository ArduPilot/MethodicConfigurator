"""
TKinter base classes reused in multiple parts of the code.

This file is part of Ardupilot methodic configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2025 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

# https://wiki.tcl-lang.org/page/Changing+Widget+Colors

import tkinter as tk
from platform import system as platform_system
from tkinter import font as tkFont  # noqa: N812
from tkinter import ttk
from typing import Optional, Union


def safe_font_nametofont(font_name: str, root: Optional[Union[tk.Tk, tk.Toplevel]] = None) -> Optional[tkFont.Font]:
    """
    Safely get a named font, with platform-specific fallbacks for macOS.
    
    Args:
        font_name: Name of the font to retrieve (e.g., "TkDefaultFont")
        root: Optional tkinter root window for context
        
    Returns:
        Font object if available, None if not found
        
    Note:
        On macOS, TkDefaultFont may not be available during initialization.
        This function provides safe fallbacks for such cases.
    """
    try:
        return tkFont.nametofont(font_name, root=root)
    except tk.TclError:
        # On macOS and some configurations, named fonts may not be available
        # Return None to allow calling code to handle the fallback
        return None


def get_safe_default_font_config(root: Optional[Union[tk.Tk, tk.Toplevel]] = None) -> dict[str, str | int]:
    """
    Get safe default font configuration with platform-specific fallbacks.
    
    Args:
        root: Optional tkinter root window for context
        
    Returns:
        Font configuration dict with 'family' and 'size' keys
    """
    # Try to get TkDefaultFont first
    font = safe_font_nametofont("TkDefaultFont", root)
    if font:
        try:
            config = font.configure()
            if config and isinstance(config, dict):
                # Handle negative font sizes (common on Linux)
                size = config.get("size", 12)
                if isinstance(size, int) and size < 0:
                    config["size"] = abs(size)
                return config
        except tk.TclError:
            pass
    
    # Platform-specific fallbacks
    if platform_system() == "Windows":
        return {"family": "Segoe UI", "size": 9}
    elif platform_system() == "Darwin":  # macOS
        return {"family": "Helvetica", "size": 13}
    else:  # Linux and others
        return {"family": "Helvetica", "size": 12}


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
        super().__init__(*args, **kwargs)

        # Get safe default font configuration
        default_config = get_safe_default_font_config()
        default_size = default_config["size"]
        
        # Try to use TkDefaultFont if available, otherwise use safe config
        default_font = safe_font_nametofont("TkDefaultFont")
        if default_font:
            try:
                # Use the actual font configuration if available
                bold_font = tkFont.Font(**default_font.configure())  # type: ignore[arg-type]
                italic_font = tkFont.Font(**default_font.configure())  # type: ignore[arg-type]
                h1_font = tkFont.Font(**default_font.configure())  # type: ignore[arg-type]
                actual_size = default_font.cget("size")
                # Handle negative font sizes (common on Linux)
                default_size = abs(actual_size) if actual_size < 0 else actual_size
            except tk.TclError:
                # Fallback to creating fonts with safe config
                bold_font = tkFont.Font(**default_config)
                italic_font = tkFont.Font(**default_config)
                h1_font = tkFont.Font(**default_config)
        else:
            # Create fonts with safe config
            bold_font = tkFont.Font(**default_config)
            italic_font = tkFont.Font(**default_config)
            h1_font = tkFont.Font(**default_config)

        bold_font.configure(weight="bold")
        italic_font.configure(slant="italic")
        h1_font.configure(size=int(default_size * 2), weight="bold")

        self.tag_configure("bold", font=bold_font)
        self.tag_configure("italic", font=italic_font)
        self.tag_configure("h1", font=h1_font, spacing3=default_size)


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
    
    # Safely get font configuration
    font = safe_font_nametofont(font_name)
    if font:
        try:
            font_dict = font.config()
        except tk.TclError:
            font_dict = None
    else:
        font_dict = None

    default_font_family = "Segoe UI" if platform_system() == "Windows" else "Helvetica"
    default_font_size = 9 if platform_system() == "Windows" else 12

    if font_dict is None:
        return default_font_family, default_font_size
    return font_dict.get("family", default_font_family), font_dict.get("size", default_font_size)
