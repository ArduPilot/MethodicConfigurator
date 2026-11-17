#!/usr/bin/env python3
"""
Check mutation CI reports remain useful after cached, partial, and failed runs.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import csv
import json
import runpy
from pathlib import Path
from typing import Any

import pytest


@pytest.fixture(name="reporter")
def fixture_reporter() -> dict[str, Any]:
    return runpy.run_path(str(Path(__file__).resolve().parents[1] / ".github/scripts/mutation_report.py"))


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


def test_partial_run_separates_measured_work_from_cached_verdicts_and_estimates(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, reporter: dict[str, Any]
) -> None:
    """A cutoff report preserves pending work and measurements without counting cached timings."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("MUTATION_JOB_STARTED_AT", "100")
    monkeypatch.setenv("MUTATION_CACHE_KEY", "previous-run")
    state_dir, output_dir = tmp_path / "mutants", tmp_path / "reports"
    output_dir.mkdir()
    measured = "app.model.x_compute__mutmut_1"
    pending = "app.model.x_compute__mutmut_2"
    cached = "app.cached.x_read__mutmut_1"
    write_json(
        state_dir / "app/model.py.meta",
        {
            "exit_code_by_key": {measured: 1, pending: None},
            "durations_by_key": {measured: 0, pending: 99},
        },
    )
    write_json(
        state_dir / "app/cached.py.meta",
        {
            "exit_code_by_key": {cached: 0},
            "durations_by_key": {cached: 999},
        },
    )
    write_json(
        state_dir / "mutmut-stats.json",
        {
            "tests_by_mangled_function_name": {"app.model.x_compute": ["test_fast", "test_slow"]},
            "duration_by_test": {"test_fast": 0.5, "test_slow": 2.5},
        },
    )
    write_json(
        output_dir / "run-timing.json",
        {
            "started_at": 160,
            "wall_seconds": 10,
            "exit_code": 124,
            "cutoff_reached": True,
        },
    )
    write_json(output_dir / "baseline-timing.json", {"wall_seconds": 20, "exit_code": 0})
    (output_dir / "forkserver.log.1").write_text(
        f"2026-11-17 12:00:00.000 [123] mutmut DEBUG: Completed {measured}: exit=-11 (1.250s)\n",
        encoding="utf-8",
    )
    (output_dir / "forkserver.log").write_text(
        "worker started\n"
        f"2026-11-17 12:00:01.000 [123] mutmut DEBUG: Completed {measured}: exit=1 (2.750s)\n"
        f"Completed {pending}: exit=1 (interrupted",
        encoding="utf-8",
    )
    (output_dir / "results.txt").write_text(
        f"{measured}: killed\n{pending}: not checked\n{cached}: survived\n", encoding="utf-8"
    )

    report = reporter["build_report"](state_dir, output_dir)

    assert report["totals"]["mutants"] == 3
    assert report["totals"]["statuses"] == {"killed": 1, "not checked": 1, "survived": 1}
    assert report["totals"]["pending_mutants"] == 1
    assert not report["totals"]["inventory_fully_checked"]
    assert report["totals"]["observed_attempts"] == 2
    assert report["totals"]["observed_unique_mutants"] == 1
    assert report["totals"]["observed_worker_seconds"] == 4
    assert report["totals"]["attempts_per_run_wall_second"] == 0.2
    assert report["seconds_before_mutation"] == 60
    assert report["environment"]["restored_cache_key"] == "previous-run"
    modules = {module["module"]: module for module in report["modules"]}
    assert modules["app.model"]["pending_selected_test_seconds"] == 3
    assert modules["app.model"]["selected_test_seconds"] == 6
    assert modules["app.model"]["mean_worker_seconds"] == 2
    assert modules["app.cached"]["mean_worker_seconds"] is None
    assert modules["app.cached"]["observed_attempts"] == 0
    assert json.loads((output_dir / "diagnostics.json").read_text()) == report
    assert (output_dir / "mutmut-stats.json").read_bytes() == (state_dir / "mutmut-stats.json").read_bytes()
    attempts = [json.loads(line) for line in (output_dir / "worker-timings.jsonl").read_text().splitlines()]
    assert {attempt["exit_code"] for attempt in attempts} == {-11, 1}
    with (output_dir / "modules.csv").open(newline="") as stream:
        assert len(list(csv.DictReader(stream))) == 2
    with (output_dir / "tests.csv").open(newline="") as stream:
        assert list(csv.reader(stream))[1] == ["test_slow", "2.5"]
    summary = reporter["render_summary"](report)
    assert "cutoff or was killed" in summary
    assert "unavailable" in summary
    assert "1 not checked" in summary


def test_failed_run_still_exports_diagnostics_without_claiming_completion(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, reporter: dict[str, Any]
) -> None:
    """Missing logs and damaged state produce a usable artifact with explicit limitations."""
    monkeypatch.chdir(tmp_path)
    state_dir, output_dir = tmp_path / "mutants", tmp_path / "reports"
    state_dir.mkdir()
    (state_dir / "broken.py.meta").write_text('{"exit_code_by_key":', encoding="utf-8")
    write_json(state_dir / "mutmut-stats.json", {})
    write_json(output_dir / "baseline-timing.json", {"wall_seconds": 1.5, "exit_code": 1})
    write_json(output_dir / "discarded-state.json", ["mutants/interrupted.py.meta"])
    (output_dir / "forkserver.log.3").touch()

    report = reporter["build_report"](state_dir, output_dir)

    assert not report["totals"]["inventory_fully_checked"]
    assert report["totals"]["attempts_per_run_wall_second"] is None
    assert report["modules"] == []
    assert len(report["warnings"]) == 4
    assert report["discarded_state_files"] == ["mutants/interrupted.py.meta"]
    assert report["baseline"]["exit_code"] == 1
    assert "No mutation inventory" in reporter["render_summary"](report)
    assert (output_dir / "modules.csv").is_file()
    assert (output_dir / "tests.csv").is_file()


def test_report_excludes_cached_targets_removed_from_the_current_scope(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, reporter: dict[str, Any]
) -> None:
    """Deleted modules and changed mutation filters must not inflate the pending backlog."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "pyproject.toml").write_text(
        '[tool.mutmut]\nsource_paths = ["app/"]\nonly_mutate = ["app/*.py"]\ndo_not_mutate = ["app/excluded.py"]\n',
        encoding="utf-8",
    )
    state_dir, output_dir = tmp_path / "mutants", tmp_path / "reports"
    for module in ("app/current", "app/deleted", "app/excluded", "other/module"):
        write_json(
            state_dir / f"{module}.py.meta",
            {
                "exit_code_by_key": {module.replace("/", ".") + ".x_run__mutmut_1": None},
            },
        )
        if module != "app/deleted":
            source = tmp_path / f"{module}.py"
            source.parent.mkdir(exist_ok=True)
            source.touch()

    report = reporter["build_report"](state_dir, output_dir)

    assert report["totals"]["mutants"] == 1
    assert report["totals"]["pending_mutants"] == 1
    assert report["modules"][0]["module"] == "app.current"
    assert report["modules"][0]["pending_mutants_with_test_associations"] == 0
    assert any("test cost is unknown" in warning for warning in report["warnings"])
