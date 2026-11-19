#!/usr/bin/env python3

"""
Export mutation measurements for CI diagnostics and future shard planning.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

from __future__ import annotations

import csv
import fnmatch
import hashlib
import json
import os
import platform
import re
import shutil
import sys
import time
import tomllib
from collections import Counter, defaultdict
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any

COMPLETION = re.compile(r"Completed (\S+): exit=(-?\d+) \((\d+(?:\.\d+)?)s\)$")


def read_json(path: Path, warnings: list[str]) -> Any:  # noqa: ANN401
    """Allow reports after failed runs with absent or interrupted state writes."""
    if not path.is_file():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (ValueError, UnicodeError) as error:
        warnings.append(f"Cannot read {path}: {error}")
        return {}


def worker_timings(output_dir: Path) -> list[dict[str, Any]]:
    """Read this run's actual attempts, including retries, from all log rotations."""
    attempts = []
    for path in sorted(output_dir.glob("forkserver.log*")):
        with path.open(encoding="utf-8", errors="replace") as stream:
            for line in stream:
                match = COMPLETION.search(line.strip())
                if match:
                    mutant, exit_code, seconds = match.groups()
                    attempts.append(
                        {
                            "mutant": mutant,
                            "exit_code": int(exit_code),
                            "worker_seconds": float(seconds),
                            "completed_at": line[:23],
                        }
                    )
    return attempts


def environment_metadata() -> dict[str, Any]:
    """Record an allowlist of comparison inputs; never dump the CI environment."""
    try:
        mutmut_version = version("mutmut")
    except PackageNotFoundError:
        mutmut_version = None
    config_path = Path("pyproject.toml")
    config_bytes = config_path.read_bytes() if config_path.is_file() else b""
    config = tomllib.loads(config_bytes.decode()).get("tool", {}).get("mutmut", {})
    shard_targets_path = Path(".cache/mutation/shard-targets.json")
    shard_targets = read_json(shard_targets_path, []) if shard_targets_path.is_file() else []
    dependency_path = Path(".cache/mutation/dependencies.txt")
    return {
        "github": {
            name: os.environ.get(name)
            for name in (
                "GITHUB_SHA",
                "GITHUB_REF",
                "GITHUB_RUN_ID",
                "GITHUB_RUN_ATTEMPT",
                "GITHUB_EVENT_NAME",
                "GITHUB_REPOSITORY",
                "RUNNER_OS",
                "RUNNER_ARCH",
                "RUNNER_ENVIRONMENT",
            )
        },
        "python": sys.version,
        "mutmut": mutmut_version,
        "platform": platform.platform(),
        "cpu_count": os.cpu_count(),
        "cpu_model": platform.processor(),
        "physical_memory_bytes": os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES") if hasattr(os, "sysconf") else None,
        "mutmut_config": config,
        "active_mutation_targets": shard_targets,
        "pyproject_sha256": hashlib.sha256(config_bytes).hexdigest(),
        "dependencies_sha256": hashlib.sha256(dependency_path.read_bytes()).hexdigest() if dependency_path.is_file() else None,
        "restored_cache_key": os.environ.get("MUTATION_CACHE_KEY"),
        "previous_artifact_id": os.environ.get("MUTATION_PREVIOUS_ARTIFACT_ID"),
        "baseline_outcome": os.environ.get("MUTATION_BASELINE_OUTCOME"),
        "mutation_outcome": os.environ.get("MUTATION_RUN_OUTCOME"),
        "mutation_shard": os.environ.get("MUTATION_SHARD"),
    }


def in_mutation_scope(path: Path, state_dir: Path, config: dict[str, Any]) -> bool:
    """Ignore stale cached metadata for deleted files or targets removed from the scope."""
    source = path.relative_to(state_dir).as_posix().removesuffix(".meta")
    roots = config.get("source_paths", [])
    if roots and (
        not Path(source).is_file() or not any(Path(source).resolve().is_relative_to(Path(root).resolve()) for root in roots)
    ):
        return False
    only_mutate = config.get("only_mutate", [])
    return (not only_mutate or any(fnmatch.fnmatch(source, pattern) for pattern in only_mutate)) and not any(
        fnmatch.fnmatch(source, pattern) for pattern in config.get("do_not_mutate", [])
    )


