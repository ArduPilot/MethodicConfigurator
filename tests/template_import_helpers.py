#!/usr/bin/env python3

"""
Independent expectations, isolated inputs and workflow assertions for template-import acceptance tests.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import json
import re
from collections.abc import Mapping
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from shutil import copy2
from typing import Any, cast

import pytest
from defusedxml import ElementTree as DET  # noqa: N814

# This helper accompanies acceptance_*.py rather than being a collected test module.
from ardupilot_methodic_configurator import _, __version__
from ardupilot_methodic_configurator import __main__ as application
from ardupilot_methodic_configurator.annotate_params import create_doc_dict
from ardupilot_methodic_configurator.backend_filesystem import LocalFilesystem
from ardupilot_methodic_configurator.backend_flightcontroller import FlightController
from ardupilot_methodic_configurator.battery_cell_voltages import BatteryCell
from ardupilot_methodic_configurator.data_model_par_dict import Par, ParDict
from ardupilot_methodic_configurator.data_model_safe_evaluator import ConfigurationStepEvalError, safe_evaluate
from ardupilot_methodic_configurator.data_model_vehicle_components_validation import (
    BATT_MONITOR_CONNECTION,
    CAN_PORTS,
    FRAME_CLASS_DICT,
    GNSS_RECEIVER_CONNECTION,
    I2C_PORTS,
    RC_PROTOCOLS_DICT,
    SERIAL_PORTS,
    SERVO_FUNCTION_ESC_CONTROL,
)

TEMPLATES_BASE = Path(__file__).resolve().parents[1] / "ardupilot_methodic_configurator" / "vehicle_templates"
EXCLUDED_PARAMETER_FILES = {"00_default.param", "01_ignore_readonly.param"}
ComponentPath = tuple[str, str, str]
ComponentValue = str | int | float
ParameterSnapshot = dict[str, tuple[float, str | None]]


def discover_templates(base_dir: Path = TEMPLATES_BASE) -> list[Path]:
    """Find direct and nested parameter templates, pruning migration directories before traversal."""
    templates: list[Path] = []

    def visit(directory: Path) -> None:
        if directory.name.endswith("_mig"):
            return
        if any(path.is_file() for path in directory.glob("*.param")):
            templates.append(directory)
        for child in sorted(directory.iterdir(), key=lambda path: path.name.lower()):
            if child.is_dir():
                visit(child)

    for vehicle_type in ("ArduCopter", "ArduPlane", "Heli", "Rover"):
        vehicle_dir = base_dir / vehicle_type
        if vehicle_dir.is_dir():
            visit(vehicle_dir)
    return templates


def template_id(template_dir: Path) -> str:
    """Return an unambiguous, platform-independent test id."""
    return template_dir.relative_to(TEMPLATES_BASE).as_posix()


def template_vehicle_type(template_dir: Path) -> str:
    """Use the template root, not a firmware-subdirectory naming heuristic, to identify the vehicle."""
    return template_dir.relative_to(TEMPLATES_BASE).parts[0]


def numbered_parameter_files(directory: Path) -> list[Path]:
    """Enumerate configuration files independently of LocalFilesystem's file-selection implementation."""
    return sorted(
        (
            path
            for path in directory.iterdir()
            if path.is_file()
            and path.suffix == ".param"
            and len(path.name) > 3
            and path.name[:2].isdigit()
            and path.name[2] == "_"
            and path.name not in EXCLUDED_PARAMETER_FILES
        ),
        key=lambda path: path.name,
    )


def parameter_snapshot(parameters: ParDict) -> ParameterSnapshot:
    """Capture values and serialized change reasons without sharing mutable Par instances."""
    return {name: (parameter.value, parameter.comment) for name, parameter in parameters.items()}


def expected_compound(directory: Path) -> ParameterSnapshot:
    """Apply the documented last-numbered-file-wins rule without using compounding or export APIs."""
    expected: ParameterSnapshot = {}
    for path in numbered_parameter_files(directory):
        expected.update(parameter_snapshot(ParDict.from_file(str(path))))
    return expected


