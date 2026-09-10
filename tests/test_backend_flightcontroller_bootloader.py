#!/usr/bin/env python3

"""
Tests for the injected bootloader transport adapter.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import base64
import hashlib
import json
import struct
import sys
import zlib
from collections.abc import Callable
from pathlib import Path

import pytest
import serial
from serial.tools.list_ports_common import ListPortInfo

from ardupilot_methodic_configurator import backend_flightcontroller_bootloader as bl
from ardupilot_methodic_configurator import data_model_firmware_upload as fw
from ardupilot_methodic_configurator.backend_flightcontroller import FlightController
from ardupilot_methodic_configurator.data_model_flightcontroller_info import FlightControllerInfo

# pylint: disable=too-many-instance-attributes,too-few-public-methods,protected-access,too-many-lines


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


def trusted_digest(image: bytes, extf_image: bytes = b"") -> str:
    """Return the independently supplied release digest expected by the facade."""
    return hashlib.sha256(apj(image, extf_image=extf_image)).hexdigest()


@pytest.fixture(autouse=True)
def stable_test_device_identity(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep facade tests independent of the host's actual USB inventory."""
    monkeypatch.setattr(
        "ardupilot_methodic_configurator.backend_flightcontroller.capture_serial_device_identity",
        lambda _device: None,
    )
    monkeypatch.setattr(
        "ardupilot_methodic_configurator.backend_flightcontroller.has_stable_bootloader_device_identity",
        lambda *_args: True,
    )


class FakeBootloaderTransport:
    """Byte-oriented fake with short reads, rev-2 support, and external flash."""

    def __init__(self, *, revision: int = 5, board_id: int = 9, flash_size: int = 2048, extf_size: int = 1024) -> None:
        self.revision = revision
        self.board_id = board_id
        self.flash_size = flash_size
        self.extf_size = extf_size
        self.flash = b""
        self.extf = b""
        self.extf_erase_size: int | None = None
        self.closed = False
        self.rebooted = False
        self.commands: list[bytes] = []
        self.requests: list[bytes] = []
        self._reply = bytearray()
        self._read_offset = 0

    def write(self, data: bytes) -> int:
        assert data.endswith(bl.EOC)
        command, body = data[:1], data[1:-1]
        self.commands.append(command)
        self.requests.append(data)
        sync = bl.INSYNC + bl.OK
        if command == bl.GET_SYNC:
            self._reply.extend(sync)
        elif command == bl.GET_DEVICE:
            values = {
                bl.INFO_BL_REV: self.revision,
                bl.INFO_BOARD_ID: self.board_id,
                bl.INFO_BOARD_REV: 0,
                bl.INFO_FLASH_SIZE: self.flash_size,
                bl.INFO_EXTF_SIZE: self.extf_size,
            }
            self._reply.extend(struct.pack("<I", values[body]) + sync)
        elif command == bl.EXTF_ERASE:
            self.extf_erase_size = struct.unpack("<I", body)[0]
            self.extf = b""
            self._reply.extend(sync + bytes((0, 6, 12, 18, 25, 31, 37, 43, 50, 56, 62, 68, 75, 81, 87, 93, 100)) + sync)
        elif command == bl.EXTF_PROG_MULTI:
            assert body, "external PROG_MULTI request has no length byte"
            assert body[0] == len(body[1:]), "external PROG_MULTI length byte is incorrect"
            self.extf += body[1:]
            self._reply.extend(sync)
        elif command == bl.EXTF_GET_CRC:
            size = struct.unpack("<I", body)[0]
            self._reply.extend(struct.pack("<I", fw.bootloader_crc32(self.extf[:size])) + sync)
        elif command in (bl.CHIP_ERASE, bl.CHIP_FULL_ERASE):
            self.flash = b""
            self._reply.extend(sync)
        elif command == bl.PROG_MULTI:
            assert body, "PROG_MULTI request has no length byte"
            assert body[0] == len(body[1:]), "PROG_MULTI length byte is incorrect"
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
            self._reply.extend(struct.pack("<I", fw.bootloader_crc32(padded)) + sync)
        elif command == bl.REBOOT:
            self.rebooted = True
            if self.revision >= 3:
                self._reply.extend(sync)
        return len(data)

    def read(self, size: int = 1) -> bytes:
        # Deliberately emulate short serial reads.
        count = min(size, 2, len(self._reply))
        data = bytes(self._reply[:count])
        del self._reply[:count]
        return data

    def flush(self) -> None:
        pass

    def reset_input_buffer(self) -> None:
        self._reply.clear()

    def close(self) -> None:
        self.closed = True


@pytest.mark.parametrize("revision", [2, 5])
def test_upload_verifies_revision_specific_protocol_and_closes(revision: int) -> None:
    image = fw.parse_apj(apj(b"abc"))
    transport = FakeBootloaderTransport(revision=revision)

    info = bl.BootloaderClient(transport).upload(image, confirmation_requested=lambda *_args: True)

    assert info.protocol_revision == revision
    assert transport.flash == b"abc\xff"
    assert transport.closed
    if revision == 2:
        assert bl.CHIP_VERIFY in transport.commands
        assert bl.GET_CRC not in transport.commands
    else:
        assert bl.GET_CRC in transport.commands
        assert bl.CHIP_VERIFY not in transport.commands


def test_protocol_byte_constants_match_the_bootloader_wire_specification() -> None:
    """Keep the fake transport from masking a protocol-byte renumbering."""
    assert {
        "INSYNC": bl.INSYNC,
        "EOC": bl.EOC,
        "OK": bl.OK,
        "FAILED": bl.FAILED,
        "INVALID": bl.INVALID,
        "BAD_SILICON_REV": bl.BAD_SILICON_REV,
        "GET_SYNC": bl.GET_SYNC,
        "GET_DEVICE": bl.GET_DEVICE,
        "CHIP_ERASE": bl.CHIP_ERASE,
        "CHIP_VERIFY": bl.CHIP_VERIFY,
        "PROG_MULTI": bl.PROG_MULTI,
        "READ_MULTI": bl.READ_MULTI,
        "GET_CRC": bl.GET_CRC,
        "REBOOT": bl.REBOOT,
        "EXTF_ERASE": bl.EXTF_ERASE,
        "EXTF_PROG_MULTI": bl.EXTF_PROG_MULTI,
        "EXTF_GET_CRC": bl.EXTF_GET_CRC,
        "CHIP_FULL_ERASE": bl.CHIP_FULL_ERASE,
        "INFO_BL_REV": bl.INFO_BL_REV,
        "INFO_BOARD_ID": bl.INFO_BOARD_ID,
        "INFO_BOARD_REV": bl.INFO_BOARD_REV,
        "INFO_FLASH_SIZE": bl.INFO_FLASH_SIZE,
        "INFO_EXTF_SIZE": bl.INFO_EXTF_SIZE,
    } == {
        "INSYNC": b"\x12",
        "EOC": b"\x20",
        "OK": b"\x10",
        "FAILED": b"\x11",
        "INVALID": b"\x13",
        "BAD_SILICON_REV": b"\x14",
        "GET_SYNC": b"\x21",
        "GET_DEVICE": b"\x22",
        "CHIP_ERASE": b"\x23",
        "CHIP_VERIFY": b"\x24",
        "PROG_MULTI": b"\x27",
        "READ_MULTI": b"\x28",
        "GET_CRC": b"\x29",
        "REBOOT": b"\x30",
        "EXTF_ERASE": b"\x34",
        "EXTF_PROG_MULTI": b"\x35",
        "EXTF_GET_CRC": b"\x37",
        "CHIP_FULL_ERASE": b"\x40",
        "INFO_BL_REV": b"\x01",
        "INFO_BOARD_ID": b"\x02",
        "INFO_BOARD_REV": b"\x03",
        "INFO_FLASH_SIZE": b"\x04",
        "INFO_EXTF_SIZE": b"\x06",
    }


def test_encode_chip_erase_preserves_the_requested_erase_mode() -> None:
    assert bl.encode_chip_erase() == b"\x23\x20"
    assert bl.encode_chip_erase(full=True) == b"\x40\x20"


@pytest.mark.parametrize(
    ("encode", "expected"),
    [
        (bl.encode_get_sync, b"\x21\x20"),
        (lambda: bl.encode_get_device(bl.INFO_BL_REV), b"\x22\x01\x20"),
        (bl.encode_chip_verify, b"\x24\x20"),
        (lambda: bl.encode_prog_multi(b"\x01\x02\x03\x04"), b"\x27\x04\x01\x02\x03\x04\x20"),
        (lambda: bl.encode_extf_prog_multi(b"\x01\x02\x03\x04"), b"\x35\x04\x01\x02\x03\x04\x20"),
        (lambda: bl.encode_read_multi(4), b"\x28\x04\x20"),
        (lambda: bl.encode_extf_erase(0x01020304), b"\x34\x04\x03\x02\x01\x20"),
        (lambda: bl.encode_extf_get_crc(0x01020304), b"\x37\x04\x03\x02\x01\x20"),
        (bl.encode_get_crc, b"\x29\x20"),
        (bl.encode_reboot, b"\x30\x20"),
    ],
)
def test_encoder_emits_the_bootloader_wire_format(encode: Callable[[], bytes], expected: bytes) -> None:
    """
    Each command uses the byte layout expected by AP_Bootloader.

    GIVEN: A command encoder and a representative request
    WHEN: The request is encoded
    THEN: Its bytes match the independent bootloader wire specification
    """
    assert encode() == expected


