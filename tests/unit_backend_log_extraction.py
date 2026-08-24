#!/usr/bin/env python3

"""
Unit tests for ardupilot_methodic_configurator/log_analysis/backend_log_extraction.py.

SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from ardupilot_methodic_configurator.log_analysis import backend_log_extraction
from ardupilot_methodic_configurator.log_analysis.backend_log_extraction import (
    _allocate_message_arrays,
    _fill_message_arrays,
    _FMTUDefinition,
    _schema_numpy_dtype,
    close_log,
    extract_schemas,
    open_log,
)
from ardupilot_methodic_configurator.log_analysis.data_model_log_data import LogData, MessageSchema

# pylint: disable=redefined-outer-name, protected-access


class MessageStub:
    """Minimal message stub for unit tests."""

    def __init__(self, msg_type: str, **payload: object) -> None:
        self._msg_type = msg_type
        self._payload = payload
        self._elements = list(payload.values())
        for key, value in payload.items():
            setattr(self, key, value)

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
        stored_units=["V"],
        scaled_units=["V"],
        multipliers=[0.01],
        multipliers_applied_at_ingest=[False],
    )
    log_data.msg_count["PARM"] = 2
    log_data.schemas["PARM"].records = 2

    _allocate_message_arrays(log_data)
    _fill_message_arrays(FakeMavLog([MessageStub("PARM", Value=1.0), MessageStub("PARM", Value=2.5)]), log_data)
    return log_data


class TestOpenLog:
    """Tests for open_log()."""

    def test_parser_does_not_reexport_data_model_types(self) -> None:
        """LogData and MessageSchema belong to the data-model module, not the backend parser API."""
        assert not hasattr(backend_log_extraction, "LogData")
        assert not hasattr(backend_log_extraction, "MessageSchema")

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
            format="bHfg",
            fields=["a", "b", "c", "d"],
            stored_units=["", "", "", ""],
            scaled_units=["", "", "", ""],
            multipliers=[None, None, None, None],
            multipliers_applied_at_ingest=[False, False, False, False],
        )

        dtype = _schema_numpy_dtype(schema)

        assert dtype.names == ("a", "b", "c", "d")
        assert dtype["a"] == np.dtype(np.int8)
        assert dtype["b"] == np.dtype(np.uint16)
        assert dtype["c"] == np.dtype(np.float32)
        assert dtype["d"] == np.dtype(np.float16)

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

    def test_fixed_point_fields_store_raw_values_and_scale_lazily(self) -> None:
        """
        Store compact fixed-point values and scale them on access.

        GIVEN fixed-point fields with raw pymavlink elements,

        WHEN values are stored in the preallocated array,
        THEN the raw integer storage is retained and scaled values are floats.
        """
        log_data = LogData()
        log_data.schemas["INTS"] = MessageSchema(
            name="INTS",
            msg_type=1,
            length=8,
            format="ce",
            fields=["Small", "Large"],
            stored_units=["", ""],
            scaled_units=["", ""],
            multipliers=[0.01, 0.01],
            multipliers_applied_at_ingest=[False, False],
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

        raw_small = log_data.get_field("INTS", "Small", scaled=False)
        raw_large = log_data.get_field("INTS", "Large", scaled=False)
        small = log_data.get_field("INTS", "Small")
        large = log_data.get_field("INTS", "Large")

        assert raw_small.dtype == np.int16
        assert raw_large.dtype == np.int32
        assert small.dtype == np.float64
        assert large.dtype == np.float64
        np.testing.assert_array_equal(raw_small, np.array([1, 3], dtype=np.int16))
        np.testing.assert_array_equal(raw_large, np.array([2, 4], dtype=np.int32))
        np.testing.assert_array_equal(small, np.array([0.01, 0.03]))
        np.testing.assert_array_equal(large, np.array([0.02, 0.04]))

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
            stored_units=["V"],
            scaled_units=["V"],
            multipliers=[None],
            multipliers_applied_at_ingest=[False],
        )
        log_data.msg_count["PARM"] = 1
        log_data.schemas["PARM"].records = 1
        _allocate_message_arrays(log_data)

        mock_mlog = FakeMavLog([MessageStub("PARM", Other=1.0)])

        with pytest.raises(ValueError, match="Field mismatch for PARM"):
            _fill_message_arrays(mock_mlog, log_data)

    def test_first_pass_records_log_identity_from_ver_message(self) -> None:
        """The counting pass also captures firmware identity without a separate scan."""
        log_data = LogData()
        mlog = FakeMavLog([MessageStub("VER", FWS="ArduCopter V4.6.3", Maj=4, Min=6, Pat=3)])

        backend_log_extraction._record_message_counts_fields_and_identity(mlog, log_data)

        assert log_data.vehicle_type == "ArduCopter"
        assert log_data.firmware_version == (4, 6, 3)
        assert log_data.msg_count["VER"] == 1

    def test_second_pass_reports_progress_against_known_message_count(self) -> None:
        """The fill pass can report determinate progress from counted messages."""
        log_data = LogData()
        log_data.schemas["PARM"] = MessageSchema(
            name="PARM",
            msg_type=1,
            length=4,
            format="f",
            fields=["Value"],
            stored_units=["V"],
            scaled_units=["V"],
            multipliers=[None],
            multipliers_applied_at_ingest=[False],
            records=2,
        )
        log_data.msg_count = {"PARM": 2, "MSG": 1}
        _allocate_message_arrays(log_data)
        mlog = FakeMavLog(
            [
                MessageStub("MSG", Message="ArduCopter V4.6.3 (abc123)"),
                MessageStub("PARM", Value=1.0),
                MessageStub("PARM", Value=2.0),
            ]
        )
        progress_calls: list[tuple[int, int]] = []

        _fill_message_arrays(mlog, log_data, lambda current, total: progress_calls.append((current, total)))

        assert progress_calls == [(1, 3), (2, 3), (3, 3)]


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
        mock_mlog = SimpleNamespace(formats={"PARM": mock_fmt}, mult_lookup={}, unit_lookup={})
        empty_log_data.msg_count["PARM"] = 5

        extract_schemas(mock_mlog, empty_log_data, {})

        schema = empty_log_data.schemas["PARM"]
        assert isinstance(schema, MessageSchema)
        assert schema.name == "PARM"
        assert schema.fields == ["Value"]
        assert schema.scaled_units == ["V"]
        assert schema.stored_units == ["V"]
        assert schema.multipliers_applied_at_ingest == [False]
        assert schema.records == 5

    def test_extract_schemas_distinguishes_stored_and_scaled_units(self, empty_log_data: LogData) -> None:  # pylint: disable=redefined-outer-name
        """FMTU multipliers convert stored values to the unprefixed UNIT unit."""
        mock_fmt = SimpleNamespace(
            name="BAT",
            type=88,
            len=10,
            format="f",
            columns=["CurrTot"],
            units=["mAh"],
            msg_mults=[None],
        )
        mock_mlog = SimpleNamespace(
            formats={"BAT": mock_fmt},
            mult_lookup={"C": 0.001},
            unit_lookup={"a": "Ah"},
        )

        extract_schemas(
            mock_mlog,
            empty_log_data,
            {88: _FMTUDefinition(unit_ids="a", mult_ids="C")},
        )

        schema = empty_log_data.schemas["BAT"]
        assert schema.stored_units == ["Ah"]
        assert schema.scaled_units == ["Ah"]
        assert schema.multipliers == [0.001]
        assert schema.multipliers_applied_at_ingest == [True]

    def test_fixture_preserves_fixed_and_dynamic_scaling(self) -> None:
        """A real log retains fixed-point precision and scales FMTU values once."""
        fixture = Path(__file__).parent / "fixtures" / "backend_log_80k.bin"

        log_data = backend_log_extraction.extract_log(str(fixture))

        battery_schema = log_data.schemas["BAT"]
        current_total_index = battery_schema.fields.index("CurrTot")
        current_total = log_data.get_field("BAT", "CurrTot", scaled=False)[0]
        scaled_current_total = log_data.get_field("BAT", "CurrTot")[0]
        temperature = log_data.get_field("BARO", "Temp", scaled=False)[0]

        assert battery_schema.stored_units[current_total_index] == "Ah"
        assert battery_schema.scaled_units[current_total_index] == "Ah"
        assert battery_schema.multipliers[current_total_index] == 0.001
        assert battery_schema.multipliers_applied_at_ingest[current_total_index] is True
        assert scaled_current_total == pytest.approx(current_total)
        assert current_total == pytest.approx(0.0017867862)
        assert temperature == 3607
        assert log_data.get_field("BARO", "Temp")[0] == pytest.approx(36.07)
