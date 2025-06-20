#!/usr/bin/env python3

"""
Behavior-driven tests for the BaseWindow class.

This file is part of Ardupilot methodic configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2025 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import contextlib
import os
import tempfile
import tkinter as tk
from collections.abc import Callable, Generator
from pathlib import Path
from tkinter import ttk
from typing import Any, NamedTuple, Optional
from unittest.mock import MagicMock, patch

import pytest
from PIL import Image

from ardupilot_methodic_configurator.frontend_tkinter_base_window import BaseWindow

# pylint: disable=protected-access


# ==================== TEST CONFIGURATION ====================


class MockConfiguration(NamedTuple):
    """Configuration for common mocking patterns."""

    patch_tkinter: bool = True
    patch_icon_setup: bool = True
    patch_theme_setup: bool = True
    patch_dpi_detection: bool = True
    dpi_scaling_factor: float = 1.0


# ==================== FIXTURES ====================


@pytest.fixture(autouse=True)
def test_environment() -> Generator[None, None, None]:
    """Ensure consistent test environment for all BaseWindow tests."""
    original_env = os.environ.get("PYTEST_CURRENT_TEST")
    os.environ["PYTEST_CURRENT_TEST"] = "true"

    yield

    if original_env is None:
        os.environ.pop("PYTEST_CURRENT_TEST", None)
    else:
        os.environ["PYTEST_CURRENT_TEST"] = original_env


@pytest.fixture
def tk_root() -> Generator[tk.Tk, None, None]:
    """Provide a real Tkinter root for integration tests."""
    try:
        root = tk.Tk()
        root.withdraw()
        yield root
    except tk.TclError:
        pytest.skip("Tkinter not available in test environment")
    finally:
        if "root" in locals():
            with contextlib.suppress(tk.TclError):
                root.destroy()


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


@pytest.fixture
def dpi_test_window(mock_tkinter_context) -> Callable[[float, float], tuple[BaseWindow, contextlib.ExitStack]]:
    """Specialized fixture for DPI testing that doesn't mock DPI detection."""

    def _create_dpi_window(mock_dpi: float, tk_scaling: float = 1.0) -> tuple[BaseWindow, contextlib.ExitStack]:
        config = MockConfiguration(patch_dpi_detection=False)
        stack, patches = mock_tkinter_context(config)

        for patch_obj in patches:
            stack.enter_context(patch_obj)

        mock_tk = stack.enter_context(patch("tkinter.Tk"))
        mock_root = MagicMock()
        mock_root.winfo_fpixels.return_value = mock_dpi
        mock_root.tk.call.return_value = tk_scaling
        mock_tk.return_value = mock_root

        window = BaseWindow()
        return window, stack

    return _create_dpi_window


@pytest.fixture
def image_test_context() -> Callable[[tuple[int, int], bool], Any]:
    """Specialized fixture for image testing with proper mocks."""

    @contextlib.contextmanager
    def _image_context(image_size: tuple[int, int] = (100, 50), file_exists: bool = True) -> Generator[dict, None, None]:
        with (
            patch("os.path.isfile", return_value=file_exists),
            patch("PIL.Image.open") as mock_open,
            patch("PIL.ImageTk.PhotoImage") as mock_photo,
            patch("tkinter.ttk.Label") as mock_label,
        ):
            # Setup image mocks
            mock_image = MagicMock()
            mock_image.size = image_size
            mock_resized_image = MagicMock()
            mock_image.resize.return_value = mock_resized_image
            mock_open.return_value = mock_image

            # Setup photo and label mocks
            mock_photo_instance = MagicMock()
            mock_photo.return_value = mock_photo_instance
            mock_label_instance = MagicMock()
            mock_label.return_value = mock_label_instance

            yield {
                "image": mock_image,
                "resized_image": mock_resized_image,
                "photo": mock_photo_instance,
                "label": mock_label_instance,
                "open_mock": mock_open,
                "photo_mock": mock_photo,
                "label_mock": mock_label,
            }

    return _image_context


