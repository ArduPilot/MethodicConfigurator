#!/usr/bin/env python3

"""
Tests for the backend_filesystem.py file.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import json
import tempfile
import unittest
from argparse import ArgumentParser
from contextlib import nullcontext
from os import devnull as os_devnull
from os import path as os_path
from pathlib import Path
from shutil import which
from subprocess import CalledProcessError, SubprocessError, run
from unittest.mock import MagicMock, mock_open, patch

import pytest

from ardupilot_methodic_configurator.__main__ import initialize_filesystem, upgrade_project_parameter_files
from ardupilot_methodic_configurator.annotate_params import get_xml_data, get_xml_dir
from ardupilot_methodic_configurator.backend_filesystem import (
    LocalFilesystem,
    _rename_file_preserving_git_history,
    validate_project_vehicle_type,
)
from ardupilot_methodic_configurator.data_model_par_dict import Par, ParDict
from ardupilot_methodic_configurator.data_model_parameter_upgrade import upgrade_parameters_for_firmware_version
from ardupilot_methodic_configurator.data_model_vehicle_project import VehicleProjectManager
from ardupilot_methodic_configurator.data_model_vehicle_project_opener import VehicleProjectOpener, VehicleProjectOpenError
from ardupilot_methodic_configurator.log_analysis.backend_data_sources import load_apm_pdef

# pylint: disable=too-many-lines, protected-access

REFRESHED_METADATA = (
    '<paramfile><param name="ArduCopter:NEW_PARAM" humanName="New parameter" documentation="New firmware metadata">'
    '<field name="RebootRequired">True</field></param></paramfile>'
)


@pytest.fixture(name="firmware_project")
def fixture_firmware_project(tmp_path: Path) -> Path:
    """Provide a real project with old metadata and schema-valid component JSON."""
    template = (
        Path(__file__).parents[1]
        / "ardupilot_methodic_configurator/vehicle_templates/ArduCopter/empty_4.6.x/vehicle_components.json"
    )
    (tmp_path / "vehicle_components.json").write_text(template.read_text(encoding="utf-8"), encoding="utf-8")
    (tmp_path / "01_project.param").write_text("NEW_PARAM,1\n", encoding="utf-8")
    (tmp_path / "apm.pdef.xml").write_text(
        '<paramfile><param name="ArduCopter:OLD_PARAM" humanName="Old parameter"/></paramfile>', encoding="utf-8"
    )
    return tmp_path


@pytest.fixture(name="metadata_download")
def fixture_metadata_download(firmware_project: Path, monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    """Replace only network IO, checking deletion and persistence ordering."""
    components_path = firmware_project / "vehicle_components.json"
    original_components = components_path.read_bytes()

    def download(_url: str, destination: str) -> bool:
        assert not (firmware_project / "apm.pdef.xml").exists()
        assert components_path.read_bytes() == original_components
        Path(destination).write_text(REFRESHED_METADATA, encoding="utf-8")
        return True

    downloader = MagicMock(side_effect=download)
    monkeypatch.setattr("ardupilot_methodic_configurator.backend_filesystem.download_file_from_url", downloader)
    monkeypatch.setattr("ardupilot_methodic_configurator.annotate_params.download_file_from_url", downloader)
    return downloader


@pytest.mark.parametrize("opening_method", ["direct", "selected", "last"])
@pytest.mark.parametrize("use_fallback", [False, True])
def test_opening_project_refreshes_metadata_and_persists_firmware_once(
    firmware_project: Path,
    metadata_download: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
    opening_method: str,
    use_fallback: bool,
) -> None:
    """
    Replace stale XML before committing the connected firmware version to JSON.

    GIVEN: A project recorded for 4.6.3 and an FC running 4.7.2
    WHEN: The project is opened directly, selected, or reopened as the last project
    THEN: Primary or fallback XML is parsed before JSON advances, and reopening uses the cache
    """
    other_project = firmware_project / "other_project"
    other_project.mkdir()
    (other_project / "apm.pdef.xml").write_text('<paramfile><param name="WRONG_CWD_PARAM"/></paramfile>', encoding="utf-8")
    monkeypatch.chdir(other_project)
    if use_fallback:
        successful_download = metadata_download.side_effect

        def download_with_fallback(url: str, destination: str) -> bool:
            if url.startswith("https://firmware.ardupilot.org/"):
                return False
            return successful_download(url, destination)

        metadata_download.side_effect = download_with_fallback
    filesystem = LocalFilesystem(None, "ArduCopter", "4.7.2", False, False)  # noqa: FBT003
    stale_key = ("ArduCopter", "4.7.2", str(firmware_project))
    filesystem._parameter_metadata_cache[stale_key] = {"STALE_RAM_PARAM": {}}
    if opening_method == "direct":
        # Exercise the constructor path, used when starting with --vehicle-dir.
        filesystem = LocalFilesystem(str(firmware_project), "ArduCopter", "4.7.2", False, False)  # noqa: FBT003
    else:
        opener = VehicleProjectOpener(filesystem)
        if opening_method == "selected":
            opener.open_vehicle_directory(str(firmware_project))
        else:
            opener.open_last_vehicle_directory(str(firmware_project))

    saved_components = json.loads((firmware_project / "vehicle_components.json").read_text(encoding="utf-8"))
    assert saved_components["Components"]["Flight Controller"]["Firmware"]["Version"] == "4.7.2"
    assert filesystem.doc_dict["NEW_PARAM"]["RebootRequired"] is True
    assert "New firmware metadata" in filesystem.doc_dict["NEW_PARAM"]["doc_tooltip"]
    assert "STALE_RAM_PARAM" not in filesystem.doc_dict
    assert (firmware_project / "apm.pdef.xml").read_text(encoding="utf-8") == REFRESHED_METADATA
    assert metadata_download.call_args_list[0].args[0] == (
        "https://firmware.ardupilot.org/Copter/stable-4.7.2/__METADATA__/apm.pdef.xml"
    )
    assert filesystem.get_parameter_files_firmware_version() == "4.6.3"

    # Repeat in the same process, then simulate restarting the application.
    VehicleProjectOpener(filesystem).open_vehicle_directory(str(firmware_project))
    assert filesystem.get_parameter_files_firmware_version() == "4.6.3"
    reopened = LocalFilesystem(str(firmware_project), "ArduCopter", "4.7.2", False, False)  # noqa: FBT003
    assert reopened.get_parameter_files_firmware_version() == "4.6.3"
    assert reopened.doc_dict["NEW_PARAM"]["RebootRequired"] is True
    assert metadata_download.call_count == (2 if use_fallback else 1)
    if use_fallback:
        assert metadata_download.call_args.args[0] == (
            "https://raw.githubusercontent.com/ArduPilot/ParameterRepository/refs/heads/main/Copter-4.7/apm.pdef.xml"
        )


def test_parameter_upgrade_survives_restart_and_partial_saves(firmware_project: Path, metadata_download: MagicMock) -> None:
    """Retain the source version until every parameter file is saved in the new form."""
    (firmware_project / "01_project.param").write_text("ANGLE_MAX,4500\n", encoding="utf-8")
    (firmware_project / "02_other.param").write_text("ANGLE_MAX,3000\n", encoding="utf-8")
    first = LocalFilesystem(str(firmware_project), "ArduCopter", "4.7.2", False, False)  # noqa: FBT003
    assert first.get_parameter_files_firmware_version() == "4.6.3"

    # Restart before conversion, then save only one of the two converted files.
    second = LocalFilesystem(str(firmware_project), "ArduCopter", "4.7.2", False, False)  # noqa: FBT003
    state = MagicMock()
    state.local_filesystem = second
    state.flight_controller.info.flight_sw_version = "4.7.2"
    upgrade_project_parameter_files(state, second.get_parameter_files_firmware_version())
    assert second.get_parameter_files_firmware_version() == "4.6.3"
    assert "ANGLE_MAX" not in second.file_parameters["01_project.param"]
    (firmware_project / "01_project.param").write_text("ATC_ANGLE_MAX,45\n", encoding="utf-8")

    third = LocalFilesystem(str(firmware_project), "ArduCopter", "4.7.2", False, False)  # noqa: FBT003
    assert third.get_parameter_files_firmware_version() == "4.6.3"
    upgrade_parameters_for_firmware_version(third.get_parameter_files_firmware_version(), "4.7.2", third.file_parameters)
    assert third.file_parameters["01_project.param"]["ATC_ANGLE_MAX"].value == 45
    assert third.file_parameters["02_other.param"]["ATC_ANGLE_MAX"].value == 30
    assert metadata_download.call_count == 1

    # Once both files on disk are upgraded, a later startup clears the marker.
    (firmware_project / "02_other.param").write_text("ATC_ANGLE_MAX,30\n", encoding="utf-8")
    fourth = LocalFilesystem(str(firmware_project), "ArduCopter", "4.7.2", False, False)  # noqa: FBT003
    state.local_filesystem = fourth
    upgrade_project_parameter_files(state, fourth.get_parameter_files_firmware_version())
    assert fourth.get_parameter_files_firmware_version() == "4.7.2"
    assert "Parameter files firmware version" not in json.loads(
        (firmware_project / "vehicle_components.json").read_text(encoding="utf-8")
    )


@pytest.mark.parametrize("method", ["open_vehicle_directory", "open_last_vehicle_directory"])
def test_connected_controller_rejects_other_vehicle_family_before_project_changes(
    firmware_project: Path, metadata_download: MagicMock, method: str
) -> None:
    """A selected Copter project must not be modified for a connected Plane."""
    original_components = (firmware_project / "vehicle_components.json").read_bytes()
    original_xml = (firmware_project / "apm.pdef.xml").read_bytes()
    filesystem = LocalFilesystem(None, "ArduPlane", "4.7.2", False, False)  # noqa: FBT003
    controller = MagicMock()
    controller.info.vehicle_type = "ArduPlane"
    manager = VehicleProjectManager(filesystem, controller)
    with pytest.raises(VehicleProjectOpenError, match="ArduPlane") as error:
        getattr(manager, method)(str(firmware_project))
    assert "ArduCopter" in error.value.message
    assert error.value.title
    assert (firmware_project / "vehicle_components.json").read_bytes() == original_components
    assert (firmware_project / "apm.pdef.xml").read_bytes() == original_xml
    metadata_download.assert_not_called()


@pytest.mark.parametrize("connected_type", ["ArduCopter", "Heli"])
def test_copter_and_heli_share_a_firmware_family(firmware_project: Path, connected_type: str) -> None:
    """A helicopter controller can use a Copter project and vice versa."""
    assert validate_project_vehicle_type(str(firmware_project), connected_type) == "ArduCopter"


@pytest.mark.parametrize(
    ("project_type", "connected_type"), [("Rover", "ArduRover"), ("ArduRover", "Rover"), ("Heli", "ArduCopter")]
)
def test_vehicle_family_aliases_are_accepted(firmware_project: Path, project_type: str, connected_type: str) -> None:
    """Equivalent project and controller type names must not block opening a project."""
    components_path = firmware_project / "vehicle_components.json"
    data = json.loads(components_path.read_text(encoding="utf-8"))
    data["Components"]["Flight Controller"]["Firmware"]["Type"] = project_type
    components_path.write_text(json.dumps(data), encoding="utf-8")
    assert validate_project_vehicle_type(str(firmware_project), connected_type) == project_type


def test_unknown_controller_type_does_not_reject_a_project(firmware_project: Path) -> None:
    """Offline use or an unidentified controller must not be treated as a mismatch."""
    assert validate_project_vehicle_type(str(firmware_project), "") == ""
    controller = MagicMock()
    controller.master = None
    controller.info.vehicle_type = "ArduPlane"
    manager = VehicleProjectManager(MagicMock(), controller)
    manager._opener.open_vehicle_directory = MagicMock(return_value=str(firmware_project))
    manager.store_recently_used_vehicle_dir = MagicMock()
    assert manager.open_vehicle_directory(str(firmware_project)) == str(firmware_project)


@pytest.mark.parametrize(
    "components",
    [
        {},
        {"Components": {}},
        {"Components": {"Flight Controller": {}}},
        {"Components": {"Flight Controller": {"Firmware": {}}}},
    ],
)
def test_project_without_a_recorded_vehicle_type_remains_openable(firmware_project: Path, components: dict) -> None:
    """Incomplete project metadata does not invent a vehicle-family mismatch."""
    (firmware_project / "vehicle_components.json").write_text(json.dumps(components), encoding="utf-8")
    assert validate_project_vehicle_type(str(firmware_project), "ArduCopter") == ""


@pytest.mark.parametrize("contents", [None, "{invalid json"])
def test_missing_or_invalid_component_file_is_left_to_project_loader(firmware_project: Path, contents: str | None) -> None:
    """The family check leaves missing or malformed files to the normal project loader."""
    components = firmware_project / "vehicle_components.json"
    if contents is None:
        components.unlink()
    else:
        components.write_text(contents, encoding="utf-8")
    assert validate_project_vehicle_type(str(firmware_project), "ArduCopter") == ""


def test_vehicle_type_check_handles_utf8_bom(firmware_project: Path) -> None:
    """A BOM in component JSON must not prevent detection of an incompatible FC."""
    components = firmware_project / "vehicle_components.json"
    contents = components.read_text(encoding="utf-8")
    components.write_text(contents, encoding="utf-8-sig")
    with pytest.raises(ValueError, match="ArduPlane"):
        validate_project_vehicle_type(str(firmware_project), "ArduPlane")


def test_xml_loader_reuses_current_directory_cache_by_default(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Existing callers can use local metadata without network access."""
    project = tmp_path / "project"
    project.mkdir()
    (tmp_path / "apm.pdef.xml").write_text(REFRESHED_METADATA, encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    with patch("ardupilot_methodic_configurator.annotate_params.download_file_from_url") as download:
        root = get_xml_data("https://example.invalid/", str(project), "apm.pdef.xml", "ArduCopter")
    assert root.find("param") is not None
    download.assert_not_called()


@pytest.mark.parametrize(
    ("source_version", "target_version"), [("4.7.2", "invalid"), ("invalid", "4.7.2"), ("4.7.2", "4.6.3")]
)
def test_pending_upgrade_is_not_cleared_for_invalid_or_older_firmware(source_version: str, target_version: str) -> None:
    """Unknown versions and a downgrade do not prove that upgrades were saved."""
    state = MagicMock()
    state.local_filesystem.file_parameters = {"01_first.param": ParDict({"TEST": Par(1)})}
    state.flight_controller.info.flight_sw_version = target_version
    clear_pending = MagicMock()
    state.local_filesystem.clear_completed_parameter_upgrade = clear_pending
    upgrade_project_parameter_files(state, source_version)
    clear_pending.assert_not_called()


def test_pending_upgrade_can_be_cleared_when_firmware_versions_are_equal() -> None:
    """Equal valid versions with unchanged files are safe to mark complete."""
    state = MagicMock()
    state.local_filesystem.file_parameters = {"01_first.param": ParDict({"TEST": Par(1)})}
    state.flight_controller.info.flight_sw_version = "4.7.2"
    clear_pending = MagicMock()
    state.local_filesystem.clear_completed_parameter_upgrade = clear_pending
    upgrade_project_parameter_files(state, "4.7.2")
    clear_pending.assert_called_once_with()


def test_parameter_upgrade_accepts_firmware_version_with_release_description() -> None:
    """Release descriptions must not suppress conversions required by the FC version."""
    state = MagicMock()
    state.local_filesystem.file_parameters = {"01_first.param": ParDict({"ANGLE_MAX": Par(4500)})}
    state.flight_controller.info.flight_sw_version = "4.7.2 official release"
    clear_pending = MagicMock()
    state.local_filesystem.clear_completed_parameter_upgrade = clear_pending
    upgrade_project_parameter_files(state, "4.6.3")
    assert state.local_filesystem.file_parameters["01_first.param"]["ATC_ANGLE_MAX"].value == 45
    clear_pending.assert_not_called()


def test_clearing_absent_pending_upgrade_is_a_noop(firmware_project: Path) -> None:
    """Projects without pending upgrades are not rewritten."""
    filesystem = LocalFilesystem(None, "ArduCopter", "", False, False)  # noqa: FBT003
    filesystem.vehicle_dir = str(firmware_project)
    filesystem.load_vehicle_components_json_data(str(firmware_project))
    original = (firmware_project / "vehicle_components.json").read_bytes()
    filesystem.clear_completed_parameter_upgrade()
    assert (firmware_project / "vehicle_components.json").read_bytes() == original


def test_pending_upgrade_is_not_removed_from_read_only_templates(firmware_project: Path) -> None:
    """Read-only templates retain their pending state without a filesystem write."""
    filesystem = LocalFilesystem(None, "ArduCopter", "", False, False)  # noqa: FBT003
    filesystem.vehicle_dir = str(firmware_project)
    filesystem.load_vehicle_components_json_data(str(firmware_project))
    assert filesystem.vehicle_components_fs.data is not None
    filesystem.vehicle_components_fs.data["Parameter files firmware version"] = "4.6.3"
    with (
        patch.object(filesystem, "_is_read_only_template", return_value=True),
        patch.object(filesystem, "save_vehicle_components_json_data") as save,
    ):
        filesystem.clear_completed_parameter_upgrade()
    save.assert_not_called()
    assert filesystem.get_parameter_files_firmware_version() == "4.6.3"


def test_failed_pending_upgrade_save_keeps_state_for_retry(firmware_project: Path, metadata_download: MagicMock) -> None:
    """A failed component JSON write must not forget the pending source version."""
    filesystem = LocalFilesystem(str(firmware_project), "ArduCopter", "4.7.2", False, False)  # noqa: FBT003
    with (
        patch.object(filesystem, "save_vehicle_components_json_data", return_value=(True, "disk full")),
        pytest.raises(OSError, match="disk full"),
    ):
        filesystem.clear_completed_parameter_upgrade()
    assert filesystem.get_parameter_files_firmware_version() == "4.6.3"
    assert metadata_download.call_count == 1


def test_pending_parameter_version_survives_a_second_firmware_change(
    firmware_project: Path, metadata_download: MagicMock
) -> None:
    """Refreshing metadata twice must not lose the version of unsaved parameter files."""
    LocalFilesystem(str(firmware_project), "ArduCopter", "4.7.2", False, False)  # noqa: FBT003

    def download(_url: str, destination: str) -> bool:
        Path(destination).write_text(REFRESHED_METADATA, encoding="utf-8")
        return True

    metadata_download.side_effect = download
    filesystem = LocalFilesystem(str(firmware_project), "ArduCopter", "4.8.0", False, False)  # noqa: FBT003
    assert filesystem.get_fc_fw_version_from_vehicle_components_json() == "4.8.0"
    assert filesystem.get_parameter_files_firmware_version() == "4.6.3"


def test_download_is_staged_on_the_same_filesystem_as_the_project(
    firmware_project: Path, metadata_download: MagicMock, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Atomic publication must work when the system temporary directory is on another filesystem."""

    def replace(source: str, destination: str) -> None:
        assert Path(source).parent.parent == firmware_project
        Path(source).replace(destination)

    monkeypatch.setattr("ardupilot_methodic_configurator.backend_filesystem.os_replace", replace)
    LocalFilesystem(str(firmware_project), "ArduCopter", "4.7.2", False, False)  # noqa: FBT003
    assert metadata_download.call_count == 1


def test_direct_start_rejects_other_vehicle_family_before_migration(firmware_project: Path) -> None:
    """A command-line project is checked against the connected controller first."""
    state = MagicMock()
    state.args.bin_log = ""
    state.args.vehicle_dir = str(firmware_project)
    state.flight_controller.info.vehicle_type = "ArduPlane"
    original_components = (firmware_project / "vehicle_components.json").read_bytes()
    original_xml = (firmware_project / "apm.pdef.xml").read_bytes()
    with (
        patch("ardupilot_methodic_configurator.__main__.show_error_message") as show_error,
        patch("ardupilot_methodic_configurator.__main__.migrate_vehicle_project_if_needed") as migrate,
        pytest.raises(ValueError, match="ArduPlane"),
    ):
        initialize_filesystem(state)
    migrate.assert_not_called()
    assert isinstance(show_error.call_args.args[0], str)
    assert show_error.call_args.args[0]
    assert "ArduPlane" in show_error.call_args.args[1]
    assert (firmware_project / "vehicle_components.json").read_bytes() == original_components
    assert (firmware_project / "apm.pdef.xml").read_bytes() == original_xml


@pytest.mark.parametrize("connected", [True, False])
def test_direct_start_uses_compatible_project_type(firmware_project: Path, connected: bool) -> None:
    """Use the selected project type, and ignore stale controller identity when offline."""
    state = MagicMock()
    state.args.bin_log = ""
    state.args.vehicle_dir = str(firmware_project)
    state.param_default_values = {}
    state.flight_controller.master = MagicMock() if connected else None
    state.flight_controller.info.vehicle_type = "ArduCopter" if connected else "ArduPlane"
    state.vehicle_type = "ArduPlane" if connected else "ArduCopter"
    with (
        patch("ardupilot_methodic_configurator.__main__.migrate_vehicle_project_if_needed"),
        patch("ardupilot_methodic_configurator.__main__.LocalFilesystem") as filesystem_class,
        patch("ardupilot_methodic_configurator.__main__.show_error_message") as show_error,
    ):
        initialize_filesystem(state)
    assert filesystem_class.call_args.args[1] == "ArduCopter"
    show_error.assert_not_called()


@pytest.mark.parametrize("failure", ["download", "malformed_xml", "empty_xml", "save_json", "delete_xml"])
def test_failed_firmware_refresh_preserves_recorded_version_and_can_be_retried(
    firmware_project: Path, metadata_download: MagicMock, failure: str
) -> None:
    """
    Keep the saved project version unchanged when metadata replacement cannot complete.

    GIVEN: Old project metadata and a failure during refresh or component persistence
    WHEN: Opening the project fails, then the same project is opened after recovery
    THEN: The old JSON survives the failure and is updated only by the successful retry
    """
    components_path = firmware_project / "vehicle_components.json"
    original_components = components_path.read_bytes()
    version = "4.7.2"
    filesystem = LocalFilesystem(None, "ArduCopter", version, False, False)  # noqa: FBT003
    opener = VehicleProjectOpener(filesystem)
    successful_download = metadata_download.side_effect

    def fail_download(url: str, destination: str) -> bool:
        if failure == "download":
            return False
        successful_download(url, destination)
        invalid_xml = {
            "malformed_xml": "<paramfile>",
            "empty_xml": "<paramfile/>",
        }
        if failure in invalid_xml:
            Path(destination).write_text(invalid_xml[failure], encoding="utf-8")
        return True

    metadata_download.side_effect = fail_download
    patch_target = (
        "ardupilot_methodic_configurator.backend_filesystem.os_remove"
        if failure == "delete_xml"
        else "ardupilot_methodic_configurator.backend_filesystem_json_with_schema.safe_write"
    )
    # The remaining scenarios fail during the actual download/parse path.
    failure_context = (
        patch(patch_target, side_effect=PermissionError("read-only project"))
        if failure in {"save_json", "delete_xml"}
        else nullcontext()
    )
    with failure_context, pytest.raises(VehicleProjectOpenError) as error:
        opener.open_vehicle_directory(str(firmware_project))

    if failure in {"download", "malformed_xml", "empty_xml"}:
        assert version in error.value.message
    if failure == "save_json":
        assert "vehicle_components.json" in error.value.message
    if failure == "delete_xml":
        assert "read-only project" in error.value.message

    assert components_path.read_bytes() == original_components
    if failure in {"download", "malformed_xml", "empty_xml"}:
        assert not (firmware_project / "apm.pdef.xml").exists()

    metadata_download.side_effect = successful_download
    opener.open_vehicle_directory(str(firmware_project))
    saved = json.loads(components_path.read_text(encoding="utf-8"))
    assert saved["Components"]["Flight Controller"]["Firmware"]["Version"] == version
    assert filesystem.doc_dict["NEW_PARAM"]["RebootRequired"] is True


@pytest.mark.parametrize("fc_version", ["", "4.6.3"])
def test_matching_or_offline_project_keeps_its_metadata_and_component_json(
    firmware_project: Path, metadata_download: MagicMock, fc_version: str
) -> None:
    """
    Reuse project metadata when firmware matches or there is no connected FC version.

    GIVEN: A project whose firmware matches the FC, or an offline session
    WHEN: The project is opened
    THEN: Its XML and component JSON remain unchanged and no download is attempted
    """
    metadata_bytes = (firmware_project / "apm.pdef.xml").read_bytes()
    component_bytes = (firmware_project / "vehicle_components.json").read_bytes()

    filesystem = LocalFilesystem(str(firmware_project), "ArduCopter", fc_version, False, False)  # noqa: FBT003

    assert "OLD_PARAM" in filesystem.doc_dict
    assert (firmware_project / "apm.pdef.xml").read_bytes() == metadata_bytes
    assert (firmware_project / "vehicle_components.json").read_bytes() == component_bytes
    metadata_download.assert_not_called()


def test_matching_project_downloads_snapshot_when_release_metadata_is_unavailable(
    firmware_project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A matching project with no local XML still uses the snapshot fallback."""
    (firmware_project / "apm.pdef.xml").unlink()
    monkeypatch.chdir(firmware_project)
    urls: list[str] = []

    def download(url: str, destination: str) -> bool:
        urls.append(url)
        if "ParameterRepository" not in url:
            return False
        Path(destination).write_text(REFRESHED_METADATA, encoding="utf-8")
        return True

    monkeypatch.setattr("ardupilot_methodic_configurator.annotate_params.download_file_from_url", download)
    filesystem = LocalFilesystem(str(firmware_project), "ArduCopter", "4.6.3", False, False)  # noqa: FBT003
    assert "NEW_PARAM" in filesystem.doc_dict
    assert len(urls) == 2
    assert urls[0] == "https://autotest.ardupilot.org/Parameters/versioned/Copter/stable-4.6.3/apm.pdef.xml"
    assert "/Copter-4.6/apm.pdef.xml" in urls[1]


def test_new_blank_project_does_not_inherit_template_firmware_version(firmware_project: Path) -> None:
    """Without a connected FC, a blanked template must not retain its old firmware identity."""
    filesystem = LocalFilesystem(None, "ArduCopter", "", False, False)  # noqa: FBT003
    filesystem.re_init(str(firmware_project), "ArduCopter", blank_component_data=True)
    assert filesystem.fw_version == ""


def test_firmware_suffix_does_not_cause_repeated_metadata_refresh(
    firmware_project: Path, metadata_download: MagicMock
) -> None:
    """A version with a release suffix fetches the right metadata only once."""
    filesystem = LocalFilesystem(str(firmware_project), "ArduCopter", "4.7.2 official", False, False)  # noqa: FBT003
    assert "NEW_PARAM" in filesystem.doc_dict
    assert "/stable-4.7.2/" in metadata_download.call_args.args[0]
    reopened = LocalFilesystem(str(firmware_project), "ArduCopter", "4.7.2 official", False, False)  # noqa: FBT003
    assert "NEW_PARAM" in reopened.doc_dict
    assert metadata_download.call_count == 1


def test_refreshed_metadata_records_the_vehicle_type_used_for_loading(
    firmware_project: Path, metadata_download: MagicMock
) -> None:
    """Component identity remains aligned with the type used to load new metadata."""

    def download(_url: str, destination: str) -> bool:
        Path(destination).write_text(REFRESHED_METADATA.replace("ArduCopter:", "Helicopter:"), encoding="utf-8")
        return True

    metadata_download.side_effect = download
    filesystem = LocalFilesystem(str(firmware_project), "Heli", "4.7.2", False, False)  # noqa: FBT003
    assert "NEW_PARAM" in filesystem.doc_dict
    components = json.loads((firmware_project / "vehicle_components.json").read_text(encoding="utf-8"))
    assert components["Components"]["Flight Controller"]["Firmware"]["Type"] == "Heli"


def test_reading_template_metadata_does_not_change_its_recorded_firmware(
    firmware_project: Path, metadata_download: MagicMock
) -> None:
    """
    Protect template component files when loading metadata for a connected FC.

    GIVEN: A template loaded for reading with template editing disabled
    WHEN: The template is inspected while different FC firmware is connected
    THEN: Its cached XML loads without changing template files or downloading replacement metadata
    """
    components = firmware_project / "vehicle_components.json"
    original = components.read_bytes()
    original_xml = (firmware_project / "apm.pdef.xml").read_bytes()
    with patch(
        "ardupilot_methodic_configurator.backend_filesystem_program_settings.ProgramSettings.get_templates_base_dir",
        return_value=str(firmware_project),
    ):
        filesystem = LocalFilesystem(str(firmware_project), "ArduCopter", "4.7.2", False, False)  # noqa: FBT003

    assert "OLD_PARAM" in filesystem.doc_dict
    assert components.read_bytes() == original
    assert (firmware_project / "apm.pdef.xml").read_bytes() == original_xml
    metadata_download.assert_not_called()


def _run_git_in_test_project(project: Path, *arguments: str) -> str:
    """Run Git in an isolated test repository without invoking configured commands."""
    git_executable = which("git")
    if git_executable is None:
        pytest.skip("Git is unavailable")
    return run(  # noqa: S603
        [git_executable, "-c", "core.fsmonitor=false", "-c", f"core.hooksPath={os_devnull}", "-C", str(project), *arguments],
        check=True,
        capture_output=True,
        text=True,
    ).stdout


@pytest.fixture(name="external_git_project")
def fixture_external_git_project(tmp_path: Path) -> Path:
    """Provide tracked project files outside the installation, in a repository subdirectory."""
    project = tmp_path / "external-project"
    steps = project / "steps"
    steps.mkdir(parents=True)
    (steps / "old.param").write_text("PARAM,1\n", encoding="utf-8")
    (steps / "old.pdef.xml").write_text("<parameters />", encoding="utf-8")
    _run_git_in_test_project(project, "init", "--quiet")
    _run_git_in_test_project(project, "add", "--", "steps/old.param", "steps/old.pdef.xml")
    return project


@pytest.mark.parametrize("editing_templates", [False, True])
def test_external_git_project_renames_tracked_parameters_and_documentation(
    external_git_project: Path, editing_templates: bool
) -> None:
    """Opening a tracked external project stages both renames regardless of template-editing mode."""
    filesystem = LocalFilesystem(
        str(external_git_project / "steps"),
        "ArduCopter",
        "4.3.0",
        allow_editing_template_files=editing_templates,
        save_component_to_system_templates=False,
        load_project=False,
    )
    filesystem.configuration_steps = {"new.param": {"old_filenames": ["old.param"]}}

    filesystem.rename_parameter_files()

    assert (external_git_project / "steps/new.param").read_text(encoding="utf-8") == "PARAM,1\n"
    assert (external_git_project / "steps/new.pdef.xml").read_text(encoding="utf-8") == "<parameters />"
    assert _run_git_in_test_project(external_git_project, "ls-files").splitlines() == [
        "steps/new.param",
        "steps/new.pdef.xml",
    ]


def test_external_git_project_with_locked_index_still_renames_files(
    external_git_project: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """An index lock leaves the index untouched while the project and its documentation migrate."""
    filesystem = LocalFilesystem(
        str(external_git_project / "steps"),
        "ArduCopter",
        "4.3.0",
        allow_editing_template_files=False,
        save_component_to_system_templates=False,
        load_project=False,
    )
    filesystem.configuration_steps = {"new.param": {"old_filenames": ["old.param"]}}
    (external_git_project / ".git/index.lock").write_text("", encoding="utf-8")

    filesystem.rename_parameter_files()

    assert (external_git_project / "steps/new.param").read_text(encoding="utf-8") == "PARAM,1\n"
    assert (external_git_project / "steps/new.pdef.xml").exists()
    assert _run_git_in_test_project(external_git_project, "ls-files").splitlines() == [
        "steps/old.param",
        "steps/old.pdef.xml",
    ]
    assert "falling back to filesystem rename" in caplog.text


@pytest.mark.parametrize("tracked", [False, True])
def test_external_git_project_rename_does_not_execute_fsmonitor_or_hooks(external_git_project: Path, tracked: bool) -> None:
    """Project Git configuration cannot invoke fsmonitor or index hooks during tracked or untracked renames."""
    monitor = external_git_project / "fsmonitor-hook.sh"
    monitor.write_text("#!/bin/sh\nprintf 'ran' > fsmonitor-called\nprintf 'token\\000'\n", encoding="utf-8")
    monitor.chmod(0o755)
    hooks = external_git_project / "hooks"
    hooks.mkdir()
    index_hook = hooks / "post-index-change"
    index_hook.write_text("#!/bin/sh\nprintf 'ran' > index-hook-called\n", encoding="utf-8")
    index_hook.chmod(0o755)
    _run_git_in_test_project(external_git_project, "config", "core.fsmonitor", monitor.as_posix())
    _run_git_in_test_project(external_git_project, "config", "core.hooksPath", hooks.as_posix())
    if not tracked:
        _run_git_in_test_project(external_git_project, "rm", "--cached", "--", "steps/old.param", "steps/old.pdef.xml")

    # Prove that both harmless marker scripts work before checking their suppression.
    _run_git_in_test_project(
        external_git_project,
        "-c",
        f"core.fsmonitor={monitor.as_posix()}",
        "-c",
        f"core.hooksPath={hooks.as_posix()}",
        "update-index",
        "--force-write-index",
    )
    monitor_marker = external_git_project / "fsmonitor-called"
    hook_marker = external_git_project / "index-hook-called"
    assert monitor_marker.exists()
    assert hook_marker.exists()
    monitor_marker.unlink()
    hook_marker.unlink()
    filesystem = LocalFilesystem(
        str(external_git_project / "steps"),
        "ArduCopter",
        "4.3.0",
        allow_editing_template_files=False,
        save_component_to_system_templates=False,
        load_project=False,
    )
    filesystem.configuration_steps = {"new.param": {"old_filenames": ["old.param"]}}

    filesystem.rename_parameter_files()

    assert (external_git_project / "steps/new.param").read_text(encoding="utf-8") == "PARAM,1\n"
    assert (external_git_project / "steps/new.pdef.xml").exists()
    assert not monitor_marker.exists()
    assert not hook_marker.exists()
    expected_paths = ["steps/new.param", "steps/new.pdef.xml"] if tracked else []
    assert _run_git_in_test_project(external_git_project, "ls-files").splitlines() == expected_paths


@pytest.mark.parametrize(
    ("version", "expected_source"),
    [
        ("4.6.3", "https://autotest.ardupilot.org/Parameters/versioned/Plane/stable-4.6.3/apm.pdef.xml"),
        ("4.7.0", "https://autotest.ardupilot.org/Parameters/versioned/Plane/stable-4.7.0/apm.pdef.xml"),
        ("4.7.1", "https://autotest.ardupilot.org/Parameters/versioned/Plane/stable-4.7.1/apm.pdef.xml"),
        ("4.7.2", "https://firmware.ardupilot.org/Plane/stable-4.7.2/__METADATA__/apm.pdef.xml"),
    ],
)
def test_standalone_metadata_uses_connected_firmware_and_normalizes_reboot_field(version: str, expected_source: str) -> None:
    """
    A standalone editor downloads and normalizes metadata for its connected firmware.

    GIVEN: A connected flight controller running a historical or current release
    WHEN: Its parameter documentation is loaded
    THEN: The correct upstream URL is downloaded and reboot metadata is normalized
    """
    filesystem = LocalFilesystem(None, "ArduPlane", version, False, False)  # noqa: FBT003
    metadata = {
        "ROLL_P": {
            "humanName": "Roll P",
            "documentation": [],
            "fields": {"RebootRequired": "True"},
            "values": {},
        }
    }
    with (
        patch("ardupilot_methodic_configurator.backend_filesystem.download_file_from_url", return_value=True) as download,
        patch("ardupilot_methodic_configurator.backend_filesystem.parse_parameter_metadata", return_value=metadata) as parse,
    ):
        source = filesystem.load_parameter_metadata_for_flight_controller("ArduPlane", version)

    assert source == expected_source
    assert download.call_args.args[0] == source
    assert parse.call_args.args[0] == ""
    assert parse.call_args.args[3] == "ArduPlane"
    assert filesystem.doc_dict["ROLL_P"]["RebootRequired"] is True


@pytest.mark.parametrize("vehicle_type", ["AntennaTracker", "AP_Periph", "Blimp", "SITL"])
@pytest.mark.parametrize("version", ["4.7.1", "4.7.2"])
def test_project_and_log_metadata_allow_optional_fallbacks(tmp_path: Path, vehicle_type: str, version: str) -> None:
    """
    Load cached vehicle metadata through both project and log-analysis consumers.

    GIVEN: A vehicle whose snapshot fallback was previously rejected
    WHEN: Project loading and log analysis read its cached parameter documentation
    THEN: Both paths parse the metadata without a fallback construction error
    """
    (tmp_path / "apm.pdef.xml").write_text(
        '<paramfile><param name="TEST_PARAM" humanName="Test" documentation="Test metadata">'
        '<field name="RebootRequired">True</field></param></paramfile>',
        encoding="utf-8",
    )
    filesystem = LocalFilesystem(
        str(tmp_path),
        vehicle_type,
        version,
        allow_editing_template_files=False,
        save_component_to_system_templates=False,
        load_project=False,
    )
    with (
        patch.object(filesystem, "load_vehicle_components_json_data", return_value=True),
        patch.object(filesystem, "rename_parameter_files"),
        patch.object(filesystem, "read_params_from_files", return_value={"01_setup.param": ParDict()}),
        patch("ardupilot_methodic_configurator.backend_filesystem.ConfigurationSteps.re_init"),
        patch("ardupilot_methodic_configurator.backend_filesystem.load_default_param_file", return_value=ParDict()),
    ):
        filesystem.re_init(str(tmp_path), vehicle_type)
    log_metadata = load_apm_pdef(str(tmp_path), vehicle_type, version)

    assert filesystem.doc_dict["TEST_PARAM"]["RebootRequired"] is True
    assert log_metadata is not None
    assert log_metadata["TEST_PARAM"]["humanName"] == "Test"


@pytest.mark.parametrize(
    ("vehicle_type", "firmware_directory", "fallback_directory"),
    [
        ("AntennaTracker", "AntennaTracker", "Tracker-4.7"),
        ("AP_Periph", "AP_Periph", "AP_Periph-4.7"),
        ("Blimp", "Blimp", "Blimp-4.7"),
        ("SITL", "SITL", None),
    ],
)
def test_log_metadata_recovers_after_primary_download_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    vehicle_type: str,
    firmware_directory: str,
    fallback_directory: str | None,
) -> None:
    """
    Try supported snapshots or development metadata after a failed release download.

    GIVEN: A vehicle whose exact-release metadata cannot be downloaded
    WHEN: Log analysis requests its parameter documentation
    THEN: It loads the correct snapshot, or skips directly to development metadata for SITL
    """
    monkeypatch.chdir(tmp_path)
    requested_urls: list[str] = []

    def download_metadata(url: str, destination: str) -> bool:
        requested_urls.append(url)
        if len(requested_urls) == 1:
            return False
        Path(destination).write_text('<paramfile><param name="TEST_PARAM" humanName="Test"/></paramfile>', encoding="utf-8")
        return True

    with patch("ardupilot_methodic_configurator.annotate_params.download_file_from_url", side_effect=download_metadata):
        metadata = load_apm_pdef(str(tmp_path), vehicle_type, "4.7.2")

    expected_fallback = (
        f"https://raw.githubusercontent.com/ArduPilot/ParameterRepository/refs/heads/main/{fallback_directory}/apm.pdef.xml"
        if fallback_directory is not None
        else f"https://autotest.ardupilot.org/Parameters/{vehicle_type}/apm.pdef.xml"
    )
    assert requested_urls == [
        f"https://firmware.ardupilot.org/{firmware_directory}/stable-4.7.2/__METADATA__/apm.pdef.xml",
        expected_fallback,
    ]
    assert metadata is not None
    assert metadata["TEST_PARAM"]["humanName"] == "Test"


def test_fc_metadata_fetch_ignores_unrelated_xml_in_current_directory(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A cached XML from another vehicle must not replace the connected FC metadata."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "apm.pdef.xml").write_text("<stale/>", encoding="utf-8")

    def download_metadata(_url: str, destination: str) -> bool:
        Path(destination).write_text(
            '<parameters><param name="ArduPlane:ROLL_P" humanName="Roll P" documentation="">'
            '<field name="RebootRequired">True</field></param></parameters>',
            encoding="utf-8",
        )
        return True

    with patch("ardupilot_methodic_configurator.backend_filesystem.download_file_from_url", side_effect=download_metadata):
        filesystem = LocalFilesystem.for_external_parameter_file(str(tmp_path), "ArduPlane", "4.6.3", ParDict())

    assert filesystem.doc_dict["ROLL_P"]["RebootRequired"] is True


def test_standalone_metadata_rejects_generic_fallback() -> None:
    """A failed exact-version download must stop before upload metadata is created."""
    with (
        patch("ardupilot_methodic_configurator.backend_filesystem.download_file_from_url", return_value=False) as download,
        pytest.raises(ValueError, match=r"stable-4\.6\.3/apm\.pdef\.xml"),
    ):
        LocalFilesystem.for_external_parameter_file(".", "ArduPlane", "4.6.3", ParDict())

    download.assert_called_once()


def test_vehicle_configuration_file_size_distinguishes_missing_empty_and_ready_files(tmp_path: Path) -> None:
    """The filesystem reports enough state to validate upload candidates without direct Path access."""
    filesystem = LocalFilesystem(
        str(tmp_path),
        "ArduCopter",
        "4.3.0",
        allow_editing_template_files=False,
        save_component_to_system_templates=False,
        load_project=False,
    )
    empty_file = tmp_path / "empty.lua"
    empty_file.touch()
    ready_file = tmp_path / "ready.lua"
    ready_file.write_bytes(b"return true")
    directory = tmp_path / "directory"
    directory.mkdir()

    assert filesystem.vehicle_configuration_file_size("missing.lua") is None
    assert filesystem.vehicle_configuration_file_size("empty.lua") == 0
    assert filesystem.vehicle_configuration_file_size("ready.lua") == len(b"return true")
    assert filesystem.vehicle_configuration_file_size("directory") is None


class TestLocalFilesystem(unittest.TestCase):  # pylint: disable=too-many-public-methods
    """LocalFilesystem test class."""

    def test_constructor_invalidates_mismatched_metadata_before_reinitializing(self) -> None:
        """Opening a project invalidates stale metadata before it can be parsed."""
        with (
            patch.object(LocalFilesystem, "remove_cached_parameter_metadata_for_mismatched_firmware") as remove_metadata,
            patch.object(LocalFilesystem, "re_init") as reinitialize,
        ):
            LocalFilesystem(
                "/project",
                "ArduCopter",
                "4.7.0",
                allow_editing_template_files=False,
                save_component_to_system_templates=False,
            )

        remove_metadata.assert_called_once_with("/project")
        reinitialize.assert_called_once_with("/project", "ArduCopter")

    def test_read_params_from_files(self) -> None:
        """Test reading parameters from files with proper filtering."""
        mock_vehicle_dir = "/mock/dir"
        filesystem = LocalFilesystem(
            mock_vehicle_dir,
            "ArduCopter",
            "4.3.0",
            allow_editing_template_files=False,
            save_component_to_system_templates=False,
        )

        with (
            patch(
                "ardupilot_methodic_configurator.backend_filesystem.os_listdir",
                return_value=["02_test.param", "00_default.param", "01_ignore_readonly.param"],
            ),
            patch("ardupilot_methodic_configurator.backend_filesystem.os_path.isdir", return_value=True),
            patch(
                "ardupilot_methodic_configurator.backend_filesystem.ParDict.load_param_file_into_dict",
                return_value=ParDict({"PARAM1": Par(1.0)}),
            ),
            patch("ardupilot_methodic_configurator.backend_filesystem.os_path.join", side_effect=os_path.join),
        ):
            result = filesystem.read_params_from_files()
            assert len(result) == 1
            assert "02_test.param" in result
            # Compare ParDict object - check it has the expected parameter
            assert isinstance(result["02_test.param"], ParDict)
            assert "PARAM1" in result["02_test.param"]
            assert result["02_test.param"]["PARAM1"].value == 1.0

    def test_str_to_bool(self) -> None:
        lfs = LocalFilesystem(
            "vehicle_dir", "vehicle_type", None, allow_editing_template_files=False, save_component_to_system_templates=False
        )
        assert lfs.str_to_bool("true")
        assert lfs.str_to_bool("yes")
        assert lfs.str_to_bool("1")
        assert not lfs.str_to_bool("false")
        assert not lfs.str_to_bool("no")
        assert not lfs.str_to_bool("0")
        assert lfs.str_to_bool("maybe") is None

    def test_re_init(self) -> None:
        """Test reinitializing the filesystem with new parameters."""
        mock_vehicle_dir = "/mock/dir"
        filesystem = LocalFilesystem(
            mock_vehicle_dir,
            "ArduCopter",
            "4.3.0",
            allow_editing_template_files=False,
            save_component_to_system_templates=False,
        )

        with (
            patch.object(filesystem, "load_vehicle_components_json_data", return_value=True),
            patch.object(filesystem, "get_fc_fw_version_from_vehicle_components_json", return_value="4.3.0"),
            patch.object(filesystem, "get_fc_fw_type_from_vehicle_components_json", return_value="ArduCopter"),
            patch.object(filesystem, "rename_parameter_files"),
            patch.object(filesystem, "read_params_from_files", return_value={}),
        ):
            filesystem.re_init(mock_vehicle_dir, "ArduCopter")
            assert filesystem.vehicle_dir == mock_vehicle_dir
            assert filesystem.vehicle_type == "ArduCopter"

    def test_re_init_refreshes_auto_detected_firmware_version_for_each_project(self) -> None:
        """Opening another project refreshes a firmware version that was auto-detected."""
        filesystem = LocalFilesystem(
            None,
            "",
            "",
            allow_editing_template_files=False,
            save_component_to_system_templates=False,
        )

        with (
            patch.object(filesystem, "load_vehicle_components_json_data", return_value=True),
            patch.object(filesystem, "get_fc_fw_version_from_vehicle_components_json", side_effect=["4.7.0", "4.6.3"]),
            patch.object(filesystem, "get_fc_fw_type_from_vehicle_components_json", return_value="ArduCopter"),
            patch.object(filesystem, "rename_parameter_files"),
            patch.object(filesystem, "read_params_from_files", return_value={}),
        ):
            filesystem.re_init("/projects/4.7", "")
            filesystem.re_init("/projects/4.6", "")

        assert filesystem.fw_version == "4.6.3"

    def test_re_init_reuses_metadata_for_the_same_vehicle_firmware(self) -> None:
        """Reinitializing a new project does not download identical metadata again."""
        filesystem = LocalFilesystem(
            None,
            "ArduCopter",
            "4.6.3",
            allow_editing_template_files=False,
            save_component_to_system_templates=False,
        )
        metadata = {
            "TEST_PARAM": {
                "humanName": "Test parameter",
                "documentation": [],
                "fields": {},
                "values": {},
            }
        }

        with (
            patch.object(filesystem, "load_vehicle_components_json_data", return_value=True),
            patch.object(filesystem, "rename_parameter_files"),
            patch.object(filesystem, "read_params_from_files", return_value={"01_setup.param": ParDict()}),
            patch("ardupilot_methodic_configurator.backend_filesystem.load_default_param_file", return_value=ParDict()),
            patch(
                "ardupilot_methodic_configurator.backend_filesystem.parse_parameter_metadata",
                return_value=metadata,
            ) as parse_metadata,
        ):
            filesystem.re_init("/projects/source", "ArduCopter")
            filesystem.re_init("/projects/new-project", "ArduCopter")

        parse_metadata.assert_called_once()

    def test_firmware_mismatch_removes_cached_parameter_metadata(self) -> None:
        """Opening a project for another FC firmware removes stale parameter metadata."""
        filesystem = LocalFilesystem(
            None,
            "ArduCopter",
            "4.7.0",
            allow_editing_template_files=False,
            save_component_to_system_templates=False,
        )
        filesystem.vehicle_components_fs.data = {
            "Components": {"Flight Controller": {"Firmware": {"Type": "ArduCopter", "Version": "4.6.3"}}}
        }

        with tempfile.TemporaryDirectory() as vehicle_dir:
            filesystem._parameter_metadata_cache[("ArduCopter", "4.7.0", get_xml_dir(vehicle_dir))] = {}
            metadata_file = os_path.join(vehicle_dir, "apm.pdef.xml")
            with open(metadata_file, "w", encoding="utf-8") as file:
                file.write("<parameters />")

            with patch.object(
                filesystem,
                "load_vehicle_components_json_data",
                return_value=filesystem.vehicle_components_fs.data,
            ):
                assert filesystem.remove_cached_parameter_metadata_for_mismatched_firmware(vehicle_dir)

            assert not os_path.exists(metadata_file)

        assert ("ArduCopter", "4.7.0", get_xml_dir(vehicle_dir)) not in filesystem._parameter_metadata_cache

    def test_firmware_patch_mismatch_removes_cached_parameter_metadata(self) -> None:
        """A patch-level firmware mismatch also removes stale parameter metadata."""
        filesystem = LocalFilesystem(
            None,
            "ArduCopter",
            "4.6.4",
            allow_editing_template_files=False,
            save_component_to_system_templates=False,
        )
        filesystem.vehicle_components_fs.data = {
            "Components": {"Flight Controller": {"Firmware": {"Type": "ArduCopter", "Version": "4.6.3"}}}
        }

        with tempfile.TemporaryDirectory() as vehicle_dir:
            filesystem._parameter_metadata_cache[("ArduCopter", "4.6.4", get_xml_dir(vehicle_dir))] = {}
            metadata_file = os_path.join(vehicle_dir, "apm.pdef.xml")
            with open(metadata_file, "w", encoding="utf-8") as file:
                file.write("<parameters />")

            with patch.object(
                filesystem,
                "load_vehicle_components_json_data",
                return_value=filesystem.vehicle_components_fs.data,
            ):
                assert filesystem.remove_cached_parameter_metadata_for_mismatched_firmware(vehicle_dir)

            assert not os_path.exists(metadata_file)

        assert ("ArduCopter", "4.6.4", get_xml_dir(vehicle_dir)) not in filesystem._parameter_metadata_cache

    def test_firmware_patch_match_keeps_cached_parameter_metadata(self) -> None:
        """Matching major, minor, and patch versions keep cached metadata intact."""
        filesystem = LocalFilesystem(
            None,
            "ArduCopter",
            "4.6.3",
            allow_editing_template_files=False,
            save_component_to_system_templates=False,
        )
        filesystem.vehicle_components_fs.data = {
            "Components": {"Flight Controller": {"Firmware": {"Type": "ArduCopter", "Version": "4.6.3"}}}
        }

        with tempfile.TemporaryDirectory() as vehicle_dir:
            cache_key = ("ArduCopter", "4.6.3", get_xml_dir(vehicle_dir))
            filesystem._parameter_metadata_cache[cache_key] = {}
            metadata_file = os_path.join(vehicle_dir, "apm.pdef.xml")
            with open(metadata_file, "w", encoding="utf-8") as file:
                file.write("<parameters />")

            with patch.object(
                filesystem,
                "load_vehicle_components_json_data",
                return_value=filesystem.vehicle_components_fs.data,
            ):
                assert not filesystem.remove_cached_parameter_metadata_for_mismatched_firmware(vehicle_dir)

            assert os_path.exists(metadata_file)
            assert cache_key in filesystem._parameter_metadata_cache

    def test_metadata_cache_is_scoped_to_project_xml_directory(self) -> None:
        """Projects with different local metadata do not share parsed documentation."""
        filesystem = LocalFilesystem(
            None,
            "ArduCopter",
            "4.7.0",
            allow_editing_template_files=False,
            save_component_to_system_templates=False,
        )
        metadata = {"TEST_PARAM": {"humanName": "Test", "documentation": [], "fields": {}, "values": {}}}

        with (
            patch.object(filesystem, "load_vehicle_components_json_data", return_value=True),
            patch.object(filesystem, "rename_parameter_files"),
            patch.object(filesystem, "read_params_from_files", return_value={"01_setup.param": ParDict()}),
            patch("ardupilot_methodic_configurator.backend_filesystem.get_xml_dir", side_effect=["/one", "/two"]),
            patch("ardupilot_methodic_configurator.backend_filesystem.load_default_param_file", return_value=ParDict()),
            patch(
                "ardupilot_methodic_configurator.backend_filesystem.parse_parameter_metadata", return_value=metadata
            ) as parse,
        ):
            filesystem.re_init("/projects/one", "ArduCopter")
            filesystem.re_init("/projects/two", "ArduCopter")

        assert parse.call_count == 2

    def test_vehicle_configuration_files_exist(self) -> None:
        """Test checking if vehicle configuration files exist."""
        mock_vehicle_dir = "/mock/dir"
        filesystem = LocalFilesystem(
            mock_vehicle_dir,
            "ArduCopter",
            "4.3.0",
            allow_editing_template_files=False,
            save_component_to_system_templates=False,
        )

        # Create mock file objects with name attribute
        mock_file1 = MagicMock()
        mock_file1.name = "vehicle_components.json"
        mock_file1.is_file.return_value = True
        mock_file2 = MagicMock()
        mock_file2.name = "02_test.param"
        mock_file2.is_file.return_value = True

        mock_path = MagicMock()
        mock_path.exists.return_value = True
        mock_path.is_dir.return_value = True
        mock_path.iterdir.return_value = [mock_file1, mock_file2]

        with (
            patch("ardupilot_methodic_configurator.backend_filesystem.Path", return_value=mock_path),
            patch("ardupilot_methodic_configurator.backend_filesystem.platform_system", return_value="Linux"),
        ):
            assert filesystem.vehicle_configuration_files_exist(mock_vehicle_dir)

        # Test with invalid files
        mock_invalid_file = MagicMock()
        mock_invalid_file.name = "invalid.txt"
        mock_invalid_file.is_file.return_value = True

        mock_path_invalid = MagicMock()
        mock_path_invalid.exists.return_value = True
        mock_path_invalid.is_dir.return_value = True
        mock_path_invalid.iterdir.return_value = [mock_invalid_file]

        with patch("ardupilot_methodic_configurator.backend_filesystem.Path", return_value=mock_path_invalid):
            assert not filesystem.vehicle_configuration_files_exist(mock_vehicle_dir)

    def test_remove_created_files_and_vehicle_dir_not_exists(self) -> None:
        """
        Remove created files and vehicle directory if they exist.

        GIVEN: A LocalFilesystem whose vehicle directory does not exist
        WHEN: remove_created_files_and_vehicle_dir is called
        THEN: It should return a localized error message indicating the directory is missing.
        """
        mock_vehicle_dir = "/mock/dir"
        filesystem = LocalFilesystem(
            mock_vehicle_dir,
            "ArduCopter",
            "4.3.0",
            allow_editing_template_files=False,
            save_component_to_system_templates=False,
        )

        with (
            patch("ardupilot_methodic_configurator.backend_filesystem.os_path.exists", return_value=False) as mock_exists,
            patch("ardupilot_methodic_configurator.backend_filesystem.os_listdir") as mock_listdir,
        ):
            ret = filesystem.remove_created_files_and_vehicle_dir()
            # Should return a non-empty error message mentioning the removed vehicle directory
            assert isinstance(ret, str)
            assert "Vehicle directory to remove does not exist" in ret
            # listdir must not have been called when directory doesn't exist
            assert not mock_listdir.called
            mock_exists.assert_called()

    def test_remove_created_files_and_vehicle_dir_success(self) -> None:
        """
        Test removing created files and vehicle directory with success.

        GIVEN: A LocalFilesystem with files, a dir and a symlink in the vehicle directory
        WHEN: remove_created_files_and_vehicle_dir is called
        THEN: It should remove files/dirs/links and return an empty string on success.
        """
        mock_vehicle_dir = "/mock/dir"
        filesystem = LocalFilesystem(
            mock_vehicle_dir,
            "ArduCopter",
            "4.3.0",
            allow_editing_template_files=False,
            save_component_to_system_templates=False,
        )

        items = ["file1", "dir1", "link1"]

        real_join = os_path.join

        def join_side_effect(a, b) -> str:
            return real_join(a, b)

        def islink_side_effect(p) -> bool:
            return p.endswith("link1")

        def isdir_side_effect(p) -> bool:
            return p.endswith("dir1")

        with (
            patch("ardupilot_methodic_configurator.backend_filesystem.os_path.exists", return_value=True),
            patch("ardupilot_methodic_configurator.backend_filesystem.os_listdir", return_value=items),
            patch("ardupilot_methodic_configurator.backend_filesystem.os_path.join", side_effect=join_side_effect),
            patch("ardupilot_methodic_configurator.backend_filesystem.os_path.islink", side_effect=islink_side_effect),
            patch("ardupilot_methodic_configurator.backend_filesystem.os_path.isdir", side_effect=isdir_side_effect),
            patch("ardupilot_methodic_configurator.backend_filesystem.os_remove") as mock_remove,
            patch("ardupilot_methodic_configurator.backend_filesystem.shutil_rmtree") as mock_rmtree,
            patch("ardupilot_methodic_configurator.backend_filesystem.os_rmdir") as mock_rmdir,
        ):
            ret = filesystem.remove_created_files_and_vehicle_dir()
            assert ret == ""
            # file1 and link1 should trigger os_remove twice
            assert mock_remove.call_count == 2
            # dir1 should trigger shutil.rmtree
            mock_rmtree.assert_called_once()
            # vehicle directory removal attempted
            mock_rmdir.assert_called_once_with(mock_vehicle_dir)

    def test_remove_created_files_and_vehicle_dir_with_errors(self) -> None:
        """
        Test removing created files and vehicle directory with errors.

        GIVEN: A LocalFilesystem where removal operations raise OSError
        WHEN: remove_created_files_and_vehicle_dir is called
        THEN: It should collect error messages and return a combined error string.
        """
        mock_vehicle_dir = "/mock/dir"
        filesystem = LocalFilesystem(
            mock_vehicle_dir,
            "ArduCopter",
            "4.3.0",
            allow_editing_template_files=False,
            save_component_to_system_templates=False,
        )

        items = ["file_err"]

        real_join = os_path.join

        def join_side_effect(a, b) -> str:
            return real_join(a, b)

        with (
            patch("ardupilot_methodic_configurator.backend_filesystem.os_path.exists", return_value=True),
            patch("ardupilot_methodic_configurator.backend_filesystem.os_listdir", return_value=items),
            patch("ardupilot_methodic_configurator.backend_filesystem.os_path.join", side_effect=join_side_effect),
            patch("ardupilot_methodic_configurator.backend_filesystem.os_path.islink", return_value=False),
            patch("ardupilot_methodic_configurator.backend_filesystem.os_path.isdir", return_value=False),
            patch("ardupilot_methodic_configurator.backend_filesystem.os_remove", side_effect=OSError("perm denied")),
            patch("ardupilot_methodic_configurator.backend_filesystem.os_rmdir", side_effect=OSError("dir remove failed")),
            patch("ardupilot_methodic_configurator.backend_filesystem.logging_exception"),
            patch("ardupilot_methodic_configurator.backend_filesystem.logging_error"),
        ):
            ret = filesystem.remove_created_files_and_vehicle_dir()
            assert isinstance(ret, str)
            # Should indicate there was an error removing created files
            assert "Error removing created files" in ret
            # Both error messages should be present (joined by "; ")
            assert "perm denied" in ret
            assert "dir remove failed" in ret

    def test_rename_parameter_files(self) -> None:
        """Project parameter renames preserve Git history when available."""
        mock_vehicle_dir = "/mock/dir"
        filesystem = LocalFilesystem(
            mock_vehicle_dir,
            "ArduCopter",
            "4.3.0",
            allow_editing_template_files=True,
            save_component_to_system_templates=False,
        )
        filesystem.configuration_steps = {"new_file.param": {"old_filenames": ["old_file.param"]}}

        with (
            patch.object(filesystem, "vehicle_configuration_file_exists") as mock_exists,
            patch("ardupilot_methodic_configurator.backend_filesystem._rename_file_preserving_git_history") as mock_rename,
            patch("ardupilot_methodic_configurator.backend_filesystem.os_path.join", side_effect=os_path.join),
        ):
            mock_exists.side_effect = lambda x: x == "old_file.param"
            filesystem.rename_parameter_files()
            expected_old = Path(os_path.join("/mock/dir", "old_file.param"))
            expected_new = Path(os_path.join("/mock/dir", "new_file.param"))
            mock_rename.assert_called_once_with(expected_old, expected_new)

    def test_git_mv_failure_logs_and_falls_back_to_filesystem_rename(self) -> None:
        """A locked Git index must not prevent the file rename from completing."""
        source = Path("old_file.param")
        destination = Path("new_file.param")
        git_error = CalledProcessError(1, ["git", "mv"])

        with (
            patch("ardupilot_methodic_configurator.backend_filesystem.shutil_which", return_value="git"),
            patch("ardupilot_methodic_configurator.backend_filesystem.run", side_effect=[None, git_error]) as mock_run,
            patch("ardupilot_methodic_configurator.backend_filesystem.os_rename") as mock_rename,
            patch("ardupilot_methodic_configurator.backend_filesystem.logging_warning") as mock_warning,
        ):
            _rename_file_preserving_git_history(source, destination)

        mock_rename.assert_called_once_with(str(source), str(destination))
        mock_warning.assert_called_once()
        assert mock_run.call_count == 2
        for git_call in mock_run.call_args_list:
            command = git_call.args[0]
            assert "core.fsmonitor=false" in command
            assert f"core.hooksPath={os_devnull}" in command

    def test_vehicle_configuration_file_exists_comprehensive(self) -> None:
        """Test checking if a specific configuration file exists with comprehensive path and size checks."""
        mock_vehicle_dir = "/mock/dir"
        filesystem = LocalFilesystem(
            mock_vehicle_dir,
            "ArduCopter",
            "4.3.0",
            allow_editing_template_files=False,
            save_component_to_system_templates=False,
        )

        # Test with all conditions met (file exists, is a file, and has size > 0)
        with (
            patch("os.path.exists", return_value=True) as mock_exists,
            patch("os.path.isfile", return_value=True) as mock_isfile,
            patch("os.path.getsize", return_value=100) as mock_getsize,
            patch("os.path.join", side_effect=os_path.join) as mock_join,
        ):
            assert filesystem.vehicle_configuration_file_exists("test.param")
            mock_exists.assert_called_once()
            mock_isfile.assert_called_once()
            mock_getsize.assert_called_once()
            mock_join.assert_called_once_with(mock_vehicle_dir, "test.param")

        # Test with file that exists but is empty
        with (
            patch("os.path.exists", return_value=True),
            patch("os.path.isfile", return_value=True),
            patch("os.path.getsize", return_value=0),
            patch("os.path.join", side_effect=os_path.join),
        ):
            assert not filesystem.vehicle_configuration_file_exists("empty.param")

        # Test with directory instead of file
        with (
            patch("os.path.exists", return_value=True),
            patch("os.path.isfile", return_value=False),
            patch("os.path.join", side_effect=os_path.join),
        ):
            assert not filesystem.vehicle_configuration_file_exists("dir.param")

        # Test with nonexistent file
        with patch("os.path.exists", return_value=False), patch("os.path.join", side_effect=os_path.join):
            assert not filesystem.vehicle_configuration_file_exists("nonexistent.param")

    @patch("os.path.exists")
    @patch("os.path.isfile")
    def test_zip_file_exists(self, mock_isfile, mock_exists) -> None:
        mock_exists.return_value = True
        mock_isfile.return_value = True
        lfs = LocalFilesystem(
            "vehicle_dir", "vehicle_type", None, allow_editing_template_files=False, save_component_to_system_templates=False
        )
        result = lfs.zip_file_exists()
        assert result
        mock_exists.assert_called_once()
        mock_isfile.assert_called_once()

    @patch("os.path.exists")
    @patch("os.path.isfile")
    def test_vehicle_image_exists(self, mock_isfile, mock_exists) -> None:
        mock_exists.return_value = True
        mock_isfile.return_value = True
        lfs = LocalFilesystem(
            "vehicle_dir", "vehicle_type", None, allow_editing_template_files=False, save_component_to_system_templates=False
        )
        result = lfs.vehicle_image_exists()
        assert result
        mock_exists.assert_called_once()
        mock_isfile.assert_called_once()

    @patch("os.path.exists")
    @patch("os.path.isdir")
    def test_directory_exists(self, mock_isdir, mock_exists) -> None:
        mock_exists.return_value = True
        mock_isdir.return_value = True
        result = LocalFilesystem.directory_exists("test_directory")
        assert result
        mock_exists.assert_called_once_with("test_directory")
        mock_isdir.assert_called_once_with("test_directory")

    def test_getcwd(self) -> None:
        """Test getting current working directory."""
        mock_vehicle_dir = "/mock/dir"
        mock_cwd = "/test/dir"
        filesystem = LocalFilesystem(
            mock_vehicle_dir,
            "ArduCopter",
            "4.3.0",
            allow_editing_template_files=False,
            save_component_to_system_templates=False,
        )

        with patch("ardupilot_methodic_configurator.backend_filesystem.os_getcwd", return_value=mock_cwd) as mock_getcwd:
            result = filesystem.getcwd()
            assert result == mock_cwd
            mock_getcwd.assert_called_once()

    @patch("os.path.join")
    def test_new_vehicle_dir(self, mock_join) -> None:
        mock_join.return_value = "base_dir/new_dir"
        result = LocalFilesystem.new_vehicle_dir("base_dir", "new_dir")
        assert result == "base_dir/new_dir"
        mock_join.assert_called_once_with("base_dir", "new_dir")

    @patch("os.path.basename")
    @patch("os.path.split")
    @patch("os.path.normpath")
    def test_get_directory_name_from_full_path(self, mock_normpath, mock_split, mock_basename) -> None:
        mock_normpath.return_value = "normalized_path"
        mock_split.return_value = ("head", "tail")
        mock_basename.return_value = "tail"
        result = LocalFilesystem.get_directory_name_from_full_path("full_path")
        assert result == "tail"
        mock_normpath.assert_called_once_with("full_path")
        mock_split.assert_called_once_with("normalized_path")
        mock_basename.assert_called_once_with("tail")

    def test_vehicle_image_filepath(self) -> None:
        lfs = LocalFilesystem(
            "vehicle_dir", "vehicle_type", None, allow_editing_template_files=False, save_component_to_system_templates=False
        )
        with patch("os.path.join") as mock_join:
            mock_join.return_value = "vehicle_dir/vehicle.jpg"
            result = lfs.vehicle_image_filepath()
            assert result == "vehicle_dir/vehicle.jpg"
            mock_join.assert_called_once_with("vehicle_dir", "vehicle.jpg")

    def test_tempcal_imu_result_param_tuple(self) -> None:
        lfs = LocalFilesystem(
            "vehicle_dir", "vehicle_type", None, allow_editing_template_files=False, save_component_to_system_templates=False
        )
        with patch("os.path.join") as mock_join:
            mock_join.return_value = "vehicle_dir/03_imu_temperature_calibration_results.param"
            result = lfs.tempcal_imu_result_param_tuple()
            assert result == (
                "03_imu_temperature_calibration_results.param",
                "vehicle_dir/03_imu_temperature_calibration_results.param",
            )
            mock_join.assert_called_once_with("vehicle_dir", "03_imu_temperature_calibration_results.param")

    def test_zip_file_path(self) -> None:
        lfs = LocalFilesystem(
            "vehicle_dir", "vehicle_type", None, allow_editing_template_files=False, save_component_to_system_templates=False
        )
        with patch("os.path.join") as mock_join:
            mock_join.return_value = "vehicle_dir/vehicle_name.zip"
            lfs.get_vehicle_directory_name = MagicMock(return_value="vehicle_name")
            result = lfs.zip_file_path()
            assert result == "vehicle_dir/vehicle_name.zip"
            mock_join.assert_called_once_with("vehicle_dir", "vehicle_name.zip")

    def test_add_configuration_file_to_zip(self) -> None:
        lfs = LocalFilesystem(
            "vehicle_dir", "vehicle_type", None, allow_editing_template_files=False, save_component_to_system_templates=False
        )
        with patch("os.path.join") as mock_join:
            mock_join.return_value = "vehicle_dir/test_file.param"
            lfs.vehicle_configuration_file_exists = MagicMock(return_value=True)
            mock_zipfile = MagicMock()
            lfs.add_configuration_file_to_zip(mock_zipfile, "test_file.param")
            mock_join.assert_called_once_with("vehicle_dir", "test_file.param")
            mock_zipfile.write.assert_called_once_with("vehicle_dir/test_file.param", arcname="test_file.param")

    def test_get_upload_local_and_remote_filenames_missing_file(self) -> None:
        """Test get_upload_local_and_remote_filenames with missing file."""
        lfs = LocalFilesystem(
            "vehicle_dir", "vehicle_type", None, allow_editing_template_files=False, save_component_to_system_templates=False
        )
        result = lfs.get_upload_local_and_remote_filenames("missing_file")
        assert result == ("", "")

    def test_get_upload_local_and_remote_filenames_missing_upload_section(self) -> None:
        """Test get_upload_local_and_remote_filenames with missing upload section."""
        lfs = LocalFilesystem(
            "vehicle_dir", "vehicle_type", None, allow_editing_template_files=False, save_component_to_system_templates=False
        )
        lfs.configuration_steps = {"selected_file": {}}
        result = lfs.get_upload_local_and_remote_filenames("selected_file")
        assert result == ("", "")

    def test_get_download_url_and_local_filename_missing_file(self) -> None:
        """Test get_download_url_and_local_filename with missing file."""
        lfs = LocalFilesystem(
            "vehicle_dir", "vehicle_type", None, allow_editing_template_files=False, save_component_to_system_templates=False
        )
        result = lfs.get_download_url_and_local_filename("missing_file")
        assert result == ("", "")

    def test_get_download_url_and_local_filename_missing_download_section(self) -> None:
        """Test get_download_url_and_local_filename with missing download section."""
        lfs = LocalFilesystem(
            "vehicle_dir", "vehicle_type", None, allow_editing_template_files=False, save_component_to_system_templates=False
        )
        lfs.configuration_steps = {"selected_file": {}}
        result = lfs.get_download_url_and_local_filename("selected_file")
        assert result == ("", "")

    def test_write_and_read_last_uploaded_filename_error_handling(self) -> None:
        """Test error handling in write_and_read_last_uploaded_filename."""
        lfs = LocalFilesystem(
            "vehicle_dir", "vehicle_type", None, allow_editing_template_files=False, save_component_to_system_templates=False
        )
        test_filename = "test.param"

        # Test write error
        with patch("builtins.open", side_effect=OSError("Write error")):
            lfs.write_last_uploaded_filename(test_filename)
            # Should not raise exception, just log error

        # Test read error
        with patch("builtins.open", side_effect=OSError("Read error")):
            result = lfs._LocalFilesystem__read_last_uploaded_filename()  # pylint: disable=protected-access
            assert result == ""

    def test_get_start_file_empty_files(self) -> None:
        """Test get_start_file with empty files list."""
        lfs = LocalFilesystem(
            "vehicle_dir", "vehicle_type", None, allow_editing_template_files=False, save_component_to_system_templates=False
        )
        lfs.file_parameters = {}
        result = lfs.get_start_file(1, tcal_available=True)
        assert result == ""

    def test_get_start_file_empty_files_no_explicit_index(self) -> None:
        """
        Regression: get_start_file must not crash with an empty file list.

        GIVEN: A vehicle directory with no intermediate parameter files
        WHEN: get_start_file is called with the implicit (-1) index
        THEN: An empty string is returned for both tcal branches instead of an
              IndexError on files[0] / files[2].
        """
        lfs = LocalFilesystem(
            "vehicle_dir", "vehicle_type", None, allow_editing_template_files=False, save_component_to_system_templates=False
        )
        lfs.file_parameters = {}

        assert lfs.get_start_file(-1, tcal_available=True) == ""
        assert lfs.get_start_file(-1, tcal_available=False) == ""

    def test_get_start_file_fewer_than_three_files_no_tcal(self) -> None:
        """
        Regression: get_start_file must not raise IndexError on files[2].

        It must not raise when fewer than three intermediate parameter files
        exist and IMU temperature calibration is not available.

        GIVEN: A vehicle directory with one or two parameter files
        WHEN: get_start_file is called with implicit index and tcal_available=False
        THEN: A valid filename is returned (the last file) rather than crashing.
        """
        lfs = LocalFilesystem(
            "vehicle_dir", "vehicle_type", None, allow_editing_template_files=False, save_component_to_system_templates=False
        )

        lfs.file_parameters = {"01_only.param": {}}
        assert lfs.get_start_file(-1, tcal_available=False) == "01_only.param"

        lfs.file_parameters = {"01_a.param": {}, "02_b.param": {}}
        assert lfs.get_start_file(-1, tcal_available=False) == "02_b.param"

    def test_get_eval_variables_with_none(self) -> None:
        """Test get_eval_variables with None values."""
        lfs = LocalFilesystem(
            "vehicle_dir", "vehicle_type", None, allow_editing_template_files=False, save_component_to_system_templates=False
        )
        lfs.vehicle_components_fs.data = None
        lfs.doc_dict = None
        result = lfs.get_eval_variables()
        assert not result

    def test_tolerance_check_with_zero_values(self) -> None:
        """Test numerical value comparison with zero values."""
        lfs = LocalFilesystem(
            "vehicle_dir", "vehicle_type", None, allow_editing_template_files=False, save_component_to_system_templates=False
        )

        # Test zero values
        x, y = 0.0, 0.0
        assert abs(x - y) <= 1e-08 + (1e-03 * abs(y))

        # Test small positive vs zero
        x, y = 1e-10, 0.0
        assert abs(x - y) <= 1e-08 + (1e-03 * abs(y))

        # Test writing
        test_filename = "test_param.param"
        expected_path = os_path.join("vehicle_dir", "last_uploaded_filename.txt")
        with patch("builtins.open", mock_open()) as mock_file:
            lfs.write_last_uploaded_filename(test_filename)
            mock_file.assert_called_once_with(expected_path, "w", encoding="utf-8", newline="\n")
            mock_file().write.assert_called_once_with(test_filename)

        # Test reading
        with patch("builtins.open", mock_open(read_data=test_filename)) as mock_file:
            result = lfs._LocalFilesystem__read_last_uploaded_filename()  # pylint: disable=protected-access
            assert result == test_filename
            mock_file.assert_called_once_with(expected_path, encoding="utf-8")

    def test_set_param_default_values_if_different(self) -> None:
        lfs = LocalFilesystem(
            "vehicle_dir", "vehicle_type", None, allow_editing_template_files=False, save_component_to_system_templates=False
        )

        # Test with new values
        new_values = {"PARAM1": MagicMock(value=1.0)}
        result = lfs.set_param_default_values_if_different(new_values)
        assert result is True
        assert lfs.param_default_dict == new_values

        # Test with same values (no change)
        result = lfs.set_param_default_values_if_different(new_values)
        assert result is False

    def test_get_start_file(self) -> None:
        lfs = LocalFilesystem(
            "vehicle_dir", "vehicle_type", None, allow_editing_template_files=False, save_component_to_system_templates=False
        )
        lfs.file_parameters = {"01_file.param": {}, "02_file.param": {}, "03_file.param": {}}

        # Test with explicit index
        result = lfs.get_start_file(1, tcal_available=True)
        assert result == "02_file.param"

        # Test with out of range index
        result = lfs.get_start_file(5, tcal_available=True)
        assert result == "03_file.param"

        # Test with tcal available
        result = lfs.get_start_file(-1, tcal_available=True)
        assert result == "01_file.param"

        # Test with tcal not available
        result = lfs.get_start_file(-1, tcal_available=False)
        assert result == "03_file.param"

    def test_get_start_file_after_final_file_skips_default(self) -> None:
        """
        After the sequence completes, restart skips 00_default.param (see #1507).

        The configuration flow records the last uploaded filename on every step.
        When the user reaches the final step (``53_everyday_use.param``) and
        relaunches the program, ``get_start_file`` should not present the
        read-only ``00_default.param`` snapshot -- that is not an editable
        configuration step.
        """
        lfs = LocalFilesystem(
            "vehicle_dir", "vehicle_type", None, allow_editing_template_files=False, save_component_to_system_templates=False
        )
        lfs.file_parameters = {
            "00_default.param": {},
            "01_tcal.param": {},
            "02_first_real.param": {},
            "53_everyday_use.param": {},
        }

        # tcal available -> start_file = files[0] = 00_default.param, so we must
        # move off it to the first non-default file.
        with patch.object(lfs, "_LocalFilesystem__read_last_uploaded_filename", return_value="53_everyday_use.param"):
            result = lfs.get_start_file(-1, tcal_available=True)
        assert result != "00_default.param"
        assert result == "01_tcal.param"

        # tcal NOT available -> start_file is already files[2] (first non-tcal
        # editable step), which is the correct wraparound target. The fix must
        # not clobber that by walking forward and landing on 01_tcal.param.
        with patch.object(lfs, "_LocalFilesystem__read_last_uploaded_filename", return_value="53_everyday_use.param"):
            result = lfs.get_start_file(-1, tcal_available=False)
        assert result == "02_first_real.param"

        # When 00_default.param is the only remaining entry, raise rather than
        # silently hand the user a non-editable file to edit.
        lfs.file_parameters = {"00_default.param": {}}
        with (
            patch.object(lfs, "_LocalFilesystem__read_last_uploaded_filename", return_value="00_default.param"),
            pytest.raises(ValueError, match=r"00_default\.param"),
        ):
            lfs.get_start_file(-1, tcal_available=True)

    def test_get_eval_variables(self) -> None:
        lfs = LocalFilesystem(
            "vehicle_dir", "vehicle_type", None, allow_editing_template_files=False, save_component_to_system_templates=False
        )

        # Test with empty components and doc_dict
        result = lfs.get_eval_variables()
        assert not result

        # Test with components and doc_dict
        lfs.vehicle_components_fs.data = {"Components": {"test": "value"}}
        lfs.doc_dict = {"param": "doc"}
        result = lfs.get_eval_variables()
        assert "vehicle_components" in result
        assert "doc_dict" in result
        assert result["vehicle_components"] == {"test": "value"}
        assert result["doc_dict"] == {"param": "doc"}

    def test_tolerance_check(self) -> None:
        """Test numerical value comparison with tolerances."""
        LocalFilesystem(
            "vehicle_dir", "vehicle_type", None, allow_editing_template_files=False, save_component_to_system_templates=False
        )

        # Test exact match
        x, y = 1.0, 1.0
        assert abs(x - y) <= 1e-08 + (1e-03 * abs(y))

        # Test within absolute tolerance
        x, y = 1.0, 1.00000001
        assert abs(x - y) <= 1e-08 + (1e-03 * abs(y))

        # Test within relative tolerance
        x, y = 1.0, 1.001
        assert abs(x - y) <= 1e-08 + (1e-03 * abs(y))

        # Test outside both tolerances
        x, y = 1.0, 1.1
        assert not abs(x - y) <= 1e-08 + (1e-03 * abs(y))

        # Test with custom tolerances
        x, y = 1.0, 1.5
        assert abs(x - y) <= 1.0 + (1e-03 * abs(y))  # atol=1.0
        x, y = 1.0, 2.0
        assert abs(x - y) <= 1e-08 + (1.0 * abs(y))  # rtol=1.0

    def test_categorize_parameters(self) -> None:
        lfs = LocalFilesystem(
            "vehicle_dir", "vehicle_type", None, allow_editing_template_files=False, save_component_to_system_templates=False
        )
        lfs.param_default_dict = {"PARAM1": MagicMock(value=1.0)}
        lfs.doc_dict = {"PARAM1": {"ReadOnly": True}, "PARAM2": {"Calibration": True}, "PARAM3": {}}

        test_params = ParDict({"PARAM1": Par(2.0), "PARAM2": Par(2.0), "PARAM3": Par(2.0)})

        readonly, calibration, ids, other = lfs.categorize_parameters(test_params)

        assert "PARAM1" in readonly
        assert "PARAM2" in calibration
        assert "PARAM3" in other
        assert not ids

    def test_calculate_derived_and_forced_param_changes(self) -> None:
        lfs = LocalFilesystem(
            "vehicle_dir", "vehicle_type", None, allow_editing_template_files=False, save_component_to_system_templates=False
        )
        # Test with empty file_parameters - returns empty dict
        result = lfs.calculate_derived_and_forced_param_changes([])
        assert not result  # Empty dict means no pending changes

        # Test with file_parameters and configuration steps:
        # Phase 1 must NOT mutate self.file_parameters
        param1 = Par(0.0, None)
        param2 = Par(0.0, None)

        # Create a ParDict instead of a regular dict
        param_dict = ParDict({"PARAM1": param1, "PARAM2": param2})
        lfs.file_parameters = {"test.param": param_dict}
        lfs.configuration_steps = {"test.param": {"forced": {}, "derived": {}}}

        lfs.derived_parameters = {"test.param": {"PARAM1": Par(1.0, None), "PARAM2": Par(2.0, None)}}
        lfs.compute_parameters = MagicMock(return_value="")
        result = lfs.calculate_derived_and_forced_param_changes([])
        # Derived values (1.0, 2.0) differ from loaded values (0.0, 0.0) so pending is non-empty
        assert result  # Non-empty dict means pending changes detected
        assert "test.param" in result
        # Original Par objects in file_parameters must be untouched
        assert param1.value == 0.0  # NOT mutated by Phase 1
        assert param2.value == 0.0  # NOT mutated by Phase 1

        # apply_computed_changes updates file_parameters
        computed = ParDict({"PARAM1": Par(1.0, None), "PARAM2": Par(2.0, None)})
        lfs.apply_computed_changes({"test.param": computed})
        assert lfs.file_parameters["test.param"] is computed

        # save_vehicle_params_to_files writes the current file_parameters to disk
        with (
            patch.object(computed, "export_to_param") as mock_export,
            patch("ardupilot_methodic_configurator.backend_filesystem.ParDict._format_params") as mock_format,
        ):
            mock_format.return_value = "formatted_params"
            lfs.save_vehicle_params_to_files(list(lfs.file_parameters))
            mock_export.assert_called_once_with(os_path.join("vehicle_dir", "test.param"))

    def test_write_param_default_values_to_file(self) -> None:
        lfs = LocalFilesystem(
            "vehicle_dir", "vehicle_type", None, allow_editing_template_files=False, save_component_to_system_templates=False
        )
        param_mock = MagicMock()
        param_mock.value = 1.0
        # Create a ParDict instead of a regular dict
        param_default_values = ParDict({"PARAM1": param_mock})

        with (
            patch("ardupilot_methodic_configurator.backend_filesystem.ParDict.export_to_param") as mock_export,
        ):
            # Test with new values
            lfs.write_param_default_values_to_file(param_default_values)
            assert lfs.param_default_dict == param_default_values
            mock_export.assert_called_with(os_path.join("vehicle_dir", "00_default.param"))

            # Test with same values (no change)
            mock_export.reset_mock()
            lfs.write_param_default_values_to_file(param_default_values)
            mock_export.assert_not_called()

    def test_export_to_param(self) -> None:
        lfs = LocalFilesystem(
            "vehicle_dir", "vehicle_type", None, allow_editing_template_files=False, save_component_to_system_templates=False
        )
        param_mock = MagicMock()
        param_mock.value = 1.0
        test_params = ParDict({"PARAM1": param_mock})

        with (
            patch.object(test_params, "export_to_param") as mock_export,
            patch("ardupilot_methodic_configurator.backend_filesystem.update_parameter_documentation") as mock_update,
        ):
            # Test with documentation annotation
            lfs.export_to_param(test_params, "test.param", annotate_doc=True)
            mock_export.assert_called_with(os_path.join("vehicle_dir", "test.param"))
            mock_update.assert_called_once()

            # Test without documentation annotation
            mock_export.reset_mock()
            mock_update.reset_mock()
            lfs.export_to_param(test_params, "test.param", annotate_doc=False)
            mock_export.assert_called_with(os_path.join("vehicle_dir", "test.param"))
            mock_update.assert_not_called()

    def test_all_intermediate_parameter_file_comments(self) -> None:
        lfs = LocalFilesystem(
            "vehicle_dir", "vehicle_type", None, allow_editing_template_files=False, save_component_to_system_templates=False
        )
        lfs.file_parameters = {
            "file1.param": {"PARAM1": MagicMock(comment="Comment 1"), "PARAM2": MagicMock(comment="Comment 2")},
            "file2.param": {"PARAM2": MagicMock(comment="Override comment 2"), "PARAM3": MagicMock(comment="Comment 3")},
        }

        result = lfs._LocalFilesystem__all_intermediate_parameter_file_comments()  # pylint: disable=protected-access
        assert result == {"PARAM1": "Comment 1", "PARAM2": "Override comment 2", "PARAM3": "Comment 3"}

    def test_get_git_commit_hash(self) -> None:
        test_hash = "abcdef1234567890"

        # Test with valid git repo
        with patch("ardupilot_methodic_configurator.backend_filesystem.run") as mock_run:
            mock_run.return_value.returncode = 0
            mock_run.return_value.stdout = test_hash + "\n"
            result = LocalFilesystem.get_git_commit_hash()
            assert result == test_hash
            mock_run.assert_called_once()

        # Test with no git repo but git_hash.txt exists
        with patch("ardupilot_methodic_configurator.backend_filesystem.run") as mock_run:
            mock_run.side_effect = SubprocessError()
            with patch("builtins.open", mock_open(read_data=test_hash)):
                result = LocalFilesystem.get_git_commit_hash()
                assert result == test_hash

        # Test with no git repo and no git_hash.txt
        with patch("ardupilot_methodic_configurator.backend_filesystem.run") as mock_run:
            mock_run.side_effect = SubprocessError()
            with patch("builtins.open") as mock_file:
                mock_file.side_effect = FileNotFoundError()
                result = LocalFilesystem.get_git_commit_hash()
                assert result == ""

    def test_extend_and_reformat_parameter_documentation_metadata(self) -> None:
        lfs = LocalFilesystem(
            "vehicle_dir", "vehicle_type", None, allow_editing_template_files=False, save_component_to_system_templates=False
        )

        test_doc_dict = {
            "PARAM1": {
                "humanName": "Test Param",
                "documentation": ["Test documentation"],
                "fields": {
                    "Units": "m/s (meters per second)",
                    "Range": "0 100",
                    "Calibration": "true",
                    "ReadOnly": "yes",
                    "RebootRequired": "1",
                    "Bitmask": "0:Option1, 1:Option2",
                },
                "values": {"1": "Value1", "2": "Value2"},
            }
        }

        lfs.doc_dict = test_doc_dict
        lfs.param_default_dict = {"PARAM1": MagicMock(value=50.0)}

        lfs._LocalFilesystem__extend_and_reformat_parameter_documentation_metadata()  # pylint: disable=protected-access

        result = lfs.doc_dict["PARAM1"]
        assert result["unit"] == "m/s"
        assert result["unit_tooltip"] == "meters per second"
        assert result["min"] == 0.0
        assert result["max"] == 100.0
        assert result["Calibration"] is True
        assert result["ReadOnly"] is True
        assert result["RebootRequired"] is True
        assert result["Bitmask"] == {0: "Option1", 1: "Option2"}
        assert result["Values"] == {1: "Value1", 2: "Value2"}
        assert "Default: 50" in result["doc_tooltip"]

    def test_add_argparse_arguments(self) -> None:
        parser = ArgumentParser()
        LocalFilesystem.add_argparse_arguments(parser)

        # Verify all expected arguments are added
        args = vars(parser.parse_args([]))
        assert "vehicle_type" in args
        assert "vehicle_dir" in args
        assert "n" in args
        assert "allow_editing_template_files" in args

        # Test default values
        assert args["vehicle_type"] == ""
        assert args["n"] == -1
        assert args["allow_editing_template_files"] is False

        # Test with parameters
        args = vars(parser.parse_args(["-t", "ArduCopter", "--n", "1", "--allow-editing-template-files"]))
        assert args["vehicle_type"] == "ArduCopter"
        assert args["n"] == 1
        assert args["allow_editing_template_files"] is True

    def test_bin_log_help_explains_the_explicit_vehicle_directory_destination(self) -> None:
        """The CLI help documents how --vehicle-dir changes a .bin-log project's destination."""
        parser = ArgumentParser()
        LocalFilesystem.add_argparse_arguments(parser)

        help_text = " ".join(parser.format_help().split())

        assert "an explicitly supplied value is the complete destination project directory" in help_text
        assert "explicitly supplied --vehicle-dir" in help_text
        assert "By default, the project is created in the default vehicles directory" in help_text
        assert "validates the vehicle type reported by the log" in help_text

    def test_annotate_intermediate_comments_to_param_dict(self) -> None:
        lfs = LocalFilesystem(
            "vehicle_dir", "vehicle_type", None, allow_editing_template_files=False, save_component_to_system_templates=False
        )

        # Set up mock comments in file_parameters
        mock_param1 = MagicMock()
        mock_param1.comment = "Comment 1"
        mock_param2 = MagicMock()
        mock_param2.comment = "Comment 2"

        lfs.file_parameters = {"file1.param": {"PARAM1": mock_param1}, "file2.param": {"PARAM2": mock_param2}}

        input_dict = {"PARAM1": 1.0, "PARAM2": 2.0, "PARAM3": 3.0}
        result = lfs.annotate_intermediate_comments_to_param_dict(input_dict)

        assert len(result) == 3
        assert result["PARAM1"].value == 1.0
        assert result["PARAM1"].comment == "Comment 1"
        assert result["PARAM2"].value == 2.0
        assert result["PARAM2"].comment == "Comment 2"
        assert result["PARAM3"].value == 3.0
        assert result["PARAM3"].comment == ""

    def test_find_lowest_available_backup_number(self) -> None:
        """Test finding the lowest available backup number."""
        lfs = LocalFilesystem(
            "vehicle_dir", "vehicle_type", None, allow_editing_template_files=False, save_component_to_system_templates=False
        )

        # Test when no backups exist
        with patch.object(lfs, "vehicle_configuration_file_exists", return_value=False):
            result = lfs.find_lowest_available_backup_number()
            assert result == 1

        # Test when backups 1-3 exist, but 4 doesn't
        with patch.object(
            lfs, "vehicle_configuration_file_exists", side_effect=lambda x: int(x.split("_")[1].split(".")[0]) < 4
        ):
            result = lfs.find_lowest_available_backup_number()
            assert result == 4

        # Test when all backups up to limit exist
        with patch.object(lfs, "vehicle_configuration_file_exists", return_value=True):
            result = lfs.find_lowest_available_backup_number()
            assert result == 99  # Should return the cap value

    def test_backup_fc_parameters_to_file(self) -> None:
        """Test backing up flight controller parameters to a file."""
        lfs = LocalFilesystem(
            "vehicle_dir", "vehicle_type", None, allow_editing_template_files=False, save_component_to_system_templates=False
        )
        test_params = {"PARAM1": 1.0, "PARAM2": 2.0}

        # Test when file doesn't exist and no last uploaded filename
        with (
            patch.object(lfs, "vehicle_configuration_file_exists", return_value=False),
            patch.object(lfs, "_LocalFilesystem__read_last_uploaded_filename", return_value=""),
            patch("ardupilot_methodic_configurator.backend_filesystem.ParDict.export_to_param") as mock_export,
            patch("ardupilot_methodic_configurator.backend_filesystem.ParDict._format_params") as mock_format,
        ):
            mock_format.return_value = "formatted_params"
            lfs.backup_fc_parameters_to_file(test_params, "backup.param")
            mock_export.assert_called_once()

        # Test with existing file (should not overwrite by default)
        with (
            patch.object(lfs, "vehicle_configuration_file_exists", return_value=True),
            patch.object(lfs, "_LocalFilesystem__read_last_uploaded_filename", return_value=""),
            patch("ardupilot_methodic_configurator.backend_filesystem.ParDict.export_to_param") as mock_export,
        ):
            lfs.backup_fc_parameters_to_file(test_params, "backup.param")
            mock_export.assert_not_called()

        # Test with force overwrite
        with (
            patch.object(lfs, "vehicle_configuration_file_exists", return_value=True),
            patch.object(lfs, "_LocalFilesystem__read_last_uploaded_filename", return_value=""),
            patch("ardupilot_methodic_configurator.backend_filesystem.ParDict.export_to_param") as mock_export,
            patch("ardupilot_methodic_configurator.backend_filesystem.ParDict._format_params") as mock_format,
        ):
            mock_format.return_value = "formatted_params"
            lfs.backup_fc_parameters_to_file(test_params, "backup.param", overwrite_existing_file=True)
            mock_export.assert_called_once()

        # Test with last uploaded filename exists and even_if_last_uploaded_filename_exists=False
        with (
            patch.object(lfs, "vehicle_configuration_file_exists", return_value=False),
            patch.object(lfs, "_LocalFilesystem__read_last_uploaded_filename", return_value="last_file.param"),
            patch("ardupilot_methodic_configurator.backend_filesystem.ParDict.export_to_param") as mock_export,
        ):
            lfs.backup_fc_parameters_to_file(test_params, "backup.param", even_if_last_uploaded_filename_exists=False)
            mock_export.assert_not_called()

    def test_zip_files(self) -> None:
        """Test zipping files functionality."""
        lfs = LocalFilesystem(
            "vehicle_dir", "vehicle_type", None, allow_editing_template_files=False, save_component_to_system_templates=False
        )

        # Setup mock file parameters and file paths
        lfs.file_parameters = {"01_file.param": {}, "02_file.param": {}}
        lfs.get_vehicle_directory_name = MagicMock(return_value="test_vehicle")

        with (
            patch("ardupilot_methodic_configurator.backend_filesystem.ZipFile") as mock_zipfile,
            patch.object(lfs, "add_configuration_file_to_zip") as mock_add_file,
            patch("os.path.join", return_value="vehicle_dir/test_vehicle.zip"),
        ):
            mock_zipfile_instance = MagicMock()
            mock_zipfile.return_value.__enter__.return_value = mock_zipfile_instance

            # Test with valid files_to_zip list
            files_to_zip = [(True, "summary1.txt"), (False, "summary2.txt")]
            lfs.zip_files(files_to_zip)

            # Should call add_configuration_file_to_zip for each parameter file
            assert mock_add_file.call_count >= 2
            # Should add all files where the first tuple value is True
            mock_add_file.assert_any_call(mock_zipfile_instance, "summary1.txt")
            # Should not add files where the first tuple value is False
            for call_args in mock_add_file.call_args_list:
                assert call_args[0][1] != "summary2.txt"

    def test_get_download_url_and_local_filename_with_valid_config(self) -> None:
        """Test get_download_url_and_local_filename with valid configuration."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            lfs = LocalFilesystem(
                tmp_dir, "vehicle_type", None, allow_editing_template_files=False, save_component_to_system_templates=False
            )
            lfs.configuration_steps = {
                "test_file.param": {
                    "download_file": [{"source_url": "https://example.com/file.bin", "dest_local": "local_file.bin"}]
                }
            }

            url, local_path = lfs.get_download_url_and_local_filename("test_file.param")
            assert url == "https://example.com/file.bin"
            assert local_path == os_path.realpath(os_path.join(tmp_dir, "local_file.bin"))

    def test_get_upload_local_and_remote_filenames_with_valid_config(self) -> None:
        """Test get_upload_local_and_remote_filenames with valid configuration."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            lfs = LocalFilesystem(
                tmp_dir, "vehicle_type", None, allow_editing_template_files=False, save_component_to_system_templates=False
            )
            lfs.configuration_steps = {
                "test_file.param": {
                    "upload_file": [{"source_local": "local_file.bin", "dest_on_fc": "/fs/microsd/APM/file.bin"}]
                }
            }

            local_path, remote_path = lfs.get_upload_local_and_remote_filenames("test_file.param")
            assert local_path == os_path.realpath(os_path.join(tmp_dir, "local_file.bin"))
            assert remote_path == "/fs/microsd/APM/file.bin"

    def test_multiple_step_files_are_resolved_in_order(self) -> None:
        """Both scripts are resolved relative to the vehicle directory."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            lfs = LocalFilesystem(
                tmp_dir, "vehicle_type", None, allow_editing_template_files=False, save_component_to_system_templates=False
            )
            lfs.configuration_steps = {
                "step.param": {
                    "download_file": [
                        {"source_url": "https://example.com/a", "dest_local": "a.lua"},
                        {"source_url": "https://example.com/b", "dest_local": "b.lua"},
                    ],
                    "upload_file": [
                        {"source_local": "a.lua", "dest_on_fc": "/APM/Scripts/a.lua"},
                        {"source_local": "b.lua", "dest_on_fc": "/APM/Scripts/b.lua"},
                    ],
                }
            }
            assert lfs.get_download_files("step.param") == [
                ("https://example.com/a", os_path.realpath(os_path.join(tmp_dir, "a.lua"))),
                ("https://example.com/b", os_path.realpath(os_path.join(tmp_dir, "b.lua"))),
            ]
            assert lfs.get_upload_files("step.param") == [
                (os_path.realpath(os_path.join(tmp_dir, "a.lua")), "/APM/Scripts/a.lua"),
                (os_path.realpath(os_path.join(tmp_dir, "b.lua")), "/APM/Scripts/b.lua"),
            ]

    def test_second_file_cannot_escape_vehicle_directory(self) -> None:
        """Validate every array entry, not just the first."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            lfs = LocalFilesystem(
                tmp_dir, "vehicle_type", None, allow_editing_template_files=False, save_component_to_system_templates=False
            )
            lfs.configuration_steps = {
                "step.param": {
                    "download_file": [
                        {"source_url": "https://example.com/a", "dest_local": "a.lua"},
                        {"source_url": "https://example.com/b", "dest_local": "../escape.lua"},
                    ]
                }
            }
            with pytest.raises(ValueError, match="escapes vehicle directory"):
                lfs.get_download_files("step.param")


class TestPathTraversalPrevention:
    """Tests that file path operations reject path traversal attempts."""

    def test_download_rejects_path_traversal_via_dest_local(self, tmp_path) -> None:
        """
        Path traversal via dest_local is blocked.

        GIVEN: A configuration step with dest_local containing '..' components
        WHEN: get_download_url_and_local_filename is called
        THEN: A ValueError is raised to prevent writing outside vehicle_dir
        """
        lfs = LocalFilesystem(
            str(tmp_path), "vehicle_type", None, allow_editing_template_files=False, save_component_to_system_templates=False
        )
        lfs.configuration_steps = {
            "test.param": {"download_file": [{"source_url": "https://example.com/payload", "dest_local": "../../.bashrc"}]}
        }

        with pytest.raises(ValueError, match="Path escapes vehicle directory"):
            lfs.get_download_url_and_local_filename("test.param")

    def test_upload_rejects_path_traversal_via_source_local(self, tmp_path) -> None:
        """
        Path traversal via source_local is blocked.

        GIVEN: A configuration step with source_local containing '..' components
        WHEN: get_upload_local_and_remote_filenames is called
        THEN: A ValueError is raised to prevent reading outside vehicle_dir
        """
        lfs = LocalFilesystem(
            str(tmp_path), "vehicle_type", None, allow_editing_template_files=False, save_component_to_system_templates=False
        )
        lfs.configuration_steps = {
            "test.param": {"upload_file": [{"source_local": "../../../etc/passwd", "dest_on_fc": "/fs/microsd/file"}]}
        }

        with pytest.raises(ValueError, match="Path escapes vehicle directory"):
            lfs.get_upload_local_and_remote_filenames("test.param")

    def test_download_allows_valid_dest_local(self, tmp_path) -> None:
        """
        Valid dest_local paths within vehicle_dir are allowed.

        GIVEN: A configuration step with a safe dest_local filename
        WHEN: get_download_url_and_local_filename is called
        THEN: The resolved path is returned without error
        """
        lfs = LocalFilesystem(
            str(tmp_path), "vehicle_type", None, allow_editing_template_files=False, save_component_to_system_templates=False
        )
        lfs.configuration_steps = {
            "test.param": {"download_file": [{"source_url": "https://example.com/file.lua", "dest_local": "script.lua"}]}
        }

        url, local_path = lfs.get_download_url_and_local_filename("test.param")
        assert url == "https://example.com/file.lua"
        assert local_path == str(tmp_path / "script.lua")

    def test_download_rejects_absolute_path(self, tmp_path) -> None:
        """
        Absolute dest_local paths are blocked.

        GIVEN: A configuration step with an absolute dest_local path
        WHEN: get_download_url_and_local_filename is called
        THEN: A ValueError is raised
        """
        lfs = LocalFilesystem(
            str(tmp_path), "vehicle_type", None, allow_editing_template_files=False, save_component_to_system_templates=False
        )
        lfs.configuration_steps = {
            "test.param": {
                "download_file": [{"source_url": "https://example.com/payload", "dest_local": "/tmp/evil"}],  # noqa: S108
            }
        }

        with pytest.raises(ValueError, match="Path escapes vehicle directory"):
            lfs.get_download_url_and_local_filename("test.param")

    def test_download_rejects_dest_local_resolving_to_base_dir(self, tmp_path) -> None:
        """
        dest_local='.' resolves to vehicle_dir itself and is rejected.

        GIVEN: A configuration step with dest_local='.' (resolves to base directory)
        WHEN: get_download_url_and_local_filename is called
        THEN: A ValueError is raised because a directory path is not a valid file target
        """
        lfs = LocalFilesystem(
            str(tmp_path), "vehicle_type", None, allow_editing_template_files=False, save_component_to_system_templates=False
        )
        lfs.configuration_steps = {
            "test.param": {"download_file": [{"source_url": "https://example.com/payload", "dest_local": "."}]}
        }

        with pytest.raises(ValueError, match="Path escapes vehicle directory"):
            lfs.get_download_url_and_local_filename("test.param")

    def test_download_rejects_symlink_escape(self, tmp_path) -> None:
        """
        Symlink pointing outside vehicle_dir is blocked.

        GIVEN: A symlink inside vehicle_dir that points to an external directory
        WHEN: dest_local references a file through the symlink
        THEN: A ValueError is raised because the resolved path escapes vehicle_dir
        """
        # Create a symlink inside tmp_path pointing outside vehicle_dir
        symlink_path = tmp_path / "escape_link"
        try:
            symlink_path.symlink_to(tempfile.gettempdir())
        except OSError:
            pytest.skip("Cannot create symlinks in this environment")

        lfs = LocalFilesystem(
            str(tmp_path), "vehicle_type", None, allow_editing_template_files=False, save_component_to_system_templates=False
        )
        lfs.configuration_steps = {
            "test.param": {"download_file": [{"source_url": "https://example.com/payload", "dest_local": "escape_link/evil"}]}
        }

        with pytest.raises(ValueError, match="Path escapes vehicle directory"):
            lfs.get_download_url_and_local_filename("test.param")


class TestTransformParamDict:
    """Unit tests for LocalFilesystem._transform_param_dict (pure in-memory, no filesystem)."""

    def test_blank_change_reason_strips_all_comments(self) -> None:
        """
        Blank-change-reason strips every comment from the parameter dict.

        GIVEN: A ParDict where every parameter has a comment
        WHEN: _transform_param_dict is called with blank_change_reason=True
        THEN: All comments should be None in the result
        """
        params = ParDict({"PARAM1": Par(1.0, "keep me not"), "PARAM2": Par(2.0, "and me too")})
        LocalFilesystem._transform_param_dict(params, blank_change_reason=True, use_fc_params=False, fc_parameters=None)
        assert params["PARAM1"].comment is None
        assert params["PARAM2"].comment is None
        assert params["PARAM1"].value == 1.0
        assert params["PARAM2"].value == 2.0

    def test_blank_change_reason_false_preserves_comments(self) -> None:
        """
        When blank_change_reason is False comments are left untouched.

        GIVEN: A ParDict where parameters have comments
        WHEN: _transform_param_dict is called with blank_change_reason=False
        THEN: Comments should remain unchanged
        """
        params = ParDict({"PARAM1": Par(1.0, "keep me")})
        LocalFilesystem._transform_param_dict(params, blank_change_reason=False, use_fc_params=False, fc_parameters=None)
        assert params["PARAM1"].comment == "keep me"

    def test_use_fc_params_substitutes_differing_values(self) -> None:
        """
        FC values that differ beyond tolerance replace template values.

        GIVEN: A ParDict with PARAM1=1.0
        WHEN: _transform_param_dict is called with use_fc_params=True and fc_parameters={PARAM1: 42.0}
        THEN: PARAM1 value should be 42.0
        """
        params = ParDict({"PARAM1": Par(1.0, "original")})
        LocalFilesystem._transform_param_dict(
            params, blank_change_reason=False, use_fc_params=True, fc_parameters={"PARAM1": 42.0}
        )
        assert params["PARAM1"].value == 42.0
        assert params["PARAM1"].comment == "original"  # comment preserved

    def test_use_fc_params_preserves_within_tolerance_values(self) -> None:
        """
        FC values within tolerance do not replace template values.

        GIVEN: A ParDict with PARAM1=2.0
        WHEN: _transform_param_dict is called with an FC value of 2.000001 (within tolerance)
        THEN: PARAM1 value should remain 2.0
        """
        params = ParDict({"PARAM1": Par(2.0)})
        LocalFilesystem._transform_param_dict(
            params, blank_change_reason=False, use_fc_params=True, fc_parameters={"PARAM1": 2.000001}
        )
        assert params["PARAM1"].value == 2.0

    def test_use_fc_params_does_not_add_params_absent_from_template(self) -> None:
        """
        FC parameters not present in the template are not added.

        GIVEN: A ParDict with only PARAM1
        WHEN: fc_parameters also contains EXTRA_PARAM not in the dict
        THEN: EXTRA_PARAM should not appear in the result
        """
        params = ParDict({"PARAM1": Par(1.0)})
        LocalFilesystem._transform_param_dict(
            params, blank_change_reason=False, use_fc_params=True, fc_parameters={"PARAM1": 5.0, "EXTRA_PARAM": 99.0}
        )
        assert "EXTRA_PARAM" not in params
        assert params["PARAM1"].value == 5.0

    def test_use_fc_params_true_with_none_fc_parameters_leaves_dict_unchanged(self) -> None:
        """
        use_fc_params=True with fc_parameters=None leaves the dict unchanged.

        GIVEN: use_fc_params is True but fc_parameters is None
        WHEN: _transform_param_dict is called
        THEN: No values or comments should be modified
        """
        params = ParDict({"PARAM1": Par(1.0, "comment")})
        LocalFilesystem._transform_param_dict(params, blank_change_reason=False, use_fc_params=True, fc_parameters=None)
        assert params["PARAM1"].value == 1.0
        assert params["PARAM1"].comment == "comment"

    def test_both_transformations_applied_together(self) -> None:
        """
        blank_change_reason and use_fc_params can be applied together in one call.

        GIVEN: A ParDict with PARAM1=1.0 and a comment
        WHEN: _transform_param_dict is called with both blank_change_reason=True and use_fc_params=True
        THEN: The value should be replaced by the FC value AND the comment should be stripped
        """
        params = ParDict({"PARAM1": Par(1.0, "drop this")})
        LocalFilesystem._transform_param_dict(
            params, blank_change_reason=True, use_fc_params=True, fc_parameters={"PARAM1": 7.0}
        )
        assert params["PARAM1"].value == 7.0
        assert params["PARAM1"].comment is None


class TestCopyTemplateFilesToNewVehicleDir(unittest.TestCase):
    """Copy Template Files To New Vehicle Directory testclass."""

    @patch("ardupilot_methodic_configurator.backend_filesystem.os_path.exists")
    @patch("ardupilot_methodic_configurator.backend_filesystem.os_listdir")
    @patch("ardupilot_methodic_configurator.backend_filesystem.os_path.join")
    @patch("ardupilot_methodic_configurator.backend_filesystem.shutil_copytree")
    @patch("ardupilot_methodic_configurator.backend_filesystem.shutil_copy2")
    @patch("ardupilot_methodic_configurator.backend_filesystem.os_path.isdir")
    def test_user_can_copy_mixed_files_and_dirs_without_transformation(  # pylint: disable=too-many-arguments, too-many-positional-arguments
        self, mock_isdir, mock_copy2, mock_copytree, mock_join, mock_listdir, mock_exists
    ) -> None:
        """
        Files, subdirectories and hidden files are all copied correctly when no transformation is requested.

        GIVEN: A template directory with a .param file, a text file, two subdirectories and a hidden file
        WHEN: copy_template_files_to_new_vehicle_dir is called with blank_change_reason=False and use_fc_params=False
        THEN: The .param and text files should be copied with shutil_copy2
         AND: The subdirectories should be copied with shutil_copytree
         AND: The hidden file should be copied
         AND: No error string should be returned
        """
        mock_exists.side_effect = lambda path: path in ["template_dir", "new_vehicle_dir"]
        mock_listdir.return_value = ["01_file1.param", "file2.txt", "dir1", ".hidden_file", "dir2"]
        mock_join.side_effect = lambda *args: "/".join(args)
        mock_isdir.side_effect = lambda path: path.endswith(("dir1", "dir2"))

        lfs = LocalFilesystem(
            "vehicle_dir", "vehicle_type", None, allow_editing_template_files=False, save_component_to_system_templates=False
        )
        result = lfs.copy_template_files_to_new_vehicle_dir(
            "template_dir", "new_vehicle_dir", blank_change_reason=False, copy_vehicle_image=False
        )

        assert result == ""

        # Verify directory copies
        mock_copytree.assert_any_call("template_dir/dir1", "new_vehicle_dir/dir1")
        mock_copytree.assert_any_call("template_dir/dir2", "new_vehicle_dir/dir2")

        # Verify file copies
        mock_copy2.assert_any_call("template_dir/01_file1.param", "new_vehicle_dir/01_file1.param")
        mock_copy2.assert_any_call("template_dir/file2.txt", "new_vehicle_dir/file2.txt")
        mock_copy2.assert_any_call("template_dir/.hidden_file", "new_vehicle_dir/.hidden_file")

    def test_user_sees_error_when_template_dir_does_not_exist(self) -> None:
        """
        An error string is returned when the template directory does not exist.

        GIVEN: A template directory path that does not exist on the filesystem
        WHEN: copy_template_files_to_new_vehicle_dir is called
        THEN: A non-empty error string should be returned describing the problem
        """
        lfs = LocalFilesystem(
            "vehicle_dir", "vehicle_type", None, allow_editing_template_files=False, save_component_to_system_templates=False
        )
        result = lfs.copy_template_files_to_new_vehicle_dir(
            "/nonexistent/template", "/some/dest", blank_change_reason=False, copy_vehicle_image=False
        )
        assert result != ""
        assert "nonexistent" in result or "exist" in result.lower()

    def test_user_sees_error_when_new_vehicle_dir_does_not_exist(self) -> None:
        """
        An error string is returned when the destination directory does not exist.

        GIVEN: A valid template directory but a destination path that does not exist
        WHEN: copy_template_files_to_new_vehicle_dir is called
        THEN: A non-empty error string should be returned describing the problem
        """
        with tempfile.TemporaryDirectory() as template_dir:
            lfs = LocalFilesystem(
                "vehicle_dir",
                "vehicle_type",
                None,
                allow_editing_template_files=False,
                save_component_to_system_templates=False,
            )
            result = lfs.copy_template_files_to_new_vehicle_dir(
                template_dir, "/nonexistent/dest", blank_change_reason=False, copy_vehicle_image=False
            )
        assert result != ""
        assert "nonexistent" in result or "exist" in result.lower()

    def test_skip_files_and_non_numbered_param_files_are_excluded(self) -> None:
        """
        Known skip-list files and non-numbered .param files are never copied.

        GIVEN: A template directory containing apm.pdef.xml, last_uploaded_filename.txt,
               tempcal_acc.png, tempcal_gyro.png and a non-numbered param file (foo.param)
        WHEN: copy_template_files_to_new_vehicle_dir is called
        THEN: None of those files should appear in the destination directory
        """
        with tempfile.TemporaryDirectory() as template_dir, tempfile.TemporaryDirectory() as new_vehicle_dir:
            skip_items = ["apm.pdef.xml", "last_uploaded_filename.txt", "tempcal_acc.png", "tempcal_gyro.png", "foo.param"]
            for name in skip_items:
                with open(os_path.join(template_dir, name), "w", encoding="utf-8") as f:
                    f.write("content")
            # Add one file that should be copied to verify the function ran
            with open(os_path.join(template_dir, "01_setup.param"), "w", encoding="utf-8") as f:
                f.write("PARAM1,1.0\n")

            lfs = LocalFilesystem(
                "vehicle_dir",
                "vehicle_type",
                None,
                allow_editing_template_files=False,
                save_component_to_system_templates=False,
            )
            result = lfs.copy_template_files_to_new_vehicle_dir(
                template_dir, new_vehicle_dir, blank_change_reason=False, copy_vehicle_image=False
            )

            assert result == ""
            for name in skip_items:
                assert not os_path.exists(os_path.join(new_vehicle_dir, name)), f"{name} should have been skipped"
            # The numbered param file must be present
            assert os_path.exists(os_path.join(new_vehicle_dir, "01_setup.param"))

    def test_copy_template_files_with_blank_change_reason(self) -> None:
        """
        Parameter file comments are stripped when blank_change_reason is True.

        GIVEN: A template .param file with comments on each line and a plain text file
        WHEN: copy_template_files_to_new_vehicle_dir is called with blank_change_reason=True
        THEN: The output .param file should contain parameters with correct values but no comments
         AND: The plain text file should be copied verbatim
        """
        with tempfile.TemporaryDirectory() as template_dir, tempfile.TemporaryDirectory() as new_vehicle_dir:
            # Create test param file with comments in the template
            param_file = os_path.join(template_dir, "01_file1.param")
            with open(param_file, "w", encoding="utf-8") as f:
                f.write("PARAM1,1.0 # test comment\nPARAM2,2.0 # another comment\n")

            # Create a non-param text file
            txt_file = os_path.join(template_dir, "file2.txt")
            with open(txt_file, "w", encoding="utf-8") as f:
                f.write("some content")

            lfs = LocalFilesystem(
                "vehicle_dir",
                "vehicle_type",
                "4.5.0",
                allow_editing_template_files=False,
                save_component_to_system_templates=False,
            )

            result = lfs.copy_template_files_to_new_vehicle_dir(
                template_dir, new_vehicle_dir, blank_change_reason=True, copy_vehicle_image=False
            )
            assert result == ""

            # Output param file must exist and contain correct values but no comments
            output_param = os_path.join(new_vehicle_dir, "01_file1.param")
            assert os_path.exists(output_param)
            with open(output_param, encoding="utf-8") as f:
                content = f.read()
            assert "# test comment" not in content, f"Comment should be stripped, got: {content!r}"
            assert "# another comment" not in content, f"Comment should be stripped, got: {content!r}"
            assert "PARAM1,1" in content, f"Expected PARAM1 value 1, got: {content!r}"
            assert "PARAM2,2" in content, f"Expected PARAM2 value 2, got: {content!r}"

            # Non-param file must be copied verbatim
            output_txt = os_path.join(new_vehicle_dir, "file2.txt")
            assert os_path.exists(output_txt)
            with open(output_txt, encoding="utf-8") as f:
                assert f.read() == "some content"

    def test_copy_template_files_with_use_fc_params(
        self,
    ) -> None:
        """
        FC parameter values replace differing template values; within-tolerance and absent params are unchanged.

        GIVEN: A template .param file with PARAM1=1.0 (comment) and PARAM2=2.0 (no comment)
        WHEN: copy_template_files_to_new_vehicle_dir is called with use_fc_params=True
          AND fc_parameters contains PARAM1=42.0 (different), PARAM2=2.000001 (within tolerance)
          AND fc_parameters also contains EXTRA_PARAM=99.0 (not in template)
        THEN: PARAM1 value should be 42 in output
         AND: PARAM1 comment should be preserved (blank_change_reason is False)
         AND: PARAM2 value should remain 2 (within tolerance)
         AND: EXTRA_PARAM should not appear in the output file
        """
        with tempfile.TemporaryDirectory() as template_dir, tempfile.TemporaryDirectory() as new_vehicle_dir:
            param_file = os_path.join(template_dir, "01_file1.param")
            with open(param_file, "w", encoding="utf-8") as f:
                f.write("PARAM1,1.0 # original comment\nPARAM2,2.0\n")

            lfs = LocalFilesystem(
                "vehicle_dir",
                "vehicle_type",
                "4.5.0",
                allow_editing_template_files=False,
                save_component_to_system_templates=False,
            )

            fc_parameters = {"PARAM1": 42.0, "PARAM2": 2.000001, "EXTRA_PARAM": 99.0}
            result = lfs.copy_template_files_to_new_vehicle_dir(
                template_dir,
                new_vehicle_dir,
                blank_change_reason=False,
                copy_vehicle_image=False,
                use_fc_params=True,
                fc_parameters=fc_parameters,
            )
            assert result == ""

            output_param = os_path.join(new_vehicle_dir, "01_file1.param")
            with open(output_param, encoding="utf-8") as f:
                content = f.read()

            assert "PARAM1,42" in content, f"Expected PARAM1 to be 42, got: {content!r}"
            assert "original comment" in content, f"Expected comment to be preserved, got: {content!r}"
            assert "PARAM2,2" in content, f"Expected PARAM2 to be present, got: {content!r}"
            # PARAM2 is within tolerance so it must not have jumped to 2.000001
            assert "PARAM2,2.000001" not in content, f"PARAM2 should stay at 2, got: {content!r}"
            assert "EXTRA_PARAM" not in content, f"EXTRA_PARAM should not be added, got: {content!r}"

    def test_copy_template_files_with_both_blank_reason_and_fc_params(self) -> None:
        """
        Both blank_change_reason and use_fc_params transformations are applied in a single pass.

        GIVEN: A template .param file with PARAM1=1.0 and a comment
        WHEN: copy_template_files_to_new_vehicle_dir is called with both blank_change_reason=True
          AND use_fc_params=True with fc_parameters containing PARAM1=7.0
        THEN: PARAM1 value should be 7 in output
         AND: The comment should be absent from the output
        """
        with tempfile.TemporaryDirectory() as template_dir, tempfile.TemporaryDirectory() as new_vehicle_dir:
            param_file = os_path.join(template_dir, "01_file1.param")
            with open(param_file, "w", encoding="utf-8") as f:
                f.write("PARAM1,1.0 # drop this comment\n")

            lfs = LocalFilesystem(
                "vehicle_dir",
                "vehicle_type",
                None,
                allow_editing_template_files=False,
                save_component_to_system_templates=False,
            )
            result = lfs.copy_template_files_to_new_vehicle_dir(
                template_dir,
                new_vehicle_dir,
                blank_change_reason=True,
                copy_vehicle_image=False,
                use_fc_params=True,
                fc_parameters={"PARAM1": 7.0},
            )
            assert result == ""

            with open(os_path.join(new_vehicle_dir, "01_file1.param"), encoding="utf-8") as f:
                content = f.read()
            assert "PARAM1,7" in content, f"Expected PARAM1=7, got: {content!r}"
            assert "drop this comment" not in content, f"Comment should be stripped, got: {content!r}"

    @patch("ardupilot_methodic_configurator.backend_filesystem.os_path.exists")
    @patch("ardupilot_methodic_configurator.backend_filesystem.os_listdir")
    @patch("ardupilot_methodic_configurator.backend_filesystem.os_path.join")
    @patch("ardupilot_methodic_configurator.backend_filesystem.shutil_copy2")
    @patch("ardupilot_methodic_configurator.backend_filesystem.os_path.isdir")
    def test_user_can_copy_vehicle_image_from_template(
        self, mock_isdir, mock_copy2, mock_join, mock_listdir, mock_exists
    ) -> None:
        """
        User can copy vehicle image file when creating a new vehicle from template.

        GIVEN: A template directory containing a vehicle.jpg file
        WHEN: The user creates a new vehicle with copy_vehicle_image=True
        THEN: The vehicle.jpg file should be copied to the new vehicle directory
        """
        # Arrange: Set up template directory with vehicle.jpg
        mock_exists.side_effect = lambda path: path in ["template_dir", "new_vehicle_dir"]
        mock_listdir.return_value = ["vehicle.jpg", "01_config.param"]
        mock_join.side_effect = lambda *args: "/".join(args)
        mock_isdir.return_value = False

        lfs = LocalFilesystem(
            "vehicle_dir", "vehicle_type", None, allow_editing_template_files=False, save_component_to_system_templates=False
        )

        # Act: Copy template files with copy_vehicle_image=True
        result = lfs.copy_template_files_to_new_vehicle_dir(
            "template_dir", "new_vehicle_dir", blank_change_reason=False, copy_vehicle_image=True
        )

        # Assert: Vehicle image should be copied
        assert result == ""  # No error
        mock_copy2.assert_any_call("template_dir/vehicle.jpg", "new_vehicle_dir/vehicle.jpg")
        mock_copy2.assert_any_call("template_dir/01_config.param", "new_vehicle_dir/01_config.param")

    @patch("ardupilot_methodic_configurator.backend_filesystem.os_path.exists")
    @patch("ardupilot_methodic_configurator.backend_filesystem.os_listdir")
    @patch("ardupilot_methodic_configurator.backend_filesystem.os_path.join")
    @patch("ardupilot_methodic_configurator.backend_filesystem.shutil_copy2")
    @patch("ardupilot_methodic_configurator.backend_filesystem.os_path.isdir")
    def test_user_can_skip_copying_vehicle_image_from_template(
        self, mock_isdir, mock_copy2, mock_join, mock_listdir, mock_exists
    ) -> None:
        """
        User can choose not to copy vehicle image file when creating a new vehicle from template.

        GIVEN: A template directory containing a vehicle.jpg file
        WHEN: The user creates a new vehicle with copy_vehicle_image=False
        THEN: The vehicle.jpg file should not be copied to the new vehicle directory
        AND: Other files should still be copied normally
        """
        # Arrange: Set up template directory with vehicle.jpg and other files
        mock_exists.side_effect = lambda path: path in ["template_dir", "new_vehicle_dir"]
        mock_listdir.return_value = ["vehicle.jpg", "01_config.param", "readme.txt"]
        mock_join.side_effect = lambda *args: "/".join(args)
        mock_isdir.return_value = False

        lfs = LocalFilesystem(
            "vehicle_dir", "vehicle_type", None, allow_editing_template_files=False, save_component_to_system_templates=False
        )

        # Act: Copy template files with copy_vehicle_image=False
        result = lfs.copy_template_files_to_new_vehicle_dir(
            "template_dir", "new_vehicle_dir", blank_change_reason=False, copy_vehicle_image=False
        )

        # Assert: Vehicle image should not be copied, but other files should be
        assert result == ""  # No error

        # Verify vehicle.jpg was NOT copied
        copy_calls = [call.args for call in mock_copy2.call_args_list]
        vehicle_jpg_calls = [call for call in copy_calls if "vehicle.jpg" in str(call)]
        assert len(vehicle_jpg_calls) == 0, "vehicle.jpg should not be copied when copy_vehicle_image=False"

        # Verify other files were copied
        mock_copy2.assert_any_call("template_dir/01_config.param", "new_vehicle_dir/01_config.param")
        mock_copy2.assert_any_call("template_dir/readme.txt", "new_vehicle_dir/readme.txt")

    @patch("ardupilot_methodic_configurator.backend_filesystem.os_path.exists")
    @patch("ardupilot_methodic_configurator.backend_filesystem.os_listdir")
    @patch("ardupilot_methodic_configurator.backend_filesystem.os_path.join")
    @patch("ardupilot_methodic_configurator.backend_filesystem.shutil_copy2")
    @patch("ardupilot_methodic_configurator.backend_filesystem.os_path.isdir")
    def test_copy_vehicle_image_defaults_to_false(self, mock_isdir, mock_copy2, mock_join, mock_listdir, mock_exists) -> None:
        """
        Vehicle image copying defaults to disabled.

        GIVEN: A template directory containing a vehicle.jpg file
        WHEN: The user creates a new vehicle with copy_vehicle_image=False
        THEN: The vehicle.jpg file should not be copied
        """
        # Arrange: Set up template directory with vehicle.jpg
        mock_exists.side_effect = lambda path: path in ["template_dir", "new_vehicle_dir"]
        mock_listdir.return_value = ["vehicle.jpg", "01_config.param"]
        mock_join.side_effect = lambda *args: "/".join(args)
        mock_isdir.return_value = False

        lfs = LocalFilesystem(
            "vehicle_dir", "vehicle_type", "", allow_editing_template_files=False, save_component_to_system_templates=False
        )

        # Act: Copy template files with copy_vehicle_image=False
        result = lfs.copy_template_files_to_new_vehicle_dir(
            "template_dir", "new_vehicle_dir", blank_change_reason=False, copy_vehicle_image=False
        )

        # Assert: No error and vehicle image should not be copied
        assert result == ""  # No error

        # Verify vehicle.jpg was NOT copied
        copy_calls = [call.args for call in mock_copy2.call_args_list]
        vehicle_jpg_calls = [call for call in copy_calls if "vehicle.jpg" in str(call)]
        assert len(vehicle_jpg_calls) == 0, "vehicle.jpg should not be copied when copy_vehicle_image=False"

        # Verify other files were copied
        mock_copy2.assert_any_call("template_dir/01_config.param", "new_vehicle_dir/01_config.param")

    @patch("ardupilot_methodic_configurator.backend_filesystem.os_path.exists")
    @patch("ardupilot_methodic_configurator.backend_filesystem.os_listdir")
    @patch("ardupilot_methodic_configurator.backend_filesystem.os_path.join")
    @patch("ardupilot_methodic_configurator.backend_filesystem.shutil_copy2")
    @patch("ardupilot_methodic_configurator.backend_filesystem.os_path.isdir")
    def test_copy_vehicle_image_with_no_image_file_present(
        self, mock_isdir, mock_copy2, mock_join, mock_listdir, mock_exists
    ) -> None:
        """
        Vehicle image copying gracefully handles missing vehicle.jpg file.

        GIVEN: A template directory without a vehicle.jpg file
        WHEN: The user creates a new vehicle with copy_vehicle_image=True
        THEN: No error should occur and other files should be copied normally
        """
        # Arrange: Set up template directory without vehicle.jpg
        mock_exists.side_effect = lambda path: path in ["template_dir", "new_vehicle_dir"]
        mock_listdir.return_value = ["01_config.param", "readme.txt"]  # No vehicle.jpg
        mock_join.side_effect = lambda *args: "/".join(args)
        mock_isdir.return_value = False

        lfs = LocalFilesystem(
            "vehicle_dir", "vehicle_type", "", allow_editing_template_files=False, save_component_to_system_templates=False
        )

        # Act: Copy template files with copy_vehicle_image=True (but no vehicle.jpg exists)
        result = lfs.copy_template_files_to_new_vehicle_dir(
            "template_dir", "new_vehicle_dir", blank_change_reason=False, copy_vehicle_image=True
        )

        # Assert: No error and other files copied normally
        assert result == ""  # No error
        mock_copy2.assert_any_call("template_dir/01_config.param", "new_vehicle_dir/01_config.param")
        mock_copy2.assert_any_call("template_dir/readme.txt", "new_vehicle_dir/readme.txt")


def test_merge_forced_or_derived_parameters_comprehensive() -> None:
    """Test merge_forced_or_derived_parameters with various scenarios."""
    lfs = LocalFilesystem(
        "vehicle_dir", "vehicle_type", "", allow_editing_template_files=False, save_component_to_system_templates=False
    )
    test_file = "test_file"

    # Test 1: Empty input parameters
    lfs.file_parameters = {test_file: {"PARAM1": Par(1.0, "original")}}
    assert lfs.merge_forced_or_derived_parameters(test_file, {}, []) is False
    assert len(lfs.file_parameters[test_file]) == 1

    # Test 2: Value change within tolerance
    lfs.file_parameters = {test_file: {"PARAM1": Par(1.0, "original")}}
    new_params = {test_file: {"PARAM1": Par(1.0001, "new")}}
    fc_parameters = ["PARAM1"]
    assert lfs.merge_forced_or_derived_parameters(test_file, new_params, fc_parameters) is False
    assert abs(lfs.file_parameters[test_file]["PARAM1"].value - 1.0) <= 1e-08 + (1e-03 * abs(1.0))

    # Test 3: Value change outside tolerance
    lfs.file_parameters = {test_file: {"PARAM1": Par(1.0, "original")}}
    new_params = {test_file: {"PARAM1": Par(1.5, "new")}}
    fc_parameters = ["PARAM1"]
    assert lfs.merge_forced_or_derived_parameters(test_file, new_params, fc_parameters) is True
    assert lfs.file_parameters[test_file]["PARAM1"].value == 1.5

    # Test 4: Multiple parameters
    lfs.file_parameters = {test_file: {"PARAM1": Par(1.0, "original1"), "PARAM2": Par(2.0, "original2")}}
    new_params = {test_file: {"PARAM1": Par(1.5, "new1"), "PARAM2": Par(2.0, "new2"), "PARAM3": Par(3.0, "new3")}}
    fc_parameters = ["PARAM1", "PARAM2", "PARAM3"]
    assert lfs.merge_forced_or_derived_parameters(test_file, new_params, fc_parameters) is True
    assert len(lfs.file_parameters[test_file]) == 3

    # Test 5: FC parameter filtering
    lfs.file_parameters = {test_file: {}}
    new_params = {test_file: {"PARAM1": Par(1.0, "new1"), "PARAM2": Par(2.0, "new2")}}
    fc_parameters = ["PARAM1"]  # Only PARAM1 exists in FC
    assert lfs.merge_forced_or_derived_parameters(test_file, new_params, fc_parameters) is True
    assert "PARAM1" in lfs.file_parameters[test_file]
    assert "PARAM2" not in lfs.file_parameters[test_file]

    # Test 6: Different file keys
    lfs.file_parameters = {"other_file": {}}
    new_params = {test_file: {"PARAM1": Par(1.0, "new")}}
    assert lfs.merge_forced_or_derived_parameters(test_file, new_params, []) is False
    assert len(lfs.file_parameters["other_file"]) == 0

    # Test 7: Empty FC parameters list (should add all params)
    lfs.file_parameters = {test_file: {}}
    new_params = {test_file: {"PARAM1": Par(1.0, "new")}}
    assert lfs.merge_forced_or_derived_parameters(test_file, new_params, []) is True
    assert "PARAM1" in lfs.file_parameters[test_file]

    # Test 8: None FC parameters list (should add all params)
    lfs.file_parameters = {test_file: {}}
    new_params = {test_file: {"PARAM1": Par(1.0, "new")}}
    assert lfs.merge_forced_or_derived_parameters(test_file, new_params, None) is True
    assert "PARAM1" in lfs.file_parameters[test_file]

    # Test 9: Comment overwrite
    original_param = Par(1.0, "original comment")
    lfs.file_parameters = {test_file: {"PARAM1": original_param}}
    new_params = {test_file: {"PARAM1": Par(1.5, "new comment")}}
    fc_parameters = ["PARAM1"]
    assert lfs.merge_forced_or_derived_parameters(test_file, new_params, fc_parameters) is True
    assert lfs.file_parameters[test_file]["PARAM1"].comment == "new comment"


def test_merge_forced_or_derived_parameters_none_parameters() -> None:
    """Test merge_forced_or_derived_parameters handles None parameters."""
    lfs = LocalFilesystem(
        "vehicle_dir", "vehicle_type", "", allow_editing_template_files=False, save_component_to_system_templates=False
    )
    test_file = "test.json"
    lfs.file_parameters = {test_file: {}}  # Test with empty dict instead of None (None is not valid type)
    lfs.merge_forced_or_derived_parameters(test_file, {}, [])
    assert lfs.file_parameters[test_file] == {}

    # Test with empty dict
    lfs.merge_forced_or_derived_parameters(test_file, {}, [])
    assert lfs.file_parameters[test_file] == {}


if __name__ == "__main__":
    unittest.main()
