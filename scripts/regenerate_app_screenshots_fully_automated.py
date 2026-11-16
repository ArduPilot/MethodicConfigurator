#!/usr/bin/env python3
"""
Fully automated regeneration of AMC application screenshots.

This script creates the screenshot windows from AMC symbols/classes directly and
captures them with pyautogui. It is non-interactive and intended for updating
images under the repository's images directory.

Usage:
    python scripts/regenerate_app_screenshots_fully_automated.py

To regenerate the MAVFTP screenshots only, add:
    --screenshots App_screenshot_MAVFTP_browser.png App_screenshot_MAVFTP_remote_panel.png

SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

from __future__ import annotations

import argparse
import logging
import os
import platform
import re
import shutil
import tempfile
import time
import tkinter as tk
import tkinter.font as tk_font
from contextlib import contextmanager
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from pathlib import Path
from tkinter import simpledialog, ttk
from typing import TYPE_CHECKING, cast
from unittest.mock import MagicMock, patch

import pyautogui
from PIL import Image, ImageDraw
from skybrush_log_analyzer.config import Config as SkybrushConfig

from ardupilot_methodic_configurator import _ as translate
from ardupilot_methodic_configurator import __version__
from ardupilot_methodic_configurator.__main__ import register_plugins
from ardupilot_methodic_configurator.backend_filesystem import LocalFilesystem
from ardupilot_methodic_configurator.backend_filesystem_program_settings import ProgramSettings
from ardupilot_methodic_configurator.backend_firmware_upload import FirmwareBoardInfo, FirmwareUploadService
from ardupilot_methodic_configurator.backend_flightcontroller import FlightController
from ardupilot_methodic_configurator.backend_flightcontroller_files import FlightControllerLogFile
from ardupilot_methodic_configurator.data_model_data_telemetry import (
    MessageRate,
    MessageSample,
    RadioSample,
    TelemetryState,
)
from ardupilot_methodic_configurator.data_model_firmware_catalog import FirmwareRelease
from ardupilot_methodic_configurator.data_model_firmware_upload import UploadStage
from ardupilot_methodic_configurator.data_model_par_dict import ParDict
from ardupilot_methodic_configurator.data_model_parameter_editor import ParameterEditor
from ardupilot_methodic_configurator.frontend_tkinter_about_popup_window import AboutWindow
from ardupilot_methodic_configurator.frontend_tkinter_base_window import BaseWindow
from ardupilot_methodic_configurator.frontend_tkinter_connection_selection import ConnectionSelectionWindow
from ardupilot_methodic_configurator.frontend_tkinter_fc_banner_window import FlightControllerBannerWindow
from ardupilot_methodic_configurator.frontend_tkinter_file_browser import FileBrowserWindow, _standalone_ui_services
from ardupilot_methodic_configurator.frontend_tkinter_firmware_upload import FirmwareUploadWindow
from ardupilot_methodic_configurator.frontend_tkinter_flightcontroller_info import FlightControllerInfoWindow
from ardupilot_methodic_configurator.frontend_tkinter_mavlink_inspector import MavlinkInspectorWindow
from ardupilot_methodic_configurator.frontend_tkinter_parameter_editor import ParameterEditorWindow
from ardupilot_methodic_configurator.frontend_tkinter_project_creator import VehicleProjectCreatorWindow
from ardupilot_methodic_configurator.frontend_tkinter_project_opener import VehicleProjectOpenerWindow
from ardupilot_methodic_configurator.frontend_tkinter_skybrush_log_analysis import FeedbackDialog, SkybrushLogAnalysisWindow
from ardupilot_methodic_configurator.frontend_tkinter_template_overview import TemplateOverviewWindow
from ardupilot_methodic_configurator.frontend_tkinter_usage_popup_windows import display_parameter_editor_usage_popup
from ardupilot_methodic_configurator.plugins.data_model_rc_calibration import RCCalibrationDataModel
from ardupilot_methodic_configurator.plugins.frontend_tkinter_rc_calibration import RCCalibrationView
from ardupilot_methodic_configurator.plugins.plugin_constants import PLUGIN_MOTOR_TEST, PLUGIN_RC_CALIBRATION
from ardupilot_methodic_configurator.plugins.plugin_factory import PluginModelContext, plugin_factory

if TYPE_CHECKING:
    from collections.abc import Callable, Generator, Iterator

ROOT_DIR = Path(__file__).resolve().parents[1]
IMAGES_DIR = ROOT_DIR / "images"
DEFAULT_VEHICLE_DIR = ROOT_DIR / "ardupilot_methodic_configurator" / "vehicle_templates" / "ArduCopter" / "empty_4.6.x"
WINDOWS_APPLICATION_ICON_PATH = ROOT_DIR / "windows" / "ardupilot_methodic_configurator.ico"


# pylint: disable=too-many-lines


@dataclass(frozen=True)
class CaptureTarget:
    """A screenshot file and capture callback key."""

    filename: str
    action: str
    scale: float = 1.0
    variant: str | None = None
    gui_complexity: str | None = None
    current_file: str | None = None


TARGETS: tuple[CaptureTarget, ...] = (
    CaptureTarget("App_screenshot_about.png", "about"),
    CaptureTarget("App_screenshot_FC_connection.png", "connection"),
    CaptureTarget("App_screenshot_FC_connection_add_another.png", "connection_add_another"),
    CaptureTarget("App_screenshot_FC_connection_no_connection.png", "connection_no_connection"),
    CaptureTarget("App_screenshot_FC_connection_udp_forwarding.png", "connection_udp_forwarding"),
    CaptureTarget("App_screenshot_FC_info_and_param_download.png", "fc_info"),
    CaptureTarget("App_screenshot_FC_banner.png", "fc_banner"),
    CaptureTarget("App_screenshot_instructions.png", "instructions"),
    CaptureTarget("App_screenshot_motor_test.png", "motor_test"),
    CaptureTarget("App_screenshot_rc_calibration.png", PLUGIN_RC_CALIBRATION),
    CaptureTarget("App_screenshot_Parameter_export.png", "parameter_export"),
    CaptureTarget("App_screenshot_MAVFTP_browser.png", "mavftp_browser"),
    CaptureTarget("App_screenshot_MAVFTP_remote_panel.png", "mavftp_remote_panel"),
    CaptureTarget("App_screenshot_MAVLink_inspector.png", "mavlink_inspector", variant="radio"),
    CaptureTarget("App_screenshot_MAVLink_inspector_no_radio.png", "mavlink_inspector", variant="no_radio"),
    CaptureTarget("App_screenshot_MAVLink_inspector_collapsed.png", "mavlink_inspector", variant="collapsed"),
    CaptureTarget("App_screenshot_Skybrush_log_analysis_login.png", "skybrush_log_analysis", scale=0.666, variant="login"),
    CaptureTarget("App_screenshot_Skybrush_log_analysis.png", "skybrush_log_analysis", scale=0.666, variant="results"),
    CaptureTarget("App_screenshot_Skybrush_log_analysis_feedback.png", "skybrush_log_analysis", variant="feedback"),
    CaptureTarget("App_screenshot_Firmware_upload.png", "firmware_upload"),
    CaptureTarget("App_screenshot_Firmware_upload_progress.png", "firmware_upload_progress"),
    CaptureTarget(
        "App_screenshot_Parameter_file_editor_and_uploader4_4_simple.png",
        "param_04_simple",
        scale=0.666,
        gui_complexity="simple",
        current_file="05_board_orientation.param",
    ),
    CaptureTarget(
        "App_screenshot_Parameter_file_editor_and_uploader4_4.png",
        "param_04_normal",
        scale=0.666,
        gui_complexity="normal",
        current_file="05_board_orientation.param",
    ),
    CaptureTarget(
        "App_screenshot_Parameter_file_editor_and_uploader4.png",
        "param_20_normal",
        scale=0.666,
        gui_complexity="normal",
        current_file="24_throttle_controller.param",
    ),
    CaptureTarget("App_screenshot_Vehicle_directory.png", "vehicle_opener"),
    CaptureTarget("App_screenshot_Vehicle_directory10.png", "vehicle_opener"),
    CaptureTarget("App_screenshot_Vehicle_directory_create_from_template.png", "vehicle_opener_from_template", scale=0.8),
    CaptureTarget(
        "App_screenshot_Vehicle_directory_create_from_flight_controller.png",
        "vehicle_opener_from_flight_controller",
        scale=0.8,
    ),
    CaptureTarget("App_screenshot_Vehicle_directory_create_from_bin.png", "vehicle_opener_from_bin", scale=0.8),
    CaptureTarget("App_screenshot_Vehicle_directory4.png", "vehicle_opener_legacy4", scale=0.8),
    CaptureTarget("App_screenshot_Vehicle_directory11.png", "vehicle_creator"),
    CaptureTarget(
        "App_screenshot_Vehicle_directory_create_from_flight_controller_creator.png",
        "vehicle_creator_from_flight_controller",
        scale=0.8,
    ),
    CaptureTarget(
        "App_screenshot_Vehicle_directory_create_from_template_source.png",
        "create_from_template_source",
        scale=0.8,
        variant="create_from_template_source",
    ),
    CaptureTarget(
        "App_screenshot_Vehicle_directory_create_from_template_name.png",
        "create_from_template_name",
        scale=0.8,
        variant="create_from_template_name",
    ),
    CaptureTarget(
        "App_screenshot_Vehicle_directory_create_from_template_create.png",
        "create_from_template_create",
        scale=0.8,
        variant="create_from_template_create",
    ),
    CaptureTarget(
        "App_screenshot_Vehicle_directory_vehicle_params0.png",
        "vehicle_creator_params0",
        scale=0.8,
        variant="from_configured_source",
    ),
    CaptureTarget("App_screenshot_Vehicle_overview.png", "template_overview"),
    CaptureTarget(
        "App_screenshot1.png",
        "param_20_normal",
        scale=0.666,
        gui_complexity="normal",
        current_file="24_throttle_controller.param",
    ),
)


class FakeConnectionFlightController:
    """Minimal flight controller API for ConnectionSelectionWindow."""

    def __init__(self) -> None:
        self.comport = None
        self.master = None

    def discover_connections(
        self,
        progress_callback: Callable[..., object] | None = None,
        preserved_connections: list[str] | None = None,
    ) -> None:
        del progress_callback, preserved_connections

    def get_connection_tuples(self) -> list[tuple[str, str]]:
        return [("/dev/ttyUSB0", "/dev/ttyUSB0"), ("Add another", "Add another")]

    def connect(
        self,
        selected_connection: str = "",
        progress_callback: Callable[..., object] | None = None,
        baudrate: int = 115200,
    ) -> str:
        del selected_connection, progress_callback, baudrate
        return ""

    def disconnect(self) -> None:
        return

    def add_connection(self, _connection: str) -> None:
        return


class FakeInfoForFlightControllerInfo:
    """Minimal FC info provider for FlightControllerInfoWindow."""

    def get_info(self) -> dict[str, str]:
        return {
            "Vendor": "Hex (0x2DAE)",
            "Product": "CubeBlack (0x1011)",
            "Hardware Version": "589824",
            "Autopilot Type": "ArduPilot - Plane/Copter/Rover/Sub/Tracker",
            "ArduPilot FW": "4.6.3",
            "MAV Type": "Quadrotor",
            "Firmware Version": "4.6.3",
            "Git Hash": "deadbeef",
            "OS Git Hash": "feedface",
            "Capabilities": "MISSION_FLOAT, PARAM_FLOAT",
            "System ID": "1",
            "Component ID": "1",
        }

    def format_display_value(self, value: str) -> str:
        return value

    def log_flight_controller_info(self) -> None:
        return


class FakeFlightControllerForInfoWindow:  # pylint: disable=too-few-public-methods
    """Minimal flight controller API for FlightControllerInfoWindow."""

    def __init__(self) -> None:
        self.info = FakeInfoForFlightControllerInfo()
        self.fc_parameters: dict[str, float] = {}
        self.master = object()

    def download_params(
        self,
        progress_callback: Callable[[int, int], None] | None,
        _complete_path: Path,
        _default_path: Path,
    ) -> tuple[dict[str, float], ParDict]:
        if progress_callback is not None:
            progress_callback(900, 999)
        return {}, ParDict()


class FakeProjectManager:
    """Minimal project manager API for opener/creator windows."""

    def __init__(
        self,
        template_dir: Path,
        base_dir: Path,
        vehicle_dir: Path,
        fc_connected: bool = False,
        fc_parameters: dict[str, float] | None = None,
    ) -> None:
        self._template_dir = str(template_dir)
        self._base_dir = str(base_dir)
        self._vehicle_dir = str(vehicle_dir)
        self._fc_connected = fc_connected
        self._fc_parameters = fc_parameters or {}

    def get_introduction_message(self) -> str:
        return "No intermediate parameter files found\nin current working directory."

    def get_recently_used_dirs(self) -> tuple[str, str, str]:
        return self._template_dir, self._base_dir, self._vehicle_dir

    def get_fc_default_template_dir(self) -> str:
        return self._template_dir

    def get_recent_vehicle_dirs(self) -> list[str]:
        return [self._vehicle_dir]

    def open_vehicle_directory(self, vehicle_dir: str) -> str:
        return vehicle_dir

    def open_last_vehicle_directory(self, vehicle_dir: str) -> str:
        return vehicle_dir

    def create_new_vehicle_from_template(
        self,
        _template_dir: str,
        base_dir: str,
        name: str,
        _settings: object,
    ) -> str:
        return str(Path(base_dir) / name)

    def is_flight_controller_connected(self) -> bool:
        return self._fc_connected

    def fc_parameters(self) -> dict[str, float]:
        return self._fc_parameters

    def get_default_vehicle_name(self) -> str:
        return "MyVehicleName"

    def get_vehicle_type(self) -> str:
        return "ArduCopter"


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="Fully automated AMC screenshot regeneration")
    parser.add_argument("--images-dir", type=Path, default=IMAGES_DIR, help="Output images directory")
    parser.add_argument(
        "--vehicle-dir",
        type=Path,
        default=DEFAULT_VEHICLE_DIR,
        help="Vehicle template dir for editor shots",
    )
    parser.add_argument("--delay", type=float, default=0.2, help="Delay before capture in seconds")
    parser.add_argument("--padding", type=int, default=0, help="Capture padding in pixels")
    parser.add_argument(
        "--screenshots",
        nargs="+",
        choices=[target.filename for target in TARGETS],
        metavar="FILENAME",
        help="Screenshot filenames to regenerate (default: all screenshots)",
    )
    parser.add_argument("--overwrite", action="store_true", help="Overwrite existing files")
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging level",
    )
    return parser.parse_args()


def configure_logging(level: str) -> None:
    """Configure script logging."""
    logging.basicConfig(level=getattr(logging, level), format="%(levelname)s: %(message)s")


def settle_tk(widget: tk.Misc, cycles: int = 4, delay: float = 0.05) -> None:
    """Allow Tk layout/events to settle before capture."""
    for _ in range(cycles):
        widget.update_idletasks()
        widget.update()
        time.sleep(delay)


def _parse_wm_geometry(widget: tk.Misc) -> tuple[int, int, int, int] | None:
    """Parse wm geometry as (x, y, width, height) in screen coordinates."""
    if not isinstance(widget, (tk.Tk, tk.Toplevel)):
        return None

    geometry = widget.wm_geometry()
    match = re.match(r"^(\d+)x(\d+)([+-]\d+)([+-]\d+)$", geometry)
    if match is None:
        return None

    width = int(match.group(1))
    height = int(match.group(2))
    x = int(match.group(3))
    y = int(match.group(4))

    # Negative coordinates are relative to right/bottom screen edges.
    if x < 0:
        x = widget.winfo_screenwidth() + x - width
    if y < 0:
        y = widget.winfo_screenheight() + y - height

    return x, y, width, height


def _iter_descendants(widget: tk.Misc) -> Iterator[tk.Misc]:
    """Yield widget and all descendants."""
    yield widget
    for child in widget.winfo_children():
        yield from _iter_descendants(child)


def _widget_text(widget: tk.Misc) -> str:
    """Get widget text when available."""
    try:
        text = widget.cget("text")
    except tk.TclError:
        return ""
    return str(text)


def _set_windows_application_icon(widget: tk.Misc) -> None:
    """Use the native AMC icon for screenshot windows on Windows."""
    if platform.system() != "Windows" or not WINDOWS_APPLICATION_ICON_PATH.is_file():
        return

    window = widget if isinstance(widget, (tk.Tk, tk.Toplevel)) else widget.winfo_toplevel()
    try:
        window.iconbitmap(default=str(WINDOWS_APPLICATION_ICON_PATH))
    except (OSError, tk.TclError) as exc:
        logging.debug("Could not set the Windows application icon: %s", exc)


def _find_descendant(widget: tk.Misc, predicate: Callable[[tk.Misc], bool]) -> tk.Misc | None:
    """Return first descendant matching predicate."""
    for candidate in _iter_descendants(widget):
        if predicate(candidate):
            return candidate
    return None


def _required_widget_box(
    parent: tk.Misc,
    predicate: Callable[[tk.Misc], bool],
    error_msg: str,
) -> tuple[int, int, int, int]:
    """Find the first matching descendant and return its screen-space bounding box."""
    widget = _find_descendant(parent, predicate)
    if widget is None:
        raise RuntimeError(error_msg)
    return _widget_screen_box(widget, margin=2)


def _press_no_on_fc_copy_prompt(root: tk.Tk) -> None:
    """Dismiss the file-24 FC-copy prompt by choosing its No button."""
    prompt_title = translate("Update file with values from FC?")
    for child in root.winfo_children():
        if not isinstance(child, tk.Toplevel) or not child.winfo_exists():
            continue
        if child.title() != prompt_title:
            continue
        no_button = _find_descendant(child, lambda widget: _widget_text(widget) == translate("No"))
        if no_button is not None:
            no_button.invoke()
        return


def _widget_screen_box(widget: tk.Misc, margin: int = 2) -> tuple[int, int, int, int]:
    """Return widget bounds in screen coordinates as (left, top, right, bottom)."""
    left = max(widget.winfo_rootx() - margin, 0)
    top = max(widget.winfo_rooty() - margin, 0)
    right = max(left + widget.winfo_width() + (margin * 2), left + 1)
    bottom = max(top + widget.winfo_height() + (margin * 2), top + 1)
    return left, top, right, bottom


def _entry_text_screen_box(  # pylint: disable=too-many-locals
    entry: tk.Misc, text: str, margin: int = 2
) -> tuple[int, int, int, int]:
    """Return a bounding box tightly around visible entry text in screen coordinates."""
    try:
        font_name = str(entry.cget("font"))
        font = tk_font.nametofont(font_name)
    except tk.TclError:
        font = tk_font.nametofont("TkDefaultFont")

    text_width_px = max(font.measure(text.strip() or "X"), 8)
    widget_left = entry.winfo_rootx()
    widget_top = entry.winfo_rooty()
    widget_width = max(entry.winfo_width(), 1)
    widget_height = max(entry.winfo_height(), 1)

    text_left = widget_left + 4
    text_right = min(text_left + text_width_px + 8, widget_left + widget_width - 2)

    left = max(text_left - margin, 0)
    top = max(widget_top - margin, 0)
    right = max(text_right + margin, left + 1)
    bottom = max(widget_top + widget_height + margin, top + 1)
    return left, top, right, bottom


def _compute_capture_region(  # pylint: disable=too-many-locals
    widget: tk.Misc, padding: int
) -> tuple[int, int, int, int]:
    """Compute screenshot region in screen coordinates."""
    inner_x = widget.winfo_rootx()
    inner_y = widget.winfo_rooty()
    inner_width = widget.winfo_width()
    inner_height = widget.winfo_height()

    x = inner_x
    y = inner_y
    width = inner_width
    height = inner_height

    if isinstance(widget, (tk.Tk, tk.Toplevel)):
        # Use WM geometry for top-left screen coordinates, then inflate for decorations.
        outer_geometry = _parse_wm_geometry(widget)
        if outer_geometry is not None:
            outer_x, outer_y, outer_w, outer_h = outer_geometry
            left_frame = max(inner_x - outer_x, 0)
            title_bar = max(inner_y - outer_y, 0)

            # Derive right/bottom from geometry when possible; fall back to symmetric borders.
            right_frame = max(outer_w - left_frame - inner_width, 0)
            bottom_frame = max(outer_h - title_bar - inner_height, 0)
            right_frame = max(right_frame, left_frame)
            bottom_frame = max(bottom_frame, left_frame)

            x = outer_x
            y = outer_y
            width = max(outer_w, inner_width + left_frame + right_frame)
            height = max(outer_h, inner_height + title_bar + bottom_frame)
        else:
            # Fallback: conservative frame/title allowance when WM geometry is unavailable.
            border = 8
            title = 32
            x = max(inner_x - border, 0)
            y = max(inner_y - title, 0)
            width = inner_width + (border * 2)
            height = inner_height + title + border

    x = max(x - padding, 0)
    y = max(y - padding, 0)
    width = max(width + (padding * 2), 1)
    height = max(height + (padding * 2), 1)
    return x, y, width, height


def capture_widget(  # pylint: disable=too-many-arguments, too-many-positional-arguments, too-many-locals
    widget: tk.Misc,
    output_path: Path,
    delay: float,
    padding: int = 0,
    scale: float = 1.0,
    highlight_boxes: list[tuple[int, int, int, int]] | None = None,
    trim_windows_frame: bool = True,
) -> None:
    """Capture screenshot of a Tk widget region."""
    _set_windows_application_icon(widget)
    settle_tk(widget)
    if delay > 0:
        time.sleep(delay)

    x, y, width, height = _compute_capture_region(widget, padding)

    image = pyautogui.screenshot(region=(x, y, width, height))
    if highlight_boxes:
        draw = ImageDraw.Draw(image)
        for left, top, right, bottom in highlight_boxes:
            rel_left = max(left - x, 0)
            rel_top = max(top - y, 0)
            rel_right = min(right - x, image.width - 1)
            rel_bottom = min(bottom - y, image.height - 1)
            if rel_right > rel_left and rel_bottom > rel_top:
                draw.rectangle((rel_left, rel_top, rel_right, rel_bottom), outline="red", width=3)

    # Remove the Windows shadow while retaining the title bar and all client pixels.
    if platform.system() == "Windows" and trim_windows_frame and isinstance(widget, (tk.Tk, tk.Toplevel)):
        left = max(widget.winfo_rootx() - x - padding, 0)
        right = min(widget.winfo_rootx() - x + widget.winfo_width() + padding, image.width)
        bottom = min(widget.winfo_rooty() - y + widget.winfo_height() + padding, image.height)
        image = image.crop((left, 0, right, bottom))
        if padding == 0:
            image = image.convert("RGBA")
            mask = Image.new("L", image.size, 0)
            ImageDraw.Draw(mask).rounded_rectangle((0, 0, image.width - 1, image.height - 1), radius=8, fill=255)
            image.putalpha(mask)

    if scale != 1.0:
        new_size = (round(image.width * scale), round(image.height * scale))
        image = image.resize(new_size, Image.Resampling.LANCZOS)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    image.save(output_path)
    logging.info("Saved %s", output_path)


@contextmanager
def hidden_root() -> Generator[tk.Tk, None, None]:
    """Create a hidden root and always clean it up."""
    root = tk.Tk()
    root.withdraw()
    try:
        yield root
    finally:
        if root.winfo_exists():
            root.destroy()


def _capture_about(output_path: Path, delay: float, padding: int) -> None:
    with hidden_root() as root:
        AboutWindow(root, __version__)
        about_window = next(child for child in root.winfo_children() if isinstance(child, tk.Toplevel))
        capture_widget(about_window, output_path, delay, padding)
        about_window.destroy()


def _capture_connection(output_path: Path, delay: float, padding: int, *, highlight_skip: bool = False) -> None:
    flight_controller = FakeConnectionFlightController()
    window = ConnectionSelectionWindow(
        cast("FlightController", flight_controller),
        "No ArduPilot flight controller was auto-detected yet.",
    )
    try:
        window.root.attributes("-topmost", 1)
        window.root.geometry("+100+100")
        window.root.lift()
        pyautogui.moveTo(20, 20)
        settle_tk(window.root)
        highlight_boxes = None
        if highlight_skip:
            highlight_boxes = [
                _required_widget_box(
                    window.root,
                    lambda widget: _widget_text(widget) == translate("Skip FC connection, just edit the .param files on disk"),
                    "Could not find the skip connection button",
                )
            ]
        capture_widget(window.root, output_path, delay, padding, highlight_boxes=highlight_boxes)
    finally:
        if hasattr(window, "connection_selection_widgets"):
            window.connection_selection_widgets.stop_periodic_refresh()
        if window.root.winfo_exists():
            window.root.destroy()


def _capture_connection_forwarding(output_path: Path, delay: float, padding: int, show_dialog: bool) -> None:
    """Capture the real custom-connection workflow without connecting or saving settings."""
    window = ConnectionSelectionWindow(
        cast("FlightController", FakeConnectionFlightController()),
        "No ArduPilot flight controller was auto-detected yet.",
    )
    widgets = window.connection_selection_widgets
    window.root.attributes("-topmost", 1)
    window.root.geometry("+100+100")
    window.root.lift()
    widgets.stop_periodic_refresh()
    widgets.conn_selection_combobox.set("Add another")
    settle_tk(window.root)
    try:
        if not show_dialog:
            capture_widget(
                window.root,
                output_path,
                delay,
                padding,
                highlight_boxes=[_widget_screen_box(widgets.conn_selection_combobox)],
            )
            return

        capture_error: Exception | None = None

        def capture_dialog() -> None:
            """Capture and cancel the real Tk dialog before any external side effects."""
            nonlocal capture_error
            dialog: simpledialog.Dialog | None = None
            try:
                dialog = next(child for child in window.root.winfo_children() if isinstance(child, simpledialog.Dialog))
                dialog.attributes("-topmost", 1)
                dialog.geometry("+150+150")
                dialog.lift()
                capture_widget(dialog, output_path, delay, padding)
            # Tk callbacks otherwise swallow exceptions, so capture and re-raise the callback error.
            except Exception as error:  # pylint: disable=broad-exception-caught
                capture_error = error
            finally:
                if dialog is not None:
                    dialog.cancel()

        askstring = simpledialog.askstring

        def ask_forwarding_connection(title: str, prompt: str) -> str | None:
            """Supply documentation text to the production dialog."""
            window.root.after(250, capture_dialog)
            return askstring(title, prompt, parent=window.root, initialvalue="udpin:0.0.0.0:14600")

        with patch(
            "ardupilot_methodic_configurator.frontend_tkinter_connection_selection.simpledialog.askstring",
            side_effect=ask_forwarding_connection,
        ):
            widgets.add_connection()
        if capture_error is not None:
            raise capture_error
    finally:
        widgets.stop_periodic_refresh()
        if window.root.winfo_exists():
            window.root.destroy()


class _MavftpScreenshotEditor:
    """Provide representative local and remote files without a flight controller."""

    is_fc_connected = True
    is_mavftp_supported = True

    def __init__(self, local_directory: Path) -> None:
        self.local_directory = local_directory

    def get_vehicle_directory(self) -> str:
        return str(self.local_directory)

    @staticmethod
    def get_remote_files(directory: str) -> list[FlightControllerLogFile]:
        listings = {
            "/APM/LOGS": [
                FlightControllerLogFile("00000157.BIN", "/APM/LOGS/00000157.BIN", 4_820_992, modified_at=1788450300),
                FlightControllerLogFile("00000158.BIN", "/APM/LOGS/00000158.BIN", 1_284_096, modified_at=1788461100),
                FlightControllerLogFile("mission-notes.txt", "/APM/LOGS/mission-notes.txt", 1_284, modified_at=1788461700),
                FlightControllerLogFile("archive", "/APM/LOGS/archive", 0, is_directory=True, modified_at=1788379200),
            ],
            "/APM": [
                FlightControllerLogFile("LOGS", "/APM/LOGS", 0, is_directory=True, modified_at=1788461700),
                FlightControllerLogFile("PARAMS", "/APM/PARAMS", 0, is_directory=True, modified_at=1788379200),
            ],
            "/": [FlightControllerLogFile("APM", "/APM", 0, is_directory=True, modified_at=1788461700)],
        }
        return listings.get(directory.rstrip("/") or "/", [])


class _MavftpScreenshotWindow(FileBrowserWindow):
    """Keep displayed modification times consistent across host time zones."""

    @staticmethod
    def _format_modified_time(timestamp: float | None, *, unsupported_when_missing: bool = False) -> str:
        if timestamp is None:
            return "Unsupported" if unsupported_when_missing else ""
        if timestamp <= 0:
            return "-"
        try:
            return datetime.fromtimestamp(timestamp, tz=UTC).strftime("%Y-%m-%d %H:%M")
        except (OverflowError, OSError, ValueError):
            return "-"


def _capture_mavftp(output_path: Path, delay: float, padding: int, *, remote_panel: bool) -> None:
    """Capture the file browser with isolated, representative fixture files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        local_directory = Path(tmpdir) / "ExampleVehicle"
        local_directory.mkdir()
        (local_directory / "analysis.csv").write_text("time,value\n0,1\n", encoding="utf-8", newline="\n")
        (local_directory / "README.txt").write_text(
            "Files copied from the flight controller.\n", encoding="utf-8", newline="\n"
        )
        (local_directory / "flight-photos").mkdir()
        for path in local_directory.iterdir():
            os.utime(path, (1_788_461_700, 1_788_461_700))

        window = _MavftpScreenshotWindow(
            None, cast("ParameterEditor", _MavftpScreenshotEditor(local_directory)), _standalone_ui_services()
        )
        try:
            window.root.attributes("-topmost", 1)
            window.root.geometry("+100+100")
            window.root.lift()
            pyautogui.moveTo(20, 20)
            deadline = time.monotonic() + 5.0
            while (not window.remote_entries or not window.local_entries) and time.monotonic() < deadline:
                window.root.update()
                time.sleep(0.05)
            if not window.remote_entries or not window.local_entries:
                msg = "The example file browser listings did not populate before the timeout"
                raise RuntimeError(msg)

            display_directory = "ExampleVehicle"
            window.local_directory_var.set(display_directory)
            window.local_directory_label.configure(
                text=translate("Local files in {directory}").format(directory=display_directory)
            )
            settle_tk(window.root)
            capture_widget(window.main_frame, output_path, delay, padding, trim_windows_frame=False)
            if remote_panel:
                right = window.local_directory_label.winfo_rootx() - window.main_frame.winfo_rootx() + padding
                with Image.open(output_path) as captured:
                    cropped = captured.crop((0, 0, min(right, captured.width), captured.height))
                    cropped.save(output_path)
        finally:
            window.root.destroy()


