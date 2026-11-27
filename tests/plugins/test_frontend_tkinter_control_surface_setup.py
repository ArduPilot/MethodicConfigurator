#!/usr/bin/env python3

"""
Behavior-driven tests for the control surface setup Tkinter plugin.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2026 Allister779

SPDX-License-Identifier: GPL-3.0-or-later
"""

import tkinter as tk
from collections.abc import Generator
from tkinter import ttk
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from ardupilot_methodic_configurator.plugins.data_model_control_surface_setup import (
    ControlSurfaceSetupDataModel,
    ControlSurfaceSetupError,
    EndpointKind,
    PlaneMode,
    SaveResult,
    ServoChannel,
    StickAxis,
)
from ardupilot_methodic_configurator.plugins.frontend_tkinter_control_surface_setup import (
    ControlSurfaceSetupView,
    register_control_surface_setup_plugin,
)
from ardupilot_methodic_configurator.plugins.plugin_constants import PLUGIN_CONTROL_SURFACE_SETUP
from ardupilot_methodic_configurator.plugins.plugin_factory import PluginModelContext, plugin_factory
from ardupilot_methodic_configurator.plugins.plugin_protocol import PluginPauseReason

# pylint: disable=redefined-outer-name,protected-access

MODULE = "ardupilot_methodic_configurator.plugins.frontend_tkinter_control_surface_setup"
AILERON = ServoChannel(1, 4, "Aileron")
TILT = ServoChannel(6, 75, "Tilt Motor Front Left")


def _model(*, tilt_rotor: bool = False) -> MagicMock:
    model = MagicMock(spec=ControlSurfaceSetupDataModel)
    model.control_surface_channels.return_value = [AILERON]
    model.tilt_servo_channels.return_value = [TILT] if tilt_rotor else []
    model.is_tilt_rotor.return_value = tilt_rotor
    model.tilt_setup_problem.return_value = ""
    model.tilt_type.return_value = 0
    model.tilt_type_options.return_value = {0: "Continuous"}
    model.tilt_setting_value.return_value = 0
    model.tilt_endpoints.return_value = (EndpointKind.MAX, EndpointKind.MIN)
    model.is_servo_reversed.return_value = False
    model.is_rc_reversed.return_value = False
    model.rc_channel.side_effect = lambda axis: {StickAxis.ROLL: 1, StickAxis.PITCH: 2, StickAxis.YAW: 4}[axis]
    model.servo_endpoint.return_value = 1500
    model.trim_needs_mechanical_adjustment.side_effect = lambda trim: abs(trim - 1500) > 50
    model.rudder_mix_warning.return_value = ""
    model.battery_voltage_status.return_value = (True, "Battery voltage 12.40V")
    model.current_mode_name.return_value = "FBWA"
    model.servo_pwm.return_value = 1510
    model.pending_reboot_parameters.return_value = []
    model.save_parameters.return_value = SaveResult(staged=["SERVO1_REVERSED"])
    return model


@pytest.fixture
def view_env(tk_root, mocker) -> Generator[SimpleNamespace, None, None]:
    """A real view with a mocked model and isolated dialogs."""
    dialogs = SimpleNamespace(
        showerror=mocker.patch(f"{MODULE}.showerror"),
        showinfo=mocker.patch(f"{MODULE}.showinfo"),
        showwarning=mocker.patch(f"{MODULE}.showwarning"),
    )
    parent = ttk.Frame(tk_root)
    model = _model(tilt_rotor=True)
    base_window = SimpleNamespace(root=tk_root, parameter_editor_table=MagicMock(), gui_complexity="simple")
    view = ControlSurfaceSetupView(parent, model, base_window)  # type: ignore[arg-type]
    try:
        yield SimpleNamespace(view=view, model=model, dialogs=dialogs, base_window=base_window)
    finally:
        view.destroy()
        parent.destroy()


class TestLayout:
    """The user sees one tab per setup stage."""

    def test_tilt_rotor_gets_a_fourth_tab(self, view_env: SimpleNamespace) -> None:
        """GIVEN Q_TILT_ENABLE=1 WHEN the view opens THEN four tabs are shown."""
        assert len(view_env.view.notebook.tabs()) == 4

    def test_plain_plane_has_three_tabs(self, tk_root, mocker) -> None:
        """GIVEN a plane without tilt rotors WHEN the view opens THEN the tilt tab is omitted."""
        mocker.patch(f"{MODULE}.showerror")
        parent = ttk.Frame(tk_root)
        view = ControlSurfaceSetupView(parent, _model(), SimpleNamespace(root=tk_root))  # type: ignore[arg-type]
        try:
            assert len(view.notebook.tabs()) == 3
        finally:
            view.destroy()
            parent.destroy()

    def test_stick_tab_offers_fbwa_and_manual(self, view_env: SimpleNamespace) -> None:
        """GIVEN the stick direction tab WHEN shown THEN FBWA and MANUAL buttons sit side by side."""
        tab = view_env.view.nametowidget(view_env.view.notebook.tabs()[1])
        labels = []

        def collect(widget: object) -> None:
            for child in widget.winfo_children():  # type: ignore[attr-defined]
                if isinstance(child, ttk.Button):
                    labels.append(child.cget("text"))
                collect(child)

        collect(tab)
        assert labels[:2] == ["Switch to FBWA", "Switch to MANUAL"]

    def test_trim_tab_has_no_simulated_sticks(self, view_env: SimpleNamespace) -> None:
        """GIVEN the trim and travel tab WHEN shown THEN it has no slider widgets."""
        tab = view_env.view.nametowidget(view_env.view.notebook.tabs()[2])
        scales = []

        def collect(widget: object) -> None:
            for child in widget.winfo_children():  # type: ignore[attr-defined]
                if isinstance(child, tk.Scale):
                    scales.append(child)
                collect(child)

        collect(tab)
        assert not scales

    def test_live_pwm_is_displayed(self, view_env: SimpleNamespace) -> None:
        """GIVEN telemetry WHEN the timer runs THEN the PWM labels show the output."""
        view_env.view._on_telemetry_timer()
        assert any(label.cget("text") == "1510 µs" for _channel, label in view_env.view._pwm_labels)


