"""
Regression tests for bounded bootloader reads.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

# ruff: noqa: INP001

import pytest

from ardupilot_methodic_configurator import backend_flightcontroller_bootloader as bl


def test_read_timeout_is_bounded_when_partial_reads_arrive_after_deadline() -> None:
    """
    A partial serial response cannot extend the bootloader read deadline.

    GIVEN: A bootloader read has received only part of its expected response
    WHEN: The deadline expires before the remaining bytes arrive
    THEN: The read fails with a bounded protocol timeout
    """

    class PartialReadTransport:  # pylint: disable=too-few-public-methods
        """Return one byte per read to exercise the response deadline."""

        def read(self, _size: int = 1) -> bytes:
            return b"x"

    clock_values = iter([0.0, 1.0])
    client = bl.BootloaderClient(PartialReadTransport(), timeout=1.0, clock=lambda: next(clock_values))

    with pytest.raises(bl.BootloaderProtocolError, match="timeout waiting"):
        client._read_exact(2)  # pylint: disable=protected-access


@pytest.mark.parametrize("arrival_time", [2.0, 2.05])
def test_read_accepts_a_complete_reply_at_or_after_deadline(arrival_time: float) -> None:
    """A complete serial reply is valid even when the clock reaches its deadline."""
    now = 0.0

    class CompleteReadTransport:  # pylint: disable=too-few-public-methods
        """Return the complete response in one serial read."""

        def read(self, _size: int = 1) -> bytes:
            nonlocal now
            now = arrival_time
            return b"\x12\x10"

    client = bl.BootloaderClient(CompleteReadTransport(), timeout=2.0, clock=lambda: now)

    assert client._read_exact(2) == b"\x12\x10"  # pylint: disable=protected-access
