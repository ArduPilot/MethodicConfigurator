"""
Skybrush Log Analysis window.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import tkinter as tk
from collections.abc import Callable
from contextlib import suppress
from logging import error as logging_error
from pathlib import Path
from tkinter import Toplevel, messagebox, ttk
from typing import TYPE_CHECKING, Any, cast

from skybrush_log_analyzer.analysis import compact
from skybrush_log_analyzer.api_client import APIClient, calculate_file_hash
from skybrush_log_analyzer.config import Config
from skybrush_log_analyzer.errors import (
    AccountUnreachable,
    APIUnreachable,
    ApplicationErrorWithMessage,
    ApplicationErrorWithURL,
    BadRequest,
    ConfigError,
    InvalidAPIKey,
    NotFound,
    ResponseParsingFailed,
    ServerError,
    Unauthenticated,
)

from ardupilot_methodic_configurator import _, __version__
from ardupilot_methodic_configurator.backend_internet import webbrowser_open_url
from ardupilot_methodic_configurator.formatting import format_elapsed_time
from ardupilot_methodic_configurator.frontend_tkinter_base_window import BaseWindow
from ardupilot_methodic_configurator.frontend_tkinter_file_browser_tasks import BackgroundTaskRunner
from ardupilot_methodic_configurator.frontend_tkinter_show import show_tooltip

if TYPE_CHECKING:
    from skybrush_log_analyzer.typing import SuggestionCategory

#: Display color for each test-case status returned by the Skybrush API.
_STATUS_COLOR = {
    "FAIL": "red3",
    "WARN": "dark orange",
    "INFO": "#0055cc",
    "PASS": "dark green",
    "SKIP": "gray50",
    "NOT_APPLICABLE": "gray50",
}

#: Prefix prepended to every console (logging) line emitted by the Skybrush log analysis integration.
_LOG_TAG = "[Skybrush log analysis]"


# ---------------- Skybrush API error messages ----------------


_SKYBRUSH_ERROR_MESSAGES: tuple[tuple[type[Exception], str], ...] = (
    (
        Unauthenticated,
        _("Not logged in. Use the Log in button to configure the API key."),
    ),
    (InvalidAPIKey, _("The Skybrush API key is invalid or has been revoked. Create a new one at {account_url}.")),
    (AccountUnreachable, _("Could not reach the Skybrush Account server at {account_url}.")),
    (APIUnreachable, _("Could not reach the Skybrush API: {message}")),
    (ConfigError, _("Could not read or write the 'skybrush-log-analyzer' configuration: {message}")),
    (BadRequest, _("The Skybrush API rejected the request: {message}")),
    (ServerError, _("The Skybrush API is currently unavailable.")),
    (ResponseParsingFailed, _("The Skybrush API returned an unexpected response.")),
)


def _skybrush_error_message(error: Exception) -> str:
    """Translate a Skybrush API error into a localized, user-facing message."""
    for error_type, message_template in _SKYBRUSH_ERROR_MESSAGES:
        if isinstance(error, error_type):
            details = error.message if isinstance(error, ApplicationErrorWithMessage) else str(error)
            account_url = error.url if isinstance(error, ApplicationErrorWithURL) else ""
            return message_template.format(message=details, account_url=account_url)
    return _("Skybrush API request failed: {error}").format(error=error)


# ---------------- display formatting helpers ----------------


def _format_api_version(version: dict[str, Any]) -> str:
    """Format the Skybrush API version info into one display line."""
    return _("Skybrush API version: {version}").format(version=version.get("app_version") or "?")


def _format_test_message(message: dict[str, Any]) -> tuple[str, str]:
    """Render a test-case message into a plain part plus a bold trailing value-with-unit part."""
    text = str(message.get("text", ""))
    timestamp = message.get("timestamp")
    if isinstance(timestamp, (int, float)) and not isinstance(timestamp, bool):
        text = f"[{format_elapsed_time(timestamp)}] {text}"
    elif isinstance(timestamp, str) and timestamp.strip():
        text = f"[{timestamp.strip()}] {text}"
    value = message.get("value")
    if value is None or str(value) == "":
        return text, ""
    bold = f" {value}"
    unit = message.get("unit")
    if isinstance(unit, str) and unit.strip():
        bold += f" {unit}"
    return f"{text}:", bold


# ---------------- feedback dialog ----------------


class FeedbackDialog:  # pylint: disable=too-few-public-methods,too-many-instance-attributes
    """Modal dialog that collects user feedback and submits it to the Skybrush team."""

    #: Categories accepted by the Skybrush suggestion endpoint, most relevant for analysis results first.
    CATEGORIES: "tuple[SuggestionCategory, ...]" = ("bug", "test_case", "improvement", "feature", "other")

    def __init__(
        self,
        parent: tk.Tk | Toplevel,
        submit: Callable[["SuggestionCategory", str, str, Callable[[object | None, Exception | None], None]], bool],
    ) -> None:
        self._parent = parent
        self._submit = submit
        self._root = Toplevel(parent)
        self._root.title(_("Send feedback"))
        self._root.geometry(f"+{parent.winfo_rootx() + 80}+{parent.winfo_rooty() + 80}")

        instructions = _(
            "Technical, self-contained feedback helps the Skybrush team the most.\n"
            "Describe what you did, what you expected, and what actually happened.\n"
            "Reference affected test names, measured values and log messages where relevant.\n"
            "If you miss a check, describe the new test that should examine the log (category 'test_case').\n"
            "Never include secrets such as passwords, tokens or API keys.\n"
            "The flight log name and its hash, plus version info, are appended automatically."
        )
        body = ttk.Frame(self._root, padding=(16, 12, 16, 12))
        body.pack(fill=tk.BOTH, expand=True)

        header = ttk.Frame(body)
        header.pack(side=tk.TOP, fill=tk.X)
        ttk.Label(header, text=_("Send feedback"), font=("TkDefaultFont", 14, "bold")).pack(anchor=tk.W)
        ttk.Label(header, text=instructions, foreground="gray50").pack(anchor=tk.W, pady=(4, 10))

        ttk.Label(body, text=_("Category")).pack(anchor=tk.W)
        self._category_box = ttk.Combobox(body, values=self.CATEGORIES, state="readonly", width=20)
        self._category_box.current(0)
        self._category_box.pack(anchor=tk.W, fill=tk.X, pady=(0, 8))

        ttk.Label(body, text=_("Title")).pack(anchor=tk.W)
        self._title_entry = ttk.Entry(body)
        self._title_entry.pack(anchor=tk.W, fill=tk.X, pady=(0, 8))

        ttk.Label(body, text=_("Description")).pack(anchor=tk.W)
        description_row = ttk.Frame(body)
        description_row.pack(anchor=tk.W, fill=tk.BOTH, expand=True, pady=(0, 4))
        self._description_text = tk.Text(description_row, wrap=tk.WORD, height=8)
        description_scrollbar = ttk.Scrollbar(description_row, orient=tk.VERTICAL, command=self._description_text.yview)
        self._description_text.configure(yscrollcommand=description_scrollbar.set)
        description_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self._description_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        actions = ttk.Frame(body)
        actions.pack(side=tk.BOTTOM, fill=tk.X)
        self._progress_label = ttk.Label(actions, text="")
        self._progress_label.pack(side=tk.LEFT)
        ttk.Button(actions, text=_("Cancel"), command=self._root.destroy).pack(side=tk.RIGHT)
        self._submit_button = ttk.Button(actions, text=_("Submit"), command=self._on_submit_click)
        self._submit_button.pack(side=tk.RIGHT, padx=(0, 8))
        self._title_entry.focus_set()

    def show(self) -> None:
        """Show the dialog modally."""
        self._root.transient(self._parent)
        self._root.grab_set()
        self._root.focus_set()
        self._parent.wait_window(self._root)

    def _on_submit_click(self) -> None:
        """Validate the input and hand the suggestion over to the background submission runner."""
        title = self._title_entry.get().strip()
        description = self._description_text.get("1.0", tk.END).strip()
        if not 1 <= len(title) <= 100:
            messagebox.showerror(
                _("Send feedback"), _("Please provide a title between 1 and 100 characters."), parent=self._root
            )
            return
        if not description:
            messagebox.showerror(
                _("Send feedback"), _("Please describe the issue in the description field."), parent=self._root
            )
            return
        category = self.CATEGORIES[self._category_box.current()]
        if not self._submit(category, title, description, self._on_submitted):
            return
        self._submit_button.configure(state="disabled")
        self._progress_label.configure(text=_("Sending feedback to the Skybrush team..."))

    def _on_submitted(self, result: object | None, error: Exception | None) -> None:
        if not self._root.winfo_exists():
            return
        self._submit_button.configure(state="normal")
        self._progress_label.configure(text="")
        if error is not None:
            messagebox.showerror(_("Send feedback"), _skybrush_error_message(error), parent=self._root)
            return
        suggestion_id = result.get("id") if isinstance(result, dict) else None
        detail = _("Thank you for your feedback! The Skybrush team will review your suggestion.")
        if isinstance(suggestion_id, int):
            detail = f"{detail} (#{suggestion_id})"
        messagebox.showinfo(_("Send feedback"), detail, parent=self._root)
        self._root.destroy()


# ---------------- login form ----------------


class LoginForm(ttk.Frame):  # pylint: disable=too-many-ancestors
    """Form that collects the Skybrush API key and passes it to the login callback."""

    def __init__(
        self,
        parent: tk.Misc,
        login: Callable[[str, Callable[[object | None, Exception | None], None]], bool],
        account_url: str,
    ) -> None:
        super().__init__(parent, padding=(16, 12, 16, 12))
        self._login = login
        self._account_url = account_url

        instructions = _(
            "A Skybrush API key is required to analyze flight logs.\n"
            "Generate it in the Skybrush Account developer area, then paste it here."
        )

        header = ttk.Frame(self)
        header.pack(side=tk.TOP, fill=tk.X)
        ttk.Label(header, text=_("Log in"), font=("TkDefaultFont", 14, "bold")).pack(anchor=tk.W)
        ttk.Label(header, text=instructions, foreground="gray50").pack(anchor=tk.W, pady=(4, 10))

        developer_row = ttk.Frame(self)
        developer_row.pack(side=tk.TOP, fill=tk.X)
        ttk.Button(
            developer_row,
            text=_("Open Skybrush Account"),
            command=lambda: webbrowser_open_url(self._account_url),
        ).pack(side=tk.LEFT)
        ttk.Label(developer_row, text=_("Create or manage your API keys there"), foreground="gray50").pack(
            side=tk.LEFT, padx=(8, 0)
        )

        ttk.Label(self, text=_("API key")).pack(anchor=tk.W, pady=(12, 0))
        self._key_entry = ttk.Entry(self, show="*", width=50)
        self._key_entry.pack(anchor=tk.W, fill=tk.X, pady=(0, 8))

        actions = ttk.Frame(self)
        actions.pack(side=tk.BOTTOM, fill=tk.X)
        self._progress_label = ttk.Label(actions, text="")
        self._progress_label.pack(side=tk.LEFT)
        self._login_button = ttk.Button(actions, text=_("Log in"), command=self._on_login_click)
        self._login_button.pack(side=tk.RIGHT)

    def focus_key_entry(self) -> None:
        """Move the keyboard focus to the API key field."""
        self._key_entry.focus_set()

    def _on_login_click(self) -> None:
        """Validate the input and start the background key validation and storing."""
        api_key = self._key_entry.get().strip()
        if not api_key:
            messagebox.showerror(_("Log in"), _("Please paste your API key."), parent=self)
            return
        if not self._login(api_key, self._on_login_done):
            return
        self._login_button.configure(state="disabled")
        self._progress_label.configure(text=_("Validating the API key and logging in..."))

    def _on_login_done(self, _result: object | None, error: Exception | None) -> None:
        if not self.winfo_exists():
            return
        self._login_button.configure(state="normal")
        self._progress_label.configure(text="")
        if error is not None:
            messagebox.showerror(_("Log in"), _skybrush_error_message(error), parent=self)
            return
        self._key_entry.delete(0, tk.END)


class SkybrushLogAnalysisWindow(BaseWindow):  # pylint: disable=too-many-instance-attributes
    """Main window of the Skybrush log analysis integration."""

    def __init__(self, root_tk: tk.Tk | tk.Toplevel, logfile: str) -> None:
        super().__init__(root_tk)
        self.logfile = logfile
        self._analysis_runner = BackgroundTaskRunner(self._schedule_while_open)
        self._web_login_runner = BackgroundTaskRunner(self._schedule_while_open)
        self._auth_runner = BackgroundTaskRunner(self._schedule_while_open)
        self._feedback_runner = BackgroundTaskRunner(self._schedule_while_open)
        self._login_runner = BackgroundTaskRunner(self._schedule_while_open)
        self._config = Config.load()
        #: Client of the log-in session; None while logged out.
        self._client: APIClient | None = APIClient(self._config) if self._config.api_key else None
        #: API version of the log-in session; empty until fetched successfully.
        self._version_info: dict[str, Any] = {}
        self._find_matches: list[tuple[str, str]] = []
        self._find_index = -1
        self._last_find_query: str | None = None
        self._find_bar_visible = False

        self.root.title(_("Skybrush Log Analysis"))
        self.root.geometry(self.calculate_scaled_geometry(1050, 800))
        self.center_window(self.root, root_tk)
        self.root.resizable(width=True, height=True)

        self._build_header()
        self._build_footer()
        self._build_results_area()
        self._build_find_bar()
        self._login_form = LoginForm(self.main_frame, self._start_login, self._config.account_url)
        self._update_login_state()
        self._start_header_status_checks()

    def _schedule_while_open(self, delay_ms: int, callback: Callable[[], None]) -> object:
        """Schedule the callback on the Tk event loop; it is skipped once the window is closed."""
        return self.root.after(delay_ms, lambda: callback() if self.root.winfo_exists() else None)

    # ---------------- window layout ----------------

    def _build_header(self) -> None:
        header = ttk.Frame(self.main_frame)
        header.pack(side=tk.TOP, fill=tk.X, padx=20, pady=(16, 8))

        left_column = ttk.Frame(header)
        left_column.pack(side=tk.LEFT, anchor=tk.NW)

        ttk.Label(left_column, text=_("Skybrush Log Analysis"), font=("TkDefaultFont", 16, "bold")).pack(anchor=tk.W)
        ttk.Label(
            left_column,
            text=_("Selected log: {filename}").format(filename=Path(self.logfile).name),
            font=("TkDefaultFont", 13),
        ).pack(anchor=tk.W, pady=(8, 0))

        self._version_label = ttk.Label(
            left_column, text=_("Skybrush API version unknown"), font=("TkDefaultFont", 12), foreground="gray50"
        )
        self._version_label.pack(anchor=tk.W, pady=(4, 0))
        self._auth_status_label = ttk.Label(
            left_column,
            text=_("Checking log-in status..."),
            font=("TkDefaultFont", 12),
            foreground="gray50",
            # Keep the status line narrow: an unwrapped 'not logged in' error message would widen the
            # left column beyond the window width and the packer would then clip the button row.
            wraplength=450,
        )
        self._auth_status_label.pack(anchor=tk.W)

        actions = ttk.Frame(header)
        actions.pack(side=tk.RIGHT, fill=tk.Y, anchor=tk.NE)

        buttons_row = ttk.Frame(actions)
        buttons_row.pack(side=tk.TOP, anchor=tk.NE)

        self._logout_button = ttk.Button(buttons_row, text=_("Log out from Skybrush Account"), command=self._apply_logout)
        self._logout_button.pack(side=tk.LEFT)
        show_tooltip(self._logout_button, _("Log out of the Skybrush analysis service and remove the stored API key"))

        self._run_analysis_button = ttk.Button(buttons_row, text=_("Analyze"), command=self._on_run_analysis_click)
        self._run_analysis_button.pack(side=tk.LEFT, padx=(8, 0))
        show_tooltip(
            self._run_analysis_button,
            _("Upload the selected log to the Skybrush API and display the results"),
        )

        self._open_web_button = ttk.Button(
            buttons_row, text=_("Open in Skybrush Log Analyzer"), command=self._on_open_in_browser_click
        )
        self._open_web_button.pack(side=tk.LEFT, padx=(8, 0))
        show_tooltip(
            self._open_web_button,
            _("Open the analysis of the selected log in the Skybrush Log Analyzer web application"),
        )

        self._feedback_button = ttk.Button(buttons_row, text=_("Send feedback"), command=self._on_send_feedback_click)
        self._feedback_button.pack(side=tk.LEFT, padx=(8, 0))
        show_tooltip(
            self._feedback_button,
            _("Report a suspicious analysis result or suggest an improvement directly to the Skybrush team"),
        )

        # Status/command feedback right-aligned in the header, bottom-aligned with the log-in status line.
        self.status_label = ttk.Label(actions, text="", anchor=tk.E, justify="right", wraplength=400)
        self.status_label.pack(side=tk.BOTTOM, anchor=tk.SE)
        # Wrap no wider than the button row above it.
        self.root.update_idletasks()
        self.status_label.configure(wraplength=max(buttons_row.winfo_reqwidth(), 200))

    def _build_footer(self) -> None:
        footer = ttk.Frame(self.main_frame)
        footer.pack(side=tk.BOTTOM, fill=tk.X, padx=20, pady=(0, 14))
        ttk.Button(footer, text=_("Close"), command=self.root.destroy).pack(side=tk.RIGHT)

    def _build_results_area(self) -> None:
        results_row = ttk.Frame(self.main_frame)
        self._results_row = results_row

        self.results_text = tk.Text(
            results_row,
            wrap=tk.WORD,
            height=20,
            state=tk.DISABLED,
            font=("TkDefaultFont", 12),
            padx=10,
            pady=8,
        )
        scrollbar = ttk.Scrollbar(results_row, orient=tk.VERTICAL, command=self.results_text.yview)
        self.results_text.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.results_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        for status, color in _STATUS_COLOR.items():
            self.results_text.tag_configure(f"status_{status}", foreground=color)
        self.results_text.tag_configure("summary", font=("TkDefaultFont", 12, "bold"))
        self.results_text.tag_configure("heading", font=("TkDefaultFont", 14, "bold"))
        self.results_text.tag_configure("bold", font=("TkDefaultFont", 12, "bold"))
        self.results_text.tag_configure("muted", foreground="gray50")
        self.results_text.tag_configure("bullet", foreground="#666666")
        self.results_text.tag_configure("error", foreground="red3")
        self.results_text.tag_configure("search_all", background="#fff3a0")
        self.results_text.tag_configure("search_current", background="#ffb36b")

        self.root.bind("<Control-f>", self._show_find_bar)
        self.root.bind("<F3>", self._on_find_next_key)
        self.root.bind("<Shift-F3>", self._on_find_prev_key)
        self.root.bind("<Escape>", self._on_escape_key)

        self._replace_results_text()
        self._append_results_text(_("No analysis results yet - click 'Analyze' to analyze the selected log.\n"), "muted")
        self._finish_results_text()

    def _build_find_bar(self) -> None:
        """Build the browser-like find bar; it stays unpacked until shown."""
        self._find_bar = ttk.Frame(self.main_frame)
        ttk.Label(self._find_bar, text=_("Find:")).pack(side=tk.LEFT)
        self._find_entry = ttk.Entry(self._find_bar)
        self._find_entry.pack(side=tk.LEFT, padx=(6, 8), fill=tk.X, expand=True)
        self._find_count_label = ttk.Label(self._find_bar, foreground="gray50")
        self._find_count_label.pack(side=tk.LEFT)
        self._find_entry.bind("<Return>", lambda _event: self._jump_to_match(1))
        self._find_entry.bind("<Shift-Return>", lambda _event: self._jump_to_match(-1))
        self._find_entry.bind("<Escape>", lambda _event: self._hide_find_bar())
        self._find_entry.bind("<KeyRelease>", self._on_find_query_changed)
        ttk.Button(self._find_bar, text="✕", width=3, command=self._hide_find_bar).pack(side=tk.RIGHT, padx=(6, 0))
        ttk.Button(self._find_bar, text="↓", width=3, command=lambda: self._jump_to_match(1)).pack(side=tk.RIGHT)
        ttk.Button(self._find_bar, text="↑", width=3, command=lambda: self._jump_to_match(-1)).pack(side=tk.RIGHT)

    # ---------------- results text helpers ----------------

    def _set_status(self, text: str) -> None:
        """Update the status line."""
        self.status_label.configure(text=text)

    def _replace_results_text(self) -> None:
        self.results_text.configure(state=tk.NORMAL)
        self.results_text.delete("1.0", tk.END)

    def _append_results_text(self, text: str, tags: str = "") -> None:
        """Append text with the given space-separated tag names."""
        self.results_text.insert(tk.END, text, tags)

    def _finish_results_text(self) -> None:
        self.results_text.configure(state=tk.DISABLED)
        self.results_text.yview_moveto(0.0)
        if self._find_bar_visible:
            self._refresh_find_matches(jump=False)

    # ---------------- find bar (Ctrl-F) ----------------

    def _show_find_bar(self, _event: object | None = None) -> None:
        """Show the browser-like find bar above the results text and focus its field."""
        if self._client is None:
            return
        self._find_bar.pack(side=tk.TOP, fill=tk.X, before=self._results_row, padx=20, pady=(0, 8))
        self._find_bar_visible = True
        self._find_entry.focus_set()
        self._find_entry.select_range(0, tk.END)
        self._refresh_find_matches(jump=True)

    def _hide_find_bar(self) -> None:
        """Remove the find bar and all of its highlights."""
        self._find_bar_visible = False
        self._find_index = -1
        self._find_matches = []
        self._clear_find_highlights()
        self._find_bar.pack_forget()

    def _clear_find_highlights(self) -> None:
        self.results_text.tag_remove("search_all", "1.0", tk.END)
        self.results_text.tag_remove("search_current", "1.0", tk.END)
        self.results_text.tag_remove("sel", "1.0", tk.END)
        self._find_count_label.configure(text="")

    def _on_find_query_changed(self, _event: "tk.Event[tk.Entry]") -> None:
        """Re-run the search only when the query text actually changed (e.g. not on F3/arrow key releases)."""
        if self._find_entry.get() != self._last_find_query:
            self._refresh_find_matches(jump=True)

    def _refresh_find_matches(self, jump: bool) -> None:
        """Locate and highlight all occurrences of the find-bar query."""
        self._clear_find_highlights()
        self._find_matches = []
        self._find_index = -1
        query = self._find_entry.get()
        self._last_find_query = query
        if not query:
            return
        widget = self.results_text
        matches: list[tuple[str, str]] = []
        start = str(widget.search(query, "1.0", nocase=True, stopindex=tk.END))
        while start:
            end = f"{start}+{len(query)}c"
            matches.append((start, end))
            widget.tag_add("search_all", start, end)
            start = str(widget.search(query, end, nocase=True, stopindex=tk.END))
        self._find_matches = matches
        if not matches:
            self._find_count_label.configure(text=_("No matches"))
            return
        if jump:
            self._jump_to_match(1)

    def _jump_to_match(self, step: int) -> None:
        """Select, highlight and scroll to the next/previous match, wrapping around."""
        total = len(self._find_matches)
        if total == 0:
            return
        self._find_index = (self._find_index + step) % total
        start, end = self._find_matches[self._find_index]
        self.results_text.tag_remove("search_current", "1.0", tk.END)
        self.results_text.tag_add("search_current", start, end)
        self.results_text.tag_remove("sel", "1.0", tk.END)
        self.results_text.tag_add("sel", start, end)
        self.results_text.see(end)
        self.results_text.see(start)
        self._find_count_label.configure(text=f"{self._find_index + 1}/{total}")

    def _on_find_next_key(self, _event: object) -> None:
        if self._find_bar_visible:
            self._jump_to_match(1)

    def _on_find_prev_key(self, _event: object) -> None:
        if self._find_bar_visible:
            self._jump_to_match(-1)

    def _on_escape_key(self, _event: object) -> None:
        if self._find_bar_visible:
            self._hide_find_bar()

    # ---------------- analysis run ----------------

    def _on_run_analysis_click(self) -> None:
        """Upload the log and run a fresh analysis of it in the background."""
        client = self._client
        if self._analysis_runner.active or client is None:
            return

        logfile = Path(self.logfile)
        if not logfile.is_file():
            messagebox.showerror(
                _("Skybrush Log Analysis"),
                _("Log file not found: {path}").format(path=self.logfile),
                parent=self.root,
            )
            return

        self._run_analysis_button.configure(state="disabled")
        self._set_status(_("Uploading log and running analysis through the Skybrush API - this can take a while"))
        self._analysis_runner.start(
            lambda _progress: compact(client.analyze(logfile)),
            None,
            lambda result, error: self._on_analysis_done(client, result, error),
        )

    def _on_analysis_done(self, client: APIClient, result: object | None, error: Exception | None) -> None:
        self._update_action_buttons()
        if client is not self._client:
            return
        if error is not None:
            logging_error(_("%s Skybrush API analysis failed: %s"), _LOG_TAG, error)
            self._show_analysis_error(_skybrush_error_message(error))
            self._end_session_if_rejected(error)
            return
        self._display_analysis_results(cast("dict[str, Any]", result))
        self._set_status(_("Analysis completed"))
        # Successful server communication: silently retry a header version check that failed earlier.
        self._retry_pending_version_check()

    # ---------------- login / logout ----------------

    def _update_login_state(self) -> None:
        """Sync the header buttons and the login form or results view with the authentication state."""
        self._logout_button.configure(state="normal" if self._client is not None else "disabled")
        self._update_action_buttons()
        if self._client is not None:
            self._login_form.pack_forget()
            self._results_row.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=20, pady=(0, 8))
        else:
            self._hide_find_bar()
            self._results_row.pack_forget()
            self._login_form.pack(side=tk.TOP, anchor=tk.N, padx=20, pady=(24, 8))
            self._login_form.focus_key_entry()

    def _update_action_buttons(self) -> None:
        """Enable the Skybrush service buttons only when logged in; in-flight buttons stay disabled."""
        state = "normal" if self._client is not None else "disabled"
        if not self._analysis_runner.active:
            self._run_analysis_button.configure(state=state)
        if not self._web_login_runner.active:
            self._open_web_button.configure(state=state)
        if not self._feedback_runner.active:
            self._feedback_button.configure(state=state)

    def _start_login(self, api_key: str, on_done: Callable[[object | None, Exception | None], None]) -> bool:
        """Start logging in with the API key in the background; False when a login is already running."""
        if self._login_runner.active:
            return False
        config_dir = self._config.config_dir

        def on_login_done(result: object | None, error: Exception | None) -> None:
            if error is None:
                self._client = cast("APIClient", result)
                self._config = self._client.config
                self._update_login_state()
                self._set_status(_("Logged in to the Skybrush Account"))
                self._start_header_status_checks()
            on_done(result, error)

        return self._login_runner.start(lambda _progress: APIClient.login(config_dir, api_key), None, on_login_done)

    def _apply_logout(self) -> None:
        """End the log-in session, removing the stored API key and token."""
        if self._client is None:
            return
        try:
            self._client.logout()
        except ConfigError as error:
            messagebox.showerror(_("Skybrush Log Analysis"), _skybrush_error_message(error), parent=self.root)
        # The client is invalidated even when removing the stored API key failed.
        self._set_logged_out(Unauthenticated())
        self._set_status(_("Logged out"))

    def _end_session_if_rejected(self, error: Exception) -> None:
        """Switch to the logged-out state when the error shows that the log-in is no longer accepted."""
        if isinstance(error, (Unauthenticated, InvalidAPIKey)):
            self._set_logged_out(error)

    def _set_logged_out(self, reason: Exception) -> None:
        """Drop the log-in session and show the login form, with the reason in the header."""
        self._client = None
        self._version_info = {}
        self._update_login_state()
        self._set_status("")
        self._version_label.configure(text=_("Skybrush API version: requires logging in"), foreground="gray50")
        self._set_auth_status(_skybrush_error_message(reason), "red3")

    # ---------------- browser links ----------------

    def _on_open_in_browser_click(self) -> None:
        """Open the analysis of the selected log in the Skybrush Log Analyzer in the default browser."""
        client = self._client
        if self._web_login_runner.active or client is None:
            return

        self._open_web_button.configure(state="disabled")
        self._set_status(_("Requesting a log-in link for the Skybrush Log Analyzer web application"))
        self._web_login_runner.start(
            lambda _progress: self._fetch_web_login_url(client),
            None,
            lambda result, error: self._on_web_login_done(client, result, error),
        )

    def _fetch_web_login_url(self, client: APIClient) -> str:
        """Acquire a single-sign-on URL for the Skybrush Log Analyzer, deep-linking to this log's analysis."""
        try:
            intent = client.get_analysis_view_intent(Path(self.logfile))
        except NotFound:
            # No stored analysis for this log within the account; open the generic analyzer view.
            intent = None
        return client.get_web_login_url(intent=intent)

    def _on_web_login_done(self, client: APIClient, result: object | None, error: Exception | None) -> None:
        self._update_action_buttons()
        if client is not self._client:
            return
        if error is not None:
            logging_error(_("%s Could not acquire a Skybrush web log-in link: %s"), _LOG_TAG, error)
            self._set_status("")
            messagebox.showerror(_("Skybrush Log Analysis"), _skybrush_error_message(error), parent=self.root)
            self._end_session_if_rejected(error)
            return
        # Acquiring the login link proves the server was reached; retry a pending header version check.
        self._retry_pending_version_check()
        if webbrowser_open_url(cast("str", result)):
            self._set_status(_("Skybrush Log Analyzer opened in the default browser"))
        else:
            messagebox.showerror(
                _("Skybrush Log Analysis"),
                _("Could not open the default web browser."),
                parent=self.root,
            )

    # ---------------- header status checks ----------------

    def _start_header_status_checks(self) -> None:
        """Fill the header version and log-in labels; the version is fetched in the background."""
        client = self._client
        if client is not None:
            self._version_label.configure(text=_("Fetching Skybrush API version..."))
            if not self._auth_runner.start(
                lambda _progress: client.version(),
                None,
                lambda result, error: self._on_version_auth_done(client, result, error),
            ):
                self._set_auth_status("", "gray50")
        else:
            self._set_logged_out(Unauthenticated())

    def _retry_pending_version_check(self) -> None:
        """Retry the header version/log-in check after any successful server communication."""
        if not self._version_info and not self._auth_runner.active:
            self._start_header_status_checks()

    def _on_version_auth_done(self, client: APIClient, result: object | None, error: Exception | None) -> None:
        if client is not self._client:
            # The check of the current session could not start while this one was running.
            if self._client is not None:
                self._start_header_status_checks()
            return
        if error is not None:
            logging_error(_("%s Skybrush log-in or API version check failed: %s"), _LOG_TAG, error)
            self._version_label.configure(text=_("Skybrush API version unknown"), foreground="gray50")
            self._set_auth_status(_skybrush_error_message(error), "red3")
            self._end_session_if_rejected(error)
            return
        self._version_info = cast("dict[str, Any]", result)
        self._version_label.configure(text=_format_api_version(self._version_info), foreground="")
        self._set_auth_status(_("Authenticated at {account_url}").format(account_url=self._config.account_url), "dark green")

    def _set_auth_status(self, text: str, color: str) -> None:
        """Set the header log-in status line with its severity color."""
        self._auth_status_label.configure(text=text, foreground=color)

    # ---------------- feedback ----------------

    def _on_send_feedback_click(self) -> None:
        """Open the feedback dialog."""
        FeedbackDialog(self.root, self._start_suggestion).show()

    def _start_suggestion(
        self,
        category: "SuggestionCategory",
        title: str,
        description: str,
        on_done: Callable[[object | None, Exception | None], None],
    ) -> bool:
        """Submit the suggestion through the Skybrush API in the background."""
        client = self._client
        version_info = self._version_info

        def on_suggestion_done(result: object | None, error: Exception | None) -> None:
            on_done(result, error)
            self._update_action_buttons()
            if client is not self._client:
                return
            if error is None:
                # A submitted suggestion proves the server was reached; use it to retry a pending version check.
                self._retry_pending_version_check()
            else:
                self._end_session_if_rejected(error)

        if self._feedback_runner.active or client is None:
            return False
        self._feedback_button.configure(state="disabled")
        return self._feedback_runner.start(
            lambda _progress: self._submit_suggestion(client, version_info, category, title, description),
            None,
            on_suggestion_done,
        )

    def _submit_suggestion(
        self, client: APIClient, version_info: dict[str, Any], category: "SuggestionCategory", title: str, description: str
    ) -> dict[str, Any]:
        """Send the suggestion with the log name, log hash and version details appended. Worker thread."""
        content_lines = [description, "", "---"]
        content_lines.append(_("ArduPilot Methodic Configurator {version}").format(version=__version__))
        logfile = Path(self.logfile)
        if logfile.is_file():
            content_lines.append(_("Flight log: {filename}").format(filename=logfile.name))
            with suppress(OSError):
                content_lines.append(_("Log file SHA-256: {hash}").format(hash=calculate_file_hash(logfile)))
        if version_info:
            content_lines.append(_format_api_version(version_info))
        return client.suggest(category=category, title=title, content="\n".join(content_lines))

    # ---------------- results rendering ----------------

    def _show_analysis_error(self, message: str) -> None:
        self._set_status("")
        self._replace_results_text()
        self._append_results_text(message + "\n", "error")
        self._finish_results_text()
        messagebox.showerror(_("Skybrush Log Analysis"), message, parent=self.root)

    def _display_analysis_results(self, view: dict[str, Any]) -> None:
        """Render the compact analysis view into the results text window."""
        self._replace_results_text()

        note_title = view.get("note_title")
        if note_title:
            self._append_results_text(str(note_title) + "\n", "heading")
        note_description = view.get("note_description")
        if note_description:
            self._append_results_text(str(note_description) + "\n\n")

        counts: dict[str, int] = view["status_counts"]
        if counts:
            self._append_status_counts(counts)

        test_results = view["test_results"]
        if not test_results:
            self._append_results_text(_("No test results were returned by the analysis.\n"), "muted")
        for result in test_results:
            self._append_result(result)

        self._finish_results_text()

    def _append_status_counts(self, counts: dict[str, int]) -> None:
        """Append the summary line, coloring each 'STATUS: n' segment with its status color."""
        self._append_results_text(_("Test cases: "), "summary")
        for index, (status, count) in enumerate(counts.items()):
            if index:
                self._append_results_text(", ", "summary")
            self._append_results_text(f"{status}: {count}", f"summary status_{status}")
        self._append_results_text("\n\n", "summary")

    def _append_result(self, result: dict[str, Any]) -> None:
        status = str(result.get("status") or "UNKNOWN")
        name = str(result.get("test_name") or "").removeprefix("paplan.tests.").removeprefix("paplan.tests:")
        title = result.get("title")
        line = f"[{status}] {name}"
        if isinstance(title, str) and title:
            line += f" - {title}"
        color_tag = f"status_{status}" if status in _STATUS_COLOR else "muted"
        self._append_results_text(line + "\n", color_tag)
        for message in result.get("messages") or []:
            # Each answer line carries its own severity: color it like the status line would be.
            severity = str(message.get("severity") or "").upper()
            severity_tag = f"status_{severity}" if severity in _STATUS_COLOR else "bullet"
            plain, bold = _format_test_message(message)
            self._append_results_text(f"    \u2022 {plain}", severity_tag)
            if bold:
                self._append_results_text(bold, f"{severity_tag} bold")
            self._append_results_text("\n", severity_tag)
        self._append_results_text("\n")
