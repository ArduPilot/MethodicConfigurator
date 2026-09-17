#!/usr/bin/env python3

"""
Tests for the configuration step parameter reorder script.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import importlib.util
import shutil
import subprocess
from pathlib import Path
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