def assert_parameter_snapshot(actual: ParDict, expected: Mapping[str, tuple[float, str | None]]) -> None:
    """Require complete parameter membership, six-decimal serialization precision and exact comments."""
    assert set(actual) == set(expected), (
        f"Missing parameters: {sorted(set(expected) - set(actual))}; "
        f"unexpected parameters: {sorted(set(actual) - set(expected))}"
    )
    for name, (value, comment) in expected.items():
        assert actual[name].value == pytest.approx(value, rel=0, abs=0.00000051), name
        # An empty in-memory reason serializes as no comment, not an empty "#".
        assert (actual[name].comment or None) == (comment or None), name


def copy_template_inputs(template_dir: Path, destination: Path) -> None:
    """Copy only immediate configuration inputs, never unrelated logs, caches or nested migration templates."""
    destination.mkdir(parents=True, exist_ok=True)
    for path in template_dir.iterdir():
        if path.is_file() and path.suffix in {".param", ".xml", ".json"}:
            copy2(path, destination / path.name)


def reference_configuration(template_dir: Path, vehicle_type: str) -> dict[str, Any]:
    """Read declarations before project loading or computation can normalize or mutate them."""
    filename = f"configuration_steps_{vehicle_type}.json"
    path = template_dir / filename
    if not path.is_file():
        path = TEMPLATES_BASE.parent / filename
    return cast("dict[str, Any]", json.loads(path.read_text(encoding="utf-8-sig"))["steps"])


def reference_metadata(template_dir: Path, vehicle_type: str) -> dict[str, Any]:
    """Parse immutable local XML independently of LocalFilesystem's mutable documentation dictionary."""
    root = DET.parse(template_dir / "apm.pdef.xml").getroot()
    assert root is not None, "Local parameter XML must contain a root element"
    metadata = create_doc_dict(root, vehicle_type, 105)
    for entry in metadata.values():
        bitmask = entry.get("fields", {}).get("Bitmask", "")
        entry["Bitmask"] = {
            int(key.strip()): label.strip()
            for item in bitmask.split(",")
            if ":" in item
            for key, label in [item.split(":", 1)]
        }
    return metadata


def expected_project_copy(template_dir: Path, source: ParameterSnapshot) -> dict[str, ParDict]:
    """Require all source values, including names absent from the selected empty template, to be imported."""
    expected = {
        path.name: ParDict(
            {
                name: Par(source.get(name, (parameter.value, None))[0])
                for name, parameter in ParDict.from_file(str(path)).items()
            }
        )
        for path in numbered_parameter_files(template_dir)
    }
    represented = {name for parameters in expected.values() for name in parameters}
    remaining = {name: Par(value) for name, (value, _comment) in source.items() if name not in represented}
    if remaining:
        highest = max((int(path.name[:2]) for path in template_dir.glob("*.param") if path.name[:2].isdigit()), default=0)
        assert highest < 99, "An import file must have an available numbered slot"
        expected[f"{highest + 1:02d}_imported_flight_controller_parameters.param"] = ParDict(remaining)
    return expected


def compound_snapshots(files: Mapping[str, ParameterSnapshot]) -> ParameterSnapshot:
    """Compound complete expected output with independent, filename-sorted last-file precedence."""
    compound: ParameterSnapshot = {}
    for filename in sorted(files):
        compound.update(files[filename])
    return compound


def assert_complete_source_round_trip(
    actual: ParDict,
    source: ParameterSnapshot,
    expected_files: Mapping[str, ParameterSnapshot],
    steps: dict[str, Any],
    variables: dict[str, Any],
) -> None:
    """Account for every source name; only independently evaluated explicit deletions can remove it."""
    expected = compound_snapshots(expected_files)
    deleted = {
        name
        for filename in expected_files
        for name, rule in steps.get(filename, {}).get("delete_parameters", {}).items()
        if not rule.get("if") or safe_evaluate(rule["if"], variables)
    }
    assert set(source) - set(expected) <= deleted, "Round-trip reference silently lost source parameters"
    assert_parameter_snapshot(actual, expected)
    for name in source:
        if name not in deleted:
            assert name in actual, f"Source parameter lost during import/regeneration: {name}"


def component_value(data: dict[str, Any], path: ComponentPath) -> ComponentValue:
    """Require each expected component field to exist instead of treating missing fields as matching None."""
    component, section, field = path
    return cast("ComponentValue", data["Components"][component][section][field])


