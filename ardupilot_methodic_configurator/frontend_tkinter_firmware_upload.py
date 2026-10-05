"""
Standalone and embedded Upload ArduPilot firmware window.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import sys
import tkinter as tk
from argparse import ArgumentParser
from collections.abc import Callable
from contextlib import suppress
from pathlib import Path
from queue import Empty, SimpleQueue
from textwrap import fill
from threading import Event, Thread
from tkinter import filedialog, messagebox, ttk

from argcomplete.completers import FilesCompleter

# Support direct execution from the repository root as well as package imports.
if __package__ in {None, ""}:  # pragma: no cover
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# pylint: disable=wrong-import-position
from ardupilot_methodic_configurator import _
from ardupilot_methodic_configurator.backend_firmware_upload import (
    FirmwareBoardInfo,
    FirmwareUploadCallbacks,
    FirmwareUploadService,
)
from ardupilot_methodic_configurator.backend_flightcontroller import FlightController
from ardupilot_methodic_configurator.backend_internet import webbrowser_open_url
from ardupilot_methodic_configurator.data_model_firmware_catalog import (
    FirmwareRelease,
    find_firmware_release,
    firmware_targets,
    firmware_types,
    firmware_versions,
    preferred_board_target,
    preferred_firmware_type,
)
from ardupilot_methodic_configurator.data_model_firmware_upload import (
    BootloaderInfo,
    FirmwareImage,
    FirmwareUploadCancelledError,
    UploadStage,
)
from ardupilot_methodic_configurator.frontend_tkinter_base_window import BaseWindow
from ardupilot_methodic_configurator.frontend_tkinter_connection_selection import ConnectionSelectionWidgets
from ardupilot_methodic_configurator.frontend_tkinter_parameter_application import (
    configure_standalone_logging,
    connect_standalone_flight_controller,
)
from ardupilot_methodic_configurator.frontend_tkinter_parameter_application import (
    create_argument_parser as create_parameter_application_argument_parser,
)
from ardupilot_methodic_configurator.frontend_tkinter_show import show_tooltip

# pylint: enable=wrong-import-position


def _show_firmware_tooltip(widget: tk.Widget, text: str) -> None:
    """Preserve explicit breaks and limit translated tooltip lines to 50 characters."""
    show_tooltip(widget, "\n".join(fill(line, width=50) for line in text.split("\n")))


def _start_background_worker(worker: Callable[[], None]) -> None:
    """Launch work without blocking Tk; tests can substitute a controlled launcher."""
    Thread(target=worker, daemon=True).start()


class _FirmwareConnectionSelector(BaseWindow):
    """Select a connection in the firmware window's Tk interpreter."""

    def __init__(self, parent: tk.Tk | tk.Toplevel, flight_controller: FlightController) -> None:
        super().__init__(parent)
        self.root.title(_("Select a flight controller"))
        self.root.geometry(self.calculate_scaled_geometry(520, 210))
        if parent.winfo_viewable():
            self.root.transient(parent)
        self.root.protocol("WM_DELETE_WINDOW", self.close)
        selection_frame = ttk.LabelFrame(self.main_frame, text=_("Flight controller connection"))
        selection_frame.pack(fill=tk.X, padx=12, pady=12)
        self.connection_selection_widgets = ConnectionSelectionWidgets(
            self,
            selection_frame,
            flight_controller,
            destroy_parent_on_connect=True,
            download_params_on_connect=False,
            default_baudrate=flight_controller.baudrate,
        )
        self.connection_selection_widgets.container_frame.pack(fill=tk.X, padx=8, pady=8)
        auto_connect = ttk.Button(self.main_frame, text=_("Auto-connect"), command=self.connection_selection_widgets.reconnect)
        auto_connect.pack(pady=8)
        _show_firmware_tooltip(auto_connect, _("Find and connect to a flight controller\nplugged into your computer by USB."))

    def close(self) -> None:
        """Dismiss the selector without releasing the firmware window's connection."""
        self.connection_selection_widgets.stop_periodic_refresh()
        self.root.destroy()


