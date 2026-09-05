"""
Documentation contracts for the firmware upload architecture.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

# ruff: noqa: INP001

from pathlib import Path


def test_firmware_upload_architecture_documents_apj_only_input() -> None:
    """
    The firmware-upload architecture documents the format accepted by the model.

    GIVEN: The firmware-upload architecture document describes file selection
    WHEN: The documented input format is inspected
    THEN: It identifies APJ input and does not advertise unsupported BIN input
    """
    architecture = Path(__file__).parents[1] / "ARCHITECTURE_firmware_upload.md"
    document = architecture.read_text(encoding="utf-8")

    assert "APJ input" in document
    assert "APJ/BIN" not in document
