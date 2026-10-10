"""
Migrate vehicle project parameter files from one format version to the next.

File renames between format versions are handled by the ``old_filenames`` entries
in ``configuration_steps_*.json`` together with the existing
``LocalFilesystem.rename_parameter_files()`` mechanism.  This module only handles
the operations that ``old_filenames`` cannot express:

* Extracting a subset of parameters from an existing file into a new file.
* Creating brand-new files whose content is not derived from any existing file.
* Deleting files that are no longer part of the configuration sequence.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import errno
import logging
import re
from contextlib import suppress
from json import dumps as json_dumps
from json import load as json_load
from os import O_CREAT, O_EXCL, O_WRONLY, close, fsync
from os import link as os_link
from os import open as os_open
from pathlib import Path
from secrets import token_hex
from shutil import copyfile, copyfileobj
from stat import S_IMODE

from ardupilot_methodic_configurator import _
from ardupilot_methodic_configurator.data_model_vehicle_project_creator import (
    VehicleProjectCreationError,
    VehicleProjectCreator,
)

# The versioned, vehicle-specific migration tables intentionally live together.
# pylint: disable=too-many-lines

# V2 rules target the draft reordered templates, but automatic V2 migration
# remains disabled until the production configuration sequence is released.
VEHICLE_COMPONENTS_FORMAT_VERSION = 1
_VEHICLE_COMPONENTS_JSON_FILENAME = "vehicle_components.json"
_PACKAGE_DIR = Path(__file__).resolve().parent

# ---------------------------------------------------------------------------
# Format version 0 → 1
# ---------------------------------------------------------------------------

# Each entry: (source_filename_v0, dest_filename_v1, list_of_param_name_patterns)
# Patterns are matched with re.fullmatch against the parameter name portion of each line.
# A plain string with no regex meta-characters is matched literally.
# If the destination file already exists the extracted lines are appended to it;
# idempotency is ensured naturally because the params are removed from the source
# after extraction, so a subsequent run extracts nothing.
#
# Keys: "all" entries run for every vehicle type; vehicle-type-specific entries
# ("ArduCopter", "ArduPlane", "Heli", "Rover") run only for matching projects.
# "all" entries are always processed first.
_PARAM_MOVES_V0_TO_V1: dict[str, list[tuple[str, str, list[str]]]] = {
    "all": [
        # BRD_HEAT_TARG and LOG_DISARMED leave 04_board_orientation → new finish file
        (
            "04_board_orientation.param",
            "04_imu_temperature_calibration_finish.param",
            ["BRD_HEAT_TARG", "LOG_DISARMED"],
        ),
        # RC receiver controller params leave 05_remote_controller → new controller file
        (
            "05_remote_controller.param",
            "07_remote_controller_controller.param",
            [r"ARMING_RUDDER", r"RC\d+_OPTION", "FS_THR_VALUE"],
        ),
        # Safety params leave 13_general_configuration → new safety file
        (
            "13_general_configuration.param",
            "16_safety_setup.param",
            ["ARMING_CHECK", "FENCE_TYPE", "FS_EKF_ACTION", "LAND_ALT_LOW", "RTL_ALT"],
        ),
        # Slew-rate params also leave 07_esc → same safety file (accumulated)
        (
            "07_esc.param",
            "16_safety_setup.param",
            ["ATC_RAT_PIT_SMAX", "ATC_RAT_RLL_SMAX", "ATC_RAT_YAW_SMAX", "PSC_ACCZ_SMAX"],
        ),
        (
            "07_esc.param",
            "14_logging.param",
            ["MOT_HOVER_LEARN"],
        ),
        # Autotune finish param leaves 53_everyday_use → new autotune finish file
        (
            "53_everyday_use.param",
            "45_autotune_finish.param",
            ["ATC_THR_MIX_MAX"],
        ),
        # Battery monitor params leave 08_batt1 / 09_batt2 → battery monitor step
        (
            "08_batt1.param",
            "10_battery_monitor.param",
            [
                r"BATT\d*_AMP_OFFSET",
                r"BATT\d*_AMP_PERVLT",
                r"BATT\d*_CURR_PIN",
                r"BATT\d*_I2C_BUS",
                r"BATT\d*_MONITOR",
                r"BATT\d*_VOLT_MULT",
                r"BATT\d*_VOLT_PIN",
            ],
        ),
        (
            "09_batt2.param",
            "10_battery_monitor.param",
            [
                r"BATT\d*_AMP_OFFSET",
                r"BATT\d*_AMP_PERVLT",
                r"BATT\d*_CURR_PIN",
                r"BATT\d*_I2C_BUS",
                r"BATT\d*_MONITOR",
                r"BATT\d*_VOLT_MULT",
                r"BATT\d*_VOLT_PIN",
            ],
        ),
        # Remaining battery params from 09_batt2 consolidate into 08_batt1
        (
            "09_batt2.param",
            "08_batt1.param",
            [
                r"BATT\d*_.+",
            ],
        ),
        # Motor / servo params leave 07_esc → dedicated esc step
        (
            "07_esc.param",
            "15_motor.param",
            [
                "BRD_IO_DSHOT",
                "BRD_IO_ENABLE",
                "MOT_PWM_MAX",
                "MOT_PWM_MIN",
                "NTF_BUZZ_TYPES",
                "NTF_LED_TYPES",
                "SERVO_BLH_AUTO",
                "SERVO_BLH_BDMASK",
                "SERVO_BLH_RVMASK",
                "SERVO_BLH_TEST",
                "SERVO_DSHOT_ESC",
                "SERVO_DSHOT_RATE",
                "SERVO_FTW_MASK",
                "SERVO_FTW_RVMASK",
                r"SERVO\d+_FUNCTION",
                r"SERVO\d+_MAX",
                r"SERVO\d+_MIN",
                r"SERVO\d+_TRIM",
                "TKOFF_RPM_MIN",
                "TKOFF_THR_MAX",
            ],
        ),
        # Motor / servo params leave 07_esc → dedicated motor step
        (
            "07_esc.param",
            "19_motor.param",
            [
                "ESC_HW_POLES",
                "SERVO_BLH_POLES",
                "SERVO_FTW_POLES",
            ],
        ),
        # Throttle / takeoff params leave 07_esc → dedicated throttle controller step
        (
            "07_esc.param",
            "20_throttle_controller.param",
            [
                "MOT_SPOOL_TIME",
                "TKOFF_SLEW_TIME",
            ],
        ),
    ],
    "ArduCopter": [],
    "ArduPlane": [],
    "Heli": [],
    "Rover": [],
}

# New files whose entire content is fixed (not derived from existing param lines).
# Each entry: (filename, file_content_string).  Empty string → empty file.
# Keys follow the same "all" / vehicle-type convention as _PARAM_MOVES_V0_TO_V1.
_NEW_FILES_V0_TO_V1: dict[str, list[tuple[str, str]]] = {
    "all": [
        ("18_osd.param", ("OSD_TYPE,0\n")),
        (
            "27_pid_notch_filter_logging.param",
            (
                "INS_LOG_BAT_MASK,1  # PID notch filters require batch logging, not raw logging\n"
                "INS_LOG_BAT_OPT,4  # PID notch filters require batch pre- and post- filters logging\n"
                "INS_RAW_LOG_OPT,0  # PID notch filters require batch logging, not raw logging\n"
                "LOG_BITMASK,2242525  # Log relevant data for PID notch filters tuning."
                " Later on we'll change this to other subsystems\n"
            ),
        ),
        (
            "28_pid_notch_filter_results.param",
            (
                "ATC_RAT_RLL_NTF,0\n"
                "ATC_RAT_PIT_NTF,0\n"
                "ATC_RAT_YAW_NTF,0\n"
                "PSC_ACCZ_NTF,0\n"
                "ATC_RAT_RLL_NEF,0\n"
                "ATC_RAT_PIT_NEF,0\n"
                "ATC_RAT_YAW_NEF,0\n"
                "PSC_ACCZ_NEF,0\n"
            ),
        ),
        # If ATC_THR_MIX_MAX was not moved in _PARAM_MOVES_V0_TO_V1 because it was not present,
        # then add it here with the correct value for autotune finish.
        # If it was moved then this will be a no-op because the file already exists and contains the moved value.
        (
            "45_autotune_finish.param",
            ("ATC_THR_MIX_MAX,0.9  # Maximize attitude control authority at high throttle\n"),
        ),
        (
            "46_pid_d_ff.param",
            ("ATC_RAT_RLL_D_FF,0\nATC_RAT_PIT_D_FF,0\nATC_RAT_YAW_D_FF,0\nPSC_ACCZ_D_FF,0\n"),
        ),
        (
            "49_windspeed_estimation_finish.param",
            (
                "LOG_DISARMED,0  # was only needed for wind speed estimation\n"
                "LOG_REPLAY,0  # was only needed for wind speed estimation\n"
            ),
        ),
        (
            "50_system_id_input_roll.param",
            (
                "ANGLE_MAX,3000\n"
                "ARMING_CHECK,1\n"
                "ATC_ANG_PIT_P,4.5\n"
                "ATC_ANG_RLL_P,4.5\n"
                "ATC_ANG_YAW_P,4.5\n"
                "ATC_RAT_RLL_I,0.135\n"
                "ATC_RATE_FF_ENAB,1\n"
                "FLTMODE5,0\n"
                "LOG_BITMASK,176126\n"
                "SID_AXIS,1  # Inject chip on the input roll signal\n"
                "SID_F_START_HZ,0.05\n"
                "SID_F_STOP_HZ,5\n"
                "SID_MAGNITUDE,0.15\n"
                "SID_T_FADE_IN,5\n"
                "SID_T_FADE_OUT,5\n"
                "SID_T_REC,130\n"
                "TUNE,0\n"
                "TUNE_MAX,0\n"
                "TUNE_MIN,0\n"
            ),
        ),
        (
            "51_system_id_input_pitch.param",
            (
                "ANGLE_MAX,3000\n"
                "ARMING_CHECK,1\n"
                "ATC_ANG_PIT_P,4.5\n"
                "ATC_ANG_RLL_P,4.5\n"
                "ATC_ANG_YAW_P,4.5\n"
                "ATC_RAT_RLL_I,0.135\n"
                "ATC_RATE_FF_ENAB,1\n"
                "FLTMODE5,0\n"
                "LOG_BITMASK,176126\n"
                "SID_AXIS,2  # Inject chip on the input pitch signal\n"
                "SID_F_START_HZ,0.05\n"
                "SID_F_STOP_HZ,5\n"
                "SID_MAGNITUDE,0.15\n"
                "SID_T_FADE_IN,5\n"
                "SID_T_FADE_OUT,5\n"
                "SID_T_REC,130\n"
                "TUNE,0\n"
                "TUNE_MAX,0\n"
                "TUNE_MIN,0\n"
            ),
        ),
        (
            "52_system_id_input_yaw.param",
            (
                "ANGLE_MAX,3000\n"
                "ARMING_CHECK,1\n"
                "ATC_ANG_PIT_P,4.5\n"
                "ATC_ANG_RLL_P,4.5\n"
                "ATC_ANG_YAW_P,4.5\n"
                "ATC_RAT_RLL_I,0.135\n"
                "ATC_RATE_FF_ENAB,1\n"
                "FLTMODE5,0\n"
                "LOG_BITMASK,176126\n"
                "SID_AXIS,3  # Inject chip on the input yaw signal\n"
                "SID_F_START_HZ,0.05\n"
                "SID_F_STOP_HZ,5\n"
                "SID_MAGNITUDE,0.15\n"
                "SID_T_FADE_IN,5\n"
                "SID_T_FADE_OUT,5\n"
                "SID_T_REC,130\n"
                "TUNE,0\n"
                "TUNE_MAX,0\n"
                "TUNE_MIN,0\n"
            ),
        ),
    ],
    "ArduCopter": [],
    "ArduPlane": [],
    "Heli": [],
    "Rover": [],
}

# Files that are no longer part of the sequence and must be removed.
# Keys follow the same "all" / vehicle-type convention as _PARAM_MOVES_V0_TO_V1.
_FILES_TO_DELETE_V0_TO_V1: dict[str, list[str]] = {
    "all": [
        "09_batt2.param",
        "26_quick_tune_setup.param",
        "27_quick_tune_results.param",
    ],
    "ArduCopter": [],
    "ArduPlane": [],
    "Heli": [],
    "Rover": [],
}

# ---------------------------------------------------------------------------
# Format version 1 → 2
# ---------------------------------------------------------------------------

# Destinations belong to each vehicle's own layout. Only ArduCopter has the
# split calibration/mode/servo layout used by the v2 migration fixture; the
# other vehicles retain their combined mandatory-hardware calibration step.
# IMUs 4/5 use INS4_/INS5_ subgroups, not suffixes on INS_ACC or INS_USE:
# https://github.com/ArduPilot/ardupilot/blob/Copter-4.6.3/libraries/AP_InertialSensor/AP_InertialSensor.cpp
# The final move flag controls conflicts: forced moves replace destination values;
# otherwise existing destination values win while the source values are removed.
_PARAM_MOVES_V1_TO_V2: dict[str, list[tuple[str, str, list[str], bool]]] = {
    "all": [],
    "ArduCopter": [
        (
            "14_mp_setup_mandatory_hardware.param",
            "16_accelerometer_calibration.param",
            [
                r"(?:INS_ACC[23]?OFFS|INS[45]_ACCOFFS)_[XYZ]",
                r"(?:INS_ACC[23]?SCAL|INS[45]_ACCSCAL)_[XYZ]",
                r"INS_USE[23]?|INS[45]_USE",
            ],
            True,
        ),
        (
            "14_mp_setup_mandatory_hardware.param",
            "03_imu_temperature_calibration_results.param",
            [r"INS_ACC[1-3]_CALTEMP|INS[45]_ACC_CALTEMP"],
            True,
        ),
        (
            "14_mp_setup_mandatory_hardware.param",
            "17_accelerometer_level.param",
            [r"AHRS_TRIM_[XY]"],
            True,
        ),
        (
            "14_mp_setup_mandatory_hardware.param",
            "19_compass_calibration.param",
            [r"COMPASS_.+"],
            True,
        ),
        (
            "14_mp_setup_mandatory_hardware.param",
            "22_flight_modes.param",
            [r"FLTMODE[1-6]", "INITIAL_MODE"],
            True,
        ),
        (
            "14_mp_setup_mandatory_hardware.param",
            "06_remote_controller_controller.param",
            [r"RC\d+_(?:MIN|MAX|TRIM)"],
            True,
        ),
        (
            "14_mp_setup_mandatory_hardware.param",
            "11_servo_outputs.param",
            [r"SERVO\d+_FUNCTION", "FRAME_CLASS"],
            True,
        ),
        (
            "14_mp_setup_mandatory_hardware.param",
            "13_initial_atc.param",
            [r"ATC_ACC_[PRY]_MAX"],
            True,
        ),
        (
            "14_mp_setup_mandatory_hardware.param",
            "29_motor_notch_filter_results.param",
            [r"INS_GYRO_FILTER", r"ATC_RAT_(?:PIT|RLL|YAW)_FLT[DT]"],
            False,
        ),
        (
            "14_mp_setup_mandatory_hardware.param",
            "23_general_configuration.param",
            [r"RNGFND\d*_.*|FLOW_TYPE"],
            True,
        ),
        (
            "05_board_orientation.param",
            "11_servo_outputs.param",
            ["FRAME_CLASS"],
            True,
        ),
        (
            "04_board_orientation.param",
            "11_servo_outputs.param",
            ["FRAME_CLASS"],
            True,
        ),
    ],
    "ArduPlane": [
        (
            "14_mp_setup_mandatory_hardware.param",
            "03_imu_temperature_calibration_results.param",
            [r"INS_ACC[1-3]_CALTEMP"],
            True,
        ),
        (
            "14_mp_setup_mandatory_hardware.param",
            "07_remote_controller_controller.param",
            [r"RC\d+_(?:MIN|MAX|TRIM|REVERSED)"],
            True,
        ),
        (
            "14_mp_setup_mandatory_hardware.param",
            "15_general_configuration.param",
            [r"FLTMODE[1-6]", "INITIAL_MODE"],
            True,
        ),
        (
            "14_mp_setup_mandatory_hardware.param",
            "16_safety_setup.param",
            ["FENCE_ACTION", "FENCE_ALT_MAX", "FENCE_ENABLE", "FENCE_RADIUS"],
            True,
        ),
    ],
    "Heli": [
        (
            "14_mp_setup_mandatory_hardware.param",
            "03_imu_temperature_calibration_results.param",
            [r"INS_ACC[1-3]_CALTEMP"],
            True,
        ),
        (
            "14_mp_setup_mandatory_hardware.param",
            "07_remote_controller_controller.param",
            [r"RC\d+_(?:MIN|MAX|TRIM|REVERSED)"],
            True,
        ),
        (
            "14_mp_setup_mandatory_hardware.param",
            "15_general_configuration.param",
            [r"FLTMODE[1-6]", "INITIAL_MODE"],
            True,
        ),
        (
            "14_mp_setup_mandatory_hardware.param",
            "16_safety_setup.param",
            ["FENCE_ACTION", "FENCE_ALT_MAX", "FENCE_ENABLE", "FENCE_RADIUS"],
            True,
        ),
    ],
    "Rover": [
        (
            "14_mp_setup_mandatory_hardware.param",
            "03_imu_temperature_calibration_results.param",
            [r"INS_ACC[1-3]_CALTEMP"],
            True,
        ),
        (
            "14_mp_setup_mandatory_hardware.param",
            "07_remote_controller_controller.param",
            [r"RC\d+_(?:MIN|MAX|TRIM|REVERSED)"],
            True,
        ),
        (
            "14_mp_setup_mandatory_hardware.param",
            "15_general_configuration.param",
            [r"MODE[1-6]", "INITIAL_MODE"],
            True,
        ),
        (
            "14_mp_setup_mandatory_hardware.param",
            "16_safety_setup.param",
            # Rover has no altitude fence; preserve any legacy FENCE_ALT_MAX
            # line in the source rather than applying a Copter deletion rule.
            ["FENCE_ACTION", "FENCE_ENABLE", "FENCE_RADIUS"],
            True,
        ),
    ],
}

# Some values remain in their historical step while also becoming part of the
# accelerometer calibration step in the v2 configuration.
_PARAM_COPIES_V1_TO_V2: dict[str, list[tuple[str, str, str, list[str]]]] = {
    "all": [],
    "ArduCopter": [
        (
            "14_mp_setup_mandatory_hardware.param",
            "03_imu_temperature_calibration_results.param",
            "16_accelerometer_calibration.param",
            [r"INS_ACC[1-3]_CALTEMP|INS[45]_ACC_CALTEMP"],
        ),
        (
            "14_mp_setup_mandatory_hardware.param",
            "17_accelerometer_level.param",
            "16_accelerometer_calibration.param",
            [r"AHRS_TRIM_[XY]"],
        ),
    ],
    # These vehicles keep calibration and level values together in the
    # mandatory-hardware step, so no duplicate calibration destinations exist.
    "ArduPlane": [],
    "Heli": [],
    "Rover": [],
}

_PARAM_DELETES_V1_TO_V2: dict[str, list[tuple[str, list[str]]]] = {
    "all": [],
    "ArduCopter": [
        (
            "14_mp_setup_mandatory_hardware.param",
            [
                "ATC_ACCEL_P_MAX",
                "ATC_ACCEL_R_MAX",
                "ATC_ACCEL_Y_MAX",
                "ATC_RAT_PIT_FLTD",
                "ATC_RAT_PIT_FLTT",
                "ATC_RAT_RLL_FLTD",
                "ATC_RAT_RLL_FLTT",
                "ATC_RAT_YAW_FLTE",
                "ATC_RAT_YAW_FLTT",
                "FENCE_ACTION",
                "FENCE_ALT_MAX",
                "FENCE_ENABLE",
                "FENCE_RADIUS",
                "FRAME_TYPE",
                "INS_GYRO_FILTER",
                "MOT_BAT_VOLT_MAX",
                "MOT_BAT_VOLT_MIN",
                "MOT_SPIN_ARM",
                "MOT_SPIN_MAX",
                "MOT_SPIN_MIN",
                "MOT_THST_EXPO",
                "MOT_THST_HOVER",
            ],
        ),
    ],
    # No corresponding obsolete hardware settings in the other layouts.
    "ArduPlane": [],
    "Heli": [],
    "Rover": [],
}

# Splits run before LocalFilesystem applies old_filenames renames. Include every
# historical mandatory-hardware filename declared by the configuration steps.
_MANDATORY_HARDWARE_OLD_FILENAMES = {
    "ArduCopter": ("11_mp_setup_mandatory_hardware.param", "12_mp_setup_mandatory_hardware.param"),
    "ArduPlane": ("11_mp_setup_mandatory_hardware.param", "12_mp_setup_mandatory_hardware.param"),
    "Heli": (
        "11_mp_setup_mandatory_hardware.param",
        "12_mp_setup_mandatory_hardware.param",
        # The OMP_M4 template predates the current Heli numbering.
        "15_mp_setup_mandatory_hardware.param",
    ),
    "Rover": ("11_mp_setup_mandatory_hardware.param", "12_mp_setup_mandatory_hardware.param"),
}
for _migration_key, _old_filenames in _MANDATORY_HARDWARE_OLD_FILENAMES.items():
    _migration_moves = _PARAM_MOVES_V1_TO_V2[_migration_key]
    for _old_filename in _old_filenames:
        _migration_moves.extend(
            (_old_filename, destination, patterns, force)
            for source, destination, patterns, force in tuple(_migration_moves)
            if source == "14_mp_setup_mandatory_hardware.param"
        )
        _PARAM_DELETES_V1_TO_V2[_migration_key].extend(
            (_old_filename, patterns)
            for source, patterns in tuple(_PARAM_DELETES_V1_TO_V2[_migration_key])
            if source == "14_mp_setup_mandatory_hardware.param"
        )
        _PARAM_COPIES_V1_TO_V2[_migration_key].extend(
            (_old_filename, source_destination, destination, patterns)
            for source, source_destination, destination, patterns in tuple(_PARAM_COPIES_V1_TO_V2[_migration_key])
            if source == "14_mp_setup_mandatory_hardware.param"
        )

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _read_param_file_lines(filepath: Path) -> list[str]:
    """Return all raw lines from a .param file, or an empty list if the file is absent."""
    try:
        with open(filepath, encoding="utf-8-sig") as fh:
            return fh.readlines()
    except FileNotFoundError:
        return []


def _write_migration_file_lines(filepath: Path, lines: list[str]) -> None:
    """Publish complete UTF-8/LF contents atomically, preserving existing permission bits."""
    temporary_path = filepath.parent / f".migration-{filepath.name}-{token_hex(16)}.tmp"
    existing_mode = S_IMODE(filepath.stat().st_mode) if filepath.exists() else None
    temporary_created = False
    try:
        # Exclusive creation leaves an occupied temporary name untouched and applies
        # normal umask/inherited permissions for newly created project files.
        with open(temporary_path, "x", encoding="utf-8", newline="\n") as fh:
            temporary_created = True
            fh.writelines(lines)
            fh.flush()
            if existing_mode is not None:
                temporary_path.chmod(existing_mode)
            fsync(fh.fileno())
        # All handles must be closed before replacement, including on Windows.
        temporary_path.replace(filepath)
    finally:
        if temporary_created:
            with suppress(OSError):
                temporary_path.unlink(missing_ok=True)


def _write_param_file_lines(filepath: Path, lines: list[str]) -> None:
    """Write parameter *lines* atomically using Unix line endings."""
    _write_migration_file_lines(filepath, lines)


def _param_name_from_line(line: str) -> str:
    """
    Return the parameter name from a .param file line, or an empty string.

    Blank lines and comment-only lines (starting with ``#``) return ``""``.
    Supports comma-, space-, and tab-separated parameter files using the same
    priority order as ParDict.load_param_file_into_dict: comma first, then
    space, then tab.
    """
    stripped = line.strip()
    if not stripped or stripped.startswith("#"):
        return ""
    # Strip inline comments before separator detection, matching the behaviour
    # of ParDict.load_param_file_into_dict, so that a line like
    # "NAME\t4 # comment" doesn't falsely split on the space before '#'.
    if "#" in stripped:
        stripped = stripped.split("#", 1)[0].strip()
    if not stripped:
        return ""
    if "," in stripped:
        return stripped.split(",", 1)[0].strip()
    if " " in stripped:
        return stripped.split(" ", 1)[0].strip()
    if "\t" in stripped:
        return stripped.split("\t", 1)[0].strip()
    return stripped


def _line_matches_any(param_name: str, patterns: list[str]) -> bool:
    """Return True if *param_name* matches any pattern in *patterns*."""
    for pattern in patterns:
        try:
            if re.fullmatch(pattern, param_name):
                return True
        except re.error:  # noqa: PERF203
            logging.warning(_("Skipping malformed regex pattern %r: not a valid regular expression"), pattern)
    return False


def _extract_param_lines(lines: list[str], patterns: list[str]) -> tuple[list[str], list[str]]:
    """Partition *lines* by whether each parameter name matches *patterns*."""
    extracted: list[str] = []
    remaining: list[str] = []
    for line in lines:
        name = _param_name_from_line(line)
        if name and _line_matches_any(name, patterns):
            extracted.append(line)
        else:
            remaining.append(line)
    return extracted, remaining


def _extract_params(source: Path, patterns: list[str]) -> tuple[list[str], list[str]]:
    """
    Partition lines of *source* by whether the parameter name matches *patterns*.

    Returns ``(extracted_lines, remaining_lines)``. Both lists preserve original
    line endings. If *source* does not exist the tuple ``([], [])`` is returned.
    """
    return _extract_param_lines(_read_param_file_lines(source), patterns)


def _copy_configuration_step_file_exclusively(source: Path, destination: Path) -> None:
    """
    Copy without overwriting when atomic hard-link publication is unavailable.

    Exclusive creation preserves competing files and normal file permissions.
    Unlike hard-link publication, readers may see the copy while it is being
    written. Remove our incomplete destination on failure so migration can retry.
    """
    created = False
    completed = False
    try:
        with source.open("rb") as source_file, destination.open("xb") as destination_file:
            created = True
            copyfileobj(source_file, destination_file)
            destination_file.flush()
            fsync(destination_file.fileno())
        completed = True
    finally:
        if created and not completed:
            with suppress(OSError):
                destination.unlink()


def _copy_configuration_step_file(source: Path, destination: Path) -> None:
    """Restore a template without overwriting, publishing atomically when hard links are supported."""
    temporary_path = destination.parent / f".migration-{token_hex(16)}.tmp"
    # Match normal file creation: let the OS apply umask and inherited ACLs rather
    # than publishing NamedTemporaryFile's private 0o600 permissions. Exclusive
    # creation protects existing files and symlinks at the temporary path.
    temporary_fd = os_open(temporary_path, O_CREAT | O_EXCL | O_WRONLY, 0o666)
    try:
        close(temporary_fd)
        copyfile(source, temporary_path)
        with temporary_path.open("r+b") as copied_file:
            fsync(copied_file.fileno())
        # Prefer atomic publication, but writable FAT/exFAT volumes and some
        # network filesystems cannot create hard links. Their fallback must use
        # exclusive creation, never a clobbering rename/replace.
        try:
            try:
                os_link(temporary_path, destination)
            except OSError as exc:
                if exc.errno not in {errno.EPERM, errno.ENOTSUP, errno.EOPNOTSUPP, errno.ENOSYS, errno.EXDEV} and getattr(
                    exc, "winerror", None
                ) not in {1, 50}:  # ERROR_INVALID_FUNCTION, ERROR_NOT_SUPPORTED
                    raise
                _copy_configuration_step_file_exclusively(temporary_path, destination)
        except FileExistsError:
            logging.info(_("Preserved configuration file created during template restoration: %s"), destination.name)
    finally:
        with suppress(OSError):
            temporary_path.unlink(missing_ok=True)


def _restore_missing_configuration_step_files(  # pylint: disable=too-many-locals
    vehicle_path: Path,
    vehicle_type: str,
    firmware_version: str,
    deleted_filenames: set[str] | None = None,
) -> None:
    """
    Copy missing configuration-step files from the matching empty firmware template.

    A project may be missing files introduced by a newer configuration. Restore only step files
    that exist in both the active configuration-step definition and the matching empty template.
    Existing project files, including empty files, are never overwritten. Matching .pdef.xml
    sidecars are restored with their step files. The v1→v2 migration calls this before splitting
    parameters so its destination files can be seeded from the template.
    Copies are published atomically where hard links are available; otherwise
    exclusive creation preserves existing files and failed copies are removed for retry.
    """
    version_match = re.search(r"(\d+)\.(\d+)", firmware_version)
    if not vehicle_type or not version_match:
        logging.warning(_("Cannot restore missing configuration files: firmware type or version is unavailable."))
        return

    major, minor = (int(part) for part in version_match.groups())
    try:
        template_dir = Path(VehicleProjectCreator.template_dir_for_bin_import(vehicle_type, major, minor))
    except VehicleProjectCreationError as exc:
        logging.warning(_("Migration template directory not found, skipping missing files: %s"), exc.message)
        return

    configuration_filename = f"configuration_steps_{vehicle_type}.json"
    configuration_path = vehicle_path / configuration_filename
    if not configuration_path.is_file():
        configuration_path = _PACKAGE_DIR / configuration_filename
    try:
        with open(configuration_path, encoding="utf-8-sig") as file:
            configuration_data = json_load(file)
    except (FileNotFoundError, OSError, ValueError) as exc:
        logging.warning(_("Cannot load configuration steps %s: %s"), configuration_path, exc)
        return

    steps = configuration_data.get("steps", {}) if isinstance(configuration_data, dict) else {}
    if not isinstance(steps, dict):
        logging.warning(_("Configuration steps file has no valid steps dictionary: %s"), configuration_path)
        return

    for filename, step_info in steps.items():
        if not isinstance(filename, str) or Path(filename).name != filename:
            logging.warning(_("Skipping unsafe configuration-step filename: %r"), filename)
            continue
        destination = vehicle_path / filename
        source = template_dir / filename
        if filename in (deleted_filenames or set()) or destination.exists() or not source.is_file():
            continue

        old_filenames = step_info.get("old_filenames", []) if isinstance(step_info, dict) else []
        if isinstance(old_filenames, list) and any(
            isinstance(old_filename, str)
            and Path(old_filename).name == old_filename
            and (vehicle_path / old_filename).is_file()
            for old_filename in old_filenames
        ):
            # LocalFilesystem.rename_parameter_files() will migrate this project file.
            # Restoring the new template filename here would block that rename.
            continue

        source_documentation = source.with_suffix(".pdef.xml")
        if source_documentation.is_file():
            # Publish documentation first so a failed sidecar copy can be retried without
            # the parameter file's presence causing this restoration to be skipped.
            _copy_configuration_step_file(source_documentation, destination.with_suffix(".pdef.xml"))
            logging.info(_("Restored missing configuration documentation from template: %s"), source_documentation.name)

        _copy_configuration_step_file(source, destination)
        logging.info(_("Restored missing configuration file from template: %s"), filename)


# ---------------------------------------------------------------------------
# Per-version migration logic
# ---------------------------------------------------------------------------


def _migrate_v0_to_v1(vehicle_path: Path, vehicle_type: str) -> set[str]:  # pylint: disable=too-many-locals, too-many-branches
    """
    Apply all format-version 0 → 1 migrations inside *vehicle_path*.

    Processes ``"all"`` entries first, then entries for *vehicle_type* (if present).

    **Step 1 - parameter extractions.**
    Parameters are moved from their old source files into destination files.
    Multiple sources may feed the same destination (they are accumulated).
    If the destination already exists the extracted lines are appended to it;
    idempotency is ensured naturally because params are removed from the source
    after extraction, so a subsequent run extracts nothing.

    **Step 2 - new files with fixed content.**
    Created only when they do not yet exist (idempotent).

    **Step 3 - deletion of obsolete files.**
    """
    deleted_filenames: set[str] = set()

    # Step 1: parameter extractions
    accumulated: dict[str, list[str]] = {}  # dest filename → lines to append

    known_vehicle_types = set(_PARAM_MOVES_V0_TO_V1) - {"all"}
    if vehicle_type and vehicle_type not in known_vehicle_types:
        logging.error(
            _("Unknown vehicle type %r; no type-specific migrations will run. Known types: %s"),
            vehicle_type,
            sorted(known_vehicle_types),
        )

    param_move_keys = ["all"] + ([vehicle_type] if vehicle_type and vehicle_type in _PARAM_MOVES_V0_TO_V1 else [])
    for key in param_move_keys:
        for src_name, dst_name, patterns in _PARAM_MOVES_V0_TO_V1[key]:
            src_path = vehicle_path / src_name

            if not src_path.exists():
                logging.warning(_("Migration source file not found, skipping extraction: %s"), src_name)
                continue

            extracted, remaining = _extract_params(src_path, patterns)
            if not extracted:
                continue

            accumulated.setdefault(dst_name, []).extend(extracted)
            _write_param_file_lines(src_path, remaining)
            logging.info(_("Extracted %d parameter line(s) from %s for %s"), len(extracted), src_name, dst_name)

    for dst_name, lines in accumulated.items():
        dst_path = vehicle_path / dst_name
        existing = _read_param_file_lines(dst_path) if dst_path.exists() else []
        existing_names = {
            _param_name_from_line(existing_line) for existing_line in existing if _param_name_from_line(existing_line)
        }
        new_lines = [line for line in lines if _param_name_from_line(line) not in existing_names]
        if not new_lines:
            continue
        _write_param_file_lines(dst_path, existing + new_lines)
        logging.info(_("%s parameter migration file: %s"), _("Updated") if existing else _("Created"), dst_name)

    # Step 2: new files with fixed content
    new_file_keys = ["all"] + ([vehicle_type] if vehicle_type and vehicle_type in _NEW_FILES_V0_TO_V1 else [])
    for key in new_file_keys:
        for filename, content in _NEW_FILES_V0_TO_V1[key]:
            file_path = vehicle_path / filename
            if not file_path.exists():
                _write_param_file_lines(file_path, [content] if content else [])
                logging.info(_("Created new file: %s"), filename)

    # Step 3: delete obsolete files
    delete_keys = ["all"] + ([vehicle_type] if vehicle_type and vehicle_type in _FILES_TO_DELETE_V0_TO_V1 else [])
    for key in delete_keys:
        for filename in _FILES_TO_DELETE_V0_TO_V1[key]:
            file_path = vehicle_path / filename
            if file_path.exists():
                remaining_params = [_param_name_from_line(line) for line in _read_param_file_lines(file_path)]
                remaining_params = [name for name in remaining_params if name]
                if remaining_params:
                    logging.warning(
                        _("Deleting obsolete file %s which still contains %d unmigrated parameter(s): %s"),
                        filename,
                        len(remaining_params),
                        remaining_params,
                    )
                file_path.unlink()
                deleted_filenames.add(filename)
                logging.info(_("Deleted obsolete file: %s"), filename)

    return deleted_filenames


def _surface_unmapped_copter_parameters(remaining_by_source: dict[Path, list[str]], accumulated: dict[str, list[str]]) -> None:
    """Keep unrecognized hardware values recoverable and visible in a mandatory step."""
    obsolete_patterns = dict(_PARAM_DELETES_V1_TO_V2["ArduCopter"])
    for src_path, remaining in remaining_by_source.items():
        if src_path.name not in obsolete_patterns:
            continue
        _obsolete, retained = _extract_param_lines(remaining, obsolete_patterns[src_path.name])
        unmapped = [line for line in retained if _param_name_from_line(line)]
        if unmapped:
            destination = "23_general_configuration.param"
            accumulated.setdefault(destination, []).extend(unmapped)
            logging.warning(
                _("Unmapped parameters from %s copied to mandatory step %s for review: %s"),
                src_path.name,
                destination,
                [_param_name_from_line(line) for line in unmapped],
            )


def _migration_destination_paths(vehicle_path: Path, vehicle_type: str) -> dict[str, Path]:
    """Overlay migrated values onto existing aliases before the normal filename renames."""
    configuration_path = vehicle_path / f"configuration_steps_{vehicle_type}.json"
    if not configuration_path.is_file():
        configuration_path = _PACKAGE_DIR / f"configuration_steps_{vehicle_type}.json"
    try:
        with open(configuration_path, encoding="utf-8-sig") as file:
            configuration_data = json_load(file)
    except (OSError, ValueError) as exc:
        logging.warning(_("Cannot load configuration steps %s: %s"), configuration_path, exc)
        return {}
    steps = configuration_data.get("steps", {}) if isinstance(configuration_data, dict) else {}
    if not isinstance(steps, dict):
        return {}

    destinations: dict[str, Path] = {}
    for filename, step_info in steps.items():
        if not isinstance(filename, str) or Path(filename).name != filename or not isinstance(step_info, dict):
            continue
        if (vehicle_path / filename).exists():
            continue
        old_filenames = step_info.get("old_filenames", [])
        if not isinstance(old_filenames, list):
            continue
        for old_filename in old_filenames:
            if (
                isinstance(old_filename, str)
                and Path(old_filename).name == old_filename
                and (vehicle_path / old_filename).is_file()
            ):
                destinations[filename] = vehicle_path / old_filename
                break
    return destinations


def _merge_migrated_parameter_lines(existing: list[str], moved: list[str], forced_names: set[str]) -> list[str]:
    """Merge moved values, preserving existing values unless their move is forced."""
    moved_names = {_param_name_from_line(line) for line in moved if _param_name_from_line(line)}
    existing_names = {_param_name_from_line(line) for line in existing if _param_name_from_line(line)}
    names_to_replace = forced_names | {name for name in moved_names if name not in existing_names}
    retained_existing = [line for line in existing if _param_name_from_line(line) not in names_to_replace]

    unique_moved_lines: list[str] = []
    seen_moved_names: set[str] = set()
    for line in reversed(moved):
        name = _param_name_from_line(line)
        if name and name in seen_moved_names:
            continue
        if name:
            seen_moved_names.add(name)
            if name in existing_names and name not in forced_names:
                continue
        unique_moved_lines.append(line)
    unique_moved_lines.reverse()
    return retained_existing + unique_moved_lines


def _migrate_v1_to_v2(vehicle_path: Path, vehicle_type: str) -> set[str]:  # noqa: PLR0915  # pylint: disable=too-many-locals, too-many-branches, too-many-statements
    """Move hardware settings to the matching vehicle layout, splitting calibration only for ArduCopter."""
    deleted_filenames: set[str] = set()
    accumulated: dict[str, list[str]] = {}
    forced_parameters: dict[str, set[str]] = {}
    remaining_by_source: dict[Path, list[str]] = {}
    destination_paths = _migration_destination_paths(vehicle_path, vehicle_type)

    param_move_keys = ["all"] + ([vehicle_type] if vehicle_type in _PARAM_MOVES_V1_TO_V2 else [])
    for key in param_move_keys:
        for src_name, dst_name, patterns, force in _PARAM_MOVES_V1_TO_V2[key]:
            src_path = vehicle_path / src_name
            if not src_path.exists():
                logging.warning(_("Migration source file not found, skipping extraction: %s"), src_name)
                continue

            source_lines = remaining_by_source.get(src_path)
            if source_lines is None:
                source_lines = _read_param_file_lines(src_path)
            extracted, remaining = _extract_param_lines(source_lines, patterns)
            if not extracted:
                remaining_by_source.setdefault(src_path, source_lines)
                continue

            accumulated.setdefault(dst_name, []).extend(extracted)
            if force:
                forced_parameters.setdefault(dst_name, set()).update(
                    name for line in extracted if (name := _param_name_from_line(line))
                )
            remaining_by_source[src_path] = remaining
            logging.info(_("Extracted %d parameter line(s) from %s for %s"), len(extracted), src_name, dst_name)

    param_copy_keys = ["all"] + ([vehicle_type] if vehicle_type in _PARAM_COPIES_V1_TO_V2 else [])
    for key in param_copy_keys:
        for _src_name, source_dst_name, dst_name, patterns in _PARAM_COPIES_V1_TO_V2[key]:
            copied = [
                line
                for line in accumulated.get(source_dst_name, [])
                if (name := _param_name_from_line(line)) and _line_matches_any(name, patterns)
            ]
            if copied:
                accumulated.setdefault(dst_name, []).extend(copied)
                forced_parameters.setdefault(dst_name, set()).update(
                    name for line in copied if (name := _param_name_from_line(line))
                )

    if vehicle_type == "ArduCopter":
        # The split layout no longer lists the combined hardware step. Preserve
        # unknown values there for recovery, but also surface them in a mandatory
        # step so simple-mode users can review them. Publish before trimming sources.
        _surface_unmapped_copter_parameters(remaining_by_source, accumulated)
        forced_parameters.setdefault("23_general_configuration.param", set()).update(
            name
            for line in accumulated.get("23_general_configuration.param", [])
            if (name := _param_name_from_line(line))
        )

    for dst_name, lines in accumulated.items():
        dst_path = destination_paths.get(dst_name, vehicle_path / dst_name)
        existing = _read_param_file_lines(dst_path) if dst_path.exists() else []
        merged_lines = _merge_migrated_parameter_lines(existing, lines, forced_parameters.get(dst_name, set()))
        _write_param_file_lines(dst_path, merged_lines)
        logging.info(_("%s parameter migration file: %s"), _("Updated") if existing else _("Created"), dst_name)

    # Commit extracted values to destinations before trimming the source files.
    # If interrupted between these writes, the destination-name merge is idempotent.
    for src_path, remaining in remaining_by_source.items():
        _write_param_file_lines(src_path, remaining)

    for key in ["all"] + ([vehicle_type] if vehicle_type in _PARAM_DELETES_V1_TO_V2 else []):
        for src_name, patterns in _PARAM_DELETES_V1_TO_V2[key]:
            src_path = vehicle_path / src_name
            if not src_path.exists():
                continue
            deleted, remaining = _extract_params(src_path, patterns)
            if deleted:
                logging.info(_("Deleted %d obsolete parameter line(s) from %s"), len(deleted), src_name)
                if any(_param_name_from_line(line) for line in remaining):
                    _write_param_file_lines(src_path, remaining)
                else:
                    src_path.unlink()
                    deleted_filenames.add(src_name)
                    logging.info(_("Deleted empty parameter file: %s"), src_name)
            elif src_path in remaining_by_source and not any(_param_name_from_line(line) for line in remaining):
                src_path.unlink()
                deleted_filenames.add(src_name)
                logging.info(_("Deleted empty parameter file: %s"), src_name)

    return deleted_filenames


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def migrate_vehicle_project_if_needed(vehicle_dir: str) -> bool:  # pylint: disable=too-many-locals
    """
    Migrate the vehicle project in *vehicle_dir* to the latest supported version.

    Reads ``vehicle_components.json`` and applies supported migrations in order,
    persisting every intermediate version before proceeding to the next stage.
    Parameter-file splits, new-file creation, and obsolete-file deletion are
    applied for all vehicle types (see module docstring).

    File renames are *not* performed here; they are handled by the
    ``old_filenames`` entries in ``ardupilot_methodic_configurator/configuration_steps_*.json`` via
    :meth:`LocalFilesystem.rename_parameter_files`.

    Returns ``True`` if a migration was performed, ``False`` otherwise.
    """
    if not vehicle_dir:
        return False

    vehicle_path = Path(vehicle_dir)
    json_path = vehicle_path / _VEHICLE_COMPONENTS_JSON_FILENAME
    if not json_path.exists():
        return False

    try:
        with open(json_path, encoding="utf-8-sig") as fh:
            data: dict = json_load(fh)
    except (OSError, ValueError) as exc:
        logging.error(_("Failed to load %s: %s"), json_path, exc)
        return False

    if not isinstance(data, dict):
        return False

    format_version: int = data.get("Format version", 0)
    if format_version < 0 or format_version >= VEHICLE_COMPONENTS_FORMAT_VERSION:
        return False

    firmware = data.get("Components", {}).get("Flight Controller", {}).get("Firmware", {})
    vehicle_type: str = firmware.get("Type", "")
    firmware_version: str = firmware.get("Version", "")

    migrated = False
    deleted_filenames_to_skip_restore: set[str] = set()
    while format_version < VEHICLE_COMPONENTS_FORMAT_VERSION:
        next_format_version = format_version + 1
        logging.info(
            _("Migrating %s vehicle project in '%s' from format version %d to %d"),
            vehicle_type or _("unknown"),
            vehicle_dir,
            format_version,
            next_format_version,
        )

        if next_format_version == 1:
            deleted_filenames = _migrate_v0_to_v1(vehicle_path, vehicle_type) or set()
        elif next_format_version == 2:
            # Seed v2 destinations before extracting project values. The split then overlays
            # those values onto the empty-template defaults instead of creating empty shells
            # that prevent the final restoration pass from copying template content.
            v2_source_filenames = {
                src_name
                for migration_key in ["all"] + ([vehicle_type] if vehicle_type in _PARAM_MOVES_V1_TO_V2 else [])
                for src_name, _dst_name, _patterns, _force in _PARAM_MOVES_V1_TO_V2[migration_key]
            }
            _restore_missing_configuration_step_files(
                vehicle_path,
                vehicle_type,
                firmware_version,
                deleted_filenames_to_skip_restore | v2_source_filenames,
            )
            deleted_filenames = _migrate_v1_to_v2(vehicle_path, vehicle_type) or set()
        else:
            logging.error(_("No migration path is defined from format version %d"), format_version)
            break

        deleted_filenames_to_skip_restore.update(deleted_filenames)
        if next_format_version == VEHICLE_COMPONENTS_FORMAT_VERSION:
            _restore_missing_configuration_step_files(
                vehicle_path, vehicle_type, firmware_version, deleted_filenames_to_skip_restore
            )

        # Persist every stage before running the next one. If the process stops
        # here, the next open resumes from this version instead of replaying v0→v1.
        data["Format version"] = next_format_version
        json_str = json_dumps(data, indent=4)
        content = json_str.rstrip("\n") + "\n"
        _write_migration_file_lines(json_path, [content])

        format_version = next_format_version
        migrated = True
        logging.info(_("Migration to format version %d complete"), format_version)

    return migrated
