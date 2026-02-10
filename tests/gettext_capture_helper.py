#!/usr/bin/env python3

"""
Shared utilities for capturing gettext invocations in generated modules.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

from collections.abc import Callable
from types import ModuleType

import pytest


def capture_gettext_calls(
    monkeypatch: pytest.MonkeyPatch,
    module: ModuleType,
    target: Callable[[], None],
) -> list[str]:
    """Patch module._ to record every string that flows through gettext."""
    captured_values: list[str] = []

    def fake_gettext(value: str) -> str:
        captured_values.append(value)
        return value

    monkeypatch.setattr(module, "_", fake_gettext)
    target()
    return captured_values