def set_component_value(data: dict[str, Any], path: ComponentPath, value: ComponentValue) -> None:
    """Change an already-present field in test input, failing if the template structure is incomplete."""
    component, section, field = path
    data["Components"][component][section][field] = value


def _battery_expectations(parameters: dict[str, float], original: dict[str, Any]) -> dict[ComponentPath, Any]:
    """Recover pack/cell voltages and monitor settings while retaining independently specified chemistry."""
    expected: dict[ComponentPath, Any] = {}
    specs = original["Components"]["Battery"]["Specifications"]
    chemistry = specs["Chemistry"]
    cells = specs["Number of cells"]
    voltage_parameters = {
        "Volt per cell max": ("Q_M_BAT_VOLT_MAX", "MOT_BAT_VOLT_MAX"),
        "Volt per cell arm": ("BATT_ARM_VOLT",),
        "Volt per cell low": ("BATT_LOW_VOLT",),
        "Volt per cell crit": ("BATT_CRT_VOLT",),
        "Volt per cell min": ("Q_M_BAT_VOLT_MIN", "MOT_BAT_VOLT_MIN"),
    }
    # The template is the independently recorded reference for cell count; voltage values
    # are checked against the supplied pack voltages, not prepopulated component values.
    has_voltage = any(parameters.get(name, 0) > 0 for names in voltage_parameters.values() for name in names)
    if has_voltage:
        assert cells > 0, "A template with battery voltages must record its cell count"
        expected[("Battery", "Specifications", "Number of cells")] = cells
        for field, names in voltage_parameters.items():
            name = next((name for name in names if name in parameters), None)
            if name is not None:
                voltage = round(parameters[name] / cells, 4)
                if BatteryCell.limit_min_voltage(chemistry) <= voltage <= BatteryCell.limit_max_voltage(chemistry):
                    expected[("Battery", "Specifications", field)] = voltage
    elif cells == 0:
        for field in voltage_parameters:
            expected[("Battery", "Specifications", field)] = 0
    if parameters.get("BATT_CAPACITY", 0) > 0:
        expected[("Battery", "Specifications", "Capacity mAh")] = int(parameters["BATT_CAPACITY"])
    if "BATT_MONITOR" in parameters:
        monitor = BATT_MONITOR_CONNECTION[str(int(parameters["BATT_MONITOR"]))]
        connection = monitor["type"]
        if isinstance(connection, tuple):
            connection = (
                connection[int(parameters.get("BATT_I2C_BUS", 0))] if set(connection) <= set(I2C_PORTS) else connection[0]
            )
        protocol = monitor["protocol"]
        expected[("Battery Monitor", "FC Connection", "Type")] = connection
        expected[("Battery Monitor", "FC Connection", "Protocol")] = protocol[0] if isinstance(protocol, tuple) else protocol

    return expected


def _connection_expectations(parameters: dict[str, float]) -> dict[ComponentPath, Any]:
    """Recover GNSS/RC/telemetry connections only when the supplied parameters identify them."""
    expected: dict[ComponentPath, Any] = {}

    gps_name = "GPS1_TYPE" if "GPS1_TYPE" in parameters else "GPS_TYPE"
    if gps_name in parameters:
        gps = GNSS_RECEIVER_CONNECTION[str(int(parameters[gps_name]))]
        ports = gps["type"]
        ports = (ports,) if isinstance(ports, str) else ports
        expected[("GNSS Receiver", "FC Connection", "Protocol")] = gps["protocol"]
        if ports == ("None",):
            expected[("GNSS Receiver", "FC Connection", "Type")] = "None"
        elif any(port in CAN_PORTS for port in ports):
            can_port = next(
                (
                    f"CAN{bus}"
                    for bus in (1, 2)
                    if parameters.get(f"CAN_D{bus}_PROTOCOL") == 1 and parameters.get(f"CAN_P{bus}_DRIVER") == 1
                ),
                "None",
            )
            expected[("GNSS Receiver", "FC Connection", "Type")] = can_port
    gps_port = next((port for port in SERIAL_PORTS if parameters.get(f"{port}_PROTOCOL") == 5), None)
    if gps_port and ("GNSS Receiver", "FC Connection", "Type") not in expected:
        expected[("GNSS Receiver", "FC Connection", "Type")] = gps_port

    rc_mask = int(parameters.get("RC_PROTOCOLS", 0))
    if rc_mask > 0 and rc_mask & (rc_mask - 1) == 0:
        expected[("RC Receiver", "FC Connection", "Protocol")] = RC_PROTOCOLS_DICT[str(rc_mask)]["protocol"]
    rc_port = next((port for port in SERIAL_PORTS if parameters.get(f"{port}_PROTOCOL") == 23), None)
    if rc_port:
        expected[("RC Receiver", "FC Connection", "Type")] = rc_port
    telemetry_port = next(
        (
            (port, {1: "MAVLink1", 2: "MAVLink2"}[int(parameters[f"{port}_PROTOCOL"])])
            for port in SERIAL_PORTS
            if parameters.get(f"{port}_PROTOCOL") in {1, 2}
        ),
        None,
    )
    if telemetry_port:
        expected[("Telemetry", "FC Connection", "Type")] = telemetry_port[0]
        expected[("Telemetry", "FC Connection", "Protocol")] = telemetry_port[1]

    return expected