def _capture_fc_info(output_path: Path, delay: float, padding: int, vehicle_dir: Path) -> None:
    fake_fc = FakeFlightControllerForInfoWindow()

    def _no_download(self: FlightControllerInfoWindow) -> None:
        self.progress_label.config(text="Downloaded 947 of 999 parameters")

    with (
        patch.object(tk.Tk, "mainloop", return_value=None),
        patch.object(FlightControllerInfoWindow, "_download_flight_controller_parameters", _no_download),
    ):
        window = FlightControllerInfoWindow(fake_fc, vehicle_dir)  # type: ignore[arg-type]
    try:
        capture_widget(window.root, output_path, delay, padding)
    finally:
        if window.root.winfo_exists():
            window.root.destroy()


def _capture_fc_banner(output_path: Path, delay: float, padding: int) -> None:
    """Capture the FC diagnostics window with illustrative banner, status and device data."""
    banner_text = [
        "ArduPilot V4.6.0 (a1b2c3d4)",
        "ChibiOS: 2026-06-18",
        "Free RAM: 123456",
        "Frame: QUAD/X",
    ]
    status_text = [
        "[2026-06-18 12:34:56] GPS 1: detected as u-blox",
        "[2026-06-18 12:34:57] EKF3 IMU0 is using GPS",
        "[2026-06-18 12:34:58] PreArm: Need Position Estimate",
    ]
    fc_parameters = {
        "BARO1_DEVID": 423937,
        "COMPASS_DEV_ID2": 423681,
        "COMPASS_PRIO1_ID": 423681,
        "INS_ACC2_ID": (52 << 16) | (1 << 8) | (3 << 3) | 2,
    }
    with hidden_root() as root:
        root.geometry("1x1+0+0")
        root.deiconify()
        window = FlightControllerBannerWindow(root, banner_text, status_text, fc_parameters)
        try:
            window.root.geometry("+100+80")
            window.root.attributes("-topmost", 1)
            window.root.lift()
            settle_tk(window.root)
            capture_widget(window.root, output_path, delay, padding)
        finally:
            if window.root.winfo_exists():
                window.root.destroy()


