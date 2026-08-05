"""
Log-analysis data source adapters.

Contains side-effecting operations (filesystem/network) that feed pure
validation and analysis logic.

SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

from json import JSONDecodeError
from json import load as json_load
from logging import error as logging_error
from pathlib import Path
from typing import Any

from ardupilot_methodic_configurator import _
from ardupilot_methodic_configurator.annotate_params import (
    PARAM_DEFINITION_XML_FILE,
    create_doc_dict,
    get_fallback_xml_url,
    get_xml_data,
    get_xml_url,
)
from ardupilot_methodic_configurator.log_analysis.utils import APMDoc


def load_configuration_steps(vehicle_type: str = "ArduCopter") -> dict[str, Any] | None:
    """
    Load the Methodic Configurator configuration steps for the given vehicle type.

    Returns None on any I/O or JSON error so callers can distinguish file errors
    from a legitimately empty configuration.
    """
    config_file = Path(__file__).parent.parent / f"configuration_steps_{vehicle_type}.json"

    try:
        with open(config_file, encoding="utf-8") as file:
            data: dict[str, Any] = json_load(file)
            steps = data.get("steps")
            return steps if isinstance(steps, dict) else None
    except FileNotFoundError:
        logging_error(_("Configuration file '{config_file}' not found").format(config_file=config_file))
    except JSONDecodeError as error:
        logging_error(_("Error in configuration file '{config_file}': {error}").format(config_file=config_file, error=error))

    return None


def load_apm_pdef(vehicle_dir: str, vehicle_type: str = "ArduCopter", firmware_version: str = "") -> APMDoc | None:
    """
    Fetch (or use cached) apm.pdef.xml and return a parameter documentation dictionary.

    Args:
        vehicle_dir: Directory where apm.pdef.xml is cached, or should be downloaded.
        vehicle_type: Vehicle type, e.g. "ArduCopter".
        firmware_version: Optional firmware version, e.g. "4.6.3".

    Returns:
        Parameter dictionary, or None if the file cannot be obtained.

    """
    xml_url = get_xml_url(vehicle_type, firmware_version)
    fallback_xml_url = get_fallback_xml_url(vehicle_type, firmware_version) if firmware_version else None

    try:
        xml_root = get_xml_data(xml_url, vehicle_dir, PARAM_DEFINITION_XML_FILE, vehicle_type, fallback_xml_url)
    except (OSError, SystemExit, ValueError):
        return None

    return create_doc_dict(xml_root, vehicle_type)
