#!/usr/bin/env python3

"""
Parameter editor GUI.

This file is part of Ardupilot methodic configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import tkinter as tk
from argparse import ArgumentParser, Namespace

# from logging import debug as logging_debug
from logging import basicConfig as logging_basicConfig
from logging import error as logging_error
from logging import getLevelName as logging_getLevelName
from logging import info as logging_info
from logging import warning as logging_warning
from tkinter import filedialog, messagebox, ttk
from typing import Union

# from logging import critical as logging_critical
from webbrowser import open as webbrowser_open  # to open the blog post documentation

from ardupilot_methodic_configurator import _, __version__
from ardupilot_methodic_configurator.annotate_params import Par
from ardupilot_methodic_configurator.backend_filesystem import LocalFilesystem, is_within_tolerance
from ardupilot_methodic_configurator.backend_filesystem_program_settings import ProgramSettings
from ardupilot_methodic_configurator.backend_flightcontroller import FlightController
from ardupilot_methodic_configurator.common_arguments import add_common_arguments_and_parse
from ardupilot_methodic_configurator.frontend_tkinter_base import (
    AutoResizeCombobox,
    BaseWindow,
    ProgressWindow,
    RichText,
    UsagePopupWindow,
    get_widget_font_family_and_size,
    show_tooltip,
)
from ardupilot_methodic_configurator.frontend_tkinter_directory_selection import VehicleDirectorySelectionWidgets
from ardupilot_methodic_configurator.frontend_tkinter_parameter_editor_documentation_frame import DocumentationFrame
from ardupilot_methodic_configurator.frontend_tkinter_parameter_editor_table import ParameterEditorTable
from ardupilot_methodic_configurator.tempcal_imu import IMUfit


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
        "Copyright © 2024 Amilcar do Carmo Lucas and ArduPilot.org\n\n"
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


class ParameterEditorWindow(BaseWindow):  # pylint: disable=too-many-instance-attributes
    """
    This class is responsible for creating and managing the graphical user interface (GUI)
    for the ArduPilot methodic configurator. It inherits from the BaseWindow class
    and provides functionalities for displaying and interacting with drone
    parameters, documentation, and flight controller connection settings.
    """

    def __init__(self, current_file: str, flight_controller: FlightController, local_filesystem: LocalFilesystem) -> None:
        super().__init__()
        self.current_file = current_file
        self.flight_controller = flight_controller
        self.local_filesystem = local_filesystem

        self.at_least_one_changed_parameter_written = False
        self.file_selection_combobox: AutoResizeCombobox
        self.show_only_differences: tk.BooleanVar
        self.annotate_params_into_files: tk.BooleanVar
        self.parameter_editor_table: ParameterEditorTable
        self.reset_progress_window: ProgressWindow
        self.param_download_progress_window: ProgressWindow
        self.tempcal_imu_progress_window: ProgressWindow
        self.file_upload_progress_window: ProgressWindow

        self.root.title(
            _("Amilcar Lucas's - ArduPilot methodic configurator ") + __version__ + _(" - Parameter file editor and uploader")
        )
        self.root.geometry("990x550")  # Set the window width

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

        self.__create_conf_widgets(__version__)

        # Create a DocumentationFrame object for the Documentation Content
        self.documentation_frame = DocumentationFrame(self.main_frame, self.local_filesystem, self.current_file)

        self.__create_parameter_area_widgets()

        # trigger a table update to ask the user what to do in the case this file needs special actions
        self.root.after(10, self.on_param_file_combobox_change(None, forced=True))  # type: ignore[func-returns-value]

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
            self, config_subframe, self.local_filesystem, self.local_filesystem.vehicle_dir, destroy_parent_on_open=False
        )
        directory_selection_frame.container_frame.pack(side=tk.LEFT, fill="x", expand=False, padx=(4, 6))

        # Create a new frame inside the config_subframe for the intermediate parameter file selection label and combobox
        file_selection_frame = ttk.Frame(config_subframe)
        file_selection_frame.pack(side=tk.LEFT, fill="x", expand=False, padx=(6, 6))

        # Create a label for the Combobox
        file_selection_label = ttk.Label(file_selection_frame, text=_("Current intermediate parameter file:"))
        file_selection_label.pack(side=tk.TOP, anchor=tk.NW)  # Add the label to the top of the file_selection_frame

        # Create Combobox for intermediate parameter file selection
        self.file_selection_combobox = AutoResizeCombobox(
            file_selection_frame,
            list(self.local_filesystem.file_parameters.keys()),
            self.current_file,
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
        self.file_selection_combobox.pack(side=tk.TOP, anchor=tk.NW, pady=(4, 0))

        font_family, _font_size = get_widget_font_family_and_size(file_selection_label)
        self.legend_frame(config_subframe, font_family)

        image_label = BaseWindow.put_image_in_label(config_frame, LocalFilesystem.application_logo_filepath())
        image_label.pack(side=tk.RIGHT, anchor=tk.NE, padx=(4, 4), pady=(4, 0))
        image_label.bind("<Button-1>", lambda event: show_about_window(self.main_frame, version))  # noqa: ARG005
        show_tooltip(image_label, _("User Manual, Support Forum, Report a Bug, Licenses, Source Code"))

    def legend_frame(self, config_subframe: ttk.Frame, font_family: str) -> None:
        style = ttk.Style()
        style.configure("Legend.TLabelframe", font=(font_family, 9))
        legend_frame = ttk.LabelFrame(config_subframe, text=_("Legend"), style="Legend.TLabelframe")
        legend_left = ttk.Frame(legend_frame)
        legend_left.pack(side=tk.LEFT, anchor=tk.NW)
        show_tooltip(legend_frame, _("the meaning of the text background colors"))

        font_size = 8
        font = (font_family, font_size)
        np_label = ttk.Label(legend_left, text=_("Normal parameter"), font=font)
        show_tooltip(np_label, _("Normal parameter - reusable in similar vehicles"))
        np_label.pack(side=tk.TOP, anchor=tk.NW)
        cal_label = ttk.Label(legend_left, text=_("Calibration param"), background="yellow", font=font)
        show_tooltip(cal_label, _("Calibration parameter - not-reusable, even in similar vehicles"))
        cal_label.pack(side=tk.TOP, anchor=tk.NW)
        readonly_label = ttk.Label(legend_left, text=_("Read-only param"), background="red", font=font)
        show_tooltip(readonly_label, _("Read-only parameter - not writable nor changeable"))
        readonly_label.pack(side=tk.TOP, anchor=tk.NW)
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
        legend_frame.pack(side=tk.LEFT, fill="x", expand=False, padx=(2, 2))

    def __create_parameter_area_widgets(self) -> None:
        self.show_only_differences = tk.BooleanVar(value=False)
        self.annotate_params_into_files = tk.BooleanVar(
            value=bool(ProgramSettings.get_setting("annotate_docs_into_param_files"))
        )

        # Create a Scrollable parameter editor table
        self.parameter_editor_table = ParameterEditorTable(self.main_frame, self.local_filesystem, self)
        self.repopulate_parameter_table(self.current_file)
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
        upload_selected_button.configure(state="normal" if self.flight_controller.master else "disabled")
        upload_selected_button.pack(side=tk.LEFT, padx=(8, 8))  # Add padding on both sides of the upload selected button
        show_tooltip(
            upload_selected_button,
            _(
                "Upload selected parameters to the flight controller and advance to the next "
                "intermediate parameter file\nIf changes have been made to the current file it will ask if you want "
                "to save them\nIt will reset the FC if necessary, re-download all parameters and validate their value"
            ),
        )

        # Create skip button
        skip_button = ttk.Button(buttons_frame, text=_("Skip parameter file"), command=self.on_skip_click)
        skip_button.pack(side=tk.RIGHT, padx=(8, 8))  # Add right padding to the skip button
        show_tooltip(
            skip_button,
            _(
                "Skip to the next intermediate parameter file without uploading any changes to the flight "
                "controller\nIf changes have been made to the current file it will ask if you want to save them"
            ),
        )

    @staticmethod
    def __display_usage_popup_window(parent: tk.Toplevel) -> None:
        usage_popup_window = BaseWindow(parent)
        style = ttk.Style()

        instructions_text = RichText(
            usage_popup_window.main_frame, wrap=tk.WORD, height=5, bd=0, background=style.lookup("TLabel", "background")
        )
        instructions_text.insert(tk.END, _("1. Read "))
        instructions_text.insert(tk.END, _("all"), "bold")
        instructions_text.insert(tk.END, _(" the documentation on top of the parameter table\n"))
        instructions_text.insert(tk.END, _("2. Edit the parameter "))
        instructions_text.insert(tk.END, _("New Values"), "italic")
        instructions_text.insert(tk.END, _(" and"), "bold")
        instructions_text.insert(tk.END, _(" their "))
        instructions_text.insert(tk.END, _("Change Reason\n"), "italic")
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
            "690x200",
            instructions_text,
        )

    def __do_tempcal_imu(self, selected_file: str) -> None:
        tempcal_imu_result_param_filename, tempcal_imu_result_param_fullpath = (
            self.local_filesystem.tempcal_imu_result_param_tuple()
        )
        if selected_file == tempcal_imu_result_param_filename:
            msg = _(
                "If you proceed the {tempcal_imu_result_param_filename}\n"
                "will be overwritten with the new calibration results.\n"
                "Do you want to provide a .bin log file and\n"
                "run the IMU temperature calibration using it?"
            )
            if messagebox.askyesno(_("IMU temperature calibration"), msg.format(**locals())):
                # file selection dialog to select the *.bin file to be used in the IMUfit temperature calibration
                filename = filedialog.askopenfilename(filetypes=[(_("ArduPilot binary log files"), ["*.bin", "*.BIN"])])
                if filename:
                    messagebox.showwarning(
                        _("IMU temperature calibration"),
                        _(
                            "Please wait, this can take a really long time "
                            "and\nthe GUI will be unresponsive until it finishes."
                        ),
                    )
                    self.tempcal_imu_progress_window = ProgressWindow(
                        self.main_frame, _("Reading IMU calibration messages"), _("Please wait, this can take a long time")
                    )
                    # Pass the selected filename to the IMUfit class
                    IMUfit(
                        logfile=filename,
                        outfile=tempcal_imu_result_param_fullpath,
                        no_graph=False,
                        log_parm=False,
                        online=False,
                        tclr=False,
                        figpath=self.local_filesystem.vehicle_dir,
                        progress_callback=self.tempcal_imu_progress_window.update_progress_bar_300_pct,
                    )
                    self.tempcal_imu_progress_window.destroy()
                    try:
                        self.local_filesystem.file_parameters = self.local_filesystem.read_params_from_files()
                    except SystemExit as exp:
                        messagebox.showerror(_("Fatal error reading parameter files"), f"{exp}")
                        raise
                    self.parameter_editor_table.set_at_least_one_param_edited(True)  # force writing doc annotations to file

    def __should_copy_fc_values_to_file(self, selected_file: str) -> None:
        auto_changed_by = self.local_filesystem.auto_changed_by(selected_file)
        if auto_changed_by and self.flight_controller.fc_parameters:
            msg = _(
                "This configuration step should be performed outside this tool by\n"
                "{auto_changed_by}\n"
                "and that should have changed the parameters on the FC.\n\n"
                "Should the FC values now be copied to the {selected_file} file?"
            )
            if messagebox.askyesno(_("Update file with values from FC?"), msg.format(**locals())):
                relevant_fc_params = {
                    key: value
                    for key, value in self.flight_controller.fc_parameters.items()
                    if key in self.local_filesystem.file_parameters[selected_file]
                }
                params_copied = self.local_filesystem.copy_fc_values_to_file(selected_file, relevant_fc_params)
                if params_copied:
                    self.parameter_editor_table.set_at_least_one_param_edited(True)

    def __should_jump_to_file(self, selected_file: str) -> str:
        jump_possible = self.local_filesystem.jump_possible(selected_file)
        for dest_file, msg in jump_possible.items():
            if messagebox.askyesno(_("Skip some steps?"), msg):
                self.file_selection_combobox.set(dest_file)
                return dest_file
        return selected_file

    def __should_download_file_from_url(self, selected_file: str) -> None:
        url, local_filename = self.local_filesystem.get_download_url_and_local_filename(selected_file)
        if url and local_filename:
            if self.local_filesystem.vehicle_configuration_file_exists(local_filename):
                return  # file already exists in the vehicle directory, no need to download it
            msg = _("Should the {local_filename} file be downloaded from the URL\n{url}?")
            if messagebox.askyesno(
                _("Download file from URL"), msg.format(**locals())
            ) and not self.local_filesystem.download_file_from_url(url, local_filename):
                error_msg = _("Failed to download {local_filename} from {url}, please download it manually")
                messagebox.showerror(_("Download failed"), error_msg.format(**locals()))

    def __should_upload_file_to_fc(self, selected_file: str) -> None:
        local_filename, remote_filename = self.local_filesystem.get_upload_local_and_remote_filenames(selected_file)
        if local_filename and remote_filename:
            if not self.local_filesystem.vehicle_configuration_file_exists(local_filename):
                error_msg = _("Local file {local_filename} does not exist")
                messagebox.showerror(_("Will not upload any file"), error_msg.format(**locals()))
                return
            if self.flight_controller.master:
                msg = _("Should the {local_filename} file be uploaded to the flight controller as {remote_filename}?")
                if messagebox.askyesno(_("Upload file to FC"), msg.format(**locals())):
                    self.file_upload_progress_window = ProgressWindow(
                        self.main_frame, _("Uploading file"), _("Uploaded {} of {} %")
                    )
                    if not self.flight_controller.upload_file(
                        local_filename, remote_filename, self.file_upload_progress_window.update_progress_bar
                    ):
                        error_msg = _("Failed to upload {local_filename} to {remote_filename}, please upload it manually")
                        messagebox.showerror(_("Upload failed"), error_msg.format(**locals()))
                    self.file_upload_progress_window.destroy()
            else:
                logging_warning(_("No flight controller connection, will not upload any file"))
                messagebox.showwarning(_("Will not upload any file"), _("No flight controller connection"))

    def on_param_file_combobox_change(self, _event: Union[None, tk.Event], forced: bool = False) -> None:
        if not self.file_selection_combobox["values"]:
            return
        self.parameter_editor_table.generate_edit_widgets_focus_out()
        selected_file = self.file_selection_combobox.get()
        if self.current_file != selected_file or forced:
            self.write_changes_to_intermediate_parameter_file()
            self.__do_tempcal_imu(selected_file)
            self.__should_copy_fc_values_to_file(selected_file)
            selected_file = self.__should_jump_to_file(selected_file)
            self.__should_download_file_from_url(selected_file)
            self.__should_upload_file_to_fc(selected_file)

            # Update the current_file attribute to the selected file
            self.current_file = selected_file
            self.at_least_one_changed_parameter_written = False
            self.documentation_frame.update_documentation_labels(selected_file)
            self.repopulate_parameter_table(selected_file)

    def download_flight_controller_parameters(self, redownload: bool = False) -> None:
        operation_string = _("Re-downloading FC parameters") if redownload else _("Downloading FC parameters")
        self.param_download_progress_window = ProgressWindow(
            self.main_frame, operation_string, _("Downloaded {} of {} parameters")
        )
        # Download all parameters from the flight controller
        self.flight_controller.fc_parameters, param_default_values = self.flight_controller.download_params(
            self.param_download_progress_window.update_progress_bar
        )
        if param_default_values:
            self.local_filesystem.write_param_default_values_to_file(param_default_values)
        self.param_download_progress_window.destroy()  # for the case that '--device test' and there is no real FC connected
        if not redownload:
            self.on_param_file_combobox_change(None, forced=True)  # the initial param read will trigger a table update

    def repopulate_parameter_table(self, selected_file: Union[None, str]) -> None:
        if not selected_file:
            return  # no file was yet selected, so skip it
        if hasattr(self.flight_controller, "fc_parameters") and self.flight_controller.fc_parameters:
            fc_parameters = self.flight_controller.fc_parameters
        else:
            fc_parameters = {}
        # Re-populate the table with the new parameters
        self.parameter_editor_table.repopulate(selected_file, fc_parameters, self.show_only_differences.get())

    def on_show_only_changed_checkbox_change(self) -> None:
        self.repopulate_parameter_table(self.current_file)

    def upload_params_that_require_reset(self, selected_params: dict) -> None:
        """
        Write the selected parameters to the flight controller that require a reset.

        After the reset, the other parameters that do not require a reset must still be written to the flight controller.
        """
        fc_reset_required = False
        fc_reset_unsure = []

        # Write each selected parameter to the flight controller
        for param_name, param in selected_params.items():
            try:
                logging_info(_("Parameter %s set to %f"), param_name, param.value)
                if param_name not in self.flight_controller.fc_parameters or not is_within_tolerance(
                    self.flight_controller.fc_parameters[param_name], param.value
                ):
                    param_metadata = self.local_filesystem.doc_dict.get(param_name, None)
                    if param_metadata and param_metadata.get("RebootRequired", False):
                        self.flight_controller.set_param(param_name, float(param.value))
                        self.at_least_one_changed_parameter_written = True
                        if param_name in self.flight_controller.fc_parameters:
                            logging_info(
                                _("Parameter %s changed from %f to %f, reset required"),
                                param_name,
                                self.flight_controller.fc_parameters[param_name],
                                param.value,
                            )
                        else:
                            logging_info(_("Parameter %s changed to %f, reset required"), param_name, param.value)
                        fc_reset_required = True
                    # Check if any of the selected parameters have a _TYPE, _EN, or _ENABLE suffix
                    elif param_name.endswith(("_TYPE", "_EN", "_ENABLE", "SID_AXIS")):
                        self.flight_controller.set_param(param_name, float(param.value))
                        self.at_least_one_changed_parameter_written = True
                        if param_name in self.flight_controller.fc_parameters:
                            logging_info(
                                _("Parameter %s changed from %f to %f, possible reset required"),
                                param_name,
                                self.flight_controller.fc_parameters[param_name],
                                param.value,
                            )
                        else:
                            logging_info(_("Parameter %s changed to %f, possible reset required"), param_name, param.value)
                        fc_reset_unsure.append(param_name)
            except ValueError as _e:  # noqa: PERF203
                error_msg = _("Failed to set parameter {param_name}: {_e}").format(**locals())
                logging_error(error_msg)
                messagebox.showerror(_("ArduPilot methodic configurator"), error_msg)

        self.__reset_and_reconnect(fc_reset_required, fc_reset_unsure)

    def __reset_and_reconnect(self, fc_reset_required: bool, fc_reset_unsure: list[str]) -> None:
        if not fc_reset_required and fc_reset_unsure:
            # Ask the user if they want to reset the ArduPilot
            _param_list_str = (", ").join(fc_reset_unsure)
            msg = _("{_param_list_str} parameter(s) potentially require a reset\nDo you want to reset the ArduPilot?")
            fc_reset_required = messagebox.askyesno(_("Possible reset required"), msg.format(**locals()))

        if fc_reset_required:
            self.reset_progress_window = ProgressWindow(
                self.main_frame, _("Resetting Flight Controller"), _("Waiting for {} of {} seconds")
            )
            filesystem_boot_delay = self.local_filesystem.file_parameters[self.current_file].get("BRD_BOOT_DELAY", Par(0.0))
            flightcontroller_boot_delay = self.flight_controller.fc_parameters.get("BRD_BOOT_DELAY", 0)
            extra_sleep_time = max(filesystem_boot_delay.value, flightcontroller_boot_delay) // 1000 + 1  # round up
            # Call reset_and_reconnect with a callback to update the reset progress bar and the progress message
            error_message = self.flight_controller.reset_and_reconnect(
                self.reset_progress_window.update_progress_bar, None, int(extra_sleep_time)
            )
            if error_message:
                logging_error(error_message)
                messagebox.showerror(_("ArduPilot methodic configurator"), error_message)
            self.reset_progress_window.destroy()  # for the case that we are doing a test and there is no real FC connected

    def on_upload_selected_click(self) -> None:
        self.parameter_editor_table.generate_edit_widgets_focus_out()

        self.write_changes_to_intermediate_parameter_file()
        selected_params = self.parameter_editor_table.get_upload_selected_params(self.current_file)
        if selected_params:
            if hasattr(self.flight_controller, "fc_parameters") and self.flight_controller.fc_parameters:
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
        self.on_skip_click(force_focus_out_event=False)

    # This function can recurse multiple times if there is an upload error
    def upload_selected_params(self, selected_params: dict) -> None:
        logging_info(_("Uploading %d selected %s parameters to flight controller..."), len(selected_params), self.current_file)

        self.upload_params_that_require_reset(selected_params)

        # Write each selected parameter to the flight controller
        for param_name, param in selected_params.items():
            try:
                self.flight_controller.set_param(param_name, param.value)
                logging_info(_("Parameter %s set to %f"), param_name, param.value)
                if param_name not in self.flight_controller.fc_parameters or not is_within_tolerance(
                    self.flight_controller.fc_parameters[param_name], param.value
                ):
                    self.at_least_one_changed_parameter_written = True
            except ValueError as _e:  # noqa: PERF203
                error_msg = _("Failed to set parameter {param_name}: {_e}").format(**locals())
                logging_error(error_msg)
                messagebox.showerror(_("ArduPilot methodic configurator"), error_msg)

        if self.at_least_one_changed_parameter_written:
            # Re-download all parameters, in case one of them changed, and validate that all uploads were successful
            self.download_flight_controller_parameters(redownload=True)
            logging_info(_("Re-download all parameters from the flight controller"))

            # Validate that the read parameters are the same as the ones in the current_file
            param_upload_error = []
            for param_name, param in selected_params.items():
                if (
                    param_name in self.flight_controller.fc_parameters
                    and param is not None
                    and not is_within_tolerance(self.flight_controller.fc_parameters[param_name], float(param.value))
                ):
                    logging_error(
                        _("Parameter %s upload to the flight controller failed. Expected: %f, Actual: %f"),
                        param_name,
                        param.value,
                        self.flight_controller.fc_parameters[param_name],
                    )
                    param_upload_error.append(param_name)
                if param_name not in self.flight_controller.fc_parameters:
                    logging_error(
                        _("Parameter %s upload to the flight controller failed. Expected: %f, Actual: N/A"),
                        param_name,
                        param.value,
                    )
                    param_upload_error.append(param_name)

            if param_upload_error:
                if messagebox.askretrycancel(
                    _("Parameter upload error"),
                    _("Failed to upload the following parameters to the flight controller:\n")
                    + f"{(', ').join(param_upload_error)}",
                ):
                    self.upload_selected_params(selected_params)
            else:
                logging_info(_("All parameters uploaded to the flight controller successfully"))
        self.local_filesystem.write_last_uploaded_filename(self.current_file)

    def on_skip_click(self, _event: Union[None, tk.Event] = None, force_focus_out_event: bool = True) -> None:
        if force_focus_out_event:
            self.parameter_editor_table.generate_edit_widgets_focus_out()
        self.write_changes_to_intermediate_parameter_file()
        # Find the next filename in the file_parameters dictionary
        files = list(self.local_filesystem.file_parameters.keys())
        if not files:
            return
        try:
            next_file_index = files.index(self.current_file) + 1
            if next_file_index >= len(files):
                self.write_summary_files()
                # Close the application and the connection
                self.close_connection_and_quit()
                return
            next_file = files[next_file_index]
            # Update the Combobox selection to the next file
            self.file_selection_combobox.set(next_file)
            # Trigger the combobox change event to update the table
            self.on_param_file_combobox_change(None)
        except ValueError:
            # If the current file is not found in the list, present a message box
            messagebox.showerror(_("ArduPilot methodic configurator"), _("Current file not found in the list of files"))
            # Close the application and the connection
            self.close_connection_and_quit()

    def write_changes_to_intermediate_parameter_file(self) -> None:
        if self.parameter_editor_table.get_at_least_one_param_edited():
            msg = _("Do you want to write the changes to the {self.current_file} file?")
            if messagebox.askyesno(_("One or more parameters have been edited"), msg.format(**locals())):
                self.local_filesystem.export_to_param(
                    self.local_filesystem.file_parameters[self.current_file],
                    self.current_file,
                    annotate_doc=self.annotate_params_into_files.get(),
                )
        self.parameter_editor_table.set_at_least_one_param_edited(False)

    def write_summary_files(self) -> None:  # pylint: disable=too-many-locals
        if not hasattr(self.flight_controller, "fc_parameters") or self.flight_controller.fc_parameters is None:
            return
        annotated_fc_parameters = self.local_filesystem.annotate_intermediate_comments_to_param_dict(
            self.flight_controller.fc_parameters
        )
        non_default__read_only_params, non_default__writable_calibrations, non_default__writable_non_calibrations = (
            self.local_filesystem.categorize_parameters(annotated_fc_parameters)
        )

        nr_total_params = len(annotated_fc_parameters)
        nr_non_default__read_only_params = len(non_default__read_only_params)
        nr_non_default__writable_calibrations = len(non_default__writable_calibrations)
        nr_non_default__writable_non_calibrations = len(non_default__writable_non_calibrations)
        _nr_unchanged_params = (
            nr_total_params
            - nr_non_default__read_only_params
            - nr_non_default__writable_calibrations
            - nr_non_default__writable_non_calibrations
        )
        # If there are no more files, present a summary message box
        summary_message = _(
            "Methodic configuration of {nr_total_params} parameters complete:\n\n"
            "{_nr_unchanged_params} kept their default value\n\n"
            "{nr_non_default__read_only_params} non-default read-only parameters - "
            "ignore these, you can not change them\n\n"
            "{nr_non_default__writable_calibrations} non-default writable sensor-calibrations - "
            "non-reusable between vehicles\n\n"
            "{nr_non_default__writable_non_calibrations} non-default writable non-sensor-calibrations - "
            "these can be reused between similar vehicles"
        )
        messagebox.showinfo(_("Last parameter file processed"), summary_message.format(**locals()))
        wrote_complete = self.write_summary_file(annotated_fc_parameters, "complete.param", annotate_doc=False)
        wrote_read_only = self.write_summary_file(
            non_default__read_only_params, "non-default_read-only.param", annotate_doc=False
        )
        wrote_calibrations = self.write_summary_file(
            non_default__writable_calibrations, "non-default_writable_calibrations.param", annotate_doc=False
        )
        wrote_non_calibrations = self.write_summary_file(
            non_default__writable_non_calibrations, "non-default_writable_non-calibrations.param", annotate_doc=False
        )
        files_to_zip = [
            (wrote_complete, "complete.param"),
            (wrote_read_only, "non-default_read-only.param"),
            (wrote_calibrations, "non-default_writable_calibrations.param"),
            (wrote_non_calibrations, "non-default_writable_non-calibrations.param"),
        ]
        self.write_zip_file(files_to_zip)

    def write_summary_file(self, param_dict: dict, filename: str, annotate_doc: bool) -> bool:
        should_write_file = True
        if param_dict:
            if self.local_filesystem.vehicle_configuration_file_exists(filename):
                msg = _("{} file already exists.\nDo you want to overwrite it?")
                should_write_file = messagebox.askyesno(_("Overwrite existing file"), msg.format(filename))
            if should_write_file:
                self.local_filesystem.export_to_param(param_dict, filename, annotate_doc)
                logging_info(_("Summary file %s written"), filename)
        return should_write_file

    def write_zip_file(self, files_to_zip: list[tuple[bool, str]]) -> bool:
        should_write_file = True
        zip_file_path = self.local_filesystem.zip_file_path()
        if self.local_filesystem.zip_file_exists():
            msg = _("{} file already exists.\nDo you want to overwrite it?")
            should_write_file = messagebox.askyesno(_("Overwrite existing file"), msg.format(zip_file_path))
        if should_write_file:
            self.local_filesystem.zip_files(files_to_zip)
            msg = _(
                "All relevant files have been zipped into the \n"
                "{zip_file_path} file.\n\nYou can now upload this file to the ArduPilot Methodic\n"
                "Configuration Blog post on discuss.ardupilot.org."
            )
            messagebox.showinfo(_("Parameter files zipped"), msg.format(**locals()))
        return should_write_file

    def close_connection_and_quit(self) -> None:
        self.parameter_editor_table.generate_edit_widgets_focus_out()
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
    return add_common_arguments_and_parse(parser)


if __name__ == "__main__":
    args = argument_parser()

    logging_basicConfig(level=logging_getLevelName(args.loglevel), format="%(asctime)s - %(levelname)s - %(message)s")

    fc = FlightController(args.reboot_time)
    filesystem = LocalFilesystem(args.vehicle_dir, args.vehicle_type, "", args.allow_editing_template_files)
    ParameterEditorWindow("04_board_orientation.param", fc, filesystem)
