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
    """Return parameter files keyed by basename, normalizing only CRLF checkout line endings."""
    return {path.name: path.read_bytes().replace(b"\r\n", b"\n") for path in directory.glob("*.param")}


def test_parameter_file_comparison_ignores_checkout_line_endings(tmp_path: Path) -> None:
    """
    Equivalent parameter files compare equally across checkout platforms.

    GIVEN: LF and CRLF copies with identical values, comments, and spacing
    WHEN: Their contents are collected for migration comparison
    THEN: Only the line endings are normalized, without changing either file
    """
    lf_directory = tmp_path / "lf"
    crlf_directory = tmp_path / "crlf"
    lf_directory.mkdir()
    crlf_directory.mkdir()
    contents = b"PARAM_A,1  # retained comment\nPARAM_B,2\n"
    lf_file = lf_directory / "01_setup.param"
    crlf_file = crlf_directory / "01_setup.param"
    lf_file.write_bytes(contents)
    crlf_file.write_bytes(contents.replace(b"\n", b"\r\n"))

    assert _param_file_contents(lf_directory) == _param_file_contents(crlf_directory)
    assert lf_file.read_bytes() == contents
    assert crlf_file.read_bytes() == contents.replace(b"\n", b"\r\n")


@pytest.mark.parametrize("changed_contents", [b"PARAM_A,2  # comment\n", b"PARAM_A,1  # changed\n", b"PARAM_A,1 # comment\n"])
def test_parameter_file_comparison_still_detects_content_changes(tmp_path: Path, changed_contents: bytes) -> None:
    """
    Normalizing line endings must not hide migration regressions.

    GIVEN: Parameter files differing in a value, comment, or spacing
    WHEN: Their contents are collected for migration comparison
    THEN: The content difference remains visible
    """
    expected_directory = tmp_path / "expected"
    actual_directory = tmp_path / "actual"
    expected_directory.mkdir()
    actual_directory.mkdir()
    (expected_directory / "01_setup.param").write_bytes(b"PARAM_A,1  # comment\r\n")
    (actual_directory / "01_setup.param").write_bytes(changed_contents)

    assert _param_file_contents(expected_directory) != _param_file_contents(actual_directory)


@pytest.fixture(name="x500_templates", params=[b"\n", b"\r\n"], ids=["lf", "crlf"])
def fixture_x500_templates(tmp_path: Path, request: pytest.FixtureRequest) -> Path:
    """Copy numbered template inputs with explicit checkout line endings, excluding local download artifacts."""
    templates_dir = Path(__file__).parents[1] / "ardupilot_methodic_configurator" / "vehicle_templates" / "ArduCopter"
    isolated_templates = tmp_path / "templates"
    for name in ("Holybro_X500", "Holybro_X500_mig", "empty_4.6.x_mig"):
        destination = isolated_templates / name
        destination.mkdir(parents=True)
        sources = sorted((templates_dir / name).glob("[0-9][0-9]_*.param"))
        sources.extend((templates_dir / name).glob("*.json"))
        for source in sources:
            contents = source.read_bytes()
            if source.suffix == ".param":
                contents = contents.replace(b"\r\n", b"\n").replace(b"\n", request.param)
            (destination / source.name).write_bytes(contents)
    return isolated_templates


def test_existing_holybro_x500_migrates_to_x500_mig_parameter_files(  # pylint: disable=too-many-locals
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, x500_templates: Path
) -> None:
    """Migrate the old template with v2 step files and compare every .param file."""
    old_template = x500_templates / "Holybro_X500"
    migrated_template = x500_templates / "Holybro_X500_mig"
    empty_v2_template = x500_templates / "empty_4.6.x_mig"
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
    # RCMAP rows are new configuration inputs, not historical format-migration
    # output. The step's add_parameters copies live mappings when it is opened;
    # filename migration must not fabricate values or overwrite custom mappings.
    controller_file = "07_remote_controller_controller.param"
    mapping_names = {"RCMAP_ROLL", "RCMAP_PITCH", "RCMAP_THROTTLE", "RCMAP_YAW"}
    expected[controller_file] = b"".join(
        line
        for line in expected[controller_file].splitlines(keepends=True)
        if line.split(b",", maxsplit=1)[0].decode("utf-8") not in mapping_names
    )
    controller_step = filesystem.configuration_steps[controller_file]
    assert mapping_names <= controller_step["add_parameters"].keys()
    assert all("New Value" not in controller_step["add_parameters"][name] for name in mapping_names)
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
