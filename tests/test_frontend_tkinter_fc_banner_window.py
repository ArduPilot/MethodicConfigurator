#!/usr/bin/env python3

"""
Unit tests for flight-controller banner window data formatting.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import re
import sys
import tkinter as tk
from collections.abc import Generator
from datetime import datetime
from tkinter import ttk
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import Mock

import pytest
from pymavlink import mavutil
from pymavlink.dialects.v20 import ardupilotmega as mavlink

from ardupilot_methodic_configurator import frontend_tkinter_fc_banner_window as banner_window
from ardupilot_methodic_configurator.backend_flightcontroller_connection import FlightControllerConnection
from ardupilot_methodic_configurator.data_model_flightcontroller_info import FlightControllerInfo
from ardupilot_methodic_configurator.frontend_tkinter_navigation_lock import NavigationLock


@pytest.fixture(name="live_banner_window", params=["win32", "darwin"])
def _live_banner_window(
    monkeypatch: pytest.MonkeyPatch,
    request: pytest.FixtureRequest,
    dpi_scaling_factor: float,
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
        window.dpi_scaling_factor = dpi_scaling_factor

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


@pytest.fixture(name="dpi_scaling_factor", params=[1.0, 1.5, 2.0])
def _dpi_scaling_factor(request: pytest.FixtureRequest) -> float:
    """Exercise standard and HiDPI divider sizing without creating native windows."""
    return request.param


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
        sashwidth=round(6 * window.dpi_scaling_factor),
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
    minimum_height = round(60 * window.dpi_scaling_factor)
    assert all(
        call.kwargs == {"minsize": minimum_height, "stretch": "always", "sticky": "nsew"} for call in panes.add.call_args_list
    )


@pytest.fixture(name="resizable_banner_window")
def _resizable_banner_window(
    root: tk.Tk, monkeypatch: pytest.MonkeyPatch
) -> Generator[banner_window.FlightControllerBannerWindow, None, None]:
    """Create real off-screen widgets for native sash-resizing tests on supported CI platforms."""
    if sys.platform == "darwin":
        pytest.skip("Real widget geometry updates are unsafe on headless macOS runners.")
    monkeypatch.setattr(banner_window.BaseWindow, "_get_dpi_scaling_factor", lambda _self: 1.0)
    # BaseWindow creates child windows withdrawn; its real centering helper also
    # maps them, so preserve that behavior while keeping test geometry off-screen.
    monkeypatch.setattr(banner_window.BaseWindow, "center_window", lambda window, _parent: window.deiconify())
    parameters = {f"COMPASS_DEV_ID{instance if instance > 1 else ''}": 423425 + instance * 256 for instance in range(1, 9)}
    window = banner_window.FlightControllerBannerWindow(root, ["ArduCopter V4.6.3"], fc_parameters=parameters)
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
def test_user_can_resize_each_diagnostics_section_up_and_down(
    resizable_banner_window: banner_window.FlightControllerBannerWindow, sash_index: int, distance: int
) -> None:
    """
    Both boundaries resize their adjacent sections using Tk's native sash positioning.

    GIVEN: Three visible diagnostic sections separated by two dividers
    WHEN: Either native sash position is moved up or down
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


@pytest.mark.parametrize("sash_index", [0, 1])
@pytest.mark.parametrize("direction", [-1, 1])
@pytest.mark.skipif(sys.platform == "darwin", reason="Real widget geometry updates are unsafe on headless macOS.")
def test_diagnostics_sections_cannot_be_resized_below_the_minimum_height(
    resizable_banner_window: banner_window.FlightControllerBannerWindow, sash_index: int, direction: int
) -> None:
    """
    Section headers remain visible when a divider is moved beyond its allowed range.

    GIVEN: Three sections with configured minimum heights
    WHEN: Either sash is moved far beyond the top or bottom of the popup
    THEN: The shrinking section stops at its minimum and no section becomes smaller
    """
    window = resizable_banner_window
    panes = window.section_panes
    frames = [window.root.nametowidget(str(pane)) for pane in panes.panes()]
    assert all(int(panes.panecget(frame, "minsize")) == 60 for frame in frames)
    x, y = panes.sash_coord(sash_index)

    panes.sash_place(sash_index, x, y + direction * 10000)
    window.root.update_idletasks()

    assert all(frame.winfo_height() >= 60 for frame in frames)
    shrinking_index = sash_index if direction < 0 else sash_index + 1
    assert frames[shrinking_index].winfo_height() == 60


