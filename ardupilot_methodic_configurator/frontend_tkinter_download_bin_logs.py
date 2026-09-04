# pylint: disable=too-many-lines
"""
Modal two-panel MAVFTP/local-file browser.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

from __future__ import annotations

import posixpath
import queue
import sys
import tkinter as tk
from dataclasses import dataclass
from pathlib import Path
from threading import Event, Thread
from tkinter import ttk
from typing import TYPE_CHECKING, Literal, Protocol, cast

from ardupilot_methodic_configurator import _
from ardupilot_methodic_configurator.backend_flightcontroller_files import FlightControllerLogFile
from ardupilot_methodic_configurator.formatting import format_filesize
from ardupilot_methodic_configurator.frontend_tkinter_base_window import BaseWindow
from ardupilot_methodic_configurator.frontend_tkinter_show import show_tooltip

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

    from ardupilot_methodic_configurator.data_model_parameter_editor import ParameterEditor
    from ardupilot_methodic_configurator.frontend_tkinter_progress_window import ProgressWindow


class DownloadBinLogsUiServices(Protocol):  # pylint: disable=too-few-public-methods
    """UI callbacks required by the two-panel file browser."""

    asksaveasfilename: Callable[..., str]
    askdirectory: Callable[..., str]
    askstring: Callable[..., str | None]
    ask_yesno: Callable[[str, str], bool]
    show_warning: Callable[[str, str], None]
    show_error: Callable[[str, str], None]
    show_info: Callable[[str, str], None]

    create_progress_window: Callable[[tk.Misc, str, str, bool], ProgressWindow]


@dataclass(frozen=True)
class LocalFileEntry:
    """A local file-system entry displayed in the local panel."""

    name: str
    path: Path
    size_bytes: int
    is_directory: bool = False


@dataclass(frozen=True)
class RemoteDownloadPlan:
    """Preflight plan for a recursive remote download."""

    directories: tuple[Path, ...]
    files: tuple[tuple[FlightControllerLogFile, Path], ...]
    failed: tuple[str, ...] = ()


class _TransferCancelledError(Exception):
    """Raised by a transfer progress callback when the user cancels."""


class DownloadBinLogsWindow(  # pylint: disable=attribute-defined-outside-init, too-many-instance-attributes
    BaseWindow
):
    """Browse remote and local files and transfer or manage selected entries."""

    DEFAULT_REMOTE_DIRECTORY = "/APM/LOGS/"
    sort_column: str
    download_button: ttk.Button
    empty_state_label: ttk.Label

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
        self.remote_entries: list[FlightControllerLogFile] = []
        self.remote_files: list[FlightControllerLogFile] = []  # Compatibility with the original file-only tests/API.
        self.local_entries: list[LocalFileEntry] = []
        self.remote_sort_column = ""
        self.local_sort_column = ""
        self.remote_sort_reverse = False
        self.local_sort_reverse = False
        self.last_selected_panel = "remote"
        self.last_selected_items: dict[str, str | None] = {"remote": None, "local": None}
        self._operation_queue: queue.Queue[tuple[str, object]] = queue.Queue()
        self._operation_thread: Thread | None = None
        self._operation_cancel_event: Event | None = None
        self._operation_progress: ProgressWindow | None = None
        self._operation_completion: Callable[[list[str], list[str], bool], None] | None = None
        self._operation_active = False
        self._remote_task_queue: queue.Queue[tuple[object, Exception | None]] = queue.Queue()
        self._remote_task_thread: Thread | None = None
        self._remote_task_completion: Callable[[object, Exception | None], None] | None = None
        self.remote_directory_var = tk.StringVar(master=self.root, value=self.DEFAULT_REMOTE_DIRECTORY)
        self.local_directory_var = tk.StringVar(
            master=self.root,
            value=self._default_local_directory(parameter_editor),
        )

        self.root.title(_("Download .bin log files"))
        self.root.geometry(self.calculate_scaled_geometry(1100, 620))
        self.center_window(self.root, parent)
        self.root.resizable(width=True, height=True)
        self.root.transient(parent)
        self.root.protocol("WM_DELETE_WINDOW", self._on_cancel_or_close)
        if sys.platform != "darwin":
            self.root.grab_set()

        self._build_widgets()
        self.refresh_remote_panel()
        self.refresh_local_panel()

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

        download_button = ttk.Button(
            action_frame,
            text=_("Download selected →"),
            command=self.download_selected_remote_entries,
        )
        download_button.pack(side=tk.LEFT)
        self.download_button = download_button
        show_tooltip(
            download_button, _("Download selected files and directories from the flight controller to the local computer")
        )

        upload_button = ttk.Button(
            action_frame,
            text=_("← Upload selected"),
            command=self.upload_selected_local_entries,
        )
        upload_button.pack(side=tk.LEFT, padx=(6, 0))
        self.upload_button = upload_button
        show_tooltip(
            upload_button, _("Upload selected files and directories from the local computer to the flight controller")
        )

        last_log_button = ttk.Button(
            action_frame,
            text=_("Download last .bin log file"),
            command=self.download_last_flight_log,
        )
        last_log_button.pack(side=tk.LEFT, padx=(14, 0))
        self.last_log_button = last_log_button
        show_tooltip(last_log_button, _("Download the last flight-controller .bin log file"))

        cancel_button = ttk.Button(action_frame, text=_("Cancel"), command=self._on_cancel_or_close)
        cancel_button.pack(side=tk.RIGHT)
        show_tooltip(cancel_button, _("Close the file browser"))
        self.cancel_button = cancel_button

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
        ttk.Label(selector, text=_("Remote destination:")).pack(side=tk.LEFT, padx=(0, 6))
        self.remote_directory_entry = ttk.Entry(selector, textvariable=self.remote_directory_var)
        self.remote_directory_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.remote_directory_entry.bind("<Return>", self._on_remote_directory_return)
        self.remote_parent_button = ttk.Button(
            selector,
            text="↖",
            width=3,
            command=self.navigate_remote_parent,
        )
        self.remote_parent_button.pack(side=tk.LEFT, padx=(6, 0))
        show_tooltip(self.remote_parent_button, _("Go to the parent directory on the flight controller"))

        open_remote_button = ttk.Button(selector, text=_("Open/Refresh"), command=self.refresh_remote_panel)
        open_remote_button.pack(side=tk.LEFT, padx=(6, 0))
        show_tooltip(open_remote_button, _("Open the remote directory and refresh its contents"))

        select_remote_button = ttk.Button(selector, text=_("Select all"), command=self.select_all_remote_entries)
        select_remote_button.pack(side=tk.LEFT, padx=(6, 0))
        show_tooltip(select_remote_button, _("Select all remote files and directories"))

        self.remote_directory_label = ttk.Label(parent, text="")
        self.remote_directory_label.pack(side=tk.TOP, anchor=tk.W, pady=(0, 4))
        self.remote_tree = self._create_tree(parent, remote=True)
        self.tree = self.remote_tree  # Compatibility alias retained for existing callers/tests.

    def _build_local_panel(self, parent: ttk.Frame) -> None:
        """Create the local directory selector and local Treeview."""
        selector = ttk.Frame(parent)
        selector.pack(side=tk.TOP, fill=tk.X, pady=(0, 4))
        ttk.Label(selector, text=_("Local directory:")).pack(side=tk.LEFT, padx=(0, 6))
        self.local_directory_entry = ttk.Entry(selector, textvariable=self.local_directory_var)
        self.local_directory_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.local_directory_entry.bind("<Return>", self._on_local_directory_return)
        self.local_parent_button = ttk.Button(
            selector,
            text="↖",
            width=3,
            command=self.navigate_local_parent,
        )
        self.local_parent_button.pack(side=tk.LEFT, padx=(6, 0))
        show_tooltip(self.local_parent_button, _("Go to the parent directory on the local computer"))

        browse_local_button = ttk.Button(selector, text=_("Browse"), command=self.choose_local_directory)
        browse_local_button.pack(side=tk.LEFT, padx=(6, 0))
        show_tooltip(browse_local_button, _("Choose a local directory"))

        refresh_local_button = ttk.Button(selector, text=_("Refresh"), command=self.refresh_local_panel)
        refresh_local_button.pack(side=tk.LEFT, padx=(6, 0))
        show_tooltip(refresh_local_button, _("Refresh the local directory contents"))

        select_local_button = ttk.Button(selector, text=_("Select all"), command=self.select_all_local_entries)
        select_local_button.pack(side=tk.LEFT, padx=(6, 0))
        show_tooltip(select_local_button, _("Select all local files and directories"))

        self.local_directory_label = ttk.Label(parent, text="")
        self.local_directory_label.pack(side=tk.TOP, anchor=tk.W, pady=(0, 4))
        self.local_tree = self._create_tree(parent, remote=False)

    def _create_tree(self, parent: ttk.Frame, *, remote: bool) -> ttk.Treeview:
        """Create one panel Treeview with sorting and navigation bindings."""
        tree = ttk.Treeview(
            parent,
            columns=("name", "type", "size"),
            show="headings",
            selectmode="extended",
        )
        sort_prefix = "remote" if remote else "local"
        columns: tuple[tuple[str, str, Literal["w", "e"], int], ...] = (
            ("name", _("Name"), "w", 180),
            ("type", _("Type"), "w", 90),
            ("size", _("Size"), "e", 90),
        )
        for column, title, anchor, width in columns:
            tree.heading(
                column,
                text=title,
                command=lambda col=column, prefix=sort_prefix: self._on_sort_heading(prefix, col),
            )
            tree.column(column, anchor=anchor, width=width, stretch=column == "name")
        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        tree.bind("<Double-1>", self._on_remote_double_click if remote else self._on_local_double_click)
        tree.bind("<Control-a>", self._on_select_all_key)
        tree.bind("<Command-a>", self._on_select_all_key)
        tree.bind("<Delete>", self._on_delete_key)
        tree.bind("<F2>", self._on_rename_key)
        tree.bind("<BackSpace>", self._on_backspace)
        tree.bind("<FocusIn>", lambda _event, panel=sort_prefix: self._remember_panel(panel))
        tree.bind("<ButtonRelease-1>", lambda event, panel=sort_prefix: self._remember_panel_from_click(panel, event))
        tree.bind("<<TreeviewSelect>>", lambda _event, panel=sort_prefix: self._remember_panel_from_selection(panel))
        scrollbar = ttk.Scrollbar(parent, orient=tk.VERTICAL, command=tree.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        tree.configure(yscrollcommand=scrollbar.set)
        return tree

    def refresh_remote_panel(self) -> None:
        """Refresh the remote panel, including directory entries."""
        if getattr(self, "_operation_active", False) or getattr(self, "_remote_task_thread", None) is not None:
            return
        remote_directory = self.remote_directory_var.get()
        if not remote_directory.strip():
            self.ui.show_error(_("Remote directory error"), _("The remote destination must not be empty."))
            return

        def complete(result: object, error: Exception | None) -> None:
            if error is not None:
                self.ui.show_error(_("Remote directory error"), str(error))
                return
            entries = cast("list[FlightControllerLogFile] | None", result)
            if entries is None:
                self.ui.show_error(_("Remote directory error"), _("Could not list the remote directory."))
                return
            self.remote_entries = entries
            self._populate_remote_tree()
            self._update_parent_navigation_buttons()
            self.remote_directory_label.configure(
                text=_("Remote files in {remote_directory}").format(remote_directory=remote_directory)
            )

        self.remote_directory_label.configure(text=_("Loading remote directory…"))
        self._start_remote_task(
            lambda: self.parameter_editor.get_remote_files(remote_directory),
            complete,
        )

    def refresh_remote_files(self) -> None:
        """Compatibility method that refreshes the original file-only listing."""
        if getattr(self, "_operation_active", False) or getattr(self, "_remote_task_thread", None) is not None:
            return
        remote_directory = self.remote_directory_var.get()
        if not remote_directory.strip():
            self.ui.show_error(_("Remote directory error"), _("The remote destination must not be empty."))
            return

        def complete(result: object, error: Exception | None) -> None:
            if error is not None:
                self.remote_files = []
                self.ui.show_error(_("Remote directory error"), str(error))
                return
            files = cast("list[FlightControllerLogFile] | None", result)
            if files is None:
                self.remote_files = []
                self.ui.show_error(_("Remote directory error"), _("Could not list the remote directory."))
                return
            self.remote_files = files
            self.remote_entries = list(self.remote_files)
            if hasattr(self, "remote_tree"):
                self._populate_remote_tree()
            else:
                self._populate_tree()
            self._update_parent_navigation_buttons()
            self.remote_directory_label.configure(
                text=_("Files in {remote_directory}").format(remote_directory=remote_directory)
            )

        self.remote_directory_label.configure(text=_("Loading remote directory…"))
        self._start_remote_task(
            lambda: self.parameter_editor.get_bin_log_files(remote_directory),
            complete,
        )

    def refresh_local_panel(self) -> None:
        """Refresh the local panel from the selected directory."""
        directory = Path(self.local_directory_var.get()).expanduser()
        if not directory.is_dir():
            self.ui.show_error(_("Local directory error"), _("The selected local directory does not exist."))
            return
        entries: list[LocalFileEntry] = []
        try:
            children = sorted(directory.iterdir(), key=lambda path: path.name.casefold())
            for child in children:
                if child.is_symlink():
                    continue
                try:
                    is_directory = child.is_dir()
                    size_bytes = 0 if is_directory else child.stat().st_size
                except OSError:
                    continue
                entries.append(LocalFileEntry(child.name, child, size_bytes, is_directory))
        except OSError as error:
            self.ui.show_error(_("Local directory error"), str(error))
            return
        self.local_entries = entries
        self._populate_local_tree()
        self._update_parent_navigation_buttons()
        self.local_directory_label.configure(text=_("Local files in {directory}").format(directory=directory))

    def _update_parent_navigation_buttons(self) -> None:
        """Enable parent buttons only when the corresponding panel has a parent."""
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
        remote_directory = self.remote_directory_var.get()
        without_trailing_slashes = remote_directory.rstrip("/")
        if not remote_directory.strip() or not without_trailing_slashes or without_trailing_slashes == "/":
            return
        self.remote_directory_var.set(posixpath.dirname(without_trailing_slashes) or "/")
        self.refresh_remote_panel()

    def navigate_local_parent(self) -> None:
        """Navigate the local panel to its parent directory."""
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
        self.last_selected_items["remote"] = None
        self.remote_sort_column = ""
        self._reset_tree_headings(self.remote_tree, "remote")
        for item_id in self.remote_tree.get_children():
            self.remote_tree.delete(item_id)
        for index, entry in enumerate(self.remote_entries):
            self.remote_tree.insert(
                "",
                tk.END,
                iid=str(index),
                values=(
                    entry.name,
                    _("Directory") if entry.is_directory else _("File"),
                    "" if entry.is_directory else format_filesize(entry.size_bytes),
                ),
            )
        self._update_empty_state(self.remote_entries, self.remote_directory_label)

    def _populate_local_tree(self) -> None:
        """Populate the local Treeview."""
        self.last_selected_items["local"] = None
        self.local_sort_column = ""
        self._reset_tree_headings(self.local_tree, "local")
        for item_id in self.local_tree.get_children():
            self.local_tree.delete(item_id)
        for index, entry in enumerate(self.local_entries):
            self.local_tree.insert(
                "",
                tk.END,
                iid=str(index),
                values=(
                    entry.name,
                    _("Directory") if entry.is_directory else _("File"),
                    "" if entry.is_directory else format_filesize(entry.size_bytes),
                ),
            )
        self._update_empty_state(self.local_entries, self.local_directory_label)

    def _populate_tree(self) -> None:
        """Compatibility population method for the original file-only Treeview."""
        if hasattr(self, "remote_tree"):
            self._populate_remote_tree()
            return
        for item_id in self.tree.get_children():
            self.tree.delete(item_id)
        for index, remote_file in enumerate(self.remote_files):
            self.tree.insert("", tk.END, iid=str(index), values=(remote_file.name, format_filesize(remote_file.size_bytes)))
        self._on_tree_selection_change()

    @staticmethod
    def _update_empty_state(entries: Sequence[FlightControllerLogFile | LocalFileEntry], label: ttk.Label) -> None:
        """Show a simple empty state when a panel contains no rows."""
        if not entries:
            label.configure(text=_("No entries found in this directory."))

    def _reset_tree_headings(self, tree: ttk.Treeview, prefix: str) -> None:
        """Reset translated headings and initial sort commands."""
        sort_state = "remote_sort_column" if prefix == "remote" else "local_sort_column"
        reverse_state = "remote_sort_reverse" if prefix == "remote" else "local_sort_reverse"
        setattr(self, sort_state, "")
        setattr(self, reverse_state, False)
        for column, title in (("name", _("Name")), ("type", _("Type")), ("size", _("Size"))):
            tree.heading(
                column,
                text=title,
                command=lambda col=column, panel=prefix: self._on_sort_heading(panel, col),
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
        """Sort one panel by name, type, or numeric size."""
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
    ) -> tuple[int, int | str, str]:
        """Return a stable sort key from an entry list."""
        item_text = str(item_id)
        if not item_text.isdigit() or int(item_text) >= len(entries):
            return (0, 0, "")
        entry = entries[int(item_text)]
        name = entry.name.casefold()
        if entry.name == "..":  # type: ignore[attr-defined]
            return (0, 0, "")
        if column == "size":
            return (1, entry.size_bytes, name)
        if column == "type":
            return (1, 0 if entry.is_directory else 1, name)
        return (1, name, entry.name)

    @staticmethod
    def _set_heading_text(tree: ttk.Treeview, column: str, reverse: bool | None) -> None:
        """Set a heading's label and optional direction marker."""
        title = {"name": _("Name"), "type": _("Type"), "size": _("Size")}[column]
        if reverse is not None:
            title += " ▼" if reverse else " ▲"
        tree.heading(column, text=title)

    def _on_remote_directory_return(self, _event: tk.Event | None = None) -> str:
        """Refresh the remote listing when Enter is pressed in its entry."""
        if hasattr(self, "remote_directory_var"):
            self.refresh_remote_panel()
        else:
            self.refresh_remote_files()
        return "break"

    def _on_local_directory_return(self, _event: tk.Event | None = None) -> str:
        """Refresh the local listing when Enter is pressed in its entry."""
        self.refresh_local_panel()
        return "break"

    def _remember_panel(self, panel: str) -> None:
        """Remember which panel was most recently focused or selected."""
        if panel in {"remote", "local"}:
            self.last_selected_panel = panel

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
        except (AttributeError, tk.TclError, TypeError, ValueError):
            self._rename_entry_with_dialog(panel, entry)

    def _finish_inline_rename(
        self,
        panel: str,
        entry: FlightControllerLogFile | LocalFileEntry,
        editor: ttk.Entry,
    ) -> str:
        """Commit an inline rename and refresh the affected panel."""
        new_name = editor.get()
        editor.destroy()
        if not self._safe_name(new_name):
            self.ui.show_error(_("Rename error"), _("The new name must be one file or directory name."))
            return "break"
        self._rename_entry(panel, entry, new_name)
        return "break"

    @staticmethod
    def _cancel_inline_rename(editor: ttk.Entry) -> str:
        """Cancel an inline rename editor."""
        editor.destroy()
        return "break"

    def _rename_entry_with_dialog(self, panel: str, entry: FlightControllerLogFile | LocalFileEntry) -> None:
        """Prompt for a new name when inline editing cannot be created."""
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
        if not self._confirm_remote_mutation_scope(_("rename"), (entry.remote_path, new_path)):
            return False
        if getattr(self, "_operation_active", False) or getattr(self, "_remote_task_thread", None) is not None:
            return False
        outcome: list[bool] = []

        def worker(
            _report_progress: Callable[[int, int], None],
            cancel_event: Event,
        ) -> tuple[list[str], list[str], bool]:
            if cancel_event.is_set():
                return [], [], True
            success = self._call_remote_bool(
                self.parameter_editor.rename_remote_path,
                entry.remote_path,
                new_path,
            )
            return ([entry.remote_path], [], False) if success else ([], [entry.remote_path], False)

        def completion(succeeded: list[str], failed: list[str], cancelled: bool) -> None:
            outcome.append(bool(succeeded) and not cancelled)
            if cancelled:
                self._show_summary(_("Rename summary"), succeeded, failed, cancelled)
            elif succeeded:
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
        if not hasattr(self, "remote_tree"):
            self.select_all_files()
            return "break"
        tree = getattr(_event, "widget", None)
        if tree not in {self.remote_tree, self.local_tree}:
            tree = self.remote_tree
        self._select_all_tree_entries(tree)
        return "break"

    @staticmethod
    def _select_all_tree_entries(tree: ttk.Treeview) -> None:
        """Select all visible entries except the parent-navigation row."""
        tree.selection_set([item_id for item_id in tree.get_children() if tree.item(item_id, "values")[0] != ".."])

    def select_all_remote_entries(self) -> None:
        """Select all remote entries except the parent-navigation row."""
        if hasattr(self, "remote_tree"):
            self._select_all_tree_entries(self.remote_tree)
            return
        self.select_all_files()

    def select_all_local_entries(self) -> None:
        """Select all local entries except the parent-navigation row."""
        if hasattr(self, "local_tree"):
            self._select_all_tree_entries(self.local_tree)

    def select_all_files(self) -> None:
        """Select all remote files for compatibility with the original window API."""
        tree = self.tree
        entries = self.remote_files
        item_ids = [str(index) for index, entry in enumerate(entries) if entry.name != ".."]
        tree.selection_set(item_ids)
        self._on_tree_selection_change()

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
        """Open a local directory on double click."""
        item_id = self.local_tree.identify_row(event.y)
        if not item_id:
            return
        entry = self._entry_from_tree(self.local_entries, item_id)
        if isinstance(entry, LocalFileEntry) and entry.is_directory:
            self.local_directory_var.set(str(entry.path))
            self.refresh_local_panel()

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
        return bool(name) and name not in {".", ".."} and "/" not in name and "\\" not in name

    @staticmethod
    def _local_path_key(path: Path) -> str:
        """Return a platform-aware key for detecting local target collisions."""
        return str(path.absolute()).casefold() if sys.platform == "win32" else str(path.absolute())

    @classmethod
    def _local_path_is_ancestor(cls, parent: Path, child: Path) -> bool:
        """Return whether one planned local path is a strict ancestor of another."""
        parent_key = cls._local_path_key(parent).rstrip("\\/")
        child_key = cls._local_path_key(child)
        return child_key.startswith((f"{parent_key}\\", f"{parent_key}/"))

    def _set_remote_controls_state(self, state: str) -> None:
        """Enable or disable controls that issue remote operations."""
        for name in (
            "remote_directory_entry",
            "remote_parent_button",
            "remote_tree",
        ):
            widget = getattr(self, name, None)
            if widget is not None:
                widget.configure(state=state)

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
        ):
            widget = getattr(self, name, None)
            if widget is not None:
                widget.configure(state=state)

    def _start_remote_task(
        self,
        task: Callable[[], object],
        completion: Callable[[object, Exception | None], None],
    ) -> bool:
        """Run blocking remote listing/planning work away from Tk's event loop."""
        if getattr(self, "_operation_active", False) or getattr(self, "_remote_task_thread", None) is not None:
            return False
        remote_task_queue = getattr(self, "_remote_task_queue", None)
        if remote_task_queue is None:
            remote_task_queue = queue.Queue()
            self._remote_task_queue = remote_task_queue
        self._remote_task_completion = completion
        self._set_remote_controls_state("disabled")

        def run() -> None:
            try:
                result = task()
                error = None
            except Exception as exception:  # pylint: disable=broad-exception-caught
                result = None
                error = exception
            remote_task_queue.put((result, error))

        if not isinstance(getattr(self, "root", None), tk.Misc):
            run()
            result, error = remote_task_queue.get()
            self._remote_task_completion = None
            self._set_remote_controls_state("normal")
            completion(result, error)
            return True

        self._remote_task_thread = Thread(target=run, name="mavftp-remote-task", daemon=True)
        self._remote_task_thread.start()
        self.root.after(50, self._poll_remote_task)
        return True

    def _poll_remote_task(self) -> None:
        """Apply a remote task result on the Tk thread."""
        try:
            result, error = self._remote_task_queue.get_nowait()
        except queue.Empty:
            if isinstance(getattr(self, "root", None), tk.Misc):
                self.root.after(50, self._poll_remote_task)
            return
        self._remote_task_thread = None
        completion = self._remote_task_completion
        self._remote_task_completion = None
        self._set_remote_controls_state("normal")
        if completion is not None:
            completion(result, error)

    def _progress_window(self, title: str, message: str) -> ProgressWindow:
        """Create a standard application progress window."""
        return self.ui.create_progress_window(getattr(self, "root", None), title, message, False)  # noqa: FBT003

    def _on_cancel_or_close(self) -> None:
        """Cancel an active transfer, or close the browser when idle."""
        if getattr(self, "_remote_task_thread", None) is not None:
            return
        cancel_event = getattr(self, "_operation_cancel_event", None)
        if cancel_event is not None:
            cancel_event.set()
            self.cancel_button.configure(text=_("Cancelling…"), state="disabled")
            return
        self.root.destroy()

    def _start_background_operation(
        self,
        title: str,
        message: str,
        worker: Callable[[Callable[[int, int], None], Event], tuple[list[str], list[str], bool]],
        completion: Callable[[list[str], list[str], bool], None],
    ) -> None:
        """Run one blocking MAVFTP operation away from Tk's event loop."""
        if getattr(self, "_operation_active", False) or getattr(self, "_remote_task_thread", None) is not None:
            return

        cancel_event = Event()

        def report_progress(current: int, total: int) -> None:
            if isinstance(getattr(self, "root", None), tk.Misc):
                self._operation_queue.put(("progress", (current, total)))
            elif self._operation_progress is not None:
                self._operation_progress.update_progress_bar(current, total)

        def run() -> None:
            try:
                result = worker(report_progress, cancel_event)
            except Exception as error:  # pylint: disable=broad-exception-caught
                result = ([], [str(error)], cancel_event.is_set())
            self._operation_queue.put(("done", result))

        # Unit-level tests construct this class with __new__ and no Tk root.
        # Keep that seam synchronous while real windows always use a worker.
        if not isinstance(getattr(self, "root", None), tk.Misc):
            self._operation_progress = self._progress_window(title, message)
            result = worker(report_progress, cancel_event)
            self._operation_progress.destroy()
            completion(*result)
            return

        self._operation_active = True
        self._operation_cancel_event = cancel_event
        self._operation_completion = completion
        self._operation_progress = self._progress_window(title, message)
        self._set_operation_controls_state("disabled")
        self.cancel_button.configure(text=_("Cancel operation"), state="normal")
        self._operation_thread = Thread(target=run, name="mavftp-transfer", daemon=True)
        self._operation_thread.start()
        self.root.after(50, self._poll_background_operation)

    def _poll_background_operation(self) -> None:
        """Apply worker progress and completion messages on the Tk thread."""
        try:
            while True:
                kind, payload = self._operation_queue.get_nowait()
                if kind == "progress" and self._operation_progress is not None:
                    current, total = cast("tuple[int, int]", payload)
                    self._operation_progress.update_progress_bar(current, total)
                elif kind == "done":
                    succeeded, failed, cancelled = cast("tuple[list[str], list[str], bool]", payload)
                    if self._operation_progress is not None:
                        self._operation_progress.destroy()
                    self._operation_progress = None
                    self._operation_thread = None
                    self._operation_cancel_event = None
                    self._operation_active = False
                    self._set_operation_controls_state("normal")
                    self.cancel_button.configure(text=_("Cancel"), state="normal")
                    completion = getattr(self, "_operation_completion", None)
                    self._operation_completion = None
                    if completion is not None:
                        completion(succeeded, failed, cancelled)
                    return
        except queue.Empty:
            pass
        except tk.TclError:
            return
        self.root.after(50, self._poll_background_operation)

    def _show_summary(self, title: str, succeeded: list[str], failed: list[str], cancelled: bool = False) -> None:
        """Show a compact per-entry operation summary."""
        lines = [(_("Succeeded: %s") % name) for name in succeeded]
        lines.extend(_("Failed: %s") % name for name in failed)
        if cancelled:
            lines.append(_("Cancelled by user."))
        (self.ui.show_error if failed else self.ui.show_info)(title, "\n".join(lines) or _("No entries processed."))

    @staticmethod
    def _remote_path_is_in_log_scope(remote_path: str) -> bool:
        """Return whether a remote path is inside the default log directory."""
        normalized = posixpath.normpath(remote_path.replace("\\", "/"))
        return normalized == "/APM/LOGS" or normalized.startswith("/APM/LOGS/")

    def _confirm_remote_mutation_scope(self, operation: str, remote_paths: Sequence[str]) -> bool:
        """Warn before a mutation leaves the normal `/APM/LOGS/` scope."""
        outside_scope = tuple(path for path in remote_paths if not self._remote_path_is_in_log_scope(path))
        if not outside_scope:
            return True
        paths = "\n".join(outside_scope[:8])
        if len(outside_scope) > 8:
            paths += "\n…"
        self.ui.show_warning(
            _("Warning: outside log directory"),
            _(
                "The following remote paths are outside /APM/LOGS/:\n\n"
                "%(paths)s\n\n"
                "The %(operation)s operation can modify flight-controller files outside the log directory."
            )
            % {"paths": paths, "operation": operation},
        )
        return self.ui.ask_yesno(
            _("Confirm remote file operation"),
            _("Proceed with %(operation)s outside /APM/LOGS/?") % {"operation": operation},
        )

    @staticmethod
    def _cancellable_progress(
        report_progress: Callable[[int, int], None],
        cancel_event: Event,
    ) -> Callable[[int, int], None]:
        """Adapt backend progress callbacks to the cancellable worker."""

        def callback(current: int, total: int) -> None:
            if cancel_event.is_set():
                raise _TransferCancelledError
            report_progress(current, total)

        return callback

    def _remote_download_plan(
        self,
        entry: FlightControllerLogFile,
        local_target: Path,
        failures: list[str] | None = None,
    ) -> tuple[list[Path], list[tuple[FlightControllerLogFile, Path]]]:
        """Recursively expand one remote entry into local directories and files."""
        if not entry.is_directory:
            if not self._safe_remote_entry_name(entry.name):
                if failures is not None:
                    failures.append(entry.remote_path)
                return [], []
            return [], [(entry, local_target)]
        directories = [local_target]
        files: list[tuple[FlightControllerLogFile, Path]] = []
        try:
            children = self.parameter_editor.get_remote_files(entry.remote_path)
        except Exception:  # pylint: disable=broad-exception-caught
            if failures is not None:
                failures.append(entry.remote_path)
            return [], []
        if children is None:
            if failures is not None:
                failures.append(entry.remote_path)
            return [], []
        for child in children:
            if child.name == "..":
                continue
            if not self._safe_remote_entry_name(child.name):
                if failures is not None:
                    failures.append(child.remote_path)
                continue
            child_dirs, child_files = self._remote_download_plan(child, local_target / child.name, failures)
            directories.extend(child_dirs)
            files.extend(child_files)
        return directories, files

    def _build_remote_download_plan(
        self,
        selected: Sequence[FlightControllerLogFile],
        local_directory: Path,
    ) -> RemoteDownloadPlan:
        """Build a recursive remote download plan without touching Tk widgets."""
        directories: list[Path] = []
        files: list[tuple[FlightControllerLogFile, Path]] = []
        failed: list[str] = []
        for entry in selected:
            if not self._safe_remote_entry_name(entry.name):
                failed.append(entry.remote_path)
                continue
            child_dirs, child_files = self._remote_download_plan(entry, local_directory / entry.name, failed)
            directories.extend(child_dirs)
            files.extend(child_files)
        return RemoteDownloadPlan(tuple(directories), tuple(files), tuple(failed))

    @classmethod
    def _local_target_conflicts(
        cls,
        plan: RemoteDownloadPlan,
    ) -> tuple[list[Path], list[Path]]:
        """Return duplicate planned targets and existing incompatible targets."""
        planned: dict[str, tuple[Path, bool]] = {}
        duplicate_targets: list[Path] = []
        for target, is_directory in (
            *((target, True) for target in plan.directories),
            *((target, False) for _entry, target in plan.files),
        ):
            key = cls._local_path_key(target)
            if key in planned:
                duplicate_targets.append(target)
            else:
                planned[key] = target, is_directory

        file_targets = tuple(target for target, is_directory in planned.values() if not is_directory)
        for file_target in file_targets:
            for other_target, _is_directory in planned.values():
                if cls._local_path_is_ancestor(file_target, other_target):
                    duplicate_targets.append(other_target)

        existing_conflicts: list[Path] = []
        for target, is_directory in planned.values():
            exists = target.exists() or target.is_symlink()
            if exists and (target.is_symlink() or not is_directory or not target.is_dir()):
                existing_conflicts.append(target)
        return duplicate_targets, existing_conflicts

    def _download_remote_plan_worker(
        self,
        plan: RemoteDownloadPlan,
        total: int,
        report_progress: Callable[[int, int], None],
        cancel_event: Event,
    ) -> tuple[list[str], list[str], bool]:
        """Create local directories and transfer the files in a remote plan."""
        completed = 0
        succeeded: list[str] = []
        failed = list(plan.failed)
        for directory in plan.directories:
            if cancel_event.is_set():
                return succeeded, failed, True
            try:
                if directory.is_symlink() or (directory.exists() and not directory.is_dir()):
                    failed.append(str(directory))
                    continue
                directory.mkdir(parents=True, exist_ok=True)
            except OSError:
                failed.append(str(directory))

        for entry, target in plan.files:
            if cancel_event.is_set():
                return succeeded, failed, True
            units = max(entry.size_bytes, 1)
            if target.is_symlink() or (target.parent.exists() and not target.parent.is_dir()):
                failed.append(entry.remote_path)
                completed += units
                report_progress(completed, total)
                continue
            callback = self._cancellable_progress(
                lambda current, maximum, offset=completed, size=units: report_progress(
                    min(total, int(offset + size * (current / maximum if maximum else 0.0))),
                    total,
                ),
                cancel_event,
            )
            try:
                success = self.parameter_editor.download_remote_file(entry.remote_path, str(target), callback)
            except _TransferCancelledError:
                return succeeded, failed, True
            except Exception:  # pylint: disable=broad-exception-caught
                success = False
            if cancel_event.is_set():
                return succeeded, failed, True
            if success:
                succeeded.append(entry.remote_path)
            else:
                failed.append(entry.remote_path)
            completed += units
            report_progress(completed, total)
        return succeeded, failed, False

    def download_selected_remote_entries(self) -> None:
        """Recursively download selected remote entries into the local panel directory."""
        if getattr(self, "_operation_active", False) or getattr(self, "_remote_task_thread", None) is not None:
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
            if not isinstance(result, RemoteDownloadPlan):
                self.ui.show_error(_("Download error"), _("Could not prepare the selected remote entries."))
                return
            duplicate_targets, existing_conflicts = self._local_target_conflicts(result)
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
            if not result.directories and not result.files:
                self._show_summary(_("Download summary"), [], list(result.failed))
                return
            total = max(sum(max(entry.size_bytes, 1) for entry, _path in result.files), 1)

            def worker(
                report_progress: Callable[[int, int], None],
                cancel_event: Event,
            ) -> tuple[list[str], list[str], bool]:
                return self._download_remote_plan_worker(result, total, report_progress, cancel_event)

            def completion(succeeded: list[str], worker_failed: list[str], cancelled: bool) -> None:
                self._show_summary(_("Download summary"), succeeded, worker_failed, cancelled)
                self.refresh_local_panel()

            self._start_background_operation(
                _("Downloading selected entries"),
                _("Downloaded {} of {} bytes"),
                worker,
                completion,
            )

        self._start_remote_task(
            lambda: self._build_remote_download_plan(selected, local_directory),
            complete_plan,
        )

    def _local_upload_plan(self, entry: LocalFileEntry, remote_target: str) -> tuple[list[str], list[tuple[Path, str, int]]]:
        """Recursively expand one local entry into remote directories and files."""
        if not entry.is_directory:
            return [], [(entry.path, remote_target, entry.size_bytes)]
        directories = [remote_target]
        files: list[tuple[Path, str, int]] = []
        try:
            children = sorted(entry.path.iterdir(), key=lambda path: path.name.casefold())
        except OSError:
            return directories, files
        for child in children:
            if child.is_symlink():
                continue
            try:
                is_directory = child.is_dir()
                size_bytes = 0 if is_directory else child.stat().st_size
            except OSError:
                continue
            child_entry = LocalFileEntry(child.name, child, size_bytes, is_directory)
            child_dirs, child_files = self._local_upload_plan(
                child_entry,
                posixpath.join(remote_target.rstrip("/"), child.name),
            )
            directories.extend(child_dirs)
            files.extend(child_files)
        return directories, files

    def upload_selected_local_entries(self) -> None:
        """Recursively upload selected local entries to the remote panel directory."""
        if getattr(self, "_operation_active", False):
            return
        selected = [entry for entry in self._selected_local_entries() if entry.name != ".."]
        if not selected:
            return
        remote_directory = self.remote_directory_var.get().rstrip("/") or "/"
        if not self._safe_remote_directory(remote_directory):
            self.ui.show_error(_("Upload error"), _("The remote destination must be an absolute directory path."))
            return
        if not self._confirm_remote_mutation_scope(_("upload"), (remote_directory,)):
            return
        if not self.ui.ask_yesno(
            _("Upload selected entries?"),
            _("Uploading may overwrite remote files. Continue?"),
        ):
            return
        directories: list[str] = []
        files: list[tuple[Path, str, int]] = []
        for entry in selected:
            target = posixpath.join(remote_directory, entry.name)
            child_dirs, child_files = self._local_upload_plan(entry, target)
            directories.extend(child_dirs)
            files.extend(child_files)
        total = max(sum(max(size, 1) for _path, _remote, size in files), 1)

        def worker(
            report_progress: Callable[[int, int], None],
            cancel_event: Event,
        ) -> tuple[list[str], list[str], bool]:
            completed = 0
            succeeded: list[str] = []
            failed: list[str] = []
            for directory in directories:
                if cancel_event.is_set():
                    return succeeded, failed, True
                if not self._call_remote_bool(self.parameter_editor.make_remote_directory, directory):
                    failed.append(directory)
            for local_path, remote_path, size in files:
                if cancel_event.is_set():
                    return succeeded, failed, True
                units = max(size, 1)
                callback = self._cancellable_progress(
                    lambda current, maximum, offset=completed, file_size=units: report_progress(
                        min(total, int(offset + file_size * (current / maximum if maximum else 0.0))),
                        total,
                    ),
                    cancel_event,
                )
                try:
                    success = self.parameter_editor.upload_file_to_fc(str(local_path), remote_path, callback)
                except _TransferCancelledError:
                    return succeeded, failed, True
                except Exception:  # pylint: disable=broad-exception-caught
                    success = False
                if cancel_event.is_set():
                    return succeeded, failed, True
                if success:
                    succeeded.append(remote_path)
                else:
                    failed.append(remote_path)
                completed += units
                report_progress(completed, total)
            return succeeded, failed, False

        def completion(succeeded: list[str], failed: list[str], cancelled: bool) -> None:
            self._show_summary(_("Upload summary"), succeeded, failed, cancelled)
            self.refresh_remote_panel()

        self._start_background_operation(
            _("Uploading selected entries"),
            _("Uploaded {} of {} bytes"),
            worker,
            completion,
        )

    def _delete_remote_entry(self, entry: FlightControllerLogFile, succeeded: list[str], failed: list[str]) -> None:
        """Delete one remote file or an empty remote directory."""
        if entry.is_directory:
            try:
                listing = self.parameter_editor.get_remote_files(entry.remote_path)
            except Exception:  # pylint: disable=broad-exception-caught
                failed.append(entry.remote_path)
                return
            if listing is None:
                failed.append(entry.remote_path)
                return
            children = [child for child in listing if child.name != ".."]
            if children:
                failed.append(entry.remote_path)
                return
        if self._call_remote_bool(self.parameter_editor.delete_remote_path, entry.remote_path, entry.is_directory):
            succeeded.append(entry.remote_path)
        else:
            failed.append(entry.remote_path)

    def delete_selected_remote_entries(self) -> None:
        """Delete selected remote files and empty directories after confirmation."""
        selected = [entry for entry in self._selected_remote_entries() if entry.name != ".."]
        if selected and not self._confirm_remote_mutation_scope(_("delete"), tuple(entry.remote_path for entry in selected)):
            return
        if not selected or not self.ui.ask_yesno(
            _("Delete remote entries?"),
            _("Delete selected files and empty directories?"),
        ):
            return

        def worker(
            _report_progress: Callable[[int, int], None],
            cancel_event: Event,
        ) -> tuple[list[str], list[str], bool]:
            succeeded: list[str] = []
            failed: list[str] = []
            for entry in selected:
                if cancel_event.is_set():
                    return succeeded, failed, True
                self._delete_remote_entry(entry, succeeded, failed)
            return succeeded, failed, False

        def completion(succeeded: list[str], failed: list[str], cancelled: bool) -> None:
            self._show_summary(_("Remote delete summary"), succeeded, failed, cancelled)
            self.refresh_remote_panel()

        self._start_background_operation(
            _("Deleting remote entries"),
            _("Deleted selected remote entries"),
            worker,
            completion,
        )

    def delete_selected_local_entries(self) -> None:
        """Delete selected local files and empty directories after confirmation."""
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

    def rename_selected_remote_entry(self) -> None:
        """Rename one selected remote entry."""
        selected = [entry for entry in self._selected_remote_entries() if entry.name != ".."]
        if len(selected) != 1:
            self.ui.show_error(_("Rename error"), _("Select exactly one remote entry to rename."))
            return
        entry = selected[0]
        new_name = self.ui.askstring(_("Rename remote entry"), _("New name:"), initialvalue=entry.name, parent=self.root)
        if new_name is None:
            return
        if not self._safe_name(new_name):
            self.ui.show_error(_("Rename error"), _("The new name must be one file or directory name."))
            return
        new_path = posixpath.join(posixpath.dirname(entry.remote_path.rstrip("/")), new_name)
        if not self._confirm_remote_mutation_scope(_("rename"), (entry.remote_path, new_path)):
            return
        self._rename_remote_entry(entry, new_name)

    def rename_selected_local_entry(self) -> None:
        """Rename one selected local entry."""
        selected = [entry for entry in self._selected_local_entries() if entry.name != ".."]
        if len(selected) != 1:
            self.ui.show_error(_("Rename error"), _("Select exactly one local entry to rename."))
            return
        entry = selected[0]
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

    # Compatibility workflow retained for existing callers of the original single/multi download UI.
    def download_selected_files(self) -> None:
        """Download selected regular files using the original destination dialogs."""
        selected_files = self._selected_files()
        if not selected_files:
            return
        if len(selected_files) == 1:
            destination = self.ui.asksaveasfilename(
                title=_("Save flight-controller file as"),
                initialfile=selected_files[0].name,
                filetypes=[(_("All files"), "*.*"), (_("Binary log files"), "*.bin")],
            )
            destination_is_directory = False
        else:
            destination = self.ui.askdirectory(title=_("Select local destination directory"))
            destination_is_directory = True
        if not destination:
            return
        progress_window = self._progress_window(_("Downloading flight-controller file(s)"), _("Downloaded {} of {} bytes"))
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

    def _selected_files(self) -> list[FlightControllerLogFile]:
        """Return selected regular files for the compatibility workflow."""
        tree = self.tree
        selected: list[FlightControllerLogFile] = []
        for item_id in tree.selection():
            entry = self._entry_from_tree(self.remote_files, item_id)
            if isinstance(entry, FlightControllerLogFile) and not entry.is_directory:
                selected.append(entry)
        return selected

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

    def _on_tree_selection_change(self, _event: tk.Event | None = None) -> None:
        """Retained for compatibility with the original remote-only window."""
        download_button = getattr(self, "download_button", None)
        if download_button is not None:
            download_button.configure(state="normal" if self.tree.selection() else "disabled")

    def _sort_by_column(self, column: str, reverse: bool) -> None:
        """Retained compatibility wrapper for the original remote-only sorter."""
        if hasattr(self, "remote_tree") and hasattr(self, "remote_entries"):
            self._sort_panel_by_column("remote", column, reverse)
            return
        rows = [(self._panel_sort_key(self.remote_files, item_id, column), item_id) for item_id in self.tree.get_children("")]
        rows.sort(key=lambda row: row[0], reverse=reverse)
        for position, (_key, item_id) in enumerate(rows):
            self.tree.move(item_id, "", position)

    @staticmethod
    def _safe_remote_entry_name(name: str) -> bool:
        """Return whether a remote listing name is safe as one path component."""
        return bool(name) and name not in {".", ".."} and "/" not in name and "\\" not in name

    @staticmethod
    def _safe_remote_directory(directory: str) -> bool:
        """Return whether a remote destination is an absolute directory path."""
        return bool(directory) and directory.startswith("/") and ".." not in directory.split("/")

    @staticmethod
    def _call_remote_bool(callback: Callable[..., bool], *args: object) -> bool:
        """Call a remote-operation callback without aborting a batch on one exception."""
        try:
            return bool(callback(*args))
        except Exception:  # pylint: disable=broad-exception-caught
            return False

    def download_last_flight_log(self) -> None:
        """Download the last flight log without blocking the Tk event loop."""
        if getattr(self, "_operation_active", False) or getattr(self, "_remote_task_thread", None) is not None:
            return
        if not self.parameter_editor.is_fc_connected:
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

        def worker(
            report_progress: Callable[[int, int], None],
            cancel_event: Event,
        ) -> tuple[list[str], list[str], bool]:
            callback = self._cancellable_progress(report_progress, cancel_event)
            try:
                success = self.parameter_editor.download_last_flight_log(filename, callback)
            except _TransferCancelledError:
                return [], [], True
            except Exception:  # pylint: disable=broad-exception-caught
                success = False
            if cancel_event.is_set():
                return [], [], True
            return ([filename], []) if success else ([], [filename], False)

        def completion(succeeded: list[str], failed: list[str], cancelled: bool) -> None:
            self._show_summary(_("Download summary"), succeeded, failed, cancelled)
            self.refresh_local_panel()

        self._start_background_operation(
            _("Downloading Flight Log"),
            _("Downloaded {}% from {}%"),
            worker,
            completion,
        )
