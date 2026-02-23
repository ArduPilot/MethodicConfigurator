#!/usr/bin/env python3

"""
Unit tests for RecentItemsHistoryList data model implementation details.

These tests cover implementation details, edge cases, internal robustness,
and configuration mechanisms that are not business-level behaviors.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import pytest

from ardupilot_methodic_configurator.data_model_recent_items_history_list import RecentItemsHistoryList


class TestRecentItemsHistoryListValidationDetails:  # pylint: disable=too-few-public-methods
    """Test low-level validation implementation details."""

    def test_cannot_store_string_with_null_byte(self) -> None:
        """Null bytes are rejected as invalid input."""
        history = RecentItemsHistoryList(settings_key="test_history", max_items=5)
        settings: dict = {}

        with pytest.raises(ValueError, match="Cannot store item with null byte in history"):
            history.store_item("item\x00value", settings)


class TestRecentItemsHistoryListNormalizationMechanism:
    """Test item normalization mechanism implementation."""

    def test_normalizer_function_is_called_before_storage(self) -> None:
        """Normalizer function is applied to items before storage."""
        history = RecentItemsHistoryList(
            settings_key="test_history",
            max_items=5,
            normalizer=str.strip,
        )
        settings: dict = {}

        settings = history.store_item("  tcp:127.0.0.1:5760  ", settings)
        settings = history.store_item("\tudp:localhost:14550\n", settings)

        items = history.get_items(settings)
        assert items == ["udp:localhost:14550", "tcp:127.0.0.1:5760"]

    def test_normalized_items_prevent_duplicates_with_different_whitespace(self) -> None:
        """Normalization prevents duplicate entries that differ only in whitespace."""
        history = RecentItemsHistoryList(
            settings_key="test_history",
            max_items=5,
            normalizer=str.strip,
        )
        settings: dict = {}

        settings = history.store_item("tcp:127.0.0.1:5760", settings)
        settings = history.store_item("  tcp:127.0.0.1:5760  ", settings)
        settings = history.store_item("\ttcp:127.0.0.1:5760\n", settings)

        items = history.get_items(settings)
        assert items == ["tcp:127.0.0.1:5760"]
        assert len(items) == 1


class TestRecentItemsHistoryListCustomComparerConfiguration:
    """Test custom comparer configuration mechanism."""

    def test_case_insensitive_duplicate_detection_with_custom_comparer(self) -> None:
        """Custom comparer enables case-insensitive duplicate detection."""
        history = RecentItemsHistoryList(
            settings_key="test_history",
            max_items=5,
            comparer=str.lower,
        )
        settings: dict = {}

        settings = history.store_item("TCP:127.0.0.1:5760", settings)
        settings = history.store_item("tcp:127.0.0.1:5760", settings)

        items = history.get_items(settings)
        assert items == ["tcp:127.0.0.1:5760"]
        assert len(items) == 1

    def test_custom_comparer_with_domain_specific_logic(self) -> None:
        """Custom comparer can implement domain-specific duplicate detection."""

        def extract_host(item: str) -> str:
            # Simplified: extract portion after "tcp:" and before ":"
            if "tcp:" in item:
                return item.split("tcp:")[1].split(":", maxsplit=1)[0]
            return item

        history = RecentItemsHistoryList(
            settings_key="test_history",
            max_items=5,
            comparer=extract_host,
        )
        settings: dict = {}

        settings = history.store_item("tcp:127.0.0.1:5760", settings)
        settings = history.store_item("tcp:127.0.0.1:5761", settings)

        items = history.get_items(settings)
        assert items == ["tcp:127.0.0.1:5761"]
        assert len(items) == 1


class TestRecentItemsHistoryListCorruptedDataHandling:
    """Test internal robustness against corrupted settings data."""

    def test_graceful_handling_of_non_list_settings_data(self) -> None:
        """Non-list data in settings returns empty list without raising errors."""
        history = RecentItemsHistoryList(settings_key="test_history", max_items=5)
        settings = {"test_history": "corrupted_string_instead_of_list"}

        items = history.get_items(settings)

        assert items == []

    def test_graceful_handling_of_non_string_items_in_list(self) -> None:
        """Non-string items are filtered out from corrupted lists."""
        history = RecentItemsHistoryList(settings_key="test_history", max_items=5)
        settings = {"test_history": ["valid_string", 123, None, "another_valid", {"key": "value"}]}

        items = history.get_items(settings)

        assert items == ["valid_string", "another_valid"]

    def test_storing_item_recovers_from_corrupted_settings(self) -> None:
        """Storing an item automatically recovers from corrupted settings data."""
        history = RecentItemsHistoryList(settings_key="test_history", max_items=5)
        settings = {"test_history": "corrupted"}

        settings = history.store_item("new_item", settings)

        items = history.get_items(settings)
        assert items == ["new_item"]

    def test_removing_item_handles_corrupted_settings_gracefully(self) -> None:
        """Removing an item handles corrupted settings without raising errors."""
        history = RecentItemsHistoryList(settings_key="test_history", max_items=5)
        settings = {"test_history": 42}

        updated_settings = history.remove_item("nonexistent", settings)

        assert updated_settings == settings


class TestRecentItemsHistoryListMultipleInstances:  # pylint: disable=too-few-public-methods
    """Test Python object model with multiple history instances."""

    def test_multiple_history_lists_operate_independently(self) -> None:
        """Multiple history list instances can operate independently in same settings."""
        connection_history = RecentItemsHistoryList(settings_key="connections", max_items=5)
        project_history = RecentItemsHistoryList(settings_key="projects", max_items=5)
        settings: dict = {}

        settings = connection_history.store_item("tcp:127.0.0.1:5760", settings)
        settings = connection_history.store_item("udp:127.0.0.1:14550", settings)
        settings = project_history.store_item("/path/to/project1", settings)
        settings = project_history.store_item("/path/to/project2", settings)

        connection_items = connection_history.get_items(settings)
        project_items = project_history.get_items(settings)

        assert connection_items == ["udp:127.0.0.1:14550", "tcp:127.0.0.1:5760"]
        assert project_items == ["/path/to/project2", "/path/to/project1"]


class TestRecentItemsHistoryListEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_history_with_max_items_of_one(self) -> None:
        """History list with max_items=1 keeps only the most recent item."""
        history = RecentItemsHistoryList(settings_key="test_history", max_items=1)
        settings: dict = {}

        settings = history.store_item("item1", settings)
        settings = history.store_item("item2", settings)
        settings = history.store_item("item3", settings)

        items = history.get_items(settings)
        assert items == ["item3"]
        assert len(items) == 1

    def test_removing_nonexistent_item_does_not_affect_history(self) -> None:
        """Removing a non-existent item does not affect the existing history."""
        history = RecentItemsHistoryList(settings_key="test_history", max_items=5)
        settings: dict = {}
        settings = history.store_item("item1", settings)
        settings = history.store_item("item2", settings)

        settings = history.remove_item("nonexistent", settings)

        items = history.get_items(settings)
        assert items == ["item2", "item1"]

    def test_history_handles_unicode_and_special_characters(self) -> None:
        """History list correctly handles Unicode and special characters."""
        history = RecentItemsHistoryList(settings_key="test_history", max_items=5)
        settings: dict = {}

        settings = history.store_item("tcp://🚁:5760", settings)
        settings = history.store_item("path/with/日本語/characters", settings)
        settings = history.store_item("item!@#$%^&*()", settings)

        items = history.get_items(settings)
        assert items == ["item!@#$%^&*()", "path/with/日本語/characters", "tcp://🚁:5760"]
