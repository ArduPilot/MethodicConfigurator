"""
Flight-controller bootloader adapter for ArduPilot APJ firmware uploads.

All byte-level bootloader protocol and local-file I/O is deliberately kept here;
``data_model_firmware_upload`` contains only parsing and upload policy.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

from __future__ import annotations

import struct
from collections.abc import Callable, Iterator
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path
from time import monotonic
from time import sleep as time_sleep
from typing import Protocol, cast

import serial
import serial.tools.list_ports

from ardupilot_methodic_configurator import _
from ardupilot_methodic_configurator.data_model_firmware_upload import (
    BL_REV_MAX,
    BL_REV_MIN,
    MAX_ENCODED_BLOB_SIZE,
    BootloaderInfo,
    BootloaderProtocolError,
    FirmwareBootloaderRecoveryError,
    FirmwareCompatibilityError,
    FirmwareConfirmationError,
    FirmwareFileError,
    FirmwareImage,
    FirmwareUploadCancelledError,
    FirmwareUploadError,
    UploadStage,
    check_bootloader_matches_connected_board,
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
BOOTLOADER_ENUMERATION_TIMEOUT = 15.0
BOOTLOADER_RETRY_DELAY = 0.5
BOOTLOADER_OPEN_RETRIES = int(BOOTLOADER_ENUMERATION_TIMEOUT / BOOTLOADER_RETRY_DELAY) + 1


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


@dataclass(frozen=True)
class SerialDeviceIdentity:
    """Stable USB attributes which survive a bootloader serial-port rename."""

    location: str = ""
    serial_number: str = ""
    interface: str = ""


DeviceResolver = Callable[[str, SerialDeviceIdentity | None], str]


def capture_serial_device_identity(device: str) -> SerialDeviceIdentity | None:
    """Capture stable USB location/serial metadata for the active serial port."""
    try:
        resolved_device = Path(device).resolve(strict=True)
    except OSError:
        resolved_device = None
    for port in serial.tools.list_ports.comports():
        if port.device != device and (
            resolved_device is None or not _serial_port_matches_device(port.device, resolved_device)
        ):
            continue
        identity = SerialDeviceIdentity(
            location=str(getattr(port, "location", "") or ""),
            serial_number=str(getattr(port, "serial_number", "") or ""),
            interface=str(getattr(port, "interface", "") or ""),
        )
        return identity if identity.location or identity.serial_number else None
    return None


def _serial_port_matches_device(port_device: str, resolved_device: Path) -> bool:
    """Return whether a listed serial device resolves to the selected device."""
    try:
        return Path(port_device).resolve(strict=True) == resolved_device
    except OSError:
        return False


def has_stable_bootloader_device_identity(device: str, identity: SerialDeviceIdentity | None) -> bool:
    """Return whether reopening this serial target can be tied to physical hardware."""
    del device  # The identity must have been captured before the reboot request.
    return identity is not None and bool(identity.location or identity.serial_number)


def _physical_usb_location(location: object) -> str:
    """Return the USB device location without a platform interface suffix."""
    return str(location or "").split(":", 1)[0]


def resolve_bootloader_device(device: str, identity: SerialDeviceIdentity | None = None) -> str:
    """
    Resolve by captured USB identity after re-enumeration.

    With a known USB identity this is fail-closed: a stale port is never opened
    while the board is re-enumerating or the hardware match is ambiguous.
    """
    # A captured USB identity must take precedence over the old device path.
    # During re-enumeration a generic path such as /dev/ttyACM0 may already
    # belong to another controller, whereas the location or serial number
    # identifies the controller that was connected before the reboot.
    if identity is not None:
        if identity.location or identity.serial_number:
            matches = [
                port
                for port in serial.tools.list_ports.comports()
                if all(
                    not expected
                    or (
                        _physical_usb_location(getattr(port, attribute, "")) == _physical_usb_location(expected)
                        if attribute == "location"
                        else getattr(port, attribute, "") == expected
                    )
                    for attribute, expected in (
                        ("location", identity.location),
                        ("serial_number", identity.serial_number),
                    )
                )
            ]
            # Prefer the captured, interface-qualified location when application
            # firmware exposes several CDC ports.  The bootloader commonly exposes
            # only one port with a different suffix, so retain physical matches when
            # there is no exact match.
            if len(matches) > 1 and identity.location:
                exact = [port for port in matches if str(getattr(port, "location", "") or "") == identity.location]
                if len(exact) == 1:
                    matches = exact
            # An application-port interface identifier need not be reproduced by the
            # bootloader.  It can only disambiguate ports from one identified device;
            # it must never eliminate a sole candidate or select between devices.
            # Linux and Windows typically leave this field unset for ArduPilot CDC ports.
            if len(matches) > 1 and identity.interface:
                locations = {_physical_usb_location(getattr(port, "location", "")) for port in matches}
                if len(locations) == 1 and locations != {""}:
                    narrowed = [port for port in matches if str(getattr(port, "interface", "") or "") == identity.interface]
                    if len(narrowed) == 1:
                        matches = narrowed
            if len(matches) == 1:
                return str(matches[0].device)
            msg = _("cannot uniquely locate the bootloader USB device")
            raise OSError(msg)
        msg = _("cannot uniquely locate the bootloader USB device")
        raise OSError(msg)
    return device


def report_progress_safely(progress_callback: ProgressCallback | None, stage: UploadStage, completed: int, total: int) -> None:
    """Invoke presentation code without allowing it to interrupt a flash operation."""
    if progress_callback is None:
        return
    try:
        progress_callback(stage, completed, total)
    except Exception:  # pylint: disable=broad-exception-caught
        return


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


def program_chunks(image: bytes) -> Iterator[bytes]:
    """Yield protocol-sized chunks without copying the whole image into a list."""
    for offset in range(0, len(image), PROG_MULTI_MAX):
        yield image[offset : offset + PROG_MULTI_MAX]


class BootloaderClient:
    """
    Synchronous bootloader session over an injected transport.

    The transport timeout controls every read.  A short read is never accepted as a
    protocol response, preventing a timeout or partial serial transfer from being
    mistaken for a successful flash operation.
    """

    def __init__(
        self,
        transport: BootloaderTransport,
        *,
        timeout: float = 2.0,
        clock: Callable[[], float] = monotonic,
        sleep: Callable[[float], None] = time_sleep,
    ) -> None:
        if timeout <= 0:
            msg = _("bootloader response timeout must be positive")
            raise ValueError(msg)
        self._transport = transport
        self._timeout = timeout
        self._clock = clock
        self._sleep = sleep

    def close(self) -> None:
        # Cleanup must never replace the protocol error which caused the upload
        # to fail.  pyserial reports close failures as OSError/SerialException,
        # while test and third-party transports may use another Exception type.
        with suppress(Exception):
            self._transport.close()

    def abort_before_erase(self, *, deadline: float | None = None, expect_ack: bool = True) -> bool:
        """
        Best-effort reboot for a declined or failed upload before anything was erased.

        Protocol revision two reboots without an acknowledgement.  Later revisions
        must acknowledge the reboot so a failed command is not mistaken for a safe
        abort.
        """
        try:
            if expect_ack:
                self._command(encode_reboot(), deadline=deadline)
            else:
                self._write(encode_reboot())
        except BootloaderProtocolError:
            return False
        return True

    def _reset_input_buffer(self) -> None:
        try:
            self._transport.reset_input_buffer()
        except (OSError, serial.SerialException) as exc:
            msg = _("cannot clear bootloader serial input: {error}").format(error=exc)
            raise BootloaderProtocolError(msg) from exc

    @staticmethod
    def _report(progress_callback: ProgressCallback | None, stage: UploadStage, completed: int, total: int) -> None:
        report_progress_safely(progress_callback, stage, completed, total)

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

    def _read_exact(self, size: int, *, timeout: float | None = None, deadline: float | None = None) -> bytes:
        received = bytearray()
        read_deadline = deadline if deadline is not None else self._clock() + (self._timeout if timeout is None else timeout)
        try:
            while len(received) < size:
                if self._clock() >= read_deadline:
                    msg = _("timeout waiting for {expected} bootloader bytes; received {actual}").format(
                        expected=size, actual=len(received)
                    )
                    raise BootloaderProtocolError(msg)
                chunk = self._transport.read(size - len(received))
                if not chunk:
                    remaining = read_deadline - self._clock()
                    if remaining > 0:
                        # A non-blocking transport can return empty reads in a tight
                        # loop. Yield briefly so a malformed transport cannot consume
                        # an entire CPU while the response deadline is pending.
                        self._sleep(min(0.01, remaining))
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

    def _sync(self, *, timeout: float | None = None, deadline: float | None = None) -> None:
        decode_sync(self._read_exact(2, timeout=timeout, deadline=deadline))

    def _command(self, request: bytes, reply_size: int = 0, *, deadline: float | None = None) -> bytes:
        self._write(request)
        reply = self._read_exact(reply_size, deadline=deadline) if reply_size else b""
        self._sync(deadline=deadline)
        return reply

    def identify(self, *, deadline: float | None = None) -> BootloaderInfo:
        self._reset_input_buffer()
        self._command(encode_get_sync(), deadline=deadline)
        revision = decode_uint32(self._command(encode_get_device(INFO_BL_REV), 4, deadline=deadline))
        if not BL_REV_MIN <= revision <= BL_REV_MAX:
            msg = _("unsupported bootloader protocol revision {revision}").format(revision=revision)
            raise BootloaderProtocolError(msg)

        # Old bootloaders can reject this newer optional query.  Resynchronize and
        # conservatively report no external flash in that case.
        try:
            extf_size = decode_uint32(self._command(encode_get_device(INFO_EXTF_SIZE), 4, deadline=deadline))
        except BootloaderProtocolError:
            extf_size = 0
            self._reset_input_buffer()
            self._command(encode_get_sync(), deadline=deadline)
        return BootloaderInfo(
            protocol_revision=revision,
            board_id=decode_uint32(self._command(encode_get_device(INFO_BOARD_ID), 4, deadline=deadline)),
            board_revision=decode_uint32(self._command(encode_get_device(INFO_BOARD_REV), 4, deadline=deadline)),
            flash_size=decode_uint32(self._command(encode_get_device(INFO_FLASH_SIZE), 4, deadline=deadline)),
            extf_size=extf_size,
        )

    def _erase_external(self, size: int) -> None:
        self._write(encode_extf_erase(size))
        self._sync()
        # The bootloader emits percentage bytes until it is almost done, then the
        # final INSYNC/OK acknowledgement.  Values below 90 are progress reports.
        deadline = self._clock() + ERASE_TIMEOUT
        last_pct = 0
        while True:
            first = self._read_exact(1, deadline=deadline)
            if last_pct >= 90 and first == INSYNC:
                decode_sync(first + self._read_exact(1, deadline=deadline))
                return
            progress = first[0]
            if progress > 100:
                msg = _("invalid external-flash erase progress {progress}").format(progress=progress)
                raise BootloaderProtocolError(msg)
            if progress < last_pct:
                msg = _("external-flash erase progress regressed from {previous} to {progress}").format(
                    previous=last_pct, progress=progress
                )
                raise BootloaderProtocolError(msg)
            if progress > last_pct:
                last_pct = progress
                deadline = self._clock() + ERASE_TIMEOUT

    def _verify_v2(self, image: FirmwareImage) -> None:
        self._command(encode_chip_verify())
        for offset in range(0, len(image.image), READ_MULTI_MAX):
            expected = image.image[offset : offset + READ_MULTI_MAX]
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

    def upload(  # noqa: PLR0915 # pylint: disable=too-many-arguments,too-many-branches,too-many-statements,too-many-locals
        self,
        image: FirmwareImage,
        *,
        full_erase: bool = False,
        cancellation_requested: CancellationRequested | None = None,
        confirmation_requested: ConfirmationRequested | None = None,
        progress_callback: ProgressCallback | None = None,
        bootloader: BootloaderInfo | None = None,
        connected_board_id: int | None = None,
    ) -> BootloaderInfo:
        """
        Identify, validate, program all image regions, verify, and reboot.

        The transport is closed on success and on every error path.  Revision two
        uses CHIP_VERIFY plus READ_MULTI and intentionally receives no reboot ACK;
        revision three and later use CRC and require that ACK.
        """
        stage = UploadStage.AWAITING_CONFIRMATION
        info = bootloader
        try:
            if confirmation_requested is None:
                msg = _("firmware upload requires explicit confirmation")
                raise FirmwareConfirmationError(msg)
            if cancellation_requested is not None and cancellation_requested():
                msg = _("firmware upload cancelled before entering the bootloader")
                raise FirmwareUploadCancelledError(msg, stage=stage.value)
            stage = UploadStage.IDENTIFYING
            self._report(progress_callback, stage, 0, 1)
            info = info or self.identify()
            self._report(progress_callback, stage, 1, 1)
            check_bootloader_matches_connected_board(info, connected_board_id)
            check_compatibility(image, info)
            if full_erase:
                # AP_Bootloader only implements CHIP_FULL_ERASE on STM32F7/H7.
                # This client does not yet use the bootloader's MCU-identification
                # responses to gate that capability, so refuse rather than send a
                # command that an unsupported target may ignore until timeout.
                msg = _("full firmware erase is unavailable because support cannot yet be determined safely")
                raise FirmwareCompatibilityError(msg)
            stage = UploadStage.AWAITING_CONFIRMATION
            self._report(progress_callback, stage, 0, 1)
            if not confirmation_requested(image, info):
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
                chunk_count = (len(image.extf_image) + PROG_MULTI_MAX - 1) // PROG_MULTI_MAX
                for index, chunk in enumerate(program_chunks(image.extf_image), start=1):
                    self._command(encode_extf_prog_multi(chunk))
                    self._report(progress_callback, stage, index, chunk_count)
                stage = UploadStage.VERIFYING
                self._report(progress_callback, stage, 0, 1)
                self._verify_external(image)
                self._report(progress_callback, stage, 1, 1)
            if image.metadata.image_size:
                stage = UploadStage.ERASING
                self._report(progress_callback, stage, 0, 1)
                self._write(encode_chip_erase(full=full_erase))
                self._sync(timeout=ERASE_TIMEOUT)
                self._report(progress_callback, stage, 1, 1)
                stage = UploadStage.PROGRAMMING
                chunk_count = (len(image.image) + PROG_MULTI_MAX - 1) // PROG_MULTI_MAX
                for index, chunk in enumerate(program_chunks(image.image), start=1):
                    self._command(encode_prog_multi(chunk))
                    self._report(progress_callback, stage, index, chunk_count)
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
        except FirmwareUploadError as exc:
            if stage in {UploadStage.IDENTIFYING, UploadStage.AWAITING_CONFIRMATION} and not self.abort_before_erase(
                expect_ack=info is None or info.protocol_revision != 2
            ):
                msg = _("cannot reboot the held bootloader; power-cycle the flight controller before reconnecting")
                raise FirmwareBootloaderRecoveryError(msg) from exc
            if stage in {UploadStage.IDENTIFYING, UploadStage.AWAITING_CONFIRMATION}:
                exc.bootloader_rebooted = True  # type: ignore[attr-defined]
            if isinstance(exc, BootloaderProtocolError):
                exc.stage = stage.value
            if stage in {UploadStage.ERASING, UploadStage.PROGRAMMING, UploadStage.VERIFYING, UploadStage.REBOOTING}:
                recovery_message = _(
                    "firmware upload failed during {stage}; the firmware flash may be incomplete. "
                    "power-cycle the flight controller before reconnecting"
                ).format(stage=stage.value)
                exc.args = (f"{exc.args[0]}; {recovery_message}", *exc.args[1:])
            raise
        except Exception as exc:
            if stage in {UploadStage.IDENTIFYING, UploadStage.AWAITING_CONFIRMATION} and not self.abort_before_erase(
                expect_ack=info is None or info.protocol_revision != 2
            ):
                msg = _("cannot reboot the held bootloader; power-cycle the flight controller before reconnecting")
                raise FirmwareBootloaderRecoveryError(msg) from exc
            if stage in {UploadStage.IDENTIFYING, UploadStage.AWAITING_CONFIRMATION}:
                exc.bootloader_rebooted = True  # type: ignore[attr-defined]
            if stage in {UploadStage.ERASING, UploadStage.PROGRAMMING, UploadStage.VERIFYING, UploadStage.REBOOTING}:
                recovery_message = _(
                    "firmware upload failed during {stage}; the firmware flash may be incomplete. "
                    "power-cycle the flight controller before reconnecting"
                ).format(stage=stage.value)
                exc.args = (f"{exc.args[0]}; {recovery_message}", *exc.args[1:])
            raise
        finally:
            self.close()


def open_serial_transport(device: str, baudrate: int, timeout: float) -> BootloaderTransport:
    """Open the real serial transport with explicit read/write timeouts."""
    return cast("BootloaderTransport", serial.Serial(device, baudrate, timeout=timeout, write_timeout=timeout, exclusive=True))


class FlightControllerBootloaderBackend:  # pylint:disable=too-many-instance-attributes
    """Production-facing adapter with injectable bootloader entry and serial transport."""

    def __init__(  # noqa: PLR0913 # pylint: disable=too-many-arguments
        self,
        device: str,
        baudrate: int,
        *,
        timeout: float = 2.0,
        enter_bootloader: BootloaderEntry | None = None,
        serial_factory: SerialFactory = open_serial_transport,
        device_resolver: DeviceResolver = resolve_bootloader_device,
        device_identity: SerialDeviceIdentity | None = None,
        open_retries: int = BOOTLOADER_OPEN_RETRIES,
        retry_delay: float = BOOTLOADER_RETRY_DELAY,
        sleep: Callable[[float], None] = time_sleep,
        clock: Callable[[], float] = monotonic,
    ) -> None:
        if timeout <= 0:
            msg = _("bootloader response timeout must be positive")
            raise ValueError(msg)
        self._device = device
        self._device_resolver = device_resolver
        self._device_identity = device_identity
        self._baudrate = baudrate
        self._timeout = timeout
        self._enter_bootloader = enter_bootloader
        self._serial_factory = serial_factory
        self._open_retries = open_retries
        self._retry_delay = retry_delay
        self._sleep = sleep
        self._clock = clock

    def inspect_firmware(self, path: Path) -> FirmwareImage:
        return load_apj(path)

    def upload(  # pylint: disable=too-many-arguments
        self,
        image: FirmwareImage,
        *,
        full_erase: bool = False,
        cancellation_requested: CancellationRequested | None = None,
        confirmation_requested: ConfirmationRequested | None = None,
        progress_callback: ProgressCallback | None = None,
        connected_board_id: int | None = None,
    ) -> BootloaderInfo:
        if confirmation_requested is None:
            msg = _("firmware upload requires explicit confirmation")
            raise FirmwareConfirmationError(msg)
        if cancellation_requested is not None and cancellation_requested():
            msg = _("firmware upload cancelled before entering the bootloader")
            raise FirmwareUploadCancelledError(msg, stage=UploadStage.ENTERING_BOOTLOADER.value)
        if self._enter_bootloader is not None:
            self._enter_bootloader()
        client, info = self._wait_for_bootloader(cancellation_requested)
        return client.upload(
            image,
            full_erase=full_erase,
            cancellation_requested=cancellation_requested,
            confirmation_requested=confirmation_requested,
            progress_callback=progress_callback,
            bootloader=info,
            connected_board_id=connected_board_id,
        )

    def _wait_for_bootloader(
        self, cancellation_requested: CancellationRequested | None = None
    ) -> tuple[BootloaderClient, BootloaderInfo]:
        if self._open_retries < 1:
            msg = _("bootloader open retries must be at least one")
            raise ValueError(msg)
        last_error: FirmwareUploadError | OSError | serial.SerialException | None = None
        deadline = self._clock() + BOOTLOADER_ENUMERATION_TIMEOUT
        for attempt in range(self._open_retries):
            if cancellation_requested is not None and cancellation_requested():
                msg = _(
                    "firmware upload was cancelled while waiting for the bootloader; "
                    "power-cycle the flight controller before reconnecting"
                )
                raise FirmwareBootloaderRecoveryError(msg) from last_error
            remaining = deadline - self._clock()
            if remaining <= 0:
                break
            attempt_timeout = min(self._timeout, remaining)
            transport, open_error = self._try_open_transport(attempt_timeout)
            if transport is not None:
                client = BootloaderClient(
                    transport,
                    timeout=attempt_timeout,
                    clock=self._clock,
                    sleep=self._sleep,
                )
                try:
                    return client, client.identify(deadline=deadline)
                except BootloaderProtocolError as exc:
                    last_error = exc
                    retry_would_exhaust_budget = self._clock() + self._retry_delay >= deadline
                    if attempt + 1 == self._open_retries or retry_would_exhaust_budget:
                        if not client.abort_before_erase(deadline=deadline):
                            client.close()
                            msg = _("cannot reboot the held bootloader; power-cycle the flight controller before reconnecting")
                            raise FirmwareBootloaderRecoveryError(msg) from exc
                        exc.bootloader_rebooted = True  # type: ignore[attr-defined]
                        exc.stage = UploadStage.IDENTIFYING.value
                    client.close()
            else:
                last_error = open_error
            if attempt + 1 < self._open_retries:
                remaining = deadline - self._clock()
                if remaining > 0:
                    self._sleep(min(self._retry_delay, remaining))
        if isinstance(last_error, BootloaderProtocolError):
            raise last_error
        msg = _(
            "cannot open the held bootloader on serial port {device}: {error}; "
            "power-cycle the flight controller before reconnecting"
        ).format(device=self._device, error=last_error)
        raise FirmwareBootloaderRecoveryError(msg) from last_error

    def _try_open_transport(
        self, timeout: float | None = None
    ) -> tuple[BootloaderTransport | None, OSError | serial.SerialException | None]:
        try:
            device = self._device_resolver(self._device, self._device_identity)
            return self._serial_factory(device, self._baudrate, self._timeout if timeout is None else timeout), None
        except (OSError, serial.SerialException) as exc:
            return None, exc
