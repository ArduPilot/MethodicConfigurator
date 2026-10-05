#!/usr/bin/env python3
"""
BDD tests for the RC calibration frontend.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2026 ArduPilot Contributors

SPDX-License-Identifier: GPL-3.0-or-later
"""

import tkinter as tk
from collections.abc import Generator
from tkinter import ttk
from typing import Any, cast
from unittest.mock import MagicMock, patch

import pytest

from ardupilot_methodic_configurator.data_model_ardupilot_parameter import ArduPilotParameter
from ardupilot_methodic_configurator.data_model_par_dict import Par
from ardupilot_methodic_configurator.data_model_parameter_editor import ParameterEditor
from ardupilot_methodic_configurator.frontend_tkinter_base_window import BaseWindow
from ardupilot_methodic_configurator.frontend_tkinter_calibration_popup_base import CalibrationPopupBase
from ardupilot_methodic_configurator.plugins.data_model_rc_calibration import RCCalibrationDataModel
from ardupilot_methodic_configurator.plugins.frontend_tkinter_rc_calibration import (
    RCCalibrationPopup,
    RCCalibrationView,
    RCChannelBars,
    RCCraftPreview,
    RCStickPreview,
)

# pylint: disable=protected-access,redefined-outer-name


def _label_texts(widget: tk.Misc) -> list[str]:
    """Collect displayed label text throughout a monitor's real widget hierarchy."""
    texts = [str(widget.cget("text"))] if isinstance(widget, (ttk.Label, tk.Label)) else []
    for child in widget.winfo_children():
        texts.extend(_label_texts(child))
    return texts


@pytest.fixture
def rc_channel_bars(tk_root: tk.Tk) -> Generator[RCChannelBars, None, None]:
    """Create and clean up the persistent 16-channel status display."""
    channel_bars = RCChannelBars(tk_root)
    channel_bars.pack(fill="x", expand=True)
    tk_root.update_idletasks()
    yield channel_bars
    channel_bars.destroy()


