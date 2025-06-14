#!/usr/bin/env python3
# PYTHON_ARGCOMPLETE_OK

"""
MAVLink File Transfer Protocol support - https://mavlink.io/en/services/ftp.html - duplicated from MAVProxy code.

Original from MAVProxy/MAVProxy/modules/mavproxy_ftp.py

This file is part of Ardupilot methodic configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2011-2024 Andrew Tridgell, 2024-2025 Amilcar Lucas

SPDX-License-Identifier: GPL-3.0-or-later
"""

import logging
import os
import random
import struct
import sys
import time
from argparse import ArgumentParser
from collections.abc import Generator
from datetime import datetime
from io import BufferedReader, BufferedWriter
from io import BytesIO as SIO  # noqa: N814
from typing import Union

import argcomplete
from argcomplete.completers import FilesCompleter
from pymavlink import mavutil

# pylint: disable=too-many-lines
# pylint: disable=invalid-name
# mypy: disable-error-code="union-attr,operator, arg-type"

# opcodes
OP_None = 0
OP_TerminateSession = 1
OP_ResetSessions = 2
OP_ListDirectory = 3
OP_OpenFileRO = 4
OP_ReadFile = 5
OP_CreateFile = 6
OP_WriteFile = 7
OP_RemoveFile = 8
OP_CreateDirectory = 9
OP_RemoveDirectory = 10
OP_OpenFileWO = 11
OP_TruncateFile = 12
OP_Rename = 13
OP_CalcFileCRC32 = 14
OP_BurstReadFile = 15
OP_Ack = 128
OP_Nack = 129

# error codes
ERR_None = 0
ERR_Fail = 1
ERR_FailErrno = 2
ERR_InvalidDataSize = 3
ERR_InvalidSession = 4
ERR_NoSessionsAvailable = 5
ERR_EndOfFile = 6
ERR_UnknownCommand = 7
ERR_FileExists = 8
ERR_FileProtected = 9
ERR_FileNotFound = 10

ERR_NoErrorCodeInPayload = 64
ERR_NoErrorCodeInNack = 65
ERR_NoFilesystemErrorInPayload = 66
ERR_InvalidErrorCode = 67
ERR_PayloadTooLarge = 68
ERR_InvalidOpcode = 69
ERR_InvalidArguments = 70
ERR_PutAlreadyInProgress = 71
ERR_FailToOpenLocalFile = 72
ERR_RemoteReplyTimeout = 73

HDR_Len = 12
MAX_Payload = 239
# pylint: enable=invalid-name


class FTP_OP:  # pylint: disable=invalid-name, too-many-instance-attributes
    """
    Represents an operation in the MAVLink File Transfer Protocol (FTP).

    This class encapsulates the details of a single FTP operation such as reading, writing, listing directories, etc.,
    including the necessary parameters and payload for the operation.
    """

    def __init__(  # pylint: disable=too-many-arguments, too-many-positional-arguments
        self,
        seq,
        session,
        opcode,
        size,
        req_opcode,
        burst_complete: bool,
        offset: int,
        payload,
    ) -> None:
        self.seq = seq  # Sequence number for the operation.
        self.session = session  # Session identifier.
        self.opcode = opcode  # Operation code indicating the type of FTP operation.
        self.size = size  # Size of the operation.
        self.req_opcode = req_opcode  # Request operation code.
        self.burst_complete: bool = burst_complete  # (bool) Flag indicating if the burst transfer is complete.
        self.offset: int = offset  # Offset for read/write operations.
        self.payload = payload  # (bytes) Payload for the operation.

    def pack(self) -> bytearray:
        """Pack message."""
        ret = struct.pack(
            "<HBBBBBBI", self.seq, self.session, self.opcode, self.size, self.req_opcode, self.burst_complete, 0, self.offset
        )
        if self.payload is not None:
            ret += self.payload
        return bytearray(ret)

    def __str__(self) -> str:
        """String representation of the FTP_OP."""
        plen = 0
        if self.payload is not None:
            plen = len(self.payload)
        ret = (
            f"OP seq:{self.seq} sess:{self.session} opcode:{self.opcode} req_opcode:{self.req_opcode}"
            f" size:{self.size} bc:{self.burst_complete} ofs:{self.offset} plen={plen}"
        )
        if plen > 0:
            ret += f" [{self.payload[0]}]"
        return ret

    def items(self) -> Generator[tuple[str, Union[int, bool, bytes]]]:
        """Yield each attribute and its value for the FTP_OP instance. For debugging purposes."""
        yield "seq", self.seq
        yield "session", self.session
        yield "opcode", self.opcode
        yield "size", self.size
        yield "req_opcode", self.req_opcode
        yield "burst_complete", self.burst_complete
        yield "offset", self.offset
        yield "payload", self.payload


class WriteQueue:  # pylint: disable=too-few-public-methods
    """
    Manages a queue of write operations for the MAVFTP class.

    Keeps track of offsets and sizes for pending write operations to ensure orderly processing.
    """

    def __init__(self, ofs: int, size: int) -> None:
        self.ofs = ofs  # Offset where the write operation starts.
        self.size = size  # Size of the data to be written.
        self.last_send = 0  # Timestamp of the last send operation.


class ParamData:
    """A class to manage parameter values and defaults for ArduPilot configuration."""

    def __init__(self) -> None:
        self.params: list[tuple[bytes, float, type]] = []  # params as (name, value, ptype)
        self.defaults: Union[None, list[tuple[bytes, float, type]]] = None  # defaults as (name, value, ptype)

    def add_param(self, name: bytes, value: float, ptype: type) -> None:
        self.params.append((name, value, ptype))

    def add_default(self, name: bytes, value: float, ptype: type) -> None:
        if self.defaults is None:
            self.defaults = []
        self.defaults.append((name, value, ptype))


class MAVFTPSetting:  # pylint: disable=too-few-public-methods
    """A single MAVFTP setting with a name, type, value and default value."""

    def __init__(self, name, s_type, default) -> None:
        self.name = name
        self.type = s_type
        self.default = default
        self.value = default


class MAVFTPSettings:
    """A collection of MAVFTP settings."""

    def __init__(self, s_vars) -> None:
        self._vars: dict[str, MAVFTPSetting] = {}
        for v in s_vars:
            self.append(v)

    def append(self, v) -> None:
        if isinstance(v, MAVFTPSetting):
            setting = v
        else:
            (name, s_type, default) = v
            setting = MAVFTPSetting(name, s_type, default)
        self._vars[setting.name] = setting

    def __getattr__(self, name) -> Union[int, float]:
        """Get attribute."""
        try:
            return self._vars[name].value  # type: ignore[no-any-return]
        except Exception as exc:
            raise AttributeError from exc

    def __setattr__(self, name, value) -> None:
        """Set attribute."""
        if name[0] == "_":
            self.__dict__[name] = value
            return
        if name in self._vars:
            self._vars[name].value = value
            return
        raise AttributeError


