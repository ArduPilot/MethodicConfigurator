"""
Parses an ArduPilot .bin log file into a raw representation of all FMT derived messages.

The ArduPilot .bin format is self-describing: FMT/FMTU messages at the start of
the file define the schema (field names, units, multipliers) of every
message type. pymavlink reads those definitions and decodes each message
accordingly, so this parser needs no hardcoded knowledge of any message type.

SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import contextlib
import os
from collections.abc import Iterator
from dataclasses import dataclass, field
from logging import error as logging_error
from typing import Any

import numpy as np
from pymavlink import mavutil

from ardupilot_methodic_configurator import _

_NO_ID_ASSIGNED = "-"  # ArduPilot's FMTU convention: '-' marks a field with no unit/multiplier ID assigned


def open_log(logfile: str) -> mavutil.mavfile:
    """
    Open an ArduPilot .bin log file.

    Args:
        logfile: Path to the .bin log file.

    Returns:
        An open pymavlink connection object.

    """
    try:
        mlog = mavutil.mavlink_connection(logfile)
    except (OSError, ValueError) as e:
        msg = _("Error opening logfile {logfile}: {error}").format(logfile=logfile, error=e)
        raise OSError(msg) from e
    return mlog  # pyright: ignore[reportReturnType]  # pymavlink stubs include CSVReader which doesn't extend mavfile


def close_log(mlog: mavutil.mavfile) -> None:
    """Close an open log connection, ignoring errors if already closed."""
    with contextlib.suppress(OSError):
        mlog.close()


def _iter_messages(mlog: mavutil.mavfile) -> Iterator[Any]:
    """
    Yield decoded DataFlash messages from an open log connection.

    Args:
        mlog: An open pymavlink connection.

    Yields:
        One decoded DataFlash message per iteration.

    """
    while True:
        msg = mlog.recv_match()
        if msg is None:
            break
        yield msg


def parse_log(logfile: str) -> Iterator[Any]:
    """
    Yield decoded DataFlash messages.

    Works on all firmware versions, every message type is yielded irrespective of their types.

    Args:
        logfile: Path to the .bin log file.

    Yields:
        One decoded DataFlash message per iteration.

    """
    mlog = open_log(logfile)
    try:
        yield from _iter_messages(mlog)
    finally:
        close_log(mlog)


@dataclass
class MessageSchema:  # pylint: disable=too-many-instance-attributes
    """Message types's FMT schema: fields, units, multipliers, types."""

    name: str
    msg_type: int
    length: int

    format: str
    fields: list[str]
    units: list[str]
    multipliers: list[float | None]

    records: int = 0


_FORMAT_TO_DTYPE: dict[str, Any] = {
    "b": np.int8,
    "B": np.uint8,
    "h": np.int16,
    "H": np.uint16,
    "i": np.int32,
    "I": np.uint32,
    "f": np.float32,
    "d": np.float64,
    "n": "S4",
    "N": "S16",
    "Z": "S64",
    "c": np.int16,
    "C": np.uint16,
    "e": np.int32,
    "E": np.uint32,
    "L": np.int32,
    "M": np.uint8,
    "q": np.int64,
    "Q": np.uint64,
}

_ARRAY_FIELD_LENGTH = 32


