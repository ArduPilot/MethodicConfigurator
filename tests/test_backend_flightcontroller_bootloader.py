#!/usr/bin/env python3

"""Tests for the injected bootloader transport adapter."""

import base64
import json
import struct
import zlib
from binascii import crc32
from pathlib import Path

import pytest

from ardupilot_methodic_configurator import backend_flightcontroller_bootloader as bl
from ardupilot_methodic_configurator import data_model_firmware_upload as fw
from ardupilot_methodic_configurator.backend_flightcontroller import FlightController
from ardupilot_methodic_configurator.data_model_flightcontroller_info import FlightControllerInfo


def apj(image: bytes, *, extf_image: bytes = b"", **overrides: object) -> bytes:
    desc: dict[str, object] = {
        "board_id": 9,
        "image_size": len(image),
        "image": base64.b64encode(zlib.compress(image)).decode(),
    }
    if extf_image:
        desc.update(
            extf_image_size=len(extf_image),
            extf_image=base64.b64encode(zlib.compress(extf_image)).decode(),
        )
    desc.update(overrides)
    return json.dumps(desc).encode()


class FakeBootloaderTransport:
    """Byte-oriented fake with short reads, rev-2 support, and external flash."""

    def __init__(self, *, revision: int = 5, flash_size: int = 2048, extf_size: int = 1024) -> None:
        self.revision = revision
        self.flash_size = flash_size
        self.extf_size = extf_size
        self.flash = b""
        self.extf = b""
        self.closed = False
        self._reply = bytearray()
        self._read_offset = 0

    def write(self, request: bytes) -> int:
        assert request.endswith(bl.EOC)
        command, body = request[:1], request[1:-1]
        sync = bl.INSYNC + bl.OK
        if command == bl.GET_SYNC:
            self._reply.extend(sync)
        elif command == bl.GET_DEVICE:
            values = {
                bl.INFO_BL_REV: self.revision,
                bl.INFO_BOARD_ID: 9,
                bl.INFO_BOARD_REV: 0,
                bl.INFO_FLASH_SIZE: self.flash_size,
                bl.INFO_EXTF_SIZE: self.extf_size,
            }
            self._reply.extend(struct.pack("<I", values[body]) + sync)
        elif command == bl.EXTF_ERASE:
            self.extf = b""
            self._reply.extend(sync + b"\x64" + sync)
        elif command == bl.EXTF_PROG_MULTI:
            self.extf += body[1:]
            self._reply.extend(sync)
        elif command == bl.EXTF_GET_CRC:
            size = struct.unpack("<I", body)[0]
            self._reply.extend(struct.pack("<I", crc32(self.extf[:size], 0)) + sync)
        elif command in (bl.CHIP_ERASE, bl.CHIP_FULL_ERASE):
            self.flash = b""
            self._reply.extend(sync)
        elif command == bl.PROG_MULTI:
            self.flash += body[1:]
            self._reply.extend(sync)
        elif command == bl.CHIP_VERIFY:
            self._read_offset = 0
            self._reply.extend(sync)
        elif command == bl.READ_MULTI:
            length = body[0]
            self._reply.extend(self.flash[self._read_offset : self._read_offset + length] + sync)
            self._read_offset += length
        elif command == bl.GET_CRC:
            padded = self.flash + b"\xff" * (self.flash_size - len(self.flash))
            self._reply.extend(struct.pack("<I", crc32(padded, 0)) + sync)
        elif command == bl.REBOOT and self.revision >= 3:
            self._reply.extend(sync)
        return len(request)

    def read(self, size: int = 1) -> bytes:
        # Deliberately emulate short serial reads.
        count = min(size, 2, len(self._reply))
        data = bytes(self._reply[:count])
        del self._reply[:count]
        return data

    def flush(self) -> None:
        pass

    def close(self) -> None:
        self.closed = True


@pytest.mark.parametrize("revision", [2, 5])
def test_upload_verifies_revision_specific_protocol_and_closes(revision: int) -> None:
    image = fw.parse_apj(apj(b"abc"))
    transport = FakeBootloaderTransport(revision=revision)

    info = bl.BootloaderClient(transport).upload(image)

    assert info.protocol_revision == revision
    assert transport.flash == b"abc\xff"
    assert transport.closed


def test_uploads_and_verifies_external_flash() -> None:
    image = fw.parse_apj(apj(b"abcd", extf_image=b"external"))
    transport = FakeBootloaderTransport()

    bl.BootloaderClient(transport).upload(image)

    assert transport.extf == b"external"
    assert transport.closed


def test_failed_upload_still_closes_transport() -> None:
    image = fw.parse_apj(apj(b"abcd"))
    transport = FakeBootloaderTransport(flash_size=3)

    with pytest.raises(fw.FirmwareCompatibilityError, match="exceeds flash"):
        bl.BootloaderClient(transport).upload(image)
    assert transport.closed


