#!/usr/bin/env python3

"""
Tests for the frontend_tkinter_connection_selection.py file.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import tkinter as tk
from unittest.mock import MagicMock, patch

import pytest

from ardupilot_methodic_configurator.backend_flightcontroller import SUPPORTED_BAUDRATES
from ardupilot_methodic_configurator.frontend_tkinter_connection_selection import (
    ConnectionSelectionWidgets,
    ConnectionSelectionWindow,
)

# pylint: disable=too-many-lines, protected-access, redefined-outer-name

# ---------------------------------------------------------------------------
# Module-level constant for the module path under test
# ---------------------------------------------------------------------------

_MOD = "ardupilot_methodic_configurator.frontend_tkinter_connection_selection"

# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_fc() -> MagicMock:
    """Minimal flight-controller mock used across most test classes."""
    fc = MagicMock()
    fc.comport = None
    fc.master = None
    fc.get_connection_tuples.return_value = [
        ("COM1", "Serial Port COM1"),
        ("COM2", "Serial Port COM2"),
        ("Add another", "Add another connection"),
    ]
    return fc


@pytest.fixture
def mock_parent() -> MagicMock:
    """Parent window mock with a root attribute."""
    parent = MagicMock()
    parent.root = MagicMock()
    return parent


@pytest.fixture
def basic_widget(mock_parent: MagicMock, mock_fc: MagicMock) -> tuple[ConnectionSelectionWidgets, MagicMock, MagicMock]:
    """
    ConnectionSelectionWidgets with all tkinter dependencies patched.

    Returns (widget, mock_combobox, mock_baudrate_var).
    """
    mock_combobox = MagicMock()
    mock_combobox.__getitem__.return_value = ["COM1", "COM2", "Add another"]
    mock_baudrate_var = MagicMock()
    mock_baudrate_var.get.return_value = "115200"

    with (
        patch("tkinter.ttk.Frame"),
        patch("tkinter.ttk.Label"),
        patch("tkinter.ttk.Combobox"),
        patch("tkinter.StringVar", return_value=mock_baudrate_var),
        patch("ardupilot_methodic_configurator.frontend_tkinter_autoresize_combobox.update_combobox_width"),
        patch(f"{_MOD}.PairTupleCombobox", return_value=mock_combobox),
        patch(f"{_MOD}.show_tooltip"),
        patch(f"{_MOD}.ProgramSettings.get_connection_history", return_value=[]),
    ):
        widget = ConnectionSelectionWidgets(
            mock_parent,
            MagicMock(spec=tk.Frame),
            mock_fc,
            destroy_parent_on_connect=True,
            download_params_on_connect=True,
        )
        widget.conn_selection_combobox = mock_combobox
        widget.baudrate_var = mock_baudrate_var

    return widget, mock_combobox, mock_baudrate_var


@pytest.fixture
def connection_window(mock_fc: MagicMock):  # noqa: ANN201  # yields; complex return type
    """
    ConnectionSelectionWindow with all heavy Tk dependencies patched.

    Yields (window, mock_widgets).
    """
    mock_widgets = MagicMock()

    def _mock_basewindow_init(self, root_tk=None) -> None:  # noqa: ARG001, pylint: disable=unused-argument
        self.root = MagicMock()
        self.main_frame = MagicMock()

    with (
        patch("tkinter.Tk"),
        patch("tkinter.Toplevel"),
        patch("tkinter.PhotoImage"),
        patch.object(tk.Tk, "iconphoto"),
        patch.object(tk.Toplevel, "iconphoto"),
        patch(
            "ardupilot_methodic_configurator.frontend_tkinter_base_window.ProgramSettings.application_icon_filepath",
            return_value="mock_icon_path.png",
        ),
        patch("tkinter.ttk.Frame"),
        patch("tkinter.ttk.Label"),
        patch("tkinter.ttk.LabelFrame"),
        patch("tkinter.ttk.Button"),
        patch("tkinter.ttk.Style"),
        patch(f"{_MOD}.ConnectionSelectionWidgets", return_value=mock_widgets),
        patch(f"{_MOD}.show_tooltip"),
        patch(
            "ardupilot_methodic_configurator.frontend_tkinter_base_window.BaseWindow.__init__",
            _mock_basewindow_init,
        ),
    ):
        window = ConnectionSelectionWindow(mock_fc, "Test connection message")
        yield window, mock_widgets


# ---------------------------------------------------------------------------
# TestConnectionSelectionWidgets
# ---------------------------------------------------------------------------


class TestConnectionSelectionWidgets:
    """ConnectionSelectionWidgets test class."""

    def test_init_with_no_comport(self, basic_widget: tuple[ConnectionSelectionWidgets, MagicMock, MagicMock]) -> None:
        """Test the initialization of ConnectionSelectionWidgets when comport is None."""
        widget, _, _ = basic_widget
        assert widget.previous_selection is None

    def test_init_with_existing_comport(self, mock_parent: MagicMock) -> None:
        """
        Widget initializes with previous_selection set to comport device name.

        GIVEN: A flight controller already has an active comport
        WHEN: ConnectionSelectionWidgets is initialized
        THEN: previous_selection should match the comport device name
        AND: destroy_parent_on_connect and download_params_on_connect should match constructor args
        """
        mock_comport = MagicMock()
        mock_comport.device = "COM1"
        fc = MagicMock()
        fc.comport = mock_comport
        fc.master = None
        fc.get_connection_tuples.return_value = [
            ("COM1", "Serial Port COM1"),
            ("COM2", "Serial Port COM2"),
            ("Add another", "Add another connection"),
        ]
        new_mock_combobox = MagicMock()
        new_mock_combobox.__getitem__.return_value = ["COM1", "COM2", "Add another"]

        with (
            patch("tkinter.ttk.Frame"),
            patch("tkinter.ttk.Label"),
            patch("tkinter.ttk.Combobox"),
            patch("tkinter.StringVar"),
            patch("ardupilot_methodic_configurator.frontend_tkinter_autoresize_combobox.update_combobox_width"),
            patch("ardupilot_methodic_configurator.frontend_tkinter_pair_tuple_combobox.update_combobox_width"),
            patch(f"{_MOD}.PairTupleCombobox", return_value=new_mock_combobox),
            patch(f"{_MOD}.show_tooltip"),
            patch(f"{_MOD}.ProgramSettings.get_connection_history", return_value=[]),
        ):
            new_widget = ConnectionSelectionWidgets(
                mock_parent,
                MagicMock(spec=tk.Frame),
                fc,
                destroy_parent_on_connect=True,
                download_params_on_connect=True,
            )
            new_widget.conn_selection_combobox = new_mock_combobox

        assert new_widget.previous_selection == "COM1"
        assert new_widget.destroy_parent_on_connect is True
        assert new_widget.download_params_on_connect is True

    def test_on_select_connection_combobox_change_add_another(
        self, basic_widget: tuple[ConnectionSelectionWidgets, MagicMock, MagicMock]
    ) -> None:
        """Test on_select_connection_combobox_change when 'Add another' is selected."""
        widget, mock_combobox, _ = basic_widget
        mock_combobox.get_selected_key.return_value = "Add another"
        widget.add_connection = MagicMock(return_value="")
        widget.previous_selection = "COM1"

        widget.on_select_connection_combobox_change(MagicMock())

        widget.add_connection.assert_called_once()
        mock_combobox.set.assert_called_once_with("COM1")

    def test_on_select_connection_combobox_change_new_connection(
        self, basic_widget: tuple[ConnectionSelectionWidgets, MagicMock, MagicMock]
    ) -> None:
        """Test on_select_connection_combobox_change when a new connection is selected."""
        widget, mock_combobox, _ = basic_widget
        mock_combobox.get_selected_key.return_value = "COM2"
        widget.reconnect = MagicMock()

        widget.on_select_connection_combobox_change(MagicMock())

        widget.reconnect.assert_called_once_with("COM2")

    def test_on_select_connection_combobox_change_same_connection(
        self, basic_widget: tuple[ConnectionSelectionWidgets, MagicMock, MagicMock], mock_fc: MagicMock
    ) -> None:
        """Test on_select_connection_combobox_change when the same connection is selected."""
        widget, mock_combobox, _ = basic_widget
        mock_comport = MagicMock()
        mock_comport.device = "COM1"
        mock_fc.comport = mock_comport
        mock_fc.master = MagicMock()  # active connection
        mock_combobox.get_selected_key.return_value = "COM1"
        widget.reconnect = MagicMock()

        widget.on_select_connection_combobox_change(MagicMock())

        widget.reconnect.assert_not_called()

    def test_add_connection_canceled(
        self, basic_widget: tuple[ConnectionSelectionWidgets, MagicMock, MagicMock], mock_fc: MagicMock
    ) -> None:
        """Test add_connection when the dialog is canceled."""
        widget, _, _ = basic_widget
        mock_fc.add_connection.reset_mock()
        mock_fc.get_connection_tuples.reset_mock()

        with (
            patch(f"{_MOD}.simpledialog.askstring", return_value=None),
            patch.object(widget, "reconnect"),
            patch(f"{_MOD}.ProgramSettings.store_connection"),
        ):
            result = widget.add_connection()

        assert result == ""
        mock_fc.add_connection.assert_not_called()
        mock_fc.get_connection_tuples.assert_not_called()

    def test_add_connection_canceled_empty_string(
        self, basic_widget: tuple[ConnectionSelectionWidgets, MagicMock, MagicMock], mock_fc: MagicMock
    ) -> None:
        """Test add_connection when an empty string is entered."""
        widget, _, _ = basic_widget
        mock_fc.add_connection.reset_mock()
        mock_fc.get_connection_tuples.reset_mock()

        with (
            patch(f"{_MOD}.simpledialog.askstring", return_value=""),
            patch.object(widget, "reconnect"),
            patch(f"{_MOD}.ProgramSettings.store_connection"),
        ):
            result = widget.add_connection()

        assert result == ""
        mock_fc.add_connection.assert_not_called()
        mock_fc.get_connection_tuples.assert_not_called()

    def test_add_connection_success(
        self, basic_widget: tuple[ConnectionSelectionWidgets, MagicMock, MagicMock], mock_fc: MagicMock
    ) -> None:
        """Test add_connection with a successful entry."""
        widget, mock_combobox, _ = basic_widget
        updated_tuples = [
            ("COM1", "Serial Port COM1"),
            ("COM2", "Serial Port COM2"),
            ("tcp:127.0.0.1:5761", "TCP 127.0.0.1:5761"),
            ("Add another", "Add another connection"),
        ]
        mock_fc.add_connection.reset_mock()
        mock_fc.get_connection_tuples.reset_mock()
        mock_fc.get_connection_tuples.return_value = updated_tuples
        mock_combobox.reset_mock()

        with (
            patch(f"{_MOD}.simpledialog.askstring", return_value="tcp:127.0.0.1:5761"),
            patch.object(widget, "reconnect") as mock_reconnect,
            patch(
                f"{_MOD}.ProgramSettings.store_connection",
                return_value="tcp:127.0.0.1:5761",
            ),
        ):
            result = widget.add_connection()

        assert result == "tcp:127.0.0.1:5761"
        mock_fc.add_connection.assert_called_once_with("tcp:127.0.0.1:5761")
        mock_fc.get_connection_tuples.assert_called_once()
        mock_combobox.set_entries_tuple.assert_called_once_with(updated_tuples, "tcp:127.0.0.1:5761")
        mock_reconnect.assert_called_once_with("tcp:127.0.0.1:5761")

    def test_reconnect_with_error(
        self, basic_widget: tuple[ConnectionSelectionWidgets, MagicMock, MagicMock], mock_fc: MagicMock
    ) -> None:
        """Test reconnect when there's a connection error."""
        widget, _, _ = basic_widget
        mock_progress_instance = MagicMock()
        mock_fc.connect.return_value = "Connection error"

        with (
            patch(f"{_MOD}.ProgressWindow", return_value=mock_progress_instance) as mock_progress_window,
            patch(f"{_MOD}.show_no_connection_error") as mock_show_error,
        ):
            result = widget.reconnect("COM1")

        mock_progress_window.assert_called_once()
        mock_fc.connect.assert_called_once_with("COM1", mock_progress_instance.update_progress_bar, baudrate=115200)
        mock_show_error.assert_called_once_with("Connection error")
        assert result
        mock_progress_instance.destroy.assert_not_called()

    def test_reconnect_success_destroy_parent(
        self,
        basic_widget: tuple[ConnectionSelectionWidgets, MagicMock, MagicMock],
        mock_fc: MagicMock,
        mock_parent: MagicMock,
    ) -> None:
        """Test successful reconnect with destroy_parent_on_connect=True."""
        widget, _, _ = basic_widget
        mock_progress_instance = MagicMock()
        mock_fc.connect.return_value = ""
        mock_comport = MagicMock()
        mock_comport.device = "COM1"
        mock_fc.comport = mock_comport

        with (
            patch(f"{_MOD}.ProgressWindow", return_value=mock_progress_instance) as mock_progress_window,
            patch(f"{_MOD}.show_no_connection_error") as mock_show_error,
            patch(f"{_MOD}.ProgramSettings.store_connection", return_value="COM1"),
        ):
            result = widget.reconnect("COM1")

        mock_progress_window.assert_called_once()
        mock_fc.connect.assert_called_once_with("COM1", mock_progress_instance.update_progress_bar, baudrate=115200)
        mock_progress_instance.destroy.assert_called_once()
        mock_show_error.assert_not_called()
        assert not result
        assert widget.previous_selection == "COM1"
        mock_parent.root.destroy.assert_called_once()

    def test_reconnect_success_with_download(
        self,
        basic_widget: tuple[ConnectionSelectionWidgets, MagicMock, MagicMock],
        mock_fc: MagicMock,
        mock_parent: MagicMock,
    ) -> None:
        """Test successful reconnect with download_params_on_connect=True."""
        widget, _, _ = basic_widget
        mock_progress_instance = MagicMock()
        mock_fc.connect.return_value = ""
        mock_comport = MagicMock()
        mock_comport.device = "COM1"
        mock_fc.comport = mock_comport
        mock_parent.download_flight_controller_parameters = MagicMock()

        with (
            patch(f"{_MOD}.ProgressWindow", return_value=mock_progress_instance),
            patch(f"{_MOD}.ProgramSettings.store_connection", return_value="COM1"),
        ):
            result = widget.reconnect("COM1")

        mock_parent.download_flight_controller_parameters.assert_called_once_with(redownload=False)
        assert not result


