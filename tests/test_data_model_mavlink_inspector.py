#!/usr/bin/env python3
"""
User-facing message ordering and decoded-field behavior without a GUI or transport.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

from dataclasses import replace

import pytest

from ardupilot_methodic_configurator.data_model_data_telemetry import MessageRate, MessageSample, TelemetryState
from ardupilot_methodic_configurator.data_model_mavlink_inspector import MavlinkInspectorDataModel

# pylint: disable=redefined-outer-name


@pytest.fixture
def messages() -> tuple[MessageRate, ...]:
    """Provide numeric values whose lexical order would produce incorrect results."""
    return tuple(
        MessageRate((system, component, name), MessageSample(count, 400, 0, (("value", str(count)),)), hz, rate, age)
        for system, component, name, count, hz, rate, age in (
            (10, 10, "Z_MESSAGE", 10, 10.0, 100.0, 10.0),
            (2, 2, "A_MESSAGE", 2, 2.0, 20.0, 2.0),
            (1, 1, "B_MESSAGE", 100, 100.0, 1000.0, 100.0),
        )
    )


@pytest.mark.parametrize(
    ("column", "order"),
    [
        ("system", (2, 1, 0)),
        ("component", (2, 1, 0)),
        ("message", (1, 2, 0)),
        ("count", (1, 0, 2)),
        ("hz", (1, 0, 2)),
        ("bytes", (1, 0, 2)),
        ("age", (1, 0, 2)),
    ],
)
def test_each_heading_sorts_by_its_meaning_and_reverses(
    messages: tuple[MessageRate, ...], column: str, order: tuple[int, ...]
) -> None:
    """
    Sort IDs, counts and rates numerically and message names alphabetically.

    GIVEN message values such as 2, 10 and 100,
    WHEN a heading is chosen twice,
    THEN its ascending order reverses without comparing formatted strings.
    """
    model = MavlinkInspectorDataModel()
    model.update(TelemetryState(messages=messages))
    assert model.rows == messages
    model.sort_by(column)
    assert model.rows == tuple(messages[index] for index in order)
    assert not model.sort_descending
    model.sort_by(column)
    assert model.rows == tuple(messages[index] for index in reversed(order))
    assert model.sort_descending


@pytest.mark.parametrize("column", ["hz", "bytes", "age"])
def test_rounding_does_not_hide_the_actual_sort_order(messages: tuple[MessageRate, ...], column: str) -> None:
    """
    Preserve distinctions between measurements rounded to the same displayed number.

    GIVEN 1.01 and 1.04 both displayed as 1.0,
    WHEN their rate or age column is sorted,
    THEN the row measuring 1.01 precedes 1.04.
    """
    slow = replace(messages[0], hz=1.01, bytes_per_second=1.01, age=1.01)
    fast = replace(messages[1], hz=1.04, bytes_per_second=1.04, age=1.04)
    model = MavlinkInspectorDataModel()
    model.update(TelemetryState(messages=(fast, slow)))
    model.sort_by(column)
    assert model.rows == (slow, fast)
    assert model.values(slow)[4:] == model.values(fast)[4:] == ("1.0", "1.0", "1.0")


def test_live_snapshot_updates_keep_sort_choice_and_replace_selected_fields(messages: tuple[MessageRate, ...]) -> None:
    """
    Keep the user's ordering while refreshing the selected message's latest contents.

    GIVEN a descending count sort and a known message identifier,
    WHEN counts change and another sender disappears,
    THEN the order and fields update and removed fields are no longer returned.
    """
    model = MavlinkInspectorDataModel()
    model.update(TelemetryState(messages=messages))
    model.sort_by("count")
    model.sort_by("count")
    selected = model.identifier(messages[1])
    assert model.fields(selected) == "value: 2"
    changed = replace(messages[1], sample=MessageSample(200, 900, 1, (("roll", "0.02"), ("pitch", "-0.01"))))
    model.update(TelemetryState(messages=(messages[0], changed)))
    assert model.rows == (changed, messages[0])
    assert model.fields(selected) == "roll: 0.02\npitch: -0.01"
    assert model.fields(model.identifier(messages[2])) == ""
    assert model.sort_column == "count"
    assert model.sort_descending
    model.update(TelemetryState())
    assert not model.rows
    assert model.fields(selected) == ""


def test_switching_headings_starts_ascending_and_equal_values_stay_stable(messages: tuple[MessageRate, ...]) -> None:
    """
    Start each newly chosen sort column ascending without shuffling equal measurements.

    GIVEN a descending sort and rows with identical frequencies,
    WHEN the frequency heading is chosen,
    THEN descending resets and the incoming order of tied rows is retained.
    """
    model = MavlinkInspectorDataModel()
    tied = tuple(replace(row, hz=1.0) for row in messages)
    model.update(TelemetryState(messages=tied))
    model.sort_by("count")
    model.sort_by("count")
    model.sort_by("hz")
    assert not model.sort_descending
    assert model.rows == tied


def test_unknown_heading_does_not_change_the_existing_sort(messages: tuple[MessageRate, ...]) -> None:
    """
    Reject an invalid column without corrupting valid inspection state.

    GIVEN a populated model sorted by count,
    WHEN an unknown heading is requested,
    THEN the request fails and both the rows and sort preferences remain intact.
    """
    model = MavlinkInspectorDataModel()
    model.update(TelemetryState(messages=messages))
    model.sort_by("count")
    before = model.rows
    with pytest.raises(ValueError, match="Unknown MAVLink message column"):
        model.sort_by("payload")
    assert model.rows == before
    assert model.sort_column == "count"
    assert not model.sort_descending


def test_same_message_from_different_senders_keeps_independent_fields(messages: tuple[MessageRate, ...]) -> None:
    """
    Distinguish repeated message names by their system and component IDs.

    GIVEN the same message type from different senders,
    WHEN their fields and display values are read,
    THEN each sender retains its own identifier, counts and decoded values.
    """
    first = replace(messages[0], key=(1, 1, "HEARTBEAT"))
    second = replace(messages[1], key=(1, 2, "HEARTBEAT"))
    third = replace(messages[2], key=(2, 1, "HEARTBEAT"))
    model = MavlinkInspectorDataModel()
    model.update(TelemetryState(messages=(first, second, third)))
    assert [model.identifier(row) for row in model.rows] == ["1:1:HEARTBEAT", "1:2:HEARTBEAT", "2:1:HEARTBEAT"]
    assert [model.fields(model.identifier(row)) for row in model.rows] == ["value: 10", "value: 2", "value: 100"]
    assert model.values(first) == (1, 1, "HEARTBEAT", 10, "10.0", "100.0", "10.0")
    model.update(TelemetryState(messages=(replace(first, sample=replace(first.sample, fields=())),)))
    assert model.fields("1:1:HEARTBEAT") == ""
