"""
In-memory ArduPilot log data structures.

These classes contain no file or pymavlink access. Backend parsers populate
them, and data-model analysis code consumes them.

SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Any

import numpy as np

from ardupilot_methodic_configurator import _


@dataclass
class MessageSchema:  # pylint: disable=too-many-instance-attributes
    """Message type's FMT schema and units for its stored and scaled values."""

    name: str
    msg_type: int
    length: int

    format: str
    fields: list[str]
    stored_units: list[str]
    scaled_units: list[str]
    multipliers: list[float | None]
    multipliers_applied_at_ingest: list[bool]

    records: int = 0


@dataclass
class LogData:
    """
    Store parsed log metadata and one structured numpy array per message type.

    Attributes:
        schemas: Message definitions extracted from FMT/FMTU/UNIT/MULT, keyed
            by message name. ``stored_units`` describes decoded values in
            ``_raw_messages`` and returned with ``scaled=False``;
            ``scaled_units`` describes values returned with ``scaled=True``.
            ``multipliers_applied_at_ingest`` records fields whose multiplier
            has already been applied without widening the stored dtype.
        _raw_messages: Per message type, a structured numpy array containing all
            decoded values for that message type. Access via get_message_columns(),
            get_field() or iter_message_records().
        msg_count: Total number of decoded messages for each message type name.

    """

    schemas: dict[str, MessageSchema] = field(default_factory=dict)
    _raw_messages: dict[str, np.ndarray] = field(default_factory=dict, repr=False)
    msg_count: dict[str, int] = field(default_factory=dict)

    flight_duration_sec: float | None = None
    log_file_size: int = 0
    vehicle_type: str | None = None
    firmware_version: tuple[int, int, int] | None = None

    def get_message_columns(self, message_name: str) -> np.ndarray | None:
        """Return the structured numpy array for one message type, if present."""
        return self._raw_messages.get(message_name)

    def add_message_columns(self, message_name: str, columns: np.ndarray, schema: MessageSchema | None = None) -> None:
        """Add in-memory columns for tests or alternate backends without touching private storage."""
        self._raw_messages[message_name] = columns
        self.msg_count[message_name] = int(columns.size)
        if schema is not None:
            self.schemas[message_name] = schema

    def get_field(self, message_name: str, field_name: str, scaled: bool = True) -> np.ndarray:
        """
        Return one field as an array.

        If scaled is True, apply the schema multiplier for that field before
        returning the data. Fixed-width byte strings are decoded to text.
        """
        array = self._raw_messages[message_name]
        field_info = array.dtype.fields
        if field_info is None:
            error_message = _("Structured array for {message_type} is missing field metadata").format(
                message_type=message_name
            )
            raise ValueError(error_message)

        values = array[field_name]
        if values.dtype.kind == "S":
            return np.char.decode(values, "ascii", errors="ignore")

        if not scaled:
            return values

        multiplier = self._field_multiplier(message_name, field_name)
        return scale_field_values(values, multiplier)

    def iter_message_records(self, message_name: str, scaled: bool = True) -> Iterator[dict[str, Any]]:
        """
        Yield decoded records for one message type.

        When scaled is True, apply schema multipliers before returning each
        record. String fields are decoded to text and fixed-size array fields are
        converted to lists.
        """
        array = self._raw_messages.get(message_name)
        if array is None:
            return

        schema = self.schemas.get(message_name)
        if schema is None:
            return

        for row in array:
            record: dict[str, Any] = {}
            for field_name in schema.fields:
                value = row[field_name]
                if isinstance(value, np.ndarray):
                    value = value.tolist()
                elif isinstance(value, np.generic):
                    value = value.item()

                if isinstance(value, bytes):
                    value = value.decode("ascii", "ignore")

                if scaled:
                    multiplier = self._field_multiplier(message_name, field_name)
                    if multiplier is not None and multiplier != 1 and not isinstance(value, str):
                        if isinstance(value, list):
                            value = scale_field_values(np.asarray(value), multiplier).tolist()
                        else:
                            value = scale_field_values(np.asarray(value), multiplier)[()]

                record[field_name] = value
            yield record

    def _field_multiplier(self, message_name: str, field_name: str) -> float | None:
        schema = self.schemas.get(message_name)
        if schema is None:
            return None

        try:
            field_index = schema.fields.index(field_name)
        except ValueError:
            return None

        if field_index >= len(schema.multipliers) or field_index >= len(schema.multipliers_applied_at_ingest):
            return None

        if schema.multipliers_applied_at_ingest[field_index]:
            return None

        return schema.multipliers[field_index]


def scale_field_values(values: np.ndarray, multiplier: float | None) -> np.ndarray:
    """Apply one deferred fixed-point or FMTU multiplier to stored values."""
    if multiplier is None or multiplier == 1:
        return values

    return values * multiplier
