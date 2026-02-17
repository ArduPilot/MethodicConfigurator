#!/usr/bin/env python3

"""
BDD tests for RecentItemsHistoryList data model.

These tests focus on business-level behavior from the perspective of calling code.
For implementation details and edge cases, see unit_data_model_recent_items_history_list.py.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import pytest

from ardupilot_methodic_configurator.data_model_recent_items_history_list import RecentItemsHistoryList


class TestHistoryListBasicOperations:
    """Test core history list operations and business rules."""

    def test_empty_history_returns_empty_list(self) -> None:
        """
        Empty history returns an empty list.

        GIVEN: A fresh history list manager with no stored items
        WHEN: Calling code requests the history items
        THEN: An empty list should be returned
        """
        # Arrange: Create history manager with empty settings
        history = RecentItemsHistoryList(settings_key="test_history", max_items=5)
        settings: dict = {}

        # Act: Retrieve items from empty history
        items = history.get_items(settings)

        # Assert: Empty list returned
        assert items == []

    def test_stored_item_is_retrievable(self) -> None:
        """
        Stored items can be retrieved from history.

        GIVEN: An empty history list
        WHEN: Calling code stores a single item
        THEN: The item should be retrievable from the history
        """
        # Arrange: Create history manager
        history = RecentItemsHistoryList(settings_key="connections", max_items=5)
        settings: dict = {}

        # Act: Store an item
        settings = history.store_item("tcp:127.0.0.1:5760", settings)

        # Assert: Item is stored and retrievable
        items = history.get_items(settings)
        assert items == ["tcp:127.0.0.1:5760"]

    def test_items_returned_in_most_recent_first_order(self) -> None:
        """
        Items are returned in most-recent-first (LIFO) order.

        GIVEN: A history list manager
        WHEN: Calling code stores multiple items sequentially
        THEN: Items should be returned in reverse chronological order
        """
        # Arrange: Create history manager
        history = RecentItemsHistoryList(settings_key="connections", max_items=10)
        settings: dict = {}

        # Act: Store items in chronological order
        settings = history.store_item("tcp:192.168.1.1:5760", settings)
        settings = history.store_item("udp:127.0.0.1:14550", settings)
        settings = history.store_item("/dev/ttyUSB0", settings)

        # Assert: Most recent item appears first
        items = history.get_items(settings)
        assert items == ["/dev/ttyUSB0", "udp:127.0.0.1:14550", "tcp:192.168.1.1:5760"]

    def test_duplicate_item_moves_to_front_without_duplication(self) -> None:
        """
        Storing a duplicate item moves it to the front without creating duplicates.

        GIVEN: A history list with existing items
        WHEN: Calling code stores an item that already exists
        THEN: The existing item should move to the front; no duplicate should be created
        """
        # Arrange: Create history with several items
        history = RecentItemsHistoryList(settings_key="test_history", max_items=5)
        settings: dict = {}
        settings = history.store_item("connection1", settings)
        settings = history.store_item("connection2", settings)
        settings = history.store_item("connection3", settings)

        # Act: Store an existing item again
        settings = history.store_item("connection2", settings)

        # Assert: Item moved to front, no duplicates created
        items = history.get_items(settings)
        assert items == ["connection2", "connection3", "connection1"]
        assert len(items) == 3

    def test_item_can_be_removed_from_history(self) -> None:
        """
        Items can be removed from history.

        GIVEN: A history list with multiple items
        WHEN: Calling code removes a specific item
        THEN: The item should be removed while preserving the order of remaining items
        """
        # Arrange: Create history with items
        history = RecentItemsHistoryList(settings_key="projects", max_items=5)
        settings: dict = {}
        settings = history.store_item("/path/project1", settings)
        settings = history.store_item("/path/project2", settings)
        settings = history.store_item("/path/project3", settings)

        # Act: Remove middle item
        settings = history.remove_item("/path/project2", settings)

        # Assert: Item removed, order preserved
        items = history.get_items(settings)
        assert items == ["/path/project3", "/path/project1"]
        assert "/path/project2" not in items


class TestHistoryListSizeManagement:
    """Test history list size limits and capacity management."""

    def test_history_enforces_maximum_size_limit(self) -> None:
        """
        History list enforces the configured maximum size limit.

        GIVEN: A history manager configured with a maximum of 3 items
        WHEN: Calling code stores more than 3 items
        THEN: Only the 3 most recent items should be retained
        """
        # Arrange: Create history with max_items=3
        history = RecentItemsHistoryList(settings_key="test_history", max_items=3)
        settings: dict = {}

        # Act: Store 5 items (exceeding max)
        for i in range(1, 6):
            settings = history.store_item(f"item{i}", settings)

        # Assert: Only last 3 items retained
        items = history.get_items(settings)
        assert items == ["item5", "item4", "item3"]
        assert len(items) == 3

    def test_oldest_items_automatically_discarded_when_at_capacity(self) -> None:
        """
        Oldest items are automatically discarded when storage limit is reached.

        GIVEN: A full history list at maximum capacity
        WHEN: Calling code stores a new item
        THEN: The oldest item should be automatically removed
        """
        # Arrange: Create full history at maximum capacity
        history = RecentItemsHistoryList(settings_key="test_history", max_items=3)
        settings: dict = {}
        settings = history.store_item("oldest", settings)
        settings = history.store_item("middle", settings)
        settings = history.store_item("newest", settings)

        # Act: Add one more item
        settings = history.store_item("brand_new", settings)

        # Assert: Oldest item discarded, new item at front
        items = history.get_items(settings)
        assert items == ["brand_new", "newest", "middle"]
        assert "oldest" not in items


class TestHistoryListValidationRules:
    """Test business validation rules for history items."""

    def test_empty_strings_are_rejected(self) -> None:
        """
        Empty strings cannot be stored in history.

        GIVEN: A history list manager
        WHEN: Calling code attempts to store an empty string
        THEN: A ValueError should be raised
        """
        # Arrange: Create history manager
        history = RecentItemsHistoryList(settings_key="test_history", max_items=5)
        settings: dict = {}

        # Act & Assert: Empty string raises ValueError
        with pytest.raises(ValueError, match="Cannot store empty string in history"):
            history.store_item("", settings)

    def test_custom_validation_rules_are_enforced(self) -> None:
        """
        Custom validation rules are enforced when storing items.

        GIVEN: A history manager with custom validation rules
        WHEN: Calling code attempts to store an item that violates the rules
        THEN: A ValueError should be raised by the validator
        """

        # Arrange: Create validator for business rule (e.g., max length)
        def validate_connection_string(item: str) -> None:
            if len(item) > 200:
                msg = "Connection string too long (max 200 characters)"
                raise ValueError(msg)

        history = RecentItemsHistoryList(
            settings_key="connections",
            max_items=10,
            validator=validate_connection_string,
        )
        settings: dict = {}

        # Act & Assert: Long string fails validation
        with pytest.raises(ValueError, match="Connection string too long"):
            history.store_item("x" * 201, settings)

    def test_items_passing_validation_are_stored_successfully(self) -> None:
        """
        Items that pass validation are stored successfully.

        GIVEN: A history manager with custom validation rules
        WHEN: Calling code stores an item that meets all validation requirements
        THEN: The item should be stored successfully
        """

        # Arrange: Create validator
        def validate_connection_string(item: str) -> None:
            if len(item) > 200:
                msg = "Connection string too long"
                raise ValueError(msg)

        history = RecentItemsHistoryList(
            settings_key="connections",
            max_items=10,
            validator=validate_connection_string,
        )
        settings: dict = {}

        # Act: Store valid item
        settings = history.store_item("tcp:127.0.0.1:5760", settings)

        # Assert: Item stored successfully
        items = history.get_items(settings)
        assert items == ["tcp:127.0.0.1:5760"]
