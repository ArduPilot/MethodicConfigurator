#!/usr/bin/env python3

"""
Acceptance tests for isolated, offline template import and parameter regeneration.

Every non-migration template exercises parameter compounding, file-mode loading and full
project initialization in separately timed tests. Project creation/regeneration additionally
covers every ArduCopter and ArduPlane template; Heli/Rover have no corresponding empty
project template and are explicitly excluded only from those workflows. Direct inference
still covers all vehicle types. Directories ending in _mig (including descendants) never
enter the template cases.

Expectations assert complete parameter membership, values and comments rather than output
existence or aggregate success rates. Inferable component fields start with deliberately
wrong values; non-inferable context is preserved. Fixtures create each workflow's project,
so validation tests do not depend on test execution order. Installed templates are never
modified. Offline metadata is parsed for real; network access is forbidden.

A separate Copter/Plane orchestration fixture runs the production project manager and
component editor with only rendering/external boundaries replaced. Startup is preview-only;
the real parameter editor persists a representative battery step only with user permission.

SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>
SPDX-License-Identifier: GPL-3.0-or-later
"""

import json
import re
import tkinter as tk
from argparse import Namespace
from collections.abc import Generator
from copy import deepcopy
from pathlib import Path
from tkinter import ttk
from typing import Any
from unittest.mock import MagicMock

import pytest
from template_import_helpers import (
    TEMPLATES_BASE,
    ImportedProject,
    OrchestratedProject,
    ParameterSnapshot,
    assert_complete_source_round_trip,
    assert_inference_result,
    assert_parameter_snapshot,
    assert_persisted_components,
    assert_project_round_trip,
    assert_uninferred_context,
    copy_template_inputs,
    discover_templates,
    expected_compound,
    expected_project_copy,
    expected_regenerated_parameters,
    inference_expectations,
    numbered_parameter_files,
    parameter_snapshot,
    poisoned_component_input,
    prepare_orchestration_reference,
    reference_configuration,
    reference_metadata,
    set_component_value,
    template_id,
    template_vehicle_type,
)
from template_import_helpers import seed_offline_parameter_metadata as _seed_offline_parameter_metadata

# Pytest names fixtures after the injected arguments; small classes group user workflows.
# pylint: disable=redefined-outer-name,too-few-public-methods
from ardupilot_methodic_configurator import __main__ as application
from ardupilot_methodic_configurator.backend_filesystem import LocalFilesystem
from ardupilot_methodic_configurator.backend_flightcontroller import DEVICE_FC_PARAM_FROM_FILE, FlightController
from ardupilot_methodic_configurator.data_model_par_dict import Par, ParDict
from ardupilot_methodic_configurator.data_model_parameter_editor import ParameterEditor
from ardupilot_methodic_configurator.data_model_safe_evaluator import ConfigurationStepEvalError
from ardupilot_methodic_configurator.data_model_vehicle_components import ComponentDataModel
from ardupilot_methodic_configurator.data_model_vehicle_components_json_schema import VehicleComponentsJsonSchema
from ardupilot_methodic_configurator.data_model_vehicle_project import VehicleProjectManager
from ardupilot_methodic_configurator.data_model_vehicle_project_creator import NewVehicleProjectSettings, VehicleProjectCreator
from ardupilot_methodic_configurator.frontend_tkinter_base_window import BaseWindow
from ardupilot_methodic_configurator.frontend_tkinter_component_editor import ComponentEditorWindow
from ardupilot_methodic_configurator.frontend_tkinter_component_editor_base import ComponentEditorWindowBase


def test_offline_metadata_seed_uses_explicit_template_source(tmp_path: Path) -> None:
    """Offline metadata seeding must copy from the requested template, not mutable filesystem state."""
    template_dir = tmp_path / "empty_template"
    target_dir = tmp_path / "new_vehicle"
    template_dir.mkdir()
    target_dir.mkdir()
    (template_dir / "apm.pdef.xml").write_text(
        "<!-- Generated from git tag Copter-4.6.3 -->\ntemplate metadata", encoding="utf-8"
    )

    _seed_offline_parameter_metadata(template_dir, target_dir, "ArduCopter", "4.6.3")

    assert (target_dir / "apm.pdef.xml").read_text(encoding="utf-8") == (
        "<!-- Generated from git tag Copter-4.6.3 -->\ntemplate metadata"
    )


def test_offline_metadata_seed_does_not_overwrite_existing_metadata(tmp_path: Path) -> None:
    """Existing project metadata must remain untouched when seeding offline fixtures."""
    template_dir = tmp_path / "empty_template"
    target_dir = tmp_path / "new_vehicle"
    template_dir.mkdir()
    target_dir.mkdir()
    (template_dir / "apm.pdef.xml").write_text("template metadata", encoding="utf-8")
    (target_dir / "apm.pdef.xml").write_text("existing metadata", encoding="utf-8")

    _seed_offline_parameter_metadata(template_dir, target_dir, "ArduCopter", "4.6.3")

    assert (target_dir / "apm.pdef.xml").read_text(encoding="utf-8") == "existing metadata"


def test_offline_metadata_seed_rejects_stale_existing_metadata(tmp_path: Path) -> None:
    """An existing cached definition must still be checked for firmware compatibility."""
    template_dir = tmp_path / "empty_template"
    target_dir = tmp_path / "new_vehicle"
    template_dir.mkdir()
    target_dir.mkdir()
    (template_dir / "apm.pdef.xml").write_text("<!-- Generated from git tag Copter-4.6.0 -->", encoding="utf-8")
    (target_dir / "apm.pdef.xml").write_text("<!-- Generated from git tag Copter-4.5.0 -->", encoding="utf-8")

    with pytest.raises(ValueError, match=re.escape("incompatible with ArduCopter 4.6.3")):
        _seed_offline_parameter_metadata(template_dir, target_dir, "ArduCopter", "4.6.3")


