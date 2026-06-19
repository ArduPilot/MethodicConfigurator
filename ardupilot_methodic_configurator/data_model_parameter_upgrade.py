"""
Parameter upgrade mappings and functions for ArduPilot firmware version transitions.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import re
from logging import warning as logging_warning

from packaging.version import InvalidVersion, Version

from ardupilot_methodic_configurator import _
from ardupilot_methodic_configurator.data_model_par_dict import Par, ParDict
from ardupilot_methodic_configurator.data_model_vehicle_components_validation import SERIAL_PROTOCOLS_DICT

# Upgrade parameter names for ArduPilot 4.6 firmware (name-only renames, same units)
PARAM_UPGRADE_DICT_46: dict[str, str] = {
    "GPS_CAN_NODEID1": "GPS1_CAN_NODEID",
    "GPS_CAN_NODEID2": "GPS2_CAN_NODEID",
    "GPS_COM_PORT": "GPS1_COM_PORT",
    "GPS_COM_PORT2": "GPS2_COM_PORT",
    "GPS_DELAY_MS": "GPS1_DELAY_MS",
    "GPS_DELAY_MS2": "GPS2_DELAY_MS",
    "GPS_GNSS_MODE": "GPS1_GNSS_MODE",
    "GPS_GNSS_MODE2": "GPS2_GNSS_MODE",
    "GPS_MB1_TYPE": "GPS1_MB_TYPE",
    "GPS_MB2_TYPE": "GPS2_MB_TYPE",
    "GPS_POS1_X": "GPS1_POS_X",
    "GPS_POS1_Y": "GPS1_POS_Y",
    "GPS_POS1_Z": "GPS1_POS_Z",
    "GPS_POS2_X": "GPS2_POS_X",
    "GPS_POS2_Y": "GPS2_POS_Y",
    "GPS_POS2_Z": "GPS2_POS_Z",
    "GPS_RATE_MS": "GPS1_RATE_MS",
    "GPS_RATE_MS2": "GPS2_RATE_MS",
    "GPS_TYPE": "GPS1_TYPE",
    "GPS_TYPE2": "GPS2_TYPE",
}

# Upgrade parameter names and values for ArduPilot 4.7 firmware.
# Tuple is (new_name, scale_factor). Scale factor converts old units to new units.
PARAM_UPGRADE_DICT_47: dict[str, tuple[str, float]] = {
    # name-only renames (same units, scale=1.0)
    "EK3_MAX_FLOW": ("EK3_FLOW_MAX", 1.0),
    "PHLD_BRAKE_RATE": ("PHLD_BRK_RATE", 1.0),
    "PSC_ACCZ_D": ("PSC_D_ACC_D", 1.0),
    "PSC_ACCZ_D_FF": ("PSC_D_ACC_D_FF", 1.0),
    "PSC_ACCZ_FF": ("PSC_D_ACC_FF", 1.0),
    "PSC_ACCZ_FLTD": ("PSC_D_ACC_FLTD", 1.0),
    "PSC_ACCZ_FLTE": ("PSC_D_ACC_FLTE", 1.0),
    "PSC_ACCZ_FLTT": ("PSC_D_ACC_FLTT", 1.0),
    "PSC_ACCZ_NEF": ("PSC_D_ACC_NEF", 1.0),
    "PSC_ACCZ_NTF": ("PSC_D_ACC_NTF", 1.0),
    "PSC_ACCZ_PDMX": ("PSC_D_ACC_PDMX", 1.0),
    "PSC_ACCZ_SMAX": ("PSC_D_ACC_SMAX", 1.0),
    "PSC_JERK_XY": ("PSC_JERK_NE", 1.0),
    "PSC_JERK_Z": ("PSC_JERK_D", 1.0),
    "PSC_POSXY_P": ("PSC_NE_POS_P", 1.0),
    "PSC_POSZ_P": ("PSC_D_POS_P", 1.0),
    "PSC_VELXY_D": ("PSC_NE_VEL_D", 1.0),
    "PSC_VELXY_FF": ("PSC_NE_VEL_FF", 1.0),
    "PSC_VELXY_FLTD": ("PSC_NE_VEL_FLTD", 1.0),
    "PSC_VELXY_FLTE": ("PSC_NE_VEL_FLTE", 1.0),
    "PSC_VELXY_I": ("PSC_NE_VEL_I", 1.0),
    "PSC_VELXY_P": ("PSC_NE_VEL_P", 1.0),
    "PSC_VELZ_D": ("PSC_D_VEL_D", 1.0),
    "PSC_VELZ_FF": ("PSC_D_VEL_FF", 1.0),
    "PSC_VELZ_FLTD": ("PSC_D_VEL_FLTD", 1.0),
    "PSC_VELZ_FLTE": ("PSC_D_VEL_FLTE", 1.0),
    "PSC_VELZ_I": ("PSC_D_VEL_I", 1.0),
    "PSC_VELZ_P": ("PSC_D_VEL_P", 1.0),
    "SYSID_MYGCS": ("MAV_GCS_SYSID", 1.0),
    "SYSID_THISMAV": ("MAV_SYSID", 1.0),
    "TELEM_DELAY": ("MAV_TELEM_DELAY", 1.0),
    "WPNAV_ACCEL_C": ("WP_ACC_CNR", 1.0),
    "WPNAV_JERK": ("WP_JERK", 1.0),
    "WPNAV_RFND_USE": ("WP_RFND_USE", 1.0),
    "WPNAV_TER_MARGIN": ("WP_TER_MARGIN", 1.0),
    # renames with /100 scaling (cm→m, cm/s→m/s, centideg→deg, cm/s²→m/s², etc.)
    "ANGLE_MAX": ("ATC_ANGLE_MAX", 0.01),
    "ATC_ACCEL_P_MAX": ("ATC_ACC_P_MAX", 0.01),
    "ATC_ACCEL_R_MAX": ("ATC_ACC_R_MAX", 0.01),
    "ATC_ACCEL_Y_MAX": ("ATC_ACC_Y_MAX", 0.01),
    "ATC_SLEW_YAW": ("ATC_RATE_WPY_MAX", 0.01),
    "CIRCLE_RADIUS": ("CIRCLE_RADIUS_M", 0.01),
    "LAND_ALT_LOW": ("LAND_ALT_LOW_M", 0.01),
    "LAND_SPEED": ("LAND_SPD_MS", 0.01),
    "LAND_SPEED_HIGH": ("LAND_SPD_HIGH_MS", 0.01),
    "LOIT_ACC_MAX": ("LOIT_ACC_MAX_M", 0.01),
    "LOIT_BRK_ACCEL": ("LOIT_BRK_ACC_M", 0.01),
    "LOIT_BRK_JERK": ("LOIT_BRK_JRK_M", 0.01),
    "LOIT_SPEED": ("LOIT_SPEED_MS", 0.01),
    "PHLD_BRAKE_ANGLE": ("PHLD_BRK_ANGLE", 0.01),
    "PILOT_ACCEL_Z": ("PILOT_ACC_Z", 0.01),
    "PILOT_SPEED_DN": ("PILOT_SPD_DN", 0.01),
    "PILOT_SPEED_UP": ("PILOT_SPD_UP", 0.01),
    "PILOT_TKOFF_ALT": ("PILOT_TKO_ALT_M", 0.01),
    "PSC_VELXY_IMAX": ("PSC_NE_VEL_IMAX", 0.01),
    "PSC_VELZ_IMAX": ("PSC_D_VEL_IMAX", 0.01),
    "RTL_ALT": ("RTL_ALT_M", 0.01),
    "RTL_ALT_FINAL": ("RTL_ALT_FINAL_M", 0.01),
    "RTL_CLIMB_MIN": ("RTL_CLIMB_MIN_M", 0.01),
    "RTL_SPEED": ("RTL_SPEED_MS", 0.01),
    "WPNAV_ACCEL": ("WP_ACC", 0.01),
    "WPNAV_ACCEL_Z": ("WP_ACC_Z", 0.01),
    "WPNAV_RADIUS": ("WP_RADIUS_M", 0.01),
    "WPNAV_SPEED": ("WP_SPD", 0.01),
    "WPNAV_SPEED_DN": ("WP_SPD_DN", 0.01),
    "WPNAV_SPEED_UP": ("WP_SPD_UP", 0.01),
    # PSC_ACCZ → PSC_D_ACC: P and I scale by /10, IMAX by /1000
    "PSC_ACCZ_P": ("PSC_D_ACC_P", 0.1),
    "PSC_ACCZ_I": ("PSC_D_ACC_I", 0.1),
    "PSC_ACCZ_IMAX": ("PSC_D_ACC_IMAX", 0.001),
}

# Protocol values for SERIAL*_PROTOCOL parameters that use MAVLink (derived from SERIAL_PROTOCOLS_DICT)
# These determine which ports will have SR parameters mapped to MAV parameters
MAVLINK_SERIAL_PROTOCOLS: frozenset[int] = frozenset(
    int(k) for k, v in SERIAL_PROTOCOLS_DICT.items() if str(v["protocol"]).startswith("MAVLink")
)


def build_sr_to_mav_mapping(file_parameters: dict[str, ParDict]) -> tuple[dict[str, str], set[int]]:
    """
    Build the SR to MAV parameter prefix mapping based on SERIAL*_PROTOCOL configuration.

    See https://ardupilot.org/copter/docs/common-mavlink-configuration.html
    Scans all SERIAL*_PROTOCOL parameters to determine which ports use MAVLink 1 or 2,
    then creates the mapping from SRx_ to MAVy_ where:
    - MAV1_ corresponds to the first port with MAVLink protocol
    - MAV2_ corresponds to the second port with MAVLink protocol
    - MAV3_ corresponds to the third port with MAVLink protocol
    - ...
    - MAV32_ corresponds to the thirty-second port with MAVLink protocol

    Args:
        file_parameters: All parameter files containing SERIAL*_PROTOCOL definitions

    Returns:
        Tuple of (SR-to-MAV mapping dict, set of MAVLink port indices)
        Example: ({"SR0_": "MAV1_", "SR2_": "MAV2_"}, {0, 2})

    """
    # Scan all parameters to find SERIAL*_PROTOCOL settings
    # Use a set to deduplicate: the same SERIAL*_PROTOCOL may appear in multiple .param files
    mavlink_port_index_set: set[int] = set()
    for params in file_parameters.values():
        for param_name, par in params.items():
            # Match SERIAL{port}_PROTOCOL pattern
            match = re.match(r"^SERIAL(\d+)_PROTOCOL$", param_name)
            if match:
                port_index = int(match.group(1))
                protocol_value = par.value

                # Check if this port uses a MAVLink protocol
                if int(protocol_value) in MAVLINK_SERIAL_PROTOCOLS:
                    mavlink_port_index_set.add(port_index)

    # Sort unique indices for consistent ordering (1st port → MAV1, 2nd port → MAV2, etc.)
    mavlink_port_indices = sorted(mavlink_port_index_set)

    # Build the mapping from SR prefix to MAV prefix
    sr_to_mav_map = {f"SR{sr_index}_": f"MAV{mav_index}_" for mav_index, sr_index in enumerate(mavlink_port_indices, start=1)}

    return sr_to_mav_map, set(mavlink_port_indices)


def _process_sr_parameter(
    name: str,
    par: Par,
    sr_to_mav_map: dict[str, str],
    mavlink_port_indices: set[int],
) -> tuple[bool, str, Par | None]:
    """
    Process a single SR parameter for 4.7 upgrade.

    Handles remapping to MAV parameters or dropping based on SERIAL*_PROTOCOL config.
    Stream rate (SR) parameters are remapped from SRx_ prefix to MAVy_ prefix based on
    which ports use MAVLink. The suffix is preserved unchanged (no renaming).
    See https://ardupilot.org/copter/docs/common-mavlink-configuration.html

    Args:
        name: Parameter name (e.g., "SR0_RAW_SENS")
        par: Parameter object
        sr_to_mav_map: Mapping from SR prefix to MAV prefix
        mavlink_port_indices: Set of port indices using MAVLink

    Returns:
        Tuple of (is_sr_param, new_name, new_par)
        is_sr_param: True if this was an SR parameter that was processed
        new_name: The new parameter name (empty if dropped)
        new_par: The new parameter object (None if dropped)

    """
    # Match SR{port}_{suffix} pattern
    match = re.match(r"^SR(\d+)_(.+)$", name)
    if not match:
        return False, "", None

    sr_port = int(match.group(1))
    sr_suffix = match.group(2)

    # SR parameter on non-MAVLink port - drop it
    if sr_port not in mavlink_port_indices:
        return True, "", None

    # Remap to MAV parameter, preserving the suffix unchanged
    sr_prefix = f"SR{sr_port}_"
    mav_prefix = sr_to_mav_map[sr_prefix]
    return True, mav_prefix + sr_suffix, par


def upgrade_file_parameters_46(file_parameters: dict[str, ParDict]) -> None:
    """
    Upgrade parameter names in-place for ArduPilot 4.6 firmware.

    Renames parameters according to PARAM_UPGRADE_DICT_46. All values and
    comments are preserved unchanged.

    Args:
        file_parameters: Mapping of filename to ParDict, modified in-place.

    """
    for filename, params in file_parameters.items():
        upgraded: dict[str, Par] = {}
        for name, par in params.items():
            new_name = PARAM_UPGRADE_DICT_46.get(name, name)
            if name != new_name and new_name in params:
                # The already-upgraded new name already exists in the original file; skip this rename
                logging_warning(
                    _(
                        "Parameter collision in '%s': both old name '%s' and new name '%s' map to '%s'. "
                        "Keeping the already-upgraded entry."
                    ),
                    filename,
                    name,
                    new_name,
                    new_name,
                )
            else:
                upgraded[new_name] = par
        file_parameters[filename] = ParDict(upgraded)


def upgrade_file_parameters_47(file_parameters: dict[str, ParDict]) -> None:
    """
    Upgrade parameter names and values in-place for ArduPilot 4.7 firmware.

    Renames parameters according to PARAM_UPGRADE_DICT_47, applying the
    associated scale factor to each value. Stream rate parameters with the
    SR prefix are remapped to MAV parameters based on SERIAL*_PROTOCOL configuration.
    SR parameters from non-MAVLink ports are dropped.
    Comments are preserved unchanged.

    Args:
        file_parameters: Mapping of filename to ParDict, modified in-place.

    """
    # Build SR to MAV mapping based on SERIAL*_PROTOCOL configuration
    sr_to_mav_map, mavlink_port_indices = build_sr_to_mav_mapping(file_parameters)

    for filename, params in file_parameters.items():  # pylint: disable=too-many-nested-blocks
        upgraded: dict[str, Par] = {}
        for name, par in params.items():
            if name in PARAM_UPGRADE_DICT_47:
                # Handle explicit parameter renames and scaling
                new_name, scale = PARAM_UPGRADE_DICT_47[name]
                if new_name in params:
                    # The already-upgraded new name already exists in the original file; skip this rename
                    logging_warning(
                        _(
                            "Parameter collision in '%s': both old name '%s' and already-present '%s' map to '%s'. "
                            "Keeping the already-upgraded entry."
                        ),
                        filename,
                        name,
                        new_name,
                        new_name,
                    )
                else:
                    upgraded[new_name] = Par(par.value * scale, par.comment)
            elif name.startswith("SERIAL") and name.endswith("_PROTOCOL"):
                # Preserve SERIAL*_PROTOCOL parameters unchanged
                upgraded[name] = par
            else:
                # Check if this is an SR parameter and process accordingly
                is_sr_param, new_name, new_par = _process_sr_parameter(name, par, sr_to_mav_map, mavlink_port_indices)

                if is_sr_param:
                    if new_par is not None:
                        if new_name in params:
                            # The already-upgraded MAV param already exists in the original file; skip the SR rename
                            logging_warning(
                                _(
                                    "Parameter collision in '%s': both SR param '%s' and already-present '%s'. "
                                    "Keeping the already-upgraded entry."
                                ),
                                filename,
                                name,
                                new_name,
                            )
                        else:
                            upgraded[new_name] = new_par
                    # else: parameter was dropped
                else:
                    # Non-SR, non-upgrade parameters - keep unchanged
                    upgraded[name] = par

        file_parameters[filename] = ParDict(upgraded)


def upgrade_parameters_for_firmware_version(
    parameter_files_version_str: str,
    flight_controller_version_str: str,
    file_parameters: dict[str, ParDict],
) -> None:
    """
    Upgrade parameters from parameter files version to flight controller version.

    Applies appropriate parameter upgrades by comparing parameter files version with
    FC version. Only upgrades that bridge the version gap are applied.
    Handles empty/invalid version strings gracefully with warnings.

    Args:
        parameter_files_version_str: Parameter files firmware version string (may be empty)
        flight_controller_version_str: Flight controller firmware version string (may be empty)
        file_parameters: File parameters dict to upgrade in-place

    """
    # Validate that both version strings are non-empty
    if not parameter_files_version_str:
        logging_warning(
            _(
                "Parameter files firmware version is unknown. Parameter file upgrades will be skipped. "
                "Please ensure the parameter files match the target flight controller firmware version."
            )
        )
        return

    if not flight_controller_version_str:
        logging_warning(
            _(
                "Flight controller firmware version is unknown. Parameter file upgrades will be skipped. "
                "Please ensure the parameter files match the target flight controller firmware version."
            )
        )
        return

    try:
        param_fw_version = Version(parameter_files_version_str)
        fc_fw_version = Version(flight_controller_version_str)
    except InvalidVersion:
        logging_warning(
            _("Invalid firmware version string(s): param_files='%s', fc='%s'. Parameter upgrades will be skipped."),
            parameter_files_version_str,
            flight_controller_version_str,
        )
        return

    # Only upgrade if FC is newer than parameter files
    if fc_fw_version > param_fw_version:
        # Apply 4.6 upgrade if files are older than 4.6 but FC is 4.6 or newer
        if param_fw_version < Version("4.6") <= fc_fw_version:
            upgrade_file_parameters_46(file_parameters)

        # Apply 4.7 upgrade if files are older than 4.7 but FC is 4.7 or newer
        if param_fw_version < Version("4.7") <= fc_fw_version:
            upgrade_file_parameters_47(file_parameters)
