"""
Normalize and assemble flight-controller STATUSTEXT diagnostics.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

from time import monotonic


def status_text_bytes(message: object) -> bytes:
    """Use the wire bytes, since PyMAVLink's text attribute decodes as ASCII."""
    raw_text = getattr(message, "_text_raw", None)
    if not isinstance(raw_text, bytes):
        raw_text = getattr(message, "text", "")
    return raw_text if isinstance(raw_text, bytes) else str(raw_text).encode("utf-8")


def decode_status_text(message: object) -> str:
    """Decode a standalone STATUSTEXT payload without its null padding."""
    return status_text_bytes(message).split(b"\x00", 1)[0].decode("utf-8", errors="replace").strip()


def message_source(message: object) -> tuple[int, int] | None:
    """Return a packet's source when available, including for test transports."""
    system = getattr(message, "get_srcSystem", lambda: None)()
    component = getattr(message, "get_srcComponent", lambda: None)()
    return (system, component) if isinstance(system, int) and isinstance(component, int) else None


class StatusTextAssembler:
    """Assemble ordered MAVLink 2 chunks; discard incomplete or expired sequences."""

    CHUNK_TIMEOUT = 5.0
    MAX_PENDING = 100

    def __init__(self) -> None:
        self._pending: dict[tuple[int, int, int], tuple[int, bytes, float]] = {}

    def clear(self) -> None:
        """Discard unfinished messages when the connection changes."""
        self._pending.clear()

    def assemble(self, message: object) -> str | None:
        """Return a complete message, preserving spaces and UTF-8 across chunks."""
        now = monotonic()
        self._pending = {key: value for key, value in self._pending.items() if now - value[2] < self.CHUNK_TIMEOUT}
        message_id = getattr(message, "id", 0)
        if not isinstance(message_id, int) or message_id == 0:
            return decode_status_text(message)
        sequence = getattr(message, "chunk_seq", 0)
        if not isinstance(sequence, int) or not 0 <= sequence <= 255:
            return None
        source = message_source(message) or (0, 0)
        key = (source[0], source[1], message_id)
        raw_text = status_text_bytes(message)
        complete = b"\x00" in raw_text or len(raw_text) < 50
        chunk = raw_text.split(b"\x00", 1)[0]
        if sequence == 0:
            previous = b""
            if key not in self._pending and len(self._pending) >= self.MAX_PENDING:
                del self._pending[next(iter(self._pending))]
        else:
            pending = self._pending.get(key)
            if pending is None or sequence == pending[0] - 1:
                # Ignore a retransmitted chunk without losing the sequence.
                return None
            expected, previous, _timestamp = pending
            if sequence != expected:
                self._pending.pop(key, None)
                return None
        text = previous + chunk
        if complete:
            self._pending.pop(key, None)
            return text.decode("utf-8", errors="replace").strip()
        self._pending[key] = (sequence + 1, text, now)
        return None