def _esc_expectations(parameters: dict[str, float], metadata: dict[str, Any]) -> dict[ComponentPath, Any]:
    """Recover ESC control, distinct telemetry wiring, and available motor-pole counts."""
    expected: dict[ComponentPath, Any] = {}

    # Serial ESC control wins over PWM; telemetry-only serial protocols must not do so.
    serial_esc = next(
        (
            (port, {38: "FETtecOneWire", 39: "Torqeedo", 41: "CoDevESC"}[int(parameters[f"{port}_PROTOCOL"])])
            for port in SERIAL_PORTS
            if parameters.get(f"{port}_PROTOCOL") in {38, 39, 41}
        ),
        None,
    )
    if serial_esc:
        expected[("ESC", "FC->ESC Connection", "Type")] = serial_esc[0]
        expected[("ESC", "FC->ESC Connection", "Protocol")] = serial_esc[1]
    elif "MOT_PWM_TYPE" in parameters:
        expected[("ESC", "FC->ESC Connection", "Type")] = (
            "AIO"
            if any(parameters.get(f"SERVO{output}_FUNCTION", 0) in SERVO_FUNCTION_ESC_CONTROL for output in range(9, 15))
            else "Main Out"
        )
        expected[("ESC", "FC->ESC Connection", "Protocol")] = metadata["MOT_PWM_TYPE"]["values"][
            str(int(parameters["MOT_PWM_TYPE"]))
        ]
    pwm_protocol = expected.get(("ESC", "FC->ESC Connection", "Protocol"), "")
    pole_name = (
        "SERVO_BLH_POLES"
        if pwm_protocol.startswith("DShot")
        else "SERVO_FTW_POLES"
        if parameters.get("SERVO_FTW_MASK")
        else "ESC_HW_POLES"
    )
    if "MOT_PWM_TYPE" in parameters and parameters.get(pole_name, 0) > 0:
        expected[("Motors", "Specifications", "Poles")] = int(parameters[pole_name])
    serial_feedback = next(
        (
            (port, {16: "ESC Telemetry", 28: "Scripting"}[int(parameters[f"{port}_PROTOCOL"])])
            for port in SERIAL_PORTS
            if parameters.get(f"{port}_PROTOCOL") in {16, 28}
        ),
        None,
    )
    if serial_esc or serial_feedback:
        feedback = serial_esc or serial_feedback
        assert feedback is not None
        expected[("ESC", "ESC->FC Telemetry", "Type")] = feedback[0]
        expected[("ESC", "ESC->FC Telemetry", "Protocol")] = feedback[1]
    elif pwm_protocol:
        expected[("ESC", "ESC->FC Telemetry", "Type")] = (
            expected[("ESC", "FC->ESC Connection", "Type")] if pwm_protocol.startswith("DShot") else "None"
        )
        expected[("ESC", "ESC->FC Telemetry", "Protocol")] = "BDShotOnly" if pwm_protocol.startswith("DShot") else "None"
    return expected