class TestRCChannelBars:
    """Test the user's live channel-value and calibration-marker display."""

    def test_user_sees_sixteen_channel_rows_and_pwm_values(self, rc_channel_bars: RCChannelBars) -> None:
        """
        The status display always provides a row for each of the first 16 RC inputs.

        GIVEN: A connected receiver reports CH1 and CH16 but no values for other rows
        WHEN: The live channel telemetry is displayed
        THEN: All 16 rows remain visible with PWM values beside the matching bars
        """
        channels = [
            {
                "name": f"CH{channel_number}",
                "value": 1525 if channel_number in (1, 16) else None,
                "min": None,
                "max": None,
            }
            for channel_number in range(1, 17)
        ]

        rc_channel_bars.update_channels(channels)

        assert len(rc_channel_bars._value_labels) == 16
        assert rc_channel_bars._value_labels[1].cget("text") == "1525 µs"
        assert rc_channel_bars._value_labels[2].cget("text") == "No Data"
        assert rc_channel_bars._value_labels[16].cget("text") == "1525 µs"
        assert rc_channel_bars._bar_canvases[1].find_withtag("live_value")

    def test_user_sees_primary_mapping_and_locked_flight_mode_function(
        self,
        tk_root: tk.Tk,
        rc_staging_context: tuple[MagicMock, ParameterEditor],
    ) -> None:
        """
        Primary channels and the flight-mode channel are shown as fixed functions.

        GIVEN: A Mode-2 RC mapping and FLTMODE_CH set to channel 5
        WHEN: The channel monitor is constructed with loaded RCx_OPTION metadata
        THEN: The first four show their mapped axes and CH5 shows Mode, with selectors only on other channels
        """
        controller, editor = rc_staging_context
        model = RCCalibrationDataModel(controller, editor)
        channel_bars = RCChannelBars(tk_root, model)
        try:
            assert [channel_bars._function_labels[number].cget("text") for number in range(1, 5)] == [
                "Roll",
                "Pitch",
                "Throttle",
                "Yaw",
            ]
            assert channel_bars._function_labels[5].cget("text") == "Mode"
            assert set(channel_bars._option_selectors) == set(range(6, 17))
            assert str(channel_bars._option_selectors[6].cget("state")) == "readonly"
            assert "6: AutoTune" in channel_bars._option_selectors[6].cget("values")
            assert "300: QuickTune" in channel_bars._option_selectors[6].cget("values")
            assert "300: QuickTune" in channel_bars._option_selectors[11].cget("values")
        finally:
            channel_bars.destroy()

    @pytest.mark.parametrize("protection", ["readonly", "forced", "derived"])
    def test_user_sees_a_locked_auxiliary_function_after_refresh(
        self, tk_root: tk.Tk, rc_staging_context: tuple[MagicMock, ParameterEditor], protection: str
    ) -> None:
        """
        A locked auxiliary function remains visible through repeated channel refreshes.

        GIVEN: CH5 is a protected Arm/Disarm option and the flight-mode switch is on CH6
        WHEN: The monitor is created and refreshed
        THEN: CH5 displays Arm/Disarm without an editable selector and no FC write occurs
        """
        controller, editor = rc_staging_context
        editor.current_step_parameters["FLTMODE_CH"].set_new_value("6")
        editor.current_step_parameters["RC5_OPTION"] = ArduPilotParameter(
            "RC5_OPTION",
            Par(1, "ExpressLRS arming"),
            metadata={"values": {"0": "Disabled", "1": "Arm/Disarm"}, "ReadOnly": protection == "readonly"},
            fc_value=1,
            forced_par=Par(1, "Required") if protection == "forced" else None,
            derived_par=Par(1, "Required") if protection == "derived" else None,
        )
        model = RCCalibrationDataModel(controller, editor)
        channel_bars = RCChannelBars(tk_root, model)
        try:
            assert channel_bars._function_labels[5].cget("text") == "Arm/Disarm"

            channel_bars.update_channels(model.get_channel_calibration())

            assert channel_bars._function_labels[5].cget("text") == "Arm/Disarm"
            assert 5 not in channel_bars._option_selectors
            controller.set_param.assert_not_called()
        finally:
            channel_bars.destroy()

    @pytest.mark.parametrize("mapping", [("RCMAP_ROLL", 1, "Roll"), ("FLTMODE_CH", 5, "Mode")])
    def test_user_can_edit_the_freed_channel_after_control_mapping_changes(
        self,
        tk_root: tk.Tk,
        rc_staging_context: tuple[MagicMock, ParameterEditor],
        mapping: tuple[str, int, str],
    ) -> None:
        """
        Changing a control channel updates both locked labels and editable selectors.

        GIVEN: An existing monitor with CH6 available for an auxiliary function
        WHEN: A primary control or flight-mode switch moves to CH6 and later moves back
        THEN: The new control channel is locked, the freed channel can stage an option, and moving back restores the controls
        """
        controller, editor = rc_staging_context
        parameter_name, original_channel, function = mapping
        model = RCCalibrationDataModel(controller, editor)
        channel_bars = RCChannelBars(tk_root, model)
        try:
            original_canvas = channel_bars._bar_canvases[original_channel]
            channel_six_canvas = channel_bars._bar_canvases[6]
            editor.current_step_parameters[parameter_name].set_new_value("6")

            channel_bars.update_channels(model.get_channel_calibration())

            assert 6 not in channel_bars._option_selectors
            assert channel_bars._function_labels[6].cget("text") == function
            assert original_channel not in channel_bars._function_labels
            selector = channel_bars._option_selectors[original_channel]
            assert str(selector.cget("state")) == "readonly"
            assert list(channel_bars._channel_rows[original_channel].pack_slaves())[1:3] == [
                selector,
                channel_bars._value_labels[original_channel],
            ]
            selector.set("300: QuickTune")
            selector.event_generate("<<ComboboxSelected>>")
            assert editor.current_step_parameters[f"RC{original_channel}_OPTION"].get_new_value() == 300

            editor.current_step_parameters[parameter_name].set_new_value(str(original_channel))
            channel_bars.update_channels(model.get_channel_calibration())

            assert channel_bars._function_labels[original_channel].cget("text") == function
            assert original_channel not in channel_bars._option_selectors
            assert str(channel_bars._option_selectors[6].cget("state")) == "readonly"
            assert list(channel_bars._channel_rows[6].pack_slaves())[1:3] == [
                channel_bars._option_selectors[6],
                channel_bars._value_labels[6],
            ]
            assert channel_bars._bar_canvases[original_channel] is original_canvas
            assert channel_bars._bar_canvases[6] is channel_six_canvas
            controller.set_param.assert_not_called()
        finally:
            channel_bars.destroy()

    def test_user_can_resume_editing_an_option_after_manual_override_is_enabled(
        self, tk_root: tk.Tk, rc_staging_context: tuple[MagicMock, ParameterEditor]
    ) -> None:
        """
        Parameter edit locks are reconciled without rebuilding the monitor.

        GIVEN: CH6 initially has an editable option
        WHEN: It becomes derived and the user later enables its manual override
        THEN: A fixed function label replaces the selector while locked and editing works again after override
        """
        controller, editor = rc_staging_context
        model = RCCalibrationDataModel(controller, editor)
        channel_bars = RCChannelBars(tk_root, model)
        try:
            parameter = ArduPilotParameter(
                "RC6_OPTION",
                Par(300, "Existing option"),
                metadata={"values": {"0": "Disabled", "300": "QuickTune"}},
                fc_value=0,
                derived_par=Par(300, "Derived option"),
            )
            editor.current_step_parameters["RC6_OPTION"] = parameter

            channel_bars.update_channels(model.get_channel_calibration())

            assert 6 not in channel_bars._option_selectors
            assert channel_bars._function_labels[6].cget("text") == "QuickTune"
            parameter.set_manual_override(True)
            channel_bars.update_channels(model.get_channel_calibration())
            selector = channel_bars._option_selectors[6]
            assert str(selector.cget("state")) == "readonly"
            assert selector.get() == "300: QuickTune"
            selector.set("0: Disabled")
            selector.event_generate("<<ComboboxSelected>>")
            assert parameter.get_new_value() == 0
            assert parameter.change_reason_for_file.count("@manual_override") == 1
            controller.set_param.assert_not_called()
        finally:
            channel_bars.destroy()

    def test_user_can_stage_auxiliary_option_without_writing_to_controller(
        self,
        tk_root: tk.Tk,
        rc_staging_context: tuple[MagicMock, ParameterEditor],
    ) -> None:
        """
        Selecting an auxiliary-channel function edits New values only.

        GIVEN: A Mode-2 mapping and loaded RCx_OPTION choices
        WHEN: The user selects QuickTune for channel 6
        THEN: RC6_OPTION is staged, the channel row refreshes, and no FC write occurs
        """
        controller, editor = rc_staging_context
        model = RCCalibrationDataModel(controller, editor)
        refreshed = MagicMock()
        channel_bars = RCChannelBars(tk_root, model, refreshed)
        try:
            selector = channel_bars._option_selectors[6]
            selector.set("300: QuickTune")
            selector.event_generate("<<ComboboxSelected>>")

            assert editor.current_step_parameters["RC6_OPTION"].get_new_value() == 300
            assert "upload" in channel_bars._feedback_label.cget("text")
            refreshed.assert_called_once()
            controller.set_param.assert_not_called()
        finally:
            channel_bars.destroy()

    def test_user_can_add_a_missing_option_parameter_to_the_current_step(
        self,
        tk_root: tk.Tk,
        rc_staging_context: tuple[MagicMock, ParameterEditor],
    ) -> None:
        """
        A missing RCx_OPTION row is added only when the user chooses that channel's function.

        GIVEN: CH11 option choices from loaded metadata but no current-step RC11_OPTION row
        WHEN: The user selects QuickTune for CH11
        THEN: The row is added and staged without issuing a flight-controller write
        """
        controller, editor = rc_staging_context
        model = RCCalibrationDataModel(controller, editor)
        channel_bars = RCChannelBars(tk_root, model)
        try:
            assert "RC11_OPTION" not in editor.current_step_parameters
            selector = channel_bars._option_selectors[11]
            selector.set("300: QuickTune")
            selector.event_generate("<<ComboboxSelected>>")

            assert editor.current_step_parameters["RC11_OPTION"].get_new_value() == 300
            controller.set_param.assert_not_called()
        finally:
            channel_bars.destroy()

    def test_user_sees_green_minimum_and_red_maximum_markers_over_the_live_bar(
        self, rc_channel_bars: RCChannelBars, tk_root: tk.Tk
    ) -> None:
        """
        Calibration extremes are drawn as differently colored vertical markers on the channel bar.

        GIVEN: CH1 has a live value of 1500 µs and tracked extremes of 1200-1800 µs
        WHEN: The channel status display is refreshed
        THEN: Green MIN and red MAX markers bracket the live value
        """
        channels: list[dict[str, Any]] = [
            {"name": f"CH{number}", "value": None, "min": None, "max": None} for number in range(1, 17)
        ]
        channels[0] = {"name": "CH1", "value": 1500, "min": 1200, "max": 1800}

        rc_channel_bars.update_channels(channels)
        tk_root.update_idletasks()

        canvas = rc_channel_bars._bar_canvases[1]
        minimum_marker = canvas.find_withtag("min_marker")
        maximum_marker = canvas.find_withtag("max_marker")

        assert len(minimum_marker) == 1
        assert len(maximum_marker) == 1
        assert canvas.itemcget(minimum_marker[0], "fill") == "green"
        assert canvas.itemcget(maximum_marker[0], "fill") == "red"
        minimum_x = canvas.coords(minimum_marker[0])[0]
        live_x = canvas.coords(canvas.find_withtag("live_value")[0])[2]
        maximum_x = canvas.coords(maximum_marker[0])[0]
        assert minimum_x < live_x < maximum_x

    def test_user_sees_min_max_trim_markers_before_starting_calibration(self, rc_channel_bars: RCChannelBars) -> None:
        """
        Default MIN/MAX/TRIM markers remain visible before calibration starts.

        GIVEN: A channel has live telemetry but no recorded calibration or loaded parameters
        WHEN: The status display is updated
        THEN: It draws the live bar and labelled default markers
        """
        channels: list[dict[str, Any]] = [
            {"name": f"CH{number}", "value": None, "min": None, "max": None} for number in range(1, 17)
        ]
        channels[0]["value"] = 1500

        rc_channel_bars.update_channels(channels)

        canvas = rc_channel_bars._bar_canvases[1]
        assert canvas.find_withtag("live_value")
        assert len(canvas.find_withtag("calibration_marker")) == 3
        for name, color in (("min", "green"), ("trim", "blue"), ("max", "red")):
            assert canvas.itemcget(canvas.find_withtag(f"{name}_marker")[0], "fill") == color
            assert canvas.itemcget(canvas.find_withtag(f"{name}_label")[0], "text") == name.upper()

    def test_float_parameter_markers_are_drawn_above_the_live_bar(self, rc_channel_bars: RCChannelBars) -> None:
        """
        Float-valued calibration parameters produce visible markers at their actual positions.

        GIVEN: A calibrated channel with float MIN/MAX/TRIM parameters
        WHEN: The status display is refreshed
        THEN: Three colored marker lines are drawn over the bar and ordered MIN < TRIM < MAX
        """
        rc_channel_bars.update_channels([{"name": "CH1", "value": 1500, "min": 982.0, "max": 2018.0, "trim": 1480.0}])
        canvas = rc_channel_bars._bar_canvases[1]
        markers = [canvas.find_withtag(f"{name}_marker")[0] for name in ("min", "trim", "max")]
        positions = [canvas.coords(marker)[0] for marker in markers]
        assert positions[0] < positions[1] < positions[2]
        assert all(
            canvas.find_all().index(marker) > canvas.find_all().index(canvas.find_withtag("live_value")[0])
            for marker in markers
        )

    def test_marker_labels_appear_only_above_the_first_channel(self, rc_channel_bars: RCChannelBars) -> None:
        """
        A single marker legend leaves the other fifteen channel rows compact.

        GIVEN: All sixteen channels have MIN/TRIM/MAX markers
        WHEN: The rows are drawn and then resized
        THEN: Only CH1 has colored text above its track while every row retains all three markers
        """
        for number, canvas in rc_channel_bars._bar_canvases.items():
            rc_channel_bars._draw_channel(number, width=450)
            track_top = canvas.coords(canvas.find_withtag("track")[0])[1]
            for name, color in (("min", "green"), ("trim", "blue"), ("max", "red")):
                marker = canvas.find_withtag(f"{name}_marker")
                assert len(marker) == 1
                assert canvas.itemcget(marker[0], "fill") == color
                label = canvas.find_withtag(f"{name}_label")
                if number == 1:
                    assert len(label) == 1
                    assert canvas.coords(label[0])[1] < track_top
                    assert canvas.itemcget(label[0], "fill") == color
                else:
                    assert not label