class MAVFTPReturn:
    """The result of a MAVFTP operation."""

    def __init__(  # pylint: disable=too-many-arguments, too-many-positional-arguments
        self,
        operation_name: str,
        error_code: int,
        system_error: int = 0,
        invalid_error_code: int = 0,
        invalid_opcode: int = 0,
        invalid_payload_size: int = 0,
    ) -> None:
        self.operation_name = operation_name
        self.error_code = error_code
        self.system_error = system_error
        self.invalid_error_code = invalid_error_code
        self.invalid_opcode = invalid_opcode
        self.invalid_payload_size = invalid_payload_size

    def display_message(self) -> None:  # pylint: disable=too-many-branches
        if self.error_code == ERR_None:
            logging.info("%s succeeded", self.operation_name)
        elif self.error_code == ERR_Fail:
            logging.error("%s failed, generic error", self.operation_name)
        elif self.error_code == ERR_FailErrno:
            logging.error("%s failed, system error %u", self.operation_name, self.system_error)
        elif self.error_code == ERR_InvalidDataSize:
            logging.error("%s failed, invalid data size", self.operation_name)
        elif self.error_code == ERR_InvalidSession:
            logging.error("%s failed, session is not currently open", self.operation_name)
        elif self.error_code == ERR_NoSessionsAvailable:
            logging.error("%s failed, no sessions available", self.operation_name)
        elif self.error_code == ERR_EndOfFile:
            logging.error("%s failed, offset past end of file", self.operation_name)
        elif self.error_code == ERR_UnknownCommand:
            logging.error("%s failed, unknown command", self.operation_name)
        elif self.error_code == ERR_FileExists:
            logging.warning("%s failed, file/directory already exists", self.operation_name)
        elif self.error_code == ERR_FileProtected:
            logging.warning("%s failed, file/directory is protected", self.operation_name)
        elif self.error_code == ERR_FileNotFound:
            logging.warning("%s failed, file/directory not found", self.operation_name)

        elif self.error_code == ERR_NoErrorCodeInPayload:
            logging.error("%s failed, payload contains no error code", self.operation_name)
        elif self.error_code == ERR_NoErrorCodeInNack:
            logging.error("%s failed, no error code", self.operation_name)
        elif self.error_code == ERR_NoFilesystemErrorInPayload:
            logging.error("%s failed, file-system error missing in payload", self.operation_name)
        elif self.error_code == ERR_InvalidErrorCode:
            logging.error("%s failed, invalid error code %u", self.operation_name, self.invalid_error_code)
        elif self.error_code == ERR_PayloadTooLarge:
            logging.error("%s failed, payload is too long %u", self.operation_name, self.invalid_payload_size)
        elif self.error_code == ERR_InvalidOpcode:
            logging.error("%s failed, invalid opcode %u", self.operation_name, self.invalid_opcode)
        elif self.error_code == ERR_InvalidArguments:
            logging.error("%s failed, invalid arguments", self.operation_name)
        elif self.error_code == ERR_PutAlreadyInProgress:
            logging.error("%s failed, put already in progress", self.operation_name)
        elif self.error_code == ERR_FailToOpenLocalFile:
            logging.error("%s failed, failed to open local file", self.operation_name)
        elif self.error_code == ERR_RemoteReplyTimeout:
            logging.error("%s failed, remote reply timeout", self.operation_name)
        else:
            logging.error("%s failed, unknown error %u in display_message()", self.operation_name, self.error_code)

    @property
    def return_code(self) -> int:
        return self.error_code


