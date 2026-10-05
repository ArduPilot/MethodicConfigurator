#!/usr/bin/env python3

"""
Behavioral tests for downloading and validating official firmware.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2026 Amilcar Lucas

SPDX-License-Identifier: GPL-3.0-or-later
"""

import base64
import gzip
import hashlib
import json
import zlib
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from ardupilot_methodic_configurator import backend_firmware_upload as firmware_upload
from ardupilot_methodic_configurator.backend_firmware_upload import (
    FirmwareUploadCallbacks,
    FirmwareUploadService,
    download_firmware,
    fetch_firmware_manifest,
)
from ardupilot_methodic_configurator.data_model_firmware_catalog import FirmwareRelease
from ardupilot_methodic_configurator.data_model_firmware_upload import (
    FirmwareCompatibilityError,
    FirmwareConfirmationError,
    FirmwareConnectionError,
    FirmwareUploadCancelledError,
)


def _release(*, board_id: int = 50, git_sha: str = "") -> FirmwareRelease:
    return FirmwareRelease(
        "Copter",
        "4.6.3",
        "OFFICIAL",
        "ExampleBoard",
        "https://firmware.ardupilot.org/Copter/stable/ExampleBoard/arducopter.apj",
        board_id,
        git_sha,
    )


def _controller(*, board_id: object = 50, device: str = "/dev/ttyACM0") -> SimpleNamespace:
    return SimpleNamespace(
        master=object(),
        comport=object(),
        comport_device=device,
        info=SimpleNamespace(apj_board_id=board_id, vehicle_type="ArduCopter", firmware_type="ExampleBoard"),
        upload_apj_firmware=MagicMock(),
    )


def _apj_contents(*, board_id: int = 50) -> bytes:
    """Encode a real firmware image for service download and inspection tests."""
    image = b"firmware image"
    return json.dumps(
        {
            "board_id": board_id,
            "image_size": len(image),
            "image": base64.b64encode(zlib.compress(image)).decode("ascii"),
            "version": "4.6.3",
        }
    ).encode("utf-8")


def _response(contents: bytes) -> MagicMock:
    """Supply streamed HTTP content without replacing download or APJ parsing."""
    response = MagicMock(spec=firmware_upload.requests.Response)
    response.url = _release().url
    response.__enter__.return_value = response
    response.iter_content.return_value = [contents[:10], contents[10:]]
    return response


def test_manifest_download_returns_decoded_json() -> None:
    """
    A valid official manifest is decompressed and decoded as JSON.

    GIVEN: A compressed response containing a JSON object.
    WHEN: The firmware manifest is fetched.
    THEN: The decoded catalog data is returned.
    """
    response = MagicMock()
    response.url = firmware_upload.MANIFEST_URL
    response.__enter__.return_value = response
    response.iter_content.return_value = [gzip.compress(b'{"firmware": []}')]
    with (
        patch.object(firmware_upload, "_get_verify_param", return_value="test-ca.pem") as verify_param,
        patch.object(firmware_upload.requests, "get", return_value=response) as request,
    ):
        assert fetch_firmware_manifest() == {"firmware": []}

    request.assert_called_once_with(
        firmware_upload.MANIFEST_URL,
        timeout=(10, 90),
        stream=True,
        verify="test-ca.pem",
    )
    verify_param.assert_called_once_with()
    response.__exit__.assert_called_once_with(None, None, None)


def test_manifest_download_propagates_http_status_errors() -> None:
    """An unsuccessful HTTP response is rejected before its body is consumed."""
    response = MagicMock()
    response.url = firmware_upload.MANIFEST_URL
    response.__enter__.return_value = response
    response.raise_for_status.side_effect = firmware_upload.requests.HTTPError("manifest unavailable")

    with (
        patch.object(firmware_upload.requests, "get", return_value=response),
        pytest.raises(firmware_upload.requests.HTTPError, match="manifest unavailable"),
    ):
        fetch_firmware_manifest()

    response.raise_for_status.assert_called_once_with()
    response.iter_content.assert_not_called()


def test_manifest_download_rejects_non_mapping_json() -> None:
    """
    A JSON list cannot serve as the firmware manifest object.

    GIVEN: A compressed response containing a JSON list.
    WHEN: The firmware manifest is fetched.
    THEN: The invalid top-level shape is rejected.
    """
    response = MagicMock()
    response.url = firmware_upload.MANIFEST_URL
    response.__enter__.return_value = response
    response.iter_content.return_value = [gzip.compress(b"[]")]
    with patch.object(firmware_upload.requests, "get", return_value=response), pytest.raises(ValueError, match="invalid"):
        fetch_firmware_manifest()


