#!/usr/bin/env python3

"""
Behaviour-driven tests for the parameter export dialog.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2026 Amilcar Lucas

SPDX-License-Identifier: GPL-3.0-or-later
"""

import tkinter as tk
from argparse import Namespace
from collections.abc import Iterator
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from ardupilot_methodic_configurator.backend_filesystem import LocalFilesystem
from ardupilot_methodic_configurator.data_model_ardupilot_parameter import ArduPilotParameter
from ardupilot_methodic_configurator.data_model_flightcontroller_info import FlightControllerInfo
from ardupilot_methodic_configurator.data_model_par_dict import ID_PARAMETER_NAMES, Par
from ardupilot_methodic_configurator.data_model_parameter_editor import ParameterEditor
from ardupilot_methodic_configurator.data_model_parameter_export import (
    ParameterExportFilters,
    build_export_filename,
    build_export_header,
    filter_parameters_for_export,
)
from ardupilot_methodic_configurator.frontend_tkinter_parameter_export import (
    ParameterExportWindow,
    _ParameterTreeTooltip,
    open_parameter_export_window,
)
from ardupilot_methodic_configurator.frontend_tkinter_parameter_export import main as standalone_main


@pytest.fixture(name="mav_id_parameter_snapshot")
def _mav_id_parameter_snapshot() -> dict[str, ArduPilotParameter]:
    """Provide one parameter for every known MAV ID plus an ordinary parameter."""
    parameters = {
        name: ArduPilotParameter(name, Par(float(index)), fc_value=float(index))
        for index, name in enumerate(sorted(ID_PARAMETER_NAMES), start=1)
    }
    parameters["NORMAL"] = ArduPilotParameter("NORMAL", Par(10.0), fc_value=10.0)
    return parameters


class TestMavIdExportFiltering:
    """The MAV ID filter includes every known identity parameter only when selected."""

    def test_user_includes_mav_ids_by_default(self, mav_id_parameter_snapshot: dict[str, ArduPilotParameter]) -> None:
        """
        Keep vehicle identity parameters in the default export selection.

        GIVEN: A snapshot contains all known MAV IDs and an ordinary parameter
        WHEN: The default export filters are applied
        THEN: The default is enabled and every parameter remains selected
        """
        filters = ParameterExportFilters()

        result = filter_parameters_for_export(mav_id_parameter_snapshot, filters)

        assert filters.include_mav_ids is True
        assert set(result) == set(mav_id_parameter_snapshot)
        assert result.keys() >= ID_PARAMETER_NAMES
        assert "NORMAL" in result

    def test_user_omits_every_mav_id_when_the_option_is_unchecked(
        self, mav_id_parameter_snapshot: dict[str, ArduPilotParameter]
    ) -> None:
        """
        Exclude all known MAV ID parameters while retaining ordinary parameters.

        GIVEN: A snapshot contains all known MAV IDs and an ordinary parameter
        WHEN: The user disables MAV ID inclusion
        THEN: Only the ordinary parameter remains eligible for export
        """
        filters = ParameterExportFilters(include_mav_ids=False)

        result = filter_parameters_for_export(mav_id_parameter_snapshot, filters)

        assert set(result) == {"NORMAL"}
        assert ID_PARAMETER_NAMES.isdisjoint(result)
        assert all(name not in result for name in ID_PARAMETER_NAMES)

    def test_user_includes_every_mav_id_when_the_option_is_checked(
        self, mav_id_parameter_snapshot: dict[str, ArduPilotParameter]
    ) -> None:
        """
        Include every known MAV ID parameter when explicitly selected.

        GIVEN: A snapshot contains all known MAV IDs and an ordinary parameter
        WHEN: The user enables MAV ID inclusion
        THEN: Every MAV ID and the ordinary parameter are selected
        """
        filters = ParameterExportFilters(include_mav_ids=True)

        result = filter_parameters_for_export(mav_id_parameter_snapshot, filters)

        assert set(result) == set(mav_id_parameter_snapshot)
        assert result.keys() >= ID_PARAMETER_NAMES
        assert "NORMAL" in result