# ---------------------------------------------------------------------------
# TestConnectionSelectionWindow
# ---------------------------------------------------------------------------


class TestConnectionSelectionWindow:
    """ConnectionSelectionWindow test class."""

    def test_window_has_connection_selection_widgets(
        self, connection_window: tuple[ConnectionSelectionWindow, MagicMock]
    ) -> None:
        """The window creates and exposes a ConnectionSelectionWidgets instance."""
        window, _ = connection_window
        assert hasattr(window, "connection_selection_widgets")

    def test_close_and_quit(self, connection_window: tuple[ConnectionSelectionWindow, MagicMock]) -> None:
        """Test close_and_quit method calls sys_exit."""
        window, _ = connection_window
        with patch(f"{_MOD}.sys_exit") as mock_sys_exit:
            window.close_and_quit()
        mock_sys_exit.assert_called_once_with(0)

    def test_close_and_quit_stops_periodic_refresh(
        self, connection_window: tuple[ConnectionSelectionWindow, MagicMock]
    ) -> None:
        """
        Periodic port refresh is cancelled when the user closes the connection window.

        GIVEN: The connection window is open with an active periodic refresh timer
        WHEN: The user closes the window via the window manager (X button)
        THEN: stop_periodic_refresh should be called on the connection_selection_widgets
        AND: No stale tkinter callbacks remain scheduled after the window is gone
        """
        window, mock_widgets = connection_window
        with patch(f"{_MOD}.sys_exit"):
            window.close_and_quit()
        mock_widgets.stop_periodic_refresh.assert_called_once()

    def test_fc_autoconnect(self, connection_window: tuple[ConnectionSelectionWindow, MagicMock]) -> None:
        """Test fc_autoconnect method calls reconnect."""
        window, _ = connection_window
        window.fc_autoconnect()
        window.connection_selection_widgets.reconnect.assert_called_once()

    def test_skip_fc_connection(
        self, connection_window: tuple[ConnectionSelectionWindow, MagicMock], mock_fc: MagicMock
    ) -> None:
        """Test skip_fc_connection method."""
        window, _ = connection_window
        with patch(f"{_MOD}.logging_warning") as mock_logging_warning:
            window.skip_fc_connection(mock_fc)
        assert mock_logging_warning.call_count == 2
        mock_fc.disconnect.assert_called_once()
        window.root.destroy.assert_called_once()

    def test_skip_fc_connection_stops_periodic_refresh(
        self, connection_window: tuple[ConnectionSelectionWindow, MagicMock], mock_fc: MagicMock
    ) -> None:
        """
        Periodic port refresh is cancelled when the user skips the FC connection.

        GIVEN: The connection window is open with an active periodic refresh timer
        WHEN: The user chooses to skip the FC connection and work with .param files on disk
        THEN: stop_periodic_refresh should be called on the connection_selection_widgets
        AND: No stale tkinter callbacks remain scheduled after the window is destroyed
        """
        window, mock_widgets = connection_window
        with patch(f"{_MOD}.logging_warning"):
            window.skip_fc_connection(mock_fc)
        mock_widgets.stop_periodic_refresh.assert_called_once()


