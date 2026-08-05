#!/usr/bin/env python3

"""
Tests for log analysis Tkinter view helpers.

SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

from unittest.mock import MagicMock, patch

from ardupilot_methodic_configurator.frontend_tkinter_log_hardware_quality import build_hardware_tab
from ardupilot_methodic_configurator.frontend_tkinter_log_quality import LogQualityReportWindow
from ardupilot_methodic_configurator.log_analysis.data_model_vehicle_overview import HardwareReport, VehicleInfo


def test_hardware_tab_shows_empty_state_when_report_has_no_sensors() -> None:
    """A hardware report with no sensor entries should still show explicit user feedback."""
    parent = MagicMock()
    inner = MagicMock()
    scroll_frame = MagicMock(view_port=inner)
    label = MagicMock()
    hw = HardwareReport(
        vehicle=VehicleInfo(
            vehicle_type="ArduCopter",
            major=4,
            minor=5,
            patch=5,
            firmware_hash=None,
            board_id=None,
            flight_controller=None,
            oper_sys=None,
        ),
        board_name=None,
        imus=[],
        compasses=[],
        baros=[],
        airspeed_sensors=[],
    )

    with (
        patch("ardupilot_methodic_configurator.frontend_tkinter_log_hardware_quality.ScrollFrame", return_value=scroll_frame),
        patch(
            "ardupilot_methodic_configurator.frontend_tkinter_log_hardware_quality.ttk.Label",
            return_value=label,
        ) as mock_label,
    ):
        build_hardware_tab(parent, hw)

    mock_label.assert_called_once_with(inner, text="No hardware data available", foreground="gray")
    label.pack.assert_called_once_with(padx=24, pady=24)


def test_release_link_opens_with_backend_internet_browser_helper() -> None:
    """Clickable report links should reuse the application's browser helper."""
    report_window = LogQualityReportWindow.__new__(LogQualityReportWindow)
    report_window.default_font_size = 11
    parent = MagicMock()
    row = MagicMock()
    key_label = MagicMock()
    link_label = MagicMock()

    with (
        patch("ardupilot_methodic_configurator.frontend_tkinter_log_quality.ttk.Frame", return_value=row),
        patch(
            "ardupilot_methodic_configurator.frontend_tkinter_log_quality.ttk.Label",
            side_effect=[key_label, link_label],
        ),
        patch("ardupilot_methodic_configurator.frontend_tkinter_log_quality.show_tooltip"),
        patch("ardupilot_methodic_configurator.frontend_tkinter_log_quality.webbrowser_open_url") as mock_open,
    ):
        report_window._add_clickable_key_value(parent, "Firmware:", "Copter-4.5.5", "https://example.test/release")  # pylint: disable=protected-access

        callback = link_label.bind.call_args.args[1]
        callback(None)

    mock_open.assert_called_once_with("https://example.test/release")
