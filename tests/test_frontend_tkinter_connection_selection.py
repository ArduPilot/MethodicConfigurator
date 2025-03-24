#!/usr/bin/env python3

"""
Tests for the frontend_tkinter_connection_selection.py file.

This file is part of Ardupilot methodic configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2025 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import tkinter as tk
import unittest
from unittest.mock import MagicMock, patch

from ardupilot_methodic_configurator.frontend_tkinter_connection_selection import (
    ConnectionSelectionWidgets,
    ConnectionSelectionWindow,
)


class TestConnectionSelectionWidgets(unittest.TestCase):
    """ConnectionSelectionWidgets test class."""

    def setUp(self) -> None:
        # Mock the parent object
        self.mock_parent = MagicMock()
        self.mock_parent.root = MagicMock()

        # Mock the parent_frame
        self.mock_parent_frame = MagicMock(spec=tk.ttk.Labelframe)

        # Mock the flight controller with a carefully constructed response
        self.mock_flight_controller = MagicMock()
        self.mock_flight_controller.comport = None
        self.mock_flight_controller.master = None
        self.mock_flight_controller.get_connection_tuples.return_value = [
            ("COM1", "Serial Port COM1"),
            ("COM2", "Serial Port COM2"),
            ("Add another", "Add another connection"),
        ]

        # Mock PairTupleCombobox
        self.mock_combobox = MagicMock()
        self.mock_combobox.__getitem__.return_value = ["COM1", "COM2", "Add another"]

        # Create the widget with patched dependencies
        with (
            patch("tkinter.ttk.Frame"),
            patch("tkinter.ttk.Label"),
            patch("ardupilot_methodic_configurator.frontend_tkinter_autoresize_combobox.update_combobox_width"),
            patch(
                "ardupilot_methodic_configurator.frontend_tkinter_pair_tuple_combobox.PairTupleCombobox",
                return_value=self.mock_combobox,
            ),
            patch("ardupilot_methodic_configurator.frontend_tkinter_connection_selection.show_tooltip"),
        ):
            self.widget = ConnectionSelectionWidgets(
                self.mock_parent,
                self.mock_parent_frame,
                self.mock_flight_controller,
                destroy_parent_on_connect=True,
                download_params_on_connect=True,
            )
            # Assign our mock combobox to the widget for test access
            self.widget.conn_selection_combobox = self.mock_combobox

    @patch("ardupilot_methodic_configurator.frontend_tkinter_connection_selection.logging_debug")
    def test_init(self, mock_logging_debug) -> None:  # pylint: disable=unused-argument
        """Test the initialization of ConnectionSelectionWidgets."""
        # Test with flight_controller.comport = None
        assert self.widget.previous_selection is None

        # Test with a flight_controller.comport with device attribute
        mock_comport = MagicMock()
        mock_comport.device = "COM1"

        # Create a new flight controller with explicit connection tuples
        new_flight_controller = MagicMock()
        new_flight_controller.comport = mock_comport
        new_flight_controller.master = None
        # Make sure this returns the exact same list each time it's called
        connection_tuples = [
            ("COM1", "Serial Port COM1"),
            ("COM2", "Serial Port COM2"),
            ("Add another", "Add another connection"),
        ]
        new_flight_controller.get_connection_tuples.return_value = connection_tuples

        # Mock the combobox with proper values attribute
        new_mock_combobox = MagicMock()
        new_mock_combobox.__getitem__.return_value = ["COM1", "COM2", "Add another"]

        # Create a mock function for update_combobox_width that does nothing
        def mock_update_width(combobox) -> None:  # pylint: disable=unused-argument
            pass

        # Create a new widget with the new flight controller with more comprehensive patching
        with (
            patch("tkinter.ttk.Frame"),
            patch("tkinter.ttk.Label"),
            # Patch both locations where update_combobox_width might be called from
            patch(
                "ardupilot_methodic_configurator.frontend_tkinter_autoresize_combobox.update_combobox_width", mock_update_width
            ),
            patch(
                "ardupilot_methodic_configurator.frontend_tkinter_pair_tuple_combobox.update_combobox_width", mock_update_width
            ),
            patch(
                "ardupilot_methodic_configurator.frontend_tkinter_pair_tuple_combobox.PairTupleCombobox",
                return_value=new_mock_combobox,
            ),
            patch("ardupilot_methodic_configurator.frontend_tkinter_connection_selection.show_tooltip"),
        ):
            new_widget = ConnectionSelectionWidgets(
                self.mock_parent,
                self.mock_parent_frame,
                new_flight_controller,
                destroy_parent_on_connect=True,
                download_params_on_connect=True,
            )
            new_widget.conn_selection_combobox = new_mock_combobox

        # Test the properties
        assert new_widget.previous_selection == "COM1"
        assert new_widget.destroy_parent_on_connect is True
        assert new_widget.download_params_on_connect is True

    @patch("ardupilot_methodic_configurator.frontend_tkinter_connection_selection.logging_debug")
    def test_on_select_connection_combobox_change_add_another(self, mock_logging_debug) -> None:  # pylint: disable=unused-argument
        """Test on_select_connection_combobox_change when 'Add another' is selected."""
        # Set up the mock event
        mock_event = MagicMock()

        # Set up the combobox to return "Add another"
        self.mock_combobox.get_selected_key.return_value = "Add another"

        # Mock the add_connection method to return an empty string (canceled)
        self.widget.add_connection = MagicMock(return_value="")
        self.widget.previous_selection = "COM1"

        # Call the method
        self.widget.on_select_connection_combobox_change(mock_event)

        # Verify add_connection was called
        self.widget.add_connection.assert_called_once()

        # Verify set was called to revert to previous selection
        self.mock_combobox.set.assert_called_once_with("COM1")

    @patch("ardupilot_methodic_configurator.frontend_tkinter_connection_selection.logging_debug")
    def test_on_select_connection_combobox_change_new_connection(self, mock_logging_debug) -> None:  # pylint: disable=unused-argument
        """Test on_select_connection_combobox_change when a new connection is selected."""
        # Set up the mock event
        mock_event = MagicMock()

        # Set up the combobox to return a connection
        self.mock_combobox.get_selected_key.return_value = "COM2"

        # Mock the reconnect method
        self.widget.reconnect = MagicMock()

        # Call the method
        self.widget.on_select_connection_combobox_change(mock_event)

        # Verify reconnect was called with the selected connection
        self.widget.reconnect.assert_called_once_with("COM2")

    @patch("ardupilot_methodic_configurator.frontend_tkinter_connection_selection.logging_debug")
    def test_on_select_connection_combobox_change_same_connection(self, mock_logging_debug) -> None:  # pylint: disable=unused-argument
        """Test on_select_connection_combobox_change when the same connection is selected."""
        # Set up the flight controller with an existing comport
        mock_comport = MagicMock()
        mock_comport.device = "COM1"
        self.mock_flight_controller.comport = mock_comport
        self.mock_flight_controller.master = MagicMock()  # Not None

        # Set up the mock event
        mock_event = MagicMock()

        # Set up the combobox to return the same connection
        self.mock_combobox.get_selected_key.return_value = "COM1"

        # Mock the reconnect method
        self.widget.reconnect = MagicMock()

        # Call the method
        self.widget.on_select_connection_combobox_change(mock_event)

        # Verify reconnect was not called
        self.widget.reconnect.assert_not_called()

    @patch("ardupilot_methodic_configurator.frontend_tkinter_connection_selection.simpledialog.askstring")
    @patch("ardupilot_methodic_configurator.frontend_tkinter_connection_selection.logging_debug")
    def test_add_connection_canceled(self, mock_logging_debug, mock_askstring) -> None:  # pylint: disable=unused-argument
        """Test add_connection when the dialog is canceled."""
        # Set up the mock to return None (dialog canceled)
        mock_askstring.return_value = None

        # Reset the mock to clear any previous calls
        self.mock_flight_controller.get_connection_tuples.reset_mock()
        self.mock_flight_controller.add_connection.reset_mock()

        # Patch the reconnect method to prevent it from being called
        with patch.object(self.widget, "reconnect"):
            # Call the method
            result = self.widget.add_connection()

            # Verify the result
            assert result == ""

            # Verify the flight controller methods were not called
            self.mock_flight_controller.add_connection.assert_not_called()
            self.mock_flight_controller.get_connection_tuples.assert_not_called()

        # Test with empty string input
        mock_askstring.return_value = ""
        with patch.object(self.widget, "reconnect"):
            result = self.widget.add_connection()
            assert result == ""
            self.mock_flight_controller.add_connection.assert_not_called()
            self.mock_flight_controller.get_connection_tuples.assert_not_called()

        self.mock_flight_controller.comport = None

    @patch("ardupilot_methodic_configurator.frontend_tkinter_connection_selection.simpledialog.askstring")
    @patch("ardupilot_methodic_configurator.frontend_tkinter_connection_selection.logging_debug")
    def test_add_connection_success(self, mock_logging_debug, mock_askstring) -> None:  # pylint: disable=unused-argument
        """Test add_connection with a successful entry."""
        # Set up the mock to return a connection string
        mock_askstring.return_value = "tcp:127.0.0.1:5761"

        # Updated connection tuples after adding
        updated_tuples = [
            ("COM1", "Serial Port COM1"),
            ("COM2", "Serial Port COM2"),
            ("tcp:127.0.0.1:5761", "TCP 127.0.0.1:5761"),
            ("Add another", "Add another connection"),
        ]

        # Reset mocks
        self.mock_flight_controller.get_connection_tuples.reset_mock()
        self.mock_flight_controller.get_connection_tuples.return_value = updated_tuples
        self.mock_combobox.reset_mock()

        # Patch the reconnect method
        with patch.object(self.widget, "reconnect") as mock_reconnect:
            # Call the method
            result = self.widget.add_connection()

            # Verify the result
            assert result == "tcp:127.0.0.1:5761"

            # Verify the flight controller methods were called
            self.mock_flight_controller.add_connection.assert_called_once_with("tcp:127.0.0.1:5761")
            self.mock_flight_controller.get_connection_tuples.assert_called_once()

            # Verify the combobox was updated
            self.mock_combobox.set_entries_tuple.assert_called_once_with(updated_tuples, "tcp:127.0.0.1:5761")

            # Verify reconnect was called
            mock_reconnect.assert_called_once_with("tcp:127.0.0.1:5761")

    @patch("ardupilot_methodic_configurator.frontend_tkinter_connection_selection.ProgressWindow")
    @patch("ardupilot_methodic_configurator.frontend_tkinter_connection_selection.show_no_connection_error")
    def test_reconnect_with_error(self, mock_show_error, mock_progress_window) -> None:
        """Test reconnect when there's a connection error."""
        # Set up the progress window mock
        mock_progress_instance = MagicMock()
        mock_progress_window.return_value = mock_progress_instance

        # Set up flight controller to return an error
        self.mock_flight_controller.connect.return_value = "Connection error"

        # Call the method
        result = self.widget.reconnect("COM1")

        # Verify the progress window was created and used
        mock_progress_window.assert_called_once()
        self.mock_flight_controller.connect.assert_called_once_with("COM1", mock_progress_instance.update_progress_bar)

        # Verify the error was shown
        mock_show_error.assert_called_once_with("Connection error")

        # Verify the result
        assert result

        # Verify the progress window wasn't destroyed
        mock_progress_instance.destroy.assert_not_called()

    @patch("ardupilot_methodic_configurator.frontend_tkinter_connection_selection.ProgressWindow")
    @patch("ardupilot_methodic_configurator.frontend_tkinter_connection_selection.show_no_connection_error")
    def test_reconnect_success_destroy_parent(self, mock_show_error, mock_progress_window) -> None:
        """Test successful reconnect with destroy_parent_on_connect=True."""
        # Set up the progress window mock
        mock_progress_instance = MagicMock()
        mock_progress_window.return_value = mock_progress_instance

        # Set up flight controller to return no error
        self.mock_flight_controller.connect.return_value = ""

        # Set up a comport with device attribute
        mock_comport = MagicMock()
        mock_comport.device = "COM1"
        self.mock_flight_controller.comport = mock_comport

        # Call the method
        result = self.widget.reconnect("COM1")

        # Verify the progress window was created, used, and destroyed
        mock_progress_window.assert_called_once()
        self.mock_flight_controller.connect.assert_called_once_with("COM1", mock_progress_instance.update_progress_bar)
        mock_progress_instance.destroy.assert_called_once()

        # Verify no error was shown
        mock_show_error.assert_not_called()

        # Verify the result
        assert not result

        # Verify the previous selection was updated
        assert self.widget.previous_selection == "COM1"

        # Verify parent.root.destroy was called
        self.mock_parent.root.destroy.assert_called_once()

    @patch("ardupilot_methodic_configurator.frontend_tkinter_connection_selection.ProgressWindow")
    def test_reconnect_success_with_download(self, mock_progress_window) -> None:
        """Test successful reconnect with download_params_on_connect=True."""
        # Set up the progress window mock
        mock_progress_instance = MagicMock()
        mock_progress_window.return_value = mock_progress_instance

        # Set up flight controller to return no error
        self.mock_flight_controller.connect.return_value = ""

        # Set up a comport with device attribute
        mock_comport = MagicMock()
        mock_comport.device = "COM1"
        self.mock_flight_controller.comport = mock_comport

        # Add download_flight_controller_parameters method to parent
        self.mock_parent.download_flight_controller_parameters = MagicMock()

        # Call the method
        result = self.widget.reconnect("COM1")

        # Verify download_flight_controller_parameters was called
        self.mock_parent.download_flight_controller_parameters.assert_called_once_with(redownload=False)

        # Verify the result
        assert not result


