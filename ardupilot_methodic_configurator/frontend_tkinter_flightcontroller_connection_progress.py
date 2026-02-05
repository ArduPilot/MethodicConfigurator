"""
Flight controller connection progress UI module.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import sys
import tkinter as tk
from logging import error as logging_error
from types import TracebackType
from typing import Literal, Optional

from ardupilot_methodic_configurator import _
from ardupilot_methodic_configurator.frontend_tkinter_progress_window import ProgressWindow

if sys.version_info >= (3, 11):
    from typing import Self
else:  # Python 3.9 and 3.10
    from typing_extensions import Self

PROGRESS_FC_INIT_COMPLETE = 20


class FlightControllerConnectionProgress:
    """
    UI class for flight controller connection progress.

    Manages the progress window and temporary Tk root for connection UI.
    """

    def __init__(self) -> None:
        # Needed because ProgressWindow needs a master and there is no application root window at this point
        self.temp_root: tk.Tk = tk.Tk()
        self.temp_root.withdraw()

        self.progress_window: ProgressWindow = ProgressWindow(
            self.temp_root,
            _("Initializing Flight Controller"),
            _("Starting initialization..."),
            only_show_when_update_progress_called=True,
        )

    def update_init_progress_bar(self, value: int, max_value: int) -> None:
        """
        Update progress bar for initialization phase.

        Maps input range [0, 100] to output range [0, PROGRESS_FC_INIT_COMPLETE].

        Args:
            value: Current progress value (0-100)
            max_value: Maximum progress value (typically 100)

        """
        if max_value <= 0:
            logging_error(_("Invalid max_value in update_init_progress_bar progress update: %d"), max_value)
            return
        self.progress_window.update_progress_bar(value * PROGRESS_FC_INIT_COMPLETE // 100, max_value)

    def update_connect_progress_bar(self, value: int, max_value: int) -> None:
        """
        Update progress bar for connection phase.

        Maps input range [0, 100] to output range [PROGRESS_FC_INIT_COMPLETE, 100].

        Args:
            value: Current progress value (0-100)
            max_value: Maximum progress value (typically 100)

        """
        if max_value <= 0:
            logging_error(_("Invalid max_value in update_connect_progress_bar progress update: %d"), max_value)
            return
        self.progress_window.update_progress_bar(
            PROGRESS_FC_INIT_COMPLETE + value * (100 - PROGRESS_FC_INIT_COMPLETE) // 100, max_value
        )

    def destroy(self) -> None:
        """Clean up resources - destroys progress window and temporary root."""
        if self.progress_window:
            self.progress_window.destroy()  # Destroy child first
        if self.temp_root:
            self.temp_root.destroy()  # Then destroy parent

    def __enter__(self) -> Self:
        """Enter context manager - returns self for use in 'with' statement."""
        return self

    def __exit__(
        self,
        exc_type: Optional[type[BaseException]],
        exc_val: Optional[BaseException],
        exc_tb: Optional[TracebackType],
    ) -> Literal[False]:
        """
        Exit context manager - ensures cleanup happens.

        Args:
            exc_type: Exception type if an exception occurred, None otherwise
            exc_val: Exception value if an exception occurred, None otherwise
            exc_tb: Exception traceback if an exception occurred, None otherwise

        Returns:
            False to propagate any exception that occurred

        """
        self.destroy()
        return False  # Don't suppress exceptions
