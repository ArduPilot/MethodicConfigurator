#!/usr/bin/env python3

"""
Tests for timestamped ArduPilot parameter history.

SPDX-FileCopyrightText: 2026 Donald Smith

SPDX-License-Identifier: GPL-3.0-or-later
"""

import math

import pytest

from ardupilot_methodic_configurator.log_analysis.data_model_parameter_history import ParameterChange, ParameterHistory


def test_absent_parameter_is_unavailable() -> None:
    assert ParameterHistory().value_at("MISSING", 10.0) is None


@pytest.mark.parametrize("time_s", [0.0, 5.0, 10.0])
def test_one_occurrence_applies_throughout_log(time_s: float) -> None:
    history = ParameterHistory({"TEST": 1.0})

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
    history = ParameterHistory(
        {"TEST": 1.0},
        {"TEST": (ParameterChange(10.0, 2.0), ParameterChange(20.0, 3.0))},
    )

    assert history.value_at("TEST", time_s) == expected


def test_initial_value_applies_from_zero_until_first_recorded_change() -> None:
    history = ParameterHistory(
        {"TEST": 1.0},
        {"TEST": (ParameterChange(10.0, 2.0),)},
    )

    assert history.value_at("TEST", 0.0) == 1.0
    assert history.value_at("TEST", 9.999999) == 1.0


def test_repeated_same_value_records_preserve_value() -> None:
    history = ParameterHistory({"TEST": 1.0})

    assert history.value_at("TEST", 7.0) == 1.0
    assert history.value_at("TEST", 10.0) == 1.0


def test_startup_values_and_sparse_changes_are_separate() -> None:
    history = ParameterHistory(
        {"TEST": 1.0, "OTHER": 10.0},
        {"TEST": (ParameterChange(15.0, 2.0),)},
    )

    assert history.initial_values == {"TEST": 1.0, "OTHER": 10.0}
    assert history.changes["TEST"] == (ParameterChange(15.0, 2.0),)
    assert history.latest_values == {"TEST": 2.0, "OTHER": 10.0}


def test_initial_values_are_immutable() -> None:
    history = ParameterHistory({"TEST": 1.0})

    with pytest.raises(TypeError):
        history.initial_values["TEST"] = 2.0  # type: ignore[index]


def test_changes_are_sorted_and_immutable() -> None:
    history = ParameterHistory(
        {"TEST": 1.0},
        {"TEST": [ParameterChange(10.0, 2.0), ParameterChange(5.0, 1.5)]},  # type: ignore[arg-type]
    )

    assert history.changes["TEST"] == (ParameterChange(5.0, 1.5), ParameterChange(10.0, 2.0))
    with pytest.raises(AttributeError):
        history.changes["TEST"].append(ParameterChange(15.0, 3.0))  # type: ignore[union-attr]


def test_multiple_parameter_names_are_independent() -> None:
    history = ParameterHistory(
        {"FIRST": 1.0, "SECOND": 20.0},
        {"FIRST": (ParameterChange(10.0, 2.0),)},
    )

    assert history.value_at("FIRST", 12.0) == 2.0
    assert history.value_at("SECOND", 12.0) == 20.0


def test_records_are_stably_sorted_and_last_duplicate_timestamp_wins() -> None:
    history = ParameterHistory(
        {"TEST": 1.0},
        {"TEST": (ParameterChange(10.0, 2.0), ParameterChange(10.0, 3.0))},
    )

    assert history.value_at("TEST", 4.0) == 1.0
    assert history.value_at("TEST", 10.0) == 3.0
    assert history.value_at("TEST", 15.0) == 3.0
    assert history.value_at("TEST", 20.0) == 3.0


def test_latest_values_are_derived_from_changes() -> None:
    history = ParameterHistory({"TEST": 1.0}, {"TEST": (ParameterChange(10.0, 2.0),)})

    assert history.latest_values == {"TEST": 2.0}


@pytest.mark.parametrize("time_s", [math.nan, math.inf, -math.inf])
def test_non_finite_query_timestamp_is_rejected(time_s: float) -> None:
    history = ParameterHistory({"TEST": 1.0})

    with pytest.raises(ValueError, match="Parameter query time_s must be finite"):
        history.value_at("TEST", time_s)