class TestParameterExportFilename:
    """Test descriptive filenames generated from export filters."""

    def test_filename_explains_unbounded_parameters_are_included_in_inside_limit_selection(self) -> None:
        """
        Filename makes the no-documented-limits behavior explicit.

        GIVEN: Only the inside-limit selector is enabled
        WHEN: The export filename is built
        THEN: The filename explains that parameters without documented limits are included
        """
        filters = ParameterExportFilters(
            include_calibrations=True,
            include_non_calibrations=True,
            include_read_only=True,
            include_non_read_only=True,
            include_default_values=True,
            include_non_default_values=True,
            include_inside_limits=True,
            include_outside_limits=False,
        )

        result = build_export_filename("ArduCopter", filters)

        assert result == "ArduCopter_inside-or-undocumented-limits.param"

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

        assert result == "ArduCopter_calibrations_read-only_default-values_inside-or-undocumented-limits.param"

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


class TestParameterExportLimitClassification:  # pylint: disable=too-few-public-methods
    """Test the documented-limit classification used by export filters."""

    def test_parameters_without_documented_limits_are_included_as_not_known_outside(self) -> None:
        """
        Parameters without bounds remain eligible for the inside-limit selection.

        GIVEN: A parameter has no documented minimum or maximum
        WHEN: Only the inside-limit selection is enabled
        THEN: The parameter is included because it is not known to violate a limit
        """
        parameter = ArduPilotParameter("UNBOUNDED", Par(12.0), metadata={}, fc_value=12.0)
        filters = ParameterExportFilters(
            include_calibrations=True,
            include_non_calibrations=True,
            include_read_only=True,
            include_non_read_only=True,
            include_default_values=True,
            include_non_default_values=True,
            include_inside_limits=True,
            include_outside_limits=False,
        )

        result = filter_parameters_for_export({parameter.name: parameter}, filters)

        assert list(result) == ["UNBOUNDED"]


class TestMavIdExportPreview:  # pylint: disable=too-few-public-methods
    """The MAV ID checkbox controls which parameters appear in the live preview."""

    def test_user_can_toggle_mav_id_checkbox_and_update_preview(
        self, mav_id_parameter_snapshot: dict[str, ArduPilotParameter]
    ) -> None:
        """
        Update the preview when the MAV ID checkbox changes.

        GIVEN: The export preview contains every known MAV ID and an ordinary parameter
        WHEN: The user unchecks and then checks Include MAV IDs
        THEN: MAV IDs disappear and return in the preview, with the count updated each time
        """
        root = tk.Tk()
        root.withdraw()
        editor = MagicMock()
        editor.filter_parameters_for_export.side_effect = filter_parameters_for_export
        parent = SimpleNamespace(root=root, parameter_editor=editor, ui=MagicMock())
        window = None
        try:
            window = ParameterExportWindow(parent, mav_id_parameter_snapshot)

            def descendants(widget: tk.Misc) -> Iterator[tk.Misc]:
                for child in widget.winfo_children():
                    yield child
                    yield from descendants(child)

            checkbox = next(
                widget
                for widget in descendants(window.main_frame)
                if widget.winfo_class() == "TCheckbutton" and widget.cget("text") == "Include MAV IDs"
            )
            assert checkbox.grid_info()["row"] == 2
            assert window.include_mav_ids.get() is True
            assert set(window.parameter_tree.get_children()) == set(mav_id_parameter_snapshot)
            assert window.parameter_count.get() == str(len(mav_id_parameter_snapshot))

            checkbox.invoke()
            assert window.include_mav_ids.get() is False
            assert window.parameter_tree.get_children() == ("NORMAL",)
            assert window.parameter_count.get() == "1"
            assert ID_PARAMETER_NAMES.isdisjoint(window._selected_parameters)  # pylint: disable=protected-access

            checkbox.invoke()
            assert window.include_mav_ids.get() is True
            assert set(window.parameter_tree.get_children()) == set(mav_id_parameter_snapshot)
            assert window.parameter_count.get() == str(len(mav_id_parameter_snapshot))
        finally:
            if window is not None:
                window.close()
            root.destroy()


