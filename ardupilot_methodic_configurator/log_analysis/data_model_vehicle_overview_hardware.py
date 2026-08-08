"""
Hardware inventory extraction helpers.

SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-FileCopyrightText: 2026 Omkar Sarkar <omkarsarkar24@gmail.com>

SPDX-License-Identifier: GPL-3.0-or-later
"""

from ardupilot_methodic_configurator.log_analysis.data_model_log_data import LogData
from ardupilot_methodic_configurator.log_analysis.data_model_vehicle_overview import (
    AirspeedInfo,
    BaroInfo,
    CompassInfo,
    HardwareReport,
    ImuInfo,
)
from ardupilot_methodic_configurator.log_analysis.data_model_vehicle_overview_compass_rules import (
    compass_external,
    compass_motor_calibrated,
)
from ardupilot_methodic_configurator.log_analysis.data_model_vehicle_overview_feature_flags import (
    airspeed_use_enabled_from_name,
    wind_compensation_enabled_from_name,
)
from ardupilot_methodic_configurator.log_analysis.data_model_vehicle_overview_health import (
    instance_health_from_message_field,
)
from ardupilot_methodic_configurator.log_analysis.data_model_vehicle_overview_health_rules import (
    airspeed_health,
    baro_health,
    compass_health,
    imu_health,
)
from ardupilot_methodic_configurator.log_analysis.data_model_vehicle_overview_identity import (
    extract_vehicle_info,
    resolve_board_name,
)
from ardupilot_methodic_configurator.log_analysis.data_model_vehicle_overview_imu_rules import (
    imu_axes_offsets,
    imu_axes_offsets_by_instance,
    imu_calibration_from_offsets,
    imu_temp_calibrated,
)
from ardupilot_methodic_configurator.log_analysis.data_model_vehicle_overview_instances import (
    airspeed_type_param,
    airspeed_use_param,
    baro_device_id_param,
    collect_present_instances,
    compass_device_id_param,
    imu_device_id_param,
    instance_suffix,
)
from ardupilot_methodic_configurator.log_analysis.data_model_vehicle_overview_param_metadata import (
    enum_value_name,
    tcal_enabled_codes,
)
from ardupilot_methodic_configurator.log_analysis.data_model_vehicle_overview_sensor_rules import (
    any_nonzero,
    decode_name_and_bus,
    parameter_enabled,
)
from ardupilot_methodic_configurator.log_analysis.utils import APMDoc

# Compatibility alias retained for the facade and existing imports.
_instance_health_from_message_field = instance_health_from_message_field


def extract_hardware_report(log_data: LogData, params: dict[str, float], apm_doc: APMDoc | None) -> HardwareReport:
    """Build the complete hardware overview for a parsed log."""
    vehicle = extract_vehicle_info(log_data)
    board_name = resolve_board_name(vehicle.board_id)

    imus = collect_present_instances(
        params,
        (1, 2, 3),
        imu_device_id_param,
        lambda instance: build_imu_info(apm_doc, log_data, params, instance),
    )

    compasses = collect_present_instances(
        params,
        (1, 2, 3),
        compass_device_id_param,
        lambda instance: build_compass_info(apm_doc, log_data, params, instance),
    )

    baros = collect_present_instances(
        params,
        (1, 2, 3),
        baro_device_id_param,
        lambda instance: build_baro_info(apm_doc, log_data, params, instance),
    )

    airspeed_sensors = collect_present_instances(
        params,
        (1, 2),
        airspeed_type_param,
        lambda instance: build_airspeed_info(apm_doc, log_data, params, instance),
    )

    return HardwareReport(
        vehicle=vehicle,
        board_name=board_name,
        imus=imus,
        compasses=compasses,
        baros=baros,
        airspeed_sensors=airspeed_sensors,
    )