def module_measurements(  # pylint: disable=too-many-locals
    state_dir: Path, output_dir: Path, attempts: list[dict[str, Any]], warnings: list[str], config: dict[str, Any]
) -> tuple[list[dict[str, Any]], dict[str, float]]:
    """Separate final inventory (which includes cached results) from current-run work."""
    stats = read_json(state_dir / "mutmut-stats.json", warnings)
    tests_by_function = stats.get("tests_by_mangled_function_name", {})
    test_seconds = stats.get("duration_by_test", {})
    statuses = {}
    results_path = output_dir / "results.txt"
    if results_path.is_file():
        for line in results_path.read_text(encoding="utf-8").splitlines():
            if ": " in line:
                mutant, status = line.strip().rsplit(": ", 1)
                statuses[mutant] = status
    attempts_by_module: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for attempt in attempts:
        attempts_by_module[attempt["mutant"].rsplit(".", 1)[0]].append(attempt)

    modules = []
    for path in sorted(state_dir.rglob("*.meta")):
        if not in_mutation_scope(path, state_dir, config):
            continue
        data = read_json(path, warnings)
        inventory = data.get("exit_code_by_key", {})
        if not inventory:
            continue
        # Each .meta belongs to one source module; keep full names to avoid collisions.
        module = next(iter(inventory)).rsplit(".", 1)[0]
        counts: Counter[str] = Counter()
        estimates: Counter[str] = Counter()
        associated_tests: set[str] = set()
        for mutant, exit_code in inventory.items():
            counts[statuses.get(mutant, "not checked" if exit_code is None else f"exit {exit_code}")] += 1
            tests = tests_by_function.get(mutant.partition("__mutmut_")[0], [])
            associated_tests.update(tests)
            selected_seconds = sum(test_seconds.get(test, 0) for test in tests)
            estimates["selected_test_seconds"] += selected_seconds
            estimates["mutants_with_test_associations"] += bool(tests)
            if exit_code is None:
                estimates["pending_selected_test_seconds"] += selected_seconds
                estimates["pending_mutants"] += 1
                estimates["pending_mutants_with_test_associations"] += bool(tests)
        measured = attempts_by_module.get(module, [])
        durations = [attempt["worker_seconds"] for attempt in measured]
        modules.append(
            {
                "module": module,
                "total_mutants": len(inventory),
                "statuses": dict(counts),
                "pending_mutants": estimates["pending_mutants"],
                "pending_mutants_with_test_associations": estimates["pending_mutants_with_test_associations"],
                "associated_tests": len(associated_tests),
                "mutants_with_test_associations": estimates["mutants_with_test_associations"],
                "selected_test_seconds": estimates["selected_test_seconds"],
                "pending_selected_test_seconds": estimates["pending_selected_test_seconds"],
                "observed_attempts": len(measured),
                "observed_unique_mutants": len({attempt["mutant"] for attempt in measured}),
                "observed_worker_seconds": sum(durations),
                "mean_worker_seconds": sum(durations) / len(durations) if durations else None,
                "max_worker_seconds": max(durations, default=None),
            }
        )
    return modules, test_seconds


