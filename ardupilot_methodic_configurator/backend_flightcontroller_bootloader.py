#!/usr/bin/env python3

"""
Flight-controller bootloader adapter for ArduPilot APJ firmware uploads.

All byte-level bootloader protocol and local-file I/O is deliberately kept here;
``data_model_firmware_upload`` contains only parsing and upload policy.
"""

from __future__ import annotations

import struct
from collections.abc import Callable
from pathlib import Path
from sys import platform as sys_platform
from time import monotonic
from time import sleep as time_sleep
from typing import Protocol, cast

import serial

from ardupilot_methodic_configurator import _
from ardupilot_methodic_configurator.data_model_firmware_upload import (
    BL_REV_MAX,
    BL_REV_MIN,
    MAX_ENCODED_BLOB_SIZE,
    BootloaderInfo,
    BootloaderProtocolError,
    FirmwareConfirmationError,
    FirmwareFileError,
    FirmwareImage,
    FirmwareUploadCancelledError,
    FirmwareUploadError,
    UploadStage,
    check_compatibility,
    parse_apj,
)

# ArduPilot/PX4 bootloader protocol bytes, from Tools/scripts/uploader.py.
INSYNC = b"\x12"
EOC = b"\x20"
OK = b"\x10"
FAILED = b"\x11"
INVALID = b"\x13"
BAD_SILICON_REV = b"\x14"

GET_SYNC = b"\x21"
GET_DEVICE = b"\x22"
CHIP_ERASE = b"\x23"
CHIP_VERIFY = b"\x24"
PROG_MULTI = b"\x27"
READ_MULTI = b"\x28"
GET_CRC = b"\x29"
REBOOT = b"\x30"
EXTF_ERASE = b"\x34"
EXTF_PROG_MULTI = b"\x35"
EXTF_GET_CRC = b"\x37"
CHIP_FULL_ERASE = b"\x40"

INFO_BL_REV = b"\x01"
INFO_BOARD_ID = b"\x02"
INFO_BOARD_REV = b"\x03"
INFO_FLASH_SIZE = b"\x04"
INFO_EXTF_SIZE = b"\x06"

PROG_MULTI_MAX = 252  # protocol maximum is 255; writes must be word aligned
READ_MULTI_MAX = 252
ERASE_TIMEOUT = 20.0
EXTF_CRC_TIMEOUT = 10.0
MAX_APJ_DESCRIPTOR_SIZE = (MAX_ENCODED_BLOB_SIZE * 2) + (1024 * 1024)


class BootloaderTransport(Protocol):
    """Minimal blocking byte stream required by the bootloader protocol."""

    def write(self, data: bytes) -> int: ...

    def read(self, size: int = 1) -> bytes: ...

    def flush(self) -> None: ...

    def reset_input_buffer(self) -> None: ...

    def close(self) -> None: ...


ProgressCallback = Callable[[UploadStage, int, int], None]
ConfirmationRequested = Callable[[FirmwareImage, BootloaderInfo], bool]
CancellationRequested = Callable[[], bool]
SerialFactory = Callable[[str, int, float], BootloaderTransport]
BootloaderEntry = Callable[[], None]
DeviceResolver = Callable[[str], str]


def resolve_bootloader_device(device: str) -> str:
    """Use Linux's stable USB by-path link when the current port can be mapped to it."""
    if not sys_platform.startswith("linux"):
        return device
    try:
        current = Path(device).resolve(strict=True)
        for by_path in Path("/dev/serial/by-path").iterdir():
            if by_path.resolve(strict=True) == current:
                return str(by_path)
    except OSError:
        pass
    return device


