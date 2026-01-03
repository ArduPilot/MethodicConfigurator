"""
Safe way to access TKinter font information.

This module provides a robust interface for accessing font information in TKinter
applications across different platforms. It handles the common issue where named
fonts like 'TkDefaultFont' may not be available during application startup,
especially on macOS systems.

The module offers functions to safely retrieve font configurations, families,
and sizes with appropriate platform-specific fallbacks. This ensures consistent
text rendering across Windows, macOS, and Linux systems.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import tkinter as tk
import tkinter.font as tkfont

# from logging import debug as logging_debug
# from logging import info as logging_info
from platform import system as platform_system
from typing import Optional, Union


def safe_font_nametofont(font_name: str = "TkDefaultFont") -> Optional[tkfont.Font]:
    """
    Safely retrieve a named font object with error handling.

    This function attempts to get a TKinter named font while gracefully handling
    cases where the font is not available, which commonly occurs during application
    initialization on macOS.

    Args:
        font_name: The name of the font to retrieve. Defaults to "TkDefaultFont".
                   Common options include "TkDefaultFont", "TkTextFont",
                   "TkFixedFont", etc.

    Returns:
        A tkfont.Font object if the named font exists and can be accessed,
        None otherwise.

    Example:
        >>> font = safe_font_nametofont("TkDefaultFont")
        >>> if font:
        ...     family = font.actual()["family"]
        ...     size = font.actual()["size"]

    Note:
        On macOS, named fonts may not be available immediately when the
        application starts. This function returns None in such cases, allowing
        the calling code to use fallback values instead of crashing.

    """
    try:
        return tkfont.nametofont(font_name)
    except tk.TclError:
        # On macOS and some configurations, named fonts may not be available
        # Return None to allow calling code to handle the fallback
        return None


def get_safe_font_config(font_name: str = "TkDefaultFont") -> dict[str, Union[str, int]]:
    """
    Get a complete font configuration with platform-appropriate fallbacks.

    Retrieves font configuration (family and size) either from the system's
    named font or from platform-specific defaults if the named font is unavailable.

    Args:
        font_name: Name of the font to retrieve. Defaults to "TkDefaultFont".

    Returns:
        Dictionary containing 'family' (str) and 'size' (int) keys with
        appropriate values for the current platform.

    Example:
        >>> config = get_safe_font_config()
        >>> print(f"Font: {config['family']}, Size: {config['size']}")
        Font: Segoe UI, Size: 9  # On Windows

    Note:
        This function always returns a valid configuration dictionary.
        Even if TKinter font queries fail, platform-specific defaults ensure
        a fallback is always provided.

    """
    # Try to get TkDefaultFont first
    font = safe_font_nametofont(font_name)
    if font:
        try:
            config = font.configure()
            if config and isinstance(config, dict):
                # Extract only the family and size values, converting to proper types
                family_val = config.get("family", "")
                # Only accept string family names that are not empty
                family = ""
                if isinstance(family_val, str) and family_val.strip():
                    family = family_val.strip()

                size_val = config.get("size")
                size = 0
                if size_val is not None:
                    try:
                        size = int(size_val)
                    except (ValueError, TypeError, OverflowError):
                        size = 0

                # Only return if we have valid values, otherwise fall back to platform defaults
                if family:  # Family is the key indicator of a valid font configuration
                    return {"family": family, "size": size}
        except tk.TclError:
            pass

    # Platform-specific fallbacks
    if platform_system() == "Windows":
        return {"family": "Segoe UI", "size": 9}
    if platform_system() == "Darwin":  # macOS
        return {"family": "Helvetica", "size": 13}
    # Linux and others
    return {"family": "Helvetica", "size": -12}


def get_safe_font_family(font_name: str = "TkDefaultFont") -> str:
    """
    Retrieve a safe font family name with platform-specific fallbacks.

    Gets the font family either from the system's named font or from a
    platform-appropriate default if the query fails.

    Args:
        font_name: Name of the font to retrieve. Defaults to "TkDefaultFont".

    Returns:
        Name of the font family as a string. Returns empty string if unable
        to determine a valid font family.

    Note:
        This function guarantees a string return value. If all attempts to
        retrieve a font family fail, it returns an empty string rather than None.

    """
    config = get_safe_font_config(font_name)
    return str(config.get("family", ""))


def get_safe_font_size(font_name: str = "TkDefaultFont") -> int:
    """
    Retrieve a safe font size with platform-specific fallbacks.

    Gets the font size either from the system's named font or from a
    platform-appropriate default if the query fails.

    Args:
        font_name: Name of the font to retrieve. Defaults to "TkDefaultFont".

    Returns:
        Font size as an integer. Returns 0 if unable to determine a valid size.

    Note:
        This function guarantees an integer return value. If the size cannot
        be determined from the system font, it falls back to platform-specific
        defaults, ensuring a valid integer is always returned.

    """
    config = get_safe_font_config(font_name)
    size_val = config.get("size", 0)
    try:
        return int(size_val) if size_val is not None else 0
    except (ValueError, TypeError, OverflowError):
        return 0


def create_scaled_font(font_config: dict[str, Union[str, int]], scale_factor: float = 1.0) -> tkfont.Font:
    """
    Create a tkinter Font object from a font configuration dictionary with optional scaling.

    Takes a font configuration dictionary (as returned by get_safe_font_config) and creates
    an actual tkinter Font object, optionally scaling the font size by a given factor.

    Args:
        font_config: Dictionary containing 'family' (str) and 'size' (int) keys.
                     Typically obtained from get_safe_font_config().
        scale_factor: Multiplier for the font size. For example, 1.2 creates a font
                     20% larger than the original. Defaults to 1.0 (no scaling).

    Returns:
        A tkinter Font object configured with the specified family and scaled size.

    Example:
        >>> config = get_safe_font_config("TkDefaultFont")
        >>> larger_font = create_scaled_font(config, 1.2)  # 20% larger
        >>> smaller_font = create_scaled_font(config, 0.8)  # 20% smaller

    Note:
        This function modifies the font_config dictionary in-place to scale the size.
        If you need to preserve the original config, pass a copy.

    """
    if isinstance(font_config["size"], int):
        font_config["size"] = int(font_config["size"] * scale_factor)
    return tkfont.Font(**font_config)  # type: ignore[arg-type]