def test_manifest_download_rejects_oversized_payload() -> None:
    """
    A catalog larger than the configured cap is rejected before decompression.

    GIVEN: A streamed manifest that exceeds the download limit.
    WHEN: The manifest is fetched.
    THEN: The service raises a clear size error.
    """
    response = MagicMock()
    response.url = firmware_upload.MANIFEST_URL
    response.__enter__.return_value = response
    response.iter_content.return_value = [b"x" * (firmware_upload.MAX_MANIFEST_DOWNLOAD + 1)]
    with patch.object(firmware_upload.requests, "get", return_value=response), pytest.raises(ValueError, match="too large"):
        fetch_firmware_manifest()


@pytest.mark.parametrize("url", ["http://firmware.ardupilot.org/file", "https://evil.example/file"])
def test_manifest_download_rejects_non_official_redirect(url: str) -> None:
    """
    Manifest redirects must remain on the official HTTPS host.

    GIVEN: An HTTP or non-ArduPilot redirect destination.
    WHEN: The manifest fetch validates the response URL.
    THEN: The response is rejected before its content is used.
    """
    response = MagicMock()
    response.url = url
    response.__enter__.return_value = response
    with patch.object(firmware_upload.requests, "get", return_value=response), pytest.raises(ValueError, match="redirected"):
        fetch_firmware_manifest()


def test_apj_download_stops_when_cancelled_before_request(tmp_path: Path) -> None:
    """
    A download is not started after the user cancels.

    GIVEN: A cancellation callback that is already set.
    WHEN: The selected APJ is downloaded.
    THEN: Cancellation is reported and no destination file is created.
    """
    release = _release()
    destination = tmp_path / "image.apj"
    with patch.object(firmware_upload.requests, "get") as request, pytest.raises(FirmwareUploadCancelledError):
        download_firmware(release, destination, lambda: True)
    request.assert_not_called()
    assert not destination.exists()


def test_apj_download_rejects_untrusted_redirect(tmp_path: Path) -> None:
    """
    An APJ response redirected off the official host is rejected.

    GIVEN: A firmware response whose final URL is outside the official host.
    WHEN: The selected APJ is downloaded.
    THEN: The response is rejected and no destination file is created.
    """
    release = _release()
    destination = tmp_path / "image.apj"
    response = MagicMock()
    response.__enter__.return_value = response
    response.url = "https://evil.example/image.apj"
    with patch.object(firmware_upload.requests, "get", return_value=response), pytest.raises(ValueError, match="redirected"):
        download_firmware(release, destination)
    assert not destination.exists()


def test_apj_download_rejects_oversized_response(tmp_path: Path) -> None:
    """
    An APJ body exceeding the configured cap is rejected.

    GIVEN: A streamed response larger than the maximum APJ download size.
    WHEN: The selected APJ is downloaded.
    THEN: A size error is raised and no destination file is created.
    """
    release = _release()
    destination = tmp_path / "image.apj"
    response = MagicMock()
    response.url = release.url
    response.__enter__.return_value = response
    response.iter_content.return_value = [b"x" * (firmware_upload.MAX_APJ_DOWNLOAD + 1)]
    with patch.object(firmware_upload.requests, "get", return_value=response), pytest.raises(ValueError, match="too large"):
        download_firmware(release, destination)
    assert not destination.exists()


def test_apj_download_rejects_empty_response(tmp_path: Path) -> None:
    """
    An empty APJ response is rejected.

    GIVEN: A successful response with no content chunks.
    WHEN: The selected APJ is downloaded.
    THEN: An empty-download error is raised and no file is created.
    """
    release = _release()
    destination = tmp_path / "image.apj"
    response = MagicMock()
    response.url = release.url
    response.__enter__.return_value = response
    response.iter_content.return_value = []
    with patch.object(firmware_upload.requests, "get", return_value=response), pytest.raises(ValueError, match="empty"):
        download_firmware(release, destination)
    assert not destination.exists()


def test_apj_download_cancellation_during_transfer_removes_temporary_file(tmp_path: Path) -> None:
    """
    Cancellation between chunks preserves the destination and removes the partial file.

    GIVEN: An existing APJ and a cancellation request after the first chunk.
    WHEN: The download continues to the next chunk.
    THEN: The old destination remains and the temporary partial file is removed.
    """
    release = _release()
    destination = tmp_path / "image.apj"
    destination.write_bytes(b"old image")
    response = MagicMock()
    response.url = release.url
    response.__enter__.return_value = response
    response.iter_content.return_value = [b"partial", b"next chunk"]
    # The service checks once before the request, then before writing each chunk.
    # Let the first chunk reach the temporary file and cancel before the second.
    cancel = iter((False, False, True))
    with (
        patch.object(firmware_upload.requests, "get", return_value=response),
        pytest.raises(FirmwareUploadCancelledError),
    ):
        download_firmware(release, destination, lambda: next(cancel))
    assert destination.read_bytes() == b"old image"
    assert list(tmp_path.iterdir()) == [destination]


