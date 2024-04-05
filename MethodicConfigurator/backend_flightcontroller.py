#!/usr/bin/env python3

'''
This file is part of Ardupilot methodic configurator. https://github.com/ArduPilot/MethodicConfigurator

AP_FLAKE8_CLEAN

(C) 2024 Amilcar do Carmo Lucas, IAV GmbH

SPDX-License-Identifier:    GPL-3
'''

from logging import debug as logging_debug
from logging import info as logging_info
from logging import warning as logging_warning
from logging import error as logging_error

# import sys
from time import sleep as time_sleep
from time import time as time_time
from os import path as os_path
from os import name as os_name
from os import readlink as os_readlink
from typing import Dict
import struct
from random import uniform as random_uniform
# import usb.core
# import usb.util
import serial.tools.list_ports
import serial.tools.list_ports_common

from serial.serialutil import SerialException
from annotate_params import Par

# from param_ftp import ParamData
from param_ftp import ftp_param_decode

from io import BytesIO as SIO

# adding all this allows pyinstaller to build a working windows executable
# note that using --hidden-import does not work for these modules
try:
    from pymavlink import mavutil
    from pymavlink import mavparm
except Exception:
    pass

# Get the current directory
# current_dir = os_path.dirname(os_path.abspath(__file__))

# Add the current directory to the PATH environment variable
# os.environ['PATH'] = os.environ['PATH'] + os.pathsep + current_dir

preferred_ports = [
    '*FTDI*',
    "*Arduino_Mega_2560*",
    "*3D*",
    "*USB_to_UART*",
    '*Ardu*',
    '*PX4*',
    '*Hex_*',
    '*Holybro_*',
    '*mRo*',
    '*FMU*',
    '*Swift-Flyer*',
    '*Serial*',
    '*CubePilot*',
    '*Qiotek*',
]


class FakeSerialForUnitTests():
    def __init__(self, device: str):
        self.device = device

    def read(self, _len):
        return ""

    def write(self, _buf):
        raise Exception("write always fails")

    def inWaiting(self):
        return 0

    def close(self):
        pass


def decode_flight_sw_version(flight_sw_version):
    '''decode 32 bit flight_sw_version mavlink parameter
    corresponds to ArduPilot encoding in  GCS_MAVLINK::send_autopilot_version'''
    fw_type_id = (flight_sw_version >>  0) % 256  # noqa E221, E222
    patch      = (flight_sw_version >>  8) % 256  # noqa E221, E222
    minor      = (flight_sw_version >> 16) % 256  # noqa E221
    major      = (flight_sw_version >> 24) % 256  # noqa E221
    if fw_type_id == 0:
        fw_type = "dev"
    elif fw_type_id == 64:
        fw_type = "alpha"
    elif fw_type_id == 128:
        fw_type = "beta"
    elif fw_type_id == 192:
        fw_type = "rc"
    elif fw_type_id == 255:
        fw_type = "official"
    else:
        fw_type = "undefined"
    return major, minor, patch, fw_type


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


class FTP_OP:
    def __init__(self, seq, session, opcode, size, req_opcode, burst_complete, offset, payload):
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
        ret = "OP seq:%u sess:%u opcode:%d req_opcode:%u size:%u bc:%u ofs:%u plen=%u" % (self.seq,
                                                                                          self.session,
                                                                                          self.opcode,
                                                                                          self.req_opcode,
                                                                                          self.size,
                                                                                          self.burst_complete,
                                                                                          self.offset,
                                                                                          plen)
        if plen > 0:
            ret += " [%u]" % self.payload[0]
        return ret


class WriteQueue:
    def __init__(self, ofs, size):
        self.ofs = ofs
        self.size = size
        self.last_send = 0


