#!/usr/bin/env python3

"""
Extract translatable strings from all configuration_steps_*.json files to pygettext compatible format.

It also extracts all description strings from the configuration_steps_schema.json file.
It creates a configuration_steps_strings.py python file that pygettext can process.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2026 Amilcar Lucas

SPDX-License-Identifier: GPL-3.0-or-later
"""

import glob
import json
import logging
import os
import re
from datetime import datetime
from typing import Any

# Set up a proper logger
logger = logging.getLogger(__name__)


def extract_result_strings_from_conditional(change_reason: str) -> list[str]:
    """
    Extract individual result strings from a ternary conditional Change Reason expression.

    When a Change Reason is a Python ternary expression of the form::

        'result1' if <condition> else 'result2'

    the result strings ('result1' and 'result2') are what actually get passed to the
    translation function ``_()`` at runtime (after ``safe_evaluate`` evaluates the
    expression).  This helper pulls those result strings out so they can be registered
    as separate msgids in the translation catalog.

    The full conditional expression is kept as a msgid too (fallback path when
    ``safe_evaluate`` fails at runtime).

    Args:
        change_reason: The raw Change Reason string from a configuration step JSON file.

    Returns:
        A list of individual result strings found in the expression.
        Returns an empty list when the string is not a ternary conditional or when
        no quoted result strings are found.

    """
    stripped = change_reason.strip()
    if " if " not in stripped or " else " not in stripped:
        return []
    result_strings: list[str] = []
    # Extract the first single-quoted string (before the leading ' if ')
    first_match = re.match(r"^'([^']+)'\s+if\s+", stripped)
    if first_match:
        result_strings.append(first_match.group(1))
    # Extract the last single-quoted string (after the trailing ' else ')
    last_match = re.search(r"else\s+'([^']+)'$", stripped)
    if last_match:
        result_strings.append(last_match.group(1))
    return result_strings


def _add_text_fields(
    step_data: dict[str, Any],
    text_fields: list[str],
    extracted_strings: dict[str, set[str]],
) -> None:
    for field in text_fields:
        value = step_data.get(field)
        if isinstance(value, str) and value.strip():
            extracted_strings[field].add(value)


def _add_jump_messages(
    step_data: dict[str, Any],
    extracted_strings: dict[str, set[str]],
) -> None:
    jump_possible = step_data.get("jump_possible")
    if not isinstance(jump_possible, dict):
        return
    for jump_message in jump_possible.values():
        if isinstance(jump_message, str) and jump_message.strip():
            extracted_strings["jump_messages"].add(jump_message)


def _add_change_reasons(
    step_data: dict[str, Any],
    extracted_strings: dict[str, set[str]],
) -> None:
    reasons = extracted_strings.setdefault("change_reasons", set())
    for param_type in ("forced_parameters", "derived_parameters", "add_parameters"):
        for param_data in step_data.get(param_type, {}).values():
            change_reason = param_data.get("Change Reason")
            if not isinstance(change_reason, str) or not change_reason.strip():
                continue
            reasons.add(change_reason)
            # Register individual result strings of ternary expressions so the
            # translated output of safe_evaluate() is also in the catalog.
            reasons.update(extract_result_strings_from_conditional(change_reason))


def process_configuration_steps(
    text_fields: list[str],
    extracted_strings: dict[str, set[str]],
    data: dict[str, Any],
) -> None:
    for step_data in data["steps"].values():
        _add_text_fields(step_data, text_fields, extracted_strings)
        _add_jump_messages(step_data, extracted_strings)
        _add_change_reasons(step_data, extracted_strings)


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
    extracted_strings["instructions_popup"] = set()

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

    except json.JSONDecodeError:
        logger.exception("Error parsing %s:", config_file)
    except Exception:  # pylint: disable=broad-exception-caught
        logger.exception("Error processing %s:", config_file)

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
        def extract_descriptions_recursively(obj: dict | list) -> None:
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

    except json.JSONDecodeError:
        logger.exception("Error parsing schema file %s:", schema_file)
    except Exception:  # pylint: disable=broad-exception-caught
        logger.exception("Error processing schema file %s:", schema_file)

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

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

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

    # Base directory for scanning (the script lives in the scripts/ subdirectory)
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
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
