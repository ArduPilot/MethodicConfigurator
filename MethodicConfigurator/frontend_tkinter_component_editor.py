#!/usr/bin/env python3

'''
This file is part of Ardupilot methodic configurator. https://github.com/ArduPilot/MethodicConfigurator

(C) 2024 Amilcar do Carmo Lucas, IAV GmbH

SPDX-License-Identifier:    GPL-3
'''

from argparse import ArgumentParser

from logging import basicConfig as logging_basicConfig
from logging import getLevelName as logging_getLevelName
# from logging import debug as logging_debug
from logging import info as logging_info

import tkinter as tk
from tkinter import ttk

from common_arguments import add_common_arguments_and_parse

from backend_filesystem import LocalFilesystem

from frontend_tkinter_base import show_tooltip
from frontend_tkinter_base import show_error_message
from frontend_tkinter_base import ScrollFrame
from frontend_tkinter_base import BaseWindow

from version import VERSION


def argument_parser():
    """
    Parses command-line arguments for the script.

    This function sets up an argument parser to handle the command-line arguments for the script.

    Returns:
    argparse.Namespace: An object containing the parsed arguments.
    """
    parser = ArgumentParser(description='A GUI for editing JSON files that contain vehicle component configurations. '
                            'Not to be used directly, but through the main ArduPilot methodic configurator script.')
    parser = LocalFilesystem.add_argparse_arguments(parser)
    parser = ComponentEditorWindow.add_argparse_arguments(parser)
    return add_common_arguments_and_parse(parser)


class VoltageTooLowError(Exception):
    """Raised when the voltage is below the minimum limit."""


class VoltageTooHighError(Exception):
    """Raised when the voltage is above the maximum limit."""


