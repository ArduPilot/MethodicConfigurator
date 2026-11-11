#!/usr/bin/env python3

"""
Behavior-driven tests for parsing tuning_report.csv files.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

from pathlib import Path

from ardupilot_methodic_configurator.log_analysis.data_model_tuning_report import load_tuning_report


def test_load_tuning_report_truncates_cells_beyond_the_header(tmp_path: Path) -> None:
    """
    Users can open a report with a row that contains an unexpected trailing value.

    GIVEN: A tuning report with two step headers and a parameter row with three values
    WHEN: The report is loaded for graphing
    THEN: The parameter series remains aligned with the two configured steps
    """
    # Arrange: A malformed but recoverable report row.
    report_path = tmp_path / "tuning_report.csv"
    report_path.write_text("Parameter,01_setup.param,02_tune.param\nMOT_SPIN_MIN,0.1,0.12,0.99\n", encoding="utf-8")

    # Act: Parse the report for the tuning graph.
    report = load_tuning_report(str(report_path))

    # Assert: Ignore only the trailing value that lacks a step header.
    assert report.steps == ["Setup", "Tune"]
    assert report.values["MOT_SPIN_MIN"] == [0.1, 0.12]
