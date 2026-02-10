#!/usr/bin/env python3

"""
Behavior-driven tests that validate the structure of the data_model_fc_ids module.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

from ardupilot_methodic_configurator import data_model_fc_ids as fc_ids


class TestFlightControllerIdsDataIntegrity:
    """BDD-style tests ensuring the generated FC ID data keeps expected types."""

    def test_vid_vendor_dict_ensures_int_keys_and_string_lists(self) -> None:
        """
        VID vendor mapping uses integers and string lists.

        GIVEN: The VID to vendor mapping contains multiple USB vendors
        WHEN: The mapping is inspected for datatype consistency
        THEN: Every key is an integer and every value is a non-empty list of strings
        """
        for vid, vendors in fc_ids.VID_VENDOR_DICT.items():
            assert isinstance(vid, int)
            assert isinstance(vendors, list)
            assert vendors, "Vendor list must not be empty"
            assert all(isinstance(name, str) and name for name in vendors)

    def test_vid_pid_product_dict_uses_tuple_keys_and_string_lists(self) -> None:
        """
        VID/PID mapping stores tuple keys and string lists.

        GIVEN: The VID/PID to product mapping represents USB products
        WHEN: The mapping is validated
        THEN: Keys are (int, int) tuples and values are non-empty string lists
        """
        for key, products in fc_ids.VID_PID_PRODUCT_DICT.items():
            assert isinstance(key, tuple)
            assert len(key) == 2
            assert all(isinstance(part, int) for part in key)
            assert isinstance(products, list)
            assert products, "Product list must not be empty"
            assert all(isinstance(product, str) and product for product in products)

    def test_apj_board_dicts_share_identical_keys_and_string_values(self) -> None:
        """
        APJ board dictionaries expose matching key sets.

        GIVEN: The APJ board dictionaries describe names, vendors, and MCU series
        WHEN: The dictionaries are compared
        THEN: They expose the same key set and each entry lists non-empty strings
        """
        name_keys = set(fc_ids.APJ_BOARD_ID_NAME_DICT)
        vendor_keys = set(fc_ids.APJ_BOARD_ID_VENDOR_DICT)
        mcu_keys = set(fc_ids.APJ_BOARD_ID_MCU_SERIES_DICT)

        assert name_keys == vendor_keys == mcu_keys

        for board_id in name_keys:
            assert isinstance(board_id, int)
            names = fc_ids.APJ_BOARD_ID_NAME_DICT[board_id]
            vendors = fc_ids.APJ_BOARD_ID_VENDOR_DICT[board_id]
            mcu_series = fc_ids.APJ_BOARD_ID_MCU_SERIES_DICT[board_id]

            assert isinstance(names, list)
            assert names
            assert isinstance(vendors, list)
            assert vendors
            assert isinstance(mcu_series, list)
            assert mcu_series
            assert all(isinstance(name, str) and name for name in names)
            assert all(isinstance(vendor, str) and vendor for vendor in vendors)
            assert all(isinstance(series, str) and series for series in mcu_series)

    def test_mcu_series_mapping_references_known_board_ids(self) -> None:
        """
        MCU series entries only reference known board IDs.

        GIVEN: The MCU series to board ID mapping cross-references board metadata
        WHEN: The mapping is validated
        THEN: Every series is a string and every referenced ID exists in the board dictionaries
        """
        known_board_ids = set(fc_ids.APJ_BOARD_ID_NAME_DICT)
        referenced_board_ids: set[int] = set()

        for series, board_ids in fc_ids.MCU_SERIES_APJ_BOARD_ID_DICT.items():
            assert isinstance(series, str)
            assert series
            assert isinstance(board_ids, list)
            assert board_ids
            assert all(isinstance(board_id, int) and board_id in known_board_ids for board_id in board_ids)
            referenced_board_ids.update(board_ids)

        assert referenced_board_ids.issuperset(known_board_ids)
