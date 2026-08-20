#!/usr/bin/env python3

"""
Tests backend_mavftp.py file.

MAVLink File Transfer Protocol support test - https://mavlink.io/en/services/ftp.html

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2026 Amilcar Lucas

SPDX-License-Identifier: GPL-3.0-or-later
"""

import logging
import struct
import unittest

# from unittest.mock import patch
from io import BytesIO, StringIO
from unittest.mock import Mock, patch

from pymavlink import mavutil

# from ardupilot_methodic_configurator.backend_mavftp import ERR_NoErrorCodeInPayload
# from ardupilot_methodic_configurator.backend_mavftp import ERR_NoErrorCodeInNack
# from ardupilot_methodic_configurator.backend_mavftp import ERR_NoFilesystemErrorInPayload
# from ardupilot_methodic_configurator.backend_mavftp import ERR_PayloadTooLarge
# from ardupilot_methodic_configurator.backend_mavftp import ERR_InvalidOpcode
from ardupilot_methodic_configurator.backend_mavftp import (
    FTP_OP,
    MAVFTP,
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
    ERR_InvalidSession,
    ERR_None,
    ERR_NoSessionsAvailable,
    ERR_PutAlreadyInProgress,
    ERR_RemoteReplyTimeout,
    ERR_UnknownCommand,
    MAVFTPReturn,
    OP_Ack,
    OP_ListDirectory,
    OP_Nack,
    OP_ReadFile,
)

PARAM_HEADER_STRUCT = struct.Struct("<HHH")
PARAM_MAGIC = 0x671B
PARAM_MAGIC_WITH_DEFAULTS = 0x671C


