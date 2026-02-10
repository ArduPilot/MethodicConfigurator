"""
Flight controller information GUI.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import logging
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk
from typing import Callable, Optional, Union

from ardupilot_methodic_configurator import _, __version__
from ardupilot_methodic_configurator.backend_flightcontroller import FlightController
from ardupilot_methodic_configurator.data_model_par_dict import ParDict
from ardupilot_methodic_configurator.frontend_tkinter_base_window import BaseWindow


class FlightControllerInfoPresenter:
    """
    Business logic for flight controller information presentation.

    Separated from UI for better testability.
    """

    def __init__(self, flight_controller: FlightController, vehicle_dir: Path) -> None:
        self.flight_controller = flight_controller
        self.vehicle_dir = vehicle_dir
        self.param_default_values: ParDict = ParDict()

    def get_info_data(self) -> dict[str, Union[str, dict[str, str]]]:
        """Get formatted flight controller information for display."""
        return self.flight_controller.info.get_info()

    def log_flight_controller_info(self) -> None:
        """Log flight controller information."""
        self.flight_controller.info.log_flight_controller_info()

    def download_parameters(self, progress_callback: Optional[Callable[[int, int], None]] = None) -> ParDict:
        """
        Download flight controller parameters.

        Args:
            progress_callback: Optional callback function for progress updates

        Returns:
            Dictionary of parameter default values

        Note:
            The flight controller's fc_parameters are updated internally by download_params().
            We only need to store the default values for this window's use.

        """
        _fc_parameters, param_default_values = self.flight_controller.download_params(
            progress_callback,
            self.vehicle_dir / "complete.param",
            self.vehicle_dir / "00_default.param",
        )
        # Note: fc_parameters are already updated in the backend, no need to reassign
        self.param_default_values = param_default_values
        return param_default_values

    def get_param_default_values(self) -> ParDict:
        """Get parameter default values."""
        return self.param_default_values


class FlightControllerInfoWindow(BaseWindow):
    """Display flight controller hardware, firmware and parameter information."""

    def __init__(self, flight_controller: FlightController, vehicle_dir: Path) -> None:
        super().__init__()
        self.root.title(_("AMC {version} - Flight Controller Info").format(version=__version__))  # Set the window title
        self.root.geometry("500x420")  # Adjust the window size as needed

        self.presenter = FlightControllerInfoPresenter(flight_controller, vehicle_dir)

        self._create_info_display()
        self.presenter.log_flight_controller_info()

        # Schedule parameter download after UI is ready
        self.root.after(50, self._download_flight_controller_parameters)
        self.root.mainloop()

    def _create_info_display(self) -> None:
        """Create the flight controller information display."""
        # Create a frame to hold all the labels and text fields
        self.info_frame = ttk.Frame(self.main_frame)
        self.info_frame.pack(fill=tk.BOTH, padx=20, pady=(20, 10))

        # Dynamically create labels and text fields for each attribute
        info_data = self.presenter.get_info_data()
        for row_nr, (description, attr_value) in enumerate(info_data.items()):
            self._create_info_row(row_nr, description, attr_value)

        self.info_frame.columnconfigure(1, weight=1)

        # Create progress frame at the bottom
        self.progress_frame = ttk.Frame(self.main_frame)
        self.progress_frame.pack(fill=tk.X, padx=20, pady=(10, 20))

        # Create progress bar
        self.progress_bar = ttk.Progressbar(self.progress_frame, length=100, mode="determinate")
        self.progress_bar.pack(side=tk.TOP, fill=tk.X, expand=False, pady=(0, 5))

        # Create progress label
        self.progress_label = ttk.Label(self.progress_frame, text=_("Ready to download parameters..."))
        self.progress_label.pack(side=tk.TOP, fill=tk.X, expand=False)

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

    def update_progress_bar(self, current_value: int, max_value: int) -> None:
        """
        Update the progress bar and the progress message with the current progress.

        Args:
            current_value (int): The current progress value.
            max_value (int): The maximum progress value.

        """
        try:
            # Check if progress widgets still exist
            if not hasattr(self, "progress_bar") or self.progress_bar is None:
                return

            # Bring the main window to front (similar to original progress_window.lift())
            self.root.lift()
        except tk.TclError as _e:
            msg = _("Lifting window: {_e}")
            logging.error(msg.format(**locals()))
            return

        self.progress_bar["value"] = current_value
        self.progress_bar["maximum"] = max_value

        # Update the progress message
        progress_message = _("Downloaded {} of {} parameters").format(current_value, max_value)
        self.progress_label.config(text=progress_message)

        # Update the display
        self.progress_bar.update()
        self.root.update_idletasks()

        # Hide progress bar when complete
        if current_value == max_value:
            self.progress_frame.pack_forget()

    def _download_flight_controller_parameters(self) -> None:
        """Download flight controller parameters with progress feedback."""
        # Update progress label to show we're starting
        self.progress_label.config(text=_("Starting parameter download..."))
        self.root.update_idletasks()

        try:
            self.presenter.download_parameters(self.update_progress_bar)
        except Exception as e:  # pylint: disable=broad-exception-caught
            # Log the error
            logging.error("Failed to download parameters: %s", e)
            # Show an error message to the user
            messagebox.showerror(_("Error"), f"{_('Failed to download parameters')}: {e}")
            # Hide progress bar on error
            self.progress_frame.pack_forget()
        finally:
            self.root.destroy()

    def get_param_default_values(self) -> ParDict:
        """Get parameter default values from the presenter."""
        return self.presenter.get_param_default_values()