def build_report(state_dir: Path, output_dir: Path) -> dict[str, Any]:  # pylint: disable=too-many-locals
    """Build a versioned report even when mutation testing failed or was interrupted."""
    warnings: list[str] = []
    metadata = environment_metadata()
    attempts = worker_timings(output_dir)
    modules, test_seconds = module_measurements(state_dir, output_dir, attempts, warnings, metadata["mutmut_config"])
    empty_shard = bool(metadata["mutation_shard"]) and not metadata["active_mutation_targets"]
    run = read_json(output_dir / "run-timing.json", warnings)
    baseline = read_json(output_dir / "baseline-timing.json", warnings)
    started_at = os.environ.get("MUTATION_JOB_STARTED_AT")
    totals: Counter[str] = Counter()
    for module in modules:
        totals.update(module["statuses"])
    pending = sum(module["pending_mutants"] for module in modules)
    unassociated = pending - sum(module["pending_mutants_with_test_associations"] for module in modules)
    if unassociated:
        warnings.append(f"{unassociated} pending mutants have no recorded test association; their test cost is unknown.")
    if not attempts and not empty_shard:
        warnings.append("No measured worker completions were logged; mutation durations are unavailable, not zero.")
    if (output_dir / "forkserver.log.3").is_file():
        warnings.append("Log rotation reached its last backup; older worker measurements may have been discarded.")
    if not modules and not empty_shard:
        warnings.append("No mutation inventory is available; this run does not establish suite completion.")
    discarded = read_json(output_dir / "discarded-state.json", warnings) or []
    report = {
        "schema_version": 1,
        "environment": metadata,
        "baseline": baseline,
        "run": run,
        "seconds_before_mutation": run["started_at"] - int(started_at) if run and started_at else None,
        "seconds_until_report": time.time() - int(started_at) if started_at else None,
        "totals": {
            "mutants": sum(module["total_mutants"] for module in modules),
            "statuses": dict(totals),
            "pending_mutants": pending,
            "inventory_fully_checked": empty_shard
            or (
                bool(modules)
                and pending == 0
                and not discarded
                and not any(warning.startswith("Cannot read") for warning in warnings)
            ),
            "observed_attempts": len(attempts),
            "observed_unique_mutants": len({attempt["mutant"] for attempt in attempts}),
            "observed_worker_seconds": sum(attempt["worker_seconds"] for attempt in attempts),
            # Includes generation, association collection and clean-test overhead.
            "attempts_per_run_wall_second": len(attempts) / run["wall_seconds"]
            if run.get("wall_seconds", 0) > 0 and attempts
            else None,
        },
        "modules": modules,
        "discarded_state_files": discarded,
        "warnings": warnings,
        "timing_notes": [
            "Observed timings come only from this run's forkserver completion logs, including retries.",
            "Worker seconds include worker initialization and tests; parallel worker seconds overlap in wall time.",
            "Inventory statuses include cached results. No-test and type-check outcomes need no worker attempt.",
            (
                "Test durations and associations may be cached. Selected-test estimates exclude startup and timeouts; "
                "fail-fast can shorten execution. They are not wall-time forecasts."
            ),
            "Incomplete, crashed or unlogged workers have no measured completion duration.",
            "Selected-test estimates sum known associations only; missing associations have unknown cost.",
            "Mutmut 3.8.1 forkserver .meta durations can be zero and are deliberately not used as measurements.",
        ],
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "diagnostics.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    if (state_dir / "mutmut-stats.json").is_file():
        shutil.copyfile(state_dir / "mutmut-stats.json", output_dir / "mutmut-stats.json")
    with (output_dir / "worker-timings.jsonl").open("w", encoding="utf-8") as stream:
        for attempt in attempts:
            stream.write(json.dumps(attempt) + "\n")
    with (output_dir / "modules.csv").open("w", encoding="utf-8", newline="") as stream:
        fields = list(modules[0]) if modules else ["module", "total_mutants", "pending_mutants"]
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows({**module, "statuses": json.dumps(module["statuses"], sort_keys=True)} for module in modules)
    with (output_dir / "tests.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(["test", "seconds"])
        sorted_test_seconds = sorted(test_seconds.items(), key=lambda item: item[1], reverse=True)
        writer.writerows(sorted_test_seconds)
    return report


def render_summary(report: dict[str, Any]) -> str:
    """Show completeness and slow modules without conflating cached results with work."""
    totals = report["totals"]
    shard = report["environment"].get("mutation_shard")
    artifact_name = f"mutation-py311-{shard}" if shard else "mutation-py311"
    lines = [
        "### Mutation testing",
        "",
        (
            f"Inventory: **{totals['mutants']} mutants**, **{totals['pending_mutants']} not checked**. "
            "Statuses include cached results; survivors have no enforced score threshold."
        ),
        "",
        (
            f"This run logged **{totals['observed_attempts']} worker completions** "
            f"({totals['observed_worker_seconds']:.1f} summed worker seconds)."
        ),
        "",
    ]
    if shard and not report["environment"].get("active_mutation_targets"):
        lines.extend([f"Shard `{shard}` has no configured mutation targets; no Mutmut run was needed.", ""])
    for label, timing in (("Baseline", report["baseline"]), ("Mutation command", report["run"])):
        if timing:
            lines.extend([f"{label}: {timing['wall_seconds'] / 60:.1f} minutes; exit code {timing['exit_code']}.", ""])
    if report["run"].get("cutoff_reached") or report["run"].get("terminated_by_sigkill"):
        lines.extend(
            ["The mutation command reached its cutoff or was killed; review pending work before claiming completion.", ""]
        )
    for warning in report["warnings"]:
        lines.extend([f"**Diagnostic:** {warning}", ""])
    lines.extend(["| Status | Count |", "| --- | ---: |"])
    lines.extend(f"| {status} | {count} |" for status, count in sorted(totals["statuses"].items()))
    status_names = sorted(set(totals["statuses"]) - {"not checked"})
    lines.extend(
        [
            "",
            "Modules sorted by measured worker time (parallel durations overlap):",
            "",
            "| Module | Mutants | Not checked | Measured attempts | Worker seconds | Pending test seconds* |"
            + "".join(f" {status} |" for status in status_names),
            "| --- | ---: | ---: | ---: | ---: | ---: |" + " ---: |" * len(status_names),
        ]
    )
    for module in sorted(report["modules"], key=lambda row: row["observed_worker_seconds"], reverse=True):
        duration = f"{module['observed_worker_seconds']:.1f}" if module["observed_attempts"] else "unavailable"
        lines.append(
            f"| `{module['module'].removeprefix('ardupilot_methodic_configurator.')}` | {module['total_mutants']} | "
            f"{module['pending_mutants']} | {module['observed_attempts']} | {duration} | "
            f"{module['pending_selected_test_seconds']:.1f} |"
            + "".join(f" {module['statuses'].get(status, 0)} |" for status in status_names)
        )
    lines.extend(
        [
            "",
            "*Test-only estimates exclude worker startup and timeouts; they are not wall-time forecasts.",
            "",
            (
                f"Download `{artifact_name}` for diagnostics.json, modules.csv, tests.csv, worker-timings.jsonl, "
                "test associations, baseline JUnit results, dependencies, resource usage, and execution/crash logs."
            ),
            "",
        ]
    )
    return "\n".join(lines)


def main() -> None:
    report = build_report(Path("mutants"), Path(".cache/mutation"))
    summary = render_summary(report)
    summary_path = Path(".cache/mutation/summary.md")
    summary_path.write_text(summary, encoding="utf-8")
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with Path(os.environ["GITHUB_STEP_SUMMARY"]).open("a", encoding="utf-8") as stream:
            stream.write(summary)


if __name__ == "__main__":
    main()
