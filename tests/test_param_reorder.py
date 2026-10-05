#!/usr/bin/env python3

"""
Tests for the configuration step parameter reorder script.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import importlib.util
import json
import shutil
import subprocess
from pathlib import Path
from textwrap import dedent
from types import ModuleType

import pytest

SCRIPT_PATH = Path(__file__).resolve().parents[1] / ".github/skills/configuration-steps-reorder/scripts/param_reorder.py"


def _load_reorder_script() -> ModuleType:
    spec = importlib.util.spec_from_file_location("param_reorder", SCRIPT_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(name="reorder_script")
def fixture_reorder_script() -> ModuleType:
    """Load an isolated reorder script with no predefined renames."""
    script = _load_reorder_script()
    script.file_renames.clear()
    return script


def test_sparse_explicit_renames_keep_the_original_numbering(reorder_script: ModuleType) -> None:
    """
    Two explicit anchors replace the full list of fifty renames.

    GIVEN: Steps numbered 02-57 and 60-66 with explicit destinations 19 and 64.
    WHEN: The user generates the rename plan.
    THEN: Every step from 15 onward shifts by four, preserving the later gap.
    """
    numbers = [*range(2, 58), *range(60, 67)]
    steps: dict[str, dict] = {f"{number:02d}_step.param": {} for number in numbers}
    reorder_script.file_renames.update({"15_step.param": "19_step.param", "60_step.param": "64_step.param"})
    expected = {f"{number if number < 15 else number + 4:02d}_step.param": f"{number:02d}_step.param" for number in numbers}

    renames = reorder_script.reorder_param_files(steps)

    assert renames == expected
    assert reorder_script.file_renames == {
        old_name: new_name for new_name, old_name in expected.items() if new_name != old_name
    }


def test_automatic_numbering_starts_at_two_and_records_only_changes(reorder_script: ModuleType) -> None:
    """
    Automatically renumbered files are available to downstream updates.

    GIVEN: A sequence with gaps and no explicit renames.
    WHEN: The user generates the rename plan.
    THEN: Numbering starts at two and unchanged filenames are not recorded as renames.
    """
    steps: dict[str, dict] = {"02_setup.param": {}, "04_safety.param": {}, "09_finish.param": {}}

    renames = reorder_script.reorder_param_files(steps)

    assert renames == {
        "02_setup.param": "02_setup.param",
        "03_safety.param": "04_safety.param",
        "04_finish.param": "09_finish.param",
    }
    assert reorder_script.file_renames == {"04_safety.param": "03_safety.param", "09_finish.param": "04_finish.param"}


def test_explicit_filename_change_advances_the_following_number(reorder_script: ModuleType) -> None:
    """
    An explicit rename can change both the number and descriptive suffix.

    GIVEN: An explicit rename to step 19 with a new descriptive suffix.
    WHEN: The user generates the rename plan.
    THEN: The explicit name is preserved and the following step receives number 20.
    """
    reorder_script.file_renames["02_setup.param"] = "19_general_configuration.param"
    steps: dict[str, dict] = {"02_setup.param": {}, "03_safety.param": {}}

    renames = reorder_script.reorder_param_files(steps)

    assert renames == {"19_general_configuration.param": "02_setup.param", "20_safety.param": "03_safety.param"}
    assert reorder_script.file_renames["03_safety.param"] == "20_safety.param"


@pytest.mark.parametrize("destination", ["01_finish.param", "02_finish.param", "03_finish.param", "03_safety.param"])
def test_explicit_rename_cannot_reuse_an_earlier_step_number(reorder_script: ModuleType, destination: str) -> None:
    """
    Invalid anchors cannot produce duplicate or descending step numbers.

    GIVEN: Two planned steps followed by an explicit destination below the next free number.
    WHEN: The user generates the rename plan.
    THEN: The invalid anchor is rejected without recording any automatic renames.
    """
    reorder_script.file_renames["09_finish.param"] = destination
    steps: dict[str, dict] = {"02_setup.param": {}, "04_safety.param": {}, "09_finish.param": {}}

    with pytest.raises(ValueError, match="next available step number is 04"):
        reorder_script.reorder_param_files(steps)

    assert reorder_script.file_renames == {"09_finish.param": destination}


def test_generating_the_same_plan_twice_preserves_the_results(reorder_script: ModuleType) -> None:
    """
    Generated renames remain stable when planning the same sequence again.

    GIVEN: An explicit anchor and a following automatically numbered step.
    WHEN: The user generates the same plan twice.
    THEN: Both the plan and the recorded renames remain identical.
    """
    reorder_script.file_renames["02_setup.param"] = "19_setup.param"
    steps: dict[str, dict] = {"02_setup.param": {}, "03_safety.param": {}}
    first_plan = reorder_script.reorder_param_files(steps)
    first_renames = reorder_script.file_renames.copy()

    second_plan = reorder_script.reorder_param_files(steps)

    assert second_plan == first_plan
    assert reorder_script.file_renames == first_renames


def test_automatic_renames_update_files_references_and_migration_aliases(
    reorder_script: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    Automatically generated renames propagate through the complete workflow.

    GIVEN: An explicit anchor, a following parameter file, its definition and references.
    WHEN: The user applies the generated plan and records migration aliases.
    THEN: All filenames and references agree and historical aliases are preserved.
    """
    json_content = dedent(
        """\
        {
            "steps": {
                "02_setup.param": {
                    "old_filenames": []
                },
                "03_safety.param": {
                    "old_filenames": ["01_legacy_safety.param"]
                }
            }
        }
        """
    )
    steps = json.loads(json_content)["steps"]
    json_path = tmp_path / "configuration_steps_ArduCopter.json"
    json_path.write_text(json_content, encoding="utf-8")
    guide_path = tmp_path / "TUNING_GUIDE_ArduCopter.md"
    guide_path.write_text("02_setup.param\n03_safety.param\n", encoding="utf-8")
    for name, contents in {"02_setup.param": "setup", "03_safety.param": "safety", "03_safety.pdef.xml": "definition"}.items():
        (tmp_path / name).write_text(contents, encoding="utf-8")
    reorder_script.file_renames["02_setup.param"] = "19_setup.param"
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(reorder_script, "_git_executable", lambda: None)

    renames = reorder_script.reorder_param_files(steps)
    param_dirs = reorder_script.loop_relevant_files(renames)
    reorder_script.reorder_actual_files(renames, param_dirs)
    reorder_script.update_old_filenames_in_json_file(str(json_path))

    assert (tmp_path / "19_setup.param").read_text(encoding="utf-8") == "setup"
    assert (tmp_path / "20_safety.param").read_text(encoding="utf-8") == "safety"
    assert (tmp_path / "20_safety.pdef.xml").read_text(encoding="utf-8") == "definition"
    assert not (tmp_path / "02_setup.param").exists()
    assert not (tmp_path / "03_safety.param").exists()
    assert not (tmp_path / "03_safety.pdef.xml").exists()
    assert guide_path.read_text(encoding="utf-8") == "19_setup.param\n20_safety.param\n"
    updated_steps = json.loads(json_path.read_text(encoding="utf-8"))["steps"]
    assert list(updated_steps) == ["19_setup.param", "20_safety.param"]
    assert updated_steps["19_setup.param"]["old_filenames"] == ["02_setup.param"]
    assert updated_steps["20_safety.param"]["old_filenames"] == ["01_legacy_safety.param", "03_safety.param"]


