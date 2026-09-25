"""
Modal window for selecting and exporting flight-controller parameters.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2026 Amilcar Lucas

SPDX-License-Identifier: GPL-3.0-or-later
"""

import tkinter as tk
from argparse import ArgumentParser, Namespace
from logging import basicConfig as logging_basicConfig
from logging import getLevelName as logging_getLevelName
from sys import platform as sys_platform
from tkinter import filedialog, ttk
from types import SimpleNamespace
from typing import TYPE_CHECKING, cast

from ardupilot_methodic_configurator import _
from ardupilot_methodic_configurator.backend_filesystem import LocalFilesystem
from ardupilot_methodic_configurator.backend_flightcontroller import FlightController
from ardupilot_methodic_configurator.common_arguments import add_common_arguments
from ardupilot_methodic_configurator.data_model_ardupilot_parameter import ArduPilotParameter
from ardupilot_methodic_configurator.data_model_parameter_editor import ParameterEditor, ParameterExportFilters
from ardupilot_methodic_configurator.frontend_tkinter_base_window import BaseWindow, show_error_popup
from ardupilot_methodic_configurator.frontend_tkinter_show import show_tooltip

if TYPE_CHECKING:
    from ardupilot_methodic_configurator.frontend_tkinter_parameter_editor import ParameterEditorWindow


def build_export_filename(vehicle_name: str, filters: ParameterExportFilters) -> str:
    """Build a descriptive parameter export filename from the selected filter options."""

    def selected_option(first_selected: bool, second_selected: bool, first_name: str, second_name: str) -> str:
        if first_selected and not second_selected:
            return first_name
        if second_selected and not first_selected:
            return second_name
        return ""

    filter_names = (
        selected_option(
            filters.include_calibrations,
            filters.include_non_calibrations,
            "calibrations",
            "non-calibrations",
        ),
        selected_option(filters.include_read_only, filters.include_non_read_only, "read-only", "non-read-only"),
        selected_option(
            filters.include_default_values,
            filters.include_non_default_values,
            "default-values",
            "non-default-values",
        ),
        selected_option(
            filters.include_inside_limits,
            filters.include_outside_limits,
            "inside-limits",
            "outside-limits",
        ),
    )
    filename_parts = [vehicle_name, *(name for name in filter_names if name)]
    return "_".join(filename_parts) + ".param"


class ParameterExportWindow(BaseWindow):  # pylint: disable=too-many-instance-attributes
    """Select parameter categories and export the matching FC values."""

    def __init__(self, parent: "ParameterEditorWindow", parameters: dict[str, ArduPilotParameter]) -> None:  # noqa: PLR0915  # pylint: disable=too-many-statements
        super().__init__(parent.root)
        self.parent = parent
        self.parameters = parameters
        self.root.title(_("Export parameters"))
        self.root.geometry(self.calculate_scaled_geometry(530, 234))
        self.root.protocol("WM_DELETE_WINDOW", self.close)
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
                    _("Inside limits"),
                    self.include_inside_limits,
                    _("Outside limits"),
                    self.include_outside_limits,
                    _(
                        "Include parameters whose current value is between the minimum and maximum documented\n"
                        "by ArduPilot. These values are within the normal range for that parameter."
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
                "The number of parameters that match every selected filter. The rows are combined with AND\n"
                "logic, so a parameter must satisfy all selected categories to be counted."
            ),
        )
        parameter_count_value = ttk.Label(parameter_count_frame, textvariable=self.parameter_count)
        parameter_count_value.pack(side=tk.LEFT, padx=(4, 0))
        show_tooltip(
            parameter_count_value,
            _("The number of parameters that will be written to the file if you press Export."),
        )

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
        self.root.update_idletasks()
        self.center_window(self.root, parent.root)
        if sys_platform != "darwin":
            self.root.grab_set()

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
        self.parameter_count.set(str(len(self._get_selected_parameters())))

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
                self.parent.parameter_editor.filter_parameters_for_export(self.parameters, filters),
                filename,
                self.annotate_documentation.get(),
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


def argument_parser() -> Namespace:  # pragma: no cover
    """Parse arguments for running the parameter export dialog standalone."""
    parser = ArgumentParser(description=_("Export parameters from an ArduPilot flight controller."))
    parser = FlightController.add_argparse_arguments(parser)
    parser = LocalFilesystem.add_argparse_arguments(parser)
    return add_common_arguments(parser).parse_args()


def main() -> None:  # pragma: no cover
    """Connect to a flight controller and open the standalone export dialog."""
    args = argument_parser()
    logging_basicConfig(level=logging_getLevelName(args.loglevel), format="%(asctime)s - %(levelname)s - %(message)s")

    # The standalone entry point intentionally shares this bootstrap with the file browser.
    # pylint: disable=duplicate-code
    flight_controller = FlightController(reboot_time=args.reboot_time, baudrate=args.baudrate)
    filesystem = LocalFilesystem(
        args.vehicle_dir,
        args.vehicle_type,
        "",
        args.allow_editing_template_files,
        args.save_component_to_system_templates,
    )
    parameter_editor = ParameterEditor("", flight_controller, filesystem)
    connection_error = flight_controller.connect(args.device)
    if connection_error:
        show_error_popup(_("Flight-controller connection error"), connection_error)
        return
    # pylint: enable=duplicate-code

    try:
        _downloaded_parameters, param_default_values = parameter_editor.download_flight_controller_parameters(
            persist_project_state=False
        )
        filesystem.param_default_dict.update(param_default_values)
        parameters = parameter_editor.get_fc_parameters_for_export()

        ui = SimpleNamespace(asksaveasfilename=filedialog.asksaveasfilename, show_error=show_error_popup)
        host = BaseWindow()
        host.root.title(_("Parameter export standalone test"))
        host.root.geometry(host.calculate_scaled_geometry(500, 150))
        ttk.Label(host.main_frame, text=_("Connected to the flight controller")).pack(padx=20, pady=30)
        parent = SimpleNamespace(root=host.root, parameter_editor=parameter_editor, ui=ui)
        ParameterExportWindow(cast("ParameterEditorWindow", parent), parameters)
        host.root.mainloop()
    finally:
        flight_controller.disconnect()


if __name__ == "__main__":  # pragma: no cover
    main()
