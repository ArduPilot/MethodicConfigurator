#!/usr/bin/env python3
"""
Integration coverage for importing a log after closing the flight-controller selector.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import contextlib
import faulthandler
import gc
import os
import subprocess
import sys
import tkinter as tk
from collections.abc import Callable
from pathlib import Path
from threading import get_ident
from unittest.mock import patch
from weakref import finalize

import pytest
from pymavlink import mavutil

from ardupilot_methodic_configurator import __version__, backend_bin_log
from ardupilot_methodic_configurator.__main__ import create_and_configure_component_editor
from ardupilot_methodic_configurator.backend_filesystem import LocalFilesystem
from ardupilot_methodic_configurator.backend_filesystem_program_settings import ProgramSettings
from ardupilot_methodic_configurator.backend_flightcontroller import FlightController
from ardupilot_methodic_configurator.backend_flightcontroller_connection import FlightControllerConnection
from ardupilot_methodic_configurator.backend_flightcontroller_factory_serial import FakeSerialPortDiscovery
from ardupilot_methodic_configurator.data_model_flightcontroller_info import FlightControllerInfo
from ardupilot_methodic_configurator.data_model_par_dict import ParDict
from ardupilot_methodic_configurator.data_model_vehicle_project import VehicleProjectManager
from ardupilot_methodic_configurator.frontend_tkinter_connection_selection import ConnectionSelectionWindow
from ardupilot_methodic_configurator.frontend_tkinter_project_opener import VehicleProjectOpenerWindow

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(sys.platform == "darwin", reason="Real Tk lifecycle test needs a display; headless Aqua cannot render"),
]

_REPO_ROOT = Path(__file__).resolve().parents[1]
_FIXTURE_LOG = _REPO_ROOT / "tests" / "fixtures" / "backend_log_80k.bin"
_SUCCESS = "BIN_LOG_IMPORT_OK"
_CHILD_TIMEOUT = 60


@pytest.mark.timeout(_CHILD_TIMEOUT + 15)
def test_user_can_import_a_real_log_after_skipping_the_flight_controller(tmp_path: Path) -> None:
    """
    Closing the connection selector must not crash the subsequent log import.

    GIVEN: The user skips the connection and leaves closed Tk resources awaiting GC
    WHEN: The real parser collects garbage on its worker while importing a real log
    THEN: A project is saved and its component editor opens without Tcl finalization errors
    """
    # Tcl aborts cannot be caught by pytest: keep the real interpreter lifecycle in a child.
    try:
        result = subprocess.run(  # noqa: S603
            [sys.executable, "-X", "faulthandler", str(Path(__file__).resolve()), str(tmp_path)],
            cwd=_REPO_ROOT,
            env={
                **os.environ,
                "PYTHONPATH": str(_REPO_ROOT),
                "AMC_COMPONENT_TEMPLATES_DIR_TEST": str(_REPO_ROOT / "ardupilot_methodic_configurator" / "vehicle_templates"),
            },
            capture_output=True,
            text=True,
            timeout=_CHILD_TIMEOUT,
            check=False,
        )
    except subprocess.TimeoutExpired as timeout_error:
        stdout = (
            timeout_error.stdout.decode(errors="replace") if isinstance(timeout_error.stdout, bytes) else timeout_error.stdout
        )
        stderr = (
            timeout_error.stderr.decode(errors="replace") if isinstance(timeout_error.stderr, bytes) else timeout_error.stderr
        )
        pytest.fail(f"Log import child timed out after {_CHILD_TIMEOUT}s.\nstdout:\n{stdout}\nstderr:\n{stderr}")

    diagnostics = f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    assert result.returncode == 0, diagnostics
    assert _SUCCESS in result.stdout.splitlines(), diagnostics
    for error in (
        "Tcl_AsyncDelete",
        "main thread is not in main loop",
        "Exception ignored in",
        "Exception in Tkinter callback",
    ):
        assert error not in result.stderr, diagnostics
    project_dir = tmp_path / "settings" / "vehicles" / _FIXTURE_LOG.stem
    assert (project_dir / "vehicle_components.json").is_file()
    parameters = ParDict.from_file(str(project_dir / "00_default.param"))
    assert parameters["SYSID_THISMAV"].value == 1
    assert len(parameters) > 1000


def _run_import_scenario(workspace: Path) -> None:
    """Exercise production windows and parsing without hardware, downloads or user settings."""
    # Load the real application icons, which ordinary pytest setup deliberately suppresses.
    os.environ.pop("PYTEST_CURRENT_TEST", None)
    settings_dir = workspace / "settings"
    settings_dir.mkdir()
    ui_thread = get_ident()
    finalized: list[tuple[str, int]] = []
    before_parsing: list[list[tuple[str, int]]] = []
    open_log = backend_bin_log.open_log

    def record_cleanup(resource: str) -> None:
        finalized.append((resource, get_ident()))

    def open_log_with_worker_collection(
        logfile: str, progress_callback: Callable[[int], None] | None = None
    ) -> mavutil.mavfile:
        assert get_ident() != ui_thread
        before_parsing.append(finalized.copy())
        # Force the condition from issue #2280 without relying on allocation thresholds.
        gc.enable()
        gc.collect()
        return open_log(logfile, progress_callback)

    # Keep closed resources alive until run_task's UI collection or the parser's worker GC.
    gc.disable()
    with (
        patch.object(ProgramSettings, "_user_config_dir", return_value=str(settings_dir)),
        patch("ardupilot_methodic_configurator.backend_filesystem.parse_parameter_metadata", return_value={}),
        patch.object(backend_bin_log, "open_log", side_effect=open_log_with_worker_collection),
    ):
        connection = FlightControllerConnection(
            info=FlightControllerInfo(), network_ports=[], serial_port_discovery=FakeSerialPortDiscovery()
        )
        controller = FlightController(network_ports=[], connection_manager=connection)
        _skip_connection(controller, record_cleanup)
        assert not finalized

        filesystem = LocalFilesystem(
            None,  # type: ignore[arg-type]
            "",
            "",
            allow_editing_template_files=False,
            save_component_to_system_templates=False,
        )
        manager = VehicleProjectManager(filesystem, controller)
        opener = VehicleProjectOpenerWindow(manager)
        try:
            opener.bin_log_selection_widgets.on_select_file_callback(str(_FIXTURE_LOG))
            expected = [("image", ui_thread), ("variable", ui_thread), ("window", ui_thread)]
            assert before_parsing
            assert all(sorted(snapshot) == expected for snapshot in before_parsing), before_parsing
            assert filesystem.vehicle_type == "ArduCopter"
            assert filesystem.fw_version == "4.6.2"
            editor = create_and_configure_component_editor(__version__, filesystem, controller, "ArduCopter", manager)
            try:
                editor.root.update_idletasks()
                assert editor.root.winfo_exists()
                assert editor.main_frame.winfo_children()
            finally:
                editor.root.destroy()
        finally:
            # The import callback normally destroys the opener; also clean up on errors.
            with contextlib.suppress(tk.TclError):
                opener.root.destroy()
            gc.collect()
            gc.enable()
    print(_SUCCESS)  # noqa: T201


def _skip_connection(controller: FlightController, record_cleanup: Callable[[str], None]) -> None:
    """Close the real selector and release its frame's references before importing the log."""
    selector = ConnectionSelectionWindow(controller, "No serial ports found")
    finalize(selector.root, record_cleanup, "window")
    finalize(selector.connection_selection_widgets.baudrate_var, record_cleanup, "variable")
    finalize(selector._icon_photo, record_cleanup, "image")  # pylint: disable=protected-access
    selector.root.after_idle(selector.skip_fc_connection, controller)
    selector.root.mainloop()


if __name__ == "__main__":
    faulthandler.dump_traceback_later(_CHILD_TIMEOUT / 2)
    try:
        _run_import_scenario(Path(sys.argv[1]))
    finally:
        faulthandler.cancel_dump_traceback_later()
