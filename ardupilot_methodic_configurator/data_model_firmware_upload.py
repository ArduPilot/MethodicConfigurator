#!/usr/bin/env python3

"""
Firmware upload domain model: APJ image decoding, bootloader protocol codec and validation rules.

No serial, MAVLink, Tkinter or dialogs live here. The backend adapter performs the I/O and
feeds bytes in and out of the pure functions defined in this module.

The protocol constants and the image normalisation mirror ArduPilot Tools/scripts/uploader.py so the
backend can follow the same erase/program/verify sequence as the reference uploader.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import base64
import json
import struct
import zlib
from binascii import crc32
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from ardupilot_methodic_configurator import _

# Bootloader protocol bytes, from ArduPilot Tools/scripts/uploader.py
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
CHIP_FULL_ERASE = b"\x40"

INFO_BL_REV = b"\x01"
INFO_BOARD_ID = b"\x02"
INFO_BOARD_REV = b"\x03"
INFO_FLASH_SIZE = b"\x04"
INFO_EXTF_SIZE = b"\x06"

BL_REV_MIN = 2
BL_REV_MAX = 5
PROG_MULTI_MAX = 252  # protocol max is 255, must be a multiple of 4
READ_MULTI_MAX = 252

# Sanity bound on decompressed image size, well above any current flight controller flash
MAX_IMAGE_SIZE = 64 * 1024 * 1024


class FirmwareUploadError(Exception):
    """Base class for typed firmware upload errors, `stage` names where it happened."""

    stage = "unknown"


class FirmwareFileError(FirmwareUploadError):
    """The firmware file is unreadable, malformed or not a supported format."""

    stage = "inspecting"


class FirmwareCompatibilityError(FirmwareUploadError):
    """The image does not match the connected board or does not fit in flash."""

    stage = "identifying"


class BootloaderProtocolError(FirmwareUploadError):
    """The bootloader answered something unexpected, or a protocol revision is unsupported."""

    stage = "identifying"


@dataclass(frozen=True)
class FirmwareImageMetadata:
    """What the user sees before confirming an upload, read from the APJ descriptor and never from the filename."""

    path: Path
    board_id: int
    image_size: int
    extf_image_size: int
    firmware_version: str
    git_identity: str
    board_revision: int | None = None


@dataclass(frozen=True)
class FirmwareImage:
    """Decoded, 4-byte padded image ready for the bootloader."""

    metadata: FirmwareImageMetadata
    image: bytes
    extf_image: bytes = b""

    def crc(self, flash_size: int) -> int:
        """CRC32 of the image padded with 0xFF up to flash_size, as computed by the bootloader GET_CRC."""
        state = crc32(self.image, 0)
        for _unused in range(len(self.image), flash_size - 1, 4):
            state = crc32(b"\xff\xff\xff\xff", state)
        return state


@dataclass(frozen=True)
class BootloaderInfo:
    """Answers to GET_DEVICE queries during identification."""

    protocol_revision: int
    board_id: int
    board_revision: int
    flash_size: int
    extf_size: int = 0


class UploadStage(Enum):
    """Workflow state, transitions are validated by `next_stage`."""

    IDLE = "idle"
    INSPECTING = "inspecting"
    AWAITING_CONFIRMATION = "awaiting_confirmation"
    ENTERING_BOOTLOADER = "entering_bootloader"
    IDENTIFYING = "identifying"
    ERASING = "erasing"
    PROGRAMMING = "programming"
    VERIFYING = "verifying"
    REBOOTING = "rebooting"
    RECONNECTING = "reconnecting"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


_HAPPY_PATH = [
    UploadStage.IDLE,
    UploadStage.INSPECTING,
    UploadStage.AWAITING_CONFIRMATION,
    UploadStage.ENTERING_BOOTLOADER,
    UploadStage.IDENTIFYING,
    UploadStage.ERASING,
    UploadStage.PROGRAMMING,
    UploadStage.VERIFYING,
    UploadStage.REBOOTING,
    UploadStage.RECONNECTING,
    UploadStage.COMPLETED,
]

# Cancellation is only allowed before the flash is touched. Once erase started, the only
# ways out are completed or failed, so a half written flash is never reported as cancelled.
_CANCELLABLE = frozenset(_HAPPY_PATH[: _HAPPY_PATH.index(UploadStage.ERASING)])
_TERMINAL = frozenset({UploadStage.COMPLETED, UploadStage.FAILED, UploadStage.CANCELLED})


def next_stage(current: UploadStage, target: UploadStage) -> UploadStage:
    """Return target if the transition is legal, raise ValueError otherwise."""
    if current in _TERMINAL:
        msg = _("{stage} is terminal").format(stage=current.value)
        raise ValueError(msg)
    if target == UploadStage.FAILED:
        return target
    if target == UploadStage.CANCELLED:
        if current in _CANCELLABLE:
            return target
        msg = _("cannot cancel during {stage}").format(stage=current.value)
        raise ValueError(msg)
    if _HAPPY_PATH.index(target) == _HAPPY_PATH.index(current) + 1:
        return target
    msg = _("illegal transition {current} -> {target}").format(current=current.value, target=target.value)
    raise ValueError(msg)


def load_apj(path: Path) -> FirmwareImage:
    """Read and decode an APJ file, raising FirmwareFileError before any serial I/O can happen."""
    if path.suffix.lower() != ".apj":
        msg = _("unsupported firmware format {suffix}, only .apj is supported").format(suffix=path.suffix)
        raise FirmwareFileError(msg)
    try:
        desc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        msg = _("cannot read APJ descriptor: {error}").format(error=exc)
        raise FirmwareFileError(msg) from exc
    if not isinstance(desc, dict):
        msg = _("APJ descriptor is not a JSON object")
        raise FirmwareFileError(msg)

    image = _decode_blob(desc, "image")
    extf_image = _decode_blob(desc, "extf_image") if "extf_image" in desc else b""

    try:
        board_id = int(desc["board_id"])
        image_size = int(desc["image_size"])
        extf_image_size = int(desc.get("extf_image_size", 0))
    except (KeyError, TypeError, ValueError) as exc:
        msg = _("APJ descriptor is missing or has invalid metadata: {error}").format(error=exc)
        raise FirmwareFileError(msg) from exc
    if board_id < 0 or image_size <= 0 or extf_image_size < 0:
        msg = _("APJ metadata values are out of range")
        raise FirmwareFileError(msg)
    if image_size > len(image) or extf_image_size > len(extf_image):
        msg = _("APJ image_size does not match the decoded image")
        raise FirmwareFileError(msg)

    board_rev = desc.get("board_revision")
    metadata = FirmwareImageMetadata(
        path=path,
        board_id=board_id,
        image_size=image_size,
        extf_image_size=extf_image_size,
        firmware_version=str(desc.get("version", "")),
        git_identity=str(desc.get("git_identity", "")),
        board_revision=int(board_rev) if board_rev is not None else None,
    )
    return FirmwareImage(metadata=metadata, image=image, extf_image=extf_image)


def _decode_blob(desc: dict, key: str) -> bytes:
    try:
        raw = zlib.decompress(base64.b64decode(desc[key], validate=True), bufsize=MAX_IMAGE_SIZE)
    except (KeyError, TypeError, ValueError, zlib.error) as exc:
        msg = _("APJ {key} is not valid base64+zlib data: {error}").format(key=key, error=exc)
        raise FirmwareFileError(msg) from exc
    if len(raw) > MAX_IMAGE_SIZE:
        msg = _("APJ {key} exceeds {limit} bytes").format(key=key, limit=MAX_IMAGE_SIZE)
        raise FirmwareFileError(msg)
    return _pad4(raw)


def _pad4(data: bytes) -> bytes:
    return data + b"\xff" * (-len(data) % 4)


def check_compatibility(image: FirmwareImage, bootloader: BootloaderInfo, *, force: bool = False) -> None:
    """Raise FirmwareCompatibilityError unless the image can safely be flashed on this bootloader."""
    if not BL_REV_MIN <= bootloader.protocol_revision <= BL_REV_MAX:
        msg = _("unsupported bootloader protocol revision {revision}").format(revision=bootloader.protocol_revision)
        raise BootloaderProtocolError(msg)
    meta = image.metadata
    if meta.board_id != bootloader.board_id and not force:
        msg = _("firmware is for board_id {image_id}, board reports {board_id}").format(
            image_id=meta.board_id, board_id=bootloader.board_id
        )
        raise FirmwareCompatibilityError(msg)
    if meta.image_size > bootloader.flash_size:
        msg = _("image of {size} bytes exceeds flash of {flash} bytes").format(
            size=meta.image_size, flash=bootloader.flash_size
        )
        raise FirmwareCompatibilityError(msg)
    if meta.extf_image_size > bootloader.extf_size:
        msg = _("external image of {size} bytes exceeds external flash of {extf} bytes").format(
            size=meta.extf_image_size, extf=bootloader.extf_size
        )
        raise FirmwareCompatibilityError(msg)


# Bootloader protocol codec. Encoders build the bytes to write, decoders check what came back.


def encode_get_sync() -> bytes:
    """GET_SYNC command."""
    return GET_SYNC + EOC


def encode_get_device(param: bytes) -> bytes:
    """GET_DEVICE command for one INFO_* parameter."""
    return GET_DEVICE + param + EOC


def encode_chip_erase(*, full: bool = False) -> bytes:
    """CHIP_ERASE, or CHIP_FULL_ERASE when full is set."""
    return (CHIP_FULL_ERASE if full else CHIP_ERASE) + EOC


def encode_prog_multi(chunk: bytes) -> bytes:
    """PROG_MULTI command carrying one chunk of at most PROG_MULTI_MAX bytes."""
    if not 0 < len(chunk) <= PROG_MULTI_MAX or len(chunk) % 4:
        msg = _("PROG_MULTI chunk must be 4..{limit} bytes and a multiple of 4, got {size}").format(
            limit=PROG_MULTI_MAX, size=len(chunk)
        )
        raise ValueError(msg)
    return PROG_MULTI + bytes([len(chunk)]) + chunk + EOC


def encode_read_multi(length: int) -> bytes:
    """READ_MULTI command for length bytes."""
    if not 0 < length <= READ_MULTI_MAX:
        msg = _("READ_MULTI length must be 1..{limit}, got {length}").format(limit=READ_MULTI_MAX, length=length)
        raise ValueError(msg)
    return READ_MULTI + bytes([length]) + EOC


def encode_get_crc() -> bytes:
    """GET_CRC command."""
    return GET_CRC + EOC


def encode_reboot() -> bytes:
    """REBOOT command."""
    return REBOOT + EOC


def decode_sync(reply: bytes) -> None:
    """Validate the two byte INSYNC/status reply that follows every command, raising on anything but OK."""
    if len(reply) < 2:
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
    """Little endian u32 as returned by GET_DEVICE and GET_CRC, before the sync bytes."""
    if len(reply) < 4:
        msg = _("short reply, expected 4 bytes, got {size}").format(size=len(reply))
        raise BootloaderProtocolError(msg)
    return int(struct.unpack("<I", reply[:4])[0])


def program_chunks(image: bytes) -> list[bytes]:
    """Split a padded image into PROG_MULTI sized chunks, in flash order."""
    return [image[i : i + PROG_MULTI_MAX] for i in range(0, len(image), PROG_MULTI_MAX)]
