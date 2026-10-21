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
from collections.abc import Generator
from contextlib import nullcontext
from pathlib import Path
from queue import SimpleQueue
from types import ModuleType, SimpleNamespace
from unittest.mock import ANY, MagicMock, call, patch

import pytest

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


@pytest.fixture(name="parameter_export_scene")
def parameter_export_scene_fixture() -> Generator[SimpleNamespace, None, None]:
    """Provide representative FC values and export controls without opening a display."""
    controller = MagicMock()
    controller.fc_parameters = {
        "WPNAV_SPEED": 500.0,
        "ANGLE_MAX": 3000.0,
        "ATC_ANG_RLL_P": 4.5,
        "RTL_ALT": 1500.0,
        "WPNAV_RADIUS": 200.0,
        "INS_ACC_ID": 1.0,
        "INS_GYR_ID": 2.0,
    }
    models = {
        name: SimpleNamespace(
            fc_value_equals_default_value=name in ("RTL_ALT", "WPNAV_RADIUS"),
            is_calibration=name.startswith("INS_"),
            is_readonly=False,
        )
        for name in controller.fc_parameters
    }
    editor = MagicMock()
    editor.parameter_editor.get_fc_parameters_for_export.return_value = models
    export_window = MagicMock(spec=screenshot_generator.tk.Toplevel)
    export_window.title.return_value = screenshot_generator.translate("Export parameters")
    checkboxes = [MagicMock(spec=screenshot_generator.ttk.Checkbutton) for _ in range(2)]
    for checkbox, label in zip(checkboxes, ("Calibration", "Default value"), strict=True):
        checkbox.cget.return_value = screenshot_generator.translate(label)
        checkbox.winfo_children.return_value = []
    decoy_label = MagicMock(spec=screenshot_generator.ttk.Label)
    decoy_label.cget.return_value = screenshot_generator.translate("Calibration")
    decoy_label.winfo_children.return_value = []
    export_window.winfo_children.return_value = [decoy_label, *checkboxes]
    editor.root.winfo_children.return_value = [export_window]
    with (
        patch.object(screenshot_generator, "_build_parameter_editor", return_value=(editor, controller)),
        patch.object(screenshot_generator.shutil, "copytree"),
        patch.object(screenshot_generator, "capture_widget") as capture,
    ):
        yield SimpleNamespace(
            editor=editor, controller=controller, models=models, window=export_window, checkboxes=checkboxes, capture=capture
        )


@pytest.mark.parametrize(
    ("failure", "message"),
    [
        ("missing-copter", "missing representative Copter parameters"),
        ("missing-defaults", "needs two default and two calibration parameters"),
        ("missing-calibrations", "needs two default and two calibration parameters"),
        ("loading-models", "Could not load parameter models"),
        ("missing-window", "Could not find the parameter export window"),
        ("capture", "Could not capture the export window"),
        (None, None),
    ],
)
def test_parameter_export_capture_always_releases_the_editor_and_connection(
    tmp_path: Path, parameter_export_scene: SimpleNamespace, failure: str | None, message: str | None
) -> None:
    """
    Screenshot preparation must not leak a window or connection when validation fails.

    GIVEN: An editor with downloaded FC values and an export preview
    WHEN: Fixture validation, preview lookup, or capture fails, or capture succeeds
    THEN: Owned resources are released and successful captures include representative rows
    """
    scene = parameter_export_scene
    if failure == "missing-copter":
        del scene.controller.fc_parameters["ANGLE_MAX"]
    elif failure == "missing-defaults":
        for name in ("RTL_ALT", "WPNAV_RADIUS"):
            del scene.models[name]
    elif failure == "missing-calibrations":
        for name in ("INS_ACC_ID", "INS_GYR_ID"):
            del scene.models[name]
    elif failure == "loading-models":
        scene.editor.parameter_editor.get_fc_parameters_for_export.side_effect = RuntimeError(message)
    elif failure == "missing-window":
        scene.editor.root.winfo_children.return_value = []
    elif failure == "capture":
        scene.capture.side_effect = RuntimeError(message)

    with pytest.raises(RuntimeError, match=message) if message is not None else nullcontext():
        screenshot_generator._capture_parameter_export(tmp_path / "export.png", 0.0, 0, tmp_path)

    scene.editor.current_plugin_view.on_deactivate.assert_called_once_with()
    scene.editor.current_plugin_view.destroy.assert_called_once_with()
    scene.editor.root.destroy.assert_called_once_with()
    scene.controller.disconnect.assert_called_once_with()
    if failure in (None, "capture"):
        scene.window.destroy.assert_called_once_with()
        for checkbox in scene.checkboxes:
            checkbox.invoke.assert_called_once_with()
        scene.capture.assert_called_once_with(scene.window, tmp_path / "export.png", 0.0, 0)
    else:
        scene.capture.assert_not_called()
    if failure is None:
        assert scene.controller.fc_parameters == {
            "WPNAV_SPEED": 600.0,
            "ANGLE_MAX": 3500.0,
            "ATC_ANG_RLL_P": 4.7,
            "RTL_ALT": 1500.0,
            "WPNAV_RADIUS": 200.0,
            "INS_ACC_ID": 1.0,
            "INS_GYR_ID": 2.0,
        }