def _capture_instructions(output_path: Path, delay: float, padding: int) -> None:
    with hidden_root() as root:
        popup = display_parameter_editor_usage_popup(root)
        if popup is None:
            msg = "Could not create parameter editor usage popup window"
            raise RuntimeError(msg)
        capture_widget(popup.root, output_path, delay, padding)
        if popup.root.winfo_exists():
            popup.root.destroy()


def _capture_vehicle_opener(output_path: Path, delay: float, padding: int, vehicle_dir: Path) -> None:
    manager = FakeProjectManager(vehicle_dir, vehicle_dir.parent, vehicle_dir)
    window = VehicleProjectOpenerWindow(manager)  # type: ignore[arg-type]
    try:
        capture_widget(window.root, output_path, delay, padding)
    finally:
        if window.root.winfo_exists():
            window.root.destroy()


def _vehicle_opener_highlight_box(window: VehicleProjectOpenerWindow, action: str) -> tuple[int, int, int, int]:
    """Resolve a highlight box for a specific vehicle opener screenshot action."""
    if action == "vehicle_opener_legacy4":
        return _required_widget_box(
            window.connection_selection_widgets.container_frame,
            lambda w: _widget_text(w) == "...",
            "Could not find open vehicle browse button",
        )
    if action == "vehicle_opener_from_template":
        return _required_widget_box(
            window.main_frame,
            lambda w: _widget_text(w).startswith("Create a vehicle project from a template"),
            "Could not find create from template button",
        )
    if action == "vehicle_opener_from_flight_controller":
        return _required_widget_box(
            window.main_frame,
            lambda w: _widget_text(w).startswith("Create a vehicle project from an already configured flight controller"),
            "Could not find create from flight controller button",
        )
    if action == "vehicle_opener_from_bin":
        return _required_widget_box(
            window.main_frame,
            lambda w: _widget_text(w).startswith("Create a vehicle project from a .bin log file"),
            "Could not find create from bin button",
        )
    msg = f"Unsupported vehicle opener highlight action: {action}"
    raise RuntimeError(msg)


