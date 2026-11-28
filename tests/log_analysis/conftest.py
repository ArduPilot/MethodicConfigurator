#!/usr/bin/env python3

"""
Shared pytest fixtures for log analysis tests.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-FileCopyrightText: 2026 Omkar Sarkar <omkarsarkar24@gmail.com>

SPDX-License-Identifier: GPL-3.0-or-later
"""

from collections.abc import Callable

import pytest

from ardupilot_methodic_configurator.log_analysis.data_model_log_analysis_context import LogAnalysisContext


@pytest.fixture
def make_context() -> Callable[..., LogAnalysisContext]:
    """Return a factory that builds LogAnalysisContext instances with empty defaults."""

    def _make(
        parameters: dict[str, float] | None = None,
        *,
        apm_doc: dict | None = None,
        configuration_steps: dict | None = None,
        vehicle_components: dict | None = None,
    ) -> LogAnalysisContext:
        return LogAnalysisContext(
            parameters=parameters or {},
            configuration_steps=configuration_steps or {},
            apm_doc=apm_doc,
            vehicle_components=vehicle_components or {},
        )

    return _make