def test_offline_metadata_seed_rejects_incompatible_firmware_metadata(tmp_path: Path) -> None:
    """Offline metadata must not silently come from another ArduPilot patch release."""
    template_dir = tmp_path / "empty_template"
    target_dir = tmp_path / "new_vehicle"
    template_dir.mkdir()
    target_dir.mkdir()
    (template_dir / "apm.pdef.xml").write_text("<!-- Generated from git tag Copter-4.6.0 -->\n<paramfile />", encoding="utf-8")

    with pytest.raises(ValueError, match=re.escape("incompatible with ArduCopter 4.6.3")):
        _seed_offline_parameter_metadata(template_dir, target_dir, "ArduCopter", "4.6.3")


def get_vehicle_template_directories() -> list[Path]:
    """Discover every parameter template while pruning migration directories and their descendants."""
    return discover_templates()


def get_empty_template_dir(vehicle_type: str) -> Path:
    """Select the explicitly supported offline project template, never a migration template."""
    versions = {"ArduCopter": "4.6.x", "ArduPlane": "4.7.x"}
    if vehicle_type not in versions:
        msg = f"No empty project template is available for {vehicle_type}"
        raise FileNotFoundError(msg)
    directory = TEMPLATES_BASE / vehicle_type / f"empty_{versions[vehicle_type]}"
    assert directory.is_dir(), f"Missing supported empty template: {directory}"
    return directory


TEMPLATE_DIRECTORIES = get_vehicle_template_directories()
TEMPLATE_CASES = [pytest.param(directory, id=template_id(directory)) for directory in TEMPLATE_DIRECTORIES]
PROJECT_CASES = [
    pytest.param(directory, id=template_id(directory))
    for directory in TEMPLATE_DIRECTORIES
    if template_vehicle_type(directory) in {"ArduCopter", "ArduPlane"}
]


@pytest.fixture(autouse=True)
def forbid_template_metadata_downloads(monkeypatch: pytest.MonkeyPatch) -> None:
    """Fail at the network boundary if any offline workflow tries to replace local metadata."""

    def reject_download(*_args: object, **_kwargs: object) -> bool:
        pytest.fail("Template acceptance tests must use local XML metadata, not download it")

    monkeypatch.setattr("ardupilot_methodic_configurator.annotate_params.download_file_from_url", reject_download)
    monkeypatch.setattr("ardupilot_methodic_configurator.backend_filesystem.download_file_from_url", reject_download)


def _compound_template_parameters(template_dir: Path, vehicle_type: str) -> ParDict:
    """Use real parameter-only filesystem services without parsing metadata or changing the template."""
    filesystem = LocalFilesystem(
        str(template_dir),
        vehicle_type,
        "",
        allow_editing_template_files=False,
        save_component_to_system_templates=False,
        load_project=False,
    )
    filesystem.file_parameters = filesystem.read_params_from_files()
    compounded, _first_step = filesystem.compound_params(last_filename=None, skip_default=False)
    return compounded


@pytest.mark.parametrize("metadata_contents", [None, "invalid XML"])
def test_user_can_compound_template_parameters_without_metadata(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    metadata_contents: str | None,
) -> None:
    """
    Overlapping numbered files, excluded files, and missing or invalid XML.

    GIVEN: Overlapping numbered files, excluded files, and missing or invalid XML
    WHEN: The user compounds and exports the parameters
    THEN: Exact membership, last-file precedence and manual-override comments survive without source edits
    """
    (tmp_path / "20_tuning.param").write_text("SHARED,2 # @manual_override tuned value\nFINAL,3\n", encoding="utf-8")
    (tmp_path / "10_setup.param").write_text("SHARED,1 # initial value\nINITIAL,4 # retained reason\n", encoding="utf-8")
    (tmp_path / "00_default.param").write_text("DEFAULT_ONLY,5\n", encoding="utf-8")
    (tmp_path / "01_ignore_readonly.param").write_text("READONLY_ONLY,6\n", encoding="utf-8")
    (tmp_path / "complete.param").write_text("UNNUMBERED_ONLY,7\n", encoding="utf-8")
    if metadata_contents is not None:
        (tmp_path / "apm.pdef.xml").write_text(metadata_contents, encoding="utf-8")
    original_files = {path.name: path.read_bytes() for path in tmp_path.iterdir()}

    def reject_metadata(*_args: object, **_kwargs: object) -> None:
        pytest.fail("Parameter compounding must not parse metadata")

    monkeypatch.setattr("ardupilot_methodic_configurator.backend_filesystem.parse_parameter_metadata", reject_metadata)
    compounded = _compound_template_parameters(tmp_path, "ArduCopter")
    output = tmp_path / "params.param"
    compounded.export_to_param(str(output))
    assert_parameter_snapshot(
        ParDict.from_file(str(output)),
        {
            "SHARED": (2, "@manual_override tuned value"),
            "INITIAL": (4, "retained reason"),
            "FINAL": (3, None),
        },
    )
    assert output.read_text(encoding="utf-8").count("@manual_override") == 1
    assert {name: (tmp_path / name).read_bytes() for name in original_files} == original_files
    assert {path.name for path in tmp_path.iterdir()} == {*original_files, "params.param"}