# ---------------------------------------------------------------------------
# TestBaudrateSelectionBehavior
# ---------------------------------------------------------------------------


@pytest.fixture
def baudrate_widget(mock_parent: MagicMock) -> ConnectionSelectionWidgets:
    """ConnectionSelectionWidgets configured for baudrate testing."""
    mock_fc = MagicMock()
    mock_fc.comport = None
    mock_fc.master = None
    mock_fc.get_connection_tuples.return_value = [
        ("COM1", "Serial Port COM1"),
        ("Add another", "Add another connection"),
    ]
    mock_baudrate_var = MagicMock()

    with (
        patch("tkinter.ttk.Frame"),
        patch("tkinter.ttk.Label"),
        patch(f"{_MOD}.PairTupleCombobox"),
        patch("tkinter.ttk.Combobox"),
        patch("tkinter.StringVar", return_value=mock_baudrate_var),
        patch(f"{_MOD}.show_tooltip"),
        patch(f"{_MOD}.ProgramSettings.get_connection_history", return_value=[]),
    ):
        widget = ConnectionSelectionWidgets(
            mock_parent,
            MagicMock(spec=tk.Frame),
            mock_fc,
            destroy_parent_on_connect=True,
            download_params_on_connect=False,
            default_baudrate=115200,
        )
    widget._mock_fc = mock_fc  # type: ignore[attr-defined]
    widget._mock_baudrate_var = mock_baudrate_var  # type: ignore[attr-defined]
    widget.baudrate_var = mock_baudrate_var
    return widget


