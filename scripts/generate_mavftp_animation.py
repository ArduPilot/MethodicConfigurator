#!/usr/bin/env python3
"""
Generate the MAVFTP download and web log analysis walkthrough animations.

Run from the repository root on an unlocked graphical desktop with Chrome
and Internet access. The default run uses the repository's Tarot X4 log:
    python scripts/generate_mavftp_animation.py

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

from __future__ import annotations

import argparse
import shutil
import tempfile
import threading
import time
import tkinter as tk
from contextlib import suppress
from dataclasses import replace
from io import BytesIO
from pathlib import Path
from tkinter import ttk
from typing import TYPE_CHECKING, cast
from unittest.mock import patch
from urllib.parse import urlsplit

from PIL import Image, ImageDraw, ImageFont
from regenerate_app_screenshots_fully_automated import (
    DEFAULT_VEHICLE_DIR,
    IMAGES_DIR,
    ROOT_DIR,
    _build_parameter_editor,
    _capture_posted_menu,
    _cleanup_plugin_view,
    _compute_capture_region,
    _find_descendant,
    _MavftpScreenshotEditor,
    _MavftpScreenshotWindow,
    _widget_screen_box,
    _widget_text,
    capture_widget,
    settle_tk,
)
from selenium.common.exceptions import (
    ElementClickInterceptedException,
    NoAlertPresentException,
    StaleElementReferenceException,
)
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as ec
from selenium.webdriver.support.ui import WebDriverWait

from ardupilot_methodic_configurator import _ as translate
from ardupilot_methodic_configurator.__main__ import register_plugins
from ardupilot_methodic_configurator.backend_filesystem_program_settings import ProgramSettings
from ardupilot_methodic_configurator.backend_web_log_tools import _SESSION, WEB_LOG_TOOLS, open_log_in_web_tool
from ardupilot_methodic_configurator.data_model_parameter_editor import ParameterEditor

if TYPE_CHECKING:
    from collections.abc import Callable

    from selenium.webdriver.remote.webdriver import WebDriver

    from ardupilot_methodic_configurator.backend_flightcontroller_files import FlightControllerLogFile
    from ardupilot_methodic_configurator.frontend_tkinter_file_browser import FileBrowserWindow


DEFAULT_LOG = (
    ROOT_DIR / "ardupilot_methodic_configurator" / "vehicle_templates" / "ArduCopter" / "Tarot_X4" / "2024-08-05 18-48-54.bin"
)
FILTER_REVIEW_URL = "https://firmware.ardupilot.org/Tools/WebTools/FilterReview/"
MAGFIT_URL = "https://firmware.ardupilot.org/Tools/WebTools/MAGFit/"
PID_REVIEW_URL = "https://firmware.ardupilot.org/Tools/WebTools/PIDReview/"
SYSTEM_ID_URL = "https://firmware.ardupilot.org/Tools/WebTools/SysID/"
DEFAULT_PARAMETER_FILE = "28_throttle_controller.param"
TOOL_PARAMETER_FILES = {
    FILTER_REVIEW_URL: "29_motor_notch_filter_results.param",
    MAGFIT_URL: "36_inflight_magnetometer_fit_results.param",
    PID_REVIEW_URL: "32_pid_notch_filter_results.param",
    SYSTEM_ID_URL: "54_system_id_input_roll.param",
}


class ExampleEditor(_MavftpScreenshotEditor):
    """Simulate a transfer into an isolated temporary directory."""

    def __init__(self, local_directory: Path, example_log: Path) -> None:
        super().__init__(local_directory)
        self.example_log = example_log

    def get_remote_files(self, directory: str) -> list[FlightControllerLogFile]:
        """Return the screenshot listing with the selected example log's real size."""
        listings = super().get_remote_files(directory)
        example_size = self.example_log.stat().st_size
        return [replace(entry, size_bytes=example_size) if entry.name == "00000158.BIN" else entry for entry in listings]

    def download_remote_file(self, _remote: str, local: str, progress: Callable[[int, int], None]) -> bool:
        shutil.copyfile(self.example_log, local)
        size = self.example_log.stat().st_size
        progress(size, size)
        return True

    def verify_remote_file(self, _remote: str, local: str) -> bool:
        """Verify that the simulated local download matches the example remote file."""
        return Path(local).read_bytes() == self.example_log.read_bytes()