@pytest.mark.skipif(sys.platform == "darwin", reason="Real widget geometry updates are unsafe on headless macOS.")
def test_shortened_device_pane_can_scroll_to_the_last_detected_device(
    resizable_banner_window: banner_window.FlightControllerBannerWindow,
) -> None:
    """
    Shortening the pane does not make detected devices unreachable.

    GIVEN: Eight real detected-device rows that initially fit in the device pane
    WHEN: The pane is shortened and its actual scrollbar command is invoked
    THEN: The table scrolls to its last row and the scrollbar reports the same position
    """
    window = resizable_banner_window
    panes = window.section_panes
    tree = window.device_tree
    scrollbar = next(child for child in tree.master.winfo_children() if isinstance(child, ttk.Scrollbar))
    assert len(tree.get_children()) == 8
    assert tree.yview() == (0.0, 1.0)
    x, _y = panes.sash_coord(1)

    panes.sash_place(1, x, panes.winfo_height() - 140)
    window.root.update_idletasks()
    before = tree.yview()
    assert before[1] < 1.0
    window.root.tk.call(scrollbar.cget("command"), "moveto", 1.0)
    window.root.update_idletasks()

    after = tree.yview()
    assert after[0] > before[0]
    assert after[1] == 1.0
    assert scrollbar.get() == after


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


@pytest.mark.skipif(sys.platform == "darwin", reason="Real modal Tk updates are unsafe on headless macOS runners.")
def test_user_sees_newest_statustext_with_local_arrival_times_at_the_top(root: tk.Tk, monkeypatch: pytest.MonkeyPatch) -> None:  # pylint: disable=too-many-locals
    """
    FC diagnostics show live STATUSTEXT in local-time arrival order.

    GIVEN: The FC has emitted many status messages, including one also shown in its boot banner
    WHEN: The user opens diagnostics and another status message arrives
    THEN: The banner duplicate is excluded and the newest timestamped message is at the top
    AND: The list remains pinned to the top while new status messages arrive
    """
    # Arrange: Connect a real PyMAVLink parser to an in-memory byte stream.
    # pylint: disable=duplicate-code  # Shared in-memory PyMAVLink transport setup.
    master = mavutil.mavfile(None, "in-memory", input=False)
    master.mav = mavlink.MAVLink(master)
    master.target_system = 1
    master.target_component = 1
    wire = bytearray()

    def recv(count: int) -> bytes:
        data = bytes(wire[:count])
        del wire[:count]
        return data

    monkeypatch.setattr(master, "recv", recv)
    connection = FlightControllerConnection(info=FlightControllerInfo())
    connection.set_master_for_testing(master)
    # pylint: enable=duplicate-code

    def enqueue_status_text(text: str) -> None:
        encoder = mavlink.MAVLink(None, srcSystem=1, srcComponent=1)
        packet = mavlink.MAVLink_statustext_message(4, text.encode(), id=0, chunk_seq=0)
        wire.extend(packet.pack(encoder))

    def poll_and_format() -> list[str]:
        connection.poll_status_text()
        return connection.status_text_display_buffer

    received_messages = [f"Diagnostic {index}" for index in range(20)]
    for message in received_messages:
        enqueue_status_text(message)
    enqueue_status_text("Boot banner duplicate")
    poll_and_format()

    navigation_lock = NavigationLock()
    window = banner_window.FlightControllerBannerWindow(
        root,
        ["Boot banner duplicate"],
        connection.status_text_display_buffer,
        status_text_provider=poll_and_format,
        navigation_lock=navigation_lock,
    )
    try:
        # Assert the initial view: complete timestamped history, newest first, duplicate filtered, top visible.
        root.update_idletasks()
        displayed_lines = window.status_text_widget.get("1.0", "end-1c").splitlines()
        assert [line.split("] ", maxsplit=1)[1] for line in displayed_lines] == [
            f"Diagnostic {index}" for index in reversed(range(len(received_messages)))
        ]
        local_today = datetime.now().astimezone().date()
        for line in displayed_lines:
            timestamp, _message = line.split("] ", maxsplit=1)
            assert re.fullmatch(r"\[\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}", timestamp)
            assert timestamp[1:11] == local_today.strftime("%Y-%m-%d")
        assert window.status_text_widget.yview()[0] == 0.0

        # Act: Let the window's scheduled poll process a newly arrived packet.
        enqueue_status_text("Newest warning")
        window.root.after(500, window.root.quit)
        window.root.mainloop()
        root.update_idletasks()

        # Assert: The actual widget refreshes from the packet stream and remains top-anchored.
        refreshed_lines = window.status_text_widget.get("1.0", "end-1c").splitlines()
        assert [line.split("] ", maxsplit=1)[1] for line in refreshed_lines] == [
            "Newest warning",
            *[f"Diagnostic {index}" for index in reversed(range(len(received_messages)))],
        ]
        assert window.status_text_widget.yview()[0] == 0.0
        assert window.status_text_widget.cget("state") == tk.DISABLED
        assert navigation_lock.locked
    finally:
        window.root.destroy()

    assert not navigation_lock.locked


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

    def __init__(self, *args, **kwargs) -> None:
        self.parent = args[0] if args else None
        self.kwargs = kwargs
        self.configure_options: dict[str, Any] = {}
        self.grid_options: dict[str, Any] = {}

    def pack(self, **_kwargs) -> None:
        pass

    def grid(self, **kwargs) -> None:
        self.grid_options.update(kwargs)

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
        self.headings.setdefault(column, {}).update(kwargs)

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