class TestParameterEditorExportSnapshotMetadata:  # pylint: disable=too-few-public-methods
    """Test pdef metadata use in FC parameter export snapshots."""

    def test_loaded_pdef_fields_classify_export_parameters(self) -> None:
        """Parameter snapshots retain calibration and read-only flags from pdef metadata."""
        filesystem = LocalFilesystem(None, "ArduPlane", "4.6.3", False, False)  # noqa: FBT003
        filesystem.doc_dict = {
            "CALIB": {"Calibration": True},
            "READONLY": {"ReadOnly": True},
        }
        flight_controller = MagicMock()
        flight_controller.fc_parameters = {"CALIB": 1.0, "READONLY": 2.0}

        parameters = ParameterEditor("", flight_controller, filesystem).get_fc_parameters_for_export()

        assert parameters["CALIB"].is_calibration is True
        assert parameters["CALIB"].is_readonly is False
        assert parameters["READONLY"].is_calibration is False
        assert parameters["READONLY"].is_readonly is True


class TestParameterExportWindow:
    """The export preview follows the selected filters and column sort order."""

    def test_preview_colors_status_rows_and_keeps_stripes_lower_priority(self) -> None:
        """Status colors take precedence over alternating neutral row backgrounds."""
        root = tk.Tk()
        root.withdraw()
        editor = MagicMock()
        editor.filter_parameters_for_export.side_effect = filter_parameters_for_export
        parent = SimpleNamespace(root=root, parameter_editor=editor, ui=MagicMock())
        parameters = {
            "READONLY": ArduPilotParameter("READONLY", Par(1.0), metadata={"ReadOnly": True}, fc_value=1.0),
            "CALIB": ArduPilotParameter("CALIB", Par(2.0), metadata={"Calibration": True}, fc_value=2.0),
            "MINIMUM": ArduPilotParameter("MINIMUM", Par(1.0), metadata={"min": 2}, fc_value=1.0),
            "MAXIMUM": ArduPilotParameter("MAXIMUM", Par(3.0), metadata={"max": 2}, fc_value=3.0),
            "DEFAULT": ArduPilotParameter("DEFAULT", Par(5.0), default_par=Par(5.0), fc_value=5.0),
            "PLAIN": ArduPilotParameter("PLAIN", Par(4.0), fc_value=4.0),
        }
        window = None
        try:
            window = ParameterExportWindow(parent, parameters)
            window.include_calibrations.set(True)
            window.include_read_only.set(True)
            window.include_default_values.set(True)
            window._update_parameter_count()  # pylint: disable=protected-access

            expected_tags = {
                "READONLY": "read_only",
                "CALIB": "calibration",
                "MINIMUM": "below_minimum",
                "MAXIMUM": "above_maximum",
                "DEFAULT": "default_value",
            }
            for name, status_tag in expected_tags.items():
                assert status_tag in window.parameter_tree.item(name, "tags")
            assert "striped" in window.parameter_tree.item("CALIB", "tags")
            assert str(window.parameter_tree.tag_configure("striped", "background")) == "#eeeeee"

            window._sort_by_column("fc_value")  # pylint: disable=protected-access
            for row_index, name in enumerate(window.parameter_tree.get_children()):
                row_tags = window.parameter_tree.item(name, "tags")
                assert ("striped" in row_tags) == (row_index % 2 == 1)
        finally:
            if window is not None:
                window.close()
            root.destroy()

    def test_preview_updates_and_sorts_numeric_fc_values(self) -> None:
        root = tk.Tk()
        root.withdraw()
        editor = MagicMock()
        editor.filter_parameters_for_export.side_effect = filter_parameters_for_export
        parent = SimpleNamespace(root=root, parameter_editor=editor, ui=MagicMock())
        parameters = {
            name: ArduPilotParameter(name, Par(value), metadata=metadata, fc_value=value)
            for name, value, metadata in (
                (
                    "ALPHA",
                    10.0,
                    {
                        "unit": "m",
                        "doc_tooltip": "Alpha documentation",
                        "doc_tooltip_sorted_numerically": "FC documentation",
                        "unit_tooltip": "Meters",
                    },
                ),
                ("BRAVO", 2.0, {"unit": "s"}),
                ("CHARLIE", 7.0, {"Calibration": True, "unit": "m"}),
            )
        }
        window = None
        try:
            window = ParameterExportWindow(parent, parameters)
            assert window.parameter_count.get() == "2"
            assert str(window.parameter_tree["show"][0]) == "headings"
            assert window.parameter_tree.item("ALPHA", "values") == ("ALPHA", "10", "m")
            assert window.parameter_tree.get_children() == ("ALPHA", "BRAVO")

            window.include_calibrations.set(True)
            window._update_parameter_count()  # pylint: disable=protected-access
            assert window.parameter_count.get() == "3"
            assert set(window.parameter_tree.get_children()) == set(parameters)

            window._sort_by_column("fc_value")  # pylint: disable=protected-access
            assert window.parameter_tree.get_children() == ("BRAVO", "CHARLIE", "ALPHA")
            assert window.parameter_tree.heading("fc_value", "text").endswith("▲")
            window._sort_by_column("fc_value")  # pylint: disable=protected-access
            assert window.parameter_tree.get_children() == ("ALPHA", "CHARLIE", "BRAVO")
            assert window.parameter_tree.heading("fc_value", "text").endswith("▼")

            with (
                patch.object(window.parameter_tree, "identify_row", return_value="ALPHA"),
                patch.object(window.parameter_tree, "identify_column", return_value="#1"),
            ):
                window._on_table_hover(SimpleNamespace(x=0, y=0))  # pylint: disable=protected-access
            assert window._parameter_tooltip.text == "Alpha documentation"  # pylint: disable=protected-access
            for column, expected in (("#2", "FC documentation"), ("#3", "Meters")):
                with (
                    patch.object(window.parameter_tree, "identify_row", return_value="ALPHA"),
                    patch.object(window.parameter_tree, "identify_column", return_value=column),
                ):
                    window._on_table_hover(SimpleNamespace(x=0, y=0))  # pylint: disable=protected-access
                assert window._parameter_tooltip.text == expected  # pylint: disable=protected-access
            window._on_table_scroll(MagicMock())  # pylint: disable=protected-access
            assert window._hovered_cell is None  # pylint: disable=protected-access

            window.include_calibrations.set(False)
            window._update_parameter_count()  # pylint: disable=protected-access
            assert window.parameter_tree.get_children() == ("ALPHA", "BRAVO")
            assert window.parameter_tree.heading("fc_value", "text").endswith("▼")
        finally:
            if window is not None:
                window.close()
            root.destroy()


