#!/usr/bin/env python3
"""
Standalone and embedded MAVLink inspector behavior and resource ownership.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import sys
import tkinter as tk
from argparse import Namespace
from collections.abc import Generator
from contextlib import ExitStack
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from ardupilot_methodic_configurator import _
from ardupilot_methodic_configurator import frontend_tkinter_mavlink_inspector as frontend
from ardupilot_methodic_configurator.backend_flightcontroller import FlightController
from ardupilot_methodic_configurator.data_model_data_telemetry import (
    MessageRate,
    MessageSample,
    RadioSample,
    TelemetrySample,
    TelemetryState,
)
from ardupilot_methodic_configurator.frontend_tkinter_mavlink_inspector import MavlinkInspectorWindow
from ardupilot_methodic_configurator.frontend_tkinter_navigation_lock import NavigationLock
from ardupilot_methodic_configurator.frontend_tkinter_parameter_editor import ParameterEditorWindow
from ardupilot_methodic_configurator.plugins.plugin_protocol import PluginPauseReason

# pylint: disable=protected-access,redefined-outer-name


@pytest.fixture
def inspector(root: tk.Tk) -> Generator[MavlinkInspectorWindow, None, None]:
    """Use real widgets with only the external transport mocked."""
    controller = MagicMock(spec=FlightController)
    controller.master = None
    with ExitStack() as stack:
        stack.enter_context(patch.object(tk.Toplevel, "winfo_fpixels", side_effect=tk.TclError("no display")))
        if sys.platform == "darwin":
            # Headless macOS CI must never attempt physical screen rendering.
            for method in ("update", "update_idletasks", "wait_visibility", "wait_window"):
                stack.enter_context(patch(f"tkinter.Misc.{method}"))
        window = frontend.open_mavlink_inspector_window(root, controller)
        window.root.after_cancel(window._timer_id)
        window._timer_id = None
        window.root.update_idletasks()
        try:
            yield window
        finally:
            window.close()


@pytest.fixture
def traffic() -> TelemetryState:
    """Provide values that sort differently as numbers and as text."""
    return TelemetryState(
        connected=True,
        receiving=True,
        messages=tuple(
            MessageRate((system, component, name), MessageSample(count, 100, 0, (("value", str(count)),)), hz, byte_rate, age)
            for system, component, name, count, hz, byte_rate, age in (
                (10, 10, "Z_MESSAGE", 10, 10.0, 100.0, 10.0),
                (2, 2, "A_MESSAGE", 2, 2.0, 20.0, 2.0),
                (1, 1, "B_MESSAGE", 100, 100.0, 1000.0, 100.0),
            )
        ),
    )


def _settle_layout(window: MavlinkInspectorWindow) -> None:
    """Process native configure events without calling Tk's unsafe update() method."""
    window.root.update_idletasks()
    window.root.after_idle(window.root.quit)
    window.root.mainloop()
    window.root.update_idletasks()


def test_embedded_inspector_owns_input_until_closed(inspector: MavlinkInspectorWindow) -> None:
    """
    Keep parent controls inaccessible while the embedded inspector owns the connection.

    GIVEN an inspector embedded in the editor
    WHEN it is open on a platform supporting modal grabs
    THEN input belongs to the inspector until closing releases the grab.
    """
    root = inspector.root.master
    assert root is not None
    assert root.grab_current() is (None if sys.platform == "darwin" else inspector.root)

    inspector.close()

    assert root.grab_current() is None


def test_radio_panel_shows_three_name_value_unit_tuples(inspector: MavlinkInspectorWindow) -> None:
    """Display loaded radio measurements in three compact columns without connection controls."""
    radio = RadioSample((51, 68), 0, 30, 40, 12, 15, 90, 7, 2)
    inspector.refresh(TelemetryState(connected=True, receiving=True, radio=radio, radio_error_rate=1.5))
    panel = inspector.radio_status
    for key, expected in {"rssi": "30", "remrssi": "40", "txbuf": "90", "rx_error_rate": "1.5"}.items():
        assert str(panel.values[key].cget("text")) == expected
    for key, value in panel.values.items():
        value_grid = value.grid_info()
        unit_grid = panel.units[key].grid_info()
        assert unit_grid["row"] == value_grid["row"]
        assert unit_grid["column"] == value_grid["column"] + 1
    assert {value.grid_info()["column"] for value in panel.values.values()} == {1, 5, 9}
    assert str(panel.units["txbuf"].cget("text")) == "%"
    assert all(int(value.cget("width")) == 10 for value in panel.values.values())
    assert str(panel.connection_status.cget("text")) == _("Traffic received on the active connection")
    assert panel.master is inspector.footer
    assert str(panel.metrics_note.cget("text")) == _(
        "RSSI and noise are device-dependent raw values. "
        "Remote RX RSSI describes reception at the far end. "
        "RX errors/s is a counter rate, not a loss percentage."
    )
    assert inspector.message_contents.title == _("MAVLink message contents")
    assert inspector.close_button.winfo_exists()
    assert not any(isinstance(child, (frontend.ttk.LabelFrame, frontend.ttk.Combobox)) for child in panel.winfo_children())

    inspector.refresh(TelemetryState())
    assert all(str(value.cget("text")) == _("Unavailable") for value in panel.values.values())
    assert not any(len(panel.values[key].grid_info()) > 0 for key, _name, _unit in panel._RADIO_METRICS)
    assert all(len(panel.values[key].grid_info()) > 0 for key, _name, _unit in panel._TRAFFIC_METRICS)
    assert str(panel.metrics_note.cget("text")) == _(
        "Radio link metrics cannot be presented. They require RADIO or RADIO_STATUS MAVLink messages."
    )
    inspector.refresh(TelemetryState(connected=True, receiving=True, radio=radio))
    assert all(panel.values[key].grid_info() for key, _name, _unit in panel._RADIO_METRICS)


