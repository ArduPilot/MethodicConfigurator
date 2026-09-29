"""
Modal window for selecting and exporting flight-controller parameters.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2026 Amilcar Lucas

SPDX-License-Identifier: GPL-3.0-or-later
"""

import sys
import tkinter as tk
from argparse import ArgumentParser, Namespace
from collections.abc import Callable
from functools import partial
from pathlib import Path
from sys import platform as sys_platform
from tkinter import ttk
from typing import TYPE_CHECKING, Protocol

# Support direct execution from the repository root as well as package imports.
if __package__ in {None, ""}:  # pragma: no cover
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# pylint: disable=wrong-import-position
from ardupilot_methodic_configurator import _
from ardupilot_methodic_configurator.backend_flightcontroller import FlightController
from ardupilot_methodic_configurator.data_model_ardupilot_parameter import ArduPilotParameter
from ardupilot_methodic_configurator.data_model_parameter_editor import ParameterEditor
from ardupilot_methodic_configurator.data_model_parameter_export import (
    ParameterExportFilters,
    build_export_filename,
    sorted_export_parameter_names,
)
from ardupilot_methodic_configurator.frontend_tkinter_base_window import BaseWindow, show_error_popup
from ardupilot_methodic_configurator.frontend_tkinter_parameter_application import (
    ParameterApplicationHost,
    initialize_standalone_parameter_editor,
    run_standalone_parameter_application,
)
from ardupilot_methodic_configurator.frontend_tkinter_parameter_application import (
    create_argument_parser as create_parameter_application_argument_parser,
)
from ardupilot_methodic_configurator.frontend_tkinter_show import Tooltip, get_monitor_bounds, show_tooltip

# pylint: enable=wrong-import-position

if TYPE_CHECKING:
    from ardupilot_methodic_configurator.frontend_tkinter_parameter_editor import ParameterEditorUiServices


class ParameterExportHost(Protocol):  # pylint: disable=too-few-public-methods
    """Parent operations required by the export dialog."""

    root: tk.Tk | tk.Toplevel
    parameter_editor: ParameterEditor
    ui: "ParameterEditorUiServices"


class _ParameterTreeTooltip(Tooltip):
    """Show parameter documentation beside the hovered Treeview cell."""

    def position_tooltip(self) -> None:
        if self.tooltip is None:
            return
        self.tooltip.update_idletasks()
        left, top, right, bottom = get_monitor_bounds(self.widget.winfo_toplevel())
        x = max(left, min(self.widget.winfo_pointerx() + 12, right - self.tooltip.winfo_reqwidth()))
        y = max(top, min(self.widget.winfo_pointery() + 12, bottom - self.tooltip.winfo_reqheight()))
        self.tooltip.geometry(f"+{x}+{y}")


