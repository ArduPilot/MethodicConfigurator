"""
Owner-scoped locking of navigation controls during long-running GUI operations.

SPDX-FileCopyrightText: 2026 ArduPilot Contributors

SPDX-License-Identifier: GPL-3.0-or-later
"""

import tkinter as tk
from contextlib import suppress
from tkinter import ttk
from typing import Protocol, cast


class _StatefulWidget(Protocol):
    """Typed subset of ttk's state API, including environments with older Tk stubs."""

    def instate(self, statespec: tuple[str, ...]) -> bool: ...

    def state(self, statespec: tuple[str, ...]) -> tuple[str, ...]: ...


class NavigationLock:
    """Disable registered controls until every operation has released its lock."""

    def __init__(self) -> None:
        self._owners: set[object] = set()
        self._widgets: dict[ttk.Widget, bool] = {}

    @property
    def locked(self) -> bool:
        """Whether any operation still owns the navigation lock."""
        return bool(self._owners)

    def register(self, widget: ttk.Widget) -> None:
        """Register a navigation control, including controls created while locked."""
        if widget in self._widgets:
            return
        self._widgets[widget] = self._is_disabled(widget)
        if self.locked:
            self._set_disabled(widget, disabled=True)

    def acquire(self, owner: object) -> None:
        """Acquire an idempotent lock for an operation without affecting other owners."""
        was_locked = self.locked
        self._owners.add(owner)
        if was_locked:
            return
        for widget in self._widgets:
            with suppress(tk.TclError):
                self._widgets[widget] = self._is_disabled(widget)
                self._set_disabled(widget, disabled=True)

    def release(self, owner: object) -> None:
        """Restore prior disabled states only when the last owner releases the lock."""
        if owner not in self._owners:
            return
        self._owners.remove(owner)
        if self.locked:
            return
        for widget, was_disabled in self._widgets.items():
            with suppress(tk.TclError):
                self._set_disabled(widget, disabled=was_disabled)

    @staticmethod
    def _is_disabled(widget: ttk.Widget) -> bool:
        """Read the disabled bit without disturbing readonly and other ttk state bits."""
        return cast("_StatefulWidget", widget).instate(("disabled",))

    @staticmethod
    def _set_disabled(widget: ttk.Widget, *, disabled: bool) -> None:
        """Change only the disabled bit."""
        cast("_StatefulWidget", widget).state(("disabled",) if disabled else ("!disabled",))
