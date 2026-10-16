"""
Standalone and embedded MAVLink message inspector.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

# PYTHON_ARGCOMPLETE_OK

import sys
import tkinter as tk
from argparse import ArgumentParser, Namespace
from contextlib import suppress
from functools import partial
from logging import basicConfig as logging_basicConfig
from tkinter import ttk
from typing import ClassVar

import argcomplete

from ardupilot_methodic_configurator import _
from ardupilot_methodic_configurator.backend_data_telemetry import DataTelemetryBackend
from ardupilot_methodic_configurator.backend_flightcontroller import FlightController
from ardupilot_methodic_configurator.backend_internet import webbrowser_open_url
from ardupilot_methodic_configurator.common_arguments import add_common_arguments
from ardupilot_methodic_configurator.data_model_data_telemetry import DataTelemetryDataModel, TelemetryState
from ardupilot_methodic_configurator.data_model_mavlink_inspector import MESSAGE_COLUMNS, MavlinkInspectorDataModel
from ardupilot_methodic_configurator.frontend_tkinter_base_window import BaseWindow, show_error_popup
from ardupilot_methodic_configurator.frontend_tkinter_collapsible_label_frame import CollapsibleLabelFrame
from ardupilot_methodic_configurator.frontend_tkinter_parameter_application import connect_standalone_flight_controller
from ardupilot_methodic_configurator.frontend_tkinter_radio_status import RadioStatusView
from ardupilot_methodic_configurator.frontend_tkinter_show import Tooltip, position_tooltip_at_pointer


class _InspectorTooltip(Tooltip):
    """Keep inspector tooltips beside the pointer and within its monitor."""

    def position_tooltip(self) -> None:
        position_tooltip_at_pointer(self.widget, self.tooltip)


class MavlinkInspectorWindow(BaseWindow):  # pylint: disable=too-many-instance-attributes
    """Inspect live MAVLink messages using the supplied flight-controller connection."""

    _TABLE_HELP = _(
        "Each row is a received message type from one sender. Select a row to read its latest fields. "
        "Click a heading to sort; click it again to reverse the order."
    )
    _COLUMN_HELP: ClassVar[dict[str, str]] = {
        "system": _("The sender's MAVLink system number identifies a vehicle or other system, not a serial port."),
        "component": _(
            "The sender's component number identifies a part of that system, such as its flight controller or radio."
        ),
        "message": _(
            "The message name describes the information received. HEARTBEAT announces a sender; ATTITUDE reports orientation."
        ),
        "count": _(
            "How many messages of this type AMC has observed from this sender during monitoring. This is not "
            "a lost-packet count."
        ),
        "hz": _("Hz means messages per second. For example, 10 Hz means about ten messages arrive each second."),
        "bytes": _(
            "B/s means received bytes per second for this message type, including MAVLink headers. It is "
            "traffic, not maximum link speed."
        ),
        "age": _(
            "Seconds since AMC last received this message from this sender. A growing age means no fresh message; "
            "rates become zero after about three seconds."
        ),
    }

    def __init__(self, flight_controller: FlightController, parent: tk.Tk | tk.Toplevel | None = None) -> None:
        super().__init__(parent)
        self.root.title(_("MAVLink inspector"))
        self.root.geometry(self.calculate_scaled_geometry(750, 650))
        self.backend = DataTelemetryBackend(flight_controller)
        self.model = DataTelemetryDataModel(flight_controller)
        self.message_model = MavlinkInspectorDataModel()
        self.tooltips: dict[tk.Widget, Tooltip] = {}
        self._hovered_cell: tuple[str, str] | None = None
        self._timer_id: str | None = None
        self._resize_timer_id: str | None = None
        self._closed = False
        self._state = TelemetryState()
        self._column_labels: dict[str, str] = {}
        self.root.protocol("WM_DELETE_WINDOW", self.close)
        self.root.bind("<Destroy>", self._on_destroy, add="+")
        if parent is not None and parent.winfo_viewable():
            self.root.transient(parent)
        self.status = ttk.Label(self.main_frame, wraplength=700, width=1)
        self.status.pack(fill="x", padx=8, pady=8)
        self.connection_note = ttk.Label(
            self.main_frame,
            text=_(
                "A USB connection measures USB traffic, not the telemetry radio link. "
                "Connect through the telemetry link you want to test."
            ),
            wraplength=700,
            width=1,
        )
        self.connection_note.pack(fill="x", padx=8, pady=(0, 6))
        self.main_frame.bind("<Configure>", self._resize_notices, add="+")
        # pylint: disable=duplicate-code
        self.section_panes = tk.PanedWindow(
            self.main_frame,
            orient=tk.VERTICAL,
            sashwidth=round(6 * self.dpi_scaling_factor),
            sashrelief=tk.RAISED,
            sashcursor="sb_v_double_arrow",
            opaqueresize=True,
            borderwidth=0,
        )
        # pylint: enable=duplicate-code
        self.section_panes.pack(fill=tk.BOTH, expand=True, padx=8, pady=(0, 4))
        minimum_section_height = round(60 * self.dpi_scaling_factor)
        self._minimum_section_height = minimum_section_height
        self._expanded_message_pane_height: int | None = None
        self._setup_message_table()
        fields_frame = ttk.Frame(self.section_panes)
        self._message_fields_pane = fields_frame
        self.section_panes.add(fields_frame, minsize=minimum_section_height, stretch="always", sticky="nsew")
        self._setup_message_contents(fields_frame)
        self.message_contents.bind("<<CollapsibleToggled>>", self._on_message_contents_toggled, add="+")
        self._setup_footer()
        self._setup_tooltips()
        self.refresh(self._state)
        self.center_window_on_screen(self.root)
        self._timer_id = self.root.after(250, self._poll)
        if parent is not None and sys.platform != "darwin":
            self.root.grab_set()

    def _setup_message_table(self) -> None:
        """Build the sortable received-message table and its scrollbar."""
        self.table_frame = ttk.Frame(self.section_panes)
        self.section_panes.add(self.table_frame, minsize=self._minimum_section_height, stretch="always", sticky="nsew")
        self.table = ttk.Treeview(self.table_frame, columns=MESSAGE_COLUMNS, show="headings", selectmode="browse", height=12)
        for column, heading in zip(
            MESSAGE_COLUMNS,
            (_("System"), _("Component"), _("Message"), _("Count"), _("Hz"), _("B/s"), _("Age (s)")),
            strict=True,
        ):
            self._column_labels[column] = heading
            self.table.heading(column, text=heading, command=partial(self._sort_by_column, column))
            self.table.column(column, width=220 if column == "message" else 85, stretch=True)
        self.table.tag_configure("striped", background="#eeeeee")
        self.table_scrollbar = ttk.Scrollbar(self.table_frame, orient="vertical", command=self.table.yview)
        self.table.configure(yscrollcommand=self.table_scrollbar.set)
        self.table_scrollbar.pack(side="right", fill="y")
        self.table.pack(fill="both", expand=True)
        self.table.bind("<<TreeviewSelect>>", self._show_fields)

    def _setup_message_contents(self, fields_frame: ttk.Frame) -> None:
        """Place decoded fields inside a collapsible section."""
        self.message_contents = CollapsibleLabelFrame(fields_frame, text=_("MAVLink message contents"))
        self.message_contents.pack(fill="both", expand=True)
        self.fields = tk.Text(self.message_contents.content_frame, height=8, wrap="word", state="disabled")
        self.fields_scrollbar = ttk.Scrollbar(
            self.message_contents.content_frame, orient="vertical", command=self.fields.yview
        )
        self.fields.configure(yscrollcommand=self.fields_scrollbar.set)
        self.fields_scrollbar.pack(side="right", fill="y")
        self.fields.pack(fill="both", expand=True)

    def _setup_footer(self) -> None:
        """Keep the radio status and close control visible outside the resizable panes."""
        self.footer = ttk.Frame(self.main_frame)
        self.footer.pack(side="bottom", fill="x", padx=8, pady=(2, 0), before=self.section_panes)
        self.radio_status = RadioStatusView(self.footer)
        self.radio_status.pack(fill="x", expand=False)
        self.buttons_frame = ttk.Frame(self.footer)
        self.buttons_frame.pack(pady=8)
        self.help_button = ttk.Button(
            self.buttons_frame,
            text=_("Help"),
            command=lambda: webbrowser_open_url(
                "https://ardupilot.github.io/MethodicConfigurator/USERMANUAL_MAVLink_inspector.html"
            ),
        )
        self.help_button.pack(side="left", padx=(4, self.calculate_scaled_padding(16)))
        self.close_button = ttk.Button(self.buttons_frame, text=_("Close"), command=self.close)
        self.close_button.pack(side="left", padx=(self.calculate_scaled_padding(16), 4))

    def _resize_notices(self, event: tk.Event) -> None:
        """Keep connection guidance readable when the inspector is made narrower."""
        for label in (self.status, self.connection_note):
            label.configure(wraplength=max(1, event.width - 16))

    def _setup_tooltips(self) -> None:
        """Explain all visible controls and container backgrounds without requiring MAVLink knowledge."""
        fields_help = _(
            "Latest decoded fields of the selected message. These are received data, not editable parameters. "
            "Field units depend on the message; Help links to the reference."
        )
        pane_help = _(
            "Drag the horizontal divider to give more height to the message table or decoded fields. The "
            "status footer stays visible."
        )
        for widget, help_text in (
            (
                self.main_frame,
                _("Monitor messages reaching AMC through its active connection. Use Help for a step-by-step introduction."),
            ),
            (
                self.status,
                _("Shows whether recent MAVLink messages are arriving. Increasing counts and small ages indicate fresh data."),
            ),
            (
                self.connection_note,
                _(
                    "To test a wireless telemetry link, connect AMC through that link. Direct USB traffic "
                    "measures the USB path."
                ),
            ),
            (self.section_panes, pane_help),
            (self.table_frame, self._TABLE_HELP),
            (self.table, self._TABLE_HELP),
            (
                self.table_scrollbar,
                _("Drag to scroll through received message types. Scrolling does not change the selected message."),
            ),
            (self._message_fields_pane, fields_help),
            (self.message_contents, fields_help),
            (self.message_contents.content_frame, fields_help),
            (self.fields, fields_help),
            (
                self.fields_scrollbar,
                _(
                    "Scroll through all decoded fields of the selected message. Select another table row to "
                    "inspect a different message."
                ),
            ),
            (
                self.footer,
                _(
                    "Connection traffic and radio readings stay visible here while the message table and "
                    "decoded fields are resized."
                ),
            ),
            (
                self.buttons_frame,
                _("Help opens the beginner's manual. Close returns to AMC, or ends the standalone inspector."),
            ),
            (
                self.help_button,
                _(
                    "Open the MAVLink inspector beginner's manual in your web browser. It explains the "
                    "columns, radio readings and connection checks; internet access is needed."
                ),
            ),
            (
                self.close_button,
                _(
                    "Stop monitoring and close this window. AMC keeps its connection; the standalone "
                    "inspector closes its own connection."
                ),
            ),
        ):
            self.tooltips[widget] = _InspectorTooltip(widget, help_text)
        self.message_contents.set_header_tooltip(
            _(
                "Click to hide or restore decoded message fields and give the table more room. You can also "
                "focus this title with Tab and press Enter or Space."
            )
        )
        self.tooltips[self.message_contents.header_label] = self.message_contents.header_tooltip
        self.table.bind("<Enter>", self._on_table_hover, add="+")
        self.table.bind("<Motion>", self._on_table_hover, add="+")
        for sequence in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
            self.table.bind(sequence, self._hide_table_tooltip, add="+")

    def _on_table_hover(self, event: tk.Event) -> None:
        """Explain the specific heading or cell currently under the pointer."""
        column = self.table.identify_column(event.x)
        region = self.table.identify_region(event.x, event.y)
        context = (column, region)
        if context == self._hovered_cell:
            return
        self._hovered_cell = context
        tooltip = self.tooltips[self.table]
        tooltip.force_hide()
        columns = {f"#{index}": name for index, name in enumerate(MESSAGE_COLUMNS, start=1)}
        if region == "separator":
            text = _("Drag this divider to change the column width. Click a column heading to sort its values.")
        elif region in ("heading", "cell") and column in columns:
            action = (
                _("Click to sort; click again to reverse the order.")
                if region == "heading"
                else _("Select a row to read its latest decoded fields below.")
            )
            text = f"{self._COLUMN_HELP[columns[column]]} {action}"
        else:
            text = self._TABLE_HELP
        tooltip.text = text
        tooltip.schedule_show(event)

    def _hide_table_tooltip(self, _event: tk.Event) -> None:
        """Dismiss a cell hint while the user scrolls to different messages."""
        self.tooltips[self.table].force_hide()
        self._hovered_cell = None

    def _on_message_contents_toggled(self, _event: tk.Event) -> None:
        """Let the decoded-fields pane shrink to its title while collapsed."""
        expanded = self.message_contents.expanded
        if not expanded:
            self._expanded_message_pane_height = self._message_fields_pane.winfo_height()
        self.section_panes.paneconfigure(  # type: ignore[no-untyped-call]
            self._message_fields_pane,
            minsize=self._minimum_section_height if expanded else 0,
            stretch="always" if expanded else "never",
        )
        if self._resize_timer_id is not None:
            self.root.after_cancel(self._resize_timer_id)
        self._resize_timer_id = self.root.after_idle(self._resize_message_contents_pane)

    def _resize_message_contents_pane(self) -> None:
        """Move the lower sash to give collapsed or restored space to the other panes."""
        self._resize_timer_id = None
        if self._closed:
            return
        self.message_contents.update_idletasks()
        if self._closed:
            return
        if self.message_contents.expanded:
            target_height = self._expanded_message_pane_height or self._minimum_section_height
        else:
            target_height = self.message_contents.winfo_reqheight()
        sash_y = self.section_panes.winfo_height() - target_height
        self.section_panes.sash_place(0, 0, sash_y)

    def refresh(self, state: TelemetryState) -> None:
        """Update rows in place, preserving selection while expiring stale rates."""
        self._state = state
        self.message_model.update(state)
        self.radio_status.update_state(state)
        self.status.configure(
            text=_("Received messages: select a row to view fields. Rates update every second; age reveals stale messages.")
            if state.receiving
            else _("No current MAVLink messages. Check the telemetry connection.")
        )
        self._render_message_rows()
        self._show_fields()

    def _render_message_rows(self) -> None:
        """Refresh table values and stripes in the model's order without losing selection."""
        identifiers = set()
        for index, row in enumerate(self.message_model.rows):
            identifier = self.message_model.identifier(row)
            identifiers.add(identifier)
            values = self.message_model.values(row)
            tags = ("striped",) if index % 2 else ()
            if self.table.exists(identifier):
                self.table.item(identifier, values=values, tags=tags)
            else:
                self.table.insert("", "end", iid=identifier, values=values, tags=tags)
            self.table.move(identifier, "", index)
        for identifier in self.table.get_children():
            if identifier not in identifiers:
                self.table.delete(identifier)
        for name, label in self._column_labels.items():
            arrow = " ▼" if self.message_model.sort_descending else " ▲"
            self.table.heading(name, text=label + arrow if name == self.message_model.sort_column else label)

    def _show_fields(self, _event: tk.Event | None = None) -> None:
        """Refresh changed fields while preserving the reader's scroll position."""
        selection = self.table.selection()
        text = self.message_model.fields(selection[0]) if selection else ""
        if self.fields.get("1.0", "end-1c") == text:
            return
        view = self.fields.yview()
        self.fields.configure(state="normal")
        self.fields.delete("1.0", "end")
        self.fields.insert("1.0", text)
        self.fields.configure(state="disabled")
        self.fields.yview_moveto(view[0])

    def _sort_by_column(self, column: str) -> None:
        """Sort ascending on the first click and reverse on subsequent clicks."""
        self.message_model.sort_by(column)
        self._render_message_rows()

    def _poll(self) -> None:
        """Own one bounded receive loop while the inspector is open."""
        if self._closed:
            return
        self._timer_id = None
        self.refresh(self.model.update(self.backend.poll()))
        self._timer_id = self.root.after(250, self._poll)

    def _on_destroy(self, event: tk.Event) -> None:
        if event.widget is self.root:
            self._stop_monitor()

    def _stop_monitor(self) -> None:
        if self._closed:
            return
        self._closed = True
        if self._timer_id is not None:
            with suppress(tk.TclError):
                self.root.after_cancel(self._timer_id)
            self._timer_id = None
        if self._resize_timer_id is not None:
            with suppress(tk.TclError):
                self.root.after_cancel(self._resize_timer_id)
            self._resize_timer_id = None
        self.backend.close()
        self.model.clear_live_data()

    def close(self) -> None:
        """Release observers and timers; an embedded inspector never disconnects the FC."""
        self._stop_monitor()
        with suppress(tk.TclError):
            self.root.destroy()


