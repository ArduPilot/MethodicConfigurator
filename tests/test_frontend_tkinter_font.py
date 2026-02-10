#!/usr/bin/env python3

"""
Test suite for frontend_tkinter_font module.

This module tests the font utility functions that provide safe access to TKinter
font information with platform-specific fallbacks.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import tkinter as tk
import tkinter.font as tkfont
from collections.abc import Generator
from typing import Union
from unittest.mock import MagicMock, patch

import pytest

from ardupilot_methodic_configurator.frontend_tkinter_font import (
    create_scaled_font,
    get_safe_font_config,
    get_safe_font_family,
    get_safe_font_size,
    safe_font_nametofont,
)

# pylint: disable=unused-argument, redefined-outer-name


@pytest.fixture
def tk_root() -> Generator[tk.Tk, None, None]:
    """Create and manage a Tkinter root window for tests."""
    root = tk.Tk()
    yield root
    root.destroy()


class TestSafeFontNameToFont:
    """Test safe_font_nametofont function for robust font access."""

    def test_user_can_access_default_system_font_successfully(self) -> None:
        """
        User can access default system font when TKinter is properly initialized.

        GIVEN: A properly initialized TKinter environment
        WHEN: User requests the default font
        THEN: Should return a valid Font object
        """
        # Arrange: Mock a successful tkfont.nametofont call
        mock_font = MagicMock(spec=tkfont.Font)
        font_patch = "ardupilot_methodic_configurator.frontend_tkinter_font.tkfont.nametofont"

        with patch(font_patch, return_value=mock_font):
            # Act: Get default font
            result = safe_font_nametofont()

            # Assert: Should return the font object
            assert result is mock_font

    def test_user_gets_none_when_system_font_unavailable(self) -> None:
        """
        User gets None when system font is unavailable during startup.

        GIVEN: TKinter environment where named fonts are not yet available
        WHEN: User requests a system font
        THEN: Should return None gracefully instead of crashing
        """
        # Arrange: Mock tkfont.nametofont to raise TclError (common on macOS startup)
        font_patch = "ardupilot_methodic_configurator.frontend_tkinter_font.tkfont.nametofont"

        with patch(font_patch, side_effect=tk.TclError("Font not found")):
            # Act: Attempt to get font
            result = safe_font_nametofont()

            # Assert: Should return None gracefully
            assert result is None

    def test_user_can_request_specific_named_fonts(self) -> None:
        """
        User can request specific named fonts by providing font name.

        GIVEN: A TKinter environment with available named fonts
        WHEN: User requests a specific font like 'TkTextFont'
        THEN: Should attempt to retrieve that specific font
        """
        # Arrange: Mock font retrieval
        mock_font = MagicMock(spec=tkfont.Font)
        font_patch = "ardupilot_methodic_configurator.frontend_tkinter_font.tkfont.nametofont"

        with patch(font_patch, return_value=mock_font) as mock_nametofont:
            # Act: Request specific font
            result = safe_font_nametofont("TkTextFont")

            # Assert: Should call nametofont with correct argument
            mock_nametofont.assert_called_once_with("TkTextFont")
            assert result is mock_font

    def test_user_gets_consistent_behavior_across_font_errors(self) -> None:
        """
        User gets consistent None return for various font access errors.

        GIVEN: Various TKinter font access error scenarios
        WHEN: User attempts to access fonts that cause different errors
        THEN: Should consistently return None for all TclError types
        """
        # Test various TclError scenarios
        error_messages = ["Font not found", "invalid font name", "font system not initialized", ""]
        font_patch = "ardupilot_methodic_configurator.frontend_tkinter_font.tkfont.nametofont"

        for error_msg in error_messages:
            with patch(font_patch, side_effect=tk.TclError(error_msg)):
                result = safe_font_nametofont("TkDefaultFont")
                assert result is None, f"Should return None for TclError: '{error_msg}'"


class TestGetSafeFontConfig:
    """Test get_safe_font_config function for complete font configuration retrieval."""

    def test_user_gets_complete_font_config_from_system_font(self) -> None:
        """
        User gets complete font configuration when system font is available.

        GIVEN: A system with accessible named fonts
        WHEN: User requests font configuration
        THEN: Should return dictionary with family and size from system font
        """
        # Arrange: Mock successful font access
        mock_font = MagicMock(spec=tkfont.Font)
        mock_font.configure.return_value = {"family": "Helvetica", "size": 12, "weight": "normal"}
        safe_font_patch = "ardupilot_methodic_configurator.frontend_tkinter_font.safe_font_nametofont"

        with patch(safe_font_patch, return_value=mock_font):
            # Act: Get font config
            result = get_safe_font_config()

            # Assert: Should return extracted family and size
            assert isinstance(result, dict)
            assert result["family"] == "Helvetica"
            assert result["size"] == 12

    @pytest.mark.parametrize(
        ("platform", "expected_family", "expected_size"),
        [
            ("Windows", "Segoe UI", 9),
            ("Darwin", "Helvetica", 13),
            ("Linux", "Helvetica", -12),
        ],
    )
    def test_user_gets_platform_fallback_when_font_unavailable(
        self, platform: str, expected_family: str, expected_size: int
    ) -> None:
        """
        User gets platform-specific fallback when system font is unavailable.

        GIVEN: A system where named fonts are not accessible
        WHEN: User requests font configuration
        THEN: Should return platform default font configuration
        """
        # Arrange: Mock platform and unavailable font
        safe_font_patch = "ardupilot_methodic_configurator.frontend_tkinter_font.safe_font_nametofont"
        platform_patch = "ardupilot_methodic_configurator.frontend_tkinter_font.platform_system"

        with patch(safe_font_patch, return_value=None), patch(platform_patch, return_value=platform):
            # Act: Get font config
            result = get_safe_font_config()

            # Assert: Should return platform defaults
            assert result["family"] == expected_family
            assert result["size"] == expected_size

    def test_user_gets_robust_handling_of_malformed_font_data(self) -> None:
        """
        User gets robust handling when system returns malformed font data.

        GIVEN: System font that returns invalid or incomplete configuration
        WHEN: User requests font configuration
        THEN: Should fall back to platform defaults gracefully
        """
        # Test cases for various malformed font data
        malformed_configs = [
            None,  # Font configure returns None
            {},  # Empty configuration
            {"family": None, "size": None},  # None values
            {"family": "", "size": "invalid"},  # Invalid size
            {"family": 123, "size": "12.5"},  # Wrong types
            {"other": "data"},  # Missing required keys
        ]

        safe_font_patch = "ardupilot_methodic_configurator.frontend_tkinter_font.safe_font_nametofont"
        platform_patch = "ardupilot_methodic_configurator.frontend_tkinter_font.platform_system"

        for config in malformed_configs:
            mock_font = MagicMock(spec=tkfont.Font)
            mock_font.configure.return_value = config

            with patch(safe_font_patch, return_value=mock_font), patch(platform_patch, return_value="Linux"):
                result = get_safe_font_config()

                # Should fall back to platform defaults
                assert result["family"] == "Helvetica"
                assert result["size"] == -12


class TestGetSafeFontFamily:
    """Test get_safe_font_family function for font family retrieval."""

    def test_user_gets_font_family_from_system_font(self) -> None:
        """
        User gets font family name when system font is available.

        GIVEN: System with accessible font configuration
        WHEN: User requests font family
        THEN: Should return the system font family name
        """
        # Arrange: Mock font config with family
        config_patch = "ardupilot_methodic_configurator.frontend_tkinter_font.get_safe_font_config"

        with patch(config_patch, return_value={"family": "Arial", "size": 12}):
            # Act: Get font family
            result = get_safe_font_family()

            # Assert: Should return family name
            assert result == "Arial"

    def test_user_gets_empty_string_when_family_unavailable(self) -> None:
        """
        User gets empty string when font family cannot be determined.

        GIVEN: Font configuration without family information
        WHEN: User requests font family
        THEN: Should return empty string instead of None
        """
        # Arrange: Mock config without family
        config_patch = "ardupilot_methodic_configurator.frontend_tkinter_font.get_safe_font_config"

        with patch(config_patch, return_value={"size": 12}):
            # Act: Get font family
            result = get_safe_font_family()

            # Assert: Should return empty string
            assert result == ""
            assert isinstance(result, str)

    def test_user_can_request_family_from_specific_font(self) -> None:
        """
        User can request font family from specific named font.

        GIVEN: Multiple named fonts with different families
        WHEN: User requests family from specific font
        THEN: Should return family for that specific font
        """
        # Arrange: Mock specific font config call
        config_patch = "ardupilot_methodic_configurator.frontend_tkinter_font.get_safe_font_config"

        with patch(config_patch, return_value={"family": "Monaco", "size": 11}) as mock_config:
            # Act: Request family from specific font
            result = get_safe_font_family("TkFixedFont")

            # Assert: Should call config with correct font name
            mock_config.assert_called_once_with("TkFixedFont")
            assert result == "Monaco"


class TestGetSafeFontSize:
    """Test get_safe_font_size function for font size retrieval."""

    def test_user_gets_font_size_from_system_font(self) -> None:
        """
        User gets font size when system font is available.

        GIVEN: System with accessible font configuration
        WHEN: User requests font size
        THEN: Should return the system font size
        """
        # Arrange: Mock font config with size
        config_patch = "ardupilot_methodic_configurator.frontend_tkinter_font.get_safe_font_config"

        with patch(config_patch, return_value={"family": "Arial", "size": 14}):
            # Act: Get font size
            result = get_safe_font_size()

            # Assert: Should return size value
            assert result == 14

    def test_user_gets_zero_when_size_unavailable(self) -> None:
        """
        User gets zero when font size cannot be determined.

        GIVEN: Font configuration without size information
        WHEN: User requests font size
        THEN: Should return 0 instead of None
        """
        # Arrange: Mock config without size
        config_patch = "ardupilot_methodic_configurator.frontend_tkinter_font.get_safe_font_config"

        with patch(config_patch, return_value={"family": "Arial"}):
            # Act: Get font size
            result = get_safe_font_size()

            # Assert: Should return 0
            assert result == 0
            assert isinstance(result, int)

    def test_user_gets_integer_type_regardless_of_config_type(self) -> None:
        """
        User always gets integer type even if config returns other types.

        GIVEN: Font configuration that might return non-integer size
        WHEN: User requests font size
        THEN: Should convert to integer type
        """
        # Test various size value types
        test_cases = [
            (None, 0),  # None should become 0
            ("12", 12),  # String numbers should convert to int
            ("invalid", 0),  # Invalid strings should become 0
            (12.7, 12),  # Float should truncate to int
            (-10, -10),  # Negative sizes are valid
            (0, 0),  # Zero size
        ]
        config_patch = "ardupilot_methodic_configurator.frontend_tkinter_font.get_safe_font_config"

        for input_size, expected_output in test_cases:
            config = {"family": "Arial", "size": input_size}
            with patch(config_patch, return_value=config):
                result = get_safe_font_size()
                assert result == expected_output
                assert isinstance(result, int)


class TestFontUtilitiesIntegration:
    """Test integration scenarios and cross-platform behavior."""

    def test_user_experiences_consistent_behavior_across_all_font_functions(self) -> None:
        """
        User experiences consistent behavior across all font utility functions.

        GIVEN: System with working font access
        WHEN: User calls different font utility functions
        THEN: Should get consistent information from all functions
        """
        # Arrange: Mock successful font access
        mock_font = MagicMock(spec=tkfont.Font)
        mock_font.configure.return_value = {"family": "Liberation Sans", "size": 11}
        safe_font_patch = "ardupilot_methodic_configurator.frontend_tkinter_font.safe_font_nametofont"

        with patch(safe_font_patch, return_value=mock_font):
            # Act: Call all font functions
            config = get_safe_font_config("TkDefaultFont")
            family = get_safe_font_family("TkDefaultFont")
            size = get_safe_font_size("TkDefaultFont")

            # Assert: All should return consistent information
            assert config["family"] == family == "Liberation Sans"
            assert config["size"] == size == 11

    def test_user_gets_graceful_degradation_with_partial_font_failures(self) -> None:
        """
        User gets graceful degradation when font access partially fails.

        GIVEN: System where font access works but returns incomplete data
        WHEN: User requests font information
        THEN: Should provide reasonable defaults for missing information
        """
        # Test scenario where font exists but configure() raises TclError
        mock_font = MagicMock(spec=tkfont.Font)
        mock_font.configure.side_effect = tk.TclError("Cannot configure font")
        safe_font_patch = "ardupilot_methodic_configurator.frontend_tkinter_font.safe_font_nametofont"
        platform_patch = "ardupilot_methodic_configurator.frontend_tkinter_font.platform_system"

        with patch(safe_font_patch, return_value=mock_font), patch(platform_patch, return_value="Linux"):
            # Act: Attempt to get font configuration
            config = get_safe_font_config()
            family = get_safe_font_family()
            size = get_safe_font_size()

            # Assert: Should fall back to platform defaults
            assert config["family"] == "Helvetica"
            assert config["size"] == -12
            assert family == "Helvetica"
            assert size == -12

    def test_application_startup_resilience_simulation(self) -> None:
        """
        Application demonstrates resilience during startup when fonts may be unavailable.

        GIVEN: Application startup scenario where TKinter fonts are not yet initialized
        WHEN: Application attempts to access font information during initialization
        THEN: Should handle gracefully without crashes and provide usable defaults
        """
        # Simulate various startup conditions
        startup_scenarios = [
            (tk.TclError("Font system not ready"), "Font system not ready"),
            (tk.TclError(""), "Empty error during startup"),
            (None, "Font returns None"),
        ]

        font_patch = "ardupilot_methodic_configurator.frontend_tkinter_font.tkfont.nametofont"
        platform_patch = "ardupilot_methodic_configurator.frontend_tkinter_font.platform_system"

        for error_condition, description in startup_scenarios:
            mock_side_effect = error_condition if isinstance(error_condition, Exception) else None

            with patch(font_patch, side_effect=mock_side_effect), patch(platform_patch, return_value="Linux"):
                # These should never raise exceptions
                try:
                    config = get_safe_font_config()
                    family = get_safe_font_family()
                    size = get_safe_font_size()

                    # Basic validation that we got usable values
                    assert isinstance(config, dict)
                    assert "family" in config
                    assert "size" in config
                    assert isinstance(family, str)
                    assert isinstance(size, int)

                except Exception as e:  # pylint: disable=broad-exception-caught
                    pytest.fail(
                        f"Font utilities should not raise exceptions during startup. Scenario: {description}, Error: {e}"
                    )


class TestCreateScaledFont:
    """Test create_scaled_font function for creating scaled Font objects."""

    def test_user_can_create_larger_font_for_better_readability(self, tk_root: tk.Tk) -> None:
        """
        User can create a larger font by applying a scale factor greater than 1.0.

        GIVEN: A font configuration with a specific size
        WHEN: User applies a scale factor of 1.2 (20% larger)
        THEN: Should create a Font object with size increased by 20%
        """
        # Arrange: Create a font configuration
        font_config: dict[str, Union[str, int]] = {"family": "Arial", "size": 10}

        # Act: Create scaled font with 1.2x multiplier
        result_font = create_scaled_font(font_config, 1.2)

        # Assert: Should return a Font object with scaled size
        assert isinstance(result_font, tkfont.Font)
        # Font config should be modified in place
        assert font_config["size"] == 12  # 10 * 1.2 = 12
        assert result_font.cget("family") == "Arial"
        assert result_font.cget("size") == 12

    def test_user_can_create_smaller_font_for_compact_display(self, tk_root: tk.Tk) -> None:
        """
        User can create a smaller font by applying a scale factor less than 1.0.

        GIVEN: A font configuration with a specific size
        WHEN: User applies a scale factor of 0.8 (20% smaller)
        THEN: Should create a Font object with size decreased by 20%
        """
        # Arrange: Create a font configuration
        font_config: dict[str, Union[str, int]] = {"family": "Helvetica", "size": 20}

        # Act: Create scaled font with 0.8x multiplier
        result_font = create_scaled_font(font_config, 0.8)

        # Assert: Should return a Font object with scaled size
        assert isinstance(result_font, tkfont.Font)
        assert font_config["size"] == 16  # 20 * 0.8 = 16
        assert result_font.cget("family") == "Helvetica"
        assert result_font.cget("size") == 16

    def test_user_can_create_unscaled_font_with_default_factor(self, tk_root: tk.Tk) -> None:
        """
        User can create an unscaled font using default scale factor.

        GIVEN: A font configuration
        WHEN: User creates font without specifying scale factor (defaults to 1.0)
        THEN: Should create a Font object with original size unchanged
        """
        # Arrange: Create a font configuration
        font_config: dict[str, Union[str, int]] = {"family": "Courier", "size": 12}

        # Act: Create font with default scale factor
        result_font = create_scaled_font(font_config)

        # Assert: Should return a Font object with original size
        assert isinstance(result_font, tkfont.Font)
        assert font_config["size"] == 12  # 12 * 1.0 = 12
        assert result_font.cget("family") == "Courier"
        assert result_font.cget("size") == 12

    def test_user_can_scale_fonts_from_safe_config_function(self, tk_root: tk.Tk) -> None:
        """
        User can combine get_safe_font_config with create_scaled_font for robust scaling.

        GIVEN: A system with available fonts
        WHEN: User gets safe font config and scales it
        THEN: Should create a properly scaled Font object with system defaults
        """
        # Arrange: Get a safe font configuration
        font_config = get_safe_font_config()
        original_size = font_config["size"]

        # Act: Create a 1.5x scaled font
        result_font = create_scaled_font(font_config.copy(), 1.5)

        # Assert: Should create properly scaled font
        assert isinstance(result_font, tkfont.Font)
        expected_size = int(original_size * 1.5) if isinstance(original_size, int) else original_size
        assert result_font.cget("size") == expected_size

    def test_user_can_create_fonts_with_precise_scaling_factors(self, tk_root: tk.Tk) -> None:
        """
        User can apply precise scaling factors for fine-tuned typography.

        GIVEN: Various scaling scenarios
        WHEN: User applies different scale factors
        THEN: Should correctly calculate scaled sizes using integer conversion
        """
        # Test various scaling scenarios
        test_cases: list[tuple[dict[str, Union[str, int]], float, int]] = [
            ({"family": "Times", "size": 10}, 1.1, 11),  # 10 * 1.1 = 11
            ({"family": "Arial", "size": 12}, 1.25, 15),  # 12 * 1.25 = 15
            ({"family": "Verdana", "size": 14}, 1.5, 21),  # 14 * 1.5 = 21
            ({"family": "Georgia", "size": 16}, 0.75, 12),  # 16 * 0.75 = 12
        ]

        for config, scale, expected_size in test_cases:
            # Act: Create scaled font
            result_font = create_scaled_font(config.copy(), scale)

            # Assert: Size should be correctly scaled and converted to int
            assert result_font.cget("size") == expected_size, f"Failed for scale {scale}"

    def test_user_font_config_is_modified_in_place_for_efficiency(self, tk_root: tk.Tk) -> None:
        """
        User's font configuration dictionary is modified in-place for memory efficiency.

        GIVEN: A font configuration dictionary
        WHEN: User creates a scaled font
        THEN: The original dictionary should have its size modified (side effect)
        """
        # Arrange: Create a font configuration
        font_config: dict[str, Union[str, int]] = {"family": "Segoe UI", "size": 9}
        original_id = id(font_config)

        # Act: Create scaled font
        create_scaled_font(font_config, 1.3)

        # Assert: Dictionary should be modified in place (same object)
        assert id(font_config) == original_id
        assert font_config["size"] == 11  # 9 * 1.3 = 11.7, int() = 11

    def test_user_can_preserve_original_config_by_passing_copy(self, tk_root: tk.Tk) -> None:
        """
        User can preserve original font config by passing a copy.

        GIVEN: A font configuration that should be preserved
        WHEN: User passes a copy of the config to create_scaled_font
        THEN: The original config should remain unchanged
        """
        # Arrange: Create original font configuration
        original_config: dict[str, Union[str, int]] = {"family": "Calibri", "size": 11}
        original_size = original_config["size"]

        # Act: Create scaled font with a copy
        create_scaled_font(original_config.copy(), 2.0)

        # Assert: Original should be unchanged
        assert original_config["size"] == original_size
        assert original_config["family"] == "Calibri"

    def test_user_can_create_fonts_for_different_ui_contexts(self, tk_root: tk.Tk) -> None:
        """
        User can create appropriately scaled fonts for different UI contexts.

        GIVEN: A base font configuration
        WHEN: User creates fonts for headers, body text, and captions
        THEN: Should create Font objects with appropriate relative sizing
        """
        # Arrange: Base font configuration
        base_config: dict[str, Union[str, int]] = {"family": "Roboto", "size": 10}

        # Act: Create fonts for different contexts
        header_font = create_scaled_font(base_config.copy(), 1.6)  # 60% larger
        body_font = create_scaled_font(base_config.copy(), 1.0)  # Normal
        caption_font = create_scaled_font(base_config.copy(), 0.85)  # 15% smaller

        # Assert: All should be valid Font objects with correct scaling
        assert isinstance(header_font, tkfont.Font)
        assert isinstance(body_font, tkfont.Font)
        assert isinstance(caption_font, tkfont.Font)

        assert header_font.cget("size") == 16  # 10 * 1.6 = 16
        assert body_font.cget("size") == 10  # 10 * 1.0 = 10
        assert caption_font.cget("size") == 8  # 10 * 0.85 = 8.5, int() = 8