@pytest.mark.parametrize("with_radio", [False, True])
@pytest.mark.skipif(sys.platform == "darwin", reason="Window geometry requires rendering, unsafe on headless macOS CI")
def test_radio_explanation_wraps_when_window_narrows(inspector: MavlinkInspectorWindow, with_radio: bool) -> None:
    """Both the missing-report notice and received-radio explanation fit the available width."""
    radio = RadioSample((51, 68), 0, 30, 40, 12, 15, 90, 7, 2) if with_radio else None
    inspector.refresh(TelemetryState(connected=True, receiving=True, radio=radio))
    inspector.root.geometry("1000x600")
    _settle_layout(inspector)
    wide_height = inspector.radio_status.metrics_note.winfo_reqheight()
    inspector.root.geometry("500x600")
    _settle_layout(inspector)
    assert inspector.radio_status.metrics_note.winfo_reqheight() > wide_height


def test_help_button_opens_inspector_manual(inspector: MavlinkInspectorWindow) -> None:
    """The Help action beside Close opens the inspector's dedicated manual."""
    assert inspector.buttons_frame.pack_slaves() == [inspector.help_button, inspector.close_button]
    with patch.object(frontend, "webbrowser_open_url") as open_manual:
        inspector.help_button.invoke()
    open_manual.assert_called_once_with("https://ardupilot.github.io/MethodicConfigurator/USERMANUAL_MAVLink_inspector.html")


def test_every_inspector_control_and_reading_has_beginner_help(inspector: MavlinkInspectorWindow) -> None:
    """
    Make explanations available on each label, value, unit, scrollbar and control.

    GIVEN the inspector and its reusable radio panel,
    WHEN a beginner points at any displayed control or reading,
    THEN a descriptive, bound tooltip is available rather than just a terse label.
    """
    hints = {**inspector.tooltips, **inspector.radio_status.tooltips}
    pending = list(inspector.main_frame.winfo_children())
    controls = []
    while pending:
        widget = pending.pop()
        pending.extend(widget.winfo_children())
        if isinstance(widget, (frontend.ttk.Label, frontend.ttk.Button, frontend.ttk.Scrollbar, tk.Text, tk.PanedWindow)):
            controls.append(widget)
    assert len(controls) > 40
    for widget in controls:
        assert widget in hints, f"Missing help for {widget}"
        assert len(hints[widget].text) >= 40
        assert widget.bind("<Enter>")
        assert widget.bind("<Leave>")
    assert "B/s means bytes per second" in hints[inspector.radio_status.units["rx_rate"]].text
    assert "not a percentage" in hints[inspector.radio_status.values["rssi"]].text
    assert "Errors/s is a count rate" in hints[inspector.radio_status.values["rx_error_rate"]].text
    assert "not editable parameters" in hints[inspector.fields].text


@pytest.mark.parametrize("region", ["heading", "cell"])
@pytest.mark.parametrize(
    ("column", "explanation"),
    [
        ("#1", "system number"),
        ("#2", "component number"),
        ("#3", "message name"),
        ("#4", "lost-packet count"),
        ("#5", "messages per second"),
        ("#6", "bytes per second"),
        ("#7", "Seconds since"),
    ],
)
def test_hovering_each_table_column_explains_its_meaning(
    inspector: MavlinkInspectorWindow, region: str, column: str, explanation: str
) -> None:
    """
    Explain each individual column, including its available action.

    GIVEN a pointer over a message heading or cell,
    WHEN it moves to that column,
    THEN the tooltip describes its meaning and sorting or row selection.
    """
    with (
        patch.object(inspector.table, "identify_column", return_value=column),
        patch.object(inspector.table, "identify_region", return_value=region),
    ):
        inspector._on_table_hover(SimpleNamespace(x=10, y=10))
    tooltip = inspector.tooltips[inspector.table]
    assert explanation in tooltip.text
    assert ("Click to sort" if region == "heading" else "Select a row") in tooltip.text
    assert tooltip.timers["show"] in inspector.root.tk.call("after", "info")


