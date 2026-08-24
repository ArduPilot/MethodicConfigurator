"""
Parses an ArduPilot .bin log file into a raw representation of all FMT derived messages.

The ArduPilot .bin format is self-describing: FMT/FMTU messages at the start of
the file define the schema (field names, units, multipliers) of every
message type. pymavlink reads those definitions and decodes each message
accordingly, so this parser needs no hardcoded knowledge of any message type.

SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-FileCopyrightText: 2026 Omkar Sarkar <omkarsarkar24@gmail.com>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import contextlib
import os
from collections.abc import Callable, Iterator, Mapping
from dataclasses import dataclass
from logging import error as logging_error
from typing import Any, Protocol, cast

import numpy as np
from pymavlink import mavutil

from ardupilot_methodic_configurator import _
from ardupilot_methodic_configurator.log_analysis import data_model_log_data
from ardupilot_methodic_configurator.log_analysis.data_model_firmware_version import parse_first_msg_version, parse_ver_fields

_NO_ID_ASSIGNED = "-"  # ArduPilot's FMTU convention: '-' marks a field with no unit/multiplier ID assigned

_MULTIPLIER_TO_PREFIX = {
    0.0: "",
    1.0: "",
    1.0e-1: "d",
    1.0e-2: "c",
    1.0e-3: "m",
    1.0e-6: "µ",
    1.0e-9: "n",
}

_FIXED_POINT_FORMATS = frozenset("cCeEL")
_EAGERLY_SCALED_FLOAT_FORMATS = frozenset("fd")


def open_log(logfile: str) -> mavutil.mavfile:
    """
    Open an ArduPilot .bin log file.

    Args:
        logfile: The path to the ArduPilot .bin log file.

    Returns:
        A mavutil.mavfile connection object.

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


class _MavFmt(Protocol):  # pylint: disable=too-few-public-methods
    """Protocol for pymavlink FMT metadata objects used by extract_schemas."""

    name: str
    type: int
    len: int
    format: str
    columns: list[str]
    units: list[str] | None
    msg_mults: list[float | None]


class _SchemaSource(Protocol):  # pylint: disable=too-few-public-methods
    """Protocol for dynamic pymavlink attributes needed during schema extraction."""

    formats: dict[Any, _MavFmt]
    mult_lookup: dict[str, float]
    unit_lookup: dict[str, str]


@dataclass(frozen=True)
class _FMTUDefinition:
    """The UNIT and MULT identifiers assigned by one FMTU message."""

    unit_ids: str
    mult_ids: str


