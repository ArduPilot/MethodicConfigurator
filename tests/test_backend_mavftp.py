#!/usr/bin/env python3

"""
Tests backend_mavftp.py file.

MAVLink File Transfer Protocol support test - https://mavlink.io/en/services/ftp.html

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2026 Amilcar Lucas

SPDX-License-Identifier: GPL-3.0-or-later
"""

import logging
import socket
import struct
import unittest

# from unittest.mock import patch
from io import BytesIO, StringIO
from types import SimpleNamespace
from unittest.mock import Mock, patch

from pymavlink import mavutil

# pylint: disable=too-many-lines
# from ardupilot_methodic_configurator.backend_mavftp import FtpError
from ardupilot_methodic_configurator.backend_mavftp import (
    FTP_OP,
    MAVFTP,
    FtpError,
    MAVFTPReturn,
    OP_Ack,
    OP_BurstReadFile,
    OP_ListDirectory,
    OP_Nack,
    OP_ReadFile,
    OP_ResetSessions,
    OP_TerminateSession,
    create_argument_parser,
)

PARAM_HEADER_STRUCT = struct.Struct("<HHH")
PARAM_MAGIC = 0x671B
PARAM_MAGIC_WITH_DEFAULTS = 0x671C


class TestMAVFTPPayloadDecoding(unittest.TestCase):  # pylint: disable=too-many-public-methods
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

        assert result.error_code == FtpError.Fail

    def test_successful_callback_does_not_write_virtual_remote_path(self) -> None:
        """A callback consumes the download without creating a local remote-path file."""
        self.mav_ftp.fh = BytesIO(b"data")
        self.mav_ftp.filename = "param.pck?withdefaults=1"
        self.mav_ftp.op_start = 1.0
        self.mav_ftp.read_gaps = []
        self.mav_ftp.reached_eof = True
        self.mav_ftp.read_total = 4
        self.mav_ftp.requested_offset = 0
        self.mav_ftp.requested_size = 4
        self.mav_ftp.callback = lambda _file: MAVFTPReturn("GetParams", FtpError.Success)

        with patch("builtins.open", side_effect=AssertionError("callback data must not be published as a file")):
            assert self.mav_ftp._MAVFTP__check_read_finished()  # pylint: disable=protected-access

    def test_foreign_malformed_reply_is_not_reported_as_local_invalid_data(self) -> None:
        """Malformed foreign traffic is ignored so a following local reply succeeds."""
        foreign_packet = Mock()
        foreign_packet.get_type.return_value = "FILE_TRANSFER_PROTOCOL"
        foreign_packet.target_system = 2
        foreign_packet.target_component = 1
        foreign_packet.payload = b"malformed"
        local_packet = Mock()
        local_packet.get_type.return_value = "FILE_TRANSFER_PROTOCOL"
        local_packet.get_srcSystem.return_value = 1
        local_packet.get_srcComponent.return_value = 1
        local_packet.target_system = 1
        local_packet.target_component = 1
        self.mav_ftp.master.source_system = 1
        self.mav_ftp.master.source_component = 1
        self.mav_ftp.last_op = FTP_OP(
            seq=0,
            session=self.mav_ftp.session,
            opcode=OP_ResetSessions,
            size=0,
            req_opcode=0,
            burst_complete=0,
            offset=0,
            payload=None,
        )
        # pylint: disable=duplicate-code
        local_reply = FTP_OP(
            seq=1,
            session=self.mav_ftp.session,
            opcode=OP_Ack,
            size=0,
            req_opcode=OP_ResetSessions,
            burst_complete=0,
            offset=0,
            payload=None,
        )
        # pylint: enable=duplicate-code

        def parse_packet(packet: Mock) -> FTP_OP:
            if packet is foreign_packet:
                error = "malformed foreign packet"
                raise struct.error(error)
            return local_reply

        def receive_packet(packet: Mock) -> MAVFTPReturn:
            if packet is local_packet:
                self.mav_ftp.read_complete = True
            return MAVFTPReturn("mavlink_packet", FtpError.Success)

        with (
            patch.object(self.mav_ftp.master, "recv_match", side_effect=[foreign_packet, local_packet]),
            patch.object(self.mav_ftp, "_MAVFTP__op_parse", side_effect=parse_packet),
            patch.object(self.mav_ftp, "_MAVFTP__receive_packet", side_effect=receive_packet),
            patch.object(self.mav_ftp, "_MAVFTP__idle_task", return_value=False),
        ):
            result = self.mav_ftp.process_ftp_reply("get", timeout=1)

        assert result.error_code == FtpError.Success

    def test_wrong_vehicle_malformed_reply_is_not_reported_as_local_invalid_data(self) -> None:
        """Malformed traffic from another vehicle is ignored before FTP parsing."""
        foreign_packet = Mock()
        foreign_packet.get_type.return_value = "FILE_TRANSFER_PROTOCOL"
        foreign_packet.get_srcSystem.return_value = 2
        foreign_packet.get_srcComponent.return_value = 1
        foreign_packet.target_system = 1
        foreign_packet.target_component = 1
        foreign_packet.payload = b"malformed"
        local_packet = Mock()
        local_packet.get_type.return_value = "FILE_TRANSFER_PROTOCOL"
        local_packet.get_srcSystem.return_value = 1
        local_packet.get_srcComponent.return_value = 1
        local_packet.target_system = 1
        local_packet.target_component = 1
        self.mav_ftp.master.source_system = 1
        self.mav_ftp.master.source_component = 1
        self.mav_ftp.last_op = FTP_OP(
            seq=0,
            session=self.mav_ftp.session,
            opcode=OP_ResetSessions,
            size=0,
            req_opcode=0,
            burst_complete=0,
            offset=0,
            payload=None,
        )
        # pylint: disable=duplicate-code
        local_reply = FTP_OP(
            seq=1,
            session=self.mav_ftp.session,
            opcode=OP_Ack,
            size=0,
            req_opcode=OP_ResetSessions,
            burst_complete=0,
            offset=0,
            payload=None,
        )
        # pylint: enable=duplicate-code
        local_packet.payload = local_reply.pack()

        with (
            patch.object(
                self.mav_ftp.master,
                "recv_match",
                side_effect=[foreign_packet, local_packet],
            ),
            patch.object(self.mav_ftp, "_MAVFTP__idle_task", return_value=False),
        ):
            result = self.mav_ftp.process_ftp_reply("ResetSessions", timeout=1)

        assert result.error_code == FtpError.Success

    def test_delayed_wrong_vehicle_malformed_reply_is_not_reported_as_local_invalid_data(self) -> None:
        """The delayed receive path filters the vehicle before parsing payloads."""
        foreign_packet = Mock()
        foreign_packet.get_type.return_value = "FILE_TRANSFER_PROTOCOL"
        foreign_packet.get_srcSystem.return_value = 2
        foreign_packet.get_srcComponent.return_value = 1
        foreign_packet.target_system = 1
        foreign_packet.target_component = 1
        foreign_packet.payload = b"malformed"
        local_packet = Mock()
        local_packet.get_type.return_value = "FILE_TRANSFER_PROTOCOL"
        local_packet.get_srcSystem.return_value = 1
        local_packet.get_srcComponent.return_value = 1
        local_packet.target_system = 1
        local_packet.target_component = 1
        # pylint: disable=duplicate-code
        local_packet.payload = FTP_OP(
            seq=1,
            session=self.mav_ftp.session,
            opcode=OP_Ack,
            size=0,
            req_opcode=OP_ResetSessions,
            burst_complete=0,
            offset=0,
            payload=None,
        ).pack()
        # pylint: enable=duplicate-code
        self.mav_ftp.master.source_system = 1
        self.mav_ftp.master.source_component = 1
        self.mav_ftp.last_op = FTP_OP(
            seq=0,
            session=self.mav_ftp.session,
            opcode=OP_ResetSessions,
            size=0,
            req_opcode=0,
            burst_complete=0,
            offset=0,
            payload=None,
        )
        self.mav_ftp.ftp_settings.pkt_lag_rx = 1.0

        with (
            patch(
                "ardupilot_methodic_configurator.backend_mavftp.time.monotonic",
                side_effect=[0.0, 0.0, 0.0, 1.0],
            ),
            patch.object(
                self.mav_ftp.master,
                "recv_match",
                side_effect=[foreign_packet, local_packet, None],
            ),
            patch.object(self.mav_ftp, "_MAVFTP__idle_task", return_value=False),
        ):
            result = self.mav_ftp.process_ftp_reply("ResetSessions", timeout=1)

        assert result.error_code == FtpError.Success

    def test_read_renews_deadline_when_idle_flush_accepts_delayed_reply(self) -> None:
        """A delayed reply accepted by idle_task must extend read's deadline."""
        idle_calls = 0

        def idle_task() -> None:
            nonlocal idle_calls
            idle_calls += 1
            if idle_calls == 1:
                self.mav_ftp.accepted_reply_generation += 1
            elif idle_calls == 3:
                self.mav_ftp.done = True

        with (
            patch.object(self.mav_ftp, "_MAVFTP__send"),
            patch.object(self.mav_ftp.master, "recv_match", return_value=None) as recv_match,
            patch.object(self.mav_ftp, "idle_task", side_effect=idle_task) as idle,
            patch("ardupilot_methodic_configurator.backend_mavftp.logging.info"),
            patch(
                "ardupilot_methodic_configurator.backend_mavftp.time.time",
                side_effect=[0.0, 0.0, 1.0, 2.0, 6.0, 6.5],
            ),
        ):
            self.mav_ftp.read("remote.bin", 1)

        assert idle.call_count == 3
        assert recv_match.call_count == 3

    def test_duplicate_burst_reply_does_not_count_as_progress(self) -> None:
        """A duplicate burst packet must not renew read progress or stall time."""
        self.mav_ftp.master.source_system = 1
        self.mav_ftp.master.source_component = 1
        self.mav_ftp.fh = BytesIO()
        self.mav_ftp.filename = "remote.bin"
        self.mav_ftp.read_to_memory = True
        self.mav_ftp.requested_offset = 0
        self.mav_ftp.requested_size = 2
        self.mav_ftp.burst_size = 239
        self.mav_ftp.session = 1
        self.mav_ftp.pending_burst_seq = 1
        self.mav_ftp.pending_burst_offset = 0
        reply = FTP_OP(
            seq=1,
            session=1,
            opcode=OP_Ack,
            size=1,
            req_opcode=OP_BurstReadFile,
            burst_complete=0,
            offset=0,
            payload=b"x",
        )
        packet = Mock()
        packet.get_type.return_value = "FILE_TRANSFER_PROTOCOL"
        packet.get_srcSystem.return_value = 1
        packet.get_srcComponent.return_value = 1
        packet.target_system = 1
        packet.target_component = 1
        packet.payload = reply.pack()

        first_result = self.mav_ftp.mavlink_packet(packet)
        generation_after_first = self.mav_ftp.accepted_reply_generation
        last_burst_after_first = self.mav_ftp.last_burst_read
        second_result = self.mav_ftp.mavlink_packet(packet)

        assert first_result is not None
        assert first_result.error_code == FtpError.Success
        assert second_result is not None
        assert second_result.error_code == FtpError.Fail
        assert generation_after_first == 1
        assert self.mav_ftp.accepted_reply_generation == generation_after_first
        assert self.mav_ftp.last_burst_read == last_burst_after_first
        assert self.mav_ftp.duplicates == 1

    def test_zero_byte_advancing_burst_does_not_count_gap_creation_as_progress(self) -> None:
        """An empty out-of-order burst reply must not renew the read deadline."""
        self.mav_ftp.master.source_system = 1
        self.mav_ftp.master.source_component = 1
        self.mav_ftp.fh = BytesIO()
        self.mav_ftp.filename = "remote.bin"
        self.mav_ftp.read_to_memory = True
        self.mav_ftp.requested_offset = 0
        self.mav_ftp.requested_size = 2
        self.mav_ftp.burst_size = 239
        self.mav_ftp.session = 1
        self.mav_ftp.pending_burst_seq = 1
        self.mav_ftp.pending_burst_offset = 0
        self.mav_ftp.last_burst_read = 10.0
        reply = FTP_OP(
            seq=1,
            session=1,
            opcode=OP_Ack,
            size=0,
            req_opcode=OP_BurstReadFile,
            burst_complete=0,
            offset=1,
            payload=b"",
        )
        packet = Mock()
        packet.get_type.return_value = "FILE_TRANSFER_PROTOCOL"
        packet.get_srcSystem.return_value = 1
        packet.get_srcComponent.return_value = 1
        packet.target_system = 1
        packet.target_component = 1
        packet.payload = reply.pack()

        result = self.mav_ftp.mavlink_packet(packet)

        assert result is not None
        assert result.error_code == FtpError.Success
        assert self.mav_ftp.read_total == 0
        assert self.mav_ftp.reached_eof is False
        assert len(self.mav_ftp.read_gaps) == 1
        assert self.mav_ftp.accepted_reply_generation == 0
        assert self.mav_ftp.last_burst_read == 10.0

    def test_termination_cleanup_does_not_count_as_read_progress(self) -> None:
        """Resetting EOF during cleanup must not advance burst progress."""
        self.mav_ftp.master.source_system = 1
        self.mav_ftp.master.source_component = 1
        self.mav_ftp.fh = BytesIO()
        self.mav_ftp.filename = "remote.bin"
        self.mav_ftp.session = 1
        self.mav_ftp.pending_burst_seq = 1
        self.mav_ftp.pending_burst_offset = 0
        self.mav_ftp.reached_eof = True
        reply = FTP_OP(
            seq=1,
            session=1,
            opcode=OP_Ack,
            size=0,
            req_opcode=OP_BurstReadFile,
            burst_complete=0,
            offset=0,
            payload=b"",
        )
        packet = Mock()
        packet.get_type.return_value = "FILE_TRANSFER_PROTOCOL"
        packet.get_srcSystem.return_value = 1
        packet.get_srcComponent.return_value = 1
        packet.target_system = 1
        packet.target_component = 1
        packet.payload = reply.pack()

        def cleanup(_op: FTP_OP, _message: Mock) -> MAVFTPReturn:
            self.mav_ftp.reached_eof = False
            return MAVFTPReturn("BurstReadFile", FtpError.Success)

        with patch.object(self.mav_ftp, "_MAVFTP__handle_burst_read", side_effect=cleanup):
            result = self.mav_ftp.mavlink_packet(packet)

        assert result is not None
        assert result.error_code == FtpError.Success
        assert self.mav_ftp.accepted_reply_generation == 0

    def test_callback_can_close_download_buffer(self) -> None:
        """A download callback may close its buffer before completion cleanup."""
        self.mav_ftp.fh = BytesIO(b"data")
        self.mav_ftp.filename = "param.pck?withdefaults=1"
        self.mav_ftp.op_start = 1.0
        self.mav_ftp.read_gaps = []
        self.mav_ftp.reached_eof = True
        self.mav_ftp.read_total = 4
        self.mav_ftp.requested_offset = 0
        self.mav_ftp.requested_size = 4

        def consume_and_close(file_handle: BytesIO) -> MAVFTPReturn:
            file_handle.close()
            return MAVFTPReturn("GetParams", FtpError.Success)

        self.mav_ftp.callback = consume_and_close

        with patch.object(self.mav_ftp, "_MAVFTP__terminate_session") as terminate:
            assert self.mav_ftp._MAVFTP__check_read_finished()  # pylint: disable=protected-access

        terminate.assert_called_once()
        assert self.mav_ftp.read_complete
        assert self.mav_ftp.callback_failure is None

    def test_delayed_foreign_terminate_reply_does_not_count_as_accepted(self) -> None:
        """A delayed terminate reply for another client must not suppress idle expiry."""
        foreign_packet = Mock()
        foreign_packet.get_type.return_value = "FILE_TRANSFER_PROTOCOL"
        foreign_packet.target_system = 2
        foreign_packet.target_component = 1
        foreign_packet.payload = FTP_OP(
            seq=1,
            session=1,
            opcode=OP_Ack,
            size=0,
            req_opcode=OP_TerminateSession,
            burst_complete=0,
            offset=0,
            payload=None,
        ).pack()
        self.mav_ftp.master.source_system = 1
        self.mav_ftp.master.source_component = 1
        self.mav_ftp.pending_terminate_seq = 1
        self.mav_ftp.rx_delay_queue = [(0.0, 1, foreign_packet)]

        with (
            patch.object(self.mav_ftp.master, "recv_match", return_value=None),
            patch.object(self.mav_ftp, "_MAVFTP__idle_task", return_value=True) as idle,
        ):
            result = self.mav_ftp.process_ftp_reply("TerminateSession", timeout=1)

        idle.assert_called_once()
        assert result.error_code == FtpError.Fail

    def test_delayed_wrong_session_terminate_reply_does_not_count_as_accepted(self) -> None:
        """A valid packet for another FTP session must not satisfy termination."""
        packet = Mock()
        packet.get_type.return_value = "FILE_TRANSFER_PROTOCOL"
        packet.get_srcSystem.return_value = 1
        packet.get_srcComponent.return_value = 1
        packet.target_system = 1
        packet.target_component = 1
        packet.payload = FTP_OP(
            seq=1,
            session=(self.mav_ftp.session + 1) % 256,
            opcode=OP_Ack,
            size=0,
            req_opcode=OP_TerminateSession,
            burst_complete=0,
            offset=0,
            payload=None,
        ).pack()
        self.mav_ftp.master.source_system = 1
        self.mav_ftp.master.source_component = 1
        self.mav_ftp.pending_terminate_seq = 0
        self.mav_ftp.rx_delay_queue = [(0.0, 1, packet)]

        with (
            patch("ardupilot_methodic_configurator.backend_mavftp.time.monotonic", return_value=1.0),
            patch.object(self.mav_ftp.master, "recv_match", return_value=None),
            patch.object(self.mav_ftp, "_MAVFTP__idle_task", return_value=True) as idle,
        ):
            result = self.mav_ftp.process_ftp_reply("TerminateSession", timeout=1)

        idle.assert_called_once()
        assert result.error_code == FtpError.Fail

    def test_burst_stall_retry_is_capped(self) -> None:
        """A stalled burst must eventually terminate instead of retrying forever."""
        self.mav_ftp.fh = BytesIO()
        self.mav_ftp.filename = "remote.bin"
        self.mav_ftp.last_burst_read = 0.0
        self.mav_ftp.pending_burst_request = FTP_OP(
            seq=0,
            session=self.mav_ftp.session,
            opcode=OP_BurstReadFile,
            size=0,
            req_opcode=0,
            burst_complete=0,
            offset=0,
            payload=None,
        )
        terminate = Mock(side_effect=lambda: setattr(self.mav_ftp, "fh", None))

        with (
            patch.object(self.mav_ftp, "_MAVFTP__send") as send,
            patch.object(self.mav_ftp, "_MAVFTP__terminate_session", terminate),
            patch(
                "ardupilot_methodic_configurator.backend_mavftp.time.time",
                side_effect=[2.0 * index for index in range(40)],
            ),
        ):
            for _ in range(30):
                self.mav_ftp._MAVFTP__idle_task()  # pylint: disable=protected-access

        assert send.call_count == 10
        terminate.assert_called_once()
        assert self.mav_ftp.read_retries == 10

    def test_completed_file_download_publishes_staging_file_without_buffering_result(self) -> None:
        """A normal download atomically publishes its staging file without a second RAM copy."""
        self.mav_ftp.fh = Mock()
        self.mav_ftp.fh.tell.return_value = 4
        self.mav_ftp.fh.fileno.return_value = 42
        self.mav_ftp.fh_owned = True
        self.mav_ftp.temp_filename = "staging.bin"
        self.mav_ftp.filename = "destination.bin"
        self.mav_ftp.op_start = 1.0
        self.mav_ftp.read_gaps = []
        self.mav_ftp.reached_eof = True
        self.mav_ftp.read_total = 4
        self.mav_ftp.requested_offset = 0
        self.mav_ftp.requested_size = 4
        self.mav_ftp.remote_size_known = True

        with (
            patch(
                "ardupilot_methodic_configurator.backend_mavftp.os.fstat",
                return_value=Mock(st_size=4),
            ),
            patch("ardupilot_methodic_configurator.backend_mavftp.os.fsync"),
            patch("ardupilot_methodic_configurator.backend_mavftp.os.replace") as replace,
            patch.object(self.mav_ftp, "_MAVFTP__terminate_session") as terminate,
        ):
            assert self.mav_ftp._MAVFTP__check_read_finished()  # pylint: disable=protected-access

        self.mav_ftp.fh.read.assert_not_called()
        self.mav_ftp.fh.close.assert_called_once()
        replace.assert_called_once_with("staging.bin", "destination.bin")
        assert self.mav_ftp.temp_filename is None
        assert self.mav_ftp.get_result is None
        terminate.assert_called_once()
        assert "Wrote 4/4 bytes to destination.bin" in self.log_stream.getvalue()

    def test_console_idle_detection_default_matches_the_established_cli_value(self) -> None:
        """The standalone MAVFTP console uses the current MAVFTP idle timeout."""
        args = create_argument_parser().parse_args(["get", "remote.bin"])

        assert args.idle_detection_time == 3.7

    def test_file_download_does_not_expose_a_stale_synchronous_read_result(self) -> None:
        """Streaming downloads clear a result left by a preceding synchronous read."""
        self.mav_ftp.get_result = b"old read result"

        with patch.object(self.mav_ftp, "_MAVFTP__send"):
            result = self.mav_ftp.cmd_get(["remote.bin"])

        assert result.error_code == FtpError.Success
        assert self.mav_ftp.get_result is None

    def test_websocket_batch_uses_link_write_for_websocket_framing(self) -> None:
        """Batched MAVLink packets must pass through the WebSocket transport wrapper."""
        port = Mock()
        port.type = socket.SOCK_STREAM
        link = Mock()
        link.port = port
        link.write.return_value = None
        mav = SimpleNamespace(file=link, file_transfer_protocol_encode=Mock())
        self.mav_ftp.master = SimpleNamespace(mav=mav)
        packets = iter((b"first", b"second"))

        def collect_packet(_operation, *, writer) -> None:
            writer.write(next(packets))

        with patch.object(
            self.mav_ftp,
            "_MAVFTP__send",
            side_effect=collect_packet,
        ):
            self.mav_ftp._MAVFTP__send_batch([Mock(), Mock()])  # pylint: disable=protected-access

        link.write.assert_called_once_with(b"firstsecond")
        port.sendall.assert_not_called()

    def test_write_payload_releases_staging_after_disk_write_failure(self) -> None:
        """A staging-file write failure terminates the transfer and reports a recoverable error."""
        self.mav_ftp.fh = Mock()
        self.mav_ftp.fh.tell.return_value = 0
        self.mav_ftp.fh.write.side_effect = OSError("disk full")
        op = FTP_OP(
            seq=1,
            session=1,
            opcode=OP_Ack,
            size=4,
            req_opcode=OP_ReadFile,
            burst_complete=0,
            offset=0,
            payload=b"data",
        )

        with patch.object(self.mav_ftp, "_MAVFTP__terminate_session") as terminate:
            assert not self.mav_ftp._MAVFTP__write_payload(op)  # pylint: disable=protected-access

        assert self.mav_ftp.callback_failure is not None
        assert self.mav_ftp.callback_failure.error_code == FtpError.Fail
        terminate.assert_called_once()

    def test_process_ftp_reply_propagates_getparams_callback_failure(self) -> None:
        """A parameter-decoding callback failure makes the transfer fail, enabling fallback."""
        callback_failure = MAVFTPReturn("GetParams", FtpError.Fail)
        packet_result = MAVFTPReturn("BurstReadFile", FtpError.Success)
        # pylint: disable=duplicate-code
        self.mav_ftp.master = Mock()
        reply = FTP_OP(
            seq=1,
            session=0,
            opcode=OP_Ack,
            size=0,
            req_opcode=OP_ResetSessions,
            burst_complete=0,
            offset=0,
            payload=None,
        )
        # pylint: enable=duplicate-code
        packet = Mock()
        packet.get_type.return_value = "FILE_TRANSFER_PROTOCOL"
        packet.get_srcSystem.return_value = 1
        packet.get_srcComponent.return_value = 1
        packet.target_system = 1
        packet.target_component = 1
        packet.payload = reply.pack()
        self.mav_ftp.master.source_system = 1
        self.mav_ftp.master.source_component = 1
        self.mav_ftp.master.recv_match.return_value = packet

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
        assert result.error_code == FtpError.Fail

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
                "op": self.ftp_operation(seq=2, opcode=OP_Nack, req_opcode=OP_ListDirectory, payload=bytes([FtpError.Fail])),
                "expected_message": "ListDirectory failed, generic error",
            },
            {
                "name": "System Error",
                "op": self.ftp_operation(
                    seq=3, opcode=OP_Nack, req_opcode=OP_ListDirectory, payload=bytes([FtpError.FailErrno, 1])
                ),  # System error 1
                "expected_message": "ListDirectory failed, system error 1",
            },
            {
                "name": "Invalid Data Size",
                "op": self.ftp_operation(
                    seq=4, opcode=OP_Nack, req_opcode=OP_ListDirectory, payload=bytes([FtpError.InvalidDataSize])
                ),
                "expected_message": "ListDirectory failed, invalid data size",
            },
            {
                "name": "Invalid Session",
                "op": self.ftp_operation(
                    seq=5, opcode=OP_Nack, req_opcode=OP_ListDirectory, payload=bytes([FtpError.InvalidSession])
                ),
                "expected_message": "ListDirectory failed, session is not currently open",
            },
            {
                "name": "No Sessions Available",
                "op": self.ftp_operation(
                    seq=6, opcode=OP_Nack, req_opcode=OP_ListDirectory, payload=bytes([FtpError.NoSessionsAvailable])
                ),
                "expected_message": "ListDirectory failed, no sessions available",
            },
            {
                "name": "End of File",
                "op": self.ftp_operation(
                    seq=7, opcode=OP_Nack, req_opcode=OP_ListDirectory, payload=bytes([FtpError.EndOfFile])
                ),
                "expected_message": "ListDirectory failed, offset past end of file",
            },
            {
                "name": "Unknown Command",
                "op": self.ftp_operation(
                    seq=8, opcode=OP_Nack, req_opcode=OP_ListDirectory, payload=bytes([FtpError.UnknownCommand])
                ),
                "expected_message": "ListDirectory failed, unknown command",
            },
            {
                "name": "File Exists",
                "op": self.ftp_operation(
                    seq=9, opcode=OP_Nack, req_opcode=OP_ListDirectory, payload=bytes([FtpError.FileExists])
                ),
                "expected_message": "ListDirectory failed, file/directory already exists",
            },
            {
                "name": "File Protected",
                "op": self.ftp_operation(
                    seq=10, opcode=OP_Nack, req_opcode=OP_ListDirectory, payload=bytes([FtpError.FileProtected])
                ),
                "expected_message": "ListDirectory failed, file/directory is protected",
            },
            {
                "name": "File Not Found",
                "op": self.ftp_operation(
                    seq=11, opcode=OP_Nack, req_opcode=OP_ListDirectory, payload=bytes([FtpError.FileNotFound])
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
                "op": self.ftp_operation(
                    seq=13, opcode=OP_Nack, req_opcode=OP_ListDirectory, payload=bytes([FtpError.Success])
                ),
                "expected_message": "ListDirectory failed, no error code",
            },
            {
                "name": "No Filesystem Error in Payload",
                "op": self.ftp_operation(
                    seq=14, opcode=OP_Nack, req_opcode=OP_ListDirectory, payload=bytes([FtpError.FailErrno])
                ),
                "expected_message": "ListDirectory failed, file-system error missing in payload",
            },
            {
                "name": "Invalid Error Code",
                "op": self.ftp_operation(
                    seq=15, opcode=OP_Nack, req_opcode=OP_ListDirectory, payload=bytes([FtpError.InvalidErrorCode])
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
                    seq=19, opcode=OP_Nack, req_opcode=OP_ListDirectory, payload=bytes([FtpError.UnknownCommand])
                ),  # Assuming 100 is an unknown opcode
                "expected_message": "ListDirectory failed, unknown command",
            },
            {
                "name": "Payload with System Error",
                "op": self.ftp_operation(
                    seq=20, opcode=OP_Nack, req_opcode=OP_ListDirectory, payload=bytes([FtpError.FailErrno, 2])
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
        ret = MAVFTPReturn("Command arguments", FtpError.InvalidArguments)
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
        ret = MAVFTPReturn("Put", FtpError.PutAlreadyInProgress)
        ret.display_message()
        log_output = self.log_stream.getvalue().strip()
        assert "Put failed, put already in progress" in log_output, "Expected put already in progress message"
        self.log_stream.seek(0)
        self.log_stream.truncate(0)

        # Fail to open local file
        ret = MAVFTPReturn("Put", FtpError.FailToOpenLocalFile)
        ret.display_message()
        log_output = self.log_stream.getvalue().strip()
        assert "Put failed, failed to open local file" in log_output, "Expected fail to open local file message"
        self.log_stream.seek(0)
        self.log_stream.truncate(0)

        # Remote Reply Timeout
        ret = MAVFTPReturn("Put", FtpError.RemoteReplyTimeout)
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
