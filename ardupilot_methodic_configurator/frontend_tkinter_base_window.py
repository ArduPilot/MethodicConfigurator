"""
Base window implementation for the ArduPilot Methodic Configurator Tkinter frontend.

This module provides the BaseWindow class, which serves as a foundation for all Tkinter-based
windows in the application. It handles common functionality such as DPI scaling, theming,
window management, and icon loading.

Key Features:
- Automatic DPI scaling detection and adjustment for HiDPI displays
- Consistent theming across all application windows
- Graceful icon loading with fallback for test environments
- Utility methods for window positioning and image handling

This file is part of Ardupilot methodic configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2025 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

# https://wiki.tcl-lang.org/page/Changing+Widget+Colors

import os
import tkinter as tk
import tkinter.font as tkfont

# from logging import debug as logging_debug
# from logging import info as logging_info
from logging import error as logging_error
from tkinter import ttk
from typing import Optional, Union

from PIL import Image, ImageTk

from ardupilot_methodic_configurator import _
from ardupilot_methodic_configurator.backend_filesystem import LocalFilesystem


class BaseWindow:
    """
    A foundational class for creating Tkinter windows in the ArduPilot Methodic Configurator.

    This class provides common functionality for all application windows, including:
    - DPI-aware scaling for HiDPI displays
    - Consistent theming and styling
    - Icon management with test environment fallbacks
    - Window positioning utilities
    - Image loading and display helpers

    The class automatically detects whether it's running in a test environment and
    adjusts behavior accordingly (e.g., skipping icon loading to avoid Tkinter issues).

    Attributes:
        root (Union[tk.Toplevel, tk.Tk]): The main Tkinter window object
        dpi_scaling_factor (float): Detected DPI scaling factor for the display
        main_frame (ttk.Frame): The primary container frame for window content

    Example:
        >>> # Create a main window
        >>> window = BaseWindow()
        >>>
        >>> # Create a child window
        >>> child = BaseWindow(window.root)

    """

    def __init__(self, root_tk: Optional[tk.Tk] = None) -> None:
        """
        Initialize a new BaseWindow instance.

        Args:
            root_tk (Optional[tk.Tk]): Parent window. If None, creates a new root window.
                                     If provided, creates a Toplevel window as a child.

        Note:
            When root_tk is None, this creates the main application window.
            When root_tk is provided, this creates a child dialog or sub-window.

        """
        self.root: Union[tk.Toplevel, tk.Tk]
        if root_tk:
            self.root = tk.Toplevel(root_tk)
        else:
            self.root = tk.Tk()
            # Only set icon for main windows, and only outside test environments
            self._setup_application_icon()

        # Detect DPI scaling for HiDPI support
        self.dpi_scaling_factor = self._get_dpi_scaling_factor()

        self.default_font_size: int = 0

        # Configure theme and styling
        self._setup_theme_and_styling()

        # Create main container frame
        self.main_frame = ttk.Frame(self.root)
        self.main_frame.pack(expand=True, fill=tk.BOTH)

    def _setup_application_icon(self) -> None:
        """
        Set up the application icon for the main window.

        This method handles icon loading with proper fallbacks for test environments
        and error conditions. Icons are only loaded for main windows (not Toplevel windows)
        and are skipped entirely during test runs to avoid Tkinter-related issues.

        Note:
            This method silently handles icon loading failures to prevent application
            crashes due to missing icon files or Tkinter configuration issues.

        """
        # Skip icon loading during tests to avoid tkinter issues
        if os.environ.get("PYTEST_CURRENT_TEST"):
            return

        # https://pythonassets.com/posts/window-icon-in-tk-tkinter/
        try:
            icon_path = LocalFilesystem.application_icon_filepath()
            self.root.iconphoto(True, tk.PhotoImage(file=icon_path))  # noqa: FBT003
        except (tk.TclError, FileNotFoundError) as e:
            # Silently ignore icon loading errors (common in test environments)
            logging_error(_("Could not load application icon: %s"), e)

    def _setup_theme_and_styling(self) -> None:
        """
        Configure the TTK theme and create custom styles.

        This method sets up the visual appearance of the application by:
        - Selecting an appropriate TTK theme
        - Creating custom styles for common UI elements
        - Applying DPI-aware font sizing

        """
        # Set the theme to 'alt' for consistent appearance
        style = ttk.Style()
        style.theme_use("alt")

        # Create custom styles with DPI-aware font sizes
        self.default_font_size = tkfont.nametofont("TkDefaultFont").cget("size")
        # Warning: on linux the font size might be negative
        bold_font_size = self.calculate_scaled_font_size(self.default_font_size)
        style.configure("Bold.TLabel", font=("TkDefaultFont", bold_font_size, "bold"))  # type: ignore[no-untyped-call]

    def _get_dpi_scaling_factor(self) -> float:
        """
        Detect the DPI scaling factor for HiDPI displays.

        This method uses multiple detection approaches to determine the appropriate
        scaling factor for the current display configuration:

        1. Calculates scaling based on actual DPI vs standard DPI (96)
        2. Checks Tkinter's internal scaling factor
        3. Uses the maximum of both methods for robustness

        Returns:
            float: The scaling factor (1.0 for standard DPI, 2.0 for 200% scaling, etc.)

        Note:
            Falls back to 1.0 if DPI detection fails, ensuring the application
            remains functional even on systems with unusual configurations.

        """
        try:
            # Get the DPI from Tkinter
            dpi = self.root.winfo_fpixels("1i")  # pixels per inch
            # Standard DPI is typically 96, so calculate scaling factor
            standard_dpi = 96.0
            scaling_factor = dpi / standard_dpi

            # Also check the tk scaling factor which might be set by the system
            tk_scaling = float(self.root.tk.call("tk", "scaling"))

            # Use the maximum of both methods to ensure we catch HiDPI scaling
            return max(scaling_factor, tk_scaling)
        except (tk.TclError, AttributeError):
            # Fallback to 1.0 if detection fails
            return 1.0

    def calculate_scaled_font_size(self, base_size: int) -> int:
        """
        Calculate a DPI-aware font size.

        Args:
            base_size (int): The base font size in points

        Returns:
            int: The scaled font size appropriate for the current display

        """
        return int(base_size * self.dpi_scaling_factor)

    def calculate_scaled_image_size(self, base_size: int) -> int:
        """
        Calculate a DPI-aware image size.

        Args:
            base_size (int): The base image size in pixels

        Returns:
            int: The scaled image size appropriate for the current display

        """
        return int(base_size * self.dpi_scaling_factor)

    def calculate_scaled_padding(self, base_padding: int) -> int:
        """
        Calculate DPI-aware padding values.

        Args:
            base_padding (int): The base padding value in pixels

        Returns:
            int: The scaled padding value appropriate for the current display

        """
        return int(base_padding * self.dpi_scaling_factor)

    def calculate_scaled_padding_tuple(self, padding1: int, padding2: int) -> tuple[int, int]:
        """
        Calculate a tuple of DPI-aware padding values.

        Args:
            padding1 (int): The first padding value in pixels
            padding2 (int): The second padding value in pixels

        Returns:
            tuple[int, int]: A tuple of scaled padding values

        """
        return (self.calculate_scaled_padding(padding1), self.calculate_scaled_padding(padding2))

    @staticmethod
    def center_window(window: Union[tk.Toplevel, tk.Tk], parent: Union[tk.Toplevel, tk.Tk]) -> None:
        """
        Center a window relative to its parent window.

        This method calculates the appropriate position to center a child window
        on top of its parent window, taking into account both windows' dimensions
        and the parent's current position.

        Args:
            window (Union[tk.Toplevel, tk.Tk]): The window to center
            parent (Union[tk.Toplevel, tk.Tk]): The parent window to center on

        Note:
            This method calls update_idletasks() to ensure accurate dimension
            calculations before positioning the window.

        Example:
            >>> main_window = BaseWindow()
            >>> dialog = BaseWindow(main_window.root)
            >>> BaseWindow.center_window(dialog.root, main_window.root)

        """
        window.update_idletasks()
        parent_width = parent.winfo_width()
        parent_height = parent.winfo_height()
        window_width = window.winfo_width()
        window_height = window.winfo_height()
        x = parent.winfo_x() + (parent_width // 2) - (window_width // 2)
        y = parent.winfo_y() + (parent_height // 2) - (window_height // 2)
        window.geometry(f"+{x}+{y}")

    def put_image_in_label(
        self,
        parent: ttk.Frame,
        filepath: str,
        image_height: int = 40,
        fallback_text: Optional[str] = None,
    ) -> ttk.Label:
        """
        Load an image and create a TTK label containing the resized image.

        This method handles image loading with comprehensive error handling and fallback
        behavior. It automatically scales images to the specified height while maintaining
        aspect ratio, and provides graceful degradation when images cannot be loaded.

        Args:
            parent (ttk.Frame): The parent frame to contain the image label
            filepath (str): Path to the image file to load
            image_height (int, optional): Target height for the image in pixels.
                                        Defaults to 40.
            fallback_text (Optional[str], optional): Text to display if image loading
                                                   fails. If None, creates an empty label.

        Returns:
            ttk.Label: A label widget containing either the loaded image or fallback content

        Raises:
            None: All exceptions are caught and handled gracefully with fallback behavior

        Example:
            >>> frame = ttk.Frame(root)
            >>> logo_label = BaseWindow.put_image_in_label(
            ...     frame,
            ...     "assets/logo.png",
            ...     image_height=60,
            ...     fallback_text="Logo"
            ... )

        Note:
            The returned label has an 'image' attribute set to prevent garbage collection
            of the PhotoImage object. This is a Tkinter requirement for image persistence.

        """
        try:
            # Validate input parameters
            if not filepath:
                msg = _("Image filepath cannot be empty")
                raise ValueError(msg)

            if image_height <= 0:
                msg = _("Image height must be positive")
                raise ValueError(msg)

            # Check if file exists
            if not os.path.isfile(filepath):
                msg = _("Image file not found: %s") % filepath
                raise FileNotFoundError(msg)

            # Load and validate the image
            image = Image.open(filepath)
            if image is None:
                msg = _("Failed to load image from %s") % filepath
                raise ValueError(msg)

            # Calculate new dimensions while preserving aspect ratio
            width, height = image.size
            if height == 0:
                msg = _("Image has zero height")
                raise ValueError(msg)

            aspect_ratio = width / height
            dpi_scaled_height = int(image_height * self.dpi_scaling_factor)

            # Resize the image
            resized_image = image.resize((int(dpi_scaled_height * aspect_ratio), dpi_scaled_height), Image.Resampling.LANCZOS)

            # Convert to PhotoImage for Tkinter
            photo = ImageTk.PhotoImage(resized_image)

            # Create the label with the image
            image_label = ttk.Label(parent, image=photo)
            # Keep a reference to prevent garbage collection
            image_label.image = photo  # type: ignore[attr-defined]

            return image_label

        except FileNotFoundError:
            # Re-raise FileNotFoundError to let calling code handle it
            raise
        except (OSError, ValueError, TypeError, AttributeError) as e:
            # Log the error for debugging
            logging_error(_("Error loading image from %s: %s"), filepath, e)

            # Create fallback label
            return ttk.Label(parent, text=fallback_text) if fallback_text else ttk.Label(parent)