def test_parse_apj_is_pure_and_requires_declared_size_to_match() -> None:
    contents = apj(b"four", image_size=1)

    with pytest.raises(fw.FirmwareFileError, match="image_size"):
        fw.parse_apj(contents, path=Path("firmware.apj"))


def test_invalid_board_revision_is_a_typed_file_error() -> None:
    with pytest.raises(fw.FirmwareFileError, match="metadata"):
        fw.parse_apj(apj(b"four", board_revision="not-a-number"))


def test_padded_payload_capacity_and_compatible_board_mapping_are_checked() -> None:
    image = fw.parse_apj(apj(b"abc"))
    with pytest.raises(fw.FirmwareCompatibilityError, match="exceeds flash"):
        fw.check_compatibility(image, fw.BootloaderInfo(5, 9, 0, 3))

    fw.check_compatibility(image, fw.BootloaderInfo(5, 33, 0, 4))


def test_bounded_decompression_rejects_before_full_output_is_allocated(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(fw, "MAX_IMAGE_SIZE", 32)

    with pytest.raises(fw.FirmwareFileError, match="exceeds"):
        fw.parse_apj(apj(b"x" * 64))


class _Master:
    def __init__(self) -> None:
        self.held_in_bootloader = False

    def reboot_autopilot(self, *, hold_in_bootloader: bool) -> None:
        self.held_in_bootloader = hold_in_bootloader


class _Connection:
    def __init__(self, device: str = "COM7") -> None:
        self.master = _Master()
        self.comport = object()
        self.comport_device = device
        self.baudrate = 115200
        self.info = FlightControllerInfo()
        self.disconnected = False
        self.reconnected = False

    def discover_connections(self, **_kwargs: object) -> None:
        pass

    def disconnect(self) -> None:
        self.disconnected = True
        self.master = None  # type: ignore[assignment]

    def create_connection_with_retry(self, *_args: object, **_kwargs: object) -> str:
        self.reconnected = True
        return ""


class _Params:
    def __init__(self) -> None:
        self.cleared = 0

    def clear_parameters(self) -> None:
        self.cleared += 1


def test_facade_enters_bootloader_releases_serial_and_reconnects(tmp_path: Path) -> None:
    connection = _Connection()
    params = _Params()
    transport = FakeBootloaderTransport()
    controller = FlightController(
        connection_manager=connection,  # type: ignore[arg-type]
        params_manager=params,  # type: ignore[arg-type]
        commands_manager=object(),  # type: ignore[arg-type]
        files_manager=object(),  # type: ignore[arg-type]
    )
    path = tmp_path / "firmware.apj"
    path.write_bytes(apj(b"abcd"))
    master = connection.master

    controller.upload_apj_firmware(path, serial_factory=lambda *_args: transport)

    assert master.held_in_bootloader
    assert connection.disconnected
    assert connection.reconnected
    assert transport.closed
    assert params.cleared == 2


def test_facade_refuses_network_mavlink_connection() -> None:
    connection = _Connection("udp:127.0.0.1:14550")
    controller = FlightController(
        connection_manager=connection,  # type: ignore[arg-type]
        params_manager=_Params(),  # type: ignore[arg-type]
        commands_manager=object(),  # type: ignore[arg-type]
        files_manager=object(),  # type: ignore[arg-type]
    )

    with pytest.raises(fw.FirmwareFileError, match="direct serial"):
        controller.upload_apj_firmware(Path("ignored.apj"))


def test_backend_retries_serial_open_after_bootloader_entry() -> None:
    image = fw.parse_apj(apj(b"abcd"))
    attempts = 0
    delays: list[float] = []
    entered = False
    transport = FakeBootloaderTransport()

    def enter() -> None:
        nonlocal entered
        entered = True

    def open_transport(*_args: object) -> bl.BootloaderTransport:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            msg = "bootloader port has not appeared yet"
            raise OSError(msg)
        return transport

    backend = bl.FlightControllerBootloaderBackend(
        "COM7",
        115200,
        enter_bootloader=enter,
        serial_factory=open_transport,
        open_retries=2,
        retry_delay=0.25,
        sleep=delays.append,
    )

    backend.upload(image)

    assert entered
    assert attempts == 2
    assert delays == [0.25]


def test_cancellation_is_honoured_before_flash_is_erased() -> None:
    transport = FakeBootloaderTransport()

    with pytest.raises(fw.FirmwareUploadCancelledError, match="before erase"):
        bl.BootloaderClient(transport).upload(fw.parse_apj(apj(b"abcd")), cancellation_requested=lambda: True)

    assert transport.flash == b""
    assert transport.extf == b""
    assert transport.closed