def test_template_discovery_prunes_migration_trees_without_losing_parent_templates(tmp_path: Path) -> None:
    """
    Direct, nested and migration templates, plus an unrelated child directory.

    GIVEN: Direct, nested and migration templates, plus an unrelated child directory
    WHEN: Templates are discovered
    THEN: All real parameter directories are returned in stable order and no migration subtree is visited
    """
    for name in (
        "ArduCopter/alpha",
        "ArduCopter/alpha/4.6.x-params",
        "ArduCopter/alpha/assets",
        "ArduCopter/alpha_mig/4.6.x-params",
        "ArduCopter/beta/child_mig",
        "ArduPlane/plane",
    ):
        directory = tmp_path / name
        directory.mkdir(parents=True)
        if not name.endswith("assets"):
            (directory / "10_setup.param").write_text("EXAMPLE,1\n", encoding="utf-8")
    assert discover_templates(tmp_path) == [
        tmp_path / "ArduCopter/alpha",
        tmp_path / "ArduCopter/alpha/4.6.x-params",
        tmp_path / "ArduPlane/plane",
    ]


def test_acceptance_cases_cover_all_supported_types_without_migration_templates() -> None:
    """
    Installed vehicle templates.

    GIVEN: Installed vehicle templates
    WHEN: Acceptance cases are collected
    THEN: All four supported vehicle types are covered and migration directories cannot enter any case
    """
    assert TEMPLATE_DIRECTORIES
    assert {template_vehicle_type(path) for path in TEMPLATE_DIRECTORIES} == {"ArduCopter", "ArduPlane", "Heli", "Rover"}
    assert all(not part.endswith("_mig") for path in TEMPLATE_DIRECTORIES for part in path.relative_to(TEMPLATES_BASE).parts)
    assert {case.values[0] for case in PROJECT_CASES} == {
        path for path in TEMPLATE_DIRECTORIES if template_vehicle_type(path) in {"ArduCopter", "ArduPlane"}
    }


def test_round_trip_expectations_reject_unexpected_invalid_derived_rules() -> None:
    """
    Malformed derivation rules cannot turn into silently accepted unchanged parameters.

    GIVEN: A derived expression with an unexpected missing input
    WHEN: The independent round-trip oracle interprets the rule
    THEN: Validation fails rather than accepting the copied FC value as correct output
    """
    original = {"10_setup.param": ParDict({"EXAMPLE": Par(1)})}
    steps = {"10_setup.param": {"derived_parameters": {"EXAMPLE": {"New Value": "unknown_variable"}}}}
    with pytest.raises(ConfigurationStepEvalError):
        expected_regenerated_parameters(
            original,
            steps,
            {"vehicle_components": {"Propellers": {"Specifications": {"Diameter_inches": 10}}}},
            {"EXAMPLE": 1},
        )


def test_round_trip_expectations_cover_overrides_additions_deletions_and_comments() -> None:
    """
    The declaration oracle distinguishes intentional changes from preservation requirements.

    GIVEN: Copied values, a manual override, conditional additions/deletions and computed reasons
    WHEN: Configuration declarations are interpreted independently of application merging
    THEN: The exact expected parameter set, values and serialized comments match a literal reference
    """
    original = {
        "10_setup.param": ParDict(
            {
                "UNCHANGED": Par(1, "original reason"),
                "OVERRIDE": Par(10, "@manual_override user choice"),
                "REMOVE": Par(6),
                "DERIVED": Par(5),
            }
        )
    }
    steps = {
        "10_setup.param": {
            "forced_parameters": {"OVERRIDE": {"New Value": "4", "Change Reason": "forced"}},
            "derived_parameters": {
                "DERIVED": {"New Value": "fc_parameters['DERIVED'] * 2", "Change Reason": "'changed' if 1 else 'unused'"}
            },
            "add_parameters": {
                "ADDED": {"if": "1", "Change Reason": "copied FC value"},
                "NOT_ADDED": {"if": "0", "New Value": "100"},
            },
            "delete_parameters": {"REMOVE": {"if": "1"}, "UNCHANGED": {"if": "0"}},
        }
    }
    expected = expected_regenerated_parameters(original, steps, {}, {"OVERRIDE": 10, "DERIVED": 2, "ADDED": 7})
    assert expected == {
        "10_setup.param": {
            "UNCHANGED": (1, "original reason"),
            "OVERRIDE": (10, "@manual_override user choice"),
            "DERIVED": (4, "changed"),
            "ADDED": (7, "copied FC value"),
        }
    }
    assert original["10_setup.param"]["DERIVED"].value == 5
    assert "REMOVE" in original["10_setup.param"]


def test_complete_round_trip_reference_rejects_unaccounted_source_loss() -> None:
    """
    Matching subsets must not conceal source loss.

    GIVEN: A source-only battery calibration omitted from the expected project
    WHEN: Complete source preservation is checked
    THEN: Even a matching actual/expected subset cannot hide the missing source name
    """
    source: ParameterSnapshot = {"BATT_VOLT_MULT": (18.181999, None), "BATT_CAPACITY": (5000, None)}
    incomplete: dict[str, ParameterSnapshot] = {"10_setup.param": {"BATT_CAPACITY": (5000, None)}}
    with pytest.raises(AssertionError, match="silently lost source"):
        assert_complete_source_round_trip(ParDict({"BATT_CAPACITY": Par(5000)}), source, incomplete, {}, {})


def test_complete_round_trip_reference_allows_only_declared_deletions() -> None:
    """
    Preservation and explicitly declared transformations are checked together.

    GIVEN: One unchanged calibration, one component-derived value and one obsolete source parameter
    WHEN: Complete output is checked against independently evaluated declarations
    THEN: Exact preservation and the explicitly enabled deletion pass, but a disabled deletion fails
    """
    source: ParameterSnapshot = {"BATT_VOLT_MULT": (18.181999, None), "DERIVED": (2, None), "OBSOLETE": (3, None)}
    files = {"10_setup.param": {"BATT_VOLT_MULT": (18.181999, None), "DERIVED": (4, "computed")}}
    actual = ParDict({"BATT_VOLT_MULT": Par(18.181999), "DERIVED": Par(4, "computed")})
    steps = {"10_setup.param": {"delete_parameters": {"OBSOLETE": {"if": "remove_obsolete"}}}}
    assert_complete_source_round_trip(actual, source, files, steps, {"remove_obsolete": True})
    with pytest.raises(AssertionError, match="silently lost source"):
        assert_complete_source_round_trip(actual, source, files, steps, {"remove_obsolete": False})