class MAVFTP:  # pylint: disable=too-many-instance-attributes
    """
    Implements the client-side logic for the MAVLink File Transfer Protocol (FTP) over MAVLink connections.

    Handles file operations such as reading, writing, listing directories, and managing sessions.
    """

    def __init__(
        self,
        master,
        target_system,
        target_component,
        settings=None,
    ) -> None:
        if settings is None:
            settings = MAVFTPSettings(
                [
                    ("debug", int, 0),
                    ("pkt_loss_tx", int, 0),
                    ("pkt_loss_rx", int, 0),
                    ("max_backlog", int, 5),
                    ("burst_read_size", int, 80),
                    ("write_size", int, 80),
                    ("write_qsize", int, 5),
                    ("idle_detection_time", float, 3.7),
                    ("read_retry_time", float, 1.0),
                    ("retry_time", float, 0.5),
                ]
            )
        self.ftp_settings = settings
        self.seq = 0
        self.session = 0
        self.network = 0
        self.last_op: Union[None, FTP_OP] = None
        self.fh: Union[None, SIO, BufferedReader, BufferedWriter] = None
        self.filename: Union[None, str] = None
        self.callback = None
        self.callback_progress = None
        self.put_callback = None
        self.put_callback_progress = None
        self.total_size = 0
        self.read_gaps: list[tuple[int, int]] = []
        self.read_gap_times: dict[tuple[int, int], float] = {}
        self.last_gap_send = 0.0
        self.read_retries = 0
        self.read_total = 0
        self.remote_file_size = None
        self.duplicates = 0
        self.last_read = None
        self.last_burst_read: Union[None, float] = None
        self.op_start: Union[None, float] = None
        self.dir_offset = 0
        self.last_op_time = time.time()
        self.last_send_time = time.time()
        self.rtt = 0.5
        self.reached_eof = False
        self.backlog = 0
        self.burst_size = self.ftp_settings.burst_read_size
        self.write_list: Union[None, set[int]] = None
        self.write_block_size = 0
        self.write_acks = 0
        self.write_total = 0
        self.write_file_size = 0
        self.write_idx = 0
        self.write_recv_idx = -1
        self.write_pending = 0
        self.write_last_send: Union[None, float] = None
        self.open_retries = 0

        self.master = master
        self.target_system = target_system
        self.target_component = target_component

        # Reset the flight controller FTP state-machine
        self.__send(FTP_OP(self.seq, self.session, OP_ResetSessions, 0, 0, 0, 0, None))
        self.process_ftp_reply("ResetSessions")

    def cmd_ftp(self, args) -> MAVFTPReturn:  # noqa PRL0911, pylint: disable=too-many-return-statements, too-many-branches
        """FTP operations."""
        usage = "Usage: ftp <list|set|get|getparams|put|rm|rmdir|rename|mkdir|status|cancel|crc>"
        if len(args) < 1:
            logging.error(usage)
            return MAVFTPReturn("FTP command", ERR_InvalidArguments)
        if args[0] == "list":
            return self.cmd_list(args[1:])
        if args[0] == "set":
            self.ftp_settings.command(args[1:])
            return MAVFTPReturn("FTP command", ERR_None)
        if args[0] == "get":
            return self.cmd_get(args[1:])
        if args[0] == "getparams":
            return self.cmd_getparams(args[1:])
        if args[0] == "put":
            return self.cmd_put(args[1:])
        if args[0] == "rm":
            return self.cmd_rm(args[1:])
        if args[0] == "rmdir":
            return self.cmd_rmdir(args[1:])
        if args[0] == "rename":
            return self.cmd_rename(args[1:])
        if args[0] == "mkdir":
            return self.cmd_mkdir(args[1:])
        if args[0] == "crc":
            return self.cmd_crc(args[1:])
        if args[0] == "status":
            return self.cmd_status()
        if args[0] == "cancel":
            return self.cmd_cancel()
        logging.error(usage)
        return MAVFTPReturn("FTP command", ERR_InvalidArguments)

    def __send(self, op) -> None:
        """Send a request."""
        op.seq = self.seq
        payload = op.pack()
        plen = len(payload)
        if plen < MAX_Payload + HDR_Len:
            payload.extend(bytearray([0] * ((HDR_Len + MAX_Payload) - plen)))
        self.master.mav.file_transfer_protocol_send(self.network, self.target_system, self.target_component, payload)
        self.seq = (self.seq + 1) % 256
        self.last_op = op
        now = time.time()
        if self.ftp_settings.debug > 1:
            logging.info("FTP: > %s dt=%.2f", op, now - self.last_op_time)
        self.last_op_time = time.time()
        self.last_send_time = now

    def __terminate_session(self) -> None:
        """Terminate current session."""
        self.__send(FTP_OP(self.seq, self.session, OP_TerminateSession, 0, 0, 0, 0, None))
        self.fh = None
        self.filename = None
        self.write_list = None
        if self.callback is not None:
            # tell caller that the transfer failed
            self.callback(None)
            self.callback = None
        if self.callback_progress is not None:
            self.callback_progress(None)
            self.callback_progress = None
        if self.put_callback is not None:
            # tell caller that the transfer failed
            self.put_callback(None)
            self.put_callback = None
        if self.put_callback_progress is not None:
            self.put_callback_progress(None)
            self.put_callback_progress = None
        self.read_gaps = []
        self.read_total = 0
        self.read_gap_times = {}
        self.last_read = None
        self.last_burst_read = None
        self.reached_eof = False
        self.backlog = 0
        self.duplicates = 0
        if self.ftp_settings.debug > 0:
            logging.info("FTP: Terminated session")
        self.process_ftp_reply("TerminateSession")
        self.session = (self.session + 1) % 256

    def cmd_list(self, args) -> MAVFTPReturn:
        """List files."""
        if len(args) == 0:
            dname = "/"
        elif len(args) == 1:
            dname = args[0]
        else:
            logging.error("Usage: list [directory]")
            return MAVFTPReturn("ListDirectory", ERR_InvalidArguments)
        logging.info("Listing %s", dname)
        enc_dname = bytearray(dname, "ascii")
        self.total_size = 0
        self.dir_offset = 0
        op = FTP_OP(self.seq, self.session, OP_ListDirectory, len(enc_dname), 0, 0, self.dir_offset, enc_dname)
        self.__send(op)
        return self.process_ftp_reply("ListDirectory")

    def __handle_list_reply(self, op, _m) -> MAVFTPReturn:
        """Handle OP_ListDirectory reply."""
        if op.opcode == OP_Ack:
            dentries = sorted(op.payload.split(b"\x00"))
            # logging.info(dentries)
            for d in dentries:
                if len(d) == 0:
                    continue
                self.dir_offset += 1
                try:
                    d = str(d, "ascii")  # noqa: PLW2901
                except Exception:  # noqa: S112 pylint: disable=broad-exception-caught
                    continue
                if d[0] == "D":
                    logging.info(" D %s", d[1:])
                elif d[0] == "F":
                    (name, size) = d[1:].split("\t")
                    size_int = int(size)
                    self.total_size += size_int
                    logging.info("   %s\t%u", name, size_int)
                else:
                    logging.info(d)
            # ask for more
            more = self.last_op
            more.offset = self.dir_offset
            self.__send(more)
        elif op.opcode == OP_Nack and len(op.payload) == 1 and op.payload[0] == ERR_EndOfFile:
            logging.info("Total size %.2f kByte", self.total_size / 1024.0)
            self.total_size = 0
        else:
            return self.__decode_ftp_ack_and_nack(op)
        return MAVFTPReturn("ListDirectory", ERR_None)

    def cmd_get(self, args, callback=None, progress_callback=None) -> MAVFTPReturn:
        """Get file."""
        if len(args) == 0 or len(args) > 2:
            logging.error("Usage: get [FILENAME <LOCALNAME>]")
            return MAVFTPReturn("OpenFileRO", ERR_InvalidArguments)
        fname = args[0]
        if len(args) > 1:
            self.filename = args[1]
        else:
            self.filename = os.path.basename(fname)
        if callback is None or self.ftp_settings.debug > 1:
            logging.info("Getting %s to %s", fname, self.filename)
        self.op_start = time.time()
        self.callback = callback
        self.callback_progress = progress_callback
        self.read_retries = 0
        self.duplicates = 0
        self.reached_eof = False
        self.burst_size = self.ftp_settings.burst_read_size
        if self.burst_size < 1 or self.burst_size > 239:
            self.burst_size = 239
        self.remote_file_size = None
        enc_fname = bytearray(fname, "ascii")
        self.open_retries = 0
        op = FTP_OP(self.seq, self.session, OP_OpenFileRO, len(enc_fname), 0, 0, 0, enc_fname)
        self.__send(op)
        return MAVFTPReturn("OpenFileRO", ERR_None)

    def __handle_open_ro_reply(self, op, _m) -> MAVFTPReturn:
        """Handle OP_OpenFileRO reply."""
        if op.opcode == OP_Ack:
            if self.filename is None:
                return MAVFTPReturn("OpenFileRO", ERR_FileNotFound)
            try:
                if self.callback is not None or self.filename == "-":
                    self.fh = SIO()
                else:
                    self.fh = open(self.filename, "wb")  # noqa: SIM115 pylint: disable=consider-using-with
            except Exception as ex:  # pylint: disable=broad-except
                logging.error("FTP: Failed to open local file %s: %s", self.filename, ex)
                self.__terminate_session()
                return MAVFTPReturn("OpenFileRO", ERR_FileNotFound)
            if op.size == 4 and len(op.payload) >= 4:
                self.remote_file_size = op.payload[0] + (op.payload[1] << 8) + (op.payload[2] << 16) + (op.payload[3] << 24)
                if self.ftp_settings.debug > 0:
                    logging.info("Remote file size: %u", self.remote_file_size)
            else:
                self.remote_file_size = None
            read = FTP_OP(self.seq, self.session, OP_BurstReadFile, self.burst_size, 0, 0, 0, None)
            self.last_burst_read = time.time()
            self.__send(read)
            return MAVFTPReturn("OpenFileRO", ERR_None)

        ret = self.__decode_ftp_ack_and_nack(op)
        if self.callback is None or self.ftp_settings.debug > 0:
            ret.display_message()
        self.__terminate_session()
        return ret

    def __check_read_finished(self) -> bool:
        """Check if download has completed."""
        # logging.debug("FTP: check_read_finished: %s %s", self.reached_eof, self.read_gaps)
        if self.reached_eof and len(self.read_gaps) == 0:
            ofs = self.fh.tell()
            dt = time.time() - self.op_start
            rate = (ofs / dt) / 1024.0
            if self.callback is not None:
                self.fh.seek(0)
                self.callback(self.fh)
                self.callback = None
            elif self.filename == "-":
                self.fh.seek(0)
                print(self.fh.read().decode("utf-8"))  # noqa: T201
            else:
                logging.info("Got %u bytes from %s in %.2fs %.1fkByte/s", ofs, self.filename, dt, rate)
                self.remote_file_size = None
            self.__terminate_session()
            return True
        return False

    def __write_payload(self, op) -> None:
        """Write payload from a read op."""
        self.fh.seek(op.offset)
        self.fh.write(op.payload)
        self.read_total += len(op.payload)
        if self.callback_progress is not None and self.remote_file_size:
            self.callback_progress(self.read_total / self.remote_file_size)

    def __handle_burst_read(self, op, _m) -> MAVFTPReturn:  # noqa PRL0911, PGH004, pylint: disable=too-many-branches, too-many-statements, too-many-return-statements
        """Handle OP_BurstReadFile reply."""
        if self.ftp_settings.pkt_loss_tx > 0 and random.uniform(0, 100) < self.ftp_settings.pkt_loss_tx:  # noqa: S311
            if self.ftp_settings.debug > 0:
                logging.warning("FTP: dropping TX")
            return MAVFTPReturn("BurstReadFile", ERR_Fail)
        if self.fh is None or self.filename is None:
            if op.session != self.session:
                # old session
                return MAVFTPReturn("BurstReadFile", ERR_InvalidSession)
            logging.warning("FTP: Unexpected burst read reply. Will be discarded")
            logging.info(op)
            return MAVFTPReturn("BurstReadFile", ERR_Fail)
        self.last_burst_read = time.time()
        size = len(op.payload)
        if size > self.burst_size:
            # this server doesn't handle the burst size argument
            self.burst_size = MAX_Payload
            if self.ftp_settings.debug > 0:
                logging.info("FTP: Setting burst size to %u", self.burst_size)
        if op.opcode == OP_Ack and self.fh is not None:
            ofs = self.fh.tell()
            if op.offset < ofs:
                # writing an earlier portion, possibly remove a gap
                gap = (op.offset, len(op.payload))
                if gap in self.read_gaps:
                    self.read_gaps.remove(gap)
                    self.read_gap_times.pop(gap)
                    if self.ftp_settings.debug > 0:
                        logging.info("FTP: removed gap %u, %u, %u", gap, self.reached_eof, len(self.read_gaps))
                else:
                    if self.ftp_settings.debug > 0:
                        logging.info("FTP: dup read reply at %u of len %u ofs=%u", op.offset, op.size, self.fh.tell())
                    self.duplicates += 1
                    return MAVFTPReturn("BurstReadFile", ERR_Fail)
                self.__write_payload(op)
                self.fh.seek(ofs)
                if self.__check_read_finished():
                    return MAVFTPReturn("BurstReadFile", ERR_None)
            elif op.offset > ofs:
                # we have a gap
                gap = (ofs, op.offset - ofs)
                max_read = self.burst_size
                while True:
                    if gap[1] <= max_read:
                        self.read_gaps.append(gap)
                        self.read_gap_times[gap] = 0
                        break
                    g = (gap[0], max_read)
                    self.read_gaps.append(g)
                    self.read_gap_times[g] = 0
                    gap = (gap[0] + max_read, gap[1] - max_read)
                self.__write_payload(op)
            else:
                self.__write_payload(op)
            if op.burst_complete:
                if op.size > 0 and op.size < self.burst_size:
                    # a burst complete with non-zero size and less than burst packet size
                    # means EOF
                    if not self.reached_eof and self.ftp_settings.debug > 0:
                        logging.info(
                            "FTP: EOF at %u with %u gaps t=%.2f",
                            self.fh.tell(),
                            len(self.read_gaps),
                            time.time() - self.op_start,
                        )
                    self.reached_eof = True
                    if self.__check_read_finished():
                        return MAVFTPReturn("BurstReadFile", ERR_None)
                    self.__check_read_send()
                    return MAVFTPReturn("BurstReadFile", ERR_None)
                more = self.last_op
                more.offset = op.offset + op.size
                if self.ftp_settings.debug > 0:
                    logging.info("FTP: burst continue at %u %u", more.offset, self.fh.tell())
                self.__send(more)
        elif op.opcode == OP_Nack:
            ecode = op.payload[0]
            if ecode in {ERR_EndOfFile, 0}:
                if not self.reached_eof and op.offset > self.fh.tell():
                    # we lost the last part of the burst
                    if self.ftp_settings.debug > 0:
                        logging.error("FTP: burst lost EOF %u %u", self.fh.tell(), op.offset)
                    return MAVFTPReturn("BurstReadFile", ERR_Fail)
                if not self.reached_eof and self.ftp_settings.debug > 0:
                    logging.info(
                        "FTP: EOF at %u with %u gaps t=%.2f", self.fh.tell(), len(self.read_gaps), time.time() - self.op_start
                    )
                self.reached_eof = True
                if self.__check_read_finished():
                    return MAVFTPReturn("BurstReadFile", ERR_None)
                self.__check_read_send()
            elif self.ftp_settings.debug > 0:
                logging.info("FTP: burst Nack (ecode:%u): %s", ecode, op)
                return MAVFTPReturn("BurstReadFile", ERR_Fail)
            if self.ftp_settings.debug > 0:
                logging.error("FTP: burst nack: %s", op)
                return MAVFTPReturn("BurstReadFile", ERR_Fail)
        else:
            logging.warning("FTP: burst error: %s", op)
        return MAVFTPReturn("BurstReadFile", ERR_Fail)

    def __handle_reply_read(self, op, _m) -> MAVFTPReturn:
        """Handle OP_ReadFile reply."""
        if self.fh is None or self.filename is None:
            if self.ftp_settings.debug > 0:
                logging.warning("FTP: Unexpected read reply")
                logging.warning(op)
            return MAVFTPReturn("ReadFile", ERR_Fail)
        if self.backlog > 0:
            self.backlog -= 1
        if op.opcode == OP_Ack and self.fh is not None:
            gap = (op.offset, op.size)
            if gap in self.read_gaps:
                self.read_gaps.remove(gap)
                self.read_gap_times.pop(gap)
                ofs = self.fh.tell()
                self.__write_payload(op)
                self.fh.seek(ofs)
                if self.ftp_settings.debug > 0:
                    logging.info("FTP: removed gap %u, %u, %u", gap, self.reached_eof, len(self.read_gaps))
                if self.__check_read_finished():
                    return MAVFTPReturn("ReadFile", ERR_None)
            elif op.size < self.burst_size:
                logging.info("FTP: file size changed to %u", op.offset + op.size)
                self.__terminate_session()
            else:
                self.duplicates += 1
                if self.ftp_settings.debug > 0:
                    logging.info("FTP: no gap read %u, %u", gap, len(self.read_gaps))
        elif op.opcode == OP_Nack:
            logging.info("FTP: Read failed with %u gaps %s", len(self.read_gaps), str(op))
            self.__terminate_session()
        self.__check_read_send()
        return MAVFTPReturn("ReadFile", ERR_None)

    def cmd_put(self, args, fh=None, callback=None, progress_callback=None) -> MAVFTPReturn:
        """Put file."""
        if len(args) == 0 or len(args) > 2:
            logging.error("Usage: put [FILENAME <REMOTENAME>]")
            return MAVFTPReturn("CreateFile", ERR_InvalidArguments)
        if self.write_list is not None:
            logging.error("FTP: put already in progress")
            return MAVFTPReturn("CreateFile", ERR_PutAlreadyInProgress)
        fname = args[0]
        self.fh = fh
        if self.fh is None:
            try:
                self.fh = open(fname, "rb")  # noqa: SIM115 pylint: disable=consider-using-with
            except Exception as ex:  # pylint: disable=broad-exception-caught
                logging.error("FTP: Failed to open %s: %s", fname, ex)
                return MAVFTPReturn("CreateFile", ERR_FailToOpenLocalFile)
        if len(args) > 1:
            self.filename = args[1]
        else:
            self.filename = os.path.basename(fname)
        if self.filename.endswith("/"):
            self.filename += os.path.basename(fname)
        if callback is None:
            logging.info("Putting %s to %s", fname, self.filename)
        self.fh.seek(0, 2)
        file_size = self.fh.tell()
        self.fh.seek(0)

        # setup write list
        self.write_block_size = self.ftp_settings.write_size
        self.write_file_size = file_size

        write_blockcount = file_size // self.write_block_size
        if file_size % self.write_block_size != 0:
            write_blockcount += 1

        self.write_list = set(range(write_blockcount))
        self.write_acks = 0
        self.write_total = write_blockcount
        self.write_idx = 0
        self.write_recv_idx = -1
        self.write_pending = 0
        self.write_last_send = None

        self.put_callback = callback
        self.put_callback_progress = progress_callback
        self.read_retries = 0
        self.op_start = time.time()
        enc_fname = bytearray(self.filename, "ascii")
        op = FTP_OP(self.seq, self.session, OP_CreateFile, len(enc_fname), 0, 0, 0, enc_fname)
        self.__send(op)
        return MAVFTPReturn("CreateFile", ERR_None)

    def __put_finished(self, flen) -> None:
        """Finish a put."""
        if self.put_callback_progress:
            self.put_callback_progress(1.0)
            self.put_callback_progress = None
        if self.put_callback is not None:
            self.put_callback(flen)
            self.put_callback = None
        else:
            dt = time.time() - self.op_start
            rate = (flen / dt) / 1024.0
            logging.info("Put %u bytes to %s file in %.2fs %.1fkByte/s", flen, self.filename, dt, rate)

    def __handle_create_file_reply(self, op, _m) -> MAVFTPReturn:
        """Handle OP_CreateFile reply."""
        if self.fh is None:
            self.__terminate_session()
            return MAVFTPReturn("CreateFile", ERR_FileNotFound)
        if op.opcode == OP_Ack:
            self.__send_more_writes()
        else:
            ret = self.__decode_ftp_ack_and_nack(op)
            self.__terminate_session()
            return ret
        return MAVFTPReturn("CreateFile", ERR_None)

    def __send_more_writes(self) -> None:
        """Send some more writes."""
        if len(self.write_list) == 0:
            # all done
            self.__put_finished(self.write_file_size)
            self.__terminate_session()
            return

        now = time.time()
        if self.write_last_send is not None and now - self.write_last_send > max(min(10 * self.rtt, 1), 0.2):
            # we seem to have lost a block of replies
            self.write_pending = max(0, self.write_pending - 1)

        n = min(self.ftp_settings.write_qsize - self.write_pending, len(self.write_list))
        for _i in range(n):
            # send in round-robin, skipping any that have been acked
            idx = self.write_idx
            while idx not in self.write_list:
                idx = (idx + 1) % self.write_total
            ofs = idx * self.write_block_size
            self.fh.seek(ofs)
            data = self.fh.read(self.write_block_size)
            write = FTP_OP(self.seq, self.session, OP_WriteFile, len(data), 0, 0, ofs, bytearray(data))
            self.__send(write)
            self.write_idx = (idx + 1) % self.write_total
            self.write_pending += 1
            self.write_last_send = now

    def __handle_write_reply(self, op, _m) -> MAVFTPReturn:
        """Handle OP_WriteFile reply."""
        if self.fh is None:
            self.__terminate_session()
            return MAVFTPReturn("WriteFile", ERR_FileNotFound)
        if op.opcode != OP_Ack:
            logging.error("FTP: Write failed")
            self.__terminate_session()
            return MAVFTPReturn("WriteFile", ERR_FileProtected)

        # assume the FTP server processes the blocks sequentially. This means
        # when we receive an ack that any blocks between the last ack and this
        # one have been lost
        idx = op.offset // self.write_block_size
        count = (idx - self.write_recv_idx) % self.write_total

        self.write_pending = max(0, self.write_pending - count)
        self.write_recv_idx = idx
        self.write_list.discard(idx)
        self.write_acks += 1
        if self.put_callback_progress:
            self.put_callback_progress(self.write_acks / float(self.write_total))
        self.__send_more_writes()
        return MAVFTPReturn("WriteFile", ERR_None)

    def cmd_rm(self, args) -> MAVFTPReturn:
        """Remove file."""
        if len(args) != 1:
            logging.error("Usage: rm [FILENAME]")
            return MAVFTPReturn("RemoveFile", ERR_InvalidArguments)
        fname = args[0]
        logging.info("Removing file %s", fname)
        enc_fname = bytearray(fname, "ascii")
        op = FTP_OP(self.seq, self.session, OP_RemoveFile, len(enc_fname), 0, 0, 0, enc_fname)
        self.__send(op)
        return self.process_ftp_reply("RemoveFile")

    def cmd_rmdir(self, args) -> MAVFTPReturn:
        """Remove directory."""
        if len(args) != 1:
            logging.error("Usage: rmdir [DIRECTORYNAME]")
            return MAVFTPReturn("RemoveDirectory", ERR_InvalidArguments)
        dname = args[0]
        logging.info("Removing directory %s", dname)
        enc_dname = bytearray(dname, "ascii")
        op = FTP_OP(self.seq, self.session, OP_RemoveDirectory, len(enc_dname), 0, 0, 0, enc_dname)
        self.__send(op)
        return self.process_ftp_reply("RemoveDirectory")

    def __handle_remove_reply(self, op, _m) -> MAVFTPReturn:
        """Handle remove reply."""
        return self.__decode_ftp_ack_and_nack(op)

    def cmd_rename(self, args) -> MAVFTPReturn:
        """Rename file or directory."""
        if len(args) < 2:
            logging.error("Usage: rename [OLDNAME NEWNAME]")
            return MAVFTPReturn("Rename", ERR_InvalidArguments)
        name1 = args[0]
        name2 = args[1]
        logging.info("Renaming %s to %s", name1, name2)
        enc_name1 = bytearray(name1, "ascii")
        enc_name2 = bytearray(name2, "ascii")
        enc_both = enc_name1 + b"\x00" + enc_name2
        op = FTP_OP(self.seq, self.session, OP_Rename, len(enc_both), 0, 0, 0, enc_both)
        self.__send(op)
        return self.process_ftp_reply("Rename")

    def __handle_rename_reply(self, op, _m) -> MAVFTPReturn:
        """Handle rename reply."""
        return self.__decode_ftp_ack_and_nack(op)

    def cmd_mkdir(self, args) -> MAVFTPReturn:
        """Make directory."""
        if len(args) != 1:
            logging.error("Usage: mkdir NAME")
            return MAVFTPReturn("CreateDirectory", ERR_InvalidArguments)
        name = args[0]
        logging.info("Creating directory %s", name)
        enc_name = bytearray(name, "ascii")
        op = FTP_OP(self.seq, self.session, OP_CreateDirectory, len(enc_name), 0, 0, 0, enc_name)
        self.__send(op)
        return self.process_ftp_reply("CreateDirectory")

    def __handle_mkdir_reply(self, op, _m) -> MAVFTPReturn:
        """Handle mkdir reply."""
        return self.__decode_ftp_ack_and_nack(op)

    def cmd_crc(self, args) -> MAVFTPReturn:
        """Get file crc."""
        if len(args) != 1:
            logging.error("Usage: crc [NAME]")
            return MAVFTPReturn("CalcFileCRC32", ERR_InvalidArguments)
        name = args[0]
        self.filename = name
        self.op_start = time.time()
        logging.info("Getting CRC for %s", name)
        enc_name = bytearray(name, "ascii")
        op = FTP_OP(self.seq, self.session, OP_CalcFileCRC32, len(enc_name), 0, 0, 0, bytearray(enc_name))
        self.__send(op)
        return self.process_ftp_reply("CalcFileCRC32")

    def __handle_crc_reply(self, op, _m) -> MAVFTPReturn:
        """Handle crc reply."""
        if op.opcode == OP_Ack and op.size == 4:
            (crc,) = struct.unpack("<I", op.payload)
            now = time.time()
            logging.info("crc: %s 0x%08x in %.1fs", self.filename, crc, now - self.op_start)
        return self.__decode_ftp_ack_and_nack(op)

    def cmd_cancel(self) -> MAVFTPReturn:
        """Cancel any pending op."""
        self.__terminate_session()
        return MAVFTPReturn("TerminateSession", ERR_None)

    def cmd_status(self) -> MAVFTPReturn:
        """Show status."""
        if self.fh is None:
            logging.info("No transfer in progress")
        else:
            ofs = self.fh.tell()
            dt = time.time() - self.op_start
            rate = (ofs / dt) / 1024.0
            logging.info(
                "Transfer at offset %u with %u gaps %u retries %.1f kByte/sec",
                ofs,
                len(self.read_gaps),
                self.read_retries,
                rate,
            )
        return MAVFTPReturn("Status", ERR_None)

    def __op_parse(self, m) -> FTP_OP:
        """Parse a FILE_TRANSFER_PROTOCOL msg."""
        hdr = bytearray(m.payload[0:12])
        (seq, session, opcode, size, req_opcode, burst_complete, _pad, offset) = struct.unpack("<HBBBBBBI", hdr)
        payload = bytearray(m.payload[12:])[:size]
        return FTP_OP(seq, session, opcode, size, req_opcode, burst_complete, offset, payload)

    def __mavlink_packet(self, m) -> MAVFTPReturn:  # noqa PRL0911, PGH004, pylint: disable=too-many-branches, too-many-return-statements
        """Handle a mavlink packet."""
        operation_name = "mavlink_packet"
        mtype = m.get_type()
        if mtype != "FILE_TRANSFER_PROTOCOL":
            logging.error("FTP: Unexpected MAVLink message type %s", mtype)
            return MAVFTPReturn(operation_name, ERR_Fail)

        if m.target_system != self.master.source_system or m.target_component != self.master.source_component:
            logging.info(
                "FTP: wrong MAVLink target %u component %u. Will discard message", m.target_system, m.target_component
            )
            return MAVFTPReturn(operation_name, ERR_Fail)

        op = self.__op_parse(m)
        now = time.time()
        dt = now - self.last_op_time
        if self.ftp_settings.debug > 1:
            logging.info("FTP: < %s dt=%.2f", op, dt)
        if op.session != self.session:
            if self.ftp_settings.debug > 0:
                logging.warning("FTP: wrong session replied %u expected %u. Will discard message", op.session, self.session)
            return MAVFTPReturn(operation_name, ERR_InvalidSession)
        self.last_op_time = now
        if self.ftp_settings.pkt_loss_rx > 0 and random.uniform(0, 100) < self.ftp_settings.pkt_loss_rx:  # noqa: S311
            if self.ftp_settings.debug > 1:
                logging.warning("FTP: dropping packet RX")
            return MAVFTPReturn(operation_name, ERR_Fail)

        if op.req_opcode == self.last_op.opcode and op.seq == (self.last_op.seq + 1) % 256:
            self.rtt = max(min(self.rtt, dt), 0.01)

        if op.req_opcode == OP_ListDirectory:
            return self.__handle_list_reply(op, m)
        if op.req_opcode == OP_OpenFileRO:
            return self.__handle_open_ro_reply(op, m)
        if op.req_opcode == OP_BurstReadFile:
            return self.__handle_burst_read(op, m)
        if op.req_opcode == OP_ResetSessions:
            return self.__handle_reset_sessions_reply(op, m)
        if op.req_opcode in {OP_None, OP_TerminateSession}:
            return MAVFTPReturn(operation_name, ERR_None)  # ignore reply
        if op.req_opcode == OP_CreateFile:
            return self.__handle_create_file_reply(op, m)
        if op.req_opcode == OP_WriteFile:
            return self.__handle_write_reply(op, m)
        if op.req_opcode in {OP_RemoveFile, OP_RemoveDirectory}:
            return self.__handle_remove_reply(op, m)
        if op.req_opcode == OP_Rename:
            return self.__handle_rename_reply(op, m)
        if op.req_opcode == OP_CreateDirectory:
            return self.__handle_mkdir_reply(op, m)
        if op.req_opcode == OP_ReadFile:
            return self.__handle_reply_read(op, m)
        if op.req_opcode == OP_CalcFileCRC32:
            return self.__handle_crc_reply(op, m)

        logging.info("FTP Unknown %s", str(op))
        return MAVFTPReturn(operation_name, ERR_InvalidOpcode)

    def __send_gap_read(self, g) -> None:
        """Send a read for a gap."""
        (offset, length) = g
        if self.ftp_settings.debug > 0:
            logging.info("FTP: Gap read of %u at %u rem=%u blog=%u", length, offset, len(self.read_gaps), self.backlog)
        read = FTP_OP(self.seq, self.session, OP_ReadFile, length, 0, 0, offset, None)
        self.__send(read)
        self.read_gaps.remove(g)
        self.read_gaps.append(g)
        self.last_gap_send = time.time()
        self.read_gap_times[g] = self.last_gap_send
        self.backlog += 1

    def __check_read_send(self) -> None:
        """See if we should send another gap read."""
        if len(self.read_gaps) == 0:
            return
        g = self.read_gaps[0]
        now = time.time()
        dt = now - self.read_gap_times[g]
        if not self.reached_eof:
            # send gap reads once
            for g, gap_time in self.read_gap_times.items():
                if gap_time == 0:
                    self.__send_gap_read(g)
            return
        if self.read_gap_times[g] > 0 and dt > self.ftp_settings.retry_time:
            if self.backlog > 0:
                self.backlog -= 1
            self.read_gap_times[g] = 0

        if self.read_gap_times[g] != 0:
            # still pending
            return
        if not self.reached_eof and self.backlog >= self.ftp_settings.max_backlog:
            # don't fill queue too far until we have got past the burst
            return
        if now - self.last_gap_send < 0.05:
            # don't send too fast
            return
        self.__send_gap_read(g)

    def __idle_task(self) -> bool:
        """Check for file gaps and lost requests."""
        now = time.time()
        assert (  # noqa: S101
            self.ftp_settings.idle_detection_time > self.ftp_settings.read_retry_time
        ), "settings.idle_detection_time must be > settings.read_retry_time"

        # see if we lost an open reply
        if (
            self.op_start is not None
            and now - self.op_start > self.ftp_settings.read_retry_time
            and self.last_op.opcode == OP_OpenFileRO
        ):
            self.op_start = now
            self.open_retries += 1
            if self.open_retries > 2:
                # fail the get
                self.op_start = None
                self.__terminate_session()
                return False  # Not idle yet
            if self.ftp_settings.debug > 0:
                logging.info("FTP: retry open")
            send_op = self.last_op
            self.__send(FTP_OP(self.seq, self.session, OP_TerminateSession, 0, 0, 0, 0, None))
            self.session = (self.session + 1) % 256
            send_op.session = self.session
            self.__send(send_op)

        if len(self.read_gaps) == 0 and self.last_burst_read is None and self.write_list is None:
            return self.__last_send_time_was_more_than_idle_detection_time_ago(now)

        if self.fh is None:
            return self.__last_send_time_was_more_than_idle_detection_time_ago(now)

        # see if burst read has stalled
        if (
            not self.reached_eof
            and self.last_burst_read is not None
            and now - self.last_burst_read > self.ftp_settings.retry_time
        ):
            dt = now - self.last_burst_read
            self.last_burst_read = now
            if self.ftp_settings.debug > 0:
                logging.info("FTP: Retry read at %u rtt=%.2f dt=%.2f", self.fh.tell(), self.rtt, dt)
            self.__send(FTP_OP(self.seq, self.session, OP_BurstReadFile, self.burst_size, 0, 0, self.fh.tell(), None))
            self.read_retries += 1

        # see if we can fill gaps
        self.__check_read_send()

        if self.write_list is not None:
            self.__send_more_writes()

        return self.__last_send_time_was_more_than_idle_detection_time_ago(now)

    def __last_send_time_was_more_than_idle_detection_time_ago(self, now: float) -> bool:
        return self.last_send_time is not None and now - self.last_send_time > float(self.ftp_settings.idle_detection_time)

    def __handle_reset_sessions_reply(self, op, _m) -> MAVFTPReturn:
        """Handle reset sessions reply."""
        return self.__decode_ftp_ack_and_nack(op)

    def process_ftp_reply(self, operation_name, timeout: float = 5) -> MAVFTPReturn:
        """Execute an FTP operation that requires processing a MAVLink response."""
        start_time = time.time()
        ret = MAVFTPReturn(operation_name, ERR_Fail)
        recv_timeout = 0.1
        assert (  # noqa: S101
            timeout == 0 or timeout > float(self.ftp_settings.idle_detection_time)
        ), "timeout must be > settings.idle_detection_time"
        assert recv_timeout < self.ftp_settings.retry_time, "recv_timeout must be < settings.retry_time"  # noqa: S101

        while True:  # an FTP operation can have multiple responses
            m = self.master.recv_match(type=["FILE_TRANSFER_PROTOCOL"], timeout=recv_timeout)
            if m is not None:
                if operation_name == "TerminateSession":
                    # self.silently_discard_terminate_session_reply()
                    ret = MAVFTPReturn(operation_name, ERR_None)
                else:
                    ret = self.__mavlink_packet(m)
            if self.__idle_task():
                break
            if timeout > 0 and time.time() - start_time > timeout:  # pylint: disable=chained-comparison
                logging.error("FTP: timed out after %f seconds", time.time() - start_time)
                ret = MAVFTPReturn(operation_name, ERR_RemoteReplyTimeout)
                break
        return ret

    def __decode_ftp_ack_and_nack(self, op: FTP_OP, operation_name: str = "") -> MAVFTPReturn:
        """Decode FTP Acknowledge reply."""
        system_error = 0
        invalid_error_code = 0
        operation_name_dict = {
            OP_None: "None",
            OP_TerminateSession: "TerminateSession",
            OP_ResetSessions: "ResetSessions",
            OP_ListDirectory: "ListDirectory",
            OP_OpenFileRO: "OpenFileRO",
            OP_ReadFile: "ReadFile",
            OP_CreateFile: "CreateFile",
            OP_WriteFile: "WriteFile",
            OP_RemoveFile: "RemoveFile",
            OP_CreateDirectory: "CreateDirectory",
            OP_RemoveDirectory: "RemoveDirectory",
            OP_OpenFileWO: "OpenFileWO",
            OP_TruncateFile: "TruncateFile",
            OP_Rename: "Rename",
            OP_CalcFileCRC32: "CalcFileCRC32",
            OP_BurstReadFile: "BurstReadFile",
        }
        op_ret_name = operation_name or operation_name_dict.get(op.req_opcode, "Unknown")
        len_payload = len(op.payload) if op.payload is not None else 0
        if op.opcode == OP_Ack:
            error_code = ERR_None
        elif op.opcode == OP_Nack:
            if len_payload <= 0:
                error_code = ERR_NoErrorCodeInPayload
            elif len_payload == 1:
                error_code = op.payload[0]
                if error_code == ERR_None:
                    error_code = ERR_NoErrorCodeInNack
                elif error_code == ERR_FailErrno:
                    error_code = ERR_NoFilesystemErrorInPayload
                elif error_code not in {
                    ERR_Fail,
                    ERR_InvalidDataSize,
                    ERR_InvalidSession,
                    ERR_NoSessionsAvailable,
                    ERR_EndOfFile,
                    ERR_UnknownCommand,
                    ERR_FileExists,
                    ERR_FileProtected,
                    ERR_FileNotFound,
                }:
                    invalid_error_code = error_code
                    error_code = ERR_InvalidErrorCode
            elif op.payload[0] == ERR_FailErrno and len_payload == 2:
                system_error = op.payload[1]
                error_code = ERR_FailErrno
            else:
                error_code = ERR_PayloadTooLarge
        else:
            error_code = ERR_InvalidOpcode
        return MAVFTPReturn(
            op_ret_name,
            error_code,
            system_error=system_error,
            invalid_error_code=invalid_error_code,
            invalid_payload_size=len_payload,
            invalid_opcode=op.opcode,
        )

    @staticmethod
    def ftp_param_decode(data: bytes) -> Union[None, ParamData]:  # pylint: disable=too-many-locals
        """Decode parameter data, returning ParamData."""
        pdata = ParamData()

        magic = 0x671B
        magic_defaults = 0x671C
        if len(data) < 6:
            logging.error("paramftp: Not enough data do decode, only %u bytes", len(data))
            return None
        magic2, _num_params, total_params = struct.unpack("<HHH", data[0:6])
        if magic2 not in {magic, magic_defaults}:
            logging.error("paramftp: bad magic 0x%x expected 0x%x", magic2, magic)
            return None
        with_defaults = magic2 == magic_defaults
        data = data[6:]

        # mapping of data type to type length and format
        data_types = {
            1: (1, "b"),
            2: (2, "h"),
            3: (4, "i"),
            4: (4, "f"),
        }

        count = 0
        pad_byte = 0
        last_name = b""
        while True:
            while len(data) > 0 and data[0] == pad_byte:
                data = data[1:]  # skip pad bytes

            if len(data) == 0:
                break

            ptype, plen = struct.unpack("<BB", data[0:2])
            flags = (ptype >> 4) & 0x0F
            has_default = with_defaults and (flags & 1) != 0
            ptype &= 0x0F

            if ptype not in data_types:
                logging.error("paramftp: bad type 0x%x", ptype)
                return None

            (type_len, type_format) = data_types[ptype]
            default_len = type_len if has_default else 0

            name_len = ((plen >> 4) & 0x0F) + 1
            common_len = plen & 0x0F
            name = last_name[0:common_len] + data[2 : 2 + name_len]
            vdata = data[2 + name_len : 2 + name_len + type_len + default_len]
            last_name = name
            data = data[2 + name_len + type_len + default_len :]
            if with_defaults:
                if has_default:
                    (
                        v1,
                        v2,
                    ) = struct.unpack("<" + type_format + type_format, vdata)
                    pdata.add_param(name, v1, ptype)
                    pdata.add_default(name, v2, ptype)
                else:
                    (v,) = struct.unpack("<" + type_format, vdata)
                    pdata.add_param(name, v, ptype)
                    pdata.add_default(name, v, ptype)
            else:
                (v,) = struct.unpack("<" + type_format, vdata)
                pdata.add_param(name, v, ptype)
            count += 1

        if count != total_params:
            logging.error("paramftp: bad count %u should be %u", count, total_params)
            return None

        return pdata

    @staticmethod
    def missionplanner_sort(item: str) -> tuple[str, ...]:
        """Sorts a parameter name according to the rules defined in the Mission Planner software."""
        return tuple(item.split("_"))

    @staticmethod
    def extract_params(pdata: list[tuple[bytes, float, type]], sort_type: str) -> dict[str, tuple[float, type]]:
        """Extract parameter values to an optionally sorted dictionary of name->(value, type)."""
        pdict = {}
        if pdata:
            for name, value, ptype in pdata:
                pdict[name.decode("utf-8")] = (value, ptype)

            if sort_type == "missionplanner":
                pdict = dict(sorted(pdict.items(), key=lambda x: MAVFTP.missionplanner_sort(x[0])))  # sort alphabetically
            elif sort_type == "mavproxy":
                pdict = dict(sorted(pdict.items()))  # sort in ASCIIbetical order
            elif sort_type == "none":
                pass
        return pdict

    @staticmethod
    def save_params(
        pdict: dict[str, tuple[float, str]],
        filename: str,
        sort_type: str,
        add_datatype_comments: bool,
        add_timestamp_comment: bool,
    ) -> None:
        """Save Ardupilot parameter information to a local file."""
        if not pdict:
            return
        with open(filename, "w", encoding="utf-8") as f:
            parameter_data_types = {
                "1": "8-bit",
                "2": "16-bit",
                "3": "32-bit integer",
                "4": "32-bit float",
            }
            if add_timestamp_comment:
                f.write(f"# Parameters saved at {datetime.now(tz=None).strftime('%Y-%m-%d %H:%M:%S')}\n")
            for name, (value, datatype) in pdict.items():
                if sort_type == "missionplanner":
                    f.write(f"{name},{format(value, '.6f').rstrip('0').rstrip('.')}")
                elif sort_type in {"mavproxy", "none"}:
                    f.write(f"{name:<16} {value:<8.6f}")

                if add_datatype_comments:
                    f.write(f"  # {parameter_data_types[datatype]}")
                f.write("\n")
        logging.info("Outputted %u parameters to %s", len(pdict), filename)

    def cmd_getparams(  # pylint: disable=too-many-arguments, too-many-positional-arguments
        self,
        args,
        progress_callback=None,
        sort_type: str = "missionplanner",
        add_datatype_comments: bool = False,
        add_timestamp_comment: bool = False,
    ) -> MAVFTPReturn:
        """Decode the parameter file and save the values and defaults to disk."""

        def decode_and_save_params(fh) -> MAVFTPReturn:
            if fh is None:
                logging.error("FTP: no parameter file handler")
                return MAVFTPReturn("GetParams", ERR_Fail)
            try:
                data = fh.read()
            except OSError as exp:
                logging.error("FTP: Failed to read file param.pck: %s", exp)
                sys.exit(1)
            pdata = MAVFTP.ftp_param_decode(data)
            if pdata is None:
                sys.exit(1)

            param_values = MAVFTP.extract_params(pdata.params, sort_type)
            param_defaults = MAVFTP.extract_params(pdata.defaults, sort_type)

            param_values_path = args[0]
            param_defaults_path = args[1] if len(args) > 1 else None

            MAVFTP.save_params(param_values, param_values_path, sort_type, add_datatype_comments, add_timestamp_comment)
            MAVFTP.save_params(param_defaults, param_defaults_path, sort_type, add_datatype_comments, add_timestamp_comment)

            if self.ftp_settings.debug > 0:
                for name, (value, _param_type) in param_values.items():
                    if name in param_defaults:
                        logging.info("%-16s %f (default %f)", name, value, param_defaults[name][0])
                    else:
                        logging.info("%-16s %f", name, value)
            return MAVFTPReturn("GetParams", ERR_None)

        return self.cmd_get(
            ["@PARAM/param.pck?withdefaults=1" if len(args) > 1 else "@PARAM/param.pck"],
            callback=decode_and_save_params,
            progress_callback=progress_callback,
        )


