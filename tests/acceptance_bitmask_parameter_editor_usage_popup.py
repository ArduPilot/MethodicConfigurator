#!/usr/bin/env python3

"""
BDD acceptance tests for the bitmask parameter editor usage popup.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2025 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

from __future__ import annotations

import tkinter as tk
from dataclasses import dataclass
from typing import TYPE_CHECKING, Callable, cast
from unittest.mock import MagicMock

import pytest

from ardupilot_methodic_configurator.backend_filesystem_program_settings import USAGE_POPUP_WINDOWS
from ardupilot_methodic_configurator.data_model_ardupilot_parameter import ArduPilotParameter
from ardupilot_methodic_configurator.frontend_tkinter_parameter_editor_table import (
    ParameterEditorTable,
    ParameterEditorTableDialogs,
)
from ardupilot_methodic_configurator.frontend_tkinter_usage_popup_windows import (
    display_bitmask_parameters_editor_usage_popup,
)

if TYPE_CHECKING:  # pragma: no cover - import for typing only
    from collections.abc import Generator

    from pytest_mock import MockerFixture

    from ardupilot_methodic_configurator.data_model_parameter_editor import ParameterEditor

MODULE_TABLE = "ardupilot_methodic_configurator.frontend_tkinter_parameter_editor_table"
MODULE_WINDOWS = "ardupilot_methodic_configurator.frontend_tkinter_usage_popup_windows"


# pylint: disable=redefined-outer-name


@dataclass
class StubStepParameter:
    """Minimal stand-in for `ArduPilotParameter` attributes needed by the helper."""

    is_editable: bool
    is_bitmask: bool


class StubParameterEditor:
    """Provide just enough behavior for the acceptance scenarios."""

    def __init__(self, on_add: Callable[[str], bool] | None = None) -> None:
        self.current_step_parameters: dict[str, StubStepParameter] = {}
        self.current_file = "01_test.param"
        self._on_add = on_add

    def should_display_bitmask_parameter_editor_usage(self, param_name: str) -> bool:
        param = self.current_step_parameters[param_name]
        return param.is_editable and param.is_bitmask

    def add_parameter_to_current_file(self, param_name: str) -> bool:
        if self._on_add is None:
            return False
        return self._on_add(param_name)

    def get_parameters_as_par_dict(self) -> dict[str, object]:  # pragma: no cover - unused helper
        return {}


@pytest.fixture
def tk_root() -> Generator[tk.Tk, None, None]:
    """Create a Tk root that stays hidden during the tests."""
    root = tk.Tk()
    root.withdraw()
    try:
        yield root
    finally:
        root.destroy()


def _build_table(tk_root: tk.Tk, parameter_editor: StubParameterEditor) -> ParameterEditorTable:
    dialogs = ParameterEditorTableDialogs(
        show_error=MagicMock(),
        show_info=MagicMock(),
        ask_yes_no=MagicMock(return_value=True),
    )
    parameter_editor_window = MagicMock()
    parameter_editor_window.gui_complexity = "simple"
    parameter_editor_window.root = tk_root
    parameter_editor_window.repopulate_parameter_table = MagicMock()
    parameter_editor_window.on_skip_click = MagicMock()
    parameter_editor_obj = cast("ParameterEditor", parameter_editor)
    return ParameterEditorTable(tk_root, parameter_editor_obj, parameter_editor_window, dialogs=dialogs)


def test_user_sees_popup_when_table_contains_editable_bitmask_parameter(tk_root: tk.Tk, mocker: MockerFixture) -> None:
    """
    Acceptance scenario for showing the popup during table render.

    GIVEN a table showing an editable bitmask parameter
    WHEN it renders
    THEN the popup is displayed.
    """
    # Arrange
    parameter_editor = StubParameterEditor()
    parameter_editor.current_step_parameters["BITMASK"] = StubStepParameter(is_editable=True, is_bitmask=True)
    table = _build_table(tk_root, parameter_editor)

    mocker.patch.object(table, "_create_column_widgets", return_value=[])
    mocker.patch.object(table, "_grid_column_widgets")
    mock_should_display = mocker.patch(f"{MODULE_TABLE}.UsagePopupWindow.should_display", return_value=True)
    mock_display = mocker.patch(f"{MODULE_TABLE}.display_bitmask_parameters_editor_usage_popup")

    fake_param = MagicMock(spec=ArduPilotParameter)

    # Act
    table._update_table({"BITMASK": fake_param}, gui_complexity="simple")  # pylint: disable=protected-access

    # Assert
    mock_should_display.assert_called_once_with("bitmask_parameter_editor")
    mock_display.assert_called_once_with(tk_root)


def test_user_preference_can_hide_popup_during_table_render(tk_root: tk.Tk, mocker: MockerFixture) -> None:
    """
    Acceptance scenario for honoring the user preference during render.

    GIVEN the user disabled the popup
    WHEN the table renders
    THEN no popup is displayed.
    """
    # Arrange
    parameter_editor = StubParameterEditor()
    parameter_editor.current_step_parameters["BITMASK"] = StubStepParameter(is_editable=True, is_bitmask=True)
    table = _build_table(tk_root, parameter_editor)

    mocker.patch.object(table, "_create_column_widgets", return_value=[])
    mocker.patch.object(table, "_grid_column_widgets")
    mocker.patch(f"{MODULE_TABLE}.UsagePopupWindow.should_display", return_value=False)
    mock_display = mocker.patch(f"{MODULE_TABLE}.display_bitmask_parameters_editor_usage_popup")

    fake_param = MagicMock(spec=ArduPilotParameter)

    # Act
    table._update_table({"BITMASK": fake_param}, gui_complexity="simple")  # pylint: disable=protected-access

    # Assert
    mock_display.assert_not_called()


def test_user_reads_all_available_bitmask_entry_methods(tk_root: tk.Tk, mocker: MockerFixture) -> None:
    """
    Acceptance scenario for listing all entry methods in the helper.

    GIVEN the helper window
    WHEN it opens
    THEN it lists the four supported entry styles.
    """
    # Arrange
    usage_popup_window = MagicMock()
    usage_popup_window.main_frame = MagicMock()
    mocker.patch(f"{MODULE_WINDOWS}.BaseWindow", return_value=usage_popup_window)
    instructions_widget = MagicMock()
    mocker.patch(f"{MODULE_WINDOWS}.RichText", return_value=instructions_widget)
    mock_display = mocker.patch(f"{MODULE_WINDOWS}.UsagePopupWindow.display")

    parent = tk_root

    # Act
    display_bitmask_parameters_editor_usage_popup(parent)

    # Assert
    mock_display.assert_called_once()
    inserted_text = "".join(call.args[1] for call in instructions_widget.insert.call_args_list if len(call.args) >= 2)
    assert "Bitmask parameters are editable in four different ways" in inserted_text
    assert "double-click" in inserted_text
    assert "decimal value" in inserted_text
    assert "0x" in inserted_text
    assert "0b" in inserted_text


def test_user_can_toggle_popup_persistence_via_settings() -> None:
    """
    Acceptance scenario for exposing the bitmask preference entry.

    GIVEN the program settings
    WHEN they are inspected
    THEN the bitmask preference entry is available.
    """
    # Arrange
    assert "bitmask_parameter_editor" in USAGE_POPUP_WINDOWS

    # Act
    definition = USAGE_POPUP_WINDOWS["bitmask_parameter_editor"]

    # Assert
    assert "Bitmask parameter editor" in definition.description
