#!/usr/bin/env python3
"""
Extract translatable strings from all vehicle_components.json files and
create a vehicle_components.py Python file that pygettext can process.

This file is part of Ardupilot methodic configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2025 Amilcar Lucas

SPDX-License-Identifier: GPL-3.0-or-later
"""

import json
import logging
import os
from datetime import datetime

# Set up a proper logger
logger = logging.getLogger(__name__)


def extract_keys_recursively(data, keys=None):
    """Recursively extract all keys from a nested JSON object."""
    if keys is None:
        keys = set()

    if isinstance(data, dict):
        for key, value in data.items():
            # Only add string keys (skip numeric indices, version numbers, etc.)
            if isinstance(key, str) and not key.isdigit():
                keys.add(key)
            # Recursively process nested structures
            extract_keys_recursively(value, keys)
    elif isinstance(data, list):
        for item in data:
            extract_keys_recursively(item, keys)

    return keys


def gather_translatable_strings(templates_dir: str) -> list[str]:
    """
    Scan all vehicle_components.json files and extract unique keys.

    Args:
        templates_dir: Directory containing vehicle templates

    Returns:
        Sorted list of translatable strings

    """
    # Find all vehicle_components.json files recursively
    json_files = []
    for root, _dirs, files in os.walk(templates_dir):
        for file in files:
            if file == "vehicle_components.json":
                json_files.append(os.path.join(root, file))

    # Extract unique keys from all JSON files
    all_keys: set[str] = set()
    for json_file in json_files:
        try:
            with open(json_file, encoding="utf-8") as f:
                data = json.load(f)
                keys = extract_keys_recursively(data)
                all_keys.update(keys)
        except json.JSONDecodeError as e:
            logger.error("Error parsing %s: %s", json_file, e)
        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.error("Error processing %s: %s", json_file, e)

    return list(all_keys)


def generate_vehicle_components_output(sorted_keys: list[str], output_file: str) -> None:
    """
    Generate the vehicle_components.py file with translatable strings.

    Args:
        sorted_keys: List of translatable strings to include
        output_file: Path to the output file

    """
    # Generate the Python file content
    current_year = datetime.now().year
    file_content = f'''"""
This file is auto-generated. Do not edit, all changes will be lost

These are translatable strings extracted from the vehicle_components.json file

This file is part of Ardupilot methodic configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-{current_year} Amilcar Lucas

SPDX-License-Identifier: GPL-3.0-or-later
"""

from ardupilot_methodic_configurator import _


def translatable_strings() -> None:
    # these are just here so that pygettext extracts them, they have no function
'''

    # Add each key as a translatable string
    for key in sorted_keys:
        file_content += f'    _vehicle_components_strings = _("{key}")\n'

    # Write to the output file
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(file_content)

    logger.info("Generated %s with %d translatable strings", output_file, len(sorted_keys))


def main() -> None:
    """Main function to coordinate the generation of translatable strings."""
    # Configure logging
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")

    # Base directory for scanning
    base_dir = os.path.dirname(os.path.abspath(__file__))
    templates_dir = os.path.join(base_dir, "ardupilot_methodic_configurator", "vehicle_templates")
    output_file = os.path.join(base_dir, "ardupilot_methodic_configurator", "vehicle_components.py")

    # Gather all translatable strings
    translatable_strings = gather_translatable_strings(templates_dir)

    # Generate the output file
    generate_vehicle_components_output(translatable_strings, output_file)


if __name__ == "__main__":
    main()
