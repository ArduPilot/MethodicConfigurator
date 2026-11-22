#!/usr/bin/env python3

"""
Validates published vehicle template component files against a JSON schema.

Finds vehicle_components.json files in the packaged vehicle templates, and validates them
against the JSON schema defined in "ardupilot_methodic_configurator/vehicle_components_schema.json".

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import json
from pathlib import Path

import pytest
from jsonschema import ValidationError, exceptions, validate, validators

# Path to the schema file
REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_FILE_PATH = REPOSITORY_ROOT / "ardupilot_methodic_configurator" / "vehicle_components_schema.json"

# pylint: disable=duplicate-code
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


def find_template_component_files(repository_root: Path) -> list[Path]:
    """Validate shipped templates without collecting temporary projects or test fixtures."""
    template_root = repository_root / "ardupilot_methodic_configurator" / "vehicle_templates"
    return sorted(template_root.rglob("vehicle_components.json"))


def test_schema_discovery_includes_nested_templates_and_excludes_scratch_projects(tmp_path: Path) -> None:
    """GIVEN a published template and scratch files, WHEN collecting schemas, THEN validate only the template."""
    template = tmp_path / "ardupilot_methodic_configurator" / "vehicle_templates" / "ArduCopter" / "vehicle" / "4.7.x"
    scratch = tmp_path / ".pytest-codex-verify-final" / "test_user_can_compound_uncached"
    for directory in (template, scratch):
        directory.mkdir(parents=True)
        (directory / "vehicle_components.json").write_text("{}", encoding="utf-8")

    assert find_template_component_files(tmp_path) == [template / "vehicle_components.json"]


@pytest.mark.parametrize("json_file", find_template_component_files(REPOSITORY_ROOT))
def test_json_schema(json_file: Path) -> None:
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


# pylint: enable=duplicate-code