@pytest.fixture(name="device_table_setup")
def _device_table_setup(
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[banner_window.FlightControllerBannerWindow, _FakeTree, list[_FakeScrollbar], dict[str, str]]:
    """Replace only Tk widget construction while retaining the real decoder and table behavior."""
    tree = _FakeTree()
    scrollbars: list[_FakeScrollbar] = []
    monkeypatch.setattr(banner_window.ttk, "Frame", _FakeWidget)
    monkeypatch.setattr(banner_window.ttk, "Treeview", lambda *_args, **kwargs: _init_tree(tree, kwargs))
    monkeypatch.setattr(
        banner_window.ttk,
        "Scrollbar",
        lambda *_args, **kwargs: _create_fake_scrollbar(scrollbars, kwargs),
    )
    tooltip_texts: dict[str, str] = {}
    monkeypatch.setattr(
        banner_window,
        "_DeviceTreeTooltip",
        lambda _tree, texts: tooltip_texts.update(texts),
    )
    window = banner_window.FlightControllerBannerWindow.__new__(banner_window.FlightControllerBannerWindow)
    window._sort_column = None
    window._sort_descending = False
    return window, tree, scrollbars, tooltip_texts


def test_device_table_uses_requested_columns_and_stripes_rows(
    device_table_setup: tuple[banner_window.FlightControllerBannerWindow, _FakeTree, list[_FakeScrollbar], dict[str, str]],
) -> None:
    """
    Real flight-controller parameters reach the displayed table without changing device information.

    GIVEN: Decodable barometer, compass and accelerometer parameters and a compass priority
    WHEN: The table is built using the real diagnostics model
    THEN: Complete rows, translated headings, stripes and original parameter tooltips are displayed
    """
    window, tree, scrollbars, tooltip_texts = device_table_setup
    baro_id = (6 << 16) | (118 << 8) | (1 << 3) | 1
    compass_id = (7 << 16) | (30 << 8) | (2 << 3) | 1
    imu_id = (19 << 16) | (1 << 8) | (3 << 3) | 2

    window._create_device_table(
        _FakeWidget(),
        {"BARO1_DEVID": baro_id, "COMPASS_DEV_ID2": compass_id, "COMPASS_PRIO1_ID": compass_id, "INS_ACC_ID": imu_id},
    )

    assert tree.kwargs["columns"] == ("DeviceName", "BusType", "Bus", "Address", "DevType", "Priority")
    assert tree.kwargs["show"] == "headings"
    assert tree.headings["DeviceName"]["text"] == "Device"
    assert tree.headings["BusType"]["text"] == "Bus type"
    assert tree.headings["DevType"]["text"] == "Device type"
    assert tree.headings["Priority"]["text"] == "Priority"
    assert tree.columns["Priority"]["anchor"] == tk.CENTER
    assert tree.get_children() == ("device-0", "device-1", "device-2")
    assert tree.tags == {"device-0": (), "device-1": ("striped",), "device-2": ()}
    assert tooltip_texts == {
        "device-0": f"BARO1_DEVID: {baro_id}",
        "device-1": f"COMPASS_DEV_ID2: {compass_id}",
        "device-2": f"INS_ACC_ID: {imu_id}",
    }
    assert tree.values == {
        "device-0": ("BARO1", "I2C", 1, 118, "DPS310", ""),
        "device-1": ("COMPASS2", "I2C", 2, 30, "HMC5883", 1),
        "device-2": ("INS_ACC", "SPI", 3, 1, "MPU6000", ""),
    }
    assert len(scrollbars) == 1


def _init_tree(tree: _FakeTree, kwargs: dict[str, Any]) -> _FakeTree:
    """Initialize a fake Treeview with the constructor options under test."""
    tree.kwargs = kwargs
    return tree


def _create_fake_scrollbar(scrollbars: list[_FakeScrollbar], kwargs: dict[str, Any]) -> _FakeScrollbar:
    """Record scrollbar creation while returning a widget substitute."""
    scrollbar = _FakeScrollbar(**kwargs)
    scrollbars.append(scrollbar)
    return scrollbar


@pytest.mark.parametrize("row_count", [0, 2, 8, 9])
def test_device_scrollbar_is_wired_for_vertical_scrolling_even_when_all_rows_initially_fit(
    device_table_setup: tuple[banner_window.FlightControllerBannerWindow, _FakeTree, list[_FakeScrollbar], dict[str, str]],
    row_count: int,
) -> None:
    """
    The device scrollbar remains available regardless of the initial number of rows.

    GIVEN: A device table that may initially fit all its rows
    WHEN: The device table is created
    THEN: Its scrollbar and scroll-position callbacks are wired for vertical scrolling
    """
    window, tree, scrollbars, _tooltip_texts = device_table_setup
    parameters = {f"BARO{index + 1}_DEVID": 423425 + index * 256 for index in range(row_count)}

    window._create_device_table(_FakeWidget(), parameters)

    assert len(tree.get_children()) == row_count
    assert len(scrollbars) == 1
    scrollbar = scrollbars[0]
    assert scrollbar.kwargs["orient"] == tk.VERTICAL
    assert scrollbar.kwargs["command"] == tree.yview
    assert tree.configure_options["yscrollcommand"] == scrollbar.set
    assert scrollbar.grid_options == {"row": 0, "column": 1, "sticky": "ns"}
    assert tree.grid_options == {"row": 0, "column": 0, "sticky": "nsew"}


def test_device_table_sort_orders_values_and_reapplies_stripes(
    device_table_setup: tuple[banner_window.FlightControllerBannerWindow, _FakeTree, list[_FakeScrollbar], dict[str, str]],
) -> None:
    """Sorting rearranges rows and recalculates alternating row tags."""
    window, tree, _scrollbars, tooltip_texts = device_table_setup
    parameters = {f"BARO{index + 1}_DEVID": (6 << 16) | (118 << 8) | (bus << 3) | 1 for index, bus in enumerate((10, 1, 2))}
    window._create_device_table(_FakeWidget(), parameters)
    values_before = dict(tree.values)
    tooltips_before = dict(tooltip_texts)

    tree.headings["Bus"]["command"]()

    assert window.device_tree.get_children() == ("device-1", "device-2", "device-0")
    assert [window.device_tree.tags[iid] for iid in window.device_tree.get_children()] == [(), ("striped",), ()]
    assert window.device_tree.headings["Bus"]["text"].endswith("▲")

    tree.headings["Bus"]["command"]()
    assert window.device_tree.get_children() == ("device-0", "device-2", "device-1")
    assert window.device_tree.headings["Bus"]["text"].endswith("▼")
    assert [tree.tags[iid] for iid in tree.get_children()] == [(), ("striped",), ()]
    assert tree.values == values_before
    assert tooltip_texts == tooltips_before


def test_user_can_sort_compass_priorities_with_unranked_devices_last(
    device_table_setup: tuple[banner_window.FlightControllerBannerWindow, _FakeTree, list[_FakeScrollbar], dict[str, str]],
) -> None:
    """
    Priority sorting exposes the compass order without mixing in other devices.

    GIVEN: Ranked compasses and an unranked device in the same table
    WHEN: The user clicks the Priority heading twice
    THEN: Compass ranks sort numerically in both directions and unranked devices stay last
    """
    window, tree, _scrollbars, _tooltip_texts = device_table_setup
    parameters = {
        "BARO1_DEVID": 423425,
        "COMPASS_DEV_ID": 423425,
        "COMPASS_DEV_ID2": 423681,
        "COMPASS_DEV_ID3": 423937,
        "COMPASS_PRIO1_ID": 423681,
        "COMPASS_PRIO2_ID": 423937,
        "COMPASS_PRIO3_ID": 423425,
    }
    window._create_device_table(_FakeWidget(), parameters)

    tree.headings["Priority"]["command"]()

    assert tree.get_children() == ("device-2", "device-3", "device-1", "device-0")
    assert window.device_tree.headings["Priority"]["text"] == "Priority ▲"
    assert [tree.tags[iid] for iid in tree.get_children()] == [(), ("striped",), (), ("striped",)]
    tree.headings["Priority"]["command"]()
    assert tree.get_children() == ("device-1", "device-3", "device-2", "device-0")
    assert window.device_tree.headings["Priority"]["text"] == "Priority ▼"
    assert [tree.tags[iid] for iid in tree.get_children()] == [(), ("striped",), (), ("striped",)]
    tree.headings["DeviceName"]["command"]()
    assert tree.get_children() == ("device-0", "device-1", "device-2", "device-3")
    assert tree.headings["Priority"]["text"] == "Priority"


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