def load_apj(path: Path) -> FirmwareImage:
    """Read an APJ file, then pass its contents to the pure domain parser."""
    if path.suffix.lower() != ".apj":
        msg = _("unsupported firmware format {suffix}, only .apj is supported").format(suffix=path.suffix)
        raise FirmwareFileError(msg)
    try:
        if path.stat().st_size > MAX_APJ_DESCRIPTOR_SIZE:
            msg = _("APJ descriptor exceeds {limit} bytes").format(limit=MAX_APJ_DESCRIPTOR_SIZE)
            raise FirmwareFileError(msg)
        with path.open("rb") as descriptor:
            contents = descriptor.read(MAX_APJ_DESCRIPTOR_SIZE + 1)
        if len(contents) > MAX_APJ_DESCRIPTOR_SIZE:
            msg = _("APJ descriptor exceeds {limit} bytes").format(limit=MAX_APJ_DESCRIPTOR_SIZE)
            raise FirmwareFileError(msg)
        return parse_apj(contents, path=path)
    except OSError as exc:
        msg = _("cannot read APJ descriptor: {error}").format(error=exc)
        raise FirmwareFileError(msg) from exc


def encode_get_sync() -> bytes:
    return GET_SYNC + EOC


def encode_get_device(param: bytes) -> bytes:
    return GET_DEVICE + param + EOC


def encode_chip_erase(*, full: bool = False) -> bytes:
    return (CHIP_FULL_ERASE if full else CHIP_ERASE) + EOC


def encode_chip_verify() -> bytes:
    return CHIP_VERIFY + EOC


def _encode_multi(command: bytes, chunk: bytes) -> bytes:
    if not 0 < len(chunk) <= PROG_MULTI_MAX or len(chunk) % 4:
        msg = _("PROG_MULTI chunk must be 4..{limit} bytes and a multiple of 4, got {size}").format(
            limit=PROG_MULTI_MAX, size=len(chunk)
        )
        raise ValueError(msg)
    return command + bytes([len(chunk)]) + chunk + EOC


def encode_prog_multi(chunk: bytes) -> bytes:
    return _encode_multi(PROG_MULTI, chunk)


def encode_extf_prog_multi(chunk: bytes) -> bytes:
    return _encode_multi(EXTF_PROG_MULTI, chunk)


def encode_read_multi(length: int) -> bytes:
    if not 0 < length <= READ_MULTI_MAX:
        msg = _("READ_MULTI length must be 1..{limit}, got {length}").format(limit=READ_MULTI_MAX, length=length)
        raise ValueError(msg)
    return READ_MULTI + bytes([length]) + EOC


def _encode_external_size(command: bytes, size: int) -> bytes:
    if not 0 < size <= 0xFFFFFFFF:
        msg = _("external flash size must be 1..4294967295 bytes, got {size}").format(size=size)
        raise ValueError(msg)
    return command + struct.pack("<I", size) + EOC


def encode_extf_erase(size: int) -> bytes:
    return _encode_external_size(EXTF_ERASE, size)


def encode_extf_get_crc(size: int) -> bytes:
    return _encode_external_size(EXTF_GET_CRC, size)


def encode_get_crc() -> bytes:
    return GET_CRC + EOC


def encode_reboot() -> bytes:
    return REBOOT + EOC


def decode_sync(reply: bytes) -> None:
    """Validate an INSYNC/status reply."""
    if len(reply) != 2:
        msg = _("short reply, expected INSYNC and status, got {reply}").format(reply=reply)
        raise BootloaderProtocolError(msg)
    if reply[0:1] != INSYNC:
        msg = _("expected INSYNC, got {byte}").format(byte=reply[0:1])
        raise BootloaderProtocolError(msg)
    status = reply[1:2]
    if status == OK:
        return
    messages = {
        INVALID: _("bootloader reports INVALID OPERATION"),
        FAILED: _("bootloader reports OPERATION FAILED"),
        BAD_SILICON_REV: _("programming not supported for this silicon revision"),
    }
    msg = messages.get(status) or _("unexpected status {status} instead of OK").format(status=status)
    raise BootloaderProtocolError(msg)


def decode_uint32(reply: bytes) -> int:
    if len(reply) != 4:
        msg = _("short reply, expected 4 bytes, got {size}").format(size=len(reply))
        raise BootloaderProtocolError(msg)
    return int(struct.unpack("<I", reply)[0])