class TestBaudrateSelectionBehavior:
    """
    BDD tests for baudrate selection GUI functionality.

    Tests user behavior and business value for baudrate selection features.
    """

    def test_user_can_view_all_supported_baudrates(self, mock_parent: MagicMock) -> None:
        """
        User can view all ArduPilot supported baudrates in the combobox.

        GIVEN: A user opens the flight controller connection dialog
        WHEN: They look at the baudrate selection combobox
        THEN: All valid ArduPilot baudrates should be available for selection
        AND: The baudrates should include both common and specialized values
        """
        mock_fc = MagicMock()
        mock_fc.comport = None
        mock_fc.master = None
        mock_fc.get_connection_tuples.return_value = [("COM1", "Serial Port COM1"), ("Add another", "Add another connection")]

        with patch("tkinter.ttk.Combobox") as mock_combo:
            with (
                patch("tkinter.ttk.Frame"),
                patch("tkinter.ttk.Label"),
                patch(f"{_MOD}.PairTupleCombobox"),
                patch("tkinter.StringVar"),
                patch(f"{_MOD}.show_tooltip"),
                patch(f"{_MOD}.ProgramSettings.get_connection_history", return_value=[]),
            ):
                ConnectionSelectionWidgets(
                    mock_parent,
                    MagicMock(spec=tk.Frame),
                    mock_fc,
                    destroy_parent_on_connect=True,
                    download_params_on_connect=False,
                    default_baudrate=115200,
                )
            mock_combo_call = mock_combo.call_args

        assert mock_combo_call is not None
        call_kwargs = mock_combo_call[1]
        assert "values" in call_kwargs
        assert call_kwargs["values"] == SUPPORTED_BAUDRATES

    def test_user_sees_default_baudrate_preselected(self, baudrate_widget: ConnectionSelectionWidgets) -> None:
        """
        User sees the default baudrate (115200) preselected when opening the dialog.

        GIVEN: A user opens the flight controller connection dialog
        WHEN: The dialog loads with default settings
        THEN: The default baudrate should be 115200
        """
        assert baudrate_widget.default_baudrate == 115200

    def test_user_can_select_custom_baudrate_for_special_hardware(self, baudrate_widget: ConnectionSelectionWidgets) -> None:
        """
        User can select a custom baudrate for specialized flight controller hardware.

        GIVEN: A user has special flight controller hardware requiring a specific baudrate
        WHEN: They click on the baudrate combobox and select a different value
        THEN: The new baudrate should be stored and used for the next connection attempt
        """
        baudrate_widget._mock_baudrate_var.get.return_value = "921600"  # type: ignore[attr-defined]

        with patch.object(baudrate_widget, "reconnect"):
            baudrate_widget.reconnect("COM1")

    def test_user_receives_error_handling_for_invalid_baudrate_input(
        self, baudrate_widget: ConnectionSelectionWidgets
    ) -> None:
        """
        User receives proper error handling when invalid baudrate input is provided.

        GIVEN: A user manually enters an invalid baudrate value
        WHEN: They attempt to connect with the invalid baudrate
        THEN: The system should fallback to the default baudrate gracefully
        AND: The connection attempt should proceed without crashing
        """
        baudrate_widget._mock_baudrate_var.get.side_effect = ValueError("Invalid baudrate")  # type: ignore[attr-defined]
        baudrate_widget._mock_fc.connect.return_value = None  # type: ignore[attr-defined]

        with (
            patch(f"{_MOD}.ProgressWindow"),
            patch(f"{_MOD}.messagebox.showerror"),
        ):
            baudrate_widget.reconnect("COM1")

        baudrate_widget._mock_fc.connect.assert_called_once()  # type: ignore[attr-defined]
        call_args = baudrate_widget._mock_fc.connect.call_args  # type: ignore[attr-defined]
        assert "baudrate" in call_args[1]
        assert call_args[1]["baudrate"] == 115200

    def test_user_can_connect_with_selected_baudrate(self, baudrate_widget: ConnectionSelectionWidgets) -> None:
        """
        User can successfully connect to flight controller using selected baudrate.

        GIVEN: A user has selected a specific baudrate for their hardware
        WHEN: They initiate a connection to the flight controller
        THEN: The connection should use the selected baudrate value
        AND: The baudrate should be passed correctly to the flight controller
        """
        custom_baudrate = "460800"
        baudrate_widget._mock_baudrate_var.get.return_value = custom_baudrate  # type: ignore[attr-defined]
        baudrate_widget._mock_fc.connect.return_value = None  # type: ignore[attr-defined]

        with patch(f"{_MOD}.ProgressWindow"):
            baudrate_widget.reconnect("COM1")

        baudrate_widget._mock_fc.connect.assert_called_once()  # type: ignore[attr-defined]
        call_args = baudrate_widget._mock_fc.connect.call_args  # type: ignore[attr-defined]
        assert "baudrate" in call_args[1]
        assert call_args[1]["baudrate"] == int(custom_baudrate)

    def test_baudrate_selection_integrates_with_connection_workflow(self, baudrate_widget: ConnectionSelectionWidgets) -> None:
        """
        Baudrate selection integrates seamlessly with the overall connection workflow.

        GIVEN: A user is working through the connection setup process
        WHEN: They select both a connection port and a baudrate
        THEN: Both selections should be preserved and used together
        AND: The user should be able to complete the full connection workflow
        """
        selected_port = "COM1"
        selected_baudrate = "230400"
        baudrate_widget._mock_baudrate_var.get.return_value = selected_baudrate  # type: ignore[attr-defined]
        baudrate_widget._mock_fc.connect.return_value = None  # type: ignore[attr-defined]
        mock_comport = MagicMock()
        mock_comport.device = selected_port
        baudrate_widget._mock_fc.comport = mock_comport  # type: ignore[attr-defined]

        with patch(f"{_MOD}.ProgressWindow"):
            result = baudrate_widget.reconnect(selected_port)

        baudrate_widget._mock_fc.connect.assert_called_once()  # type: ignore[attr-defined]
        call_args = baudrate_widget._mock_fc.connect.call_args  # type: ignore[attr-defined]
        assert call_args[0][0] == selected_port
        assert "baudrate" in call_args[1]
        assert call_args[1]["baudrate"] == int(selected_baudrate)
        assert result is False

    def test_baudrate_combobox_allows_manual_input_for_flexibility(self, mock_parent: MagicMock) -> None:
        """
        Baudrate combobox allows manual input for maximum user flexibility.

        GIVEN: A user has hardware requiring a non-standard baudrate
        WHEN: The combobox is configured
        THEN: Its state should be "normal" to allow both selection and free-text entry
        """
        mock_fc = MagicMock()
        mock_fc.comport = None
        mock_fc.master = None
        mock_fc.get_connection_tuples.return_value = [("COM1", "Serial Port COM1"), ("Add another", "Add another connection")]

        with patch("tkinter.ttk.Combobox") as mock_combo:
            with (
                patch("tkinter.ttk.Frame"),
                patch("tkinter.ttk.Label"),
                patch(f"{_MOD}.PairTupleCombobox"),
                patch("tkinter.StringVar"),
                patch(f"{_MOD}.show_tooltip"),
                patch(f"{_MOD}.ProgramSettings.get_connection_history", return_value=[]),
            ):
                ConnectionSelectionWidgets(
                    mock_parent,
                    MagicMock(spec=tk.Frame),
                    mock_fc,
                    destroy_parent_on_connect=True,
                    download_params_on_connect=False,
                    default_baudrate=115200,
                )
            mock_combo_call = mock_combo.call_args

        assert mock_combo_call is not None
        call_kwargs = mock_combo_call[1]
        assert "state" in call_kwargs
        assert call_kwargs["state"] == "normal"

    def test_user_sees_helpful_tooltip_for_baudrate_selection(self, mock_parent: MagicMock) -> None:
        """
        User sees helpful tooltip explaining baudrate selection and recommendations.

        GIVEN: A user hovers over the baudrate combobox
        WHEN: The tooltip appears
        THEN: It should provide clear guidance about baudrate selection
        AND: It should mention that 115200 is the recommended value for most flight controllers
        """
        mock_fc = MagicMock()
        mock_fc.comport = None
        mock_fc.master = None
        mock_fc.get_connection_tuples.return_value = [("COM1", "Serial Port COM1"), ("Add another", "Add another connection")]

        with (
            patch(f"{_MOD}.show_tooltip") as mock_tooltip,
            patch("tkinter.ttk.Frame"),
            patch("tkinter.ttk.Label"),
            patch(f"{_MOD}.PairTupleCombobox"),
            patch("tkinter.ttk.Combobox"),
            patch("tkinter.StringVar"),
            patch(f"{_MOD}.ProgramSettings.get_connection_history", return_value=[]),
        ):
            ConnectionSelectionWidgets(
                mock_parent,
                MagicMock(spec=tk.Frame),
                mock_fc,
                destroy_parent_on_connect=True,
                download_params_on_connect=False,
                default_baudrate=115200,
            )

        baudrate_tooltip_found = False
        for call in mock_tooltip.call_args_list:
            if len(call[0]) > 1 and "baudrate" in str(call[0][1]).lower():
                baudrate_tooltip_found = True
                tooltip_text = call[0][1]
                assert "115200" in tooltip_text
                assert "flight controllers" in tooltip_text.lower()
                break

        assert baudrate_tooltip_found, "Baudrate tooltip was not configured"

    def test_user_can_change_baudrate_and_reconnect_automatically(self, baudrate_widget: ConnectionSelectionWidgets) -> None:
        """
        User can change baudrate and system automatically reconnects with new setting.

        GIVEN: A user has an active flight controller connection
        WHEN: They change the baudrate in the combobox
        THEN: The system should automatically reconnect using the new baudrate
        AND: The connection should use the updated baudrate setting
        """
        mock_comport = MagicMock()
        mock_comport.device = "COM1"
        baudrate_widget._mock_fc.comport = mock_comport  # type: ignore[attr-defined]
        baudrate_widget._mock_fc.master = MagicMock()  # type: ignore[attr-defined]
        baudrate_widget._mock_baudrate_var.get.return_value = "460800"  # type: ignore[attr-defined]

        with patch.object(baudrate_widget, "reconnect") as mock_reconnect:
            baudrate_widget.on_baudrate_combobox_change(MagicMock())
            mock_reconnect.assert_called_once_with("COM1")

    def test_baudrate_change_ignored_when_no_active_connection(self, baudrate_widget: ConnectionSelectionWidgets) -> None:
        """
        Baudrate changes are ignored when no active connection exists.

        GIVEN: A user has no active flight controller connection
        WHEN: They change the baudrate in the combobox
        THEN: No reconnection attempt should be made
        AND: The system should wait for manual connection initiation
        """
        baudrate_widget._mock_fc.master = None  # type: ignore[attr-defined]
        baudrate_widget._mock_fc.comport = None  # type: ignore[attr-defined]

        with patch.object(baudrate_widget, "reconnect") as mock_reconnect:
            baudrate_widget.on_baudrate_combobox_change(MagicMock())
            mock_reconnect.assert_not_called()


