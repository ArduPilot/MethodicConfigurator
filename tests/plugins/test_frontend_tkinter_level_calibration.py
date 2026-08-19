"""
Behavior-driven tests for the level calibration Tkinter plugin.

This file is part of ArduPilot Methodic Configurator.
https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2026 Amilcar do Carmo Lucas

SPDX-License-Identifier: GPL-3.0-or-later
"""

from collections.abc import Generator
from tkinter import ttk
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from ardupilot_methodic_configurator.plugins.data_model_level_calibration import LevelCalibrationDataModel
from ardupilot_methodic_configurator.plugins.frontend_tkinter_level_calibration import LevelCalibrationView


@pytest.fixture
def level_calibration_view(tk_root, mocker) -> Generator[SimpleNamespace, None, None]:
    """Provide a real level-calibration view with its external UI effects isolated."""
    model = MagicMock(spec=LevelCalibrationDataModel)
    showinfo = mocker.patch("ardupilot_methodic_configurator.plugins.frontend_tkinter_level_calibration.showinfo")
    showerror = mocker.patch("ardupilot_methodic_configurator.plugins.frontend_tkinter_level_calibration.showerror")
    parent = ttk.Frame(tk_root)
    try:
        yield SimpleNamespace(
            view=LevelCalibrationView(parent, model, SimpleNamespace(root=tk_root)),
            model=model,
            showinfo=showinfo,
            showerror=showerror,
        )
    finally:
        parent.destroy()


class TestLevelCalibrationView:
    """Test the user feedback displayed by the level calibration view."""

    def test_user_sees_success_when_level_trim_completes(self, level_calibration_view) -> None:
        """
        A successful calibration is presented as an informational result.

        GIVEN: The model completes the level trim successfully
        WHEN: The user selects Level Calibration
        THEN: The view shows the completion message without an error dialog
        """
        # Arrange (Given)
        level_calibration_view.model.start_level_calibration.return_value = (True, "Level calibration successful")

        # Act (When)
        level_calibration_view.view._on_level_calibration()

        # Assert (Then)
        level_calibration_view.showinfo.assert_called_once_with("Calibration Result", "Level calibration successful")
        level_calibration_view.showerror.assert_not_called()

    def test_user_sees_error_when_level_trim_fails(self, level_calibration_view) -> None:
        """
        A failed calibration is presented as an actionable error.

        GIVEN: The model rejects the level trim
        WHEN: The user selects Level Calibration
        THEN: The view shows the failure message without a success dialog
        """
        # Arrange (Given)
        level_calibration_view.model.start_level_calibration.return_value = (False, "Vehicle is moving")

        # Act (When)
        level_calibration_view.view._on_level_calibration()

        # Assert (Then)
        level_calibration_view.showerror.assert_called_once_with("Calibration Failed", "Vehicle is moving")
        level_calibration_view.showinfo.assert_not_called()
