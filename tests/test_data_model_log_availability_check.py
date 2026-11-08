#!/usr/bin/env python3

"""
Tests for ardupilot_methodic_configurator/log_analysis/data_model_log_availability_check.py.

SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import numpy as np
import pytest

from ardupilot_methodic_configurator.log_analysis.data_model_log_availability_check import (
    check_cpu_performance_message,
    get_pm_status,
    validate_configuration_steps_data,
    validate_fmt_schema,
)
from ardupilot_methodic_configurator.log_analysis.data_model_log_data import LogData, MessageSchema

# pylint: disable=redefined-outer-name


def _make_schema(fields: list[str]) -> MessageSchema:
    return MessageSchema(
        name="TEST",
        msg_type=1,
        length=4,
        format="f",
        fields=fields,
        stored_units=[""] * len(fields),
        scaled_units=[""] * len(fields),
        multipliers=[None] * len(fields),
        multipliers_applied_at_ingest=[False] * len(fields),
    )


@pytest.fixture
def schema_with_two_fields() -> MessageSchema:
    """Fixture providing a valid schema with two columns."""
    return _make_schema(["A", "B"])


@pytest.fixture
def matching_columns() -> np.ndarray:
    """Fixture providing matching structured columns for schema validation."""
    return np.array([(1, 2), (3, 4)], dtype=[("A", np.int32), ("B", np.int32)])


@pytest.fixture
def mismatching_columns() -> np.ndarray:
    """Fixture providing columns whose field names do not match the schema."""
    return np.array([(1, 4), (3, 5)], dtype=[("A", np.int32), ("C", np.int32)])


class TestValidateFmtSchema:
    """Validate FMT Schema with the rest of the log."""

    def test_field_mismatch_is_detected(self, schema_with_two_fields: MessageSchema, mismatching_columns: np.ndarray) -> None:
        """
        Validate field mismatch detection.

        GIVEN a schema and stored columns with different field names,

        WHEN the schema is validated,
        THEN a field mismatch issue should be reported.
        """
        schema = schema_with_two_fields
        columns = mismatching_columns

        result = validate_fmt_schema(schema, columns)

        assert result.valid is False
        assert "mismatch" in result.issues[0].lower()

    def test_matching_records_are_valid(self, schema_with_two_fields: MessageSchema, matching_columns: np.ndarray) -> None:
        """
        Validate matching schema records.

        GIVEN a schema and matching stored columns,

        WHEN the schema is validated,
        THEN no issues should be reported.
        """
        schema = schema_with_two_fields
        columns = matching_columns

        result = validate_fmt_schema(schema, columns)

        assert result.valid is True
        assert not result.issues


def test_pm_non_finite_values_are_reported_as_invalid() -> None:
    """NaN PM telemetry must not be treated as a valid performance report."""
    log_data = LogData()
    log_data.add_message_columns(
        "PM",
        np.array(
            [(np.nan, np.nan, np.nan, np.nan, np.nan, np.nan, np.nan)],
            dtype=[
                ("Load", "f8"),
                ("NLon", "f8"),
                ("MaxT", "f8"),
                ("Mem", "f8"),
                ("InE", "f8"),
                ("ErC", "f8"),
                ("ErrL", "f8"),
            ],
        ),
    )

    validation = check_cpu_performance_message(log_data)
    status = get_pm_status(log_data)

    assert validation.valid is False
    assert len(validation.issues) == 7
    assert all("non-finite telemetry values" in issue for issue in validation.issues)
    assert status is not None
    assert status.healthy is None


@pytest.mark.parametrize(("mask", "counter"), [("InE", "ErC"), ("IntE", "ErrC")])
def test_pm_internal_errors_are_reported_for_each_firmware_schema(mask: str, counter: str) -> None:
    """Internal error masks and counts are recognized under their historical names."""
    log_data = LogData()
    log_data.add_message_columns("PM", np.array([(0, 0), (1, 3)], dtype=[(mask, "i4"), (counter, "i4")]))

    result = check_cpu_performance_message(log_data)

    assert not result.valid
    assert result.issues == [f"Internal firmware errors were detected ({mask})", "Internal error count: 3"]


@pytest.mark.parametrize("field", ["IntE", "ErrC"])
def test_pm_legacy_internal_error_fields_report_non_finite_values(field: str) -> None:
    """Unreadable historical error fields cannot silently pass validation."""
    log_data = LogData()
    log_data.add_message_columns("PM", np.array([(np.nan,)], dtype=[(field, "f8")]))

    result = check_cpu_performance_message(log_data)

    assert not result.valid
    assert result.issues == [f"{field} contains non-finite telemetry values"]


@pytest.mark.parametrize("error_count", [0, 3])
def test_pm_42_schema_reports_internal_errors_without_requiring_newer_fields(error_count: int) -> None:
    """The 4.2 PM schema remains readable with NLoop and no LR field."""
    fields = ["TimeUS", "NLon", "NLoop", "MaxT", "Mem", "Load", "ErrL", "IntE", "ErrC", "SPIC", "I2CC", "I2CI", "Ex"]
    columns = np.zeros(2, dtype=[(name, "u8") for name in fields])
    columns["NLoop"] = 4000
    columns["IntE"][1] = int(error_count > 0)
    columns["ErrC"][1] = error_count
    log_data = LogData()
    log_data.add_message_columns("PM", columns)

    result = check_cpu_performance_message(log_data)

    assert result.valid is (error_count == 0)
    assert result.issues == (
        ["Internal firmware errors were detected (IntE)", "Internal error count: 3"] if error_count else []
    )


def test_pm_prefers_current_error_fields_when_aliases_coexist() -> None:
    """A mixed schema reports each signal once using the preferred field."""
    log_data = LogData()
    log_data.add_message_columns(
        "PM", np.array([(1, 2, 3, 4)], dtype=[(name, "i4") for name in ("InE", "IntE", "ErC", "ErrC")])
    )

    result = check_cpu_performance_message(log_data)

    assert result.issues == ["Internal firmware errors were detected (InE)", "Internal error count: 3"]


@pytest.mark.parametrize(
    ("field", "values", "expected_issues"),
    [
        ("InE", (0, 0), []),
        ("IntE", (0, 0), []),
        ("ErC", (0, 0), []),
        ("ErrC", (0, 0), []),
        ("InE", (1, 0), ["Internal firmware errors were detected (InE)"]),
        ("IntE", (1, 0), ["Internal firmware errors were detected (IntE)"]),
        ("ErC", (3, 2), ["Internal error count: 3"]),
        ("ErrC", (3, 2), ["Internal error count: 3"]),
    ],
)
def test_pm_reports_each_internal_error_signal_independently(
    field: str, values: tuple[int, int], expected_issues: list[str]
) -> None:
    """
    Report each internal-error signal independently.

    GIVEN a single current or legacy PM internal-error field,
    WHEN the log is validated,
    THEN zero values pass and nonzero values report the peak rather than the sum or last sample.
    """
    log_data = LogData()
    log_data.add_message_columns("PM", np.array([(value,) for value in values], dtype=[(field, "u4")]))

    result = check_cpu_performance_message(log_data)

    assert result.valid is (not expected_issues)
    assert result.issues == expected_issues


@pytest.mark.parametrize(("mask", "counter"), [("InE", "ErC"), ("InE", "ErrC"), ("IntE", "ErC"), ("IntE", "ErrC")])
def test_pm_resolves_mask_and_counter_aliases_independently(mask: str, counter: str) -> None:
    """
    Resolve the mask and count field names independently.

    GIVEN current or legacy names selected independently for mask and count,
    WHEN the PM fields are validated,
    THEN both signals are reported without requiring a matching name pair.
    """
    log_data = LogData()
    log_data.add_message_columns("PM", np.array([(1, 7)], dtype=[(mask, "u4"), (counter, "u4")]))

    result = check_cpu_performance_message(log_data)

    assert not result.valid
    assert result.issues == [f"Internal firmware errors were detected ({mask})", "Internal error count: 7"]


def test_pm_does_not_fall_back_to_legacy_errors_when_current_fields_are_zero() -> None:
    """
    Prefer present current fields even when their values are zero.

    GIVEN zero current error fields alongside nonzero legacy aliases,
    WHEN PM error signals are checked,
    THEN field presence determines precedence even when the preferred values are zero.
    """
    log_data = LogData()
    log_data.add_message_columns(
        "PM", np.array([(0, 1, 0, 9)], dtype=[(name, "u4") for name in ("InE", "IntE", "ErC", "ErrC")])
    )

    result = check_cpu_performance_message(log_data)

    assert result.valid
    assert not result.issues


@pytest.mark.parametrize("field", ["InE", "IntE", "ErC", "ErrC"])
@pytest.mark.parametrize("invalid_value", [np.nan, np.inf, -np.inf])
def test_pm_reports_non_finite_error_samples_without_reducing_them(field: str, invalid_value: float) -> None:
    """
    Diagnose non-finite error samples before numerical reduction.

    GIVEN a PM error field with both finite and non-finite samples,
    WHEN the log is validated,
    THEN it reports unreadable telemetry instead of reducing or converting the invalid samples.
    """
    log_data = LogData()
    log_data.add_message_columns("PM", np.array([(1.0,), (invalid_value,)], dtype=[(field, "f8")]))

    result = check_cpu_performance_message(log_data)

    assert not result.valid
    assert result.issues == [f"{field} contains non-finite telemetry values"]


def test_pm_error_signals_preserve_report_order() -> None:
    """PM error findings retain the established order used by reports and snapshots."""
    log_data = LogData()
    log_data.add_message_columns(
        "PM",
        np.array(
            [(25.0, 3, 0, 20_000, 1, 2, 42)],
            dtype=[
                ("Load", "f8"),
                ("NLon", "i4"),
                ("MaxT", "i4"),
                ("Mem", "i4"),
                ("InE", "i4"),
                ("ErC", "i4"),
                ("ErrL", "i4"),
            ],
        ),
    )

    validation = check_cpu_performance_message(log_data)

    assert validation.issues == [
        "Internal firmware errors were detected (InE)",
        "Internal error count: 2",
        "An internal error line was recorded (ErrL)",
        "Detected 3 scheduler long loops",
    ]


class TestValidateConfigurationSteps:
    """Validate configuration steps using extracted log data."""

    def test_missing_configuration_steps_is_handled(self) -> None:
        """
        Return no validation results for empty configuration steps.

        GIVEN no configuration steps are available,

        WHEN validation is requested,
        THEN the function should return an empty result list.
        """
        log_data = LogData()

        assert not validate_configuration_steps_data(log_data, configuration_steps={})

    def test_required_message_missing_invalidates_step(self) -> None:
        """
        Mark a step invalid when a required message is missing.

        GIVEN a required message is missing from the log,

        WHEN the configuration step is validated,
        THEN the step should be marked invalid.
        """
        log_data = LogData()
        log_data.add_message_columns("TEST", np.array([(1,)], dtype=[("A", np.int32)]), _make_schema(["A"]))

        results = validate_configuration_steps_data(
            log_data,
            {
                "demo.step": {
                    "blog_text": "Demo",
                    "related_bin_messages": {
                        "TEST": {"name": "Demo message", "required": True},
                        "MISSING": {"name": "Missing message", "required": True},
                    },
                }
            },
        )

        assert len(results) == 1
        assert results[0].valid is False
        assert results[0].message_results["TEST"].valid is True
        assert results[0].message_results["MISSING"].valid is False
        assert results[0].message_results["MISSING"].issues == ["Schema not found"]

    def test_valid_required_message_keeps_step_valid(self) -> None:
        """
        Keep a step valid when required data matches.

        GIVEN a required message exists and matches its schema,

        WHEN the configuration step is validated,
        THEN the step should remain valid.
        """
        log_data = LogData()
        log_data.add_message_columns("TEST", np.array([(1,)], dtype=[("A", np.int32)]), _make_schema(["A"]))

        results = validate_configuration_steps_data(
            log_data,
            {
                "demo.step": {
                    "blog_text": "Demo",
                    "related_bin_messages": {
                        "TEST": {"name": "Demo message", "required": True},
                    },
                }
            },
        )

        assert len(results) == 1
        assert results[0].valid is True
        assert results[0].message_results["TEST"].valid is True

    def test_missing_optional_message_does_not_invalidate_step(self) -> None:
        """
        Ignore missing optional messages during validation.

        GIVEN an optional message is absent from the log,

        WHEN the configuration step is validated,
        THEN the step should still be valid.
        """
        log_data = LogData()

        results = validate_configuration_steps_data(
            log_data,
            {
                "demo.step": {
                    "blog_text": "Demo",
                    "related_bin_messages": {
                        "OPTIONAL": {"name": "Optional message", "required": False},
                    },
                }
            },
        )

        assert len(results) == 1
        assert results[0].valid is True
        assert results[0].message_results["OPTIONAL"].valid is True
        assert results[0].message_results["OPTIONAL"].issues == []
