"""
Modal preview and upload window for parameter files outside an AMC vehicle project.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import sys
import tempfile
import tkinter as tk
from argparse import ArgumentParser, Namespace
from pathlib import Path
from sys import platform as sys_platform
from tkinter import ttk
from typing import TYPE_CHECKING, Protocol

# Keep the direct-execution bootstrap before package imports.
# pylint: disable=wrong-import-position
# Support direct execution from the repository root as well as package imports.
if __package__ in {None, ""}:  # pragma: no cover
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ardupilot_methodic_configurator import _
from ardupilot_methodic_configurator.backend_filesystem import LocalFilesystem
from ardupilot_methodic_configurator.backend_flightcontroller import FlightController
from ardupilot_methodic_configurator.common_arguments import add_common_arguments
from ardupilot_methodic_configurator.data_model_ardupilot_parameter import ArduPilotParameter
from ardupilot_methodic_configurator.data_model_parameter_compare_and_upload import (
    confirm_external_upload_selection,
    refresh_external_fc_values,
)
from ardupilot_methodic_configurator.data_model_parameter_editor import ParameterEditor
from ardupilot_methodic_configurator.frontend_tkinter_base_window import BaseWindow, show_error_popup
from ardupilot_methodic_configurator.frontend_tkinter_parameter_application import (
    ParameterApplicationHost,
    initialize_standalone_parameter_editor,
    run_standalone_parameter_application,
)
from ardupilot_methodic_configurator.frontend_tkinter_parameter_editor_table import (
    ParameterEditorTable,
    ParameterEditorTableHost,
    ParameterTableOptions,
)
from ardupilot_methodic_configurator.frontend_tkinter_show import show_tooltip

# pylint: enable=wrong-import-position

if TYPE_CHECKING:
    from ardupilot_methodic_configurator.frontend_tkinter_parameter_editor import ParameterEditorUiServices


class ParameterUploadHost(ParameterEditorTableHost, Protocol):
    """The UI operations required by the external parameter upload dialog."""

    @property
    def root(self) -> tk.Tk | tk.Toplevel: ...

    parameter_editor: ParameterEditor
    ui: "ParameterEditorUiServices"

    def upload_external_params(self, selected_params: dict) -> bool: ...

    def reset_all_parameters_to_default(self) -> bool: ...


class ParameterFileUploadWindow(BaseWindow):
    """Display an external parameter file and optionally upload its values to the FC."""

    def __init__(
        self,
        parent: ParameterUploadHost,
        filepath: str,
        parameters: dict[str, ArduPilotParameter],
    ) -> None:
        super().__init__(parent.root)
        self.parent = parent
        self.filepath = filepath
        self.parameters = parameters
        self.show_only_changed = tk.BooleanVar(value=False)
        self.table_options = ParameterTableOptions(
            show_parameter_actions=False,
            show_upload_column=True,
            show_manual_override_column=True,
            show_change_reason_column=False,
            values_editable=False,
            skip_when_no_differences=False,
            manual_override_for_all_parameters=True,
            render_batch_size=200,
            render_complete_callback=self._enable_upload_button,
        )

        self.root.title(_("Compare and upload parameter file - {filename}").format(filename=Path(filepath).name))
        self.root.geometry(self.calculate_scaled_geometry(500, 620))
        self.root.protocol("WM_DELETE_WINDOW", self.close)

        file_label = ttk.Label(self.main_frame, text=filepath)
        file_label.pack(side=tk.TOP, fill="x", padx=8, pady=(8, 4))
        show_tooltip(
            file_label,
            _("Parameter file selected for comparison and optional upload. This file is not managed by AMC."),
        )

        self.table = ParameterEditorTable(
            self.main_frame,
            parent.parameter_editor,
            parent,
            options=self.table_options,
            parameters=self.parameters,
        )
        self.table.pack(side=tk.TOP, fill="both", expand=True, padx=4, pady=4)

        controls = ttk.Frame(self.main_frame)
        controls.pack(side=tk.BOTTOM, fill="x", padx=8, pady=8)

        changed_checkbox = ttk.Checkbutton(
            controls,
            text=_("Show only changed parameters"),
            variable=self.show_only_changed,
            command=self.repopulate_table,
        )
        changed_checkbox.pack(side=tk.TOP, anchor=tk.W, pady=(0, 8))

        buttons = ttk.Frame(controls)
        buttons.pack(side=tk.TOP, fill="x")

        close_button = ttk.Button(buttons, text=_("Close"), command=self.close)
        close_button.pack(side=tk.RIGHT, padx=(8, 0))
        reset_button = ttk.Button(
            buttons,
            text=_("Reset all FC parameters to defaults"),
            command=self.reset_all_parameters_to_default,
        )
        reset_button.pack(side=tk.LEFT, padx=(0, 8))
        self.upload_button = ttk.Button(
            buttons,
            text=_("Upload selected params to the FC"),
            command=self.upload_parameters,
            state="disabled",
        )
        self.upload_button.pack(side=tk.LEFT)
        show_tooltip(self.upload_button, _("Upload the selected parameters to the flight controller"))

        # Dialog placement and deferred rendering follow the export dialog pattern.
        # pylint: disable=duplicate-code
        parent_is_visible = parent.root.winfo_viewable()
        if parent_is_visible:
            self.root.transient(parent.root)
        self.root.update_idletasks()
        if parent_is_visible:
            self.center_window(self.root, parent.root)
        else:
            self.center_window_on_screen(self.root)
        if sys_platform != "darwin":
            self.root.grab_set()

        # center_window() calls update(), which drains idle callbacks.  Start
        # batched table rendering only afterwards so the dialog is displayed
        # before later batches are rendered.
        def render_table() -> None:
            self.table.repopulate_table(show_only_differences=False, gui_complexity=parent.gui_complexity)

        self.root.after_idle(render_table)
        # pylint: enable=duplicate-code

    def _enable_upload_button(self) -> None:
        """Allow uploading only after every row has an Upload selection state."""
        self.upload_button.configure(state="normal")

    def repopulate_table(self) -> None:
        """Refresh the table using the current changed-only filter."""
        self.upload_button.configure(state="disabled")
        self.table.repopulate_table(self.show_only_changed.get(), self.parent.gui_complexity)

    def upload_parameters(self) -> None:
        """Upload the checked parameters from the external file and close after success."""
        omitted_manual_edits = self.table.get_unselected_manually_edited_different_parameter_names()
        if not confirm_external_upload_selection(omitted_manual_edits, self.parent.ui.show_warning):
            return
        selected_params = self.table.get_upload_selected_params(self.parent.gui_complexity)
        if not self.parent.parameter_editor.ensure_upload_preconditions(dict(selected_params), self.parent.ui.show_warning):
            return
        if self.parent.upload_external_params(selected_params):
            refresh_external_fc_values(self.parameters, self.parent.parameter_editor.fc_parameters)
            self.close()

    def reset_all_parameters_to_default(self) -> None:
        """Confirm and reset all flight-controller parameters to their factory defaults."""
        if (
            self.parent.ui.ask_yesno(
                _("Reset all FC parameters"),
                _("Are you sure you want to reset all FC parameters to their default values?"),
            )
            and self.parent.reset_all_parameters_to_default()
        ):
            # The reset clears the FC parameter cache.  Closing the modal
            # prevents stale comparisons and forces a fresh external-file
            # preview after reconnecting.
            self.close()

    def close(self) -> None:
        """Close the modal window and refresh the underlying parameter table."""
        if sys_platform != "darwin":
            self.root.grab_release()
        self.root.destroy()
        self.parent.repopulate_parameter_table()


class StandaloneUploadHost(ParameterApplicationHost):
    """Add upload operations to the shared parameter dialog host."""

    def upload_external_params(self, selected_params: dict) -> bool:
        """Upload selected parameters using the editor's progress UI."""
        try:
            return self.ui.upload_params_with_progress(
                self.root,
                self.parameter_editor.upload_external_params_workflow,
                selected_params,
            )
        except Exception as exc:  # pylint: disable=broad-exception-caught
            self.ui.show_error(_("Upload Error"), f"{_('Failed to upload parameters:')} {exc}")
            return False

    def reset_all_parameters_to_default(self) -> bool:
        """Reset the FC with the same progress UI used by AMC."""
        return self.ui.reset_all_parameters_to_default_with_progress(
            self.root, self.parameter_editor.reset_all_parameters_to_default
        )


