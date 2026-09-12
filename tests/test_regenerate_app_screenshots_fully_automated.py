#!/usr/bin/env python3

"""
Tests for the fully automated application screenshot generator.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import argparse
import importlib.util
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import ANY, MagicMock, patch

from ardupilot_methodic_configurator.plugins.plugin_constants import PLUGIN_MOTOR_TEST

# pylint: disable=protected-access


def _load_screenshot_generator() -> ModuleType:
    """Load the standalone screenshot script as a test module."""
    script_path = Path(__file__).parents[1] / "scripts" / "regenerate_app_screenshots_fully_automated.py"
    spec = importlib.util.spec_from_file_location("screenshot_generator", script_path)
    if spec is None or spec.loader is None:
        message = f"Could not load screenshot generator from {script_path}"
        raise RuntimeError(message)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


screenshot_generator = _load_screenshot_generator()


def test_cleanup_plugin_view_ignores_non_callable_optional_hook() -> None:
    """Cleanup must not call an attribute that only happens to use the hook name."""
    destroy = MagicMock()
    plugin_view = SimpleNamespace(on_deactivate="not callable", destroy=destroy)

    screenshot_generator._cleanup_plugin_view(plugin_view)

    destroy.assert_called_once_with()


def test_screenshot_generator_registers_application_plugins_before_capture(tmp_path) -> None:
    """Screenshot generation initializes plugins just like normal application startup."""
    args = argparse.Namespace(
        images_dir=tmp_path,
        vehicle_dir=tmp_path,
        delay=0.0,
        padding=0,
        overwrite=False,
        log_level="WARNING",
    )

    with (
        patch.object(screenshot_generator, "parse_args", return_value=args),
        patch.object(screenshot_generator, "configure_logging"),
        patch.object(screenshot_generator, "register_plugins") as mock_register_plugins,
        patch.object(screenshot_generator, "capture_target"),
    ):
        assert screenshot_generator.main() == 0

    mock_register_plugins.assert_called_once_with()


def test_simple_parameter_editor_capture_suppresses_external_documentation(tmp_path) -> None:
    """Simple-mode capture does not launch a browser while settling the editor."""
    screenshot_generator.register_plugins()

    with (
        patch("ardupilot_methodic_configurator.data_model_parameter_editor.webbrowser_open_url") as open_browser,
        patch.object(screenshot_generator, "capture_widget"),
    ):
        screenshot_generator._capture_parameter_editor(
            tmp_path / "parameter-editor.png",
            delay=0.0,
            padding=0,
            vehicle_dir=screenshot_generator.DEFAULT_VEHICLE_DIR,
            current_file="05_board_orientation.param",
            gui_complexity="simple",
            scale=0.666,
        )

    open_browser.assert_not_called()


def test_motor_test_capture_uses_registered_plugin_with_fake_connection(tmp_path) -> None:
    """Motor-test screenshots use the registered plugin and a connected test FC."""
    fake_flight_controller = MagicMock()
    fake_window = MagicMock()
    fake_model = MagicMock()
    fake_plugin_view = MagicMock()
    fake_factory = MagicMock()
    fake_factory.create_model.return_value = fake_model
    fake_factory.create.return_value = fake_plugin_view

    with (
        patch.object(screenshot_generator, "FlightController", return_value=fake_flight_controller),
        patch.object(screenshot_generator, "LocalFilesystem"),
        patch.object(screenshot_generator, "BaseWindow", return_value=fake_window),
        patch.object(screenshot_generator, "plugin_factory", fake_factory),
        patch.object(screenshot_generator, "capture_widget"),
    ):
        screenshot_generator._capture_motor_test(
            tmp_path / "motor-test.png",
            delay=0.0,
            padding=0,
            vehicle_dir=screenshot_generator.DEFAULT_VEHICLE_DIR,
        )

    fake_flight_controller.set_master_for_testing.assert_called_once_with(ANY)
    assert fake_flight_controller.fc_parameters["FRAME_CLASS"] == 1.0
    assert fake_flight_controller.fc_parameters["FRAME_TYPE"] == 1.0
    assert fake_flight_controller.request_scaled_imu_messages.return_value == (True, "")
    assert fake_flight_controller.poll_scaled_imu.return_value is None
    assert fake_flight_controller.request_periodic_battery_status.return_value == (True, "")
    assert fake_flight_controller.get_battery_status.return_value == (None, "")
    fake_factory.create_model.assert_called_once()
    model_context = fake_factory.create_model.call_args.args[1]
    assert fake_factory.create_model.call_args.args[0] == PLUGIN_MOTOR_TEST
    assert model_context.flight_controller is fake_flight_controller
    fake_factory.create.assert_called_once_with(PLUGIN_MOTOR_TEST, fake_window.main_frame, fake_model, fake_window)
    fake_plugin_view.pack.assert_called_once_with(fill="both", expand=True)
    fake_flight_controller.disconnect.assert_called_once_with()
