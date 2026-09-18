#!/usr/bin/env python3
r"""
Regenerate the screenshots used by USERMANUAL_MAVFTP.md.

The script starts the MAVFTP browser with representative in-memory
flight-controller data and a temporary local directory. It does not connect to
a flight controller or modify files outside its temporary directory and the
two output images.

Usage:
    python -m scripts.regenerate_mavftp_screenshots

SPDX-FileCopyrightText: 2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

from __future__ import annotations

import argparse
import ctypes
import sys
import time
from ctypes import wintypes
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import TYPE_CHECKING, cast

from PIL import Image

from ardupilot_methodic_configurator.backend_flightcontroller_files import FlightControllerLogFile
from ardupilot_methodic_configurator.frontend_tkinter_download_bin_logs import (
    DownloadBinLogsWindow,
    _standalone_ui_services,
)

if TYPE_CHECKING:
    from ardupilot_methodic_configurator.data_model_parameter_editor import ParameterEditor

ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIRECTORY = ROOT_DIR / "images"


class _BitmapInfoHeader(ctypes.Structure):  # pylint: disable=too-few-public-methods
    """Windows BITMAPINFOHEADER structure used by GetDIBits."""

    _fields_ = [
        ("biSize", wintypes.DWORD),
        ("biWidth", wintypes.LONG),
        ("biHeight", wintypes.LONG),
        ("biPlanes", wintypes.WORD),
        ("biBitCount", wintypes.WORD),
        ("biCompression", wintypes.DWORD),
        ("biSizeImage", wintypes.DWORD),
        ("biXPelsPerMeter", wintypes.LONG),
        ("biYPelsPerMeter", wintypes.LONG),
        ("biClrUsed", wintypes.DWORD),
        ("biClrImportant", wintypes.DWORD),
    ]


class _BitmapInfo(ctypes.Structure):  # pylint: disable=too-few-public-methods
    """Windows BITMAPINFO structure without a colour table for 32-bit pixels."""

    _fields_ = [("bmiHeader", _BitmapInfoHeader)]


class _DemoParameterEditor:
    """Minimal parameter-editor API that supplies deterministic screenshot data."""

    is_fc_connected = True
    is_mavftp_supported = True

    def __init__(self, local_directory: Path) -> None:
        self.local_directory = local_directory

    def get_vehicle_directory(self) -> str:
        """Return the temporary local directory displayed by the PC panel."""
        return str(self.local_directory)

    @staticmethod
    def get_remote_files(directory: str) -> list[FlightControllerLogFile]:
        """Return representative MAVFTP entries for the displayed directory."""
        normalized = directory.rstrip("/") or "/"
        listings = {
            "/APM/LOGS": [
                FlightControllerLogFile(
                    "00000157.BIN",
                    "/APM/LOGS/00000157.BIN",
                    4_820_992,
                    modified_at=1788450300,
                ),
                FlightControllerLogFile(
                    "00000158.BIN",
                    "/APM/LOGS/00000158.BIN",
                    1_284_096,
                    modified_at=1788461100,
                ),
                FlightControllerLogFile(
                    "mission-notes.txt",
                    "/APM/LOGS/mission-notes.txt",
                    1_284,
                    modified_at=1788461700,
                ),
                FlightControllerLogFile(
                    "archive",
                    "/APM/LOGS/archive",
                    0,
                    is_directory=True,
                    modified_at=1788379200,
                ),
            ],
            "/APM": [
                FlightControllerLogFile("LOGS", "/APM/LOGS", 0, is_directory=True, modified_at=1788461700),
                FlightControllerLogFile("PARAMS", "/APM/PARAMS", 0, is_directory=True, modified_at=1788379200),
            ],
            "/": [FlightControllerLogFile("APM", "/APM", 0, is_directory=True, modified_at=1788461700)],
        }
        return listings.get(normalized, [])


def _capture_window(hwnd: int) -> Image.Image:
    """Capture a Tk window with PrintWindow, including when screen capture is unavailable."""
    if sys.platform != "win32":
        message = "MAVFTP screenshots can currently be generated only on Windows."
        raise RuntimeError(message)

    user32 = ctypes.windll.user32
    gdi32 = ctypes.windll.gdi32
    rectangle = wintypes.RECT()
    if not user32.GetWindowRect(hwnd, ctypes.byref(rectangle)):
        raise ctypes.WinError()
    width = rectangle.right - rectangle.left
    height = rectangle.bottom - rectangle.top
    if width <= 0 or height <= 0:
        message = "The MAVFTP window has an invalid size."
        raise RuntimeError(message)

    window_dc = user32.GetWindowDC(hwnd)
    memory_dc = gdi32.CreateCompatibleDC(window_dc)
    bitmap = gdi32.CreateCompatibleBitmap(window_dc, width, height)
    previous_bitmap = gdi32.SelectObject(memory_dc, bitmap)
    try:
        if not user32.PrintWindow(hwnd, memory_dc, 2):  # PW_RENDERFULLCONTENT
            message = "Windows could not render the MAVFTP window for capture."
            raise RuntimeError(message)
        bitmap_info = _BitmapInfo(
            _BitmapInfoHeader(
                ctypes.sizeof(_BitmapInfoHeader),
                width,
                -height,
                1,
                32,
                0,
                width * height * 4,
                0,
                0,
                0,
                0,
            )
        )
        raw_pixels = ctypes.create_string_buffer(width * height * 4)
        copied_rows = gdi32.GetDIBits(memory_dc, bitmap, 0, height, raw_pixels, ctypes.byref(bitmap_info), 0)
        if copied_rows != height:
            message = f"Windows captured {copied_rows} of {height} rows."
            raise RuntimeError(message)
        return Image.frombuffer("RGB", (width, height), bytes(raw_pixels), "raw", "BGRX", 0, 1).copy()
    finally:
        gdi32.SelectObject(memory_dc, previous_bitmap)
        gdi32.DeleteObject(bitmap)
        gdi32.DeleteDC(memory_dc)
        user32.ReleaseDC(hwnd, window_dc)


def _wait_for_initial_listing(window: DownloadBinLogsWindow, timeout_seconds: float = 5.0) -> None:
    """Allow the asynchronous initial remote listing to populate the Treeview."""
    deadline = time.monotonic() + timeout_seconds
    while not window.remote_entries and time.monotonic() < deadline:
        window.root.update()
        time.sleep(0.05)
    if not window.remote_entries:
        message = "The example remote directory did not populate before the timeout."
        raise RuntimeError(message)


def _write_screenshots(output_directory: Path) -> None:
    """Create the full browser screenshot and a crop focused on the FC panel."""
    output_directory.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix="methodic-configurator-mavftp-") as temporary_directory:
        local_directory = Path(temporary_directory)
        (local_directory / "analysis.csv").write_text("time,value\n0,1\n", encoding="utf-8")
        (local_directory / "flight-photos").mkdir()
        (local_directory / "README.txt").write_text(
            "Files copied from the flight controller.\n",
            encoding="utf-8",
        )

        window = DownloadBinLogsWindow(
            None,
            cast("ParameterEditor", _DemoParameterEditor(local_directory)),
            _standalone_ui_services(),
        )
        try:
            window.root.update()
            _wait_for_initial_listing(window)
            window.root.update_idletasks()
            window.root.update()
            browser_image = _capture_window(window.root.winfo_id())
            browser_image.save(output_directory / "App_screenshot_MAVFTP_browser.png")
            browser_image.crop((0, 0, browser_image.width // 2 + 10, browser_image.height)).save(
                output_directory / "App_screenshot_MAVFTP_remote_panel.png"
            )
        finally:
            window.root.destroy()


def main() -> None:
    """Parse arguments and regenerate the MAVFTP manual screenshots."""
    parser = argparse.ArgumentParser(description="Regenerate MAVFTP user-manual screenshots.")
    parser.add_argument(
        "--output-directory",
        type=Path,
        default=DEFAULT_OUTPUT_DIRECTORY,
        help="Directory that receives the generated PNG files (default: %(default)s).",
    )
    arguments = parser.parse_args()
    _write_screenshots(arguments.output_directory)


if __name__ == "__main__":
    main()
