#!/usr/bin/env python3

'''
MAVLink File Transfer Protocol support test - https://mavlink.io/en/services/ftp.html

This file is part of Ardupilot methodic configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024 Amilcar Lucas

SPDX-License-Identifier: GPL-3.0-or-later
'''

import unittest
#from unittest.mock import patch
from io import StringIO
import logging
from pymavlink import mavutil
from backend_mavftp import FTP_OP, MAVFTP, MAVFTPReturn

from backend_mavftp import OP_ListDirectory
from backend_mavftp import OP_ReadFile
from backend_mavftp import OP_Ack
from backend_mavftp import OP_Nack
from backend_mavftp import ERR_None
from backend_mavftp import ERR_Fail
from backend_mavftp import ERR_FailErrno
from backend_mavftp import ERR_InvalidDataSize
from backend_mavftp import ERR_InvalidSession
from backend_mavftp import ERR_NoSessionsAvailable
from backend_mavftp import ERR_EndOfFile
from backend_mavftp import ERR_UnknownCommand
from backend_mavftp import ERR_FileExists
from backend_mavftp import ERR_FileProtected
from backend_mavftp import ERR_FileNotFound
#from backend_mavftp import ERR_NoErrorCodeInPayload
#from backend_mavftp import ERR_NoErrorCodeInNack
#from backend_mavftp import ERR_NoFilesystemErrorInPayload
from backend_mavftp import ERR_InvalidErrorCode
#from backend_mavftp import ERR_PayloadTooLarge
#from backend_mavftp import ERR_InvalidOpcode
from backend_mavftp import ERR_InvalidArguments
from backend_mavftp import ERR_PutAlreadyInProgress
from backend_mavftp import ERR_FailToOpenLocalFile
from backend_mavftp import ERR_RemoteReplyTimeout


class TestMAVFTPPayloadDecoding(unittest.TestCase):
    """Test MAVFTP payload decoding"""

    def setUp(self):
        self.log_stream = StringIO()
        logging.basicConfig(stream=self.log_stream, level=logging.DEBUG, format='%(levelname)s: %(message)s')

        # Mock mavutil.mavlink_connection to simulate a connection
        self.mock_master = mavutil.mavlink_connection(device="udp:localhost:14550", source_system=1)

        # Initialize MAVFTP instance for testing
        self.mav_ftp = MAVFTP(self.mock_master, target_system=1, target_component=1)

    def tearDown(self):
        self.log_stream.seek(0)
        self.log_stream.truncate(0)

    def test_decode_ftp_ack_and_nack(self):
        # Test cases grouped by expected outcome