class FlightController:
    """
    A class to manage the connection and parameters of a flight controller.

    Attributes:
        device (str): The connection string to the flight controller.
        master (mavutil.mavlink_connection): The MAVLink connection object.
        fc_parameters (Dict[str, float]): A dictionary of flight controller parameters.
    """
    def __init__(self, reboot_time: int):
        """
        Initialize the FlightController communication object.

        """
        # warn people about ModemManager which interferes badly with ArduPilot
        if os_path.exists("/usr/sbin/ModemManager"):
            logging_warning("You should uninstall ModemManager as it conflicts with ArduPilot")

        self.reboot_time = reboot_time
        comports = FlightController.list_serial_ports()
        # ubcports = FlightController.list_usb_devices()
        netports = FlightController.list_network_ports()
        # list of tuples with the first element being the port name and the second element being the port description
        self.connection_tuples = [(port.device, port.description) for port in comports] + [(port, port) for port in netports]
        logging_info('Available connection ports are:')
        for port in self.connection_tuples:
            logging_info("%s - %s", port[0], port[1])
        self.connection_tuples += [tuple(['Add another', 'Add another'])]  # now that is is logged, add the 'Add another' tuple
        self.master = None
        self.comport = None
        self.ftp_settings_debug = 2
        self.ftp_settings_pkt_loss_rx = 0
        self.ftp_settings_pkt_loss_tx = 0
        self.ftp_settings_burst_read_size = 80
        self.ftp_settings_max_backlog = 5
        self.ftp_settings_retry_time = 0.5
        self.close_connection() # initialize the connection variables,'and prevent code duplication
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
        self.last_op_time = time_time()
        self.write_list = None
        self.read_gaps = []
        self.read_gap_times = {}
        self.read_total = 0
        self.duplicates = 0
        self.last_read = None
        self.last_burst_read = None
        self.op_start = None
        self.reached_eof = False
        self.backlog = 0
        self.read_retries = 0
        self.burst_size = self.ftp_settings_burst_read_size
        self.open_retries = 0

        self.ftp_count = None
        self.ftp_started = False
        self.ftp_failed = False
        self.mav_param_set = set()
        self.param_types = {}
        self.fetch_one = dict()
        self.fetch_set = None
        self.mav_param = mavparm.MAVParmDict()
        self.mav_param_count = 0
        self.default_params = None
        self.warned_component = False

    def close_connection(self):
        """
        Close the connection to the flight controller.
        """
        if self.master is not None:
            self.master.close()
            self.master = None
        self.fc_parameters = {}
        self.target_system = None
        self.target_component = None
        self.capabilities = None
        self.version = None

    def add_connection(self, connection_string: str):
        """
        Add a new connection to the list of available connections.
        """
        if connection_string:
            # Check if connection_string is not the first element of any tuple in self.other_connection_tuples
            if all(connection_string != t[0] for t in self.connection_tuples):
                self.connection_tuples.insert(-1, (connection_string, connection_string))
                logging_debug("Added connection %s", connection_string)
                return True
            logging_debug("Did not add duplicated connection %s", connection_string)
        else:
            logging_debug("Did not add empty connection")
        return False

    def connect(self, device: str, progress_callback=None):
        """
        Connect to the FlightController with a connection string.

        Args:
            device (str): The connection string to the flight controller.
        """
        if device:
            self.add_connection(device)
            self.comport = mavutil.SerialPort(device=device, description=device)
        else:
            autodetect_serial = self.auto_detect_serial()
            if autodetect_serial:
                # Resolve the soft link if it's a Linux system
                if os_name == 'posix':
                    try:
                        dev = autodetect_serial[0].device
                        logging_debug("Auto-detected device %s", dev)
                        # Get the directory part of the soft link
                        softlink_dir = os_path.dirname(dev)
                        # Resolve the soft link and join it with the directory part
                        resolved_path = os_path.abspath(os_path.join(softlink_dir, os_readlink(dev)))
                        autodetect_serial[0].device = resolved_path
                        logging_debug("Resolved soft link %s to %s", dev, resolved_path)
                    except OSError:
                        pass # Not a soft link, proceed with the original device path
                self.comport = autodetect_serial[0]
                # Add the detected serial port to the list of available connections because it is not there
                if self.comport.device not in [t[0] for t in self.connection_tuples]:
                    self.connection_tuples.insert(-1, (self.comport.device, self.comport.description))
            else:
                return "No serial ports found. Please connect a flight controller and try again."
        error_message = self.create_connection_with_retry(progress_callback=progress_callback)
        if device == 'test': # FIXME for testing only
            self.fc_parameters['INS_LOG_BAT_MASK'] = 1.0
            self.fc_parameters['INS_TCAL1_TMAX'] = 1.0
            self.fc_parameters['COMPASS_DEV_ID'] = 1.0
        return error_message

    def request_message(self, message_id: int):
        self.master.mav.command_long_send(
            self.target_system,
            self.target_component,
            mavutil.mavlink.MAV_CMD_REQUEST_MESSAGE,
            0, # confirmation
            message_id, 0, 0, 0, 0, 0, 0)

    def cmd_version(self):
        '''show version'''
        self.request_message(mavutil.mavlink.MAVLINK_MSG_ID_AUTOPILOT_VERSION)

    def create_connection_with_retry(self, progress_callback, retries: int = 3,
                                     timeout: int = 5) -> mavutil.mavlink_connection:
        """
        Attempt to create a connection to the flight controller with retries.

        Args:
            retries (int, optional): The number of retries before giving up. Defaults to 3.
            timeout (int, optional): The timeout in seconds for each connection attempt. Defaults to 5.

        Returns:
            mavutil.mavlink_connection: The MAVLink connection object if successful, None otherwise.
        """
        if self.comport is None or self.comport.device == 'test': # FIXME for testing only
            return None
        logging_info("Will connect to %s", self.comport.device)
        try:
            # Create the connection
            self.master = mavutil.mavlink_connection(device=self.comport.device, timeout=timeout,
                                                     retries=retries, progress_callback=progress_callback)
            logging_debug("Waiting for heartbeat")
            m = self.master.wait_heartbeat(timeout=timeout)
            if m is None:
                logging_error("No heartbeat received, connection failed.")
                return "No heartbeat received, connection failed."
            self.target_system = m.get_srcSystem()
            self.target_component = m.get_srcComponent()
            logging_debug("Connection established with systemID %d, componentID %d.", self.target_system,
                          self.target_component)
            self.cmd_version()
            m = self.master.recv_match(type='AUTOPILOT_VERSION', blocking=True, timeout=timeout)
            if m is None:
                logging_error("No AUTOPILOT_VERSION message received, connection failed.")
                return "No AUTOPILOT_VERSION message received, connection failed."
            self.capabilities = m.capabilities
            vMajor, vMinor, vPatch, vFwType = decode_flight_sw_version(m.flight_sw_version)
            self.version = "{0}.{1}.{2}".format(vMajor, vMinor, vPatch)
            logging_info("Capabilities: %d, Version: %s %s", self.capabilities, self.version, vFwType)
        except (ConnectionError, SerialException, PermissionError, ConnectionRefusedError) as e:
            logging_warning("Connection failed: %s", e)
            logging_error("Failed to connect after %d attempts.", retries)
            return e
        return ""

    def read_params(self, progress_callback=None) -> Dict[str, float]:
        """
        Requests all flight controller parameters from a MAVLink connection.

        Returns:
            Dict[str, float]: A dictionary of flight controller parameters.
        """
        if self.master is None and self.comport is not None and self.comport.device == 'test': # FIXME for testing only
            filename = os_path.join('4.4.4-test-params', '00_default.param')
            logging_warning("Testing active, will load all parameters from the %s file", filename)
            par_dict_with_comments = Par.load_param_file_into_dict(filename)
            return {k: v.value for k, v in par_dict_with_comments.items()}

        if self.master is None:
            return None

        # Check if MAVFTP is supported
        # FIXME remove the "not" once it works
        if self.capabilities and not (self.capabilities & mavutil.mavlink.MAV_PROTOCOL_CAPABILITY_FTP):
            logging_info("MAVFTP is supported by the %s flight controller", self.comport.device)
            parameters, _defaults = self.read_params_via_mavftp(progress_callback)
            return parameters

        logging_info("MAVFTP is not supported by the %s flight controller, fallback to MAVLink", self.comport.device)
        # MAVFTP is not supported, fall back to MAVLink
        return self.read_params_via_mavlink(progress_callback)

    def read_params_via_mavlink(self, progress_callback=None) -> Dict[str, float]:
        logging_debug("Will fetch all parameters from the %s flight controller", self.comport.device)
        # Request all parameters
        self.master.mav.param_request_list_send(
            self.master.target_system, self.master.target_component
        )

        # Dictionary to store parameters
        parameters = {}

        # Loop to receive all parameters
        while True:
            try:
                m = self.master.recv_match(type='PARAM_VALUE', blocking=True)
                if m is None:
                    break
                message = m.to_dict()
                param_id = message['param_id'] # .decode("utf-8")
                param_value = message['param_value']
                parameters[param_id] = param_value
                logging_debug('Received parameter: %s = %s', param_id, param_value)
                # Call the progress callback with the current progress
                if progress_callback:
                    progress_callback(len(parameters), m.param_count)
                if m.param_count == len(parameters):
                    logging_debug("Fetched %d parameter values from the %s flight controller",
                                  m.param_count, self.comport.device)
                    break
            except Exception as error:
                logging_error('Error: %s', error)
                break
        return parameters

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
            logging_info("> %s dt=%.2f" % (op, now - self.last_op_time))
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
            logging_info("Getting %s as %s" % (fname, self.filename))
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

    def read_params_via_mavftp(self, progress_callback=None) -> Dict[str, float]:
        """
        Reads parameters from the flight controller using MAVFTP.

        Args:
            progress_callback (function, optional): A callback function to report progress.

        Returns:
            Dict[str, float]: A dictionary of flight controller parameters.
        """
        # Assuming you have a method to start an FTP session
        self.ftp_started = True
        self.ftp_count = None
        self.cmd_get(["@PARAM/param.pck?withdefaults=1"], callback=self.ftp_callback,
                     callback_progress=self.ftp_callback_progress)

        # Placeholder for the FTP session object
        # ftp_session = None

        # Placeholder for the parameters dictionary
        # parameters = {}

        # Assuming you have a method to initiate the FTP download
        # This method should accept the callback functions as arguments
        # ftp_download(ftp_session, ftp_callback, ftp_progress_callback)

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
            if magic2 == 0x671b or magic2 == 0x671c:
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
        self.fetch_one = dict()
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
        # self.mpstate.console.set_status('Params', 'Param %u/%u' % (total_params, total_params))
        logging_info("Received %u parameters (ftp)" % total_params)
        # if self.logdir is not None:
        #    self.mav_param.save(os.path.join(self.logdir, self.parm_file), '*', verbose=True)
        # self.log_params(pdata.params)

        if with_defaults:
            self.default_params = mavparm.MAVParmDict()
            for (name, v, ptype) in pdata.defaults:
                name = str(name.decode('utf-8'))
                self.default_params[name] = v
        #    if self.logdir:
        #        defaults_path = os.path.join(self.logdir, "defaults.parm")
        #        self.default_params.save(defaults_path, '*', verbose=False)
        #        logging_info("Saved %u defaults to %s" % (len(pdata.defaults), defaults_path))

    def op_parse(self, m):
        '''parse a FILE_TRANSFER_PROTOCOL msg'''
        hdr = bytearray(m.payload[0:12])
        (seq, session, opcode, size, req_opcode, burst_complete, _pad, offset) = struct.unpack("<HBBBBBBI", hdr)
        payload = bytearray(m.payload[12:])[:size]
        return FTP_OP(seq, session, opcode, size, req_opcode, burst_complete, offset, payload)

    def mavlink_packet(self, m):
        '''handle a mavlink packet'''
        mtype = m.get_type()
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

            # if op.req_opcode == self.last_op.opcode and op.seq == (self.last_op.seq + 1) % 256:
            #    self.rtt = max(min(self.rtt, dt), 0.01)
            if op.req_opcode == OP_OpenFileRO:
                self.handle_open_RO_reply(op, m)
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
            print("Gap read of %u at %u rem=%u blog=%u", length, offset, len(self.read_gaps), self.backlog)
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
            for g in self.read_gap_times.keys():
                if self.read_gap_times[g] == 0:
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

    def handle_open_RO_reply(self, op, m):
        '''handle OP_OpenFileRO reply'''
        if op.opcode == OP_Ack:
            if self.filename is None:
                return
            try:
                if self.callback is not None or self.filename == '-':
                    self.fh = SIO()
                else:
                    self.fh = open(self.filename, 'wb')
            except Exception as ex:
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

    def handle_burst_read(self, op, m):
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
            if ecode == ERR_EndOfFile or ecode == 0:
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

    def handle_reply_read(self, op, m):
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

    def write_payload(self, op):
        '''write payload from a read op'''
        self.fh.seek(op.offset)
        self.fh.write(op.payload)
        self.read_total += len(op.payload)
        if self.callback_progress is not None:
            self.callback_progress(self.fh, self.read_total)

    def set_param(self, param_name: str, param_value: float):
        """
        Set a parameter on the flight controller.

        Args:
            param_name (str): The name of the parameter to set.
            param_value (float): The value to set the parameter to.
        """
        if self.master is None: # FIXME for testing only
            return None
        return self.master.param_set_send(param_name, param_value)

    def reset_and_reconnect(self, reset_progress_callback=None, connection_progress_callback=None, sleep_time: int = None):
        """
        Reset the flight controller and reconnect.

        Args:
            sleep_time (int, optional): The time in seconds to wait before reconnecting.
        """
        if self.master is None: # FIXME for testing only
            return None
        # Issue a reset
        self.master.reboot_autopilot()
        logging_info("Reset command sent to ArduPilot.")
        time_sleep(0.3)

        self.close_connection()

        current_step = 0

        if sleep_time is None or sleep_time <= 7:
            sleep_time = self.reboot_time

        while current_step != sleep_time:
            # Call the progress callback with the current progress
            if reset_progress_callback:
                reset_progress_callback(current_step, sleep_time)

            # Wait for sleep_time seconds
            time_sleep(1)
            current_step += 1

        # Call the progress callback with the current progress
        if reset_progress_callback:
            reset_progress_callback(current_step, sleep_time)

        # Reconnect to the flight controller
        self.create_connection_with_retry(connection_progress_callback)

    @staticmethod
    def list_usb_devices():
        """
        List all connected USB devices.
        """
        ret = []
        return ret # FIXME for testing only
        # devices = usb.core.find(find_all=True)
        # for device in devices:
        #     try:
        #         manufacturer = usb.util.get_string(device, device.iManufacturer)
        #     except ValueError as e:
        #         logging_warning("Failed to retrieve string descriptor for device (VID:PID) - %04x:%04x: %s",
        #                         device.idVendor, device.idProduct, e)
        #         manufacturer = "Unknown"
        #     try:
        #         product = usb.util.get_string(device, device.iProduct)
        #     except ValueError as e:
        #         logging_warning("Failed to retrieve string descriptor for device (VID:PID) - %04x:%04x: %s",
        #                         device.idVendor, device.idProduct, e)
        #         product = "Unknown"
        #     logging_info("USB device (VID:PID) - %04x:%04x, Manufacturer: %s, Product: %s",
        #                  device.idVendor,
        #                  device.idProduct,
        #                  manufacturer,
        #                  product)
        #     ret.append([device.idVendor,
        #                 device.idProduct,
        #                 manufacturer,
        #                 product])
        # return ret

    @staticmethod
    def list_serial_ports():
        """
        List all available serial ports.
        """
        comports = serial.tools.list_ports.comports()
        # for port in comports:
        #     logging_debug("ComPort - %s, Description: %s", port.device, port.description)
        return comports

    @staticmethod
    def list_network_ports():
        """
        List all available network ports.
        """
        return ['tcp:127.0.0.1:5760', 'udp:127.0.0.1:14550']

    @staticmethod
    def auto_detect_serial():
        serial_list = mavutil.auto_detect_serial(preferred_list=preferred_ports)
        serial_list.sort(key=lambda x: x.device)

        # remove OTG2 ports for dual CDC
        if len(serial_list) == 2 and serial_list[0].device.startswith("/dev/serial/by-id"):
            if serial_list[0].device[:-1] == serial_list[1].device[0:-1]:
                serial_list.pop(1)

        return serial_list

    def get_connection_tuples(self):
        """
        Get all available connections.
        """
        return self.connection_tuples

    @staticmethod
    def list_ardupilot_supported_usb_pid_vid():
        """
        List all ArduPilot supported USB vendor ID (VID) and product ID (PID).

        source: https://ardupilot.org/dev/docs/USB-IDs.html
        """
        return {
            0x0483: {'vendor': 'ST Microelectronics', 'PID': {0x5740: 'ChibiOS'}},
            0x1209: {'vendor': 'ArduPilot', 'PID': {0x5740: 'MAVLink',
                                                    0x5741: 'Bootloader',
                                                    }
                     },
            0x16D0: {'vendor': 'ArduPilot', 'PID': {0x0E65: 'MAVLink'}},
            0x26AC: {'vendor': '3D Robotics', 'PID': {}},
            0x2DAE: {'vendor': 'Hex', 'PID': {0x1101: 'CubeBlack+',
                                              0x1001: 'CubeBlack bootloader',
                                              0x1011: 'CubeBlack',
                                              0x1016: 'CubeOrange',
                                              0x1005: 'CubePurple bootloader',
                                              0x1015: 'CubePurple',
                                              0x1002: 'CubeYellow bootloader',
                                              0x1012: 'CubeYellow',
                                              0x1003: 'CubeBlue bootloader',
                                              0x1013: 'CubeBlue',              # These where detected by microsoft copilot
                                              0x1004: 'CubeGreen bootloader',
                                              0x1014: 'CubeGreen',
                                              0x1006: 'CubeRed bootloader',
                                              0x1017: 'CubeRed',
                                              0x1007: 'CubeOrange bootloader',
                                              0x1018: 'CubeOrange',
                                              0x1008: 'CubePurple bootloader',
                                              0x1019: 'CubePurple',
                                              }
                     },
            0x3162: {'vendor': 'Holybro', 'PID': {0x004B: 'Durandal'}},
            0x27AC: {'vendor': 'Laser Navigation', 'PID': {0x1151: 'VRBrain-v51',
                                                           0x1152: 'VRBrain-v52',
                                                           0x1154: 'VRBrain-v54',
                                                           0x1910: 'VRCore-v10',
                                                           0x1351: 'VRUBrain-v51',
                                                           }
                     },
        }
