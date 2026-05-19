#!/usr/bin/env python3

"""
Capture helper for mocking safe_write in backend_safe_file_io tests.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import io
import json
from typing import IO, Any, Callable


def make_capture_safe_write() -> tuple[dict[str, Any], list[bool], Callable[[str, Callable[[IO[str]], object]], None]]:
    """
    Create a ``safe_write`` side-effect that captures written JSON data.

    Returns a (captured_data, called, side_effect) triple:
    - ``captured_data``: dict updated with the JSON that the write_func produces.
    - ``called``: single-element list (``[False]``) flipped to ``True`` on invocation.
    - ``side_effect``: function to assign to ``mock_safe_write.side_effect``.

    Usage::

        captured_data, called, side_effect = make_capture_safe_write()
        mock_safe_write.side_effect = side_effect
        ...
        assert called[0]
        assert captured_data == expected

    """
    captured_data: dict[str, Any] = {}
    called: list[bool] = [False]

    def _capture(_filepath: str, write_func: Callable[[IO[str]], object]) -> None:
        fake_file = io.StringIO()
        write_func(fake_file)
        captured_data.update(json.loads(fake_file.getvalue()))
        called[0] = True

    return captured_data, called, _capture
