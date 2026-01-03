"""
Data model for vehicle components import from FC parameters.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import contextlib

# from logging import debug as logging_debug
from logging import error as logging_error
from logging import warning as logging_warning
from typing import Any, Optional

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
    ComponentDataModelValidation,
)


def is_single_bit_set(value: int) -> bool:
    """
    Check if exactly one bit is set in a bitmask (value is a power of 2 and non-zero).

    Args:
        value: Integer value to check

    Returns:
        True if value is a power of 2 (exactly one bit set), False otherwise

    Examples:
        >>> is_single_bit_set(1)   # 0b0001
        True
        >>> is_single_bit_set(4)   # 0b0100
        True
        >>> is_single_bit_set(5)   # 0b0101 (multiple bits)
        False
        >>> is_single_bit_set(0)   # no bits set
        False

    """
    return value > 0 and value & (value - 1) == 0


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
        Note: Logs warnings (not errors) when firmware has protocols not in code dictionaries,
        as this is expected when ArduPilot firmware is updated with new features.

        For bitmask parameters (doc_dict == "Bitmask"), the documentation key represents a bit position,
        but our dictionary keys are the actual bitmask values (2^bit_position), so we convert for comparison.
        """
        is_valid = True
        if not doc or doc_key not in doc or not doc[doc_key] or doc_dict not in doc[doc_key]:
            return False

        is_bitmask = doc_dict == "Bitmask"

        for key, doc_protocol in doc[doc_key][doc_dict].items():
            # For bitmask parameters, convert bit position to bitmask value (2^bit_position)
            # e.g., bit position "0" -> value "1", bit position "9" -> value "512"
            if is_bitmask:
                try:
                    check_key = str(2 ** int(key))
                except (ValueError, TypeError):
                    logging_warning(_("Invalid bit position %s in %s metadata"), key, doc_key)
                    continue
            else:
                check_key = key

            if check_key in dict_to_check:
                code_protocol = dict_to_check[check_key].get("protocol", None)
                if code_protocol != doc_protocol:
                    logging_warning(_("Protocol %s does not match %s in %s metadata"), code_protocol, doc_protocol, doc_key)
                    is_valid = False
            else:
                logging_warning(
                    _("Protocol %s (%s) not found in %s code dictionary (firmware may be newer)"), doc_protocol, key, doc_key
                )
                is_valid = False
        return is_valid

    def process_fc_parameters(
        self,
        fc_parameters: dict[str, float],
        doc: dict[str, Any],
    ) -> None:
        """
        Process flight controller parameters and update the data model accordingly.

        This method consolidates all parameter processing logic in one place.
        """
        # First verify dictionaries match documentation
        self._verify_dict_is_uptodate(doc, SERIAL_PROTOCOLS_DICT, "SERIAL1_PROTOCOL", "values")
        self._verify_dict_is_uptodate(doc, BATT_MONITOR_CONNECTION, "BATT_MONITOR", "values")
        # GPS_TYPE was renamed to GPS1_TYPE in ArduPilot 4.6
        if "GPS1_TYPE" in doc:
            self._verify_dict_is_uptodate(doc, GNSS_RECEIVER_CONNECTION, "GPS1_TYPE", "values")
        elif "GPS_TYPE" in doc:
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
        # GPS_TYPE was renamed to GPS1_TYPE in ArduPilot 4.6, check for both
        gps1_type = fc_parameters.get("GPS1_TYPE", fc_parameters.get("GPS_TYPE", 0))
        param_name = "GPS1_TYPE" if "GPS1_TYPE" in fc_parameters else "GPS_TYPE"
        try:
            gps1_type = int(gps1_type)
        except (ValueError, TypeError):
            logging_error(_("Invalid non-integer value for %s: %s"), param_name, gps1_type)
            gps1_type = 0

        if str(gps1_type) in GNSS_RECEIVER_CONNECTION:
            gps1_connection_type = GNSS_RECEIVER_CONNECTION[str(gps1_type)].get("type")
            gps1_connection_protocol = GNSS_RECEIVER_CONNECTION[str(gps1_type)].get("protocol")
            # Normalize gps1_connection_type to a list for consistent handling
            if isinstance(gps1_connection_type, str):
                gps1_connection_type = [gps1_connection_type]
            # gps1_connection_type is now a list of possible connection types
            if gps1_connection_type == ["None"]:
                self.set_component_value(("GNSS Receiver", "FC Connection", "Type"), "None")
                self.set_component_value(("GNSS Receiver", "FC Connection", "Protocol"), "None")
            elif gps1_connection_type and any(conn_type in SERIAL_PORTS for conn_type in gps1_connection_type):
                # GNSS connection type will be detected later in set_serial_type_from_fc_parameters
                self.set_component_value(("GNSS Receiver", "FC Connection", "Protocol"), str(gps1_connection_protocol))
            elif gps1_connection_type and any(conn_type in CAN_PORTS for conn_type in gps1_connection_type):
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
            logging_error("%s value %u not in GNSS_RECEIVER_CONNECTION", param_name, gps1_type)
            self.set_component_value(("GNSS Receiver", "FC Connection", "Type"), "None")

    def _set_serial_type_from_fc_parameters(  # pylint: disable=too-many-branches,too-many-statements # noqa: PLR0915
        self, fc_parameters: dict
    ) -> bool:
        """Process serial port parameters and update the data model. Returns True if ESC is serial controlled."""
        if "RC_PROTOCOLS" in fc_parameters:
            try:
                rc_protocols_nr = int(fc_parameters["RC_PROTOCOLS"])
            except (ValueError, TypeError):
                logging_error(_("Invalid non-integer value for RC_PROTOCOLS %s"), fc_parameters["RC_PROTOCOLS"])
                rc_protocols_nr = 0
            # RC_PROTOCOLS is a bitmask where each bit represents an enabled protocol
            # Only set a specific protocol if exactly one bit is set (power of 2)
            # If multiple bits are set, we can't determine which protocol is actually in use
            if is_single_bit_set(rc_protocols_nr):
                # Exactly one bit is set (power of 2) - use the value directly as the key
                rc_value = str(rc_protocols_nr)
                if rc_value in RC_PROTOCOLS_DICT:
                    protocol = RC_PROTOCOLS_DICT[rc_value].get("protocol")
                    self.set_component_value(("RC Receiver", "FC Connection", "Protocol"), str(protocol))
            elif rc_protocols_nr > 0:
                # Multiple bits are set - cannot determine which protocol is active
                logging_error(
                    _("RC_PROTOCOLS has multiple protocols enabled (%d). Cannot determine active protocol."), rc_protocols_nr
                )

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
                # Note: Protocol is set by RC_PROTOCOLS processing, not SERIAL_PROTOCOLS
                rc += 1
            elif component == "Telemetry" and telem == 1:
                self.set_component_value(("Telemetry", "FC Connection", "Type"), serial)
                self.set_component_value(("Telemetry", "FC Connection", "Protocol"), protocol)
                telem += 1
            elif component == "GNSS Receiver" and gnss == 1:
                # Only set GNSS Type from SERIAL if it hasn't been set to a CAN port already
                # Processing order dependency: _set_gnss_type_from_fc_parameters() is called first,
                # which sets CAN ports based on GPS_TYPE/GPS1_TYPE parameter. This check prevents
                # overwriting CAN configuration with SERIAL when a GNSS uses CAN for connection.
                current_gnss_type = self.get_component_value(("GNSS Receiver", "FC Connection", "Type"))
                if current_gnss_type not in CAN_PORTS:
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

    def _set_esc_type_from_fc_parameters(self, fc_parameters: dict[str, float], doc: dict[str, Any]) -> None:
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

    def _set_battery_type_from_fc_parameters(self, fc_parameters: dict[str, float]) -> None:
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

        if "BATT_CAPACITY" in fc_parameters:
            try:
                batt_capacity = int(fc_parameters["BATT_CAPACITY"])
                if batt_capacity > 0:
                    self.set_component_value(("Battery", "Specifications", "Capacity mAh"), batt_capacity)
            except (ValueError, TypeError) as e:
                logging_error(_("Error processing BATT_CAPACITY parameter: %s"), str(e))

        # Estimate number of cells from voltage parameters
        self._estimate_battery_cell_count(fc_parameters)

    def _estimate_cells_from_voltage_param(
        self, param_name: str, param_value: float, volt_per_cell_spec: str
    ) -> Optional[int]:
        """
        Estimate cell count from a voltage parameter.

        Args:
            param_name: Name of the parameter for logging
            param_value: Value of the voltage parameter
            volt_per_cell_spec: Battery specification name (e.g., "Volt per cell max")

        Returns:
            Estimated cell count or None if estimation failed

        """
        volt_per_cell_value = self.get_component_value(("Battery", "Specifications", volt_per_cell_spec))

        volt_per_cell = 0.0
        if isinstance(volt_per_cell_value, (int, float, str)) and volt_per_cell_value:
            with contextlib.suppress(ValueError, TypeError):
                volt_per_cell = float(volt_per_cell_value)

        if volt_per_cell <= 0:
            return None

        try:
            voltage = float(param_value)
            if voltage > 0:
                return round(voltage / volt_per_cell)
        except (ValueError, TypeError, ZeroDivisionError) as e:
            logging_error(_("Error processing %s parameter: %s"), param_name, str(e))

        return None

    def _estimate_battery_cell_count(self, fc_parameters: dict[str, float]) -> None:
        """
        Estimate battery cell count from voltage parameters.

        Uses MOT_BAT_VOLT_MAX, BATT_LOW_VOLT, or BATT_CRT_VOLT along with
        current volt-per-cell values to estimate the number of cells.

        Args:
            fc_parameters: Dictionary of flight controller parameters

        """
        # Try to estimate cell count from available voltage parameters
        # Priority: MOT_BAT_VOLT_MAX > BATT_LOW_VOLT > BATT_CRT_VOLT
        estimated_cells = None

        if "MOT_BAT_VOLT_MAX" in fc_parameters:
            estimated_cells = self._estimate_cells_from_voltage_param(
                "MOT_BAT_VOLT_MAX", fc_parameters["MOT_BAT_VOLT_MAX"], "Volt per cell max"
            )

        if estimated_cells is None and "BATT_LOW_VOLT" in fc_parameters:
            estimated_cells = self._estimate_cells_from_voltage_param(
                "BATT_LOW_VOLT", fc_parameters["BATT_LOW_VOLT"], "Volt per cell low"
            )

        if estimated_cells is None and "BATT_CRT_VOLT" in fc_parameters:
            estimated_cells = self._estimate_cells_from_voltage_param(
                "BATT_CRT_VOLT", fc_parameters["BATT_CRT_VOLT"], "Volt per cell crit"
            )

        # If no estimation succeeded, all volt per cell values must be invalid
        if estimated_cells is None:
            logging_error(_("All volt per cell values are zero or invalid; cannot estimate battery cell count"))
            return

        # Validate and set the estimated cell count
        cell_path = ("Battery", "Specifications", "Number of cells")
        if cell_path in ComponentDataModelValidation.VALIDATION_RULES:
            _type, (min_cells, max_cells), _doc = ComponentDataModelValidation.VALIDATION_RULES[cell_path]
            if min_cells <= estimated_cells <= max_cells:
                self.set_component_value(cell_path, estimated_cells)
            else:
                logging_error(
                    _("Estimated battery cell count %s is out of valid range (%d to %d)"),
                    estimated_cells,
                    min_cells,
                    max_cells,
                )

    def _set_motor_poles_from_fc_parameters(self, fc_parameters: dict[str, float]) -> None:
        """Process motor parameters and update the data model."""
        if "MOT_PWM_TYPE" in fc_parameters:
            mot_pwm_type_str = str(fc_parameters["MOT_PWM_TYPE"])
            if mot_pwm_type_str in MOT_PWM_TYPE_DICT and MOT_PWM_TYPE_DICT[mot_pwm_type_str].get("is_dshot", False):
                if "SERVO_BLH_POLES" in fc_parameters:
                    self.set_component_value(("Motors", "Specifications", "Poles"), fc_parameters["SERVO_BLH_POLES"])
            elif "SERVO_FTW_MASK" in fc_parameters and fc_parameters["SERVO_FTW_MASK"] and "SERVO_FTW_POLES" in fc_parameters:
                self.set_component_value(("Motors", "Specifications", "Poles"), fc_parameters["SERVO_FTW_POLES"])
