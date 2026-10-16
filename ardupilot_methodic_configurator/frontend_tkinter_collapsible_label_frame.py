"""
A reusable labelled section with a clickable title and collapsible content.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import tkinter as tk
from tkinter import ttk
from typing import Any

from ardupilot_methodic_configurator import _
from ardupilot_methodic_configurator.frontend_tkinter_show import show_tooltip


class CollapsibleLabelFrame(ttk.LabelFrame):  # pylint: disable=too-many-ancestors
    """
    Hide content vertically without destroying widgets or their state.

    Put section controls inside ``content_frame`` using any geometry manager.
    Pack or grid the section without vertical expansion to let it shrink around
    its header. Titles passed to this widget should already be translated.
    Use ``set_title()`` to change the visible title after construction.

    Example::

        section = CollapsibleLabelFrame(parent, text=_("Advanced settings"))
        section.pack(fill="x", expand=False)
        ttk.Entry(section.content_frame).pack(fill="x")

    ``header_label`` occupies the native LabelFrame title position. It supports
    mouse clicks, Tab focus, Enter and Space, without adding a button row.
    This component has no parameter-editor or vehicle-model dependencies.
    """

    def __init__(self, master: tk.Misc, *, text: str, expanded: bool = True, **kwargs: Any) -> None:  # noqa: ANN401
        # The header replaces the native label, avoiding a duplicate title.
        super().__init__(master, **kwargs)
        self._title = text
        self._expanded = expanded
        self.columnconfigure(0, weight=1)
        label_style = f"{self.cget('style') or 'TLabelframe'}.Label"
        self.header_label = ttk.Label(self, cursor="hand2", takefocus=True, style=label_style)
        self.configure(labelwidget=self.header_label)
        for sequence in ("<Button-1>", "<Return>", "<space>"):
            self.header_label.bind(sequence, self._on_toggle_event)
        self.header_label.bind("<FocusIn>", self._on_header_focus)
        self.header_label.bind("<FocusOut>", self._on_header_focus)
        self.header_tooltip = show_tooltip(self.header_label, _("Show or hide this section's contents"))
        self.content_frame = ttk.Frame(self)
        self.content_frame.grid(row=0, column=0, sticky="nsew")
        # Grid keeps its last size when all children are removed. A one-pixel
        # placeholder makes Tk recalculate the native title/border minimum.
        self._collapsed_placeholder = ttk.Frame(self, width=1, height=1)
        self.rowconfigure(0, weight=int(expanded))
        if not expanded:
            self.content_frame.grid_remove()
            self._collapsed_placeholder.grid(row=0, column=0)
        self._refresh_header()

    @property
    def expanded(self) -> bool:
        """Whether the section's content is displayed."""
        return self._expanded

    @property
    def title(self) -> str:
        """The section title without its disclosure indicator."""
        return self._title

    def set_title(self, text: str) -> None:
        """Update a translated title without changing the expansion state."""
        self._title = text
        self._refresh_header()

    def set_header_tooltip(self, text: str) -> None:
        """Replace the header hint with context-specific text, or clear it."""
        self.header_tooltip.force_hide()
        self.header_tooltip.text = text

    def set_expanded(self, expanded: bool) -> None:
        """Show or hide the existing content, retaining its geometry settings."""
        if expanded == self._expanded:
            return
        self._expanded = expanded
        if expanded:
            self._collapsed_placeholder.grid_remove()
            self.content_frame.grid()
        else:
            try:
                focused = self.focus_get()
            except KeyError:
                # Tkinter cannot resolve focus in a native message box on X11.
                focused = None
            if focused is not None and (focused is self.content_frame or str(focused).startswith(f"{self.content_frame}.")):
                self.header_label.focus_set()
            self.content_frame.grid_remove()
            self._collapsed_placeholder.grid(row=0, column=0)
        self.rowconfigure(0, weight=int(expanded))
        self._refresh_header()
        self.event_generate("<<CollapsibleToggled>>")

    def toggle(self) -> None:
        """Toggle the content without recreating any widgets."""
        self.set_expanded(not self._expanded)

    def _refresh_header(self) -> None:
        indicator = "▼" if self._expanded else "▶"
        self.header_label.configure(text=f"{indicator} {self._title}")

    def _on_toggle_event(self, _event: tk.Event) -> str:
        """Make the native title label operable by mouse, Enter and Space."""
        self.header_label.focus_set()
        self.toggle()
        return "break"

    def _on_header_focus(self, event: tk.Event) -> None:
        """Underline the disclosure indicator while the title has keyboard focus."""
        self.header_label.configure(underline=0 if event.type == tk.EventType.FocusIn else -1)
