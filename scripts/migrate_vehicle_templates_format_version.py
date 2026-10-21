#!/usr/bin/env python3

"""
Migrate packaged vehicle templates to the current format version.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

# ruff: noqa: S101, T201

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from shutil import copytree, ignore_patterns, rmtree
from warnings import warn

import pytest

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

# Direct execution needs the repository on sys.path before importing the application.
# pylint: disable=wrong-import-position
import ardupilot_methodic_configurator.backend_filesystem as filesystem_module  # noqa: E402
from ardupilot_methodic_configurator.backend_filesystem import LocalFilesystem  # noqa: E402
from ardupilot_methodic_configurator.backend_filesystem_migration import (  # noqa: E402
    VEHICLE_COMPONENTS_FORMAT_VERSION,
)
from ardupilot_methodic_configurator.data_model_par_dict import ParDict, is_within_tolerance  # noqa: E402
from ardupilot_methodic_configurator.data_model_vehicle_project_opener import VehicleProjectOpener  # noqa: E402

# pylint: enable=wrong-import-position

_SOURCE_VEHICLE_TEMPLATES = _PROJECT_ROOT / "ardupilot_methodic_configurator" / "vehicle_templates"
_VEHICLE_TEMPLATE_CASES = sorted(
    (
        path.parent.relative_to(_SOURCE_VEHICLE_TEMPLATES),
        path.parent,
    )
    for path in _SOURCE_VEHICLE_TEMPLATES.rglob("vehicle_components.json")
    if list(path.parent.glob("*.param"))
)


class _MigrationModePlugin:  # pylint: disable=too-few-public-methods
    """Carry the CLI mode into the module pytest imports for collection."""

    def __init__(self, dry_run: bool) -> None:
        self.dry_run = dry_run

    def pytest_configure(self, config: pytest.Config) -> None:
        """Expose the chosen mode to fixtures in the collected test module."""
        config.option.template_migration_dry_run = self.dry_run


@pytest.fixture(scope="module", name="migration_dry_run")
def _migration_dry_run(request: pytest.FixtureRequest) -> bool:
    """Default to copies when the test module is invoked directly through pytest."""
    return getattr(request.config.option, "template_migration_dry_run", True)


@pytest.fixture(scope="module", name="vehicle_templates_root")
def _vehicle_templates_root(migration_dry_run: bool) -> Path:
    """Return a fresh inspection directory for dry runs, or the source tree for migrations."""
    if not migration_dry_run:
        return _SOURCE_VEHICLE_TEMPLATES
    inspection_root = _PROJECT_ROOT / "migration_test"
    if inspection_root.exists():
        rmtree(inspection_root)
    inspection_root.mkdir()
    return inspection_root


class TestVehicleTemplateMigrationRoundTrip:  # pylint: disable=too-few-public-methods
    """Exercise format migration against every packaged vehicle template."""

    @staticmethod
    def _compound_param_files(vehicle_dir: Path) -> ParDict:
        """Compound the same numbered project files, in the same order, as LocalFilesystem."""
        local_filesystem = LocalFilesystem(
            str(vehicle_dir),
            "",
            "",
            allow_editing_template_files=True,
            save_component_to_system_templates=False,
            load_project=False,
        )
        local_filesystem.file_parameters = local_filesystem.read_params_from_files()
        return local_filesystem.compound_params()[0]

    @staticmethod
    def _format_parameter_differences(before: ParDict, after: ParDict) -> list[str]:
        """Describe each changed, added, or removed parameter with its v1 and v2 state."""
        differences: list[str] = []
        for name in sorted(before.keys() | after.keys()):
            old_parameter = before.get(name)
            new_parameter = after.get(name)
            if old_parameter is not None and new_parameter is not None:
                value_changed = not is_within_tolerance(old_parameter.value, new_parameter.value)
                comment_changed = (old_parameter.comment or "") != (new_parameter.comment or "")
                if not value_changed and not comment_changed:
                    continue
                changes = []
                if value_changed:
                    changes.append(f"value: {old_parameter.value!r} -> {new_parameter.value!r}")
                if comment_changed:
                    changes.append(f"comment: {old_parameter.comment!r} -> {new_parameter.comment!r}")
                differences.append(f"  {name}: " + "; ".join(changes))
            elif old_parameter is not None:
                differences.append(f"  {name}: v1=({old_parameter.value!r}, {old_parameter.comment!r}) -> v2=<missing>")
            else:
                assert new_parameter is not None
                differences.append(f"  {name}: v1=<missing> -> v2=({new_parameter.value!r}, {new_parameter.comment!r})")
        return differences

    @pytest.mark.parametrize(
        ("vehicle_relative_path", "source_vehicle_dir"),
        _VEHICLE_TEMPLATE_CASES,
        ids=[relative_path.as_posix() for relative_path, _ in _VEHICLE_TEMPLATE_CASES],
    )
    def test_user_keeps_all_parameter_values_when_vehicle_templates_migrate_to_v2(  # pylint: disable=too-many-locals
        self,
        monkeypatch: pytest.MonkeyPatch,
        migration_dry_run: bool,
        vehicle_templates_root: Path,
        vehicle_relative_path: Path,
        source_vehicle_dir: Path,
    ) -> None:
        """
        Migrating every packaged vehicle template preserves its complete parameter set.

        GIVEN: A vehicle template with its parameter files compounded
        WHEN: Each vehicle project is opened through the normal project opener
        THEN: Every original parameter value remains available, including values moved to new steps
        """
        vehicle_id = vehicle_relative_path.as_posix()
        vehicle_dir = vehicle_templates_root / vehicle_relative_path
        if migration_dry_run:
            vehicle_dir.parent.mkdir(parents=True, exist_ok=True)
            copytree(source_vehicle_dir, vehicle_dir, ignore=ignore_patterns("*.bin", "*.zip"))

        # Parameter metadata is unrelated to template migration and would otherwise require firmware XML.
        monkeypatch.setattr(filesystem_module, "parse_parameter_metadata", lambda *_args, **_kwargs: {})

        complete_v1 = self._compound_param_files(vehicle_dir)
        assert complete_v1, f"[{vehicle_id}] No parameters were found before migration"
        if migration_dry_run:
            complete_v1.export_to_param(str(vehicle_dir / "complete_v1.param"))
        components_path = vehicle_dir / "vehicle_components.json"
        original_format_version = json.loads(components_path.read_text(encoding="utf-8-sig")).get("Format version", 0)

        vehicle_type = vehicle_relative_path.parts[0]
        local_filesystem = LocalFilesystem(
            str(vehicle_dir),
            vehicle_type,
            "",
            allow_editing_template_files=True,
            save_component_to_system_templates=False,
            load_project=False,
        )
        VehicleProjectOpener(local_filesystem).open_last_vehicle_directory(str(vehicle_dir))

        components = json.loads(components_path.read_text(encoding="utf-8-sig"))
        assert components.get("Format version") == VEHICLE_COMPONENTS_FORMAT_VERSION, (
            f"[{vehicle_id}] Project format was not migrated to {VEHICLE_COMPONENTS_FORMAT_VERSION}"
        )

        complete_v2 = self._compound_param_files(vehicle_dir)
        assert complete_v2, f"[{vehicle_id}] No parameters were found after migration"
        if migration_dry_run:
            complete_v2.export_to_param(str(vehicle_dir / "complete_v2.param"))

        vehicle_differences = self._format_parameter_differences(complete_v1, complete_v2)
        if original_format_version >= VEHICLE_COMPONENTS_FORMAT_VERSION:
            # Build the detailed diff per vehicle so pytest reports the exact changed parameters.
            if vehicle_differences:
                pytest.fail(
                    f"[{vehicle_id}] complete_v1.param vs complete_v2.param:\n" + "\n".join(vehicle_differences),
                    pytrace=False,
                )
        else:
            # New steps can add parameters, but they must not change the effective
            # value after the application's numbered-file compounding rules run.
            if vehicle_differences:
                warn(
                    f"[{vehicle_id}] complete_v1.param vs complete_v2.param:\n" + "\n".join(vehicle_differences),
                    UserWarning,
                    stacklevel=2,
                )
            differences = []
            for name, parameter in complete_v1.items():
                migrated_parameter = complete_v2.get(name)
                if migrated_parameter is None or not is_within_tolerance(parameter.value, migrated_parameter.value):
                    migrated_value = migrated_parameter.value if migrated_parameter else "<missing>"
                    differences.append(f"  {name}: {parameter.value!r} -> {migrated_value!r}")
            if differences:
                pytest.fail(f"[{vehicle_id}] effective parameter values changed:\n" + "\n".join(differences), pytrace=False)


def _confirm_in_place_migration() -> bool:
    """Ask before modifying and staging packaged vehicle templates."""
    print(
        "This will update the vehicle templates in place and git stage the results.\n"
        "Run this script with --dry-run first and inspect its output before continuing."
    )
    try:
        return input("Continue with the in-place migration? [y/N] ").strip().lower() in {"y", "yes"}
    except EOFError:
        return False


def _snapshot_migratable_files() -> dict[Path, bytes]:
    """Capture files that template migration can change, to stage only this run's results."""
    extensions = {".json", ".param", ".xml"}
    return {
        path.relative_to(_PROJECT_ROOT): path.read_bytes()
        for path in _SOURCE_VEHICLE_TEMPLATES.rglob("*")
        if path.is_file() and path.suffix in extensions
    }


