#!/usr/bin/env python3

"""
Behavioral checks for official firmware selection by connected APJ board ID.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import base64
import gzip
import hashlib
import json
import zlib
from collections.abc import Iterator
from dataclasses import replace
from pathlib import Path
from threading import Event
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from urllib.parse import urlparse

import pytest
from requests import Response

from ardupilot_methodic_configurator.backend_firmware_upload import (
    FirmwareUploadCallbacks,
    FirmwareUploadService,
    download_firmware,
    fetch_firmware_manifest,
)
from ardupilot_methodic_configurator.data_model_firmware_catalog import (
    FirmwareRelease,
    find_firmware_release,
    firmware_targets,
    firmware_types,
    firmware_versions,
    preferred_board_target,
    preferred_catalog_choice,
    preferred_firmware_type,
    releases_for_board,
)
from ardupilot_methodic_configurator.data_model_firmware_upload import (
    BootloaderInfo,
    FirmwareCompatibilityError,
    FirmwareConnectionError,
    FirmwareFileError,
)


def _apj_contents(*, board_id: int = 9, git_identity: str = "abcdef12") -> bytes:
    """Encode a real APJ descriptor for the download and local-file workflows."""
    payload = b"firmware image"
    return json.dumps(
        {
            "board_id": board_id,
            "image_size": len(payload),
            "image": base64.b64encode(zlib.compress(payload)).decode("ascii"),
            "git_identity": git_identity,
            "version": "4.6.0",
        }
    ).encode("utf-8")


def _firmware_response(release: FirmwareRelease, contents: bytes) -> MagicMock:
    """Replace only HTTP transport while preserving streamed APJ bytes."""
    response = MagicMock(spec=Response)
    response.url = release.url
    response.__enter__.return_value = response
    response.iter_content.return_value = [contents[:10], contents[10:]]
    return response


@pytest.fixture(name="upload_controller")
def upload_controller_fixture() -> SimpleNamespace:
    """Provide concrete connection metadata with only the hardware upload replaced."""
    return SimpleNamespace(
        master=object(),
        comport=object(),
        comport_device="COM3",
        info=SimpleNamespace(apj_board_id=9, vehicle_type="ArduCopter", firmware_type="fmuv3"),
        upload_apj_firmware=MagicMock(return_value=BootloaderInfo(5, 9, 0, 2048)),
    )


@pytest.fixture(name="selectable_releases")
def selectable_releases_fixture() -> list[FirmwareRelease]:
    """Offer multiple board targets, versions, vehicle types, and Copter variants."""
    return [
        FirmwareRelease(
            "Copter",
            "4.5.0",
            "OFFICIAL",
            "fmuv3",
            "https://firmware.ardupilot.org/Copter/stable-4.5.0/fmuv3/arducopter.apj",
            9,
        ),
        FirmwareRelease(
            "Copter", "4.6.0", "OFFICIAL", "fmuv3", "https://firmware.ardupilot.org/Copter/stable/fmuv3/arducopter.apj", 9
        ),
        FirmwareRelease(
            "Copter",
            "4.6.0",
            "OFFICIAL",
            "CubeBlack",
            "https://firmware.ardupilot.org/Copter/stable/CubeBlack/arducopter.apj",
            9,
        ),
        FirmwareRelease(
            "Copter", "4.6.0", "OFFICIAL", "fmuv3", "https://firmware.ardupilot.org/Copter/stable/fmuv3/arducopter-heli.apj", 9
        ),
        FirmwareRelease(
            "Plane", "4.6.0", "OFFICIAL", "fmuv3", "https://firmware.ardupilot.org/Plane/stable/fmuv3/arduplane.apj", 9
        ),
    ]


def test_firmware_types_distinguish_copter_variants_without_duplicates(selectable_releases: list[FirmwareRelease]) -> None:
    """
    A catalog offers distinct vehicle and Copter variant choices.

    GIVEN: Multiple releases for the same vehicle types and different Copter variants.
    WHEN: Available firmware types are requested.
    THEN: Each type is listed once, in alphabetical order.
    """
    assert firmware_types(selectable_releases) == ["Copter - heli", "Copter - multicopter", "Plane"]


@pytest.mark.parametrize(
    ("firmware_type", "targets"),
    [
        ("Copter - multicopter", ["CubeBlack", "fmuv3"]),
        ("Copter - heli", ["fmuv3"]),
        ("Plane", ["fmuv3"]),
        ("Rover", []),
    ],
)
def test_selected_type_limits_targets(
    selectable_releases: list[FirmwareRelease], firmware_type: str, targets: list[str]
) -> None:
    """
    Target choices are specific to the chosen firmware type.

    GIVEN: Releases for multiple types with overlapping board targets.
    WHEN: Targets are requested for one type.
    THEN: Only that type's distinct targets are offered.
    """
    assert firmware_targets(selectable_releases, firmware_type) == targets


@pytest.mark.parametrize(
    ("firmware_type", "target", "indices"),
    [
        ("Copter - multicopter", "fmuv3", [0, 1]),
        ("Copter - multicopter", "CubeBlack", [2]),
        ("Copter - heli", "fmuv3", [3]),
        ("Plane", "fmuv3", [4]),
        ("Plane", "CubeBlack", []),
        ("Rover", "fmuv3", []),
    ],
)
def test_selected_type_and_target_limit_versions_in_catalog_order(
    selectable_releases: list[FirmwareRelease], firmware_type: str, target: str, indices: list[int]
) -> None:
    """
    A version belongs to both a firmware type and board target.

    GIVEN: A catalog containing several versions, targets, and vehicle types.
    WHEN: Versions are requested for the current type and target.
    THEN: Only matching release labels are returned, preserving catalog order.
    """
    assert firmware_versions(selectable_releases, firmware_type, target) == [
        selectable_releases[index].label for index in indices
    ]


@pytest.mark.parametrize(
    ("current", "preferred"),
    [("Copter", "Copter - multicopter"), ("Heli", "Copter - heli"), ("Plane", "Plane"), ("Rover", "Copter - heli")],
)
def test_installed_vehicle_type_selects_the_matching_firmware_variant(
    selectable_releases: list[FirmwareRelease], current: str, preferred: str
) -> None:
    """
    The installed firmware is preferred only when the catalog offers it.

    GIVEN: A catalog offering multicopter, helicopter, and Plane firmware.
    WHEN: A default firmware type is chosen for the installed vehicle.
    THEN: Its matching variant is preferred, otherwise the first catalog type is selected.
    """
    assert preferred_firmware_type(firmware_types(selectable_releases), current) == preferred


@pytest.mark.parametrize(
    ("targets", "board_name", "preferred"),
    [
        (["CubeBlack", "fmuv3"], "fmuv3", "fmuv3"),
        (["CubeBlack", "fmuv3"], "CubeBlack", "CubeBlack"),
        (["CubeBlack", "fmuv3"], "CubeBlack, CubePurple, fmuv3", ""),
        (["fmuv3"], "CubeBlack, fmuv3", "fmuv3"),
        ([], "fmuv3", ""),
    ],
)
def test_detected_board_target_is_selected_only_when_exact_or_unambiguous(
    targets: list[str], board_name: str, preferred: str
) -> None:
    """
    Ambiguous detected board aliases never choose a target implicitly.

    GIVEN: A detected board name and zero, one, or multiple catalog targets.
    WHEN: Its target default is determined.
    THEN: Only an exact match or a single available target is selected.
    """
    assert preferred_board_target(targets, board_name) == preferred


@pytest.mark.parametrize(
    ("firmware_type", "target", "version_index", "matches"),
    [
        ("Copter - multicopter", "fmuv3", 1, True),
        ("Copter - heli", "fmuv3", 3, True),
        ("Copter - heli", "fmuv3", 1, False),
        ("Copter - multicopter", "CubeBlack", 1, False),
        ("Plane", "fmuv3", 1, False),
    ],
)
def test_version_labels_cannot_select_a_release_from_another_type_or_target(
    selectable_releases: list[FirmwareRelease], firmware_type: str, target: str, version_index: int, matches: bool
) -> None:
    """
    Stale version labels never select another type's or target's release.

    GIVEN: A version label selected from a specific release.
    WHEN: It is resolved under the current firmware type and target.
    THEN: The original release is returned only when all selections still match.
    """
    selected = selectable_releases[version_index]
    assert find_firmware_release(selectable_releases, firmware_type, target, selected.label) is (selected if matches else None)


def test_empty_catalog_and_unselected_version_have_no_selection(selectable_releases: list[FirmwareRelease]) -> None:
    """
    No firmware is selected implicitly without an explicit version choice.

    GIVEN: An empty catalog or a catalog with no selected version.
    WHEN: Choices and the selected release are requested.
    THEN: Empty choices remain empty and no release is selected.
    """
    assert firmware_types([]) == []
    assert firmware_targets([], "Plane") == []
    assert firmware_versions([], "Plane", "fmuv3") == []
    assert preferred_firmware_type([], "Copter") == ""
    assert preferred_catalog_choice([], "fmuv3") == ""
    assert find_firmware_release([], "Plane", "fmuv3", "4.6.0") is None
    assert find_firmware_release(selectable_releases, "Plane", "fmuv3", "") is None


@pytest.mark.parametrize("port_present", [False, True])
def test_usb_port_presence_controls_whether_stale_connection_is_released(port_present: bool) -> None:
    """
    Only a missing USB serial port releases the retained connection.

    GIVEN: A controller with a retained MAVLink connection object.
    WHEN: Its USB serial port is checked.
    THEN: The connection is released only if its port disappeared.
    """
    controller = MagicMock()
    controller.master = object()
    controller.comport_device = "COM3"
    port = MagicMock()
    port.device = "COM3"
    controller.get_serial_ports.return_value = [port] if port_present else []

    removed = FirmwareUploadService.disconnect_if_serial_port_removed(controller)

    assert removed is not port_present
    if port_present:
        controller.disconnect.assert_not_called()
    else:
        controller.disconnect.assert_called_once_with()


@pytest.mark.parametrize("device", ["udp:127.0.0.1:14550", "tcp:localhost:5760", ""])
def test_serial_monitor_does_not_disconnect_network_connections(device: str) -> None:
    """
    USB monitoring ignores connections without a serial endpoint.

    GIVEN: A network connection or a controller without a serial device.
    WHEN: USB presence is checked.
    THEN: No serial scan or disconnect is performed.
    """
    controller = MagicMock()
    controller.comport_device = device

    assert not FirmwareUploadService.disconnect_if_serial_port_removed(controller)

    controller.get_serial_ports.assert_not_called()
    controller.disconnect.assert_not_called()


def test_serial_scan_error_does_not_discard_a_working_connection() -> None:
    """
    An operating-system discovery error preserves the connection.

    GIVEN: A connected controller.
    WHEN: Serial discovery raises an operating-system error.
    THEN: The monitor preserves the connection so a later check can retry.
    """
    controller = MagicMock()
    controller.comport_device = "COM3"
    controller.get_serial_ports.side_effect = OSError("discovery temporarily unavailable")

    assert not FirmwareUploadService.disconnect_if_serial_port_removed(controller)

    controller.disconnect.assert_not_called()


@pytest.mark.parametrize(("vehicle_type", "recommended_type"), [("ArduCopter", "Copter"), ("Heli", "Heli")])
def test_connected_board_preserves_the_installed_copter_variant(vehicle_type: str, recommended_type: str) -> None:
    """The selector can recommend helicopter firmware for a connected helicopter."""
    controller = MagicMock()
    controller.master = object()
    controller.info.apj_board_id = "9"
    controller.info.vehicle_type = vehicle_type

    board_info = FirmwareUploadService.connected_board_info(controller)

    assert board_info is not None
    assert board_info.recommended_vehicle_type == recommended_type


def test_user_sees_all_official_apj_versions_for_connected_board() -> None:
    """A connected board sees stable, beta and development images for its board ID."""
    manifest = {
        "firmware": [
            {
                "format": "apj",
                "board_id": 50,
                "vehicletype": "Copter",
                "platform": "ExampleBoard",
                "mav-firmware-version": "4.6.3",
                "mav-firmware-version-type": "OFFICIAL",
                "git-sha": "abcdef1234567890",
                "url": "https://firmware.ardupilot.org/Copter/stable/ExampleBoard/arducopter.apj",
            },
            {
                "format": "apj",
                "board_id": 50,
                "vehicletype": "Copter",
                "platform": "ExampleBoard",
                "mav-firmware-version": "4.7.0",
                "mav-firmware-version-type": "BETA",
                "url": "https://firmware.ardupilot.org/Copter/beta/ExampleBoard/arducopter.apj",
            },
            {
                "format": "apj",
                "board_id": 50,
                "vehicletype": "Plane",
                "platform": "ExampleBoard",
                "mav-firmware-version": "4.7.0",
                "mav-firmware-version-type": "DEV",
                "url": "https://firmware.ardupilot.org/Plane/latest/ExampleBoard/arduplane.apj",
            },
            {
                "format": "apj",
                "board_id": 51,
                "vehicletype": "Copter",
                "platform": "OtherBoard",
                "url": "https://firmware.ardupilot.org/Copter/stable/OtherBoard/arducopter.apj",
            },
            {
                "format": "apj",
                "board_id": 50,
                "vehicletype": "Copter",
                "platform": "ExampleBoard",
                "url": "https://other.example/Copter/stable/ExampleBoard/arducopter.apj",
            },
        ]
    }

    releases = releases_for_board(manifest, 50)

    assert {(release.vehicle_type, release.channel) for release in releases} == {
        ("Copter", "OFFICIAL"),
        ("Copter", "BETA"),
        ("Plane", "DEV"),
    }
    assert all(release.board_id == 50 for release in releases)
    assert all(urlparse(release.url).hostname == "firmware.ardupilot.org" for release in releases)
    assert next(release for release in releases if release.version == "4.6.3").git_sha == "abcdef1234567890"


def test_user_downloads_the_selected_official_file_with_a_bound_digest(
    tmp_path: Path, selectable_releases: list[FirmwareRelease]
) -> None:
    """The APJ passed to the flasher is exactly the file hashed from HTTPS."""
    release = selectable_releases[1]
    response = MagicMock()
    response.url = release.url
    response.iter_content.return_value = [b"first", b"second"]
    response.__enter__.return_value = response
    destination = tmp_path / "selected.apj"

    with (
        patch(
            "ardupilot_methodic_configurator.backend_firmware_upload._get_verify_param",
            return_value="test-ca.pem",
        ) as verify_param,
        patch("ardupilot_methodic_configurator.backend_firmware_upload.requests.get", return_value=response) as request,
    ):
        digest = download_firmware(release, destination, Event().is_set)

    assert destination.read_bytes() == b"firstsecond"
    assert digest == hashlib.sha256(b"firstsecond").hexdigest()
    request.assert_called_once_with(release.url, timeout=(10, 90), stream=True, verify="test-ca.pem")
    verify_param.assert_called_once_with()
    response.raise_for_status.assert_called_once_with()
    response.__exit__.assert_called_once_with(None, None, None)


def test_catalog_rejects_redirect_away_from_official_server() -> None:
    """A redirected manifest cannot be used to choose firmware for flashing."""
    response = MagicMock()
    response.url = "https://other.example/manifest.json.gz"
    response.iter_content.return_value = [gzip.compress(json.dumps({"firmware": []}).encode())]
    response.__enter__.return_value = response

    with (
        patch("ardupilot_methodic_configurator.backend_firmware_upload.requests.get", return_value=response),
        pytest.raises(ValueError, match="redirected away"),
    ):
        fetch_firmware_manifest()


def test_versions_are_sorted_numerically_for_one_vehicle() -> None:
    """Given 4.9 and 4.10 releases, the version selector lists 4.9 first."""
    entries = [
        {
            "format": "apj",
            "board_id": 50,
            "vehicletype": "Copter",
            "platform": "ExampleBoard",
            "mav-firmware-version": version,
            "url": f"https://firmware.ardupilot.org/Copter/{version}/ExampleBoard/arducopter.apj",
        }
        for version in ("4.10.0", "4.9.0")
    ]

    releases = releases_for_board({"firmware": entries}, 50)

    assert [release.version for release in releases] == ["4.9.0", "4.10.0"]


@pytest.mark.parametrize(
    ("vehicle_type", "old_version", "first_version"),
    [
        ("Copter", "3.6.5", "3.6.6"),
        ("Plane", "3.9.5", "3.9.6"),
        ("Rover", "3.4.2", "3.5.0"),
        ("Sub", "3.5.4", "4.0.0"),
    ],
)
def test_selector_omits_releases_without_git_identity(vehicle_type: str, old_version: str, first_version: str) -> None:
    """A version that cannot pass build verification is absent from the catalog."""
    entries = [
        {
            "format": "apj",
            "board_id": 9,
            "vehicletype": vehicle_type,
            "platform": "fmuv3",
            "mav-firmware-version": version,
            "git-sha": "abcdef1234567890",
            "url": f"https://firmware.ardupilot.org/{vehicle_type}/stable-{version}/fmuv3/firmware.apj",
        }
        for version in (old_version, first_version)
    ]

    releases = releases_for_board({"firmware": entries}, 9)

    assert [release.version for release in releases] == [first_version]


@pytest.mark.parametrize("collection", [{}, None, "firmware", 9])
def test_manifest_rejects_invalid_firmware_collection(collection: object) -> None:
    """
    Invalid catalog structure is rejected.

    GIVEN: A manifest whose firmware collection is not a list.
    WHEN: Releases are selected for a board.
    THEN: Invalid collection shape raises ValueError.
    """
    with pytest.raises(ValueError, match="Invalid ArduPilot firmware manifest"):
        releases_for_board({"firmware": collection}, 9)


@pytest.mark.parametrize(
    ("field", "invalid_value"),
    [
        ("format", "px4"),
        ("board_id", "not a number"),
        ("board_id", None),
        ("board_id", 50),
        ("url", 123),
        ("url", "http://firmware.ardupilot.org/Copter/stable/fmuv3/arducopter.apj"),
        ("url", "https://other.example/Copter/stable/fmuv3/arducopter.apj"),
        ("url", "https://firmware.ardupilot.org/Copter/stable/fmuv3/arducopter.bin"),
        ("vehicletype", 3),
        ("platform", None),
    ],
)
def test_manifest_skips_an_entry_with_one_invalid_field(field: str, invalid_value: object) -> None:
    """
    Malformed entries cannot hide valid releases or bypass individual validation rules.

    GIVEN: A valid release and another entry with exactly one invalid field.
    WHEN: Releases are selected for its board.
    THEN: Only the valid release remains, regardless of entry order.
    """
    valid = {
        "format": "apj",
        "board_id": 9,
        "vehicletype": "Copter",
        "platform": "fmuv3",
        "mav-firmware-version": "4.6.0",
        "url": "https://firmware.ardupilot.org/Copter/stable/fmuv3/arducopter.apj",
    }
    expected = releases_for_board({"firmware": [valid]}, 9)
    assert len(expected) == 1
    invalid = {**valid, field: invalid_value}
    assert releases_for_board({"firmware": [invalid]}, 9) == []
    assert releases_for_board({"firmware": [invalid, valid]}, 9) == expected
    assert releases_for_board({"firmware": [valid, invalid]}, 9) == expected


@pytest.mark.parametrize("entry", [None, [], "firmware"])
def test_manifest_skips_entries_that_are_not_objects(entry: object) -> None:
    """Given a non-object entry, selecting board releases ignores it safely."""
    assert releases_for_board({"firmware": [entry]}, 9) == []


def test_manifest_uses_defaults_for_missing_version_channel_and_git_identity() -> None:
    """
    An identifiable APJ without optional manifest fields still gets a usable descriptor.

    GIVEN: A valid APJ manifest entry without optional version, channel, or SHA fields.
    WHEN: The catalog creates the release descriptor.
    THEN: Stable fallback values are supplied for each missing field.
    """
    (release,) = releases_for_board(
        {
            "firmware": [
                {
                    "format": "apj",
                    "board_id": 9,
                    "vehicletype": "Experimental",
                    "platform": "fmuv3",
                    "url": "https://firmware.ardupilot.org/Experimental/latest/fmuv3/image.apj",
                }
            ]
        },
        9,
    )
    assert release.version == "Unknown"
    assert release.channel == "unknown"
    assert release.git_sha == ""


def test_failed_download_preserves_existing_apj_and_removes_temporary_file(
    tmp_path: Path, selectable_releases: list[FirmwareRelease]
) -> None:
    """Given an interrupted APJ download, the previous destination remains intact."""
    release = selectable_releases[1]
    destination = tmp_path / "selected.apj"
    destination.write_bytes(b"previous APJ")
    response = MagicMock()
    response.url = release.url
    response.__enter__.return_value = response

    def interrupted_content(_size: int) -> Iterator[bytes]:
        yield b"partial"
        msg = "connection interrupted"
        raise OSError(msg)

    response.iter_content.side_effect = interrupted_content
    with (
        patch("ardupilot_methodic_configurator.backend_firmware_upload.requests.get", return_value=response),
        pytest.raises(OSError, match="connection interrupted"),
    ):
        download_firmware(release, destination)

    assert destination.read_bytes() == b"previous APJ"
    assert list(tmp_path.iterdir()) == [destination]


@pytest.mark.parametrize("actual_identity", ["12345678", "", "a"])
def test_upload_rejects_apj_from_a_different_manifest_build(
    actual_identity: str, selectable_releases: list[FirmwareRelease], upload_controller: SimpleNamespace
) -> None:
    """Given a mutable stable URL, the downloaded APJ must match the manifest's git SHA."""
    release = replace(selectable_releases[1], git_sha="abcdef1234567890")
    response = _firmware_response(release, _apj_contents(git_identity=actual_identity))
    with (
        patch("ardupilot_methodic_configurator.backend_firmware_upload.requests.get", return_value=response),
        pytest.raises(FirmwareCompatibilityError, match="build"),
    ):
        FirmwareUploadService.upload_release(
            upload_controller,
            release,
            callbacks=FirmwareUploadCallbacks(confirmation_requested=lambda *_args: True),
        )
    response.raise_for_status.assert_called_once_with()
    response.iter_content.assert_called_once_with(65536)
    upload_controller.upload_apj_firmware.assert_not_called()


