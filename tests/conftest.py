#!/usr/bin/env python3

"""
Shared pytest fixtures for vehicle components data model tests.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import contextlib
import json
import logging
import os
import platform
import select
import signal
import subprocess
import time
import tkinter as tk
from collections.abc import Callable, Generator
from pathlib import Path
from typing import Any, NamedTuple, Optional
from unittest.mock import patch

import pyautogui
import pytest
from test_data_model_vehicle_components_common import SAMPLE_DOC_DICT, ComponentDataModelFixtures

from ardupilot_methodic_configurator.backend_filesystem import LocalFilesystem
from ardupilot_methodic_configurator.backend_flightcontroller import FlightController
from ardupilot_methodic_configurator.data_model_parameter_editor import ParameterEditor
from ardupilot_methodic_configurator.frontend_tkinter_base_window import BaseWindow

# ==================== SHARED TKINTER TESTING CONFIGURATION ====================


class MockConfiguration(NamedTuple):
    """Configuration for common mocking patterns in Tkinter tests."""

    patch_tkinter: bool = True
    patch_icon_setup: bool = True
    patch_theme_setup: bool = True
    patch_dpi_detection: bool = True
    dpi_scaling_factor: float = 1.0


# ==================== SHARED TKINTER FIXTURES ====================


@pytest.fixture(autouse=True)
def test_environment() -> Generator[None, None, None]:
    """Ensure consistent test environment for all Tkinter tests."""
    original_env = os.environ.get("PYTEST_CURRENT_TEST")
    os.environ["PYTEST_CURRENT_TEST"] = "true"

    yield

    if original_env is None:
        os.environ.pop("PYTEST_CURRENT_TEST", None)
    else:
        os.environ["PYTEST_CURRENT_TEST"] = original_env


@pytest.fixture(scope="session")
def root() -> Generator[tk.Tk, None, None]:
    """Create and clean up Tk root window for testing (session-scoped for robustness)."""
    # Try to reuse existing root or create new one
    try:
        root_instance = tk._default_root  # type: ignore[attr-defined] # pylint: disable=protected-access
        if root_instance is None:
            root_instance = tk.Tk()
    except (AttributeError, tk.TclError):
        root_instance = tk.Tk()

    root_instance.withdraw()  # Hide the main window during tests

    # Patch the iconphoto method to prevent errors with mock PhotoImage
    original_iconphoto = root_instance.iconphoto

    def mock_iconphoto(*args, **kwargs) -> None:  # pylint: disable=unused-argument
        pass

    root_instance.iconphoto = mock_iconphoto  # type: ignore[method-assign]

    yield root_instance

    # Restore original method and destroy root
    root_instance.iconphoto = original_iconphoto  # type: ignore[method-assign]

    # Only destroy if we're the last test
    with contextlib.suppress(tk.TclError):
        root_instance.quit()  # Close the event loop


@pytest.fixture
def tk_root() -> Generator[tk.Tk, None, None]:
    """Provide a real Tkinter root for integration tests (legacy name for compatibility)."""
    tk_root_instance = None
    try:
        tk_root_instance = tk.Tk()
        tk_root_instance.withdraw()
        yield tk_root_instance
    except tk.TclError:
        pytest.skip("Tkinter not available in test environment")
    finally:
        if tk_root_instance is not None:
            with contextlib.suppress(tk.TclError):
                tk_root_instance.destroy()


@pytest.fixture
def mock_tkinter_context() -> Callable[[Optional[MockConfiguration]], tuple[contextlib.ExitStack, list]]:
    """Provide common Tkinter mocking context manager."""

    def _mock_context(config: Optional[MockConfiguration] = None) -> tuple[contextlib.ExitStack, list]:
        if config is None:
            config = MockConfiguration()

        patches = []

        if config.patch_tkinter:
            patches.extend([patch("tkinter.Tk"), patch("tkinter.Toplevel")])

        if config.patch_icon_setup:
            patches.append(patch.object(BaseWindow, "_setup_application_icon"))

        if config.patch_theme_setup:
            patches.append(patch.object(BaseWindow, "_setup_theme_and_styling"))

        if config.patch_dpi_detection:
            patches.append(patch.object(BaseWindow, "_get_dpi_scaling_factor", return_value=config.dpi_scaling_factor))

        return contextlib.ExitStack(), patches

    return _mock_context


# ==================== VEHICLE COMPONENTS DATA MODEL FIXTURES ====================


# Make all fixtures available across test files
@pytest.fixture
def vehicle_components() -> ComponentDataModelFixtures:
    """Create a VehicleComponents instance."""
    return ComponentDataModelFixtures.create_vehicle_components()


@pytest.fixture
def component_datatypes() -> dict[str, Any]:
    """Create component datatypes."""
    return ComponentDataModelFixtures.create_component_datatypes()


@pytest.fixture
def sample_doc_dict() -> dict[str, Any]:
    """Create a sample doc_dict for testing."""
    return SAMPLE_DOC_DICT.copy()


# ==================== GUI TESTING CONSTANTS ====================


PARAMETER_EDITOR_TABLE_HEADERS_SIMPLE = (
    "-/+",
    "Parameter",
    "Current Value",
    " ",
    "New Value",
    "Unit",
    "Why are you changing this parameter?",
)

PARAMETER_EDITOR_TABLE_HEADERS_ADVANCED = (
    "-/+",
    "Parameter",
    "Current Value",
    " ",
    "New Value",
    "Unit",
    "Upload",
    "Why are you changing this parameter?",
)


@pytest.fixture
def gui_test_environment() -> None:
    """Set up GUI test environment with screen validation."""
    # Verify screen environment is available
    screen_width, screen_height = pyautogui.size()
    assert screen_width > 0
    assert screen_height > 0

    # Verify we can take a screenshot
    screenshot = pyautogui.screenshot()
    assert screenshot is not None
    assert screenshot.size[0] > 0
    assert screenshot.size[1] > 0


@pytest.fixture
def test_param_editor(tmp_path) -> ParameterEditor:
    """Create a test ParameterEditor with minimal setup for GUI tests."""
    # Create a temporary directory structure
    vehicle_dir = tmp_path / "test_vehicle"
    vehicle_dir.mkdir()

    # Create minimal parameter files
    (vehicle_dir / "00_default.param").write_text("# Test default parameters\n")
    (vehicle_dir / "04_board_orientation.param").write_text("# Test board orientation\n")

    # Create minimal vehicle_components.json
    vehicle_components_data = {
        "Format version": 0,
        "Components": {
            "Flight Controller": {
                "Product": {"Manufacturer": "", "Model": "", "URL": "", "Version": ""},
                "Firmware": {"Type": "ArduCopter", "Version": "4.5.1"},
                "Specifications": {"MCU Series": ""},
                "Notes": "",
            },
            "Frame": {
                "Product": {"Manufacturer": "", "Model": "", "URL": "", "Version": ""},
                "Specifications": {"TOW min Kg": 0.1, "TOW max Kg": 0.1},
                "Notes": "",
            },
            "Battery Monitor": {
                "Product": {"Manufacturer": "", "Model": "", "URL": "", "Version": ""},
                "Firmware": {"Type": "", "Version": ""},
                "FC Connection": {"Type": "", "Protocol": ""},
                "Notes": "",
            },
        },
    }
    (vehicle_dir / "vehicle_components.json").write_text(json.dumps(vehicle_components_data, indent=2))

    # Create mock FlightController
    fc = FlightController(reboot_time=5, baudrate=115200)

    # Create LocalFilesystem
    filesystem = LocalFilesystem(
        str(vehicle_dir), "ArduCopter", "", allow_editing_template_files=False, save_component_to_system_templates=False
    )

    # Create ParameterEditor
    return ParameterEditor("04_board_orientation.param", fc, filesystem)


# ==================== SITL TESTING FIXTURES ====================


class SITLManager:
    """Manages ArduCopter SITL process lifecycle."""

    def __init__(self, sitl_binary: Optional[str] = None) -> None:
        self.sitl_binary = sitl_binary or os.environ.get("SITL_BINARY")
        self.process: Optional[subprocess.Popen] = None
        self.connection_string = "tcp:127.0.0.1:5760"
        self._ready = False

    def is_available(self) -> bool:
        """Check if SITL binary is available."""
        return self.sitl_binary is not None and Path(self.sitl_binary).exists()

    def is_running(self) -> bool:
        """Check if SITL process is currently running."""
        return self.process is not None and self.process.poll() is None

    def ensure_running(self) -> bool:
        """Ensure the SITL process is running, starting it if necessary."""
        if self.is_running() and self._ready:
            return True
        return self.start()

    def start(self) -> bool:  # pylint: disable=too-many-return-statements, too-many-branches, too-many-statements, too-many-locals # noqa: PLR0911, PLR0915
        """Start SITL process."""
        if self.is_running():
            logging.info("SITL already running, reusing existing instance")
            return True

        if not self.is_available():
            return False

        # Kill any existing SITL processes
        self.stop()

        self._ready = False

        if self.sitl_binary is None:
            return False

        # Validate SITL binary path for security
        sitl_path = Path(self.sitl_binary)
        if not sitl_path.exists():
            logging.error("SITL binary does not exist: %s", self.sitl_binary)
            return False
        if not sitl_path.is_file():
            logging.error("SITL binary is not a file: %s", self.sitl_binary)
            return False
        # Ensure the binary name looks reasonable (contains 'arducopter' or 'sitl')
        if not any(keyword in sitl_path.name.lower() for keyword in ["arducopter", "sitl", "copter"]):
            logging.warning("SITL binary name looks suspicious: %s", sitl_path.name)

        # Build SITL command
        sitl_args = [
            "--model",
            "quad",
            "--home",
            "40.071374,-105.229930,1440,0",  # Random location
            "--defaults",
            "copter.parm",  # Relative to SITL binary directory
            "--sysid",
            "1",
            "--speedup",
            "1",  # Real-time for better connection stability on Windows/WSL
        ]

        # On Windows, run SITL through WSL
        if platform.system() == "Windows":
            # Convert Windows path to WSL path
            wsl_sitl_path = str(sitl_path).replace("\\", "/").replace("C:", "/mnt/c")
            wsl_cwd = str(sitl_path.parent).replace("\\", "/").replace("C:", "/mnt/c")

            # Run SITL in WSL - simpler command that keeps process alive
            cmd = ["wsl", "cd", wsl_cwd, "&&", wsl_sitl_path, *sitl_args]
        else:
            cmd = [self.sitl_binary, *sitl_args]

        # Set environment to force unbuffered output
        env = os.environ.copy()
        env["PYTHONUNBUFFERED"] = "1"

        sitl_ready = False

        try:  # pylint: disable=too-many-nested-blocks
            # Change to SITL binary directory so it finds copter.parm
            cwd = str(sitl_path.parent)

            # pylint: disable=consider-using-with
            self.process = subprocess.Popen(  # noqa: S603
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,  # Merge stderr into stdout
                start_new_session=True,  # Create new process group
                bufsize=0,  # Unbuffered for real-time output
                universal_newlines=True,
                env=env,
                cwd=cwd,
            )
            # pylint: enable=consider-using-with

            # Wait for SITL to initialize and print startup messages
            timeout = 20  # Increased timeout for slower systems
            start_time = time.time()
            startup_output = []

            while time.time() - start_time < timeout:
                if self.process.poll() is not None:
                    # Process died
                    stdout, _ = self.process.communicate()
                    error_msg = f"SITL process died with exit code {self.process.returncode}."
                    if stdout:
                        error_msg += f" Output: {stdout[:500]}"  # First 500 chars
                    logging.error(error_msg)
                    pytest.fail(error_msg)
                    return False

                # Check for ready indicator in output
                if self.process.stdout:
                    # Check if there's data to read (non-blocking)
                    if platform.system() != "Windows":
                        ready, _, _ = select.select([self.process.stdout], [], [], 0.1)
                        if ready:
                            line = self.process.stdout.readline()
                            if line:
                                startup_output.append(line.strip())
                                logging.info("SITL: %s", line.strip())  # Changed to info for visibility
                                # Look for signs SITL is ready - be more specific
                                if "bind port 5760" in line.lower() or "waiting for connection" in line.lower():
                                    logging.info("SITL is ready and waiting for connections")
                                    sitl_ready = True
                                    # Don't return yet, consume a bit more output
                                    time.sleep(1)  # Let SITL stabilize
                                    return True
                    else:
                        # On Windows, just wait
                        time.sleep(1)
                else:
                    time.sleep(0.5)

            # If we got here, check if we saw the ready message
            if sitl_ready:
                logging.info("SITL is ready")
                return True

            # If process is still running, assume it's ready
            if self.process.poll() is None:
                logging.warning("SITL startup timeout reached but process still running, assuming SITL is ready")
                return True

            logging.error("SITL failed to start within timeout")
            return False

        except (OSError, subprocess.SubprocessError, FileNotFoundError, PermissionError) as e:
            logging.error("Failed to start SITL: %s", e)
            pytest.fail(f"Failed to start SITL: {e}")
            return False
        finally:
            if sitl_ready:
                self._ready = True
            elif self.is_running():
                # Even if we hit timeout but process is running, assume ready to allow reuse
                self._ready = True

    def stop(self) -> None:
        """Stop SITL process."""
        if self.process:
            try:
                self._ready = False
                if platform.system() == "Windows":
                    # On Windows, kill the WSL bash process and any child processes
                    # First try graceful termination
                    subprocess.run(["wsl", "pkill", "-f", "arducopter"], check=False, capture_output=True)  # noqa: S607
                    self.process.terminate()
                    try:
                        self.process.wait(timeout=10)
                    except subprocess.TimeoutExpired:
                        # Force kill
                        subprocess.run(
                            ["wsl", "pkill", "-9", "-f", "arducopter"],  # noqa: S607
                            check=False,
                            capture_output=True,
                        )
                        self.process.kill()
                        self.process.wait(timeout=5)
                else:
                    # Kill the entire process group on Linux
                    os.killpg(os.getpgid(self.process.pid), signal.SIGTERM)

                    # Wait for process to terminate
                    try:
                        self.process.wait(timeout=10)
                    except subprocess.TimeoutExpired:
                        # Force kill if it doesn't terminate gracefully
                        os.killpg(os.getpgid(self.process.pid), signal.SIGKILL)
                        self.process.wait(timeout=5)

            except (ProcessLookupError, OSError):
                # Process already dead
                pass
            finally:
                self.process = None
        else:
            self._ready = False


@pytest.fixture(scope="session")
def sitl_manager() -> Generator[SITLManager, None, None]:
    """Provide SITL manager for the test session."""
    manager = SITLManager()

    if not manager.is_available():
        pytest.skip("ArduCopter SITL binary not available")

    if not manager.start():
        pytest.skip("Failed to start ArduCopter SITL")

    yield manager

    # Cleanup
    manager.stop()


@pytest.fixture
def sitl_flight_controller(sitl_manager: SITLManager) -> Generator[FlightController, None, None]:  # pylint: disable=redefined-outer-name
    """FlightController connected to SITL instance."""
    if not sitl_manager.ensure_running():
        pytest.fail("Could not start SITL")

    # Allow brief stabilization if SITL was just started
    time.sleep(2)

    fc = FlightController(reboot_time=2, baudrate=115200)

    # Attempt to connect, retrying once if SITL is still warming up
    connection_error = fc.connect(device=sitl_manager.connection_string)
    if connection_error:
        time.sleep(3)
        connection_error = fc.connect(device=sitl_manager.connection_string)

    if connection_error:
        pytest.fail(f"Could not connect to SITL: {connection_error}")

    yield fc

    # Cleanup connection but keep SITL running for subsequent tests
    fc.disconnect()