class TestActions:
    """Controls write live and report failures."""

    def test_mode_switch_requires_battery_power(self, view_env: SimpleNamespace) -> None:
        """GIVEN low battery WHEN switching to FBWA THEN the mode is not changed and the user is told why."""
        view_env.model.battery_voltage_status.return_value = (False, "too low")
        view_env.view._switch_mode(PlaneMode.FBWA)
        view_env.model.set_flight_mode.assert_not_called()
        view_env.dialogs.showerror.assert_called_once()

    def test_mode_switch_commands_the_model(self, view_env: SimpleNamespace) -> None:
        """GIVEN battery power WHEN switching to MANUAL THEN the model switches mode."""
        view_env.view._switch_mode(PlaneMode.MANUAL)
        view_env.model.set_flight_mode.assert_called_once_with(PlaneMode.MANUAL)

    def test_invalid_endpoint_shows_error_and_resyncs(self, view_env: SimpleNamespace) -> None:
        """GIVEN the model rejects a value WHEN editing THEN an error is shown."""
        view_env.model.set_servo_endpoint.side_effect = ControlSurfaceSetupError("bad")
        view_env.view._on_endpoint(AILERON, EndpointKind.TRIM, 1000)
        view_env.dialogs.showerror.assert_called_once()

    def test_fractional_pwm_is_rejected(self, view_env: SimpleNamespace) -> None:
        """GIVEN a fractional value WHEN editing THEN nothing is written."""
        view_env.view._on_endpoint(AILERON, EndpointKind.TRIM, 1500.5)
        view_env.model.set_servo_endpoint.assert_not_called()

    def test_trim_warning_appears_beyond_50_us(self, view_env: SimpleNamespace) -> None:
        """GIVEN TRIM=1600 WHEN updated THEN a mechanical adjustment warning is shown."""
        view_env.model.servo_endpoint.return_value = 1600
        view_env.view._update_trim_warning(AILERON)
        assert "50" in view_env.view._trim_warnings[1].cget("text")

    def test_save_refreshes_parameter_table(self, view_env: SimpleNamespace) -> None:
        """GIVEN a successful save THEN the user is informed and the table refreshes."""
        view_env.view._save(["SERVO1_REVERSED"], "reason")
        view_env.dialogs.showinfo.assert_called_once()
        view_env.base_window.parameter_editor_table.repopulate_table.assert_called_once()

    def test_reboot_is_requested_when_needed(self, view_env: SimpleNamespace) -> None:
        """GIVEN a reboot-required parameter WHEN saving THEN a reboot warning is shown."""
        view_env.model.pending_reboot_parameters.return_value = ["Q_TILT_TYPE"]
        view_env.view._save(["Q_TILT_TYPE"], "reason")
        assert any("Q_TILT_TYPE" in str(c.args) for c in view_env.dialogs.showwarning.call_args_list)


class TestLifecycle:
    """Leaving the step stops timers and undoes temporary state."""

    def test_deactivate_shuts_model_down_and_cancels_timers(self, view_env: SimpleNamespace) -> None:
        """GIVEN an active view WHEN deactivated THEN timers stop and overrides and mode are restored."""
        view_env.view.on_deactivate()
        view_env.model.shutdown.assert_called_once()
        assert view_env.view._telemetry_timer is None
        assert view_env.view._battery_timer is None

    @pytest.mark.parametrize("reason", list(PluginPauseReason))
    def test_suspend_stops_polling_without_commands_and_resume_restarts(
        self, view_env: SimpleNamespace, reason: PluginPauseReason
    ) -> None:
        """GIVEN an active view WHEN suspended for any reason THEN polling stops, nothing is sent, and resume restarts it."""
        view_env.view.on_suspend(reason)
        assert view_env.view._telemetry_timer is None
        view_env.model.set_flight_mode.assert_not_called()
        view_env.model.shutdown.assert_not_called()
        view_env.view.on_resume()
        assert view_env.view._telemetry_timer is not None


class TestRegistration:  # pylint: disable=too-few-public-methods
    """The plugin registers with the factory and requires an FC."""

    def test_plugin_registers_with_model_factory(self) -> None:
        """GIVEN registration WHEN queried THEN the plugin exists and requires a flight controller."""
        register_control_surface_setup_plugin()
        assert plugin_factory.is_registered(PLUGIN_CONTROL_SURFACE_SETUP)
        assert plugin_factory.requires_flight_controller(PLUGIN_CONTROL_SURFACE_SETUP)
        context = PluginModelContext(
            flight_controller=MagicMock(fc_parameters={}),
            local_filesystem=MagicMock(),
            parameter_editor=MagicMock(),
        )
        assert isinstance(plugin_factory.create_model(PLUGIN_CONTROL_SURFACE_SETUP, context), ControlSurfaceSetupDataModel)
