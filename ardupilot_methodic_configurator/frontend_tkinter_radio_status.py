"""
Reusable three-column presentation for MAVLink RADIO and RADIO_STATUS readings.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

from __future__ import annotations

from tkinter import ttk
from typing import TYPE_CHECKING, ClassVar

from ardupilot_methodic_configurator import _
from ardupilot_methodic_configurator.frontend_tkinter_show import Tooltip, position_tooltip_at_pointer

if TYPE_CHECKING:
    import tkinter as tk

    from ardupilot_methodic_configurator.data_model_data_telemetry import TelemetryState


class _RadioStatusTooltip(Tooltip):
    """Keep radio status hints beside the pointer and within its monitor."""

    def position_tooltip(self) -> None:
        position_tooltip_at_pointer(self.widget, self.tooltip)


class RadioStatusView(ttk.Frame):  # pylint: disable=too-many-ancestors
    """Render connection health and radio readings as three name/value/unit tuples per row."""

    _TRAFFIC_METRICS = (
        ("rx_rate", _("RX rate"), "B/s"),
        ("tx_rate", _("TX rate"), "B/s"),
        ("parse_error_rate", _("Parse errors"), _("errors/s")),
    )
    _RADIO_METRICS = (
        ("rssi", _("Local RX RSSI"), _("raw")),
        ("remrssi", _("Remote RX RSSI"), _("raw")),
        ("rx_error_rate", _("RX errors"), _("errors/s")),
        ("noise", _("Local noise"), _("raw")),
        ("remnoise", _("Remote noise"), _("raw")),
        ("rxerrors", _("RX errors total"), _("errors")),
        ("fixed", _("Corrected packets"), _("packets")),
        ("txbuf", _("TX buffer free"), "%"),
    )
    _METRIC_HELP: ClassVar[dict[str, str]] = {
        "rx_rate": _(
            "Bytes received by AMC each second on its active connection. B/s means bytes per second. USB "
            "measures USB traffic; connect through a telemetry radio to test that path."
        ),
        "tx_rate": _(
            "Bytes sent by AMC each second. TX means transmit; B/s means bytes per second. Zero can be normal"
            " when the inspector is only listening."
        ),
        "parse_error_rate": _(
            "MAVLink decoding errors observed by AMC per second. This is not a packet-loss percentage. "
            "Increasing errors can indicate a poor link or incorrect serial settings."
        ),
        "rssi": _(
            "Received signal strength at the reporting radio. The raw scale depends on the radio; it is not a"
            " percentage or automatically dBm. Consult your radio's documentation."
        ),
        "remrssi": _(
            "Received signal strength at the far end of the telemetry link. This uses the radio's raw scale "
            "and describes reception in the opposite direction."
        ),
        "noise": _(
            "Background noise at the reporting radio, in device-dependent raw units. Compare it using the "
            "same radio equipment and its manufacturer's guidance."
        ),
        "remnoise": _(
            "Background noise at the far end of the telemetry link, in that radio's raw units. It is not a "
            "signal-strength percentage."
        ),
        "rx_error_rate": _(
            "Increase in the radio's receive-error counter per second. Errors/s is a count rate, not percent "
            "packet loss. It needs two suitable radio reports."
        ),
        "rxerrors": _(
            "Total receive errors reported by the radio. The counter can restart after a radio reboot; it is "
            "not the number of MAVLink messages received by AMC."
        ),
        "fixed": _(
            "Number of radio packets recovered by error correction, as reported by the modem. This is a "
            "cumulative packet count, separate from receive errors."
        ),
        "txbuf": _(
            "Percentage of the radio's transmit buffer that is free. For example, 90% means most queue space "
            "is available. This is not signal strength or percent delivery success."
        ),
    }

    def __init__(self, master: tk.Misc) -> None:
        super().__init__(master)
        self.tooltips: dict[tk.Widget, Tooltip] = {}
        self.connection_status = ttk.Label(self, style="Bold.TLabel", wraplength=520, width=1)
        self.connection_status.grid(row=0, column=0, columnspan=11, sticky="ew", padx=4, pady=(4, 2))
        self.values: dict[str, ttk.Label] = {}
        self.units: dict[str, ttk.Label] = {}
        self._grid_metrics(self._TRAFFIC_METRICS, row=1)
        radio_heading = ttk.Label(self, text=_("Radio Link status"), style="Bold.TLabel")
        radio_heading.grid(row=2, column=0, columnspan=11, sticky="w", padx=4, pady=(8, 2))
        self._radio_widgets = self._grid_metrics(self._RADIO_METRICS, row=3)
        for widget in self._radio_widgets:
            widget.grid_remove()
        self.metrics_note = ttk.Label(self, wraplength=520, justify="left", width=1)
        self.metrics_note.grid(row=6, column=0, columnspan=11, sticky="ew", padx=4, pady=(4, 6))
        for help_widget, help_text in (
            (
                self,
                _(
                    "Traffic is measured on AMC's active connection. Radio readings describe the latest modem"
                    " report on that connection, not the RC receiver setup."
                ),
            ),
            (
                self.connection_status,
                _(
                    "Shows whether AMC has a live connection and recent received messages. Unavailable means "
                    "no current measurement; zero is a measured value."
                ),
            ),
            (
                radio_heading,
                _(
                    "Telemetry modem readings require RADIO or RADIO_STATUS messages. They do not identify "
                    "individual flight-controller serial ports."
                ),
            ),
            (
                self.metrics_note,
                _(
                    "Missing radio reports can be normal over USB. Radio columns appear with fresh reports "
                    "and hide when those reports become stale; other MAVLink traffic may still be arriving."
                ),
            ),
        ):
            self.tooltips[help_widget] = _RadioStatusTooltip(help_widget, help_text)
        self.bind("<Configure>", self._resize_text, add="+")
        for value in self.values.values():
            value.configure(text=_("Unavailable"))

    def _resize_text(self, event: tk.Event) -> None:
        """Wrap the explanation to the space allocated by either host window."""
        wraplength = max(1, event.width - 8)
        for label in (self.connection_status, self.metrics_note):
            label.configure(wraplength=wraplength)

    def _grid_metrics(self, metrics: tuple[tuple[str, str, str], ...], *, row: int) -> list[ttk.Label]:
        """Place metric tuples together, leaving elastic space between their three groups."""
        widgets: list[ttk.Label] = []
        for index, (key, name, unit) in enumerate(metrics):
            metric_row, group = divmod(index, 3)
            column = group * 4
            name_label = ttk.Label(self, text=name)
            name_label.grid(row=row + metric_row, column=column, sticky="w", padx=(4, 1), pady=2)
            value = ttk.Label(self, anchor="e", width=10, padding=(1, 0))
            value.grid(row=row + metric_row, column=column + 1, sticky="e", padx=1, pady=2)
            unit_label = ttk.Label(self, text=unit)
            unit_label.grid(row=row + metric_row, column=column + 2, sticky="w", padx=(1, 4), pady=2)
            self.values[key] = value
            self.units[key] = unit_label
            widgets.extend((name_label, value, unit_label))
            for widget in (name_label, value, unit_label):
                self.tooltips[widget] = _RadioStatusTooltip(widget, self._METRIC_HELP[key])
        for column in (3, 7):
            self.columnconfigure(column, minsize=24, weight=1)
        return widgets

    def update_state(self, state: TelemetryState) -> None:
        """Display the loaded model state; connection ownership stays with the host."""
        sample = state.radio
        for widget in self._radio_widgets:
            if sample is None:
                widget.grid_remove()
            else:
                widget.grid()
        traffic_values = {
            "rx_rate": state.rx_rate,
            "tx_rate": state.tx_rate,
            "parse_error_rate": state.parse_error_rate,
        }
        radio_values = {
            "rssi": sample.rssi if sample else None,
            "remrssi": sample.remrssi if sample else None,
            "noise": sample.noise if sample else None,
            "remnoise": sample.remnoise if sample else None,
            "txbuf": sample.txbuf if sample else None,
            "rx_error_rate": state.radio_error_rate,
            "rxerrors": sample.rxerrors if sample else None,
            "fixed": sample.fixed if sample else None,
        }
        self.connection_status.configure(
            text=(
                _("Unable to read telemetry. Check the connection.")
                if state.error
                else _("Flight controller disconnected.")
                if not state.connected
                else _("Traffic received on the active connection")
                if state.receiving
                else _("No current MAVLink data. Check telemetry power, wiring and connection selection.")
            )
        )
        self.metrics_note.configure(
            text=(
                _("Radio link metrics cannot be presented. They require RADIO or RADIO_STATUS MAVLink messages.")
                if sample is None
                else _(
                    "RSSI and noise are device-dependent raw values. "
                    "Remote RX RSSI describes reception at the far end. "
                    "RX errors/s is a counter rate, not a loss percentage."
                )
            )
        )
        for key, value in {**traffic_values, **radio_values}.items():
            self.values[key].configure(
                text=(
                    _("Unavailable")
                    if value is None
                    else f"{value:.1f}"
                    if key in {"rx_rate", "tx_rate", "parse_error_rate", "rx_error_rate"}
                    else str(value)
                )
            )
