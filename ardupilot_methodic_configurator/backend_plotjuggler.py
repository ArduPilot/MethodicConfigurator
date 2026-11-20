"""
Generate PlotJuggler 4 layouts for ArduPilot BIN logs.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np
from jinja2 import Environment, FileSystemLoader, StrictUndefined

from ardupilot_methodic_configurator import _
from ardupilot_methodic_configurator.backend_bin_log import extract_log
from ardupilot_methodic_configurator.backend_filesystem_program_settings import ProgramSettings

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping, Sequence

    from ardupilot_methodic_configurator.log_analysis.data_model_log_data import LogData

LAYOUT_TEMPLATE_NAME = "plotjuggler_layout.pj4.xml.j2"
LAYOUT_FILE_NAME = "plotjuggler_layout.pj4.xml"
INSTANCE_FIELDS = ("I", "Inst", "Instance")  # same labels the PlotJuggler parser uses to split messages per instance
BATTERY_MESSAGE = "BAT"
BATTERY_FIELDS = ("Volt", "Curr", "CurrTot", "RemPct")
GPS_MESSAGE = "GPS"
GPS_ACCURACY_MESSAGE = "GPA"
# Each group holds (message, field) pairs with similar expected amplitudes so that a plot shares a readable y-axis
GPS_FIELD_GROUPS: tuple[tuple[tuple[str, str], ...], ...] = (
    ((GPS_MESSAGE, "Status"), (GPS_MESSAGE, "NSats")),
    ((GPS_MESSAGE, "HDop"),),
    ((GPS_MESSAGE, "Spd"), (GPS_MESSAGE, "VZ")),
    ((GPS_MESSAGE, "Alt"),),
    ((GPS_MESSAGE, "GCrs"), (GPS_MESSAGE, "Yaw")),
    ((GPS_MESSAGE, "Lat"), (GPS_MESSAGE, "Lng")),
)
GPS_ACCURACY_GROUPS: tuple[tuple[tuple[str, str], ...], ...] = (
    ((GPS_ACCURACY_MESSAGE, "HAcc"), (GPS_ACCURACY_MESSAGE, "VAcc"), (GPS_ACCURACY_MESSAGE, "SAcc")),
    ((GPS_MESSAGE, "HDop"), (GPS_ACCURACY_MESSAGE, "VDop")),
    ((GPS_ACCURACY_MESSAGE, "YAcc"),),
)
PID_MESSAGES = ("PIDA", "PIDR", "PIDP", "PIDY")
PID_FIELD_GROUPS: tuple[tuple[str, ...], ...] = (("Tar", "Act", "Err"), ("P", "I", "D", "FF", "DFF"))
RC_INPUT_MESSAGE = "RCIN"
SERVO_OUTPUT_MESSAGE = "RCOU"
RC_CHANNEL_FIELD = re.compile(r"^C(\d+)$")
RCMAP_PARAMETERS = ("RCMAP_ROLL", "RCMAP_PITCH", "RCMAP_THROTTLE", "RCMAP_YAW")
RC_INPUT_CHANNELS = 16
RCOU_FUNCTIONS_MOTOR = frozenset((*range(33, 41), *range(82, 86), *range(160, 180)))
COLOR_PALETTE = ("#1f77b4", "#d62728", "#1ac938", "#ff7f0e", "#9467bd", "#17becf", "#bcbd22")
MODE_MESSAGE = "MODE"
# The ArduPilot BIN loader publishes the flight mode regions on this topic and field, from the MODE rows
MODE_MARKER_TOPIC = "_markers"
MODE_MARKER_FIELD = "mode"
SHADE_FLIGHT_MODES_SETTING = "plotjuggler/shade_flight_modes"


@dataclass(frozen=True)
class _Curve:
    topic: str
    field: str
    color: str
    visible: bool = True


@dataclass(frozen=True)
class _Plot:
    title: str
    curves: list[_Curve]
    id: str = ""
    area_id: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "id", str(uuid.uuid4()))
        object.__setattr__(self, "area_id", str(uuid.uuid4()))


@dataclass(frozen=True)
class _Tab:
    name: str
    plots: list[_Plot]
    id: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "id", str(uuid.uuid4()))

    @property
    def sizes(self) -> str:
        return ";".join(f"{1 / len(self.plots):.8f}" for _plot in self.plots)


def _make_plot(title: str, topic_fields: list[tuple[str, str]]) -> _Plot:
    curves = [
        _Curve(topic=topic, field=field, color=COLOR_PALETTE[index % len(COLOR_PALETTE)])
        for index, (topic, field) in enumerate(topic_fields)
    ]
    return _Plot(title=title, curves=curves)


def _instance_field(columns: np.ndarray) -> str | None:
    """Return the field the PlotJuggler parser splits messages on, which must be an integer instance number."""
    names = columns.dtype.names or ()
    return next(
        (name for name in INSTANCE_FIELDS if name in names and np.issubdtype(columns.dtype[name], np.integer)),
        None,
    )


def _instances(log: LogData, message: str) -> list[int]:
    columns = log.get_message_columns(message)
    if columns is None or columns.size == 0:
        return []
    instance_field = _instance_field(columns)
    if instance_field is None:
        return []
    return sorted({int(value) for value in columns[instance_field]})


def _message_topics(log: LogData, message: str, field: str, instance: int | None = None) -> list[tuple[str, str]]:
    """Return (topic, field) pairs for a message field, restricted to one instance when given."""
    columns = log.get_message_columns(message)
    if columns is None or columns.size == 0 or field not in (columns.dtype.names or ()):
        return []
    if _instance_field(columns) is None:
        return [(message, field)] if instance is None else []
    instances = _instances(log, message)
    selected = instances if instance is None else [instance] if instance in instances else []
    return [(f"{message}/{value}", field) for value in selected]


def _plots(log: LogData, groups: Sequence[Sequence[tuple[str, str]]], instance: int | None = None) -> list[_Plot]:
    """Build one plot per group, skipping groups without any data."""
    plots = []
    for group in groups:
        curves: list[tuple[str, str]] = []
        titles: list[str] = []
        for message, field in group:
            topic_fields = _message_topics(log, message, field, instance)
            if topic_fields:
                curves.extend(topic_fields)
                titles.append(field)
        if curves:
            plots.append(_make_plot(", ".join(dict.fromkeys(titles)), curves))
    return plots


def _rc_channels(log: LogData, message_names: Sequence[str]) -> dict[int, tuple[str, str]]:
    """Map each logged channel to its original topic and field."""
    channels: dict[int, tuple[str, str]] = {}
    for message_name in message_names:
        columns = log.get_message_columns(message_name)
        if columns is None or columns.size == 0:
            continue
        for field in columns.dtype.names or ():
            match = RC_CHANNEL_FIELD.match(field)
            if match is not None:
                channels.setdefault(int(match.group(1)), (message_name, field))
    return channels


def _rc_input_order(channels: Iterable[int], parameters: Mapping[str, float]) -> list[int]:
    """Put the configured roll, pitch, throttle and yaw channels first."""
    preferred = [
        int(parameters[name]) for name in RCMAP_PARAMETERS if parameters.get(name, 0) in range(1, RC_INPUT_CHANNELS + 1)
    ]
    return sorted(
        channels,
        key=lambda channel: (preferred.index(channel) if channel in preferred else len(preferred), channel),
    )


def _rc_output_order(channels: Iterable[int], parameters: Mapping[str, float]) -> list[int]:
    """Put outputs assigned to motor functions first."""
    return sorted(
        channels,
        key=lambda channel: (
            parameters.get(f"SERVO{channel}_FUNCTION", 0) not in RCOU_FUNCTIONS_MOTOR,
            channel,
        ),
    )


def _build_tabs(log: LogData, parameters: Mapping[str, float]) -> list[_Tab]:
    tabs: list[_Tab] = []
    battery_plots = _plots(log, [((BATTERY_MESSAGE, field),) for field in BATTERY_FIELDS])
    if battery_plots:
        tabs.append(_Tab(name=_("Battery"), plots=battery_plots))

    gps_plots = _plots(log, GPS_FIELD_GROUPS)
    if gps_plots:
        tabs.append(_Tab(name=_("GPS"), plots=gps_plots))
    receivers = sorted(set(_instances(log, GPS_MESSAGE)) | set(_instances(log, GPS_ACCURACY_MESSAGE)))
    for receiver in receivers:
        accuracy_plots = _plots(log, GPS_ACCURACY_GROUPS, instance=receiver)
        if accuracy_plots:
            name = _("GPS {receiver} accuracy").format(receiver=receiver + 1)
            tabs.append(_Tab(name=name, plots=accuracy_plots))

    for message in PID_MESSAGES:
        pid_plots = _plots(log, [tuple((message, field) for field in group) for group in PID_FIELD_GROUPS])
        if pid_plots:
            tabs.append(_Tab(name=message, plots=pid_plots))

    rc_input = _rc_channels(log, (RC_INPUT_MESSAGE, "RCI2"))
    if rc_input:
        plot = _make_plot(RC_INPUT_MESSAGE, [rc_input[channel] for channel in _rc_input_order(rc_input, parameters)])
        tabs.append(_Tab(name=RC_INPUT_MESSAGE, plots=[plot]))

    rc_output = _rc_channels(log, (SERVO_OUTPUT_MESSAGE, "RCO2", "RCO3"))
    if rc_output:
        plot = _make_plot(SERVO_OUTPUT_MESSAGE, [rc_output[channel] for channel in _rc_output_order(rc_output, parameters)])
        tabs.append(_Tab(name="RCOUT", plots=[plot]))
    return tabs


def _has_flight_modes(log: LogData) -> bool:
    columns = log.get_message_columns(MODE_MESSAGE)
    return columns is not None and columns.size > 0


def _shade_plots_with_flight_modes(tabs: list[_Tab]) -> None:
    """Add a hidden mode marker curve to every plot: its markers shade the plot background per flight mode."""
    for tab in tabs:
        for plot in tab.plots:
            plot.curves.append(_Curve(topic=MODE_MARKER_TOPIC, field=MODE_MARKER_FIELD, color="#808080", visible=False))


def generate_plotjuggler_layout(log_path: Path, parameters: Mapping[str, float], output_dir: Path) -> Path:
    """Render a PlotJuggler 4 layout with battery, RC input and RC output plots for one log."""
    try:
        log = extract_log(str(log_path))
    except SystemExit as exc:
        raise ValueError(str(exc)) from exc
    tabs = _build_tabs(log, parameters)
    if not tabs:
        msg = _("The log has no battery, GPS, PID or RC channel data to plot")
        raise ValueError(msg)
    if bool(ProgramSettings.get_setting(SHADE_FLIGHT_MODES_SETTING)) and _has_flight_modes(log):
        _shade_plots_with_flight_modes(tabs)

    resolved_log = log_path.resolve()
    environment = Environment(
        loader=FileSystemLoader(Path(__file__).parent),
        autoescape=True,
        undefined=StrictUndefined,
        trim_blocks=True,
        lstrip_blocks=True,
        keep_trailing_newline=True,
    )
    content = environment.get_template(LAYOUT_TEMPLATE_NAME).render(
        tabs=tabs,
        log_path=str(resolved_log),
        log_name=resolved_log.name,
        plugin_config={"filepath": str(resolved_log)},
    )
    layout_path = output_dir / LAYOUT_FILE_NAME
    layout_path.write_text(content, encoding="utf-8")
    return layout_path


def open_in_plotjuggler(log_path: Path, layout_path: Path) -> None:
    """Launch PlotJuggler with the selected log and generated layout."""
    executable = shutil.which("plotjuggler4")
    if executable is None and sys.platform == "win32":
        program_files = os.environ.get("PROGRAMW6432") or os.environ.get("PROGRAMFILES")
        if program_files:
            installed_executable = Path(program_files) / "PlotJuggler4" / "bin" / "PlotJuggler4.exe"
            if installed_executable.is_file():
                executable = str(installed_executable)
    executable = executable or shutil.which("plotjuggler")
    if executable is None:
        msg = _("PlotJuggler 4 was not found on PATH")
        raise FileNotFoundError(msg)
    log_path = log_path.resolve()
    layout_path = layout_path.resolve()
    subprocess.Popen(  # noqa: S603  # pylint: disable=consider-using-with
        [executable, "--datafile", str(log_path), "--layout", str(layout_path)],
        cwd=layout_path.parent,
        close_fds=True,
    )
