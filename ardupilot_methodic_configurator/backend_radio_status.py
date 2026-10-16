"""
Enable telemetry-radio status reports with periodic ground-station heartbeats.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

from collections.abc import Callable
from logging import debug as logging_debug
from threading import Event, RLock, Thread
from typing import Any

from pymavlink.dialects.v20 import ardupilotmega as mavlink
from serial import SerialException


class RadioStatusBackend:
    """Send the local serial heartbeat SiK needs before injecting radio reports."""

    def __init__(self) -> None:
        self._master: Any = None
        self._stop = Event()
        self._thread: Thread | None = None
        self._original_send: Callable[..., None] | None = None

    def start(self, master: Any) -> None:  # noqa: ANN401
        """Start once per connection and keep sending independently of monitor polling."""
        if master is self._master:
            return
        self.close()
        self._master = master
        # Each worker retains its own stop event and send closure. Even a driver
        # that ignores cancellation cannot revive it when another session starts.
        stop = Event()
        self._stop = stop
        # PyMAVLink packs, writes and updates sequence/signing state in send().
        # Serialize the entire operation with other tools using this encoder.
        send = master.mav.send
        send_lock = getattr(master.mav, "amc_send_lock", None)
        if send_lock is None:
            send_lock = RLock()
            master.mav.amc_send_lock = send_lock

        def locked_send(message: Any, force_mavlink1: bool = False) -> None:  # noqa: ANN401
            with send_lock:
                if stop.is_set():
                    message_text = "MAVLink sender has stopped"
                    raise OSError(message_text)
                send(message, force_mavlink1=force_mavlink1)

        def send_heartbeat() -> None:
            locked_send(
                master.mav.heartbeat_encode(
                    mavlink.MAV_TYPE_GCS,
                    mavlink.MAV_AUTOPILOT_INVALID,
                    0,
                    0,
                    mavlink.MAV_STATE_ACTIVE,
                )
            )

        self._original_send = send
        master.mav.send = locked_send
        try:
            send_heartbeat()
        except (OSError, SerialException, AttributeError, TypeError, ValueError):
            self.close()
            raise
        self._thread = Thread(target=self._run, args=(master, send_heartbeat, stop), name="gcs-heartbeat", daemon=True)
        self._thread.start()

    @staticmethod
    def _run(master: Any, send_heartbeat: Callable[[], None], stop: Event) -> None:  # noqa: ANN401
        """Retry transient write failures without receiving packets or changing streams."""
        try:
            while not stop.wait(1.0):
                try:
                    send_heartbeat()
                except (OSError, SerialException, AttributeError, TypeError, ValueError) as exc:  # noqa: PERF203
                    logging_debug("Error sending GCS heartbeat: %s", exc)
        finally:
            # An in-flight pymavlink reset can install a new port after close()
            # times out and disconnect closes the previous port. Keep this
            # cleanup tied to the worker's own session across reconnects.
            if stop.is_set():
                close_port = getattr(getattr(master, "port", None), "close", None)
                if callable(close_port):
                    try:
                        close_port()
                    except (OSError, SerialException) as exc:
                        logging_debug("Error closing stopped GCS heartbeat port: %s", exc)

    def close(self) -> None:
        """Cancel pending writes and bound the wait before transport cleanup."""
        self._stop.set()
        if self._thread is not None:
            # PyMAVLink may otherwise reopen the port when cancellation or
            # transport close interrupts a serial write.
            if hasattr(self._master, "autoreconnect"):
                self._master.autoreconnect = False
            cancel_write = getattr(getattr(self._master, "port", None), "cancel_write", None)
            if callable(cancel_write):
                try:
                    cancel_write()  # pylint: disable=not-callable
                except (OSError, SerialException) as exc:
                    logging_debug("Error cancelling GCS heartbeat write: %s", exc)
            self._thread.join(timeout=1.0)
            if self._thread.is_alive():
                logging_debug("GCS heartbeat write did not stop before shutdown timeout; closing transport")
            self._thread = None
        if self._master is not None and self._original_send is not None:
            self._master.mav.send = self._original_send
        self._master = None
        self._original_send = None
