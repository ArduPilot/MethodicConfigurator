"""
TKinter base classes reused in multiple parts of the code.

This file is part of Ardupilot methodic configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2025 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

# https://wiki.tcl-lang.org/page/Changing+Widget+Colors

import tkinter as tk

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
    A base class for creating windows in the ArduPilot Methodic Configurator application.

    This class provides a foundation for creating windows in the application, including setting up the
    root window, applying a theme, and configuring the application icon. It also includes methods for
    creating a progress window and centering a window on its parent.
    """

    def __init__(self, root_tk: Optional[tk.Tk] = None) -> None:
        self.root: Union[tk.Toplevel, tk.Tk]
        if root_tk:
            self.root = tk.Toplevel(root_tk)
        else:
            self.root = tk.Tk()
            # Set the application icon for the window and all child windows
            # https://pythonassets.com/posts/window-icon-in-tk-tkinter/
            self.root.iconphoto(True, tk.PhotoImage(file=LocalFilesystem.application_icon_filepath()))  # noqa: FBT003

        # Set the theme to 'alt'
        style = ttk.Style()
        style.theme_use("alt")
        style.configure("Bold.TLabel", font=("TkDefaultFont", 10, "bold"))

        self.main_frame = ttk.Frame(self.root)
        self.main_frame.pack(expand=True, fill=tk.BOTH)

    @staticmethod
    def center_window(window: Union[tk.Toplevel, tk.Tk], parent: Union[tk.Toplevel, tk.Tk]) -> None:
        """
        Center a window on its parent window.

        Args:
            window (tk.Toplevel|tk.Tk): The window to center.
            parent (tk.Toplevel|tk.Tk): The parent window.

        """
        window.update_idletasks()
        parent_width = parent.winfo_width()
        parent_height = parent.winfo_height()
        window_width = window.winfo_width()
        window_height = window.winfo_height()
        x = parent.winfo_x() + (parent_width // 2) - (window_width // 2)
        y = parent.winfo_y() + (parent_height // 2) - (window_height // 2)
        window.geometry(f"+{x}+{y}")

    @staticmethod
    def put_image_in_label(parent: ttk.Frame, filepath: str, image_height: int = 40) -> ttk.Label:
        # Load the image and scale it down to image_height pixels in height
        image = Image.open(filepath)
        width, height = image.size
        aspect_ratio = width / height
        new_width = int(image_height * aspect_ratio)
        resized_image = image.resize((new_width, image_height))

        # Convert the image to a format that can be used by Tkinter
        try:
            photo = ImageTk.PhotoImage(resized_image)

            # Create a label with the resized image
            image_label = ttk.Label(parent, image=photo)
            # Keep a reference to the image to prevent it from being garbage collected
            image_label.image = photo  # type: ignore[attr-defined]
        except TypeError as e:
            logging_error(_("Error loading %s image from file: %s"), filepath, e)
            image_label = ttk.Label(parent)
        return image_label