@pytest.fixture
def sample_image_file() -> Generator[str, None, None]:
    """Create a real temporary image file for testing."""
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
        img = Image.new("RGB", (100, 50), color="red")
        img.save(tmp.name)
        tmp_path = tmp.name

    yield tmp_path
    Path(tmp_path).unlink(missing_ok=True)


# ==================== BEHAVIOR-FOCUSED TESTS ====================


class TestWindowCreationBehavior:
    """Test window creation scenarios from user perspective."""

    def test_application_starts_with_main_window(self, mock_tkinter_context) -> None:
        """
        Application starts with main window.

        GIVEN: User starts the application
        WHEN: No parent window exists
        THEN: Should create a main application window with icon and theming
        """
        stack, patches = mock_tkinter_context()

        with stack:
            for patch_obj in patches:
                stack.enter_context(patch_obj)

            mock_tk = stack.enter_context(patch("tkinter.Tk"))
            mock_root = MagicMock()
            mock_tk.return_value = mock_root

            window = BaseWindow()

            # Verify main window creation
            mock_tk.assert_called_once()
            assert window.root == mock_root
            assert hasattr(window, "main_frame")

    def test_dialog_opens_as_child_window(self, tk_root) -> None:
        """
        Dialog opens as child window.

        GIVEN: User interacts with main application
        WHEN: A dialog needs to be shown
        THEN: Should create child window that doesn't interfere with main window
        """
        with (
            patch.object(BaseWindow, "_setup_application_icon") as mock_icon,
            patch.object(BaseWindow, "_setup_theme_and_styling"),
            patch.object(BaseWindow, "_get_dpi_scaling_factor", return_value=1.0),
        ):
            child_window = BaseWindow(tk_root)

            # Verify child window behavior
            assert isinstance(child_window.root, tk.Toplevel)
            mock_icon.assert_not_called()  # Child windows don't set icons


class TestDisplayScalingBehavior:
    """Test how the application adapts to different display configurations."""

    @pytest.mark.parametrize(
        ("system_dpi", "expected_scaling"),
        [
            (96, 1.0),  # Standard 1080p monitor
            (144, 1.5),  # 150% Windows scaling
            (192, 2.0),  # 4K monitor with 200% scaling
            (120, 1.25),  # Intermediate scaling
        ],
    )
    def test_adapts_to_system_display_scaling(self, dpi_test_window, system_dpi, expected_scaling) -> None:
        """
        Application adapts to system display scaling.

        GIVEN: User has different DPI/scaling configurations
        WHEN: Application starts
        THEN: Should detect and apply appropriate scaling factor
        """
        window, stack = dpi_test_window(system_dpi)

        with stack:
            scaling_factor = window._get_dpi_scaling_factor()
            assert scaling_factor == expected_scaling

    def test_falls_back_gracefully_when_dpi_detection_fails(self, dpi_test_window) -> None:
        """
        Falls back gracefully when DPI detection fails.

        GIVEN: User's system has unusual DPI configuration
        WHEN: DPI detection encounters errors
        THEN: Should use safe default scaling to remain functional
        """
        # Simulate DPI detection failure
        with patch("tkinter.Tk") as mock_tk:
            mock_root = MagicMock()
            mock_root.winfo_fpixels.side_effect = tk.TclError("No display")
            mock_tk.return_value = mock_root

            with (
                patch.object(BaseWindow, "_setup_application_icon"),
                patch.object(BaseWindow, "_setup_theme_and_styling"),
            ):
                window = BaseWindow()
                scaling_factor = window._get_dpi_scaling_factor()
                assert scaling_factor == 1.0  # Safe default

    @pytest.mark.parametrize(
        ("font_size", "scaling", "expected"),
        [
            (10, 1.0, 10),  # No scaling
            (12, 1.5, 18),  # 150% scaling
            (8, 2.0, 16),  # 200% scaling
        ],
    )
    def test_scales_fonts_for_readability(self, mock_tkinter_context, font_size, scaling, expected) -> None:
        """
        Scales fonts for readability across different displays.

        GIVEN: User has high-DPI display
        WHEN: Text needs to be displayed
        THEN: Should scale font sizes to maintain readability
        """
        config = MockConfiguration(dpi_scaling_factor=scaling)
        stack, patches = mock_tkinter_context(config)

        with stack:
            for patch_obj in patches:
                stack.enter_context(patch_obj)

            window = BaseWindow()
            scaled_size = window.calculate_scaled_font_size(font_size)
            assert scaled_size == expected