def _capture_vehicle_opener_with_highlight(  # pylint: disable=too-many-arguments, too-many-positional-arguments
    output_path: Path,
    delay: float,
    padding: int,
    vehicle_dir: Path,
    action: str = "vehicle_opener_legacy4",
    scale: float = 1.0,
    fc_connected: bool = False,
) -> None:
    fc_params = _load_fc_params_from_file(vehicle_dir) if fc_connected else None
    manager = FakeProjectManager(
        vehicle_dir,
        vehicle_dir.parent,
        vehicle_dir,
        fc_connected=fc_connected,
        fc_parameters=fc_params,
    )
    window = VehicleProjectOpenerWindow(manager)  # type: ignore[arg-type]
    try:
        settle_tk(window.root, cycles=6, delay=0.05)
        box = _vehicle_opener_highlight_box(window, action)
        capture_widget(window.root, output_path, delay, padding, scale=scale, highlight_boxes=[box])
    finally:
        if window.root.winfo_exists():
            window.root.destroy()


def _capture_vehicle_creator(output_path: Path, delay: float, padding: int, vehicle_dir: Path) -> None:
    manager = FakeProjectManager(vehicle_dir, vehicle_dir.parent, vehicle_dir)
    window = VehicleProjectCreatorWindow(manager)  # type: ignore[arg-type]
    try:
        capture_widget(window.root, output_path, delay, padding)
    finally:
        if window.root.winfo_exists():
            window.root.destroy()


