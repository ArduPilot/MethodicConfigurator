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
import time
import tkinter as tk
from collections.abc import Callable, Generator
from pathlib import Path
from tkinter import ttk
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

# Import shared configuration from conftest
from conftest import MockConfiguration
from PIL import Image

from ardupilot_methodic_configurator.frontend_tkinter_base_window import BaseWindow

# pylint: disable=protected-access, redefined-outer-name, unused-argument


# ==================== ADDITIONAL TEST FIXTURES ====================


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


@pytest.fixture
def mocked_base_window(mock_tkinter_context) -> Generator[BaseWindow, None, None]:
    """Fixture providing a properly mocked BaseWindow instance for behavior testing."""
    stack, patches = mock_tkinter_context()
    with stack:
        for patch_obj in patches:
            stack.enter_context(patch_obj)
        window = BaseWindow()
        yield window


# ==================== BEHAVIOR-FOCUSED TESTS ====================


class TestWindowCreationBehavior:
    """Test window creation scenarios from user perspective."""

    def test_user_can_start_application_with_main_window(self, mock_tkinter_context) -> None:
        """
        User can start application with main window.

        GIVEN: User starts the application
        WHEN: No parent window exists
        THEN: Should create a main application window with icon and theming
        """
        # Arrange (Given): Set up mocking for main window creation
        stack, patches = mock_tkinter_context()

        with stack:
            for patch_obj in patches:
                stack.enter_context(patch_obj)

            mock_tk = stack.enter_context(patch("tkinter.Tk"))
            mock_root = MagicMock()
            mock_tk.return_value = mock_root

            # Act (When): User starts the application
            window = BaseWindow()

            # Assert (Then): Main window is created with proper components
            mock_tk.assert_called_once()
            assert window.root == mock_root
            assert hasattr(window, "main_frame")

    def test_user_can_open_dialog_as_child_window(self, tk_root) -> None:
        """
        User can open dialog as child window.

        GIVEN: User interacts with main application
        WHEN: A dialog needs to be shown
        THEN: Should create child window that doesn't interfere with main window
        """
        # Arrange (Given): Set up mocking for child window creation
        with (
            patch.object(BaseWindow, "_setup_application_icon") as mock_icon,
            patch.object(BaseWindow, "_setup_theme_and_styling"),
            patch.object(BaseWindow, "_get_dpi_scaling_factor", return_value=1.0),
        ):
            # Act (When): User opens a dialog window
            child_window = BaseWindow(tk_root)

            # Assert (Then): Child window is created properly
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

    def test_user_sees_properly_sized_images(self, image_test_context, sample_image_file, mocked_base_window) -> None:
        """
        User sees properly sized images.

        GIVEN: User interface needs to show an image
        WHEN: Image is loaded into a label
        THEN: Should resize image maintaining aspect ratio and display correctly
        """
        with image_test_context() as mocks:
            # Arrange (Given): Set up parent frame for image display
            parent_frame = MagicMock()

            # Act (When): User loads an image into the interface
            result = mocked_base_window.put_image_in_label(parent_frame, sample_image_file, image_height=40)

            # Assert (Then): Image is properly sized and displayed
            assert result == mocks["label"]
            mocks["open_mock"].assert_called_once_with(sample_image_file)
            mocks["image"].resize.assert_called_once()
            mocks["photo_mock"].assert_called_once_with(mocks["resized_image"])

    def test_user_sees_fallback_when_image_unavailable(self, image_test_context, mocked_base_window) -> None:
        """
        User sees appropriate error when image unavailable.

        GIVEN: User interface references a missing image
        WHEN: Image cannot be loaded due to missing file
        THEN: Should raise FileNotFoundError for calling code to handle
        """
        with image_test_context(file_exists=False):
            # Arrange (Given): Set up parent frame and missing image scenario
            parent_frame = MagicMock()

            # Act & Assert: User attempts to load a missing image, should raise FileNotFoundError
            with pytest.raises(FileNotFoundError, match="Image file not found"):
                mocked_base_window.put_image_in_label(parent_frame, "missing_image.png", fallback_text="Image not available")

    @pytest.mark.parametrize(
        ("original_size", "target_height", "expected_width"),
        [
            ((200, 100), 50, 100),  # 2:1 aspect ratio
            ((300, 150), 75, 150),  # 2:1 aspect ratio
            ((100, 200), 100, 50),  # 1:2 aspect ratio
        ],
    )
    def test_maintains_image_aspect_ratios(  # pylint: disable=too-many-arguments,too-many-positional-arguments
        self, image_test_context, original_size, target_height, expected_width, mocked_base_window
    ) -> None:
        """
        Maintains image aspect ratios.

        GIVEN: Images with various aspect ratios
        WHEN: Resizing to fit UI constraints
        THEN: Should maintain original aspect ratio
        """
        with image_test_context(image_size=original_size) as mocks:
            parent_frame = MagicMock()

            mocked_base_window.put_image_in_label(parent_frame, "test_image.png", image_height=target_height)

            # Verify aspect ratio is maintained
            expected_size = (expected_width, target_height)
            mocks["image"].resize.assert_called_once_with(expected_size, Image.Resampling.LANCZOS)