class TestImageDisplayBehavior:
    """Test how images are displayed to users."""

    def test_displays_images_with_proper_sizing(self, image_test_context, sample_image_file) -> None:
        """
        Displays images with proper sizing.

        GIVEN: User interface needs to show an image
        WHEN: Image is loaded into a label
        THEN: Should resize image maintaining aspect ratio and display correctly
        """
        with image_test_context() as mocks:
            parent_frame = MagicMock()

            result = BaseWindow.put_image_in_label(parent_frame, sample_image_file, image_height=40)

            # Verify behavior from user perspective
            assert result == mocks["label"]
            mocks["open_mock"].assert_called_once_with(sample_image_file)
            mocks["image"].resize.assert_called_once()
            mocks["photo_mock"].assert_called_once_with(mocks["resized_image"])

    def test_shows_fallback_when_image_unavailable(self, image_test_context) -> None:
        """
        Shows fallback when image unavailable.

        GIVEN: User interface references a missing image
        WHEN: Image cannot be loaded
        THEN: Should show fallback text instead of crashing
        """
        with image_test_context(file_exists=False) as mocks:
            parent_frame = MagicMock()

            result = BaseWindow.put_image_in_label(parent_frame, "missing_image.png", fallback_text="Image not available")

            # Should create label with fallback text
            mocks["label_mock"].assert_called_with(parent_frame, text="Image not available")
            assert result == mocks["label"]

    @pytest.mark.parametrize(
        ("original_size", "target_height", "expected_width"),
        [
            ((200, 100), 50, 100),  # 2:1 aspect ratio
            ((300, 150), 75, 150),  # 2:1 aspect ratio
            ((100, 200), 100, 50),  # 1:2 aspect ratio
        ],
    )
    def test_maintains_image_aspect_ratios(self, image_test_context, original_size, target_height, expected_width) -> None:
        """
        Maintains image aspect ratios.

        GIVEN: Images with various aspect ratios
        WHEN: Resizing to fit UI constraints
        THEN: Should maintain original aspect ratio
        """
        with image_test_context(image_size=original_size) as mocks:
            parent_frame = MagicMock()

            BaseWindow.put_image_in_label(parent_frame, "test_image.png", image_height=target_height)

            # Verify aspect ratio is maintained
            expected_size = (expected_width, target_height)
            mocks["image"].resize.assert_called_once_with(expected_size, Image.Resampling.LANCZOS)


