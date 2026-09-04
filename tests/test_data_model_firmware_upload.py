#!/usr/bin/env python3

"""
Unit tests for the firmware upload domain model.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import base64
import json
import struct
import zlib
from binascii import crc32
from pathlib import Path

import pytest

from ardupilot_methodic_configurator import data_model_firmware_upload as fw

# pylint: disable=redefined-outer-name, too-few-public-methods, too-many-return-statements


def write_apj(tmp_path: Path, image: bytes, **overrides: object) -> Path:
    desc: dict[str, object] = {
        "board_id": 9,
        "image_size": len(image),
        "image": base64.b64encode(zlib.compress(image)).decode(),
        "version": "4.6.0",
        "git_identity": "abc1234",
    }
    desc.update(overrides)
    path = tmp_path / "arducopter.apj"
    path.write_text(json.dumps(desc), encoding="utf-8")
    return path


@pytest.fixture
def small_image() -> bytes:
    return bytes(range(256)) * 3 + b"\x01\x02\x03"  # 771 bytes, not a multiple of 4


class TestApjLoading:
    """User selects a firmware file and the model tells them what it is before touching the board."""

    def test_user_sees_metadata_from_a_valid_apj_file(self, tmp_path: Path, small_image: bytes) -> None:
        """
        Test user sees metadata from a valid apj file.

        GIVEN: a well formed APJ file
        WHEN: it is loaded
        THEN: metadata comes from the descriptor and the image is padded to 4 bytes with 0xFF
        """
        image = fw.load_apj(write_apj(tmp_path, small_image))

        assert image.metadata.board_id == 9
        assert image.metadata.image_size == len(small_image)
        assert image.metadata.firmware_version == "4.6.0"
        assert image.image == small_image + b"\xff"
        assert len(image.image) % 4 == 0
        assert image.extf_image == b""

    def test_user_gets_a_clear_error_for_a_non_apj_file(self, tmp_path: Path) -> None:
        """
        Test user gets a clear error for a non apj file.

        GIVEN: a .bin file
        WHEN: the user tries to load it
        THEN: a typed file error explains only .apj is supported
        """
        path = tmp_path / "arducopter.bin"
        path.write_bytes(b"\x00" * 16)

        with pytest.raises(fw.FirmwareFileError, match=r"only \.apj"):
            fw.load_apj(path)

    @pytest.mark.parametrize(
        ("content", "reason"),
        [
            ("not json", "descriptor"),
            ("[1, 2]", "not a JSON object"),
            (json.dumps({"board_id": 9, "image_size": 4, "image": "!!notbase64!!"}), "base64"),
            (json.dumps({"board_id": 9, "image_size": 4, "image": base64.b64encode(b"notzlib").decode()}), "zlib"),
            (json.dumps({"image_size": 4, "image": base64.b64encode(zlib.compress(b"abcd")).decode()}), "metadata"),
            (
                json.dumps({"board_id": 9, "image_size": 99, "image": base64.b64encode(zlib.compress(b"abcd")).decode()}),
                "image_size",
            ),
        ],
    )
    def test_malformed_apj_is_rejected_before_any_serial_access(self, tmp_path: Path, content: str, reason: str) -> None:
        """
        Test malformed apj is rejected before any serial access.

        GIVEN: a corrupt or inconsistent APJ file
        WHEN: it is loaded
        THEN: a FirmwareFileError names the problem
        """
        path = tmp_path / "bad.apj"
        path.write_text(content, encoding="utf-8")

        with pytest.raises(fw.FirmwareFileError, match=reason):
            fw.load_apj(path)

    def test_oversized_image_is_rejected(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """
        Test oversized image is rejected.

        GIVEN: an APJ whose image decompresses beyond the sanity bound
        WHEN: it is loaded
        THEN: it is refused instead of allocating the whole thing
        """
        monkeypatch.setattr(fw, "MAX_IMAGE_SIZE", 1024)
        big = b"\x00" * 4096
        path = write_apj(tmp_path, big)

        with pytest.raises(fw.FirmwareFileError, match="exceeds"):
            fw.load_apj(path)

    def test_crc_matches_the_reference_uploader_computation(self, tmp_path: Path, small_image: bytes) -> None:
        """
        Test crc matches the reference uploader computation.

        GIVEN: a loaded image and a flash size larger than the image
        WHEN: the CRC is computed
        THEN: it equals crc32 over the image padded with 0xFF up to flash size, as Tools/scripts/uploader.py does
        """
        image = fw.load_apj(write_apj(tmp_path, small_image))
        flash_size = 2048
        expected = crc32(image.image + b"\xff" * (flash_size - len(image.image)), 0)

        assert image.crc(flash_size) == expected


class TestCompatibility:
    """The model refuses to flash anything that does not match the detected board."""

    @pytest.fixture
    def image(self, tmp_path: Path, small_image: bytes) -> fw.FirmwareImage:
        return fw.load_apj(write_apj(tmp_path, small_image))

    def test_matching_board_and_enough_flash_is_accepted(self, image: fw.FirmwareImage) -> None:
        fw.check_compatibility(image, fw.BootloaderInfo(5, 9, 0, 2048))

    def test_board_id_mismatch_is_refused_by_default(self, image: fw.FirmwareImage) -> None:
        with pytest.raises(fw.FirmwareCompatibilityError, match="board_id 9, board reports 42"):
            fw.check_compatibility(image, fw.BootloaderInfo(5, 42, 0, 2048))

    def test_board_id_mismatch_is_allowed_only_with_explicit_force(self, image: fw.FirmwareImage) -> None:
        fw.check_compatibility(image, fw.BootloaderInfo(5, 42, 0, 2048), force=True)

    def test_image_larger_than_flash_is_refused_even_when_forced(self, image: fw.FirmwareImage) -> None:
        with pytest.raises(fw.FirmwareCompatibilityError, match="exceeds flash"):
            fw.check_compatibility(image, fw.BootloaderInfo(5, 9, 0, 512), force=True)

    @pytest.mark.parametrize("revision", [1, 6])
    def test_unsupported_bootloader_revision_is_refused(self, image: fw.FirmwareImage, revision: int) -> None:
        with pytest.raises(fw.BootloaderProtocolError, match="revision"):
            fw.check_compatibility(image, fw.BootloaderInfo(revision, 9, 0, 2048))


class TestStateMachine:
    """Cancellation is only offered while it is still safe."""

    def test_happy_path_walks_every_stage_in_order(self) -> None:
        stage = fw.UploadStage.IDLE
        for target in list(fw.UploadStage)[1:11]:
            stage = fw.next_stage(stage, target)
        assert stage is fw.UploadStage.COMPLETED

    def test_user_can_cancel_before_the_flash_is_erased(self) -> None:
        assert fw.next_stage(fw.UploadStage.AWAITING_CONFIRMATION, fw.UploadStage.CANCELLED) is fw.UploadStage.CANCELLED
        assert fw.next_stage(fw.UploadStage.IDENTIFYING, fw.UploadStage.CANCELLED) is fw.UploadStage.CANCELLED

    @pytest.mark.parametrize("stage", [fw.UploadStage.ERASING, fw.UploadStage.PROGRAMMING, fw.UploadStage.VERIFYING])
    def test_user_cannot_cancel_once_the_flash_is_being_written(self, stage: fw.UploadStage) -> None:
        with pytest.raises(ValueError, match="cannot cancel"):
            fw.next_stage(stage, fw.UploadStage.CANCELLED)

    def test_any_stage_can_fail(self) -> None:
        assert fw.next_stage(fw.UploadStage.PROGRAMMING, fw.UploadStage.FAILED) is fw.UploadStage.FAILED

    def test_skipping_a_stage_is_rejected(self) -> None:
        with pytest.raises(ValueError, match="illegal transition"):
            fw.next_stage(fw.UploadStage.INSPECTING, fw.UploadStage.ERASING)

    def test_terminal_stages_do_not_move(self) -> None:
        with pytest.raises(ValueError, match="terminal"):
            fw.next_stage(fw.UploadStage.COMPLETED, fw.UploadStage.IDLE)


class FakeBootloader:
    """
    Minimal rev 5 bootloader behind a byte pipe.

    It consumes exactly what the codec encodes and answers like the real protocol, so a
    mismatch between encoder and decoder fails here instead of on hardware.
    """

    def __init__(self, board_id: int = 9, flash_size: int = 2048) -> None:
        self.board_id = board_id
        self.flash_size = flash_size
        self.flash = b""
        self.erased = False
        self.rebooted = False

    def exchange(self, request: bytes) -> bytes:  # noqa: PLR0911
        assert request.endswith(fw.EOC)
        cmd, body = request[0:1], request[1:-1]
        if cmd == fw.GET_SYNC:
            return fw.INSYNC + fw.OK
        if cmd == fw.GET_DEVICE:
            values = {
                fw.INFO_BL_REV: 5,
                fw.INFO_BOARD_ID: self.board_id,
                fw.INFO_BOARD_REV: 0,
                fw.INFO_FLASH_SIZE: self.flash_size,
                fw.INFO_EXTF_SIZE: 0,
            }
            return struct.pack("<I", values[body]) + fw.INSYNC + fw.OK
        if cmd == fw.CHIP_ERASE:
            self.erased, self.flash = True, b""
            return fw.INSYNC + fw.OK
        if cmd == fw.PROG_MULTI:
            if not self.erased:
                return fw.INSYNC + fw.FAILED
            length, chunk = body[0], body[1:]
            assert len(chunk) == length
            self.flash += chunk
            return fw.INSYNC + fw.OK
        if cmd == fw.GET_CRC:
            padded = self.flash + b"\xff" * (self.flash_size - len(self.flash))
            return struct.pack("<I", crc32(padded, 0)) + fw.INSYNC + fw.OK
        if cmd == fw.REBOOT:
            self.rebooted = True
            return fw.INSYNC + fw.OK
        return fw.INSYNC + fw.INVALID


def identify(bl: FakeBootloader) -> fw.BootloaderInfo:
    fw.decode_sync(bl.exchange(fw.encode_get_sync()))

    def info(param: bytes) -> int:
        reply = bl.exchange(fw.encode_get_device(param))
        fw.decode_sync(reply[4:])
        return fw.decode_uint32(reply)

    return fw.BootloaderInfo(
        info(fw.INFO_BL_REV),
        info(fw.INFO_BOARD_ID),
        info(fw.INFO_BOARD_REV),
        info(fw.INFO_FLASH_SIZE),
        info(fw.INFO_EXTF_SIZE),
    )


class TestBootloaderCodec:
    """Encoders and decoders agree with a fake bootloader on the full erase, program, verify sequence."""

    def test_full_upload_sequence_verifies_against_fake_bootloader(self, tmp_path: Path, small_image: bytes) -> None:
        """
        Test full upload sequence verifies against fake bootloader.

        GIVEN: a loaded image and a fake bootloader with a matching board id
        WHEN: identify, erase, program every chunk, then GET_CRC
        THEN: the bootloader CRC equals the image CRC and the reboot is acknowledged
        """
        image = fw.load_apj(write_apj(tmp_path, small_image))
        bl = FakeBootloader()

        info = identify(bl)
        fw.check_compatibility(image, info)
        fw.decode_sync(bl.exchange(fw.encode_chip_erase()))
        chunks = fw.program_chunks(image.image)
        for chunk in chunks:
            fw.decode_sync(bl.exchange(fw.encode_prog_multi(chunk)))
        crc_reply = bl.exchange(fw.encode_get_crc())
        fw.decode_sync(crc_reply[4:])
        fw.decode_sync(bl.exchange(fw.encode_reboot()))

        assert info == fw.BootloaderInfo(5, 9, 0, 2048, 0)
        assert len(chunks) == -(-len(image.image) // fw.PROG_MULTI_MAX)
        assert bl.flash == image.image
        assert fw.decode_uint32(crc_reply) == image.crc(info.flash_size)
        assert bl.rebooted

    def test_programming_before_erase_surfaces_as_a_protocol_error(self, tmp_path: Path, small_image: bytes) -> None:
        image = fw.load_apj(write_apj(tmp_path, small_image))
        bl = FakeBootloader()

        with pytest.raises(fw.BootloaderProtocolError, match="OPERATION FAILED"):
            fw.decode_sync(bl.exchange(fw.encode_prog_multi(fw.program_chunks(image.image)[0])))

    @pytest.mark.parametrize(
        ("reply", "reason"),
        [
            (b"", "short reply"),
            (b"\x00\x10", "expected INSYNC"),
            (fw.INSYNC + fw.INVALID, "INVALID"),
            (fw.INSYNC + fw.BAD_SILICON_REV, "silicon"),
            (fw.INSYNC + b"\x7f", "unexpected status"),
        ],
    )
    def test_bad_sync_replies_are_typed_errors(self, reply: bytes, reason: str) -> None:
        with pytest.raises(fw.BootloaderProtocolError, match=reason):
            fw.decode_sync(reply)

    @pytest.mark.parametrize("length", [0, 3, fw.PROG_MULTI_MAX + 4])
    def test_prog_multi_refuses_chunks_the_bootloader_would_reject(self, length: int) -> None:
        with pytest.raises(ValueError, match="PROG_MULTI"):
            fw.encode_prog_multi(b"\x00" * length)

    def test_read_multi_encodes_length_byte(self) -> None:
        assert fw.encode_read_multi(252) == fw.READ_MULTI + b"\xfc" + fw.EOC
        with pytest.raises(ValueError, match="READ_MULTI"):
            fw.encode_read_multi(253)

    def test_short_uint32_reply_is_a_protocol_error(self) -> None:
        with pytest.raises(fw.BootloaderProtocolError, match="4 bytes"):
            fw.decode_uint32(b"\x01\x02")
