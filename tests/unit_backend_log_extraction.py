#!/usr/bin/env python3

"""
Unit tests for ardupilot_methodic_configurator/log_analysis/backend_log_extraction.py.

SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from ardupilot_methodic_configurator.log_analysis.backend_log_extraction import (
    LogData,
    MessageSchema,
    close_log,
    extract_schemas,
    open_log,
    read_messages,
    store_message,
)


class MessageStub:
    """Minimal message stub for unit tests."""

    def __init__(self, msg_type: str, **payload: object) -> None:
        self._msg_type = msg_type
        self._payload = payload

    def get_type(self) -> str:
        return self._msg_type

    def to_dict(self) -> dict[str, object]:
        return dict(self._payload)


class FakeMavLog:  # pylint: disable=too-few-public-methods
    """Minimal recv_match stub for unit tests."""

    def __init__(self, responses: list[object]) -> None:
        self._responses = list(responses)

    def recv_match(self) -> object | None:
        if not self._responses:
            return None
        next_item = self._responses.pop(0)
        if isinstance(next_item, Exception):
            raise next_item
        return next_item


@pytest.fixture
def empty_log_data() -> LogData:
    """Fixture providing a fresh, empty LogData instance for each test."""
    return LogData()


class TestOpenLog:
    """Tests for open_log()."""

    def test_valid_bin_file_path_yields_connection(self) -> None:
        """GIVEN a valid log path, WHEN open_log is called, THEN the connection is returned."""
        mock_conn = MagicMock()
        with patch(
            "ardupilot_methodic_configurator.log_analysis.backend_log_extraction.mavutil.mavlink_connection",
            return_value=mock_conn,
        ):
            result = open_log("dummy.bin")
        assert result is mock_conn

    def test_missing_file_raises_oserror(self) -> None:
        """GIVEN a missing log path, WHEN open_log is called, THEN an OSError is raised."""
        with (
            patch(
                "ardupilot_methodic_configurator.log_analysis.backend_log_extraction.mavutil.mavlink_connection",
                side_effect=FileNotFoundError("no such file"),
            ),
            pytest.raises(OSError, match=r"Error opening logfile dummy\.bin"),
        ):
            open_log("dummy.bin")


class TestCloseLog:
    """Tests for close_log()."""

    def test_log_connection_is_closed(self) -> None:
        """GIVEN an open log connection, WHEN close_log is called, THEN close() is invoked."""
        mock_conn = MagicMock()
        close_log(mock_conn)
        mock_conn.close.assert_called_once()

    def test_already_closed_connection_does_not_raise(self) -> None:
        """GIVEN a connection that raises on close, WHEN close_log is called, THEN no exception escapes."""
        mock_conn = MagicMock()
        mock_conn.close.side_effect = OSError("already closed")
        close_log(mock_conn)


class TestStoreMessage:  # pylint: disable=too-few-public-methods
    """Tests for store_message()."""

    def test_store_message_adds_to_raw_messages_and_counts(self, empty_log_data: LogData) -> None:  # pylint: disable=redefined-outer-name
        """GIVEN a message, WHEN it is stored, THEN counts and raw payloads are updated."""
        mock_msg = MessageStub("PARM", Name="TEST", Value=1.0)

        store_message(empty_log_data, "PARM", mock_msg)

        assert empty_log_data.msg_count["PARM"] == 1
        assert empty_log_data.raw_messages["PARM"] == [{"Name": "TEST", "Value": 1.0}]


class TestReadMessages:
    """Tests for read_messages()."""

    def test_read_messages_loops_until_none(self, empty_log_data: LogData) -> None:  # pylint: disable=redefined-outer-name
        """GIVEN a finite stream of messages, WHEN read, THEN all are stored and the loop stops."""
        mock_mlog = FakeMavLog([MessageStub("PARM", Name="TEST"), MessageStub("BAT", Volt=16.0)])

        read_messages(mock_mlog, empty_log_data)

        assert empty_log_data.msg_count["PARM"] == 1
        assert empty_log_data.msg_count["BAT"] == 1
        assert len(empty_log_data.raw_messages) == 2

    def test_read_messages_raises_when_recv_match_fails(self, empty_log_data: LogData) -> None:  # pylint: disable=redefined-outer-name
        """GIVEN a parser failure, WHEN read_messages is called, THEN the exception is propagated."""
        mock_mlog = FakeMavLog([RuntimeError("parse failed")])

        with pytest.raises(RuntimeError, match="parse failed"):
            read_messages(mock_mlog, empty_log_data)


class TestExtractSchemas:  # pylint: disable=too-few-public-methods
    """Tests for extract_schemas()."""

    def test_extract_schemas_populates_message_schema(self, empty_log_data: LogData) -> None:  # pylint: disable=redefined-outer-name
        """GIVEN discovered FMT metadata, WHEN schemas are extracted, THEN LogData is populated."""
        mock_fmt = SimpleNamespace(
            name="PARM",
            type=1,
            len=10,
            format="f",
            columns=["Value"],
            units=["V"],
            msg_mults=[1.0],
        )
        mock_mlog = SimpleNamespace(formats={"PARM": mock_fmt})
        empty_log_data.msg_count["PARM"] = 5

        extract_schemas(mock_mlog, empty_log_data)

        schema = empty_log_data.schemas["PARM"]
        assert isinstance(schema, MessageSchema)
        assert schema.name == "PARM"
        assert schema.fields == ["Value"]
        assert schema.units == ["V"]
        assert schema.records == 5
