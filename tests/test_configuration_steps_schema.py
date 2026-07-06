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

import pytest
from jsonschema import ValidationError, exceptions, validate, validators

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