def test_v2_verification_uses_the_read_chunk_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Legacy read-back verification uses the bootloader's read limit independently.

    GIVEN: Program and read commands have different protocol chunk limits
    WHEN: A revision-two image is verified after programming
    THEN: Read-back requests stay within the read-command limit
    """
    monkeypatch.setattr(bl, "PROG_MULTI_MAX", 252)
    monkeypatch.setattr(bl, "READ_MULTI_MAX", 64)
    image = fw.parse_apj(apj(bytes(range(100)), board_id=9))

    transport = FakeBootloaderTransport(revision=2)
    info = bl.BootloaderClient(transport).upload(image, confirmation_requested=lambda *_args: True)

    assert info.protocol_revision == 2
    read_requests = [request for request in transport.requests if request[:1] == bl.READ_MULTI]
    assert [request[1] for request in read_requests] == [64, 36]
    assert all(request[2:] == bl.EOC for request in read_requests)


def test_identify_resets_stale_bytes_before_old_bootloader_fallback() -> None:
    """
    Old bootloader fallback synchronization starts with a clean input buffer.

    GIVEN: The optional external-flash query leaves a stale response on the serial input
    WHEN: The client falls back after the query fails
    THEN: The stale bytes are cleared before fallback synchronization and identification succeeds
    """

    class OldBootloaderTransport(FakeBootloaderTransport):
        """Leave stale bytes after rejecting the external-flash query."""

        def __init__(self) -> None:
            super().__init__(revision=2)
            self.reset_count = 0

        def write(self, data: bytes) -> int:
            if data[:1] == bl.GET_DEVICE and data[1:-1] == bl.INFO_EXTF_SIZE:
                self._reply.extend(bl.INVALID + b"old")
                return len(data)
            return super().write(data)

        def read(self, size: int = 1) -> bytes:
            if not self._reply:
                msg = "old bootloader rejected external-flash query"
                raise OSError(msg)
            return super().read(size)

        def reset_input_buffer(self) -> None:
            self.reset_count += 1
            super().reset_input_buffer()

    transport = OldBootloaderTransport()

    info = bl.BootloaderClient(transport).identify()

    assert info == bl.BootloaderInfo(protocol_revision=2, board_id=9, board_revision=0, flash_size=2048, extf_size=0)
    assert transport.reset_count == 2


def test_uploads_and_verifies_external_flash() -> None:
    """
    External-flash erase accepts progress bytes that overlap protocol markers.

    GIVEN: The bootloader reports a monotonic erase-progress ramp containing 18%
    WHEN: An APJ with an external image is uploaded
    THEN: The client consumes progress and waits for the final INSYNC/OK response
    """
    image = fw.parse_apj(apj(b"abcd", extf_image=b"ext"))
    transport = FakeBootloaderTransport()

    bl.BootloaderClient(transport).upload(image, confirmation_requested=lambda *_args: True)

    assert transport.extf == b"ext\xff"
    assert transport.extf_erase_size == image.metadata.extf_image_size
    assert transport.closed
    assert transport.requests == [
        bl.encode_get_sync(),
        bl.encode_get_device(bl.INFO_BL_REV),
        bl.encode_get_device(bl.INFO_EXTF_SIZE),
        bl.encode_get_device(bl.INFO_BOARD_ID),
        bl.encode_get_device(bl.INFO_BOARD_REV),
        bl.encode_get_device(bl.INFO_FLASH_SIZE),
        bl.encode_extf_erase(image.metadata.extf_image_size),
        bl.encode_extf_prog_multi(image.extf_image[0 : bl.PROG_MULTI_MAX]),
        bl.encode_extf_get_crc(image.metadata.extf_image_size),
        bl.encode_chip_erase(),
        bl.encode_prog_multi(image.image),
        bl.encode_get_crc(),
        bl.encode_reboot(),
    ]
    for request in transport.requests:
        if request[:1] in {bl.PROG_MULTI, bl.EXTF_PROG_MULTI}:
            assert request[1] == len(request[2:-1])


def test_upload_splits_internal_and_external_payloads_at_the_protocol_boundary() -> None:
    """
    Both flash regions use complete, word-aligned protocol chunks.

    GIVEN: Each APJ payload is one byte larger than the maximum bootloader chunk
    WHEN: The client uploads and verifies both regions
    THEN: Each region is sent as a maximum chunk followed by a padded four-byte chunk
    """
    internal = bytes(range(253))
    external = bytes(reversed(range(253)))
    image = fw.parse_apj(apj(internal, extf_image=external))
    transport = FakeBootloaderTransport()

    bl.BootloaderClient(transport).upload(image, confirmation_requested=lambda *_args: True)

    internal_requests = [request for request in transport.requests if request[:1] == bl.PROG_MULTI]
    external_requests = [request for request in transport.requests if request[:1] == bl.EXTF_PROG_MULTI]
    assert [request[1] for request in internal_requests] == [252, 4]
    assert [request[1] for request in external_requests] == [252, 4]
    assert [request[2:-1] for request in internal_requests] == [internal[:252], internal[252:] + b"\xff\xff\xff"]
    assert [request[2:-1] for request in external_requests] == [external[:252], external[252:] + b"\xff\xff\xff"]
    assert transport.flash == internal + b"\xff\xff\xff"
    assert transport.extf == external + b"\xff\xff\xff"


def test_external_crc_mismatch_rejects_the_upload() -> None:
    """A bad external-flash CRC must not be accepted after programming."""

    class BadExternalCrcTransport(FakeBootloaderTransport):
        """Return an incorrect CRC after external-flash programming."""

        def write(self, data: bytes) -> int:
            if data[:1] == bl.EXTF_GET_CRC:
                self._reply.extend(struct.pack("<I", 0) + bl.INSYNC + bl.OK)
                return len(data)
            return super().write(data)

    with pytest.raises(fw.BootloaderProtocolError, match="external firmware CRC") as error:
        bl.BootloaderClient(BadExternalCrcTransport()).upload(
            fw.parse_apj(apj(b"abcd", extf_image=b"external")), confirmation_requested=lambda *_args: True
        )

    assert error.value.stage == fw.UploadStage.VERIFYING.value


def test_external_erase_rejects_regressing_progress() -> None:
    class RegressingEraseTransport(FakeBootloaderTransport):
        """Reports external erase progress that moves backwards."""

        def write(self, data: bytes) -> int:
            if data[:1] == bl.EXTF_ERASE:
                self._reply.extend(bl.INSYNC + bl.OK + bytes((10, 20, 19)))
                return len(data)
            return super().write(data)

    client = bl.BootloaderClient(RegressingEraseTransport())

    with pytest.raises(fw.BootloaderProtocolError, match="regressed"):
        client._erase_external(3)


def test_external_erase_rejects_progress_above_one_hundred() -> None:
    """An impossible erase percentage is a protocol error, not completion."""

    class InvalidProgressTransport(FakeBootloaderTransport):
        """Reports an external erase percentage outside the protocol range."""

        def write(self, data: bytes) -> int:
            if data[:1] == bl.EXTF_ERASE:
                self._reply.extend(bl.INSYNC + bl.OK + bytes((101,)))
                return len(data)
            return super().write(data)

    with pytest.raises(fw.BootloaderProtocolError, match="invalid external-flash erase progress"):
        bl.BootloaderClient(InvalidProgressTransport())._erase_external(3)


def test_external_erase_does_not_accept_a_premature_final_status() -> None:
    """The final INSYNC marker is valid only after erase progress reaches the completion threshold."""

    class PrematureCompletionTransport(FakeBootloaderTransport):
        """Places a final status marker before the erase is nearly complete."""

        def write(self, data: bytes) -> int:
            if data[:1] == bl.EXTF_ERASE:
                self._reply.extend(bl.INSYNC + bl.OK + bytes((10,)) + bl.INSYNC + bl.OK)
                return len(data)
            return super().write(data)

    with pytest.raises(fw.BootloaderProtocolError, match="regressed"):
        bl.BootloaderClient(PrematureCompletionTransport())._erase_external(3)


def test_external_erase_reports_a_failed_final_status() -> None:
    """A final external erase failure is not mistaken for successful completion."""

    class FailedEraseTransport(FakeBootloaderTransport):
        """Reports a failed final erase acknowledgement after reaching 100%."""

        def write(self, data: bytes) -> int:
            if data[:1] == bl.EXTF_ERASE:
                self._reply.extend(bl.INSYNC + bl.OK + bytes((100,)) + bl.INSYNC + bl.FAILED)
                return len(data)
            return super().write(data)

    with pytest.raises(fw.BootloaderProtocolError, match="OPERATION FAILED"):
        bl.BootloaderClient(FailedEraseTransport())._erase_external(3)


def test_stalled_external_erase_times_out_without_rebooting_after_erase() -> None:
    class StalledEraseTransport(FakeBootloaderTransport):
        """Stops reporting progress after starting an external erase."""

        def write(self, data: bytes) -> int:
            if data[:1] == bl.EXTF_ERASE:
                self._reply.extend(bl.INSYNC + bl.OK + b"\x00")
                return len(data)
            return super().write(data)

    now = 0.0

    def clock() -> float:
        nonlocal now
        now += 0.25
        return now

    image = fw.parse_apj(apj(b"abcd", extf_image=b"ext"))
    transport = StalledEraseTransport()

    with pytest.raises(fw.BootloaderProtocolError, match="timeout waiting"):
        bl.BootloaderClient(transport, clock=clock).upload(image, confirmation_requested=lambda *_args: True)

    assert not transport.rebooted


@pytest.mark.timeout(5)
def test_external_erase_times_out_when_progress_never_advances() -> None:
    """Repeated progress bytes must not keep a stalled erase alive indefinitely."""

    class RepeatingProgressTransport(FakeBootloaderTransport):
        """Reports 1% forever after acknowledging the erase command."""

        def __init__(self) -> None:
            super().__init__()
            self.erasing = False

        def write(self, data: bytes) -> int:
            if data[:1] == bl.EXTF_ERASE:
                self.erasing = True
                self._reply.extend(bl.INSYNC + bl.OK)
                return len(data)
            return super().write(data)

        def read(self, size: int = 1) -> bytes:
            reply = super().read(size)
            return reply or (b"\x01" if self.erasing else b"")

    now = 0.0

    def clock() -> float:
        nonlocal now
        now += 0.25
        return now

    with pytest.raises(fw.BootloaderProtocolError, match="timeout waiting"):
        bl.BootloaderClient(RepeatingProgressTransport(), clock=clock)._erase_external(3)


def test_external_erase_refreshes_deadline_only_when_progress_advances() -> None:
    """A progressing erase may exceed 20 seconds, but each advance refreshes inactivity timeout."""

    class SlowProgressTransport:
        """Deliver one erase-progress byte every two simulated seconds."""

        def __init__(self) -> None:
            self.now = 0.0
            self.reply = bytearray()

        def write(self, data: bytes) -> int:
            assert data[:1] == bl.EXTF_ERASE
            self.reply.extend(bl.INSYNC + bl.OK + bytes(range(0, 101, 10)) + bl.INSYNC + bl.OK)
            return len(data)

        def flush(self) -> None:
            pass

        def read(self, size: int = 1) -> bytes:
            self.now += 2.0
            count = min(1, size, len(self.reply))
            data = bytes(self.reply[:count])
            del self.reply[:count]
            return data

    transport = SlowProgressTransport()
    bl.BootloaderClient(transport, timeout=10.0, clock=lambda: transport.now)._erase_external(3)

    assert transport.now > bl.ERASE_TIMEOUT


def test_external_only_upload_does_not_touch_internal_flash() -> None:
    """External-only firmware skips internal erase, programming, and verification."""
    image = fw.parse_apj(apj(b"", extf_image=b"external"))
    transport = FakeBootloaderTransport()

    bl.BootloaderClient(transport).upload(image, confirmation_requested=lambda *_args: True)

    assert transport.flash == b""
    assert transport.extf == b"external"
    assert transport.closed
    assert not any(
        command in {bl.CHIP_ERASE, bl.CHIP_FULL_ERASE, bl.PROG_MULTI, bl.CHIP_VERIFY, bl.READ_MULTI, bl.GET_CRC}
        for command in transport.commands
    )


def test_upload_reports_each_external_and_internal_region_in_order() -> None:
    """
    Progress distinguishes the two flash regions and their verification phases.

    GIVEN: An APJ contains both external and internal firmware regions
    WHEN: The bootloader uploads and verifies the APJ
    THEN: Progress reports each region in protocol order without merging stages
    """
    events: list[tuple[bl.UploadStage, int, int]] = []
    transport = FakeBootloaderTransport()

    bl.BootloaderClient(transport).upload(
        fw.parse_apj(apj(b"abcd", extf_image=b"ext")),
        confirmation_requested=lambda *_args: True,
        progress_callback=lambda stage, done, total: events.append((stage, done, total)),
    )

    assert events == [
        (fw.UploadStage.IDENTIFYING, 0, 1),
        (fw.UploadStage.IDENTIFYING, 1, 1),
        (fw.UploadStage.AWAITING_CONFIRMATION, 0, 1),
        (fw.UploadStage.AWAITING_CONFIRMATION, 1, 1),
        (fw.UploadStage.ERASING, 0, 1),
        (fw.UploadStage.ERASING, 1, 1),
        (fw.UploadStage.PROGRAMMING, 1, 1),
        (fw.UploadStage.VERIFYING, 0, 1),
        (fw.UploadStage.VERIFYING, 1, 1),
        (fw.UploadStage.ERASING, 0, 1),
        (fw.UploadStage.ERASING, 1, 1),
        (fw.UploadStage.PROGRAMMING, 1, 1),
        (fw.UploadStage.VERIFYING, 0, 1),
        (fw.UploadStage.VERIFYING, 1, 1),
        (fw.UploadStage.REBOOTING, 0, 1),
        (fw.UploadStage.REBOOTING, 1, 1),
    ]


def test_upload_survives_progress_callback_failures() -> None:
    """A presentation callback failure cannot interrupt a verified flash."""
    transport = FakeBootloaderTransport()

    def broken_progress(*_args: object) -> None:
        msg = "progress UI failed"
        raise RuntimeError(msg)

    bl.BootloaderClient(transport).upload(
        fw.parse_apj(apj(b"abcd")),
        confirmation_requested=lambda *_args: True,
        progress_callback=broken_progress,
    )

    assert transport.flash == b"abcd"
    assert transport.rebooted
    assert transport.closed


def test_failed_upload_still_closes_transport() -> None:
    image = fw.parse_apj(apj(b"abcd"))
    transport = FakeBootloaderTransport(flash_size=0)

    with pytest.raises(fw.FirmwareCompatibilityError, match="exceeds flash"):
        bl.BootloaderClient(transport).upload(image, confirmation_requested=lambda *_args: True)
    assert transport.closed


def test_read_timeout_is_bounded_even_when_serial_keeps_returning_empty_reads() -> None:
    class EmptyReadTransport(FakeBootloaderTransport):
        """Transport that simulates a serial port timing out without a response."""

        reads = 0

        def read(self, size: int = 1) -> bytes:
            self.reads += 1
            return b""

    transport = EmptyReadTransport()
    clock_values = iter([0.0, 0.5, 1.0])
    client = bl.BootloaderClient(transport, timeout=1.0, clock=lambda: next(clock_values))

    with pytest.raises(fw.BootloaderProtocolError, match="timeout waiting"):
        client._read_exact(1)  # Exercise the transport deadline directly.

    assert transport.reads == 1


def test_client_uses_injected_sleep_for_empty_nonblocking_reads() -> None:
    """The read-loop yield is deterministic and does not need a module monkeypatch."""

    class EmptyReadTransport(FakeBootloaderTransport):
        """Return empty reads to exercise the injected yield function."""

        def read(self, size: int = 1) -> bytes:
            return b""

    sleeps: list[float] = []
    clock_values = iter([0.0, 0.0, 0.5, 1.0])
    client = bl.BootloaderClient(EmptyReadTransport(), timeout=1.0, clock=lambda: next(clock_values), sleep=sleeps.append)

    with pytest.raises(fw.BootloaderProtocolError, match="timeout waiting"):
        client._read_exact(1)

    assert sleeps == [0.01]


def test_backend_passes_its_injected_sleep_to_the_bootloader_client() -> None:
    """
    Bootloader discovery keeps the client's nonblocking-read yield injectable.

    GIVEN: Opening the bootloader succeeds but its first read is empty
    WHEN: The backend uploads firmware with an injected sleep function
    THEN: The bootloader client uses that function rather than module-global sleep
    """

    class EmptyOnceTransport(FakeBootloaderTransport):
        """Return one empty read before providing the bootloader response."""

        empty_reads = 1

        def read(self, size: int = 1) -> bytes:
            if self.empty_reads:
                self.empty_reads -= 1
                return b""
            return super().read(size)

    sleeps: list[float] = []
    backend = bl.FlightControllerBootloaderBackend(
        "COM7",
        115200,
        serial_factory=lambda *_args: EmptyOnceTransport(),
        sleep=sleeps.append,
    )

    backend.upload(fw.parse_apj(apj(b"abcd")), confirmation_requested=lambda *_args: True)

    assert sleeps == [0.01]


@pytest.mark.parametrize(
    ("operation", "error_type", "message"),
    [
        ("write", OSError, "transport write failed"),
        ("read", serial.SerialException, "transport read failed"),
        ("read", OSError, "transport read failed"),
        ("flush", serial.SerialException, "transport write failed"),
        ("reset", OSError, "cannot clear bootloader serial input"),
        ("reset", serial.SerialException, "cannot clear bootloader serial input"),
    ],
)
def test_transport_errors_are_converted_to_typed_protocol_errors(
    operation: str, error_type: type[Exception], message: str
) -> None:
    """Serial-layer failures must not escape as untyped transport exceptions."""

    class FailingTransport:
        """Raise the selected serial failure from one transport operation."""

        def write(self, _data: bytes) -> int:
            if operation == "write":
                msg = "transport failed"
                raise error_type(msg)
            return 0

        def read(self, _size: int = 1) -> bytes:
            if operation == "read":
                msg = "transport failed"
                raise error_type(msg)
            return b""

        def flush(self) -> None:
            if operation == "flush":
                msg = "transport failed"
                raise error_type(msg)

        def reset_input_buffer(self) -> None:
            if operation == "reset":
                msg = "transport failed"
                raise error_type(msg)

        def close(self) -> None:
            pass

    client = bl.BootloaderClient(FailingTransport(), sleep=lambda _delay: None)
    action = {
        "write": lambda: client._write(bl.encode_get_sync()),
        "read": lambda: client._read_exact(1),
        "flush": lambda: client._write(bl.encode_get_sync()),
        "reset": client._reset_input_buffer,
    }[operation]

    with pytest.raises(fw.BootloaderProtocolError, match=message):
        action()


@pytest.mark.parametrize(
    ("operation", "reply_size"),
    [
        ("get_sync", 0),
        ("get_device", 4),
        ("chip_erase", 0),
        ("full_erase", 0),
        ("chip_verify", 0),
        ("prog_multi", 0),
        ("extf_prog_multi", 0),
        ("extf_erase", 0),
        ("read_multi", 4),
        ("get_crc", 4),
        ("extf_get_crc", 4),
        ("reboot", 0),
    ],
)
def test_each_bootloader_command_rejects_a_failed_status(operation: str, reply_size: int) -> None:
    """Every command path propagates a failed bootloader status as a typed error."""

    class FailedStatusTransport:
        """Return a failed status for any command while preserving expected reply lengths."""

        def __init__(self) -> None:
            self.reply = bytearray()

        def write(self, data: bytes) -> int:
            command = data[:1]
            if command in {bl.GET_DEVICE, bl.READ_MULTI, bl.GET_CRC, bl.EXTF_GET_CRC}:
                self.reply.extend(b"\x00" * 4)
            self.reply.extend(bl.INSYNC + bl.FAILED)
            return len(data)

        def read(self, size: int = 1) -> bytes:
            data = bytes(self.reply[:size])
            del self.reply[:size]
            return data

        def flush(self) -> None:
            pass

        def reset_input_buffer(self) -> None:
            self.reply.clear()

        def close(self) -> None:
            pass

    requests = {
        "get_sync": bl.encode_get_sync(),
        "get_device": bl.encode_get_device(bl.INFO_BL_REV),
        "chip_erase": bl.encode_chip_erase(),
        "full_erase": bl.encode_chip_erase(full=True),
        "chip_verify": bl.encode_chip_verify(),
        "prog_multi": bl.encode_prog_multi(b"\x00\x00\x00\x00"),
        "extf_prog_multi": bl.encode_extf_prog_multi(b"\x00\x00\x00\x00"),
        "extf_erase": bl.encode_extf_erase(4),
        "read_multi": bl.encode_read_multi(4),
        "get_crc": bl.encode_get_crc(),
        "extf_get_crc": bl.encode_extf_get_crc(4),
        "reboot": bl.encode_reboot(),
    }
    client = bl.BootloaderClient(FailedStatusTransport())

    with pytest.raises(fw.BootloaderProtocolError, match="OPERATION FAILED"):
        client._command(requests[operation], reply_size)


def test_partial_transport_write_is_rejected() -> None:
    class PartialWriteTransport:
        """Accept only part of each request."""

        def write(self, data: bytes) -> int:
            return len(data) - 1

        def flush(self) -> None:
            pass

    client = bl.BootloaderClient(PartialWriteTransport())

    with pytest.raises(fw.BootloaderProtocolError, match="wrote 1 of 2 bytes"):
        client._write(bl.encode_get_sync())


def test_client_requires_confirmation_and_reboots_before_closing() -> None:
    transport = FakeBootloaderTransport()

    with pytest.raises(fw.FirmwareConfirmationError, match="explicit confirmation"):
        bl.BootloaderClient(transport).upload(fw.parse_apj(apj(b"abcd")))

    assert transport.rebooted
    assert transport.closed


def test_declined_confirmation_reboots_before_closing() -> None:
    transport = FakeBootloaderTransport()

    with pytest.raises(fw.FirmwareUploadCancelledError, match="not confirmed"):
        bl.BootloaderClient(transport).upload(fw.parse_apj(apj(b"abcd")), confirmation_requested=lambda *_args: False)

    assert transport.rebooted
    assert transport.closed


def test_parse_apj_is_pure_and_requires_declared_size_to_match() -> None:
    contents = apj(b"four", image_size=1)

    with pytest.raises(fw.FirmwareFileError, match="image_size"):
        fw.parse_apj(contents, path=Path("firmware.apj"))


def test_parse_apj_wraps_invalid_unicode_text_as_a_file_error() -> None:
    """The public text parser must not leak UnicodeEncodeError."""
    with pytest.raises(fw.FirmwareFileError, match="cannot parse APJ descriptor"):
        fw.parse_apj("\ud800")


def test_parse_apj_wraps_excessively_nested_json_as_a_file_error() -> None:
    """Deep but size-bounded APJ JSON must not leak RecursionError."""
    contents = b'{"x":' * 50_000 + b"0" + b"}" * 50_000
    assert len(contents) < bl.MAX_APJ_DESCRIPTOR_SIZE

    with pytest.raises(fw.FirmwareFileError):
        fw.parse_apj(contents)


def test_invalid_board_revision_is_a_typed_file_error() -> None:
    with pytest.raises(fw.FirmwareFileError, match="metadata"):
        fw.parse_apj(apj(b"four", board_revision="not-a-number"))


@pytest.mark.skipif(not hasattr(sys, "get_int_max_str_digits"), reason="CPython integer digit limit was added in Python 3.11")
def test_parse_apj_wraps_json_integer_digit_limit_as_file_error() -> None:
    """A JSON number beyond CPython's digit limit must not escape untyped."""
    digit_limit = sys.get_int_max_str_digits()
    if digit_limit == 0:
        pytest.skip("CPython integer digit limit is disabled")

    contents = b'{"board_id":' + (b"9" * (digit_limit + 1)) + b"}"

    with pytest.raises(fw.FirmwareFileError, match="cannot parse APJ descriptor"):
        fw.parse_apj(contents)


