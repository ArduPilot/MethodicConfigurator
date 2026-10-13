#!/usr/bin/env python3

"""
Unit tests for flight-controller banner window data formatting.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import sys
import tkinter as tk
from collections.abc import Generator
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import Mock

import pytest

from ardupilot_methodic_configurator import frontend_tkinter_fc_banner_window as banner_window
from ardupilot_methodic_configurator.frontend_tkinter_navigation_lock import NavigationLock


@pytest.fixture(name="live_banner_window", params=["win32", "darwin"])
def _live_banner_window(
    monkeypatch: pytest.MonkeyPatch,
    request: pytest.FixtureRequest,
) -> tuple[banner_window.FlightControllerBannerWindow, Mock, Mock, NavigationLock]:
    """Construct the real window using mocked Tk widgets and a live diagnostics provider."""
    monkeypatch.setattr(banner_window, "sys_platform", request.param)
    root = Mock()
    root.after.return_value = "diagnostics-poll"
    text = Mock()
    text.yview.return_value = (0.0, 1.0)
    provider = Mock(return_value=["ArduCopter V4.6.3", "Runtime warning"])
    lock = NavigationLock()

    def initialize(window: banner_window.FlightControllerBannerWindow, _parent: object) -> None:
        window.root = root
        window.main_frame = Mock()
        window.dpi_scaling_factor = 1.0

    monkeypatch.setattr(banner_window.BaseWindow, "__init__", initialize)
    monkeypatch.setattr(banner_window.BaseWindow, "center_window", Mock())
    monkeypatch.setattr(banner_window.tk, "PanedWindow", Mock())
    monkeypatch.setattr(banner_window.ttk, "LabelFrame", _FakeWidget)
    monkeypatch.setattr(banner_window.ttk, "Button", Mock())
    monkeypatch.setattr(banner_window.ttk, "Frame", _FakeWidget)
    monkeypatch.setattr(banner_window.ttk, "Treeview", _FakeTree)
    monkeypatch.setattr(banner_window.ttk, "Scrollbar", _FakeScrollbar)
    monkeypatch.setattr(banner_window, "_DeviceTreeTooltip", Mock())
    monkeypatch.setattr(banner_window.scrolledtext, "ScrolledText", Mock(return_value=text))
    window = banner_window.FlightControllerBannerWindow(
        root, ["ArduCopter V4.6.3"], status_text_provider=provider, navigation_lock=lock
    )
    return window, text, provider, lock


def test_diagnostics_sections_have_two_vertical_resize_dividers(
    live_banner_window: tuple[banner_window.FlightControllerBannerWindow, Mock, Mock, NavigationLock],
) -> None:
    """
    Diagnostics sections share a vertically resizable container.

    GIVEN: The diagnostics popup is open on Windows or macOS
    WHEN: The user wants to allocate more height to one section
    THEN: Both section boundaries are draggable and the section titles retain a minimum height
    """
    window, _text, _provider, _lock = live_banner_window
    panes_constructor = cast("Mock", banner_window.tk.PanedWindow)
    panes_constructor.assert_called_once_with(  # pylint: disable=no-member
        window.main_frame,
        orient=tk.VERTICAL,
        sashwidth=6,
        sashrelief=tk.RAISED,
        sashcursor="sb_v_double_arrow",
        opaqueresize=True,
        borderwidth=0,
    )
    panes = cast("Mock", window.section_panes)
    assert [call.args[0].kwargs["text"] for call in panes.add.call_args_list] == [
        "FC banner",
        "Latest 100 STATUSTEXT messages",
        "Detected devices",
    ]
    assert all(call.kwargs == {"minsize": 60, "stretch": "always", "sticky": "nsew"} for call in panes.add.call_args_list)


@pytest.fixture(name="resizable_banner_window")
def _resizable_banner_window(
    root: tk.Tk, monkeypatch: pytest.MonkeyPatch
) -> Generator[banner_window.FlightControllerBannerWindow, None, None]:
    """Create real off-screen widgets for native sash-resizing tests on supported CI platforms."""
    if sys.platform == "darwin":
        pytest.skip("Real widget geometry updates are unsafe on headless macOS runners.")
    monkeypatch.setattr(banner_window.BaseWindow, "_get_dpi_scaling_factor", lambda _self: 1.0)
    monkeypatch.setattr(banner_window.BaseWindow, "center_window", Mock())
    monkeypatch.setattr(banner_window, "_DeviceTreeTooltip", Mock())
    window = banner_window.FlightControllerBannerWindow(root, ["ArduCopter V4.6.3"])
    try:
        window.root.tk.call("wm", "transient", window.root, "")
        window.root.geometry("800x680+20000+20000")
        # Allow native window mapping before checking pane sizes; this fixture skips macOS.
        window.root.after(50, window.root.quit)
        window.root.mainloop()
        window.root.update_idletasks()
        yield window
    finally:
        window.root.destroy()


@pytest.mark.parametrize("sash_index", [0, 1])
@pytest.mark.parametrize("distance", [-40, 40])
@pytest.mark.skipif(sys.platform == "darwin", reason="Real widget geometry updates are unsafe on headless macOS.")
def test_user_can_drag_each_diagnostics_divider_up_and_down(
    resizable_banner_window: banner_window.FlightControllerBannerWindow, sash_index: int, distance: int
) -> None:
    """
    Both boundaries resize their adjacent sections using Tk's native sash positioning.

    GIVEN: Three visible diagnostic sections separated by two dividers
    WHEN: The user drags either divider up or down
    THEN: The two adjacent sections change height and the third section stays unchanged
    """
    window = resizable_banner_window
    panes = window.section_panes
    frames = [window.root.nametowidget(str(pane)) for pane in panes.panes()]
    heights_before = [frame.winfo_height() for frame in frames]
    x, y = panes.sash_coord(sash_index)
    # Native drag bindings use sash placement; avoid DPI-sensitive synthetic pointer events.
    panes.sash_place(sash_index, x, y + distance)
    window.root.update_idletasks()

    heights_after = [frame.winfo_height() for frame in frames]
    assert heights_after[sash_index] == heights_before[sash_index] + distance
    assert heights_after[sash_index + 1] == heights_before[sash_index + 1] - distance
    unchanged_index = 2 if sash_index == 0 else 0
    assert heights_after[unchanged_index] == heights_before[unchanged_index]


def test_user_sees_fresh_runtime_messages_without_banner_duplicates(
    live_banner_window: tuple[banner_window.FlightControllerBannerWindow, Mock, Mock, NavigationLock],
) -> None:
    """GIVEN a live provider, WHEN the popup opens and refreshes, THEN new runtime text appears without the banner."""
    window, text, provider, lock = live_banner_window
    assert text.insert.call_args.args[1] == "Runtime warning"
    assert lock.locked
    if banner_window.sys_platform == "darwin":
        window.root.grab_set.assert_not_called()
    else:
        window.root.grab_set.assert_called_once()
    provider.return_value = ["ArduCopter V4.6.3", "Runtime warning", "New diagnostic"]
    window._refresh_status_text()  # pylint: disable=protected-access
    assert text.insert.call_args.args[1] == "Runtime warning\nNew diagnostic"


def test_refresh_preserves_the_position_of_a_user_reading_older_messages(
    live_banner_window: tuple[banner_window.FlightControllerBannerWindow, Mock, Mock, NavigationLock],
) -> None:
    """GIVEN a user scrolled upwards, WHEN new text arrives, THEN refreshing does not jump to the bottom."""
    window, text, provider, _lock = live_banner_window
    text.yview.return_value = (0.25, 0.5)
    text.see.reset_mock()
    provider.return_value = ["Runtime warning", "New diagnostic"]
    window._refresh_status_text()  # pylint: disable=protected-access
    text.yview_moveto.assert_called_once_with(0.25)
    text.see.assert_not_called()


def test_closing_the_popup_stops_reception_and_releases_navigation(
    live_banner_window: tuple[banner_window.FlightControllerBannerWindow, Mock, Mock, NavigationLock],
) -> None:
    """GIVEN a polling popup, WHEN it is destroyed, THEN its timer is cancelled and other FC operations can resume."""
    window, _text, provider, lock = live_banner_window
    window._on_destroy(SimpleNamespace(widget=window.root))  # pylint: disable=protected-access
    window.root.after_cancel.assert_called_once_with("diagnostics-poll")
    assert not lock.locked
    provider.reset_mock()
    window._refresh_status_text()  # pylint: disable=protected-access
    provider.assert_not_called()


# pylint: disable=protected-access


class _FakeWidget:
    """Small Tk widget substitute for testing table setup without a display."""

    def __init__(self, *_args, **kwargs) -> None:
        self.kwargs = kwargs
        self.configure_options: dict[str, Any] = {}

    def pack(self, **_kwargs) -> None:
        pass

    def grid(self, **_kwargs) -> None:
        pass

    def configure(self, **kwargs) -> None:
        self.configure_options.update(kwargs)

    def rowconfigure(self, *_args, **_kwargs) -> None:
        pass

    def columnconfigure(self, *_args, **_kwargs) -> None:
        pass


class _FakeScrollbar(_FakeWidget):
    """Scrollbar substitute that accepts Treeview position updates."""

    def set(self, _first: float, _last: float) -> None:
        pass


class _FakeTree(_FakeWidget):
    def __init__(self, *_args, **kwargs) -> None:
        super().__init__(*_args, **kwargs)
        self.values: dict[str, tuple[str, ...]] = {}
        self.tags: dict[str, tuple[str, ...]] = {}
        self.children: list[str] = []
        self.headings: dict[str, dict[str, Any]] = {}
        self.columns: dict[str, dict[str, Any]] = {}

    def tag_configure(self, *_args, **_kwargs) -> None:
        pass

    def heading(self, column: str, **kwargs) -> None:
        self.headings[column] = kwargs

    def column(self, column: str, **kwargs) -> None:
        self.columns[column] = kwargs

    def insert(self, _parent: str, _index: str, iid: str, values: tuple[str, ...], tags: tuple[str, ...]) -> None:
        self.children.append(iid)
        self.values[iid] = values
        self.tags[iid] = tags

    def yview(self) -> None:
        pass

    def xview(self) -> None:
        pass

    def get_children(self, _parent: str = "") -> tuple[str, ...]:
        return tuple(self.children)

    def set(self, item: str, column: str) -> str:
        columns = self.kwargs["columns"]
        return str(self.values[item][columns.index(column)])

    def move(self, item: str, _parent: str, index: int) -> None:
        self.children.remove(item)
        self.children.insert(index, item)

    def item(self, item: str, **kwargs) -> dict[str, tuple[str, ...]]:
        if "tags" in kwargs:
            self.tags[item] = kwargs["tags"]
        return {"tags": self.tags[item]}


def test_device_table_uses_requested_columns_and_stripes_rows(monkeypatch: pytest.MonkeyPatch) -> None:
    """The visible Treeview omits DevID and displays the supplied device rows."""
    tree = _FakeTree()
    scrollbars: list[dict[str, Any]] = []
    monkeypatch.setattr(banner_window.ttk, "Frame", _FakeWidget)
    monkeypatch.setattr(banner_window.ttk, "Treeview", lambda *_args, **kwargs: _init_tree(tree, kwargs))
    monkeypatch.setattr(
        banner_window.ttk,
        "Scrollbar",
        lambda *_args, **kwargs: _create_fake_scrollbar(scrollbars, kwargs),
    )
    rows = [
        ("BARO1", "I2C", 0, 118, "BARO_DPS310", "BARO1_DEVID: 423425"),
        ("INS_ACC", "SPI", 1, 1, "INS_ICM42688", "INS_ACC_ID: 3408138"),
    ]
    monkeypatch.setattr(banner_window, "device_rows", lambda _params: rows)
    tooltip_texts: dict[str, str] = {}
    monkeypatch.setattr(
        banner_window,
        "_DeviceTreeTooltip",
        lambda _tree, texts: tooltip_texts.update(texts),
    )
    window = banner_window.FlightControllerBannerWindow.__new__(banner_window.FlightControllerBannerWindow)
    window._sort_column = None
    window._sort_descending = False

    window._create_device_table(_FakeWidget(), {})

    assert tree.kwargs["columns"] == ("DeviceName", "BusType", "Bus", "Address", "DevType")
    assert tree.kwargs["show"] == "headings"
    assert tree.headings["DeviceName"]["text"] == "Device"
    assert tree.headings["BusType"]["text"] == "Bus type"
    assert tree.headings["DevType"]["text"] == "Device type"
    assert tree.get_children() == ("device-0", "device-1")
    assert tree.tags == {"device-0": (), "device-1": ("striped",)}
    assert tooltip_texts == {
        "device-0": "BARO1_DEVID: 423425",
        "device-1": "INS_ACC_ID: 3408138",
    }
    assert len(scrollbars) == 1


def _init_tree(tree: _FakeTree, kwargs: dict[str, Any]) -> _FakeTree:
    """Initialize a fake Treeview with the constructor options under test."""
    tree.kwargs = kwargs
    return tree


def _create_fake_scrollbar(scrollbars: list[dict[str, Any]], kwargs: dict[str, Any]) -> _FakeScrollbar:
    """Record scrollbar creation while returning a widget substitute."""
    scrollbars.append(kwargs)
    return _FakeScrollbar(**kwargs)


@pytest.mark.parametrize("row_count", [0, 2, 8, 9])
def test_user_can_scroll_devices_after_shortening_the_device_pane(monkeypatch: pytest.MonkeyPatch, row_count: int) -> None:
    """
    The device scrollbar remains available regardless of the initial number of rows.

    GIVEN: A device table that may initially fit all its rows
    WHEN: The user shortens the device pane with its divider
    THEN: A vertical scrollbar is available to reach rows that no longer fit
    """
    tree = _FakeTree()
    scrollbars: list[dict[str, Any]] = []
    rows = [(f"INS_ACC{index}", "SPI", index, index, "IMU", f"INS_ACC{index}_ID: {index}") for index in range(row_count)]
    monkeypatch.setattr(banner_window.ttk, "Frame", _FakeWidget)
    monkeypatch.setattr(banner_window.ttk, "Treeview", lambda *_args, **kwargs: _init_tree(tree, kwargs))
    monkeypatch.setattr(
        banner_window.ttk,
        "Scrollbar",
        lambda *_args, **kwargs: _create_fake_scrollbar(scrollbars, kwargs),
    )
    monkeypatch.setattr(banner_window, "device_rows", lambda _params: rows)
    monkeypatch.setattr(banner_window, "_DeviceTreeTooltip", lambda _tree, _texts: None)
    window = banner_window.FlightControllerBannerWindow.__new__(banner_window.FlightControllerBannerWindow)
    window._sort_column = None
    window._sort_descending = False

    window._create_device_table(_FakeWidget(), {})

    assert len(tree.get_children()) == row_count
    assert len(scrollbars) == 1
    assert scrollbars[0]["orient"] == banner_window.tk.VERTICAL
    assert "yscrollcommand" in tree.configure_options


def test_device_table_sort_orders_values_and_reapplies_stripes() -> None:
    """Sorting rearranges rows and recalculates alternating row tags."""
    window = banner_window.FlightControllerBannerWindow.__new__(banner_window.FlightControllerBannerWindow)
    window.device_tree = _FakeTree(columns=window.DEVICE_COLUMNS)
    window._sort_column = None
    window._sort_descending = False
    for iid, bus in (("device-0", "4"), ("device-1", "1"), ("device-2", "2")):
        window.device_tree.insert("", "end", iid=iid, values=(iid, "SPI", bus, "1", "IMU"), tags=())

    window._sort_by_column("Bus")

    assert window.device_tree.get_children() == ("device-1", "device-2", "device-0")
    assert [window.device_tree.tags[iid] for iid in window.device_tree.get_children()] == [(), ("striped",), ()]
    assert window.device_tree.headings["Bus"]["text"].endswith("▲")

    window._sort_by_column("Bus")
    assert window.device_tree.get_children() == ("device-0", "device-2", "device-1")
    assert window.device_tree.headings["Bus"]["text"].endswith("▼")


def test_device_tooltip_uses_parameter_text_only_in_first_column(monkeypatch: pytest.MonkeyPatch) -> None:
    """Hovering a device name shows its source parameter and value."""
    tooltip = banner_window._DeviceTreeTooltip.__new__(banner_window._DeviceTreeTooltip)
    tooltip.position_at_pointer = True
    tooltip.widget = SimpleNamespace(
        identify_row=lambda _y: "device-0",
        identify_column=lambda _x: "#1",
    )
    tooltip.tooltip_texts = {"device-0": "BARO1_DEVID: 423425"}
    tooltip.text = ""
    tooltip.force_hide = lambda: None
    shown_texts: list[str] = []
    monkeypatch.setattr(banner_window.Tooltip, "schedule_show", lambda self, _event: shown_texts.append(self.text))

    tooltip.schedule_show(SimpleNamespace(x=10, y=10))
    assert shown_texts == ["BARO1_DEVID: 423425"]

    tooltip.widget.identify_column = lambda _x: "#2"
    tooltip.schedule_show(SimpleNamespace(x=200, y=10))
    assert shown_texts == ["BARO1_DEVID: 423425"]
    assert tooltip.text == ""


def test_device_tooltip_is_positioned_near_pointer(monkeypatch: pytest.MonkeyPatch) -> None:
    """Tooltip placement follows the pointer instead of the Treeview corner."""
    tooltip = banner_window._DeviceTreeTooltip.__new__(banner_window._DeviceTreeTooltip)
    positions: list[str] = []
    tooltip.widget = SimpleNamespace(
        winfo_toplevel=object,
        winfo_pointerx=lambda: 200,
        winfo_pointery=lambda: 300,
    )
    tooltip.tooltip = SimpleNamespace(
        update_idletasks=lambda: None,
        winfo_reqwidth=lambda: 150,
        winfo_reqheight=lambda: 40,
        geometry=positions.append,
    )
    monkeypatch.setattr(
        "ardupilot_methodic_configurator.frontend_tkinter_show.get_monitor_bounds",
        lambda _widget: (0, 0, 1000, 800),
    )

    tooltip.position_tooltip()

    assert positions == ["+212+312"]