def program_chunks(image: bytes) -> list[bytes]:
    return [image[offset : offset + PROG_MULTI_MAX] for offset in range(0, len(image), PROG_MULTI_MAX)]


class BootloaderClient:
    """
    Synchronous bootloader session over an injected transport.

    The transport timeout controls every read.  A short read is never accepted as a
    protocol response, preventing a timeout or partial serial transfer from being
    mistaken for a successful flash operation.
    """

    def __init__(self, transport: BootloaderTransport, *, clock: Callable[[], float] = monotonic) -> None:
        self._transport = transport
        self._clock = clock

    def close(self) -> None:
        self._transport.close()

    def _reset_input_buffer(self) -> None:
        try:
            self._transport.reset_input_buffer()
        except (OSError, serial.SerialException) as exc:
            msg = _("cannot clear bootloader serial input: {error}").format(error=exc)
            raise BootloaderProtocolError(msg) from exc

    @staticmethod
    def _report(progress_callback: ProgressCallback | None, stage: UploadStage, completed: int, total: int) -> None:
        if progress_callback is None:
            return
        try:
            progress_callback(stage, completed, total)
        except Exception:
            # Progress presentation must not interrupt an irreversible write.
            return

    def _write(self, request: bytes) -> None:
        try:
            written = self._transport.write(request)
            self._transport.flush()
        except (OSError, serial.SerialException) as exc:
            msg = _("bootloader transport write failed: {error}").format(error=exc)
            raise BootloaderProtocolError(msg) from exc
        if written != len(request):
            msg = _("bootloader transport wrote {written} of {expected} bytes").format(written=written, expected=len(request))
            raise BootloaderProtocolError(msg)

    def _read_exact(self, size: int, *, timeout: float | None = None) -> bytes:
        received = bytearray()
        deadline = self._clock() + timeout if timeout is not None else None
        try:
            while len(received) < size:
                chunk = self._transport.read(size - len(received))
                if not chunk:
                    if deadline is not None and self._clock() < deadline:
                        continue
                    msg = _("timeout waiting for {expected} bootloader bytes; received {actual}").format(
                        expected=size, actual=len(received)
                    )
                    raise BootloaderProtocolError(msg)
                received.extend(chunk)
        except (OSError, serial.SerialException) as exc:
            msg = _("bootloader transport read failed: {error}").format(error=exc)
            raise BootloaderProtocolError(msg) from exc
        return bytes(received)

    def _sync(self, *, timeout: float | None = None) -> None:
        decode_sync(self._read_exact(2, timeout=timeout))

    def _command(self, request: bytes, reply_size: int = 0) -> bytes:
        self._write(request)
        reply = self._read_exact(reply_size) if reply_size else b""
        self._sync()
        return reply

    def identify(self) -> BootloaderInfo:
        self._reset_input_buffer()
        self._command(encode_get_sync())
        revision = decode_uint32(self._command(encode_get_device(INFO_BL_REV), 4))
        if not BL_REV_MIN <= revision <= BL_REV_MAX:
            msg = _("unsupported bootloader protocol revision {revision}").format(revision=revision)
            raise BootloaderProtocolError(msg)

        # Old bootloaders can reject this newer optional query.  Resynchronize and
        # conservatively report no external flash in that case.
        try:
            extf_size = decode_uint32(self._command(encode_get_device(INFO_EXTF_SIZE), 4))
        except BootloaderProtocolError:
            extf_size = 0
            self._command(encode_get_sync())
        return BootloaderInfo(
            protocol_revision=revision,
            board_id=decode_uint32(self._command(encode_get_device(INFO_BOARD_ID), 4)),
            board_revision=decode_uint32(self._command(encode_get_device(INFO_BOARD_REV), 4)),
            flash_size=decode_uint32(self._command(encode_get_device(INFO_FLASH_SIZE), 4)),
            extf_size=extf_size,
        )

    def _erase_external(self, size: int) -> None:
        self._write(encode_extf_erase(size))
        self._sync()
        # The bootloader emits percentage bytes until it is almost done, then the
        # final INSYNC/OK acknowledgement.  Values below 90 are progress reports.
        deadline = self._clock() + ERASE_TIMEOUT
        while True:
            first = self._read_exact(1, timeout=max(0.0, deadline - self._clock()))
            if first == INSYNC:
                decode_sync(first + self._read_exact(1, timeout=max(0.0, deadline - self._clock())))
                return
            if first[0] > 100:
                msg = _("invalid external-flash erase progress {progress}").format(progress=first[0])
                raise BootloaderProtocolError(msg)

    def _verify_v2(self, image: FirmwareImage) -> None:
        self._command(encode_chip_verify())
        for expected in program_chunks(image.image):
            programmed = self._command(encode_read_multi(len(expected)), len(expected))
            if programmed != expected:
                msg = _("firmware read-back verification failed")
                raise BootloaderProtocolError(msg)

    def _verify_v3(self, image: FirmwareImage, flash_size: int) -> None:
        actual = decode_uint32(self._command(encode_get_crc(), 4))
        if actual != image.crc(flash_size):
            msg = _("firmware CRC verification failed")
            raise BootloaderProtocolError(msg)

    def _verify_external(self, image: FirmwareImage) -> None:
        self._write(encode_extf_get_crc(image.metadata.extf_image_size))
        actual = decode_uint32(self._read_exact(4, timeout=EXTF_CRC_TIMEOUT))
        self._sync(timeout=EXTF_CRC_TIMEOUT)
        if actual != image.extf_crc():
            msg = _("external firmware CRC verification failed")
            raise BootloaderProtocolError(msg)

    def upload(  # noqa: PLR0915
        self,
        image: FirmwareImage,
        *,
        force: bool = False,
        full_erase: bool = False,
        cancellation_requested: CancellationRequested | None = None,
        confirmation_requested: ConfirmationRequested | None = None,
        progress_callback: ProgressCallback | None = None,
        bootloader: BootloaderInfo | None = None,
    ) -> BootloaderInfo:
        """
        Identify, validate, program all image regions, verify, and reboot.

        The transport is closed on success and on every error path.  Revision two
        uses CHIP_VERIFY plus READ_MULTI and intentionally receives no reboot ACK;
        revision three and later use CRC and require that ACK.
        """
        stage = UploadStage.IDENTIFYING
        try:
            self._report(progress_callback, stage, 0, 1)
            info = bootloader or self.identify()
            self._report(progress_callback, stage, 1, 1)
            check_compatibility(image, info, force=force)
            stage = UploadStage.AWAITING_CONFIRMATION
            self._report(progress_callback, stage, 0, 1)
            if confirmation_requested is not None and not confirmation_requested(image, info):
                msg = _("firmware upload was not confirmed")
                raise FirmwareUploadCancelledError(msg, stage=stage.value)
            self._report(progress_callback, stage, 1, 1)
            if cancellation_requested is not None and cancellation_requested():
                msg = _("firmware upload cancelled before erase")
                raise FirmwareUploadCancelledError(msg, stage=stage.value)
            if image.metadata.extf_image_size:
                stage = UploadStage.ERASING
                self._report(progress_callback, stage, 0, 1)
                self._erase_external(image.metadata.extf_image_size)
                self._report(progress_callback, stage, 1, 1)
                stage = UploadStage.PROGRAMMING
                chunks = program_chunks(image.extf_image)
                for index, chunk in enumerate(chunks, start=1):
                    self._command(encode_extf_prog_multi(chunk))
                    self._report(progress_callback, stage, index, len(chunks))
                stage = UploadStage.VERIFYING
                self._report(progress_callback, stage, 0, 1)
                self._verify_external(image)
                self._report(progress_callback, stage, 1, 1)
            stage = UploadStage.ERASING
            self._report(progress_callback, stage, 0, 1)
            self._write(encode_chip_erase(full=full_erase))
            self._sync(timeout=ERASE_TIMEOUT)
            self._report(progress_callback, stage, 1, 1)
            stage = UploadStage.PROGRAMMING
            chunks = program_chunks(image.image)
            for index, chunk in enumerate(chunks, start=1):
                self._command(encode_prog_multi(chunk))
                self._report(progress_callback, stage, index, len(chunks))
            stage = UploadStage.VERIFYING
            self._report(progress_callback, stage, 0, 1)
            if info.protocol_revision == 2:
                self._verify_v2(image)
            else:
                self._verify_v3(image, info.flash_size)
            self._report(progress_callback, stage, 1, 1)
            stage = UploadStage.REBOOTING
            self._report(progress_callback, stage, 0, 1)
            if info.protocol_revision == 2:
                self._write(encode_reboot())
            else:
                self._command(encode_reboot())
            self._report(progress_callback, stage, 1, 1)
            return info
        except BootloaderProtocolError as exc:
            exc.stage = stage.value
            raise
        finally:
            self.close()


