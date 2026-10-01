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

import ardupilot_methodic_configurator.backend_filesystem_migration as migration_module
from ardupilot_methodic_configurator.backend_filesystem import LocalFilesystem
from ardupilot_methodic_configurator.backend_filesystem_migration import (
    VEHICLE_COMPONENTS_FORMAT_VERSION,
    _line_matches_any,
    _param_name_from_line,
    migrate_vehicle_project_if_needed,
)
from ardupilot_methodic_configurator.data_model_par_dict import ParDict

# pylint: disable=redefined-outer-name, unused-argument
# pylint: disable=too-many-lines


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
        Migration persists the latest format version after applying all supported steps.

        GIVEN: A vehicle directory with vehicle_components.json at format version 0
        WHEN: migrate_vehicle_project_if_needed is called once
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
        Running migrations through all versions does not duplicate param lines.

        GIVEN: A vehicle directory at format version 0 with a param that will be extracted
        WHEN: migrate_vehicle_project_if_needed is called until no migration remains
        THEN: Each format transition runs once, and the destination has no duplicate entries
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
        THEN: True is returned and the latest format version is written
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
# V1 → V2 parameter file migrations
# ---------------------------------------------------------------------------


class TestV1ToV2ParameterExtractions:
    """Tests that consecutive format migrations are persisted as separate steps."""

    def test_v2_destinations_are_seeded_from_empty_template_before_parameter_splits(
        self, vehicle_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """
        V2 template values survive while migrated project values override conflicts.

        GIVEN: A format-1 project with a mandatory-hardware file and a v2 empty template
        WHEN: The project migrates to format 2
        THEN: Template parameters are present, duplicate migrations reach both steps, and FRAME_CLASS is only in servo outputs
        """
        template_dir = vehicle_dir / "templates" / "ArduCopter" / "empty_4.6.x"
        template_dir.mkdir(parents=True)
        template_values = {
            "03_imu_temperature_calibration_results.param": "TEMPLATE_TEMP,1\n",
            "14_accelerometer_calibration.param": "TEMPLATE_ACCEL,1\nINS_ACCSCAL_X,1\n",
            "15_accelerometer_level.param": "TEMPLATE_LEVEL,1\n",
            "16_compass_calibration.param": "TEMPLATE_COMPASS,1\n",
            "17_flight_modes.param": "INITIAL_MODE,0\n",
            "18_servo_outputs.param": "TEMPLATE_SERVO,1\nSERVO1_FUNCTION,0\nFRAME_CLASS,0\n",
        }
        for filename, content in template_values.items():
            (template_dir / filename).write_text(content, encoding="utf-8")

        (vehicle_dir / "configuration_steps_ArduCopter.json").write_text(
            json.dumps({"steps": {filename: {} for filename in template_values} | {"05_board_orientation.param": {}}}),
            encoding="utf-8",
        )
        (vehicle_dir / "vehicle_components.json").write_text(
            json.dumps(
                {
                    "Format version": 1,
                    "Components": {"Flight Controller": {"Firmware": {"Type": "ArduCopter", "Version": "4.6.3 official"}}},
                }
            ),
            encoding="utf-8",
        )
        mandatory_hardware = vehicle_dir / "14_mp_setup_mandatory_hardware.param"
        mandatory_hardware.write_text(
            "INS_ACCSCAL_X,0.998941\nINS_ACC1_CALTEMP,45\nAHRS_TRIM_X,0.01\nFLTMODE1,3\nSERVO1_FUNCTION,33\nFRAME_CLASS,1\n",
            encoding="utf-8",
        )
        board_orientation = vehicle_dir / "05_board_orientation.param"
        board_orientation.write_text("AHRS_ORIENTATION,0\nFRAME_CLASS,1\n", encoding="utf-8")
        monkeypatch.setattr(
            migration_module.VehicleProjectCreator,
            "template_dir_for_bin_import",
            staticmethod(lambda _vehicle_type, _major, _minor: str(template_dir)),
        )
        monkeypatch.setattr(migration_module, "VEHICLE_COMPONENTS_FORMAT_VERSION", 2)

        assert migrate_vehicle_project_if_needed(str(vehicle_dir)) is True

        accelerometer = (vehicle_dir / "14_accelerometer_calibration.param").read_text(encoding="utf-8")
        imu_temperature = (vehicle_dir / "03_imu_temperature_calibration_results.param").read_text(encoding="utf-8")
        accelerometer_level = (vehicle_dir / "15_accelerometer_level.param").read_text(encoding="utf-8")
        flight_modes = (vehicle_dir / "17_flight_modes.param").read_text(encoding="utf-8")
        servo_outputs = (vehicle_dir / "18_servo_outputs.param").read_text(encoding="utf-8")

        assert "INS_ACC1_CALTEMP,45" in accelerometer
        assert "INS_ACC1_CALTEMP,45" in imu_temperature
        assert "AHRS_TRIM_X,0.01" in accelerometer
        assert "AHRS_TRIM_X,0.01" in accelerometer_level
        assert "INS_ACCSCAL_X,0.998941" in accelerometer
        assert "TEMPLATE_ACCEL,1" in accelerometer
        assert "TEMPLATE_TEMP,1" in imu_temperature
        assert "TEMPLATE_LEVEL,1" in accelerometer_level
        assert "TEMPLATE_COMPASS,1" in (vehicle_dir / "16_compass_calibration.param").read_text(encoding="utf-8")
        assert "INITIAL_MODE,0" in flight_modes
        assert "FLTMODE1,3" in flight_modes
        assert "TEMPLATE_SERVO,1" in servo_outputs
        assert "SERVO1_FUNCTION,33" in servo_outputs
        assert "FRAME_CLASS,1" in servo_outputs
        assert "FRAME_CLASS" not in board_orientation.read_text(encoding="utf-8")
        assert "FRAME_CLASS" not in accelerometer
        assert "FRAME_CLASS" not in (vehicle_dir / "05_board_orientation.param").read_text(encoding="utf-8")
        frame_class_files = [
            path.name
            for path in vehicle_dir.glob("*.param")
            if path.name != "00_default.param" and "FRAME_CLASS" in path.read_text(encoding="utf-8")
        ]
        assert frame_class_files == ["18_servo_outputs.param"]

    @pytest.mark.parametrize("failed_destination", ["14_accelerometer_calibration.param", "15_accelerometer_level.param"])
    def test_interrupted_split_preserves_source_values_and_can_be_retried(
        self, vehicle_dir: Path, monkeypatch: pytest.MonkeyPatch, failed_destination: str
    ) -> None:
        """
        A destination write failure cannot discard the project's only copy of calibration values.

        GIVEN: A format-1 source with calibration and trim values and a failing destination write
        WHEN: Migration is interrupted and then retried with working storage
        THEN: The source and version survive the failure, and retry produces each value exactly once
        """
        components = vehicle_dir / "vehicle_components.json"
        components.write_text(
            json.dumps({"Format version": 1, "Components": {"Flight Controller": {"Firmware": {"Type": "ArduCopter"}}}}),
            encoding="utf-8",
        )
        source = vehicle_dir / "14_mp_setup_mandatory_hardware.param"
        original_content = "INS_ACCSCAL_X,0.998941\nAHRS_TRIM_X,0.01\nUNRELATED_SOURCE,9\n"
        source.write_text(original_content, encoding="utf-8")
        monkeypatch.setattr(migration_module, "VEHICLE_COMPONENTS_FORMAT_VERSION", 2)
        original_write = migration_module._write_param_file_lines  # pylint: disable=protected-access

        def fail_destination_write(filepath: Path, lines: list[str]) -> None:
            if filepath.name == failed_destination:
                message = "simulated destination write failure"
                raise OSError(message)
            original_write(filepath, lines)

        with monkeypatch.context() as failure:
            failure.setattr(migration_module, "_write_param_file_lines", fail_destination_write)
            with pytest.raises(OSError, match="simulated destination write failure"):
                migrate_vehicle_project_if_needed(str(vehicle_dir))

        assert source.read_text(encoding="utf-8") == original_content
        assert json.loads(components.read_text(encoding="utf-8"))["Format version"] == 1

        assert migrate_vehicle_project_if_needed(str(vehicle_dir)) is True
        assert (vehicle_dir / "14_accelerometer_calibration.param").read_text(encoding="utf-8") == (
            "INS_ACCSCAL_X,0.998941\nAHRS_TRIM_X,0.01\n"
        )
        assert (vehicle_dir / "15_accelerometer_level.param").read_text(encoding="utf-8") == "AHRS_TRIM_X,0.01\n"
        assert source.read_text(encoding="utf-8") == "UNRELATED_SOURCE,9\n"
        assert json.loads(components.read_text(encoding="utf-8"))["Format version"] == 2

    def test_project_calibration_overrides_destination_defaults_without_duplicates(self, vehicle_dir: Path) -> None:
        """
        Project calibration values replace conflicting defaults while preserving unrelated settings.

        GIVEN: A mandatory-hardware source and an existing calibration destination with conflicting values
        WHEN: The format-2 split is applied and retried
        THEN: The source values win once and unrelated destination values and comments survive
        """
        source = vehicle_dir / "14_mp_setup_mandatory_hardware.param"
        source.write_text("INS_ACCSCAL_X,0.998941 # measured\nINS_USE,1\nUNRELATED_SOURCE,9\n", encoding="utf-8")
        destination = vehicle_dir / "14_accelerometer_calibration.param"
        destination.write_text("# keep this comment\nINS_ACCSCAL_X,1\nINS_USE,0\nINS_ACCOFFS_X,0.25\n", encoding="utf-8")

        migration_module._migrate_v1_to_v2(vehicle_dir, "ArduCopter")  # pylint: disable=protected-access
        first_content = destination.read_text(encoding="utf-8")
        migration_module._migrate_v1_to_v2(vehicle_dir, "ArduCopter")  # pylint: disable=protected-access

        parameters = ParDict.load_param_file_into_dict(str(destination))
        assert parameters["INS_ACCSCAL_X"].value == 0.998941
        assert parameters["INS_USE"].value == 1
        assert parameters["INS_ACCOFFS_X"].value == 0.25
        assert "# keep this comment\n" in first_content
        assert "# measured" in first_content
        assert destination.read_text(encoding="utf-8") == first_content
        assert source.read_text(encoding="utf-8") == "UNRELATED_SOURCE,9\n"

    @pytest.mark.parametrize(
        "source_name",
        [
            "11_mp_setup_mandatory_hardware.param",
            "12_mp_setup_mandatory_hardware.param",
            "14_mp_setup_mandatory_hardware.param",
        ],
    )
    def test_legacy_mandatory_hardware_values_are_split_before_renames(
        self, vehicle_dir: Path, vehicle_components_v0: Path, monkeypatch: pytest.MonkeyPatch, source_name: str
    ) -> None:
        """
        A format-0 project's calibration values reach the dedicated format-2 steps.

        GIVEN: A format-0 project with any supported mandatory-hardware filename
        WHEN: Migration runs through format 2 before filesystem renames
        THEN: All split values survive and the obsolete source is removed
        """
        source = vehicle_dir / source_name
        source.write_text(
            "INS_ACCSCAL_X,0.998941\nINS_ACC1_CALTEMP,45\nAHRS_TRIM_X,0.01\n"
            "COMPASS_OFS_X,12\nFLTMODE1,0\nRC1_MIN,1100\nSERVO1_FUNCTION,33\nFRAME_CLASS,1\n",
            encoding="utf-8",
        )
        monkeypatch.setattr(migration_module, "VEHICLE_COMPONENTS_FORMAT_VERSION", 2)

        assert migrate_vehicle_project_if_needed(str(vehicle_dir)) is True

        expected = {
            "14_accelerometer_calibration.param": ("INS_ACCSCAL_X,0.998941\nINS_ACC1_CALTEMP,45\nAHRS_TRIM_X,0.01\n"),
            "03_imu_temperature_calibration_results.param": "INS_ACC1_CALTEMP,45\n",
            "15_accelerometer_level.param": "AHRS_TRIM_X,0.01\n",
            "16_compass_calibration.param": "COMPASS_OFS_X,12\n",
            "17_flight_modes.param": "FLTMODE1,0\n",
            "07_remote_controller_controller.param": "RC1_MIN,1100\n",
            "18_servo_outputs.param": "SERVO1_FUNCTION,33\nFRAME_CLASS,1\n",
        }
        for filename, line in expected.items():
            assert line in (vehicle_dir / filename).read_text(encoding="utf-8")
        assert not source.exists()
        assert json.loads(vehicle_components_v0.read_text(encoding="utf-8"))["Format version"] == 2

    def test_format_zero_project_is_migrated_through_all_versions_in_one_open(
        self, vehicle_dir: Path, vehicle_components_v0: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """
        Each migration pass applies one version transition and persists it before the next pass.

        GIVEN: A format-version 0 project containing values used by both migrations
        WHEN: The project is migrated once
        THEN: v0→v1 is persisted before v1→v2 begins, and the final version is 2
        """
        source = vehicle_dir / "14_mp_setup_mandatory_hardware.param"
        source.write_text(
            "INS_ACCSCAL_X,1.1\n"
            "INS_ACC2SCAL_Y,2.2\n"
            "INS_USE,1\n"
            "INS_USE2,1\n"
            "INS_USE3,1\n"
            "INS_ACC1_CALTEMP,45\n"
            "AHRS_TRIM_X,0.01\n"
            "COMPASS_EXTERNAL,1\n"
            "COMPASS_OFS1_X,12\n"
            "FLTMODE1, stabilize\n"
            "RC1_MIN,1100\n"
            "FRAME_CLASS,1\n"
            "INS_ACCSCAL_X,0.998941\n"
            "MOT_THST_HOVER,0.301157\n"
            "SERVO1_FUNCTION,33\n"
            "UNRELATED_TEST,1\n",
            encoding="utf-8",
        )

        transition_versions: list[tuple[int, int]] = []
        v1_to_v2_input: list[str] = []
        original_v1_to_v2 = migration_module._migrate_v1_to_v2  # pylint: disable=protected-access

        def run_v0_to_v1(_path: Path, _vehicle_type: str) -> None:
            persisted_version = json.loads((vehicle_dir / "vehicle_components.json").read_text(encoding="utf-8"))[
                "Format version"
            ]
            transition_versions.append((0, persisted_version))

        def run_v1_to_v2(path: Path, vehicle_type: str) -> None:
            persisted_version = json.loads((vehicle_dir / "vehicle_components.json").read_text(encoding="utf-8"))[
                "Format version"
            ]
            transition_versions.append((1, persisted_version))
            v1_to_v2_input.append(source.read_text(encoding="utf-8"))
            original_v1_to_v2(path, vehicle_type)

        monkeypatch.setattr(migration_module, "_migrate_v0_to_v1", run_v0_to_v1)
        monkeypatch.setattr(migration_module, "_migrate_v1_to_v2", run_v1_to_v2)
        monkeypatch.setattr(migration_module, "_restore_missing_configuration_step_files", lambda *_args: None)
        monkeypatch.setattr(migration_module, "VEHICLE_COMPONENTS_FORMAT_VERSION", 2)

        result = migrate_vehicle_project_if_needed(str(vehicle_dir))
        final_data = json.loads((vehicle_dir / "vehicle_components.json").read_text(encoding="utf-8"))
        transitions_during_open = transition_versions.copy()
        second_result = migrate_vehicle_project_if_needed(str(vehicle_dir))

        assert result is True
        assert transitions_during_open == [(0, 0), (1, 1)]
        assert final_data["Format version"] == 2
        assert second_result is False
        assert "FRAME_CLASS,1" in v1_to_v2_input[0]
        assert "INS_ACCSCAL_X,0.998941" in v1_to_v2_input[0]
        assert "MOT_THST_HOVER,0.301157" in v1_to_v2_input[0]
        assert "UNRELATED_TEST,1" in v1_to_v2_input[0]

        second_pass_content = source.read_text(encoding="utf-8")
        assert "UNRELATED_TEST,1" in second_pass_content
        assert "INS_ACCSCAL_X,0.998941" not in second_pass_content
        assert "INS_ACCSCAL_X,0.998941" in (vehicle_dir / "14_accelerometer_calibration.param").read_text(encoding="utf-8")
        assert "INS_ACC1_CALTEMP,45" in (vehicle_dir / "03_imu_temperature_calibration_results.param").read_text(
            encoding="utf-8"
        )

    def test_restore_does_not_block_rename_from_an_old_filename(
        self, vehicle_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A template step is not restored when the project has its declared old filename."""
        template_dir = vehicle_dir / "templates" / "ArduCopter" / "empty_4.6.x"
        template_dir.mkdir(parents=True)
        (template_dir / "05_board_orientation.param").write_text("TEMPLATE,1\n", encoding="utf-8")
        (vehicle_dir / "configuration_steps_ArduCopter.json").write_text(
            json.dumps({"steps": {"05_board_orientation.param": {"old_filenames": ["04_board_orientation.param"]}}}),
            encoding="utf-8",
        )
        (vehicle_dir / "vehicle_components.json").write_text(
            json.dumps(
                {
                    "Format version": 0,
                    "Components": {"Flight Controller": {"Firmware": {"Type": "ArduCopter", "Version": "4.6.3"}}},
                }
            ),
            encoding="utf-8",
        )
        old_step = vehicle_dir / "04_board_orientation.param"
        old_step.write_text("AHRS_ORIENTATION,2\n", encoding="utf-8")
        monkeypatch.setattr(
            migration_module.VehicleProjectCreator,
            "template_dir_for_bin_import",
            staticmethod(lambda _vehicle_type, _major, _minor: str(template_dir)),
        )

        assert migrate_vehicle_project_if_needed(str(vehicle_dir)) is True
        assert old_step.read_text(encoding="utf-8") == "AHRS_ORIENTATION,2\n"
        assert not (vehicle_dir / "05_board_orientation.param").exists()

        filesystem = LocalFilesystem.__new__(LocalFilesystem)
        filesystem.vehicle_dir = str(vehicle_dir)
        filesystem.configuration_steps = {"05_board_orientation.param": {"old_filenames": ["04_board_orientation.param"]}}
        filesystem.rename_parameter_files()

        assert not old_step.exists()
        assert (vehicle_dir / "05_board_orientation.param").read_text(encoding="utf-8") == "AHRS_ORIENTATION,2\n"


class TestDeletedConfigurationStepFiles:  # pylint: disable=too-few-public-methods
    """Tests that restoration does not undo an intentional migration deletion."""

    def test_deleted_mandatory_hardware_file_is_not_restored_from_empty_template(
        self, vehicle_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A step deleted by v1→v2 stays deleted even when the empty template has that file."""
        template_dir = vehicle_dir / "templates" / "ArduCopter" / "empty_4.6.x"
        template_dir.mkdir(parents=True)
        (template_dir / "14_mp_setup_mandatory_hardware.param").write_text(
            "FRAME_CLASS,0\nINS_ACCSCAL_X,1\nMOT_THST_HOVER,0.35\n", encoding="utf-8"
        )
        (vehicle_dir / "configuration_steps_ArduCopter.json").write_text(
            json.dumps({"steps": {"14_mp_setup_mandatory_hardware.param": {}}}), encoding="utf-8"
        )
        (vehicle_dir / "vehicle_components.json").write_text(
            json.dumps(
                {
                    "Format version": 1,
                    "Components": {"Flight Controller": {"Firmware": {"Type": "ArduCopter", "Version": "4.6.3"}}},
                }
            ),
            encoding="utf-8",
        )
        mandatory_hardware = vehicle_dir / "14_mp_setup_mandatory_hardware.param"
        mandatory_hardware.write_text("FRAME_CLASS,1\nINS_ACCSCAL_X,0.998941\nMOT_THST_HOVER,0.301157\n", encoding="utf-8")
        monkeypatch.setattr(
            migration_module.VehicleProjectCreator,
            "template_dir_for_bin_import",
            staticmethod(lambda _vehicle_type, _major, _minor: str(template_dir)),
        )
        # Exercise the v1→v2 stage while the checked-in target remains format 1.
        monkeypatch.setattr(migration_module, "VEHICLE_COMPONENTS_FORMAT_VERSION", 2)

        assert migrate_vehicle_project_if_needed(str(vehicle_dir)) is True

        assert not mandatory_hardware.exists()
        assert "INS_ACCSCAL_X,0.998941" in (vehicle_dir / "14_accelerometer_calibration.param").read_text(encoding="utf-8")


class TestMissingConfigurationStepFileRestore:
    """Tests restoration of configuration-step files absent from old projects."""

    @pytest.mark.parametrize("existing_content", ["", "PROJECT_VALUE,17\n"])
    def test_restore_preserves_existing_steps_and_ignores_unlisted_template_files(
        self, vehicle_dir: Path, monkeypatch: pytest.MonkeyPatch, existing_content: str
    ) -> None:
        """
        Restoring missing steps preserves deliberate project contents and deletions.

        GIVEN: Existing, missing, deleted and unlisted files in a matching empty template
        WHEN: Missing configuration steps are restored using the project's step definitions
        THEN: Only the missing declared step is copied, including when existing files are empty
        """
        template_dir = vehicle_dir / "template"
        template_dir.mkdir()
        for filename in ["90_existing.param", "91_missing.param", "92_deleted.param", "93_unlisted.param"]:
            (template_dir / filename).write_text("TEMPLATE_VALUE,42\n", encoding="utf-8")
        existing = vehicle_dir / "90_existing.param"
        existing.write_text(existing_content, encoding="utf-8")
        (vehicle_dir / "configuration_steps_ArduCopter.json").write_text(
            json.dumps({"steps": {name: {} for name in ["90_existing.param", "91_missing.param", "92_deleted.param"]}}),
            encoding="utf-8",
        )
        monkeypatch.setattr(
            migration_module.VehicleProjectCreator,
            "template_dir_for_bin_import",
            staticmethod(lambda *_args: str(template_dir)),
        )

        migration_module._restore_missing_configuration_step_files(  # pylint: disable=protected-access
            vehicle_dir, "ArduCopter", "4.6.3", {"92_deleted.param"}
        )

        assert existing.read_text(encoding="utf-8") == existing_content
        assert (vehicle_dir / "91_missing.param").read_text(encoding="utf-8") == "TEMPLATE_VALUE,42\n"
        assert not (vehicle_dir / "92_deleted.param").exists()
        assert not (vehicle_dir / "93_unlisted.param").exists()

    def test_missing_step_file_is_copied_from_matching_empty_firmware_template(
        self, vehicle_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A missing step is restored from the empty_{major}.{minor}.x template after migration."""
        templates_dir = vehicle_dir / "templates"
        template_dir = templates_dir / "ArduCopter" / "empty_4.6.x"
        template_dir.mkdir(parents=True)
        (template_dir / "99_restored.param").write_text("RESTORED_PARAM,42\n", encoding="utf-8")
        (vehicle_dir / "configuration_steps_ArduCopter.json").write_text(
            json.dumps({"steps": {"99_restored.param": {}}}), encoding="utf-8"
        )
        (vehicle_dir / "vehicle_components.json").write_text(
            json.dumps(
                {
                    "Format version": 0,
                    "Components": {"Flight Controller": {"Firmware": {"Type": "ArduCopter", "Version": "4.6.3"}}},
                }
            ),
            encoding="utf-8",
        )
        monkeypatch.setattr(
            migration_module.VehicleProjectCreator,
            "template_dir_for_bin_import",
            staticmethod(lambda _vehicle_type, _major, _minor: str(template_dir)),
        )

        assert migrate_vehicle_project_if_needed(str(vehicle_dir)) is True
        assert (vehicle_dir / "99_restored.param").read_text(encoding="utf-8") == "RESTORED_PARAM,42\n"


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


# ---------------------------------------------------------------------------
# _param_name_from_line
# ---------------------------------------------------------------------------


class TestParamNameFromLine:
    """Unit tests for the _param_name_from_line helper."""

    def test_comma_separated_returns_name_only(self) -> None:
        """
        Comma-separated lines (Mission Planner format) return only the parameter name.

        GIVEN: A line in the format 'NAME,value'
        WHEN: _param_name_from_line is called
        THEN: Only the parameter name is returned
        """
        assert _param_name_from_line("BATT_MONITOR,4\n") == "BATT_MONITOR"

    def test_space_separated_returns_name_only(self) -> None:
        """
        Bug fix: space-separated lines must extract only the parameter name.

        GIVEN: A line in the format 'NAME value' (mavproxy format)
        WHEN: _param_name_from_line is called
        THEN: Only the parameter name is returned, not the full 'NAME value' string
        """
        assert _param_name_from_line("BATT_MONITOR 4\n") == "BATT_MONITOR"

    def test_tab_separated_returns_name_only(self) -> None:
        r"""
        Bug fix: tab-separated lines must extract only the parameter name.

        GIVEN: A line in the format 'NAME\tvalue' (mavproxy format)
        WHEN: _param_name_from_line is called
        THEN: Only the parameter name is returned, not the full 'NAME\tvalue' string

        Previously returned the entire line, breaking duplicate-parameter
        detection during migration and producing invalid .param files.
        """
        assert _param_name_from_line("BATT_MONITOR\t4\n") == "BATT_MONITOR"

    def test_comma_takes_priority_over_space(self) -> None:
        """
        When both comma and space are present, comma separator is used first.

        GIVEN: A line 'NAME,value with spaces'
        WHEN: _param_name_from_line is called
        THEN: The name before the comma is returned, matching load_param_file_into_dict priority
        """
        assert _param_name_from_line("PARAM_NAME,val ue\n") == "PARAM_NAME"  # codespell:ignore

    def test_blank_line_returns_empty_string(self) -> None:
        """
        Blank-only lines return an empty string.

        GIVEN: A blank line
        WHEN: _param_name_from_line is called
        THEN: An empty string is returned.
        """
        assert _param_name_from_line("   \n") == ""

    def test_comment_line_returns_empty_string(self) -> None:
        """
        Comment lines starting with '#' return an empty string.

        GIVEN: A comment line starting with '#'
        WHEN: _param_name_from_line is called
        THEN: An empty string is returned.
        """
        assert _param_name_from_line("# this is a comment\n") == ""

    def test_duplicate_detection_with_tab_separated_file(self) -> None:
        r"""
        End-to-end regression: tab-separated duplicate params are detected.

        GIVEN: An existing .param file with 'BATT_MONITOR\t4' (tab-separated)
          AND: A list of lines to merge containing 'BATT_MONITOR\t5'
        WHEN: Duplicate detection uses _param_name_from_line on both sides
        THEN: The duplicate is detected and the second line is NOT appended,
              leaving a file with exactly one BATT_MONITOR entry
        """
        existing = ["BATT_MONITOR\t4\n"]
        lines_to_add = ["BATT_MONITOR\t5\n"]

        existing_names = {name for line in existing if (name := _param_name_from_line(line))}
        new_lines = [line for line in lines_to_add if _param_name_from_line(line) not in existing_names]

        assert new_lines == [], "duplicate should be suppressed, not appended"

    def test_tab_separated_line_with_inline_comment_returns_name_only(self) -> None:
        r"""
        Tab-separated line with an inline comment returns only the parameter name.

        GIVEN: A line in the format 'NAME\tvalue # inline comment'
        WHEN: _param_name_from_line is called
        THEN: Only the parameter name is returned; the inline comment must not
              cause the space before '#' to be treated as the separator.
        """
        assert _param_name_from_line("BATT_MONITOR\t4 # inline comment\n") == "BATT_MONITOR"


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