def test_padded_payload_capacity_and_compatible_board_mapping_are_checked() -> None:
    image = fw.parse_apj(apj(b"abc"))
    with pytest.raises(fw.FirmwareCompatibilityError, match="exceeds flash"):
        fw.check_compatibility(image, fw.BootloaderInfo(5, 9, 0, 0))

    fw.check_compatibility(image, fw.BootloaderInfo(5, 33, 0, 4))


def test_bounded_decompression_rejects_before_full_output_is_allocated(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(fw, "MAX_IMAGE_SIZE", 32)

    limits: list[int] = []

    class BoundedDecompressor:
        """Expose the decompressor output limit supplied by the parser."""

        unconsumed_tail = b"still compressed"
        unused_data = b""
        eof = True

        def decompress(self, _compressed: bytes, max_length: int) -> bytes:
            limits.append(max_length)
            return b"x" * max_length

        def flush(self) -> bytes:
            return b""

    monkeypatch.setattr(fw.zlib, "decompressobj", BoundedDecompressor)

    with pytest.raises(fw.FirmwareFileError, match="exceeds"):
        fw.parse_apj(apj(b"x" * 64))
    assert limits == [33]


def test_parser_rejects_trailing_compressed_data_and_non_text_version() -> None:
    encoded = base64.b64encode(zlib.compress(b"abcd") + b"unexpected").decode()
    trailing_data = json.dumps({"board_id": 9, "image_size": 4, "image": encoded})

    with pytest.raises(fw.FirmwareFileError, match="trailing bytes"):
        fw.parse_apj(trailing_data)
    with pytest.raises(fw.FirmwareFileError, match="version metadata"):
        fw.parse_apj(apj(b"abcd", version=46))
    with pytest.raises(fw.FirmwareFileError, match="git_identity metadata"):
        fw.parse_apj(apj(b"abcd", git_identity=42))


def test_parser_rejects_oversized_encoded_blob_before_base64_decode(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(fw, "MAX_ENCODED_BLOB_SIZE", 8)

    with pytest.raises(fw.FirmwareFileError, match="encoded"):
        fw.parse_apj(apj(b"abcd"))


def test_reader_rejects_oversized_apj_descriptor_before_reading(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = tmp_path / "firmware.apj"
    path.write_bytes(apj(b"abcd"))
    monkeypatch.setattr(bl, "MAX_APJ_DESCRIPTOR_SIZE", 8)

    with pytest.raises(fw.FirmwareFileError, match="descriptor exceeds"):
        bl.load_apj(path)


def test_load_apj_rejects_non_apj_suffix(tmp_path: Path) -> None:
    path = tmp_path / "firmware.bin"
    path.write_bytes(b"whatever")

    with pytest.raises(fw.FirmwareFileError, match="unsupported firmware format"):
        bl.load_apj(path)


def test_encode_extf_erase_rejects_out_of_range_size() -> None:
    with pytest.raises(ValueError, match="external flash size"):
        bl.encode_extf_erase(0)
    with pytest.raises(ValueError, match="external flash size"):
        bl.encode_extf_erase(0x1_0000_0000)


def test_bootloader_client_rejects_non_positive_timeout() -> None:
    with pytest.raises(ValueError, match="timeout must be positive"):
        bl.BootloaderClient(FakeBootloaderTransport(), timeout=0)


def test_identify_rejects_unsupported_protocol_revision() -> None:
    transport = FakeBootloaderTransport(revision=1)
    with pytest.raises(fw.BootloaderProtocolError, match="unsupported bootloader protocol revision"):
        bl.BootloaderClient(transport).identify()


def test_bootloader_port_is_re_resolved_by_usb_identity_and_ambiguity_is_refused(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A re-enumerated bootloader must not reuse an arbitrary stale serial port."""
    reenumerated = ListPortInfo("COM11")
    reenumerated.location = "1-2.3"
    reenumerated.serial_number = "FC-123"
    monkeypatch.setattr(bl.serial.tools.list_ports, "comports", lambda: [reenumerated])

    identity = bl.SerialDeviceIdentity(location="1-2.3", serial_number="FC-123")
    assert bl.resolve_bootloader_device("COM7", identity) == "COM11"

    duplicate = ListPortInfo("COM12")
    duplicate.location = "1-2.3"
    duplicate.serial_number = "FC-123"
    monkeypatch.setattr(bl.serial.tools.list_ports, "comports", lambda: [reenumerated, duplicate])
    with pytest.raises(OSError, match="cannot uniquely"):
        bl.resolve_bootloader_device("COM7", identity)


def test_usb_identity_is_used_for_reenumerated_linux_devices(monkeypatch: pytest.MonkeyPatch) -> None:
    """A matching USB identity must win over the old Linux device path."""
    reenumerated = ListPortInfo("/dev/ttyACM1")
    reenumerated.location = "1-2.3"
    reenumerated.serial_number = "FC-123"
    monkeypatch.setattr(bl.serial.tools.list_ports, "comports", lambda: [reenumerated])

    identity = bl.SerialDeviceIdentity(location="1-2.3", serial_number="FC-123")

    assert bl.resolve_bootloader_device("/dev/ttyACM0", identity) == "/dev/ttyACM1"


def test_bootloader_port_prefers_usb_identity_over_reused_linux_device_path(monkeypatch: pytest.MonkeyPatch) -> None:
    """A newly assigned tty path must not override the captured controller identity."""
    reenumerated = ListPortInfo("/dev/ttyACM1")
    reenumerated.location = "1-2.3"
    reenumerated.serial_number = "FC-123"
    monkeypatch.setattr(bl.serial.tools.list_ports, "comports", lambda: [reenumerated])

    assert (
        bl.resolve_bootloader_device("/dev/ttyACM0", bl.SerialDeviceIdentity(location="1-2.3", serial_number="FC-123"))
        == "/dev/ttyACM1"
    )


def test_bootloader_upload_requires_usb_metadata(monkeypatch: pytest.MonkeyPatch) -> None:
    """The upload gate rejects a connection with no stable USB metadata."""
    monkeypatch.setattr(bl.serial.tools.list_ports, "comports", list)

    identity = bl.capture_serial_device_identity("/dev/ttyACM0")

    assert identity is None
    assert not bl.has_stable_bootloader_device_identity("/dev/ttyACM0", identity)


def test_bootloader_port_refuses_a_different_usb_serial(monkeypatch: pytest.MonkeyPatch) -> None:
    """A different USB serial number cannot satisfy the captured identity."""
    replacement = ListPortInfo("/dev/ttyACM1")
    replacement.location = "1-2.3"
    replacement.serial_number = "OTHER"
    monkeypatch.setattr(bl.serial.tools.list_ports, "comports", lambda: [replacement])
    identity = bl.SerialDeviceIdentity(
        location="1-2.3",
        serial_number="ORIGINAL",
    )

    with pytest.raises(OSError, match="cannot uniquely"):
        bl.resolve_bootloader_device("/dev/ttyACM0", identity)


def test_client_reports_recovery_error_when_pre_erase_reboot_fails() -> None:
    class RebootFailureTransport(FakeBootloaderTransport):
        """Fail reboot writes to exercise the recovery error path."""

        def write(self, data: bytes) -> int:
            if data[:1] == bl.REBOOT:
                msg = "reboot write failed"
                raise OSError(msg)
            return super().write(data)

    transport = RebootFailureTransport(board_id=9)
    image = fw.parse_apj(apj(b"abcd", board_id=42))

    with pytest.raises(fw.FirmwareBootloaderRecoveryError, match="power-cycle"):
        bl.BootloaderClient(transport).upload(image, confirmation_requested=lambda *_args: True)

    assert transport.closed


def test_full_erase_is_refused_before_any_flash_command() -> None:
    """The client refuses full erase until it can determine the board capability safely."""
    transport = FakeBootloaderTransport()

    with pytest.raises(fw.FirmwareCompatibilityError, match="full firmware erase"):
        bl.BootloaderClient(transport).upload(
            fw.parse_apj(apj(b"abcd")), full_erase=True, confirmation_requested=lambda *_args: True
        )

    assert bl.CHIP_FULL_ERASE not in transport.commands
    assert transport.flash == b""


def test_backend_rejects_invalid_timeout_before_entering_bootloader() -> None:
    entered = False

    def enter() -> None:
        nonlocal entered
        entered = True

    with pytest.raises(ValueError, match="timeout"):
        bl.FlightControllerBootloaderBackend("COM7", 115200, timeout=0, enter_bootloader=enter)

    assert not entered


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
        self.active_baudrate = 921600
        self.info = FlightControllerInfo()
        self.info.apj_board_id = "9"
        self.disconnected = False
        self.reconnected = False
        self.reconnect_baudrate: int | None = None
        self.reconnect_device: str | None = None

    def discover_connections(self, **_kwargs: object) -> None:
        pass

    def disconnect(self) -> None:
        self.disconnected = True
        self.master = None  # type: ignore[assignment]

    def create_connection_with_retry(self, *_args: object, **kwargs: object) -> str:
        self.reconnected = True
        self.reconnect_baudrate = kwargs.get("baudrate") if isinstance(kwargs.get("baudrate"), int) else None
        return ""

    def connect(self, device: str, **kwargs: object) -> str:
        self.reconnect_device = device
        self.comport_device = device
        self.master = _Master()
        return self.create_connection_with_retry(**kwargs)


class _Params:
    def __init__(self) -> None:
        self.cleared = 0

    def clear_parameters(self) -> None:
        self.cleared += 1


class _Commands:
    COMMAND_ACK_TIMEOUT = 5.0

    def __init__(self, result: tuple[bool, str] = (True, "")) -> None:
        self.result = result
        self.calls: list[dict[str, object]] = []

    def send_command_and_wait_ack(self, **kwargs: object) -> tuple[bool, str]:
        self.calls.append(kwargs)
        return self.result

    def reboot_to_bootloader(self) -> tuple[bool, str]:
        return self.send_command_and_wait_ack(param1=3)


def test_facade_reconnects_using_the_reenumerated_serial_device(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Reconnection follows the controller's stable identity after re-enumeration.

    GIVEN: The controller was connected on COM7 and is captured with a stable USB identity
    WHEN: Flashing makes the controller reappear on COM13
    THEN: The facade reconnects through COM13 and updates the active connection
    """
    connection = _Connection()
    params = _Params()
    commands = _Commands()
    transport = FakeBootloaderTransport()
    controller = FlightController(
        connection_manager=connection,  # type: ignore[arg-type]
        params_manager=params,  # type: ignore[arg-type]
        commands_manager=commands,  # type: ignore[arg-type]
        files_manager=object(),  # type: ignore[arg-type]
    )
    path = tmp_path / "firmware.apj"
    path.write_bytes(apj(b"abcd"))
    monkeypatch.setattr(
        "ardupilot_methodic_configurator.backend_flightcontroller.resolve_bootloader_device",
        lambda _device, _identity: "COM13",
    )

    controller.upload_apj_firmware(
        path,
        expected_firmware_sha256=trusted_digest(b"abcd"),
        serial_factory=lambda *_args: transport,
        confirmation_requested=lambda *_args: True,
    )

    assert connection.disconnected
    assert connection.reconnected
    assert connection.reconnect_device == "COM13"
    assert connection.reconnect_baudrate == 921600
    assert commands.calls[0]["param1"] == 3
    assert transport.closed
    assert params.cleared == 2


def test_facade_verifies_board_identity_after_reconnect(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """
    A successful serial reconnect still requires the expected APJ board identity.

    GIVEN: The bootloader flashes successfully but the reconnected MAVLink board is different
    WHEN: The facade completes the reconnect step
    THEN: It rejects the result with a firmware identity error
    """

    class WrongBoardAfterReconnect(_Connection):
        """Change the reported board identity when the new MAVLink connection opens."""

        def create_connection_with_retry(self, *_args: object, **kwargs: object) -> str:
            result = super().create_connection_with_retry(*_args, **kwargs)
            self.info.apj_board_id = "42"
            return result

    connection = WrongBoardAfterReconnect()
    controller = FlightController(
        connection_manager=connection,  # type: ignore[arg-type]
        params_manager=_Params(),  # type: ignore[arg-type]
        commands_manager=_Commands(),  # type: ignore[arg-type]
        files_manager=object(),  # type: ignore[arg-type]
    )
    path = tmp_path / "firmware.apj"
    path.write_bytes(apj(b"abcd"))
    monkeypatch.setattr(
        "ardupilot_methodic_configurator.backend_flightcontroller.resolve_bootloader_device",
        lambda _device, _identity: "COM13",
    )

    with pytest.raises(fw.FirmwareIdentityError, match="does not match firmware"):
        controller.upload_apj_firmware(
            path,
            expected_firmware_sha256=trusted_digest(b"abcd"),
            serial_factory=lambda *_args: FakeBootloaderTransport(),
            confirmation_requested=lambda *_args: True,
        )

    assert connection.reconnected
    assert connection.reconnect_device == "COM13"


def test_facade_waits_for_serial_identity_to_reappear_before_reconnecting(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    Reconnection waits while the board is temporarily absent during re-enumeration.

    GIVEN: The stable USB identity is unavailable during the first resolver calls
    WHEN: The firmware upload completes and starts reconnection
    THEN: The facade retries identity resolution and connects after the board reappears
    """
    connection = _Connection()
    commands = _Commands()
    controller = FlightController(
        connection_manager=connection,  # type: ignore[arg-type]
        params_manager=_Params(),  # type: ignore[arg-type]
        commands_manager=commands,  # type: ignore[arg-type]
        files_manager=object(),  # type: ignore[arg-type]
    )
    path = tmp_path / "firmware.apj"
    path.write_bytes(apj(b"abcd"))
    resolver_calls = 0

    def resolve(_device: str, _identity: object) -> str:
        nonlocal resolver_calls
        resolver_calls += 1
        if resolver_calls < 3:
            msg = "device is still re-enumerating"
            raise OSError(msg)
        return "COM13"

    monkeypatch.setattr(
        "ardupilot_methodic_configurator.backend_flightcontroller.resolve_bootloader_device",
        resolve,
    )

    controller.upload_apj_firmware(
        path,
        expected_firmware_sha256=trusted_digest(b"abcd"),
        serial_factory=lambda *_args: FakeBootloaderTransport(),
        confirmation_requested=lambda *_args: True,
    )

    assert resolver_calls == 3
    assert connection.reconnect_device == "COM13"


def test_facade_retries_reconnect_when_connect_returns_an_error(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Reconnection keeps trying while connect() reports a transient failure.

    GIVEN: resolve_bootloader_device succeeds at once but the board is not open yet
    WHEN: connect() returns an error string on the first attempts then an empty string
    THEN: The facade spends the retry budget and reports success once connect() succeeds
    """
    connect_results = iter(["port not ready", "port not ready", ""])

    class _FlakyConnection(_Connection):
        def connect(self, device: str, **kwargs: object) -> str:
            self.reconnect_device = device
            self.comport_device = device
            self.master = _Master()
            error = next(connect_results)
            if not error:
                self.reconnected = True
            return error

    connection = _FlakyConnection()
    controller = FlightController(
        connection_manager=connection,  # type: ignore[arg-type]
        params_manager=_Params(),  # type: ignore[arg-type]
        commands_manager=_Commands(),  # type: ignore[arg-type]
        files_manager=object(),  # type: ignore[arg-type]
    )
    path = tmp_path / "firmware.apj"
    path.write_bytes(apj(b"abcd"))
    monkeypatch.setattr(
        "ardupilot_methodic_configurator.backend_flightcontroller.resolve_bootloader_device",
        lambda _device, _identity: "COM13",
    )

    controller.upload_apj_firmware(
        path,
        expected_firmware_sha256=trusted_digest(b"abcd"),
        serial_factory=lambda *_args: FakeBootloaderTransport(),
        confirmation_requested=lambda *_args: True,
    )

    assert connection.reconnected
    assert connection.reconnect_device == "COM13"


def test_facade_reports_reconnect_retry_exhaustion_after_a_verified_flash(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    Reconnect failures consume the bounded retry window and preserve the recovery message.

    GIVEN: The bootloader flash succeeds but every MAVLink reconnect attempt fails
    WHEN: The facade exhausts its reconnect deadline
    THEN: It reports that the verified controller must be reconnected manually
    """
    now = 0.0
    connect_calls = 0

    def clock() -> float:
        return now

    def sleep(delay: float) -> None:
        nonlocal now
        now += delay

    class NeverReadyConnection(_Connection):
        """Keep reporting a transient connection error until the retry deadline."""

        def connect(self, device: str, **kwargs: object) -> str:
            nonlocal connect_calls
            connect_calls += 1
            self.reconnect_device = device
            self.comport_device = device
            self.master = _Master()
            return "port not ready"

    monkeypatch.setattr("ardupilot_methodic_configurator.backend_flightcontroller.time_monotonic", clock)
    monkeypatch.setattr("ardupilot_methodic_configurator.backend_flightcontroller.time_sleep", sleep)
    monkeypatch.setattr("ardupilot_methodic_configurator.backend_flightcontroller.FIRMWARE_RECONNECT_RESOLVE_TIMEOUT", 0.25)
    monkeypatch.setattr(
        "ardupilot_methodic_configurator.backend_flightcontroller.resolve_bootloader_device",
        lambda _device, _identity: "COM13",
    )
    connection = NeverReadyConnection()
    controller = FlightController(
        connection_manager=connection,  # type: ignore[arg-type]
        params_manager=_Params(),  # type: ignore[arg-type]
        commands_manager=_Commands(),  # type: ignore[arg-type]
        files_manager=object(),  # type: ignore[arg-type]
    )
    path = tmp_path / "firmware.apj"
    path.write_bytes(apj(b"abcd"))

    with pytest.raises(fw.FirmwareReconnectError, match=r"written and verified.*Reconnect it manually"):
        controller.upload_apj_firmware(
            path,
            expected_firmware_sha256=trusted_digest(b"abcd"),
            serial_factory=lambda *_args: FakeBootloaderTransport(),
            confirmation_requested=lambda *_args: True,
        )

    assert connect_calls == 3
    assert now == pytest.approx(0.6)


def test_facade_reports_rejected_bootloader_entry_without_releasing_serial(tmp_path: Path) -> None:
    """
    A rejected bootloader command stops the upload before disconnecting MAVLink.

    GIVEN: The connected vehicle rejects the reboot-and-hold command
    WHEN: A firmware upload requests bootloader entry
    THEN: The user receives the rejection reason and the active connection remains available
    """
    connection = _Connection()
    commands = _Commands((False, "Command denied"))
    controller = FlightController(
        connection_manager=connection,  # type: ignore[arg-type]
        params_manager=_Params(),  # type: ignore[arg-type]
        commands_manager=commands,  # type: ignore[arg-type]
        files_manager=object(),  # type: ignore[arg-type]
    )
    path = tmp_path / "firmware.apj"
    path.write_bytes(apj(b"abcd"))

    with pytest.raises(fw.FirmwareConnectionError, match="Command denied"):
        controller.upload_apj_firmware(
            path,
            expected_firmware_sha256=trusted_digest(b"abcd"),
            confirmation_requested=lambda *_args: True,
        )

    assert not connection.disconnected
    assert connection.master is not None


def test_facade_requires_trusted_sha_before_flashing(tmp_path: Path) -> None:
    connection = _Connection()
    controller = FlightController(
        connection_manager=connection,  # type: ignore[arg-type]
        params_manager=_Params(),  # type: ignore[arg-type]
        commands_manager=_Commands(),  # type: ignore[arg-type]
        files_manager=object(),  # type: ignore[arg-type]
    )
    path = tmp_path / "firmware.apj"
    path.write_bytes(apj(b"abcd"))

    with pytest.raises(fw.FirmwareConfirmationError, match="trusted SHA-256"):
        controller.upload_apj_firmware(
            path,
            expected_firmware_sha256=None,
            serial_factory=lambda *_args: FakeBootloaderTransport(),
            confirmation_requested=lambda *_args: True,
        )
    assert not connection.disconnected


def test_facade_validates_the_trusted_digest_before_bootloader_entry(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The facade must not allow a selected APJ to bypass its release digest."""
    calls: list[str] = []
    connection = _Connection()
    controller = FlightController(
        connection_manager=connection,  # type: ignore[arg-type]
        params_manager=_Params(),  # type: ignore[arg-type]
        commands_manager=_Commands(),  # type: ignore[arg-type]
        files_manager=object(),  # type: ignore[arg-type]
    )
    path = tmp_path / "firmware.apj"
    path.write_bytes(apj(b"abcd"))
    monkeypatch.setattr(
        "ardupilot_methodic_configurator.backend_flightcontroller.verify_expected_firmware_digest",
        lambda _image, digest: calls.append(digest),
    )

    controller.upload_apj_firmware(
        path,
        expected_firmware_sha256="0" * 64,
        serial_factory=lambda *_args: FakeBootloaderTransport(),
        confirmation_requested=lambda *_args: True,
    )

    assert calls == ["0" * 64]


def test_facade_reports_a_verified_flash_when_automatic_reconnect_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A post-flash port ambiguity must tell the user to reconnect manually."""
    connection = _Connection()
    controller = FlightController(
        connection_manager=connection,  # type: ignore[arg-type]
        params_manager=_Params(),  # type: ignore[arg-type]
        commands_manager=_Commands(),  # type: ignore[arg-type]
        files_manager=object(),  # type: ignore[arg-type]
    )
    path = tmp_path / "firmware.apj"
    path.write_bytes(apj(b"abcd"))
    monkeypatch.setattr("ardupilot_methodic_configurator.backend_flightcontroller.FIRMWARE_RECONNECT_RESOLVE_TIMEOUT", 0)

    with pytest.raises(fw.FirmwareReconnectError, match=r"written and verified.*Reconnect it manually"):
        controller.upload_apj_firmware(
            path,
            expected_firmware_sha256=trusted_digest(b"abcd"),
            serial_factory=lambda *_args: FakeBootloaderTransport(),
            confirmation_requested=lambda *_args: True,
        )


def test_facade_refuses_network_mavlink_connection() -> None:
    connection = _Connection("udp:127.0.0.1:14550")
    controller = FlightController(
        connection_manager=connection,  # type: ignore[arg-type]
        params_manager=_Params(),  # type: ignore[arg-type]
        commands_manager=object(),  # type: ignore[arg-type]
        files_manager=object(),  # type: ignore[arg-type]
    )

    with pytest.raises(fw.FirmwareConnectionError, match="direct serial"):
        controller.upload_apj_firmware(Path("ignored.apj"))


def test_facade_requires_pre_reboot_board_identity(tmp_path: Path) -> None:
    connection = _Connection()
    connection.info.apj_board_id = ""
    controller = FlightController(
        connection_manager=connection,  # type: ignore[arg-type]
        params_manager=_Params(),  # type: ignore[arg-type]
        commands_manager=object(),  # type: ignore[arg-type]
        files_manager=object(),  # type: ignore[arg-type]
    )
    path = tmp_path / "firmware.apj"
    path.write_bytes(apj(b"abcd"))

    with pytest.raises(fw.FirmwareConnectionError, match="APJ board_id"):
        controller.upload_apj_firmware(
            path,
            expected_firmware_sha256=trusted_digest(b"abcd"),
            confirmation_requested=lambda *_args: True,
        )

    assert not connection.master.held_in_bootloader


def test_facade_requires_stable_usb_identity_before_bootloader_entry(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """An unidentifiable serial connection must not be rebooted into the bootloader."""
    connection = _Connection()
    controller = FlightController(
        connection_manager=connection,  # type: ignore[arg-type]
        params_manager=_Params(),  # type: ignore[arg-type]
        commands_manager=_Commands(),  # type: ignore[arg-type]
        files_manager=object(),  # type: ignore[arg-type]
    )
    path = tmp_path / "firmware.apj"
    path.write_bytes(apj(b"abcd"))
    monkeypatch.setattr(
        "ardupilot_methodic_configurator.backend_flightcontroller.has_stable_bootloader_device_identity",
        bl.has_stable_bootloader_device_identity,
    )

    with pytest.raises(fw.FirmwareConnectionError, match="stable USB"):
        controller.upload_apj_firmware(
            path,
            expected_firmware_sha256=trusted_digest(b"abcd"),
            confirmation_requested=lambda *_args: True,
        )

    assert not connection.master.held_in_bootloader


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

    backend.upload(image, confirmation_requested=lambda *_args: True)

    assert entered
    assert attempts == 2
    assert delays == [0.25]


def test_backend_requires_manual_recovery_after_all_serial_open_retries_fail() -> None:
    """
    Exhausting the bootloader port-open budget is reported as a recovery action.

    GIVEN: The controller entered bootloader mode but its serial port never opens
    WHEN: Every configured serial-open attempt fails
    THEN: The backend reports all attempts and asks the user to power-cycle the controller
    """
    attempts = 0
    delays: list[float] = []

    def enter() -> None:
        pass

    def open_transport(*_args: object) -> bl.BootloaderTransport:
        nonlocal attempts
        attempts += 1
        msg = "bootloader port is still absent"
        raise OSError(msg)

    backend = bl.FlightControllerBootloaderBackend(
        "COM7",
        115200,
        enter_bootloader=enter,
        serial_factory=open_transport,
        open_retries=3,
        retry_delay=0.25,
        sleep=delays.append,
    )

    with pytest.raises(fw.FirmwareBootloaderRecoveryError, match="power-cycle") as error:
        backend.upload(fw.parse_apj(apj(b"abcd")), confirmation_requested=lambda *_args: True)

    assert attempts == 3
    assert delays == [0.25, 0.25]
    assert "bootloader port is still absent" in str(error.value)


def test_backend_honours_cancellation_during_bootloader_discovery() -> None:
    attempts = 0

    def enter() -> None:
        pass

    def open_transport(*_args: object) -> bl.BootloaderTransport:
        nonlocal attempts
        attempts += 1
        msg = "bootloader port is still absent"
        raise OSError(msg)

    backend = bl.FlightControllerBootloaderBackend(
        "COM7",
        115200,
        enter_bootloader=enter,
        serial_factory=open_transport,
        open_retries=3,
        retry_delay=0.25,
        sleep=lambda _delay: None,
    )

    checks = iter([False, False, True])
    with pytest.raises(fw.FirmwareBootloaderRecoveryError, match=r"cancelled.*power-cycle"):
        backend.upload(
            fw.parse_apj(apj(b"abcd")),
            cancellation_requested=lambda: next(checks),
            confirmation_requested=lambda *_args: True,
        )

    assert attempts == 1


def test_backend_default_open_retry_budget_covers_bootloader_enumeration() -> None:
    backend = bl.FlightControllerBootloaderBackend("COM7", 115200)

    assert backend._open_retries == bl.BOOTLOADER_OPEN_RETRIES  # pylint: disable=protected-access
    assert bl.BOOTLOADER_ENUMERATION_TIMEOUT >= 10.0
    assert backend._open_retries * bl.BOOTLOADER_RETRY_DELAY >= bl.BOOTLOADER_ENUMERATION_TIMEOUT  # pylint: disable=protected-access


def test_backend_requires_manual_recovery_when_the_held_bootloader_never_opens() -> None:
    entered = False

    def enter() -> None:
        nonlocal entered
        entered = True

    def open_transport(*_args: object) -> bl.BootloaderTransport:
        msg = "bootloader port has not appeared"
        raise OSError(msg)

    backend = bl.FlightControllerBootloaderBackend(
        "COM7",
        115200,
        enter_bootloader=enter,
        serial_factory=open_transport,
        open_retries=1,
    )

    with pytest.raises(fw.FirmwareBootloaderRecoveryError, match="power-cycle"):
        backend.upload(fw.parse_apj(apj(b"abcd")), confirmation_requested=lambda *_args: True)

    assert entered


def test_backend_retries_bootloader_identification_after_stale_serial_data() -> None:
    """
    A failed identification retry reuses the held bootloader without re-entry.

    GIVEN: The first bootloader connection returns stale synchronization data
    WHEN: The backend closes that connection and retries identification
    THEN: It opens the next transport without requesting bootloader entry again
    """

    class StaleTransport(FakeBootloaderTransport):
        """Replies with stale bytes to the initial synchronization request."""

        def write(self, data: bytes) -> int:
            if data[:1] == bl.GET_SYNC:
                self._reply.extend(b"\x00\x10")
                return len(data)
            return super().write(data)

    stale = StaleTransport()
    working = FakeBootloaderTransport()
    transports = iter([stale, working])
    entries = 0

    def enter() -> None:
        nonlocal entries
        entries += 1

    backend = bl.FlightControllerBootloaderBackend(
        "COM7",
        115200,
        enter_bootloader=enter,
        serial_factory=lambda *_args: next(transports),
        open_retries=2,
        retry_delay=0,
        sleep=lambda _delay: None,
    )

    backend.upload(fw.parse_apj(apj(b"abcd")), confirmation_requested=lambda *_args: True)

    assert stale.closed
    assert working.closed
    assert entries == 1
    assert not stale.rebooted


def test_upload_reports_protocol_stages_and_confirmation_boundary() -> None:
    events: list[tuple[bl.UploadStage, int, int]] = []
    confirmed: list[fw.BootloaderInfo] = []
    transport = FakeBootloaderTransport()

    bl.BootloaderClient(transport).upload(
        fw.parse_apj(apj(b"abcd")),
        confirmation_requested=lambda _image, info: confirmed.append(info) is None,
        progress_callback=lambda stage, done, total: events.append((stage, done, total)),
    )

    assert confirmed == [fw.BootloaderInfo(5, 9, 0, 2048, 1024)]
    assert events == [
        (fw.UploadStage.IDENTIFYING, 0, 1),
        (fw.UploadStage.IDENTIFYING, 1, 1),
        (fw.UploadStage.AWAITING_CONFIRMATION, 0, 1),
        (fw.UploadStage.AWAITING_CONFIRMATION, 1, 1),
        (fw.UploadStage.ERASING, 0, 1),
        (fw.UploadStage.ERASING, 1, 1),
        (fw.UploadStage.PROGRAMMING, 1, 1),
        (fw.UploadStage.VERIFYING, 0, 1),
        (fw.UploadStage.VERIFYING, 1, 1),
        (fw.UploadStage.REBOOTING, 0, 1),
        (fw.UploadStage.REBOOTING, 1, 1),
    ]


def test_verify_failure_reports_the_verifying_stage() -> None:
    class BadCrcTransport(FakeBootloaderTransport):
        """Reports a CRC which cannot match the flashed image."""

        def write(self, data: bytes) -> int:
            if data[:1] == bl.GET_CRC:
                self._reply.extend(struct.pack("<I", 0) + bl.INSYNC + bl.OK)
                return len(data)
            return super().write(data)

    transport = BadCrcTransport()
    with pytest.raises(fw.BootloaderProtocolError, match="CRC") as error:
        bl.BootloaderClient(transport).upload(fw.parse_apj(apj(b"abcd")), confirmation_requested=lambda *_args: True)

    assert error.value.stage == fw.UploadStage.VERIFYING.value
    assert not transport.rebooted


def test_cancellation_is_honoured_before_entering_the_bootloader() -> None:
    transport = FakeBootloaderTransport()

    with pytest.raises(fw.FirmwareUploadCancelledError, match="before entering"):
        bl.BootloaderClient(transport).upload(
            fw.parse_apj(apj(b"abcd")),
            cancellation_requested=lambda: True,
            confirmation_requested=lambda *_args: True,
        )

    assert transport.flash == b""
    assert transport.extf == b""
    assert transport.closed


def test_facade_requires_explicit_confirmation(tmp_path: Path) -> None:
    controller = FlightController(
        connection_manager=_Connection(),  # type: ignore[arg-type]
        params_manager=_Params(),  # type: ignore[arg-type]
        commands_manager=object(),  # type: ignore[arg-type]
        files_manager=object(),  # type: ignore[arg-type]
    )
    path = tmp_path / "firmware.apj"
    path.write_bytes(apj(b"abcd"))

    with pytest.raises(fw.FirmwareConfirmationError, match="explicit confirmation"):
        controller.upload_apj_firmware(path)


def test_facade_recovers_connection_after_declined_confirmation(tmp_path: Path) -> None:
    connection = _Connection()
    transport = FakeBootloaderTransport()
    controller = FlightController(
        connection_manager=connection,  # type: ignore[arg-type]
        params_manager=_Params(),  # type: ignore[arg-type]
        commands_manager=_Commands(),  # type: ignore[arg-type]
        files_manager=object(),  # type: ignore[arg-type]
    )
    path = tmp_path / "firmware.apj"
    path.write_bytes(apj(b"abcd"))

    with pytest.raises(fw.FirmwareUploadCancelledError, match="not confirmed"):
        controller.upload_apj_firmware(
            path,
            expected_firmware_sha256=trusted_digest(b"abcd"),
            serial_factory=lambda *_args: transport,
            confirmation_requested=lambda *_args: False,
        )

    assert transport.rebooted
    assert connection.reconnected


def test_facade_refuses_a_different_bootloader_and_recovers(tmp_path: Path) -> None:
    connection = _Connection()
    connection.info.apj_board_id = "42"
    transport = FakeBootloaderTransport(board_id=9)
    controller = FlightController(
        connection_manager=connection,  # type: ignore[arg-type]
        params_manager=_Params(),  # type: ignore[arg-type]
        commands_manager=_Commands(),  # type: ignore[arg-type]
        files_manager=object(),  # type: ignore[arg-type]
    )
    path = tmp_path / "firmware.apj"
    path.write_bytes(apj(b"abcd"))

    with pytest.raises(fw.FirmwareTargetMismatchError, match="differs from connected"):
        controller.upload_apj_firmware(
            path,
            expected_firmware_sha256=trusted_digest(b"abcd"),
            serial_factory=lambda *_args: transport,
            confirmation_requested=lambda *_args: True,
        )

    assert transport.rebooted
    assert connection.reconnected


def test_facade_recovers_after_confirmation_callback_error(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A GUI callback failure before erase must not strand the board in bootloader mode."""
    connection = _Connection()
    transport = FakeBootloaderTransport()
    controller = FlightController(
        connection_manager=connection,  # type: ignore[arg-type]
        params_manager=_Params(),  # type: ignore[arg-type]
        commands_manager=_Commands(),  # type: ignore[arg-type]
        files_manager=object(),  # type: ignore[arg-type]
    )
    path = tmp_path / "firmware.apj"
    path.write_bytes(apj(b"abcd"))
    monkeypatch.setattr(
        "ardupilot_methodic_configurator.backend_flightcontroller.capture_serial_device_identity",
        lambda _device: None,
    )
    monkeypatch.setattr(
        "ardupilot_methodic_configurator.backend_flightcontroller.has_stable_bootloader_device_identity",
        lambda *_args: True,
    )

    def raise_from_confirmation(*_args: object) -> bool:
        msg = "confirmation UI failed"
        raise RuntimeError(msg)

    with pytest.raises(RuntimeError, match="confirmation UI failed"):
        controller.upload_apj_firmware(
            path,
            expected_firmware_sha256=trusted_digest(b"abcd"),
            serial_factory=lambda *_args: transport,
            confirmation_requested=raise_from_confirmation,
        )

    assert transport.rebooted
    assert connection.reconnected


def test_facade_does_not_attempt_mavlink_reconnect_without_a_bootloader_reboot(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    connection = _Connection()
    controller = FlightController(
        connection_manager=connection,  # type: ignore[arg-type]
        params_manager=_Params(),  # type: ignore[arg-type]
        commands_manager=_Commands(),  # type: ignore[arg-type]
        files_manager=object(),  # type: ignore[arg-type]
    )
    path = tmp_path / "firmware.apj"
    path.write_bytes(apj(b"abcd"))

    def unavailable_upload(
        backend: bl.FlightControllerBootloaderBackend, *_args: object, **_kwargs: object
    ) -> fw.BootloaderInfo:
        assert backend._enter_bootloader is not None
        backend._enter_bootloader()
        msg = "power-cycle the flight controller before reconnecting"
        raise fw.FirmwareBootloaderRecoveryError(msg)

    monkeypatch.setattr(bl.FlightControllerBootloaderBackend, "upload", unavailable_upload)

    with pytest.raises(fw.FirmwareBootloaderRecoveryError, match="power-cycle"):
        controller.upload_apj_firmware(
            path,
            expected_firmware_sha256=trusted_digest(b"abcd"),
            confirmation_requested=lambda *_args: True,
        )

    assert connection.disconnected
    assert not connection.reconnected


def test_facade_does_not_reboot_or_reconnect_after_programming_failure(
    tmp_path: Path,
) -> None:
    """A programming failure must leave recovery to the bootloader safety check."""

    class ProgrammingFailureTransport(FakeBootloaderTransport):
        """Fail the first internal-flash programming command."""

        def write(self, data: bytes) -> int:
            if data[:1] == bl.PROG_MULTI:
                msg = "programming write failed"
                raise OSError(msg)
            return super().write(data)

    connection = _Connection()
    transport = ProgrammingFailureTransport()
    controller = FlightController(
        connection_manager=connection,  # type: ignore[arg-type]
        params_manager=_Params(),  # type: ignore[arg-type]
        commands_manager=_Commands(),  # type: ignore[arg-type]
        files_manager=object(),  # type: ignore[arg-type]
    )
    path = tmp_path / "firmware.apj"
    path.write_bytes(apj(b"abcd"))

    with pytest.raises(fw.BootloaderProtocolError, match="programming write failed"):
        controller.upload_apj_firmware(
            path,
            expected_firmware_sha256=trusted_digest(b"abcd"),
            serial_factory=lambda *_args: transport,
            confirmation_requested=lambda *_args: True,
        )

    assert not transport.rebooted
    assert not connection.reconnected
