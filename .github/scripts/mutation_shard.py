#!/usr/bin/env python3

"""
Select one isolated Mutmut shard while preserving the configured test suite.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

from __future__ import annotations

import configparser
import fnmatch
import json
import os
import sys
from pathlib import Path
from typing import Any

# pylint: disable=import-error
from mutmut.__main__ import cli  # ty: ignore[unresolved-import]
from mutmut.configuration import config  # ty: ignore[unresolved-import]
from mutmut.utils import logging_utils  # ty: ignore[unresolved-import]

# pylint: enable=import-error

# Mutmut's default 10 MiB/three-backup rotation can discard early completion
# records. Its handler treats maxBytes=0 as unbounded logging.
_RotatingFileHandler = logging_utils.RotatingFileHandler


class _UnrotatedFileHandler(_RotatingFileHandler):  # pylint: disable=too-few-public-methods
    """Retain every worker completion in the shard's log."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:  # noqa: ANN401
        kwargs["maxBytes"] = 0
        kwargs["backupCount"] = 0
        super().__init__(*args, **kwargs)


SHARDS = (
    "software-update-flight-controller-communication",
    "backend",
    "data-model",
    "frontend",
    "log-analysis-backend",
    "log-analysis-data-model",
    "log-analysis-frontend",
    "plugins-backend",
    "plugins-data-model",
    "plugins-frontend",
)
APPLICATION_TARGETS = {
    "ardupilot_methodic_configurator/data_model_software_updates.py",
    "ardupilot_methodic_configurator/frontend_tkinter_software_update.py",
    "ardupilot_methodic_configurator/backend_internet.py",
    "ardupilot_methodic_configurator/backend_firmware_upload.py",
    "ardupilot_methodic_configurator/backend_flightcontroller.py",
    "ardupilot_methodic_configurator/backend_flightcontroller_connection.py",
    "ardupilot_methodic_configurator/backend_flightcontroller_params.py",
    "ardupilot_methodic_configurator/backend_flightcontroller_commands.py",
    "ardupilot_methodic_configurator/backend_flightcontroller_files.py",
    "ardupilot_methodic_configurator/backend_flightcontroller_protocols.py",
    "ardupilot_methodic_configurator/backend_flightcontroller_reconnect.py",
    "ardupilot_methodic_configurator/backend_flightcontroller_factory_serial.py",
    "ardupilot_methodic_configurator/backend_flightcontroller_factory_mavlink.py",
    "ardupilot_methodic_configurator/backend_flightcontroller_factory_mavftp.py",
    "ardupilot_methodic_configurator/backend_flightcontroller_business_logic.py",
    "ardupilot_methodic_configurator/backend_flightcontroller_bootloader.py",
    "ardupilot_methodic_configurator/data_model_flightcontroller_info.py",
    "ardupilot_methodic_configurator/frontend_tkinter_connection_selection.py",
    "ardupilot_methodic_configurator/frontend_tkinter_flightcontroller_info.py",
    "ardupilot_methodic_configurator/frontend_tkinter_flightcontroller_connection_progress.py",
    "ardupilot_methodic_configurator/frontend_tkinter_file_browser.py",
    "ardupilot_methodic_configurator/frontend_tkinter_file_browser_operations.py",
    "ardupilot_methodic_configurator/frontend_tkinter_file_browser_tasks.py",
    "ardupilot_methodic_configurator/frontend_tkinter_firmware_upload.py",
}
APPLICATION_TESTS = [
    "tests/unit_data_model_software_updates.py",
    "tests/unit_frontend_tkinter_software_update.py",
    "tests/bdd_software_update.py",
    "tests/acceptance_software_update.py",
    "tests/unit_backend_internet.py",
    "tests/unit_backend_internet_checksum_parsing.py",
    "tests/unit_backend_internet_download_resume.py",
    "tests/test_backend_firmware_upload.py",
    "tests/test_data_model_firmware_catalog.py",
    "tests/test_frontend_tkinter_firmware_upload.py",
    "tests/test_backend_flightcontroller.py",
    "tests/test_backend_flightcontroller_connection.py",
    "tests/test_backend_flightcontroller_params.py",
    "tests/unit_backend_flightcontroller_params.py",
    "tests/test_backend_flightcontroller_commands.py",
    "tests/unit_backend_flightcontroller_commands.py",
    "tests/test_backend_flightcontroller_files.py",
    "tests/test_backend_flightcontroller_file_browser.py",
    "tests/test_backend_flightcontroller_factory_serial.py",
    "tests/test_backend_flightcontroller_factory_mavlink.py",
    "tests/test_backend_flightcontroller_factory_mavftp.py",
    "tests/test_backend_flightcontroller_business_logic.py",
    "tests/test_backend_flightcontroller_bootloader.py",
    "tests/test_bootloader_identity.py",
    "tests/test_backend_flightcontroller_reconnect.py",
    "tests/test_data_model_flightcontroller_info.py",
    "tests/test_frontend_tkinter_connection_selection.py",
    "tests/test_frontend_tkinter_flightcontroller_info.py",
    "tests/test_frontend_tkinter_flightcontroller_connection_progress.py",
    "tests/bdd_frontend_tkinter_file_browser.py",
    "tests/test_frontend_tkinter_file_browser.py",
    "tests/test_frontend_tkinter_file_browser_operations.py",
    "tests/test_frontend_tkinter_file_browser_tasks.py",
]
PACKAGE_ROOT = "ardupilot_methodic_configurator"
FAMILY_DIRECTORIES = {
    "": ("backend", "data-model", "frontend"),
    "log_analysis": ("log-analysis-backend", "log-analysis-data-model", "log-analysis-frontend"),
    "plugins": ("plugins-backend", "plugins-data-model", "plugins-frontend"),
}
EXCEPTIONS = {
    "data-model": ("ardupilot_methodic_configurator/battery_cell_voltages.py",),
    "plugins-data-model": ("ardupilot_methodic_configurator/plugins/imu_helpers.py",),
}
EXCEPTION_SHARDS = {target: shard for shard, targets in EXCEPTIONS.items() for target in targets}


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


