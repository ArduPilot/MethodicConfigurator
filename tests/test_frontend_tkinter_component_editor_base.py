#!/usr/bin/env python3

"""
Component editor GUI tests.

This file is part of Ardupilot methodic configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2025 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import tkinter as tk
from unittest.mock import MagicMock, patch

import pytest

from ardupilot_methodic_configurator.backend_filesystem import LocalFilesystem
from ardupilot_methodic_configurator.frontend_tkinter_component_editor_base import ComponentEditorWindowBase


@pytest.fixture
def editor() -> ComponentEditorWindowBase:
    """Create a ComponentEditorWindowBase for testing with a real but hidden root window."""
    # Create mocks for all image-related operations
    with (
        patch(
            "ardupilot_methodic_configurator.frontend_tkinter_base.LocalFilesystem.application_icon_filepath"
        ) as mock_icon_path,
        patch("tkinter.PhotoImage") as mock_photo_image,
        patch("PIL.Image.open") as mock_pil_image_open,
        patch("tkinter.Tk.iconphoto"),
        patch("PIL.ImageTk.PhotoImage") as mock_imagetk_photo,
        patch("PIL.Image.new") as mock_pil_new,
    ):
        # Set up the mocks
        mock_icon_path.return_value = "dummy_path.png"

        # Mock tkinter PhotoImage
        mock_photo = MagicMock()
        mock_photo.name = "mock_photo_image"
        mock_photo_image.return_value = mock_photo

        # Mock PIL.Image
        mock_pil_image = MagicMock()
        mock_pil_image.size = (100, 100)
        mock_pil_image_open.return_value = mock_pil_image
        mock_pil_new.return_value = mock_pil_image

        # Mock PIL.ImageTk
        mock_imagetk = MagicMock()
        mock_imagetk.name = "mock_imagetk_photo"
        mock_imagetk_photo.return_value = mock_imagetk

        # Mock the filesystem
        filesystem = MagicMock(spec=LocalFilesystem)
        filesystem.vehicle_dir = "dummy_vehicle_dir"
        filesystem.load_vehicle_components_json_data.return_value = {"Components": {}}
        filesystem.vehicle_image_filepath = MagicMock(return_value="dummy_vehicle_image.png")

        # Create a real Tkinter root window but keep it hidden
        root = tk.Tk()
        root.withdraw()  # Hide the window

        # Create the editor
        editor = ComponentEditorWindowBase("1.0.0", filesystem)

        # Add save_component_json method mock needed by tests
        editor.save_component_json = MagicMock()

        yield editor

        # Clean up
        root.destroy()


@patch("tkinter.messagebox.askyesnocancel")
@patch("sys.exit")
def test_on_closing_save(mock_exit, mock_dialog, editor) -> None:
    """Test when user chooses to save before closing."""
    mock_dialog.return_value = True
    editor.save_component_json = MagicMock()

    editor.on_closing()

    mock_dialog.assert_called_once()
    editor.save_component_json.assert_called_once()
    mock_exit.assert_called_once_with(0)


@patch("tkinter.messagebox.askyesnocancel")
@patch("sys.exit")
def test_on_closing_no_save(mock_exit, mock_dialog, editor) -> None:
    """Test when user chooses not to save before closing."""
    mock_dialog.return_value = False

    editor.on_closing()

    mock_dialog.assert_called_once()
    editor.root.destroy.assert_called_once()
    mock_exit.assert_called_once_with(0)


@patch("tkinter.messagebox.askyesnocancel")
@patch("sys.exit")
def test_on_closing_cancel(mock_exit, mock_dialog, editor) -> None:
    """Test when user cancels the closing operation."""
    mock_dialog.return_value = None

    editor.on_closing()

    mock_dialog.assert_called_once()
    editor.root.destroy.assert_not_called()
    mock_exit.assert_not_called()