class TestErrorResilienceBehavior:
    """Test how application handles error conditions gracefully."""

    def test_continues_when_icon_loading_fails(self) -> None:
        """
        Continues when icon loading fails.

        GIVEN: User's system has icon loading issues
        WHEN: Application attempts to set window icon
        THEN: Should log error but continue functioning normally
        """
        # Remove test environment marker to trigger icon loading
        env_without_pytest = {k: v for k, v in os.environ.items() if k != "PYTEST_CURRENT_TEST"}

        with (
            patch.dict(os.environ, env_without_pytest, clear=True),
            patch("tkinter.Tk"),
            patch.object(BaseWindow, "_setup_theme_and_styling"),
            patch.object(BaseWindow, "_get_dpi_scaling_factor", return_value=1.0),
            patch(
                "ardupilot_methodic_configurator.frontend_tkinter_base_window.LocalFilesystem.application_icon_filepath",
                return_value="test_icon.png",
            ),
            patch("tkinter.PhotoImage"),
            patch("ardupilot_methodic_configurator.frontend_tkinter_base_window.logging_error") as mock_log,
        ):
            window = BaseWindow()
            window.root = MagicMock()
            window.root.iconphoto.side_effect = tk.TclError("Icon error")

            # Should handle error gracefully
            window._setup_application_icon()
            mock_log.assert_called_once()

    def test_provides_safe_defaults_when_configuration_fails(self, mock_tkinter_context) -> None:
        """
        Provides safe defaults when configuration fails.

        GIVEN: User's system has configuration issues
        WHEN: Various setup operations fail
        THEN: Should provide reasonable defaults to maintain usability
        """
        config = MockConfiguration(patch_dpi_detection=False)
        stack, patches = mock_tkinter_context(config)

        with stack:
            for patch_obj in patches:
                stack.enter_context(patch_obj)

            # Mock DPI detection failure
            mock_tk = stack.enter_context(patch("tkinter.Tk"))
            mock_root = MagicMock()
            mock_root.winfo_fpixels.side_effect = tk.TclError("Display error")
            mock_tk.return_value = mock_root

            window = BaseWindow()
            scaling_factor = window._get_dpi_scaling_factor()
            assert scaling_factor == 1.0  # Safe fallback


class TestWindowManagementBehavior:
    """Test window positioning and management from user perspective."""

    def test_centers_dialogs_on_parent_window(self, tk_root) -> None:
        """
        Centers dialogs on parent window.

        GIVEN: User opens a dialog from main window
        WHEN: Dialog needs to be positioned
        THEN: Should appear centered on the parent window
        """
        child = tk.Toplevel(tk_root)
        tk_root.geometry("400x300+100+100")
        child.geometry("200x150")

        BaseWindow.center_window(child, tk_root)

        # Verify positioning (allowing for window manager differences)
        child.update_idletasks()
        assert child.winfo_x() >= 0
        assert child.winfo_y() >= 0

        child.destroy()

    def test_handles_edge_cases_in_window_positioning(self, tk_root) -> None:
        """
        Handles edge cases in window positioning.

        GIVEN: Unusual window sizes or positions
        WHEN: Attempting to position windows
        THEN: Should handle gracefully without errors
        """
        child = tk.Toplevel(tk_root)
        child.geometry("1x1")  # Minimal size

        # Should not raise exceptions
        BaseWindow.center_window(child, tk_root)

        child.destroy()

    def test_window_destruction_cleanup(self, tk_root) -> None:
        """
        Window destruction cleanup.

        GIVEN: User closes application windows
        WHEN: Windows are destroyed
        THEN: Should clean up resources properly
        """
        window = BaseWindow(tk_root)

        # Verify window exists initially
        assert window.root.winfo_exists()

        # Simulate window destruction
        window.root.destroy()

        # Should handle cleanup gracefully - window should be destroyed
        assert not window.root.winfo_exists()

    @pytest.mark.parametrize("extreme_dpi", [48, 480, 960])  # Very low and very high DPI
    def test_extreme_dpi_scenarios(self, dpi_test_window, extreme_dpi) -> None:
        """
        Extreme DPI scenarios.

        GIVEN: User has extremely high or low DPI displays
        WHEN: Application detects DPI
        THEN: Should handle gracefully with reasonable bounds
        """
        window, stack = dpi_test_window(extreme_dpi)

        with stack:
            scaling_factor = window._get_dpi_scaling_factor()
            # Should be reasonable (between 0.5 and 10.0)
            assert 0.5 <= scaling_factor <= 10.0

    def test_memory_management_for_images(self, image_test_context, sample_image_file) -> None:
        """
        Memory management for images.

        GIVEN: Application loads multiple images
        WHEN: Images are displayed in labels
        THEN: Should maintain references to prevent garbage collection
        """
        with image_test_context() as mocks:
            parent_frame = MagicMock()

            label = BaseWindow.put_image_in_label(parent_frame, sample_image_file)

            # Should maintain image reference
            assert hasattr(label, "image") or hasattr(mocks["label"], "image")


