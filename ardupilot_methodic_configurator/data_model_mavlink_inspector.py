"""
MAVLink inspector message ordering and presentation without Tkinter or external I/O.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ardupilot_methodic_configurator.data_model_data_telemetry import MessageRate, TelemetryState

MESSAGE_COLUMNS = ("system", "component", "message", "count", "hz", "bytes", "age")


class MavlinkInspectorDataModel:
    """Keep sorting preferences and decoded messages across live snapshot updates."""

    def __init__(self) -> None:
        self.sort_column: str | None = None
        self.sort_descending = False
        self._messages: dict[str, MessageRate] = {}

    def update(self, state: "TelemetryState") -> None:
        """Replace stale rows and fields while preserving the user's sort choice."""
        self._messages = {self.identifier(row): row for row in state.messages}

    def sort_by(self, column: str) -> None:
        """Sort a new column ascending; reverse when the same heading is chosen again."""
        if column not in MESSAGE_COLUMNS:
            msg = f"Unknown MAVLink message column: {column}"
            raise ValueError(msg)
        self.sort_descending = not self.sort_descending if column == self.sort_column else False
        self.sort_column = column

    @property
    def rows(self) -> tuple["MessageRate", ...]:
        """Order by raw numbers so display rounding never changes the result."""
        column = self.sort_column
        rows = tuple(self._messages.values())
        if column is None:
            return rows
        return tuple(sorted(rows, key=lambda row: self._sort_value(row, column), reverse=self.sort_descending))

    @staticmethod
    def _sort_value(row: "MessageRate", column: str) -> int | float | str:
        sort_values: dict[str, int | float | str] = {
            "system": row.key[0],
            "component": row.key[1],
            "message": row.key[2],
            "count": row.sample.count,
            "hz": row.hz,
            "bytes": row.bytes_per_second,
            "age": row.age,
        }
        return sort_values[column]

    @staticmethod
    def identifier(row: "MessageRate") -> str:
        """Distinguish the same message type emitted by different systems or components."""
        system, component, name = row.key
        return f"{system}:{component}:{name}"

    @staticmethod
    def values(row: "MessageRate") -> tuple[int, int, str, int, str, str, str]:
        """Format rates and age for display, keeping the original measurements intact."""
        system, component, name = row.key
        return (system, component, name, row.sample.count, f"{row.hz:.1f}", f"{row.bytes_per_second:.1f}", f"{row.age:.1f}")

    def fields(self, identifier: str) -> str:
        """Return latest decoded values, or clear the detail pane for an expired selection."""
        row = self._messages.get(identifier)
        if row is None:
            return ""
        return "\n".join(f"{name}: {value}" for name, value in row.sample.fields)