@pytest.fixture
def stick_preview(tk_root: tk.Tk) -> Generator[RCStickPreview, None, None]:
    """Create a real stick preview without forcing the physical event loop."""
    preview = RCStickPreview(tk_root)
    preview.pack()
    tk_root.update_idletasks()
    yield preview
    preview.destroy()


class TestRCStickPreview:
    """Check physical transmitter stick geometry, mode selection and retained telemetry."""

    @pytest.mark.parametrize("mode", [1, 2, 3, 4])
    def test_centered_sticks_show_two_centered_red_circles_one_twelfth_the_square_size(
        self, stick_preview: RCStickPreview, mode: int
    ) -> None:
        """
        Both stick circles are centered and correctly sized in every transmitter mode.

        GIVEN: Four centered axes and a selected transmitter Mode 1-4
        WHEN: The preview is updated
        THEN: Two side-by-side white squares have centered red circles with a 1/12 diameter ratio
        """
        stick_preview._mode.set(mode)
        stick_preview.update_axes({"roll": 0.0, "pitch": 0.0, "throttle": 0.0, "yaw": 0.0})

        assert len(stick_preview._canvases) == 2
        assert stick_preview.cget("text") == "Remote controller stick preview"
        for column, canvas in enumerate(stick_preview._canvases):
            square = canvas.coords(canvas.find_withtag("gimbal")[0])
            circle = canvas.coords(canvas.find_withtag("stick")[0])
            size = square[2] - square[0]
            assert square[3] - square[1] == size
            assert size == 126
            assert canvas.itemcget(canvas.find_withtag("gimbal")[0], "fill") == "white"
            assert canvas.itemcget(canvas.find_withtag("stick")[0], "fill") == "red"
            assert (circle[0] + circle[2]) / 2 == (square[0] + square[2]) / 2
            assert (circle[1] + circle[3]) / 2 == (square[1] + square[3]) / 2
            assert circle[2] - circle[0] == pytest.approx(size / 12)
            assert int(canvas.grid_info()["column"]) == column

    @pytest.mark.parametrize(
        ("mode", "left_axes", "right_axes"),
        [
            (1, ("yaw", "pitch"), ("roll", "throttle")),
            (2, ("yaw", "throttle"), ("roll", "pitch")),
            (3, ("roll", "pitch"), ("yaw", "throttle")),
            (4, ("roll", "throttle"), ("yaw", "pitch")),
        ],
    )
    def test_sticks_move_to_the_correct_corners_for_the_selected_mode(
        self, stick_preview: RCStickPreview, mode: int, left_axes: tuple[str, str], right_axes: tuple[str, str]
    ) -> None:
        """
        Stick mode selects the physical axes on each gimbal.

        GIVEN: Full right/up input on the selected physical stick axes
        WHEN: The user selects a transmitter mode
        THEN: Both circles reach the top-right corner without crossing the white square boundaries
        """
        stick_preview._mode.set(mode)
        sample = dict.fromkeys((*left_axes, *right_axes), 1000.0)
        sample["pitch"] = -1000.0  # Pushing forward commands negative pitch.
        stick_preview.update_axes(sample)

        for canvas in stick_preview._canvases:
            square = canvas.coords(canvas.find_withtag("gimbal")[0])
            circle = canvas.coords(canvas.find_withtag("stick")[0])
            assert circle[2] == pytest.approx(square[2])
            assert circle[1] == pytest.approx(square[1])

    def test_changing_mode_remaps_the_last_live_sample_immediately(self, stick_preview: RCStickPreview) -> None:
        """
        The selector remaps current sticks without waiting for another RC packet.

        GIVEN: Mode 2 with a raised throttle and centered other axes
        WHEN: The user selects Mode 1
        THEN: The raised throttle moves from the left gimbal to the right gimbal
        """
        stick_preview.update_axes({"roll": 0.0, "pitch": 0.0, "throttle": 1000.0, "yaw": 0.0})
        left, right = stick_preview._canvases
        before_left = left.coords(left.find_withtag("stick")[0])
        before_right = right.coords(right.find_withtag("stick")[0])
        stick_preview.mode_selector.set("1")
        stick_preview.mode_selector.event_generate("<<ComboboxSelected>>")
        assert left.coords(left.find_withtag("stick")[0]) == before_right
        assert right.coords(right.find_withtag("stick")[0]) == before_left

    def test_heartbeat_only_update_preserves_stick_positions(self, stick_preview: RCStickPreview) -> None:
        """
        Heartbeat packets do not falsely center the transmitter sticks.

        GIVEN: The monitor has displayed a displaced stick
        WHEN: Only a flight-mode update arrives
        THEN: The last stick positions are unchanged
        """
        stick_preview.update_axes({"yaw": 1000.0})
        canvas = stick_preview._canvases[0]
        before = canvas.coords(canvas.find_withtag("stick")[0])
        stick_preview.update_axes({"flight_mode": "3"})
        assert canvas.coords(canvas.find_withtag("stick")[0]) == before


