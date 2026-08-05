#!/usr/bin/env python3

"""
Tests for log-analysis backend orchestration.

SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

from typing import Any

import numpy as np

from ardupilot_methodic_configurator.log_analysis import backend_log_analysis
from ardupilot_methodic_configurator.log_analysis.backend_log_analysis import analyze_log_file
from ardupilot_methodic_configurator.log_analysis.data_model_log_data import LogData, MessageSchema


def test_analyze_log_file_loads_inputs_and_builds_context(monkeypatch: Any) -> None:  # noqa: ANN401
    """Backend orchestration should load the log and pass loaded project data into the pure analyzer."""
    log_data = LogData()
    log_data.vehicle_type = "ArduCopter"
    log_data.firmware_version = (4, 6, 3)
    log_data.add_message_columns(
        "PARM",
        np.array([("LOG_BITMASK", 7.0)], dtype=[("Name", "U16"), ("Value", "f8")]),
        MessageSchema(
            name="PARM",
            msg_type=1,
            length=1,
            format="Nf",
            fields=["Name", "Value"],
            units=[],
            multipliers=[None, None],
            records=1,
        ),
    )

    sentinel_summary = object()

    def progress_callback(_current: int, _total: int) -> None:
        pass

    seen: dict[str, Any] = {}

    def fake_extract_log(_filepath: str, progress_callback: object | None = None) -> LogData:
        seen["progress_callback"] = progress_callback
        return log_data

    monkeypatch.setattr(backend_log_analysis, "extract_log", fake_extract_log)

    def fake_validate(
        log_vehicle_type: str,
        log_version: tuple[int, int, int],
        project_type: object,
        project_version: object,
    ) -> None:
        seen["validate"] = (log_vehicle_type, log_version, project_type, project_version)

    def fake_analyze(received_log_data: LogData, context: backend_log_analysis.LogAnalysisContext) -> object:
        seen["log_data"] = received_log_data
        seen["context"] = context
        return sentinel_summary

    monkeypatch.setattr(backend_log_analysis, "validate_log_matches_vehicle", fake_validate)
    monkeypatch.setattr(backend_log_analysis, "analyze_log", fake_analyze)

    summary = analyze_log_file(
        "/fake/log.bin",
        project_vehicle_type="ArduCopter",
        project_firmware_version="4.6.3",
        vehicle_components={"Frame": {}},
        configuration_steps={"05_battery.param": {}},
        apm_doc={"LOG_BITMASK": {}},
        progress_callback=progress_callback,
    )

    assert summary is sentinel_summary
    assert seen["validate"] == ("ArduCopter", (4, 6, 3), "ArduCopter", "4.6.3")
    assert seen["log_data"] is log_data
    assert seen["context"].parameters == {"LOG_BITMASK": 7.0}
    assert seen["context"].configuration_steps == {"05_battery.param": {}}
    assert seen["context"].vehicle_components == {"Frame": {}}
    assert seen["context"].apm_doc == {"LOG_BITMASK": {}}
    assert seen["progress_callback"] is progress_callback
