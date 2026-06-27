#!/usr/bin/env python3

"""
Behavior-driven tests for ArduPilot parameter upgrade functionality.

This module contains comprehensive tests for firmware version parameter migrations,
including 4.6 GPS renames and 4.7+ parameter name/value transformations.

SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

from pathlib import Path

import pytest

from ardupilot_methodic_configurator.data_model_par_dict import Par, ParDict
from ardupilot_methodic_configurator.data_model_parameter_upgrade import (
    PARAM_UPGRADE_DICT_46,
    PARAM_UPGRADE_DICT_47,
    build_sr_to_mav_mapping,
    upgrade_file_parameters_46,
    upgrade_file_parameters_47,
    upgrade_parameters_for_firmware_version,
)

# pylint: disable=redefined-outer-name, too-many-lines


@pytest.fixture
def sample_parameters_45() -> dict[str, ParDict]:
    """
    Fixture providing parameter files from firmware 4.5.

    Includes GPS parameters with old naming convention that need upgrading to 4.6+
    """
    return {
        "00_default.param": ParDict(
            {
                "GPS_TYPE": Par(1.0, "GPS type"),
                "GPS_TYPE2": Par(1.0, "Secondary GPS type"),
                "GPS_COM_PORT": Par(3.0, "GPS serial port"),
                "GPS_COM_PORT2": Par(4.0, "Secondary GPS serial port"),
                "GPS_DELAY_MS": Par(0.0, "GPS delay"),
                "GPS_DELAY_MS2": Par(10.0, "Secondary GPS delay"),
                "GPS_GNSS_MODE": Par(3.0, "GPS GNSS mode"),
                "GPS_GNSS_MODE2": Par(3.0, "Secondary GPS GNSS mode"),
                "GPS_RATE_MS": Par(200.0, "GPS rate"),
                "GPS_RATE_MS2": Par(200.0, "Secondary GPS rate"),
                "GPS_CAN_NODEID1": Par(0.0, "GPS CAN node ID 1"),
                "GPS_CAN_NODEID2": Par(0.0, "GPS CAN node ID 2"),
                "OTHER_PARAM": Par(42.0, "Should remain unchanged"),
            }
        ),
    }


@pytest.fixture
def sample_parameters_46() -> dict[str, ParDict]:
    """
    Fixture providing parameter files from firmware 4.6.

    Includes upgraded GPS parameters with new naming convention.
    """
    return {
        "00_default.param": ParDict(
            {
                "GPS1_TYPE": Par(1.0, "GPS type"),
                "GPS2_TYPE": Par(1.0, "Secondary GPS type"),
                "GPS1_COM_PORT": Par(3.0, "GPS serial port"),
                "GPS2_COM_PORT": Par(4.0, "Secondary GPS serial port"),
                "GPS1_DELAY_MS": Par(0.0, "GPS delay"),
                "GPS2_DELAY_MS": Par(10.0, "Secondary GPS delay"),
                "PSC_VELXY_D": Par(10.0, "XY velocity damping"),
                "PSC_VELZ_D": Par(5.0, "Z velocity damping"),
                "OTHER_PARAM": Par(42.0, "Should remain unchanged"),
            }
        ),
    }


@pytest.fixture
def sample_parameters_46_with_scaling() -> dict[str, ParDict]:
    """
    Fixture providing parameter files from firmware 4.6 with parameters that need scaling for 4.7.

    Includes PSC and other parameters that have different units in 4.7.
    Uses default SERIAL*_PROTOCOL configuration with MAVLink on SERIAL0 and SERIAL1.
    """
    return {
        "00_default.param": ParDict(
            {
                "GPS1_TYPE": Par(1.0, "GPS type"),
                # PSC_ACCZ parameters that scale by 0.1 for P/I, 0.001 for IMAX
                "PSC_ACCZ_P": Par(2.0, "Altitude P gain in cm/s²"),
                "PSC_ACCZ_I": Par(1.5, "Altitude I gain"),
                "PSC_ACCZ_IMAX": Par(500.0, "Altitude I max"),
                "PSC_ACCZ_D": Par(0.5, "Altitude D gain"),
                # Other 4.7 renames with /100 scaling (cm → m)
                "LAND_SPEED": Par(100.0, "Land speed in cm/s"),
                "RTL_ALT": Par(1500.0, "RTL altitude in cm"),
                "WPNAV_SPEED": Par(500.0, "Waypoint speed in cm/s"),
                # Stream rates with SR prefix (default mapping: SR0 and SR1 are MAVLink ports)
                "SERIAL0_PROTOCOL": Par(2.0, "Serial 0 protocol: MAVLink2"),
                "SERIAL1_PROTOCOL": Par(1.0, "Serial 1 protocol: MAVLink1"),
                "SERIAL2_PROTOCOL": Par(0.0, "Serial 2 protocol: Disabled"),
                "SERIAL3_PROTOCOL": Par(0.0, "Serial 3 protocol: Disabled"),
                "SR0_RAW_SENS": Par(2.0, "Raw sensors rate"),
                "SR1_EXTRA1": Par(2.0, "Secondary extra1 data rate"),
                "SR4_EXTRA1": Par(2.0, "Tertiary extra1 port 4 exceeds MAV4"),
                "OTHER_PARAM": Par(42.0, "Should remain unchanged"),
            }
        ),
    }


@pytest.fixture
def sample_parameters_46_with_mavlink_on_serial2_and_4() -> dict[str, ParDict]:
    """
    Fixture providing parameter files with MAVLink on SERIAL2 and SERIAL4 (non-sequential).

    Tests dynamic mapping: SR2 → MAV1, SR4 → MAV2
    """
    return {
        "00_default.param": ParDict(
            {
                "SERIAL0_PROTOCOL": Par(0.0, "Serial 0 protocol: Disabled"),
                "SERIAL1_PROTOCOL": Par(3.0, "Serial 1 protocol: GPS"),
                "SERIAL2_PROTOCOL": Par(2.0, "Serial 2 protocol: MAVLink2"),
                "SERIAL3_PROTOCOL": Par(3.0, "Serial 3 protocol: GPS"),
                "SERIAL4_PROTOCOL": Par(1.0, "Serial 4 protocol: MAVLink1"),
                "SR2_EXT_STAT": Par(2.0, "Extended status rate on SERIAL2"),
                "SR4_RAW_SENS": Par(4.0, "Raw sensors rate on SERIAL4"),
                "SR3_EXTRA1": Par(2.0, "Extra 1 data (should not be remapped)"),
            }
        ),
    }


class TestParameterUpgrade46:
    """Test parameter upgrade for firmware 4.6 (GPS naming updates)."""

    def test_user_can_upgrade_gps_parameters_to_4_6_naming(self, sample_parameters_45) -> None:
        """
        User GPS parameters are upgraded from 4.5 to 4.6 naming convention.

        GIVEN: Parameter files with old GPS_TYPE, GPS_COM_PORT, etc. naming
        WHEN: upgrade_file_parameters_46 is called
        THEN: Parameters are renamed to GPS1_TYPE, GPS1_COM_PORT, etc.
        AND: Parameter values and comments remain unchanged
        """
        # Arrange: Create parameters with old naming
        params = sample_parameters_45.copy()

        # Act: Upgrade parameters to 4.6
        upgrade_file_parameters_46(params)

        # Assert: Parameters renamed correctly (new names present)
        assert "GPS1_TYPE" in params["00_default.param"]
        assert "GPS2_TYPE" in params["00_default.param"]
        assert "GPS1_COM_PORT" in params["00_default.param"]
        assert "GPS2_COM_PORT" in params["00_default.param"]
        assert "GPS1_DELAY_MS" in params["00_default.param"]
        assert "GPS2_DELAY_MS" in params["00_default.param"]

        # Assert: Old parameter names are removed
        assert "GPS_TYPE" not in params["00_default.param"]
        assert "GPS_TYPE2" not in params["00_default.param"]
        assert "GPS_COM_PORT" not in params["00_default.param"]
        assert "GPS_COM_PORT2" not in params["00_default.param"]
        assert "GPS_DELAY_MS" not in params["00_default.param"]
        assert "GPS_DELAY_MS2" not in params["00_default.param"]

    def test_gps_parameter_values_preserved_during_4_6_upgrade(self, sample_parameters_45) -> None:
        """
        GPS parameter values are preserved during 4.6 upgrade.

        GIVEN: Parameters with GPS values and comments
        WHEN: upgrade_file_parameters_46 is called
        THEN: Values remain identical, only names change
        """
        # Arrange
        params = sample_parameters_45.copy()
        original_value = params["00_default.param"]["GPS_TYPE"].value
        original_comment = params["00_default.param"]["GPS_TYPE"].comment

        # Act
        upgrade_file_parameters_46(params)

        # Assert
        assert params["00_default.param"]["GPS1_TYPE"].value == original_value
        assert params["00_default.param"]["GPS1_TYPE"].comment == original_comment

    def test_non_gps_parameters_unchanged_during_4_6_upgrade(self, sample_parameters_45) -> None:
        """
        Non-GPS parameters are unchanged during 4.6 upgrade.

        GIVEN: Parameters including GPS and non-GPS parameters
        WHEN: upgrade_file_parameters_46 is called
        THEN: Non-GPS parameters remain unchanged
        """
        # Arrange
        params = sample_parameters_45.copy()

        # Act
        upgrade_file_parameters_46(params)

        # Assert
        assert "OTHER_PARAM" in params["00_default.param"]
        assert params["00_default.param"]["OTHER_PARAM"].value == 42.0

    def test_all_gps_renames_from_dict_applied(self) -> None:
        """
        All GPS parameter renames from PARAM_UPGRADE_DICT_46 are applied.

        GIVEN: Parameters that need all possible 4.6 GPS renames
        WHEN: upgrade_file_parameters_46 is called
        THEN: All old GPS parameter names are replaced with new ones
        """
        # Arrange: Create parameters with all GPS rename keys
        all_gps_params = {}
        for old_name in PARAM_UPGRADE_DICT_46:
            all_gps_params[old_name] = Par(1.0, f"Test {old_name}")

        params = {"00_default.param": ParDict(all_gps_params)}

        # Act
        upgrade_file_parameters_46(params)

        # Assert: All old GPS names are gone and new names exist, with values preserved
        for old_name, new_name in PARAM_UPGRADE_DICT_46.items():
            assert old_name not in params["00_default.param"]
            assert new_name in params["00_default.param"]
            assert params["00_default.param"][new_name].value == pytest.approx(1.0)


class TestParameterUpgrade47:
    """Test parameter upgrade for firmware 4.7+ (comprehensive renames and scaling)."""

    def test_user_can_upgrade_parameters_to_4_7_naming(self, sample_parameters_46_with_scaling) -> None:
        """
        User parameters are upgraded from 4.6 to 4.7 naming convention with proper scaling.

        GIVEN: Parameter files with 4.6 naming and units (cm, cm/s, etc.)
        WHEN: upgrade_file_parameters_47 is called
        THEN: Parameters are renamed and values scaled to 4.7 units (m, m/s, etc.)
        """
        # Arrange
        params = sample_parameters_46_with_scaling.copy()

        # Act
        upgrade_file_parameters_47(params)

        # Assert: PSC_ACCZ → PSC_D_ACC renamed (old names gone, new names present)
        assert "PSC_D_ACC_P" in params["00_default.param"]
        assert "PSC_D_ACC_I" in params["00_default.param"]
        assert "PSC_D_ACC_D" in params["00_default.param"]
        assert "PSC_ACCZ_P" not in params["00_default.param"]
        assert "PSC_ACCZ_I" not in params["00_default.param"]
        assert "PSC_ACCZ_D" not in params["00_default.param"]

        # Assert: Land/RTL/WP parameters renamed with /100 scaling (old names gone, new names present)
        assert "LAND_SPD_MS" in params["00_default.param"]
        assert "RTL_ALT_M" in params["00_default.param"]
        assert "WP_SPD" in params["00_default.param"]
        assert "LAND_SPEED" not in params["00_default.param"]
        assert "RTL_ALT" not in params["00_default.param"]
        assert "WPNAV_SPEED" not in params["00_default.param"]

    def test_psc_accz_p_i_scaling_by_0_1(self, sample_parameters_46_with_scaling) -> None:
        """
        PSC_ACCZ P and I parameters are scaled by 0.1 during 4.7 upgrade.

        GIVEN: PSC_ACCZ_P=2.0, PSC_ACCZ_I=1.5 from firmware 4.6
        WHEN: upgrade_file_parameters_47 is called
        THEN: PSC_D_ACC_P becomes 0.2, PSC_D_ACC_I becomes 0.15
        """
        # Arrange
        params = sample_parameters_46_with_scaling.copy()

        # Act
        upgrade_file_parameters_47(params)

        # Assert
        assert params["00_default.param"]["PSC_D_ACC_P"].value == pytest.approx(0.2)
        assert params["00_default.param"]["PSC_D_ACC_I"].value == pytest.approx(0.15)

    def test_psc_accz_imax_scaling_by_0_001(self, sample_parameters_46_with_scaling) -> None:
        """
        PSC_ACCZ_IMAX parameter is scaled by 0.001 during 4.7 upgrade.

        GIVEN: PSC_ACCZ_IMAX=500.0 from firmware 4.6
        WHEN: upgrade_file_parameters_47 is called
        THEN: PSC_D_ACC_IMAX becomes 0.5, old name removed
        """
        # Arrange
        params = sample_parameters_46_with_scaling.copy()

        # Act
        upgrade_file_parameters_47(params)

        # Assert
        assert params["00_default.param"]["PSC_D_ACC_IMAX"].value == pytest.approx(0.5)
        assert "PSC_ACCZ_IMAX" not in params["00_default.param"]

    def test_psc_accz_d_not_scaled_during_4_7_upgrade(self, sample_parameters_46_with_scaling) -> None:
        """
        PSC_ACCZ_D parameter is renamed but NOT scaled (scale=1.0) during 4.7 upgrade.

        GIVEN: PSC_ACCZ_D=0.5 from firmware 4.6
        WHEN: upgrade_file_parameters_47 is called
        THEN: PSC_D_ACC_D retains value 0.5 (scale factor 1.0), old name removed
        """
        # Arrange
        params = sample_parameters_46_with_scaling.copy()

        # Act
        upgrade_file_parameters_47(params)

        # Assert
        assert params["00_default.param"]["PSC_D_ACC_D"].value == pytest.approx(0.5)
        assert "PSC_ACCZ_D" not in params["00_default.param"]

    def test_cm_to_m_scaling_by_0_01(self, sample_parameters_46_with_scaling) -> None:
        """
        Parameters with cm units are scaled by 0.01 to convert to m during 4.7 upgrade.

        GIVEN: LAND_SPEED=100cm/s, RTL_ALT=1500cm, WPNAV_SPEED=500cm/s
        WHEN: upgrade_file_parameters_47 is called
        THEN: Values scaled: 100*0.01=1.0, 1500*0.01=15.0, 500*0.01=5.0
        """
        # Arrange
        params = sample_parameters_46_with_scaling.copy()

        # Act
        upgrade_file_parameters_47(params)

        # Assert
        assert params["00_default.param"]["LAND_SPD_MS"].value == pytest.approx(1.0)
        assert params["00_default.param"]["RTL_ALT_M"].value == pytest.approx(15.0)
        assert params["00_default.param"]["WP_SPD"].value == pytest.approx(5.0)

    def test_sr0_sr1_mapped_to_mav1_mav2_when_serial0_serial1_use_mavlink(self, sample_parameters_46_with_scaling) -> None:
        """
        SR0 and SR1 are mapped to MAV1 and MAV2 when SERIAL0 and SERIAL1 use MAVLink.

        GIVEN: SR0_*, SR1_* parameters and SERIAL0_PROTOCOL=MAVLink2, SERIAL1_PROTOCOL=MAVLink
        WHEN: upgrade_file_parameters_47 is called
        THEN: SR0 → MAV1, SR1 → MAV2 (dynamic mapping based on protocol configuration)
        AND: SR suffix is preserved unchanged (e.g., RAW_SENS stays RAW_SENS)
        """
        # Arrange
        params = sample_parameters_46_with_scaling.copy()

        # Act
        upgrade_file_parameters_47(params)

        # Assert: Dynamic mapping applied correctly with suffixes and values preserved
        assert "MAV1_RAW_SENS" in params["00_default.param"]
        assert "MAV2_EXTRA1" in params["00_default.param"]
        assert params["00_default.param"]["MAV1_RAW_SENS"].value == pytest.approx(2.0)
        assert params["00_default.param"]["MAV2_EXTRA1"].value == pytest.approx(2.0)
        assert "SR0_RAW_SENS" not in params["00_default.param"]
        assert "SR1_EXTRA1" not in params["00_default.param"]

    def test_sr2_mapped_to_mav1_when_serial2_is_first_mavlink_port(
        self, sample_parameters_46_with_mavlink_on_serial2_and_4
    ) -> None:
        """
        SR2 is mapped to MAV1 when SERIAL2 is the first port with MAVLink protocol.

        GIVEN: SERIAL0=Disabled, SERIAL1=GPS, SERIAL2=MAVLink2, SERIAL3=GPS, SERIAL4=MAVLink1
        WHEN: upgrade_file_parameters_47 is called
        THEN: SR2 → MAV1 (first MAVLink port), SR4 → MAV2 (second MAVLink port)
        AND: SR suffix is preserved unchanged (e.g., RAW_SENS stays RAW_SENS)
        AND: SR3 parameters are dropped (SERIAL3 is not MAVLink)
        """
        # Arrange
        params = sample_parameters_46_with_mavlink_on_serial2_and_4.copy()

        # Act
        upgrade_file_parameters_47(params)

        # Assert: Dynamic mapping based on SERIAL*_PROTOCOL with suffixes and values preserved
        assert "MAV1_EXT_STAT" in params["00_default.param"]
        assert "MAV2_RAW_SENS" in params["00_default.param"]
        assert params["00_default.param"]["MAV1_EXT_STAT"].value == pytest.approx(2.0)
        assert params["00_default.param"]["MAV2_RAW_SENS"].value == pytest.approx(4.0)
        assert "SR2_EXT_STAT" not in params["00_default.param"]
        # SR3 is not a MAVLink port (SERIAL3_PROTOCOL=GPS), so SR3 params should be dropped
        assert "SR3_EXTRA1" not in params["00_default.param"]
        assert "SR4_RAW_SENS" not in params["00_default.param"]

    def test_sr_parameters_dropped_when_port_is_not_mavlink(self, sample_parameters_46_with_scaling) -> None:
        """
        SR parameters are dropped when their port is not configured as MAVLink.

        GIVEN: SR4_EXTRA1 but SERIAL4_PROTOCOL is absent (defaults to non-MAVLink)
              while SERIAL0 (MAVLink2) and SERIAL1 (MAVLink1) map to MAV1 and MAV2 respectively
        WHEN: upgrade_file_parameters_47 is called
        THEN: SR4_EXTRA1 is dropped (port 4 is not a MAVLink port in this fixture)
        AND: SR0/SR1 are remapped to MAV1/MAV2 (their ports are MAVLink)
        """
        # Arrange
        params = sample_parameters_46_with_scaling.copy()

        # Act
        upgrade_file_parameters_47(params)

        # Assert: SR4 dropped (SERIAL4_PROTOCOL not present → port 4 not MAVLink)
        assert "SR4_EXTRA1" not in params["00_default.param"]
        # Sanity: SR0/SR1 were remapped (their ports ARE MAVLink)
        assert "MAV1_RAW_SENS" in params["00_default.param"]
        assert "MAV2_EXTRA1" in params["00_default.param"]

    def test_non_upgraded_parameters_unchanged_during_4_7_upgrade(self, sample_parameters_46_with_scaling) -> None:
        """
        Parameters not in upgrade dictionaries remain unchanged during 4.7 upgrade.

        GIVEN: OTHER_PARAM=42.0 (not in any upgrade dictionary)
        WHEN: upgrade_file_parameters_47 is called
        THEN: OTHER_PARAM remains with value 42.0
        """
        # Arrange
        params = sample_parameters_46_with_scaling.copy()

        # Act
        upgrade_file_parameters_47(params)

        # Assert
        assert "OTHER_PARAM" in params["00_default.param"]
        assert params["00_default.param"]["OTHER_PARAM"].value == 42.0

    def test_all_47_renames_with_scaling_applied(self) -> None:
        """
        All parameter renames and scaling factors from PARAM_UPGRADE_DICT_47 are applied correctly.

        GIVEN: Parameters matching all keys in PARAM_UPGRADE_DICT_47
        WHEN: upgrade_file_parameters_47 is called
        THEN: Each parameter is renamed and scaled according to its mapping
        """
        # Arrange: Create parameters for each upgrade dictionary entry
        test_params = {}
        for old_name in PARAM_UPGRADE_DICT_47:
            test_params[old_name] = Par(100.0, f"Test {old_name}")

        params = {"00_default.param": ParDict(test_params)}

        # Act
        upgrade_file_parameters_47(params)

        # Assert: Verify each rename and scaling
        for old_name, (new_name, scale) in PARAM_UPGRADE_DICT_47.items():
            assert old_name not in params["00_default.param"]
            assert new_name in params["00_default.param"]
            expected_value = 100.0 * scale
            assert params["00_default.param"][new_name].value == pytest.approx(expected_value)


class TestVersionComparisonLogic:
    """Test version comparison and upgrade application logic."""

    def test_user_upgrading_45_to_47_gets_both_46_and_47_upgrades(self) -> None:
        """
        User jumping from 4.5 to 4.7 receives both 4.6 and 4.7 parameter upgrades.

        GIVEN: Parameter files from 4.5 including GPS params and a 4.7-upgradeable PSC param
        WHEN: upgrade_parameters_for_firmware_version is called
        THEN: 4.6 GPS renames applied (GPS_TYPE → GPS1_TYPE)
        AND: 4.7 renames applied (PSC_VELXY_D → PSC_NE_VEL_D, scale=1.0)
        """
        # Arrange: Include both old GPS params (need 4.6 upgrade) and a 4.7-upgradeable PSC param
        params = {
            "00_default.param": ParDict(
                {
                    "GPS_TYPE": Par(1.0, "GPS type"),
                    "GPS_CAN_NODEID1": Par(0.0, "GPS CAN node ID 1"),
                    "PSC_VELXY_D": Par(10.0, "XY velocity damping"),  # 4.7: → PSC_NE_VEL_D, scale=1.0
                    "LAND_SPEED": Par(300.0, "Land speed cm/s"),  # 4.7: → LAND_SPD_MS, scale=0.01
                    "SERIAL0_PROTOCOL": Par(2.0, "MAVLink2"),
                }
            )
        }

        # Act
        upgrade_parameters_for_firmware_version("4.5", "4.7", params)

        # Assert: 4.6 upgrade applied (GPS renames)
        assert "GPS1_TYPE" in params["00_default.param"]
        assert "GPS_TYPE" not in params["00_default.param"]
        assert "GPS1_CAN_NODEID" in params["00_default.param"]
        assert "GPS_CAN_NODEID1" not in params["00_default.param"]

        # Assert: 4.7 upgrade applied (PSC rename + LAND scaling)
        assert "PSC_NE_VEL_D" in params["00_default.param"]
        assert params["00_default.param"]["PSC_NE_VEL_D"].value == pytest.approx(10.0)
        assert "PSC_VELXY_D" not in params["00_default.param"]
        assert "LAND_SPD_MS" in params["00_default.param"]
        assert params["00_default.param"]["LAND_SPD_MS"].value == pytest.approx(3.0)
        assert "LAND_SPEED" not in params["00_default.param"]

    def test_user_upgrading_46_to_47_gets_only_47_upgrade(self, sample_parameters_46) -> None:
        """
        User upgrading from 4.6 to 4.7 receives only 4.7 parameter upgrades.

        GIVEN: Parameter files from 4.6 with GPS1_TYPE and PSC_VELXY_D, FC running 4.7
        WHEN: upgrade_parameters_for_firmware_version is called
        THEN: Only 4.7 upgrades applied: PSC_VELXY_D → PSC_NE_VEL_D
        AND: 4.6 GPS names unchanged (already upgraded): GPS1_TYPE stays as-is
        """
        # Arrange
        params = sample_parameters_46.copy()

        # Act
        upgrade_parameters_for_firmware_version("4.6", "4.7", params)

        # Assert: 4.6 GPS names unchanged (already upgraded)
        assert "GPS1_TYPE" in params["00_default.param"]

        # Assert: 4.7 rename actually applied to PSC params present in the fixture
        assert "PSC_NE_VEL_D" in params["00_default.param"]
        assert "PSC_D_VEL_D" in params["00_default.param"]
        assert "PSC_VELXY_D" not in params["00_default.param"]
        assert "PSC_VELZ_D" not in params["00_default.param"]

    def test_same_version_no_upgrade_applied(self, sample_parameters_46) -> None:
        """
        No parameter upgrades are applied when FC and parameter file versions are identical.

        GIVEN: Parameter files from 4.6, FC running 4.6
        WHEN: upgrade_parameters_for_firmware_version is called
        THEN: No parameters are modified
        """
        # Arrange
        params = sample_parameters_46.copy()
        original_params = dict(params["00_default.param"].items())

        # Act
        upgrade_parameters_for_firmware_version("4.6", "4.6", params)

        # Assert
        assert dict(params["00_default.param"].items()) == original_params

    def test_older_fc_than_files_no_upgrade_applied(self, sample_parameters_46) -> None:
        """
        No upgrades are applied when FC is older than parameter files.

        GIVEN: Parameter files from 4.6, FC running 4.5 (older)
        WHEN: upgrade_parameters_for_firmware_version is called
        THEN: Parameters remain unchanged (cannot downgrade safely)
        """
        # Arrange
        params = sample_parameters_46.copy()
        original_params = dict(params["00_default.param"].items())

        # Act
        upgrade_parameters_for_firmware_version("4.6", "4.5", params)

        # Assert
        assert dict(params["00_default.param"].items()) == original_params

    def test_parameter_comments_preserved_through_all_upgrades(self) -> None:
        """
        Parameter comments are preserved through all upgrade operations.

        GIVEN: Parameters with descriptive comments
        WHEN: upgrade_parameters_for_firmware_version is called
        THEN: Comments remain unchanged
        """
        # Arrange
        comment = "Important GPS configuration"
        params = {
            "00_default.param": ParDict(
                {
                    "GPS_TYPE": Par(1.0, comment),
                }
            )
        }

        # Act
        upgrade_parameters_for_firmware_version("4.5", "4.7", params)

        # Assert: comment and value both preserved through both upgrade steps
        assert params["00_default.param"]["GPS1_TYPE"].comment == comment
        assert params["00_default.param"]["GPS1_TYPE"].value == pytest.approx(1.0)

    def test_four_dot_six_one_upgrades_to_four_dot_seven(self) -> None:
        """
        Parameter files from 4.6.1 are correctly upgraded to 4.7.

        GIVEN: Parameter files from firmware 4.6.1 with GPS1_TYPE and PSC_VELXY_D, FC running 4.7.0
        WHEN: upgrade_parameters_for_firmware_version is called
        THEN: Only 4.7 upgrades applied (4.6 already done)
        AND: GPS1_TYPE preserved unchanged, PSC_VELXY_D renamed to PSC_NE_VEL_D
        """
        # Arrange
        params = {
            "00_default.param": ParDict(
                {
                    "GPS1_TYPE": Par(1.0, "GPS type"),
                    "PSC_VELXY_D": Par(10.0, "XY velocity damping"),
                }
            )
        }

        # Act
        upgrade_parameters_for_firmware_version("4.6.1", "4.7.0", params)

        # Assert: 4.6 GPS naming preserved (no GPS_TYPE was in the file, GPS1_TYPE stays)
        assert "GPS1_TYPE" in params["00_default.param"]
        assert params["00_default.param"]["GPS1_TYPE"].value == pytest.approx(1.0)

        # Assert: 4.7 rename applied (PSC_VELXY_D → PSC_NE_VEL_D, scale=1.0)
        assert "PSC_NE_VEL_D" in params["00_default.param"]
        assert params["00_default.param"]["PSC_NE_VEL_D"].value == pytest.approx(10.0)
        assert "PSC_VELXY_D" not in params["00_default.param"]

    def test_multiple_parameter_files_upgraded_together(self) -> None:
        """
        Multiple parameter files are upgraded together consistently.

        GIVEN: Multiple parameter files with old naming conventions
        WHEN: upgrade_parameters_for_firmware_version is called
        THEN: All files are upgraded using the same upgrade rules
        """
        # Arrange
        params = {
            "00_default.param": ParDict(
                {
                    "GPS_TYPE": Par(1.0, "GPS type"),
                }
            ),
            "02_radio.param": ParDict(
                {
                    "GPS_COM_PORT": Par(3.0, "GPS serial port"),
                }
            ),
        }

        # Act
        upgrade_parameters_for_firmware_version("4.5", "4.6", params)

        # Assert: Both files upgraded
        assert "GPS1_TYPE" in params["00_default.param"]
        assert "GPS1_COM_PORT" in params["02_radio.param"]
        assert "GPS_TYPE" not in params["00_default.param"]
        assert "GPS_COM_PORT" not in params["02_radio.param"]


class TestParameterUpgradeIntegration:  # pylint: disable=too-few-public-methods
    """Integration tests for complete parameter upgrade workflows."""

    @staticmethod
    def _load_template_parameters(template_dir: Path) -> dict[str, ParDict]:
        """Load all .param files from a template directory."""
        params = {}
        if template_dir.exists():
            for param_file in sorted(template_dir.glob("*.param")):
                params[param_file.name] = ParDict.load_param_file_into_dict(str(param_file))
        return params

    @staticmethod
    def _compare_file_parameters(upgraded_dict, expected_dict, filename: str) -> list[str]:
        """Compare two parameter dictionaries and return list of differences."""
        differences = []
        expected_names = set(expected_dict.keys())
        upgraded_names = set(upgraded_dict.keys())

        missing_in_upgraded = expected_names - upgraded_names
        extra_in_upgraded = upgraded_names - expected_names

        if missing_in_upgraded:
            msg = f"{filename}: Parameters in 4.7.x but not in upgraded 4.6.x: "
            msg += str(sorted(missing_in_upgraded)[:5])
            if len(missing_in_upgraded) > 5:
                msg += "..."
            differences.append(msg)

        if extra_in_upgraded:
            msg = f"{filename}: Parameters in upgraded 4.6.x but not in 4.7.x: "
            msg += str(sorted(extra_in_upgraded)[:5])
            if len(extra_in_upgraded) > 5:
                msg += "..."
            differences.append(msg)

        # Compare common parameters' values
        common_params = expected_names & upgraded_names
        value_mismatches = []
        for param_name in sorted(common_params):
            expected_value = expected_dict[param_name].value
            upgraded_value = upgraded_dict[param_name].value

            if isinstance(expected_value, float) and isinstance(upgraded_value, float):
                if abs(expected_value - upgraded_value) > 0.001:
                    msg = f"{param_name}: expected {expected_value}, got {upgraded_value}"
                    value_mismatches.append(msg)
            elif expected_value != upgraded_value:
                msg = f"{param_name}: expected {expected_value}, got {upgraded_value}"
                value_mismatches.append(msg)

        if value_mismatches:
            if len(value_mismatches) <= 10:
                msg = f"{filename}: Value mismatches:\n  " + "\n  ".join(value_mismatches)
                differences.append(msg)
            else:
                msg = f"{filename}: Value mismatches ({len(value_mismatches)} total):\n  "
                msg += "\n  ".join(value_mismatches[:10])
                msg += f"\n  ... and {len(value_mismatches) - 10} more"
                differences.append(msg)

        return differences

    @pytest.mark.integration
    def test_upgrading_empty_4_6_x_template_matches_empty_4_7_x_template(self, capsys) -> None:  # pylint: disable=too-many-locals
        """
        Empty 4.6.x template upgraded to 4.7 matches the empty 4.7.x template.

        GIVEN: All .param files from ardupilot_methodic_configurator/vehicle_templates/ArduCopter/empty_4.6.x
        WHEN: Parameters are upgraded from 4.6.0 to 4.7.0 using upgrade_parameters_for_firmware_version
        THEN: Upgraded parameters closely match those in empty_4.7.x template
        AND: Any differences are documented and minimal (expected: SERIAL4_PROTOCOL-like external additions)

        This test validates the parameter upgrade logic against real template data.
        This test is quite fast although it is an integration test.
        """
        # Arrange: Load templates and upgrade
        template_46_dir = Path("ardupilot_methodic_configurator/vehicle_templates/ArduCopter/empty_4.6.x")
        template_47_dir = Path("ardupilot_methodic_configurator/vehicle_templates/ArduCopter/empty_4.7.x")

        upgraded_params_46 = self._load_template_parameters(template_46_dir)
        expected_params_47 = self._load_template_parameters(template_47_dir)

        if not upgraded_params_46 or not expected_params_47:
            pytest.skip("Template directories not found or no .param files in template directories")

        # Act: Upgrade 4.6.x parameters to 4.7.0
        upgrade_parameters_for_firmware_version("4.6.0", "4.7.0", upgraded_params_46)

        # Assert: Compare upgraded parameters with expected 4.7.x parameters
        differences = []
        for filename, expected_dict in expected_params_47.items():
            if filename not in upgraded_params_46:
                differences.append(f"Missing file in upgraded: {filename}")
                continue

            upgraded_dict = upgraded_params_46[filename]
            differences.extend(self._compare_file_parameters(upgraded_dict, expected_dict, filename))

        # Verify that template files are loaded (at minimum they should have parameters)
        total_upgraded_params = sum(len(params) for params in upgraded_params_46.values())
        total_expected_params = sum(len(params) for params in expected_params_47.values())

        assert total_upgraded_params > 0, "No parameters found in upgraded 4.6.x template"
        assert total_expected_params > 0, "No parameters found in 4.7.x template"

        # Assert that upgrade results in reasonable parameter counts
        param_count_ratio = total_upgraded_params / total_expected_params
        assert param_count_ratio >= 0.9368, (
            f"Parameter count too low: upgraded={total_upgraded_params}, "
            f"expected={total_expected_params}, ratio={param_count_ratio:.2%}"
        )

        # Assert no regressions in the number of structural differences
        # (The 4.7.x template intentionally has different default values for some params,
        # so zero differences is not the goal — but the count must not grow unboundedly.)
        assert len(differences) <= 40, (
            f"Too many differences ({len(differences)}) between upgraded 4.6.x and 4.7.x templates:\n"
            + "\n".join(f"  - {d}" for d in differences)
        )

        # Capture and output summary
        summary = "\n".join(
            [
                "\n=== Integration Test Summary ===",
                f"Upgraded parameters: {total_upgraded_params}",
                f"Expected parameters: {total_expected_params}",
                f"Coverage ratio: {param_count_ratio:.1%}",
                "Conclusion: Upgrade successful for firmware version transition.",
            ]
        )

        if differences:
            capsys.readouterr()  # Clear captured output first
            summary_details = summary + "\n\nDetailed differences:\n"
            for diff in differences:
                summary_details += f"  - {diff}\n"
            print(summary_details)  # noqa: T201
        else:
            capsys.readouterr()  # Clear captured output first
            print(summary)  # noqa: T201


class TestFloatingPointPrecision:
    """Test floating point rounding and precision handling during upgrades."""

    def test_float_rounding_after_scaling_by_0_01(self) -> None:
        """
        Scaled floating point values maintain correct numeric results after 0.01 scaling.

        GIVEN: Parameters scaled by 0.01 with various input values
        WHEN: upgrade_file_parameters_47 is called
        THEN: Scaled results are numerically correct (verified via pytest.approx)
        """
        # Test specific values known to cause float precision issues
        params = {
            "00_default.param": ParDict(
                {
                    "LAND_SPEED": Par(1.0, "1cm/s"),  # 1.0 * 0.01 = 0.01
                    "RTL_ALT": Par(100.0, "100cm"),  # 100.0 * 0.01 = 1.0
                    "WPNAV_SPEED": Par(125.5, "125.5cm/s"),  # 125.5 * 0.01 = 1.255
                    "SERIAL0_PROTOCOL": Par(2.0, "MAVLink2"),
                    "SERIAL1_PROTOCOL": Par(1.0, "MAVLink1"),
                }
            ),
        }

        upgrade_file_parameters_47(params)

        # Assert precise values without floating point artifacts after .6f file serialization
        assert params["00_default.param"]["LAND_SPD_MS"].value == pytest.approx(0.01)
        assert params["00_default.param"]["RTL_ALT_M"].value == pytest.approx(1.0)
        assert params["00_default.param"]["WP_SPD"].value == pytest.approx(1.255)
        assert "LAND_SPEED" not in params["00_default.param"]
        assert "RTL_ALT" not in params["00_default.param"]
        assert "WPNAV_SPEED" not in params["00_default.param"]

    def test_very_small_scaled_values_preserve_precision(self) -> None:
        """
        Very small values (< 0.01) maintain precision after scaling.

        GIVEN: Parameters with very small values that scale even smaller
        WHEN: upgrade_file_parameters_47 is called
        THEN: Precision is preserved without truncation
        """
        params = {
            "00_default.param": ParDict(
                {
                    "PSC_ACCZ_P": Par(0.5, "0.5"),  # 0.5 * 0.1 = 0.05
                    "PSC_ACCZ_I": Par(0.1, "0.1"),  # 0.1 * 0.1 = 0.01
                    "SERIAL0_PROTOCOL": Par(2.0, "MAVLink2"),
                }
            ),
        }

        upgrade_file_parameters_47(params)

        assert params["00_default.param"]["PSC_D_ACC_P"].value == pytest.approx(0.05)
        assert params["00_default.param"]["PSC_D_ACC_I"].value == pytest.approx(0.01)
        assert "PSC_ACCZ_P" not in params["00_default.param"]
        assert "PSC_ACCZ_I" not in params["00_default.param"]

    def test_large_values_scaled_maintain_precision(self) -> None:
        """
        Large values scaled by 0.001 maintain precision.

        GIVEN: PSC_ACCZ_IMAX=50000.0 (scaled by 0.001)
        WHEN: upgrade_file_parameters_47 is called
        THEN: Result is 50.0 with correct precision
        """
        params = {
            "00_default.param": ParDict(
                {
                    "PSC_ACCZ_IMAX": Par(50000.0, "Large IMAX"),
                    "SERIAL0_PROTOCOL": Par(2.0, "MAVLink2"),
                }
            ),
        }

        upgrade_file_parameters_47(params)

        assert params["00_default.param"]["PSC_D_ACC_IMAX"].value == pytest.approx(50.0)
        assert "PSC_ACCZ_IMAX" not in params["00_default.param"]


class TestEdgeCasesForSerialPortMapping:
    """Test edge cases for SR to MAV parameter mapping with various port configurations."""

    def test_mavlink_on_single_high_port_number(self) -> None:
        """
        MAVLink on port 15 (high port number) maps to MAV1.

        GIVEN: SERIAL15_PROTOCOL=MAVLink2 (only MAVLink port)
        WHEN: build_sr_to_mav_mapping is called
        THEN: SR15 maps to MAV1 (first MAVLink port)
        """
        params = {
            "00_default.param": ParDict(
                {
                    "SERIAL0_PROTOCOL": Par(0.0, "Disabled"),
                    "SERIAL1_PROTOCOL": Par(3.0, "GPS"),
                    "SERIAL15_PROTOCOL": Par(2.0, "MAVLink2"),
                }
            ),
        }

        sr_to_mav, mavlink_ports = build_sr_to_mav_mapping(params)

        assert sr_to_mav == {"SR15_": "MAV1_"}
        assert mavlink_ports == {15}

    def test_mavlink_on_multiple_non_sequential_ports(self) -> None:
        """
        MAVLink on multiple non-sequential ports (1, 5, 10) maps correctly.

        GIVEN: SERIAL1, SERIAL5, SERIAL10 with MAVLink protocols
        WHEN: build_sr_to_mav_mapping is called
        THEN: First port → MAV1, second → MAV2, third → MAV3
        """
        params = {
            "00_default.param": ParDict(
                {
                    "SERIAL0_PROTOCOL": Par(3.0, "GPS"),
                    "SERIAL1_PROTOCOL": Par(2.0, "MAVLink2"),
                    "SERIAL5_PROTOCOL": Par(1.0, "MAVLink1"),
                    "SERIAL10_PROTOCOL": Par(2.0, "MAVLink2"),
                }
            ),
        }

        sr_to_mav, mavlink_ports = build_sr_to_mav_mapping(params)

        assert sr_to_mav == {"SR1_": "MAV1_", "SR5_": "MAV2_", "SR10_": "MAV3_"}
        assert mavlink_ports == {1, 5, 10}

    def test_all_ports_non_mavlink_no_sr_mapping(self) -> None:
        """
        When no ports use MAVLink, SR parameters have no mapping.

        GIVEN: All SERIAL*_PROTOCOL are non-MAVLink (GPS, disabled, etc.)
        WHEN: build_sr_to_mav_mapping is called
        THEN: Empty SR-to-MAV mapping dict returned, mavlink_ports set is empty
        """
        params = {
            "00_default.param": ParDict(
                {
                    "SERIAL0_PROTOCOL": Par(3.0, "GPS"),
                    "SERIAL1_PROTOCOL": Par(0.0, "Disabled"),
                    "SERIAL2_PROTOCOL": Par(3.0, "GPS"),
                }
            ),
        }

        sr_to_mav, mavlink_ports = build_sr_to_mav_mapping(params)

        assert sr_to_mav == {}
        assert mavlink_ports == set()

    def test_sr_parameters_dropped_when_no_mavlink_ports(self) -> None:
        """
        All SR parameters are dropped when no ports use MAVLink.

        GIVEN: SR0_*, SR1_*, SR2_* but no SERIAL*_PROTOCOL uses MAVLink
        WHEN: upgrade_file_parameters_47 is called
        THEN: All SR parameters removed
        """
        params = {
            "00_default.param": ParDict(
                {
                    "SERIAL0_PROTOCOL": Par(3.0, "GPS"),
                    "SERIAL1_PROTOCOL": Par(0.0, "Disabled"),
                    "SR0_RAW_SENS": Par(2.0, "Raw sensors"),
                    "SR1_EXTRA1": Par(2.0, "Extra 1"),
                    "SR2_EXTRA3": Par(2.0, "Extra 3"),
                }
            ),
        }

        upgrade_file_parameters_47(params)

        assert "SR0_RAW_SENS" not in params["00_default.param"]
        assert "SR1_EXTRA1" not in params["00_default.param"]
        assert "SR2_EXTRA3" not in params["00_default.param"]


class TestCollisionHandling:
    """Test behavior when both old and new parameter names coexist in the same file."""

    def test_46_collision_keeps_already_upgraded_entry_and_warns(self, caplog) -> None:
        """
        When both old and new GPS names coexist, the already-upgraded entry is kept.

        GIVEN: A file containing both GPS_TYPE (old) and GPS1_TYPE (new, already upgraded)
        WHEN: upgrade_file_parameters_46 is called
        THEN: GPS1_TYPE value from the already-upgraded entry is preserved
        AND: A collision warning is logged
        AND: Only one GPS1_TYPE entry exists in the result
        """
        params = {
            "00_default.param": ParDict(
                {
                    "GPS1_TYPE": Par(5.0, "Already upgraded value"),  # already-upgraded entry
                    "GPS_TYPE": Par(1.0, "Old entry"),  # old name that would also map to GPS1_TYPE
                }
            ),
        }

        upgrade_file_parameters_46(params)

        # Already-upgraded entry wins
        assert "GPS1_TYPE" in params["00_default.param"]
        assert params["00_default.param"]["GPS1_TYPE"].value == pytest.approx(5.0)
        assert params["00_default.param"]["GPS1_TYPE"].comment == "Already upgraded value"
        assert "GPS_TYPE" not in params["00_default.param"]
        assert "collision" in caplog.text.lower()

    def test_47_collision_keeps_already_upgraded_entry_and_warns(self, caplog) -> None:
        """
        When both old and new names coexist, the already-upgraded entry is kept.

        GIVEN: A file containing both PSC_ACCZ_P (old) and PSC_D_ACC_P (new, already upgraded)
        WHEN: upgrade_file_parameters_47 is called
        THEN: PSC_D_ACC_P value from the already-upgraded entry is preserved (not rescaled again)
        AND: A collision warning is logged
        """
        params = {
            "00_default.param": ParDict(
                {
                    "PSC_D_ACC_P": Par(0.2, "Already upgraded and scaled value"),  # already-upgraded
                    "PSC_ACCZ_P": Par(10.0, "Old entry — would scale to 1.0 if applied"),  # old name
                    "SERIAL0_PROTOCOL": Par(2.0, "MAVLink2"),
                }
            ),
        }

        upgrade_file_parameters_47(params)

        # Already-upgraded entry wins; old value (10.0 * 0.1 = 1.0) is NOT applied
        assert "PSC_D_ACC_P" in params["00_default.param"]
        assert params["00_default.param"]["PSC_D_ACC_P"].value == pytest.approx(0.2)
        assert params["00_default.param"]["PSC_D_ACC_P"].comment == "Already upgraded and scaled value"
        assert "PSC_ACCZ_P" not in params["00_default.param"]
        assert "collision" in caplog.text.lower()

    def test_46_collision_old_first_keeps_already_upgraded_entry_and_warns(self, caplog) -> None:
        """
        When old name appears before new name, the already-upgraded entry is still kept.

        GIVEN: A file containing both GPS_TYPE (old, inserted first) and GPS1_TYPE (new, inserted second)
        WHEN: upgrade_file_parameters_46 is called
        THEN: GPS1_TYPE value from the already-upgraded entry is preserved
        AND: A collision warning is logged
        AND: Only one GPS1_TYPE entry exists in the result
        """
        params = {
            "00_default.param": ParDict(
                {
                    "GPS_TYPE": Par(1.0, "Old entry"),  # old name inserted first
                    "GPS1_TYPE": Par(5.0, "Already upgraded value"),  # already-upgraded entry inserted second
                }
            ),
        }

        upgrade_file_parameters_46(params)

        # Already-upgraded entry wins regardless of insertion order
        assert "GPS1_TYPE" in params["00_default.param"]
        assert params["00_default.param"]["GPS1_TYPE"].value == pytest.approx(5.0)
        assert params["00_default.param"]["GPS1_TYPE"].comment == "Already upgraded value"
        assert "GPS_TYPE" not in params["00_default.param"]
        assert "collision" in caplog.text.lower()

    def test_47_collision_old_first_keeps_already_upgraded_entry_and_warns(self, caplog) -> None:
        """
        When old name appears before new name, the already-upgraded entry is still kept.

        GIVEN: A file containing both PSC_ACCZ_P (old, inserted first) and PSC_D_ACC_P (new, inserted second)
        WHEN: upgrade_file_parameters_47 is called
        THEN: PSC_D_ACC_P value from the already-upgraded entry is preserved (not rescaled again)
        AND: A collision warning is logged
        """
        params = {
            "00_default.param": ParDict(
                {
                    "PSC_ACCZ_P": Par(10.0, "Old entry — would scale to 1.0 if applied"),  # old name inserted first
                    "PSC_D_ACC_P": Par(0.2, "Already upgraded and scaled value"),  # already-upgraded inserted second
                    "SERIAL0_PROTOCOL": Par(2.0, "MAVLink2"),
                }
            ),
        }

        upgrade_file_parameters_47(params)

        # Already-upgraded entry wins regardless of insertion order; old value (10.0 * 0.1 = 1.0) is NOT applied
        assert "PSC_D_ACC_P" in params["00_default.param"]
        assert params["00_default.param"]["PSC_D_ACC_P"].value == pytest.approx(0.2)
        assert params["00_default.param"]["PSC_D_ACC_P"].comment == "Already upgraded and scaled value"
        assert "PSC_ACCZ_P" not in params["00_default.param"]
        assert "collision" in caplog.text.lower()

    def test_47_sr_collision_keeps_already_upgraded_mav_entry_and_warns(self, caplog) -> None:
        """
        When both an SR param and an already-upgraded MAV param coexist, the MAV entry is kept.

        GIVEN: A file containing both SR0_RAW_SENS (old SR param) and MAV1_RAW_SENS (already upgraded)
        WHEN: upgrade_file_parameters_47 is called
        THEN: MAV1_RAW_SENS value from the already-upgraded entry is preserved
        AND: A collision warning is logged
        AND: SR0_RAW_SENS is not in the result
        """
        params = {
            "00_default.param": ParDict(
                {
                    "SERIAL0_PROTOCOL": Par(2.0, "MAVLink2"),
                    "SR0_RAW_SENS": Par(4.0, "Old SR param"),
                    "MAV1_RAW_SENS": Par(10.0, "Already upgraded MAV param"),
                }
            ),
        }

        upgrade_file_parameters_47(params)

        # Already-upgraded MAV entry wins; SR value is NOT applied
        assert "MAV1_RAW_SENS" in params["00_default.param"]
        assert params["00_default.param"]["MAV1_RAW_SENS"].value == pytest.approx(10.0)
        assert params["00_default.param"]["MAV1_RAW_SENS"].comment == "Already upgraded MAV param"
        assert "SR0_RAW_SENS" not in params["00_default.param"]
        assert "collision" in caplog.text.lower()


class TestEmptyAndPartialParameterSets:
    """Test upgrades with empty or partial parameter sets."""

    def test_upgrade_empty_parameter_dict(self) -> None:
        """
        Upgrading empty parameter dict produces empty dict.

        GIVEN: Empty parameter dictionary
        WHEN: upgrade_file_parameters_46 and upgrade_file_parameters_47 called
        THEN: Result is still empty
        """
        params = {"00_default.param": ParDict({})}

        upgrade_file_parameters_46(params)
        assert params["00_default.param"] == ParDict({})

        params = {"00_default.param": ParDict({})}
        upgrade_file_parameters_47(params)
        assert params["00_default.param"] == ParDict({})

    def test_upgrade_with_only_non_upgradeable_parameters(self) -> None:
        """
        Parameters not in upgrade dicts remain unchanged.

        GIVEN: Only custom/non-standard parameters
        WHEN: upgrade_file_parameters_46 and 47 called
        THEN: All parameters preserved unchanged
        """
        params = {
            "00_default.param": ParDict(
                {
                    "CUSTOM_PARAM_1": Par(42.0, "Custom"),
                    "CUSTOM_PARAM_2": Par(99.5, "Another custom"),
                }
            ),
        }

        original = dict(params["00_default.param"])
        upgrade_file_parameters_46(params)
        upgrade_file_parameters_47(params)

        assert "CUSTOM_PARAM_1" in params["00_default.param"]
        assert "CUSTOM_PARAM_2" in params["00_default.param"]
        assert len(params["00_default.param"]) == 2
        assert params["00_default.param"]["CUSTOM_PARAM_1"].value == original["CUSTOM_PARAM_1"].value
        assert params["00_default.param"]["CUSTOM_PARAM_2"].value == original["CUSTOM_PARAM_2"].value

    def test_upgrade_partial_46_parameters_only_upgrades_present_ones(self) -> None:
        """
        Only present GPS parameters are upgraded, missing ones don't appear.

        GIVEN: Partial set of GPS parameters (only GPS_TYPE and GPS_COM_PORT)
        WHEN: upgrade_file_parameters_46 is called
        THEN: Only present parameters are upgraded, missing ones not created
        """
        params = {
            "00_default.param": ParDict(
                {
                    "GPS_TYPE": Par(1.0, "GPS type"),
                    "GPS_COM_PORT": Par(3.0, "GPS port"),
                    "OTHER": Par(5.0, "Other param"),
                }
            ),
        }

        upgrade_file_parameters_46(params)

        assert "GPS1_TYPE" in params["00_default.param"]
        assert "GPS1_COM_PORT" in params["00_default.param"]
        assert "GPS2_TYPE" not in params["00_default.param"]  # Not created
        assert "GPS2_COM_PORT" not in params["00_default.param"]  # Not created
        assert "OTHER" in params["00_default.param"]


class TestSerialProtocolPreservation:  # pylint: disable=too-few-public-methods
    """Test that SERIAL*_PROTOCOL parameters are preserved unchanged."""

    def test_serial_protocol_parameters_never_modified(self) -> None:
        """
        SERIAL*_PROTOCOL parameters are preserved exactly during upgrades.

        GIVEN: Various SERIAL*_PROTOCOL values (0, 1, 2, 3, 10)
        WHEN: upgrade_file_parameters_46 and 47 called
        THEN: Values unchanged, params still exist
        """
        params = {
            "00_default.param": ParDict(
                {
                    "SERIAL0_PROTOCOL": Par(2.0, "MAVLink2"),
                    "SERIAL1_PROTOCOL": Par(1.0, "MAVLink1"),
                    "SERIAL2_PROTOCOL": Par(3.0, "GPS"),
                    "SERIAL3_PROTOCOL": Par(0.0, "Disabled"),
                    "SERIAL10_PROTOCOL": Par(2.0, "High port"),
                }
            ),
        }

        original_serials = {k: v.value for k, v in params["00_default.param"].items() if k.startswith("SERIAL")}

        upgrade_file_parameters_46(params)
        upgrade_file_parameters_47(params)

        # Check all SERIAL*_PROTOCOL params preserved
        for key, value in original_serials.items():
            assert key in params["00_default.param"]
            assert params["00_default.param"][key].value == value


class TestCommentsPreservation:
    """Test that parameter comments are preserved through upgrades."""

    def test_comments_preserved_during_46_upgrade(self) -> None:
        """
        Parameter comments are preserved during 4.6 GPS renames.

        GIVEN: GPS parameters with descriptive comments
        WHEN: upgrade_file_parameters_46 is called
        THEN: Comments remain unchanged
        """
        original_comment = "My custom GPS type description"
        params = {
            "00_default.param": ParDict(
                {
                    "GPS_TYPE": Par(1.0, original_comment),
                }
            ),
        }

        upgrade_file_parameters_46(params)

        assert params["00_default.param"]["GPS1_TYPE"].comment == original_comment

    def test_comments_preserved_with_scaling_during_47_upgrade(self) -> None:
        """
        Comments are preserved even when values are scaled in 4.7 upgrade.

        GIVEN: Parameters with comments that will be scaled
        WHEN: upgrade_file_parameters_47 is called
        THEN: Comments remain unchanged even after scaling
        """
        original_comment = "Land speed in centimeters per second"
        params = {
            "00_default.param": ParDict(
                {
                    "LAND_SPEED": Par(100.0, original_comment),
                    "SERIAL0_PROTOCOL": Par(2.0, "MAVLink"),
                }
            ),
        }

        upgrade_file_parameters_47(params)

        assert params["00_default.param"]["LAND_SPD_MS"].comment == original_comment
        # Value should be scaled
        assert params["00_default.param"]["LAND_SPD_MS"].value == pytest.approx(1.0)


class TestVersionValidationEdgeCases:
    """Test edge cases in version string validation and comparison."""

    def test_empty_string_versions_trigger_warning_and_skip(self, caplog) -> None:
        """
        Empty version strings trigger warnings and skip upgrade.

        GIVEN: Empty parameter_files_version_str or flight_controller_version_str
        WHEN: upgrade_parameters_for_firmware_version is called
        THEN: Warning logged, no upgrade applied
        """
        params = {"00_default.param": ParDict({"GPS_TYPE": Par(1.0, "GPS")})}

        # Test empty param version
        upgrade_parameters_for_firmware_version("", "4.7.0", params)
        assert "Parameter files firmware version is unknown" in caplog.text
        assert "GPS_TYPE" in params["00_default.param"]  # Params unchanged

        # Test empty FC version
        caplog.clear()
        upgrade_parameters_for_firmware_version("4.6.0", "", params)
        assert "Flight controller firmware version is unknown" in caplog.text
        assert "GPS_TYPE" in params["00_default.param"]  # Params unchanged

    def test_invalid_version_strings_trigger_warning(self, caplog) -> None:
        """
        Invalid version strings trigger warnings and skip upgrade.

        GIVEN: Malformed version strings (e.g., "not-a-version", "4.x.y")
        WHEN: upgrade_parameters_for_firmware_version is called
        THEN: Warning logged, upgrade skipped
        """
        params = {"00_default.param": ParDict({"GPS_TYPE": Par(1.0, "GPS")})}

        upgrade_parameters_for_firmware_version("invalid-version", "4.7.0", params)
        assert "Invalid firmware version string" in caplog.text
        assert "GPS_TYPE" in params["00_default.param"]  # Params unchanged

    def test_prerelease_versions_handled(self) -> None:
        """
        Pre-release versions (with -rc, -dev) are handled correctly.

        GIVEN: Pre-release version strings like "4.7.0-rc1" or "4.6.0-dev"
        WHEN: upgrade_parameters_for_firmware_version is called
        THEN: Version comparison works correctly
        """
        params = {
            "00_default.param": ParDict(
                {
                    "GPS_TYPE": Par(1.0, "GPS"),
                    "SERIAL0_PROTOCOL": Par(2.0, "MAVLink"),
                }
            ),
        }

        # RC version should still trigger upgrade when FC > param version
        upgrade_parameters_for_firmware_version("4.6.0-rc1", "4.7.0-rc2", params)

        # Assert: 4.6 upgrade applied
        assert "GPS1_TYPE" in params["00_default.param"]
        assert "GPS_TYPE" not in params["00_default.param"]

        # Assert: 4.7 upgrade also applied — SERIAL0_PROTOCOL preserved (it is not in 4.7 rename dict)
        # No 4.7-specific rename in this fixture; 4.7 path is covered by TestVersionComparisonLogic
        assert "SERIAL0_PROTOCOL" in params["00_default.param"]
        assert params["00_default.param"]["SERIAL0_PROTOCOL"].value == pytest.approx(2.0)


class TestRoundTripConsistency:
    """Test that upgrades are consistent and idempotent where expected."""

    def test_same_version_upgrade_is_no_op_for_already_upgraded_params(self) -> None:
        """
        Calling upgrade with equal versions leaves already-upgraded parameters unchanged.

        GIVEN: Parameters already using 4.7.0 names (GPS1_TYPE, LAND_SPD_MS)
        WHEN: upgrade_parameters_for_firmware_version is called with matching versions
        THEN: No changes applied — already-upgraded parameter names are not re-processed
        """
        params_before = {
            "00_default.param": ParDict(
                {
                    "GPS1_TYPE": Par(1.0, "GPS"),
                    "LAND_SPD_MS": Par(1.0, "Land"),
                    "SERIAL0_PROTOCOL": Par(2.0, "MAVLink"),
                }
            ),
        }

        # Make a copy to compare after
        params_after = {
            "00_default.param": ParDict(
                {
                    "GPS1_TYPE": Par(1.0, "GPS"),
                    "LAND_SPD_MS": Par(1.0, "Land"),
                    "SERIAL0_PROTOCOL": Par(2.0, "MAVLink"),
                }
            ),
        }

        # Call with same version (no upgrade needed)
        upgrade_parameters_for_firmware_version("4.7.0", "4.7.0", params_after)

        # Verify no changes
        assert set(params_after["00_default.param"].keys()) == set(params_before["00_default.param"].keys())
        for key in params_before["00_default.param"]:
            assert params_after["00_default.param"][key].value == params_before["00_default.param"][key].value

    def test_upgrading_46_to_47_then_to_later_version(self) -> None:
        """
        Upgrading 4.6 → 4.7 then 4.7 → 4.8 (hypothetical) applies only 4.7 once.

        GIVEN: Parameters from 4.6
        WHEN: Upgraded first to 4.7.0, then to 4.8.0 (hypothetical)
        THEN: All PSC and other parameters upgraded exactly once
        """
        params = {
            "00_default.param": ParDict(
                {
                    "GPS_TYPE": Par(1.0, "GPS"),
                    "PSC_ACCZ_P": Par(2.0, "P gain"),
                    "SERIAL0_PROTOCOL": Par(2.0, "MAVLink"),
                }
            ),
        }

        upgrade_parameters_for_firmware_version("4.6.0", "4.7.0", params)
        # PSC_ACCZ_P should now be PSC_D_ACC_P with scaled value
        assert "PSC_D_ACC_P" in params["00_default.param"]
        assert params["00_default.param"]["PSC_D_ACC_P"].value == pytest.approx(0.2)

        # Upgrade again (to 4.8, but code only handles up to 4.7)
        upgrade_parameters_for_firmware_version("4.7.0", "4.8.0", params)
        # Should not re-upgrade already-upgraded parameters
        assert "PSC_D_ACC_P" in params["00_default.param"]
        assert params["00_default.param"]["PSC_D_ACC_P"].value == pytest.approx(0.2)


class TestMultipleFileConfigurations:
    """Test upgrades with multiple parameter files with different configurations."""

    def test_different_serial_configs_in_different_files(self) -> None:
        """
        Different SERIAL*_PROTOCOL configs in different files are handled correctly.

        GIVEN: Two files with different MAVLink port configurations
        WHEN: upgrade_file_parameters_47 is called
        THEN: SR mapping is built from all files combined
        """
        params = {
            "00_default.param": ParDict(
                {
                    "SERIAL0_PROTOCOL": Par(2.0, "MAVLink2"),
                    "SR0_RAW_SENS": Par(2.0, "Raw sensors"),
                }
            ),
            "02_radio.param": ParDict(
                {
                    "SERIAL1_PROTOCOL": Par(1.0, "MAVLink1"),
                    "SR1_EXTRA1": Par(2.0, "Extra 1"),
                }
            ),
        }

        upgrade_file_parameters_47(params)

        # SR0 should map to MAV1, SR1 to MAV2 (from combined mapping)
        assert "MAV1_RAW_SENS" in params["00_default.param"]
        assert "MAV2_EXTRA1" in params["02_radio.param"]
        assert "SR0_RAW_SENS" not in params["00_default.param"]
        assert "SR1_EXTRA1" not in params["02_radio.param"]

    def test_upgrade_preserves_file_boundaries(self) -> None:
        """
        Parameters stay in their original files during upgrade.

        GIVEN: Parameters split across multiple files
        WHEN: Upgrades applied
        THEN: No parameters move between files
        """
        params = {
            "00_default.param": ParDict({"GPS_TYPE": Par(1.0, "GPS")}),
            "02_radio.param": ParDict({"GPS_COM_PORT": Par(3.0, "Port")}),
        }

        upgrade_file_parameters_46(params)

        # GPS1_TYPE should be in 00_default, GPS1_COM_PORT in 02_radio
        assert "GPS1_TYPE" in params["00_default.param"]
        assert "GPS1_TYPE" not in params["02_radio.param"]
        assert "GPS1_COM_PORT" in params["02_radio.param"]
        assert "GPS1_COM_PORT" not in params["00_default.param"]