def test_embedded_monitor_initialises_all_markers_and_preserves_channels_on_heartbeat(tk_root: tk.Tk) -> None:
    """
    The real embedded view displays configured markers immediately and keeps RC state on heartbeat-only polls.

    GIVEN: A connected backend and cached channel calibration
    WHEN: The view opens, receives RC telemetry, and then receives only a heartbeat
    THEN: Markers, sticks and live values are retained without displaying a flight-mode readout
    """
    controller = MagicMock()
    controller.fc_parameters = {"RC1_MIN": 990.0, "RC1_MAX": 2010.0, "RC1_TRIM": 1490.0}
    controller.master.recv_match.return_value = None
    parent = tk.Frame(tk_root)
    view = RCCalibrationView(parent, RCCalibrationDataModel(controller), MagicMock(spec=BaseWindow))
    try:
        assert len(view.stick_preview._canvases) == 2
        assert isinstance(view.craft_preview, RCCraftPreview)
        assert view.craft_preview.cget("text") == "Live monitor"
        canvas = view.channel_bars._bar_canvases[1]
        assert len(canvas.find_withtag("calibration_marker")) == 3
        message = MagicMock(chancount=4)
        for channel_number in range(1, 17):
            setattr(message, f"chan{channel_number}_raw", 1600 if channel_number == 1 else 1500)
        controller.master.recv_match.side_effect = [message, None]
        view._stop_polling()
        view._check_telemetry()
        before = view.channel_bars._value_labels[1].cget("text")
        heartbeat = MagicMock(custom_mode=3)
        controller.master.recv_match.side_effect = [None, heartbeat]
        view._stop_polling()
        view._check_telemetry()
        assert before == "1600 µs"
        assert view.channel_bars._value_labels[1].cget("text") == before
        assert len(canvas.find_withtag("calibration_marker")) == 3
        assert not any("Flight Mode:" in text for text in _label_texts(view))
        assert view.craft_preview._axes["roll"] != 0
        controller.set_param.assert_not_called()
    finally:
        view.destroy()
        parent.destroy()


