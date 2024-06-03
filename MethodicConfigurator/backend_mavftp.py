#!/usr/bin/env python3

'''
MAVLink File Transfer Protocol support
Original from MAVProxy/MAVProxy/modules/mavproxy_ftp.py

This file is part of Ardupilot methodic configurator. https://github.com/ArduPilot/MethodicConfigurator

(C) 2024 Amilcar do Carmo Lucas

SPDX-License-Identifier:    GPL-3
'''

# pylint: skip-file

from sys import exit as sys_exit

from argparse import ArgumentParser

from logging import basicConfig as logging_basicConfig
from logging import getLevelName as logging_getLevelName
from logging import debug as logging_debug
from logging import info as logging_info
from logging import warning as logging_warning
# from logging import error as logging_error

import struct
from time import time as time_time
from random import uniform as random_uniform
from os import path as os_path
from typing import Dict

from io import BytesIO as SIO

# from param_ftp import ParamData
from MethodicConfigurator.param_ftp import ftp_param_decode

from MethodicConfigurator.common_arguments import add_common_arguments_and_parse

from MethodicConfigurator.backend_flightcontroller import FlightController

# adding all this allows pyinstaller to build a working Windows executable
# note that using --hidden-import does not work for these modules
try:
    from pymavlink import mavutil
    from pymavlink import mavparm
except ImportError:
    pass

# pylint: disable=invalid-name
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

HDR_Len = 12
MAX_Payload = 239
# pylint: enable=invalid-name

class FTP_OP:  # pylint: disable=missing-class-docstring, invalid-name, too-many-instance-attributes
    def __init__(self, seq, session, opcode, size,  # pylint: disable=too-many-arguments
                 req_opcode, burst_complete, offset, payload):
        self.seq = seq
        self.session = session
        self.opcode = opcode
        self.size = size
        self.req_opcode = req_opcode
        self.burst_complete = burst_complete
        self.offset = offset
        self.payload = payload

    def pack(self):
        '''pack message'''
        ret = struct.pack("<HBBBBBBI", self.seq, self.session, self.opcode, self.size, self.req_opcode, self.burst_complete,
                          0, self.offset)
        if self.payload is not None:
            ret += self.payload
        ret = bytearray(ret)
        return ret

    def __str__(self):
        plen = 0
        if self.payload is not None:
            plen = len(self.payload)
        ret = f"OP seq:{self.seq} sess:{self.session} opcode:{self.opcode} req_opcode:{self.req_opcode}" \
              f" size:{self.size} bc:{self.burst_complete} ofs:{self.offset} plen={plen}"
        if plen > 0:
            ret += f" [{self.payload[0]}]"
        return ret


class WriteQueue:  # pylint: disable=missing-class-docstring, too-few-public-methods
    def __init__(self, ofs, size):
        self.ofs = ofs
        self.size = size
        self.last_send = 0