@pytest.fixture(name="export_action_window")
def _export_action_window(tmp_path: Path, mav_id_parameter_snapshot) -> tuple[ParameterExportWindow, MagicMock, Path]:
    """Provide a dialog callback backed by the real parameter export model."""
    filesystem = LocalFilesystem(None, "ArduCopter", "4.6.3", False, False)  # noqa: FBT003
    controller = MagicMock()
    controller.info = SimpleNamespace(vehicle_type="ArduCopter")
    editor = ParameterEditor("", controller, filesystem)
    ui = MagicMock()
    output = tmp_path / "selected.param"
    ui.asksaveasfilename.return_value = str(output)
    window = ParameterExportWindow.__new__(ParameterExportWindow)
    window.parent = SimpleNamespace(parameter_editor=editor, ui=ui)
    window.parameters = {
        **mav_id_parameter_snapshot,
        "CALIB": ArduPilotParameter("CALIB", Par(1.0), metadata={"Calibration": True}, fc_value=1.0),
    }
    window._mav_ids_selected = True  # pylint: disable=protected-access
    window._get_filters = lambda: ParameterExportFilters(  # pylint: disable=protected-access
        include_mav_ids=window._mav_ids_selected  # pylint: disable=protected-access
    )
    window.annotate_documentation = SimpleNamespace(get=lambda: False)
    window.close = MagicMock()
    return window, ui, output


def test_user_exports_only_the_parameters_shown_by_current_filters(export_action_window) -> None:
    """
    Write the current export selection to a parameter file.

    GIVEN: A normal parameter, all MAV IDs, and a calibration parameter in the FC snapshot
    WHEN: The user exports with the default filters
    THEN: All MAV IDs and the normal parameter are saved, but the calibration parameter is omitted
    """
    window, ui, output = export_action_window

    window.export()

    contents = output.read_text()
    assert "NORMAL" in contents
    assert all(name in contents for name in ID_PARAMETER_NAMES)
    assert "CALIB" not in contents
    assert ui.asksaveasfilename.call_args.kwargs["initialfile"].startswith("ArduCopter_")
    window.close.assert_called_once_with()


