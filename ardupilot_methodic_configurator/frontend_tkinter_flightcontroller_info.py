"""
Flight controller information GUI.

This file is part of Ardupilot methodic configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2025 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import logging
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Callable, Optional, Union

from ardupilot_methodic_configurator import _, __version__
from ardupilot_methodic_configurator.annotate_params import Par
from ardupilot_methodic_configurator.backend_flightcontroller import FlightController
from ardupilot_methodic_configurator.frontend_tkinter_base_window import BaseWindow
from ardupilot_methodic_configurator.frontend_tkinter_progress_window import ProgressWindow


class FlightControllerInfoPresenter:
    """
    Business logic for flight controller information presentation.

    Separated from UI for better testability.
    """

    def __init__(self, flight_controller: FlightController) -> None:
        self.flight_controller = flight_controller
        self.param_default_values: dict[str, Par] = {}

    def get_info_data(self) -> dict[str, Union[str, dict[str, str]]]:
        """Get formatted flight controller information for display."""
        return self.flight_controller.info.get_info()

    def log_flight_controller_info(self) -> None:
        """Log flight controller information."""
        self.flight_controller.info.log_flight_controller_info()

    def download_parameters(self, progress_callback: Optional[Callable[[int, int], None]] = None) -> dict[str, Par]:
        """
        Download flight controller parameters.

        Args:
            progress_callback: Optional callback function for progress updates

        Returns:
            Dictionary of parameter default values

        """
        fc_parameters, param_default_values = self.flight_controller.download_params(progress_callback)
        self.flight_controller.fc_parameters = fc_parameters
        self.param_default_values = param_default_values
        return param_default_values

    def get_param_default_values(self) -> dict[str, Par]:
        """Get parameter default values."""
        return self.param_default_values


class FlightControllerInfoWindow(BaseWindow):
    """Display flight controller hardware, firmware and parameter information."""

    def __init__(self, flight_controller: FlightController) -> None:
        super().__init__()
        self.root.title(_("ArduPilot methodic configurator ") + __version__ + _(" - Flight Controller Info"))
        self.root.geometry("500x350")  # Adjust the window size as needed

        self.presenter = FlightControllerInfoPresenter(flight_controller)

        self._create_info_display()
        self.presenter.log_flight_controller_info()

        # Schedule parameter download after UI is ready
        self.root.after(50, self._download_flight_controller_parameters)
        self.root.mainloop()

    def _create_info_display(self) -> None:
        """Create the flight controller information display."""
        # Create a frame to hold all the labels and text fields
        self.info_frame = ttk.Frame(self.main_frame)
        self.info_frame.pack(fill=tk.BOTH, padx=20, pady=20)

        # Dynamically create labels and text fields for each attribute
        info_data = self.presenter.get_info_data()
        for row_nr, (description, attr_value) in enumerate(info_data.items()):
            self._create_info_row(row_nr, description, attr_value)

        self.info_frame.columnconfigure(1, weight=1)

    def _create_info_row(self, row_nr: int, description: str, attr_value: Union[str, dict[str, str]]) -> None:
        """Create a single row of information display."""
        label = ttk.Label(self.info_frame, text=f"{description}:")
        label.grid(row=row_nr, column=0, sticky="w")

        text_field = ttk.Entry(self.info_frame)
        text_field.grid(row=row_nr, column=1, sticky="ew", columnspan=1)

        # Format the value for display using the backend logic
        display_value = self.presenter.flight_controller.info.format_display_value(attr_value)
        text_field.insert(tk.END, display_value)
        text_field.configure(state="readonly")

    def _download_flight_controller_parameters(self) -> None:
        """Download flight controller parameters with progress feedback."""
        param_download_progress_window = ProgressWindow(
            self.root, _("Downloading FC parameters"), _("Downloaded {} of {} parameters")
        )

        try:
            self.presenter.download_parameters(param_download_progress_window.update_progress_bar)
        except Exception as e:  # pylint: disable=broad-exception-caught
            # Log the error
            logging.error("Failed to download parameters: %s", e)
            # Show an error message to the user
            messagebox.showerror(_("Error"), f"{_('Failed to download parameters')}: {e}")
        finally:
            param_download_progress_window.destroy()  # for the case that '--device test' and there is no real FC connected
            self.root.destroy()

    def get_param_default_values(self) -> dict[str, Par]:
        """Get parameter default values from the presenter."""
        return self.presenter.get_param_default_values()
