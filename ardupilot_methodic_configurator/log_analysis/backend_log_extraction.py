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
from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Any

from pymavlink import mavutil


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
        msg = f"Error opening logfile {logfile}: {e!s}"
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


# Cap raw_messages storage to 1 sample per message type to prevent memory exhaustion on large .bin log files
# Set to 0 to store them all (not recommended for large logs)
MAX_SAMPLES_PER_TYPE = 1
"""Maximum number of sample records stored per message type (memory guard)."""


@dataclass
class LogData:
    """
    Storing parsed log metadata and one sample record per message type.

    Attributes:
        schemas: Raw message definitions extracted from FMT/FMTU/UNIT/MULT,
            keyed by message name. Each holds columns, units, multipliers and
            types exactly as pymavlink reports them.
        raw_messages: Up to MAX_SAMPLES_PER_TYPE decoded records per message type,
            keyed by type name. Capped to prevent memory exhaustion on large logs.
        msg_count: Total number of decoded messages for each message type name.

    """

    schemas: dict[str, MessageSchema] = field(default_factory=dict)
    raw_messages: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    msg_count: dict[str, int] = field(default_factory=dict)


def store_message(log_data: LogData, msg_type: str, msg: Any) -> None:  # noqa: ANN401
    """
    Record one decoded message: increment its count and store a sample of its fields.

    Only up to MAX_SAMPLES_PER_TYPE records are stored per type to cap memory usage.

    Args:
        log_data: The LogData instance to update.
        msg_type: The message type name (e.g. "GPS").
        msg: The decoded pymavlink message.

    """
    log_data.msg_count[msg_type] = log_data.msg_count.get(msg_type, 0) + 1
    bucket = log_data.raw_messages.setdefault(msg_type, [])
    if MAX_SAMPLES_PER_TYPE == 0 or len(bucket) < MAX_SAMPLES_PER_TYPE:
        bucket.append(msg.to_dict())


def read_messages(mlog: mavutil.mavfile, log_data: LogData) -> None:
    """
    Read every message from the log into log_data.

    Args:
        mlog: An open pymavlink connection.
        log_data: The LogData instance to populate.

    """
    for msg in _iter_messages(mlog):
        store_message(log_data, msg.get_type(), msg)


def extract_schemas(mlog: mavutil.mavfile, log_data: LogData) -> None:
    """
    Copy pymavlink's discovered FMT/FMTU schemas into log_data.schemas.

    Stored dicts (not pymavlink objects). Raw metadata only units and multipliers are stored.

    Args:
        mlog: An open pymavlink connection (fully read).
        log_data: The LogData instance to populate.

    """
    for fmt in mlog.formats.values():
        log_data.schemas[fmt.name] = MessageSchema(
            name=fmt.name,
            msg_type=fmt.type,
            length=fmt.len,
            format=fmt.format,
            fields=list(fmt.columns),
            units=list(fmt.units) if fmt.units is not None else [],
            multipliers=list(getattr(fmt, "msg_mults", None) or []),
            records=log_data.msg_count.get(fmt.name, 0),
        )


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
    mlog = open_log(logfile)

    try:
        read_messages(mlog, log_data)
        # extract_schemas should not raise any exception if it does it should fail
        extract_schemas(mlog, log_data)
    finally:
        close_log(mlog)

    return log_data