# pylint: disable=line-too-long
        test_cases = [
            {
                "name": "Successful Operation",
                "op": FTP_OP(seq=1, session=1, opcode=OP_Ack, size=0, req_opcode=OP_ListDirectory, burst_complete=0, offset=0, payload=None),
                "expected_message": "ListDirectory succeeded"
            },
            {
                "name": "Generic Failure",
                "op": FTP_OP(seq=2, session=1, opcode=OP_Nack, size=0, req_opcode=OP_ListDirectory, burst_complete=0, offset=0, payload=bytes([ERR_Fail])),
                "expected_message": "ListDirectory failed, generic error"
            },
            {
                "name": "System Error",
                "op": FTP_OP(seq=3, session=1, opcode=OP_Nack, size=0, req_opcode=OP_ListDirectory, burst_complete=0, offset=0, payload=bytes([ERR_FailErrno, 1])),  # System error 1
                "expected_message": "ListDirectory failed, system error 1"
            },
            {
                "name": "Invalid Data Size",
                "op": FTP_OP(seq=4, session=1, opcode=OP_Nack, size=0, req_opcode=OP_ListDirectory, burst_complete=0, offset=0, payload=bytes([ERR_InvalidDataSize])),
                "expected_message": "ListDirectory failed, invalid data size"
            },
            {
                "name": "Invalid Session",
                "op": FTP_OP(seq=5, session=1, opcode=OP_Nack, size=0, req_opcode=OP_ListDirectory, burst_complete=0, offset=0, payload=bytes([ERR_InvalidSession])),
                "expected_message": "ListDirectory failed, session is not currently open"
            },
            {
                "name": "No Sessions Available",
                "op": FTP_OP(seq=6, session=1, opcode=OP_Nack, size=0, req_opcode=OP_ListDirectory, burst_complete=0, offset=0, payload=bytes([ERR_NoSessionsAvailable])),
                "expected_message": "ListDirectory failed, no sessions available"
            },
            {
                "name": "End of File",
                "op": FTP_OP(seq=7, session=1, opcode=OP_Nack, size=0, req_opcode=OP_ListDirectory, burst_complete=0, offset=0, payload=bytes([ERR_EndOfFile])),
                "expected_message": "ListDirectory failed, offset past end of file"
            },
            {
                "name": "Unknown Command",
                "op": FTP_OP(seq=8, session=1, opcode=OP_Nack, size=0, req_opcode=OP_ListDirectory, burst_complete=0, offset=0, payload=bytes([ERR_UnknownCommand])),
                "expected_message": "ListDirectory failed, unknown command"
            },
            {
                "name": "File Exists",
                "op": FTP_OP(seq=9, session=1, opcode=OP_Nack, size=0, req_opcode=OP_ListDirectory, burst_complete=0, offset=0, payload=bytes([ERR_FileExists])),
                "expected_message": "ListDirectory failed, file/directory already exists"
            },
            {
                "name": "File Protected",
                "op": FTP_OP(seq=10, session=1, opcode=OP_Nack, size=0, req_opcode=OP_ListDirectory, burst_complete=0, offset=0, payload=bytes([ERR_FileProtected])),
                "expected_message": "ListDirectory failed, file/directory is protected"
            },
            {
                "name": "File Not Found",
                "op": FTP_OP(seq=11, session=1, opcode=OP_Nack, size=0, req_opcode=OP_ListDirectory, burst_complete=0, offset=0, payload=bytes([ERR_FileNotFound])),
                "expected_message": "ListDirectory failed, file/directory not found"
            },
            {
                "name": "No Error Code in Payload",
                "op": FTP_OP(seq=12, session=1, opcode=OP_Nack, size=0, req_opcode=OP_ListDirectory, burst_complete=0, offset=0, payload=None),
                "expected_message": "ListDirectory failed, payload contains no error code"
            },
            {
                "name": "No Error Code in Nack",
                "op": FTP_OP(seq=13, session=1, opcode=OP_Nack, size=0, req_opcode=OP_ListDirectory, burst_complete=0, offset=0, payload=bytes([ERR_None])),
                "expected_message": "ListDirectory failed, no error code"
            },
            {
                "name": "No Filesystem Error in Payload",
                "op": FTP_OP(seq=14, session=1, opcode=OP_Nack, size=0, req_opcode=OP_ListDirectory, burst_complete=0, offset=0, payload=bytes([ERR_FailErrno])),
                "expected_message": "ListDirectory failed, file-system error missing in payload"
            },
            {
                "name": "Invalid Error Code",
                "op": FTP_OP(seq=15, session=1, opcode=OP_Nack, size=0, req_opcode=OP_ListDirectory, burst_complete=0, offset=0, payload=bytes([ERR_InvalidErrorCode])),
                "expected_message": "ListDirectory failed, invalid error code"
            },
            {
                "name": "Payload Too Large",
                "op": FTP_OP(seq=16, session=1, opcode=OP_Nack, size=0, req_opcode=OP_ListDirectory, burst_complete=0, offset=0, payload=bytes([0, 0, 0])),
                "expected_message": "ListDirectory failed, payload is too long"
            },
            {
                "name": "Invalid Opcode",
                "op": FTP_OP(seq=17, session=1, opcode=126, size=0, req_opcode=OP_ListDirectory, burst_complete=0, offset=0, payload=None),
                "expected_message": "ListDirectory failed, invalid opcode 126"
            },
            {
                "name": "Unknown Opcode in Request",
                "op": FTP_OP(seq=19, session=1, opcode=OP_Nack, size=0, req_opcode=OP_ListDirectory, burst_complete=0, offset=0, payload=bytes([ERR_UnknownCommand])),  # Assuming 100 is an unknown opcode
                "expected_message": "ListDirectory failed, unknown command"
            },
            {
                "name": "Payload with System Error",
                "op": FTP_OP(seq=20, session=1, opcode=OP_Nack, size=0, req_opcode=OP_ListDirectory, burst_complete=0, offset=0, payload=bytes([ERR_FailErrno, 2])),  # System error 2
                "expected_message": "ListDirectory failed, system error 2"
            },
            {
                "name": "Invalid Error Code in Payload",
                "op": FTP_OP(seq=21, session=1, opcode=OP_Nack, size=0, req_opcode=OP_ListDirectory, burst_complete=0, offset=0, payload=bytes([105])),  # Assuming 105 is an invalid error code
                "expected_message": "ListDirectory failed, invalid error code 105"
            },
            {
                "name": "Invalid Opcode with Payload",
                "op": FTP_OP(seq=23, session=1, opcode=126, size=0, req_opcode=OP_ReadFile, burst_complete=0, offset=0, payload=bytes([1, 1])),  # Invalid opcode with payload
                "expected_message": "ReadFile failed, invalid opcode 126"
            },
            # Add more test cases as needed...
        ]