class TestConnectionSelectionWindow(unittest.TestCase):  # pylint: disable=too-many-instance-attributes
    """ConnectionSelectionWindow test class."""

    def setUp(self) -> None:  # noqa: PLR0915 # pylint: disable=too-many-statements
        # Mock tk.Tk and tk.Toplevel before patching BaseWindow
        self.tk_patcher = patch("tkinter.Tk")
        self.mock_tk = self.tk_patcher.start()
        self.addCleanup(self.tk_patcher.stop)

        self.toplevel_patcher = patch("tkinter.Toplevel")
        self.mock_toplevel = self.toplevel_patcher.start()
        self.addCleanup(self.toplevel_patcher.stop)

        # Mock the PhotoImage to prevent icon issues
        self.photo_patcher = patch("tkinter.PhotoImage")
        self.mock_photo = self.photo_patcher.start()
        self.addCleanup(self.photo_patcher.stop)

        # Critical: patch the iconphoto methods to prevent errors
        self.iconphoto_tk_patcher = patch.object(tk.Tk, "iconphoto")
        self.mock_iconphoto_tk = self.iconphoto_tk_patcher.start()
        self.addCleanup(self.iconphoto_tk_patcher.stop)

        self.iconphoto_toplevel_patcher = patch.object(tk.Toplevel, "iconphoto")
        self.mock_iconphoto_toplevel = self.iconphoto_toplevel_patcher.start()
        self.addCleanup(self.iconphoto_toplevel_patcher.stop)

        # Patch the filesystem icon path
        self.icon_path_patcher = patch(
            "ardupilot_methodic_configurator.frontend_tkinter_base_window.LocalFilesystem.application_icon_filepath",
            return_value="mock_icon_path.png",
        )
        self.mock_icon_path = self.icon_path_patcher.start()
        self.addCleanup(self.icon_path_patcher.stop)

        # Patch widgets for UI components
        self.frame_patcher = patch("tkinter.ttk.Frame")
        self.mock_frame = self.frame_patcher.start()
        self.addCleanup(self.frame_patcher.stop)

        self.label_patcher = patch("tkinter.ttk.Label")
        self.mock_label = self.label_patcher.start()
        self.addCleanup(self.label_patcher.stop)

        self.labelframe_patcher = patch("tkinter.ttk.LabelFrame")
        self.mock_labelframe = self.labelframe_patcher.start()
        self.addCleanup(self.labelframe_patcher.stop)

        self.button_patcher = patch("tkinter.ttk.Button")
        self.mock_button = self.button_patcher.start()
        self.addCleanup(self.button_patcher.stop)

        # Patch the style
        self.style_patcher = patch("tkinter.ttk.Style")
        self.mock_style = self.style_patcher.start()
        self.addCleanup(self.style_patcher.stop)

        # Mock ConnectionSelectionWidgets
        self.widgets_patcher = patch(
            "ardupilot_methodic_configurator.frontend_tkinter_connection_selection.ConnectionSelectionWidgets"
        )
        self.mock_widgets_class = self.widgets_patcher.start()
        self.addCleanup(self.widgets_patcher.stop)

        # Create a mock instance for ConnectionSelectionWidgets
        self.mock_widgets = MagicMock()
        self.mock_widgets_class.return_value = self.mock_widgets

        # Patch tooltip
        self.tooltip_patcher = patch("ardupilot_methodic_configurator.frontend_tkinter_connection_selection.show_tooltip")
        self.mock_tooltip = self.tooltip_patcher.start()
        self.addCleanup(self.tooltip_patcher.stop)

        # Mock the flight controller
        self.mock_flight_controller = MagicMock()
        self.mock_flight_controller.comport = None
        self.mock_flight_controller.get_connection_tuples.return_value = [
            ("COM1", "Serial Port COM1"),
            ("COM2", "Serial Port COM2"),
            ("Add another", "Add another connection"),
        ]

        # Create a BaseWindow.__init__ function that sets the right attributes
        def mock_basewindow_init(self, root_tk=None) -> None:  # noqa: ARG001 # pylint: disable=unused-argument
            # Create and assign the mocked root attribute
            self.root = MagicMock()
            # Create and assign the mocked main_frame attribute
            self.main_frame = MagicMock()

        # Patch BaseWindow.__init__
        self.basewindow_patcher = patch(
            "ardupilot_methodic_configurator.frontend_tkinter_base_window.BaseWindow.__init__", mock_basewindow_init
        )
        self.mock_basewindow_init = self.basewindow_patcher.start()
        self.addCleanup(self.basewindow_patcher.stop)

        # Create the test instance
        self.window = ConnectionSelectionWindow(self.mock_flight_controller, "Test connection message")

        # Verify that connection_selection_widgets was created and is our mock
        assert hasattr(self.window, "connection_selection_widgets")

    @patch("ardupilot_methodic_configurator.frontend_tkinter_connection_selection.sys_exit")
    def test_close_and_quit(self, mock_sys_exit) -> None:
        """Test close_and_quit method."""
        self.window.close_and_quit()
        mock_sys_exit.assert_called_once_with(0)

    def test_fc_autoconnect(self) -> None:
        """Test fc_autoconnect method."""
        # Call the method
        self.window.fc_autoconnect()

        # Verify reconnect was called
        self.window.connection_selection_widgets.reconnect.assert_called_once()

    @patch("ardupilot_methodic_configurator.frontend_tkinter_connection_selection.logging_warning")
    def test_skip_fc_connection(self, mock_logging_warning) -> None:
        """Test skip_fc_connection method."""
        # Call the method
        self.window.skip_fc_connection(self.mock_flight_controller)

        # Verify logging was called
        assert mock_logging_warning.call_count == 2

        # Verify flight controller was disconnected
        self.mock_flight_controller.disconnect.assert_called_once()

        # Verify window was destroyed
        self.window.root.destroy.assert_called_once()


if __name__ == "__main__":
    unittest.main()
