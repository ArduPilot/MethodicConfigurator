#!/usr/bin/env python3

'''
This file is part of Ardupilot methodic configurator. https://github.com/ArduPilot/MethodicConfigurator

(C) 2024 Amilcar do Carmo Lucas

SPDX-License-Identifier:    GPL-3
'''

from argparse import ArgumentParser

from logging import basicConfig as logging_basicConfig
from logging import getLevelName as logging_getLevelName
# from logging import debug as logging_debug
#from logging import info as logging_info

import tkinter as tk
from tkinter import ttk

from MethodicConfigurator.common_arguments import add_common_arguments_and_parse

from MethodicConfigurator.backend_filesystem import LocalFilesystem

from MethodicConfigurator.battery_cell_voltages import BatteryCell

from MethodicConfigurator.frontend_tkinter_component_editor_base import ComponentEditorWindowBase

#from MethodicConfigurator.frontend_tkinter_base import show_tooltip
from MethodicConfigurator.frontend_tkinter_base import show_error_message

from MethodicConfigurator.version import VERSION


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

class ComponentEditorWindow(ComponentEditorWindowBase):
    """
    This class validates the user input and handles user interactions
    for editing component configurations in the ArduPilot Methodic Configurator.
    """
    def __init__(self, version, local_filesystem: LocalFilesystem=None):
        ComponentEditorWindowBase.__init__(self, version, local_filesystem)
        style = ttk.Style()
        style.configure("comb_input_invalid.TCombobox", fieldbackground="red")
        style.configure("comb_input_valid.TCombobox", fieldbackground="white")
        style.configure("entry_input_invalid.TEntry", fieldbackground="red")
        style.configure("entry_input_valid.TEntry", fieldbackground="white")

    def update_json_data(self):
        super().update_json_data()
        if 'Components' not in self.data:
            self.data['Components'] = {}
        if 'Battery' not in self.data['Components']:
            self.data['Components']['Battery'] = {}
        if 'Specifications' not in self.data['Components']['Battery']:
            self.data['Components']['Battery']['Specifications'] = {}
        if 'Chemistry' not in self.data['Components']['Battery']['Specifications']:
            self.data['Components']['Battery']['Specifications']['Chemistry'] = "Lipo"
        if 'Capacity mAh' not in self.data['Components']['Battery']['Specifications']:
            self.data['Components']['Battery']['Specifications']['Capacity mAh'] = 0
        if 'Frame' not in self.data['Components']:
            self.data['Components']['Frame'] = {}
        if 'Specifications' not in self.data['Components']['Frame']:
            self.data['Components']['Frame']['Specifications'] = {}
        if 'TOW min Kg' not in self.data['Components']['Frame']['Specifications']:
            self.data['Components']['Frame']['Specifications']['TOW min Kg'] = 1
        if 'TOW max Kg' not in self.data['Components']['Frame']['Specifications']:
            self.data['Components']['Frame']['Specifications']['TOW max Kg'] = 1

    def set_component_value_and_update_ui(self, path: tuple, value: str):
        data_path = self.data['Components']
        for key in path[:-1]:
            data_path = data_path[key]
        data_path[path[-1]] = value
        entry = self.entry_widgets[path]
        entry.delete(0, tk.END)
        entry.insert(0, value)
        entry.config(state="disabled")

    def set_vehicle_type_and_version(self, vehicle_type: str, version: str):
        self.set_component_value_and_update_ui(('Flight Controller', 'Firmware', 'Type'), vehicle_type)
        if version:
            self.set_component_value_and_update_ui(('Flight Controller', 'Firmware', 'Version'), version)

    def set_fc_manufacturer(self, manufacturer: str):
        if manufacturer and manufacturer!= "Unknown" and manufacturer!= "ArduPilot":
            self.set_component_value_and_update_ui(('Flight Controller', 'Product', 'Manufacturer'), manufacturer)

    def set_fc_model(self, model: str):
        if model and model!= "Unknown" and model!= "MAVLink":
            self.set_component_value_and_update_ui(('Flight Controller', 'Product', 'Model'), model)

    @staticmethod
    def reverse_key_search(doc: dict, param_name: str, values: list) -> list:
        return [key for key, value in doc[param_name]["values"].items() if value in values]

    def set_values_from_fc_parameters(self, fc_parameters: dict, doc: dict):
        serial_ports = ["SERIAL1", "SERIAL2", "SERIAL3", "SERIAL4", "SERIAL5", "SERIAL6", "SERIAL7", "SERIAL8"]
        #can_ports = ["CAN1", "CAN2"]
        #i2c_ports = ["I2C1", "I2C2", "I2C3", "I2C4"]

        rc_receiver_protocols = self.reverse_key_search(doc, "SERIAL1_PROTOCOL", ["RC Input"])
        telemetry_protocols = self.reverse_key_search(doc, "SERIAL1_PROTOCOL",
                                                      ["MAVLink1", "MAVLink2", "MAVLink High Latency"])
        gnss_protocols = self.reverse_key_search(doc, "SERIAL1_PROTOCOL", ["GPS"])
        esc_protocols = self.reverse_key_search(doc, "SERIAL1_PROTOCOL", ["ESC Telemetry", "FETtecOneWire", "CoDevESC"])
        for serial in serial_ports:
            if serial + "_PROTOCOL" in fc_parameters:
                if fc_parameters[serial + "_PROTOCOL"] in rc_receiver_protocols:
                    self.data['Components']['RC Receiver']['FC Connection']['Type'] = serial
                    #self.data['Components']['RC Receiver']['FC Connection']['Protocol'] = \
                    # doc['RC_PROTOCOLS']['values'][fc_parameters['RC_PROTOCOLS']]
                elif fc_parameters[serial + "_PROTOCOL"] in telemetry_protocols:
                    self.data['Components']['Telemetry']['FC Connection']['Type'] = serial
                    self.data['Components']['Telemetry']['FC Connection']['Protocol'] = \
                        doc[serial + "_PROTOCOL"]['values'][str(fc_parameters[serial + "_PROTOCOL"]).rstrip('0').rstrip('.')]
                elif fc_parameters[serial + "_PROTOCOL"] in gnss_protocols:
                    self.data['Components']['GNSS Receiver']['FC Connection']['Type'] = serial
                    self.data['Components']['GNSS Receiver']['FC Connection']['Protocol'] = \
                        doc['GPS_TYPE']['values'][str(fc_parameters['GPS_TYPE']).rstrip('0').rstrip('.')]
                elif fc_parameters[serial + "_PROTOCOL"] in esc_protocols:
                    self.data['Components']['ESC']['FC Connection']['Type'] = serial
                    self.data['Components']['ESC']['FC Connection']['Protocol'] = \
                        doc['MOT_PWM_TYPE']['values'][str(fc_parameters['MOT_PWM_TYPE']).rstrip('0').rstrip('.')]
        if "BATT_MONITOR" in fc_parameters:
            analog = [key for key, value in doc["BATT_MONITOR"]["values"].items() \
                      if value in ['Analog Voltage Only', 'Analog Voltage and Current']]
            if fc_parameters["BATT_MONITOR"] in analog:
                self.data['Components']['Battery Monitor']['FC Connection']['Type'] = "Analog"
            self.data['Components']['Battery Monitor']['FC Connection']['Protocol'] = \
                doc['BATT_MONITOR']['values'][str(fc_parameters["BATT_MONITOR"]).rstrip('0').rstrip('.')]

    def add_entry_or_combobox(self, value, entry_frame, path):
        serial_ports = ["SERIAL1", "SERIAL2", "SERIAL3", "SERIAL4", "SERIAL5", "SERIAL6", "SERIAL7", "SERIAL8"]
        can_ports = ["CAN1", "CAN2"]
        i2c_ports = ["I2C1", "I2C2", "I2C3", "I2C4"]

        combobox_config = {
            ('Flight Controller', 'Firmware', 'Type'): {
                "values": LocalFilesystem.supported_vehicles(),
            },
            ('RC Receiver', 'FC Connection', 'Type'): {
                "values": ["RCin/SBUS"] + serial_ports + can_ports,
            },
            ('RC Receiver', 'FC Connection', 'Protocol'): {
                "values": ["All", "PPM", "IBUS", "SBUS", "SBUS_NI", "DSM", "SUMD", "SRXL", "SRXL2",
                           "CRSF", "ST24", "FPORT", "FPORT2", "FastSBUS", "DroneCAN", "Ghost", "MAVRadio"],
            },
            ('Telemetry', 'FC Connection', 'Type'): {
                "values": serial_ports + can_ports,
            },
            ('Telemetry', 'FC Connection', 'Protocol'): {
                # TODO get this list from SERIAL1_PROTOCOL pdef metadata pylint: disable=fixme
                "values": ["MAVLink1", "MAVLink2", "MAVLink High Latency"],
            },
            ('Battery Monitor', 'FC Connection', 'Type'): {
                "values": ['Analog'] + i2c_ports + serial_ports + can_ports,
            },
            ('Battery Monitor', 'FC Connection', 'Protocol'): {
                # TODO get this list from BATT_MONITOR pdef metadata pylint: disable=fixme
                "values": ['Analog Voltage Only', 'Analog Voltage and Current', 'Solo', 'Bebop', 'SMBus-Generic',
                           'DroneCAN-BatteryInfo', 'ESC', 'Sum Of Selected Monitors', 'FuelFlow', 'FuelLevelPWM',
                           'SMBUS-SUI3', 'SMBUS-SUI6', 'NeoDesign', 'SMBus-Maxell', 'Generator-Elec', 'Generator-Fuel',
                           'Rotoye', 'MPPT', 'INA2XX', 'LTC2946', 'Torqeedo', 'FuelLevelAnalog',
                           'Synthetic Current and Analog Voltage', 'INA239_SPI', 'EFI', 'AD7091R5', 'Scripting'],
            },
            ('ESC', 'FC Connection', 'Type'): {
                "values": ['Main Out', 'AIO'] + serial_ports + can_ports,
            },
            ('ESC', 'FC Connection', 'Protocol'): {
                # TODO get this list from MOT_PWM_TYPE pdef metadata pylint: disable=fixme
                "values": ['Normal', 'OneShot', 'OneShot125', 'Brushed', 'DShot150', 'DShot300', 'DShot600',
                           'DShot1200', 'PWMRange', 'PWMAngle'],
            },
            ('GNSS receiver', 'FC Connection', 'Type'): {
                "values": serial_ports + can_ports,
            },
            ('GNSS receiver', 'FC Connection', 'Protocol'): {
                # TODO get this list from GPS_TYPE pdef metadata pylint: disable=fixme
                "values": ['Auto', 'uBlox', 'NMEA', 'SiRF', 'HIL', 'SwiftNav', 'DroneCAN', 'SBF', 'GSOF', 'ERB',
                           'MAV', 'NOVA', 'HemisphereNMEA', 'uBlox-MovingBaseline-Base', 'uBlox-MovingBaseline-Rover',
                           'MSP', 'AllyStar', 'ExternalAHRS', 'Unicore', 'DroneCAN-MovingBaseline-Base',
                           'DroneCAN-MovingBaseline-Rover', 'UnicoreNMEA', 'UnicoreMovingBaselineNMEA', 'SBF-DualAntenna'],
            },
            ('Battery', 'Specifications', 'Chemistry'): {
                "values": BatteryCell.chemistries(),
            },
        }
        config = combobox_config.get(path)
        if config:
            cb = ttk.Combobox(entry_frame, values=config["values"])
            cb.bind("<FocusOut>", lambda event, path=path: self.validate_combobox(event, path))
            cb.bind("<KeyRelease>", lambda event, path=path: self.validate_combobox(event, path))
            cb.set(value)
            return cb

        entry = ttk.Entry(entry_frame)
        entry_config = {
            ('Battery', 'Specifications', 'Volt per cell max'): {
                "type": float,
                "validate": lambda event, entry=entry, path=path: self.validate_cell_voltage(event, entry, path),
            },
            ('Battery', 'Specifications', 'Volt per cell low'): {
                "type": float,
                "validate": lambda event, entry=entry, path=path: self.validate_cell_voltage(event, entry, path),
            },
            ('Battery', 'Specifications', 'Volt per cell crit'): {
                "type": float,
                "validate": lambda event, entry=entry, path=path: self.validate_cell_voltage(event, entry, path),
            },
            ('Battery', 'Specifications', 'Number of cells'): {
                "type": int,
                "validate": lambda event, entry=entry, path=path: self.validate_nr_cells(event, entry, path),
            },
            ('Motors', 'Specifications', 'Poles'): {
                "type": int,
                "validate": lambda event, entry=entry, path=path: self.validate_motor_poles(event, entry, path),
            },
            ('Propellers', 'Specifications', 'Diameter_inches'): {
                "type": int,
                "validate": lambda event, entry=entry, path=path: self.validate_propeller(event, entry, path),
            },
        }
        config = entry_config.get(path)
        if config:
            entry.bind("<FocusOut>", config["validate"])
            entry.bind("<KeyRelease>", config["validate"])
        entry.insert(0, str(value))
        return entry

    def validate_combobox(self, event, path) -> bool:
        """
        Validates the value of a combobox.
        """
        combobox = event.widget # Get the combobox widget that triggered the event
        value = combobox.get() # Get the current value of the combobox
        allowed_values = combobox.cget("values") # Get the list of allowed values

        if value not in allowed_values:
            if event.type == "10": # FocusOut events
                show_error_message("Error", f"Invalid value '{value}' for {'>'.join(list(path))}\n"
                                   f"Allowed values are: {', '.join(allowed_values)}")
            combobox.configure(style="comb_input_invalid.TCombobox")
            return False
        combobox.configure(style="comb_input_valid.TCombobox")
        return True

    def validate_cell_voltage(self, event, entry, path):  # pylint: disable=too-many-branches
        """
        Validates the value of a battery cell voltage entry.
        """
        chemistry_path = ('Battery', 'Specifications', 'Chemistry')
        if chemistry_path not in self.entry_widgets:
            show_error_message("Error", "Battery Chemistry not set. Will default to Lipo.")
            chemistry = "Lipo"
        else:
            chemistry = self.entry_widgets[chemistry_path].get()
        value = entry.get()
        is_focusout_event = event and event.type == "10"
        try:
            voltage = float(value)
            if voltage < BatteryCell.limit_min_voltage(chemistry):
                if is_focusout_event:
                    entry.delete(0, tk.END)
                    entry.insert(0, BatteryCell.limit_min_voltage(chemistry))
                raise VoltageTooLowError(f"is below the {chemistry} minimum limit of "
                                         f"{BatteryCell.limit_min_voltage(chemistry)}")
            if voltage > BatteryCell.limit_max_voltage(chemistry):
                if is_focusout_event:
                    entry.delete(0, tk.END)
                    entry.insert(0, BatteryCell.limit_max_voltage(chemistry))
                raise VoltageTooHighError(f"is above the {chemistry} maximum limit of "
                                          f"{BatteryCell.limit_max_voltage(chemistry)}")
        except (VoltageTooLowError, VoltageTooHighError) as e:
            if is_focusout_event:
                show_error_message("Error", f"Invalid value '{value}' for {'>'.join(list(path))}\n"
                                   f"{e}")
            else:
                entry.configure(style="entry_input_invalid.TEntry")
                return False
        except ValueError as e:
            if is_focusout_event:
                show_error_message("Error", f"Invalid value '{value}' for {'>'.join(list(path))}\n"
                                f"{e}\nWill be set to the recommended value.")
                entry.delete(0, tk.END)
                if path[-1] == "Volt per cell max":
                    entry.insert(0, str(BatteryCell.recommended_max_voltage(chemistry)))
                elif path[-1] == "Volt per cell low":
                    entry.insert(0, str(BatteryCell.recommended_low_voltage(chemistry)))
                elif path[-1] == "Volt per cell crit":
                    entry.insert(0, str(BatteryCell.recommended_crit_voltage(chemistry)))
                else:
                    entry.insert(0, "3.8")
            else:
                entry.configure(style="entry_input_invalid.TEntry")
                return False
        entry.configure(style="entry_input_valid.TEntry")
        return True

    def validate_nr_cells(self, event, entry, path):
        is_focusout_event = event and event.type == "10"
        try:
            value = int(entry.get())
            if value < 1 or value > 50:
                entry.configure(style="entry_input_invalid.TEntry")
                raise ValueError("Nr of cells must be an integer between 1 and 50")
        except ValueError as e:
            if is_focusout_event:
                show_error_message("Error", f"Invalid value '{value}' for {'>'.join(list(path))}\n{e}")
            return False
        entry.configure(style="entry_input_valid.TEntry")
        return True

    def validate_motor_poles(self, event, entry, path):
        is_focusout_event = event and event.type == "10"
        try:
            value = int(entry.get())
            if value < 3 or value > 50:
                entry.configure(style="entry_input_invalid.TEntry")
                raise ValueError("Motor poles must be an integer between 3 and 50")
        except ValueError as e:
            if is_focusout_event:
                show_error_message("Error", f"Invalid value '{value}' for {'>'.join(list(path))}\n{e}")
            return False
        entry.configure(style="entry_input_valid.TEntry")
        return True

    def validate_propeller(self, event, entry, path):
        is_focusout_event = event and event.type == "10"
        try:
            value = float(entry.get())
            if value < 0.3 or value > 400:
                entry.configure(style="entry_input_invalid.TEntry")
                raise ValueError("Propeller diameter in inches must be a float between 0.3 and 400")
        except ValueError as e:
            if is_focusout_event:
                show_error_message("Error", f"Invalid value '{value}' for {'>'.join(list(path))}\n{e}")
            return False
        entry.configure(style="entry_input_valid.TEntry")
        return True

    def save_data(self):
        if self.validate_data():
            ComponentEditorWindowBase.save_data(self)

    def validate_data(self):  # pylint: disable=too-many-branches
        invalid_values = False
        duplicated_connections = False
        fc_serial_connection = {}

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
                    if value in fc_serial_connection and value not in ["CAN1", "CAN2", "I2C1", "I2C2", "I2C3", "I2C4"]:
                        if path[0] in ['Telemetry', 'RC Receiver'] and \
                           fc_serial_connection[value] in ['Telemetry', 'RC Receiver']:
                            entry.configure(style="comb_input_valid.TCombobox")
                            continue  # Allow telemetry and RC Receiver connections using the same SERIAL port
                        show_error_message("Error", f"Duplicate FC connection type '{value}' for {'>'.join(list(path))}")
                        entry.configure(style="comb_input_invalid.TCombobox")
                        duplicated_connections = True
                        continue
                    fc_serial_connection[value] = path[0]
                entry.configure(style="comb_input_valid.TCombobox")

            if path in [('Battery', 'Specifications', 'Volt per cell max'), ('Battery', 'Specifications', 'Volt per cell low'),
                        ('Battery', 'Specifications', 'Volt per cell crit')]:
                if not self.validate_cell_voltage(None, entry, path):
                    invalid_values = True
            if path == ('Battery', 'Specifications', 'Volt per cell low'):
                if value >= self.entry_widgets[('Battery', 'Specifications', 'Volt per cell max')].get():
                    show_error_message("Error", "Battery Cell Low voltage must be lower than max voltage")
                    entry.configure(style="entry_input_invalid.TEntry")
                    invalid_values = True
            if path == ('Battery', 'Specifications', 'Volt per cell crit'):
                if value >= self.entry_widgets[('Battery', 'Specifications', 'Volt per cell low')].get():
                    show_error_message("Error", "Battery Cell Crit voltage must be lower than low voltage")
                    entry.configure(style="entry_input_invalid.TEntry")
                    invalid_values = True
            if path == ('Battery', 'Specifications', 'Number of cells'):
                if not self.validate_nr_cells(None, entry, path):
                    invalid_values = True
            if path == ('Motors', 'Specifications', 'Poles'):
                if not self.validate_motor_poles(None, entry, path):
                    invalid_values = True
            if path == ('Propellers', 'Specifications', 'Diameter_inches'):
                if not self.validate_propeller(None, entry, path):
                    invalid_values = True

        return not (invalid_values or duplicated_connections)


if __name__ == "__main__":
    args = argument_parser()

    logging_basicConfig(level=logging_getLevelName(args.loglevel), format='%(asctime)s - %(levelname)s - %(message)s')

    filesystem = LocalFilesystem(args.vehicle_dir, args.vehicle_type, args.allow_editing_template_files)
    app = ComponentEditorWindow(VERSION, filesystem)
    app.root.mainloop()