@pytest.mark.parametrize(
    ("region", "column", "explanation"),
    [("separator", "#1", "change the column width"), ("nothing", "", "Each row"), ("cell", "#99", "Each row")],
)
def test_hovering_dividers_or_empty_table_space_gives_relevant_help(
    inspector: MavlinkInspectorWindow, region: str, column: str, explanation: str
) -> None:
    """
    Provide usable hints even where the pointer is not over a known message column.

    GIVEN a divider, empty table area or unknown column,
    WHEN the pointer enters it,
    THEN help explains resizing or the overall table instead of a stale column.
    """
    with (
        patch.object(inspector.table, "identify_column", return_value=column),
        patch.object(inspector.table, "identify_region", return_value=region),
    ):
        inspector._on_table_hover(SimpleNamespace(x=10, y=10))
    assert explanation in inspector.tooltips[inspector.table].text


def test_table_help_stays_stable_until_the_pointer_moves_or_scrolls(inspector: MavlinkInspectorWindow) -> None:
    """
    Avoid tooltip flicker and remove old hints when scrolling.

    GIVEN a pending hint for a table cell,
    WHEN the pointer stays in that cell and then the user scrolls,
    THEN the same hint stays scheduled until scrolling dismisses it.
    """
    event = SimpleNamespace(x=10, y=10)
    with (
        patch.object(inspector.table, "identify_column", return_value="#5"),
        patch.object(inspector.table, "identify_region", return_value="cell"),
    ):
        inspector._on_table_hover(event)
        tooltip = inspector.tooltips[inspector.table]
        timer = tooltip.timers["show"]
        inspector._on_table_hover(event)
        assert tooltip.timers["show"] == timer
        inspector._hide_table_tooltip(event)
        assert timer not in inspector.root.tk.call("after", "info")
        inspector._on_table_hover(event)
        assert tooltip.timers["show"] != timer


def test_usb_connection_guidance_is_visible_and_wraps_safely(inspector: MavlinkInspectorWindow) -> None:
    """
    Explain the measurement path before a beginner interprets the traffic readings.

    GIVEN an inspector for any active transport,
    WHEN its guidance is read or the window becomes narrow,
    THEN it explains USB traffic versus the radio link and keeps positive wrapping widths.
    """
    assert len(inspector.connection_note.pack_info()) > 0
    assert "USB connection measures USB traffic, not the telemetry radio link" in inspector.connection_note.cget("text")
    inspector._resize_notices(SimpleNamespace(width=0))
    assert int(inspector.connection_note.cget("wraplength")) == 1
    inspector._resize_notices(SimpleNamespace(width=400))
    assert int(inspector.connection_note.cget("wraplength")) == 384


@pytest.mark.skipif(sys.platform == "darwin", reason="Window geometry requires rendering, unsafe on headless macOS CI")
def test_footer_actions_stay_visible_and_well_separated_with_radio_data(inspector: MavlinkInspectorWindow) -> None:
    """
    Keep the two footer actions accessible when all radio readings are displayed.

    GIVEN a populated radio report,
    WHEN the fixed footer reserves room below the message panes,
    THEN Help and Close remain visible with a clear gap between them.
    """
    radio = RadioSample((51, 68), 0, 30, 40, 12, 15, 90, 7, 2)
    inspector.refresh(TelemetryState(connected=True, receiving=True, radio=radio))
    _settle_layout(inspector)
    assert inspector.close_button.winfo_ismapped()
    assert inspector.help_button.winfo_ismapped()
    gap = inspector.close_button.winfo_x() - inspector.help_button.winfo_x() - inspector.help_button.winfo_width()
    assert gap >= 24
    assert inspector.close_button.winfo_rooty() + inspector.close_button.winfo_height() <= (
        inspector.root.winfo_rooty() + inspector.root.winfo_height()
    )


@pytest.mark.parametrize(
    ("state", "status"),
    [
        (TelemetryState(error=True), "Unable to read telemetry"),
        (TelemetryState(), "Flight controller disconnected"),
        (TelemetryState(connected=True), "No current MAVLink data"),
    ],
)
def test_radio_status_explains_connection_failures_without_showing_old_metrics(
    inspector: MavlinkInspectorWindow, state: TelemetryState, status: str
) -> None:
    """
    Explain unavailable measurements after error, disconnect or a quiet link.

    GIVEN a connection without current radio data,
    WHEN its state is shown,
    THEN the matching guidance appears and no radio readings are presented as current.
    """
    inspector.refresh(state)
    assert status in inspector.radio_status.connection_status.cget("text")
    assert len(inspector.radio_status.values["rssi"].grid_info()) == 0
    assert "RADIO or RADIO_STATUS" in inspector.radio_status.metrics_note.cget("text")


