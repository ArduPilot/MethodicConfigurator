#!/usr/bin/env python3

"""
Validates all configuration_steps_*.json files against a JSON schema.

Finds all configuration_steps_*.json files in the project and its subdirectories, and validates them
against the JSON schema defined in "ardupilot_methodic_configurator/configuration_steps_schema.json".

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import fnmatch
import json
import os
import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest
from jsonschema import ValidationError, exceptions, validate, validators

from ardupilot_methodic_configurator.backend_filesystem_configuration_steps import ConfigurationSteps

# Path to the schema file
SCHEMA_FILE_PATH = os.path.join("ardupilot_methodic_configurator", "configuration_steps_schema.json")

# Load the schema
with open(SCHEMA_FILE_PATH, encoding="utf-8") as schema_file:
    schema = json.load(schema_file)


def test_schema_validity() -> None:
    """Test that the schema itself is a valid JSON Schema document."""
    try:
        # Validate the schema against the JSON Schema meta-schema
        # This checks if our schema is a valid JSON Schema
        validators.validator_for(schema).check_schema(schema)
    except exceptions.SchemaError as e:
        pytest.fail(f"The schema file {SCHEMA_FILE_PATH} is not a valid JSON Schema: {e}")


def test_related_bin_messages_schema_rejects_malformed_entries() -> None:
    """Ensure related_bin_messages entries require both name and required fields."""
    valid_document = {
        "steps": {
            "01_demo.param": {
                "why": "demo",
                "why_now": "demo",
                "blog_text": "demo",
                "blog_url": "https://example.com",
                "wiki_text": "demo",
                "wiki_url": "https://example.com",
                "external_tool_text": "demo",
                "external_tool_url": "https://example.com",
                "mandatory_text": "100% mandatory (0% optional)",
                "related_bin_messages": {
                    "GPS": {
                        "name": "GPS",
                        "required": True,
                    }
                },
            }
        }
    }
    validate(instance=valid_document, schema=schema)

    invalid_document_missing_required = {
        "steps": {
            "01_demo.param": {
                "why": "demo",
                "why_now": "demo",
                "blog_text": "demo",
                "blog_url": "https://example.com",
                "wiki_text": "demo",
                "wiki_url": "https://example.com",
                "external_tool_text": "demo",
                "external_tool_url": "https://example.com",
                "mandatory_text": "100% mandatory (0% optional)",
                "related_bin_messages": {
                    "GPS": {
                        "name": "GPS",
                    }
                },
            }
        }
    }

    with pytest.raises(ValidationError, match=r"'required' is a required property"):
        validate(instance=invalid_document_missing_required, schema=schema)

    invalid_document_extra_property = {
        "steps": {
            "01_demo.param": {
                "why": "demo",
                "why_now": "demo",
                "blog_text": "demo",
                "blog_url": "https://example.com",
                "wiki_text": "demo",
                "wiki_url": "https://example.com",
                "external_tool_text": "demo",
                "external_tool_url": "https://example.com",
                "mandatory_text": "100% mandatory (0% optional)",
                "related_bin_messages": {
                    "GPS": {
                        "name": "GPS",
                        "required": True,
                        "unexpected": "boom",
                    }
                },
            }
        }
    }

    with pytest.raises(ValidationError, match=r"Additional properties are not allowed"):
        validate(instance=invalid_document_extra_property, schema=schema)


def test_arducopter_configuration_steps_bin_messages_each_have_a_required_message() -> None:
    """Ensure every step with related_bin_messages declares at least one required message."""
    arducopter_file = Path(__file__).parent.parent / "ardupilot_methodic_configurator" / "configuration_steps_ArduCopter.json"
    with open(arducopter_file, encoding="utf-8") as file:
        config = json.load(file)

    steps = config["steps"]
    steps_with_mappings = {step_name: step for step_name, step in steps.items() if step.get("related_bin_messages")}

    assert steps_with_mappings, "No configuration steps have related_bin_messages"

    for step_name, step in steps_with_mappings.items():
        messages = step["related_bin_messages"]
        has_required = any(msg_info.get("required", False) for msg_info in messages.values())
        assert has_required, f"Step '{step_name}' has no required message in related_bin_messages"


@pytest.mark.parametrize("vehicle_type", ["ArduCopter", "ArduPlane", "Heli", "Rover"])
def test_serial_rc_receiver_derives_rcin_protocol_for_each_vehicle_type(vehicle_type: str) -> None:
    """Selecting a serial RC Receiver connection assigns RCIN to every supported vehicle type."""
    configuration_steps_file = (
        Path(__file__).parent.parent / "ardupilot_methodic_configurator" / f"configuration_steps_{vehicle_type}.json"
    )
    with open(configuration_steps_file, encoding="utf-8") as file:
        config = json.load(file)

    step_file = "06_remote_controller_receiver.param"
    step_info = config["steps"][step_file]
    config_steps = ConfigurationSteps("vehicle_dir", vehicle_type)

    for serial_port in range(1, 10):
        serial_name = f"SERIAL{serial_port}"
        variables = {
            "vehicle_components": {"RC Receiver": {"FC Connection": {"Type": serial_name, "Protocol": "CRSF"}}},
            "doc_dict": {"RC_PROTOCOLS": {"values": {}, "Bitmask": {9: "CRSF"}}},
        }

        error = config_steps.compute_parameters(step_file, step_info, "derived", variables)

        assert error == ""
        assert config_steps.derived_parameters[step_file][f"{serial_name}_PROTOCOL"].value == 23.0

    non_serial_variables = {
        "vehicle_components": {"RC Receiver": {"FC Connection": {"Type": "RCin/SBUS", "Protocol": "CRSF"}}},
        "doc_dict": {"RC_PROTOCOLS": {"values": {}, "Bitmask": {9: "CRSF"}}},
    }
    error = config_steps.compute_parameters(step_file, step_info, "derived", non_serial_variables)

    assert error == ""
    assert not any(
        name.startswith("SERIAL") and name.endswith("_PROTOCOL") for name in config_steps.derived_parameters[step_file]
    )


def test_arduplane_configuration_steps_do_not_write_copter_only_parameters() -> None:
    """ArduPlane configuration steps must use QuadPlane Q_A_, Q_M_, and Q_P_ parameter groups."""
    configuration_steps_file = (
        Path(__file__).parent.parent / "ardupilot_methodic_configurator" / "configuration_steps_ArduPlane.json"
    )
    with open(configuration_steps_file, encoding="utf-8") as file:
        config = json.load(file)

    copter_only_parameter_names = {
        parameter_name
        for step in config["steps"].values()
        for section in ("add_parameters", "delete_parameters", "derived_parameters", "forced_parameters")
        for parameter_name in step.get(section, {})
        if parameter_name.startswith(("ATC_", "MOT_", "PSC_"))
    }

    assert not copter_only_parameter_names


@pytest.mark.parametrize(
    ("firmware_version", "expected_parameter_names"),
    [
        ("4.6.3", {"Q_A_THR_MIX_MAN", "Q_P_ACCZ_I", "Q_P_ACCZ_P"}),
        ("4.7.0", {"Q_A_THR_MIX_MAN", "Q_P_D_ACC_I", "Q_P_D_ACC_P"}),
    ],
)
def test_arduplane_throttle_controller_uses_quadplane_parameters(
    firmware_version: str, expected_parameter_names: set[str]
) -> None:
    """Throttle-controller gains target the matching QuadPlane parameters for each firmware generation."""
    configuration_steps_file = (
        Path(__file__).parent.parent / "ardupilot_methodic_configurator" / "configuration_steps_ArduPlane.json"
    )
    with open(configuration_steps_file, encoding="utf-8") as file:
        config = json.load(file)

    config_steps = ConfigurationSteps("vehicle_dir", "ArduPlane")
    throttle_step_file = "24_throttle_controller.param"
    throttle_step = config["steps"][throttle_step_file]
    variables = {
        "fc_parameters": {"Q_M_THST_HOVER": 0.2},
        "vehicle_components": {"Flight Controller": {"Firmware": {"Version": firmware_version}}},
    }
    error = config_steps.compute_parameters(throttle_step_file, throttle_step, "derived", variables)

    assert error == ""
    assert set(config_steps.derived_parameters[throttle_step_file]) == expected_parameter_names


def test_arduplane_quadplane_only_steps_skip_missing_hover_thrust_without_warnings() -> None:
    """QuadPlane-only steps must not warn while evaluating a fixed-wing Plane without Q_M_THST_HOVER."""
    configuration_steps_file = (
        Path(__file__).parent.parent / "ardupilot_methodic_configurator" / "configuration_steps_ArduPlane.json"
    )
    with open(configuration_steps_file, encoding="utf-8") as file:
        config = json.load(file)

    fixed_wing_variables = {
        "fc_parameters": {},
        "vehicle_components": {"Flight Controller": {"Firmware": {"Version": "4.7.0"}}},
    }
    with patch("ardupilot_methodic_configurator.backend_filesystem_configuration_steps.logging_warning") as logging_warning:
        config_steps = ConfigurationSteps("vehicle_dir", "ArduPlane")
        error = config_steps.compute_parameters(
            "24_throttle_controller.param",
            config["steps"]["24_throttle_controller.param"],
            "derived",
            fixed_wing_variables,
        )
        motor_notch_error = config_steps.compute_parameters(
            "22_motor_notch_logging.param",
            config["steps"]["22_motor_notch_logging.param"],
            "forced",
            fixed_wing_variables,
        )

    assert error == ""
    assert motor_notch_error == ""
    logging_warning.assert_not_called()


@pytest.mark.parametrize(
    ("template_name", "expected_parameter_names"),
    [
        (
            "normal_plane",
            {"Q_A_THR_MIX_MAN", "Q_P_ACCZ_I", "Q_P_ACCZ_P"},
        ),
        (
            "empty_4.7.x",
            {"Q_A_THR_MIX_MAN", "Q_P_D_ACC_I", "Q_P_D_ACC_P"},
        ),
    ],
)
def test_arduplane_throttle_controller_templates_use_quadplane_parameters(
    template_name: str, expected_parameter_names: set[str]
) -> None:
    """Plane throttle-controller templates use the parameter spelling matching their firmware generation."""
    parameter_file = (
        Path(__file__).parent.parent
        / "ardupilot_methodic_configurator"
        / "vehicle_templates"
        / "ArduPlane"
        / template_name
        / "24_throttle_controller.param"
    )
    parameter_names = {line.partition(",")[0] for line in parameter_file.read_text(encoding="utf-8").splitlines() if line}

    assert parameter_names == expected_parameter_names


def find_json_files(directory) -> list[str]:
    """Find all configuration_steps_*.json files in the specified directory and its subdirectories."""
    json_files = []
    for root, _, files in os.walk(directory):
        for file in files:
            if (
                file.startswith("configuration_steps_")
                and file.endswith(".json")
                and file != "configuration_steps_schema.json"
            ):
                json_files.append(os.path.join(root, file))  # noqa: PERF401
    return json_files


def git_tracked_json_files() -> list[str]:
    """Find all git tracked configuration_steps_*.json files in the repository."""
    try:
        files = subprocess.check_output(["git", "ls-files"], encoding="utf-8").splitlines()  # noqa: S607
        return [
            f
            for f in files
            if fnmatch.fnmatch(os.path.basename(f), "configuration_steps_*.json")
            and os.path.basename(f) != "configuration_steps_schema.json"
        ]
    except (subprocess.CalledProcessError, FileNotFoundError):
        return find_json_files(".")


@pytest.mark.parametrize("json_file", git_tracked_json_files())
def test_json_schema(json_file) -> None:
    """Test that the JSON files conform to the predefined schema."""
    with open(json_file, encoding="utf-8") as file:
        json_data = json.load(file)

    # Validate the JSON data against the schema
    try:
        validate(instance=json_data, schema=schema)
    except ValidationError as e:
        error_type = e.validator  # This gives the type of validation (for example, 'required', 'type', etc.)
        error_path = e.path  # This gives the path in the JSON that caused the error
        pytest.fail(f"Validation error in {json_file} - Error Type: {error_type}, Path: {error_path}")
        # pytest.fail(f"Validation error in {json_file}: {e.message}")
