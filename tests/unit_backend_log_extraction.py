#!/usr/bin/env python3

"""
Unit tests for ardupilot_methodic_configurator/backend_bin_log.py.

SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import os
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from ardupilot_methodic_configurator import backend_bin_log
from ardupilot_methodic_configurator.backend_bin_log import (
    _allocate_message_arrays,
    _fill_message_arrays,
    _FMTUDefinition,
    _ParameterHistoryState,
    _ProgressReporter,
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
    log_data.schemas["TEST"] = MessageSchema(
        name="TEST",
        msg_type=1,
        length=4,
        format="f",
        fields=["Value"],
        stored_units=["V"],
        scaled_units=["V"],
        multipliers=[0.01],
        multipliers_applied_at_ingest=[False],
    )
    log_data.msg_count["TEST"] = 2
    log_data.schemas["TEST"].records = 2

    _allocate_message_arrays(log_data)
    _fill_message_arrays(FakeMavLog([MessageStub("TEST", Value=1.0), MessageStub("TEST", Value=2.5)]), log_data)
    return log_data


class TestOpenLog:
    """Tests for open_log()."""

    def test_parser_does_not_reexport_data_model_types(self) -> None:
        """LogData and MessageSchema belong to the data-model module, not the backend parser API."""
        assert not hasattr(backend_bin_log, "LogData")
        assert not hasattr(backend_bin_log, "MessageSchema")

    def test_valid_bin_file_path_yields_connection(self) -> None:
        """GIVEN a valid log path, WHEN open_log is called, THEN the connection is returned."""
        mock_conn = MagicMock()
        with patch(
            "ardupilot_methodic_configurator.backend_bin_log.mavutil.mavlink_connection",
            return_value=mock_conn,
        ):
            result = open_log("dummy.bin")
        assert result is mock_conn

    def test_missing_file_raises_oserror(self) -> None:
        """GIVEN a missing log path, WHEN open_log is called, THEN an OSError is raised."""
        with (
            patch(
                "ardupilot_methodic_configurator.backend_bin_log.mavutil.mavlink_connection",
                side_effect=FileNotFoundError("no such file"),
            ),
            pytest.raises(OSError, match=r"Error opening logfile dummy\.bin"),
        ):
            open_log("dummy.bin")


class TestFirstPassCache:
    """Tests for reuse and invalidation of compact first-pass data."""

    @pytest.fixture(autouse=True)
    def reset_cache(self) -> None:
        """Reset the first-pass cache before each cache test."""
        backend_bin_log._extract_log_first_pass_cached.cache_clear()

    def test_unchanged_log_reuses_first_pass(self, tmp_path: Path) -> None:
        """An unchanged log is parsed in the first pass only once."""
        logfile = tmp_path / "flight.bin"
        logfile.write_bytes(b"log")
        first_pass = LogData()

        with patch.object(backend_bin_log, "_extract_log_first_pass_uncached", return_value=first_pass) as parse:
            cached_first, first_identity = backend_bin_log._get_first_pass_log_data(str(logfile))
            cached_second, second_identity = backend_bin_log._get_first_pass_log_data(str(logfile))

        assert parse.call_count == 1
        assert cached_first is not cached_second
        assert cached_first == cached_second
        assert first_identity == second_identity

    def test_full_pass_mutation_does_not_pollute_cached_first_pass(self, tmp_path: Path) -> None:
        """Full-pass mutations leave subsequent first-pass results compact."""
        logfile = tmp_path / "flight.bin"
        logfile.write_bytes(b"log")
        first_pass = LogData()

        with patch.object(backend_bin_log, "_extract_log_first_pass_uncached", return_value=first_pass):
            full_pass, _ = backend_bin_log._get_first_pass_log_data(str(logfile))
            full_pass.add_message_columns("GPS", np.empty(1, dtype=[("TimeUS", "<u8")]))
            compact_pass, _ = backend_bin_log._get_first_pass_log_data(str(logfile))

        assert compact_pass.get_message_columns("GPS") is None

    def test_loading_another_log_replaces_cached_first_pass(self, tmp_path: Path) -> None:
        """Only the most recently loaded log remains cached."""
        first_logfile = tmp_path / "first.bin"
        second_logfile = tmp_path / "second.bin"
        first_logfile.write_bytes(b"first")
        second_logfile.write_bytes(b"second")

        with patch.object(
            backend_bin_log, "_extract_log_first_pass_uncached", side_effect=[LogData(), LogData(), LogData()]
        ) as parse:
            backend_bin_log._get_first_pass_log_data(str(first_logfile))
            backend_bin_log._get_first_pass_log_data(str(second_logfile))
            backend_bin_log._get_first_pass_log_data(str(first_logfile))

        assert parse.call_count == 3

    def test_same_size_modified_log_invalidates_first_pass(self, tmp_path: Path) -> None:
        """Changing a log invalidates the cache even when its size is unchanged."""
        logfile = tmp_path / "flight.bin"
        logfile.write_bytes(b"abc")
        first_pass = LogData()

        with patch.object(backend_bin_log, "_extract_log_first_pass_uncached", return_value=first_pass) as parse:
            backend_bin_log._get_first_pass_log_data(str(logfile))
            logfile.write_bytes(b"xyz")
            os.utime(logfile, ns=(1_000_000_000, 2_000_000_000))
            backend_bin_log._get_first_pass_log_data(str(logfile))

        assert parse.call_count == 2

    def test_full_extract_reloads_first_pass_when_file_changes_between_passes(self, tmp_path: Path) -> None:
        """Full extraction does not combine first-pass data from an older file state."""
        logfile = tmp_path / "flight.bin"
        logfile.write_bytes(b"log")
        first_pass = LogData()
        second_pass = LogData()
        first_identity = object()
        second_identity = object()
        mock_connection = MagicMock()

        with (
            patch.object(
                backend_bin_log,
                "_get_first_pass_log_data",
                side_effect=[(first_pass, first_identity), (second_pass, second_identity)],
            ) as get_first_pass,
            patch.object(backend_bin_log, "_log_file_identity", return_value=second_identity),
            patch.object(backend_bin_log, "_allocate_message_arrays"),
            patch.object(backend_bin_log, "open_log", return_value=mock_connection),
            patch.object(backend_bin_log, "_fill_message_arrays"),
            patch.object(backend_bin_log, "extract_log_metadata"),
        ):
            result = backend_bin_log.extract_log(str(logfile))

        assert result is second_pass
        assert get_first_pass.call_count == 2
        assert get_first_pass.call_args_list[0].args == (str(logfile), None)
        assert get_first_pass.call_args_list[1].args == (str(logfile), None)


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

        assert log_data.get_field("TEST", "Value", scaled=False).shape == (2,)

        np.testing.assert_allclose(
            log_data.get_field("TEST", "Value", scaled=False),
            np.array([1.0, 2.5], dtype=np.float32),
        )
        np.testing.assert_allclose(log_data.get_field("TEST", "Value"), np.array([0.01, 0.025]))
        assert list(log_data.iter_message_records("TEST")) == [{"Value": 0.01}, {"Value": 0.025}]

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
        log_data.schemas["TEST"] = MessageSchema(
            name="TEST",
            msg_type=1,
            length=4,
            format="f",
            fields=["Value"],
            stored_units=["V"],
            scaled_units=["V"],
            multipliers=[None],
            multipliers_applied_at_ingest=[False],
        )
        log_data.msg_count["TEST"] = 1
        log_data.schemas["TEST"].records = 1
        _allocate_message_arrays(log_data)

        mock_mlog = FakeMavLog([MessageStub("TEST", Other=1.0)])

        with pytest.raises(ValueError, match="Field mismatch for TEST"):
            _fill_message_arrays(mock_mlog, log_data)

    def test_first_pass_records_identity_and_compact_parameter_data(self) -> None:
        """The counting pass captures identity and PARM data without a third log read."""
        log_data = LogData()
        mlog = FakeMavLog(
            [
                MessageStub("VER", FWS="ArduCopter V4.6.3", Maj=4, Min=6, Pat=3),
                MessageStub("PARM", TimeUS=5_000_000, Name="TEST", Value=2.0),
            ]
        )

        _fmtu_definitions, parameter_state = backend_bin_log._record_message_counts_fields_and_identity(mlog, log_data)

        assert log_data.vehicle_type == "ArduCopter"
        assert log_data.firmware_version == (4, 6, 3)
        assert log_data.msg_count["VER"] == 1
        assert parameter_state.first_occurrence == {"TEST": 2.0}
        assert parameter_state.current_values == {"TEST": 2.0}
        assert not parameter_state.changes

    def test_first_pass_prefers_structured_ver_identity(self) -> None:
        """The structured VER identity takes priority over an earlier MSG fallback."""
        log_data = LogData()
        mlog = FakeMavLog(
            [
                MessageStub("MSG", Message="ArduPlane V3.9.9 (stale)"),
                MessageStub("VER", FWS="ArduCopter V4.6.3", Maj=4, Min=6, Pat=3),
            ]
        )

        backend_bin_log._record_message_counts_fields_and_identity(mlog, log_data)

        assert log_data.vehicle_type == "ArduCopter"
        assert log_data.firmware_version == (4, 6, 3)

    def test_first_pass_uses_parseable_msg_identity_as_fallback(self) -> None:
        """The first parseable MSG version supplies identity when VER is unavailable."""
        log_data = LogData()
        mlog = FakeMavLog(
            [
                MessageStub("MSG", Message="Boot started"),
                MessageStub("MSG", Message="ArduPlane V4.5 (abcdef01)"),
            ]
        )

        backend_bin_log._record_message_counts_fields_and_identity(mlog, log_data)

        assert log_data.vehicle_type == "ArduPlane"
        assert log_data.firmware_version == (4, 5, 0)

    def test_first_pass_parameter_history_applies_discovered_scaling(self) -> None:
        """PARM records captured in the first pass are scaled after schema discovery."""
        log_data = LogData()
        log_data.schemas["PARM"] = MessageSchema(
            name="PARM",
            msg_type=1,
            length=1,
            format="QNf",
            fields=["TimeUS", "Name", "Value"],
            stored_units=["µs", "", "dV"],
            scaled_units=["s", "", "V"],
            multipliers=[1e-6, None, 0.1],
            multipliers_applied_at_ingest=[False, False, True],
        )

        parameter_state = backend_bin_log._ParameterHistoryState.create()
        parameter_state.record({"TimeUS": 5_000_000, "Name": "TEST", "Value": 20.0, "Default": 10.0})
        history = backend_bin_log._build_first_pass_parameter_history(log_data, parameter_state)

        assert history.value_at("TEST", 5.0) == 2.0
        assert history.latest_values == {"TEST": 2.0}
        assert log_data.parameter_defaults == {"TEST": 1.0}

    def test_parameter_repeated_during_startup_uses_last_value_and_warns(self) -> None:
        """A boot-time duplicate replaces the initial value and is reported."""
        state = _ParameterHistoryState.create()

        with patch.object(backend_bin_log, "logging_warning") as warning:
            state.record({"TimeUS": 1_000_000, "Name": "TEST", "Value": 1.0})
            state.record({"TimeUS": 1_050_000, "Name": "TEST", "Value": 2.0})

        assert state.first_occurrence == {"TEST": 2.0}
        assert state.current_values == {"TEST": 2.0}
        warning.assert_called_once_with("Parameter TEST changed from 1.0 to 2.0 before boot process completed")

    def test_first_pass_uses_timestamp_gap_and_keeps_late_parameters_as_changes(self) -> None:
        """A late parameter is a timestamped first appearance, not an initial value."""
        log_data = LogData()
        log_data.schemas["PARM"] = MessageSchema(
            name="PARM",
            msg_type=1,
            length=1,
            format="QNf",
            fields=["TimeUS", "Name", "Value"],
            stored_units=["µs", "", ""],
            scaled_units=["s", "", ""],
            multipliers=[1e-6, None, None],
            multipliers_applied_at_ingest=[False, False, False],
        )
        parameter_state = backend_bin_log._ParameterHistoryState.create()
        parameter_state.record({"TimeUS": 1_000_000, "Name": "ENABLE", "Value": 0.0})
        parameter_state.record({"TimeUS": 1_050_000, "Name": "BASE", "Value": 1.0})
        parameter_state.record({"TimeUS": 1_161_000, "Name": "ENABLE", "Value": 1.0})
        parameter_state.record({"TimeUS": 1_170_000, "Name": "NEW_PARAM", "Value": 42.0})

        history = backend_bin_log._build_first_pass_parameter_history(log_data, parameter_state)

        assert parameter_state.initialization_complete is True
        assert history.initial_values == {"ENABLE": 0.0, "BASE": 1.0}
        assert history.latest_values == {"ENABLE": 1.0, "BASE": 1.0, "NEW_PARAM": 42.0}
        assert history.value_at("NEW_PARAM", 1.169) is None
        assert history.value_at("NEW_PARAM", 1.170) == 42.0

    def test_parameter_history_validates_names_and_values(self) -> None:
        """Invalid PARM names and values retain the importer's user-facing errors."""
        state = _ParameterHistoryState.create()

        with pytest.raises(SystemExit, match="Invalid parameter name format"):
            state.record({"Name": "invalid", "Value": 1.0})

        with pytest.raises(SystemExit, match="Error converting not-a-number to float"):
            state.record({"Name": "VALID", "Value": "not-a-number"})

    def test_parameter_history_ignores_incomplete_records(self) -> None:
        """PARM records missing a name or value do not alter the compact state."""
        state = _ParameterHistoryState.create()
        state.record({"Name": "VALID", "TimeUS": 1.0, "Value": 1.0})
        state.record({"Name": "VALID", "TimeUS": 2.0})
        state.record({"Name": "OTHER", "TimeUS": 3.0})

        assert state.first_occurrence == {"VALID": 1.0}
        assert state.current_values == {"VALID": 1.0}

    @pytest.mark.parametrize("timestamp", [float("nan"), float("inf"), float("-inf")])
    def test_parameter_history_rejects_non_finite_record_timestamps(self, timestamp: float) -> None:
        """Non-finite PARM timestamps cannot enter the parameter timeline."""
        state = _ParameterHistoryState.create()

        with pytest.raises(ValueError, match="PARM timestamp for VALID must be finite"):
            state.record({"Name": "VALID", "TimeUS": timestamp, "Value": 1.0})

    def test_parameter_history_ignores_repeated_values_after_startup(self) -> None:
        """Repeated post-startup values do not create redundant changes."""
        state = _ParameterHistoryState.create()
        state.record({"Name": "VALID", "TimeUS": 1.0, "Value": 1.0})
        state.record({"Name": "OTHER", "TimeUS": 2.0, "Value": 2.0})
        state.record({"Name": "VALID", "TimeUS": 111_002.0, "Value": 1.0})

        assert state.changes == {}  # pylint: disable=use-implicit-booleaness-not-comparison

    def test_parameter_history_gap_boundary_is_explicit(self) -> None:
        """The startup snapshot remains open at 110 ms and closes after it."""
        state = _ParameterHistoryState.create()
        state.record({"Name": "TEST", "TimeUS": 0.0, "Value": 1.0})
        state.record({"Name": "TEST", "TimeUS": 110_000.0, "Value": 2.0})

        assert state.initialization_complete is False
        assert not state.changes

        state.record({"Name": "TEST", "TimeUS": 220_001.0, "Value": 3.0})

        assert state.initialization_complete is True
        assert state.changes == {"TEST": [(220_001.0, 3.0)]}

    def test_parameter_history_rejects_decreasing_timestamps(self) -> None:
        """History classification requires the ordered PARM stream used by the log."""
        state = _ParameterHistoryState.create()
        state.record({"Name": "TEST", "TimeUS": 2.0, "Value": 1.0})

        with pytest.raises(ValueError, match=r"PARM timestamps.*non-decreasing"):
            state.record({"Name": "TEST", "TimeUS": 1.0, "Value": 2.0})

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

        _fill_message_arrays(
            mlog,
            log_data,
            _ProgressReporter(lambda current, total: progress_calls.append((current, total)), 0, 100),
        )

        assert progress_calls == [(0, 100), (33, 100), (67, 100), (100, 100)]
        assert log_data.get_message_columns("PARM") is None


class TestExtractSchemas:
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

        log_data = backend_bin_log.extract_log(str(fixture))

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