@pytest.mark.skipif(sys.platform == "darwin", reason="Window geometry requires rendering, unsafe on headless macOS CI")
def test_user_can_resize_each_inspector_area(inspector: MavlinkInspectorWindow) -> None:
    """Dragging either divider gives each area more room."""
    panes = inspector.section_panes
    assert str(panes.cget("orient")) == tk.VERTICAL
    assert len(panes.panes()) == 2
    # Exercise real Tk geometry without running the inspector's polling timer.
    _settle_layout(inspector)
    for divider in range(1):
        x, y = panes.sash_coord(divider)
        panes.sash_place(divider, x, y + 10)
        assert panes.sash_coord(divider)[1] != y


@pytest.mark.skipif(sys.platform == "darwin", reason="Window geometry requires rendering, unsafe on headless macOS CI")
def test_collapsing_message_contents_releases_its_pane_height(inspector: MavlinkInspectorWindow) -> None:
    """Give the message table and radio readings the space freed by collapsed fields."""
    pane = inspector.message_contents.master
    _settle_layout(inspector)
    original_sash_y = inspector.section_panes.sash_coord(0)[1]
    inspector.message_contents.set_expanded(False)
    _settle_layout(inspector)
    assert int(inspector.section_panes.paneconfigure(pane, "minsize")[-1]) == 0
    assert inspector.section_panes.paneconfigure(pane, "stretch")[-1] == "never"
    collapsed_sash_y = inspector.section_panes.sash_coord(0)[1]
    assert collapsed_sash_y > original_sash_y
    inspector.message_contents.set_expanded(True)
    _settle_layout(inspector)
    assert int(inspector.section_panes.paneconfigure(pane, "minsize")[-1]) == inspector._minimum_section_height
    assert inspector.section_panes.paneconfigure(pane, "stretch")[-1] == "always"
    assert inspector.section_panes.sash_coord(0)[1] < collapsed_sash_y


@pytest.mark.parametrize("column", ["system", "component", "count", "hz", "bytes", "age", "message"])
def test_user_sorts_each_heading_and_stripes_follow_display_order(
    inspector: MavlinkInspectorWindow,
    traffic: TelemetryState,
    column: str,
) -> None:
    """
    Sort columns numerically or alphabetically with alternating stripes.

    GIVEN rows containing 2, 10 and 100,
    WHEN a heading is clicked twice,
    THEN ordering reverses and stripes follow visible positions.
    """
    inspector.refresh(traffic)
    command = inspector.table.heading(column, "command")
    inspector.root.tk.call(command)
    ordered = inspector.table.get_children()
    values = [inspector.table.set(identifier, column) for identifier in ordered]
    assert values == (sorted(values) if column == "message" else sorted(values, key=float))
    assert str(inspector.table.heading(column, "text")).endswith(" ▲")
    inspector.root.tk.call(command)
    assert inspector.table.get_children() == tuple(reversed(ordered))
    assert str(inspector.table.heading(column, "text")).endswith(" ▼")
    for index, identifier in enumerate(inspector.table.get_children()):
        assert tuple(inspector.table.item(identifier, "tags")) == (("striped",) if index % 2 else ())


def test_live_updates_preserve_sort_selection_and_decoded_fields(
    inspector: MavlinkInspectorWindow,
    traffic: TelemetryState,
) -> None:
    """
    Preserve inspection context as live message counts arrive.

    GIVEN a selected row sorted by count,
    WHEN live data changes its count and removes another row,
    THEN it moves into order, stays selected and displays its updated fields.
    """
    inspector.refresh(traffic)
    inspector._sort_by_column("count")
    identifier = "2:2:A_MESSAGE"
    inspector.table.selection_set(identifier)
    changed = replace(traffic.messages[1], sample=MessageSample(200, 500, 1, (("value", "200"),)))
    inspector.refresh(replace(traffic, messages=(traffic.messages[0], changed)))
    assert inspector.table.get_children()[-1] == identifier
    assert inspector.table.selection() == (identifier,)
    assert "value: 200" in inspector.fields.get("1.0", "end")
    assert not inspector.table.exists("1:1:B_MESSAGE")
    inspector.refresh(TelemetryState())
    assert not inspector.table.get_children()
    assert inspector.fields.get("1.0", "end").strip() == ""


