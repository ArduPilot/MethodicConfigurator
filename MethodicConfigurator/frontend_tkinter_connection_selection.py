#!/usr/bin/env python3

'''
This file is part of Ardupilot methodic configurator. https://github.com/ArduPilot/MethodicConfigurator

(C) 2024 Amilcar do Carmo Lucas, IAV GmbH

SPDX-License-Identifier:    GPL-3
'''

from sys import exit as sys_exit

from argparse import ArgumentParser

from logging import basicConfig as logging_basicConfig
from logging import getLevelName as logging_getLevelName
from logging import debug as logging_debug
from logging import warning as logging_warning
from logging import critical as logging_critical

import tkinter as tk
from tkinter import ttk
from tkinter import simpledialog

from backend_flightcontroller import FlightController

from frontend_tkinter_base import show_no_connection_error
from frontend_tkinter_base import show_tooltip
from frontend_tkinter_base import update_combobox_width
from frontend_tkinter_base import BaseWindow


VERSION = "0.0.1"


# https://dev.to/geraldew/python-tkinter-an-exercise-in-wrapping-the-combobox-ndb
class PairTupleCombobox(ttk.Combobox):  # pylint: disable=too-many-ancestors
    """
    A custom Combobox widget that allows for the display of a list of tuples, where each tuple contains a key and a value.
    This widget processes the list of tuples to separate keys and values for display purposes, and allows for the selection
    of a tuple based on its key.
    """
    def process_list_pair_tuple(self, list_pair_tuple):
        r_list_keys = []
        r_list_shows = []
        for tpl in list_pair_tuple:
            r_list_keys.append(tpl[0])
            r_list_shows.append(tpl[1])
        return r_list_keys, r_list_shows

    def __init__(self, container, list_pair_tuple, selected_element, *args, **kwargs):
        super().__init__(container, *args, **kwargs)
        self.set_entries_tupple(list_pair_tuple, selected_element)

    def set_entries_tupple(self, list_pair_tuple, selected_element):
        self.list_keys, self.list_shows = self.process_list_pair_tuple(list_pair_tuple)
        self['values'] = tuple(self.list_shows)
        # still need to set the default value from the nominated key
        if selected_element:
            try:
                default_key_index = self.list_keys.index(selected_element)
                self.current(default_key_index)
            except IndexError:
                logging_critical("connection combobox selected string '%s' not in list %s", selected_element, self.list_keys)
                sys_exit(1)
            except ValueError:
                logging_critical("connection combobox selected string '%s' not in list %s", selected_element, self.list_keys)
                sys_exit(1)
            update_combobox_width(self)
        else:
            logging_warning("No connection combobox element selected")

    def get_selected_key(self):
        try:
            i_index = self.current()
            return self.list_keys[i_index]
        except IndexError:
            return None