# ------------------------------------------------------------
# These functions are to use this script as a standalone tool
# ------------------------------------------------------------


def create_argument_parser() -> ArgumentParser:
    """
    Parses command-line arguments for the script.

    This function sets up an argument parser to handle the command-line arguments for the script.
    """
    parser = ArgumentParser(
        description="MAVFTP - MAVLink File Transfer Protocol https://mavlink.io/en/services/ftp.html"
        " A tool to do file operations between a ground control station and a drone using the MAVLink"
        " protocol."
    )
    parser.add_argument("--baudrate", type=int, default=115200, help="master port baud rate. Default is %(default)s")
    parser.add_argument(  # type: ignore[attr-defined]
        "--device",
        type=str,
        default="",
        help="serial device. For windows use COMx where x is the port number. "
        "For Unix use /dev/ttyUSBx where x is the port number. Default is autodetection",
    ).completer = FilesCompleter(directories=False, allowednames=[".port"])  # type: ignore[no-untyped-call]
    parser.add_argument(
        "--source-system", type=int, default=250, help="MAVLink source system for this GCS. Default is %(default)s"
    )
    parser.add_argument("--loglevel", default="INFO", help="log level. Default is %(default)s")

    # MAVFTP settings
    parser.add_argument(
        "--debug",
        type=int,
        default=0,
        choices=[0, 1, 2],
        help="Debug level 0 for none, 2 for max verbosity. Default is %(default)s",
    )
    parser.add_argument("--pkt_loss_tx", type=int, default=0, help="Packet loss on TX. Default is %(default)s")
    parser.add_argument("--pkt_loss_rx", type=int, default=0, help="Packet loss on RX. Default is %(default)s")
    parser.add_argument("--max_backlog", type=int, default=5, help="Max backlog. Default is %(default)s")
    parser.add_argument("--burst_read_size", type=int, default=80, help="Burst read size. Default is %(default)s")
    parser.add_argument("--write_size", type=int, default=80, help="Write size. Default is %(default)s")
    parser.add_argument("--write_qsize", type=int, default=5, help="Write queue size. Default is %(default)s")
    parser.add_argument("--idle_detection_time", type=float, default=1.2, help="Idle detection time. Default is %(default)s")
    parser.add_argument("--read_retry_time", type=float, default=1.0, help="Read retry time. Default is %(default)s")
    parser.add_argument("--retry_time", type=float, default=0.5, help="Retry time. Default is %(default)s")

    subparsers = parser.add_subparsers(dest="command", required=True)

    # Get command
    parser_get = subparsers.add_parser("get", help="Get a file from the remote flight controller.")
    parser_get.add_argument("arg1", type=str, metavar="remote_path", help="Path to the file on the remote flight controller.")
    parser_get.add_argument(  # type: ignore[attr-defined]
        "arg2", nargs="?", type=str, metavar="local_path", help="Optional local path to save the file."
    ).completer = FilesCompleter()  # type: ignore[no-untyped-call]

    # Getparams command
    parser_getparams = subparsers.add_parser("getparams", help="Get and decode parameters from the remote flight controller.")
    parser_getparams.add_argument(  # type: ignore[attr-defined]
        "arg1", type=str, metavar="param_values_path", help="Local path to save the parameter values file to."
    ).completer = FilesCompleter()  # type: ignore[no-untyped-call]
    parser_getparams.add_argument(  # type: ignore[attr-defined]
        "arg2",
        nargs="?",
        type=str,
        metavar="param_defaults_path",
        help="Optional local path to save the parameter defaults file to.",
    ).completer = FilesCompleter()  # type: ignore[no-untyped-call]
    parser_getparams.add_argument(
        "-s",
        "--sort",
        choices=["none", "missionplanner", "mavproxy"],
        default="missionplanner",
        help="Sort the parameters in the file. Default is %(default)s.",
    )
    parser_getparams.add_argument(
        "-dtc",
        "--add_datatype_comments",
        action="store_true",
        default=False,
        help="Add parameter datatype type comments to the outputted parameter files. Default is %(default)s.",
    )
    parser_getparams.add_argument(
        "-t",
        "--add_timestamp_comment",
        action="store_true",
        default=False,
        help="Add timestamp comment at the top of the file. Default is %(default)s.",
    )

    # Put command
    parser_put = subparsers.add_parser("put", help="Put a file to the remote flight controller.")
    parser_put.add_argument(  # type: ignore[attr-defined]
        "arg1", type=str, metavar="local_path", help="Local path to the file to upload to the flight controller."
    ).completer = FilesCompleter()  # type: ignore[no-untyped-call]
    parser_put.add_argument(
        "arg2",
        nargs="?",
        type=str,
        metavar="remote_path",
        help="Optional remote path where the file should be uploaded on the remote flight controller.",
    )

    # List command
    parser_list = subparsers.add_parser("list", help="List files in a directory on the remote flight controller.")
    parser_list.add_argument("arg1", nargs="?", type=str, metavar="remote_path", help="Optional path to list files from.")

    # Mkdir command
    parser_mkdir = subparsers.add_parser("mkdir", help="Create a directory on the remote flight controller.")
    parser_mkdir.add_argument("arg1", type=str, metavar="remote_path", help="Path to the directory to create.")

    # Rmdir command
    parser_rmdir = subparsers.add_parser("rmdir", help="Remove a directory on the remote flight controller.")
    parser_rmdir.add_argument("arg1", type=str, metavar="remote_path", help="Path to the directory to remove.")

    # Rm command
    parser_rm = subparsers.add_parser("rm", help="Remove a file on the remote flight controller.")
    parser_rm.add_argument("arg1", type=str, metavar="remote_path", help="Path to the file to remove.")

    # Rename command
    parser_rename = subparsers.add_parser("rename", help="Rename a file or directory on the remote flight controller.")
    parser_rename.add_argument("arg1", type=str, metavar="old_remote_path", help="Current path of the file/directory.")
    parser_rename.add_argument("new_remote_path", type=str, metavar="arg2", help="New path for the file/directory.")

    # CRC command
    parser_crc = subparsers.add_parser("crc", help="Calculate the CRC of a file on the remote flight controller.")
    parser_crc.add_argument("arg1", type=str, metavar="remote_path", help="Path to the file to calculate the CRC of.")

    # Add other subparsers commands as needed
    argcomplete.autocomplete(parser)
    return parser


