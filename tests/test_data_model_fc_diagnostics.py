#!/usr/bin/env python3

"""
Behavior tests for complete flight-controller diagnostics.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import pytest
from pymavlink.dialects.v20.ardupilotmega import MAVLink_statustext_message

from ardupilot_methodic_configurator import data_model_fc_diagnostics as diagnostics


def test_long_status_text_preserves_utf8_and_spaces_across_chunks() -> None:
    """GIVEN split UTF-8 text, WHEN all chunks arrive, THEN one intact diagnostic is returned."""
    assembler = diagnostics.StatusTextAssembler()
    text = "A" * 49 + "é useful details"
    payload = text.encode("utf-8")
    assert assembler.assemble(MAVLink_statustext_message(4, payload[:50], id=42, chunk_seq=0)) is None
    assert assembler.assemble(MAVLink_statustext_message(4, payload[50:], id=42, chunk_seq=1)) == text
    assert assembler.assemble(MAVLink_statustext_message(4, b"A" * 49 + b" ", id=43, chunk_seq=0)) is None
    assert assembler.assemble(MAVLink_statustext_message(4, b"tail", id=43, chunk_seq=1)) == "A" * 49 + " tail"


def test_missing_chunk_does_not_display_a_misleading_partial_diagnostic() -> None:
    """GIVEN a missing middle chunk, WHEN the ending arrives, THEN no partial message is emitted."""
    assembler = diagnostics.StatusTextAssembler()
    assert assembler.assemble(MAVLink_statustext_message(4, b"A" * 50, id=42, chunk_seq=0)) is None
    assert assembler.assemble(MAVLink_statustext_message(4, b"ending", id=42, chunk_seq=2)) is None


def test_retransmitted_chunk_does_not_interrupt_a_long_diagnostic() -> None:
    """GIVEN a repeated middle chunk, WHEN the ending arrives, THEN the text contains each chunk once."""
    assembler = diagnostics.StatusTextAssembler()
    for sequence in (0, 1, 1):
        assert assembler.assemble(MAVLink_statustext_message(4, b"A" * 50, id=42, chunk_seq=sequence)) is None
    assert assembler.assemble(MAVLink_statustext_message(4, b"ending", id=42, chunk_seq=2)) == "A" * 100 + "ending"


def test_expired_chunks_cannot_be_combined_with_a_later_message(monkeypatch: pytest.MonkeyPatch) -> None:
    """GIVEN an unfinished old message, WHEN its continuation arrives late, THEN it is discarded."""
    now = [0.0]
    monkeypatch.setattr(diagnostics, "monotonic", lambda: now[0])
    assembler = diagnostics.StatusTextAssembler()
    assert assembler.assemble(MAVLink_statustext_message(4, b"A" * 50, id=42, chunk_seq=0)) is None
    now[0] = 6.0
    assert assembler.assemble(MAVLink_statustext_message(4, b"old ending", id=42, chunk_seq=1)) is None
    assert assembler.assemble(MAVLink_statustext_message(4, b"new message", id=42, chunk_seq=0)) == "new message"


def test_identical_chunk_ids_from_different_vehicles_are_assembled_separately() -> None:
    """GIVEN two senders using one ID, WHEN chunks interleave, THEN their messages stay separate."""
    assembler = diagnostics.StatusTextAssembler()
    for system, text, sequence, expected in (
        (1, b"A" * 50, 0, None),
        (2, b"B" * 50, 0, None),
        (1, b"first ending", 1, "A" * 50 + "first ending"),
        (2, b"second ending", 1, "B" * 50 + "second ending"),
    ):
        message = MAVLink_statustext_message(4, text, id=42, chunk_seq=sequence)
        message._header.srcSystem = system  # pylint: disable=protected-access
        assert assembler.assemble(message) == expected


def test_empty_final_chunk_completes_an_exact_multiple_of_fifty_bytes() -> None:
    """GIVEN fifty text bytes, WHEN the null ending arrives, THEN the complete diagnostic is emitted."""
    assembler = diagnostics.StatusTextAssembler()
    assert assembler.assemble(MAVLink_statustext_message(4, b"A" * 50, id=42, chunk_seq=0)) is None
    assert assembler.assemble(MAVLink_statustext_message(4, b"\x00", id=42, chunk_seq=1)) == "A" * 50