def build_imu_info(apm_doc: APMDoc | None, log_data: LogData, params: dict[str, float], instance: int) -> ImuInfo:  # pylint: disable=too-many-locals
    """Build ImuInfo for one IMU instance."""
    suffix = instance_suffix(instance)

    acc_id = params.get(f"INS_ACC{suffix}_ID")
    gyr_id = params.get(f"INS_GYR{suffix}_ID")

    accel_name, accel_bus_type = decode_name_and_bus(acc_id, "imu")
    gyro_name, gyro_bus_type = decode_name_and_bus(gyr_id, "imu")

    use = parameter_enabled(params, f"INS_USE{suffix}")

    accel_offsets = imu_axes_offsets(params, "INS_ACC", f"{suffix}OFFS")
    accel_calibrated = imu_calibration_from_offsets(accel_offsets)

    gyro_offsets = imu_axes_offsets(params, "INS_GYR", f"{suffix}OFFS")
    gyro_calibrated = imu_calibration_from_offsets(gyro_offsets)

    enabled_codes = tcal_enabled_codes(apm_doc, instance)
    tcal_enable = params.get(f"INS_TCAL{instance}_ENABLE")
    accel_temp_calibrated = imu_temp_calibrated(tcal_enable, enabled_codes)
    gyro_temp_calibrated = accel_temp_calibrated
    position_offsets = imu_axes_offsets_by_instance(params, "INS_POS", instance)
    position_offset_set = imu_calibration_from_offsets(position_offsets)

    accel_healthy, gyro_healthy = imu_health(log_data, instance)

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


def build_compass_info(apm_doc: APMDoc | None, log_data: LogData, params: dict[str, float], instance: int) -> CompassInfo:  # pylint: disable=too-many-locals
    """Build CompassInfo for one compass instance (1-indexed, matching ArduPilot's numbering)."""
    suffix = instance_suffix(instance)

    dev_id = params.get(f"COMPASS_DEV_ID{suffix}")
    name, bus_type = decode_name_and_bus(dev_id, "compass")

    use = parameter_enabled(params, f"COMPASS_USE{suffix}")

    offsets = [params.get(f"COMPASS_OFS{suffix}_{axis}") for axis in ("X", "Y", "Z")]
    calibrated = any_nonzero(offsets)

    mot_values = [params.get(f"COMPASS_MOT{suffix}_{axis}") for axis in ("X", "Y", "Z")]
    motct = params.get("COMPASS_MOTCT")
    motct_active = None
    if motct is not None and apm_doc is not None:
        motct_name = enum_value_name(apm_doc, "COMPASS_MOTCT", motct)
        motct_active = motct_name is not None and motct_name != "Disabled"
    motor_calibrated = compass_motor_calibrated(mot_values, motct_active)

    external = compass_external(params, instance)

    healthy = compass_health(log_data, instance)

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


def build_baro_info(apm_doc: APMDoc | None, log_data: LogData, params: dict[str, float], instance: int) -> BaroInfo:
    """Build BaroInfo for one barometer instance (1-indexed, matching ArduPilot's numbering)."""
    dev_id = params.get(f"BARO{instance}_DEVID")
    name, bus_type = decode_name_and_bus(dev_id, "baro")

    wcf_enable = params.get("BARO_WCF_ENABLE")
    wind_compensation = None
    if wcf_enable is not None:
        if apm_doc is not None:
            wcf_name = enum_value_name(apm_doc, "BARO_WCF_ENABLE", wcf_enable)
            wind_compensation = wind_compensation_enabled_from_name(wcf_name)
        else:
            wind_compensation = wcf_enable == 1

    healthy = baro_health(log_data, instance)

    return BaroInfo(instance=instance, name=name, bus_type=bus_type, wind_compensation=wind_compensation, healthy=healthy)


def build_airspeed_info(apm_doc: APMDoc | None, log_data: LogData, params: dict[str, float], instance: int) -> AirspeedInfo:
    """Build AirspeedInfo for one airspeed sensor instance."""
    type_param = airspeed_type_param(instance)
    use_param = airspeed_use_param(instance)

    type_code = params.get(type_param)
    sensor_type = None
    if type_code is not None:
        sensor_type = enum_value_name(apm_doc, type_param, type_code)

    use_code = params.get(use_param)
    use = None
    if use_code is not None:
        use_name = enum_value_name(apm_doc, use_param, use_code)
        use = airspeed_use_enabled_from_name(use_name)

    healthy = airspeed_health(log_data, instance)

    return AirspeedInfo(instance=instance, sensor_type=sensor_type, use=use, healthy=healthy)
