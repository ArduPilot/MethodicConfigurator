"""
Vehicle and flight-controller identity, extracted from an ArduPilot log.

SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import contextlib
from dataclasses import dataclass

from ardupilot_methodic_configurator.data_model_fc_ids import APJ_BOARD_ID_NAME_DICT
from ardupilot_methodic_configurator.log_analysis.backend_firmware_version import parse_first_msg_version, parse_ver_fields
from ardupilot_methodic_configurator.log_analysis.backend_log_extraction import LogData
from ardupilot_methodic_configurator.log_analysis.decode_devid_lib import (
    decode_device_id,
    get_device_type_name,
)
from ardupilot_methodic_configurator.log_analysis.utils import APMDoc, find_matching_param_values

_STARTUP_ANCHOR_LINE = "Param space used:"


@dataclass
class ImuInfo:  # pylint: disable=too-many-instance-attributes
    """Single IMU instance."""

    instance: int
    accel_name: str | None
    accel_bus_type: str | None
    gyro_name: str | None
    gyro_bus_type: str | None
    use: bool | None
    accel_calibrated: bool | None
    gyro_calibrated: bool | None
    accel_temp_calibrated: bool | None
    gyro_temp_calibrated: bool | None
    position_offset_set: bool | None
    accel_healthy: bool | None
    gyro_healthy: bool | None


@dataclass
class CompassInfo:  # pylint: disable=too-many-instance-attributes
    """Single compass instance."""

    instance: int
    name: str | None
    bus_type: str | None
    external: bool | None
    use: bool | None
    calibrated: bool | None
    motor_calibrated: bool | None
    healthy: bool | None


@dataclass
class BaroInfo:
    """Single barometer instance."""

    instance: int
    name: str | None
    bus_type: str | None
    wind_compensation: bool | None
    healthy: bool | None


@dataclass
class AirspeedInfo:
    """Single airspeed sensor instance."""

    instance: int
    sensor_type: str | None
    use: bool | None
    healthy: bool | None


@dataclass
class StartupInfo:
    """OS and flight-controller identity strings, read from the MSG startup block."""

    os_string: str | None
    flight_controller: str | None


def extract_startup_info(log_data: LogData) -> StartupInfo:
    """Extract the OS and flight-controller strings logged at startup."""
    columns = log_data.get_message_columns("MSG")
    if columns is None or columns.size == 0:
        return StartupInfo(os_string=None, flight_controller=None)

    messages = log_data.get_field("MSG", "Message")

    for i, message in enumerate(messages):
        if i < 2:
            continue
        if message.startswith(_STARTUP_ANCHOR_LINE):
            return StartupInfo(os_string=messages[i - 2], flight_controller=messages[i - 1])

    return StartupInfo(os_string=None, flight_controller=None)


@dataclass
class VehicleInfo:  # pylint: disable=too-many-instance-attributes
    """Vehicle type, firmware version, board id, and flight-controller identity."""

    vehicle_type: str | None
    major: int | None
    minor: int | None
    patch: int | None
    firmware_hash: str | None
    board_id: int | None
    flight_controller: str | None
    oper_sys: str | None


@dataclass
class HardwareReport:
    """Complete hardware identity for one log: vehicle, IMUs, compasses, baros, airspeed sensors."""

    vehicle: VehicleInfo
    board_name: str | None
    imus: list[ImuInfo]
    compasses: list[CompassInfo]
    baros: list[BaroInfo]
    airspeed_sensors: list[AirspeedInfo]


def extract_hardware_report(log_data: LogData, params: dict[str, float], apm_doc: APMDoc | None) -> HardwareReport:
    """Build the complete hardware overview for a parsed log."""
    vehicle = extract_vehicle_info(log_data)
    board_name = resolve_board_name(vehicle.board_id)

    imus = []
    for instance in (1, 2, 3):
        suffix = "" if instance == 1 else str(instance)
        if params.get(f"INS_ACC{suffix}_ID") is not None:
            imus.append(build_imu_info(apm_doc, log_data, params, instance))

    compasses = []
    for instance in (1, 2, 3):
        suffix = "" if instance == 1 else str(instance)
        if params.get(f"COMPASS_DEV_ID{suffix}") is not None:
            compasses.append(build_compass_info(apm_doc, log_data, params, instance))

    baros = []
    for instance in (1, 2, 3):
        if params.get(f"BARO{instance}_DEVID") is not None:
            baros.append(build_baro_info(apm_doc, log_data, params, instance))  # noqa: PERF401

    airspeed_sensors = []
    for instance in (1, 2):
        suffix = "" if instance == 1 else str(instance)
        if params.get(f"ARSPD_TYPE{suffix}") is not None:
            airspeed_sensors.append(build_airspeed_info(apm_doc, log_data, params, instance))

    return HardwareReport(
        vehicle=vehicle,
        board_name=board_name,
        imus=imus,
        compasses=compasses,
        baros=baros,
        airspeed_sensors=airspeed_sensors,
    )


def _vehicle_info_from_ver(log_data: LogData) -> VehicleInfo | None:
    """Read vehicle type, version, hash, and board id from the VER message, if present."""
    ver_columns = log_data.get_message_columns("VER")
    if ver_columns is None or ver_columns.size == 0:
        return None

    names = ver_columns.dtype.names or ()
    required = {"FWS", "Maj", "Min", "Pat"}
    if not required.issubset(names):
        return None

    fws = log_data.get_field("VER", "FWS")[0]
    result = parse_ver_fields(
        fws, log_data.get_field("VER", "Maj")[0], log_data.get_field("VER", "Min")[0], log_data.get_field("VER", "Pat")[0]
    )
    if result is None:
        return None

    vehicle_type, major, minor, patch = result

    firmware_hash = None
    if "GH" in names:
        with contextlib.suppress(TypeError, ValueError):
            gh = int(log_data.get_field("VER", "GH")[0])
            if gh != 0:
                firmware_hash = f"{gh:08x}"

    board_id = None
    if "APJ" in names:
        with contextlib.suppress(TypeError, ValueError):
            apj = int(log_data.get_field("VER", "APJ")[0])
            if apj != 0:
                board_id = apj

    return VehicleInfo(
        vehicle_type=vehicle_type,
        major=major,
        minor=minor,
        patch=patch,
        firmware_hash=firmware_hash,
        board_id=board_id,
        flight_controller=None,
        oper_sys=None,
    )


def _vehicle_info_from_msg_fallback(log_data: LogData) -> VehicleInfo | None:
    """Read vehicle type, version, and hash from a MSG line, for firmware with no VER message."""
    columns = log_data.get_message_columns("MSG")
    if columns is None or columns.size == 0:
        return None

    parsed = parse_first_msg_version(log_data.get_field("MSG", "Message"))
    if parsed is not None:
        vehicle_type, major, minor, patch, firmware_hash = parsed
        return VehicleInfo(
            vehicle_type=vehicle_type,
            major=int(major),
            minor=int(minor),
            patch=int(patch),
            firmware_hash=firmware_hash,
            board_id=None,
            flight_controller=None,
            oper_sys=None,
        )

    return None


def extract_vehicle_info(log_data: LogData) -> VehicleInfo:
    """Extract vehicle identity and FC identity from a parsed log."""
    info = _vehicle_info_from_ver(log_data)
    if info is None:
        info = _vehicle_info_from_msg_fallback(log_data)
    if info is None:
        info = VehicleInfo(
            vehicle_type=None,
            major=None,
            minor=None,
            patch=None,
            firmware_hash=None,
            board_id=None,
            flight_controller=None,
            oper_sys=None,
        )

    startup_info = extract_startup_info(log_data)
    info.flight_controller = startup_info.flight_controller
    info.oper_sys = startup_info.os_string

    return info


def resolve_board_name(board_id: int | None) -> str | None:
    """Resolve a numeric APJ board ID to its board name, using AMC's bundled fc_id data."""
    if board_id is None:
        return None
    names = APJ_BOARD_ID_NAME_DICT.get(board_id)
    return names[0] if names else None


