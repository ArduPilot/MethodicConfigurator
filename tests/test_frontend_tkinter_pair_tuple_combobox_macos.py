#!/usr/bin/env python3

"""
Darwin keyboard-navigation tests for PairTupleCombobox.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import tkinter as tk
from unittest.mock import patch

import pytest

from ardupilot_methodic_configurator.frontend_tkinter_pair_tuple_combobox import PairTupleCombobox

# pylint: disable=protected-access


@pytest.mark.parametrize(
    ("direction", "initial_index", "invalid_selection", "expected_index"),
    [("up", 1, False, 0), ("down", 0, False, 1), ("up", 0, True, 0), ("down", 0, True, 0)],
)
def test_macos_key_navigation_selects_and_emits_event_without_idle_update(
    tk_root: tk.Tk, direction: str, initial_index: int, invalid_selection: bool, expected_index: int
) -> None:
    """Arrow navigation on macOS changes selection and emits its event without processing idle tasks."""
    test_data = [("key1", "Value 1"), ("key2", "Value 2"), ("key3", "Value 3")]
    combobox = PairTupleCombobox(tk_root, test_data, "key1", "test_combo")
    handler = combobox._on_key_up if direction == "up" else combobox._on_key_down

    with (
        patch("ardupilot_methodic_configurator.frontend_tkinter_pair_tuple_combobox.platform_system", return_value="Darwin"),
        patch.object(combobox, "current") as mock_current,
        patch.object(combobox, "update_idletasks") as mock_update,
        patch.object(combobox, "event_generate") as mock_event_gen,
        patch.object(combobox, "selection_range") as mock_selection,
    ):
        mock_current.side_effect = [ValueError("Invalid selection"), None] if invalid_selection else None
        mock_current.return_value = initial_index

        result = handler(None)

        assert result == "break"
        assert mock_current.call_args_list[-1].args == (expected_index,)
        if not invalid_selection or direction == "down":
            mock_selection.assert_called_once_with(0, tk.END)
        mock_event_gen.assert_called_once_with("<<ComboboxSelected>>")
        mock_update.assert_not_called()