def test_embedded_monitor_aligns_sections_with_documentation_and_moves_scrollbar_to_pane_edge(tk_root: tk.Tk) -> None:
    """
    The monitor uses the documentation margin rather than an oversized nested border.

    GIVEN: Documentation and an RC monitor in the same fixed-width editor area
    WHEN: Tk lays out the embedded monitor without running the event loop
    THEN: Sections share Documentation's outer margin with no extra inset and a scrollbar at the pane edge
    """
    controller = MagicMock()
    controller.fc_parameters = {}
    controller.master.recv_match.return_value = None
    host = ttk.Frame(tk_root)
    # Place assigns deterministic geometry even when the test root is withdrawn.
    host.place(x=0, y=0, width=700, height=500)
    documentation = ttk.LabelFrame(host, text="Documentation")
    documentation.pack(fill="x", padx=4, pady=2)
    parent = ttk.Frame(host)
    parent.pack(fill="both", expand=True)
    view = RCCalibrationView(parent, RCCalibrationDataModel(controller), MagicMock(spec=BaseWindow))
    view.pack(fill="both", expand=True)
    try:
        tk_root.update_idletasks()
        sections = (view.craft_preview, view.stick_preview, view.channel_bars)
        scrollbar = view._scroll_frame.vsb
        assert view._scroll_frame.canvas.coords(view._scroll_frame.canvas_window) == [0.0, 0.0]
        assert view._scroll_frame.winfo_x() == documentation.winfo_x() == 4
        assert view._scroll_frame.winfo_width() == documentation.winfo_width()
        assert view._scroll_frame.winfo_x() + scrollbar.winfo_x() + scrollbar.winfo_width() == view.winfo_width() - 4
        assert scrollbar.pack_info()["side"] == "right"
        assert view._scroll_frame.view_port.winfo_x() == 0
        assert view._scroll_frame.view_port.winfo_y() == 0
        for section in sections:
            assert section.pack_info()["padx"] == 0
            assert section.pack_info()["fill"] == "x"
            assert tuple(int(str(value)) for value in section.cget("padding")) == (4,)
            assert section.pack_info()["pady"] == (0, 4)
        assert not any("Flight Mode:" in text for text in _label_texts(view))
    finally:
        view.destroy()
        host.destroy()


