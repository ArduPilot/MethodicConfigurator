"""
Parses tuning_report.csv into parameter transitions across configuration steps.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-FileCopyrightText: 2026 Omkar Sarkar <omkarsarkar24@gmail.com>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import csv
from dataclasses import dataclass


def step_display_name(step_filename: str) -> str:
    """Strip .param extension and leading NN_ for a cleaner legend label."""
    name = step_filename.removesuffix(".param")
    parts = name.split("_", 1)
    return parts[1].replace("_", " ").title() if len(parts) == 2 and parts[0].isdigit() else name


@dataclass
class TuningReport:
    """Forward-filled parameter values per configuration step, parsed from tuning_report.csv."""

    steps: list[str]  # column headers, in order (cleaned display names)
    values: dict[str, list[float | None]]  # param_name -> one value per step (forward-filled)


def load_tuning_report(csv_path: str) -> TuningReport:
    """Load and forward-fill tuning_report.csv."""
    with open(csv_path, encoding="utf-8", newline="") as f:
        reader = csv.reader(f)
        try:
            header = next(reader)
        except StopIteration as exc:
            msg = "tuning_report.csv is empty"
            raise ValueError(msg) from exc

        if len(header) < 2 or not header[0].strip():
            msg = "tuning_report.csv has no parameter-step columns"
            raise ValueError(msg)

        # Apply the display name cleanup directly to the headers
        steps = [step_display_name(step) for step in header[1:]]

        raw_rows: list[tuple[str, list[str]]] = []
        for row in reader:
            if not row or not row[0]:
                continue
            param_name = row[0]
            raw_values = row[1:]
            # Defensive: some CSV writers drop trailing empty cells, pad to match step count.
            if len(raw_values) < len(steps):
                raw_values = raw_values + [""] * (len(steps) - len(raw_values))
            elif len(raw_values) > len(steps):
                raw_values = raw_values[: len(steps)]
            raw_rows.append((param_name, raw_values))

    values: dict[str, list[float | None]] = {}

    for param_name, raw_values in raw_rows:
        filled: list[float | None] = []
        last: float | None = None
        for raw in raw_values:
            if raw.strip():
                last = float(raw)
            filled.append(last)
        values[param_name] = filled

    return TuningReport(steps=steps, values=values)