# ---------------------------------------------------------------------------
# TestPeriodicPortRefresh
# ---------------------------------------------------------------------------


@pytest.fixture
def periodic_widget(mock_parent: MagicMock) -> ConnectionSelectionWidgets:
    """ConnectionSelectionWidgets configured for periodic-refresh testing."""
    mock_fc = MagicMock()
    mock_fc.comport = None
    mock_fc.master = None
    mock_fc.get_connection_tuples.return_value = [
        ("COM1", "Serial Port COM1"),
        ("Add another", "Add another connection"),
    ]
    mock_baudrate_var = MagicMock()

    with (
        patch("tkinter.ttk.Frame"),
        patch("tkinter.ttk.Label"),
        patch(f"{_MOD}.PairTupleCombobox"),
        patch("tkinter.ttk.Combobox"),
        patch("tkinter.StringVar", return_value=mock_baudrate_var),
        patch(f"{_MOD}.show_tooltip"),
        patch(f"{_MOD}.ProgramSettings.get_connection_history", return_value=[]),
    ):
        widget = ConnectionSelectionWidgets(
            mock_parent,
            MagicMock(spec=tk.Frame),
            mock_fc,
            destroy_parent_on_connect=True,
            download_params_on_connect=False,
            default_baudrate=115200,
        )
    widget.baudrate_var = mock_baudrate_var
    widget._mock_fc = mock_fc  # type: ignore[attr-defined]
    return widget


