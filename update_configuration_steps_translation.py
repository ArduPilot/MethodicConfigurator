#!/usr/bin/env python3

"""
Extract translatable strings from all configuration_steps_*.json files to pygettext compatible format.

It also extracts all description strings from the configuration_steps_schema.json file.
It creates a configuration_steps_strings.py python file that pygettext can process.

This file is part of Ardupilot methodic configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2025 Amilcar Lucas

SPDX-License-Identifier: GPL-3.0-or-later
"""

import glob
import json
import logging
import os
from datetime import datetime
from typing import Any, Union

# Set up a proper logger
logger = logging.getLogger(__name__)


def process_configuration_steps(text_fields: list[str], extracted_strings: dict[str, set[str]], data: dict[str, Any]) -> None:
    for step_data in data["steps"].values():
        # Extract standard text fields
        for field in text_fields:
            if field in step_data and isinstance(step_data[field], str) and step_data[field].strip():
                extracted_strings[field].add(step_data[field])

        # Special handling for jump_possible messages
        if "jump_possible" in step_data:
            for jump_message in step_data["jump_possible"].values():
                if isinstance(jump_message, str) and jump_message.strip():
                    extracted_strings["jump_messages"].add(jump_message)

        # Extract change reasons from forced_parameters and derived_parameters
        for param_type in ["forced_parameters", "derived_parameters"]:
            if param_type in step_data:
                for param_data in step_data[param_type].values():
                    if "Change Reason" in param_data and isinstance(param_data["Change Reason"], str):
                        extracted_strings["change_reasons"] = extracted_strings.get("change_reasons", set())
                        extracted_strings["change_reasons"].add(param_data["Change Reason"])


def extract_strings_from_config_steps(config_file: str) -> dict[str, set[str]]:
    """
    Extract translatable strings from a configuration steps file.

    Args:
        config_file: Path to the configuration steps file

    Returns:
        Dictionary with string categories and their unique values

    """
    # Fields to extract from each step
    text_fields = ["why", "why_now", "blog_text", "wiki_text", "external_tool_text"]

    # Store unique strings by category
    extracted_strings: dict[str, set[str]] = {field: set() for field in text_fields}
    extracted_strings["jump_messages"] = set()  # Special handling for jump_possible messages

    try:
        with open(config_file, encoding="utf-8") as f:
            data = json.load(f)

        # Process each configuration step
        if "steps" in data:
            process_configuration_steps(text_fields, extracted_strings, data)

        # Process phases if present
        if "phases" in data:
            for phase_name, phase_data in data["phases"].items():
                if phase_name and isinstance(phase_name, str):
                    extracted_strings["phase_names"] = extracted_strings.get("phase_names", set())
                    extracted_strings["phase_names"].add(phase_name)
                if "description" in phase_data and isinstance(phase_data["description"], str):
                    extracted_strings["phase_descriptions"] = extracted_strings.get("phase_descriptions", set())
                    extracted_strings["phase_descriptions"].add(phase_data["description"])

    except json.JSONDecodeError as e:
        logger.error("Error parsing %s: %s", config_file, e)
    except Exception as e:  # pylint: disable=broad-exception-caught
        logger.error("Error processing %s: %s", config_file, e)

    return extracted_strings


def gather_all_translatable_strings(config_dir: str) -> dict[str, list[str]]:
    """
    Scan all configuration_steps_*.json files and extract unique translatable strings.

    Args:
        config_dir: Directory containing configuration steps files

    Returns:
        Dictionary with string categories and sorted lists of unique strings

    """
    # Find all configuration_steps_*.json files
    config_files = glob.glob(os.path.join(config_dir, "configuration_steps_*.json"))

    # Collect all strings from all files
    all_strings: dict[str, set[str]] = {}

    for config_file in config_files:
        extracted_strings = extract_strings_from_config_steps(config_file)

        # Merge extracted strings into all_strings
        for category, strings in extracted_strings.items():
            if category not in all_strings:
                all_strings[category] = set()
            all_strings[category].update(strings)

    # Convert sets to sorted lists
    return {category: sorted(strings) for category, strings in all_strings.items()}