# ==================== INTEGRATION TESTS ====================


@pytest.mark.integration
class TestCompleteWorkflows:
    """Test complete user workflows end-to-end with real Tkinter."""

    def test_complete_application_startup_workflow(self, tk_root) -> None:
        """
        Complete application startup workflow.

        GIVEN: User starts the application
        WHEN: Application initializes completely
        THEN: Should have functional window with proper theme and scaling
        """
        window = BaseWindow(tk_root)

        # Verify complete initialization
        assert isinstance(window.root, tk.Toplevel)
        assert isinstance(window.main_frame, ttk.Frame)
        assert window.dpi_scaling_factor > 0

        # Verify theme is applied
        style = ttk.Style()
        assert style.theme_use() in ["alt", "clam", "default"]  # Valid themes

    def test_main_window_creation_workflow(self) -> None:
        """
        Main window creation workflow.

        GIVEN: User starts application without parent window
        WHEN: Creating main window
        THEN: Should create root Tk window with all components
        """
        window = None
        try:
            window = BaseWindow()

            # Verify main window components
            assert isinstance(window.root, tk.Tk)
            assert isinstance(window.main_frame, ttk.Frame)
            assert hasattr(window, "dpi_scaling_factor")

            # Verify window is configured properly
            assert window.root.winfo_exists()

        except tk.TclError:
            pytest.skip("Tkinter display not available")
        finally:
            if window is not None and hasattr(window, "root"):
                with contextlib.suppress(tk.TclError):
                    window.root.destroy()

    def test_dialog_window_creation_workflow(self, tk_root) -> None:
        """
        Dialog window creation workflow.

        GIVEN: User opens dialog from main application
        WHEN: Creating child window
        THEN: Should create Toplevel window properly centered
        """
        # Create main window
        main_window = BaseWindow(tk_root)

        # Create dialog window - pass the root as parent for type compatibility
        dialog_window = BaseWindow(tk_root)

        # Verify dialog structure
        assert isinstance(dialog_window.root, tk.Toplevel)
        assert dialog_window.root.master == tk_root

        # Verify both windows coexist
        assert main_window.root.winfo_exists()
        assert dialog_window.root.winfo_exists()

    def test_multi_window_management_workflow(self, tk_root) -> None:
        """
        Multi-window management workflow.

        GIVEN: User has multiple windows open
        WHEN: Managing multiple BaseWindow instances
        THEN: Should handle multiple windows without conflicts
        """
        windows = []

        try:
            # Create multiple child windows
            for i in range(3):
                window = BaseWindow(tk_root)
                window.root.title(f"Test Window {i}")
                windows.append(window)

            # All windows should exist
            for window in windows:
                assert window.root.winfo_exists()
                assert isinstance(window.main_frame, ttk.Frame)

            # Each should have independent DPI scaling
            scaling_factors = [w.dpi_scaling_factor for w in windows]
            assert all(factor > 0 for factor in scaling_factors)

        finally:
            # Cleanup
            for window in windows:
                with contextlib.suppress(tk.TclError):
                    window.root.destroy()