class ConnectionSelectionWidgets():  # pylint: disable=too-many-instance-attributes
    """
    A class for managing the selection of flight controller connections in the GUI.

    This class provides functionality for displaying available flight controller connections,
    allowing the user to select a connection, and handling the connection process.
    """
    def __init__(self, parent, parent_frame, flight_controller: FlightController):
        self.parent = parent
        self.flight_controller = flight_controller
        self.previous_selection = flight_controller.comport.device if hasattr(self.flight_controller.comport, "device") \
            else None
        self.connection_progress_window = None
        self.connection_progress_bar = None
        self.connection_progress_label = None

        # Create a new frame for the flight controller connection selection label and combobox
        self.container_frame = tk.Frame(parent_frame)

        # Create a description label for the flight controller connection selection
        conn_selection_label = tk.Label(self.container_frame, text="flight controller connection:")
        conn_selection_label.pack(side=tk.TOP, anchor=tk.NW) # Add the label to the top of the conn_selection_frame

        # Create a read-only combobox for flight controller connection selection
        self.conn_selection_combobox = PairTupleCombobox(self.container_frame, self.flight_controller.get_connection_tuples(),
                                                         self.previous_selection,
                                                         state='readonly')
        self.conn_selection_combobox.bind("<<ComboboxSelected>>", self.on_select_connection_combobox_change)
        self.conn_selection_combobox.pack(side=tk.TOP, anchor=tk.NW, pady=(4, 0))
        show_tooltip(self.conn_selection_combobox, "Select the flight controller connection\nYou can add a custom connection "
                     "to the existing ones")

    def on_select_connection_combobox_change(self, _event):
        selected_connection = self.conn_selection_combobox.get_selected_key()
        logging_debug(f"Connection combobox changed to: {selected_connection}")
        if self.flight_controller.master is None or selected_connection != self.flight_controller.comport.device:
            if selected_connection == 'Add another':
                if not self.add_connection() and self.previous_selection:
                    # nothing got selected revert to the current connection
                    self.conn_selection_combobox.set(self.previous_selection)
                return
            self.reconnect(selected_connection)

    def add_connection(self):
        # Open the connection selection dialog
        selected_connection = simpledialog.askstring("Flight Controller Connection",
                                                     "Enter the connection string to the flight controller. "
                                                     "Examples are:\n\nCOM4 (on windows)\n"
                                                     "/dev/serial/by-id/usb-xxx (on linux)\n"
                                                     "tcp:127.0.0.1:5761\n"
                                                     "udp:udp:127.0.0.1:14551")
        if selected_connection:
            logging_debug(f"Will add new connection: {selected_connection} if not duplicated")
            self.flight_controller.add_connection(selected_connection)
            connection_tuples = self.flight_controller.get_connection_tuples()
            logging_debug(f"Updated connection tuples: {connection_tuples} with selected connection: {selected_connection}")
            self.conn_selection_combobox.set_entries_tupple(connection_tuples, selected_connection)
            self.reconnect(selected_connection)
        else:
            logging_debug(f"Add connection canceled or string empty {selected_connection}")
        return selected_connection

    def reconnect(self, selected_connection: str = None):
        if selected_connection:
            [self.connection_progress_window,
             self.connection_progress_bar,
             self.connection_progress_label] = self.parent.create_progress_window("Connecting with the FC")
            error_message = self.flight_controller.connect(selected_connection, self.update_connection_progress_bar)
            if error_message:
                show_no_connection_error(error_message)
                return True
            self.connection_progress_window.destroy()
            # Store the current connection as the previous selection
            self.previous_selection = self.flight_controller.comport.device
        return False

    def update_connection_progress_bar(self, current_value: int, max_value: int):
        """
        Update the FC connection progress bar and the progress message with the current progress.

        Args:
            current_value (int): The current progress value.
            max_value (int): The maximum progress value.
        """
        self.connection_progress_window.lift()

        self.connection_progress_bar['value'] = current_value
        self.connection_progress_bar['maximum'] = max_value
        self.connection_progress_bar.update()

        # Update the reset progress message
        self.connection_progress_label.config(text=f"waiting for {current_value} of {max_value} seconds")

        # Close the reset progress window when the process is complete
        if current_value == max_value:
            self.connection_progress_window.destroy()


class ConnectionSelectionWindow(BaseWindow):  # pylint: disable=too-few-public-methods
    """
    A window for selecting a flight controller connection.

    This class provides a graphical user interface for selecting a connection to a flight controller.
    It inherits from the BaseWindow class and uses the ConnectionSelectionWidgets class to handle
    the UI elements related to connection selection.
    """
    def __init__(self, flight_controller: FlightController):
        super().__init__()
        self.root.title("Select FC connection")
        self.root.geometry("300x100") # Set the window size

        # Create an instance of ConnectionSelectionWidgets
        self.connection_selection_widgets = ConnectionSelectionWidgets(self, self.root, flight_controller)

        # Pack the ConnectionSelectionWidgets instance to make it visible
        self.connection_selection_widgets.container_frame.pack(expand=False, fill=tk.X, padx=6, pady=6)


def argument_parser():
    """
    Parses command-line arguments for the script.

    This function sets up an argument parser to handle the command-line arguments for the script.

    Returns:
    argparse.Namespace: An object containing the parsed arguments.
    """
    parser = ArgumentParser(description='This main is for testing and development only, '
                            'usually the ConnectionSelectionWidgets is called from another script')
    parser.add_argument('--device',
                        type=str,
                        default="",
                        help='MAVLink connection string to the flight controller. Defaults to autodetection'
                        )  # pylint: disable=R0801
    parser.add_argument('-r', '--reboot-time',
                        type=int,
                        default=7,
                        help='Flight controller reboot time. '
                        'Default is %(default)s')  # pylint: disable=R0801
    parser.add_argument('--loglevel',
                        type=str,
                        default='INFO',
                        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'],
                        help='Logging level (default is INFO).')  # pylint: disable=R0801
    parser.add_argument('-v', '--version',
                        action='version',
                        version=f'%(prog)s {VERSION}',
                        help='Display version information and exit.')  # pylint: disable=R0801
    return parser.parse_args()


if __name__ == "__main__":
    # This main is for testing and development only, usually the ConnectionSelectionWindow is called from another script
    argsp = argument_parser()

    logging_basicConfig(level=logging_getLevelName(argsp.loglevel), format='%(asctime)s - %(levelname)s - %(message)s')

    fc = FlightController(argsp.reboot_time) # Initialize your FlightController instance
    result = fc.connect(device=argsp.device) # Connect to the flight controller
    if result:
        logging_warning(result)
    else:
        window = ConnectionSelectionWindow(fc)
        window.root.mainloop()
    fc.disconnect() # Disconnect from the flight controller