# pylint: enable=line-too-long

        for case in test_cases:
            ret = self.mav_ftp._MAVFTP__decode_ftp_ack_and_nack(case['op'])  # pylint: disable=protected-access
            ret.display_message()
            log_output = self.log_stream.getvalue().strip()
            self.assertIn(case["expected_message"], log_output,
                          f"Test {case['name']}: Expected {case['expected_message']} but got {log_output}")
            self.log_stream.seek(0)
            self.log_stream.truncate(0)

        # Invalid Arguments
        ret = MAVFTPReturn("Command arguments", ERR_InvalidArguments)
        ret.display_message()
        log_output = self.log_stream.getvalue().strip()
        self.assertIn("Command arguments failed, invalid arguments", log_output, "Expected invalid arguments message")
        self.log_stream.seek(0)
        self.log_stream.truncate(0)

        # Test for unknown error code in display_message
        op = FTP_OP(seq=22, session=1, opcode=OP_Nack, size=0, req_opcode=OP_ListDirectory, burst_complete=0, offset=0,
                    payload=bytes([255]))
        ret = self.mav_ftp._MAVFTP__decode_ftp_ack_and_nack(op, "ListDirectory")  # pylint: disable=protected-access
        ret.error_code = 125  # Set error code to 125 to trigger unknown error message
        ret.display_message()
        log_output = self.log_stream.getvalue().strip()
        self.assertIn("ListDirectory failed, unknown error 125 in display_message()", log_output,
                      "Expected unknown error message for unknown error code")
        self.log_stream.seek(0)
        self.log_stream.truncate(0)

        # Put already in progress
        ret = MAVFTPReturn("Put", ERR_PutAlreadyInProgress)
        ret.display_message()
        log_output = self.log_stream.getvalue().strip()
        self.assertIn("Put failed, put already in progress", log_output, "Expected put already in progress message")
        self.log_stream.seek(0)
        self.log_stream.truncate(0)

        # Fail to open local file
        ret = MAVFTPReturn("Put", ERR_FailToOpenLocalFile)
        ret.display_message()
        log_output = self.log_stream.getvalue().strip()
        self.assertIn("Put failed, failed to open local file", log_output, "Expected fail to open local file message")
        self.log_stream.seek(0)
        self.log_stream.truncate(0)

        # Remote Reply Timeout
        ret = MAVFTPReturn("Put", ERR_RemoteReplyTimeout)
        ret.display_message()
        log_output = self.log_stream.getvalue().strip()
        self.assertIn("Put failed, remote reply timeout", log_output, "Expected remote reply timeout message")
        self.log_stream.seek(0)
        self.log_stream.truncate(0)


if __name__ == '__main__':
    unittest.main()