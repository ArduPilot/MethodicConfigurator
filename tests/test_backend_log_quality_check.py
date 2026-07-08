#!/usr/bin/env python3

"""
Tests for ardupilot_methodic_configurator/log_analysis/backend_log_quality_check.py.

SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import numpy as np

from ardupilot_methodic_configurator.log_analysis.backend_log_extraction import LogData, MessageSchema
from ardupilot_methodic_configurator.log_analysis.backend_log_quality_check import (
    validate_configuration_steps,
    validate_fmt_schema,
)


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


class TestValidateFmtSchema:
    """Validate FMT Schema with the rest of the log."""

    def test_field_mismatch_is_detected(self) -> None:
        schema = _make_schema(["A", "B"])
        # columns have A and C, but schema expects A and B: B missing, C extra
        columns = {"A": np.array([1, 3]), "C": np.array([4, 5])}

        result = validate_fmt_schema(schema, columns)

        assert result.valid is False
        assert "mismatch" in result.issues[0].lower()

    def test_matching_records_are_valid(self) -> None:
        schema = _make_schema(["A", "B"])
        columns = {"A": np.array([1, 3]), "B": np.array([2, 4])}

        result = validate_fmt_schema(schema, columns)

        assert result.valid is True
        assert not result.issues


class TestValidateConfigurationSteps:
    """Validate configuration steps using extracted log data."""

    def test_missing_configuration_steps_is_handled(self) -> None:
        log_data = LogData()

        assert not validate_configuration_steps(log_data, configuration_steps={})

    def test_required_message_missing_invalidates_step(self) -> None:
        log_data = LogData()
        log_data.schemas["TEST"] = _make_schema(["A"])
        log_data.raw_messages["TEST"] = {"A": np.array([1])}

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
        log_data = LogData()
        log_data.schemas["TEST"] = _make_schema(["A"])
        log_data.raw_messages["TEST"] = {"A": np.array([1])}

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