def _tcal_enabled_codes(apm_doc: APMDoc | None, instance: int) -> set[str]:
    """Return the INS_TCAL{n}_ENABLE codes meaning from apm.pdef.xml."""
    if apm_doc is None:
        return set()
    return find_matching_param_values(apm_doc, f"INS_TCAL{instance}_ENABLE", "Enabled")


def build_imu_info(apm_doc: APMDoc | None, log_data: LogData, params: dict[str, float], instance: int) -> ImuInfo:  # pylint: disable=too-many-locals
    """Build ImuInfo for one IMU instance."""
    suffix = "" if instance == 1 else str(instance)

    acc_id = params.get(f"INS_ACC{suffix}_ID")
    gyr_id = params.get(f"INS_GYR{suffix}_ID")

    accel_name = accel_bus_type = None
    if acc_id is not None:
        decoded = decode_device_id(int(acc_id))
        accel_name = get_device_type_name(decoded["devtype"], "imu")
        accel_bus_type = decoded["bus_type_name"]

    gyro_name = gyro_bus_type = None
    if gyr_id is not None:
        decoded = decode_device_id(int(gyr_id))
        gyro_name = get_device_type_name(decoded["devtype"], "imu")
        gyro_bus_type = decoded["bus_type_name"]

    use_param = params.get(f"INS_USE{suffix}")
    use = None if use_param is None else use_param == 1

    accel_offsets = [params.get(f"INS_ACC{suffix}OFFS_{axis}") for axis in ("X", "Y", "Z")]
    accel_calibrated = None if any(v is None for v in accel_offsets) else any(v != 0 for v in accel_offsets)

    gyro_offsets = [params.get(f"INS_GYR{suffix}OFFS_{axis}") for axis in ("X", "Y", "Z")]
    gyro_calibrated = None if any(v is None for v in gyro_offsets) else any(v != 0 for v in gyro_offsets)

    enabled_codes = _tcal_enabled_codes(apm_doc, instance)
    tcal_enable = params.get(f"INS_TCAL{instance}_ENABLE")
    accel_temp_calibrated = None if tcal_enable is None else str(int(tcal_enable)) in enabled_codes
    gyro_temp_calibrated = accel_temp_calibrated
    position_offsets = [params.get(f"INS_POS{instance}_{axis}") for axis in ("X", "Y", "Z")]
    position_offset_set = None if any(v is None for v in position_offsets) else any(v != 0 for v in position_offsets)

    accel_healthy = gyro_healthy = None
    imu_columns = log_data.get_message_columns("IMU")
    names = imu_columns.dtype.names if imu_columns is not None else None
    if imu_columns is not None and imu_columns.size > 0 and names is not None and {"I", "AH", "GH"}.issubset(names):
        instance_numbers = log_data.get_field("IMU", "I")
        mask = instance_numbers == (instance - 1)

        if mask.any():
            ah_values = log_data.get_field("IMU", "AH")[mask]
            gh_values = log_data.get_field("IMU", "GH")[mask]
            accel_healthy = bool((ah_values == 0).sum() == 0)
            gyro_healthy = bool((gh_values == 0).sum() == 0)

    return ImuInfo(
        instance=instance,
        accel_name=accel_name,
        accel_bus_type=accel_bus_type,
        gyro_name=gyro_name,
        gyro_bus_type=gyro_bus_type,
        use=use,
        accel_calibrated=accel_calibrated,
        gyro_calibrated=gyro_calibrated,
        accel_temp_calibrated=accel_temp_calibrated,
        gyro_temp_calibrated=gyro_temp_calibrated,
        position_offset_set=position_offset_set,
        accel_healthy=accel_healthy,
        gyro_healthy=gyro_healthy,
    )