def inference_expectations(
    parameters: dict[str, float], original: dict[str, Any], metadata: dict[str, Any]
) -> dict[ComponentPath, Any]:
    """
    Describe fields recoverable from supplied parameters, independently of the inference methods.

    Chemistry is explicit context: pack voltage alone cannot uniquely identify it. Ambiguous RC
    protocols, missing motor pole counts, absent serial ports and unavailable voltage settings
    are not counted as successful inference. Their original values must instead be preserved.
    """
    expected = {
        **_battery_expectations(parameters, original),
        **_connection_expectations(parameters),
        **_esc_expectations(parameters, metadata),
    }
    vehicle_type = original["Components"]["Flight Controller"]["Firmware"]["Type"]
    frame_parameter = "Q_FRAME_CLASS" if vehicle_type == "ArduPlane" else "FRAME_CLASS"
    if frame_parameter in parameters:
        expected[("Frame", "Specifications", "Frame class")] = FRAME_CLASS_DICT[vehicle_type][int(parameters[frame_parameter])]
    elif vehicle_type == "ArduPlane" and not parameters.get("Q_ENABLE", 0):
        expected[("Frame", "Specifications", "Frame class")] = "Undefined"
    assert expected, "Every eligible template must exercise at least one recoverable component field"
    return expected


def poisoned_component_input(original: dict[str, Any], expected: dict[ComponentPath, Any]) -> dict[str, Any]:
    """Keep non-inferable context, but replace every recoverable value with a different sentinel."""
    poisoned = deepcopy(original)
    for path, value in expected.items():
        set_component_value(poisoned, path, -999 if isinstance(value, (int, float)) else "__not_inferred__")
    return poisoned


def assert_inference_result(actual: dict[str, Any], expected: dict[ComponentPath, Any]) -> None:
    """Check every recoverable field, including membership, without percentages or missing-value fallbacks."""
    for path, value in expected.items():
        actual_value = component_value(actual, path)
        if isinstance(value, (int, float)):
            assert actual_value == pytest.approx(value, rel=0, abs=0.00005), path
        else:
            assert actual_value == value, path


def assert_uninferred_context(
    actual: dict[str, Any], original: dict[str, Any], inferred_paths: dict[ComponentPath, Any]
) -> None:
    """Require every component, section and uninferred leaf to survive, not merely product metadata."""
    assert set(actual) == set(original)
    assert set(actual["Components"]) == set(original["Components"])
    for component, sections in original["Components"].items():
        assert set(actual["Components"][component]) == set(sections), component
        for section, fields in sections.items():
            result = actual["Components"][component][section]
            if not isinstance(fields, dict):
                assert result == fields, (component, section)
                continue
            assert set(result) == set(fields), (component, section)
            for field, value in fields.items():
                if (component, section, field) not in inferred_paths:
                    assert result[field] == value, (component, section, field)


def _computed_rule(name: str, rule: dict[str, Any], kind: str, context: dict[str, Any]) -> tuple[float, str | None] | None:
    """Resolve one declared value/reason without using application's compute or merge methods."""
    try:
        result = safe_evaluate(str(rule["New Value"]), context)
    except ConfigurationStepEvalError as error:
        # Sparse parameter files can omit EK3_PRIMARY, and genuinely empty Copter
        # templates have no propeller size. These are the only unavailable inputs
        # accepted by this oracle; arbitrary malformed rules must fail the test.
        propeller_diameter = context["vehicle_components"]["Propellers"]["Specifications"]["Diameter_inches"]
        cause = error.__cause__
        missing_primary = (
            isinstance(cause, KeyError) and str(cause) == repr("EK3_PRIMARY") and "EK3_PRIMARY" not in context["fc_parameters"]
        )
        empty_propeller = (
            propeller_diameter == 0
            and "Diameter_inches" in str(rule["New Value"])
            and isinstance(cause, (ZeroDivisionError, ValueError))
        )
        if kind == "derived_parameters" and (missing_primary or empty_propeller):
            return None
        raise
    if isinstance(result, str):
        metadata = context["doc_dict"][name]
        if metadata["values"]:
            matches = [code for code, label in metadata["values"].items() if label == result]
        else:
            matches = [2**code for code, label in metadata["Bitmask"].items() if label == result]
        if not matches:
            # A serial ESC protocol (e.g. FETtecOneWire) has no MOT_PWM_TYPE enum.
            # Such an advisory derived entry must preserve the copied FC value.
            assert kind == "derived_parameters", f"Unexpected unresolvable {kind} value for {name}: {result}"
            assert name == "MOT_PWM_TYPE", f"Unexpected unresolvable enum for {name}: {result}"
            assert result in {"FETtecOneWire", "Torqeedo", "CoDevESC"}, f"Unexpected serial ESC protocol: {result}"
            return None
        result = matches[0]
    reason = rule.get("Change Reason", "")
    if " if " in reason and " else " in reason:
        reason = str(safe_evaluate(reason, context))
    return float(result), _(reason) or None


