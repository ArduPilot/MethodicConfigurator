"""
Flight controller information GUI.

This file is part of Ardupilot methodic configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2025 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import tkinter as tk

# from logging import debug as logging_debug
from logging import error as logging_error
from logging import info as logging_info
from tkinter import ttk
from typing import Callable, Optional

from serial.serialutil import SerialException

from ardupilot_methodic_configurator import _, __version__
from ardupilot_methodic_configurator.annotate_params import Par
from ardupilot_methodic_configurator.backend_flightcontroller import FlightController
from ardupilot_methodic_configurator.frontend_tkinter_base_window import BaseWindow
from ardupilot_methodic_configurator.frontend_tkinter_progress_window import ProgressWindow


class FlightControllerInfoWindow(BaseWindow):
    """Display flight controller hardware, firmware and parameter information."""

    def __init__(self, flight_controller: FlightController, root_tk: Optional[tk.Tk] = None) -> None:
        """
        Initialize the FlightControllerInfoWindow.

        Args:
            flight_controller: The flight controller to display information for
            root_tk: Optional parent Tk root window

        """
        super().__init__(root_tk)
        self.root.title(_("ArduPilot methodic configurator ") + __version__ + _(" - Flight Controller Info"))
        self.root.geometry("500x350")  # Adjust the window size as needed
        self.flight_controller = flight_controller
        self.param_default_values: dict[str, Par] = {}

        # Initialize UI components
        self._init_ui()

        # Log flight controller information
        self._log_flight_controller_info()

        # Schedule parameter download after window is shown
        if not root_tk:  # Only schedule if this is the main window
            self.root.after(50, self._schedule_download_parameters)

    def _init_ui(self) -> None:
        """Initialize the UI components."""
        # Create a frame to hold all the labels and text fields
        self.info_frame = ttk.Frame(self.main_frame)
        self.info_frame.pack(fill=tk.BOTH, padx=20, pady=20)

        # Dynamically create labels and text fields for each attribute
        self._create_info_fields()

        self.info_frame.columnconfigure(1, weight=1)

    def _create_info_fields(self) -> None:
        """Create the information fields in the UI."""
        for row_nr, (description, attr_value) in enumerate(self.flight_controller.info.get_info().items()):
            label = ttk.Label(self.info_frame, text=f"{description}:")
            label.grid(row=row_nr, column=0, sticky="w")

            text_field = ttk.Entry(self.info_frame)
            text_field.grid(row=row_nr, column=1, sticky="ew", columnspan=1)

            # Check if the attribute exists and has a non-empty value before inserting
            if attr_value:
                if isinstance(attr_value, dict):
                    text_field.insert(tk.END, (", ").join(attr_value.keys()))
                else:
                    text_field.insert(tk.END, attr_value)
            else:
                text_field.insert(tk.END, _("N/A"))  # Insert "Not Available" if the attribute is missing or empty
            text_field.configure(state="readonly")

    def _log_flight_controller_info(self) -> None:
        """Log information about the flight controller."""
        logging_info(_("Firmware Version: %s"), self.flight_controller.info.flight_sw_version_and_type)
        logging_info(_("Firmware first 8 hex bytes of the FC git hash: %s"), self.flight_controller.info.flight_custom_version)
        logging_info(
            _("Firmware first 8 hex bytes of the ChibiOS git hash: %s"), self.flight_controller.info.os_custom_version
        )
        logging_info(
            _("Flight Controller firmware type: %s (%s)"),
            self.flight_controller.info.firmware_type,
            self.flight_controller.info.apj_board_id,
        )
        logging_info(_("Flight Controller HW / board version: %s"), self.flight_controller.info.board_version)
        logging_info(_("Flight Controller USB vendor ID: %s"), self.flight_controller.info.vendor)
        logging_info(_("Flight Controller USB product ID: %s"), self.flight_controller.info.product)

    def _schedule_download_parameters(self) -> None:
        """Schedule the download of parameters and exit when complete."""
        try:
            self.download_flight_controller_parameters()
            self.root.destroy()
        except (OSError, ConnectionError, SerialException, PermissionError, ValueError, RuntimeError) as e:
            logging_error(_("Failed to download parameters: %s"), str(e))
            self.root.destroy()

    def run(self) -> None:
        """Run the application main loop."""
        self.root.mainloop()

    def download_flight_controller_parameters(self, progress_callback: Optional[Callable[[int, int], None]] = None) -> None:
        """
        Download parameters from the flight controller with progress tracking and error handling.

        Args:
            progress_callback: Optional callback function to track progress

        Raises:
            ConnectionError: If connection to the flight controller fails
            SerialException: If there's an error with the serial communication
            PermissionError: If there's a permission error when accessing the device
            IOError: If there's an I/O error during communication
            ValueError: If there's an invalid value during parameter processing
            RuntimeError: If any other runtime error occurs during parameter download

        """
        if progress_callback:
            # Use provided callback directly
            try:
                self.flight_controller.fc_parameters, self.param_default_values = self.flight_controller.download_params(
                    progress_callback
                )
            except (OSError, ConnectionError, SerialException, PermissionError, ValueError, RuntimeError) as e:
                logging_error(_("Error downloading flight controller parameters: %s"), str(e))
                # Re-raise the exception after logging
                raise
        else:
            # Create progress window and use its update function
            param_download_progress_window = ProgressWindow(
                self.root, _("Downloading FC parameters"), _("Downloaded {} of {} parameters")
            )
            try:
                self.flight_controller.fc_parameters, self.param_default_values = self.flight_controller.download_params(
                    param_download_progress_window.update_progress_bar
                )
            except (OSError, ConnectionError, SerialException, PermissionError, ValueError, RuntimeError) as e:
                logging_error(_("Error downloading flight controller parameters: %s"), str(e))
                # Make sure to destroy the progress window even on error
                param_download_progress_window.destroy()
                # Re-raise the exception after cleanup
                raise
            # Normal cleanup path when no exceptions occur
            param_download_progress_window.destroy()  # for the case that '--device test' and there is no real FC connected

    def get_param_default_values(self) -> dict[str, Par]:
        """Get the default parameter values."""
        return self.param_default_values
