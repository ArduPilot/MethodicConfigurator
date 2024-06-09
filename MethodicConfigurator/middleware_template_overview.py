#!/usr/bin/env python3

'''
This file is part of Ardupilot methodic configurator. https://github.com/ArduPilot/MethodicConfigurator

(C) 2024 Amilcar do Carmo Lucas

SPDX-License-Identifier:    GPL-3
'''

class TemplateOverview:  # pylint: disable=too-many-instance-attributes
    """
    Represents a single vehicle template configuration within the ArduPilot Methodic Configurator.

    This class encapsulates the data and attributes associated with a specific vehicle template configuration.
    It is designed to hold information about various components of a drone, such as the flight controller, telemetry system,
    ESCs, propellers, and GNSS receiver, along with their specifications. The class facilitates easy access to these
    attributes, enabling the GUI to display and select the templates in a structured format.
    """
    def __init__(self, components_data: dict):
        # The declaration order of these parameters determines the column order in the GUI
        self.fc_manufacturer = components_data.get('Flight Controller', {}).get('Product', {}).get('Manufacturer', '')
        self.fc_model = components_data.get('Flight Controller', {}).get('Product', {}).get('Model', '')
        self.tow_min_kg = components_data.get('Frame', {}).get('Specifications', {}).get('TOW min Kg', '')
        self.tow_max_kg = components_data.get('Frame', {}).get('Specifications', {}).get('TOW max Kg', '')
        self.rc_protocol = components_data.get('RC Receiver', {}).get('FC Connection', {}).get('Protocol', '')
        self.telemetry_model = components_data.get('Telemetry', {}).get('Product', {}).get('Model', '')
        self.esc_protocol = components_data.get('ESC', {}).get('FC Connection', {}).get('Protocol', '')
        self.prop_diameter_inches = components_data.get('Propellers', {}).get('Specifications', {}).get('Diameter_inches', '')
        self.gnss_model = components_data.get('GNSS receiver', {}).get('Product', {}).get('Model', '')

    @staticmethod
    def columns():
        # Must match the order in the __init__() function above
        return ("Template path",
                "FC\nManufacturer",
                "FC\nModel",
                "TOW Min\n[KG]",
                "TOW Max\n[KG]",
                "RC\nProtocol",
                "Telemetry\nModel",
                "ESC\nProtocol",
                "Prop Diameter\n[inches]",
                "GNSS\nModel")

    def attributes(self):
        return self.__dict__.keys()
