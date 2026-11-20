#!/usr/bin/env python3
"""
Tests for the Jinja2-based PlotJuggler 4 layout generator.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import shutil
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from xml.etree.ElementTree import Element

import numpy as np
import pytest
from defusedxml import ElementTree as DET  # noqa: N814, just parsing, no data-structure manipulation

from ardupilot_methodic_configurator import backend_plotjuggler
from ardupilot_methodic_configurator.backend_plotjuggler import generate_plotjuggler_layout, open_in_plotjuggler

FIXTURE_LOG = Path(__file__).parent / "fixtures" / "backend_log_80k.bin"
BATTERY_DTYPE = [("Inst", "i1"), ("Volt", "f4"), ("Curr", "f4"), ("CurrTot", "f4"), ("RemPct", "f4")]
GPS_DTYPE = [("I", "u1"), ("Status", "u1"), ("NSats", "u1"), ("HDop", "f4"), ("Spd", "f4"), ("VZ", "f4"), ("Alt", "f4")]
GPA_DTYPE = [("I", "u1"), ("HAcc", "f4"), ("VAcc", "f4"), ("SAcc", "f4"), ("VDop", "f4"), ("YAcc", "f4")]


def _stub_log(messages: dict[str, np.ndarray]) -> SimpleNamespace:
    """Stand-in for LogData exposing only the message columns used by the generator."""
    return SimpleNamespace(get_message_columns=messages.get)


def _instanced_array(dtype: list[tuple[str, str]], instances: list[int]) -> np.ndarray:
    rows = np.zeros(len(instances), dtype=dtype)
    rows["I"] = instances
    return rows


def _rc_array(channels: list[int], message_dtype: str = "u2") -> np.ndarray:
    dtype = [(f"C{channel}", message_dtype) for channel in channels]
    return np.zeros(3, dtype=dtype)


def _battery_array(instances: list[int]) -> np.ndarray:
    rows = np.zeros(len(instances), dtype=BATTERY_DTYPE)
    rows["Inst"] = instances
    return rows


def _load_root(layout_path: Path) -> Element:
    root: Element | None = DET.parse(layout_path).getroot()
    assert root is not None
    return root


def _parse_tabs(layout_path: Path) -> dict[str, Element]:
    return {tab.get("tab_name", ""): tab for tab in _load_root(layout_path).iter("Tab")}


def _curve_fields(tab: Element) -> list[str]:
    return [curve.get("field", "") for curve in tab.iter("curve") if curve.get("topic") != "_markers"]


def test_layout_contains_expected_tabs_in_output_directory(tmp_path: Path) -> None:
    """Given a log with battery, GPS, PID and RC data, when generating, then the layout is written to the output directory."""
    layout_path = generate_plotjuggler_layout(FIXTURE_LOG, {}, tmp_path)

    assert layout_path == tmp_path / "plotjuggler_layout.pj4.xml"
    tabs = _parse_tabs(layout_path)
    assert list(tabs) == ["Battery", "GPS", "GPS 1 accuracy", "PIDA", "PIDR", "PIDP", "PIDY", "RCIN", "RCOUT"]
    assert _curve_fields(tabs["RCIN"]) == [f"C{channel}" for channel in range(1, 17)]


def test_gps_signals_with_similar_amplitudes_share_a_plot_across_receivers(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Given two GPS receivers, when generating, then speed and vertical speed share one plot with a curve per receiver."""
    stub = _stub_log({"GPS": _instanced_array(GPS_DTYPE, [0, 1]), "RCIN": _rc_array([1])})
    monkeypatch.setattr(backend_plotjuggler, "extract_log", lambda _path: stub)

    layout_path = generate_plotjuggler_layout(FIXTURE_LOG, {}, tmp_path)

    gps_tab = _parse_tabs(layout_path)["GPS"]
    speed_plot = next(plot for plot in gps_tab.iter("plot") if plot.get("title") == "Spd, VZ")
    assert sorted((curve.get("topic"), curve.get("field")) for curve in speed_plot.iter("curve")) == [
        ("GPS/0", "Spd"),
        ("GPS/0", "VZ"),
        ("GPS/1", "Spd"),
        ("GPS/1", "VZ"),
    ]


