"""
Data model for vehicle components import from FC parameters.

This file is part of Ardupilot methodic configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2025 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

# from logging import debug as logging_debug
from logging import error as logging_error
from math import log2
from typing import Any

from ardupilot_methodic_configurator import _
from ardupilot_methodic_configurator.data_model_vehicle_components_base import ComponentDataModelBase
from ardupilot_methodic_configurator.data_model_vehicle_components_validation import (
    BATT_MONITOR_CONNECTION,
    CAN_PORTS,
    GNSS_RECEIVER_CONNECTION,
    MOT_PWM_TYPE_DICT,
    RC_PROTOCOLS_DICT,
    SERIAL_PORTS,
    SERIAL_PROTOCOLS_DICT,
)


class ComponentDataModelImport(ComponentDataModelBase):
    """
    A class to handle component data import from FC parameters separate from UI logic.

    This improves testability by isolating data operations.
    """

    def is_fc_manufacturer_valid(self, manufacturer: str) -> bool:
        """Is flight controller manufacturer data valid."""
        return bool(manufacturer and manufacturer not in (_("Unknown"), "ArduPilot"))

    def is_fc_model_valid(self, model: str) -> bool:
        """Is flight controller model data valid."""
        return bool(model and model not in (_("Unknown"), "MAVLink"))

    @staticmethod
    def _reverse_key_search(
        doc: dict[str, dict[str, dict[str, float]]], param_name: str, values: list[float], fallbacks: list[int]
    ) -> list[int]:
        """
        Search for keys in documentation that have specified values.

        Used to find parameter keys from parameter values.
        """
        retv = [int(key) for key, value in doc[param_name]["values"].items() if value in values]
        if len(values) != len(fallbacks):
            logging_error(_("Length of values %u and fallbacks %u differ for %s"), len(values), len(fallbacks), param_name)
        if retv:
            return retv
        logging_error(_("No values found for %s in the metadata"), param_name)
        return fallbacks

    def _verify_dict_is_uptodate(
        self, doc: dict[str, Any], dict_to_check: dict[str, dict[str, Any]], doc_key: str, doc_dict: str
    ) -> bool:
        """
        Verify that a dictionary is up-to-date with the apm.pdef.xml documentation metadata.

        Returns True if valid, False if there are discrepancies.
        """
        is_valid = True
        if not doc or doc_key not in doc or not doc[doc_key] or doc_dict not in doc[doc_key]:
            return False

        for key, doc_protocol in doc[doc_key][doc_dict].items():
            if key in dict_to_check:
                code_protocol = dict_to_check[key].get("protocol", None)
                if code_protocol != doc_protocol:
                    logging_error(_("Protocol %s does not match %s in %s metadata"), code_protocol, doc_protocol, doc_key)
                    is_valid = False
            else:
                logging_error(_("Protocol %s not found in %s metadata"), doc_protocol, doc_key)
                is_valid = False
        return is_valid

    def process_fc_parameters(
        self,
        fc_parameters: dict[str, Any],
        doc: dict[str, Any],
    ) -> None:
        """
        Process flight controller parameters and update the data model accordingly.

        This method consolidates all parameter processing logic in one place.
        """
        # First verify dictionaries match documentation
        self._verify_dict_is_uptodate(doc, SERIAL_PROTOCOLS_DICT, "SERIAL1_PROTOCOL", "values")
        self._verify_dict_is_uptodate(doc, BATT_MONITOR_CONNECTION, "BATT_MONITOR", "values")
        self._verify_dict_is_uptodate(doc, GNSS_RECEIVER_CONNECTION, "GPS_TYPE", "values")
        self._verify_dict_is_uptodate(doc, MOT_PWM_TYPE_DICT, "MOT_PWM_TYPE", "values")
        self._verify_dict_is_uptodate(doc, RC_PROTOCOLS_DICT, "RC_PROTOCOLS", "Bitmask")

        # Process parameters in sequence
        self._set_gnss_type_from_fc_parameters(fc_parameters)
        esc_is_serial = self._set_serial_type_from_fc_parameters(fc_parameters)
        if not esc_is_serial:
            self._set_esc_type_from_fc_parameters(fc_parameters, doc)

        self._set_battery_type_from_fc_parameters(fc_parameters)
        self._set_motor_poles_from_fc_parameters(fc_parameters)

    def _set_gnss_type_from_fc_parameters(self, fc_parameters: dict) -> None:
        """Process GNSS receiver parameters and update the data model."""
        gps1_type = fc_parameters.get("GPS_TYPE", 0)
        try:
            gps1_type = int(gps1_type)
        except (ValueError, TypeError):
            logging_error(_("Invalid non-integer value for GPS_TYPE %s"), gps1_type)
            gps1_type = 0

        if str(gps1_type) in GNSS_RECEIVER_CONNECTION:
            gps1_connection_type = GNSS_RECEIVER_CONNECTION[str(gps1_type)].get("type")
            gps1_connection_protocol = GNSS_RECEIVER_CONNECTION[str(gps1_type)].get("protocol")
            if gps1_connection_type == "None":
                self.set_component_value(("GNSS Receiver", "FC Connection", "Type"), "None")
                self.set_component_value(("GNSS Receiver", "FC Connection", "Protocol"), "None")
            elif gps1_connection_type in SERIAL_PORTS:
                # GNSS connection type will be detected later in set_serial_type_from_fc_parameters
                self.set_component_value(("GNSS Receiver", "FC Connection", "Protocol"), str(gps1_connection_protocol))
            elif gps1_connection_type in CAN_PORTS:
                if (
                    "CAN_D1_PROTOCOL" in fc_parameters
                    and fc_parameters["CAN_D1_PROTOCOL"] == 1
                    and "CAN_P1_DRIVER" in fc_parameters
                    and fc_parameters["CAN_P1_DRIVER"] == 1
                ):
                    self.set_component_value(("GNSS Receiver", "FC Connection", "Type"), "CAN1")
                elif (
                    "CAN_D2_PROTOCOL" in fc_parameters
                    and fc_parameters["CAN_D2_PROTOCOL"] == 1
                    and "CAN_P2_DRIVER" in fc_parameters
                    and fc_parameters["CAN_P2_DRIVER"] == 2
                ):
                    self.set_component_value(("GNSS Receiver", "FC Connection", "Type"), "CAN2")
                else:
                    logging_error(
                        _("Invalid CAN_Dx_PROTOCOL %s and CAN_Px_DRIVER %s for GNSS Receiver"),
                        fc_parameters.get("CAN_D1_PROTOCOL"),
                        fc_parameters.get("CAN_P1_DRIVER"),
                    )
                    self.set_component_value(("GNSS Receiver", "FC Connection", "Type"), "None")
                self.set_component_value(("GNSS Receiver", "FC Connection", "Protocol"), str(gps1_connection_protocol))
            else:
                logging_error("Invalid GNSS connection type %s", gps1_connection_type)
                self.set_component_value(("GNSS Receiver", "FC Connection", "Type"), "None")
        else:
            logging_error("GPS_TYPE %u not in GNSS_RECEIVER_CONNECTION", gps1_type)
            self.set_component_value(("GNSS Receiver", "FC Connection", "Type"), "None")

    def _set_serial_type_from_fc_parameters(self, fc_parameters: dict) -> bool:  # pylint: disable=too-many-branches
        """Process serial port parameters and update the data model. Returns True if ESC is serial controlled."""
        if "RC_PROTOCOLS" in fc_parameters:
            try:
                rc_protocols_nr = int(fc_parameters["RC_PROTOCOLS"])
            except (ValueError, TypeError):
                logging_error(_("Invalid non-integer value for RC_PROTOCOLS %s"), fc_parameters["RC_PROTOCOLS"])
                rc_protocols_nr = 0
            # check if rc_protocols_nr is a power of two (only one bit set) and not zero
            if rc_protocols_nr > 0 and rc_protocols_nr & (rc_protocols_nr - 1) == 0:
                # rc_bit is the number of the bit that is set
                rc_bit = str(int(log2(rc_protocols_nr)))
                protocol = RC_PROTOCOLS_DICT[rc_bit].get("protocol")
                self.set_component_value(("RC Receiver", "FC Connection", "Protocol"), str(protocol))

        rc = 1
        telem = 1
        gnss = 1
        esc = 1
        for serial in SERIAL_PORTS:
            if serial + "_PROTOCOL" not in fc_parameters:
                continue
            serial_protocol_nr = 0
            try:
                serial_protocol_nr = int(fc_parameters[serial + "_PROTOCOL"])
            except (ValueError, TypeError):
                msg = _("Invalid non-integer value for {serial}_PROTOCOL {serial_protocol_nr}")
                logging_error(msg.format(serial=serial, serial_protocol_nr=fc_parameters[serial + "_PROTOCOL"]))
                continue

            if serial_protocol_nr == 0:
                continue  # zero is an invalid protocol

            index_str = str(serial_protocol_nr)
            if index_str not in SERIAL_PROTOCOLS_DICT:
                continue

            component = SERIAL_PROTOCOLS_DICT[index_str].get("component")
            protocol = SERIAL_PROTOCOLS_DICT[index_str].get("protocol")
            if component is None:
                continue

            if component == "RC Receiver" and rc == 1:
                self.set_component_value(("RC Receiver", "FC Connection", "Type"), serial)
                rc += 1
            elif component == "Telemetry" and telem == 1:
                self.set_component_value(("Telemetry", "FC Connection", "Type"), serial)
                self.set_component_value(("Telemetry", "FC Connection", "Protocol"), protocol)
                telem += 1
            elif component == "GNSS Receiver" and gnss == 1:
                self.set_component_value(("GNSS Receiver", "FC Connection", "Type"), serial)
                gnss += 1
            elif component == "ESC":
                if esc == 1:
                    # Only set component values for the first ESC
                    self.set_component_value(("ESC", "FC Connection", "Type"), serial)
                    self.set_component_value(("ESC", "FC Connection", "Protocol"), protocol)
                # Count all ESC components
                esc += 1

        return esc >= 2

    def _set_esc_type_from_fc_parameters(self, fc_parameters: dict[str, Any], doc: dict[str, Any]) -> None:
        """Process ESC parameters and update the data model."""
        mot_pwm_type = fc_parameters.get("MOT_PWM_TYPE", 0)
        try:
            mot_pwm_type = int(mot_pwm_type)
        except (ValueError, TypeError):
            logging_error(_("Invalid non-integer value for MOT_PWM_TYPE %s"), mot_pwm_type)
            mot_pwm_type = 0

        main_out_functions = [fc_parameters.get("SERVO" + str(i) + "_FUNCTION", 0) for i in range(1, 9)]

        # if any element of main_out_functions is in [33, 34, 35, 36] then ESC is connected to main_out
        if any(servo_function in {33, 34, 35, 36} for servo_function in main_out_functions):
            self.set_component_value(("ESC", "FC Connection", "Type"), "Main Out")
        else:
            self.set_component_value(("ESC", "FC Connection", "Type"), "AIO")

        if "MOT_PWM_TYPE" in doc and "values" in doc["MOT_PWM_TYPE"]:
            protocol = str(doc["MOT_PWM_TYPE"]["values"].get(str(mot_pwm_type)))
            if protocol:
                self.set_component_value(("ESC", "FC Connection", "Protocol"), protocol)
        # Fallback to MOT_PWM_TYPE_DICT if doc is not available
        elif str(mot_pwm_type) in MOT_PWM_TYPE_DICT:
            protocol = str(MOT_PWM_TYPE_DICT[str(mot_pwm_type)]["protocol"])
            self.set_component_value(("ESC", "FC Connection", "Protocol"), protocol)

    def _set_battery_type_from_fc_parameters(self, fc_parameters: dict[str, Any]) -> None:
        """Process battery monitor parameters and update the data model."""
        if "BATT_MONITOR" in fc_parameters:
            try:
                batt_monitor = int(fc_parameters["BATT_MONITOR"])
                fc_conn_type = BATT_MONITOR_CONNECTION[str(batt_monitor)].get("type", "None")
                fc_conn_protocol = BATT_MONITOR_CONNECTION[str(batt_monitor)].get("protocol", "Disabled")

                if isinstance(fc_conn_type, list):
                    fc_conn_type = fc_conn_type[0]
                if isinstance(fc_conn_protocol, list):
                    fc_conn_protocol = fc_conn_protocol[0]

                self.set_component_value(("Battery Monitor", "FC Connection", "Type"), fc_conn_type)
                self.set_component_value(("Battery Monitor", "FC Connection", "Protocol"), fc_conn_protocol)
            except (ValueError, KeyError, TypeError) as e:
                logging_error(_("Error processing BATT_MONITOR parameter: %s"), str(e))

    def _set_motor_poles_from_fc_parameters(self, fc_parameters: dict[str, Any]) -> None:
        """Process motor parameters and update the data model."""
        if "MOT_PWM_TYPE" in fc_parameters:
            mot_pwm_type_str = str(fc_parameters["MOT_PWM_TYPE"])
            if mot_pwm_type_str in MOT_PWM_TYPE_DICT and MOT_PWM_TYPE_DICT[mot_pwm_type_str].get("is_dshot", False):
                if "SERVO_BLH_POLES" in fc_parameters:
                    self.set_component_value(("Motors", "Specifications", "Poles"), fc_parameters["SERVO_BLH_POLES"])
            elif "SERVO_FTW_MASK" in fc_parameters and fc_parameters["SERVO_FTW_MASK"] and "SERVO_FTW_POLES" in fc_parameters:
                self.set_component_value(("Motors", "Specifications", "Poles"), fc_parameters["SERVO_FTW_POLES"])