def test_firmware_screenshot_capture_uses_sample_catalog_and_optional_progress(tmp_path) -> None:
    """
    Firmware screenshots use sample events without hardware, downloads, or a real display.

    GIVEN: A mocked firmware window and screenshot capture dependencies.
    WHEN: Normal and progress screenshots are prepared.
    THEN: Catalog and optional progress events are queued and the window is closed.
    """
    window = MagicMock()
    window.events = SimpleQueue()
    window.catalog_request_id = 4
    window.root.winfo_width.return_value = 750
    window.root.winfo_reqheight.return_value = 500

    with (
        patch.object(screenshot_generator, "FirmwareUploadWindow", return_value=window),
        patch.object(screenshot_generator, "settle_tk"),
        patch.object(screenshot_generator, "capture_widget") as capture,
        patch.object(screenshot_generator.pyautogui, "moveTo") as move_mouse,
    ):
        screenshot_generator._capture_firmware_upload(tmp_path / "firmware.png", 0, 0, show_progress=False)
        catalog_event = window.events.get_nowait()

        screenshot_generator._capture_firmware_upload(tmp_path / "firmware-progress.png", 0, 0, show_progress=True)
        progress_events = [window.events.get_nowait() for _ in range(3)]

    assert catalog_event[0:2] == ("catalog", 4)
    assert len(catalog_event[2]) == 1
    assert catalog_event[2][0].label == "4.6.0 (OFFICIAL, stable) — CubeBlack / arducopter.apj"
    assert [event[0] for event in progress_events] == ["catalog", "progress", "progress"]
    assert progress_events[1][1:] == (screenshot_generator.UploadStage.ERASING, 1, 1)
    assert progress_events[2][1:] == (screenshot_generator.UploadStage.PROGRAMMING, 65, 100)
    assert window.close.call_count == 2
    assert [call.args[1] for call in capture.call_args_list] == [
        tmp_path / "firmware.png",
        tmp_path / "firmware-progress.png",
    ]
    assert capture.call_count == 2
    assert move_mouse.call_args_list == [call(20, 20), call(20, 20)]


def test_capture_target_routes_both_firmware_screenshot_actions(tmp_path) -> None:
    """
    Both firmware screenshot targets use the firmware-specific capture routine.

    GIVEN: Normal and progress firmware screenshot targets.
    WHEN: The screenshot dispatcher handles both targets.
    THEN: The firmware capture receives the matching progress setting.
    """
    args = argparse.Namespace(delay=0.0, padding=0, vehicle_dir=tmp_path)

    with patch.object(screenshot_generator, "_capture_firmware_upload") as capture:
        screenshot_generator.capture_target(
            screenshot_generator.CaptureTarget("firmware.png", "firmware_upload"), tmp_path / "firmware.png", args
        )
        screenshot_generator.capture_target(
            screenshot_generator.CaptureTarget("progress.png", "firmware_upload_progress"), tmp_path / "progress.png", args
        )

    assert capture.call_args_list == [
        call(
            tmp_path / "firmware.png",
            0.0,
            0,
            show_progress=False,
        ),
        call(
            tmp_path / "progress.png",
            0.0,
            0,
            show_progress=True,
        ),
    ]


