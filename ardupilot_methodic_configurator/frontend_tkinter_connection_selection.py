#!/usr/bin/env python3

"""
GUI to select the connection to the FC.

This file is part of Ardupilot methodic configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2025 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import tkinter as tk
from argparse import ArgumentParser, Namespace
from logging import basicConfig as logging_basicConfig
from logging import debug as logging_debug
from logging import getLevelName as logging_getLevelName
from logging import warning as logging_warning
from sys import exit as sys_exit
from tkinter import simpledialog, ttk
from typing import Union

from ardupilot_methodic_configurator import _
from ardupilot_methodic_configurator.backend_flightcontroller import FlightController
from ardupilot_methodic_configurator.common_arguments import add_common_arguments
from ardupilot_methodic_configurator.frontend_tkinter_base_window import BaseWindow
from ardupilot_methodic_configurator.frontend_tkinter_pair_tuple_combobox import PairTupleCombobox
from ardupilot_methodic_configurator.frontend_tkinter_progress_window import ProgressWindow
from ardupilot_methodic_configurator.frontend_tkinter_show import show_no_connection_error, show_tooltip


class ConnectionDialog(simpledialog.Dialog):
    """
    Custom dialog for adding a new flight controller connection with baudrate selection.

    This dialog allows the user to specify both the connection string and the baudrate
    for the new connection.
    """

    def __init__(self, parent: tk.Tk, default_baudrate: int = 115200) -> None:
        self.connection_string = ""
        self.baudrate = default_baudrate
        self.default_baudrate = default_baudrate
        super().__init__(parent, title=_("Flight Controller Connection"))

    def body(self, master) -> tk.Widget:  # noqa: ANN001
        """Create the dialog body with connection string and baudrate fields."""
        # Connection string field
        tk.Label(master, text=_("Connection string:")).grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        self.connection_entry = tk.Entry(master, width=40)
        self.connection_entry.grid(row=0, column=1, columnspan=2, padx=5, pady=5, sticky=tk.W + tk.E)

        # Add example text
        example_text = _(
            "Examples:\nCOM4 (on Windows)\n/dev/serial/by-id/usb-xxx (on Linux)\ntcp:127.0.0.1:5761\nudp:127.0.0.1:14551"
        )
        tk.Label(master, text=example_text, justify=tk.LEFT, font=("TkDefaultFont", 8)).grid(
            row=1, column=0, columnspan=3, sticky=tk.W, padx=5, pady=(0, 10)
        )

        # Baudrate field
        tk.Label(master, text=_("Baudrate:")).grid(row=2, column=0, sticky=tk.W, padx=5, pady=5)
        self.baudrate_var = tk.StringVar(value=str(self.default_baudrate))
        self.baudrate_combobox = ttk.Combobox(
            master,
            textvariable=self.baudrate_var,
            values=["9600", "19200", "38400", "57600", "115200", "230400", "460800", "921600"],
            state="normal",
            width=15,
        )
        self.baudrate_combobox.grid(row=2, column=1, padx=5, pady=5, sticky=tk.W)

        master.columnconfigure(1, weight=1)
        return self.connection_entry  # Return the widget that should have initial focus

    def validate(self) -> bool:
        """Validate the input fields."""
        self.connection_string = self.connection_entry.get().strip()
        if not self.connection_string:
            return False

        try:
            self.baudrate = int(self.baudrate_var.get())
            if self.baudrate <= 0:
                return False
        except ValueError:
            return False

        return True

    def apply(self) -> None:
        """Apply the dialog results."""
        # Values are already set in validate()


class ConnectionSelectionWidgets:  # pylint: disable=too-many-instance-attributes
    """
    A class for managing the selection of flight controller connections in the GUI.

    This class provides functionality for displaying available flight controller connections,
    allowing the user to select a connection, and handling the connection process.
    """

    def __init__(  # pylint: disable=too-many-arguments, too-many-positional-arguments
        self,
        parent,  # noqa: ANN001 ConnectionSelectionWindow can not add it here, otherwise a dependency loop will be created
        parent_frame: ttk.Labelframe,
        flight_controller: FlightController,
        destroy_parent_on_connect: bool,
        download_params_on_connect: bool,
        default_baudrate: int = 115200,
    ) -> None:
        self.parent = parent
        self.flight_controller = flight_controller
        self.destroy_parent_on_connect = destroy_parent_on_connect
        self.download_params_on_connect = download_params_on_connect
        self.default_baudrate = default_baudrate
        self.previous_selection: Union[None, str] = (
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

        # Create a frame for connection and baudrate selection
        selection_frame = ttk.Frame(self.container_frame)
        selection_frame.pack(side=tk.TOP, pady=(4, 0))

        # Create a read-only combobox for flight controller connection selection
        self.conn_selection_combobox = PairTupleCombobox(
            selection_frame,
            self.flight_controller.get_connection_tuples(),
            self.previous_selection,
            "FC connection",
            state="readonly",
        )
        self.conn_selection_combobox.bind("<<ComboboxSelected>>", self.on_select_connection_combobox_change, "+")
        self.conn_selection_combobox.pack(side=tk.LEFT, padx=(0, 5))
        show_tooltip(
            self.conn_selection_combobox,
            _("Select the flight controller connection\nYou can add a custom connection to the existing ones"),
        )

        # Create a label for baudrate
        baudrate_label = ttk.Label(selection_frame, text=_("Baudrate:"))
        baudrate_label.pack(side=tk.LEFT, padx=(10, 5))

        # Create a combobox for baudrate selection
        self.baudrate_var = tk.StringVar(value=str(self.default_baudrate))
        self.baudrate_combobox = ttk.Combobox(
            selection_frame,
            textvariable=self.baudrate_var,
            values=["9600", "19200", "38400", "57600", "115200", "230400", "460800", "921600"],
            state="normal",
            width=10,
        )
        self.baudrate_combobox.pack(side=tk.LEFT)
        show_tooltip(
            self.baudrate_combobox,
            _("Select the baudrate for the connection\nMost flight controllers use 115200"),
        )

    def on_select_connection_combobox_change(self, _event: tk.Event) -> None:
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
            # Update baudrate combobox with stored baudrate for this connection
            if selected_connection:
                stored_baudrate = self.flight_controller.get_connection_baudrate(selected_connection)
                self.baudrate_var.set(str(stored_baudrate))
            self.reconnect(selected_connection)  # type: ignore[arg-type] # workaround for mypy issue

    def add_connection(self) -> str:
        # Open the connection selection dialog
        dialog = ConnectionDialog(self.parent.root, self.default_baudrate)
        if dialog.result:
            selected_connection = dialog.connection_string
            baudrate = dialog.baudrate
            error_msg = _("Will add new connection: {selected_connection} with baudrate: {baudrate} if not duplicated")
            logging_debug(error_msg.format(**locals()))
            self.flight_controller.add_connection(selected_connection, baudrate)
            connection_tuples = self.flight_controller.get_connection_tuples()
            error_msg = _("Updated connection tuples: {connection_tuples} with selected connection: {selected_connection}")
            logging_debug(error_msg.format(**locals()))
            self.conn_selection_combobox.set_entries_tuple(connection_tuples, selected_connection)
            # Set the baudrate for this connection
            self.baudrate_var.set(str(baudrate))
            self.reconnect(selected_connection)
        else:
            error_msg = _("Add connection canceled or invalid input")
            logging_debug(error_msg.format(**locals()))
            selected_connection = ""
        return selected_connection

    def reconnect(self, selected_connection: str = "") -> bool:  # Default is auto-connect
        self.connection_progress_window = ProgressWindow(
            self.parent.root, _("Connecting with the FC"), _("Connection step {} of {}")
        )
        # Get the current baudrate from the combobox
        try:
            current_baudrate = int(self.baudrate_var.get())
        except (ValueError, AttributeError):
            current_baudrate = self.default_baudrate

        error_message = self.flight_controller.connect(
            selected_connection, self.connection_progress_window.update_progress_bar, baudrate=current_baudrate
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
        if self.download_params_on_connect and hasattr(self.parent, "download_flight_controller_parameters"):
            self.parent.download_flight_controller_parameters(redownload=False)
        return False


class ConnectionSelectionWindow(BaseWindow):
    """
    A window for selecting a flight controller connection.

    This class provides a graphical user interface for selecting a connection to a flight controller.
    It inherits from the BaseWindow class and uses the ConnectionSelectionWidgets class to handle
    the UI elements related to connection selection.
    """

    def __init__(
        self,
        flight_controller: FlightController,
        connection_result_string: str,
        default_baudrate: int = 115200,
    ) -> None:
        super().__init__()
        self.root.title(_("Flight controller connection"))
        self.root.geometry("460x462")  # Set the window size
        self.default_baudrate = default_baudrate

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
        option1_label_frame = ttk.LabelFrame(self.main_frame, labelwidget=option1_label)
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
        option2_label_frame = ttk.LabelFrame(self.main_frame, labelwidget=option2_label)
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
            self,
            option2_label_frame,
            flight_controller,
            destroy_parent_on_connect=True,
            download_params_on_connect=False,
            default_baudrate=self.default_baudrate,
        )
        self.connection_selection_widgets.container_frame.pack(expand=False, fill=tk.X, padx=80, pady=6)

        # Option 3 - Skip FC connection, just edit the .param files on disk
        option3_label = ttk.Label(text=_("No connection"), style="Bold.TLabel")
        option3_label_frame = ttk.LabelFrame(self.main_frame, labelwidget=option3_label)
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
            command=lambda fc=flight_controller: self.skip_fc_connection(fc),  # type: ignore[misc]
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

    def close_and_quit(self) -> None:
        sys_exit(0)

    def fc_autoconnect(self) -> None:
        self.connection_selection_widgets.reconnect()

    def skip_fc_connection(self, flight_controller: FlightController) -> None:
        logging_warning(_("Will proceed without FC connection. FC parameters will not be downloaded nor uploaded"))
        logging_warning(_("Only the intermediate '.param' files on the PC disk will be edited"))
        flight_controller.disconnect()
        self.root.destroy()


def argument_parser() -> Namespace:
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
    return add_common_arguments(parser).parse_args()


# pylint: disable=duplicate-code
def main() -> None:
    args = argument_parser()

    logging_basicConfig(level=logging_getLevelName(args.loglevel), format="%(asctime)s - %(levelname)s - %(message)s")

    logging_warning(
        _("This main is for testing and development only, usually the ConnectionSelectionWindow is called from another script")
    )
    # pylint: enable=duplicate-code

    flight_controller = FlightController(reboot_time=args.reboot_time, baudrate=args.baudrate)
    result = flight_controller.connect(device=args.device)
    if result:
        logging_warning(result)
        window = ConnectionSelectionWindow(flight_controller, result, default_baudrate=args.baudrate)
        window.root.mainloop()
    flight_controller.disconnect()  # Disconnect from the flight controller


if __name__ == "__main__":
    main()
