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

import logging
import re
from json import dumps as json_dumps
from json import load as json_load
from pathlib import Path
from shutil import copyfile

from ardupilot_methodic_configurator import _
from ardupilot_methodic_configurator.data_model_vehicle_project_creator import (
    VehicleProjectCreationError,
    VehicleProjectCreator,
)

VEHICLE_COMPONENTS_FORMAT_VERSION = 2
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

_PARAM_MOVES_V1_TO_V2: dict[str, list[tuple[str, str, list[str]]]] = {
    "all": [
        (
            "14_mp_setup_mandatory_hardware.param",
            "14_accelerometer_calibration.param",
            [r"INS_ACC(?:[2-3])?SCAL_[XYZ]", r"INS_USE[2-3]?"],
        ),
        (
            "14_mp_setup_mandatory_hardware.param",
            "03_imu_temperature_calibration_results.param",
            [r"INS_ACC[1-3]_CALTEMP"],
        ),
        (
            "14_mp_setup_mandatory_hardware.param",
            "15_accelerometer_level.param",
            [r"AHRS_TRIM_[XY]"],
        ),
        (
            "14_mp_setup_mandatory_hardware.param",
            "16_compass_calibration.param",
            [r"COMPASS_.+"],
        ),
        (
            "14_mp_setup_mandatory_hardware.param",
            "17_flight_modes.param",
            [r"FLTMODE[1-6]"],
        ),
        (
            "14_mp_setup_mandatory_hardware.param",
            "07_remote_controller_controller.param",
            [r"RC\d+_(?:MIN|MAX|TRIM)"],
        ),
        (
            "14_mp_setup_mandatory_hardware.param",
            "18_servo_outputs.param",
            [r"SERVO\d+_FUNCTION"],
        ),
    ],
    "ArduCopter": [],
    "ArduPlane": [],
    "Heli": [],
    "Rover": [],
}

_NEW_FILES_V1_TO_V2: dict[str, list[tuple[str, str]]] = {
    "all": [
        ("14_accelerometer_calibration.param", ""),
        ("15_accelerometer_level.param", ""),
        ("16_compass_calibration.param", ""),
        ("17_flight_modes.param", ""),
        ("18_servo_outputs.param", ""),
    ],
    "ArduCopter": [],
    "ArduPlane": [],
    "Heli": [],
    "Rover": [],
}

_PARAM_DELETES_V1_TO_V2: dict[str, list[tuple[str, list[str]]]] = {
    "all": [
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
                "FRAME_CLASS",
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
    "ArduCopter": [],
    "ArduPlane": [],
    "Heli": [],
    "Rover": [],
}

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


def _write_param_file_lines(filepath: Path, lines: list[str]) -> None:
    """Write *lines* to *filepath* using Unix line endings."""
    with open(filepath, "w", encoding="utf-8", newline="\n") as fh:
        fh.writelines(lines)


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


def _extract_params(source: Path, patterns: list[str]) -> tuple[list[str], list[str]]:
    """
    Partition lines of *source* by whether the parameter name matches *patterns*.

    Returns ``(extracted_lines, remaining_lines)``.  Both lists preserve the
    original line endings.  If *source* does not exist the tuple ``([], [])``
    is returned.
    """
    lines = _read_param_file_lines(source)
    extracted: list[str] = []
    remaining: list[str] = []
    for line in lines:
        name = _param_name_from_line(line)
        if name and _line_matches_any(name, patterns):
            extracted.append(line)
        else:
            remaining.append(line)
    return extracted, remaining


def _restore_missing_configuration_step_files(vehicle_path: Path, vehicle_type: str, firmware_version: str) -> None:
    """
    Copy missing configuration-step files from the matching empty firmware template.

    A project may have been created before a configuration step was introduced.  Once all
    version-specific migration operations have completed, restore only those absent step files
    that exist in both the current configuration-step definition and the matching empty template.
    Existing project files, including empty files, are never overwritten.
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

    for filename in steps:
        if not isinstance(filename, str) or Path(filename).name != filename:
            logging.warning(_("Skipping unsafe configuration-step filename: %r"), filename)
            continue
        destination = vehicle_path / filename
        source = template_dir / filename
        if destination.exists() or not source.is_file():
            continue
        copyfile(source, destination)
        logging.info(_("Restored missing configuration file from template: %s"), filename)


# ---------------------------------------------------------------------------
# Per-version migration logic
# ---------------------------------------------------------------------------


def _migrate_v0_to_v1(vehicle_path: Path, vehicle_type: str) -> None:  # pylint: disable=too-many-locals, too-many-branches
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
                logging.info(_("Deleted obsolete file: %s"), filename)


def _migrate_v1_to_v2(vehicle_path: Path, vehicle_type: str) -> None:
    """Split mandatory hardware calibration results into dedicated ArduCopter files."""
    accumulated: dict[str, list[str]] = {}

    param_move_keys = ["all"] + ([vehicle_type] if vehicle_type in _PARAM_MOVES_V1_TO_V2 else [])
    for key in param_move_keys:
        for src_name, dst_name, patterns in _PARAM_MOVES_V1_TO_V2[key]:
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
                    logging.info(_("Deleted empty parameter file: %s"), src_name)

    new_file_keys = ["all"] + ([vehicle_type] if vehicle_type in _NEW_FILES_V1_TO_V2 else [])
    for key in new_file_keys:
        for filename, content in _NEW_FILES_V1_TO_V2[key]:
            file_path = vehicle_path / filename
            if not file_path.exists():
                _write_param_file_lines(file_path, [content] if content else [])
                logging.info(_("Created new file: %s"), filename)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def migrate_vehicle_project_if_needed(vehicle_dir: str) -> bool:
    """
    Migrate the vehicle project in *vehicle_dir* to the latest format version.

    Reads ``vehicle_components.json``, checks ``"Format version"``, and—if the
    project is on an older format version—migrates it and updates the
    ``"Format version"`` field.  Parameter-file splits, new-file creation, and
    obsolete-file deletion are applied for all vehicle types (see module
    docstring).  The JSON file is saved before returning.

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
    if format_version >= VEHICLE_COMPONENTS_FORMAT_VERSION:
        return False

    firmware = data.get("Components", {}).get("Flight Controller", {}).get("Firmware", {})
    vehicle_type: str = firmware.get("Type", "")
    firmware_version: str = firmware.get("Version", "")

    logging.info(
        _("Migrating %s vehicle project in '%s' from format version %d to %d"),
        vehicle_type or _("unknown"),
        vehicle_dir,
        format_version,
        VEHICLE_COMPONENTS_FORMAT_VERSION,
    )

    if format_version < 1:
        _migrate_v0_to_v1(vehicle_path, vehicle_type)
        _restore_missing_configuration_step_files(vehicle_path, vehicle_type, firmware_version)
    if format_version < 2:
        _migrate_v1_to_v2(vehicle_path, vehicle_type)
        _restore_missing_configuration_step_files(vehicle_path, vehicle_type, firmware_version)

    data["Format version"] = VEHICLE_COMPONENTS_FORMAT_VERSION
    json_str = json_dumps(data, indent=4)
    content = json_str.rstrip("\n") + "\n"
    with open(json_path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(content)

    logging.info(_("Migration to format version %d complete"), VEHICLE_COMPONENTS_FORMAT_VERSION)
    return True
