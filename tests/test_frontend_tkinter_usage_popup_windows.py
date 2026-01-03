#!/usr/bin/env python3

"""
BDD Tests for the frontend_tkinter_usage_popup_windows.py file.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import tkinter as tk
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from pytest_mock import MockerFixture

from ardupilot_methodic_configurator.frontend_tkinter_usage_popup_windows import (
    confirm_component_properties,
    display_component_editor_usage_popup,
    display_parameter_editor_usage_popup,
    display_workflow_explanation,
)

MODULE = "ardupilot_methodic_configurator.frontend_tkinter_usage_popup_windows"


# pylint: disable=redefined-outer-name


@pytest.fixture
def mock_parent() -> MagicMock:
    """Provide a Tk-compatible parent mock."""
    parent = MagicMock(spec=tk.Tk)
    parent.winfo_exists.return_value = True
    return parent


@pytest.fixture(autouse=True)
def mock_font_helpers(mocker: MockerFixture) -> None:
    """Avoid creating a real Tk default root when computing fonts."""
    mocker.patch(f"{MODULE}.get_safe_font_config", return_value={"size": 12, "family": "Arial"})
    mocker.patch(f"{MODULE}.create_scaled_font", return_value="font")
    popup_module = "ardupilot_methodic_configurator.frontend_tkinter_usage_popup_window"
    mocker.patch(f"{popup_module}.BooleanVar")


def test_display_parameter_editor_usage_popup_invokes_usage_window(mocker: MockerFixture, mock_parent: MagicMock) -> None:
    """
    Parameter editor helper triggers the usage popup when its parent window still exists.

    GIVEN: A live parent Tk window and patched UI helpers
    WHEN: The parameter editor usage popup helper is invoked
    THEN: UsagePopupWindow.display runs with the expected arguments and disables edits
    """
    # Arrange (Given)
    usage_popup_window = MagicMock()
    mocker.patch(f"{MODULE}.BaseWindow", return_value=usage_popup_window)
    instructions_widget = MagicMock()
    mocker.patch(f"{MODULE}.RichText", return_value=instructions_widget)
    mock_display = mocker.patch(f"{MODULE}.UsagePopupWindow.display")

    # Act (When)
    display_parameter_editor_usage_popup(mock_parent)

    # Assert (Then)
    mock_display.assert_called_once()
    args = mock_display.call_args[0]
    assert args[0] is mock_parent
    assert args[1] is usage_popup_window
    assert args[3] == "parameter_editor"
    assert args[4] == "690x360"
    assert args[5] is instructions_widget
    instructions_widget.config.assert_called_with(state=tk.DISABLED)


def test_display_parameter_editor_usage_popup_skips_when_parent_missing(mocker: MockerFixture) -> None:
    """
    Helper aborts when the intended parent window no longer exists.

    GIVEN: A parent Tk mock that reports it has been destroyed
    WHEN: The parameter editor usage popup helper runs
    THEN: No popup-related constructors or displays are triggered
    """
    # Arrange (Given)
    parent = MagicMock(spec=tk.Tk)
    parent.winfo_exists.return_value = False
    mock_display = mocker.patch(f"{MODULE}.UsagePopupWindow.display")
    mock_base_window = mocker.patch(f"{MODULE}.BaseWindow")

    # Act (When)
    display_parameter_editor_usage_popup(parent)

    # Assert (Then)
    mock_display.assert_not_called()
    mock_base_window.assert_not_called()


def test_display_component_editor_usage_popup_invokes_usage_window(mocker: MockerFixture, mock_parent: MagicMock) -> None:
    """
    Component editor helper shows the popup when its parent window is alive.

    GIVEN: A Tk parent window and patched UI helpers
    WHEN: The component editor usage helper runs
    THEN: UsagePopupWindow.display is called with the expected arguments
    """
    # Arrange (Given)
    usage_popup_window = MagicMock()
    usage_popup_window.main_frame = MagicMock()
    mocker.patch(f"{MODULE}.BaseWindow", return_value=usage_popup_window)
    instructions_widget = MagicMock()
    mocker.patch(f"{MODULE}.RichText", return_value=instructions_widget)
    mock_display = mocker.patch(f"{MODULE}.UsagePopupWindow.display")

    # Act (When)
    display_component_editor_usage_popup(mock_parent)

    # Assert (Then)
    mock_display.assert_called_once()
    args = mock_display.call_args[0]
    assert args[0] is mock_parent
    assert args[1] is usage_popup_window
    assert args[2] == "How to use the component editor window"
    assert args[3] == "component_editor"
    assert args[4] == "690x210"
    assert args[5] is instructions_widget
    instructions_widget.config.assert_called_with(state=tk.DISABLED)


def test_display_component_editor_usage_popup_skips_when_parent_missing(mocker: MockerFixture) -> None:
    """
    Component editor helper exits gracefully when the parent window vanished.

    GIVEN: A parent Tk mock that reports it does not exist anymore
    WHEN: The component editor usage helper executes
    THEN: No popup window is constructed or displayed
    """
    # Arrange (Given)
    parent = MagicMock(spec=tk.Tk)
    parent.winfo_exists.return_value = False
    mock_display = mocker.patch(f"{MODULE}.UsagePopupWindow.display")
    mock_base_window = mocker.patch(f"{MODULE}.BaseWindow")

    # Act (When)
    result = display_component_editor_usage_popup(parent)

    # Assert (Then)
    assert result is None
    mock_base_window.assert_not_called()
    mock_display.assert_not_called()


def test_display_workflow_explanation_creates_links(mocker: MockerFixture) -> None:
    """
    Workflow popup helper builds link-rich content and returns the constructed window.

    GIVEN: A mocked popup window and filesystem hook supplying the workflow image
    WHEN: The workflow explanation helper is invoked
    THEN: The popup shows the image and clickable links to documentation resources
    """
    # Arrange (Given)
    popup_window = MagicMock()
    popup_window.main_frame = MagicMock()
    popup_window.root = MagicMock()
    popup_window.put_image_in_label.return_value = MagicMock()
    mocker.patch(f"{MODULE}.BaseWindow", return_value=popup_window)
    image_path = str(Path("workflow.png"))
    mocker.patch(f"{MODULE}.ProgramSettings.workflow_image_filepath", return_value=image_path)

    rich_text_instances: list[MagicMock] = []

    def _rich_text_factory(*_args, **_kwargs) -> MagicMock:
        widget = MagicMock()
        rich_text_instances.append(widget)
        return widget

    mocker.patch(f"{MODULE}.RichText", side_effect=_rich_text_factory)

    # Act (When)
    popup = display_workflow_explanation()

    # Assert (Then)
    assert popup is popup_window
    assert popup_window.put_image_in_label.called
    assert len(rich_text_instances) >= 2
    link_widget = rich_text_instances[1]
    link_widget.insert_clickable_link.assert_any_call(
        "quick start guide",
        "quickstart_link",
        "https://ardupilot.github.io/MethodicConfigurator/#quick-start",
    )
    link_widget.insert_clickable_link.assert_any_call(
        "YouTube tutorials",
        "YouTube_link",
        "https://www.youtube.com/playlist?list=PL1oa0qoJ9W_89eMcn4x2PB6o3fyPbheA9",
    )


def test_display_workflow_explanation_handles_missing_image(mocker: MockerFixture) -> None:
    """
    Workflow helper falls back to a label when the image asset is missing.

    GIVEN: A popup window whose image loader raises FileNotFoundError
    WHEN: The workflow explanation helper attempts to place the image
    THEN: A fallback ttk.Label is packed so the user still sees guidance
    """
    # Arrange (Given)
    popup_window = MagicMock()
    popup_window.main_frame = MagicMock()
    popup_window.root = MagicMock()
    popup_window.put_image_in_label.side_effect = FileNotFoundError()
    mocker.patch(f"{MODULE}.BaseWindow", return_value=popup_window)
    missing_image_path = str(Path("missing_workflow.png"))
    mocker.patch(f"{MODULE}.ProgramSettings.workflow_image_filepath", return_value=missing_image_path)
    mocker.patch(f"{MODULE}.RichText", return_value=MagicMock())
    fallback_label = MagicMock()
    mocker.patch(f"{MODULE}.ttk.Label", return_value=fallback_label)

    # Act (When)
    display_workflow_explanation()

    # Assert (Then)
    fallback_label.pack.assert_called_once()


def test_confirm_component_properties_delegates_to_confirmation_window(mocker: MockerFixture, mock_parent: MagicMock) -> None:
    """
    Component confirmation helper delegates to ConfirmationPopupWindow.

    GIVEN: A valid parent window and patched confirmation popup dependencies
    WHEN: Component confirmation is requested
    THEN: The confirmation popup displays and returns True
    """
    # Arrange (Given)
    popup_window = MagicMock()
    mocker.patch(f"{MODULE}.BaseWindow", return_value=popup_window)
    mocker.patch(f"{MODULE}.RichText", return_value=MagicMock())
    mock_confirm = mocker.patch(f"{MODULE}.ConfirmationPopupWindow.display", return_value=True)

    # Act (When)
    result = confirm_component_properties(mock_parent)

    # Assert (Then)
    assert result is True
    mock_confirm.assert_called_once()
    args = mock_confirm.call_args[0]
    assert args[3] == "component_editor_validation"


def test_confirm_component_properties_skips_when_parent_missing(mocker: MockerFixture) -> None:
    """
    Confirmation helper exits quietly when the parent window vanished.

    GIVEN: A parent Tk mock that reports it no longer exists
    WHEN: Component confirmation is requested
    THEN: The helper returns False without opening UI elements
    """
    # Arrange (Given)
    parent = MagicMock(spec=tk.Tk)
    parent.winfo_exists.return_value = False
    mock_confirm = mocker.patch(f"{MODULE}.ConfirmationPopupWindow.display")

    # Act (When)
    result = confirm_component_properties(parent)

    # Assert (Then)
    assert result is False
    mock_confirm.assert_not_called()