def _create_vehicle_creator_window(
    vehicle_dir: Path, fc_connected: bool = False, from_flight_controller: bool = False
) -> VehicleProjectCreatorWindow:
    fc_params = _load_fc_params_from_file(vehicle_dir) if fc_connected else {}
    manager = FakeProjectManager(
        vehicle_dir,
        vehicle_dir.parent,
        vehicle_dir,
        fc_connected=fc_connected,
        fc_parameters=fc_params if fc_connected else None,
    )
    window = VehicleProjectCreatorWindow(manager, from_flight_controller=from_flight_controller)  # type: ignore[arg-type]
    settle_tk(window.root, cycles=6, delay=0.05)
    return window


def _capture_vehicle_creator_from_flight_controller(output_path: Path, delay: float, padding: int, vehicle_dir: Path) -> None:
    """Capture the minimal creator dialog for an already configured flight controller."""
    window = _create_vehicle_creator_window(vehicle_dir, fc_connected=True, from_flight_controller=True)
    try:
        capture_widget(window.root, output_path, delay, padding)
    finally:
        if window.root.winfo_exists():
            window.root.destroy()


def _find_template_browse_button(window: VehicleProjectCreatorWindow) -> tuple[int, int, int, int]:
    """Find and return bounding box for template browse button."""
    return _required_widget_box(
        window.template_dir.container_frame,
        lambda w: _widget_text(w) == "...",
        "Could not find source template browse button",
    )


def _find_name_entry(window: VehicleProjectCreatorWindow, use_text_box: bool = False) -> tuple[int, int, int, int]:
    """Find and return bounding box for vehicle name entry."""
    entry = _find_descendant(
        window.new_dir.container_frame,
        lambda w: w.winfo_class() in {"Entry", "TEntry"},
    )
    if entry is None:
        msg = "Could not find destination vehicle name entry"
        raise RuntimeError(msg)
    if use_text_box:
        return _entry_text_screen_box(entry, window.new_dir.get_selected_directory(), margin=2)
    return _widget_screen_box(entry, margin=2)


def _find_create_button(window: VehicleProjectCreatorWindow) -> tuple[int, int, int, int]:
    """Find and return bounding box for create vehicle directory button."""
    return _required_widget_box(
        window.main_frame,
        lambda w: _widget_text(w).startswith("Create a vehicle project from a template"),
        "Could not find create vehicle directory button",
    )


def _vehicle_creator_highlight_box(window: VehicleProjectCreatorWindow, variant: str) -> tuple[int, int, int, int]:  # pylint: disable=too-many-locals
    """Resolve a highlight box for a specific vehicle creator screenshot variant."""
    result: tuple[int, int, int, int] | None = None

    # Template source selection
    if variant in ("from_configured_source", "create_from_template_source"):
        result = _find_template_browse_button(window)
    # Vehicle name entry - without FC options
    elif variant == "create_from_template_name":
        result = _find_name_entry(window, use_text_box=False)
    # Vehicle name with text styling
    elif variant == "legacy2":
        result = _find_name_entry(window, use_text_box=True)
    # Create button - without FC options
    elif variant == "create_from_template_create":
        result = _find_create_button(window)
    else:
        # FC-dependent variants with options
        checkbox1 = window.new_project_settings_widgets.get("use_fc_params")
        checkbox2 = window.new_project_settings_widgets.get("infer_comp_specs_and_conn_from_fc_params")
        if checkbox1 is None or checkbox2 is None:
            msg = "Could not find 'use_fc_params' or 'infer_comp_specs_and_conn_from_fc_params' setting checkbox"
            raise RuntimeError(msg)

        if variant == "from_configured_options":
            # Tick both checkboxes
            checkbox1.invoke()
            checkbox2.invoke()
            # Get bounding boxes for both
            box1_left, box1_top, box1_right, box1_bottom = _widget_screen_box(checkbox1, margin=2)
            box2_left, box2_top, box2_right, box2_bottom = _widget_screen_box(checkbox2, margin=2)
            # Return combined bounding box encompassing both
            combined_left = min(box1_left, box2_left)
            combined_top = min(box1_top, box2_top)
            combined_right = max(box1_right, box2_right)
            combined_bottom = max(box1_bottom, box2_bottom)
            result = combined_left, combined_top, combined_right, combined_bottom
        elif variant == "from_configured_name":
            # Tick both checkboxes
            checkbox1.invoke()
            checkbox2.invoke()
            result = _find_name_entry(window, use_text_box=False)
        elif variant == "from_configured_create":
            # Tick both checkboxes
            checkbox1.invoke()
            checkbox2.invoke()
            result = _find_create_button(window)
        else:
            msg = f"Unsupported vehicle creator highlight variant: {variant}"
            raise RuntimeError(msg)

    return result


def _capture_vehicle_creator_with_highlight(  # pylint: disable=too-many-arguments, too-many-positional-arguments
    output_path: Path,
    delay: float,
    padding: int,
    vehicle_dir: Path,
    variant: str,
    scale: float = 1.0,
    fc_connected: bool = False,
) -> None:
    window = _create_vehicle_creator_window(vehicle_dir, fc_connected=fc_connected)
    try:
        box = _vehicle_creator_highlight_box(window, variant)
        capture_widget(window.root, output_path, delay, padding, scale=scale, highlight_boxes=[box])
    finally:
        if window.root.winfo_exists():
            window.root.destroy()


def _capture_template_overview(output_path: Path, delay: float, padding: int) -> None:
    with hidden_root() as root:
        window = TemplateOverviewWindow(root, connected_fc_vehicle_type="ArduCopter")
        items = window.tree.get_children()
        if items:
            item = items[min(15, len(items) - 1)]
            window.tree.selection_set(item)
            window.tree.focus(item)
            window.tree.see(item)
        capture_widget(window.root, output_path, delay, padding)
        if window.root.winfo_exists():
            window.root.destroy()


def _load_fc_params_from_file(vehicle_dir: Path) -> dict[str, float]:
    """Load default parameter values from 00_default.param as a flat {name: float} dict."""
    default_param_file = vehicle_dir / "00_default.param"
    if not default_param_file.exists():
        return {}
    pardict = ParDict.load_param_file_into_dict(str(default_param_file))
    return {name: param.value for name, param in pardict.items()}


def _configure_fake_flight_controller(flight_controller: FlightController, fc_params: dict[str, float]) -> None:
    """Configure a connected, non-blocking FC double for screenshot-only GUI workflows."""
    flight_controller.set_master_for_testing(MagicMock())
    flight_controller.fc_parameters = fc_params
    flight_controller.request_scaled_imu_messages = MagicMock(return_value=(True, ""))
    flight_controller.poll_scaled_imu = MagicMock(return_value=None)
    flight_controller.request_periodic_battery_status = MagicMock(return_value=(True, ""))
    flight_controller.get_battery_statuses = MagicMock(return_value=(None, ""))


def _cleanup_plugin_view(plugin_view: object) -> None:
    """Call optional plugin cleanup hooks on a dynamically-created view."""
    on_deactivate = getattr(plugin_view, "on_deactivate", None)
    if callable(on_deactivate):
        on_deactivate()
    destroy = getattr(plugin_view, "destroy", None)
    if callable(destroy):
        destroy()