def _compass_external(params: dict[str, float], instance: int) -> bool | None:
    """Read COMPASS_EXTERNAL/2/3."""
    value = params.get("COMPASS_EXTERNAL") if instance == 1 else params.get(f"COMPASS_EXTERN{instance}")
    return None if value is None else value == 1


# Note: COMPASS_MOTCT (motor interference compensation) is not yet cross-checked here.
# Every test log so far has it at 0.0 (disabled).
def build_compass_info(apm_doc: APMDoc | None, log_data: LogData, params: dict[str, float], instance: int) -> CompassInfo:  # pylint: disable=too-many-locals
    """Build CompassInfo for one compass instance (1-indexed, matching ArduPilot's numbering)."""
    suffix = "" if instance == 1 else str(instance)

    dev_id = params.get(f"COMPASS_DEV_ID{suffix}")
    name = bus_type = None
    if dev_id is not None:
        decoded = decode_device_id(int(dev_id))
        name = get_device_type_name(decoded["devtype"], "compass")
        bus_type = decoded["bus_type_name"]

    use_param = params.get(f"COMPASS_USE{suffix}")
    use = None if use_param is None else use_param == 1

    offsets = [params.get(f"COMPASS_OFS{suffix}_{axis}") for axis in ("X", "Y", "Z")]
    calibrated = None if any(v is None for v in offsets) else any(v != 0 for v in offsets)

    mot_values = [params.get(f"COMPASS_MOT{suffix}_{axis}") for axis in ("X", "Y", "Z")]
    motct = params.get("COMPASS_MOTCT")
    motct_active = None
    if motct is not None and apm_doc is not None:
        motct_values = apm_doc.get("COMPASS_MOTCT", {}).get("values", {})
        motct_name = motct_values.get(str(int(motct)))
        motct_active = motct_name is not None and motct_name != "Disabled"
    motor_calibrated = None
    if not any(v is None for v in mot_values):
        offsets_set = any(v != 0 for v in mot_values)
        motor_calibrated = offsets_set if motct_active is None else (offsets_set and motct_active)

    external = _compass_external(params, instance)

    healthy = None
    mag_schema = log_data.schemas.get("MAG")
    if mag_schema is not None and "I" in mag_schema.fields and "Health" in mag_schema.fields:
        mag_columns = log_data.get_message_columns("MAG")
        if mag_columns is not None and mag_columns.size > 0:
            instance_numbers = log_data.get_field("MAG", "I")
            mask = instance_numbers == (instance - 1)
            if mask.any():
                health_values = log_data.get_field("MAG", "Health")[mask]
                healthy = bool((health_values == 0).sum() == 0)

    return CompassInfo(
        instance=instance,
        name=name,
        bus_type=bus_type,
        external=external,
        use=use,
        calibrated=calibrated,
        motor_calibrated=motor_calibrated,
        healthy=healthy,
    )


