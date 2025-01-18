#!/usr/bin/env python3

"""
Tests for FTP_OP class in backend_mavftp.py.

This file is part of Ardupilot methodic configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2025 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import unittest

import pytest

from ardupilot_methodic_configurator.backend_mavftp import (
    FTP_OP,
    ERR_EndOfFile,
    ERR_Fail,
    ERR_FailErrno,
    ERR_FailToOpenLocalFile,
    ERR_FileExists,
    ERR_FileNotFound,
    ERR_FileProtected,
    ERR_InvalidArguments,
    ERR_InvalidDataSize,
    ERR_InvalidErrorCode,
    ERR_InvalidOpcode,
    ERR_InvalidSession,
    ERR_NoErrorCodeInNack,
    ERR_NoErrorCodeInPayload,
    ERR_NoFilesystemErrorInPayload,
    ERR_None,
    ERR_NoSessionsAvailable,
    ERR_PayloadTooLarge,
    ERR_PutAlreadyInProgress,
    ERR_RemoteReplyTimeout,
    ERR_UnknownCommand,
    MAVFTPReturn,
    MAVFTPSetting,
    MAVFTPSettings,
    ParamData,
    WriteQueue,
)


class TestFTPOP(unittest.TestCase):
    """Test cases for FTP_OP class."""

    def test_init(self) -> None:
        """Test initialization of FTP_OP."""
        op = FTP_OP(seq=1, session=2, opcode=3, size=4, req_opcode=5, burst_complete=True, offset=6, payload=b"test")
        assert op.seq == 1
        assert op.session == 2
        assert op.opcode == 3
        assert op.size == 4
        assert op.req_opcode == 5
        assert op.burst_complete
        assert op.offset == 6
        assert op.payload == b"test"

    def test_pack_with_payload(self) -> None:
        """Test pack method with payload."""
        op = FTP_OP(seq=1, session=2, opcode=3, size=4, req_opcode=5, burst_complete=True, offset=6, payload=b"test")
        packed = op.pack()
        assert isinstance(packed, bytearray)
        # Header should be 12 bytes (struct.pack("<HBBBBBBI"))
        # Plus 4 bytes for the "test" payload
        assert len(packed) == 16
        # Check first bytes match expected values
        assert packed[0] == 1  # seq (low byte)
        assert packed[1] == 0  # seq (high byte)
        assert packed[2] == 2  # session
        assert packed[3] == 3  # opcode
        assert packed[4] == 4  # size
        assert packed[5] == 5  # req_opcode
        assert packed[6] == 1  # burst_complete (True = 1)
        assert packed[12:16] == b"test"  # payload

    def test_pack_without_payload(self) -> None:
        """Test pack method without payload."""
        op = FTP_OP(seq=1, session=2, opcode=3, size=4, req_opcode=5, burst_complete=False, offset=6, payload=None)
        packed = op.pack()
        assert isinstance(packed, bytearray)
        # Header should be 12 bytes (struct.pack("<HBBBBBBI"))
        assert len(packed) == 12
        # Check first bytes match expected values
        assert packed[0] == 1  # seq (low byte)
        assert packed[1] == 0  # seq (high byte)
        assert packed[2] == 2  # session
        assert packed[3] == 3  # opcode
        assert packed[4] == 4  # size
        assert packed[5] == 5  # req_opcode
        assert packed[6] == 0  # burst_complete (False = 0)

    def test_str_with_payload(self) -> None:
        """Test string representation with payload."""
        op = FTP_OP(seq=1, session=2, opcode=3, size=4, req_opcode=5, burst_complete=True, offset=6, payload=b"test")
        str_rep = str(op)
        assert "seq:1" in str_rep
        assert "sess:2" in str_rep
        assert "opcode:3" in str_rep
        assert "req_opcode:5" in str_rep
        assert "size:4" in str_rep
        assert "bc:True" in str_rep
        assert "ofs:6" in str_rep
        assert "plen=4" in str_rep
        assert "[116]" in str_rep  # ASCII value of 't'

    def test_str_without_payload(self) -> None:
        """Test string representation without payload."""
        op = FTP_OP(seq=1, session=2, opcode=3, size=4, req_opcode=5, burst_complete=False, offset=6, payload=None)
        str_rep = str(op)
        assert "seq:1" in str_rep
        assert "sess:2" in str_rep
        assert "opcode:3" in str_rep
        assert "req_opcode:5" in str_rep
        assert "size:4" in str_rep
        assert "bc:False" in str_rep
        assert "ofs:6" in str_rep
        assert "plen=0" in str_rep
        assert "[" not in str_rep  # No payload byte representation

    def test_items(self) -> None:
        """Test items generator method."""
        op = FTP_OP(seq=1, session=2, opcode=3, size=4, req_opcode=5, burst_complete=True, offset=6, payload=b"test")
        items = dict(op.items())
        assert items["seq"] == 1
        assert items["session"] == 2
        assert items["opcode"] == 3
        assert items["size"] == 4
        assert items["req_opcode"] == 5
        assert items["burst_complete"]
        assert items["offset"] == 6
        assert items["payload"] == b"test"


class TestWriteQueue(unittest.TestCase):
    """Test cases for WriteQueue class."""

    def test_init(self) -> None:
        """Test initialization of WriteQueue."""
        queue = WriteQueue(ofs=100, size=1024)
        assert queue.ofs == 100
        assert queue.size == 1024
        assert queue.last_send == 0

    def test_attributes_types(self) -> None:
        """Test attribute types of WriteQueue."""
        queue = WriteQueue(ofs=100, size=1024)
        assert isinstance(queue.ofs, int)
        assert isinstance(queue.size, int)
        assert isinstance(queue.last_send, (int, float))

    def test_attribute_modification(self) -> None:
        """Test modifying WriteQueue attributes."""
        queue = WriteQueue(ofs=100, size=1024)
        queue.ofs = 200
        queue.size = 2048
        queue.last_send = 1.5

        assert queue.ofs == 200
        assert queue.size == 2048
        assert queue.last_send == 1.5


class TestParamData(unittest.TestCase):
    """Test cases for ParamData class."""

    def test_init(self) -> None:
        """Test initialization of ParamData."""
        param_data = ParamData()
        assert not param_data.params
        assert param_data.defaults is None

    def test_add_param(self) -> None:
        """Test adding parameters."""
        param_data = ParamData()
        param_data.add_param(b"TEST_PARAM", 1.5, float)
        assert len(param_data.params) == 1
        assert param_data.params[0] == (b"TEST_PARAM", 1.5, float)

    def test_add_default(self) -> None:
        """Test adding default parameters."""
        param_data = ParamData()
        param_data.add_default(b"TEST_PARAM", 2.0, float)
        assert len(param_data.defaults) == 1
        assert param_data.defaults[0] == (b"TEST_PARAM", 2.0, float)

    def test_multiple_params(self) -> None:
        """Test adding multiple parameters."""
        param_data = ParamData()
        param_data.add_param(b"PARAM1", 1.0, float)
        param_data.add_param(b"PARAM2", 2, int)
        param_data.add_default(b"PARAM1", 1.5, float)
        param_data.add_default(b"PARAM2", 3, int)

        assert len(param_data.params) == 2
        assert len(param_data.defaults) == 2
        assert param_data.params[0] == (b"PARAM1", 1.0, float)
        assert param_data.params[1] == (b"PARAM2", 2, int)
        assert param_data.defaults[0] == (b"PARAM1", 1.5, float)
        assert param_data.defaults[1] == (b"PARAM2", 3, int)


class TestMAVFTPSetting(unittest.TestCase):
    """Test cases for MAVFTPSetting class."""

    def test_init(self) -> None:
        """Test initialization of MAVFTPSetting."""
        setting = MAVFTPSetting("test_setting", int, 42)
        assert setting.name == "test_setting"
        assert setting.type is int
        assert setting.default == 42
        assert setting.value == 42

    def test_value_modification(self) -> None:
        """Test modifying setting value."""
        setting = MAVFTPSetting("test_setting", int, 42)
        setting.value = 100
        assert setting.value == 100
        assert setting.default == 42  # Default should remain unchanged


class TestMAVFTPSettings(unittest.TestCase):
    """Test cases for MAVFTPSettings class."""

    def test_init(self) -> None:
        """Test initialization of MAVFTPSettings."""
        settings_vars = [("setting1", int, 42), ("setting2", float, 3.14), ("setting3", bool, True)]
        settings = MAVFTPSettings(settings_vars)
        assert settings.setting1 == 42
        assert settings.setting2 == 3.14
        assert settings.setting3 is True

    def test_append_setting(self) -> None:
        """Test appending new settings."""
        settings = MAVFTPSettings([])
        settings.append(("new_setting", int, 100))
        assert settings.new_setting == 100

    def test_append_setting_object(self) -> None:
        """Test appending MAVFTPSetting object."""
        settings = MAVFTPSettings([])
        setting = MAVFTPSetting("test_setting", int, 42)
        settings.append(setting)
        assert settings.test_setting == 42

    def test_modify_setting(self) -> None:
        """Test modifying setting values."""
        settings = MAVFTPSettings([("test_setting", int, 42)])
        settings.test_setting = 100
        assert settings.test_setting == 100

    def test_invalid_setting_access(self) -> None:
        """Test accessing non-existent setting."""
        settings = MAVFTPSettings([])
        with pytest.raises(AttributeError):
            _ = settings.nonexistent_setting

    def test_invalid_setting_modification(self) -> None:
        """Test modifying non-existent setting."""
        settings = MAVFTPSettings([])
        with pytest.raises(AttributeError):
            settings.nonexistent_setting = 42


class TestMAVFTPReturn(unittest.TestCase):
    """Test cases for MAVFTPReturn class."""

    def test_init(self) -> None:
        """Test initialization with different parameters."""
        ret = MAVFTPReturn("TestOp", ERR_None)
        assert ret.operation_name == "TestOp"
        assert ret.error_code == ERR_None
        assert ret.system_error == 0
        assert ret.invalid_error_code == 0
        assert ret.invalid_opcode == 0
        assert ret.invalid_payload_size == 0

        # Test with all parameters
        ret = MAVFTPReturn("TestOp", ERR_Fail, 1, 2, 3, 4)
        assert ret.operation_name == "TestOp"
        assert ret.error_code == ERR_Fail
        assert ret.system_error == 1
        assert ret.invalid_error_code == 2
        assert ret.invalid_opcode == 3
        assert ret.invalid_payload_size == 4

    def test_return_code(self) -> None:
        """Test return_code property."""
        ret = MAVFTPReturn("TestOp", ERR_None)
        assert ret.return_code == ERR_None

        ret = MAVFTPReturn("TestOp", ERR_Fail)
        assert ret.return_code == ERR_Fail

    def test_display_message_success(self) -> None:
        """Test display_message for successful operations."""
        ret = MAVFTPReturn("TestOp", ERR_None)
        with self.assertLogs(level="INFO") as cm:
            ret.display_message()
        assert "TestOp succeeded" in cm.output[0]

    def test_display_message_errors(self) -> None:
        """Test display_message for various error conditions."""
        error_test_cases = [
            # ERROR level messages
            (ERR_Fail, "TestOp failed, generic error", "ERROR"),
            (ERR_FailErrno, "TestOp failed, system error 42", "ERROR"),
            (ERR_InvalidDataSize, "TestOp failed, invalid data size", "ERROR"),
            (ERR_InvalidSession, "TestOp failed, session is not currently open", "ERROR"),
            (ERR_NoSessionsAvailable, "TestOp failed, no sessions available", "ERROR"),
            (ERR_EndOfFile, "TestOp failed, offset past end of file", "ERROR"),
            (ERR_UnknownCommand, "TestOp failed, unknown command", "ERROR"),
            (ERR_NoErrorCodeInPayload, "TestOp failed, payload contains no error code", "ERROR"),
            (ERR_NoErrorCodeInNack, "TestOp failed, no error code", "ERROR"),
            (ERR_NoFilesystemErrorInPayload, "TestOp failed, file-system error missing in payload", "ERROR"),
            (ERR_InvalidErrorCode, "TestOp failed, invalid error code 42", "ERROR"),
            (ERR_PayloadTooLarge, "TestOp failed, payload is too long 42", "ERROR"),
            (ERR_InvalidOpcode, "TestOp failed, invalid opcode 42", "ERROR"),
            (ERR_InvalidArguments, "TestOp failed, invalid arguments", "ERROR"),
            (ERR_PutAlreadyInProgress, "TestOp failed, put already in progress", "ERROR"),
            (ERR_FailToOpenLocalFile, "TestOp failed, failed to open local file", "ERROR"),
            (ERR_RemoteReplyTimeout, "TestOp failed, remote reply timeout", "ERROR"),
            # WARNING level messages
            (ERR_FileExists, "TestOp failed, file/directory already exists", "WARNING"),
            (ERR_FileProtected, "TestOp failed, file/directory is protected", "WARNING"),
            (ERR_FileNotFound, "TestOp failed, file/directory not found", "WARNING"),
        ]

        for error_code, expected_message, level in error_test_cases:
            ret = MAVFTPReturn(
                "TestOp", error_code, system_error=42, invalid_error_code=42, invalid_opcode=42, invalid_payload_size=42
            )
            with self.assertLogs(level=level) as cm:
                ret.display_message()
            assert expected_message in cm.output[0]

    def test_display_message_unknown_error(self) -> None:
        """Test display_message for unknown error code."""
        ret = MAVFTPReturn("TestOp", 999)  # Unknown error code
        with self.assertLogs(level="ERROR") as cm:
            ret.display_message()
        assert "TestOp failed, unknown error 999 in display_message()" in cm.output[0]


if __name__ == "__main__":
    unittest.main()
