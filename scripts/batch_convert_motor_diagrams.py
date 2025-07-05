#!/usr/bin/env python3
"""
Batch convert all motor diagrams from SVG to PNG.

Using Firefox rendering to preserve 3D transforms and create a size comparison table.

The conversion process:
1. Renders SVG to 1200x1200 canvas using Firefox-geckodriver
2. Crops whitespace around the image
3. Removes alpha channel (converts to RGB)
4. Anti-aliasing resize to target size (default 200x200)
5. Saves as PNG without alpha channel

This file is part of ArduPilot methodic configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2025 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>
SPDX-License-Identifier: GPL-3.0-or-later
"""

import argparse
import csv
import logging
import os
import shutil
from io import BytesIO
from pathlib import Path
from typing import Union

from PIL import Image
from selenium import webdriver
from selenium.webdriver.firefox.options import Options as FirefoxOptions
from selenium.webdriver.firefox.service import Service as FirefoxService
from webdriver_manager.firefox import GeckoDriverManager

DEFAULT_RESIZE_WIDTH: int = 200
DEFAULT_RESIZE_HEIGHT: int = 200

# Set up logging at module level
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def crop_whitespace(image: Image.Image, margin: int = 5) -> Image.Image:
    """Crop whitespace around image, leaving specified margin."""
    # Convert to RGB if needed for cropping
    if image.mode == "RGBA":
        # Create white background for transparency
        background = Image.new("RGB", image.size, (255, 255, 255))
        background.paste(image, mask=image.split()[-1])
        image = background
    elif image.mode != "RGB":
        image = image.convert("RGB")

    # Find the bounding box of non-white content
    # Convert to grayscale for easier processing
    gray = image.convert("L")

    # Get bounding box (left, top, right, bottom) of non-white content
    # We consider anything not pure white (255) as content
    bbox = gray.point(lambda x: 0 if x == 255 else 1, mode="1").getbbox()

    if bbox is None:
        # If the image is entirely white, return original with margin
        return image

    left, top, right, bottom = bbox

    # Add margin while staying within image bounds
    width, height = image.size
    left = max(0, left - margin)
    top = max(0, top - margin)
    right = min(width, right + margin)
    bottom = min(height, bottom + margin)

    # Crop the image
    return image.crop((left, top, right, bottom))


def setup_firefox_service() -> tuple[Union[FirefoxService, None], str]:
    """Set up Firefox service with geckodriver fallback logic."""
    # Create Firefox driver with fallback for geckodriver
    try:
        # Try to use system geckodriver first
        geckodriver_path = shutil.which("geckodriver")
        if geckodriver_path:
            return FirefoxService(executable_path=geckodriver_path), "Success"
        # Fallback to webdriver_manager (may hit rate limit)
        return FirefoxService(GeckoDriverManager().install()), "Success"
    except (OSError, RuntimeError, ValueError) as e:
        # If webdriver_manager fails due to rate limit, try common system paths
        common_paths = [
            "geckodriver.exe",  # Windows executable
            "geckodriver",  # Unix executable
            "/usr/bin/geckodriver",
            "/usr/local/bin/geckodriver",
            "/snap/bin/geckodriver",
            "C:\\Program Files\\geckodriver\\geckodriver.exe",  # Windows common install
            "C:\\Windows\\System32\\geckodriver.exe",  # Windows system path
        ]

        for path in common_paths:
            if os.path.exists(path) or shutil.which(path):
                try:
                    logger.info("Using geckodriver: %s", path)  # Debug output
                    return FirefoxService(executable_path=path), "Success"
                except (OSError, RuntimeError, ValueError) as exc:
                    # Log the exception but continue trying other paths
                    logger.warning("Failed to create FirefoxService with %s: %s", path, exc)
                    continue

        return None, f"Geckodriver not found. Please install geckodriver. Original error: {e!s}"


def process_image(png_data: bytes, resize_width: int, resize_height: int) -> Image.Image:
    """Process PNG screenshot: crop, remove alpha, resize to (resize_width, resize_height)."""
    image = Image.open(BytesIO(png_data))
    cropped_image = crop_whitespace(image, margin=5)
    if cropped_image.mode == "RGBA":
        background = Image.new("RGB", cropped_image.size, (255, 255, 255))
        background.paste(cropped_image, mask=cropped_image.split()[-1])
        cropped_image = background
    elif cropped_image.mode != "RGB":
        cropped_image = cropped_image.convert("RGB")
    return cropped_image.resize((resize_width, resize_height), Image.Resampling.LANCZOS)