@pytest.fixture
def compounded_file(template_dir: Path, tmp_path: Path) -> Path:
    """Produce one template's export using real compounding and serialization, failing on empty output."""
    parameters = _compound_template_parameters(template_dir, template_vehicle_type(template_dir))
    assert parameters, f"No configuration parameters in {template_id(template_dir)}"
    output = tmp_path / "params.param"
    parameters.export_to_param(str(output))
    return output


@pytest.fixture
def initialized_template(template_dir: Path, tmp_path: Path) -> LocalFilesystem:
    """Fully open an isolated template copy, including configuration loading, migration and XML parsing."""
    copied_template = tmp_path / "source_template"
    copy_template_inputs(template_dir, copied_template)
    assert (copied_template / "apm.pdef.xml").is_file(), template_id(template_dir)
    return LocalFilesystem(
        str(copied_template),
        template_vehicle_type(template_dir),
        "",
        allow_editing_template_files=False,
        save_component_to_system_templates=False,
    )


class TestTemplateCompounding:
    """Assert complete compounding and serialization behavior for every discovered template."""

    @pytest.mark.parametrize("template_dir", TEMPLATE_CASES)
    def test_user_can_compound_all_template_parameters(self, template_dir: Path, compounded_file: Path) -> None:
        """
        Each installed non-migration template's numbered parameter files.

        GIVEN: Each installed non-migration template's numbered parameter files
        WHEN: Its parameters are compounded and serialized
        THEN: Every expected name, final value and comment is preserved, with no extra parameters
        """
        expected = expected_compound(template_dir)
        assert expected, template_id(template_dir)
        assert_parameter_snapshot(ParDict.from_file(str(compounded_file)), expected)
        names = [line.split(",", 1)[0] for line in compounded_file.read_text(encoding="utf-8").splitlines()]
        assert len(names) == len(set(names)) == len(expected)
        assert names == sorted(expected, key=ParDict.missionplanner_sort)

    @pytest.mark.parametrize("template_dir", TEMPLATE_CASES)
    def test_user_can_fully_initialize_each_template(
        self,
        template_dir: Path,
        initialized_template: LocalFilesystem,
    ) -> None:
        """
        A private copy of each template, with real offline metadata.

        GIVEN: A private copy of each template, with real offline metadata
        WHEN: The user opens it through normal project initialization
        THEN: Components, configuration steps, phases, migrated files and parameter tooltips are loaded
        """
        filesystem = initialized_template
        assert filesystem.vehicle_type == template_vehicle_type(template_dir)
        assert filesystem.fw_version == filesystem.get_fc_fw_version_from_vehicle_components_json()
        assert filesystem.vehicle_components_fs.data
        valid, message = filesystem.validate_vehicle_components(filesystem.vehicle_components_fs.data)
        assert valid, message
        assert filesystem.configuration_steps
        assert filesystem.configuration_phases
        configuration = Path(filesystem.vehicle_dir) / filesystem.configuration_steps_filename
        if not configuration.is_file():
            configuration = TEMPLATES_BASE.parent / filesystem.configuration_steps_filename
        declared_configuration = json.loads(configuration.read_text(encoding="utf-8-sig"))
        assert set(filesystem.configuration_steps) == set(declared_configuration["steps"])
        assert filesystem.configuration_phases == declared_configuration["phases"]
        assert set(filesystem.file_parameters) == {
            path.name for path in numbered_parameter_files(Path(filesystem.vehicle_dir))
        }
        expected = expected_compound(template_dir)
        compound, _ = filesystem.compound_params()
        assert_parameter_snapshot(compound, expected)
        assert filesystem.doc_dict
        documented = set(compound) & set(filesystem.doc_dict)
        assert documented, "No loaded template parameters have documentation"
        for name in documented:
            assert "doc_tooltip" in filesystem.doc_dict[name], name
            assert "doc_tooltip_sorted_numerically" in filesystem.doc_dict[name], name


