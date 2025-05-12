"""
ArduPilot parameter bitmask utilities.

This file is part of Ardupilot methodic configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2025 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""


class BitmaskHelper:
    """Helper class for working with ArduPilot parameter bitmasks."""

    @staticmethod
    def get_checked_keys(value: int, bitmask_dict: dict[int, str]) -> set[int]:
        """
        Convert a decimal value to a set of checked bit keys.

        Args:
            value: The decimal value to convert
            bitmask_dict: Dictionary mapping bit positions to descriptions

        Returns:
            Set of keys (bit positions) that are set in the value

        """
        return {key for key in bitmask_dict if (value >> key) & 1}

    @staticmethod
    def get_value_from_keys(checked_keys: list[int]) -> int:
        """
        Convert a list of checked bit keys to a decimal value.

        Args:
            checked_keys: List of bit positions that are set

        Returns:
            The decimal value representing the bits set

        """
        return sum(1 << key for key in checked_keys)

    @staticmethod
    def get_description(value: int, bitmask_dict: dict[int, str]) -> str:
        """
        Get a human-readable description of which bits are set.

        Args:
            value: The decimal value
            bitmask_dict: Dictionary mapping bit positions to descriptions

        Returns:
            String listing the descriptions of set bits, comma-separated

        """
        checked_keys = BitmaskHelper.get_checked_keys(value, bitmask_dict)
        if not checked_keys:
            return "None"

        return ", ".join(bitmask_dict[key] for key in sorted(checked_keys))