def test_serial_monitor_ignores_disconnected_controller() -> None:
    """
    A disconnected controller is left alone by stale-port monitoring.

    GIVEN: A controller whose MAVLink master is already absent.
    WHEN: The stale-port monitor checks the controller.
    THEN: No disconnect is requested.
    """
    controller = MagicMock()
    controller.master = None
    assert not FirmwareUploadService.disconnect_if_serial_port_removed(controller)
    controller.disconnect.assert_not_called()


def test_serial_monitor_ignores_unavailable_port_inventory() -> None:
    """
    An OS error while listing serial ports does not cause a false disconnect.

    GIVEN: A connected controller and a serial-port scan that raises OSError.
    WHEN: The stale-port monitor checks the controller.
    THEN: It leaves the controller connected.
    """
    controller = MagicMock()
    controller.master = object()
    controller.get_serial_ports.side_effect = OSError("scan failed")
    assert not FirmwareUploadService.disconnect_if_serial_port_removed(controller)
    controller.disconnect.assert_not_called()


@pytest.mark.parametrize("board_id", ["unknown", -1])
def test_board_identity_is_unavailable_for_invalid_id(board_id: object) -> None:
    """
    A missing or negative APJ ID is not treated as a flashable board.

    GIVEN: A connected controller with an invalid APJ board ID.
    WHEN: Board information is requested.
    THEN: The service reports that no valid board identity is available.
    """
    controller = _controller(board_id=board_id)
    assert FirmwareUploadService.connected_board_info(controller) is None


@pytest.mark.parametrize(
    "device",
    [
        "",
        "udp:127.0.0.1:14550",
        "udpin:127.0.0.1:14550",
        "udpout:127.0.0.1:14550",
        "tcp:127.0.0.1:5760",
        "tcpin:127.0.0.1:5760",
        "tcpout:127.0.0.1:5760",
        "ws://127.0.0.1:5760",
        "wss://127.0.0.1:5760",
        "UDP:127.0.0.1:14550",
    ],
)
def test_upload_requires_a_direct_usb_connection(device: str) -> None:
    """
    Firmware writes require a direct serial connection and never use network MAVLink.

    GIVEN: A missing or network-based connection string.
    WHEN: A custom firmware upload is requested.
    THEN: The service rejects the request before inspecting the file.
    """
    controller = _controller(device=device)
    with (
        patch.object(firmware_upload, "load_apj") as inspect_apj,
        pytest.raises(FirmwareConnectionError),
    ):
        FirmwareUploadService.upload_custom_file(controller, Path("firmware.apj"))
    inspect_apj.assert_not_called()
    controller.upload_apj_firmware.assert_not_called()


def test_upload_requires_explicit_confirmation_and_a_valid_board_id() -> None:
    """
    The backend refuses writes without confirmation or a readable connected board ID.

    GIVEN: An upload request without confirmation or with an unreadable board ID.
    WHEN: The custom upload path validates the request.
    THEN: The service raises a typed confirmation or connection error.
    """
    controller = _controller()
    with pytest.raises(FirmwareConfirmationError):
        FirmwareUploadService.upload_custom_file(controller, Path("firmware.apj"))
    controller.upload_apj_firmware.assert_not_called()
    with pytest.raises(FirmwareConnectionError, match="board ID"):
        FirmwareUploadService.upload_custom_file(
            _controller(board_id="unknown"),
            Path("firmware.apj"),
            callbacks=FirmwareUploadCallbacks(confirmation_requested=lambda *_: True),
        )


def test_official_release_rejects_wrong_board_before_download() -> None:
    """
    A release for another board is rejected before touching the network.

    GIVEN: An official release with a different board ID than the connected controller.
    WHEN: The upload service validates the release.
    THEN: It raises a compatibility error without downloading firmware.
    """
    with patch.object(firmware_upload, "download_firmware") as download, pytest.raises(FirmwareCompatibilityError):
        FirmwareUploadService.upload_release(
            _controller(),
            _release(board_id=51),
            callbacks=FirmwareUploadCallbacks(confirmation_requested=lambda *_: True),
        )
    download.assert_not_called()


def test_official_release_rejects_downloaded_image_for_different_board() -> None:
    """A downloaded APJ must match both the selected release and connected board."""
    controller = _controller()
    release = _release()
    response = _response(_apj_contents(board_id=51))
    callbacks = FirmwareUploadCallbacks(confirmation_requested=lambda *_args: True)

    with (
        patch.object(firmware_upload.requests, "get", return_value=response),
        pytest.raises(FirmwareCompatibilityError, match="detected board ID"),
    ):
        FirmwareUploadService.upload_release(controller, release, callbacks=callbacks)

    response.iter_content.assert_called_once_with(65536)
    controller.upload_apj_firmware.assert_not_called()