def wait_for(root: tk.Misc, condition: Callable[[], bool], timeout: float = 15) -> None:
    """Process Tk callbacks until an asynchronous operation finishes."""
    deadline = time.monotonic() + timeout
    while not condition():
        if time.monotonic() > deadline:
            msg = "Timed out waiting for the example workflow"
            raise TimeoutError(msg)
        root.update()
        time.sleep(0.05)
    settle_tk(root)


def capture_webtool_frame(driver: WebDriver, label: str, url: str) -> Image.Image:
    """Capture a loaded analysis tool in the shared animation frame layout."""
    if url == FILTER_REVIEW_URL:
        with suppress(NoAlertPresentException):
            driver.switch_to.alert.accept()
    driver.set_window_size(1200, 900)
    hostname = urlsplit(url).hostname
    if hostname in {"plot.ardupilot.org", "plotbeta.ardupilot.org"}:
        wait = WebDriverWait(driver, 90, ignored_exceptions=(ElementClickInterceptedException, StaleElementReferenceException))
        wait.until(ec.invisibility_of_element_located((By.ID, "waiting")))
        # Retry real clicks while the viewer's startup overlay intercepts them.
        for label_text in ("Plot Individual Field", "Canonical vehicle attitude", "achieved vehicle roll"):
            wait.until(lambda d, target=label_text: click_visible_text(d, target), message=label_text)
        wait.until(lambda d: d.find_elements(By.CSS_SELECTOR, ".scatterlayer .trace path.js-line"))
    time.sleep(2)
    with Image.open(BytesIO(driver.get_screenshot_as_png())) as screenshot:
        frame = screenshot.convert("RGB")
    frame.thumbnail((1200, 700), Image.Resampling.LANCZOS)
    canvas = Image.new("RGB", (1200, 750), "#eeeeee")
    canvas.paste(frame, ((1200 - frame.width) // 2, 50))
    draw = ImageDraw.Draw(canvas)
    draw.rectangle((0, 0, 1200, 50), fill="#202b35")
    description = f"6. {label} displays the selected log"
    draw.text((20, 12), description, fill="white", font=ImageFont.load_default(size=20))
    return canvas


def click_visible_text(driver: WebDriver, label: str) -> bool:
    """Click a visible matching control, returning whether it was found."""
    for element in driver.find_elements(By.XPATH, f"//*[contains(text(), '{label}')]"):
        if element.is_displayed():
            element.click()
            return True
    return False


def create_tool_launcher(completed: threading.Event, launch_errors: list[Exception]) -> Callable[[str, Path], None]:
    """Create the callback used by the file menu's background launcher."""

    def launch_tool(target_url: str, path: Path) -> None:
        try:
            open_log_in_web_tool(target_url, path)
        except Exception as error:  # pylint: disable=broad-exception-caught
            launch_errors.append(error)
        finally:
            completed.set()

    return launch_tool


def parameter_file_for_tool(url: str) -> str:
    """Return the configuration step shown at the start of a tool animation."""
    return TOOL_PARAMETER_FILES.get(url, DEFAULT_PARAMETER_FILE)


def main() -> None:  # noqa: C901, PLR0915  # pylint: disable=too-many-locals,too-many-statements,too-many-branches
    """Record MAVFTP downloads opened in each supported log analysis webtool."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=IMAGES_DIR)
    parser.add_argument("--vehicle-dir", type=Path, default=DEFAULT_VEHICLE_DIR)
    parser.add_argument(
        "--log", type=Path, default=DEFAULT_LOG, help="DataFlash log to use (default: repository Tarot X4 log)"
    )
    parser.add_argument(
        "--tool",
        action="append",
        choices=[tool.label for tool in WEB_LOG_TOOLS.values()],
        help="Generate only the named tool. May be repeated. Default includes every supported tool.",
    )
    args = parser.parse_args()
    if not args.log.is_file():
        parser.error(f"Log file does not exist: {args.log}")
    selected_tools = {url: tool for url, tool in WEB_LOG_TOOLS.items() if args.tool is None or tool.label in args.tool}
    register_plugins()
    frames: list[Image.Image] = []
    durations: list[int] = []
    pointer = (120, 100)
    browser: FileBrowserWindow | None = None

    with tempfile.TemporaryDirectory() as tmp:
        temporary = Path(tmp)
        vehicle = temporary / "ExampleVehicle"
        shutil.copytree(args.vehicle_dir, vehicle)
        local = temporary / "Downloads"
        local.mkdir()
        example = ExampleEditor(local, args.log)
        frame_path = temporary / "frame.png"

        def record(  # pylint: disable=too-many-locals
            widget: tk.Misc,
            caption: str,
            box: tuple[int, int, int, int] | None = None,
            *,
            target: tuple[int, int] | None = None,
            click: str = "left",
        ) -> None:
            nonlocal pointer
            if browser is not None and widget == browser.main_frame:
                display_directory = tk.StringVar(master=browser.root, value="ExampleVehicle")
                original_label = browser.local_directory_label.cget("text")
                browser.local_directory_entry.configure(textvariable=display_directory)
                browser.local_directory_label.configure(
                    text=translate("Local files in {directory}").format(directory="ExampleVehicle")
                )
                settle_tk(browser.root)
                try:
                    capture_widget(
                        widget, frame_path, 0, highlight_boxes=(lambda: [box]) if box else None, trim_windows_frame=False
                    )
                finally:
                    browser.local_directory_entry.configure(textvariable=browser.local_directory_var)
                    browser.local_directory_label.configure(text=original_label)
            else:
                capture_widget(
                    widget, frame_path, 0, highlight_boxes=(lambda: [box]) if box else None, trim_windows_frame=False
                )
            x, y, _, _ = _compute_capture_region(widget, 0)
            with Image.open(frame_path) as image:
                frame = image.convert("RGB")
            original_width, original_height = frame.size
            frame.thumbnail((1200, 700), Image.Resampling.LANCZOS)
            offset = (1200 - frame.width) // 2
            canvas = Image.new("RGB", (1200, 750), "#eeeeee")
            canvas.paste(frame, (offset, 50))
            draw = ImageDraw.Draw(canvas)
            draw.rectangle((0, 0, 1200, 50), fill="#202b35")
            draw.text((20, 12), caption, fill="white", font=ImageFont.load_default(size=20))

            if target is None and box is not None:
                target = ((box[0] + box[2]) // 2, (box[1] + box[3]) // 2)
            if target is None:
                frames.append(canvas)
                durations.append(2700)
                return
            destination = (
                offset + round((target[0] - x) * frame.width / original_width),
                50 + round((target[1] - y) * frame.height / original_height),
            )

            def add_pointer(position: tuple[int, int], duration: int, *, pressed: bool = False) -> None:
                image = canvas.copy()
                marker = ImageDraw.Draw(image)
                px, py = position
                marker.ellipse((px - 19, py - 19, px + 19, py + 19), fill="#ffd83d", outline="#a05b00", width=3)
                marker.polygon(
                    [
                        (px, py),
                        (px, py + 22),
                        (px + 6, py + 16),
                        (px + 11, py + 26),
                        (px + 15, py + 24),
                        (px + 10, py + 14),
                        (px + 19, py + 14),
                    ],
                    fill="white",
                    outline="black",
                    width=2,
                )
                if pressed:
                    marker.ellipse((px - 28, py - 28, px + 28, py + 28), outline="#e22b2b", width=5)
                    marker.text(
                        (px + 24, py - 30),
                        f"{click.upper()} CLICK",
                        fill="#b00000",
                        font=ImageFont.load_default(size=18),
                        stroke_width=2,
                        stroke_fill="white",
                    )
                frames.append(image)
                durations.append(duration)

            for step in range(1, 5):
                position = tuple(round(pointer[i] + (destination[i] - pointer[i]) * step / 4) for i in range(2))
                add_pointer(cast("tuple[int, int]", position), 300)
            add_pointer(destination, 450, pressed=True)
            add_pointer(destination, 1050)
            pointer = destination

        def row_target(tree: ttk.Treeview, index: int) -> tuple[int, int]:
            """Return the screen coordinates of a visible file row."""
            x, y, width, height = tree.bbox(str(index))
            return tree.winfo_rootx() + x + min(width // 2, 100), tree.winfo_rooty() + y + height // 2

        with (
            patch.object(ProgramSettings, "_user_config_dir", return_value=str(temporary)),
            patch.object(ParameterEditor, "is_mavftp_supported", property(lambda _self: True)),
        ):
            intro_frames: dict[str, tuple[list[Image.Image], list[int], tuple[int, int]]] = {}
            for parameter_file in dict.fromkeys(parameter_file_for_tool(url) for url in selected_tools):
                intro_editor, intro_controller = _build_parameter_editor(parameter_file, vehicle, "normal")
                try:
                    intro_editor.root.attributes("-topmost", 1)
                    intro_editor.root.lift()
                    settle_tk(intro_editor.root)
                    intro_button = _find_descendant(
                        intro_editor.root,
                        lambda w: isinstance(w, ttk.Button) and _widget_text(w) == translate("Download .bin\nlog file(s)"),
                    )
                    if intro_button is None:
                        msg = f"Could not find the download button for {parameter_file}"
                        raise RuntimeError(msg)
                    frames.clear()
                    durations.clear()
                    pointer = (120, 100)
                    record(intro_editor.root, "1. Open the MAVFTP file browser", _widget_screen_box(intro_button))
                    intro_frames[parameter_file] = (frames.copy(), durations.copy(), pointer)
                finally:
                    if intro_editor.current_plugin_view is not None:
                        _cleanup_plugin_view(intro_editor.current_plugin_view)
                    if intro_editor.root.winfo_exists():
                        intro_editor.root.destroy()
                    intro_controller.disconnect()

            frames.clear()
            durations.clear()
            pointer = next(iter(intro_frames.values()))[2]
            editor, controller = _build_parameter_editor(DEFAULT_PARAMETER_FILE, vehicle, "normal")
        try:
            editor.root.attributes("-topmost", 1)
            editor.root.lift()
            settle_tk(editor.root)
            button = _find_descendant(
                editor.root, lambda w: isinstance(w, ttk.Button) and _widget_text(w) == translate("Download .bin\nlog file(s)")
            )
            if button is None:
                msg = "Could not find the download button"
                raise RuntimeError(msg)

            def make_browser(parent: tk.Misc, _model: ParameterEditor, ui: object, **kwargs: object) -> FileBrowserWindow:
                return _MavftpScreenshotWindow(parent, cast("ParameterEditor", example), ui, **kwargs)

            with patch(
                "ardupilot_methodic_configurator.frontend_tkinter_parameter_editor.FileBrowserWindow", side_effect=make_browser
            ):
                button.invoke()
            browser = editor._file_browser_window  # noqa: SLF001  # pylint: disable=protected-access
            if browser is None:
                msg = "The file browser did not open"
                raise RuntimeError(msg)
            browser.root.attributes("-topmost", 1)
            browser.root.lift()
            wait_for(browser.root, lambda: bool(browser.remote_entries))
            browser.verify_transfers_var.set(True)
            index = next(i for i, entry in enumerate(browser.remote_entries) if entry.name == "00000158.BIN")
            record(
                browser.main_frame,
                "2. Select a flight log on the flight controller",
                target=row_target(browser.remote_tree, index),
            )
            browser.remote_tree.selection_set(str(index))
            browser.remote_tree.event_generate("<<TreeviewSelect>>")
            settle_tk(browser.root)
            record(browser.main_frame, "3. Download the selected log", _widget_screen_box(browser.download_button))
            with patch.object(browser, "_show_summary"):
                browser.download_button.invoke()
                wait_for(browser.root, lambda: any(entry.name == "00000158.BIN" for entry in browser.local_entries))
            index = next(i for i, entry in enumerate(browser.local_entries) if entry.name == "00000158.BIN")
            record(
                browser.main_frame,
                "4. Right-click the downloaded log on the PC",
                target=row_target(browser.local_tree, index),
                click="right",
            )
            browser.local_tree.selection_set(str(index))
            menu = browser._build_context_menu(browser.local_tree, remote=False)  # noqa: SLF001  # pylint: disable=protected-access
            position = (browser.local_tree.winfo_rootx() + 100, browser.local_tree.winfo_rooty() + 30)
            common_frames, common_durations = frames.copy(), durations.copy()
            common_pointer = pointer
            for url, tool in selected_tools.items():
                intro, intro_durations, _intro_pointer = intro_frames[parameter_file_for_tool(url)]
                frames[:], durations[:] = [*intro, *common_frames], [*intro_durations, *common_durations]
                pointer = common_pointer
                _capture_posted_menu(
                    menu,
                    position,
                    lambda label=tool.label: record(
                        browser.main_frame,
                        f"5. Choose {label}",
                        target=(position[0] + 45, position[1] + menu.yposition(menu.index(label)) + 8),
                    ),
                )
                completed = threading.Event()
                launch_error: list[Exception] = []
                launch_tool = create_tool_launcher(completed, launch_error)
                with patch("ardupilot_methodic_configurator.frontend_tkinter_file_browser.open_log_in_web_tool", launch_tool):
                    menu.invoke(translate(tool.label))
                    wait_for(browser.root, completed.is_set, timeout=90)
                if launch_error:
                    msg = f"Could not open the example log in {tool.label}"
                    raise RuntimeError(msg) from launch_error[0]
                driver = _SESSION._driver  # noqa: SLF001  # pylint: disable=protected-access
                if driver is None:
                    msg = "Chrome did not start"
                    raise RuntimeError(msg)
                canvas = capture_webtool_frame(driver, tool.label, url)
                slug = (urlsplit(url).path.rstrip("/").split("/")[-1] or urlsplit(url).netloc.split(".")[0]).lower()
                slug = "".join(char if char.isalnum() else "_" for char in slug).strip("_")
                output = args.output_dir / f"MAVFTP_download_{slug}.gif"
                output.parent.mkdir(parents=True, exist_ok=True)
                compact_frames = []
                for frame in [*frames, canvas]:
                    resized = frame.copy()
                    resized.thumbnail((760, 475), Image.Resampling.LANCZOS)
                    compact_frames.append(resized.quantize(colors=24))
                compact_frames[0].save(
                    output,
                    save_all=True,
                    append_images=compact_frames[1:],
                    duration=[*durations, 2700],
                    loop=0,
                    optimize=True,
                )

        finally:
            _SESSION.close()
            if browser is not None and browser.root.winfo_exists():
                browser.root.destroy()
            if editor.current_plugin_view is not None:
                _cleanup_plugin_view(editor.current_plugin_view)
            if editor.root.winfo_exists():
                editor.root.destroy()
            controller.disconnect()


if __name__ == "__main__":
    main()
