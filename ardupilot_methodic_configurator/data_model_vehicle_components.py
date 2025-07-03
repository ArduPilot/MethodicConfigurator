"""
Data model for vehicle components.

This file is part of Ardupilot methodic configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2025 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

from ardupilot_methodic_configurator.data_model_vehicle_components_display import ComponentDataModelDisplay
from ardupilot_methodic_configurator.data_model_vehicle_components_import import ComponentDataModelImport
from ardupilot_methodic_configurator.data_model_vehicle_components_templates import ComponentDataModelTemplates
from ardupilot_methodic_configurator.data_model_vehicle_components_validation import ComponentDataModelValidation


class ComponentDataModel(
    ComponentDataModelValidation, ComponentDataModelImport, ComponentDataModelTemplates, ComponentDataModelDisplay
):
    """
    Handle vehicle component data operations.

    Combines base data model functionality with FC data import,
    component template handling, display logic, and data validation.
    """
