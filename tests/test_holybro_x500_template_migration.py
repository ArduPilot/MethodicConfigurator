#!/usr/bin/env python3

"""
Test migration of the original Holybro X500 template.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import difflib
import json
import shutil
from pathlib import Path

import pytest

import ardupilot_methodic_configurator.backend_filesystem_migration as migration_module
from ardupilot_methodic_configurator.backend_filesystem import LocalFilesystem
from ardupilot_methodic_configurator.backend_filesystem_configuration_steps import ConfigurationSteps


def _param_file_contents(directory: Path) -> dict[str, bytes]:
    """Return all parameter files keyed by basename."""
    return {path.name: path.read_bytes() for path in directory.glob("*.param")}


def test_existing_holybro_x500_migrates_to_x500_mig_parameter_files(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Migrate the old template with v2 step files and compare every .param file."""
    templates_dir = Path(__file__).parents[1] / "ardupilot_methodic_configurator" / "vehicle_templates" / "ArduCopter"
    old_template = templates_dir / "Holybro_X500"
    migrated_template = templates_dir / "Holybro_X500_mig"
    empty_v2_template = templates_dir / "empty_4.6.x_mig"
    project_dir = tmp_path / "Holybro_X500"
    project_dir.mkdir()

    for source in old_template.iterdir():
        if source.is_file() and (source.suffix == ".param" or source.name == "vehicle_components.json"):
            shutil.copy2(source, project_dir / source.name)

    # Older projects stored the startup mode with the mandatory hardware values.
    mandatory_hardware = project_dir / "14_mp_setup_mandatory_hardware.param"
    mandatory_hardware.write_text(mandatory_hardware.read_text(encoding="utf-8") + "INITIAL_MODE,0\n", encoding="utf-8")

    # This represents replacing the normal package step definition with the
    # X500_mig v2 definition for this migration.
    shutil.copy2(
        migrated_template / "configuration_steps_ArduCopter.json",
        project_dir / "configuration_steps_ArduCopter.json",
    )

    monkeypatch.setattr(migration_module, "VEHICLE_COMPONENTS_FORMAT_VERSION", 2)
    monkeypatch.setattr(
        migration_module.VehicleProjectCreator,
        "template_dir_for_bin_import",
        staticmethod(lambda _vehicle_type, _major, _minor: str(empty_v2_template)),
    )

    assert migration_module.migrate_vehicle_project_if_needed(str(project_dir)) is True
    assert json.loads((project_dir / "vehicle_components.json").read_text(encoding="utf-8"))["Format version"] == 2

    # Project opening applies the filename aliases after the format migration.
    filesystem = LocalFilesystem(
        str(project_dir),
        "ArduCopter",
        "4.6.3",
        allow_editing_template_files=False,
        save_component_to_system_templates=False,
        load_project=False,
    )
    ConfigurationSteps.re_init(filesystem, str(project_dir), "ArduCopter")
    filesystem.rename_parameter_files()

    actual = _param_file_contents(project_dir)
    expected = _param_file_contents(migrated_template)
    mismatched_files = sorted(
        filename for filename in actual.keys() | expected.keys() if actual.get(filename) != expected.get(filename)
    )
    file_diffs: list[str] = []
    for filename in mismatched_files:
        expected_lines = (expected.get(filename) or b"").decode("utf-8", errors="backslashreplace").splitlines(keepends=True)
        actual_lines = (actual.get(filename) or b"").decode("utf-8", errors="backslashreplace").splitlines(keepends=True)
        full_file_context = max(len(expected_lines), len(actual_lines))
        file_diffs.extend(
            difflib.unified_diff(
                expected_lines,
                actual_lines,
                fromfile=f"Holybro_X500_mig/{filename}",
                tofile=f"migrated_project/{filename}",
                n=full_file_context,
            )
        )

    assert not mismatched_files, "Migrated Holybro_X500 .param files differ:\n" + "".join(file_diffs)