def create_argument_parser() -> ArgumentParser:  # pragma: no cover
    """Create the argument parser for the standalone comparison/upload program."""
    parser = ArgumentParser(description=_("Compare an ArduPilot parameter file with a flight controller and upload values."))
    parser = FlightController.add_argparse_arguments(parser)
    parser = LocalFilesystem.add_argparse_arguments(parser)
    return add_common_arguments(parser)


def argument_parser() -> Namespace:  # pragma: no cover
    """Parse arguments for running the parameter editor and upload preview standalone."""
    return create_argument_parser().parse_args()


def main() -> None:  # pragma: no cover
    """Open the external parameter-file comparison and upload window standalone."""
    args = argument_parser()
    selected_filepath: str | None = None
    with tempfile.TemporaryDirectory(prefix="amc-parameter-compare-") as scratch_directory:

        def initialize_editor(
            root: tk.Tk,
            flight_controller: FlightController,
            ui: "ParameterEditorUiServices",
        ) -> ParameterEditor | None:
            nonlocal selected_filepath
            selected_filepath = ui.askopenfilename(
                parent=root,
                title=_("Select an ArduPilot parameter file"),
                filetypes=[
                    (_("ArduPilot parameter files"), "*.parm *.param"),
                    (_("All files"), "*.*"),
                ],
            )
            if not selected_filepath:
                return None
            # Keep downloaded FC snapshots away from the user-selected file, which may
            # itself be vehicle_dir/complete.param. The directory must survive until
            # the standalone window closes because upload verification downloads again.
            return initialize_standalone_parameter_editor(
                args,
                flight_controller,
                ui,
                parameter_download_dir=Path(scratch_directory),
            )

        def open_window(
            root: tk.Tk,
            parameter_editor: ParameterEditor,
            ui: "ParameterEditorUiServices",
        ) -> ParameterFileUploadWindow | bool:
            if selected_filepath is None:
                return False
            try:
                parameters = parameter_editor.load_external_parameter_file(selected_filepath)
            except (OSError, ValueError) as exc:
                ui.show_error(_("Parameter file error"), str(exc))
                return False
            host = StandaloneUploadHost(root, parameter_editor, ui, on_close=root.quit)
            return ParameterFileUploadWindow(host, selected_filepath, parameters)

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