class ComponentEditorWindow(BaseWindow):
    """
    A class for editing JSON files in the ArduPilot methodic configurator.

    This class provides a graphical user interface for editing JSON files that
    contain vehicle component configurations. It inherits from the BaseWindow
    class, which provides basic window functionality.
    """
    def __init__(self, version, local_filesystem: LocalFilesystem=None):
        super().__init__()
        self.local_filesystem = local_filesystem

        self.root.title("Amilcar Lucas's - ArduPilot methodic configurator - " + version + " - Vehicle Component Editor")
        self.root.geometry("880x600") # Set the window width

        self.data = local_filesystem.load_vehicle_components_json_data(local_filesystem.vehicle_dir)
        if len(self.data) < 1:
            # Schedule the window to be destroyed after the mainloop has started
            self.root.after(100, self.root.destroy) # Adjust the delay as needed
            return

        self.entry_widgets = {} # Dictionary for entry widgets

        self.main_frame = ttk.Frame(self.root)
        self.main_frame.pack(side=tk.TOP, fill="x", expand=False, pady=(4, 0)) # Pack the frame at the top of the window

        # Load the vehicle image and scale it down to image_height pixels in height
        if local_filesystem.vehicle_image_exists():
            image_label = self.put_image_in_label(self.main_frame, local_filesystem.vehicle_image_filepath(), 100)
            image_label.pack(side=tk.RIGHT, anchor=tk.NE, padx=(4, 4), pady=(4, 0))
            show_tooltip(image_label, "Replace the vehicle.jpg file in the vehicle directory to change the vehicle image.")
        else:
            image_label = tk.Label(self.main_frame, text="No vehicle.jpg image file found on the vehicle directory.")
            image_label.pack(side=tk.RIGHT, anchor=tk.NE, padx=(4, 4), pady=(4, 0))

        style = ttk.Style()
        style.configure("comb_input_invalid.TCombobox", fieldbackground="red")
        style.configure("comb_input_valid.TCombobox", fieldbackground="white")
        self.chemistry = ""

        self.scroll_frame = ScrollFrame(self.root)
        self.scroll_frame.pack(side="top", fill="both", expand=True)

        self.__populate_frames()

        self.save_button = ttk.Button(self.root, text="Save data and start configuration", command=self.save_data)
        self.save_button.pack(pady=7)

    def __populate_frames(self):
        """
        Populates the ScrollFrame with widgets based on the JSON data.
        """
        if "Components" in self.data:
            for key, value in self.data["Components"].items():
                self.__add_widget(self.scroll_frame.view_port, key, value, [])

    def __add_widget(self, parent, key, value, path):
        """
        Adds a widget to the parent widget with the given key and value.

        Parameters:
        parent (tkinter.Widget): The parent widget to which the LabelFrame/Entry will be added.
        key (str): The key for the LabelFrame/Entry.
        value (dict): The value associated with the key.
        path (list): The path to the current key in the JSON data.
        """
        if isinstance(value, dict):             # JSON non-leaf elements, add LabelFrame widget
            frame = ttk.LabelFrame(parent, text=key)
            is_toplevel = parent == self.scroll_frame.view_port
            side = tk.TOP if is_toplevel else tk.LEFT
            pady = 5 if is_toplevel else 3
            anchor = tk.NW if is_toplevel else tk.N
            frame.pack(fill=tk.X, side=side, pady=pady, padx=5, anchor=anchor)
            for sub_key, sub_value in value.items():
                # recursively add child elements
                self.__add_widget(frame, sub_key, sub_value, path + [key])
        else:                                   # JSON leaf elements, add Entry widget
            entry_frame = ttk.Frame(parent)
            entry_frame.pack(side=tk.TOP, fill=tk.X, pady=(0, 5))

            label = ttk.Label(entry_frame, text=key)
            label.pack(side=tk.LEFT)

            entry = self.add_entry_or_combobox(value, entry_frame, tuple(path+[key]))
            entry.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(0, 5))

            # Store the entry widget in the entry_widgets dictionary for later retrieval
            self.entry_widgets[tuple(path+[key])] = entry

    def save_data(self):
        """
        Saves the edited JSON data back to the file.
        """
        invalid_values = False
        duplicated_connections = False
        fc_connection_types = set()

        for path, entry in self.entry_widgets.items():
            value = entry.get()

            if isinstance(entry, ttk.Combobox):
                if value not in entry.cget("values"):
                    show_error_message("Error", f"Invalid value '{value}' for {'>'.join(list(path))}\n"
                                    f"Allowed values are: {', '.join(entry.cget('values'))}")
                    entry.configure(style="comb_input_invalid.TCombobox")
                    invalid_values = True
                    continue
                if 'FC Connection' in path and 'Type' in path:
                    if value in fc_connection_types and value not in ["CAN1", "CAN2", "I2C1", "I2C2", "I2C3", "I2C4"]:
                        show_error_message("Error", f"Duplicate FC connection type '{value}' for {'>'.join(list(path))}")
                        entry.configure(style="comb_input_invalid.TCombobox")
                        duplicated_connections = True
                        continue
                    fc_connection_types.add(value)
                entry.configure(style="comb_input_valid.TCombobox")

            if path in [('Battery', 'Specifications', 'Volt per cell max'), ('Battery', 'Specifications', 'Volt per cell low'),
                        ('Battery', 'Specifications', 'Volt per cell crit')]:
                self.validate_battery_voltages(None, entry, path)

            # Navigate through the nested dictionaries using the elements of the path
            current_data = self.data["Components"]
            for key in path[:-1]:
                current_data = current_data[key]

            # Update the value in the data dictionary
            current_data[path[-1]] = value

        if invalid_values or duplicated_connections:
            return

        # Save the updated data back to the JSON file
        if self.local_filesystem.save_vehicle_components_json_data(self.data, self.local_filesystem.vehicle_dir):
            show_error_message("Error", "Failed to save data to file. Is the destination write protected?")
        else:
            logging_info("Data saved successfully.")
        self.root.destroy()

    @staticmethod
    def add_argparse_arguments(parser):
        parser.add_argument('--skip-component-editor',
                            action='store_true',
                            help='Skip the component editor window. Only use this if all components have been configured. '
                            'Default to false')
        return parser

    def set_vehicle_type_and_version(self, vehicle_type: str, version: str):
        self.data['Components']['Flight Controller']['Firmware']['Type'] = vehicle_type
        entry = self.entry_widgets[('Flight Controller', 'Firmware', 'Type')]
        entry.delete(0, tk.END)
        entry.insert(0, vehicle_type)
        entry.config(state="disabled")
        if version:
            self.data['Components']['Flight Controller']['Firmware']['Version'] = version
            entry = self.entry_widgets[('Flight Controller', 'Firmware', 'Version')]
            entry.delete(0, tk.END)
            entry.insert(0, version)
            entry.config(state="disabled")

    def add_entry_or_combobox(self, value, entry_frame, path):  # pylint: disable=too-many-return-statements
                                                                # pylint: disable=too-many-statements
        serial_ports = ["SERIAL1", "SERIAL2", "SERIAL3", "SERIAL4", "SERIAL5", "SERIAL6", "SERIAL7", "SERIAL8"]
        can_ports = ["CAN1", "CAN2"]
        i2c_ports = ["I2C1", "I2C2", "I2C3", "I2C4"]

        if path == ('RC Receiver', 'FC Connection', 'Type'):
            cb = ttk.Combobox(entry_frame, values=["RCin/SBUS"] + serial_ports + can_ports)
            cb.bind("<FocusOut>", lambda event, path=path: self.validate_combobox(event, path))
            #cb.bind("<Key>", lambda event, path=path: self.validate_combobox(event, path))
            cb.set(value)
            return cb
        if path == ('RC Receiver', 'FC Connection', 'Protocol'):
            # TODO get this list from RC_PROTOCOLS pdef metadata pylint: disable=fixme
            cb = ttk.Combobox(entry_frame, values=["All", "PPM", "IBUS", "SBUS", "SBUS_NI", "DSM", "SUMD", "SRXL", "SRXL2",
                                                   "CRSF", "ST24", "FPORT", "FPORT2", "FastSBUS", "DroneCAN", "Ghost",
                                                   "MAVRadio"])
            cb.bind("<FocusOut>", lambda event, path=path: self.validate_combobox(event, path))
            cb.set(value)
            return cb
        if path == ('Telemetry', 'FC Connection', 'Type'):
            cb = ttk.Combobox(entry_frame, values=serial_ports + can_ports)
            cb.set(value)
            return cb
        if path == ('Telemetry', 'FC Connection', 'Protocol'):
            # TODO get this list from SERIAL1_PROTOCOL pdef metadata pylint: disable=fixme
            cb = ttk.Combobox(entry_frame, values=["MAVLink1", "MAVLink2", "MAVLink High Latency"])
            cb.bind("<FocusOut>", lambda event, path=path: self.validate_combobox(event, path))
            cb.set(value)
            return cb
        if path == ('Battery Monitor', 'FC Connection', 'Type'):
            cb = ttk.Combobox(entry_frame, values=['Analog'] + i2c_ports + serial_ports + can_ports)
            cb.bind("<FocusOut>", lambda event, path=path: self.validate_combobox(event, path))
            cb.set(value)
            return cb
        if path == ('Battery Monitor', 'FC Connection', 'Protocol'):
            # TODO get this list from BATT_MONITOR pdef metadata pylint: disable=fixme
            cb = ttk.Combobox(entry_frame, values=['Analog Voltage Only', 'Analog Voltage and Current', 'Solo', 'Bebop',
                                                   'SMBus-Generic', 'DroneCAN-BatteryInfo', 'ESC',
                                                   'Sum Of Selected Monitors', 'FuelFlow', 'FuelLevelPWM', 'SMBUS-SUI3',
                                                   'SMBUS-SUI6', 'NeoDesign', 'SMBus-Maxell', 'Generator-Elec',
                                                   'Generator-Fuel', 'Rotoye', 'MPPT', 'INA2XX', 'LTC2946', 'Torqeedo',
                                                   'FuelLevelAnalog', 'Synthetic Current and Analog Voltage', 'INA239_SPI',
                                                   'EFI', 'AD7091R5', 'Scripting'])
            cb.bind("<FocusOut>", lambda event, path=path: self.validate_combobox(event, path))
            cb.set(value)
            return cb
        if path == ('ESC', 'FC Connection', 'Type'):
            cb = ttk.Combobox(entry_frame, values=['Main Out'] + serial_ports + can_ports)
            cb.bind("<FocusOut>", lambda event, path=path: self.validate_combobox(event, path))
            cb.set(value)
            return cb
        if path == ('ESC', 'FC Connection', 'Protocol'):
            # TODO get this list from MOT_PWM_TYPE pdef metadata pylint: disable=fixme
            cb = ttk.Combobox(entry_frame, values=['Normal', 'OneShot', 'OneShot125', 'Brushed', 'DShot150', 'DShot300',
                                                   'DShot600', 'DShot1200', 'PWMRange', 'PWMAngle'])
            cb.bind("<FocusOut>", lambda event, path=path: self.validate_combobox(event, path))
            cb.set(value)
            return cb
        if path == ('GNSS receiver', 'FC Connection', 'Type'):
            cb = ttk.Combobox(entry_frame, values=serial_ports + can_ports)
            cb.bind("<FocusOut>", lambda event, path=path: self.validate_combobox(event, path))
            cb.set(value)
            return cb
        if path == ('GNSS receiver', 'FC Connection', 'Protocol'):
            # TODO get this list from GPS_TYPE pdef metadata pylint: disable=fixme
            cb = ttk.Combobox(entry_frame, values=['Auto', 'uBlox', 'NMEA', 'SiRF', 'HIL', 'SwiftNav', 'DroneCAN', 'SBF',
                                                   'GSOF', 'ERB', 'MAV', 'NOVA', 'HemisphereNMEA',
                                                   'uBlox-MovingBaseline-Base', 'uBlox-MovingBaseline-Rover',
                                                   'MSP', 'AllyStar', 'ExternalAHRS', 'Unicore',
                                                   'DroneCAN-MovingBaseline-Base', 'DroneCAN-MovingBaseline-Rover',
                                                   'UnicoreNMEA', 'UnicoreMovingBaselineNMEA', 'SBF-DualAntenna'])
            cb.bind("<FocusOut>", lambda event, path=path: self.validate_combobox(event, path))
            cb.set(value)
            return cb
        if path == ('Battery', 'Specifications', 'Chemistry'):
            cb = ttk.Combobox(entry_frame, values=['LiIon', 'LiIonSS', 'LiIonSSHV', 'Lipo', 'LipoHV', 'LipoHVSS'])
            cb.bind("<FocusOut>", lambda event, path=path: self.validate_combobox(event, path))
            cb.set(value)
            self.chemistry = value
            return cb

        entry = ttk.Entry(entry_frame)
        if path in [('Battery', 'Specifications', 'Volt per cell max'), ('Battery', 'Specifications', 'Volt per cell low'),
                    ('Battery', 'Specifications', 'Volt per cell crit')]:
            entry.bind("<FocusOut>", lambda event, entry=entry, path=path: self.validate_battery_voltages(event, entry, path))
        entry.insert(0, str(value))
        return entry

    def validate_combobox(self, event, path):
        """
        Validates the value of a combobox.
        """
        combobox = event.widget # Get the combobox widget that triggered the event
        value = combobox.get() # Get the current value of the combobox
        allowed_values = combobox.cget("values") # Get the list of allowed values

        if value not in allowed_values:
            if event.type == 10:
                show_error_message("Error", f"Invalid value '{value}' for {'>'.join(list(path))}\n"
                                   f"Allowed values are: {', '.join(allowed_values)}")
            combobox.configure(style="comb_input_invalid.TCombobox")
        else:
            combobox.configure(style="comb_input_valid.TCombobox")

        if path == ('Battery', 'Specifications', 'Chemistry'):
            self.chemistry = value

    def validate_battery_voltages(self, _event, entry, path):
        """
        Validates the value of a battery voltage entry.
        """
        value = entry.get()
        try:
            voltage = float(value)
            if voltage < self.volt_limit_min:
                entry.delete(0, tk.END)
                entry.insert(0, self.volt_limit_min)
                raise VoltageTooLowError(f"is below the {self.chemistry} minimum limit of {self.volt_limit_min}")
            if voltage > self.volt_limit_max:
                entry.delete(0, tk.END)
                entry.insert(0, self.volt_limit_max)
                raise VoltageTooHighError(f"is above the {self.chemistry} maximum limit of {self.volt_limit_max}")
        except (VoltageTooLowError, VoltageTooHighError) as e:
            show_error_message("Error", f"Invalid value '{value}' for {'>'.join(list(path))}\n"
                                f"{e}")
        except ValueError as e:
            show_error_message("Error", f"Invalid value '{value}' for {'>'.join(list(path))}\n"
                            f"{e}")
            entry.delete(0, tk.END)
            entry.insert(0, "3.8")

    @property
    def volt_limit_min(self) -> float:  # pylint: disable=too-many-return-statements
        if self.chemistry == 'LiIon':
            return 2.5
        if self.chemistry == 'LiIonSS':
            return 2.4
        if self.chemistry == 'LiIonSSHV':
            return 2.4
        if self.chemistry == 'Lipo':
            return 3.0
        if self.chemistry == 'LipoHV':
            return 3.0
        if self.chemistry == 'LipoHVSS':
            return 2.9
        return 2.4

    @property
    def volt_limit_max(self) -> float:  # pylint: disable=too-many-return-statements
        if self.chemistry == 'LiIon':
            return 4.1
        if self.chemistry == 'LiIonSS':
            return 4.2
        if self.chemistry == 'LiIonSSHV':
            return 4.45
        if self.chemistry == 'Lipo':
            return 4.2
        if self.chemistry == 'LipoHV':
            return 4.35
        if self.chemistry == 'LipoHVSS':
            return 4.2
        return 4.45

if __name__ == "__main__":
    args = argument_parser()

    logging_basicConfig(level=logging_getLevelName(args.loglevel), format='%(asctime)s - %(levelname)s - %(message)s')

    filesystem = LocalFilesystem(args.vehicle_dir, args.vehicle_type)
    app = ComponentEditorWindow(VERSION, filesystem)
    app.root.mainloop()