def _build_parameter_editor(
    current_file: str,
    vehicle_dir: Path,
    gui_complexity: str,
) -> tuple[ParameterEditorWindow, FlightController]:
    # Save prior settings to restore afterward and avoid persistent side effects.
    prev_gui_complexity = ProgramSettings.get_setting("gui_complexity")
    prev_usage_popup = ProgramSettings.get_setting("display_usage_popup/parameter_editor")

    ProgramSettings.set_setting("gui_complexity", gui_complexity)
    ProgramSettings.set_display_usage_popup("parameter_editor", value=False)

    fc_params = _load_fc_params_from_file(vehicle_dir)

    filesystem = LocalFilesystem(
        str(vehicle_dir),
        "ArduCopter",
        "4.6.3",
        allow_editing_template_files=True,
        save_component_to_system_templates=False,
    )
    flight_controller = FlightController()

    # Fake an FC connection so the table renders FC values instead of "N/A".
    # Stub telemetry requests as well, because plugin activation runs during Tk event settling.
    _configure_fake_flight_controller(flight_controller, fc_params)

    # Patch download_params so the window startup download returns our fake data
    # without attempting any real MAVLink communication.
    try:
        with (
            patch.object(
                FlightController,
                "download_params",
                return_value=(fc_params, ParDict()),
            ),
            patch.object(ParameterEditor, "open_documentation_in_browser"),
        ):
            editor = ParameterEditor(current_file, flight_controller, filesystem)
            window = ParameterEditorWindow(editor)
            if current_file == "24_throttle_controller.param":
                # This step asks whether the FC values should be copied into the
                # file. Choose No before the startup workflow can block on it.
                # Leave enough time for the dialog to finish its own setup
                # (including focus_set()) before destroying it.
                window.root.after(500, lambda: _press_no_on_fc_copy_prompt(window.root))
            settle_tk(window.root, cycles=8, delay=0.05)
    finally:
        # Restore prior settings to avoid persistent side effects on the user's config.
        if prev_gui_complexity is not None:
            ProgramSettings.set_setting("gui_complexity", prev_gui_complexity)
        if prev_usage_popup is not None:
            ProgramSettings.set_display_usage_popup("parameter_editor", bool(prev_usage_popup))

    return window, flight_controller


def _capture_parameter_editor(  # pylint: disable=too-many-arguments, too-many-positional-arguments
    output_path: Path,
    delay: float,
    padding: int,
    vehicle_dir: Path,
    current_file: str,
    gui_complexity: str,
    scale: float = 1.0,
) -> None:
    # Use a temporary copy of the vehicle dir so LocalFilesystem cannot create
    # untracked files (e.g. apm.pdef.xml) in the repository working tree.
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_vehicle_dir = Path(tmpdir) / vehicle_dir.name
        shutil.copytree(vehicle_dir, tmp_vehicle_dir)
        window, flight_controller = _build_parameter_editor(current_file, tmp_vehicle_dir, gui_complexity)
        try:
            capture_widget(window.root, output_path, delay, padding, scale)
        finally:
            if window.current_plugin_view is not None:
                _cleanup_plugin_view(window.current_plugin_view)
            if window.root.winfo_exists():
                window.root.destroy()
            flight_controller.disconnect()


def _capture_parameter_export(  # pylint: disable=too-many-locals
    output_path: Path, delay: float, padding: int, vehicle_dir: Path
) -> None:
    """Capture the FC parameter export dialog with representative downloaded values."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_vehicle_dir = Path(tmpdir) / vehicle_dir.name
        shutil.copytree(vehicle_dir, tmp_vehicle_dir)
        editor_window, flight_controller = _build_parameter_editor(
            "05_board_orientation.param",
            tmp_vehicle_dir,
            "normal",
        )
        export_window = None
        try:
            fc_parameters = flight_controller.fc_parameters
            parameter_models = editor_window.parameter_editor.get_fc_parameters_for_export()
            non_default_names = ("WPNAV_SPEED", "ANGLE_MAX", "ATC_ANG_RLL_P")
            if not all(name in fc_parameters for name in non_default_names):
                msg = "The parameter export screenshot fixture is missing representative Copter parameters"
                raise RuntimeError(msg)
            fc_parameters["WPNAV_SPEED"] += 100.0
            fc_parameters["ANGLE_MAX"] = 3500.0
            fc_parameters["ATC_ANG_RLL_P"] = 4.7

            default_names = [
                name
                for name in ("RTL_ALT", "WPNAV_RADIUS")
                if name in parameter_models
                and parameter_models[name].fc_value_equals_default_value
                and not parameter_models[name].is_calibration
            ]
            default_names.extend(
                name
                for name, parameter in parameter_models.items()
                if len(default_names) < 2
                and name not in default_names
                and parameter.fc_value_equals_default_value
                and not parameter.is_calibration
                and not parameter.is_readonly
            )
            calibration_names = [
                name
                for name, parameter in parameter_models.items()
                if parameter.is_calibration and name.startswith(("COMPASS_", "INS_"))
            ]
            if len(calibration_names) < 2:
                calibration_names.extend(
                    name
                    for name, parameter in parameter_models.items()
                    if len(calibration_names) < 2 and name not in calibration_names and parameter.is_calibration
                )
            if len(default_names) < 2 or len(calibration_names) < 2:
                msg = "The parameter export screenshot fixture needs two default and two calibration parameters"
                raise RuntimeError(msg)

            selected_names = [*non_default_names, *default_names[:2], *calibration_names[:2]]
            selected_fc_parameters = {name: fc_parameters[name] for name in selected_names}
            fc_parameters.clear()
            fc_parameters.update(selected_fc_parameters)
            editor_window.on_export_parameters_click()
            export_window = next(
                (
                    child
                    for child in editor_window.root.winfo_children()
                    if isinstance(child, tk.Toplevel) and child.title() == translate("Export parameters")
                ),
                None,
            )
            if export_window is None:
                msg = "Could not find the parameter export window for the parameter export screenshot"
                raise RuntimeError(msg)
            for checkbox_label in ("Calibration", "Default value"):
                checkbox = _find_descendant(
                    export_window,
                    lambda widget, label=checkbox_label: (
                        isinstance(widget, (ttk.Checkbutton, tk.Checkbutton)) and _widget_text(widget) == translate(label)
                    ),
                )
                invoke = getattr(checkbox, "invoke", None)
                if not callable(invoke):
                    msg = f"Could not find the {checkbox_label} checkbox for the parameter export screenshot"
                    raise RuntimeError(msg)
                invoke()
            capture_widget(export_window, output_path, delay, padding)
        finally:
            if export_window is not None and export_window.winfo_exists():
                export_window.destroy()
            if editor_window.current_plugin_view is not None:
                _cleanup_plugin_view(editor_window.current_plugin_view)
            if editor_window.root.winfo_exists():
                editor_window.root.destroy()
            flight_controller.disconnect()


def _mavlink_inspector_state(*, with_radio: bool) -> TelemetryState:
    """Provide illustrative received values, independent of hardware or network access."""
    attitude_fields = (("roll", "0.01"), ("pitch", "0.02"), ("yaw", "1.57"), ("rollspeed", "0.0"))
    messages = [
        MessageRate((1, 1, name), MessageSample(count, count * 40, 120.0, fields), hz, rate, 0.1)
        for name, count, hz, rate, fields in (
            ("HEARTBEAT", 120, 1.0, 21.0, (("type", "2"), ("autopilot", "3"))),
            ("SYS_STATUS", 240, 2.0, 86.0, (("voltage_battery", "16800"),)),
            ("ATTITUDE", 1200, 10.0, 400.0, attitude_fields),
            ("GLOBAL_POSITION_INT", 240, 2.0, 84.0, (("relative_alt", "0"),)),
            ("VFR_HUD", 240, 2.0, 64.0, (("groundspeed", "0.0"),)),
        )
    ]
    radio = RadioSample((51, 68), 120.0, 160, 150, 50, 45, 90, 3, 12) if with_radio else None
    if radio is not None:
        messages.append(
            MessageRate(
                (51, 68, "RADIO_STATUS"),
                MessageSample(120, 2520, 120.0, (("rssi", "160"), ("remrssi", "150"), ("txbuf", "90"))),
                1.0,
                21.0,
                0.1,
            )
        )
    return TelemetryState(
        connected=True,
        receiving=True,
        rx_rate=685.0,
        tx_rate=35.0,
        parse_error_rate=0.0,
        radio_error_rate=0.0 if radio is not None else None,
        radio=radio,
        messages=tuple(messages),
    )


def _capture_mavlink_inspector(output_path: Path, delay: float, padding: int, variant: str) -> None:
    """Capture the actual inspector with and without modem reports, or with fields collapsed."""
    controller = MagicMock(spec=FlightController)
    controller.master = None
    with hidden_root() as root, patch.object(MavlinkInspectorWindow, "_poll"):
        window = MavlinkInspectorWindow(controller, root)
        try:
            window.root.geometry("+100+80")
            window.root.attributes("-topmost", 1)
            window.root.lift()
            window.refresh(_mavlink_inspector_state(with_radio=variant != "no_radio"))
            window.table.selection_set("1:1:ATTITUDE")
            window.table.event_generate("<<TreeviewSelect>>")
            settle_tk(window.root)
            if variant == "collapsed":
                window.message_contents.set_expanded(False)
            capture_widget(window.main_frame, output_path, delay, padding, trim_windows_frame=False)
        finally:
            window.close()


_SKYBRUSH_MODULE = "ardupilot_methodic_configurator.frontend_tkinter_skybrush_log_analysis"


def _skybrush_message(text: str, severity: str, **extra: object) -> dict[str, object]:
    """Build one illustrative Skybrush test-case message."""
    return {"text": text, "severity": severity, **extra}


def _skybrush_analysis_response() -> dict[str, object]:
    """Provide an illustrative raw Skybrush analysis response, independent of network access."""
    return {
        "test_results": [
            {
                "test_name": "paplan.tests.vibration",
                "status": "WARN",
                "title": "IMU vibration levels",
                "messages": [
                    _skybrush_message("Peak Z-axis vibration", "WARN", value=42.7, unit="m/s/s", timestamp=312.4),
                    _skybrush_message("Accelerometer clipping events", "INFO", value=3),
                ],
            },
            {
                "test_name": "paplan.tests.battery",
                "status": "PASS",
                "title": "Battery voltage sag",
                "messages": [_skybrush_message("Minimum cell voltage under load", "PASS", value=3.62, unit="V")],
            },
            {
                "test_name": "paplan.tests.gnss",
                "status": "PASS",
                "title": "GNSS reception quality",
                "messages": [_skybrush_message("Minimum number of satellites", "PASS", value=17)],
            },
            {
                "test_name": "paplan.tests.ekf",
                "status": "INFO",
                "title": "EKF innovations",
                "messages": [_skybrush_message("EKF lane switch", "INFO", timestamp=96.0)],
            },
            {
                "test_name": "paplan.tests.motor_balance",
                "status": "PASS",
                "title": "Motor output balance",
                "messages": [_skybrush_message("Maximum motor output spread", "PASS", value=8.5, unit="%")],
            },
            {"test_name": "paplan.tests.rtk", "status": "NOT_APPLICABLE", "title": "RTK fix quality"},
        ],
    }


class _SkybrushScreenshotClient:
    """Answer the Skybrush API calls locally, so no account, API key or network is needed."""

    def __init__(self, config: SkybrushConfig) -> None:
        self.config = config

    @staticmethod
    def version() -> dict[str, str]:
        return {"app_version": "1.0.0"}

    @staticmethod
    def analyze(_path: Path) -> dict[str, object]:
        return _skybrush_analysis_response()


def _wait_for_tk(root: tk.Misc, predicate: Callable[[], bool], error_msg: str, timeout: float = 5.0) -> None:
    """Process Tk events until the predicate holds, raising when it times out."""
    deadline = time.monotonic() + timeout
    while not predicate():
        if time.monotonic() > deadline:
            raise RuntimeError(error_msg)
        root.update()
        time.sleep(0.05)


def _fill_skybrush_feedback_dialog(dialog: tk.Toplevel) -> None:
    """Enter illustrative feedback into the dialog fields, without submitting it."""
    title_entry = _find_descendant(
        dialog, lambda widget: isinstance(widget, ttk.Entry) and not isinstance(widget, ttk.Combobox)
    )
    description_text = _find_descendant(dialog, lambda widget: isinstance(widget, tk.Text))
    category_box = _find_descendant(dialog, lambda widget: isinstance(widget, ttk.Combobox))
    if (
        not isinstance(title_entry, ttk.Entry)
        or not isinstance(description_text, tk.Text)
        or not isinstance(category_box, ttk.Combobox)
    ):
        msg = "Could not find the feedback dialog category, title and description fields"
        raise RuntimeError(msg)
    category_box.set("other")
    title_entry.insert(0, "Great log analysis")
    description_text.insert("1.0", "The Skybrush Log Analyzer works great, thank you! 👍")


def _capture_skybrush_log_analysis(  # pylint: disable=too-many-locals
    output_path: Path, delay: float, padding: int, variant: str, scale: float = 1.0
) -> None:
    """Capture the Skybrush log analysis window logged out, with results, or with the feedback dialog."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # An empty config directory yields the default service URLs without reading the user's API key.
        config_dir = Path(tmpdir) / "skybrush-log-analyzer"
        config_dir.mkdir()
        config = SkybrushConfig.load(config_dir=config_dir)
        if variant != "login":
            config = replace(config, api_key="screenshot-api-key")
        logfile = Path(tmpdir) / "00000158.BIN"
        logfile.write_bytes(b"\0")

        with (
            hidden_root() as root,
            patch(f"{_SKYBRUSH_MODULE}.Config.load", return_value=config),
            patch(f"{_SKYBRUSH_MODULE}.APIClient", _SkybrushScreenshotClient),
            patch.object(FeedbackDialog, "show"),
        ):
            window = SkybrushLogAnalysisWindow(root, str(logfile))
            try:
                # Set topmost first: on Windows it reverts a still-pending geometry change.
                window.root.attributes("-topmost", 1)
                window.root.geometry("+100+80")
                window.root.lift()
                pyautogui.moveTo(20, 20)  # Keep hover tooltips out of the documentation screenshots.
                header_text = (
                    translate("Skybrush API version: requires logging in")
                    if variant == "login"
                    else translate("Skybrush API version: {version}").format(version="1.0.0")
                )
                _wait_for_tk(
                    window.root,
                    lambda: _find_descendant(window.root, lambda widget: _widget_text(widget) == header_text) is not None,
                    "The Skybrush log analysis header did not show the API version before the timeout",
                )
                if variant == "login":
                    capture_widget(window.root, output_path, delay, padding, scale=scale)
                    return

                analyze_button = _find_descendant(window.root, lambda widget: _widget_text(widget) == translate("Analyze"))
                if not isinstance(analyze_button, ttk.Button):
                    msg = "Could not find the Skybrush Analyze button"
                    raise RuntimeError(msg)
                analyze_button.invoke()
                _wait_for_tk(
                    window.root,
                    lambda: _widget_text(window.status_label) == translate("Analysis completed"),
                    "The illustrative Skybrush analysis did not complete before the timeout",
                )
                if variant == "results":
                    capture_widget(window.root, output_path, delay, padding, scale=scale)
                    return

                feedback_button = _find_descendant(
                    window.root, lambda widget: _widget_text(widget) == translate("Send feedback")
                )
                if not isinstance(feedback_button, ttk.Button):
                    msg = "Could not find the Skybrush Send feedback button"
                    raise RuntimeError(msg)
                feedback_button.invoke()
                dialog = next(
                    (
                        child
                        for child in window.root.winfo_children()
                        if isinstance(child, tk.Toplevel) and child.title() == translate("Send feedback")
                    ),
                    None,
                )
                if dialog is None:
                    msg = "Could not find the Skybrush feedback dialog"
                    raise RuntimeError(msg)
                dialog.attributes("-topmost", 1)
                dialog.lift()
                dialog.focus_force()  # Show the dialog with an active title bar.
                _fill_skybrush_feedback_dialog(dialog)
                capture_widget(dialog, output_path, delay, padding, scale=scale)
            finally:
                if window.root.winfo_exists():
                    window.root.destroy()