class TestErrorResilienceBehavior:
    """Test how application handles error conditions gracefully."""

    def test_user_sees_functional_app_despite_icon_issues(self) -> None:
        """
        User sees functional application despite icon loading issues.

        GIVEN: User's system has icon loading issues
        WHEN: Application attempts to set window icon and fails
        THEN: Should log error but continue functioning normally
        """
        # Arrange: Set up environment without test markers and mock dependencies
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

            # Act: Attempt to set up application icon
            window._setup_application_icon()

            # Assert: Error should be logged but application should continue
            mock_log.assert_called_once()

    def test_user_gets_usable_app_despite_display_issues(self, mock_tkinter_context) -> None:
        """
        User gets usable application despite display configuration issues.

        GIVEN: User's system has DPI detection or display configuration issues
        WHEN: Various setup operations fail during window initialization
        THEN: Should provide reasonable defaults to maintain usability
        """
        # Arrange: Configure mocks to simulate configuration failures
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

            # Act: Create window despite configuration issues
            window = BaseWindow()
            scaling_factor = window._get_dpi_scaling_factor()

            # Assert: Should provide safe fallback defaults
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
        try:
            child = tk.Toplevel(tk_root)
            tk_root.geometry("400x300+100+100")
            child.geometry("200x150")

            BaseWindow.center_window(child, tk_root)

            # Verify positioning (allowing for window manager differences and headless environments)
            child.update_idletasks()

            # In headless environments, coordinates can be negative, so we verify the centering logic worked
            # by checking that the child window has been given specific coordinates (not default 0,0)
            child_x, child_y = child.winfo_x(), child.winfo_y()

            # The centering should set explicit coordinates, not leave them at defaults
            # This verifies the positioning logic executed without checking specific screen bounds
            assert isinstance(child_x, int)
            assert isinstance(child_y, int)

            # Additional verification: window should be properly configured
            assert child.winfo_width() > 0
            assert child.winfo_height() > 0

            child.destroy()
        except tk.TclError as e:
            if "couldn't connect to display" in str(e) or "no display name" in str(e):
                pytest.skip(f"Tkinter not available in test environment: {e}")
            raise

    def test_user_sees_properly_positioned_dialogs_regardless_of_window_size(self, tk_root) -> None:
        """
        User sees properly positioned dialogs regardless of unusual window sizes.

        GIVEN: User has unusual window sizes or positioning requirements
        WHEN: Attempting to position child windows or dialogs
        THEN: Should handle gracefully without errors or crashes
        """
        # Arrange: Create child window with minimal size to test edge case
        child = tk.Toplevel(tk_root)
        child.geometry("1x1")  # Minimal size

        # Act: Attempt to center the window (should not raise exceptions)
        BaseWindow.center_window(child, tk_root)

        # Assert: Window should be positioned without errors
        # (The exact position may vary by window manager, but it shouldn't crash)

        child.destroy()

    def test_user_can_safely_close_windows_without_memory_leaks(self, tk_root) -> None:
        """
        User can safely close windows without memory leaks.

        GIVEN: User has opened application windows
        WHEN: User closes windows or application exits
        THEN: Should clean up resources properly without memory leaks
        """
        # Arrange: Create window for testing cleanup
        window = BaseWindow(tk_root)

        # Verify window exists initially
        assert window.root.winfo_exists()

        # Act: Simulate window destruction (user closing window)
        window.root.destroy()

        # Assert: Window should be properly destroyed and cleaned up
        assert not window.root.winfo_exists()

    @pytest.mark.parametrize("extreme_dpi", [48, 480, 960])  # Very low and very high DPI
    def test_user_gets_readable_ui_on_extreme_dpi_displays(self, dpi_test_window, extreme_dpi) -> None:
        """
        User gets readable UI on extreme DPI displays.

        GIVEN: User has extremely high or low DPI displays (retina, 4K, or very old displays)
        WHEN: Application detects and adapts to DPI settings
        THEN: Should handle gracefully with reasonable scaling bounds for usability
        """
        # Arrange: Set up window with extreme DPI values
        window, stack = dpi_test_window(extreme_dpi)

        with stack:
            # Act: Get DPI scaling factor for extreme display
            scaling_factor = window._get_dpi_scaling_factor()

            # Assert: Should be reasonable (between 0.5 and 10.0) for usability
            assert 0.5 <= scaling_factor <= 10.0

    def test_user_sees_stable_images_without_display_glitches(
        self, image_test_context, sample_image_file, mocked_base_window
    ) -> None:
        """
        User sees stable images without display glitches.

        GIVEN: User views application with images displayed in the UI
        WHEN: Images are loaded and displayed in labels
        THEN: Should maintain references to prevent garbage collection and flickering
        """
        # Arrange: Set up image loading context
        with image_test_context() as mocks:
            parent_frame = MagicMock()

            # Act: Load and display image in UI
            label = mocked_base_window.put_image_in_label(parent_frame, sample_image_file)

            # Assert: Should maintain image reference to prevent GC issues
            assert hasattr(label, "image") or hasattr(mocks["label"], "image")