def test_official_release_reports_download_and_upload_status_callbacks() -> None:
    """
    The UI receives download status and the verified bytes are passed to the facade.

    GIVEN: A matching official release with status and confirmation callbacks.
    WHEN: The service validates the downloaded APJ and uploads it.
    THEN: It reports progress status and forwards the trusted digest.
    """
    controller = _controller()
    contents = _apj_contents()
    statuses: list[str] = []

    def cancellation_requested() -> bool:
        return False

    def confirmation_requested(*_args: object) -> bool:
        return True

    def progress_callback(*_args: object) -> None:
        return None

    callbacks = FirmwareUploadCallbacks(
        confirmation_requested=confirmation_requested,
        cancellation_requested=cancellation_requested,
        progress_callback=progress_callback,
        status_callback=statuses.append,
    )
    with patch.object(firmware_upload.requests, "get", return_value=_response(contents)):
        FirmwareUploadService.upload_release(controller, _release(), callbacks=callbacks)
    assert statuses == [firmware_upload._("Downloading firmware…")]
    uploaded_path = controller.upload_apj_firmware.call_args.args[0]
    controller.upload_apj_firmware.assert_called_once_with(
        uploaded_path,
        expected_firmware_sha256=hashlib.sha256(contents).hexdigest(),
        cancellation_requested=cancellation_requested,
        confirmation_requested=confirmation_requested,
        progress_callback=progress_callback,
    )
    assert uploaded_path.name == "firmware.apj"
    assert not uploaded_path.parent.exists()


def test_official_release_parses_downloaded_apj_before_upload() -> None:
    """A downloaded APJ is parsed and checked before its digest reaches the facade."""
    controller = _controller()
    apj_contents = _apj_contents()
    expected_digest = hashlib.sha256(apj_contents).hexdigest()

    def confirmation_requested(*_args: object) -> bool:
        return True

    uploaded_paths: list[Path] = []
    bootloader = firmware_upload.BootloaderInfo(5, 50, 0, 2048)

    def upload(path: Path, **_kwargs: object) -> firmware_upload.BootloaderInfo:
        assert path.read_bytes() == apj_contents
        uploaded_paths.append(path)
        return bootloader

    controller.upload_apj_firmware.side_effect = upload
    response = _response(apj_contents)
    with patch.object(firmware_upload.requests, "get", return_value=response):
        result = FirmwareUploadService.upload_release(
            controller,
            _release(),
            callbacks=FirmwareUploadCallbacks(confirmation_requested=confirmation_requested),
        )

    assert result is bootloader
    assert len(uploaded_paths) == 1
    uploaded_path = uploaded_paths[0]
    controller.upload_apj_firmware.assert_called_once_with(
        uploaded_path,
        expected_firmware_sha256=expected_digest,
        cancellation_requested=None,
        confirmation_requested=confirmation_requested,
        progress_callback=None,
    )
    assert uploaded_path.name == "firmware.apj"
    assert not uploaded_path.exists()  # TemporaryDirectory is cleaned when upload_release returns.


def test_custom_file_reports_status_before_inspection_and_passes_callbacks(tmp_path: Path) -> None:
    """
    Local APJ inspection reports progress and forwards trusted digest and callbacks.

    GIVEN: A local APJ that matches the connected board and callbacks for the upload.
    WHEN: The custom upload service inspects and forwards the file.
    THEN: It reports inspection status and passes the digest and callbacks to the facade.
    """
    controller = _controller()
    contents = _apj_contents()
    statuses: list[str] = []

    def cancellation_requested() -> bool:
        return False

    def confirmation_requested(*_args: object) -> bool:
        return True

    def progress_callback(*_args: object) -> None:
        return None

    path = tmp_path / "custom.apj"
    path.write_bytes(contents)

    def record_inspection(status: str) -> None:
        assert path.exists()
        assert not controller.upload_apj_firmware.called
        statuses.append(status)

    callbacks = FirmwareUploadCallbacks(
        confirmation_requested=confirmation_requested,
        cancellation_requested=cancellation_requested,
        progress_callback=progress_callback,
        status_callback=record_inspection,
    )
    FirmwareUploadService.upload_custom_file(controller, path, callbacks=callbacks)
    assert statuses == [firmware_upload._("Inspecting selected firmware…")]
    controller.upload_apj_firmware.assert_called_once_with(
        path,
        expected_firmware_sha256=hashlib.sha256(contents).hexdigest(),
        cancellation_requested=cancellation_requested,
        confirmation_requested=confirmation_requested,
        progress_callback=progress_callback,
    )
    assert path.read_bytes() == contents