class TestMAVFTPPayloadDecoding(unittest.TestCase):
    """Test MAVFTP payload decoding."""

    def setUp(self) -> None:
        self.log_stream = StringIO()
        handler = logging.StreamHandler(self.log_stream)
        formatter = logging.Formatter("%(levelname)s: %(message)s")
        handler.setFormatter(formatter)
        logger = logging.getLogger()
        logger.addHandler(handler)
        logger.setLevel(logging.DEBUG)

        # Mock mavutil.mavlink_connection to simulate a connection
        self.mock_master = mavutil.mavlink_connection(device="udp:localhost:0", source_system=1)

        # Initialize MAVFTP instance for testing
        self.mav_ftp = MAVFTP(self.mock_master, target_system=1, target_component=1)

    def tearDown(self) -> None:
        self.log_stream.seek(0)
        self.log_stream.truncate(0)

    def test_logging(self) -> None:
        # Code that triggers logging
        logging.info("This is a test log message")

        # Flush and get log output
        log_output = self.log_stream.getvalue()

        # Assert to check if the expected log is in log_output
        assert "This is a test log message" in log_output

    def test_getparams_decode_failure_returns_ftp_error_instead_of_exiting(self) -> None:
        """A malformed packed parameter file must be reported without terminating the app."""
        self.mav_ftp.cmd_get = Mock()
        self.mav_ftp.cmd_get.side_effect = lambda _args, callback, **_kwargs: callback(BytesIO(b"bad"))

        result = self.mav_ftp.cmd_getparams(["values.param", "defaults.param"])

        assert result.error_code == ERR_Fail

    def test_process_ftp_reply_propagates_getparams_callback_failure(self) -> None:
        """A parameter-decoding callback failure makes the transfer fail, enabling fallback."""
        callback_failure = MAVFTPReturn("GetParams", ERR_Fail)
        packet_result = MAVFTPReturn("BurstReadFile", ERR_None)
        self.mav_ftp.master = Mock()
        self.mav_ftp.master.recv_match.return_value = Mock()

        def simulate_finished_transfer(_message: object) -> MAVFTPReturn:
            self.mav_ftp.callback_failure = callback_failure
            return packet_result

        with patch.object(self.mav_ftp, "_MAVFTP__mavlink_packet", side_effect=simulate_finished_transfer):
            result = self.mav_ftp.process_ftp_reply("getparams", timeout=5)

        assert result is callback_failure

    def test_param_decode_rejects_truncated_parameter_record(self) -> None:
        """A packed parameter record missing its value must return no data."""
        payload = PARAM_HEADER_STRUCT.pack(PARAM_MAGIC, 1, 1) + b"\x01\x00A"

        assert MAVFTP.ftp_param_decode(payload) is None

    def test_param_decode_decodes_plain_parameter_value(self) -> None:
        """A packed parameter record is decoded into its name, value, and type."""
        payload = PARAM_HEADER_STRUCT.pack(PARAM_MAGIC, 1, 1)
        payload += b"\x04\x30TEST" + struct.pack("<f", 12.5)

        result = MAVFTP.ftp_param_decode(payload)

        assert result is not None
        assert result.params == [(b"TEST", 12.5, 4)]
        assert result.defaults is None

    def test_param_decode_accepts_subset_response(self) -> None:
        """A subset response has fewer transmitted parameters than the total count."""
        payload = PARAM_HEADER_STRUCT.pack(PARAM_MAGIC, 1, 2)
        payload += b"\x04\x30TEST" + struct.pack("<f", 12.5)

        result = MAVFTP.ftp_param_decode(payload)

        assert result is not None
        assert result.params == [(b"TEST", 12.5, 4)]

    def test_param_decode_decodes_explicit_default_value(self) -> None:
        """A defaults record keeps the transmitted default value."""
        payload = PARAM_HEADER_STRUCT.pack(PARAM_MAGIC_WITH_DEFAULTS, 1, 1)
        payload += b"\x14\x30RATE" + struct.pack("<ff", 12.5, 10.0)

        result = MAVFTP.ftp_param_decode(payload)

        assert result is not None
        assert result.params == [(b"RATE", 12.5, 4)]
        assert result.defaults == [(b"RATE", 10.0, 4)]

    def test_param_decode_handles_shared_names_and_padding(self) -> None:
        """Padding and a shared name prefix are ignored and reconstructed correctly."""
        payload = PARAM_HEADER_STRUCT.pack(PARAM_MAGIC, 2, 2)
        payload += b"\x01\x20FOO" + struct.pack("<b", 1)
        payload += b"\x00\x00\x01\x02B" + struct.pack("<b", 2)

        result = MAVFTP.ftp_param_decode(payload)

        assert result is not None
        assert result.params == [(b"FOO", 1, 1), (b"FOB", 2, 1)]

    def test_param_decode_rejects_invalid_shared_name_prefix(self) -> None:
        """A record cannot reference more prefix bytes than its predecessor contains."""
        payload = PARAM_HEADER_STRUCT.pack(PARAM_MAGIC, 1, 1) + b"\x01\x0fA\x05"

        assert MAVFTP.ftp_param_decode(payload) is None

    def test_param_decode_rejects_truncated_parameter_header(self) -> None:
        """
        A packed parameter file with an incomplete record header is rejected.

        GIVEN: A valid packed-parameter file header followed by one record-header byte
        WHEN: MAVFTP decodes the parameter data
        THEN: It returns no data instead of attempting to unpack an incomplete header
        """
        # Arrange (Given): A header followed by only the parameter type byte
        payload = PARAM_HEADER_STRUCT.pack(PARAM_MAGIC, 1, 1) + b"\x01"

        # Act (When): Decode the incomplete packed parameter data
        result = MAVFTP.ftp_param_decode(payload)

        # Assert (Then): The invalid file is rejected safely
        assert result is None

    def test_getparams_read_error_returns_ftp_error_instead_of_exiting(self) -> None:
        """
        A packed parameter file read error is returned to the caller.

        GIVEN: MAVFTP supplies a parameter file handler whose read fails
        WHEN: The parameter download callback processes the file
        THEN: It returns an FTP failure rather than terminating the application
        """
        # Arrange (Given): A file handler that cannot be read
        unreadable_file = Mock()
        unreadable_file.read.side_effect = OSError("read failed")
        self.mav_ftp.cmd_get = Mock()
        self.mav_ftp.cmd_get.side_effect = lambda _args, callback, **_kwargs: callback(unreadable_file)

        # Act (When): Request the packed parameters
        result = self.mav_ftp.cmd_getparams(["values.param", "defaults.param"])

        # Assert (Then): The caller receives a recoverable FTP failure
        assert result.error_code == ERR_Fail

    @staticmethod
    def ftp_operation(seq: int, opcode: int, req_opcode: int, payload: bytearray) -> FTP_OP:
        return FTP_OP(
            seq=seq, session=1, opcode=opcode, size=0, req_opcode=req_opcode, burst_complete=0, offset=0, payload=payload
        )

    def test_decode_ftp_ack_and_nack(self) -> None:
        # Test cases grouped by expected outcome
        test_cases = [
            {
                "name": "Successful Operation",
                "op": self.ftp_operation(seq=1, opcode=OP_Ack, req_opcode=OP_ListDirectory, payload=None),
                "expected_message": "ListDirectory succeeded",
            },
            {
                "name": "Generic Failure",
                "op": self.ftp_operation(seq=2, opcode=OP_Nack, req_opcode=OP_ListDirectory, payload=bytes([ERR_Fail])),
                "expected_message": "ListDirectory failed, generic error",
            },
            {
                "name": "System Error",
                "op": self.ftp_operation(
                    seq=3, opcode=OP_Nack, req_opcode=OP_ListDirectory, payload=bytes([ERR_FailErrno, 1])
                ),  # System error 1
                "expected_message": "ListDirectory failed, system error 1",
            },
            {
                "name": "Invalid Data Size",
                "op": self.ftp_operation(
                    seq=4, opcode=OP_Nack, req_opcode=OP_ListDirectory, payload=bytes([ERR_InvalidDataSize])
                ),
                "expected_message": "ListDirectory failed, invalid data size",
            },
            {
                "name": "Invalid Session",
                "op": self.ftp_operation(
                    seq=5, opcode=OP_Nack, req_opcode=OP_ListDirectory, payload=bytes([ERR_InvalidSession])
                ),
                "expected_message": "ListDirectory failed, session is not currently open",
            },
            {
                "name": "No Sessions Available",
                "op": self.ftp_operation(
                    seq=6, opcode=OP_Nack, req_opcode=OP_ListDirectory, payload=bytes([ERR_NoSessionsAvailable])
                ),
                "expected_message": "ListDirectory failed, no sessions available",
            },
            {
                "name": "End of File",
                "op": self.ftp_operation(seq=7, opcode=OP_Nack, req_opcode=OP_ListDirectory, payload=bytes([ERR_EndOfFile])),
                "expected_message": "ListDirectory failed, offset past end of file",
            },
            {
                "name": "Unknown Command",
                "op": self.ftp_operation(
                    seq=8, opcode=OP_Nack, req_opcode=OP_ListDirectory, payload=bytes([ERR_UnknownCommand])
                ),
                "expected_message": "ListDirectory failed, unknown command",
            },
            {
                "name": "File Exists",
                "op": self.ftp_operation(seq=9, opcode=OP_Nack, req_opcode=OP_ListDirectory, payload=bytes([ERR_FileExists])),
                "expected_message": "ListDirectory failed, file/directory already exists",
            },
            {
                "name": "File Protected",
                "op": self.ftp_operation(
                    seq=10, opcode=OP_Nack, req_opcode=OP_ListDirectory, payload=bytes([ERR_FileProtected])
                ),
                "expected_message": "ListDirectory failed, file/directory is protected",
            },
            {
                "name": "File Not Found",
                "op": self.ftp_operation(
                    seq=11, opcode=OP_Nack, req_opcode=OP_ListDirectory, payload=bytes([ERR_FileNotFound])
                ),
                "expected_message": "ListDirectory failed, file/directory not found",
            },
            {
                "name": "No Error Code in Payload",
                "op": self.ftp_operation(seq=12, opcode=OP_Nack, req_opcode=OP_ListDirectory, payload=None),
                "expected_message": "ListDirectory failed, payload contains no error code",
            },
            {
                "name": "No Error Code in Nack",
                "op": self.ftp_operation(seq=13, opcode=OP_Nack, req_opcode=OP_ListDirectory, payload=bytes([ERR_None])),
                "expected_message": "ListDirectory failed, no error code",
            },
            {
                "name": "No Filesystem Error in Payload",
                "op": self.ftp_operation(seq=14, opcode=OP_Nack, req_opcode=OP_ListDirectory, payload=bytes([ERR_FailErrno])),
                "expected_message": "ListDirectory failed, file-system error missing in payload",
            },
            {
                "name": "Invalid Error Code",
                "op": self.ftp_operation(
                    seq=15, opcode=OP_Nack, req_opcode=OP_ListDirectory, payload=bytes([ERR_InvalidErrorCode])
                ),
                "expected_message": "ListDirectory failed, invalid error code",
            },
            {
                "name": "Payload Too Large",
                "op": self.ftp_operation(seq=16, opcode=OP_Nack, req_opcode=OP_ListDirectory, payload=bytes([0, 0, 0])),
                "expected_message": "ListDirectory failed, payload is too long",
            },
            {
                "name": "Invalid Opcode",
                "op": self.ftp_operation(seq=17, opcode=126, req_opcode=OP_ListDirectory, payload=None),
                "expected_message": "ListDirectory failed, invalid opcode 126",
            },
            {
                "name": "Unknown Opcode in Request",
                "op": self.ftp_operation(
                    seq=19, opcode=OP_Nack, req_opcode=OP_ListDirectory, payload=bytes([ERR_UnknownCommand])
                ),  # Assuming 100 is an unknown opcode
                "expected_message": "ListDirectory failed, unknown command",
            },
            {
                "name": "Payload with System Error",
                "op": self.ftp_operation(
                    seq=20, opcode=OP_Nack, req_opcode=OP_ListDirectory, payload=bytes([ERR_FailErrno, 2])
                ),  # System error 2
                "expected_message": "ListDirectory failed, system error 2",
            },
            {
                "name": "Invalid Error Code in Payload",
                "op": self.ftp_operation(
                    seq=21, opcode=OP_Nack, req_opcode=OP_ListDirectory, payload=bytes([105])
                ),  # Assuming 105 is an invalid error code
                "expected_message": "ListDirectory failed, invalid error code 105",
            },
            {
                "name": "Invalid Opcode with Payload",
                "op": self.ftp_operation(
                    seq=23, opcode=126, req_opcode=OP_ReadFile, payload=bytes([1, 1])
                ),  # Invalid opcode with payload
                "expected_message": "ReadFile failed, invalid opcode 126",
            },
            # Add more test cases as needed...
        ]

        for case in test_cases:
            ret = self.mav_ftp._MAVFTP__decode_ftp_ack_and_nack(case["op"])  # pylint: disable=protected-access
            ret.display_message()
            log_output = self.log_stream.getvalue().strip()
            expected_message = str(case["expected_message"])
            assert expected_message in log_output, (
                f"Test {case['name']}: Expected {case['expected_message']} but got {log_output}"
            )
            self.log_stream.seek(0)
            self.log_stream.truncate(0)

        # Invalid Arguments
        ret = MAVFTPReturn("Command arguments", ERR_InvalidArguments)
        ret.display_message()
        log_output = self.log_stream.getvalue().strip()
        assert "Command arguments failed, invalid arguments" in log_output, "Expected invalid arguments message"
        self.log_stream.seek(0)
        self.log_stream.truncate(0)

        # Test for unknown error code in display_message
        op = self.ftp_operation(seq=22, opcode=OP_Nack, req_opcode=OP_ListDirectory, payload=bytes([255]))
        ret = self.mav_ftp._MAVFTP__decode_ftp_ack_and_nack(op, "ListDirectory")  # pylint: disable=protected-access
        ret.error_code = 125  # Set error code to 125 to trigger unknown error message
        ret.display_message()
        log_output = self.log_stream.getvalue().strip()
        assert "ListDirectory failed, unknown error 125 in display_message()" in log_output, (
            "Expected unknown error message for unknown error code"
        )
        self.log_stream.seek(0)
        self.log_stream.truncate(0)

        # Put already in progress
        ret = MAVFTPReturn("Put", ERR_PutAlreadyInProgress)
        ret.display_message()
        log_output = self.log_stream.getvalue().strip()
        assert "Put failed, put already in progress" in log_output, "Expected put already in progress message"
        self.log_stream.seek(0)
        self.log_stream.truncate(0)

        # Fail to open local file
        ret = MAVFTPReturn("Put", ERR_FailToOpenLocalFile)
        ret.display_message()
        log_output = self.log_stream.getvalue().strip()
        assert "Put failed, failed to open local file" in log_output, "Expected fail to open local file message"
        self.log_stream.seek(0)
        self.log_stream.truncate(0)

        # Remote Reply Timeout
        ret = MAVFTPReturn("Put", ERR_RemoteReplyTimeout)
        ret.display_message()
        log_output = self.log_stream.getvalue().strip()
        assert "Put failed, remote reply timeout" in log_output, "Expected remote reply timeout message"
        self.log_stream.seek(0)
        self.log_stream.truncate(0)