def test_user_can_exclude_mav_ids_from_export_file(export_action_window) -> None:
    """
    Omit all known MAV IDs from the saved parameter file when unchecked.

    GIVEN: A flight-controller snapshot contains every known MAV ID
    WHEN: The user disables MAV ID inclusion and exports
    THEN: No MAV ID is written, while ordinary parameters are still written
    """
    window, _ui, output = export_action_window
    window._mav_ids_selected = False  # pylint: disable=protected-access

    window.export()

    contents = output.read_text()
    assert "NORMAL" in contents
    assert "CALIB" not in contents
    assert all(name not in contents for name in ID_PARAMETER_NAMES)
    window.close.assert_called_once_with()


def test_cancelling_export_does_not_write_or_close_dialog(export_action_window) -> None:
    """
    Keep the export dialog open when the user cancels file selection.

    GIVEN: The export file chooser is open
    WHEN: The user cancels it
    THEN: No file is written and the dialog remains available
    """
    window, ui, output = export_action_window
    ui.asksaveasfilename.return_value = ""

    window.export()

    assert not output.exists()
    window.close.assert_not_called()


def test_export_error_is_reported_without_closing_dialog(export_action_window) -> None:
    """
    Let the user retry after a parameter file write error.

    GIVEN: The selected destination cannot be written
    WHEN: The user presses Export
    THEN: The error is shown and the dialog stays open
    """
    window, ui, _output = export_action_window
    with patch.object(window.parent.parameter_editor, "export_parameters", side_effect=OSError("disk full")):
        window.export()

    ui.show_error.assert_called_once_with("Parameter export error", "disk full")
    window.close.assert_not_called()


def test_embedded_export_uses_fc_snapshot_and_notifies_owner_when_closed() -> None:
    """
    Open export from another Tk application without taking its event loop.

    GIVEN: An application-owned root and a connected parameter editor
    WHEN: The embedded export dialog closes
    THEN: It uses the FC snapshot and calls the owner's close callback
    """
    root = MagicMock()
    editor = MagicMock()
    ui = MagicMock()
    on_close = MagicMock()
    snapshot = {"ROLL_P": MagicMock()}
    editor.get_fc_parameters_for_export.return_value = snapshot
    with patch("ardupilot_methodic_configurator.frontend_tkinter_parameter_export.ParameterExportWindow") as dialog_type:
        opened = open_parameter_export_window(root, editor, ui, gui_complexity="normal", on_close=on_close)

    assert opened is dialog_type.return_value
    host, passed_snapshot = dialog_type.call_args.args
    assert host.root is root
    assert host.parameter_editor is editor
    assert host.ui is ui
    assert host.gui_complexity == "normal"
    assert passed_snapshot is snapshot
    dialog_type.call_args.kwargs["on_close"]()
    on_close.assert_called_once_with()


def test_standalone_export_delegates_connection_and_window_ownership_to_shared_application() -> None:
    """
    Use the shared standalone lifecycle for parameter export.

    GIVEN: The export console command is started
    WHEN: Its shared bootstrap requests a model and a dialog
    THEN: Both callbacks use the shared controller, owner, and UI service
    """
    args = Namespace(vehicle_dir="vehicle", vehicle_type="Copter")
    with (
        patch("ardupilot_methodic_configurator.frontend_tkinter_parameter_export.argument_parser", return_value=args),
        patch("ardupilot_methodic_configurator.frontend_tkinter_parameter_export.run_standalone_parameter_application") as run,
    ):
        standalone_main()

    passed_args, initialize, open_dialog = run.call_args.args
    assert passed_args is args
    root = MagicMock()
    controller = MagicMock()
    ui = MagicMock()
    editor = MagicMock()
    with (
        patch(
            "ardupilot_methodic_configurator.frontend_tkinter_parameter_export.initialize_standalone_parameter_editor",
            return_value=editor,
        ) as create_editor,
        patch("ardupilot_methodic_configurator.frontend_tkinter_parameter_export.open_parameter_export_window") as open_export,
    ):
        assert initialize(root, controller, ui) is editor
        assert open_dialog(root, editor, ui) is open_export.return_value

    create_editor.assert_called_once_with(args, controller, ui)
    assert open_export.call_args.args == (root, editor, ui)
    open_export.call_args.kwargs["on_close"]()
    root.quit.assert_called_once_with()


