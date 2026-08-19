#!/usr/bin/env python3

"""
Inserts and/or removes parameter files in the configuration sequence defined in the configuration_steps_ArduCopter.json.

It also replaces all occurrences of the old names with the new names
 in all *.py and *.md files in the current directory.
Finally, it renames the actual files on disk.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import json
import logging
import os
import shutil
import subprocess
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]

SEQUENCE_FILENAME = "configuration_steps_ArduCopter.json"
# Extra files (Python scripts, YAML workflows, etc.) whose content references
# parameter filenames by name and must be updated whenever files are renamed.
EXTRA_FILES_TO_UPDATE = [
    "param_pid_adjustment_update.py",
    "test_param_pid_adjustment_update.py",
    "annotate_params.py",
    "copy_magfit_pdef_to_template_dirs.py",
    "update_magfit_pdef.xml.yml",
]
file_renames = {}

# Add lines like these to rename files
# file_renames["old_name"] = "new_name"

# Explicit renames for the current files after inserting steps 14-17.
file_renames["15_general_configuration.param"] = "18_general_configuration.param"
file_renames["16_safety_setup.param"] = "19_safety_setup.param"
file_renames["17_remote_id.param"] = "20_remote_id.param"
file_renames["18_osd.param"] = "21_osd.param"
file_renames["19_motor.param"] = "22_motor.param"
file_renames["20_esc.param"] = "23_esc.param"
file_renames["21_motor_notch_filter_setup.param"] = "24_motor_notch_filter_setup.param"
file_renames["22_motor_notch_logging.param"] = "25_motor_notch_logging.param"
file_renames["23_optional_pid_adjustment.param"] = "26_optional_pid_adjustment.param"
file_renames["24_throttle_controller.param"] = "27_throttle_controller.param"
file_renames["25_motor_notch_filter_results.param"] = "28_motor_notch_filter_results.param"
file_renames["26_ekf_config.param"] = "29_ekf_config.param"
file_renames["27_pid_notch_filter_logging.param"] = "30_pid_notch_filter_logging.param"
file_renames["28_pid_notch_filter_results.param"] = "31_pid_notch_filter_results.param"
file_renames["29_quick_tune_setup.param"] = "32_quick_tune_setup.param"
file_renames["30_quick_tune_results.param"] = "33_quick_tune_results.param"
file_renames["31_inflight_magnetometer_fit_setup.param"] = "34_inflight_magnetometer_fit_setup.param"
file_renames["32_inflight_magnetometer_fit_results.param"] = "35_inflight_magnetometer_fit_results.param"
file_renames["33_evaluate_the_aircraft_tune_ff_disable.param"] = "36_evaluate_the_aircraft_tune_ff_disable.param"
file_renames["34_evaluate_the_aircraft_tune_ff_enable.param"] = "37_evaluate_the_aircraft_tune_ff_enable.param"
file_renames["35_autotune_roll_setup.param"] = "38_autotune_roll_setup.param"
file_renames["36_autotune_roll_results.param"] = "39_autotune_roll_results.param"
file_renames["37_autotune_pitch_setup.param"] = "40_autotune_pitch_setup.param"
file_renames["38_autotune_pitch_results.param"] = "41_autotune_pitch_results.param"
file_renames["39_autotune_yaw_setup.param"] = "42_autotune_yaw_setup.param"
file_renames["40_autotune_yaw_results.param"] = "43_autotune_yaw_results.param"
file_renames["41_autotune_yawd_setup.param"] = "44_autotune_yawd_setup.param"
file_renames["42_autotune_yawd_results.param"] = "45_autotune_yawd_results.param"
file_renames["43_autotune_roll_pitch_retune_setup.param"] = "46_autotune_roll_pitch_retune_setup.param"
file_renames["44_autotune_roll_pitch_retune_results.param"] = "47_autotune_roll_pitch_retune_results.param"
file_renames["45_autotune_finish.param"] = "48_autotune_finish.param"
file_renames["46_pid_d_ff.param"] = "49_pid_d_ff.param"
file_renames["47_windspeed_estimation.param"] = "50_windspeed_estimation.param"
file_renames["48_barometer_compensation.param"] = "51_barometer_compensation.param"
file_renames["49_windspeed_estimation_finish.param"] = "52_windspeed_estimation_finish.param"
file_renames["50_system_id_input_roll.param"] = "53_system_id_input_roll.param"
file_renames["51_system_id_input_pitch.param"] = "54_system_id_input_pitch.param"
file_renames["52_system_id_input_yaw.param"] = "55_system_id_input_yaw.param"
file_renames["53_system_id_mixer_roll.param"] = "56_system_id_mixer_roll.param"
file_renames["54_system_id_mixer_pitch.param"] = "57_system_id_mixer_pitch.param"
file_renames["55_system_id_mixer_yaw.param"] = "58_system_id_mixer_yaw.param"
file_renames["56_system_id_mixer_thrust.param"] = "59_system_id_mixer_thrust.param"
file_renames["57_analytical_pid_optimization.param"] = "60_analytical_pid_optimization.param"
file_renames["60_position_controller.param"] = "64_position_controller.param"
file_renames["61_guided_operation.param"] = "65_guided_operation.param"
file_renames["62_precision_land.param"] = "66_precision_land.param"
file_renames["63_optical_flow_setup.param"] = "67_optical_flow_setup.param"
file_renames["64_optical_flow_results.param"] = "68_optical_flow_results.param"
file_renames["65_use_optical_flow_instead_of_gnss.param"] = "69_use_optical_flow_instead_of_gnss.param"
file_renames["66_everyday_use.param"] = "70_everyday_use.param"


def reorder_param_files(steps: dict) -> dict[str, str]:
    """Reorder parameters and prepare renaming rules."""
    # Iterate over the param_files and rename the keys to be in two-digit prefix ascending order
    param_files = list(steps)
    renames = {}
    for i, old_key in enumerate(param_files, 2):
        new_key = f"{i:02d}_{old_key.split('_', 1)[1]}"
        # If the old filename has an explicit rename entry, use its entire new name;
        # otherwise fall back to the auto-numbered name.
        new_key = file_renames.get(old_key, new_key)
        renames[new_key] = old_key
        if old_key != new_key:
            msg = f"Info: Will rename {old_key} to {new_key}"
            logging.info(msg)
    return renames


def loop_relevant_files(renames: dict[str, str]) -> list[str]:
    param_dirs = ["."]
    # Search all *.py, *.json and *.md files in the current directory
    # and replace all occurrences of the old names with the new names
    for root, _dirs, files in os.walk("."):
        for file in files:
            if file.endswith(".param") and root not in param_dirs:
                param_dirs.append(root)
            if file == "LICENSE.md":
                continue
            if file == "vehicle_components.json":
                continue
            if file in EXTRA_FILES_TO_UPDATE or file.endswith((".md", ".json")):
                update_file_contents(renames, root, file)
    return param_dirs


def update_file_contents(renames: dict[str, str], root: str, file: str) -> None:
    with open(os.path.join(root, file), encoding="utf-8", newline="") as handle:
        file_content = handle.read()
    if "configuration_steps" in file and file.endswith(".json"):
        # Use renames (current JSON key -> new key) so that historical names already
        # stored in old_filenames are never accidentally overwritten.
        for new_name, old_name in renames.items():
            file_content = file_content.replace(old_name, new_name)
    else:
        if file.startswith("TUNING_GUIDE_") and file.endswith(".md"):
            for old_filename in file_renames:
                if old_filename not in file_content:
                    msg = f"The intermediate parameter file '{old_filename}' is not mentioned in the {file} file"
                    logging.error(msg)
        for old_name, new_name in file_renames.items():
            file_content = file_content.replace(old_name, new_name)
    with open(os.path.join(root, file), "w", encoding="utf-8", newline="") as handle:
        handle.write(file_content)


def _parse_old_filenames_from_line(line: str) -> list[str]:
    """Extract filename strings from an old_filenames JSON line."""
    bracket_start = line.index("[")
    bracket_end = line.rindex("]")
    text = line[bracket_start + 1 : bracket_end].strip()
    return [v.strip().strip('"') for v in text.split(",")] if text else []


def _format_old_filenames_line(indent: str, values: list[str], trailing_comma: bool) -> str:
    """Format an old_filenames JSON line."""
    values_str = ", ".join(f'"{v}"' for v in values)
    return f'{indent}"old_filenames": [{values_str}]{"," if trailing_comma else ""}\n'


def update_old_filenames_in_json_file(json_path: str) -> None:  # pylint: disable=too-many-locals,too-many-branches
    """
    Update old_filenames fields in the JSON file using targeted text replacement.

    Must be called after loop_relevant_files so the JSON already has the new step keys.
    Reads the file as text to avoid reformatting. Uses brace counting to correctly
    identify step block boundaries and deduplicates multiple old_filenames entries.
    """
    with open(json_path, encoding="utf-8", newline="") as f:
        lines = f.readlines()

    needs_update: dict[str, list[str]] = {}
    for old_name, new_name in file_renames.items():
        if old_name != new_name:
            needs_update.setdefault(new_name, []).append(old_name)

    new_lines: list[str] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        # Step keys have exactly 8 spaces of indentation inside "steps": { ... }
        if not (line.startswith('        "') and line.rstrip().endswith('": {')):
            new_lines.append(line)
            i += 1
            continue
        stripped = line.strip()
        step_key = stripped[1 : stripped.index('"', 1)]
        if step_key not in needs_update:
            new_lines.append(line)
            i += 1
            continue
        # Collect all lines for this step using brace counting
        step_lines: list[str] = [line]
        i += 1
        depth = 1
        while i < len(lines) and depth > 0:
            depth += lines[i].count("{") - lines[i].count("}")
            step_lines.append(lines[i])
            i += 1
        # Merge all old_filenames entries (existing + new names) into one
        of_indices = [k for k, sl in enumerate(step_lines) if sl.strip().startswith('"old_filenames"')]
        merged: list[str] = []
        for k in of_indices:
            for v in _parse_old_filenames_from_line(step_lines[k]):
                if v not in merged:
                    merged.append(v)
        for name in needs_update[step_key]:
            if name not in merged:
                merged.append(name)
        if of_indices:
            first = of_indices[0]
            first_line = step_lines[first]
            if '"old_filenames"' not in first_line:
                msg = (
                    f"BUG: expected 'old_filenames' at step_lines[{first}] but got: {first_line!r}. "
                    "The JSON indentation may have changed — update the 8-space assumption in "
                    "update_old_filenames_in_json_file()."
                )
                raise ValueError(msg)
            indent = first_line[: len(first_line) - len(first_line.lstrip())]
            step_lines[first] = _format_old_filenames_line(indent, merged, first_line.rstrip().endswith(","))
            for k in reversed(of_indices[1:]):
                del step_lines[k]
        else:
            ref = step_lines[1] if len(step_lines) > 1 else ""
            indent = ref[: len(ref) - len(ref.lstrip())] if ref.strip() else "            "
            step_lines.insert(1, _format_old_filenames_line(indent, merged, trailing_comma=True))
        new_lines.extend(step_lines)

    with open(json_path, "w", encoding="utf-8", newline="") as f:
        f.writelines(new_lines)


def _git_executable() -> str | None:
    """Return the absolute path to the git executable, or None if unavailable."""
    return shutil.which("git")


def _is_git_tracked(filepath: str, git_executable: str) -> bool:
    """Return True if *filepath* is tracked by git in the current repository."""
    try:
        subprocess.run(  # noqa: S603
            [git_executable, "ls-files", "--error-unmatch", filepath],
            check=True,
            capture_output=True,
            text=True,
        )
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


def rename_file(old_name: str, new_name: str, param_dir: str) -> None:
    """Rename a single file, using git mv when the file is tracked."""
    old_name_path = os.path.join(param_dir, old_name)
    new_name_path = os.path.join(param_dir, new_name)

    if old_name == new_name or os.path.normcase(os.path.normpath(old_name_path)) == os.path.normcase(
        os.path.normpath(new_name_path)
    ):
        return

    if not os.path.exists(old_name_path):
        logging.debug("Skipping missing file %s", old_name_path)
        return

    git_executable = _git_executable()
    if git_executable and _is_git_tracked(old_name_path, git_executable):
        try:
            subprocess.run(  # noqa: S603
                [git_executable, "mv", "-f", "--", old_name_path, new_name_path],
                check=True,
                capture_output=True,
                text=True,
            )
            return
        except subprocess.CalledProcessError as exc:
            stderr = exc.stderr.strip() if exc.stderr else ""
            logging.warning(
                "git mv failed for %s -> %s, falling back to os.rename: %s%s",
                old_name_path,
                new_name_path,
                exc,
                f"\n  stderr: {stderr}" if stderr else "",
            )
    os.rename(old_name_path, new_name_path)


def reorder_actual_files(renames: dict[str, str], param_dirs: list[str]) -> None:
    # Rename the actual files on disk based on renames re-ordering
    for param_dir in param_dirs:
        for new_name, old_name in renames.items():
            rename_file(old_name, new_name, param_dir)
            if old_name.endswith(".param"):
                rename_file(old_name[:-6] + ".pdef.xml", new_name[:-6] + ".pdef.xml", param_dir)


def main() -> None:
    logging.basicConfig(level="INFO", format="%(asctime)s - %(levelname)s - %(message)s")
    os.chdir(PROJECT_ROOT)
    json_path = os.path.join("ardupilot_methodic_configurator", SEQUENCE_FILENAME)
    with open(json_path, encoding="utf-8") as f:
        json_content = json.load(f)
    steps = json_content["steps"]
    renames = reorder_param_files(steps)
    param_dirs = loop_relevant_files(renames)
    reorder_actual_files(renames, param_dirs)
    update_old_filenames_in_json_file(json_path)


if __name__ == "__main__":
    main()