def test_floating_monitor_shares_the_stick_boxes_and_three_channel_markers(tk_root: tk.Tk) -> None:
    """
    The floating live monitor presents the same markers and stick preview as the embedded view.

    GIVEN: A hidden test window and a model with channel calibration parameters
    WHEN: The popup is created using its real UI construction
    THEN: Compact sections show sticks and markers without a flight-mode readout, and polling is cancelled on destroy
    """
    controller = MagicMock()
    controller.fc_parameters = {"RC1_MIN": 990.0, "RC1_MAX": 2010.0, "RC1_TRIM": 1490.0}
    controller.master.recv_match.return_value = None
    root = tk.Toplevel(tk_root)
    root.withdraw()
    parent = tk.Toplevel(tk_root)
    parent.withdraw()

    def init_hidden_base(window: BaseWindow, _root_tk: tk.Toplevel) -> None:
        window.root = root
        window.main_frame = ttk.Frame(root)
        window.main_frame.pack(fill="both", expand=True)

    try:
        with (
            patch.object(BaseWindow, "__init__", init_hidden_base),
            patch.object(CalibrationPopupBase, "_resize_and_center"),
            patch.object(root, "lift"),
            patch.object(root, "focus_force"),
        ):
            popup = RCCalibrationPopup(cast("tk.Widget", parent), RCCalibrationDataModel(controller))
        assert len(popup.stick_preview._canvases) == 2
        assert isinstance(popup.craft_preview, RCCraftPreview)
        assert len(popup.channel_bars._bar_canvases) == 16
        assert all(len(canvas.find_withtag("calibration_marker")) == 3 for canvas in popup.channel_bars._bar_canvases.values())
        content_frame = cast("ttk.Frame", popup._scroll_frame.master)
        assert content_frame.pack_info()["padx"] == 4
        assert content_frame.pack_info()["pady"] == 4
        assert popup._scroll_frame.vsb.pack_info()["side"] == "right"
        assert popup._scroll_frame.canvas.coords(popup._scroll_frame.canvas_window) == [0.0, 0.0]
        for section in (popup.craft_preview, popup.stick_preview, popup.channel_bars):
            assert tuple(int(str(value)) for value in section.cget("padding")) == (4,)
            assert section.pack_info()["pady"] == (0, 4)
        message = MagicMock(chancount=4)
        for number in range(1, 17):
            setattr(message, f"chan{number}_raw", 1700 if number == 3 else 1500)
        controller.master.recv_match.side_effect = [message, None]
        popup._stop_polling()
        popup._check_telemetry()
        assert popup.channel_bars._value_labels[3].cget("text") == "1700 µs"
        controller.master.recv_match.side_effect = [None, MagicMock(custom_mode=5)]
        popup._stop_polling()
        popup._check_telemetry()
        assert popup.channel_bars._value_labels[3].cget("text") == "1700 µs"
        assert not any("Flight Mode:" in text for text in _label_texts(root))
        assert popup.craft_preview._axes["throttle"] == 0.4
        timer = popup._timer_id
        popup.destroy()
        assert popup._timer_id is None
        assert timer not in tk_root.tk.call("after", "info")
    finally:
        if root.winfo_exists():
            root.destroy()
        parent.destroy()


