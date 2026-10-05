"""
Firmware catalog and upload workflow, independent of the Tk frontend.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import gzip
import hashlib
import json
import re
import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from logging import debug as logging_debug
from os.path import normcase, realpath
from pathlib import Path
from urllib.parse import urlparse

import requests

from ardupilot_methodic_configurator import _
from ardupilot_methodic_configurator.backend_flightcontroller import FlightController
from ardupilot_methodic_configurator.backend_flightcontroller_bootloader import (
    CancellationRequested,
    ConfirmationRequested,
    ProgressCallback,
    load_apj,
)
from ardupilot_methodic_configurator.backend_internet import _get_verify_param
from ardupilot_methodic_configurator.data_model_firmware_catalog import FirmwareRelease, releases_for_board
from ardupilot_methodic_configurator.data_model_firmware_upload import (
    BootloaderInfo,
    FirmwareCompatibilityError,
    FirmwareConfirmationError,
    FirmwareConnectionError,
    FirmwareUploadCancelledError,
)

MANIFEST_URL = "https://firmware.ardupilot.org/manifest.json.gz"
MAX_MANIFEST_DOWNLOAD = 32 * 1024 * 1024
MAX_APJ_DOWNLOAD = 100 * 1024 * 1024


@dataclass(frozen=True)
class FirmwareBoardInfo:
    """Board identity and recommended firmware type for display and selection."""

    board_id: int
    board_name: str
    device: str
    recommended_vehicle_type: str


@dataclass(frozen=True)
class FirmwareUploadCallbacks:
    """Optional callbacks used to report and confirm an upload."""

    cancellation_requested: CancellationRequested | None = None
    confirmation_requested: ConfirmationRequested | None = None
    progress_callback: ProgressCallback | None = None
    status_callback: Callable[[str], None] | None = None


def _ensure_official_https_url(url: str, description: str) -> None:
    """Reject redirects away from the official HTTPS firmware server."""
    parsed = urlparse(url)
    if parsed.hostname != "firmware.ardupilot.org" or parsed.scheme != "https":
        msg = _("The {description} redirected away from the official ArduPilot server").format(description=description)
        raise ValueError(msg)


def fetch_firmware_manifest() -> dict:
    """Download and decode the official firmware manifest."""
    with requests.get(MANIFEST_URL, timeout=(10, 90), stream=True, verify=_get_verify_param()) as response:
        response.raise_for_status()
        _ensure_official_https_url(response.url, _("firmware catalog"))
        chunks: list[bytes] = []
        size = 0
        for chunk in response.iter_content(65536):
            size += len(chunk)
            if size > MAX_MANIFEST_DOWNLOAD:
                msg = _("The ArduPilot firmware catalog is too large")
                raise ValueError(msg)
            chunks.append(chunk)
    manifest = json.loads(gzip.decompress(b"".join(chunks)))
    if not isinstance(manifest, dict):
        msg = _("The ArduPilot firmware catalog is invalid")
        raise ValueError(msg)
    return manifest


def download_firmware(
    release: FirmwareRelease, destination: Path, cancellation_requested: CancellationRequested | None = None
) -> str:
    """Download one APJ to a temporary file and return its exact SHA-256."""
    digest = hashlib.sha256()
    size = 0
    if cancellation_requested is not None and cancellation_requested():
        msg = _("Firmware download cancelled")
        raise FirmwareUploadCancelledError(msg)
    with requests.get(release.url, timeout=(10, 90), stream=True, verify=_get_verify_param()) as response:
        response.raise_for_status()
        _ensure_official_https_url(response.url, _("firmware download"))
        temporary_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                dir=destination.parent, prefix=f".{destination.name}.", suffix=".tmp", delete=False
            ) as output:
                temporary_path = Path(output.name)
                for chunk in response.iter_content(65536):
                    if cancellation_requested is not None and cancellation_requested():
                        msg = _("Firmware download cancelled")
                        raise FirmwareUploadCancelledError(msg)
                    size += len(chunk)
                    if size > MAX_APJ_DOWNLOAD:
                        msg = _("The firmware image is too large")
                        raise ValueError(msg)
                    output.write(chunk)
                    digest.update(chunk)
            if not size:
                msg = _("The firmware download is empty")
                raise ValueError(msg)
            temporary_path.replace(destination)
        finally:
            if temporary_path is not None:
                temporary_path.unlink(missing_ok=True)
    return digest.hexdigest()


class FirmwareUploadService:
    """Run catalog and flash operations without any GUI dependencies."""

    @staticmethod
    def disconnect_if_serial_port_removed(flight_controller: FlightController) -> bool:
        """Release a stale serial connection without consuming MAVLink messages."""
        device = flight_controller.comport_device
        if flight_controller.master is None or not device or ":" in device:
            return False
        try:
            connected_device = normcase(realpath(device))
            available_devices = {normcase(realpath(port.device)) for port in flight_controller.get_serial_ports()}
        except OSError as exc:
            logging_debug("Could not check firmware upload connection: %s", exc)
            return False
        if connected_device in available_devices:
            return False
        flight_controller.disconnect()
        return True

    @staticmethod
    def connected_board_info(flight_controller: FlightController) -> FirmwareBoardInfo | None:
        """Return the connected board identity, or None when it is unavailable."""
        if flight_controller.master is None:
            return None
        try:
            board_id = int(flight_controller.info.apj_board_id)
        except (TypeError, ValueError):
            return None
        if board_id < 0:
            return None
        recommended_type = {
            "ArduCopter": "Copter",
            "ArduPlane": "Plane",
            "ArduSub": "Sub",
            "ArduBlimp": "Blimp",
        }.get(flight_controller.info.vehicle_type, flight_controller.info.vehicle_type)
        return FirmwareBoardInfo(
            board_id=board_id,
            board_name=flight_controller.info.firmware_type,
            device=flight_controller.comport_device,
            recommended_vehicle_type=recommended_type,
        )

    @staticmethod
    def releases_for_connected_board(board_id: int) -> list[FirmwareRelease]:
        """Return official APJ releases for a board from the current manifest."""
        return releases_for_board(fetch_firmware_manifest(), board_id)

    @staticmethod
    def _board_ready_for_upload(flight_controller: FlightController, callbacks: FirmwareUploadCallbacks) -> FirmwareBoardInfo:
        """Require a directly connected board and an explicit flash confirmation callback."""
        device = flight_controller.comport_device
        network_prefixes = ("udp:", "udpin:", "udpout:", "tcp:", "tcpin:", "tcpout:", "ws:", "wss:")
        if (
            flight_controller.master is None
            or flight_controller.comport is None
            or not device
            or device.lower().startswith(network_prefixes)
        ):
            msg = _("Firmware upload requires a direct USB serial connection to the flight controller")
            raise FirmwareConnectionError(msg)
        if callbacks.confirmation_requested is None:
            msg = _("Firmware upload requires explicit confirmation")
            raise FirmwareConfirmationError(msg)
        board_info = FirmwareUploadService.connected_board_info(flight_controller)
        if board_info is None:
            msg = _("Firmware upload requires the connected flight-controller board ID")
            raise FirmwareConnectionError(msg)
        return board_info

    @staticmethod
    def upload_release(
        flight_controller: FlightController,
        release: FirmwareRelease,
        *,
        callbacks: FirmwareUploadCallbacks | None = None,
    ) -> BootloaderInfo:
        """Download, validate, flash, verify and reconnect the selected release."""
        callbacks = callbacks or FirmwareUploadCallbacks()
        board_info = FirmwareUploadService._board_ready_for_upload(flight_controller, callbacks)
        if board_info.board_id != release.board_id:
            msg = _("The selected release does not match the connected flight-controller board")
            raise FirmwareCompatibilityError(msg)

        with tempfile.TemporaryDirectory(prefix="ardupilot_firmware_") as directory:
            apj_path = Path(directory) / "firmware.apj"
            if callbacks.status_callback is not None:
                callbacks.status_callback(_("Downloading firmware…"))
            digest = download_firmware(release, apj_path, callbacks.cancellation_requested)
            current_board_info = FirmwareUploadService._board_ready_for_upload(flight_controller, callbacks)
            if current_board_info.device != board_info.device or current_board_info.board_id != board_info.board_id:
                msg = _("The flight-controller connection changed while downloading firmware")
                raise FirmwareConnectionError(msg)
            image = load_apj(apj_path)
            if image.metadata.board_id != release.board_id:
                msg = _("The downloaded firmware does not match the detected board ID")
                raise FirmwareCompatibilityError(msg)
            if release.git_sha:
                expected = release.git_sha.casefold()
                actual = image.metadata.git_identity.casefold()
                if re.fullmatch(r"[0-9a-f]{7,40}", actual) is None or not expected.startswith(actual):
                    msg = _("The downloaded firmware build does not match the selected release")
                    raise FirmwareCompatibilityError(msg)
            return flight_controller.upload_apj_firmware(
                apj_path,
                expected_firmware_sha256=digest,
                cancellation_requested=callbacks.cancellation_requested,
                confirmation_requested=callbacks.confirmation_requested,
                progress_callback=callbacks.progress_callback,
            )

    @staticmethod
    def upload_custom_file(
        flight_controller: FlightController,
        path: Path,
        *,
        callbacks: FirmwareUploadCallbacks | None = None,
    ) -> BootloaderInfo:
        """Validate and flash a user-selected APJ through the existing upload facade."""
        callbacks = callbacks or FirmwareUploadCallbacks()
        board_info = FirmwareUploadService._board_ready_for_upload(flight_controller, callbacks)
        if callbacks.status_callback is not None:
            callbacks.status_callback(_("Inspecting selected firmware…"))
        image = load_apj(path)
        if image.metadata.board_id != board_info.board_id:
            msg = _("The selected APJ does not match the connected flight-controller board ID")
            raise FirmwareCompatibilityError(msg)
        return flight_controller.upload_apj_firmware(
            path,
            expected_firmware_sha256=image.metadata.apj_sha256,
            cancellation_requested=callbacks.cancellation_requested,
            confirmation_requested=callbacks.confirmation_requested,
            progress_callback=callbacks.progress_callback,
        )
