#!/usr/bin/env python3

"""
This file is part of Ardupilot methodic configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import tkinter as tk
from argparse import ArgumentParser
from logging import basicConfig as logging_basicConfig
from logging import debug as logging_debug
from logging import getLevelName as logging_getLevelName
from logging import warning as logging_warning
from sys import exit as sys_exit
from tkinter import simpledialog, ttk

from MethodicConfigurator import _
from MethodicConfigurator.backend_flightcontroller import FlightController
from MethodicConfigurator.common_arguments import add_common_arguments_and_parse
from MethodicConfigurator.frontend_tkinter_base import BaseWindow, ProgressWindow, show_no_connection_error, show_tooltip
from MethodicConfigurator.frontend_tkinter_pair_tuple_combobox import PairTupleCombobox


class ConnectionSelectionWidgets:  # pylint: disable=too-many-instance-attributes
    """
    A class for managing the selection of flight controller connections in the GUI.

    This class provides functionality for displaying available flight controller connections,
    allowing the user to select a connection, and handling the connection process.
    """

    def __init__(  # pylint: disable=too-many-arguments
        self,
        parent,
        parent_frame,
        flight_controller: FlightController,
        destroy_parent_on_connect: bool,
        download_params_on_connect: bool,
    ):
        self.parent = parent
        self.flight_controller = flight_controller
        self.destroy_parent_on_connect = destroy_parent_on_connect
        self.download_params_on_connect = download_params_on_connect
        self.previous_selection = (
            flight_controller.comport.device
            if flight_controller.comport and hasattr(flight_controller.comport, "device")
            else None
        )
        self.connection_progress_window: ProgressWindow

        # Create a new frame for the flight controller connection selection label and combobox
        self.container_frame = ttk.Frame(parent_frame)

        # Create a description label for the flight controller connection selection
        conn_selection_label = ttk.Label(self.container_frame, text=_("flight controller connection:"))
        conn_selection_label.pack(side=tk.TOP)  # Add the label to the top of the conn_selection_frame

        # Create a read-only combobox for flight controller connection selection
        self.conn_selection_combobox = PairTupleCombobox(
            self.container_frame,
            self.flight_controller.get_connection_tuples(),
            self.previous_selection,
            "FC connection",
            state="readonly",
        )
        self.conn_selection_combobox.bind("<<ComboboxSelected>>", self.on_select_connection_combobox_change, "+")
        self.conn_selection_combobox.pack(side=tk.TOP, pady=(4, 0))
        show_tooltip(
            self.conn_selection_combobox,
            _("Select the flight controller connection\nYou can add a custom connection to the existing ones"),
        )

    def on_select_connection_combobox_change(self, _event):
        selected_connection = self.conn_selection_combobox.get_selected_key()
        error_msg = _("Connection combobox changed to: {selected_connection}")
        logging_debug(error_msg.format(**locals()))
        comport_device = (
            self.flight_controller.comport.device
            if self.flight_controller.comport and hasattr(self.flight_controller.comport, "device")
            else None
        )
        if self.flight_controller.master is None or selected_connection != comport_device:
            if selected_connection == "Add another":
                if not self.add_connection() and self.previous_selection:
                    # nothing got selected revert to the current connection
                    self.conn_selection_combobox.set(self.previous_selection)
                return
            self.reconnect(selected_connection)

    def add_connection(self):
        # Open the connection selection dialog
        selected_connection = simpledialog.askstring(
            _("Flight Controller Connection"),
            _(
                "Enter the connection string to the flight controller. "
                "Examples are:\n\nCOM4 (on windows)\n"
                "/dev/serial/by-id/usb-xxx (on linux)\n"
                "tcp:127.0.0.1:5761\n"
                "udp:127.0.0.1:14551"
            ),
        )
        if selected_connection:
            error_msg = _("Will add new connection: {selected_connection} if not duplicated")
            logging_debug(error_msg.format(**locals()))
            self.flight_controller.add_connection(selected_connection)
            connection_tuples = self.flight_controller.get_connection_tuples()
            error_msg = _("Updated connection tuples: {connection_tuples} with selected connection: {selected_connection}")
            logging_debug(error_msg.format(**locals()))
            self.conn_selection_combobox.set_entries_tupple(connection_tuples, selected_connection)
            self.reconnect(selected_connection)
        else:
            error_msg = _("Add connection canceled or string empty {selected_connection}")
            logging_debug(error_msg.format(**locals()))
        return selected_connection

    def reconnect(self, selected_connection: str = ""):  # defaults to auto-connect
        self.connection_progress_window = ProgressWindow(
            self.parent.root, _("Connecting with the FC"), _("Connection step {} of {}")
        )
        error_message = self.flight_controller.connect(
            selected_connection, self.connection_progress_window.update_progress_bar
        )
        if error_message:
            show_no_connection_error(error_message)
            return True
        self.connection_progress_window.destroy()
        # Store the current connection as the previous selection
        if self.flight_controller.comport and hasattr(self.flight_controller.comport, "device"):
            self.previous_selection = self.flight_controller.comport.device
        if self.destroy_parent_on_connect:
            self.parent.root.destroy()
        if self.download_params_on_connect and hasattr(self.parent, _("download_flight_controller_parameters")):
            self.parent.download_flight_controller_parameters(redownload=False)
        return False


class ConnectionSelectionWindow(BaseWindow):
    """
    A window for selecting a flight controller connection.

    This class provides a graphical user interface for selecting a connection to a flight controller.
    It inherits from the BaseWindow class and uses the ConnectionSelectionWidgets class to handle
    the UI elements related to connection selection.
    """

    def __init__(self, flight_controller: FlightController, connection_result_string: str):
        super().__init__()
        self.root.title(_("Flight controller connection"))
        self.root.geometry("460x450")  # Set the window size

        # Explain why we are here
        if flight_controller.comport is None:
            introduction_text = _("No ArduPilot flight controller was auto-detected detected yet.")
        elif ":" in connection_result_string:
            introduction_text = connection_result_string.replace(":", ":\n")
        else:
            introduction_text = connection_result_string
        self.introduction_label = ttk.Label(
            self.main_frame,
            anchor=tk.CENTER,
            justify=tk.CENTER,
            text=introduction_text + _("\nChoose one of the following three options:"),
        )
        self.introduction_label.pack(expand=False, fill=tk.X, padx=6, pady=6)

        # Option 1 - Auto-connect
        option1_label = ttk.Label(text=_("Auto connection"), style="Bold.TLabel")
        option1_label_frame = ttk.LabelFrame(self.main_frame, labelwidget=option1_label, borderwidth=2, relief="solid")
        option1_label_frame.pack(expand=False, fill=tk.X, padx=6, pady=6)
        option1_label = ttk.Label(
            option1_label_frame,
            anchor=tk.CENTER,
            justify=tk.CENTER,
            text=_(
                "Connect a flight controller to the PC,\n"
                "wait 7 seconds for it to fully boot and\n"
                "press the Auto-connect button below to connect to it"
            ),
        )
        option1_label.pack(expand=False, fill=tk.X, padx=6)
        autoconnect_button = ttk.Button(option1_label_frame, text=_("Auto-connect"), command=self.fc_autoconnect)
        autoconnect_button.pack(expand=False, fill=tk.X, padx=100, pady=6)
        show_tooltip(autoconnect_button, _("Auto-connect to a 'Mavlink'-talking serial device"))

        # Option 2 - Manually select the flight controller connection or add a new one
        option2_label = ttk.Label(text=_("Manual connection"), style="Bold.TLabel")
        option2_label_frame = ttk.LabelFrame(self.main_frame, labelwidget=option2_label, borderwidth=2, relief="solid")
        option2_label_frame.pack(expand=False, fill=tk.X, padx=6, pady=6)
        # pylint: disable=duplicate-code
        option2_label = ttk.Label(
            option2_label_frame,
            anchor=tk.CENTER,
            justify=tk.CENTER,
            text=_(
                "Connect a flight controller to the PC,\n"
                "wait 7 seconds for it to fully boot and\n"
                "manually select the fight controller connection or add a new one"
            ),
        )
        # pylint: enable=duplicate-code
        option2_label.pack(expand=False, fill=tk.X, padx=6)
        self.connection_selection_widgets = ConnectionSelectionWidgets(
            self, option2_label_frame, flight_controller, destroy_parent_on_connect=True, download_params_on_connect=False
        )
        self.connection_selection_widgets.container_frame.pack(expand=False, fill=tk.X, padx=80, pady=6)

        # Option 3 - Skip FC connection, just edit the .param files on disk
        option3_label = ttk.Label(text=_("No connection"), style="Bold.TLabel")
        option3_label_frame = ttk.LabelFrame(self.main_frame, labelwidget=option3_label, borderwidth=2, relief="solid")
        option3_label_frame.pack(expand=False, fill=tk.X, padx=6, pady=6)
        # option3_label = ttk.Label(option3_label_frame, anchor=tk.CENTER, justify=tk.CENTER,
        #                          text=_("Skip the flight controller connection,\n")
        #                          "no default parameter values will be fetched from the FC,\n"
        #                          "default parameter values from disk will be used instead\n"
        #                          "(if '00_default.param' file is present)\n"
        #                          "and just edit the intermediate '.param' files on disk")
        # option3_label.pack(expand=False, fill=tk.X, padx=6)
        skip_fc_connection_button = ttk.Button(
            option3_label_frame,
            text=_("Skip FC connection, just edit the .param files on disk"),
            command=lambda flight_controller=flight_controller: self.skip_fc_connection(flight_controller),  # type: ignore
        )
        skip_fc_connection_button.pack(expand=False, fill=tk.X, padx=15, pady=6)
        show_tooltip(
            skip_fc_connection_button,
            _(
                "No parameter values will be fetched from the FC, default parameter values from disk will be used\n"
                "instead (if '00_default.param' file is present) and just edit the intermediate '.param' files on disk"
            ),
        )

        # Bind the close_connection_and_quit function to the window close event
        self.root.protocol("WM_DELETE_WINDOW", self.close_and_quit)

    def close_and_quit(self):
        sys_exit(0)

    def fc_autoconnect(self):
        self.connection_selection_widgets.reconnect()

    def skip_fc_connection(self, flight_controller: FlightController):
        logging_warning(_("Will proceed without FC connection. FC parameters will not be downloaded nor uploaded"))
        logging_warning(_("Only the intermediate '.param' files on the PC disk will be edited"))
        flight_controller.disconnect()
        self.root.destroy()


def argument_parser():
    """
    Parses command-line arguments for the script.

    This function sets up an argument parser to handle the command-line arguments for the script.

    Returns:
    argparse.Namespace: An object containing the parsed arguments.
    """
    parser = ArgumentParser(
        description=_(
            "This main is for testing and development only. "
            "Usually, the ConnectionSelectionWidgets is called from another script"
        )
    )
    parser = FlightController.add_argparse_arguments(parser)
    return add_common_arguments_and_parse(parser)


# pylint: disable=duplicate-code
def main():
    args = argument_parser()

    logging_basicConfig(level=logging_getLevelName(args.loglevel), format="%(asctime)s - %(levelname)s - %(message)s")

    logging_warning(
        _(
            "This main is for testing and development only, usually the ConnectionSelectionWindow is called from "
            "another script"
        )
    )
    # pylint: enable=duplicate-code

    flight_controller = FlightController(args.reboot_time)  # Initialize your FlightController instance
    result = flight_controller.connect(device=args.device)  # Connect to the flight controller
    if result:
        logging_warning(result)
        window = ConnectionSelectionWindow(flight_controller, result)
        window.root.mainloop()
    flight_controller.disconnect()  # Disconnect from the flight controller


if __name__ == "__main__":
    main()
