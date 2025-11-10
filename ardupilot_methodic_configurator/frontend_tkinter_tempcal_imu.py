"""
Frontend integration for IMU temperature calibration.

This module provides the GUI integration for IMU temperature calibration,
handling user interactions and coordinating with the business logic layer.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2025 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ardupilot_methodic_configurator.plugin_constants import PLUGIN_TEMPCAL_IMU
from ardupilot_methodic_configurator.plugin_factory_workflow import plugin_factory_workflow

if TYPE_CHECKING:
    from ardupilot_methodic_configurator.business_logic_tempcal_imu import TempCalIMUDataModel


class TempCalIMUWorkflow:  # pylint: disable=too-few-public-methods
    """
    Manages the IMU temperature calibration workflow from the GUI perspective.

    This class handles the GUI-specific aspects of the calibration process,
    including creating the progress window and coordinating workflow execution.
    """

    def __init__(self, root_window: object, data_model: TempCalIMUDataModel) -> None:
        """
        Initialize the IMU temperature calibration workflow.

        Args:
            root_window: The root Tkinter window for creating dialogs
            data_model: The business logic data model for calibration

        """
        self.root_window = root_window
        self.data_model = data_model

    def run_workflow(self) -> bool:
        """
        Execute the complete IMU temperature calibration workflow.

        This method creates the progress window and delegates the
        actual workflow logic to the business logic layer.

        Returns:
            bool: True if calibration was performed successfully, False otherwise

        """
        # Run the calibration - cleanup is handled by the data model's finally block
        return self.data_model.run_calibration()


def create_tempcal_imu_workflow(
    root_window: object,
    data_model: object,
) -> TempCalIMUWorkflow:
    """
    Factory function to create a TempCalIMUWorkflow instance.

    Args:
        root_window: The root Tkinter window
        data_model: The business logic data model

    Returns:
        TempCalIMUWorkflow: A new workflow instance

    """
    return TempCalIMUWorkflow(root_window, data_model)  # type: ignore[arg-type]


def register_tempcal_imu_plugin() -> None:
    """Register the tempcal_imu workflow plugin creator with the workflow factory."""
    plugin_factory_workflow.register(PLUGIN_TEMPCAL_IMU, create_tempcal_imu_workflow)
