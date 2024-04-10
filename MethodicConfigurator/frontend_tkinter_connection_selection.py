#!/usr/bin/env python3

'''
This file is part of Ardupilot methodic configurator. https://github.com/ArduPilot/MethodicConfigurator

(C) 2024 Amilcar do Carmo Lucas, IAV GmbH

SPDX-License-Identifier:    GPL-3
'''

import tkinter as tk
from tkinter import ttk
from tkinter import simpledialog
from logging import debug as logging_debug
from logging import warning as logging_warning
from logging import critical as logging_critical

from backend_flightcontroller import FlightController

from frontend_tkinter_base import show_no_connection_error
from frontend_tkinter_base import show_tooltip
from frontend_tkinter_base import update_combobox_width


# https://dev.to/geraldew/python-tkinter-an-exercise-in-wrapping-the-combobox-ndb
class PairTupleCombobox(ttk.Combobox):

    def _process_listPairTuple(self, ip_listPairTuple):
        r_list_keys = []
        r_list_shows = []
        for tpl in ip_listPairTuple:
            r_list_keys.append(tpl[0])
            r_list_shows.append(tpl[1])
        return r_list_keys, r_list_shows

    def __init__(self, container, p_listPairTuple, selected_element, *args, **kwargs):
        super().__init__(container, *args, **kwargs)
        self.set_entries_tupple(p_listPairTuple, selected_element)

    def set_entries_tupple(self, p_listPairTuple, selected_element):
        self.list_keys, self.list_shows = self._process_listPairTuple(p_listPairTuple)
        self['values'] = tuple(self.list_shows)
        # still need to set the default value from the nominated key
        if selected_element:
            try:
                default_key_index = self.list_keys.index(selected_element)
                self.current(default_key_index)
            except IndexError:
                logging_critical("connection combobox selected string '%s' not in list %s", selected_element, self.list_keys)
                exit(1)
            except ValueError:
                logging_critical("connection combobox selected string '%s' not in list %s", selected_element, self.list_keys)
                exit(1)
            update_combobox_width(self)
        else:
            logging_warning("No connection combobox element selected")

    def getSelectedKey(self):
        try:
            i_index = self.current()
            return self.list_keys[i_index]
        except IndexError:
            return None


class ConnectionSelectionWindow():
    def __init__(self, parent, parent_frame, flight_controller: FlightController):
        self.parent = parent
        self.flight_controller = flight_controller
        self.previous_selection = flight_controller.comport.device if hasattr(self.flight_controller.comport, "device") \
            else None

        # Create a new frame for the flight controller connection selection label and combobox
        conn_selection_frame = tk.Frame(parent_frame)
        conn_selection_frame.pack(side=tk.RIGHT, fill="x", expand=False, padx=(6, 4))

        # Create a description label for the flight controller connection selection
        conn_selection_label = tk.Label(conn_selection_frame, text="flight controller connection:")
        conn_selection_label.pack(side=tk.TOP, anchor=tk.NW) # Add the label to the top of the conn_selection_frame

        # Create a read-only combobox for flight controller connection selection
        self.conn_selection_combobox = PairTupleCombobox(conn_selection_frame, self.flight_controller.get_connection_tuples(),
                                                         self.previous_selection,
                                                         state='readonly')
        self.conn_selection_combobox.bind("<<ComboboxSelected>>", self.on_select_connection_combobox_change)
        self.conn_selection_combobox.pack(side=tk.TOP, anchor=tk.NW, pady=(4, 0))
        show_tooltip(self.conn_selection_combobox, "Select the flight controller connection\nYou can add a custom connection "
                     "to the existing ones")

    def on_select_connection_combobox_change(self, _event):
        selected_connection = self.conn_selection_combobox.getSelectedKey()
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
            self.previous_selection = self.flight_controller.comport.device # Store the current connection as the previous selection
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
