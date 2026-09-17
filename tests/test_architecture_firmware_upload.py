"""
Documentation contracts for the firmware upload architecture.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

# ruff: noqa: INP001

from pathlib import Path

from ardupilot_methodic_configurator import backend_flightcontroller_bootloader as bootloader


def _documents_firmware_upload_contract(document: str) -> bool:
    """Return whether the architecture identifies the live upload backend contract."""
    required_details = (
        "APJ input",
        "`backend_flightcontroller_bootloader.py`",
        "`FlightControllerBootloaderBackend`",
        "`BootloaderClient`",
        "`data_model_firmware_upload.py`",
        "`FlightController.upload_apj_firmware()`",
        f"{bootloader.BOOTLOADER_ENUMERATION_TIMEOUT:g}-second wall-clock budget",
    )
    return all(detail in document for detail in required_details) and "APJ/BIN" not in document


def test_firmware_upload_architecture_documents_apj_only_input() -> None:
    """
    The firmware-upload architecture documents the format accepted by the model.

    GIVEN: The firmware-upload architecture document describes file selection
    WHEN: The documented input format is inspected
    THEN: It identifies APJ input and does not advertise unsupported BIN input
    """
    architecture = Path(__file__).parents[1] / "ARCHITECTURE_firmware_upload.md"
    document = architecture.read_text(encoding="utf-8")

    assert _documents_firmware_upload_contract(document)


def test_firmware_upload_architecture_contract_rejects_stale_backend_details() -> None:
    """The contract must reject renamed backend details and an incorrect timeout."""
    architecture = Path(__file__).parents[1] / "ARCHITECTURE_firmware_upload.md"
    document = architecture.read_text(encoding="utf-8")
    stale_document = (
        document.replace("`backend_flightcontroller_bootloader.py`", "`obsolete_bootloader_backend.py`")
        .replace("`FlightControllerBootloaderBackend`", "`ObsoleteBootloaderBackend`")
        .replace("15-second wall-clock budget", "999-second wall-clock budget")
    )

    assert not _documents_firmware_upload_contract(stale_document)