def test_tracked_parameter_files_survive_a_rename_cycle(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Given tracked files with occupied target names, both payloads arrive intact."""
    git_executable = shutil.which("git")
    assert git_executable is not None
    subprocess.run([git_executable, "init", "-q", str(tmp_path)], check=True)  # noqa: S603
    for name, contents in {
        "a.param": "parameter A",
        "b.param": "parameter B",
        "a.pdef.xml": "definition A",
        "b.pdef.xml": "definition B",
    }.items():
        (tmp_path / name).write_text(contents, encoding="utf-8")
    subprocess.run(  # noqa: S603
        [git_executable, "add", "--", "a.param", "b.param", "a.pdef.xml", "b.pdef.xml"], cwd=tmp_path, check=True
    )
    monkeypatch.chdir(tmp_path)

    _load_reorder_script().reorder_actual_files({"b.param": "a.param", "a.param": "b.param"}, [str(tmp_path)])

    assert (tmp_path / "a.param").read_text(encoding="utf-8") == "parameter B"
    assert (tmp_path / "b.param").read_text(encoding="utf-8") == "parameter A"
    assert (tmp_path / "a.pdef.xml").read_text(encoding="utf-8") == "definition B"
    assert (tmp_path / "b.pdef.xml").read_text(encoding="utf-8") == "definition A"
    staged_a = subprocess.run(  # noqa: S603
        [git_executable, "show", ":a.param"], cwd=tmp_path, check=True, capture_output=True, text=True
    )
    assert staged_a.stdout == "parameter B"
    assert not list(tmp_path.glob(".param-reorder-*"))


def test_unrelated_destination_is_preserved(tmp_path: Path) -> None:
    """Given an occupied destination outside the rename set, no file is changed."""
    (tmp_path / "a.param").write_text("source", encoding="utf-8")
    (tmp_path / "b.param").write_text("existing destination", encoding="utf-8")
    script = _load_reorder_script()

    with pytest.raises(FileExistsError, match="Refusing to overwrite"):
        script.reorder_actual_files({"b.param": "a.param"}, [str(tmp_path)])

    assert (tmp_path / "a.param").read_text(encoding="utf-8") == "source"
    assert (tmp_path / "b.param").read_text(encoding="utf-8") == "existing destination"
    assert not list(tmp_path.glob(".param-reorder-*"))


def test_occupied_pdef_destination_blocks_parameter_rename(tmp_path: Path) -> None:
    """Given an occupied companion definition destination, neither file is moved."""
    (tmp_path / "01_setup.param").write_text("parameter source", encoding="utf-8")
    (tmp_path / "01_setup.pdef.xml").write_text("definition source", encoding="utf-8")
    (tmp_path / "02_setup.pdef.xml").write_text("existing definition", encoding="utf-8")

    with pytest.raises(FileExistsError, match="Refusing to overwrite"):
        _load_reorder_script().reorder_actual_files({"02_setup.param": "01_setup.param"}, [str(tmp_path)])

    assert (tmp_path / "01_setup.param").read_text(encoding="utf-8") == "parameter source"
    assert (tmp_path / "01_setup.pdef.xml").read_text(encoding="utf-8") == "definition source"
    assert (tmp_path / "02_setup.pdef.xml").read_text(encoding="utf-8") == "existing definition"
    assert not list(tmp_path.glob(".param-reorder-*"))


def test_failed_final_move_keeps_remaining_files_in_staging(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Given a failed final move, files not yet renamed remain available in staging."""
    (tmp_path / "a.param").write_text("parameter A", encoding="utf-8")
    (tmp_path / "b.param").write_text("parameter B", encoding="utf-8")
    script = _load_reorder_script()
    original_rename_file = script.rename_file
    rename_calls = 0

    def fail_on_first_final_move(old_name: str, new_name: str, param_dir: str) -> None:
        nonlocal rename_calls
        rename_calls += 1
        if rename_calls == 3:
            msg = "simulated filesystem failure"
            raise OSError(msg)
        original_rename_file(old_name, new_name, param_dir)

    monkeypatch.setattr(script, "_git_executable", lambda: None)
    monkeypatch.setattr(script, "rename_file", fail_on_first_final_move)

    with pytest.raises(OSError, match="simulated filesystem failure"):
        script.reorder_actual_files({"b.param": "a.param", "a.param": "b.param"}, [str(tmp_path)])

    staging_dirs = list(tmp_path.glob(".param-reorder-*"))
    assert len(staging_dirs) == 1
    assert (staging_dirs[0] / "a.param").read_text(encoding="utf-8") == "parameter A"
    assert (staging_dirs[0] / "b.param").read_text(encoding="utf-8") == "parameter B"
