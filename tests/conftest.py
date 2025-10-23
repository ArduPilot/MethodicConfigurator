#!/usr/bin/env python3

"""
Shared pytest fixtures for vehicle components data model tests.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2025 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import contextlib
import json
import os
import tkinter as tk
from collections.abc import Callable, Generator
from typing import Any, NamedTuple, Optional
from unittest.mock import MagicMock, patch

import pytest
from test_data_model_vehicle_components_common import SAMPLE_DOC_DICT, ComponentDataModelFixtures

from ardupilot_methodic_configurator.backend_filesystem import LocalFilesystem
from ardupilot_methodic_configurator.backend_flightcontroller import FlightController
from ardupilot_methodic_configurator.configuration_manager import ConfigurationManager
from ardupilot_methodic_configurator.data_model_par_dict import Par, ParDict
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
    # Only import pyautogui within the fixture to avoid slowing down non-GUI tests
    import pyautogui  # pylint: disable=import-outside-toplevel # noqa: PLC0415

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
def test_config_manager(tmp_path) -> ConfigurationManager:
    """Create a test ConfigurationManager with minimal setup for GUI tests."""
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

    # Create ConfigurationManager
    return ConfigurationManager("04_board_orientation.param", fc, filesystem)


# ==================== CONFIGURATION MANAGER TEST FIXTURES ====================


@pytest.fixture
def mock_flight_controller() -> MagicMock:
    """Fixture providing a mock flight controller with realistic test data."""
    mock_fc = MagicMock()
    mock_fc.fc_parameters = {"PARAM1": 1.0, "PARAM2": 3.0}
    mock_fc.master = MagicMock()  # Mock the master connection
    mock_fc.download_params = MagicMock(return_value=({"PARAM1": 1.0, "PARAM2": 3.0}, {}))
    mock_fc.upload_file = MagicMock(return_value=True)
    return mock_fc


@pytest.fixture
def mock_local_filesystem() -> MagicMock:
    """Fixture providing a mock local filesystem with realistic test data."""
    mock_fs = MagicMock()
    mock_fs.file_parameters = {"test_file.param": {"PARAM1": Par(1.0), "PARAM2": Par(3.0)}}
    mock_fs.param_default_dict = ParDict()
    mock_fs.doc_dict = SAMPLE_DOC_DICT  # Use sample doc dict for documentation availability
    mock_fs.forced_parameters = {}
    mock_fs.derived_parameters = {}
    mock_fs.export_to_param = MagicMock()
    mock_fs.vehicle_dir = "/mock/vehicle/dir"
    mock_fs.configuration_phases = {"Phase 1": {}, "Phase 2": {}, "Phase 3": {}}
    mock_fs.write_last_uploaded_filename = MagicMock()

    # Mock get_parameter_file_list to return expected files
    mock_fs.get_parameter_file_list.return_value = ["01_setup.param", "02_config.param", "complete.param"]

    # Mock get_documentation_text_and_url method with realistic return values
    mock_fs.get_documentation_text_and_url.side_effect = mock_get_documentation_text_and_url_basic
    return mock_fs


@pytest.fixture
def configuration_manager(mock_flight_controller, mock_local_filesystem) -> ConfigurationManager:  # pylint: disable=redefined-outer-name
    """Fixture providing a properly configured ConfigurationManager for behavior testing."""
    return ConfigurationManager("00_default.param", mock_flight_controller, mock_local_filesystem)


# ==================== SHARED TEST UTILITIES ====================


def mock_get_documentation_text_and_url_basic(file_name: str, _doc_type: str) -> tuple[str, str]:
    """Mock implementation that returns realistic documentation text based on file patterns."""
    if file_name.startswith(("01_", "02_", "1.", "10_", "123_", "99_")):
        # Numbered files are typically mandatory (high percentage)
        return ("80% mandatory (20% optional)", f"docs/{file_name}.html")
    if file_name in (
        "optional_step.param",
        "advanced_config.param",
        "complete.param",
        "00_default.param",  # Default file should be optional
        "",  # Empty filename
        "0_invalid_number.param",
    ):
        # Special files are typically optional (low percentage)
        return ("10% mandatory (90% optional)", f"docs/{file_name}.html")
    # Default case for other files
    return ("50% mandatory (50% optional)", f"docs/{file_name}.html")


def assert_download_workflow_result(
    configuration_manager,  # pylint: disable=redefined-outer-name
    selected_file: str,
    download_result: bool,
    confirmation_result: bool = True,
    expect_error_shown: bool = False,
) -> None:
    """
    Helper function to test download workflow results.

    Args:
        configuration_manager: The configuration manager instance
        selected_file: The file to test download for
        download_result: Expected result of the download function
        confirmation_result: Whether user confirms download (default True)
        expect_error_shown: Whether error should be shown (default False)

    """
    url = "https://example.com/test.bin"
    local_filename = "test.bin"

    configuration_manager._local_filesystem.get_download_url_and_local_filename.return_value = (url, local_filename)  # pylint: disable=protected-access
    configuration_manager._local_filesystem.vehicle_configuration_file_exists.return_value = False  # pylint: disable=protected-access

    ask_confirmation_mock = MagicMock(return_value=confirmation_result)
    show_error_mock = MagicMock()

    with patch("ardupilot_methodic_configurator.configuration_manager.download_file_from_url", return_value=download_result):
        # Act: Execute download workflow
        result = configuration_manager.should_download_file_from_url_workflow(
            selected_file,
            ask_confirmation=ask_confirmation_mock,
            show_error=show_error_mock,
        )

    # Assert: Check result and mock calls
    assert result is (download_result if confirmation_result else True)
    ask_confirmation_mock.assert_called_once()
    if expect_error_shown:
        show_error_mock.assert_called_once()
    else:
        show_error_mock.assert_not_called()