def _capture_firmware_upload(output_path: Path, delay: float, padding: int, show_progress: bool) -> None:
    """Capture the real firmware UI with sample catalog data and no hardware or downloads."""
    controller = MagicMock(spec=FlightController)
    board = FirmwareBoardInfo(9, "CubeBlack", "/dev/ttyACM0", "Copter")
    release = FirmwareRelease(
        "Copter", "4.6.0", "OFFICIAL", "CubeBlack", "https://firmware.ardupilot.org/Copter/stable/CubeBlack/arducopter.apj", 9
    )
    with (
        patch.object(FirmwareUploadService, "connected_board_info", return_value=board),
        patch.object(FirmwareUploadWindow, "refresh_versions"),
    ):
        window = FirmwareUploadWindow(controller)
        try:
            window.events.put(("catalog", window.catalog_request_id, [release]))
            settle_tk(window.root)
            window.version.set(release.label)
            window.version_combo.event_generate("<<ComboboxSelected>>")
            if show_progress:
                window.busy = True
                window.uploading = True
                for button in (window.refresh_button, window.upload_button, window.custom_button):
                    button.configure(state="disabled")
                window.events.put(("progress", UploadStage.ERASING, 1, 1))
                window.events.put(("progress", UploadStage.PROGRAMMING, 65, 100))
            # Expand to the requested height so every action button is visible at this display's DPI.
            window.root.update_idletasks()
            window.root.geometry(f"{window.root.winfo_width()}x{window.root.winfo_reqheight()}")
            pyautogui.moveTo(20, 20)  # Keep hover tooltips out of the documentation screenshots.
            capture_widget(window.root, output_path, delay, padding)
        finally:
            window.uploading = False
            window.close()


