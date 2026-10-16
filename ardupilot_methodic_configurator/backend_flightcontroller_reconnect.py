"""
Observe the selected FC without competing with its current MAVLink reader.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

from __future__ import annotations

from contextlib import suppress
from logging import info as logging_info
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Event
from time import monotonic
from typing import TYPE_CHECKING, Any, cast

from serial import SerialException

from ardupilot_methodic_configurator import _
from ardupilot_methodic_configurator.backend_flightcontroller_connection import _connection_device_key

if TYPE_CHECKING:
    from collections.abc import Callable

    from ardupilot_methodic_configurator.backend_flightcontroller import FlightController


class FlightControllerReconnect:  # pylint: disable=too-many-instance-attributes
    """
    One editor session, bound to the original controller's nonempty hardware UID.

    The owner must yield reception before calling poll(read=True) or reconnect().
    The packet hook only observes; it never reads, sends, or changes stream rates.
    """

    HEARTBEAT_TIMEOUT = 8.0

    def __init__(self, flight_controller: FlightController, clock: Callable[[], float] = monotonic) -> None:
        self._fc = flight_controller
        self._clock = clock
        self._uid = flight_controller.info.hw_unique_id
        self._device = flight_controller.comport_device
        self._baudrate = flight_controller.active_baudrate
        self._serial_identity: tuple[str | None, int | None, int | None, str | None] | None = None
        self._master: Any = None
        self._autoreconnect: bool | None = None
        self._target = (0, 0)
        self._last_heartbeat = clock()
        self.cancelled = Event()
        if self.enabled:
            self._target = (int(flight_controller.info.system_id), int(flight_controller.info.component_id))
            # Discovery is metadata-only. The radio's USB identity locates the
            # endpoint; only AUTOPILOT_VERSION's UID identifies the remote FC.
            with suppress(OSError):
                for port in flight_controller.get_serial_ports():
                    if _connection_device_key(port.device) == _connection_device_key(self._device):
                        self._serial_identity = (port.serial_number, port.vid, port.pid, port.interface)
                        break
            self._attach()

    @property
    def enabled(self) -> bool:
        """Unknown hardware identity cannot authorize automatic reconnection."""
        return bool(self._uid and self._device and self._device not in {"none", "file"})

    def _attach(self) -> None:
        master = cast("Any", self._fc.master)
        if master is self._master:
            return
        self._detach()
        self._master = master
        if master is not None:
            if hasattr(master, "autoreconnect"):
                self._autoreconnect = master.autoreconnect
                # Only this monitor may reopen a transport: it verifies the UID
                # and refreshes parameters before returning it to the editor.
                master.autoreconnect = False
            master.message_hooks.append(self._observe)
        self.defer()

    def _detach(self) -> None:
        if self._master is not None and self._observe in self._master.message_hooks:
            self._master.message_hooks.remove(self._observe)
        if self._master is not None and self._autoreconnect is not None:
            self._master.autoreconnect = self._autoreconnect
        self._autoreconnect = None
        self._master = None

    def _observe(self, _master: object, message: Any) -> None:  # noqa: ANN401
        if message.get_type() == "HEARTBEAT" and (message.get_srcSystem(), message.get_srcComponent()) == self._target:
            self._last_heartbeat = self._clock()

    def defer(self) -> None:
        """Allow a full grace period after reception was intentionally unavailable."""
        self._last_heartbeat = self._clock()

    def poll(self, *, read: bool) -> bool:
        """Check liveness; read within a time budget only after the current owner yields."""
        if not self.enabled or self.cancelled.is_set():
            return True
        if self._fc.master is None or self._fc.info.hw_unique_id != self._uid:
            return False
        self._attach()
        if getattr(self._master, "portdead", False):
            return False
        if read:
            try:
                deadline = self._clock() + 0.01
                while self._clock() < deadline:
                    message = self._master.recv_match(blocking=False)
                    if message is None or (
                        message.get_type() == "HEARTBEAT"
                        and (message.get_srcSystem(), message.get_srcComponent()) == self._target
                    ):
                        break
            except (OSError, SerialException):
                return False
        return self._clock() - self._last_heartbeat < self.HEARTBEAT_TIMEOUT

    def _reconnect_devices(self) -> list[str]:
        """Prefer the selected endpoint, then try matching USB interfaces without getting stuck on one."""
        if self._serial_identity is None:
            return [self._device]
        try:
            ports = self._fc.get_serial_ports()
        except OSError:
            return [self._device]
        serial_number, vid, pid, interface = self._serial_identity
        # Missing USB metadata cannot justify probing arbitrary serial devices.
        if serial_number is None and (vid is None or pid is None):
            return [self._device]
        matches = [
            port
            for port in ports
            if (port.vid, port.pid) == (vid, pid) and (serial_number is None or port.serial_number == serial_number)
        ]
        selected_key = _connection_device_key(self._device)
        matches.sort(key=lambda port: (_connection_device_key(port.device) != selected_key, port.interface != interface))
        # Interface metadata is frequently absent or shared. It is a preference,
        # not a unique identifier; try every matching endpoint and verify the FC UID.
        devices = [port.device for port in matches]
        return list(dict.fromkeys(devices)) or [self._device]

    def _connect_original_controller(self) -> str:
        error = _("The original flight controller is not available.")
        for device in self._reconnect_devices():
            if self.cancelled.is_set():
                return _("Reconnection cancelled.")
            self._fc.disconnect()
            error = self._fc.connect(device, log_errors=False, baudrate=self._baudrate)
            if not error and self._fc.info.hw_unique_id != self._uid:
                error = _(
                    "The connected flight controller has a different or unknown hardware ID. Waiting for the original FC."
                )
            if not error and (int(self._fc.info.system_id or 0), int(self._fc.info.component_id or 0)) != self._target:
                error = _(
                    "The connected flight controller has a different MAVLink system or component ID. "
                    "Waiting for the original FC."
                )
            if not error:
                self._device = device
                return ""
            logging_info(_("Reconnect attempt on %(device)s failed: %(error)s"), {"device": device, "error": error})
        return error

    def reconnect(self) -> str:
        """
        Try once, verify identity, then refresh values without writing parameters.

        Called off the Tk thread with all other FC users paused. Failed attempts
        leave no usable connection or cached parameters. The editor schedules retries.
        """
        if not self.enabled or self.cancelled.is_set():
            return _("Reconnection cancelled.")
        self._detach()
        self._fc.disconnect()
        refreshed = False
        try:
            error = self._connect_original_controller()
            if error:
                return error
            if self.cancelled.is_set():
                return _("Reconnection cancelled.")
            self._attach()
            # MAVFTP uses files even for an in-memory refresh. Keep its scratch
            # files out of the working directory and the user's vehicle project.
            with TemporaryDirectory() as directory:
                parameters, _defaults = self._fc.download_params(
                    parameter_values_filename=Path(directory) / "complete.param",
                    parameter_defaults_filename=Path(directory) / "00_default.param",
                    cancellation_requested=self.cancelled.is_set,
                )
            if not parameters:
                return _("Could not refresh flight-controller parameters. Retrying.")
            if self.cancelled.is_set():
                return _("Reconnection cancelled.")
            refreshed = True
            return ""
        finally:
            if not refreshed:
                self._detach()
                self._fc.disconnect()

    def close(self) -> None:
        """Cancel further attempts; the caller waits for any worker to yield before releasing the FC."""
        self.cancelled.set()
        self._detach()