@pytest.mark.integration
class TestRealImageIntegration:
    """Test image operations with real files and Tkinter."""

    def test_real_image_loading_integration(self, tk_root, sample_image_file) -> None:
        """
        Real image loading integration.

        GIVEN: Real image file and Tkinter window
        WHEN: Loading image into label
        THEN: Should create functional image label
        """
        window = BaseWindow(tk_root)

        # Load real image
        label = BaseWindow.put_image_in_label(window.main_frame, sample_image_file, image_height=50)

        # Verify label creation
        assert isinstance(label, ttk.Label)
        assert label.master == window.main_frame

        # Should have image reference
        assert hasattr(label, "image") or label.cget("image")

    def test_image_scaling_integration(self, tk_root, sample_image_file) -> None:
        """
        Image scaling integration with real DPI.

        GIVEN: Real image and varying DPI scaling
        WHEN: Loading images at different sizes
        THEN: Should scale images appropriately
        """
        window = BaseWindow(tk_root)

        # Test different image heights
        heights = [25, 50, 100]
        labels = []

        for height in heights:
            label = BaseWindow.put_image_in_label(window.main_frame, sample_image_file, image_height=height)
            labels.append(label)

        # All labels should be created
        assert len(labels) == len(heights)
        for label in labels:
            assert isinstance(label, ttk.Label)

    def test_multiple_image_loading_integration(self, tk_root) -> None:
        """
        Multiple image loading integration.

        GIVEN: Multiple image files
        WHEN: Loading them simultaneously
        THEN: Should handle multiple images without memory issues
        """
        window = BaseWindow(tk_root)
        temp_files = []
        labels = []

        try:
            # Create multiple temporary images
            for i in range(5):
                with tempfile.NamedTemporaryFile(suffix=f"_{i}.png", delete=False) as tmp:
                    img = Image.new("RGB", (50, 25), color=(i * 50, 100, 150))
                    img.save(tmp.name)
                    temp_files.append(tmp.name)

            # Load all images
            for img_file in temp_files:
                label = BaseWindow.put_image_in_label(window.main_frame, img_file, image_height=30)
                labels.append(label)

            # Verify all loaded successfully
            assert len(labels) == len(temp_files)
            for label in labels:
                assert isinstance(label, ttk.Label)

        finally:
            # Cleanup temp files
            for temp_file in temp_files:
                Path(temp_file).unlink(missing_ok=True)


@pytest.mark.integration
class TestThemeIntegration:
    """Test theme and styling integration with real Tkinter."""

    def test_theme_consistency_across_windows(self, tk_root) -> None:
        """
        Theme consistency across windows.

        GIVEN: Multiple BaseWindow instances
        WHEN: Creating windows with themes
        THEN: Should maintain consistent theming across all windows
        """
        windows = []

        try:
            # Create multiple windows
            for _ in range(3):
                window = BaseWindow(tk_root)
                windows.append(window)

            # Check theme consistency
            styles = [ttk.Style() for _ in windows]
            themes = [style.theme_use() for style in styles]

            # All should use the same theme
            assert len(set(themes)) == 1  # All themes should be identical
            assert themes[0] in ["alt", "clam", "default"]

        finally:
            for window in windows:
                with contextlib.suppress(tk.TclError):
                    window.root.destroy()

    def test_dpi_scaling_integration(self, tk_root) -> None:
        """
        DPI scaling integration with real display.

        GIVEN: Real display environment
        WHEN: Detecting and applying DPI scaling
        THEN: Should work with actual system DPI settings
        """
        window = BaseWindow(tk_root)

        # Should detect actual DPI
        dpi_factor = window.dpi_scaling_factor
        assert isinstance(dpi_factor, float)
        assert 0.5 <= dpi_factor <= 5.0  # Reasonable range

        # Font scaling should work
        base_font_size = 12
        scaled_size = window.calculate_scaled_font_size(base_font_size)
        expected_size = int(base_font_size * dpi_factor)
        assert scaled_size == expected_size

        # Padding scaling should work
        base_padding = 10
        scaled_padding = window.calculate_scaled_padding(base_padding)
        expected_padding = int(base_padding * dpi_factor)
        assert scaled_padding == expected_padding


