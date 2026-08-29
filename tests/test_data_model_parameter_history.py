#!/usr/bin/env python3

"""
Tests for timestamped ArduPilot parameter history.

SPDX-FileCopyrightText: 2026 Donald Smith

SPDX-License-Identifier: GPL-3.0-or-later
"""

import math

import numpy as np
import pytest

from ardupilot_methodic_configurator.log_analysis.data_model_log_data import LogData, MessageSchema
from ardupilot_methodic_configurator.log_analysis.data_model_parameter_history import ParameterHistory

# The PARM LogData fixture intentionally mirrors backend orchestration setup.
# pylint: disable=duplicate-code


def _log_data(records: list[tuple[float, str, float]]) -> LogData:
    log_data = LogData()
    rows = np.array(records, dtype=[("TimeUS", "f8"), ("Name", "U16"), ("Value", "f8")])
    log_data.add_message_columns(
        "PARM",
        rows,
        MessageSchema(
            name="PARM",
            msg_type=1,
            length=1,
            format="Qnf",
            fields=["TimeUS", "Name", "Value"],
            stored_units=["s", "", ""],
            scaled_units=["s", "", ""],
            multipliers=[None, None, None],
            multipliers_applied_at_ingest=[False, False, False],
            records=len(records),
        ),
    )
    return log_data


def test_absent_parameter_is_unavailable() -> None:
    assert ParameterHistory.from_log_data(LogData()).value_at("MISSING", 10.0) is None


@pytest.mark.parametrize("time_s", [0.0, 5.0, 10.0])
def test_one_occurrence_applies_throughout_log(time_s: float) -> None:
    history = ParameterHistory.from_log_data(_log_data([(5.0, "TEST", 1.0)]))

    assert history.value_at("TEST", time_s) == 1.0


@pytest.mark.parametrize(
    ("time_s", "expected"),
    [
        (4.999999, 1.0),
        (5.0, 1.0),
        (5.000001, 1.0),
        (9.999999, 1.0),
        (10.0, 2.0),
        (10.000001, 2.0),
        (14.0, 2.0),
        (20.0, 3.0),
        (25.0, 3.0),
    ],
)
def test_value_at_uses_baseline_and_stepwise_changes(time_s: float, expected: float) -> None:
    history = ParameterHistory.from_log_data(_log_data([(5.0, "TEST", 1.0), (10.0, "TEST", 2.0), (20.0, "TEST", 3.0)]))

    assert history.value_at("TEST", time_s) == expected


def test_repeated_same_value_records_preserve_value() -> None:
    history = ParameterHistory.from_log_data(_log_data([(5.0, "TEST", 1.0), (10.0, "TEST", 1.0)]))

    assert history.value_at("TEST", 7.0) == 1.0
    assert history.value_at("TEST", 10.0) == 1.0


def test_multiple_parameter_names_are_independent() -> None:
    history = ParameterHistory.from_log_data(_log_data([(5.0, "FIRST", 1.0), (6.0, "SECOND", 20.0), (10.0, "FIRST", 2.0)]))

    assert history.value_at("FIRST", 12.0) == 2.0
    assert history.value_at("SECOND", 12.0) == 20.0


def test_records_are_stably_sorted_and_last_duplicate_timestamp_wins() -> None:
    history = ParameterHistory.from_log_data(_log_data([(20.0, "TEST", 3.0), (10.0, "TEST", 1.0), (10.0, "TEST", 2.0)]))

    assert history.value_at("TEST", 9.0) == 1.0
    assert history.value_at("TEST", 10.0) == 2.0
    assert history.value_at("TEST", 15.0) == 2.0
    assert history.value_at("TEST", 20.0) == 3.0


def test_scaled_timeus_is_queried_in_seconds() -> None:
    log_data = _log_data([(5_000_000.0, "TEST", 1.0), (10_000_000.0, "TEST", 2.0)])
    schema = log_data.schemas["PARM"]
    schema.stored_units[0] = "µs"
    schema.multipliers[0] = 1e-6

    history = ParameterHistory.from_log_data(log_data)

    assert history.value_at("TEST", 9.0) == 1.0
    assert history.value_at("TEST", 10.0) == 2.0


def test_incomplete_records_are_ignored() -> None:
    log_data = _log_data([(5.0, "TEST", 1.0)])
    log_data.add_message_columns(
        "PARM",
        np.array([("TEST", 2.0)], dtype=[("Name", "U16"), ("Value", "f8")]),
        MessageSchema(
            name="PARM",
            msg_type=1,
            length=1,
            format="nf",
            fields=["Name", "Value"],
            stored_units=["", ""],
            scaled_units=["", ""],
            multipliers=[None, None],
            multipliers_applied_at_ingest=[False, False],
            records=1,
        ),
    )

    assert ParameterHistory.from_log_data(log_data).value_at("TEST", 10.0) is None


@pytest.mark.parametrize("time_s", [math.nan, math.inf, -math.inf])
def test_non_finite_record_timestamp_is_rejected(time_s: float) -> None:
    with pytest.raises(ValueError, match="PARM timestamp for TEST must be finite"):
        ParameterHistory.from_log_data(_log_data([(time_s, "TEST", 1.0)]))


@pytest.mark.parametrize("time_s", [math.nan, math.inf, -math.inf])
def test_non_finite_query_timestamp_is_rejected(time_s: float) -> None:
    history = ParameterHistory.from_log_data(_log_data([(5.0, "TEST", 1.0)]))

    with pytest.raises(ValueError, match="Parameter query time_s must be finite"):
        history.value_at("TEST", time_s)