def auto_detect_serial() -> list[mavutil.SerialPort]:
    preferred_ports = [
        "*FTDI*",
        "*3D*",
        "*USB_to_UART*",
        "*Ardu*",
        "*PX4*",
        "*Hex_*",
        "*Holybro_*",
        "*mRo*",
        "*FMU*",
        "*Swift-Flyer*",
        "*Serial*",
        "*CubePilot*",
        "*Qiotek*",
    ]
    serial_list: list[mavutil.SerialPort] = mavutil.auto_detect_serial(preferred_list=preferred_ports)
    serial_list.sort(key=lambda x: x.device)

    # remove OTG2 ports for dual CDC
    if (
        len(serial_list) == 2
        and serial_list[0].device.startswith("/dev/serial/by-id")
        and serial_list[0].device[:-1] == serial_list[1].device[0:-1]
    ):
        serial_list.pop(1)

    return serial_list


def auto_connect(device) -> mavutil.SerialPort:
    comport = None
    if device:
        comport = mavutil.SerialPort(device=device, description=device)
    else:
        autodetect_serial = auto_detect_serial()
        if autodetect_serial:
            # Resolve the soft link if it's a Linux system
            if os.name == "posix":
                try:
                    dev = autodetect_serial[0].device
                    logging.debug("Auto-detected device %s", dev)
                    # Get the directory part of the soft link
                    softlink_dir = os.path.dirname(dev)
                    # Resolve the soft link and join it with the directory part
                    resolved_path = os.path.abspath(os.path.join(softlink_dir, os.readlink(dev)))
                    autodetect_serial[0].device = resolved_path
                    logging.debug("Resolved soft link %s to %s", dev, resolved_path)
                except OSError:
                    pass  # Not a soft link, proceed with the original device path
            comport = autodetect_serial[0]
        else:
            logging.error("No serial ports found. Please connect a flight controller and try again.")
            sys.exit(1)
    return comport