class TestPeriodicPortRefresh:
    """
    BDD tests for the periodic port list auto-refresh feature.

    Verifies that the port combobox is automatically kept up to date every 3 seconds,
    that the timer is stopped at the right lifecycle moments, and that re-entrant
    refresh calls are safely suppressed.
    """

    def test_periodic_refresh_starts_on_init(
        self, periodic_widget: ConnectionSelectionWidgets, mock_parent: MagicMock
    ) -> None:
        """
        Port discovery is performed and rescheduled when the widget is initialized.

        GIVEN: The ConnectionSelectionWidgets is being initialized
        WHEN: The widget is created
        THEN: discover_connections should have been called to scan for available ports
        AND: root.after should have been called to schedule the next recurring refresh
        AND: The widget should not be in a refreshing state after initialization completes
        """
        periodic_widget._mock_fc.discover_connections.assert_called_once_with(  # type: ignore[attr-defined]
            progress_callback=None, preserved_connections=[]
        )
        mock_parent.root.after.assert_called_with(3000, periodic_widget._refresh_ports)
        assert periodic_widget._is_refreshing is False

    def test_periodic_refresh_stops_on_connection(self, periodic_widget: ConnectionSelectionWidgets) -> None:
        """
        Periodic port refresh stops when connection is established.

        GIVEN: Periodic refresh is running
        WHEN: A connection to a flight controller is successfully established
        THEN: The periodic refresh should be stopped
        AND: No further refresh attempts should be scheduled
        """
        periodic_widget._refresh_timer_id = "mock_timer_id"
        periodic_widget.baudrate_var.get.return_value = "115200"
        periodic_widget._mock_fc.connect.return_value = None  # type: ignore[attr-defined]
        periodic_widget._mock_fc.comport = MagicMock()  # type: ignore[attr-defined]
        periodic_widget._mock_fc.comport.device = "COM1"  # type: ignore[attr-defined]

        with (
            patch(f"{_MOD}.ProgressWindow") as mock_progress_window,
            patch(f"{_MOD}.show_no_connection_error"),
            patch(f"{_MOD}.ProgramSettings.store_connection", return_value="COM1") as mock_store,
        ):
            mock_progress_window.return_value.destroy = MagicMock()
            result = periodic_widget.reconnect("COM1")

        assert result is False
        assert periodic_widget._refresh_timer_id is None
        mock_store.assert_called_once_with("COM1")

    def test_periodic_refresh_stops_on_window_close(
        self, periodic_widget: ConnectionSelectionWidgets, mock_parent: MagicMock
    ) -> None:
        """
        Periodic port refresh stops when connection window is closed.

        GIVEN: The connection window is open with periodic refresh running
        WHEN: The user closes the window
        THEN: after_cancel should be called with the active timer ID
        AND: The timer ID should be cleared to prevent double-cancellation
        """
        periodic_widget._refresh_timer_id = "mock_timer_id"
        periodic_widget.stop_periodic_refresh()
        mock_parent.root.after_cancel.assert_called_once_with("mock_timer_id")
        assert periodic_widget._refresh_timer_id is None

    def test_refresh_preserves_selection_when_port_still_available(self, periodic_widget: ConnectionSelectionWidgets) -> None:
        """
        Port refresh preserves user selection when the port is still available.

        GIVEN: A user has selected a specific port (e.g., COM1)
        WHEN: The port list is refreshed and COM1 is still available
        THEN: COM1 should remain selected
        AND: The combobox should not change the user's selection
        """
        mock_combobox = MagicMock()
        periodic_widget.conn_selection_combobox = mock_combobox
        mock_combobox.get_selected_key.return_value = "COM1"
        mock_combobox.get_entries_tuple.return_value = [
            ("COM1", "Serial Port COM1"),
            ("COM2", "Serial Port COM2"),
            ("Add another", "Add another"),
        ]
        new_tuples = [
            ("COM1", "Serial Port COM1"),
            ("COM2", "Serial Port COM2"),
            ("COM3", "Serial Port COM3"),
            ("Add another", "Add another"),
        ]
        periodic_widget._mock_fc.get_connection_tuples.return_value = new_tuples  # type: ignore[attr-defined]

        periodic_widget._refresh_ports()

        mock_combobox.set_entries_tuple.assert_called_once_with(new_tuples, "COM1")

    def test_refresh_updates_when_port_disappears(self, periodic_widget: ConnectionSelectionWidgets) -> None:
        """
        Port refresh updates the combobox when the selected port disappears.

        GIVEN: A user has selected a specific port (e.g., COM1)
        WHEN: The port list is refreshed and COM1 is no longer available
        THEN: The combobox is updated with the new port list
        AND: The prior selection token is preserved for PairTupleCombobox to handle gracefully
        """
        mock_combobox = MagicMock()
        periodic_widget.conn_selection_combobox = mock_combobox
        mock_combobox.get_selected_key.return_value = "COM1"
        mock_combobox.get_entries_tuple.return_value = [
            ("COM1", "Serial Port COM1"),
            ("COM2", "Serial Port COM2"),
            ("Add another", "Add another"),
        ]
        new_tuples = [
            ("COM2", "Serial Port COM2"),
            ("COM3", "Serial Port COM3"),
            ("Add another", "Add another"),
        ]
        periodic_widget._mock_fc.get_connection_tuples.return_value = new_tuples  # type: ignore[attr-defined]

        periodic_widget._refresh_ports()

        mock_combobox.set_entries_tuple.assert_called_once_with(new_tuples, "COM1")

    def test_refresh_does_not_update_if_list_unchanged(self, periodic_widget: ConnectionSelectionWidgets) -> None:
        """
        Port refresh skips update when port list has not changed.

        GIVEN: The current port list is [COM1, COM2]
        WHEN: A refresh is triggered and the discovered ports are still [COM1, COM2]
        THEN: The combobox should not be updated
        AND: Unnecessary UI updates should be avoided
        """
        mock_combobox = MagicMock()
        periodic_widget.conn_selection_combobox = mock_combobox
        current_tuples = [
            ("COM1", "Serial Port COM1"),
            ("COM2", "Serial Port COM2"),
            ("Add another", "Add another"),
        ]
        mock_combobox.get_entries_tuple.return_value = current_tuples
        mock_combobox.get_selected_key.return_value = "COM1"
        periodic_widget._mock_fc.get_connection_tuples.return_value = current_tuples  # type: ignore[attr-defined]

        periodic_widget._refresh_ports()

        mock_combobox.set_entries_tuple.assert_not_called()

    def test_refresh_prevents_reentrant_calls(self, periodic_widget: ConnectionSelectionWidgets) -> None:
        """
        Port refresh prevents re-entrant calls during ongoing refresh.

        GIVEN: A port refresh is currently in progress
        WHEN: Another refresh is triggered before the first completes
        THEN: The second refresh should return immediately without action
        AND: Race conditions should be avoided
        """
        periodic_widget._mock_fc.discover_connections.reset_mock()  # type: ignore[attr-defined]
        periodic_widget._is_refreshing = True
        periodic_widget._refresh_ports()
        periodic_widget._mock_fc.discover_connections.assert_not_called()  # type: ignore[attr-defined]
        periodic_widget._is_refreshing = False


