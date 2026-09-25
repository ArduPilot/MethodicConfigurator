#!/usr/bin/env python3

"""
Behaviour-driven tests for the parameter export dialog.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2026 Amilcar Lucas

SPDX-License-Identifier: GPL-3.0-or-later
"""

from ardupilot_methodic_configurator.data_model_parameter_editor import ParameterExportFilters
from ardupilot_methodic_configurator.frontend_tkinter_parameter_export import build_export_filename


class TestParameterExportFilename:
    """Test descriptive filenames generated from export filters."""

    def test_filename_describes_single_selection_for_each_property(self) -> None:
        """
        Filename includes each selected category when every property has one option selected.

        GIVEN: One option is selected for every export filter pair
        WHEN: The export filename is built
        THEN: The filename describes all four selected categories in filter order
        """
        filters = ParameterExportFilters(
            include_calibrations=True,
            include_non_calibrations=False,
            include_read_only=True,
            include_non_read_only=False,
            include_default_values=True,
            include_non_default_values=False,
            include_inside_limits=True,
            include_outside_limits=False,
        )

        result = build_export_filename("ArduCopter", filters)

        assert result == "ArduCopter_calibrations_read-only_default-values_inside-limits.param"

    def test_filename_describes_non_selected_categories(self) -> None:
        """
        Filename identifies the second option when it is selected exclusively.

        GIVEN: Only the non-calibration, non-read-only, non-default, and outside-limit options are selected
        WHEN: The export filename is built
        THEN: The filename contains the corresponding non-category names
        """
        filters = ParameterExportFilters(
            include_calibrations=False,
            include_non_calibrations=True,
            include_read_only=False,
            include_non_read_only=True,
            include_default_values=False,
            include_non_default_values=True,
            include_inside_limits=False,
            include_outside_limits=True,
        )

        result = build_export_filename("Rover", filters)

        assert result == "Rover_non-calibrations_non-read-only_non-default-values_outside-limits.param"

    def test_filename_omits_properties_with_both_options_selected(self) -> None:
        """
        Filename omits non-descriptive properties when both options are selected.

        GIVEN: Both options are selected for every export filter pair
        WHEN: The export filename is built
        THEN: The filename contains only the vehicle name and param extension
        """
        filters = ParameterExportFilters(
            include_calibrations=True,
            include_non_calibrations=True,
            include_read_only=True,
            include_non_read_only=True,
            include_default_values=True,
            include_non_default_values=True,
            include_inside_limits=True,
            include_outside_limits=True,
        )

        result = build_export_filename("ArduPlane", filters)

        assert result == "ArduPlane.param"