def test_cancel_calibration_restores_configured_markers_immediately(tk_root: tk.Tk) -> None:
    """
    Calibration controls update the markers immediately rather than leaving stale observed values.

    GIVEN: A real view, configured RC1 limits, and live observed extremes
    WHEN: The user starts calibration, moves the channel and then presses Cancel
    THEN: Observed MIN/MAX are discarded, configured MIN/MAX/TRIM return, and no parameters are written
    """
    controller = MagicMock()
    controller.fc_parameters = {"RC1_MIN": 1000.0, "RC1_MAX": 2000.0, "RC1_TRIM": 1490.0}
    controller.master.recv_match.return_value = None
    parent = tk.Frame(tk_root)
    view = RCCalibrationView(parent, RCCalibrationDataModel(controller), MagicMock(spec=BaseWindow))
    try:
        view._start_btn.invoke()
        assert str(view._cancel_btn.cget("state")) == "normal"
        message = MagicMock(chancount=1)
        for number in range(1, 17):
            setattr(message, f"chan{number}_raw", 1300)
        controller.master.recv_match.side_effect = [message, None]
        view._stop_polling()
        view._check_telemetry()
        assert view.channel_bars._channel_values[1]["min"] == 1300
        view._cancel_btn.invoke()
        assert view.channel_bars._channel_values[1] == {"value": 1300, "min": 1000, "max": 2000, "trim": 1490}
        assert str(view._start_btn.cget("state")) == "normal"
        assert str(view._finish_btn.cget("state")) == "disabled"
        controller.set_param.assert_not_called()
    finally:
        view.destroy()
        parent.destroy()


def test_mode_combobox_stages_mapping_and_refreshes_new_values_without_upload(
    tk_root: tk.Tk, rc_staging_context: tuple[MagicMock, ParameterEditor]
) -> None:
    """
    Mapping changes are visible edits, not silent FC writes.

    GIVEN: An embedded plugin using the real staged editor and a retained RC sample
    WHEN: The user selects Mode 1 and then Mode 4
    THEN: All four RCMAP New values and direction labels update, the table refreshes, and no upload occurs
    """
    controller, editor = rc_staging_context
    model = RCCalibrationDataModel(controller, editor)
    message = MagicMock(chancount=4)
    for number in range(1, 17):
        setattr(message, f"chan{number}_raw", 1800 if number == 3 else 1500)
    controller.master.recv_match.side_effect = [message, None]
    model.get_rc_telemetry()
    base_window = MagicMock()
    base_window.show_only_differences.get.return_value = False
    base_window.gui_complexity = "simple"
    parent = ttk.Frame(tk_root)
    view = RCCalibrationView(parent, model, base_window)
    try:
        assert view.stick_preview.mode_selector.get() == "2"
        assert [view.channel_bars._function_labels[number].cget("text") for number in range(1, 5)] == [
            "Roll",
            "Pitch",
            "Throttle",
            "Yaw",
        ]
        view.stick_preview.mode_selector.set("1")
        view.stick_preview.mode_selector.event_generate("<<ComboboxSelected>>")
        assert editor.current_step_parameters["RCMAP_THROTTLE"].get_new_value() == 2
        assert editor.current_step_parameters["RCMAP_PITCH"].get_new_value() == 3
        assert view.stick_preview._axis_labels[0].cget("text") == "YAW ↔ / PITCH ↕"
        assert view.stick_preview._axis_labels[1].cget("text") == "ROLL ↔ / THROTTLE ↕"
        assert [view.channel_bars._function_labels[number].cget("text") for number in range(1, 5)] == [
            "Roll",
            "Throttle",
            "Pitch",
            "Yaw",
        ]
        assert view.stick_preview._axes["pitch"] == 600
        assert view.stick_preview._axes["throttle"] == 0
        view.stick_preview.mode_selector.set("4")
        view.stick_preview.mode_selector.event_generate("<<ComboboxSelected>>")
        assert editor.current_step_parameters["RCMAP_ROLL"].get_new_value() == 4
        assert editor.current_step_parameters["RCMAP_YAW"].get_new_value() == 1
        assert view.stick_preview._axis_labels[0].cget("text") == "ROLL ↔ / THROTTLE ↕"
        base_window.parameter_editor_table.repopulate_table.assert_called_with(
            show_only_differences=False, gui_complexity="simple"
        )
        assert "upload" in view.stick_preview._mapping_status.cget("text")
        controller.set_param.assert_not_called()
        assert controller.fc_parameters["RCMAP_THROTTLE"] == 3
    finally:
        view.destroy()
        parent.destroy()