@pytest.mark.parametrize("changed", [False, True])
@pytest.mark.skipif(sys.platform == "darwin", reason="Window geometry requires rendering, unsafe on headless macOS CI")
def test_live_fields_remain_readable_while_scrolled(inspector: MavlinkInspectorWindow, changed: bool) -> None:
    """
    Keep long messages readable and unchanged fields available for copying.

    GIVEN a long decoded message scrolled to a selected field,
    WHEN telemetry refreshes with unchanged or updated field values,
    THEN the view stays scrolled and unchanged text remains selected for copying.
    """
    fields = tuple((f"field_{index}", str(index)) for index in range(60))
    message = MessageRate((1, 1, "LONG_MESSAGE"), MessageSample(1, 100, 0, fields), 1.0, 100.0, 0.0)
    state = TelemetryState(connected=True, receiving=True, messages=(message,))
    inspector.refresh(state)
    inspector.table.selection_set("1:1:LONG_MESSAGE")
    inspector._show_fields()
    _settle_layout(inspector)
    inspector.fields.yview_moveto(0.5)
    inspector.fields.tag_add("sel", "31.0", "31.end")
    view = inspector.fields.yview()
    selection = inspector.fields.tag_ranges("sel")
    assert view[0] > 0
    assert selection

    if changed:
        updated = replace(message, sample=replace(message.sample, fields=(*fields[:-1], ("field_59", "updated"))))
        state = replace(state, messages=(updated,))
    inspector.refresh(state)
    _settle_layout(inspector)

    assert inspector.fields.yview() == pytest.approx(view)
    if changed:
        assert "field_59: updated" in inspector.fields.get("1.0", "end")
    else:
        assert inspector.fields.tag_ranges("sel") == selection
        assert inspector.fields.get("sel.first", "sel.last") == "field_30: 30"


@pytest.mark.parametrize("direct_destroy", [False, True])
def test_closing_inspector_releases_only_its_own_resources(inspector: MavlinkInspectorWindow, direct_destroy: bool) -> None:
    """
    Release observers and timers even when an owner destroys the window.

    GIVEN an inspector with a parser observer,
    WHEN closed or destroyed directly,
    THEN callbacks and hooks disappear while the shared FC remains connected.
    """
    controller = inspector.model.flight_controller
    master = MagicMock(message_hooks=[])
    master.recv_match.return_value = None
    controller.master = master
    inspector.backend.poll()
    assert len(master.message_hooks) == 1
    inspector._poll()
    timer = inspector._timer_id
    if direct_destroy:
        inspector.root.destroy()
    else:
        inspector.close()
    inspector.close()
    assert inspector._timer_id is None
    assert timer not in inspector.root.tk.call("after", "info")
    assert not master.message_hooks
    controller.disconnect.assert_not_called()


def test_polling_refreshes_real_rates_and_keeps_one_follow_up_callback(inspector: MavlinkInspectorWindow) -> None:
    """
    Convert backend snapshots into live rows and one continuing measurement loop.

    GIVEN two observations a second apart on the same connection,
    WHEN the inspector polls each snapshot,
    THEN counts and rates update through the real models and a single next poll remains scheduled.
    """
    connection = object()
    key = (1, 1, "HEARTBEAT")
    first = TelemetrySample(connection, 0, 40, messages={key: MessageSample(1, 40, 0, (("type", "2"),))})
    second = TelemetrySample(connection, 1, 120, messages={key: MessageSample(3, 120, 1, (("type", "2"),))})
    with patch.object(inspector.backend, "poll", side_effect=[first, second]) as poll:
        inspector._poll()
        assert inspector._state.rx_rate is None
        previous_timer = inspector._timer_id
        inspector.root.after_cancel(previous_timer)
        inspector.table.selection_set("1:1:HEARTBEAT")
        inspector._poll()
        assert poll.call_count == 2
    assert inspector._state.rx_rate == 80.0
    assert inspector.table.set("1:1:HEARTBEAT", "count") == "3"
    assert inspector.table.set("1:1:HEARTBEAT", "hz") == "2.0"
    assert inspector.table.selection() == ("1:1:HEARTBEAT",)
    assert "type: 2" in inspector.fields.get("1.0", "end")
    callbacks = inspector.root.tk.call("after", "info")
    assert previous_timer not in callbacks
    assert callbacks.count(inspector._timer_id) == 1


def test_rapid_collapse_changes_coalesce_and_close_cancels_pending_work(inspector: MavlinkInspectorWindow) -> None:
    """
    Leave no queued resize or polling work behind when a user closes quickly.

    GIVEN rapidly collapsed and expanded message contents,
    WHEN Close is clicked before the pending resize runs,
    THEN obsolete resizes are cancelled, the monitor stops, and later callbacks do nothing.
    """
    inspector.message_contents.set_expanded(False)
    first_resize = inspector._resize_timer_id
    inspector.message_contents.set_expanded(True)
    last_resize = inspector._resize_timer_id
    assert first_resize != last_resize
    assert first_resize not in inspector.root.tk.call("after", "info")
    inspector.tooltips[inspector.fields].schedule_show()
    tooltip_timer = inspector.tooltips[inspector.fields].timers["show"]
    inspector.close_button.invoke()
    assert inspector._closed
    assert last_resize not in inspector.root.tk.call("after", "info")
    assert tooltip_timer not in inspector.root.tk.call("after", "info")
    assert inspector._resize_timer_id is None
    with patch.object(inspector.backend, "poll") as poll:
        inspector._poll()
        poll.assert_not_called()
    inspector._resize_message_contents_pane()
    assert inspector._timer_id is None
    inspector.model.flight_controller.disconnect.assert_not_called()


