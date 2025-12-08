#!/usr/bin/env python3

"""
Acceptance tests for the only-changed-get-uploaded usage popup.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2025 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

from __future__ import annotations

import tkinter as tk
from typing import TYPE_CHECKING, Any, cast  # pylint: disable=unused-import
from unittest.mock import MagicMock

from ardupilot_methodic_configurator.frontend_tkinter_parameter_editor import ParameterEditorWindow
from ardupilot_methodic_configurator.frontend_tkinter_usage_popup_windows import (
    only_upload_changed_parameters_usage_popup,
)

if TYPE_CHECKING:
    from pytest_mock import MockerFixture

PE_MODULE = "ardupilot_methodic_configurator.frontend_tkinter_parameter_editor"
POPUP_MODULE = "ardupilot_methodic_configurator.frontend_tkinter_usage_popup_windows"


class _FakeTk:  # pylint: disable=too-few-public-methods
    """Minimal Tk stand-in for isinstance checks and parent validation."""

    def winfo_exists(self) -> bool:
        return True


def _build_parameter_editor_window(root: object) -> tuple[ParameterEditorWindow, dict[str, MagicMock]]:
    """Create a ParameterEditorWindow instance without running the heavy __init__."""
    window = ParameterEditorWindow.__new__(ParameterEditorWindow)
    window.root = cast("tk.Tk", root)
    window.gui_complexity = "normal"

    write_changes = MagicMock()
    get_upload_params = MagicMock(return_value={"ATC_RAT_PIT_P": 0.123})
    ensure_preconditions = MagicMock(return_value=True)
    upload_params = MagicMock()
    on_skip = MagicMock()
    ui = MagicMock()
    ui.show_warning = MagicMock()

    parameter_table = MagicMock()
    parameter_table.get_upload_selected_params = get_upload_params
    parameter_editor = MagicMock()
    parameter_editor.ensure_upload_preconditions = ensure_preconditions

    cast("Any", window).write_changes_to_intermediate_parameter_file = write_changes
    cast("Any", window).parameter_editor_table = parameter_table
    cast("Any", window).parameter_editor = parameter_editor
    cast("Any", window).ui = ui
    cast("Any", window).upload_selected_params = upload_params
    cast("Any", window).on_skip_click = on_skip

    mocks = {
        "write_changes": write_changes,
        "get_upload_params": get_upload_params,
        "ensure_preconditions": ensure_preconditions,
        "ui": ui,
        "upload_selected_params": upload_params,
        "on_skip": on_skip,
    }
    return window, mocks


def test_user_sees_usage_popup_before_uploading_parameters(mocker: MockerFixture) -> None:
    """
    Popup displays when the upload button is pressed for the first time.

    GIVEN: A parameter editor window with the usage popup preference enabled
    WHEN: The user triggers the "Upload selected params" action
    THEN: The usage popup appears before the upload workflow continues
    AND: The upload workflow still proceeds with the selected parameters
    """
    mocker.patch(f"{PE_MODULE}.tk.Tk", _FakeTk)
    root = _FakeTk()
    window, mocks = _build_parameter_editor_window(root)

    popup_spy = mocker.patch(f"{PE_MODULE}.only_upload_changed_parameters_usage_popup")
    mocker.patch(f"{PE_MODULE}.UsagePopupWindow.should_display", return_value=True)

    window.on_upload_selected_click()

    popup_spy.assert_called_once_with(root)
    mocks["write_changes"].assert_called_once()
    mocks["get_upload_params"].assert_called_once_with("normal")
    mocks["ensure_preconditions"].assert_called_once()
    mocks["upload_selected_params"].assert_called_once_with({"ATC_RAT_PIT_P": 0.123})
    mocks["on_skip"].assert_called_once()


def test_user_skips_usage_popup_when_preference_disabled(mocker: MockerFixture) -> None:
    """
    Popup is suppressed when the user deselected it previously.

    GIVEN: A parameter editor window with the "show again" preference disabled
    WHEN: The user presses the upload button
    THEN: The usage popup is not shown
    AND: The upload workflow still completes normally
    """
    mocker.patch(f"{PE_MODULE}.tk.Tk", _FakeTk)
    root = _FakeTk()
    window, mocks = _build_parameter_editor_window(root)

    popup_spy = mocker.patch(f"{PE_MODULE}.only_upload_changed_parameters_usage_popup")
    mocker.patch(f"{PE_MODULE}.UsagePopupWindow.should_display", return_value=False)

    window.on_upload_selected_click()

    popup_spy.assert_not_called()
    mocks["write_changes"].assert_called_once()
    mocks["upload_selected_params"].assert_called_once()
    mocks["on_skip"].assert_called_once()


def test_usage_popup_renders_message_and_image(mocker: MockerFixture) -> None:
    """
    Popup explains the upload rules with text and imagery.

    GIVEN: A live parent window and an accessible illustration
    WHEN: The usage popup helper renders the window
    THEN: The instructional text and image are both inserted into the popup
    """
    parent = MagicMock(spec=tk.Tk)
    parent.winfo_exists.return_value = True
    popup_window = MagicMock()
    popup_window.main_frame = MagicMock()
    popup_window.root = MagicMock()
    image_label = MagicMock()
    popup_window.put_image_in_label.return_value = image_label

    mocker.patch(f"{POPUP_MODULE}.BaseWindow", return_value=popup_window)
    instructions_widget = MagicMock()
    mocker.patch(f"{POPUP_MODULE}.RichText", return_value=instructions_widget)
    mocker.patch(f"{POPUP_MODULE}.get_safe_font_config", return_value={"family": "Arial", "size": 12})
    mocker.patch(f"{POPUP_MODULE}.create_scaled_font", return_value="Arial 12")
    mocker.patch(f"{POPUP_MODULE}.UsagePopupWindow.setup_window")
    mocker.patch(f"{POPUP_MODULE}.UsagePopupWindow.finalize_setup_window")
    mocker.patch(f"{POPUP_MODULE}.ProgramSettings.what_gets_uploaded_image_filepath", return_value="image.png")

    result = only_upload_changed_parameters_usage_popup(parent)

    assert result is popup_window
    instructions_widget.insert.assert_any_call(tk.END, "Only", "bold")
    instructions_widget.insert.assert_any_call(tk.END, "No other FC parameters will be changed.")
    instructions_widget.config.assert_called_once_with(state=tk.DISABLED)
    popup_window.put_image_in_label.assert_called_once_with(popup_window.main_frame, "image.png", image_height=68)
    image_label.pack.assert_called_once()


def test_usage_popup_falls_back_to_label_when_image_missing(mocker: MockerFixture) -> None:
    """
    Popup still offers guidance when the illustration cannot be loaded.

    GIVEN: The usage popup image asset is missing
    WHEN: The helper attempts to render the illustration
    THEN: A fallback ttk.Label is displayed instead of the missing image
    """
    parent = MagicMock(spec=tk.Tk)
    parent.winfo_exists.return_value = True
    popup_window = MagicMock()
    popup_window.main_frame = MagicMock()
    popup_window.root = MagicMock()
    popup_window.put_image_in_label.side_effect = FileNotFoundError()

    mocker.patch(f"{POPUP_MODULE}.BaseWindow", return_value=popup_window)
    mocker.patch(f"{POPUP_MODULE}.RichText", return_value=MagicMock())
    mocker.patch(f"{POPUP_MODULE}.get_safe_font_config", return_value={"family": "Arial", "size": 12})
    mocker.patch(f"{POPUP_MODULE}.create_scaled_font", return_value="Arial 12")
    mocker.patch(f"{POPUP_MODULE}.UsagePopupWindow.setup_window")
    mocker.patch(f"{POPUP_MODULE}.UsagePopupWindow.finalize_setup_window")
    mocker.patch(f"{POPUP_MODULE}.ProgramSettings.what_gets_uploaded_image_filepath", return_value="missing.png")
    fallback_label = MagicMock()
    mocker.patch(f"{POPUP_MODULE}.ttk.Label", return_value=fallback_label)

    only_upload_changed_parameters_usage_popup(parent)

    fallback_label.pack.assert_called_once()
