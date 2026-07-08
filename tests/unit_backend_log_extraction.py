#!/usr/bin/env python3

"""
Unit tests for ardupilot_methodic_configurator/log_analysis/backend_log_extraction.py.

SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from ardupilot_methodic_configurator.log_analysis.backend_log_extraction import (
    LogData,
    MessageSchema,
    _allocate_message_arrays,
    _fill_message_arrays,
    _schema_numpy_dtype,
    close_log,
    extract_schemas,
    open_log,
)

# pylint: disable=redefined-outer-name, protected-access


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


@pytest.fixture
def populated_log_data_with_float_field() -> LogData:
    """Fixture providing one preallocated message type with floating-point values."""
    log_data = LogData()
    log_data.schemas["PARM"] = MessageSchema(
        name="PARM",
        msg_type=1,
        length=4,
        format="f",
        fields=["Value"],
        units=["V"],
        multipliers=[0.01],
    )
    log_data.msg_count["PARM"] = 2
    log_data.schemas["PARM"].records = 2

    _allocate_message_arrays(log_data)
    _fill_message_arrays(FakeMavLog([MessageStub("PARM", Value=1.0), MessageStub("PARM", Value=2.5)]), log_data)
    return log_data


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


class TestNumpyAllocation:
    """Tests for the structured numpy allocation helpers."""

    def test_schema_numpy_dtype_maps_numeric_fields(self) -> None:
        """
        Map numeric FMT characters to numpy dtypes.

        GIVEN a schema with numeric FMT characters,

        WHEN a numpy dtype is created,
        THEN the dtype should match the declared field types.
        """
        schema = MessageSchema(
            name="TEST",
            msg_type=1,
            length=4,
            format="bHf",
            fields=["a", "b", "c"],
            units=["", "", ""],
            multipliers=[None, None, None],
        )

        dtype = _schema_numpy_dtype(schema)

        assert dtype.names == ("a", "b", "c")
        assert dtype["a"] == np.dtype(np.int8)
        assert dtype["b"] == np.dtype(np.uint16)
        assert dtype["c"] == np.dtype(np.float32)

    def test_preallocated_arrays_store_and_scale_message_values(self, populated_log_data_with_float_field: LogData) -> None:
        """
        Store and scale preallocated message values.

        GIVEN a preallocated message array with multipliers,

        WHEN the stored values are accessed,
        THEN raw values remain unchanged and scaled access applies the multiplier.
        """
        log_data = populated_log_data_with_float_field

        assert log_data.get_field("PARM", "Value", scaled=False).shape == (2,)

        np.testing.assert_allclose(
            log_data.get_field("PARM", "Value", scaled=False),
            np.array([1.0, 2.5], dtype=np.float32),
        )
        np.testing.assert_allclose(log_data.get_field("PARM", "Value"), np.array([0.01, 0.025]))
        assert list(log_data.iter_message_records("PARM")) == [{"Value": 0.01}, {"Value": 0.025}]

    def test_get_message_columns_returns_raw_structured_array(self) -> None:
        """
        Return the raw structured array for a message type.

        GIVEN a stored structured array,

        WHEN the raw columns are requested,
        THEN the original structured numpy array is returned.
        """
        log_data = LogData()
        log_data._raw_messages["PARM"] = np.array([(1.0,)], dtype=[("Value", np.float32)])

        columns = log_data.get_message_columns("PARM")

        assert columns is not None
        assert columns.dtype.names == ("Value",)

    def test_integer_scaling_promotes_dtype(self) -> None:
        """
        Promote fixed-point integers when scaling.

        GIVEN fixed-point integer fields,

        WHEN scaled values are accessed,
        THEN the returned dtype should be widened to avoid overflow.
        """
        log_data = LogData()
        log_data.schemas["INTS"] = MessageSchema(
            name="INTS",
            msg_type=1,
            length=8,
            format="ce",
            fields=["Small", "Large"],
            units=["", ""],
            multipliers=[100, 100],
        )
        log_data.msg_count["INTS"] = 2
        log_data.schemas["INTS"].records = 2

        _allocate_message_arrays(log_data)
        mock_mlog = FakeMavLog(
            [
                MessageStub("INTS", Small=1, Large=2),
                MessageStub("INTS", Small=3, Large=4),
            ]
        )
        _fill_message_arrays(mock_mlog, log_data)

        small = log_data.get_field("INTS", "Small")
        large = log_data.get_field("INTS", "Large")

        assert small.dtype == np.int32
        assert large.dtype == np.int64
        np.testing.assert_array_equal(small, np.array([100, 300], dtype=np.int32))
        np.testing.assert_array_equal(large, np.array([200, 400], dtype=np.int64))

    def test_fill_message_arrays_raises_on_field_mismatch(self) -> None:
        """
        Reject messages whose fields do not match the schema.

        GIVEN a decoded message with unexpected fields,

        WHEN the preallocated arrays are filled,
        THEN a validation error is raised.
        """
        log_data = LogData()
        log_data.schemas["PARM"] = MessageSchema(
            name="PARM",
            msg_type=1,
            length=4,
            format="f",
            fields=["Value"],
            units=["V"],
            multipliers=[None],
        )
        log_data.msg_count["PARM"] = 1
        log_data.schemas["PARM"].records = 1
        _allocate_message_arrays(log_data)

        mock_mlog = FakeMavLog([MessageStub("PARM", Other=1.0)])

        with pytest.raises(ValueError, match="Field mismatch for PARM"):
            _fill_message_arrays(mock_mlog, log_data)


class TestExtractSchemas:  # pylint: disable=too-few-public-methods
    """Tests for extract_schemas()."""

    def test_extract_schemas_populates_message_schema(self, empty_log_data: LogData) -> None:  # pylint: disable=redefined-outer-name
        """
        Populate schemas from discovered FMT metadata.

        GIVEN discovered FMT metadata,

        WHEN schemas are extracted,
        THEN LogData should contain the schema details and record count.
        """
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