def _capture_motor_test(output_path: Path, delay: float, padding: int, vehicle_dir: Path) -> None:
    fc_params = _load_fc_params_from_file(vehicle_dir)
    fc_params["FRAME_CLASS"] = 1.0
    fc_params["FRAME_TYPE"] = 1.0

    # Use a temporary copy of the vehicle dir so LocalFilesystem cannot create
    # untracked files (e.g. apm.pdef.xml) in the repository working tree.
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_vehicle_dir = Path(tmpdir) / vehicle_dir.name
        shutil.copytree(vehicle_dir, tmp_vehicle_dir)

        filesystem = LocalFilesystem(
            str(tmp_vehicle_dir),
            "ArduCopter",
            "4.6.3",
            allow_editing_template_files=True,
            save_component_to_system_templates=False,
        )
        flight_controller = FlightController()
        _configure_fake_flight_controller(flight_controller, fc_params)
        flight_controller.stop_all_motors = MagicMock(return_value=(True, ""))

        model = plugin_factory.create_model(
            PLUGIN_MOTOR_TEST,
            PluginModelContext(
                flight_controller=flight_controller,
                local_filesystem=filesystem,
                parameter_editor=cast("ParameterEditor", MagicMock()),
            ),
        )
        if model is None:
            msg = f"Could not create {PLUGIN_MOTOR_TEST} plugin model"
            raise RuntimeError(msg)

        window = BaseWindow()
        window.root.title(translate("ArduPilot Motor Test"))
        window.root.geometry(window.calculate_scaled_geometry(400, 610))
        plugin_view = plugin_factory.create(PLUGIN_MOTOR_TEST, window.main_frame, model, window)
        if plugin_view is None:
            window.root.destroy()
            msg = f"Could not create {PLUGIN_MOTOR_TEST} plugin view"
            raise RuntimeError(msg)
        plugin_view.pack(fill="both", expand=True)
        try:
            capture_widget(window.root, output_path, delay, padding)
        finally:
            _cleanup_plugin_view(plugin_view)
            window.root.destroy()
            flight_controller.disconnect()


def _capture_rc_calibration(output_path: Path, delay: float, padding: int) -> None:
    """Capture the registered RC calibration view with representative live channel input."""
    fc_params = {
        "RCMAP_ROLL": 1.0,
        "RCMAP_PITCH": 2.0,
        "RCMAP_THROTTLE": 3.0,
        "RCMAP_YAW": 4.0,
        "FLTMODE_CH": 5.0,
    }
    for channel_number in range(1, 17):
        fc_params.update(
            {
                f"RC{channel_number}_MIN": 1000.0,
                f"RC{channel_number}_MAX": 2000.0,
                f"RC{channel_number}_TRIM": 1500.0,
            }
        )

    flight_controller = FlightController()
    _configure_fake_flight_controller(flight_controller, fc_params)
    model = RCCalibrationDataModel(flight_controller)
    values = (1710, 1370, 1810, 1580, 1200, 1850, *([1500] * 10))
    channels = [{**channel, "value": value} for channel, value in zip(model.get_channel_calibration(), values, strict=True)]
    model.get_rc_telemetry = MagicMock(
        return_value={
            "roll": 420.0,
            "pitch": -260.0,
            "throttle": 620.0,
            "yaw": 180.0,
            "channels": channels,
        }
    )

    window = BaseWindow()
    window.root.title(translate("ArduPilot RC Calibration"))
    window.root.geometry("850x840")
    plugin_view = RCCalibrationView(window.main_frame, model, window)
    plugin_view.pack(fill="both", expand=True)
    try:
        capture_widget(window.root, output_path, delay, padding)
    finally:
        _cleanup_plugin_view(plugin_view)
        if window.root.winfo_exists():
            window.root.destroy()
        flight_controller.disconnect()


_SIMPLE_ACTIONS = {
    "about": _capture_about,
    "connection": _capture_connection,
    "instructions": _capture_instructions,
    "template_overview": _capture_template_overview,
    "fc_banner": _capture_fc_banner,
    # Plugin identifier (imported constant, not a string literal)
    PLUGIN_RC_CALIBRATION: _capture_rc_calibration,
}

_VEHICLE_DIR_ACTIONS = {
    "fc_info": _capture_fc_info,
    "motor_test": _capture_motor_test,
    "parameter_export": _capture_parameter_export,
    "vehicle_opener": _capture_vehicle_opener,
    "vehicle_creator": _capture_vehicle_creator,
    "vehicle_creator_from_flight_controller": _capture_vehicle_creator_from_flight_controller,
}

_VEHICLE_OPENER_HIGHLIGHT = frozenset(
    {
        "vehicle_opener_from_template",
        "vehicle_opener_from_flight_controller",
        "vehicle_opener_legacy4",
        "vehicle_opener_from_bin",
    }
)


def capture_target(target: CaptureTarget, output_path: Path, args: argparse.Namespace) -> None:  # pylint: disable=too-many-branches
    """Capture one screenshot target."""
    action = target.action
    delay = args.delay
    padding = args.padding
    vehicle_dir = args.vehicle_dir

    if (simple_handler := _SIMPLE_ACTIONS.get(action)) is not None:
        simple_handler(output_path, delay, padding)
        return

    if (vehicle_handler := _VEHICLE_DIR_ACTIONS.get(action)) is not None:
        vehicle_handler(output_path, delay, padding, vehicle_dir)
        return

    match action:
        case "mavftp_browser" | "mavftp_remote_panel":
            _capture_mavftp(output_path, delay, padding, remote_panel=action == "mavftp_remote_panel")
        case "connection_no_connection":
            _capture_connection(output_path, delay, padding, highlight_skip=True)
        case "connection_add_another" | "connection_udp_forwarding":
            _capture_connection_forwarding(
                output_path,
                delay,
                padding,
                show_dialog=action == "connection_udp_forwarding",
            )
        case "mavlink_inspector":
            _capture_mavlink_inspector(output_path, delay, padding, target.variant or "radio")
        case "skybrush_log_analysis":
            _capture_skybrush_log_analysis(output_path, delay, padding, target.variant or "results", target.scale)
        case "firmware_upload" | "firmware_upload_progress":
            _capture_firmware_upload(
                output_path,
                delay,
                padding,
                show_progress=action == "firmware_upload_progress",
            )
        case _ if action.startswith("param_"):
            current_file = target.current_file
            gui_complexity = target.gui_complexity
            if current_file is None or gui_complexity is None:
                msg = f"param_* targets require current_file and gui_complexity (action={action})"
                raise RuntimeError(msg)
            _capture_parameter_editor(
                output_path,
                delay,
                padding,
                vehicle_dir,
                current_file=current_file,
                gui_complexity=gui_complexity,
                scale=target.scale,
            )
        case _ if action in _VEHICLE_OPENER_HIGHLIGHT:
            _capture_vehicle_opener_with_highlight(
                output_path,
                delay,
                padding,
                vehicle_dir,
                action=action,
                scale=target.scale,
                fc_connected=action == "vehicle_opener_from_flight_controller",
            )
        case _ if action.startswith("vehicle_creator_"):
            variant = target.variant
            if variant is None:
                msg = f"vehicle_creator_* targets require variant (action={action})"
                raise RuntimeError(msg)
            _capture_vehicle_creator_with_highlight(
                output_path,
                delay,
                padding,
                vehicle_dir,
                variant,
                scale=target.scale,
                fc_connected=True,
            )
        case _ if action.startswith("create_from_template_"):
            variant = target.variant
            if variant is None:
                msg = f"create_from_template_* targets require variant (action={action})"
                raise RuntimeError(msg)
            _capture_vehicle_creator_with_highlight(
                output_path,
                delay,
                padding,
                vehicle_dir,
                variant,
                scale=target.scale,
                fc_connected=False,
            )
        case _:
            msg = f"Unsupported action: {action}"
            raise RuntimeError(msg)


def main() -> int:
    """Program entrypoint."""
    args = parse_args()
    configure_logging(args.log_level)
    # Screenshot windows are created directly rather than through application
    # startup, so explicitly initialize the same plugin registry first.
    register_plugins()

    pyautogui.FAILSAFE = True

    if not args.vehicle_dir.exists():
        logging.error("Vehicle dir does not exist: %s", args.vehicle_dir)
        return 1

    screenshots = getattr(args, "screenshots", None)
    requested_screenshots = list(screenshots) if screenshots is not None else None
    targets = [target for target in TARGETS if requested_screenshots is None or target.filename in requested_screenshots]
    selected_filenames = {target.filename for target in targets}

    failures: list[str] = []
    for target in targets:
        output_path = args.images_dir / target.filename if args.overwrite else args.images_dir / f"{target.filename}.new.png"

        try:
            capture_target(target, output_path, args)
        except Exception:  # pylint: disable=broad-exception-caught
            failures.append(target.filename)
            logging.exception("Failed to generate %s:", target.filename)

    # Keep the historical alias in sync in case only one of the two was captured.
    alias_filenames = {"App_screenshot_Parameter_file_editor_and_uploader4.png", "App_screenshot1.png"}
    if selected_filenames & alias_filenames:
        suffix = "" if args.overwrite else ".new.png"
        path_4 = args.images_dir / f"App_screenshot_Parameter_file_editor_and_uploader4.png{suffix}"
        path_1 = args.images_dir / f"App_screenshot1.png{suffix}"
        if path_4.exists() and not path_1.exists():
            shutil.copy2(path_4, path_1)
        if path_1.exists() and not path_4.exists():
            shutil.copy2(path_1, path_4)

    if failures:
        logging.error("Completed with failures: %s", ", ".join(failures))
        return 2

    logging.info("All requested screenshots generated successfully.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
