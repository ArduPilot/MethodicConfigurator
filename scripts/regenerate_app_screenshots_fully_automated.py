#!/usr/bin/env python3
"""
Fully automated regeneration of AMC application screenshots.

This script creates the screenshot windows from AMC symbols/classes directly and
captures them with pyautogui. It is non-interactive and intended for updating
images under the repository's images directory.

Usage:
    python scripts/regenerate_app_screenshots_fully_automated.py

SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

from __future__ import annotations

import argparse
import logging
import platform
import re
import shutil
import tempfile
import time
import tkinter as tk
import tkinter.font as tk_font
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, cast
from unittest.mock import MagicMock, patch

import pyautogui
from PIL import Image, ImageDraw

from ardupilot_methodic_configurator import __version__
from ardupilot_methodic_configurator.backend_filesystem import LocalFilesystem
from ardupilot_methodic_configurator.backend_filesystem_program_settings import ProgramSettings
from ardupilot_methodic_configurator.backend_flightcontroller import FlightController
from ardupilot_methodic_configurator.data_model_motor_test import MotorTestDataModel
from ardupilot_methodic_configurator.data_model_par_dict import ParDict
from ardupilot_methodic_configurator.data_model_parameter_editor import ParameterEditor
from ardupilot_methodic_configurator.frontend_tkinter_about_popup_window import AboutWindow
from ardupilot_methodic_configurator.frontend_tkinter_connection_selection import ConnectionSelectionWindow
from ardupilot_methodic_configurator.frontend_tkinter_flightcontroller_info import FlightControllerInfoWindow
from ardupilot_methodic_configurator.frontend_tkinter_motor_test import MotorTestView, MotorTestWindow
from ardupilot_methodic_configurator.frontend_tkinter_parameter_editor import ParameterEditorWindow
from ardupilot_methodic_configurator.frontend_tkinter_project_creator import VehicleProjectCreatorWindow
from ardupilot_methodic_configurator.frontend_tkinter_project_opener import VehicleProjectOpenerWindow
from ardupilot_methodic_configurator.frontend_tkinter_template_overview import TemplateOverviewWindow
from ardupilot_methodic_configurator.frontend_tkinter_usage_popup_windows import display_parameter_editor_usage_popup

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator

ROOT_DIR = Path(__file__).resolve().parents[1]
IMAGES_DIR = ROOT_DIR / "images"
DEFAULT_VEHICLE_DIR = ROOT_DIR / "ardupilot_methodic_configurator" / "vehicle_templates" / "ArduCopter" / "empty_4.6.x"


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
    CaptureTarget("App_screenshot_FC_info_and_param_download.png", "fc_info"),
    CaptureTarget("App_screenshot_instructions.png", "instructions"),
    CaptureTarget("App_screenshot_motor_test.png", "motor_test"),
    CaptureTarget(
        "App_screenshot_Parameter_file_editor_and_uploader4_4_simple.png",
        "param_04_simple",
        scale=0.666,
        gui_complexity="simple",
        current_file="04_board_orientation.param",
    ),
    CaptureTarget(
        "App_screenshot_Parameter_file_editor_and_uploader4_4.png",
        "param_04_normal",
        scale=0.666,
        gui_complexity="normal",
        current_file="04_board_orientation.param",
    ),
    CaptureTarget(
        "App_screenshot_Parameter_file_editor_and_uploader4.png",
        "param_20_normal",
        scale=0.666,
        gui_complexity="normal",
        current_file="20_throttle_controller.param",
    ),
    CaptureTarget("App_screenshot_Vehicle_directory.png", "vehicle_opener"),
    CaptureTarget("App_screenshot_Vehicle_directory10.png", "vehicle_opener"),
    CaptureTarget("App_screenshot_Vehicle_directory_create_from_template.png", "vehicle_opener_from_template", scale=0.8),
    CaptureTarget("App_screenshot_Vehicle_directory_create_from_bin.png", "vehicle_opener_from_bin", scale=0.8),
    CaptureTarget("App_screenshot_Vehicle_directory4.png", "vehicle_opener_legacy4", scale=0.8),
    CaptureTarget("App_screenshot_Vehicle_directory11.png", "vehicle_creator"),
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
    CaptureTarget(
        "App_screenshot_Vehicle_directory_create_from_configured_options.png",
        "vehicle_creator_options",
        scale=0.8,
        variant="from_configured_options",
    ),
    CaptureTarget(
        "App_screenshot_Vehicle_directory_create_from_configured_name.png",
        "vehicle_creator_name",
        scale=0.8,
        variant="from_configured_name",
    ),
    CaptureTarget(
        "App_screenshot_Vehicle_directory_create_from_configured_create.png",
        "vehicle_creator_create",
        scale=0.8,
        variant="from_configured_create",
    ),
    CaptureTarget("App_screenshot_Vehicle_overview.png", "template_overview"),
    CaptureTarget(
        "App_screenshot1.png",
        "param_20_normal",
        scale=0.666,
        gui_complexity="normal",
        current_file="20_throttle_controller.param",
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


def _find_descendant(widget: tk.Misc, predicate: Callable[[tk.Misc], bool]) -> tk.Misc | None:
    """Return first descendant matching predicate."""
    for candidate in _iter_descendants(widget):
        if predicate(candidate):
            return candidate
    return None


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
) -> None:
    """Capture screenshot of a Tk widget region."""
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

    # Crop superfluous pixels on Windows before resizing
    if platform.system() == "Windows":
        crop_left = 15
        crop_right = 15
        crop_bottom = 20
        if image.width > crop_left + crop_right and image.height > crop_bottom:
            image = image.crop((crop_left, 0, image.width - crop_right, image.height - crop_bottom))

    if scale != 1.0:
        new_size = (round(image.width * scale), round(image.height * scale))
        image = image.resize(new_size, Image.Resampling.LANCZOS)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    image.save(output_path)
    logging.info("Saved %s", output_path)


@contextmanager
def hidden_root() -> Iterator[tk.Tk]:
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


def _capture_connection(output_path: Path, delay: float, padding: int) -> None:
    flight_controller = FakeConnectionFlightController()
    window = ConnectionSelectionWindow(
        cast("FlightController", flight_controller),
        "No ArduPilot flight controller was auto-detected yet.",
    )
    try:
        capture_widget(window.root, output_path, delay, padding)
    finally:
        if hasattr(window, "connection_selection_widgets"):
            window.connection_selection_widgets.stop_periodic_refresh()
        if window.root.winfo_exists():
            window.root.destroy()


def _capture_fc_info(output_path: Path, delay: float, padding: int, vehicle_dir: Path) -> None:
    fake_fc = FakeFlightControllerForInfoWindow()

    def _no_download(self: FlightControllerInfoWindow) -> None:
        self.progress_label.config(text="Downloaded 947 of 999 parameters")

    with (
        patch.object(tk.Tk, "mainloop", lambda _self: None),
        patch.object(FlightControllerInfoWindow, "_download_flight_controller_parameters", _no_download),
    ):
        window = FlightControllerInfoWindow(fake_fc, vehicle_dir)  # type: ignore[arg-type]
    try:
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
        browse_button = _find_descendant(
            window.connection_selection_widgets.container_frame,
            lambda w: _widget_text(w) == "...",
        )
        if browse_button is None:
            msg = "Could not find open vehicle browse button"
            raise RuntimeError(msg)
        return _widget_screen_box(browse_button, margin=2)

    if action == "vehicle_opener_from_template":
        template_button = _find_descendant(
            window.main_frame,
            lambda w: _widget_text(w).startswith("Create a vehicle configuration directory from template"),
        )
        if template_button is None:
            msg = "Could not find create from template button"
            raise RuntimeError(msg)
        return _widget_screen_box(template_button, margin=2)

    if action == "vehicle_opener_from_bin":
        bin_button = _find_descendant(
            window.main_frame,
            lambda w: _widget_text(w).startswith("Create a vehicle project from a .bin log file"),
        )
        if bin_button is None:
            msg = "Could not find create from bin button"
            raise RuntimeError(msg)
        return _widget_screen_box(bin_button, margin=2)

    msg = f"Unsupported vehicle opener highlight action: {action}"
    raise RuntimeError(msg)


def _capture_vehicle_opener_with_highlight(
    output_path: Path,
    delay: float,
    padding: int,
    vehicle_dir: Path,
    action: str = "vehicle_opener_legacy4",
    scale: float = 1.0,
) -> None:
    manager = FakeProjectManager(vehicle_dir, vehicle_dir.parent, vehicle_dir)
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


def _create_vehicle_creator_window(vehicle_dir: Path, fc_connected: bool = False) -> VehicleProjectCreatorWindow:
    fc_params = _load_fc_params_from_file(vehicle_dir) if fc_connected else {}
    manager = FakeProjectManager(
        vehicle_dir,
        vehicle_dir.parent,
        vehicle_dir,
        fc_connected=fc_connected,
        fc_parameters=fc_params if fc_connected else None,
    )
    window = VehicleProjectCreatorWindow(manager)  # type: ignore[arg-type]
    settle_tk(window.root, cycles=6, delay=0.05)
    return window


def _find_template_browse_button(window: VehicleProjectCreatorWindow) -> tuple[int, int, int, int]:
    """Find and return bounding box for template browse button."""
    browse_button = _find_descendant(
        window.template_dir.container_frame,
        lambda w: _widget_text(w) == "...",
    )
    if browse_button is None:
        msg = "Could not find source template browse button"
        raise RuntimeError(msg)
    return _widget_screen_box(browse_button, margin=2)


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
    create_button = _find_descendant(
        window.main_frame,
        lambda w: _widget_text(w).startswith("Create a vehicle configuration directory"),
    )
    if create_button is None:
        msg = "Could not find create vehicle directory button"
        raise RuntimeError(msg)
    return _widget_screen_box(create_button, margin=2)


def _vehicle_creator_highlight_box(window: VehicleProjectCreatorWindow, variant: str) -> tuple[int, int, int, int]:
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
    flight_controller.set_master_for_testing(MagicMock())  # make master non-None
    flight_controller.fc_parameters = fc_params  # pre-populate parameter cache

    # Patch download_params so the window startup download returns our fake data
    # without attempting any real MAVLink communication.
    try:
        with patch.object(
            FlightController,
            "download_params",
            return_value=(fc_params, ParDict()),
        ):
            editor = ParameterEditor(current_file, flight_controller, filesystem)
            window = ParameterEditorWindow(editor)
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
            if window.root.winfo_exists():
                window.root.destroy()
            flight_controller.disconnect()


def _suppress_motor_view_periodic_updates(_view: MotorTestView) -> None:
    """Disable periodic updates to keep capture deterministic and non-blocking."""
    return


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
        flight_controller.set_master_for_testing(MagicMock())
        flight_controller.fc_parameters = fc_params
        flight_controller.stop_all_motors = MagicMock(return_value=(True, ""))

        model = MotorTestDataModel(flight_controller, filesystem)
        with patch.object(MotorTestView, "_update_view", _suppress_motor_view_periodic_updates):
            window = MotorTestWindow(model)
        try:
            capture_widget(window.root, output_path, delay, padding)
        finally:
            window.on_close()


def capture_target(target: CaptureTarget, output_path: Path, args: argparse.Namespace) -> None:
    """Capture one screenshot target."""
    action = target.action
    if action == "about":
        _capture_about(output_path, args.delay, args.padding)
    elif action == "connection":
        _capture_connection(output_path, args.delay, args.padding)
    elif action == "fc_info":
        _capture_fc_info(output_path, args.delay, args.padding, args.vehicle_dir)
    elif action == "instructions":
        _capture_instructions(output_path, args.delay, args.padding)
    elif action == "motor_test":
        _capture_motor_test(output_path, args.delay, args.padding, args.vehicle_dir)
    elif action.startswith("param_"):
        if target.gui_complexity is None:
            msg = f"gui_complexity required for {action}"
            raise RuntimeError(msg)
        if target.current_file is None:
            msg = f"current_file required for {action}"
            raise RuntimeError(msg)
        _capture_parameter_editor(
            output_path,
            args.delay,
            args.padding,
            args.vehicle_dir,
            current_file=target.current_file,
            gui_complexity=target.gui_complexity,
            scale=target.scale,
        )
    elif action == "vehicle_opener":
        _capture_vehicle_opener(output_path, args.delay, args.padding, args.vehicle_dir)
    elif action in ("vehicle_opener_from_template", "vehicle_opener_legacy4", "vehicle_opener_from_bin"):
        _capture_vehicle_opener_with_highlight(
            output_path, args.delay, args.padding, args.vehicle_dir, action=action, scale=target.scale
        )
    elif action == "vehicle_creator":
        _capture_vehicle_creator(output_path, args.delay, args.padding, args.vehicle_dir)
    elif action.startswith("vehicle_creator_"):
        if target.variant is None:
            msg = f"variant required for {action}"
            raise RuntimeError(msg)
        # Enable FC connection for all vehicle_creator variants to show FC-dependent options
        _capture_vehicle_creator_with_highlight(
            output_path,
            args.delay,
            args.padding,
            args.vehicle_dir,
            target.variant,
            scale=target.scale,
            fc_connected=True,
        )
    elif action.startswith("create_from_template_"):
        if target.variant is None:
            msg = f"variant required for {action}"
            raise RuntimeError(msg)
        # Create from template shows the flow without pre-configured FC options
        _capture_vehicle_creator_with_highlight(
            output_path,
            args.delay,
            args.padding,
            args.vehicle_dir,
            target.variant,
            scale=target.scale,
            fc_connected=False,
        )
    elif action == "template_overview":
        _capture_template_overview(output_path, args.delay, args.padding)
    else:
        msg = f"Unsupported action: {action}"
        raise RuntimeError(msg)


def main() -> int:
    """Program entrypoint."""
    args = parse_args()
    configure_logging(args.log_level)

    pyautogui.FAILSAFE = True

    if not args.vehicle_dir.exists():
        logging.error("Vehicle dir does not exist: %s", args.vehicle_dir)
        return 1

    failures: list[str] = []
    for target in TARGETS:
        output_path = args.images_dir / target.filename if args.overwrite else args.images_dir / f"{target.filename}.new.png"

        try:
            capture_target(target, output_path, args)
        except Exception as exc:  # pylint: disable=broad-exception-caught
            failures.append(target.filename)
            logging.exception("Failed to generate %s: %s", target.filename, exc)

    # Keep the historical alias in sync in case only one of the two was captured.
    if args.overwrite:
        path_4 = args.images_dir / "App_screenshot_Parameter_file_editor_and_uploader4.png"
        path_1 = args.images_dir / "App_screenshot1.png"
    else:
        path_4 = args.images_dir / "App_screenshot_Parameter_file_editor_and_uploader4.png.new.png"
        path_1 = args.images_dir / "App_screenshot1.png.new.png"
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