_FORMAT_TO_DTYPE: dict[str, Any] = {
    "b": np.int8,
    "B": np.uint8,
    "h": np.int16,
    "H": np.uint16,
    "i": np.int32,
    "I": np.uint32,
    "f": np.float32,
    "g": np.float16,
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


def _schema_numpy_dtype(schema: data_model_log_data.MessageSchema) -> np.dtype[Any]:
    """Build a compact structured NumPy dtype matching the log's stored values."""
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


def _validate_message_fields(schema: data_model_log_data.MessageSchema, payload: dict[str, Any]) -> None:
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


def process_ver_identity(msg: Any) -> tuple[str, int, int, int] | None:  # noqa: ANN401
    """Extract firmware identity from a VER message, if possible."""
    fws = getattr(msg, "FWS", None)
    if isinstance(fws, bytes):
        fws = fws.decode("utf-8", errors="replace")
    elif not isinstance(fws, str):
        return None
    return parse_ver_fields(fws, getattr(msg, "Maj", None), getattr(msg, "Min", None), getattr(msg, "Pat", None))


def process_msg_identity(msg: Any) -> tuple[str, int, int, int] | None:  # noqa: ANN401
    """Extract firmware identity from an old-style MSG firmware line, if possible."""
    message = getattr(msg, "Message", "")
    if isinstance(message, bytes):
        message = message.decode("utf-8", errors="replace")
    elif not isinstance(message, str):
        return None
    parsed = parse_first_msg_version([message])
    if parsed is None:
        return None
    vehicle_type, major, minor, patch, _firmware_hash = parsed
    return vehicle_type, major, minor, patch


def _set_log_identity(log_data: data_model_log_data.LogData, identity: tuple[str, int, int, int]) -> None:
    """Store parsed firmware identity on the in-memory log data."""
    vehicle_type, major, minor, patch = identity
    log_data.vehicle_type = vehicle_type
    log_data.firmware_version = (major, minor, patch)


def _record_message_counts_fields_and_identity(
    mlog: mavutil.mavfile, log_data: data_model_log_data.LogData
) -> dict[int, _FMTUDefinition]:
    """
    First pass: count messages, capture FMTU unit/multiplier IDs, and find log identity.

    FMTU IDs map each field position to a UNIT and MULT entry, resolved later
    against pymavlink's completed lookup tables.
    """
    fmtu_definitions: dict[int, _FMTUDefinition] = {}
    msg_fallback_identity: tuple[str, int, int, int] | None = None
    for msg in _iter_messages(mlog):
        msg_type = msg.get_type()
        log_data.msg_count[msg_type] = log_data.msg_count.get(msg_type, 0) + 1
        if msg_type == "FMTU":
            fmtu_definitions[int(msg.FmtType)] = _FMTUDefinition(unit_ids=msg.UnitIds, mult_ids=msg.MultIds)
        elif msg_type == "VER" and log_data.vehicle_type is None:
            identity = process_ver_identity(msg)
            if identity is not None:
                _set_log_identity(log_data, identity)
        elif msg_type == "MSG" and msg_fallback_identity is None:
            msg_fallback_identity = process_msg_identity(msg)

    if log_data.vehicle_type is None and msg_fallback_identity is not None:
        _set_log_identity(log_data, msg_fallback_identity)

    return fmtu_definitions


def _resolve_multipliers(fmt: Any, mult_ids: str | None, mult_lookup: dict[str, float]) -> list[float | None]:  # noqa: ANN401
    """Return each field's stored-to-scaled fixed-point or FMTU multiplier."""
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


def _resolve_multipliers_applied_at_ingest(fmt: Any, multipliers: list[float | None]) -> list[bool]:  # noqa: ANN401
    """Mark dynamic FMTU multipliers that can be applied without widening float storage."""
    return [
        fmt.format[index] in _EAGERLY_SCALED_FLOAT_FORMATS and fmt.msg_mults[index] is None and multiplier not in (None, 1)
        for index, multiplier in enumerate(multipliers)
    ]


def _resolve_scaled_units(fmt: Any, unit_ids: str | None, unit_lookup: dict[str, str]) -> list[str]:  # noqa: ANN401
    """Return units for values after dynamic FMTU multipliers are applied."""
    fallback_units = list(fmt.units) if fmt.units is not None else [""] * len(fmt.columns)
    if unit_ids is None:
        return fallback_units

    return [
        unit_lookup.get(unit_ids[index], fallback_units[index])
        if index < len(unit_ids) and unit_ids[index] != _NO_ID_ASSIGNED
        else fallback_units[index]
        for index in range(len(fmt.columns))
    ]


def _resolve_stored_units(
    scaled_units: list[str],
    multipliers: list[float | None],
    multipliers_applied_at_ingest: list[bool],
) -> list[str]:
    """Return units corresponding to the values physically stored in NumPy arrays."""
    stored_units: list[str] = []
    for unit, multiplier, applied_at_ingest in zip(scaled_units, multipliers, multipliers_applied_at_ingest, strict=True):
        if applied_at_ingest or multiplier is None or multiplier == 1:
            stored_units.append(unit)
            continue

        prefix = _MULTIPLIER_TO_PREFIX.get(multiplier)
        stored_units.append(f"{prefix}{unit}" if prefix is not None else f"{multiplier:.4g} {unit}")
    return stored_units


def _raw_fixed_point_value(msg: Any, field_index: int, field_name: str) -> Any:  # noqa: ANN401
    """Return one unscaled fixed-point value from pymavlink's DataFlash message storage."""
    try:
        return msg._elements[field_index]  # pylint: disable=protected-access # noqa: SLF001 # pymavlink's raw DataFlash representation
    except (AttributeError, IndexError) as error:
        message = _("pymavlink did not expose raw fixed-point field {field_name}").format(field_name=field_name)
        raise ValueError(message) from error


def _allocate_message_arrays(log_data: data_model_log_data.LogData) -> None:
    """Allocate one structured numpy array per message type."""
    for message_name, schema in log_data.schemas.items():
        log_data._raw_messages[message_name] = np.empty(schema.records, dtype=_schema_numpy_dtype(schema))  # pylint: disable=protected-access # noqa: SLF001


def _message_values(
    msg: Any,  # noqa: ANN401
    schema: data_model_log_data.MessageSchema,
    payload: dict[str, Any],
    field_info: Mapping[str, Any],
) -> list[Any]:
    """Convert one decoded message into values compatible with its structured-array schema."""
    values: list[Any] = []
    for field_index, field_name in enumerate(schema.fields):
        format_char = schema.format[field_index]
        value = (
            _raw_fixed_point_value(msg, field_index, field_name)
            if format_char in _FIXED_POINT_FORMATS
            else payload[field_name]
        )
        if schema.multipliers_applied_at_ingest[field_index]:
            multiplier = schema.multipliers[field_index]
            if multiplier is not None:
                value *= multiplier
        if field_info[field_name][0].kind == "S" and isinstance(value, str):
            value = value.encode("ascii", "ignore")
        values.append(value)
    return values


def _fill_message_arrays(  # pylint: disable=too-many-locals
    mlog: mavutil.mavfile,
    log_data: data_model_log_data.LogData,
    progress_callback: Callable[[int, int], None] | None = None,
) -> None:
    """
    Second pass: validate each decoded record and populate the preallocated arrays.

    The first pass only counts messages. Per-record field validation happens here,
    once schemas are known and before values are stored into the numpy arrays.
    """
    write_positions: dict[str, int] = dict.fromkeys(log_data._raw_messages, 0)  # pylint: disable=protected-access # noqa: SLF001
    parsed_messages = 0
    total_messages = sum(log_data.msg_count.values())

    for msg in _iter_messages(mlog):
        parsed_messages += 1
        if progress_callback is not None:
            progress_callback(parsed_messages, total_messages)

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

        array[index] = tuple(_message_values(msg, schema, payload, field_info))
        write_positions[msg_type] = index + 1

    for message_name, schema in log_data.schemas.items():
        written = write_positions.get(message_name, 0)
        if written != schema.records:
            msg = _("Message count mismatch for {message_name}: expected {expected}, wrote {written}").format(
                message_name=message_name, expected=schema.records, written=written
            )
            raise ValueError(msg)


def extract_schemas(
    mlog: mavutil.mavfile,
    log_data: data_model_log_data.LogData,
    fmtu_definitions: dict[int, _FMTUDefinition],
) -> None:
    """
    Copy pymavlink's discovered FMT/FMTU schemas into log_data.schemas.

    Stored schemas distinguish units for decoded stored values from units for
    values returned after dynamic FMTU scaling.

    Args:
        mlog: An open pymavlink connection (fully read).
        log_data: The LogData instance to populate.
        fmtu_definitions: Per message type, FMTU UNIT and MULT identifiers.

    """
    schema_source = cast("_SchemaSource", mlog)
    for fmt in schema_source.formats.values():
        fmtu_definition = fmtu_definitions.get(fmt.type)
        multipliers = _resolve_multipliers(
            fmt,
            fmtu_definition.mult_ids if fmtu_definition is not None else None,
            schema_source.mult_lookup,
        )
        multipliers_applied_at_ingest = _resolve_multipliers_applied_at_ingest(fmt, multipliers)
        scaled_units = _resolve_scaled_units(
            fmt,
            fmtu_definition.unit_ids if fmtu_definition is not None else None,
            schema_source.unit_lookup,
        )
        log_data.schemas[fmt.name] = data_model_log_data.MessageSchema(
            name=fmt.name,
            msg_type=fmt.type,
            length=fmt.len,
            format=fmt.format,
            fields=list(fmt.columns),
            scaled_units=scaled_units,
            multipliers=multipliers,
            multipliers_applied_at_ingest=multipliers_applied_at_ingest,
            records=log_data.msg_count.get(fmt.name, 0),
            stored_units=_resolve_stored_units(
                scaled_units,
                multipliers,
                multipliers_applied_at_ingest,
            ),
        )


def extract_log_metadata(log_data: data_model_log_data.LogData, logfile: str) -> None:
    """Extract generic metadata from a parsed log."""
    log_data.log_file_size = os.path.getsize(logfile)
    log_data.flight_duration_sec = compute_flight_duration(log_data)


def compute_flight_duration(log_data: data_model_log_data.LogData) -> float | None:
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

            time_seconds = log_data.get_field(message_name, "TimeUS")
            states = log_data.get_field(message_name, state_field)
            total_time = 0
            start_time = None

            # Many logs have multiple arm/disarm events, calculate them separately and sum up
            for timestamp_seconds, state in zip(time_seconds, states, strict=True):
                if state == start_value and start_time is None:
                    start_time = timestamp_seconds
                elif state == stop_value and start_time is not None:
                    total_time += timestamp_seconds - start_time
                    start_time = None

            # If there is no disarm message the flight time can't be calculated.
            if start_time is not None:
                logging_error(
                    _("{message_name} log ends while still armed, no trailing disarm found").format(message_name=message_name)
                )

            if total_time > 0:
                return float(total_time)

    except (KeyError, ValueError) as error:
        logging_error(_("Could not compute flight duration: {error}").format(error=error))

    return None


def extract_log(
    logfile: str,
    progress_callback: Callable[[int, int], None] | None = None,
) -> data_model_log_data.LogData:
    """
    Parse a complete ArduPilot .bin log into a generic LogData object.

    Captures every message type using the log's own FMT
    schema, so new ArduPilot message types are handled automatically.

    (Pymavlink uses hardcoded print statements that break once an issue is found in the log
    so catching the error cannot be implemented yet).

    Args:
        logfile: Path to the .bin log file.
        progress_callback: Optional callback receiving second-pass parser progress as (current, total).

    Returns:
        A populated LogData object.

    """
    log_data = data_model_log_data.LogData()

    # first pass: count messages, capture identity, and let pymavlink discover schemas for preallocated arrays
    mlog = open_log(logfile)
    try:
        fmtu_definitions = _record_message_counts_fields_and_identity(mlog, log_data)
        # extract_schemas should not raise any exception if it does it should fail
        extract_schemas(mlog, log_data, fmtu_definitions)
    finally:
        close_log(mlog)

    _allocate_message_arrays(log_data)

    # second pass: validate data and read it into static sized numpy arrays
    mlog = open_log(logfile)
    try:
        _fill_message_arrays(mlog, log_data, progress_callback)
    finally:
        close_log(mlog)

    extract_log_metadata(log_data, logfile)

    return log_data
