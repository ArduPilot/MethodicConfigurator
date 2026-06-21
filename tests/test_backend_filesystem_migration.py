#!/usr/bin/env python3

"""
Tests for the backend_filesystem_migration.py file.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import json
import logging
from pathlib import Path

import pytest

from ardupilot_methodic_configurator.backend_filesystem_migration import (
    VEHICLE_COMPONENTS_FORMAT_VERSION,
    _line_matches_any,
    _param_name_from_line,
    migrate_vehicle_project_if_needed,
)

# pylint: disable=redefined-outer-name, unused-argument


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def vehicle_dir(tmp_path: Path) -> Path:
    """Fixture providing a temporary vehicle directory for migration tests."""
    return tmp_path


@pytest.fixture
def vehicle_components_v0(vehicle_dir: Path) -> Path:
    """Fixture providing a vehicle_components.json at format version 0."""
    data = {
        "Format version": 0,
        "Components": {
            "Flight Controller": {
                "Firmware": {"Type": "ArduCopter"},
            }
        },
    }
    json_path = vehicle_dir / "vehicle_components.json"
    json_path.write_text(json.dumps(data, indent=4), encoding="utf-8")
    return json_path


@pytest.fixture
def vehicle_components_current(vehicle_dir: Path) -> Path:
    """Fixture providing a vehicle_components.json already at the current format version."""
    data = {
        "Format version": VEHICLE_COMPONENTS_FORMAT_VERSION,
        "Components": {"Flight Controller": {"Firmware": {"Type": "ArduCopter"}}},
    }
    json_path = vehicle_dir / "vehicle_components.json"
    json_path.write_text(json.dumps(data, indent=4), encoding="utf-8")
    return json_path


# ---------------------------------------------------------------------------
# migrate_vehicle_project_if_needed — guard conditions
# ---------------------------------------------------------------------------


class TestMigrationGuardConditions:
    """Tests that migration is correctly skipped for invalid or up-to-date projects."""

    def test_migration_is_skipped_when_vehicle_dir_is_empty(self) -> None:
        """
        Migration returns False when no vehicle directory is provided.

        GIVEN: No vehicle directory path
        WHEN: migrate_vehicle_project_if_needed is called with an empty string
        THEN: False is returned and no files are touched
        """
        result = migrate_vehicle_project_if_needed("")

        assert result is False

    def test_migration_is_skipped_when_vehicle_components_json_is_absent(self, vehicle_dir: Path) -> None:
        """
        Migration returns False when vehicle_components.json does not exist.

        GIVEN: A vehicle directory with no vehicle_components.json file
        WHEN: migrate_vehicle_project_if_needed is called
        THEN: False is returned
        """
        result = migrate_vehicle_project_if_needed(str(vehicle_dir))

        assert result is False

    def test_migration_is_skipped_when_project_is_already_current(
        self, vehicle_dir: Path, vehicle_components_current: Path
    ) -> None:
        """
        Migration returns False when the project format version is already current.

        GIVEN: A vehicle directory with vehicle_components.json at the current format version
        WHEN: migrate_vehicle_project_if_needed is called
        THEN: False is returned and the file is unchanged
        """
        original_mtime = vehicle_components_current.stat().st_mtime

        result = migrate_vehicle_project_if_needed(str(vehicle_dir))

        assert result is False
        assert vehicle_components_current.stat().st_mtime == original_mtime

    def test_migration_is_skipped_when_vehicle_components_json_contains_invalid_json(self, vehicle_dir: Path) -> None:
        """
        Migration returns False when vehicle_components.json cannot be parsed.

        GIVEN: A vehicle directory with a malformed vehicle_components.json
        WHEN: migrate_vehicle_project_if_needed is called
        THEN: False is returned without raising an exception
        """
        (vehicle_dir / "vehicle_components.json").write_text("{ not valid json }", encoding="utf-8")

        result = migrate_vehicle_project_if_needed(str(vehicle_dir))

        assert result is False

    def test_migration_is_skipped_when_vehicle_components_json_contains_a_list(self, vehicle_dir: Path) -> None:
        """
        Migration returns False when vehicle_components.json root value is not a dict.

        GIVEN: A vehicle directory with vehicle_components.json that contains a JSON list
        WHEN: migrate_vehicle_project_if_needed is called
        THEN: False is returned
        """
        (vehicle_dir / "vehicle_components.json").write_text("[1, 2, 3]", encoding="utf-8")

        result = migrate_vehicle_project_if_needed(str(vehicle_dir))

        assert result is False


# ---------------------------------------------------------------------------
# migrate_vehicle_project_if_needed — successful migration
# ---------------------------------------------------------------------------


class TestMigrationSuccess:
    """Tests that the migration applies correctly and updates the format version."""

    def test_migration_returns_true_for_outdated_project(self, vehicle_dir: Path, vehicle_components_v0: Path) -> None:
        """
        Migration returns True when the project format version is outdated.

        GIVEN: A vehicle directory with vehicle_components.json at format version 0
        WHEN: migrate_vehicle_project_if_needed is called
        THEN: True is returned
        """
        result = migrate_vehicle_project_if_needed(str(vehicle_dir))

        assert result is True

    def test_migration_updates_format_version_in_vehicle_components_json(
        self, vehicle_dir: Path, vehicle_components_v0: Path
    ) -> None:
        """
        Migration writes the current format version back to vehicle_components.json.

        GIVEN: A vehicle directory with vehicle_components.json at format version 0
        WHEN: migrate_vehicle_project_if_needed is called
        THEN: vehicle_components.json has 'Format version' equal to VEHICLE_COMPONENTS_FORMAT_VERSION
        """
        migrate_vehicle_project_if_needed(str(vehicle_dir))

        updated = json.loads(vehicle_components_v0.read_text(encoding="utf-8"))
        assert updated["Format version"] == VEHICLE_COMPONENTS_FORMAT_VERSION

    def test_migration_preserves_existing_vehicle_components_data(
        self, vehicle_dir: Path, vehicle_components_v0: Path
    ) -> None:
        """
        Migration does not discard other fields already stored in vehicle_components.json.

        GIVEN: A vehicle_components.json at format version 0 with a firmware type field
        WHEN: migrate_vehicle_project_if_needed is called
        THEN: The firmware type field is still present after migration
        """
        migrate_vehicle_project_if_needed(str(vehicle_dir))

        updated = json.loads(vehicle_components_v0.read_text(encoding="utf-8"))
        assert updated["Components"]["Flight Controller"]["Firmware"]["Type"] == "ArduCopter"

    def test_migration_is_idempotent(self, vehicle_dir: Path, vehicle_components_v0: Path) -> None:
        """
        Running migration twice on the same project does not duplicate param lines.

        GIVEN: A vehicle directory at format version 0 with a param that will be extracted
        WHEN: migrate_vehicle_project_if_needed is called twice in succession
        THEN: The first call returns True, the second returns False, and the destination
              param file contains no duplicate entries
        """
        (vehicle_dir / "04_board_orientation.param").write_text("BRD_HEAT_TARG,45\n", encoding="utf-8")

        first_result = migrate_vehicle_project_if_needed(str(vehicle_dir))
        second_result = migrate_vehicle_project_if_needed(str(vehicle_dir))

        assert first_result is True
        assert second_result is False
        finish_content = (vehicle_dir / "04_imu_temperature_calibration_finish.param").read_text(encoding="utf-8")
        assert finish_content.count("BRD_HEAT_TARG") == 1  # not duplicated by a second run

    def test_migration_logs_progress_messages(
        self, vehicle_dir: Path, vehicle_components_v0: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        """
        Migration emits informational log messages describing its progress.

        GIVEN: A vehicle directory at format version 0
        WHEN: migrate_vehicle_project_if_needed is called
        THEN: At least one INFO-level log message is emitted
        """
        with caplog.at_level(logging.INFO):
            migrate_vehicle_project_if_needed(str(vehicle_dir))

        assert any(record.levelno == logging.INFO for record in caplog.records)

    def test_migration_works_with_project_that_has_no_format_version_key(self, vehicle_dir: Path) -> None:
        """
        Migration treats a missing 'Format version' key as format version 0.

        GIVEN: A vehicle_components.json with no 'Format version' key
        WHEN: migrate_vehicle_project_if_needed is called
        THEN: True is returned and the format version key is written
        """
        data = {"Components": {}}
        (vehicle_dir / "vehicle_components.json").write_text(json.dumps(data), encoding="utf-8")

        result = migrate_vehicle_project_if_needed(str(vehicle_dir))

        assert result is True
        updated = json.loads((vehicle_dir / "vehicle_components.json").read_text(encoding="utf-8"))
        assert updated["Format version"] == VEHICLE_COMPONENTS_FORMAT_VERSION


# ---------------------------------------------------------------------------
# V0 → V1 parameter file migrations
# ---------------------------------------------------------------------------


class TestV0ToV1ParameterExtractions:
    """Tests that specific parameters are moved between files during v0→v1 migration."""

    def test_imu_calibration_params_are_extracted_from_board_orientation_file(
        self, vehicle_dir: Path, vehicle_components_v0: Path
    ) -> None:
        """
        BRD_HEAT_TARG and LOG_DISARMED are moved out of 04_board_orientation.param.

        GIVEN: 04_board_orientation.param contains BRD_HEAT_TARG, LOG_DISARMED and AHRS_ORIENTATION
        WHEN: migrate_vehicle_project_if_needed is called
        THEN: BRD_HEAT_TARG and LOG_DISARMED appear in 04_imu_temperature_calibration_finish.param
              and AHRS_ORIENTATION remains in 04_board_orientation.param
        """
        source = vehicle_dir / "04_board_orientation.param"
        source.write_text("AHRS_ORIENTATION,0\nBRD_HEAT_TARG,45\nLOG_DISARMED,1\n", encoding="utf-8")

        migrate_vehicle_project_if_needed(str(vehicle_dir))

        finish_file = vehicle_dir / "04_imu_temperature_calibration_finish.param"
        assert finish_file.exists()
        finish_content = finish_file.read_text(encoding="utf-8")
        assert "BRD_HEAT_TARG,45" in finish_content  # value must be preserved, not just name
        assert "LOG_DISARMED,1" in finish_content

        remaining_content = source.read_text(encoding="utf-8")
        assert "AHRS_ORIENTATION,0" in remaining_content
        assert "BRD_HEAT_TARG" not in remaining_content
        assert "LOG_DISARMED" not in remaining_content

    def test_rc_controller_params_are_extracted_into_dedicated_file(
        self, vehicle_dir: Path, vehicle_components_v0: Path
    ) -> None:
        """
        RC controller parameters leave 05_remote_controller.param and go to a dedicated file.

        GIVEN: 05_remote_controller.param contains RC5_OPTION, ARMING_RUDDER and RC_PROTOCOLS
        WHEN: migrate_vehicle_project_if_needed is called
        THEN: RC5_OPTION and ARMING_RUDDER appear in 07_remote_controller_controller.param
              and RC_PROTOCOLS stays in 05_remote_controller.param
        """
        source = vehicle_dir / "05_remote_controller.param"
        source.write_text("RC_PROTOCOLS,1\nRC5_OPTION,1\nARMING_RUDDER,2\n", encoding="utf-8")

        migrate_vehicle_project_if_needed(str(vehicle_dir))

        controller_file = vehicle_dir / "07_remote_controller_controller.param"
        assert controller_file.exists()
        controller_content = controller_file.read_text(encoding="utf-8")
        assert "RC5_OPTION" in controller_content
        assert "ARMING_RUDDER" in controller_content

        remaining_content = source.read_text(encoding="utf-8")
        assert "RC_PROTOCOLS" in remaining_content
        assert "RC5_OPTION" not in remaining_content

    def test_safety_params_are_extracted_from_general_configuration_file(
        self, vehicle_dir: Path, vehicle_components_v0: Path
    ) -> None:
        """
        Safety parameters leave 13_general_configuration.param for 16_safety_setup.param.

        GIVEN: 13_general_configuration.param contains ARMING_CHECK, FENCE_TYPE and SCR_ENABLE
        WHEN: migrate_vehicle_project_if_needed is called
        THEN: ARMING_CHECK and FENCE_TYPE appear in 16_safety_setup.param
              and SCR_ENABLE remains in 13_general_configuration.param
        """
        source = vehicle_dir / "13_general_configuration.param"
        source.write_text("SCR_ENABLE,1\nARMING_CHECK,1\nFENCE_TYPE,7\n", encoding="utf-8")

        migrate_vehicle_project_if_needed(str(vehicle_dir))

        safety_file = vehicle_dir / "16_safety_setup.param"
        assert safety_file.exists()
        safety_content = safety_file.read_text(encoding="utf-8")
        assert "ARMING_CHECK" in safety_content
        assert "FENCE_TYPE" in safety_content

        remaining_content = source.read_text(encoding="utf-8")
        assert "SCR_ENABLE" in remaining_content
        assert "ARMING_CHECK" not in remaining_content

    def test_slew_rate_params_are_accumulated_into_safety_file_from_esc_file(
        self, vehicle_dir: Path, vehicle_components_v0: Path
    ) -> None:
        """
        ESC slew-rate parameters accumulate into 16_safety_setup.param alongside safety params.

        GIVEN: 07_esc.param contains ATC_RAT_PIT_SMAX and MOT_PWM_MAX
        WHEN: migrate_vehicle_project_if_needed is called
        THEN: ATC_RAT_PIT_SMAX appears in 16_safety_setup.param
              and MOT_PWM_MAX does not appear in 16_safety_setup.param
        """
        esc_file = vehicle_dir / "07_esc.param"
        esc_file.write_text("ATC_RAT_PIT_SMAX,50\nATC_RAT_RLL_SMAX,50\nMOT_PWM_MAX,2000\n", encoding="utf-8")

        migrate_vehicle_project_if_needed(str(vehicle_dir))

        safety_file = vehicle_dir / "16_safety_setup.param"
        assert safety_file.exists()
        safety_content = safety_file.read_text(encoding="utf-8")
        assert "ATC_RAT_PIT_SMAX" in safety_content
        assert "ATC_RAT_RLL_SMAX" in safety_content
        assert "MOT_PWM_MAX" not in safety_content

    def test_autotune_param_leaves_everyday_use_file(self, vehicle_dir: Path, vehicle_components_v0: Path) -> None:
        """
        ATC_THR_MIX_MAX is moved from 53_everyday_use.param to 45_autotune_finish.param.

        GIVEN: 53_everyday_use.param contains ATC_THR_MIX_MAX and other parameters
        WHEN: migrate_vehicle_project_if_needed is called
        THEN: ATC_THR_MIX_MAX appears in 45_autotune_finish.param
              and is removed from 53_everyday_use.param
        """
        everyday_file = vehicle_dir / "53_everyday_use.param"
        # Use 0.5, which differs from the Step-2 hardcoded default (0.9), to prove the
        # user's tuned value is preserved rather than overwritten by the new-file default.
        everyday_file.write_text("ATC_THR_MIX_MAX,0.5\nSOME_OTHER_PARAM,1\n", encoding="utf-8")

        migrate_vehicle_project_if_needed(str(vehicle_dir))

        autotune_file = vehicle_dir / "45_autotune_finish.param"
        assert autotune_file.exists()
        autotune_content = autotune_file.read_text(encoding="utf-8")
        assert "ATC_THR_MIX_MAX,0.5" in autotune_content  # user value, not Step-2 default 0.9

        remaining = everyday_file.read_text(encoding="utf-8")
        assert "ATC_THR_MIX_MAX" not in remaining
        assert "SOME_OTHER_PARAM" in remaining

    def test_battery_monitor_params_move_from_batt1_to_dedicated_file(
        self, vehicle_dir: Path, vehicle_components_v0: Path
    ) -> None:
        """
        Battery monitor parameters leave 08_batt1.param for 10_battery_monitor.param.

        GIVEN: 08_batt1.param contains BATT_MONITOR, BATT_VOLT_PIN and BATT_CAPACITY
        WHEN: migrate_vehicle_project_if_needed is called
        THEN: BATT_MONITOR and BATT_VOLT_PIN appear in 10_battery_monitor.param
              and BATT_CAPACITY remains in 08_batt1.param
        """
        batt_file = vehicle_dir / "08_batt1.param"
        batt_file.write_text("BATT_MONITOR,4\nBATT_VOLT_PIN,14\nBATT_CAPACITY,5000\n", encoding="utf-8")

        migrate_vehicle_project_if_needed(str(vehicle_dir))

        monitor_file = vehicle_dir / "10_battery_monitor.param"
        assert monitor_file.exists()
        monitor_content = monitor_file.read_text(encoding="utf-8")
        assert "BATT_MONITOR" in monitor_content
        assert "BATT_VOLT_PIN" in monitor_content

        remaining = batt_file.read_text(encoding="utf-8")
        assert "BATT_CAPACITY" in remaining
        assert "BATT_MONITOR" not in remaining

    def test_extracted_params_are_not_duplicated_in_existing_destination_file(
        self, vehicle_dir: Path, vehicle_components_v0: Path
    ) -> None:
        """
        Parameters that already exist in the destination file are not appended again.

        GIVEN: 04_board_orientation.param has BRD_HEAT_TARG and 04_imu_temperature_calibration_finish.param
               already contains BRD_HEAT_TARG
        WHEN: migrate_vehicle_project_if_needed is called
        THEN: BRD_HEAT_TARG appears exactly once in 04_imu_temperature_calibration_finish.param
        """
        source = vehicle_dir / "04_board_orientation.param"
        source.write_text("BRD_HEAT_TARG,45\n", encoding="utf-8")

        dest = vehicle_dir / "04_imu_temperature_calibration_finish.param"
        dest.write_text("BRD_HEAT_TARG,40\n", encoding="utf-8")

        migrate_vehicle_project_if_needed(str(vehicle_dir))

        finish_content = dest.read_text(encoding="utf-8")
        assert finish_content.count("BRD_HEAT_TARG") == 1  # no duplication
        assert "BRD_HEAT_TARG" not in source.read_text(encoding="utf-8")  # removed from source

    def test_missing_source_file_is_skipped_with_a_warning(
        self, vehicle_dir: Path, vehicle_components_v0: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        """
        A missing migration source file produces a warning and does not abort the migration.

        GIVEN: The migration source file 53_everyday_use.param does not exist
        WHEN: migrate_vehicle_project_if_needed is called
        THEN: A WARNING is logged and migration continues (returns True)
        """
        # All 14 source files are absent; migration still completes (Step 2 creates new files)
        with caplog.at_level(logging.WARNING):
            result = migrate_vehicle_project_if_needed(str(vehicle_dir))

        assert result is True
        assert any(record.levelno == logging.WARNING for record in caplog.records)

    def test_hover_learn_param_is_extracted_from_esc_file_into_logging_file(
        self, vehicle_dir: Path, vehicle_components_v0: Path
    ) -> None:
        """
        MOT_HOVER_LEARN leaves 07_esc.param and lands in 14_logging.param.

        GIVEN: 07_esc.param contains MOT_HOVER_LEARN and MOT_PWM_MAX
        WHEN: migrate_vehicle_project_if_needed is called
        THEN: MOT_HOVER_LEARN appears in 14_logging.param with its original value
              and MOT_PWM_MAX remains in 07_esc.param
        """
        esc_file = vehicle_dir / "07_esc.param"
        esc_file.write_text("MOT_HOVER_LEARN,2\nMOT_PWM_MAX,2000\n", encoding="utf-8")

        migrate_vehicle_project_if_needed(str(vehicle_dir))

        logging_file = vehicle_dir / "14_logging.param"
        assert logging_file.exists()
        assert "MOT_HOVER_LEARN,2" in logging_file.read_text(encoding="utf-8")
        assert "MOT_HOVER_LEARN" not in esc_file.read_text(encoding="utf-8")

    def test_servo_params_with_numbered_suffix_are_extracted_to_motor_file(
        self, vehicle_dir: Path, vehicle_components_v0: Path
    ) -> None:
        r"""
        Numbered SERVO params (e.g. SERVO5_FUNCTION) are matched by regex and moved to 15_motor.param.

        GIVEN: 07_esc.param contains SERVO5_FUNCTION and SERVO_BLH_POLES
        WHEN: migrate_vehicle_project_if_needed is called
        THEN: SERVO5_FUNCTION appears in 15_motor.param (regex SERVO\\d+_FUNCTION matched)
              and SERVO_BLH_POLES is in 19_motor.param (literal match)
              and neither remain in 07_esc.param
        """
        esc_file = vehicle_dir / "07_esc.param"
        esc_file.write_text("SERVO5_FUNCTION,33\nSERVO_BLH_POLES,14\nMOT_SPOOL_TIME,0.5\n", encoding="utf-8")

        migrate_vehicle_project_if_needed(str(vehicle_dir))

        motor_file = vehicle_dir / "15_motor.param"
        assert motor_file.exists()
        assert "SERVO5_FUNCTION,33" in motor_file.read_text(encoding="utf-8")

        poles_file = vehicle_dir / "19_motor.param"
        assert poles_file.exists()
        assert "SERVO_BLH_POLES,14" in poles_file.read_text(encoding="utf-8")

        esc_remaining = esc_file.read_text(encoding="utf-8")
        assert "SERVO5_FUNCTION" not in esc_remaining
        assert "SERVO_BLH_POLES" not in esc_remaining

    def test_throttle_controller_params_leave_esc_file(self, vehicle_dir: Path, vehicle_components_v0: Path) -> None:
        """
        MOT_SPOOL_TIME and TKOFF_SLEW_TIME leave 07_esc.param for 20_throttle_controller.param.

        GIVEN: 07_esc.param contains MOT_SPOOL_TIME and TKOFF_SLEW_TIME alongside other params
        WHEN: migrate_vehicle_project_if_needed is called
        THEN: Both params appear in 20_throttle_controller.param with their original values
              and are absent from 07_esc.param
        """
        esc_file = vehicle_dir / "07_esc.param"
        esc_file.write_text("MOT_SPOOL_TIME,0.5\nTKOFF_SLEW_TIME,2.0\nARMING_CHECK,1\n", encoding="utf-8")

        migrate_vehicle_project_if_needed(str(vehicle_dir))

        throttle_file = vehicle_dir / "20_throttle_controller.param"
        assert throttle_file.exists()
        content = throttle_file.read_text(encoding="utf-8")
        assert "MOT_SPOOL_TIME,0.5" in content
        assert "TKOFF_SLEW_TIME,2.0" in content

        esc_remaining = esc_file.read_text(encoding="utf-8")
        assert "MOT_SPOOL_TIME" not in esc_remaining
        assert "TKOFF_SLEW_TIME" not in esc_remaining
        assert "ARMING_CHECK" in esc_remaining  # unrelated param stays

    def test_remaining_batt2_params_consolidate_into_batt1_file(self, vehicle_dir: Path, vehicle_components_v0: Path) -> None:
        """
        Non-monitor battery params from 09_batt2.param consolidate into 08_batt1.param.

        GIVEN: 09_batt2.param contains BATT2_CAPACITY (not a monitor/volt/curr param)
        WHEN: migrate_vehicle_project_if_needed is called
        THEN: BATT2_CAPACITY appears in 08_batt1.param
              and 09_batt2.param is deleted
        """
        (vehicle_dir / "09_batt2.param").write_text("BATT2_CAPACITY,10000\n", encoding="utf-8")

        migrate_vehicle_project_if_needed(str(vehicle_dir))

        batt1_file = vehicle_dir / "08_batt1.param"
        assert batt1_file.exists()
        assert "BATT2_CAPACITY,10000" in batt1_file.read_text(encoding="utf-8")
        assert not (vehicle_dir / "09_batt2.param").exists()


# ---------------------------------------------------------------------------
# V0 → V1 new file creation
# ---------------------------------------------------------------------------


class TestV0ToV1NewFileCreation:
    """Tests that new files required by v1 are created during migration."""

    def test_osd_param_file_is_created_when_absent(self, vehicle_dir: Path, vehicle_components_v0: Path) -> None:
        """
        18_osd.param is created with OSD_TYPE,0 when the project is migrated.

        GIVEN: A vehicle directory at format version 0 with no 18_osd.param
        WHEN: migrate_vehicle_project_if_needed is called
        THEN: 18_osd.param exists and contains OSD_TYPE,0
        """
        migrate_vehicle_project_if_needed(str(vehicle_dir))

        osd_file = vehicle_dir / "18_osd.param"
        assert osd_file.exists()
        assert "OSD_TYPE,0" in osd_file.read_text(encoding="utf-8")

    def test_pid_notch_filter_logging_file_is_created_when_absent(
        self, vehicle_dir: Path, vehicle_components_v0: Path
    ) -> None:
        """
        27_pid_notch_filter_logging.param is created with required notch filter params.

        GIVEN: A vehicle directory at format version 0 with no 27_pid_notch_filter_logging.param
        WHEN: migrate_vehicle_project_if_needed is called
        THEN: 27_pid_notch_filter_logging.param exists and contains INS_LOG_BAT_MASK
        """
        migrate_vehicle_project_if_needed(str(vehicle_dir))

        notch_file = vehicle_dir / "27_pid_notch_filter_logging.param"
        assert notch_file.exists()
        assert "INS_LOG_BAT_MASK" in notch_file.read_text(encoding="utf-8")

    def test_pid_notch_filter_results_file_is_created_when_absent(
        self, vehicle_dir: Path, vehicle_components_v0: Path
    ) -> None:
        """
        28_pid_notch_filter_results.param is created with default zero values.

        GIVEN: A vehicle directory at format version 0
        WHEN: migrate_vehicle_project_if_needed is called
        THEN: 28_pid_notch_filter_results.param contains ATC_RAT_RLL_NTF,0
        """
        migrate_vehicle_project_if_needed(str(vehicle_dir))

        results_file = vehicle_dir / "28_pid_notch_filter_results.param"
        assert results_file.exists()
        assert "ATC_RAT_RLL_NTF,0" in results_file.read_text(encoding="utf-8")

    def test_autotune_finish_file_is_created_when_absent(self, vehicle_dir: Path, vehicle_components_v0: Path) -> None:
        """
        45_autotune_finish.param is created with ATC_THR_MIX_MAX when no source exists.

        GIVEN: A vehicle directory at format version 0 with no 53_everyday_use.param
        WHEN: migrate_vehicle_project_if_needed is called
        THEN: 45_autotune_finish.param exists and contains ATC_THR_MIX_MAX
        """
        migrate_vehicle_project_if_needed(str(vehicle_dir))

        autotune_file = vehicle_dir / "45_autotune_finish.param"
        assert autotune_file.exists()
        assert "ATC_THR_MIX_MAX" in autotune_file.read_text(encoding="utf-8")

    def test_windspeed_estimation_finish_file_is_created_when_absent(
        self, vehicle_dir: Path, vehicle_components_v0: Path
    ) -> None:
        """
        49_windspeed_estimation_finish.param is created with LOG_DISARMED,0 and LOG_REPLAY,0.

        GIVEN: A vehicle directory at format version 0
        WHEN: migrate_vehicle_project_if_needed is called
        THEN: 49_windspeed_estimation_finish.param contains LOG_DISARMED,0 and LOG_REPLAY,0
        """
        migrate_vehicle_project_if_needed(str(vehicle_dir))

        finish_file = vehicle_dir / "49_windspeed_estimation_finish.param"
        assert finish_file.exists()
        content = finish_file.read_text(encoding="utf-8")
        assert "LOG_DISARMED,0" in content
        assert "LOG_REPLAY,0" in content

    def test_system_id_roll_file_is_created_when_absent(self, vehicle_dir: Path, vehicle_components_v0: Path) -> None:
        """
        50_system_id_input_roll.param is created with SID_AXIS,1.

        GIVEN: A vehicle directory at format version 0
        WHEN: migrate_vehicle_project_if_needed is called
        THEN: 50_system_id_input_roll.param exists with SID_AXIS,1
        """
        migrate_vehicle_project_if_needed(str(vehicle_dir))

        roll_file = vehicle_dir / "50_system_id_input_roll.param"
        assert roll_file.exists()
        assert "SID_AXIS,1" in roll_file.read_text(encoding="utf-8")

    def test_existing_new_files_are_not_overwritten_during_migration(
        self, vehicle_dir: Path, vehicle_components_v0: Path
    ) -> None:
        """
        New-file creation is skipped for files that already exist.

        GIVEN: 18_osd.param already exists with custom content
        WHEN: migrate_vehicle_project_if_needed is called
        THEN: 18_osd.param retains its original content
        """
        osd_file = vehicle_dir / "18_osd.param"
        custom_content = "OSD_TYPE,3\nOSD_UNITS,1\n"
        osd_file.write_text(custom_content, encoding="utf-8")

        migrate_vehicle_project_if_needed(str(vehicle_dir))

        assert osd_file.read_text(encoding="utf-8") == custom_content

    def test_pid_d_ff_file_is_created_when_absent(self, vehicle_dir: Path, vehicle_components_v0: Path) -> None:
        """
        46_pid_d_ff.param is created with roll/pitch/yaw/accz D-FF parameters all set to zero.

        GIVEN: A vehicle directory at format version 0 with no 46_pid_d_ff.param
        WHEN: migrate_vehicle_project_if_needed is called
        THEN: 46_pid_d_ff.param contains all four D-FF parameters set to 0
        """
        migrate_vehicle_project_if_needed(str(vehicle_dir))

        dff_file = vehicle_dir / "46_pid_d_ff.param"
        assert dff_file.exists()
        content = dff_file.read_text(encoding="utf-8")
        assert "ATC_RAT_RLL_D_FF,0" in content
        assert "ATC_RAT_PIT_D_FF,0" in content
        assert "ATC_RAT_YAW_D_FF,0" in content
        assert "PSC_ACCZ_D_FF,0" in content

    def test_all_three_system_id_files_are_created_with_correct_axis_assignments(
        self, vehicle_dir: Path, vehicle_components_v0: Path
    ) -> None:
        """
        System-ID files are created for roll (axis 1), pitch (axis 2), and yaw (axis 3).

        GIVEN: A vehicle directory at format version 0
        WHEN: migrate_vehicle_project_if_needed is called
        THEN: 50_system_id_input_roll.param has SID_AXIS,1
              51_system_id_input_pitch.param has SID_AXIS,2
              52_system_id_input_yaw.param has SID_AXIS,3
        """
        migrate_vehicle_project_if_needed(str(vehicle_dir))

        assert "SID_AXIS,1" in (vehicle_dir / "50_system_id_input_roll.param").read_text(encoding="utf-8")
        assert "SID_AXIS,2" in (vehicle_dir / "51_system_id_input_pitch.param").read_text(encoding="utf-8")
        assert "SID_AXIS,3" in (vehicle_dir / "52_system_id_input_yaw.param").read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# V0 → V1 obsolete file deletion
# ---------------------------------------------------------------------------


class TestV0ToV1ObsoleteFileDeletion:
    """Tests that files no longer part of the v1 sequence are removed."""

    def test_second_battery_file_is_deleted_after_migration(self, vehicle_dir: Path, vehicle_components_v0: Path) -> None:
        """
        09_batt2.param is removed because its content consolidates into 08_batt1.param.

        GIVEN: 09_batt2.param exists in the vehicle directory
        WHEN: migrate_vehicle_project_if_needed is called
        THEN: 09_batt2.param no longer exists
        """
        (vehicle_dir / "09_batt2.param").write_text("BATT2_MONITOR,4\n", encoding="utf-8")

        migrate_vehicle_project_if_needed(str(vehicle_dir))

        assert not (vehicle_dir / "09_batt2.param").exists()

    def test_old_quick_tune_setup_file_is_deleted_after_migration(
        self, vehicle_dir: Path, vehicle_components_v0: Path
    ) -> None:
        """
        26_quick_tune_setup.param is removed because it is obsolete in v1.

        GIVEN: 26_quick_tune_setup.param exists in the vehicle directory
        WHEN: migrate_vehicle_project_if_needed is called
        THEN: 26_quick_tune_setup.param no longer exists
        """
        (vehicle_dir / "26_quick_tune_setup.param").write_text("QUIK_ENABLE,1\n", encoding="utf-8")

        migrate_vehicle_project_if_needed(str(vehicle_dir))

        assert not (vehicle_dir / "26_quick_tune_setup.param").exists()

    def test_old_quick_tune_results_file_is_deleted_after_migration(
        self, vehicle_dir: Path, vehicle_components_v0: Path
    ) -> None:
        """
        27_quick_tune_results.param is removed because it is obsolete in v1.

        GIVEN: 27_quick_tune_results.param exists in the vehicle directory
        WHEN: migrate_vehicle_project_if_needed is called
        THEN: 27_quick_tune_results.param no longer exists
        """
        (vehicle_dir / "27_quick_tune_results.param").write_text("QUIK_ENABLE,0\n", encoding="utf-8")

        migrate_vehicle_project_if_needed(str(vehicle_dir))

        assert not (vehicle_dir / "27_quick_tune_results.param").exists()

    def test_obsolete_files_that_are_already_absent_are_silently_ignored(
        self, vehicle_dir: Path, vehicle_components_v0: Path
    ) -> None:
        """
        Migration succeeds even when the obsolete files are already absent.

        GIVEN: None of the obsolete files (09_batt2.param etc.) exist
        WHEN: migrate_vehicle_project_if_needed is called
        THEN: True is returned without raising an exception
        """
        result = migrate_vehicle_project_if_needed(str(vehicle_dir))

        assert result is True


# ---------------------------------------------------------------------------
# Pattern-matching edge cases
# ---------------------------------------------------------------------------


class TestPatternMatchingEdgeCases:
    r"""
    Non-obvious pattern-matching behaviors that exercise the regex engine path.

    Simple literal-match and regex-match behaviors are already demonstrated
    implicitly by the integration tests above (e.g. BATT\\d*_MONITOR matching
    BATT2_MONITOR, SERVO\\d+_FUNCTION matching SERVO5_FUNCTION).  Only the
    two edge cases that cannot be meaningfully exercised at the integration
    level are covered here.
    """

    def test_regex_fullmatch_prevents_partial_prefix_match(self) -> None:
        """
        A pattern that is a strict prefix of a param name does not match.

        GIVEN: The pattern 'ARMING' (no wildcard)
        WHEN: _line_matches_any is called with 'ARMING_CHECK'
        THEN: False is returned, confirming re.fullmatch semantics are used
        """
        assert _line_matches_any("ARMING_CHECK", ["ARMING"]) is False

    def test_malformed_regex_is_handled_gracefully(self) -> None:
        """
        A syntactically invalid regex pattern does not raise and returns False.

        GIVEN: A malformed pattern '[invalid' that re.fullmatch cannot compile
        WHEN: _line_matches_any is called with any parameter name
        THEN: False is returned without raising an exception
        """
        assert _line_matches_any("ARMING_CHECK", ["[invalid"]) is False

    def test_param_name_from_line_handles_comma_separated(self) -> None:
        """
        Comma-separated lines (Mission Planner format) extract the parameter name.

        GIVEN: A line in the format 'NAME,value'
        WHEN: _param_name_from_line is called
        THEN: Only the parameter name is returned, value is discarded
        """
        assert _param_name_from_line("BATT_MONITOR,4\n") == "BATT_MONITOR"

    def test_param_name_from_line_handles_tab_separated(self) -> None:
        r"""
        Bug fix: tab-separated lines (mavproxy format) must extract only the name.

        GIVEN: A line in the format 'NAME\tvalue', a valid ArduPilot param
            file format also accepted by ParDict.load_param_file_into_dict
        WHEN: _param_name_from_line is called
        THEN: Only the parameter name is returned, not the full line

        Previously this returned the entire line (name and value together),
        which broke duplicate-parameter detection during migration: a
        tab-separated file with the same parameter at a different value in
        the source and destination would not be recognized as a duplicate,
        producing an invalid .param file with the parameter listed twice.
        """
        assert _param_name_from_line("BATT_MONITOR\t4\n") == "BATT_MONITOR"

    def test_param_name_from_line_handles_space_separated(self) -> None:
        """
        Bug fix: space-separated lines (mavproxy format) must extract only the name.

        GIVEN: A line in the format 'NAME value'
        WHEN: _param_name_from_line is called
        THEN: Only the parameter name is returned, not the full line
        """
        assert _param_name_from_line("BATT_MONITOR 4\n") == "BATT_MONITOR"


# ---------------------------------------------------------------------------
# Vehicle-type gating
# ---------------------------------------------------------------------------


class TestVehicleTypeGating:
    """Tests that vehicle-type-specific migration entries are applied correctly."""

    def test_unknown_vehicle_type_logs_an_error_but_migration_still_succeeds(
        self, vehicle_dir: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        """
        An unrecognised vehicle type triggers an ERROR log but does not abort migration.

        GIVEN: A vehicle_components.json at format version 0 with type 'ArduSub'
        WHEN: migrate_vehicle_project_if_needed is called
        THEN: True is returned, an ERROR is logged mentioning the unknown type,
              and the format version is updated to the current version
        """
        data = {
            "Format version": 0,
            "Components": {"Flight Controller": {"Firmware": {"Type": "ArduSub"}}},
        }
        (vehicle_dir / "vehicle_components.json").write_text(json.dumps(data, indent=4), encoding="utf-8")

        with caplog.at_level(logging.ERROR):
            result = migrate_vehicle_project_if_needed(str(vehicle_dir))

        assert result is True
        assert any("ArduSub" in record.message for record in caplog.records if record.levelno == logging.ERROR)
        updated = json.loads((vehicle_dir / "vehicle_components.json").read_text(encoding="utf-8"))
        assert updated["Format version"] == VEHICLE_COMPONENTS_FORMAT_VERSION

    def test_known_non_ardupilot_copter_vehicle_type_migrates_without_errors(
        self, vehicle_dir: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        """
        A known non-ArduCopter vehicle type (e.g. ArduPlane) runs 'all' migrations cleanly.

        GIVEN: A vehicle_components.json at format version 0 with type 'ArduPlane'
        WHEN: migrate_vehicle_project_if_needed is called
        THEN: True is returned with no ERROR-level log messages,
              and the 'all' new files (e.g. 18_osd.param) are created
        """
        data = {
            "Format version": 0,
            "Components": {"Flight Controller": {"Firmware": {"Type": "ArduPlane"}}},
        }
        (vehicle_dir / "vehicle_components.json").write_text(json.dumps(data, indent=4), encoding="utf-8")

        with caplog.at_level(logging.ERROR):
            result = migrate_vehicle_project_if_needed(str(vehicle_dir))

        assert result is True
        assert not any(record.levelno == logging.ERROR for record in caplog.records)
        assert (vehicle_dir / "18_osd.param").exists()
