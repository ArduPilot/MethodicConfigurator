#!/usr/bin/env python3

'''
This file is part of Ardupilot methodic configurator. https://github.com/ArduPilot/MethodicConfigurator

(C) 2024 Amilcar do Carmo Lucas

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

from MethodicConfigurator.common_arguments import add_common_arguments_and_parse

from MethodicConfigurator.backend_flightcontroller import FlightController

from MethodicConfigurator.frontend_tkinter_base import show_no_connection_error
from MethodicConfigurator.frontend_tkinter_base import show_tooltip
from MethodicConfigurator.frontend_tkinter_base import update_combobox_width
from MethodicConfigurator.frontend_tkinter_base import ProgressWindow
from MethodicConfigurator.frontend_tkinter_base import BaseWindow


# https://dev.to/geraldew/python-tkinter-an-exercise-in-wrapping-the-combobox-ndb
class PairTupleCombobox(ttk.Combobox):  # pylint: disable=too-many-ancestors
    """
    A custom Combobox widget that allows for the display of a list of tuples, where each tuple contains a key and a value.
    This widget processes the list of tuples to separate keys and values for display purposes and allows for the selection
    of a tuple based on its key.
    """
    def process_list_pair_tuple(self, list_pair_tuple):
        r_list_keys = []
        r_list_shows = []
        for tpl in list_pair_tuple:
            r_list_keys.append(tpl[0])
            r_list_shows.append(tpl[1])
        return r_list_keys, r_list_shows

    def __init__(self, container, list_pair_tuple, selected_element, cb_name, *args, **kwargs):
        super().__init__(container, *args, **kwargs)
        self.cb_name = cb_name
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
                logging_critical("%s combobox selected string '%s' not in list %s",
                                 self.cb_name, selected_element, self.list_keys)
                sys_exit(1)
            except ValueError:
                logging_critical("%s combobox selected string '%s' not in list %s",
                                 self.cb_name, selected_element, self.list_keys)
                sys_exit(1)
            update_combobox_width(self)
        else:
            logging_warning("No %s combobox element selected", self.cb_name)

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
    def __init__(self, parent, parent_frame, flight_controller: FlightController,  # pylint: disable=too-many-arguments
                 destroy_parent_on_connect: bool, download_params_on_connect: bool):
        self.parent = parent
        self.flight_controller = flight_controller
        self.destroy_parent_on_connect = destroy_parent_on_connect
        self.download_params_on_connect = download_params_on_connect
        self.previous_selection = flight_controller.comport.device if hasattr(self.flight_controller.comport, "device") \
            else None
        self.connection_progress_window = None

        # Create a new frame for the flight controller connection selection label and combobox
        self.container_frame = ttk.Frame(parent_frame)

        # Create a description label for the flight controller connection selection
        conn_selection_label = ttk.Label(self.container_frame, text="flight controller connection:")
        conn_selection_label.pack(side=tk.TOP) # Add the label to the top of the conn_selection_frame

        # Create a read-only combobox for flight controller connection selection
        self.conn_selection_combobox = PairTupleCombobox(self.container_frame, self.flight_controller.get_connection_tuples(),
                                                         self.previous_selection,
                                                        "FC connection",
                                                         state='readonly')
        self.conn_selection_combobox.bind("<<ComboboxSelected>>", self.on_select_connection_combobox_change)
        self.conn_selection_combobox.pack(side=tk.TOP, pady=(4, 0))
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
                                                     "udp:127.0.0.1:14551")
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

    def reconnect(self, selected_connection: str = ""):  # defaults to auto-connect
        self.connection_progress_window = ProgressWindow(self.parent.root, "Connecting with the FC",
                                                         "Connection step {} of {}")
        error_message = self.flight_controller.connect(selected_connection,
                                                       self.connection_progress_window.update_progress_bar)
        if error_message:
            show_no_connection_error(error_message)
            return True
        self.connection_progress_window.destroy()
        # Store the current connection as the previous selection
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
    def __init__(self, flight_controller: FlightController, connection_result_string: str):
        super().__init__()
        self.root.title("Flight controller connection")
        self.root.geometry("460x450") # Set the window size

        # Explain why we are here
        if flight_controller.comport is None:
            introduction_text = "No ArduPilot flight controller was auto-detected detected yet."
        else:
            if ":" in connection_result_string:
                introduction_text = connection_result_string.replace(":", ":\n")
            else:
                introduction_text = connection_result_string
        self.introduction_label = ttk.Label(self.main_frame, anchor=tk.CENTER, justify=tk.CENTER,
                                            text=introduction_text + "\nChoose one of the following three options:")
        self.introduction_label.pack(expand=False, fill=tk.X, padx=6, pady=6)

        # Option 1 - Auto-connect
        option1_label = ttk.Label(text="Auto-connect to flight controller", style="Bold.TLabel")
        option1_label_frame = ttk.LabelFrame(self.main_frame, labelwidget=option1_label, borderwidth=1, relief="solid")
        option1_label_frame.pack(expand=False, fill=tk.X, padx=6, pady=6)
        option1_label = ttk.Label(option1_label_frame, anchor=tk.CENTER, justify=tk.CENTER,
                                  text="Connect a flight controller to the PC,\n"
                                  "wait 7 seconds for it to fully boot and\n"
                                  "press the Auto-connect button below to connect to it")
        option1_label.pack(expand=False, fill=tk.X, padx=6)
        autoconnect_button = ttk.Button(option1_label_frame, text="Auto-connect", command=self.fc_autoconnect)
        autoconnect_button.pack(expand=False, fill=tk.X, padx=100, pady=6)
        show_tooltip(autoconnect_button, "Auto-connect to a 'Mavlink'-talking serial device")

        # Option 2 - Manually select the flight controller connection or add a new one
        option2_label = ttk.Label(text="Select flight controller connection", style="Bold.TLabel")
        option2_label_frame = ttk.LabelFrame(self.main_frame, labelwidget=option2_label, borderwidth=1, relief="solid")
        option2_label_frame.pack(expand=False, fill=tk.X, padx=6, pady=6)
        option2_label = ttk.Label(option2_label_frame, anchor=tk.CENTER, justify=tk.CENTER,
                                  text="Connect a flight controller to the PC,\n"
                                  "wait 7 seconds for it to fully boot and\n"
                                  "manually select the fight controller connection or add a new one")
        option2_label.pack(expand=False, fill=tk.X, padx=6)
        self.connection_selection_widgets = ConnectionSelectionWidgets(self, option2_label_frame, flight_controller,
                                                                       destroy_parent_on_connect=True,
                                                                       download_params_on_connect=False)
        self.connection_selection_widgets.container_frame.pack(expand=False, fill=tk.X, padx=80, pady=6)

        # Option 3 - Skip FC connection, just edit the .param files on disk
        option3_label = ttk.Label(text="No flight controller connection", style="Bold.TLabel")
        option3_label_frame = ttk.LabelFrame(self.main_frame, labelwidget=option3_label, borderwidth=1, relief="solid")
        option3_label_frame.pack(expand=False, fill=tk.X, padx=6, pady=6)
        #option3_label = ttk.Label(option3_label_frame, anchor=tk.CENTER, justify=tk.CENTER,
        #                          text="Skip the flight controller connection,\n"
        #                          "no default parameter values will be fetched from the FC,\n"
        #                          "default parameter values from disk will be used instead\n"
        #                          "(if '00_default.param' file is present)\n"
        #                          "and just edit the intermediate '.param' files on disk")
        #option3_label.pack(expand=False, fill=tk.X, padx=6)
        skip_fc_connection_button = ttk.Button(option3_label_frame,
                                              text="Skip FC connection, just edit the .param files on disk",
                                              command=lambda flight_controller=flight_controller:
                                              self.skip_fc_connection(flight_controller))
        skip_fc_connection_button.pack(expand=False, fill=tk.X, padx=15, pady=6)
        show_tooltip(skip_fc_connection_button,
                     "No parameter values will be fetched from the FC, default parameter values from disk will be used\n"
                     "instead (if '00_default.param' file is present) and just edit the intermediate '.param' files on disk")

        # Bind the close_connection_and_quit function to the window close event
        self.root.protocol("WM_DELETE_WINDOW", self.close_and_quit)

    def close_and_quit(self):
        sys_exit(0)

    def fc_autoconnect(self):
        self.connection_selection_widgets.reconnect()

    def skip_fc_connection(self, flight_controller: FlightController):
        logging_warning("Will proceed without FC connection. FC parameters will not be downloaded nor uploaded")
        logging_warning("Only the intermediate '.param' files on the PC disk will be edited")
        flight_controller.disconnect()
        self.root.destroy()


def argument_parser():
    """
    Parses command-line arguments for the script.

    This function sets up an argument parser to handle the command-line arguments for the script.

    Returns:
    argparse.Namespace: An object containing the parsed arguments.
    """
    parser = ArgumentParser(description='This main is for testing and development only. '
                            'Usually, the ConnectionSelectionWidgets is called from another script')
    parser = FlightController.add_argparse_arguments(parser)
    return add_common_arguments_and_parse(parser)


def main():
    args = argument_parser()

    logging_basicConfig(level=logging_getLevelName(args.loglevel), format='%(asctime)s - %(levelname)s - %(message)s')

    logging_warning("This main is for testing and development only, usually the ConnectionSelectionWindow is called from "
                    "another script")

    flight_controller = FlightController(args.reboot_time) # Initialize your FlightController instance
    result = flight_controller.connect(device=args.device) # Connect to the flight controller
    if result:
        logging_warning(result)
        window = ConnectionSelectionWindow(flight_controller, result)
        window.root.mainloop()
    flight_controller.disconnect() # Disconnect from the flight controller


if __name__ == "__main__":
    main()