def all_python_files() -> set[str]:
    """Return every Python file under the application package."""
    return {path.as_posix() for path in Path(PACKAGE_ROOT).rglob("*.py") if path.is_file()}


def coverage_omit_patterns() -> set[str]:
    """Read the report exclusions Mutmut must mirror."""
    coverage = configparser.ConfigParser()
    coverage.read(".coveragerc", encoding="utf-8")
    return {pattern.strip() for pattern in coverage.get("report", "omit").split(",") if pattern.strip()}


def shard_for_target(target: str) -> str:
    """Map categorized modules to their family and uncategorized modules to its backend shard."""
    if target in APPLICATION_TARGETS:
        return "software-update-flight-controller-communication"
    path = Path(target)
    relative = path.relative_to(PACKAGE_ROOT)
    directory = relative.parts[0] if len(relative.parts) > 1 and relative.parts[0] in FAMILY_DIRECTORIES else ""
    backend, data_model, frontend = FAMILY_DIRECTORIES[directory]
    filename = path.name
    if filename.startswith("data_model_"):
        return data_model
    if filename.startswith("frontend_tkinter_"):
        return frontend
    # Backend-prefixed files and modules without a family prefix (package
    # initializers, helpers, entry points, utilities) share the family backend shard.
    return backend


def targets_for_shard(shard: str) -> list[str]:
    """Return every configured source target assigned to a named shard."""
    return sorted(target for target in configured_targets() if EXCEPTION_SHARDS.get(target, shard_for_target(target)) == shard)


def validate_shard_coverage() -> None:
    """Fail unless non-omitted package Python files are configured and assigned once."""
    discovered = all_python_files()
    coverage_omits = coverage_omit_patterns()
    settings = config()
    if set(settings.do_not_mutate) != coverage_omits:
        missing_from_mutmut = sorted(coverage_omits - set(settings.do_not_mutate))
        extra_in_mutmut = sorted(set(settings.do_not_mutate) - coverage_omits)
        message = f"Mutmut exclusions must match .coveragerc: missing={missing_from_mutmut}, extra={extra_in_mutmut}"
        raise ValueError(message)
    expected = {target for target in discovered if not any(fnmatch.fnmatch(target, pattern) for pattern in coverage_omits)}
    configured = configured_targets()
    if configured != expected:
        missing_from_config = sorted(expected - configured)
        outside_package = sorted(configured - expected)
        message = (
            "Mutmut scope must match coverage-included package Python files: "
            f"unconfigured={missing_from_config}, unexpected={outside_package}"
        )
        raise ValueError(message)
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
    if shard == "software-update-flight-controller-communication":
        settings.pytest_add_cli_args_test_selection = APPLICATION_TESTS
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
    max_children = os.environ.get("MUTATION_MAX_CHILDREN", "14")
    cli(["run", "--max-children", max_children])


if __name__ == "__main__":
    main()