class ParameterExportWindow(BaseWindow):  # pylint: disable=too-many-instance-attributes
    """Select parameter categories and export the matching FC values."""

    def __init__(  # noqa: PLR0915  # pylint: disable=too-many-statements
        self,
        parent: ParameterExportHost,
        parameters: dict[str, ArduPilotParameter],
        *,
        on_close: Callable[[], None] | None = None,
    ) -> None:
        super().__init__(parent.root)
        self.parent = parent
        self.parameters = parameters
        self._on_close = on_close
        self.root.title(_("Export parameters"))
        self.root.geometry(self.calculate_scaled_geometry(525, 500))
        self.root.protocol("WM_DELETE_WINDOW", self.close)
        parent_is_visible = parent.root.winfo_viewable()
        if parent_is_visible:
            self.root.transient(parent.root)

        self.include_calibrations = tk.BooleanVar(value=False)
        self.include_non_calibrations = tk.BooleanVar(value=True)
        self.include_read_only = tk.BooleanVar(value=False)
        self.include_non_read_only = tk.BooleanVar(value=True)
        self.include_default_values = tk.BooleanVar(value=False)
        self.include_non_default_values = tk.BooleanVar(value=True)
        self.include_inside_limits = tk.BooleanVar(value=True)
        self.include_outside_limits = tk.BooleanVar(value=True)
        self.annotate_documentation = tk.BooleanVar(value=False)
        self.parameter_count = tk.StringVar()
        self._sort_column: str | None = None
        self._sort_descending = False
        self._hovered_cell: tuple[str, str] | None = None

        content = ttk.Frame(self.main_frame)
        content.pack(fill="both", expand=True, padx=12, pady=12)
        parameter_properties_frame = ttk.LabelFrame(content, text=_("Parameter properties"))
        parameter_properties_frame.pack(fill="x", pady=(0, 6))
        show_tooltip(
            parameter_properties_frame,
            _(
                "These choices describe what a parameter is. Select one or both options in each row.\n"
                "A parameter is exported only when it matches every selected row."
            ),
            position_below=False,
        )
        self._create_filter_rows(
            parameter_properties_frame,
            (
                (
                    _("Calibration"),
                    self.include_calibrations,
                    _("Non-calibration"),
                    self.include_non_calibrations,
                    _(
                        "Include calibration parameters. These store board-dependent sensor calibration,\n"
                        "such as accelerometer, gyroscope, or compass corrections. They are specific to\n"
                        "this flight controller and must not be copied to another board."
                    ),
                    _(
                        "Include parameters that are not sensor calibration values. These settings describe\n"
                        "how ArduPilot should operate and are generally more suitable for copying to another\n"
                        "flight controller of the same vehicle and firmware type."
                    ),
                ),
                (
                    _("Read-only"),
                    self.include_read_only,
                    _("Non-read-only"),
                    self.include_non_read_only,
                    _(
                        "Include read-only parameters. ArduPilot reports these values for information,\n"
                        "status, or detected hardware, and normally does not allow them to be changed."
                    ),
                    _(
                        "Include parameters that are not read-only. These are the parameters that ArduPilot\n"
                        "normally allows you to change and use for vehicle configuration."
                    ),
                ),
            ),
        )
        parameter_values_frame = ttk.LabelFrame(content, text=_("Parameter values"))
        parameter_values_frame.pack(fill="x")
        show_tooltip(
            parameter_values_frame,
            _(
                "These choices describe the current value read from the flight controller. Select one or both\n"
                "options in each row. A parameter is exported only when it matches every selected row."
            ),
            position_below=False,
        )
        self._create_filter_rows(
            parameter_values_frame,
            (
                (
                    _("Default value"),
                    self.include_default_values,
                    _("Non-default value"),
                    self.include_non_default_values,
                    _(
                        "Include parameters whose current flight-controller value is the default supplied by\n"
                        "the ArduPilot firmware. This means no custom value has been applied."
                    ),
                    _(
                        "Include parameters whose current flight-controller value differs from the firmware\n"
                        "default. These values represent a customization or a change made during setup."
                    ),
                ),
                (
                    _("Inside or undocumented limits"),
                    self.include_inside_limits,
                    _("Outside limits"),
                    self.include_outside_limits,
                    _(
                        "Include parameters whose current value is not known to violate a documented limit.\n"
                        "Parameters with no documented minimum or maximum are included because they are not\n"
                        "known to be outside a limit. If only one bound is documented, that bound is checked."
                    ),
                    _(
                        "Include parameters whose current value is below the minimum or above the maximum\n"
                        "documented by ArduPilot. Such values may be invalid or unsafe; exporting them is\n"
                        "mainly useful for diagnosis or recovery."
                    ),
                ),
            ),
        )

        parameter_count_frame = ttk.Frame(content)
        parameter_count_frame.pack(anchor=tk.W, pady=(12, 0))
        parameter_count_label = ttk.Label(parameter_count_frame, text=_("Parameters selected for export:"))
        parameter_count_label.pack(side=tk.LEFT)
        show_tooltip(
            parameter_count_label,
            _(
                "The number of parameters that match every selected filter.\n"
                "The rows are combined with AND logic, so a parameter must\n"
                "satisfy all selected categories to be counted."
            ),
        )
        parameter_count_value = ttk.Label(parameter_count_frame, textvariable=self.parameter_count)
        parameter_count_value.pack(side=tk.LEFT, padx=(4, 0))
        show_tooltip(
            parameter_count_value,
            _("The number of parameters that will be written to the file if you press Export."),
        )

        self._create_parameter_table(content)

        buttons = ttk.Frame(content)
        buttons.pack(side=tk.BOTTOM, fill="x", pady=(16, 0))
        annotate_checkbox = ttk.Checkbutton(
            buttons,
            text=_("Annotate parameters with documentation"),
            variable=self.annotate_documentation,
        )
        annotate_checkbox.pack(side=tk.LEFT)
        show_tooltip(
            annotate_checkbox,
            _(
                "Add human-readable comments with ArduPilot documentation to the exported file.\n"
                "This makes the file easier to understand but does not change parameter values."
            ),
        )
        cancel_button = ttk.Button(buttons, text=_("Cancel"), command=self.close)
        cancel_button.pack(side=tk.RIGHT)
        show_tooltip(cancel_button, _("Close this window and discard this export selection without creating a file."))
        export_button = ttk.Button(buttons, text=_("Export"), command=self.export)
        export_button.pack(side=tk.RIGHT, padx=(0, 8))
        show_tooltip(
            export_button,
            _(
                "Choose where to save a .param file containing the selected flight-controller parameters.\n"
                "The suggested filename describes your selections."
            ),
        )

        self._update_parameter_count()
        # Window placement mirrors the compare and upload parameter dialog.
        # pylint: disable=duplicate-code
        self.root.update_idletasks()
        if parent_is_visible:
            self.center_window(self.root, parent.root)
        else:
            self.center_window_on_screen(self.root)
        if sys_platform != "darwin":
            self.root.grab_set()
        # pylint: enable=duplicate-code

    def _create_parameter_table(self, parent: ttk.Frame) -> None:
        """Create a scrollable preview whose headings stay visible while rows scroll."""
        table_frame = ttk.Frame(parent)
        table_frame.pack(fill="both", expand=True, pady=(6, 0))
        columns = ("name", "fc_value", "unit")
        self.parameter_tree = ttk.Treeview(table_frame, columns=columns, show="headings", selectmode="none")
        # Create status tags first so they take priority over the neutral stripe.
        for tag, color in (
            ("read_only", "purple1"),
            ("calibration", "yellow"),
            ("default_value", "light blue"),
            ("below_minimum", "orangered"),
            ("above_maximum", "red3"),
            ("striped", "#eeeeee"),
        ):
            self.parameter_tree.tag_configure(tag, background=color)
        self._column_labels = {
            "name": _("Parameter name"),
            "fc_value": _("FC value"),
            "unit": _("Units"),
        }
        for column, label in self._column_labels.items():
            self.parameter_tree.heading(column, text=label, command=partial(self._sort_by_column, column))
        self.parameter_tree.column("name", width=320, minwidth=150, stretch=True)
        self.parameter_tree.column("fc_value", width=140, minwidth=90, anchor=tk.E, stretch=False)
        self.parameter_tree.column("unit", width=120, minwidth=70, stretch=False)
        scrollbar = ttk.Scrollbar(table_frame, orient=tk.VERTICAL, command=self.parameter_tree.yview)
        self.parameter_tree.configure(yscrollcommand=scrollbar.set)
        self.parameter_tree.pack(side=tk.LEFT, fill="both", expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self._parameter_tooltip = _ParameterTreeTooltip(self.parameter_tree, "")
        self.parameter_tree.bind("<Enter>", self._on_table_hover)
        self.parameter_tree.bind("<Motion>", self._on_table_hover)
        self.parameter_tree.bind("<MouseWheel>", self._on_table_scroll, "+")
        self.parameter_tree.bind("<Button-4>", self._on_table_scroll, "+")
        self.parameter_tree.bind("<Button-5>", self._on_table_scroll, "+")

    def _on_table_hover(self, event: tk.Event) -> None:
        """Update the tooltip when the pointer moves to another parameter cell."""
        row = self.parameter_tree.identify_row(event.y)
        column = self.parameter_tree.identify_column(event.x)
        hovered_cell = (row, column) if row else None
        if hovered_cell == self._hovered_cell:
            return
        self._parameter_tooltip.force_hide()
        self._hovered_cell = hovered_cell
        parameter = self._selected_parameters.get(row)
        if parameter is None:
            return
        tooltip = {
            "#1": parameter.tooltip_new_value,
            "#2": parameter.tooltip_fc_value,
            "#3": parameter.tooltip_unit,
        }.get(column, "")
        if tooltip:
            self._parameter_tooltip.text = tooltip
            self._parameter_tooltip.schedule_show(event)

    def _on_table_scroll(self, _event: tk.Event) -> None:
        self._parameter_tooltip.force_hide()
        self._hovered_cell = None

    def _sort_by_column(self, column: str) -> None:
        """Sort ascending on first click and reverse on the next click."""
        self._sort_descending = not self._sort_descending if column == self._sort_column else False
        self._sort_column = column
        self._apply_sort()

    def _apply_sort(self) -> None:
        if self._sort_column is not None:
            for column, label in self._column_labels.items():
                arrow = " ▼" if self._sort_descending else " ▲"
                self.parameter_tree.heading(column, text=label + arrow if column == self._sort_column else label)

            ordered_names = sorted_export_parameter_names(self._selected_parameters, self._sort_column, self._sort_descending)
            for index, name in enumerate(ordered_names):
                self.parameter_tree.move(name, "", index)

        for index, name in enumerate(self.parameter_tree.get_children()):
            parameter = self._selected_parameters[name]
            status_tags = self._get_parameter_status_tags(parameter)
            tags = list(status_tags)
            if index % 2:
                tags.append("striped")
            self.parameter_tree.item(name, tags=tuple(tags))

    @staticmethod
    def _get_parameter_status_tags(parameter: ArduPilotParameter) -> tuple[str, ...]:
        """Return all applicable row colors in tag-priority order."""
        tags: list[str] = []
        if parameter.is_readonly:
            tags.append("read_only")
        if parameter.is_calibration:
            tags.append("calibration")
        if parameter.fc_value_equals_default_value:
            tags.append("default_value")
        if parameter.fc_value_is_below_limit():
            tags.append("below_minimum")
        if parameter.fc_value_is_above_limit() or parameter.fc_value_has_unknown_bits_set():
            tags.append("above_maximum")
        return tuple(tags)

    def _create_filter_rows(
        self,
        parent: ttk.LabelFrame,
        rows: tuple[tuple[str, tk.BooleanVar, str, tk.BooleanVar, str, str], ...],
    ) -> None:
        parent.columnconfigure(0, weight=1)
        parent.columnconfigure(1, weight=1)
        for row_index, (
            left_label,
            left_variable,
            right_label,
            right_variable,
            left_tooltip,
            right_tooltip,
        ) in enumerate(rows):
            left_checkbox = ttk.Checkbutton(
                parent, text=left_label, variable=left_variable, command=self._update_parameter_count
            )
            left_checkbox.grid(row=row_index, column=0, sticky=tk.W, pady=2)
            show_tooltip(left_checkbox, left_tooltip)
            right_checkbox = ttk.Checkbutton(
                parent, text=right_label, variable=right_variable, command=self._update_parameter_count
            )
            right_checkbox.grid(row=row_index, column=1, sticky=tk.W, pady=2)
            show_tooltip(right_checkbox, right_tooltip)

    def _get_filters(self) -> ParameterExportFilters:
        return ParameterExportFilters(
            include_calibrations=self.include_calibrations.get(),
            include_non_calibrations=self.include_non_calibrations.get(),
            include_read_only=self.include_read_only.get(),
            include_non_read_only=self.include_non_read_only.get(),
            include_default_values=self.include_default_values.get(),
            include_non_default_values=self.include_non_default_values.get(),
            include_inside_limits=self.include_inside_limits.get(),
            include_outside_limits=self.include_outside_limits.get(),
        )

    def _get_selected_parameters(self) -> dict[str, ArduPilotParameter]:
        return self.parent.parameter_editor.filter_parameters_for_export(self.parameters, self._get_filters())

    def _update_parameter_count(self) -> None:
        self._selected_parameters = self._get_selected_parameters()
        self.parameter_count.set(str(len(self._selected_parameters)))
        self._parameter_tooltip.force_hide()
        self._hovered_cell = None
        current_rows = self.parameter_tree.get_children()
        if current_rows:
            self.parameter_tree.delete(*current_rows)
        for name, parameter in self._selected_parameters.items():
            self.parameter_tree.insert("", tk.END, iid=name, values=(name, parameter.fc_value_as_string, parameter.unit))
        self._apply_sort()

    def export(self) -> None:
        """Ask for an output path and export the selected parameters."""
        filters = self._get_filters()
        filename = self.parent.ui.asksaveasfilename(
            title=_("Export parameters"),
            initialfile=build_export_filename(self.parent.parameter_editor.connected_vehicle_type, filters),
            defaultextension=".param",
            filetypes=[(_("ArduPilot parameter files"), "*.param")],
        )
        if not filename:
            return

        try:
            self.parent.parameter_editor.export_parameters(
                self._get_selected_parameters(), filename, self.annotate_documentation.get()
            )
        except (OSError, ValueError) as exc:
            self.parent.ui.show_error(_("Parameter export error"), str(exc))
            return
        self.close()

    def close(self) -> None:
        """Close the export dialog without changing project state."""
        if sys_platform != "darwin":
            self.root.grab_release()
        self.root.destroy()
        if self._on_close is not None:
            self._on_close()


def open_parameter_export_window(  # pylint: disable=too-many-arguments
    root: tk.Tk | tk.Toplevel,
    parameter_editor: ParameterEditor,
    ui: "ParameterEditorUiServices",
    parameters: dict[str, ArduPilotParameter] | None = None,
    *,
    gui_complexity: str | None = None,
    on_close: Callable[[], None] | None = None,
) -> ParameterExportWindow:
    """Create an export dialog in an application-owned Tk event loop."""
    host = ParameterApplicationHost(
        root,
        parameter_editor,
        ui,
        gui_complexity=gui_complexity,
        on_close=on_close,
    )
    export_parameters = parameters if parameters is not None else parameter_editor.get_fc_parameters_for_export()
    return ParameterExportWindow(host, export_parameters, on_close=host.repopulate_parameter_table)


def create_argument_parser() -> ArgumentParser:  # pragma: no cover
    """Create the argument parser for the standalone parameter export program."""
    return create_parameter_application_argument_parser(_("Export parameters from an ArduPilot flight controller."))


def argument_parser() -> Namespace:  # pragma: no cover
    """Parse arguments for running the parameter export dialog standalone."""
    return create_argument_parser().parse_args()


def main() -> None:  # pragma: no cover
    """Connect to a flight controller and open the standalone export dialog."""
    args = argument_parser()

    def initialize_editor(
        _root: tk.Tk,
        flight_controller: FlightController,
        ui: "ParameterEditorUiServices",
    ) -> ParameterEditor | None:
        return initialize_standalone_parameter_editor(args, flight_controller, ui)

    def open_window(
        root: tk.Tk,
        parameter_editor: ParameterEditor,
        ui: "ParameterEditorUiServices",
    ) -> ParameterExportWindow:
        return open_parameter_export_window(root, parameter_editor, ui, on_close=root.quit)

    # pylint: disable=duplicate-code
    run_standalone_parameter_application(
        args,
        initialize_editor,
        open_window,
        root_factory=tk.Tk,
        flight_controller_factory=FlightController,
        error_popup=show_error_popup,
    )
    # pylint: enable=duplicate-code


if __name__ == "__main__":  # pragma: no cover
    main()
