#!/usr/bin/env python3

'''
This file is part of Ardupilot methodic configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
'''

#from logging import debug as logging_debug
from logging import info as logging_info

import tkinter as tk
from tkinter import ttk

from MethodicConfigurator.backend_flightcontroller import FlightController
#from MethodicConfigurator.backend_flightcontroller_info import BackendFlightcontrollerInfo

#from MethodicConfigurator.frontend_tkinter_base import show_tooltip
from MethodicConfigurator.frontend_tkinter_base import ProgressWindow
from MethodicConfigurator.frontend_tkinter_base import BaseWindow

from MethodicConfigurator.internationalization import _

from MethodicConfigurator.version import VERSION


class FlightControllerInfoWindow(BaseWindow):
    """
    Display flight controller hardware, firmware and parameter information
    """
    def __init__(self, flight_controller: FlightController):
        super().__init__()
        self.root.title(_("ArduPilot methodic configurator ") + VERSION + _(" - Flight Controller Info"))
        self.root.geometry("500x350")  # Adjust the window size as needed
        self.flight_controller = flight_controller
        self.param_default_values = {}

        # Create a frame to hold all the labels and text fields
        self.info_frame = ttk.Frame(self.main_frame)
        self.info_frame.pack(fill=tk.BOTH, padx=20, pady=20)

        # Dynamically create labels and text fields for each attribute
        for row_nr, (description, attr_value) in enumerate(flight_controller.info.get_info().items()):
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
                text_field.insert(tk.END, "N/A")  # Insert "Not Available" if the attribute is missing or empty
            text_field.configure(state="readonly")

        self.info_frame.columnconfigure(1, weight=1)

        logging_info(_("Firmware Version: %s"), flight_controller.info.flight_sw_version_and_type)
        logging_info(_(f"Firmware first 8 hex bytes of the FC git hash: {flight_controller.info.flight_custom_version}"))
        logging_info(_(f"Firmware first 8 hex bytes of the ChibiOS git hash: {flight_controller.info.os_custom_version}"))
        logging_info(_(f"Flight Controller HW / board version: {flight_controller.info.board_version}"))
        logging_info(_(f"Flight Controller USB vendor ID: {flight_controller.info.vendor}"))
        logging_info(_(f"Flight Controller USB product ID: {flight_controller.info.product}"))

        self.root.after(50, self.download_flight_controller_parameters()) # 50 milliseconds
        self.root.mainloop()

    def download_flight_controller_parameters(self):
        param_download_progress_window = ProgressWindow(self.root, _("Downloading FC parameters"),
                                                        _("Downloaded {} of {} parameters"))
        self.flight_controller.fc_parameters, self.param_default_values = self.flight_controller.download_params(
            param_download_progress_window.update_progress_bar)
        param_download_progress_window.destroy()  # for the case that '--device test' and there is no real FC connected
        self.root.destroy()

    def get_param_default_values(self):
        return self.param_default_values
