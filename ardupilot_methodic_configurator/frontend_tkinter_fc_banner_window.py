"""
Display flight-controller banner, status messages, and detected devices.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import tkinter as tk
from collections.abc import Callable
from contextlib import suppress
from functools import partial
from sys import platform as sys_platform
from tkinter import scrolledtext, ttk
from typing import cast

from ardupilot_methodic_configurator import _
from ardupilot_methodic_configurator.backend_internet import webbrowser_open_url
from ardupilot_methodic_configurator.data_model_fc_diagnostics import device_rows
from ardupilot_methodic_configurator.frontend_tkinter_base_window import BaseWindow
from ardupilot_methodic_configurator.frontend_tkinter_navigation_lock import NavigationLock
from ardupilot_methodic_configurator.frontend_tkinter_show import Tooltip, position_tooltip_at_pointer


class FlightControllerBannerWindow(BaseWindow):  # pylint: disable=too-many-instance-attributes
    """Popup showing the FC boot banner, recent status text, and detected devices."""

    DEVICE_COLUMNS = ("DeviceName", "BusType", "Bus", "Address", "DevType", "Priority")
    DEVICE_TABLE_HEIGHT = 8

    def __init__(  # pylint: disable=too-many-arguments
        self,
        parent: tk.Tk | tk.Toplevel,
        banner_text: list[str],
        status_text: list[str] | None = None,
        fc_parameters: dict[str, float] | None = None,
        *,
        status_text_provider: Callable[[], list[str]] | None = None,
        navigation_lock: NavigationLock | None = None,
    ) -> None:
        super().__init__(parent)
        self.root.title(_("Flight Controller Banner"))
        self.root.geometry(self.calculate_scaled_geometry(800, 680))
        self.root.minsize(650, 520)
        self._sort_column: str | None = None
        self._sort_descending = False
        self._status_text_provider = status_text_provider
        self._parent_navigation_lock = navigation_lock
        self._poll_job: str | None = None
        self._banner_text = set(banner_text)
        self._last_status_text = self._runtime_text(status_text or [])

        self.section_panes = tk.PanedWindow(
            self.main_frame,
            orient=tk.VERTICAL,
            sashwidth=round(6 * self.dpi_scaling_factor),
            sashrelief=tk.RAISED,
            sashcursor="sb_v_double_arrow",
            opaqueresize=True,
            borderwidth=0,
        )
        self.section_panes.pack(fill=tk.BOTH, expand=True, padx=8, pady=(8, 4))
        minimum_section_height = round(60 * self.dpi_scaling_factor)

        banner_frame = ttk.LabelFrame(self.section_panes, text=_("FC banner"))
        self.section_panes.add(banner_frame, minsize=minimum_section_height, stretch="always", sticky="nsew")
        self._create_text_buffer(banner_frame, banner_text, _("No banner messages captured."))

        status_frame = ttk.LabelFrame(self.section_panes, text=_("Latest 100 STATUSTEXT messages"))
        self.section_panes.add(status_frame, minsize=minimum_section_height, stretch="always", sticky="nsew")
        self.status_text_widget = self._create_text_buffer(
            status_frame, self._last_status_text, _("No status messages captured.")
        )
        self.status_text_widget.see("1.0")

        devices_frame = ttk.LabelFrame(self.section_panes, text=_("Detected devices"))
        self.section_panes.add(devices_frame, minsize=minimum_section_height, stretch="always", sticky="nsew")
        self._create_device_table(devices_frame, fc_parameters or {})

        buttons_frame = ttk.Frame(self.main_frame)
        buttons_frame.pack(fill=tk.X, padx=8, pady=(4, 8))
        help_button = ttk.Button(
            buttons_frame,
            text=_("Help"),
            command=lambda: webbrowser_open_url("https://ardupilot.github.io/MethodicConfigurator/USERMANUAL_fc_banner.html"),
        )
        help_button.pack(side=tk.LEFT, padx=4)
        close_button = ttk.Button(buttons_frame, text=_("Close"), command=self.root.destroy)
        close_button.pack(side=tk.RIGHT, padx=4)
        self.root.bind("<Destroy>", self._on_destroy, "+")
        self.root.transient(parent)
        # On macOS, grab_set() causes UI freeze (issue #1264), so skip it.
        if sys_platform != "darwin":
            self.root.grab_set()
        if navigation_lock is not None:
            navigation_lock.acquire(self)
        BaseWindow.center_window(self.root, parent)
        if status_text_provider is not None:
            self._refresh_status_text()

    def _runtime_text(self, lines: list[str]) -> list[str]:
        """Exclude banner information even when a caller supplies overlapping snapshots."""
        return [line for line in lines if self._status_message(line).strip() not in self._banner_text]

    @staticmethod
    def _status_message(line: str) -> str:
        """Remove the display-only arrival timestamp before comparing a line with the banner."""
        if line.startswith("["):
            _timestamp, separator, message = line.partition("] ")
            if separator:
                return message
        return line

    def _refresh_status_text(self) -> None:
        """Refresh while this modal view owns the connection, preserving the reader's scroll position."""
        self._poll_job = None
        if self._status_text_provider is None:
            return
        lines = self._runtime_text(self._status_text_provider())
        if lines != self._last_status_text:
            top, _bottom = self.status_text_widget.yview()
            self.status_text_widget.configure(state=tk.NORMAL)
            self.status_text_widget.delete("1.0", tk.END)
            self.status_text_widget.insert(tk.END, "\n".join(lines) if lines else _("No status messages captured."))
            self.status_text_widget.configure(state=tk.DISABLED)
            if top <= 0.001:
                self.status_text_widget.see("1.0")
            else:
                self.status_text_widget.yview_moveto(top)
            self._last_status_text = lines
        self._poll_job = self.root.after(200, self._refresh_status_text)

    def _on_destroy(self, event: tk.Event) -> None:
        """Stop receiving and release navigation when this window or its parent is destroyed."""
        if event.widget is not self.root:
            return
        if self._poll_job is not None:
            with suppress(tk.TclError):
                self.root.after_cancel(self._poll_job)
            self._poll_job = None
        self._status_text_provider = None
        if self._parent_navigation_lock is not None:
            self._parent_navigation_lock.release(self)

    @staticmethod
    def _create_text_buffer(parent: ttk.LabelFrame, lines: list[str], empty_text: str) -> scrolledtext.ScrolledText:
        text_widget = scrolledtext.ScrolledText(parent, wrap=tk.WORD, height=5, state=tk.NORMAL)
        text_widget.pack(fill=tk.BOTH, expand=True, padx=6, pady=6)
        text_widget.insert(tk.END, "\n".join(lines) if lines else empty_text)
        text_widget.configure(state=tk.DISABLED)
        return text_widget

    def _create_device_table(self, parent: ttk.LabelFrame, fc_parameters: dict[str, float]) -> None:
        rows = device_rows(fc_parameters)
        container = ttk.Frame(parent)
        container.pack(fill=tk.BOTH, expand=True, padx=6, pady=6)
        tree = ttk.Treeview(container, columns=self.DEVICE_COLUMNS, show="headings", height=self.DEVICE_TABLE_HEIGHT)
        self.device_tree = tree
        tree.tag_configure("striped", background="#eeeeee")
        tree.grid(row=0, column=0, sticky="nsew")
        # A shortened device pane can overflow even with fewer than eight rows.
        vertical_scrollbar = ttk.Scrollbar(container, orient=tk.VERTICAL, command=tree.yview)
        tree.configure(yscrollcommand=vertical_scrollbar.set)
        vertical_scrollbar.grid(row=0, column=1, sticky="ns")
        container.rowconfigure(0, weight=1)
        container.columnconfigure(0, weight=1)

        widths = {"DeviceName": 190, "BusType": 100, "Bus": 70, "Address": 90, "DevType": 190, "Priority": 80}
        for column in self.DEVICE_COLUMNS:
            tree.heading(column, text=self._heading_text(column), command=partial(self._sort_by_column, column))
            tree.column(
                column,
                width=widths[column],
                anchor=tk.W if column in ("DeviceName", "DevType") else tk.CENTER,
            )

        for index, row in enumerate(rows):
            tags = ("striped",) if index % 2 else ()
            display_values = (*row[:-2], "" if row[-2] is None else row[-2])
            tree.insert("", tk.END, iid=f"device-{index}", values=display_values, tags=tags)
        self._device_tooltip = _DeviceTreeTooltip(tree, {f"device-{index}": row[-1] for index, row in enumerate(rows)})

    def _sort_by_column(self, column: str) -> None:
        """Sort the detected-device table by a clicked heading."""
        descending = self._sort_column == column and not self._sort_descending
        items = [(self.device_tree.set(item, column), item) for item in self.device_tree.get_children("")]
        unranked_items: list[tuple[str, str]] = []
        if column == "Priority":
            unranked_items = [pair for pair in items if not pair[0]]
            items = [pair for pair in items if pair[0]]
        try:
            items.sort(key=lambda pair: float(pair[0]), reverse=descending)
        except ValueError:
            items.sort(key=lambda pair: pair[0].casefold(), reverse=descending)
        items.extend(unranked_items)
        for index, (_value, item) in enumerate(items):
            self.device_tree.move(item, "", index)
        for index, item in enumerate(self.device_tree.get_children("")):
            self.device_tree.item(item, tags=("striped",) if index % 2 else ())
        if self._sort_column is not None:
            self.device_tree.heading(self._sort_column, text=self._heading_text(self._sort_column))
        self._sort_column = column
        self._sort_descending = descending
        arrow = " ▼" if descending else " ▲"
        self.device_tree.heading(column, text=self._heading_text(column) + arrow)

    @staticmethod
    def _heading_text(column: str) -> str:
        labels = {
            "DeviceName": _("Device"),
            "BusType": _("Bus type"),
            "Bus": _("Bus"),
            "Address": _("Address"),
            "DevType": _("Device type"),
            "Priority": _("Priority"),
        }
        return labels[column]


class _DeviceTreeTooltip(Tooltip):
    """Show the original parameter name and value over a displayed device name."""

    def __init__(self, widget: ttk.Treeview, tooltip_texts: dict[str, str]) -> None:
        self.tooltip_texts = tooltip_texts
        super().__init__(widget, "")
        widget.bind("<Motion>", self.schedule_show, "+")

    def position_tooltip(self) -> None:
        position_tooltip_at_pointer(self.widget, self.tooltip)

    def schedule_show(self, _event: tk.Event | None = None) -> None:
        """Update tooltip text for the row under the pointer, only in the first column."""
        if _event is None:
            return
        tree = cast("ttk.Treeview", self.widget)
        item = tree.identify_row(_event.y)
        if tree.identify_column(_event.x) != "#1" or item not in self.tooltip_texts:
            self.text = ""
            self.force_hide()
            return
        text = self.tooltip_texts[item]
        if text != self.text:
            self.force_hide()
            self.text = text
        super().schedule_show(_event)
