#!/usr/bin/env python3
"""
SVG Viewer Application for ArduPilot Motor Diagrams.

A Tkinter application that allows users to select and view SVG files from the
../ardupilot_methodic_configurator/images directory. The SVG files are rendered
using Firefox-geckodriver and displayed as resized images with antialiasing.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import argparse
import contextlib
import os
import shutil
import tempfile
import time
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk
from typing import Optional

from batch_convert_motor_diagrams import crop_whitespace
from PIL import Image
from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.firefox.service import Service

DEFAULT_IMAGE_WIDTH: int = 200
DEFAULT_IMAGE_HEIGHT: int = 200


class SVGViewerApp:  # pylint: disable=too-many-instance-attributes
    """Main application class for the SVG viewer."""

    def __init__(
        self,
        root: tk.Tk,
        image_width: int = DEFAULT_IMAGE_WIDTH,
        image_height: int = DEFAULT_IMAGE_HEIGHT,
        render_wait: float = 2.0,
    ) -> None:
        """
        Initialize the SVG viewer application.

        Args:
            root (tk.Tk): The Tkinter root window.
            image_width (int): The width to resize images to (default: DEFAULT_IMAGE_WIDTH).
            image_height (int): The height to resize images to (default: DEFAULT_IMAGE_HEIGHT).
            render_wait (float): Seconds to wait for SVG rendering before screenshot (default: 2).

        """
        self.root = root
        self.root.title("ArduPilot Motor Diagrams SVG Viewer")
        self.root.geometry("400x450")

        # Initialize variables
        self.svg_files: list[Path] = []
        self.current_image: Optional[tk.PhotoImage] = None
        self.temp_dir = tempfile.mkdtemp()
        self.image_width = image_width
        self.image_height = image_height
        self.render_wait = render_wait

        # Setup UI
        self.setup_ui()

        # Load SVG files
        self.load_svg_files()

        # Cleanup on close
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

    def setup_ui(self) -> None:
        """Setup the user interface components."""
        # Main frame
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky="nsew")

        # Configure grid weights
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)
        main_frame.rowconfigure(2, weight=1)

        # Title label
        title_label = ttk.Label(main_frame, text="ArduPilot Motor Diagrams", font=("Arial", 14, "bold"))
        title_label.grid(row=0, column=0, columnspan=2, pady=(0, 10))

        # SVG file selection
        ttk.Label(main_frame, text="Select SVG File:").grid(row=1, column=0, sticky=tk.W, pady=(0, 5))

        self.svg_combobox = ttk.Combobox(main_frame, state="readonly", width=40)
        self.svg_combobox.grid(row=1, column=1, sticky="ew", pady=(0, 5))
        self.svg_combobox.bind("<<ComboboxSelected>>", self.on_svg_selected)

        # Image display frame
        image_frame = ttk.LabelFrame(main_frame, text="Motor Diagram", padding="5")
        image_frame.grid(row=2, column=0, columnspan=2, sticky="nsew", pady=(10, 0))
        image_frame.columnconfigure(0, weight=1)
        image_frame.rowconfigure(0, weight=1)

        # Image label
        self.image_label = ttk.Label(image_frame, text="Select an SVG file to view", font=("Arial", 10), anchor="center")
        self.image_label.grid(row=0, column=0, sticky="nsew")

        # File size information frame
        size_frame = ttk.LabelFrame(main_frame, text="File Size Information", padding="5")
        size_frame.grid(row=3, column=0, columnspan=2, sticky="ew", pady=(10, 0))

        # File size labels
        self.size_info_var = tk.StringVar()
        self.size_info_var.set("No file selected")
        size_info_label = ttk.Label(size_frame, textvariable=self.size_info_var, font=("Arial", 9))
        size_info_label.grid(row=0, column=0, sticky="w")

        # Status bar
        self.status_var = tk.StringVar()
        self.status_var.set("Ready")
        status_bar = ttk.Label(main_frame, textvariable=self.status_var, relief=tk.SUNKEN, anchor=tk.W)
        status_bar.grid(row=4, column=0, columnspan=2, sticky="ew", pady=(10, 0))

    def load_svg_files(self) -> None:
        """Load SVG files from the images directory."""
        images_dir = Path("../ardupilot_methodic_configurator/images")

        if not images_dir.exists():
            messagebox.showerror(
                "Error", f"Images directory not found: {images_dir}\nPlease ensure you're running from the correct directory."
            )
            return

        # Find all SVG files
        self.svg_files = sorted(images_dir.glob("*.svg"))

        if not self.svg_files:
            messagebox.showwarning("Warning", f"No SVG files found in {images_dir}")
            return

        # Populate combobox
        svg_names = [svg_file.name for svg_file in self.svg_files]
        self.svg_combobox["values"] = svg_names

        self.status_var.set(f"Loaded {len(self.svg_files)} SVG files")

    def on_svg_selected(self, _event: tk.Event) -> None:
        """Handle SVG file selection from combobox."""
        selection_index = self.svg_combobox.current()
        if selection_index < 0:
            return

        selected_svg = self.svg_files[selection_index]
        self.render_svg(selected_svg)

    def render_svg(self, svg_path: Path) -> None:
        """Render SVG file using Firefox-geckodriver and display it."""
        self.status_var.set(f"Rendering {svg_path.name}...")
        self.root.update()

        try:
            # Create temporary PNG file
            temp_png = Path(self.temp_dir) / f"{svg_path.stem}_temp.png"

            # Render SVG to PNG using Firefox
            if self.convert_svg_to_png(str(svg_path), str(temp_png), wait_time=self.render_wait):
                # Load and resize image, passing both PNG and original SVG paths
                self.display_image(temp_png, svg_path)
                self.status_var.set(f"Successfully loaded {svg_path.name}")
            else:
                messagebox.showerror("Error", f"Failed to render {svg_path.name}")
                self.status_var.set("Rendering failed")
                self.size_info_var.set("Rendering failed")

        except (OSError, RuntimeError, ValueError) as e:
            messagebox.showerror("Error", f"Error rendering {svg_path.name}: {e!s}")
            self.status_var.set("Error occurred")
            self.size_info_var.set("Error occurred")

    def convert_svg_to_png(self, svg_path: str, png_path: str, wait_time: float = 2.0) -> bool:
        """Convert SVG to PNG using Firefox-geckodriver."""
        try:
            # Setup Firefox options
            options = Options()
            options.add_argument("--headless")
            options.add_argument("--width=1200")
            options.add_argument("--height=1200")

            # Setup service to use system geckodriver
            service = Service("/usr/bin/geckodriver")

            # Create WebDriver
            driver = webdriver.Firefox(service=service, options=options)

            try:
                # Open the SVG file
                svg_url = f"file://{os.path.abspath(svg_path)}"
                driver.get(svg_url)

                # Wait for rendering
                time.sleep(wait_time)

                # Take screenshot
                driver.save_screenshot(png_path)
                return True

            finally:
                driver.quit()

        except (OSError, RuntimeError, ValueError):
            # Silently ignore conversion errors - they will be handled by the caller
            return False

    def display_image(self, png_path: Path, svg_path: Path) -> None:
        """Load image, crop whitespace, resize to selected size, save as PNG, and display."""
        try:
            # Open image
            original_image = Image.open(png_path)

            # Remove alpha channel if present and crop whitespace
            cropped_image = crop_whitespace(original_image, margin=5)

            # Resize with high-quality antialiasing
            image_resized = cropped_image.resize((self.image_width, self.image_height), Image.Resampling.LANCZOS)

            # Ensure it's RGB (should already be from crop_whitespace)
            if image_resized.mode != "RGB":
                image_resized = image_resized.convert("RGB")

            # Save the processed image as PNG
            processed_png_path = Path(self.temp_dir) / f"processed_{self.image_width}x{self.image_height}.png"
            image_resized.save(processed_png_path, "PNG")

            # Convert to PPM format for Tkinter display (avoids ImageTk issues)
            temp_ppm_path = Path(self.temp_dir) / "temp_display.ppm"
            image_resized.save(temp_ppm_path, "PPM")

            # Create Tkinter PhotoImage from PPM file
            self.current_image = tk.PhotoImage(file=str(temp_ppm_path))

            # Update image label
            self.image_label.configure(image=self.current_image, text="")

            # Calculate and display file sizes (including processed PNG)
            self.update_size_info(svg_path, png_path, processed_png_path, temp_ppm_path)

        except (OSError, RuntimeError, ValueError) as e:
            messagebox.showerror("Error", f"Error displaying image: {e!s}")
            self.size_info_var.set("Error processing image")

    def format_file_size(self, size_bytes: int) -> str:
        """Format file size in human readable format."""
        if size_bytes < 1024:
            return f"{size_bytes} B"
        if size_bytes < 1024 * 1024:
            return f"{size_bytes / 1024:.1f} KB"
        return f"{size_bytes / (1024 * 1024):.1f} MB"

    def update_size_info(self, svg_path: Path, original_png_path: Path, processed_png_path: Path, ppm_path: Path) -> None:
        """Update the file size information display."""
        try:
            svg_size = svg_path.stat().st_size
            original_png_size = original_png_path.stat().st_size
            processed_png_size = processed_png_path.stat().st_size
            ppm_size = ppm_path.stat().st_size

            size_text = (
                f"SVG: {self.format_file_size(svg_size)}  |  "
                f"Original PNG: {self.format_file_size(original_png_size)}  |  "
                f"Processed PNG: {self.format_file_size(processed_png_size)}  |  "
                f"PPM: {self.format_file_size(ppm_size)}"
            )

            self.size_info_var.set(size_text)

        except (OSError, RuntimeError, ValueError) as e:
            self.size_info_var.set(f"Error reading file sizes: {e!s}")

    def on_closing(self) -> None:
        """Handle application closing."""
        # Cleanup temporary files
        with contextlib.suppress(Exception):
            shutil.rmtree(self.temp_dir, ignore_errors=True)

        self.root.destroy()


def main() -> None:
    """
    Main function to run the SVG viewer application.

    This application allows you to select and view SVG motor diagram files from the
    ../ardupilot_methodic_configurator/images directory. SVGs are rendered using Firefox-geckodriver
    and displayed as resized images in a Tkinter GUI. You can select the output image width and height
    and the render wait time using command-line arguments.

    Parameters
    ----------
        --image-width: Width of the displayed/resized image in pixels (default: DEFAULT_IMAGE_WIDTH)
        --image-height: Height of the displayed/resized image in pixels (default: DEFAULT_IMAGE_HEIGHT)
        --render-wait: Seconds to wait for SVG rendering before screenshot (default: 2)

    """
    parser = argparse.ArgumentParser(
        description="SVG Viewer Application for ArduPilot Motor Diagrams. "
        "Renders SVGs using Firefox-geckodriver and displays them as resized images in a Tkinter GUI."
    )
    parser.add_argument(
        "--image-width",
        type=int,
        default=DEFAULT_IMAGE_WIDTH,
        help="Width of the displayed/resized image in pixels (default: %(default)s)",
    )
    parser.add_argument(
        "--image-height",
        type=int,
        default=DEFAULT_IMAGE_HEIGHT,
        help="Height of the displayed/resized image in pixels (default: %(default)s)",
    )
    parser.add_argument(
        "--render-wait",
        type=float,
        default=2.0,
        help="Seconds to wait for SVG rendering before screenshot (default: %(default)s)",
    )
    args = parser.parse_args()

    # Check if geckodriver is available
    if not os.path.exists("/usr/bin/geckodriver"):
        messagebox.showerror(
            "Error",
            "geckodriver not found at /usr/bin/geckodriver\nPlease install it with: sudo apt install firefox-geckodriver",
        )
        return

    # Create and run the application
    root = tk.Tk()
    SVGViewerApp(
        root,
        image_width=args.image_width,
        image_height=args.image_height,
        render_wait=args.render_wait,
    )
    root.mainloop()


if __name__ == "__main__":
    main()