class FirmwareUploadWindow(BaseWindow):  # pylint: disable=too-many-instance-attributes
    """Choose an official release for the detected board and flash it safely."""

    def __init__(
        self,
        flight_controller: FlightController | None = None,
        *,
        parent: tk.Tk | tk.Toplevel | None = None,
        owns_connection: bool = False,
        service: FirmwareUploadService | None = None,
        worker_launcher: Callable[[Callable[[], None]], None] | None = None,
    ) -> None:
        super().__init__(parent)
        self.flight_controller = flight_controller or FlightController()
        self.service = FirmwareUploadService() if service is None else service
        self.worker_launcher = _start_background_worker if worker_launcher is None else worker_launcher
        self.owns_connection = owns_connection or flight_controller is None
        self.releases: list[FirmwareRelease] = []
        self.events: SimpleQueue[tuple] = SimpleQueue()
        self.cancelled = Event()
        self.busy = False
        self.uploading = False
        # A later cancellation cannot clear a restart requirement from an upload or idle disconnect.
        self.restart_required = False
        self.connecting = False
        self._connection_timer_id: str | None = None
        self._event_poll_id: str | None = None
        self.catalog_request_id = 0
        self.board_id: int | None = None
        self._active_progress_stage: UploadStage | None = None
        self.root.title(_("Upload ArduPilot firmware"))
        window_height = round(328 * 1.3) if self.root.tk.call("tk", "windowingsystem") == "win32" else 328
        self.root.geometry(self.calculate_scaled_geometry(750, window_height))
        self.center_window_on_screen(self.root)
        if parent is not None and parent.winfo_viewable():
            self.root.transient(parent)
        self.root.protocol("WM_DELETE_WINDOW", self.close)

        board_frame = ttk.LabelFrame(self.main_frame, text=_("Connected flight controller"))
        board_frame.pack(fill=tk.X, padx=12, pady=10)
        self.board_text = tk.StringVar(master=self.root, value=_("No flight controller connected"))
        board_label = ttk.Label(board_frame, textvariable=self.board_text)
        board_label.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=8, pady=8)
        self.connect_button = ttk.Button(board_frame, text=_("Connect"), command=self.connect)
        self.connect_button.pack(side=tk.RIGHT, padx=8, pady=8)

        self._create_selection_widgets()

        status_label, actions = self._create_upload_controls()
        self._create_help_button(actions)
        self._add_window_tooltips(board_label, status_label)

        self._event_poll_id = self.root.after(100, self._poll_events)
        self._refresh_board()
        self._connection_timer_id = self.root.after(1000, self._monitor_connection)

    def _create_upload_controls(self) -> tuple[ttk.Label, ttk.Frame]:
        """Create status, progress, and upload controls below firmware selection."""
        self.status = tk.StringVar(master=self.root, value=_("Connect a flight controller to detect its board"))
        status_label = ttk.Label(self.main_frame, textvariable=self.status, wraplength=690)
        status_label.pack(fill=tk.X, padx=18, pady=7)
        self.progress_bars: dict[UploadStage, ttk.Progressbar] = {}
        self._create_progress_bars()
        actions = ttk.Frame(self.main_frame)
        actions.pack(fill=tk.X, padx=12, pady=10)
        self.custom_button = ttk.Button(
            actions, text=_("Upload custom APJ…"), command=self.select_custom_firmware, state="disabled"
        )
        self.custom_button.pack(side=tk.LEFT, padx=4)
        self.upload_button = ttk.Button(actions, text=_("Upload firmware"), command=self.start_upload, state="disabled")
        self.upload_button.pack(side=tk.RIGHT, padx=4)
        self.cancel_button = ttk.Button(actions, text=_("Cancel"), command=self.cancelled.set, state="disabled")
        self.cancel_button.pack(side=tk.RIGHT, padx=4)
        return status_label, actions

    def _create_help_button(self, parent: ttk.Frame) -> None:
        """Add a link to the firmware upload user manual."""
        self.help_button = ttk.Button(
            parent,
            text=_("Help"),
            command=lambda: webbrowser_open_url(
                "https://ardupilot.github.io/MethodicConfigurator/USERMANUAL_firmware_upload.html"
            ),
        )
        self.help_button.pack(side=tk.LEFT, padx=4)
        show_tooltip(self.help_button, _("Open the firmware upload user manual"))

    def _add_window_tooltips(self, board_label: ttk.Label, status_label: ttk.Label) -> None:
        """Explain connection details and firmware actions to new users."""
        for widget, text in (
            (
                board_label,
                _(
                    "The flight controller is the small computer\n"
                    "that runs your vehicle.\n"
                    "This shows its model and USB connection.\n"
                    "The board ID identifies compatible firmware."
                ),
            ),
            (
                self.connect_button,
                _("Connect your flight controller by USB.\nIts model is detected so compatible firmware\ncan be offered."),
            ),
            (
                status_label,
                _("Shows the current step, result, or error\nwhile preparing and installing firmware."),
            ),
            (
                self.custom_button,
                _(
                    "Choose an .apj firmware file on your computer.\n"
                    "APJ is ArduPilot's firmware file format.\n"
                    "The file must match your connected board.\n"
                    "You will be asked to confirm before writing."
                ),
            ),
            (
                self.upload_button,
                _(
                    "Download the selected firmware and prepare\n"
                    "to install it on your flight controller.\n"
                    "Installation replaces its current firmware.\n"
                    "You will be asked to confirm before writing.\n"
                    "Keep the USB cable connected until it finishes."
                ),
            ),
            (
                self.cancel_button,
                _("Stop before the current firmware is erased.\nCancellation is unavailable once erasing starts."),
            ),
        ):
            _show_firmware_tooltip(widget, text)

    def _create_selection_widgets(self) -> None:
        """Build the firmware type, target, and version selectors."""
        selection_frame = ttk.LabelFrame(self.main_frame, text=_("Official ArduPilot firmware"))
        selection_frame.pack(fill=tk.X, padx=12, pady=5)
        _show_firmware_tooltip(
            selection_frame,
            _(
                "Firmware is the software that runs on your\n"
                "flight controller. These releases come from\n"
                "the official ArduPilot download server."
            ),
        )
        type_label = ttk.Label(selection_frame, text=_("Firmware type:"))
        type_label.grid(row=0, column=0, sticky=tk.W, padx=8, pady=7)
        self.vehicle_type = tk.StringVar(master=self.root)
        self.type_combo = ttk.Combobox(selection_frame, textvariable=self.vehicle_type, state="disabled", width=26)
        self.type_combo.grid(row=0, column=1, sticky=tk.EW, padx=8, pady=7)
        self.type_combo.bind("<<ComboboxSelected>>", self._update_targets)
        target_label = ttk.Label(selection_frame, text=_("Firmware target:"))
        target_label.grid(row=1, column=0, sticky=tk.W, padx=8, pady=7)
        self.target = tk.StringVar(master=self.root)
        self.target_combo = ttk.Combobox(selection_frame, textvariable=self.target, state="disabled", width=26)
        self.target_combo.grid(row=1, column=1, sticky=tk.EW, padx=8, pady=7)
        self.target_combo.bind("<<ComboboxSelected>>", self._update_versions)
        version_label = ttk.Label(selection_frame, text=_("Firmware version:"))
        version_label.grid(row=2, column=0, sticky=tk.W, padx=8, pady=7)
        self.version = tk.StringVar(master=self.root)
        self.version_combo = ttk.Combobox(selection_frame, textvariable=self.version, state="disabled", width=58)
        self.version_combo.grid(row=2, column=1, sticky=tk.EW, padx=8, pady=7)
        self.version_combo.bind("<<ComboboxSelected>>", self._version_selected)
        self.refresh_button = ttk.Button(
            selection_frame, text=_("Refresh versions"), command=self.refresh_versions, state="disabled"
        )
        self.refresh_button.grid(row=3, column=1, sticky=tk.E, padx=8, pady=7)
        _show_firmware_tooltip(
            self.refresh_button,
            _("Download the latest list of available\nfirmware releases from ArduPilot.\nAn internet connection is required."),
        )
        for label, combo, text in (
            (
                type_label,
                self.type_combo,
                _(
                    "Choose the software for your vehicle.\n"
                    "Copter - multicopter is for drones with\n"
                    "several propellers. Copter - heli is for\n"
                    "helicopters. Plane is for airplanes.\n"
                    "Rover is for ground vehicles and boats.\n"
                    "Sub is for underwater vehicles.\n"
                    "Only available builds are listed."
                ),
            ),
            (
                target_label,
                self.target_combo,
                _(
                    "A target is a firmware build for a board model.\n"
                    "Only targets matching your connected board\n"
                    "are listed. Some boards have several options.\n"
                    "The target can change the available features."
                ),
            ),
            (
                version_label,
                self.version_combo,
                _(
                    "Choose which software release to install.\n"
                    "OFFICIAL is the current stable release.\n"
                    "BETA is a release being tested.\n"
                    "DEV is a development build.\n"
                    "STABLE-x.y.z is an older stable release.\n"
                    "Only versions for your chosen type and target\n"
                    "are listed."
                ),
            ),
        ):
            _show_firmware_tooltip(label, text)
            _show_firmware_tooltip(combo, text)
        selection_frame.columnconfigure(1, weight=1)

    def _refresh_board(self) -> None:
        """Read board identity from the existing MAVLink connection."""
        board_info = self.service.connected_board_info(self.flight_controller)
        if board_info is None:
            self.catalog_request_id += 1
            self.busy = False
            self._clear_catalog()
        elif self.board_id != board_info.board_id:
            self._clear_catalog()
        self._render_board(board_info)
        if board_info is None:
            self.status.set(_("Connect a flight controller to detect its board"))
            return
        self.refresh_versions()

    def _render_board(self, board_info: FirmwareBoardInfo | None) -> None:
        """Render loaded board identity and connection controls without fetching a catalog."""
        connected = board_info is not None
        self.board_id = board_info.board_id if board_info is not None else None
        if board_info is None:
            self.board_text.set(_("No flight controller connected"))
        else:
            self.board_text.set(
                _("{board_name} (APJ board ID {board_id}) — {device}").format(
                    board_name=board_info.board_name,
                    board_id=board_info.board_id,
                    device=board_info.device,
                )
            )
        self.connect_button.configure(state="disabled" if connected else "normal")
        self.refresh_button.configure(state="normal" if connected else "disabled")
        self.custom_button.configure(state="normal" if connected else "disabled")

    def _monitor_connection(self) -> None:
        """
        Record a sticky AMC restart requirement if a detected board is removed while idle.

        Reconnecting or later cancelling safely does not clear the requirement.
        """
        self._connection_timer_id = None
        try:
            if not self.uploading and not self.connecting:
                board_was_detected = self.board_id is not None
                removed = self.service.disconnect_if_serial_port_removed(self.flight_controller)
                if board_was_detected and (removed or self.flight_controller.master is None):
                    # Closing later exits AMC even if the board is reconnected in this window.
                    self.restart_required = True
                    self._refresh_board()
        finally:
            if self.root.winfo_exists():
                self._connection_timer_id = self.root.after(1000, self._monitor_connection)

    def connect(self) -> None:
        """Use the existing connection selector when no FC is connected."""
        if self.uploading or self.connecting:
            return
        connection_was_active = self.flight_controller.master is not None
        selector = _FirmwareConnectionSelector(self.root, self.flight_controller)
        previous_grab = self.root.grab_current()  # type: ignore[no-untyped-call] # Tk stubs omit this return type.
        self.connecting = True
        self.connect_button.configure(state="disabled")
        try:
            selector.root.grab_set()
            self.root.wait_window(selector.root)
        finally:
            self.connecting = False
            if self.root.winfo_exists():
                if previous_grab is not None and previous_grab.winfo_exists():
                    previous_grab.grab_set()
                self.connect_button.configure(state="normal")
                self._refresh_board()
                if not connection_was_active and self.flight_controller.master is not None:
                    # Let normal startup download parameters and defaults before configuration.
                    self.restart_required = True

    def refresh_versions(self) -> None:
        """Fetch the firmware manifest without blocking the GUI."""
        if self.board_id is None or self.busy:
            return
        self.busy = True
        self.refresh_button.configure(state="disabled")
        self.upload_button.configure(state="disabled")
        self.status.set(_("Loading available firmware versions…"))
        board_id = self.board_id
        self.catalog_request_id += 1
        request_id = self.catalog_request_id

        def worker() -> None:
            try:
                releases = self.service.releases_for_connected_board(board_id)
                self.events.put(("catalog", request_id, releases))
            except Exception as exc:  # pylint: disable=broad-exception-caught # Relay worker failures to the UI.
                self.events.put(("catalog_error", request_id, str(exc)))

        self.worker_launcher(worker)

    def _show_catalog(self, releases: list[FirmwareRelease]) -> None:
        self.busy = False
        self.releases = releases
        self.refresh_button.configure(state="normal")
        self.custom_button.configure(state="normal")
        types = firmware_types(releases)
        self.type_combo.configure(values=types, state="readonly" if types else "disabled")
        if types:
            board_info = self.service.connected_board_info(self.flight_controller)
            current = board_info.recommended_vehicle_type if board_info is not None else ""
            self.vehicle_type.set(preferred_firmware_type(types, current))
            self._update_targets()
            self.status.set(_("Select a firmware type, target and version for the detected board"))
        else:
            self.vehicle_type.set("")
            self.target.set("")
            self.target_combo.configure(values=(), state="disabled")
            self.version.set("")
            self.version_combo.configure(values=(), state="disabled")
            self.status.set(_("No APJ firmware is listed for this board ID"))

    def _clear_catalog(self) -> None:
        """Remove choices that belong to a previous or disconnected board."""
        self.releases = []
        self.vehicle_type.set("")
        self.type_combo.configure(values=(), state="disabled")
        self.target.set("")
        self.target_combo.configure(values=(), state="disabled")
        self.version.set("")
        self.version_combo.configure(values=(), state="disabled")
        self.upload_button.configure(state="disabled")
        self.custom_button.configure(state="disabled")

    def _update_targets(self, _event: tk.Event | None = None) -> None:
        """Show only platforms listed for this board and firmware type."""
        targets = firmware_targets(self.releases, self.vehicle_type.get())
        self.target_combo.configure(values=targets, state="readonly" if targets else "disabled")
        board_info = self.service.connected_board_info(self.flight_controller)
        preferred = board_info.board_name if board_info is not None else ""
        self.target.set(preferred_board_target(targets, preferred))
        self._update_versions()

    def _update_versions(self, _event: tk.Event | None = None) -> None:
        choices = firmware_versions(self.releases, self.vehicle_type.get(), self.target.get())
        self.version_combo.configure(values=choices, state="readonly" if choices else "disabled")
        self.version.set("")
        self.upload_button.configure(state="disabled")

    def _version_selected(self, _event: tk.Event | None = None) -> None:
        self.upload_button.configure(state="normal" if self._selected_release() is not None and not self.busy else "disabled")

    def _selected_release(self) -> FirmwareRelease | None:
        return find_firmware_release(self.releases, self.vehicle_type.get(), self.target.get(), self.version.get())

    def start_upload(self) -> None:
        """Download, validate, confirm and flash the selected release in a worker."""
        release = self._selected_release()
        if release is None or self.busy:
            return
        if not messagebox.askyesno(
            _("Upload ArduPilot firmware"),
            _(
                "Download {release} for board ID {board_id} and prepare to flash it?\n\n"
                "After a successful or failed upload, closing this window closes AMC. "
                "Restart AMC to continue configuration. Cancelling before erase keeps AMC open "
                "unless a detected board was unplugged while idle."
            ).format(release=release.label, board_id=release.board_id),
            parent=self.root,
        ):
            return
        self._start_upload(
            release.label,
            lambda callbacks: self.service.upload_release(self.flight_controller, release, callbacks=callbacks),
        )

    def select_custom_firmware(self, apj_path: Path | None = None) -> None:
        """Select a local APJ and upload it after the same two confirmations."""
        if self.uploading:
            return
        board_info = self.service.connected_board_info(self.flight_controller)
        if board_info is None:
            return
        selected = (
            str(apj_path)
            if apj_path is not None
            else filedialog.askopenfilename(
                parent=self.root,
                title=_("Select APJ firmware file"),
                filetypes=[(_("ArduPilot firmware"), "*.apj"), (_("All files"), "*.*")],
            )
        )
        if not selected:
            return
        path = Path(selected)
        if not messagebox.askyesno(
            _("Upload ArduPilot firmware"),
            _(
                "Use local firmware {file} for board ID {board_id} and prepare to flash it?\n\n"
                "After a successful or failed upload, closing this window closes AMC. "
                "Restart AMC to continue configuration. Cancelling before erase keeps AMC open "
                "unless a detected board was unplugged while idle."
            ).format(file=path, board_id=board_info.board_id),
            parent=self.root,
        ):
            return
        self._start_upload(
            str(path),
            lambda callbacks: self.service.upload_custom_file(self.flight_controller, path, callbacks=callbacks),
        )

    def _start_upload(self, label: str, upload: Callable[[FirmwareUploadCallbacks], BootloaderInfo]) -> None:
        """Run either firmware source through shared progress and confirmation UI."""
        self.catalog_request_id += 1
        self.cancelled.clear()
        self.busy = True
        self.uploading = True
        self._reset_progress_bars()
        self.refresh_button.configure(state="disabled")
        self.upload_button.configure(state="disabled")
        self.custom_button.configure(state="disabled")
        self.connect_button.configure(state="disabled")
        self.cancel_button.configure(state="normal")

        def confirm(image: FirmwareImage, bootloader: BootloaderInfo) -> bool:
            reply = Event()
            result: list[bool] = []
            self.events.put(("confirm", label, image.metadata.apj_sha256, bootloader.board_id, reply, result))
            return bool(reply.wait(timeout=300) and result and result[0])

        def progress(stage: UploadStage, completed: int, total: int) -> None:
            self.events.put(("progress", stage, completed, total))

        def status(status_text: str) -> None:
            self.events.put(("status", status_text))

        def worker() -> None:
            try:
                upload(
                    FirmwareUploadCallbacks(
                        cancellation_requested=self.cancelled.is_set,
                        confirmation_requested=confirm,
                        progress_callback=progress,
                        status_callback=status,
                    ),
                )
                self.events.put(("done",))
            except Exception as exc:  # pylint: disable=broad-exception-caught # Relay worker failures to the UI.
                self.events.put(("error", exc))

        self.worker_launcher(worker)

    def _poll_events(self) -> None:
        """Drain worker events on the Tk thread and schedule the next poll."""
        self._event_poll_id = None
        try:
            while True:
                try:
                    event = self.events.get_nowait()
                except Empty:
                    break
                self._handle_event(event)
        finally:
            if self.root.winfo_exists():
                self._event_poll_id = self.root.after(100, self._poll_events)

    def _handle_event(self, event: tuple) -> None:
        """Apply one worker event without depending on polling or timers."""
        kind = event[0]
        if kind in {"catalog", "catalog_error"}:
            if event[1] != self.catalog_request_id or self.uploading:
                return
            if kind == "catalog":
                self._show_catalog(event[2])
            else:
                self._finish(event[2])
                messagebox.showerror(_("Firmware catalog error"), event[2], parent=self.root)
        elif kind == "status":
            self.status.set(event[1])
        elif kind == "progress":
            _event_name, stage, completed, total = event
            self.status.set(_("Firmware upload: {stage}").format(stage=self._stage_label(stage)))
            if stage == UploadStage.ERASING:
                self.cancel_button.configure(state="disabled")
            self._update_progress(stage, completed, total)
        elif kind == "confirm":
            _event_name, label, digest, bootloader_id, reply, result = event
            self._handle_confirmation(label, digest, bootloader_id, reply, result)
        elif kind == "done":
            self._handle_upload_result(None)
        elif kind == "error":
            self._handle_upload_result(event[1])

    def _handle_confirmation(self, label: str, digest: str, board_id: int, reply: Event, result: list[bool]) -> None:
        """Prompt on the Tk thread and always release the waiting worker."""
        try:
            result.append(
                messagebox.askyesno(
                    _("Confirm firmware flash"),
                    _("Erase and flash {release}?\n\nBootloader board ID: {board_id}\nAPJ SHA-256: {digest}").format(
                        release=label, board_id=board_id, digest=digest
                    ),
                    parent=self.root,
                )
            )
        except Exception as exc:  # pylint: disable=broad-exception-caught # Tk dialog failures must release the worker.
            result.append(False)
            self.status.set(str(exc))
        finally:
            reply.set()

    def _handle_upload_result(self, error: Exception | None) -> None:
        """Record the sticky restart requirement before rendering the upload result."""
        cancelled = isinstance(error, FirmwareUploadCancelledError)
        if not cancelled:
            self.restart_required = True
        status = str(error) if error is not None else _("Firmware upload completed and flight controller reconnected")
        self._finish(status)
        if cancelled:
            messagebox.showinfo(_("Firmware upload cancelled"), status, parent=self.root)
        else:
            status += "\n\n" + _("Close this window and restart AMC before continuing configuration.")
            if error is None:
                messagebox.showinfo(_("Upload ArduPilot firmware"), status, parent=self.root)
            else:
                messagebox.showerror(_("Firmware upload failed"), status, parent=self.root)

    def _finish(self, status: str) -> None:
        self.busy = False
        self.uploading = False
        self.status.set(status)
        self._stop_progress_animations()
        self.cancel_button.configure(state="disabled")
        board_info = self.service.connected_board_info(self.flight_controller)
        if board_info is None or self.board_id != board_info.board_id:
            self._clear_catalog()
        self._render_board(board_info)
        self.upload_button.configure(
            state="normal" if board_info is not None and self._selected_release() is not None else "disabled"
        )

    @staticmethod
    def _stage_label(stage: UploadStage) -> str:
        """Return a translated, readable label for every upload stage."""
        return {
            UploadStage.IDLE: _("Idle"),
            UploadStage.INSPECTING: _("Inspecting firmware"),
            UploadStage.AWAITING_CONFIRMATION: _("Awaiting confirmation"),
            UploadStage.ENTERING_BOOTLOADER: _("Entering bootloader"),
            UploadStage.IDENTIFYING: _("Identifying board"),
            UploadStage.ERASING: _("Erasing firmware"),
            UploadStage.PROGRAMMING: _("Programming firmware"),
            UploadStage.VERIFYING: _("Verifying firmware"),
            UploadStage.REBOOTING: _("Rebooting board"),
            UploadStage.RECONNECTING: _("Reconnecting to board"),
            UploadStage.COMPLETED: _("Completed"),
            UploadStage.FAILED: _("Failed"),
            UploadStage.CANCELLED: _("Cancelled"),
        }[stage]

    def _create_progress_bars(self) -> None:
        """Create separate feedback bars for erase, programming and verification."""
        for stage, label, tooltip in (
            (
                UploadStage.ERASING,
                _("Erase"),
                _(
                    "Removing the old firmware from the board\n"
                    "before writing the selected firmware.\n"
                    "Keep the USB cable connected."
                ),
            ),
            (
                UploadStage.PROGRAMMING,
                _("Program"),
                _("Writing the selected firmware to the board.\nKeep the USB cable connected."),
            ),
            (
                UploadStage.VERIFYING,
                _("Verify"),
                _("Checking that the firmware was written\ncorrectly before restarting the board."),
            ),
        ):
            row = ttk.Frame(self.main_frame)
            row.pack(fill=tk.X, padx=18, pady=2)
            stage_label = ttk.Label(row, text=label, width=10)
            stage_label.pack(side=tk.LEFT)
            _show_firmware_tooltip(stage_label, tooltip)
            progress_indicator = ttk.Progressbar(row, mode="determinate", maximum=100)
            progress_indicator.pack(side=tk.LEFT, fill=tk.X, expand=True)
            _show_firmware_tooltip(progress_indicator, tooltip)
            self.progress_bars[stage] = progress_indicator

    def _reset_progress_bars(self) -> None:
        """Clear progress values before starting another upload."""
        self._stop_progress_animations()
        for progress_indicator in self.progress_bars.values():
            progress_indicator.configure(mode="determinate", value=0)

    def _stop_progress_animations(self) -> None:
        """Stop any indeterminate bars when a stage or operation ends."""
        for progress_indicator in self.progress_bars.values():
            if str(progress_indicator.cget("mode")) == "indeterminate":
                progress_indicator.stop()
                progress_indicator.configure(mode="determinate")
        self._active_progress_stage = None

    def _update_progress(self, stage: UploadStage, completed: int, total: int) -> None:
        """Show measured progress, or animate while the bootloader gives no estimate."""
        progress_indicator = self.progress_bars.get(stage)
        if progress_indicator is None:
            return
        if self._active_progress_stage != stage:
            self._stop_progress_animations()
            self._active_progress_stage = stage
        if total == 0:
            if str(progress_indicator.cget("mode")) != "indeterminate":
                progress_indicator.configure(mode="indeterminate")
                progress_indicator.start(12)
            return
        if str(progress_indicator.cget("mode")) == "indeterminate":
            progress_indicator.stop()
        progress_indicator.configure(mode="determinate", value=max(0, min(100, 100 * completed / max(total, 1))))
        if completed >= total:
            self._active_progress_stage = None

    def close(self) -> None:
        """Keep the window alive while a bootloader operation is running."""
        if self.uploading:
            messagebox.showinfo(
                _("Upload ArduPilot firmware"), _("Wait for the current operation to finish"), parent=self.root
            )
            return
        if self.owns_connection:
            self.flight_controller.disconnect()
        if self._connection_timer_id is not None:
            with suppress(tk.TclError):
                self.root.after_cancel(self._connection_timer_id)
            self._connection_timer_id = None
        if self._event_poll_id is not None:
            with suppress(tk.TclError):
                self.root.after_cancel(self._event_poll_id)
            self._event_poll_id = None
        self.root.destroy()


def create_argument_parser() -> ArgumentParser:  # pragma: no cover
    """Create the argument parser for the standalone firmware upload program."""
    parser = create_parameter_application_argument_parser(_("Upload ArduPilot firmware"))
    parser.add_argument(
        "--custom-apj",
        type=Path,
        metavar="PATH",
        help=_("Upload this local APJ firmware file after connecting (with confirmation)."),
    ).completer = FilesCompleter(allowednames=(".apj",))  # type: ignore[attr-defined]
    return parser


def main() -> None:  # pragma: no cover
    """Connect to a flight controller and open the firmware upload tool."""
    parser = create_argument_parser()
    args = parser.parse_args()
    configure_standalone_logging(args)
    flight_controller = FlightController(reboot_time=args.reboot_time, baudrate=args.baudrate)
    try:
        if not connect_standalone_flight_controller(args, flight_controller):
            return
        window = FirmwareUploadWindow(flight_controller)
        if args.custom_apj is not None:
            # Use the same board check and both confirmations as a file chosen in the UI.
            window.root.after(100, lambda: window.select_custom_firmware(args.custom_apj))
        window.root.mainloop()
    finally:
        flight_controller.disconnect()


if __name__ == "__main__":  # pragma: no cover
    main()
