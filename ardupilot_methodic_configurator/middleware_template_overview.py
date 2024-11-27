"""
Middleware between the flight controller information backend and the GUI fronted.

This file is part of Ardupilot methodic configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

from ardupilot_methodic_configurator import _


class TemplateOverview:  # pylint: disable=too-many-instance-attributes
    """
    Represents a single vehicle template configuration within the ArduPilot Methodic Configurator.

    This class encapsulates the data and attributes associated with a specific vehicle template configuration.
    It is designed to hold information about various components of a drone, such as the flight controller, telemetry system,
    ESCs, propellers, and GNSS Receiver, along with their specifications. The class facilitates easy access to these
    attributes, enabling the GUI to display and select the templates in a structured format.
    """

    def __init__(self, components_data: dict) -> None:
        # The declaration order of these parameters determines the column order in the GUI
        self.fc_manufacturer = components_data.get("Flight Controller", {}).get("Product", {}).get("Manufacturer", "")
        self.fc_model = components_data.get("Flight Controller", {}).get("Product", {}).get("Model", "")
        self.tow_max_kg = components_data.get("Frame", {}).get("Specifications", {}).get("TOW max Kg", "")
        self.prop_diameter_inches = components_data.get("Propellers", {}).get("Specifications", {}).get("Diameter_inches", "")
        self.rc_protocol = components_data.get("RC Receiver", {}).get("FC Connection", {}).get("Protocol", "")
        self.telemetry_model = components_data.get("Telemetry", {}).get("Product", {}).get("Model", "")
        self.esc_protocol = components_data.get("ESC", {}).get("FC Connection", {}).get("Protocol", "")
        self.gnss_model = components_data.get("GNSS Receiver", {}).get("Product", {}).get("Model", "")
        self.gnss_connection = components_data.get("GNSS Receiver", {}).get("FC Connection", {}).get("Type", "")

    @staticmethod
    def columns() -> tuple[str, ...]:
        # Must match the order in the __init__() function above
        return (
            _("Template path"),
            _("FC\nManufacturer"),
            _("FC\nModel"),
            _("TOW Max\n[Kg]"),
            _("Prop Diameter\n[inches]"),
            _("RC\nProtocol"),
            _("Telemetry\nModel"),
            _("ESC\nProtocol"),
            _("GNSS\nModel"),
            _("GNSS\nConnection"),
        )

    def attributes(self) -> list[str]:
        return self.__dict__.keys()  # type: ignore[return-value]
