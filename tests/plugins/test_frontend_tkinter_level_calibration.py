#!/usr/bin/env python3

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

# pytest injects fixtures by matching the test function parameter name.
# pylint: disable=redefined-outer-name,protected-access


@pytest.fixture
def level_calibration_view(tk_root, mocker) -> Generator[SimpleNamespace, None, None]:
    """Provide a real level-calibration view with its external UI effects isolated."""
    # pylint: disable=duplicate-code
    model = MagicMock(spec=LevelCalibrationDataModel)
    base_window = SimpleNamespace(
        root=tk_root,
        download_flight_controller_parameters=MagicMock(),
        parameter_editor=SimpleNamespace(update_parameters_from_fc_values=MagicMock()),
        repopulate_parameter_table=MagicMock(),
    )
    # pylint: enable=duplicate-code
    showinfo = mocker.patch("ardupilot_methodic_configurator.plugins.frontend_tkinter_level_calibration.showinfo")
    showerror = mocker.patch("ardupilot_methodic_configurator.plugins.frontend_tkinter_level_calibration.showerror")
    parent = ttk.Frame(tk_root)
    try:
        yield SimpleNamespace(
            view=LevelCalibrationView(parent, model, base_window),
            model=model,
            base_window=base_window,
            showinfo=showinfo,
            showerror=showerror,
        )
    finally:
        parent.destroy()


class TestLevelCalibrationView:
    """Test the user feedback displayed by the level calibration view."""

    def test_layout_matches_the_accelerometer_calibration_rows(self, level_calibration_view) -> None:
        """
        The level-calibration row uses the same button/text arrangement as accelerometer calibration.

        GIVEN: The level-calibration view is displayed
        WHEN: Its controls are laid out
        THEN: The button is left-aligned and the explanatory text fills the row on the right
        """
        button_pack = level_calibration_view.view._level_btn.pack_info()
        info_pack = level_calibration_view.view._level_info_label.pack_info()

        assert button_pack["side"] == "left"
        assert button_pack["padx"] == (8, 16)
        assert button_pack["anchor"] == "n"
        assert info_pack["side"] == "left"
        assert info_pack["fill"] == "x"
        assert info_pack["expand"] == 1
        assert info_pack["anchor"] == "w"

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
        level_calibration_view.base_window.download_flight_controller_parameters.assert_called_once_with(redownload=True)
        level_calibration_view.base_window.parameter_editor.update_parameters_from_fc_values.assert_called_once_with()
        level_calibration_view.base_window.repopulate_parameter_table.assert_called_once_with()

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