def convert_with_firefox(  # pylint: disable=too-many-arguments, too-many-positional-arguments
    svg_path: str,
    png_path: str,
    canvas_width: int = 1200,
    canvas_height: int = 1200,
    resize_width: int = 200,
    resize_height: int = 200,
) -> tuple[bool, str]:
    """
    Convert SVG to PNG using Firefox browser with image processing pipeline.

    Pipeline:
    1. Render SVG to large canvas (default 1200x1200) for high quality
    2. Crop whitespace around image content
    3. Remove alpha channel (convert to RGB)
    4. Anti-aliasing resize to target size (default 200x200)
    5. Save as PNG without alpha channel
    """
    driver = None
    try:
        firefox_options = FirefoxOptions()
        firefox_options.add_argument("--headless")
        firefox_options.add_argument("--no-sandbox")
        firefox_options.add_argument("--disable-dev-shm-usage")

        # Set up Firefox service
        service, error_msg = setup_firefox_service()
        if service is None:
            return False, error_msg

        driver = webdriver.Firefox(service=service, options=firefox_options)

        # Set window size to large canvas for high quality rendering
        driver.set_window_size(canvas_width, canvas_height)

        # Convert SVG path to absolute path and handle Windows paths
        svg_abs_path = os.path.abspath(svg_path)

        # Convert Windows path to file URL format
        if os.name == "nt":  # Windows
            # Replace backslashes with forward slashes and handle drive letter
            svg_abs_path = svg_abs_path.replace("\\", "/")
            svg_abs_path = f"file:///{svg_abs_path}" if svg_abs_path[1] == ":" else f"file://{svg_abs_path}"
        else:
            svg_abs_path = f"file://{svg_abs_path}"

        logger.info("Opening URL: %s", svg_abs_path)  # Debug output

        # Open SVG file
        driver.get(svg_abs_path)

        # Take screenshot
        png_data = driver.get_screenshot_as_png()
        processed_image = process_image(png_data, resize_width, resize_height)
        processed_image.save(png_path, "PNG")
        return True, "Success"
    except (OSError, RuntimeError, ValueError) as e:
        return False, str(e)
    finally:
        if driver:
            driver.quit()


def print_comparison_table(comparison_data: list[dict], png_path: Path) -> None:  # pylint: disable=too-many-locals
    """Print the file size comparison table and save to CSV."""
    logger.info("\nFile Size Comparison Table:")
    logger.info("=" * 80)
    logger.info("%-35s %-12s %-12s %-10s", "Filename", "SVG Size", "PNG Size", "PNG/SVG %")
    logger.info("-" * 80)

    total_svg_size = 0
    total_png_size = 0

    for data in comparison_data:
        filename = data["filename"]
        svg_size = int(data["svg_size"])
        png_size = int(data["png_size"])
        ratio = data["ratio_percent"]

        # Format sizes
        svg_size_str = f"{svg_size:,} B" if svg_size < 1024 else f"{svg_size / 1024:.1f} KB"
        png_size_str = f"{png_size:,} B" if png_size < 1024 else f"{png_size / 1024:.1f} KB"

        logger.info("%-35s %-12s %-12s %7.1f%%", filename, svg_size_str, png_size_str, ratio)
        total_svg_size += svg_size
        total_png_size += png_size

    logger.info("-" * 80)

    # Summary statistics
    total_svg_str = f"{total_svg_size:,} B" if total_svg_size < 1024 * 1024 else f"{total_svg_size / (1024 * 1024):.1f} MB"
    total_png_str = f"{total_png_size:,} B" if total_png_size < 1024 * 1024 else f"{total_png_size / (1024 * 1024):.1f} MB"
    overall_ratio = (total_png_size / total_svg_size) * 100 if total_svg_size > 0 else 0

    logger.info("%-35s %-12s %-12s %7.1f%%", "TOTAL", total_svg_str, total_png_str, overall_ratio)
    avg_svg_kb = total_svg_size / len(comparison_data) / 1024
    avg_png_kb = total_png_size / len(comparison_data) / 1024
    logger.info("%-35s %.1f KB    %.1f KB    %7.1f%%", "AVERAGE", avg_svg_kb, avg_png_kb, overall_ratio)

    # Save to CSV
    csv_file = png_path / "size_comparison.csv"
    with open(csv_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["filename", "svg_size", "png_size", "ratio_percent"])
        writer.writeheader()
        writer.writerows(comparison_data)

    logger.info("\nDetailed comparison saved to: %s", csv_file)


