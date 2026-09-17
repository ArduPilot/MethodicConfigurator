#!/usr/bin/env python3

"""
Test migration of the original Holybro X500 template.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

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


def test_existing_holybro_x500_migrates_to_x500_mig_parameter_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Migrate the old template with v2 step files and compare every .param file."""
    templates_dir = Path(__file__).parents[1] / "ardupilot_methodic_configurator" / "vehicle_templates" / "ArduCopter"
    old_template = templates_dir / "Holybro_X500"
    migrated_template = templates_dir / "Holybro_X500_mig"
    project_dir = tmp_path / "Holybro_X500"
    empty_v2_template = tmp_path / "empty_v2"
    project_dir.mkdir()
    empty_v2_template.mkdir()

    for source in old_template.iterdir():
        if source.is_file() and (source.suffix == ".param" or source.name == "vehicle_components.json"):
            shutil.copy2(source, project_dir / source.name)

    # This represents replacing the normal package step definition with the
    # X500_mig v2 definition for this migration.
    shutil.copy2(
        migrated_template / "configuration_steps_ArduCopter.json",
        project_dir / "configuration_steps_ArduCopter.json",
    )

    # Model the requested v2 empty template: it contains every target step file,
    # while leaving their contents empty so migrated project values remain authoritative.
    for target_file in migrated_template.glob("*.param"):
        (empty_v2_template / target_file.name).write_text("", encoding="utf-8")

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
        filename
        for filename in actual.keys() | expected.keys()
        if actual.get(filename) != expected.get(filename)
    )

    assert not mismatched_files, (
        "Migrated Holybro_X500 .param files differ from Holybro_X500_mig: "
        + ", ".join(mismatched_files)
    )