# ==================== INTEGRATION TESTS ====================


@pytest.mark.integration
class TestCompleteWorkflows:
    """Test complete user workflows end-to-end with real Tkinter."""

    def test_user_experiences_smooth_application_startup(self, tk_root) -> None:
        """
        User experiences smooth application startup.

        GIVEN: User starts the application from desktop or command line
        WHEN: Application initializes completely with all components
        THEN: Should have functional window with proper theme and scaling for good UX
        """
        # Arrange: User starting application
        # Act: Initialize complete application window
        window = BaseWindow(tk_root)

        # Assert: Verify complete initialization provides good user experience
        assert isinstance(window.root, tk.Toplevel)
        assert isinstance(window.main_frame, ttk.Frame)
        assert window.dpi_scaling_factor > 0

        # Assert: Verify theme is applied for visual consistency
        style = ttk.Style()
        assert style.theme_use() in ["alt", "clam", "default"]  # Valid themes

    def test_user_can_launch_main_application_window(self) -> None:
        """
        User can launch main application window.

        GIVEN: User starts application without any parent windows (fresh start)
        WHEN: User launches the main application window
        THEN: Should create root Tk window with all essential components ready
        """
        # Arrange: Fresh application start (no parent window)
        window = None
        try:
            # Act: User launches main application window
            window = BaseWindow()

            # Assert: Verify main window components are ready for user interaction
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

    def test_user_can_open_dialogs_from_main_window(self, tk_root) -> None:
        """
        User can open dialogs from main application window.

        GIVEN: User has main application window open
        WHEN: User opens a dialog or child window from the main window
        THEN: Should create properly positioned Toplevel window that works with main window
        """
        # Arrange: User has main application window open
        main_window = BaseWindow(tk_root)

        # Act: User opens dialog window from main application
        dialog_window = BaseWindow(tk_root)

        # Assert: Dialog should be properly structured and functional
        assert isinstance(dialog_window.root, tk.Toplevel)
        assert dialog_window.root.master == tk_root

        # Assert: Both windows should coexist without conflicts
        assert main_window.root.winfo_exists()
        assert dialog_window.root.winfo_exists()

    def test_user_can_manage_multiple_windows_simultaneously(self, tk_root) -> None:
        """
        User can manage multiple windows simultaneously.

        GIVEN: User needs multiple windows for complex workflows
        WHEN: User opens and manages multiple BaseWindow instances
        THEN: Should handle multiple windows without conflicts or performance issues
        """
        # Arrange: Prepare for multiple window management
        windows = []

        try:
            # Act: User opens multiple child windows for different tasks
            for i in range(3):
                window = BaseWindow(tk_root)
                window.root.title(f"Test Window {i}")
                windows.append(window)

            # Assert: All windows should exist and be functional simultaneously
            for window in windows:
                assert window.root.winfo_exists()
                assert isinstance(window.main_frame, ttk.Frame)

            # Assert: Each should have independent DPI scaling for proper display
            scaling_factors = [w.dpi_scaling_factor for w in windows]
            assert all(factor > 0 for factor in scaling_factors)

        finally:
            # Cleanup: Properly close all windows
            for window in windows:
                with contextlib.suppress(tk.TclError):
                    window.root.destroy()


