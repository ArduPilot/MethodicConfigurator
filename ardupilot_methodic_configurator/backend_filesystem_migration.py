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

from ardupilot_methodic_configurator import _

VEHICLE_COMPONENTS_FORMAT_VERSION = 1
_VEHICLE_COMPONENTS_JSON_FILENAME = "vehicle_components.json"

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
    """
    stripped = line.strip()
    if not stripped or stripped.startswith("#"):
        return ""
    return stripped.split(",", 1)[0].strip()


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

    vehicle_type: str = data.get("Components", {}).get("Flight Controller", {}).get("Firmware", {}).get("Type", "")

    logging.info(
        _("Migrating %s vehicle project in '%s' from format version %d to %d"),
        vehicle_type or _("unknown"),
        vehicle_dir,
        format_version,
        VEHICLE_COMPONENTS_FORMAT_VERSION,
    )

    if format_version < 1:
        _migrate_v0_to_v1(vehicle_path, vehicle_type)

    data["Format version"] = VEHICLE_COMPONENTS_FORMAT_VERSION
    json_str = json_dumps(data, indent=4)
    content = json_str.rstrip("\n") + "\n"
    with open(json_path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(content)

    logging.info(_("Migration to format version %d complete"), VEHICLE_COMPONENTS_FORMAT_VERSION)
    return True