@pytest.mark.integration
class TestWindowPositioningIntegration:
    """Test window positioning with real Tkinter geometry management."""

    def test_window_centering_integration(self, tk_root) -> None:
        """
        Window centering integration.

        GIVEN: Parent and child windows with real geometry
        WHEN: Centering child on parent
        THEN: Should position windows correctly on screen
        """
        # Setup parent window with known size
        tk_root.geometry("400x300+100+100")
        tk_root.update_idletasks()

        # Create child window
        child_window = BaseWindow(tk_root)
        child_window.root.geometry("200x150")

        # Center the child
        BaseWindow.center_window(child_window.root, tk_root)
        child_window.root.update_idletasks()

        # Verify positioning (should be centered)
        parent_x, parent_y = tk_root.winfo_x(), tk_root.winfo_y()
        parent_w, parent_h = tk_root.winfo_width(), tk_root.winfo_height()
        child_x, child_y = child_window.root.winfo_x(), child_window.root.winfo_y()

        # Child should be roughly centered (allowing for window manager differences)
        expected_x = parent_x + (parent_w - 200) // 2
        expected_y = parent_y + (parent_h - 150) // 2

        # Allow some tolerance for window manager variations
        assert abs(child_x - expected_x) <= 50
        assert abs(child_y - expected_y) <= 50

    def test_multiple_window_positioning_integration(self, tk_root) -> None:
        """
        Multiple window positioning integration.

        GIVEN: Multiple child windows
        WHEN: Positioning them relative to parent
        THEN: Should handle multiple positioned windows
        """
        child_windows = []

        try:
            # Create multiple child windows
            for _ in range(3):
                child = BaseWindow(tk_root)
                child.root.geometry("150x100")
                child_windows.append(child)

            # Position each child
            for child in child_windows:
                BaseWindow.center_window(child.root, tk_root)
                child.root.update_idletasks()

            # All should be positioned on screen
            for child in child_windows:
                x, y = child.root.winfo_x(), child.root.winfo_y()
                assert x >= 0  # Should be visible on screen
                assert y >= 0

        finally:
            for child in child_windows:
                with contextlib.suppress(tk.TclError):
                    child.root.destroy()


@pytest.mark.integration
@pytest.mark.slow
class TestPerformanceIntegration:
    """Test performance characteristics with real Tkinter operations."""

    def test_window_creation_performance(self) -> None:
        """
        Window creation performance.

        GIVEN: Performance requirements
        WHEN: Creating multiple windows rapidly
        THEN: Should create windows efficiently without blocking
        """
        import time

        start_time = time.time()
        windows = []

        try:
            # Create 10 windows rapidly
            for _ in range(10):
                window = BaseWindow()
                windows.append(window)

            creation_time = time.time() - start_time

            # Should create windows reasonably quickly (< 5 seconds for 10 windows)
            assert creation_time < 5.0

            # All windows should exist
            for window in windows:
                assert window.root.winfo_exists()

        except tk.TclError:
            pytest.skip("Tkinter display not available")
        finally:
            for window in windows:
                with contextlib.suppress(tk.TclError):
                    window.root.destroy()

    def test_image_loading_performance(self, sample_image_file) -> None:
        """
        Image loading performance.

        GIVEN: Image loading requirements
        WHEN: Loading multiple images
        THEN: Should load images efficiently
        """
        window = None
        try:
            window = BaseWindow()
            import time

            start_time = time.time()
            labels = []

            # Load same image multiple times (simulating gallery)
            for _ in range(20):
                label = BaseWindow.put_image_in_label(window.main_frame, sample_image_file, image_height=40)
                labels.append(label)

            loading_time = time.time() - start_time

            # Should load images reasonably quickly (< 3 seconds for 20 images)
            assert loading_time < 3.0

            # All labels should be created
            assert len(labels) == 20

        except tk.TclError:
            pytest.skip("Tkinter display not available")
        finally:
            if window is not None and hasattr(window, "root"):
                with contextlib.suppress(tk.TclError):
                    window.root.destroy()


if __name__ == "__main__":
    pytest.main([__file__])