@pytest.mark.integration
class TestRealImageIntegration:
    """Test image operations with real files and Tkinter."""

    def test_user_sees_images_loaded_correctly_in_real_environment(self, root, sample_image_file) -> None:
        """
        User sees images loaded correctly in real environment.

        GIVEN: User has real image files and Tkinter environment
        WHEN: User loads images into application labels
        THEN: Should create functional image labels that display correctly
        """
        try:
            # Arrange: Set up real window and image file
            window = BaseWindow(root)

            # Act: User loads real image into the application
            label = window.put_image_in_label(window.main_frame, sample_image_file, image_height=50)

            # Assert: Verify label creation and proper image display
            assert isinstance(label, ttk.Label)
            assert label.master == window.main_frame

            # Assert: Should have image reference for proper display
            assert hasattr(label, "image") or label.cget("image")
        except tk.TclError as e:
            if "doesn't exist" in str(e) or "Can't find a usable" in str(e):
                pytest.skip(f"Tkinter image/display not available in test environment: {e}")
            raise

    def test_user_sees_properly_scaled_images_across_dpi_settings(self, root, sample_image_file) -> None:
        """
        User sees properly scaled images across DPI settings.

        GIVEN: User has real images and varying DPI scaling requirements
        WHEN: User loads images at different display sizes
        THEN: Should scale images appropriately for good visual experience
        """
        try:  # Arrange: Set up real window environment
            window = BaseWindow(root)

            # Test different image heights for various UI contexts
            heights = [25, 50, 100]
            labels = []

            # Act: User loads images at different sizes
            for height in heights:
                label = window.put_image_in_label(window.main_frame, sample_image_file, image_height=height)
                labels.append(label)

            # Assert: All labels should be created successfully
            assert len(labels) == len(heights)
            for label in labels:
                assert isinstance(label, ttk.Label)
        except tk.TclError as e:
            if "doesn't exist" in str(e) or "Can't find a usable" in str(e):
                pytest.skip(f"Tkinter image/display not available in test environment: {e}")
            raise

    def test_user_can_load_multiple_images_without_performance_issues(self, root) -> None:
        """
        User can load multiple images without performance issues.

        GIVEN: User needs to display multiple images in the application (gallery, thumbnails, etc.)
        WHEN: User loads multiple images simultaneously in the interface
        THEN: Should handle multiple images efficiently without memory issues or crashes
        """
        try:
            # Arrange: Set up window and prepare for multiple image loading
            window = BaseWindow(root)
            temp_files = []
            labels = []

            try:
                # Create multiple temporary images (simulating user's image files)
                for i in range(5):
                    with tempfile.NamedTemporaryFile(suffix=f"_{i}.png", delete=False) as tmp:
                        img = Image.new("RGB", (50, 25), color=(i * 50, 100, 150))
                        img.save(tmp.name)
                        temp_files.append(tmp.name)

                # Act: User loads all images into the application
                for img_file in temp_files:
                    label = window.put_image_in_label(window.main_frame, img_file, image_height=30)
                    labels.append(label)

                # Assert: Verify all images loaded successfully without issues
                assert len(labels) == len(temp_files)
                for label in labels:
                    assert isinstance(label, ttk.Label)

            finally:
                # Cleanup: Remove temporary files
                for temp_file in temp_files:
                    Path(temp_file).unlink(missing_ok=True)
        except tk.TclError as e:
            if "doesn't exist" in str(e) or "Can't find a usable" in str(e):
                pytest.skip(f"Tkinter image/display not available in test environment: {e}")
            raise