@pytest.mark.parametrize("git_identity", ["abcdef12", "ABCDEF12", "abcdef1234567890"])
def test_matching_manifest_git_sha_allows_the_downloaded_apj(
    selectable_releases: list[FirmwareRelease], upload_controller: SimpleNamespace, git_identity: str
) -> None:
    """Given a matching APJ git identity, the selected release reaches the upload facade."""
    release = replace(selectable_releases[1], git_sha="abcdef1234567890")
    contents = _apj_contents(git_identity=git_identity)
    response = _firmware_response(release, contents)
    uploaded_paths: list[Path] = []
    bootloader = BootloaderInfo(5, 9, 0, 2048)

    def upload(path: Path, **_kwargs: object) -> BootloaderInfo:
        assert path.read_bytes() == contents
        assert list(path.parent.iterdir()) == [path]
        uploaded_paths.append(path)
        return bootloader

    upload_controller.upload_apj_firmware.side_effect = upload
    callbacks = FirmwareUploadCallbacks(confirmation_requested=lambda *_args: True)
    with patch("ardupilot_methodic_configurator.backend_firmware_upload.requests.get", return_value=response) as request:
        result = FirmwareUploadService.upload_release(
            upload_controller,
            release,
            callbacks=callbacks,
        )

    assert result is bootloader
    request.assert_called_once()
    assert request.call_args.args == (release.url,)
    response.raise_for_status.assert_called_once_with()
    response.iter_content.assert_called_once_with(65536)
    response.__exit__.assert_called_once_with(None, None, None)
    assert len(uploaded_paths) == 1
    apj_path = uploaded_paths[0]
    assert apj_path.name == "firmware.apj"
    assert not apj_path.parent.exists()
    upload_controller.upload_apj_firmware.assert_called_once_with(
        apj_path,
        expected_firmware_sha256=hashlib.sha256(contents).hexdigest(),
        cancellation_requested=None,
        confirmation_requested=callbacks.confirmation_requested,
        progress_callback=None,
    )