class MAVFTP:  # pylint: disable=missing-class-docstring, too-many-instance-attributes
    def __init__(self, master, target_system, target_component):
        self.ftp_settings_debug = 2
        self.ftp_settings_pkt_loss_rx = 0
        self.ftp_settings_pkt_loss_tx = 0
        self.ftp_settings_burst_read_size = 80
        self.ftp_settings_max_backlog = 5
        self.ftp_settings_retry_time = 0.5
        self.seq = 0
        self.session = 0
        self.network = 0
        self.last_op = None
        self.fh = None
        self.filename = None
        self.callback = None
        self.callback_progress = None
        self.put_callback = None
        self.put_callback_progress = None
        self.read_gaps = []
        self.read_gap_times = {}
        self.last_gap_send = 0
        self.read_retries = 0
        self.read_total = 0
        self.duplicates = 0
        self.last_read = None
        self.last_burst_read = None
        self.op_start = None
        self.last_op_time = time_time()
        self.rtt = 0.5
        self.reached_eof = False
        self.backlog = 0
        self.burst_size = self.ftp_settings_burst_read_size
        self.write_list = None
        self.open_retries = 0

        self.ftp_count = None
        self.ftp_started = False
        self.ftp_failed = False
        self.mav_param_set = set()
        self.param_types = {}
        self.fetch_one = {}
        self.fetch_set = None
        self.mav_param = mavparm.MAVParmDict()
        self.mav_param_count = 0
        self.default_params = None
        self.warned_component = False
        self.master = master
        self.target_system = target_system
        self.target_component = target_component
        master.message_hooks.append(self.mavlink_packet)

    def send(self, op):
        '''send a request'''
        op.seq = self.seq
        payload = op.pack()
        plen = len(payload)
        if plen < MAX_Payload + HDR_Len:
            payload.extend(bytearray([0]*((HDR_Len+MAX_Payload)-plen)))
        self.master.mav.file_transfer_protocol_send(self.network, self.target_system, self.target_component, payload)
        self.seq = (self.seq + 1) % 256
        self.last_op = op
        now = time_time()
        if self.ftp_settings_debug > 1:
            logging_info("> %s dt=%.2f", op, now - self.last_op_time)
        self.last_op_time = time_time()

    def terminate_session(self):
        '''terminate current session'''
        self.send(FTP_OP(self.seq, self.session, OP_TerminateSession, 0, 0, 0, 0, None))
        self.fh = None
        self.filename = None
        self.write_list = None
        if self.callback is not None:
            # tell caller that the transfer failed
            self.callback(None)
            self.callback = None
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
        self.session = (self.session + 1) % 256
        self.reached_eof = False
        self.backlog = 0
        self.duplicates = 0
        if self.ftp_settings_debug > 0:
            logging_info("Terminated session")

    def cmd_get(self, args, callback=None, callback_progress=None):
        '''get file'''
        self.terminate_session()
        fname = args[0]
        if len(args) > 1:
            self.filename = args[1]
        else:
            self.filename = os_path.basename(fname)
        if callback is None or self.ftp_settings_debug > 1:
            logging_info("Getting %s as %s", fname, self.filename)
        self.op_start = time_time()
        self.callback = callback
        self.callback_progress = callback_progress
        self.read_retries = 0
        self.duplicates = 0
        self.reached_eof = False
        self.burst_size = self.ftp_settings_burst_read_size
        if self.burst_size < 1:
            self.burst_size = 239
        elif self.burst_size > 239:
            self.burst_size = 239
        enc_fname = bytearray(fname, 'ascii')
        self.open_retries = 0
        op = FTP_OP(self.seq, self.session, OP_OpenFileRO, len(enc_fname), 0, 0, 0, enc_fname)
        self.send(op)

    def handle_open_ro_reply(self, op, _m):
        '''handle OP_OpenFileRO reply'''
        if op.opcode == OP_Ack:
            if self.filename is None:
                return
            try:
                if self.callback is not None or self.filename == '-':
                    self.fh = SIO()
                else:
                    self.fh = open(self.filename, 'wb')  # pylint: disable=consider-using-with
            except Exception as ex:  # pylint: disable=broad-except
                logging_info("Failed to open %s: %s", self.filename, ex)
                self.terminate_session()
                return
            read = FTP_OP(self.seq, self.session, OP_BurstReadFile, self.burst_size, 0, 0, 0, None)
            self.last_burst_read = time_time()
            self.send(read)
        else:
            if self.callback is None or self.ftp_settings_debug > 0:
                logging_info("ftp open failed")
            self.terminate_session()

    def check_read_finished(self):
        '''check if download has completed'''
        if self.reached_eof and len(self.read_gaps) == 0:
            ofs = self.fh.tell()
            dt = time_time() - self.op_start
            rate = (ofs / dt) / 1024.0
            if self.callback is not None:
                self.fh.seek(0)
                self.callback(self.fh)
                self.callback = None
            elif self.filename == "-":
                self.fh.seek(0)
                logging_info(self.fh.read().decode('utf-8'))
            else:
                logging_info("Wrote %u bytes to %s in %.2fs %.1fkByte/s", ofs, self.filename, dt, rate)
            self.terminate_session()
            return True
        return False

    def write_payload(self, op):
        '''write payload from a read op'''
        self.fh.seek(op.offset)
        self.fh.write(op.payload)
        self.read_total += len(op.payload)
        if self.callback_progress is not None:
            self.callback_progress(self.fh, self.read_total)

    def handle_burst_read(self, op, _m):  # pylint: disable=too-many-branches, too-many-statements, too-many-return-statements
        '''handle OP_BurstReadFile reply'''
        if self.ftp_settings_pkt_loss_tx > 0:
            if random_uniform(0, 100) < self.ftp_settings_pkt_loss_tx:
                if self.ftp_settings_debug > 0:
                    logging_info("FTP: dropping TX")
                return
        if self.fh is None or self.filename is None:
            if op.session != self.session:
                # old session
                return
            logging_info("FTP Unexpected burst read reply")
            logging_info(op)
            return
        self.last_burst_read = time_time()
        size = len(op.payload)
        if size > self.burst_size:
            # this server doesn't handle the burst size argument
            self.burst_size = MAX_Payload
            if self.ftp_settings_debug > 0:
                logging_info("Setting burst size to %u", self.burst_size)
        if op.opcode == OP_Ack and self.fh is not None:
            ofs = self.fh.tell()
            if op.offset < ofs:
                # writing an earlier portion, possibly remove a gap
                gap = (op.offset, len(op.payload))
                if gap in self.read_gaps:
                    self.read_gaps.remove(gap)
                    self.read_gap_times.pop(gap)
                    if self.ftp_settings_debug > 0:
                        logging_info("FTP: removed gap", gap, self.reached_eof, len(self.read_gaps))
                else:
                    if self.ftp_settings_debug > 0:
                        logging_info("FTP: dup read reply at %u of len %u ofs=%u", op.offset, op.size, self.fh.tell())
                    self.duplicates += 1
                    return
                self.write_payload(op)
                self.fh.seek(ofs)
                if self.check_read_finished():
                    return
            elif op.offset > ofs:
                # we have a gap
                gap = (ofs, op.offset-ofs)
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
                self.write_payload(op)
            else:
                self.write_payload(op)
            if op.burst_complete:
                if op.size > 0 and op.size < self.burst_size:
                    # a burst complete with non-zero size and less than burst packet size
                    # means EOF
                    if not self.reached_eof and self.ftp_settings_debug > 0:
                        logging_info("EOF at %u with %u gaps t=%.2f", self.fh.tell(),
                                     len(self.read_gaps), time_time() - self.op_start)
                    self.reached_eof = True
                    if self.check_read_finished():
                        return
                    self.check_read_send()
                    return
                more = self.last_op
                more.offset = op.offset + op.size
                if self.ftp_settings_debug > 0:
                    logging_info("FTP: burst continue at %u %u", more.offset, self.fh.tell())
                self.send(more)
        elif op.opcode == OP_Nack:
            ecode = op.payload[0]
            if self.ftp_settings_debug > 0:
                logging_info("FTP: burst nack: ", op)
            if ecode in (ERR_EndOfFile, 0):
                if not self.reached_eof and op.offset > self.fh.tell():
                    # we lost the last part of the burst
                    if self.ftp_settings_debug > 0:
                        logging_info("burst lost EOF %u %u", self.fh.tell(), op.offset)
                    return
                if not self.reached_eof and self.ftp_settings_debug > 0:
                    logging_info("EOF at %u with %u gaps t=%.2f", self.fh.tell(),
                                 len(self.read_gaps), time_time() - self.op_start)
                self.reached_eof = True
                if self.check_read_finished():
                    return
                self.check_read_send()
            elif self.ftp_settings_debug > 0:
                logging_info("FTP: burst Nack (ecode:%u): %s", ecode, op)
        else:
            logging_info("FTP: burst error: %s", op)

    def handle_reply_read(self, op, _m):
        '''handle OP_ReadFile reply'''
        if self.fh is None or self.filename is None:
            if self.ftp_settings_debug > 0:
                logging_info("FTP Unexpected read reply")
                logging_info(op)
            return
        if self.backlog > 0:
            self.backlog -= 1
        if op.opcode == OP_Ack and self.fh is not None:
            gap = (op.offset, op.size)
            if gap in self.read_gaps:
                self.read_gaps.remove(gap)
                self.read_gap_times.pop(gap)
                ofs = self.fh.tell()
                self.write_payload(op)
                self.fh.seek(ofs)
                if self.ftp_settings_debug > 0:
                    logging_info("FTP: removed gap", gap, self.reached_eof, len(self.read_gaps))
                if self.check_read_finished():
                    return
            elif op.size < self.burst_size:
                logging_info("FTP: file size changed to %u", op.offset+op.size)
                self.terminate_session()
            else:
                self.duplicates += 1
                if self.ftp_settings_debug > 0:
                    logging_info("FTP: no gap read", gap, len(self.read_gaps))
        elif op.opcode == OP_Nack:
            logging_info("Read failed with %u gaps", len(self.read_gaps), str(op))
            self.terminate_session()
        self.check_read_send()

    def op_parse(self, m):
        '''parse a FILE_TRANSFER_PROTOCOL msg'''
        hdr = bytearray(m.payload[0:12])
        (seq, session, opcode, size, req_opcode, burst_complete, _pad, offset) = struct.unpack("<HBBBBBBI", hdr)
        payload = bytearray(m.payload[12:])[:size]
        return FTP_OP(seq, session, opcode, size, req_opcode, burst_complete, offset, payload)

    def mavlink_packet(self, m):
        '''handle a mavlink packet'''
        mtype = m.get_type()
        logging_info("Received MAVLink message: %s", mtype)
        if mtype == "FILE_TRANSFER_PROTOCOL":
            if m.target_system != self.target_system or m.target_component != self.target_component:
                if m.target_system == self.target_component and not self.warned_component:
                    self.warned_component = True
                    logging_info("FTP reply for mavlink component %u", m.target_component)
                return

            op = self.op_parse(m)
            now = time_time()
            dt = now - self.last_op_time
            if self.ftp_settings_debug > 1:
                logging_info("< %s dt=%.2f", op, dt)
            self.last_op_time = now
            if self.ftp_settings_pkt_loss_rx > 0:
                if random_uniform(0, 100) < self.ftp_settings_pkt_loss_rx:
                    if self.ftp_settings_debug > 1:
                        logging_info("FTP: dropping packet RX")
                    return

            if op.req_opcode == self.last_op.opcode and op.seq == (self.last_op.seq + 1) % 256:
                self.rtt = max(min(self.rtt, dt), 0.01)
            if op.req_opcode == OP_OpenFileRO:
                self.handle_open_ro_reply(op, m)
            elif op.req_opcode == OP_BurstReadFile:
                self.handle_burst_read(op, m)
            elif op.req_opcode == OP_TerminateSession:
                pass
            # elif op.req_opcode == OP_WriteFile:
            #    self.handle_write_reply(op, m)
            # elif op.req_opcode in [OP_RemoveFile, OP_RemoveDirectory]:
            #     self.handle_remove_reply(op, m)
            # elif op.req_opcode == OP_ReadFile:
            #    self.handle_reply_read(op, m)
            else:
                logging_info('FTP Unknown %s', str(op))

    def send_gap_read(self, g):
        '''send a read for a gap'''
        (offset, length) = g
        if self.ftp_settings_debug > 0:
            logging_info("Gap read of %u at %u rem=%u blog=%u", length, offset, len(self.read_gaps), self.backlog)
        read = FTP_OP(self.seq, self.session, OP_ReadFile, length, 0, 0, offset, None)
        self.send(read)
        self.read_gaps.remove(g)
        self.read_gaps.append(g)
        self.last_gap_send = time_time()
        self.read_gap_times[g] = self.last_gap_send
        self.backlog += 1

    def check_read_send(self):
        '''see if we should send another gap read'''
        if len(self.read_gaps) == 0:
            return
        g = self.read_gaps[0]
        now = time_time()
        dt = now - self.read_gap_times[g]
        if not self.reached_eof:
            # send gap reads once
            for g, v in self.read_gap_times.items():
                if v == 0:
                    self.send_gap_read(g)
            return
        if self.read_gap_times[g] > 0 and dt > self.ftp_settings_retry_time:
            if self.backlog > 0:
                self.backlog -= 1
            self.read_gap_times[g] = 0

        if self.read_gap_times[g] != 0:
            # still pending
            return
        if not self.reached_eof and self.backlog >= self.ftp_settings_max_backlog:
            # don't fill queue too far until we have got past the burst
            return
        if now - self.last_gap_send < 0.05:
            # don't send too fast
            return
        self.send_gap_read(g)

    def idle_task(self):
        '''check for file gaps and lost requests'''
        now = time_time()

        # see if we lost an open reply
        if self.op_start is not None and now - self.op_start > 1.0 and self.last_op.opcode == OP_OpenFileRO:
            self.op_start = now
            self.open_retries += 1
            if self.open_retries > 2:
                # fail the get
                self.op_start = None
                self.terminate_session()
                return
            if self.ftp_settings_debug > 0:
                logging_info("FTP: retry open")
            send_op = self.last_op
            self.send(FTP_OP(self.seq, self.session, OP_TerminateSession, 0, 0, 0, 0, None))
            self.session = (self.session + 1) % 256
            send_op.session = self.session
            self.send(send_op)

        if len(self.read_gaps) == 0 and self.last_burst_read is None and self.write_list is None:
            return

        if self.fh is None:
            return

        # see if burst read has stalled
        if not self.reached_eof and self.last_burst_read is not None and \
           now - self.last_burst_read > self.ftp_settings_retry_time:
            dt = now - self.last_burst_read
            self.last_burst_read = now
            if self.ftp_settings_debug > 0:
                logging_info("Retry read at %u rtt=%.2f dt=%.2f", self.fh.tell(), self.rtt, dt)
            self.send(FTP_OP(self.seq, self.session, OP_BurstReadFile, self.burst_size, 0, 0, self.fh.tell(), None))
            self.read_retries += 1

        # see if we can fill gaps
        self.check_read_send()

        #if self.write_list is not None:
        #    self.send_more_writes()

    def read_params_via_mavftp(self, progress_callback=None) -> Dict[str, float]:
        """
        Reads parameter values and defaults from the flight controller using MAVFTP.

        Args:
            progress_callback (function, optional): A callback function to report progress.
        """
        self.ftp_started = True
        self.ftp_count = None
        self.cmd_get(["@PARAM/param.pck?withdefaults=1"], callback=self.ftp_callback,
                     callback_progress=self.ftp_callback_progress)

        while self.ftp_started:
            self.idle_task()
            if progress_callback:
                progress_callback()

        return self.mav_param, self.default_params

    def ftp_callback_progress(self, fh, total_size):
        '''callback as read progresses'''
        logging_debug("ftp_callback_progress")
        if self.ftp_count is None and total_size >= 6:
            ofs = fh.tell()
            fh.seek(0)
            buf = fh.read(6)
            fh.seek(ofs)
            magic2, _num_params, total_params = struct.unpack("<HHH", buf)
            if magic2 in (0x671b, 0x671c):
                self.ftp_count = total_params
        # approximate count
        if self.ftp_count is not None:
            # each entry takes 11 bytes on average
            per_entry_size = 11
            done = min(int(total_size / per_entry_size), self.ftp_count-1)
            # self.mpstate.console.set_status('Params', 'Param %u/%u' % (done, self.ftp_count))
            logging_info("Received %u/%u parameters (ftp)", done, self.ftp_count)

    def ftp_callback(self, fh):
        '''callback from ftp fetch of parameters'''
        logging_debug("ftp_callback")
        self.ftp_started = False
        if fh is None:
            logging_debug("fetch failed")
            # the fetch failed
            self.ftp_failed = True
            return

        # magic = 0x671b
        # magic_defaults = 0x671c
        data = fh.read()
        pdata = ftp_param_decode(data)
        if pdata is None or len(pdata.params) == 0:
            return
        with_defaults = pdata.defaults is not None

        self.param_types = {}
        self.mav_param_set = set()
        self.fetch_one = {}
        self.fetch_set = None
        self.mav_param.clear()
        total_params = len(pdata.params)
        self.mav_param_count = total_params

        idx = 0
        for (name, v, _ptype) in pdata.params:
            # we need to set it to REAL32 to ensure we use write value for param_set
            name = str(name.decode('utf-8'))
            self.param_types[name] = mavutil.mavlink.MAV_PARAM_TYPE_REAL32
            self.mav_param_set.add(idx)
            self.mav_param[name] = v
            idx += 1

        self.ftp_failed = False
        logging_info("Received %u parameters (ftp)", total_params)
        # if self.logdir is not None:
        #    self.mav_param.save(os.path.join(self.logdir, self.parm_file), '*', verbose=True)
        # self.log_params(pdata.params)

        if with_defaults:
            self.default_params = mavparm.MAVParmDict()
            for (name, v, _ptype) in pdata.defaults:
                name = str(name.decode('utf-8'))
                self.default_params[name] = v
        #    if self.logdir:
        #        defaults_path = os.path.join(self.logdir, "defaults.parm")
        #        self.default_params.save(defaults_path, '*', verbose=False)
        #        logging_info("Saved %u defaults to %s" % (len(pdata.defaults), defaults_path))