def test_user_can_export_with_documentation_annotation(export_action_window) -> None:
    """
    Add parameter documentation when the user requests annotated export.

    GIVEN: A valid export selection with annotation enabled
    WHEN: The user saves the parameter file
    THEN: The export model receives the firmware metadata and default values
    """
    window, _ui, output = export_action_window
    window.annotate_documentation = SimpleNamespace(get=lambda: True)
    with patch("ardupilot_methodic_configurator.data_model_parameter_export.update_parameter_documentation") as annotate:
        window.export()

    assert output.exists()
    assert annotate.call_args.args[1:3] == (str(output), "missionplanner")
    assert annotate.call_args.args[0] is window.parent.parameter_editor._local_filesystem.doc_dict  # pylint: disable=protected-access
    window.close.assert_called_once_with()


def test_caller_supplied_export_snapshot_is_used_without_redownloading() -> None:
    """
    Preserve a caller's existing FC snapshot in the embedded dialog.

    GIVEN: The editor already selected a parameter snapshot
    WHEN: It opens the export dialog
    THEN: The dialog receives that exact snapshot without creating another one
    """
    editor = MagicMock()
    selected = {"ROLL_P": MagicMock()}
    with patch("ardupilot_methodic_configurator.frontend_tkinter_parameter_export.ParameterExportWindow") as dialog_type:
        open_parameter_export_window(MagicMock(), editor, MagicMock(), selected, gui_complexity="normal")

    assert dialog_type.call_args.args[1] is selected
    editor.get_fc_parameters_for_export.assert_not_called()


def test_documentation_tooltip_stays_within_monitor_bounds() -> None:
    """
    Place row documentation where it remains visible at the screen edge.

    GIVEN: The pointer is near the bottom-right of a monitor
    WHEN: Parameter documentation appears
    THEN: The tooltip is clamped inside the monitor bounds
    """
    tooltip = _ParameterTreeTooltip.__new__(_ParameterTreeTooltip)
    tooltip.widget = MagicMock()
    tooltip.widget.winfo_pointerx.return_value = 195
    tooltip.widget.winfo_pointery.return_value = 95
    tooltip.tooltip = MagicMock()
    tooltip.tooltip.winfo_reqwidth.return_value = 80
    tooltip.tooltip.winfo_reqheight.return_value = 30
    with patch(
        "ardupilot_methodic_configurator.frontend_tkinter_parameter_export.get_monitor_bounds",
        return_value=(0, 0, 200, 100),
    ):
        tooltip.position_tooltip()

    tooltip.tooltip.geometry.assert_called_once_with("+120+70")


def test_closing_export_dialog_notifies_owner() -> None:
    """
    Return control to the application that opened the modal export dialog.

    GIVEN: An embedded export dialog with an owner callback
    WHEN: The user closes the dialog
    THEN: The Tk dialog is destroyed and its owner is notified
    """
    window = ParameterExportWindow.__new__(ParameterExportWindow)
    window.root = MagicMock()
    window._on_close = MagicMock()  # pylint: disable=protected-access

    window.close()

    window.root.destroy.assert_called_once_with()
    window._on_close.assert_called_once_with()  # pylint: disable=protected-access


def test_export_header_uses_vehicle_name_and_connected_fc_metadata() -> None:
    """Include identity fields and firmware Git hash in the export header."""
    info = FlightControllerInfo()
    info.vehicle_type = "ArduCopter"
    info.firmware_type = "CubeOrangePlus"
    info.apj_board_id = "1063"
    info.board_version = "0"
    info.autopilot = "ArduPilotMega"
    info.mav_type = "Quadrotor"
    info.flight_sw_version_and_type = "4.6.3 beta"
    info.flight_custom_version = "3fc7011a"

    info.hw_unique_id = "0x1234ABCDEF567890"
    header = build_export_header("Holybro X500", info, datetime(2026, 9, 29, 12, 34, 56, tzinfo=timezone.utc))

    assert header == [
        "# Vehicle: Holybro X500",
        "# FC board: CubeOrangePlus (board ID 1063, hardware version 0)",
        "# FC HW unique ID: 0x1234ABCDEF567890",
        "# FC type: Quadrotor (ArduCopter)",
        "# FW version: 4.6.3 beta",
        "# FW git hash: 3fc7011a",
        "# Export date/time: 2026-09-29 12:34:56+00:00",
    ]