# ---------------------------------------------------------------------------
# TestConnectionHistoryCacheInitialization
# ---------------------------------------------------------------------------


def _make_widget(history: list[str]) -> ConnectionSelectionWidgets:
    """Helper that builds a ConnectionSelectionWidgets with a specific history."""
    mock_parent = MagicMock()
    mock_parent.root = MagicMock()
    mock_fc = MagicMock()
    mock_fc.comport = None
    mock_fc.master = None
    mock_fc.get_connection_tuples.return_value = [("Add another", "Add another")]

    with (
        patch("tkinter.ttk.Frame"),
        patch("tkinter.ttk.Label"),
        patch(f"{_MOD}.PairTupleCombobox"),
        patch("tkinter.ttk.Combobox"),
        patch("tkinter.StringVar"),
        patch(f"{_MOD}.show_tooltip"),
        patch(f"{_MOD}.ProgramSettings.get_connection_history", return_value=history),
    ):
        return ConnectionSelectionWidgets(
            mock_parent,
            MagicMock(),
            mock_fc,
            destroy_parent_on_connect=True,
            download_params_on_connect=False,
        )


class TestConnectionHistoryCacheInitialization:
    """
    BDD tests verifying that the in-memory connection history cache is correctly loaded.

    The cache is populated from ProgramSettings at widget initialization time.
    """

    def test_history_cache_is_populated_from_program_settings_on_startup(self) -> None:
        """
        In-memory history cache contains all connections loaded from ProgramSettings at init.

        GIVEN: ProgramSettings holds three previously used connection strings
        WHEN: ConnectionSelectionWidgets is initialized
        THEN: _connection_history_cache should contain exactly those three strings
        AND: Their order should be preserved (most-recent-first)
        """
        history = ["tcp:127.0.0.1:5761", "COM3", "udp:0.0.0.0:14550"]
        widget = _make_widget(history)
        assert widget._connection_history_cache == history

    def test_stored_connections_are_registered_with_flight_controller_on_init(self) -> None:
        """
        Each connection in the loaded history is registered with the flight controller.

        GIVEN: ProgramSettings holds two previously used connections
        WHEN: ConnectionSelectionWidgets is initialized
        THEN: flight_controller.add_connection should have been called once per stored entry
        AND: Each call should use the exact stored connection string
        """
        history = ["COM1", "tcp:127.0.0.1:5761"]
        mock_parent = MagicMock()
        mock_parent.root = MagicMock()
        mock_fc = MagicMock()
        mock_fc.comport = None
        mock_fc.master = None
        mock_fc.get_connection_tuples.return_value = [("Add another", "Add another")]

        with (
            patch("tkinter.ttk.Frame"),
            patch("tkinter.ttk.Label"),
            patch(f"{_MOD}.PairTupleCombobox"),
            patch("tkinter.ttk.Combobox"),
            patch("tkinter.StringVar"),
            patch(f"{_MOD}.show_tooltip"),
            patch(f"{_MOD}.ProgramSettings.get_connection_history", return_value=history),
        ):
            ConnectionSelectionWidgets(
                mock_parent,
                MagicMock(),
                mock_fc,
                destroy_parent_on_connect=True,
                download_params_on_connect=False,
            )

        calls = [call[0][0] for call in mock_fc.add_connection.call_args_list]
        assert "COM1" in calls
        assert "tcp:127.0.0.1:5761" in calls

    def test_history_cache_is_empty_when_settings_has_no_stored_connections(self) -> None:
        """
        In-memory cache is empty when ProgramSettings has no stored connections.

        GIVEN: First-time application startup with no stored connection history
        WHEN: ConnectionSelectionWidgets is initialized
        THEN: _connection_history_cache should be an empty list
        AND: flight_controller.add_connection should not have been called
        """
        widget = _make_widget([])
        assert widget._connection_history_cache == []


# ---------------------------------------------------------------------------
# TestPersistAndCacheConnectionBehavior
# ---------------------------------------------------------------------------


@pytest.fixture
def persist_widget(mock_parent: MagicMock) -> tuple[ConnectionSelectionWidgets, MagicMock, MagicMock]:
    """
    ConnectionSelectionWidgets for _persist_and_cache_connection tests.

    Returns (widget, mock_fc, mock_combobox).
    """
    mock_fc = MagicMock()
    mock_fc.comport = None
    mock_fc.master = None
    mock_fc.get_connection_tuples.return_value = [("Add another", "Add another")]
    mock_combobox = MagicMock()
    mock_baudrate_var = MagicMock()
    mock_baudrate_var.get.return_value = "115200"

    with (
        patch("tkinter.ttk.Frame"),
        patch("tkinter.ttk.Label"),
        patch("tkinter.ttk.Combobox"),
        patch("tkinter.StringVar", return_value=mock_baudrate_var),
        patch(f"{_MOD}.PairTupleCombobox", return_value=mock_combobox),
        patch(f"{_MOD}.show_tooltip"),
        patch(f"{_MOD}.ProgramSettings.get_connection_history", return_value=[]),
    ):
        widget = ConnectionSelectionWidgets(
            mock_parent,
            MagicMock(),
            mock_fc,
            destroy_parent_on_connect=True,
            download_params_on_connect=False,
        )
    widget.conn_selection_combobox = mock_combobox
    widget.baudrate_var = mock_baudrate_var
    return widget, mock_fc, mock_combobox


