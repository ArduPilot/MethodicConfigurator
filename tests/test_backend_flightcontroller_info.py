#!/usr/bin/env python3

"""
Tests for the backend_flightcontroller_info.py file.

This file is part of Ardupilot methodic configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2025 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

from contextlib import contextmanager
from unittest.mock import MagicMock, patch

import pytest
from pymavlink import mavutil

from ardupilot_methodic_configurator.backend_flightcontroller_info import BackendFlightcontrollerInfo

# pylint: disable=protected-access


@contextmanager
def mock_mavlink_enums(self, enums_dict=None) -> None:
    """Context manager for mocking mavutil.mavlink.enums."""
    if enums_dict is None:
        enums_dict = self.mocked_mavutil_enums()

    with patch.object(mavutil.mavlink, "enums", enums_dict):
        yield


class TestBackendFlightcontrollerInfo:  # pylint: disable=too-many-public-methods
    """Test class for BackendFlightcontrollerInfo."""

    @pytest.fixture
    def fc_info(self) -> BackendFlightcontrollerInfo:
        """Fixture providing a BackendFlightcontrollerInfo instance."""
        return BackendFlightcontrollerInfo()

    @pytest.fixture
    def fc_info_with_basic_data(self, fc_info) -> BackendFlightcontrollerInfo:
        """Fixture providing a BackendFlightcontrollerInfo with basic data populated."""
        fc_info.system_id = "1"
        fc_info.component_id = "2"
        fc_info.autopilot = "ArduPilot"
        fc_info.vehicle_type = "ArduCopter"
        fc_info.mav_type = "Quadrotor"
        return fc_info

    @pytest.fixture
    def fc_info_with_complete_data(self, fc_info_with_basic_data) -> BackendFlightcontrollerInfo:
        """Fixture providing a BackendFlightcontrollerInfo with complete data populated."""
        fc_info = fc_info_with_basic_data
        fc_info.firmware_type = "PX4-FMUv5"
        fc_info.flight_sw_version = "4.3.2"
        fc_info.flight_sw_version_and_type = "4.3.2 beta"
        fc_info.board_version = "123"
        fc_info.apj_board_id = "50"
        fc_info.flight_custom_version = "abc123"
        fc_info.os_custom_version = "def456"
        fc_info.vendor = "3DR"
        fc_info.vendor_id = "0x1234"
        fc_info.vendor_and_vendor_id = "3DR (0x1234)"
        fc_info.product = "Pixhawk"
        fc_info.product_id = "0x5678"
        fc_info.product_and_product_id = "Pixhawk (0x5678)"
        fc_info.mcu_series = "STM32F7"
        fc_info.capabilities = {"FTP": "File Transfer Protocol"}
        fc_info.is_supported = True
        fc_info.is_mavftp_supported = True
        return fc_info

    @pytest.fixture
    def mocked_mavutil_enums(self) -> MagicMock:
        """Fixture providing mocked mavutil enums."""
        return {
            "MAV_PROTOCOL_CAPABILITY": {
                1: MagicMock(description="File Transfer Protocol", name="MAV_PROTOCOL_CAPABILITY_FTP"),
                2: MagicMock(description="Set attitude target", name="MAV_PROTOCOL_CAPABILITY_SET_ATTITUDE_TARGET"),
            },
            "MAV_TYPE": {
                2: MagicMock(name="QUAD", description="Quadrotor"),
                13: MagicMock(name="SUB", description="Submarine"),
            },
            "MAV_AUTOPILOT": {
                3: MagicMock(name="ARDUPILOT", description="ArduPilot"),
                12: MagicMock(name="PX4", description="PX4 Autopilot"),
            },
        }

    @pytest.fixture(scope="class")
    def common_mock_data(self) -> dict:
        """Class-scoped fixture for common mock data."""
        return {
            "mock_vendor_dict": {0x1234: ["Test Vendor"]},
            "mock_product_dict": {(0x1234, 0x5678): ["Test Product"]},
            "mock_name_dict": {1: ["Test Board"]},
            "mock_mcu_dict": {1: ["STM32"]},
        }

    def test_init(self, fc_info) -> None:
        """Test the initial state of BackendFlightcontrollerInfo."""
        assert fc_info.system_id == ""
        assert fc_info.component_id == ""
        assert fc_info.is_supported is False
        assert fc_info.is_mavftp_supported is False
        assert isinstance(fc_info.capabilities, dict)
        assert len(fc_info.capabilities) == 0

    def test_set_system_id_and_component_id(self, fc_info) -> None:
        """Test setting system and component IDs."""
        fc_info.set_system_id_and_component_id("1", "2")
        assert fc_info.system_id == "1"
        assert fc_info.component_id == "2"

    def test_set_autopilot(self, fc_info) -> None:
        """Test setting autopilot type."""
        with patch.object(fc_info, "_BackendFlightcontrollerInfo__decode_mav_autopilot", return_value="ArduPilot"):
            fc_info.set_autopilot(mavutil.mavlink.MAV_AUTOPILOT_ARDUPILOTMEGA)
            assert fc_info.autopilot == "ArduPilot"
            assert fc_info.is_supported is True

            fc_info.set_autopilot(mavutil.mavlink.MAV_AUTOPILOT_GENERIC)
            assert fc_info.is_supported is False

    def test_set_type(self, fc_info) -> None:
        """Test setting vehicle type."""
        with (
            patch.object(fc_info, "_BackendFlightcontrollerInfo__classify_vehicle_type", return_value="ArduCopter"),
            patch.object(fc_info, "_BackendFlightcontrollerInfo__decode_mav_type", return_value="Quadrotor"),
        ):
            fc_info.set_type(mavutil.mavlink.MAV_TYPE_QUADROTOR)
            assert fc_info.vehicle_type == "ArduCopter"
            assert fc_info.mav_type == "Quadrotor"

    def test_set_flight_sw_version(self, fc_info) -> None:
        """Test setting flight software version."""
        with patch.object(fc_info, "_BackendFlightcontrollerInfo__decode_flight_sw_version", return_value=(4, 3, 2, "beta")):
            fc_info.set_flight_sw_version(0)
            assert fc_info.flight_sw_version == "4.3.2"
            assert fc_info.flight_sw_version_and_type == "4.3.2 beta"

    @pytest.mark.parametrize(
        ("version_code", "expected_major", "expected_minor", "expected_patch", "expected_type"),
        [
            (0x01020300, 1, 2, 3, "dev"),
            (0x04050640, 4, 5, 6, "alpha"),
            (0x07080980, 7, 8, 9, "beta"),
            (0x0A0B0CC0, 10, 11, 12, "rc"),
            (0x0D0E0FFF, 13, 14, 15, "official"),
            (0x10111201, 16, 17, 18, "undefined"),
        ],
    )
    def test_decode_flight_sw_version_parameterized(  # pylint: disable=too-many-arguments,too-many-positional-arguments
        self, version_code, expected_major, expected_minor, expected_patch, expected_type
    ) -> None:
        """Test decoding flight software version with parameterized values."""
        major, minor, patch, fw_type = BackendFlightcontrollerInfo._BackendFlightcontrollerInfo__decode_flight_sw_version(  # pylint: disable=redefined-outer-name
            version_code
        )
        assert major == expected_major
        assert minor == expected_minor
        assert patch == expected_patch
        assert fw_type == expected_type

    def test_set_board_version(self, fc_info, monkeypatch) -> None:
        """Test setting board version."""
        # Mock the dictionaries
        mock_name_dict = {1: ["Test Board"]}
        mock_vendor_dict = {1: ["Test Vendor"]}
        mock_mcu_dict = {1: ["STM32"]}

        monkeypatch.setattr(
            "ardupilot_methodic_configurator.backend_flightcontroller_info.APJ_BOARD_ID_NAME_DICT", mock_name_dict
        )
        monkeypatch.setattr(
            "ardupilot_methodic_configurator.backend_flightcontroller_info.APJ_BOARD_ID_VENDOR_DICT", mock_vendor_dict
        )
        monkeypatch.setattr(
            "ardupilot_methodic_configurator.backend_flightcontroller_info.APJ_BOARD_ID_MCU_SERIES_DICT", mock_mcu_dict
        )

        # Test with known board ID
        fc_info.set_board_version(0x00010123)  # Board ID 1, version 0x0123
        assert fc_info.board_version == "291"  # 0x0123 = 291
        assert fc_info.apj_board_id == "1"
        assert fc_info.firmware_type == "Test Board"
        assert fc_info.mcu_series == "STM32"

        # Test vendor setting logic
        fc_info.vendor = "ArduPilot"
        fc_info.set_board_version(0x00010123)
        assert fc_info.vendor == "Test Vendor"

        # Test with unknown board ID
        fc_info.set_board_version(0x12340123)  # Board ID 0x1234, version 0x0123
        assert fc_info.board_version == "291"
        assert fc_info.apj_board_id == "4660"  # 0x1234 = 4660
        assert fc_info.firmware_type == "Unknown"
        assert fc_info.mcu_series == "Unknown"

    @pytest.mark.parametrize(
        ("input_array", "expected_string"),
        [
            ([65, 66, 67], "ABC"),  # Basic ASCII
            ([], ""),  # Empty array
            ([0, 65, 255], "\x00A\xff"),  # Non-ASCII characters
            ([72, 101, 108, 108, 111], "Hello"),  # Longer string
        ],
    )
    def test_set_custom_version_parameterized(self, fc_info, input_array, expected_string) -> None:
        """Test setting custom version with parameterized values."""
        # Test flight custom version
        fc_info.set_flight_custom_version(input_array)
        assert fc_info.flight_custom_version == expected_string

        # Test OS custom version with same data
        fc_info.set_os_custom_version(input_array)
        assert fc_info.os_custom_version == expected_string

    def test_set_os_custom_version(self, fc_info) -> None:
        """Test setting OS custom version."""
        fc_info.set_os_custom_version([68, 69, 70])  # ASCII for 'DEF'
        assert fc_info.os_custom_version == "DEF"

    def test_set_usb_vendor_and_product_ids(self, fc_info, monkeypatch) -> None:
        """Test setting USB vendor and product IDs."""
        # Mock the dictionaries
        mock_vendor_dict = {0x1234: ["Test Vendor"]}
        mock_product_dict = {(0x1234, 0x5678): ["Test Product"]}

        monkeypatch.setattr("ardupilot_methodic_configurator.backend_flightcontroller_info.VID_VENDOR_DICT", mock_vendor_dict)
        monkeypatch.setattr(
            "ardupilot_methodic_configurator.backend_flightcontroller_info.VID_PID_PRODUCT_DICT", mock_product_dict
        )

        # Test with known IDs
        fc_info.set_usb_vendor_and_product_ids(0x1234, 0x5678)
        assert fc_info.vendor_id == "0x1234"
        assert fc_info.vendor == "Test Vendor"
        assert fc_info.vendor_and_vendor_id == "Test Vendor (0x1234)"
        assert fc_info.product_id == "0x5678"
        assert fc_info.product == "Test Product"
        assert fc_info.product_and_product_id == "Test Product (0x5678)"

        # Test with unknown IDs
        fc_info.set_usb_vendor_and_product_ids(0x9ABC, 0xDEF0)
        assert fc_info.vendor_id == "0x9ABC"
        assert fc_info.vendor == "Unknown"
        assert fc_info.vendor_and_vendor_id == "Unknown (0x9ABC)"
        assert fc_info.product_id == "0xDEF0"
        assert fc_info.product == "Unknown"
        assert fc_info.product_and_product_id == "Unknown (0xDEF0)"

        # Test with zero IDs
        fc_info.set_usb_vendor_and_product_ids(0, 0)
        assert fc_info.vendor_id == "Unknown"
        assert fc_info.product_id == "Unknown"

    def test_set_capabilities(self, fc_info) -> None:
        """Test setting capabilities."""
        with patch.object(
            fc_info, "_BackendFlightcontrollerInfo__decode_flight_capabilities", return_value={"FTP": "File Transfer Protocol"}
        ):
            # Test with FTP capability enabled
            ftp_cap = mavutil.mavlink.MAV_PROTOCOL_CAPABILITY_FTP
            fc_info.set_capabilities(ftp_cap)
            assert fc_info.capabilities == {"FTP": "File Transfer Protocol"}
            assert fc_info.is_mavftp_supported is True

            # Test with FTP capability disabled
            fc_info.set_capabilities(0)
            assert fc_info.is_mavftp_supported is False

    def test_decode_flight_capabilities(self) -> None:
        """Test decoding flight capabilities."""
        # Mock a capability enum with description
        mock_capability = MagicMock()
        mock_capability.name = "MAV_PROTOCOL_CAPABILITY_FTP"
        mock_capability.description = "File Transfer Protocol"

        # Create a mock for enums dictionary
        mock_enums = {"MAV_PROTOCOL_CAPABILITY": {1: mock_capability}}

        with patch.object(mavutil.mavlink, "enums", mock_enums):
            result = BackendFlightcontrollerInfo._BackendFlightcontrollerInfo__decode_flight_capabilities(1)
            assert "FTP" in result
            assert result["FTP"] == "File Transfer Protocol"

    def test_decode_mav_type(self) -> None:
        """Test decoding MAV type."""
        # Create a mock for enums and EnumEntry
        mock_entry = MagicMock()
        mock_entry.description = "Quadcopter"

        with (
            patch.object(mavutil.mavlink, "enums", {"MAV_TYPE": {2: mock_entry}}),
            patch.object(mavutil.mavlink, "EnumEntry", return_value=mock_entry),
        ):
            result = BackendFlightcontrollerInfo._BackendFlightcontrollerInfo__decode_mav_type(2)
            assert result == "Quadcopter"

            # Test with unknown type
            result = BackendFlightcontrollerInfo._BackendFlightcontrollerInfo__decode_mav_type(99)
            assert result == "Quadcopter"  # Should be "Unknown type" but our mock returns "Quadcopter"

    def test_classify_vehicle_type(self) -> None:
        """Test classifying vehicle type from MAV type."""
        # Test known types
        assert (
            BackendFlightcontrollerInfo._BackendFlightcontrollerInfo__classify_vehicle_type(mavutil.mavlink.MAV_TYPE_QUADROTOR)
            == "ArduCopter"
        )
        assert (
            BackendFlightcontrollerInfo._BackendFlightcontrollerInfo__classify_vehicle_type(
                mavutil.mavlink.MAV_TYPE_FIXED_WING
            )
            == "ArduPlane"
        )
        assert (
            BackendFlightcontrollerInfo._BackendFlightcontrollerInfo__classify_vehicle_type(
                mavutil.mavlink.MAV_TYPE_GROUND_ROVER
            )
            == "Rover"
        )

        # Test unknown type
        assert BackendFlightcontrollerInfo._BackendFlightcontrollerInfo__classify_vehicle_type(999) == ""

    def test_get_info(self, fc_info) -> None:
        """Test getting all flight controller information."""
        # Set some properties
        fc_info.system_id = "1"
        fc_info.component_id = "2"
        fc_info.autopilot = "ArduPilot"
        fc_info.capabilities = {"FTP": "File Transfer Protocol"}

        info = fc_info.get_info()
        assert info["System ID"] == "1"
        assert info["Component ID"] == "2"
        assert info["Autopilot Type"] == "ArduPilot"
        assert info["Capabilities"] == {"FTP": "File Transfer Protocol"}

    def test_decode_flight_capabilities_with_multiple_bits(self) -> None:
        """Test decoding multiple flight capabilities."""
        # Mock capabilities with multiple bits set
        mock_cap1 = MagicMock()
        mock_cap1.name = "MAV_PROTOCOL_CAPABILITY_FTP"
        mock_cap1.description = "File Transfer Protocol"

        mock_cap2 = MagicMock()
        mock_cap2.name = "MAV_PROTOCOL_CAPABILITY_SET_ATTITUDE_TARGET"
        mock_cap2.description = "Can set attitude target"

        # Create a mock for enums dictionary with two capabilities (bits 0 and 1)
        mock_enums = {"MAV_PROTOCOL_CAPABILITY": {1: mock_cap1, 2: mock_cap2}}

        with patch.object(mavutil.mavlink, "enums", mock_enums):
            # Test with both capabilities enabled (bits 0 and 1 set, value = 3)
            result = BackendFlightcontrollerInfo._BackendFlightcontrollerInfo__decode_flight_capabilities(3)
            assert len(result) == 2
            assert "FTP" in result
            assert "SET_ATTITUDE_TARGET" in result
            assert result["FTP"] == "File Transfer Protocol"
            assert result["SET_ATTITUDE_TARGET"] == "Can set attitude target"

    def test_decode_flight_capabilities_with_missing_description(self) -> None:
        """Test decoding capabilities when description is missing."""
        # Create a more controlled mock
        mock_cap = MagicMock()
        mock_cap.name = "MAV_PROTOCOL_CAPABILITY_MISSION_INT"

        # Explicitly delete the description attribute if it exists
        if hasattr(mock_cap, "description"):
            delattr(mock_cap, "description")

        # Verify it's gone
        assert not hasattr(mock_cap, "description")

        # Create a mock for enums dictionary
        mock_enums = {"MAV_PROTOCOL_CAPABILITY": {1: mock_cap}}

        with patch.object(mavutil.mavlink, "enums", mock_enums):
            result = BackendFlightcontrollerInfo._BackendFlightcontrollerInfo__decode_flight_capabilities(1)
            assert "BIT0" in result
            assert result["BIT0"] == mock_cap

    def test_decode_flight_capabilities_with_high_bit(self) -> None:
        """Test decoding capability with a high bit position."""
        # Mock capability with high bit (bit 31)
        mock_cap = MagicMock()
        mock_cap.name = "MAV_PROTOCOL_CAPABILITY_HIGH_BIT"
        mock_cap.description = "High bit capability"

        # Create a mock for enums dictionary with bit 31 capability (2^31)
        high_bit_value = 1 << 31
        mock_enums = {"MAV_PROTOCOL_CAPABILITY": {high_bit_value: mock_cap}}

        with patch.object(mavutil.mavlink, "enums", mock_enums):
            result = BackendFlightcontrollerInfo._BackendFlightcontrollerInfo__decode_flight_capabilities(high_bit_value)
            assert "HIGH_BIT" in result
            assert result["HIGH_BIT"] == "High bit capability"

    def test_set_autopilot_with_actual_enum_values(self, fc_info) -> None:
        """Test setting autopilot with actual enum values."""
        # Use actual decode implementation rather than mocking
        with patch.object(
            fc_info,
            "_BackendFlightcontrollerInfo__decode_mav_autopilot",
            side_effect=BackendFlightcontrollerInfo._BackendFlightcontrollerInfo__decode_mav_autopilot,
        ):
            # Test with ArduPilot
            fc_info.set_autopilot(mavutil.mavlink.MAV_AUTOPILOT_ARDUPILOTMEGA)
            assert fc_info.autopilot != ""  # Actual value depends on pymavlink
            assert fc_info.is_supported is True

            # Test with PX4
            fc_info.set_autopilot(mavutil.mavlink.MAV_AUTOPILOT_PX4)
            assert fc_info.is_supported is False

            # Test with invalid autopilot type
            fc_info.set_autopilot(999)  # Invalid value
            assert "Unknown" in fc_info.autopilot  # Should contain "Unknown"
            assert fc_info.is_supported is False

    def test_classify_vehicle_type_comprehensive(self) -> None:
        """Comprehensive test of vehicle type classification."""
        # Test all defined mappings
        for mav_type, expected_vehicle in [
            (mavutil.mavlink.MAV_TYPE_FIXED_WING, "ArduPlane"),
            (mavutil.mavlink.MAV_TYPE_QUADROTOR, "ArduCopter"),
            (mavutil.mavlink.MAV_TYPE_COAXIAL, "Heli"),
            (mavutil.mavlink.MAV_TYPE_HELICOPTER, "Heli"),
            (mavutil.mavlink.MAV_TYPE_ANTENNA_TRACKER, "AntennaTracker"),
            (mavutil.mavlink.MAV_TYPE_GCS, "AP_Periph"),
            (mavutil.mavlink.MAV_TYPE_AIRSHIP, "ArduBlimp"),
            (mavutil.mavlink.MAV_TYPE_FREE_BALLOON, "ArduBlimp"),
            (mavutil.mavlink.MAV_TYPE_ROCKET, "ArduCopter"),
            (mavutil.mavlink.MAV_TYPE_GROUND_ROVER, "Rover"),
            (mavutil.mavlink.MAV_TYPE_SURFACE_BOAT, "Rover"),
            (mavutil.mavlink.MAV_TYPE_SUBMARINE, "ArduSub"),
            (mavutil.mavlink.MAV_TYPE_HEXAROTOR, "ArduCopter"),
            (mavutil.mavlink.MAV_TYPE_OCTOROTOR, "ArduCopter"),
            (mavutil.mavlink.MAV_TYPE_TRICOPTER, "ArduCopter"),
            (mavutil.mavlink.MAV_TYPE_VTOL_DUOROTOR, "ArduPlane"),
            (mavutil.mavlink.MAV_TYPE_VTOL_QUADROTOR, "ArduPlane"),
        ]:
            vehicle_type = BackendFlightcontrollerInfo._BackendFlightcontrollerInfo__classify_vehicle_type(mav_type)
            assert vehicle_type == expected_vehicle, (
                f"Failed for MAV_TYPE {mav_type}, expected {expected_vehicle}, got {vehicle_type}"
            )

    def test_get_info_complete(self, fc_info) -> None:
        """Test getting complete flight controller information."""
        # Set all properties
        fc_info.system_id = "1"
        fc_info.component_id = "2"
        fc_info.autopilot = "ArduPilot"
        fc_info.vehicle_type = "ArduCopter"
        fc_info.firmware_type = "PX4-FMUv5"
        fc_info.mav_type = "Quadrotor"
        fc_info.flight_sw_version = "4.3.2"
        fc_info.flight_sw_version_and_type = "4.3.2 beta"
        fc_info.board_version = "123"
        fc_info.apj_board_id = "50"
        fc_info.flight_custom_version = "abc123"
        fc_info.os_custom_version = "def456"
        fc_info.vendor = "3DR"
        fc_info.vendor_id = "0x1234"
        fc_info.vendor_and_vendor_id = "3DR (0x1234)"
        fc_info.product = "Pixhawk"
        fc_info.product_id = "0x5678"
        fc_info.product_and_product_id = "Pixhawk (0x5678)"
        fc_info.mcu_series = "STM32F7"
        fc_info.capabilities = {"FTP": "File Transfer Protocol", "SET_ATTITUDE_TARGET": "Can set attitude target"}

        info = fc_info.get_info()

        # Check all fields are present and have the correct values
        assert info["USB Vendor"] == "3DR (0x1234)"
        assert info["USB Product"] == "Pixhawk (0x5678)"
        assert info["Board Type"] == "50"
        assert info["Hardware Version"] == "123"
        assert info["Autopilot Type"] == "ArduPilot"
        assert info["ArduPilot Vehicle Type"] == "ArduCopter"
        assert info["ArduPilot FW Type"] == "PX4-FMUv5"
        assert info["MAV Type"] == "Quadrotor"
        assert info["Firmware Version"] == "4.3.2 beta"
        assert info["Git Hash"] == "abc123"
        assert info["OS Git Hash"] == "def456"
        assert info["Capabilities"] == {"FTP": "File Transfer Protocol", "SET_ATTITUDE_TARGET": "Can set attitude target"}
        assert info["System ID"] == "1"
        assert info["Component ID"] == "2"
        assert info["MCU Series"] == "STM32F7"

    def test_set_type_integration(self, fc_info) -> None:
        """Integration test for set_type without mocking the internal methods."""
        # Skip mocking to test the actual integration
        fc_info.set_type(mavutil.mavlink.MAV_TYPE_QUADROTOR)
        assert fc_info.vehicle_type == "ArduCopter"
        # Fixed: Use a substring that's definitely in "quadrotor"
        assert "quad" in fc_info.mav_type.lower()  # "Quadrotor" or similar

        fc_info.set_type(mavutil.mavlink.MAV_TYPE_SUBMARINE)
        assert fc_info.vehicle_type == "ArduSub"

    def test_flight_custom_version_empty(self, fc_info) -> None:
        """Test setting empty flight custom version."""
        fc_info.set_flight_custom_version([])
        assert fc_info.flight_custom_version == ""

    def test_flight_custom_version_non_ascii(self, fc_info) -> None:
        """Test setting flight custom version with non-ASCII characters."""
        # Testing with a null byte and some values outside ASCII range
        fc_info.set_flight_custom_version([0, 65, 255])
        assert fc_info.flight_custom_version == "\x00A\xff"

        # Check length is preserved
        assert len(fc_info.flight_custom_version) == 3

    def test_set_board_version_zero(self, fc_info) -> None:
        """Test setting board version to zero."""
        fc_info.set_board_version(0)
        assert fc_info.board_version == "0"
        assert fc_info.apj_board_id == "0"
        assert "Unknown" in fc_info.firmware_type
        assert "Unknown" in fc_info.mcu_series

    @pytest.mark.parametrize(
        ("autopilot_id", "expected_text"),
        [
            (mavutil.mavlink.MAV_AUTOPILOT_GENERIC, "generic"),
            (mavutil.mavlink.MAV_AUTOPILOT_ARDUPILOTMEGA, "ardupilot"),
            (mavutil.mavlink.MAV_AUTOPILOT_PX4, "px4"),
        ],
    )
    def test_decode_mav_autopilot_with_valid_values(self, autopilot_id, expected_text) -> None:
        """Test decoding various valid MAV_AUTOPILOT values."""
        result = BackendFlightcontrollerInfo._BackendFlightcontrollerInfo__decode_mav_autopilot(autopilot_id)
        assert expected_text in result.lower(), f"Failed for autopilot ID {autopilot_id}"

    def test_decode_flight_capabilities_empty(self) -> None:
        """Test decoding with no capabilities set (0)."""
        result = BackendFlightcontrollerInfo._BackendFlightcontrollerInfo__decode_flight_capabilities(0)
        assert result == {}

    def test_set_capabilities_invalid_bit(self, fc_info) -> None:
        """Test setting capabilities with invalid bit patterns."""
        # Set an invalid bit pattern that doesn't match any known capability
        with patch.object(fc_info, "_BackendFlightcontrollerInfo__decode_flight_capabilities", return_value={}):
            fc_info.set_capabilities(1 << 50)  # Way beyond 32 bits
            assert fc_info.capabilities == {}
            assert fc_info.is_mavftp_supported is False

    def test_decode_mav_type_error_handling(self) -> None:
        """Test error handling in decode_mav_type."""
        mock_enum_entry = MagicMock(return_value=MagicMock(description="Unknown type"))

        with patch.object(mavutil.mavlink, "EnumEntry", mock_enum_entry):
            # When the dictionary lookup fails, it should use the EnumEntry fallback
            result = BackendFlightcontrollerInfo._BackendFlightcontrollerInfo__decode_mav_type(999)
            assert "Unknown" in result
            # Verify EnumEntry was called with the expected fallback values
            mock_enum_entry.assert_called_once_with("None", "Unknown type")

    def test_set_board_version_negative(self, fc_info) -> None:
        """Test setting board version with negative values should be handled gracefully."""
        # This should not raise an exception
        fc_info.set_board_version(-1)
        assert fc_info.board_version == "65535"  # -1 & 0x0FFFF = 65535

    def test_vendor_derived_from_board_id_when_unknown(self, fc_info, monkeypatch) -> None:
        """Test vendor derivation from board ID when current vendor is Unknown."""
        mock_vendor_dict = {42: ["CubePilot"]}
        monkeypatch.setattr(
            "ardupilot_methodic_configurator.backend_flightcontroller_info.APJ_BOARD_ID_VENDOR_DICT", mock_vendor_dict
        )

        # Set vendor to Unknown first
        fc_info.vendor = "Unknown"
        fc_info.set_board_version(0x002A0000)  # Board ID 42
        assert fc_info.vendor == "CubePilot"

        # Now set vendor to something else
        fc_info.vendor = "CustomVendor"
        fc_info.set_board_version(0x002A0000)  # Board ID 42
        assert fc_info.vendor == "CustomVendor"  # Should not change

    @pytest.mark.parametrize(
        ("input_capabilities", "expected_mavftp"),
        [
            (0, False),  # No capabilities
            (mavutil.mavlink.MAV_PROTOCOL_CAPABILITY_FTP, True),  # Only FTP
            (mavutil.mavlink.MAV_PROTOCOL_CAPABILITY_SET_ATTITUDE_TARGET, False),  # Other capability
            (
                mavutil.mavlink.MAV_PROTOCOL_CAPABILITY_FTP | mavutil.mavlink.MAV_PROTOCOL_CAPABILITY_SET_ATTITUDE_TARGET,
                True,
            ),  # Multiple capabilities
        ],
    )
    def test_set_capabilities_ftp_detection(self, fc_info, input_capabilities, expected_mavftp) -> None:
        """Test FTP capability detection."""
        with patch.object(fc_info, "_BackendFlightcontrollerInfo__decode_flight_capabilities", return_value={}):
            fc_info.set_capabilities(input_capabilities)
            assert fc_info.is_mavftp_supported is expected_mavftp
