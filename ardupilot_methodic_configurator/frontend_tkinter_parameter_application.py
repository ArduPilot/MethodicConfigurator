"""
Shared bootstrap helpers for standalone and embedded parameter tools.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import tkinter as tk
from argparse import ArgumentParser, Namespace
from collections.abc import Callable
from contextlib import suppress
from logging import basicConfig as logging_basicConfig
from logging import getLevelName as logging_getLevelName
from typing import TYPE_CHECKING, Any

from ardupilot_methodic_configurator import _
from ardupilot_methodic_configurator.backend_filesystem import LocalFilesystem
from ardupilot_methodic_configurator.backend_filesystem_program_settings import ProgramSettings
from ardupilot_methodic_configurator.backend_flightcontroller import FlightController
from ardupilot_methodic_configurator.common_arguments import add_common_arguments
from ardupilot_methodic_configurator.data_model_parameter_editor import ParameterEditor
from ardupilot_methodic_configurator.frontend_tkinter_base_window import show_error_popup
from ardupilot_methodic_configurator.frontend_tkinter_connection_selection import ConnectionSelectionWindow

if TYPE_CHECKING:
    from ardupilot_methodic_configurator.frontend_tkinter_parameter_editor import ParameterEditorUiServices


class ParameterApplicationHost:
    """Host services shared by embedded and standalone parameter dialogs."""

    def __init__(
        self,
        root: tk.Tk | tk.Toplevel,
        parameter_editor: ParameterEditor,
        ui: "ParameterEditorUiServices",
        *,
        gui_complexity: str | None = None,
        on_close: Callable[[], None] | None = None,
    ) -> None:
        self.root = root
        self.parameter_editor = parameter_editor
        self.ui = ui
        self.gui_complexity = gui_complexity or str(ProgramSettings.get_setting("gui_complexity"))
        self._on_close = on_close

    def repopulate_parameter_table(self) -> None:
        """Notify the owner that a standalone or embedded dialog has closed."""
        if self._on_close is not None:
            self._on_close()

    def on_skip_click(self) -> None:
        """Satisfy the parameter-table host interface; skipping is unavailable here."""


def create_argument_parser(description: str) -> ArgumentParser:
    """Create the common parser for standalone tools using FC and filesystem options."""
    parser = ArgumentParser(description=description)
    parser = FlightController.add_argparse_arguments(parser)
    parser = LocalFilesystem.add_argparse_arguments(parser)
    return add_common_arguments(parser)


def configure_standalone_logging(args: Namespace) -> None:
    """Configure logging from the shared standalone command-line arguments."""
    logging_basicConfig(level=logging_getLevelName(args.loglevel), format="%(asctime)s - %(levelname)s - %(message)s")


def initialize_standalone_parameter_editor(
    args: Namespace,
    flight_controller: FlightController,
    ui: "ParameterEditorUiServices",
) -> ParameterEditor | None:
    """Create the connected-controller parameter model and report setup errors in the UI."""
    try:
        return ParameterEditor.for_connected_flight_controller(
            flight_controller,
            args.vehicle_dir,
            args.vehicle_type,
        )
    except (OSError, ValueError, SystemExit) as exc:
        ui.show_error(_("Flight-controller parameter setup error"), str(exc))
        return None


def connect_standalone_flight_controller(
    args: Namespace,
    flight_controller: FlightController,
    *,
    connection_selection_window_factory: Callable[..., ConnectionSelectionWindow] = ConnectionSelectionWindow,
    error_popup: Callable[[str, str], None] = show_error_popup,
) -> bool:
    """Connect using CLI settings, prompting for a port after failed auto-detection."""
    connection_error = flight_controller.connect(args.device)
    if not connection_error:
        return True
    if args.device or _("No auto-detected ports responded") not in connection_error:
        error_popup(_("Flight-controller connection error"), connection_error)
        return False

    connection_window = connection_selection_window_factory(
        flight_controller,
        connection_error,
        default_baudrate=args.baudrate,
        show_skip_connection_option=False,
    )
    connection_window.root.mainloop()
    return flight_controller.master is not None


def run_standalone_parameter_application(  # pylint: disable=too-many-arguments
    args: Namespace,
    initialize_editor: Callable[[tk.Tk, FlightController, "ParameterEditorUiServices"], ParameterEditor | None],
    open_window: Callable[[tk.Tk, ParameterEditor, "ParameterEditorUiServices"], Any],
    *,
    root_factory: Callable[..., tk.Tk] = tk.Tk,
    flight_controller_factory: Callable[..., FlightController] = FlightController,
    connection_selection_window_factory: Callable[..., ConnectionSelectionWindow] = ConnectionSelectionWindow,
    error_popup: Callable[[str, str], None] = show_error_popup,
) -> None:
    """
    Run a parameter tool while keeping root and connection ownership in one place.

    ``initialize_editor`` prepares the tool-specific filesystem/editor state and
    may return ``None`` when the user cancels. ``open_window`` creates the
    tool-specific dialog and may return ``False`` when opening it was cancelled.
    Neither callback owns the Tk event loop.
    """
    configure_standalone_logging(args)
    root: tk.Tk | None = None
    flight_controller: FlightController | None = None
    try:
        flight_controller = flight_controller_factory(reboot_time=args.reboot_time, baudrate=args.baudrate)
        # The connection selector creates its own Tk root. Let it finish before
        # creating the placeholder root for the parameter dialog.
        if not connect_standalone_flight_controller(
            args,
            flight_controller,
            connection_selection_window_factory=connection_selection_window_factory,
            error_popup=error_popup,
        ):
            return

        # Keep a small visible owner window while parameter data loads.
        root = root_factory(className="ArduPilotMethodicConfigurator")
        root.title(_("Preparing parameter data"))
        root.geometry("500x100")
        root.deiconify()
        root.update_idletasks()

        # ParameterEditorUiServices is imported lazily to keep this shared
        # bootstrap independent of the large editor frontend at import time.
        from ardupilot_methodic_configurator.frontend_tkinter_parameter_editor import (  # noqa: PLC0415  # pylint: disable=import-outside-toplevel
            ParameterEditorUiServices,
        )

        ui = ParameterEditorUiServices.default()
        parameter_editor = initialize_editor(root, flight_controller, ui)
        if parameter_editor is None:
            return
        root.withdraw()
        if open_window(root, parameter_editor, ui) is False:
            return
        root.mainloop()
    finally:
        if flight_controller is not None:
            flight_controller.disconnect()
        if root is not None:
            with suppress(tk.TclError):
                root.destroy()
