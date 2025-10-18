#!/usr/bin/env python3

"""
Script to process all vehicle templates and test parameter derivation.

This script loads each leaf directory in the vehicle_templates directory
and tests the parameter derivation logic.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2025 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import logging
import os
import sys
from pathlib import Path

# Add parent directory to path to import from ardupilot_methodic_configurator
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ardupilot_methodic_configurator import __version__  # pylint: disable=wrong-import-position
from ardupilot_methodic_configurator.backend_filesystem import LocalFilesystem  # pylint: disable=wrong-import-position
from ardupilot_methodic_configurator.data_model_vehicle_components import (  # pylint: disable=wrong-import-position
    ComponentDataModel,
)
from ardupilot_methodic_configurator.data_model_vehicle_components_json_schema import (  # pylint: disable=wrong-import-position
    VehicleComponentsJsonSchema,
)


def find_template_directories() -> list[Path]:
    """
    Find all leaf template directories in the vehicle_templates directory.

    Returns:
        list[Path]: List of leaf directory paths

    """
    # Get the vehicle_templates directory relative to this script
    script_dir = Path(__file__).parent
    templates_dir = script_dir / "ardupilot_methodic_configurator" / "vehicle_templates"

    if not templates_dir.exists():
        logging.error("Templates directory not found at %s", templates_dir)
        sys.exit(1)

    # Find all leaf directories (those containing no subdirectories)
    leaf_dirs = []
    for root, dirs, _files in os.walk(templates_dir):
        if not dirs:  # This is a leaf directory
            leaf_dirs.append(Path(root))

    logging.info("Found %d template directories to process", len(leaf_dirs))
    return leaf_dirs


def process_template_directory(template_dir: Path) -> None:
    """Process a single template directory."""
    logging.info("\nProcessing template: %s", template_dir)

    try:
        # Initialize LocalFilesystem with the template directory
        local_fs = LocalFilesystem(
            vehicle_dir=str(template_dir),
            vehicle_type="",
            fw_version=__version__,
            allow_editing_template_files=True,
            save_component_to_system_templates=False,
        )

        if local_fs.vehicle_type not in str(template_dir):
            logging.error("Vehicle type mismatch in %s", template_dir)
            return

        if not local_fs.vehicle_components_fs.data or not isinstance(local_fs.vehicle_components_fs.data, dict):
            logging.error("Vehicle components are empty/invalid in %s", template_dir)
            return

        # Use ComponentDataModel to update the vehicle components structure
        schema = VehicleComponentsJsonSchema(local_fs.load_schema())
        datatypes = schema.get_all_value_datatypes()
        data_model = ComponentDataModel(local_fs.vehicle_components_fs.data, datatypes, schema)
        data_model.update_json_structure()
        local_fs.vehicle_components_fs.data = data_model.get_component_data()

        local_fs.save_vehicle_components_json_data(local_fs.vehicle_components_fs.data, str(template_dir))

        existing_fc_params = list(local_fs.param_default_dict.keys()) if local_fs.param_default_dict else []

        # Test parameter derivation (passing None means only forced/derived params are computed)
        error = local_fs.update_and_export_vehicle_params_from_fc(
            source_param_values=None, existing_fc_params=existing_fc_params
        )
        if error:
            logging.error("Error processing %s:", template_dir)
            logging.error(error)

    except Exception as e:  # pylint: disable=broad-exception-caught
        logging.error("Failed to process %s:", template_dir)
        logging.error(str(e))


def main() -> None:
    """Main function to process all template directories."""
    # Configure logging
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

    leaf_dirs = find_template_directories()

    # Process each template directory
    for template_dir in leaf_dirs:
        process_template_directory(template_dir)


if __name__ == "__main__":
    main()