def test_upload_rejects_connection_change_during_firmware_download(selectable_releases: list[FirmwareRelease]) -> None:
    """Given a changed serial device during download, the APJ is not sent to the new device."""
    release = replace(selectable_releases[1], git_sha="abcdef1234567890")
    controller = MagicMock()
    controller.master = object()
    controller.comport = object()
    controller.comport_device = "/dev/ttyACM0"
    controller.info.apj_board_id = 9

    def change_connection(*_args: object) -> str:
        controller.comport_device = "/dev/ttyACM1"
        return "digest"

    with (
        patch(
            "ardupilot_methodic_configurator.backend_firmware_upload.download_firmware",
            side_effect=change_connection,
        ),
        patch("ardupilot_methodic_configurator.backend_firmware_upload.load_apj") as load_apj,
        pytest.raises(FirmwareConnectionError, match="connection changed"),
    ):
        FirmwareUploadService.upload_release(
            controller,
            release,
            callbacks=FirmwareUploadCallbacks(confirmation_requested=lambda *_args: True),
        )

    load_apj.assert_not_called()
    controller.upload_apj_firmware.assert_not_called()


def test_custom_apj_uses_its_checked_digest_for_upload(tmp_path: Path, upload_controller: SimpleNamespace) -> None:
    """A selected local image reaches the upload facade with its exact APJ digest."""
    path = tmp_path / "custom.apj"
    contents = _apj_contents()
    path.write_bytes(contents)
    callbacks = FirmwareUploadCallbacks(confirmation_requested=lambda *_args: True)

    result = FirmwareUploadService.upload_custom_file(upload_controller, path, callbacks=callbacks)

    assert result is upload_controller.upload_apj_firmware.return_value
    assert path.read_bytes() == contents
    assert list(tmp_path.iterdir()) == [path]
    upload_controller.upload_apj_firmware.assert_called_once_with(
        path,
        expected_firmware_sha256=hashlib.sha256(contents).hexdigest(),
        cancellation_requested=None,
        confirmation_requested=callbacks.confirmation_requested,
        progress_callback=None,
    )