def expected_regenerated_parameters(
    original_files: dict[str, ParDict], steps: dict[str, Any], variables: dict[str, Any], fc_parameters: dict[str, float]
) -> dict[str, ParameterSnapshot]:
    """
    Interpret the configuration declarations as an oracle for final file membership and values.

    Only expression evaluation is shared with the application (tested separately); calculation,
    merging, deletion, serialization and file persistence are all exercised by the acceptance test.
    """
    expected = {filename: parameter_snapshot(params) for filename, params in original_files.items()}
    context = {**variables, "fc_parameters": fc_parameters}
    for filename, parameters in expected.items():
        step = steps.get(filename, {})
        for key in ("forced_parameters", "derived_parameters", "add_parameters"):
            for name, rule in step.get(key, {}).items():
                if rule.get("if") and not safe_evaluate(rule["if"], context):
                    continue
                if key != "add_parameters" and name not in fc_parameters:
                    continue
                if key == "add_parameters" and name in parameters:
                    continue
                if name in parameters and (parameters[name][1] or "").startswith("@manual_override"):
                    continue
                if "New Value" in rule:
                    result = _computed_rule(name, rule, key, context)
                    if result is not None:
                        parameters[name] = result
                elif key == "add_parameters" and name in fc_parameters:
                    parameters[name] = (
                        fc_parameters[name],
                        rule.get("Change Reason", _("Copied from the connected flight controller")) or None,
                    )
        for name, rule in step.get("delete_parameters", {}).items():
            if not rule.get("if") or safe_evaluate(rule["if"], context):
                parameters.pop(name, None)
    return expected


@dataclass
class ImportedProject:  # pylint: disable=too-many-instance-attributes
    """Per-test project inputs and independent reference snapshots."""

    filesystem: LocalFilesystem
    directory: Path
    fc_parameters: dict[str, float]
    copied_parameters: dict[str, ParDict]
    expected_components: dict[ComponentPath, Any]
    original_components: dict[str, Any]
    source_parameters: ParameterSnapshot
    reference_steps: dict[str, Any]
    reference_variables: dict[str, Any]
    expected_files: dict[str, ParameterSnapshot]


@dataclass
class OrchestratedProject:
    """A real manager/editor workflow, separate from the manually inferred domain fixture."""

    state: application.ApplicationState
    project: ImportedProject
    parameter_bytes_before_setup: dict[str, bytes]
    warnings: list[tuple[str, str]]


def seed_offline_parameter_metadata(
    metadata_source_dir: Path, new_vehicle_dir: str | Path, vehicle_type: str, firmware_version: str
) -> None:
    """Copy cached parameter metadata into a generated project for offline acceptance tests."""
    metadata_source = metadata_source_dir / "apm.pdef.xml"
    metadata_target = Path(new_vehicle_dir) / "apm.pdef.xml"
    metadata_to_validate = metadata_target if metadata_target.exists() else metadata_source
    if not metadata_to_validate.is_file():
        msg = f"Offline parameter metadata not found: {metadata_to_validate}"
        raise FileNotFoundError(msg)
    metadata_vehicle = {"ArduCopter": "Copter", "ArduPlane": "Plane"}.get(vehicle_type)
    if metadata_vehicle and firmware_version:
        metadata_text = metadata_to_validate.read_text(encoding="utf-8")
        metadata_match = re.search(rf"Generated from git tag {metadata_vehicle}-(\d+\.\d+\.\d+)", metadata_text)
        expected_release = firmware_version.split(" ", maxsplit=1)[0]
        if metadata_match and metadata_match.group(1) != expected_release:
            msg = f"Offline parameter metadata {metadata_to_validate} is incompatible with {vehicle_type} {firmware_version}"
            raise ValueError(msg)
    if metadata_target.exists():
        return
    copy2(metadata_source, metadata_target)