def open_mavlink_inspector_window(
    root: tk.Tk | tk.Toplevel,
    flight_controller: FlightController,
) -> MavlinkInspectorWindow:
    """Embed the inspector in an existing application-owned Tk event loop."""
    return MavlinkInspectorWindow(flight_controller, root)


def create_argument_parser() -> ArgumentParser:  # pragma: no cover
    """Expose the standard FC connection and logging options with shell completions."""
    parser = ArgumentParser(description=_("Inspect live MAVLink messages and their datarates."))
    parser = FlightController.add_argparse_arguments(parser)
    parser = add_common_arguments(parser)
    argcomplete.autocomplete(parser)
    return parser


def argument_parser() -> Namespace:  # pragma: no cover
    """Parse arguments for the standalone MAVLink inspector."""
    return create_argument_parser().parse_args()


def main() -> None:  # pragma: no cover
    """Connect without downloading parameters, inspect traffic and always disconnect on exit."""
    args = argument_parser()
    logging_basicConfig(level=args.loglevel, format="%(asctime)s - %(levelname)s - %(message)s")
    controller = FlightController(reboot_time=args.reboot_time, baudrate=args.baudrate)
    window: MavlinkInspectorWindow | None = None
    try:
        if not connect_standalone_flight_controller(args, controller):
            return
        if controller.master is None:
            show_error_popup(_("MAVLink inspector"), _("A live flight-controller connection is required."))
            return
        window = MavlinkInspectorWindow(controller)
        window.root.mainloop()
    finally:
        if window is not None:
            window.close()
        controller.disconnect()


if __name__ == "__main__":  # pragma: no cover
    main()