# pylint: disable=duplicate-code
def extract_descriptions_from_schema(schema_file: str) -> list[str]:
    """
    Extract all description strings from the schema file.

    Args:
        schema_file: Path to the schema file

    Returns:
        Sorted list of description strings

    """
    descriptions: set[str] = set()

    try:
        with open(schema_file, encoding="utf-8") as f:
            schema = json.load(f)

        # Recursive function to extract all descriptions
        def extract_descriptions_recursively(obj: Union[dict, list]) -> None:
            if isinstance(obj, dict):
                # Extract description if it exists
                if "description" in obj and isinstance(obj["description"], str):
                    descriptions.add(obj["description"])

                # Process all values recursively
                for value in obj.values():
                    extract_descriptions_recursively(value)
            elif isinstance(obj, list):
                # Process list items recursively
                for item in obj:
                    extract_descriptions_recursively(item)

        # Start the extraction process
        extract_descriptions_recursively(schema)

    except json.JSONDecodeError as e:
        logger.error("Error parsing schema file %s: %s", schema_file, e)
    except Exception as e:  # pylint: disable=broad-exception-caught
        logger.error("Error processing schema file %s: %s", schema_file, e)

    return sorted(descriptions)


# pylint: enable=duplicate-code


def generate_config_steps_output(all_strings: dict[str, list[str]], schema_descriptions: list[str], output_file: str) -> None:
    """
    Generate the configuration_steps_strings.py file with translatable strings.

    Args:
        all_strings: Dictionary with string categories and their sorted unique values
        schema_descriptions: List of description strings from the schema
        output_file: Path to the output file

    """
    # Generate the Python file content
    current_year = datetime.now().year

    # Count total number of strings across all categories
    total_string_count = sum(len(strings) for strings in all_strings.values())

    # Add noqa comment if there are many strings (causing too-many-statements warning)
    ignore_too_many_statements = "  # noqa: PLR0915 # pylint: disable=too-many-statements" if total_string_count > 50 else ""

    file_content = f'''"""
Auto-generated by the update_configuration_steps_translation.py. Do not edit, ALL CHANGES WILL BE LOST.

This file is part of Ardupilot methodic configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-{current_year} Amilcar Lucas

SPDX-License-Identifier: GPL-3.0-or-later
"""

from ardupilot_methodic_configurator import _

# ruff: noqa: E501
# fmt: off
# pylint: disable=line-too-long


def configuration_steps_strings() -> None:{ignore_too_many_statements}
    """
    Translatable strings extracted from all configuration_steps_*.json files.

    For pygettext to extract them, they have no other function
    """
'''

    # Add all extracted strings by category
    for category, strings in all_strings.items():
        file_content += f"    # {category}\n"
        for string in strings:
            # Escape any double quotes in the string
            escaped_string = string.replace('"', '\\"')

            # Check if this is a multiline string
            if "\n" in escaped_string:
                # Use triple quotes for multiline strings
                file_content += f'    _config_steps_strings = _("""{escaped_string}""")\n'
            else:
                # Use single quotes for single-line strings
                file_content += f'    _config_steps_strings = _("{escaped_string}")\n'
        file_content += "\n"

    # Add the configuration_steps_descriptions function
    ignore_too_many_statements = (
        "  # noqa: PLR0915 # pylint: disable=too-many-statements" if len(schema_descriptions) > 50 else ""
    )

    file_content += f'''
# fmt: on


def configuration_steps_descriptions() -> None:{ignore_too_many_statements}
    """
    Translatable strings extracted from the configuration_steps_schema.json file.

    For pygettext to extract them, they have no other function
    """
'''

    # Add each description as a translatable string
    for description in schema_descriptions:
        # Escape any double quotes in the description
        escaped_description = description.replace('"', '\\"')

        # Check if this is a multiline string
        if "\n" in escaped_description:
            # Use triple quotes for multiline strings
            file_content += f'    _config_steps_descriptions = _("""{escaped_description}""")\n'
        else:
            # Use single quotes for single-line strings
            file_content += f'    _config_steps_descriptions = _("{escaped_description}")\n'

    # Write to the output file
    with open(output_file, "w", encoding="utf-8", newline="\n") as f:
        f.write(file_content)

    # Log summary info
    logger.info(
        "Generated %s with %d translatable strings and %d description strings",
        output_file,
        total_string_count,
        len(schema_descriptions),
    )


def main() -> None:
    """Main function to coordinate the generation of translatable strings."""
    # Configure logging
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")

    # Base directory for scanning
    base_dir = os.path.dirname(os.path.abspath(__file__))
    config_dir = os.path.join(base_dir, "ardupilot_methodic_configurator")
    schema_file = os.path.join(config_dir, "configuration_steps_schema.json")
    output_file = os.path.join(config_dir, "configuration_steps_strings.py")

    # Gather all translatable strings from configuration steps files
    all_strings = gather_all_translatable_strings(config_dir)

    # Extract descriptions from schema file
    schema_descriptions = extract_descriptions_from_schema(schema_file)

    # Generate the output file with both configuration steps strings and schema descriptions
    generate_config_steps_output(all_strings, schema_descriptions, output_file)


if __name__ == "__main__":
    main()
