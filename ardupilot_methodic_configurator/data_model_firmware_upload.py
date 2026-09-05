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
import zlib
from binascii import crc32
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any

from ardupilot_methodic_configurator import _

BL_REV_MIN = 2
BL_REV_MAX = 5

# Sanity bound on each decompressed image, well above any current flight controller flash.
MAX_IMAGE_SIZE = 64 * 1024 * 1024
# A base64 APJ blob can be roughly 4/3 the compressed input.  Permit a small
# compression-stream overhead while rejecting a descriptor before decoding it.
MAX_ENCODED_BLOB_SIZE = ((MAX_IMAGE_SIZE + 65536) * 4 // 3) + 4


class FirmwareUploadError(Exception):
    """Base class for typed firmware upload errors, `stage` names where it happened."""

    stage = "unknown"

    def __init__(self, message: str, *, stage: str | None = None) -> None:
        super().__init__(message)
        if stage is not None:
            self.stage = stage


class FirmwareFileError(FirmwareUploadError):
    """The firmware file is unreadable, malformed or not a supported format."""

    stage = "inspecting"


class FirmwareCompatibilityError(FirmwareUploadError):
    """The image does not match the connected board or does not fit in flash."""

    stage = "identifying"


class BootloaderProtocolError(FirmwareUploadError):
    """The bootloader answered something unexpected, or a protocol revision is unsupported."""

    stage = "identifying"


class FirmwareReconnectError(FirmwareUploadError):
    """Firmware was flashed but the normal flight-controller connection did not return."""

    stage = "reconnecting"


class FirmwareUploadCancelledError(FirmwareUploadError):
    """The user cancelled before firmware erase began."""

    stage = "identifying"


class FirmwareConfirmationError(FirmwareUploadError):
    """An irreversible upload was requested without explicit confirmation."""

    stage = "awaiting_confirmation"


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

    def extf_crc(self) -> int:
        """CRC32 of the unpadded external-flash payload."""
        return crc32(self.extf_image[: self.metadata.extf_image_size], 0)


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


def parse_apj(contents: str | bytes, *, path: Path = Path()) -> FirmwareImage:
    """Purely parse and validate APJ contents; callers own file-system access."""
    try:
        desc: Any = json.loads(contents)
    except (UnicodeDecodeError, json.JSONDecodeError, TypeError) as exc:
        msg = _("cannot parse APJ descriptor: {error}").format(error=exc)
        raise FirmwareFileError(msg) from exc
    if not isinstance(desc, dict):
        msg = _("APJ descriptor is not a JSON object")
        raise FirmwareFileError(msg)

    raw_image = _decode_blob(desc, "image")
    raw_extf_image = _decode_blob(desc, "extf_image") if "extf_image" in desc else b""

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
    if image_size != len(raw_image) or extf_image_size != len(raw_extf_image):
        msg = _("APJ image_size does not match the decoded image")
        raise FirmwareFileError(msg)

    board_rev = desc.get("board_revision")
    try:
        parsed_board_rev = int(board_rev) if board_rev is not None else None
    except (TypeError, ValueError) as exc:
        msg = _("APJ descriptor is missing or has invalid metadata: {error}").format(error=exc)
        raise FirmwareFileError(msg) from exc
    metadata = FirmwareImageMetadata(
        path=path,
        board_id=board_id,
        image_size=image_size,
        extf_image_size=extf_image_size,
        firmware_version=str(desc.get("version", "")),
        git_identity=str(desc.get("git_identity", "")),
        board_revision=parsed_board_rev,
    )
    return FirmwareImage(metadata=metadata, image=_pad4(raw_image), extf_image=_pad4(raw_extf_image))


def _decode_blob(desc: dict, key: str) -> bytes:
    try:
        encoded = desc[key]
        if not isinstance(encoded, (str, bytes)):
            msg = _("APJ {key} is not valid base64+zlib data: expected text").format(key=key)
            raise FirmwareFileError(msg)
        if len(encoded) > MAX_ENCODED_BLOB_SIZE:
            msg = _("APJ {key} exceeds {limit} encoded bytes").format(key=key, limit=MAX_ENCODED_BLOB_SIZE)
            raise FirmwareFileError(msg)
        compressed = base64.b64decode(encoded, validate=True)
        decompressor = zlib.decompressobj()
        raw = decompressor.decompress(compressed, MAX_IMAGE_SIZE + 1)
        if len(raw) > MAX_IMAGE_SIZE or decompressor.unconsumed_tail:
            msg = _("APJ {key} exceeds {limit} bytes").format(key=key, limit=MAX_IMAGE_SIZE)
            raise FirmwareFileError(msg)
        raw += decompressor.flush(MAX_IMAGE_SIZE + 1 - len(raw))
        if len(raw) > MAX_IMAGE_SIZE:
            msg = _("APJ {key} exceeds {limit} bytes").format(key=key, limit=MAX_IMAGE_SIZE)
            raise FirmwareFileError(msg)
        if not decompressor.eof:
            msg = _("APJ {key} is not valid base64+zlib data: truncated stream").format(key=key)
            raise FirmwareFileError(msg)
    except (KeyError, TypeError, ValueError, zlib.error) as exc:
        msg = _("APJ {key} is not valid base64+zlib data: {error}").format(key=key, error=exc)
        raise FirmwareFileError(msg) from exc
    return raw


def _pad4(data: bytes) -> bytes:
    return data + b"\xff" * (-len(data) % 4)


def check_compatibility(image: FirmwareImage, bootloader: BootloaderInfo, *, force: bool = False) -> None:
    """Raise FirmwareCompatibilityError unless the image can safely be flashed on this bootloader."""
    if not BL_REV_MIN <= bootloader.protocol_revision <= BL_REV_MAX:
        msg = _("unsupported bootloader protocol revision {revision}").format(revision=bootloader.protocol_revision)
        raise BootloaderProtocolError(msg)
    meta = image.metadata
    compatible_board_ids = {33: 9}
    board_matches = meta.board_id == bootloader.board_id or compatible_board_ids.get(bootloader.board_id) == meta.board_id
    if not board_matches and not force:
        msg = _("firmware is for board_id {image_id}, board reports {board_id}").format(
            image_id=meta.board_id, board_id=bootloader.board_id
        )
        raise FirmwareCompatibilityError(msg)
    if len(image.image) > bootloader.flash_size:
        msg = _("image of {size} bytes exceeds flash of {flash} bytes").format(
            size=len(image.image), flash=bootloader.flash_size
        )
        raise FirmwareCompatibilityError(msg)
    if len(image.extf_image) > bootloader.extf_size:
        msg = _("external image of {size} bytes exceeds external flash of {extf} bytes").format(
            size=len(image.extf_image), extf=bootloader.extf_size
        )
        raise FirmwareCompatibilityError(msg)
