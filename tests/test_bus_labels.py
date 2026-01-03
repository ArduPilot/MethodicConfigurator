#!/usr/bin/env python3

"""
Tests for bus labels functionality in component editor.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

from ardupilot_methodic_configurator.data_model_vehicle_components_validation import (
    SERIAL_BUS_LABELS,
    SERIAL_PORTS,
    get_connection_type_tuples_with_labels,
)


class TestBusLabels:
    """Test bus labels functionality."""

    def test_serial_bus_labels_defined(self) -> None:
        """Test that SERIAL_BUS_LABELS is properly defined."""
        assert isinstance(SERIAL_BUS_LABELS, dict)
        assert len(SERIAL_BUS_LABELS) == 8
        assert SERIAL_BUS_LABELS["SERIAL1"] == "Telem1 (SERIAL1)"
        assert SERIAL_BUS_LABELS["SERIAL2"] == "Telem2 (SERIAL2)"
        assert SERIAL_BUS_LABELS["SERIAL3"] == "GPS1 (SERIAL3)"
        assert SERIAL_BUS_LABELS["SERIAL4"] == "GPS2 (SERIAL4)"
        # SERIAL5-8 don't have special labels, they use their own names
        assert SERIAL_BUS_LABELS["SERIAL5"] == "SERIAL5"
        assert SERIAL_BUS_LABELS["SERIAL6"] == "SERIAL6"
        assert SERIAL_BUS_LABELS["SERIAL7"] == "SERIAL7"
        assert SERIAL_BUS_LABELS["SERIAL8"] == "SERIAL8"

    def test_get_connection_type_tuples_with_labels_serial_ports(self) -> None:
        """Test conversion of SERIAL ports to tuples with labels."""
        result = get_connection_type_tuples_with_labels(tuple(SERIAL_PORTS))

        # Check that we get the right number of tuples
        assert len(result) == 8

        # Check specific tuples
        assert result[0] == ("SERIAL1", "Telem1 (SERIAL1)")
        assert result[1] == ("SERIAL2", "Telem2 (SERIAL2)")
        assert result[2] == ("SERIAL3", "GPS1 (SERIAL3)")
        assert result[3] == ("SERIAL4", "GPS2 (SERIAL4)")
        assert result[4] == ("SERIAL5", "SERIAL5")
        assert result[5] == ("SERIAL6", "SERIAL6")
        assert result[6] == ("SERIAL7", "SERIAL7")
        assert result[7] == ("SERIAL8", "SERIAL8")

    def test_get_connection_type_tuples_with_labels_non_serial(self) -> None:
        """Test conversion of non-SERIAL ports (should return as-is)."""
        test_ports = ("CAN1", "CAN2", "I2C1")
        result = get_connection_type_tuples_with_labels(test_ports)

        # Non-SERIAL ports should be returned as (value, value)
        assert result == [("CAN1", "CAN1"), ("CAN2", "CAN2"), ("I2C1", "I2C1")]

    def test_get_connection_type_tuples_with_labels_mixed(self) -> None:
        """Test conversion of mixed SERIAL and non-SERIAL ports."""
        test_ports = ("None", "SERIAL1", "SERIAL3", "CAN1", "SERIAL5")
        result = get_connection_type_tuples_with_labels(test_ports)

        expected = [
            ("None", "None"),
            ("SERIAL1", "Telem1 (SERIAL1)"),
            ("SERIAL3", "GPS1 (SERIAL3)"),
            ("CAN1", "CAN1"),
            ("SERIAL5", "SERIAL5"),
        ]
        assert result == expected

    def test_get_connection_type_tuples_with_labels_empty(self) -> None:
        """Test conversion of empty tuple."""
        result = get_connection_type_tuples_with_labels(())
        assert not result