def argument_parser():
    """
    Parses command-line arguments for the script.

    This function sets up an argument parser to handle the command-line arguments for the script.

    Returns:
    argparse.Namespace: An object containing the parsed arguments.
    """
    parser = ArgumentParser(description='This main is for testing and development only. '
                            'Usually, the backend_mavftp is called from another script')
    parser = FlightController.add_argparse_arguments(parser)
    return add_common_arguments_and_parse(parser)


def main():
    args = argument_parser()

    logging_basicConfig(level=logging_getLevelName(args.loglevel), format='%(asctime)s - %(levelname)s - %(message)s')

    logging_warning("This main is for testing and development only. "
                    "Usually the backend_mavftp is called from another script")

    flight_controller = FlightController(args.reboot_time) # Initialize your FlightController instance
    result = flight_controller.connect(device=args.device) # Connect to the flight controller
    if result:
        logging_warning(result)
        sys_exit(1)

    # pylint: disable=protected-access
    mavftp = MAVFTP(flight_controller.master,
                    flight_controller._FlightController__target_system,
                    flight_controller._FlightController__target_component)
    # pylint: enable=protected-access

    mav_params, default_params = mavftp.read_params_via_mavftp() # Read parameters from the flight controller using MAVFTP
    print(mav_params) # Print the parameters
    print(default_params) # Print the default parameters

    flight_controller.disconnect() # Disconnect from the flight controller


if __name__ == "__main__":
    main()