def test_cleanup_plugin_view_ignores_non_callable_optional_hook() -> None:
    """Cleanup must not call an attribute that only happens to use the hook name."""
    destroy = MagicMock()
    plugin_view = SimpleNamespace(on_deactivate="not callable", destroy=destroy)

    screenshot_generator._cleanup_plugin_view(plugin_view)

    destroy.assert_called_once_with()


def test_screenshot_window_uses_native_windows_application_icon() -> None:
    """Screenshot windows use the AMC .ico instead of Python's default process icon."""
    window = MagicMock()

    with patch.object(screenshot_generator.platform, "system", return_value="Windows"):
        screenshot_generator._set_windows_application_icon(window)

    window.winfo_toplevel.assert_called_once_with()
    window.winfo_toplevel.return_value.iconbitmap.assert_called_once_with(
        default=str(screenshot_generator.WINDOWS_APPLICATION_ICON_PATH)
    )


def test_screenshot_generator_can_select_individual_targets(tmp_path) -> None:
    """The CLI selection limits generation to the requested screenshot target."""
    args = argparse.Namespace(
        images_dir=tmp_path,
        vehicle_dir=tmp_path,
        delay=0.0,
        padding=0,
        overwrite=False,
        log_level="WARNING",
        screenshots=["App_screenshot_Parameter_export.png"],
    )

    with (
        patch.object(screenshot_generator, "parse_args", return_value=args),
        patch.object(screenshot_generator, "configure_logging"),
        patch.object(screenshot_generator, "register_plugins"),
        patch.object(screenshot_generator, "capture_target") as capture,
    ):
        assert screenshot_generator.main() == 0

    assert capture.call_count == 1
    assert capture.call_args.args[0].action == "parameter_export"


def test_screenshot_alias_uses_png_suffix_for_new_captures(tmp_path) -> None:
    """The historical screenshot alias is copied from the correctly named new image."""
    args = argparse.Namespace(
        images_dir=tmp_path,
        vehicle_dir=tmp_path,
        delay=0.0,
        padding=0,
        overwrite=False,
        log_level="WARNING",
        screenshots=["App_screenshot_Parameter_file_editor_and_uploader4.png"],
    )

    def capture(_target: object, output_path: Path, _args: argparse.Namespace) -> None:
        output_path.write_bytes(b"screenshot")

    with (
        patch.object(screenshot_generator, "parse_args", return_value=args),
        patch.object(screenshot_generator, "configure_logging"),
        patch.object(screenshot_generator, "register_plugins"),
        patch.object(screenshot_generator, "capture_target", side_effect=capture),
    ):
        assert screenshot_generator.main() == 0

    source = tmp_path / "App_screenshot_Parameter_file_editor_and_uploader4.png.new.png"
    alias = tmp_path / "App_screenshot1.png.new.png"
    assert source.read_bytes() == b"screenshot"
    assert alias.read_bytes() == b"screenshot"


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
        patch.object(screenshot_generator.ProgramSettings, "_user_config_dir", return_value=str(tmp_path)),
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
    assert fake_flight_controller.get_battery_statuses.return_value == (None, "")
    fake_factory.create_model.assert_called_once()
    model_context = fake_factory.create_model.call_args.args[1]
    assert fake_factory.create_model.call_args.args[0] == PLUGIN_MOTOR_TEST
    assert model_context.flight_controller is fake_flight_controller
    fake_factory.create.assert_called_once_with(PLUGIN_MOTOR_TEST, fake_window.main_frame, fake_model, fake_window)
    fake_plugin_view.pack.assert_called_once_with(fill="both", expand=True)
    fake_flight_controller.disconnect.assert_called_once_with()