def wait_heartbeat(m) -> None:
    """Wait for a heartbeat so we know the target system IDs."""
    logging.info("Waiting for flight controller heartbeat")
    m.wait_heartbeat(timeout=5)
    logging.info("Heartbeat from system %u, component %u", m.target_system, m.target_system)


def main() -> None:
    """For testing/example purposes only."""
    args = create_argument_parser().parse_args()

    logging.basicConfig(level=logging.getLevelName(args.loglevel), format="%(levelname)s - %(message)s")

    # create a mavlink serial instance
    comport = auto_connect(args.device)
    master = mavutil.mavlink_connection(comport.device, baud=args.baudrate, source_system=args.source_system)

    # wait for the heartbeat msg to find the system ID
    wait_heartbeat(master)

    ftp_settings = MAVFTPSettings(
        [
            ("debug", int, args.debug),
            ("pkt_loss_tx", int, args.pkt_loss_tx),
            ("pkt_loss_rx", int, args.pkt_loss_rx),
            ("max_backlog", int, args.max_backlog),
            ("burst_read_size", int, args.burst_read_size),
            ("write_size", int, args.write_size),
            ("write_qsize", int, args.write_qsize),
            ("idle_detection_time", float, args.idle_detection_time),
            ("read_retry_time", float, args.read_retry_time),
            ("retry_time", float, args.retry_time),
        ]
    )

    mav_ftp = MAVFTP(
        master, target_system=master.target_system, target_component=master.target_component, settings=ftp_settings
    )

    cmd_ftp_args = [args.command]
    if "arg1" in args and args.arg1:
        cmd_ftp_args.append(args.arg1)
    if "arg2" in args and args.arg2:
        cmd_ftp_args.append(args.arg2)

    ret = mav_ftp.cmd_ftp(cmd_ftp_args)

    if args.command in {"get", "put", "getparams"}:
        ret = mav_ftp.process_ftp_reply(args.command, timeout=500)

    if isinstance(ret, str):
        logging.error("Command returned: %s, but it should return a MAVFTPReturn instead", ret)
    elif isinstance(ret, MAVFTPReturn):
        if ret.error_code:
            ret.display_message()
    elif ret is None:
        logging.error("Command returned: None, but it should return a MAVFTPReturn instead")
    else:
        logging.error("Command returned: something strange, but it should return a MAVFTPReturn instead")

    master.close()


if __name__ == "__main__":
    main()