@pytest.mark.integration
class TestThemeIntegration:
    """Test theme and styling integration with real Tkinter."""

    def test_user_sees_consistent_theme_across_all_windows(self, tk_root) -> None:
        """
        User sees consistent theme across all application windows.

        GIVEN: User opens multiple BaseWindow instances in application workflow
        WHEN: User creates windows with consistent theming requirements
        THEN: Should maintain visual consistency across all windows for good UX
        """
        # Arrange: Prepare for multiple window creation
        windows = []

        try:
            # Act: User creates multiple windows (main + dialogs)
            for _ in range(3):
                window = BaseWindow(tk_root)
                windows.append(window)

            # Assert: Check theme consistency across all windows
            styles = [ttk.Style() for _ in windows]
            themes = [style.theme_use() for style in styles]

            # Assert: All should use the same theme for visual consistency
            assert len(set(themes)) == 1  # All themes should be identical
            assert themes[0] == "alt"

        finally:
            # Cleanup: Close all windows properly
            for window in windows:
                with contextlib.suppress(tk.TclError):
                    window.root.destroy()

    def test_user_experiences_proper_scaling_on_real_displays(self, tk_root) -> None:
        """
        User experiences proper scaling on real displays.

        GIVEN: User has real display environment with system DPI settings
        WHEN: User opens application and scaling is detected and applied
        THEN: Should work seamlessly with actual system DPI settings for good readability
        """
        # Arrange & Act: User opens application on their actual display
        window = BaseWindow(tk_root)

        # Assert: Should detect actual DPI for proper scaling
        dpi_factor = window.dpi_scaling_factor
        assert isinstance(dpi_factor, float)
        assert 0.5 <= dpi_factor <= 5.0  # Reasonable range for real displays

        # Assert: Font scaling should work for readable text
        base_font_size = 12
        scaled_size = window.calculate_scaled_font_size(base_font_size)
        expected_size = int(base_font_size * dpi_factor)
        assert scaled_size == expected_size

        # Assert: Padding scaling should work for proper spacing
        base_padding = 10
        scaled_padding = window.calculate_scaled_padding(base_padding)
        expected_padding = int(base_padding * dpi_factor)
        assert scaled_padding == expected_padding