def _stage_migration_changes(before: dict[Path, bytes]) -> None:
    """Stage only migratable files whose contents changed during this run."""
    after = _snapshot_migratable_files()
    changed_paths = sorted(path for path in before.keys() | after.keys() if before.get(path) != after.get(path))
    if not changed_paths:
        print("Vehicle templates already use the current format; there are no changes to stage.")
        return
    tracked = subprocess.run(
        ["git", "ls-files", "-z", "--cached", "--", "ardupilot_methodic_configurator/vehicle_templates"],  # noqa: S607
        cwd=_PROJECT_ROOT,
        check=True,
        capture_output=True,
    )
    tracked_paths = {Path(os.fsdecode(path)) for path in tracked.stdout.split(b"\0") if path}
    # Git renames can already have staged and removed their old names from the index.
    # Passing those now-missing paths to `git add` makes the whole command fail.
    paths_to_add = [path for path in changed_paths if (_PROJECT_ROOT / path).exists() or path in tracked_paths]
    if paths_to_add:
        subprocess.run(  # noqa: S603
            ["git", "add", "-A", "--", *(str(path) for path in paths_to_add)],  # noqa: S607
            cwd=_PROJECT_ROOT,
            check=True,
        )
    print(f"Git staged {len(changed_paths)} changed vehicle template file(s).")


def main() -> int:
    """Run the dry migration check or confirm, migrate, and stage template changes."""
    parser = argparse.ArgumentParser(description="Migrate packaged vehicle templates to the current format version.")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="migrate copies under migration_test/ and leave packaged templates unchanged",
    )
    args, pytest_args = parser.parse_known_args()

    if not args.dry_run and not _confirm_in_place_migration():
        print("Migration cancelled.")
        return 1

    before = {} if args.dry_run else _snapshot_migratable_files()
    result = int(pytest.main(["-vv", __file__, *pytest_args], plugins=[_MigrationModePlugin(args.dry_run)]))
    if result == 0 and not args.dry_run:
        _stage_migration_changes(before)
    return result


if __name__ == "__main__":
    raise SystemExit(main())
