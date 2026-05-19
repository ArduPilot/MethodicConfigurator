#!/usr/bin/env python3

"""
Unit tests for the make_capture_safe_write test helper in test_helpers.py.

These tests verify the contract of the capture helper that is used across
many test files to assert JSON data written through safe_write mocks.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import io
import json
from unittest.mock import patch

from test_backend_safe_file_io_write_capture import make_capture_safe_write

from ardupilot_methodic_configurator.backend_filesystem_vehicle_components import VehicleComponents


class TestMakeCapturesSafeWrite:
    """Unit tests for the make_capture_safe_write test helper."""

    def test_capture_helper_records_written_json_data(self) -> None:
        """
        make_capture_safe_write records JSON written through its side_effect.

        GIVEN: A freshly created capture helper with empty state
        WHEN: The side_effect is called with a write function that emits JSON
        THEN: captured_data should contain the written JSON
        AND: called[0] should flip to True
        """
        captured_data, called, side_effect = make_capture_safe_write()

        assert called[0] is False
        assert not captured_data

        test_data = {"key": "value", "number": 42}

        def write_json(f: io.TextIOWrapper) -> None:
            json.dump(test_data, f)

        side_effect("/fake/path", write_json)

        assert called[0] is True
        assert captured_data == test_data

    def test_capture_helper_can_be_used_as_mock_side_effect(self) -> None:
        """
        make_capture_safe_write integrates correctly when patching a real caller's safe_write.

        GIVEN: A real caller (VehicleComponents) that writes JSON via safe_write internally
        WHEN: safe_write in that module is replaced with the capture side_effect
        THEN: The JSON data the caller would have written is captured for assertion
        AND: called[0] should be True after the caller runs
        """
        captured_data, called, side_effect = make_capture_safe_write()

        with (
            patch("ardupilot_methodic_configurator.backend_filesystem_vehicle_components.safe_write") as mock_safe_write,
            patch(
                "ardupilot_methodic_configurator.backend_filesystem_program_settings.ProgramSettings.get_templates_base_dir",
                return_value="/fake",
            ),
            patch("ardupilot_methodic_configurator.backend_filesystem_vehicle_components.os_makedirs"),
        ):
            mock_safe_write.side_effect = side_effect
            templates = {"Motor": [{"name": "Test Motor", "data": {"kv": 2300}}]}
            VehicleComponents().save_component_templates_to_file(templates)

        assert called[0] is True
        assert "Motor" in captured_data
