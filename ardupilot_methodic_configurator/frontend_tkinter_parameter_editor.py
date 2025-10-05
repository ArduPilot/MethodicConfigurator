#!/usr/bin/env python3

"""
Parameter editor GUI.

This file is part of Ardupilot methodic configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2025 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import sys
import time
import tkinter as tk
from argparse import ArgumentParser, Namespace

# from logging import debug as logging_debug
from logging import basicConfig as logging_basicConfig
from logging import error as logging_error
from logging import getLevelName as logging_getLevelName
from logging import info as logging_info
from logging import warning as logging_warning
from tkinter import filedialog, messagebox, ttk
from typing import Literal, Optional, Union

# from logging import critical as logging_critical
from webbrowser import open as webbrowser_open  # to open the blog post documentation

from ardupilot_methodic_configurator import _, __version__
from ardupilot_methodic_configurator.backend_filesystem import LocalFilesystem
from ardupilot_methodic_configurator.backend_filesystem_program_settings import ProgramSettings
from ardupilot_methodic_configurator.backend_flightcontroller import FlightController
from ardupilot_methodic_configurator.common_arguments import add_common_arguments
from ardupilot_methodic_configurator.configuration_manager import ConfigurationManager
from ardupilot_methodic_configurator.frontend_tkinter_autoresize_combobox import AutoResizeCombobox
from ardupilot_methodic_configurator.frontend_tkinter_base_window import (
    BaseWindow,
    ask_yesno_popup,
    show_error_popup,
    show_info_popup,
    show_warning_popup,
)
from ardupilot_methodic_configurator.frontend_tkinter_directory_selection import VehicleDirectorySelectionWidgets
from ardupilot_methodic_configurator.frontend_tkinter_font import create_scaled_font, get_safe_font_config
from ardupilot_methodic_configurator.frontend_tkinter_parameter_editor_documentation_frame import DocumentationFrame
from ardupilot_methodic_configurator.frontend_tkinter_parameter_editor_table import ParameterEditorTable
from ardupilot_methodic_configurator.frontend_tkinter_progress_window import ProgressWindow
from ardupilot_methodic_configurator.frontend_tkinter_rich_text import RichText, get_widget_font_family_and_size
from ardupilot_methodic_configurator.frontend_tkinter_show import show_tooltip
from ardupilot_methodic_configurator.frontend_tkinter_stage_progress import StageProgressBar
from ardupilot_methodic_configurator.frontend_tkinter_usage_popup_window import UsagePopupWindow


def show_about_window(root: ttk.Frame, _version: str) -> None:  # pylint: disable=too-many-locals
    # Create a new window for the custom "About" message
    about_window = tk.Toplevel(root)
    about_window.title(_("About"))
    about_window.geometry("650x320")

    main_frame = ttk.Frame(about_window)
    main_frame.pack(expand=True, fill=tk.BOTH)

    # Add the "About" message
    about_message = _(
        "ArduPilot Methodic Configurator Version: {_version}\n\n"
        "A clear configuration sequence for ArduPilot vehicles.\n\n"
        "Copyright © 2024-2025 Amilcar do Carmo Lucas and ArduPilot.org\n\n"
        "Licensed under the GNU General Public License v3.0"
    )
    about_label = ttk.Label(main_frame, text=about_message.format(**locals()), wraplength=450)
    about_label.grid(column=0, row=0, padx=10, pady=10, columnspan=5)  # Span across all columns

    usage_popup_frame = ttk.Frame(main_frame)
    usage_popup_frame.grid(column=0, row=1, columnspan=5, padx=10, pady=10)

    usage_popup_label = ttk.Label(usage_popup_frame, text=_("Display usage popup"))
    usage_popup_label.pack(side=tk.TOP, anchor=tk.W)

    component_editor_var = tk.BooleanVar(value=ProgramSettings.display_usage_popup("component_editor"))
    component_editor_checkbox = ttk.Checkbutton(
        usage_popup_frame,
        text=_("Component editor window"),
        variable=component_editor_var,
        command=lambda: ProgramSettings.set_display_usage_popup("component_editor", component_editor_var.get()),
    )
    component_editor_checkbox.pack(side=tk.TOP, anchor=tk.W)

    parameter_editor_var = tk.BooleanVar(value=ProgramSettings.display_usage_popup("parameter_editor"))
    parameter_editor_checkbox = ttk.Checkbutton(
        usage_popup_frame,
        text=_("Parameter file editor and uploader window"),
        variable=parameter_editor_var,
        command=lambda: ProgramSettings.set_display_usage_popup("parameter_editor", parameter_editor_var.get()),
    )
    parameter_editor_checkbox.pack(side=tk.TOP, anchor=tk.W)

    # Create buttons for each action
    user_manual_button = ttk.Button(
        main_frame,
        text=_("User Manual"),
        command=lambda: webbrowser_open("https://github.com/ArduPilot/MethodicConfigurator/blob/master/USERMANUAL.md"),
    )
    support_forum_button = ttk.Button(
        main_frame,
        text=_("Support Forum"),
        command=lambda: webbrowser_open("http://discuss.ardupilot.org/t/new-ardupilot-methodic-configurator-gui/115038/1"),
    )
    report_bug_button = ttk.Button(
        main_frame,
        text=_("Report a Bug"),
        command=lambda: webbrowser_open("https://github.com/ArduPilot/MethodicConfigurator/issues/new/choose"),
    )
    licenses_button = ttk.Button(
        main_frame,
        text=_("Licenses"),
        command=lambda: webbrowser_open("https://github.com/ArduPilot/MethodicConfigurator/blob/master/credits/CREDITS.md"),
    )
    source_button = ttk.Button(
        main_frame, text=_("Source Code"), command=lambda: webbrowser_open("https://github.com/ArduPilot/MethodicConfigurator")
    )

    # Place buttons using grid for equal spacing and better control over layout
    user_manual_button.grid(column=0, row=2, padx=10, pady=10)
    support_forum_button.grid(column=1, row=2, padx=10, pady=10)
    report_bug_button.grid(column=2, row=2, padx=10, pady=10)
    licenses_button.grid(column=3, row=2, padx=10, pady=10)
    source_button.grid(column=4, row=2, padx=10, pady=10)

    # Configure the grid to ensure equal spacing and expansion
    main_frame.columnconfigure([0, 1, 2, 3, 4], weight=1)

    # Center the about window on its parent
    BaseWindow.center_window(about_window, root.winfo_toplevel())


class ParameterEditorWindow(BaseWindow):  # pylint: disable=too-many-instance-attributes
    """
    Parameter editor and upload graphical user interface (GUI) window.

    It inherits from the BaseWindow class and displays documentation and edit widgets to
    operate on drone parameters.
    """

    def __init__(self, configuration_manager: ConfigurationManager) -> None:
        super().__init__()
        self.configuration_manager = configuration_manager
        # Maintain backward compatibility with existing code
        self.local_filesystem = configuration_manager.filesystem

        self.at_least_one_changed_parameter_written = False
        self.file_selection_combobox: AutoResizeCombobox
        self.show_only_differences: tk.BooleanVar
        self.annotate_params_into_files: tk.BooleanVar
        self.parameter_editor_table: ParameterEditorTable
        self.reset_progress_window: ProgressWindow
        self.param_download_progress_window: ProgressWindow
        self.tempcal_imu_progress_window: ProgressWindow
        self.file_upload_progress_window: ProgressWindow
        self.skip_button: ttk.Button
        self.last_time_asked_to_save: float = 0
        self.gui_complexity = str(ProgramSettings.get_setting("gui_complexity"))

        self.root.title(
            _("Amilcar Lucas's - ArduPilot methodic configurator ") + __version__ + _(" - Parameter file editor and uploader")
        )
        self.root.geometry("990x630")  # Set the window width and height

        # Bind the close_connection_and_quit function to the window close event
        self.root.protocol("WM_DELETE_WINDOW", self.close_connection_and_quit)

        style = ttk.Style()
        style.map("readonly.TCombobox", fieldbackground=[("readonly", "white")])
        style.map("readonly.TCombobox", selectbackground=[("readonly", "white")])
        style.map("readonly.TCombobox", selectforeground=[("readonly", "black")])
        style.map("default_v.TCombobox", fieldbackground=[("readonly", "light blue")])
        style.map("default_v.TCombobox", selectbackground=[("readonly", "light blue")])
        style.map("default_v.TCombobox", selectforeground=[("readonly", "black")])
        style.configure("default_v.TEntry", fieldbackground="light blue")
        style.configure("below_limit.TEntry", fieldbackground="orangered")
        style.configure("above_limit.TEntry", fieldbackground="red3")

        self.__create_conf_widgets(__version__)

        if self.local_filesystem.configuration_phases:
            # Get the first two characters of the last configuration step filename
            last_step_filename = next(reversed(self.local_filesystem.file_parameters.keys()))
            last_step_nr = int(last_step_filename[:2]) + 1 if len(last_step_filename) >= 2 else 1

            self.stage_progress_bar = StageProgressBar(
                self.main_frame, self.local_filesystem.configuration_phases, last_step_nr, self.gui_complexity
            )
            self.stage_progress_bar.pack(side=tk.TOP, fill="x", expand=False, pady=(2, 2), padx=(4, 4))

        # Create a DocumentationFrame object for the Documentation Content
        self.documentation_frame = DocumentationFrame(
            self.main_frame, self.local_filesystem, self.configuration_manager.current_file
        )
        self.documentation_frame.documentation_frame.pack(side=tk.TOP, fill="x", expand=False, pady=(2, 2), padx=(4, 4))

        self.__create_parameter_area_widgets()

        # trigger a table update to ask the user what to do in the case this file needs special actions
        self.root.after(10, lambda: self.on_param_file_combobox_change(None, forced=True))

        # this one should be on top of the previous one hence the longer time
        if UsagePopupWindow.should_display("parameter_editor"):
            self.root.after(100, self.__display_usage_popup_window(self.root))  # type: ignore[arg-type]
        self.root.mainloop()

    def __create_conf_widgets(self, version: str) -> None:
        config_frame = ttk.Frame(self.main_frame)
        config_frame.pack(side=tk.TOP, fill="x", expand=False, pady=(4, 0))  # Pack the frame at the top of the window

        config_subframe = ttk.Frame(config_frame)
        config_subframe.pack(side=tk.LEFT, fill="x", expand=True, anchor=tk.NW)  # Pack the frame at the top of the window

        # Create a new frame inside the config_subframe for the intermediate parameter file directory selection labels
        # and directory selection button
        directory_selection_frame = VehicleDirectorySelectionWidgets(
            self,
            config_subframe,
            self.local_filesystem.vehicle_dir,
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
            list(self.local_filesystem.file_parameters.keys()),
            self.configuration_manager.current_file,
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

    def __create_parameter_area_widgets(self) -> None:
        self.show_only_differences = tk.BooleanVar(value=False)
        self.annotate_params_into_files = tk.BooleanVar(
            value=bool(ProgramSettings.get_setting("annotate_docs_into_param_files"))
        )

        # Create a Scrollable parameter editor table
        self.parameter_editor_table = ParameterEditorTable(self.main_frame, self.local_filesystem, self)
        self.repopulate_parameter_table(self.configuration_manager.current_file)
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
            state="normal" if self.local_filesystem.doc_dict else "disabled",
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
            text=_("Upload selected params to FC, and advance to next param file"),
            command=self.on_upload_selected_click,
        )
        upload_selected_button.configure(state="normal" if self.configuration_manager.is_fc_connected else "disabled")
        upload_selected_button.pack(side=tk.LEFT, padx=(8, 8))  # Add padding on both sides of the upload selected button
        show_tooltip(
            upload_selected_button,
            _(
                "Upload selected parameters to the flight controller and advance to the next "
                "intermediate parameter file\nIf changes have been made to the current file it will ask if you want "
                "to save them\nIt will reset the FC if necessary, re-download all parameters and validate their value"
            )
            if self.configuration_manager.is_fc_connected
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
                if (self.configuration_manager.is_fc_connected and self.configuration_manager.is_mavftp_supported)
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
            if (self.configuration_manager.is_fc_connected and self.configuration_manager.is_mavftp_supported)
            else _("No flight controller connected or MAVFTP not supported"),
        )

        # Create skip button
        self.skip_button = ttk.Button(buttons_frame, text=_("Skip parameter file"), command=self.on_skip_click)
        self.skip_button.configure(
            state=(
                "normal"
                if self.gui_complexity != "simple"
                or self.configuration_manager.is_configuration_step_optional(self.configuration_manager.current_file)
                or not self.configuration_manager.is_fc_connected
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

    @staticmethod
    def __display_usage_popup_window(parent: tk.Tk) -> None:
        usage_popup_window = BaseWindow(parent)
        style = ttk.Style()

        instructions_text = RichText(
            usage_popup_window.main_frame,
            wrap=tk.WORD,
            height=11,
            bd=0,
            background=style.lookup("TLabel", "background"),
            font=create_scaled_font(get_safe_font_config(), 1.5),
        )
        instructions_text.insert(tk.END, _("1. Read "))
        instructions_text.insert(tk.END, _("all"), "bold")
        instructions_text.insert(tk.END, _(" the documentation on top of the parameter table\n"))
        instructions_text.insert(tk.END, _("2. Edit the parameter "))
        instructions_text.insert(tk.END, _("New Values"), "italic")
        instructions_text.insert(tk.END, _(" and"), "bold")
        instructions_text.insert(tk.END, _(" their "))
        instructions_text.insert(tk.END, _("Change Reason\n"), "italic")
        instructions_text.insert(tk.END, "   " + _("Documenting change reasons is crucial because it:") + "\n")
        instructions_text.insert(tk.END, "   " + _(" * Promotes thoughtful decisions over impulsive changes") + "\n")
        instructions_text.insert(tk.END, "   " + _(" * Provides documentation for vehicle certification requirements") + "\n")
        instructions_text.insert(
            tk.END, "   " + _(" * Enables validation or suggestions from team members or AI tools") + "\n"
        )
        instructions_text.insert(
            tk.END, "   " + _(" * Preserves your reasoning for future reference or troubleshooting") + "\n"
        )
        instructions_text.insert(tk.END, _("3. Use "))
        instructions_text.insert(tk.END, _("Del"), "italic")
        instructions_text.insert(tk.END, _(" and "))
        instructions_text.insert(tk.END, _("Add"), "italic")
        instructions_text.insert(tk.END, _(" buttons to delete and add parameters if necessary\n"))
        instructions_text.insert(tk.END, _("4. Press the "))
        instructions_text.insert(tk.END, _("Upload selected params to FC, and advance to next param file"), "italic")
        instructions_text.insert(tk.END, _(" button\n"))
        instructions_text.insert(tk.END, _("5. Repeat from the top until the program automatically closes"))
        instructions_text.config(state=tk.DISABLED)

        UsagePopupWindow.display(
            parent,
            usage_popup_window,
            _("How to use the parameter file editor and uploader window"),
            "parameter_editor",
            "690x360",
            instructions_text,
        )

    def __do_tempcal_imu(self, selected_file: str) -> None:
        """
        Handle IMU temperature calibration using the new callback-based workflow.

        This method creates GUI-specific callback functions and injects them into
        the business logic workflow method, achieving proper separation of concerns.
        """

        def select_file(title: str, filetypes: list[str]) -> Optional[str]:
            """GUI callback for file selection dialog."""
            return filedialog.askopenfilename(title=title, filetypes=[(_("ArduPilot binary log files"), filetypes)])

        # Create progress window for the calibration
        self.tempcal_imu_progress_window = ProgressWindow(
            self.root,
            _("Reading IMU calibration messages"),
            _("Please wait, this can take a long time"),
            only_show_when_update_progress_called=True,
        )

        try:
            # Inject GUI callbacks into business logic workflow
            success = self.configuration_manager.handle_imu_temperature_calibration_workflow(
                selected_file,
                ask_user_confirmation=ask_yesno_popup,
                select_file=select_file,
                show_warning=show_warning_popup,
                show_error=show_error_popup,
                progress_callback=self.tempcal_imu_progress_window.update_progress_bar_300_pct,
            )

            if success:
                # Force writing doc annotations to file
                self.parameter_editor_table.set_at_least_one_param_edited(True)

        finally:
            self.tempcal_imu_progress_window.destroy()

    def __handle_dialog_choice(self, result: list, dialog: tk.Toplevel, choice: Optional[bool]) -> None:
        result.append(choice)
        dialog.destroy()

    def __should_copy_fc_values_to_file(self, selected_file: str) -> None:  # pylint: disable=too-many-locals
        should_copy, relevant_fc_params, auto_changed_by = self.configuration_manager.should_copy_fc_values_to_file(
            selected_file
        )
        if should_copy and relevant_fc_params and auto_changed_by:
            msg = _(
                "This configuration step requires external changes by: {auto_changed_by}\n\n"
                "The external tool experiment procedure is described in the tuning guide.\n\n"
                "Choose an option:\n"
                "* CLOSE - Close the application and go perform the experiment\n"
                "* YES - Copy current FC values to {selected_file} (if you've already completed the experiment)\n"
                "* NO - Continue without copying values (if you haven't performed the experiment yet,"
                " but know what you are doing)"
            ).format(auto_changed_by=auto_changed_by, selected_file=selected_file)

            # Create custom dialog with Close, Yes, No buttons
            dialog = tk.Toplevel(self.root)
            # Hide dialog initially to prevent flickering
            dialog.withdraw()
            dialog.transient(self.root)
            dialog.title(_("Update file with values from FC?"))
            dialog.resizable(width=False, height=False)
            dialog.protocol("WM_DELETE_WINDOW", dialog.destroy)

            # Message text
            message_label = tk.Label(dialog, text=msg, justify=tk.LEFT, padx=20, pady=10)
            message_label.pack(padx=10, pady=10)

            # Result variable
            result: list[Optional[Literal[True, False]]] = [None]

            # Button frame
            button_frame = tk.Frame(dialog)
            button_frame.pack(pady=10)

            # Close button (default)
            close_button = tk.Button(
                button_frame,
                text=_("Close"),
                width=10,
                command=lambda: self.__handle_dialog_choice(result, dialog, choice=None),
            )
            close_button.pack(side=tk.LEFT, padx=5)

            # Yes button
            yes_button = tk.Button(
                button_frame, text=_("Yes"), width=10, command=lambda: self.__handle_dialog_choice(result, dialog, choice=True)
            )
            yes_button.pack(side=tk.LEFT, padx=5)

            # No button
            no_button = tk.Button(
                button_frame, text=_("No"), width=10, command=lambda: self.__handle_dialog_choice(result, dialog, choice=False)
            )
            no_button.pack(side=tk.LEFT, padx=5)

            dialog.bind("<Return>", lambda _event: self.__handle_dialog_choice(result, dialog, None))

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
            response = result[-1] if len(result) > 1 else None

            if response is True:  # Yes option
                params_copied = self.configuration_manager.copy_fc_values_to_file(selected_file, relevant_fc_params)
                if params_copied:
                    self.parameter_editor_table.set_at_least_one_param_edited(True)
            elif response is None:  # Close option
                sys.exit(0)
            # If response is False (No option), do nothing and continue

    def __should_jump_to_file(self, selected_file: str) -> str:
        jump_options = self.configuration_manager.get_file_jump_options(selected_file)
        for dest_file, msg in jump_options.items():
            if self.gui_complexity == "simple" or messagebox.askyesno(
                _("Skip some steps?"), _(msg) if msg else _("Skip to {dest_file}?").format(**locals())
            ):
                self.file_selection_combobox.set(dest_file)
                return dest_file
        return selected_file

    def __should_download_file_from_url(self, selected_file: str) -> None:
        self.configuration_manager.should_download_file_from_url_workflow(
            selected_file,
            ask_confirmation=ask_yesno_popup,
            show_error=show_error_popup,
        )

    def __should_upload_file_to_fc(self, selected_file: str) -> None:
        self.file_upload_progress_window = ProgressWindow(
            self.root, _("Uploading file"), _("Uploaded {} of {} %"), only_show_when_update_progress_called=True
        )

        try:
            self.configuration_manager.should_upload_file_to_fc_workflow(
                selected_file,
                ask_confirmation=ask_yesno_popup,
                show_error=show_error_popup,
                show_warning=show_warning_popup,
                progress_callback=self.file_upload_progress_window.update_progress_bar,
            )
        finally:
            self.file_upload_progress_window.destroy()

    def on_param_file_combobox_change(self, _event: Union[None, tk.Event], forced: bool = False) -> None:
        if not self.file_selection_combobox["values"]:
            return
        selected_file = self.file_selection_combobox.get()
        self._update_progress_bar_from_file(selected_file)
        if self.configuration_manager.current_file != selected_file or forced:
            self.write_changes_to_intermediate_parameter_file()
            self.__do_tempcal_imu(selected_file)
            # open the documentation of the next step in the browser,
            # before giving the user the option to close the SW in the __should_copy_fc_values_to_file method
            self.documentation_frame.open_documentation_in_browser(selected_file)
            self.__should_copy_fc_values_to_file(selected_file)
            selected_file = self.__should_jump_to_file(selected_file)
            self.__should_download_file_from_url(selected_file)
            self.__should_upload_file_to_fc(selected_file)

            # Update the current_file attribute to the selected file
            self.configuration_manager.current_file = selected_file
            self.at_least_one_changed_parameter_written = False
            self.documentation_frame.refresh_documentation_labels(selected_file)
            self.documentation_frame.update_why_why_now_tooltip(selected_file)
            self.repopulate_parameter_table(selected_file)
            self._update_skip_button_state()

    def _update_progress_bar_from_file(self, selected_file: str) -> None:
        if self.local_filesystem.configuration_phases:
            try:
                step_nr = int(selected_file[:2])
                self.stage_progress_bar.update_progress(step_nr)
            except ValueError as _e:
                msg = _("Failed to update progress bar, {selected_file} does not start with two digits like it should: {_e}")
                logging_error(msg.format(**locals()))

    def download_flight_controller_parameters(self, redownload: bool = False) -> None:
        operation_string = _("Re-downloading FC parameters") if redownload else _("Downloading FC parameters")
        self.param_download_progress_window = ProgressWindow(self.root, operation_string, _("Downloaded {} of {} parameters"))
        self.configuration_manager.download_flight_controller_parameters(
            self.param_download_progress_window.update_progress_bar
        )
        self.param_download_progress_window.destroy()  # for the case that '--device test' and there is no real FC connected
        if not redownload:
            self.on_param_file_combobox_change(None, forced=True)  # the initial param read will trigger a table update

    def repopulate_parameter_table(self, selected_file: Union[None, str]) -> None:
        if not selected_file:
            return  # no file was yet selected, so skip it
        # Re-populate the table with the new parameters
        self.parameter_editor_table.repopulate(
            selected_file, self.configuration_manager.fc_parameters, self.show_only_differences.get(), self.gui_complexity
        )

    def on_show_only_changed_checkbox_change(self) -> None:
        self.repopulate_parameter_table(self.configuration_manager.current_file)

    def upload_params_that_require_reset(self, selected_params: dict) -> None:
        """
        Write only the selected parameters to the flight controller that require a reset.

        After the reset, the other parameters that do not require a reset must still be written to the flight controller.
        """
        self.reset_progress_window = ProgressWindow(
            self.root,
            _("Resetting Flight Controller"),
            _("Waiting for {} of {} seconds"),
            only_show_when_update_progress_called=True,
        )

        if self.configuration_manager.upload_parameters_that_require_reset_workflow(
            selected_params,
            ask_confirmation=ask_yesno_popup,
            show_error=show_error_popup,
            progress_callback=self.reset_progress_window.update_progress_bar,
        ):
            self.at_least_one_changed_parameter_written = True

        self.reset_progress_window.destroy()  # for the case that we are doing a test and there is no real FC connected

    def on_upload_selected_click(self) -> None:
        self.write_changes_to_intermediate_parameter_file()
        selected_params = self.parameter_editor_table.get_upload_selected_params(
            self.configuration_manager.current_file, str(self.gui_complexity)
        )
        if selected_params:
            if self.configuration_manager.fc_parameters:
                self.upload_selected_params(selected_params)
            else:
                logging_warning(
                    _("No parameters were yet downloaded from the flight controller, will not upload any parameter")
                )
                messagebox.showwarning(_("Will not upload any parameter"), _("No flight controller connection"))
        else:
            logging_warning(_("No parameter was selected for upload, will not upload any parameter"))
            messagebox.showwarning(_("Will not upload any parameter"), _("No parameter was selected for upload"))
        # Delete the parameter table and create a new one with the next file if available
        self.on_skip_click()

    # This function can recurse multiple times if there is an upload error
    def upload_selected_params(self, selected_params: dict) -> None:
        logging_info(
            _("Uploading %d selected %s parameters to flight controller..."),
            len(selected_params),
            self.configuration_manager.current_file,
        )

        self.upload_params_that_require_reset(selected_params)

        # Use ConfigurationManager to handle the business logic
        nr_changed = self.configuration_manager.upload_selected_parameters_workflow(
            selected_params, show_error=show_error_popup
        )

        # Update GUI state if any parameters were changed
        if nr_changed > 0:
            self.at_least_one_changed_parameter_written = True

        if self.at_least_one_changed_parameter_written:
            # Re-download all parameters, in case one of them changed, and validate that all uploads were successful
            self.download_flight_controller_parameters(redownload=True)
            param_upload_error = self.configuration_manager.validate_uploaded_parameters(selected_params)

            if param_upload_error:
                if messagebox.askretrycancel(
                    _("Parameter upload error"),
                    _("Failed to upload the following parameters to the flight controller:\n")
                    + f"{(', ').join(param_upload_error)}",
                ):
                    self.upload_selected_params(selected_params)
            else:
                logging_info(_("All parameters uploaded to the flight controller successfully"))

            self.configuration_manager.export_fc_params_missing_or_different()

        self.local_filesystem.write_last_uploaded_filename(self.configuration_manager.current_file)

    def on_download_last_flight_log_click(self) -> None:
        """Handle the download last flight log button click."""
        # Create a progress window for the download
        progress_window = ProgressWindow(
            self.root,
            _("Downloading Flight Log"),
            _("Downloaded {}% from {}%"),
            only_show_when_update_progress_called=False,
        )

        def ask_saveas_filename() -> str:
            return filedialog.asksaveasfilename(
                title=_("Save flight log as"),
                defaultextension=".bin",
                filetypes=[
                    (_("Binary log files"), "*.bin"),
                    (_("All files"), "*.*"),
                ],
            )

        self.configuration_manager.download_last_flight_log_workflow(
            ask_saveas_filename=ask_saveas_filename,
            show_error=show_error_popup,
            show_info=show_info_popup,
            progress_callback=progress_window.update_progress_bar,
        )
        progress_window.destroy()

    def _update_skip_button_state(self) -> None:
        """Update the skip button state based on whether the current configuration step is optional."""
        if hasattr(self, "skip_button"):
            skip_button_state = (
                "normal"
                if self.gui_complexity != "simple"
                or self.configuration_manager.is_configuration_step_optional(self.configuration_manager.current_file)
                or not self.configuration_manager.is_fc_connected
                else "disabled"
            )
            self.skip_button.configure(state=skip_button_state)

    def on_skip_click(self, _event: Union[None, tk.Event] = None) -> None:
        self.write_changes_to_intermediate_parameter_file()

        # Use ConfigurationManager to get the next non-optional file
        next_file = self.configuration_manager.get_next_non_optional_file(self.configuration_manager.current_file)

        if next_file is None:
            # No more files to process, write summary and close
            self.configuration_manager.write_summary_files_workflow(
                show_info=show_info_popup,
                ask_confirmation=ask_yesno_popup,
            )
            # Close the application and the connection
            self.close_connection_and_quit()
            return

        # Update the Combobox selection to the next file
        self.file_selection_combobox.set(next_file)
        # Trigger the combobox change event to update the table
        self.on_param_file_combobox_change(None)

    def write_changes_to_intermediate_parameter_file(self) -> None:
        elapsed_since_last_ask = time.time() - self.last_time_asked_to_save
        # if annotate parameters into files is true, we always need to write to file, because
        # the parameter metadata might have changed, or not be present in the file.
        # In that situation, avoid asking multiple times to write the file, by checking the time last asked
        # But only if self.annotate_params_into_files.get()
        if self.parameter_editor_table.get_at_least_one_param_edited() or (
            self.annotate_params_into_files.get() and elapsed_since_last_ask > 1.0
        ):
            msg = _("Do you want to write the changes to the {current_filename} file?").format(
                current_filename=self.configuration_manager.current_file
            )
            if messagebox.askyesno(_("One or more parameters have been edited"), msg.format(**locals())):
                self.local_filesystem.export_to_param(
                    self.local_filesystem.file_parameters[self.configuration_manager.current_file],
                    self.configuration_manager.current_file,
                    annotate_doc=self.annotate_params_into_files.get(),
                )
        self.parameter_editor_table.set_at_least_one_param_edited(False)
        self.last_time_asked_to_save = time.time()

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
    ParameterEditorWindow(ConfigurationManager("04_board_orientation.param", fc, filesystem))