def test_each_gps_receiver_gets_an_accuracy_tab(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Given two GPS receivers with accuracy messages, when generating, then each receiver has its own accuracy tab."""
    stub = _stub_log(
        {
            "GPS": _instanced_array(GPS_DTYPE, [0, 1]),
            "GPA": _instanced_array(GPA_DTYPE, [0, 1]),
            "RCIN": _rc_array([1]),
        }
    )
    monkeypatch.setattr(backend_plotjuggler, "extract_log", lambda _path: stub)

    layout_path = generate_plotjuggler_layout(FIXTURE_LOG, {}, tmp_path)

    tabs = _parse_tabs(layout_path)
    assert [name for name in tabs if "accuracy" in name] == ["GPS 1 accuracy", "GPS 2 accuracy"]
    horizontal_accuracy = [
        (curve.get("topic"), curve.get("field"))
        for curve in tabs["GPS 2 accuracy"].iter("curve")
        if curve.get("field") == "HAcc"
    ]
    assert horizontal_accuracy == [("GPA/1", "HAcc")]


def test_pid_integral_term_is_not_mistaken_for_an_instance(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Given a PIDR message whose float I field is the integral term, when generating, then it uses the plain topic."""
    pid_dtype = [("Tar", "f4"), ("Act", "f4"), ("Err", "f4"), ("P", "f4"), ("I", "f4"), ("D", "f4")]
    stub = _stub_log({"PIDR": np.zeros(3, dtype=pid_dtype), "RCIN": _rc_array([1])})
    monkeypatch.setattr(backend_plotjuggler, "extract_log", lambda _path: stub)

    layout_path = generate_plotjuggler_layout(FIXTURE_LOG, {}, tmp_path)

    integral_curves = [(curve.get("topic"), curve.get("field")) for curve in _parse_tabs(layout_path)["PIDR"].iter("curve")]
    assert ("PIDR", "I") in integral_curves
    assert all(topic == "PIDR" for topic, _field in integral_curves)


def test_rcin_roll_pitch_throttle_yaw_channels_come_first(tmp_path: Path) -> None:
    """Given an RCMAP that maps roll to channel 3, when generating, then channel 3 is the first RCIN curve."""
    parameters = {"RCMAP_ROLL": 3, "RCMAP_PITCH": 1, "RCMAP_THROTTLE": 2, "RCMAP_YAW": 4}

    layout_path = generate_plotjuggler_layout(FIXTURE_LOG, parameters, tmp_path)

    fields = _curve_fields(_parse_tabs(layout_path)["RCIN"])
    assert fields[:4] == ["C3", "C1", "C2", "C4"]


def test_rcout_motors_from_all_function_ranges_come_first(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Given tilt, generator and motor outputs, when generating, then only motor outputs are prioritised."""
    functions = (41, 42, 45, 46, 47, 33, 40, 82, 85, 160, 179)
    parameters = {f"SERVO{channel}_FUNCTION": function for channel, function in enumerate(functions, start=1)}
    stub = _stub_log({"RCOU": _rc_array(list(range(1, len(functions) + 1)))})
    monkeypatch.setattr(backend_plotjuggler, "extract_log", lambda _path: stub)

    layout_path = generate_plotjuggler_layout(FIXTURE_LOG, parameters, tmp_path)

    assert _curve_fields(_parse_tabs(layout_path)["RCOUT"]) == [
        "C6",
        "C7",
        "C8",
        "C9",
        "C10",
        "C11",
        "C1",
        "C2",
        "C3",
        "C4",
        "C5",
    ]


def test_rc_tabs_include_higher_channels_from_their_original_topics(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Given extended RC messages, when generating, then include their channels in the configured order."""
    stub = _stub_log(
        {
            "RCIN": _rc_array(list(range(1, 15))),
            "RCI2": np.zeros(3, dtype=[("C15", "u2"), ("C16", "u2"), ("OMask", "u2"), ("Flags", "u1")]),
            "RCOU": _rc_array(list(range(1, 15))),
            "RCO2": _rc_array(list(range(15, 19))),
            "RCO3": _rc_array(list(range(19, 33))),
        }
    )
    monkeypatch.setattr(backend_plotjuggler, "extract_log", lambda _path: stub)
    parameters = {"RCMAP_ROLL": 15, "RCMAP_PITCH": 2, "SERVO16_FUNCTION": 82, "SERVO32_FUNCTION": 179}

    layout_path = generate_plotjuggler_layout(FIXTURE_LOG, parameters, tmp_path)

    tabs = _parse_tabs(layout_path)
    assert [(curve.get("topic"), curve.get("field")) for curve in tabs["RCIN"].iter("curve")] == [
        ("RCI2", "C15"),
        ("RCIN", "C2"),
        ("RCIN", "C1"),
        *(("RCIN", f"C{channel}") for channel in range(3, 15)),
        ("RCI2", "C16"),
    ]
    assert [(curve.get("topic"), curve.get("field")) for curve in tabs["RCOUT"].iter("curve")] == [
        ("RCO2", "C16"),
        ("RCO3", "C32"),
        *(("RCOU", f"C{channel}") for channel in range(1, 15)),
        *(("RCO2", f"C{channel}") for channel in (15, 17, 18)),
        *(("RCO3", f"C{channel}") for channel in range(19, 32)),
    ]


def test_each_battery_instance_gets_its_own_curve(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Given two battery instances, when generating, then each voltage curve references its own BAT topic."""
    stub = _stub_log({"BAT": _battery_array([0, 2]), "RCIN": _rc_array([1])})
    monkeypatch.setattr(backend_plotjuggler, "extract_log", lambda _path: stub)

    layout_path = generate_plotjuggler_layout(FIXTURE_LOG, {}, tmp_path)

    battery_tab = _parse_tabs(layout_path)["Battery"]
    volt_curves = [curve for curve in battery_tab.iter("curve") if curve.get("field") == "Volt"]
    assert [curve.get("topic") for curve in volt_curves] == ["BAT/0", "BAT/2"]


def test_every_plot_gets_a_hidden_flight_mode_marker_curve(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Given flight mode changes and shading enabled, when generating, then every plot has a hidden mode marker curve."""
    monkeypatch.setattr(backend_plotjuggler.ProgramSettings, "get_setting", lambda _setting: True)
    layout_path = generate_plotjuggler_layout(FIXTURE_LOG, {}, tmp_path)

    plots = list(_load_root(layout_path).iter("plot"))
    assert plots
    for plot in plots:
        mode_curves = [curve for curve in plot.iter("curve") if curve.get("topic") == "_markers"]
        assert len(mode_curves) == 1
        assert mode_curves[0].get("field") == "mode"
        assert mode_curves[0].get("markers_visible") == "true"
        assert mode_curves[0].get("visible") == "false"


def test_disabled_shading_setting_adds_no_mode_marker_curve(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Given flight mode changes and shading disabled, when generating, then no curve references the mode topic."""
    monkeypatch.setattr(backend_plotjuggler.ProgramSettings, "get_setting", lambda _setting: False)
    layout_path = generate_plotjuggler_layout(FIXTURE_LOG, {}, tmp_path)

    assert not any(curve.get("topic") == "_markers" for curve in _load_root(layout_path).iter("curve"))


def test_log_without_flight_modes_has_no_mode_marker_curve(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Given a log without MODE rows, when generating, then no curve references the flight mode marker topic."""
    stub = _stub_log({"BAT": _battery_array([0]), "RCIN": _rc_array([1])})
    monkeypatch.setattr(backend_plotjuggler, "extract_log", lambda _path: stub)

    layout_path = generate_plotjuggler_layout(FIXTURE_LOG, {}, tmp_path)

    assert not any(curve.get("topic") == "_markers" for curve in _load_root(layout_path).iter("curve"))


def test_malformed_log_reports_extraction_error(tmp_path: Path) -> None:
    """Given a malformed log, when extracting exits, then layout generation reports a catchable error."""
    error = SystemExit("Malformed PARM record")
    with (
        patch.object(backend_plotjuggler, "extract_log", side_effect=error),
        pytest.raises(ValueError, match="Malformed PARM record") as caught,
    ):
        generate_plotjuggler_layout(FIXTURE_LOG, {}, tmp_path)

    assert caught.value.__cause__ is error
    assert not (tmp_path / "plotjuggler_layout.pj4.xml").exists()


def test_log_without_battery_gps_pid_or_rc_data_is_rejected(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Given a log with none of the plotted messages, when generating, then a ValueError is raised and no layout is written."""
    monkeypatch.setattr(backend_plotjuggler, "extract_log", lambda _path: _stub_log({}))

    with pytest.raises(ValueError, match="no battery, GPS, PID or RC"):
        generate_plotjuggler_layout(FIXTURE_LOG, {}, tmp_path)
    assert not (tmp_path / "plotjuggler_layout.pj4.xml").exists()


def test_special_characters_in_log_path_produce_valid_xml(tmp_path: Path) -> None:
    """Given a log path with XML-special characters, when generating, then the layout preserves the path in valid XML."""
    log_path = tmp_path / "flight & 'test' [1].bin"
    shutil.copyfile(FIXTURE_LOG, log_path)

    layout_path = generate_plotjuggler_layout(log_path, {}, tmp_path)

    root = _load_root(layout_path)
    file_info = root.find("previouslyLoaded_Datafiles/fileInfo")
    assert file_info is not None
    assert file_info.get("filename") == str(log_path.resolve())


@pytest.mark.parametrize("executable", ["plotjuggler4", "plotjuggler"])
def test_plotjuggler_on_path_receives_absolute_log_and_layout_paths(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, executable: str
) -> None:
    """Given relative paths in different directories, when opening, then both paths work from PlotJuggler's cwd."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(backend_plotjuggler.sys, "platform", "linux")
    log = Path("local logs") / "flight.bin"
    layout = Path("vehicle files") / "layout.xml"
    with (
        patch.object(
            backend_plotjuggler.shutil, "which", side_effect=lambda name: name if name == executable else None
        ) as which,
        patch.object(backend_plotjuggler.subprocess, "Popen") as popen,
    ):
        open_in_plotjuggler(log, layout)

    assert [call.args[0] for call in which.call_args_list] == (
        ["plotjuggler4"] if executable == "plotjuggler4" else ["plotjuggler4", "plotjuggler"]
    )
    popen.assert_called_once_with(
        [executable, "--datafile", str(log.resolve()), "--layout", str(layout.resolve())],
        cwd=layout.resolve().parent,
        close_fds=True,
    )


def test_plotjuggler_uses_default_windows_installation_without_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Given a default PlotJuggler 4 installation, when opening, then PATH does not need to contain it."""
    executable = tmp_path / "PlotJuggler4" / "bin" / "PlotJuggler4.exe"
    executable.parent.mkdir(parents=True)
    executable.touch()
    monkeypatch.setenv("PROGRAMW6432", str(tmp_path))
    monkeypatch.setattr(backend_plotjuggler.sys, "platform", "win32")

    with (
        patch.object(backend_plotjuggler.shutil, "which", return_value=None) as which,
        patch.object(backend_plotjuggler.subprocess, "Popen") as popen,
    ):
        open_in_plotjuggler(FIXTURE_LOG, tmp_path / "layout.xml")

    which.assert_called_once_with("plotjuggler4")
    assert popen.call_args.args[0][0] == str(executable)


def test_plotjuggler_reports_missing_executable(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Given no PlotJuggler executable, when opening, then report that it could not be found."""
    monkeypatch.setattr(backend_plotjuggler.sys, "platform", "linux")

    with (
        patch.object(backend_plotjuggler.shutil, "which", return_value=None),
        patch.object(backend_plotjuggler.subprocess, "Popen") as popen,
        pytest.raises(FileNotFoundError, match="PlotJuggler 4 was not found"),
    ):
        open_in_plotjuggler(FIXTURE_LOG, tmp_path / "layout.xml")

    popen.assert_not_called()