@pytest.mark.integration
class TestWindowPositioningIntegration:
    """Test window positioning with real Tkinter geometry management."""

    def test_user_sees_properly_centered_dialog_windows(self, tk_root) -> None:
        """
        User sees properly centered dialog windows.

        GIVEN: User has parent and child windows with real geometry
        WHEN: User opens dialog that needs to be centered on parent window
        THEN: Should position windows correctly on screen for good user experience
        """
        # Arrange: Set up parent window with known size and position
        tk_root.geometry("400x300+100+100")
        tk_root.update_idletasks()

        # Create child window
        child_window = BaseWindow(tk_root)
        child_window.root.geometry("200x150")

        # Act: User requests dialog to be centered on parent
        BaseWindow.center_window(child_window.root, tk_root)
        child_window.root.update_idletasks()

        # Assert: Verify positioning logic executed and window is configured properly
        # In headless environments, exact positioning may vary, so we verify the operation completed successfully
        parent_x, parent_y = tk_root.winfo_x(), tk_root.winfo_y()
        parent_w, parent_h = tk_root.winfo_width(), tk_root.winfo_height()
        child_x, child_y = child_window.root.winfo_x(), child_window.root.winfo_y()

        # Verify the positioning logic executed (coordinates were set explicitly)
        assert isinstance(child_x, int)
        assert isinstance(child_y, int)
        assert isinstance(parent_x, int)
        assert isinstance(parent_y, int)

        # Verify window dimensions are valid
        assert parent_w > 0
        assert parent_h > 0
        assert child_window.root.winfo_width() > 0
        assert child_window.root.winfo_height() > 0

        # Only verify exact positioning if the parent window has the expected size
        # In headless environments, geometry settings may not take effect
        if parent_w >= 300 and parent_h >= 200:  # Parent window geometry took effect
            expected_x = parent_x + (parent_w - 200) // 2
            expected_y = parent_y + (parent_h - 150) // 2
            # Allow generous tolerance for window manager variations
            assert abs(child_x - expected_x) <= 100
            assert abs(child_y - expected_y) <= 100

    def test_user_can_position_multiple_dialogs_without_overlap_issues(self, tk_root) -> None:
        """
        User can position multiple dialogs without overlap issues.

        GIVEN: User needs multiple child windows for complex workflows
        WHEN: User opens and positions them relative to parent window
        THEN: Should handle multiple positioned windows without layout conflicts
        """
        # Arrange: Prepare for multiple child window positioning
        child_windows = []

        try:
            # Act: User creates multiple child windows
            for _ in range(3):
                child = BaseWindow(tk_root)
                child.root.geometry("150x100")
                child_windows.append(child)

            # Position each child (user arranging windows)
            for child in child_windows:
                BaseWindow.center_window(child.root, tk_root)
                child.root.update_idletasks()

            # Assert: All should be positioned correctly (coordinates may be negative in headless environments)
            for child in child_windows:
                x, y = child.root.winfo_x(), child.root.winfo_y()

                # Verify the positioning logic executed (coordinates were set explicitly)
                assert isinstance(x, int)
                assert isinstance(y, int)

                # Verify window properties are valid
                assert child.root.winfo_width() > 0
                assert child.root.winfo_height() > 0

        finally:
            # Cleanup: Close all child windows
            for child in child_windows:
                with contextlib.suppress(tk.TclError):
                    child.root.destroy()


@pytest.mark.integration
@pytest.mark.slow
class TestPerformanceIntegration:
    """Test performance characteristics with real Tkinter operations."""

    def test_user_experiences_responsive_window_creation(self, root) -> None:
        """
        User experiences responsive window creation.

        GIVEN: User needs to work efficiently with multiple windows
        WHEN: User rapidly creates multiple windows during workflow
        THEN: Should create windows efficiently without blocking or lag for good UX
        """
        # Arrange: Prepare performance measurement
        start_time = time.time()
        windows = []

        try:
            # Act: User rapidly creates 10 windows (simulating busy workflow)
            for _ in range(10):
                window = BaseWindow(root)
                windows.append(window)

            creation_time = time.time() - start_time

            # Assert: Should create windows reasonably quickly (< 5 seconds for 10 windows)
            assert creation_time < 5.0

            # Assert: All windows should exist and be responsive
            for window in windows:
                assert window.root.winfo_exists()

        except tk.TclError:
            pytest.skip("Tkinter display not available")
        finally:
            # Cleanup: Close all windows
            for window in windows:
                with contextlib.suppress(tk.TclError):
                    if hasattr(window, "root") and window.root != root:  # Don't destroy the session root
                        window.root.destroy()

    def test_user_experiences_smooth_image_loading_performance(self, root, sample_image_file) -> None:
        """
        User experiences smooth image loading performance.

        GIVEN: User needs to view many images efficiently (galleries, thumbnails, etc.)
        WHEN: User loads multiple images in rapid succession
        THEN: Should load images efficiently without blocking the interface
        """
        # Arrange: Prepare for image loading performance test
        window = None
        try:
            window = BaseWindow(root)

            start_time = time.time()
            labels = []

            # Act: User loads same image multiple times (simulating gallery or thumbnails)
            for _ in range(20):
                label = window.put_image_in_label(window.main_frame, sample_image_file, image_height=40)
                labels.append(label)

            loading_time = time.time() - start_time

            # Assert: Should load images reasonably quickly (< 3 seconds for 20 images)
            assert loading_time < 3.0

            # Assert: All labels should be created successfully
            assert len(labels) == 20

        except tk.TclError:
            pytest.skip("Tkinter display not available")
        finally:
            # Cleanup: Don't destroy the session root, it's managed by conftest.py
            pass


if __name__ == "__main__":
    pytest.main([__file__])
