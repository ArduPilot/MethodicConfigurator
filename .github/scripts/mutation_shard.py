"""
Select one isolated Mutmut shard while preserving the configured test suite.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

# ruff: noqa: INP001

from __future__ import annotations

import fnmatch
import json
import os
import sys
from pathlib import Path
from typing import Any

from mutmut.__main__ import cli
from mutmut.configuration import config
from mutmut.utils import logging_utils

# Mutmut's default 10 MiB/three-backup rotation can discard early completion
# records. Its handler treats maxBytes=0 as unbounded logging.
_RotatingFileHandler = logging_utils.RotatingFileHandler


class _UnrotatedFileHandler(_RotatingFileHandler):
    """Retain every worker completion in the shard's log."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:  # noqa: ANN401
        kwargs["maxBytes"] = 0
        kwargs["backupCount"] = 0
        super().__init__(*args, **kwargs)


SHARDS = {
    "backend": ("ardupilot_methodic_configurator", "backend_*.py"),
    "data-model": ("ardupilot_methodic_configurator", "data_model_*.py"),
    "frontend": ("ardupilot_methodic_configurator", "frontend_tkinter_*.py"),
    "log-analysis-backend": ("ardupilot_methodic_configurator/log_analysis", "backend_*.py"),
    "log-analysis-data-model": ("ardupilot_methodic_configurator/log_analysis", "data_model_*.py"),
    "log-analysis-frontend": ("ardupilot_methodic_configurator/log_analysis", "frontend_tkinter_*.py"),
    "plugins-backend": ("ardupilot_methodic_configurator/plugins", "backend_*.py"),
    "plugins-data-model": ("ardupilot_methodic_configurator/plugins", "data_model_*.py"),
    "plugins-frontend": ("ardupilot_methodic_configurator/plugins", "frontend_tkinter_*.py"),
}
EXCEPTIONS = {
    "data-model": ("ardupilot_methodic_configurator/battery_cell_voltages.py",),
    "plugins-data-model": ("ardupilot_methodic_configurator/plugins/imu_helpers.py",),
}


def configured_targets() -> set[str]:
    """Expand the repository's configured mutation scope into source paths."""
    settings = config()
    sources = (path.as_posix() for root in settings.source_paths for path in root.rglob("*.py"))
    return {
        source
        for source in sources
        if any(fnmatch.fnmatch(source, pattern) for pattern in settings.only_mutate)
        and not any(fnmatch.fnmatch(source, pattern) for pattern in settings.do_not_mutate)
    }


def targets_for_shard(shard: str) -> list[str]:
    """Return existing mutation targets assigned to a named shard."""
    directory, filename_pattern = SHARDS[shard]
    candidates = {path.as_posix() for path in Path(directory).glob(filename_pattern) if path.is_file()}
    candidates.update(EXCEPTIONS.get(shard, ()))
    return sorted(candidates & configured_targets())


def validate_shard_coverage() -> None:
    """Fail if the configured mutation scope contains unassigned or duplicate files."""
    assigned: list[str] = [target for shard in SHARDS for target in targets_for_shard(shard)]
    duplicates = sorted({target for target in assigned if assigned.count(target) > 1})
    missing = sorted(configured_targets() - set(assigned))
    if duplicates or missing:
        message = f"Invalid mutation shard coverage: duplicates={duplicates}, unassigned={missing}"
        raise ValueError(message)


def main() -> None:
    """Run Mutmut with only this shard's configured source files."""
    if len(sys.argv) != 2 or sys.argv[1] not in SHARDS:
        names = ", ".join(SHARDS)
        message = f"Usage: python .github/scripts/mutation_shard.py SHARD (one of: {names})"
        raise SystemExit(message)
    shard = sys.argv[1]
    validate_shard_coverage()
    settings = config()
    targets = targets_for_shard(shard)
    report_dir = Path(".cache/mutation")
    report_dir.mkdir(parents=True, exist_ok=True)
    (report_dir / "shard-targets.json").write_text(json.dumps(targets, indent=2) + "\n", encoding="utf-8")
    if not targets:
        sys.stderr.write(f"Shard {shard!r} has no configured source files; no mutation run is needed.\n")
        return
    settings.only_mutate = targets
    settings.cache_invalidation_exclude.extend(
        (".github/workflows/mutation.yml", ".github/scripts/mutation_*.py", "CONTRIBUTING.md")
    )
    if os.environ.get("MUTATION_IGNORE_GIT_CHANGES") == "1":
        # The local copies contain these workflow/documentation edits; they do
        # not change application behavior or the selected tests.
        settings.use_git_change_detection = False
        settings.on_dependency_change = "ignore"
    settings.log_to_file = True
    settings.log_file_path = str(Path(".cache/mutation/forkserver.log").resolve())
    logging_utils.RotatingFileHandler = _UnrotatedFileHandler
    # The full selected test list remains unchanged for cross-module associations.
    cli(["run", "--max-children", "2"])


if __name__ == "__main__":
    main()
