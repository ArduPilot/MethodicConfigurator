"""
Modal window for browsing and downloading flight-controller log-directory files.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

from __future__ import annotations

import sys
import tkinter as tk
from tkinter import ttk
from typing import TYPE_CHECKING, Protocol

from ardupilot_methodic_configurator import _
from ardupilot_methodic_configurator.formatting import format_filesize
from ardupilot_methodic_configurator.frontend_tkinter_base_window import BaseWindow

if TYPE_CHECKING:
    from collections.abc import Callable

    from ardupilot_methodic_configurator.backend_flightcontroller_files import FlightControllerLogFile
    from ardupilot_methodic_configurator.data_model_parameter_editor import ParameterEditor
    from ardupilot_methodic_configurator.frontend_tkinter_progress_window import ProgressWindow


class DownloadBinLogsUiServices(Protocol):
    """UI callbacks required by the log-download modal."""

    asksaveasfilename: Callable[..., str]
    askdirectory: Callable[..., str]
    ask_yesno: Callable[[str, str], bool]
    show_error: Callable[[str, str], None]
    show_info: Callable[[str, str], None]

    create_progress_window: Callable[[tk.Misc, str, str, bool], ProgressWindow]


class DownloadBinLogsWindow(BaseWindow):  # pylint: disable=too-many-instance-attributes
    """Browse remote log-directory files and download selected entries."""

    DEFAULT_REMOTE_DIRECTORY = "/APM/LOGS/"

    def __init__(
        self,
        parent: tk.Tk | tk.Toplevel,
        parameter_editor: ParameterEditor,
        ui_services: DownloadBinLogsUiServices,
    ) -> None:
        super().__init__(parent)
        self.parent = parent
        self.parameter_editor = parameter_editor
        self.ui = ui_services
        self.remote_files: list[FlightControllerLogFile] = []
        self.sort_column = ""
        self.remote_directory_var = tk.StringVar(master=self.root, value=self.DEFAULT_REMOTE_DIRECTORY)

        self.root.title(_("Download .bin log files"))
        self.root.geometry(self.calculate_scaled_geometry(620, 520))
        self.center_window(self.root, parent)
        self.root.resizable(width=True, height=True)
        self.root.transient(parent)
        self.root.protocol("WM_DELETE_WINDOW", self.root.destroy)
        if sys.platform != "darwin":
            self.root.grab_set()

        self._build_widgets()
        self.refresh_remote_files()

    def _build_widgets(self) -> None:
        destination_frame = ttk.Frame(self.main_frame)
        destination_frame.pack(side=tk.TOP, fill=tk.X, padx=10, pady=(10, 4))

        ttk.Label(destination_frame, text=_("Remote destination:")).pack(side=tk.LEFT, padx=(0, 6))
        self.remote_directory_entry = ttk.Entry(destination_frame, textvariable=self.remote_directory_var)
        self.remote_directory_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.remote_directory_entry.bind("<Return>", self._on_remote_directory_return)

        refresh_button = ttk.Button(destination_frame, text=_("Open/Refresh"), command=self.refresh_remote_files)
        refresh_button.pack(side=tk.LEFT, padx=(6, 0))

        self.remote_directory_label = ttk.Label(self.main_frame, text="")
        self.remote_directory_label.pack(side=tk.TOP, anchor=tk.W, padx=10, pady=(2, 4))

        list_frame = ttk.Frame(self.main_frame)
        list_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=10, pady=(0, 8))

        self.tree = ttk.Treeview(
            list_frame,
            columns=("name", "size"),
            show="headings",
            selectmode="extended",
        )
        self._reset_sort_headings()
        self.tree.column("name", anchor=tk.W, stretch=True)
        self.tree.column("size", anchor=tk.E, width=100, stretch=False)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.tree.bind("<<TreeviewSelect>>", self._on_tree_selection_change)
        self.tree.bind("<Control-a>", self._on_select_all_key)

        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.tree.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree.configure(yscrollcommand=scrollbar.set)

        self.empty_state_label = ttk.Label(self.main_frame, text="")
        self.empty_state_label.pack(side=tk.TOP, padx=10, pady=(0, 6))

        button_frame = ttk.Frame(self.main_frame)
        button_frame.pack(side=tk.BOTTOM, fill=tk.X, padx=10, pady=(0, 10))

        self.download_button = ttk.Button(
            button_frame,
            text=_("Download"),
            command=self.download_selected_files,
            state="disabled",
        )
        self.download_button.pack(side=tk.LEFT)

        ttk.Button(
            button_frame,
            text=_("Select all"),
            command=self.select_all_files,
        ).pack(side=tk.LEFT, padx=(8, 0))

        last_log_button = ttk.Button(
            button_frame,
            text=_("Download last .bin log file"),
            command=self.download_last_flight_log,
        )
        last_log_button.pack(side=tk.LEFT, padx=(8, 0))

        ttk.Button(button_frame, text=_("Cancel"), command=self.root.destroy).pack(side=tk.RIGHT)

    def refresh_remote_files(self) -> None:
        """Reload the remote file list from the selected remote directory."""
        remote_directory = self.remote_directory_var.get().strip()
        if not remote_directory:
            self.ui.show_error(_("Remote directory error"), _("The remote destination must not be empty."))
            return

        try:
            self.remote_files = self.parameter_editor.get_bin_log_files(remote_directory)
        except Exception as error:  # pylint: disable=broad-exception-caught
            self.remote_files = []
            self.ui.show_error(_("Remote directory error"), str(error))
            return

        self._populate_tree()
        self.remote_directory_label.configure(text=_("Files in {remote_directory}").format(remote_directory=remote_directory))

    def _on_remote_directory_return(self, _event: tk.Event | None = None) -> str:
        """Refresh the remote listing when Enter is pressed in the directory entry."""
        self.refresh_remote_files()
        return "break"

    def _populate_tree(self) -> None:
        """Replace the tree contents with the current remote file list."""
        self.sort_column = ""
        self._reset_sort_headings()
        for item_id in self.tree.get_children():
            self.tree.delete(item_id)

        for index, remote_file in enumerate(self.remote_files):
            self.tree.insert(
                "",
                tk.END,
                iid=str(index),
                values=(remote_file.name, format_filesize(remote_file.size_bytes)),
            )

        if self.remote_files:
            self.empty_state_label.configure(text="")
        else:
            self.empty_state_label.configure(text=_("No regular files found in this remote directory."))
        self._on_tree_selection_change()

    def _reset_sort_headings(self) -> None:
        """Set translated Treeview headings and their initial sort commands."""
        self.tree.heading(
            "name",
            text=_("File name"),
            command=lambda: self._sort_by_column("name", reverse=False),
        )
        self.tree.heading(
            "size",
            text=_("Size"),
            command=lambda: self._sort_by_column("size", reverse=False),
        )

    def _sort_by_column(self, column: str, reverse: bool) -> None:
        """Sort Treeview rows by filename or numeric file size."""
        if self.sort_column and self.sort_column != column:
            self._set_sort_heading(self.sort_column, reverse=None)

        self._set_sort_heading(column, reverse=reverse)
        self.sort_column = column

        rows = [(self._sort_key(item_id, column), item_id) for item_id in self.tree.get_children("")]
        rows.sort(key=lambda row: row[0], reverse=reverse)
        for position, (_sort_key, item_id) in enumerate(rows):
            self.tree.move(item_id, "", position)

        self.tree.heading(
            column,
            command=lambda: self._sort_by_column(column, reverse=not reverse),
        )

    def _set_sort_heading(self, column: str, reverse: bool | None) -> None:
        """Update one heading's text, optionally adding a sort-direction arrow."""
        heading_text = _("File name") if column == "name" else _("Size")
        if reverse is not None:
            heading_text += " ▼" if reverse else " ▲"
        self.tree.heading(column, text=heading_text)

    def _sort_key(self, item_id: str, column: str) -> tuple[int | str, str]:
        """Return a stable sort key using the unformatted application values."""
        item_text = str(item_id)
        if item_text.isdigit() and int(item_text) < len(self.remote_files):
            remote_file = self.remote_files[int(item_text)]
            if column == "size":
                return remote_file.size_bytes, remote_file.name.casefold()
            return remote_file.name.casefold(), remote_file.name
        return (0, "") if column == "size" else ("", "")

    def select_all_files(self) -> None:
        """Select every listed regular file except the parent-directory entry."""
        selectable_item_ids = [str(index) for index, remote_file in enumerate(self.remote_files) if remote_file.name != ".."]
        self.tree.selection_set(selectable_item_ids)
        self._on_tree_selection_change()

    def _on_select_all_key(self, _event: tk.Event | None = None) -> str:
        """Select all files when the user presses Ctrl+A in the Treeview."""
        self.select_all_files()
        return "break"

    def _on_tree_selection_change(self, _event: tk.Event | None = None) -> None:
        """Enable downloading only when at least one remote file is selected."""
        selected = self.tree.selection()
        self.download_button.configure(state="normal" if selected else "disabled")

    def _selected_files(self) -> list[FlightControllerLogFile]:
        """Return remote-file records corresponding to the current tree selection."""
        selected_files: list[FlightControllerLogFile] = []
        for item_id in self.tree.selection():
            if not str(item_id).isdigit():
                continue
            index = int(item_id)
            if index < len(self.remote_files):
                selected_files.append(self.remote_files[index])
        return selected_files

    def download_selected_files(self) -> None:
        """Ask for a local destination and download the selected remote files."""
        selected_files = self._selected_files()
        if not selected_files:
            return

        if len(selected_files) == 1:
            remote_file = selected_files[0]
            destination = self.ui.asksaveasfilename(
                title=_("Save flight-controller file as"),
                initialfile=remote_file.name,
                filetypes=[
                    (_("All files"), "*.*"),
                    (_("Binary log files"), "*.bin"),
                ],
            )
            destination_is_directory = False
        else:
            destination = self.ui.askdirectory(title=_("Select local destination directory"))
            destination_is_directory = True

        if not destination:
            return

        progress_window = self.ui.create_progress_window(
            self.root,
            _("Downloading flight-controller file(s)"),
            _("Downloaded {} of {} bytes"),
            False,  # noqa: FBT003
        )
        try:
            self.parameter_editor.download_selected_bin_logs_workflow(
                selected_files=selected_files,
                destination=destination,
                destination_is_directory=destination_is_directory,
                ask_overwrite=self.ui.ask_yesno,
                show_error=self.ui.show_error,
                show_info=self.ui.show_info,
                progress_callback=progress_window.update_progress_bar,
            )
        finally:
            progress_window.destroy()

    def download_last_flight_log(self) -> None:
        """Invoke the existing last-flight-log download workflow."""
        progress_window = self.ui.create_progress_window(
            self.root,
            _("Downloading Flight Log"),
            _("Downloaded {}% from {}%"),
            False,  # noqa: FBT003
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

        try:
            self.parameter_editor.download_last_flight_log_workflow(
                ask_saveas_filename=ask_saveas_filename,
                show_error=self.ui.show_error,
                show_info=self.ui.show_info,
                progress_callback=progress_window.update_progress_bar,
            )
        finally:
            progress_window.destroy()
