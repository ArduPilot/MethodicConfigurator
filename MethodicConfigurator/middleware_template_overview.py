#!/usr/bin/env python3

'''
This file is part of Ardupilot methodic configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
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
        self.tow_max_kg = components_data.get('Frame', {}).get('Specifications', {}).get('TOW max Kg', '')
        self.prop_diameter_inches = components_data.get('Propellers', {}).get('Specifications', {}).get('Diameter_inches', '')
        self.rc_protocol = components_data.get('RC Receiver', {}).get('FC Connection', {}).get('Protocol', '')
        self.telemetry_model = components_data.get('Telemetry', {}).get('Product', {}).get('Model', '')
        self.esc_protocol = components_data.get('ESC', {}).get('FC Connection', {}).get('Protocol', '')
        self.gnss_model = components_data.get('GNSS receiver', {}).get('Product', {}).get('Model', '')
        self.gnss_connection = components_data.get('GNSS receiver', {}).get('FC Connection', {}).get('Type', '')

    @staticmethod
    def columns():
        # Must match the order in the __init__() function above
        return ("Template path",
                "FC\nManufacturer",
                "FC\nModel",
                "TOW Max\n[KG]",
                "Prop Diameter\n[inches]",
                "RC\nProtocol",
                "Telemetry\nModel",
                "ESC\nProtocol",
                "GNSS\nModel",
                "GNSS\nConnection",
                )

    def attributes(self):
        return self.__dict__.keys()
