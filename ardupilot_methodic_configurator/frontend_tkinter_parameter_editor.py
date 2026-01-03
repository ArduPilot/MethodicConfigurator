#!/usr/bin/env python3

"""
Parameter editor GUI.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

from __future__ import annotations

import contextlib
import tkinter as tk
from argparse import ArgumentParser, Namespace

# from logging import debug as logging_debug
from logging import basicConfig as logging_basicConfig
from logging import error as logging_error
from logging import exception as logging_exception
from logging import getLevelName as logging_getLevelName
from logging import warning as logging_warning
from sys import exit as sys_exit
from tkinter import filedialog, ttk
from typing import TYPE_CHECKING, Callable, Optional, Protocol, Union, cast

# from logging import critical as logging_critical
from ardupilot_methodic_configurator import _, __version__
from ardupilot_methodic_configurator.backend_filesystem import LocalFilesystem
from ardupilot_methodic_configurator.backend_filesystem_freedesktop import FreeDesktop
from ardupilot_methodic_configurator.backend_filesystem_program_settings import ProgramSettings
from ardupilot_methodic_configurator.backend_flightcontroller import FlightController
from ardupilot_methodic_configurator.common_arguments import add_common_arguments
from ardupilot_methodic_configurator.data_model_parameter_editor import ExperimentChoice, ParameterEditor
from ardupilot_methodic_configurator.frontend_tkinter_about_popup_window import show_about_window
from ardupilot_methodic_configurator.frontend_tkinter_autoresize_combobox import AutoResizeCombobox
from ardupilot_methodic_configurator.frontend_tkinter_base_window import (
    BaseWindow,
    ask_retry_cancel_popup,
    ask_yesno_popup,
    show_error_popup,
    show_info_popup,
    show_warning_popup,
)
from ardupilot_methodic_configurator.frontend_tkinter_directory_selection import VehicleDirectorySelectionWidgets
from ardupilot_methodic_configurator.frontend_tkinter_font import get_safe_font_config
from ardupilot_methodic_configurator.frontend_tkinter_parameter_editor_documentation_frame import DocumentationFrame
from ardupilot_methodic_configurator.frontend_tkinter_parameter_editor_table import ParameterEditorTable
from ardupilot_methodic_configurator.frontend_tkinter_progress_window import ProgressWindow
from ardupilot_methodic_configurator.frontend_tkinter_rich_text import get_widget_font_family_and_size
from ardupilot_methodic_configurator.frontend_tkinter_show import show_tooltip
from ardupilot_methodic_configurator.frontend_tkinter_stage_progress import StageProgressBar
from ardupilot_methodic_configurator.frontend_tkinter_usage_popup_window import UsagePopupWindow
from ardupilot_methodic_configurator.frontend_tkinter_usage_popup_windows import (
    display_parameter_editor_usage_popup,
    only_upload_changed_parameters_usage_popup,
)
from ardupilot_methodic_configurator.plugin_factory import plugin_factory

if TYPE_CHECKING:
    from ardupilot_methodic_configurator.data_model_par_dict import ParDict

# pylint: disable=too-many-lines


class _PaneConfigurable(Protocol):  # pylint: disable=too-few-public-methods
    """Subset of PanedWindow API needed for type-safe pane configuration."""

    def paneconfigure(self, pane: tk.Widget, **kwargs: object) -> None: ...


class ParameterEditorUiServices:  # pylint: disable=too-many-instance-attributes
    """Container for UI dependencies injected into the parameter editor window."""

    def __init__(  # pylint: disable=too-many-arguments, too-many-positional-arguments
        self,
        create_progress_window: Callable[[tk.Misc, str, str, bool], ProgressWindow],
        ask_yesno: Callable[[str, str], bool],
        ask_retry_cancel: Callable[[str, str], bool],
        show_warning: Callable[[str, str], None],
        show_error: Callable[[str, str], None],
        show_info: Callable[[str, str], None],
        asksaveasfilename: Callable[..., str],
        askopenfilename: Callable[..., str],
        exit_callback: Callable[[int], None],
    ) -> None:
        self.create_progress_window = create_progress_window
        self.ask_yesno = ask_yesno
        self.ask_retry_cancel = ask_retry_cancel
        self.show_warning = show_warning
        self.show_error = show_error
        self.show_info = show_info
        self.asksaveasfilename = asksaveasfilename
        self.askopenfilename = askopenfilename
        self.sys_exit = exit_callback

    @classmethod
    def default(cls) -> ParameterEditorUiServices:
        """Create UI services backed by the real Tkinter helpers."""

        def _create_progress_window(
            parent: tk.Misc,
            title: str,
            template: str,
            only_show_when_update_called: bool = False,
        ) -> ProgressWindow:
            return ProgressWindow(parent, title, template, only_show_when_update_progress_called=only_show_when_update_called)

        return cls(
            create_progress_window=_create_progress_window,
            ask_yesno=ask_yesno_popup,
            ask_retry_cancel=ask_retry_cancel_popup,
            show_warning=show_warning_popup,
            show_error=show_error_popup,
            show_info=show_info_popup,
            asksaveasfilename=filedialog.asksaveasfilename,
            askopenfilename=filedialog.askopenfilename,
            exit_callback=sys_exit,
        )

    def upload_params_with_progress(
        self,
        parent_window: tk.Misc,
        upload_callback: Callable[..., None],
        selected_params: dict,
    ) -> None:
        """
        Handle parameter upload with progress windows.

        This method centralizes the common pattern of:
        1. Creating reset and download progress window callbacks
        2. Calling the upload workflow with all required callbacks
        3. Cleaning up progress windows in a finally block

        Args:
            parent_window: The parent window for progress dialogs
            upload_callback: The upload workflow function to call
            selected_params: Dictionary of parameters to upload

        """
        reset_progress_window: ProgressWindow | None = None
        download_progress_window: ProgressWindow | None = None

        def get_reset_progress_callback() -> Callable[[int, int], None] | None:
            """Create and return progress window callback for FC reset only when needed."""
            nonlocal reset_progress_window
            show_only_on_update = True
            reset_progress_window = self.create_progress_window(
                parent_window,
                _("Resetting Flight Controller"),
                _("Waiting for {} of {} seconds"),
                show_only_on_update,
            )
            return reset_progress_window.update_progress_bar

        def get_download_progress_callback() -> Callable[[int, int], None] | None:
            """Create and return progress window callback for parameter download only when needed."""
            nonlocal download_progress_window
            show_immediately = False
            download_progress_window = self.create_progress_window(
                parent_window,
                _("Re-downloading FC parameters"),
                _("Downloaded {} of {} parameters"),
                show_immediately,
            )
            return download_progress_window.update_progress_bar

        try:
            upload_callback(
                selected_params,
                ask_confirmation=self.ask_yesno,
                ask_retry_cancel=self.ask_retry_cancel,
                show_error=self.show_error,
                get_reset_progress_callback=get_reset_progress_callback,
                get_download_progress_callback=get_download_progress_callback,
            )
        finally:
            # Clean up progress windows if they were created
            if reset_progress_window is not None:
                reset_progress_window.destroy()
            if download_progress_window is not None:
                download_progress_window.destroy()


class ParameterEditorWindow(BaseWindow):  # pylint: disable=too-many-instance-attributes
    """
    Parameter editor and upload graphical user interface (GUI) window.

    It inherits from the BaseWindow class and displays documentation and edit widgets to
    operate on drone parameters.
    """

    def __init__(
        self,
        parameter_editor: ParameterEditor,
        ui_services: ParameterEditorUiServices | None = None,
    ) -> None:
        super().__init__()
        self.parameter_editor = parameter_editor
        self.ui = ui_services or ParameterEditorUiServices.default()

        self.file_selection_combobox: AutoResizeCombobox
        self.show_only_differences: tk.BooleanVar
        self.annotate_params_into_files: tk.BooleanVar
        self.parameter_editor_table: ParameterEditorTable
        self.skip_button: ttk.Button
        self.gui_complexity = str(ProgramSettings.get_setting("gui_complexity"))
        self.parameter_area_container: ttk.Frame
        self.current_plugin: dict | None = None
        self.current_plugin_view: object | None = None  # Plugin view instance (implements PluginView protocol)
        self.parameter_area_paned: tk.PanedWindow | None = None
        self.parameter_container: ttk.Frame
        self._tempcal_imu_progress_window: ProgressWindow | None = None
        self.file_upload_progress_window: ProgressWindow | None = None
        self._param_download_progress_window: ProgressWindow | None = None

        self.root.title(
            _("Amilcar Lucas's - ArduPilot methodic configurator ") + __version__ + _(" - Parameter file editor and uploader")
        )
        self.root.geometry("990x630")  # Set the window width and height

        # Bind the close_connection_and_quit function to the window close event
        self.root.protocol("WM_DELETE_WINDOW", self.close_connection_and_quit)

        # Note: Entry and Combobox styles are configured in BaseWindow._setup_theme_and_styling()

        self._create_conf_widgets(__version__)

        last_step_nr = self.parameter_editor.get_last_configuration_step_number()
        if last_step_nr is not None:
            phases = self.parameter_editor.get_sorted_phases_with_end_and_weight(last_step_nr)

            self.stage_progress_bar = StageProgressBar(self.main_frame, phases, last_step_nr, self.gui_complexity)
            self.stage_progress_bar.pack(side=tk.TOP, fill="x", expand=False, pady=(2, 2), padx=(4, 4))

        # Create a DocumentationFrame object for the Documentation Content
        self.documentation_frame = DocumentationFrame(self.main_frame, self.parameter_editor)
        self.documentation_frame.documentation_frame.pack(side=tk.TOP, fill="x", expand=False, pady=(2, 2), padx=(4, 4))

        self._create_parameter_area_widgets()

        # Resize window height to ensure all widgets, including the skip button, are fully visible
        # as some Linux Window managers like KDE, like to change font sizes and padding.
        # So we need to dynamically accommodate for that after placing the widgets
        self.root.update_idletasks()
        req_height = self.root.winfo_reqheight()
        self.root.geometry(f"990x{req_height}")

        # Set up startup notification for the main application window
        FreeDesktop.setup_startup_notification(self.root)  # type: ignore[arg-type]

        # trigger a table update to ask the user what to do in the case this file needs special actions
        self.root.after(10, lambda: self.on_param_file_combobox_change(None, forced=True))

        # this one should be on top of the previous one hence the longer time
        if isinstance(self.root, tk.Tk) and UsagePopupWindow.should_display("parameter_editor"):
            self.root.after(100, lambda: display_parameter_editor_usage_popup(cast("tk.Tk", self.root)))

    def run(self) -> None:
        """
        Start the GUI main event loop.

        This method should be called after instantiation to start the GUI.
        Separated from __init__ to allow for testing and more flexible initialization.
        """
        self.root.mainloop()

    def _create_conf_widgets(self, version: str) -> None:
        config_frame = ttk.Frame(self.main_frame)
        config_frame.pack(side=tk.TOP, fill="x", expand=False, pady=(4, 0))  # Pack the frame at the top of the window

        config_subframe = ttk.Frame(config_frame)
        config_subframe.pack(side=tk.LEFT, fill="x", expand=True, anchor=tk.NW)  # Pack the frame at the top of the window

        # Create a new frame inside the config_subframe for the intermediate parameter file directory selection labels
        # and directory selection button
        directory_selection_frame = VehicleDirectorySelectionWidgets(
            self,
            config_subframe,
            self.parameter_editor.get_vehicle_directory(),
            destroy_parent_on_open=False,
        )
        if self.gui_complexity != "simple":
            directory_selection_frame.container_frame.pack(side=tk.LEFT, fill="x", expand=False, padx=(4, 6))

        # Create a new frame inside the config_subframe for the intermediate parameter file selection label and combobox
        file_selection_frame = ttk.Frame(config_subframe)
        if self.gui_complexity != "simple":
            file_selection_frame.pack(side=tk.LEFT, fill="x", expand=False, padx=(6, 6))

        # Create a label for the Combobox
        file_selection_label = ttk.Label(file_selection_frame, text=_("Current intermediate parameter file:"))
        if self.gui_complexity != "simple":
            file_selection_label.pack(side=tk.TOP, anchor=tk.NW)  # Add the label to the top of the file_selection_frame

        # Create Combobox for intermediate parameter file selection
        self.file_selection_combobox = AutoResizeCombobox(
            file_selection_frame,
            self.parameter_editor.parameter_files(),
            self.parameter_editor.current_file,
            _(
                "Select the intermediate parameter file from the list of available"
                " files in the selected vehicle directory\nIt will automatically "
                "advance to the next file once the current file is uploaded to the "
                "fight controller"
            ),
            state="readonly",
            width=45,
            style="readonly.TCombobox",
        )
        self.file_selection_combobox.bind("<<ComboboxSelected>>", self.on_param_file_combobox_change)
        if self.gui_complexity != "simple":  # only display the combobox when not simple
            self.file_selection_combobox.pack(side=tk.TOP, anchor=tk.NW, pady=(4, 0))

        self.legend_frame(config_subframe)

        image_label = self.put_image_in_label(config_frame, LocalFilesystem.application_logo_filepath())
        image_label.pack(side=tk.RIGHT, anchor=tk.NE, padx=(4, 4), pady=(4, 0))
        image_label.bind("<Button-1>", lambda event: show_about_window(self.main_frame, version))  # noqa: ARG005
        show_tooltip(image_label, _("User Manual, Support Forum, Report a Bug, Licenses, Source Code"))

    def legend_frame(self, config_subframe: ttk.Frame) -> None:  # pylint: disable=too-many-locals
        font_family, font_size = get_widget_font_family_and_size(config_subframe)
        style = ttk.Style()
        style.configure("Legend.TLabelframe", font=(font_family, font_size))
        legend_frame = ttk.LabelFrame(config_subframe, text=_("Legend"), style="Legend.TLabelframe")
        legend_left = ttk.Frame(legend_frame)
        legend_left.pack(side=tk.LEFT, anchor=tk.NW)
        show_tooltip(legend_frame, _("the meaning of the text background colors"), position_below=False)

        font = (font_family, font_size - 1 if font_size > 0 else font_size + 1)
        np_label = ttk.Label(legend_left, text=_("Normal parameter"), font=font)
        show_tooltip(np_label, _("Normal parameter - reusable in similar vehicles"))
        np_label.pack(side=tk.TOP, anchor=tk.NW)
        cal_label = ttk.Label(legend_left, text=_("Calibration param"), background="yellow", font=font)
        show_tooltip(cal_label, _("Calibration parameter - not-reusable, even in similar vehicles"))
        cal_label.pack(side=tk.TOP, anchor=tk.NW)
        readonly_label = ttk.Label(legend_left, text=_("Read-only param"), background="purple1", font=font)
        show_tooltip(readonly_label, _("Read-only parameter - not writable nor changeable"))
        readonly_label.pack(side=tk.TOP, anchor=tk.NW)
        toolow_label = ttk.Label(legend_left, text=_("Below limit"), background="orangered", font=font)
        show_tooltip(toolow_label, _("Parameter value below the minimum recommended value"))
        toolow_label.pack(side=tk.TOP, anchor=tk.NW)
        legend_right = ttk.Frame(legend_frame)
        legend_right.pack(side=tk.RIGHT, anchor=tk.NE)
        default_label = ttk.Label(legend_right, text=_("Default value"), background="lightblue", font=font)
        show_tooltip(default_label, _("This is the default value of this parameter"))
        default_label.pack(side=tk.TOP, anchor=tk.NW)
        na_label = ttk.Label(legend_right, text=_("Not available"), background="orange", font=font)
        show_tooltip(na_label, _("This parameter is not available on the connected flight controller"))
        na_label.pack(side=tk.TOP, anchor=tk.NW)
        ne_label = ttk.Label(legend_right, text=_("Not editable"), font=font)
        show_tooltip(
            ne_label,
            _(
                "This value has been automatically calculated by the software using data\n"
                "from the component editor window or from the 'configuration_steps.json' file"
            ),
        )
        ne_label.configure(state="disabled")
        ne_label.pack(side=tk.TOP, anchor=tk.NW)
        toohigh_label = ttk.Label(legend_right, text=_("Above limit"), background="red3", font=font)
        show_tooltip(toohigh_label, _("Parameter value above the maximum recommended value"))
        toohigh_label.pack(side=tk.TOP, anchor=tk.NW)
        legend_frame.pack(side=tk.LEFT, fill="x", expand=False, padx=(2, 2))

    def _create_parameter_area_widgets(self) -> None:
        self.show_only_differences = tk.BooleanVar(value=False)
        self.annotate_params_into_files = tk.BooleanVar(
            value=bool(ProgramSettings.get_setting("annotate_docs_into_param_files"))
        )

        # Container allows hot-swapping between plugin and non-plugin layouts
        # without destroying the parent main_frame structure. This enables dynamic
        # UI reconfiguration when switching between parameter files with different plugin requirements.
        self.parameter_area_container = ttk.Frame(self.main_frame)
        self.parameter_area_container.pack(side="top", fill="both", expand=True)

        # Track current plugin state to enable efficient layout switching and lifecycle management
        self.current_plugin = None
        self.parameter_container = self.parameter_area_container

        # Create the scrollable parameter editor table in the container
        self.parameter_editor_table = ParameterEditorTable(self.parameter_container, self.parameter_editor, self)
        # Table will be populated by the scheduled on_param_file_combobox_change callback
        self.parameter_editor_table.pack(side="top", fill="both", expand=True)

        # Create a frame for the buttons
        buttons_frame = ttk.Frame(self.main_frame)
        buttons_frame.pack(side="bottom", fill="x", expand=False, pady=(10, 10))

        # Create a frame for the checkboxes
        checkboxes_frame = ttk.Frame(buttons_frame)
        checkboxes_frame.pack(side=tk.LEFT, padx=(8, 8))

        # Create a checkbox for toggling parameter display
        only_changed_checkbox = ttk.Checkbutton(
            checkboxes_frame,
            text=_("See only changed parameters"),
            variable=self.show_only_differences,
            command=self.on_show_only_changed_checkbox_change,
        )
        if self.gui_complexity != "simple":
            only_changed_checkbox.pack(side=tk.TOP, anchor=tk.NW)
            show_tooltip(
                only_changed_checkbox,
                _("Toggle to show only parameters that will change if/when uploaded to the flight controller"),
            )

        annotate_params_checkbox = ttk.Checkbutton(
            checkboxes_frame,
            text=_("Annotate docs into .param files"),
            state="normal" if self.parameter_editor.parameter_documentation_available() else "disabled",
            variable=self.annotate_params_into_files,
            command=lambda: ProgramSettings.set_setting(
                "annotate_docs_into_param_files", self.annotate_params_into_files.get()
            ),
        )
        if self.gui_complexity != "simple":
            annotate_params_checkbox.pack(side=tk.TOP, anchor=tk.NW)
            show_tooltip(
                annotate_params_checkbox,
                _(
                    "Annotate ArduPilot parameter documentation metadata into the intermediate parameter files\n"
                    "The files will be bigger, but all the existing parameter documentation will be included inside"
                ),
            )

        # Create upload button
        upload_selected_button = ttk.Button(
            buttons_frame,
            text=_("Upload selected params to FC,\nand advance to next param file"),
            command=self.on_upload_selected_click,
        )
        upload_selected_button.configure(state="normal" if self.parameter_editor.is_fc_connected else "disabled")
        upload_selected_button.pack(side=tk.LEFT, padx=(8, 8))  # Add padding on both sides of the upload selected button
        show_tooltip(
            upload_selected_button,
            _(
                "Upload selected parameters to the flight controller and advance to the next "
                "intermediate parameter file\nIf changes have been made to the current file it will ask if you want "
                "to save them\nIt will reset the FC if necessary, re-download all parameters and validate their value"
            )
            if self.parameter_editor.is_fc_connected
            else _("No flight controller connected, upload not available"),
        )

        # Create download last flight log button
        download_log_button = ttk.Button(
            buttons_frame,
            text=_("Download last flight log"),
            command=self.on_download_last_flight_log_click,
        )
        download_log_button.configure(
            state=(
                "normal"
                if (self.parameter_editor.is_fc_connected and self.parameter_editor.is_mavftp_supported)
                else "disabled"
            )
        )
        download_log_button.pack(side=tk.LEFT, padx=(8, 8))  # Add padding on both sides of the download log button
        show_tooltip(
            download_log_button,
            _(
                "Download the last flight log from the flight controller\n"
                "This will save the previous flight log to a file on your computer for analysis"
            )
            if (self.parameter_editor.is_fc_connected and self.parameter_editor.is_mavftp_supported)
            else _("No flight controller connected or MAVFTP not supported"),
        )

        # Create Zip file for forum button
        zip_vehicle_for_forum_button = ttk.Button(
            buttons_frame,
            text=_("Zip Vehicle for Forum Help"),
            command=self.on_zip_vehicle_for_forum_help_click,
        )
        zip_vehicle_for_forum_button.configure(state=("normal" if self.parameter_editor.parameter_files() else "disabled"))
        zip_vehicle_for_forum_button.pack(
            side=tk.LEFT, padx=(8, 8)
        )  # Add padding on both sides of the Create Zip file for forum button
        show_tooltip(
            zip_vehicle_for_forum_button,
            _("Creates a .zip file of the configuration files\nso that they can be easily shared for forum help")
            if self.parameter_editor.parameter_files()
            else _("No intermediate parameter files available"),
        )

        # Create skip button
        self.skip_button = ttk.Button(buttons_frame, text=_("Skip parameter file"), command=self.on_skip_click)
        self.skip_button.configure(
            state=(
                "normal"
                if self.gui_complexity != "simple"
                or self.parameter_editor.is_configuration_step_optional()
                or not self.parameter_editor.is_fc_connected
                else "disabled"
            )
        )
        self.skip_button.pack(side=tk.RIGHT, padx=(8, 8))  # Add right padding to the skip button
        show_tooltip(
            self.skip_button,
            _(
                "Skip to the next intermediate parameter file without uploading any changes to the flight "
                "controller\nIf changes have been made to the current file it will ask if you want to save them"
            ),
        )

    def _cleanup_plugin_views(self) -> None:
        """Clean up existing plugin views and UI elements."""
        # Call deactivation hook on current plugin before cleanup
        if self.current_plugin_view is not None and hasattr(self.current_plugin_view, "on_deactivate"):
            try:
                self.current_plugin_view.on_deactivate()  # pyright: ignore[reportAttributeAccessIssue]
            except (AttributeError, TypeError) as e:
                logging_warning(_("Error deactivating plugin: %s"), e)

        # Clean up existing plugin view
        if self.current_plugin_view is not None:
            try:
                self.current_plugin_view.destroy()  # type: ignore[attr-defined]
            except (AttributeError, tk.TclError) as e:
                logging_warning(_("Error destroying plugin view: %s"), e)
            finally:
                self.current_plugin_view = None

        # Note: parameter_editor_table doesn't need explicit destroy()
        # It will be automatically destroyed when its parent container is destroyed

        # Clean up existing paned window
        if self.parameter_area_paned is not None:
            try:
                self.parameter_area_paned.destroy()
            except (AttributeError, tk.TclError) as e:
                logging_warning(_("Error destroying paned window: %s"), e)
            finally:
                self.parameter_area_paned = None

    def _update_plugin_layout(self, plugin: Optional[dict]) -> None:  # noqa: UP045
        """
        Update the plugin layout based on the current plugin configuration.

        This method handles the complete lifecycle of plugin views:
        - Calls deactivation hook on current plugin
        - Destroys existing plugin views and UI elements
        - Creates new layout based on plugin placement
        - Instantiates new plugin view
        - Calls activation hook on new plugin
        - Recreates parameter table

        Args:
            plugin: Plugin configuration dict with 'name' and 'placement' keys, or None

        """
        # If plugin configuration hasn't changed at all, do nothing
        if self.current_plugin == plugin:
            return

        # Determine old and new placements
        old_placement = self.current_plugin.get("placement") if self.current_plugin else None
        new_placement = plugin.get("placement") if plugin else None

        # Optimization: If both old and new are None (no plugin), avoid any widget destruction
        if old_placement is None and new_placement is None:
            self.current_plugin = plugin
            return

        # If layout structure is the same, just swap the plugin content without rebuilding
        if old_placement == new_placement and old_placement is not None and plugin is not None:
            # Same layout structure, just swap plugin
            self._swap_plugin_in_place(plugin)
            return

        # Layout structure is different - need full rebuild
        self._rebuild_plugin_layout(plugin)

    def _swap_plugin_in_place(self, plugin: dict) -> None:  # pylint: disable=too-many-branches
        """
        Swap plugin content without rebuilding the entire layout.

        This is an optimization for when the layout structure (left/top) doesn't change,
        only the plugin itself changes.

        Args:
            plugin: New plugin configuration dict

        """
        # Deactivate and destroy old plugin
        if self.current_plugin_view is not None:
            if hasattr(self.current_plugin_view, "on_deactivate"):
                try:
                    self.current_plugin_view.on_deactivate()  # pyright: ignore[reportAttributeAccessIssue]
                except (AttributeError, TypeError) as e:
                    logging_warning(_("Error deactivating plugin: %s"), e)

            try:
                self.current_plugin_view.destroy()  # type: ignore[attr-defined]
            except (AttributeError, tk.TclError) as e:
                logging_warning(_("Error destroying plugin view: %s"), e)
            finally:
                self.current_plugin_view = None

        # Locate the existing plugin parent frame based on placement strategy.
        # This avoids full layout rebuild when only the plugin content needs updating.
        placement = plugin.get("placement")
        plugin_parent: ttk.Frame | None = None

        if placement == "left" and self.parameter_area_paned is not None:
            # Left placement uses a PanedWindow with plugin in the first (left) pane
            panes: tuple[str, ...] = self.parameter_area_paned.panes()  # type: ignore[no-untyped-call]
            if panes:
                # Convert Tcl pane path to widget reference
                plugin_parent = self.parameter_area_paned.nametowidget(panes[0])
        elif placement == "top":
            # Top placement uses a vertical stack with plugin frame at the top
            # Navigate the widget tree to find the plugin container
            for child in self.parameter_area_container.winfo_children():
                if isinstance(child, ttk.Frame):
                    # Located the top_container frame
                    children = child.winfo_children()
                    if children and isinstance(children[0], ttk.Frame):
                        plugin_parent = children[0]
                    break

        if plugin_parent:
            # Clear the plugin parent frame
            for widget in plugin_parent.winfo_children():
                widget.destroy()

            # Load new plugin into existing frame
            self._load_plugin(plugin_parent, plugin)

        self.current_plugin = plugin

    def _rebuild_plugin_layout(self, plugin: dict | None) -> None:
        """
        Completely rebuild the plugin layout structure.

        This is only called when the layout structure actually changes
        (e.g., from no plugin to left plugin, or from left to top).

        Args:
            plugin: New plugin configuration dict or None

        """
        # Clean up existing views
        self._cleanup_plugin_views()

        # Complete rebuild: destroy old layout and create new structure from scratch
        self.parameter_area_container.destroy()

        # Recreate container to hold the new layout configuration
        self.parameter_area_container = ttk.Frame(self.main_frame)
        self.parameter_area_container.pack(side="top", fill="both", expand=True)

        self.current_plugin = plugin

        if plugin and plugin.get("placement") == "left":
            # Left placement: Create horizontal split with plugin on left, parameters on right
            # This gives the plugin persistent visibility while working with parameters
            self.parameter_area_paned = tk.PanedWindow(self.parameter_area_container, orient=tk.HORIZONTAL)
            self.parameter_area_paned.pack(side="top", fill="both", expand=True)

            # Create left pane for plugin with minimum width to ensure visibility
            left_frame = ttk.Frame(self.parameter_area_paned)
            self.parameter_area_paned.add(left_frame, minsize=500, stretch="always")
            self._set_pane_sticky(self.parameter_area_paned, left_frame)

            # Instantiate and display the plugin in the left frame
            self._load_plugin(left_frame, plugin)

            # Create right pane for parameter table (gets remaining space)
            right_frame = ttk.Frame(self.parameter_area_paned)
            self.parameter_area_paned.add(right_frame, stretch="always")
            self._set_pane_sticky(self.parameter_area_paned, right_frame)

            self.parameter_container = right_frame
        elif plugin and plugin.get("placement") == "top":
            # Top placement: Create vertical stack with plugin above parameters
            # This gives plugin full horizontal width, useful for wide controls
            top_container = ttk.Frame(self.parameter_area_container)
            top_container.pack(side="top", fill="both", expand=True)

            # Create top frame for plugin (fixed height, expands horizontally only)
            top_plugin_frame = ttk.Frame(top_container)
            top_plugin_frame.pack(side="top", fill="both", expand=True)
            self._load_plugin(top_plugin_frame, plugin)

            # Visual separator between plugin and parameter table
            ttk.Separator(top_container, orient="horizontal").pack(side="top", fill="x", pady=2)

            # Create bottom frame for parameter table (takes remaining vertical space)
            bottom_frame = ttk.Frame(top_container)
            bottom_frame.pack(side="top", fill="both", expand=True)

            self.parameter_container = bottom_frame
        else:
            # No plugin configured: use simple single-frame layout
            # Parameter table directly fills the entire container
            self.parameter_container = self.parameter_area_container

        # Recreate the parameter editor table in the appropriate container.
        # The container varies based on plugin placement (left pane, below plugin, or full area).
        self.parameter_editor_table = ParameterEditorTable(self.parameter_container, self.parameter_editor, self)
        self.parameter_editor_table.pack(side="top", fill="both", expand=True)

    @staticmethod
    def _set_pane_sticky(paned_window: tk.PanedWindow, pane: tk.Widget) -> None:
        """Type-safe helper to configure pane stickiness on paned windows."""
        pane_interface = cast("_PaneConfigurable", paned_window)
        pane_interface.paneconfigure(pane, sticky="nsew")

    def _load_plugin(self, parent_frame: ttk.Frame, plugin: dict) -> None:
        """
        Load a plugin into the given frame using the plugin factory.

        This method uses dependency injection to avoid circular imports.
        Plugins are registered with the factory and instantiated dynamically.

        Args:
            parent_frame: The frame to load the plugin into
            plugin: Plugin configuration dict with 'name' key

        """
        plugin_name = plugin.get("name")
        if not plugin_name:
            ttk.Label(parent_frame, text=_("Plugin configuration missing name")).pack()
            return

        # Check if plugin is registered
        if not plugin_factory.is_registered(plugin_name):
            error_msg = _("Unknown plugin: {plugin_name}").format(plugin_name=plugin_name)
            ttk.Label(parent_frame, text=error_msg, foreground="red").pack()
            logging_error(error_msg)
            return

        # Get the data model for the plugin
        model = self.parameter_editor.create_plugin_data_model(plugin_name)
        if model is None:
            error_msg = _("Plugin requires flight controller connection")
            ttk.Label(parent_frame, text=error_msg).pack()
            logging_warning(error_msg)
            return

        # Create plugin using factory with error handling
        try:
            plugin_view = plugin_factory.create(plugin_name, parent_frame, model, self)
            if plugin_view is None:
                msg = _("Failed to create plugin: {plugin_name}").format(plugin_name=plugin_name)
                logging_error(msg)
                ttk.Label(parent_frame, text=msg, foreground="red").pack()
                return

            # Pack the plugin view
            plugin_view.pack(fill="both", expand=True)  # type: ignore[attr-defined]

            # Call activation hook if available
            if hasattr(plugin_view, "on_activate"):
                try:
                    plugin_view.on_activate()  # pyright: ignore[reportAttributeAccessIssue]
                except (AttributeError, TypeError) as e:
                    logging_warning(_("Error activating plugin: %s"), e)
                    # Failed to activate - clean up and abort
                    with contextlib.suppress(AttributeError, tk.TclError):
                        plugin_view.destroy()  # type: ignore[attr-defined]
                    return

            # Only store reference after successful activation
            self.current_plugin_view = plugin_view

        except (ImportError, AttributeError, TypeError, ValueError) as e:
            msg = _("Error loading plugin {plugin_name}: {error}").format(plugin_name=plugin_name, error=str(e))
            logging_exception(msg)  # Log full traceback
            ttk.Label(parent_frame, text=msg, foreground="red").pack()

    def _do_tempcal_imu(self, selected_file: str) -> None:
        """
        Handle IMU temperature calibration using the new callback-based workflow.

        This method creates GUI-specific callback functions and injects them into
        the business logic workflow method, achieving proper separation of concerns.
        """

        def select_file(title: str, filetypes: list[str]) -> Optional[str]:  # noqa: UP045
            """GUI callback for file selection dialog."""
            return self.ui.askopenfilename(title=title, filetypes=[(_("ArduPilot binary log files"), filetypes)])

        def get_progress_callback() -> Callable | None:
            """Create and return progress window callback only when calibration will actually happen."""
            show_only_on_update = True
            tempcal_imu_progress_window = self.ui.create_progress_window(
                self.root,
                _("Reading IMU calibration messages"),
                _("Please wait, this can take a long time"),
                show_only_on_update,
            )
            # Store reference for cleanup
            self._tempcal_imu_progress_window = tempcal_imu_progress_window
            return tempcal_imu_progress_window.update_progress_bar_300_pct

        try:
            # Inject GUI callbacks into business logic workflow
            _success = self.parameter_editor.handle_imu_temperature_calibration_workflow(
                selected_file,
                ask_user_confirmation=self.ui.ask_yesno,
                select_file=select_file,
                show_warning=self.ui.show_warning,
                show_error=self.ui.show_error,
                get_progress_callback=get_progress_callback,
            )

        finally:
            # Clean up progress window if it was created
            if self._tempcal_imu_progress_window is not None:
                self._tempcal_imu_progress_window.destroy()
                self._tempcal_imu_progress_window = None

    def _handle_dialog_choice(self, result: list, dialog: tk.Toplevel, choice: ExperimentChoice) -> None:
        result.append(choice)
        dialog.destroy()

    def _should_copy_fc_values_to_file(self, selected_file: str) -> ExperimentChoice:
        def ask_user_choice(title: str, message: str, options: list[str]) -> ExperimentChoice:  # pylint: disable=too-many-locals
            """GUI callback for asking user choice with custom dialog."""
            # Create custom dialog with Close, Yes, No buttons
            dialog = tk.Toplevel(self.root)
            # Hide dialog initially to prevent flickering
            dialog.withdraw()
            dialog.transient(self.root)
            dialog.title(title)
            dialog.resizable(width=False, height=False)
            dialog.protocol("WM_DELETE_WINDOW", dialog.destroy)

            # Message text
            message_label = tk.Label(dialog, text=message, justify=tk.LEFT, padx=20, pady=10)
            message_label.pack(padx=10, pady=10)

            # Clickable link to tuning guide
            safe_font_config = get_safe_font_config()
            link_label = tk.Label(
                dialog,
                text=_("Click here to open the Tuning Guide relevant Section"),
                fg="blue",
                cursor="hand2",
                font=(str(safe_font_config["family"]), int(safe_font_config["size"]), "underline"),
            )
            link_label.pack(pady=(0, 10))
            link_label.bind("<Button-1>", lambda _e: self.parameter_editor.open_documentation_in_browser(selected_file))

            # Result variable
            result: list[ExperimentChoice] = []

            # Button frame
            button_frame = tk.Frame(dialog)
            button_frame.pack(pady=10)

            # Close button (default)
            close_button = tk.Button(
                button_frame,
                text=options[0],  # "Close"
                width=10,
                command=lambda: self._handle_dialog_choice(result, dialog, choice="close"),
            )
            close_button.pack(side=tk.LEFT, padx=5)

            # Yes button
            yes_button = tk.Button(
                button_frame,
                text=options[1],
                width=10,  # "Yes"
                command=lambda: self._handle_dialog_choice(result, dialog, choice=True),
            )
            yes_button.pack(side=tk.LEFT, padx=5)

            # No button
            no_button = tk.Button(
                button_frame,
                text=options[2],
                width=10,  # "No"
                command=lambda: self._handle_dialog_choice(result, dialog, choice=False),
            )
            no_button.pack(side=tk.LEFT, padx=5)

            dialog.bind("<Return>", lambda _event: self._handle_dialog_choice(result, dialog, choice="close"))

            # Center the dialog on the parent window
            dialog.deiconify()
            dialog.update_idletasks()
            dialog_width = dialog.winfo_width()
            dialog_height = dialog.winfo_height()
            parent_x = self.root.winfo_rootx()
            parent_y = self.root.winfo_rooty()
            parent_width = self.root.winfo_width()
            parent_height = self.root.winfo_height()
            x = parent_x + (parent_width - dialog_width) // 2
            y = parent_y + (parent_height - dialog_height) // 2
            dialog.geometry(f"+{x}+{y}")

            # Show dialog at correct position and make it modal
            dialog.grab_set()

            # Set focus after dialog is shown and modal
            close_button.focus_set()  # Give the Close button focus

            # Wait until dialog is closed
            self.root.wait_window(dialog)
            return result[-1] if result else "close"

        return self.parameter_editor.handle_copy_fc_values_workflow(
            selected_file,
            ask_user_choice,
            self.ui.show_info,
        )

    def _should_upload_file_to_fc(self, selected_file: str) -> None:
        def get_progress_callback() -> Callable | None:
            """Create and return progress window callback only when upload will actually happen."""
            show_only_on_update = True
            self.file_upload_progress_window = self.ui.create_progress_window(
                self.root,
                _("Uploading file"),
                _("Uploaded {} of {} %"),
                show_only_on_update,
            )
            return self.file_upload_progress_window.update_progress_bar

        try:
            self.parameter_editor.should_upload_file_to_fc_workflow(
                selected_file,
                ask_confirmation=self.ui.ask_yesno,
                show_error=self.ui.show_error,
                show_warning=self.ui.show_warning,
                get_progress_callback=get_progress_callback,
            )
        finally:
            # Clean up progress window if it was created
            if self.file_upload_progress_window is not None:
                self.file_upload_progress_window.destroy()
                self.file_upload_progress_window = None

    def on_param_file_combobox_change(self, _event: Union[None, tk.Event], forced: bool = False) -> None:  # noqa: UP007
        if not self.file_selection_combobox["values"]:
            return
        selected_file = self.file_selection_combobox.get()
        self._update_progress_bar_from_file(selected_file)

        # Only proceed if file changed or forced
        if self.parameter_editor.current_file != selected_file or forced:
            # Write any pending changes before switching files
            self.write_changes_to_intermediate_parameter_file()

            # Handle the parameter file change workflow
            final_file, should_continue = self.parameter_editor.handle_param_file_change_workflow(
                selected_file,
                forced,
                self.gui_complexity,
                self.documentation_frame.get_auto_open_documentation_in_browser(),
                handle_imu_temp_cal=self._do_tempcal_imu,
                handle_copy_fc_values=self._should_copy_fc_values_to_file,
                handle_upload_file=self._should_upload_file_to_fc,
                ask_confirmation=self.ui.ask_yesno,
                show_error=self.ui.show_error,
                show_info=self.ui.show_info,
            )

            # If user chose to close, exit
            if not should_continue:
                self.root.quit()
                self.ui.sys_exit(0)

            # Update the combobox if file changed due to jump
            if final_file != selected_file:
                self.file_selection_combobox.set(final_file)

            # Update GUI state
            self.documentation_frame.refresh_documentation_labels()
            self.documentation_frame.update_why_why_now_tooltip()

            # Update plugin layout if needed
            plugin = self.parameter_editor.get_plugin(final_file)
            self._update_plugin_layout(plugin)

            # Repopulate parameter table with new file
            self.repopulate_parameter_table()
            self._update_skip_button_state()

    def _update_progress_bar_from_file(self, selected_file: str) -> None:
        if self.parameter_editor.configuration_phases():
            try:
                step_nr = int(selected_file[:2])
                self.stage_progress_bar.update_progress(step_nr)
            except ValueError as _e:
                msg = _("Failed to update progress bar, {selected_file} does not start with two digits like it should: {_e}")
                logging_error(msg.format(**locals()))

    def download_flight_controller_parameters(self, redownload: bool = False) -> None:
        operation_string = _("Re-downloading FC parameters") if redownload else _("Downloading FC parameters")

        def get_progress_callback() -> Callable | None:
            """Create and return progress window callback for parameter download."""
            show_when_downloading = False
            param_download_progress_window = self.ui.create_progress_window(
                self.root,
                operation_string,
                _("Downloaded {} of {} parameters"),
                show_when_downloading,
            )
            # Store reference for cleanup
            self._param_download_progress_window = param_download_progress_window
            return param_download_progress_window.update_progress_bar

        # Download parameters using the lazy factory callback
        self.parameter_editor.download_flight_controller_parameters(get_progress_callback)

        # Clean up progress window if it was created
        if self._param_download_progress_window is not None:
            # for the case that '--device test' and there is no real FC connected
            self._param_download_progress_window.destroy()
            self._param_download_progress_window = None

        if not redownload:
            self.on_param_file_combobox_change(None, forced=True)  # the initial param read will trigger a table update

    def repopulate_parameter_table(self) -> None:
        if not self.parameter_editor.current_file:
            return  # no file was yet selected, so skip it
        # Re-populate the table with the new parameters
        self.parameter_editor_table.repopulate_table(self.show_only_differences.get(), self.gui_complexity)

    def on_show_only_changed_checkbox_change(self) -> None:
        self.repopulate_parameter_table()

    def on_upload_selected_click(self) -> None:
        if isinstance(self.root, tk.Tk) and UsagePopupWindow.should_display("only_changed_get_uploaded"):
            only_upload_changed_parameters_usage_popup(self.root)
        self.write_changes_to_intermediate_parameter_file()
        selected_params: ParDict = self.parameter_editor_table.get_upload_selected_params(self.gui_complexity)
        precondition_payload: dict[str, object] = dict(selected_params)
        if not self.parameter_editor.ensure_upload_preconditions(precondition_payload, self.ui.show_warning):
            self.on_skip_click()
            return

        self.upload_selected_params(selected_params)
        # Delete the parameter table and create a new one with the next file if available
        self.on_skip_click()

    # This function can recurse multiple times if there is an upload error
    def upload_selected_params(self, selected_params: dict) -> None:
        self.ui.upload_params_with_progress(
            self.root,
            self.parameter_editor.upload_selected_params_workflow,
            selected_params,
        )

    def on_download_last_flight_log_click(self) -> None:
        """Handle the download last flight log button click."""
        # Create a progress window for the download
        show_when_updating = False
        progress_window = self.ui.create_progress_window(
            self.root,
            _("Downloading Flight Log"),
            _("Downloaded {}% from {}%"),
            show_when_updating,
        )

        def ask_saveas_filename() -> str:
            return self.ui.asksaveasfilename(
                title=_("Save flight log as"),
                defaultextension=".bin",
                filetypes=[
                    (_("Binary log files"), "*.bin"),
                    (_("All files"), "*.*"),
                ],
            )

        self.parameter_editor.download_last_flight_log_workflow(
            ask_saveas_filename=ask_saveas_filename,
            show_error=self.ui.show_error,
            show_info=self.ui.show_info,
            progress_callback=progress_window.update_progress_bar,
        )
        progress_window.destroy()

    def on_zip_vehicle_for_forum_help_click(self) -> None:
        """Handle the zip vehicle for forum help button click."""
        self.parameter_editor.create_forum_help_zip_workflow(
            show_error=self.ui.show_error,
            show_info=self.ui.show_info,
        )

    def _update_skip_button_state(self) -> None:
        """Update the skip button state based on whether the current configuration step is optional."""
        if hasattr(self, "skip_button"):
            skip_button_state = (
                "normal"
                if self.gui_complexity != "simple"
                or self.parameter_editor.is_configuration_step_optional()
                or not self.parameter_editor.is_fc_connected
                else "disabled"
            )
            self.skip_button.configure(state=skip_button_state)

    def on_skip_click(self, _event: Union[None, tk.Event] = None) -> None:  # noqa: UP007
        self.write_changes_to_intermediate_parameter_file()

        # Use ParameterEditor to get the next non-optional file
        next_file = self.parameter_editor.get_next_non_optional_file()

        if next_file is None:
            # No more files to process, write summary and close
            self.parameter_editor.write_summary_files_workflow(
                show_info=self.ui.show_info,
                ask_confirmation=self.ui.ask_yesno,
            )
            # Close the application and the connection
            self.close_connection_and_quit()
            return

        # Update the Combobox selection to the next file
        self.file_selection_combobox.set(next_file)
        # Trigger the combobox change event to update the table
        self.on_param_file_combobox_change(None)

    def write_changes_to_intermediate_parameter_file(self) -> None:
        self.parameter_editor.handle_write_changes_workflow(
            self.annotate_params_into_files.get(),
            self.ui.ask_yesno,
        )

    def close_connection_and_quit(self) -> None:
        focused_widget = self.parameter_editor_table.view_port.focus_get()
        if focused_widget is not None:
            focused_widget.event_generate("<FocusOut>", when="now")  # trigger a sync between GUI and data-model values
        self.write_changes_to_intermediate_parameter_file()
        self.root.quit()  # Then stop the Tkinter event loop

    @staticmethod
    def add_argparse_arguments(parser: ArgumentParser) -> ArgumentParser:
        return parser


def argument_parser() -> Namespace:
    """
    Parses command-line arguments for the script.

    This function sets up an argument parser to handle the command-line arguments for the script.

    Returns:
    argparse.Namespace: An object containing the parsed arguments.

    """
    parser = ArgumentParser(
        description=_(
            "A GUI for editing ArduPilot param files. "
            "Not to be used directly, but through the main ArduPilot methodic configurator script."
        )
    )
    parser = FlightController.add_argparse_arguments(parser)
    parser = LocalFilesystem.add_argparse_arguments(parser)
    parser = ParameterEditorWindow.add_argparse_arguments(parser)
    return add_common_arguments(parser).parse_args()


if __name__ == "__main__":
    args = argument_parser()

    logging_basicConfig(level=logging_getLevelName(args.loglevel), format="%(asctime)s - %(levelname)s - %(message)s")

    fc = FlightController(reboot_time=args.reboot_time, baudrate=args.baudrate)
    filesystem = LocalFilesystem(
        args.vehicle_dir, args.vehicle_type, "", args.allow_editing_template_files, args.save_component_to_system_templates
    )
    window = ParameterEditorWindow(ParameterEditor("04_board_orientation.param", fc, filesystem))
    window.run()