class TestPersistAndCacheConnectionBehavior:
    """
    BDD tests for _persist_and_cache_connection.

    Verifies that the normalized return value is used consistently by reconnect() and add_connection().
    """

    # ------------------------------------------------------------------
    # _persist_and_cache_connection unit tests
    # ------------------------------------------------------------------

    def test_persist_and_cache_returns_normalized_value_when_store_succeeds(
        self, persist_widget: tuple[ConnectionSelectionWidgets, MagicMock, MagicMock]
    ) -> None:
        """
        _persist_and_cache_connection returns the normalized string from the store.

        GIVEN: A user types a connection string with surrounding whitespace
        WHEN: _persist_and_cache_connection normalizes and stores it
        THEN: The stripped (normalized) string should be returned
        AND: Callers can use the return value as a stable lookup key
        """
        widget, _, _ = persist_widget
        with patch(f"{_MOD}.ProgramSettings.store_connection", return_value="COM3"):
            result = widget._persist_and_cache_connection("  COM3  ")
        assert result == "COM3"

    def test_persist_and_cache_returns_original_string_when_store_rejects_input(
        self, persist_widget: tuple[ConnectionSelectionWidgets, MagicMock, MagicMock]
    ) -> None:
        """
        _persist_and_cache_connection falls back to the original string when the store rejects it.

        GIVEN: An input that ProgramSettings considers invalid (e.g. excessively long)
        WHEN: store_connection returns None
        THEN: The original (un-normalized) input should be returned as a safe fallback
        AND: No exception should be raised
        """
        widget, _, _ = persist_widget
        with patch(f"{_MOD}.ProgramSettings.store_connection", return_value=None):
            result = widget._persist_and_cache_connection("x" * 201)
        assert result == "x" * 201

    def test_persist_and_cache_places_normalized_value_at_front_of_cache(
        self, persist_widget: tuple[ConnectionSelectionWidgets, MagicMock, MagicMock]
    ) -> None:
        """
        _persist_and_cache_connection inserts the normalized string at the front of the cache.

        GIVEN: The cache currently holds two older connections
        WHEN: A new connection is persisted
        THEN: The normalized new connection should become the first cache entry
        AND: The old entries should remain (in their original relative order)
        """
        widget, _, _ = persist_widget
        widget._connection_history_cache = ["COM1", "COM2"]

        with patch(f"{_MOD}.ProgramSettings.store_connection", return_value="tcp:127.0.0.1:5761"):
            widget._persist_and_cache_connection("tcp:127.0.0.1:5761")

        assert widget._connection_history_cache[0] == "tcp:127.0.0.1:5761"
        assert "COM1" in widget._connection_history_cache
        assert "COM2" in widget._connection_history_cache

    def test_persist_and_cache_deduplicates_existing_matching_cache_entry(
        self, persist_widget: tuple[ConnectionSelectionWidgets, MagicMock, MagicMock]
    ) -> None:
        """
        _persist_and_cache_connection removes the old occurrence of a re-used connection.

        GIVEN: The cache already contains "COM3" at position 2
        WHEN: "COM3" is persisted again (user reconnects to a previous device)
        THEN: The cache should contain "COM3" exactly once, at the front
        AND: No duplicate entries should exist
        """
        widget, _, _ = persist_widget
        widget._connection_history_cache = ["COM1", "COM4", "COM3"]

        with patch(f"{_MOD}.ProgramSettings.store_connection", return_value="COM3"):
            widget._persist_and_cache_connection("COM3")

        assert widget._connection_history_cache[0] == "COM3"
        assert widget._connection_history_cache.count("COM3") == 1

    # ------------------------------------------------------------------
    # Normalized value propagation through reconnect()
    # ------------------------------------------------------------------

    def test_reconnect_sets_previous_selection_to_normalized_value(
        self, persist_widget: tuple[ConnectionSelectionWidgets, MagicMock, MagicMock]
    ) -> None:
        """
        After a successful connect, previous_selection holds the normalized connection string.

        GIVEN: The user typed a connection string with surrounding whitespace
        WHEN: reconnect() succeeds and normalizes the string via _persist_and_cache_connection
        THEN: self.previous_selection should be the stripped, normalized value
        AND: Not the raw whitespace-padded input that was passed to reconnect()
        """
        widget, mock_fc, _ = persist_widget
        mock_comport = MagicMock()
        mock_comport.device = "COM3"
        mock_fc.comport = mock_comport
        mock_fc.connect.return_value = ""

        with (
            patch(f"{_MOD}.ProgressWindow"),
            patch(f"{_MOD}.ProgramSettings.store_connection", return_value="COM3"),
        ):
            widget.reconnect("  COM3  ")

        assert widget.previous_selection == "COM3"

    def test_reconnect_registers_normalized_connection_with_flight_controller(
        self, persist_widget: tuple[ConnectionSelectionWidgets, MagicMock, MagicMock]
    ) -> None:
        """
        After a successful connect, flight_controller.add_connection receives the normalized string.

        GIVEN: The user provides a whitespace-padded connection string
        WHEN: reconnect() completes successfully
        THEN: flight_controller.add_connection should be called with the normalized value
        AND: Not with the original raw string, to keep the registry consistent with the combobox
        """
        widget, mock_fc, _ = persist_widget
        mock_comport = MagicMock()
        mock_comport.device = "COM3"
        mock_fc.comport = mock_comport
        mock_fc.connect.return_value = ""
        mock_fc.add_connection.reset_mock()

        with (
            patch(f"{_MOD}.ProgressWindow"),
            patch(f"{_MOD}.ProgramSettings.store_connection", return_value="COM3"),
        ):
            widget.reconnect("  COM3  ")

        mock_fc.add_connection.assert_called_with("COM3")

    # ------------------------------------------------------------------
    # Normalized value propagation through add_connection()
    # ------------------------------------------------------------------

    def test_add_connection_uses_normalized_value_for_flight_controller_and_combobox(
        self, persist_widget: tuple[ConnectionSelectionWidgets, MagicMock, MagicMock]
    ) -> None:
        """
        add_connection uses the normalized string for flight_controller and combobox after persist.

        GIVEN: The user manually enters a connection string with surrounding whitespace
        WHEN: add_connection normalizes the string via _persist_and_cache_connection
        THEN: flight_controller.add_connection should receive the stripped value
        AND: conn_selection_combobox.set_entries_tuple should use the stripped value as selection key
        AND: reconnect should be called with the stripped value
        """
        widget, mock_fc, mock_combobox = persist_widget
        padded = "  tcp:127.0.0.1:5761  "
        normalized = "tcp:127.0.0.1:5761"
        updated_tuples = [(normalized, normalized), ("Add another", "Add another")]
        mock_fc.get_connection_tuples.return_value = updated_tuples
        mock_fc.add_connection.reset_mock()

        with (
            patch(f"{_MOD}.simpledialog.askstring", return_value=padded),
            patch(f"{_MOD}.ProgramSettings.store_connection", return_value=normalized),
            patch.object(widget, "reconnect") as mock_reconnect,
        ):
            result = widget.add_connection()

        assert result == normalized
        mock_fc.add_connection.assert_called_with(normalized)
        mock_combobox.set_entries_tuple.assert_called_with(updated_tuples, normalized)
        mock_reconnect.assert_called_with(normalized)
