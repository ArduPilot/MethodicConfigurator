#!/usr/bin/env python3

"""
Tests for the backend_filesystem_migration.py file.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import errno
import json
import logging
import os
import subprocess
import sys
from collections.abc import Iterable
from pathlib import Path
from shutil import copyfile
from stat import S_IMODE
from typing import IO, BinaryIO

import pytest

import ardupilot_methodic_configurator.backend_filesystem as filesystem_module
import ardupilot_methodic_configurator.backend_filesystem_migration as migration_module
from ardupilot_methodic_configurator.annotate_params import parse_parameter_metadata
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


def _interrupt_migration_write(monkeypatch: pytest.MonkeyPatch, destination: Path, failure_stage: str) -> None:
    """Inject a storage failure after a real write begins, without mocking migration logic."""
    original_open = open
    original_fsync = migration_module.fsync
    original_replace = Path.replace
    failing_descriptors: set[int] = set()
    message = f"simulated migration {failure_stage} failure"

    def open_with_failure(path: Path, mode: str = "r", *, encoding: str | None = None, newline: str | None = None) -> IO[str]:
        # Ownership passes to the caller's context manager, just like builtins.open.
        stream = original_open(path, mode, encoding=encoding, newline=newline)  # pylint: disable=consider-using-with
        if mode in {"w", "x"} and (path == destination or path.name.startswith(f".migration-{destination.name}-")):
            failing_descriptors.add(stream.fileno())
            original_write = stream.write

            def partial_write(content: str) -> int:
                original_write(content[:10])
                stream.flush()
                raise OSError(message)

            def partial_writelines(lines: Iterable[str]) -> None:
                partial_write("".join(lines))

            if failure_stage == "write":
                monkeypatch.setattr(stream, "write", partial_write)
                monkeypatch.setattr(stream, "writelines", partial_writelines)
        return stream

    def failing_fsync(descriptor: int) -> None:
        if failure_stage == "fsync" and descriptor in failing_descriptors:
            raise OSError(message)
        original_fsync(descriptor)

    def failing_replace(temporary: Path, target: Path) -> Path:
        if failure_stage == "replace" and target == destination:
            raise OSError(message)
        return original_replace(temporary, target)

    monkeypatch.setattr(migration_module, "open", open_with_failure, raising=False)
    monkeypatch.setattr(migration_module, "fsync", failing_fsync)
    monkeypatch.setattr(Path, "replace", failing_replace)


# ---------------------------------------------------------------------------
# Atomic migration file publication
# ---------------------------------------------------------------------------


class TestAtomicMigrationFileWrites:
    """Migration saves preserve file contents and project permission policies."""

    @pytest.mark.parametrize("lines", [[], ["VALUE,17  # measured °C\n"]], ids=["empty", "utf8"])
    def test_new_parameter_files_follow_normal_creation_permissions(self, vehicle_dir: Path, lines: list[str]) -> None:
        """
        Atomic saves create empty and UTF-8 parameter files with normal project permissions.

        GIVEN: A missing parameter file and a normally created comparison file
        WHEN: Migration publishes the requested contents
        THEN: Contents match exactly and creation permissions match the normal file
        """
        destination = vehicle_dir / "new.param"
        comparison = vehicle_dir / "comparison.param"
        comparison.write_bytes(b"normal creation")

        migration_module._write_param_file_lines(destination, lines)  # pylint: disable=protected-access

        assert destination.read_bytes() == "".join(lines).encode("utf-8")
        assert S_IMODE(destination.stat().st_mode) == S_IMODE(comparison.stat().st_mode)
        assert not list(vehicle_dir.glob("*.tmp"))

    @pytest.mark.skipif(os.name != "posix", reason="POSIX permission bits are not meaningful on Windows")
    @pytest.mark.parametrize("permission_mode", [0o600, 0o640, 0o660])
    def test_saving_existing_parameter_files_preserves_permissions(self, vehicle_dir: Path, permission_mode: int) -> None:
        """
        Atomic replacement must not broaden or restrict existing project file permissions.

        GIVEN: A parameter file with private or shared permissions
        WHEN: Migration replaces its contents
        THEN: Its original permission bits survive
        """
        destination = vehicle_dir / "existing.param"
        destination.write_bytes(b"VALUE,1\n")
        destination.chmod(permission_mode)

        migration_module._write_param_file_lines(destination, ["VALUE,2\n"])  # pylint: disable=protected-access

        assert destination.read_bytes() == b"VALUE,2\n"
        assert S_IMODE(destination.stat().st_mode) == permission_mode
        assert not list(vehicle_dir.glob("*.tmp"))

    def test_user_can_retry_save_without_overwriting_an_occupied_temporary_name(
        self, vehicle_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """
        A temporary-name collision cannot destroy unrelated files or existing project values.

        GIVEN: A project parameter file and an occupied temporary filename
        WHEN: Saving collides with that name, then retries with a fresh name
        THEN: Both original files survive the failure and only the project file changes on retry
        """
        destination = vehicle_dir / "existing.param"
        destination.write_bytes(b"VALUE,1\n")
        occupied = vehicle_dir / ".migration-existing.param-occupied.tmp"
        occupied.write_bytes(b"unrelated file")

        with monkeypatch.context() as collision:
            collision.setattr(migration_module, "token_hex", lambda *_args: "occupied")
            with pytest.raises(FileExistsError):
                migration_module._write_param_file_lines(destination, ["VALUE,2\n"])  # pylint: disable=protected-access

        assert destination.read_bytes() == b"VALUE,1\n"
        assert occupied.read_bytes() == b"unrelated file"

        migration_module._write_param_file_lines(destination, ["VALUE,2\n"])  # pylint: disable=protected-access

        assert destination.read_bytes() == b"VALUE,2\n"
        assert occupied.read_bytes() == b"unrelated file"
        assert list(vehicle_dir.glob("*.tmp")) == [occupied]


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


class TestParameterFileDocumentationRenames:
    """Step-specific parameter documentation follows filename aliases without losing user files."""

    @pytest.fixture(
        params=[
            "22_inflight_magnetometer_fit_setup.param",
            "24_inflight_magnetometer_fit_setup.param",
            "31_inflight_magnetometer_fit_setup.param",
        ]
    )
    def magfit_alias_project(self, vehicle_dir: Path, request: pytest.FixtureRequest) -> tuple[LocalFilesystem, Path, Path]:
        """Provide a legacy MagFit step and real documentation with the V2 template's aliases."""
        template_dir = (
            Path(__file__).parents[1] / "ardupilot_methodic_configurator/vehicle_templates/ArduCopter/Holybro_X500_mig"
        )
        new_filename = "35_inflight_magnetometer_fit_setup.param"
        step = json.loads((template_dir / "configuration_steps_ArduCopter.json").read_text(encoding="utf-8"))["steps"][
            new_filename
        ]
        old_filename: str = request.param
        assert old_filename in step["old_filenames"]
        old_step = vehicle_dir / old_filename
        new_step = vehicle_dir / new_filename
        old_step.write_bytes((template_dir / new_filename).read_bytes())
        old_step.with_suffix(".pdef.xml").write_bytes((template_dir / new_step.with_suffix(".pdef.xml").name).read_bytes())
        filesystem = LocalFilesystem.__new__(LocalFilesystem)
        filesystem.vehicle_dir = str(vehicle_dir)
        filesystem.configuration_steps = {new_filename: step}
        return filesystem, old_step, new_step

    def test_user_keeps_magfit_parameter_documentation_after_step_rename(
        self, magfit_alias_project: tuple[LocalFilesystem, Path, Path]
    ) -> None:
        """
        MagFit documentation remains discoverable after a legacy step is renamed.

        GIVEN: A legacy MagFit step with its Lua parameter documentation
        WHEN: Filename aliases are applied and then applied again on reopening
        THEN: Both files use the V2 name, their bytes are unchanged, and the metadata can be loaded
        """
        filesystem, old_step, new_step = magfit_alias_project
        old_documentation = old_step.with_suffix(".pdef.xml")
        new_documentation = new_step.with_suffix(".pdef.xml")
        original_parameters = old_step.read_bytes()
        original_documentation = old_documentation.read_bytes()

        filesystem.rename_parameter_files()
        filesystem.rename_parameter_files()

        assert not old_step.exists()
        assert not old_documentation.exists()
        assert new_step.read_bytes() == original_parameters
        assert new_documentation.read_bytes() == original_documentation
        metadata = parse_parameter_metadata("", str(new_step.parent), new_documentation.name, "ArduCopter", 105)
        assert metadata["MAGH_LOG_ENABLE"]["humanName"] == "Enable MAGH.Active logging"
        assert metadata["MAGH_LOG_ENABLE"]["documentation"]

    def test_user_recovers_documentation_left_behind_by_an_earlier_step_rename(
        self, magfit_alias_project: tuple[LocalFilesystem, Path, Path]
    ) -> None:
        """
        Opening an already-renamed project repairs its orphaned documentation.

        GIVEN: The parameter file already has the V2 name but its sidecar still has the legacy name
        WHEN: The project's filename aliases are checked again
        THEN: The sidecar follows the existing step without changing parameter values
        """
        filesystem, old_step, new_step = magfit_alias_project
        old_documentation = old_step.with_suffix(".pdef.xml")
        original_documentation = old_documentation.read_bytes()
        old_step.rename(new_step)
        original_parameters = new_step.read_bytes()

        filesystem.rename_parameter_files()

        assert not old_documentation.exists()
        assert new_step.with_suffix(".pdef.xml").read_bytes() == original_documentation
        assert new_step.read_bytes() == original_parameters

    def test_user_legacy_step_replaces_an_empty_new_step_placeholder(
        self, magfit_alias_project: tuple[LocalFilesystem, Path, Path]
    ) -> None:
        """
        A non-empty legacy step replaces an empty destination placeholder.

        GIVEN: A legacy step with parameters and an empty file under the new name
        WHEN: Filename aliases are applied
        THEN: The legacy parameters and documentation move to the new names
        """
        filesystem, old_step, new_step = magfit_alias_project
        original_parameters = old_step.read_bytes()
        original_documentation = old_step.with_suffix(".pdef.xml").read_bytes()
        new_step.write_bytes(b"")

        filesystem.rename_parameter_files()

        assert not old_step.exists()
        assert new_step.read_bytes() == original_parameters
        assert not old_step.with_suffix(".pdef.xml").exists()
        assert new_step.with_suffix(".pdef.xml").read_bytes() == original_documentation

    @pytest.mark.parametrize("existing_content", [b"", b"<paramfile>user documentation</paramfile>\n"])
    def test_user_documentation_at_the_new_name_is_never_overwritten(
        self, magfit_alias_project: tuple[LocalFilesystem, Path, Path], existing_content: bytes
    ) -> None:
        """
        Destination documentation, including empty files, is preserved.

        GIVEN: Both legacy documentation and a destination sidecar already exist
        WHEN: The parameter step is renamed
        THEN: The parameters move but both documentation files retain their original contents
        """
        filesystem, old_step, new_step = magfit_alias_project
        old_documentation = old_step.with_suffix(".pdef.xml")
        new_documentation = new_step.with_suffix(".pdef.xml")
        original_documentation = old_documentation.read_bytes()
        original_parameters = old_step.read_bytes()
        new_documentation.write_bytes(existing_content)

        filesystem.rename_parameter_files()

        assert not old_step.exists()
        assert new_step.read_bytes() == original_parameters
        assert old_documentation.read_bytes() == original_documentation
        assert new_documentation.read_bytes() == existing_content

    def test_documentation_stays_with_a_legacy_step_when_parameter_rename_is_blocked(
        self, magfit_alias_project: tuple[LocalFilesystem, Path, Path]
    ) -> None:
        """
        A conflicting parameter destination does not detach the old step's documentation.

        GIVEN: Both the legacy and V2 parameter files exist
        WHEN: Filename alias renaming refuses to overwrite the V2 step
        THEN: Both parameter files and the legacy sidecar are unchanged
        """
        filesystem, old_step, new_step = magfit_alias_project
        old_documentation = old_step.with_suffix(".pdef.xml")
        original_parameters = old_step.read_bytes()
        original_documentation = old_documentation.read_bytes()
        new_step.write_bytes(b"MAGH_LOG_ENABLE,0\n")

        filesystem.rename_parameter_files()

        assert old_step.read_bytes() == original_parameters
        assert new_step.read_bytes() == b"MAGH_LOG_ENABLE,0\n"
        assert old_documentation.read_bytes() == original_documentation
        assert not new_step.with_suffix(".pdef.xml").exists()

    def test_step_without_optional_documentation_can_still_be_renamed(
        self, magfit_alias_project: tuple[LocalFilesystem, Path, Path]
    ) -> None:
        """
        Documentation is optional when renaming a step.

        GIVEN: A legacy parameter step has no sidecar
        WHEN: The step is renamed
        THEN: The parameters move successfully without creating a documentation file
        """
        filesystem, old_step, new_step = magfit_alias_project
        original_parameters = old_step.read_bytes()
        old_step.with_suffix(".pdef.xml").unlink()

        filesystem.rename_parameter_files()

        assert not old_step.exists()
        assert new_step.read_bytes() == original_parameters
        assert not new_step.with_suffix(".pdef.xml").exists()

    def test_orphaned_documentation_without_either_parameter_file_is_not_moved(
        self, magfit_alias_project: tuple[LocalFilesystem, Path, Path]
    ) -> None:
        """
        A standalone sidecar is not attached to a nonexistent configuration step.

        GIVEN: Legacy documentation exists but neither parameter filename exists
        WHEN: Filename aliases are checked
        THEN: The sidecar stays at its original path
        """
        filesystem, old_step, new_step = magfit_alias_project
        old_documentation = old_step.with_suffix(".pdef.xml")
        original_documentation = old_documentation.read_bytes()
        old_step.unlink()

        filesystem.rename_parameter_files()

        assert old_documentation.read_bytes() == original_documentation
        assert not new_step.exists()
        assert not new_step.with_suffix(".pdef.xml").exists()

    def test_user_can_retry_a_failed_documentation_rename_without_losing_parameters(
        self, magfit_alias_project: tuple[LocalFilesystem, Path, Path], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """
        A sidecar rename failure remains recoverable after the parameter rename completes.

        GIVEN: Storage rejects the documentation rename after the parameter file has moved
        WHEN: The user retries after the storage failure is resolved
        THEN: The retained documentation moves to the V2 name without changing the parameter file
        """
        filesystem, old_step, new_step = magfit_alias_project
        old_documentation = old_step.with_suffix(".pdef.xml")
        original_parameters = old_step.read_bytes()
        original_documentation = old_documentation.read_bytes()
        original_rename = filesystem_module.os_rename
        message = "Simulated sidecar rename failure"

        def interrupted_rename(source: str, destination: str) -> None:
            if Path(source) == old_documentation:
                raise OSError(message)
            original_rename(source, destination)

        with monkeypatch.context() as failure_patch:
            failure_patch.setattr(filesystem_module, "os_rename", interrupted_rename)
            with pytest.raises(OSError, match=message):
                filesystem.rename_parameter_files()

        assert not old_step.exists()
        assert new_step.read_bytes() == original_parameters
        assert old_documentation.read_bytes() == original_documentation
        assert not new_step.with_suffix(".pdef.xml").exists()
        filesystem.rename_parameter_files()
        assert not old_documentation.exists()
        assert new_step.with_suffix(".pdef.xml").read_bytes() == original_documentation
        assert new_step.read_bytes() == original_parameters


class TestV1ToV2ParameterExtractions:
    """Tests that consecutive format migrations are persisted as separate steps."""

    def test_user_keeps_manual_rate_filter_values_when_migrating_to_v2(self, vehicle_dir: Path) -> None:
        """
        Existing filter settings move unless a destination value already takes precedence.

        GIVEN: A V1 mandatory-hardware file with hand-set gyro and rate-filter values
        WHEN: The ArduCopter project migrates to V2
        THEN: Non-conflicting values move, the existing destination value remains, and hardware settings move
        """
        (vehicle_dir / "configuration_steps_ArduCopter.json").write_text(
            json.dumps(
                {
                    "steps": {
                        "29_motor_notch_filter_results.param": {
                            "old_filenames": ["25_motor_notch_filter_results.param"]
                        }
                    }
                }
            ),
            encoding="utf-8",
        )
        hardware = vehicle_dir / "14_mp_setup_mandatory_hardware.param"
        hardware.write_text(
            "INS_GYRO_FILTER,150 # hand-set\n"
            "ATC_RAT_PIT_FLTD,60\n"
            "ATC_RAT_PIT_FLTT,0\n"
            "ATC_RAT_RLL_FLTD,75\n"
            "ATC_RAT_RLL_FLTT,0\n"
            "ATC_RAT_YAW_FLTD,12\n"
            "ATC_RAT_YAW_FLTT,0\n"
            "COMPASS_EXTERNAL,1\n",
            encoding="utf-8",
        )
        legacy_results = vehicle_dir / "25_motor_notch_filter_results.param"
        legacy_results.write_text("INS_GYRO_FILTER,20\nINS_HNTCH_FREQ,42\n", encoding="utf-8")

        migration_module._migrate_v1_to_v2(vehicle_dir, "ArduCopter")  # pylint: disable=protected-access

        filters = legacy_results.read_text(encoding="utf-8")
        remaining_hardware = hardware.read_text(encoding="utf-8") if hardware.exists() else ""
        compass = (vehicle_dir / "19_compass_calibration.param").read_text(encoding="utf-8")
        assert "INS_GYRO_FILTER,20\n" in filters
        assert "INS_GYRO_FILTER,150 # hand-set\n" not in filters
        for parameter in (
            "ATC_RAT_PIT_FLTD,60",
            "ATC_RAT_PIT_FLTT,0",
            "ATC_RAT_RLL_FLTD,75",
            "ATC_RAT_RLL_FLTT,0",
            "ATC_RAT_YAW_FLTD,12",
            "ATC_RAT_YAW_FLTT,0",
        ):
            assert parameter in filters
            assert parameter not in remaining_hardware
        assert "INS_HNTCH_FREQ,42\n" in filters
        assert "COMPASS_EXTERNAL,1\n" in compass

    @pytest.mark.parametrize(
        "step_migration",
        [
            ("07_remote_controller_controller.param", "06_remote_controller_controller.param", "RC1_MIN"),
            ("11_initial_atc.param", "13_initial_atc.param", "ATC_ACC_P_MAX"),
            ("15_general_configuration.param", "23_general_configuration.param", "FLOW_TYPE"),
        ],
    )
    @pytest.mark.parametrize("configuration_location", ["project", "package"])
    def test_existing_v1_step_values_survive_parameter_splits_and_filename_renames(
        self,
        vehicle_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
        step_migration: tuple[str, str, str],
        configuration_location: str,
    ) -> None:
        """
        Splitting hardware values must not block renaming a customized V1 step.

        GIVEN: A V1 step with custom values and a hardware source with a conflicting value
        WHEN: The V2 split runs before the normal filename rename, then is retried
        THEN: The source value wins once while comments and unrelated user settings survive
        """
        old_filename, new_filename, moved_parameter = step_migration
        steps = {new_filename: {"old_filenames": [old_filename]}}
        configuration_dir = vehicle_dir
        if configuration_location == "package":
            configuration_dir = vehicle_dir / "package"
            configuration_dir.mkdir()
            monkeypatch.setattr(migration_module, "_PACKAGE_DIR", configuration_dir)
        (configuration_dir / "configuration_steps_ArduCopter.json").write_text(json.dumps({"steps": steps}), encoding="utf-8")
        old_step = vehicle_dir / old_filename
        old_step.write_text(f"# user settings\nUNRELATED_SETTING,23\n{moved_parameter},0\n", encoding="utf-8")
        hardware = vehicle_dir / "14_mp_setup_mandatory_hardware.param"
        hardware.write_text(f"{moved_parameter},17 # measured\n", encoding="utf-8")

        migration_module._migrate_v1_to_v2(vehicle_dir, "ArduCopter")  # pylint: disable=protected-access
        assert not (vehicle_dir / new_filename).exists()
        filesystem = LocalFilesystem.__new__(LocalFilesystem)
        filesystem.vehicle_dir = str(vehicle_dir)
        filesystem.configuration_steps = steps
        filesystem.rename_parameter_files()
        migrated = (vehicle_dir / new_filename).read_bytes()
        migration_module._migrate_v1_to_v2(vehicle_dir, "ArduCopter")  # pylint: disable=protected-access
        filesystem.rename_parameter_files()

        assert not old_step.exists()
        assert migrated == f"# user settings\nUNRELATED_SETTING,23\n{moved_parameter},17 # measured\n".encode()
        assert (vehicle_dir / new_filename).read_bytes() == migrated
        assert not hardware.exists()

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
            "16_accelerometer_calibration.param": "TEMPLATE_ACCEL,1\nINS_ACCSCAL_X,1\n",
            "17_accelerometer_level.param": "TEMPLATE_LEVEL,1\n",
            "19_compass_calibration.param": "TEMPLATE_COMPASS,1\n",
            "22_flight_modes.param": "INITIAL_MODE,0\n",
            "11_servo_outputs.param": "TEMPLATE_SERVO,1\nSERVO1_FUNCTION,0\nFRAME_CLASS,0\n",
        }
        for filename, content in template_values.items():
            (template_dir / filename).write_text(content, encoding="utf-8")

        (vehicle_dir / "configuration_steps_ArduCopter.json").write_text(
            json.dumps(
                {
                    "steps": {filename: {} for filename in template_values}
                    | {"15_board_orientation.param": {"old_filenames": ["05_board_orientation.param"]}}
                }
            ),
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
            "INS_ACCSCAL_X,0.998941\nINS_ACC1_CALTEMP,45\nAHRS_TRIM_X,0.01\nFLTMODE1,3\nINITIAL_MODE,1\n"
            "SERVO1_FUNCTION,33\nFRAME_CLASS,1\n",
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

        accelerometer = (vehicle_dir / "16_accelerometer_calibration.param").read_text(encoding="utf-8")
        imu_temperature = (vehicle_dir / "03_imu_temperature_calibration_results.param").read_text(encoding="utf-8")
        accelerometer_level = (vehicle_dir / "17_accelerometer_level.param").read_text(encoding="utf-8")
        flight_modes = (vehicle_dir / "22_flight_modes.param").read_text(encoding="utf-8")
        servo_outputs = (vehicle_dir / "11_servo_outputs.param").read_text(encoding="utf-8")

        assert "INS_ACC1_CALTEMP,45" in accelerometer
        assert "INS_ACC1_CALTEMP,45" in imu_temperature
        assert "AHRS_TRIM_X,0.01" in accelerometer
        assert "AHRS_TRIM_X,0.01" in accelerometer_level
        assert "INS_ACCSCAL_X,0.998941" in accelerometer
        assert "TEMPLATE_ACCEL,1" in accelerometer
        assert "TEMPLATE_TEMP,1" in imu_temperature
        assert "TEMPLATE_LEVEL,1" in accelerometer_level
        assert "TEMPLATE_COMPASS,1" in (vehicle_dir / "19_compass_calibration.param").read_text(encoding="utf-8")
        assert "INITIAL_MODE,1" in flight_modes
        assert flight_modes.count("INITIAL_MODE,") == 1
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
        assert frame_class_files == ["11_servo_outputs.param"]

    @pytest.mark.parametrize("failed_destination", ["16_accelerometer_calibration.param", "17_accelerometer_level.param"])
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
        assert (vehicle_dir / "16_accelerometer_calibration.param").read_text(encoding="utf-8") == (
            "INS_ACCSCAL_X,0.998941\nAHRS_TRIM_X,0.01\n"
        )
        assert (vehicle_dir / "17_accelerometer_level.param").read_text(encoding="utf-8") == "AHRS_TRIM_X,0.01\n"
        assert source.read_text(encoding="utf-8") == "UNRELATED_SOURCE,9\n"
        assert json.loads(components.read_text(encoding="utf-8"))["Format version"] == 2

    @pytest.mark.parametrize("failure_stage", ["write", "fsync", "replace"])
    @pytest.mark.parametrize(
        "failed_filename",
        [
            "16_accelerometer_calibration.param",
            "17_accelerometer_level.param",
            "23_general_configuration.param",
            "14_mp_setup_mandatory_hardware.param",
            "vehicle_components.json",
        ],
    )
    def test_user_can_retry_split_without_losing_existing_values_after_storage_failure(
        self, vehicle_dir: Path, monkeypatch: pytest.MonkeyPatch, failed_filename: str, failure_stage: str
    ) -> None:
        """
        Failed parameter or version writes preserve the previously published file.

        GIVEN: A format-1 project with source-only values and existing destination-only values
        WHEN: Writing, syncing or publishing a destination, source or version file fails, then migration is retried
        THEN: The failed file and version survive byte-for-byte, and retry preserves every unrelated value
        """
        components = vehicle_dir / "vehicle_components.json"
        components.write_text(
            json.dumps({"Format version": 1, "Components": {"Flight Controller": {"Firmware": {"Type": "ArduCopter"}}}}),
            encoding="utf-8",
        )
        source = vehicle_dir / "14_mp_setup_mandatory_hardware.param"
        accelerometer = vehicle_dir / "16_accelerometer_calibration.param"
        level = vehicle_dir / "17_accelerometer_level.param"
        general = vehicle_dir / "23_general_configuration.param"
        source.write_bytes(b"INS_ACCSCAL_X,0.998941\r\nAHRS_TRIM_X,0.01\r\nUNRELATED_SOURCE,9\r\n")
        accelerometer.write_bytes(b"# measured calibration\r\nUNRELATED_ACCEL,17\r\nINS_ACCSCAL_X,1\r\n")
        level.write_bytes(b"# keep level settings\r\nUNRELATED_LEVEL,23\r\nAHRS_TRIM_X,0\r\n")
        general.write_bytes(b"UNRELATED_GENERAL,31\r\n")
        originals = {path.name: path.read_bytes() for path in (components, source, accelerometer, level, general)}
        monkeypatch.setattr(migration_module, "VEHICLE_COMPONENTS_FORMAT_VERSION", 2)
        failed_file = vehicle_dir / failed_filename

        with monkeypatch.context() as failure:
            _interrupt_migration_write(failure, failed_file, failure_stage)
            with pytest.raises(OSError, match=f"simulated migration {failure_stage} failure"):
                migrate_vehicle_project_if_needed(str(vehicle_dir))

        assert failed_file.read_bytes() == originals[failed_filename]
        assert components.read_bytes() == originals[components.name]
        if failed_file in (accelerometer, level, general):
            assert source.read_bytes() == originals[source.name]
        assert not list(vehicle_dir.glob("*.tmp"))

        assert migrate_vehicle_project_if_needed(str(vehicle_dir)) is True

        assert accelerometer.read_bytes() == (
            b"# measured calibration\nUNRELATED_ACCEL,17\nINS_ACCSCAL_X,0.998941\nAHRS_TRIM_X,0.01\n"
        )
        assert level.read_bytes() == b"# keep level settings\nUNRELATED_LEVEL,23\nAHRS_TRIM_X,0.01\n"
        assert source.read_bytes() == b"UNRELATED_SOURCE,9\n"
        assert general.read_bytes() == b"UNRELATED_GENERAL,31\nUNRELATED_SOURCE,9\n"
        assert json.loads(components.read_bytes())["Format version"] == 2
        assert components.read_bytes().endswith(b"\n")
        assert b"\r" not in components.read_bytes()
        assert migrate_vehicle_project_if_needed(str(vehicle_dir)) is False
        assert not list(vehicle_dir.glob("*.tmp"))

    def test_project_calibration_overrides_destination_defaults_without_duplicates(self, vehicle_dir: Path) -> None:
        """
        Project calibration values replace conflicting defaults while preserving unrelated settings.

        GIVEN: A mandatory-hardware source and an existing calibration destination with conflicting values
        WHEN: The format-2 split is applied and retried
        THEN: The source values win once and unrelated destination values and comments survive
        """
        source = vehicle_dir / "14_mp_setup_mandatory_hardware.param"
        source.write_text("INS_ACCSCAL_X,0.998941 # measured\nINS_USE,1\nUNRELATED_SOURCE,9\n", encoding="utf-8")
        destination = vehicle_dir / "16_accelerometer_calibration.param"
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
            "16_accelerometer_calibration.param": ("INS_ACCSCAL_X,0.998941\nINS_ACC1_CALTEMP,45\nAHRS_TRIM_X,0.01\n"),
            "03_imu_temperature_calibration_results.param": "INS_ACC1_CALTEMP,45\n",
            "17_accelerometer_level.param": "AHRS_TRIM_X,0.01\n",
            "19_compass_calibration.param": "COMPASS_OFS_X,12\n",
            "22_flight_modes.param": "FLTMODE1,0\n",
            "06_remote_controller_controller.param": "RC1_MIN,1100\n",
            "11_servo_outputs.param": "SERVO1_FUNCTION,33\nFRAME_CLASS,1\n",
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
        assert "INS_ACCSCAL_X,0.998941" in (vehicle_dir / "16_accelerometer_calibration.param").read_text(encoding="utf-8")
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


class TestVehicleSpecificV1ToV2Migration:
    """Each vehicle keeps calibration values and moves settings within its own layout."""

    @pytest.mark.parametrize(
        ("vehicle_type", "source_name"),
        [
            (vehicle, source)
            for vehicle in ("ArduPlane", "Heli", "Rover")
            for source in (
                "11_mp_setup_mandatory_hardware.param",
                "12_mp_setup_mandatory_hardware.param",
                "14_mp_setup_mandatory_hardware.param",
            )
        ]
        + [("Heli", "15_mp_setup_mandatory_hardware.param")],
    )
    def test_user_keeps_calibration_and_safety_values_in_vehicle_specific_steps(
        self, vehicle_dir: Path, monkeypatch: pytest.MonkeyPatch, vehicle_type: str, source_name: str
    ) -> None:
        """
        Non-Copter conversions retain calibration and preserve settings in existing steps.

        GIVEN: A format-1 vehicle with measured calibration, RC, mode and fence values
        WHEN: It migrates to format 2 and migration is retried
        THEN: Valid settings move to that vehicle's steps without creating Copter-only files or losing values
        """
        mode_name = "MODE1" if vehicle_type == "Rover" else "FLTMODE1"
        retained_lines = [
            "AHRS_TRIM_X,0.012 # measured level\n",
            "INS_ACCSCAL_X,0.998 # measured accelerometer\n",
            "COMPASS_OFS_X,12 # measured compass\n",
            "SERVO1_FUNCTION,73 # configured output\n",
            "INS_GYRO_FILTER,20\n",
            f"{'FLTMODE1' if vehicle_type == 'Rover' else 'MODE1'},99 # unrelated legacy value\n",
        ]
        if vehicle_type == "Rover":
            retained_lines.append("FENCE_ALT_MAX,80 # legacy altitude setting\n")
        elif vehicle_type == "ArduPlane":
            retained_lines.append("Q_M_THST_HOVER,0.32 # quadplane setting\n")
        else:
            retained_lines.append("H_RSC_MODE,3 # helicopter rotor control\n")
        moved = {
            "03_imu_temperature_calibration_results.param": "INS_ACC1_CALTEMP,45 # measured temperature\n",
            "07_remote_controller_controller.param": "RC1_MIN,1100 # measured RC\nRC2_REVERSED,1\n",
            "15_general_configuration.param": f"{mode_name},3 # selected mode\nINITIAL_MODE,1\n",
            "16_safety_setup.param": "FENCE_ACTION,1\nFENCE_ENABLE,1\nFENCE_RADIUS,150 # project fence\n",
        }
        if vehicle_type != "Rover":
            moved["16_safety_setup.param"] += "FENCE_ALT_MAX,80 # altitude fence\n"
        source = vehicle_dir / source_name
        source.write_text("".join(retained_lines) + "".join(moved.values()), encoding="utf-8")
        (vehicle_dir / "16_safety_setup.param").write_text(
            "# retained safety comment\nFENCE_RADIUS,300\nARMING_CHECK,1\n", encoding="utf-8"
        )
        components = vehicle_dir / "vehicle_components.json"
        components.write_text(
            json.dumps({"Format version": 1, "Components": {"Flight Controller": {"Firmware": {"Type": vehicle_type}}}}),
            encoding="utf-8",
        )
        monkeypatch.setattr(migration_module, "VEHICLE_COMPONENTS_FORMAT_VERSION", 2)

        assert migrate_vehicle_project_if_needed(str(vehicle_dir)) is True

        assert source.read_text(encoding="utf-8") == "".join(retained_lines)
        for filename, content in moved.items():
            expected = "# retained safety comment\nARMING_CHECK,1\n" if filename == "16_safety_setup.param" else ""
            assert (vehicle_dir / filename).read_text(encoding="utf-8") == expected + content
        layout_path = (
            Path(__file__).parents[1] / "ardupilot_methodic_configurator" / f"configuration_steps_{vehicle_type}.json"
        )
        assert {path.name for path in vehicle_dir.glob("*.param")} - {source_name} <= set(
            json.loads(layout_path.read_text(encoding="utf-8"))["steps"]
        )
        assert json.loads(components.read_bytes())["Format version"] == 2
        before_retry = {path.name: path.read_bytes() for path in vehicle_dir.iterdir()}
        assert migrate_vehicle_project_if_needed(str(vehicle_dir)) is False
        assert {path.name: path.read_bytes() for path in vehicle_dir.iterdir()} == before_retry

    def test_user_can_open_retained_calibration_from_historical_heli_step(self, vehicle_dir: Path) -> None:
        """
        Heli's historical hardware step remains reachable after the conversion and filename rename.

        GIVEN: The OMP_M4 hardware filename with measured calibration and fence settings
        WHEN: Heli conversion runs before the usual project filename renames
        THEN: Calibration reaches the active hardware step and the fence reaches the safety step
        """
        source = vehicle_dir / "15_mp_setup_mandatory_hardware.param"
        source.write_text("INS_ACCSCAL_X,0.998\nFENCE_RADIUS,150\n", encoding="utf-8")

        migration_module._migrate_v1_to_v2(vehicle_dir, "Heli")  # pylint: disable=protected-access
        filesystem = LocalFilesystem.__new__(LocalFilesystem)
        filesystem.vehicle_dir = str(vehicle_dir)
        configuration = Path(__file__).parents[1] / "ardupilot_methodic_configurator" / "configuration_steps_Heli.json"
        filesystem.configuration_steps = json.loads(configuration.read_text(encoding="utf-8"))["steps"]
        filesystem.rename_parameter_files()

        assert not source.exists()
        assert (vehicle_dir / "14_mp_setup_mandatory_hardware.param").read_text(encoding="utf-8") == "INS_ACCSCAL_X,0.998\n"
        assert (vehicle_dir / "16_safety_setup.param").read_text(encoding="utf-8") == "FENCE_RADIUS,150\n"

    @pytest.mark.parametrize(
        ("vehicle_type", "template_name"),
        [
            ("ArduPlane", "normal_plane"),
            ("Rover", "AION_R1"),
            ("Rover", "Carisma_SCA-1E"),
            ("Heli", "OMP_M4"),
        ],
    )
    def test_existing_vehicle_templates_keep_all_parameter_values_in_their_layout(
        self, vehicle_dir: Path, monkeypatch: pytest.MonkeyPatch, vehicle_type: str, template_name: str
    ) -> None:
        """
        Real Plane, Rover and Heli projects do not acquire Copter-only calibration files.

        GIVEN: Numbered parameter files from an existing vehicle template at format 1
        WHEN: Migration to format 2 runs against the vehicle's own configuration steps
        THEN: Every original parameter line survives and every newly created file is an active step
        """
        package = Path(__file__).parents[1] / "ardupilot_methodic_configurator"
        template = package / "vehicle_templates" / vehicle_type / template_name
        for source in template.glob("[0-9][0-9]_*.param"):
            copyfile(source, vehicle_dir / source.name)
        copyfile(template / "vehicle_components.json", vehicle_dir / "vehicle_components.json")
        originals = {path.name for path in vehicle_dir.glob("*.param")}
        original_lines = {
            line
            for path in vehicle_dir.glob("*.param")
            if path.name != "00_default.param"
            for line in path.read_text(encoding="utf-8-sig").splitlines()
            if _param_name_from_line(line)
        }
        monkeypatch.setattr(migration_module, "VEHICLE_COMPONENTS_FORMAT_VERSION", 2)

        assert migrate_vehicle_project_if_needed(str(vehicle_dir)) is True

        resulting_files = {path.name for path in vehicle_dir.glob("*.param")}
        steps = json.loads((package / f"configuration_steps_{vehicle_type}.json").read_text(encoding="utf-8"))["steps"]
        assert resulting_files - originals <= set(steps)
        resulting_lines = {
            line
            for path in vehicle_dir.glob("*.param")
            if path.name != "00_default.param"
            for line in path.read_text(encoding="utf-8-sig").splitlines()
            if _param_name_from_line(line)
        }
        assert original_lines <= resulting_lines
        safety = (vehicle_dir / "16_safety_setup.param").read_text(encoding="utf-8")
        assert "FENCE_ACTION,1" in safety
        assert "FENCE_RADIUS,300" in safety
        assert migrate_vehicle_project_if_needed(str(vehicle_dir)) is False

    @pytest.mark.parametrize(
        ("vehicle_type", "template_name", "layout_template"),
        [
            ("ArduCopter", "Holybro_X500", "Holybro_X500_mig"),
            ("ArduCopter", "Holybro_X500", "empty_4.6.x_mig"),
            ("ArduPlane", "normal_plane", ""),
            ("Heli", "OMP_M4", ""),
            ("Rover", "AION_R1", ""),
        ],
    )
    def test_conversion_rules_target_existing_steps_and_vehicle_parameter_names(  # pylint: disable=too-many-locals
        self, vehicle_type: str, template_name: str, layout_template: str
    ) -> None:
        """
        Migration rules refer to supported parameter names and the matching vehicle layout.

        GIVEN: Each vehicle's default parameter set and destination configuration steps
        WHEN: Its move, copy and deletion rules are inspected
        THEN: Every destination is an active step and every pattern matches a parameter for that vehicle
        """
        package = Path(__file__).parents[1] / "ardupilot_methodic_configurator"
        templates = package / "vehicle_templates" / vehicle_type
        defaults = {
            _param_name_from_line(line)
            for line in (templates / template_name / "00_default.param").read_text(encoding="utf-8-sig").splitlines()
            if _param_name_from_line(line)
        }
        if vehicle_type == "ArduCopter":
            # Firmware 4.7 renames and optional IMU subgroups are not present in
            # the X500's three-IMU 4.6 default export.
            defaults.update(
                _param_name_from_line(line)
                for line in (templates / "empty_4.7.x" / "00_default.param").read_text(encoding="utf-8-sig").splitlines()
                if _param_name_from_line(line)
            )
            defaults.update(
                f"INS{imu}_{suffix}" for imu in (4, 5) for suffix in ("USE", "ACC_CALTEMP", "ACCOFFS_X", "ACCSCAL_X")
            )
        configuration = (
            templates / layout_template if layout_template else package
        ) / f"configuration_steps_{vehicle_type}.json"
        steps = json.loads(configuration.read_text(encoding="utf-8"))["steps"]
        moves = migration_module._PARAM_MOVES_V1_TO_V2  # pylint: disable=protected-access
        copies = migration_module._PARAM_COPIES_V1_TO_V2  # pylint: disable=protected-access
        deletes = migration_module._PARAM_DELETES_V1_TO_V2  # pylint: disable=protected-access
        assert not moves["all"]
        assert not copies["all"]
        assert not deletes["all"]
        assert moves[vehicle_type]
        for _source, destination, patterns, _force in moves[vehicle_type]:
            assert destination in steps
            for pattern in patterns:
                assert any(_line_matches_any(name, [pattern]) for name in defaults), pattern
        for _source, moved_destination, destination, patterns in copies[vehicle_type]:
            assert moved_destination in steps
            assert destination in steps
            for pattern in patterns:
                assert any(_line_matches_any(name, [pattern]) for name in defaults), pattern
        for _source, patterns in deletes[vehicle_type]:
            for pattern in patterns:
                assert any(_line_matches_any(name, [pattern]) for name in defaults), pattern

    @pytest.mark.parametrize("vehicle_type", ["", "UnknownVehicle"])
    def test_unknown_vehicle_does_not_apply_another_vehicles_conversion(self, vehicle_dir: Path, vehicle_type: str) -> None:
        """
        Unknown vehicle types cannot silently receive Copter-specific conversions.

        GIVEN: An unrecognized vehicle with calibration, mode and fence parameters
        WHEN: The v1-to-v2 conversion is requested
        THEN: Its parameter file is byte-for-byte unchanged and no new files appear
        """
        source = vehicle_dir / "14_mp_setup_mandatory_hardware.param"
        original = b"INS_ACCSCAL_X,0.998\r\nFLTMODE1,3\r\nFENCE_ACTION,1\r\n"
        source.write_bytes(original)

        deleted = migration_module._migrate_v1_to_v2(vehicle_dir, vehicle_type)  # pylint: disable=protected-access

        assert deleted == set()
        assert source.read_bytes() == original
        assert list(vehicle_dir.iterdir()) == [source]


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
        assert "INS_ACCSCAL_X,0.998941" in (vehicle_dir / "16_accelerometer_calibration.param").read_text(encoding="utf-8")


class TestMissingConfigurationStepFileRestore:
    """Tests restoration of configuration-step files absent from old projects."""

    @pytest.fixture(
        params=[(number, None) for number in sorted({errno.EPERM, errno.ENOTSUP, errno.EOPNOTSUPP, errno.ENOSYS, errno.EXDEV})]
        + [(errno.EINVAL, 1), (errno.EINVAL, 50)]
    )
    def filesystem_without_hard_links(self, monkeypatch: pytest.MonkeyPatch, request: pytest.FixtureRequest) -> None:
        """Simulate a writable filesystem that cannot publish hard links."""
        error_number, windows_error = request.param

        def unavailable_link(_source: Path, _destination: Path) -> None:
            error = OSError(error_number, "Hard links unavailable on this filesystem")
            if windows_error is not None:
                error.winerror = windows_error
            raise error

        monkeypatch.setattr(migration_module, "os_link", unavailable_link)

    @pytest.fixture
    def project_with_missing_step(self, vehicle_dir: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
        """Provide an old project with one missing step and an isolated matching template."""
        template_dir = vehicle_dir / "template"
        template_dir.mkdir()
        (template_dir / "99_restored.param").write_bytes(
            b"\xef\xbb\xbfRESTORED_PARAM,42 # retained comment\r\nANOTHER_PARAM,7\r\n"
        )
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
            staticmethod(lambda *_args: str(template_dir)),
        )
        return template_dir / "99_restored.param"

    @pytest.mark.usefixtures("filesystem_without_hard_links")
    def test_user_can_open_and_reopen_project_without_hard_link_support(
        self, vehicle_dir: Path, project_with_missing_step: Path
    ) -> None:
        """
        Migration succeeds on filesystems without hard-link support.

        GIVEN: A writable project filesystem rejects hard links and one configuration step is missing
        WHEN: The user opens the project and then opens it again
        THEN: The complete step is restored once, migration is finalized, and no temporary files remain
        """
        destination = vehicle_dir / project_with_missing_step.name
        original_template = project_with_missing_step.read_bytes()
        components = vehicle_dir / "vehicle_components.json"

        assert migrate_vehicle_project_if_needed(str(vehicle_dir)) is True
        assert destination.read_bytes() == original_template
        assert project_with_missing_step.read_bytes() == original_template
        migrated_components = components.read_bytes()
        assert json.loads(migrated_components)["Format version"] == VEHICLE_COMPONENTS_FORMAT_VERSION
        assert migrate_vehicle_project_if_needed(str(vehicle_dir)) is False
        assert components.read_bytes() == migrated_components
        assert destination.read_bytes() == original_template
        assert not list(vehicle_dir.glob("*.tmp"))

    @pytest.mark.parametrize("content", [b"", b"USER_VALUE,17\n"])
    @pytest.mark.usefixtures("filesystem_without_hard_links")
    def test_restore_without_hard_links_preserves_competing_project_file(
        self,
        vehicle_dir: Path,
        project_with_missing_step: Path,
        monkeypatch: pytest.MonkeyPatch,
        content: bytes,
    ) -> None:
        """
        A fallback restoration cannot overwrite a file another writer creates.

        GIVEN: Hard links are unavailable and a step is initially missing
        WHEN: Another writer creates that step before the fallback copy starts
        THEN: Its contents, including an empty file, are preserved and migration completes
        """
        destination = vehicle_dir / project_with_missing_step.name
        unavailable_link = migration_module.os_link

        def competing_link(source: Path, target: Path) -> None:
            target.write_bytes(content)
            unavailable_link(source, target)

        monkeypatch.setattr(migration_module, "os_link", competing_link)

        assert migrate_vehicle_project_if_needed(str(vehicle_dir)) is True
        assert destination.read_bytes() == content
        assert not list(vehicle_dir.glob("*.tmp"))

    @pytest.mark.parametrize("failure_stage", ["copy", "fsync"])
    @pytest.mark.usefixtures("filesystem_without_hard_links")
    def test_user_can_retry_interrupted_restore_without_hard_links(
        self,
        vehicle_dir: Path,
        project_with_missing_step: Path,
        monkeypatch: pytest.MonkeyPatch,
        failure_stage: str,
    ) -> None:
        """
        A failed fallback copy leaves the project ready for a complete retry.

        GIVEN: Hard links are unavailable and the fallback copy or flush fails
        WHEN: The user opens the project again after the storage failure is resolved
        THEN: No partial step survives the failure and every template byte is restored on retry
        """
        destination = vehicle_dir / project_with_missing_step.name
        components = vehicle_dir / "vehicle_components.json"
        original_components = components.read_bytes()
        original_template = project_with_missing_step.read_bytes()
        original_fsync = migration_module.fsync
        message = f"Simulated fallback {failure_stage} failure"

        def interrupted_copy(source: BinaryIO, target: BinaryIO) -> None:
            target.write(source.read(10))
            raise OSError(message)

        def interrupted_fsync(descriptor: int) -> None:
            if destination.exists():
                raise OSError(message)
            original_fsync(descriptor)

        with monkeypatch.context() as failure_patch:
            if failure_stage == "copy":
                failure_patch.setattr(migration_module, "copyfileobj", interrupted_copy)
            else:
                failure_patch.setattr(migration_module, "fsync", interrupted_fsync)
            with pytest.raises(OSError, match=message):
                migrate_vehicle_project_if_needed(str(vehicle_dir))

        assert components.read_bytes() == original_components
        assert not destination.exists()
        assert not list(vehicle_dir.glob("*.tmp"))
        assert project_with_missing_step.read_bytes() == original_template
        assert migrate_vehicle_project_if_needed(str(vehicle_dir)) is True
        assert destination.read_bytes() == original_template
        assert not list(vehicle_dir.glob("*.tmp"))

    def test_restored_step_requests_normal_project_file_permissions(
        self, vehicle_dir: Path, project_with_missing_step: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """
        Restored steps must not inherit a private temporary file's owner-only mode.

        GIVEN: An old project with a missing step from its firmware template
        WHEN: Migration creates a temporary copy for that step
        THEN: It requests normal file permissions and lets the OS apply umask and inherited ACLs
        """
        original_open = os.open
        requested_modes: list[int] = []

        def record_creation_mode(path: str | Path, flags: int, mode: int = 0o777, *, dir_fd: int | None = None) -> int:
            if Path(path).parent == vehicle_dir and flags & os.O_CREAT:
                requested_modes.append(mode)
            return original_open(path, flags, mode, dir_fd=dir_fd)

        monkeypatch.setattr(migration_module, "os_open", record_creation_mode)

        assert migrate_vehicle_project_if_needed(str(vehicle_dir)) is True

        assert requested_modes == [0o666]
        assert (vehicle_dir / project_with_missing_step.name).read_bytes() == project_with_missing_step.read_bytes()
        assert not list(vehicle_dir.glob("*.tmp"))

    @pytest.mark.skipif(os.name != "posix", reason="POSIX permission bits are not meaningful on Windows")
    @pytest.mark.parametrize("creation_umask", [0o022, 0o002, 0o027, 0o077], ids=["standard", "shared", "group", "private"])
    def test_restored_step_matches_normal_file_permissions_under_umask(
        self, vehicle_dir: Path, project_with_missing_step: Path, creation_umask: int
    ) -> None:
        """
        Restoration respects shared and private project permission policies.

        GIVEN: A read-only template and a process with a specific file-creation umask
        WHEN: A missing step and a normal comparison file are created in that process
        THEN: Both files have the same umask-derived permissions, without inheriting the template's mode
        """
        destination = vehicle_dir / project_with_missing_step.name
        comparison = vehicle_dir / "normal_creation.param"
        project_with_missing_step.chmod(0o400)
        # Isolate the umask change from the pytest process and any background threads.
        script = """
import os
import sys
from pathlib import Path
from ardupilot_methodic_configurator.backend_filesystem_migration import _copy_configuration_step_file

os.umask(int(sys.argv[4]))
Path(sys.argv[3]).write_bytes(b"normal file")
_copy_configuration_step_file(Path(sys.argv[1]), Path(sys.argv[2]))
"""
        subprocess.run(  # noqa: S603
            [
                sys.executable,
                "-c",
                script,
                str(project_with_missing_step),
                str(destination),
                str(comparison),
                str(creation_umask),
            ],
            check=True,
            cwd=Path(__file__).parents[1],
        )

        assert S_IMODE(destination.stat().st_mode) == S_IMODE(comparison.stat().st_mode) == 0o666 & ~creation_umask
        assert S_IMODE(project_with_missing_step.stat().st_mode) == 0o400
        assert destination.read_bytes() == project_with_missing_step.read_bytes()
        assert not list(vehicle_dir.glob("*.tmp"))

    def test_temporary_name_collision_preserves_the_existing_file(
        self, vehicle_dir: Path, project_with_missing_step: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """
        An occupied temporary filename must not be overwritten or removed.

        GIVEN: A file already exists at the proposed temporary-copy path
        WHEN: Migration attempts to create that temporary file, then retries with a new name
        THEN: The occupied file is preserved and the retry restores the missing step
        """
        occupied = vehicle_dir / ".migration-occupied.tmp"
        occupied.write_bytes(b"unrelated file")
        destination = vehicle_dir / project_with_missing_step.name
        components = vehicle_dir / "vehicle_components.json"
        original_components = components.read_bytes()

        with monkeypatch.context() as collision_patch:
            collision_patch.setattr(migration_module, "token_hex", lambda *_args: "occupied")
            with pytest.raises(FileExistsError):
                migrate_vehicle_project_if_needed(str(vehicle_dir))

        assert occupied.read_bytes() == b"unrelated file"
        assert components.read_bytes() == original_components
        assert not destination.exists()

        assert migrate_vehicle_project_if_needed(str(vehicle_dir)) is True
        assert destination.read_bytes() == project_with_missing_step.read_bytes()
        assert occupied.read_bytes() == b"unrelated file"
        assert list(vehicle_dir.glob("*.tmp")) == [occupied]

    def test_user_can_retry_migration_after_an_interrupted_template_copy(
        self, vehicle_dir: Path, project_with_missing_step: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """
        A failed restoration must not publish a partial configuration step.

        GIVEN: An old project is missing a step from its matching firmware template
        WHEN: Copying that step fails after writing some bytes, then migration is retried
        THEN: The failed copy leaves no destination or temporary file and retry restores every byte
        """
        destination = vehicle_dir / project_with_missing_step.name
        components = vehicle_dir / "vehicle_components.json"
        original_components = components.read_bytes()
        original_template = project_with_missing_step.read_bytes()

        def interrupted_copy(source: Path, target: Path) -> None:
            Path(target).write_bytes(Path(source).read_bytes()[:10])
            message = "Simulated interrupted template copy"
            raise OSError(message)

        with monkeypatch.context() as failure_patch:
            failure_patch.setattr(migration_module, "copyfile", interrupted_copy)
            with pytest.raises(OSError, match="Simulated interrupted template copy"):
                migrate_vehicle_project_if_needed(str(vehicle_dir))

        assert components.read_bytes() == original_components
        assert not destination.exists()
        assert not list(vehicle_dir.glob("*.tmp"))
        assert project_with_missing_step.read_bytes() == original_template

        assert migrate_vehicle_project_if_needed(str(vehicle_dir)) is True
        assert destination.read_bytes() == original_template
        assert json.loads(components.read_text(encoding="utf-8"))["Format version"] == VEHICLE_COMPONENTS_FORMAT_VERSION
        assert not list(vehicle_dir.glob("*.tmp"))

    def test_user_can_retry_migration_when_restored_step_cannot_be_published(
        self, vehicle_dir: Path, project_with_missing_step: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """
        Publishing a restored step happens only after its complete contents have been copied.

        GIVEN: An old project with a missing step and a complete firmware template
        WHEN: The completed temporary copy cannot replace the destination
        THEN: Migration remains pending, the temporary file is cleaned up, and retry succeeds
        """
        destination = vehicle_dir / project_with_missing_step.name
        components = vehicle_dir / "vehicle_components.json"
        original_components = components.read_bytes()
        original_template = project_with_missing_step.read_bytes()

        def failed_publish(temporary: Path, target: Path) -> None:
            assert temporary.parent == destination.parent
            assert temporary.read_bytes() == original_template
            assert target == destination
            assert not destination.exists()
            message = "Simulated publication failure"
            raise OSError(message)

        with monkeypatch.context() as failure_patch:
            failure_patch.setattr(migration_module, "os_link", failed_publish)
            with pytest.raises(OSError, match="Simulated publication failure"):
                migrate_vehicle_project_if_needed(str(vehicle_dir))

        assert components.read_bytes() == original_components
        assert not destination.exists()
        assert not list(vehicle_dir.glob("*.tmp"))
        assert migrate_vehicle_project_if_needed(str(vehicle_dir)) is True
        assert destination.read_bytes() == original_template
        assert not list(vehicle_dir.glob("*.tmp"))

    def test_restored_step_is_not_visible_until_template_copy_completes(
        self, vehicle_dir: Path, project_with_missing_step: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """
        Readers must not observe an incomplete restored step.

        GIVEN: An old project with a missing configuration step
        WHEN: Its firmware template is copied successfully
        THEN: The destination remains absent throughout copying and appears with unchanged bytes afterwards
        """
        destination = vehicle_dir / project_with_missing_step.name

        def observed_copy(source: Path, target: Path) -> None:
            assert not destination.exists()
            copyfile(source, target)
            assert not destination.exists()

        monkeypatch.setattr(migration_module, "copyfile", observed_copy)

        assert migrate_vehicle_project_if_needed(str(vehicle_dir)) is True

        assert destination.read_bytes() == project_with_missing_step.read_bytes()
        assert not list(vehicle_dir.glob("*.tmp"))

    @pytest.mark.parametrize("content", [b"", b"USER_VALUE,17\n"])
    def test_restore_preserves_file_created_while_template_is_being_copied(
        self, vehicle_dir: Path, project_with_missing_step: Path, monkeypatch: pytest.MonkeyPatch, content: bytes
    ) -> None:
        """
        Preserve competing writes during restoration.

        GIVEN: Another writer creates a previously missing step during restoration
        WHEN: The complete template copy is published
        THEN: Even an empty competing file is preserved and temporary files are removed
        """
        destination = vehicle_dir / project_with_missing_step.name

        def competing_copy(source: Path, target: Path) -> None:
            copyfile(source, target)
            destination.write_bytes(content)

        monkeypatch.setattr(migration_module, "copyfile", competing_copy)
        assert migrate_vehicle_project_if_needed(str(vehicle_dir)) is True
        assert destination.read_bytes() == content
        assert not list(vehicle_dir.glob("*.tmp"))

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


@pytest.mark.parametrize("hardware_filename", ["14_mp_setup_mandatory_hardware.param", "11_mp_setup_mandatory_hardware.param"])
def test_user_can_review_unmapped_hardware_settings_in_simple_mode(
    tmp_path: Path, caplog: pytest.LogCaptureFixture, hardware_filename: str
) -> None:
    """
    Keep hardware settings visible after migration.

    GIVEN: Hardware settings include rangefinder, flow, 4.7 acceleration and unknown parameters
    WHEN: The Copter hardware step is split
    THEN: Known values reach active steps and unknown values remain recoverable and visible with a warning
    """
    source = tmp_path / hardware_filename
    source.write_text(
        "FLOW_TYPE,1\nRNGFND1_TYPE,10\nATC_ACC_P_MAX,72\nATC_ACC_R_MAX,73\nATC_ACC_Y_MAX,74\n"
        "UNMAPPED_SETTING,17 # user reason\n",
        encoding="utf-8",
    )
    general = tmp_path / "23_general_configuration.param"
    general.write_text("UNRELATED_GENERAL,23\nFLOW_TYPE,0\n", encoding="utf-8")

    migration_module._migrate_v1_to_v2(tmp_path, "ArduCopter")  # pylint: disable=protected-access
    assert source.read_text(encoding="utf-8") == "UNMAPPED_SETTING,17 # user reason\n"
    contents = general.read_text(encoding="utf-8")
    assert "FLOW_TYPE,1\n" in contents
    assert "RNGFND1_TYPE,10\n" in contents
    assert "UNRELATED_GENERAL,23\n" in contents
    assert "UNMAPPED_SETTING,17 # user reason\n" in contents
    assert "UNMAPPED_SETTING" in caplog.text
    atc = ParDict.load_param_file_into_dict(str(tmp_path / "13_initial_atc.param"))
    assert {name: param.value for name, param in atc.items()} == {
        "ATC_ACC_P_MAX": 72,
        "ATC_ACC_R_MAX": 73,
        "ATC_ACC_Y_MAX": 74,
    }
    layout = Path(__file__).parents[1] / (
        "ardupilot_methodic_configurator/vehicle_templates/ArduCopter/Holybro_X500_mig/configuration_steps_ArduCopter.json"
    )
    step = json.loads(layout.read_text(encoding="utf-8"))["steps"][general.name]
    assert int(step["mandatory_text"].split("%")[0]) > 20
    migration_module._migrate_v1_to_v2(tmp_path, "ArduCopter")  # pylint: disable=protected-access
    assert general.read_text(encoding="utf-8") == contents


def test_user_keeps_fourth_and_fifth_imu_calibration_values(tmp_path: Path) -> None:
    """
    Preserve calibration of optional IMU subgroups.

    GIVEN: Calibration values use the Copter-4.6.3 IMU 4_/5_ subgroup names
    WHEN: The hardware step is split
    THEN: Offsets, scales and use flags reach calibration, with temperatures also retained in the temperature step
    """
    values = {
        f"INS{imu}_{suffix}": index + 1
        for imu in (4, 5)
        for index, suffix in enumerate(
            ("USE", "ACCOFFS_X", "ACCOFFS_Y", "ACCOFFS_Z", "ACCSCAL_X", "ACCSCAL_Y", "ACCSCAL_Z", "ACC_CALTEMP")
        )
    }
    (tmp_path / "14_mp_setup_mandatory_hardware.param").write_text(
        "".join(f"{name},{value}\n" for name, value in values.items()), encoding="utf-8"
    )
    migration_module._migrate_v1_to_v2(tmp_path, "ArduCopter")  # pylint: disable=protected-access
    calibration = ParDict.load_param_file_into_dict(str(tmp_path / "16_accelerometer_calibration.param"))
    temperatures = ParDict.load_param_file_into_dict(str(tmp_path / "03_imu_temperature_calibration_results.param"))
    assert {name: param.value for name, param in calibration.items()} == values
    assert {name: param.value for name, param in temperatures.items()} == {
        name: value for name, value in values.items() if name.endswith("CALTEMP")
    }
    assert not (tmp_path / "14_mp_setup_mandatory_hardware.param").exists()


@pytest.mark.parametrize("template_name", ["TarotFY680Hexacopter", "empty_4.7.x"])
def test_existing_copter_projects_keep_extra_hardware_values_in_active_steps(tmp_path: Path, template_name: str) -> None:
    """
    Preserve hardware settings from real projects with additional sensors or newer firmware.

    GIVEN: A Tarot or Copter 4.7 template has hardware values outside the original split rules
    WHEN: Its mandatory-hardware file is converted to the split layout
    THEN: Rangefinder, optical flow and renamed acceleration values survive in active configuration steps
    """
    package = Path(__file__).parents[1] / "ardupilot_methodic_configurator"
    template = package / "vehicle_templates" / "ArduCopter" / template_name
    hardware = next(template.glob("*_mp_setup_mandatory_hardware.param"))
    copyfile(hardware, tmp_path / hardware.name)
    original = ParDict.load_param_file_into_dict(str(hardware))
    expected = {
        name: param.value for name, param in original.items() if name.startswith(("RNGFND", "ATC_ACC_")) or name == "FLOW_TYPE"
    }
    assert expected
    migration_module._migrate_v1_to_v2(tmp_path, "ArduCopter")  # pylint: disable=protected-access
    layout = package / "vehicle_templates/ArduCopter/Holybro_X500_mig/configuration_steps_ArduCopter.json"
    steps = json.loads(layout.read_text(encoding="utf-8"))["steps"]
    visible_values = {
        name: param.value
        for filename in steps
        if (tmp_path / filename).is_file() and int(steps[filename]["mandatory_text"].split("%")[0]) > 20
        for name, param in ParDict.load_param_file_into_dict(str(tmp_path / filename)).items()
    }
    assert {name: visible_values[name] for name in expected} == expected


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