@dataclass
class LogData:
    """
    Storing parsed log metadata and one structured numpy array per message type.

    Attributes:
        schemas: Raw message definitions extracted from FMT/FMTU/UNIT/MULT,
            keyed by message name. Each holds columns, units, multipliers and
            types exactly as pymavlink reports them.
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

    def get_message_columns(self, message_name: str) -> np.ndarray | None:
        """Return the structured numpy array for one message type, if present."""
        return self._raw_messages.get(message_name)

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

        multiplier, format_char = self._field_multiplier_and_format(message_name, field_name)
        return _scale_field_values(values, multiplier, format_char)

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
                    multiplier, format_char = self._field_multiplier_and_format(message_name, field_name)
                    if multiplier is not None and multiplier != 1 and not isinstance(value, str):
                        if isinstance(value, list):
                            value = _scale_field_values(np.asarray(value), multiplier, format_char).tolist()
                        else:
                            value = _scale_field_values(np.asarray(value), multiplier, format_char)[()]

                record[field_name] = value
            yield record

    def _field_multiplier_and_format(self, message_name: str, field_name: str) -> tuple[float | None, str | None]:
        schema = self.schemas.get(message_name)
        if schema is None:
            return None, None

        try:
            field_index = schema.fields.index(field_name)
        except ValueError:
            return None, None

        if field_index >= len(schema.multipliers):
            return None, None

        format_char = schema.format[field_index] if field_index < len(schema.format) else None
        return schema.multipliers[field_index], format_char


def _schema_numpy_dtype(schema: MessageSchema) -> np.dtype[Any]:
    """Build a structured numpy dtype that mirrors a message schema."""
    if len(schema.fields) != len(schema.format):
        msg = _("Schema {name} has mismatched field and format counts").format(name=schema.name)
        raise ValueError(msg)

    dtype_fields: list[Any] = []
    for field_name, format_char in zip(schema.fields, schema.format, strict=True):
        if format_char == "a":
            dtype_fields.append((field_name, np.int16, (_ARRAY_FIELD_LENGTH,)))
            continue

        dtype = _FORMAT_TO_DTYPE.get(format_char)
        if dtype is None:
            msg = _("Unsupported log format character {format_char!r} in schema {name}").format(
                format_char=format_char, name=schema.name
            )
            raise ValueError(msg)

        dtype_fields.append((field_name, dtype))

    return np.dtype(dtype_fields)


def _promoted_integer_dtype(dtype: np.dtype[Any]) -> np.dtype[Any]:
    """Return a wider integer dtype suitable for fixed-point scaled fields."""
    if dtype.kind == "i":
        if dtype.itemsize <= 2:
            return np.dtype(np.int32)
        return np.dtype(np.int64)

    if dtype.kind == "u":
        if dtype.itemsize <= 2:
            return np.dtype(np.uint32)
        return np.dtype(np.uint64)

    return dtype


def _is_integer_multiplier(multiplier: float | None) -> bool:
    """Return True when a multiplier can be applied without leaving integer space."""
    return multiplier is not None and float(multiplier).is_integer()


def _scale_field_values(values: np.ndarray, multiplier: float | None, format_char: str | None = None) -> np.ndarray:
    """Apply a field multiplier while preserving integer width for fixed-point fields."""
    if multiplier is None or multiplier == 1:
        return values

    if format_char in {"c", "C", "e", "E"} and values.dtype.kind in {"i", "u"} and _is_integer_multiplier(multiplier):
        promoted_dtype = _promoted_integer_dtype(values.dtype)
        return values.astype(promoted_dtype, copy=False) * int(multiplier)

    return values * multiplier


def _validate_message_fields(schema: MessageSchema, payload: dict[str, Any]) -> None:
    """Ensure a decoded message exposes exactly the fields defined by its schema."""
    expected_fields = set(schema.fields)
    actual_fields = {field_name for field_name in payload if field_name != "mavpackettype"}

    missing = expected_fields - actual_fields
    extra = actual_fields - expected_fields
    if missing or extra:
        msg = _("Field mismatch for {name}. Missing: {missing}, extra: {extra}").format(
            name=schema.name, missing=sorted(missing), extra=sorted(extra)
        )
        raise ValueError(msg)


def _record_message_counts_and_fields(mlog: mavutil.mavfile, log_data: LogData) -> dict[int, str]:
    """
    First pass: count message occurrences and capture each type's FMTU MultIds string.

    MultIds maps each field position to a single-character multiplier ID,
    resolved later against mlog.mult_lookup.
    """
    mult_ids_by_type: dict[int, str] = {}
    for msg in _iter_messages(mlog):
        msg_type = msg.get_type()
        log_data.msg_count[msg_type] = log_data.msg_count.get(msg_type, 0) + 1
        if msg_type == "FMTU":
            mult_ids_by_type[int(msg.FmtType)] = msg.MultIds
    return mult_ids_by_type


def _resolve_multipliers(fmt: Any, mult_ids: str | None, mult_lookup: dict[str, float]) -> list[float | None]:  # noqa: ANN401
    resolved: list[float | None] = []
    for i, fixed_mult in enumerate(fmt.msg_mults):
        if fixed_mult is not None:
            resolved.append(fixed_mult)
            continue

        if mult_ids is not None and i < len(mult_ids) and mult_ids[i] != _NO_ID_ASSIGNED and mult_ids[i] in mult_lookup:
            resolved.append(mult_lookup[mult_ids[i]])
        else:
            resolved.append(None)

    return resolved


def _allocate_message_arrays(log_data: LogData) -> None:
    """Allocate one structured numpy array per message type."""
    for message_name, schema in log_data.schemas.items():
        log_data._raw_messages[message_name] = np.empty(schema.records, dtype=_schema_numpy_dtype(schema))  # pylint: disable=protected-access # noqa: SLF001


def _fill_message_arrays(mlog: mavutil.mavfile, log_data: LogData) -> None:  # pylint: disable=too-many-locals
    """
    Second pass: validate each decoded record and populate the preallocated arrays.

    The first pass only counts messages. Per-record field validation happens here,
    once schemas are known and before values are stored into the numpy arrays.
    """
    write_positions: dict[str, int] = dict.fromkeys(log_data._raw_messages, 0)  # pylint: disable=protected-access # noqa: SLF001

    for msg in _iter_messages(mlog):
        msg_type = msg.get_type()
        array = log_data._raw_messages.get(msg_type)  # pylint: disable=protected-access # noqa: SLF001
        schema = log_data.schemas.get(msg_type)
        if array is None or schema is None:
            continue

        index = write_positions[msg_type]
        if index >= len(array):
            error_message = _("Message count for {message_type} exceeded the preallocated array size").format(
                message_type=msg_type
            )
            raise ValueError(error_message)

        payload = msg.to_dict()
        _validate_message_fields(schema, payload)

        field_info = array.dtype.fields
        if field_info is None:
            error_message = _("Structured array for {message_type} is missing field metadata").format(message_type=msg_type)
            raise ValueError(error_message)

        values: list[Any] = []
        for field_name in schema.fields:
            value = payload[field_name]

            dtype = field_info[field_name][0]
            if dtype.kind == "S" and isinstance(value, str):
                value = value.encode("ascii", "ignore")
            values.append(value)
        array[index] = tuple(values)
        write_positions[msg_type] = index + 1

    for message_name, schema in log_data.schemas.items():
        written = write_positions.get(message_name, 0)
        if written != schema.records:
            msg = _("Message count mismatch for {message_name}: expected {expected}, wrote {written}").format(
                message_name=message_name, expected=schema.records, written=written
            )
            raise ValueError(msg)


def extract_schemas(mlog: mavutil.mavfile, log_data: LogData, mult_ids_by_type: dict[int, str]) -> None:
    """
    Copy pymavlink's discovered FMT/FMTU schemas into log_data.schemas.

    Stored dicts (not pymavlink objects). Raw metadata only units and multipliers are stored.

    Args:
        mlog: An open pymavlink connection (fully read).
        log_data: The LogData instance to populate.
        mult_ids_by_type: Per message type, the MultIds string from that type's FMTU message.

    """
    for fmt in mlog.formats.values():
        log_data.schemas[fmt.name] = MessageSchema(
            name=fmt.name,
            msg_type=fmt.type,
            length=fmt.len,
            format=fmt.format,
            fields=list(fmt.columns),
            units=list(fmt.units) if fmt.units is not None else [],
            multipliers=_resolve_multipliers(fmt, mult_ids_by_type.get(fmt.type), mlog.mult_lookup),
            records=log_data.msg_count.get(fmt.name, 0),
        )


def extract_log_metadata(log_data: LogData, logfile: str) -> None:
    """Extract generic metadata from a parsed log."""
    log_data.log_file_size = os.path.getsize(logfile)
    log_data.flight_duration_sec = compute_flight_duration(log_data)


def compute_flight_duration(log_data: LogData) -> float | None:
    """
    Compute the total flight duration in seconds.

    Args:
        log_data: parsed log.

    Returns:
        Time in seconds or None.

    """
    message_info = (
        ("ARM", "ArmState", 1, 0),
        ("EV", "Id", 10, 11),
    )

    try:
        for message_name, state_field, start_value, stop_value in message_info:
            records = log_data.get_message_columns(message_name)
            if records is None or records.size == 0:
                continue

            timeus = log_data.get_field(message_name, "TimeUS", scaled=False)
            states = log_data.get_field(message_name, state_field)
            total_time = 0
            start_time = None

            # Many logs have multiple arm/disarm events, calculate them separately and sum up
            for time_dur, state in zip(timeus, states, strict=True):
                if state == start_value and start_time is None:
                    start_time = time_dur
                elif state == stop_value and start_time is not None:
                    total_time += time_dur - start_time
                    start_time = None

            # If there is no disarm message the flight time can't be calculated.
            if start_time is not None:
                logging_error(
                    _("{message_name} log ends while still armed, no trailing disarm found").format(message_name=message_name)
                )

            if total_time > 0:
                return total_time / 1e6  # 1_000_000

    except (KeyError, ValueError) as error:
        logging_error(_("Could not compute flight duration: {error}").format(error=error))

    return None


def extract_log(logfile: str) -> LogData:
    """
    Parse a complete ArduPilot .bin log into a generic LogData object.

    Captures every message type using the log's own FMT
    schema, so new ArduPilot message types are handled automatically.

    (Pymavlink uses hardcoded print statements that break once an issue is found in the log
    so catching the error cannot be implemented yet).

    Args:
        logfile: Path to the .bin log file.

    Returns:
        A populated LogData object.

    """
    log_data = LogData()

    # first pass: count messages per message-type so that second pass can read data into known-sized arrays
    mlog = open_log(logfile)
    try:
        mult_ids_by_type = _record_message_counts_and_fields(mlog, log_data)
        # extract_schemas should not raise any exception if it does it should fail
        extract_schemas(mlog, log_data, mult_ids_by_type)
    finally:
        close_log(mlog)

    _allocate_message_arrays(log_data)

    # second pass: validate data and read it into static sized numpy arrays
    mlog = open_log(logfile)
    try:
        _fill_message_arrays(mlog, log_data)
    finally:
        close_log(mlog)

    extract_log_metadata(log_data, logfile)

    return log_data