def test_closing_during_layout_settling_does_not_access_destroyed_widgets(inspector: MavlinkInspectorWindow) -> None:
    """
    Stop a resize cleanly if window closure runs while Tk is settling its layout.

    GIVEN a queued resize whose idle processing closes the window,
    WHEN that resize resumes,
    THEN it stops before reading or moving any destroyed widgets.
    """
    with patch.object(inspector.message_contents, "update_idletasks", side_effect=inspector.close):
        inspector._resize_message_contents_pane()
    assert inspector._closed
    assert inspector._resize_timer_id is None


def test_destroying_a_child_widget_does_not_stop_the_connection_monitor(inspector: MavlinkInspectorWindow) -> None:
    """
    Ignore child-destruction events propagated to the inspector's toplevel.

    GIVEN a monitor owning a live observer,
    WHEN a child widget is destroyed,
    THEN the window stays open and keeps the observer until the inspector itself closes.
    """
    master = MagicMock(message_hooks=[])
    master.recv_match.return_value = None
    inspector.model.flight_controller.master = master
    inspector.backend.poll()
    child = frontend.ttk.Frame(inspector.root)
    child.destroy()
    assert not inspector._closed
    assert len(master.message_hooks) == 1


def test_embedded_inspector_is_attached_to_its_visible_owner(inspector: MavlinkInspectorWindow) -> None:
    """
    Associate an embedded inspector with the visible application that opened it.

    GIVEN a visible owning application window,
    WHEN another inspector is opened as its child,
    THEN the window manager records that ownership and closing the child leaves its owner intact.
    """
    with patch.object(inspector.root, "winfo_viewable", return_value=True):
        child = frontend.open_mavlink_inspector_window(inspector.root, inspector.model.flight_controller)
    try:
        assert str(child.root.transient()) == str(inspector.root)
    finally:
        child.close()
    assert not inspector._closed


@pytest.mark.parametrize("failure", [False, True])
def test_standalone_operation_owns_connection_until_exit(failure: bool) -> None:
    """
    Disconnect the standalone connection even if the GUI fails.

    GIVEN device, baudrate and logging arguments,
    WHEN the GUI runs or raises an error,
    THEN it uses that connection and cleans up the monitor and controller.
    """
    args = Namespace(device="udp:127.0.0.1:14550", baudrate=57600, reboot_time=7, loglevel="INFO")
    with (
        patch.object(frontend, "argument_parser", return_value=args),
        patch.object(frontend, "FlightController") as controller_type,
        patch.object(frontend, "connect_standalone_flight_controller", return_value=True) as connect,
        patch.object(frontend, "MavlinkInspectorWindow") as window_type,
    ):
        window = window_type.return_value
        if failure:
            window.root.mainloop.side_effect = RuntimeError("GUI failure")
            with pytest.raises(RuntimeError, match="GUI failure"):
                frontend.main()
        else:
            frontend.main()
        controller = controller_type.return_value
        controller_type.assert_called_once_with(reboot_time=7, baudrate=57600)
        connect.assert_called_once_with(args, controller)
        window_type.assert_called_once_with(controller)
        window.close.assert_called_once_with()
        controller.disconnect.assert_called_once_with()
        controller.download_params.assert_not_called()


@pytest.mark.parametrize("connected", [False, True])
def test_cancelled_or_offline_connection_does_not_open_inspector(connected: bool) -> None:
    """
    Require a live transport before launching the standalone monitor.

    GIVEN a failed connection or offline device,
    WHEN the command starts,
    THEN no inspector opens and the controller is cleaned up.
    """
    with (
        patch.object(frontend, "argument_parser", return_value=Namespace(reboot_time=5, baudrate=57600, loglevel="INFO")),
        patch.object(frontend, "FlightController") as controller_type,
        patch.object(frontend, "connect_standalone_flight_controller", return_value=connected),
        patch.object(frontend, "show_error_popup") as error,
        patch.object(frontend, "MavlinkInspectorWindow") as window_type,
    ):
        controller_type.return_value.master = None
        frontend.main()
        window_type.assert_not_called()
        controller_type.return_value.disconnect.assert_called_once_with()
        assert error.called is connected


@pytest.mark.parametrize("failure_stage", ["connection", "window"])
def test_standalone_startup_errors_still_disconnect_the_controller(failure_stage: str) -> None:
    """
    Release a standalone connection even if startup fails before the event loop.

    GIVEN a connection or window-construction failure,
    WHEN standalone startup raises,
    THEN the controller disconnects and the original error remains visible.
    """
    with (
        patch.object(frontend, "argument_parser", return_value=Namespace(reboot_time=5, baudrate=57600, loglevel="INFO")),
        patch.object(frontend, "FlightController") as controller_type,
        patch.object(frontend, "connect_standalone_flight_controller", return_value=True) as connect,
        patch.object(frontend, "MavlinkInspectorWindow") as window_type,
    ):
        (connect if failure_stage == "connection" else window_type).side_effect = OSError("startup failed")
        with pytest.raises(OSError, match="startup failed"):
            frontend.main()
        controller_type.return_value.disconnect.assert_called_once_with()


