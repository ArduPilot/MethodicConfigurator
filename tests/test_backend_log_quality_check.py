#!/usr/bin/env python3

"""
Tests for ardupilot_methodic_configurator/log_analysis/backend_log_quality_check.py.

SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import numpy as np
import pytest

from ardupilot_methodic_configurator.log_analysis.backend_log_extraction import LogData, MessageSchema
from ardupilot_methodic_configurator.log_analysis.backend_log_quality_check import (
    validate_configuration_steps,
    validate_fmt_schema,
)

# pylint: disable=redefined-outer-name


def _make_schema(fields: list[str]) -> MessageSchema:
    return MessageSchema(
        name="TEST",
        msg_type=1,
        length=4,
        format="f",
        fields=fields,
        units=[""] * len(fields),
        multipliers=[None] * len(fields),
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

        assert not validate_configuration_steps(log_data, configuration_steps={})

    def test_required_message_missing_invalidates_step(self) -> None:
        """
        Mark a step invalid when a required message is missing.

        GIVEN a required message is missing from the log,

        WHEN the configuration step is validated,
        THEN the step should be marked invalid.
        """
        log_data = LogData()
        log_data.schemas["TEST"] = _make_schema(["A"])
        log_data._raw_messages["TEST"] = np.array([(1,)], dtype=[("A", np.int32)])  # pylint: disable=protected-access

        results = validate_configuration_steps(
            log_data,
            configuration_steps={
                "steps": {
                    "demo.step": {
                        "blog_text": "Demo",
                        "related_bin_messages": {
                            "TEST": {"name": "Demo message", "required": True},
                            "MISSING": {"name": "Missing message", "required": True},
                        },
                    }
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
        log_data.schemas["TEST"] = _make_schema(["A"])
        log_data._raw_messages["TEST"] = np.array([(1,)], dtype=[("A", np.int32)])  # pylint: disable=protected-access

        results = validate_configuration_steps(
            log_data,
            configuration_steps={
                "steps": {
                    "demo.step": {
                        "blog_text": "Demo",
                        "related_bin_messages": {
                            "TEST": {"name": "Demo message", "required": True},
                        },
                    }
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

        results = validate_configuration_steps(
            log_data,
            configuration_steps={
                "steps": {
                    "demo.step": {
                        "blog_text": "Demo",
                        "related_bin_messages": {
                            "OPTIONAL": {"name": "Optional message", "required": False},
                        },
                    }
                }
            },
        )

        assert len(results) == 1
        assert results[0].valid is True
        assert results[0].message_results["OPTIONAL"].valid is True
        assert results[0].message_results["OPTIONAL"].issues == []
