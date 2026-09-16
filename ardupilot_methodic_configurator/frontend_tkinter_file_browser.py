# pylint: disable=too-many-lines
"""
Modal two-panel MAVFTP/local-file browser.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

from __future__ import annotations

import os
import posixpath
import subprocess
import sys
import tkinter as tk
from argparse import ArgumentParser, Namespace
from datetime import datetime, timezone
from logging import basicConfig as logging_basicConfig
from logging import getLevelName as logging_getLevelName
from pathlib import Path
from tkinter import filedialog, simpledialog, ttk
from typing import TYPE_CHECKING, Literal, Protocol, cast

from ardupilot_methodic_configurator import _
from ardupilot_methodic_configurator.backend_filesystem import LocalFilesystem
from ardupilot_methodic_configurator.backend_flightcontroller import FlightController
from ardupilot_methodic_configurator.backend_flightcontroller_files import (
    FlightControllerLogFile,
    LastLogDownloadResult,
    is_safe_local_entry_name,
)
from ardupilot_methodic_configurator.backend_internet import webbrowser_open_url
from ardupilot_methodic_configurator.common_arguments import add_common_arguments
from ardupilot_methodic_configurator.data_model_parameter_editor import ParameterEditor
from ardupilot_methodic_configurator.formatting import format_filesize
from ardupilot_methodic_configurator.frontend_tkinter_base_window import (
    BaseWindow,
    ask_yesno_popup,
    show_error_popup,
    show_info_popup,
)
from ardupilot_methodic_configurator.frontend_tkinter_file_browser_operations import (
    LocalFileEntry,
    LocalUploadPlan,
    RemoteDownloadPlan,
    RemoteDownloadPreflight,
    TransferBatchResults,
    _build_local_upload_plan,
    _create_remote_directory_worker,
    _delete_remote_entries_worker,
    _download_last_flight_log_worker,
    _download_remote_plan_worker,
    _local_directory_entries,
    _prepare_remote_download,
    _rename_remote_entry_worker,
    _retry_local_upload_plan,
    _retry_remote_download_plan,
    _upload_local_plan_worker,
)
from ardupilot_methodic_configurator.frontend_tkinter_file_browser_tasks import BackgroundTaskRunner, TaskRunner
from ardupilot_methodic_configurator.frontend_tkinter_progress_window import ProgressWindow
from ardupilot_methodic_configurator.frontend_tkinter_show import show_tooltip

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence


class FileBrowserUiServices(Protocol):  # pylint: disable=too-few-public-methods
    """UI callbacks required by the two-panel file browser."""

    asksaveasfilename: Callable[..., str]
    askdirectory: Callable[..., str]
    askstring: Callable[..., str | None]
    ask_yesno: Callable[[str, str], bool]
    show_error: Callable[[str, str], None]
    show_info: Callable[[str, str], None]

    create_progress_window: Callable[[tk.Misc, str, str, bool], ProgressWindow]


class FileBrowserWindow(  # pylint: disable=attribute-defined-outside-init, too-many-instance-attributes
    BaseWindow
):
    """Browse remote and local files and transfer or manage selected entries."""

    DEFAULT_REMOTE_DIRECTORY = "/APM/LOGS/"
    MAX_SUMMARY_ENTRIES = 20
    TREE_COLUMNS: tuple[tuple[str, str, Literal["w", "e"], int], ...] = (
        ("name", _("Name"), "w", 170),
        ("type", _("Type"), "w", 80),
        ("size", _("Size"), "e", 80),
        ("modified", _("Modified"), "w", 145),
    )
    download_button: ttk.Button

    def __init__(
        self,
        parent: tk.Tk | tk.Toplevel | None,
        parameter_editor: ParameterEditor,
        ui_services: FileBrowserUiServices,
        *,
        task_runner: TaskRunner | None = None,
    ) -> None:
        super().__init__(parent)
        self.parent = parent
        self.parameter_editor = parameter_editor
        self.ui = ui_services
        self.remote_entries: list[FlightControllerLogFile] = []
        self.local_entries: list[LocalFileEntry] = []
        self.remote_sort_column = ""
        self.local_sort_column = ""
        self.remote_sort_reverse = False
        self.local_sort_reverse = False
        self.last_selected_panel = "remote"
        self.last_selected_items: dict[str, str | None] = {"remote": None, "local": None}
        self._pending_entry_selection: dict[str, str | None] = {"remote": None, "local": None}
        self._task_runner: TaskRunner = task_runner if task_runner is not None else BackgroundTaskRunner(self.root.after)
        self.verify_transfers_var = tk.BooleanVar(master=self.root, value=False)
        self._panel_navigation_enabled = True
        self._closed_callback: Callable[[], None] | None = None
        self.remote_directory_var = tk.StringVar(master=self.root, value=self.DEFAULT_REMOTE_DIRECTORY)
        self.local_directory_var = tk.StringVar(
            master=self.root,
            value=self._default_local_directory(parameter_editor),
        )

        self.root.title(_("Flight-controller files"))
        self.root.geometry(self.calculate_scaled_geometry(1100, 620))
        if parent is None:
            self.center_window_on_screen(self.root)
        else:
            self.center_window(self.root, parent)
        self.root.resizable(width=True, height=True)
        if parent is not None:
            self.root.transient(parent)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        if parent is not None and sys.platform != "darwin":
            self.root.grab_set()

        self._build_widgets()
        self._bind_panel_navigation()
        self.root.after_idle(self._refresh_initial_panels)

    def set_closed_callback(self, callback: Callable[[], None] | None) -> None:
        """Set a callback invoked after the browser window is closed."""
        self._closed_callback = callback

    def _refresh_initial_panels(self) -> None:
        """Populate both panels after Tk has had a chance to render the window."""
        self.refresh_local_panel()
        self.refresh_remote_panel(("/APM/", "/"))

    def _build_widgets(self) -> None:
        """Create the two file panels and action buttons."""
        panels = ttk.PanedWindow(self.main_frame, orient=tk.HORIZONTAL)
        panels.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=8, pady=(8, 4))

        remote_panel = ttk.Frame(panels)
        local_panel = ttk.Frame(panels)
        panels.add(remote_panel, weight=1)
        panels.add(local_panel, weight=1)

        self._build_remote_panel(remote_panel)
        self._build_local_panel(local_panel)

        action_frame = ttk.Frame(self.main_frame)
        action_frame.pack(side=tk.BOTTOM, fill=tk.X, padx=8, pady=(4, 8))
        for column in range(4):
            action_frame.columnconfigure(column, weight=1, uniform="action")

        download_button = ttk.Button(
            action_frame,
            text=_("Download selected →"),
            command=self.download_selected_remote_entries,
        )
        self.download_button = download_button
        download_button.grid(row=0, column=0, columnspan=2, padx=3, sticky=tk.EW)
        show_tooltip(
            download_button, _("Download selected files and directories from the flight controller to the local computer")
        )

        upload_button = ttk.Button(
            action_frame,
            text=_("← Upload selected"),
            command=self.upload_selected_local_entries,
        )
        self.upload_button = upload_button
        upload_button.grid(row=0, column=2, columnspan=2, padx=3, sticky=tk.EW)
        show_tooltip(
            upload_button, _("Upload selected files and directories from the local computer to the flight controller")
        )

        self.verify_checkbox = ttk.Checkbutton(
            action_frame,
            text=_("Verify transfers with CRC32"),
            variable=self.verify_transfers_var,
        )
        self.verify_checkbox.grid(row=1, column=0, sticky=tk.W, padx=3, pady=(6, 0))
        show_tooltip(self.verify_checkbox, _("Compare local and flight-controller checksums after each transfer"))

        self.last_log_button = ttk.Button(
            action_frame,
            text=_("Download last FC log"),
            command=self.download_last_flight_log,
        )
        self.last_log_button.grid(row=1, column=1, padx=3, pady=(6, 0), sticky=tk.EW)
        show_tooltip(self.last_log_button, _("Download the last flight-controller .bin log file"))

        self.help_button = ttk.Button(
            action_frame,
            text=_("Help"),
            command=lambda: webbrowser_open_url("https://ardupilot.github.io/MethodicConfigurator/USERMANUAL_MAVFTP.html"),
        )
        self.help_button.grid(row=1, column=2, padx=3, pady=(6, 0), sticky=tk.EW)
        show_tooltip(self.help_button, _("Open the MAVFTP file browser user manual"))

        self.close_button = ttk.Button(action_frame, text=_("Close"), command=self._on_close)
        self.close_button.grid(row=1, column=3, padx=3, pady=(6, 0), sticky=tk.EW)
        show_tooltip(self.close_button, _("Close the file browser"))

    def _bind_panel_navigation(self) -> None:
        """Handle panel-navigation arrows even before a Treeview receives focus."""
        self.root.bind("<Left>", self._on_left_arrow)
        self.root.bind("<Right>", self._on_right_arrow)

    @staticmethod
    def _default_local_directory(parameter_editor: ParameterEditor) -> str:
        """Return the current vehicle directory, falling back to the working directory."""
        try:
            vehicle_directory = parameter_editor.get_vehicle_directory()
        except (AttributeError, OSError, TypeError):
            vehicle_directory = ""
        if isinstance(vehicle_directory, str) and vehicle_directory:
            path = Path(vehicle_directory).expanduser()
            if path.is_dir():
                return str(path)
        return str(Path.cwd())

    def _build_remote_panel(self, parent: ttk.Frame) -> None:
        """Create the remote destination selector and remote Treeview."""
        selector = ttk.Frame(parent)
        selector.pack(side=tk.TOP, fill=tk.X, pady=(0, 4))
        ttk.Label(selector, text=_("FC directory:")).pack(side=tk.LEFT, padx=(0, 6))
        self.remote_directory_entry = ttk.Entry(selector, textvariable=self.remote_directory_var)
        self.remote_directory_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.remote_directory_entry.bind("<Return>", self._on_remote_directory_return)
        self.remote_parent_button = ttk.Button(
            selector,
            text="↑",
            width=3,
            command=self.navigate_remote_parent,
        )
        self.remote_parent_button.pack(side=tk.LEFT, padx=(6, 0))
        show_tooltip(self.remote_parent_button, _("Go to the parent directory on the flight controller"))

        open_remote_button = ttk.Button(selector, text="⟳", width=3, command=self.refresh_remote_panel)
        open_remote_button.pack(side=tk.LEFT, padx=(6, 0))
        show_tooltip(open_remote_button, _("Open the remote directory and refresh its contents"))

        select_remote_button = ttk.Button(selector, text=_("Select all"), command=self.select_all_remote_entries)
        select_remote_button.pack(side=tk.LEFT, padx=(6, 0))
        show_tooltip(select_remote_button, _("Select all remote files and directories"))

        self.remote_directory_label = ttk.Label(parent, text="")
        self.remote_directory_label.pack(side=tk.TOP, anchor=tk.W, pady=(0, 4))
        self.remote_empty_state_label = ttk.Label(parent, text="")
        self.remote_empty_state_label.pack(side=tk.TOP, anchor=tk.W, pady=(0, 4))
        self.remote_tree = self._create_tree(parent, remote=True)

    def _build_local_panel(self, parent: ttk.Frame) -> None:
        """Create the local directory selector and local Treeview."""
        selector = ttk.Frame(parent)
        selector.pack(side=tk.TOP, fill=tk.X, pady=(0, 4))
        ttk.Label(selector, text=_("PC directory:")).pack(side=tk.LEFT, padx=(0, 6))
        self.local_directory_entry = ttk.Entry(selector, textvariable=self.local_directory_var)
        self.local_directory_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.local_directory_entry.bind("<Return>", self._on_local_directory_return)
        self.local_parent_button = ttk.Button(
            selector,
            text="↑",
            width=3,
            command=self.navigate_local_parent,
        )
        self.local_parent_button.pack(side=tk.LEFT, padx=(6, 0))
        show_tooltip(self.local_parent_button, _("Go to the parent directory on the local computer"))

        browse_local_button = ttk.Button(selector, text=_("Browse"), command=self.choose_local_directory)
        browse_local_button.pack(side=tk.LEFT, padx=(6, 0))
        show_tooltip(browse_local_button, _("Choose a local directory"))

        refresh_local_button = ttk.Button(selector, text="⟳", width=3, command=self.refresh_local_panel)
        refresh_local_button.pack(side=tk.LEFT, padx=(6, 0))
        show_tooltip(refresh_local_button, _("Refresh the local directory contents"))

        select_local_button = ttk.Button(selector, text=_("Select all"), command=self.select_all_local_entries)
        select_local_button.pack(side=tk.LEFT, padx=(6, 0))
        show_tooltip(select_local_button, _("Select all local files and directories"))

        self.local_directory_label = ttk.Label(parent, text="")
        self.local_directory_label.pack(side=tk.TOP, anchor=tk.W, pady=(0, 4))
        self.local_empty_state_label = ttk.Label(parent, text="")
        self.local_empty_state_label.pack(side=tk.TOP, anchor=tk.W, pady=(0, 4))
        self.local_tree = self._create_tree(parent, remote=False)

    def _create_tree(self, parent: ttk.Frame, *, remote: bool) -> ttk.Treeview:
        """Create one panel Treeview with sorting and navigation bindings."""
        tree = ttk.Treeview(
            parent,
            columns=("name", "type", "size", "modified"),
            show="headings",
            selectmode="extended",
        )
        sort_prefix = "remote" if remote else "local"
        self._configure_tree_columns(tree, sort_prefix)
        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        tree.bind("<Double-1>", self._on_remote_double_click if remote else self._on_local_double_click)
        tree.bind("<Control-a>", self._on_select_all_key)
        tree.bind("<Command-a>", self._on_select_all_key)
        tree.bind("<Delete>", self._on_delete_key)
        tree.bind("<F2>", self._on_rename_key)
        tree.bind("<BackSpace>", self._on_backspace)
        tree.bind("<F5>", self._on_refresh_key)
        tree.bind("<Left>", self._on_left_arrow)
        tree.bind("<Right>", self._on_right_arrow)

        def show_context_menu(event: tk.Event, is_remote: bool = remote) -> str:
            return self._show_context_menu(event, is_remote)

        tree.bind("<Button-3>", show_context_menu)
        if sys.platform == "darwin":
            tree.bind("<Control-Button-1>", show_context_menu)

        def remember_focus(_event: tk.Event, panel: str = sort_prefix) -> None:
            self._remember_panel(panel)

        def remember_click(event: tk.Event, panel: str = sort_prefix) -> None:
            self._remember_panel_from_click(panel, event)

        def remember_selection(_event: tk.Event, panel: str = sort_prefix) -> None:
            self._remember_panel_from_selection(panel)

        tree.bind("<FocusIn>", remember_focus)
        tree.bind("<ButtonRelease-1>", remember_click)
        tree.bind("<<TreeviewSelect>>", remember_selection)
        scrollbar = ttk.Scrollbar(parent, orient=tk.VERTICAL, command=tree.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        tree.configure(yscrollcommand=scrollbar.set)
        return tree

    def _configure_tree_columns(self, tree: ttk.Treeview, sort_prefix: str) -> None:
        """Configure headings and column widths for one panel."""
        for column, title, anchor, width in self.TREE_COLUMNS:

            def sort_heading(col: str = column, prefix: str = sort_prefix) -> None:
                self._on_sort_heading(prefix, col)

            tree.heading(column, text=title, command=sort_heading)
            tree.column(column, anchor=anchor, width=width, stretch=column == "name")

    def refresh_remote_panel(self, fallback_directories: tuple[str, ...] = ()) -> None:
        """Refresh the remote panel, including directory entries."""
        if self._controls_locked():
            return
        remote_directory = self.remote_directory_var.get()
        if not remote_directory.strip():
            self.ui.show_error(_("Remote directory error"), _("The remote destination must not be empty."))
            return
        remote_empty_state_label = getattr(self, "remote_empty_state_label", None)
        if remote_empty_state_label is not None:
            remote_empty_state_label.configure(text="")

        def complete(result: object, error: Exception | None) -> None:
            if isinstance(error, FileNotFoundError) and fallback_directories:
                fallback_directory, *remaining_directories = fallback_directories
                self.remote_directory_var.set(fallback_directory)
                self.refresh_remote_panel(tuple(remaining_directories))
                return
            if error is not None:
                self.ui.show_error(_("Remote directory error"), str(error))
                return
            entries = cast("list[FlightControllerLogFile] | None", result)
            if entries is None:
                self.ui.show_error(_("Remote directory error"), _("Could not list the remote directory."))
                return
            self.remote_entries = entries
            self._populate_remote_tree()
            self._select_pending_entry("remote")
            self._update_parent_navigation_buttons()
            self.remote_directory_label.configure(
                text=_("Remote files in {remote_directory}").format(remote_directory=remote_directory)
            )

        self.remote_directory_label.configure(text=_("Loading remote directory…"))

        self._start_remote_task(
            lambda: self.parameter_editor.get_remote_files(remote_directory),
            complete,
        )

    def refresh_local_panel(self) -> None:
        """Refresh the local panel from the selected directory."""
        directory = Path(self.local_directory_var.get()).expanduser()
        local_empty_state_label = getattr(self, "local_empty_state_label", None)
        if local_empty_state_label is not None:
            local_empty_state_label.configure(text="")
        if not directory.is_dir():
            self.ui.show_error(_("Local directory error"), _("The selected local directory does not exist."))
            return
        entries: list[LocalFileEntry] = []
        try:
            entries = _local_directory_entries(directory)
        except OSError as error:
            self.ui.show_error(_("Local directory error"), str(error))
            return
        self.local_entries = entries
        self._populate_local_tree()
        self._select_pending_entry("local")
        self._update_parent_navigation_buttons()
        self.local_directory_label.configure(text=_("Local files in {directory}").format(directory=directory))

    def _update_parent_navigation_buttons(self) -> None:
        """Enable parent buttons only when the corresponding panel has a parent."""
        if self._controls_locked():
            return
        remote_button = getattr(self, "remote_parent_button", None)
        remote_directory_var = getattr(self, "remote_directory_var", None)
        if remote_button is not None and remote_directory_var is not None:
            remote_directory = remote_directory_var.get().rstrip("/")
            remote_button.configure(state="normal" if remote_directory and remote_directory != "/" else "disabled")

        local_button = getattr(self, "local_parent_button", None)
        local_directory_var = getattr(self, "local_directory_var", None)
        if local_button is not None and local_directory_var is not None:
            local_directory = Path(local_directory_var.get()).expanduser()
            local_button.configure(state="normal" if local_directory.parent != local_directory else "disabled")

    def navigate_remote_parent(self) -> None:
        """Navigate the remote panel to its parent directory."""
        if self._controls_locked():
            return
        remote_directory = self.remote_directory_var.get()
        without_trailing_slashes = remote_directory.rstrip("/")
        if not remote_directory.strip() or not without_trailing_slashes or without_trailing_slashes == "/":
            return
        self.remote_directory_var.set(posixpath.dirname(without_trailing_slashes) or "/")
        self.refresh_remote_panel()

    def navigate_local_parent(self) -> None:
        """Navigate the local panel to its parent directory."""
        if self._controls_locked():
            return
        local_directory = Path(self.local_directory_var.get()).expanduser()
        if local_directory.parent != local_directory:
            self.local_directory_var.set(str(local_directory.parent))
            self.refresh_local_panel()

    def choose_local_directory(self) -> None:
        """Choose and open a local directory."""
        directory = self.ui.askdirectory(
            title=_("Select local directory"),
            initialdir=self.local_directory_var.get(),
        )
        if directory:
            self.local_directory_var.set(directory)
            self.refresh_local_panel()

    def _populate_remote_tree(self) -> None:
        """Populate the remote Treeview."""
        self._populate_tree("remote")

    def _populate_local_tree(self) -> None:
        """Populate the local Treeview."""
        self._populate_tree("local")

    def _populate_tree(self, panel: Literal["remote", "local"]) -> None:
        """Render one panel's rows while keeping its selection and sort state separate."""
        remote = panel == "remote"
        tree = self.remote_tree if remote else self.local_tree
        entries: Sequence[FlightControllerLogFile | LocalFileEntry] = self.remote_entries if remote else self.local_entries
        empty_state_label = self.remote_empty_state_label if remote else self.local_empty_state_label
        self.last_selected_items[panel] = None
        self._reset_tree_headings(tree, panel)
        for item_id in tree.get_children():
            tree.delete(item_id)
        for index, entry in enumerate(entries):
            tree.insert(
                "",
                tk.END,
                iid=str(index),
                values=(
                    entry.name,
                    _("Directory") if entry.is_directory else _("File"),
                    "" if entry.is_directory else format_filesize(entry.size_bytes),
                    self._format_modified_time(entry.modified_at, unsupported_when_missing=remote),
                ),
            )
        self._update_empty_state(entries, empty_state_label)
        self._update_transfer_buttons()

    def _select_entry_after_refresh(self, panel: str, entry_name: str) -> None:
        """Select an entry by name after the next successful panel refresh."""
        pending_selection = cast(
            "dict[str, str | None] | None",
            getattr(self, "_pending_entry_selection", None),
        )
        if pending_selection is None:
            new_pending_selection: dict[str, str | None] = {"remote": None, "local": None}
            self._pending_entry_selection = new_pending_selection
            pending_selection = new_pending_selection
        pending_selection[panel] = entry_name

    def _select_pending_entry(self, panel: str) -> None:
        """Select and reveal the entry requested before a panel refresh."""
        pending_selection = getattr(self, "_pending_entry_selection", None)
        if not pending_selection:
            return
        entry_name = pending_selection.get(panel)
        pending_selection[panel] = None
        if entry_name is None:
            return
        entries: Sequence[FlightControllerLogFile | LocalFileEntry] = (
            self.remote_entries if panel == "remote" else self.local_entries
        )
        tree = self.remote_tree if panel == "remote" else self.local_tree
        item_id = next((str(index) for index, entry in enumerate(entries) if entry.name == entry_name), None)
        if item_id is None:
            return
        tree.selection_set(item_id)
        tree.focus(item_id)
        tree.see(item_id)
        self.last_selected_items[panel] = item_id
        self._remember_panel(panel)
        self._update_transfer_buttons()

    @staticmethod
    def _update_empty_state(entries: Sequence[FlightControllerLogFile | LocalFileEntry], label: ttk.Label) -> None:
        """Show a simple empty state when a panel contains no rows."""
        label.configure(text=_("No entries found in this directory.") if not entries else "")

    @staticmethod
    def _format_modified_time(timestamp: float | None, *, unsupported_when_missing: bool = False) -> str:
        """Format a Unix modification timestamp for a browser table cell."""
        if timestamp is None:
            return _("Unsupported") if unsupported_when_missing else ""
        if timestamp <= 0:
            return "-"
        try:
            return datetime.fromtimestamp(timestamp, tz=timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M")
        except (OverflowError, OSError, ValueError):
            return "-"

    def _reset_tree_headings(self, tree: ttk.Treeview, prefix: str) -> None:
        """Reset translated headings and initial sort commands."""
        sort_state = "remote_sort_column" if prefix == "remote" else "local_sort_column"
        reverse_state = "remote_sort_reverse" if prefix == "remote" else "local_sort_reverse"
        setattr(self, sort_state, "")
        setattr(self, reverse_state, False)
        for column, title in (
            ("name", _("Name")),
            ("type", _("Type")),
            ("size", _("Size")),
            ("modified", _("Modified")),
        ):

            def sort_heading(col: str = column, panel: str = prefix) -> None:
                self._on_sort_heading(panel, col)

            tree.heading(
                column,
                text=title,
                command=sort_heading,
            )

    def _on_sort_heading(self, panel: str, column: str) -> None:
        """Toggle the selected column direction, or start a new ascending sort."""
        state_name = "remote_sort_column" if panel == "remote" else "local_sort_column"
        reverse_state = "remote_sort_reverse" if panel == "remote" else "local_sort_reverse"
        previous_column = getattr(self, state_name)
        previous_reverse = getattr(self, reverse_state)
        reverse = not previous_reverse if previous_column == column else False
        self._sort_panel_by_column(panel, column, reverse)

    def _sort_panel_by_column(self, panel: str, column: str, reverse: bool) -> None:
        """Sort one panel by name, type, numeric size, or modification time."""
        tree = self.remote_tree if panel == "remote" else self.local_tree
        entries = self.remote_entries if panel == "remote" else self.local_entries
        state_name = "remote_sort_column" if panel == "remote" else "local_sort_column"
        reverse_state = "remote_sort_reverse" if panel == "remote" else "local_sort_reverse"
        previous = getattr(self, state_name)
        if previous and previous != column:
            self._set_heading_text(tree, previous, None)
        self._set_heading_text(tree, column, reverse)
        setattr(self, state_name, column)
        setattr(self, reverse_state, reverse)
        rows = [(self._panel_sort_key(entries, item_id, column), item_id) for item_id in tree.get_children("")]
        rows.sort(key=lambda row: row[0], reverse=reverse)
        for position, (_key, item_id) in enumerate(rows):
            tree.move(item_id, "", position)
        tree.heading(column, command=lambda: self._on_sort_heading(panel, column))

    @staticmethod
    def _panel_sort_key(
        entries: Sequence[FlightControllerLogFile | LocalFileEntry],
        item_id: str,
        column: str,
    ) -> tuple[int, float | int | str, str]:
        """Return a stable sort key from an entry list."""
        item_text = str(item_id)
        if not item_text.isdigit() or int(item_text) >= len(entries):
            return (0, 0, "")
        entry = entries[int(item_text)]
        name = entry.name.casefold()
        if entry.name == "..":
            return (0, 0, "")
        if column == "size":
            return (1, entry.size_bytes, name)
        if column == "modified":
            return (1, entry.modified_at if entry.modified_at is not None else float("-inf"), name)
        if column == "type":
            return (1, 0 if entry.is_directory else 1, name)
        return (1, name, entry.name)

    @staticmethod
    def _set_heading_text(tree: ttk.Treeview, column: str, reverse: bool | None) -> None:
        """Set a heading's label and optional direction marker."""
        title = {
            "name": _("Name"),
            "type": _("Type"),
            "size": _("Size"),
            "modified": _("Modified"),
        }[column]
        if reverse is not None:
            title += " ▼" if reverse else " ▲"
        tree.heading(column, text=title)

    def _on_remote_directory_return(self, _event: tk.Event | None = None) -> str:
        """Refresh the remote listing when Enter is pressed in its entry."""
        self.refresh_remote_panel()
        return "break"

    def _on_local_directory_return(self, _event: tk.Event | None = None) -> str:
        """Refresh the local listing when Enter is pressed in its entry."""
        self.refresh_local_panel()
        return "break"

    def _on_refresh_key(self, event: tk.Event | None = None) -> str:
        """Refresh the panel that currently owns the F5 key event."""
        widget = getattr(event, "widget", None)
        if widget is self.remote_tree:
            self._remember_panel("remote")
            self.refresh_remote_panel()
        elif widget is self.local_tree:
            self._remember_panel("local")
            self.refresh_local_panel()
        return "break"

    def _remember_panel(self, panel: str) -> None:
        """Remember which panel was most recently focused or selected."""
        if panel in {"remote", "local"}:
            self.last_selected_panel = panel

    def _controls_locked(self) -> bool:
        """Return whether a task owns the browser controls."""
        runner = getattr(self, "_task_runner", None)
        return runner is not None and runner.active

    def _remember_panel_from_click(self, panel: str, event: tk.Event) -> None:
        """Remember the panel and row most recently clicked by the user."""
        self._remember_panel(panel)
        tree = self.remote_tree if panel == "remote" else self.local_tree
        item_id = tree.identify_row(event.y)
        if item_id:
            self.last_selected_items[panel] = item_id

    def _remember_panel_from_selection(self, panel: str) -> None:
        """Remember the panel and focused row after a Treeview selection change."""
        self._remember_panel(panel)
        tree = self.remote_tree if panel == "remote" else self.local_tree
        item_id = tree.focus()
        if item_id:
            self.last_selected_items[panel] = item_id
        self._update_transfer_buttons()

    def _on_left_arrow(self, _event: tk.Event | None = None) -> str:
        """Focus the left remote panel and select its first entry when needed."""
        if isinstance(getattr(_event, "widget", None), (tk.Entry, ttk.Entry)):
            return ""
        if not getattr(self, "_panel_navigation_enabled", True):
            return ""
        self._focus_panel("remote")
        return "break"

    def _on_right_arrow(self, _event: tk.Event | None = None) -> str:
        """Focus the right local panel and select its first entry when needed."""
        if isinstance(getattr(_event, "widget", None), (tk.Entry, ttk.Entry)):
            return ""
        if not getattr(self, "_panel_navigation_enabled", True):
            return ""
        self._focus_panel("local")
        return "break"

    def _focus_panel(self, panel: str) -> None:
        """Focus a panel and select its first usable entry if it has no selection."""
        tree = self.remote_tree if panel == "remote" else self.local_tree
        self._remember_panel(panel)
        tree.focus_set()
        selected = tuple(tree.selection())
        item_id: str | None = None
        if selected:
            focused_item = tree.focus()
            item_id = focused_item
            if item_id not in selected:
                item_id = selected[0]
        else:
            item_id = self._first_selectable_tree_item(tree)
            if item_id is not None:
                tree.selection_set(item_id)
                self.last_selected_items[panel] = item_id
        if item_id is not None:
            tree.focus(item_id)
            tree.see(item_id)
        self._update_transfer_buttons()

    @staticmethod
    def _first_selectable_tree_item(tree: ttk.Treeview) -> str | None:
        """Return the first entry other than the parent-navigation row."""
        for item_id in tree.get_children(""):
            values = tree.item(item_id, "values")
            if isinstance(values, (tuple, list)) and values and values[0] == "..":
                continue
            return item_id
        return None

    def _on_backspace(self, event: tk.Event | None = None) -> str:
        """Navigate to the parent directory of the last selected panel."""
        widget = getattr(event, "widget", None)
        if widget is not None and widget is getattr(self, "remote_tree", None):
            self._remember_panel("remote")
        elif widget is not None and widget is getattr(self, "local_tree", None):
            self._remember_panel("local")

        if self.last_selected_panel == "remote":
            self.navigate_remote_parent()
        else:
            self.navigate_local_parent()
        return "break"

    def _on_delete_key(self, event: tk.Event | None = None) -> str:
        """Delete all selected entries in the last selected panel."""
        if self._controls_locked():
            return "break"
        widget = getattr(event, "widget", None)
        if widget is self.remote_tree:
            self._remember_panel("remote")
        elif widget is self.local_tree:
            self._remember_panel("local")
        if self.last_selected_panel == "remote":
            self.delete_selected_remote_entries()
        else:
            self.delete_selected_local_entries()
        return "break"

    def _on_rename_key(self, event: tk.Event | None = None) -> str:
        """Start in-place rename for exactly one currently selected entry."""
        if self._controls_locked():
            return "break"
        widget = getattr(event, "widget", None)
        if widget is getattr(self, "remote_tree", None) and widget is not None:
            self._remember_panel("remote")
        elif widget is getattr(self, "local_tree", None) and widget is not None:
            self._remember_panel("local")

        panel = self.last_selected_panel
        tree = self.remote_tree if panel == "remote" else self.local_tree
        selected_items = tuple(tree.selection())
        if len(selected_items) != 1:
            return "break"
        item_id = selected_items[0]
        self.last_selected_items[panel] = item_id
        entries = self.remote_entries if panel == "remote" else self.local_entries
        entry = self._entry_from_tree(entries, item_id or "")
        if entry is None or entry.name == "..":
            return "break"
        self._start_inline_rename(panel, item_id or "", entry)
        return "break"

    def _start_inline_rename(
        self,
        panel: str,
        item_id: str,
        entry: FlightControllerLogFile | LocalFileEntry,
    ) -> None:
        """Create an inline name editor, falling back to a dialog if needed."""
        tree = self.remote_tree if panel == "remote" else self.local_tree
        self._panel_navigation_enabled = False
        try:
            bounds = tree.bbox(item_id, "name")
            if len(bounds) != 4:
                msg = "The selected row is not visible"
                raise tk.TclError(msg)
            x, y, width, height = (int(value) for value in bounds)
            if width <= 0 or height <= 0:
                msg = "The selected row is not visible"
                raise tk.TclError(msg)
            editor = ttk.Entry(tree)
            editor.insert(0, entry.name)
            editor.select_range(0, tk.END)
            editor.place(x=x, y=y, width=width, height=height)
            editor.focus_set()
            editor.bind(
                "<Return>",
                lambda _event: self._finish_inline_rename(panel, entry, editor),
            )
            editor.bind("<Escape>", lambda _event: self._cancel_inline_rename(editor))
            editor.bind("<FocusOut>", lambda _event: self._finish_inline_rename(panel, entry, editor))
        except (AttributeError, tk.TclError, TypeError, ValueError):
            self._rename_entry_with_dialog(panel, entry)

    def _finish_inline_rename(
        self,
        panel: str,
        entry: FlightControllerLogFile | LocalFileEntry,
        editor: ttk.Entry,
    ) -> str:
        """Commit an inline rename and refresh the affected panel."""
        try:
            new_name = editor.get()
            editor.destroy()
            if not self._safe_name(new_name):
                self.ui.show_error(_("Rename error"), _("The new name must be one file or directory name."))
                return "break"
            if new_name == entry.name:
                return "break"
            self._rename_entry(panel, entry, new_name)
            return "break"
        finally:
            self._panel_navigation_enabled = True

    def _cancel_inline_rename(self, editor: ttk.Entry) -> str:
        """Cancel an inline rename editor."""
        try:
            editor.destroy()
            return "break"
        finally:
            self._panel_navigation_enabled = True

    def _rename_entry_with_dialog(self, panel: str, entry: FlightControllerLogFile | LocalFileEntry) -> None:
        """Prompt for a new name when inline editing cannot be created."""
        try:
            new_name = self.ui.askstring(
                _("Rename remote entry") if panel == "remote" else _("Rename local entry"),
                _("New name:"),
                initialvalue=entry.name,
                parent=self.root,
            )
            if new_name is not None and self._safe_name(new_name):
                self._rename_entry(panel, entry, new_name)
            elif new_name is not None:
                self.ui.show_error(_("Rename error"), _("The new name must be one file or directory name."))
        finally:
            self._panel_navigation_enabled = True

    def _rename_entry(self, panel: str, entry: FlightControllerLogFile | LocalFileEntry, new_name: str) -> bool:
        """Rename one remote or local entry and refresh its panel."""
        if panel == "remote" and isinstance(entry, FlightControllerLogFile):
            return self._rename_remote_entry(entry, new_name)
        if panel == "local" and isinstance(entry, LocalFileEntry):
            return self._rename_local_entry(entry, new_name)
        return False

    def _rename_remote_entry(self, entry: FlightControllerLogFile, new_name: str) -> bool:
        """Rename one remote entry."""
        new_path = posixpath.join(posixpath.dirname(entry.remote_path.rstrip("/")), new_name)
        if self._controls_locked():
            return False
        outcome: list[bool] = []
        rename_remote_path = self.parameter_editor.rename_remote_path

        def worker(_report_progress: Callable[[int, int], None]) -> tuple[list[str], list[str]]:
            return _rename_remote_entry_worker(entry, new_path, rename_remote_path)

        def completion(succeeded: list[str], _failed: list[str]) -> None:
            outcome.append(bool(succeeded))
            if succeeded:
                self.ui.show_info(
                    _("Rename summary"),
                    _("Renamed %(old)s to %(new)s.") % {"old": entry.name, "new": new_name},
                )
                self.refresh_remote_panel()
            else:
                self.ui.show_error(_("Rename error"), _("Could not rename the remote entry."))

        self._start_background_operation(
            _("Renaming remote entry"),
            _("Renaming remote entry"),
            worker,
            completion,
        )
        # Unit tests use a synchronous no-Tk seam; a real window reports the
        # result asynchronously after the operation has been scheduled.
        return outcome[0] if outcome else True

    def _rename_local_entry(self, entry: LocalFileEntry, new_name: str) -> bool:
        """Rename one local entry."""
        if self._controls_locked():
            return False
        target = entry.path.with_name(new_name)
        if target.exists():
            self.ui.show_error(_("Rename error"), _("The target name already exists."))
            return False
        try:
            entry.path.rename(target)
        except OSError as error:
            self.ui.show_error(_("Rename error"), str(error))
            return False
        self.ui.show_info(
            _("Rename summary"),
            _("Renamed %(old)s to %(new)s.") % {"old": entry.name, "new": new_name},
        )
        self.refresh_local_panel()
        return True

    def _on_select_all_key(self, _event: tk.Event | None = None) -> str:
        """Select all entries in the focused panel, except parent navigation."""
        tree = getattr(_event, "widget", None)
        if tree not in {self.remote_tree, self.local_tree}:
            tree = self.remote_tree
        self._select_all_tree_entries(tree)
        return "break"

    @staticmethod
    def _select_all_tree_entries(tree: ttk.Treeview) -> None:
        """Select all visible entries except the parent-navigation row."""
        selectable_items = []
        for item_id in tree.get_children():
            values = tree.item(item_id, "values")
            if not isinstance(values, (tuple, list)) or not values or values[0] != "..":
                selectable_items.append(item_id)
        tree.selection_set(selectable_items)

    def select_all_remote_entries(self) -> None:
        """Select all remote entries except the parent-navigation row."""
        self._select_all_tree_entries(self.remote_tree)

    def select_all_local_entries(self) -> None:
        """Select all local entries except the parent-navigation row."""
        if hasattr(self, "local_tree"):
            self._select_all_tree_entries(self.local_tree)

    def _on_remote_double_click(self, event: tk.Event) -> None:
        """Open a remote directory on double click."""
        item_id = self.remote_tree.identify_row(event.y)
        if not item_id:
            return
        entry = self._entry_from_tree(self.remote_entries, item_id)
        if isinstance(entry, FlightControllerLogFile) and entry.is_directory:
            self.remote_directory_var.set(entry.remote_path)
            self.refresh_remote_panel()

    def _on_local_double_click(self, event: tk.Event) -> None:
        """Open the local directory or file under the pointer."""
        item_id = self.local_tree.identify_row(event.y)
        if not item_id:
            return
        entry = self._entry_from_tree(self.local_entries, item_id)
        if not isinstance(entry, LocalFileEntry) or self._controls_locked():
            return
        if entry.is_directory:
            self.local_directory_var.set(str(entry.path))
            self.refresh_local_panel()
        else:
            self._open_local_file(entry)

    def _show_context_menu(self, event: tk.Event, remote: bool) -> str:
        """Display the context menu for the panel that received a right click."""
        panel = "remote" if remote else "local"
        tree = self.remote_tree if remote else self.local_tree
        item_id = tree.identify_row(event.y)
        if item_id:
            if item_id not in tree.selection():
                tree.selection_set(item_id)
            tree.focus(item_id)
            self.last_selected_items[panel] = item_id
        self._remember_panel(panel)
        self._update_transfer_buttons()

        menu = tk.Menu(tree, tearoff=False)
        can_open = False
        if not remote:
            selected_entries = self._selected_local_entries()
            can_open = len(selected_entries) == 1 and not selected_entries[0].is_directory
        menu.add_command(
            label=_("New directory"),
            command=self.create_new_remote_directory if remote else self.create_new_local_directory,
        )
        if not remote:
            menu.add_command(
                label=_("Open"),
                command=self.open_selected_local_file,
                state="normal" if can_open else "disabled",
            )
        menu_closed = False

        def close_menu(_event: tk.Event | None = None) -> None:
            """Release and destroy the menu after Tk has unmapped it."""
            nonlocal menu_closed
            if menu_closed:
                return
            menu_closed = True
            try:
                menu.grab_release()
            finally:
                menu.destroy()

        def defer_close(_event: tk.Event | None = None) -> None:
            menu.after_idle(close_menu)

        menu.bind("<Unmap>", defer_close, add="+")
        try:
            menu.tk_popup(event.x_root, event.y_root)
        except tk.TclError:
            close_menu()
            raise
        finally:
            if not menu_closed:
                menu.grab_release()
        return "break"

    def open_selected_local_file(self) -> None:
        """Open one selected local file with the operating system's default application."""
        selected_entries = self._selected_local_entries()
        if len(selected_entries) != 1:
            return
        self._open_local_file(selected_entries[0])

    def _open_local_file(self, entry: LocalFileEntry) -> None:
        """Open one local file, regardless of how the UI selected it."""
        if self._controls_locked() or entry.is_directory:
            return
        path = entry.path
        try:
            if sys.platform == "win32":
                os.startfile(str(path))  # noqa: S606
            else:
                opener = "open" if sys.platform == "darwin" else "xdg-open"
                subprocess.Popen([opener, str(path.resolve())], start_new_session=True)  # noqa: S603  # pylint: disable=consider-using-with
        except OSError as error:
            self.ui.show_error(_("Open file error"), str(error))

    @staticmethod
    def _entry_from_tree(
        entries: Sequence[FlightControllerLogFile | LocalFileEntry],
        item_id: str,
    ) -> FlightControllerLogFile | LocalFileEntry | None:
        """Resolve a stable Treeview item id to its application entry."""
        if not str(item_id).isdigit():
            return None
        index = int(item_id)
        return entries[index] if 0 <= index < len(entries) else None

    def _selected_remote_entries(self) -> list[FlightControllerLogFile]:
        """Return selected remote entries, including directories."""
        selected: list[FlightControllerLogFile] = []
        for item_id in self.remote_tree.selection():
            entry = self._entry_from_tree(self.remote_entries, item_id)
            if isinstance(entry, FlightControllerLogFile):
                selected.append(entry)
        return selected

    def _selected_local_entries(self) -> list[LocalFileEntry]:
        """Return selected local entries, including directories."""
        selected: list[LocalFileEntry] = []
        for item_id in self.local_tree.selection():
            entry = self._entry_from_tree(self.local_entries, item_id)
            if isinstance(entry, LocalFileEntry):
                selected.append(entry)
        return selected

    @staticmethod
    def _safe_name(name: str) -> bool:
        """Return whether a user-provided rename is one safe path component."""
        return is_safe_local_entry_name(name)

    @staticmethod
    def _set_widget_state(widget: ttk.Widget, state: str) -> None:
        """Set a widget's enabled state using the API it supports."""
        widget.state(["disabled"] if state == "disabled" else ["!disabled"])

    def _set_remote_controls_state(self, state: str) -> None:
        """Enable or disable controls that issue remote operations."""
        for name in (
            "remote_directory_entry",
            "remote_parent_button",
            "remote_tree",
        ):
            widget = getattr(self, name, None)
            if widget is not None:
                self._set_widget_state(widget, state)

    def _set_operation_controls_state(self, state: str) -> None:
        """Enable or disable all browser controls during a remote operation."""
        self._set_remote_controls_state(state)
        for name in (
            "local_directory_entry",
            "local_parent_button",
            "local_tree",
            "download_button",
            "upload_button",
            "last_log_button",
            "verify_checkbox",
        ):
            widget = getattr(self, name, None)
            if widget is not None:
                self._set_widget_state(widget, state)

    def _start_task(
        self,
        task: Callable[[Callable[[int, int], None]], object],
        on_progress: Callable[[int, int], None] | None,
        on_done: Callable[[object | None, Exception | None], None],
        *,
        disable_all_controls: bool,
    ) -> bool:
        """Keep browser controls locked for the lifetime of one background task."""
        if self._controls_locked():
            return False

        def set_controls(state: str) -> None:
            if disable_all_controls:
                self._set_operation_controls_state(state)
            else:
                self._set_remote_controls_state(state)
            if getattr(self, "close_button", None) is not None:
                self.close_button.configure(state=state)

        set_controls("disabled")

        def done(result: object | None, error: Exception | None) -> None:
            set_controls("normal")
            self._update_parent_navigation_buttons()
            self._update_transfer_buttons()
            on_done(result, error)

        try:
            started = self._task_runner.start(task, on_progress, done)
        except Exception:
            set_controls("normal")
            raise
        if not started:
            set_controls("normal")
        return started

    def _start_remote_task(
        self,
        task: Callable[[], object],
        completion: Callable[[object, Exception | None], None],
        *,
        disable_all_controls: bool = False,
    ) -> bool:
        """Run blocking remote listing/planning work away from Tk's event loop."""
        return self._start_task(
            lambda _progress: task(),
            None,
            completion,
            disable_all_controls=disable_all_controls,
        )

    def _progress_window(self, title: str, message: str) -> ProgressWindow:
        """Create a standard application progress window."""
        root = cast("tk.Misc", getattr(self, "root", None))
        return self.ui.create_progress_window(root, title, message, False)  # noqa: FBT003

    def _on_close(self) -> None:
        """Close only when no background operation is using the window."""
        if self._controls_locked():
            self.ui.show_error(
                _("Transfer error"),
                _("Another file operation is already in progress."),
            )
            return
        self.root.destroy()
        if self._closed_callback is not None:
            self._closed_callback()

    def run(self) -> None:
        """Start the standalone browser event loop."""
        self.root.mainloop()

    def _start_background_operation(
        self,
        title: str,
        message: str,
        worker: Callable[[Callable[[int, int], None]], tuple[list[str], list[str]]],
        completion: Callable[[list[str], list[str]], None],
    ) -> bool:
        """Run one blocking MAVFTP operation away from Tk's event loop."""
        if self._controls_locked():
            self.ui.show_error(
                _("Transfer error"),
                _("Another file operation is already in progress."),
            )
            return False
        progress = self._progress_window(title, message)

        def done(result: object | None, error: Exception | None) -> None:
            progress.destroy()
            if error is not None:
                completion([], [str(error)])
            else:
                succeeded, failed = cast("tuple[list[str], list[str]]", result)
                completion(succeeded, failed)

        try:
            started = self._start_task(
                worker,
                progress.update_progress_bar,
                done,
                disable_all_controls=True,
            )
        except Exception:
            progress.destroy()
            raise
        if not started:
            progress.destroy()
            self.ui.show_error(
                _("Transfer error"),
                _("Another file operation is already in progress."),
            )
            return False
        return True

    def _show_summary(
        self,
        title: str,
        succeeded: list[str],
        failed: list[str],
        verification: dict[str, bool | None] | None = None,
    ) -> None:
        """Show a compact per-entry operation summary."""
        verification = verification or {}
        failure_lines = [
            (_("Not verified: %s") if verification.get(name) is False else _("Failed: %s")) % name for name in failed
        ]
        success_lines = [
            (
                _("Verified: %s")
                if verification.get(name) is True
                else _("Not verified: %s")
                if name in verification
                else _("Succeeded: %s")
            )
            % name
            for name in succeeded
        ]
        if len(failure_lines) >= self.MAX_SUMMARY_ENTRIES:
            lines = failure_lines[: self.MAX_SUMMARY_ENTRIES]
        else:
            success_limit = self.MAX_SUMMARY_ENTRIES - len(failure_lines)
            lines = success_lines[:success_limit] + failure_lines
        hidden_count = len(succeeded) + len(failed) - len(lines)
        if hidden_count > 0:
            lines.append(_("… %s more entries omitted.") % hidden_count)
        (self.ui.show_error if failed else self.ui.show_info)(title, "\n".join(lines) or _("No entries processed."))

    # Keep the summary and retry dependencies explicit rather than adding a one-use options object.
    def _complete_transfer_batch(  # pylint: disable=too-many-arguments
        self,
        results: TransferBatchResults,
        succeeded: list[str],
        failed: list[str],
        *,
        summary_title: str,
        refresh: Callable[[], None],
        retry_prompt: tuple[str, str],
        retry_action: Callable[[], None] | None,
    ) -> None:
        """Show this batch's cumulative outcome and offer its one optional retry."""
        results.record(succeeded, failed)
        self._show_summary(summary_title, results.succeeded, results.failed, results.verification)
        if retry_action is not None and self.ui.ask_yesno(*retry_prompt) is True:
            retry_action()
        refresh()

    def download_selected_remote_entries(self) -> None:
        """Recursively download selected remote entries into the local panel directory."""
        if self._controls_locked():
            return
        selected = [entry for entry in self._selected_remote_entries() if entry.name != ".."]
        if not selected:
            return
        local_directory = Path(self.local_directory_var.get()).expanduser()
        if not local_directory.is_dir():
            self.ui.show_error(_("Download error"), _("The selected local directory does not exist."))
            return

        def complete_plan(result: object, error: Exception | None) -> None:
            if error is not None:
                self.ui.show_error(_("Download error"), str(error))
                return
            if not isinstance(result, RemoteDownloadPreflight):
                self.ui.show_error(_("Download error"), _("Could not prepare the selected remote entries."))
                return
            plan = result.plan
            duplicate_targets = result.duplicate_targets
            existing_conflicts = result.existing_conflicts
            if duplicate_targets:
                names = "\n".join(str(path) for path in duplicate_targets)
                self.ui.show_error(
                    _("Download error"),
                    _("Several selected entries map to the same local target:\n\n%s") % names,
                )
                return
            if existing_conflicts and not self.ui.ask_yesno(
                _("Overwrite existing local entries?"),
                _("Some local entries already exist. Overwrite them?"),
            ):
                return
            if not plan.directories and not plan.files:
                self._show_summary(_("Download summary"), [], list(plan.failed))
                return
            download_remote_file = self.parameter_editor.download_remote_file
            verify_remote_file = self.parameter_editor.verify_remote_file if self.verify_transfers_var.get() else None
            results = TransferBatchResults()

            def run_batch(
                batch: RemoteDownloadPlan,
                *,
                allow_retry: bool,
            ) -> None:
                total = max(sum(max(entry.size_bytes, 1) for entry, _path in batch.files), 1)
                results.prepare([entry.remote_path for entry, _target in batch.files])

                def worker(report_progress: Callable[[int, int], None]) -> tuple[list[str], list[str]]:
                    return _download_remote_plan_worker(
                        batch,
                        local_directory,
                        total,
                        download_remote_file,
                        report_progress,
                        verify_remote_file=verify_remote_file,
                        verification_results=results.verification,
                    )

                def completion(succeeded: list[str], worker_failed: list[str]) -> None:
                    retry_plan = _retry_remote_download_plan(batch, worker_failed) if allow_retry else None
                    self._complete_transfer_batch(
                        results,
                        succeeded,
                        worker_failed,
                        summary_title=_("Download summary"),
                        refresh=self.refresh_local_panel,
                        retry_prompt=(_("Retry failed downloads?"), _("Retry only the failed file downloads?")),
                        retry_action=(lambda: run_batch(retry_plan, allow_retry=False))
                        if retry_plan is not None and retry_plan.files
                        else None,
                    )

                self._start_background_operation(
                    _("Downloading selected entries"),
                    _("Downloaded {} of {} bytes"),
                    worker,
                    completion,
                )

            run_batch(plan, allow_retry=True)

        get_remote_files = self.parameter_editor.get_remote_files
        self._start_remote_task(
            lambda: _prepare_remote_download(selected, local_directory, get_remote_files),
            complete_plan,
        )

    def upload_selected_local_entries(self) -> None:
        """Recursively upload selected local entries to the remote panel directory."""
        if self._controls_locked():
            return
        selected = [entry for entry in self._selected_local_entries() if entry.name != ".."]
        if not selected:
            return
        remote_directory = self.remote_directory_var.get().rstrip("/") or "/"
        if not self._safe_remote_directory(remote_directory):
            self.ui.show_error(_("Upload error"), _("The remote destination must be an absolute directory path."))
            return
        if not self.ui.ask_yesno(
            _("Upload selected entries?"),
            _("Uploading may overwrite remote files. Continue?"),
        ):
            return

        def complete_plan(result: object, error: Exception | None) -> None:
            if error is not None:
                self.ui.show_error(_("Upload error"), str(error))
                return
            if not isinstance(result, LocalUploadPlan):
                self.ui.show_error(_("Upload error"), _("Could not prepare the selected local entries."))
                return
            if not result.directories and not result.files:
                self._show_summary(_("Upload summary"), [], list(result.failed))
                return
            make_remote_directory = self.parameter_editor.make_remote_directory
            upload_file_to_fc = self.parameter_editor.upload_file_to_fc
            verify_remote_file = self.parameter_editor.verify_remote_file if self.verify_transfers_var.get() else None
            results = TransferBatchResults()

            def run_batch(
                batch: LocalUploadPlan,
                *,
                allow_retry: bool,
            ) -> None:
                total = max(sum(max(size, 1) for _path, _remote, size in batch.files), 1)
                results.prepare([remote_path for _path, remote_path, _size in batch.files])

                def worker(report_progress: Callable[[int, int], None]) -> tuple[list[str], list[str]]:
                    return _upload_local_plan_worker(
                        batch,
                        total,
                        make_remote_directory,
                        upload_file_to_fc,
                        report_progress,
                        verify_remote_file=verify_remote_file,
                        verification_results=results.verification,
                    )

                def completion(succeeded: list[str], failed: list[str]) -> None:
                    retry_plan = _retry_local_upload_plan(batch, failed) if allow_retry else None
                    self._complete_transfer_batch(
                        results,
                        succeeded,
                        failed,
                        summary_title=_("Upload summary"),
                        refresh=self.refresh_remote_panel,
                        retry_prompt=(_("Retry failed uploads?"), _("Retry only the failed file uploads?")),
                        retry_action=(lambda: run_batch(retry_plan, allow_retry=False))
                        if retry_plan is not None and retry_plan.files
                        else None,
                    )

                self._start_background_operation(
                    _("Uploading selected entries"),
                    _("Uploaded {} of {} bytes"),
                    worker,
                    completion,
                )

            run_batch(result, allow_retry=True)

        self._start_remote_task(
            lambda: _build_local_upload_plan(selected, remote_directory),
            complete_plan,
            disable_all_controls=True,
        )

    def delete_selected_remote_entries(self) -> None:
        """Delete selected remote files and empty directories after confirmation."""
        if self._controls_locked():
            return
        selected = [entry for entry in self._selected_remote_entries() if entry.name != ".."]
        if not selected or not self.ui.ask_yesno(
            _("Delete remote entries?"),
            _("Delete selected files and empty directories?"),
        ):
            return

        get_remote_files = self.parameter_editor.get_remote_files
        delete_remote_path = self.parameter_editor.delete_remote_path

        def worker(_report_progress: Callable[[int, int], None]) -> tuple[list[str], list[str]]:
            return _delete_remote_entries_worker(selected, get_remote_files, delete_remote_path)

        def completion(succeeded: list[str], failed: list[str]) -> None:
            self._show_summary(_("Remote delete summary"), succeeded, failed)
            self.refresh_remote_panel()

        self._start_background_operation(
            _("Deleting remote entries"),
            _("Deleted selected remote entries"),
            worker,
            completion,
        )

    def delete_selected_local_entries(self) -> None:
        """Delete selected local files and empty directories after confirmation."""
        if self._controls_locked():
            return
        selected = [entry for entry in self._selected_local_entries() if entry.name != ".."]
        if not selected or not self.ui.ask_yesno(
            _("Delete local entries?"),
            _("Delete selected files and empty directories?"),
        ):
            return
        succeeded: list[str] = []
        failed: list[str] = []
        for entry in selected:
            if self._delete_local_entry(entry):
                succeeded.append(str(entry.path))
            else:
                failed.append(str(entry.path))
        self._show_summary(_("Local delete summary"), succeeded, failed)
        self.refresh_local_panel()

    def create_new_remote_directory(self) -> None:
        """Prompt for and create a directory in the displayed remote directory."""
        if self._controls_locked():
            return
        new_name = self.ui.askstring(_("New remote directory"), _("Directory name:"), parent=self.root)
        if new_name is None:
            return
        if not self._safe_name(new_name):
            self.ui.show_error(_("New directory error"), _("The directory name must be a single directory name."))
            return
        remote_directory = self.remote_directory_var.get().rstrip("/") or "/"
        if not self._safe_remote_directory(remote_directory):
            self.ui.show_error(_("New directory error"), _("The remote destination must be an absolute directory path."))
            return
        new_path = posixpath.join(remote_directory, new_name)
        make_remote_directory = self.parameter_editor.make_remote_directory

        def worker(_report_progress: Callable[[int, int], None]) -> tuple[list[str], list[str]]:
            return _create_remote_directory_worker(new_path, make_remote_directory)

        def completion(succeeded: list[str], _failed: list[str]) -> None:
            if succeeded:
                self.ui.show_info(_("New directory summary"), _("Created remote directory %(name)s.") % {"name": new_name})
                self._select_entry_after_refresh("remote", new_name)
                self.refresh_remote_panel()
            else:
                self.ui.show_error(_("New directory error"), _("Could not create the remote directory."))

        self._start_background_operation(
            _("Creating remote directory"),
            _("Creating remote directory"),
            worker,
            completion,
        )

    def create_new_local_directory(self) -> None:
        """Prompt for and create a directory in the displayed local directory."""
        if self._controls_locked():
            return
        new_name = self.ui.askstring(_("New local directory"), _("Directory name:"), parent=self.root)
        if new_name is None:
            return
        if not self._safe_name(new_name):
            self.ui.show_error(_("New directory error"), _("The directory name must be a single directory name."))
            return
        local_directory = Path(self.local_directory_var.get()).expanduser()
        if not local_directory.is_dir():
            self.ui.show_error(_("New directory error"), _("The selected local directory does not exist."))
            return
        target = local_directory / new_name
        if target.exists():
            self.ui.show_error(_("New directory error"), _("The target name already exists."))
            return
        try:
            target.mkdir()
        except OSError as error:
            self.ui.show_error(_("New directory error"), str(error))
            return
        self.ui.show_info(_("New directory summary"), _("Created local directory %(name)s.") % {"name": new_name})
        self._select_entry_after_refresh("local", new_name)
        self.refresh_local_panel()

    def rename_selected_remote_entry(self) -> None:
        """Rename one selected remote entry."""
        if self._controls_locked():
            return
        selected = [entry for entry in self._selected_remote_entries() if entry.name != ".."]
        if len(selected) != 1:
            self.ui.show_error(_("Rename error"), _("Select exactly one remote entry to rename."))
            return
        entry = selected[0]
        self._panel_navigation_enabled = False
        try:
            new_name = self.ui.askstring(_("Rename remote entry"), _("New name:"), initialvalue=entry.name, parent=self.root)
            if new_name is None:
                return
            if not self._safe_name(new_name):
                self.ui.show_error(_("Rename error"), _("The new name must be one file or directory name."))
                return
            self._rename_remote_entry(entry, new_name)
        finally:
            self._panel_navigation_enabled = True

    def rename_selected_local_entry(self) -> None:
        """Rename one selected local entry."""
        if self._controls_locked():
            return
        selected = [entry for entry in self._selected_local_entries() if entry.name != ".."]
        if len(selected) != 1:
            self.ui.show_error(_("Rename error"), _("Select exactly one local entry to rename."))
            return
        entry = selected[0]
        self._panel_navigation_enabled = False
        try:
            new_name = self.ui.askstring(_("Rename local entry"), _("New name:"), initialvalue=entry.name, parent=self.root)
            if new_name is None:
                return
            if not self._safe_name(new_name):
                self.ui.show_error(_("Rename error"), _("The new name must be one file or directory name."))
                return
            target = entry.path.with_name(new_name)
            if target.exists():
                self.ui.show_error(_("Rename error"), _("The target name already exists."))
                return
            try:
                entry.path.rename(target)
            except OSError as error:
                self.ui.show_error(_("Rename error"), str(error))
                return
            self.ui.show_info(_("Rename summary"), _("Renamed %(old)s to %(new)s.") % {"old": entry.name, "new": new_name})
            self.refresh_local_panel()
        finally:
            self._panel_navigation_enabled = True

    @staticmethod
    def _delete_local_entry(entry: LocalFileEntry) -> bool:
        """Delete one local entry and return whether it succeeded."""
        try:
            if entry.is_directory:
                entry.path.rmdir()
            else:
                entry.path.unlink()
        except OSError:
            return False
        return True

    def _update_transfer_buttons(self) -> None:
        """Enable each transfer button only when its panel has selectable entries."""
        if self._controls_locked():
            return
        download_button = getattr(self, "download_button", None)
        if download_button is not None:
            selected_remote = [entry for entry in self._selected_remote_entries() if entry.name != ".."]
            download_button.configure(state="normal" if selected_remote else "disabled")
        upload_button = getattr(self, "upload_button", None)
        if upload_button is not None and hasattr(self, "local_tree"):
            selected_local = [entry for entry in self._selected_local_entries() if entry.name != ".."]
            upload_button.configure(state="normal" if selected_local else "disabled")

    @staticmethod
    def _safe_remote_directory(directory: str) -> bool:
        """Return whether a remote destination is an absolute directory path."""
        return bool(directory) and directory.startswith("/") and ".." not in directory.split("/")

    def download_last_flight_log(self) -> None:
        """Download the last flight log without blocking the Tk event loop."""
        if self._controls_locked():
            return
        if not self.parameter_editor.is_fc_link_connected:
            self.ui.show_error(_("Error"), _("No flight controller connected"))
            return
        if not self.parameter_editor.is_mavftp_supported:
            self.ui.show_error(_("Error"), _("MAVFTP is not supported by the flight controller"))
            return
        filename = self.ui.asksaveasfilename(
            title=_("Save flight log as"),
            defaultextension=".bin",
            filetypes=[(_("Binary log files"), "*.bin"), (_("All files"), "*.*")],
        )
        if not filename:
            return
        download_last_flight_log = self.parameter_editor.download_last_flight_log
        outcome = LastLogDownloadResult.FAILED

        def worker(report_progress: Callable[[int, int], None]) -> tuple[list[str], list[str]]:
            nonlocal outcome
            outcome = _download_last_flight_log_worker(filename, download_last_flight_log, report_progress)
            return ([filename], []) if outcome is LastLogDownloadResult.SUCCESS else ([], [filename])

        def completion(succeeded: list[str], failed: list[str]) -> None:
            if failed:
                self.ui.show_error(
                    _("Download error"),
                    (
                        _("No flight logs found on the flight controller.")
                        if outcome is LastLogDownloadResult.NO_LOGS
                        else _("Could not download the flight log; check the console for details.")
                    ),
                )
            else:
                self._show_summary(_("Download summary"), succeeded, failed)
                self.refresh_local_panel()

        self._start_background_operation(
            _("Downloading Flight Log"),
            _("Downloaded {}% from {}%"),
            worker,
            completion,
        )


def argument_parser() -> Namespace:  # pragma: no cover
    """Parse arguments for running the MAVFTP browser as a standalone window."""
    parser = ArgumentParser(description=_("Browse and transfer files on an ArduPilot flight controller."))
    parser = FlightController.add_argparse_arguments(parser)
    parser = LocalFilesystem.add_argparse_arguments(parser)
    return add_common_arguments(parser).parse_args()


def _standalone_ui_services() -> FileBrowserUiServices:  # pragma: no cover
    """Create the Tk-backed services required by the standalone browser."""

    def create_progress_window(
        parent: tk.Misc,
        title: str,
        message: str,
        only_show_when_update_called: bool,
    ) -> ProgressWindow:
        return ProgressWindow(
            parent,
            title,
            message,
            only_show_when_update_progress_called=only_show_when_update_called,
        )

    return cast(
        "FileBrowserUiServices",
        type(
            "StandaloneUiServices",
            (),
            {
                "asksaveasfilename": staticmethod(filedialog.asksaveasfilename),
                "askdirectory": staticmethod(filedialog.askdirectory),
                "askstring": staticmethod(simpledialog.askstring),
                "ask_yesno": staticmethod(ask_yesno_popup),
                "show_error": staticmethod(show_error_popup),
                "show_info": staticmethod(show_info_popup),
                "create_progress_window": staticmethod(create_progress_window),
            },
        )(),
    )


def main() -> None:  # pragma: no cover
    """Open the MAVFTP browser as a standalone window."""
    args = argument_parser()
    logging_basicConfig(level=logging_getLevelName(args.loglevel), format="%(asctime)s - %(levelname)s - %(message)s")

    # pylint: disable=duplicate-code
    flight_controller = FlightController(reboot_time=args.reboot_time, baudrate=args.baudrate)
    filesystem = LocalFilesystem(
        args.vehicle_dir,
        args.vehicle_type,
        "",
        args.allow_editing_template_files,
        args.save_component_to_system_templates,
    )
    # pylint: enable=duplicate-code
    parameter_editor = ParameterEditor("", flight_controller, filesystem)
    connection_error = flight_controller.connect(args.device)
    if connection_error:
        show_error_popup(_("Flight-controller connection error"), connection_error)
        return

    window = FileBrowserWindow(None, parameter_editor, _standalone_ui_services())
    window.run()


if __name__ == "__main__":  # pragma: no cover
    main()