def test_standalone_argument_parser_accepts_user_connection_options() -> None:
    """
    Apply user-supplied connection arguments to the standalone entry point.

    GIVEN a serial device and baudrate on the command line,
    WHEN the public argument parser runs,
    THEN both options are available to connection setup.
    """
    with patch.object(sys, "argv", ["amc_mavlink_inspector", "--device", "COM5", "--baudrate", "57600"]):
        args = frontend.argument_parser()
    assert (args.device, args.baudrate) == ("COM5", 57600)


def test_inspector_cli_and_package_publish_connection_completions() -> None:
    """
    Publish a console command and standard connection completions.

    GIVEN the packaged inspector entry points,
    WHEN its parser accepts connection arguments,
    THEN script, completer and PowerShell names reference the inspector.
    """
    parser = frontend.create_argument_parser()
    args = parser.parse_args(["--device", "udp:127.0.0.1:14550", "--baudrate", "57600"])
    assert args.device == "udp:127.0.0.1:14550"
    assert args.baudrate == 57600
    assert any(hasattr(action, "completer") for action in parser._actions)
    repo = Path(__file__).resolve().parents[1]
    metadata = (repo / "pyproject.toml").read_text(encoding="utf-8")
    module = "ardupilot_methodic_configurator.frontend_tkinter_mavlink_inspector"
    for function in ("main", "create_argument_parser"):
        assert f'amc_mavlink_inspector = "{module}:{function}"' in metadata
    assert "'amc_mavlink_inspector'" in (repo / "ardupilot_methodic_configurator_command_line_completion.psm1").read_text()


@pytest.mark.parametrize("paired", [False, True])
def test_header_launch_pauses_plugin_and_restores_it_after_close(paired: bool) -> None:
    """
    Embed the inspector without competing with plugin receivers.

    GIVEN an editor with an active plugin,
    WHEN the header opens the inspector,
    THEN the plugin pauses and resumes around the shared-connection inspection.
    """
    editor = MagicMock(spec=ParameterEditorWindow)
    editor._connection_recovery = None
    editor.navigation_lock = NavigationLock()
    editor._file_browser_window = None
    plugin = MagicMock(spec=["on_suspend", "on_resume"] if paired else ["on_activate", "on_deactivate"])
    editor.current_plugin_view = plugin
    editor.parameter_editor = MagicMock(is_fc_link_connected=True)
    editor.root = MagicMock()
    editor.ui = MagicMock()
    window = MagicMock()

    def open_window(*_args: object) -> MagicMock:
        assert editor.navigation_lock.locked
        (plugin.on_suspend if paired else plugin.on_deactivate).assert_called_once_with(
            *((PluginPauseReason.EXCLUSIVE_OPERATION,) if paired else ())
        )
        (plugin.on_resume if paired else plugin.on_activate).assert_not_called()
        return window

    with patch(
        "ardupilot_methodic_configurator.frontend_tkinter_parameter_editor.open_mavlink_inspector_window",
        side_effect=open_window,
    ) as open_inspector:
        ParameterEditorWindow.on_mavlink_inspector_click(editor)
    open_inspector.assert_called_once_with(editor.root, editor.parameter_editor.flight_controller)
    editor.root.wait_window.assert_called_once_with(window.root)
    (plugin.on_resume if paired else plugin.on_activate).assert_called_once_with()
    assert not editor.navigation_lock.locked


@pytest.mark.parametrize("paired", [False, True])
@pytest.mark.parametrize("failure_stage", ["pause", "open", "wait"])
def test_inspector_failure_restores_plugin_and_navigation(paired: bool, failure_stage: str) -> None:
    """
    Keep plugin monitoring usable after an inspector launch fails.

    GIVEN an active plugin with paired or legacy lifecycle hooks,
    WHEN pausing, opening the inspector or waiting for it raises,
    THEN the plugin resumes exactly once and navigation is released.
    """
    editor = MagicMock(spec=ParameterEditorWindow)
    editor._connection_recovery = None
    editor.navigation_lock = NavigationLock()
    editor._file_browser_window = None
    plugin = MagicMock(spec=["on_suspend", "on_resume"] if paired else ["on_activate", "on_deactivate"])
    editor.current_plugin_view = plugin
    editor.parameter_editor = MagicMock(is_fc_link_connected=True)
    editor.root = MagicMock()
    pause = plugin.on_suspend if paired else plugin.on_deactivate
    resume = plugin.on_resume if paired else plugin.on_activate
    failure = RuntimeError("inspector launch failed")
    if failure_stage == "pause":
        pause.side_effect = failure
    elif failure_stage == "wait":
        editor.root.wait_window.side_effect = failure
    window = MagicMock()
    with (
        patch(
            "ardupilot_methodic_configurator.frontend_tkinter_parameter_editor.open_mavlink_inspector_window",
            return_value=window,
            side_effect=failure if failure_stage == "open" else None,
        ) as open_inspector,
        pytest.raises(RuntimeError, match="inspector launch failed"),
    ):
        ParameterEditorWindow.on_mavlink_inspector_click(editor)
    pause.assert_called_once_with(*((PluginPauseReason.EXCLUSIVE_OPERATION,) if paired else ()))
    resume.assert_called_once_with()
    assert not editor.navigation_lock.locked
    if failure_stage == "pause":
        open_inspector.assert_not_called()
    if failure_stage == "wait":
        window.close.assert_called_once_with()
    else:
        window.close.assert_not_called()