def prepare_orchestration_reference(  # pylint: disable=too-many-locals
    template_dir: Path, empty_template: Path, isolated_empty: Path, *, infer_components: bool
) -> ImportedProject:
    """Capture independent expectations and prepare isolated inputs before production initialization."""
    vehicle_type = template_vehicle_type(template_dir)
    source = expected_compound(template_dir)
    copied = expected_project_copy(empty_template, source)
    steps = reference_configuration(empty_template, vehicle_type)
    metadata = reference_metadata(empty_template, vehicle_type)
    original = json.loads((template_dir / "vehicle_components.json").read_text(encoding="utf-8"))
    firmware = json.loads((empty_template / "vehicle_components.json").read_text(encoding="utf-8"))["Components"][
        "Flight Controller"
    ]["Firmware"]
    original["Components"]["Flight Controller"]["Firmware"] = deepcopy(firmware)
    inferred = inference_expectations({name: value for name, (value, _reason) in source.items()}, original, metadata)
    if infer_components:
        input_components = poisoned_component_input(original, inferred)
        expected_components = inferred
    else:
        # A valid, deliberately different user specification proves inference remains optional.
        original["Components"]["Battery"]["Specifications"]["Capacity mAh"] = 1200
        input_components = deepcopy(original)
        expected_components = {path: component_value(original, path) for path in inferred}
    copy_template_inputs(empty_template, isolated_empty)
    (isolated_empty / "vehicle_components.json").write_text(json.dumps(input_components), encoding="utf-8")
    original["Program version"] = __version__
    original["Configuration template"] = isolated_empty.name
    reference_components = deepcopy(original)
    for path, value in expected_components.items():
        set_component_value(reference_components, path, value)
    variables = {
        "vehicle_components": reference_components["Components"],
        "doc_dict": metadata,
        "fc_parameters": {name: value for name, (value, _reason) in source.items()},
    }
    filesystem = LocalFilesystem(
        str(isolated_empty), vehicle_type, "", allow_editing_template_files=False, save_component_to_system_templates=False
    )
    return ImportedProject(
        filesystem=filesystem,
        directory=isolated_empty,
        fc_parameters=dict(variables["fc_parameters"]),
        copied_parameters=copied,
        expected_components=expected_components,
        original_components=original,
        source_parameters=source,
        reference_steps=steps,
        reference_variables=variables,
        expected_files={filename: parameter_snapshot(parameters) for filename, parameters in copied.items()},
    )


def assert_project_round_trip(project: ImportedProject) -> None:
    """Check every persisted file and the complete source against references captured before execution."""
    filesystem = project.filesystem
    expected = project.expected_files
    output_files = numbered_parameter_files(project.directory)
    assert {path.name for path in output_files} == set(expected)
    compared = 0
    for path in output_files:
        actual = ParDict.from_file(str(path))
        values = expected[path.name]
        assert_parameter_snapshot(actual, values)
        compared += len(values)
        assert_parameter_snapshot(actual, parameter_snapshot(filesystem.file_parameters[path.name]))
    assert compared > 0
    compound, _ = filesystem.compound_params()
    assert_complete_source_round_trip(
        compound, project.source_parameters, expected, project.reference_steps, project.reference_variables
    )
    # A literal cross-stage invariant, independent even of the declaration oracle.
    if project.fc_parameters.get("BATT_CAPACITY", 0) > 0:
        assert compound["BATT_CAPACITY"].value == int(project.fc_parameters["BATT_CAPACITY"])


def assert_persisted_components(project: ImportedProject, controller: FlightController) -> None:
    """Verify the real component editor saved the reference state without changing source FC values."""
    filesystem = project.filesystem
    persisted = json.loads((project.directory / "vehicle_components.json").read_text(encoding="utf-8"))
    assert_inference_result(persisted, project.expected_components)
    assert_uninferred_context(persisted, project.original_components, project.expected_components)
    assert persisted["Program version"] == __version__
    assert persisted["Configuration template"] == project.original_components["Configuration template"]
    assert filesystem.vehicle_components_fs.data == persisted
    assert filesystem.get_eval_variables()["vehicle_components"] == persisted["Components"]
    assert controller.fc_parameters == pytest.approx(project.fc_parameters, rel=0, abs=0.00000051)