def test_custom_apj_for_another_board_is_rejected_before_upload(tmp_path: Path, upload_controller: SimpleNamespace) -> None:
    """A local APJ for a different board cannot reach bootloader entry."""
    path = tmp_path / "other-board.apj"
    contents = _apj_contents(board_id=51)
    path.write_bytes(contents)

    with pytest.raises(FirmwareCompatibilityError, match="board ID"):
        FirmwareUploadService.upload_custom_file(
            upload_controller,
            path,
            callbacks=FirmwareUploadCallbacks(confirmation_requested=lambda *_args: True),
        )

    assert path.read_bytes() == contents
    upload_controller.upload_apj_firmware.assert_not_called()


def test_custom_upload_rejects_a_non_apj_file_before_flash(tmp_path: Path) -> None:
    """A user-selected file with the wrong format cannot reach bootloader entry."""
    controller = MagicMock()
    controller.master = object()
    controller.comport = object()
    controller.comport_device = "/dev/ttyACM0"
    controller.info.apj_board_id = 50
    path = tmp_path / "firmware.bin"
    path.write_bytes(b"not an APJ")

    with pytest.raises(FirmwareFileError, match=r"only \.apj is supported"):
        FirmwareUploadService.upload_custom_file(
            controller,
            path,
            callbacks=FirmwareUploadCallbacks(confirmation_requested=lambda *_args: True),
        )

    controller.upload_apj_firmware.assert_not_called()