@pytest.mark.parametrize("plugin_replaced", [False, True])
def test_inspector_does_not_resume_a_plugin_whose_owner_is_gone(plugin_replaced: bool) -> None:
    """
    Avoid restarting a receiver for a removed editor or plugin.

    GIVEN an inspector with its plugin suspended,
    WHEN its parent closes or its plugin is replaced,
    THEN closing the inspector leaves the old receiver stopped.
    """
    editor = MagicMock(spec=ParameterEditorWindow)
    editor._connection_recovery = None
    editor.navigation_lock = NavigationLock()
    editor._file_browser_window = None
    plugin = MagicMock(spec=["on_suspend", "on_resume"])
    editor.current_plugin_view = plugin
    editor.parameter_editor = MagicMock(is_fc_link_connected=True)
    editor.root = MagicMock()

    def remove_owner(_root: object) -> None:
        if plugin_replaced:
            editor.current_plugin_view = None
        else:
            editor.root.winfo_exists.return_value = False

    editor.root.wait_window.side_effect = remove_owner
    with patch("ardupilot_methodic_configurator.frontend_tkinter_parameter_editor.open_mavlink_inspector_window"):
        ParameterEditorWindow.on_mavlink_inspector_click(editor)
    plugin.on_suspend.assert_called_once_with(PluginPauseReason.EXCLUSIVE_OPERATION)
    plugin.on_resume.assert_not_called()
    assert not editor.navigation_lock.locked


@pytest.mark.parametrize("hooks", [None, [], ["on_activate"], ["on_deactivate"]])
def test_inspector_opens_for_plugins_without_paired_lifecycle_hooks(hooks: list[str] | None) -> None:
    """
    Allow inspection on steps whose views have no paired lifecycle hooks.

    GIVEN a configuration step without paired activation and deactivation hooks,
    WHEN the inspector button is clicked,
    THEN the inspector opens and releases the navigation lock when closed.
    """
    editor = MagicMock(spec=ParameterEditorWindow)
    editor._connection_recovery = None
    editor.navigation_lock = NavigationLock()
    editor._file_browser_window = None
    plugin = MagicMock(spec=hooks) if hooks is not None else None
    editor.current_plugin_view = plugin
    editor.parameter_editor = MagicMock(is_fc_link_connected=True)
    editor.root = MagicMock()
    window = MagicMock()
    with patch(
        "ardupilot_methodic_configurator.frontend_tkinter_parameter_editor.open_mavlink_inspector_window",
        return_value=window,
    ) as open_inspector:
        ParameterEditorWindow.on_mavlink_inspector_click(editor)
    open_inspector.assert_called_once_with(editor.root, editor.parameter_editor.flight_controller)
    editor.root.wait_window.assert_called_once_with(window.root)
    window.close.assert_called_once_with()
    assert not editor.navigation_lock.locked
    if plugin is not None:
        assert not plugin.mock_calls


@pytest.mark.parametrize("connected", [False, True])
def test_header_button_is_below_forum_zip_button(inspector: MavlinkInspectorWindow, connected: bool) -> None:
    """
    Expose the inspector on every configuration step.

    GIVEN real editor header widgets and the current connection state,
    WHEN the header is built,
    THEN the inspector follows the forum zip button and is available only with a live link.
    """
    editor = MagicMock(spec=ParameterEditorWindow)
    editor._connection_recovery = None
    editor.navigation_lock = NavigationLock()
    editor.parameter_editor = MagicMock(is_fc_link_connected=connected)
    parent = tk.Frame(inspector.root)
    editor.put_image_in_label.side_effect = lambda frame, _path: tk.Label(frame)
    ParameterEditorWindow._create_logo_and_forum_help_widgets(editor, parent, "test", "TButton")
    frame = parent.winfo_children()[0]
    buttons = [child for child in frame.pack_slaves() if isinstance(child, frontend.ttk.Button)]
    assert [str(button.cget("text")) for button in buttons] == [_("Zip vehicle for Forum help"), _("MAVLink inspector")]
    buttons[1].invoke()
    assert editor.on_mavlink_inspector_click.called is connected
    parent.destroy()