def build_baro_info(apm_doc: APMDoc | None, log_data: LogData, params: dict[str, float], instance: int) -> BaroInfo:  # pylint: disable=too-many-locals
    """Build BaroInfo for one barometer instance (1-indexed, matching ArduPilot's numbering)."""
    dev_id = params.get(f"BARO{instance}_DEVID")
    name = bus_type = None
    if dev_id is not None:
        decoded = decode_device_id(int(dev_id))
        name = get_device_type_name(decoded["devtype"], "baro")
        bus_type = decoded["bus_type_name"]

    wcf_enable = params.get("BARO_WCF_ENABLE")
    wind_compensation = None
    if wcf_enable is not None:
        if apm_doc is not None:
            wcf_values = apm_doc.get("BARO_WCF_ENABLE", {}).get("values", {})
            wcf_name = wcf_values.get(str(int(wcf_enable)))
            wind_compensation = wcf_name is not None and wcf_name.lower() not in ("disabled", "none")
        else:
            wind_compensation = wcf_enable == 1

    healthy = None
    baro_schema = log_data.schemas.get("BARO")
    if baro_schema is not None:
        health_field = "Health" if "Health" in baro_schema.fields else "H" if "H" in baro_schema.fields else None
        baro_columns = log_data.get_message_columns("BARO")
        names = baro_columns.dtype.names if baro_columns is not None else None
        if (
            health_field is not None
            and baro_columns is not None
            and baro_columns.size > 0
            and names is not None
            and "I" in names
        ):
            instance_numbers = log_data.get_field("BARO", "I")
            mask = instance_numbers == (instance - 1)
            if mask.any():
                health_values = log_data.get_field("BARO", health_field)[mask]
                healthy = bool((health_values == 0).sum() == 0)

    return BaroInfo(instance=instance, name=name, bus_type=bus_type, wind_compensation=wind_compensation, healthy=healthy)


def build_airspeed_info(apm_doc: APMDoc | None, log_data: LogData, params: dict[str, float], instance: int) -> AirspeedInfo:  # pylint: disable=too-many-locals
    """Build AirspeedInfo for one airspeed sensor instance."""
    suffix = "" if instance == 1 else str(instance)

    type_code = params.get(f"ARSPD_TYPE{suffix}")
    sensor_type = None
    if type_code is not None and apm_doc is not None:
        type_values = apm_doc.get("ARSPD_TYPE", {}).get("values", {})
        sensor_type = type_values.get(str(int(type_code)))

    use_code = params.get(f"ARSPD_USE{suffix}")
    use = None
    if use_code is not None and apm_doc is not None:
        use_values = apm_doc.get("ARSPD_USE", {}).get("values", {})
        use_name = use_values.get(str(int(use_code)))
        use = use_name in ("Use", "UseWhenZeroThrottle")

    healthy = None
    arsp_columns = log_data.get_message_columns("ARSP")
    if arsp_columns is not None and arsp_columns.size > 0:
        names = arsp_columns.dtype.names
        if names is not None and "H" in names and "I" in names:
            instance_numbers = log_data.get_field("ARSP", "I")
            mask = instance_numbers == (instance - 1)
            if mask.any():
                health_values = log_data.get_field("ARSP", "H")[mask]
                healthy = bool((health_values == 0).sum() == 0)

    return AirspeedInfo(instance=instance, sensor_type=sensor_type, use=use, healthy=healthy)