def batch_convert_and_compare(  # pylint: disable=too-many-locals, too-many-arguments, too-many-positional-arguments
    svg_dir: str,
    png_dir: str,
    canvas_width: int = 1200,
    canvas_height: int = 1200,
    resize_width: int = 200,
    resize_height: int = 200,
) -> None:
    """Convert all SVG files with image processing pipeline and create comparison table."""
    svg_path = Path(svg_dir)
    png_path = Path(png_dir)
    png_path.mkdir(parents=True, exist_ok=True)

    logger.info("Looking for SVG files in: %s", svg_path.absolute())

    # Find all motor diagram SVG files
    svg_files = list(svg_path.glob("m_*.svg"))
    svg_files.sort()

    logger.info(
        "Found %d SVG files: %s%s", len(svg_files), [f.name for f in svg_files[:5]], "..." if len(svg_files) > 5 else ""
    )

    if not svg_files:
        logger.warning("No motor diagram SVG files found in %s", svg_dir)
        return

    logger.info("Converting %d motor diagram files...", len(svg_files))

    # Data for comparison table
    comparison_data = []

    success_count = 0

    for i, svg_file in enumerate(svg_files):
        png_file = png_path / (svg_file.stem + ".png")
        logger.info("Converting %s (%d/%d)...", svg_file.name, i + 1, len(svg_files))
        success, message = convert_with_firefox(
            str(svg_file), str(png_file), canvas_width, canvas_height, resize_width, resize_height
        )
        if success:
            logger.info("✓ Conversion successful.")
            success_count += 1

            # Get file sizes
            svg_size = svg_file.stat().st_size
            png_size = png_file.stat().st_size
            size_ratio = (png_size / svg_size) * 100 if svg_size > 0 else 0

            comparison_data.append(
                {"filename": svg_file.name, "svg_size": svg_size, "png_size": png_size, "ratio_percent": size_ratio}
            )
        else:
            logger.error("Conversion failed for %s: %s", svg_file.name, message)

    logger.info("\nConversion complete: %d/%d files successful", success_count, len(svg_files))

    # Create comparison table
    if comparison_data:
        print_comparison_table(comparison_data, png_path)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Batch convert all motor diagrams from SVG to PNG using Firefox rendering.")
    parser.add_argument(
        "--svg-dir",
        type=str,
        default="../ardupilot_methodic_configurator/images/",
        help="Directory containing SVG motor diagrams (default: %(default)s)",
    )
    parser.add_argument(
        "--png-dir",
        type=str,
        default="../motor_diagrams_png_200x200/",
        help="Directory to save converted PNG images (default: %(default)s)",
    )
    parser.add_argument(
        "--canvas-width",
        type=int,
        default=1200,
        help="Width of Firefox rendering canvas in pixels (default: %(default)s)",
    )
    parser.add_argument(
        "--canvas-height",
        type=int,
        default=1200,
        help="Height of Firefox rendering canvas in pixels (default: %(default)s)",
    )
    parser.add_argument(
        "--resize-width",
        type=int,
        default=DEFAULT_RESIZE_WIDTH,
        help="Width of output PNG images in pixels (default: %(default)s)",
    )
    parser.add_argument(
        "--resize-height",
        type=int,
        default=DEFAULT_RESIZE_HEIGHT,
        help="Height of output PNG images in pixels (default: %(default)s)",
    )
    parser.add_argument(
        "--loglevel",
        type=str,
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        default="INFO",
        help="Set logging level (default: %(default)s)",
    )

    args = parser.parse_args()

    # Update logging level
    logger.setLevel(args.loglevel)

    logger.info("Starting motor diagram batch conversion...")
    try:
        # Convert all motor diagrams with new processing pipeline:
        # - Customizable canvas size for high quality rendering
        # - Crop whitespace around content
        # - Remove alpha channel
        # - Anti-aliasing resize to user-specified size
        # - Save as optimized PNG
        # Note: Output PNGs will be resized to (resize_width, resize_height)
        # Example usage:
        #   python batch_convert_motor_diagrams.py \
        #       --svg-dir ./images \
        #       --png-dir ./pngs \
        #       --resize-width 200 \
        #       --resize-height 200 \
        #       --loglevel DEBUG
        batch_convert_and_compare(
            args.svg_dir,
            args.png_dir,
            canvas_width=args.canvas_width,
            canvas_height=args.canvas_height,
            resize_width=args.resize_width,
            resize_height=args.resize_height,
        )
        logger.info("Conversion completed successfully!")
    except (OSError, RuntimeError, ValueError) as e:
        logger.error("Error during conversion: %s", e)
        import traceback

        traceback.print_exc()
