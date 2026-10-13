#!/usr/bin/env python3

"""
Behavior tests for sections that preserve their contents when collapsed.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import tkinter as tk
from collections.abc import Iterator
from tkinter import ttk
from unittest.mock import patch

import pytest

from ardupilot_methodic_configurator.frontend_tkinter_collapsible_label_frame import CollapsibleLabelFrame

# pylint: disable=redefined-outer-name


@pytest.fixture
def section_window(root: tk.Tk) -> Iterator[tk.Toplevel]:
    """Provide a mapped section host without creating another Tk interpreter."""
    window = tk.Toplevel(root)
    window.geometry("500x400+0+0")
    window.update_idletasks()
    try:
        yield window
    finally:
        window.destroy()


@pytest.mark.parametrize("manager", ["pack", "grid"])
def test_user_can_collapse_and_restore_controls_without_losing_edits(section_window: tk.Toplevel, manager: str) -> None:
    """
    Collapsing leaves only the header and restores the same edited widgets.

    GIVEN: A section containing an edited entry and a checkbox
    WHEN: The user collapses and expands it repeatedly
    THEN: It shrinks around its header and retains widget identity, state and grid settings
    """
    section = CollapsibleLabelFrame(section_window, text="Advanced settings")
    if manager == "pack":
        section.pack(fill="x")
    else:
        section_window.columnconfigure(0, weight=1)
        section.grid(row=0, column=0, sticky="ew")
    entry = ttk.Entry(section.content_frame)
    entry.grid(row=0, column=0, sticky="ew", padx=12, pady=20)
    entry.insert(0, "Keep this edit")
    selected = tk.BooleanVar(section, value=True)
    checkbox = ttk.Checkbutton(section.content_frame, variable=selected)
    checkbox.grid(row=1, column=0, sticky="w", pady=10)
    section_window.update_idletasks()
    expanded_height = section.winfo_height()
    content_geometry = section.content_frame.grid_info()
    entry_geometry = entry.grid_info()
    assert isinstance(section.header_label, ttk.Label)
    assert str(section.cget("labelwidget")) == str(section.header_label)
    assert section.header_label.winfo_manager() == "labelframe"
    assert section.header_label not in section.grid_slaves()
    assert content_geometry["row"] == 0

    for _ in range(3):
        section.header_label.event_generate("<Button-1>")
        section_window.update_idletasks()

        assert not section.expanded
        assert section.header_label.winfo_ismapped()
        assert section.header_label.cget("text") == "▶ Advanced settings"
        assert not section.content_frame.winfo_ismapped()
        assert not entry.winfo_ismapped()
        assert section.winfo_height() < expanded_height
        assert entry.winfo_exists()
        assert entry.get() == "Keep this edit"
        assert selected.get()

        section.header_label.event_generate("<Button-1>")
        section_window.update_idletasks()

        assert section.expanded
        assert section.header_label.cget("text") == "▼ Advanced settings"
        assert entry.winfo_ismapped()
        assert checkbox.winfo_ismapped()
        assert section.winfo_height() == expanded_height
        assert section.content_frame.grid_info() == content_geometry
        assert entry.grid_info() == entry_geometry
        assert entry.get() == "Keep this edit"
        assert selected.get()


def test_user_can_start_collapsed_and_update_the_header(section_window: tk.Toplevel) -> None:
    """
    Updating the title does not unexpectedly reopen a collapsed section.

    GIVEN: A section initially collapsed with packed content
    WHEN: The title changes and the user later expands it
    THEN: The new title remains visible and the existing content is restored
    """
    section = CollapsibleLabelFrame(section_window, text="First step", expanded=False)
    section.pack(fill="x")
    label = ttk.Label(section.content_frame, text="Preserved content")
    label.pack()
    section_window.update_idletasks()

    section.set_title("Second step")
    section.set_expanded(False)
    section_window.update_idletasks()

    assert section.title == "Second step"
    assert section.header_label.cget("text") == "▶ Second step"
    assert section.header_label.winfo_ismapped()
    assert not label.winfo_ismapped()

    section.set_expanded(True)
    section.set_expanded(True)
    section_window.update_idletasks()

    assert section.expanded
    assert section.header_label.cget("text") == "▼ Second step"
    assert label.winfo_ismapped()


@pytest.mark.parametrize("key", ["<Return>", "<KeyPress-space>"])
def test_user_can_toggle_sections_using_the_keyboard(section_window: tk.Toplevel, key: str) -> None:
    """
    The header can be operated without a mouse.

    GIVEN: An expanded section with a focusable header
    WHEN: The user presses Enter or Space on the header
    THEN: The content collapses
    """
    section = CollapsibleLabelFrame(section_window, text="Settings")
    section.pack(fill="x")
    ttk.Entry(section.content_frame).pack()
    section_window.update_idletasks()
    section.header_label.focus_force()
    section_window.update_idletasks()

    section.header_label.event_generate(key)
    section_window.update_idletasks()

    assert not section.expanded
    assert section_window.focus_get() is section.header_label
    section.header_label.event_generate(key)
    section_window.update_idletasks()
    assert section.expanded


def test_collapsing_moves_focus_out_of_hidden_content(section_window: tk.Toplevel) -> None:
    """
    Keyboard focus is not left inside an invisible control.

    GIVEN: Focus is inside a nested content entry
    WHEN: The section is collapsed programmatically
    THEN: Focus moves to its persistent header
    """
    section = CollapsibleLabelFrame(section_window, text="Settings")
    section.pack(fill="x")
    nested = ttk.Frame(section.content_frame)
    nested.pack()
    entry = ttk.Entry(nested)
    entry.pack()
    section_window.update_idletasks()
    entry.focus_force()
    section_window.update_idletasks()

    section.set_expanded(False)
    section_window.update_idletasks()

    assert section_window.focus_get() is section.header_label
    assert not entry.winfo_ismapped()


def test_user_can_collapse_while_a_native_dialog_has_focus(section_window: tk.Toplevel) -> None:
    """A native dialog's unknown focus window must not interrupt collapsing."""
    section = CollapsibleLabelFrame(section_window, text="Settings")
    section.pack(fill="x")
    entry = ttk.Entry(section.content_frame)
    entry.pack()
    section_window.update_idletasks()

    with patch.object(section, "focus_get", side_effect=KeyError("__tk__messagebox")):
        section.set_expanded(False)

    assert not section.expanded
    assert not entry.winfo_ismapped()


