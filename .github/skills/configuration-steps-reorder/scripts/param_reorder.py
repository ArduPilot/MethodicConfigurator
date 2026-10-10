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
import tempfile
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
file_renames: dict[str, str] = {}

# Add lines like these to rename files
# file_renames["old_name"] = "new_name"

# Explicit numbering anchors; following steps use the next available number.
file_renames["15_general_configuration.param"] = "19_general_configuration.param"
file_renames["60_position_controller.param"] = "64_position_controller.param"


def reorder_param_files(steps: dict) -> dict[str, str]:
    """
    Number steps in sequence order, continuing after each explicit destination.

    Record automatic renames in file_renames so reference and migration updates
    use the same plan as the actual file moves.
    """
    renames: dict[str, str] = {}
    next_number = 2
    for old_key in steps:
        new_key = f"{next_number:02d}_{old_key.split('_', 1)[1]}"
        new_key = file_renames.get(old_key, new_key)
        new_number = int(new_key.split("_", 1)[0])
        if new_number < next_number:
            msg = f"Cannot rename {old_key} to {new_key}: the next available step number is {next_number:02d}"
            raise ValueError(msg)
        next_number = new_number + 1
        renames[new_key] = old_key
        if old_key != new_key:
            msg = f"Info: Will rename {old_key} to {new_key}"
            logging.info(msg)
    file_renames.update({old_name: new_name for new_name, old_name in renames.items() if old_name != new_name})
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


def _git_tracked_path(filepath: str, git_executable: str) -> tuple[str, str] | None:
    """Return a file's Git root and repository-relative path when it is tracked."""
    try:
        absolute_path = Path(filepath).resolve()
        repository_root = subprocess.run(  # noqa: S603
            [git_executable, "-C", str(absolute_path.parent), "rev-parse", "--show-toplevel"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        relative_path = absolute_path.relative_to(Path(repository_root)).as_posix()
        subprocess.run(  # noqa: S603
            [git_executable, "-C", repository_root, "ls-files", "--error-unmatch", "--", relative_path],
            check=True,
            capture_output=True,
            text=True,
        )
        return repository_root, relative_path
    except (FileNotFoundError, ValueError, subprocess.CalledProcessError):
        return None


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

    if os.path.lexists(new_name_path):
        msg = f"Refusing to overwrite {new_name_path} with {old_name_path}"
        raise FileExistsError(msg)

    git_executable = _git_executable()
    tracked_path = _git_tracked_path(old_name_path, git_executable) if git_executable else None
    if tracked_path:
        repository_root, relative_old_path = tracked_path
        relative_new_path = Path(new_name_path).resolve().relative_to(Path(repository_root)).as_posix()
        try:
            subprocess.run(  # noqa: S603
                [git_executable, "-C", repository_root, "mv", "-f", "--", relative_old_path, relative_new_path],
                check=True,
                capture_output=True,
                text=True,
            )
            return
        except subprocess.CalledProcessError as exc:
            stderr = exc.stderr.strip() if exc.stderr else ""
            logging.error(
                "git mv failed for tracked file %s -> %s: %s%s",
                old_name_path,
                new_name_path,
                exc,
                f"\n  stderr: {stderr}" if stderr else "",
            )
            raise
    os.rename(old_name_path, new_name_path)


def reorder_actual_files(renames: dict[str, str], param_dirs: list[str]) -> None:
    """Stage each directory's files before moving them to their final names."""
    for param_dir in param_dirs:
        moves: list[tuple[str, str]] = []
        for new_name, old_name in renames.items():
            if old_name != new_name and os.path.exists(os.path.join(param_dir, old_name)):
                moves.append((old_name, new_name))
            if old_name.endswith(".param"):
                old_xml, new_xml = old_name[:-6] + ".pdef.xml", new_name[:-6] + ".pdef.xml"
                if old_xml != new_xml and os.path.exists(os.path.join(param_dir, old_xml)):
                    moves.append((old_xml, new_xml))

        sources = {os.path.normcase(old_name) for old_name, _ in moves}
        targets = [os.path.normcase(new_name) for _, new_name in moves]
        if len(sources) != len(moves) or len(set(targets)) != len(moves):
            msg = f"Duplicate source or destination in {param_dir}"
            raise ValueError(msg)
        for _old_name, new_name in moves:
            if os.path.normcase(new_name) not in sources and os.path.lexists(os.path.join(param_dir, new_name)):
                msg = f"Refusing to overwrite {os.path.join(param_dir, new_name)}"
                raise FileExistsError(msg)

        if not moves:
            continue
        staging_dir = tempfile.mkdtemp(prefix=".param-reorder-", dir=param_dir)
        staging_name = os.path.basename(staging_dir)
        try:
            for old_name, _new_name in moves:
                rename_file(old_name, os.path.join(staging_name, old_name), param_dir)
            for old_name, new_name in moves:
                rename_file(os.path.join(staging_name, old_name), new_name, param_dir)
        except (OSError, subprocess.CalledProcessError):
            logging.exception("Rename failed; inspect %s for remaining staged files", staging_dir)
            raise
        os.rmdir(staging_dir)


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
