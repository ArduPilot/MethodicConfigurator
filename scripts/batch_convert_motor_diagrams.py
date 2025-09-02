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

import csv
import os
import shutil
from io import BytesIO
from pathlib import Path

from PIL import Image
from selenium import webdriver
from selenium.webdriver.firefox.options import Options as FirefoxOptions
from selenium.webdriver.firefox.service import Service as FirefoxService
from webdriver_manager.firefox import GeckoDriverManager

# ruff: noqa: T201


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


def convert_with_firefox(
    svg_path: str, png_path: str, canvas_width: int = 1200, canvas_height: int = 1200, target_size: int = 200
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
        # Firefox options
        firefox_options = FirefoxOptions()
        firefox_options.add_argument("--headless")
        firefox_options.add_argument("--no-sandbox")
        firefox_options.add_argument("--disable-dev-shm-usage")

        # Create Firefox driver with fallback for geckodriver
        try:
            # Try to use system geckodriver first
            geckodriver_path = shutil.which("geckodriver")
            if geckodriver_path:
                service = FirefoxService(executable_path=geckodriver_path)
            else:
                # Fallback to webdriver_manager (may hit rate limit)
                service = FirefoxService(GeckoDriverManager().install())
        except Exception as e:
            # If webdriver_manager fails due to rate limit, try common system paths
            common_paths = [
                "/usr/bin/geckodriver",
                "/usr/local/bin/geckodriver",
                "/snap/bin/geckodriver",
                "geckodriver",  # PATH lookup
            ]

            service = None
            for path in common_paths:
                if os.path.exists(path) or (path == "geckodriver" and shutil.which("geckodriver")):
                    try:
                        service = FirefoxService(executable_path=path)
                        break
                    except Exception as exc:
                        # Log the exception but continue trying other paths
                        print(f"Warning: Failed to create FirefoxService with {path}: {exc}")
                        continue

            if not service:
                return False, f"Geckodriver not found. Please install geckodriver. Original error: {e!s}"

        driver = webdriver.Firefox(service=service, options=firefox_options)

        # Set window size to large canvas for high quality rendering
        driver.set_window_size(canvas_width, canvas_height)

        # Convert SVG path to absolute path
        svg_abs_path = os.path.abspath(svg_path)

        # Open SVG file
        driver.get(f"file://{svg_abs_path}")

        # Take screenshot
        png_data = driver.get_screenshot_as_png()

        # Load image with PIL for processing
        image = Image.open(BytesIO(png_data))

        # Step 1: Crop whitespace around image content
        cropped_image = crop_whitespace(image, margin=5)

        # Step 2: Remove alpha channel (convert to RGB)
        if cropped_image.mode == "RGBA":
            # Create white background for transparency
            background = Image.new("RGB", cropped_image.size, (255, 255, 255))
            background.paste(cropped_image, mask=cropped_image.split()[-1])
            cropped_image = background
        elif cropped_image.mode != "RGB":
            cropped_image = cropped_image.convert("RGB")

        # Step 3: Anti-aliasing resize to target size
        resized_image = cropped_image.resize((target_size, target_size), Image.Resampling.LANCZOS)

        # Step 4: Save as PNG without alpha channel
        resized_image.save(png_path, "PNG")

        return True, "Success"

    except Exception as e:
        return False, str(e)
    finally:
        if driver:
            driver.quit()


def print_comparison_table(comparison_data: list[dict], png_path: Path) -> None:
    """Print the file size comparison table and save to CSV."""
    print("\nFile Size Comparison Table:")
    print("=" * 80)
    print(f"{'Filename':<35} {'SVG Size':<12} {'PNG Size':<12} {'PNG/SVG %':<10}")
    print("-" * 80)

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

        print(f"{filename:<35} {svg_size_str:<12} {png_size_str:<12} {ratio:>7.1f}%")

        total_svg_size += svg_size
        total_png_size += png_size

    print("-" * 80)

    # Summary statistics
    total_svg_str = f"{total_svg_size:,} B" if total_svg_size < 1024 * 1024 else f"{total_svg_size / (1024 * 1024):.1f} MB"
    total_png_str = f"{total_png_size:,} B" if total_png_size < 1024 * 1024 else f"{total_png_size / (1024 * 1024):.1f} MB"
    overall_ratio = (total_png_size / total_svg_size) * 100 if total_svg_size > 0 else 0

    print(f"{'TOTAL':<35} {total_svg_str:<12} {total_png_str:<12} {overall_ratio:>7.1f}%")
    avg_svg_kb = total_svg_size / len(comparison_data) / 1024
    avg_png_kb = total_png_size / len(comparison_data) / 1024
    print(f"{'AVERAGE':<35} {avg_svg_kb:.1f} KB    {avg_png_kb:.1f} KB    {overall_ratio:>7.1f}%")

    # Save to CSV
    csv_file = png_path / "size_comparison.csv"
    with open(csv_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["filename", "svg_size", "png_size", "ratio_percent"])
        writer.writeheader()
        writer.writerows(comparison_data)

    print(f"\nDetailed comparison saved to: {csv_file}")


def batch_convert_and_compare(
    svg_dir: str, png_dir: str, canvas_width: int = 1200, canvas_height: int = 1200, target_size: int = 200
) -> None:
    """Convert all SVG files with image processing pipeline and create comparison table."""
    svg_path = Path(svg_dir)
    png_path = Path(png_dir)
    png_path.mkdir(parents=True, exist_ok=True)

    # Find all motor diagram SVG files
    svg_files = list(svg_path.glob("m_*.svg"))
    svg_files.sort()

    if not svg_files:
        print(f"No motor diagram SVG files found in {svg_dir}")
        return

    print(f"Converting {len(svg_files)} motor diagram files...")

    # Data for comparison table
    comparison_data = []

    success_count = 0
    for i, svg_file in enumerate(svg_files):
        png_file = png_path / (svg_file.stem + ".png")

        print(f"Converting {svg_file.name} ({i + 1}/{len(svg_files)})...", end=" ")

        success, message = convert_with_firefox(str(svg_file), str(png_file), canvas_width, canvas_height, target_size)

        if success:
            print("✓")
            success_count += 1

            # Get file sizes
            svg_size = svg_file.stat().st_size
            png_size = png_file.stat().st_size
            size_ratio = (png_size / svg_size) * 100 if svg_size > 0 else 0

            comparison_data.append(
                {"filename": svg_file.name, "svg_size": svg_size, "png_size": png_size, "ratio_percent": size_ratio}
            )
        else:
            print(f"✗ {message}")

    print(f"\nConversion complete: {success_count}/{len(svg_files)} files successful")

    # Create comparison table
    if comparison_data:
        print_comparison_table(comparison_data, png_path)


if __name__ == "__main__":
    # Convert all motor diagrams with new processing pipeline:
    # - 1200x1200 canvas for high quality rendering
    # - Crop whitespace around content
    # - Remove alpha channel
    # - Anti-aliasing resize to 200x200
    # - Save as optimized PNG
    batch_convert_and_compare(
        "../ardupilot_methodic_configurator/images/",
        "../motor_diagrams_png_200x200/",
        canvas_width=1200,
        canvas_height=1200,
        target_size=200,
    )