def open_serial_transport(device: str, baudrate: int, timeout: float) -> BootloaderTransport:
    """Open the real serial transport with explicit read/write timeouts."""
    return cast("BootloaderTransport", serial.Serial(device, baudrate, timeout=timeout, write_timeout=timeout, exclusive=True))


class FlightControllerBootloaderBackend:
    """Production-facing adapter with injectable bootloader entry and serial transport."""

    def __init__(
        self,
        device: str,
        baudrate: int,
        *,
        timeout: float = 2.0,
        enter_bootloader: BootloaderEntry | None = None,
        serial_factory: SerialFactory = open_serial_transport,
        device_resolver: DeviceResolver = resolve_bootloader_device,
        open_retries: int = 5,
        retry_delay: float = 0.5,
        sleep: Callable[[float], None] = time_sleep,
    ) -> None:
        self._device = device_resolver(device)
        self._baudrate = baudrate
        self._timeout = timeout
        self._enter_bootloader = enter_bootloader
        self._serial_factory = serial_factory
        self._open_retries = open_retries
        self._retry_delay = retry_delay
        self._sleep = sleep

    def inspect_firmware(self, path: Path) -> FirmwareImage:
        return load_apj(path)

    def upload(
        self,
        image: FirmwareImage,
        *,
        force: bool = False,
        full_erase: bool = False,
        cancellation_requested: CancellationRequested | None = None,
        confirmation_requested: ConfirmationRequested | None = None,
        progress_callback: ProgressCallback | None = None,
    ) -> BootloaderInfo:
        if confirmation_requested is None:
            msg = _("firmware upload requires explicit confirmation")
            raise FirmwareConfirmationError(msg)
        if self._enter_bootloader is not None:
            self._enter_bootloader()
        client, info = self._wait_for_bootloader()
        return client.upload(
            image,
            force=force,
            full_erase=full_erase,
            cancellation_requested=cancellation_requested,
            confirmation_requested=confirmation_requested,
            progress_callback=progress_callback,
            bootloader=info,
        )

    def _wait_for_bootloader(self) -> tuple[BootloaderClient, BootloaderInfo]:
        if self._open_retries < 1:
            msg = _("bootloader open retries must be at least one")
            raise ValueError(msg)
        last_error: FirmwareUploadError | OSError | serial.SerialException | None = None
        for attempt in range(self._open_retries):
            transport, open_error = self._try_open_transport()
            if transport is not None:
                client = BootloaderClient(transport)
                try:
                    return client, client.identify()
                except BootloaderProtocolError as exc:
                    last_error = exc
                    client.close()
            else:
                last_error = open_error
            if attempt + 1 < self._open_retries:
                self._sleep(self._retry_delay)
        msg = _("cannot synchronize with bootloader on serial port {device}: {error}").format(
            device=self._device, error=last_error
        )
        raise BootloaderProtocolError(msg, stage=UploadStage.ENTERING_BOOTLOADER.value) from last_error

    def _try_open_transport(self) -> tuple[BootloaderTransport | None, OSError | serial.SerialException | None]:
        try:
            return self._serial_factory(self._device, self._baudrate, self._timeout), None
        except (OSError, serial.SerialException) as exc:
            return None, exc