class TestFileBasedParameterLoading:
    """File simulation must load actual names and values, not merely the right parameter count."""

    @pytest.mark.parametrize("template_dir", TEMPLATE_CASES)
    def test_user_can_load_parameters_from_compounded_file(
        self,
        template_dir: Path,
        compounded_file: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """
        Every template's compounded params.param file.

        GIVEN: Every template's compounded params.param file
        WHEN: A file-mode flight controller connects and downloads it
        THEN: Both returned and stored parameters contain exactly the original final names and values
        """
        monkeypatch.chdir(compounded_file.parent)
        controller = FlightController(reboot_time=0)
        try:
            assert controller.connect(DEVICE_FC_PARAM_FROM_FILE, log_errors=True) == ""
            downloaded, _defaults = controller.download_params()
            expected = {name: value for name, (value, _comment) in expected_compound(template_dir).items()}
            assert set(downloaded) == set(expected)
            assert downloaded == pytest.approx(expected, rel=0, abs=0.00000051)
            assert controller.fc_parameters == pytest.approx(expected, rel=0, abs=0.00000051)
        finally:
            controller.disconnect()


@pytest.fixture
def imported_project(  # pylint: disable=too-many-locals
    template_dir: Path,
    compounded_file: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> ImportedProject:
    """Create a project for each requesting test, independently of all other test methods."""
    monkeypatch.chdir(compounded_file.parent)
    controller = FlightController(reboot_time=0)
    try:
        assert controller.connect(DEVICE_FC_PARAM_FROM_FILE, log_errors=True) == ""
        fc_parameters, _ = controller.download_params()
        assert fc_parameters
        # Disconnect clears the controller-owned mapping; the workflow needs its own snapshot.
        fc_parameters = dict(fc_parameters)
    finally:
        controller.disconnect()
    vehicle_type = template_vehicle_type(template_dir)
    empty_template = get_empty_template_dir(vehicle_type)
    # Capture input references before any production project loading or inference.
    source_parameters = expected_compound(template_dir)
    reference_steps = reference_configuration(empty_template, vehicle_type)
    metadata = reference_metadata(empty_template, vehicle_type)
    copied_parameters = expected_project_copy(empty_template, source_parameters)
    original_components = json.loads((template_dir / "vehicle_components.json").read_text(encoding="utf-8"))
    empty_components = json.loads((empty_template / "vehicle_components.json").read_text(encoding="utf-8"))
    original_components["Components"]["Flight Controller"]["Firmware"] = deepcopy(
        empty_components["Components"]["Flight Controller"]["Firmware"]
    )
    expected_components = inference_expectations(
        {name: value for name, (value, _comment) in source_parameters.items()}, original_components, metadata
    )
    reference_components = deepcopy(original_components)
    for path, value in expected_components.items():
        set_component_value(reference_components, path, value)
    reference_variables = {
        "vehicle_components": reference_components["Components"],
        "doc_dict": metadata,
        "fc_parameters": {name: value for name, (value, _comment) in source_parameters.items()},
    }
    expected_files = expected_regenerated_parameters(
        copied_parameters, reference_steps, reference_variables, reference_variables["fc_parameters"]
    )
    isolated_empty = tmp_path / "empty_template"
    copy_template_inputs(empty_template, isolated_empty)
    filesystem = LocalFilesystem(
        str(isolated_empty),
        vehicle_type,
        "",
        allow_editing_template_files=False,
        save_component_to_system_templates=False,
    )
    # Preserve user-supplied, non-inferable vehicle context (chemistry, propeller size,
    # product information, etc.). Poison every recoverable field below; the source data
    # must never make disabled inference pass. The project's firmware is the selected
    # empty template's firmware, even when the FC parameter fixture predates that release.
    settings = NewVehicleProjectSettings(
        copy_vehicle_image=False,
        blank_component_data=False,
        reset_fc_parameters_to_their_defaults=False,
        infer_comp_specs_and_conn_from_fc_params=True,
        use_fc_params=True,
        blank_change_reason=True,
    )
    new_directory = Path(
        VehicleProjectCreator(filesystem).create_new_vehicle_from_template(
            str(isolated_empty),
            str(tmp_path / "projects"),
            "imported_vehicle",
            settings,
            fc_connected=False,
            fc_parameters=fc_parameters,
        )
    )
    assert new_directory.is_dir()
    # Validate the copy stage before regeneration can overwrite calibration values.
    assert {path.name for path in numbered_parameter_files(new_directory)} == set(copied_parameters)
    for filename, parameters in copied_parameters.items():
        assert_parameter_snapshot(ParDict.from_file(str(new_directory / filename)), parameter_snapshot(parameters))
    _seed_offline_parameter_metadata(isolated_empty, new_directory, vehicle_type, filesystem.fw_version)
    filesystem.re_init(str(new_directory), vehicle_type)
    poisoned = poisoned_component_input(original_components, expected_components)
    model = ComponentDataModel(poisoned, filesystem.doc_dict, VehicleComponentsJsonSchema(filesystem.load_schema()))
    model.process_fc_parameters(fc_parameters, filesystem.doc_dict)
    inferred = model.get_component_data()
    assert_inference_result(inferred, expected_components)
    assert_uninferred_context(inferred, original_components, expected_components)
    valid, message = filesystem.validate_vehicle_components(inferred)
    assert valid, message
    error, message = filesystem.save_vehicle_components_json_data(inferred, str(new_directory))
    assert not error, message
    filesystem.load_vehicle_components_json_data(str(new_directory))
    return ImportedProject(
        filesystem,
        new_directory,
        fc_parameters,
        copied_parameters,
        expected_components,
        original_components,
        source_parameters,
        reference_steps,
        reference_variables,
        expected_files,
    )


@pytest.fixture
def regenerated_project(imported_project: ImportedProject) -> ImportedProject:
    """Apply and persist real forced/derived changes using the actual imported FC values."""
    return regenerate_project(imported_project)


def regenerate_project(project: ImportedProject) -> ImportedProject:
    """Execute real regeneration separately so regression tests can inject faults at production boundaries."""
    pending = project.filesystem.calculate_derived_and_forced_param_changes(
        list(project.fc_parameters),
        fc_parameters=project.fc_parameters,
    )
    project.filesystem.apply_computed_changes(pending)
    project.filesystem.save_vehicle_params_to_files(list(project.filesystem.file_parameters))
    return project


@pytest.fixture
def infer_components() -> bool:
    """Enable production component inference unless a test explicitly declines it."""
    return True


def _reject_workflow_error(title: str, message: str) -> None:
    """Do not let a mocked error dialog conceal failed validation, saving or calculation."""
    pytest.fail(f"{title}: {message}")


@pytest.fixture
def headless_component_editor(monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, str]]:
    """Replace rendering/dialogs, not the real editor, validation, inference or save callbacks."""
    warnings: list[tuple[str, str]] = []

    def initialize_shell(window: ComponentEditorWindow, _root_tk: tk.Tk | None = None) -> None:
        window.root = MagicMock(spec=tk.Tk)
        # Simulate the user's Save button through the real application mainloop adapter.
        window.root.mainloop.side_effect = window.on_save_pressed

    def render_entries(window: ComponentEditorWindow) -> None:
        # Tk entry doubles expose live model values to the REAL pre-save validation.
        # An empty entry_widgets mapping would silently bypass field validation.
        for component, sections in window.data_model.get_component_data()["Components"].items():
            for section, fields in sections.items():
                if not isinstance(fields, dict):
                    continue
                for field in fields:
                    path = (component, section, field)
                    entry = MagicMock(spec=ttk.Entry)
                    entry.get.side_effect = lambda path=path: str(window.data_model.get_component_value(path))
                    window.entry_widgets[path] = entry

    monkeypatch.setattr(BaseWindow, "__init__", initialize_shell)
    monkeypatch.setattr(tk, "StringVar", MagicMock())
    monkeypatch.setattr(ComponentEditorWindowBase, "_initialize_ui", lambda _window: None)
    monkeypatch.setattr(ComponentEditorWindow, "populate_frames", render_entries)
    editor_module = "ardupilot_methodic_configurator.frontend_tkinter_component_editor_base"
    monkeypatch.setattr(f"{editor_module}.ConfirmationPopupWindow.should_display", lambda _name: True)
    monkeypatch.setattr(f"{editor_module}.confirm_component_properties", lambda _root: True)
    monkeypatch.setattr(f"{editor_module}.show_error_message", _reject_workflow_error)
    monkeypatch.setattr(application, "show_error_message", _reject_workflow_error)
    monkeypatch.setattr(application, "show_warning_message", lambda title, message: warnings.append((title, message)))
    monkeypatch.setattr(application, "should_open_firmware_documentation", lambda _controller: False)
    monkeypatch.setattr(LocalFilesystem, "store_recently_used_template_dirs", lambda _template, _base: None)
    monkeypatch.setattr(LocalFilesystem, "store_recently_used_vehicle_dir", lambda _directory: None)
    return warnings


@pytest.fixture
def orchestrated_project(  # pylint: disable=too-many-locals,too-many-arguments
    template_dir: Path,
    compounded_file: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    headless_component_editor: list[tuple[str, str]],
    infer_components: bool,
) -> Generator[OrchestratedProject, None, None]:
    """Run production creation, opening, component setup, validation, saving and change preview."""
    vehicle_type = template_vehicle_type(template_dir)
    # All references precede the first production initialization.
    project = prepare_orchestration_reference(
        template_dir,
        get_empty_template_dir(vehicle_type),
        tmp_path / "orchestration_template",
        infer_components=infer_components,
    )
    isolated_empty = project.directory
    filesystem = project.filesystem
    original = project.original_components
    firmware = original["Components"]["Flight Controller"]["Firmware"]
    real_copy = filesystem.copy_template_files_to_new_vehicle_dir

    def copy_with_offline_metadata(template: str, destination: str, **options: Any) -> str:  # noqa: ANN401
        error = real_copy(template, destination, **options)
        assert not error, error
        # Only replace the unavailable download boundary; manager/open/re_init remain real.
        _seed_offline_parameter_metadata(Path(template), destination, vehicle_type, firmware["Version"])
        return error

    monkeypatch.setattr(filesystem, "copy_template_files_to_new_vehicle_dir", copy_with_offline_metadata)
    monkeypatch.chdir(compounded_file.parent)
    controller = FlightController(reboot_time=0)
    try:
        assert controller.connect(DEVICE_FC_PARAM_FROM_FILE, log_errors=True) == ""
        parameters, _defaults = controller.download_params()
        assert parameters == pytest.approx(project.fc_parameters, rel=0, abs=0.00000051)
        controller.info.flight_sw_version_and_type = firmware["Version"]
        product = original["Components"]["Flight Controller"]["Product"]
        controller.info.vendor = product["Manufacturer"]
        controller.info.firmware_type = product["Model"]
        controller.info.mcu_series = original["Components"]["Flight Controller"]["Specifications"]["MCU Series"]
        manager = VehicleProjectManager(filesystem, controller)
        settings = NewVehicleProjectSettings(
            infer_comp_specs_and_conn_from_fc_params=infer_components, use_fc_params=True, blank_change_reason=True
        )
        directory = Path(
            manager.create_new_vehicle_from_template(
                str(isolated_empty), str(tmp_path / "projects"), "orchestrated_vehicle", settings
            )
        )
        project.directory = directory
        assert directory == Path(filesystem.vehicle_dir)
        assert manager.is_new_project
        assert manager.infer_comp_specs_and_conn_from_fc_params is infer_components
        assert set(filesystem.file_parameters) == set(project.copied_parameters)
        before = {path.name: path.read_bytes() for path in numbered_parameter_files(directory)}
        for filename, expected in project.expected_files.items():
            assert_parameter_snapshot(ParDict.from_file(str(directory / filename)), expected)
        state = application.ApplicationState(Namespace())
        state.local_filesystem = filesystem
        state.flight_controller = controller
        state.vehicle_project_manager = manager
        state.vehicle_type = vehicle_type
        # No direct process_fc_parameters(), JSON save, re_init() or bulk apply calls here.
        application.run_initial_component_editor(state)
        assert_persisted_components(project, controller)
        yield OrchestratedProject(state, project, before, headless_component_editor)
    finally:
        controller.disconnect()


def _expected_reviewed_battery(project: ImportedProject) -> ParameterSnapshot:
    """Independently account for non-default auto-imports before declared battery derivation/deletion."""
    filename = "11_battery.param"
    inputs = project.copied_parameters[filename].deep_copy()
    defaults = ParDict.from_file(str(get_empty_template_dir(project.filesystem.vehicle_type) / "00_default.param"))
    step = project.reference_steps[filename]
    # Both representative fixtures use Analog: this step has no connection-prefix renames.
    assert project.reference_variables["vehicle_components"]["Battery Monitor"]["FC Connection"]["Type"] == "Analog"
    for name, value in project.fc_parameters.items():
        if (
            name not in inputs
            and name in defaults
            and any(re.match(pattern, name) for pattern in step.get("autoimport_nondefault_regexp", []))
            and abs(value - defaults[name].value) > 1e-8 + 1e-4 * abs(defaults[name].value)
        ):
            inputs[name] = Par(value)
    return expected_regenerated_parameters(
        {filename: inputs}, project.reference_steps, project.reference_variables, project.fc_parameters
    )[filename]


@pytest.mark.parametrize(
    "template_dir",
    [
        pytest.param(TEMPLATES_BASE / "ArduCopter" / "Holybro_X500", id="ArduCopter/Holybro_X500"),
        pytest.param(TEMPLATES_BASE / "ArduPlane" / "normal_plane", id="ArduPlane/normal_plane"),
    ],
)
class TestProductionTemplateImportOrchestration:
    """Bridge domain acceptance coverage to the real application and parameter-editor orchestration."""

    def test_new_project_setup_previews_changes_without_writing_parameters(
        self, orchestrated_project: OrchestratedProject
    ) -> None:
        """
        New project setup previews changes without modifying parameter files.

        GIVEN: A project created/opened by the real manager with inference enabled
        WHEN: The real initial editor validates and saves inferred components
        THEN: Changes are announced, but every parameter byte and loaded value stays unchanged.
        """
        workflow = orchestrated_project
        project = workflow.project
        assert project.fc_parameters["BATT_CAPACITY"] > 1200
        assert any("11_battery.param" in message for _title, message in workflow.warnings)
        assert {path.name: path.read_bytes() for path in numbered_parameter_files(project.directory)} == (
            workflow.parameter_bytes_before_setup
        )
        assert_project_round_trip(project)

    @pytest.mark.parametrize("infer_components", [False])
    def test_declining_inference_preserves_user_component_specifications(
        self, orchestrated_project: OrchestratedProject
    ) -> None:
        """
        Declining inference preserves the user's component specifications.

        GIVEN: Valid user component specifications differing from the source FC
        WHEN: Project creation disables inference and the real initial editor saves
        THEN: The saved and evaluation-context capacity stays at the user's value, not the FC value.
        """
        project = orchestrated_project.project
        assert project.fc_parameters["BATT_CAPACITY"] > 1200
        data = json.loads((project.directory / "vehicle_components.json").read_text(encoding="utf-8"))
        assert data["Components"]["Battery"]["Specifications"]["Capacity mAh"] == 1200
        assert_project_round_trip(project)

    @pytest.mark.parametrize("accept_save", [True, False], ids=["save-accepted", "save-declined"])
    def test_reviewed_parameter_step_is_persisted_only_with_user_permission(
        self, orchestrated_project: OrchestratedProject, accept_save: bool
    ) -> None:
        """
        Reviewed parameter changes are saved only with user permission.

        GIVEN: A real manager-created project with components saved by the real initial editor
        WHEN: The parameter editor opens the battery step and the user accepts or declines saving
        THEN: Complete reviewed values/reasons match declarations, and only accepted changes reach disk.
        """
        workflow = orchestrated_project
        project = workflow.project
        filename = "11_battery.param"
        expected = _expected_reviewed_battery(project)
        editor = ParameterEditor(filename, workflow.state.flight_controller, project.filesystem)
        selected, proceed = editor.handle_param_file_change_workflow(
            filename,
            forced=True,
            gui_complexity="normal",
            auto_open_documentation=False,
            handle_imu_temp_cal=lambda _filename: None,
            handle_copy_fc_values=lambda _filename: False,
            handle_upload_file=lambda _filename: False,
            ask_confirmation=lambda _title, _message: False,
            show_error=_reject_workflow_error,
            show_info=lambda _title, _message: None,
        )
        assert (selected, proceed) == (filename, True)
        assert_parameter_snapshot(editor.get_parameters_as_par_dict(), expected)
        assert (project.directory / filename).read_bytes() == workflow.parameter_bytes_before_setup[filename]
        confirmations: list[tuple[str, str]] = []

        def confirm_save(title: str, message: str) -> bool:
            confirmations.append((title, message))
            return accept_save

        assert (
            editor.handle_write_changes_workflow(annotate_params_into_files=False, ask_user_confirmation=confirm_save)
            is accept_save
        )
        assert len(confirmations) == 1
        assert filename in confirmations[0][1]
        if accept_save:
            project.expected_files[filename] = expected
            assert (project.directory / filename).read_bytes() != workflow.parameter_bytes_before_setup[filename]
            assert all(not parameter.is_dirty for parameter in editor.current_step_parameters.values())
        else:
            assert (project.directory / filename).read_bytes() == workflow.parameter_bytes_before_setup[filename]
            assert any(parameter.is_dirty for parameter in editor.current_step_parameters.values())
        for path in numbered_parameter_files(project.directory):
            if path.name != filename:
                assert path.read_bytes() == workflow.parameter_bytes_before_setup[path.name]
        assert_project_round_trip(project)

    @pytest.mark.parametrize("missing_operation", ["inference", "component_save"])
    def test_acceptance_fixture_rejects_missing_production_operations(
        self,
        template_dir: Path,
        request: pytest.FixtureRequest,
        monkeypatch: pytest.MonkeyPatch,
        missing_operation: str,
    ) -> None:
        """
        Missing production operations are rejected rather than repaired by fixtures.

        GIVEN: The same isolated inputs used by the production orchestration acceptance fixture
        WHEN: Production inference or the component Save action is accidentally omitted
        THEN: The fixture's persisted-state assertions reject that regression rather than repairing it.
        """
        assert not template_dir.name.endswith("_mig")
        if missing_operation == "inference":
            monkeypatch.setattr(ComponentEditorWindow, "set_values_from_fc_parameters", lambda *_args: None)
            # With poisoned values, the real validation must refuse to save.
            with pytest.raises(pytest.fail.Exception):
                request.getfixturevalue("orchestrated_project")
        else:
            monkeypatch.setattr(ComponentEditorWindow, "on_save_pressed", lambda _window: None)
            with pytest.raises(AssertionError):
                request.getfixturevalue("orchestrated_project")


@pytest.mark.parametrize("template_dir", [TEMPLATES_BASE / "ArduCopter" / "Holybro_X500"])
@pytest.mark.parametrize("fault", ["evaluation_context", "missing_rules", "missing_source_parameter"])
def test_round_trip_detects_corrupted_production_state(
    imported_project: ImportedProject, monkeypatch: pytest.MonkeyPatch, fault: str
) -> None:
    """
    Previously invisible production faults fail complete round-trip validation.

    GIVEN: A complete imported project and an independently captured reference
    WHEN: Production evaluation context, generation rules or source-only calibration is corrupted
    THEN: The same round-trip assertion used for all templates rejects each formerly invisible fault
    """
    project = imported_project
    assert project.fc_parameters["BATT_CAPACITY"] == 5000
    assert project.source_parameters["BATT_VOLT_MULT"][0] == pytest.approx(18.181999)
    if fault == "evaluation_context":
        original_get_variables = project.filesystem.get_eval_variables

        def wrong_capacity() -> dict[str, Any]:
            variables = deepcopy(original_get_variables())
            variables["vehicle_components"]["Battery"]["Specifications"]["Capacity mAh"] = 1
            return variables

        monkeypatch.setattr(project.filesystem, "get_eval_variables", wrong_capacity)
    elif fault == "missing_rules":
        project.filesystem.configuration_steps = {name: {} for name in project.filesystem.configuration_steps}
    else:
        for parameters in project.filesystem.file_parameters.values():
            parameters.pop("BATT_VOLT_MULT", None)
    regenerate_project(project)
    with pytest.raises(AssertionError):
        assert_project_round_trip(project)


class TestTemplateImportWithComponentInference:
    """Every supported project template must import successfully; no aggregate failure allowance."""

    @pytest.mark.parametrize("template_dir", PROJECT_CASES)
    def test_user_can_create_project_with_component_inference(self, imported_project: ImportedProject) -> None:
        """
        Each ArduCopter or ArduPlane template's FC values and a corresponding empty template.

        GIVEN: Each ArduCopter or ArduPlane template's FC values and a corresponding empty template
        WHEN: A private vehicle project is created and components inferred from poisoned input
        THEN: All configuration files exist and all recoverable components are correct and persisted
        """
        project = imported_project
        data = json.loads((project.directory / "vehicle_components.json").read_text(encoding="utf-8"))
        assert_inference_result(data, project.expected_components)
        assert set(project.filesystem.file_parameters) == set(project.copied_parameters)
        assert project.filesystem.doc_dict
        assert (project.directory / "apm.pdef.xml").is_file()


class TestComponentInferenceValidation:
    """Require actual reconstruction of every recoverable field, not retention of prefilled expectations."""

    @pytest.mark.parametrize("template_dir", TEMPLATE_CASES)
    def test_component_inference_from_params_file_matches_original(
        self,
        template_dir: Path,
        initialized_template: LocalFilesystem,
    ) -> None:
        """
        A real template's parameters, metadata and deliberately incorrect inferable component values.

        GIVEN: A real template's parameters, metadata and deliberately incorrect inferable component values
        WHEN: The model processes the parameters
        THEN: Every recoverable field matches its independent reference and context is left unchanged
        """
        filesystem = initialized_template
        original = deepcopy(filesystem.vehicle_components_fs.data)
        assert original is not None
        fc_parameters = {name: value for name, (value, _comment) in expected_compound(template_dir).items()}
        expected = inference_expectations(fc_parameters, original, filesystem.doc_dict)
        poisoned = poisoned_component_input(original, expected)
        model = ComponentDataModel(poisoned, filesystem.doc_dict, VehicleComponentsJsonSchema(filesystem.load_schema()))
        model.process_fc_parameters(fc_parameters, filesystem.doc_dict)
        actual = model.get_component_data()
        assert_inference_result(actual, expected)
        assert poisoned == poisoned_component_input(original, expected), "Inference mutated caller-owned input"
        assert_uninferred_context(actual, original, expected)

    @pytest.mark.parametrize("template_dir", PROJECT_CASES)
    def test_inferred_components_match_original_templates(self, regenerated_project: ImportedProject) -> None:
        """
        A fixture-created, independently regenerated project for every supported template.

        GIVEN: A fixture-created, independently regenerated project for every supported template
        WHEN: Persisted component data is read without relying on any preceding test
        THEN: All recoverable values survive regeneration and firmware identity remains valid
        """
        project = regenerated_project
        data = json.loads((project.directory / "vehicle_components.json").read_text(encoding="utf-8"))
        assert_inference_result(data, project.expected_components)
        assert_uninferred_context(data, project.original_components, project.expected_components)
        assert (
            data["Components"]["Flight Controller"]["Firmware"]
            == project.original_components["Components"]["Flight Controller"]["Firmware"]
        )


class TestParameterDerivationValidation:
    """Validate every output parameter against source FC values and explicit configuration declarations."""

    @pytest.mark.parametrize("template_dir", PROJECT_CASES)
    def test_parameter_values_preserved_through_round_trip(self, regenerated_project: ImportedProject) -> None:
        """
        Every copied configuration file with FC values, followed by real component-driven regeneration.

        GIVEN: Every copied configuration file with FC values, followed by real component-driven regeneration
        WHEN: Persisted files are compared with an independent interpretation of the configuration steps
        THEN: Exact membership and values match, unchanged calibrations survive, and memory agrees with disk
        """
        assert_project_round_trip(regenerated_project)