class TestMAVFTPWritePathCrashes(unittest.TestCase):
    """Test MAVFTP write path crash fixes."""

    def setUp(self) -> None:
        self.mock_master = mavutil.mavlink_connection(device="udp:localhost:0", source_system=1)
        self.mav_ftp = MAVFTP(self.mock_master, target_system=1, target_component=1)

    def test_send_more_writes_none_write_list_does_not_crash(self) -> None:
        """Bug fix: len(None) TypeError when write_list is None."""
        self.mav_ftp.write_list = None
        try:
            self.mav_ftp._MAVFTP__send_more_writes()  # pylint: disable=protected-access
        except TypeError as e:
            self.fail(f"__send_more_writes raised TypeError with None write_list: {e}")

    def test_handle_write_reply_empty_file_does_not_crash(self) -> None:
        """Bug fix: ZeroDivisionError when uploading empty file (write_total=0)."""
        self.mav_ftp.write_total = 0
        self.mav_ftp.write_block_size = 239
        self.mav_ftp.write_list = set()
        self.mav_ftp.write_recv_idx = -1
        self.mav_ftp.write_pending = 0
        self.mav_ftp.write_acks = 0
        self.mav_ftp.put_callback_progress = None
        op = FTP_OP(seq=1, session=1, opcode=OP_Ack, size=0, req_opcode=0, burst_complete=0, offset=0, payload=None)
        try:
            self.mav_ftp._MAVFTP__handle_write_reply(op, None)  # pylint: disable=protected-access
        except ZeroDivisionError as e:
            self.fail(f"__handle_write_reply raised ZeroDivisionError for empty file: {e}")

    def test_send_more_writes_none_guard_at_line_886(self) -> None:
        """Bug fix: Missing None guard before len(write_list) at line 886."""
        self.mav_ftp.write_list = None
        self.mav_ftp.write_file_size = 0
        try:
            self.mav_ftp._MAVFTP__send_more_writes()  # pylint: disable=protected-access
        except TypeError as e:
            self.fail(f"__send_more_writes raised TypeError at len(write_list) guard: {e}")


if __name__ == "__main__":
    unittest.main()
