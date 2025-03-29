#!/usr/bin/env python3

"""
Validates all vehicle_components.json files against a JSON schema.

Finds all vehicle_components.json files in the project and its subdirectories, and validates them
against the JSON schema defined in "ardupilot_methodic_configurator/vehicle_components_schema.json".

This file is part of Ardupilot methodic configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2025 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import json
import os

import pytest
from jsonschema import ValidationError, exceptions, validate, validators

# Path to the schema file
SCHEMA_FILE_PATH = os.path.join("ardupilot_methodic_configurator", "vehicle_components_schema.json")

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


def find_json_files(directory) -> list[str]:
    """Find all vehicle_components.json files in the specified directory and its subdirectories."""
    json_files = []
    for root, _, files in os.walk(directory):
        for file in files:
            if file == "vehicle_components.json":
                json_files.append(os.path.join(root, file))  # noqa: PERF401
    return json_files


@pytest.mark.parametrize("json_file", find_json_files("."))
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


# pylint: enable=duplicate-code