def test_header_focus_indicator_handles_a_native_dialog(section_window: tk.Toplevel) -> None:
    """A native dialog does not leave the header underlined or raise an error."""
    section = CollapsibleLabelFrame(section_window, text="Settings")
    section.pack(fill="x")
    section_window.update_idletasks()

    with patch.object(section, "focus_get", side_effect=KeyError("__tk__messagebox")):
        section.header_label.event_generate("<FocusIn>")
        assert section.header_label.cget("underline") == 0
        section.header_label.event_generate("<FocusOut>")

    assert section.header_label.cget("underline") == -1


def test_user_can_tab_to_a_visibly_focused_title(section_window: tk.Toplevel) -> None:
    """
    A title label remains discoverable and operable in the keyboard focus order.

    GIVEN: A section between two other focusable controls
    WHEN: The user tabs onto its title, collapses it and tabs away
    THEN: Focus is indicated on the title and skips its hidden content
    """
    before = ttk.Entry(section_window)
    before.pack()
    section = CollapsibleLabelFrame(section_window, text="Settings")
    section.pack(fill="x")
    ttk.Entry(section.content_frame).pack()
    after = ttk.Entry(section_window)
    after.pack()
    section_window.update_idletasks()
    before.focus_force()
    section_window.update_idletasks()

    before.event_generate("<Tab>")
    section_window.update_idletasks()
    section.header_label.event_generate("<FocusIn>")

    assert section_window.focus_get() is section.header_label
    assert section.header_label.cget("underline") == 0

    section.header_label.event_generate("<space>")
    section.header_label.event_generate("<Tab>")
    section_window.update_idletasks()
    section.header_label.event_generate("<FocusOut>")

    assert section_window.focus_get() is after
    assert section.header_label.cget("underline") == -1


def test_user_can_collapse_sections_independently_by_clicking_only_the_title(section_window: tk.Toplevel) -> None:
    """
    Reused section instances do not share state or toggle on content clicks.

    GIVEN: Two sections with clickable content and different initial states
    WHEN: The user clicks content, then each title
    THEN: Only the chosen section changes state
    """
    first = CollapsibleLabelFrame(section_window, text="First")
    first.pack(fill="x")
    entry = ttk.Entry(first.content_frame)
    entry.pack()
    second = CollapsibleLabelFrame(section_window, text="Second", expanded=False)
    second.pack(fill="x")
    ttk.Label(second.content_frame, text="Content").pack()
    section_window.update_idletasks()

    entry.event_generate("<Button-1>")
    first.event_generate("<Button-1>")
    section_window.update_idletasks()
    assert first.expanded
    assert not second.expanded

    first.header_label.event_generate("<Button-1>")
    section_window.update_idletasks()
    assert not first.expanded
    assert not second.expanded

    second.header_label.event_generate("<Button-1>")
    section_window.update_idletasks()
    assert not first.expanded
    assert second.expanded