def test_finish_button_only_stages_calibration_until_parameter_upload(
    tk_root: tk.Tk, rc_staging_context: tuple[MagicMock, ParameterEditor]
) -> None:
    """
    Finish Calibration stages measurements rather than writing the controller.

    GIVEN: A real embedded view tracking valid extrema
    WHEN: The user presses Finish Calibration
    THEN: New values and markers show the measurements, status requests upload, and no PARAM_SET is sent
    """
    controller, editor = rc_staging_context
    model = RCCalibrationDataModel(controller, editor)
    parent = ttk.Frame(tk_root)
    view = RCCalibrationView(parent, model, MagicMock())
    try:
        view._start_btn.invoke()
        model._channel_min = {0: 1100}
        model._channel_max = {0: 1900}
        view._finish_btn.invoke()
        assert editor.current_step_parameters["RC1_MIN"].get_new_value() == 1100
        assert view.channel_bars._channel_values[1]["min"] == 1100
        assert "upload" in view._status_label.cget("text")
        assert str(view._finish_btn.cget("state")) == "disabled"
        controller.set_param.assert_not_called()
    finally:
        view.destroy()
        parent.destroy()


def test_custom_mapping_and_failed_mode_change_do_not_silently_replace_parameters(
    tk_root: tk.Tk, rc_staging_context: tuple[MagicMock, ParameterEditor]
) -> None:
    """
    A custom or protected channel map is retained until a complete valid edit is possible.

    GIVEN: A custom mapping and a read-only RCMAP parameter
    WHEN: The user selects a preset
    THEN: The selector remains Custom, an error is shown, and no controller write occurs
    """
    controller, editor = rc_staging_context
    parameter = editor.current_step_parameters["RCMAP_ROLL"]
    parameter.set_new_value("5")
    parameter._metadata["ReadOnly"] = True
    preview = RCStickPreview(tk_root, RCCalibrationDataModel(controller, editor))
    try:
        assert preview.mode_selector.get() == "Custom"
        preview.mode_selector.set("1")
        preview.mode_selector.event_generate("<<ComboboxSelected>>")
        assert preview.mode_selector.get() == "Custom"
        assert str(preview._mapping_status.cget("foreground")) == "red"
        assert parameter.get_new_value() == 5
        controller.set_param.assert_not_called()
    finally:
        preview.destroy()


def test_all_stick_modes_show_roll_and_pitch_direction_arrows(stick_preview: RCStickPreview) -> None:
    """
    Every mode labels both horizontal and vertical axes with their direction symbols.

    GIVEN: The two-gimbal stick preview
    WHEN: Each mode is drawn
    THEN: ROLL and YAW have horizontal arrows, PITCH and THROTTLE have vertical arrows
    """
    for mode in range(1, 5):
        stick_preview._mode.set(mode)
        stick_preview.update_axes({})
        labels = " ".join(label.cget("text") for label in stick_preview._axis_labels)
        for text in ("ROLL ↔", "YAW ↔", "PITCH ↕", "THROTTLE ↕"):
            assert text in labels


def test_craft_preview_yaw_turns_while_held_and_holds_when_centered_or_stale(
    tk_root: tk.Tk, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    The example craft behaves like the reference receiver monitor rather than real attitude telemetry.

    GIVEN: A clock-controlled craft preview and valid RC channel data
    WHEN: Yaw is held, centered, then telemetry stops
    THEN: Heading advances at the visual yaw rate, holds at center, and stops after a stale-input timeout
    """
    clock = [10.0]
    monkeypatch.setattr("ardupilot_methodic_configurator.plugins.frontend_tkinter_rc_calibration.monotonic", lambda: clock[0])
    preview = RCCraftPreview(tk_root)
    channels = [{"value": 1500}] * 4
    try:
        preview.update_telemetry({"yaw": 1000, "roll": 500, "pitch": -500, "throttle": 1000, "channels": channels})
        assert preview._heading == 0
        clock[0] += 0.1
        preview.update_telemetry({"flight_mode": "3"})
        assert preview._heading == pytest.approx(12)
        assert preview._axes == {"roll": 0.5, "pitch": -0.5, "yaw": 1.0, "throttle": 1.0}
        assert preview.status_label.cget("text") == "4 channels live"
        clock[0] += 0.1
        preview.update_telemetry({"yaw": 0, "channels": channels})
        heading = preview._heading
        clock[0] += 0.1
        preview.update_telemetry({"yaw": 30, "channels": channels})  # Within the visual yaw deadband.
        assert preview._heading == heading
        preview.update_telemetry({"yaw": 1000, "channels": channels})
        clock[0] += 1
        preview.update_telemetry({})
        assert preview._heading == heading
        assert preview.status_label.cget("text") == "No RC telemetry"
    finally:
        preview.destroy()


def test_craft_preview_is_rendered_before_telemetry_without_inventing_live_status(tk_root: tk.Tk) -> None:
    """
    The replacement for Preview Stages is visible even before the first RC sample.

    GIVEN: A newly opened live monitor
    WHEN: No RC telemetry has arrived
    THEN: It shows a neutral example craft with no live status and safely ignores nonfinite axis samples
    """
    preview = RCCraftPreview(tk_root)
    try:
        assert preview.image_label.cget("image")
        assert preview.status_label.cget("text") == "No RC telemetry"
        preview.update_telemetry({"roll": float("nan"), "channels": [{"value": None}]})
        assert preview._axes["roll"] == 0
        assert preview.status_label.cget("text") == "No RC telemetry"
    finally:
        preview.destroy()
