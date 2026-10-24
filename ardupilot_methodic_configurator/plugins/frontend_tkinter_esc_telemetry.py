"""
Plugin factories for the reusable ESC telemetry table.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import tkinter as tk
from tkinter import ttk

from ardupilot_methodic_configurator.data_model_esc_telemetry import EscTelemetryDataModel
from ardupilot_methodic_configurator.frontend_tkinter_esc_telemetry import EscTelemetryView
from ardupilot_methodic_configurator.plugins.plugin_constants import PLUGIN_ESC_TELEMETRY
from ardupilot_methodic_configurator.plugins.plugin_factory import PluginModelContext, plugin_factory


def _create_model(context: PluginModelContext) -> EscTelemetryDataModel:
    return EscTelemetryDataModel(context.flight_controller)


def _create_view(parent: tk.Frame | ttk.Frame, model: object, base_window: object) -> EscTelemetryView:
    if not isinstance(model, EscTelemetryDataModel):
        message = "Expected ESC telemetry data model"
        raise TypeError(message)
    return EscTelemetryView(parent, model, base_window)  # type: ignore[arg-type]


def register_esc_telemetry_plugin() -> None:
    """Register reusable ESC telemetry through the shared plugin dispatcher."""
    plugin_factory.register(PLUGIN_ESC_TELEMETRY, _create_view, _create_model)
