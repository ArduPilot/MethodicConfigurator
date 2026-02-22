"""
Recent items history list manager.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

from typing import Any, Callable, Optional

from ardupilot_methodic_configurator import _


class RecentItemsHistoryList:
    """
    Helper class to manage most-recent-first (LIFO) history lists with deduplication.

    This class provides a reusable pattern for managing history lists in settings,
    with configurable validation, normalization, and comparison strategies.
    """

    def __init__(  # pylint: disable=too-many-arguments, too-many-positional-arguments
        self,
        settings_key: str,
        max_items: int,
        normalizer: Optional[Callable[[str], str]] = None,
        validator: Optional[Callable[[str], None]] = None,
        comparer: Optional[Callable[[str], str]] = None,
    ) -> None:
        """
        Initialize a history list manager.

        Args:
            settings_key: The key in settings dict where this history is stored
            max_items: Maximum number of items to keep in history
            normalizer: Optional function to normalize items before storage (default: identity)
            validator: Optional function to validate items before storage (called if provided, raises on invalid)
            comparer: Optional function to normalize items for duplicate detection (default: identity)

        """
        self.settings_key = settings_key
        self.max_items = max_items
        self.normalizer = normalizer or (lambda x: x)
        self.validator = validator
        self.comparer = comparer or (lambda x: x)

    def get_items(self, settings: dict[str, Any]) -> list[str]:
        """
        Get the history list from settings.

        Args:
            settings: The settings dictionary

        Returns:
            List of items in most-recent-first order, filtered to valid strings only

        """
        history = settings.get(self.settings_key, [])

        # Handle corrupted data gracefully
        if not isinstance(history, list):
            return []

        # Ensure all entries are strings
        return [item for item in history if isinstance(item, str)]

    def store_item(self, item: str, settings: dict[str, Any]) -> dict[str, Any]:
        """
        Store an item in the history list.

        The item is added to the front of the list. If it already exists,
        it is moved to the front. The list is limited to max_items.

        Performs minimal validation to reject truly invalid inputs (empty strings, null bytes),
        then calls the validator if one was provided during initialization.

        Args:
            item: The item to store
            settings: The settings dictionary

        Returns:
            Updated settings dictionary

        Raises:
            ValueError: If item is empty, contains null byte, or fails validator check

        """
        # Minimal validation: reject truly invalid inputs
        if not item:
            msg = _("Cannot store empty string in history")
            raise ValueError(msg)
        if "\x00" in item:
            msg = _("Cannot store item with null byte in history")
            raise ValueError(msg)

        # Call the validator if provided
        if self.validator is not None:
            self.validator(item)

        history = settings.get(self.settings_key, [])

        # Handle corrupted data
        if not isinstance(history, list):
            history = []

        # Normalize the item for storage
        normalized_item = self.normalizer(item)

        # Remove duplicates using equality comparer
        history = self._remove_duplicate(history, normalized_item)

        # Add to front
        history.insert(0, normalized_item)

        # Limit to max items
        history = history[: self.max_items]

        # Update settings
        settings[self.settings_key] = history
        return settings

    def remove_item(self, item: str, settings: dict[str, Any]) -> dict[str, Any]:
        """
        Remove an item from the history list.

        Args:
            item: The item to remove
            settings: The settings dictionary

        Returns:
            Updated settings dictionary

        """
        history = settings.get(self.settings_key, [])

        if not isinstance(history, list):
            return settings

        # Remove the item
        history = self._remove_duplicate(history, item)

        # Update settings
        settings[self.settings_key] = history
        return settings

    def _remove_duplicate(self, history: list[str], item: str) -> list[str]:
        """
        Remove duplicate item from list while preserving order.

        Args:
            history: List of items
            item: Item to remove if it exists

        Returns:
            List with duplicate removed, order preserved

        """
        normalized_target = self.comparer(item)
        return [h for h in history if self.comparer(h) != normalized_target]
